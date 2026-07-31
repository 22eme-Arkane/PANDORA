"""Visualiseur d'images plein écran, avec navigation entre plusieurs vues.

Sert à examiner en grand une image générée sans quitter la page qui l'a
produite (demande Matthieu 2026-07-31, atelier 7 vues). La navigation ‹ ›
compte autant que l'agrandissement : comparer « Avant » et « Arrière » d'un
même décor est le geste naturel pour juger une rotation de caméra.

Raccourcis : ← → (ou ‹ ›) pour changer de vue, Échap pour fermer.
"""

from __future__ import annotations

import os

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPixmap, QGuiApplication

from ui.styles import CP
from core.i18n import translate


class ImagePreviewDialog(QDialog):
    """`items` = [(libellé, chemin), …] ; `index` = vue affichée à l'ouverture.

    Les entrées sans fichier lisible sont ignorées ; le dialogue ne s'ouvre
    pas s'il ne reste rien à montrer (voir `show_images`).
    """

    def __init__(self, items: list[tuple[str, str]], index: int = 0, parent=None,
                 title: str = "Aperçu"):
        super().__init__(parent)
        self._items = [(lbl, p) for lbl, p in items
                       if p and os.path.isfile(p)]
        self._index = max(0, min(index, len(self._items) - 1)) if self._items else 0
        self._base_title = translate(title)

        self.setWindowTitle(self._base_title)
        self.setStyleSheet(f"background:{CP['bg1']};")
        scr = QGuiApplication.primaryScreen().availableGeometry()
        self.resize(int(scr.width() * 0.88), int(scr.height() * 0.88))
        self.setSizeGripEnabled(True)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(14, 12, 14, 12)
        lay.setSpacing(10)

        self._image = QLabel()
        self._image.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._image.setStyleSheet(f"background:{CP['bg0']};border-radius:8px;")
        self._image.setMinimumHeight(200)
        lay.addWidget(self._image, 1)

        bar = QHBoxLayout()
        bar.setSpacing(10)
        self._btn_prev = self._nav_button("‹")
        self._btn_prev.clicked.connect(self.previous)
        bar.addWidget(self._btn_prev)

        self._caption = QLabel()
        self._caption.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._caption.setStyleSheet(
            f"color:{CP['text_primary']};font-size:12px;font-weight:700;"
            f"background:transparent;")
        bar.addWidget(self._caption, 1)

        self._btn_next = self._nav_button("›")
        self._btn_next.clicked.connect(self.next)
        bar.addWidget(self._btn_next)

        btn_close = QPushButton(translate("Fermer"))
        btn_close.setFixedHeight(34)
        btn_close.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_close.setStyleSheet(
            f"QPushButton{{background:transparent;color:{CP['text_secondary']};"
            f"border:1px solid {CP['border']};border-radius:8px;"
            f"font-size:11px;padding:0 18px;}}"
            f"QPushButton:hover{{color:{CP['text_primary']};"
            f"border-color:{CP['accent']};}}")
        btn_close.clicked.connect(self.accept)
        bar.addWidget(btn_close)
        lay.addLayout(bar)

        self._refresh()

    # ── Navigation ────────────────────────────────────────────────────────────

    def previous(self):
        if len(self._items) > 1:
            self._index = (self._index - 1) % len(self._items)
            self._refresh()

    def next(self):
        if len(self._items) > 1:
            self._index = (self._index + 1) % len(self._items)
            self._refresh()

    def current_label(self) -> str:
        return self._items[self._index][0] if self._items else ""

    def keyPressEvent(self, e):
        if e.key() in (Qt.Key.Key_Left, Qt.Key.Key_Up):
            self.previous()
            return
        if e.key() in (Qt.Key.Key_Right, Qt.Key.Key_Down, Qt.Key.Key_Space):
            self.next()
            return
        super().keyPressEvent(e)   # Échap ferme (comportement QDialog)

    def resizeEvent(self, e):
        super().resizeEvent(e)
        self._draw()

    # ── Interne ───────────────────────────────────────────────────────────────

    def _nav_button(self, glyph: str) -> QPushButton:
        b = QPushButton(glyph)
        b.setFixedSize(38, 34)
        b.setCursor(Qt.CursorShape.PointingHandCursor)
        b.setStyleSheet(
            f"QPushButton{{background:{CP['bg3']};color:{CP['text_primary']};"
            f"border:1px solid {CP['border']};border-radius:8px;"
            f"font-size:16px;font-weight:700;}}"
            f"QPushButton:hover{{border-color:{CP['accent']};color:{CP['accent']};}}"
            f"QPushButton:disabled{{color:{CP['text_dim']};"
            f"border-color:{CP['border']};}}")
        return b

    def _refresh(self):
        n = len(self._items)
        multi = n > 1
        self._btn_prev.setEnabled(multi)
        self._btn_next.setEnabled(multi)
        self._btn_prev.setVisible(multi)
        self._btn_next.setVisible(multi)
        if not self._items:
            self._caption.setText(translate("Aucune image à afficher"))
            self.setWindowTitle(self._base_title)
            return
        label = self._items[self._index][0]
        self._caption.setText(f"{label}   ({self._index + 1}/{n})" if multi else label)
        self.setWindowTitle(f"{self._base_title} — {label}" if label
                            else self._base_title)
        self._draw()

    def _draw(self):
        if not self._items:
            return
        path = self._items[self._index][1]
        pix = QPixmap(path)
        if pix.isNull():
            self._image.setText(translate("Image illisible"))
            return
        area = self._image.size()
        # Jamais AGRANDIE au-delà de sa taille native (une vue 1344 px étirée
        # plein écran deviendrait floue et mentirait sur sa qualité réelle).
        w = min(area.width(), pix.width())
        h = min(area.height(), pix.height())
        if w > 0 and h > 0:
            pix = pix.scaled(w, h, Qt.AspectRatioMode.KeepAspectRatio,
                             Qt.TransformationMode.SmoothTransformation)
        self._image.setPixmap(pix)


def show_images(parent, items: list[tuple[str, str]], index: int = 0,
                title: str = "Aperçu") -> bool:
    """Ouvre le visualiseur si au moins une image est lisible. True si ouvert."""
    usable = [(lbl, p) for lbl, p in (items or []) if p and os.path.isfile(p)]
    if not usable:
        return False
    # L'index reçu vise `items` ; on le reporte sur la liste filtrée.
    target = 0
    if 0 <= index < len(items or []):
        wanted = (items[index][1] or "")
        target = next((i for i, (_l, p) in enumerate(usable) if p == wanted), 0)
    dlg = ImagePreviewDialog(usable, target, parent, title=title)
    dlg.exec()
    return True
