import random
from pathlib import Path
from typing import Optional
from PIL import Image, ImageDraw, ImageFont, ImageFilter
from datetime import datetime, date

# Detecta ruta absoluta al directorio raíz del proyecto
IMAGES_DIR = Path("media/images") 

def pick_image_for_destination(
    destination_iata: str,
    images_dir: Path = IMAGES_DIR,
) -> Optional[Path]:
    """
    Devuelve la ruta a una imagen para el aeropuerto dado.
    - Busca primero fotos que empiecen por el código IATA (MAN1.*, MAN2.*...)
    - Si no encuentra, usa una imagen Default* aleatoria.
    - Si tampoco hay defaults, devuelve None.
    """

    destination_iata = destination_iata.upper()

    # 1) Fotos específicas del aeropuerto (MAN1.jpg, MAN2.png, etc.)
    specific_images = sorted(
        img for img in images_dir.iterdir()
        if img.is_file() and img.stem.upper().startswith(destination_iata)
    )

    if specific_images:
        return random.choice(specific_images)

    # 2) Fotos por defecto (Default1.jpg, Default2.png, etc.)
    default_images = sorted(
        img for img in images_dir.iterdir()
        if img.is_file() and img.stem.upper().startswith("DEFAULT")
    )

    if default_images:
        return random.choice(default_images)

    # 3) No hay imágenes disponibles
    return None


# scripts/create_reel_v4.py
from pathlib import Path
from typing import Tuple, Optional
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter
from moviepy.video.io.ImageSequenceClip import ImageSequenceClip

WIDTH, HEIGHT = 1080, 1920
FPS = 30

# ---------- CONFIG VISUAL ----------
COLORS = {
    "white": (255, 255, 255, 255),
    "dates": (234, 234, 234, 255),
    "shadow_dark": (0, 0, 0, 190),
    "card": (11, 18, 32, 210),  # navy de marca para la banda inferior
}

# Degradado más marcado para que el fondo no “compita”
GRADIENT_TOP_OPACITY = 0.20   # antes 0.00
GRADIENT_BOT_OPACITY = 0.70   # antes 0.40

LOGO_GLOW_BLUR = 4
LOGO_GLOW_ALPHA = 140
LOGO_WIDTH_PX = int(WIDTH * 0.30)           # antes 240 → logo más protagonista
LOGO_POS = "top-right"
LOGO_MARGIN = 30
SAFE_AREA = 20

# Tipografías (preferencia Poppins/Nunito; si no, Segoe/Arial)
FONT_CANDIDATES = [
    # Copia tu TTF a la carpeta y pon el nombre aquí si quieres 100% Poppins
    "Poppins-SemiBold.ttf", "Poppins-Regular.ttf",
    "Nunito-Bold.ttf", "Nunito-Regular.ttf",
    r"C:\Windows\Fonts\seguisym.ttf",      # Windows: símbolos
    r"C:\Windows\Fonts\segoeui.ttf",       # Windows: Segoe UI
    r"C:\Windows\Fonts\arial.ttf",         # Windows: Arial
    "DejaVuSans.ttf", "DejaVuSans-Bold.ttf",
]

# ---------- UTILIDADES ----------
def _draw_text_band(frame: Image.Image) -> tuple[Image.Image, tuple[int, int, int, int]]:
    """
    Dibuja una banda semitransparente donde irán precio / ruta / fechas / marca.
    Devuelve el frame modificado y el bbox (left, top, right, bottom) de la banda.
    """
    # Banda algo más baja y menos alta para que se vea más elegante
    band_height = int(HEIGHT * 0.28)
    margin_side = int(WIDTH * 0.06)
    margin_bottom = int(HEIGHT * 0.06)

    left = margin_side
    right = WIDTH - margin_side
    bottom = HEIGHT - margin_bottom
    top = bottom - band_height

    overlay = Image.new("RGBA", frame.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)

    band_color = COLORS["card"]           # azul navy de marca
    radius = int(HEIGHT * 0.03)          # esquinas redondeadas relativas al alto
    draw.rounded_rectangle([left, top, right, bottom], radius, fill=band_color)

    frame = Image.alpha_composite(frame, overlay)
    return frame, (left, top, right, bottom)


def _find_font_path() -> Optional[str]:
    for p in FONT_CANDIDATES:
        try:
            if Path(p).exists():
                return str(p)
        except Exception:
            pass
    return None

_FONT_PATH = _find_font_path()

