"""Conteneur à onglets de la partie Décors.

Décision Matthieu 2026-07-31 (première étape de la refonte Décors) : deux
onglets — « Standard » (la page classique, INCHANGÉE) et « Avancé »
(l'atelier de rotations multi-angles, interface dédiée au workflow plus
costaud). Le conteneur remplace PageDecors dans la navigation ; il expose
``refresh()`` pour le rafraîchissement de navigation et rafraîchit
l'onglet qui devient visible.
"""

from PyQt6.QtWidgets import QWidget, QVBoxLayout, QTabWidget

from ui.styles import CP
from core.i18n import translate
from ui.page_decors import PageDecors
from ui.page_decors_multiview import PageDecorsMultiview


class DecorsHub(QWidget):
    def __init__(self):
        super().__init__()
        self.setStyleSheet(f"background:{CP['bg0']};")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)

        self.tabs = QTabWidget()
        # Même habillage que les onglets d'AI Studio : barre centrée sur fond
        # bg0, onglets transparents, filet sous la barre (bord haut du pane).
        self.tabs.setDocumentMode(False)
        self.tabs.setStyleSheet(
            self.tabs.styleSheet()
            + f"QTabWidget::pane{{border:none;border-top:1px solid {CP['border']};}}"
            + "QTabWidget::tab-bar{alignment:center;}"
            + f"QTabBar{{background:{CP['bg0']};border:none;}}"
            + f"QTabBar::tab{{background:transparent;color:{CP['text_secondary']};}}"
            + f"QTabBar::tab:hover{{background:transparent;color:{CP['text_primary']};}}")
        self.tabs.tabBar().setExpanding(False)
        self.tabs.tabBar().setDrawBase(False)

        # « Standard » / « Avancé » (renommage Matthieu 2026-07-31) : la
        # distinction est le NIVEAU d'outillage, pas le contenu — l'onglet
        # avancé accueillera la suite de la refonte Décors.
        # Émoticônes plutôt que symboles géométriques (◻ / ⟳) : c'est la
        # convention des sections de PANDORA, celles du panneau droit du
        # Scénario en tête (🎨 références, 🎵 musique, 📖 scénario, 🎯 découpage).
        # Deux espaces après l'émoticône, comme partout ailleurs.
        #
        # ⚠ Le bâtiment U+1F3DB est « textuel par défaut » : sans le SÉLECTEUR
        # EMOJI U+FE0F, Qt affiche un carré vide (vérifié en rendu offscreen).
        # Il est donc écrit en échappement explicite — le sélecteur est un
        # caractère INVISIBLE, qu'une copie hâtive perdrait sans prévenir, et
        # le carré reviendrait. La flèche circulaire, elle, est native.
        _ICO_STD = "🏛️"   # batiment classique + selecteur emoji
        _ICO_ADV = "🔄"         # fleche circulaire (rotations)
        self.page_decors = PageDecors()
        self.page_multiview = PageDecorsMultiview()
        self.tabs.addTab(self.page_decors, _ICO_STD + "  " + translate("Standard"))
        self.tabs.addTab(self.page_multiview, _ICO_ADV + "  " + translate("Avancé"))
        lay.addWidget(self.tabs)
        # L'onglet qui DEVIENT visible se rafraîchit (les vues générées dans
        # l'atelier apparaissent en revenant sur « Décors », et inversement).
        self.tabs.currentChanged.connect(self._on_tab_changed)

    def refresh(self):
        """Appelé par la navigation (pandora_window) : onglet visible seulement
        — l'autre se rafraîchira quand il deviendra visible."""
        w = self.tabs.currentWidget()
        if hasattr(w, "refresh"):
            w.refresh()

    def _on_tab_changed(self, _i: int):
        w = self.tabs.currentWidget()
        if hasattr(w, "refresh"):
            w.refresh()
