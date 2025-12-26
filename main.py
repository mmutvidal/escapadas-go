import random
import uuid
import importlib
from pathlib import Path
from datetime import date, timedelta

import run_services as rn
import flights.aggregator as ag
import media.video_generator as vg
import content.caption_builder as cb
import review.telegram_review as tr
from instagram.ig_client import InstagramClient
import affiliates.affiliates as af
import web.exporter as ex
import web.uploader as up
from flights.base import Flight
from flights.published_history import is_recently_published, register_publication
# from content.video_hook import build_video_hook
# import content.video_hook_premium as vh
from content.destinations import get_country
import content.video_hook_curiosity as vh
import media.reel_ab as rab
from config.markets import MARKETS
import argparse
from flights.published_history import make_flight_key

# LOGO_PATH = "media/images/EscapGo_circ_logo_transparent.png"
# VIDEO_PATH = "media/videos/reel.mp4"
# MARKET = "PMI"


# ----------------------------------------------
# 1) Ventana aleatoria: hoy → random(2–6 meses)
# ----------------------------------------------
def choose_random_search_window(min_months=1, max_months=1):
    today = date.today()
    months = random.randint(min_months, max_months)
    offset_days = months * 30
    end = today + timedelta(days=offset_days)
    return today, end


# ----------------------------------------------
# 2) Elegir main candidate
# ----------------------------------------------
def pick_main_candidate(cfg, min_discount_pct=40.0):
    start, end = choose_random_search_window()
    print(f"🔎 [{cfg.code}] Buscando vuelos entre {start} y {end}")

    flights = ag.get_flights_in_period(start, end, cfg.origin_iata)  # ✅ origin
    print(f"   {len(flights)} vuelos encontrados")

    flights = [
        f for f in flights
        if not is_recently_published(
            f,
            cooldown_days=14,
            route_cooldown_days=5
        )
    ]
    print(f"   {len(flights)} tras filtrar publicados")

    if not flights:
        raise RuntimeError(f"[{cfg.code}] No hay vuelos nuevos")

    best_by_cat = ag.get_best_by_category_scored(
        flights, min_discount_pct=min_discount_pct
    )

    if not best_by_cat:
        raise RuntimeError(f"[{cfg.code}] No hay vuelos con descuento suficiente")

    main_item = ag.choose_main_candidate_prob(best_by_cat)
    return main_item, best_by_cat, flights


# ----------------------------------------------
# 3–4) Generar VIDEO + CAPTION
# ----------------------------------------------
def build_video_and_caption(cfg, main_item):
    main_flight: Flight = main_item["flight"]
    main_category_code = (
        main_item.get("category_code")
        or main_item.get("category", {}).get("code")
    )

    brand_handle = cfg.ig_handle

    
    # importlib.reload(cb)
    caption_text = cb.build_caption_for_flight(
        main_flight,
        category_code=main_category_code,
        tone="emocional",
        brand_handle=cfg.ig_handle,   # 👈 si tu caption_builder lo soporta
    )

    video_hook = vh.build_video_hook_curiosity(
        category_label=str(main_category_code),
        country=get_country(main_flight.destination),
        discount_pct=getattr(main_flight, "discount_pct", None),
        price=getattr(main_flight, "price", None),
        start_date=str(main_flight.start_date)[:10],
        end_date=str(main_flight.end_date)[:10],
        max_len=44,
    )

    # importlib.reload(vg)
    video_path_or_url, variant_used, origin_pill_variant = rab.create_reel_for_flight_ab(
        main_flight,
        out_mp4_path=cfg.video_path,
        logo_path=cfg.logo_path,
        duration=6.0,
        brand_line=brand_handle,
        s3_bucket=None,
        hook_text=video_hook,
        hook_mode="band",
        variant="auto",
        ratio_new=cfg.ab_ratio_new,
        key_mode="route_dates",
        origin_pill_ab_ratio=1,  # ✅ pill A/B 50/50 (ajústalo si quieres por market)
    )
    
    print("AB variant:", variant_used, "| origin pill:", origin_pill_variant)

    combined_variant = f"{variant_used}|{origin_pill_variant}"

    
    # guarda para telegram_review
    main_item["video_hook"] = video_hook
    main_item["variant_used"] = combined_variant
    main_item["origin_pill_variant"] = origin_pill_variant

    return main_flight, main_category_code, caption_text


