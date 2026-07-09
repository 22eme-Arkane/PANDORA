"""
ui/dialog_reference_images.py — Gestion des images de RÉFÉRENCE (inspiration) d'un plan.

Jusqu'à 3 images d'inspiration par plan (Storyboard Cinéma + Séquences Live). Elles
sont injectées en génération Seedance avec le rôle « reference » : le modèle s'en
INSPIRE (ambiance, composition, design) sans les copier à l'identique. Ajout depuis
un fichier OU la bibliothèque d'images globale ; retrait par vignette.

Partagé Cinéma / Live (les plans sont les mêmes shots core.storyboard).
"""
import os

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QWidget, QFileDialog,
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPixmap

from ui.styles import CP
from core.i18n import translate

MAX_REFS = 3
_IMG_FILTER = "Images (*.png *.jpg *.jpeg *.webp *.bmp)"


def build_reference_thumb(paths, width: int = 100, height: int = 58, bg: str = "#0c0e1a"):
    """Aperçu composite des images de référence d'un plan pour la cellule « Référence »
    du storyboard : les N images (max 3) côte à côte et ENTIÈRES (fit inside, jamais
    recadrées/tronquées). Renvoie un QPixmap width×height (vide si aucune image valide).
    Partagé Storyboard Cinéma + Séquences Live."""
    from PyQt6.QtGui import QPixmap, QPainter, QColor
    valid = [p for p in (paths or []) if p and os.path.isfile(p)][:MAX_REFS]
    if not valid:
        return QPixmap()
    n = len(valid)
    gap = 3 if n > 1 else 0
    cw = max(1, (width - gap * (n - 1)) // n)
    canvas = QPixmap(width, height)
    canvas.fill(QColor(bg))
    painter = QPainter(canvas)
    try:
        for i, path in enumerate(valid):
            src = QPixmap(path)
            if src.isNull():
                continue
            sc = src.scaled(cw, height, Qt.AspectRatioMode.KeepAspectRatio,
                            Qt.TransformationMode.SmoothTransformation)
            x = i * (cw + gap) + (cw - sc.width()) // 2
            y = (height - sc.height()) // 2
            painter.drawPixmap(x, y, sc)
    finally:
        painter.end()
    return canvas


class ReferenceImagesDialog(QDialog):
    """Édite la liste `reference_images` (chemins) d'un plan. `result_paths()` après
    exec() renvoie la liste finale (vide si Annuler)."""

    def __init__(self, paths, parent=None):
        super().__init__(parent)
        self._paths = [p for p in (paths or []) if p and os.path.isfile(p)][:MAX_REFS]
        self.setWindowTitle(translate("Images de référence (inspiration)"))
        self.setStyleSheet(f"QDialog{{background:{CP['bg1']};}}")
        self.setMinimumWidth(480)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(18, 16, 18, 16)
        lay.setSpacing(12)

        _title = QLabel(translate("Images de référence — inspiration du plan"))
        _title.setStyleSheet(
            f"color:{CP['accent']};font-size:13px;font-weight:800;letter-spacing:0.5px;"
            f"background:transparent;border:none;")
        lay.addWidget(_title)

        _help = QLabel(translate(
            "Jusqu'à 3 images. Seedance s'en INSPIRE (ambiance, composition) pour ce "
            "plan — ce n'est PAS un rendu à l'identique. Ex. : une photo d'escalier "
            "infini pour guider l'esprit du plan."))
        _help.setWordWrap(True)
        _help.setStyleSheet(
            f"color:{CP['text_secondary']};font-size:11px;background:transparent;border:none;")
        lay.addWidget(_help)

        # Bande de vignettes
        self._thumbs_row = QHBoxLayout()
        self._thumbs_row.setSpacing(8)
        self._thumbs_row.setAlignment(Qt.AlignmentFlag.AlignLeft)
        _thumbs_wrap = QWidget()
        _thumbs_wrap.setStyleSheet("background:transparent;")
        _thumbs_wrap.setLayout(self._thumbs_row)
        lay.addWidget(_thumbs_wrap)

        # Boutons d'ajout
        _add_row = QHBoxLayout()
        _add_row.setSpacing(8)
        self._btn_file = QPushButton(translate("＋ Fichier…"))
        self._btn_file.clicked.connect(self._add_from_file)
        self._btn_lib = QPushButton(translate("＋ Bibliothèque"))
        self._btn_lib.clicked.connect(self._add_from_library)
        for _b in (self._btn_file, self._btn_lib):
            _b.setCursor(Qt.CursorShape.PointingHandCursor)
            _b.setStyleSheet(
                f"QPushButton{{background:transparent;border:1px solid {CP['accent']};"
                f"border-radius:7px;color:{CP['accent']};font-size:11px;font-weight:700;"
                f"padding:6px 14px;}}"
                f"QPushButton:hover{{background:rgba(78,205,196,0.15);}}"
                f"QPushButton:disabled{{border-color:{CP['border']};color:{CP['text_dim']};}}")
        _add_row.addWidget(self._btn_file)
        _add_row.addWidget(self._btn_lib)
        _add_row.addStretch(1)
        lay.addLayout(_add_row)

        # OK / Annuler
        _btn_row = QHBoxLayout()
        _btn_row.addStretch(1)
        _cancel = QPushButton(translate("Annuler"))
        _cancel.clicked.connect(self.reject)
        _ok = QPushButton(translate("Valider"))
        _ok.clicked.connect(self.accept)
        _cancel.setStyleSheet(
            f"QPushButton{{background:{CP['bg3']};border:1px solid {CP['border']};"
            f"border-radius:7px;color:{CP['text_primary']};font-size:11px;padding:7px 16px;}}"
            f"QPushButton:hover{{background:{CP['bg4']};}}")
        _ok.setStyleSheet(
            f"QPushButton{{background:{CP['accent']};border:none;border-radius:7px;"
            f"color:#07080f;font-size:11px;font-weight:800;padding:7px 18px;}}"
            f"QPushButton:hover{{background:#6fe0d8;}}")
        _btn_row.addWidget(_cancel)
        _btn_row.addWidget(_ok)
        lay.addLayout(_btn_row)

        try:
            from ui.widgets import disable_default_buttons
            disable_default_buttons(self)
        except Exception:
            pass

        self._refresh_thumbs()

    def _refresh_thumbs(self):
        # Vide la bande
        while self._thumbs_row.count():
            it = self._thumbs_row.takeAt(0)
            if it.widget():
                it.widget().deleteLater()
        if not self._paths:
            empty = QLabel(translate("Aucune image de référence."))
            empty.setStyleSheet(
                f"color:{CP['text_dim']};font-size:11px;font-style:italic;"
                f"background:transparent;border:none;")
            self._thumbs_row.addWidget(empty)
        for _p in self._paths:
            self._thumbs_row.addWidget(self._make_thumb(_p))
        self._btn_file.setEnabled(len(self._paths) < MAX_REFS)
        self._btn_lib.setEnabled(len(self._paths) < MAX_REFS)

    def _make_thumb(self, path):
        cell = QWidget()
        cell.setFixedSize(110, 92)
        cell.setStyleSheet(
            f"background:{CP['bg2']};border:1px solid {CP['border']};border-radius:8px;")
        cl = QVBoxLayout(cell)
        cl.setContentsMargins(4, 4, 4, 4)
        cl.setSpacing(2)
        img = QLabel()
        img.setFixedSize(100, 58)
        img.setAlignment(Qt.AlignmentFlag.AlignCenter)
        pix = QPixmap(path)
        if not pix.isNull():
            img.setPixmap(pix.scaled(100, 58, Qt.AspectRatioMode.KeepAspectRatio,
                                     Qt.TransformationMode.SmoothTransformation))
        img.setStyleSheet("background:transparent;border:none;")
        cl.addWidget(img)
        rm = QPushButton(translate("✕ Retirer"))
        rm.setCursor(Qt.CursorShape.PointingHandCursor)
        rm.setStyleSheet(
            f"QPushButton{{background:transparent;color:{CP['red']};border:none;"
            f"font-size:9px;font-weight:700;}}QPushButton:hover{{color:#ff8098;}}")
        rm.clicked.connect(lambda _=False, p=path: self._remove(p))
        cl.addWidget(rm)
        return cell

    def _add_paths(self, new_paths):
        for _p in new_paths:
            if _p and os.path.isfile(_p) and _p not in self._paths and len(self._paths) < MAX_REFS:
                self._paths.append(_p)
        self._refresh_thumbs()

    def _add_from_file(self):
        files, _ = QFileDialog.getOpenFileNames(
            self, translate("Choisir des images de référence"), "", _IMG_FILTER)
        if files:
            self._add_paths(files)

    def _add_from_library(self):
        try:
            from ui.dialog_image_library import ImageLibraryDialog
            picked = ImageLibraryDialog.pick(parent=self)
            if picked:
                self._add_paths(picked)
        except Exception:
            # Bibliothèque indisponible → repli sur le sélecteur de fichiers.
            self._add_from_file()

    def _remove(self, path):
        self._paths = [p for p in self._paths if p != path]
        self._refresh_thumbs()

    def result_paths(self):
        return list(self._paths)
