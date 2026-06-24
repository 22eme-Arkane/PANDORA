"""
ui/page_staging.py — Mise en scène & Plan de feu (vue de dessus, par plan).

PageStaging (mode 'staging') : place CAMÉRA, personnages et éléments sur un plan
vu de dessus issu du décor. L'axe caméra est réécrit dans le plan du storyboard.
PageLighting (mode 'lighting') : place les LUMIÈRES (type de projecteur +
direction) sur le MÊME plan — record partagé par plan (core/staging).

Le plan de fond vient d'un DÉCOR : par défaut celui assigné au plan du storyboard,
mais un sélecteur permet de choisir un AUTRE décor par plan (rec["plan_decor_id"]).

« Synchronisation » remplace l'ancienne génération de plan :
  · storyboard → plans : chaque plan reprend le plan vu de dessus de son décor ;
  · mise en scène → storyboard : place les comédiens dans la section [MISE EN SCÈNE]
    du prompt et la caméra dans les champs techniques (camera_axis / camera_placement) ;
  · plan de feu → storyboard : alimente la section [PLAN DE FEU] du prompt.
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QComboBox,
    QListWidget, QListWidgetItem, QInputDialog, QMenu, QMessageBox, QFileDialog,
)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QShortcut, QKeySequence
from ui.styles import CP
from ui.widgets import HelpBlock
from ui.staging_canvas import StagingCanvas
from core.i18n import translate
import os
import core.storyboard as sb_api
import core.staging as staging
import core.decors as decors_api


def _btn(label: str) -> QPushButton:
    b = QPushButton(label)
    b.setMinimumHeight(34)
    b.setCursor(Qt.CursorShape.PointingHandCursor)
    b.setStyleSheet(
        f"QPushButton{{background:{CP['bg3']};color:{CP['text_primary']};"
        f"border:1px solid {CP['border']};border-radius:7px;font-size:11px;"
        f"font-weight:600;padding:0 12px;}}"
        f"QPushButton:hover{{background:{CP['bg2']};border-color:{CP['accent_dim']};}}"
    )
    return b


class PageStaging(QWidget):

    MODE = "staging"

    def __init__(self):
        super().__init__()
        self._mode = self.MODE
        self._shots: list[dict] = []
        self._shot: dict | None = None
        self.setStyleSheet(f"background:{CP['bg0']};")

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ── Bandeau ────────────────────────────────────────────────────────────
        band = QWidget()
        band.setFixedHeight(60)
        band.setStyleSheet(f"background:{CP['bg1']};border-bottom:1px solid {CP['border']};")
        bl = QHBoxLayout(band)
        bl.setContentsMargins(20, 0, 20, 0)
        title = QLabel(("🎬  " if self._mode == "staging" else "💡  ")
                       + translate("Mise en scène" if self._mode == "staging" else "Plan de feu"))
        title.setStyleSheet(
            f"color:{CP['text_primary']};font-size:16px;font-weight:700;background:transparent;")
        bl.addWidget(title)
        bl.addStretch()
        root.addWidget(band)

        hb = HelpBlock(
            "Mise en scène — plan vu de dessus" if self._mode == "staging"
            else "Plan de feu — éclairage vu de dessus",
            self._help_lines(), CP)
        _hw = QWidget(); _hl = QVBoxLayout(_hw)
        _hl.setContentsMargins(20, 8, 20, 4); _hl.addWidget(hb)
        root.addWidget(_hw)

        # ── Corps : liste des plans (gauche) + canevas (droite) ─────────────────
        body = QHBoxLayout()
        body.setContentsMargins(16, 8, 16, 16)
        body.setSpacing(12)

        left = QVBoxLayout()
        left.setSpacing(6)
        _lst_lbl = QLabel(translate("Plans du storyboard"))
        _lst_lbl.setStyleSheet(f"color:{CP['text_dim']};font-size:10px;font-weight:700;"
                               f"letter-spacing:1px;background:transparent;")
        left.addWidget(_lst_lbl)
        self._list = QListWidget()
        self._list.setFixedWidth(220)
        self._list.setStyleSheet(
            f"QListWidget{{background:{CP['bg2']};border:1px solid {CP['border']};"
            f"border-radius:8px;color:{CP['text_primary']};font-size:12px;padding:4px;}}"
            f"QListWidget::item{{padding:6px 8px;border-radius:5px;}}"
            f"QListWidget::item:selected{{background:{CP['accent_dim']};color:#07080f;}}"
        )
        self._list.currentRowChanged.connect(self._on_shot_changed)
        # Clic droit sur un plan → copier la mise en scène / le plan de feu d'un
        # autre plan (scènes similaires : ne pas tout recréer).
        self._list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._list.customContextMenuRequested.connect(self._on_list_context)
        left.addWidget(self._list, 1)
        body.addLayout(left)

        right = QVBoxLayout()
        right.setSpacing(8)
        self._canvas = StagingCanvas(mode=self._mode)
        self._canvas.changed.connect(self._autosave)
        self._canvas.actor_context.connect(self._on_actor_context)
        self._canvas.light_context.connect(self._on_light_context)
        self._canvas.camera_context.connect(self._on_camera_context)
        self._canvas.empty_context.connect(self._on_empty_context)
        # Auto-synchro INSTANTANÉE des sections du prompt — débouncée (250 ms) pour
        # rester fluide pendant un glissé. Mise en scène → [🎭 MISE EN SCÈNE] + axe /
        # placement caméra ; Plan de feu → [💡 PLAN DE FEU]. Plus besoin du menu.
        self._sync_timer = QTimer(self)
        self._sync_timer.setSingleShot(True)
        self._sync_timer.setInterval(250)
        self._sync_timer.timeout.connect(self._apply_current_to_storyboard)
        # Analyse VISION (Claude lit le plan du décor pour situer persos/caméra/
        # lumière par rapport au mobilier visible) — débounce plus long, en plus du
        # placement déterministe instantané. Démarrée par _autosave.
        self._vision_timer = QTimer(self)
        self._vision_timer.setSingleShot(True)
        self._vision_timer.setInterval(1500)
        self._vision_timer.timeout.connect(self._run_vision)
        self._vision_worker = None
        self._vision_shot_id = None
        right.addLayout(self._build_toolbar())
        right.addWidget(self._canvas, 1)
        body.addLayout(right, 1)
        root.addLayout(body, 1)

        # Suppr / Retour arrière : retire le jeton sélectionné (la poubelle a été
        # retirée de la barre ; le déplacement et la rotation se font à la souris).
        self._sc_del = QShortcut(QKeySequence(QKeySequence.StandardKey.Delete), self)
        self._sc_del.activated.connect(self._canvas.remove_selected)
        self._sc_bs = QShortcut(QKeySequence(Qt.Key.Key_Backspace), self)
        self._sc_bs.activated.connect(self._canvas.remove_selected)

    # ── Contenu spécifique au mode ──────────────────────────────────────────────

    def _help_lines(self):
        if self._mode == "staging":
            return [
                "▸ Sélectionnez un plan, choisissez le plan de décor à utiliser, puis placez la caméra, les acteurs et les éléments.",
                "▸ Glissez les jetons à la souris ; pivotez la caméra avec sa poignée ou ⟲ ⟳. L'axe caméra est réécrit dans le storyboard.",
                "▸ « Synchronisation » a DEUX sens : storyboard → mise en scène (reconstruit acteurs/caméra et récupère les plans de décor, ex. après « Tout supprimer ») ; mise en scène → storyboard (met à jour les prompts).",
            ]
        return [
            "▸ Reprend le plan de la Mise en scène : placez les projecteurs et choisissez leur type.",
            "▸ Glissez chaque lumière à la souris, orientez-la avec sa poignée ou ⟲ ⟳ pour définir le faisceau.",
            "▸ « Synchronisation » renvoie l'éclairage défini ici vers les prompts du storyboard.",
        ]

    def _build_toolbar(self) -> QHBoxLayout:
        tb = QHBoxLayout()
        tb.setSpacing(8)

        # Sélecteur : quel plan de décor utiliser pour CE plan du storyboard.
        _pl_lbl = QLabel(translate("Plan du décor :"))
        _pl_lbl.setStyleSheet(f"color:{CP['text_dim']};font-size:11px;background:transparent;")
        tb.addWidget(_pl_lbl)
        self._plan_combo = QComboBox()
        self._plan_combo.setMinimumWidth(190)
        self._plan_combo.setStyleSheet(
            f"QComboBox{{background:{CP['bg3']};color:{CP['text_primary']};"
            f"border:1px solid {CP['border']};border-radius:7px;font-size:11px;"
            f"padding:5px 10px;}}"
            f"QComboBox:hover{{border-color:{CP['accent_dim']};}}")
        self._plan_combo.currentIndexChanged.connect(self._on_plan_decor_changed)
        tb.addWidget(self._plan_combo)

        # Sauvegarder / Ouvrir (dossier dédié : « Mise en scène » ou « Plan de feu »).
        b_save = _btn("💾  " + translate("Sauvegarder"))
        b_save.clicked.connect(self._on_save_staging)
        b_open = _btn("📂  " + translate("Ouvrir"))
        b_open.clicked.connect(self._on_open_staging)
        tb.addWidget(b_save)
        tb.addWidget(b_open)

        # Ajout d'un élément selon le mode (déplacement + rotation = souris/poignée ;
        # suppression d'un jeton = touche Suppr ou clic droit → Supprimer).
        if self._mode == "staging":
            b_actor = _btn("＋ " + translate("Ajouter acteur"))
            b_actor.clicked.connect(self._add_actor)
            tb.addWidget(b_actor)
        else:
            b_light = _btn("＋ " + translate("Lumière"))
            b_light.clicked.connect(self._add_light)
            tb.addWidget(b_light)
        tb.addStretch()

        # « Synchronisation » — remplace « Générer le plan ». Menu déroulant.
        self._btn_sync = _btn("⟳  " + translate("Synchronisation"))
        self._btn_sync.clicked.connect(self._open_sync_menu)
        tb.addWidget(self._btn_sync)

        # « Tout supprimer » — bouton rouge à DROITE (même emplacement que dans
        # le Storyboard). Vide tous les éléments éditables du plan courant.
        self._btn_clear_all = QPushButton("✕  " + translate("Tout supprimer"))
        self._btn_clear_all.setCursor(Qt.CursorShape.PointingHandCursor)
        _red = CP.get("red", "#ff4f6a")
        self._btn_clear_all.setStyleSheet(
            f"QPushButton{{background:transparent;color:{_red};"
            f"border:1px solid {_red};border-radius:8px;"
            f"font-size:12px;font-weight:700;padding:7px 16px;}}"
            f"QPushButton:hover{{background:rgba(255,79,106,0.12);}}")
        self._btn_clear_all.clicked.connect(self._on_clear_all)
        tb.addWidget(self._btn_clear_all)
        return tb

    def _on_clear_all(self):
        # Rien à supprimer ? (ex. Plan de feu sans projecteur, ou plan déjà vide) →
        # on le DIT clairement (sinon le clic semble « ne rien faire »).
        if not self._canvas.has_clearable():
            QMessageBox.information(
                self, translate("Tout supprimer"),
                translate("Rien à supprimer sur ce plan."))
            return
        box = QMessageBox(self)
        box.setIcon(QMessageBox.Icon.Warning)
        box.setWindowTitle(translate("Tout supprimer"))
        box.setText(translate("Tout supprimer du plan ? Cette action est irréversible."))
        box.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        box.setDefaultButton(QMessageBox.StandardButton.No)
        if box.exec() == QMessageBox.StandardButton.Yes:
            self._canvas.clear_all()   # émet changed → autosave (vide aussi le plan)
            self._refresh_plan_combo()  # reflète « Aucun plan »

    # ── Données ─────────────────────────────────────────────────────────────────

    def showEvent(self, e):
        super().showEvent(e)
        self.refresh()

    def refresh(self):
        cur = self._shot.get("id") if self._shot else None
        try:
            versions = sb_api.list_versions()
            vid = versions[0]["id"] if versions else sb_api.DEFAULT_VERSION_ID
            self._shots = sb_api.list_shots(vid)
        except Exception:
            self._shots = []
        self._list.blockSignals(True)
        self._list.clear()
        for s in self._shots:
            num = s.get("number", "?")
            self._list.addItem(QListWidgetItem(f"Plan {num} — {s.get('scene_title', '')[:24]}"))
        self._list.blockSignals(False)
        if self._shots:
            idx = next((i for i, s in enumerate(self._shots) if s.get("id") == cur), 0)
            self._list.setCurrentRow(idx)

    def _resolve_floor_plan(self, shot: dict, rec: dict) -> str:
        """Plan vu de dessus à afficher : décor choisi pour CE plan (plan_decor_id),
        sinon le décor assigné dans le storyboard. « __none__ » = aucun plan
        (forcé par « Tout supprimer »)."""
        override = rec.get("plan_decor_id", "")
        if override == "__none__":
            return ""
        if override:
            dec = decors_api.get_decor(override)
            return (dec or {}).get("floor_plan", "")
        return decors_api.floor_plan_for_shot(shot)

    def _on_shot_changed(self, row: int):
        if row < 0 or row >= len(self._shots):
            self._shot = None
            return
        self._shot = self._shots[row]
        rec = staging.get(self._shot["id"])
        fp = self._resolve_floor_plan(self._shot, rec)
        if fp and os.path.isfile(fp):
            rec["plan_image"] = fp
        # Amorçage : acteurs + CAMÉRA (selon l'axe du plan) depuis le storyboard, UNE
        # SEULE FOIS — repli pour les storyboards créés avant le semis à la génération.
        # Le flag « _actors_seeded » évite de re-semer après un « Tout supprimer ».
        if self._mode == "staging":
            if not rec.get("_actors_seeded"):
                seeded = staging.seed_record_for_shot(self._shot)
                if not rec.get("actors"):
                    rec["actors"] = seeded["actors"]
                rec["camera"] = seeded["camera"]   # caméra placée selon camera_axis
            rec["_actors_seeded"] = True
        self._canvas.load(rec)
        self._refresh_plan_combo()

    def _reload_current(self):
        self._on_shot_changed(self._list.currentRow())

    def _refresh_plan_combo(self):
        if not hasattr(self, "_plan_combo"):
            return
        self._plan_combo.blockSignals(True)
        self._plan_combo.clear()
        self._plan_combo.addItem(translate("Auto (décor du plan)"), "")
        self._plan_combo.addItem(translate("Aucun plan (vide)"), "__none__")
        try:
            for d in decors_api.list_decors():
                name = d.get("name") or translate("(décor sans nom)")
                # ◆ = un plan vu de dessus existe déjà pour ce décor.
                label = ("◆ " + name) if d.get("floor_plan") else name
                self._plan_combo.addItem(label, d.get("id", ""))
        except Exception:
            pass
        cur = staging.get(self._shot["id"]).get("plan_decor_id", "") if self._shot else ""
        idx = 0
        for i in range(self._plan_combo.count()):
            if self._plan_combo.itemData(i) == cur:
                idx = i
                break
        self._plan_combo.setCurrentIndex(idx)
        self._plan_combo.blockSignals(False)

    def _on_plan_decor_changed(self, idx: int):
        if not self._shot:
            return
        rec = staging.get(self._shot["id"])
        rec["plan_decor_id"] = self._plan_combo.currentData() or ""
        fp = self._resolve_floor_plan(self._shot, rec)
        rec["plan_image"] = fp if (fp and os.path.isfile(fp)) else ""
        staging.save(self._shot["id"], rec)
        self._canvas.load(rec)

    # ── Actions ─────────────────────────────────────────────────────────────────

    def _add_actor(self):
        # Liste COMPLÈTE du casting du projet (+ les personnages déjà sur ce plan).
        chars = []
        try:
            import core.casting as casting
            chars = [c.get("name", "") for c in casting.list_characters() if c.get("name")]
        except Exception:
            chars = []
        for n in (self._shot or {}).get("character_names", []) or []:
            if n and n not in chars:
                chars.append(n)
        if chars:
            menu = QMenu(self)
            for n in chars:
                menu.addAction(n, lambda _=False, nm=n: self._canvas.add_actor(nm))
            menu.addSeparator()
            menu.addAction(translate("Autre…"), self._add_actor_free)
            menu.exec(self.cursor().pos())
        else:
            self._add_actor_free()

    def _add_actor_free(self):
        name, ok = QInputDialog.getText(self, translate("Acteur"), translate("Nom :"))
        if ok and name.strip():
            self._canvas.add_actor(name.strip())

    def _add_light(self):
        from ui.dialog_projector import ProjectorDialog
        dlg = ProjectorDialog(self)
        if dlg.exec() == ProjectorDialog.DialogCode.Accepted:
            r = dlg.result_data()
            if r:
                self._canvas.add_light(r["name"], r["role"],
                                       r.get("family", ""), r.get("model", ""))

    # ── Clic droit sur le VIDE du canevas → ajout au point cliqué ────────────────

    def _on_empty_context(self, x: float, y: float):
        menu = QMenu(self)
        if self._mode == "staging":
            chars = []
            try:
                import core.casting as casting
                chars = [c.get("name", "") for c in casting.list_characters() if c.get("name")]
            except Exception:
                chars = []
            for n in (self._shot or {}).get("character_names", []) or []:
                if n and n not in chars:
                    chars.append(n)
            sub = menu.addMenu(translate("Ajouter un acteur"))
            for n in chars:
                sub.addAction(n, lambda _=False, nm=n: self._canvas.add_actor(nm, x, y))
            if chars:
                sub.addSeparator()
            sub.addAction(translate("Autre…"), lambda: self._add_actor_free_at(x, y))
            menu.addAction(translate("Placer la caméra ici"),
                           lambda: self._canvas.place_camera(x, y))
        else:
            menu.addAction(translate("Créer un projecteur"), lambda: self._add_light_at(x, y))
        menu.exec(self.cursor().pos())

    def _add_actor_free_at(self, x: float, y: float):
        name, ok = QInputDialog.getText(self, translate("Acteur"), translate("Nom :"))
        if ok and name.strip():
            self._canvas.add_actor(name.strip(), x, y)

    def _add_light_at(self, x: float, y: float):
        from ui.dialog_projector import ProjectorDialog
        dlg = ProjectorDialog(self)
        if dlg.exec() == ProjectorDialog.DialogCode.Accepted:
            r = dlg.result_data()
            if r:
                self._canvas.add_light(r["name"], r["role"],
                                       r.get("family", ""), r.get("model", ""), x, y)

    # ── Clic droit : changer l'acteur (Mise en scène) / le projecteur (Plan de feu) ──

    def _on_actor_context(self, model: dict):
        names = (self._shot or {}).get("character_names", []) or []
        menu = QMenu(self)
        for n in names:
            menu.addAction(n, lambda _=False, nm=n: self._rename_actor(model, nm))
        menu.addAction(translate("Autre…"), lambda: self._rename_actor_free(model))
        menu.addSeparator()
        menu.addAction(translate("Supprimer"), lambda: self._canvas.remove_model(model))
        menu.exec(self.cursor().pos())

    def _rename_actor(self, model: dict, name: str):
        model["name"] = name
        self._canvas.reload()
        self._autosave()

    def _rename_actor_free(self, model: dict):
        name, ok = QInputDialog.getText(self, translate("Acteur"), translate("Nom :"),
                                        text=model.get("name", ""))
        if ok and name.strip():
            self._rename_actor(model, name.strip())

    def _on_light_context(self, model: dict):
        menu = QMenu(self)
        menu.addAction(translate("Modifier le projecteur"), lambda: self._edit_light(model))
        menu.addAction(translate("Réglages du projecteur"), lambda: self._settings_light(model))
        _on = (model.get("settings") or {}).get("on", True)
        menu.addAction(translate("Éteindre le projecteur") if _on else translate("Allumer le projecteur"),
                       lambda: self._toggle_light(model))
        menu.addSeparator()
        menu.addAction(translate("Supprimer"), lambda: self._canvas.remove_model(model))
        menu.exec(self.cursor().pos())

    def _toggle_light(self, model: dict):
        """Allume / éteint le projecteur : éteint → jeton grisé + exclu du prompt."""
        import core.projectors as proj
        s = model.setdefault("settings",
                             proj.default_settings(model.get("family", ""), model.get("model", "")))
        s["on"] = not s.get("on", True)
        self._canvas.reload()
        self._autosave()

    def _on_camera_context(self, model: dict):
        menu = QMenu(self)
        menu.addAction(translate("Hauteur de la caméra"), lambda: self._camera_height(model))
        menu.exec(self.cursor().pos())

    def _camera_height(self, model: dict):
        from PyQt6.QtWidgets import QInputDialog
        cur = float(model.get("height", 1.5) or 1.5)
        h, ok = QInputDialog.getDouble(self, translate("Hauteur de la caméra"),
                                       translate("Hauteur (m) :"), cur, 0.0, 12.0, 1)
        if ok:
            model["height"] = h
            self._autosave()

    def _settings_light(self, model: dict):
        """Réglages réalistes du projecteur (intensité, température, teinte, ±vert,
        gélatine, faisceau) selon les capacités du modèle → écrits dans le prompt."""
        from ui.dialog_projector_settings import ProjectorSettingsDialog
        dlg = ProjectorSettingsDialog(self, light=model)
        if dlg.exec() == ProjectorSettingsDialog.DialogCode.Accepted:
            r = dlg.result_data()
            if r is not None:
                model["settings"] = r
                self._canvas.reload()
                self._autosave()   # → débounce → réécrit [💡 PLAN DE FEU] avec les réglages

    def _edit_light(self, model: dict):
        from ui.dialog_projector import ProjectorDialog
        dlg = ProjectorDialog(self, role=model.get("type", "key"),
                              family=model.get("family", ""), model=model.get("model", ""))
        if dlg.exec() == ProjectorDialog.DialogCode.Accepted:
            r = dlg.result_data()
            if r:
                model.update({"name": r["name"], "type": r["role"],
                              "family": r.get("family", ""), "model": r.get("model", "")})
                self._canvas.reload()
                self._autosave()

    # ── Synchronisation (remplace « Générer le plan ») ──────────────────────────

    def _open_sync_menu(self):
        menu = QMenu(self)
        menu.setStyleSheet(
            f"QMenu{{background:{CP['bg2']};border:1px solid {CP['border']};"
            f"border-radius:8px;padding:4px 0;}}"
            f"QMenu::item{{color:{CP['text_primary']};padding:8px 18px;font-size:11px;}}"
            f"QMenu::item:selected{{background:{CP['accent_dim']};color:#07080f;}}")
        menu.addAction(translate("Synchroniser les décors (storyboard → plans)"),
                       self._sync_decors)
        if self._mode == "staging":
            menu.addAction(translate("Synchroniser la mise en scène → storyboard"),
                           self._sync_to_storyboard)
            menu.addAction(translate("Synchroniser le storyboard → mise en scène"),
                           self._sync_from_storyboard)
        else:
            menu.addAction(translate("Synchroniser le plan de feu → storyboard"),
                           self._sync_to_storyboard)
        menu.exec(self._btn_sync.mapToGlobal(self._btn_sync.rect().bottomLeft()))

    def _sync_decors(self):
        """storyboard → plans : chaque plan reprend le plan vu de dessus de son décor
        assigné (repasse en Auto, ignore un éventuel choix manuel)."""
        n = 0
        for s in self._shots:
            sid = s.get("id")
            if not sid:
                continue
            rec = staging.get(sid)
            rec["plan_decor_id"] = ""
            fp = decors_api.floor_plan_for_shot(s)
            if fp and os.path.isfile(fp):
                rec["plan_image"] = fp
                n += 1
            staging.save(sid, rec)
        self._reload_current()
        QMessageBox.information(
            self, translate("Synchronisation"),
            translate("Décors synchronisés depuis le storyboard.") + f"  ({n})")

    def _sync_from_storyboard(self):
        """storyboard → mise en scène (sens INVERSE) : reconstruit la mise en scène
        (acteurs + caméra) de CHAQUE plan depuis ses données du storyboard (axe caméra
        + personnages assignés) et remet le plan de décor en Auto. FORCE le re-semis
        (contourne le flag _actors_seeded posé par « Tout supprimer ») → c'est ainsi
        qu'on RÉCUPÈRE la mise en scène après l'avoir supprimée. Remplace les
        placements manuels actuels, d'où la confirmation."""
        if not self._shots:
            QMessageBox.information(self, translate("Synchronisation"),
                                   translate("Aucun plan dans le storyboard."))
            return
        box = QMessageBox(self)
        box.setIcon(QMessageBox.Icon.Warning)
        box.setWindowTitle(translate("Synchronisation"))
        box.setText(translate(
            "Reconstruire la mise en scène de tous les plans depuis le storyboard ?\n"
            "Les placements actuels (acteurs, caméra) seront remplacés."))
        box.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        box.setDefaultButton(QMessageBox.StandardButton.No)
        if box.exec() != QMessageBox.StandardButton.Yes:
            return
        n = 0
        for s in self._shots:
            sid = s.get("id")
            if not sid:
                continue
            rec = staging.get(sid)
            seeded = staging.seed_record_for_shot(s)
            rec["actors"] = seeded["actors"]
            rec["camera"] = seeded["camera"]
            rec["_actors_seeded"] = True
            rec["plan_decor_id"] = ""   # repasse en Auto → le plan de décor revient
            fp = decors_api.floor_plan_for_shot(s)
            rec["plan_image"] = fp if (fp and os.path.isfile(fp)) else ""
            staging.save(sid, rec)
            n += 1
        self._reload_current()
        QMessageBox.information(
            self, translate("Synchronisation"),
            translate("Mise en scène reconstruite depuis le storyboard.") + f"  ({n})")

    def _sync_to_storyboard(self):
        """mise en scène / plan de feu → storyboard : place les comédiens dans la
        section [MISE EN SCÈNE] du prompt et la caméra dans les champs techniques
        (camera_axis / camera_placement) ; le plan de feu alimente [PLAN DE FEU]."""
        from core.prompt_sections import parse as _parse, build as _build
        n = 0
        for s in self._shots:
            sid = s.get("id")
            if not sid:
                continue
            rec = staging.get(sid)
            cur = s.get("seedance_prompt", "") or ""
            sec = _parse(cur)
            action = sec.get("action") or cur
            changed = False
            if self._mode == "staging":
                actors_txt = staging.staging_actors_summary(sid)
                new = _build(action=action, staging=actors_txt or sec.get("staging", ""),
                             ambiance=sec.get("ambiance", ""), decor=sec.get("decor", ""),
                             lighting=sec.get("lighting", ""), technique=sec.get("technique", ""),
                             sound=sec.get("sound", ""))
                if new and new != cur:
                    s["seedance_prompt"] = new
                    changed = True
                # Caméra → champs TECHNIQUES du plan (pas dans le texte de mise en scène).
                # Axe déduit de la POSITION caméra/acteurs → déplacer la caméra met à
                # jour l'axe dans le storyboard.
                cam = rec.get("camera") or {}
                axis = staging.axis_from_placement(rec) if cam else ""
                zone = staging.camera_placement(sid)
                if axis and s.get("camera_axis") != axis:
                    s["camera_axis"] = axis
                    changed = True
                if zone and s.get("camera_placement") != zone:
                    s["camera_placement"] = zone
                    changed = True
            else:
                light_txt = staging.lighting_summary(sid)
                new = _build(action=action, staging=sec.get("staging", ""),
                             ambiance=sec.get("ambiance", ""), decor=sec.get("decor", ""),
                             lighting=light_txt or sec.get("lighting", ""),
                             technique=sec.get("technique", ""), sound=sec.get("sound", ""))
                if new and new != cur:
                    s["seedance_prompt"] = new
                    changed = True
            if changed:
                try:
                    sb_api.save_shot({k: v for k, v in s.items() if not k.startswith("_")})
                    n += 1
                except Exception:
                    pass
        msg = (translate("Mise en scène synchronisée vers le storyboard.")
               if self._mode == "staging"
               else translate("Plan de feu synchronisé vers le storyboard."))
        QMessageBox.information(self, translate("Synchronisation"), msg + f"  ({n})")

    # ── Sauvegarder / Ouvrir (dossier dédié, boîte de dialogue Windows) ─────────

    def _on_save_staging(self):
        sub = "Mise en scène" if self._mode == "staging" else "Plan de feu"
        start = os.path.join(staging.staging_saves_dir(self._mode), sub + ".json")
        path, _ = QFileDialog.getSaveFileName(
            self, translate("Sauvegarder"), start, "PANDORA (*.json)")
        if not path:
            return
        if not path.lower().endswith(".json"):
            path += ".json"
        try:
            staging.export_staging_to(path)
            QMessageBox.information(self, translate("Sauvegarder"), translate("Enregistré ✓"))
        except Exception as e:
            QMessageBox.critical(self, "Erreur", f"Échec de la sauvegarde : {e}")

    def _on_open_staging(self):
        path, _ = QFileDialog.getOpenFileName(
            self, translate("Ouvrir"), staging.staging_saves_dir(self._mode),
            "PANDORA (*.json)")
        if not path:
            return
        try:
            n = staging.import_staging_from(path)
            self._reload_current()
            QMessageBox.information(self, translate("Ouvrir"), f"{n} plan(s) chargé(s).")
        except Exception as e:
            QMessageBox.critical(self, "Erreur", f"Échec de l'ouverture : {e}")

    def _autosave(self):
        if not self._shot:
            return
        rec = self._canvas.commit()
        staging.save(self._shot["id"], rec)
        # Met à jour les sections du prompt du plan courant après une courte pause
        # (débounce) → instantané du point de vue de l'utilisateur, sans thrash disque.
        self._sync_timer.start()
        # … puis Claude analyse le plan (débounce plus long) pour préciser le
        # placement par rapport au mobilier visible (« assise à la table »).
        self._vision_timer.start()

    # ── Analyse VISION du plan par Claude (placement précis vs mobilier visible) ──

    def _run_vision(self):
        """Lance Claude Vision sur le plan du décor (mobilier visible) + les positions
        des jetons → description précise. Skippé sans clé Anthropic / sans plan /
        si une analyse tourne déjà. Le placement déterministe reste affiché entre-temps."""
        if not self._shot:
            return
        if self._vision_worker is not None and self._vision_worker.isRunning():
            return
        try:
            from core.config import load_config
            if not load_config().get("anthropic_key", "").strip():
                return
        except Exception:
            return
        rec = staging.get(self._shot["id"])
        plan = rec.get("plan_image", "")
        if not (plan and os.path.isfile(plan)):
            return   # pas de plan (Kontext) → on garde le placement déterministe
        tokens = []
        cam = rec.get("camera") or {}
        if cam:
            tokens.append({"kind": "camera", "label": "caméra",
                           "x": cam.get("x", .5), "y": cam.get("y", .5),
                           "info": "axe " + staging.axis_from_placement(rec)})
        for a in (rec.get("actors") or []):
            tokens.append({"kind": "actor", "label": a.get("name", "?"),
                           "x": a.get("x", .5), "y": a.get("y", .5)})
        for l in (rec.get("lights") or []):
            if (l.get("settings") or {}).get("on", True):
                tokens.append({"kind": "light",
                               "label": l.get("name", "") or l.get("type", ""),
                               "x": l.get("x", .5), "y": l.get("y", .5),
                               "info": (l.get("model", "") or l.get("type", ""))})
        if not tokens:
            return
        decor_desc = self._shot.get("decor_name", "") or ""
        from api.staging_vision import StagingVisionWorker
        self._vision_shot_id = self._shot["id"]
        self._vision_worker = StagingVisionWorker(plan, tokens, self._mode, decor_desc)
        self._vision_worker.finished.connect(self._on_vision_done)
        self._vision_worker.failed.connect(lambda _e: None)
        self._vision_worker.start()

    def _on_vision_done(self, txt: str):
        # Le plan a pu changer pendant l'analyse → n'écrire que si c'est le même.
        if (txt and self._shot
                and self._shot.get("id") == getattr(self, "_vision_shot_id", None)):
            self._apply_vision_text(txt)

    def _apply_vision_text(self, txt: str):
        """Écrit la description précise de Claude dans la bonne section du prompt :
        staging → REMPLACE [MISE EN SCÈNE] (le placement déterministe était vague) ;
        feu → AJOUTE l'origine/ambiance de la lumière au [PLAN DE FEU] déterministe
        (on garde la direction relative caméra + les distances chiffrées)."""
        from core.prompt_sections import parse as _parse, build as _build
        s = self._shot
        sec = _parse(s.get("seedance_prompt", "") or "")
        if self._mode == "staging":
            staging_txt = txt
            lighting_txt = sec.get("lighting", "")
        else:
            staging_txt = sec.get("staging", "")
            base = sec.get("lighting", "")
            lighting_txt = (base + "  " + txt).strip() if base else txt
        new = _build(action=sec.get("action", ""), staging=staging_txt,
                     ambiance=sec.get("ambiance", ""), decor=sec.get("decor", ""),
                     lighting=lighting_txt, technique=sec.get("technique", ""),
                     sound=sec.get("sound", ""))
        if new and new != (s.get("seedance_prompt", "") or ""):
            s["seedance_prompt"] = new
            try:
                sb_api.save_shot({k: v for k, v in s.items() if not k.startswith("_")})
            except Exception:
                pass

    def _apply_current_to_storyboard(self):
        """Réécrit INSTANTANÉMENT la(les) section(s) du prompt du plan COURANT."""
        if self._shot:
            self._write_sections(self._shot, staging.get(self._shot["id"]))

    def _write_sections(self, shot: dict, rec: dict):
        """Réécrit la(les) section(s) concernée(s) du prompt d'UN plan depuis son
        record de mise en scène, et sauvegarde le plan dans le storyboard :
          · Mise en scène → [🎭 MISE EN SCÈNE] + axe / placement / distance caméra ;
          · Plan de feu    → [💡 PLAN DE FEU].
        ⚠ Le PLAN DE FEU dépend de l'AXE CAMÉRA (direction relative de la lumière) :
        il est donc recalculé AUSSI quand on déplace la caméra en Mise en scène.
        Les autres sections (Action, Ambiance, Décor, Technique, Sound) sont préservées."""
        from core.prompt_sections import parse as _parse, build as _build
        sid = shot["id"]
        cur = shot.get("seedance_prompt", "") or ""
        sec = _parse(cur)
        changed = False
        # Plan de feu RELATIF À LA CAMÉRA → recalculé dans les 2 modes s'il y a des
        # lumières (sinon on préserve l'intention de lumière éventuelle du découpage).
        if rec.get("lights"):
            light_txt = staging.lighting_summary(sid)
            if light_txt != sec.get("lighting", ""):
                sec["lighting"] = light_txt
                changed = True
        elif self._mode == "lighting" and sec.get("lighting"):
            sec["lighting"] = ""   # plus aucune lumière en mode plan de feu → vider
            changed = True
        if self._mode == "staging":
            staging_txt = staging.staging_actors_summary(sid)
            if staging_txt != sec.get("staging", ""):
                sec["staging"] = staging_txt
                changed = True
            # Caméra → champs TECHNIQUES du plan (axe + placement) ET distance RÉELLE
            # (colonne DIST. du storyboard) dérivée de la position sur l'échelle du décor.
            cam = rec.get("camera") or {}
            axis = staging.axis_from_placement(rec) if cam else ""
            zone = staging.camera_placement(sid)
            if axis and shot.get("camera_axis") != axis:
                shot["camera_axis"] = axis
                changed = True
            if zone and shot.get("camera_placement") != zone:
                shot["camera_placement"] = zone
                changed = True
            dist_m = staging.camera_distance_m(rec)
            if dist_m > 0:
                dist_str = f"{dist_m:g}m"
                if shot.get("camera_distance") != dist_str:
                    shot["camera_distance"] = dist_str
                    changed = True
            # Hauteur caméra (clic droit caméra → Hauteur) → champ du plan, à côté
            # de la distance (colonne/dialog storyboard).
            h_cam = cam.get("height")
            if h_cam:
                h_str = f"{float(h_cam):g} m"
                if shot.get("camera_height") != h_str:
                    shot["camera_height"] = h_str
                    changed = True
        if not changed:
            return
        shot["seedance_prompt"] = _build(
            action=sec.get("action") or cur, staging=sec.get("staging", ""),
            ambiance=sec.get("ambiance", ""), decor=sec.get("decor", ""),
            lighting=sec.get("lighting", ""), technique=sec.get("technique", ""),
            sound=sec.get("sound", "") or (shot.get("sound_prompt") or ""))
        try:
            sb_api.save_shot({k: v for k, v in shot.items() if not k.startswith("_")})
        except Exception:
            pass

    # ── Clic droit sur la liste : copier d'un autre plan (scènes similaires) ─────

    def _on_list_context(self, pos):
        item = self._list.itemAt(pos)
        if item is None:
            return
        row = self._list.row(item)
        if row < 0 or row >= len(self._shots):
            return
        target = self._shots[row]
        others = [(i, s) for i, s in enumerate(self._shots) if i != row]
        menu = QMenu(self)
        head = menu.addAction(
            translate("Copier le plan de feu d'un autre plan") if self._mode == "lighting"
            else translate("Copier la mise en scène d'un autre plan"))
        head.setEnabled(False)
        menu.addSeparator()
        if not others:
            menu.addAction(translate("(aucun autre plan)")).setEnabled(False)
        for i, s in others:
            nm = f"{translate('Plan')} {s.get('number', i + 1)}"
            t = (s.get("scene_title") or s.get("seq_name") or "").strip()
            if t:
                nm += f" — {t}"
            menu.addAction(nm, lambda _=False, src=s, tgt=target: self._copy_staging_from(src, tgt))

        # Sous-menu : changer le plan du décor utilisé pour CE plan.
        menu.addSeparator()
        plan_menu = menu.addMenu(translate("Changer le plan du décor"))
        _cur = staging.get(target["id"]).get("plan_decor_id", "")
        for _did, _label in [("", translate("Auto (décor du plan)")),
                             ("__none__", translate("Aucun plan (vide)"))]:
            _a = plan_menu.addAction(("● " if _cur == _did else "   ") + _label)
            _a.triggered.connect(lambda _=False, d=_did, tgt=target: self._set_plan_decor_for(tgt, d))
        plan_menu.addSeparator()
        try:
            for d in decors_api.list_decors():
                _did = d.get("id", "")
                _nm = d.get("name") or translate("(décor sans nom)")
                if d.get("floor_plan"):
                    _nm = "◆ " + _nm
                _a = plan_menu.addAction(("● " if _cur == _did else "   ") + _nm)
                _a.triggered.connect(lambda _=False, dd=_did, tgt=target: self._set_plan_decor_for(tgt, dd))
        except Exception:
            pass
        menu.exec(self._list.mapToGlobal(pos))

    def _set_plan_decor_for(self, tgt_shot: dict, decor_id: str):
        """Change le plan de décor d'UN plan (clic droit) et recharge si courant."""
        rec = staging.get(tgt_shot["id"])
        rec["plan_decor_id"] = decor_id or ""
        fp = self._resolve_floor_plan(tgt_shot, rec)
        rec["plan_image"] = fp if (fp and os.path.isfile(fp)) else ""
        staging.save(tgt_shot["id"], rec)
        if self._shot and self._shot.get("id") == tgt_shot.get("id"):
            self._reload_current()

    def _do_copy(self, src_shot: dict, tgt_shot: dict) -> str:
        """Copie (sans UI) la mise en scène (mode staging : caméra + acteurs +
        accessoires) ou le plan de feu (mode lighting : projecteurs) d'un plan SOURCE
        vers un plan CIBLE. Réécrit le prompt du plan cible ; recharge si courant.
        Renvoie le libellé du résultat."""
        import copy as _copy
        src = staging.get(src_shot["id"])
        tgt = staging.get(tgt_shot["id"])
        if self._mode == "staging":
            tgt["camera"] = _copy.deepcopy(src.get("camera") or tgt.get("camera") or {})
            tgt["actors"] = _copy.deepcopy(src.get("actors") or [])
            tgt["props"]  = _copy.deepcopy(src.get("props") or [])
            tgt["_actors_seeded"] = True   # ne pas re-semer depuis character_names
            what = translate("Mise en scène copiée")
        else:
            tgt["lights"] = _copy.deepcopy(src.get("lights") or [])
            what = translate("Plan de feu copié")
        staging.save(tgt_shot["id"], tgt)
        self._write_sections(tgt_shot, tgt)
        if self._shot and self._shot.get("id") == tgt_shot.get("id"):
            self._reload_current()
        return what

    def _copy_staging_from(self, src_shot: dict, tgt_shot: dict):
        what = self._do_copy(src_shot, tgt_shot)
        src_lbl = f"{translate('Plan')} {src_shot.get('number', '?')}"
        QMessageBox.information(self, translate("Copier"), f"{what} ({src_lbl}).")


class PageLighting(PageStaging):
    """Plan de feu — même canevas, mode lumières, record partagé avec la Mise en
    scène (réutilise le plan vu de dessus généré)."""
    MODE = "lighting"
