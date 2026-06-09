"""
ui/page_live_assets.py — Page générique Casting / Accessoires / Véhicules pour Live.

Master-détail : liste à gauche, éditeur à droite (nom, catégorie, description,
galerie d'images avec génération Nano Banana + ajout manuel).

Données dédiées Live et isolées par projet (core/live_assets.py).
Une seule classe paramétrée par `kind` ∈ {"casting","accessoires","vehicules"}.
"""

import os
import shutil

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QLineEdit,
    QTextEdit, QScrollArea, QFrame, QFileDialog, QMessageBox, QProgressBar,
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QPixmap

from ui.styles import CP
from core.i18n import translate
import core.live_assets as la


_KINDS = {
    "casting": {
        "title": "Casting", "hint": "character", "add": "Ajouter un personnage",
        "name_ph": "Nom du personnage", "cat_ph": "Rôle / type",
        "desc_ph": "Apparence, costume, style visuel…",
    },
    "accessoires": {
        "title": "Accessoires", "hint": "accessory", "add": "Ajouter un accessoire",
        "name_ph": "Nom de l'accessoire", "cat_ph": "Catégorie",
        "desc_ph": "Matière, couleur, état…",
    },
    "vehicules": {
        "title": "Véhicules", "hint": "vehicle", "add": "Ajouter un véhicule",
        "name_ph": "Nom du véhicule", "cat_ph": "Catégorie",
        "desc_ph": "Marque, modèle, couleur, état…",
    },
}


# ── Vignette d'image avec bouton retirer ────────────────────────────────────

class _ImgThumb(QFrame):
    removed = pyqtSignal(str)

    def __init__(self, path: str):
        super().__init__()
        self._path = path
        self.setFixedSize(84, 84)
        self.setStyleSheet(
            f"QFrame{{background:{CP['bg3']};border:1px solid {CP['border']};border-radius:6px;}}"
        )
        lbl = QLabel(self)
        lbl.setGeometry(2, 2, 80, 80)
        lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl.setStyleSheet("border:none;background:transparent;")
        if path and os.path.isfile(path):
            pix = QPixmap(path).scaled(
                80, 80, Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                Qt.TransformationMode.SmoothTransformation)
            lbl.setPixmap(pix)
        else:
            lbl.setText("—")
        btn = QPushButton("×", self)
        btn.setFixedSize(16, 16)
        btn.move(66, 2)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.setStyleSheet(
            f"QPushButton{{background:{CP['bg2']};color:{CP['text_dim']};"
            f"border:1px solid {CP['border']};border-radius:3px;font-size:9px;}}"
            f"QPushButton:hover{{color:#e05c5c;border-color:#e05c5c;}}"
        )
        btn.clicked.connect(lambda: self.removed.emit(self._path))


# ── Page ────────────────────────────────────────────────────────────────────

