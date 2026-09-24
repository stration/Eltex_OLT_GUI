"""Генерирует .ico для LTP-GUI из исходной картинки assets/logo.jpg.

Если logo.jpg отсутствует — рисует fallback (синий квадрат с буквой L).

Требует Pillow:
  .venv\\Scripts\\activate
  pip install pillow
  python make_icon.py
"""
from pathlib import Path

try:
    from PIL import Image, ImageDraw, ImageFont, ImageOps
except ImportError:
    raise SystemExit("Pillow не установлен. Запустите: pip install pillow")


HERE = Path(__file__).resolve().parent
ASSETS = HERE.parent / "assets"
ASSETS.mkdir(parents=True, exist_ok=True)

OUT = ASSETS / "ltp-gui.ico"
LOGO_CANDIDATES = [
    ASSETS / "logo.png",
    ASSETS / "logo.jpg",
    ASSETS / "logo.jpeg",
]

# Цвета — для fallback
BG = (99, 102, 241)
FG = (255, 255, 255)

# Размеры для .ico
SIZES = [(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]


def _find_logo() -> Path | None:
    for p in LOGO_CANDIDATES:
        if p.exists():
            return p
    return None


def _load_logo() -> Image.Image | None:
    """Загружает логотип и приводит к квадрату RGBA."""
    src = _find_logo()
    if src is None:
        return None
    img = Image.open(src).convert("RGBA")

    # Обрезаем до квадрата по центру
    w, h = img.size
    side = min(w, h)
    left = (w - side) // 2
    top = (h - side) // 2
    img = img.crop((left, top, left + side, top + side))
    return img


def _make_fallback() -> Image.Image:
    """Fallback: синий квадрат со скруглёнными углами + буква L."""
    size = 256
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    radius = int(size * 0.18)
    draw.rounded_rectangle(
        (0, 0, size - 1, size - 1),
        radius=radius,
        fill=BG,
        outline=(79, 82, 221),
        width=3,
    )

    font = None
    for name in (
        "C:/Windows/Fonts/arialbd.ttf",
        "C:/Windows/Fonts/segoeuib.ttf",
        "arialbd.ttf",
        "arial.ttf",
        "DejaVuSans-Bold.ttf",
    ):
        try:
            font = ImageFont.truetype(name, size=int(size * 0.66))
            break
        except Exception:
            continue
    if font is None:
        font = ImageFont.load_default()

    text = "L"
    bbox = draw.textbbox((0, 0), text, font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    tx = (size - tw) // 2 - bbox[0]
    ty = (size - th) // 2 - bbox[1]
    draw.text((tx + 3, ty + 3), text, fill=(0, 0, 0, 80), font=font)
    draw.text((tx, ty), text, fill=FG, font=font)
    return img


def main():
    logo = _load_logo()
    if logo is not None:
        print(f"[i] Использую логотип: {_find_logo()}")
        # Приводим к 256×256 (дальше Pillow сам сделает нужные размеры)
        base = logo.resize((256, 256), Image.LANCZOS)
    else:
        print("[i] Логотип не найден, использую fallback (буква L)")
        base = _make_fallback()

    base.save(OUT, format="ICO", sizes=SIZES)
    print(f"[OK] Иконка сохранена: {OUT}")


if __name__ == "__main__":
    main()