"""
ui/tab_modify_live.py — Onglet « Modifier des clips » (PANDORA | Live) — mode LOT.

Refonte 2026-07-01 (parité Cinéma, sans DaVinci) : traite un LOT de clips en une
passe, comme le « Modifier des clips » Cinéma — et permet aussi un seul clip.
  - reçoit des clips depuis la Vidéothèque Live (add_clips_from_paths) ou fichiers
  - liste cochable (chaque clip coché = régénéré dans la file)
  - prompt GLOBAL (même consigne pour tout le lot) ou PAR CLIP (une consigne par clip)
  - image de référence GLOBALE ou PAR CLIP (@Image1)
  - section RENDU & AUDIO (son natif + résolution)
  - génération réelle Seedance (clip source = @Video1, mode "ext"/new_take), en file

PAS de dépendance DaVinci (ni inbox pandora_send, ni bridge, ni import Media Pool) ;
PAS de lip-sync LatentSync (post-prod Cinéma, hors périmètre VJ/mapping).
"""

import os

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QScrollArea, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QTextEdit, QComboBox, QSlider, QProgressBar,
    QListWidget, QListWidgetItem, QRadioButton, QButtonGroup, QCheckBox, QFrame,
)

from ui.styles import C
from ui.widgets import HelpBlock, show_api_error
from core.i18n import translate
from core.worker import GenerationWorker, abandon_thread
import core.vj_styles as vj
from ui.tab_video_engines_live import (
    _section, _divider, _combo_style, _prompt_style,
    _slider_style, _btn_accent_style, _btn_ghost_style,
)


# Modèles de prompt « Type de modification » — portés du Cinéma (@Video1 = clip
# d'origine). Reprend tout à l'identique et ne change QUE la cible → reprise ciblée
# sans tout régénérer. Texte FR traduit à l'affichage/envoi.
_MOD_TEMPLATES = {
    "retake": ("Reprends exactement @Video1 à l'identique — mêmes mouvements, cadrage, "
               "lumière, couleurs et contenu. Corrige UNIQUEMENT le défaut suivant : "
               "[décris précisément la zone et le problème]. Ne change RIEN d'autre : "
               "c'est une reprise ciblée (retake) du même clip."),
    "grade": ("Reprends exactement @Video1 — même image, mouvements et contenu, à "
              "l'identique. Change UNIQUEMENT l'étalonnage colorimétrique : [décris le "
              "look voulu]. Ne modifie ni la composition ni les sujets."),
    "bg": ("Reprends exactement @Video1 — mêmes sujets, mouvements, cadrage et lumière. "
           "Remplace UNIQUEMENT le décor / l'arrière-plan. Garde la même intégration "
           "lumineuse et les mêmes ombres. Ne change rien d'autre."),
}

_RES_OPTS = [("720p  (~$0.30/s)", "720p"), ("1080p", "1080p"), ("480p  (~$0.16/s)", "480p")]


class _RefPicker(QPushButton):
    """Sélecteur d'image de référence compact : clic vide → choisir ; clic plein → vider."""
    changed = pyqtSignal()

    def __init__(self, label: str = ""):
        super().__init__()
        self._path = ""
        self._label = label or translate("Image de référence")
        self.setMinimumHeight(30)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setStyleSheet(
            f"QPushButton{{background:transparent;color:{C['text_secondary']};"
            f"border:1px dashed {C['border_bright']};border-radius:7px;font-size:11px;"
            f"padding:0 12px;text-align:left;}}"
            f"QPushButton:hover{{color:{C['accent']};border-color:{C['accent']};}}"
        )
        self.clicked.connect(self._toggle)
        self._refresh()

    def _toggle(self):
        if self._path:
            self.set_path("")
        else:
            from PyQt6.QtWidgets import QFileDialog
            p, _ = QFileDialog.getOpenFileName(
                self, translate("Image de référence"), "",
                "Images (*.png *.jpg *.jpeg *.webp)")
            if p:
                self.set_path(p)

    def set_path(self, p: str):
        self._path = p or ""
        self._refresh()
        self.changed.emit()

    def _refresh(self):
        if self._path:
            self.setText("🖼  " + os.path.basename(self._path) + "     ✕")
        else:
            self.setText("＋  " + self._label)

    def path(self) -> str:
        return self._path


