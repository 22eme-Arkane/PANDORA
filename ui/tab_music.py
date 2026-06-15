"""
ui/tab_music.py — Onglet « Musique IA » du Studio IA PANDORA | Cinéma.

Génération musicale multi-moteurs fal.ai (catalogue api/music.py), avec par
défaut le moteur le plus performant (Lyria 2). Pattern UI calqué sur
ui/tab_sound_design.py (en-tête, prompt, durée, file d'attente, résultats).

Le champ « Paroles » n'apparaît que pour les moteurs qui savent chanter.
"""

import os

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QTextEdit,
    QComboBox, QSpinBox, QSlider, QProgressBar, QScrollArea,
)
from PyQt6.QtCore import Qt, pyqtSignal, QUrl
from PyQt6.QtGui import QDesktopServices

from ui.styles import C, STYLESHEET
from core.i18n import translate
import api.music as music_api


class TabMusic(QScrollArea):
    """Génération musicale Cinéma — tous les moteurs musique de fal.ai."""

    generation_done = pyqtSignal(str)   # chemin du fichier généré

    def __init__(self):
        super().__init__()
        self.setStyleSheet(STYLESHEET)
        self.setWidgetResizable(True)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setFrameStyle(0)
        self._worker = None

        _container = QWidget()
        self.setWidget(_container)
        root = QVBoxLayout(_container)
        root.setContentsMargins(28, 22, 28, 22)
        root.setSpacing(14)

        # ── En-tête ───────────────────────────────────────────────────────────
        title = QLabel("♪  " + translate("Musique IA"))
        title.setStyleSheet(
            f"color:{C['text_primary']};font-size:18px;font-weight:800;"
            f"letter-spacing:1px;background:transparent;border:none;")
        root.addWidget(title)

        sub = QLabel(translate(
            "Compose la musique de tes scènes : score instrumental ou chanson "
            "avec paroles, via les meilleurs moteurs de fal.ai."))
        sub.setWordWrap(True)
        sub.setStyleSheet(
            f"color:{C['text_dim']};font-size:11px;background:transparent;border:none;")
        root.addWidget(sub)

        # ── Moteur ────────────────────────────────────────────────────────────
        root.addWidget(self._section_label(translate("MOTEUR DE GÉNÉRATION")))
        self._engine = QComboBox()
        for key in music_api.ENGINE_ORDER:
            spec = music_api.MUSIC_ENGINES.get(key)
            if spec:
                self._engine.addItem(spec["label"], key)
        idx = self._engine.findData(music_api.default_engine())
        if idx >= 0:
            self._engine.setCurrentIndex(idx)
        self._engine.setStyleSheet(
            f"QComboBox{{background:{C['bg2']};color:{C['text_primary']};"
            f"border:1px solid {C['border']};border-radius:8px;padding:8px 10px;font-size:12px;}}")
        self._engine.currentIndexChanged.connect(self._on_engine_changed)
        root.addWidget(self._engine)

        # ── Prompt ────────────────────────────────────────────────────────────
        root.addWidget(self._section_label(translate("STYLE / DESCRIPTION")))
        self._prompt = QTextEdit()
        self._prompt.setPlaceholderText(translate(
            "Décris la musique (en anglais de préférence). "
            "Ex. « epic orchestral score, slow build, strings and brass, cinematic, tense »"))
        self._prompt.setFixedHeight(110)
        self._prompt.setStyleSheet(
            f"QTextEdit{{background:{C['bg2']};color:{C['text_primary']};"
            f"border:1px solid {C['border']};border-radius:8px;padding:10px;font-size:12px;}}")
        root.addWidget(self._prompt)

        # ── Paroles (moteurs avec voix uniquement) ────────────────────────────
        self._lyrics_lbl = self._section_label(translate("PAROLES (optionnel)"))
        root.addWidget(self._lyrics_lbl)
        self._lyrics = QTextEdit()
        self._lyrics.setPlaceholderText(translate(
            "Paroles à chanter. Laisse vide pour un morceau instrumental."))
        self._lyrics.setFixedHeight(90)
        self._lyrics.setStyleSheet(
            f"QTextEdit{{background:{C['bg2']};color:{C['text_primary']};"
            f"border:1px solid {C['border']};border-radius:8px;padding:10px;font-size:12px;}}")
        root.addWidget(self._lyrics)

        # ── Durée : tirette + saisie directe (synchronisées) ─────────────────
        dur_row = QHBoxLayout()
        dur_row.setSpacing(10)
        dur_lbl = QLabel(translate("Durée"))
        dur_lbl.setStyleSheet(
            f"color:{C['text_secondary']};font-size:11px;background:transparent;border:none;")
        dur_row.addWidget(dur_lbl)

        self._dur_slider = QSlider(Qt.Orientation.Horizontal)
        self._dur_slider.setRange(5, 285)
        self._dur_slider.setValue(30)
        self._dur_slider.setStyleSheet(
            f"QSlider::groove:horizontal{{height:4px;background:{C['bg3']};border-radius:2px;}}"
            f"QSlider::sub-page:horizontal{{height:4px;background:{C['accent']};border-radius:2px;}}"
            f"QSlider::handle:horizontal{{width:14px;height:14px;margin:-6px 0;border-radius:7px;"
            f"background:{C['accent']};}}"
            f"QSlider::handle:horizontal:hover{{background:#6eded6;}}")
        dur_row.addWidget(self._dur_slider, 1)

        # Saisie directe de la durée souhaitée
        self._duration = QSpinBox()
        self._duration.setRange(5, 285)
        self._duration.setValue(30)
        self._duration.setSuffix(" s")
        self._duration.setFixedWidth(82)
        self._duration.setStyleSheet(
            f"QSpinBox{{background:{C['bg2']};color:{C['text_primary']};"
            f"border:1px solid {C['border']};border-radius:6px;padding:5px 8px;font-size:12px;}}")
        dur_row.addWidget(self._duration)

        # Synchronisation tirette ↔ saisie
        self._dur_slider.valueChanged.connect(
            lambda v: self._duration.value() != v and self._duration.setValue(v))
        self._duration.valueChanged.connect(
            lambda v: self._dur_slider.value() != v and self._dur_slider.setValue(v))

        self._price_lbl = QLabel("")
        self._price_lbl.setStyleSheet(
            f"color:{C['text_dim']};font-size:10px;background:transparent;border:none;")
        dur_row.addWidget(self._price_lbl)
        root.addLayout(dur_row)

        # ── Barre de génération ───────────────────────────────────────────────
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

        self._btn_generate = QPushButton("♪  " + translate("Générer la musique"))
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

        from ui.tab_video_engines import _btn_ghost_style as _bgs
        self._btn_open_dir = QPushButton(translate("Ouvrir le dossier"))
        self._btn_open_dir.setFixedHeight(30)
        self._btn_open_dir.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_open_dir.setToolTip(translate("Ouvre le dossier des musiques générées."))
        self._btn_open_dir.setStyleSheet(_bgs())
        self._btn_open_dir.clicked.connect(self._on_open_dir)
        root.addWidget(self._btn_open_dir)

        _scroll = QScrollArea()
        _scroll.setWidgetResizable(True)
        _scroll.setMinimumHeight(150)
        _scroll.setStyleSheet("QScrollArea{border:none;background:transparent;}")
        self._results_w = QWidget()
        self._results_w.setStyleSheet("background:transparent;")
        self._results_lay = QVBoxLayout(self._results_w)
        self._results_lay.setContentsMargins(0, 0, 0, 0)
        self._results_lay.setSpacing(6)
        self._results_lay.addStretch()
        _scroll.setWidget(self._results_w)
        root.addWidget(_scroll, 1)

        self._on_engine_changed()   # ajuste champ paroles + durée + prix

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _section_label(self, text):
        lbl = QLabel(text)
        lbl.setStyleSheet(
            f"color:{C['text_dim']};font-size:10px;font-weight:700;letter-spacing:1.5px;"
            f"background:transparent;border:none;")
        return lbl

    def _on_engine_changed(self):
        spec = music_api.engine_spec(self._engine.currentData())
        show_lyrics = bool(spec.get("lyrics"))
        self._lyrics_lbl.setVisible(show_lyrics)
        self._lyrics.setVisible(show_lyrics)
        max_dur = int(spec.get("max_dur", 60))
        self._dur_slider.setMaximum(max_dur)
        self._duration.setMaximum(max_dur)
        if self._duration.value() > max_dur:
            self._duration.setValue(max_dur)   # propage à la tirette via le signal
        self._price_lbl.setText(spec.get("price", ""))

    def _out_dir(self) -> str:
        return music_api._music_output_dir()

    def _on_open_dir(self):
        try:
            os.startfile(self._out_dir())
        except AttributeError:
            import subprocess
            subprocess.Popen(["xdg-open", self._out_dir()])

    # ── Génération ────────────────────────────────────────────────────────────

    def _on_generate(self):
        prompt = self._prompt.toPlainText().strip()
        if not prompt:
            self._status.setText(translate("Décris d'abord la musique à générer."))
            return
        lyrics = self._lyrics.toPlainText() if self._lyrics.isVisible() else ""
        self._worker = music_api.MusicWorker(
            engine_key=self._engine.currentData(),
            prompt=prompt,
            lyrics=lyrics,
            duration=float(self._duration.value()),
            out_dir=self._out_dir(),
        )
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
        name = QLabel("♪ " + os.path.basename(path))
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
        btn_play.clicked.connect(
            lambda checked=False, p=path: QDesktopServices.openUrl(QUrl.fromLocalFile(p)))
        rl.addWidget(btn_play)
        self._results_lay.insertWidget(0, row)

    def retranslate(self):
        pass
