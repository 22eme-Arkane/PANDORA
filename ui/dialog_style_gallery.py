"""Gallery dialog to pick a visual style reference image for Seedance generation."""
import os
import shutil

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFrame, QScrollArea, QWidget, QGridLayout, QFileDialog,
    QInputDialog,
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPixmap

from ui.styles import CP, PANDORA_STYLESHEET
import core.style as style_api

_THUMB_W   = 168
_THUMB_H   = 106
_GRID_COLS = 4

import sys as _sys
from core.paths import APP_ROOT as _APP_ROOT
# Write dir: always writable (LOCALAPPDATA in frozen, project root in dev)
_STYLE_REFS_DIR = os.path.join(_APP_ROOT, "assets", "style_refs")


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

    def _on_card_clicked(self, card: _ImageCard):
        if self._selected and self._selected is not card:
            self._selected.set_selected(False)
        self._selected = card

    def _on_card_double_clicked(self, card: _ImageCard):
        self._on_card_clicked(card)
        dlg = self.window()
        if isinstance(dlg, StyleGalleryDialog):
            dlg._confirm()

    def load_images(self, paths: list[str], preselected: str = ""):
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
        self.setStyleSheet(PANDORA_STYLESHEET + f"QDialog{{background:{CP['bg1']};}}")
        from ui.widgets import fit_dialog_to_screen
        fit_dialog_to_screen(self, 0.65, 0.84, 720, 500)

        self._current_key     = current_style_key
        self._selected_key    = current_style_key
        self._result_path     = ""
        self._preselected_ref = current_ref_image
        self._style_btns: dict[str, QPushButton] = {}

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

        # ── Left: collapsible style tree ──────────────────────────────────
        left = QWidget()
        left.setFixedWidth(242)
        left.setStyleSheet(
            f"background:{CP['bg2']};border-right:1px solid {CP['border']};"
        )
        left_main = QVBoxLayout(left)
        left_main.setContentsMargins(0, 0, 0, 0)
        left_main.setSpacing(0)

        scroll_left = QScrollArea()
        scroll_left.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll_left.setWidgetResizable(True)
        scroll_left.setStyleSheet("QScrollArea{background:transparent;border:none;}")

        tree_container = QWidget()
        tree_container.setStyleSheet("background:transparent;")
        self._tree_lay = QVBoxLayout(tree_container)
        self._tree_lay.setContentsMargins(0, 4, 0, 4)
        self._tree_lay.setSpacing(0)

        # Standard groups
        for g in style_api.GROUPS:
            styles = [s for s in style_api.STYLES if s.get("group") == g["key"]]
            if not styles:
                continue
            self._add_section(g["name"].upper(), g["icon"], styles, expanded=True)

        # Custom categories section (always built, shown only when populated)
        self._custom_hdr = QPushButton("  ▼  ✦  MES STYLES")
        self._custom_hdr.setFixedHeight(28)
        self._custom_hdr.setCursor(Qt.CursorShape.PointingHandCursor)
        self._custom_hdr.setStyleSheet(self._group_hdr_style())

        self._custom_container = QWidget()
        self._custom_container.setStyleSheet("background:transparent;")
        self._custom_cont_lay = QVBoxLayout(self._custom_container)
        self._custom_cont_lay.setContentsMargins(0, 0, 0, 0)
        self._custom_cont_lay.setSpacing(0)

        self._populate_custom_section()

        _exp_c = [True]
        def _toggle_custom():
            _exp_c[0] = not _exp_c[0]
            self._custom_container.setVisible(_exp_c[0])
            arrow = "▼" if _exp_c[0] else "▶"
            self._custom_hdr.setText(f"  {arrow}  ✦  MES STYLES")
        self._custom_hdr.clicked.connect(_toggle_custom)

        # Show custom section only if there are items
        _has_custom = self._custom_cont_lay.count() > 0
        self._custom_hdr.setVisible(_has_custom)
        self._custom_container.setVisible(_has_custom)

        self._tree_lay.addWidget(self._custom_hdr)
        self._tree_lay.addWidget(self._custom_container)
        self._tree_lay.addStretch()

        scroll_left.setWidget(tree_container)
        left_main.addWidget(scroll_left, 1)

        # "＋ Nouvelle catégorie" button
        btn_new_cat = QPushButton("＋  Nouvelle catégorie")
        btn_new_cat.setFixedHeight(36)
        btn_new_cat.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_new_cat.setStyleSheet(
            f"QPushButton{{background:transparent;color:{CP['accent']};"
            f"border:none;border-top:1px solid {CP['border']};"
            f"font-size:10px;font-weight:700;padding:0 14px;text-align:left;}}"
            f"QPushButton:hover{{background:{CP['bg3']};color:{CP['text_primary']};}}"
        )
        btn_new_cat.clicked.connect(self._on_new_category)
        left_main.addWidget(btn_new_cat)

        body_lay.addWidget(left)

        # ── Right: image grid + add button ────────────────────────────────
        right = QWidget()
        right.setStyleSheet("background:transparent;")
        right_lay = QVBoxLayout(right)
        right_lay.setContentsMargins(0, 0, 0, 0)
        right_lay.setSpacing(0)

        self._right_title = QLabel("Sélectionne un style à gauche")
        self._right_title.setFixedHeight(38)
        self._right_title.setStyleSheet(
            f"color:{CP['text_secondary']};font-size:11px;font-weight:700;"
            f"padding:0 16px;background:{CP['bg2']};border-bottom:1px solid {CP['border']};"
        )
        right_lay.addWidget(self._right_title)

        scroll = QScrollArea()
        scroll.setStyleSheet("QScrollArea{background:transparent;border:none;}")
        scroll.setWidgetResizable(True)
        self._grid = _ImageGrid()
        scroll.setWidget(self._grid)
        right_lay.addWidget(scroll, 1)

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

        btn_clear = QPushButton("✕  Retirer le template")
        btn_clear.setFixedHeight(34)
        btn_clear.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_clear.setStyleSheet(
            f"QPushButton{{background:transparent;color:{CP['red']};"
            f"border:1px solid rgba(255,79,106,0.40);border-radius:6px;"
            f"font-size:10px;font-weight:700;padding:0 14px;}}"
            f"QPushButton:hover{{background:rgba(255,79,106,0.10);}}"
        )
        btn_clear.clicked.connect(self._on_clear)
        fl.addWidget(btn_clear)

        btn_cancel = QPushButton("Annuler")
        btn_cancel.setFixedHeight(34)
        btn_cancel.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_cancel.setStyleSheet(
            f"QPushButton{{background:transparent;color:{CP['text_secondary']};"
            f"border:1px solid {CP['border']};border-radius:6px;"
            f"font-size:10px;font-weight:700;padding:0 14px;}}"
            f"QPushButton:hover{{background:{CP['bg3']};color:{CP['text_primary']};}}"
        )
        btn_cancel.clicked.connect(self.reject)
        fl.addWidget(btn_cancel)

        self._btn_confirm = QPushButton("✓  Utiliser ce template")
        self._btn_confirm.setFixedHeight(34)
        self._btn_confirm.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_confirm.setStyleSheet(
            f"QPushButton{{background:{CP['accent']};color:#07080f;"
            f"border:none;border-radius:6px;"
            f"font-size:10px;font-weight:700;padding:0 18px;}}"
            f"QPushButton:hover{{background:#6eded6;}}"
            f"QPushButton:pressed{{background:#3bc0b8;}}"
        )
        self._btn_confirm.setEnabled(False)
        self._btn_confirm.clicked.connect(self._confirm)
        fl.addWidget(self._btn_confirm)

        main.addWidget(footer)

        # Pre-select
        if current_style_key and current_style_key in self._style_btns:
            self._select_style(current_style_key, emit=False)
        elif self._style_btns:
            first_key = next(iter(self._style_btns))
            self._select_style(first_key, emit=False)

    # ── Style helpers ─────────────────────────────────────────────────────────

    def _group_hdr_style(self) -> str:
        return (
            f"QPushButton{{background:{CP['bg3']};color:{CP['accent']};"
            f"border:none;border-top:1px solid {CP['border']};"
            f"font-size:9px;font-weight:700;text-align:left;padding:0 8px;}}"
            f"QPushButton:hover{{background:rgba(78,205,196,0.08);}}"
        )

    def _item_style(self, selected: bool) -> str:
        if selected:
            return (
                f"QPushButton{{background:rgba(78,205,196,0.14);color:{CP['accent']};"
                f"border:none;font-size:12px;font-weight:700;text-align:left;padding:0 14px;}}"
            )
        return (
            f"QPushButton{{background:transparent;color:{CP['text_secondary']};"
            f"border:none;font-size:12px;font-weight:400;text-align:left;padding:0 14px;}}"
            f"QPushButton:hover{{background:rgba(255,255,255,0.04);"
            f"color:{CP['text_primary']};}}"
        )

    # ── Tree building ─────────────────────────────────────────────────────────

    def _add_section(self, label: str, icon: str, styles: list, expanded: bool = True):
        hdr = QPushButton(f"  {'▼' if expanded else '▶'}  {icon}  {label}")
        hdr.setFixedHeight(28)
        hdr.setCursor(Qt.CursorShape.PointingHandCursor)
        hdr.setStyleSheet(self._group_hdr_style())

        container = QWidget()
        container.setStyleSheet("background:transparent;")
        cont_lay = QVBoxLayout(container)
        cont_lay.setContentsMargins(0, 0, 0, 0)
        cont_lay.setSpacing(0)

        for s in styles:
            btn = self._make_style_btn(s["key"], s["icon"], s["name"])
            cont_lay.addWidget(btn)

        container.setVisible(expanded)
        _exp = [expanded]

        def _toggle():
            _exp[0] = not _exp[0]
            container.setVisible(_exp[0])
            arrow = "▼" if _exp[0] else "▶"
            hdr.setText(f"  {arrow}  {icon}  {label}")
        hdr.clicked.connect(_toggle)

        self._tree_lay.addWidget(hdr)
        self._tree_lay.addWidget(container)

    def _populate_custom_section(self):
        if not os.path.isdir(_STYLE_REFS_DIR):
            return
        known = {s["key"] for s in style_api.STYLES}
        for name in sorted(os.listdir(_STYLE_REFS_DIR)):
            folder = os.path.join(_STYLE_REFS_DIR, name)
            if os.path.isdir(folder) and name not in known and name not in self._style_btns:
                display = name.replace("_", " ").title()
                btn = self._make_style_btn(name, "✦", display)
                self._custom_cont_lay.addWidget(btn)

    def _make_style_btn(self, key: str, icon: str, name: str) -> QPushButton:
        selected = (key == self._selected_key)
        btn = QPushButton(f"    {icon}  {name}")
        btn.setFixedHeight(34)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.setStyleSheet(self._item_style(selected))
        btn.clicked.connect(lambda: self._select_style(key))
        self._style_btns[key] = btn
        return btn

    # ── Selection ─────────────────────────────────────────────────────────────

    def _select_style(self, key: str, emit: bool = True):
        if self._selected_key and self._selected_key in self._style_btns:
            self._style_btns[self._selected_key].setStyleSheet(self._item_style(False))
        self._selected_key = key
        if key in self._style_btns:
            self._style_btns[key].setStyleSheet(self._item_style(True))
        if emit:
            self._load_style_images(key)

    def _load_style_images(self, key: str):
        self._current_key = key
        style = next((s for s in style_api.STYLES if s["key"] == key), None)
        if style:
            icon = style.get("icon", "")
            name = style.get("name", key)
        else:
            name = key.replace("_", " ").title()
            icon = "✦"
        self._right_title.setText(f"  {icon}  {name}")
        images = style_api.get_style_ref_images_for_key(key)
        saved  = style_api.get_style_ref_image_for_key(key)
        pre    = saved if saved else (self._preselected_ref if key == self._current_key else "")
        self._grid.load_images(images, preselected=pre)
        self._update_confirm_btn()

    # ── Slots ─────────────────────────────────────────────────────────────────

    def _update_confirm_btn(self):
        sel = self._grid.selected_path()
        if sel:
            fname = os.path.basename(sel)
            self._selected_hint.setText(f"Sélectionnée : {fname}")
            self._btn_confirm.setEnabled(True)
        else:
            self._selected_hint.setText("Aucune image sélectionnée")
            self._btn_confirm.setEnabled(False)
        from PyQt6.QtCore import QTimer
        QTimer.singleShot(200, self._update_confirm_btn)

    def _on_add_image(self):
        if not self._current_key:
            return
        # Porte unique : bibliothèque globale (disque accessible depuis le dialog) —
        # l'image choisie est ensuite COPIÉE dans la catégorie de templates.
        from ui.dialog_image_library import ImageLibraryDialog
        paths = ImageLibraryDialog.pick(self)
        if not paths:
            return
        dest_dir = os.path.join(_STYLE_REFS_DIR, self._current_key)
        os.makedirs(dest_dir, exist_ok=True)
        added = []
        for src in paths:
            fname = os.path.basename(src)
            dst   = os.path.join(dest_dir, fname)
            if os.path.exists(dst) and os.path.abspath(src) != os.path.abspath(dst):
                base, ext = os.path.splitext(fname)
                i = 1
                while os.path.exists(dst):
                    dst = os.path.join(dest_dir, f"{base}_{i}{ext}")
                    i  += 1
            if os.path.abspath(src) != os.path.abspath(dst):
                shutil.copy2(src, dst)
            added.append(dst)
        images = style_api.get_style_ref_images_for_key(self._current_key)
        self._grid.load_images(images, preselected=added[-1] if added else "")

    def _on_new_category(self):
        name, ok = QInputDialog.getText(
            self, "Nouvelle catégorie", "Nom de la catégorie :"
        )
        if not ok or not name.strip():
            return
        clean = name.strip()
        slug  = clean.lower().replace(" ", "_")
        slug  = "".join(c for c in slug if c.isalnum() or c == "_")
        if not slug:
            return
        folder = os.path.join(_STYLE_REFS_DIR, slug)
        os.makedirs(folder, exist_ok=True)
        if slug not in self._style_btns:
            display = clean.title()
            btn = self._make_style_btn(slug, "✦", display)
            self._custom_cont_lay.addWidget(btn)
        # Make the custom section visible
        self._custom_hdr.setVisible(True)
        self._custom_container.setVisible(True)
        self._select_style(slug)

    def _on_clear(self):
        self._result_path = ""
        self.accept()

    def _confirm(self):
        self._result_path = self._grid.selected_path()
        if self._result_path:
            self.accept()

    # ── Public ────────────────────────────────────────────────────────────────

    def result_path(self) -> str:
        return self._result_path

    def was_cleared(self) -> bool:
        return self.result() == QDialog.DialogCode.Accepted and self._result_path == ""
