from __future__ import annotations
import hashlib
from datetime import datetime
from typing import Optional


# -----------------------------
# Helpers
# -----------------------------


def _pick(options: list[str], seed: str) -> str:
    h = hashlib.sha256(seed.encode("utf-8")).hexdigest()
    return options[int(h[:8], 16) % len(options)]

def _season_es(start_date: Optional[str]) -> Optional[str]:
    if not start_date:
        return None
    try:
        m = int(str(start_date)[:10].split("-")[1])
    except Exception:
        return None
    if m in (3, 4, 5): return "primavera"
    if m in (6, 7, 8): return "verano"
    if m in (9, 10):   return "otoño"
    return "invierno"

def _nights(start_date: Optional[str], end_date: Optional[str]) -> Optional[int]:
    try:
        d1 = datetime.strptime(str(start_date)[:10], "%Y-%m-%d")
        d2 = datetime.strptime(str(end_date)[:10], "%Y-%m-%d")
        return max((d2 - d1).days, 1)
    except Exception:
        return None

def _trip_len_label(nights: Optional[int]) -> str:
    if nights is None:
        return "escapada"
    if nights <= 2:
        return "fin de semana"
    if nights <= 4:
        return "escapada"
    return "viaje"

def _cheap_level(discount_pct: Optional[float], price: Optional[float]) -> str:
    disc = float(discount_pct) if discount_pct is not None else 0.0
    p = float(price) if price is not None else 999.0
    # umbrales ajustables
    if disc >= 55 or p < 45: return "muy"
    if disc >= 35 or p < 70: return "bastante"
    return "normal"

def _norm_cat(category: Optional[str]) -> str:
    s = (category or "").strip().lower()
    mapping = {
        "ultra_chollo": "ultra",
        "finde_perfecto": "finde",
        "romantica": "romantica",
        "cultural": "cultural",
        "gastronomica": "gastro",
    }
    return mapping.get(s, s.replace(" ", "_"))

def _sentence_case(s: str) -> str:
    s = (s or "").strip()
    if not s:
        return s
    return s[0].upper() + s[1:]

def _fits_len(s: str, max_len: int) -> bool:
    return len((s or "").strip()) <= max_len


def _editorial_angle(seed: str) -> str:
    """
    Punto de vista humano/editorial desde el que se presenta el plan.
    """
    angles = [
        "descubrimiento",   # no lo tenías en mente
        "timing",           # ahora encaja
        "sorpresa",         # no cuadra… pero cuadra
        "facilidad",        # más fácil de lo que parece
        "valor",            # mejor de lo esperado
    ]
    return _pick(angles, seed + "|angle")

