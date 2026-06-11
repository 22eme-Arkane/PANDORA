"""
ui/tab_sound_design_live.py — Onglet Sound Design du Studio IA Live.

Génère le design sonore d'une performance Live/Mapping via Mirelo SFX 1.6 (fal.ai) :
  - Mode « Prompt → SFX »        : un PROMPT SON (texte) → fichier audio (text-to-audio)
  - Mode « Loop → bande-son »    : un loop vidéo + prompt optionnel → vidéo SONORISÉE
                                   et SYNCHRONISÉE (video-to-video)

Les prompts son sont produits par « Mise en page PANDORA » (un PROMPT SON par plan) ;
on peut les coller ici. Composant 100 % Live — n'impacte pas Cinéma.
"""

import os

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QTextEdit,
    QDoubleSpinBox, QProgressBar, QStackedWidget, QScrollArea, QFileDialog, QFrame,
)
from PyQt6.QtCore import Qt, pyqtSignal, QUrl, QThread
from PyQt6.QtGui import QDesktopServices

from ui.styles import C, STYLESHEET
from core.i18n import translate


class _MixWorker(QThread):
    """Exécute la commande ffmpeg de fondu enchaîné en arrière-plan."""
    finished = pyqtSignal(str)
    failed   = pyqtSignal(str)

    def __init__(self, cmd: list, out_path: str):
        super().__init__()
        self._cmd = cmd
        self._out = out_path

    def run(self):
        import subprocess
        try:
            flags = 0x08000000 if os.name == "nt" else 0   # CREATE_NO_WINDOW
            proc = subprocess.run(self._cmd, capture_output=True,
                                  creationflags=flags, timeout=600)
            if proc.returncode != 0 or not os.path.isfile(self._out):
                err = (proc.stderr or b"").decode(errors="replace")[-300:]
                self.failed.emit(f"ffmpeg : {err or 'échec du mixage'}")
                return
            self.finished.emit(self._out)
        except FileNotFoundError:
            self.failed.emit("ffmpeg introuvable — installez-le ou placez ffmpeg.exe "
                             "à la racine de PANDORA.")
        except Exception as e:
            self.failed.emit(str(e)[:200])


