"""
ui/dialog_draw_video.py — « Draw-to-Video » : dessiner sur une image du clip.

L'utilisateur choisit un instant du clip (curseur), dessine des marques colorées
(zones où appliquer un effet : feu, fumée…), puis valide. L'image annotée est
renvoyée et utilisée comme RÉFÉRENCE pour la génération ; le prompt est préfixé
d'une consigne demandant au moteur de remplacer les dessins par l'effet décrit.

Approximation du « Draw-to-Video » (pas d'endpoint scribble natif sur fal/Seedance) :
l'image annotée guide le moteur sur l'emplacement et la nature de l'effet.
"""

import os
import time
import subprocess

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QSlider, QSpinBox,
    QWidget,
)
from PyQt6.QtCore import Qt, QPoint
from PyQt6.QtGui import QImage, QPixmap, QPainter, QPen, QColor

from ui.styles import CP
from core.i18n import translate
from core.video_utils import get_ffmpeg_exe, get_ffprobe_exe, _NO_WINDOW


# Palette de dessin (couleurs vives = repères clairs pour le moteur)
_COLORS = ["#ff3b30", "#ff9500", "#ffcc00", "#34c759", "#0a84ff", "#bf5af2", "#ffffff", "#000000"]
_DISPLAY_W = 760   # largeur d'affichage/export de l'image annotée


def _probe_duration(path: str) -> float:
    try:
        out = subprocess.run(
            [get_ffprobe_exe(), "-v", "error", "-show_entries", "format=duration",
             "-of", "default=nw=1:nk=1", path],
            capture_output=True, text=True, timeout=30, creationflags=_NO_WINDOW)
        return max(0.0, float((out.stdout or "0").strip()))
    except Exception:
        return 0.0


def _extract_frame(path: str, t: float, out_path: str) -> bool:
    try:
        r = subprocess.run(
            [get_ffmpeg_exe(), "-y", "-ss", f"{max(0.0, t):.3f}", "-i", path,
             "-frames:v", "1", "-q:v", "2", out_path],
            capture_output=True, timeout=120, creationflags=_NO_WINDOW)
        return r.returncode == 0 and os.path.isfile(out_path) and os.path.getsize(out_path) > 0
    except Exception:
        return False


def _probe_fps(path: str) -> float:
    """Cadence (images/seconde) du flux vidéo, pour un vrai time code SMPTE."""
    try:
        out = subprocess.run(
            [get_ffprobe_exe(), "-v", "error", "-select_streams", "v:0",
             "-show_entries", "stream=r_frame_rate", "-of", "default=nw=1:nk=1", path],
            capture_output=True, text=True, timeout=30, creationflags=_NO_WINDOW)
        val = (out.stdout or "").strip()
        if "/" in val:
            num, den = val.split("/", 1)
            den = float(den)
            return float(num) / den if den else 0.0
        return float(val) if val else 0.0
    except Exception:
        return 0.0


def _format_tc(frame: int, fps: float) -> str:
    """Index d'image → time code SMPTE HH:MM:SS:FF."""
    f = max(1, int(round(fps)))
    frame = max(0, int(frame))
    total_s, ff = divmod(frame, f)
    hh, rem = divmod(total_s, 3600)
    mm, ss = divmod(rem, 60)
    return f"{hh:02d}:{mm:02d}:{ss:02d}:{ff:02d}"


