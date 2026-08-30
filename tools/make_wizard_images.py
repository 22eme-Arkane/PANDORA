"""Génère les images de l'assistant d'installation Inno Setup, à TOUTES les échelles.

Sources prioritaires :
  - assets/icons/wizard_large.png  → wizard_large*.bmp
  - assets/icons/wizard_small.png  → wizard_small*.bmp
Repli (génération depuis app_icon.png) uniquement si les sources sont absentes.

⚠ POURQUOI PLUSIEURS TAILLES (constat Matthieu 2026-08-30, build 2.3.0)
Sur la page de fin de l'installeur, les cases à cocher apparaissaient tronquées.
Le projet ne fournissait qu'une seule image, à l'échelle 100 % (164×314), alors
que Windows tourne couramment à 125 % ou 150 % : Inno devait étirer l'image et
la mise en page se calculait sur une échelle qui n'était pas celle de l'écran.

Inno Setup accepte une LISTE d'images séparées par des virgules et choisit
celle qui correspond au facteur d'échelle courant. On produit donc les quatre
échelles usuelles — 100, 125, 150 et 200 % — dérivées de la taille de base.
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

#: Échelles produites. La clé est le suffixe de fichier ; « » = l'image de base,
#: celle que `WizardImageFile` cite en premier.
SCALES = (("", 1.0), ("_125", 1.25), ("_150", 1.5), ("_200", 2.0))

BASE_LARGE = (164, 314)
BASE_SMALL = (55, 58)


def _sizes(base: tuple[int, int]) -> list[tuple[str, tuple[int, int]]]:
    return [(suf, (round(base[0] * f), round(base[1] * f))) for suf, f in SCALES]


def _from_source(src: str, base: tuple[int, int], stem: str) -> bool:
    """Décline une source PNG à toutes les échelles. Faux si la source manque."""
    if not os.path.isfile(src):
        return False
    img = Image.open(src).convert("RGB")
    for suf, size in _sizes(base):
        dst = os.path.join(ASSETS, f"{stem}{suf}.bmp")
        # On repart TOUJOURS de la source pleine résolution : agrandir la
        # version 100 % donnerait une image molle aux échelles hautes.
        img.resize(size, Image.LANCZOS).save(dst, format="BMP")
        print(f"  {stem}{suf}.bmp  {size[0]}x{size[1]}")
    return True


def _badge() -> "Image.Image":
    for name in ("app_icon.png", "pandora_badge.png"):
        p = os.path.join(ASSETS, name)
        if os.path.isfile(p):
            return Image.open(p).convert("RGBA")
    print("ERREUR : ni wizard_*.png ni app_icon.png/pandora_badge.png")
    sys.exit(1)


def _fallback_large(stem: str, base: tuple[int, int]) -> None:
    badge = _badge()
    for suf, (W, H) in _sizes(base):
        canvas = Image.new("RGBA", (W, H), BG + (255,))
        logo_size = min(W - round(24 * W / base[0]), round(130 * W / base[0]))
        logo = badge.resize((logo_size, logo_size), Image.LANCZOS)
        canvas.paste(logo, ((W - logo_size) // 2,
                            H // 2 - logo_size // 2 - round(20 * H / base[1])), logo)
        out = Image.new("RGB", (W, H), BG)
        out.paste(canvas, mask=canvas.split()[3])
        out.save(os.path.join(ASSETS, f"{stem}{suf}.bmp"), format="BMP")
        print(f"  {stem}{suf}.bmp  {W}x{H}  [repli]")


def _fallback_small(stem: str, base: tuple[int, int]) -> None:
    badge = _badge()
    for suf, (W, H) in _sizes(base):
        out = Image.new("RGB", (W, H), BG)
        logo = badge.resize((W, H), Image.LANCZOS)
        out.paste(logo, (0, 0), logo)
        out.save(os.path.join(ASSETS, f"{stem}{suf}.bmp"), format="BMP")
        print(f"  {stem}{suf}.bmp  {W}x{H}  [repli]")


# ASCII pur : build.ps1 lance ce script dans une console cp1252 et s'arrête à
# la première erreur. Un simple caractère de filet (U+2500) suffit à tuer le
# build sur un UnicodeEncodeError.
print("Images de l'assistant d'installation - 4 echelles")
if not _from_source(os.path.join(ASSETS, "icons", "wizard_large.png"),
                    BASE_LARGE, "wizard_large"):
    _fallback_large("wizard_large", BASE_LARGE)

if not _from_source(os.path.join(ASSETS, "icons", "wizard_small.png"),
                    BASE_SMALL, "wizard_small"):
    _fallback_small("wizard_small", BASE_SMALL)
