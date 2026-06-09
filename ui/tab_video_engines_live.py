"""
ui/tab_video_engines.py — Onglet Génération Directe (sans storyboard).

Moteurs disponibles :
  · Seedance 2.0 T2V      — bytedance/seedance-2.0/text-to-video              (~$0.30/s)
  · Seedance Fast T2V     — bytedance/seedance-2.0/fast/text-to-video         (~$0.09/s)
  · Happy Horse 1.0 T2V   — alibaba/happy-horse/text-to-video                 ($0.14-0.28/s)
  · Happy Horse 1.0 I2V   — alibaba/happy-horse/image-to-video                ($0.14-0.28/s)
  · Kling O3 4K T2V       — fal-ai/kling-video/o3/4k/text-to-video            (~$0.42/s)
  · Kling O3 4K I2V       — fal-ai/kling-video/o3/4k/image-to-video           (~$0.42/s)
  · Kling v3 Pro I2V      — fal-ai/kling-video/v3/pro/image-to-video          ($0.112-0.196/s)
  · Kling v3 Pro T2V      — fal-ai/kling-video/v3/pro/text-to-video           ($0.112-0.196/s)
  · Kling v3 4K T2V       — fal-ai/kling-video/v3/4k/text-to-video            ($0.28-0.39/s)
  · PixVerse v6 T2V       — fal-ai/pixverse/v6/text-to-video                  ($0.025-0.115/s)
  · PixVerse v4.5 I2V     — fal-ai/pixverse/v4.5/image-to-video               ($0.04-0.08/s)
  · Veo 3.1 T2V           — fal-ai/veo3.1                                     (~$1.00/vidéo)
  · Sora 2 T2V            — fal-ai/sora-2/text-to-video                       (~$0.40/vidéo)
"""

import os
from PyQt6.QtWidgets import (
    QScrollArea, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QTextEdit, QComboBox, QSlider, QCheckBox,
    QProgressBar, QFileDialog, QFrame, QStackedWidget,
)
from PyQt6.QtCore import Qt, pyqtSignal
from core.i18n import translate
from PyQt6.QtGui import QPixmap
from ui.styles import C
from ui.widgets import HelpBlock, show_api_error
from ui.icons import claude_icon_pixmap, install_hover_icon
from api.enhance import EnhanceWorker


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


# ── Carré de référence visuelle « + » (style PANDORA, réutilisable) ─────────────

class _RefSquare(QWidget):
    """Carré 60×60 — '+' vide ou miniature de l'image chargée, avec bouton × pour retirer."""
    picked  = pyqtSignal(str)
    cleared = pyqtSignal()

    _SZ = 60

    def __init__(self, tooltip: str = "Ajouter une image de référence", parent=None):
        super().__init__(parent)
        self.setFixedSize(self._SZ, self._SZ)
        self._path = ""

        self._btn_pick = QPushButton("+", self)
        self._btn_pick.setFixedSize(self._SZ, self._SZ)
        self._btn_pick.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_pick.setToolTip(tooltip)
        self._btn_pick.setStyleSheet(
            f"QPushButton{{background:transparent;color:{C['text_dim']};"
            f"border:1px dashed {C['border_bright']};border-radius:8px;"
            f"font-size:24px;font-weight:300;padding:0;}}"
            f"QPushButton:hover{{color:{C['accent']};border-color:{C['accent']};"
            f"background:rgba(124,107,255,0.08);}}"
            f"QPushButton:pressed{{background:rgba(124,107,255,0.16);}}"
        )
        self._btn_pick.clicked.connect(self._on_pick)

        self._thumb = QLabel(self)
        self._thumb.setGeometry(0, 0, self._SZ, self._SZ)
        self._thumb.setScaledContents(True)
        self._thumb.setStyleSheet("border-radius:8px;")
        self._thumb.setVisible(False)

        self._btn_clear = QPushButton("×", self)
        self._btn_clear.setFixedSize(16, 16)
        self._btn_clear.move(self._SZ - 18, 2)
        self._btn_clear.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_clear.setStyleSheet(
            f"QPushButton{{background:{C['bg2']};color:{C['text_dim']};"
            f"border:1px solid {C['border']};border-radius:3px;font-size:9px;padding:0;}}"
            f"QPushButton:hover{{color:{C['red']};border-color:{C['red']};background:{C['bg3']};}}"
        )
        self._btn_clear.setVisible(False)
        self._btn_clear.clicked.connect(self._on_clear)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.addWidget(self._btn_pick)

    def path(self) -> str:
        return self._path

    def set_path(self, path: str):
        if path and os.path.isfile(path):
            self._path = path
            pix = QPixmap(path).scaled(
                self._SZ, self._SZ,
                Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                Qt.TransformationMode.SmoothTransformation,
            )
            self._thumb.setPixmap(pix)
            self._thumb.setVisible(True)
            self._btn_pick.setVisible(False)
            self._btn_clear.setVisible(True)
        else:
            self._clear_state()

    def _clear_state(self):
        self._path = ""
        self._thumb.setVisible(False)
        self._btn_pick.setVisible(True)
        self._btn_clear.setVisible(False)

    def _on_pick(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Choisir une image de référence", "",
            "Images (*.png *.jpg *.jpeg *.webp *.bmp);;Tous les fichiers (*)",
        )
        if path:
            self.set_path(path)
            self.picked.emit(path)

    def _on_clear(self):
        self._clear_state()
        self.cleared.emit()


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
        self._res_combo.addItem("1080p  (~$0.40 / 5 s)", "1080p")
        self._res_combo.addItem("720p  (~$0.20 / 5 s)", "720p")
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
            self._res_combo.addItem("1080p  (~$0.60/5s)", "1080p")
            self._res_combo.addItem("720p   (~$0.30/5s)", "720p")
            self._res_combo.addItem("480p   (~$0.16/5s)", "480p")
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
        self._dur_slider.setMinimum(4)
        self._dur_slider.setMaximum(15)
        self._dur_slider.setValue(5)
        self._dur_slider.setStyleSheet(_slider_style())
        self._dur_slider.valueChanged.connect(lambda v: self._dur_lbl.setText(f"Durée : {v} s"))
        dur_col.addWidget(self._dur_slider)
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


