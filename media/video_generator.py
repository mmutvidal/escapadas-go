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

from content.destinations import get_city  # para convertir IATA → ciudad

import uuid

try:
    import boto3
except ImportError:
    boto3 = None  # por si este módulo se importa en un entorno sin boto3



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

WEEKDAYS_ES = [
    "LUN", "MAR", "MIÉ", "JUE", "VIE", "SÁB", "DOM",
]

def _parse_date_ymd(s: str) -> datetime:
    return datetime.strptime(s[:10], "%Y-%m-%d")

def format_dates_dd_mmm(start_date: str, end_date: str) -> str:
    """
    Recibe '2025-12-12' y '2025-12-14' y devuelve
    'VIE 12 DIC – DOM 14 DIC'
    """
    d1 = _parse_date_ymd(start_date)
    d2 = _parse_date_ymd(end_date)

    def f(d: datetime) -> str:
        dow = WEEKDAYS_ES[d.weekday()]            # día de la semana
        return f"{dow} {d.day:02d} {MONTHS_ES[d.month - 1]}"

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
    # "badge_bg": (255, 209, 117, 235),      # fondo descuento
    # "badge_text": (255, 255, 255, 230),
    # # "pill_bg": (29, 44, 76, 240),          # fondo categoría
    # "pill_text": (230, 232, 236, 255),
    # "pill_bg": (255, 255, 255, 35),
    # "pill_text": (255, 255, 255),
    # "pill_border_soft": (255, 255, 255, 80),

    "pill_bg": (30, 65, 120),     # Azul corporativo oscuro
    "pill_text": (255, 255, 255),
    "pill_border_soft": (255, 255, 255, 60),
    
        # nuevos
    "accent": (249, 196, 88, 255),        # para el badge de descuento
    "pill_text_dark": (15, 23, 42, 255),  # texto oscuro sobre el badge amarillo
    # "pill_border_soft": (255, 255, 255, 120),
    # "red": (165, 32, 25, 1),
    "red": (213, 107, 71, 1),
}

# ORIGIN_THEME = {
#     "PMI": {"bg": (30, 65, 120), "text": (255, 255, 255)},     # azul
#     "BCN": {"bg": (16, 112, 84), "text": (255, 255, 255)},     # verde
#     "MAD": {"bg": (153, 27, 27), "text": (255, 255, 255)},     # rojo
#     "VLC": {"bg": (194, 65, 12), "text": (255, 255, 255)},     # naranja
#     # fallback
#     "_DEFAULT": {"bg": (30, 65, 120), "text": (255, 255, 255)},
# }

ORIGIN_THEME = {
    # Islas
    "PMI": {"bg": (30, 65, 120), "text": (255, 255, 255)},     # azul profundo (Mallorca)
    "TFN": {"bg": (88, 28, 135), "text": (255, 255, 255)},    # morado volcánico (Canarias)

    # Península
    "BCN": {"bg": (16, 112, 84), "text": (255, 255, 255)},    # verde mediterráneo
    "MAD": {"bg": (153, 27, 27), "text": (255, 255, 255)},    # rojo institucional
    "VLC": {"bg": (194, 65, 12), "text": (255, 255, 255)},    # naranja cálido
    "AGP": {"bg": (15, 118, 110), "text": (255, 255, 255)},   # teal andaluz
    "ALC": {"bg": (180, 83, 9), "text": (255, 255, 255)},     # ámbar / dorado

    # fallback
    "_DEFAULT": {"bg": (30, 65, 120), "text": (255, 255, 255)},
}


GRADIENT_TOP_OPACITY = 0.15
GRADIENT_BOT_OPACITY = 0.65

LOGO_WIDTH_REL = 0.26         # porcentaje del ancho del vídeo
LOGO_MARGIN = 40
SAFE_AREA = 40

CARD_WIDTH_REL = 0.86
CARD_HEIGHT_REL = 0.30
CARD_RADIUS = 90

LOGO_GLOW_BLUR = 10
LOGO_GLOW_ALPHA = 100

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


def get_origin_theme(origin: str):
    origin = (origin or "").upper()
    return ORIGIN_THEME.get(origin, ORIGIN_THEME["_DEFAULT"])
    

def _ease_in_out(x: float) -> float:
    # clamp 0..1
    if x <= 0: return 0.0
    if x >= 1: return 1.0
    return x * x * (3 - 2 * x)

def _alpha_window(t: float, start: float, end: float, fade: float = 0.18) -> int:
    """
    Devuelve alpha 0..255.
    - Entra con fade (segundos) desde start
    - Se mantiene hasta end
    - Si end es None, se mantiene hasta el final
    """
    if end is not None and t >= end:
        return 0

    if t < start:
        return 0

    # fade-in
    if fade > 0:
        x = (t - start) / fade
        a = int(255 * _ease_in_out(x))
        return max(0, min(255, a))

    return 255

