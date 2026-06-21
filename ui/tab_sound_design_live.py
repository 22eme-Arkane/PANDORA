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
    QComboBox,
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


class TabSoundDesignLive(QScrollArea):
    """Sound design Live via Mirelo SFX 1.6 (texte→audio + vidéo→bande-son synchronisée).

    L'onglet ENTIER est scrollable (comme Générer depuis Séquences) — sinon Qt
    écrase/tronque les sections quand le contenu dépasse la fenêtre (vu en réel)."""

    generation_done = pyqtSignal(str)   # chemin du fichier généré

    def __init__(self):
        super().__init__()
        self.setStyleSheet(STYLESHEET)
        self.setWidgetResizable(True)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setFrameStyle(0)
        self._mode = "text"          # "text" | "video"
        self._video_path = ""
        self._worker = None

        _container = QWidget()
        self.setWidget(_container)
        root = QVBoxLayout(_container)
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
        # Connecté comme dans Générer depuis Séquences : un plan → prompt SON +
        # durée chargés ; plusieurs plans → la file se construit immédiatement.
        self._storyboard.shot_selected.connect(self._on_conductor_shot)
        self._storyboard.shots_selected.connect(self._on_conductor_shots)
        root.addWidget(self._storyboard)
        self._apply_seq_btn_style()
        self._set_seq_source(self._seq_mode)

        # Pas de liste détaillée des plans chargés : la sélection se LIT dans le
        # Conducteur (comme Générer depuis Séquences) et le bouton affiche (N).

        # ── RENDU : même design que « RENDU & AUDIO » de Générer depuis Séq. ──
        from PyQt6.QtWidgets import QCheckBox
        rendu_box = QFrame()
        rendu_box.setObjectName("sd_rendu")
        rendu_box.setStyleSheet(
            f"QFrame#sd_rendu{{background:{C['bg2']};border:1px solid {C['border']};"
            f"border-radius:8px;padding:0px;}}")
        rb_lay = QVBoxLayout(rendu_box)
        rb_lay.setContentsMargins(0, 0, 0, 0)
        rb_lay.setSpacing(1)
        _rendu_header = QWidget()
        _rendu_header.setStyleSheet("background:transparent;border:none;")
        _rh_lay = QHBoxLayout(_rendu_header)
        _rh_lay.setContentsMargins(14, 8, 14, 6)
        _rendu_title = QLabel(translate("RENDU"))
        _rendu_title.setStyleSheet(
            f"color:{C['accent']};font-size:9px;letter-spacing:2px;"
            f"font-family:'Consolas',monospace;font-weight:700;"
            f"background:transparent;border:none;")
        _rh_lay.addWidget(_rendu_title)
        _rh_lay.addStretch()
        rb_lay.addWidget(_rendu_header)

        def _rendu_toggle(title: str, subtitle: str, checked: bool) -> QFrame:
            w = QFrame()
            w.setStyleSheet(
                f"QFrame{{background:transparent;border:none;border-top:1px solid {C['border']};"
                f"border-radius:0px;padding:4px;}}"
                f"QCheckBox{{color:{C['text_secondary']};background:transparent;border:none;}}"
                f"QCheckBox::indicator{{width:16px;height:16px;"
                f"border:1px solid {C['border_bright']};border-radius:4px;background:{C['bg3']};}}"
                f"QCheckBox::indicator:checked{{background:{C['accent']};border-color:{C['accent']};}}"
                f"QCheckBox::indicator:unchecked:hover{{border-color:{C['accent_dim']};}}")
            lw = QHBoxLayout(w)
            lw.setContentsMargins(14, 8, 14, 8)
            col = QVBoxLayout()
            col.setSpacing(2)
            t = QLabel(title)
            t.setStyleSheet(f"color:{C['text_secondary']};font-size:12px;font-weight:600;border:none;")
            col.addWidget(t)
            if subtitle:
                s = QLabel(subtitle)
                s.setWordWrap(True)
                s.setStyleSheet(f"color:{C['text_dim']};font-size:10px;border:none;")
                col.addWidget(s)
            lw.addLayout(col, 1)
            cb = QCheckBox()
            cb.setChecked(checked)
            lw.addWidget(cb)
            return w

        _auto_mix_row = _rendu_toggle(
            translate("Assembler la bande-son (durée exacte)"),
            translate("À la fin de la file : une seule piste CALÉE sur la vidéo — "
                      "chaque plan garde sa durée exacte, micro-fondus aux jonctions "
                      "(pas de coupes nettes, pas de décalage)."),
            True)
        self._auto_mix_cb = _auto_mix_row.findChild(QCheckBox)
        rb_lay.addWidget(_auto_mix_row)
        root.addWidget(rendu_box)

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
        self._btn_generate = QPushButton("▶▶  " + translate("Lancer la file d'attente"))
        self._btn_generate.setFixedHeight(44)
        self._btn_generate.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_generate.setStyleSheet(
            f"QPushButton{{background:{C['accent']};color:#07080f;border:none;"
            f"border-radius:9px;font-size:13px;font-weight:800;letter-spacing:0.5px;}}"
            f"QPushButton:hover{{background:#6eded6;}}"
            f"QPushButton:disabled{{background:{C['bg3']};color:{C['text_dim']};}}")
        self._btn_generate.clicked.connect(self._on_generate)

        # Ordre demandé : barre de progression AU-DESSUS de Générer,
        # « Annuler la file » EN DESSOUS.
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
        root.addWidget(self._btn_generate)

        self._btn_cancel_queue = QPushButton("■  " + translate("Annuler la file"))
        self._btn_cancel_queue.setFixedHeight(34)
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
        root.addWidget(self._btn_cancel_queue)

        self._status = QLabel("")
        self._status.setStyleSheet(
            f"color:{C['text_secondary']};font-size:10px;background:transparent;border:none;")
        root.addWidget(self._status)

        # ── Résultats ─────────────────────────────────────────────────────────
        res_row = QHBoxLayout()
        res_lbl = QLabel(translate("Fichiers générés"))
        res_lbl.setStyleSheet(
            f"color:{C['text_dim']};font-size:9px;font-weight:700;letter-spacing:1px;"
            f"background:transparent;border:none;")
        res_row.addWidget(res_lbl)
        res_row.addStretch()
        root.addLayout(res_row)

        # Toujours actif : ouvre la destination même avant de générer.
        # Style uniforme « ghost » pleine largeur (comme Modifier des clips)
        from ui.tab_video_engines_live import _btn_ghost_style as _bgs
        self._btn_open_dir = QPushButton(translate("Ouvrir le dossier"))
        self._btn_open_dir.setFixedHeight(30)
        self._btn_open_dir.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_open_dir.setToolTip(translate(
            "Ouvre le dossier de destination du sound design."))
        self._btn_open_dir.setStyleSheet(_bgs())
        self._btn_open_dir.clicked.connect(self._on_open_dir)
        root.addWidget(self._btn_open_dir)

        _scroll = QScrollArea()
        _scroll.setWidgetResizable(True)
        _scroll.setMinimumHeight(160)   # jamais écrasé par le reste de l'onglet
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

        eng_row = QHBoxLayout()
        eng_row.setSpacing(8)
        eng_lbl = QLabel(translate("Moteur"))
        eng_lbl.setStyleSheet(
            f"color:{C['text_secondary']};font-size:11px;background:transparent;border:none;")
        self._video_engine_combo = QComboBox()
        self._video_engine_combo.addItem(translate("SFX 1.6 (Mirelo)  ·  bande-son auto"), "sfx16")
        self._video_engine_combo.addItem(translate("Foley Control  ·  SFX synchronisés (~$0.002/s)"), "foley")
        self._video_engine_combo.setStyleSheet(
            f"QComboBox{{background:{C['bg2']};color:{C['text_primary']};"
            f"border:1px solid {C['border']};border-radius:6px;padding:4px 8px;font-size:11px;}}"
            f"QComboBox QAbstractItemView{{background:{C['bg2']};color:{C['text_primary']};"
            f"selection-background-color:{C['accent_dim']};}}")
        eng_row.addWidget(eng_lbl)
        eng_row.addWidget(self._video_engine_combo, 1)
        lay.addLayout(eng_row)

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
        # Sélection du Conducteur si présente (Ctrl/Maj/lasso), sinon toute la séquence
        shots = self._storyboard.get_selected_shots() if hasattr(self, "_storyboard") else []
        if not shots:
            import core.storyboard as sb
            prev_ns = sb.get_namespace()
            try:
                sb.set_namespace(f"live_seq_{self._seq_mode}")
                shots = sb.list_shots()
            finally:
                sb.set_namespace(prev_ns)
        self._build_queue_from_shots(shots)

    def _build_queue_from_shots(self, shots: list):
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

    # ── Conducteur → champs (comme Générer depuis Séquences) ─────────────────

    def _on_conductor_shot(self, shot: dict):
        """Un plan sélectionné → son PROMPT SON et sa DURÉE remplissent le
        panneau manuel ; la file est remise à zéro (le plan prime)."""
        if not shot:
            return
        prompt = (shot.get("sound_prompt", "") or "").strip()
        try:
            dur = float(shot.get("duration", 5.0) or 5.0)
        except (TypeError, ValueError):
            dur = 5.0
        dur = max(1.0, min(60.0, dur))
        self._set_mode("text")
        self._txt_prompt.setPlainText(prompt)
        self._dur_text.setValue(dur)
        self._sfx_queue = []
        self._refresh_sfx_queue()
        n = shot.get("number", "?")
        self._status.setText(
            f"Plan {n} → {dur:g}s · "
            + (translate("prompt son chargé ✓") if prompt
               else translate("⚠ pas de prompt son sur ce plan (champ 🔊 Son)")))

    def _on_conductor_shots(self, shots: list):
        """Multi-sélection (Ctrl/Maj/lasso) → la file se construit aussitôt,
        avec le prompt son et la durée de CHAQUE plan."""
        self._build_queue_from_shots(shots or [])

    def _refresh_sfx_queue(self):
        """Pas de liste détaillée (la sélection se lit dans le Conducteur) —
        seul le bouton reflète la file, harmonisé avec Générer depuis Séquences."""
        n_pending = sum(1 for x in self._sfx_queue if x["status"] == "pending")
        self._btn_generate.setText(
            "▶▶  " + translate("Lancer la file d'attente")
            + (f"  ({n_pending})" if n_pending else ""))

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
        # Le statut montre LE prompt du plan en cours — chaque clip part bien
        # avec SON prompt (retour Matthieu : doute sur un prompt unique)
        _snip = it["prompt"][:60] + ("…" if len(it["prompt"]) > 60 else "")
        self._status.setText(
            f"[{done + 1}/{len(self._sfx_queue)}] Plan {it['number']} "
            f"({it['duration']:g}s) · {_snip}")
        # ANTI-ARRÊT DE CHAÎNE : parquer le worker PRÉCÉDENT avant de réassigner
        # (le réassigner à chaud détruisait un QThread en train de se terminer —
        # la file s'arrêtait après le 1er clip, vu en réel avec 12 plans)
        if getattr(self, "_queue_worker", None) is not None:
            from core.worker import abandon_thread
            abandon_thread(self._queue_worker)
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
        # Conformation à la durée CALÉE du plan (l'API rend une durée approchée) :
        # le clip son se pose tel quel sous sa vidéo, sans recalage manuel
        if path:
            path = self._conform_audio(path, it.get("duration") or 0.0)
        it["out"] = path or ""
        if path:
            self._add_result(path)
            self.generation_done.emit(path)
        self._refresh_sfx_queue()
        self._process_next_sfx()

    def _on_sfx_item_failed(self, msg: str):
        it = self._sfx_queue[self._sfx_idx]
        it["status"] = "error"
        it["error"]  = msg[:200]   # visible dans l'info-bulle de la ligne
        self._status.setText(f"✗  Plan {it['number']} : {msg[:90]}")
        self._refresh_sfx_queue()
        self._process_next_sfx()

    def _on_open_dir(self):
        """Ouvre le dossier de destination — disponible AVANT toute génération."""
        try:
            os.startfile(self._sfx_out_dir())
        except AttributeError:
            import subprocess
            subprocess.Popen(["xdg-open", self._sfx_out_dir()])

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
        # RENDU : export automatique de la bande-son assemblée (option cochée)
        n_done = sum(1 for it in self._sfx_queue
                     if it["status"] == "done" and it["out"])
        if (not getattr(self, "_sfx_cancelled", False) and n_done >= 2
                and self._auto_mix_cb.isChecked()):
            self._on_export_mix()

    # ── Bande-son CALÉE sur la vidéo (durée exacte, sans chevauchement) ───────
    # L'acrossfade CHEVAUCHE les clips : la bande perdait (N-1)×1s et n'était
    # plus alignée avec les clips vidéo posés bout à bout (vu en réel, 12 plans).
    # Doctrine = même principe que la conformation vidéo : chaque ambiance est
    # d'abord conformée à la durée CALÉE de son plan (silence si trop courte,
    # coupe si trop longue), puis concaténée avec des micro-fondus de 50 ms qui
    # ne mangent AUCUNE durée. Total = somme exacte des plans = la timeline.

    @staticmethod
    def _build_conform_cmd(ffmpeg: str, src: str, dst: str, dur: float) -> list:
        """Conforme UN fichier audio à la durée calée du plan. Pure (testable)."""
        return [ffmpeg, "-y", "-i", src,
                "-af", f"apad,atrim=0:{dur:g}", dst]

    @staticmethod
    def _build_assemble_cmd(ffmpeg: str, ins: list, durs: list, out: str,
                            fade_s: float = 0.05) -> list:
        """Commande ffmpeg : concatène N fichiers audio, chacun conformé à SA
        durée calée, micro-fondus aux jonctions SANS chevauchement (la durée
        totale = somme exacte des durées). Pure (testable) — N ≥ 2."""
        cmd = [ffmpeg, "-y"]
        for p in ins:
            cmd += ["-i", p]
        parts = []
        for i, d in enumerate(durs):
            st = max(0.0, d - fade_s)
            parts.append(
                f"[{i}:a]aresample=48000,aformat=channel_layouts=stereo,"
                f"apad,atrim=0:{d:g},"
                f"afade=t=in:d={fade_s:g},afade=t=out:st={st:g}:d={fade_s:g}[c{i}]")
        parts.append("".join(f"[c{i}]" for i in range(len(ins)))
                     + f"concat=n={len(ins)}:v=0:a=1[mix]")
        cmd += ["-filter_complex", ";".join(parts), "-map", "[mix]", out]
        return cmd

    def _conform_audio(self, path: str, dur: float) -> str:
        """Conforme le fichier généré à la durée du plan, EN PLACE (même nom →
        le clip se pose tel quel sous sa vidéo dans la timeline). Silencieux en
        cas d'échec : on garde le fichier brut plutôt que de perdre la génération."""
        if not path or not os.path.isfile(path) or not dur:
            return path
        try:
            from core.video_utils import get_ffmpeg_exe
            ff = get_ffmpeg_exe()
        except Exception:
            ff = "ffmpeg"
        tmp = path + ".cale.wav"
        try:
            import subprocess
            flags = 0x08000000 if os.name == "nt" else 0   # CREATE_NO_WINDOW
            proc = subprocess.run(self._build_conform_cmd(ff, path, tmp, dur),
                                  capture_output=True, creationflags=flags, timeout=120)
            if proc.returncode == 0 and os.path.isfile(tmp) and os.path.getsize(tmp) > 0:
                os.replace(tmp, path)
        except Exception:
            pass
        finally:
            if os.path.isfile(tmp):
                try:
                    os.remove(tmp)
                except OSError:
                    pass
        return path

    def _on_export_mix(self):
        import time as _time
        pairs = [(it["out"], float(it["duration"])) for it in self._sfx_queue
                 if it["status"] == "done" and it["out"] and os.path.isfile(it["out"])]
        if len(pairs) < 2:
            self._status.setText(translate("Il faut au moins 2 ambiances générées."))
            return
        try:
            from core.video_utils import get_ffmpeg_exe
            ff = get_ffmpeg_exe()
        except Exception:
            ff = "ffmpeg"
        ins  = [p for p, _ in pairs]
        durs = [d for _, d in pairs]
        out = os.path.join(self._sfx_out_dir(), f"bande_son_{int(_time.time())}.wav")
        cmd = self._build_assemble_cmd(ff, ins, durs, out)
        self._status.setText(translate("Assemblage de la bande-son (durée exacte)…"))
        self._mix_worker = _MixWorker(cmd, out)
        self._mix_worker.finished.connect(self._on_mix_done)
        self._mix_worker.failed.connect(self._on_mix_failed)
        self._mix_worker.start()

    def _on_mix_done(self, path: str):
        self._status.setText(translate("Bande-son calée exportée ✓ (durée = somme des plans)"))
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
            _eng = getattr(self, "_video_engine_combo", None)
            _eng_key = _eng.currentData() if _eng else "sfx16"
            if _eng_key == "foley":
                from api.tts import FoleyControlWorker
                self._worker = FoleyControlWorker(
                    self._video_path, self._txt_prompt_video.toPlainText().strip(),
                    float(self._dur_video.value()), label="live_foley")
            else:
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
