"""ui/language_row.py — Le choix de la langue, dans Paramètres → Général.

Les drapeaux FR / EN de la barre du bas sont retirés (montage de Matthieu,
27/10/2026) : la langue se choisit ici, dans les Paramètres Cinéma et Live
(composant neutre). `chosen(code)` est relié par la fenêtre à son changement de
langue (`_on_lang_change`), qui retraduit toute l'interface sur-le-champ.
"""
from __future__ import annotations

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import QButtonGroup, QHBoxLayout, QPushButton, QWidget

from core.i18n import get_lang
from ui.styles import CP

#: (code, libellé) — chaque langue s'écrit dans sa propre langue.
LANGUAGES = (("fr", "Français"), ("en", "English"))


class LanguageRow(QWidget):
    chosen = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet("background:transparent;")
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(8)
        self._group = QButtonGroup(self)
        self._group.setExclusive(True)
        self.buttons: dict[str, QPushButton] = {}
        style = (
            f"QPushButton{{background:transparent;color:{CP['text_secondary']};"
            f"border:1px solid {CP['border']};border-radius:7px;font-size:12px;"
            f"font-weight:600;padding:0 18px;}}"
            f"QPushButton:hover{{background:{CP['bg3']};color:{CP['text_primary']};}}"
            f"QPushButton:checked{{color:{CP['accent']};border-color:{CP['accent']};"
            f"background:rgba(78,205,196,0.10);}}")
        for code, label in LANGUAGES:
            b = QPushButton(label)
            b.setCheckable(True)
            b.setFixedHeight(36)
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.setStyleSheet(style)
            b.clicked.connect(lambda _c=False, c=code: self._pick(c))
            self._group.addButton(b)
            lay.addWidget(b)
            self.buttons[code] = b
        lay.addStretch(1)
        self.sync()

    def sync(self) -> None:
        cur = get_lang()
        for code, b in self.buttons.items():
            b.setChecked(code == cur)

    def _pick(self, code: str) -> None:
        if code != get_lang():
            self.chosen.emit(code)
        self.sync()
