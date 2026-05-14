import os
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QScrollArea, QGridLayout, QLineEdit, QFrame, QMessageBox, QComboBox,
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QPixmap
from ui.styles import CP
from ui.icons import load_icon
from ui.widgets import HelpBlock
import core.decors as decors_api
from core.decors import CATEGORIES
from ui.dialog_decor import DecorDialog


# ── Carte décor ───────────────────────────────────────────────────────────────

class DecorCard(QWidget):
    edit_requested   = pyqtSignal(dict)
    delete_requested = pyqtSignal(str)

    _W     = 162
    _H_IMG = 160
    _H_INFO = 72

    def __init__(self, data: dict):
        super().__init__()
        self._data = data
        self.setFixedSize(self._W, self._H_IMG + self._H_INFO)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)

        # Image
        self._thumb = QLabel()
        self._thumb.setFixedSize(self._W, self._H_IMG)
        self._thumb.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._thumb.setStyleSheet(
            f"background:{CP['bg3']};border-radius:10px 10px 0 0;"
            f"color:{CP['text_dim']};font-size:36px;"
        )
        img = data.get("image_path", "")
        if img and os.path.isfile(img):
            pix = QPixmap(img).scaled(
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
            self._thumb.setText("◻")
        lay.addWidget(self._thumb)

        # Category badge
        cat = data.get("category", "")
        if cat:
            badge = QLabel(cat, self._thumb)
            badge.setGeometry(8, 8, min(self._W - 16, len(cat) * 7 + 14), 20)
            badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
            badge.setStyleSheet(
                f"color:#07080f;background:{CP['green']};border-radius:4px;"
                f"font-size:9px;font-weight:700;letter-spacing:0.5px;"
            )

        # Overlay hover
        self._overlay = QWidget(self._thumb)
        self._overlay.setGeometry(0, 0, self._W, self._H_IMG)
        self._overlay.setStyleSheet("background:rgba(7,8,15,0.72);border-radius:10px 10px 0 0;")
        self._overlay.hide()

        ov = QHBoxLayout(self._overlay)
        ov.setAlignment(Qt.AlignmentFlag.AlignCenter)
        ov.setSpacing(10)

        def _ov_btn(text, color):
            b = QPushButton(text)
            b.setFixedHeight(32)
            b.setStyleSheet(
                f"QPushButton{{background:transparent;color:{color};"
                f"border:1.5px solid {color};border-radius:6px;"
                f"font-size:11px;font-weight:700;padding:0 10px;}}"
                f"QPushButton:hover{{background:{color};color:#07080f;}}"
            )
            return b

        btn_edit = _ov_btn("Éditer", CP["accent"])
        btn_del  = _ov_btn("Supprimer", CP["red"])
        btn_edit.clicked.connect(lambda: self.edit_requested.emit(self._data))
        btn_del.clicked.connect(lambda: self.delete_requested.emit(self._data["id"]))
        ov.addWidget(btn_edit)
        ov.addWidget(btn_del)

        # Info strip
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
        il.addWidget(n_lbl)

        cat_lbl = QLabel(cat)
        cat_lbl.setStyleSheet(
            f"color:{CP['green']};font-size:9px;font-weight:700;"
            f"background:transparent;border:none;"
        )
        il.addWidget(cat_lbl)

        n_shots = len(data.get("assigned_shots", []))
        c_lbl = QLabel(f"{n_shots} plan{'s' if n_shots != 1 else ''}" if n_shots else "Non assigné")
        c_lbl.setWordWrap(False)
        c_lbl.setStyleSheet(
            f"color:{CP['text_dim']};font-size:9px;background:transparent;border:none;"
        )
        il.addWidget(c_lbl)
        lay.addWidget(info)

    def enterEvent(self, e): self._overlay.show()
    def leaveEvent(self, e): self._overlay.hide()


# ── Page principale Décors ────────────────────────────────────────────────────

class PageDecors(QWidget):

    def __init__(self):
        super().__init__()
        self.setStyleSheet(f"background:{CP['bg0']};")
        self._all_items: list[dict] = []

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
        _hl.addWidget(HelpBlock("Décors — Lieux de tournage", [
            "▸ Répertoriez tous les lieux de tournage avec description, ambiance et contraintes techniques.",
            "▸ Ajoutez des images de référence (photo de repérage, moodboard) pour chaque décor.",
            "▸ Catégorisez par type (intérieur, extérieur, studio…) pour filtrer rapidement.",
            "▸ Les décors sont assignables aux plans du storyboard pour un suivi de production précis.",
            "▸ La liste des décors peut être générée automatiquement depuis le scénario (page Scénario → Claude IA).",
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

    def _build_topbar(self):
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
        _ico_pix = load_icon("decors.png", 28)
        if not _ico_pix.isNull():
            _ico.setPixmap(_ico_pix)
        lay.addWidget(_ico)

        title = QLabel("Décors")
        title.setStyleSheet(
            f"color:{CP['text_primary']};font-size:22px;font-weight:700;background:transparent;"
        )
        lay.addWidget(title)
        lay.addStretch()
        return bar

    def _build_toolbar(self):
        bar = QWidget()
        bar.setFixedHeight(60)
        bar.setStyleSheet(f"background:{CP['bg0']};")
        lay = QHBoxLayout(bar)
        lay.setContentsMargins(32, 0, 32, 0)
        lay.setSpacing(12)

        lbl_cat = QLabel("Catégorie :")
        lbl_cat.setStyleSheet(
            f"color:{CP['text_secondary']};font-size:11px;background:transparent;"
        )
        lay.addWidget(lbl_cat)

        self._cat_filter = QComboBox()
        self._cat_filter.addItems(["Toutes"] + CATEGORIES)
        self._cat_filter.setFixedHeight(36)
        self._cat_filter.setFixedWidth(160)
        self._cat_filter.setStyleSheet(
            f"QComboBox{{background:{CP['bg2']};border:1px solid {CP['border']};"
            f"border-radius:6px;color:{CP['text_primary']};font-size:12px;padding:0 10px;}}"
            f"QComboBox::drop-down{{border:none;width:20px;}}"
            f"QComboBox QAbstractItemView{{background:{CP['bg3']};border:1px solid {CP['border_bright']};"
            f"color:{CP['text_primary']};selection-background-color:{CP['accent_dim']};}}"
        )
        self._cat_filter.currentTextChanged.connect(lambda _: self._apply_filter())
        lay.addWidget(self._cat_filter)

        self._search = QLineEdit()
        self._search.setPlaceholderText("🔍  Rechercher un décor…")
        self._search.setFixedHeight(36)
        self._search.setStyleSheet(
            f"QLineEdit{{background:{CP['bg2']};border:1px solid {CP['border']};"
            f"border-radius:18px;color:{CP['text_primary']};font-size:12px;padding:0 16px;}}"
            f"QLineEdit:focus{{border-color:{CP['accent_dim']};}}"
        )
        self._search.textChanged.connect(self._apply_filter)
        lay.addWidget(self._search, 1)

        btn_new = QPushButton("✦  Créer un décor")
        btn_new.setFixedHeight(36)
        btn_new.setStyleSheet(
            f"QPushButton{{background:{CP['accent']};color:#07080f;"
            f"border:none;border-radius:8px;font-size:12px;font-weight:700;padding:0 18px;}}"
            f"QPushButton:hover{{background:#6eded6;}}"
            f"QPushButton:pressed{{background:{CP['accent_dim']};color:#fff;}}"
        )
        btn_new.clicked.connect(self._on_new)
        lay.addWidget(btn_new)
        return bar

    def refresh(self):
        self._all_items = decors_api.list_decors()
        self._apply_filter()

    def _apply_filter(self):
        cat = self._cat_filter.currentText()
        q   = self._search.text().lower()
        items = self._all_items
        if cat != "Toutes":
            items = [d for d in items if d.get("category") == cat]
        if q:
            items = [d for d in items if q in d.get("name", "").lower()]
        self._render(items)

    def _render(self, items: list[dict]):
        while self._grid.count():
            w = self._grid.takeAt(0)
            if w.widget():
                w.widget().deleteLater()

        if not items:
            empty = QLabel("Aucun décor.\nClique sur ✦ Créer un décor pour commencer.")
            empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
            empty.setStyleSheet(
                f"color:{CP['text_dim']};font-size:13px;background:transparent;border:none;"
            )
            self._grid.addWidget(empty, 0, 0, 1, 6)
            return

        cols = 6
        for i, item in enumerate(items):
            card = DecorCard(item)
            card.edit_requested.connect(self._on_edit)
            card.delete_requested.connect(self._on_delete)
            self._grid.addWidget(card, i // cols, i % cols)

    def _on_new(self):
        dlg = DecorDialog(self)
        if dlg.exec() == DecorDialog.DialogCode.Accepted:
            self.refresh()

    def _on_edit(self, item: dict):
        dlg = DecorDialog(self, item=item)
        if dlg.exec() == DecorDialog.DialogCode.Accepted:
            self.refresh()

    def _on_delete(self, decor_id: str):
        decor = decors_api.get_decor(decor_id)
        name = decor.get("name", "ce décor") if decor else "ce décor"
        reply = QMessageBox.question(
            self, "Supprimer",
            f"Supprimer {name} ?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            decors_api.delete_decor(decor_id)
            self.refresh()
