"""Génère assets/pandora_badge.icns (icône macOS) depuis la même source que
tools/make_ico.py : assets/app_icon.png (1024×1024) ou assets/pandora_badge.png.

Pillow écrit l'ICNS directement (pas besoin d'iconutil) — le script tourne donc
aussi bien sur le runner macOS de GitHub Actions qu'en local sous Windows.
"""
import os
import sys

ROOT   = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ASSETS = os.path.join(ROOT, "assets")
DST    = os.path.join(ASSETS, "pandora_badge.icns")

src = os.path.join(ASSETS, "app_icon.png")
if not os.path.isfile(src):
    src = os.path.join(ASSETS, "pandora_badge.png")
if not os.path.isfile(src):
    print("ERREUR : aucun fichier source trouvé dans assets/ (app_icon.png ou pandora_badge.png)")
    sys.exit(1)

try:
    from PIL import Image
except ImportError:
    print("ERREUR : Pillow n'est pas installé. Exécuter : pip install Pillow")
    sys.exit(1)

img = Image.open(src).convert("RGBA")
side = max(img.size)
# Toile carrée (l'ICNS exige des tailles carrées) — image centrée
canvas = Image.new("RGBA", (side, side), (0, 0, 0, 0))
canvas.paste(img, ((side - img.width) // 2, (side - img.height) // 2))
canvas = canvas.resize((1024, 1024), Image.LANCZOS)

canvas.save(DST, format="ICNS",
            sizes=[(16, 16), (32, 32), (64, 64), (128, 128),
                   (256, 256), (512, 512), (1024, 1024)])
print(f"ICNS généré : {DST}")
