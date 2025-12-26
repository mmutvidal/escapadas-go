import json
import os
from openai import OpenAI
from typing import Union
from datetime import datetime
from .destinations import get_city
import re


FlightLike = Union[dict, object]

from config.settings import OPENAI_API_KEY  # 👈 nuevo import

client = OpenAI(api_key=OPENAI_API_KEY)


def _extract_json_object(text: str) -> str:
    """
    Extrae el primer objeto JSON {...} de un texto (por si el modelo añade texto extra).
    """
    if not text:
        raise ValueError("Respuesta vacía del modelo (no hay JSON).")
    m = re.search(r"\{.*\}", text, flags=re.DOTALL)
    if not m:
        raise ValueError(f"No se encontró un objeto JSON en la respuesta: {text[:200]}")
    return m.group(0)

    
def _weekday_es(date_str: str) -> str:
    """
    Acepta 'YYYY-MM-DD' o ISO 'YYYY-MM-DDTHH:MM:SS(.sss)Z'
    Devuelve el día con mayúscula inicial (formato editorial).
    """
    if not date_str:
        return ""

    s = str(date_str)
    if "T" in s:
        s = s.split("T")[0]

    d = datetime.strptime(s, "%Y-%m-%d").date()
    names = ["lunes", "martes", "miércoles", "jueves",
             "viernes", "sábado", "domingo"]
    return names[d.weekday()].capitalize()

def _get_field(f: FlightLike, name: str, default=None):
    if isinstance(f, dict):
        return f.get(name, default)
    return getattr(f, name, default)



def build_dates_block(flight) -> str:
    start = str(_get_field(flight, "start_date", "")).split("T")[0][:10]
    end = str(_get_field(flight, "end_date", "")).split("T")[0][:10]

    start_day = _weekday_es(start)
    end_day = _weekday_es(end)

    start_dt = datetime.strptime(start, "%Y-%m-%d")
    end_dt = datetime.strptime(end, "%Y-%m-%d")

    # ciudades a partir de IATA
    origin_iata = _get_field(flight, "origin") or _get_field(flight, "origin_airport")
    dest_iata   = _get_field(flight, "destination") or _get_field(flight, "destination_airport")
    
    origin_city = get_city(origin_iata or "")
    dest_city = get_city(dest_iata or "")
    
    return (
        f"📅 {start_day} {start_dt.day} → {end_day} {end_dt.day}\n"
        f"✈️ {origin_city} → {dest_city}\n"
        f"💸 {int(_get_field(flight, 'price'))} € ida y vuelta"
    )


