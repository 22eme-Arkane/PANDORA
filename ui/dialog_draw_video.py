"""
ui/dialog_draw_video.py — « Draw-to-Video » : dessiner sur une image du clip.

L'utilisateur choisit un instant du clip sur une TIMELINE de monteur (playhead
saisissable à la souris, clic n'importe où = saut direct, molette/flèches =
±1 image, Maj+flèches = ±1 s), dessine des marques colorées (zones où
appliquer un effet : feu, fumée…), puis valide. L'image annotée est renvoyée
et utilisée comme RÉFÉRENCE/GUIDE pour la génération ; le prompt est préfixé
d'une consigne demandant au moteur de remplacer les dessins par l'effet décrit.

Réactivité du scrub : un worker QThread pré-extrait en tâche de fond un cache
de vignettes basse résolution (~1 image/s, plafonné à 120, hauteur 360 px).
Pendant le drag, la vignette la plus proche s'affiche INSTANTANÉMENT ; après
un débounce de 150 ms (et au relâchement), la frame PLEINE résolution exacte
est extraite pour dessiner dessus.

Approximation du « Draw-to-Video » (pas d'endpoint scribble natif sur
fal/Seedance) : l'image annotée guide le moteur sur l'emplacement et la nature
de l'effet.
"""

import os
import time
import hashlib
import subprocess

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QSpinBox,
    QWidget,
)
from PyQt6.QtCore import Qt, QPoint, QPointF, QRectF, QTimer, QThread, pyqtSignal
from PyQt6.QtGui import (
    QImage, QPixmap, QPainter, QPen, QColor, QCursor, QPolygonF,
)

from ui.styles import CP
from core.i18n import translate
from core.video_utils import get_ffmpeg_exe, get_ffprobe_exe, _NO_WINDOW


# Palette de dessin (couleurs vives = repères clairs pour le moteur)
_COLORS = ["#ff3b30", "#ff9500", "#ffcc00", "#34c759", "#0a84ff", "#bf5af2", "#ffffff", "#000000"]
_DISPLAY_W = 760   # largeur d'affichage/export de l'image annotée

_THUMB_H = 360       # hauteur des vignettes du cache de scrub (basse résolution)
_THUMB_MAX = 120     # plafond de vignettes pré-extraites (~1 image/s)
_DEBOUNCE_MS = 150   # délai avant extraction de la frame pleine résolution


def _rgba(hex_color: str, alpha: float) -> str:
    """#rrggbb → chaîne CSS rgba() (JAMAIS de suffixe hex-opacity sur fond sombre)."""
    h = hex_color.lstrip("#")
    return f"rgba({int(h[0:2], 16)},{int(h[2:4], 16)},{int(h[4:6], 16)},{alpha})"


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


# ── Cache de vignettes (worker) ────────────────────────────────────────────────

class _ThumbCacheWorker(QThread):
    """Pré-extrait N vignettes basse résolution réparties sur la durée du clip.

    Une seule passe ffmpeg (filtre fps) écrit les fichiers séquentiellement :
    le fichier i est considéré complet dès que le fichier i+1 existe, ce qui
    permet d'émettre les vignettes au fil de l'eau — la timeline devient
    réactive sans attendre la fin du cache.

    Signal de fin = `done` (JAMAIS `finished`, signal natif de QThread).
    Jamais terminate() : le dialogue le parque via core.worker.abandon_thread
    (blockSignals + requestInterruption + quit + référence anti-GC).
    """

    thumb_ready = pyqtSignal(int, str)   # (index de vignette, chemin du .jpg)
    done = pyqtSignal()

    def __init__(self, clip_path: str, duration: float, cache_dir: str, count: int):
        super().__init__()
        self._clip = clip_path
        self._dur = max(0.001, float(duration))
        self._dir = cache_dir
        self._count = max(1, int(count))

    def _path(self, i: int) -> str:
        return os.path.join(self._dir, f"thumb_{i + 1:04d}.jpg")

    def run(self):
        try:
            cmd = [get_ffmpeg_exe(), "-y", "-i", self._clip, "-an", "-sn",
                   "-vf", f"fps={self._count}/{self._dur:.6f},scale=-2:{_THUMB_H}",
                   "-frames:v", str(self._count), "-q:v", "5",
                   os.path.join(self._dir, "thumb_%04d.jpg")]
            proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL,
                                    stderr=subprocess.DEVNULL, creationflags=_NO_WINDOW)
        except Exception:
            self.done.emit()
            return
        emitted = -1
        try:
            while True:
                if self.isInterruptionRequested():
                    try:
                        proc.kill()
                    except Exception:
                        pass
                    return
                rc = proc.poll()
                j = emitted + 1
                # i complet quand i+1 existe (écriture séquentielle de ffmpeg)
                while j < self._count and os.path.isfile(self._path(j + 1)):
                    self.thumb_ready.emit(j, self._path(j))
                    emitted = j
                    j += 1
                if rc is not None:
                    break
                self.msleep(60)
        except Exception:
            pass
        # Fin du process : tout fichier présent est complet.
        j = emitted + 1
        while j < self._count and os.path.isfile(self._path(j)):
            self.thumb_ready.emit(j, self._path(j))
            j += 1
        self.done.emit()


