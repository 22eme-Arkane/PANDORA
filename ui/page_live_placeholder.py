"""
ui/page_live_placeholder.py — Placeholder générique pour les sections Live en cours
de construction (Conducteur, Casting, Accessoires, Véhicules, Séquences Mapping…).

Affiche une icône, un titre, un badge « Bientôt disponible » et une description.
Tout le texte passe par i18n (FR/EN).
"""

from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel
from PyQt6.QtCore import Qt

from ui.styles import CP
from core.i18n import translate


class LivePlaceholder(QWidget):
    """Page placeholder Live (titre + badge + description)."""

    def __init__(self, title: str, desc: str, icon: str = "◆",
                 badge: str = "Bientôt disponible"):
        super().__init__()
        self._title_fr = title
        self._desc_fr  = desc
        self._badge_fr = badge
        self.setStyleSheet(f"background:{CP['bg0']};")

        root = QVBoxLayout(self)
        root.setContentsMargins(40, 40, 40, 40)
        root.setSpacing(14)
        root.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self._icon = QLabel(icon)
        self._icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._icon.setStyleSheet(
            f"color:{CP['accent2']};font-size:46px;background:transparent;border:none;"
        )
        root.addWidget(self._icon)

        self._title = QLabel(translate(title))
        self._title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._title.setStyleSheet(
            f"color:{CP['text_primary']};font-size:20px;font-weight:800;"
            f"letter-spacing:1px;background:transparent;border:none;"
        )
        root.addWidget(self._title)

        self._badge = QLabel(translate(badge))
        self._badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._badge.setStyleSheet(
            f"color:{CP['accent2']};font-size:10px;font-weight:700;letter-spacing:2px;"
            f"background:rgba(124,107,255,0.12);border:1px solid rgba(124,107,255,0.30);"
            f"border-radius:10px;padding:5px 14px;"
        )
        root.addWidget(self._badge, 0, Qt.AlignmentFlag.AlignCenter)

        self._desc = QLabel(translate(desc))
        self._desc.setWordWrap(True)
        self._desc.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._desc.setMaximumWidth(580)
        self._desc.setStyleSheet(
            f"color:{CP['text_secondary']};font-size:12px;line-height:1.5;"
            f"background:transparent;border:none;"
        )
        root.addWidget(self._desc, 0, Qt.AlignmentFlag.AlignCenter)

    def retranslate(self):
        self._title.setText(translate(self._title_fr))
        self._badge.setText(translate(self._badge_fr))
        self._desc.setText(translate(self._desc_fr))