def _with_alpha(color, a: int):
    """
    Acepta (R,G,B) o (R,G,B,A) y devuelve (R,G,B,a)
    """
    if color is None:
        return None
    if len(color) == 4:
        r, g, b, _ = color
    else:
        r, g, b = color
    return (r, g, b, a)



def _text_bbox(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.FreeTypeFont):
    # bbox (x0,y0,x1,y1)
    return draw.textbbox((0, 0), text, font=font)

def _text_size(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.FreeTypeFont):
    x0, y0, x1, y1 = _text_bbox(draw, text, font)
    return (x1 - x0), (y1 - y0)

def _wrap_text_max_lines(draw, text, font, max_width, max_lines=3):
    words = (text or "").split()
    if not words:
        return [""]

    lines = []
    cur = ""

    for w in words:
        test = (cur + " " + w).strip()
        tw, _ = _text_size(draw, test, font)

        if tw <= max_width:
            cur = test
        else:
            # si ya vamos a crear la última línea, metemos el resto aquí
            if len(lines) == max_lines - 1:
                # mete palabra actual y lo que falta
                rest = " ".join([w] + words[words.index(w)+1:])
                cur = (cur + " " + rest).strip() if cur else rest
                break

            if cur:
                lines.append(cur)
            cur = w

    if cur and len(lines) < max_lines:
        lines.append(cur)

    return lines[:max_lines]
    

def _ellipsize_to_width(draw, text, font, max_width):
    if not text:
        return text
    ell = "…"
    if _text_size(draw, text, font)[0] <= max_width:
        return text
    # recorta hasta que quepa con elipsis
    s = text
    while s and _text_size(draw, s + ell, font)[0] > max_width:
        s = s[:-1]
    return (s + ell) if s else ell

def _fit_text_in_box(draw, text, font_kind="default",
                     max_w=800, max_h=260,
                     start_size=90, min_size=44,
                     max_lines=2, line_spacing=1.06):
    """
    Devuelve (lines, font) ajustados para caber en una caja max_w x max_h.
    - Baja tamaño hasta que quepa.
    - Wrap hasta max_lines.
    - Si aun así no cabe, elipsiza última línea.
    """
    text = (text or "").strip()
    if not text:
        return ([""], _font(min_size, kind=font_kind))

    size = start_size
    while size >= min_size:
        font = _font(size, kind=font_kind)
        lines = _wrap_text_max_lines(draw, text, font, max_w, max_lines=max_lines)

        # Medimos alto total
        line_heights = []
        max_line_w = 0
        for ln in lines:
            w, h = _text_size(draw, ln, font)
            max_line_w = max(max_line_w, w)
            line_heights.append(h)

        total_h = 0
        for i, h in enumerate(line_heights):
            total_h += h
            if i < len(line_heights) - 1:
                total_h += int(h * (line_spacing - 1.0))

        # Cabe?
        if max_line_w <= max_w and total_h <= max_h:
            return (lines, font)

        size -= 2

    # Último recurso: usa min_size y elipsiza
    font = _font(min_size, kind=font_kind)
    lines = _wrap_text_max_lines(draw, text, font, max_w, max_lines=max_lines)
    if lines:
        lines[-1] = _ellipsize_to_width(draw, lines[-1], font, max_w)
    return (lines, font)

def _draw_multiline_centered(draw, lines, font, center_x, center_y, fill,
                            line_spacing=1.25, min_gap=10):
    # Medimos cada línea
    widths, heights = [], []
    for ln in lines:
        w, h = _text_size(draw, ln, font)
        widths.append(w)
        heights.append(h)

    # Un line_height único (el máximo) + spacing
    base_h = max(heights) if heights else 0
    line_h = max(int(base_h * line_spacing), base_h + min_gap)

    total_h = line_h * len(lines)
    y = int(center_y - total_h / 2)

    for i, ln in enumerate(lines):
        x = int(center_x - widths[i] / 2)
        # centramos cada línea dentro de su “slot”
        y_line = y + int((line_h - heights[i]) / 2)
        draw.text((x, y_line), ln, font=font, fill=fill)
        y += line_h


def choose_origin_pill_variant(ab_ratio_on: float = 0.5) -> tuple[bool, str]:
    """
    Devuelve:
      - show_origin_pill (bool)
      - origin_pill_variant ("origin_pill_on" | "origin_pill_off")
    """
    r = random.random()
    show = r < float(ab_ratio_on)
    return show, ("origin_pill_on" if show else "origin_pill_off")


