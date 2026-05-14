import os
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QScrollArea, QGridLayout, QLineEdit, QFrame, QMessageBox,
    QFileDialog,
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QPixmap, QPixmapCache, QColor
from ui.styles import CP
from ui.icons import load_icon
from ui.widgets import HelpBlock
import core.casting as casting_api
from ui.dialog_character import CharacterDialog
import shutil, time as _time


# ── Carte personnage ──────────────────────────────────────────────────────────

class CharacterCard(QWidget):
    edit_requested   = pyqtSignal(dict)
    delete_requested = pyqtSignal(str)

    _W = 162
    _H_IMG = 190
    _H_INFO = 56
    _H = _H_IMG + _H_INFO

    def __init__(self, data: dict):
        super().__init__()
        self._data = data
        self.setFixedSize(self._W, self._H)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)

        # ── Portrait ──────────────────────────────────────────────────────────
        self._thumb = QLabel()
        self._thumb.setFixedSize(self._W, self._H_IMG)
        self._thumb.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._thumb.setStyleSheet(
            f"background:{CP['bg3']};border-radius:10px 10px 0 0;"
            f"color:{CP['text_dim']};font-size:36px;"
        )

        img_path = data.get("image_path", "")
        if img_path and os.path.isfile(img_path):
            QPixmapCache.remove(img_path)
            pix = QPixmap(img_path).scaled(
                self._W, self._H_IMG,
                Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                Qt.TransformationMode.SmoothTransformation,
            )
            pix = pix.copy(
                (pix.width()  - self._W)    // 2,
                (pix.height() - self._H_IMG) // 2,
                self._W, self._H_IMG,
            )
            self._thumb.setPixmap(pix)
        else:
            self._thumb.setText("👤")

        lay.addWidget(self._thumb)

        # ── Overlay hover (éditer / supprimer) ───────────────────────────────
        self._overlay = QWidget(self._thumb)
        self._overlay.setGeometry(0, 0, self._W, self._H_IMG)
        self._overlay.setStyleSheet("background:rgba(7,8,15,0.72);border-radius:10px 10px 0 0;")
        self._overlay.hide()

        ov_lay = QHBoxLayout(self._overlay)
        ov_lay.setContentsMargins(0, 0, 0, 0)
        ov_lay.setSpacing(10)
        ov_lay.setAlignment(Qt.AlignmentFlag.AlignCenter)

        def _ov_btn(text, color):
            b = QPushButton(text)
            b.setFixedHeight(32)
            b.setStyleSheet(
                f"QPushButton{{background:transparent;color:{color};"
                f"border:1.5px solid {color};border-radius:6px;"
                f"font-size:11px;font-weight:700;padding:0 12px;}}"
                f"QPushButton:hover{{background:{color};color:#07080f;}}"
            )
            return b

        btn_edit = _ov_btn("Éditer", CP["accent"])
        btn_del  = _ov_btn("Supprimer", CP["red"])
        btn_edit.clicked.connect(lambda: self.edit_requested.emit(self._data))
        btn_del.clicked.connect(lambda: self.delete_requested.emit(self._data["id"]))
        ov_lay.addWidget(btn_edit)
        ov_lay.addWidget(btn_del)

        # ── Info ──────────────────────────────────────────────────────────────
        info = QWidget()
        info.setFixedHeight(self._H_INFO)
        info.setStyleSheet(
            f"background:{CP['bg2']};border-radius:0 0 10px 10px;"
            f"border:1px solid {CP['border']};border-top:none;"
        )
        il = QVBoxLayout(info)
        il.setContentsMargins(10, 8, 10, 8)
        il.setSpacing(2)

        n_lbl = QLabel(data.get("name", "—"))
        n_lbl.setStyleSheet(
            f"color:{CP['text_primary']};font-size:12px;font-weight:700;"
            f"background:transparent;border:none;"
        )
        n_lbl.setWordWrap(False)

        r_lbl = QLabel(data.get("role", ""))
        r_lbl.setStyleSheet(
            f"color:{CP['text_secondary']};font-size:10px;"
            f"background:transparent;border:none;"
        )

        il.addWidget(n_lbl)
        il.addWidget(r_lbl)
        lay.addWidget(info)

    def enterEvent(self, e):
        self._overlay.show()

    def leaveEvent(self, e):
        self._overlay.hide()


# ── Page principale Castings ──────────────────────────────────────────────────

