"""
Dialog that extracts elements from a scenario (Claude) then optionally generates
images for each one (Nano Banana) — one stop for all 5 categories.

Two modes offered to the user at launch:
  • Identifier seulement   — extract + save, no image generation
  • Identifier et générer  — extract + save + Nano Banana image per item
"""
import os
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QScrollArea, QWidget, QFrame, QProgressBar,
)
from PyQt6.QtCore import Qt
from ui.styles import CP
from core.i18n import translate


# ── Small item row ─────────────────────────────────────────────────────────────

class _ItemRow(QWidget):
    _STATUS_PENDING  = ("·  En attente",              CP.get("text_dim",       "#5a6a7a"))
    _STATUS_SAVING   = ("↓  Sauvegarde…",              CP.get("text_secondary", "#8899aa"))
    _STATUS_GEN      = ("⟳  Génération image…",       CP.get("accent",         "#4ecdc4"))
    _STATUS_DONE     = ("✓  Image générée",             CP.get("accent",         "#4ecdc4"))
    _STATUS_NO_IMG   = ("✓  Sauvegardé",               CP.get("text_dim",       "#5a6a7a"))
    _STATUS_ERR      = ("⚠  Erreur",                   CP.get("red",            "#ff4f6a"))

    def __init__(self, name: str, badge: str = ""):
        super().__init__()
        lay = QHBoxLayout(self)
        lay.setContentsMargins(10, 6, 10, 6)
        lay.setSpacing(8)

        if badge:
            b = QLabel(badge)
            b.setStyleSheet(
                f"color:#07080f;background:{CP.get('accent','#4ecdc4')};"
                f"border-radius:3px;font-size:8px;font-weight:700;padding:1px 5px;"
            )
            b.setFixedHeight(16)
            lay.addWidget(b)

        self._name_lbl = QLabel(name)
        self._name_lbl.setStyleSheet(
            f"color:{CP['text_primary']};font-size:11px;font-weight:600;background:transparent;"
        )
        lay.addWidget(self._name_lbl, 1)

        self._status_lbl = QLabel(self._STATUS_PENDING[0])
        self._status_lbl.setStyleSheet(
            f"color:{self._STATUS_PENDING[1]};font-size:10px;background:transparent;"
        )
        lay.addWidget(self._status_lbl)

    def set_state(self, key: str):
        s, c = getattr(self, f"_STATUS_{key}", self._STATUS_PENDING)
        self._status_lbl.setText(s)
        self._status_lbl.setStyleSheet(
            f"color:{c};font-size:10px;background:transparent;"
        )


# ── Main dialog ────────────────────────────────────────────────────────────────

