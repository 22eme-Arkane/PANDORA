import os
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QScrollArea, QGridLayout, QLineEdit, QFrame, QMessageBox,
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QPixmap
from ui.styles import CP
from ui.icons import load_icon
from ui.widgets import HelpBlock
import core.vehicles as veh_api
from core.vehicles import CATEGORIES
from ui.dialog_vehicle import VehicleDialog

_CAT_ICONS = {
    "Voiture": "🚗", "Moto": "🏍", "Camion": "🚛",
    "Bateau": "🚢", "Avion": "✈", "Train": "🚂",
    "Vélo": "🚲", "Autre": "🛻",
}
_CAT_COLOR = {
    "Voiture":  CP.get("accent",  "#4ecdc4"),
    "Moto":     CP.get("orange",  "#ff8c42"),
    "Camion":   CP.get("accent2", "#7c6bff"),
    "Bateau":   "#3b9ede",
    "Avion":    "#8bc34a",
    "Train":    "#e91e63",
    "Vélo":     "#ff9800",
    "Autre":    CP.get("text_secondary", "#8899aa"),
}


class VehicleCard(QWidget):
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

        self._thumb = QLabel()
        self._thumb.setFixedSize(self._W, self._H_IMG)
        self._thumb.setAlignment(Qt.AlignmentFlag.AlignCenter)
        cat = data.get("category", "Voiture")
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
            self._thumb.setText(_CAT_ICONS.get(cat, "🚗"))
        lay.addWidget(self._thumb)

        badge = QLabel(cat, self._thumb)
        badge.setGeometry(8, 8, 80, 22)
        badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        col = _CAT_COLOR.get(cat, CP["accent"])
        badge.setStyleSheet(
            f"color:#07080f;background:{col};border-radius:4px;"
            f"font-size:9px;font-weight:700;letter-spacing:0.5px;"
        )

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

        cat_col = _CAT_COLOR.get(cat, CP["text_secondary"])
        cat_lbl = QLabel(cat)
        cat_lbl.setStyleSheet(
            f"color:{cat_col};font-size:9px;font-weight:700;"
            f"background:transparent;border:none;"
        )
        il.addWidget(cat_lbl)

        desc = data.get("description", data.get("prompt", ""))
        if desc:
            d_lbl = QLabel(desc[:60] + "…" if len(desc) > 60 else desc)
            d_lbl.setWordWrap(False)
            d_lbl.setStyleSheet(
                f"color:{CP['text_dim']};font-size:9px;background:transparent;border:none;"
            )
            il.addWidget(d_lbl)
        lay.addWidget(info)

    def enterEvent(self, e): self._overlay.show()
    def leaveEvent(self, e): self._overlay.hide()


