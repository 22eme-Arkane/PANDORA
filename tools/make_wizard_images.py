"""Génère les images de l'assistant d'installation (Inno Setup, style « modern dark »).

Refonte du 27/10/2026 (demande Matthieu : « un nouvel installeur plus moderne comme
celui que nous avons fait pour le projet AIODOS ») — même recette que
AIODOS/tools/installer_pages.py :

  - grande image (pages d'accueil et de fin) : le logo dans un halo doré, sur un
    noir chaud en dégradé, et le nom PANDORA aux lettres espacées dessous ;
  - petite image (en haut à droite des autres pages) : le logo seul, sur fond
    transparent.

Source : assets/app_icon.png (tools/make_logo_assets.py, le logo du 27/10/2026).
Sortie : installer/wizard-<largeur>.png et installer/small-<côté>.png (gitignorés,
régénérés à chaque build : build.ps1 étape 2 et .github/workflows/build.yml).

⚠ POURQUOI SEPT TAILLES (constat Matthieu 2026-08-30, build 2.3.0) : Inno Setup
choisit dans la liste l'image qui correspond à l'échelle de l'écran (100 à
250 %) ; avec une seule taille, il l'étirait. Ce n'était PAS la cause des cases
tronquées de la page de fin (c'était RunList.Offset, voir [Code] de
pandora_setup.iss), mais une image nette à chaque échelle reste la règle.
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ASSETS = os.path.join(ROOT, "assets")
OUT = os.path.join(ROOT, "installer")

try:
    from PIL import Image, ImageDraw, ImageFilter, ImageFont
except ImportError:
    print("ERREUR : Pillow non installe. pip install Pillow")
    sys.exit(1)

#: Grande image et petite image, de 100 à 250 % (les tailles qu'Inno Setup 6.6+
#: sait choisir) — mêmes valeurs que l'installeur d'AIODOS.
LARGE = ((202, 386), (269, 515), (336, 643), (403, 772), (430, 824), (498, 953), (534, 1022))
SMALL = (58, 77, 97, 116, 124, 143, 159)
#: Le thème « Noir & or » de PANDORA (ui/themes.py).
BG = (8, 7, 6)
PANEL = (26, 22, 16)
GOLD = (216, 173, 79)
TEXT = (242, 234, 216)
FONTS = (r"C:\Windows\Fonts\seguisb.ttf", r"C:\Windows\Fonts\segoeui.ttf",
         "/System/Library/Fonts/Supplemental/Arial.ttf")


def _font(size: int):
    for path in FONTS:
        try:
            return ImageFont.truetype(path, size)
        except OSError:
            continue
    return ImageFont.load_default(size)


def _spaced(draw, center: float, top: float, text: str, font, spacing: float):
    """Un mot aux lettres espacées, centré sur `center`."""
    widths = [font.getlength(ch) for ch in text]
    x = center - (sum(widths) + spacing * (len(text) - 1)) / 2
    for ch, width in zip(text, widths):
        draw.text((x, top), ch, font=font, fill=TEXT, anchor="lt")
        x += width + spacing


def large(logo: "Image.Image", size: tuple) -> "Image.Image":
    w, h = size
    shade = Image.linear_gradient("L").resize(size)          # noir en haut, clair en bas
    image = Image.composite(Image.new("RGB", size, PANEL), Image.new("RGB", size, BG), shade)
    cx, cy = w / 2, h * 0.40
    glow = Image.new("L", size, 0)
    r = w * 0.46
    ImageDraw.Draw(glow).ellipse((cx - r, cy - r, cx + r, cy + r), fill=70)
    glow = glow.filter(ImageFilter.GaussianBlur(w * 0.14))
    image = Image.composite(Image.new("RGB", size, GOLD), image, glow)
    side = round(w * 0.58)
    emblem = logo.resize((side, side), Image.LANCZOS)
    image.paste(emblem, (round(cx - side / 2), round(cy - side / 2)), emblem)
    draw = ImageDraw.Draw(image)
    name_top = cy + side / 2 + w * 0.10
    font = _font(round(w * 0.105))
    _spaced(draw, cx, name_top, "PANDORA", font, w * 0.022)
    # Un filet d'or sous le nom
    line_y = name_top + font.size * 1.45
    half = w * 0.09
    draw.line((cx - half, line_y, cx + half, line_y), fill=GOLD, width=max(1, round(w / 200)))
    return image


def small(logo: "Image.Image", side: int) -> "Image.Image":
    """Le logo sur fond transparent, avec une marge : à pleine taille, la tuile
    touchait le bord de la fenêtre en haut à droite."""
    inner = round(side * 0.84)
    out = Image.new("RGBA", (side, side), (0, 0, 0, 0))
    out.paste(logo.resize((inner, inner), Image.LANCZOS), ((side - inner) // 2,) * 2)
    return out


def main() -> None:
    src = os.path.join(ASSETS, "app_icon.png")
    if not os.path.isfile(src):
        print("ERREUR : assets/app_icon.png absent (python tools/make_logo_assets.py)")
        sys.exit(1)
    logo = Image.open(src).convert("RGBA")
    os.makedirs(OUT, exist_ok=True)
    # ASCII pur : build.ps1 lance ce script dans une console cp1252 et s'arrête à
    # la première erreur d'encodage.
    print("Images de l'assistant d'installation - 7 echelles")
    for size in LARGE:
        large(logo, size).save(os.path.join(OUT, f"wizard-{size[0]}.png"))
        print(f"  installer/wizard-{size[0]}.png  {size[0]}x{size[1]}")
    for side in SMALL:
        small(logo, side).save(os.path.join(OUT, f"small-{side}.png"))
        print(f"  installer/small-{side}.png  {side}x{side}")


if __name__ == "__main__":
    main()
