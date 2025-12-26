# flights/aggregator.py

from typing import List, Optional, Tuple
from datetime import date, timedelta

from flights.base import Flight
from flights.api_ryanair import RyanairAPI
from flights.api_kiwi import KiwiAPI

from datetime import datetime
# from flights.base import Flight
import random
from typing import Dict, Any, List

from collections import defaultdict
import statistics
from math import floor, ceil


# import flights.flights_settings

# import json
# from pathlib import Path
# from datetime import date, datetime
# from typing import Dict
# # from base import Flight

# HISTORY_FILE = Path("published_deals.json")

import flights.published_history as ph


PRIORITY_DESTINATIONS = {
    "BLQ": 30,   # Bologna
    "MXP": 25,
    "BGY": 20,
    "FCO": 20,
}

PREFERRED_AIRLINES = {
    "Ryanair": 15,
    "Vueling": 10,
}



# DESTINATION_TAGS = {
#     "PAR": ["romantica", "cultural", "gastronomica"],
#     "ORY": ["romantica", "cultural"],
#     "CDG": ["romantica", "cultural"],
#     "VCE": ["romantica", "cultural"],
#     "VRN": ["romantica"],
#     "FCO": ["cultural", "gastronomica"],
#     "CIA": ["cultural"],
#     "BLQ": ["cultural", "gastronomica"],
#     "LIS": ["cultural", "gastronomica"],
#     "OPO": ["cultural", "gastronomica"],
#     "SEV": ["cultural", "gastronomica"],
#     "SVQ": ["cultural", "gastronomica"],
#     "BCN": ["cultural", "gastronomica"],
#     "MAD": ["cultural"],
#     "BUD": ["romantica", "cultural"],
# }

DESTINATION_TAGS = {
    # 🌍 Norte / Centro Europa
    "CPH": ["romantica", "cultural", "gastronomica"],      # Copenhague
    "ARN": ["romantica", "cultural", "gastronomica"],      # Estocolmo
    "GOT": ["cultural", "gastronomica"],                   # Gotemburgo
    "EDI": ["romantica", "cultural"],                      # Edimburgo
    "ATH": ["cultural", "gastronomica"],                   # Atenas

    "DUB": ["cultural", "gastronomica"],                   # Dublín
    "HAM": ["cultural"],                                   # Hamburgo
    "BER": ["cultural", "gastronomica"],                   # Berlín
    "BUD": ["romantica", "cultural"],                      # Budapest
    "DRS": ["cultural"],                                   # Dresde
    "LEJ": ["cultural"],                                   # Leipzig
    "PRG": ["romantica", "cultural", "gastronomica"],      # Praga
    "VIE": ["romantica", "cultural", "gastronomica"],      # Viena
    "AMS": ["romantica", "cultural", "gastronomica"],      # Ámsterdam

    "CGN": ["cultural", "gastronomica"],                   # Colonia
    "ZAG": ["cultural"],                                   # Zagreb
    "NUE": ["cultural", "gastronomica"],                   # Núremberg
    "BRU": ["cultural", "gastronomica"],                   # Bruselas
    "FRA": ["cultural"],                                   # Frankfurt
    "WAW": ["cultural", "gastronomica"],                   # Varsovia
    "MUC": ["cultural", "gastronomica"],                   # Múnich

    "ZRH": ["romantica", "cultural", "gastronomica"],      # Zúrich
    "BSL": ["cultural", "gastronomica"],                   # Basilea

    # ✈️ Aeropuertos “low cost” que sirven a ciudades potentes
    "LTN": ["cultural"],                   # Londres (Luton)
    "STN": ["cultural"],                   # Londres (Stansted)
    "LGW": ["cultural"],                   # Londres (Gatwick)

    # RAK – Marruecos
    "RAK": ["romantica", "cultural", "gastronomica"],      # Marrakech

    # 🇵🇹 Portugal
    "LIS": ["cultural", "gastronomica"],                   # Lisboa
    "OPO": ["cultural", "gastronomica"],                   # Oporto

    # 🇮🇹 Italia
    "NAP": ["cultural", "gastronomica"],                   # Nápoles
    "BLQ": ["cultural", "gastronomica"],                   # Bolonia
    "BGY": ["romantica", "cultural", "gastronomica"],      # Bérgamo / área Milán
    "FCO": ["cultural", "gastronomica"],                   # Roma Fiumicino
    "MXP": ["romantica", "cultural", "gastronomica"],      # Milán Malpensa
    "PSA": ["cultural", "gastronomica"],                   # Pisa / Toscana
    "TSF": ["romantica", "cultural", "gastronomica"],      # Treviso (área Venecia)

    # 🇫🇷 Francia / Suiza francófona
    "ORY": ["romantica", "cultural"],                      # París Orly
    "GVA": ["romantica", "cultural", "gastronomica"],      # Ginebra
    "LYS": ["cultural", "gastronomica"],                   # Lyon
    "MRS": ["cultural", "gastronomica"],                   # Marsella
    "TLS": ["cultural", "gastronomica"],                   # Toulouse

    # 🇪🇸 España (península)
    "SCQ": ["cultural", "gastronomica"],                   # Santiago de Compostela
    "SVQ": ["cultural", "gastronomica"],                   # Sevilla
    "AGP": ["gastronomica", "cultural"],                   # Málaga
    "BIO": ["cultural", "gastronomica"],                   # Bilbao
    "GRX": ["romantica", "cultural", "gastronomica"],      # Granada
    "VIT": ["cultural", "gastronomica"],                   # Vitoria
    "MAD": ["cultural", "gastronomica"],                   # Madrid
    "ZAZ": ["cultural", "gastronomica"],                   # Zaragoza
    "ALC": ["gastronomica"],                               # Alicante
    "VLC": ["cultural", "gastronomica"],                   # Valencia
    "XRY": ["cultural", "gastronomica"],                   # Jerez de la Frontera
    "OVD": ["gastronomica"],                               # Asturias (Oviedo/Gijón)
    "SDR": ["gastronomica"],                               # Santander

    # 🇪🇸 Islas / costa con enfoque más foodie
    "LPA": ["gastronomica"],                               # Las Palmas (Canarias)
}



