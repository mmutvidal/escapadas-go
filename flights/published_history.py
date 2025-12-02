import json
from pathlib import Path
from datetime import date, datetime
from typing import Dict
from flights.base import Flight

HISTORY_FILE = Path("published_deals.json")

def _load_history() -> Dict[str, dict]:
    if not HISTORY_FILE.exists():
        return {}
    with open(HISTORY_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def _save_history(history: Dict[str, dict]) -> None:
    HISTORY_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(history, f, ensure_ascii=False, indent=2)


def make_flight_key(f: Flight) -> str:
    # solo fecha, sin hora
    start = f.start_date[:10]
    end = f.end_date[:10]
    return f"{f.origin}-{f.destination}-{start}-{end}"


def is_recently_published(f: Flight, cooldown_days: int = 14) -> bool:
    history = _load_history()
    key = make_flight_key(f)
    data = history.get(key)
    if not data:
        return False

    pub_date = date.fromisoformat(data["published_at"])
    return (date.today() - pub_date).days < cooldown_days


def register_publication(f: Flight, category_code: str) -> None:
    history = _load_history()
    key = make_flight_key(f)
    history[key] = {
        "published_at": date.today().isoformat(),
        "category": category_code,
    }
    _save_history(history)