def build_caption_json(payload: dict) -> dict:
    system_prompt = """Eres un experto en Instagram especializado en crear captions largos y retenibles
para Reels de chollos de vuelos.

Debes devolver ÚNICAMENTE un JSON con la siguiente estructura EXACTA:

{
  "hook": "",
  "bridge": "",
  "dates_block": "",
  "itinerary_block": "",
  "extra_block": "",
  "cta_block": "",
  "hashtags": ""
}

Reglas IMPORTANTES:

- Escribe SIEMPRE en español neutro, cercano pero no infantil.
- El texto total (sumando todos los campos menos "hashtags") debe estar entre 90 y 140 palabras.
- El objetivo es que la persona tarde al menos 8–12 segundos en leerlo todo.
- "hook": 1 sola frase muy corta, clara y potente (máx. 12 palabras), sin emojis, sin fechas ni precios, pensada para detener el scroll.
- "bridge": 1–2 frases que inviten a seguir leyendo.
- Cuando "category_code" sea "finde_perfecto", menciona en "bridge" que los horarios permiten aprovechar al máximo el fin de semana.

- El bloque "dates_block" debe copiarse exactamente tal como se proporciona. No reformules, no traduzcas ni alteres su formato. No añadas ni elimines emojis ni saltos de línea.
- Si el campo "category_code" es "finde_perfecto" y se proporcionan "start_time" y "end_time",
  solamente en este caso debes añadir los horarios de salida y regreso en la primera línea del dates_block siguiendo este ejemplo:
  "📅 Viernes 28 (19:45) → Domingo 30 (21:30)".

- "itinerary_block": estructura SIEMPRE según el número de días proporcionado en 'stay_nights':
  - Cabecera por día: "🇮🇹 Día 1, Centro histórico:"
  - 2–3 bullets por día, cada bullet ≤ 10 palabras.

- "extra_block": 1–2 frases que destaquen lo especial del destino adaptado a la categoría.
  Al final incluye dos saltos de línea y añade SIEMPRE una frase que recomiende reservar pronto para evitar subidas de precios.
  Varía la redacción en cada generación (no repitas siempre lo mismo).

- DESCUENTO ("discount_pct"):
  - Si existe "discount_pct" y es mayor que 40:
      · Menciona el descuento UNA sola vez.
      · Inclúyelo EXCLUSIVAMENTE en el "bridge".
      · NO vuelvas a mencionarlo en "extra_block".
  - Redondea siempre al número entero más cercano.
  - Si "discount_pct" es menor a 40 o no existe, NO hables de descuento.

- "cta_block": 1 sola frase con CTA suave y variada.
  Debe incluir SIEMPRE una referencia a que las reservas están en el enlace de la bio o en el sitio indicado por "booking_hint".

- "hashtags": 6–10 hashtags relacionados, separados por espacios, sin emojis.
- No incluyas comillas dobles dentro de los valores del JSON.
- No añadas texto fuera del JSON.
- No inventes vuelos ni precios: usa siempre los datos proporcionados.
- Adapta el tono según la categoría.

- No uses expresiones vagas tipo: ‘hoy’, ‘mañana’, ‘este finde’, etc.
"""
    user_prompt = f"""Genera el JSON del caption para este payload siguiendo las reglas:

{json.dumps(payload, ensure_ascii=False)}
"""
    resp = client.chat.completions.create(
        model="gpt-4.1-mini",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.8,
    )

    raw = (resp.choices[0].message.content or "").strip()
    raw_json = _extract_json_object(raw)
    return json.loads(raw_json)



def build_hook(flight) -> str:
    """
    Crea un hook determinista a partir del vuelo y la categoría.
    NO usa expresiones vagas tipo 'este finde', 'hoy', etc.
    """

    price = int(round(flight['price_eur']))
    dest = flight['destination_city']  # o como lo tengas guardado
    nights = flight['stay_nights']
    category_code = flight['category_code']
    
    if category_code == "finde_perfecto":
        return f"✈️ Fin de semana en {dest} por {price}€ ida y vuelta."
    elif category_code == "ultra_chollo":
        return f"🔥 Chollazo: {dest} ida y vuelta por solo {price}€."
    elif category_code == "romantica":
        return f"💘 Escapada romántica a {dest} desde {price}€ ida y vuelta."
    elif category_code == "cultural":
        return f"🏛 Escapada cultural a {dest} por {price}€ ida y vuelta."
    elif category_code == "gastronomica":
        return f"🍽 Viaje gastro a {dest} por {price}€ ida y vuelta."
    else:
        # default
        if nights == 1:
            return f"✈️ Escapada a {dest} por {price}€ ida y vuelta."
        else:
            return f"✈️ {nights} noches en {dest} por {price}€ ida y vuelta."


def build_caption_text(cj: dict, hook_override: str | None = None) -> str:
    hook = hook_override or cj.get("hook", "")

    parts = [
        hook,
        "",
        cj.get("bridge", ""),
        "",
        cj.get("dates_block", ""),
        "",
        cj.get("itinerary_block", ""),
        "",
        cj.get("extra_block", ""),
        "",
        cj.get("cta_block", ""),
        "",
        cj.get("hashtags", ""),
    ]
    return "\n\n".join(p for p in parts if str(p).strip())


# def build_caption_text(cj: dict) -> str:
#     """
#     Une los bloques JSON en un solo caption listo para IG.
#     """
#     parts = [
#         cj["hook"],
#         "",
#         cj["bridge"],
#         "",
#         cj["dates_block"],
#         "",
#         cj["itinerary_block"],
#         "",
#         cj["extra_block"],
#         "",
#         cj["cta_block"],
#         "",
#         cj["hashtags"],
#     ]
#     # quita líneas vacías repetidas
#     return "\n".join(p for p in parts if p is not None and str(p).strip())