# ---------------------------------------------------------------------------
# Helpers de dibujo
# ---------------------------------------------------------------------------
def _get_field(obj, key, default=None):
    """
    Permite usar indistintamente dicts o objetos con atributos.
    """
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def _short_category_label(cat) -> Optional[str]:
    """
    Recibe algo tipo:
      - {"code": "finde_perfecto", "label": "🔥 Ultra Chollo"}
      - "finde_perfecto"
      - "🍝 Escapada gastronómica"
    y devuelve un texto corto para el badge SIN emojis iniciales.
    """
    if isinstance(cat, dict):
        code = cat.get("code") or cat.get("label")
    else:
        code = cat

    if not code:
        return None

    # Helper para quitar iconos / símbolos al principio
    def _strip_leading_symbols(s: str) -> str:
        s = (s or "").strip()
        while s and not s[0].isalnum():
            s = s[1:].lstrip()
        return s

    # Si nos llega algo tipo "🍝 Escapada gastronómica", lo tratamos
    # como etiqueta humana: limpiamos icono y devolvemos tal cual.
    if isinstance(code, str) and "escapada" in code.lower():
        label = _strip_leading_symbols(code)
        return label.upper()

    # --- Caso normal: usamos códigos cortos y el mapping ---
    mapping = {
        "finde_perfecto":    "Finde perfecto",
        "ultra_chollo":      "Ultra chollo",
        "chollo":            "Chollo",
        "romantica":         "Escapada romántica",
        "cultural":          "Escapada cultural",
        "gastronomica":      "Escapada gastronómica",
        "escapada_perfecta": "Escapada perfecta",
        "oferta":            "Oferta",
    }

    if isinstance(code, str):
        key = _strip_leading_symbols(code).lower().replace(" ", "_")
    else:
        key = code

    label = mapping.get(key)
    if not label:
        # fallback genérico pero ya sin emojis delante
        clean = _strip_leading_symbols(str(code))
        label = clean.replace("_", " ").title()

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

    # radius = pill_h / 2
    radius = 22
    
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

def _draw_pill_with_shadow(
    base_img: Image.Image,
    text: str,
    font: ImageFont.FreeTypeFont,
    center_x: float,
    center_y: float,
    padding_x: float,
    padding_y: float,
    bg_color,
    text_color,
    border_color=None,
    shadow_offset_y: int = 6,
    shadow_blur: int = 10,
    shadow_alpha: int = 100,
):
    """
    Dibuja una pill con sombra suave debajo.
    Trabaja directamente sobre base_img.
    """
    if not text:
        return

    if base_img.mode != "RGBA":
        base_img = base_img.convert("RGBA")

    W, H = base_img.size
    temp = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    temp_draw = ImageDraw.Draw(temp, "RGBA")

    # Medidas del texto y pill
    bbox = temp_draw.textbbox((0, 0), text, font=font)
    text_w = bbox[2] - bbox[0]
    text_h = bbox[3] - bbox[1]

    pill_w = text_w + 2 * padding_x
    pill_h = text_h + 2 * padding_y

    x0 = center_x - pill_w / 2
    y0 = center_y - pill_h / 2
    x1 = center_x + pill_w / 2
    y1 = center_y + pill_h / 2

    radius = 22  # igual que en _draw_pill

    # 1) Sombra (pill negra semi-transparente, desplazada y desenfocada)
    shadow_color = (0, 0, 0, shadow_alpha)
    temp_draw.rounded_rectangle(
        (x0, y0 + shadow_offset_y, x1, y1 + shadow_offset_y),
        radius=radius,
        fill=shadow_color,
    )
    temp = temp.filter(ImageFilter.GaussianBlur(shadow_blur))

    # Mezclamos sombra con la imagen base
    base_img.alpha_composite(temp)

    # 2) Pill normal encima
    draw = ImageDraw.Draw(base_img, "RGBA")
    draw.rounded_rectangle(
        (x0, y0, x1, y1),
        radius=radius,
        fill=bg_color,
        outline=border_color,
        width=2 if border_color else 0,
    )

    # 3) Texto centrado real dentro de la pill
    bbox = draw.textbbox((0, 0), text, font=font)
    text_w = bbox[2] - bbox[0]
    text_h = bbox[3] - bbox[1]

    text_x = x0 + (pill_w - text_w) / 2 - bbox[0]
    text_y = y0 + (pill_h - text_h) / 2 - bbox[1]

    draw.text((text_x, text_y), text, font=font, fill=text_color)


def _draw_horizontal_fade_line(
    base_img: Image.Image,
    x0: int,
    x1: int,
    y: int,
    color=(255, 255, 255),
    max_alpha: int = 90,
    width: int = 3,
):
    """
    Dibuja una línea horizontal con un pequeño degradado:
    - máxima opacidad en el centro
    - se desvanece hacia los extremos
    """
    if x1 <= x0:
        return

    line_w = int(x1 - x0)
    line_h = width

    # Aseguramos RGB + alpha
    if len(color) == 4:
        r, g, b, _ = color
    else:
        r, g, b = color

    grad = Image.new("RGBA", (line_w, line_h), (0, 0, 0, 0))
    pixels = grad.load()

    for i in range(line_w):
        # 0 en la izquierda, 1 en la derecha
        rel = i / (line_w - 1 if line_w > 1 else 1)
        # distancia al centro (0 en el centro, 1 en los bordes)
        dist_center = abs(rel - 0.5) / 0.5
        alpha = int(max_alpha * (1.0 - dist_center))  # máximo en el centro, 0 en los bordes
        if alpha < 0:
            alpha = 0
        pixels[i, 0] = (r, g, b, alpha)
        # copiamos al resto de filas si width > 1
        for j in range(1, line_h):
            pixels[i, j] = (r, g, b, alpha)

    # centramos verticalmente la línea alrededor de y
    paste_y = int(y - line_h / 2)
    base_img.alpha_composite(grad, (int(x0), paste_y))
    

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



