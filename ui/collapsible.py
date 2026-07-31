"""Section repliable réutilisable (en-tête ▼/▶ + corps masquable).

Les fiches d'élément ont accumulé beaucoup de contrôles : à l'ouverture,
tout était empilé d'un bloc et il fallait dérouler longuement pour trouver
le prompt (constat Matthieu 2026-07-31 : « ça devient illisible »). Les
parties secondaires sont désormais rangées dans des sections repliées par
défaut, le prompt restant ouvert.

Le motif existait déjà, dupliqué en local dans les pages Scénario
(`_make_toggle` + `_section_container`) ; il est ici factorisé pour être
partagé par les fenêtres d'élément.
"""

from __future__ import annotations

from PyQt6.QtWidgets import QWidget, QVBoxLayout, QPushButton
from PyQt6.QtCore import Qt

from ui.styles import CP
from core.i18n import translate


class CollapsibleSection(QWidget):
    """En-tête cliquable + corps masquable.

    `title` est traduit à la construction ; le glyphe ▼/▶ est recalculé à
    chaque bascule (il ne fait donc pas partie du texte traduit).
    """

    def __init__(self, title: str, expanded: bool = True, parent=None,
                 margins: tuple = (0, 6, 0, 2)):
        super().__init__(parent)
        self._title = translate(title)
        self.setStyleSheet("background:transparent;")

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(4)

        self._btn = QPushButton()
        self._btn.setCheckable(True)
        self._btn.setChecked(expanded)
        self._btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn.setFixedHeight(28)
        self._btn.setStyleSheet(
            f"QPushButton{{background:{CP['bg2']};color:{CP['text_secondary']};"
            f"border:1px solid {CP['border']};border-radius:6px;"
            f"font-size:10px;font-weight:700;letter-spacing:0.8px;"
            f"text-align:left;padding:0 10px;}}"
            f"QPushButton:hover{{background:{CP['bg3']};color:{CP['text_primary']};}}"
            f"QPushButton:checked{{color:{CP['accent']};"
            f"border-color:{CP['accent_dim']};}}"
        )
        outer.addWidget(self._btn)

        self._body = QWidget()
        self._body.setStyleSheet("background:transparent;")
        self._body_lay = QVBoxLayout(self._body)
        self._body_lay.setContentsMargins(*margins)
        self._body_lay.setSpacing(8)
        outer.addWidget(self._body)

        self._body.setVisible(expanded)
        self._sync_text()
        self._btn.toggled.connect(self._on_toggled)

    # ── API ───────────────────────────────────────────────────────────────────

    def body(self) -> QWidget:
        return self._body

    def body_layout(self) -> QVBoxLayout:
        return self._body_lay

    def add_widget(self, widget) -> None:
        self._body_lay.addWidget(widget)

    def add_layout(self, layout) -> None:
        self._body_lay.addLayout(layout)

    def set_expanded(self, expanded: bool) -> None:
        self._btn.setChecked(bool(expanded))

    def is_expanded(self) -> bool:
        return self._btn.isChecked()

    def set_title(self, title: str) -> None:
        self._title = translate(title)
        self._sync_text()

    def header_button(self) -> QPushButton:
        """Le bouton d'en-tête — pour un badge, un compteur ou un test."""
        return self._btn

    # ── Interne ───────────────────────────────────────────────────────────────

    def _on_toggled(self, checked: bool) -> None:
        self._body.setVisible(checked)
        self._sync_text()

    def _sync_text(self) -> None:
        self._btn.setText(f"{'▼' if self._btn.isChecked() else '▶'}  {self._title}")
