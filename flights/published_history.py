# flights/published_history.py
from __future__ import annotations

import json
from pathlib import Path
from datetime import date, datetime
from typing import Dict, Any, Optional, Tuple

HISTORY_FILE = Path("published_deals.json")


# ----------------- helpers de carga/guardado ----------------- #

def _load_history() -> Dict[str, dict]:
    if not HISTORY_FILE.exists():
        return {}
    with open(HISTORY_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def _save_history(history: Dict[str, dict]) -> None:
    HISTORY_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(history, f, ensure_ascii=False, indent=2)


# ----------------- helpers fecha / Flight o dict ----------------- #

def _iso_date_yyyy_mm_dd(x: Any) -> str:
    """Devuelve 'YYYY-MM-DD' desde date/datetime/ISO str."""
    if not x:
        return ""
    if hasattr(x, "strftime"):
        return x.strftime("%Y-%m-%d")
    s = str(x).strip()
    if not s:
        return ""
    if "T" in s:
        s = s.split("T")[0]
    if " " in s:
        s = s.split(" ")[0]
    return s[:10]


def _parse_pub_date(published_at) -> Optional[date]:
    """
    published_at puede ser 'YYYY-MM-DD' o ISO datetime.
    """
    if not published_at:
        return None
    s = str(published_at).strip()
    if not s:
        return None

    # si viene con T, nos quedamos con la fecha
    if "T" in s:
        s = s.split("T")[0]

    try:
        return date.fromisoformat(s[:10])
    except ValueError:
        try:
            return datetime.fromisoformat(str(published_at)).date()
        except ValueError:
            return None


def _fget(f: Any, attr: str, default=None):
    """Devuelve f.attr o f[attr] indistintamente."""
    if isinstance(f, dict):
        return f.get(attr, default)
    return getattr(f, attr, default)


def _route_from_key(key: str) -> Tuple[str, str]:
    """
    key: ORIGIN-DEST-YYYY-MM-DD-YYYY-MM-DD
    Ojo: al hacer split("-"), las fechas también se parten.
    Aun así, ORIGIN es parts[0], DEST es parts[1].
    """
    parts = key.split("-")
    origin = parts[0] if len(parts) >= 1 else ""
    dest = parts[1] if len(parts) >= 2 else ""
    return origin, dest


def make_flight_key(f: Any) -> str:
    """
    Clave exacta: ORIGIN-DEST-YYYY-MM-DD-YYYY-MM-DD
    Ej: PMI-BER-2026-02-06-2026-02-09
    """
    start_raw = _fget(f, "start_date", "") or _fget(f, "startDate", "")
    end_raw = _fget(f, "end_date", "") or _fget(f, "endDate", "")

    start = _iso_date_yyyy_mm_dd(start_raw)
    end = _iso_date_yyyy_mm_dd(end_raw)

    origin = (_fget(f, "origin", "") or _fget(f, "origin_iata", "") or "").upper()
    dest = (_fget(f, "destination", "") or _fget(f, "destination_iata", "") or "").upper()

    return f"{origin}-{dest}-{start}-{end}"


def is_recently_published(
    f: Any,
    cooldown_days: int = 14,        # mismo origen+destino+fechas
    route_cooldown_days: int = 5,   # mismo origen+destino (sin fechas)
) -> bool:
    """
    True si:
      1) se publicó EXACTAMENTE (origen+destino+fechas) en los últimos cooldown_days, o
      2) se publicó (origen+destino) en los últimos route_cooldown_days (cualquier fecha)
    """
    history = _load_history()
    today = date.today()

    # 1) cooldown exacto (ruta + fechas)
    key = make_flight_key(f)
    data = history.get(key)
    if data:
        pub_date = _parse_pub_date(data.get("published_at"))
        if pub_date and (today - pub_date).days < cooldown_days:
            return True

    # 2) cooldown por ruta (origen+destino) sin fechas
    if route_cooldown_days and route_cooldown_days > 0:
        origin_cur = (_fget(f, "origin", "") or _fget(f, "origin_iata", "") or "").upper()
        dest_cur = (_fget(f, "destination", "") or _fget(f, "destination_iata", "") or "").upper()

        if origin_cur and dest_cur:
            newest: Optional[date] = None
            for k, v in history.items():
                o, d = _route_from_key(k)
                if o.upper() != origin_cur or d.upper() != dest_cur:
                    continue

                pub_date = _parse_pub_date(v.get("published_at"))
                if not pub_date:
                    continue

                if newest is None or pub_date > newest:
                    newest = pub_date

            if newest and (today - newest).days < route_cooldown_days:
                return True

    return False


def register_publication(f: Any, category_code: str) -> None:
    """
    Registra que este vuelo se ha publicado hoy, con su categoría.
    Acepta Flight o dict.
    """
    history = _load_history()
    key = make_flight_key(f)
    history[key] = {
        "published_at": date.today().isoformat(),
        "category": category_code,
    }
    _save_history(history)