class _Kling4KForm(QWidget):
    """Formulaire Kling v3 4K T2V."""
    def __init__(self):
        super().__init__()
        self.setStyleSheet("background:transparent;")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(12)

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
        self._dur_lbl = QLabel("Durée : 5 s  (~$1.40)")
        self._dur_lbl.setStyleSheet(
            f"color:{C['text_secondary']};font-size:12px;background:transparent;"
        )
        dur_col.addWidget(self._dur_lbl)
        self._dur_slider = QSlider(Qt.Orientation.Horizontal)
        self._dur_slider.setMinimum(3)
        self._dur_slider.setMaximum(15)
        self._dur_slider.setValue(5)
        self._dur_slider.setStyleSheet(_slider_style())
        self._dur_slider.valueChanged.connect(self._update_dur_label)
        dur_col.addWidget(self._dur_slider)
        params_row.addLayout(dur_col, 2)

        note_col = QVBoxLayout()
        note_col.setSpacing(4)
        note = QLabel("4K · Audio natif inclus")
        note.setStyleSheet(
            f"color:{C['accent']};font-size:11px;font-weight:700;background:transparent;"
        )
        note_col.addWidget(note)
        note2 = QLabel("$0.28–$0.39 / seconde")
        note2.setStyleSheet(
            f"color:{C['text_dim']};font-size:10px;"
            f"font-family:'Consolas',monospace;background:transparent;"
        )
        note_col.addWidget(note2)
        note_col.addStretch()
        params_row.addLayout(note_col, 1)

        lay.addLayout(params_row)

    def _update_dur_label(self, val: int):
        self._dur_lbl.setText(f"Durée : {val} s  (~${val * 0.28:.2f})")

    def get_params(self) -> dict:
        return {
            "mode":            "t2v",
            "variant":         "4k",
            "prompt":          self._prompt.toPlainText().strip(),
            "negative_prompt": self._neg.toPlainText().strip(),
            "duration":        self._dur_slider.value(),
            "generate_audio":  True,
            "shot_type":       "customize",
        }

    def error(self) -> str:
        if not self._prompt.toPlainText().strip():
            return "Le prompt est requis pour Kling v3 4K."
        return ""


class _Veo31Form(QWidget):
    """Formulaire Veo 3.1 T2V."""
    def __init__(self):
        super().__init__()
        self.setStyleSheet("background:transparent;")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(12)

        # Caractéristiques fixes
        note_card = QWidget()
        note_card.setStyleSheet(
            f"QWidget{{background:rgba(78,205,196,0.06);"
            f"border:1px solid {C['accent_dim']};border-radius:8px;}}"
        )
        note_lay = QHBoxLayout(note_card)
        note_lay.setContentsMargins(14, 10, 14, 10)
        note_lay.setSpacing(20)
        for label, value in [
            ("Durée", "8 s (fixe)"),
            ("Résolution", "1080p"),
            ("Audio", "Natif"),
            ("Coût", "~$1.00 / vidéo"),
        ]:
            col = QVBoxLayout()
            col.setSpacing(2)
            lbl = QLabel(label.upper())
            lbl.setStyleSheet(
                f"color:{C['text_dim']};font-size:9px;"
                f"letter-spacing:1px;background:transparent;"
            )
            val_lbl = QLabel(value)
            val_lbl.setStyleSheet(
                f"color:{C['accent']};font-size:12px;font-weight:700;background:transparent;"
            )
            col.addWidget(lbl)
            col.addWidget(val_lbl)
            note_lay.addLayout(col)
        note_lay.addStretch()
        lay.addWidget(note_card)

        self._prompt = QTextEdit()
        self._prompt.setPlaceholderText(
            "Décrivez la scène en détail — Veo 3.1 génère vidéo + audio haute qualité…\n"
            "(FR accepté, traduit automatiquement en anglais)"
        )
        self._prompt.setMinimumHeight(120)
        self._prompt.setMaximumHeight(200)
        self._prompt.setStyleSheet(_prompt_style())
        lay.addWidget(self._prompt)

    def get_params(self) -> dict:
        return {"prompt": self._prompt.toPlainText().strip()}

    def error(self) -> str:
        if not self._prompt.toPlainText().strip():
            return "Le prompt est requis pour Veo 3.1."
        return ""


