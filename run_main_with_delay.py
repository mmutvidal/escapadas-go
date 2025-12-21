# run_with_random_publish_time.py
from __future__ import annotations

import os
import random
import time
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

# Importa tu flujo
from main import run_daily_workflow  # ajusta import según tu proyecto


TZ = ZoneInfo("Europe/Madrid")

# Ventanas por día (0=lunes ... 6=domingo)
# Formato: (hora_inicio, minuto_inicio, hora_fin, minuto_fin)
WINDOWS = {
    0: ((19, 0), (20, 30)),   # L
    1: ((19, 0), (20, 30)),   # M
    2: ((19, 0), (20, 30)),   # X
    3: ((19, 0), (20, 30)),   # J
    4: ((18, 30), (20, 30)),  # V
    5: ((18, 30), (20, 30)),    # S (mediodía)
    6: ((18, 30), (20, 30)),   # D (tarde)
}

# Pequeño “jitter” extra para que no caiga siempre en el mismo minuto exacto
EXTRA_JITTER_SECONDS = 20


def choose_random_time_today(now: datetime) -> datetime:
    wd = now.weekday()
    (h1, m1), (h2, m2) = WINDOWS.get(wd, ((19, 0), (20, 30)))

    start = now.replace(hour=h1, minute=m1, second=0, microsecond=0)
    end = now.replace(hour=h2, minute=m2, second=0, microsecond=0)

    # Si por lo que sea ya estamos fuera de ventana (o se ejecuta tarde),
    # lo lanzamos “ya” con un pequeño retraso aleatorio.
    if now >= end:
        return now + timedelta(seconds=random.randint(10, 60))

    # Elegimos un minuto aleatorio dentro de la ventana
    total_seconds = int((end - start).total_seconds())
    offset = random.randint(0, total_seconds)
    target = start + timedelta(seconds=offset)

    # Añadimos jitter pequeño para no ser exactos
    target += timedelta(seconds=random.randint(0, EXTRA_JITTER_SECONDS))
    return target


def main():
    now = datetime.now(TZ)
    target = choose_random_time_today(now)

    sleep_s = max(0, int((target - now).total_seconds()))

    print(f"[scheduler] Ahora:   {now.isoformat()}")
    print(f"[scheduler] Objetivo:{target.isoformat()}")
    print(f"[scheduler] Durmiendo {sleep_s} segundos...")

    time.sleep(sleep_s)

    # Lanza tu flujo
    run_daily_workflow(auto_publish=False)


if __name__ == "__main__":
    main()