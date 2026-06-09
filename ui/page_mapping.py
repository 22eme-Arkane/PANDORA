"""
ui/page_mapping.py — Page Mapping de PANDORA | Live (PLACEHOLDER).

Cette page est volontairement un emplacement vide pour la session « interface ».
Le mapping vidéo proprement dit n'est PAS implémenté ici.

TODO (sessions futures — NE PAS coder maintenant) :
  - Import d'une photo du lieu (mur, scène, objet à mapper)
  - Détection automatique des zones de mapping (OpenCV + Claude Vision)
  - Édition manuelle des quads / masques de projection
  - Export vers Resolume (warping) via OSC / REST si nécessaire
  - Génération temps réel / mapping live
"""

from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel
from PyQt6.QtCore import Qt

from ui.styles import CP
from core.i18n import translate


class PageMapping(QWidget):
    """Placeholder de la future page Mapping."""

    def __init__(self):
        super().__init__()
        self.setStyleSheet(f"background:{CP['bg0']};")

        root = QVBoxLayout(self)
        root.setContentsMargins(40, 40, 40, 40)
        root.setSpacing(14)
        root.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self._icon = QLabel("◈")
        self._icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._icon.setStyleSheet(
            f"color:{CP['accent2']};font-size:48px;background:transparent;border:none;"
        )
        root.addWidget(self._icon)

        self._title = QLabel(translate("Mapping vidéo"))
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
        _wrap = QVBoxLayout()
        _wrap.setAlignment(Qt.AlignmentFlag.AlignCenter)
        root.addWidget(self._badge, 0, Qt.AlignmentFlag.AlignCenter)

        self._desc = QLabel(translate(
            "Le mapping assistera la préparation de vos projections : import d'une "
            "photo du lieu, détection automatique des zones, puis export vers votre "
            "logiciel de mapping. Cette partie sera développée prochainement."
        ))
        self._desc.setWordWrap(True)
        self._desc.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._desc.setMaximumWidth(520)
        self._desc.setStyleSheet(
            f"color:{CP['text_secondary']};font-size:12px;line-height:1.5;"
            f"background:transparent;border:none;"
        )
        root.addWidget(self._desc, 0, Qt.AlignmentFlag.AlignCenter)

    def retranslate(self):
        self._title.setText(translate("Mapping vidéo"))
        self._badge.setText(translate("Bientôt disponible"))
        self._desc.setText(translate(
            "Le mapping assistera la préparation de vos projections : import d'une "
            "photo du lieu, détection automatique des zones, puis export vers votre "
            "logiciel de mapping. Cette partie sera développée prochainement."
        ))
