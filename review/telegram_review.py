import re
from datetime import date, timedelta
from telegram.ext import MessageHandler, Filters

import os
import json
from pathlib import Path
from typing import Dict, Any, List

from telegram import Bot, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Updater, CallbackQueryHandler, CommandHandler

from instagram.ig_client import InstagramClient
from storage.uploader import get_public_url

# IMPORTS NUEVOS: usa los que ya tienes en tu proyecto
import content.caption_builder as cb
import media.video_generator as vg
import flights.aggregator as ag


from config.settings import BOT_TOKEN,REVIEW_CHAT_ID 


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
        bot.send_video(
            chat_id=REVIEW_CHAT_ID,
            video=f,
            caption=job["caption"],
            reply_markup=keyboard,
            supports_streaming=True,
        )


# ---------- Helpers para "Otro" ----------

def _pick_next_candidate(job: Dict[str, Any]) -> Dict[str, Any] | None:
    """
    Devuelve el siguiente candidato de la lista, actualizando current_index.
    Si no hay candidatos o ya no quedan, devuelve None.
    Estrategia simple: ir avanzando en la lista; si se acaba, opcionalmente
    podemos hacer wrap-around. Por ahora: parar cuando se acaba.
    """
    candidates: List[Dict[str, Any]] = job.get("candidates", [])
    if not candidates:
        return None

    idx = job.get("current_index", 0)

    # siguiente índice
    next_idx = idx + 1
    if next_idx >= len(candidates):
        # no hay más candidatos; podrías hacer wrap a 0 si quieres:
        # next_idx = 0
        return None

    job["current_index"] = next_idx
    return candidates[next_idx]


def _build_reel_for_candidate(candidate: Dict[str, Any]) -> tuple[str, Path]:
    """
    Regenera caption + vídeo para un candidato concreto (dict),
    usando la función genérica de video_generator.
    """
    # candidate es un dict con origin, destination, price, start_date, end_date, category_code, etc.
    caption = cb.build_caption_for_flight(
        candidate,
        category_code=candidate.get("category_code"),
        tone="emocional",
    )
    caption = caption.replace("\n\n\n", "\n\n")  # por si acaso

    # ruta de salida
    out_dir = Path("media/videos")
    out_dir.mkdir(parents=True, exist_ok=True)
    dest = candidate.get("destination", "XXX")
    out_path = out_dir / f"reel_review_{dest}.mp4"

    logo_path = (
        r"C:\Users\Macia\Desktop\Jupyter Notebooks\EscapadasMallorca"
        r"\media\images\EscapGo_circ_logo_transparent.png"
    )

    vg.create_reel_for_flight(
        flight=candidate,          # dict compatible con el helper
        out_mp4_path=str(out_path),
        logo_path=logo_path,
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
        query.edit_message_reply_markup(reply_markup=None)

        # try:
        #     video_url = get_public_url(job["video_path"])
        #     ig = InstagramClient()
        #     creation_id = ig.create_reel_container(video_url, job["caption"])
        #     if ig.wait_until_ready(creation_id):
        #         reel_id = ig.publish_reel(creation_id)
        #         permalink = ig.get_media_permalink(reel_id)
        #         query.message.reply_text(f"✅ Publicado:\n{permalink}")
        #     else:
        #         query.message.reply_text("❌ IG no ha podido procesar el vídeo.")
        # except Exception as e:
        #     query.message.reply_text(f"❌ Error publicando: {e}")

        print("Publicando")

        # Limpiamos
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
                context.bot.send_video(
                    chat_id=query.message.chat_id,   # usa el chat real del mensaje
                    video=f,
                    caption=new_caption,
                    reply_markup=keyboard,
                    supports_streaming=True,
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
    y devuelve:
      - nº de vuelos encontrados
      - mejor vuelo por categoría (best_by_cat) con fechas y métricas formateadas.
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

    # resumen best_by_cat
    try:
        best_by_cat = ag.get_best_by_category_scored(flights)
    except Exception as e:
        update.message.reply_text(
            f"Se han encontrado {len(flights)} vuelos, pero ha fallado "
            f"get_best_by_category_scored: {e}"
        )
        return

    lines = []
    lines.append(
        f"🔍 Buscando vuelos entre {start} y {end}.\n"
        f"✈️ Encontrados: {len(flights)}\n"
    )

    if not best_by_cat:
        lines.append("⚠️ No se ha podido calcular el mejor por categoría.")
    else:
        lines.append("🏆 Mejores por categoría:\n")
        for item in best_by_cat:
            f = item["flight"]
            cat = item["category"]
            score = item.get("score", 0.0)

            price = getattr(f, "price", None)
            ppk = getattr(f, "price_per_km", None)
            start_d = getattr(f, "start_date", None)
            end_d = getattr(f, "end_date", None)

            price_str = f"{float(price):.2f} €" if price is not None else "N/D"
            ppk_str = f"{float(ppk):.2f} €/km" if ppk is not None else "N/D"
            score_str = f"{float(score):.2f}"

            dates_str = _format_date_range(start_d, end_d)

            lines.append(
                f"{cat['label']}\n"
                f"  {f.origin} → {f.destination}\n"
                f"  Fechas: {dates_str}\n"
                f"  Precio: {price_str} | {ppk_str} | score {score_str}\n"
            )

    update.message.reply_text("\n".join(lines))

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
