"""
ui/tab_upscale_live.py — Onglet « Upscaling » du Studio IA Live.

Fonctionne comme « Modifier » mais en LOT (file d'attente de plans) :
  - reçoit des clips depuis la Vidéothèque (pont add_clips_from_paths + « Importer
    toute la Vidéothèque »), ou via un sélecteur de fichiers ;
  - upscale TOUTE la file (ex. tout généré en 480p → ressortir en 1080p/4K) ;
  - moteurs fal.ai : Topaz Video (qualité max) ou SeedVR2 (rapide).

Composant 100 % Live. Une fois stabilisé, sera porté à PANDORA Cinéma.
"""

import os

from PyQt6.QtCore import Qt, pyqtSignal, QUrl
from PyQt6.QtGui import QDesktopServices
from PyQt6.QtWidgets import (
    QScrollArea, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QComboBox, QProgressBar, QFileDialog,
)

from ui.styles import C
from ui.widgets import HelpBlock
from core.i18n import translate
from api.upscale import UPSCALE_MODELS, TOPAZ_MODELS
from ui.tab_video_engines_live import (
    _section, _divider, _combo_style, _btn_accent_style, _btn_ghost_style,
)

_VIDEO_EXTS = (".mp4", ".mov", ".webm", ".m4v", ".gif")


