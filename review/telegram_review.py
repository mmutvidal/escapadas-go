import re
from datetime import date, timedelta
from telegram.ext import MessageHandler, Filters

import os
import json
from pathlib import Path
from typing import Dict, Any, List
import uuid
from telegram import Bot, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Updater, CallbackQueryHandler, CommandHandler

from instagram.ig_client import InstagramClient
# from storage.uploader import get_public_url

# IMPORTS NUEVOS: usa los que ya tienes en tu proyecto
import content.caption_builder as cb
import media.video_generator as vg
import flights.aggregator as ag

import affiliates.affiliates as af
import web.exporter as ex
import web.uploader as up
from flights.published_history import register_publication

from config.settings import BOT_TOKEN,REVIEW_CHAT_ID 

S3_BUCKET_REELS = "escapadasgo-reels"
S3_PREFIX_REELS = "pmi/"   # si algún día tienes más markets, lo paramos


MARKET = "PMI"  # más adelante lo podrás hacer dinámico

LOGO_PATH = "media/images/EscapGo_circ_logo_transparent.png"

# Carpeta para guardar los jobs en disco (compartida entre procesos)
JOBS_DIR = Path("review_jobs")
JOBS_DIR.mkdir(exist_ok=True)

# Opcional: cache en memoria (solo útil dentro de cada proceso)
PENDING_JOBS: Dict[str, Dict[str, Any]] = {}


def _job_path(job_id: str) -> Path:
    return JOBS_DIR / f"{job_id}.json"


def _serialize_job(job: Dict[str, Any]) -> Dict[str, Any]:
    """
    Convertimos objetos no serializables (Path, etc.) a strings.
    Ahora SÍ guardamos candidates y current_index.
    """
    return {
        "flight": None,  # si quieres, luego lo serializamos mejor
        "caption": job["caption"],
        "video_path": str(job["video_path"]),
        "candidates": job.get("candidates", []),
        "current_index": job.get("current_index", 0),
    }


def _deserialize_job(data: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "flight": None,  # opcional
        "caption": data["caption"],
        "video_path": Path(data["video_path"]),
        "candidates": data.get("candidates", []),
        "current_index": data.get("current_index", 0),
    }


def save_job(job_id: str, job: Dict[str, Any]) -> None:
    with _job_path(job_id).open("w", encoding="utf-8") as f:
        json.dump(_serialize_job(job), f, ensure_ascii=False, indent=2)


def load_job(job_id: str) -> Dict[str, Any] | None:
    path = _job_path(job_id)
    if not path.exists():
        return None
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    return _deserialize_job(data)


def delete_job(job_id: str) -> None:
    path = _job_path(job_id)
    if path.exists():
        path.unlink()


def to_review_candidates(best_by_cat):
    """
    Utilidad opcional: convertir la lista best_by_cat en candidatos JSON-friendly.
    Cada item de best_by_cat es:
      {"flight": Flight(...), "category": {"code":..., "label":...}, "score": ...}
    """
    candidates = []
    for item in best_by_cat:
        f = item["flight"]
        cat = item["category"]

        # opcional: solo fecha (YYYY-MM-DD)
        def only_date(dt_str):
            # si ya es "YYYY-MM-DD HH:MM:SS"
            return dt_str.split(" ")[0] if isinstance(dt_str, str) else str(dt_str)

        candidates.append({
            "category_code": cat["code"],
            "category_label": cat["label"],

            "origin": f.origin,
            "destination": f.destination,
            "start_date": only_date(f.start_date),
            "end_date": only_date(f.end_date),
            "price": float(f.price),
            "airline": f.airline,
            "link": f.link,

            # opcionales por si los quieres luego en caption:
            "distance_km": getattr(f, "distance_km", None),
            "price_per_km": getattr(f, "price_per_km", None),
            "score": item.get("score"),
            "discount_pct": getattr(f, "discount_pct", None),
            "route_typical_price": getattr(f, "route_typical_price", None),
        })
    return candidates


def register_job(job_id: str, flight, caption: str, video_path: Path, candidates=None):
    """
    Registrar un job de revisión. Se guarda en memoria (para este proceso)
    y en disco (para compartir con el bot de Telegram).

    'candidates' debe ser una lista de payloads de vuelo (por ejemplo los de
    to_review_candidates(best_by_cat)), empezando por el que ya has usado
    para generar este primer reel o incluyendo otros alternativos.
    """
    job = {
        "flight": flight,
        "caption": caption,
        "video_path": Path(video_path),
        "candidates": candidates or [],  # lista de dicts
        "current_index": 0,              # índice dentro de candidates
    }

    PENDING_JOBS[job_id] = job
    save_job(job_id, job)


