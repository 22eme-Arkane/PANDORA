"""Gallery dialog to pick a visual style reference image for Seedance generation."""
import os
import shutil

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFrame, QScrollArea, QWidget, QGridLayout, QFileDialog,
    QListWidget, QListWidgetItem,
)
from PyQt6.QtCore import Qt, QSize
from PyQt6.QtGui import QPixmap, QColor

from ui.styles import CP, PANDORA_STYLESHEET
import core.style as style_api

_THUMB_W   = 168
_THUMB_H   = 106
_GRID_COLS = 4
import sys as _sys
_ASSETS_ROOT = (os.path.join(_sys._MEIPASS, "assets") if getattr(_sys, "frozen", False)
                else os.path.join(os.path.dirname(os.path.dirname(__file__)), "assets"))
_STYLE_REFS_DIR = os.path.join(_ASSETS_ROOT, "style_refs")


# ── Image card ────────────────────────────────────────────────────────────────

class _ImageCard(QFrame):
    def __init__(self, image_path: str):
        super().__init__()
        self._path     = image_path
        self._selected = False
        self.setFixedSize(_THUMB_W, _THUMB_H + 4)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(2, 2, 2, 2)
        lay.setSpacing(0)

        self._img = QLabel()
        self._img.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._img.setFixedSize(_THUMB_W - 4, _THUMB_H - 4)
        pix = QPixmap(image_path)
        if not pix.isNull():
            pix = pix.scaled(
                _THUMB_W - 4, _THUMB_H - 4,
                Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                Qt.TransformationMode.SmoothTransformation,
            )
            # Centre-crop to fixed size
            dw = pix.width()  - (_THUMB_W - 4)
            dh = pix.height() - (_THUMB_H - 4)
            pix = pix.copy(max(0, dw // 2), max(0, dh // 2), _THUMB_W - 4, _THUMB_H - 4)
            self._img.setPixmap(pix)
        else:
            self._img.setText(os.path.basename(image_path))
            self._img.setStyleSheet(
                f"color:{CP['text_dim']};font-size:9px;background:{CP['bg3']};"
            )
        lay.addWidget(self._img)
        self._refresh_style()

    def _refresh_style(self):
        if self._selected:
            self.setStyleSheet(
                f"QFrame{{border:2px solid {CP['accent']};border-radius:6px;"
                f"background:{CP['accent_dim']};}}"
            )
        else:
            self.setStyleSheet(
                f"QFrame{{border:1px solid {CP['border']};border-radius:6px;"
                f"background:{CP['bg2']};}}"
                f"QFrame:hover{{border-color:{CP['border_bright']};}}"
            )

    def set_selected(self, v: bool):
        self._selected = v
        self._refresh_style()

    def path(self) -> str:
        return self._path

    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            self.set_selected(True)
            # Bubble up: parent grid widget handles deselecting siblings
            if hasattr(self.parent(), "_on_card_clicked"):
                self.parent()._on_card_clicked(self)

    def mouseDoubleClickEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            self.set_selected(True)
            if hasattr(self.parent(), "_on_card_double_clicked"):
                self.parent()._on_card_double_clicked(self)


# ── Image grid widget ─────────────────────────────────────────────────────────

class _ImageGrid(QWidget):
    def __init__(self):
        super().__init__()
        self.setStyleSheet("background:transparent;")
        self._cards:    list[_ImageCard] = []
        self._selected: _ImageCard | None = None

        self._lay = QGridLayout(self)
        self._lay.setContentsMargins(12, 12, 12, 12)
        self._lay.setSpacing(8)

    # Called by card on click
    def _on_card_clicked(self, card: _ImageCard):
        if self._selected and self._selected is not card:
            self._selected.set_selected(False)
        self._selected = card

    def _on_card_double_clicked(self, card: _ImageCard):
        self._on_card_clicked(card)
        # Propagate to dialog
        dlg = self.window()
        if isinstance(dlg, StyleGalleryDialog):
            dlg._confirm()

    def load_images(self, paths: list[str], preselected: str = ""):
        # Clear existing
        while self._lay.count():
            item = self._lay.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self._cards.clear()
        self._selected = None

        if not paths:
            lbl = QLabel(
                "Aucun template disponible pour ce style.\n\n"
                "Ajoutez des images en utilisant le bouton « + Ajouter un template »\n"
                "ou glissez vos fichiers dans le dossier :\n"
                f"assets/style_refs/{{style_key}}/"
            )
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lbl.setWordWrap(True)
            lbl.setStyleSheet(
                f"color:{CP['text_dim']};font-size:11px;background:transparent;"
            )
            self._lay.addWidget(lbl, 0, 0, 1, _GRID_COLS)
            return

        for i, path in enumerate(paths):
            card = _ImageCard(path)
            row, col = divmod(i, _GRID_COLS)
            self._lay.addWidget(card, row, col)
            self._cards.append(card)
            if path == preselected:
                card.set_selected(True)
                self._selected = card

        # Fill remaining columns in last row with spacers
        remainder = len(paths) % _GRID_COLS
        if remainder:
            for c in range(remainder, _GRID_COLS):
                sp = QWidget()
                sp.setFixedSize(_THUMB_W, _THUMB_H + 4)
                sp.setStyleSheet("background:transparent;")
                last_row = len(paths) // _GRID_COLS
                self._lay.addWidget(sp, last_row, c)

    def selected_path(self) -> str:
        return self._selected.path() if self._selected else ""


# ── Dialog ────────────────────────────────────────────────────────────────────

class StyleGalleryDialog(QDialog):
    def __init__(self, parent=None, current_style_key: str = "", current_ref_image: str = ""):
        super().__init__(parent)
        self.setWindowTitle("Templates de style")
        self.setFixedSize(980, 640)
        self.setStyleSheet(PANDORA_STYLESHEET + f"QDialog{{background:{CP['bg1']};}}")

        self._current_key  = current_style_key
        self._result_path  = ""   # filled on confirm

        main = QVBoxLayout(self)
        main.setContentsMargins(0, 0, 0, 0)
        main.setSpacing(0)

        # ── Header ──────────────────────────────────────────────────────────
        hdr = QWidget()
        hdr.setFixedHeight(52)
        hdr.setStyleSheet(f"background:{CP['bg2']};border-bottom:1px solid {CP['border']};")
        hl = QHBoxLayout(hdr)
        hl.setContentsMargins(20, 0, 20, 0)
        hl.setSpacing(12)
        title = QLabel("Choisir un template de style")
        title.setStyleSheet(
            f"color:{CP['text_primary']};font-size:13px;font-weight:700;background:transparent;"
        )
        hl.addWidget(title)
        hl.addStretch()
        hint = QLabel("L'image sera envoyée à Seedance comme 4ᵉ référence visuelle (style)")
        hint.setStyleSheet(f"color:{CP['text_dim']};font-size:10px;background:transparent;")
        hl.addWidget(hint)
        main.addWidget(hdr)

        # ── Body ────────────────────────────────────────────────────────────
        body = QWidget()
        body.setStyleSheet("background:transparent;")
        body_lay = QHBoxLayout(body)
        body_lay.setContentsMargins(0, 0, 0, 0)
        body_lay.setSpacing(0)

        # Left: style list
        self._list = QListWidget()
        self._list.setFixedWidth(242)
        self._list.setStyleSheet(
            f"QListWidget{{background:{CP['bg2']};border:none;"
            f"border-right:1px solid {CP['border']};outline:0;}}"
            f"QListWidget::item{{padding:6px 14px;color:{CP['text_secondary']};"
            f"font-size:12px;border:none;}}"
            f"QListWidget::item:selected{{background:rgba(78,205,196,0.14);"
            f"color:{CP['accent']};font-weight:700;}}"
            f"QListWidget::item:hover:!selected{{background:rgba(255,255,255,0.04);}}"
        )
        self._list.currentItemChanged.connect(self._on_style_changed)

        cur_group = None
        for s in style_api.STYLES:
            grp = s.get("group", "")
            if grp != cur_group:
                cur_group = grp
                gi = next((g for g in style_api.GROUPS if g["key"] == grp), None)
                if gi:
                    sep_item = QListWidgetItem(f"  {gi['icon']}  {gi['name'].upper()}")
                    sep_item.setFlags(Qt.ItemFlag.NoItemFlags)
                    sep_item.setForeground(QColor(CP.get("accent", "#4ecdc4")))
                    f = sep_item.font()
                    f.setPointSize(8)
                    f.setBold(True)
                    sep_item.setFont(f)
                    self._list.addItem(sep_item)
            item = QListWidgetItem(f"    {s['icon']}  {s['name']}")
            item.setData(Qt.ItemDataRole.UserRole, s["key"])
            self._list.addItem(item)

        body_lay.addWidget(self._list)

        # Right: image grid + add button
        right = QWidget()
        right.setStyleSheet("background:transparent;")
        right_lay = QVBoxLayout(right)
        right_lay.setContentsMargins(0, 0, 0, 0)
        right_lay.setSpacing(0)

        # Title bar of right panel
        self._right_title = QLabel("Sélectionne un style à gauche")
        self._right_title.setFixedHeight(38)
        self._right_title.setStyleSheet(
            f"color:{CP['text_secondary']};font-size:11px;font-weight:700;"
            f"padding:0 16px;background:{CP['bg2']};border-bottom:1px solid {CP['border']};"
        )
        right_lay.addWidget(self._right_title)

        # Scroll area for grid
        scroll = QScrollArea()
        scroll.setStyleSheet("QScrollArea{background:transparent;border:none;}")
        scroll.setWidgetResizable(True)
        self._grid = _ImageGrid()
        scroll.setWidget(self._grid)
        right_lay.addWidget(scroll, 1)

        # Add image row
        add_bar = QWidget()
        add_bar.setFixedHeight(46)
        add_bar.setStyleSheet(
            f"background:{CP['bg2']};border-top:1px solid {CP['border']};"
        )
        add_lay = QHBoxLayout(add_bar)
        add_lay.setContentsMargins(14, 0, 14, 0)
        add_lay.setSpacing(10)
        add_hint = QLabel("Ajoutez vos propres images de référence pour ce style :")
        add_hint.setStyleSheet(f"color:{CP['text_dim']};font-size:10px;background:transparent;")
        add_lay.addWidget(add_hint)
        add_lay.addStretch()
        btn_add = QPushButton("＋  Ajouter un template…")
        btn_add.setFixedHeight(30)
        btn_add.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_add.setStyleSheet(
            f"QPushButton{{background:transparent;color:{CP['text_secondary']};"
            f"border:1px solid {CP['border']};border-radius:5px;"
            f"font-size:10px;font-weight:700;padding:0 12px;}}"
            f"QPushButton:hover{{background:{CP['bg3']};color:{CP['text_primary']};"
            f"border-color:{CP['border_bright']};}}"
        )
        btn_add.clicked.connect(self._on_add_image)
        add_lay.addWidget(btn_add)
        right_lay.addWidget(add_bar)

        body_lay.addWidget(right, 1)
        main.addWidget(body, 1)

        # ── Footer ──────────────────────────────────────────────────────────
        footer = QWidget()
        footer.setFixedHeight(56)
        footer.setStyleSheet(
            f"background:{CP['bg2']};border-top:1px solid {CP['border']};"
        )
        fl = QHBoxLayout(footer)
        fl.setContentsMargins(20, 0, 20, 0)
        fl.setSpacing(10)

        self._selected_hint = QLabel("Aucune image sélectionnée")
        self._selected_hint.setStyleSheet(
            f"color:{CP['text_dim']};font-size:10px;background:transparent;"
        )
        fl.addWidget(self._selected_hint, 1)

        _ss_clear = (
            f"QPushButton{{background:transparent;color:{CP['red']};"
            f"border:1px solid rgba(255,79,106,0.40);border-radius:6px;"
            f"font-size:10px;font-weight:700;padding:0 14px;}}"
            f"QPushButton:hover{{background:rgba(255,79,106,0.10);}}"
        )
        btn_clear = QPushButton("✕  Retirer le template")
        btn_clear.setFixedHeight(34)
        btn_clear.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_clear.setStyleSheet(_ss_clear)
        btn_clear.clicked.connect(self._on_clear)
        fl.addWidget(btn_clear)

        _ss_cancel = (
            f"QPushButton{{background:transparent;color:{CP['text_secondary']};"
            f"border:1px solid {CP['border']};border-radius:6px;"
            f"font-size:10px;font-weight:700;padding:0 14px;}}"
            f"QPushButton:hover{{background:{CP['bg3']};color:{CP['text_primary']};}}"
        )
        btn_cancel = QPushButton("Annuler")
        btn_cancel.setFixedHeight(34)
        btn_cancel.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_cancel.setStyleSheet(_ss_cancel)
        btn_cancel.clicked.connect(self.reject)
        fl.addWidget(btn_cancel)

        _ss_confirm = (
            f"QPushButton{{background:{CP['accent']};color:#07080f;"
            f"border:none;border-radius:6px;"
            f"font-size:10px;font-weight:700;padding:0 18px;}}"
            f"QPushButton:hover{{background:#6eded6;}}"
            f"QPushButton:pressed{{background:#3bc0b8;}}"
        )
        self._btn_confirm = QPushButton("✓  Utiliser ce template")
        self._btn_confirm.setFixedHeight(34)
        self._btn_confirm.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_confirm.setStyleSheet(_ss_confirm)
        self._btn_confirm.setEnabled(False)
        self._btn_confirm.clicked.connect(self._confirm)
        fl.addWidget(self._btn_confirm)

        main.addWidget(footer)

        # Pre-select current style in list
        self._preselected_ref = current_ref_image
        if current_style_key:
            for i in range(self._list.count()):
                item = self._list.item(i)
                if item and item.data(Qt.ItemDataRole.UserRole) == current_style_key:
                    self._list.setCurrentItem(item)
                    break
        elif self._list.count() > 0:
            # Select first real style item
            for i in range(self._list.count()):
                item = self._list.item(i)
                if item and item.data(Qt.ItemDataRole.UserRole):
                    self._list.setCurrentItem(item)
                    break

    # ── Slots ─────────────────────────────────────────────────────────────────

    def _on_style_changed(self, current: QListWidgetItem, _prev):
        if not current:
            return
        key = current.data(Qt.ItemDataRole.UserRole)
        if not key:
            return
        self._current_key = key
        style = next((s for s in style_api.STYLES if s["key"] == key), {})
        icon  = style.get("icon", "")
        name  = style.get("name", key)
        self._right_title.setText(f"  {icon}  {name}")
        images = style_api.get_style_ref_images_for_key(key)
        saved  = style_api.get_style_ref_image_for_key(key)
        pre    = saved if saved else (self._preselected_ref if key == self._current_key else "")
        self._grid.load_images(images, preselected=pre)
        self._update_confirm_btn()

    def _update_confirm_btn(self):
        sel = self._grid.selected_path()
        if sel:
            fname = os.path.basename(sel)
            self._selected_hint.setText(f"Sélectionnée : {fname}")
            self._btn_confirm.setEnabled(True)
        else:
            self._selected_hint.setText("Aucune image sélectionnée")
            self._btn_confirm.setEnabled(False)
        # Poll grid on each paint (lightweight)
        from PyQt6.QtCore import QTimer
        QTimer.singleShot(200, self._update_confirm_btn)

    def _on_add_image(self):
        if not self._current_key:
            return
        paths, _ = QFileDialog.getOpenFileNames(
            self,
            "Choisir des images de référence",
            "",
            "Images (*.jpg *.jpeg *.png *.webp)",
        )
        if not paths:
            return
        dest_dir = os.path.join(_STYLE_REFS_DIR, self._current_key)
        os.makedirs(dest_dir, exist_ok=True)
        added = []
        for src in paths:
            fname = os.path.basename(src)
            dst   = os.path.join(dest_dir, fname)
            # Avoid overwrite collision
            if os.path.exists(dst) and os.path.abspath(src) != os.path.abspath(dst):
                base, ext = os.path.splitext(fname)
                i = 1
                while os.path.exists(dst):
                    dst = os.path.join(dest_dir, f"{base}_{i}{ext}")
                    i  += 1
            if os.path.abspath(src) != os.path.abspath(dst):
                shutil.copy2(src, dst)
            added.append(dst)
        # Reload grid, pre-select last added
        images = style_api.get_style_ref_images_for_key(self._current_key)
        self._grid.load_images(images, preselected=added[-1] if added else "")

    def _on_clear(self):
        self._result_path = ""
        self.accept()

    def _confirm(self):
        self._result_path = self._grid.selected_path()
        if self._result_path:
            self.accept()

    # ── Public ────────────────────────────────────────────────────────────────

    def result_path(self) -> str:
        """Returns the chosen image path, or '' if cleared/cancelled."""
        return self._result_path

    def was_cleared(self) -> bool:
        return self.result() == QDialog.DialogCode.Accepted and self._result_path == ""
