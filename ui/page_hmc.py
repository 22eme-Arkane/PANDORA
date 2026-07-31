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
import core.hmc as hmc_api
import core.casting as casting_api
from ui.element_io_buttons import make_save_open_buttons, toolbar_separator
from core.hmc import TYPES
from ui.dialog_hmc import HMCDialog

_TYPE_ICONS = {"Habit": "👗", "Maquillage": "💄", "Coiffure": "✂"}
_TYPE_COLOR = {
    "Habit":     CP.get("accent",     "#4ecdc4"),
    "Maquillage": CP.get("accent2",   "#7c6bff"),
    "Coiffure":  CP.get("orange",     "#ff8c42"),
}


# ── Carte HMC ─────────────────────────────────────────────────────────────────

class HMCCard(QWidget):
    edit_requested   = pyqtSignal(dict)
    delete_requested = pyqtSignal(str)
    selected         = pyqtSignal(dict)   # clic sur la carte → fiche latérale

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
        hmc_type = data.get("hmc_type", "Habit")
        self._thumb.setStyleSheet(
            f"background:{CP['bg3']};border-radius:10px 10px 0 0;"
            f"color:{CP['text_dim']};font-size:36px;"
        )
        # Vignette en cache, décodée à la taille d'affichage (audit 2026-07-31).
        from ui.thumb_cache import card_pixmap, ensure_cache_size
        ensure_cache_size()
        pix = card_pixmap(data.get("image_path", ""), self._W, self._H_IMG)
        if pix is not None:
            self._thumb.setPixmap(pix)
        else:
            self._thumb.setText(_TYPE_ICONS.get(hmc_type, "✂"))
        lay.addWidget(self._thumb)

        # Badge type
        badge = QLabel(hmc_type, self._thumb)
        badge.setGeometry(8, 8, 80, 22)
        badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        col = _TYPE_COLOR.get(hmc_type, CP["accent"])
        badge.setStyleSheet(
            f"color:#07080f;background:{col};border-radius:4px;"
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

        # Type badge line
        hmc_type = data.get("hmc_type", "")
        type_col = _TYPE_COLOR.get(hmc_type, CP["text_secondary"])
        type_lbl = QLabel(hmc_type)
        type_lbl.setStyleSheet(
            f"color:{type_col};font-size:9px;font-weight:700;"
            f"background:transparent;border:none;"
        )
        il.addWidget(type_lbl)

        # Assigned character names
        assigned_ids = data.get("assigned_to", [])
        if assigned_ids:
            names = []
            for cid in assigned_ids:
                char = casting_api.get_character(cid)
                if char:
                    names.append(char.get("name", "?"))
            chars_txt = ", ".join(names) if names else ""
        else:
            chars_txt = ""
        c_lbl = QLabel(chars_txt or "Non assigné")
        c_lbl.setWordWrap(False)
        c_lbl.setStyleSheet(
            f"color:{CP['text_dim']};font-size:9px;background:transparent;border:none;"
        )
        il.addWidget(c_lbl)
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


# ── Page principale HMC ───────────────────────────────────────────────────────

class PageHMC(QWidget):

    def __init__(self):
        super().__init__()
        self.setStyleSheet(f"background:{CP['bg0']};")
        self._all_items: list[dict] = []
        self._active_filter = "Tous"
        self._selected_id: str = ""

        # Fiche latérale droite repliable (poignée FICHE) — demande 2026-07-23.
        from ui.element_side_panel import attach_side_panel
        _content = QWidget()
        _content.setStyleSheet("background:transparent;")
        root = QVBoxLayout(_content)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        self._side_panel = attach_side_panel(
            self, _content, "Sélectionnez un élément HMC", "🧥")

        # Bandeau titre retiré (demande Matthieu 2026-07-22).

        # Separateur haut retire (2026-07-23) : la barre d'outils est la 1re rangee,
        # sa ligne basse tombe pile sur celles des en-tetes GUIDE / IA (40 px).

        root.addWidget(self._build_toolbar())

        _hw = QWidget()
        _hw.setStyleSheet("background:transparent;")
        _hl = QVBoxLayout(_hw)
        _hl.setContentsMargins(32, 8, 32, 4)
        _hl.setSpacing(0)
        _hl.addWidget(HelpBlock("HMC — Habillage, Maquillage, Coiffure", [
            "▸ Créez une fiche HMC par personnage ou par scène avec description et références visuelles.",
            "▸ Catégories : Habillage (costumes, tenues), Maquillage, Coiffure, Effets spéciaux.",
            "▸ Ajoutez des images de référence pour chaque élément afin de guider les équipes artistiques.",
            "▸ Les fiches HMC peuvent être générées automatiquement depuis le scénario (page Scénario → Claude IA).",
        ], CP))
        root.addWidget(_hw)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet("QScrollArea{background:transparent;border:none;}")

        self._grid_container = QWidget()
        self._grid_container.setStyleSheet("background:transparent;")
        # Une section dépliable PAR CATÉGORIE (demande Matthieu 2026-07-31).
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
            "Aucun élément HMC pour ce projet.",
            on_generate=lambda: open_generate_from_scenario(self, "hmc"))
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
        _ico_pix = load_icon("HMC.png", 28)
        if not _ico_pix.isNull():
            _ico.setPixmap(_ico_pix)
        lay.addWidget(_ico)

        title = QLabel("HMC — Habillage · Maquillage · Coiffure")
        title.setStyleSheet(
            f"color:{CP['text_primary']};font-size:20px;font-weight:700;background:transparent;"
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
        lay.setSpacing(10)

        # Filtres type — conservés (Tous / Habillage / Maquillage / Coiffure) mais
        # ajoutés À DROITE du bouton « Action », plus bas (demande 2026-07-22).
        self._filter_btns: dict[str, QPushButton] = {}
        for label in ["Tous"] + TYPES:
            btn = QPushButton(label)
            btn.setFixedHeight(32)
            btn.setCheckable(True)
            btn.setChecked(label == "Tous")
            btn.setStyleSheet(self._filter_style(label == "Tous"))
            btn.clicked.connect(lambda checked, lbl=label: self._set_filter(lbl))
            self._filter_btns[label] = btn

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
        # Barre de recherche RETIRÉE de l'affichage (2026-07-22) ; widget vivant.
        self._search.setParent(bar)
        self._search.hide()

        self._btn_save_file, self._btn_open_file = make_save_open_buttons(
            self, kind="hmc",
            list_fn=hmc_api.list_hmc_items,
            save_fn=hmc_api.save_hmc_item,
            delete_fn=hmc_api.delete_hmc_item,
            refresh_fn=self.refresh)

        btn_new = QPushButton("✦  Créer un élément HMC")
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
        # Sauvegarder, Ouvrir, Créer un élément HMC, Tout supprimer (rouge) —
        # puis les filtres type à sa droite.
        from ui.widgets import make_actions_menu_button
        self._btn_actions = make_actions_menu_button(
            bar, [self._btn_save_file, self._btn_open_file, btn_new],
            red_entry=btn_del_all)
        lay.addWidget(self._btn_actions)
        for _label in ["Tous"] + TYPES:
            lay.addWidget(self._filter_btns[_label])
        lay.addStretch(1)
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
            items = [h for h in items if h.get("hmc_type") == self._active_filter]
        if q:
            items = [h for h in items if q in h.get("name", "").lower()]
        self._render(items)

    def refresh(self):
        self._all_items = hmc_api.list_hmc_items()
        self._apply_filter()

    def _render(self, items: list[dict]):
        from core.i18n import translate
        while self._sections_lay.count():
            w = self._sections_lay.takeAt(0)
            if w.widget():
                w.widget().deleteLater()

        if not items:
            if not self._all_items:
                # Aucun élément du tout → bloc centré + bouton de génération.
                self._scroll.setVisible(False)
                self._empty_state.setVisible(True)
                return
            empty = QLabel(translate("Aucun élément HMC ne correspond au filtre."))
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
            card = HMCCard(item)
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

    def _on_card_selected(self, item: dict):
        from ui.element_side_panel import storyboard_stats
        self._selected_id = item.get("id", "")
        _sub = item.get("hmc_type", "")
        if item.get("character_name"):
            _sub = (_sub + "  ·  " if _sub else "") + item["character_name"]
        self._side_panel.show_item(
            name=item.get("name", ""),
            subtitle=_sub,
            description=item.get("description") or item.get("prompt", ""),
            stats=storyboard_stats("hmc", item),
            image_path=item.get("image_path", ""),
        )

    def _on_delete_all(self):
        if not self._all_items:
            return
        from PyQt6.QtWidgets import QMessageBox
        r = QMessageBox.question(
            self, "Supprimer tout le HMC",
            f"Supprimer les {len(self._all_items)} élément(s) HMC ?\nCette action est irréversible.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if r != QMessageBox.StandardButton.Yes:
            return
        for item in list(self._all_items):
            hmc_api.delete_hmc_item(item["id"])
        self.refresh()

    def _on_new(self):
        dlg = HMCDialog(self)
        if dlg.exec() == HMCDialog.DialogCode.Accepted:
            self.refresh()

    def _on_edit(self, item: dict):
        dlg = HMCDialog(self, item=item)
        if dlg.exec() == HMCDialog.DialogCode.Accepted:
            self.refresh()

    def _on_delete(self, item_id: str):
        item = hmc_api.get_hmc_item(item_id)
        name = item.get("name", "cet élément") if item else "cet élément"
        reply = QMessageBox.question(
            self, "Supprimer",
            f"Supprimer {name} ?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            hmc_api.delete_hmc_item(item_id)
            self.refresh()