class _HappyHorseForm(QWidget):
    """Formulaire Happy Horse 1.0 — T2V ou I2V."""
    def __init__(self, mode: str = "t2v"):
        super().__init__()
        self._mode = mode
        self.setStyleSheet("background:transparent;")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(12)

        if mode == "i2v":
            self._img = _ImagePicker("Image de départ (requis)")
            lay.addWidget(self._img)

        self._prompt = QTextEdit()
        self._prompt.setPlaceholderText(
            "Décrivez la scène… (FR accepté, traduit automatiquement en anglais)"
        )
        self._prompt.setMinimumHeight(90)
        self._prompt.setMaximumHeight(150)
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
        self._res_combo.addItem("1080p  (~$0.28/s)", "1080p")
        self._res_combo.addItem("720p  (~$0.14/s)", "720p")
        self._res_combo.currentIndexChanged.connect(self._update_dur_label)
        res_col.addWidget(self._res_combo)
        params_row.addLayout(res_col, 1)

        ratio_col = QVBoxLayout()
        ratio_col.setSpacing(6)
        ratio_lbl = QLabel("Format :")
        ratio_lbl.setStyleSheet(f"color:{C['text_secondary']};font-size:12px;background:transparent;")
        ratio_col.addWidget(ratio_lbl)
        self._ratio_combo = QComboBox()
        self._ratio_combo.setStyleSheet(_combo_style())
        for lbl2, val in [("16:9 — Paysage", "16:9"), ("9:16 — Portrait", "9:16"), ("1:1 — Carré", "1:1")]:
            self._ratio_combo.addItem(lbl2, val)
        ratio_col.addWidget(self._ratio_combo)
        params_row.addLayout(ratio_col, 1)

        lay.addLayout(params_row)

        dur_col = QVBoxLayout()
        dur_col.setSpacing(6)
        self._dur_lbl = QLabel("Durée : 5 s  (~$0.70)")
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
        lay.addLayout(dur_col)

    def _update_dur_label(self, *_):
        val  = self._dur_slider.value()
        rate = 0.28 if self._res_combo.currentData() == "1080p" else 0.14
        self._dur_lbl.setText(f"Durée : {val} s  (~${val * rate:.2f})")

    def get_params(self) -> dict | None:
        if self._mode == "i2v" and not self._img.path():
            return None
        p: dict = {
            "mode":         self._mode,
            "prompt":       self._prompt.toPlainText().strip(),
            "resolution":   self._res_combo.currentData() or "720p",
            "aspect_ratio": self._ratio_combo.currentData() or "16:9",
            "duration":     self._dur_slider.value(),
        }
        if self._mode == "i2v":
            p["image_url"] = self._img.path()
        return p

    def error(self) -> str:
        if not self._prompt.toPlainText().strip():
            return "Le prompt est requis pour Happy Horse."
        if self._mode == "i2v" and not self._img.path():
            return "Image de départ requise pour Happy Horse I2V."
        return ""


class _KlingO3Form(QWidget):
    """Formulaire Kling O3 4K — T2V ou I2V."""
    def __init__(self, mode: str = "t2v"):
        super().__init__()
        self._mode = mode
        self.setStyleSheet("background:transparent;")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(12)

        # Badge 4K
        badge = QLabel("4K · ~$0.42/s · Audio optionnel")
        badge.setStyleSheet(
            f"color:{C['accent']};font-size:11px;font-weight:700;background:transparent;"
        )
        lay.addWidget(badge)

        if mode == "i2v":
            self._img = _ImagePicker("Image de départ (requis)")
            lay.addWidget(self._img)

        self._prompt = QTextEdit()
        self._prompt.setPlaceholderText(
            "Décrivez la scène… (FR accepté, traduit automatiquement en anglais)"
        )
        self._prompt.setMinimumHeight(90)
        self._prompt.setMaximumHeight(150)
        self._prompt.setStyleSheet(_prompt_style())
        lay.addWidget(self._prompt)

        params_row = QHBoxLayout()
        params_row.setSpacing(16)

        dur_col = QVBoxLayout()
        dur_col.setSpacing(6)
        self._dur_lbl = QLabel("Durée : 5 s  (~$2.10)")
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
        self._audio_chk.setChecked(False)
        self._audio_chk.setStyleSheet(f"color:{C['text_primary']};font-size:12px;background:transparent;")
        audio_col.addWidget(self._audio_chk)
        audio_col.addStretch()
        params_row.addLayout(audio_col, 1)

        lay.addLayout(params_row)

    def _update_dur_label(self, val: int):
        self._dur_lbl.setText(f"Durée : {val} s  (~${val * 0.42:.2f})")

    def get_params(self) -> dict | None:
        if self._mode == "i2v" and not self._img.path():
            return None
        p: dict = {
            "mode":           self._mode,
            "prompt":         self._prompt.toPlainText().strip(),
            "duration":       self._dur_slider.value(),
            "generate_audio": self._audio_chk.isChecked(),
        }
        if self._mode == "i2v":
            p["image_url"] = self._img.path()
        return p

    def error(self) -> str:
        if not self._prompt.toPlainText().strip():
            return "Le prompt est requis pour Kling O3 4K."
        if self._mode == "i2v" and not self._img.path():
            return "Image de départ requise pour Kling O3 I2V."
        return ""


