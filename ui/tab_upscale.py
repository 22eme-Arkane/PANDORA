"""
ui/tab_upscale.py — Onglet « Upscaling » du Studio IA PANDORA | Cinéma.

Porté depuis le Live (ui/tab_upscale_live.py, stabilisé en réel) — copie
ADAPTÉE Cinéma, aucun import de fichier Live :
  - reçoit des clips depuis la Vidéothèque ou un sélecteur de fichiers ;
  - upscale TOUTE la file (ex. tout généré en 480p → ressortir en 1080p/4K) ;
  - moteurs fal.ai : Topaz Video (qualité max) ou SeedVR2 (rapide) ;
  - la sortie garde le MÊME NOM que la source → Relink Media direct DaVinci.
"""

import os

from PyQt6.QtCore import Qt, pyqtSignal, QUrl, QThread
from PyQt6.QtGui import QDesktopServices
from PyQt6.QtWidgets import (
    QScrollArea, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QComboBox, QProgressBar, QFileDialog, QFrame,
)

from ui.styles import C
from ui.widgets import HelpBlock
from core.i18n import translate
from api.upscale import UPSCALE_MODELS, TOPAZ_MODELS
from ui.tab_video_engines import (
    _section, _divider, _combo_style, _btn_accent_style, _btn_ghost_style,
)

_VIDEO_EXTS = (".mp4", ".mov", ".webm", ".m4v", ".gif")


class _MidThumbWorker(QThread):
    """Extrait la frame du MILIEU de chaque clip (ffmpeg) — pas la première :
    les plans ouvrent/ferment souvent au noir. Cache disque partagé."""
    thumb_ready = pyqtSignal(str, str)   # (clip_path, png_path)

    def __init__(self, paths: list):
        super().__init__()
        self._paths = list(paths or [])

    @staticmethod
    def cache_path(path: str) -> str:
        import hashlib
        from core.context import get_data_root
        d = os.path.join(get_data_root(), ".thumbs_mid")
        os.makedirs(d, exist_ok=True)
        try:
            mtime = int(os.path.getmtime(path))
        except OSError:
            mtime = 0
        h = hashlib.md5(f"{path}|{mtime}".encode("utf-8")).hexdigest()[:16]
        return os.path.join(d, f"{h}.png")

    def run(self):
        import subprocess
        try:
            from core.video_utils import get_ffmpeg_exe
            ff = get_ffmpeg_exe()
        except Exception:
            ff = "ffmpeg"
        try:
            from core.video_conform import probe_duration
        except Exception:
            probe_duration = None
        flags = 0x08000000 if os.name == "nt" else 0
        for p in self._paths:
            if self.isInterruptionRequested():
                return
            out = self.cache_path(p)
            if os.path.isfile(out):
                self.thumb_ready.emit(p, out)
                continue
            mid = 0.0
            if probe_duration is not None:
                try:
                    mid = max(0.0, (probe_duration(p) or 0) / 2.0)
                except Exception:
                    mid = 0.0
            cmd = [ff, "-y", "-ss", f"{mid:.2f}", "-i", p,
                   "-frames:v", "1", "-vf", "scale=320:-1", out]
            try:
                subprocess.run(cmd, capture_output=True, creationflags=flags,
                               timeout=30)
            except Exception:
                continue
            if os.path.isfile(out):
                self.thumb_ready.emit(p, out)