# -----------------------------
# Hook generator
# -----------------------------
def build_video_hook_curiosity(
    *,
    category_label: str,
    country: Optional[str],
    discount_pct: Optional[float] = None,
    price: Optional[float] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    max_len: int = 44,
) -> str:
    """
    Hook premium de curiosidad (1 frase).
    - Adaptado por país, estación, duración y nivel de chollo.
    - Sin ciudad, sin precio/fechas exactas.
    - Determinístico (mismo vuelo -> mismo hook).
    """
    cat = _norm_cat(category_label)
    season = _season_es(start_date)
    nights = _nights(start_date, end_date)
    trip = _trip_len_label(nights)
    cheap = _cheap_level(discount_pct, price)

    # seed estable por vuelo
    seed = f"{cat}|{country}|{start_date}|{end_date}|{discount_pct}|{price}"

    angle = _editorial_angle(seed)

    
    # -----------------------------
    # “Arquetipos” de curiosidad
    # (una idea, una frase, tono premium)
    # -----------------------------
    # Nota: {country} es país (permitido); {season} es estación; {trip} = finde/escapada/viaje
    base_general = [
        "Este {trip} encaja mejor de lo que crees",
        "Hay una forma mejor de hacer este {trip}",
        "Esto no debería cuadrar… pero cuadra",
        "Te va a sorprender lo bien que encaja",
    ]

    base_country = [
        "{country} sale mejor de lo que imaginas",
        "No es el momento típico para {country}",
        "La mejor versión de {country} no es en verano",
        "Hay un {trip} a {country} que no te esperas",
    ]

    base_season = [
        "{season} es cuando mejor se disfruta",
        "En {season}, esto se vive distinto",
        "En {season}, este plan tiene sentido",
    ]

    duration_bias = []
    if nights:
        if nights <= 2:
            duration_bias += [
                "Un plan corto que se aprovecha mucho",
                "Poco tiempo, muy bien aprovechado",
            ]
        elif nights <= 4:
            duration_bias += [
                "Cuatro días dan para mucho aquí",
                "El tiempo justo para disfrutarlo bien",
            ]
        else:
            duration_bias += [
                "Cuando hay tiempo, este plan brilla",
                "Un viaje con margen para disfrutar",
            ]

    
    # Categoría: matices (sin explicar demasiado)
    cat_bias = {
        "cultural": [
            "Esta ciudad se vive mejor con calma",   # sin nombrarla; funciona por imagen
            "El plan cultural que no te esperas",
            "Cuando apetece callejear, esto encaja",
        ],
        "romantica": [
            "Un plan para dos que sale redondo",
            "Hay una escapada para dos que no esperas",
            "Este plan de pareja encaja demasiado bien",
        ],
        "gastro": [
            "Este plan se come… literalmente",
            "Hay un finde para comer bien que sorprende",
            "Un plan foodie que encaja mejor ahora",
        ],
        "finde": [
            "Un fin de semana que se decide en un minuto",
            "Este finde se te pone demasiado fácil",
            "El plan perfecto para desconectar un poco",
        ],
        "ultra": [
            "Esto suele salir mucho peor de precio",
            "Hay un precio que no cuadra con esto",
            "No debería estar así de bien ahora mismo",
        ],
    }


    angle_templates = {
        "descubrimiento": [
            "No tenías este {trip} en mente",
            "Este plan aparece cuando menos lo esperas",
            "No es el primer sitio que pensarías",
        ],
        "timing": [
            "Ahora mismo, este plan encaja",
            "Este es el momento para este {trip}",
            "Este {trip} tiene sentido justo ahora",
        ],
        "sorpresa": [
            "Esto no debería cuadrar… pero cuadra",
            "No encaja sobre el papel, pero funciona",
            "Parece raro, pero es muy buena idea",
        ],
        "facilidad": [
            "Este {trip} se decide en un minuto",
            "Más fácil de lo que parece",
            "Este plan se pone demasiado a tiro",
        ],
        "valor": [
            "Sale mucho mejor de lo normal",
            "Mejor de lo que esperarías",
            "Este {trip} sorprende por lo bien que sale",
        ],
    }
    
    # Intensidad por precio/descuento (pero sin decirlo)
    if cheap in ("muy", "bastante"):
        base_general += [
            "No es tan caro como parece",
            "Sale mucho mejor de lo normal",
        ]
        base_country += [
            "{country} no es tan caro como parece",
            "Lo de {country} hoy sale muy bien",
        ]
        if cat == "ultra":
            base_general += [
                "Esto no dura, te aviso",
                "Ojo, porque esto vuela",
            ]

    question_templates = [
        "¿Y si este {trip} fuera mejor de lo que crees?",
        "¿Seguro que este no es el momento?",
        "¿Por qué este plan encaja tanto ahora?",
    ]

    contrast_templates = [
        "No es lo típico. Por eso funciona",
        "No parece el plan ideal, hasta que lo es",
        "No es obvio. Y justo ahí está lo bueno",
    ]

    # Pool de candidatos según señales
    pools: list[list[str]] = []
    pools.append(cat_bias.get(cat, []))
    pools.append(base_general)
    pools.append(angle_templates.get(angle, []))
    pools.append(question_templates)
    pools.append(contrast_templates)
    pools.append(duration_bias)
    if country:
        pools.append(base_country)
    if season and cat in ("cultural", "finde", "romantica"):
        pools.append(base_season)

    # Elegir pool y plantilla
    pool = _pick([p for p in pools if p], seed + "|pool")
    tmpl = _pick(pool, seed + "|tmpl")

    hook = tmpl.format(country=country, season=season, trip=trip).strip()
    hook = _sentence_case(hook)

    variant = int(hashlib.sha256(seed.encode()).hexdigest(), 16) % 3

    if variant == 1:
        hook = hook.replace("Este ", "")
    elif variant == 2:
        hook = hook.replace("Este ", "Un ")

    # -----------------------------
    # Control de longitud: si se pasa, simplificamos (sin country/season)
    # -----------------------------
    if not _fits_len(hook, max_len):
        # 1) si contiene country, quitamos "a {country}" o "{country}"
        if country and "{country}" in tmpl:
            hook2 = tmpl.replace(" a {country}", "").replace("{country}", "Europa").format(
                country=country, season=season, trip=trip
            ).strip()
            hook2 = _sentence_case(hook2)
            if _fits_len(hook2, max_len):
                return hook2

        # 2) fallback a pool general corto
        short_pool = [
            "Esto no debería cuadrar… pero cuadra",
            "Te va a sorprender lo bien que encaja",
            "Este plan encaja mejor de lo que crees",
            "Hay una forma mejor de hacerlo",
        ]
        hook3 = _sentence_case(_pick(short_pool, seed + "|short"))
        if _fits_len(hook3, max_len):
            return hook3

        # 3) último recurso: cortar (poco probable)
        return hook[:max_len].rstrip(" .,")

    return hook