# ── Timeline de monteur ────────────────────────────────────────────────────────

_TICK_STEPS = [0.2, 0.5, 1, 2, 5, 10, 15, 30, 60, 120, 300, 600, 1800, 3600]


def _fmt_tick(t: float, step: float) -> str:
    if step < 1.0:
        return f"{t:.1f}"
    m, s = divmod(int(round(t)), 60)
    return f"{m:d}:{s:02d}"


class _TimelineBar(QWidget):
    """Timeline de monteur : règle graduée + playhead que l'on SAISIT à la souris.
    Clic n'importe où = saut direct ; glisser = scrub continu (vignettes cache)."""

    frame_changed = pyqtSignal(int)    # scrub utilisateur (continu, pendant le drag)
    scrub_released = pyqtSignal(int)   # relâchement du playhead

    _PAD = 12       # marge horizontale (le playhead reste dans le widget)
    _RULER_H = 18   # zone des graduations (haut)

    def __init__(self, total_frames: int, fps: float, parent=None):
        super().__init__(parent)
        self._total = max(0, int(total_frames))
        self._fps = fps if fps > 0 else 25.0
        self._frame = 0
        self._dragging = False
        self._hover_x = -1.0
        self._cache_done = 0
        self._cache_total = 0
        self.setFixedHeight(58)
        self.setMinimumWidth(320)
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setToolTip(translate("Timeline : cliquer = sauter, glisser = naviguer"))

    # — API —
    def frame(self) -> int:
        return self._frame

    def set_frame(self, f: int):
        """Positionne le playhead SANS émettre (mise à jour programmatique)."""
        self._frame = max(0, min(int(f), self._total))
        self.update()

    def is_scrubbing(self) -> bool:
        return self._dragging

    def set_cache_progress(self, done: int, total: int):
        self._cache_done, self._cache_total = done, total
        self.update()

    # — Géométrie —
    def _span(self) -> float:
        return max(1.0, self.width() - 2.0 * self._PAD)

    def _frame_to_x(self, f: int) -> float:
        if self._total <= 0:
            return float(self._PAD)
        return self._PAD + (f / self._total) * self._span()

    def _x_to_frame(self, x: float) -> int:
        if self._total <= 0:
            return 0
        rel = max(0.0, min(1.0, (x - self._PAD) / self._span()))
        return int(round(rel * self._total))

    # — Interaction —
    def _scrub(self, x: float):
        f = self._x_to_frame(x)
        if f != self._frame:
            self._frame = f
            self.frame_changed.emit(f)
        self.update()

    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            self.setFocus()
            self._dragging = True
            self._scrub(e.position().x())

    def mouseMoveEvent(self, e):
        if self._dragging:
            self._scrub(e.position().x())
        else:
            self._hover_x = e.position().x()
            self.update()

    def mouseReleaseEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton and self._dragging:
            self._dragging = False
            self.scrub_released.emit(self._frame)
            self.update()

    def leaveEvent(self, e):
        self._hover_x = -1.0
        self.update()
        super().leaveEvent(e)

    # — Rendu —
    def paintEvent(self, e):
        w, h = float(self.width()), float(self.height())
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        # Panneau
        p.setPen(QPen(QColor(CP["border"]), 1))
        p.setBrush(QColor(CP["bg2"]))
        p.drawRoundedRect(QRectF(0.5, 0.5, w - 1.0, h - 1.0), 8, 8)
        pad = float(self._PAD)
        track = QRectF(pad, self._RULER_H + 4.0, w - 2.0 * pad, h - self._RULER_H - 12.0)
        # Piste
        p.setPen(QPen(QColor(CP["border_bright"]), 1))
        p.setBrush(QColor(CP["bg0"]))
        p.drawRoundedRect(track, 4, 4)
        # Partie écoulée
        px = self._frame_to_x(self._frame)
        if px > track.left() + 2.0:
            fill = QColor(CP["accent"])
            fill.setAlpha(48)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(fill)
            p.drawRoundedRect(
                QRectF(track.left() + 1.0, track.top() + 1.0,
                       px - track.left() - 2.0, track.height() - 2.0), 3, 3)
        # Graduations temporelles
        total_t = self._total / self._fps if self._fps > 0 else 0.0
        if total_t > 0:
            pps = self._span() / total_t
            step = next((s for s in _TICK_STEPS if s * pps >= 56.0), 3600.0)
            f = p.font()
            f.setPixelSize(9)
            p.setFont(f)
            minor = step / 5.0 if (step / 5.0) * pps >= 8.0 else 0.0
            if minor:
                p.setPen(QPen(QColor(CP["border_bright"]), 1))
                t = 0.0
                while t <= total_t + 1e-6:
                    x = pad + t * pps
                    p.drawLine(QPointF(x, self._RULER_H - 3.0), QPointF(x, self._RULER_H + 1.0))
                    t += minor
            t = 0.0
            while t <= total_t + 1e-6:
                x = pad + t * pps
                p.setPen(QPen(QColor(CP["border_bright"]), 1))
                p.drawLine(QPointF(x, self._RULER_H - 7.0), QPointF(x, self._RULER_H + 2.0))
                p.setPen(QColor(CP["text_secondary"]))
                r = QRectF(x - 30.0, 1.0, 60.0, self._RULER_H - 8.0)
                if r.left() < 2.0:
                    r.moveLeft(2.0)
                if r.right() > w - 2.0:
                    r.moveRight(w - 2.0)
                p.drawText(r, Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignBottom,
                           _fmt_tick(t, step))
                t += step
        # Progression du cache de vignettes (fine bande en bas de piste)
        if 0 < self._cache_done < self._cache_total:
            frac = self._cache_done / self._cache_total
            strip = QColor(CP["accent2"])
            strip.setAlpha(150)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(strip)
            p.drawRect(QRectF(track.left() + 1.0, track.bottom() - 2.5,
                              (track.width() - 2.0) * frac, 2.0))
        # Survol : repère fin sous la souris
        if self._hover_x >= 0 and not self._dragging:
            hx = max(track.left(), min(track.right(), self._hover_x))
            p.setPen(QPen(QColor(CP["border_bright"]), 1))
            p.drawLine(QPointF(hx, track.top() + 1.0), QPointF(hx, track.bottom() - 1.0))
        # Playhead : trait accent + poignée triangulaire
        p.setPen(QPen(QColor(CP["accent"]), 2))
        p.drawLine(QPointF(px, self._RULER_H - 2.0), QPointF(px, track.bottom() - 1.0))
        handle = QPolygonF([QPointF(px - 5.5, 3.0), QPointF(px + 5.5, 3.0),
                            QPointF(px, self._RULER_H - 2.0)])
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(CP["accent"]))
        p.drawPolygon(handle)
        p.end()


