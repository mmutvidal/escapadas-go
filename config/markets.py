# config/markets.py
from dataclasses import dataclass
from typing import Optional
from config.settings import PMI_IG_USER_ID, PMI_PAGE_TOKEN, ES_IG_USER_ID, ES_PAGE_TOKEN



@dataclass(frozen=True)
class MarketConfig:
    code: str                # "PMI", "BCN", ...
    origin_iata: str         # "PMI"
    ig_handle: str           # "@escapadasgo_mallorca"
    s3_reels_prefix: str     # "pmi/"
    web_key_prefix: str      # "pmi/"  (o "es/" para el general)
    logo_path: str
    video_path: str
    ig_user_id: Optional[str] = None
    page_token: Optional[str] = None
    distance_mapping_path: str | None = None  # si lo usas para scoring
    min_discount_pct: float = 40.0
    ab_ratio_new: float = 0.5


MARKETS = {
    "PMI": MarketConfig(
        code="PMI",
        origin_iata="PMI",
        ig_handle="@escapadasgo_mallorca",
        s3_reels_prefix="pmi/",
        web_key_prefix="pmi/",
        logo_path="media/images/EscapGo_circ_logo_transparent.png",
        video_path="media/videos/reel.mp4",
        distance_mapping_path="distance_mapping_pmi.xlsx",
        min_discount_pct=40.0,
        ab_ratio_new=0.5,
        ig_user_id=PMI_IG_USER_ID,
        page_token=PMI_PAGE_TOKEN,
    ),
    "BCN": MarketConfig(
        code="BCN",
        origin_iata="BCN",
        ig_handle="@escapadasgo",          # o @escapadasgo_barcelona si creas
        s3_reels_prefix="bcn/",
        web_key_prefix="es/",
        logo_path="media/images/EscapGo_circ_logo_transparent.png",
        video_path="media/videos/reel.mp4",
        min_discount_pct=40.0,
        ab_ratio_new=1,
        ig_user_id=ES_IG_USER_ID,
        page_token=ES_PAGE_TOKEN,
    ),
    "MAD": MarketConfig(
        code="MAD",
        origin_iata="MAD",
        ig_handle="@escapadasgo",
        s3_reels_prefix="mad/",
        web_key_prefix="es/",
        logo_path="media/images/EscapGo_circ_logo_transparent.png",
        video_path="media/videos/reel.mp4",
        min_discount_pct=40.0,
        ab_ratio_new=0.5,        
        ig_user_id=ES_IG_USER_ID,
        page_token=ES_PAGE_TOKEN,
    ),
    "VLC": MarketConfig(
        code="VLC",
        origin_iata="VLC",
        ig_handle="@escapadasgo",
        s3_reels_prefix="vlc/",
        web_key_prefix="es/",
        logo_path="media/images/EscapGo_circ_logo_transparent.png",
        video_path="media/videos/reel.mp4",
        min_discount_pct=40.0,
        ab_ratio_new=0.5,
        ig_user_id=ES_IG_USER_ID,
        page_token=ES_PAGE_TOKEN,
    ),
    "TFN": MarketConfig(
        code="TFN",
        origin_iata="TFN",
        ig_handle="@escapadasgo",
        s3_reels_prefix="tfn/",
        web_key_prefix="es/",
        logo_path="media/images/EscapGo_circ_logo_transparent.png",
        video_path="media/videos/reel.mp4",
        min_discount_pct=40.0,
        ab_ratio_new=0.5,
        ig_user_id=ES_IG_USER_ID,
        page_token=ES_PAGE_TOKEN,
    ),
    "ALC": MarketConfig(
        code="ALC",
        origin_iata="ALC",
        ig_handle="@escapadasgo",
        s3_reels_prefix="alc/",
        web_key_prefix="es/",
        logo_path="media/images/EscapGo_circ_logo_transparent.png",
        video_path="media/videos/reel.mp4",
        min_discount_pct=40.0,
        ab_ratio_new=0.5,
        ig_user_id=ES_IG_USER_ID,
        page_token=ES_PAGE_TOKEN,
    ),
    "AGP": MarketConfig(
        code="AGP",
        origin_iata="AGP",
        ig_handle="@escapadasgo",
        s3_reels_prefix="agp/",
        web_key_prefix="es/",
        logo_path="media/images/EscapGo_circ_logo_transparent.png",
        video_path="media/videos/reel.mp4",
        min_discount_pct=40.0,
        ab_ratio_new=0.5,
        ig_user_id=ES_IG_USER_ID,
        page_token=ES_PAGE_TOKEN,
    ),
}
