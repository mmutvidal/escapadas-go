# instagram/ig_client.py

import os
import time
import requests
from typing import Optional

from config.settings import IG_USER_ID,PAGE_TOKEN,GRAPH_BASE_URL

class InstagramClient:
    def __init__(self, ig_user_id: Optional[str] = None, page_token: Optional[str] = None):
        self.ig_user_id = ig_user_id or IG_USER_ID
        self.page_token = page_token or PAGE_TOKEN

        if not self.ig_user_id or not self.page_token:
            raise ValueError("Faltan IG_USER_ID o PAGE_TOKEN en variables de entorno.")

    # ---------- 1) Crear contenedor de Reel ----------

    def create_reel_container(self, video_url: str, caption: str) -> str:
        """
        Crea un 'media container' para un Reel de IG a partir de una video_url.
        Devuelve el 'creation_id'.
        """
        endpoint = f"{GRAPH_BASE_URL}/{self.ig_user_id}/media"

        payload = {
            "media_type": "REELS",
            "video_url": video_url,
            "caption": caption,
            "access_token": self.page_token,
            # opcional:
            # "share_to_feed": "true",  # para que salga también en el feed
        }

        resp = requests.post(endpoint, data=payload, timeout=30)
        try:
            resp.raise_for_status()
        except Exception as e:
            print("❌ Error al crear contenedor de Reel:", resp.text)
            raise

        data = resp.json()
        creation_id = data.get("id")
        print(f"✅ Contenedor creado. creation_id={creation_id}")
        return creation_id

    # ---------- 2) Polling hasta que el contenedor esté listo ----------

    def wait_until_ready(self, creation_id: str, timeout_sec: int = 300, poll_interval: int = 5) -> bool:
        """
        Hace polling hasta que el media container pasa a 'FINISHED' o falle.
        Devuelve True si está listo, False si no.
        """
        endpoint = f"{GRAPH_BASE_URL}/{creation_id}"
        params = {
            "fields": "status_code,status",
            "access_token": self.page_token,
        }

        start = time.time()
        while True:
            resp = requests.get(endpoint, params=params, timeout=15)
            if resp.status_code != 200:
                print("⚠️ Error al consultar estado del contenedor:", resp.text)
                time.sleep(poll_interval)
                continue

            data = resp.json()
            status_code = data.get("status_code")
            status = data.get("status")

            print(f"⏳ Estado contenedor {creation_id}: {status_code} ({status})")

            if status_code == "FINISHED":
                print("✅ Video procesado y listo para publicar.")
                return True

            if status_code in ("ERROR", "EXPIRED"):
                print("❌ Error procesando el vídeo:", data)
                return False

            if (time.time() - start) > timeout_sec:
                print("⏰ Timeout esperando a que el vídeo esté listo.")
                return False

            time.sleep(poll_interval)

    # ---------- 3) Publicar el Reel ----------

    def publish_reel(self, creation_id: str) -> str:
        """
        Publica el Reel ya creado (creation_id) en el perfil de Instagram.
        Devuelve el ID del Reel publicado.
        """
        endpoint = f"{GRAPH_BASE_URL}/{self.ig_user_id}/media_publish"
        payload = {
            "creation_id": creation_id,
            "access_token": self.page_token,
        }

        resp = requests.post(endpoint, data=payload, timeout=30)
        try:
            resp.raise_for_status()
        except Exception as e:
            print("❌ Error al publicar el Reel:", resp.text)
            raise

        data = resp.json()
        reel_id = data.get("id")
        print(f"🎬 Reel publicado. id={reel_id}")
        return reel_id

    # ---------- 4) Obtener permalink (opcional, para logs / BD / compartir) ----------

    def get_media_permalink(self, media_id: str) -> Optional[str]:
        endpoint = f"{GRAPH_BASE_URL}/{media_id}"
        params = {
            "fields": "permalink",
            "access_token": self.page_token,
        }
        resp = requests.get(endpoint, params=params, timeout=15)
        if resp.status_code != 200:
            print("⚠️ Error obteniendo permalink:", resp.text)
            return None
        return resp.json().get("permalink")
