"""
ui/dialog_image_library.py — Bibliothèque d'images de référence (Cinéma + Live).

Porte d'entrée UNIQUE pour ajouter des références partout dans PANDORA :
scénario/conducteur, casting, décors, accessoires, HMC, véhicules, templates.

Deux modes :
  - pick=True  (défaut) : sélecteur — « Utiliser la sélection » renvoie les
    images choisies ; « Parcourir le disque… » reste disponible pour un fichier
    ponctuel (avec proposition de le ranger dans une collection au passage).
  - pick=False : simple gestionnaire (organiser ses collections).

Usage le plus courant :
    paths = ImageLibraryDialog.pick(self)   # [] si annulé
"""

import os

from PyQt6.QtCore import Qt, QSize
from PyQt6.QtGui import QIcon, QPixmap
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QListWidget,
    QListWidgetItem, QFileDialog, QInputDialog, QMessageBox, QAbstractItemView,
)

from core import image_library as lib
from core.i18n import translate
from ui.styles import CP

_DISK_FILTER = "Images (*.png *.jpg *.jpeg *.webp *.bmp)"


class ImageLibraryDialog(QDialog):
    """Bibliothèque globale : collections à gauche, vignettes à droite."""

    def __init__(self, parent=None, pick: bool = True):
        super().__init__(parent)
        self._pick = pick
        self.picked: list[str] = []   # résultat (mode pick)

        self.setWindowTitle(translate("Bibliothèque d'images"))
        self.resize(940, 620)
        self.setStyleSheet(
            f"QDialog{{background:{CP['bg1']};}}"
            f"QLabel{{background:transparent;color:{CP['text_primary']};}}"
        )

        root = QVBoxLayout(self)
        root.setContentsMargins(20, 18, 20, 18)
        root.setSpacing(12)

        # ── En-tête ──────────────────────────────────────────────────────────
        hdr = QHBoxLayout()
        title = QLabel(translate("📚  Bibliothèque d'images"))
        title.setStyleSheet(f"color:{CP['text_primary']};font-size:14px;font-weight:700;")
        self._status = QLabel(translate("Partagée entre tous les projets — Cinéma et Live"))
        self._status.setStyleSheet(
            f"color:{CP['text_dim']};font-size:10px;font-family:'Consolas',monospace;")
        hdr.addWidget(title)
        hdr.addStretch()
        hdr.addWidget(self._status)
        root.addLayout(hdr)

        # ── Corps : collections | images ─────────────────────────────────────
        body = QHBoxLayout()
        body.setSpacing(12)

        left = QVBoxLayout()
        left.setSpacing(8)
        self._col_list = QListWidget()
        self._col_list.setFixedWidth(230)
        self._col_list.setStyleSheet(
            f"QListWidget{{background:{CP['bg2']};border:1px solid {CP['border']};"
            f"border-radius:8px;color:{CP['text_primary']};font-size:11px;padding:4px;}}"
            f"QListWidget::item{{padding:8px 10px;border-radius:6px;}}"
            f"QListWidget::item:selected{{background:{CP['bg4']};color:{CP['accent']};}}"
            f"QListWidget::item:hover{{background:{CP['bg3']};}}"
        )
        self._col_list.currentRowChanged.connect(self._on_collection_changed)
        left.addWidget(self._col_list, 1)

        _small_ss = (
            f"QPushButton{{background:{CP['bg3']};color:{CP['text_secondary']};"
            f"border:1px solid {CP['border']};border-radius:6px;"
            f"font-size:10px;font-weight:600;padding:0 10px;}}"
            f"QPushButton:hover{{background:{CP['bg4']};color:{CP['text_primary']};}}"
        )
        col_btns = QHBoxLayout()
        col_btns.setSpacing(6)
        for label, tip, cb in (
            ("✚", translate("Nouvelle collection"), self._on_new_collection),
            ("✎", translate("Renommer la collection"), self._on_rename_collection),
            ("✕", translate("Supprimer la collection"), self._on_delete_collection),
        ):
            b = QPushButton(label)
            b.setFixedHeight(28)
            b.setToolTip(tip)
            b.setStyleSheet(_small_ss)
            b.clicked.connect(cb)
            col_btns.addWidget(b)
        col_btns.addStretch()
        left.addLayout(col_btns)
        body.addLayout(left)

        right = QVBoxLayout()
        right.setSpacing(8)
        self._img_list = QListWidget()
        self._img_list.setViewMode(QListWidget.ViewMode.IconMode)
        self._img_list.setIconSize(QSize(110, 110))
        self._img_list.setGridSize(QSize(126, 132))
        self._img_list.setResizeMode(QListWidget.ResizeMode.Adjust)
        self._img_list.setMovement(QListWidget.Movement.Static)
        self._img_list.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self._img_list.setStyleSheet(
            f"QListWidget{{background:{CP['bg2']};border:1px solid {CP['border']};"
            f"border-radius:8px;color:{CP['text_dim']};font-size:9px;padding:8px;}}"
            f"QListWidget::item{{border-radius:6px;padding:2px;}}"
            f"QListWidget::item:selected{{background:{CP['bg4']};border:1px solid {CP['accent']};}}"
        )
        if pick:
            self._img_list.itemDoubleClicked.connect(self._on_use_selection)
        right.addWidget(self._img_list, 1)

        img_btns = QHBoxLayout()
        img_btns.setSpacing(8)
        btn_add_imgs = QPushButton(translate("⬆  Ajouter des images"))
        btn_add_imgs.setFixedHeight(30)
        btn_add_imgs.setToolTip(translate(
            "Copie des images du disque dans cette collection\n"
            "(la bibliothèque garde sa propre copie)."))
        btn_add_imgs.setStyleSheet(_small_ss)
        btn_add_imgs.clicked.connect(self._on_add_images)
        btn_remove = QPushButton(translate("Retirer de la collection"))
        btn_remove.setFixedHeight(30)
        btn_remove.setStyleSheet(_small_ss)
        btn_remove.clicked.connect(self._on_remove_images)
        img_btns.addWidget(btn_add_imgs)
        img_btns.addWidget(btn_remove)
        img_btns.addStretch()
        right.addLayout(img_btns)
        body.addLayout(right, 1)
        root.addLayout(body, 1)

        # ── Pied ─────────────────────────────────────────────────────────────
        foot = QHBoxLayout()
        foot.setSpacing(8)
        _ghost_ss = (
            f"QPushButton{{background:{CP['bg3']};color:{CP['text_secondary']};"
            f"border:1px solid {CP['border']};border-radius:7px;"
            f"font-size:11px;font-weight:600;padding:0 20px;}}"
            f"QPushButton:hover{{background:{CP['bg4']};color:{CP['text_primary']};}}"
        )
        _accent_ss = (
            f"QPushButton{{background:{CP['accent']};color:#07080f;"
            f"border:none;border-radius:7px;font-size:11px;font-weight:700;padding:0 20px;}}"
            f"QPushButton:hover{{background:#6eded6;}}"
            f"QPushButton:disabled{{background:{CP['bg3']};color:{CP['text_dim']};"
            f"border:1px solid {CP['border']};}}"
        )
        btn_close = QPushButton(translate("Fermer"))
        btn_close.setFixedHeight(36)
        btn_close.setStyleSheet(_ghost_ss)
        btn_close.clicked.connect(self.reject)
        foot.addWidget(btn_close)
        foot.addStretch()
        if pick:
            btn_disk = QPushButton(translate("💻  Parcourir le disque…"))
            btn_disk.setFixedHeight(36)
            btn_disk.setToolTip(translate(
                "Choisir des fichiers hors bibliothèque —\n"
                "PANDORA proposera de les ranger dans une collection."))
            btn_disk.setStyleSheet(_ghost_ss)
            btn_disk.clicked.connect(self._on_browse_disk)
            foot.addWidget(btn_disk)
            self._btn_use = QPushButton(translate("✓  Utiliser la sélection"))
            self._btn_use.setFixedHeight(36)
            self._btn_use.setEnabled(False)
            self._btn_use.setStyleSheet(_accent_ss)
            self._btn_use.clicked.connect(self._on_use_selection)
            foot.addWidget(self._btn_use)
            self._img_list.itemSelectionChanged.connect(self._refresh_use_btn)
        root.addLayout(foot)

        self._reload_collections()

    # ── API pratique ──────────────────────────────────────────────────────────

    @classmethod
    def pick(cls, parent=None) -> list:
        """Ouvre la bibliothèque en mode sélection ; renvoie les chemins choisis
        (bibliothèque OU disque), [] si annulé."""
        dlg = cls(parent, pick=True)
        dlg.exec()
        return dlg.picked

    # ── Collections ───────────────────────────────────────────────────────────

    def _current_key(self) -> str:
        it = self._col_list.currentItem()
        return it.data(Qt.ItemDataRole.UserRole) if it else ""

    def _reload_collections(self, select_key: str = ""):
        self._col_list.blockSignals(True)
        self._col_list.clear()
        cols = lib.list_collections()
        for c in cols:
            it = QListWidgetItem(f"{c['name']}   ·  {c['count']}")
            it.setData(Qt.ItemDataRole.UserRole, c["key"])
            self._col_list.addItem(it)
        self._col_list.blockSignals(False)
        if cols:
            row = 0
            if select_key:
                row = next((i for i, c in enumerate(cols) if c["key"] == select_key), 0)
            self._col_list.setCurrentRow(row)
        else:
            self._img_list.clear()
            self._status.setText(translate(
                "Crée une collection (✚) puis ajoute-lui des images."))

    def _on_collection_changed(self, _row: int):
        self._reload_images()

    def _on_new_collection(self):
        name, ok = QInputDialog.getText(
            self, translate("Nouvelle collection"), translate("Nom de la collection :"))
        if not ok or not name.strip():
            return
        key = lib.create_collection(name.strip())
        self._reload_collections(select_key=key)

    def _on_rename_collection(self):
        key = self._current_key()
        if not key:
            return
        it = self._col_list.currentItem()
        old = it.text().rsplit("   ·", 1)[0] if it else ""
        name, ok = QInputDialog.getText(
            self, translate("Renommer la collection"),
            translate("Nom de la collection :"), text=old)
        if not ok or not name.strip():
            return
        lib.rename_collection(key, name.strip())
        self._reload_collections(select_key=key)

    def _on_delete_collection(self):
        key = self._current_key()
        if not key:
            return
        n = len(lib.list_images(key))
        reply = QMessageBox.question(
            self, translate("Supprimer la collection"),
            f"{translate('Supprimer cette collection et ses images ?')}\n"
            f"{n} image(s) — {translate('les copies de la bibliothèque seront effacées.')}",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        lib.delete_collection(key)
        self._reload_collections()

    # ── Images ────────────────────────────────────────────────────────────────

    def _reload_images(self):
        self._img_list.clear()
        key = self._current_key()
        for path in lib.list_images(key):
            pix = QPixmap(path)
            it = QListWidgetItem()
            if not pix.isNull():
                it.setIcon(QIcon(pix.scaled(
                    110, 110, Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation)))
            it.setText(os.path.basename(path)[:16])
            it.setData(Qt.ItemDataRole.UserRole, path)
            it.setToolTip(path)
            self._img_list.addItem(it)
        n = self._img_list.count()
        self._status.setText(f"{n} image(s)")

    def _on_add_images(self):
        key = self._current_key()
        if not key:
            self._on_new_collection()
            key = self._current_key()
            if not key:
                return
        paths, _ = QFileDialog.getOpenFileNames(
            self, translate("Ajouter des images à la collection"), "", _DISK_FILTER)
        if not paths:
            return
        lib.add_images(key, paths)
        self._reload_collections(select_key=key)

    def _on_remove_images(self):
        items = self._img_list.selectedItems()
        if not items:
            return
        for it in items:
            lib.remove_image(it.data(Qt.ItemDataRole.UserRole))
        self._reload_collections(select_key=self._current_key())

    # ── Mode sélection ────────────────────────────────────────────────────────

    def _refresh_use_btn(self):
        n = len(self._img_list.selectedItems())
        self._btn_use.setEnabled(n > 0)
        self._btn_use.setText(
            f"✓  {translate('Utiliser la sélection')} ({n})" if n
            else f"✓  {translate('Utiliser la sélection')}")

    def _on_use_selection(self, *_a):
        self.picked = [it.data(Qt.ItemDataRole.UserRole)
                       for it in self._img_list.selectedItems()]
        if self.picked:
            self.accept()

    def _on_browse_disk(self):
        paths, _ = QFileDialog.getOpenFileNames(
            self, translate("Choisir des images sur le disque"), "", _DISK_FILTER)
        if not paths:
            return
        # Proposer de les ranger : la bibliothèque s'enrichit au fil de l'eau.
        cols = lib.list_collections()
        if cols:
            reply = QMessageBox.question(
                self, translate("Bibliothèque d'images"),
                translate("Ajouter aussi ces images à la collection courante ?"),
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if reply == QMessageBox.StandardButton.Yes and self._current_key():
                copied = lib.add_images(self._current_key(), paths)
                if copied:
                    paths = copied   # on référence les copies pérennes
        self.picked = list(paths)
        self.accept()
