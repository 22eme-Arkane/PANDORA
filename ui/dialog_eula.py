import os
import sys

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QTextEdit, QWidget,
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont

from ui.styles import CP, PANDORA_STYLESHEET
from core.i18n import get_lang

if getattr(sys, "frozen", False):
    _BASE = sys._MEIPASS
else:
    _BASE = os.path.dirname(os.path.dirname(__file__))

_EULA_PATH    = os.path.join(_BASE, "EULA.txt")
_EULA_EN_PATH = os.path.join(_BASE, "EULA_EN.txt")


def _load(path: str) -> str:
    try:
        with open(path, encoding="utf-8") as f:
            return f.read()
    except Exception:
        return "Could not load the license agreement."


_BTN_LANG = (
    "QPushButton{background:transparent;border:1px solid %s;border-radius:4px;"
    "color:%s;font-size:10px;font-weight:700;padding:0 8px;min-width:32px;min-height:22px;}"
    "QPushButton:hover{background:rgba(255,255,255,0.06);}"
    "QPushButton[active=true]{background:%s;color:#07080f;border-color:%s;}"
)


class EulaDialog(QDialog):
    """
    Affiche la charte d'utilisation.

    mode="read"   → bouton "Fermer" seulement (consultation depuis l'app)
    mode="accept" → boutons "J'accepte" / "Je refuse" (premier lancement)
    """

    def __init__(self, parent=None, mode: str = "read"):
        super().__init__(parent)
        self._mode = mode
        self._lang = get_lang()
        self.setWindowTitle("Charte d'utilisation — PANDORA")
        self.setStyleSheet(PANDORA_STYLESHEET + f"QDialog{{background:{CP['bg1']};}}")
        from ui.widgets import fit_dialog_to_screen
        fit_dialog_to_screen(self, 0.55, 0.80, 660, 480)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)

        # ── En-tête ──────────────────────────────────────────────────────────
        hdr = QWidget()
        hdr.setFixedHeight(56)
        hdr.setStyleSheet(f"background:{CP['bg2']};border-bottom:1px solid {CP['border']};")
        hl = QHBoxLayout(hdr)
        hl.setContentsMargins(24, 0, 24, 0)
        hl.setSpacing(8)

        self._title_lbl = QLabel()
        self._title_lbl.setStyleSheet(
            f"color:{CP['text_primary']};font-size:14px;font-weight:700;background:transparent;"
        )
        hl.addWidget(self._title_lbl)
        hl.addStretch()

        sub_lbl = QLabel("PANDORA v1.0 — 22eme Arkane")
        sub_lbl.setStyleSheet(f"color:{CP['text_dim']};font-size:10px;background:transparent;")
        hl.addWidget(sub_lbl)

        hl.addSpacing(16)

        # Toggle FR / EN
        _s = _BTN_LANG % (CP['border'], CP['text_secondary'], CP['accent'], CP['accent'])
        self._btn_fr = QPushButton("🇫🇷")
        self._btn_en = QPushButton("🇬🇧")
        for btn in (self._btn_fr, self._btn_en):
            btn.setStyleSheet(_s)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setCheckable(False)
            hl.addWidget(btn)
        self._btn_fr.clicked.connect(lambda: self._set_lang("fr"))
        self._btn_en.clicked.connect(lambda: self._set_lang("en"))

        lay.addWidget(hdr)

        # ── Texte ─────────────────────────────────────────────────────────────
        self._text = QTextEdit()
        self._text.setReadOnly(True)
        self._text.setFont(QFont("Consolas", 10))
        self._text.setStyleSheet(
            f"QTextEdit{{background:{CP['bg2']};color:{CP['text_secondary']};"
            f"border:none;padding:20px 28px;line-height:1.6;}}"
            f"QScrollBar:vertical{{background:{CP['bg3']};width:8px;border:none;}}"
            f"QScrollBar::handle:vertical{{background:{CP['border_bright']};border-radius:4px;min-height:30px;}}"
        )
        lay.addWidget(self._text, 1)

        # ── Pied de page ─────────────────────────────────────────────────────
        footer = QWidget()
        footer.setFixedHeight(60)
        footer.setStyleSheet(f"background:{CP['bg2']};border-top:1px solid {CP['border']};")
        fl = QHBoxLayout(footer)
        fl.setContentsMargins(24, 0, 24, 0)
        fl.setSpacing(12)

        if mode == "accept":
            self._hint = QLabel()
            self._hint.setStyleSheet(f"color:{CP['text_dim']};font-size:10px;background:transparent;")
            fl.addWidget(self._hint, 1)

            self._btn_refuse = QPushButton()
            self._btn_refuse.setFixedHeight(36)
            self._btn_refuse.setCursor(Qt.CursorShape.PointingHandCursor)
            self._btn_refuse.setStyleSheet(
                f"QPushButton{{background:transparent;color:{CP['red']};"
                f"border:1px solid rgba(255,79,106,0.40);border-radius:6px;"
                f"font-size:11px;font-weight:700;padding:0 18px;}}"
                f"QPushButton:hover{{background:rgba(255,79,106,0.10);}}"
            )
            self._btn_refuse.clicked.connect(self.reject)
            fl.addWidget(self._btn_refuse)

            self._btn_accept = QPushButton()
            self._btn_accept.setFixedHeight(36)
            self._btn_accept.setCursor(Qt.CursorShape.PointingHandCursor)
            self._btn_accept.setStyleSheet(
                f"QPushButton{{background:{CP['accent']};color:#07080f;"
                f"border:none;border-radius:6px;"
                f"font-size:11px;font-weight:700;padding:0 22px;}}"
                f"QPushButton:hover{{background:#6eded6;}}"
                f"QPushButton:pressed{{background:#3bc0b8;}}"
            )
            self._btn_accept.clicked.connect(self.accept)
            fl.addWidget(self._btn_accept)

        else:  # "read"
            fl.addStretch()
            self._btn_close = QPushButton()
            self._btn_close.setFixedHeight(36)
            self._btn_close.setCursor(Qt.CursorShape.PointingHandCursor)
            self._btn_close.setStyleSheet(
                f"QPushButton{{background:{CP['bg3']};color:{CP['text_primary']};"
                f"border:1px solid {CP['border']};border-radius:6px;"
                f"font-size:11px;font-weight:700;padding:0 22px;}}"
                f"QPushButton:hover{{background:{CP.get('bg4', CP['border'])};"
                f"border-color:{CP['border_bright']};}}"
            )
            self._btn_close.clicked.connect(self.accept)
            fl.addWidget(self._btn_close)

        lay.addWidget(footer)

        # Initial render
        self._refresh()

    # ── Langue ───────────────────────────────────────────────────────────────

    def _set_lang(self, lang: str):
        self._lang = lang
        self._refresh()

    def _refresh(self):
        fr = self._lang == "fr"
        # Texte
        self._text.setPlainText(_load(_EULA_PATH if fr else _EULA_EN_PATH))
        self._text.verticalScrollBar().setValue(0)
        # Titre
        self._title_lbl.setText("Charte d'utilisation" if fr else "License Agreement")
        # Boutons actifs
        self._btn_fr.setProperty("active", fr)
        self._btn_en.setProperty("active", not fr)
        for btn in (self._btn_fr, self._btn_en):
            btn.style().unpolish(btn)
            btn.style().polish(btn)
        # Labels mode accept
        if self._mode == "accept":
            if fr:
                self._hint.setText("Vous devez accepter la charte pour utiliser PANDORA.")
                self._btn_refuse.setText("Je refuse")
                self._btn_accept.setText("J'accepte")
            else:
                self._hint.setText("You must accept the agreement to use PANDORA.")
                self._btn_refuse.setText("Decline")
                self._btn_accept.setText("Accept")
        else:
            self._btn_close.setText("Fermer" if fr else "Close")
