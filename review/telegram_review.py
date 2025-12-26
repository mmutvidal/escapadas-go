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

from content.destinations import get_country
import content.video_hook_curiosity as vh
import media.reel_ab as rab

from config.markets import MARKETS

from config.settings import BOT_TOKEN,REVIEW_CHAT_ID 

S3_BUCKET_REELS = "escapadasgo-reels"
# S3_PREFIX_REELS = "pmi/"   # si algún día tienes más markets, lo paramos
# MARKET = "PMI"  # más adelante lo podrás hacer dinámico
# LOGO_PATH = "media/images/EscapGo_circ_logo_transparent.png"


# Carpeta para guardar los jobs en disco (compartida entre procesos)
JOBS_DIR = Path("review_jobs")
JOBS_DIR.mkdir(exist_ok=True)

# Opcional: cache en memoria (solo útil dentro de cada proceso)
PENDING_JOBS: Dict[str, Dict[str, Any]] = {}


def _job_path(job_id: str) -> Path:
    return JOBS_DIR / f"{job_id}.json"


def _serialize_job(job: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "market": job.get("market"),
        "flight": job.get("flight"),   # ✅ AÑADIR
        "ig_handle": job.get("ig_handle"),
        "ig_user_id": job.get("ig_user_id"),
        "page_token": job.get("page_token"),
        "s3_prefix_reels": job.get("s3_prefix_reels"),
        "web_key_prefix": job.get("web_key_prefix"),
        "web_json_path": str(job.get("web_json_path") or ""),
        "logo_path": job.get("logo_path"),
        "ab_ratio_new": job.get("ab_ratio_new", 0.5),

        "caption": job["caption"],
        "video_path": str(job["video_path"]),
        "video_hook": job.get("video_hook"),
        "variant": job.get("variant"),

        "candidates": job.get("candidates", []),
        "current_index": job.get("current_index", 0),
    }


