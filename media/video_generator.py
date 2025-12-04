import random
from pathlib import Path
from typing import Optional
from datetime import datetime, date
import math

from PIL import Image, ImageDraw, ImageFont, ImageFilter
# from moviepy.editor import ImageClip

import numpy as np
from moviepy.editor import ImageClip, VideoFileClip, CompositeVideoClip, vfx
from moviepy.video.io.ImageSequenceClip import ImageSequenceClip

# --- Parche compatibilidad Pillow 10+ ---
# MoviePy todavía usa Image.ANTIALIAS; en Pillow 10 se renombró a LANCZOS.
if not hasattr(Image, "ANTIALIAS"):
    Image.ANTIALIAS = Image.LANCZOS

FPS = 30


# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

IMAGES_DIR = Path("media/images")

FONT_DEFAULT_PATH = "media/fonts/Montserrat-Regular.ttf"   # o la que uses
FONT_ROUTE_PATH   = "media/fonts/DejaVuSans.ttf"           # nueva, con ✈
# ---------------------------------------------------------------------------
# Picking background images
# ---------------------------------------------------------------------------

def pick_image_for_destination(
    destination_iata: str,
    images_dir: Path = IMAGES_DIR,
) -> Optional[Path]:
    """
    Devuelve la ruta a una imagen para el aeropuerto dado.
    - Busca primero fotos que empiecen por el código IATA (VIE1.*, VIE2.*...)
    - Si no hay, intenta DEFAULT*
    - Si tampoco, devuelve None
    """
    images_dir = Path(images_dir)

    if not images_dir.exists():
        return None

    # 1) Intentar con el código IATA
    candidates = sorted(
        list(images_dir.glob(f"{destination_iata.upper()}*.*"))
    )

    # 2) Fallback a DEFAULT
    if not candidates:
        candidates = sorted(list(images_dir.glob("DEFAULT*.*")))

    if not candidates:
        return None

    return random.choice(candidates)


from collections.abc import Mapping

def _fget(obj, key, default=None):
    """
    Lee un campo de 'obj' tanto si es dataclass/objeto como si es dict.
    """
    if isinstance(obj, Mapping):
        return obj.get(key, default)
    return getattr(obj, key, default)

# ---------------------------------------------------------------------------
# Utilidad fechas
# ---------------------------------------------------------------------------

MONTHS_ES = [
    "ENE", "FEB", "MAR", "ABR", "MAY", "JUN",
    "JUL", "AGO", "SEP", "OCT", "NOV", "DIC",
]

def _parse_date_ymd(s: str) -> datetime:
    return datetime.strptime(s[:10], "%Y-%m-%d")

def format_dates_dd_mmm(start_date: str, end_date: str) -> str:
    """
    Recibe '2025-12-12' y '2025-12-14' y devuelve '12 DIC – 14 DIC'
    """
    d1 = _parse_date_ymd(start_date)
    d2 = _parse_date_ymd(end_date)

    def f(d: datetime) -> str:
        return f"{d.day:02d} {MONTHS_ES[d.month - 1]}"

    return f"{f(d1)} – {f(d2)}"

# ---------------------------------------------------------------------------
# Config visual
# ---------------------------------------------------------------------------

WIDTH, HEIGHT = 1080, 1920

COLORS = {
    "white": (255, 255, 255, 255),
    "dates": (230, 232, 236, 255),
    "price": (255, 209, 117, 255),
    "card":  (11, 18, 32, 220),
    "card_border": (255, 255, 255, 35),
    "card_glow": (0, 0, 0, 110),
    "brand": (210, 210, 215, 255),

    # NUEVO
    "badge_bg": (255, 209, 117, 235),      # fondo descuento
    "badge_text": (15, 20, 30, 255),
    "pill_bg": (29, 44, 76, 240),          # fondo categoría
    "pill_text": (230, 232, 236, 255),

        # nuevos
    "accent": (249, 196, 88, 255),        # para el badge de descuento
    "pill_text_dark": (15, 23, 42, 255),  # texto oscuro sobre el badge amarillo
    "pill_border_soft": (255, 255, 255, 120),
}