class _DrawCanvas(QWidget):
    """Image de fond + calque de dessin transparent (trait libre)."""

    def __init__(self):
        super().__init__()
        self._base: QPixmap | None = None
        self._overlay: QImage | None = None
        self._last: QPoint | None = None
        self.pen_color = QColor(_COLORS[0])
        self.pen_width = 8
        self.eraser = False
        self.setMinimumSize(_DISPLAY_W, int(_DISPLAY_W * 9 / 16))
        self.setStyleSheet(f"background:{CP['bg0']};border:1px solid {CP['border']};border-radius:8px;")

    def set_base(self, pixmap: QPixmap):
        scaled = pixmap.scaledToWidth(_DISPLAY_W, Qt.TransformationMode.SmoothTransformation)
        self._base = scaled
        # On PRÉSERVE le dessin en cours tant que la taille ne change pas (scrub
        # entre images d'un même clip). Calque neuf seulement à la 1re image ou si
        # la taille diffère.
        if self._overlay is None or self._overlay.size() != scaled.size():
            self._overlay = QImage(scaled.size(), QImage.Format.Format_ARGB32)
            self._overlay.fill(Qt.GlobalColor.transparent)
        self.setFixedSize(scaled.size())
        self.update()

    def set_overlay(self, image_path: str):
        """Recharge un calque de dessin existant (ré-édition d'un dessin précédent)."""
        if self._base is None or not image_path or not os.path.isfile(image_path):
            return
        img = QImage(image_path)
        if img.isNull():
            return
        if img.size() != self._base.size():
            img = img.scaled(self._base.size(), Qt.AspectRatioMode.IgnoreAspectRatio,
                             Qt.TransformationMode.SmoothTransformation)
        self._overlay = img.convertToFormat(QImage.Format.Format_ARGB32)
        self.update()

    def clear_drawing(self):
        if self._overlay is not None:
            self._overlay.fill(Qt.GlobalColor.transparent)
            self.update()

    def has_base(self) -> bool:
        return self._base is not None

    def paintEvent(self, e):
        p = QPainter(self)
        if self._base is not None:
            p.drawPixmap(0, 0, self._base)
        if self._overlay is not None:
            p.drawImage(0, 0, self._overlay)
        p.end()

    def mousePressEvent(self, e):
        if self._overlay is not None and e.button() == Qt.MouseButton.LeftButton:
            self._last = e.position().toPoint()

    def mouseMoveEvent(self, e):
        if self._overlay is None or self._last is None:
            return
        cur = e.position().toPoint()
        p = QPainter(self._overlay)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        if self.eraser:
            p.setCompositionMode(QPainter.CompositionMode.CompositionMode_Clear)
            pen = QPen(QColor(0, 0, 0, 0), self.pen_width * 2)
        else:
            pen = QPen(self.pen_color, self.pen_width)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        p.setPen(pen)
        p.drawLine(self._last, cur)
        p.end()
        self._last = cur
        self.update()

    def mouseReleaseEvent(self, e):
        self._last = None

    def export(self, out_path: str) -> bool:
        if self._base is None:
            return False
        result = self._base.toImage().convertToFormat(QImage.Format.Format_ARGB32)
        p = QPainter(result)
        if self._overlay is not None:
            p.drawImage(0, 0, self._overlay)
        p.end()
        return result.save(out_path, "PNG")

    def export_overlay(self, out_path: str) -> bool:
        """Sauve le calque de dessin SEUL (transparent) → permet la ré-édition."""
        if self._overlay is None:
            return False
        return self._overlay.save(out_path, "PNG")