def _deserialize_job(data: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "market": data.get("market"),
        "flight": data.get("flight"),  # ✅ AÑADIR
        "ig_handle": data.get("ig_handle"),
        "ig_user_id": data.get("ig_user_id"),
        "page_token": data.get("page_token"),
        "s3_prefix_reels": data.get("s3_prefix_reels"),
        "web_key_prefix": data.get("web_key_prefix"),
        "web_json_path": Path(data["web_json_path"]) if data.get("web_json_path") else None,
        "logo_path": data.get("logo_path"),
        "ab_ratio_new": data.get("ab_ratio_new", 0.5),

        "caption": data["caption"],
        "video_path": Path(data["video_path"]),
        "video_hook": data.get("video_hook"),
        "variant": data.get("variant"),

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

def _flight_to_dict(f: Any) -> Any:
    """
    Acepta Flight o dict. Devuelve dict JSON-friendly.
    """
    if f is None:
        return None
    if isinstance(f, dict):
        return f
    # Intentar extraer atributos típicos
    d = {}
    for k in [
        "origin","destination","start_date","end_date","price","airline","link",
        "discount_pct","route_typical_price","distance_km","price_per_km"
    ]:
        if hasattr(f, k):
            v = getattr(f, k)
            d[k] = str(v) if k in ("start_date","end_date") else v
    return d or None

def _extract_origin_from_text(text: str, default_origin: str | None = None) -> str | None:
    """
    Detecta un código IATA (PMI, BCN, MAD, VLC, etc.) en el texto.
    Si no hay ninguno, devuelve default_origin.
    """
    if not text:
        return default_origin

    tokens = text.upper().split()
    for t in tokens:
        if len(t) == 3 and t.isalpha():
            return t

    return default_origin


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
            s = str(dt_str)
            if "T" in s:
                s = s.split("T")[0]
            if " " in s:
                s = s.split(" ")[0]
            return s[:10]

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


def register_job(
    job_id: str,
    caption: str,
    video_path: Path,
    candidates=None,
    flight: Any = None,                 # ✅ AÑADIR
    video_hook: str | None = None,
    market: str | None = None,
    ig_handle: str | None = None,
    ig_user_id: str | None = None,
    page_token: str | None = None,
    s3_prefix_reels: str | None = None,
    web_key_prefix: str | None = None,
    web_json_path: str | Path | None = None,
    logo_path: str | None = None,
    ab_ratio_new: float = 0.5,
    variant: str | None = None,
):
    job = {
        "market": market,
        "ig_handle": ig_handle,
        "ig_user_id": ig_user_id,
        "page_token": page_token,
        "s3_prefix_reels": s3_prefix_reels,
        "web_key_prefix": web_key_prefix,
        "web_json_path": Path(web_json_path) if web_json_path else None,
        "logo_path": logo_path,
        "ab_ratio_new": ab_ratio_new,
        
        "flight": _flight_to_dict(flight),   # ✅ AÑADIR

        "caption": caption,
        "video_path": Path(video_path),
        "video_hook": video_hook,
        "variant": variant,

        "candidates": candidates or [],
        "current_index": 0,
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


def _build_reel_for_candidate(candidate: Dict[str, Any], job: Dict[str, Any]) -> tuple[str, Path, str, str]:
    # 1) Caption
    brand_handle = job.get("ig_handle") or "@escapadasgo"
    # booking_hint por mercado: si guardas uno explícito en job, úsalo. Si no:
    booking_hint = "escapadasgo.com o el enlace de la bio"
    if brand_handle == "@escapadasgo_mallorca":
        booking_hint = "escapadasgo.com/mallorca o el enlace de la bio"
    
    caption = cb.build_caption_for_flight(
        candidate,
        category_code=candidate.get("category_code"),
        tone="emocional",
        brand_handle=brand_handle,
        booking_hint=booking_hint,
    ).replace("\n\n\n", "\n\n")

    # 2) Hook (curiosidad, premium)
    category_label = candidate.get("category_label") or candidate.get("category_code") or ""
    video_hook = vh.build_video_hook_curiosity(
        category_label=str(category_label),
        country=get_country(candidate.get("destination")),
        discount_pct=candidate.get("discount_pct"),
        price=candidate.get("price"),
        start_date=str(candidate.get("start_date", ""))[:10],
        end_date=str(candidate.get("end_date", ""))[:10],
        max_len=44,
    )

    # 3) Vídeo
    out_dir = Path("media/videos")
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "reel.mp4"

    # vg.create_reel_for_flight(
    #     flight=candidate,               # dict compatible
    #     out_mp4_path=str(out_path),
    #     logo_path=LOGO_PATH,
    #     duration=6.0,
    #     hook_text=video_hook,           # ✅ AQUÍ
    #     hook_mode="band",               # ✅ AQUÍ
    # )

    logo_path = job.get("logo_path") or "media/images/EscapGo_circ_logo_transparent.png"
    ratio_new = float(job.get("ab_ratio_new", 0.5))
    
    video_path_or_url, variant_used, origin_pill_variant = rab.create_reel_for_flight_ab(
        candidate,
        out_mp4_path=str(out_path),
        logo_path=logo_path,
        brand_line=brand_handle,
        duration=6.0,
        s3_bucket=None,
        hook_text=video_hook,
        hook_mode="band",
        variant="auto",
        ratio_new=ratio_new,
        key_mode="route_dates",
        origin_pill_ab_ratio=1,  # ✅ pill A/B 50/50
    )
    
    combined_variant = f"{variant_used}|{origin_pill_variant}"
    return caption, out_path, video_hook, combined_variant



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
                local_path=job["video_path"],
                bucket=S3_BUCKET_REELS,
                prefix=job.get("s3_prefix_reels") or "",
            )

            # 1.2) Crear contenedor de Reel en IG usando la URL de S3
            ig = InstagramClient(
                ig_user_id=job.get("ig_user_id"),
                page_token=job.get("page_token"),
            )            
            creation_id = ig.create_reel_container(
                video_url=video_url,
                caption=job["caption"],
            )

            # 1.3) Esperar a que IG procese el vídeo y publicar
            if ig.wait_until_ready(creation_id):
                # Logging correcto (usa job)
                token = job.get("page_token") or ""
                print(
                    f"[PUBLISH] market={job.get('market')} "
                    f"handle={job.get('ig_handle')} "
                    f"ig_user_id={job.get('ig_user_id')} "
                    f"token_suffix={token[-10:] if token else 'NONE'}"
                )
                
                # Guardas para evitar publicar con defaults por accidente
                if not job.get("ig_user_id") or not job.get("page_token"):
                    raise RuntimeError(
                        "Faltan ig_user_id/page_token en el job. "
                        "Esto causaría publicar con defaults del .env en la cuenta incorrecta."
                    )

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

            market = job.get("market") or "UNK"
            json_path = job.get("web_json_path") or Path("local_copy.json")
            web_key_prefix = job.get("web_key_prefix") or f"{market.lower()}/"
            
            data = ex.update_flights_json(
                main_item=main_item,
                json_path=json_path,
                market=market,
                reel_url=permalink or video_url,
                affiliate_url=affiliate_url,
                max_entries=5,
            )
            
            key = f"{web_key_prefix}flights_of_the_day.json"
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

        new_caption, new_video_path, new_hook, variant_used = _build_reel_for_candidate(next_cand, job)
        job["variant"] = variant_used        
        job["video_hook"] = new_hook
        print(f"Nuevo video generado en: {new_video_path}")

        job["caption"] = new_caption
        job["video_path"] = new_video_path
        job["video_hook"] = new_hook

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
      vuelo BCN 10 180
      vuelo MAD 7 150

    Flujo:
      - busca vuelos en [hoy+offset_start, hoy+offset_start+offset_range]
      - calcula best_by_cat (min_discount_pct=40)
      - elige main candidate
      - genera reel + caption
      - registra job y lo envía a revisión
    """
    raw_text = (update.message.text or "").strip()
    text_up = raw_text.upper()

    # Soportar:
    #  - "VUELO 10 180"
    #  - "VUELO BCN 10 180"
    m = re.match(r"^VUELO(?:\s+([A-Z]{3}))?\s+(\d+)\s+(\d+)$", text_up)
    if not m:
        return

    origin_iata = (m.group(1) or "").strip().upper() or None
    offset_start = int(m.group(2))
    offset_range = int(m.group(3))

    start = date.today() + timedelta(days=offset_start)
    end = start + timedelta(days=offset_range)

    # Default origin si no se especifica
    if not origin_iata:
        origin_iata = "PMI"  # cambia aquí si quieres otro default

    update.message.reply_text(
        f"🔎 Buscando vuelos con salida desde {origin_iata}…\n"
        f"Rango: {start} → {end}"
    )

    # 1) Buscar vuelos
    try:
        flights = ag.get_flights_in_period(start, end, origin_iata=origin_iata)
    except Exception as e:
        update.message.reply_text(f"❌ Error obteniendo vuelos: {e}")
        return

    if not flights:
        update.message.reply_text(f"🔍 No se han encontrado vuelos entre {start} y {end}.")
        return

    # 2) Mejor por categoría
    try:
        best_by_cat = ag.get_best_by_category_scored(
            flights,
            min_discount_pct=40.0,
        )
    except Exception as e:
        update.message.reply_text(
            f"Se han encontrado {len(flights)} vuelos, pero ha fallado scoring: {e}"
        )
        return

    if not best_by_cat:
        update.message.reply_text(
            f"✈️ Encontrados {len(flights)} vuelos, pero ninguno cumple el descuento mínimo."
        )
        return

    # 3) Elegir main
    try:
        main_item = ag.choose_main_candidate_prob(best_by_cat)
    except Exception as e:
        update.message.reply_text(f"❌ Error eligiendo candidato principal: {e}")
        return

    main_flight = main_item["flight"]
    main_cat = main_item["category"]
    main_cat_code = main_cat.get("code")

    # 4) Convertir a candidatos review-friendly
    review_candidates = to_review_candidates(best_by_cat)

    # Reordenar para que el principal quede primero (evitar `is`)
    def _key_from_cand(c):
        return (
            (c.get("origin") or "").upper(),
            (c.get("destination") or "").upper(),
            str(c.get("start_date") or "")[:10],
            str(c.get("end_date") or "")[:10],
            float(c.get("price") or 0.0),
        )

    main_key = (
        main_flight.origin.upper(),
        main_flight.destination.upper(),
        str(main_flight.start_date)[:10],
        str(main_flight.end_date)[:10],
        float(main_flight.price),
    )

    main_idx = 0
    for i, c in enumerate(review_candidates):
        if _key_from_cand(c) == main_key and c.get("category_code") == main_cat_code:
            main_idx = i
            break

    if main_idx != 0:
        review_candidates[0], review_candidates[main_idx] = review_candidates[main_idx], review_candidates[0]

    main_candidate = review_candidates[0]

    # 5) Resolver cfg/market según origin_iata (PMI, BCN, MAD, VLC...)
    cfg = MARKETS.get(origin_iata)
    if not cfg:
        update.message.reply_text(
            f"❌ Mercado/origen '{origin_iata}' no configurado en MARKETS.\n"
            f"Disponibles: {', '.join(MARKETS.keys())}"
        )
        return

    # Construimos un job “base” con los datos del market correcto
    tmp_job = {
        "market": cfg.code,
        "ig_handle": cfg.ig_handle,
        "ig_user_id": cfg.ig_user_id,
        "page_token": cfg.page_token,
        "s3_prefix_reels": cfg.s3_reels_prefix,
        "web_key_prefix": cfg.web_key_prefix,
        "logo_path": cfg.logo_path,
        "ab_ratio_new": float(getattr(cfg, "ab_ratio_new", 0.5)),
    }

    # Validación temprana para que no llegue un job incompleto a aprobación
    if not tmp_job["ig_user_id"] or not tmp_job["page_token"]:
        update.message.reply_text(
            f"❌ El market {cfg.code} no tiene ig_user_id/page_token.\n"
            f"Revisa tu .env y config/markets.py"
        )
        return

    # 6) Generar reel + caption para main_candidate usando el branding del market
    new_caption, new_video_path, new_hook, variant_used = _build_reel_for_candidate(main_candidate, tmp_job)

    # 7) Registrar job completo y enviar a revisión
    job_id = str(uuid.uuid4())
    register_job(
        job_id=job_id,
        caption=new_caption,
        video_path=new_video_path,
        candidates=review_candidates,
        flight=main_flight,                 # opcional, pero útil
        video_hook=new_hook,
        variant=variant_used,

        market=tmp_job["market"],
        ig_handle=tmp_job["ig_handle"],
        ig_user_id=tmp_job["ig_user_id"],
        page_token=tmp_job["page_token"],
        s3_prefix_reels=tmp_job["s3_prefix_reels"],
        web_key_prefix=tmp_job["web_key_prefix"],
        logo_path=tmp_job["logo_path"],
        ab_ratio_new=tmp_job["ab_ratio_new"],
    )
    send_review_candidate(job_id)

    # 7) Resumen
    dates_str = _format_date_range(main_candidate.get("start_date"), main_candidate.get("end_date"))
    price_val = main_candidate.get("price")
    price_str = f"{price_val:.2f} €" if price_val is not None else "N/D"

    update.message.reply_text(
        f"✅ Generado y enviado a revisión.\n"
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
