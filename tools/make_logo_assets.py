"""Génère les icônes de PANDORA depuis le logo source (docs/logo/).

Nouveau logo (27/10/2026) : cerveau mi-organique blanc / mi-circuit doré sur une
tuile noire aux coins arrondis, livré en 2000×1116 sur fond noir. On découpe la
tuile, on rend ses coins TRANSPARENTS (masque anticrénelé), puis on écrit :

  assets/app_icon.png          1024 px — source haute définition (make_icns.py)
  assets/pandora_badge.png      512 px — badge_pixmap()
  assets/icons/app icon.png     256 px
  assets/icons/pandora_icone.ico + assets/pandora_badge.ico — 16 à 256 px

Usage : python tools/make_logo_assets.py [chemin/du/logo]
"""
import os
import sys

from PIL import Image, ImageDraw

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ASSETS = os.path.join(ROOT, "assets")
SOURCE = os.path.join(ROOT, "docs", "logo", "pandora_logo_2026-10.webp")
#: La tuile dans l'image source (mesurée : 597-1402 × 155-960, rayon ≈ 182 px),
#: rognée d'un pixel pour ne pas garder le liseré du fond noir.
TILE_BOX = (598, 156, 1402, 960)
RADIUS = 180
ICO_SIZES = [16, 20, 24, 32, 40, 48, 64, 96, 128, 256]


def tile(src_path: str = SOURCE) -> Image.Image:
    im = Image.open(src_path).convert("RGB").crop(TILE_BOX)
    w, h = im.size
    k = 4                                            # masque suréchantillonné ×4
    mask = Image.new("L", (w * k, h * k), 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, w * k - 1, h * k - 1),
                                           radius=RADIUS * k, fill=255)
    out = im.convert("RGBA")
    out.putalpha(mask.resize((w, h), Image.LANCZOS))
    return out


def main(src_path: str = SOURCE):
    logo = tile(src_path)

    def sized(s):
        return logo.resize((s, s), Image.LANCZOS)

    sized(1024).save(os.path.join(ASSETS, "app_icon.png"))
    sized(512).save(os.path.join(ASSETS, "pandora_badge.png"))
    sized(256).save(os.path.join(ASSETS, "icons", "app icon.png"))
    frames = [sized(s) for s in ICO_SIZES]
    for dst in (os.path.join(ASSETS, "icons", "pandora_icone.ico"),
                os.path.join(ASSETS, "pandora_badge.ico")):
        frames[-1].save(dst, format="ICO", sizes=[(s, s) for s in ICO_SIZES],
                        append_images=frames[:-1])
    print(f"Logo {logo.size} -> app_icon 1024, badge 512, app icon 256, "
          f"ICO {ICO_SIZES}")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else SOURCE)
