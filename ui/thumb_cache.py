"""Vignettes de cartes mises en cache — au format d'affichage, pas au format source.

Les cartes d'élément (Castings, Décors, Accessoires, HMC, Véhicules) chargeaient
leur image ainsi, à CHAQUE construction :

    QPixmapCache.remove(chemin)          # on vide le cache…
    pix = QPixmap(chemin).scaled(162, 190, …)

C'est-à-dire : décoder le fichier ENTIER — les fiches de personnage font
2160×3840 — puis le réduire à 162 px de large, et recommencer au prochain
affichage de la page. Vingt personnages, c'était vingt décodages de pleine
résolution chaque fois qu'on ouvrait l'onglet ; les Décors montaient à 845 ms
et le Casting à 392 ms (audit de lenteur du 2026-07-31, demandé par Matthieu :
« quand je clique sur un onglet, le temps d'ouverture est long »).

Ici, on garde le pixmap DÉJÀ réduit, sous une clé qui porte la DATE DE
MODIFICATION du fichier. C'est ce qui permet de supprimer le `remove()` :
une image régénérée a une date neuve, donc une clé neuve, donc elle est
rechargée — sans qu'on ait à vider quoi que ce soit à l'aveugle.
"""

from __future__ import annotations

import os

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPixmap, QPixmapCache


def _key(path: str, w: int, h: int, mode: str) -> str:
    try:
        _mtime = os.path.getmtime(path)
    except OSError:
        _mtime = 0
    return f"{path}|{w}x{h}|{mode}|{_mtime}"


def card_pixmap(path: str, w: int, h: int, *, cover: bool = True) -> QPixmap | None:
    """Vignette `w×h` prête à poser, ou None si le fichier est illisible.

    `cover=True` remplit le cadre et recadre au centre (comportement des cartes) ;
    `cover=False` tient dans le cadre en conservant le ratio.
    """
    if not path or not os.path.isfile(path):
        return None
    _k = _key(path, w, h, "cover" if cover else "fit")
    _cached = QPixmapCache.find(_k)
    if _cached is not None and not _cached.isNull():
        return _cached

    # Décodage RÉDUIT : on demande au lecteur d'image de sortir directement
    # une image proche de la taille voulue, au lieu de développer 2160×3840
    # pixels pour n'en garder que 162×190. La page Décors le faisait déjà —
    # c'est cette bonne pratique qui est généralisée ici.
    from PyQt6.QtCore import QSize
    from PyQt6.QtGui import QImageReader
    src = QPixmap()
    try:
        _r = QImageReader(path)
        _r.setAutoTransform(True)
        _s = _r.size()
        if _s.isValid() and _s.width() and _s.height():
            _f = max(w / _s.width(), h / _s.height())
            if _f < 1.0:                      # jamais AGRANDIR à la lecture
                _r.setScaledSize(QSize(max(1, round(_s.width() * _f)),
                                       max(1, round(_s.height() * _f))))
        _img = _r.read()
        if not _img.isNull():
            src = QPixmap.fromImage(_img)
    except Exception:
        src = QPixmap()
    if src.isNull():
        src = QPixmap(path)                   # repli : lecture directe
    if src.isNull():
        return None
    if cover:
        pix = src.scaled(w, h, Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                         Qt.TransformationMode.SmoothTransformation)
        pix = pix.copy(max(0, (pix.width() - w) // 2),
                       max(0, (pix.height() - h) // 2), w, h)
    else:
        pix = src.scaled(w, h, Qt.AspectRatioMode.KeepAspectRatio,
                         Qt.TransformationMode.SmoothTransformation)
    QPixmapCache.insert(_k, pix)
    return pix


def ensure_cache_size(mb: int = 96) -> None:
    """Le cache Qt par défaut (~10 Mo) ne tient pas un casting entier en
    vignettes : il évincerait les premières cartes pendant qu'on pose les
    dernières, et chaque ouverture d'onglet redeviendrait un rechargement."""
    try:
        if QPixmapCache.cacheLimit() < mb * 1024:
            QPixmapCache.setCacheLimit(mb * 1024)
    except Exception:
        pass
