"""Génère les images du dépôt GitHub, à partir du logo de l'application (assets/app_icon.png) :

  - docs/readme/pandora_logo.png : le logo du README, avec PANDORA écrit dessous, même recette que
    la grande image de l'installeur (halo doré, lettres espacées, filet d'or) ;
  - docs/readme/social-preview.png : l'image de partage du dépôt, 1280 × 640 (à déposer à la main
    dans Settings → Social preview : GitHub n'a pas d'API pour cela).

Demande Matthieu du 30/10/2026. Couleurs et polices : tools/make_wizard_images.py.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from make_wizard_images import BG, GOLD, PANEL, ROOT, TEXT, _font, _spaced, large  # noqa: E402

from PIL import Image, ImageDraw, ImageFilter  # noqa: E402

OUT = os.path.join(ROOT, "docs", "readme")
MUTED = (176, 166, 146)


def _gradient(size: tuple) -> "Image.Image":
    shade = Image.linear_gradient("L").resize(size)
    return Image.composite(Image.new("RGB", size, PANEL), Image.new("RGB", size, BG), shade)


def _halo(image: "Image.Image", cx: float, cy: float, r: float, blur: float, level: int = 70) -> "Image.Image":
    glow = Image.new("L", image.size, 0)
    ImageDraw.Draw(glow).ellipse((cx - r, cy - r, cx + r, cy + r), fill=level)
    glow = glow.filter(ImageFilter.GaussianBlur(blur))
    return Image.composite(Image.new("RGB", image.size, GOLD), image, glow)


def readme_logo(logo: "Image.Image") -> "Image.Image":
    """La grande image de l'installeur, recadrée sur le logo et le nom, aux coins arrondis."""
    w, h = 800, 1530                         # même proportion que l'assistant d'installation
    full = large(logo, (w, h))
    side = round(w * 0.58)
    top = round(h * 0.40 - side / 2 - w * 0.10)
    bottom = round(h * 0.40 + side / 2 + w * 0.10 + w * 0.105 * 1.45 + w * 0.09)
    card = full.crop((0, top, w, bottom)).convert("RGBA")
    mask = Image.new("L", card.size, 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, card.width - 1, card.height - 1), radius=56, fill=255)
    card.putalpha(mask)
    return card


def social_preview(logo: "Image.Image") -> "Image.Image":
    w, h = 1280, 640
    image = _gradient((w, h))
    cx, cy = 340, h / 2
    image = _halo(image, cx, cy, 280, 110)
    side = 400
    emblem = logo.resize((side, side), Image.LANCZOS)
    image.paste(emblem, (round(cx - side / 2), round(cy - side / 2)), emblem)
    draw = ImageDraw.Draw(image)
    tx = 610
    title = _font(100)
    x = tx
    for ch in "PANDORA":
        draw.text((x, 188), ch, font=title, fill=TEXT, anchor="lt")
        x += title.getlength(ch) + 16
    draw.line((tx + 2, 322, tx + 120, 322), fill=GOLD, width=4)
    draw.text((tx, 350), "From the written page to generated, edited shots.", font=_font(27), fill=TEXT, anchor="lt")
    draw.text((tx, 396), "Free, open-source AI film studio.", font=_font(25), fill=MUTED, anchor="lt")
    draw.text((tx, 432), "Windows & macOS. Your projects stay on your disk.", font=_font(25), fill=MUTED, anchor="lt")
    return image


def main() -> None:
    logo = Image.open(os.path.join(ROOT, "assets", "app_icon.png")).convert("RGBA")
    os.makedirs(OUT, exist_ok=True)
    readme_logo(logo).save(os.path.join(OUT, "pandora_logo.png"), optimize=True)
    social_preview(logo).save(os.path.join(OUT, "social-preview.png"), optimize=True)
    print("docs/readme/pandora_logo.png  docs/readme/social-preview.png")


if __name__ == "__main__":
    main()
