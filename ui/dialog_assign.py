"""
Dialogue de sélection de personnages pour l'assignation d'un accessoire ou item HMC.
"""
import os
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QScrollArea, QWidget, QCheckBox, QFrame,
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPixmap
from ui.styles import CP, PANDORA_STYLESHEET
import core.casting as casting_api


class AssignCharactersDialog(QDialog):
    """
    Dialogue pour choisir les personnages auxquels assigner un élément.
    Retourne la liste des IDs sélectionnés via get_selected_ids().
    """

    def __init__(self, parent=None, current_ids: list | None = None):
        super().__init__(parent)
        self._current = set(current_ids or [])
        self._checks: dict[str, QCheckBox] = {}

        self.setWindowTitle("Assigner à des personnages")
        self.setFixedSize(480, 500)
        self.setStyleSheet(PANDORA_STYLESHEET + f"QDialog{{background:{CP['bg1']};}}")

        root = QVBoxLayout(self)
        root.setContentsMargins(24, 20, 24, 20)
        root.setSpacing(14)

        title = QLabel("Sélectionne les personnages")
        title.setStyleSheet(
            f"color:{CP['text_primary']};font-size:16px;font-weight:700;background:transparent;"
        )
        root.addWidget(title)

        hint = QLabel("Les modifications sont bidirectionnelles : la fiche personnage sera mise à jour automatiquement.")
        hint.setWordWrap(True)
        hint.setStyleSheet(
            f"color:{CP['text_dim']};font-size:10px;font-family:'Consolas',monospace;background:transparent;"
        )
        root.addWidget(hint)

        sep = QFrame()
        sep.setFixedHeight(1)
        sep.setStyleSheet(f"background:{CP['border']};")
        root.addWidget(sep)

        # Liste des personnages
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea{background:transparent;border:none;}")

        container = QWidget()
        container.setStyleSheet("background:transparent;")
        lay = QVBoxLayout(container)
        lay.setContentsMargins(0, 4, 0, 4)
        lay.setSpacing(6)

        chars = casting_api.list_characters()
        if not chars:
            empty = QLabel("Aucun personnage créé.\nCrée des personnages dans l'onglet Castings d'abord.")
            empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
            empty.setStyleSheet(
                f"color:{CP['text_dim']};font-size:12px;background:transparent;padding:20px;"
            )
            lay.addWidget(empty)
        else:
            for char in chars:
                row = self._make_row(char)
                lay.addWidget(row)

        lay.addStretch()
        scroll.setWidget(container)
        root.addWidget(scroll, 1)

        # Boutons
        btn_row = QHBoxLayout()
        btn_cancel = QPushButton("Annuler")
        btn_cancel.setFixedHeight(38)
        btn_cancel.setStyleSheet(
            f"QPushButton{{background:transparent;color:{CP['text_secondary']};"
            f"border:1px solid {CP['border']};border-radius:8px;font-size:12px;font-weight:700;padding:0 18px;}}"
            f"QPushButton:hover{{background:{CP['bg3']};color:{CP['text_primary']};}}"
        )
        btn_cancel.clicked.connect(self.reject)

        btn_ok = QPushButton("✓  Confirmer")
        btn_ok.setFixedHeight(38)
        btn_ok.setStyleSheet(
            f"QPushButton{{background:{CP['accent']};color:#07080f;"
            f"border:none;border-radius:8px;font-size:12px;font-weight:700;padding:0 18px;}}"
            f"QPushButton:hover{{background:#6eded6;}}"
        )
        btn_ok.clicked.connect(self.accept)

        btn_row.addWidget(btn_cancel)
        btn_row.addStretch()
        btn_row.addWidget(btn_ok)
        root.addLayout(btn_row)

        from core.i18n import retranslate_widget
        retranslate_widget(self)

    def _make_row(self, char: dict) -> QWidget:
        row = QFrame()
        row.setCursor(Qt.CursorShape.PointingHandCursor)
        row.setStyleSheet(
            f"QFrame{{background:{CP['bg2']};border:1px solid {CP['border']};"
            f"border-radius:8px;}}"
        )
        lay = QHBoxLayout(row)
        lay.setContentsMargins(12, 8, 12, 8)
        lay.setSpacing(12)

        # Portrait miniature
        thumb = QLabel()
        thumb.setFixedSize(36, 36)
        thumb.setAlignment(Qt.AlignmentFlag.AlignCenter)
        thumb.setStyleSheet(
            f"background:{CP['bg3']};border-radius:4px;color:{CP['text_dim']};font-size:16px;"
        )
        img = char.get("image_path", "")
        if img and os.path.isfile(img):
            pix = QPixmap(img).scaled(
                36, 36,
                Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                Qt.TransformationMode.SmoothTransformation,
            )
            pix = pix.copy((pix.width()-36)//2, (pix.height()-36)//2, 36, 36)
            thumb.setPixmap(pix)
        else:
            thumb.setText("👤")
        lay.addWidget(thumb)

        # Nom + rôle
        col = QVBoxLayout()
        col.setSpacing(2)
        name_lbl = QLabel(char.get("name", "—"))
        name_lbl.setStyleSheet(
            f"color:{CP['text_primary']};font-size:12px;font-weight:700;background:transparent;border:none;"
        )
        role_lbl = QLabel(char.get("role", ""))
        role_lbl.setStyleSheet(
            f"color:{CP['text_secondary']};font-size:10px;background:transparent;border:none;"
        )
        col.addWidget(name_lbl)
        col.addWidget(role_lbl)
        lay.addLayout(col, 1)

        # Checkbox
        cb = QCheckBox()
        cb.setChecked(char.get("id", "") in self._current)
        cb.setStyleSheet(f"QCheckBox::indicator{{width:18px;height:18px;}}")
        lay.addWidget(cb)
        self._checks[char.get("id", "")] = cb

        # Cliquer n'importe où sur la ligne bascule la checkbox
        row.mousePressEvent = lambda e, c=cb: c.setChecked(not c.isChecked())

        return row

    def get_selected_ids(self) -> list[str]:
        return [cid for cid, cb in self._checks.items() if cb.isChecked()]
