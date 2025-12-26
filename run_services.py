import subprocess
import sys
import os
import time
import json
from pathlib import Path

BASE_DIR = Path(r"C:\Users\Macia\Desktop\Jupyter Notebooks\EscapadasMallorca")
LOCK_PATH = BASE_DIR / "services.lock.json"


def _pid_is_running(pid: int) -> bool:
    """Check simple sin dependencias (Windows)."""
    if not pid:
        return False
    try:
        # tasklist devuelve errorlevel != 0 si no existe
        out = subprocess.check_output(
            ["tasklist", "/FI", f"PID eq {pid}"],
            stderr=subprocess.STDOUT,
            text=True,
        )
        return str(pid) in out
    except Exception:
        return False


def _load_lock() -> dict:
    if LOCK_PATH.exists():
        try:
            return json.loads(LOCK_PATH.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}


def _save_lock(data: dict) -> None:
    LOCK_PATH.write_text(json.dumps(data, indent=2), encoding="utf-8")


def start_process(cmd, name: str):
    """
    Lanza un proceso en BASE_DIR.
    En Windows usamos CREATE_NEW_CONSOLE para que cada uno tenga su ventana.
    """
    creationflags = 0
    if os.name == "nt":
        creationflags = subprocess.CREATE_NEW_CONSOLE

    return subprocess.Popen(
        cmd,
        cwd=str(BASE_DIR),
        creationflags=creationflags,
    )


def ensure_telegram_bot():
    lock = _load_lock()
    pid = lock.get("telegram_review_pid")

    if pid and _pid_is_running(int(pid)):
        print(f"✅ Telegram review ya está corriendo (PID {pid}). No lo arranco de nuevo.")
        return None

    # Arranca bot
    print("🤖 Arrancando Telegram review…")
    proc = start_process([sys.executable, "-m", "review.telegram_review"], name="telegram_review")

    lock["telegram_review_pid"] = proc.pid
    _save_lock(lock)

    print(f"✅ Telegram review arrancado (PID {proc.pid}).")
    return proc


def main():
    try:
        ensure_telegram_bot()

        print("\n✅ Servicios lanzados.")
        print("Pulsa Ctrl+C en esta ventana para pararlos.\n")

        while True:
            time.sleep(60)

    except KeyboardInterrupt:
        print("\n⏹ Deteniendo servicios (solo lock)…")
        # Nota: como los procesos están en otra consola, no los “matamos” aquí.
        # Si quieres, podemos implementar stop real leyendo el lock y haciendo taskkill.
        print("Hecho.")


def start_services():
    """
    Lanza run_services.py como supervisor.
    Importante: NO redirigir stdout/stderr a PIPE sin leerlos (puede bloquear).
    """
    cmd = [sys.executable, "run_services.py"]
    proc = subprocess.Popen(cmd, cwd=str(BASE_DIR))
    print(f"Servicios iniciados (PID {proc.pid})")
    return proc


if __name__ == "__main__":
    main()