# ── Outils de dessin (feedback visuel) ─────────────────────────────────────────

class _ColorSwatch(QPushButton):
    """Pastille de couleur : état sélectionné ÉVIDENT (anneau accent épais +
    léger agrandissement de la pastille active). Un seul outil actif à la fois."""

    def __init__(self, color: str, on_pick):
        super().__init__()
        self._color = color
        self.setCheckable(True)
        self.setFixedSize(28, 28)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setStyleSheet("QPushButton{background:transparent;border:none;}")
        self.setToolTip(color)
        self.clicked.connect(lambda _=False: on_pick(self))

    def color(self) -> str:
        return self._color

    def enterEvent(self, e):
        self.update()
        super().enterEvent(e)

    def leaveEvent(self, e):
        self.update()
        super().leaveEvent(e)

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        c = QPointF(14.0, 14.0)
        sel = self.isChecked()
        if sel:
            p.setPen(QPen(QColor(CP["accent"]), 2.4))
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawEllipse(c, 12.2, 12.2)
        elif self.underMouse():
            p.setPen(QPen(QColor(CP["border_bright"]), 1.6))
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawEllipse(c, 11.0, 11.0)
        radius = 11.0 if sel else 8.0    # pastille active légèrement agrandie
        p.setPen(QPen(QColor(CP["border_bright"]), 1))
        p.setBrush(QColor(self._color))
        p.drawEllipse(c, radius, radius)
        p.end()