DESTINATION_CATEGORY_LABELS = {
    "romantica":    "❤️ Escapada Romántica",
    "cultural":     "🏛 Escapada Cultural",
    "gastronomica": "🍝 Escapada Gastronómica",
}


def _percentile(values, q: float) -> float:
    """
    Percentil simple con interpolación lineal.
    q en [0,1]. Ej: 0.6 = percentil 60.
    """
    if not values:
        raise ValueError("Empty list")

    vals = sorted(values)
    n = len(vals)
    if n == 1:
        return vals[0]

    pos = (n - 1) * q
    lo = floor(pos)
    hi = ceil(pos)

    if lo == hi:
        return vals[lo]

    frac = pos - lo
    return vals[lo] + (vals[hi] - vals[lo]) * frac



def annotate_route_price_stats(
    flights: List["Flight"],
    use_percentile: float = 0.7,
    min_samples_for_percentile: int = 5,
) -> None:
    """
    Para cada ruta (origin, destination) calcula un precio 'habitual'
    y anota en cada Flight:
      - route_typical_price
      - discount_pct  (positivo = más barato que lo habitual)

    Estrategia:
      - si hay suficientes datos en la ruta, usar percentil (por defecto 60)
      - si no, usar mediana (más robusta)
    """
    prices_by_route = defaultdict(list)
    for f in flights:
        if f.price is not None:
            key = (f.origin, f.destination)
            prices_by_route[key].append(f.price)

    typical_by_route = {}
    for key, price_list in prices_by_route.items():
        if not price_list:
            continue

        # if len(price_list) >= min_samples_for_percentile and use_percentile is not None:
        #     # percentil 70 por defecto
        #     typical = _percentile(price_list, use_percentile)
        # else:
        #     # fallback conservador
        #     typical = statistics.median(price_list)

        typical = max(_percentile(price_list, use_percentile),statistics.mean(price_list))
        
        typical_by_route[key] = typical

    for f in flights:
        key = (f.origin, f.destination)
        typical = typical_by_route.get(key)
        if typical is None or typical <= 0 or f.price is None:
            f.route_typical_price = None
            f.discount_pct = None
            continue

        f.route_typical_price = round(typical, 2)
        discount = (typical - f.price) / typical * 100.0
        f.discount_pct = round(discount, 1)


def generate_weekend_date_pairs(start_date: date, end_date: date) -> List[Tuple[date, date]]:
    """
    Genera todas las combinaciones de:
    - Jueves  -> Domingo
    - Jueves  -> Lunes
    - Viernes -> Domingo
    - Viernes -> Lunes
    dentro del rango [start_date, end_date].
    """

    pairs = []
    current = start_date

    while current <= end_date:
        wd = current.weekday()  # 0=Lunes ... 3=Jueves, 4=Viernes, 6=Domingo

        # JUEVES
        if wd == 3:
            thu = current
            sun = thu + timedelta(days=3)
            mon = thu + timedelta(days=4)

            if sun <= end_date:
                pairs.append((thu, sun))  # Jueves-Domingo
            if mon <= end_date:
                pairs.append((thu, mon))  # Jueves-Lunes

        # VIERNES
        if wd == 4:
            fri = current
            sun = fri + timedelta(days=2)
            mon = fri + timedelta(days=3)

            if sun <= end_date:
                pairs.append((fri, sun))  # Viernes-Domingo
            if mon <= end_date:
                pairs.append((fri, mon))  # Viernes-Lunes

        current += timedelta(days=1)

    return pairs