GRADIENT_TOP_OPACITY = 0.15
GRADIENT_BOT_OPACITY = 0.65

LOGO_WIDTH_REL = 0.26         # porcentaje del ancho del vídeo
LOGO_MARGIN = 40
SAFE_AREA = 40

CARD_WIDTH_REL = 0.86
CARD_HEIGHT_REL = 0.30
CARD_RADIUS = 90

LOGO_GLOW_BLUR = 8
LOGO_GLOW_ALPHA = 120

# ---------------------------------------------------------------------------
# Fuentes
# ---------------------------------------------------------------------------

FONT_CANDIDATES = [
    # Si añades aquí Poppins/Nunito locales, tendrán prioridad
    "Poppins-SemiBold.ttf",
    "Poppins-Regular.ttf",
    "Nunito-Bold.ttf",
    "Nunito-Regular.ttf",
    # Windows
    r"C:\\Windows\\Fonts\\segoeui.ttf",
    r"C:\\Windows\\Fonts\\seguisym.ttf",
    r"C:\\Windows\\Fonts\\arial.ttf",
    # Linux / Mac típicas
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/Library/Fonts/Arial.ttf",
]

def _find_font_path() -> Optional[str]:
    for p in FONT_CANDIDATES:
        try:
            if Path(p).exists():
                return str(p)
        except Exception:
            continue
    return None

_FONT_PATH = _find_font_path()


def _font(size: int, kind: str = "default") -> ImageFont.FreeTypeFont:
    """
    kind:
      - "default": para fechas, precio, etc.
      - "route": para el texto PMI ✈ VIE (usa una fuente que soporte ✈)
    """
    if kind == "route":
        path = FONT_ROUTE_PATH
    else:
        path = FONT_DEFAULT_PATH

    return ImageFont.truetype(path, size)

# ---------------------------------------------------------------------------
# Helpers de dibujo
# ---------------------------------------------------------------------------

def _short_category_label(cat) -> Optional[str]:
    """
    Recibe algo tipo:
      - {"code": "finde_perfecto", "label": "🔥 Ultra Chollo"}
      - "finde_perfecto"
    y devuelve un texto corto para el badge.
    """
    if isinstance(cat, dict):
        code = cat.get("code")
    else:
        code = cat

    if not code:
        return None

    mapping = {
        "finde_perfecto": "Finde perfecto",
        "ultra_chollo": "Ultra chollo",
        "chollo": "Chollo",
        "romantica": "Escapada romántica",
        "cultural": "Escapada cultural",
        "gastronomica": "Escapada gastro",
        "escapada_perfecta": "Escapada perfecta",
        "oferta": "Oferta",
    }

    label = mapping.get(code)
    if not label:
        # fallback: usar el propio código formateado
        label = str(code).replace("_", " ").title()

    return label.upper()


def _draw_pill(
    draw: ImageDraw.ImageDraw,
    text: str,
    font: ImageFont.FreeTypeFont,
    center_x: float,
    center_y: float,
    padding_x: float,
    padding_y: float,
    bg_color,
    text_color,
    border_color=None,
):
    # Medimos texto
    bbox = draw.textbbox((0, 0), text, font=font)
    text_w = bbox[2] - bbox[0]
    text_h = bbox[3] - bbox[1]

    pill_w = text_w + 2 * padding_x
    pill_h = text_h + 2 * padding_y

    x0 = center_x - pill_w / 2
    y0 = center_y - pill_h / 2
    x1 = center_x + pill_w / 2
    y1 = center_y + pill_h / 2

    radius = pill_h / 2

    draw.rounded_rectangle(
        (x0, y0, x1, y1),
        radius=radius,
        fill=bg_color,
        outline=border_color,
        width=2 if border_color else 0,
    )

    text_x = x0 + padding_x
    text_y = y0 + padding_y
    draw.text((text_x, text_y), text, font=font, fill=text_color)


