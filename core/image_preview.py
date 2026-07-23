"""Apercus legers generes en processus interne pour les grilles PANDORA.

Les images de generation peuvent peser plusieurs megaoctets. Les decoder toutes
au premier affichage d'une page donne l'impression que plusieurs fenetres se
succedent. Les apercus sont donc prepares dans le worker de generation, avant
que le bouton de navigation soit rendu disponible.
"""
from __future__ import annotations

import os


def make_preview(source_path: str, suffix: str = "preview",
                 max_size: tuple[int, int] = (512, 512)) -> str:
    """Cree un JPEG leger a cote de *source_path* et renvoie son chemin.

    Tout se fait avec Pillow dans le processus PANDORA : aucun programme externe
    ni aucune fenetre systeme n'est lance. Une erreur de preview ne doit jamais
    invalider l'image originale, donc une chaine vide est renvoyee en repli.
    """
    if not source_path or not os.path.isfile(source_path):
        return ""
    root, _ext = os.path.splitext(source_path)
    preview_path = f"{root}_{suffix}.jpg"
    try:
        from PIL import Image, ImageOps

        with Image.open(source_path) as src:
            image = ImageOps.exif_transpose(src).convert("RGB")
            image.thumbnail(max_size, Image.Resampling.LANCZOS)
            image.save(preview_path, "JPEG", quality=84, optimize=True)
        return preview_path
    except Exception:
        try:
            if os.path.isfile(preview_path):
                os.remove(preview_path)
        except OSError:
            pass
        return ""
