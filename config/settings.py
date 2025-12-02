# config/settings.py
from pathlib import Path
import os

from dotenv import load_dotenv

# Ruta base del proyecto
BASE_DIR = Path(__file__).resolve().parent.parent

# Cargar .env de la raíz
load_dotenv(BASE_DIR / ".env")

# --- Claves de API ---
KIWI_API_KEY = os.getenv("KIWI_API_KEY")
KIWI_API_BASE = os.getenv("KIWI_API_BASE")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
BOT_TOKEN = os.getenv("BOT_TOKEN")
REVIEW_CHAT_ID = os.getenv("REVIEW_CHAT_ID")


# --- AWS / S3 ---
AWS_ACCESS_KEY_ID = os.getenv("AWS_ACCESS_KEY_ID")
AWS_SECRET_ACCESS_KEY = os.getenv("AWS_SECRET_ACCESS_KEY")
AWS_REGION = os.getenv("AWS_REGION")
S3_BUCKET = os.getenv("S3_BUCKET")

# --- Afiliados ---
TRAVELPAYOUTS_MARKER = os.getenv("TRAVELPAYOUTS_MARKER")
TRAVELPAYOUTS_KIWI_PROMO_ID = os.getenv("TRAVELPAYOUTS_KIWI_PROMO_ID")
TRAVELPAYOUTS_KIWI_BASE = os.getenv("TRAVELPAYOUTS_KIWI_BASE")
SKYSCANNER_BASE = os.getenv("SKYSCANNER_BASE")
SKYSCANNER_ASSOCIATE_ID = os.getenv("SKYSCANNER_ASSOCIATE_ID")
SKYSCANNER_MARKET = os.getenv("SKYSCANNER_MARKET", "ES")
SKYSCANNER_LOCALE = os.getenv("SKYSCANNER_LOCALE", "es-ES")
SKYSCANNER_CURRENCY = os.getenv("SKYSCANNER_CURRENCY", "EUR")

# --- Proyecto / branding ---
DEFAULT_MARKET = os.getenv("DEFAULT_MARKET", "PMI")
DEFAULT_BRAND_HANDLE = os.getenv("DEFAULT_BRAND_HANDLE", "escapadasgo")
DEFAULT_ORIGIN_CITY = os.getenv("DEFAULT_ORIGIN_CITY", "Palma de Mallorca")

# --- Instagram ---
IG_USER_ID = os.getenv("IG_USER_ID")
PAGE_TOKEN = os.getenv("PAGE_TOKEN")
GRAPH_BASE_URL = os.getenv("GRAPH_BASE_URL")  # o la versión que estés usando


# Donde guardas tus JSON públicos por mercado
PUBLIC_JSON_BASE_URL = os.getenv(
    "PUBLIC_JSON_BASE_URL",
    "https://escapadasgo-public.s3.eu-west-1.amazonaws.com",
)