class _BrushPreview(QWidget):
    """Aperçu vivant du trait : montre couleur + taille courantes (anneau si gomme)."""

    def __init__(self, canvas):
        super().__init__()
        self._canvas = canvas
        self.setFixedSize(30, 30)
        self.setToolTip(translate("Aperçu du trait"))

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        p.setPen(QPen(QColor(CP["border"]), 1))
        p.setBrush(QColor(CP["bg0"]))
        p.drawRoundedRect(QRectF(0.5, 0.5, 29.0, 29.0), 6, 6)
        c = QPointF(15.0, 15.0)
        if self._canvas.eraser:
            d = max(6.0, min(22.0, float(self._canvas.pen_width * 2)))
            p.setPen(QPen(QColor(CP["text_primary"]), 1.6))
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawEllipse(c, d / 2.0, d / 2.0)
        else:
            d = max(3.0, min(22.0, float(self._canvas.pen_width)))
            p.setPen(QPen(QColor(CP["border_bright"]), 1))
            p.setBrush(QColor(self._canvas.pen_color))
            p.drawEllipse(c, d / 2.0, d / 2.0)
        p.end()


# ── Canevas de dessin ──────────────────────────────────────────────────────────

class _DrawCanvas(QWidget):
    """Image de fond + calque de dessin transparent (trait libre)."""

    def __init__(self):
        super().__init__()
        self._base: QPixmap | None = None
        self._fallback = False           # base = repli gris (pas une vraie frame)
        self._overlay: QImage | None = None
        self._last: QPoint | None = None
        self.pen_color = QColor(_COLORS[0])
        self.pen_width = 8
        self.eraser = False
        self.setMinimumSize(_DISPLAY_W, int(_DISPLAY_W * 9 / 16))
        self.setStyleSheet(f"background:{CP['bg0']};border:1px solid {CP['border']};border-radius:8px;")
        self.update_tool_cursor()

    def set_base(self, pixmap: QPixmap, fallback: bool = False):
        # Les vignettes du cache (basse résolution) et les frames pleine
        # résolution doivent donner EXACTEMENT la même taille affichée, sinon
        # le calque de dessin serait réinitialisé à chaque scrub → on force la
        # taille de la 1re vraie image.
        if self._base is not None and not self._fallback and self._base.width() > 0:
            scaled = pixmap.scaled(self._base.size(),
                                   Qt.AspectRatioMode.IgnoreAspectRatio,
                                   Qt.TransformationMode.SmoothTransformation)
        else:
            scaled = pixmap.scaledToWidth(_DISPLAY_W, Qt.TransformationMode.SmoothTransformation)
        self._base = scaled
        self._fallback = fallback
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

    def update_tool_cursor(self):
        """Curseur = cercle à la taille du trait (couleur du pinceau, blanc = gomme)."""
        d = self.pen_width * 2 if self.eraser else self.pen_width
        d = max(8, min(64, int(d)))
        pm = QPixmap(d + 6, d + 6)
        pm.fill(Qt.GlobalColor.transparent)
        p = QPainter(pm)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        rect = QRectF(3.0, 3.0, float(d), float(d))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.setPen(QPen(QColor(0, 0, 0, 200), 3))
        p.drawEllipse(rect)
        ring = QColor("#ffffff") if self.eraser else QColor(self.pen_color)
        p.setPen(QPen(ring, 1.6))
        p.drawEllipse(rect)
        p.end()
        self.setCursor(QCursor(pm, pm.width() // 2, pm.height() // 2))

    def paintEvent(self, e):
        p = QPainter(self)
        if self._base is not None:
            p.drawPixmap(0, 0, self._base)
        if self._overlay is not None:
            p.drawImage(0, 0, self._overlay)
        p.end()

    def _stroke_to(self, cur: QPoint):
        if self._overlay is None or self._last is None:
            return
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

    def mousePressEvent(self, e):
        if self._overlay is not None and e.button() == Qt.MouseButton.LeftButton:
            self._last = e.position().toPoint()
            self._stroke_to(self._last)   # un simple clic pose un point

    def mouseMoveEvent(self, e):
        if self._overlay is None or self._last is None:
            return
        self._stroke_to(e.position().toPoint())

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


# ── Dialogue ───────────────────────────────────────────────────────────────────

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
        self._total_frames = max(0, int(round(self._dur * self._fps)) - 1)   # index image
        self._frame = max(0, min(int(prev_frame), self._total_frames))
        self._exact_loaded = -1              # index de la frame pleine résolution affichée
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
            "Comment ça marche : choisis l'instant, puis dessine des repères (flèches, "
            "cercles…) pour indiquer CE QUI change et OÙ. À la validation, l'IA (Claude "
            "Vision) lit ton dessin ET ton texte, puis traduit ton intention en consigne "
            "précise pour le moteur vidéo. Le clip part PROPRE : tes traits ne sont "
            "jamais envoyés et n'apparaîtront pas dans la vidéo. Dans le prompt, décris "
            "simplement ton intention en t'appuyant sur tes repères (ex. « les flèches "
            "indiquent la nouvelle position des personnages »)."))
        hint.setWordWrap(True)
        hint.setStyleSheet(f"color:{CP['text_dim']};font-size:11px;background:transparent;")
        root.addWidget(hint)

        # ── Time code + timeline de monteur ────────────────────────────────────
        tl = QHBoxLayout()
        tl.setSpacing(8)
        tlbl = QLabel(translate("Time Code :"))
        tlbl.setStyleSheet(f"color:{CP['text_secondary']};font-size:11px;background:transparent;")
        tl.addWidget(tlbl)
        self._time_lbl = QLabel(_format_tc(self._frame, self._fps))
        self._time_lbl.setStyleSheet(
            f"color:{CP['accent']};font-size:14px;font-weight:700;"
            f"font-family:Consolas,monospace;background:transparent;")
        tl.addWidget(self._time_lbl)
        self._dur_lbl = QLabel("/  " + _format_tc(self._total_frames, self._fps))
        self._dur_lbl.setStyleSheet(
            f"color:{CP['text_dim']};font-size:11px;font-family:Consolas,monospace;"
            f"background:transparent;")
        tl.addWidget(self._dur_lbl)
        tl.addStretch()
        keys = QLabel(translate("Flèches : ±1 image · Maj+flèches : ±1 s · molette : ±1 image"))
        keys.setStyleSheet(f"color:{CP['text_dim']};font-size:10px;background:transparent;")
        tl.addWidget(keys)
        root.addLayout(tl)

        self._timeline = _TimelineBar(self._total_frames, self._fps)
        self._timeline.set_frame(self._frame)
        self._timeline.frame_changed.connect(self._apply_scrub)
        self._timeline.scrub_released.connect(self._apply_scrub)
        root.addWidget(self._timeline)

        # Débounce : la frame pleine résolution n'est extraite qu'à l'arrêt du scrub
        self._debounce = QTimer(self)
        self._debounce.setSingleShot(True)
        self._debounce.setInterval(_DEBOUNCE_MS)
        self._debounce.timeout.connect(self._load_exact_frame)

        # ── Canevas de dessin ───────────────────────────────────────────────────
        self._canvas = _DrawCanvas()
        _cw = QWidget(); _cl = QHBoxLayout(_cw); _cl.setContentsMargins(0, 0, 0, 0)
        _cl.addStretch(); _cl.addWidget(self._canvas); _cl.addStretch()
        root.addWidget(_cw)

        # ── Outils : couleurs, taille, gomme, effacer ───────────────────────────
        tools = QHBoxLayout()
        tools.setSpacing(4)
        self._swatches: list[_ColorSwatch] = []
        for c in _COLORS:
            b = _ColorSwatch(c, self._pick_swatch)
            self._swatches.append(b)
            tools.addWidget(b)
        self._swatches[0].setChecked(True)   # outil actif au départ = 1re couleur
        tools.addSpacing(12)
        tools.addWidget(self._tlabel(translate("Taille")))
        self._size = QSpinBox()
        self._size.setRange(2, 60)
        self._size.setValue(8)
        self._size.setMinimumWidth(56)
        self._size.setStyleSheet(
            f"QSpinBox{{background:{CP['bg3']};color:{CP['text_primary']};"
            f"border:1px solid {CP['border']};border-radius:6px;"
            f"padding:3px 6px;font-size:11px;}}")
        self._size.valueChanged.connect(self._on_size_changed)
        tools.addWidget(self._size)
        self._brush_prev = _BrushPreview(self._canvas)
        tools.addWidget(self._brush_prev)
        tools.addSpacing(12)
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

        # ── Cache de vignettes (scrub instantané) ───────────────────────────────
        self._thumbs: dict[int, str] = {}       # index → chemin .jpg
        self._thumb_pix: dict[int, QPixmap] = {}  # memoïsation des pixmaps
        self._thumb_count = 0
        self._thumb_worker: _ThumbCacheWorker | None = None
        self._setup_thumb_cache()

        self._reload_frame()   # charge l'image du time code courant (pleine résolution)
        # Ré-édition : si un dessin existait déjà pour ce clip, on le restaure sur
        # le calque (éditable) au lieu d'ouvrir un schéma vierge.
        if self._prev_overlay:
            self._canvas.set_overlay(self._prev_overlay)

        from ui.widgets import disable_default_buttons
        disable_default_buttons(self)   # Entrée ne déclenche pas Annuler/Valider

    # ── Cache de vignettes ─────────────────────────────────────────────────────

    def _thumb_path(self, i: int) -> str:
        return os.path.join(self._thumb_dir, f"thumb_{i + 1:04d}.jpg")

    def _setup_thumb_cache(self):
        if not (self._clip and os.path.isfile(self._clip)) or self._dur <= 0.05:
            return
        n = int(round(self._dur))                       # ~1 vignette/seconde
        n = max(8, min(_THUMB_MAX, n if n > 0 else 8))  # plancher 8, plafond 120
        n = min(n, self._total_frames + 1)
        if n <= 0:
            return
        self._thumb_count = n
        try:
            sig = f"{self._clip}|{os.path.getmtime(self._clip)}|{os.path.getsize(self._clip)}|{n}|{_THUMB_H}"
        except Exception:
            sig = f"{self._clip}|{n}|{_THUMB_H}"
        h = hashlib.md5(sig.encode("utf-8", "replace")).hexdigest()[:12]
        cache_root = os.path.join(self._out_dir, "_thumb_cache")
        self._thumb_dir = os.path.join(cache_root, h)
        try:
            os.makedirs(self._thumb_dir, exist_ok=True)
            self._prune_cache(cache_root, keep=h)
        except Exception:
            return
        existing = [i for i in range(n) if os.path.isfile(self._thumb_path(i))]
        if len(existing) >= n:
            # Cache complet d'une session précédente → réutilisé instantanément.
            for i in existing:
                self._thumbs[i] = self._thumb_path(i)
            self._timeline.set_cache_progress(n, n)
            return
        self._timeline.set_cache_progress(0, n)
        self._thumb_worker = _ThumbCacheWorker(self._clip, self._dur, self._thumb_dir, n)
        self._thumb_worker.thumb_ready.connect(self._on_thumb_ready)
        self._thumb_worker.done.connect(self._on_thumbs_done)
        self._thumb_worker.start()

    @staticmethod
    def _prune_cache(cache_root: str, keep: str, max_dirs: int = 10):
        """Borne le nombre de caches de clips conservés (les plus anciens partent)."""
        try:
            subs = [d for d in os.listdir(cache_root)
                    if d != keep and os.path.isdir(os.path.join(cache_root, d))]
            if len(subs) <= max_dirs:
                return
            subs.sort(key=lambda d: os.path.getmtime(os.path.join(cache_root, d)))
            import shutil
            for d in subs[:len(subs) - max_dirs]:
                shutil.rmtree(os.path.join(cache_root, d), ignore_errors=True)
        except Exception:
            pass

    def _on_thumb_ready(self, i: int, path: str):
        self._thumbs[i] = path
        self._timeline.set_cache_progress(len(self._thumbs), self._thumb_count)

    def _on_thumbs_done(self):
        self._timeline.set_cache_progress(self._thumb_count, self._thumb_count)

    def _show_cached_thumb(self, f: int):
        """Affiche INSTANTANÉMENT la vignette cache la plus proche (drag fluide)."""
        if not self._thumbs or self._dur <= 0 or self._thumb_count <= 0:
            return
        t = f / (self._fps or 25.0)
        ideal = min(self._thumb_count - 1, max(0, int(t * self._thumb_count / self._dur)))
        if ideal in self._thumbs:
            idx = ideal
        else:
            idx = min(self._thumbs.keys(), key=lambda k: abs(k - ideal))
        pm = self._thumb_pix.get(idx)
        if pm is None:
            pm = QPixmap(self._thumbs[idx])
            if pm.isNull():
                return
            self._thumb_pix[idx] = pm
        self._canvas.set_base(pm)

    # ── Navigation temporelle ──────────────────────────────────────────────────

    def _apply_scrub(self, f: int):
        """Position changée (drag, clic, clavier, molette) : TC + vignette + débounce."""
        f = max(0, min(int(f), self._total_frames))
        self._frame = f
        self._time_lbl.setText(_format_tc(f, self._fps))
        if f == self._exact_loaded:
            return   # la frame exacte est déjà affichée
        self._show_cached_thumb(f)
        self._debounce.start()

    def _user_seek(self, f: int):
        """Saut clavier/molette : synchronise le playhead puis applique."""
        f = max(0, min(int(f), self._total_frames))
        self._timeline.set_frame(f)
        self._apply_scrub(f)

    def _load_exact_frame(self):
        if self._timeline.is_scrubbing():
            self._debounce.start()   # toujours en train de glisser → on repousse
            return
        self._reload_frame()

    def keyPressEvent(self, e):
        if e.key() in (Qt.Key.Key_Left, Qt.Key.Key_Right):
            step = 1
            if e.modifiers() & Qt.KeyboardModifier.ShiftModifier:
                step = max(1, int(round(self._fps)))     # Maj = ±1 seconde
            delta = step if e.key() == Qt.Key.Key_Right else -step
            self._user_seek(self._frame + delta)
            e.accept()
            return
        super().keyPressEvent(e)

    def wheelEvent(self, e):
        delta = e.angleDelta().y()
        if delta:
            self._user_seek(self._frame + (1 if delta < 0 else -1))
            e.accept()
            return
        super().wheelEvent(e)

    # ── Outils ─────────────────────────────────────────────────────────────────

    def _tlabel(self, text):
        l = QLabel(text)
        l.setStyleSheet(f"color:{CP['text_secondary']};font-size:11px;background:transparent;")
        return l

    def _tool_btn_ss(self):
        return (
            f"QPushButton{{background:{CP['bg3']};color:{CP['text_secondary']};"
            f"border:1px solid {CP['border']};border-radius:6px;font-size:11px;padding:4px 12px;}}"
            f"QPushButton:checked{{background:{_rgba(CP['accent'], 0.16)};color:{CP['accent']};"
            f"border:2px solid {CP['accent']};font-weight:700;}}"
            f"QPushButton:hover{{border-color:{CP['accent_dim']};}}")

    def _pick_swatch(self, btn: "_ColorSwatch"):
        """Sélection d'une couleur : exclusif (une pastille OU la gomme)."""
        for b in self._swatches:
            b.setChecked(b is btn)
        self._canvas.pen_color = QColor(btn.color())
        self._canvas.eraser = False
        self._btn_eraser.setChecked(False)
        self._canvas.update_tool_cursor()
        self._brush_prev.update()

    def _toggle_eraser(self):
        on = self._btn_eraser.isChecked()
        self._canvas.eraser = on
        if on:
            for b in self._swatches:
                b.setChecked(False)          # gomme active = aucune pastille cochée
        else:
            for b in self._swatches:         # retour au pinceau : re-coche la couleur
                b.setChecked(QColor(b.color()) == self._canvas.pen_color)
        self._canvas.update_tool_cursor()
        self._brush_prev.update()

    def _on_size_changed(self, v: int):
        self._canvas.pen_width = v
        self._canvas.update_tool_cursor()
        self._brush_prev.update()

    # ── Frame pleine résolution ────────────────────────────────────────────────

    def _reload_frame(self):
        t = self._frame / (self._fps or 25.0)
        tmp = os.path.join(self._out_dir, "_frame_tmp.png")
        os.makedirs(self._out_dir, exist_ok=True)
        if _extract_frame(self._clip, t, tmp):
            pm = QPixmap(tmp)
            if not pm.isNull():
                self._canvas.set_base(pm)
                self._exact_loaded = self._frame
                return
        # Repli : pas de frame (ffmpeg absent) → canevas vide gris
        if not self._canvas.has_base():
            blank = QPixmap(_DISPLAY_W, int(_DISPLAY_W * 9 / 16))
            blank.fill(QColor(CP['bg0']))
            self._canvas.set_base(blank, fallback=True)

    # ── Cycle de vie ───────────────────────────────────────────────────────────

    def _park_worker(self):
        # Parque le worker de cache SANS terminate() (anti-segfault) :
        # blockSignals + requestInterruption + quit + référence anti-GC.
        if self._thumb_worker is not None:
            try:
                from core.worker import abandon_thread
                abandon_thread(self._thumb_worker)
            except Exception:
                pass
            self._thumb_worker = None

    def done(self, code):
        self._park_worker()          # accept() / reject() / Échap
        super().done(code)

    def closeEvent(self, e):
        self._park_worker()          # fermeture par la croix ou close() direct
        super().closeEvent(e)

    def _accept(self):
        ts = int(time.time())
        out = os.path.join(self._out_dir, f"drawtovideo_{ts}.png")
        if self._canvas.export(out):                       # image aplatie (réf. génération)
            self._result_path = out
        ov = os.path.join(self._out_dir, f"drawoverlay_{ts}.png")
        if self._canvas.export_overlay(ov):                # calque seul (ré-édition)
            self._overlay_path = ov
        self._frame = self._timeline.frame()
        self.accept()

    def result_path(self) -> str:
        return self._result_path

    def overlay_path(self) -> str:
        """Calque de dessin seul — à repasser en `prev_overlay` pour ré-éditer."""
        return self._overlay_path

    def frame_index(self) -> int:
        """Index d'image choisi — à repasser en `prev_frame` pour ré-éditer."""
        return self._frame