def send_review_candidate(job_id: str):
    """
    Envía al Telegram de revisión el vídeo + caption con botones de Aprobado/Otro.
    Usa la info desde disco por si se llama desde otro proceso.
    """
    if not BOT_TOKEN or not REVIEW_CHAT_ID:
        raise ValueError("Faltan TELEGRAM_BOT_TOKEN o TELEGRAM_REVIEW_CHAT_ID en .env")

    bot = Bot(token=BOT_TOKEN)
    job = PENDING_JOBS.get(job_id) or load_job(job_id)
    if not job:
        raise ValueError(f"Job {job_id} no encontrado para enviar a revisión.")

    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ Publicar", callback_data=f"approve:{job_id}"),
            InlineKeyboardButton("🔁 Otro", callback_data=f"another:{job_id}"),
        ]
    ])

    with job["video_path"].open("rb") as f:
        # 1) Enviamos el vídeo con los botones, pero SIN caption
        bot.send_video(
            chat_id=REVIEW_CHAT_ID,
            video=f,
            reply_markup=keyboard,
            supports_streaming=True,
        )
    
    # 2) Enviamos el caption en un mensaje aparte
    bot.send_message(
        chat_id=REVIEW_CHAT_ID,
        text=job["caption"],
    )


# ---------- Helpers para "Otro" ----------

def _pick_next_candidate(job: dict) -> dict | None:
    candidates = job.get("candidates") or []
    if not candidates:
        return None

    idx = job.get("current_index", 0)
    idx = (idx + 1) % len(candidates)   # en vez de parar al final

    job["current_index"] = idx
    return candidates[idx]


def _get_current_candidate(job: Dict[str, Any]) -> Dict[str, Any] | None:
    """
    Devuelve el candidato actualmente seleccionado según current_index.
    """
    candidates: List[Dict[str, Any]] = job.get("candidates", [])
    if not candidates:
        return None
    idx = job.get("current_index", 0)
    if not (0 <= idx < len(candidates)):
        idx = 0
    return candidates[idx]


def _build_reel_for_candidate(candidate: Dict[str, Any]) -> tuple[str, Path]:
    """
    Regenera caption + vídeo para un candidato concreto (dict),
    usando la función genérica de video_generator.
    """
    # 1) Caption
    caption = cb.build_caption_for_flight(
        candidate,
        category_code=candidate.get("category_code"),
        tone="emocional",
    ).replace("\n\n\n", "\n\n")  # por si acaso

    # 2) Vídeo
    out_dir = Path("media/videos")
    out_dir.mkdir(parents=True, exist_ok=True)
    dest = candidate.get("destination", "XXX")
    # Podemos sobreescribir siempre reel.mp4 para simplificar
    out_path = out_dir / "reel.mp4"

    vg.create_reel_for_flight(
        flight=candidate,          # dict compatible con el helper
        out_mp4_path=str(out_path),
        logo_path=LOGO_PATH,
        duration=4.0,
    )

    return caption, out_path



# --------- Handlers ----------

def start(update, context):
    update.message.reply_text("Hola, te enviaré las escapadas para revisar 😄")


