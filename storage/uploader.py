# storage/uploader.py

import os
import time
import threading
import subprocess
from pathlib import Path

from pyngrok import ngrok

# Ajusta si quieres otro puerto
SERVER_PORT = 8000

# BASE_DIR = raíz del proyecto (donde está main.py, media/, etc.)
BASE_DIR = Path(__file__).resolve().parent.parent

# Estado global sencillo para no abrir 20 túneles
_server_started = False
_public_base_url = None


def _start_local_http_server():
    """
    Lanza `python -m http.server` en un hilo en segundo plano,
    sirviendo el directorio raíz del proyecto.
    """
    global _server_started
    if _server_started:
        return

    def run_server():
        # Servimos desde la raíz del proyecto
        os.chdir(BASE_DIR)
        # Esto bloquearía el hilo, pero lo lanzamos en un hilo daemon
        subprocess.run(
            ["python", "-m", "http.server", str(SERVER_PORT)],
            check=False,
        )

    t = threading.Thread(target=run_server, daemon=True)
    t.start()

    # Darle un pelín de tiempo a que arranque
    time.sleep(2)
    _server_started = True


def _ensure_ngrok_tunnel() -> str:
    """
    Crea un túnel ngrok al puerto local y devuelve la URL pública base,
    por ejemplo: https://xxxxx.ngrok-free.app
    """
    global _public_base_url
    if _public_base_url:
        return _public_base_url

    # Crea túnel HTTP -> nos dará URL http y https
    tunnel = ngrok.connect(SERVER_PORT, "http")
    public_url = tunnel.public_url

    # Forzamos https por seguridad / Graph
    if public_url.startswith("http://"):
        public_url = public_url.replace("http://", "https://", 1)

    _public_base_url = public_url
    print(f"🌍 Ngrok tunnel activo: {_public_base_url}")
    return _public_base_url


def get_public_url(local_video_path: Path) -> str:
    """
    Recibe la ruta local a un vídeo (p.ej. media/videos/reel_2025-11-17.mp4)
    y devuelve una URL pública accesible por Instagram:
      https://xxxxx.ngrok-free.app/media/videos/reel_2025-11-17.mp4
    """

    # Aseguramos que la ruta es absoluta y existe
    local_video_path = local_video_path.resolve()
    if not local_video_path.exists():
        raise FileNotFoundError(f"Vídeo no encontrado: {local_video_path}")

    # 1) Arrancar servidor HTTP local (si no lo está ya)
    _start_local_http_server()

    # 2) Obtener URL base de ngrok
    base_url = _ensure_ngrok_tunnel()

    # 3) Calcular ruta relativa desde BASE_DIR para construir la URL
    try:
        rel_path = local_video_path.relative_to(BASE_DIR)
    except ValueError:
        # Si por lo que sea el vídeo está fuera del proyecto
        raise ValueError(
            f"El vídeo {local_video_path} no está dentro de {BASE_DIR}"
        )

    # Usar formato con / (para URL)
    rel_url_path = rel_path.as_posix()

    public_video_url = f"{base_url}/{rel_url_path}"
    print(f"🔗 URL pública del vídeo: {public_video_url}")
    return public_video_url