def get_available_flights(start_date: date, end_date: date, origin_iata: str) -> List[Flight]:
    """
    Llama a todas las APIs para todos los combos de fechas
    generados en el rango [start_date, end_date].
    """

    apis = [
        RyanairAPI(origin=origin_iata),
        KiwiAPI(origin=origin_iata),
    ]

    all_flights: List[Flight] = []

    date_pairs = generate_weekend_date_pairs(start_date, end_date)

    for depart_date, return_date in date_pairs:
        depart_str = depart_date.isoformat()
        return_str = return_date.isoformat()

        print(f"🗓  Buscando vuelos {depart_str} → {return_str}...")

        for api in apis:
            try:
                flights = api.search(depart_str, return_str)
                if flights:
                    all_flights.extend(flights)
            except Exception as e:
                print(f"❌ Error consultando {api.__class__.__name__}: {e}")

    return all_flights


# --------- scoring --------- #


def score_flight(f: Flight) -> float:
    """
    Score balanceado:
    - 40% precio absoluto
    - 40% precio/km
    - 10% destino prioritario
    - 5% aerolínea
    - 5% popularidad (si no existe → 0)
    """

    # -------------------------
    # 1. Precio absoluto (normalizado)
    # menor precio → score más alto
    # supondremos rango típico 0€ - 300€
    # -------------------------
    max_price = 300
    norm_price = 1 - min(f.price / max_price, 1)   # 0 = caro, 1 = barato

    # -------------------------
    # 2. Precio por km (normalizado)
    # menor €/km → mejor
    # supondremos rango típico 0 - 0.50 €/km
    # -------------------------
    ppkm = f.price_per_km
    if ppkm is None:
        norm_ppkm = 0
    else:
        max_ppkm = 0.50
        norm_ppkm = 1 - min(ppkm / max_ppkm, 1)

    # -------------------------
    # 3. Destino prioritario (normalizado)
    # -------------------------
    dest_bonus_raw = PRIORITY_DESTINATIONS.get(f.destination, 0)
    max_dest_bonus = max(PRIORITY_DESTINATIONS.values()) if PRIORITY_DESTINATIONS else 1
    norm_destination = dest_bonus_raw / max_dest_bonus

    # -------------------------
    # 4. Aerolínea (normalizado)
    # -------------------------
    airline_bonus_raw = PREFERRED_AIRLINES.get(f.airline, 0)
    max_airline_bonus = max(PREFERRED_AIRLINES.values()) if PREFERRED_AIRLINES else 1
    norm_airline = airline_bonus_raw / max_airline_bonus

    # -------------------------
    # 5. Popularidad (opcional)
    # si no existe, se asume desconocido = 0
    # -------------------------
    popularity_raw = getattr(f, "popularity", 0)  # ej. rating del destino, búsquedas o lo que quieras
    norm_popularity = min(max(popularity_raw, 0), 1)  # ya debe venir 0–1

    # -------------------------
    # Aplicar pesos reales
    # -------------------------
    score = (
        norm_price       * 0.50 +
        norm_ppkm        * 0.50 +
        norm_destination * 0 +
        norm_airline     * 0 +
        norm_popularity  * 0
    )

    return score

def score_flight_basic(f: Flight) -> float:
    """
    Score simple combinado:
    - precio absoluto (más barato = mejor)
    - precio por km
    - % de descuento vs precio habitual de la ruta (si existe)

    Todos los términos se combinan en algo sencillo pero efectivo.
    """
    if f.price is None or f.price_per_km is None:
        return -999999  # descartamos vuelos mal formados

    # 1) Componentes inversos para precio y €/km
    price_component = 1 / max(f.price, 1)
    ppkm_component = 1 / max(f.price_per_km, 0.001)

    # 2) Descuento normalizado: 0 a 1 (cap a 90% para no disparar)
    discount_pct = getattr(f, "discount_pct", None) or 0.0
    discount_pct = max(discount_pct, 0.0)               # si es más caro que la media → 0
    discount_cap = 90.0
    discount_norm = min(discount_pct, discount_cap) / discount_cap

    # Pesos: 40% precio, 40% €/km, 20% descuento
    return (
        0.45 * price_component +
        0.25 * ppkm_component +
        0.3 * (1 + discount_norm)  # sumamos 1 para que siempre aporte algo
    )