def handle_button(update, context):
    query = update.callback_query
    data = query.data  # "approve:<job_id>" o "another:<job_id>"

    try:
        action, job_id = data.split(":", 1)
    except ValueError:
        query.answer("Botón inválido.")
        return

    # Intentamos memoria, y si no, disco
    job = PENDING_JOBS.get(job_id) or load_job(job_id)
    if not job:
        query.answer("Este trabajo ya no existe.")
        return

    if action == "approve":
        query.answer("Publicando en Instagram…")
        # quitamos los botones para que no se vuelva a pulsar
        query.edit_message_reply_markup(reply_markup=None)

        # ✅ Candidato actualmente seleccionado
        cand = _get_current_candidate(job) or {}

        # ------------------------------------------------------------------
        # 1) Subir MP4 a S3 y publicar en Instagram
        # ------------------------------------------------------------------
        permalink = None
        video_url = None
        try:
            # 1.1) Subir el vídeo local actual a S3
            video_url = vg.upload_reel_to_s3(
                local_path=job["video_path"],   # Path o str
                bucket=S3_BUCKET_REELS,
                prefix=S3_PREFIX_REELS,
            )

            # 1.2) Crear contenedor de Reel en IG usando la URL de S3
            ig = InstagramClient()
            creation_id = ig.create_reel_container(
                video_url=video_url,
                caption=job["caption"],
            )

            # 1.3) Esperar a que IG procese el vídeo y publicar
            if ig.wait_until_ready(creation_id):
                reel_id = ig.publish_reel(creation_id)
                permalink = ig.get_media_permalink(reel_id)
                query.message.reply_text(f"✅ Reel publicado en Instagram:\n{permalink}")
            else:
                query.message.reply_text("❌ Instagram no ha podido procesar el vídeo.")
                PENDING_JOBS.pop(job_id, None)
                delete_job(job_id)
                return

        except Exception as e:
            query.message.reply_text(f"❌ Error publicando en Instagram: {e}")
            PENDING_JOBS.pop(job_id, None)
            delete_job(job_id)
            return

        # ------------------------------------------------------------------
        # 2) Actualizar flights_of_the_day.json + subir a S3
        # ------------------------------------------------------------------
        try:
            # Usamos SIEMPRE el candidato actual como base
            flight_for_affiliate = cand or job.get("flight") or {}

            # build_affiliate_url_for_flight ahora acepta Flight o dict
            affiliate_url = af.build_affiliate_url_for_flight(flight_for_affiliate)

            # Construimos un main_item mínimo para exporter.update_flights_json
            main_item = {
                "flight": cand or flight_for_affiliate,
                "category": {
                    "code": cand.get("category_code")
                            or getattr(flight_for_affiliate, "category_code", None),
                    "label": cand.get("category_label")
                             or getattr(flight_for_affiliate, "category_label", None),
                },
                "score": cand.get("score"),
                "discount_pct": cand.get("discount_pct")
                                 or getattr(flight_for_affiliate, "discount_pct", None),
            }

            data = ex.update_flights_json(
                main_item=main_item,
                json_path="local_copy.json",
                market=MARKET,
                reel_url=permalink or video_url,   # preferimos el permalink del Reel
                affiliate_url=affiliate_url,
                max_entries=5,
            )

            key = f"{MARKET.lower()}/flights_of_the_day.json"
            up.upload_flights_json(data, key=key)

            query.message.reply_text(
                f"🗂 Web actualizada y JSON subido a S3 (key={key})."
            )

        except Exception as e:
            query.message.reply_text(f"⚠️ Publicado en IG, pero error actualizando S3: {e}")

        # ------------------------------------------------------------------
        # 3) Registrar publicación en histórico (published_deals.json)
        # ------------------------------------------------------------------
        try:
            flight_for_history = cand or job.get("flight") or {}
            category_code = (
                cand.get("category_code")
                or getattr(flight_for_history, "category_code", "")
                or ""
            )
            register_publication(flight_for_history, category_code=category_code)
            query.message.reply_text("📝 Publicación registrada en historial (published_deals).")
        except Exception as e:
            query.message.reply_text(f"⚠️ Error registrando en historial: {e}")

        # ------------------------------------------------------------------
        # 4) Limpiar el job
        # ------------------------------------------------------------------
        PENDING_JOBS.pop(job_id, None)
        delete_job(job_id)

    elif action == "another":
        query.answer("Buscando otra opción…")
        query.edit_message_reply_markup(reply_markup=None)

        next_cand = _pick_next_candidate(job)
        if not next_cand:
            query.message.reply_text("⚠️ No hay más opciones alternativas definidas.")
            print("Sin más candidatos para este job.")
            return

        print(f"Siguiente candidato: {next_cand.get('destination')} idx={job.get('current_index')}")

        new_caption, new_video_path = _build_reel_for_candidate(next_cand)
        print(f"Nuevo video generado en: {new_video_path}")

        job["caption"] = new_caption
        job["video_path"] = new_video_path
        PENDING_JOBS[job_id] = job
        save_job(job_id, job)

        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("✅ Publicar", callback_data=f"approve:{job_id}"),
                InlineKeyboardButton("🔁 Otro", callback_data=f"another:{job_id}"),
            ]
        ])

        try:
            with new_video_path.open("rb") as f:
                # 1) Vídeo con botones, sin caption
                context.bot.send_video(
                    chat_id=query.message.chat_id,
                    video=f,
                    reply_markup=keyboard,
                    supports_streaming=True,
                )
            
            # 2) Caption en mensaje aparte
            context.bot.send_message(
                chat_id=query.message.chat_id,
                text=new_caption,
            )
            
            print("Enviado nuevo candidato para revisión.")
        except Exception as e:
            print(f"❌ Error enviando nuevo candidato: {e}")
            query.message.reply_text(f"❌ Error enviando vídeo: {e}")

def _format_date_range(start, end) -> str:
    """Convierte fechas a 'YYYY-MM-DD – YYYY-MM-DD'."""
    def as_str(d):
        if d is None:
            return ""
        if hasattr(d, "strftime"):
            return d.strftime("%Y-%m-%d")
        d = str(d)
        # si viene 'YYYY-MM-DD HH:MM:SS'
        return d.split(" ")[0]
    return f"{as_str(start)} – {as_str(end)}"