def _fit_cover(img: Image.Image, target_w: int, target_h: int) -> Image.Image:
    """
    Resize estilo 'cover':
    - Mantiene proporción
    - Asegura que la imagen cubra completamente target_w x target_h
    - Recorta el exceso por los lados
    """
    src_w, src_h = img.size
    src_ratio = src_w / src_h
    target_ratio = target_w / target_h

    # Determinar si escalamos por ancho o por alto
    if src_ratio > target_ratio:
        # Imagen demasiado ancha → ajustar por altura
        new_h = target_h
        new_w = int(new_h * src_ratio)
    else:
        # Imagen demasiado alta → ajustar por anchura
        new_w = target_w
        new_h = int(new_w / src_ratio)

    # Resize con alta calidad
    img_resized = img.resize((new_w, new_h), Image.LANCZOS)

    # Recorte centrado
    x0 = (new_w - target_w) // 2
    y0 = (new_h - target_h) // 2
    x1 = x0 + target_w
    y1 = y0 + target_h

    return img_resized.crop((x0, y0, x1, y1))

def _apply_vertical_gradient(base: Image.Image) -> Image.Image:
    """
    Aplica un degradado negro de arriba (poco) a abajo (más opaco)
    para que la banda y el texto respiren.
    """
    base = base.convert("RGBA")
    w, h = base.size

    gradient = Image.new("L", (1, h))
    for y in range(h):
        t = y / (h - 1)
        alpha_float = (
            GRADIENT_TOP_OPACITY * (1 - t)
            + GRADIENT_BOT_OPACITY * t
        )
        gradient.putpixel((0, y), int(alpha_float * 255))

    alpha = gradient.resize((w, h))
    black = Image.new("RGBA", (w, h), (0, 0, 0, 255))
    black.putalpha(alpha)

    return Image.alpha_composite(base, black)

def _rounded_rect(draw: ImageDraw.ImageDraw, xy, radius, fill, outline=None, width: int = 1):
    x0, y0, x1, y1 = xy
    draw.rounded_rectangle(xy, radius=radius, fill=fill, outline=outline, width=width)

def _draw_centered_text(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.FreeTypeFont, center_x: int, y: int, fill):
    bbox = font.getbbox(text)
    w = bbox[2] - bbox[0]
    h = bbox[3] - bbox[1]
    x = center_x - w // 2
    draw.text((x, y), text, font=font, fill=fill)
    return h

def _measure_text(font: ImageFont.FreeTypeFont, text: str):
    bbox = font.getbbox(text)
    return bbox[2] - bbox[0], bbox[3] - bbox[1]

def centered_zoom(clip, zoom_func):
    """
    Aplica un zoom progresivo manteniendo el centro exacto del clip.
    """
    w, h = clip.size

    def make_frame(t):
        frame = clip.get_frame(t)
        import numpy as np
        from PIL import Image

        zoom = zoom_func(t)

        # Convertimos a PIL
        pil = Image.fromarray(frame)

        # Nuevo tamaño según zoom
        new_w = int(w * zoom)
        new_h = int(h * zoom)

        # Redimensionar usando LANCZOS
        resized = pil.resize((new_w, new_h), Image.LANCZOS)

        # Coordenadas para recortar al centro
        left = (new_w - w) // 2
        top = (new_h - h) // 2
        right = left + w
        bottom = top + h

        cropped = resized.crop((left, top, right, bottom))
        return np.array(cropped)

    return clip.set_make_frame(make_frame)

def zoom_factor(t):
    # zoom inicial y final
    z0, z1 = 1.05, 1.13

    # easing type ease-in-out
    ratio = t / duration
    eased = ratio**2 * (3 - 2 * ratio)

    return z0 + (z1 - z0) * eased


# ---------------------------------------------------------------------------
# Composición del frame
# ---------------------------------------------------------------------------

# def _compose_frame(
#     bg_image_path: str,
#     title: str,
#     price: str,
#     dates: str,
#     logo_path: Optional[str],
#     brand_line: Optional[str],
# ) -> Image.Image:
#     """
#     Devuelve un frame PIL ya compuesto con:
#     - fondo
#     - degradado
#     - logo arriba derecha
#     - banda central con ruta, fechas, precio
#     - @escapadasgo_mallorca abajo
#     """
#     # --- Fondo ---
#     bg = Image.open(bg_image_path).convert("RGB")
#     bg = bg.resize((WIDTH, HEIGHT), Image.LANCZOS)
#     bg = bg.filter(ImageFilter.GaussianBlur(radius=1.5))
#     bg = _apply_vertical_gradient(bg)

