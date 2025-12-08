# web/exporter.py  (o el módulo que prefieras)
from __future__ import annotations
import json
from pathlib import Path
from datetime import datetime, date
from typing import Dict, Any, List, Optional

from content.destinations import get_city


def _fget(obj: Any, attr: str, default=None):
    """Devuelve obj.attr o obj[attr] indistintamente (Flight o dict)."""
    if isinstance(obj, dict):
        return obj.get(attr, default)
    return getattr(obj, attr, default)
    

def _ensure_iso_date(d) -> str:
    """Convierte varias formas de fecha a 'YYYY-MM-DD'."""
    if d is None:
        return ""
    if hasattr(d, "strftime"):
        return d.strftime("%Y-%m-%d")
    s = str(d)
    return s.split(" ")[0]  # por si viene 'YYYY-MM-DD HH:MM:SS'


def _float_or_none(x) -> Optional[float]:
    try:
        if x is None:
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
    cat = item["category"]
    score = item.get("score")

    # Soportar Flight o dict
    origin_iata = _fget(f, "origin")
    dest_iata   = _fget(f, "destination")

    origin_city = get_city(origin_iata, include_flag=False)
    dest_city   = get_city(dest_iata, include_flag=False)

    start_date = _ensure_iso_date(_fget(f, "start_date", None))
    end_date   = _ensure_iso_date(_fget(f, "end_date", None))

    price_eur     = _float_or_none(_fget(f, "price", None))
    price_per_km  = _float_or_none(_fget(f, "price_per_km", None))
    distance_km   = _float_or_none(_fget(f, "distance_km", None))
    route_typical = _float_or_none(_fget(f, "route_typical_price", None))
    discount_pct  = _float_or_none(_fget(f, "discount_pct", None))

    featured_today = date.today().strftime("%Y-%m-%d")
    entry_id = f"{featured_today}_{origin_iata.lower()}_{dest_iata.lower()}"

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
    json_path: Path | str = Path("web/mallorca/flights_of_the_day.json"),
    market: str = "PMI",
    reel_url: Optional[str] = None,
    affiliate_url: Optional[str] = None,
    max_entries: int = 10,
) -> Dict[str, Any]:
    """
    Actualiza el fichero flights_of_the_day.json con el vuelo del día.

    - main_item: item de best_by_cat elegido como "vuelo del día"
                 ({"flight": Flight, "category": {...}, "score": ...})
    - json_path: ruta al fichero JSON de la web.
    - market: código de mercado (para Mallorca, "PMI"; en el futuro BCN/MAD).
    - reel_url: enlace público al Reel de Instagram (si ya lo tienes).
    - affiliate_url: enlace de afiliado (Skyscanner/Tequila) si lo usas.
    - max_entries: nº máximo de vuelos a conservar (incluyendo el de hoy).

    Devuelve el dict completo que se ha guardado en el JSON.
    """

    json_path = Path(json_path)
    json_path.parent.mkdir(parents=True, exist_ok=True)

    # 1) Cargar estado anterior (si existe)
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

    # 2) Construir nueva entrada desde main_item
    new_entry = _build_flight_entry(
        main_item,
        market=market,
        reel_url=reel_url,
        affiliate_url=affiliate_url,
    )

    new_id = new_entry["id"]

    # # 3) Eliminar cualquier entrada previa con ese mismo id
    # flights = [f for f in flights if f.get("id") != new_id]

    # 4) Insertar el nuevo vuelo al principio (vuelo del día)
    flights.insert(0, new_entry)

    # 5) Recortar histórico a max_entries
    if max_entries is not None and max_entries > 0:
        flights = flights[:max_entries]

    # 6) Construir estructura final
    now_iso = datetime.utcnow().isoformat(timespec="seconds") + "Z"
    new_data = {
        "market": market,
        "updated_at": now_iso,
        "today_id": new_id,
        "flights": flights,
    }

    # 7) Guardar JSON
    with json_path.open("w", encoding="utf-8") as f:
        json.dump(new_data, f, ensure_ascii=False, indent=2)

    return new_data