def handle_text_query(update, context):
    """
    Permite escribir en el chat:
      vuelo 10 180
    y lanza el flujo completo:
      - busca vuelos en [hoy+10, hoy+10+180]
      - calcula best_by_cat (con min_discount_pct=40)
      - elige main candidate
      - genera reel + caption
      - registra job y lo envía a revisión
    Además envía un resumen textual.
    """
    text = (update.message.text or "").strip().lower()

    m = re.match(r"^vuelo\s+(\d+)\s+(\d+)$", text)
    if not m:
        # no es nuestro patrón -> ignoramos
        return

    offset_start = int(m.group(1))   # ej. 10 días desde hoy
    offset_range = int(m.group(2))   # ej. 180 días de ventana

    start = date.today() + timedelta(days=offset_start)
    end = start + timedelta(days=offset_range)

    # 1) Buscar vuelos en el rango
    try:
        flights = ag.get_flights_in_period(start, end)
    except Exception as e:
        update.message.reply_text(f"❌ Error obteniendo vuelos: {e}")
        return

    if not flights:
        update.message.reply_text(
            f"🔍 No se han encontrado vuelos entre {start} y {end}."
        )
        return

    # 2) Calcular mejores por categoría con descuento mínimo
    try:
        best_by_cat = ag.get_best_by_category_scored(
            flights,
            min_discount_pct=40.0,
        )
    except Exception as e:
        update.message.reply_text(
            f"Se han encontrado {len(flights)} vuelos, pero ha fallado "
            f"get_best_by_category_scored: {e}"
        )
        return

    if not best_by_cat:
        update.message.reply_text(
            f"✈️ Encontrados {len(flights)} vuelos, pero ninguno cumple el descuento mínimo."
        )
        return

    # 3) Elegir candidato principal
    try:
        main_item = ag.choose_main_candidate_prob(best_by_cat)
    except Exception as e:
        update.message.reply_text(f"❌ Error eligiendo candidato principal: {e}")
        return

    main_flight = main_item["flight"]
    main_cat = main_item["category"]
    main_cat_code = main_cat.get("code")

    # 4) Convertir todos a candidatos "review-friendly"
    review_candidates = to_review_candidates(best_by_cat)

    # Identificar el índice del candidato principal en review_candidates
    main_idx = 0
    for i, item in enumerate(best_by_cat):
        if item["flight"] is main_flight and item["category"].get("code") == main_cat_code:
            main_idx = i
            break

    # Reordenamos para que el principal quede en índice 0
    if main_idx != 0:
        review_candidates[0], review_candidates[main_idx] = review_candidates[main_idx], review_candidates[0]

    main_candidate = review_candidates[0]

    # 5) Generar reel + caption para ese main_candidate
    new_caption, new_video_path = _build_reel_for_candidate(main_candidate)

    # 6) Registrar job y enviarlo a revisión
    job_id = str(uuid.uuid4())
    register_job(
        job_id=job_id,
        flight=None,                 # no lo usamos ahora mismo
        caption=new_caption,
        video_path=new_video_path,
        candidates=review_candidates,
    )
    send_review_candidate(job_id)

    # 7) Resumen textual en el chat donde se escribió "vuelo 10 180"
    dates_str = _format_date_range(main_candidate.get("start_date"), main_candidate.get("end_date"))
    price_val = main_candidate.get("price")
    price_str = f"{price_val:.2f} €" if price_val is not None else "N/D"

    update.message.reply_text(
        f"✅ Generado y enviado a revisión.\n"
        f"Periodo búsqueda: {start} – {end}\n"
        f"Candidato principal:\n"
        f"  {main_cat.get('label', '')}\n"
        f"  {main_candidate.get('origin')} → {main_candidate.get('destination')}\n"
        f"  Fechas: {dates_str}\n"
        f"  Precio: {price_str}\n"
        f"job_id: {job_id}"
    )

def run_bot():
    if not BOT_TOKEN:
        raise ValueError("Falta TELEGRAM_BOT_TOKEN en .env")

    updater = Updater(BOT_TOKEN, use_context=True)
    dp = updater.dispatcher

    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(CallbackQueryHandler(handle_button))

    # 🔹 nuevo handler para mensajes "vuelo 10 180"
    dp.add_handler(MessageHandler(Filters.text & ~Filters.command, handle_text_query))

    print("🤖 Bot de revisión escuchando (polling)…")
    updater.start_polling()
    updater.idle()


if __name__ == "__main__":
    run_bot()
