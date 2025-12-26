# web/exporter.py
from __future__ import annotations
import json
from pathlib import Path
from datetime import datetime, date
from typing import Dict, Any, List, Optional

from content.destinations import get_city


# ✅ Mapea market -> carpeta web
MARKET_SLUG = {
    "PMI": "mallorca",
    "BCN": "barcelona",
    "MAD": "madrid",
    # si activas más:
    "VLC": "valencia",
    "AGP": "malaga",
    "ALC": "alicante",
    "TFN": "tenerife",
}


def get_market_web_dir(market: str, web_root: str | Path = "web") -> Path:
    market = (market or "").upper().strip()
    slug = MARKET_SLUG.get(market)
    if not slug:
        raise ValueError(f"Market '{market}' no tiene slug configurado en MARKET_SLUG")
    return Path(web_root) / slug


def _fget(obj: Any, attr: str, default=None):
    """Devuelve obj.attr o obj[attr] indistintamente (Flight o dict)."""
    if isinstance(obj, dict):
        return obj.get(attr, default)
    return getattr(obj, attr, default)


def _ensure_iso_date(d) -> str:
    """
    Convierte varias formas de fecha a 'YYYY-MM-DD'.
    Acepta:
      - date/datetime
      - 'YYYY-MM-DD'
      - ISO 'YYYY-MM-DDTHH:MM:SS(.sss)Z'
      - 'YYYY-MM-DD HH:MM:SS'
    """
    if d is None:
        return ""
    if hasattr(d, "strftime"):
        return d.strftime("%Y-%m-%d")
    s = str(d).strip()
    if not s:
        return ""
    if "T" in s:
        s = s.split("T")[0]
    if " " in s:
        s = s.split(" ")[0]
    return s[:10]


def _float_or_none(x) -> Optional[float]:
    try:
        if x is None or x == "":
            return None
        return float(x)
    except Exception:
        return None


def _build_flight_entry(
    item: Dict[str, Any],
    market: str,
    reel_url: Optional[str] = None,
    affiliate_url: Optional[str] = None,
) -> Dict[str, Any]:
    f = item["flight"]
    cat = item.get("category") or {}
    score = item.get("score")

    origin_iata = (_fget(f, "origin") or _fget(f, "origin_iata") or "").upper()
    dest_iata = (_fget(f, "destination") or _fget(f, "destination_iata") or "").upper()

    origin_city = get_city(origin_iata, include_flag=False) if origin_iata else ""
    dest_city = get_city(dest_iata, include_flag=False) if dest_iata else ""

    start_date = _ensure_iso_date(_fget(f, "start_date", None))
    end_date = _ensure_iso_date(_fget(f, "end_date", None))

    price_eur = _float_or_none(_fget(f, "price", None))
    price_per_km = _float_or_none(_fget(f, "price_per_km", None))
    distance_km = _float_or_none(_fget(f, "distance_km", None))
    route_typical = _float_or_none(_fget(f, "route_typical_price", None))
    discount_pct = _float_or_none(_fget(f, "discount_pct", None))

    featured_today = date.today().strftime("%Y-%m-%d")

    entry_id = f"{featured_today}_{origin_iata.lower()}_{dest_iata.lower()}_{start_date}_{end_date}"
    now_iso = datetime.utcnow().isoformat(timespec="seconds") + "Z"

    return {
        "id": entry_id,
        "date_featured": featured_today,
        "market": market,

        "category_code": cat.get("code"),
        "category_label": cat.get("label"),

        "origin_iata": origin_iata,
        "origin_city": origin_city,
        "destination_iata": dest_iata,
        "destination_city": dest_city,

        "start_date": start_date,
        "end_date": end_date,

        "price_eur": price_eur,
        "price_per_km": price_per_km,
        "route_typical_price": route_typical,
        "discount_pct": discount_pct,
        "distance_km": distance_km,
        "score": _float_or_none(score),

        "airline": _fget(f, "airline", None),

        "booking_url": _fget(f, "link", None),
        "affiliate_url": affiliate_url,
        "reel_url": reel_url,

        "created_at": now_iso,
    }


def update_flights_json(
    main_item: Dict[str, Any],
    json_path: Path | str,
    market: str,
    reel_url: Optional[str] = None,
    affiliate_url: Optional[str] = None,
    max_entries: int = 10,
    dedupe_by_id: bool = True,
    dedupe_by_route_dates: bool = True,
) -> Dict[str, Any]:
    """
    Actualiza el JSON con el vuelo del día.

    - json_path: ruta al fichero JSON de la web.
    - market: código de mercado ("PMI", "BCN"...).
    """

    json_path = Path(json_path)
    json_path.parent.mkdir(parents=True, exist_ok=True)

    if json_path.exists():
        try:
            with json_path.open("r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            data = {}
    else:
        data = {}

    flights: List[Dict[str, Any]] = data.get("flights", [])
    if not isinstance(flights, list):
        flights = []

    new_entry = _build_flight_entry(
        main_item,
        market=market,
        reel_url=reel_url,
        affiliate_url=affiliate_url,
    )

    new_id = new_entry["id"]

    if dedupe_by_id:
        flights = [x for x in flights if x.get("id") != new_id]

    if dedupe_by_route_dates:
        o = new_entry.get("origin_iata")
        d = new_entry.get("destination_iata")
        sd = new_entry.get("start_date")
        ed = new_entry.get("end_date")
        flights = [
            x for x in flights
            if not (
                x.get("origin_iata") == o and
                x.get("destination_iata") == d and
                x.get("start_date") == sd and
                x.get("end_date") == ed
            )
        ]

    flights.insert(0, new_entry)

    if max_entries is not None and max_entries > 0:
        flights = flights[:max_entries]

    now_iso = datetime.utcnow().isoformat(timespec="seconds") + "Z"
    new_data = {
        "market": market,
        "updated_at": now_iso,
        "today_id": new_id,
        "flights": flights,
    }

    with json_path.open("w", encoding="utf-8") as f:
        json.dump(new_data, f, ensure_ascii=False, indent=2)

    return new_data


def update_market_web_jsons(
    main_item: Dict[str, Any],
    market: str,
    web_root: str | Path = "web",
    reel_url: Optional[str] = None,
    affiliate_url: Optional[str] = None,
    max_entries: int = 10,
) -> Dict[str, Dict[str, Any]]:
    """
    Actualiza los JSONs de la web para un market en su carpeta:
      - web/<slug>/flights.json
      - web/<slug>/flights_of_the_day.json

    Devuelve dict con ambos resultados.
    """
    out_dir = get_market_web_dir(market, web_root=web_root)
    out_dir.mkdir(parents=True, exist_ok=True)

    flights_json = out_dir / "flights.json"
    flights_today_json = out_dir / "flights_of_the_day.json"

    r1 = update_flights_json(
        main_item=main_item,
        json_path=flights_json,
        market=market,
        reel_url=reel_url,
        affiliate_url=affiliate_url,
        max_entries=max_entries,
    )

    r2 = update_flights_json(
        main_item=main_item,
        json_path=flights_today_json,
        market=market,
        reel_url=reel_url,
        affiliate_url=affiliate_url,
        max_entries=max_entries,
        # en "of_the_day" normalmente quieres solo 1 entrada (opcional)
    )

    return {"flights": r1, "flights_of_the_day": r2}