class PageLiveAssets(QWidget):
    """CRUD générique d'un type d'asset Live (casting/accessoires/véhicules)."""

    def __init__(self, kind: str):
        super().__init__()
        self._kind = kind
        self._cfg  = _KINDS.get(kind, _KINDS["casting"])
        self._current: dict | None = None
        self._workers: list = []

        self.setStyleSheet(f"background:{CP['bg0']};")
        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        root.addWidget(self._build_list_panel())
        root.addWidget(self._build_editor_panel(), 1)

        self._reload_list()
        self._set_editor_enabled(False)

    # ── Panneau liste ────────────────────────────────────────────────────────

    def _build_list_panel(self) -> QWidget:
        panel = QWidget()
        panel.setFixedWidth(300)
        panel.setStyleSheet(f"background:{CP['bg1']};border-right:1px solid {CP['border']};")
        lay = QVBoxLayout(panel)
        lay.setContentsMargins(16, 18, 16, 16)
        lay.setSpacing(12)

        title = QLabel(translate(self._cfg["title"]))
        title.setStyleSheet(
            f"color:{CP['text_primary']};font-size:18px;font-weight:800;background:transparent;border:none;"
        )
        lay.addWidget(title)

        btn_add = QPushButton("＋  " + translate(self._cfg["add"]))
        btn_add.setFixedHeight(38)
        btn_add.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_add.setStyleSheet(
            f"QPushButton{{background:transparent;color:{CP['accent2']};"
            f"border:1.5px solid {CP['accent2']};border-radius:8px;"
            f"font-size:12px;font-weight:700;padding:0 12px;}}"
            f"QPushButton:hover{{background:rgba(124,107,255,0.12);}}"
        )
        btn_add.clicked.connect(self._on_add)
        lay.addWidget(btn_add)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet("QScrollArea{background:transparent;border:none;}")
        self._list_container = QWidget()
        self._list_container.setStyleSheet("background:transparent;")
        self._list_lay = QVBoxLayout(self._list_container)
        self._list_lay.setContentsMargins(0, 0, 0, 0)
        self._list_lay.setSpacing(6)
        self._list_lay.setAlignment(Qt.AlignmentFlag.AlignTop)
        scroll.setWidget(self._list_container)
        lay.addWidget(scroll, 1)
        return panel

    def _reload_list(self):
        while self._list_lay.count():
            it = self._list_lay.takeAt(0)
            if it.widget():
                it.widget().deleteLater()
        items = la.list_assets(self._kind)
        if not items:
            empty = QLabel(translate("Aucun élément. Cliquez « + » pour en créer un."))
            empty.setWordWrap(True)
            empty.setStyleSheet(f"color:{CP['text_dim']};font-size:11px;background:transparent;")
            self._list_lay.addWidget(empty)
            return
        for asset in items:
            self._list_lay.addWidget(self._make_row(asset))

    def _make_row(self, asset: dict) -> QWidget:
        row = QPushButton()
        row.setCursor(Qt.CursorShape.PointingHandCursor)
        row.setFixedHeight(54)
        active = self._current and self._current.get("id") == asset.get("id")
        row.setStyleSheet(
            f"QPushButton{{background:{'rgba(124,107,255,0.15)' if active else CP['bg2']};"
            f"color:{CP['text_primary']};text-align:left;padding:0 12px;"
            f"border:1px solid {CP['accent2'] if active else CP['border']};border-radius:8px;"
            f"font-size:12px;font-weight:600;}}"
            f"QPushButton:hover{{border-color:{CP['border_bright']};}}"
        )
        imgs = asset.get("images", [])
        name = asset.get("name", "(sans nom)")
        cat  = asset.get("category", "")
        row.setText(f"{name}" + (f"   ·  {cat}" if cat else "") + (f"      🖼 {len(imgs)}" if imgs else ""))
        row.clicked.connect(lambda: self._select(asset))
        return row

    # ── Panneau éditeur ──────────────────────────────────────────────────────

    def _build_editor_panel(self) -> QWidget:
        panel = QScrollArea()
        panel.setWidgetResizable(True)
        panel.setStyleSheet("QScrollArea{background:transparent;border:none;}")
        inner = QWidget()
        inner.setStyleSheet("background:transparent;")
        panel.setWidget(inner)
        lay = QVBoxLayout(inner)
        lay.setContentsMargins(32, 24, 32, 24)
        lay.setSpacing(16)

        def _lbl(t):
            l = QLabel(translate(t))
            l.setStyleSheet(f"color:{CP['text_secondary']};font-size:11px;background:transparent;border:none;")
            return l

        def _input_style():
            return (
                f"QLineEdit,QTextEdit{{background:{CP['bg3']};border:1px solid {CP['border']};"
                f"border-radius:6px;color:{CP['text_primary']};font-size:13px;padding:6px 10px;}}"
                f"QLineEdit:focus,QTextEdit:focus{{border-color:{CP['accent2']};}}"
            )

        self._ed_title = QLabel(translate("Nouvel élément"))
        self._ed_title.setStyleSheet(
            f"color:{CP['text_primary']};font-size:20px;font-weight:800;background:transparent;border:none;"
        )
        lay.addWidget(self._ed_title)

        lay.addWidget(_lbl("Nom"))
        self._name = QLineEdit()
        self._name.setPlaceholderText(translate(self._cfg["name_ph"]))
        self._name.setFixedHeight(38)
        self._name.setStyleSheet(_input_style())
        lay.addWidget(self._name)

        lay.addWidget(_lbl("Catégorie"))
        self._category = QLineEdit()
        self._category.setPlaceholderText(translate(self._cfg["cat_ph"]))
        self._category.setFixedHeight(38)
        self._category.setStyleSheet(_input_style())
        lay.addWidget(self._category)

        lay.addWidget(_lbl("Description"))
        self._desc = QTextEdit()
        self._desc.setPlaceholderText(translate(self._cfg["desc_ph"]))
        self._desc.setMinimumHeight(90)
        self._desc.setMaximumHeight(150)
        self._desc.setStyleSheet(_input_style())
        lay.addWidget(self._desc)

        # ── Images ───────────────────────────────────────────────────────────
        lay.addWidget(_lbl("Images de référence"))
        self._imgs_row = QHBoxLayout()
        self._imgs_row.setSpacing(8)
        self._imgs_row.setAlignment(Qt.AlignmentFlag.AlignLeft)
        _imgs_wrap = QWidget()
        _imgs_wrap.setStyleSheet("background:transparent;")
        _imgs_wrap.setLayout(self._imgs_row)
        lay.addWidget(_imgs_wrap)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)
        self._btn_gen = QPushButton("✦  " + translate("Générer une image"))
        self._btn_gen.setFixedHeight(34)
        self._btn_gen.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_gen.setStyleSheet(
            f"QPushButton{{background:{CP['accent2']};color:#fff;border:none;border-radius:7px;"
            f"font-size:11px;font-weight:700;padding:0 14px;}}"
            f"QPushButton:hover{{background:#8f80ff;}}"
            f"QPushButton:disabled{{background:{CP['bg3']};color:{CP['text_dim']};}}"
        )
        self._btn_gen.clicked.connect(self._on_generate)
        btn_row.addWidget(self._btn_gen)

        btn_addimg = QPushButton("＋  " + translate("Ajouter une image"))
        btn_addimg.setFixedHeight(34)
        btn_addimg.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_addimg.setStyleSheet(
            f"QPushButton{{background:transparent;color:{CP['text_secondary']};"
            f"border:1px solid {CP['border']};border-radius:7px;font-size:11px;font-weight:700;padding:0 12px;}}"
            f"QPushButton:hover{{background:{CP['bg2']};color:{CP['text_primary']};}}"
        )
        btn_addimg.clicked.connect(self._on_add_image)
        btn_row.addWidget(btn_addimg)
        btn_row.addStretch()
        lay.addLayout(btn_row)

        self._gen_progress = QProgressBar()
        self._gen_progress.setFixedHeight(5)
        self._gen_progress.setTextVisible(False)
        self._gen_progress.setStyleSheet(
            f"QProgressBar{{background:{CP['bg3']};border-radius:2px;border:none;}}"
            f"QProgressBar::chunk{{background:{CP['accent2']};border-radius:2px;}}"
        )
        self._gen_progress.hide()
        lay.addWidget(self._gen_progress)

        self._gen_status = QLabel("")
        self._gen_status.setStyleSheet(
            f"color:{CP['text_dim']};font-size:10px;font-family:'Consolas',monospace;background:transparent;"
        )
        self._gen_status.hide()
        lay.addWidget(self._gen_status)

        lay.addStretch()

        # ── Actions ──────────────────────────────────────────────────────────
        actions = QHBoxLayout()
        actions.setSpacing(10)
        self._btn_save = QPushButton(translate("Enregistrer"))
        self._btn_save.setFixedHeight(40)
        self._btn_save.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_save.setStyleSheet(
            f"QPushButton{{background:{CP['accent']};color:#07080f;border:none;border-radius:8px;"
            f"font-size:12px;font-weight:700;padding:0 22px;}}"
            f"QPushButton:hover{{background:#6eded6;}}"
        )
        self._btn_save.clicked.connect(self._on_save)
        actions.addWidget(self._btn_save)

        self._btn_delete = QPushButton(translate("Supprimer"))
        self._btn_delete.setFixedHeight(40)
        self._btn_delete.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_delete.setStyleSheet(
            f"QPushButton{{background:transparent;color:#e05c5c;border:1px solid rgba(224,92,92,0.5);"
            f"border-radius:8px;font-size:12px;font-weight:700;padding:0 18px;}}"
            f"QPushButton:hover{{background:rgba(224,92,92,0.10);}}"
        )
        self._btn_delete.clicked.connect(self._on_delete)
        actions.addWidget(self._btn_delete)
        actions.addStretch()
        lay.addLayout(actions)
        return panel

    # ── Sélection / état ─────────────────────────────────────────────────────

    def _set_editor_enabled(self, on: bool):
        for w in (self._name, self._category, self._desc, self._btn_gen,
                  self._btn_save, self._btn_delete):
            w.setEnabled(on)

    def _select(self, asset: dict):
        self._current = asset
        self._name.setText(asset.get("name", ""))
        self._category.setText(asset.get("category", ""))
        self._desc.setPlainText(asset.get("description", ""))
        self._ed_title.setText(asset.get("name") or translate("Nouvel élément"))
        self._set_editor_enabled(True)
        self._refresh_images()
        self._reload_list()

    def _on_add(self):
        self._select({"id": "", "name": "", "category": "", "description": "", "images": []})
        self._ed_title.setText(translate("Nouvel élément"))
        self._name.setFocus()

    def _refresh_images(self):
        while self._imgs_row.count():
            it = self._imgs_row.takeAt(0)
            if it.widget():
                it.widget().deleteLater()
        for p in (self._current or {}).get("images", []):
            th = _ImgThumb(p)
            th.removed.connect(self._on_remove_image)
            self._imgs_row.addWidget(th)

    # ── Enregistrer / supprimer ──────────────────────────────────────────────

    def _collect(self) -> dict:
        a = dict(self._current or {})
        a["name"]        = self._name.text().strip()
        a["category"]    = self._category.text().strip()
        a["description"] = self._desc.toPlainText().strip()
        a.setdefault("images", [])
        return a

    def _on_save(self):
        a = self._collect()
        if not a["name"]:
            QMessageBox.warning(self, translate("Nom requis"), translate("Donnez un nom à l'élément."))
            return
        saved = la.upsert_asset(self._kind, a)
        self._current = saved
        self._ed_title.setText(saved.get("name"))
        self._reload_list()

    def _on_delete(self):
        if not self._current or not self._current.get("id"):
            self._current = None
            self._set_editor_enabled(False)
            self._name.clear(); self._category.clear(); self._desc.clear()
            self._refresh_images()
            return
        la.delete_asset(self._kind, self._current["id"])
        self._current = None
        self._name.clear(); self._category.clear(); self._desc.clear()
        self._ed_title.setText(translate("Nouvel élément"))
        self._set_editor_enabled(False)
        self._refresh_images()
        self._reload_list()

    # ── Images : ajout manuel ────────────────────────────────────────────────

    def _ensure_saved(self) -> bool:
        """S'assure que l'asset courant est enregistré (a un id)."""
        if self._current is None:
            return False
        if not self._current.get("id"):
            if not self._name.text().strip():
                QMessageBox.warning(self, translate("Nom requis"),
                                    translate("Donnez un nom avant d'ajouter des images."))
                return False
            self._on_save()
        return bool(self._current and self._current.get("id"))

    def _on_add_image(self):
        if not self._ensure_saved():
            return
        paths, _ = QFileDialog.getOpenFileNames(
            self, translate("Choisir une ou plusieurs images"), "",
            "Images (*.png *.jpg *.jpeg *.webp *.bmp)")
        if not paths:
            return
        dest_dir = la.images_dir(self._kind)
        for p in paths:
            try:
                dst = os.path.join(dest_dir, os.path.basename(p))
                if os.path.abspath(p) != os.path.abspath(dst):
                    shutil.copy2(p, dst)
                self._current.setdefault("images", []).append(dst)
            except Exception:
                pass
        la.upsert_asset(self._kind, self._current)
        self._refresh_images()
        self._reload_list()

    def _on_remove_image(self, path: str):
        if not self._current:
            return
        self._current["images"] = [p for p in self._current.get("images", []) if p != path]
        if self._current.get("id"):
            la.upsert_asset(self._kind, self._current)
        self._refresh_images()
        self._reload_list()

    # ── Génération Nano Banana ───────────────────────────────────────────────

    def _on_generate(self):
        if not self._ensure_saved():
            return
        desc = self._desc.toPlainText().strip()
        name = self._name.text().strip()
        if not desc:
            QMessageBox.warning(self, translate("Description requise"),
                                translate("Décrivez l'élément pour générer une image."))
            return
        from api.nano_banana import GenerateItemWorker
        self._btn_gen.setEnabled(False)
        self._gen_progress.setValue(0); self._gen_progress.show()
        self._gen_status.show(); self._gen_status.setText(translate("Génération en cours…"))

        w = GenerateItemWorker(
            prompt=desc, item_name=name or "live",
            subdir=la.subdir(self._kind), num_images=1,
            subject_hint=self._cfg["hint"],
        )
        w.progress.connect(self._on_gen_progress)
        w.finished.connect(self._on_gen_finished)
        w.failed.connect(self._on_gen_failed)
        w.finished.connect(lambda *_: self._cleanup_worker(w))
        w.failed.connect(lambda *_: self._cleanup_worker(w))
        self._workers.append(w)
        w.start()

    def _on_gen_progress(self, pct: int, msg: str):
        self._gen_progress.setValue(pct)
        self._gen_status.setText(translate(msg))

    def _on_gen_finished(self, path: str):
        self._btn_gen.setEnabled(True)
        self._gen_progress.hide()
        if path and os.path.isfile(path):
            self._current.setdefault("images", []).append(path)
            la.upsert_asset(self._kind, self._current)
            self._gen_status.setText("✓  " + os.path.basename(path))
            self._refresh_images()
            self._reload_list()
        else:
            self._gen_status.setText("✓  " + translate("Terminé (mode démo — aucune clé fal.ai)"))

    def _on_gen_failed(self, err: str):
        self._btn_gen.setEnabled(True)
        self._gen_progress.hide()
        self._gen_status.setText(f"✗  {err[:120]}")

    def _cleanup_worker(self, w):
        try:
            self._workers.remove(w)
        except ValueError:
            pass