class TabModifyLive(QScrollArea):
    """Modifier un LOT de clips (Live) — génération réelle via Seedance, en file."""

    generation_done = pyqtSignal(dict)

    _ENGINES = [
        ("Seedance 2.0  (~$0.30/s)",      "seedance-2.0"),
        ("Seedance Fast  (~$0.09/s)",     "seedance-2.0-fast"),
    ]

    def __init__(self):
        super().__init__()
        self.setWidgetResizable(True)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        self._clips: list[str] = []
        self._per_clip_prompts: dict[int, str] = {}
        self._per_clip_ref: dict[int, str]     = {}
        self._current_idx: int = -1
        self._queue: list[int] = []
        self._queue_pos = 0
        self._worker = None
        self._last_folder = ""
        self._library_provider = None

        container = QWidget()
        container.setStyleSheet(f"background:{C['bg0']};")
        self.setWidget(container)
        lay = QVBoxLayout(container)
        lay.setContentsMargins(24, 20, 24, 24)
        lay.setSpacing(16)

        lay.addWidget(HelpBlock(translate("Modifier des clips (Live)"), [
            translate("▸ Ajoutez des clips (fichiers ou Vidéothèque). Cochez ceux à régénérer."),
            translate("▸ Prompt GLOBAL (même consigne pour tout le lot) ou PAR CLIP."),
            translate("▸ Le clip source sert de référence (@Video1) — Seedance en produit une nouvelle version."),
        ], C))

        # ── Sources de clips ─────────────────────────────────────────────────
        src_row = QHBoxLayout()
        src_row.setSpacing(8)
        _ss_src = (
            f"QPushButton{{background:transparent;color:{C['text_secondary']};"
            f"border:1px solid {C['border']};border-radius:7px;font-size:11px;"
            f"font-weight:600;padding:0 12px;}}"
            f"QPushButton:hover{{color:{C['text_primary']};border-color:{C['border_bright']};}}"
        )
        self._btn_add_clips = QPushButton("➕  " + translate("Ajouter des clips"))
        self._btn_add_clips.setMinimumHeight(32)
        self._btn_add_clips.setStyleSheet(_ss_src)
        self._btn_add_clips.clicked.connect(self._on_add_files)
        src_row.addWidget(self._btn_add_clips)
        self._btn_import_lib = QPushButton("⇪  " + translate("Importer la Vidéothèque"))
        self._btn_import_lib.setMinimumHeight(32)
        self._btn_import_lib.setStyleSheet(_ss_src)
        self._btn_import_lib.clicked.connect(self._on_import_library)
        src_row.addWidget(self._btn_import_lib)
        self._btn_sel_all = QPushButton(translate("Tout cocher"))
        self._btn_sel_all.setMinimumHeight(32)
        self._btn_sel_all.setStyleSheet(_ss_src)
        self._btn_sel_all.clicked.connect(lambda: self._check_all(True))
        src_row.addWidget(self._btn_sel_all)
        self._btn_clear_clips = QPushButton(translate("Vider"))
        self._btn_clear_clips.setMinimumHeight(32)
        self._btn_clear_clips.setStyleSheet(_ss_src)
        self._btn_clear_clips.clicked.connect(self._on_clear_clips)
        src_row.addWidget(self._btn_clear_clips)
        src_row.addStretch()
        lay.addLayout(src_row)

        # ── Liste des clips (cochables) ──────────────────────────────────────
        lay.addWidget(_section(translate("Clips à modifier")))
        self._clip_list = QListWidget()
        self._clip_list.setFixedHeight(150)
        self._clip_list.setStyleSheet(
            f"QListWidget{{background:{C['bg2']};border:1px solid {C['border']};"
            f"border-radius:8px;color:{C['text_primary']};font-size:11px;padding:4px;}}"
            f"QListWidget::item{{padding:5px 6px;border-radius:5px;}}"
            f"QListWidget::item:selected{{background:{C['accent_dim']};color:{C['text_primary']};}}"
        )
        self._clip_list.currentRowChanged.connect(self._on_clip_row_changed)
        lay.addWidget(self._clip_list)

        self._empty_lbl = QLabel(translate("Aucun clip — ajoutez-en ou importez la Vidéothèque."))
        self._empty_lbl.setStyleSheet(
            f"color:{C['text_dim']};font-size:11px;font-style:italic;background:transparent;")
        lay.addWidget(self._empty_lbl)

        # ── Template de style (VJ) ───────────────────────────────────────────
        lay.addWidget(_section(translate("Template de style")))
        self._style_combo = QComboBox()
        self._style_combo.setMinimumHeight(34)
        self._style_combo.setStyleSheet(_combo_style())
        self._style_combo.addItem(translate("Aucun style"), "")
        for s in vj.get_styles():
            self._style_combo.addItem(vj.localized_name(s), s["key"])
        self._style_combo.currentIndexChanged.connect(self._on_style_changed)
        lay.addWidget(self._style_combo)

        # ── Mode de prompt : global / par clip ───────────────────────────────
        mode_row = QHBoxLayout()
        mode_row.setSpacing(14)
        self._rb_global   = QRadioButton(translate("Prompt global"))
        self._rb_per_clip = QRadioButton(translate("Prompt par clip"))
        self._rb_global.setChecked(True)
        self._rb_group = QButtonGroup(self)
        self._rb_group.addButton(self._rb_global, 0)
        self._rb_group.addButton(self._rb_per_clip, 1)
        for rb in (self._rb_global, self._rb_per_clip):
            rb.setStyleSheet(f"color:{C['text_primary']};font-size:12px;background:transparent;")
        self._rb_global.toggled.connect(self._on_prompt_mode_changed)
        mode_row.addWidget(self._rb_global)
        mode_row.addWidget(self._rb_per_clip)
        mode_row.addStretch()
        lay.addLayout(mode_row)

        # ── Prompt GLOBAL ────────────────────────────────────────────────────
        self._global_panel = QWidget()
        self._global_panel.setStyleSheet("background:transparent;")
        _gp = QVBoxLayout(self._global_panel)
        _gp.setContentsMargins(0, 0, 0, 0)
        _gp.setSpacing(8)
        self._prompt = QTextEdit()
        self._prompt.setPlaceholderText(translate(
            "Décrivez la modification… (FR accepté, traduit automatiquement)"))
        self._prompt.setMinimumHeight(80)
        self._prompt.setMaximumHeight(140)
        self._prompt.setStyleSheet(_prompt_style())
        _gp.addWidget(self._prompt)
        self._global_ref = _RefPicker(translate("Image de référence globale"))
        _gp.addWidget(self._global_ref)
        lay.addWidget(self._global_panel)

        # ── Prompt PAR CLIP ──────────────────────────────────────────────────
        self._per_clip_panel = QWidget()
        self._per_clip_panel.setVisible(False)
        self._per_clip_panel.setStyleSheet("background:transparent;")
        _pp = QVBoxLayout(self._per_clip_panel)
        _pp.setContentsMargins(0, 0, 0, 0)
        _pp.setSpacing(8)
        self._pc_title = QLabel(translate("← Sélectionnez un clip dans la liste pour écrire son prompt."))
        self._pc_title.setStyleSheet(f"color:{C['text_dim']};font-size:11px;background:transparent;")
        _pp.addWidget(self._pc_title)
        self._pc_prompt = QTextEdit()
        self._pc_prompt.setPlaceholderText(translate(
            "Prompt de CE clip… (FR accepté, traduit automatiquement)"))
        self._pc_prompt.setMinimumHeight(80)
        self._pc_prompt.setMaximumHeight(140)
        self._pc_prompt.setStyleSheet(_prompt_style())
        self._pc_prompt.setEnabled(False)
        _pp.addWidget(self._pc_prompt)
        self._pc_ref = _RefPicker(translate("Image de référence de ce clip"))
        self._pc_ref.setEnabled(False)
        self._pc_ref.changed.connect(self._save_current_per_clip)
        _pp.addWidget(self._pc_ref)
        lay.addWidget(self._per_clip_panel)

        # ── Type de modification (Retake…) ───────────────────────────────────
        self._mod_combo = QComboBox()
        self._mod_combo.setMinimumHeight(30)
        self._mod_combo.setStyleSheet(_combo_style())
        self._mod_combo.addItem(translate("✎ Insérer un modèle…"), "")
        self._mod_combo.addItem(translate("Corriger un défaut précis (Retake)"), "retake")
        self._mod_combo.addItem(translate("Changer l'étalonnage (couleurs)"), "grade")
        self._mod_combo.addItem(translate("Changer le décor (arrière-plan)"), "bg")
        self._mod_combo.setToolTip(translate(
            "Insère un modèle de prompt (@Video1 = clip d'origine) — à compléter ensuite."))
        self._mod_combo.currentIndexChanged.connect(self._on_mod_type)
        lay.addWidget(self._mod_combo)

        # ── RENDU & AUDIO (repliable) ────────────────────────────────────────
        self._ra_open = False
        # .replace : « & » nu = mnémonique Qt sur un QPushButton (caractère avalé)
        self._ra_toggle = QPushButton("▶  " + translate("RENDU & AUDIO").replace("&", "&&"))
        self._ra_toggle.setMinimumHeight(30)
        self._ra_toggle.setCursor(Qt.CursorShape.PointingHandCursor)
        self._ra_toggle.setStyleSheet(
            f"QPushButton{{background:{C['bg2']};color:{C['text_secondary']};"
            f"border:1px solid {C['border']};border-radius:7px;font-size:11px;"
            f"font-weight:700;padding:0 12px;text-align:left;}}"
            f"QPushButton:hover{{color:{C['text_primary']};}}")
        self._ra_toggle.clicked.connect(self._toggle_rendu_audio)
        lay.addWidget(self._ra_toggle)

        self._ra_body = QFrame()
        self._ra_body.setVisible(False)
        self._ra_body.setStyleSheet("background:transparent;")
        _ra = QVBoxLayout(self._ra_body)
        _ra.setContentsMargins(4, 6, 4, 6)
        _ra.setSpacing(10)
        self._audio_chk = QCheckBox(translate("Générer l'audio (son natif)"))
        self._audio_chk.setChecked(True)
        self._audio_chk.setStyleSheet(f"color:{C['text_primary']};font-size:12px;background:transparent;")
        _ra.addWidget(self._audio_chk)
        _res_row = QHBoxLayout()
        _res_row.setSpacing(8)
        _res_lbl = QLabel(translate("Résolution :"))
        _res_lbl.setStyleSheet(f"color:{C['text_secondary']};font-size:12px;background:transparent;")
        _res_row.addWidget(_res_lbl)
        self._res_combo = QComboBox()
        self._res_combo.setMinimumHeight(30)
        self._res_combo.setStyleSheet(_combo_style())
        for _lbl, _val in _RES_OPTS:
            self._res_combo.addItem(_lbl, _val)
        _res_row.addWidget(self._res_combo, 1)
        _ra.addLayout(_res_row)
        lay.addWidget(self._ra_body)

        # ── Moteur + durée ───────────────────────────────────────────────────
        row = QHBoxLayout()
        row.setSpacing(16)
        eng_col = QVBoxLayout()
        eng_col.setSpacing(6)
        eng_col.addWidget(_section(translate("Moteur de génération")))
        self._engine_combo = QComboBox()
        self._engine_combo.setMinimumHeight(34)
        self._engine_combo.setStyleSheet(_combo_style())
        for label, key in self._ENGINES:
            self._engine_combo.addItem(label, key)
        eng_col.addWidget(self._engine_combo)
        row.addLayout(eng_col, 1)
        dur_col = QVBoxLayout()
        dur_col.setSpacing(6)
        self._dur_lbl = QLabel(translate("Durée :") + " 5 s")
        self._dur_lbl.setStyleSheet(f"color:{C['text_secondary']};font-size:12px;background:transparent;")
        dur_col.addWidget(self._dur_lbl)
        self._dur_slider = QSlider(Qt.Orientation.Horizontal)
        self._dur_slider.setMinimum(2)
        self._dur_slider.setMaximum(10)
        self._dur_slider.setValue(5)
        self._dur_slider.setStyleSheet(_slider_style())
        self._dur_slider.valueChanged.connect(
            lambda v: self._dur_lbl.setText(translate("Durée :") + f" {v} s"))
        dur_col.addWidget(self._dur_slider)
        row.addLayout(dur_col, 1)
        lay.addLayout(row)

        lay.addWidget(_divider())

        # ── Générer (file d'attente) ─────────────────────────────────────────
        self._btn_generate = QPushButton("▶▶  " + translate("Lancer la file d'attente"))
        self._btn_generate.setMinimumHeight(46)
        self._btn_generate.setStyleSheet(_btn_accent_style())
        self._btn_generate.clicked.connect(self._on_generate)
        lay.addWidget(self._btn_generate)

        self._progress = QProgressBar()
        self._progress.setFixedHeight(6)
        self._progress.setTextVisible(False)
        self._progress.setValue(0)
        self._progress.setStyleSheet(
            f"QProgressBar{{background:{C['bg3']};border-radius:3px;border:none;}}"
            f"QProgressBar::chunk{{background:{C['accent']};border-radius:3px;}}")
        self._progress.hide()
        lay.addWidget(self._progress)

        self._status_lbl = QLabel("")
        self._status_lbl.setStyleSheet(
            f"color:{C['text_secondary']};font-size:11px;"
            f"font-family:'Consolas',monospace;background:transparent;")
        self._status_lbl.hide()
        lay.addWidget(self._status_lbl)

        self._btn_open = QPushButton(translate("Ouvrir le dossier"))
        self._btn_open.setFixedHeight(30)
        self._btn_open.setToolTip(translate("Ouvre le dossier de destination des clips."))
        self._btn_open.setStyleSheet(_btn_ghost_style())
        self._btn_open.clicked.connect(self._on_open_folder)
        lay.addWidget(self._btn_open)

        lay.addStretch()
        self._refresh_clip_state()

    # ── Sources de clips ──────────────────────────────────────────────────────

    def set_library_provider(self, fn):
        """fn() → list[str] des clips de la Vidéothèque (« Importer la Vidéothèque »)."""
        self._library_provider = fn

    def _on_add_files(self):
        from PyQt6.QtWidgets import QFileDialog
        paths, _ = QFileDialog.getOpenFileNames(
            self, translate("Ajouter des clips"), "",
            "Vidéos (*.mp4 *.mov *.webm *.m4v *.gif);;Tous les fichiers (*)")
        if paths:
            self.add_clips_from_paths(paths)

    def _on_import_library(self):
        if not self._library_provider:
            return
        try:
            paths = list(self._library_provider() or [])
        except Exception:
            paths = []
        self.add_clips_from_paths(paths)

    def _on_clear_clips(self):
        self._clips.clear()
        self._per_clip_prompts.clear()
        self._per_clip_ref.clear()
        self._current_idx = -1
        self._reload_list()

    def add_clips_from_paths(self, paths: list):
        for p in paths:
            if p and os.path.isfile(p) and p not in self._clips:
                self._clips.append(p)
        self._reload_list()

    def _reload_list(self):
        self._clip_list.blockSignals(True)
        self._clip_list.clear()
        for p in self._clips:
            it = QListWidgetItem(os.path.basename(p))
            it.setFlags(it.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            it.setCheckState(Qt.CheckState.Checked)
            self._clip_list.addItem(it)
        self._clip_list.blockSignals(False)
        if self._clips:
            self._clip_list.setCurrentRow(len(self._clips) - 1)
        self._refresh_clip_state()

    def _check_all(self, checked: bool):
        st = Qt.CheckState.Checked if checked else Qt.CheckState.Unchecked
        for i in range(self._clip_list.count()):
            self._clip_list.item(i).setCheckState(st)

    def _refresh_clip_state(self):
        has = bool(self._clips)
        self._empty_lbl.setVisible(not has)
        self._clip_list.setVisible(has)
        self._btn_generate.setEnabled(has)

    # ── Prompt mode / par clip ─────────────────────────────────────────────────

    def _on_prompt_mode_changed(self, _checked=False):
        per_clip = self._rb_per_clip.isChecked()
        self._global_panel.setVisible(not per_clip)
        self._per_clip_panel.setVisible(per_clip)
        if per_clip:
            self._load_current_per_clip()

    def _on_clip_row_changed(self, row: int):
        # Sauvegarde le prompt/réf du clip précédent avant de changer.
        self._save_current_per_clip()
        self._current_idx = row
        if self._rb_per_clip.isChecked():
            self._load_current_per_clip()

    def _save_current_per_clip(self):
        if 0 <= self._current_idx < len(self._clips) and self._pc_prompt.isEnabled():
            self._per_clip_prompts[self._current_idx] = self._pc_prompt.toPlainText()
            self._per_clip_ref[self._current_idx] = self._pc_ref.path()

    def _load_current_per_clip(self):
        idx = self._clip_list.currentRow()
        self._current_idx = idx
        ok = 0 <= idx < len(self._clips)
        self._pc_prompt.setEnabled(ok)
        self._pc_ref.setEnabled(ok)
        if ok:
            name = os.path.basename(self._clips[idx])
            self._pc_title.setText(translate("Prompt du clip :") + f"  {name}")
            self._pc_prompt.blockSignals(True)
            self._pc_prompt.setPlainText(self._per_clip_prompts.get(idx, ""))
            self._pc_prompt.blockSignals(False)
            self._pc_ref.blockSignals(True)
            self._pc_ref.set_path(self._per_clip_ref.get(idx, ""))
            self._pc_ref.blockSignals(False)
        else:
            self._pc_title.setText(translate("← Sélectionnez un clip dans la liste pour écrire son prompt."))

    # ── Style + modèles ────────────────────────────────────────────────────────

    def _active_prompt_widget(self) -> QTextEdit:
        return self._pc_prompt if self._rb_per_clip.isChecked() else self._prompt

    def _on_style_changed(self, _idx: int):
        key = self._style_combo.currentData()
        if not key:
            return
        st = vj.get_style(key)
        if st:
            self._active_prompt_widget().setPlainText(st["prompt"])

    def _on_mod_type(self, _idx: int):
        """Insère un modèle « Type de modification » (Retake…) dans le prompt actif."""
        key = self._mod_combo.currentData()
        if key:
            tpl = translate(_MOD_TEMPLATES.get(key, ""))
            if tpl:
                self._active_prompt_widget().setPlainText(tpl)
        self._mod_combo.blockSignals(True)
        self._mod_combo.setCurrentIndex(0)
        self._mod_combo.blockSignals(False)

    def _toggle_rendu_audio(self):
        self._ra_open = not self._ra_open
        self._ra_body.setVisible(self._ra_open)
        self._ra_toggle.setText(
            ("▼" if self._ra_open else "▶") + "  "
            + translate("RENDU & AUDIO").replace("&", "&&"))

    # ── Génération en LOT ──────────────────────────────────────────────────────

    def _on_generate(self):
        if self._worker and self._worker.isRunning():
            return
        self._save_current_per_clip()
        sel = [i for i in range(self._clip_list.count())
               if self._clip_list.item(i).checkState() == Qt.CheckState.Checked]
        if not sel:
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.warning(self, translate("Aucun clip"),
                                translate("Cochez au moins un clip à modifier."))
            return
        self._queue = sel
        self._queue_pos = 0
        self._btn_generate.setEnabled(False)
        self._btn_generate.setText(translate("Génération en cours…"))
        self._progress.setValue(0)
        self._progress.show()
        self._status_lbl.show()
        self._process_next()

    def _build_params(self, idx: int, clip_path: str) -> dict:
        if self._rb_per_clip.isChecked():
            prompt = (self._per_clip_prompts.get(idx, "") or "").strip() \
                or self._prompt.toPlainText().strip()
            ref = self._per_clip_ref.get(idx, "") or self._global_ref.path()
        else:
            prompt = self._prompt.toPlainText().strip()
            ref = self._global_ref.path()
        if "@Video1" not in prompt:
            prompt = f"@Video1 {prompt}".strip() if prompt else "@Video1"
        params = {
            "mode":           "ext",
            "direction":      "new_take",
            "prompt":         prompt,
            "model":          self._engine_combo.currentData() or "seedance-2.0",
            "duration":       self._dur_slider.value(),
            "resolution":     self._res_combo.currentData() or "720p",
            "aspect_ratio":   "16:9",
            "generate_audio": self._audio_chk.isChecked(),
            "video_path":     clip_path,
        }
        if ref and os.path.isfile(ref):
            params["ref_images"] = [ref]
            if "@Image1" not in params["prompt"]:
                params["prompt"] = (params["prompt"] + " @Image1").strip()
        return params

    def _process_next(self):
        if self._queue_pos >= len(self._queue):
            self._btn_generate.setEnabled(True)
            self._btn_generate.setText("▶▶  " + translate("Lancer la file d'attente"))
            self._status_lbl.setText("✓  " + translate("File terminée."))
            self._status_lbl.setStyleSheet(
                f"color:{C['accent']};font-size:11px;background:transparent;")
            return
        idx = self._queue[self._queue_pos]
        clip = self._clips[idx]
        params = self._build_params(idx, clip)
        # Parquer le worker précédent AVANT de réassigner (anti-blocage de file).
        if self._worker is not None:
            abandon_thread(self._worker)
        self._worker = GenerationWorker(params)
        self._worker.progress.connect(self._on_progress)
        self._worker.finished.connect(lambda r, _i=idx: self._on_one_finished(r, _i))
        self._worker.failed.connect(lambda e, _i=idx: self._on_one_failed(e, _i))
        self._worker.start()
        n, tot = self._queue_pos + 1, len(self._queue)
        self._set_item_prefix(idx, "⏳ ")
        self._status_lbl.setText(f"⏳  {n}/{tot} — {os.path.basename(clip)}")

    def _on_progress(self, pct: int, msg: str):
        self._progress.setValue(pct)

    def _on_one_finished(self, result: dict, idx: int):
        local = result.get("local_path", "")
        if not local and result.get("video_url"):
            try:
                from core.download import download_result
                from core.config import get_output_dir
                ir = download_result(result, get_output_dir())
            except Exception as e:
                ir = {"success": False, "mock": False, "local_path": "", "error": str(e)}
            if ir.get("success") and not ir.get("mock"):
                local = ir.get("local_path", "")
                result = {**result, "local_path": local}
        if local:
            self._last_folder = os.path.dirname(local)
            self._set_item_prefix(idx, "✓ ")
            self.generation_done.emit(result)
        else:
            self._set_item_prefix(idx, "✓ ")   # mode démo (pas de clé)
        self._queue_pos += 1
        self._process_next()

    def _on_one_failed(self, err: str, idx: int):
        self._set_item_prefix(idx, "✗ ")
        self._queue_pos += 1
        if self._queue_pos >= len(self._queue):
            self._status_lbl.setText(f"✗  {err[:100]}")
            show_api_error(self, err)
        self._process_next()

    def _set_item_prefix(self, idx: int, prefix: str):
        it = self._clip_list.item(idx)
        if it is None:
            return
        base = os.path.basename(self._clips[idx]) if 0 <= idx < len(self._clips) else it.text()
        it.setText(prefix + base)

    def _on_open_folder(self):
        folder = self._last_folder
        if not folder or not os.path.isdir(folder):
            from core.config import get_output_dir
            folder = get_output_dir()
            os.makedirs(folder, exist_ok=True)
        try:
            os.startfile(folder)
        except AttributeError:
            import subprocess
            subprocess.Popen(["xdg-open", folder])