#     frame = bg.copy().convert("RGBA")
#     draw = ImageDraw.Draw(frame, "RGBA")

#     center_x = WIDTH // 2

#     # ============================================================
#     # LOGO ARRIBA DERECHA
#     # ============================================================
#     if logo_path and Path(logo_path).exists():
#         logo = Image.open(logo_path).convert("RGBA")
#         logo_target_w = int(WIDTH * LOGO_WIDTH_REL)
#         ratio = logo_target_w / logo.width
#         logo_target_h = int(logo.height * ratio)
#         logo = logo.resize((logo_target_w, logo_target_h), Image.LANCZOS)

#         # Glow suave detrás del logo
#         glow = logo.copy()
#         r, g, b, a = glow.split()
#         glow = glow.filter(ImageFilter.GaussianBlur(LOGO_GLOW_BLUR))
#         glow_layer = Image.new("RGBA", glow.size, (0, 0, 0, LOGO_GLOW_ALPHA))
#         glow_layer.putalpha(a)

#         logo_x = WIDTH - logo.width - LOGO_MARGIN
#         logo_y = LOGO_MARGIN

#         frame.alpha_composite(glow_layer, (logo_x, logo_y))
#         frame.alpha_composite(logo, (logo_x, logo_y))

#     # ============================================================
#     # BANDA CENTRAL
#     # ============================================================
#     card_w = int(WIDTH * CARD_WIDTH_REL)
#     card_h = int(HEIGHT * CARD_HEIGHT_REL)
#     card_x0 = center_x - card_w // 2
#     card_y0 = HEIGHT // 2 - card_h // 2
#     card_x1 = card_x0 + card_w
#     card_y1 = card_y0 + card_h

#     # Sombra de la tarjeta
#     shadow = Image.new("RGBA", (card_w + 40, card_h + 40), (0, 0, 0, 0))
#     shadow_draw = ImageDraw.Draw(shadow, "RGBA")
#     _rounded_rect(
#         shadow_draw,
#         (20, 20, card_w + 20, card_h + 20),
#         radius=CARD_RADIUS,
#         fill=(0, 0, 0, 160),
#     )
#     shadow = shadow.filter(ImageFilter.GaussianBlur(18))
#     frame.alpha_composite(shadow, (card_x0 - 20, card_y0 - 20))

#     # Tarjeta principal
#     _rounded_rect(
#         draw,
#         (card_x0, card_y0, card_x1, card_y1),
#         radius=CARD_RADIUS,
#         fill=COLORS["card"],
#         outline=COLORS["card_border"],
#         width=2,
#     )

#     # ============================================================
#     # TIPOGRAFÍAS Y TEXTOS
#     # ============================================================
#     route_font = _font(110, kind="route")   # PMI ✈ VIE, con DejaVuSans
#     dates_font = _font(60,  kind="default")
#     price_font = _font(75,  kind="default")
    
#     route_text = title.upper()   # "PMI ✈ VIE"
#     dates_text = dates.upper()
#     price_text = price

#     # Alturas de cada bloque
#     _, h_route = _measure_text(route_font, route_text)
#     _, h_dates = _measure_text(dates_font, dates_text)
#     _, h_price = _measure_text(price_font, price_text)

#     # Espaciados
#     gap_route_line = 115     # entre ruta y línea
#     gap_line_dates = 43     # entre línea y fechas
#     gap_dates_price = 51    # entre fechas y precio
#     line_width = 3

#     # Altura total ocupada por todo el bloque dentro de la tarjeta
#     total_h = (
#         h_route
#         + gap_route_line
#         + line_width
#         + gap_line_dates
#         + h_dates
#         + gap_dates_price
#         + h_price
#     )

