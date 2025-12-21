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


LOGO_PATH = "media/images/EscapGo_circ_logo_transparent.png"
VIDEO_PATH = "media/videos/reel.mp4"
MARKET = "PMI"

print("🔧 Levantando servicios (web + Telegram)...")
proc = rn.start_services()  # si devuelve algo tipo Popen, queda en background


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
def pick_main_candidate(min_discount_pct=40.0):
    start, end = choose_random_search_window()
    print(f"🔎 Buscando vuelos entre {start} y {end}")

    flights = ag.get_flights_in_period(start, end)
    print(f"   {len(flights)} vuelos encontrados")

    flights = [f for f in flights if not is_recently_published(f)]
    print(f"   {len(flights)} tras filtrar publicados")

    if not flights:
        raise RuntimeError("No hay vuelos nuevos")

    best_by_cat = ag.get_best_by_category_scored(
        flights, min_discount_pct=min_discount_pct
    )

    if not best_by_cat:
        raise RuntimeError("No hay vuelos con descuento suficiente")

    main_item = ag.choose_main_candidate_prob(best_by_cat)
    return main_item, best_by_cat, flights


# ----------------------------------------------
# 3–4) Generar VIDEO + CAPTION
# ----------------------------------------------
def build_video_and_caption(main_item):
    main_flight: Flight = main_item["flight"]
    main_category_code = (
        main_item.get("category_code")
        or main_item.get("category", {}).get("code")
    )

    # 3) CAPTION
    importlib.reload(cb)
    caption_text = cb.build_caption_for_flight(
        main_flight,
        category_code=main_category_code,
        tone="emocional",
    )


    #     # VIDEO HOOK determinístico (sin destino/fechas/precio explícitos)
    # video_hook = build_video_hook(
    #     category_code=str(main_category_code),
    #     discount_pct=getattr(main_flight, "discount_pct", None),
    #     price=getattr(main_flight, "price", None),
    #     start_date=str(getattr(main_flight, "start_date", ""))[:10],
    #     end_date=str(getattr(main_flight, "end_date", ""))[:10],
    #     origin=getattr(main_flight, "origin", None),
    #     destination=getattr(main_flight, "destination", None),
    # )

    video_hook = vh.build_video_hook_curiosity(
        category_label=str(main_category_code),            # "Escapada cultural", etc.
        country=get_country(main_flight.destination),       # "Reino Unido", "Italia"...
        discount_pct=getattr(main_flight, "discount_pct", None),
        price=getattr(main_flight, "price", None),
        start_date=str(main_flight.start_date)[:10],
        end_date=str(main_flight.end_date)[:10],
        max_len=44,
    )
    print("HOOK QUE VOY A PINTAR:\n", video_hook)
    
    # 4) VIDEO (local para review)
    importlib.reload(vg)
    video_path_or_url, variant_used = rab.create_reel_for_flight_ab(
        main_flight,
        out_mp4_path=VIDEO_PATH,
        logo_path=LOGO_PATH,
        duration=6.0,
        s3_bucket=None,
        hook_text=video_hook,     # solo se usa si sale "new"
        hook_mode="band",         # solo se usa si sale "new"
        variant="auto",           # auto / new / old
        ratio_new=0.5,            # 50/50
        key_mode="route_dates",   # estable por vuelo
    )
    print("AB variant:", variant_used)

    return main_flight, main_category_code, caption_text