def _compose_frame(
    bg: Image.Image,
    route_main: str,
    route_codes: str,
    price: str,
    dates: str,
    logo_path: Optional[str],
    brand_line: Optional[str],
    t: float = 0.0,
    reveal: Optional[dict] = None,
    hook_text: Optional[str] = None,
    hook_mode: str = "band",   # "band" o "pill"
    discount_pct: Optional[float] = None,
    category_label: Optional[str] = None,
    origin_pill_text: Optional[str] = None,
    origin_code: Optional[str] = None,
    show_origin_pill: bool = False,
) -> Image.Image:
    """
    Devuelve un frame PIL ya compuesto con:
    - fondo (a partir de una PIL.Image)
    - degradado
    - logo arriba derecha
    - banda central con:
        línea 1: ciudades (Mallorca – Milán)
        línea 2: códigos IATA (PMI ✈ BGY)
        fechas
        precio
        descuento debajo
    - píldora de categoría con sombra, solapando la tarjeta
    - @escapadasgo_mallorca abajo
    """
    # ------------------------------------------------------------
    # REVEAL TIMINGS (por defecto)
    # ------------------------------------------------------------
    if reveal is None:
        reveal = {
            "hook":  (0.00, 0.90),   # hook visible desde el inicio
            "pill":  (0.90, None),
            "main":  (1.10, None),
            "codes": (1.35, None),
            "line":  (1.35, None),
            "dates": (2.00, None),
            "price": (3.30, None),
            "disc":  (3.30, None),
        }

    a_hook  = _alpha_window(t, *reveal["hook"],  fade=0.12)
    a_pill  = _alpha_window(t, *reveal["pill"],  fade=0.18)
    a_main  = _alpha_window(t, *reveal["main"],  fade=0.18)
    a_codes = _alpha_window(t, *reveal["codes"], fade=0.18)
    a_line  = _alpha_window(t, *reveal["line"],  fade=0.18)
    a_dates = _alpha_window(t, *reveal["dates"], fade=0.18)
    a_price = _alpha_window(t, *reveal["price"], fade=0.18)
    a_disc  = _alpha_window(t, *reveal["disc"],  fade=0.18)
    
    disable_origin_branding = ((origin_code or "").upper() == "PMI")

    
    # --- Fondo ---
    bg = bg.convert("RGB")
    bg = bg.resize((WIDTH, HEIGHT), Image.LANCZOS)
    bg = bg.filter(ImageFilter.GaussianBlur(radius=1.5))
    bg = _apply_vertical_gradient(bg)

    frame = bg.copy().convert("RGBA")
    draw = ImageDraw.Draw(frame, "RGBA")

    center_x = WIDTH // 2

    W, H = frame.size
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
    # ORIGIN PILL (arriba izquierda)
    # ============================================================
    if (not disable_origin_branding) and show_origin_pill and origin_pill_text:
        origin_font = _font(40)
        theme = get_origin_theme(origin_code or "")  # origin_code = "BCN"
        _draw_pill_with_shadow(
            base_img=frame,
            text=origin_pill_text.upper(),
            font=origin_font,
            center_x=SAFE_AREA + 220,
            center_y=SAFE_AREA + 70,
            padding_x=26,
            padding_y=14,
            bg_color=theme["bg"],
            text_color=theme["text"],
            border_color=(255, 255, 255, 70),
        )

    
    # ============================================================
    # BANDA CENTRAL (tarjeta)
    # ============================================================
    card_w = int(WIDTH * CARD_WIDTH_REL)
    card_h = int(HEIGHT * CARD_HEIGHT_REL)
    card_x0 = center_x - card_w // 2
    card_y0 = HEIGHT // 2 - card_h // 2
    card_x1 = card_x0 + card_w
    card_y1 = card_y0 + card_h

   
    # Sombra de la tarjeta
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
    # ORIGIN COLOR BAR (dentro del card, izquierda)
    # ============================================================
    # if show_origin_pill and origin_code:
    #     theme = get_origin_theme(origin_code)
    #     bar_w = 10
    #     draw.rounded_rectangle(
    #         (card_x0 + 22, card_y0 + 26, card_x0 + 22 + bar_w, card_y1 - 26),
    #         radius=10,
    #         fill=theme["bg"],
    #     )

    if (not disable_origin_branding) and show_origin_pill and origin_code:
        theme = get_origin_theme(origin_code)
        band_w = 10
        draw.rectangle((0, 0, band_w, H), fill=theme["bg"])
        
    # ============================================================
    # HOOK GRANDE EN LA BANDA (visible en t=0 para preview)
    # ============================================================
    hook = hook_text
    
    hook_box_w = int(card_w * 0.84)   # un pelín más estrecha para respirar
    hook_box_h = int(card_h * 0.68)   # más alta para permitir 3 líneas
    
    lines, hfont = _fit_text_in_box(
        draw=draw,
        text=hook,
        font_kind="default",
        max_w=hook_box_w,
        max_h=hook_box_h,
        start_size=86,
        min_size=40,
        max_lines=3,
        line_spacing=1.18,
    )
    
    # alpha: visible en frame 0
    hook_start, hook_end = reveal.get("hook", (0.0, 0.9))
    if t <= (1.0 / FPS):
        a_hook = 255
    else:
        a_hook = _alpha_window(t, hook_start, hook_end, fade=0.12)
    
    if a_hook > 0:
        _draw_multiline_centered(
            draw,
            lines,
            hfont,
            center_x,
            (card_y0 + card_y1) // 2,
            fill=_with_alpha(COLORS["white"], a_hook),
            line_spacing=1.28,
        )

    