#     # Y inicial para centrar el conjunto dentro de la tarjeta
#     start_y = card_y0 + (card_h - total_h) // 2

#     # ------------------------------------------------------------
#     # 1) Ruta (PMI ✈ VIE)
#     # ------------------------------------------------------------
#     y = start_y
#     h_used_route = _draw_centered_text(
#         draw, route_text, route_font, center_x, y, COLORS["white"]
#     )

#     # ------------------------------------------------------------
#     # 2) Línea divisoria (justo debajo de la ruta, sin cruzarla)
#     # ------------------------------------------------------------
#     y += h_used_route + gap_route_line
#     line_y = y  # posición vertical de la línea

#     line_margin_x = 140
#     draw.line(
#         (card_x0 + line_margin_x, line_y, card_x1 - line_margin_x, line_y),
#         fill=(255, 255, 255, 90),
#         width=line_width,
#     )

#     # ------------------------------------------------------------
#     # 3) Fechas
#     # ------------------------------------------------------------
#     y = line_y + gap_line_dates
#     h_used_dates = _draw_centered_text(
#         draw, dates_text, dates_font, center_x, y, COLORS["dates"]
#     )

#     # ------------------------------------------------------------
#     # 4) Precio
#     # ------------------------------------------------------------
#     y = y + h_used_dates + gap_dates_price
#     _draw_centered_text(
#         draw, price_text, price_font, center_x, y, COLORS["price"]
#     )

#     # ============================================================
#     # BRAND LINE ABAJO (fuera de la tarjeta)
#     # ============================================================
#     if brand_line:
#         brand_font = _font(46)
#         _, h_brand = _measure_text(brand_font, brand_line)
#         brand_y = HEIGHT - SAFE_AREA - h_brand - 100
#         _draw_centered_text(
#             draw, brand_line, brand_font, center_x, brand_y, COLORS["brand"]
#         )

#     return frame

