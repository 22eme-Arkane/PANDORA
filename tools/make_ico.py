"""Génère assets/pandora_badge.ico depuis assets/pandora_badge.png (ou app_icon.png)."""
import os
import sys

ROOT   = os.path.dirname(os.path.dirname(__file__))
ASSETS = os.path.join(ROOT, "assets")

# app_icon.png (1024×1024) est la source haute résolution préférée
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

# Toutes les tailles standard Windows + haute densité
sizes = [16, 20, 24, 32, 40, 48, 64, 96, 128, 256]

# Pillow ICO : passer les images pré-redimensionnées comme liste
# La première doit être la plus grande (256) pour que Windows l'utilise en priorité
frames = [img.resize((s, s), Image.LANCZOS) for s in sizes]

dst = os.path.join(ASSETS, "pandora_badge.ico")

# Sauvegarder : frame[0] = 16px, puis toutes les autres en append
# sizes= doit lister exactement les mêmes dimensions que les frames
frames[0].save(
    dst,
    format="ICO",
    sizes=[(s, s) for s in sizes],
    append_images=frames[1:],
)
print(f"ICO généré : {dst}  ({len(sizes)} tailles : {sizes})")