class DrawVideoDialog(QDialog):
    """Dialogue Draw-to-Video. result_path() = image annotée (ou '')."""

    def __init__(self, clip_path: str, out_dir: str, parent=None,
                 prev_overlay: str = "", prev_frame: int = 0):
        super().__init__(parent)
        self._clip = clip_path
        self._out_dir = out_dir
        self._result_path = ""
        self._overlay_path = ""              # calque seul (ré-édition)
        self._prev_overlay = prev_overlay or ""
        self._dur = _probe_duration(clip_path)
        self._fps = _probe_fps(clip_path) or 25.0
        self._frame = max(0, int(prev_frame))
        self.setWindowTitle(translate("Dessiner sur la vidéo — Draw-to-Video"))
        self.setStyleSheet(f"background:{CP['bg1']};")
        self.setMinimumWidth(_DISPLAY_W + 60)

        root = QVBoxLayout(self)
        root.setContentsMargins(20, 16, 20, 16)
        root.setSpacing(12)

        title = QLabel("✏  " + translate("Dessiner sur la vidéo"))
        title.setStyleSheet(f"color:{CP['text_primary']};font-size:15px;font-weight:700;background:transparent;")
        root.addWidget(title)

        hint = QLabel(translate(
            "Choisis l'instant, puis dessine pour REPÉRER les zones (entoure ce qu'il "
            "faut modifier, ou esquisse où ajouter un élément). Les traits servent "
            "seulement de repère : ils n'apparaîtront PAS dans la vidéo finale."))
        hint.setWordWrap(True)
        hint.setStyleSheet(f"color:{CP['text_dim']};font-size:11px;background:transparent;")
        root.addWidget(hint)

        # ── Curseur d'instant ───────────────────────────────────────────────────
        tl = QHBoxLayout()
        tl.setSpacing(8)
        tlbl = QLabel(translate("Time Code :"))
        tlbl.setStyleSheet(f"color:{CP['text_secondary']};font-size:11px;background:transparent;")
        tl.addWidget(tlbl)
        self._slider = QSlider(Qt.Orientation.Horizontal)
        _total_frames = max(0, int(round(self._dur * self._fps)) - 1)   # index image
        self._slider.setRange(0, _total_frames)
        self._slider.setValue(min(self._frame, _total_frames))
        self._slider.sliderReleased.connect(self._reload_frame)
        tl.addWidget(self._slider, 1)
        self._time_lbl = QLabel(_format_tc(self._slider.value(), self._fps))
        self._time_lbl.setStyleSheet(
            f"color:{CP['text_dim']};font-size:11px;font-family:Consolas,monospace;"
            f"background:transparent;")
        self._slider.valueChanged.connect(
            lambda v: self._time_lbl.setText(_format_tc(v, self._fps)))
        tl.addWidget(self._time_lbl)
        root.addLayout(tl)

        # ── Canevas de dessin ───────────────────────────────────────────────────
        self._canvas = _DrawCanvas()
        _cw = QWidget(); _cl = QHBoxLayout(_cw); _cl.setContentsMargins(0, 0, 0, 0)
        _cl.addStretch(); _cl.addWidget(self._canvas); _cl.addStretch()
        root.addWidget(_cw)

        # ── Outils : couleurs, taille, gomme, effacer ───────────────────────────
        tools = QHBoxLayout()
        tools.setSpacing(6)
        for c in _COLORS:
            b = QPushButton()
            b.setFixedSize(22, 22)
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.setStyleSheet(f"QPushButton{{background:{c};border:1px solid {CP['border_bright']};border-radius:11px;}}")
            b.clicked.connect(lambda _=False, col=c: self._set_color(col))
            tools.addWidget(b)
        tools.addSpacing(10)
        tools.addWidget(self._tlabel(translate("Taille")))
        self._size = QSpinBox()
        self._size.setRange(2, 60)
        self._size.setValue(8)
        self._size.valueChanged.connect(lambda v: setattr(self._canvas, "pen_width", v))
        tools.addWidget(self._size)
        self._btn_eraser = QPushButton(translate("Gomme"))
        self._btn_eraser.setCheckable(True)
        self._btn_eraser.setStyleSheet(self._tool_btn_ss())
        self._btn_eraser.clicked.connect(self._toggle_eraser)
        tools.addWidget(self._btn_eraser)
        btn_clear = QPushButton(translate("Effacer"))
        btn_clear.setStyleSheet(self._tool_btn_ss())
        btn_clear.clicked.connect(self._canvas.clear_drawing)
        tools.addWidget(btn_clear)
        tools.addStretch()
        root.addLayout(tools)

        # ── Boutons ─────────────────────────────────────────────────────────────
        btns = QHBoxLayout()
        btns.addStretch()
        cancel = QPushButton(translate("Annuler"))
        cancel.setStyleSheet(
            f"QPushButton{{background:{CP['bg3']};color:{CP['text_secondary']};"
            f"border:1px solid {CP['border']};border-radius:7px;font-size:12px;padding:7px 16px;}}"
            f"QPushButton:hover{{background:{CP['bg2']};}}")
        cancel.clicked.connect(self.reject)
        ok = QPushButton(translate("Valider"))
        ok.setStyleSheet(
            f"QPushButton{{background:{CP['accent']};color:#07080f;border:none;"
            f"border-radius:7px;font-size:12px;font-weight:700;padding:7px 18px;}}"
            f"QPushButton:hover{{background:#6eded6;}}")
        ok.clicked.connect(self._accept)
        btns.addWidget(cancel)
        btns.addWidget(ok)
        root.addLayout(btns)

        self._reload_frame()   # charge l'image du time code courant
        # Ré-édition : si un dessin existait déjà pour ce clip, on le restaure sur
        # le calque (éditable) au lieu d'ouvrir un schéma vierge.
        if self._prev_overlay:
            self._canvas.set_overlay(self._prev_overlay)

    def _tlabel(self, text):
        l = QLabel(text)
        l.setStyleSheet(f"color:{CP['text_secondary']};font-size:11px;background:transparent;")
        return l

    def _tool_btn_ss(self):
        return (
            f"QPushButton{{background:{CP['bg3']};color:{CP['text_secondary']};"
            f"border:1px solid {CP['border']};border-radius:6px;font-size:11px;padding:4px 12px;}}"
            f"QPushButton:checked{{background:rgba(78,205,196,0.16);color:{CP['accent']};"
            f"border-color:{CP['accent']};}}"
            f"QPushButton:hover{{border-color:{CP['accent_dim']};}}")

    def _set_color(self, c: str):
        self._canvas.pen_color = QColor(c)
        self._canvas.eraser = False
        self._btn_eraser.setChecked(False)

    def _toggle_eraser(self):
        self._canvas.eraser = self._btn_eraser.isChecked()

    def _reload_frame(self):
        t = self._slider.value() / (self._fps or 25.0)
        tmp = os.path.join(self._out_dir, "_frame_tmp.png")
        os.makedirs(self._out_dir, exist_ok=True)
        if _extract_frame(self._clip, t, tmp):
            pm = QPixmap(tmp)
            if not pm.isNull():
                self._canvas.set_base(pm)
                return
        # Repli : pas de frame (ffmpeg absent) → canevas vide gris
        if not self._canvas.has_base():
            blank = QPixmap(_DISPLAY_W, int(_DISPLAY_W * 9 / 16))
            blank.fill(QColor(CP['bg0']))
            self._canvas.set_base(blank)

    def _accept(self):
        ts = int(time.time())
        out = os.path.join(self._out_dir, f"drawtovideo_{ts}.png")
        if self._canvas.export(out):                       # image aplatie (réf. génération)
            self._result_path = out
        ov = os.path.join(self._out_dir, f"drawoverlay_{ts}.png")
        if self._canvas.export_overlay(ov):                # calque seul (ré-édition)
            self._overlay_path = ov
        self._frame = self._slider.value()
        self.accept()

    def result_path(self) -> str:
        return self._result_path

    def overlay_path(self) -> str:
        """Calque de dessin seul — à repasser en `prev_overlay` pour ré-éditer."""
        return self._overlay_path

    def frame_index(self) -> int:
        """Index d'image choisi — à repasser en `prev_frame` pour ré-éditer."""
        return self._frame