# ============================================================
    # PÍLDORA (HOOK primero, luego categoría)
    # ============================================================
    pill_font = _font(28)
    pill_center_x = center_x
    pill_center_y = card_y0 - 14

    hook_start, hook_end = reveal.get("hook", (0.0, 0.9))
    
    # IMPORTANTE: que en el primer frame ya sea visible para el preview
    if t <= (1.0 / FPS):
        a_hook = 255
    else:
        a_hook = _alpha_window(t, hook_start, hook_end, fade=0.12)

    # Si estamos en fase hook, mostramos hook_text (o fallback)
    # if a_hook > 0:
    #     ht = (hook_text or "SAL DE MALLORCA POR <40€").upper()
    #     _draw_pill_with_shadow(
    #         base_img=frame,
    #         text=ht,
    #         font=pill_font,
    #         center_x=pill_center_x,
    #         center_y=pill_center_y,
    #         padding_x=30,
    #         padding_y=18,
    #         bg_color=_with_alpha(COLORS.get("pill_bg", (30, 65, 120)), a_hook),
    #         text_color=_with_alpha((255, 255, 255), a_hook),
    #         border_color=COLORS.get("pill_border_soft", (255, 255, 255, 60)),
    #     )
    if category_label and a_pill > 0:
        cat_text = category_label.upper()
        _draw_pill_with_shadow(
            base_img=frame,
            text=cat_text,
            font=pill_font,
            center_x=pill_center_x,
            center_y=pill_center_y,
            padding_x=30,
            padding_y=18,
            bg_color=COLORS.get("pill_bg", (30, 65, 120)),
            text_color=COLORS.get("pill_text", (255, 255, 255)),
            border_color=COLORS.get("pill_border_soft", (255, 255, 255, 60)),
        )

    # ============================================================
    # TIPOGRAFÍAS Y TEXTOS PRINCIPALES
    # ============================================================

    # Textos base
    route_main_text  = route_main          # "Mallorca – Friedrichshafen"
    route_codes_text = route_codes.upper() # "PMI ✈ FDH"
    dates_text       = dates.upper()
    price_text       = price

    # 1) Fuente dinámica para la línea principal (ciudades)
    base_route_size = 88   # tamaño ideal
    min_route_size  = 58   # no bajaremos de aquí
    max_route_width = int(card_w * 0.82)  # margen lateral dentro de la tarjeta

    current_size = base_route_size
    route_main_font = _font(current_size, kind="default")

    w_route_main, _ = _measure_text(route_main_font, route_main_text)

    # Reducimos tamaño poco a poco hasta que quepa
    while w_route_main > max_route_width and current_size > min_route_size:
        current_size -= 2
        route_main_font = _font(current_size, kind="default")
        w_route_main, _ = _measure_text(route_main_font, route_main_text)

    # 2) Resto de fuentes (pueden quedarse fijas)
    route_codes_font = _font(50,  kind="route")
    dates_font       = _font(60,  kind="default")
    price_font       = _font(75,  kind="default")
    

    # --- Descuento debajo del precio ---
    min_discount_to_show = 30.0
    show_discount = discount_pct is not None and discount_pct >= min_discount_to_show

    if show_discount:
        disc_value = max(float(discount_pct), 0.0)
        disc_int = int(round(disc_value))
        discount_text = f"(↓ {disc_int}% más barato de lo habitual)"
        discount_font = _font(35, kind="default")
        _, h_discount = _measure_text(discount_font, discount_text)
    else:
        discount_text = ""
        discount_font = None
        h_discount = 0

    # --------- Medimos alturas de cada bloque de texto ----------
    _, h_route_main  = _measure_text(route_main_font,  route_main_text)
    _, h_route_codes = _measure_text(route_codes_font, route_codes_text)
    _, h_dates       = _measure_text(dates_font,       dates_text)
    _, h_price       = _measure_text(price_font,       price_text)

    # Altura total ocupada SOLO por textos (sin espacios ni márgenes)
    reserved_height = h_route_main + h_route_codes + h_dates + h_price + h_discount

    # Espacio disponible dentro de la tarjeta para márgenes + separaciones
    available_space = max(card_h - reserved_height, 0)

     # ------------------------------------------------------------------
    # SISTEMA DE PESOS AJUSTADO
    #  - Más margen arriba (top_w ↑)
    #  - Menos aire alrededor de las fechas (w_line_dates, w_dates_price ↓)
    # ------------------------------------------------------------------
    top_w            = 1.5   # antes 1.0 → más aire arriba
    w_main_codes     = 1.8   # similar, poco espacio entre ciudades/códigos
    w_codes_line     = 2.1   # antes 1.2 → menos hueco hasta la línea
    w_line_dates     = 1.25   # antes 1.2 → menos hueco línea→fechas
    w_dates_price    = 1.8   # antes 1.8 → menos hueco fechas→precio
    w_price_discount = 1 if show_discount else 0.0
    bottom_w         = 1.3   # mantenemos algo de aire abajo

    total_weight = (
        top_w
        + w_main_codes
        + w_codes_line
        + w_line_dates
        + w_dates_price
        + w_price_discount
        + bottom_w
    )

    unit = available_space / total_weight if total_weight > 0 else 0.0

    top_gap              = max(40, top_w * unit)  # fuerza mínimo de 40px arriba
    gap_route_main_codes = w_main_codes * unit
    gap_codes_line       = w_codes_line * unit
    gap_line_dates       = w_line_dates * unit
    gap_dates_price      = w_dates_price * unit
    gap_price_discount   = w_price_discount * unit  # 0 si no hay descuento

    a_main  = _alpha_window(t, *reveal["main"],  fade=0.18)
    a_codes = _alpha_window(t, *reveal["codes"], fade=0.18)
    a_line  = _alpha_window(t, *reveal["line"],  fade=0.18)
    a_dates = _alpha_window(t, *reveal["dates"], fade=0.18)
    a_price = _alpha_window(t, *reveal["price"], fade=0.18)
    a_disc  = _alpha_window(t, *reveal["disc"],  fade=0.18)

    in_hook_phase = (t < reveal["hook"][1])

    # ------------------------------------------------------------------
    # Ahora dibujamos usando esos gaps: el bottom queda implícito y
    # automáticamente simétrico gracias al reparto de pesos.
    # ------------------------------------------------------------------
    y = card_y0 + int(round(top_gap))

    # 1) Ciudades
    if a_main > 0:
        h_used = _draw_centered_text(draw, route_main_text, route_main_font, center_x, int(y), _with_alpha(COLORS["white"], a_main))
    else:
        h_used = h_route_main
        
    # 2) Códigos IATA
    y += h_used + gap_route_main_codes
    if a_codes > 0:
        h_used = _draw_centered_text(draw, route_codes_text, route_codes_font, center_x, int(y), _with_alpha(COLORS["dates"], a_codes))
    else:
        h_used = h_route_codes
        
    
    # 3) Línea separadora con degradado suave
    line_margin_x = 140
    y += h_used + gap_codes_line
    line_y = y
    
    if a_line > 0:
        _draw_horizontal_fade_line(
            base_img=frame,
            x0=card_x0 + line_margin_x,
            x1=card_x1 - line_margin_x,
            y=line_y,
            color=(255, 255, 255, a_line),
            max_alpha=int(90 * (a_line / 255.0)),
            width=3,
        )

    y = line_y + gap_line_dates
    

    # 4) Fechas
    if a_dates > 0:
        h_used = _draw_centered_text(draw, dates_text, dates_font, center_x, int(y), _with_alpha(COLORS["dates"], a_dates))
    else:
        h_used = h_dates
        
    y += h_used + gap_dates_price

    # 5) Precio
    if a_price > 0:
        h_used = _draw_centered_text(draw, price_text, price_font, center_x, int(y), _with_alpha(COLORS["price"], a_price))
    else:
        h_used = h_price
        
    y += h_used

    # 6) Descuento (si procede)
    if show_discount and discount_font and a_disc > 0:
        y += gap_price_discount
        _draw_centered_text(draw, discount_text, discount_font, center_x, int(y), _with_alpha(COLORS["red"], a_disc))
        

    # ============================================================
    # BRAND LINE ABAJO
    # ============================================================
    if brand_line:
        brand_font = _font(46)
        _, h_brand = _measure_text(brand_font, brand_line)
        brand_y = HEIGHT - SAFE_AREA - h_brand - 90
        _draw_centered_text(draw, brand_line, brand_font, center_x, brand_y, COLORS["brand"])

    return frame