def _compose_frame(
    bg: Image.Image,
    title: str,
    price: str,
    dates: str,
    logo_path: Optional[str],
    brand_line: Optional[str],
    discount_pct: Optional[float] = None,
    category_label: Optional[str] = None,
) -> Image.Image:
    """
    Devuelve un frame PIL ya compuesto con:
    - fondo (a partir de una PIL.Image)
    - degradado
    - logo arriba derecha
    - banda central con ruta, fechas, precio
    - pequeño texto de descuento bajo el precio
    - píldora de categoría arriba izqda. de la tarjeta
    - @escapadasgo_mallorca abajo
    """
    # --- Fondo ---
    bg = bg.convert("RGB")
    bg = bg.resize((WIDTH, HEIGHT), Image.LANCZOS)
    bg = bg.filter(ImageFilter.GaussianBlur(radius=1.5))
    bg = _apply_vertical_gradient(bg)

    frame = bg.copy().convert("RGBA")
    draw = ImageDraw.Draw(frame, "RGBA")

    center_x = WIDTH // 2

    # ============================================================
    # LOGO ARRIBA DERECHA
    # ============================================================
    if logo_path and Path(logo_path).exists():
        logo = Image.open(logo_path).convert("RGBA")
        logo_target_w = int(WIDTH * LOGO_WIDTH_REL)
        ratio = logo_target_w / logo.width
        logo_target_h = int(logo.height * ratio)
        logo = logo.resize((logo_target_w, logo_target_h), Image.LANCZOS)

        glow = logo.copy()
        r, g, b, a = glow.split()
        glow = glow.filter(ImageFilter.GaussianBlur(LOGO_GLOW_BLUR))
        glow_layer = Image.new("RGBA", glow.size, (0, 0, 0, LOGO_GLOW_ALPHA))
        glow_layer.putalpha(a)

        logo_x = WIDTH - logo.width - LOGO_MARGIN
        logo_y = LOGO_MARGIN

        frame.alpha_composite(glow_layer, (logo_x, logo_y))
        frame.alpha_composite(logo, (logo_x, logo_y))

    # ============================================================
    # BANDA CENTRAL
    # ============================================================
    card_w = int(WIDTH * CARD_WIDTH_REL)
    card_h = int(HEIGHT * CARD_HEIGHT_REL)
    card_x0 = center_x - card_w // 2
    card_y0 = HEIGHT // 2 - card_h // 2
    card_x1 = card_x0 + card_w
    card_y1 = card_y0 + card_h

    # Sombra
    shadow = Image.new("RGBA", (card_w + 40, card_h + 40), (0, 0, 0, 0))
    shadow_draw = ImageDraw.Draw(shadow, "RGBA")
    _rounded_rect(
        shadow_draw,
        (20, 20, card_w + 20, card_h + 20),
        radius=CARD_RADIUS,
        fill=(0, 0, 0, 160),
    )
    shadow = shadow.filter(ImageFilter.GaussianBlur(18))
    frame.alpha_composite(shadow, (card_x0 - 20, card_y0 - 20))

    # Tarjeta principal
    _rounded_rect(
        draw,
        (card_x0, card_y0, card_x1, card_y1),
        radius=CARD_RADIUS,
        fill=COLORS["card"],
        outline=COLORS["card_border"],
        width=2,
    )

    # ============================================================
    # PÍLDORA DE CATEGORÍA (arriba izquierda de la tarjeta)
    # ============================================================
    pill_padding_x = 26
    pill_padding_y = 10

    if category_label:
        cat_text = category_label.upper()
        cat_font = _font(34)
        w_cat, h_cat = _measure_text(cat_font, cat_text)

        pill_w = w_cat + 2 * pill_padding_x
        pill_h = h_cat + 2 * pill_padding_y

        pill_x0 = card_x0 + 40
        pill_y0 = card_y0 + 34
        pill_x1 = pill_x0 + pill_w
        pill_y1 = pill_y0 + pill_h

        _rounded_rect(
            draw,
            (pill_x0, pill_y0, pill_x1, pill_y1),
            radius=pill_h // 2,
            fill=COLORS["pill_bg"],
        )

        text_x = pill_x0 + (pill_w - w_cat) // 2
        text_y = pill_y0 + (pill_h - h_cat) // 2
        draw.text((text_x, text_y), cat_text, font=cat_font, fill=COLORS["pill_text"])

    # ============================================================
    # TIPOGRAFÍAS Y TEXTOS PRINCIPALES
    # ============================================================
    route_font = _font(110, kind="route")   # PMI ✈ VIE
    dates_font = _font(60,  kind="default")
    price_font = _font(75,  kind="default")

    route_text = title.upper()
    dates_text = dates.upper()
    price_text = price

    # --- Descuento como texto debajo del precio (Opción B) ---
    min_discount_to_show = 30.0
    show_discount = discount_pct is not None and discount_pct >= min_discount_to_show

    if show_discount:
        disc_value = max(float(discount_pct), 0.0)
        disc_int = int(round(disc_value))
        discount_text = f"↓ {disc_int}% más barato de lo habitual"
        discount_font = _font(44, kind="default")
        _, h_discount = _measure_text(discount_font, discount_text)
        gap_price_discount = 22  # espacio entre precio y línea de descuento
    else:
        discount_text = ""
        discount_font = None
        h_discount = 0
        gap_price_discount = 0

    # Alturas
    _, h_route = _measure_text(route_font, route_text)
    _, h_dates = _measure_text(dates_font, dates_text)
    _, h_price = _measure_text(price_font, price_text)

    gap_route_line   = 115   # ruta → línea
    gap_line_dates   = 43    # línea → fechas
    gap_dates_price  = 40    # fechas → precio

    extra_block_h = gap_price_discount + h_discount if show_discount else 0

    total_h = (
        h_route
        + gap_route_line
        + gap_line_dates
        + h_dates
        + gap_dates_price
        + h_price
        + extra_block_h
    )

    start_y = card_y0 + (card_h - total_h) // 2
    y = start_y

    # 1) Ruta
    h_used = _draw_centered_text(draw, route_text, route_font, center_x, y, COLORS["white"])
    y += h_used + gap_route_line

    # 2) Línea
    line_margin_x = 140
    line_y = y
    draw.line(
        (card_x0 + line_margin_x, line_y, card_x1 - line_margin_x, line_y),
        fill=(255, 255, 255, 90),
        width=3,
    )
    y = line_y + gap_line_dates

    # 3) Fechas
    h_used = _draw_centered_text(draw, dates_text, dates_font, center_x, y, COLORS["dates"])
    y += h_used + gap_dates_price

    # 4) Precio
    h_used = _draw_centered_text(draw, price_text, price_font, center_x, y, COLORS["price"])
    y += h_used

    # 5) Descuento (si aplica)
    if show_discount and discount_font:
        y += gap_price_discount
        _draw_centered_text(
            draw,
            discount_text,
            discount_font,
            center_x,
            y,
            COLORS["accent"],   # amarillo suave para destacar
        )

    # ============================================================
    # BRAND LINE ABAJO (fuera de la tarjeta)
    # ============================================================
    if brand_line:
        brand_font = _font(46)
        _, h_brand = _measure_text(brand_font, brand_line)
        brand_y = HEIGHT - SAFE_AREA - h_brand - 100
        _draw_centered_text(draw, brand_line, brand_font, center_x, brand_y, COLORS["brand"])

    return frame

    

