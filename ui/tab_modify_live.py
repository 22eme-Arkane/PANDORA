"""
ui/tab_modify_live.py — Onglet « Modifier » dédié à PANDORA | Live.

Version allégée et adaptée au live de l'ancien « Modifier des clips » :
  - reçoit des clips depuis la Vidéothèque Live (pont add_clips_from_paths)
  - choix d'un clip, d'un template de style VJ et d'un prompt de modification
  - génère une nouvelle version via Seedance (le clip est uploadé en référence
    vidéo @Video1, mode "ext"/new_take)

PAS de dépendance DaVinci (ni inbox pandora_send, ni bridge, ni import Media Pool).
On verra à l'usage si cet onglet est conservé.
"""

import os

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QScrollArea, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QTextEdit, QComboBox, QSlider, QProgressBar,
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


class TabModifyLive(QScrollArea):
    """Modifier un clip déjà généré (Live) — génération réelle via Seedance."""

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
        self._worker = None
        self._last_folder = ""

        container = QWidget()
        container.setStyleSheet(f"background:{C['bg0']};")
        self.setWidget(container)
        lay = QVBoxLayout(container)
        lay.setContentsMargins(24, 20, 24, 24)
        lay.setSpacing(16)

        lay.addWidget(HelpBlock(translate("Modifier un clip (Live)"), [
            translate("▸ Envoyez un clip depuis la Vidéothèque (⤷ Modifier)."),
            translate("▸ Choisissez un style, écrivez la modification souhaitée, puis générez."),
            translate("▸ Le clip source est utilisé comme référence — Seedance en produit une nouvelle version."),
        ], C))

        # ── Sources de clips (comme l'Upscaling) ─────────────────────────────
        self._library_provider = None    # callable → list[str] (branché par le Studio)
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
        self._btn_clear_clips = QPushButton(translate("Vider"))
        self._btn_clear_clips.setMinimumHeight(32)
        self._btn_clear_clips.setStyleSheet(_ss_src)
        self._btn_clear_clips.clicked.connect(self._on_clear_clips)
        src_row.addWidget(self._btn_clear_clips)
        src_row.addStretch()
        lay.addLayout(src_row)

        # ── Clip à modifier ───────────────────────────────────────────────────
        lay.addWidget(_section(translate("Clip à modifier")))
        self._clip_combo = QComboBox()
        self._clip_combo.setMinimumHeight(34)
        self._clip_combo.setStyleSheet(_combo_style())
        lay.addWidget(self._clip_combo)

        self._empty_lbl = QLabel(translate("Aucun clip — envoyez-en un depuis la Vidéothèque."))
        self._empty_lbl.setStyleSheet(
            f"color:{C['text_dim']};font-size:11px;font-style:italic;background:transparent;"
        )
        lay.addWidget(self._empty_lbl)

        # ── Template de style (VJ) ────────────────────────────────────────────
        lay.addWidget(_section(translate("Template de style")))
        self._style_combo = QComboBox()
        self._style_combo.setMinimumHeight(34)
        self._style_combo.setStyleSheet(_combo_style())
        self._style_combo.addItem(translate("Aucun style"), "")
        for s in vj.get_styles():
            self._style_combo.addItem(vj.localized_name(s), s["key"])
        self._style_combo.currentIndexChanged.connect(self._on_style_changed)
        lay.addWidget(self._style_combo)

        # ── Prompt de modification ────────────────────────────────────────────
        lay.addWidget(_section(translate("Prompt de modification")))
        self._prompt = QTextEdit()
        self._prompt.setPlaceholderText(translate(
            "Décrivez la modification… (FR accepté, traduit automatiquement)"
        ))
        self._prompt.setMinimumHeight(90)
        self._prompt.setMaximumHeight(150)
        self._prompt.setStyleSheet(_prompt_style())
        lay.addWidget(self._prompt)

        # ── Moteur + durée ────────────────────────────────────────────────────
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
        self._dur_lbl = QLabel(translate("Durée : 5 s"))
        self._dur_lbl.setStyleSheet(f"color:{C['text_secondary']};font-size:12px;background:transparent;")
        dur_col.addWidget(self._dur_lbl)
        self._dur_slider = QSlider(Qt.Orientation.Horizontal)
        self._dur_slider.setMinimum(2)
        self._dur_slider.setMaximum(10)
        self._dur_slider.setValue(5)
        self._dur_slider.setStyleSheet(_slider_style())
        self._dur_slider.valueChanged.connect(
            lambda v: self._dur_lbl.setText(translate("Durée :") + f" {v} s")
        )
        dur_col.addWidget(self._dur_slider)
        row.addLayout(dur_col, 1)
        lay.addLayout(row)

        lay.addWidget(_divider())

        # ── Générer ───────────────────────────────────────────────────────────
        self._btn_generate = QPushButton("▶  " + translate("Générer la modification"))
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
            f"QProgressBar::chunk{{background:{C['accent']};border-radius:3px;}}"
        )
        self._progress.hide()
        lay.addWidget(self._progress)

        self._status_lbl = QLabel("")
        self._status_lbl.setStyleSheet(
            f"color:{C['text_secondary']};font-size:11px;"
            f"font-family:'Consolas',monospace;background:transparent;"
        )
        self._status_lbl.hide()
        lay.addWidget(self._status_lbl)

        self._btn_open = QPushButton(translate("Ouvrir le dossier"))
        self._btn_open.setFixedHeight(30)
        self._btn_open.setEnabled(False)
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
        self._reload_combo()

    # ── Pont depuis la Vidéothèque ──────────────────────────────────────────

    def add_clips_from_paths(self, paths: list):
        for p in paths:
            if p and os.path.isfile(p) and p not in self._clips:
                self._clips.append(p)
        self._reload_combo()

    def _reload_combo(self):
        self._clip_combo.blockSignals(True)
        self._clip_combo.clear()
        for p in self._clips:
            self._clip_combo.addItem(os.path.basename(p), p)
        if self._clips:
            self._clip_combo.setCurrentIndex(len(self._clips) - 1)  # le dernier reçu
        self._clip_combo.blockSignals(False)
        self._refresh_clip_state()

    def _refresh_clip_state(self):
        has = bool(self._clips)
        self._empty_lbl.setVisible(not has)
        self._clip_combo.setVisible(has)
        self._btn_generate.setEnabled(has)

    # ── Style ───────────────────────────────────────────────────────────────

    def _on_style_changed(self, _idx: int):
        key = self._style_combo.currentData()
        if not key:
            return
        st = vj.get_style(key)
        if st:
            self._prompt.setPlainText(st["prompt"])

    # ── Génération ──────────────────────────────────────────────────────────

    def _on_generate(self):
        if self._worker and self._worker.isRunning():
            return
        clip_path = self._clip_combo.currentData()
        if not clip_path or not os.path.isfile(clip_path):
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.warning(self, translate("Aucun clip"),
                                translate("Envoyez d'abord un clip depuis la Vidéothèque."))
            return

        prompt = self._prompt.toPlainText().strip()
        if "@Video1" not in prompt:
            prompt = f"@Video1 {prompt}" if prompt else "@Video1"

        params = {
            "mode":         "ext",
            "direction":    "new_take",
            "prompt":       prompt,
            "model":        self._engine_combo.currentData() or "seedance-2.0",
            "duration":     self._dur_slider.value(),
            "resolution":   "720p",
            "aspect_ratio": "16:9",
            "video_path":   clip_path,
        }

        self._worker = GenerationWorker(params)
        self._worker.progress.connect(self._on_progress)
        self._worker.finished.connect(self._on_finished)
        self._worker.failed.connect(self._on_failed)
        self._worker.start()

        self._btn_generate.setEnabled(False)
        self._btn_generate.setText(translate("Génération en cours…"))
        self._progress.setValue(0)
        self._progress.show()
        self._status_lbl.show()

    def _on_progress(self, pct: int, msg: str):
        self._progress.setValue(pct)
        self._status_lbl.setText(translate(msg))

    def _on_finished(self, result: dict):
        self._btn_generate.setEnabled(True)
        self._btn_generate.setText("▶  " + translate("Générer la modification"))
        self._progress.setValue(100)
        local = result.get("local_path", "")
        # Seedance (run_real) renvoie video_url sans local_path : on télécharge le clip.
        if not local and result.get("video_url"):
            try:
                from davinci.importer import import_result
                from core.config import get_output_dir
                ir = import_result(result, get_output_dir(), import_to_davinci=False)
            except Exception as e:
                ir = {"success": False, "mock": False, "local_path": "", "error": str(e)}
            if ir.get("success") and not ir.get("mock"):
                local = ir.get("local_path", "")
                result = {**result, "local_path": local}
        if local:
            self._last_folder = os.path.dirname(local)
            self._status_lbl.setText("✓  " + os.path.basename(local))
            self._status_lbl.setStyleSheet(
                f"color:{C['accent']};font-size:11px;background:transparent;"
            )
            self._btn_open.setEnabled(True)
            self.generation_done.emit(result)
        else:
            self._status_lbl.setText("✓  " + translate("Terminé (mode démo — aucune clé fal.ai)"))

    def _on_failed(self, err: str):
        self._btn_generate.setEnabled(True)
        self._btn_generate.setText("▶  " + translate("Générer la modification"))
        self._progress.setValue(0)
        self._status_lbl.setText(f"✗  {err[:120]}")
        show_api_error(self, err)

    def _on_open_folder(self):
        if self._last_folder and os.path.isdir(self._last_folder):
            try:
                os.startfile(self._last_folder)
            except AttributeError:
                import subprocess
                subprocess.Popen(["xdg-open", self._last_folder])
