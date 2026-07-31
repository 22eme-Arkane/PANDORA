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
import core.accessories as acc_api
from ui.element_io_buttons import make_save_open_buttons, toolbar_separator
from ui.dialog_accessory import AccessoryDialog


# ── Carte accessoire ──────────────────────────────────────────────────────────

class AccessoryCard(QWidget):
    edit_requested   = pyqtSignal(dict)
    delete_requested = pyqtSignal(str)
    selected         = pyqtSignal(dict)   # clic sur la carte → fiche latérale

    _W     = 162
    _H_IMG = 160
    _H_INFO = 52

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
            self._thumb.setText("🎭")
        lay.addWidget(self._thumb)

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

        cat_lbl = QLabel(data.get("category", ""))
        cat_lbl.setStyleSheet(
            f"color:{CP['accent']};font-size:9px;font-weight:700;"
            f"background:transparent;border:none;"
        )
        il.addWidget(cat_lbl)
        lay.addWidget(info)

    def enterEvent(self, e): self._overlay.show()
    def leaveEvent(self, e): self._overlay.hide()

    def mousePressEvent(self, e):
        # Clic sur la carte (hors boutons de l'overlay) → sélection dans la fiche.
        if e.button() == Qt.MouseButton.LeftButton:
            self.selected.emit(self._data)
            e.accept()
            return
        super().mousePressEvent(e)


# ── Page principale Accessoires ───────────────────────────────────────────────