def get_best_flight_in_period(start_date: date, end_date: date, origin_iata) -> Optional[Flight]:
    """
    Devuelve el mejor vuelo encontrado en el rango [start_date, end_date]
    usando el score que ya tienes definido (precio, price/km, etc.).
    """
    print(f"🔎 Buscando chollos entre {start_date} y {end_date}...")

    flights = get_available_flights(start_date, end_date, origin_iata)
    if not flights:
        print("⚠️ No se encontraron vuelos en ninguna API.")
        return None

    flights_sorted = sorted(flights, key=score_flight, reverse=True)
    best_flight = flights_sorted[0]

    ppkm = getattr(best_flight, "price_per_km", None)
    print(
        "✨ Mejor vuelo:",
        f"{best_flight.origin} → {best_flight.destination} | "
        f"{best_flight.price}€ | "
        f"{best_flight.airline} | "
        f"price/km={ppkm}"
    )

    return best_flight


def get_flights_in_period(start_date: date, end_date: date, origin_iata) -> List[Flight]:
    """
    Devuelve TODOS los vuelos encontrados en el rango [start_date, end_date]
    usando get_available_flights (que ya hace las combinaciones de días relevantes).
    """
    print(f"🔎 Buscando vuelos entre {start_date} y {end_date}...")

    flights = get_available_flights(start_date, end_date, origin_iata)
    if not flights:
        print("⚠️ No se encontraron vuelos en ninguna API.")
        return []

    annotate_route_price_stats(flights)

    print(f"✅ Encontrados {len(flights)} vuelos en total.")
    return flights

    
def classify_flight(f: Flight) -> dict:
    """
    PRIORIDAD:
    1) 🎉 Finde Perfecto
    2) 🔥 Ultra Chollo
    3) ❤️ / 🏛 / 🍝 (según destino)
    4) ✨ Escapada Perfecta (DEFAULT)
    """

    ppkm = f.price_per_km
    price = f.price

    dt_out = _parse_dt(f.start_date)
    dt_ret = _parse_dt(f.end_date)

    out_hour = dt_out.hour if dt_out else None
    ret_hour = dt_ret.hour if dt_ret else None
    duration_days = (
        (dt_ret - dt_out).days
        if dt_out and dt_ret
        else None
    )

    # 1) 🎉 FINDE PERFECTO
    if dt_out and dt_ret and duration_days is not None:
        if (
            dt_out.weekday() == 4 and        # viernes
            dt_ret.weekday() == 6 and        # domingo
            16 <= (out_hour or 0) <= 22 and
            15 <= (ret_hour or 0) <= 22 and
            1 <= duration_days <= 3
        ):
            return {"code": "finde_perfecto", "label": "🎉 Finde Perfecto"}
    # 2) CATEGORÍA POR DESTINO (romántica / cultural / gastronómica)
    dest_cat = pick_destination_category(f)
    if dest_cat is not None:
        return dest_cat

    return {"code": "ultra_chollo", "label": "🔥 Ultra Chollo"}
    
    # # 3) 🔥 ULTRA CHOLLO
    # if ppkm is not None and price is not None:
    #     if ppkm < 0.07 and price < 90:
    #         return {"code": "ultra_chollo", "label": "🔥 Ultra Chollo"}


    # # 4) ✨ ESCAPADA PERFECTA (DEFAULT)
    # # Si no entra en ninguna anterior, lo etiquetamos así.
    # # Puedes añadir alguna condición suave (duración mínima, etc.) si quieres.
    # if duration_days is not None and 1 <= duration_days <= 7:
    #     return {"code": "escapada_perfecta", "label": "✨ Escapada Perfecta"}

    # # fallback rarísimo (fechas rotas, etc.)
    # return {"code": "oferta", "label": "✈️ Oferta"}




def get_best_by_category_cheapest(
    flights: List[Flight],
    cooldown_days: int = 14,
    destination_cooldown_days: int = 5,
    min_discount_pct: float = 40.0,
) -> List[dict]:
    best_per_cat: Dict[str, dict] = {}

    for f in flights:
        if ph.is_recently_published(f, cooldown_days=cooldown_days, route_cooldown_days=route_cooldown_days):
            continue

        discount_pct = getattr(f, "discount_pct", None)
        if discount_pct is None or discount_pct < min_discount_pct:
            continue

        category = classify_flight(f)
        code = category["code"]

        price = getattr(f, "price", None)
        if price is None:
            continue

        current = best_per_cat.get(code)
        if current is None or price < current["flight"].price:
            best_per_cat[code] = {
                "flight": f,
                "category": category,
            }

    return list(best_per_cat.values())

    