# ---------------------------------------------------------------------------
# Helper de más alto nivel
# ---------------------------------------------------------------------------

def create_reel_for_flight(
    flight,
    out_mp4_path: str,
    logo_path: Optional[str] = None,
    brand_line: Optional[str] = "@escapadasgo_mallorca",
    duration: float = 4.0,
):
    """
    Helper que construye title/dates/price a partir de un objeto Flight O de un dict.
    Espera que el flight/candidate tenga:
      - origin, destination (IATA)
      - start_date, end_date (YYYY-MM-DD o 'YYYY-MM-DD HH:MM:SS')
      - price (numérico)
    """
    origin = _fget(flight, "origin", "PMI") or "PMI"
    destination = _fget(flight, "destination", "VIE") or "VIE"

    start_raw = _fget(flight, "start_date", "") or ""
    end_raw   = _fget(flight, "end_date", "") or ""

    # Nos aseguramos de quedarnos solo con 'YYYY-MM-DD' si viene con hora
    start_date = str(start_raw)[:10] if start_raw else ""
    end_date   = str(end_raw)[:10] if end_raw else ""

    price_value = _fget(flight, "price", 0) or 0
    price_value = float(price_value)

    title = f"{origin} ✈ {destination}"

    # Solo formateamos si tenemos ambas fechas
    if start_date and end_date:
        dates = format_dates_dd_mmm(start_date, end_date)
    else:
        dates = ""

    price_str = f"{int(round(price_value))} € i/v"

    # --------- NUEVO: descuento y categoría ----------
    raw_discount = _fget(flight, "discount_pct", None)
    discount_pct = float(raw_discount) if raw_discount is not None else None

    category_code = _fget(flight, "category_code", None)

    # Mapeo simple a etiqueta + icono
    category_label = None
    if category_code:
        code = str(category_code).lower()
        mapping = {
            "finde_perfecto":     "✨ Finde perfecto",
            "ultra_chollo":       "🔥 Ultra chollo",
            "cultural":           "🏛 Escapada cultural",
            "romantica":          "💞 Escapada romántica",
            "gastronomica":       "🍽 Escapada gastro",
            "escapada_perfecta":  "⭐ Escapada perfecta",
        }
        category_label = mapping.get(code, code.replace("_", " ").title())

    # -----------------------------------------------

    bg_path = pick_image_for_destination(destination) or pick_image_for_destination("DEFAULT")
    if not bg_path:
        raise FileNotFoundError(
            "No se ha encontrado ninguna imagen para el destino ni DEFAULT en media/images"
        )

    create_reel_v4(
        bg_image_path=str(bg_path),
        out_mp4_path=out_mp4_path,
        title=title,
        price=price_str,
        dates=dates,
        duration=duration,
        logo_path=logo_path,
        brand_line=brand_line,
        discount_pct=discount_pct,
        category_label=category_label,
    )

    return out_mp4_path
