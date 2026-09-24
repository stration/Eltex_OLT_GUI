"""Создаёт PNG-фавиконы из assets/ltp-gui.ico для frontend/public/.

Требует Pillow:
  pip install pillow
"""
from pathlib import Path
from PIL import Image

HERE = Path(__file__).resolve().parent
ASSETS = HERE.parent / "assets"
PUBLIC = HERE.parent / "frontend" / "public"

PUBLIC.mkdir(parents=True, exist_ok=True)

SRC = ASSETS / "ltp-gui.ico"
if not SRC.exists():
    raise SystemExit(f"Нет файла {SRC}. Сначала запустите make_icon.py")

img = Image.open(SRC).convert("RGBA")

# 32×32 — для современных браузеров
img.resize((32, 32), Image.LANCZOS).save(PUBLIC / "favicon-32x32.png")

# 16×16 — маленький
img.resize((16, 16), Image.LANCZOS).save(PUBLIC / "favicon-16x16.png")

# 180×180 — для apple-touch-icon (iOS)
img.resize((180, 180), Image.LANCZOS).save(PUBLIC / "apple-touch-icon.png")

# 192×192 и 512×512 — для Android / PWA
img.resize((192, 192), Image.LANCZOS).save(PUBLIC / "android-chrome-192x192.png")
img.resize((512, 512), Image.LANCZOS).save(PUBLIC / "android-chrome-512x512.png")

print(f"[OK] PNG-фавиконы сохранены в {PUBLIC}")