def _font(size: int) -> ImageFont.FreeTypeFont:
    if _FONT_PATH:
        try:
            return ImageFont.truetype(_FONT_PATH, size)
        except Exception:
            pass
    return ImageFont.load_default()

def _fit_cover(img: Image.Image, target_w=WIDTH, target_h=HEIGHT) -> Image.Image:
    # Escala y recorta centrado para llenar 1080x1920 conservando proporción
    w, h = img.size
    r_img = w / h
    r_tgt = target_w / target_h
    if r_img > r_tgt:
        # demasiado ancha -> encajar por alto
        new_h = target_h
        new_w = int(round(w * (new_h / h)))
    else:
        # demasiado alta -> encajar por ancho
        new_w = target_w
        new_h = int(round(h * (new_w / w)))
    im = img.resize((new_w, new_h), Image.LANCZOS)
    left = max(0, (new_w - target_w) // 2)
    top = max(0, (new_h - target_h) // 2)
    return im.crop((left, top, left + target_w, top + target_h))

def _gradient_overlay(h=HEIGHT, w=WIDTH,
                      top_op=GRADIENT_TOP_OPACITY, bot_op=GRADIENT_BOT_OPACITY,
                      tint=(0, 0, 0)) -> Image.Image:
    grad = np.zeros((h, w, 4), dtype=np.uint8)
    for y in range(h):
        t = y / (h - 1)
        alpha = int(255 * (top_op + (bot_op - top_op) * t))
        grad[y, :, 0] = tint[0]
        grad[y, :, 1] = tint[1]
        grad[y, :, 2] = tint[2]
        grad[y, :, 3] = alpha
    return Image.fromarray(grad, "RGBA")

def _draw_text_center(frame: Image.Image, text: str, center_y: int,
                      font_size: int, color=COLORS["white"],
                      shadow=COLORS["shadow_dark"], shadow_offset=(0, 2)) -> None:
    draw = ImageDraw.Draw(frame)
    f = _font(font_size)
    bbox = draw.textbbox((0, 0), text, font=f)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    x = (WIDTH - tw) // 2
    y = int(center_y - th // 2)

    # Sombra suave
    if shadow:
        sx, sy = shadow_offset
        draw.text((x + sx, y + sy), text, font=f, fill=shadow)
    draw.text((x, y), text, font=f, fill=color)

def _place_logo(logo_path: str, width_px=LOGO_WIDTH_PX,
                pos=LOGO_POS, margin=LOGO_MARGIN, safe=SAFE_AREA) -> Tuple[Image.Image, Tuple[int, int]]:
    logo = Image.open(logo_path).convert("RGBA")
    w0, h0 = logo.size
    scale = width_px / max(1, w0)
    logo = logo.resize((int(w0 * scale), int(h0 * scale)), Image.LANCZOS)
    lx, ly = logo.size

    if pos == "top-left":
        xy = (margin + safe, margin)
    elif pos == "bottom-left":
        xy = (margin + safe, HEIGHT - ly - margin)
    elif pos == "bottom-right":
        xy = (WIDTH - lx - margin - safe, HEIGHT - ly - margin)
    else:
        xy = (WIDTH - lx - margin - safe, margin)
    return logo, xy

def _logo_with_glow(logo_rgba: Image.Image, glow_alpha=LOGO_GLOW_ALPHA, blur=LOGO_GLOW_BLUR) -> Image.Image:
    # Crea halo suave alrededor del logo (blanco)
    w, h = logo_rgba.size
    glow = Image.new("RGBA", (w, h), (255, 255, 255, 0))
    mask = logo_rgba.split()[-1].filter(ImageFilter.GaussianBlur(2))
    glow.putalpha(mask)
    glow = glow.filter(ImageFilter.GaussianBlur(blur))
    # ajusta opacidad del glow
    arr = np.array(glow, dtype=np.uint8)
    arr[:, :, 3] = np.minimum(arr[:, :, 3], glow_alpha).astype(np.uint8)
    glow = Image.fromarray(arr, "RGBA")

    base = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    base = Image.alpha_composite(base, glow)
    base = Image.alpha_composite(base, logo_rgba)
    return base


def _render_frame(
    base_img: Image.Image,
    title: str,
    price: str,
    dates: str,
    logo_path: Optional[str],
    brand_line: Optional[str] = None,
) -> Image.Image:
    frame = base_img.convert("RGBA")

    # 1) Degradado para rebajar la foto
    grad = _gradient_overlay()
    frame = Image.alpha_composite(frame, grad)

    # 2) Banda inferior
    frame, band_bbox = _draw_text_band(frame)
    band_left, band_top, band_right, band_bottom = band_bbox
    band_h = band_bottom - band_top

    draw = ImageDraw.Draw(frame)

    # --- Fuentes basadas en la altura del vídeo para mantener proporciones ---
    route_fs = int(HEIGHT * 0.045 )   # ruta (más grande)
    dates_fs = int(HEIGHT * 0.032 )   # fechas
    price_fs = int(HEIGHT * 0.035 )   # precio
    brand_fs = int(HEIGHT * 0.017) if brand_line else None  # micro-línea

    f_route = _font(route_fs)
    f_dates = _font(dates_fs)
    f_price = _font(price_fs)
    f_brand = _font(brand_fs) if brand_line else None

    def text_size(text: str, font: ImageFont.FreeTypeFont) -> tuple[int, int]:
        bbox = draw.textbbox((0, 0), text, font=font)
        w = bbox[2] - bbox[0]
        h = bbox[3] - bbox[1]
        return w, h

    w_route, h_route = text_size(title, f_route)
    w_dates, h_dates = text_size(dates, f_dates)
    w_price, h_price = text_size(price, f_price)

    if brand_line:
        w_brand, h_brand = text_size(brand_line, f_brand)
    else:
        w_brand = h_brand = 0

    # --- Layout vertical dentro de la banda ---
    top_margin = band_h * 0.15
    bottom_margin = band_h * 0.13

    if brand_line:
        text_total_h = h_route + h_dates + h_price + h_brand
        gaps = 3  # entre ruta/fechas, fechas/precio, precio/brand
    else:
        text_total_h = h_route + h_dates + h_price
        gaps = 2  # solo entre ruta/fechas y fechas/precio

    available_h = band_h - top_margin - bottom_margin
    gap = max(10, (available_h - text_total_h) / max(1, gaps))

    # Posiciones top de cada bloque
    y_route_top = band_top + top_margin
    y_dates_top = y_route_top + h_route + gap
    y_price_top = y_dates_top + h_dates + gap
    if brand_line:
        y_brand_top = y_price_top + h_price + gap

    # Helper para centrar en X usando _draw_text_center (que pide center_y)
    def draw_centered_line(text: str, font: ImageFont.FreeTypeFont, top_y: float, color) -> None:
        center_y = top_y + (text_size(text, font)[1] / 2)
        _draw_text_center(
            frame,
            text,
            int(center_y),
            font_size=font.size,
            color=color,
        )

    # 3) Dibujamos las líneas principales
    draw_centered_line(title, f_route, y_route_top, COLORS["white"])
    draw_centered_line(dates, f_dates, y_dates_top, COLORS["dates"])
    draw_centered_line(price, f_price, y_price_top, COLORS["white"])

    # 4) Micro-línea de marca (si la hay)
    if brand_line and f_brand:
        draw_centered_line(brand_line, f_brand, y_brand_top, COLORS["dates"])

    # 5) Logo en esquina superior
    if logo_path and Path(logo_path).exists():
        logo, (x, y) = _place_logo(logo_path)
        logo = _logo_with_glow(logo)
        frame.alpha_composite(logo, (x, y))

    return frame


# ---------- API PRINCIPAL ----------
def create_reel_v4(
    bg_image_path: str,
    out_mp4_path: str,
    title: str,
    price: str,
    dates: str,
    duration: float = 7.0,
    logo_path: Optional[str] = None,
    fps: int = FPS,
    brand_line: Optional[str] = None,
):
    """Genera un reel 1080x1920 con overlay, tipografía blanca y logo con halo."""
    base = Image.open(Path(bg_image_path)).convert("RGB")
    base = _fit_cover(base)

    frames = int(round(duration * fps))
    seq = []
    for i in range(frames):
        # zoom suave 7% a lo largo del clip
        t = i / max(1, frames - 1)
        s = 1.0 + 0.07 * t
        w = int(round(WIDTH * s))
        h = int(round(HEIGHT * s))
        bg = base.resize((w, h), Image.LANCZOS)
        left = max(0, (w - WIDTH) // 2)
        top = max(0, (h - HEIGHT) // 2)
        bg = bg.crop((left, top, left + WIDTH, top + HEIGHT))

        frame = _render_frame(
            bg,
            title=title,
            price=price,
            dates=dates,
            logo_path=logo_path,
            brand_line=brand_line,
        )
        seq.append(np.asarray(frame.convert("RGB")))

    clip = ImageSequenceClip(seq, fps=fps)
    clip.write_videofile(out_mp4_path, fps=fps, codec="libx264", audio=False, preset="medium", threads=4)


def render_example_png(
    bg_image_path: str,
    out_png_path: str,
    title: str,
    price: str,
    dates: str,
    logo_path: Optional[str] = None,
    brand_line: Optional[str] = None,
):
    """Exporta un PNG único 1080x1920 con el diseño final (para revisar)."""
    base = Image.open(Path(bg_image_path)).convert("RGB")
    base = _fit_cover(base)
    frame = _render_frame(
        base,
        title=title,
        price=price,
        dates=dates,
        logo_path=logo_path,
        brand_line=brand_line,
    )
    Path(out_png_path).parent.mkdir(parents=True, exist_ok=True)
    frame.convert("RGB").save(out_png_path, "PNG", optimize=True)


# ---------- HELPERS DE ALTO NIVEL PARA VUELOS ----------

from datetime import datetime
from typing import Union

# tipo flexible: puede ser tu objeto Flight o el dict serializable
FlightLike = Union[dict, object]


def _get_field(f: FlightLike, name: str, default=None):
    """
    Lee un campo tanto si 'f' es dict como si es un objeto con atributos.
    """
    if isinstance(f, dict):
        return f.get(name, default)
    return getattr(f, name, default)


def _format_dates_for_reel(start, end):
    def to_date(x):
        if x is None:
            return None
        if isinstance(x, datetime):
            return x.date()
        if isinstance(x, date):
            return x
        if isinstance(x, str):
            # admite "2025-11-28" y "2025-11-28T20:20:00.000Z"
            s = x[:10]  # "YYYY-MM-DD"
            return datetime.strptime(s, "%Y-%m-%d").date()
        return None

    d1 = to_date(start)
    d2 = to_date(end)
    if not d1 or not d2:
        return ""

    # lo que ya tengas para formatear, por ejemplo:
    # 28 NOV – 30 NOV
    month_map = {1: "ENE", 2: "FEB", 3: "MAR", 4: "ABR", 5: "MAY", 6: "JUN",
                 7: "JUL", 8: "AGO", 9: "SEP", 10: "OCT", 11: "NOV", 12: "DIC"}

    def fmt(d):
        return f"{d.day:02d} {month_map[d.month]}"

    return f"{fmt(d1)} – {fmt(d2)}"


def create_reel_for_flight(
    flight: FlightLike,
    out_mp4_path: str,
    logo_path: Optional[str] = None,
    duration: float = 4.0,
) -> str:
    """
    Capa de alto nivel: a partir de un vuelo (Flight o dict),
    construye title/price/dates, escoge imagen y llama a create_reel_v4.

    Devuelve la ruta de salida (out_mp4_path).
    """
    origin = _get_field(flight, "origin", "PMI")
    destination = _get_field(flight, "destination", "???")
    price_val = _get_field(flight, "price") or _get_field(flight, "price_eur")
    start_date = _get_field(flight, "start_date")
    end_date = _get_field(flight, "end_date")

    # Intentamos sacar la ciudad de origen si existe
    origin_city = _get_field(flight, "origin_city", "Mallorca")

    # Título: "PMI ✈ EIN"
    title = f"{origin} ✈ {destination}"

    # Precio: "98 € i/v"
    if price_val is not None:
        price = f"{int(round(float(price_val)))} € i/v"
    else:
        price = ""

    # Fechas: "29 NOV – 1 DIC"
    dates = _format_dates_for_reel(start_date, end_date)

    # Micro-línea de marca
    # brand_handle = "escapadasgo"
    # brand_line = f"@{brand_handle} · salidas desde {origin_city}"
    
    brand_handle = "escapadasgo_mallorca"
    brand_line = f"@{brand_handle}"
    
    # Imagen de fondo
    bg_path = pick_image_for_destination(destination)
    if not bg_path:
        bg_path = pick_image_for_destination("DEFAULT")

    create_reel_v4(
        bg_image_path=str(bg_path),
        out_mp4_path=out_mp4_path,
        title=title,
        price=price,
        dates=dates,
        duration=duration,
        logo_path=logo_path,
        brand_line=brand_line,
    )

    return out_mp4_path