class PageVehicles(QWidget):

    def __init__(self):
        super().__init__()
        self.setStyleSheet(f"background:{CP['bg0']};")
        self._all_items: list[dict] = []
        self._active_filter = "Tous"

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
        _hl.addWidget(HelpBlock("Véhicules — Parc automobile & transport", [
            "▸ Répertoriez tous les véhicules nécessaires au tournage (voitures, motos, camions…).",
            "▸ Précisez la marque, le modèle, l'année, la couleur et les contraintes de disponibilité.",
            "▸ Ajoutez des images de référence pour faciliter la recherche et la location.",
            "▸ La liste peut être générée automatiquement depuis le scénario (page Scénario → Claude IA).",
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
        _ico_pix = load_icon("vehicule.png", 28)
        if not _ico_pix.isNull():
            _ico.setPixmap(_ico_pix)
        lay.addWidget(_ico)

        title = QLabel("Véhicules")
        title.setStyleSheet(
            f"color:{CP['text_primary']};font-size:20px;font-weight:700;background:transparent;"
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
        lay.setSpacing(10)

        self._filter_btns: dict[str, QPushButton] = {}
        for label in ["Tous"] + CATEGORIES:
            btn = QPushButton(label)
            btn.setFixedHeight(32)
            btn.setCheckable(True)
            btn.setChecked(label == "Tous")
            btn.setStyleSheet(self._filter_style(label == "Tous"))
            btn.clicked.connect(lambda checked, lbl=label: self._set_filter(lbl))
            self._filter_btns[label] = btn
            lay.addWidget(btn)

        lay.addStretch()

        self._search = QLineEdit()
        self._search.setPlaceholderText("🔍  Rechercher…")
        self._search.setFixedHeight(36)
        self._search.setFixedWidth(200)
        self._search.setStyleSheet(
            f"QLineEdit{{background:{CP['bg2']};border:1px solid {CP['border']};"
            f"border-radius:18px;color:{CP['text_primary']};font-size:12px;padding:0 16px;}}"
            f"QLineEdit:focus{{border-color:{CP['accent_dim']};}}"
        )
        self._search.textChanged.connect(self._apply_filter)
        lay.addWidget(self._search)

        btn_new = QPushButton("✦  Créer un véhicule")
        btn_new.setFixedHeight(36)
        btn_new.setStyleSheet(
            f"QPushButton{{background:{CP['accent']};color:#07080f;"
            f"border:none;border-radius:8px;font-size:12px;font-weight:700;padding:0 18px;}}"
            f"QPushButton:hover{{background:#6eded6;}}"
            f"QPushButton:pressed{{background:{CP['accent_dim']};color:#fff;}}"
        )
        btn_new.clicked.connect(self._on_new)

        _red = CP.get("red", "#ff4f6a")
        btn_del_all = QPushButton("✕  Tout supprimer")
        btn_del_all.setFixedHeight(36)
        btn_del_all.setStyleSheet(
            f"QPushButton{{background:transparent;color:{_red};"
            f"border:1.5px solid {_red};border-radius:8px;"
            f"font-size:11px;font-weight:700;padding:0 14px;}}"
            f"QPushButton:hover{{background:rgba(255,79,106,0.10);}}"
            f"QPushButton:pressed{{background:rgba(255,79,106,0.20);}}"
        )
        btn_del_all.clicked.connect(self._on_delete_all)

        lay.addWidget(btn_new)
        lay.addWidget(btn_del_all)
        return bar

    def _filter_style(self, active: bool) -> str:
        if active:
            return (
                f"QPushButton{{background:{CP['accent']};color:#07080f;"
                f"border:none;border-radius:6px;font-size:11px;font-weight:700;padding:0 14px;}}"
            )
        return (
            f"QPushButton{{background:transparent;color:{CP['text_secondary']};"
            f"border:1px solid {CP['border']};border-radius:6px;font-size:11px;font-weight:600;padding:0 14px;}}"
            f"QPushButton:hover{{background:{CP['bg2']};color:{CP['text_primary']};}}"
        )

    def _set_filter(self, label: str):
        self._active_filter = label
        for lbl, btn in self._filter_btns.items():
            btn.setStyleSheet(self._filter_style(lbl == label))
        self._apply_filter()

    def _apply_filter(self):
        q = self._search.text().lower()
        items = self._all_items
        if self._active_filter != "Tous":
            items = [v for v in items if v.get("category") == self._active_filter]
        if q:
            items = [v for v in items if q in v.get("name", "").lower()]
        self._render(items)

    def refresh(self):
        self._all_items = veh_api.list_vehicles()
        self._apply_filter()

    def _render(self, items: list[dict]):
        while self._grid.count():
            w = self._grid.takeAt(0)
            if w.widget():
                w.widget().deleteLater()

        if not items:
            empty = QLabel("Aucun véhicule.\nClique sur ✦ Créer un véhicule pour commencer.")
            empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
            empty.setStyleSheet(
                f"color:{CP['text_dim']};font-size:13px;background:transparent;border:none;"
            )
            self._grid.addWidget(empty, 0, 0, 1, 6)
            return

        cols = 6
        for i, item in enumerate(items):
            card = VehicleCard(item)
            card.edit_requested.connect(self._on_edit)
            card.delete_requested.connect(self._on_delete)
            self._grid.addWidget(card, i // cols, i % cols)

    def _on_delete_all(self):
        if not self._all_items:
            return
        from PyQt6.QtWidgets import QMessageBox
        r = QMessageBox.question(
            self, "Supprimer tous les véhicules",
            f"Supprimer les {len(self._all_items)} véhicule(s) ?\nCette action est irréversible.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if r != QMessageBox.StandardButton.Yes:
            return
        for item in list(self._all_items):
            veh_api.delete_vehicle(item["id"])
        self.refresh()

    def _on_new(self):
        dlg = VehicleDialog(self)
        if dlg.exec() == VehicleDialog.DialogCode.Accepted:
            self.refresh()

    def _on_edit(self, item: dict):
        dlg = VehicleDialog(self, item=item)
        if dlg.exec() == VehicleDialog.DialogCode.Accepted:
            self.refresh()

    def _on_delete(self, item_id: str):
        item = veh_api.get_vehicle(item_id)
        name = item.get("name", "ce véhicule") if item else "ce véhicule"
        reply = QMessageBox.question(
            self, "Supprimer",
            f"Supprimer {name} ?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            veh_api.delete_vehicle(item_id)
            self.refresh()