def upload_reel_to_s3(
    local_path: str,
    bucket: str,
    prefix: str = "reels/",
    public: bool = True,
) -> str:
    """
    Sube el MP4 a S3 y devuelve la URL pública (o la URL normal del bucket).
    Requiere que boto3 esté configurado con credenciales válidas.
    """
    if boto3 is None:
        raise RuntimeError("boto3 no está instalado en este entorno.")

    s3 = boto3.client("s3")

    lp = Path(local_path)
    ext = lp.suffix or ".mp4"
    # nombre único para evitar colisiones
    key = f"{prefix}{uuid.uuid4().hex}{ext}"

    extra_args = {"ContentType": "video/mp4"}
    if public:
        extra_args["ACL"] = "public-read"

    s3.upload_file(
        Filename=str(lp),
        Bucket=bucket,
        Key=key,
        ExtraArgs=extra_args,
    )

    # URL pública estilo estándar; si usas CloudFront, aquí se cambia
    url = f"https://{bucket}.s3.amazonaws.com/{key}"
    return url
    

# ---------------------------------------------------------------------------
# Creación del reel
# ---------------------------------------------------------------------------

def create_reel_v4(
    bg_image_path: str,
    out_mp4_path: str,
    route_main: str,          # << antes era title
    route_codes: str,         # << NUEVO
    price: str,
    dates: str,
    duration: float = 7.0,
    logo_path: Optional[str] = None,
    fps: int = FPS,
    brand_line: Optional[str] = None,
    discount_pct: Optional[float] = None,
    category_label: Optional[str] = None,
    hook_text: Optional[str] = None,   # 👈 PASAS EL HOOK AL GENERADOR
    hook_mode: str = "",
    origin_pill_text: Optional[str] = None,
    origin_code: Optional[str] = None,
    show_origin_pill: bool = False,
):
    """
    Genera un reel 1080x1920 con:
    - fondo con zoom/pan suave
    - overlay de degradado + banda + textos + logo
    usando _render_frame en cada fotograma.
    """

    # 1) Cargamos la imagen base y la adaptamos a 1080x1920 (cover)
    base = Image.open(Path(bg_image_path)).convert("RGB")
    base = _fit_cover(base, WIDTH, HEIGHT)  # debe quedar exactamente (WIDTH, HEIGHT)

    total_frames = int(round(duration * fps))
    frames = []

    # Parámetros del zoom “loopable”: zoom sinusoidal, mismo valor al inicio y al final
    zoom_center = 1.05     # valor medio del zoom
    zoom_amp = 0.06        # amplitud (sube y baja +-)
    # Con esto: zoom(t) = 1.05 + 0.06 * sin(2π t / duration)

    reveal = {
        "hook":  (0.00, 1.50),   # antes 0.90
        "pill":  (1.20, None),   # solape suave
        "main":  (1.60, None),
        "codes": (1.85, None),
        "line":  (1.85, None),
        "dates": (2.30, None),
        "price": (3.45, None),
        "disc":  (3.45, None),
    }

    # reveal = {
    #     "hook":  (0.00, 1.80),   # antes 0.90
    #     "pill":  (1.50, None),   # solape suave
    #     "main":  (1.90, None),
    #     "codes": (2.45, None),
    #     "line":  (2.45, None),
    #     "dates": (2.80, None),
    #     "price": (3.75, None),
    #     "disc":  (3.75, None),
    # }


    # reveal = {
    #         "hook":  (0.00, 0.90),   # hook visible desde el inicio
    #         "pill":  (0.90, None),
    #         "main":  (1.10, None),
    #         "codes": (1.35, None),
    #         "line":  (1.35, None),
    #         "dates": (2.00, None),
    #         "price": (3.30, None),
    #         "disc":  (3.30, None),
    # }
    
    
    # hook_text = "MALLORCA → EUROPA POR <40€"
    # hook_mode = "band"
    
    for i in range(total_frames):
        t = i / fps

        # 2) Calculamos zoom factor suave y periódico
        z = zoom_center + zoom_amp * math.sin(2 * math.pi * t / duration)

        # 3) Reescalamos y recortamos al centro
        w0, h0 = base.size
        new_w, new_h = int(w0 * z), int(h0 * z)

        # Resize con LANCZOS (equivalente moderno de ANTIALIAS)
        zoomed = base.resize((new_w, new_h), Image.LANCZOS)

        # Recorte centrado a 1080x1920
        left = max(0, (new_w - WIDTH) // 2)
        top = max(0, (new_h - HEIGHT) // 2)
        right = left + WIDTH
        bottom = top + HEIGHT
        zoomed_cropped = zoomed.crop((left, top, right, bottom))
        
        # 4) Aplicamos overlay completo para este frame
        frame_pil = _compose_frame(
            zoomed_cropped,
            route_main=route_main,
            route_codes=route_codes,
            price=price,
            dates=dates,
            logo_path=logo_path,
            brand_line=brand_line,
            t=t,
            reveal=reveal,
            hook_text=hook_text,
            hook_mode=hook_mode,
            discount_pct=discount_pct,
            category_label=category_label,
            origin_pill_text=origin_pill_text,
            origin_code=origin_code,
            show_origin_pill=show_origin_pill,
        )

        # MoviePy trabaja con arrays numpy
        frame_np = np.array(frame_pil.convert("RGB"))
        frames.append(frame_np)

    # 5) Montamos el clip de secuencia de imágenes
    clip = ImageSequenceClip(frames, fps=fps)

    # 6) Exportamos el mp4
    Path(out_mp4_path).parent.mkdir(parents=True, exist_ok=True)
    clip.write_videofile(
        out_mp4_path,
        fps=fps,
        codec="libx264",
        audio=False,
        preset="medium",
        threads=4,
        bitrate="6000k",
    )
    

# ---------------------------------------------------------------------------
# Helper de más alto nivel
# ---------------------------------------------------------------------------

def create_reel_for_flight(
    flight,
    out_mp4_path: str,
    logo_path: Optional[str],
    brand_line: str = "@escapadasgo_mallorca",
    duration: float = 6.0,
    s3_bucket: Optional[str] = None,
    s3_prefix: str = "reels/",
    s3_public: bool = True,
    hook_text: Optional[str] = None,   # 👈 PASAS EL HOOK AL GENERADOR
    hook_mode: str = "band",
    origin_pill_ab_ratio: float = 0.5,
    force_origin_pill: Optional[bool] = None,
    return_origin_pill_variant: bool = False,
) -> str:
    """
    Genera el reel para un vuelo:
      - Si s3_bucket es None → devuelve la ruta local (out_mp4_path).
      - Si s3_bucket tiene valor → sube el vídeo a S3 y devuelve la URL pública.
    """
    origin = _get_field(flight, "origin", "PMI").upper()
    destination = _get_field(flight, "destination", "VIE")
    start_date = str(_get_field(flight, "start_date", ""))[:10]
    end_date = str(_get_field(flight, "end_date", ""))[:10]
    price_value = _get_field(flight, "price", 0)

    # Texto pill (profesional y corto)
    origin_pill_text = f"DESDE {origin}"

    # A/B: on/off (puedes forzarlo con force_origin_pill)
    if force_origin_pill is None:
        show_origin_pill, origin_pill_variant = choose_origin_pill_variant(origin_pill_ab_ratio)
    else:
        show_origin_pill = bool(force_origin_pill)
        origin_pill_variant = "origin_pill_on" if show_origin_pill else "origin_pill_off"

    
    discount_pct = _get_field(flight, "discount_pct", None)

    raw_cat = (
        _get_field(flight, "category_label", None)
        or _get_field(flight, "category", None)
        or _get_field(flight, "category_code", None)
    )
    if raw_cat:
        category_label = _short_category_label(raw_cat)
    else:
        category_label = None

    # --- NUEVO: ciudades + códigos ---
    origin_city = get_city(origin, include_flag=False)
    dest_city   = get_city(destination, include_flag=False)

    route_main  = f"{origin_city} – {dest_city}"              # Mallorca – Milán
    route_codes = f"{origin.upper()} ✈ {destination.upper()}"  # PMI ✈ BGY

    dates = format_dates_dd_mmm(start_date, end_date)
    price_str = f"{int(round(price_value))} € i/v"

    bg_path = pick_image_for_destination(destination) or pick_image_for_destination("DEFAULT")
    if not bg_path:
        raise FileNotFoundError(
            "No se ha encontrado ninguna imagen para el destino ni DEFAULT en media/images"
        )

    # 1) Generar el vídeo local
    create_reel_v4(
        bg_image_path=str(bg_path),
        out_mp4_path=out_mp4_path,
        route_main=route_main,
        route_codes=route_codes,
        price=price_str,
        dates=dates,
        duration=duration,
        logo_path=logo_path,
        brand_line=brand_line,
        discount_pct=discount_pct,
        category_label=category_label,
        hook_text= hook_text,   # 👈 PASAS EL HOOK AL GENERADOR
        hook_mode= hook_mode,
        origin_pill_text=origin_pill_text,
        origin_code=origin,
        show_origin_pill=show_origin_pill,
    )

    # 2) Si hay bucket de S3, subirlo y devolver la URL
    result = out_mp4_path
    if s3_bucket:
        result = upload_reel_to_s3(
            local_path=out_mp4_path,
            bucket=s3_bucket,
            prefix=s3_prefix,
            public=s3_public,
        )

    if return_origin_pill_variant:
        return result, origin_pill_variant

    return result