# ----------------------------------------------
# 5) Enviar a review Telegram (local mp4)
#   👉 Aquí reordenamos candidatos para que el main
#      quede SIEMPRE en índice 0.
# ----------------------------------------------
def send_to_review(cfg, main_item, best_by_cat, caption_text):
    main_flight: Flight = main_item["flight"]
    main_cat_code = (
        main_item.get("category_code")
        or main_item.get("category", {}).get("code")
    )

    job_id = str(uuid.uuid4())
    review_candidates = tr.to_review_candidates(best_by_cat)

    main_key = make_flight_key(main_flight)
    main_idx = 0
    for i, item in enumerate(best_by_cat):
        item_flight = item["flight"]
        item_cat_code = (
            item.get("category_code")
            or item.get("category", {}).get("code")
        )
        if make_flight_key(item_flight) == main_key and item_cat_code == main_cat_code:
            main_idx = i
            break

    if main_idx != 0:
        print(f"ℹ️ Reordenando candidatos: main_idx={main_idx} pasa a 0")
        review_candidates[0], review_candidates[main_idx] = (
            review_candidates[main_idx],
            review_candidates[0],
        )

    tr.register_job(
        job_id=job_id,
        market=cfg.code,
        ig_handle=cfg.ig_handle,
    
        # ✅ Publicación en la cuenta correcta (por market)
        ig_user_id=cfg.ig_user_id,
        page_token=cfg.page_token,
    
        # ✅ Prefijos por market
        s3_prefix_reels=cfg.s3_reels_prefix,   # cfg.s3_reels_prefix -> register_job.s3_prefix_reels
        web_key_prefix=cfg.web_key_prefix,
    
        # ✅ Branding & AB
        logo_path=cfg.logo_path,
        ab_ratio_new=cfg.ab_ratio_new,
    
        # ✅ Resto como ya lo tenías
        flight=main_flight,
        caption=caption_text,
        video_path=Path(cfg.video_path),
        candidates=review_candidates,
        video_hook=main_item.get("video_hook"),
        variant=main_item.get("variant_used")
    )

    tr.send_review_candidate(job_id)
    print(f"📲 [{cfg.code}] Enviado a review. job_id={job_id}")
    return job_id


# ----------------------------------------------
# 6–7–8) Publicar en IG, actualizar web, registrar histórico
# (esta función queda para modo auto_publish futuro)
# ----------------------------------------------
def publish_to_instagram_and_update_web(cfg, main_item, caption_text):
    main_flight = main_item["flight"]

    print("📤 Subiendo vídeo a S3 para Instagram...")
    video_url = vg.upload_reel_to_s3(
        cfg.video_path,                 # ✅ por market
        bucket="escapadasgo-reels",
        prefix=cfg.s3_reels_prefix,     # ✅ pmi/ bcn/ ...
    )

    print("📤 Publicando en Instagram...")
    ig = InstagramClient(
        ig_user_id=cfg.ig_user_id,
        page_token=cfg.page_token,
    )

    creation_id = ig.create_reel_container(video_url=video_url, caption=caption_text)
    if not ig.wait_until_ready(creation_id):
        print("❌ Instagram no procesó el vídeo")
        return None

    print(f"[PUBLISH] market={cfg.code} handle={cfg.ig_handle} ig_user_id={cfg.ig_user_id} token_suffix={cfg.page_token[-10:]}")
    
    reel_id = ig.publish_reel(creation_id)
    permalink = ig.get_media_permalink(reel_id)
    print(f"   ✔ Publicado: {permalink}")

    print("🗂 Actualizando web...")
    affiliate_url = af.build_affiliate_url_for_flight(main_flight)

    # ✅ JSON path por market (tú decides estructura)
    json_path = cfg.web_json_path  # ej: "web/mallorca/flights_of_the_day.json" o "web/es/..."

    data = ex.update_flights_json(
        main_item=main_item,
        json_path=json_path,
        market=cfg.code,                 # ✅ market real
        reel_url=permalink,
        affiliate_url=affiliate_url,
        max_entries=5,
    )

    # ✅ subida S3 con key por market/prefix
    up.upload_flights_json(data, key=f"{cfg.web_key_prefix}flights_of_the_day.json")

    print("   ✔ Web actualizada")

    register_publication(main_flight, category_code=main_item.get("category_code"))
    print("📝 Histórico actualizado")

    return permalink




