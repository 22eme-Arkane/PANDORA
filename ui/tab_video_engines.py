"""
ui/tab_video_engines.py — Onglet Génération Directe (sans storyboard).

Moteurs disponibles :
  · Seedance 2.0 T2V  — bytedance/seedance-2.0/text-to-video       (~$0.30/s)
  · Seedance Fast T2V — bytedance/seedance-2.0/fast/text-to-video  (~$0.09/s)
  · Kling v3 Pro I2V  — fal-ai/kling-video/v3/pro/image-to-video   ($0.112-0.196/s)
  · Kling v3 Pro T2V  — fal-ai/kling-video/v3/pro/text-to-video    ($0.112-0.196/s)
  · PixVerse v4.5 I2V — fal-ai/pixverse/v4.5/image-to-video        ($0.04-0.08/s)
"""

import os
from PyQt6.QtWidgets import (
    QScrollArea, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QTextEdit, QComboBox, QSlider, QCheckBox,
    QProgressBar, QFileDialog, QFrame, QStackedWidget,
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QPixmap
from ui.styles import C


# ── Helpers ────────────────────────────────────────────────────────────────────

def _section(text: str) -> QLabel:
    lbl = QLabel(text.upper())
    lbl.setStyleSheet(
        f"color:{C['accent']};font-size:9px;font-weight:700;"
        f"letter-spacing:3px;font-family:'Consolas',monospace;background:transparent;"
    )
    return lbl


def _divider() -> QWidget:
    d = QWidget()
    d.setFixedHeight(1)
    d.setStyleSheet(f"background:{C['border']};")
    return d


def _combo_style() -> str:
    return (
        f"QComboBox{{background:{C['bg3']};border:1px solid {C['border']};"
        f"border-radius:6px;color:{C['text_primary']};font-size:12px;padding:5px 10px;}}"
        f"QComboBox:hover{{border-color:{C['accent_dim']};}}"
        f"QComboBox::drop-down{{border:none;width:22px;}}"
        f"QComboBox QAbstractItemView{{background:{C['bg3']};color:{C['text_primary']};"
        f"border:1px solid {C['border']};selection-background-color:{C['accent_dim']};}}"
    )


def _slider_style() -> str:
    return (
        f"QSlider::groove:horizontal{{height:4px;background:{C['bg3']};border-radius:2px;}}"
        f"QSlider::handle:horizontal{{width:14px;height:14px;"
        f"background:{C['accent']};border-radius:7px;margin:-5px 0;}}"
        f"QSlider::sub-page:horizontal{{background:{C['accent_dim']};border-radius:2px;}}"
    )


def _prompt_style() -> str:
    return (
        f"QTextEdit{{background:{C['bg3']};border:1px solid {C['border']};"
        f"border-radius:8px;color:{C['text_primary']};"
        f"font-size:12px;padding:10px 12px;}}"
        f"QTextEdit:focus{{border-color:{C['accent_dim']};}}"
    )


def _btn_accent_style() -> str:
    return (
        f"QPushButton{{background:{C['accent']};color:#07080f;border:none;"
        f"border-radius:8px;font-size:13px;font-weight:700;padding:0 20px;}}"
        f"QPushButton:hover{{background:#6eded6;}}"
        f"QPushButton:pressed{{background:{C['accent_dim']};color:#fff;}}"
        f"QPushButton:disabled{{background:{C['bg3']};color:{C['text_dim']};}}"
    )


def _btn_ghost_style() -> str:
    return (
        f"QPushButton{{background:transparent;color:{C['text_secondary']};"
        f"border:1px solid {C['border']};border-radius:7px;"
        f"font-size:11px;font-weight:700;padding:0 14px;}}"
        f"QPushButton:hover{{background:{C['bg3']};color:{C['text_primary']};"
        f"border-color:{C['border_bright']};}}"
        f"QPushButton:pressed{{background:{C['bg3']};}}"
    )


# ── Image picker mini-widget ───────────────────────────────────────────────────

class _ImagePicker(QWidget):
    """Bouton de sélection d'image + preview 100×60."""
    path_changed = pyqtSignal(str)

    def __init__(self, label: str = "Image de départ"):
        super().__init__()
        self.setStyleSheet("background:transparent;")
        self._path = ""

        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(6)

        top = QHBoxLayout()
        top.setSpacing(8)
        lbl = QLabel(label)
        lbl.setStyleSheet(f"color:{C['text_secondary']};font-size:12px;background:transparent;")
        top.addWidget(lbl)
        top.addStretch()
        self._path_lbl = QLabel("Aucune")
        self._path_lbl.setStyleSheet(
            f"color:{C['text_dim']};font-size:11px;"
            f"font-family:'Consolas',monospace;background:transparent;"
        )
        top.addWidget(self._path_lbl)
        lay.addLayout(top)

        row = QHBoxLayout()
        row.setSpacing(10)
        self._thumb = QLabel()
        self._thumb.setFixedSize(80, 50)
        self._thumb.setStyleSheet(
            f"background:{C['bg3']};border:1px solid {C['border']};border-radius:6px;"
        )
        self._thumb.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._thumb.setText("—")
        row.addWidget(self._thumb)

        btn = QPushButton("Choisir…")
        btn.setFixedHeight(32)
        btn.setStyleSheet(_btn_ghost_style())
        btn.clicked.connect(self._pick)
        row.addWidget(btn)
        row.addStretch()
        lay.addLayout(row)

    def _pick(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Choisir une image", "",
            "Images (*.png *.jpg *.jpeg *.webp *.bmp)"
        )
        if path:
            self._path = path
            self._path_lbl.setText(os.path.basename(path))
            pix = QPixmap(path).scaled(
                80, 50,
                Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                Qt.TransformationMode.SmoothTransformation,
            )
            self._thumb.setPixmap(pix)
            self._thumb.setText("")
            self.path_changed.emit(path)

    def path(self) -> str:
        return self._path

    def clear(self):
        self._path = ""
        self._path_lbl.setText("Aucune")
        self._thumb.setText("—")
        self._thumb.setPixmap(QPixmap())


# ── Sous-formulaires par moteur ────────────────────────────────────────────────

class _KlingI2VForm(QWidget):
    """Formulaire Kling I2V."""
    def __init__(self):
        super().__init__()
        self.setStyleSheet("background:transparent;")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(12)

        self._img = _ImagePicker("Image de départ (requis)")
        lay.addWidget(self._img)

        self._img_end = _ImagePicker("Image de fin (optionnel)")
        lay.addWidget(self._img_end)

        lay.addWidget(_section("Prompt"))
        self._prompt = QTextEdit()
        self._prompt.setPlaceholderText(
            "Décrivez le mouvement et l'action de la scène… (FR accepté, traduit auto)"
        )
        self._prompt.setMinimumHeight(80)
        self._prompt.setMaximumHeight(120)
        self._prompt.setStyleSheet(_prompt_style())
        lay.addWidget(self._prompt)

        neg_lbl = QLabel("Prompt négatif (optionnel) :")
        neg_lbl.setStyleSheet(f"color:{C['text_secondary']};font-size:12px;background:transparent;")
        lay.addWidget(neg_lbl)
        self._neg = QTextEdit()
        self._neg.setMaximumHeight(60)
        self._neg.setStyleSheet(_prompt_style())
        lay.addWidget(self._neg)

        # Durée + audio
        params_row = QHBoxLayout()
        params_row.setSpacing(16)

        dur_col = QVBoxLayout()
        dur_col.setSpacing(6)
        self._dur_lbl = QLabel("Durée : 5 s  (~$0.56)")
        self._dur_lbl.setStyleSheet(f"color:{C['text_secondary']};font-size:12px;background:transparent;")
        dur_col.addWidget(self._dur_lbl)
        self._dur_slider = QSlider(Qt.Orientation.Horizontal)
        self._dur_slider.setMinimum(3)
        self._dur_slider.setMaximum(15)
        self._dur_slider.setValue(5)
        self._dur_slider.setStyleSheet(_slider_style())
        self._dur_slider.valueChanged.connect(self._update_dur_label)
        dur_col.addWidget(self._dur_slider)
        dur_hints = QLabel("3 s                    8 s                   15 s")
        dur_hints.setStyleSheet(
            f"color:{C['text_dim']};font-size:9px;font-family:'Consolas',monospace;background:transparent;"
        )
        dur_col.addWidget(dur_hints)
        params_row.addLayout(dur_col, 2)

        audio_col = QVBoxLayout()
        audio_col.setSpacing(6)
        audio_lbl = QLabel("Audio :")
        audio_lbl.setStyleSheet(f"color:{C['text_secondary']};font-size:12px;background:transparent;")
        audio_col.addWidget(audio_lbl)
        self._audio_chk = QCheckBox("Générer l'audio (recommandé)")
        self._audio_chk.setChecked(True)
        self._audio_chk.setStyleSheet(f"color:{C['text_primary']};font-size:12px;background:transparent;")
        audio_col.addWidget(self._audio_chk)
        audio_col.addStretch()
        params_row.addLayout(audio_col, 1)

        lay.addLayout(params_row)

    def _update_dur_label(self, val: int):
        price = val * (0.168 if self._audio_chk.isChecked() else 0.112)
        self._dur_lbl.setText(f"Durée : {val} s  (~${price:.2f})")

    def get_params(self) -> dict | None:
        img = self._img.path()
        if not img:
            return None
        return {
            "mode":             "i2v",
            "image_url":        img,
            "end_image_url":    self._img_end.path(),
            "prompt":           self._prompt.toPlainText().strip(),
            "negative_prompt":  self._neg.toPlainText().strip(),
            "duration":         self._dur_slider.value(),
            "generate_audio":   self._audio_chk.isChecked(),
            "shot_type":        "customize",
        }

    def error(self) -> str:
        if not self._img.path():
            return "Image de départ requise pour Kling I2V."
        return ""


class _KlingT2VForm(QWidget):
    """Formulaire Kling T2V."""
    def __init__(self):
        super().__init__()
        self.setStyleSheet("background:transparent;")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(12)

        lay.addWidget(_section("Prompt"))
        self._prompt = QTextEdit()
        self._prompt.setPlaceholderText(
            "Décrivez la scène complète… (FR accepté, traduit automatiquement en anglais)"
        )
        self._prompt.setMinimumHeight(100)
        self._prompt.setMaximumHeight(160)
        self._prompt.setStyleSheet(_prompt_style())
        lay.addWidget(self._prompt)

        neg_lbl = QLabel("Prompt négatif (optionnel) :")
        neg_lbl.setStyleSheet(f"color:{C['text_secondary']};font-size:12px;background:transparent;")
        lay.addWidget(neg_lbl)
        self._neg = QTextEdit()
        self._neg.setMaximumHeight(60)
        self._neg.setStyleSheet(_prompt_style())
        lay.addWidget(self._neg)

        params_row = QHBoxLayout()
        params_row.setSpacing(16)

        dur_col = QVBoxLayout()
        dur_col.setSpacing(6)
        self._dur_lbl = QLabel("Durée : 5 s  (~$0.84)")
        self._dur_lbl.setStyleSheet(f"color:{C['text_secondary']};font-size:12px;background:transparent;")
        dur_col.addWidget(self._dur_lbl)
        self._dur_slider = QSlider(Qt.Orientation.Horizontal)
        self._dur_slider.setMinimum(3)
        self._dur_slider.setMaximum(15)
        self._dur_slider.setValue(5)
        self._dur_slider.setStyleSheet(_slider_style())
        self._dur_slider.valueChanged.connect(self._update_dur_label)
        dur_col.addWidget(self._dur_slider)
        params_row.addLayout(dur_col, 2)

        audio_col = QVBoxLayout()
        audio_col.setSpacing(6)
        audio_lbl = QLabel("Audio :")
        audio_lbl.setStyleSheet(f"color:{C['text_secondary']};font-size:12px;background:transparent;")
        audio_col.addWidget(audio_lbl)
        self._audio_chk = QCheckBox("Générer l'audio")
        self._audio_chk.setChecked(True)
        self._audio_chk.setStyleSheet(f"color:{C['text_primary']};font-size:12px;background:transparent;")
        audio_col.addWidget(self._audio_chk)
        audio_col.addStretch()
        params_row.addLayout(audio_col, 1)

        lay.addLayout(params_row)

    def _update_dur_label(self, val: int):
        price = val * (0.196 if self._audio_chk.isChecked() else 0.112)
        self._dur_lbl.setText(f"Durée : {val} s  (~${price:.2f})")

    def get_params(self) -> dict:
        return {
            "mode":            "t2v",
            "prompt":          self._prompt.toPlainText().strip(),
            "negative_prompt": self._neg.toPlainText().strip(),
            "duration":        self._dur_slider.value(),
            "generate_audio":  self._audio_chk.isChecked(),
            "shot_type":       "customize",
        }

    def error(self) -> str:
        if not self._prompt.toPlainText().strip():
            return "Le prompt est requis pour Kling T2V."
        return ""


class _PixVerseForm(QWidget):
    """Formulaire PixVerse I2V."""
    def __init__(self):
        super().__init__()
        self.setStyleSheet("background:transparent;")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(12)

        self._img = _ImagePicker("Image de départ (requis)")
        lay.addWidget(self._img)

        lay.addWidget(_section("Prompt"))
        self._prompt = QTextEdit()
        self._prompt.setPlaceholderText(
            "Décrivez le mouvement… (FR accepté)"
        )
        self._prompt.setMinimumHeight(80)
        self._prompt.setMaximumHeight(120)
        self._prompt.setStyleSheet(_prompt_style())
        lay.addWidget(self._prompt)

        params_row = QHBoxLayout()
        params_row.setSpacing(16)

        res_col = QVBoxLayout()
        res_col.setSpacing(6)
        res_lbl = QLabel("Résolution :")
        res_lbl.setStyleSheet(f"color:{C['text_secondary']};font-size:12px;background:transparent;")
        res_col.addWidget(res_lbl)
        self._res_combo = QComboBox()
        self._res_combo.setStyleSheet(_combo_style())
        self._res_combo.addItem("720p  (~$0.20 / 5 s)", "720p")
        self._res_combo.addItem("1080p  (~$0.40 / 5 s)", "1080p")
        res_col.addWidget(self._res_combo)
        params_row.addLayout(res_col, 1)

        note_col = QVBoxLayout()
        note_col.setSpacing(6)
        note_lbl = QLabel("Durée : 5 s (fixe)")
        note_lbl.setStyleSheet(f"color:{C['text_dim']};font-size:11px;background:transparent;")
        note_col.addWidget(note_lbl)
        note2 = QLabel("Sans audio natif · Idéal pour itérations rapides")
        note2.setStyleSheet(f"color:{C['text_dim']};font-size:10px;background:transparent;")
        note_col.addWidget(note2)
        note_col.addStretch()
        params_row.addLayout(note_col, 1)

        lay.addLayout(params_row)

    def get_params(self) -> dict | None:
        img = self._img.path()
        if not img:
            return None
        return {
            "image_url":  img,
            "prompt":     self._prompt.toPlainText().strip(),
            "duration":   5,
            "resolution": self._res_combo.currentData() or "720p",
        }

    def error(self) -> str:
        if not self._img.path():
            return "Image requise pour PixVerse I2V."
        return ""


class _SeedanceT2VForm(QWidget):
    """Formulaire Seedance 2.0 / Fast T2V — interface directe sans storyboard."""
    def __init__(self, model_key: str = "seedance-2.0"):
        super().__init__()
        self._model_key = model_key
        self.setStyleSheet("background:transparent;")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(12)

        lay.addWidget(_section("Prompt"))
        self._prompt = QTextEdit()
        self._prompt.setPlaceholderText(
            "Décrivez librement la scène à générer…\n"
            "(FR accepté, traduit automatiquement en anglais)"
        )
        self._prompt.setMinimumHeight(100)
        self._prompt.setMaximumHeight(180)
        self._prompt.setStyleSheet(_prompt_style())
        lay.addWidget(self._prompt)

        params_row = QHBoxLayout()
        params_row.setSpacing(16)

        # Résolution
        res_col = QVBoxLayout()
        res_col.setSpacing(6)
        res_lbl = QLabel("Résolution :")
        res_lbl.setStyleSheet(f"color:{C['text_secondary']};font-size:12px;background:transparent;")
        res_col.addWidget(res_lbl)
        self._res_combo = QComboBox()
        self._res_combo.setStyleSheet(_combo_style())
        if "fast" in model_key.lower():
            self._res_combo.addItem("480p  (~$0.09/5s)",  "480p")
            self._res_combo.addItem("720p  (~$0.18/5s)",  "720p")
        else:
            self._res_combo.addItem("720p  (~$0.30/5s)",  "720p")
            self._res_combo.addItem("1080p (~$0.60/5s)", "1080p")
        res_col.addWidget(self._res_combo)
        params_row.addLayout(res_col, 1)

        # Ratio
        ratio_col = QVBoxLayout()
        ratio_col.setSpacing(6)
        ratio_lbl = QLabel("Format :")
        ratio_lbl.setStyleSheet(f"color:{C['text_secondary']};font-size:12px;background:transparent;")
        ratio_col.addWidget(ratio_lbl)
        self._ratio_combo = QComboBox()
        self._ratio_combo.setStyleSheet(_combo_style())
        for label, val in [("16:9 — Paysage", "16:9"), ("9:16 — Portrait", "9:16"), ("1:1 — Carré", "1:1")]:
            self._ratio_combo.addItem(label, val)
        ratio_col.addWidget(self._ratio_combo)
        params_row.addLayout(ratio_col, 1)

        lay.addLayout(params_row)

        # Durée
        dur_col = QVBoxLayout()
        dur_col.setSpacing(6)
        self._dur_lbl = QLabel("Durée : 5 s")
        self._dur_lbl.setStyleSheet(f"color:{C['text_secondary']};font-size:12px;background:transparent;")
        dur_col.addWidget(self._dur_lbl)
        self._dur_slider = QSlider(Qt.Orientation.Horizontal)
        self._dur_slider.setMinimum(2)
        self._dur_slider.setMaximum(10)
        self._dur_slider.setValue(5)
        self._dur_slider.setStyleSheet(_slider_style())
        self._dur_slider.valueChanged.connect(lambda v: self._dur_lbl.setText(f"Durée : {v} s"))
        dur_col.addWidget(self._dur_slider)
        dur_hints = QLabel("2 s                   5 s                  10 s")
        dur_hints.setStyleSheet(
            f"color:{C['text_dim']};font-size:9px;font-family:'Consolas',monospace;background:transparent;"
        )
        dur_col.addWidget(dur_hints)
        lay.addLayout(dur_col)

    def get_params(self) -> dict:
        return {
            "mode":             "t2v",
            "model":            self._model_key,
            "prompt":           self._prompt.toPlainText().strip(),
            "duration":         str(self._dur_slider.value()),
            "resolution":       self._res_combo.currentData() or "720p",
            "aspect_ratio":     self._ratio_combo.currentData() or "16:9",
        }

    def error(self) -> str:
        if not self._prompt.toPlainText().strip():
            return "Le prompt est requis."
        return ""


# ── Tab principal ──────────────────────────────────────────────────────────────

class TabVideoEngines(QWidget):
    """Onglet génération directe — Prochainement."""
    generation_done = pyqtSignal(dict)

    def __init__(self):
        super().__init__()
        self.setStyleSheet(f"background:{C['bg0']};")

        lay = QVBoxLayout(self)
        lay.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lay.setSpacing(16)

        ico = QLabel("🎬")
        ico.setAlignment(Qt.AlignmentFlag.AlignCenter)
        ico.setStyleSheet("font-size:52px;background:transparent;")

        lbl = QLabel("Génération directe")
        lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl.setStyleSheet(
            f"color:{C['text_primary']};font-size:24px;font-weight:700;"
            f"letter-spacing:1px;background:transparent;"
        )

        sub = QLabel("Kling v3 Pro · PixVerse v4.5 · Seedance Fast — moteurs alternatifs")
        sub.setAlignment(Qt.AlignmentFlag.AlignCenter)
        sub.setStyleSheet(
            f"color:{C['text_secondary']};font-size:13px;background:transparent;"
        )

        badge = QLabel("BIENTÔT DISPONIBLE")
        badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        badge.setStyleSheet(
            f"color:{C['accent']};font-size:10px;font-weight:700;"
            f"letter-spacing:2px;font-family:'Consolas',monospace;"
            f"border:1px solid {C['accent_dim']};border-radius:4px;"
            f"padding:5px 14px;background:rgba(78,205,196,0.06);"
        )

        lay.addWidget(ico)
        lay.addWidget(lbl)
        lay.addWidget(sub)
        lay.addSpacing(8)
        lay.addWidget(badge, 0, Qt.AlignmentFlag.AlignCenter)
        return  # tout le code ci-dessous est désactivé

        self._worker = None

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet(f"QScrollArea{{background:{C['bg0']};border:none;}}")

        container = QWidget()
        container.setStyleSheet(f"background:{C['bg0']};")
        scroll.setWidget(container)

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.addWidget(scroll)

        lay = QVBoxLayout(container)
        lay.setContentsMargins(24, 20, 24, 24)
        lay.setSpacing(16)

        # ── En-tête ────────────────────────────────────────────────────────────
        info_row = QHBoxLayout()
        info_row.setSpacing(16)

        for name, badge, price in [
            ("Seedance 2.0", "T2V", "~$0.30/s"),
            ("Seedance Fast", "T2V", "~$0.09/s"),
            ("Kling v3 Pro", "I2V + T2V", "$0.112-0.196/s"),
            ("PixVerse v4.5", "I2V", "$0.04-0.08/s"),
        ]:
            card = QWidget()
            card.setStyleSheet(
                f"QWidget{{background:{C['bg2']};border:1px solid {C['border']};"
                f"border-radius:8px;}}"
            )
            cl = QVBoxLayout(card)
            cl.setContentsMargins(14, 10, 14, 10)
            cl.setSpacing(3)
            n_lbl = QLabel(name)
            n_lbl.setStyleSheet(
                f"color:{C['text_primary']};font-size:13px;font-weight:700;background:transparent;"
            )
            b_lbl = QLabel(badge)
            b_lbl.setStyleSheet(
                f"color:{C['accent']};font-size:10px;font-weight:700;"
                f"letter-spacing:1px;background:transparent;"
            )
            p_lbl = QLabel(price)
            p_lbl.setStyleSheet(
                f"color:{C['text_dim']};font-size:10px;font-family:'Consolas',monospace;"
                f"background:transparent;"
            )
            cl.addWidget(n_lbl)
            cl.addWidget(b_lbl)
            cl.addWidget(p_lbl)
            info_row.addWidget(card, 1)

        lay.addLayout(info_row)
        lay.addWidget(_divider())

        # ── Sélecteur moteur ───────────────────────────────────────────────────
        lay.addWidget(_section("Moteur de génération"))

        self._engine_combo = QComboBox()
        self._engine_combo.setMinimumHeight(36)
        self._engine_combo.setStyleSheet(_combo_style())
        from PyQt6.QtGui import QColor as _QColor, QBrush as _QBrush
        for label, key, enabled in self._ENGINES:
            self._engine_combo.addItem(label, key)
            if not enabled:
                idx = self._engine_combo.count() - 1
                model = self._engine_combo.model()
                item = model.item(idx)
                if item:
                    item.setEnabled(False)
                    item.setForeground(_QBrush(_QColor(C['text_dim'])))
        self._engine_combo.currentIndexChanged.connect(self._on_engine_changed)
        lay.addWidget(self._engine_combo)

        # ── Formulaires empilés ────────────────────────────────────────────────
        self._stack = QStackedWidget()
        self._form_seedance     = _SeedanceT2VForm("seedance-2.0")
        self._form_seedance_fast = _SeedanceT2VForm("seedance-2.0-fast")
        self._form_kling_i2v    = _KlingI2VForm()
        self._form_kling_t2v    = _KlingT2VForm()
        self._form_pixverse     = _PixVerseForm()
        self._stack.addWidget(self._form_seedance)
        self._stack.addWidget(self._form_seedance_fast)
        self._stack.addWidget(self._form_kling_i2v)
        self._stack.addWidget(self._form_kling_t2v)
        self._stack.addWidget(self._form_pixverse)
        lay.addWidget(self._stack)

        lay.addWidget(_divider())

        # ── Bouton génération ──────────────────────────────────────────────────
        btn_row = QHBoxLayout()
        self._btn_generate = QPushButton("▶  Générer")
        self._btn_generate.setMinimumHeight(44)
        self._btn_generate.setStyleSheet(_btn_accent_style())
        self._btn_generate.clicked.connect(self._on_generate)
        btn_row.addWidget(self._btn_generate)
        btn_row.addStretch()
        lay.addLayout(btn_row)

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

        # ── Résultat ───────────────────────────────────────────────────────────
        self._result_card = QWidget()
        self._result_card.setObjectName("resultCard")
        self._result_card.setStyleSheet(
            f"QWidget#resultCard{{background:{C['bg2']};border:1px solid {C['border']};"
            f"border-radius:10px;}}"
        )
        result_lay = QVBoxLayout(self._result_card)
        result_lay.setContentsMargins(16, 14, 16, 14)
        result_lay.setSpacing(8)
        self._result_lbl = QLabel("Aucune vidéo générée.")
        self._result_lbl.setStyleSheet(
            f"color:{C['text_dim']};font-size:12px;background:transparent;"
        )
        self._result_lbl.setWordWrap(True)
        result_lay.addWidget(self._result_lbl)
        result_btn_row = QHBoxLayout()
        self._btn_open = QPushButton("Ouvrir le dossier")
        self._btn_open.setFixedHeight(30)
        self._btn_open.setEnabled(False)
        self._btn_open.setStyleSheet(_btn_ghost_style())
        self._btn_open.clicked.connect(self._on_open_folder)
        result_btn_row.addWidget(self._btn_open)
        result_btn_row.addStretch()
        result_lay.addLayout(result_btn_row)
        lay.addWidget(self._result_card)

        lay.addStretch()

        self._last_folder: str = ""

    # ── Changement moteur ──────────────────────────────────────────────────────

    def _on_engine_changed(self, idx: int):
        self._stack.setCurrentIndex(idx)

    def _current_form(self):
        idx = self._engine_combo.currentIndex()
        return [
            self._form_seedance, self._form_seedance_fast,
            self._form_kling_i2v, self._form_kling_t2v, self._form_pixverse,
        ][idx]

    def _current_engine_key(self) -> str:
        return self._engine_combo.currentData() or "kling_i2v"

    # ── Génération ─────────────────────────────────────────────────────────────

    def _on_generate(self):
        if self._worker and self._worker.isRunning():
            return

        form   = self._current_form()
        err    = form.error()
        if err:
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.warning(self, "Paramètre manquant", err)
            return

        key    = self._current_engine_key()
        params = form.get_params()
        if params is None:
            return

        if key in ("seedance_t2v", "seedance_fast_t2v"):
            from core.worker import GenerationWorker
            self._worker = GenerationWorker(params)
        elif key in ("kling_i2v", "kling_t2v"):
            from api.video_engines import KlingWorker
            self._worker = KlingWorker(params)
        else:
            from api.video_engines import PixVerseWorker
            self._worker = PixVerseWorker(params)

        self._worker.progress.connect(self._on_progress)
        self._worker.finished.connect(self._on_finished)
        self._worker.failed.connect(self._on_failed)
        self._worker.start()

        self._btn_generate.setEnabled(False)
        self._btn_generate.setText("Génération en cours…")
        self._progress.setValue(0)
        self._progress.show()
        self._status_lbl.show()

    def _on_progress(self, pct: int, msg: str):
        self._progress.setValue(pct)
        self._status_lbl.setText(msg)

    def _on_finished(self, result: dict):
        self._btn_generate.setEnabled(True)
        self._btn_generate.setText("▶  Générer")
        self._progress.setValue(100)

        local = result.get("local_path", "")
        model = result.get("model", "")
        dur   = result.get("duration", 0)
        cost  = result.get("credits_used", 0)

        if local:
            self._last_folder = os.path.dirname(local)
            self._result_lbl.setText(
                f"✓  {os.path.basename(local)}"
                f"  ·  {dur}s  ·  {model}  ·  ~${cost:.2f}"
            )
            self._result_lbl.setStyleSheet(
                f"color:{C['accent']};font-size:12px;background:transparent;"
            )
            self._btn_open.setEnabled(True)
            self.generation_done.emit(result)
        else:
            self._status_lbl.setText("✓  Terminé (mode mock — aucune clé fal.ai)")

    def _on_failed(self, err: str):
        self._btn_generate.setEnabled(True)
        self._btn_generate.setText("▶  Générer")
        self._progress.setValue(0)
        self._status_lbl.setText(f"✗  {err[:120]}")
        from PyQt6.QtWidgets import QMessageBox
        QMessageBox.critical(self, "Erreur génération", err)

    def _on_open_folder(self):
        if self._last_folder and os.path.isdir(self._last_folder):
            import subprocess
            try:
                os.startfile(self._last_folder)
            except AttributeError:
                subprocess.Popen(["xdg-open", self._last_folder])
