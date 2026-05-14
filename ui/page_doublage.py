"""
ui/page_doublage.py — Page Doublage : prochainement.
"""

from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel
from PyQt6.QtCore import Qt
from ui.styles import CP
from ui.icons import load_icon


class PageDoublage(QWidget):
    def __init__(self):
        super().__init__()
        self.setStyleSheet(f"background:{CP['bg0']};")

        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setAlignment(Qt.AlignmentFlag.AlignCenter)

        inner = QVBoxLayout()
        inner.setSpacing(18)
        inner.setAlignment(Qt.AlignmentFlag.AlignCenter)

        ico_lbl = QLabel()
        ico_lbl.setFixedSize(64, 64)
        ico_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        ico_lbl.setStyleSheet("background:transparent;")
        _pix = load_icon("doublage.png", 64)
        if not _pix.isNull():
            ico_lbl.setPixmap(_pix)
        else:
            ico_lbl.setText("🎙")
            ico_lbl.setStyleSheet("font-size:48px;background:transparent;")
        inner.addWidget(ico_lbl, 0, Qt.AlignmentFlag.AlignHCenter)

        title = QLabel("Doublage & Post-Production Audio")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet(
            f"color:{CP['text_primary']};font-size:22px;font-weight:700;"
            f"letter-spacing:1px;background:transparent;"
        )
        inner.addWidget(title)

        badge = QLabel("PROCHAINEMENT")
        badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        badge.setStyleSheet(
            f"color:{CP['accent2']};font-size:10px;font-weight:700;letter-spacing:3px;"
            f"font-family:'Consolas',monospace;"
            f"background:rgba(124,107,255,0.10);border:1px solid rgba(124,107,255,0.30);"
            f"border-radius:6px;padding:5px 14px;"
        )
        inner.addWidget(badge, 0, Qt.AlignmentFlag.AlignHCenter)

        desc = QLabel(
            "Synthèse vocale IA, assignation aux personnages,\n"
            "lipsync natif Seedance — en cours de développement."
        )
        desc.setAlignment(Qt.AlignmentFlag.AlignCenter)
        desc.setWordWrap(True)
        desc.setStyleSheet(
            f"color:{CP['text_secondary']};font-size:13px;line-height:1.6;"
            f"background:transparent;"
        )
        inner.addWidget(desc)

        lay.addLayout(inner)

    def refresh(self):
        pass
