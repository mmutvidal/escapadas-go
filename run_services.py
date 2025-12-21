import subprocess
import sys
import os
import time
import signal

BASE_DIR = r"C:\Users\Macia\Desktop\Jupyter Notebooks\EscapadasMallorca"


import json

LOCK_PATH = os.path.join(BASE_DIR, "services.lock.json")

def _pid_is_running(pid: int) -> bool:
    if pid <= 0:
        return False
    try:
        # Windows: tasklist devuelve 0 si existe
        out = subprocess.run(
            ["tasklist", "/FI", f"PID eq {pid}"],
            capture_output=True, text=True
        ).stdout
        return str(pid) in out
    except Exception:
        return False

def _read_lock():
    try:
        with open(LOCK_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None

def _write_lock(pid: int):
    with open(LOCK_PATH, "w", encoding="utf-8") as f:
        json.dump({"pid": pid}, f)

def _clear_lock():
    try:
        os.remove(LOCK_PATH)
    except FileNotFoundError:
        pass




def start_process(cmd):
    """
    Lanza un proceso en BASE_DIR.
    En Windows usamos CREATE_NEW_CONSOLE para que cada uno tenga su ventana.
    """
    creationflags = 0
    if os.name == "nt":  # Windows
        creationflags = subprocess.CREATE_NEW_CONSOLE

    print("Lanzando:", " ".join(cmd))
    return subprocess.Popen(
        cmd,
        cwd=BASE_DIR,
        creationflags=creationflags,
    )

def main():
    procs = []

    try:
        # 1) Bot de Telegram
        procs.append(start_process([sys.executable, "-m", "review.telegram_review"]))

        # # 2) Servidor HTTP para los vídeos (puerto 8000)
        # procs.append(start_process([sys.executable, "-m", "http.server", "8000"]))

        # # 3) Ngrok
        # # (asegúrate de que 'ngrok' está en el PATH o pon la ruta completa)
        # procs.append(start_process(["ngrok", "http", "8000"]))

        print("\n✅ Servicios lanzados.")
        print("Pulsa Ctrl+C en esta ventana para pararlos.\n")

        # Mantener el script vivo mientras los hijos corren
        while True:
            time.sleep(60)

    except KeyboardInterrupt:
        print("\n⏹ Deteniendo servicios...")
        _clear_lock()
        for p in procs:
            try:
                p.terminate()
            except Exception:
                pass
        for p in procs:
            try:
                p.wait(timeout=10)
            except Exception:
                pass
        print("Todos los procesos detenidos.")


def start_services():
    lock = _read_lock()
    if lock and _pid_is_running(int(lock.get("pid", 0))):
        print(f"Servicios ya estaban iniciados (PID {lock['pid']}).")
        return None  # o devolver el pid

    cmd = [sys.executable, "run_services.py"]
    proc = subprocess.Popen(
        cmd,
        cwd=BASE_DIR,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )
    _write_lock(proc.pid)
    print(f"Servicios iniciados (PID {proc.pid})")
    return proc


def stop_services(proc):
    print(f"Deteniendo servicios (PID {proc.pid})...")

    # En Windows, Popen.terminate() envía una señal de terminación compatible
    proc.terminate()
    _clear_lock()

    try:
        proc.wait(timeout=10)
        print("Servicios detenidos correctamente.")
    except subprocess.TimeoutExpired:
        print("Forzando cierre...")
        proc.kill()


if __name__ == "__main__":
    main()
