"""
core/image_resolution.py — Définition des images générées, au ratio EXACT.

Pourquoi ce module (2026-07-27, constat de Matthieu) : les tailles cibles vivaient
dans une table figée, `core.image_engines._AR_TARGETS`, héritée des « buckets »
d'entraînement SDXL :

    "16:9": (1344, 768)   →  1344/768 = 1,7500
    "4:3":  (1152, 896)   →  1,2857  au lieu de 1,3333
    "21:9": (1536, 640)   →  2,4000  au lieu de 2,3333

Ces tailles sont choisies pour la diffusion, pas pour la géométrie : SEUL le 1:1 y
est juste. Toute image générée par PANDORA était donc légèrement étirée.

Ça n'a rien d'anecdotique. Un Mood mesuré à 1360×776 (ratio 1,7526) sert d'image
de départ à une génération vidéo demandée en 16:9 (1,7778) : le moteur étire de
1,4 %, et la façade du bâtiment ne se superpose plus à la vraie. C'est le
recalage image par image sous After Effects.

Ce module calcule au lieu de tabuler. Trois garanties :

  ① le ratio est EXACT — 1920/1080 vaut 16/9 au bit près, pas « à peu près » ;
  ② les deux côtés sont des multiples de 8, ce qu'exigent tous les VAE de
    diffusion (un côté non aligné est arrondi par le moteur… ce qui casserait
    précisément le ratio qu'on vient de garantir) ;
  ③ la surface reste proche de la définition demandée, donc le prix et le temps
    de génération restent prévisibles.

Défaut : **1920×1080** (décision Matthieu). Le 4K reste accessible au cas par cas
via le sélecteur, mais il coûte nettement plus cher sur la plupart des moteurs.
"""

from __future__ import annotations

import math
import re

# ── Le catalogue proposé à l'utilisateur ──────────────────────────────────────
# La hauteur de référence est celle du 16:9 ; les autres ratios reçoivent la
# surface ÉQUIVALENTE, pas la même hauteur. Sans quoi un portrait 9:16 en
# « 1080 » ne ferait que 607×1080 — quatre fois moins de pixels qu'un paysage,
# pour une ligne de menu qui promet la même chose.
RESOLUTIONS = (
    ("720p",  "1280 × 720  ·  HD"),
    ("1080p", "1920 × 1080  ·  Full HD"),
    ("1440p", "2560 × 1440  ·  QHD"),
    ("4k",    "3840 × 2160  ·  4K UHD"),
)

DEFAULT_KEY = "1080p"

# Surface de référence de chaque palier, en pixels (celle du 16:9 correspondant).
_PIXELS = {
    "720p":  1280 * 720,
    "1080p": 1920 * 1080,
    "1440p": 2560 * 1440,
    "4k":    3840 * 2160,
}

# Alignement exigé par les VAE de diffusion. 8 et non 16 : c'est le plus petit
# qui passe partout, et plus il est grand, plus il éloigne du ratio exact.
_ALIGN = 8

_RATIO_RE = re.compile(r"^\s*(\d+)\s*[:xX×/]\s*(\d+)\s*$")


def normalize_key(key: str) -> str:
    """Clé de définition valide, `DEFAULT_KEY` sinon. Ne lève jamais."""
    k = (key or "").strip().lower()
    return k if k in _PIXELS else DEFAULT_KEY


def label_for(key: str) -> str:
    """Libellé affichable d'une clé de définition."""
    k = normalize_key(key)
    return next((lbl for _k, lbl in RESOLUTIONS if _k == k), k)


def parse_ratio(aspect_ratio: str) -> tuple:
    """« 16:9 » → (16, 9), réduit. (1, 1) si illisible — jamais d'exception."""
    m = _RATIO_RE.match(aspect_ratio or "")
    if not m:
        return (1, 1)
    w, h = int(m.group(1)), int(m.group(2))
    if w <= 0 or h <= 0:
        return (1, 1)
    d = math.gcd(w, h)
    return (w // d, h // d)


def _base_unit(w0: int, h0: int) -> tuple:
    """Plus petit (w, h) au ratio EXACT dont les deux côtés sont multiples de 8.

    Cherché plutôt que calculé par formule : le multiplicateur dépend des
    facteurs 2 déjà présents dans le ratio (16:9 demande 8, 4:3 demande 8, mais
    8:5 se contente de 1). Une boucle bornée est ici plus sûre qu'une astuce.
    """
    for m in range(1, _ALIGN + 1):
        if (w0 * m) % _ALIGN == 0 and (h0 * m) % _ALIGN == 0:
            return (w0 * m, h0 * m)
    return (w0 * _ALIGN, h0 * _ALIGN)


def target_for(aspect_ratio: str = "16:9", key: str = DEFAULT_KEY,
               max_pixels: int = 0) -> tuple:
    """(largeur, hauteur) au ratio EXACT, à la définition demandée.

    `max_pixels` borne la surface pour un moteur qui plafonne : on redescend au
    multiple inférieur du motif de base, donc le ratio reste exact — jamais un
    recadrage, jamais un étirement.
    """
    w0, h0 = parse_ratio(aspect_ratio)
    bw, bh = _base_unit(w0, h0)
    want = _PIXELS[normalize_key(key)]
    if max_pixels and max_pixels > 0:
        want = min(want, max_pixels)
    k = max(1, round(math.sqrt(want / float(bw * bh))))
    if max_pixels and max_pixels > 0:
        while k > 1 and (bw * k) * (bh * k) > max_pixels:
            k -= 1
    return (bw * k, bh * k)


# ── Traduction vers les moteurs qui ne prennent pas de dimensions ─────────────
# Nano Banana 2 / Pro couplent `aspect_ratio` + `resolution` (enum). Ce chemin
# donne déjà des ratios exacts — c'est le seul du catalogue à ne pas avoir besoin
# du calcul ci-dessus. On lui traduit donc le palier, en arrondissant vers le
# HAUT : mieux vaut 2048×1152 que 1024×576 quand l'utilisateur a demandé 1080p.
_NANO_ENUM = {"720p": "1K", "1080p": "2K", "1440p": "2K", "4k": "4K"}


def nano_enum(key: str = DEFAULT_KEY) -> str:
    """Palier PANDORA → enum `resolution` des Nano Banana (1K / 2K / 4K)."""
    return _NANO_ENUM[normalize_key(key)]


def describe(aspect_ratio: str = "16:9", key: str = DEFAULT_KEY,
             max_pixels: int = 0) -> str:
    """« 1920 × 1080 » — ce qui sera RÉELLEMENT demandé au moteur.

    À afficher à côté du sélecteur : un moteur bridé ne rend pas ce que le menu
    annonce, et le silence là-dessus se paie en incompréhension.
    """
    w, h = target_for(aspect_ratio, key, max_pixels)
    return f"{w} × {h}"
