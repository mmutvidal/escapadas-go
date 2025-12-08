import random
import uuid
import importlib
from pathlib import Path
from datetime import date, timedelta

import run_services as rn          # o de donde tengas start_services()
import flights.aggregator as ag                   # get_flights_in_period, get_best_by_category_scored, choose_main_candidate_prob
import media.video_generator as vg
import content.caption_builder as cb
import review.telegram_review as tr
from instagram.ig_client import InstagramClient
import affiliates.affiliates as af
import web.exporter as ex
import web.uploader as up
from flights.base import Flight
from flights.published_history import is_recently_published, register_publication  # :contentReference[oaicite:0]{index=0}


LOGO_PATH = "media/images/EscapGo_circ_logo_transparent.png"
VIDEO_PATH = "media/videos/reel.mp4"

# Si sirves el vídeo por HTTP (ngrok, etc.) para Instagram:
PUBLIC_VIDEO_URL = "https://TU-DOMINIO/media/videos/reel.mp4"

MARKET = "PMI"   # más adelante puedes parametrizarlo


# 1) Elegir ventana de fechas aleatoria entre 2 y 6 meses
def choose_random_search_window(min_months=2, max_months=6, span_days=15):
    """
    Devuelve (start_date, end_date) para buscar vuelos.
    start = hoy + random(2–6 meses aprox)
    end   = start + span_days
    """
    today = date.today()
    # aproximamos "mes" como 30 días para no depender de dateutil
    offset_days = random.randint(min_months * 30, max_months * 30)
    start = today + timedelta(days=offset_days)
    end = start + timedelta(days=span_days)
    return start, end


def pick_main_candidate(min_discount_pct=40.0):
    """
    2) Busca vuelos, filtra publicados recientemente y elige el mejor por categoría.
    Devuelve (main_item, best_by_cat_filtrado)
    """
    start, end = choose_random_search_window()
    print(f"🔎 Buscando vuelos entre {start} y {end}...")

    flights = ag.get_flights_in_period(start, end)
    print(f"   Encontrados {len(flights)} vuelos en bruto")

    # Filtramos los que ya se han publicado recientemente (mismas fechas y ruta)
    flights = [f for f in flights if not is_recently_published(f)]
    print(f"   {len(flights)} vuelos tras filtrar publicados recientemente")

    if not flights:
        raise RuntimeError("No hay vuelos nuevos en esta ventana de fechas")

    # Calculamos score por categoría
    best_by_cat = ag.get_best_by_category_scored(
        flights,
        min_discount_pct=min_discount_pct,
    )
    if not best_by_cat:
        raise RuntimeError("No hay vuelos que cumplan el descuento mínimo")

    main_item = ag.choose_main_candidate_prob(best_by_cat)
    return main_item, best_by_cat


def build_video_and_caption(main_item):
    """
    3) Genera vídeo
    4) Genera caption
    Devuelve (main_flight, main_category_code, caption_text)
    """
    main_flight: Flight = main_item["flight"]
    main_category_code = main_item.get("category_code") or getattr(main_flight, "category_code", None)

    # 3) Vídeo
    importlib.reload(vg)
    print("🎬 Generando vídeo...")
    vg.create_reel_for_flight(
        main_flight,
        out_mp4_path=VIDEO_PATH,
        logo_path=LOGO_PATH,
        duration=4.0,
    )
    print(f"   Vídeo generado en {VIDEO_PATH}")

    # 4) Caption
    importlib.reload(cb)
    print("✍️ Generando caption...")
    caption_text = cb.build_caption_for_flight(
        main_flight,
        category_code=main_category_code,
        tone="emocional",
    )
    print("   Caption generado")

    return main_flight, main_category_code, caption_text


def send_to_review(main_item, best_by_cat, caption_text):
    """
    5) Mandar a review por Telegram.
    """
    main_flight: Flight = main_item["flight"]

    job_id = str(uuid.uuid4())
    local_video_path = Path(VIDEO_PATH)
    review_candidates = tr.to_review_candidates(best_by_cat)

    tr.register_job(
        job_id=job_id,
        flight=main_flight,
        caption=caption_text,
        video_path=local_video_path,
        candidates=review_candidates,
    )
    tr.send_review_candidate(job_id)
    print(f"📲 Enviado a Telegram para revisión. job_id={job_id}")

    return job_id


