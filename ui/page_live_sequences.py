"""
ui/page_live_sequences.py — Page Séquences de PANDORA | Live (PLACEHOLDER).

Équivalent de l'onglet Storyboard de Cinéma, mais pour composer des SÉQUENCES de
loops optimisées pour Resolume (enchaînements, durées, transitions, colonnes).

Cette session : placeholder léger. La structure (table de séquences, génération
par segment, export vers Resolume) sera développée ensuite.

TODO (futur) :
  - Table de séquences (chaque ligne = un segment / loop) façon storyboard
  - Choix du style VJ par segment (core/vj_styles.py)
  - Durée, transition, BPM / sync
  - Génération par segment via le Studio IA (moteurs existants)
  - Export d'une composition vers Resolume (couches × colonnes)
  - Conversion d'un projet PANDORA | Cinéma en projet Live (à faire plus tard)
"""

from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel
from PyQt6.QtCore import Qt

from ui.styles import CP
from core.i18n import translate


class PageLiveSequences(QWidget):
    """Placeholder de la future page Séquences (storyboard Live)."""

    def __init__(self):
        super().__init__()
        self.setStyleSheet(f"background:{CP['bg0']};")

        root = QVBoxLayout(self)
        root.setContentsMargins(40, 40, 40, 40)
        root.setSpacing(14)
        root.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self._icon = QLabel("▤")
        self._icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._icon.setStyleSheet(
            f"color:{CP['accent2']};font-size:48px;background:transparent;border:none;"
        )
        root.addWidget(self._icon)

        self._title = QLabel(translate("Séquences"))
        self._title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._title.setStyleSheet(
            f"color:{CP['text_primary']};font-size:20px;font-weight:800;"
            f"letter-spacing:1px;background:transparent;border:none;"
        )
        root.addWidget(self._title)

        self._badge = QLabel(translate("Bientôt disponible"))
        self._badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._badge.setStyleSheet(
            f"color:{CP['accent2']};font-size:10px;font-weight:700;letter-spacing:2px;"
            f"background:rgba(124,107,255,0.12);border:1px solid rgba(124,107,255,0.30);"
            f"border-radius:10px;padding:5px 14px;"
        )
        root.addWidget(self._badge, 0, Qt.AlignmentFlag.AlignCenter)

        self._desc = QLabel(translate(
            "Composez des enchaînements de loops optimisés pour Resolume — "
            "l'équivalent du storyboard, pensé pour le live. Choix du style par "
            "segment, durées et transitions, puis export vers votre composition. "
            "Cette partie sera développée prochainement."
        ))
        self._desc.setWordWrap(True)
        self._desc.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._desc.setMaximumWidth(560)
        self._desc.setStyleSheet(
            f"color:{CP['text_secondary']};font-size:12px;line-height:1.5;"
            f"background:transparent;border:none;"
        )
        root.addWidget(self._desc, 0, Qt.AlignmentFlag.AlignCenter)

    def retranslate(self):
        self._title.setText(translate("Séquences"))
        self._badge.setText(translate("Bientôt disponible"))
        self._desc.setText(translate(
            "Composez des enchaînements de loops optimisés pour Resolume — "
            "l'équivalent du storyboard, pensé pour le live. Choix du style par "
            "segment, durées et transitions, puis export vers votre composition. "
            "Cette partie sera développée prochainement."
        ))