class PageAccessories(QWidget):

    def __init__(self):
        super().__init__()
        self.setStyleSheet(f"background:{CP['bg0']};")
        self._all_items: list[dict] = []
        self._selected_id: str = ""

        # Fiche latérale droite repliable (poignée FICHE) — demande 2026-07-23.
        from ui.element_side_panel import attach_side_panel
        _content = QWidget()
        _content.setStyleSheet("background:transparent;")
        root = QVBoxLayout(_content)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        self._side_panel = attach_side_panel(
            self, _content, "Sélectionnez un accessoire", "▣")

        # Bandeau titre retiré (demande Matthieu 2026-07-22).

        # Separateur haut retire (2026-07-23) : la barre d'outils est la 1re rangee,
        # sa ligne basse tombe pile sur celles des en-tetes GUIDE / IA (40 px).

        root.addWidget(self._build_toolbar())

        _hw = QWidget()
        _hw.setStyleSheet("background:transparent;")
        _hl = QVBoxLayout(_hw)
        _hl.setContentsMargins(32, 8, 32, 4)
        _hl.setSpacing(0)
        _hl.addWidget(HelpBlock("Accessoires — Props & matériel", [
            "▸ Listez tous les accessoires nécessaires au tournage avec description et quantité.",
            "▸ Ajoutez des images de référence pour chaque prop afin de faciliter les achats et la régie.",
            "▸ Assignez les accessoires aux personnages et aux plans du storyboard.",
            "▸ La liste peut être générée automatiquement depuis le scénario (page Scénario → Claude IA).",
        ], CP))
        root.addWidget(_hw)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet("QScrollArea{background:transparent;border:none;}")

        self._grid_container = QWidget()
        self._grid_container.setStyleSheet("background:transparent;")
        # Une section dépliable PAR CATÉGORIE (demande Matthieu 2026-07-31) :
        # « Armes », « Mobilier », « Bagage »… étaient mélangés dans une seule
        # grille, alors que la catégorie est écrite sous chaque vignette.
        self._sections_lay = QVBoxLayout(self._grid_container)
        self._sections_lay.setSpacing(14)
        self._sections_lay.setAlignment(Qt.AlignmentFlag.AlignTop)
        self._sections_lay.setContentsMargins(32, 24, 32, 32)
        self._collapsed: dict[str, bool] = {}
        from ui.grid_flow import ColumnsWatcher
        self._cols_watch = ColumnsWatcher()

        scroll.setWidget(self._grid_container)
        self._scroll = scroll
        root.addWidget(scroll, 1)

        # État vide CENTRÉ + « Générer depuis le scénario » (demande 2026-07-23).
        from ui.element_side_panel import make_empty_state, open_generate_from_scenario
        self._empty_state = make_empty_state(
            "Aucun accessoire pour ce projet.",
            on_generate=lambda: open_generate_from_scenario(self, "accessory"))
        self._empty_state.setVisible(False)
        root.addWidget(self._empty_state, 1)

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
        _ico_pix = load_icon("accesoires.png", 28)
        if not _ico_pix.isNull():
            _ico.setPixmap(_ico_pix)
        lay.addWidget(_ico)

        title = QLabel("Accessoires")
        title.setStyleSheet(
            f"color:{CP['text_primary']};font-size:22px;font-weight:700;background:transparent;"
        )
        lay.addWidget(title)
        lay.addStretch()
        return bar

    def _build_toolbar(self):
        bar = QWidget()
        # 40 px + ligne basse : premiere rangee alignee sur les en-tetes GUIDE/IA (2026-07-23).
        bar.setFixedHeight(40)
        bar.setStyleSheet(f"background:{CP['bg0']};border-bottom:1px solid {CP['border']};")
        lay = QHBoxLayout(bar)
        lay.setContentsMargins(32, 0, 32, 0)
        lay.setSpacing(12)

        self._search = QLineEdit()
        self._search.setPlaceholderText("🔍  Rechercher un accessoire…")
        self._search.setFixedHeight(36)
        self._search.setStyleSheet(
            f"QLineEdit{{background:{CP['bg2']};border:1px solid {CP['border']};"
            f"border-radius:18px;color:{CP['text_primary']};font-size:12px;padding:0 16px;}}"
            f"QLineEdit:focus{{border-color:{CP['accent_dim']};}}"
        )
        self._search.textChanged.connect(self._filter)
        # Barre de recherche RETIRÉE de l'affichage (2026-07-22) ; widget vivant.
        self._search.setParent(bar)
        self._search.hide()

        self._btn_save_file, self._btn_open_file = make_save_open_buttons(
            self, kind="accessories",
            list_fn=acc_api.list_accessories,
            save_fn=acc_api.save_accessory,
            delete_fn=acc_api.delete_accessory,
            refresh_fn=self.refresh)

        btn_new = QPushButton("✦  Créer un accessoire")
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

        # ── Bouton « Action » (2026-07-22, même principe que le Storyboard) :
        # Sauvegarder, Ouvrir, Créer un accessoire, Tout supprimer (rouge).
        from ui.widgets import make_actions_menu_button
        self._btn_actions = make_actions_menu_button(
            bar, [self._btn_save_file, self._btn_open_file, btn_new],
            red_entry=btn_del_all)
        lay.addWidget(self._btn_actions)
        lay.addStretch(1)
        return bar

    def refresh(self):
        self._all_items = acc_api.list_accessories()
        self._render(self._all_items)

    def _grid_columns(self) -> int:
        """Colonnes qui tiennent vraiment dans la zone d'affichage."""
        from ui.grid_flow import columns_for
        _vp = self._scroll.viewport().width() if hasattr(self, "_scroll") else 0
        return columns_for(max(0, _vp - 64))

    def _cards_grid(self, items: list[dict], cols: int | None = None) -> QWidget:
        if cols is None:
            cols = self._grid_columns()
        wrap = QWidget()
        wrap.setStyleSheet("background:transparent;")
        g = QGridLayout(wrap)
        g.setSpacing(18)
        g.setContentsMargins(0, 0, 0, 0)
        g.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        for i, item in enumerate(items):
            card = AccessoryCard(item)
            card.edit_requested.connect(self._on_edit)
            card.delete_requested.connect(self._on_delete)
            card.selected.connect(self._on_card_selected)
            g.addWidget(card, i // cols, i % cols)
        return wrap

    def resizeEvent(self, e):
        super().resizeEvent(e)
        try:
            if self._cols_watch.changed(self._grid_columns()) and self._all_items:
                self._render(self._all_items)
        except Exception:
            pass

    def _render(self, items: list[dict]):
        from core.i18n import translate
        while self._sections_lay.count():
            _it = self._sections_lay.takeAt(0)
            if _it.widget():
                _it.widget().deleteLater()

        if not items:
            if not self._all_items:
                # Aucun accessoire du tout → bloc centré + bouton de génération.
                self._scroll.setVisible(False)
                self._empty_state.setVisible(True)
                return
            empty = QLabel(translate("Aucun accessoire ne correspond au filtre."))
            empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
            empty.setStyleSheet(
                f"color:{CP['text_dim']};font-size:13px;background:transparent;border:none;"
            )
            self._sections_lay.addWidget(empty)
            return
        self._empty_state.setVisible(False)
        self._scroll.setVisible(True)

        from ui.grid_flow import group_by_category
        from ui.collapsible import CollapsibleSection
        for _cat, _items in group_by_category(items):
            _exp = self._collapsed.get(_cat, True)
            sec = CollapsibleSection(
                f"{translate(_cat)}   ·   {len(_items)}", expanded=bool(_exp))
            sec.add_widget(self._cards_grid(_items))
            sec.header_button().toggled.connect(
                lambda ok, k=_cat: self._collapsed.__setitem__(k, bool(ok)))
            self._sections_lay.addWidget(sec)

    def _on_card_selected(self, item: dict):
        from ui.element_side_panel import storyboard_stats
        self._selected_id = item.get("id", "")
        self._side_panel.show_item(
            name=item.get("name", ""),
            subtitle=item.get("category", ""),
            description=item.get("description") or item.get("prompt", ""),
            stats=storyboard_stats("accessory", item),
            image_path=item.get("image_path", ""),
        )

    def _filter(self, text: str):
        q = text.lower()
        filtered = [
            a for a in self._all_items
            if q in a.get("name", "").lower() or q in a.get("category", "").lower()
        ] if q else self._all_items
        self._render(filtered)

    def _on_delete_all(self):
        if not self._all_items:
            return
        from PyQt6.QtWidgets import QMessageBox
        r = QMessageBox.question(
            self, "Supprimer tous les accessoires",
            f"Supprimer les {len(self._all_items)} accessoire(s) ?\nCette action est irréversible.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if r != QMessageBox.StandardButton.Yes:
            return
        for item in list(self._all_items):
            acc_api.delete_accessory(item["id"])
        self.refresh()

    def _on_new(self):
        dlg = AccessoryDialog(self)
        if dlg.exec() == AccessoryDialog.DialogCode.Accepted:
            self.refresh()

    def _on_edit(self, item: dict):
        dlg = AccessoryDialog(self, item=item)
        if dlg.exec() == AccessoryDialog.DialogCode.Accepted:
            self.refresh()

    def _on_delete(self, acc_id: str):
        acc = acc_api.get_accessory(acc_id)
        name = acc.get("name", "cet accessoire") if acc else "cet accessoire"
        reply = QMessageBox.question(
            self, "Supprimer",
            f"Supprimer {name} ?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            acc_api.delete_accessory(acc_id)
            self.refresh()