class ExtractGenerateDialog(QDialog):
    """
    Usage:
        dlg = ExtractGenerateDialog.for_characters(text, parent)
        dlg.exec()
    """

    def __init__(self, parent, title: str, icon: str, scenario_text: str,
                 extract_worker_cls, save_fn, item_subdir: str,
                 is_characters: bool = False, post_save_fn=None,
                 category_label: str = "éléments"):
        super().__init__(parent)
        self._scenario_text      = scenario_text
        self._extract_cls        = extract_worker_cls
        self._save_fn            = save_fn
        self._post_save_fn       = post_save_fn
        self._subdir             = item_subdir
        self._is_characters      = is_characters
        self._category_label     = category_label
        self._generate_images    = False          # set by user choice
        self._saved_items: list[dict] = []
        self._item_rows:   list[_ItemRow] = []
        self._gen_idx      = 0
        self._extract_worker   = None
        self._gen_worker       = None
        self._cancelled        = False
        self._page_key: str    = ""   # set by factory — page to navigate to after completion
        self._page_label: str  = ""   # label for the navigate button

        self.setWindowTitle(f"{translate('Générer —')} {translate(title)}")
        self.setMinimumWidth(520)
        self.setMinimumHeight(400)
        self.setStyleSheet(f"background:{CP['bg1']};")

        root = QVBoxLayout(self)
        root.setContentsMargins(24, 20, 24, 20)
        root.setSpacing(16)

        # ── Header ──────────────────────────────────────────────────────────────
        hdr = QHBoxLayout()
        ico = QLabel(icon)
        ico.setFixedSize(36, 36)
        ico.setAlignment(Qt.AlignmentFlag.AlignCenter)
        ico.setStyleSheet(f"font-size:22px;background:{CP['bg2']};border-radius:8px;")
        hdr.addWidget(ico)
        _col = QVBoxLayout()
        _col.setSpacing(2)
        _t = QLabel(translate(title))
        _t.setStyleSheet(
            f"color:{CP['text_primary']};font-size:16px;font-weight:700;background:transparent;"
        )
        _col.addWidget(_t)
        self._phase_lbl = QLabel(translate("Choisir une option pour démarrer"))
        self._phase_lbl.setStyleSheet(
            f"color:{CP['text_dim']};font-size:10px;background:transparent;"
        )
        _col.addWidget(self._phase_lbl)
        hdr.addLayout(_col, 1)
        root.addLayout(hdr)

        sep = QFrame()
        sep.setFixedHeight(1)
        sep.setStyleSheet(f"background:{CP['border']};")
        root.addWidget(sep)

        # ── Choice screen ────────────────────────────────────────────────────────
        self._choice_frame = QWidget()
        self._choice_frame.setStyleSheet("background:transparent;")
        choice_lay = QVBoxLayout(self._choice_frame)
        choice_lay.setContentsMargins(0, 8, 0, 8)
        choice_lay.setSpacing(10)

        _hint = QLabel(translate("Comment souhaitez-vous procéder ?"))
        _hint.setStyleSheet(
            f"color:{CP['text_secondary']};font-size:11px;background:transparent;"
        )
        choice_lay.addWidget(_hint)

        btn_identify = QPushButton("  " + translate(f"Identifier les {category_label}"))
        btn_identify.setFixedHeight(44)
        btn_identify.setStyleSheet(
            f"QPushButton{{background:transparent;color:{CP['text_primary']};"
            f"border:1px solid {CP['border']};border-radius:8px;"
            f"font-size:12px;font-weight:600;text-align:left;padding-left:14px;}}"
            f"QPushButton:hover{{background:{CP['bg3']};border-color:{CP['text_secondary']};}}"
        )
        btn_identify.setToolTip(translate("Extrait et sauvegarde les éléments — sans générer d'images"))
        btn_identify.clicked.connect(lambda: self._start(generate=False))
        choice_lay.addWidget(btn_identify)

        btn_gen = QPushButton("  " + translate("Identifier et générer les images"))
        btn_gen.setFixedHeight(44)
        btn_gen.setStyleSheet(
            f"QPushButton{{background:{CP['accent']};color:#07080f;"
            f"border:none;border-radius:8px;"
            f"font-size:12px;font-weight:700;text-align:left;padding-left:14px;}}"
            f"QPushButton:hover{{background:#6eded6;}}"
        )
        btn_gen.setToolTip(translate("Extrait, sauvegarde, puis génère une image via Nano Banana pour chaque élément"))
        btn_gen.clicked.connect(lambda: self._start(generate=True))
        choice_lay.addWidget(btn_gen)

        root.addWidget(self._choice_frame)

        # ── Progress bar (extraction phase, hidden until started) ────────────────
        self._progress = QProgressBar()
        self._progress.setRange(0, 0)
        self._progress.setFixedHeight(4)
        self._progress.setTextVisible(False)
        self._progress.setStyleSheet(
            f"QProgressBar{{background:{CP['bg3']};border:none;border-radius:2px;}}"
            f"QProgressBar::chunk{{background:{CP['accent']};border-radius:2px;}}"
        )
        self._progress.setVisible(False)
        root.addWidget(self._progress)

        self._status_lbl = QLabel("")
        self._status_lbl.setStyleSheet(
            f"color:{CP['text_secondary']};font-size:11px;background:transparent;"
        )
        self._status_lbl.setVisible(False)
        root.addWidget(self._status_lbl)

        # ── Item list (hidden until extraction done) ────────────────────────────
        self._list_frame = QWidget()
        self._list_frame.setVisible(False)
        self._list_frame.setStyleSheet("background:transparent;")
        self._list_lay = QVBoxLayout(self._list_frame)
        self._list_lay.setContentsMargins(0, 0, 0, 0)
        self._list_lay.setSpacing(2)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet("QScrollArea{background:transparent;border:none;}")
        scroll.setWidget(self._list_frame)
        scroll.setMinimumHeight(160)
        root.addWidget(scroll, 1)

        # ── Gen progress ────────────────────────────────────────────────────────
        self._gen_progress = QProgressBar()
        self._gen_progress.setRange(0, 1)
        self._gen_progress.setValue(0)
        self._gen_progress.setFixedHeight(4)
        self._gen_progress.setTextVisible(False)
        self._gen_progress.setStyleSheet(
            f"QProgressBar{{background:{CP['bg3']};border:none;border-radius:2px;}}"
            f"QProgressBar::chunk{{background:{CP.get('orange','#ff8c42')};border-radius:2px;}}"
        )
        self._gen_progress.setVisible(False)
        root.addWidget(self._gen_progress)

        self._gen_lbl = QLabel("")
        self._gen_lbl.setStyleSheet(
            f"color:{CP['text_dim']};font-size:9px;"
            f"font-family:'Consolas',monospace;background:transparent;"
        )
        self._gen_lbl.setVisible(False)
        root.addWidget(self._gen_lbl)

        # ── Footer — bouton Annuler uniquement (la croix suffit pour fermer) ──────
        sep2 = QFrame()
        sep2.setFixedHeight(1)
        sep2.setStyleSheet(f"background:{CP['border']};")
        root.addWidget(sep2)

        footer = QHBoxLayout()
        footer.setContentsMargins(0, 6, 0, 0)
        footer.setSpacing(0)

        self._btn_cancel = QPushButton(translate("✕  Annuler"))
        self._btn_cancel.setFixedHeight(38)
        self._btn_cancel.setMinimumWidth(120)
        self._btn_cancel.setStyleSheet(
            f"QPushButton{{background:{CP['bg3']};color:{CP.get('red','#ff4f6a')};"
            f"border:1px solid rgba(255,79,106,0.40);border-radius:8px;"
            f"font-size:12px;font-weight:700;padding:0 18px;}}"
            f"QPushButton:hover{{background:rgba(255,79,106,0.10);"
            f"border-color:rgba(255,79,106,0.70);}}"
        )
        self._btn_cancel.clicked.connect(self._on_cancel)

        self._btn_navigate = QPushButton("→  Voir")
        self._btn_navigate.setFixedHeight(38)
        self._btn_navigate.setStyleSheet(
            f"QPushButton{{background:{CP['accent']};color:#07080f;"
            f"border:none;border-radius:8px;font-size:12px;font-weight:700;padding:0 18px;}}"
            f"QPushButton:hover{{background:#6eded6;}}"
        )
        self._btn_navigate.clicked.connect(self._on_navigate)
        self._btn_navigate.setVisible(False)

        footer.addWidget(self._btn_cancel)
        footer.addStretch()
        footer.addWidget(self._btn_navigate)
        root.addLayout(footer)

    # ── Cancel / close ────────────────────────────────────────────────────────

    def reject(self):
        self._cancelled = True
        for w in (self._extract_worker, self._gen_worker):
            if w and w.isRunning():
                try:
                    w.finished.disconnect()
                    w.failed.disconnect()
                except Exception:
                    pass
                w.terminate()
        super().reject()

    def _on_cancel(self):
        self.reject()

    def _finish_state(self, show_navigate: bool = False):
        self._btn_cancel.setText("Fermer")
        self._btn_cancel.setStyleSheet(
            f"QPushButton{{background:{CP['bg3']};color:{CP['text_secondary']};"
            f"border:1px solid {CP['border']};border-radius:8px;"
            f"font-size:12px;font-weight:600;padding:0 18px;}}"
            f"QPushButton:hover{{background:{CP['bg2']};}}"
        )
        if show_navigate and self._page_key:
            self._btn_navigate.setText(f"→  {self._page_label}")
            self._btn_navigate.setVisible(True)

    def _on_navigate(self):
        self.accept()

    # ── Mode selection ─────────────────────────────────────────────────────────

    def _start(self, generate: bool):
        if self._cancelled:
            return
        self._generate_images = generate
        self._choice_frame.setVisible(False)
        self._progress.setVisible(True)
        self._status_lbl.setVisible(True)
        self._start_extraction()

    # ── Extraction phase ───────────────────────────────────────────────────────

    def _start_extraction(self):
        self._phase_lbl.setText(translate("Extraction via Claude IA…"))
        self._status_lbl.setText(translate("Claude analyse le scénario…"))
        w = self._extract_cls(self._scenario_text)
        self._extract_worker = w
        w.finished.connect(self._on_extraction_done)
        w.failed.connect(self._on_extraction_failed)
        w.start()

    def _on_extraction_done(self, items: list):
        if self._cancelled:
            return
        self._progress.setRange(0, 1)
        self._progress.setValue(1)

        valid = [it for it in items if it.get("name")]
        if not valid:
            self._status_lbl.setText(translate("Aucun élément identifié dans le scénario."))
            self._phase_lbl.setText(translate("Terminé"))
            self._finish_state()
            if getattr(self, "_auto_close", False):
                from PyQt6.QtCore import QTimer
                QTimer.singleShot(800, self.accept)
            return

        count = len(valid)
        self._list_frame.setVisible(True)

        for it in valid:
            badge = it.get("role") or it.get("category") or it.get("hmc_type") or ""
            row = _ItemRow(it.get("name", "?"), badge=badge)
            self._list_lay.addWidget(row)
            self._item_rows.append(row)
        self._list_lay.addStretch()

        # Save all items first
        for i, it in enumerate(valid):
            row = self._item_rows[i]
            row.set_state("SAVING")
            saved = self._save_fn(it)
            if self._post_save_fn:
                self._post_save_fn(saved, it)
            self._saved_items.append(saved)
            row.set_state("PENDING")

        if self._generate_images:
            self._status_lbl.setText(
                f"{count} élément(s) identifié(s) — génération des images…"
            )
            self._phase_lbl.setText("Génération des images via Nano Banana…")
            n = len(self._saved_items)
            self._gen_progress.setRange(0, n)
            self._gen_progress.setValue(0)
            self._gen_progress.setVisible(True)
            self._gen_lbl.setVisible(True)
            self._gen_idx = 0
            self._gen_next()
        else:
            for row in self._item_rows:
                row.set_state("NO_IMG")
            self._on_all_saved_no_images()

    def _on_extraction_failed(self, err: str):
        if self._cancelled:
            return
        self._progress.setRange(0, 1)
        self._progress.setValue(0)
        self._phase_lbl.setText("Erreur d'extraction")
        self._status_lbl.setText(f"⚠ {err[:120]}")
        self._finish_state()
        if getattr(self, "_auto_close", False):
            from PyQt6.QtCore import QTimer
            QTimer.singleShot(2000, self.accept)

    # ── Save-only completion ───────────────────────────────────────────────────

    def _on_all_saved_no_images(self):
        total = len(self._saved_items)
        self._status_lbl.setText(f"{total} élément(s) sauvegardé(s) — sans image")
        self._phase_lbl.setText("Terminé")
        self._finish_state(show_navigate=True)
        if getattr(self, "_auto_close", False):
            from PyQt6.QtCore import QTimer
            QTimer.singleShot(800, self.accept)

    # ── Image generation phase ─────────────────────────────────────────────────

    def _gen_next(self):
        if self._cancelled:
            return
        if self._gen_idx >= len(self._saved_items):
            self._on_all_done()
            return

        item = self._saved_items[self._gen_idx]
        row  = self._item_rows[self._gen_idx]
        row.set_state("GEN")

        n = len(self._saved_items)
        self._gen_lbl.setText(
            f"Image {self._gen_idx + 1}/{n} — {item.get('name', '?')}"
        )

        prompt = item.get("prompt") or item.get("description") or item.get("name", "")
        name   = item.get("name", "item")

        if self._is_characters:
            from api.nano_banana import GeneratePortraitWorker
            w = GeneratePortraitWorker(
                prompt=prompt,
                char_name=name,
                gen_mode="sheet_5views",
            )
            w.finished.connect(lambda p, s: self._on_img_done(p or s))
            w.failed.connect(self._on_img_failed)
        else:
            from api.nano_banana import GenerateItemWorker
            w = GenerateItemWorker(
                prompt=prompt,
                item_name=name,
                subdir=self._subdir,
            )
            w.finished.connect(self._on_img_done)
            w.failed.connect(self._on_img_failed)

        self._gen_worker = w
        w.start()

    def _on_img_done(self, img_path: str):
        if self._cancelled:
            return
        item = self._saved_items[self._gen_idx]
        row  = self._item_rows[self._gen_idx]

        if img_path and os.path.isfile(img_path):
            item["image_path"] = img_path
            try:
                self._save_fn(item)
            except Exception:
                pass
            row.set_state("DONE")
        else:
            row.set_state("NO_IMG")

        self._gen_progress.setValue(self._gen_idx + 1)
        self._gen_idx += 1
        self._gen_next()

    def _on_img_failed(self, err: str):
        if self._cancelled:
            return
        row = self._item_rows[self._gen_idx]
        row.set_state("ERR")
        self._gen_progress.setValue(self._gen_idx + 1)
        self._gen_idx += 1
        self._gen_next()

    def _on_all_done(self):
        done  = sum(1 for it in self._saved_items if it.get("image_path"))
        total = len(self._saved_items)
        self._gen_lbl.setText(f"✓  Terminé — {done}/{total} image(s) générée(s)")
        self._gen_lbl.setStyleSheet(
            f"color:{CP['accent']};font-size:9px;"
            f"font-family:'Consolas',monospace;background:transparent;"
        )
        self._phase_lbl.setText("Terminé")
        self._status_lbl.setText(
            f"{total} élément(s) sauvegardé(s) · {done} image(s) générée(s)"
        )
        self._finish_state(show_navigate=True)
        if getattr(self, "_auto_close", False):
            from PyQt6.QtCore import QTimer
            QTimer.singleShot(1200, self.accept)

    # ── Factory methods ────────────────────────────────────────────────────────

    @classmethod
    def for_characters(cls, scenario_text: str, parent=None):
        from api.screenplay import ExtractCharactersWorker
        import core.casting as casting_api

        def save(it):
            d = {
                "name":          it.get("name", ""),
                "description":   it.get("description", ""),
                "prompt":        it.get("prompt") or it.get("description", ""),
                "role":          it.get("role", "Secondaire"),
                "image_path":    it.get("image_path", ""),
                "accessory_ids": it.get("accessory_ids", []),
                "hmc_ids":       it.get("hmc_ids", []),
            }
            if it.get("id"):
                d["id"] = it["id"]
            return casting_api.save_character(d)

        dlg = cls(
            parent,
            title="Personnages depuis le scénario",
            icon="◎",
            scenario_text=scenario_text,
            extract_worker_cls=ExtractCharactersWorker,
            save_fn=save,
            item_subdir="castings",
            is_characters=True,
            category_label="personnages",
        )
        dlg._page_key   = "castings"
        dlg._page_label = "Voir le Casting"
        return dlg

    @classmethod
    def for_decors(cls, scenario_text: str, parent=None):
        from api.screenplay import ExtractDecorsWorker
        import core.decors as decors_api
        import core.storyboard as sb_api

        def save(it):
            d = {
                "name":       it.get("name", ""),
                "prompt":     it.get("prompt") or it.get("description", ""),
                "category":   it.get("category", "Autre"),
                "image_path": it.get("image_path", ""),
                "ref_paths":  it.get("ref_paths", []),
            }
            if it.get("id"):
                d["id"] = it["id"]
            return decors_api.save_decor(d)

        def post_save(saved, raw_it):
            shots = sb_api.list_shots()
            scene_headers = [h.upper() for h in raw_it.get("scene_headers", [])]
            decor_name_up = raw_it.get("name", "").upper()
            decor_id      = saved.get("id", "")
            decor_name    = saved.get("name", "")
            for shot in shots:
                shot_decor  = (shot.get("decor_name") or "").upper()
                shot_header = (shot.get("scene_title") or "").upper()
                match = (
                    (shot_decor and shot_decor == decor_name_up)
                    or any(h and h in shot_header for h in scene_headers)
                    or any(h and shot_decor and shot_decor in h for h in scene_headers)
                )
                if match:
                    updated = dict(shot)
                    updated["decor_id"]   = decor_id
                    updated["decor_name"] = decor_name
                    sb_api.save_shot(updated)

        dlg = cls(
            parent,
            title="Décors depuis le scénario",
            icon="⌂",
            scenario_text=scenario_text,
            extract_worker_cls=ExtractDecorsWorker,
            save_fn=save,
            item_subdir="decors",
            post_save_fn=post_save,
            category_label="décors",
        )
        dlg._page_key   = "decors"
        dlg._page_label = "Voir les Décors"
        return dlg

    @classmethod
    def for_accessories(cls, scenario_text: str, parent=None):
        from api.screenplay import ExtractAccessoriesWorker
        import core.accessories as acc_api

        def save(it):
            d = {
                "name":        it.get("name", ""),
                "description": it.get("description", ""),
                "prompt":      it.get("prompt") or it.get("description", ""),
                "category":    it.get("category", "Autre…"),
                "image_path":  it.get("image_path", ""),
            }
            if it.get("id"):
                d["id"] = it["id"]
            return acc_api.save_accessory(d)

        dlg = cls(
            parent,
            title="Accessoires depuis le scénario",
            icon="⊡",
            scenario_text=scenario_text,
            extract_worker_cls=ExtractAccessoriesWorker,
            save_fn=save,
            item_subdir="accessories",
            category_label="accessoires",
        )
        dlg._page_key   = "accessoires"
        dlg._page_label = "Voir les Accessoires"
        return dlg

    @classmethod
    def for_hmc(cls, scenario_text: str, parent=None):
        from api.screenplay import ExtractHMCWorker
        import core.hmc as hmc_api

        def save(it):
            d = {
                "name":           it.get("name", ""),
                "description":    it.get("description", ""),
                "prompt":         it.get("prompt") or it.get("description", ""),
                "hmc_type":       it.get("hmc_type", "Habit"),
                "image_path":     it.get("image_path", ""),
                "character_name": it.get("character_name", ""),
            }
            if it.get("id"):
                d["id"] = it["id"]
            return hmc_api.save_hmc_item(d)

        dlg = cls(
            parent,
            title="HMC depuis le scénario",
            icon="✂",
            scenario_text=scenario_text,
            extract_worker_cls=ExtractHMCWorker,
            save_fn=save,
            item_subdir="hmc",
            category_label="éléments HMC",
        )
        dlg._page_key   = "hmc"
        dlg._page_label = "Voir le HMC"
        return dlg

    @classmethod
    def for_vehicles(cls, scenario_text: str, parent=None):
        from api.screenplay import ExtractVehiclesWorker
        import core.vehicles as veh_api

        def save(it):
            d = {
                "name":        it.get("name", ""),
                "description": it.get("description", ""),
                "prompt":      it.get("prompt") or it.get("description", ""),
                "category":    it.get("category", "Autre"),
                "image_path":  it.get("image_path", ""),
            }
            if it.get("id"):
                d["id"] = it["id"]
            return veh_api.save_vehicle(d)

        dlg = cls(
            parent,
            title="Véhicules depuis le scénario",
            icon="🚗",
            scenario_text=scenario_text,
            extract_worker_cls=ExtractVehiclesWorker,
            save_fn=save,
            item_subdir="vehicles",
            category_label="véhicules",
        )
        dlg._page_key   = "vehicles"
        dlg._page_label = "Voir les Véhicules"
        return dlg