def publish_to_instagram_and_update_web(main_item, caption_text, video_url=PUBLIC_VIDEO_URL):
    """
    6) Publicar en Instagram
    7) Subir flights_of_the_day.json a S3
    8) Registrar publicación en histórico
    """
    main_flight: Flight = main_item["flight"]
    main_category_code = main_item.get("category_code") or getattr(main_flight, "category_code", None)

    # 6) Instagram
    print("📤 Publicando en Instagram...")
    ig = InstagramClient()

    creation_id = ig.create_reel_container(video_url=video_url, caption=caption_text)
    if not ig.wait_until_ready(creation_id):
        print("❌ No se pudo procesar el vídeo, no se publica en Instagram.")
        return

    reel_id = ig.publish_reel(creation_id)
    permalink = ig.get_media_permalink(reel_id)
    print("✅ Reel publicado:")
    print("   ID:", reel_id)
    print("   Permalink:", permalink)

    # 7) Actualizar flights_of_the_day.json y subir a S3
    print("🗂 Actualizando flights_of_the_day.json y subiendo a S3...")
    affiliate_url = af.build_affiliate_url_for_flight(main_flight)

    data = ex.update_flights_json(
        main_item=main_item,
        json_path="local_copy.json",
        market=MARKET,
        reel_url=permalink,        # mejor mandar al reel de IG que al mp4
        affiliate_url=affiliate_url,
        max_entries=5,
    )

    key = f"{MARKET.lower()}/flights_of_the_day.json"
    up.upload_flights_json(data, key=key)
    print(f"   JSON actualizado y subido a S3 con key={key}")

    # 8) Registrar en histórico para evitar repeticiones
    register_publication(main_flight, category_code=main_category_code or "")
    print("📝 Publicación registrada en published_deals.json")


def run_daily_workflow(auto_publish=False, video_url=PUBLIC_VIDEO_URL, min_discount_pct=40.0):
    """
    Orquestador principal.
    - auto_publish=False → modo actual: genera y envía a Telegram, NO publica ni actualiza S3.
    - auto_publish=True  → hace toda la pipeline hasta IG + S3 + histórico.
    """
    print("🚀 Lanzando daily workflow Escapadas GO (Mallorca)...")

    # 1) Levantar servicios web / bot
    print("🔧 Levantando servicios (web + Telegram)...")
    proc = rn.start_services()  # si devuelve algo tipo Popen, queda en background

    try:
        # 2) Buscar vuelos y elegir main candidate
        main_item, best_by_cat = pick_main_candidate(min_discount_pct=min_discount_pct)
        main_flight: Flight = main_item["flight"]
        print(f"✅ Candidato principal: {main_flight.origin} → {main_flight.destination} "
              f"{main_flight.start_date[:10]} – {main_flight.end_date[:10]} "
              f"@ {getattr(main_flight, 'price', '?')} €")

        # 3 + 4) Vídeo + caption
        main_flight, main_category_code, caption_text = build_video_and_caption(main_item)

        # 5) Mandar a review (siempre, mientras mantengas el paso de control humano)
        job_id = send_to_review(main_item, best_by_cat, caption_text)

        if auto_publish:
            # PUBLICACIÓN AUTOMÁTICA (cuando quieras eliminar el review o
            # mover la lógica del botón "Publicar" aquí)
            publish_to_instagram_and_update_web(main_item, caption_text, video_url=video_url)
        else:
            print("ℹ️ Modo revisión activado: la publicación en IG + S3 se hará desde el flujo de Telegram.")

    finally:
        # Si quieres cerrar servicios al terminar (opcional, depende de cómo funcione rn.start_services())
        # proc.terminate() o similar, si procede.
        pass


if __name__ == "__main__":
    # Ahora mismo en modo "review": genera vídeo + caption y los manda a Telegram.
    run_daily_workflow(auto_publish=False)