def get_best_by_category_scored(
    flights: List[Flight],
    cooldown_days: int = 14,
    route_cooldown_days: int = 5,
    min_discount_pct: float = 40.0,  # ← aquí defines el mínimo (30–40%)
) -> List[dict]:

    best_per_cat: Dict[str, dict] = {}

    for f in flights:
        # 0) descartamos vuelos publicados hace poco
        if ph.is_recently_published(f, cooldown_days=cooldown_days, route_cooldown_days=route_cooldown_days):
            continue

        # 1) descartamos vuelos sin descuento suficiente
        discount_pct = getattr(f, "discount_pct", None)
        if discount_pct is None or discount_pct < min_discount_pct:
            continue

        # 2) clasificamos y puntuamos sólo los que pasan el filtro
        category = classify_flight(f)
        code = category["code"]

        # 👇 AÑADIR ESTO
        # Guardamos la categoría directamente en el Flight
        f.category_code = category.get("code")
        f.category_label = category.get("label")

        score = score_flight_basic(f)

        current = best_per_cat.get(code)
        if current is None or score > current["score"]:
            best_per_cat[code] = {
                "flight": f,
                "category": category,
                "score": score,
            }

    return list(best_per_cat.values())



def _parse_dt(dt_str: str):
    try:
        s = str(dt_str)
        if s.endswith("Z"):
            s = s[:-1]  # quitar Z
        # si tiene milisegundos tipo .000, fromisoformat lo soporta normalmente
        return datetime.fromisoformat(s)
    except Exception:
        return None


def pick_destination_category(f: Flight):
    tags = DESTINATION_TAGS.get(f.destination)
    if not tags:
        return None

    tag = random.choice(tags)
    label = DESTINATION_CATEGORY_LABELS.get(tag)
    if not label:
        return None

    return {"code": tag, "label": label}



def choose_main_candidate_prob(
    best_by_cat: List[Dict[str, Any]],
    rng: Optional[random.Random] = None,
) -> Optional[Dict[str, Any]]:
    """
    Elige el candidato del día con probabilidad ponderada por categoría.

    Grupos:
      - 'finde': category.code == 'finde_perfecto'
      - 'chollo': category.code in ('ultra_chollo', 'chollo')
      - 'other': resto de categorías

    Pesos base sobre grupos:
      finde  -> 0.30
      chollo -> 0.25
      other  -> 0.45

    Si algún grupo no tiene candidatos, se redistribuye el peso proporcionalmente
    entre los grupos restantes.

    Devuelve el item completo (dict) de best_by_cat, o None si la lista está vacía.
    """
    if not best_by_cat:
        return None

    if rng is None:
        rng = random

    groups = {
        "finde": [],
        "chollo": [],
        "other": [],
    }

    for item in best_by_cat:
        code = item.get("category", {}).get("code")
        if code == "finde_perfecto":
            groups["finde"].append(item)
        elif code in ("ultra_chollo", "chollo"):
            groups["chollo"].append(item)
        else:
            groups["other"].append(item)

    # Pesos base
    base_weights = {
        "finde": 0.40,
        "chollo": 0.20,
        "other": 0.40,
    }

    # Filtrar solo grupos que tienen candidatos
    available = [(name, items) for name, items in groups.items() if items]
    if not available:
        return None

    names = [name for name, _ in available]
    total_weight = sum(base_weights[name] for name, _ in available)

    # Probabilidades normalizadas
    probs = [base_weights[name] / total_weight for name in names]

    # Elegir grupo según peso
    r = rng.random()
    cumulative = 0.0
    chosen_group = names[-1]  # por si acaso
    for name, p in zip(names, probs):
        cumulative += p
        if r <= cumulative:
            chosen_group = name
            break

    candidates = groups[chosen_group]

    # Dentro del grupo elegido, escogemos el mejor por score (con desempate aleatorio)
    best_score = None
    best_items: List[Dict[str, Any]] = []
    for item in candidates:
        s = item.get("score", 0.0)
        if best_score is None or s > best_score:
            best_score = s
            best_items = [item]
        elif s == best_score:
            best_items.append(item)

    return rng.choice(best_items)