class TabSoundDesignLive(QWidget):
    """Sound design Live via Mirelo SFX 1.6 (texte→audio + vidéo→bande-son synchronisée)."""

    generation_done = pyqtSignal(str)   # chemin du fichier généré

    def __init__(self):
        super().__init__()
        self.setStyleSheet(STYLESHEET)
        self._mode = "text"          # "text" | "video"
        self._video_path = ""
        self._worker = None

        root = QVBoxLayout(self)
        root.setContentsMargins(28, 22, 28, 22)
        root.setSpacing(14)

        # ── En-tête ───────────────────────────────────────────────────────────
        title = QLabel("♫  " + translate("Sound Design — Mirelo SFX"))
        title.setStyleSheet(
            f"color:{C['text_primary']};font-size:18px;font-weight:800;"
            f"letter-spacing:1px;background:transparent;border:none;")
        root.addWidget(title)

        sub = QLabel(translate(
            "Sonorise ta performance : un prompt son → SFX, ou un loop vidéo → bande-son "
            "synchronisée. Colle ici les PROMPT SON générés par « Mise en page PANDORA »."))
        sub.setWordWrap(True)
        sub.setStyleSheet(
            f"color:{C['text_dim']};font-size:11px;background:transparent;border:none;")
        root.addWidget(sub)

        # ── Depuis les Séquences EN HAUT (même logique que Générer depuis
        #    Séquences : sélecteur Live/Mapping + Conducteur visuel des plans)
        self._sfx_queue: list[dict] = []     # {number, title, prompt, duration, status, out}
        self._sfx_running = False
        self._seq_mode = "live"

        _seq_title = QLabel(translate("Depuis les Séquences — file d'attente"))
        _seq_title.setStyleSheet(
            f"color:{C['accent']};font-size:12px;font-weight:800;"
            f"letter-spacing:0.5px;background:transparent;border:none;")
        root.addWidget(_seq_title)

        seq_row = QHBoxLayout()
        seq_row.setSpacing(8)
        self._btn_seq_live    = self._make_seq_btn(translate("Séquences Live"), "live")
        self._btn_seq_mapping = self._make_seq_btn(translate("Séquences Mapping"), "mapping")
        seq_row.addWidget(self._btn_seq_live)
        seq_row.addWidget(self._btn_seq_mapping)
        self._btn_load_plans = QPushButton("⟳  " + translate("Charger les plans"))
        self._btn_load_plans.setFixedHeight(30)
        self._btn_load_plans.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_load_plans.setToolTip(translate(
            "Charge les plans en file d'attente — la sélection du Conducteur\n"
            "si tu en as une (Ctrl+clic = multi), sinon toute la séquence."))
        self._btn_load_plans.setStyleSheet(
            f"QPushButton{{background:transparent;color:{C['text_secondary']};"
            f"border:1px solid {C['border']};border-radius:7px;font-size:11px;"
            f"font-weight:600;padding:0 12px;}}"
            f"QPushButton:hover{{color:{C['text_primary']};border-color:{C['border_bright']};}}")
        self._btn_load_plans.clicked.connect(self._load_seq_plans)
        seq_row.addWidget(self._btn_load_plans)
        seq_row.addStretch()
        root.addLayout(seq_row)

        # Conducteur visuel (vignettes des plans) — même composant que
        # « Générer depuis Séquences » ; suit le sélecteur Live/Mapping.
        from ui.tab_t2v_live import StoryboardSelector
        self._storyboard = StoryboardSelector()
        root.addWidget(self._storyboard)
        self._apply_seq_btn_style()
        self._set_seq_source(self._seq_mode)

        self._queue_box = QVBoxLayout()
        self._queue_box.setSpacing(5)
        root.addLayout(self._queue_box)

        # ── RENDU : options de sortie de la file ──────────────────────────────
        rendu_lbl = QLabel(translate("RENDU"))
        rendu_lbl.setStyleSheet(
            f"color:{C['text_dim']};font-size:9px;font-weight:700;letter-spacing:2px;"
            f"background:transparent;border:none;")
        root.addWidget(rendu_lbl)
        from PyQt6.QtWidgets import QCheckBox
        self._auto_mix_cb = QCheckBox(translate(
            "Exporter la bande-son fondue (1s) à la fin de la file"))
        self._auto_mix_cb.setChecked(True)
        self._auto_mix_cb.setToolTip(translate(
            "Concatène les SFX générés en UNE bande-son continue avec fondu enchaîné "
            "entre les plans (pas de coupes nettes) — ffmpeg acrossfade."))
        self._auto_mix_cb.setStyleSheet(
            f"QCheckBox{{color:{C['text_secondary']};font-size:10px;background:transparent;}}")
        root.addWidget(self._auto_mix_cb)

        run_row = QHBoxLayout()
        run_row.setSpacing(8)
        self._btn_cancel_queue = QPushButton("■  " + translate("Annuler la file"))
        self._btn_cancel_queue.setFixedHeight(38)
        self._btn_cancel_queue.setVisible(False)
        self._btn_cancel_queue.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_cancel_queue.setToolTip(translate(
            "Arrête la file : le plan en cours est abandonné,\n"
            "les plans restants sont conservés en attente."))
        self._btn_cancel_queue.setStyleSheet(
            f"QPushButton{{background:{C['bg3']};color:{C['red']};"
            f"border:1px solid {C['red']};border-radius:8px;font-size:11px;"
            f"font-weight:700;padding:0 14px;}}"
            f"QPushButton:hover{{background:rgba(255,79,106,0.12);}}")
        self._btn_cancel_queue.clicked.connect(self._on_cancel_queue)
        run_row.addWidget(self._btn_cancel_queue)
        run_row.addStretch()
        root.addLayout(run_row)

        # ── Génération manuelle (un prompt / un loop) ─────────────────────────
        _sep = QFrame()
        _sep.setFixedHeight(1)
        _sep.setStyleSheet(f"background:{C['border']};")
        root.addWidget(_sep)

        mode_row = QHBoxLayout()
        mode_row.setSpacing(0)
        self._btn_mode_text  = self._make_mode_btn(translate("Prompt → SFX"), "text")
        self._btn_mode_video = self._make_mode_btn(translate("Loop vidéo → bande-son"), "video")
        mode_row.addWidget(self._btn_mode_text)
        mode_row.addWidget(self._btn_mode_video)
        mode_row.addStretch()
        root.addLayout(mode_row)

        self._stack = QStackedWidget()
        self._stack.addWidget(self._build_text_panel())
        self._stack.addWidget(self._build_video_panel())
        root.addWidget(self._stack)

        # ── Barre de génération (UNIQUE : file si chargée, sinon manuel) ─────
        self._btn_generate = QPushButton(translate("⚡  Générer le son"))
        self._btn_generate.setFixedHeight(44)
        self._btn_generate.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_generate.setStyleSheet(
            f"QPushButton{{background:{C['accent']};color:#07080f;border:none;"
            f"border-radius:9px;font-size:13px;font-weight:800;letter-spacing:0.5px;}}"
            f"QPushButton:hover{{background:#6eded6;}}"
            f"QPushButton:disabled{{background:{C['bg3']};color:{C['text_dim']};}}")
        self._btn_generate.clicked.connect(self._on_generate)
        root.addWidget(self._btn_generate)

        self._progress = QProgressBar()
        self._progress.setRange(0, 100)
        self._progress.setValue(0)
        self._progress.setTextVisible(False)
        self._progress.setFixedHeight(4)
        self._progress.setVisible(False)
        self._progress.setStyleSheet(
            f"QProgressBar{{background:{C['bg2']};border:none;border-radius:2px;}}"
            f"QProgressBar::chunk{{background:{C['accent']};border-radius:2px;}}")
        root.addWidget(self._progress)

        self._status = QLabel("")
        self._status.setStyleSheet(
            f"color:{C['text_secondary']};font-size:10px;background:transparent;border:none;")
        root.addWidget(self._status)

        # ── Résultats ─────────────────────────────────────────────────────────
        res_lbl = QLabel(translate("Fichiers générés"))
        res_lbl.setStyleSheet(
            f"color:{C['text_dim']};font-size:9px;font-weight:700;letter-spacing:1px;"
            f"background:transparent;border:none;")
        root.addWidget(res_lbl)

        _scroll = QScrollArea()
        _scroll.setWidgetResizable(True)
        _scroll.setStyleSheet("QScrollArea{border:none;background:transparent;}")
        self._results_w = QWidget()
        self._results_w.setStyleSheet("background:transparent;")
        self._results_lay = QVBoxLayout(self._results_w)
        self._results_lay.setContentsMargins(0, 0, 0, 0)
        self._results_lay.setSpacing(6)
        self._results_lay.addStretch()
        _scroll.setWidget(self._results_w)
        root.addWidget(_scroll, 1)

        self._set_mode("text")

    # ── Construction des panneaux ─────────────────────────────────────────────

    def _make_mode_btn(self, label: str, key: str) -> QPushButton:
        btn = QPushButton(label)
        btn.setCheckable(True)
        btn.setFixedHeight(34)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.clicked.connect(lambda checked=False, k=key: self._set_mode(k))
        return btn

    def _apply_mode_style(self):
        for btn, key in ((self._btn_mode_text, "text"), (self._btn_mode_video, "video")):
            active = (key == self._mode)
            if active:
                btn.setStyleSheet(
                    f"QPushButton{{background:rgba(78,205,196,0.16);color:{C['accent']};"
                    f"border:1px solid {C['accent']};border-radius:7px;"
                    f"font-size:11px;font-weight:700;padding:0 16px;}}")
            else:
                btn.setStyleSheet(
                    f"QPushButton{{background:transparent;color:{C['text_secondary']};"
                    f"border:1px solid {C['border']};border-radius:7px;"
                    f"font-size:11px;font-weight:600;padding:0 16px;}}"
                    f"QPushButton:hover{{color:{C['text_primary']};border-color:{C['border_bright']};}}")
            btn.setChecked(active)

    def _set_mode(self, key: str):
        self._mode = key if key in ("text", "video") else "text"
        self._stack.setCurrentIndex(0 if self._mode == "text" else 1)
        self._apply_mode_style()

    def _build_text_panel(self) -> QWidget:
        w = QWidget()
        w.setStyleSheet("background:transparent;")
        lay = QVBoxLayout(w)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(8)

        self._txt_prompt = QTextEdit()
        self._txt_prompt.setPlaceholderText(translate(
            "Décris l'ambiance / les effets sonores (en anglais de préférence). "
            "Ex. « deep pulsing bass drone, glitchy risers, crowd energy, no vocals »"))
        self._txt_prompt.setFixedHeight(120)
        self._txt_prompt.setStyleSheet(
            f"QTextEdit{{background:{C['bg2']};color:{C['text_primary']};"
            f"border:1px solid {C['border']};border-radius:8px;padding:10px;font-size:12px;}}")
        lay.addWidget(self._txt_prompt)

        lay.addLayout(self._build_duration_row("text"))
        return w

    def _build_video_panel(self) -> QWidget:
        w = QWidget()
        w.setStyleSheet("background:transparent;")
        lay = QVBoxLayout(w)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(8)

        pick_row = QHBoxLayout()
        pick_row.setSpacing(8)
        self._btn_pick = QPushButton(translate("📁  Choisir un loop vidéo…"))
        self._btn_pick.setFixedHeight(38)
        self._btn_pick.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_pick.setStyleSheet(
            f"QPushButton{{background:{C['bg2']};color:{C['text_primary']};"
            f"border:1px solid {C['border']};border-radius:8px;font-size:11px;font-weight:700;padding:0 14px;}}"
            f"QPushButton:hover{{background:{C['bg3']};border-color:{C['border_bright']};}}")
        self._btn_pick.clicked.connect(self._on_pick_video)
        pick_row.addWidget(self._btn_pick)
        self._lbl_video = QLabel(translate("Aucun loop sélectionné"))
        self._lbl_video.setStyleSheet(
            f"color:{C['text_dim']};font-size:10px;background:transparent;border:none;")
        pick_row.addWidget(self._lbl_video, 1)
        lay.addLayout(pick_row)

        self._txt_prompt_video = QTextEdit()
        self._txt_prompt_video.setPlaceholderText(translate(
            "Prompt son optionnel (anglais) pour orienter la bande-son. "
            "Laisse vide pour une sonorisation automatique du loop."))
        self._txt_prompt_video.setFixedHeight(80)
        self._txt_prompt_video.setStyleSheet(
            f"QTextEdit{{background:{C['bg2']};color:{C['text_primary']};"
            f"border:1px solid {C['border']};border-radius:8px;padding:10px;font-size:12px;}}")
        lay.addWidget(self._txt_prompt_video)

        lay.addLayout(self._build_duration_row("video"))
        return w

    def _build_duration_row(self, which: str):
        row = QHBoxLayout()
        row.setSpacing(8)
        lbl = QLabel(translate("Durée"))
        lbl.setStyleSheet(
            f"color:{C['text_secondary']};font-size:11px;background:transparent;border:none;")
        spin = QDoubleSpinBox()
        spin.setRange(1.0, 60.0)
        spin.setDecimals(0)
        spin.setValue(10)
        spin.setSuffix(" s")
        spin.setStyleSheet(
            f"QDoubleSpinBox{{background:{C['bg2']};color:{C['text_primary']};"
            f"border:1px solid {C['border']};border-radius:6px;padding:5px 8px;font-size:12px;}}")
        row.addWidget(lbl)
        row.addWidget(spin)
        row.addStretch()
        if which == "text":
            self._dur_text = spin
        else:
            self._dur_video = spin
        return row

    # ── Génération ────────────────────────────────────────────────────────────

    def open_with_prompt(self, prompt: str, duration: float = 10.0):
        """Pré-remplit le mode « Prompt → SFX » depuis un plan de séquence
        (sound_prompt + durée du plan) — bouton « ➤ SFX » du tableau Séquences."""
        self._set_mode("text")
        self._txt_prompt.setPlainText(prompt or "")
        try:
            self._dur_text.setValue(max(1.0, min(60.0, float(duration or 10.0))))
        except (TypeError, ValueError):
            pass

    # ── File d'attente depuis les Séquences ──────────────────────────────────

    def _make_seq_btn(self, label: str, key: str) -> QPushButton:
        b = QPushButton(label)
        b.setCheckable(True)
        b.setFixedHeight(30)
        b.setCursor(Qt.CursorShape.PointingHandCursor)
        b.clicked.connect(lambda checked=False, k=key: self._set_seq_source(k))
        return b

    def _apply_seq_btn_style(self):
        for b, k in ((self._btn_seq_live, "live"), (self._btn_seq_mapping, "mapping")):
            active = (self._seq_mode == k)
            b.setChecked(active)
            b.setStyleSheet(
                f"QPushButton{{background:{'rgba(78,205,196,0.16)' if active else 'transparent'};"
                f"color:{C['accent'] if active else C['text_secondary']};"
                f"border:1px solid {C['accent'] if active else C['border']};"
                f"border-radius:7px;font-size:11px;font-weight:700;padding:0 14px;}}"
                f"QPushButton:hover{{border-color:{C['accent']};}}")

    def _set_seq_source(self, mode: str):
        self._seq_mode = mode if mode in ("live", "mapping") else "live"
        self._apply_seq_btn_style()
        # Le Conducteur visuel suit la séquence choisie (comme Générer depuis Séq.)
        import core.storyboard as sb
        sb.set_namespace(f"live_seq_{self._seq_mode}")
        if hasattr(self, "_storyboard"):
            self._storyboard.refresh()

    def _load_seq_plans(self):
        # Sélection du Conducteur si présente (Ctrl+clic = multi), sinon toute la séquence
        shots = self._storyboard.get_selected_shots() if hasattr(self, "_storyboard") else []
        if not shots:
            import core.storyboard as sb
            prev_ns = sb.get_namespace()
            try:
                sb.set_namespace(f"live_seq_{self._seq_mode}")
                shots = sb.list_shots()
            finally:
                sb.set_namespace(prev_ns)

        def _num(s):
            try:
                return int(s.get("number") or 0)
            except (TypeError, ValueError):
                return 0

        self._sfx_queue = []
        for s in sorted(shots, key=_num):
            prompt = (s.get("sound_prompt", "") or "").strip()
            if not prompt:
                continue
            try:
                dur = float(s.get("duration", 5.0) or 5.0)
            except (TypeError, ValueError):
                dur = 5.0
            self._sfx_queue.append({
                "number":   s.get("number", 0),
                "title":    s.get("scene_title", "") or "",
                "prompt":   prompt,
                "duration": max(1.0, min(60.0, dur)),
                "status":   "pending",
                "out":      "",
            })
        self._refresh_sfx_queue()
        if not self._sfx_queue:
            self._status.setText(translate(
                "Aucun plan avec prompt son dans cette séquence — génère le découpage "
                "ou renseigne les champs 🔊 Son."))
        else:
            self._status.setText(
                f"{len(self._sfx_queue)} {translate('plan(s) chargé(s) — prêt à générer.')}")

    def _refresh_sfx_queue(self):
        while self._queue_box.count():
            it = self._queue_box.takeAt(0)
            if it.widget():
                it.widget().deleteLater()
        for i, it in enumerate(self._sfx_queue):
            self._queue_box.addWidget(self._make_sfx_row(i, it))
        # Bouton UNIQUE : « Générer la file (N) » si une file est chargée,
        # sinon « Générer le son » (mode manuel)
        n_pending = sum(1 for x in self._sfx_queue if x["status"] == "pending")
        if n_pending:
            self._btn_generate.setText(
                "⚡  " + translate("Générer la file") + f"  ({n_pending})")
        else:
            self._btn_generate.setText("⚡  " + translate("Générer le son"))

    def _make_sfx_row(self, index: int, it: dict) -> QWidget:
        row = QWidget()
        row.setStyleSheet(
            f"background:{C['bg2']};border:1px solid {C['border']};border-radius:6px;")
        rl = QHBoxLayout(row)
        rl.setContentsMargins(10, 5, 8, 5)
        rl.setSpacing(8)
        badge = {"pending": "•", "running": "⟳", "done": "✓", "error": "✗"}.get(it["status"], "•")
        bcol  = {"pending": C["text_dim"], "running": C["accent"],
                 "done": C["accent"], "error": C["red"]}.get(it["status"], C["text_dim"])
        bl = QLabel(badge)
        bl.setFixedWidth(14)
        bl.setStyleSheet(f"color:{bcol};font-size:12px;font-weight:800;"
                         "background:transparent;border:none;")
        rl.addWidget(bl)
        _p = it["prompt"]
        name = QLabel(f"Plan {it['number']} · {it['duration']:.1f}s — "
                      + (_p[:70] + "…" if len(_p) > 70 else _p))
        name.setToolTip(_p)
        name.setStyleSheet(
            f"color:{C['text_primary']};font-size:10px;background:transparent;border:none;")
        rl.addWidget(name, 1)
        if not self._sfx_running:
            rm = QPushButton("✕")
            rm.setFixedSize(20, 20)
            rm.setCursor(Qt.CursorShape.PointingHandCursor)
            rm.setStyleSheet(
                f"QPushButton{{background:{C['bg3']};color:{C['text_secondary']};"
                f"border:1px solid {C['border']};border-radius:3px;font-size:9px;font-weight:700;}}"
                f"QPushButton:hover{{background:{C['red']};color:#fff;border-color:{C['red']};}}")
            rm.clicked.connect(lambda checked=False, i=index: self._remove_sfx(i))
            rl.addWidget(rm)
        return row

    def _remove_sfx(self, index: int):
        if self._sfx_running:
            return
        if 0 <= index < len(self._sfx_queue):
            self._sfx_queue.pop(index)
            self._refresh_sfx_queue()

    def _sfx_out_dir(self) -> str:
        from core.context import get_data_root
        d = os.path.join(get_data_root(), "live_sound_design")
        os.makedirs(d, exist_ok=True)
        return d

    def _on_run_queue(self):
        if self._sfx_running or not self._sfx_queue:
            return
        for it in self._sfx_queue:
            if it["status"] != "done":
                it["status"] = "pending"
        self._sfx_running = True
        self._sfx_cancelled = False
        self._btn_load_plans.setEnabled(False)
        self._btn_cancel_queue.setVisible(True)
        self._set_busy(True)
        self._refresh_sfx_queue()
        self._process_next_sfx()

    def _on_cancel_queue(self):
        """Arrêt de la file : plan en cours abandonné, restants conservés."""
        if not self._sfx_running:
            return
        self._sfx_cancelled = True
        if getattr(self, "_queue_worker", None) is not None:
            # ANTI-CRASH : worker PARQUÉ (signaux coupés) — jamais déréférencé à chaud
            from core.worker import abandon_thread
            abandon_thread(self._queue_worker)
            self._queue_worker = None
        # Le plan interrompu repasse en attente (relançable tel quel)
        if 0 <= getattr(self, "_sfx_idx", -1) < len(self._sfx_queue):
            it = self._sfx_queue[self._sfx_idx]
            if it["status"] == "running":
                it["status"] = "pending"
        self._finish_sfx_queue()

    def _process_next_sfx(self):
        if getattr(self, "_sfx_cancelled", False):
            self._finish_sfx_queue()
            return
        nxt = next((i for i, it in enumerate(self._sfx_queue)
                    if it["status"] == "pending"), None)
        if nxt is None:
            self._finish_sfx_queue()
            return
        self._sfx_idx = nxt
        it = self._sfx_queue[nxt]
        it["status"] = "running"
        self._refresh_sfx_queue()
        done = sum(1 for x in self._sfx_queue if x["status"] == "done")
        self._status.setText(f"[{done + 1}/{len(self._sfx_queue)}] Plan {it['number']} …")
        from api.tts import SFX1Worker
        self._queue_worker = SFX1Worker(
            it["prompt"], it["duration"],
            label=f"plan{it['number']}_sfx", out_dir=self._sfx_out_dir())
        self._queue_worker.progress.connect(self._on_progress)
        self._queue_worker.finished.connect(self._on_sfx_item_done)
        self._queue_worker.failed.connect(self._on_sfx_item_failed)
        self._queue_worker.start()

    def _on_sfx_item_done(self, path: str):
        it = self._sfx_queue[self._sfx_idx]
        it["status"] = "done"
        it["out"] = path or ""
        if path:
            self._add_result(path)
            self.generation_done.emit(path)
        self._refresh_sfx_queue()
        self._process_next_sfx()

    def _on_sfx_item_failed(self, msg: str):
        it = self._sfx_queue[self._sfx_idx]
        it["status"] = "error"
        self._status.setText(f"✗  Plan {it['number']} : {msg[:90]}")
        self._refresh_sfx_queue()
        self._process_next_sfx()

    def _finish_sfx_queue(self):
        self._sfx_running = False
        self._set_busy(False)
        self._btn_load_plans.setEnabled(True)
        self._btn_cancel_queue.setVisible(False)
        ok  = sum(1 for it in self._sfx_queue if it["status"] == "done")
        err = sum(1 for it in self._sfx_queue if it["status"] == "error")
        if getattr(self, "_sfx_cancelled", False):
            rest = sum(1 for it in self._sfx_queue if it["status"] == "pending")
            self._status.setText(
                "■  " + translate("File annulée") + f" — {ok} "
                + translate("ambiance(s) générée(s)") + f", {rest} "
                + translate("en attente"))
        else:
            self._status.setText(
                f"✓  {ok} {translate('ambiance(s) générée(s)')}"
                + (f"  ·  {err} {translate('erreur(s)')}" if err else ""))
        self._refresh_sfx_queue()
        # RENDU : export automatique de la bande-son fondue (option cochée)
        n_done = sum(1 for it in self._sfx_queue
                     if it["status"] == "done" and it["out"])
        if (not getattr(self, "_sfx_cancelled", False) and n_done >= 2
                and self._auto_mix_cb.isChecked()):
            self._on_export_mix()

    # ── Bande-son continue (fondu enchaîné entre les plans) ───────────────────

    @staticmethod
    def _build_crossfade_cmd(ffmpeg: str, ins: list, out: str,
                             fade_s: float = 1.0) -> list:
        """Commande ffmpeg : enchaîne N fichiers audio avec acrossfade (pas de
        coupes nettes). Pure (testable) — N ≥ 2."""
        cmd = [ffmpeg, "-y"]
        for p in ins:
            cmd += ["-i", p]
        parts, prev = [], "0:a"
        for i in range(1, len(ins)):
            label = f"a{i}"
            parts.append(f"[{prev}][{i}:a]acrossfade=d={fade_s}:c1=tri:c2=tri[{label}]")
            prev = label
        cmd += ["-filter_complex", ";".join(parts), "-map", f"[{prev}]", out]
        return cmd

    def _on_export_mix(self):
        import time as _time
        ins = [it["out"] for it in self._sfx_queue
               if it["status"] == "done" and it["out"] and os.path.isfile(it["out"])]
        if len(ins) < 2:
            self._status.setText(translate("Il faut au moins 2 ambiances générées."))
            return
        try:
            from core.video_utils import get_ffmpeg_exe
            ff = get_ffmpeg_exe()
        except Exception:
            ff = "ffmpeg"
        out = os.path.join(self._sfx_out_dir(), f"bande_son_{int(_time.time())}.wav")
        cmd = self._build_crossfade_cmd(ff, ins, out)
        self._status.setText(translate("Mixage de la bande-son (fondu enchaîné)…"))
        self._mix_worker = _MixWorker(cmd, out)
        self._mix_worker.finished.connect(self._on_mix_done)
        self._mix_worker.failed.connect(self._on_mix_failed)
        self._mix_worker.start()

    def _on_mix_done(self, path: str):
        self._status.setText(translate("Bande-son continue exportée ✓"))
        self._add_result(path)
        self.generation_done.emit(path)

    def _on_mix_failed(self, msg: str):
        self._status.setText(f"✗  {msg[:120]}")

    def _on_pick_video(self):
        path, _ = QFileDialog.getOpenFileName(
            self, translate("Choisir un loop vidéo"), "",
            "Vidéos (*.mp4 *.mov *.webm *.m4v *.gif);;Tous les fichiers (*)")
        if path:
            self._video_path = path
            self._lbl_video.setText(os.path.basename(path))
            self._lbl_video.setStyleSheet(
                f"color:{C['text_secondary']};font-size:10px;background:transparent;border:none;")

    def _on_generate(self):
        # Bouton UNIQUE : une file chargée se génère en priorité ; sans file,
        # c'est la génération manuelle (prompt ou loop vidéo).
        if any(x["status"] == "pending" for x in self._sfx_queue):
            self._on_run_queue()
            return
        if self._mode == "text":
            prompt = self._txt_prompt.toPlainText().strip()
            if not prompt:
                self._status.setText(translate("Écris d'abord un prompt son."))
                return
            from api.tts import SFX1Worker
            self._worker = SFX1Worker(prompt, float(self._dur_text.value()), label="live_sfx")
        else:
            if not self._video_path or not os.path.isfile(self._video_path):
                self._status.setText(translate("Choisis d'abord un loop vidéo."))
                return
            from api.tts import SFX1VideoWorker
            self._worker = SFX1VideoWorker(
                self._video_path, self._txt_prompt_video.toPlainText().strip(),
                float(self._dur_video.value()), label="live_sfx_video")

        self._set_busy(True)
        self._worker.progress.connect(self._on_progress)
        self._worker.finished.connect(self._on_finished)
        self._worker.failed.connect(self._on_failed)
        self._worker.start()

    def _set_busy(self, busy: bool):
        self._btn_generate.setEnabled(not busy)
        self._progress.setVisible(busy)
        if busy:
            self._progress.setValue(0)

    def _on_progress(self, pct: int, msg: str):
        self._progress.setValue(pct)
        self._status.setText(msg)

    def _on_finished(self, path: str):
        self._set_busy(False)
        if not path:
            self._status.setText(translate("Mode mock — renseigne la clé fal.ai dans Paramètres."))
            return
        self._status.setText(translate("Généré ✓"))
        self._add_result(path)
        self.generation_done.emit(path)

    def _on_failed(self, msg: str):
        self._set_busy(False)
        self._status.setText(msg)

    def _add_result(self, path: str):
        row = QWidget()
        row.setStyleSheet(
            f"background:{C['bg2']};border:1px solid {C['border']};border-radius:7px;")
        rl = QHBoxLayout(row)
        rl.setContentsMargins(10, 6, 8, 6)
        rl.setSpacing(8)
        is_video = path.lower().endswith((".mp4", ".mov", ".webm", ".m4v", ".gif"))
        name = QLabel(("🎬 " if is_video else "🔊 ") + os.path.basename(path))
        name.setStyleSheet(
            f"color:{C['text_primary']};font-size:10px;background:transparent;border:none;")
        rl.addWidget(name, 1)
        btn_play = QPushButton(translate("Lire"))
        btn_play.setFixedHeight(26)
        btn_play.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_play.setStyleSheet(
            f"QPushButton{{background:transparent;color:{C['accent']};"
            f"border:1px solid {C['accent_dim']};border-radius:5px;"
            f"font-size:10px;font-weight:700;padding:0 12px;}}"
            f"QPushButton:hover{{background:rgba(78,205,196,0.10);}}")
        btn_play.clicked.connect(lambda checked=False, p=path: QDesktopServices.openUrl(QUrl.fromLocalFile(p)))
        rl.addWidget(btn_play)
        # insère en haut (avant le stretch final)
        self._results_lay.insertWidget(0, row)

    def retranslate(self):
        pass
