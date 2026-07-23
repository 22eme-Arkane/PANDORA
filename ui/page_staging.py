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
    QLineEdit, QFrame,
)
from PyQt6.QtCore import Qt, QTimer, QSize
from PyQt6.QtGui import QShortcut, QKeySequence
from ui.styles import CP
from ui.widgets import HelpBlock
from ui.staging_canvas import StagingCanvas
from ui.lighting_workspace import (
    LightingInspector, LightingInspectorToggle, LightingShotCard,
    LightingToolbar, sequence_label,
)
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
    # La reconstruction d'une page peut créer de nombreuses cartes et charger un
    # plan. PandoraWindow la planifie après le premier rendu pour ne pas bloquer
    # la pompe d'événements Windows pendant un changement d'onglet.
    DEFER_NAV_REFRESH = True

    def __init__(self):
        super().__init__()
        self._mode = self.MODE
        self._shots: list[dict] = []
        self._shot: dict | None = None
        self.setStyleSheet(f"background:{CP['bg0']};")

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # Bandeau titre (« Mise en scène » / « Plan de feu ») retiré — demande
        # Matthieu 2026-07-22 : la fenêtre gagne la hauteur du bandeau.

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
        # Le rafraîchissement est géré et regroupé par PandoraWindow._navigate.
        # L'ancien appel direct provoquait un second refresh synchrone lors de la
        # navigation, puis parfois un troisième à l'ActivationChange.

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
        if self._mode == "staging" or getattr(self, "_combined_plateau", False):
            if not rec.get("_actors_seeded"):
                seeded = staging.seed_record_for_shot(self._shot)
                if not rec.get("actors"):
                    rec["actors"] = seeded["actors"]
                rec["camera"] = seeded["camera"]   # caméra placée selon camera_axis
            rec["_actors_seeded"] = True
            staging.apply_camera_optics(rec, self._shot)
            for actor in rec.get("actors", []):
                if not actor.get("gender"):
                    actor["gender"] = self._actor_gender(actor.get("name", ""))
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
                menu.addAction(n, lambda _=False, nm=n: self._canvas.add_actor(
                    nm, gender=self._actor_gender(nm)))
            menu.addSeparator()
            menu.addAction(translate("Autre…"), self._add_actor_free)
            menu.exec(self.cursor().pos())
        else:
            self._add_actor_free()

    def _add_actor_free(self):
        name, ok = QInputDialog.getText(self, translate("Acteur"), translate("Nom :"))
        if ok and name.strip():
            self._canvas.add_actor(name.strip())

    @staticmethod
    def _actor_gender(name: str) -> str:
        """Genre visuel du pion, déduit de la fiche casting sans modifier celle-ci."""
        try:
            import core.casting as casting
            char = next((c for c in casting.list_characters()
                         if str(c.get("name", "")).casefold() == str(name).casefold()), {})
        except Exception:
            char = {}
        explicit = str(char.get("gender") or char.get("sex") or char.get("sexe") or "").casefold()
        if explicit:
            return "female" if explicit.startswith("f") else "male" if explicit.startswith("h") or explicit.startswith("m") else ""
        haystack = " ".join((str(name), str(char.get("description") or ""))).casefold()
        female_terms = ("femme", "mère", "fille", "actrice", "elle ", " la ")
        male_terms = ("homme", "père", "fils", "acteur", " il ", " le ")
        if any(term in haystack for term in female_terms):
            return "female"
        if any(term in haystack for term in male_terms):
            return "male"
        return ""

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
        if self._mode == "staging" or getattr(self, "_combined_plateau", False):
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
                sub.addAction(n, lambda _=False, nm=n: self._canvas.add_actor(
                    nm, x, y, self._actor_gender(nm)))
            if chars:
                sub.addSeparator()
            sub.addAction(translate("Autre…"), lambda: self._add_actor_free_at(x, y))
            menu.addAction(translate("Placer la caméra ici"),
                           lambda: self._canvas.place_camera(x, y))
        if self._mode != "staging":
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
        model["gender"] = self._actor_gender(name)
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
        import core.projectors as proj
        from ui.dialog_projector import ProjectorDialog
        dlg = ProjectorDialog(self, role=model.get("type", "key"),
                              family=model.get("family", ""), model=model.get("model", ""))
        if dlg.exec() == ProjectorDialog.DialogCode.Accepted:
            r = dlg.result_data()
            if r:
                old_settings = model.get("settings") or {}
                family = r.get("family", "")
                projector_model = r.get("model", "")
                settings = proj.default_settings(family, projector_model)
                # Les réglages physiques de placement restent valables après un
                # changement de tête ; les commandes propres à l'ancien modèle
                # (faisceau, pixels, effet…) repartent sur des valeurs sûres.
                for key in ("on", "intensity", "height", "tilt"):
                    if key in old_settings:
                        settings[key] = old_settings[key]
                model.update({"name": r["name"], "type": r["role"],
                              "family": family, "model": projector_model,
                              "settings": settings})
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
        if self._mode == "staging" or getattr(self, "_combined_plateau", False):
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
        from core.prompt_sections import parse as _parse, rebuild as _rebuild
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
                # Vision fraîche (ancrée au mobilier) prioritaire sur le déterministe —
                # ce menu réécrivait TOUTES les sections vision du projet en résumés vagues.
                _sv = rec.get("vision_staging", "")
                if _sv and rec.get("vision_staging_sig") == staging.positions_sig(rec, "staging"):
                    actors_txt = _sv
                else:
                    actors_txt = staging.staging_actors_summary(sid)
                # rebuild() : ne touche que staging (+ action si le prompt était à
                # plat) et PRÉSERVE [🎨 STYLE VISUEL] et les autres sections.
                new = _rebuild(cur, action=action,
                               staging=actors_txt or sec.get("staging", ""))
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
                _lv = rec.get("vision_lighting", "")
                if light_txt and _lv and rec.get("vision_lighting_sig") == staging.positions_sig(rec, "lighting"):
                    light_txt = f"{light_txt}  {_lv}".strip()
                new = _rebuild(cur, action=action,
                               lighting=light_txt or sec.get("lighting", ""))
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
            # Une analyse tourne déjà : se RÉARMER au lieu d'abandonner — sinon les
            # dernières positions ne seraient jamais analysées et une vision périmée
            # resterait la seule disponible.
            self._vision_timer.start()
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
        # Signature des positions AU LANCEMENT — le résultat ne sera appliqué que
        # si les positions n'ont pas bougé entre-temps (sinon vision périmée).
        self._vision_sig = staging.positions_sig(rec, self._mode)
        self._vision_worker = StagingVisionWorker(plan, tokens, self._mode, decor_desc)
        self._vision_worker.finished.connect(self._on_vision_done)
        self._vision_worker.failed.connect(lambda _e: None)
        self._vision_worker.start()

    def _on_vision_done(self, txt: str):
        # Le plan OU les positions ont pu changer pendant l'analyse → n'écrire que
        # si c'est le même plan ET les mêmes positions (jamais de vision périmée).
        if not (txt and self._shot
                and self._shot.get("id") == getattr(self, "_vision_shot_id", None)):
            return
        rec = staging.get(self._shot["id"])
        sig = staging.positions_sig(rec, self._mode)
        if sig != getattr(self, "_vision_sig", None):
            return   # les jetons ont bougé depuis le lancement → résultat obsolète
        # PERSISTER la description vision dans le record : c'est elle qui PRIME sur
        # le résumé déterministe tant que les positions n'ont pas changé
        # (cf. _write_sections / _sync_to_storyboard) — avant ce correctif elle
        # était écrasée au premier déplacement de jeton et perdue à jamais.
        if self._mode == "staging":
            rec["vision_staging"], rec["vision_staging_sig"] = txt, sig
        else:
            rec["vision_lighting"], rec["vision_lighting_sig"] = txt, sig
        staging.save(self._shot["id"], rec)
        self._apply_vision_text(txt)

    def _apply_vision_text(self, txt: str):
        """Écrit la description précise de Claude dans la bonne section du prompt :
        staging → REMPLACE [MISE EN SCÈNE] (le placement déterministe était vague) ;
        feu → AJOUTE l'origine/ambiance de la lumière au [PLAN DE FEU] déterministe
        (on garde la direction relative caméra + les distances chiffrées)."""
        from core.prompt_sections import parse as _parse, rebuild as _rebuild
        s = self._shot
        cur = s.get("seedance_prompt", "") or ""
        sec = _parse(cur)
        if self._mode == "staging":
            staging_txt = txt
            lighting_txt = sec.get("lighting", "")
        else:
            staging_txt = sec.get("staging", "")
            base = sec.get("lighting", "")
            lighting_txt = (base + "  " + txt).strip() if base else txt
        # rebuild() préserve [🎨 STYLE VISUEL] et les sections non touchées.
        new = _rebuild(cur, staging=staging_txt, lighting=lighting_txt)
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
        sec = _parse(cur)   # contient déjà [🎨 STYLE VISUEL] s'il est présent
        changed = False
        # Plan de feu RELATIF À LA CAMÉRA → recalculé dans les 2 modes s'il y a des
        # lumières (sinon on préserve l'intention de lumière éventuelle du découpage).
        if rec.get("lights"):
            light_txt = staging.lighting_summary(sid)
            # Description VISION du plan de feu (origine de la lumière vs mobilier)
            # encore valable → AJOUTÉE au résumé déterministe (directions + distances).
            _lv = rec.get("vision_lighting", "")
            if _lv and rec.get("vision_lighting_sig") == staging.positions_sig(rec, "lighting"):
                light_txt = f"{light_txt}  {_lv}".strip()
            if light_txt != sec.get("lighting", ""):
                sec["lighting"] = light_txt
                changed = True
        elif self._mode == "lighting" and sec.get("lighting"):
            sec["lighting"] = ""   # plus aucune lumière en mode plan de feu → vider
            changed = True
        if self._mode == "staging" or getattr(self, "_combined_plateau", False):
            # La description VISION (ancrée au mobilier réellement visible : « assise
            # à la table, côté gauche ») PRIME sur le résumé déterministe tant que
            # les positions n'ont pas changé — elle n'est plus jamais écrasée par lui.
            _sv = rec.get("vision_staging", "")
            if _sv and rec.get("vision_staging_sig") == staging.positions_sig(rec, "staging"):
                staging_txt = _sv
            else:
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
        # sec (issu de parse) porte TOUTES les sections, dont [🎨 STYLE VISUEL] :
        # build(**sec) après avoir fixé action/sound les préserve toutes.
        sec["action"] = sec.get("action") or cur
        sec["sound"]  = sec.get("sound", "") or (shot.get("sound_prompt") or "")
        shot["seedance_prompt"] = _build(**sec)
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

        # Échelle RÉELLE du plan (largeur du décor en mètres) : fiabilise les
        # distances chiffrées écrites dans les prompts — tant qu'elle n'est pas
        # renseignée, elles sont précédées de « environ » (10 m supposés).
        menu.addSeparator()
        _span = staging.get(target["id"]).get("plan_span_m") or 0
        _span_lbl = translate("Échelle du plan (largeur en mètres)…")
        if _span:
            _span_lbl += f"  [{_span:g} m]"
        menu.addAction(_span_lbl, lambda _=False, tgt=target: self._set_plan_span_for(tgt))
        menu.exec(self._list.mapToGlobal(pos))

    def _set_plan_span_for(self, tgt_shot: dict):
        """Échelle RÉELLE du plan d'UN plan : largeur du décor en mètres
        (rec["plan_span_m"]). Toutes les distances (plan de feu, colonne DIST.)
        en découlent ; une fois renseignée, le « environ » disparaît des prompts."""
        rec = staging.get(tgt_shot["id"])
        try:
            cur = float(rec.get("plan_span_m") or staging.DEFAULT_PLAN_SPAN_M)
        except (TypeError, ValueError):
            cur = staging.DEFAULT_PLAN_SPAN_M
        val, ok = QInputDialog.getDouble(
            self, translate("Échelle du plan"),
            translate("Largeur réelle du décor sur le plan (mètres) :"),
            cur, 1.0, 500.0, 1)
        if not ok:
            return
        rec["plan_span_m"] = round(val, 1)
        staging.save(tgt_shot["id"], rec)
        self._write_sections(tgt_shot, rec)   # distances des prompts recalculées
        if self._shot and self._shot.get("id") == tgt_shot.get("id"):
            self._reload_current()

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
    """Plan de feu — poste de travail dédié relié au moteur de mise en scène."""
    MODE = "lighting"

    def __init__(self):
        QWidget.__init__(self)
        self._mode = self.MODE
        self._combined_plateau = True
        self._shots: list[dict] = []
        self._all_shots: list[dict] = []
        self._shot: dict | None = None
        self.setStyleSheet(f"background:{CP['bg0']};")

        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        left = QFrame()
        left.setObjectName("LightingShotsPanel")
        left.setFixedWidth(292)
        left.setStyleSheet(
            "QFrame#LightingShotsPanel{"
            "background:qlineargradient(x1:0,y1:0,x2:1,y2:0,"
            "stop:0 #0a1a29,stop:1 #0c2130);"
            "border-right:1px solid rgba(78,205,196,0.38);}"
        )
        ll = QVBoxLayout(left)
        ll.setContentsMargins(10, 12, 10, 10)
        ll.setSpacing(8)
        section = QLabel(translate("PLANS DU STORYBOARD"))
        section.setStyleSheet(
            f"color:{CP['text_dim']};font-size:9px;font-weight:800;letter-spacing:1px;"
            "background:transparent;border:none;"
        )
        ll.addWidget(section)
        self._sequence_combo = QComboBox()
        self._sequence_combo.setMinimumHeight(36)
        self._sequence_combo.setStyleSheet(self._combo_style())
        self._sequence_combo.currentIndexChanged.connect(self._apply_shot_filter)
        ll.addWidget(self._sequence_combo)
        # Menu du plan de décor REMONTÉ ici, à la place de la recherche
        # (demande Matthieu 2026-07-23).
        self._plan_combo = QComboBox()
        self._plan_combo.setToolTip(translate("Plan du décor"))
        self._plan_combo.setMinimumHeight(36)
        self._plan_combo.setStyleSheet(self._combo_style())
        self._plan_combo.currentIndexChanged.connect(self._on_plan_decor_changed)
        ll.addWidget(self._plan_combo)
        # Recherche RETIRÉE de l'affichage (2026-07-23) — le widget reste vivant
        # car le filtre de la liste lit son texte.
        self._search = QLineEdit(left)
        self._search.setPlaceholderText(translate("Rechercher un plan…"))
        self._search.textChanged.connect(self._apply_shot_filter)
        self._search.hide()
        self._list = QListWidget()
        self._list.setSpacing(5)
        # Barre de défilement VERTICALE à GAUCHE (liste en RTL, les cartes
        # repassent en LTR dans _rebuild_shot_list) ; barre HORIZONTALE coupée —
        # c'était le « rectangle noir » qui apparaissait en bas de la liste.
        self._list.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
        self._list.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._list.setStyleSheet(
            "QListWidget{background:transparent;border:none;outline:none;padding:0;}"
            f"QListWidget::item{{background:{CP['bg2']};border:1px solid {CP['border']};"
            "border-radius:8px;}"
            "QListWidget::item:hover{background:rgba(255,255,255,0.04);"
            f"border-color:{CP['border_bright']};}}"
            "QListWidget::item:selected{background:rgba(78,205,196,0.10);"
            f"border:1px solid {CP['accent']};}}"
        )
        self._list.currentRowChanged.connect(self._on_shot_changed)
        self._list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._list.customContextMenuRequested.connect(self._on_list_context)
        ll.addWidget(self._list, 1)

        # Bouton « Action » (2026-07-23) : ouvre le menu de synchronisation.
        # Libellé écrit et style contour BLEU, comme « Soutenir Pandora »/« Ouvrir ».
        _blue = "#4aa3ff"
        self._btn_sync = QPushButton("☰  " + translate("Action"))
        self._btn_sync.setFixedHeight(34)
        self._btn_sync.setToolTip(translate("Synchronisation"))
        self._btn_sync.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_sync.setStyleSheet(
            f"QPushButton{{background:transparent;color:{_blue};"
            f"border:1px solid {_blue};border-radius:7px;"
            f"font-size:11px;font-weight:700;padding:0 14px;}}"
            f"QPushButton:hover{{background:rgba(74,163,255,0.12);}}"
            f"QPushButton:pressed{{background:rgba(74,163,255,0.22);}}"
        )
        self._btn_sync.clicked.connect(self._open_sync_menu)
        ll.addWidget(self._btn_sync)
        self._shot_count = QLabel()
        self._shot_count.setStyleSheet(
            f"color:{CP['text_dim']};font-size:9px;background:transparent;border:none;"
        )
        ll.addWidget(self._shot_count)
        root.addWidget(left)

        center = QWidget()
        center.setStyleSheet(f"background:{CP['bg0']};")
        cl = QHBoxLayout(center)
        cl.setContentsMargins(9, 9, 9, 9)
        cl.setSpacing(8)
        self._tools = LightingToolbar()
        self._btn_clear_all = self._tools.clear_button
        cl.addWidget(self._tools, 0, Qt.AlignmentFlag.AlignTop)
        self._canvas = StagingCanvas(mode="combined")
        cl.addWidget(self._canvas, 1)
        root.addWidget(center, 1)

        self._inspector = LightingInspector()
        root.addWidget(self._inspector)
        self._inspector_toggle = LightingInspectorToggle(opened=True)
        self._inspector_toggle.toggled.connect(self._set_inspector_visible)
        root.addWidget(self._inspector_toggle)

        self._sync_timer = QTimer(self)
        self._sync_timer.setSingleShot(True)
        self._sync_timer.setInterval(250)
        self._sync_timer.timeout.connect(self._apply_current_to_storyboard)
        self._vision_timer = QTimer(self)
        self._vision_timer.setSingleShot(True)
        self._vision_timer.setInterval(1500)
        self._vision_timer.timeout.connect(self._run_vision)
        self._vision_worker = None
        self._vision_shot_id = None
        self._inspector_light_signature = ()

        self._canvas.changed.connect(self._autosave)
        self._canvas.changed.connect(self._sync_inspector_structure)
        self._canvas.actor_context.connect(self._on_actor_context)
        self._canvas.light_context.connect(self._on_light_context)
        self._canvas.camera_context.connect(self._on_camera_context)
        self._canvas.empty_context.connect(self._on_empty_context)
        self._tools.tool_changed.connect(self._canvas.set_tool)
        self._tools.add_light_requested.connect(self._add_light)
        self._tools.add_actor_requested.connect(self._add_actor)
        self._tools.place_camera_requested.connect(lambda: self._canvas.place_camera(0.5, 0.85))
        self._tools.fit_requested.connect(self._canvas.fit_scene)
        self._tools.zoom_requested.connect(self._canvas.zoom_by)
        self._tools.grid_requested.connect(self._canvas.set_grid_visible)
        self._tools.clear_requested.connect(self._on_clear_all)
        self._inspector.changed.connect(self._on_inspector_changed)
        self._inspector.advanced_requested.connect(self._open_advanced_settings)
        self._inspector.delete_requested.connect(self._delete_light_from_inspector)

        self._sc_del = QShortcut(QKeySequence(QKeySequence.StandardKey.Delete), self)
        self._sc_del.activated.connect(self._canvas.remove_selected)
        self._sc_bs = QShortcut(QKeySequence(Qt.Key.Key_Backspace), self)
        self._sc_bs.activated.connect(self._canvas.remove_selected)

    @staticmethod
    def _combo_style() -> str:
        return (
            f"QComboBox{{background:{CP['bg2']};color:{CP['text_primary']};"
            f"border:1px solid {CP['border']};border-radius:7px;padding:6px 9px;"
            "font-size:9px;}"
            f"QComboBox:hover{{border-color:{CP['accent_dim']};}}"
        )

    @staticmethod
    def _compact_button_style() -> str:
        return (
            f"QPushButton{{background:{CP['bg2']};color:{CP['accent']};"
            f"border:1px solid {CP['border']};border-radius:7px;font-size:15px;}}"
            f"QPushButton:hover{{border-color:{CP['accent_dim']};"
            "background:rgba(78,205,196,0.10);}}"
        )

    def refresh(self):
        current_id = self._shot.get("id") if self._shot else ""
        try:
            versions = sb_api.list_versions()
            vid = versions[0]["id"] if versions else sb_api.DEFAULT_VERSION_ID
            self._all_shots = sb_api.list_shots(vid)
        except Exception:
            self._all_shots = []
        previous = self._sequence_combo.currentData()
        sequence_values = []
        for shot in self._all_shots:
            value = sequence_label(shot)
            if value not in sequence_values:
                sequence_values.append(value)
        self._sequence_combo.blockSignals(True)
        self._sequence_combo.clear()
        self._sequence_combo.addItem(translate("Toutes les séquences"), "")
        for value in sequence_values:
            self._sequence_combo.addItem(value, value)
        idx = self._sequence_combo.findData(previous)
        self._sequence_combo.setCurrentIndex(max(0, idx))
        self._sequence_combo.blockSignals(False)
        self._rebuild_shot_list(current_id)

    def _apply_shot_filter(self, *_args):
        current_id = self._shot.get("id") if self._shot else ""
        self._rebuild_shot_list(current_id)

    def _rebuild_shot_list(self, current_id=""):
        seq = self._sequence_combo.currentData() or ""
        query = self._search.text().strip().casefold()
        self._shots = []
        for shot in self._all_shots:
            haystack = " ".join((sequence_label(shot), str(shot.get("number", "")),
                                 shot.get("scene_title", ""), shot.get("name", ""))).casefold()
            if seq and sequence_label(shot) != seq:
                continue
            if query and query not in haystack:
                continue
            self._shots.append(shot)
        self._list.blockSignals(True)
        self._list.clear()
        for shot in self._shots:
            item = QListWidgetItem()
            item.setSizeHint(QSize(258, 66))
            self._list.addItem(item)
            card = LightingShotCard(shot)
            # La liste est en RTL (barre de défilement à gauche) : chaque carte
            # repasse en LTR pour garder sa mise en page normale.
            card.setLayoutDirection(Qt.LayoutDirection.LeftToRight)
            self._list.setItemWidget(item, card)
        self._list.blockSignals(False)
        self._shot_count.setText(f"{len(self._shots)} {translate('plan(s)')}")
        if self._shots:
            row = next((i for i, s in enumerate(self._shots) if s.get("id") == current_id), 0)
            self._list.setCurrentRow(row)
        else:
            self._shot = None
            self._canvas.load({
                "plan_image": "", "camera": {"x": 0.5, "y": 0.85, "angle": 0.0},
                "actors": [], "props": [], "lights": [],
            })
            self._inspector.set_lights([])

    def _on_shot_changed(self, row: int):
        super()._on_shot_changed(row)
        self._refresh_inspector()

    def _refresh_inspector(self):
        if not self._shot:
            self._inspector_light_signature = ()
            self._inspector.set_lights([])
            return
        # Les cartes doivent modifier les mêmes dictionnaires que le canevas.
        # Une relecture via staging.get() créait une copie : le canevas sauvait
        # ensuite ses anciennes valeurs par-dessus, d'où les curseurs qui
        # revenaient immédiatement à leur position initiale.
        lights = self._canvas.commit().get("lights", [])
        self._inspector_light_signature = tuple(id(light) for light in lights)
        self._inspector.set_lights(lights)

    def _sync_inspector_structure(self):
        """Reconstruit l'inspecteur seulement si la liste des sources change."""
        lights = self._canvas.commit().get("lights", [])
        signature = tuple(id(light) for light in lights)
        if signature != self._inspector_light_signature:
            self._refresh_inspector()

    def _on_inspector_changed(self, _light: dict):
        self._canvas.reload()
        self._autosave()

    def _open_advanced_settings(self, light: dict):
        self._settings_light(light)
        self._refresh_inspector()

    def _delete_light_from_inspector(self, light: dict):
        self._canvas.remove_model(light)

    def _edit_light(self, model: dict):
        super()._edit_light(model)
        self._refresh_inspector()

    def _toggle_light(self, model: dict):
        super()._toggle_light(model)
        self._refresh_inspector()

    def _toggle_inspector(self):
        self._set_inspector_visible(not self._inspector.isVisible())

    def _set_inspector_visible(self, visible: bool):
        self._inspector.setVisible(bool(visible))
        self._inspector_toggle.set_open(bool(visible))

    def _open_sync_menu(self):
        menu = QMenu(self)
        menu.setStyleSheet(
            f"QMenu{{background:{CP['bg2']};border:1px solid {CP['border']};"
            f"border-radius:8px;padding:4px 0;}}"
            f"QMenu::item{{color:{CP['text_primary']};padding:8px 18px;font-size:11px;}}"
            f"QMenu::item:selected{{background:{CP['accent_dim']};color:#07080f;}}")
        menu.addAction(translate("Synchroniser les décors (storyboard → plateau)"),
                       self._sync_decors)
        menu.addAction(translate("Synchroniser le plateau complet → storyboard"),
                       self._sync_to_storyboard)
        menu.addAction(translate("Reconstruire caméra et acteurs depuis le storyboard"),
                       self._sync_from_storyboard)
        menu.exec(self._btn_sync.mapToGlobal(self._btn_sync.rect().bottomLeft()))

    def _sync_to_storyboard(self):
        """Le plateau combiné synchronise mise en scène, caméra et éclairage."""
        n = 0
        for shot in self._shots:
            sid = shot.get("id")
            if not sid:
                continue
            self._write_sections(shot, staging.get(sid))
            n += 1
        QMessageBox.information(
            self, translate("Synchronisation"),
            translate("Plateau synchronisé vers le storyboard.") + f"  ({n})")

    def _on_clear_all(self):
        super()._on_clear_all()
        self._refresh_inspector()
