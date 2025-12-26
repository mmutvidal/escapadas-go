# media/reel_ab.py
from __future__ import annotations

import hashlib
from typing import Optional, Literal, Any

import media.video_generator as vg_new
import media.old_video_generator as vg_old


Variant = Literal["auto", "new", "old"]


def _get_field(obj: Any, name: str, default=None):
    # Soporta objetos Flight o dicts
    if isinstance(obj, dict):
        return obj.get(name, default)
    return getattr(obj, name, default)


def choose_variant_deterministic(
    flight: Any,
    ratio_new: float = 0.5,
    salt: str = "escapadasgo-v1",
    key_mode: Literal["route_dates", "route_only"] = "route_dates",
) -> Literal["new", "old"]:
    """
    Decide A/B de forma determinística (estable), para que el mismo vuelo
    caiga siempre en el mismo bucket.

    key_mode:
      - route_dates: origen+destino+fechas (estable por vuelo concreto)
      - route_only:  origen+destino (estable por ruta; útil si quieres mezclar fechas)
    """
    origin = str(_get_field(flight, "origin", ""))
    dest = str(_get_field(flight, "destination", ""))
    start = str(_get_field(flight, "start_date", ""))[:10]
    end = str(_get_field(flight, "end_date", ""))[:10]

    if key_mode == "route_only":
        key = f"{origin}|{dest}"
    else:
        key = f"{origin}|{dest}|{start}|{end}"

    h = hashlib.md5((salt + "|" + key).encode("utf-8")).hexdigest()
    bucket = int(h[:8], 16) / 0xFFFFFFFF  # 0..1
    return "new" if bucket < ratio_new else "old"


def create_reel_for_flight_ab(
    flight: Any,
    out_mp4_path: str,
    logo_path: Optional[str],
    brand_line: str = "@escapadasgo_mallorca",
    duration: float = 6.0,
    s3_bucket: Optional[str] = None,
    s3_prefix: str = "reels/",
    s3_public: bool = True,
    # NUEVO (solo lo usa la variante "new")
    hook_text: Optional[str] = None,
    hook_mode: str = "band",
    # A/B vídeo (new vs old)
    variant: Variant = "auto",
    ratio_new: float = 0.5,
    key_mode: Literal["route_dates", "route_only"] = "route_dates",
    salt: str = "escapadasgo-v1",
    # ✅ NUEVO: A/B pill de origen (on/off)
    origin_pill_ab_ratio: float = 0.5,
    force_origin_pill: Optional[bool] = None,
) -> tuple[str, str, str]:
    """
    Devuelve (result_path_or_url, chosen_variant, origin_pill_variant)

    origin_pill_variant:
      - "origin_pill_on" / "origin_pill_off"
    """
    if variant == "auto":
        variant = choose_variant_deterministic(
            flight, ratio_new=ratio_new, salt=salt, key_mode=key_mode
        )

    if variant == "new":
        res, origin_pill_variant = vg_new.create_reel_for_flight(
            flight,
            out_mp4_path=out_mp4_path,
            logo_path=logo_path,
            brand_line=brand_line,
            duration=duration,
            s3_bucket=s3_bucket,
            s3_prefix=s3_prefix,
            s3_public=s3_public,
            hook_text=hook_text,
            hook_mode=hook_mode,
            # ✅ Pill A/B
            origin_pill_ab_ratio=origin_pill_ab_ratio,
            force_origin_pill=force_origin_pill,
            return_origin_pill_variant=True,
        )
        return res, "new", origin_pill_variant

    # "old"
    res = vg_old.create_reel_for_flight(
        flight,
        out_mp4_path=out_mp4_path,
        logo_path=logo_path,
        brand_line=brand_line,
        duration=duration,
        s3_bucket=s3_bucket,
        s3_prefix=s3_prefix,
        s3_public=s3_public,
    )
    return res, "old", "origin_pill_off"