class TabUpscale(QScrollArea):
    """Upscaling en lot d'une file de clips (Cinéma)."""

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

        lay.addWidget(HelpBlock(translate("Upscaling de vos clips"), [
            translate("▸ Ajoutez des clips, ou importez toute la Vidéothèque."),
            translate("▸ Choisissez le moteur et le facteur (ex. ×2, ×4)."),
            translate("▸ La sortie garde le MÊME NOM que la source → Relink Media direct dans DaVinci."),
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
        # Bande HORIZONTALE de petits carrés — compact, hauteur BORNÉE
        self._chips_host = QWidget()
        self._chips_host.setStyleSheet("background:transparent;")
        self._chips_box = QHBoxLayout(self._chips_host)
        self._chips_box.setContentsMargins(6, 6, 12, 6)
        self._chips_box.setSpacing(8)
        self._chips_box.setAlignment(
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        self._chips_scroll = QScrollArea()
        self._chips_scroll.setWidget(self._chips_host)
        self._chips_scroll.setWidgetResizable(True)
        self._chips_scroll.setFixedHeight(116)
        self._chips_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._chips_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self._chips_scroll.setStyleSheet(
            f"QScrollArea{{background:rgba(78,205,196,0.04);"
            f"border:1px solid rgba(78,205,196,0.18);border-radius:10px;}}"
            f"QScrollBar:horizontal{{height:4px;background:{C['bg2']};"
            f"border-radius:2px;margin:0;}}"
            f"QScrollBar::handle:horizontal{{background:rgba(78,205,196,0.40);"
            f"border-radius:2px;min-width:30px;}}"
            f"QScrollBar::add-line:horizontal,QScrollBar::sub-line:horizontal{{width:0;}}")
        from ui.widgets import WheelHScroller
        WheelHScroller.attach(self._chips_scroll)
        self._chip_thumbs: dict = {}
        self._chip_thumb_worker = None
        lay.addWidget(self._chips_scroll)

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
        self._btn_run = QPushButton("▶▶  " + translate("Lancer la file d'attente"))
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
        # Toujours actif : ouvre le dossier de DESTINATION même avant de générer
        self._btn_open.setToolTip(translate("Ouvre le dossier de destination des upscales."))
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

    # ── File d'attente (rendu) — petits carrés ────────────────────────────────

    def _refresh_queue(self):
        while self._chips_box.count():
            item = self._chips_box.takeAt(0)
            w = item.widget() if item else None
            if w:
                w.hide()
                w.setParent(None)
                w.deleteLater()
        self._chip_thumbs.clear()
        self._empty_lbl.setVisible(not self._queue)
        self._chips_scroll.setVisible(bool(self._queue))
        for i, it in enumerate(self._queue):
            self._chips_box.addWidget(self._make_chip(i, it))
        self._chips_box.addStretch()
        n = len(self._queue)
        self._btn_run.setText("▶▶  " + translate("Lancer la file d'attente")
                              + (f"  ({n})" if n else ""))
        self._btn_run.setEnabled(bool(n) and not self._proc_running)
        # Vignettes mi-clip (cache disque .thumbs_mid)
        paths = [it["path"] for it in self._queue if os.path.isfile(it["path"])]
        if paths:
            if self._chip_thumb_worker is not None:
                from core.worker import abandon_thread
                abandon_thread(self._chip_thumb_worker)
            self._chip_thumb_worker = _MidThumbWorker(paths)
            self._chip_thumb_worker.thumb_ready.connect(self._on_chip_thumb)
            self._chip_thumb_worker.start()

    def _on_chip_thumb(self, clip_path: str, png_path: str):
        from PyQt6.QtGui import QPixmap
        lbl = self._chip_thumbs.get(clip_path)
        if lbl is None:
            return
        pix = QPixmap(png_path)
        if not pix.isNull():
            lbl.setPixmap(pix.scaled(
                104, 56, Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation))

    def _make_chip(self, index: int, it: dict) -> QWidget:
        st = it["status"]
        border = {"pending": C["border"], "running": C["accent"],
                  "done": C["green"], "error": C["red"]}.get(st, C["border"])
        chip = QFrame()
        chip.setObjectName("upchip")
        chip.setFixedSize(118, 96)
        chip.setStyleSheet(
            f"QFrame#upchip{{background:{C['bg2']};border:2px solid {border};"
            f"border-radius:8px;}}")
        cl = QVBoxLayout(chip)
        cl.setContentsMargins(5, 5, 5, 4)
        cl.setSpacing(3)
        thumb = QLabel("▶")
        thumb.setFixedSize(104, 56)
        thumb.setAlignment(Qt.AlignmentFlag.AlignCenter)
        thumb.setStyleSheet(
            f"background:{C['bg0']};border:none;border-radius:4px;"
            f"color:{C['text_dim']};font-size:9px;")
        cl.addWidget(thumb)
        self._chip_thumbs[it["path"]] = thumb
        base = os.path.basename(it["path"])
        badge = {"pending": "•", "running": "⟳", "done": "✓", "error": "✗"}.get(st, "•")
        name = QLabel(f"{badge} {base[:13]}" + ("…" if len(base) > 13 else ""))
        name.setStyleSheet(
            f"color:{border if st != 'pending' else C['text_secondary']};"
            f"font-size:8px;font-weight:700;background:transparent;border:none;")
        cl.addWidget(name)
        tip = base + f"\n{translate('Statut')} : {st}"
        if st == "error" and it.get("error"):
            tip += f"\n✗ {it['error']}"
        if st == "done" and it.get("out"):
            tip += "\n" + translate("Double-clic : lire le clip upscalé")
        if not self._proc_running:
            tip += "\n" + translate("Clic droit : retirer de la file")
        chip.setToolTip(tip)

        chip.mousePressEvent = lambda e, i=index: (
            self._remove(i) if e.button() == Qt.MouseButton.RightButton else None)
        if st == "done" and it.get("out"):
            chip.mouseDoubleClickEvent = lambda e, p=it["out"]: \
                QDesktopServices.openUrl(QUrl.fromLocalFile(p))
        return chip

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
            # ANTI-CRASH : on PARQUE le worker (signaux coupés)
            from core.worker import abandon_thread
            abandon_thread(self._worker)
            self._worker = None
        for it in self._queue:
            if it["status"] == "running":
                it["status"] = "pending"
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
        it["status"] = "running"
        self._refresh_queue()
        done = sum(1 for x in self._queue if x["status"] == "done")
        total = len(self._queue)
        self._status.setText(
            f"[{done + 1}/{total}] {os.path.basename(it['path'])} …")
        # ANTI-ARRÊT DE CHAÎNE : parquer le worker précédent avant de réassigner
        if getattr(self, "_worker", None) is not None:
            from core.worker import abandon_thread
            abandon_thread(self._worker)
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
            self.generation_done.emit(path)
        else:
            it["status"] = "done"   # mode mock (aucune clé)
        self._refresh_queue()
        self._process_next()

    def _on_item_failed(self, err: str):
        it = self._queue[self._proc_index]
        it["status"] = "error"
        it["error"]  = err[:200]   # visible dans l'info-bulle de la puce
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
        """Ouvre le dossier de destination — disponible AVANT toute génération."""
        folder = self._last_folder if (self._last_folder
                                       and os.path.isdir(self._last_folder)) else ""
        if not folder:
            from api.upscale import _upscale_output_dir
            folder = _upscale_output_dir()
        try:
            os.startfile(folder)
        except AttributeError:
            import subprocess
            subprocess.Popen(["xdg-open", folder])

    def retranslate(self):
        pass
