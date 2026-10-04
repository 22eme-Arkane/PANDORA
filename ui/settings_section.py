"""
ui/settings_section.py — Section REPLIABLE des pages Paramètres (Cinéma et Live).

Demande Matthieu du 04/10/2026 : « c'est devenu le bazar… des menus déroulants
pour chaque partie ». Chaque partie devient une carte à en-tête cliquable :
flèche, titre, et un résumé de l'état à droite (« fal.ai ✓ · Claude ✓ »)
qui dit l'essentiel sans avoir à déplier.

L'état ouvert / fermé est retenu pour la SESSION, pas dans la config : la page
s'enregistre déjà à chaque frappe, et un clic d'affichage n'a rien à y écrire.

⚠ Le titre n'est jamais réécrit au repli (la flèche est un libellé à part) :
CollapsibleSection réécrivait son libellé à chaque bascule et perdait la
traduction (mémoire « casting principaux / figuration »).
"""
from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from core.i18n import translate
from ui.styles import CP

#: Mémoire de session de l'état des sections, partagée entre les deux éditions.
_OPEN: dict[str, bool] = {}


class SettingsSection(QFrame):
    """Carte repliable : `body` est le QVBoxLayout où ranger le contenu."""

    def __init__(self, title: str, summary: str = "", opened: bool = False,
                 key: str = "", parent=None):
        super().__init__(parent)
        self._key = key or title
        self.setObjectName("settingsSection")
        # Sélecteur par NOM : un style « QFrame{…} » s'appliquerait à tous les
        # QFrame enfants (panneau DaVinci, rangées…).
        self.setStyleSheet(
            f"QFrame#settingsSection{{background:{CP['bg1']};"
            f"border:1px solid {CP['border']};border-radius:10px;}}")
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        self._header = QPushButton()
        self._header.setObjectName("settingsSectionHeader")
        self._header.setCursor(Qt.CursorShape.PointingHandCursor)
        self._header.setFixedHeight(48)
        self._header.setStyleSheet(
            "QPushButton#settingsSectionHeader{background:transparent;border:none;"
            "text-align:left;padding:0;}"
            f"QPushButton#settingsSectionHeader:hover{{background:{CP['bg2']};"
            "border-radius:10px;}")
        hl = QHBoxLayout(self._header)
        hl.setContentsMargins(16, 0, 16, 0)
        hl.setSpacing(10)
        self._arrow = QLabel()
        self._arrow.setFixedWidth(14)
        self._title = QLabel(translate(title).upper())
        self._summary = QLabel("")
        self._summary.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        for lbl in (self._arrow, self._title, self._summary):
            # Les clics traversent les libellés jusqu'au bouton d'en-tête.
            lbl.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self._arrow.setStyleSheet(
            f"color:{CP['accent']};font-size:10px;background:transparent;border:none;")
        self._title.setStyleSheet(
            f"color:{CP['accent']};font-size:10px;font-weight:700;letter-spacing:3px;"
            f"font-family:'Consolas',monospace;background:transparent;border:none;")
        self._summary.setStyleSheet(
            f"color:{CP['text_dim']};font-size:10px;background:transparent;border:none;")
        hl.addWidget(self._arrow)
        hl.addWidget(self._title)
        hl.addStretch(1)
        hl.addWidget(self._summary)
        self._header.clicked.connect(self.toggle)
        outer.addWidget(self._header)

        self._body_w = QWidget()
        self._body_w.setStyleSheet("background:transparent;")
        self.body = QVBoxLayout(self._body_w)
        self.body.setContentsMargins(18, 4, 18, 18)
        self.body.setSpacing(12)
        outer.addWidget(self._body_w)

        # Résumé FIXE traduit ici, une fois ; set_summary() reçoit ensuite des
        # textes déjà traduits (les traduire deux fois remplaçait « Claude »
        # par le nom de l'assistant… deux fois : « Claude Opus 5.5 Opus 5.5 »).
        self.set_summary(translate(summary) if summary else "")
        self.set_open(_OPEN.get(self._key, opened))

    def is_open(self) -> bool:
        return self._body_w.isVisibleTo(self)

    def set_open(self, open_: bool):
        self._body_w.setVisible(bool(open_))
        self._arrow.setText("▼" if open_ else "▶")
        _OPEN[self._key] = bool(open_)

    def toggle(self):
        self.set_open(not _OPEN.get(self._key, False))

    def set_summary(self, text: str):
        """Texte DÉJÀ traduit par l'appelant."""
        self._summary.setText(text or "")
