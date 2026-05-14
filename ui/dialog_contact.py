from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFrame, QApplication,
)
from PyQt6.QtCore import Qt
from ui.styles import CP, PANDORA_STYLESHEET

_EMAIL = "22eme.arkane@gmail.com"


class ContactDialog(QDialog):

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Nous contacter")
        self.setFixedSize(520, 370)
        self.setStyleSheet(PANDORA_STYLESHEET + f"QDialog{{background:{CP['bg1']};}}")

        lay = QVBoxLayout(self)
        lay.setContentsMargins(32, 28, 32, 28)
        lay.setSpacing(18)

        # ── Header ────────────────────────────────────────────────────────────
        head = QHBoxLayout()
        badge = QLabel("✉")
        badge.setFixedSize(48, 48)
        badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        badge.setStyleSheet(
            f"background:qlineargradient(x1:0,y1:0,x2:1,y2:1,"
            f"stop:0 {CP['accent']},stop:1 {CP['accent2']});"
            f"border-radius:12px;color:#07080f;"
            f"font-size:22px;font-weight:900;border:none;"
        )
        head.addWidget(badge)
        head.addSpacing(14)

        title_col = QVBoxLayout()
        title_col.setSpacing(2)
        title = QLabel("Nous contacter")
        title.setStyleSheet(
            f"color:{CP['text_primary']};font-size:20px;font-weight:800;background:transparent;"
        )
        sub = QLabel("PANDORA × 22eme ARKANE")
        sub.setStyleSheet(
            f"color:{CP['text_dim']};font-size:10px;font-family:'Consolas',monospace;"
            f"letter-spacing:1px;background:transparent;"
        )
        title_col.addWidget(title)
        title_col.addWidget(sub)
        head.addLayout(title_col)
        head.addStretch()
        lay.addLayout(head)

        # ── Adresse e-mail + bouton copier ────────────────────────────────────
        email_frame = QFrame()
        email_frame.setStyleSheet(
            f"QFrame{{background:{CP['bg2']};border:1px solid {CP['border']};"
            f"border-radius:10px;}}"
        )
        ef = QHBoxLayout(email_frame)
        ef.setContentsMargins(16, 12, 12, 12)
        ef.setSpacing(12)

        email_lbl = QLabel(_EMAIL)
        email_lbl.setStyleSheet(
            f"color:{CP['accent']};font-size:13px;font-family:'Consolas',monospace;"
            f"font-weight:700;background:transparent;border:none;"
        )

        self._btn_copy = QPushButton("⎘  Copier")
        self._btn_copy.setFixedHeight(34)
        self._btn_copy.setFixedWidth(104)
        self._btn_copy.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_copy.setStyleSheet(
            f"QPushButton{{background:transparent;color:{CP['text_secondary']};"
            f"border:1px solid {CP['border']};border-radius:6px;"
            f"font-size:11px;font-weight:700;padding:0 12px;}}"
            f"QPushButton:hover{{background:{CP['bg3']};color:{CP['text_primary']};"
            f"border-color:{CP['border_bright']};}}"
            f"QPushButton:pressed{{background:{CP['bg4']};}}"
        )
        self._btn_copy.clicked.connect(self._copy_email)

        ef.addWidget(email_lbl, 1)
        ef.addWidget(self._btn_copy)
        lay.addWidget(email_frame)

        # ── Instructions ──────────────────────────────────────────────────────
        inst_frame = QFrame()
        inst_frame.setStyleSheet(
            f"QFrame{{background:rgba(78,205,196,0.05);"
            f"border:1px solid rgba(78,205,196,0.15);border-radius:10px;}}"
        )
        il = QVBoxLayout(inst_frame)
        il.setContentsMargins(16, 14, 16, 14)
        il.setSpacing(10)

        def _row(icon: str, subject: str, detail: str) -> QHBoxLayout:
            row = QHBoxLayout()
            row.setSpacing(10)
            ico = QLabel(icon)
            ico.setFixedWidth(22)
            ico.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignHCenter)
            ico.setStyleSheet("background:transparent;border:none;font-size:14px;")
            col = QVBoxLayout()
            col.setSpacing(2)
            subj_lbl = QLabel(subject)
            subj_lbl.setStyleSheet(
                f"color:{CP['text_primary']};font-size:11px;font-weight:700;"
                f"background:transparent;border:none;"
            )
            det_lbl = QLabel(detail)
            det_lbl.setWordWrap(True)
            det_lbl.setStyleSheet(
                f"color:{CP['text_secondary']};font-size:10px;"
                f"background:transparent;border:none;"
            )
            col.addWidget(subj_lbl)
            col.addWidget(det_lbl)
            row.addWidget(ico)
            row.addLayout(col, 1)
            return row

        il.addLayout(_row(
            "🐛",
            "Signaler un bug — objet : Bug",
            "Décrivez le problème et les étapes pour le reproduire.",
        ))
        il.addLayout(_row(
            "💬",
            "Avis / suggestion — objet : Avis",
            "Partagez vos retours, idées de fonctionnalités ou impressions.",
        ))
        lay.addWidget(inst_frame)

        lay.addStretch()

        # ── Footer : charte + fermer ──────────────────────────────────────────
        footer_row = QHBoxLayout()
        footer_row.setSpacing(10)

        btn_eula = QPushButton("Charte d'utilisation")
        btn_eula.setFixedHeight(40)
        btn_eula.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_eula.setStyleSheet(
            f"QPushButton{{background:transparent;color:{CP['text_dim']};"
            f"border:1px solid {CP['border']};border-radius:8px;"
            f"font-size:11px;font-weight:600;}}"
            f"QPushButton:hover{{color:{CP['text_secondary']};border-color:{CP['border_bright']};}}"
        )
        btn_eula.clicked.connect(self._open_eula)
        footer_row.addWidget(btn_eula)

        btn_close = QPushButton("Fermer")
        btn_close.setFixedHeight(40)
        btn_close.setStyleSheet(
            f"QPushButton{{background:{CP['bg3']};color:{CP['text_secondary']};"
            f"border:1px solid {CP['border']};border-radius:8px;"
            f"font-size:12px;font-weight:700;}}"
            f"QPushButton:hover{{background:{CP['bg4']};color:{CP['text_primary']};}}"
        )
        btn_close.clicked.connect(self.accept)
        footer_row.addWidget(btn_close, 1)
        lay.addLayout(footer_row)

        from core.i18n import retranslate_widget
        retranslate_widget(self)

    def _open_eula(self):
        from ui.dialog_eula import EulaDialog
        EulaDialog(self, mode="read").exec()

    def _copy_email(self):
        QApplication.clipboard().setText(_EMAIL)
        self._btn_copy.setText("✓  Copié !")
        self._btn_copy.setStyleSheet(
            f"QPushButton{{background:rgba(78,205,196,0.12);color:{CP['accent']};"
            f"border:1px solid {CP['accent']}44;border-radius:6px;"
            f"font-size:11px;font-weight:700;padding:0 12px;}}"
        )
        from PyQt6.QtCore import QTimer
        _default = (
            f"QPushButton{{background:transparent;color:{CP['text_secondary']};"
            f"border:1px solid {CP['border']};border-radius:6px;"
            f"font-size:11px;font-weight:700;padding:0 12px;}}"
            f"QPushButton:hover{{background:{CP['bg3']};color:{CP['text_primary']};"
            f"border-color:{CP['border_bright']};}}"
            f"QPushButton:pressed{{background:{CP['bg4']};}}"
        )
        QTimer.singleShot(2000, lambda: (
            self._btn_copy.setText("⎘  Copier"),
            self._btn_copy.setStyleSheet(_default),
        ))