# def run_daily_workflow(auto_publish=False):
#     """
#     Orquestador principal.
#     - auto_publish=False → modo actual: genera y envía a Telegram, NO publica ni actualiza S3.
#     - auto_publish=True  → hace toda la pipeline hasta IG + S3 + histórico.
#     """
#     print("🚀 Lanzando daily workflow Escapadas GO (Mallorca)...")

#     # Si quisieras levantar servicios:
#     # print("🔧 Levantando servicios (web + Telegram)...")
#     # proc = rn.start_services()

#     min_discount_pct = 40
#     auto_publish = False  # de momento sólo modo review

#     try:
#         # 2) Buscar vuelos y elegir main candidate
#         main_item, best_by_cat, flights = pick_main_candidate(
#             min_discount_pct=min_discount_pct
#         )
#         main_flight: Flight = main_item["flight"]
#         print(
#             f"✅ Candidato principal: {main_flight.origin} → {main_flight.destination} "
#             f"{main_flight.start_date[:10]} – {main_flight.end_date[:10]} "
#             f"@ {getattr(main_flight, 'price', '?')} €"
#         )

#         # 3 + 4) Vídeo + caption
#         main_flight, main_category_code, caption_text = build_video_and_caption(
#             main_item
#         )

#         # 5) Mandar a review (flujo actual)
#         job_id = send_to_review(main_item, best_by_cat, caption_text)

#         if auto_publish:
#             # FUTURO: publicación automática sin review
#             publish_to_instagram_and_update_web(main_item, caption_text)
#         else:
#             print(
#                 "ℹ️ Modo revisión activado: la publicación en IG + S3 se hará desde el flujo de Telegram."
#             )

#     finally:
#         # Aquí podrías cerrar servicios si usas rn.start_services()
#         pass

def run_daily_workflow(cfg, auto_publish=False):
    print(f"🚀 Daily workflow market={cfg.code} origin={cfg.origin_iata}")

    main_item, best_by_cat, flights = pick_main_candidate(
        cfg=cfg,
        min_discount_pct=cfg.min_discount_pct,
    )

    main_flight, main_category_code, caption_text = build_video_and_caption(
        cfg=cfg,
        main_item=main_item,
    )

    job_id = send_to_review(cfg, main_item, best_by_cat, caption_text)
    return job_id


def parse_markets_arg(s: str):
    if not s:
        return list(MARKETS.keys())
    parts = [p.strip().upper() for p in s.split(",") if p.strip()]
    return parts


if __name__ == "__main__":
    print("🔧 Levantando servicios (web + Telegram)...")
    proc = rn.start_services()  # UNA VEZ

    ap = argparse.ArgumentParser()
    ap.add_argument("--markets", default="PMI,BCN,MAD,VLC", help="Comma-separated markets")
    ap.add_argument("--auto_publish", action="store_true")
    args = ap.parse_args()

    markets = parse_markets_arg(args.markets)

    for m in markets:
        cfg = MARKETS[m]
        try:
            run_daily_workflow(cfg, auto_publish=args.auto_publish)
        except Exception as e:
            print(f"❌ Error en market {m}: {e}")