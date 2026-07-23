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
from ui.element_io_buttons import make_save_open_buttons, toolbar_separator
from ui.dialog_character import CharacterDialog
import shutil, time as _time


# ── Carte personnage ──────────────────────────────────────────────────────────

class CharacterCard(QWidget):
    edit_requested   = pyqtSignal(dict)
    delete_requested = pyqtSignal(str)
    selected         = pyqtSignal(dict)   # clic sur la carte → fiche latérale

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

    def mousePressEvent(self, e):
        # Clic sur la carte (hors boutons de l'overlay, qui consomment le leur)
        # → sélection : la fiche latérale droite affiche ce personnage.
        if e.button() == Qt.MouseButton.LeftButton:
            self.selected.emit(self._data)
            e.accept()
            return
        super().mousePressEvent(e)


# ── Page principale Castings ──────────────────────────────────────────────────

class PageCastings(QWidget):

    def __init__(self):
        super().__init__()
        self.setStyleSheet(f"background:{CP['bg0']};")
        self._all_chars: list[dict] = []
        self._selected_id: str = ""

        # ── Fiche latérale droite repliable (demande Matthieu 2026-07-23) :
        # même principe que la poignée GUIDE / ASSISTANT — photo en grand,
        # description et nombre de plans du personnage sélectionné. ──
        outer = QHBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        _content = QWidget()
        _content.setStyleSheet("background:transparent;")
        root = QVBoxLayout(_content)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # Bandeau titre « Castings » retiré (demande Matthieu 2026-07-22).

        # Separateur haut retire (2026-07-23) : la barre d'outils est la 1re rangee,
        # sa ligne basse tombe pile sur celles des en-tetes GUIDE / IA (40 px).

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
        self._scroll = scroll
        root.addWidget(scroll, 1)

        # État vide CENTRÉ dans la fenêtre (demande Matthieu 2026-07-23).
        from ui.element_side_panel import make_empty_state
        self._empty_state = make_empty_state(
            "Aucun personnage.\nClique sur ✦ Créer un personnage pour commencer.")
        self._empty_state.setVisible(False)
        root.addWidget(self._empty_state, 1)

        outer.addWidget(_content, 1)
        outer.addWidget(self._build_char_panel())
        from ui.page_scenario import _PanelToggle
        self._char_toggle = _PanelToggle("FICHE", opened=False)
        self._char_toggle.toggled.connect(self._on_char_panel_toggled)
        outer.addWidget(self._char_toggle)

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
        # 40 px + ligne basse : premiere rangee alignee sur les en-tetes GUIDE/IA (2026-07-23).
        bar.setFixedHeight(40)
        bar.setStyleSheet(f"background:{CP['bg0']};border-bottom:1px solid {CP['border']};")
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
        # Barre de recherche RETIRÉE de l'affichage (demande Matthieu 2026-07-22) ;
        # le widget reste vivant car _filter lit son texte.
        self._search.setParent(bar)
        self._search.hide()

        self._btn_save_file, self._btn_open_file = make_save_open_buttons(
            self, kind="casting",
            list_fn=casting_api.list_characters,
            save_fn=casting_api.save_character,
            delete_fn=casting_api.delete_character,
            refresh_fn=self.refresh)

        # Importer des photos = créer un personnage par image (≠ « Ouvrir » qui
        # recharge un casting sauvegardé). Regroupé avec les actions de création.
        btn_import = QPushButton("↑  Importer des photos")
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

        _red = CP.get("red", "#ff4f6a")
        btn_del_all = QPushButton("✕  Supprimer tout le casting")
        btn_del_all.setFixedHeight(36)
        btn_del_all.setStyleSheet(
            f"QPushButton{{background:transparent;color:{_red};"
            f"border:1.5px solid {_red};border-radius:8px;"
            f"font-size:11px;font-weight:700;padding:0 14px;}}"
            f"QPushButton:hover{{background:rgba(255,79,106,0.10);}}"
            f"QPushButton:pressed{{background:rgba(255,79,106,0.20);}}"
        )
        btn_del_all.clicked.connect(self._on_delete_all)

        # ── Bouton « Action » (demande Matthieu 2026-07-22, même principe que le
        # Storyboard) : Sauvegarder, Ouvrir, Créer un personnage, Supprimer tout le
        # casting (rouge). « Importer des photos » est retiré de l'affichage.
        btn_import.setParent(bar)
        btn_import.hide()
        from ui.widgets import make_actions_menu_button
        self._btn_actions = make_actions_menu_button(
            bar, [self._btn_save_file, self._btn_open_file, btn_new],
            red_entry=btn_del_all)
        lay.addWidget(self._btn_actions)
        lay.addStretch(1)
        return bar

    # ── Fiche latérale droite (personnage sélectionné) ────────────────────────

    _PANEL_W = 320

    def _build_char_panel(self) -> QWidget:
        from core.i18n import translate
        panel = QWidget()
        panel.setFixedWidth(self._PANEL_W)
        panel.setStyleSheet(f"background:{CP['bg1']};")
        lay = QVBoxLayout(panel)
        lay.setContentsMargins(14, 14, 14, 14)
        lay.setSpacing(10)

        self._cp_photo = QLabel("👤")
        self._cp_photo.setFixedSize(self._PANEL_W - 28, 330)
        self._cp_photo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._cp_photo.setStyleSheet(
            f"background:{CP['bg3']};border-radius:10px;color:{CP['text_dim']};font-size:44px;"
        )
        lay.addWidget(self._cp_photo)

        self._cp_name = QLabel(translate("Sélectionnez un personnage"))
        self._cp_name.setWordWrap(True)
        self._cp_name.setStyleSheet(
            f"color:{CP['text_primary']};font-size:16px;font-weight:700;background:transparent;"
        )
        lay.addWidget(self._cp_name)

        self._cp_role = QLabel("")
        self._cp_role.setStyleSheet(
            f"color:{CP['accent']};font-size:10px;font-weight:700;background:transparent;"
        )
        lay.addWidget(self._cp_role)

        self._cp_stats = QLabel("")
        self._cp_stats.setWordWrap(True)
        self._cp_stats.setStyleSheet(
            f"color:{CP['text_secondary']};font-size:11px;background:transparent;"
        )
        lay.addWidget(self._cp_stats)

        _desc_scroll = QScrollArea()
        _desc_scroll.setWidgetResizable(True)
        _desc_scroll.setFrameStyle(0)
        _desc_scroll.setStyleSheet("QScrollArea{background:transparent;border:none;}")
        self._cp_desc = QLabel("")
        self._cp_desc.setWordWrap(True)
        self._cp_desc.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        self._cp_desc.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self._cp_desc.setStyleSheet(
            f"color:{CP['text_secondary']};font-size:11px;background:transparent;"
        )
        _desc_scroll.setWidget(self._cp_desc)
        lay.addWidget(_desc_scroll, 1)

        panel.setVisible(False)   # fermé par défaut (rien de sélectionné)
        self._char_panel = panel
        return panel

    def _on_char_panel_toggled(self, opened: bool):
        self._char_panel.setVisible(opened)

    def _on_card_selected(self, data: dict):
        from core.i18n import translate
        self._selected_id = data.get("id", "")
        img = data.get("image_path", "")
        w, h = self._PANEL_W - 28, 330
        if img and os.path.isfile(img):
            pix = QPixmap(img).scaled(
                w, h, Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                Qt.TransformationMode.SmoothTransformation)
            pix = pix.copy((pix.width() - w) // 2, (pix.height() - h) // 2, w, h)
            self._cp_photo.setPixmap(pix)
        else:
            self._cp_photo.setPixmap(QPixmap())
            self._cp_photo.setText("👤")
        self._cp_name.setText(data.get("name") or "—")
        self._cp_role.setText((data.get("role") or "").upper())
        plans, seqs = self._char_plan_stats(data)
        if plans:
            _s = f"🎬  {plans} {translate('plan(s) au storyboard')}"
            if seqs:
                _s += f"  ·  {seqs} {translate('séquence(s)')}"
        else:
            _s = translate("Aucun plan au storyboard pour l'instant")
        self._cp_stats.setText(_s)
        self._cp_desc.setText((data.get("prompt") or "").strip()
                              or translate("Aucune description."))
        # La sélection OUVRE la fiche si elle est fermée (fermable via la poignée).
        if not self._char_panel.isVisible():
            self._char_toggle._open = True
            self._char_toggle._update_arrow()
            self._char_panel.setVisible(True)

    def _char_plan_stats(self, data: dict) -> tuple[int, int]:
        """(nb de plans, nb de séquences) du storyboard où ce personnage apparaît."""
        try:
            import core.storyboard as sb
            shots = sb.list_shots()
        except Exception:
            return 0, 0
        cid = data.get("id", "")
        name = (data.get("name") or "").strip().lower()
        n, seqs = 0, set()
        for s in shots:
            ids = s.get("character_ids") or []
            names = [str(x).strip().lower() for x in (s.get("character_names") or [])]
            if (cid and cid in ids) or (name and name in names):
                n += 1
                sq = s.get("seq_num")
                if sq not in (None, ""):
                    seqs.add(sq)
        return n, len(seqs)

    # ── Grille ────────────────────────────────────────────────────────────────

    def refresh(self):
        self._all_chars = casting_api.list_characters()
        self._render(self._all_chars)
        # La fiche latérale suit les données : re-remplie si le personnage existe
        # toujours, remise à zéro sinon.
        if self._selected_id:
            cur = next((c for c in self._all_chars
                        if c.get("id") == self._selected_id), None)
            if cur is not None:
                self._on_card_selected(cur)
            else:
                self._selected_id = ""
                from core.i18n import translate
                self._cp_photo.setPixmap(QPixmap())
                self._cp_photo.setText("👤")
                self._cp_name.setText(translate("Sélectionnez un personnage"))
                self._cp_role.setText("")
                self._cp_stats.setText("")
                self._cp_desc.setText("")

    def _render(self, chars: list[dict]):
        while self._grid.count():
            item = self._grid.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        if not chars:
            if not self._all_chars:
                # Aucun personnage du tout → bloc centré dans la fenêtre.
                self._scroll.setVisible(False)
                self._empty_state.setVisible(True)
                return
            from core.i18n import translate
            empty = QLabel(translate("Aucun personnage ne correspond au filtre."))
            empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
            empty.setStyleSheet(
                f"color:{CP['text_dim']};font-size:13px;background:transparent;border:none;"
            )
            self._grid.addWidget(empty, 0, 0, 1, 9)
            return
        self._empty_state.setVisible(False)
        self._scroll.setVisible(True)

        # 9 colonnes (2026-07-23) : utiliser toute la largeur de la fenêtre.
        cols = 9
        for i, char in enumerate(chars):
            card = CharacterCard(char)
            card.edit_requested.connect(self._on_edit)
            card.delete_requested.connect(self._on_delete)
            card.selected.connect(self._on_card_selected)
            self._grid.addWidget(card, i // cols, i % cols)

    def _filter(self, text: str):
        q = text.lower()
        filtered = [
            c for c in self._all_chars
            if q in c.get("name", "").lower() or q in c.get("role", "").lower()
        ] if q else self._all_chars
        self._render(filtered)

    # ── Actions ───────────────────────────────────────────────────────────────

    def _on_delete_all(self):
        if not self._all_chars:
            return
        from PyQt6.QtWidgets import QMessageBox
        r = QMessageBox.question(
            self, "Supprimer tout le casting",
            f"Supprimer les {len(self._all_chars)} personnage(s) ?\nCette action est irréversible.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if r != QMessageBox.StandardButton.Yes:
            return
        for char in list(self._all_chars):
            casting_api.delete_character(char["id"])
        self.refresh()

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
