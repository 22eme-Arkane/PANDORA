"""
Dialogue affiché après la génération d'une image Nano Banana.
Deux choix : Recommencer ou Utiliser cette image.
"""
import os
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QPixmap
from ui.styles import CP, PANDORA_STYLESHEET


class GenerationResultDialog(QDialog):
    """
    Fenêtre résultat après génération d'une image.
    retry_requested — émis si l'utilisateur clique « Recommencer ».
    was_used() → True si l'utilisateur a validé l'image.
    """
    retry_requested = pyqtSignal()

    def __init__(
        self,
        parent=None,
        portrait_path: str = "",
        sheet_path: str = "",
        title: str = "Image générée",
    ):
        super().__init__(parent)
        self._used = False

        self.setWindowTitle(title)
        self.setModal(True)
        self.setFixedSize(560, 580)
        self.setStyleSheet(PANDORA_STYLESHEET + f"QDialog{{background:{CP['bg1']};}}")

        lay = QVBoxLayout(self)
        lay.setContentsMargins(28, 22, 28, 22)
        lay.setSpacing(14)

        t = QLabel(title)
        t.setStyleSheet(
            f"color:{CP['text_primary']};font-size:17px;font-weight:700;background:transparent;"
        )
        lay.addWidget(t)

        # Zone image
        self._img_lbl = QLabel()
        self._img_lbl.setFixedSize(504, 440)
        self._img_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._img_lbl.setWordWrap(True)
        self._img_lbl.setStyleSheet(
            f"background:{CP['bg2']};border:1px solid {CP['border']};"
            f"border-radius:12px;color:{CP['text_dim']};font-size:12px;"
        )
        self._img_lbl.setText("Mode mock — aucune image réelle générée\n(configure ta clé fal.ai dans Paramètres)")
        lay.addWidget(self._img_lbl)

        # Affiche la meilleure image disponible (sheet > portrait)
        display = sheet_path if (sheet_path and os.path.isfile(sheet_path)) else portrait_path
        if display and os.path.isfile(display):
            self._show(display)

        # Boutons
        btn_row = QHBoxLayout()
        btn_row.setSpacing(12)

        btn_retry = QPushButton("↩  Recommencer")
        btn_retry.setFixedHeight(44)
        btn_retry.setStyleSheet(
            f"QPushButton{{background:transparent;color:{CP['text_secondary']};"
            f"border:1px solid {CP['border']};border-radius:8px;"
            f"font-size:12px;font-weight:700;padding:0 18px;}}"
            f"QPushButton:hover{{background:{CP['bg3']};color:{CP['text_primary']};}}"
        )
        btn_retry.clicked.connect(self._on_retry)

        btn_use = QPushButton("✓  Utiliser cette image")
        btn_use.setFixedHeight(44)
        btn_use.setStyleSheet(
            f"QPushButton{{background:{CP['accent']};color:#07080f;"
            f"border:none;border-radius:8px;"
            f"font-size:13px;font-weight:700;padding:0 22px;}}"
            f"QPushButton:hover{{background:#6eded6;}}"
            f"QPushButton:pressed{{background:{CP['accent_dim']};color:#fff;}}"
        )
        btn_use.clicked.connect(self._on_use)

        btn_row.addWidget(btn_retry)
        btn_row.addStretch()
        btn_row.addWidget(btn_use)
        lay.addLayout(btn_row)

        from core.i18n import retranslate_widget
        retranslate_widget(self)

    def _show(self, path: str):
        pix = QPixmap(path)
        if not pix.isNull():
            pix = pix.scaled(
                504, 440,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            self._img_lbl.setPixmap(pix)
            self._img_lbl.setText("")

    def _on_retry(self):
        self.retry_requested.emit()
        self.reject()

    def _on_use(self):
        self._used = True
        self.accept()

    def was_used(self) -> bool:
        return self._used
