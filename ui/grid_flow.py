"""Nombre de colonnes d'une grille de vignettes, calculé sur la largeur RÉELLE.

Les pages d'éléments (Castings, Décors, Accessoires, HMC, Véhicules) posaient
leurs cartes sur un nombre de colonnes ÉCRIT EN DUR — 6 ici, 9 là. Deux défauts
en découlaient, constatés par Matthieu le 2026-07-31 :

  · sur un écran large, la grille sautait la ligne trop tôt et laissait un tiers
    d'espace vide à droite ;
  · sur une fenêtre plus étroite — ou dès que le panneau FICHE s'ouvrait et
    mangeait 400 px — les vignettes débordaient et se retrouvaient ROGNÉES,
    en-tête de section compris. Rien ne se re-disposait, puisque le nombre de
    colonnes ne dépendait de rien.

Ce module ne fait qu'une chose : dire combien de cartes tiennent vraiment. Les
pages l'appellent avec la largeur de leur zone d'affichage et se re-rendent
quand ce nombre CHANGE — jamais à chaque pixel de redimensionnement.
"""

from __future__ import annotations

#: Gabarit commun des cartes d'élément (voir `_W` dans les pages).
CARD_W = 162
SPACING = 18


def columns_for(available_px: int, card_w: int = CARD_W, spacing: int = SPACING,
                minimum: int = 1, maximum: int = 14) -> int:
    """Combien de cartes de `card_w` tiennent dans `available_px`.

    N cartes occupent N×card_w + (N−1)×spacing. On résout pour le plus grand N
    qui tient, borné à `minimum` (une carte rognée vaut mieux qu'aucune ligne)
    et à `maximum` (au-delà, les vignettes deviennent illisibles sur un écran
    très large).
    """
    try:
        w = int(available_px)
    except Exception:
        return minimum
    if w <= 0:                      # widget pas encore posé : on ne devine pas
        return maximum              # (le premier resize corrigera)
    _step = max(1, int(card_w) + int(spacing))
    n = (w + int(spacing)) // _step
    return max(minimum, min(int(maximum), int(n)))


#: Nom de la section qui accueille les éléments sans catégorie renseignée.
SANS_CATEGORIE = "Sans catégorie"


def group_by_category(items: list, key: str = "category",
                      fallback: str = SANS_CATEGORIE) -> list:
    """[(catégorie, éléments)] — ordre alphabétique, sans-catégorie en dernier.

    Les pages Accessoires, HMC et Véhicules affichaient une seule grille où
    « Armes », « Mobilier » et « Autre… » se suivaient au hasard de l'ordre de
    création. La catégorie était pourtant écrite sous chaque vignette : elle
    devient le rangement (demande Matthieu 2026-07-31).

    Les libellés vides, « Autre… » compris, tombent dans la même section — trois
    variantes d'écriture ne doivent pas faire trois sections.
    """
    buckets: dict = {}
    for it in (items or []):
        _c = ((it or {}).get(key) or "").strip()
        if not _c or _c.lower().rstrip("…. ") in ("autre", "autres"):
            _c = fallback
        buckets.setdefault(_c, []).append(it)
    _nommees = sorted((c for c in buckets if c != fallback), key=str.casefold)
    out = [(c, buckets[c]) for c in _nommees]
    if fallback in buckets:
        out.append((fallback, buckets[fallback]))
    return out


def watch_viewport(scroll, page) -> None:
    """Re-dispose la grille de `page` quand la ZONE D'AFFICHAGE de `scroll` change.

    Constaté par Matthieu le 29/10/2026 sur la 2.7.0 (panneau FICHE ouvert par
    défaut) : Décors, Castings… restaient sur 3 colonnes avec deux tiers d'écran
    vides. La grille était posée sur la largeur de départ du viewport (640 px) et
    la page ne se re-disposait que sur SON redimensionnement — qui arrive AVANT
    celui de sa zone de défilement (d'où une largeur périmée), et jamais quand on
    ouvre ou ferme la FICHE. On écoute donc le viewport lui-même ; la page
    recalcule comme sur un redimensionnement (son resizeEvent ne re-pose les
    cartes que si le nombre de colonnes change)."""
    from PyQt6.QtCore import QEvent, QObject, QTimer
    from PyQt6.QtGui import QResizeEvent

    class _Watch(QObject):
        def __init__(self):
            super().__init__(page)
            self._timer = QTimer(self)
            self._timer.setSingleShot(True)
            self._timer.setInterval(0)          # regroupe les rafales d'un redimensionnement
            self._timer.timeout.connect(self._fire)

        def eventFilter(self, obj, ev):     # noqa: N802
            if ev.type() == QEvent.Type.Resize:
                self._timer.start()
            return False

        def _fire(self):
            try:
                page.resizeEvent(QResizeEvent(page.size(), page.size()))
            except Exception:
                pass

    w = _Watch()
    scroll.viewport().installEventFilter(w)
    page._viewport_watch = w      # gardé en vie avec la page


class ColumnsWatcher:
    """Mémorise le dernier nombre de colonnes rendu.

    Sert à ne re-poser les cartes que lorsque la largeur change ASSEZ pour
    gagner ou perdre une colonne : un redimensionnement continu déclencherait
    sinon des dizaines de reconstructions de grille.
    """

    __slots__ = ("_last",)

    def __init__(self):
        self._last = -1

    def changed(self, cols: int) -> bool:
        if int(cols) == self._last:
            return False
        self._last = int(cols)
        return True

    def reset(self) -> None:
        self._last = -1
