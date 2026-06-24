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
from ui.element_io_buttons import make_save_open_buttons, toolbar_separator
from core.decors import CATEGORIES
from core.i18n import translate, to_source
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
        cat_w = 0
        if cat:
            cat_w = min(self._W - 16, len(cat) * 7 + 14)
            badge = QLabel(cat, self._thumb)
            badge.setGeometry(8, 8, cat_w, 20)
            badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
            badge.setStyleSheet(
                f"color:#07080f;background:{CP['green']};border-radius:4px;"
                f"font-size:9px;font-weight:700;letter-spacing:0.5px;"
            )

        # Badge de FACE (rouge) — pour les vues d'une pièce (7 vues) : indique
        # clairement de quelle face il s'agit (Avant/Arrière/Gauche/Droite/Sol/
        # Plafond/Ensemble), à côté de la catégorie.
        rv = data.get("room_view", "")
        if rv:
            _red = CP.get("red", "#ff4f6a")
            fx = 8 + (cat_w + 5 if cat_w else 0)
            fb = QLabel(rv.upper(), self._thumb)
            fb.setGeometry(fx, 8, min(self._W - fx - 8, len(rv) * 7 + 14), 20)
            fb.setAlignment(Qt.AlignmentFlag.AlignCenter)
            fb.setStyleSheet(
                f"color:#ffffff;background:{_red};border-radius:4px;"
                f"font-size:9px;font-weight:800;letter-spacing:0.5px;"
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
        self._collapsed: dict[str, bool] = {}   # état replié des bandeaux par pièce

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
        # Pile verticale de sections : décors libres (grille simple) + un bandeau
        # dépliable par pièce (room_group) regroupant ses 7 vues.
        self._sections_lay = QVBoxLayout(self._grid_container)
        self._sections_lay.setSpacing(14)
        self._sections_lay.setAlignment(Qt.AlignmentFlag.AlignTop)
        self._sections_lay.setContentsMargins(32, 18, 32, 28)

        scroll.setWidget(self._grid_container)
        root.addWidget(scroll, 1)

        # ── Séparation + « Plan des décors » (synchro Mise en scène / Plan de feu) ──
        fp_sep = QFrame()
        fp_sep.setFixedHeight(1)
        fp_sep.setStyleSheet(f"background:{CP['border']};")
        root.addWidget(fp_sep)
        root.addWidget(self._build_floor_plans_section())

        self._fp_worker = None
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

        # Sauvegarder / Ouvrir un décor — à côté de la barre de recherche.
        self._btn_save_file, self._btn_open_file = make_save_open_buttons(
            self, kind="decors",
            list_fn=decors_api.list_decors,
            save_fn=decors_api.save_decor,
            delete_fn=decors_api.delete_decor,
            refresh_fn=self.refresh)
        lay.addWidget(self._btn_save_file)
        lay.addWidget(self._btn_open_file)

        # Séparateur (espace + trait) entre le groupe fichier et « Créer ».
        lay.addSpacing(6)
        lay.addWidget(toolbar_separator())
        lay.addSpacing(6)

        btn_new = QPushButton("✦  Créer un décor")
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

    # ── Plan des décors (vue de dessus, partagée avec Mise en scène / Plan de feu) ──

    def _build_floor_plans_section(self):
        wrap = QWidget()
        wrap.setFixedHeight(168)
        wrap.setStyleSheet(f"background:{CP['bg0']};")
        v = QVBoxLayout(wrap)
        v.setContentsMargins(32, 8, 32, 10)
        v.setSpacing(4)

        head = QHBoxLayout()
        lbl = QLabel("▦  " + translate("Plan des décors"))
        lbl.setStyleSheet(
            f"color:{CP['text_secondary']};font-size:12px;font-weight:700;"
            f"letter-spacing:1px;background:transparent;")
        head.addWidget(lbl)
        sub = QLabel(translate("— vus de dessus, synchronisés avec Mise en scène et Plan de feu"))
        sub.setStyleSheet(f"color:{CP['text_dim']};font-size:9px;background:transparent;")
        head.addWidget(sub)
        head.addStretch()
        self._fp_btn = QPushButton("✦  " + translate("Générer les plans manquants"))
        self._fp_btn.setFixedHeight(28)
        self._fp_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._fp_btn.setStyleSheet(
            f"QPushButton{{background:transparent;color:{CP['accent']};"
            f"border:1px solid {CP['accent_dim']};border-radius:6px;"
            f"font-size:10px;font-weight:700;padding:0 12px;}}"
            f"QPushButton:hover{{background:rgba(78,205,196,0.10);}}"
            f"QPushButton:disabled{{color:{CP['text_dim']};border-color:{CP['border']};}}")
        self._fp_btn.clicked.connect(self._on_gen_missing_plans)
        head.addWidget(self._fp_btn)
        v.addLayout(head)

        hs = QScrollArea()
        hs.setWidgetResizable(True)
        hs.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        hs.setStyleSheet("QScrollArea{background:transparent;border:none;}")
        inner = QWidget()
        inner.setStyleSheet("background:transparent;")
        self._fp_row = QHBoxLayout(inner)
        self._fp_row.setContentsMargins(0, 4, 0, 0)
        self._fp_row.setSpacing(12)
        self._fp_row.addStretch()
        hs.setWidget(inner)
        v.addWidget(hs, 1)
        return wrap

    def _fp_card(self, decor: dict, display_name: str | None = None):
        disp = display_name or decor.get("name", "—")
        card = QWidget()
        card.setFixedSize(132, 104)
        cv = QVBoxLayout(card)
        cv.setContentsMargins(0, 0, 0, 0)
        cv.setSpacing(0)
        thumb = QLabel()
        thumb.setFixedSize(132, 78)
        thumb.setAlignment(Qt.AlignmentFlag.AlignCenter)
        fp = decor.get("floor_plan", "")
        has = bool(fp and os.path.isfile(fp))
        thumb.setStyleSheet(
            f"background:{CP['bg3']};border:1px solid {CP['border']};"
            f"border-radius:8px 8px 0 0;color:{CP['text_dim']};font-size:11px;")
        if has:
            pix = QPixmap(fp).scaled(
                132, 78, Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                Qt.TransformationMode.SmoothTransformation)
            pix = pix.copy((pix.width() - 132) // 2, (pix.height() - 78) // 2, 132, 78)
            thumb.setPixmap(pix)
            # Clic → aperçu en grand + options (variation / import).
            thumb.setCursor(Qt.CursorShape.PointingHandCursor)
            thumb.setToolTip(translate("Cliquer pour agrandir et modifier le plan"))

            def _click(e, _d=decor):
                if e.button() == Qt.MouseButton.LeftButton:
                    self._open_plan_preview(_d)
            thumb.mousePressEvent = _click
        else:
            thumb.setText("▦\n" + translate("à générer"))
        cv.addWidget(thumb)
        name = QLabel(disp)
        name.setFixedHeight(26)
        name.setAlignment(Qt.AlignmentFlag.AlignCenter)
        name.setStyleSheet(
            f"color:{CP['text_primary'] if has else CP['text_dim']};font-size:9px;"
            f"background:{CP['bg2']};border:1px solid {CP['border']};border-top:none;"
            f"border-radius:0 0 8px 8px;")
        cv.addWidget(name)
        card.setToolTip(disp)
        return card

    def _open_plan_preview(self, decor: dict):
        """Aperçu du plan d'architecte + OPTIONS : créer une variation (calée sur le
        plan d'ensemble) ou importer une image (ex. retouche Photoshop). Tout
        changement est resynchronisé : la Mise en scène et le Plan de feu lisent
        `decor.floor_plan` en direct → ils utilisent le nouveau plan."""
        path = decor.get("floor_plan", "")
        name = decor.get("room_group") or decor.get("name", "")
        if not (path and os.path.isfile(path)):
            return
        from PyQt6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton
        from PyQt6.QtGui import QGuiApplication
        dlg = QDialog(self)
        dlg.setWindowTitle((f"{translate('Plan du décor')} — {name}") if name else translate("Plan du décor"))
        dlg.setStyleSheet(f"background:{CP['bg1']};")
        lay = QVBoxLayout(dlg)
        lay.setContentsMargins(12, 12, 12, 12)
        lay.setSpacing(10)
        lbl = QLabel()
        lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        scr = QGuiApplication.primaryScreen().availableGeometry()
        maxw, maxh = int(scr.width() * 0.78), int(scr.height() * 0.72)
        pix = QPixmap(path)
        if pix.width() > maxw or pix.height() > maxh:
            pix = pix.scaled(maxw, maxh, Qt.AspectRatioMode.KeepAspectRatio,
                             Qt.TransformationMode.SmoothTransformation)
        lbl.setPixmap(pix)
        lay.addWidget(lbl)

        def _action_btn(text, accent=False):
            b = QPushButton(text)
            b.setFixedHeight(34)
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            if accent:
                b.setStyleSheet(
                    f"QPushButton{{background:{CP['accent']};color:#07080f;border:none;"
                    f"border-radius:8px;font-size:11px;font-weight:700;padding:0 16px;}}"
                    f"QPushButton:hover{{background:#6eded6;}}")
            else:
                b.setStyleSheet(
                    f"QPushButton{{background:transparent;color:{CP['text_secondary']};"
                    f"border:1px solid {CP['border']};border-radius:8px;font-size:11px;padding:0 16px;}}"
                    f"QPushButton:hover{{color:{CP['text_primary']};border-color:{CP['accent']};}}")
            return b

        row = QHBoxLayout()
        row.setSpacing(10)
        btn_var = _action_btn("🎲  " + translate("Créer une variation (calée sur l'ensemble)"), accent=True)
        btn_var.clicked.connect(lambda: (dlg.accept(), self._on_plan_variation(decor)))
        btn_imp = _action_btn("📂  " + translate("Importer une image"))
        btn_imp.clicked.connect(lambda: (dlg.accept(), self._on_plan_import(decor)))
        btn_close = _action_btn(translate("Fermer"))
        btn_close.clicked.connect(dlg.accept)
        row.addWidget(btn_var)
        row.addWidget(btn_imp)
        row.addStretch()
        row.addWidget(btn_close)
        lay.addLayout(row)
        dlg.exec()

    def _apply_floor_plan_by_id(self, decor_id: str, path: str):
        """Affecte le plan au décor ET à tous ses frères de pièce (room_group), puis
        rafraîchit. La Mise en scène / le Plan de feu lisent ce plan en direct."""
        if not (decor_id and path and os.path.isfile(path)):
            return
        target = next((d for d in self._all_items if d.get("id") == decor_id), None)
        group = (target or {}).get("room_group", "") if target else ""
        ids = ([d.get("id") for d in self._all_items
                if d.get("room_group", "") == group and d.get("id")]
               if group else [decor_id])
        for did in ids:
            try:
                decors_api.set_floor_plan(did, path)
            except Exception:
                pass
        self.refresh()

    def _on_plan_import(self, decor: dict):
        """Importer une image comme plan d'architecte (ex. retouche Photoshop)."""
        from PyQt6.QtWidgets import QFileDialog
        p, _ = QFileDialog.getOpenFileName(
            self, translate("Importer un plan d'architecte"), "",
            "Images (*.png *.jpg *.jpeg *.webp)")
        if not p:
            return
        dst = p
        try:
            import time as _t
            import shutil as _sh
            from core.staging import images_dir
            dst = os.path.join(images_dir(),
                               f"floorplan_import_{int(_t.time())}{os.path.splitext(p)[1].lower()}")
            _sh.copy2(p, dst)
        except Exception:
            dst = p
        self._apply_floor_plan_by_id(decor.get("id", ""), dst)

    def _on_plan_variation(self, decor: dict):
        """Créer une variation du plan, calée sur le plan d'ensemble (image du décor)."""
        from core.config import load_config
        if self._fp_worker is not None and self._fp_worker.isRunning():
            return
        if getattr(self, "_fp_var_worker", None) and self._fp_var_worker.isRunning():
            return
        if not load_config().get("api_key", "").strip():
            QMessageBox.information(
                self, translate("Variation du plan"),
                translate("Configure ta clé fal.ai dans Paramètres pour générer une variation."))
            return
        from api.nano_banana import GenerateFloorPlanVariationWorker
        from core.worker import abandon_thread
        prev = getattr(self, "_fp_var_worker", None)
        if prev is not None:
            abandon_thread(prev)
        self._fp_var_worker = GenerateFloorPlanVariationWorker(
            decor.get("id", ""), decor.get("image_path", ""),
            decor.get("prompt") or decor.get("name", ""))
        self._fp_var_worker.done.connect(self._on_plan_variation_done)
        self._fp_var_worker.start()
        if hasattr(self, "_fp_btn"):
            self._fp_btn.setEnabled(False)
            self._fp_btn.setText("✦  " + translate("Variation du plan…"))

    def _on_plan_variation_done(self, decor_id: str, path: str):
        from core.worker import abandon_thread
        w = getattr(self, "_fp_var_worker", None)
        if w is not None:
            abandon_thread(w)
            self._fp_var_worker = None
        if path and os.path.isfile(path):
            self._apply_floor_plan_by_id(decor_id, path)
        else:
            QMessageBox.warning(
                self, translate("Variation du plan"),
                translate("La variation n'a pas pu être générée (clé fal.ai ? réseau ?)."))
            self._refresh_floor_plans()

    def _fp_representatives(self) -> list[dict]:
        """Un plan par PIÈCE (room_group) + chaque décor libre — les 7 vues d'une
        pièce partagent le même plan vu de dessus, on n'en affiche donc qu'un."""
        seen, out = set(), []
        for d in self._all_items:
            g = d.get("room_group", "") or ""
            key = ("g:" + g) if g else ("d:" + d.get("id", ""))
            if key in seen:
                continue
            seen.add(key)
            out.append(d)
        return out

    def _refresh_floor_plans(self):
        if not hasattr(self, "_fp_row"):
            return
        while self._fp_row.count() > 1:   # garde le stretch final
            it = self._fp_row.takeAt(0)
            if it.widget():
                it.widget().deleteLater()
        reps = self._fp_representatives()
        for d in reps:
            disp = d.get("room_group") or d.get("name", "—")
            self._fp_row.insertWidget(self._fp_row.count() - 1, self._fp_card(d, disp))
        missing = sum(1 for d in reps
                      if not (d.get("floor_plan") and os.path.isfile(d["floor_plan"])))
        if hasattr(self, "_fp_btn"):
            self._fp_btn.setEnabled(missing > 0 and (self._fp_worker is None
                                                     or not self._fp_worker.isRunning()))
            self._fp_btn.setText("✦  " + translate("Générer les plans manquants")
                                 + (f" ({missing})" if missing else ""))

    def _on_gen_missing_plans(self):
        if self._fp_worker is not None and self._fp_worker.isRunning():
            return
        decors = [d for d in self._fp_representatives()
                  if not (d.get("floor_plan") and os.path.isfile(d["floor_plan"]))]
        if not decors:
            return
        jobs = [{"id": d["id"], "prompt": d.get("prompt") or d.get("name", ""),
                 "name": d.get("name", "plan")} for d in decors if d.get("id")]
        from api.nano_banana import GenerateFloorPlansWorker
        self._fp_worker = GenerateFloorPlansWorker(jobs)
        self._fp_worker.plan_done.connect(self._on_fp_plan_done)
        self._fp_worker.finished.connect(self._on_fp_plans_finished)
        self._fp_btn.setEnabled(False)
        self._fp_btn.setText(translate("Génération…"))
        self._fp_worker.start()

    def _on_fp_plan_done(self, decor_id: str, path: str):
        if path:
            try:
                decors_api.set_floor_plan(decor_id, path)
            except Exception:
                pass

    def _on_fp_plans_finished(self, n: int):
        self.refresh()

    def refresh(self):
        self._all_items = decors_api.list_decors()
        self._apply_filter()
        self._refresh_floor_plans()

    def _apply_filter(self):
        cat = self._cat_filter.currentText()
        q   = self._search.text().lower()
        items = self._all_items
        if cat != translate("Toutes"):
            items = [d for d in items if d.get("category") == to_source(cat)]
        if q:
            items = [d for d in items if q in d.get("name", "").lower()]
        self._render(items)

    def _render(self, items: list[dict]):
        # Vide les sections existantes.
        while self._sections_lay.count():
            w = self._sections_lay.takeAt(0)
            if w.widget():
                w.widget().deleteLater()

        if not items:
            empty = QLabel("Aucun décor.\nClique sur ✦ Créer un décor pour commencer.")
            empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
            empty.setStyleSheet(
                f"color:{CP['text_dim']};font-size:13px;background:transparent;border:none;"
            )
            self._sections_lay.addWidget(empty)
            return

        # Décors libres (sans pièce) en grille simple ; chaque pièce (room_group)
        # dans un bandeau dépliable regroupant ses vues.
        for group, group_items in decors_api.group_by_room(items):
            if group:
                self._sections_lay.addWidget(self._group_section(group, group_items))
            else:
                self._sections_lay.addWidget(self._cards_grid(group_items))
        self._sections_lay.addStretch(1)

    def _make_card(self, item: dict) -> DecorCard:
        card = DecorCard(item)
        card.edit_requested.connect(self._on_edit)
        card.delete_requested.connect(self._on_delete)
        return card

    def _cards_grid(self, items: list[dict], cols: int = 6) -> QWidget:
        wrap = QWidget()
        wrap.setStyleSheet("background:transparent;")
        g = QGridLayout(wrap)
        g.setSpacing(18)
        g.setContentsMargins(0, 0, 0, 0)
        g.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        for i, item in enumerate(items):
            g.addWidget(self._make_card(item), i // cols, i % cols)
        return wrap

    def _group_section(self, title: str, items: list[dict]) -> QWidget:
        """Bandeau dépliable d'une pièce : en-tête « ▼ <pièce> · N vue(s) » qui
        replie/déplie la grille de ses décors. L'état est mémorisé entre rafraîchis."""
        sec = QWidget()
        sec.setStyleSheet("background:transparent;")
        v = QVBoxLayout(sec)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(8)

        collapsed = self._collapsed.get(title, False)
        n = len(items)

        def _label(open_: bool) -> str:
            return ("▼  " if open_ else "▶  ") + f"{title}   ·   {n} vue(s)"

        head = QPushButton(_label(not collapsed))
        head.setCursor(Qt.CursorShape.PointingHandCursor)
        head.setFixedHeight(34)
        head.setStyleSheet(
            f"QPushButton{{text-align:left;background:{CP['bg2']};color:{CP['text_primary']};"
            f"border:1px solid {CP['border']};border-left:3px solid {CP['accent']};"
            f"border-radius:8px;font-size:12px;font-weight:700;padding:0 14px;}}"
            f"QPushButton:hover{{background:{CP['bg3']};}}")

        # Variations de TOUTE la pièce (toutes les vues du groupe), prompt éditable.
        _acc2 = CP.get("accent2", "#7c6bff")
        btn_var = QPushButton("🎲  " + translate("Variations"))
        btn_var.setFixedHeight(34)
        btn_var.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_var.setToolTip(translate(
            "Créer des variations de TOUTE la pièce (toutes les vues), avec un prompt éditable"))
        btn_var.setStyleSheet(
            f"QPushButton{{background:transparent;color:{_acc2};"
            f"border:1px solid {_acc2};border-radius:8px;font-size:11px;font-weight:700;padding:0 12px;}}"
            f"QPushButton:hover{{background:rgba(124,107,255,0.12);}}")
        btn_var.clicked.connect(
            lambda _=False, t=title, it=list(items): self._on_room_variations(t, it))

        head_row = QHBoxLayout()
        head_row.setSpacing(8)
        head_row.setContentsMargins(0, 0, 0, 0)
        head_row.addWidget(head, 1)
        head_row.addWidget(btn_var)
        v.addLayout(head_row)

        body = self._cards_grid(items)
        body.setVisible(not collapsed)
        v.addWidget(body)

        def _toggle(_=False):
            new_collapsed = not self._collapsed.get(title, False)
            self._collapsed[title] = new_collapsed
            body.setVisible(not new_collapsed)
            head.setText(_label(not new_collapsed))
        head.clicked.connect(_toggle)
        return sec

    def _on_room_variations(self, room_group: str, items: list):
        """Ouvre la fenêtre de variations de la pièce (régénère toutes ses vues
        avec un prompt éditable). Choisir la pièce = tout le groupe d'un coup."""
        from ui.dialog_room_variations import RoomVariationsDialog
        dlg = RoomVariationsDialog(self, room_group, items)
        dlg.created.connect(self.refresh)
        dlg.exec()
        if getattr(dlg, "_created", False):
            self.refresh()

    def _on_delete_all(self):
        if not self._all_items:
            return
        from PyQt6.QtWidgets import QMessageBox
        r = QMessageBox.question(
            self, "Supprimer tous les décors",
            f"Supprimer les {len(self._all_items)} décor(s) ?\nCette action est irréversible.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if r != QMessageBox.StandardButton.Yes:
            return
        for item in list(self._all_items):
            decors_api.delete_decor(item["id"])
        self.refresh()

    def _on_new(self):
        dlg = DecorDialog(self)
        accepted = dlg.exec() == DecorDialog.DialogCode.Accepted
        # Les « 7 vues → 7 décors » persistent même si la fiche est juste fermée.
        if accepted or getattr(dlg, "_decors_created", False):
            self.refresh()

    def _on_edit(self, item: dict):
        dlg = DecorDialog(self, item=item)
        accepted = dlg.exec() == DecorDialog.DialogCode.Accepted
        if accepted or getattr(dlg, "_decors_created", False):
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
