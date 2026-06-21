"""
ui/tab_sound_design.py — Onglet « Sound Design » du Studio IA PANDORA | Cinéma.

Porté depuis le Live (ui/tab_sound_design_live.py, stabilisé en réel) — copie
ADAPTÉE Cinéma, aucun import de fichier Live. Deux modes via Mirelo SFX 1.6 :
  - « Prompt → SFX »        : un PROMPT SON (texte) → fichier audio (text-to-audio)
  - « Vidéo → bande-son »   : un clip + prompt optionnel → vidéo SONORISÉE
                              et SYNCHRONISÉE (video-to-video)

La file d'attente pilotée par le Conducteur est propre au Live (les plans
Cinéma n'ont pas de champ « prompt son ») — ici, génération manuelle.
"""

import os

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QTextEdit,
    QDoubleSpinBox, QProgressBar, QStackedWidget, QScrollArea, QFileDialog,
    QComboBox,
)
from PyQt6.QtCore import Qt, pyqtSignal, QUrl
from PyQt6.QtGui import QDesktopServices

from ui.styles import C, STYLESHEET
from core.i18n import translate


class TabSoundDesign(QScrollArea):
    """Sound design Cinéma via Mirelo SFX 1.6 (texte→audio + vidéo→bande-son).
    L'onglet ENTIER est scrollable — sinon Qt écrase les sections quand le
    contenu dépasse la fenêtre (vu en réel côté Live)."""

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
            "Sonorise tes plans : un prompt son → SFX/ambiance, ou un clip "
            "vidéo → bande-son synchronisée (Mirelo SFX 1.6, ~$0.01/s)."))
        sub.setWordWrap(True)
        sub.setStyleSheet(
            f"color:{C['text_dim']};font-size:11px;background:transparent;border:none;")
        root.addWidget(sub)

        # ── Modes ─────────────────────────────────────────────────────────────
        mode_row = QHBoxLayout()
        mode_row.setSpacing(0)
        self._btn_mode_text  = self._make_mode_btn(translate("Prompt → SFX"), "text")
        self._btn_mode_video = self._make_mode_btn(translate("Vidéo → bande-son"), "video")
        mode_row.addWidget(self._btn_mode_text)
        mode_row.addWidget(self._btn_mode_video)
        mode_row.addStretch()
        root.addLayout(mode_row)

        self._stack = QStackedWidget()
        self._stack.addWidget(self._build_text_panel())
        self._stack.addWidget(self._build_video_panel())
        root.addWidget(self._stack)

        # ── Barre de génération (progression AU-DESSUS du bouton) ─────────────
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

        self._btn_generate = QPushButton("▶▶  " + translate("Lancer la file d'attente"))
        self._btn_generate.setFixedHeight(44)
        self._btn_generate.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_generate.setStyleSheet(
            f"QPushButton{{background:{C['accent']};color:#07080f;border:none;"
            f"border-radius:9px;font-size:13px;font-weight:800;letter-spacing:0.5px;}}"
            f"QPushButton:hover{{background:#6eded6;}}"
            f"QPushButton:disabled{{background:{C['bg3']};color:{C['text_dim']};}}")
        self._btn_generate.clicked.connect(self._on_generate)
        root.addWidget(self._btn_generate)

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
        # Style uniforme « ghost » pleine largeur
        from ui.tab_video_engines import _btn_ghost_style as _bgs
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
            "Ex. « rain on a tin roof, distant thunder, no music, no vocals »"))
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
        self._btn_pick = QPushButton(translate("📁  Choisir un clip vidéo…"))
        self._btn_pick.setFixedHeight(38)
        self._btn_pick.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_pick.setStyleSheet(
            f"QPushButton{{background:{C['bg2']};color:{C['text_primary']};"
            f"border:1px solid {C['border']};border-radius:8px;font-size:11px;font-weight:700;padding:0 14px;}}"
            f"QPushButton:hover{{background:{C['bg3']};border-color:{C['border_bright']};}}")
        self._btn_pick.clicked.connect(self._on_pick_video)
        pick_row.addWidget(self._btn_pick)
        self._lbl_video = QLabel(translate("Aucun clip sélectionné"))
        self._lbl_video.setStyleSheet(
            f"color:{C['text_dim']};font-size:10px;background:transparent;border:none;")
        pick_row.addWidget(self._lbl_video, 1)
        lay.addLayout(pick_row)

        self._txt_prompt_video = QTextEdit()
        self._txt_prompt_video.setPlaceholderText(translate(
            "Prompt son optionnel (anglais) pour orienter la bande-son. "
            "Laisse vide pour une sonorisation automatique du clip."))
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
        """Pré-remplit le mode « Prompt → SFX » (point d'entrée externe)."""
        self._set_mode("text")
        self._txt_prompt.setPlainText(prompt or "")
        try:
            self._dur_text.setValue(max(1.0, min(60.0, float(duration or 10.0))))
        except (TypeError, ValueError):
            pass

    def _sfx_out_dir(self) -> str:
        from core.context import get_data_root
        d = os.path.join(get_data_root(), "sound_design")
        os.makedirs(d, exist_ok=True)
        return d

    def _on_open_dir(self):
        """Ouvre le dossier de destination — disponible AVANT toute génération."""
        try:
            os.startfile(self._sfx_out_dir())
        except AttributeError:
            import subprocess
            subprocess.Popen(["xdg-open", self._sfx_out_dir()])

    def _on_pick_video(self):
        path, _ = QFileDialog.getOpenFileName(
            self, translate("Choisir un clip vidéo"), "",
            "Vidéos (*.mp4 *.mov *.webm *.m4v *.gif);;Tous les fichiers (*)")
        if path:
            self._video_path = path
            self._lbl_video.setText(os.path.basename(path))
            self._lbl_video.setStyleSheet(
                f"color:{C['text_secondary']};font-size:10px;background:transparent;border:none;")

    def _on_generate(self):
        if self._mode == "text":
            prompt = self._txt_prompt.toPlainText().strip()
            if not prompt:
                self._status.setText(translate("Écris d'abord un prompt son."))
                return
            from api.tts import SFX1Worker
            self._worker = SFX1Worker(prompt, float(self._dur_text.value()),
                                      label="sfx", out_dir=self._sfx_out_dir())
        else:
            if not self._video_path or not os.path.isfile(self._video_path):
                self._status.setText(translate("Choisis d'abord un clip vidéo."))
                return
            _eng = getattr(self, "_video_engine_combo", None)
            _eng_key = _eng.currentData() if _eng else "sfx16"
            if _eng_key == "foley":
                from api.tts import FoleyControlWorker
                self._worker = FoleyControlWorker(
                    self._video_path, self._txt_prompt_video.toPlainText().strip(),
                    float(self._dur_video.value()), label="foley")
            else:
                from api.tts import SFX1VideoWorker
                self._worker = SFX1VideoWorker(
                    self._video_path, self._txt_prompt_video.toPlainText().strip(),
                    float(self._dur_video.value()), label="sfx_video")

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
