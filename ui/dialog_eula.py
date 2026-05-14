import os
import sys

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QTextEdit, QWidget,
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont

from ui.styles import CP, PANDORA_STYLESHEET

if getattr(sys, "frozen", False):
    _EULA_PATH = os.path.join(sys._MEIPASS, "EULA.txt")
else:
    _EULA_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "EULA.txt")


def _load_eula() -> str:
    try:
        with open(_EULA_PATH, encoding="utf-8") as f:
            return f.read()
    except Exception:
        return "Impossible de charger la charte d'utilisation."


class EulaDialog(QDialog):
    """
    Affiche la charte d'utilisation.

    mode="read"   → bouton "Fermer" seulement (consultation depuis l'app)
    mode="accept" → boutons "J'accepte" / "Je refuse" (premier lancement)
    """

    def __init__(self, parent=None, mode: str = "read"):
        super().__init__(parent)
        self._mode = mode
        self.setWindowTitle("Charte d'utilisation — PANDORA")
        self.setMinimumSize(760, 580)
        self.setStyleSheet(PANDORA_STYLESHEET + f"QDialog{{background:{CP['bg1']};}}")

        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)

        # ── En-tête ──────────────────────────────────────────────────────────
        hdr = QWidget()
        hdr.setFixedHeight(56)
        hdr.setStyleSheet(f"background:{CP['bg2']};border-bottom:1px solid {CP['border']};")
        hl = QHBoxLayout(hdr)
        hl.setContentsMargins(24, 0, 24, 0)
        title_lbl = QLabel("Charte d'utilisation")
        title_lbl.setStyleSheet(
            f"color:{CP['text_primary']};font-size:14px;font-weight:700;background:transparent;"
        )
        hl.addWidget(title_lbl)
        hl.addStretch()
        sub_lbl = QLabel("PANDORA v1.0 — 22eme Arkane")
        sub_lbl.setStyleSheet(f"color:{CP['text_dim']};font-size:10px;background:transparent;")
        hl.addWidget(sub_lbl)
        lay.addWidget(hdr)

        # ── Texte ─────────────────────────────────────────────────────────────
        self._text = QTextEdit()
        self._text.setReadOnly(True)
        self._text.setPlainText(_load_eula())
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
            hint = QLabel("Vous devez accepter la charte pour utiliser PANDORA.")
            hint.setStyleSheet(f"color:{CP['text_dim']};font-size:10px;background:transparent;")
            fl.addWidget(hint, 1)

            btn_refuse = QPushButton("Je refuse")
            btn_refuse.setFixedHeight(36)
            btn_refuse.setCursor(Qt.CursorShape.PointingHandCursor)
            btn_refuse.setStyleSheet(
                f"QPushButton{{background:transparent;color:{CP['red']};"
                f"border:1px solid rgba(255,79,106,0.40);border-radius:6px;"
                f"font-size:11px;font-weight:700;padding:0 18px;}}"
                f"QPushButton:hover{{background:rgba(255,79,106,0.10);}}"
            )
            btn_refuse.clicked.connect(self.reject)
            fl.addWidget(btn_refuse)

            btn_accept = QPushButton("J'accepte")
            btn_accept.setFixedHeight(36)
            btn_accept.setCursor(Qt.CursorShape.PointingHandCursor)
            btn_accept.setStyleSheet(
                f"QPushButton{{background:{CP['accent']};color:#07080f;"
                f"border:none;border-radius:6px;"
                f"font-size:11px;font-weight:700;padding:0 22px;}}"
                f"QPushButton:hover{{background:#6eded6;}}"
                f"QPushButton:pressed{{background:#3bc0b8;}}"
            )
            btn_accept.clicked.connect(self.accept)
            fl.addWidget(btn_accept)

        else:  # "read"
            fl.addStretch()
            btn_close = QPushButton("Fermer")
            btn_close.setFixedHeight(36)
            btn_close.setCursor(Qt.CursorShape.PointingHandCursor)
            btn_close.setStyleSheet(
                f"QPushButton{{background:{CP['bg3']};color:{CP['text_primary']};"
                f"border:1px solid {CP['border']};border-radius:6px;"
                f"font-size:11px;font-weight:700;padding:0 22px;}}"
                f"QPushButton:hover{{background:{CP['bg4'] if 'bg4' in CP else CP['border']};"
                f"border-color:{CP['border_bright']};}}"
            )
            btn_close.clicked.connect(self.accept)
            fl.addWidget(btn_close)

        lay.addWidget(footer)
