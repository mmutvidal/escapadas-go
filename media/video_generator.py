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

    # 3) Texto
    text_x = x0 + padding_x
    text_y = y0 + padding_y
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
    route_main: str,              # Mallorca – Milán
    route_codes: str,             # PMI ✈ BGY
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
    - banda central con:
        línea 1: ciudades (Mallorca – Milán)
        línea 2: códigos IATA (PMI ✈ BGY)
        fechas
        precio
        descuento debajo
    - píldora de categoría con sombra, solapando la tarjeta
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
    # PÍLDORA DE CATEGORÍA (con sombra, solapando la tarjeta)
    # ============================================================
    if category_label:
        cat_text = category_label.upper()
        pill_font = _font(28)

        pill_center_x = center_x
        pill_center_y = card_y0 - 14   # solapa ligeramente la tarjeta

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
    
    # ------------------------------------------------------------------
    # Ahora dibujamos usando esos gaps: el bottom queda implícito y
    # automáticamente simétrico gracias al reparto de pesos.
    # ------------------------------------------------------------------
    y = card_y0 + int(round(top_gap))

    # 1) Ciudades
    h_used = _draw_centered_text(
        draw,
        route_main_text,
        route_main_font,
        center_x,
        int(y),
        COLORS["white"],
    )
    y += h_used + gap_route_main_codes

    # 2) Códigos IATA
    h_used = _draw_centered_text(
        draw,
        route_codes_text,
        route_codes_font,
        center_x,
        int(y),
        COLORS["dates"],
    )
    y += h_used + gap_codes_line

    
    # 3) Línea separadora con degradado suave
    line_margin_x = 140
    line_y = y

    _draw_horizontal_fade_line(
        base_img=frame,
        x0=card_x0 + line_margin_x,
        x1=card_x1 - line_margin_x,
        y=line_y,
        color=(255, 255, 255),
        max_alpha=90,
        width=3,
    )

    y = line_y + gap_line_dates
    

    # 4) Fechas
    h_used = _draw_centered_text(
        draw,
        dates_text,
        dates_font,
        center_x,
        int(y),
        COLORS["dates"],
    )
    y += h_used + gap_dates_price

    # 5) Precio
    h_used = _draw_centered_text(
        draw,
        price_text,
        price_font,
        center_x,
        int(y),
        COLORS["price"],
    )
    y += h_used

    # 6) Descuento (si procede)
    if show_discount and discount_font:
        y += gap_price_discount
        _draw_centered_text(
            draw,
            discount_text,
            discount_font,
            center_x,
            int(y),
            COLORS["red"],
        )

    # ============================================================
    # BRAND LINE ABAJO
    # ============================================================
    if brand_line:
        brand_font = _font(46)
        _, h_brand = _measure_text(brand_font, brand_line)
        brand_y = HEIGHT - SAFE_AREA - h_brand - 90
        _draw_centered_text(draw, brand_line, brand_font, center_x, brand_y, COLORS["brand"])

    return frame


    

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
            discount_pct=discount_pct,
            category_label=category_label,
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
    duration: float = 4.0,
) -> str:
    origin = _get_field(flight, "origin", "PMI")
    destination = _get_field(flight, "destination", "VIE")
    start_date = str(_get_field(flight, "start_date", ""))[:10]
    end_date = str(_get_field(flight, "end_date", ""))[:10]
    price_value = _get_field(flight, "price", 0)

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

    route_main  = f"{origin_city} – {dest_city}"           # Mallorca – Milán
    route_codes = f"{origin.upper()} ✈ {destination.upper()}"  # PMI ✈ BGY

    dates = format_dates_dd_mmm(start_date, end_date)
    price_str = f"{int(round(price_value))} € i/v"

    bg_path = pick_image_for_destination(destination) or pick_image_for_destination("DEFAULT")
    if not bg_path:
        raise FileNotFoundError(
            "No se ha encontrado ninguna imagen para el destino ni DEFAULT en media/images"
        )

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
    )

    return out_mp4_path

