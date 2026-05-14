from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel
from PyQt6.QtCore import Qt
from ui.styles import CP


class PageStub(QWidget):
    def __init__(self, title: str, icon: str, desc: str = ""):
        super().__init__()
        self.setStyleSheet(f"background:{CP['bg1']};")
        lay = QVBoxLayout(self)
        lay.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lay.setSpacing(16)

        ico = QLabel(icon)
        ico.setAlignment(Qt.AlignmentFlag.AlignCenter)
        ico.setStyleSheet("font-size:52px;background:transparent;")

        lbl = QLabel(title)
        lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl.setStyleSheet(
            f"color:{CP['text_primary']};font-size:24px;font-weight:700;letter-spacing:1px;"
        )

        sub = QLabel(desc or "Cette section est en cours de développement.")
        sub.setAlignment(Qt.AlignmentFlag.AlignCenter)
        sub.setStyleSheet(
            f"color:{CP['text_secondary']};font-size:13px;"
        )

        badge = QLabel("BIENTÔT DISPONIBLE")
        badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        badge.setStyleSheet(f"""
            color:{CP['accent']};font-size:10px;font-weight:700;
            letter-spacing:2px;font-family:'Consolas',monospace;
            border:1px solid {CP['accent_dim']};border-radius:4px;
            padding:5px 14px;background:rgba(78,205,196,0.06);
        """)

        lay.addWidget(ico)
        lay.addWidget(lbl)
        lay.addWidget(sub)
        lay.addSpacing(8)
        lay.addWidget(badge, 0, Qt.AlignmentFlag.AlignCenter)
