"""
Galerie de toutes les images générées pour un personnage.
Permet de choisir le portrait actif et de supprimer des entrées.
"""
import os
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QScrollArea, QWidget, QGridLayout,
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPixmap
from ui.styles import CP, PANDORA_STYLESHEET


class CharacterGalleryDialog(QDialog):

    def __init__(
        self,
        parent=None,
        generated_images: list | None = None,
        current_portrait: str = "",
        current_sheet: str = "",
        char_name: str = "",
    ):
        super().__init__(parent)
        self._images          = [dict(img) for img in (generated_images or [])]
        self._active_portrait = current_portrait
        self._active_sheet    = current_sheet
        self._chosen          = None  # set when user clicks "Utiliser"

        label = f" — {char_name}" if char_name else ""
        self.setWindowTitle(f"Aperçu du personnage{label}")
        self.setFixedSize(740, 540)
        self.setStyleSheet(PANDORA_STYLESHEET + f"QDialog{{background:{CP['bg1']};}}")

        lay = QVBoxLayout(self)
        lay.setContentsMargins(24, 20, 24, 20)
        lay.setSpacing(12)

        # Titre
        title = QLabel(f"Aperçu du personnage{label}")
        title.setStyleSheet(
            f"color:{CP['text_primary']};font-size:17px;font-weight:700;background:transparent;"
        )
        lay.addWidget(title)

        hint = QLabel(
            "Clique sur « Utiliser » pour définir une image comme portrait actif du personnage. "
            "« Supprimer de la liste » retire l'entrée mais ne supprime pas le fichier sur le disque."
        )
        hint.setWordWrap(True)
        hint.setStyleSheet(
            f"color:{CP['text_dim']};font-size:10px;background:transparent;"
        )
        lay.addWidget(hint)

        # Grille scrollable
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea{background:transparent;border:none;}")

        self._grid_widget = QWidget()
        self._grid_widget.setStyleSheet("background:transparent;")
        self._grid = QGridLayout(self._grid_widget)
        self._grid.setSpacing(14)
        self._grid.setContentsMargins(0, 4, 0, 4)
        self._grid.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)

        scroll.setWidget(self._grid_widget)
        lay.addWidget(scroll, 1)

        self._render()

        # Bouton Fermer
        btn_close = QPushButton("Fermer")
        btn_close.setFixedHeight(40)
        btn_close.setStyleSheet(
            f"QPushButton{{background:{CP['bg3']};color:{CP['text_secondary']};"
            f"border:1px solid {CP['border']};border-radius:8px;"
            f"font-size:12px;font-weight:700;padding:0 20px;}}"
            f"QPushButton:hover{{background:{CP['bg2']};color:{CP['text_primary']};}}"
        )
        btn_close.clicked.connect(self.accept)
        hrow = QHBoxLayout()
        hrow.addStretch()
        hrow.addWidget(btn_close)
        lay.addLayout(hrow)

        from core.i18n import retranslate_widget
        retranslate_widget(self)

    # ── Rendu ─────────────────────────────────────────────────────────────────

    def _render(self):
        while self._grid.count():
            item = self._grid.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        if not self._images:
            empty = QLabel("Aucune image générée pour ce personnage.\nLance une génération depuis le dialogue d'édition.")
            empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
            empty.setWordWrap(True)
            empty.setStyleSheet(
                f"color:{CP['text_dim']};font-size:12px;background:transparent;padding:40px;"
            )
            self._grid.addWidget(empty, 0, 0, 1, 4)
            return

        COLS = 4
        for i, entry in enumerate(self._images):
            card = self._make_card(entry, i)
            self._grid.addWidget(card, i // COLS, i % COLS)

    def _make_card(self, entry: dict, idx: int) -> QWidget:
        portrait = entry.get("portrait", "")
        sheet    = entry.get("sheet", "")
        is_active = (
            (portrait and portrait == self._active_portrait) or
            (sheet    and sheet    == self._active_sheet)
        )

        card = QWidget()
        card.setFixedSize(158, 216)
        border = CP["accent"] if is_active else CP["border"]
        card.setStyleSheet(
            f"QWidget{{background:{CP['bg2']};border:2px solid {border};border-radius:10px;}}"
        )

        lay = QVBoxLayout(card)
        lay.setContentsMargins(7, 7, 7, 7)
        lay.setSpacing(5)

        # Vignette
        thumb = QLabel()
        thumb.setFixedSize(142, 124)
        thumb.setAlignment(Qt.AlignmentFlag.AlignCenter)
        thumb.setStyleSheet(
            f"background:{CP['bg3']};border-radius:6px;color:{CP['text_dim']};"
            f"font-size:11px;border:none;"
        )
        display = sheet if (sheet and os.path.isfile(sheet)) else portrait
        if display and os.path.isfile(display):
            pix = QPixmap(display).scaled(
                142, 124,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            thumb.setPixmap(pix)
        else:
            thumb.setText("Image\nmanquante")
        lay.addWidget(thumb)

        # Badge actif
        if is_active:
            badge = QLabel("ACTIF")
            badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
            badge.setFixedHeight(18)
            badge.setStyleSheet(
                f"color:#07080f;background:{CP['accent']};border-radius:4px;"
                f"font-size:9px;font-weight:700;letter-spacing:0.5px;border:none;"
            )
            lay.addWidget(badge)

        # Bouton Utiliser
        btn_use = QPushButton("✓  Utiliser")
        btn_use.setFixedHeight(28)
        btn_use.setStyleSheet(
            f"QPushButton{{background:transparent;color:{CP['accent']};"
            f"border:1px solid {CP['accent_dim']};border-radius:5px;"
            f"font-size:10px;font-weight:700;padding:0;}}"
            f"QPushButton:hover{{background:{CP['accent']};color:#07080f;}}"
        )
        btn_use.clicked.connect(lambda checked=False, e=entry: self._use(e))
        lay.addWidget(btn_use)

        # Bouton Supprimer
        btn_del = QPushButton("Supprimer de la liste")
        btn_del.setFixedHeight(26)
        btn_del.setStyleSheet(
            f"QPushButton{{background:transparent;color:{CP['text_dim']};"
            f"border:1px solid {CP['border']};border-radius:5px;"
            f"font-size:9px;font-weight:700;padding:0;}}"
            f"QPushButton:hover{{background:rgba(255,79,106,0.12);"
            f"color:{CP['red']};border-color:{CP['red']};}}"
        )
        btn_del.clicked.connect(lambda checked=False, i=idx: self._delete(i))
        lay.addWidget(btn_del)

        return card

    # ── Actions ───────────────────────────────────────────────────────────────

    def _use(self, entry: dict):
        self._chosen          = entry
        self._active_portrait = entry.get("portrait", "")
        self._active_sheet    = entry.get("sheet", "")
        self._render()

    def _delete(self, idx: int):
        if 0 <= idx < len(self._images):
            self._images.pop(idx)
            self._render()

    def get_chosen(self) -> dict | None:
        return self._chosen

    def get_images(self) -> list:
        return list(self._images)