# ----------------------------------------------
# 5) Enviar a review Telegram (local mp4)
#   👉 Aquí reordenamos candidatos para que el main
#      quede SIEMPRE en índice 0.
# ----------------------------------------------
def send_to_review(main_item, best_by_cat, caption_text):
    main_flight: Flight = main_item["flight"]
    main_cat_code = (
        main_item.get("category_code")
        or main_item.get("category", {}).get("code")
    )

    job_id = str(uuid.uuid4())

    # 5.1) Convertimos todos a candidatos para Telegram
    review_candidates = tr.to_review_candidates(best_by_cat)

    # 5.2) Buscamos qué índice de best_by_cat corresponde al main
    main_idx = 0
    for i, item in enumerate(best_by_cat):
        item_flight = item["flight"]
        item_cat_code = (
            item.get("category_code")
            or item.get("category", {}).get("code")
        )
        if item_flight is main_flight and item_cat_code == main_cat_code:
            main_idx = i
            break

    # 5.3) Reordenamos para que el principal quede en posición 0
    if main_idx != 0:
        print(f"ℹ️ Reordenando candidatos: main_idx={main_idx} pasa a 0")
        review_candidates[0], review_candidates[main_idx] = (
            review_candidates[main_idx],
            review_candidates[0],
        )

    # 5.4) Registrar job: current_index arranca en 0 -> main candidate
    tr.register_job(
        job_id=job_id,
        flight=main_flight,
        caption=caption_text,
        video_path=Path(VIDEO_PATH),
        candidates=review_candidates,
    )

    tr.send_review_candidate(job_id)
    print(f"📲 Enviado a review. job_id={job_id}")

    return job_id


# ----------------------------------------------
# 6–7–8) Publicar en IG, actualizar web, registrar histórico
# (esta función queda para modo auto_publish futuro)
# ----------------------------------------------
def publish_to_instagram_and_update_web(main_item, caption_text):
    main_flight: Flight = main_item["flight"]

    print("📤 Subiendo vídeo a S3 para Instagram...")
    video_url = vg.upload_reel_to_s3(
        VIDEO_PATH,
        bucket="escapadasgo-reels",
        prefix="pmi/",
    )

    print("📤 Publicando en Instagram...")
    ig = InstagramClient()

    creation_id = ig.create_reel_container(video_url=video_url, caption=caption_text)
    if not ig.wait_until_ready(creation_id):
        print("❌ Instagram no procesó el vídeo")
        return

    reel_id = ig.publish_reel(creation_id)
    permalink = ig.get_media_permalink(reel_id)
    print(f"   ✔ Publicado: {permalink}")

    print("🗂 Actualizando web...")
    affiliate_url = af.build_affiliate_url_for_flight(main_flight)

    data = ex.update_flights_json(
        main_item=main_item,
        json_path="local_copy.json",
        market=MARKET,
        reel_url=permalink,
        affiliate_url=affiliate_url,
        max_entries=5,
    )

    up.upload_flights_json(data, key=f"{MARKET.lower()}/flights_of_the_day.json")
    print("   ✔ Web actualizada")

    register_publication(main_flight, category_code=main_item.get("category_code"))
    print("📝 Histórico actualizado")




def run_daily_workflow(auto_publish=False):
    """
    Orquestador principal.
    - auto_publish=False → modo actual: genera y envía a Telegram, NO publica ni actualiza S3.
    - auto_publish=True  → hace toda la pipeline hasta IG + S3 + histórico.
    """
    print("🚀 Lanzando daily workflow Escapadas GO (Mallorca)...")

    # Si quisieras levantar servicios:
    # print("🔧 Levantando servicios (web + Telegram)...")
    # proc = rn.start_services()

    min_discount_pct = 40
    auto_publish = False  # de momento sólo modo review

    try:
        # 2) Buscar vuelos y elegir main candidate
        main_item, best_by_cat, flights = pick_main_candidate(
            min_discount_pct=min_discount_pct
        )
        main_flight: Flight = main_item["flight"]
        print(
            f"✅ Candidato principal: {main_flight.origin} → {main_flight.destination} "
            f"{main_flight.start_date[:10]} – {main_flight.end_date[:10]} "
            f"@ {getattr(main_flight, 'price', '?')} €"
        )

        # 3 + 4) Vídeo + caption
        main_flight, main_category_code, caption_text = build_video_and_caption(
            main_item
        )

        # 5) Mandar a review (flujo actual)
        job_id = send_to_review(main_item, best_by_cat, caption_text)

        if auto_publish:
            # FUTURO: publicación automática sin review
            publish_to_instagram_and_update_web(main_item, caption_text)
        else:
            print(
                "ℹ️ Modo revisión activado: la publicación en IG + S3 se hará desde el flujo de Telegram."
            )

    finally:
        # Aquí podrías cerrar servicios si usas rn.start_services()
        pass


if __name__ == "__main__":
    # Ahora mismo en modo "review": genera vídeo + caption y los manda a Telegram.
    run_daily_workflow(auto_publish=False)