class TabUpscaleLive(QScrollArea):
    """Upscaling en lot d'une file de clips (Live)."""

    generation_done = pyqtSignal(str)   # chemin du clip upscalé

    def __init__(self):
        super().__init__()
        self.setWidgetResizable(True)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        self._queue: list[dict] = []     # {path, status: pending|done|error, out}
        self._worker = None
        self._proc_running = False
        self._last_folder = ""
        self._library_provider = None    # callable → list[str]

        container = QWidget()
        container.setStyleSheet(f"background:{C['bg0']};")
        self.setWidget(container)
        lay = QVBoxLayout(container)
        lay.setContentsMargins(24, 20, 24, 24)
        lay.setSpacing(16)

        lay.addWidget(HelpBlock(translate("Upscaling de la séquence (Live)"), [
            translate("▸ Ajoutez des clips, ou importez toute la Vidéothèque."),
            translate("▸ Choisissez le moteur et le facteur (ex. ×2, ×4)."),
            translate("▸ « Upscaler toute la file » ressort tous les plans en haute résolution."),
        ], C))

        # ── Source des clips ──────────────────────────────────────────────────
        src_row = QHBoxLayout()
        src_row.setSpacing(8)
        self._btn_add = QPushButton("➕  " + translate("Ajouter des clips"))
        self._btn_add.setMinimumHeight(34)
        self._btn_add.setStyleSheet(_btn_ghost_style())
        self._btn_add.clicked.connect(self._on_add_files)
        src_row.addWidget(self._btn_add)
        self._btn_import_lib = QPushButton("⇪  " + translate("Importer la Vidéothèque"))
        self._btn_import_lib.setMinimumHeight(34)
        self._btn_import_lib.setStyleSheet(_btn_ghost_style())
        self._btn_import_lib.clicked.connect(self._on_import_library)
        src_row.addWidget(self._btn_import_lib)
        self._btn_clear = QPushButton(translate("Vider"))
        self._btn_clear.setMinimumHeight(34)
        self._btn_clear.setStyleSheet(_btn_ghost_style())
        self._btn_clear.clicked.connect(self._on_clear)
        src_row.addWidget(self._btn_clear)
        src_row.addStretch()
        lay.addLayout(src_row)

        # ── File d'attente ────────────────────────────────────────────────────
        lay.addWidget(_section(translate("File d'attente")))
        self._empty_lbl = QLabel(translate("File vide — ajoutez des clips ou importez la Vidéothèque."))
        self._empty_lbl.setStyleSheet(
            f"color:{C['text_dim']};font-size:11px;font-style:italic;background:transparent;")
        lay.addWidget(self._empty_lbl)
        self._queue_box = QVBoxLayout()
        self._queue_box.setSpacing(5)
        lay.addLayout(self._queue_box)

        # ── Réglages ──────────────────────────────────────────────────────────
        lay.addWidget(_divider())
        set_row = QHBoxLayout()
        set_row.setSpacing(16)

        mcol = QVBoxLayout(); mcol.setSpacing(6)
        mcol.addWidget(_section(translate("Moteur d'upscaling")))
        self._model_combo = QComboBox()
        self._model_combo.setMinimumHeight(34)
        self._model_combo.setStyleSheet(_combo_style())
        for label, key in UPSCALE_MODELS:
            self._model_combo.addItem(label, key)
        self._model_combo.currentIndexChanged.connect(self._on_model_changed)
        mcol.addWidget(self._model_combo)
        set_row.addLayout(mcol, 2)

        fcol = QVBoxLayout(); fcol.setSpacing(6)
        fcol.addWidget(_section(translate("Facteur")))
        self._factor_combo = QComboBox()
        self._factor_combo.setMinimumHeight(34)
        self._factor_combo.setStyleSheet(_combo_style())
        self._factor_combo.addItem("×2  (480p→~1080p)", 2)
        self._factor_combo.addItem("×4  (480p→~4K)", 4)
        fcol.addWidget(self._factor_combo)
        set_row.addLayout(fcol, 1)

        tcol = QVBoxLayout(); tcol.setSpacing(6)
        tcol.addWidget(_section(translate("Modèle Topaz")))
        self._topaz_combo = QComboBox()
        self._topaz_combo.setMinimumHeight(34)
        self._topaz_combo.setStyleSheet(_combo_style())
        for label, key in TOPAZ_MODELS:
            self._topaz_combo.addItem(translate(label), key)
        tcol.addWidget(self._topaz_combo)
        set_row.addLayout(tcol, 1)
        lay.addLayout(set_row)

        # ── Lancer ────────────────────────────────────────────────────────────
        self._btn_run = QPushButton("▶  " + translate("Upscaler toute la file"))
        self._btn_run.setMinimumHeight(46)
        self._btn_run.setStyleSheet(_btn_accent_style())
        self._btn_run.clicked.connect(self._on_run)
        lay.addWidget(self._btn_run)

        self._btn_cancel = QPushButton("■  " + translate("Annuler la file"))
        self._btn_cancel.setMinimumHeight(36)
        self._btn_cancel.setVisible(False)
        self._btn_cancel.setToolTip(translate(
            "Arrête la file : le clip en cours est abandonné,\n"
            "les clips restants sont conservés en attente."))
        self._btn_cancel.setStyleSheet(
            f"QPushButton{{background:{C['bg3']};color:{C['red']};"
            f"border:1px solid {C['red']};border-radius:7px;"
            f"font-size:11px;font-weight:700;}}"
            f"QPushButton:hover{{background:rgba(255,79,106,0.12);}}"
        )
        self._btn_cancel.clicked.connect(self._on_cancel)
        lay.addWidget(self._btn_cancel)

        self._progress = QProgressBar()
        self._progress.setFixedHeight(6)
        self._progress.setTextVisible(False)
        self._progress.setValue(0)
        self._progress.setStyleSheet(
            f"QProgressBar{{background:{C['bg3']};border-radius:3px;border:none;}}"
            f"QProgressBar::chunk{{background:{C['accent']};border-radius:3px;}}")
        self._progress.hide()
        lay.addWidget(self._progress)

        self._status = QLabel("")
        self._status.setStyleSheet(
            f"color:{C['text_secondary']};font-size:11px;"
            f"font-family:'Consolas',monospace;background:transparent;")
        lay.addWidget(self._status)

        self._btn_open = QPushButton(translate("Ouvrir le dossier"))
        self._btn_open.setFixedHeight(30)
        self._btn_open.setEnabled(False)
        self._btn_open.setStyleSheet(_btn_ghost_style())
        self._btn_open.clicked.connect(self._on_open_folder)
        lay.addWidget(self._btn_open)

        lay.addStretch()
        self._on_model_changed()
        self._refresh_queue()

    # ── Connexion Vidéothèque ─────────────────────────────────────────────────

    def set_library_provider(self, fn):
        """fn() → list[str] des clips de la Vidéothèque (pour « Importer la Vidéothèque »)."""
        self._library_provider = fn

    def add_clips_from_paths(self, paths: list):
        existing = {it["path"] for it in self._queue}
        added = 0
        for p in paths or []:
            if p and os.path.isfile(p) and p not in existing:
                self._queue.append({"path": p, "status": "pending", "out": ""})
                existing.add(p)
                added += 1
        if added:
            self._refresh_queue()
        return added

    def _on_import_library(self):
        if not self._library_provider:
            self._status.setText(translate("Vidéothèque indisponible."))
            return
        try:
            paths = list(self._library_provider() or [])
        except Exception:
            paths = []
        n = self.add_clips_from_paths(paths)
        self._status.setText(
            f"{n} " + translate("clip(s) importé(s) depuis la Vidéothèque."))

    def _on_add_files(self):
        paths, _ = QFileDialog.getOpenFileNames(
            self, translate("Ajouter des clips"), "",
            "Vidéos (*.mp4 *.mov *.webm *.m4v *.gif);;Tous les fichiers (*)")
        if paths:
            self.add_clips_from_paths(paths)

    def _on_clear(self):
        if self._proc_running:
            return
        self._queue.clear()
        self._refresh_queue()

    # ── File d'attente (rendu) ────────────────────────────────────────────────

    def _refresh_queue(self):
        while self._queue_box.count():
            item = self._queue_box.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self._empty_lbl.setVisible(not self._queue)
        for i, it in enumerate(self._queue):
            self._queue_box.addWidget(self._make_queue_row(i, it))
        n = len(self._queue)
        self._btn_run.setText("▶  " + translate("Upscaler toute la file")
                              + (f"  ({n})" if n else ""))
        self._btn_run.setEnabled(bool(n) and not self._proc_running)

    def _make_queue_row(self, index: int, it: dict) -> QWidget:
        row = QWidget()
        row.setStyleSheet(
            f"background:{C['bg2']};border:1px solid {C['border']};border-radius:6px;")
        rl = QHBoxLayout(row)
        rl.setContentsMargins(10, 5, 8, 5)
        rl.setSpacing(8)
        st = it["status"]
        badge = {"pending": "•", "done": "✓", "error": "✗"}.get(st, "•")
        bcol  = {"pending": C["text_dim"], "done": C["accent"], "error": C["red"]}.get(st, C["text_dim"])
        bl = QLabel(badge)
        bl.setFixedWidth(14)
        bl.setStyleSheet(f"color:{bcol};font-size:12px;font-weight:800;background:transparent;border:none;")
        rl.addWidget(bl)
        name = QLabel(os.path.basename(it["path"]))
        name.setStyleSheet(
            f"color:{C['text_primary']};font-size:10px;background:transparent;border:none;")
        rl.addWidget(name, 1)
        if st == "done" and it.get("out"):
            btn = QPushButton(translate("Lire"))
            btn.setFixedHeight(24)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setStyleSheet(
                f"QPushButton{{background:transparent;color:{C['accent']};"
                f"border:1px solid {C['accent_dim']};border-radius:5px;font-size:9px;"
                f"font-weight:700;padding:0 10px;}}"
                f"QPushButton:hover{{background:rgba(78,205,196,0.10);}}")
            btn.clicked.connect(lambda checked=False, p=it["out"]:
                                QDesktopServices.openUrl(QUrl.fromLocalFile(p)))
            rl.addWidget(btn)
        if not self._proc_running:
            rm = QPushButton("✕")
            rm.setFixedSize(20, 20)
            rm.setCursor(Qt.CursorShape.PointingHandCursor)
            rm.setStyleSheet(
                f"QPushButton{{background:{C['bg3']};color:{C['text_secondary']};"
                f"border:1px solid {C['border']};border-radius:3px;font-size:9px;font-weight:700;}}"
                f"QPushButton:hover{{background:{C['red']};color:#fff;border-color:{C['red']};}}")
            rm.clicked.connect(lambda checked=False, i=index: self._remove(i))
            rl.addWidget(rm)
        return row

    def _remove(self, index: int):
        if self._proc_running:
            return
        if 0 <= index < len(self._queue):
            self._queue.pop(index)
            self._refresh_queue()

    # ── Réglages ──────────────────────────────────────────────────────────────

    def _on_model_changed(self):
        is_topaz = (self._model_combo.currentData() == "topaz")
        self._topaz_combo.setEnabled(is_topaz)

    # ── Traitement en lot ─────────────────────────────────────────────────────

    def _on_run(self):
        if self._proc_running or not self._queue:
            return
        # ré-arme les éléments non terminés
        for it in self._queue:
            if it["status"] != "done":
                it["status"] = "pending"
        self._proc_running = True
        self._cancelled = False
        self._btn_run.setEnabled(False)
        self._btn_add.setEnabled(False)
        self._btn_import_lib.setEnabled(False)
        self._btn_clear.setEnabled(False)
        self._btn_cancel.setVisible(True)
        self._progress.show()
        self._refresh_queue()
        self._process_next()

    def _on_cancel(self):
        """Arrêt de la file : clip en cours abandonné, restants conservés."""
        if not self._proc_running:
            return
        self._cancelled = True
        if self._worker is not None:
            # ANTI-CRASH : on PARQUE le worker (signaux coupés) — jamais de
            # déréférencement d'un QThread en cours d'exécution.
            from core.worker import abandon_thread
            abandon_thread(self._worker)
            self._worker = None
        self._finish_batch()

    def _process_next(self):
        if getattr(self, "_cancelled", False):
            self._finish_batch()
            return
        nxt = next((i for i, it in enumerate(self._queue)
                    if it["status"] == "pending"), None)
        if nxt is None:
            self._finish_batch()
            return
        self._proc_index = nxt
        it = self._queue[nxt]
        done = sum(1 for x in self._queue if x["status"] == "done")
        total = len(self._queue)
        self._status.setText(
            f"[{done + 1}/{total}] {os.path.basename(it['path'])} …")
        from api.upscale import UpscaleVideoWorker
        self._worker = UpscaleVideoWorker(
            it["path"],
            model=self._model_combo.currentData() or "topaz",
            upscale_factor=int(self._factor_combo.currentData() or 2),
            topaz_model=self._topaz_combo.currentData() or "Proteus",
            label=os.path.splitext(os.path.basename(it["path"]))[0] + "_up",
        )
        self._worker.progress.connect(self._on_progress)
        self._worker.finished.connect(self._on_item_finished)
        self._worker.failed.connect(self._on_item_failed)
        self._worker.start()

    def _on_progress(self, pct: int, msg: str):
        self._progress.setValue(pct)

    def _on_item_finished(self, path: str):
        it = self._queue[self._proc_index]
        if path:
            it["status"] = "done"
            it["out"] = path
            self._last_folder = os.path.dirname(path)
            self._btn_open.setEnabled(True)
            self.generation_done.emit(path)
        else:
            # mode mock (aucune clé) — on marque terminé sans fichier
            it["status"] = "done"
        self._refresh_queue()
        self._process_next()

    def _on_item_failed(self, err: str):
        it = self._queue[self._proc_index]
        it["status"] = "error"
        self._status.setText(f"✗  {err[:100]}")
        self._refresh_queue()
        self._process_next()

    def _finish_batch(self):
        self._proc_running = False
        self._btn_cancel.setVisible(False)
        self._btn_add.setEnabled(True)
        self._btn_import_lib.setEnabled(True)
        self._btn_clear.setEnabled(True)
        ok  = sum(1 for it in self._queue if it["status"] == "done")
        err = sum(1 for it in self._queue if it["status"] == "error")
        if getattr(self, "_cancelled", False):
            rest = sum(1 for it in self._queue if it["status"] == "pending")
            self._progress.hide()
            self._status.setText(
                "■  " + translate("File annulée") + f" — {ok} "
                + translate("upscalé(s)") + f", {rest} " + translate("en attente"))
        else:
            self._progress.setValue(100)
            self._status.setText(
                f"✓  {ok} " + translate("upscalé(s)")
                + (f"  ·  {err} " + translate("erreur(s)") if err else ""))
        self._refresh_queue()

    def _on_open_folder(self):
        if self._last_folder and os.path.isdir(self._last_folder):
            try:
                os.startfile(self._last_folder)
            except AttributeError:
                import subprocess
                subprocess.Popen(["xdg-open", self._last_folder])

    def retranslate(self):
        pass