def _to_date_str(d) -> str:
    """
    Normaliza a 'YYYY-MM-DD' para la API de captions.
    Acepta:
      - 'YYYY-MM-DD'
      - 'YYYY-MM-DD HH:MM:SS'
      - datetime/date
    """
    if d is None:
        return ""
    if isinstance(d, datetime):
        return d.date().strftime("%Y-%m-%d")
    if hasattr(d, "year") and hasattr(d, "month"):
        return d.strftime("%Y-%m-%d")
    if isinstance(d, str):
        return d.split(" ")[0]
    return str(d)


def _to_time_str(d) -> str:
    """
    Extrae 'HH:MM' si viene una fecha con hora, o devuelve cadena vacía.
    """
    if d is None:
        return ""
    if isinstance(d, datetime):
        return d.strftime("%H:%M")
    if isinstance(d, str) and " " in d:
        # 'YYYY-MM-DD HH:MM:SS'
        try:
            return d.split(" ")[1][:5]   # HH:MM
        except Exception:
            return ""
    return ""


def build_caption_for_flight(
    flight: FlightLike,
    brand_handle: str = "@escapadasgo",
    booking_hint: str = "el enlace de la bio",
    category_code: str | None = None,
    tone: str = "emocional",
    hashtags_base: list[str] | None = None,
) -> str:
    """
    Capa de alto nivel:
    - toma un Flight o un dict (como el candidate de review)
    - construye el payload
    - genera el caption final (hook + cuerpo) con tus funciones existentes.
    """

    if hashtags_base is None:
        hashtags_base = ["#viajar", "#vuelosbaratos", "#escapadas"]

    origin_iata = _get_field(flight, "origin") or _get_field(flight, "origin_airport")
    dest_iata   = _get_field(flight, "destination") or _get_field(flight, "destination_airport")
    price_eur   = _get_field(flight, "price_eur") or _get_field(flight, "price")
    start_raw   = _get_field(flight, "start_date")
    end_raw     = _get_field(flight, "end_date")
    discount_pct = _get_field(flight, "discount_pct")
    
    start_date = _to_date_str(start_raw)
    end_date   = _to_date_str(end_raw)
    start_time = _to_time_str(start_raw)
    end_time   = _to_time_str(end_raw)

    start_weekday = _weekday_es(start_date) if start_date else ""
    end_weekday   = _weekday_es(end_date) if end_date else ""
    
    # ciudades a partir de IATA
    origin_city = get_city(origin_iata or "")
    dest_city = get_city(dest_iata or "")

    # noches de estancia (opcional)
    stay_nights = None
    try:
        s = _to_date_str(start_date)
        e = _to_date_str(end_date)
        if s and e:
            d1 = datetime.strptime(s, "%Y-%m-%d").date()
            d2 = datetime.strptime(e, "%Y-%m-%d").date()
            stay_nights = (d2 - d1).days
    except Exception:
        pass

    dates_block = build_dates_block(flight)

    
    payload = {
        "brand_handle": brand_handle,
        "booking_hint": booking_hint,   # ✅ NUEVO
        "category_code": category_code,          # p.ej. "cultural", "romantica"
        "origin_city": origin_city,
        "origin_airport": origin_iata,
        "destination_city": dest_city,
        "destination_airport": dest_iata,
        "price_eur": float(price_eur) if price_eur is not None else None,
        "start_date": start_date,
        "end_date": end_date,
        "start_weekday": start_weekday,
        "end_weekday": end_weekday,
        "start_time": start_time,                # NUEVO
        "end_time": end_time,                    # NUEVO
        "stay_nights": stay_nights,
        "tone": tone,
        "hashtags_base": hashtags_base,
        "discount_pct": discount_pct,
        "dates_block": dates_block,
    }

    cj = build_caption_json(payload)
    # hook = build_hook(payload)
    # caption_text = build_caption_text(cj, hook_override=hook)
    caption_text = build_caption_text(cj, None)

    return caption_text