class _PixVerseV6Form(QWidget):
    """Formulaire PixVerse v6 T2V."""
    _PRICE = {"360p": 0.025, "540p": 0.05, "720p": 0.075, "1080p": 0.115}

    def __init__(self):
        super().__init__()
        self.setStyleSheet("background:transparent;")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(12)

        self._prompt = QTextEdit()
        self._prompt.setPlaceholderText(
            "Décrivez la scène… (FR accepté, traduit automatiquement en anglais)"
        )
        self._prompt.setMinimumHeight(90)
        self._prompt.setMaximumHeight(150)
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
        self._res_combo.addItem("1080p  (~$0.115/s)", "1080p")
        self._res_combo.addItem("720p   (~$0.075/s)", "720p")
        self._res_combo.addItem("540p   (~$0.050/s)", "540p")
        self._res_combo.addItem("360p   (~$0.025/s)", "360p")
        self._res_combo.currentIndexChanged.connect(self._update_dur_label)
        res_col.addWidget(self._res_combo)
        params_row.addLayout(res_col, 1)

        ratio_col = QVBoxLayout()
        ratio_col.setSpacing(6)
        ratio_lbl = QLabel("Format :")
        ratio_lbl.setStyleSheet(f"color:{C['text_secondary']};font-size:12px;background:transparent;")
        ratio_col.addWidget(ratio_lbl)
        self._ratio_combo = QComboBox()
        self._ratio_combo.setStyleSheet(_combo_style())
        for lbl2, val in [("16:9 — Paysage", "16:9"), ("9:16 — Portrait", "9:16"), ("1:1 — Carré", "1:1")]:
            self._ratio_combo.addItem(lbl2, val)
        ratio_col.addWidget(self._ratio_combo)
        params_row.addLayout(ratio_col, 1)

        lay.addLayout(params_row)

        dur_row = QHBoxLayout()
        dur_row.setSpacing(16)

        dur_col = QVBoxLayout()
        dur_col.setSpacing(6)
        self._dur_lbl = QLabel("Durée : 5 s  (~$0.58)")
        self._dur_lbl.setStyleSheet(f"color:{C['text_secondary']};font-size:12px;background:transparent;")
        dur_col.addWidget(self._dur_lbl)
        self._dur_slider = QSlider(Qt.Orientation.Horizontal)
        self._dur_slider.setMinimum(3)
        self._dur_slider.setMaximum(8)
        self._dur_slider.setValue(5)
        self._dur_slider.setStyleSheet(_slider_style())
        self._dur_slider.valueChanged.connect(self._update_dur_label)
        dur_col.addWidget(self._dur_slider)
        dur_hints = QLabel("3 s              5 s              8 s")
        dur_hints.setStyleSheet(
            f"color:{C['text_dim']};font-size:9px;font-family:'Consolas',monospace;background:transparent;"
        )
        dur_col.addWidget(dur_hints)
        dur_row.addLayout(dur_col, 2)

        audio_col = QVBoxLayout()
        audio_col.setSpacing(6)
        audio_lbl = QLabel("Audio :")
        audio_lbl.setStyleSheet(f"color:{C['text_secondary']};font-size:12px;background:transparent;")
        audio_col.addWidget(audio_lbl)
        self._audio_chk = QCheckBox("Générer l'audio")
        self._audio_chk.setChecked(False)
        self._audio_chk.setStyleSheet(f"color:{C['text_primary']};font-size:12px;background:transparent;")
        audio_col.addWidget(self._audio_chk)
        audio_col.addStretch()
        dur_row.addLayout(audio_col, 1)

        lay.addLayout(dur_row)

    def _update_dur_label(self, *_):
        val  = self._dur_slider.value()
        rate = self._PRICE.get(self._res_combo.currentData() or "720p", 0.075)
        self._dur_lbl.setText(f"Durée : {val} s  (~${val * rate:.2f})")

    def get_params(self) -> dict:
        return {
            "prompt":         self._prompt.toPlainText().strip(),
            "resolution":     self._res_combo.currentData() or "720p",
            "aspect_ratio":   self._ratio_combo.currentData() or "16:9",
            "duration":       self._dur_slider.value(),
            "generate_audio": self._audio_chk.isChecked(),
        }

    def error(self) -> str:
        if not self._prompt.toPlainText().strip():
            return "Le prompt est requis pour PixVerse v6."
        return ""


class _Sora2Form(QWidget):
    """Formulaire Sora 2 T2V."""
    def __init__(self):
        super().__init__()
        self.setStyleSheet("background:transparent;")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(12)

        note_card = QWidget()
        note_card.setStyleSheet(
            f"QWidget{{background:transparent;border:1px solid {C['accent_dim']};border-radius:8px;}}"
        )
        note_lay = QHBoxLayout(note_card)
        note_lay.setContentsMargins(14, 10, 14, 10)
        note_lay.setSpacing(20)
        for label, value in [
            ("Durée", "4 s (fixe)"),
            ("Résolution", "1080p"),
            ("Coût", "~$0.40 / vidéo"),
        ]:
            col = QVBoxLayout()
            col.setSpacing(2)
            lbl = QLabel(label.upper())
            lbl.setStyleSheet(
                f"color:{C['text_dim']};font-size:9px;letter-spacing:1px;background:transparent;"
            )
            val_lbl = QLabel(value)
            val_lbl.setStyleSheet(
                f"color:{C['accent']};font-size:12px;font-weight:700;background:transparent;"
            )
            col.addWidget(lbl)
            col.addWidget(val_lbl)
            note_lay.addLayout(col)
        note_lay.addStretch()
        lay.addWidget(note_card)

        self._prompt = QTextEdit()
        self._prompt.setPlaceholderText(
            "Décrivez la scène en détail — Sora 2 génère une vidéo 1080p haute qualité…\n"
            "(FR accepté, traduit automatiquement en anglais)"
        )
        self._prompt.setMinimumHeight(100)
        self._prompt.setMaximumHeight(180)
        self._prompt.setStyleSheet(_prompt_style())
        lay.addWidget(self._prompt)

        ratio_col = QVBoxLayout()
        ratio_col.setSpacing(6)
        ratio_lbl = QLabel("Format :")
        ratio_lbl.setStyleSheet(f"color:{C['text_secondary']};font-size:12px;background:transparent;")
        ratio_col.addWidget(ratio_lbl)
        self._ratio_combo = QComboBox()
        self._ratio_combo.setStyleSheet(_combo_style())
        for lbl2, val in [("16:9 — Paysage", "16:9"), ("9:16 — Portrait", "9:16"), ("1:1 — Carré", "1:1")]:
            self._ratio_combo.addItem(lbl2, val)
        ratio_col.addWidget(self._ratio_combo)
        lay.addLayout(ratio_col)

    def get_params(self) -> dict:
        return {
            "prompt":       self._prompt.toPlainText().strip(),
            "aspect_ratio": self._ratio_combo.currentData() or "16:9",
        }

    def error(self) -> str:
        if not self._prompt.toPlainText().strip():
            return "Le prompt est requis pour Sora 2."
        return ""


