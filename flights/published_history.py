# flights/published_history.py

import json
from pathlib import Path
from datetime import date, datetime
from typing import Dict, Any

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


# ----------------- helpers para Flight o dict ----------------- #

def _fget(f: Any, attr: str, default=None):
    """Devuelve f.attr o f[attr] indistintamente."""
    if isinstance(f, dict):
        return f.get(attr, default)
    return getattr(f, attr, default)


def make_flight_key(f: Any) -> str:
    """
    Construye una clave tipo:
      PMI-STN-2026-01-15-2026-01-19
    a partir de un Flight o de un dict con los mismos campos.
    """
    start_raw = _fget(f, "start_date", "") or _fget(f, "startDate", "")
    end_raw = _fget(f, "end_date", "") or _fget(f, "endDate", "")

    start = str(start_raw)[:10]
    end = str(end_raw)[:10]

    origin = _fget(f, "origin", "") or _fget(f, "origin_iata", "")
    destination = _fget(f, "destination", "") or _fget(f, "destination_iata", "")

    return f"{origin}-{destination}-{start}-{end}"


def is_recently_published(f: Any, cooldown_days: int = 14) -> bool:
    """
    Devuelve True si este vuelo (misma ruta + mismas fechas) se ha
    publicado en los últimos `cooldown_days` días.
    """
    history = _load_history()
    key = make_flight_key(f)
    data = history.get(key)
    if not data:
        return False

    published_at = data.get("published_at")
    if not published_at:
        return False

    try:
        pub_date = date.fromisoformat(str(published_at))
    except ValueError:
        try:
            pub_date = datetime.fromisoformat(str(published_at)).date()
        except ValueError:
            return False

    return (date.today() - pub_date).days < cooldown_days


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
