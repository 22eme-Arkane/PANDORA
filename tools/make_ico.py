"""Génère assets/pandora_badge.ico depuis assets/pandora_badge.png (ou app_icon.png)."""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(__file__))
ASSETS = os.path.join(ROOT, "assets")

src = os.path.join(ASSETS, "pandora_badge.png")
if not os.path.isfile(src):
    src = os.path.join(ASSETS, "app_icon.png")
if not os.path.isfile(src):
    print("ERREUR : aucun fichier source trouvé dans assets/ (pandora_badge.png ou app_icon.png)")
    sys.exit(1)

try:
    from PIL import Image
except ImportError:
    print("ERREUR : Pillow n'est pas installé. Exécuter : pip install Pillow")
    sys.exit(1)

img = Image.open(src).convert("RGBA")
sizes = [16, 24, 32, 48, 64, 128, 256]
frames = [img.resize((s, s), Image.LANCZOS) for s in sizes]

dst = os.path.join(ASSETS, "pandora_badge.ico")
frames[0].save(dst, format="ICO", sizes=[(s, s) for s in sizes], append_images=frames[1:])
print(f"ICO généré : {dst}")