# ── Tab principal ──────────────────────────────────────────────────────────────

# Consigne injectée quand une « Mapping source » est fournie (image verrouillée).
_MAPPING_LOCK = (
    "The first frame must exactly match the reference image: identical "
    "subject, identical perspective, identical window/element positions, "
    "identical proportions and architecture. Do not redraw, reframe, or "
    "alter the geometry of the structure. Static locked-off camera, fixed "
    "frame, no camera movement (no pan, no tilt, no zoom in or out, no "
    "dolly, no rotation, no perspective change). The facade/object stays "
    "geometrically identical to the reference for the whole clip; only "
    "lighting, time of day, atmosphere, colors and background may change "
    "as described next."
)


class TabVideoEngines(QWidget):
    """Onglet génération directe multi-moteurs."""
    generation_done = pyqtSignal(dict)

    _ENGINES = [
        ("Seedance 2.0 — T2V  (~$0.30/s)",            "seedance_t2v",      True),
        ("Seedance Fast — T2V  (~$0.09/s)",             "seedance_fast_t2v", True),
        ("Happy Horse 1.0 — T2V  ($0.14-0.28/s) ★",   "happy_horse_t2v",   True),
        ("Happy Horse 1.0 — I2V  ($0.14-0.28/s)",      "happy_horse_i2v",   True),
        ("Kling O3 4K — T2V  (~$0.42/s)",              "kling_o3_t2v",      True),
        ("Kling O3 4K — I2V  (~$0.42/s)",              "kling_o3_i2v",      True),
        ("Kling v3 Pro — I2V  ($0.112-0.196/s)",       "kling_i2v",         True),
        ("Kling v3 Pro — T2V  ($0.112-0.196/s)",       "kling_t2v",         True),
        ("Kling v3 4K — T2V  ($0.28-0.39/s)",          "kling_4k_t2v",      True),
        ("PixVerse v6 — T2V  ($0.025-0.115/s)",        "pixverse_v6_t2v",   True),
        ("PixVerse v4.5 — I2V  ($0.04-0.08/s)",        "pixverse_i2v",      True),
        ("Veo 3.1 — T2V  (~$1.00 / vidéo)",            "veo31_t2v",         True),
        ("Sora 2 — T2V  (~$0.40 / vidéo · 4 s)",      "sora2_t2v",         True),
    ]

    def __init__(self):
        super().__init__()
        self.setStyleSheet(f"background:{C['bg0']};")

        self._worker = None
        self._enhance_worker = None
        self._last_folder: str = ""

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
        # Réfs pour l'insertion optionnelle du sélecteur de styles VJ (PANDORA | Live).
        # Inertes pour Cinéma : enable_vj_style_selector() n'est jamais appelé là.
        self._main_lay = lay
        self._vj_style_combo = None
        self._ref_squares = None
        self._mapping_squares = None
        self._live_extra = 0   # nb de widgets Live insérés avant le prompt
        self._inj_preview_body = None
        self._inj_preview_open = False

        # ── En-tête ────────────────────────────────────────────────────────────
        lay.addWidget(HelpBlock("Génération Directe — Multi-moteurs IA", [
            "▸ Génération vidéo sans storyboard — idéal pour expérimenter rapidement avec différents modèles.",
            "▸ Seedance 2.0 : moteur principal (~$0.30/s) · Seedance Fast : version rapide (~$0.09/s).",
            "▸ Happy Horse 1.0 ★ : modèle Alibaba #1 Video Arena, 720p ou 1080p, T2V + I2V ($0.14–0.28/s).",
            "▸ Kling O3 4K : dernier Kling, résolution 4K, T2V + I2V (~$0.42/s).",
            "▸ Kling v3 Pro : I2V + T2V ($0.112–0.196/s) · Kling v3 4K : T2V ultra-def ($0.28–0.39/s).",
            "▸ PixVerse v6 : T2V 360p–1080p avec audio optionnel ($0.025–0.115/s).",
            "▸ Veo 3.1 : modèle Google, audio natif, 8 s fixes, 1080p (~$1.00/vidéo).",
            "▸ Sora 2 : modèle OpenAI, 4 s fixes, 1080p, haute qualité (~$0.40/vidéo).",
            "▸ Les prompts en français sont traduits automatiquement en anglais avant envoi.",
        ], C))

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
                mdl = self._engine_combo.model()
                item = mdl.item(idx)
                if item:
                    item.setEnabled(False)
                    item.setForeground(_QBrush(_QColor(C['text_dim'])))
        self._engine_combo.currentIndexChanged.connect(self._on_engine_changed)
        lay.addWidget(self._engine_combo)

        # Point d'insertion du sélecteur de styles VJ (Live) — juste avant le prompt
        self._vj_insert_index = lay.count()

        # ── Prompt header : label + bouton améliorer à droite ─────────────────
        _prompt_hdr = QHBoxLayout()
        _prompt_hdr.setContentsMargins(0, 0, 0, 0)
        _prompt_hdr.setSpacing(6)
        _prompt_hdr.addWidget(_section("Prompt"))
        _prompt_hdr.addStretch()
        self._btn_enhance = QPushButton()
        self._btn_enhance.setFixedSize(28, 28)
        self._btn_enhance.setToolTip("Améliorer le prompt avec Claude")
        self._btn_enhance.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_enhance.setStyleSheet(
            "QPushButton{background:transparent;border:none;border-radius:5px;padding:0;}"
            "QPushButton:hover{background:rgba(124,107,255,0.12);}"
            "QPushButton:pressed{background:rgba(124,107,255,0.20);}"
            "QPushButton:disabled{opacity:0.3;}"
        )
        _pn = claude_icon_pixmap(16, C["text_dim"])
        _ph = claude_icon_pixmap(16, C["accent"])
        if not _pn.isNull():
            install_hover_icon(self._btn_enhance, _pn, _ph, icon_size=16)
        else:
            self._btn_enhance.setText("☁")
        self._btn_enhance.clicked.connect(self._on_enhance)
        _lbl_enh = QLabel("Améliorer le prompt")
        _lbl_enh.setStyleSheet(
            f"color:{C['text_dim']};font-size:10px;background:transparent;border:none;"
        )
        _prompt_hdr.addWidget(_lbl_enh)
        _prompt_hdr.addWidget(self._btn_enhance)
        lay.addLayout(_prompt_hdr)

        # ── Formulaires empilés ────────────────────────────────────────────────
        self._stack = QStackedWidget()
        self._forms = [
            _SeedanceT2VForm("seedance-2.0"),
            _SeedanceT2VForm("seedance-2.0-fast"),
            _HappyHorseForm("t2v"),
            _HappyHorseForm("i2v"),
            _KlingO3Form("t2v"),
            _KlingO3Form("i2v"),
            _KlingI2VForm(),
            _KlingT2VForm(),
            _Kling4KForm(),
            _PixVerseV6Form(),
            _PixVerseForm(),
            _Veo31Form(),
            _Sora2Form(),
        ]
        for form in self._forms:
            self._stack.addWidget(form)
        lay.addWidget(self._stack)

        lay.addWidget(_divider())

        # ── Bouton génération ──────────────────────────────────────────────────
        self._btn_generate = QPushButton("▶  Générer")
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

        # PANDORA | Live : active les outils VJ / Mapping (génération de loops)
        try:
            self.enable_vj_style_selector()
            self.enable_reference_images()
            self.enable_mapping_source()
            self.enable_injection_preview()
        except Exception:
            pass

    # ── Changement moteur ──────────────────────────────────────────────────────

    def _on_engine_changed(self, idx: int):
        # Chaque moteur a son propre formulaire (donc son propre champ prompt).
        # On reporte le prompt du moteur précédent vers le nouveau pour ne pas
        # « perdre » ce que l'utilisateur a écrit en changeant de moteur.
        prev_idx = self._stack.currentIndex()
        carried = ""
        if 0 <= prev_idx < len(self._forms):
            prev_prompt = getattr(self._forms[prev_idx], "_prompt", None)
            if prev_prompt is not None:
                carried = prev_prompt.toPlainText()

        self._stack.setCurrentIndex(idx)

        if carried:
            new_prompt = getattr(self._forms[idx], "_prompt", None)
            if new_prompt is not None and not new_prompt.toPlainText().strip():
                new_prompt.setPlainText(carried)

    # ── Sélecteur de styles VJ (PANDORA | Live uniquement) ──────────────────────

    def enable_vj_style_selector(self):
        """Insère un menu déroulant « Template de style » (20 styles VJ) au-dessus du
        prompt. Choisir un style charge son prompt de loop dans le champ prompt du
        moteur courant. Appelé seulement par PANDORA | Live — Cinéma n'est pas touché.
        """
        if self._vj_style_combo is not None:
            return
        import core.vj_styles as vj

        self._vj_section = _section(translate("Template de style"))
        self._vj_style_combo = QComboBox()
        self._vj_style_combo.setMinimumHeight(34)
        self._vj_style_combo.setStyleSheet(_combo_style())
        self._vj_style_combo.addItem(translate("Aucun style"), "")
        for s in vj.get_styles():
            self._vj_style_combo.addItem(vj.localized_name(s), s["key"])
        self._vj_style_combo.currentIndexChanged.connect(self._on_vj_style_changed)

        base = self._vj_insert_index + self._live_extra
        self._main_lay.insertWidget(base, self._vj_section)
        self._main_lay.insertWidget(base + 1, self._vj_style_combo)
        self._live_extra += 2

    def _on_vj_style_changed(self, _idx: int):
        key = self._vj_style_combo.currentData()
        if not key:
            return
        import core.vj_styles as vj
        st = vj.get_style(key)
        if not st:
            return
        # Charge le prompt du style dans le champ prompt du moteur courant.
        form = self._current_form()
        prompt_widget = getattr(form, "_prompt", None)
        if prompt_widget is not None:
            prompt_widget.setPlainText(st["prompt"])

    # ── Images de référence (carrés « + ») — PANDORA | Live uniquement ──────────

    def enable_reference_images(self, n: int = 3):
        """Insère une rangée de carrés « + » pour ajouter jusqu'à n images de référence.
        Les chemins choisis sont injectés dans params['ref_images'] à la génération.
        Appelé seulement par PANDORA | Live — Cinéma n'est pas touché.
        """
        if self._ref_squares is not None:
            return
        cont = QWidget()
        cont.setStyleSheet("background:transparent;")
        cl = QVBoxLayout(cont)
        cl.setContentsMargins(0, 0, 0, 0)
        cl.setSpacing(6)
        cl.addWidget(_section(translate("Images de référence")))
        row = QHBoxLayout()
        row.setSpacing(8)
        self._ref_squares = []
        for _ in range(n):
            sq = _RefSquare(tooltip=translate("Ajouter une image de référence"))
            self._ref_squares.append(sq)
            row.addWidget(sq)
        row.addStretch()
        cl.addLayout(row)

        self._main_lay.insertWidget(self._vj_insert_index + self._live_extra, cont)
        self._live_extra += 1

    def _collect_ref_images(self) -> list:
        if not self._ref_squares:
            return []
        return [s.path() for s in self._ref_squares
                if s.path() and os.path.isfile(s.path())][:3]

    # ── Mapping source (image verrouillée) — PANDORA | Live uniquement ──────────

    def enable_mapping_source(self, n: int = 2):
        """Insère une rangée de carrés « + » pour l'image à mapper (façade, objet…).
        Quand une image est présente, on injecte une consigne forte : Seedance doit
        garder l'image IDENTIQUE (caméra fixe, pas de zoom/pan/rotation) — seuls la
        lumière, l'ambiance et le fond peuvent changer. Live uniquement.
        """
        if self._mapping_squares is not None:
            return
        cont = QWidget()
        cont.setStyleSheet("background:transparent;")
        cl = QVBoxLayout(cont)
        cl.setContentsMargins(0, 0, 0, 0)
        cl.setSpacing(6)
        cl.addWidget(_section(translate("Mapping source")))
        hint = QLabel(translate(
            "Image du lieu/objet à mapper — gardée identique (caméra fixe). "
            "Seuls lumière, ambiance et fond peuvent changer via le prompt."
        ))
        hint.setWordWrap(True)
        hint.setStyleSheet(
            f"color:{C['text_dim']};font-size:10px;background:transparent;border:none;"
        )
        cl.addWidget(hint)
        row = QHBoxLayout()
        row.setSpacing(8)
        self._mapping_squares = []
        for _ in range(n):
            sq = _RefSquare(tooltip=translate("Ajouter l'image à mapper"))
            self._mapping_squares.append(sq)
            row.addWidget(sq)
        row.addStretch()
        cl.addLayout(row)

        self._main_lay.insertWidget(self._vj_insert_index + self._live_extra, cont)
        self._live_extra += 1

    def _collect_mapping_sources(self) -> list:
        if not self._mapping_squares:
            return []
        return [s.path() for s in self._mapping_squares
                if s.path() and os.path.isfile(s.path())][:2]

    # ── Contexte injecté (aperçu en rouge) — PANDORA | Live uniquement ──────────

    def enable_injection_preview(self):
        """Encart repliable « Contexte injecté » : montre le prompt complet envoyé,
        avec le texte utilisateur en clair et tout l'ajout automatique en rouge.
        À appeler après enable_vj_style_selector / reference_images / mapping_source.
        """
        if self._inj_preview_body is not None:
            return

        cont = QWidget()
        cont.setStyleSheet("background:transparent;")
        cl = QVBoxLayout(cont)
        cl.setContentsMargins(0, 0, 0, 0)
        cl.setSpacing(6)

        self._inj_header = QPushButton("▶  ◈ " + translate("Contexte injecté"))
        self._inj_header.setFlat(True)
        self._inj_header.setCursor(Qt.CursorShape.PointingHandCursor)
        self._inj_header.setStyleSheet(
            f"QPushButton{{background:transparent;color:{C['red']};"
            f"font-size:10px;font-weight:700;letter-spacing:1px;"
            f"border:none;text-align:left;padding:0;}}"
            f"QPushButton:hover{{color:#ff7d8a;}}"
        )
        self._inj_header.clicked.connect(self._toggle_injection_preview)
        cl.addWidget(self._inj_header)

        self._inj_preview_body = QLabel("")
        self._inj_preview_body.setWordWrap(True)
        self._inj_preview_body.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )
        self._inj_preview_body.setVisible(False)
        self._inj_preview_body.setStyleSheet(
            f"color:{C['text_secondary']};font-size:10px;"
            f"font-family:'Consolas',monospace;"
            f"background:rgba(255,79,106,0.05);border:1px solid rgba(255,79,106,0.25);"
            f"border-radius:6px;padding:8px 10px;"
        )
        cl.addWidget(self._inj_preview_body)

        idx = self._main_lay.indexOf(self._btn_generate)
        if idx < 0:
            idx = self._main_lay.count()
        self._main_lay.insertWidget(idx, cont)

        # Mises à jour en direct
        for f in self._forms:
            pw = getattr(f, "_prompt", None)
            if pw is not None:
                pw.textChanged.connect(self._refresh_injection_preview)
        if self._vj_style_combo is not None:
            self._vj_style_combo.currentIndexChanged.connect(self._refresh_injection_preview)
        for sq in (self._ref_squares or []) + (self._mapping_squares or []):
            sq.picked.connect(lambda *_: self._refresh_injection_preview())
            sq.cleared.connect(self._refresh_injection_preview)
        self._engine_combo.currentIndexChanged.connect(self._refresh_injection_preview)

        self._refresh_injection_preview()

    def _toggle_injection_preview(self):
        self._inj_preview_open = not self._inj_preview_open
        self._inj_preview_body.setVisible(self._inj_preview_open)
        self._inj_header.setText(
            ("▼" if self._inj_preview_open else "▶") + "  ◈ " + translate("Contexte injecté")
        )

    def _refresh_injection_preview(self):
        if self._inj_preview_body is None:
            return
        import html as _html
        RED  = C["red"]
        SEC  = C["text_secondary"]
        DIM  = C["text_dim"]

        form = self._current_form()
        pw   = getattr(form, "_prompt", None)
        user = pw.toPlainText().strip() if pw is not None else ""
        maps = self._collect_mapping_sources()
        refs = self._collect_ref_images()

        segments = []
        if maps:
            segments.append(
                f"<span style='color:{RED};'>{_html.escape(_MAPPING_LOCK)}</span>"
            )
        if user:
            segments.append(f"<span style='color:{SEC};'>{_html.escape(user)}</span>")
        elif not maps:
            segments.append(f"<span style='color:{DIM};'>({translate('prompt vide')})</span>")

        notes = []
        n_img = len(maps) + len(refs)
        if n_img:
            _t = f"+ {n_img} {translate('image(s) jointe(s) en référence')}"
            if maps:
                _t += f" ({translate('dont mapping verrouillé')})"
            notes.append(_t)
        notes.append("+ " + translate("traduction automatique en anglais avant envoi"))

        notes_html = "<br>".join(
            f"<span style='color:{RED};'>{_html.escape(n)}</span>" for n in notes
        )
        body = " ".join(segments)
        if notes_html:
            body += "<br><br>" + notes_html
        self._inj_preview_body.setText(body)

    # ── Amélioration Claude ────────────────────────────────────────────────────

    def _on_enhance(self):
        form = self._current_form()
        prompt_widget = getattr(form, "_prompt", None)
        if not prompt_widget:
            return
        text = prompt_widget.toPlainText().strip()
        if not text:
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.warning(self, "Prompt vide", "Écris un prompt à améliorer !")
            return
        self._btn_enhance.setEnabled(False)
        self._enhance_worker = EnhanceWorker(text)
        self._enhance_worker.finished.connect(self._on_enhance_done)
        self._enhance_worker.failed.connect(self._on_enhance_failed)
        self._enhance_worker.start()

    def _on_enhance_done(self, enhanced: str):
        form = self._current_form()
        prompt_widget = getattr(form, "_prompt", None)
        if prompt_widget:
            prompt_widget.setPlainText(enhanced)
        self._btn_enhance.setEnabled(True)

    def _on_enhance_failed(self, error: str):
        self._btn_enhance.setEnabled(True)
        from PyQt6.QtWidgets import QMessageBox
        QMessageBox.warning(self, "Amélioration impossible", error)

    def _current_form(self):
        return self._forms[self._engine_combo.currentIndex()]

    def _current_engine_key(self) -> str:
        return self._engine_combo.currentData() or "seedance_t2v"

    # ── Génération ─────────────────────────────────────────────────────────────

    def _on_generate(self):
        if self._worker and self._worker.isRunning():
            return

        form = self._current_form()
        maps = self._collect_mapping_sources()
        refs = self._collect_ref_images()
        err  = form.error()
        # Une image de référence/mapping conditionne la génération : un prompt texte
        # vide est alors acceptable (on ne bloque pas sur « prompt requis »).
        if err and (maps or refs) and "prompt" in err.lower():
            err = ""
        if err:
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.warning(self, "Paramètre manquant", err)
            return

        key    = self._current_engine_key()
        params = form.get_params()
        if params is None:
            return

        # Images de référence + mapping → reference-to-video côté Seedance.
        # L'image de mapping passe en premier (référence dominante @Image1).
        all_refs = (maps + refs)[:4]
        if all_refs:
            params["ref_images"] = all_refs

        # Mapping : verrouille l'image source (caméra fixe, géométrie identique).
        # Seuls lumière / ambiance / fond peuvent changer via le prompt utilisateur.
        if maps:
            user_p = (params.get("prompt") or "").strip()
            params["prompt"] = f"{_MAPPING_LOCK} {user_p}".strip()

        if key in ("seedance_t2v", "seedance_fast_t2v"):
            from core.worker import GenerationWorker
            self._worker = GenerationWorker(params)
        elif key in ("happy_horse_t2v", "happy_horse_i2v"):
            from api.video_engines import HappyHorseWorker
            self._worker = HappyHorseWorker(params)
        elif key in ("kling_o3_t2v", "kling_o3_i2v"):
            from api.video_engines import KlingO3Worker
            self._worker = KlingO3Worker(params)
        elif key == "veo31_t2v":
            from api.video_engines import Veo3Worker
            self._worker = Veo3Worker(params)
        elif key == "kling_4k_t2v":
            from api.video_engines import KlingWorker
            params["variant"] = "4k"
            self._worker = KlingWorker(params)
        elif key in ("kling_i2v", "kling_t2v"):
            from api.video_engines import KlingWorker
            self._worker = KlingWorker(params)
        elif key == "pixverse_v6_t2v":
            from api.video_engines import PixVerseV6Worker
            self._worker = PixVerseV6Worker(params)
        elif key == "sora2_t2v":
            from api.video_engines import Sora2Worker
            self._worker = Sora2Worker(params)
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
        self._status_lbl.setText(translate(msg))

    def _on_finished(self, result: dict):
        self._btn_generate.setEnabled(True)
        self._btn_generate.setText("▶  Générer")
        self._progress.setValue(100)

        local = result.get("local_path", "")
        model = result.get("model", "")
        dur   = result.get("duration", 0)
        cost  = result.get("credits_used", 0)

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
            elif not ir.get("mock") and ir.get("error"):
                self._status_lbl.setText(f"✗  {translate('Téléchargement échoué :')} {ir['error'][:100]}")

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
            self._status_lbl.setText(translate("✓  Terminé (mode démo — aucune clé fal.ai)"))

    def _on_failed(self, err: str):
        self._btn_generate.setEnabled(True)
        self._btn_generate.setText("▶  Générer")
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