class PageCastings(QWidget):

    def __init__(self):
        super().__init__()
        self.setStyleSheet(f"background:{CP['bg0']};")
        self._all_chars: list[dict] = []

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        root.addWidget(self._build_topbar())

        sep = QFrame()
        sep.setFixedHeight(1)
        sep.setStyleSheet(f"background:{CP['border']};")
        root.addWidget(sep)

        root.addWidget(self._build_toolbar())

        _hw = QWidget()
        _hw.setStyleSheet("background:transparent;")
        _hl = QVBoxLayout(_hw)
        _hl.setContentsMargins(32, 8, 32, 4)
        _hl.setSpacing(0)
        _hl.addWidget(HelpBlock("Castings — Personnages du film", [
            "▸ Créez une fiche par personnage : nom, rôle, description physique et psychologique.",
            "▸ Générez un portrait IA via Nano Banana en un clic (clé API requise dans Paramètres).",
            "▸ Plusieurs portraits peuvent être générés pour un même personnage — choisissez le meilleur.",
            "▸ Les personnages sont réutilisés dans le storyboard et injectés comme références visuelles dans Seedance.",
            "▸ Filtrez et recherchez par nom ou rôle depuis la barre d'outils.",
        ], CP))
        root.addWidget(_hw)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet("QScrollArea{background:transparent;border:none;}")

        self._grid_container = QWidget()
        self._grid_container.setStyleSheet("background:transparent;")
        self._grid = QGridLayout(self._grid_container)
        self._grid.setSpacing(18)
        self._grid.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        self._grid.setContentsMargins(32, 24, 32, 32)

        scroll.setWidget(self._grid_container)
        root.addWidget(scroll, 1)

        self.refresh()

    # ── Barre du haut ─────────────────────────────────────────────────────────

    def _build_topbar(self) -> QWidget:
        bar = QWidget()
        bar.setFixedHeight(60)
        bar.setStyleSheet(f"background:{CP['bg1']};")
        lay = QHBoxLayout(bar)
        lay.setContentsMargins(32, 0, 32, 0)
        lay.setSpacing(10)

        _ico = QLabel()
        _ico.setFixedSize(28, 28)
        _ico.setAlignment(Qt.AlignmentFlag.AlignCenter)
        _ico.setStyleSheet("background:transparent;")
        _ico_pix = load_icon("castings.png", 28)
        if not _ico_pix.isNull():
            _ico.setPixmap(_ico_pix)
        lay.addWidget(_ico)

        title = QLabel("Castings")
        title.setStyleSheet(
            f"color:{CP['text_primary']};font-size:22px;font-weight:700;background:transparent;"
        )
        lay.addWidget(title)
        lay.addStretch()
        return bar

    # ── Barre d'outils ────────────────────────────────────────────────────────

    def _build_toolbar(self) -> QWidget:
        bar = QWidget()
        bar.setFixedHeight(60)
        bar.setStyleSheet(f"background:{CP['bg0']};")
        lay = QHBoxLayout(bar)
        lay.setContentsMargins(32, 0, 32, 0)
        lay.setSpacing(12)

        # Recherche
        self._search = QLineEdit()
        self._search.setPlaceholderText("🔍  Rechercher un personnage…")
        self._search.setFixedHeight(36)
        self._search.setStyleSheet(
            f"QLineEdit{{background:{CP['bg2']};border:1px solid {CP['border']};"
            f"border-radius:18px;color:{CP['text_primary']};font-size:12px;padding:0 16px;}}"
            f"QLineEdit:focus{{border-color:{CP['accent_dim']};}}"
        )
        self._search.textChanged.connect(self._filter)
        lay.addWidget(self._search, 1)

        lay.addStretch()

        # Import
        btn_import = QPushButton("↑  Import")
        btn_import.setFixedHeight(36)
        btn_import.setStyleSheet(
            f"QPushButton{{background:transparent;color:{CP['text_secondary']};"
            f"border:1px solid {CP['border']};border-radius:8px;"
            f"font-size:12px;font-weight:700;padding:0 16px;}}"
            f"QPushButton:hover{{background:{CP['bg2']};color:{CP['text_primary']};}}"
        )
        btn_import.clicked.connect(self._on_import)

        # Créer
        btn_new = QPushButton("✦  Créer un personnage")
        btn_new.setFixedHeight(36)
        btn_new.setStyleSheet(
            f"QPushButton{{background:{CP['accent']};color:#07080f;"
            f"border:none;border-radius:8px;font-size:12px;font-weight:700;padding:0 18px;}}"
            f"QPushButton:hover{{background:#6eded6;}}"
            f"QPushButton:pressed{{background:{CP['accent_dim']};color:#fff;}}"
        )
        btn_new.clicked.connect(self._on_new)

        lay.addWidget(btn_import)
        lay.addWidget(btn_new)
        return bar

    # ── Grille ────────────────────────────────────────────────────────────────

    def refresh(self):
        self._all_chars = casting_api.list_characters()
        self._render(self._all_chars)

    def _render(self, chars: list[dict]):
        while self._grid.count():
            item = self._grid.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        if not chars:
            empty = QLabel("Aucun personnage.\nClique sur ✦ Créer un personnage pour commencer.")
            empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
            empty.setStyleSheet(
                f"color:{CP['text_dim']};font-size:13px;background:transparent;border:none;"
            )
            self._grid.addWidget(empty, 0, 0, 1, 6)
            return

        cols = 6
        for i, char in enumerate(chars):
            card = CharacterCard(char)
            card.edit_requested.connect(self._on_edit)
            card.delete_requested.connect(self._on_delete)
            self._grid.addWidget(card, i // cols, i % cols)

    def _filter(self, text: str):
        q = text.lower()
        filtered = [
            c for c in self._all_chars
            if q in c.get("name", "").lower() or q in c.get("role", "").lower()
        ] if q else self._all_chars
        self._render(filtered)

    # ── Actions ───────────────────────────────────────────────────────────────

    def _on_new(self):
        dlg = CharacterDialog(self)
        if dlg.exec() == CharacterDialog.DialogCode.Accepted:
            self.refresh()

    def _on_edit(self, char: dict):
        dlg = CharacterDialog(self, character=char)
        dlg.exec()
        self.refresh()

    def _on_delete(self, char_id: str):
        char = casting_api.get_character(char_id)
        name = char.get("name", "ce personnage") if char else "ce personnage"
        reply = QMessageBox.question(
            self, "Supprimer",
            f"Supprimer {name} ?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            casting_api.delete_character(char_id)
            self.refresh()

    def _on_import(self):
        paths, _ = QFileDialog.getOpenFileNames(
            self, "Importer des portraits", "",
            "Images (*.png *.jpg *.jpeg *.webp)"
        )
        for path in paths:
            from core.casting import images_dir
            base = os.path.splitext(os.path.basename(path))[0]
            dest = os.path.join(images_dir(), f"{base}_{int(_time.time())}.png")
            shutil.copy(path, dest)
            char = {"name": base, "role": "", "image_path": dest}
            casting_api.save_character(char)
        if paths:
            self.refresh()
