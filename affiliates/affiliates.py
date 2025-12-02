from __future__ import annotations
from dataclasses import asdict
from datetime import datetime
from typing import Optional
from urllib.parse import urlencode, quote_plus
import urllib.parse


from flights.base import Flight

from config.settings import (
    TRAVELPAYOUTS_MARKER,
    TRAVELPAYOUTS_KIWI_PROMO_ID,
    TRAVELPAYOUTS_KIWI_BASE,
    SKYSCANNER_ASSOCIATE_ID,
    SKYSCANNER_BASE,
    SKYSCANNER_MARKET,
    SKYSCANNER_LOCALE,
    SKYSCANNER_CURRENCY,
)


def _extract_ymd(date_str: str) -> Optional[str]:
    """
    Recibe algo tipo '2025-12-05 19:25:00' o '2025-12-05T19:25:00.000Z'
    y devuelve '2025-12-05'.
    """
    if not date_str:
        return None

    # Normalizamos: quitamos 'Z' y cambiamos 'T' por espacio
    s = date_str.replace("Z", " ").replace("T", " ")
    # Nos quedamos con la parte antes del espacio
    return s.split(" ")[0]


def build_skyscanner_affiliate_link(
    flight: Flight,
    market: str = "ES",
    locale: str = "es-ES",
    currency: str = "EUR",
    adultsv2: int = 1,
    cabinclass: str = "economy",
) -> str:
    """
    Devuelve un deep-link de Skyscanner con parámetros de origen/destino/fechas.
    """
    origin = flight.origin
    dest = flight.destination

    outbound = _extract_ymd(flight.start_date)
    inbound = _extract_ymd(flight.end_date)

    params = {
        "origin": origin,
        "destination": dest,
        "outboundDate": outbound,
        "inboundDate": inbound,
        "adultsv2": adultsv2,
        "cabinclass": cabinclass,
        "market": market,
        "locale": locale,
        "currency": currency,
        "mediaPartnerId": SKYSCANNER_ASSOCIATE_ID,
    }

    return f"{SKYSCANNER_BASE}?{urlencode(params)}"

# def build_kiwi_deep_link(origin_iata, dest_iata, start_date, end_date):
#     # fechas en 'YYYY-MM-DD'
#     base = "https://www.kiwi.com/deep"
#     params = {
#         "from": origin_iata,
#         "to": dest_iata,
#         "departure": start_date,
#     }
#     if end_date:
#         params["return"] = end_date

#     from urllib.parse import urlencode
#     return f"{base}?{urlencode(params)}"

def build_kiwi_deep_link(origin_iata, dest_iata, start_date, end_date):
    base = "https://www.kiwi.com/deep"
    params = {
        "from": origin_iata,
        "to": dest_iata,
        "departure": start_date,  # YYYY-MM-DD
    }
    if end_date:
        params["return"] = end_date

    return f"{base}?{urlencode(params)}"

def build_kiwi_public_search_link(origin, dest, start_date, end_date):
    # Formato oficial aceptado por Travelpayouts
    # https://www.kiwi.com/es/search/results/PMI-VIE/2025-12-04/2025-12-07
    start = start_date[:10]
    end = end_date[:10]
    return f"https://www.kiwi.com/es/search/results/{origin}-{dest}/{start}/{end}"



def build_kiwi_affiliate_link(origin_iata, dest_iata, start_date, end_date):
    # 1) Deep link puro de Kiwi
    deep = build_kiwi_deep_link(origin_iata, dest_iata, start_date, end_date)

    # 2) URL-encode del deep link
    encoded = urllib.parse.quote(deep, safe="")

    # 3) Enlace de Travelpayouts
    params = {
        "shmarker": TRAVELPAYOUTS_MARKER,
        "promo_id": TRAVELPAYOUTS_KIWI_PROMO_ID,
        "source_type": "customlink",
        "type": "click",
        "custom_url": encoded,
    }
    return f"{TRAVELPAYOUTS_KIWI_BASE}?{urllib.parse.urlencode(params)}"
    


# def build_kiwi_affiliate_link_direct(flight: Flight) -> str:
#     """
#     Si prefieres usar directamente Kiwi sin Travelpayouts,
#     usa este helper en vez del de Travelpayouts.
#     """
#     origin = flight.origin
#     dest = flight.destination
#     outbound = _extract_ymd(flight.start_date)
#     inbound = _extract_ymd(flight.end_date)

#     return build_kiwi_deep_link(
#         origin_iata=origin,
#         dest_iata=dest,
#         start_date=outbound,
#         end_date=inbound,
#     )


def build_affiliate_url_for_flight(f: Flight) -> Optional[str]:
    origin = f.origin
    dest = f.destination

    # normalizar fechas a YYYY-MM-DD
    start = str(f.start_date)[:10]
    end   = str(f.end_date)[:10]

    if (f.airline or "").lower() == "ryanair":
        return build_skyscanner_affiliate_link(f)
    else:
        return build_kiwi_affiliate_link(origin, dest, start, end)