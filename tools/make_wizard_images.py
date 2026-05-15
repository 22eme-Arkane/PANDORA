"""Génère assets/wizard_large.bmp (164×314) et assets/wizard_small.bmp (55×58) pour Inno Setup.

Sources prioritaires :
  - assets/icons/wizard_large.png  → wizard_large.bmp
  - assets/icons/wizard_small.png  → wizard_small.bmp
Fallback (génération depuis app_icon.png) uniquement si les sources sont absentes.
"""
import os
import sys

ROOT   = os.path.dirname(os.path.dirname(__file__))
ASSETS = os.path.join(ROOT, "assets")

try:
    from PIL import Image
except ImportError:
    print("ERREUR : Pillow non installé. pip install Pillow")
    sys.exit(1)

BG = (7, 8, 15)  # #07080f — fond sombre PANDORA

# ── Wizard large (164×314) ────────────────────────────────────────────────────
src_large = os.path.join(ASSETS, "icons", "wizard_large.png")
dst_large = os.path.join(ASSETS, "wizard_large.bmp")

if os.path.isfile(src_large):
    img = Image.open(src_large).convert("RGB")
    img = img.resize((164, 314), Image.LANCZOS)
    img.save(dst_large, format="BMP")
    print(f"Wizard large : {dst_large}  (164×314)")
else:
    # Fallback : générer depuis app_icon.png
    src = os.path.join(ASSETS, "app_icon.png")
    if not os.path.isfile(src):
        src = os.path.join(ASSETS, "pandora_badge.png")
    if not os.path.isfile(src):
        print("ERREUR : wizard_large.png et app_icon.png introuvables")
        sys.exit(1)
    badge = Image.open(src).convert("RGBA")
    W, H = 164, 314
    canvas = Image.new("RGBA", (W, H), BG + (255,))
    logo_size = min(W - 24, 130)
    logo = badge.resize((logo_size, logo_size), Image.LANCZOS)
    x = (W - logo_size) // 2
    y = H // 2 - logo_size // 2 - 20
    canvas.paste(logo, (x, y), logo)
    out = Image.new("RGB", (W, H), BG)
    out.paste(canvas, mask=canvas.split()[3])
    out.save(dst_large, format="BMP")
    print(f"Wizard large (fallback) : {dst_large}  (164×314)")

# ── Wizard small (55×58) ─────────────────────────────────────────────────────
src_small = os.path.join(ASSETS, "icons", "wizard_small.png")
dst_small = os.path.join(ASSETS, "wizard_small.bmp")

if os.path.isfile(src_small):
    img = Image.open(src_small).convert("RGB")
    img = img.resize((55, 58), Image.LANCZOS)
    img.save(dst_small, format="BMP")
    print(f"Wizard small : {dst_small}  (55×58)")
else:
    # Fallback : générer depuis app_icon.png
    src = os.path.join(ASSETS, "app_icon.png")
    if not os.path.isfile(src):
        src = os.path.join(ASSETS, "pandora_badge.png")
    if not os.path.isfile(src):
        print("ERREUR : wizard_small.png et app_icon.png introuvables")
        sys.exit(1)
    badge = Image.open(src).convert("RGBA")
    SW, SH = 55, 58
    out = Image.new("RGB", (SW, SH), BG)
    logo_s = badge.resize((SW, SH), Image.LANCZOS)
    out.paste(logo_s, (0, 0), logo_s)
    out.save(dst_small, format="BMP")
    print(f"Wizard small (fallback) : {dst_small}  (55×58)")
