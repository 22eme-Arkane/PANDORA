"""Page de démarrage unifiée de PANDORA.

Cette page remplace le sélecteur Cinéma/Live puis l'ancien splash projets.
Le choix d'un mode ne change pas de page : il filtre les projets récents et
détermine le type du prochain projet créé.
"""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime

from PyQt6.QtCore import Qt, QSize, QRectF, QPointF, pyqtSignal
from PyQt6.QtGui import (
    QColor,
    QIcon,
    QImageReader,
    QKeyEvent,
    QLinearGradient,
    QPainter,
    QPainterPath,
    QPen,
    QPixmap,
    QPolygonF,
    QRadialGradient,
)
from PyQt6.QtWidgets import (
    QDialog,
    QFileDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

import core.project as project_api
from core.i18n import get_lang, set_lang, translate
from core.version import VERSION
from ui.icons import app_icon, load_icon
from ui.splash import NewProjectDialog
from ui.styles import CP


_ASSETS = (
    os.path.join(sys._MEIPASS, "assets")
    if getattr(sys, "frozen", False)
    else os.path.join(os.path.dirname(os.path.dirname(__file__)), "assets")
)

_MODE_COLORS = {
    "cinema": CP["accent"],
    "live": CP["accent2"],
}


def _alpha(color: str, value: int) -> QColor:
    result = QColor(color)
    result.setAlpha(max(0, min(255, value)))
    return result


def _relative_time(iso_value: str) -> str:
    try:
        delta = datetime.now() - datetime.fromisoformat(iso_value)
    except Exception:
        return ""
    english = get_lang() == "en"
    if delta.days <= 0:
        hours = delta.seconds // 3600
        if hours <= 0:
            minutes = max(1, delta.seconds // 60)
            return f"{minutes} min ago" if english else f"Il y a {minutes} min"
        return f"{hours}h ago" if english else f"Il y a {hours}h"
    if delta.days == 1:
        return "Yesterday" if english else "Hier"
    if delta.days < 7:
        return f"{delta.days} days ago" if english else f"Il y a {delta.days} jours"
    return iso_value[:10]


def _existing_image(path: str, *bases: str) -> str:
    if not path:
        return ""
    candidates = [path]
    if not os.path.isabs(path):
        candidates.extend(os.path.join(base, path) for base in bases if base)
    for candidate in candidates:
        candidate = os.path.normpath(candidate)
        if os.path.isfile(candidate):
            return candidate
    return ""


def first_project_mood(data: dict) -> str:
    """Retourne l'image active du premier mood disponible dans le projet.

    On inspecte d'abord les aperçus du storyboard (Cinéma puis namespaces Live)
    et l'on utilise l'image active du premier plan qui en possède une. Le champ
    historique ``thumbnail`` sert uniquement de repli.
    """
    root = os.path.normpath(data.get("_path", ""))
    legacy_thumbnail = _existing_image(data.get("thumbnail", ""), root)
    if not root or not os.path.isdir(root):
        return legacy_thumbnail

    data_root = os.path.join(root, "data")
    namespaces = ("storyboard", "live_seq_live", "live_seq_mapping")
    for namespace in namespaces:
        apercus_root = os.path.join(data_root, namespace, "apercus")
        if not os.path.isdir(apercus_root):
            continue
        for current, dirs, files in os.walk(apercus_root):
            dirs.sort()
            if "apercus.json" not in files:
                continue
            meta_path = os.path.join(current, "apercus.json")
            try:
                with open(meta_path, "r", encoding="utf-8") as stream:
                    meta = json.load(stream)
            except Exception:
                continue
            paths = meta.get("paths", []) if isinstance(meta, dict) else []
            if not isinstance(paths, list) or not paths:
                continue
            active = meta.get("active_idx", 0)
            try:
                active = int(active)
            except (TypeError, ValueError):
                active = 0
            order = [active] + [i for i in range(len(paths)) if i != active]
            for index in order:
                if not 0 <= index < len(paths):
                    continue
                found = _existing_image(str(paths[index]), current, root)
                if not found:
                    found = _existing_image(os.path.basename(str(paths[index])), current)
                if found:
                    return found
    return legacy_thumbnail


def _scaled_pixmap(path: str, size: QSize) -> QPixmap:
    if not path or not os.path.isfile(path) or size.isEmpty():
        return QPixmap()
    reader = QImageReader(path)
    reader.setAutoTransform(True)
    source = reader.size()
    if source.isValid() and source.width() > 0 and source.height() > 0:
        scale = max(size.width() / source.width(), size.height() / source.height())
        reader.setScaledSize(
            QSize(max(size.width(), int(source.width() * scale)),
                  max(size.height(), int(source.height() * scale)))
        )
    image = reader.read()
    return QPixmap.fromImage(image) if not image.isNull() else QPixmap()


class _Background(QWidget):
    """Fond atmosphérique haute définition, avec repli vectoriel."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._background_pixmap = QPixmap(
            os.path.join(_ASSETS, "start_background_v2.png")
        )

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        rect = QRectF(self.rect())

        if not self._background_pixmap.isNull() and rect.width() and rect.height():
            pix = self._background_pixmap
            scale = max(rect.width() / pix.width(), rect.height() / pix.height())
            source_w = rect.width() / scale
            source_h = rect.height() / scale
            source = QRectF(
                (pix.width() - source_w) / 2,
                (pix.height() - source_h) / 2,
                source_w,
                source_h,
            )
            painter.drawPixmap(rect, pix, source)
        else:
            base = QLinearGradient(rect.topLeft(), rect.bottomLeft())
            base.setColorAt(0.0, QColor("#0b111c"))
            base.setColorAt(0.52, QColor(CP["bg1"]))
            base.setColorAt(1.0, QColor("#080d16"))
            painter.fillRect(rect, base)

        veil = QLinearGradient(rect.topLeft(), rect.bottomLeft())
        veil.setColorAt(0.0, QColor(3, 8, 15, 48))
        veil.setColorAt(0.54, QColor(3, 8, 15, 16))
        veil.setColorAt(1.0, QColor(3, 7, 13, 74))
        painter.fillRect(rect, veil)

        cyan = QRadialGradient(rect.width() * 0.27, rect.height() * 0.48,
                               rect.width() * 0.48)
        cyan.setColorAt(0.0, _alpha(CP["accent"], 18))
        cyan.setColorAt(1.0, _alpha(CP["accent"], 0))
        painter.fillRect(rect, cyan)

        violet = QRadialGradient(rect.width() * 0.75, rect.height() * 0.45,
                                 rect.width() * 0.50)
        violet.setColorAt(0.0, _alpha(CP["accent2"], 17))
        violet.setColorAt(1.0, _alpha(CP["accent2"], 0))
        painter.fillRect(rect, violet)

        floor = QLinearGradient(0, rect.height() * 0.62, 0, rect.height())
        floor.setColorAt(0.0, QColor(7, 12, 21, 0))
        floor.setColorAt(0.40, QColor(7, 12, 21, 70))
        floor.setColorAt(1.0, QColor(3, 7, 13, 120))
        painter.fillRect(rect, floor)


class _CoverImage(QWidget):
    def __init__(self, path: str = "", radius: float = 10.0,
                 focus_y: float = 0.5, focus_x: float = 0.5, parent=None):
        super().__init__(parent)
        self._path = path
        self._radius = radius
        self._focus_y = max(0.0, min(1.0, focus_y))
        # focus_x : 0.0 = bord gauche conservé (rognage à droite), 0.5 = centré
        # (rognage des deux côtés), 1.0 = bord droit conservé.
        self._focus_x = max(0.0, min(1.0, focus_x))
        self._cache = QPixmap()
        self._cache_size = QSize()
        self.setMinimumHeight(130)

    def set_path(self, path: str):
        self._path = path
        self._cache = QPixmap()
        self._cache_size = QSize()
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        target = QRectF(self.rect())
        clip = QPainterPath()
        clip.addRoundedRect(target, self._radius, self._radius)
        painter.setClipPath(clip)
        painter.fillRect(target, QColor(CP["bg3"]))
        if self._cache_size != self.size():
            self._cache = _scaled_pixmap(self._path, self.size())
            self._cache_size = self.size()
        if self._cache.isNull():
            return
        pix = self._cache
        x = -(pix.width() - self.width()) * self._focus_x
        y = -(pix.height() - self.height()) * self._focus_y
        painter.drawPixmap(int(x), int(y), pix)


class _ModeGlyph(QWidget):
    """Pictogramme filaire net, dessiné directement dans l'interface."""

    def __init__(self, mode: str, parent=None):
        super().__init__(parent)
        self._mode = mode
        self.setFixedSize(48, 48)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        color = QColor(_MODE_COLORS[self._mode])
        painter.setPen(QPen(color, 1.8, Qt.PenStyle.SolidLine,
                            Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
        painter.setBrush(Qt.BrushStyle.NoBrush)

        if self._mode == "cinema":
            painter.drawRoundedRect(QRectF(9, 17, 30, 22), 3, 3)
            painter.drawLine(QPointF(9, 23), QPointF(39, 23))
            painter.drawLine(QPointF(11, 17), QPointF(16, 11))
            painter.drawLine(QPointF(18, 17), QPointF(23, 11))
            painter.drawLine(QPointF(25, 17), QPointF(30, 11))
            painter.drawLine(QPointF(32, 17), QPointF(37, 11))
            painter.drawLine(QPointF(11, 17), QPointF(37, 11))
            painter.drawPolygon(QPolygonF([
                QPointF(21, 27), QPointF(21, 35), QPointF(29, 31)
            ]))
        else:
            points = [
                QPointF(6, 25), QPointF(12, 25), QPointF(15, 18),
                QPointF(19, 34), QPointF(23, 10), QPointF(27, 38),
                QPointF(31, 20), QPointF(35, 28), QPointF(39, 25),
                QPointF(43, 25),
            ]
            painter.drawPolyline(QPolygonF(points))


class _ModeCard(QWidget):
    selected = pyqtSignal(str)

    def __init__(self, mode: str, image_path: str, parent=None):
        super().__init__(parent)
        self.mode = mode
        self._selected = False
        self._hovered = False
        self._available = True
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setMinimumHeight(248)
        self.setMaximumHeight(420)
        self.setAccessibleName("Cinéma" if mode == "cinema" else "Live")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(2, 2, 2, 2)
        layout.setSpacing(0)

        self._image = _CoverImage(
            image_path,
            radius=11,
            focus_y=0.14 if mode == "live" else 0.5,
            # Cartes 25 % moins larges (2026-07-22) : le visuel Cinéma est rogné à
            # DROITE (astronaute conservé), le visuel Live des DEUX côtés (centré).
            focus_x=0.5 if mode == "live" else 0.0,
        )
        self._image.setMinimumHeight(145)
        layout.addWidget(self._image, 5)

        info = QWidget()
        info.setStyleSheet("background:transparent;")
        row = QHBoxLayout(info)
        row.setContentsMargins(24, 14, 22, 15)
        row.setSpacing(14)

        self._icon = _ModeGlyph(mode)
        row.addWidget(self._icon)

        text_col = QVBoxLayout()
        text_col.setSpacing(5)
        self._title = QLabel()
        self._title.setStyleSheet(
            f"color:{CP['text_primary']};font-size:21px;font-weight:600;background:transparent;"
        )
        self._description = QLabel()
        self._description.setWordWrap(True)
        self._description.setStyleSheet(
            f"color:{CP['text_secondary']};font-size:11px;background:transparent;"
        )
        text_col.addWidget(self._title)
        text_col.addWidget(self._description)
        row.addLayout(text_col, 1)

        layout.addWidget(info, 2)
        self.retranslate()

    def retranslate(self):
        self._title.setText("Cinéma" if self.mode == "cinema" else "Live")
        text = (
            "Créez un film ou une vidéo générés par IA"
            if self.mode == "cinema"
            else "Créez un live vidéo ou un mapping générés par IA"
        )
        self._description.setText(translate(text))

    def set_available(self, available: bool):
        self._available = available
        self.setCursor(
            Qt.CursorShape.PointingHandCursor if available else Qt.CursorShape.ForbiddenCursor
        )
        self.setToolTip(
            "" if available else translate("Le module Live n'est pas disponible dans cette édition.")
        )
        self.update()

    def set_selected(self, selected: bool):
        if self._selected == selected:
            return
        self._selected = selected
        self.setAccessibleDescription("Sélectionné" if selected else "")
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = QRectF(self.rect()).adjusted(1.5, 1.5, -1.5, -1.5)
        path = QPainterPath()
        path.addRoundedRect(rect, 12, 12)
        painter.fillPath(path, QColor(12, 19, 31, 238))

        color = _MODE_COLORS[self.mode]
        if self._selected:
            for width, alpha in ((7.0, 22), (4.0, 42), (1.7, 235)):
                painter.setPen(QPen(_alpha(color, alpha), width))
                painter.drawPath(path)
        elif self._hovered and self._available:
            painter.setPen(QPen(_alpha(color, 135), 1.2))
            painter.drawPath(path)
        else:
            painter.setPen(QPen(QColor(CP["border"]), 1.0))
            painter.drawPath(path)
        if not self._available:
            painter.fillPath(path, QColor(5, 8, 14, 125))

    def enterEvent(self, event):
        self._hovered = True
        self.update()

    def leaveEvent(self, event):
        self._hovered = False
        self.update()

    def mouseReleaseEvent(self, event):
        if (
            self._available
            and event.button() == Qt.MouseButton.LeftButton
            and self.rect().contains(event.position().toPoint())
        ):
            self.selected.emit(self.mode)

    def keyPressEvent(self, event: QKeyEvent):
        if self._available and event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter, Qt.Key.Key_Space):
            self.selected.emit(self.mode)
            event.accept()
            return
        super().keyPressEvent(event)


class _ActionTile(QWidget):
    clicked = pyqtSignal()

    def __init__(self, kind: str, parent=None):
        super().__init__(parent)
        self.kind = kind
        self._hovered = False
        self._color = CP["accent"]
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setFixedHeight(88)

        row = QHBoxLayout(self)
        row.setContentsMargins(12, 8, 12, 8)
        row.setSpacing(14)
        self._icon = QLabel()
        self._icon.setFixedSize(52, 52)
        self._icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        row.addWidget(self._icon)
        column = QVBoxLayout()
        column.setSpacing(4)
        self._title = QLabel()
        self._title.setStyleSheet(
            f"color:{CP['text_primary']};font-size:13px;font-weight:700;background:transparent;"
        )
        self._subtitle = QLabel()
        self._subtitle.setWordWrap(True)
        self._subtitle.setStyleSheet(
            f"color:{CP['text_secondary']};font-size:10px;background:transparent;"
        )
        column.addWidget(self._title)
        column.addWidget(self._subtitle)
        row.addLayout(column, 1)
        self.retranslate()
        self.set_mode("cinema")

    def retranslate(self):
        if self.kind == "new":
            self._title.setText(translate("Nouveau projet"))
            self._subtitle.setText(translate("Créez un projet vierge et commencez l'écriture."))
        else:
            self._title.setText(translate("Ouvrir un projet"))
            self._subtitle.setText(translate("Parcourez vos projets en local."))

    def set_mode(self, mode: str):
        self._color = _MODE_COLORS[mode]
        filename = "new_project.png" if self.kind == "new" else "open_project.png"
        pix = load_icon(filename, 27, self._color)
        self._icon.setPixmap(pix)
        self._icon.setStyleSheet(
            f"background:rgba({self._color_rgb()},0.06);border:1px solid {self._color};"
            "border-radius:8px;"
        )
        self.update()

    def _color_rgb(self) -> str:
        color = QColor(self._color)
        return f"{color.red()},{color.green()},{color.blue()}"

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        if self._hovered or self.hasFocus():
            rect = QRectF(self.rect()).adjusted(1, 1, -1, -1)
            painter.setPen(QPen(_alpha(self._color, 80), 1))
            painter.setBrush(_alpha(self._color, 11))
            painter.drawRoundedRect(rect, 9, 9)

    def enterEvent(self, event):
        self._hovered = True
        self.update()

    def leaveEvent(self, event):
        self._hovered = False
        self.update()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self.rect().contains(event.position().toPoint()):
            self.clicked.emit()

    def keyPressEvent(self, event: QKeyEvent):
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter, Qt.Key.Key_Space):
            self.clicked.emit()
            event.accept()
            return
        super().keyPressEvent(event)


class _RecentCard(QWidget):
    clicked = pyqtSignal(dict)

    def __init__(self, data: dict, parent=None):
        super().__init__(parent)
        self._data = data
        self._hovered = False
        self._color = _MODE_COLORS.get(data.get("mode", "cinema"), CP["accent"])
        self.setFixedHeight(68)
        self.setMinimumWidth(150)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(6, 6, 9, 6)
        layout.setSpacing(9)
        thumb = _CoverImage(first_project_mood(data), radius=6)
        thumb.setFixedSize(58, 56)
        layout.addWidget(thumb)

        column = QVBoxLayout()
        column.setSpacing(3)
        name = QLabel(data.get("name", "Projet"))
        name.setWordWrap(True)
        name.setMaximumHeight(34)
        name.setStyleSheet(
            f"color:{self._color};font-size:11px;font-weight:700;background:transparent;"
        )
        mode = QLabel("Cinéma" if data.get("mode", "cinema") == "cinema" else "Live")
        mode.setStyleSheet(f"color:{CP['text_dim']};font-size:9px;background:transparent;")
        when = _relative_time(data.get("modified_at", ""))
        modified = QLabel(("Modified " if get_lang() == "en" else "Modifié ") + when)
        modified.setStyleSheet(f"color:{CP['text_secondary']};font-size:9px;background:transparent;")
        column.addWidget(name)
        column.addWidget(mode)
        column.addWidget(modified)
        layout.addLayout(column, 1)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        painter.setBrush(QColor(14, 22, 36, 220))
        painter.setPen(QPen(_alpha(self._color, 105 if self._hovered else 36), 1))
        painter.drawRoundedRect(rect, 8, 8)

    def enterEvent(self, event):
        self._hovered = True
        self.update()

    def leaveEvent(self, event):
        self._hovered = False
        self.update()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self.rect().contains(event.position().toPoint()):
            self.clicked.emit(self._data)

    def keyPressEvent(self, event: QKeyEvent):
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter, Qt.Key.Key_Space):
            self.clicked.emit(self._data)
            event.accept()
            return
        super().keyPressEvent(event)


class StartPage(_Background):
    """Fenêtre de démarrage unique Cinéma/Live + projets."""

    project_selected = pyqtSignal(dict)
    lang_changed = pyqtSignal(str)

    def __init__(self, allow_live: bool = True, parent=None):
        super().__init__(parent)
        self._allow_live = allow_live
        self._mode = "cinema"
        self._recent_projects: list[dict] = []
        self._recent_offset = 0
        self.setWindowTitle("PANDORA — by 22eme ARKANE")
        self.resize(1320, 820)
        self.setMinimumSize(1120, 700)

        root = QVBoxLayout(self)
        root.setContentsMargins(48, 26, 48, 18)
        root.setSpacing(24)
        self._root_layout = root

        self._top_spacer = QWidget()
        self._top_spacer.setFixedHeight(0)
        self._top_spacer.setStyleSheet("background:transparent;")
        root.addWidget(self._top_spacer)

        brand = QWidget()
        brand.setStyleSheet("background:transparent;")
        brand_layout = QVBoxLayout(brand)
        brand_layout.setContentsMargins(0, 0, 0, 0)
        brand_layout.setSpacing(8)
        brand_layout.setAlignment(Qt.AlignmentFlag.AlignHCenter)

        logo = QLabel()
        logo.setFixedSize(72, 72)
        logo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        pix = app_icon().pixmap(72, 72)
        if not pix.isNull():
            logo.setPixmap(pix)
        logo.setStyleSheet("background:transparent;")
        brand_layout.addWidget(logo, 0, Qt.AlignmentFlag.AlignHCenter)

        title = QLabel("P A N D O R A")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet(
            f"color:{CP['text_primary']};font-size:30px;font-weight:400;"
            "letter-spacing:7px;background:transparent;"
        )
        brand_layout.addWidget(title)

        byline = QLabel("by 22eme ARKANE")
        byline.setAlignment(Qt.AlignmentFlag.AlignCenter)
        byline.setStyleSheet(
            f"color:{CP['text_secondary']};font-size:10px;letter-spacing:2px;background:transparent;"
        )
        brand_layout.addWidget(byline)

        accent_line = QFrame()
        accent_line.setFixedSize(28, 1)
        accent_line.setStyleSheet(f"background:{CP['accent2']};border:none;")
        brand_layout.addWidget(accent_line, 0, Qt.AlignmentFlag.AlignHCenter)

        self._tagline = QLabel()
        self._tagline.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._tagline.setStyleSheet(
            f"color:{CP['text_secondary']};font-size:11px;background:transparent;"
        )
        brand_layout.addWidget(self._tagline)
        root.addWidget(brand)

        # Cartes 25 % moins larges (demande Matthieu 2026-07-22) : colonnes
        # [marge, Cinéma, écart, Live, marge]. Chaque colonne de contenu fait
        # 75/200 = 37,5 % de la largeur (au lieu de ~50 %), l'espace libéré part
        # dans les marges latérales et l'écart central. Les blocs du bas occupent
        # les MÊMES colonnes : Nouveau/Ouvrir reste aligné sous Cinéma et les
        # Projets récents sous Live.
        grid = QGridLayout()
        grid.setHorizontalSpacing(0)
        grid.setVerticalSpacing(12)
        # Blocs resserrés vers le CENTRE (retour Matthieu 2026-07-23) : l'espace
        # libéré par les cartes -25 % part dans les marges LATÉRALES, l'écart
        # central reste petit pour que Cinéma et Live restent proches.
        grid.setColumnStretch(0, 24)
        grid.setColumnStretch(1, 75)
        grid.setColumnStretch(2, 6)
        grid.setColumnMinimumWidth(2, 24)
        grid.setColumnStretch(3, 75)
        grid.setColumnStretch(4, 24)

        self._cinema = _ModeCard("cinema", os.path.join(_ASSETS, "start_cinema_hero_v3.png"))
        self._live = _ModeCard("live", os.path.join(_ASSETS, "start_live_hero_v4.png"))
        self._cinema.selected.connect(self.set_mode)
        self._live.selected.connect(self.set_mode)
        self._live.set_available(allow_live)
        grid.addWidget(self._cinema, 0, 1)
        grid.addWidget(self._live, 0, 3)

        actions = QWidget()
        actions.setFixedHeight(108)
        actions.setStyleSheet("background:rgba(7,12,21,0.38);border-radius:8px;")
        actions_layout = QHBoxLayout(actions)
        actions_layout.setContentsMargins(8, 2, 8, 2)
        actions_layout.setSpacing(6)
        self._new_action = _ActionTile("new")
        self._open_action = _ActionTile("open")
        self._new_action.clicked.connect(self._on_new)
        self._open_action.clicked.connect(self._on_open)
        inner_sep = QFrame()
        inner_sep.setFixedWidth(1)
        inner_sep.setStyleSheet(f"background:{CP['border']};")
        actions_layout.addWidget(self._new_action, 1)
        actions_layout.addWidget(inner_sep)
        actions_layout.addWidget(self._open_action, 1)
        grid.addWidget(actions, 1, 1)

        recent_panel = QWidget()
        recent_panel.setFixedHeight(108)
        recent_panel.setStyleSheet("background:rgba(7,12,21,0.38);border-radius:8px;")
        recent_layout = QVBoxLayout(recent_panel)
        recent_layout.setContentsMargins(10, 7, 7, 7)
        recent_layout.setSpacing(5)
        header = QHBoxLayout()
        self._recent_title = QLabel()
        self._recent_title.setStyleSheet(
            f"color:{CP['text_secondary']};font-size:9px;font-weight:700;"
            "letter-spacing:1px;background:transparent;"
        )
        header.addWidget(self._recent_title)
        header.addStretch()
        recent_layout.addLayout(header)

        recent_row = QHBoxLayout()
        recent_row.setSpacing(6)

        self._previous_recent = QPushButton("‹")
        self._previous_recent.setFixedSize(30, 68)
        self._previous_recent.setCursor(Qt.CursorShape.PointingHandCursor)
        recent_row.addWidget(self._previous_recent)

        self._recent_container = QWidget()
        self._recent_container.setStyleSheet("background:transparent;")
        self._recent_cards = QHBoxLayout(self._recent_container)
        self._recent_cards.setContentsMargins(0, 0, 0, 0)
        self._recent_cards.setSpacing(7)
        recent_row.addWidget(self._recent_container, 1)

        self._next_recent = QPushButton("›")
        self._next_recent.setFixedSize(30, 68)
        self._next_recent.setCursor(Qt.CursorShape.PointingHandCursor)
        navigation_style = (
            f"QPushButton{{background:{CP['bg2']};color:{CP['text_secondary']};"
            f"border:1px solid {CP['border']};border-radius:7px;font-size:26px;}}"
            f"QPushButton:hover{{color:{CP['text_primary']};border-color:{CP['border_bright']};}}"
            f"QPushButton:disabled{{background:transparent;color:{CP['text_dim']};"
            f"border-color:transparent;}}"
        )
        self._previous_recent.setStyleSheet(navigation_style)
        self._next_recent.setStyleSheet(navigation_style)
        self._previous_recent.clicked.connect(self._show_previous_recents)
        self._next_recent.clicked.connect(self._show_next_recents)
        recent_row.addWidget(self._next_recent)
        recent_layout.addLayout(recent_row)
        grid.addWidget(recent_panel, 1, 3)

        bottom_separator = QFrame()
        bottom_separator.setObjectName("startBottomSeparator")
        bottom_separator.setFixedSize(1, 44)
        bottom_separator.setStyleSheet("background:rgba(255,255,255,0.10);")
        grid.addWidget(
            bottom_separator,
            1,
            2,
            alignment=Qt.AlignmentFlag.AlignCenter,
        )
        root.addLayout(grid)
        root.addStretch(1)

        footer = QHBoxLayout()
        footer.setSpacing(4)
        self._lang_buttons: dict[str, QPushButton] = {}
        for code, label in (("fr", "FR"), ("en", "EN")):
            button = QPushButton(label)
            button.setFixedSize(43, 28)
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            button.clicked.connect(lambda _checked=False, value=code: self._change_language(value))
            self._lang_buttons[code] = button
            footer.addWidget(button)
        footer.addStretch()
        version = QLabel(f"v{VERSION}")
        version.setStyleSheet(f"color:{CP['text_dim']};font-size:10px;background:transparent;")
        footer.addWidget(version)
        root.addLayout(footer)

        self.retranslate()
        self.set_mode("cinema")

    def resizeEvent(self, event):
        super().resizeEvent(event)
        extra_top = int(max(0, min(410, self.height() - 820)) * 20 / 410)
        self._root_layout.setContentsMargins(48, 26 + extra_top, 48, 18)
        top_space = int(max(0, min(380, self.height() - 820)) * 82 / 380)
        self._top_spacer.setFixedHeight(top_space)

        card_height = max(286, min(420, int(self.height() * 0.36)))
        self._cinema.setFixedHeight(card_height)
        self._live.setFixedHeight(card_height)

    def retranslate(self):
        self._tagline.setText(translate("Votre environnement créatif pour le cinéma et le live"))
        self._recent_title.setText(translate("PROJETS RÉCENTS"))
        self._cinema.retranslate()
        self._live.retranslate()
        self._new_action.retranslate()
        self._open_action.retranslate()
        self._refresh_language_buttons()
        self._rebuild_recents()

    def refresh(self):
        """Recharge les projets récents lors d'un retour depuis l'espace de travail."""
        self._rebuild_recents()

    def set_mode(self, mode: str):
        if mode not in _MODE_COLORS or (mode == "live" and not self._allow_live):
            return
        self._mode = mode
        self._cinema.set_selected(mode == "cinema")
        self._live.set_selected(mode == "live")
        self._new_action.set_mode(mode)
        self._open_action.set_mode(mode)
        self._rebuild_recents()

    def _scan_project_locations(self):
        try:
            from core.config import load_config
            config = load_config()
            locations = {project_api._DEFAULT_DIR}
            last = str(config.get("last_project_location", "")).strip()
            if last:
                locations.add(last)
            for folder in locations:
                if os.path.isdir(folder):
                    project_api.scan_folder(folder)
        except Exception:
            pass

    def _clear_layout(self, layout):
        while layout.count():
            item = layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

    def _rebuild_recents(self):
        if not hasattr(self, "_recent_cards"):
            return
        self._scan_project_locations()
        self._recent_projects = [
            data for data in project_api.list_recent(20)
            if data.get("mode", "cinema") == self._mode
        ]
        self._recent_offset = 0
        self._show_recent_page()

    def _show_recent_page(self):
        self._clear_layout(self._recent_cards)
        projects = self._recent_projects
        if not projects:
            empty = QLabel(translate("Aucun projet récent"))
            empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
            empty.setStyleSheet(
                f"color:{CP['text_dim']};font-size:11px;background:transparent;padding:0 18px;"
            )
            self._recent_cards.addWidget(empty)
            self._previous_recent.setEnabled(False)
            self._next_recent.setEnabled(False)
            return

        # Pagination par DEUX cartes (2026-07-22) : le panneau, 25 % moins large,
        # n'accueille confortablement que deux vignettes.
        _page = 2
        maximum = max(0, len(projects) - _page)
        self._recent_offset = max(0, min(self._recent_offset, maximum))
        visible = projects[self._recent_offset:self._recent_offset + _page]
        for data in visible:
            card = _RecentCard(data)
            card.clicked.connect(self._open_recent)
            self._recent_cards.addWidget(card, 1)
        if len(visible) < _page:
            self._recent_cards.addStretch(_page - len(visible))

        self._previous_recent.setEnabled(self._recent_offset > 0)
        self._next_recent.setEnabled(self._recent_offset + _page < len(projects))

    def _show_previous_recents(self):
        self._recent_offset = max(0, self._recent_offset - 2)
        self._show_recent_page()

    def _show_next_recents(self):
        if self._recent_offset + 2 < len(self._recent_projects):
            self._recent_offset += 2
        self._show_recent_page()

    def _change_language(self, code: str):
        if code == get_lang():
            return
        set_lang(code)
        self.retranslate()
        self.lang_changed.emit(code)

    def _refresh_language_buttons(self):
        current = get_lang()
        for code, button in self._lang_buttons.items():
            active = code == current
            button.setStyleSheet(
                "QPushButton{background:%s;color:%s;border:1px solid %s;"
                "border-radius:6px;font-size:10px;font-weight:700;}"
                "QPushButton:hover{background:%s;}"
                % (
                    "rgba(78,205,196,0.10)" if active else "transparent",
                    CP["text_primary"] if active else CP["text_dim"],
                    CP["accent"] if active else CP["border"],
                    CP["bg3"],
                )
            )

    def _on_new(self):
        dialog = NewProjectDialog(self, mode=self._mode)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            data = dialog.get_project()
            if data:
                self.project_selected.emit(data)

    def _on_open(self):
        folder = QFileDialog.getExistingDirectory(self, translate("Ouvrir un projet PANDORA"), "")
        if not folder:
            return
        data = project_api.load_project(folder)
        if not data:
            QMessageBox.warning(
                self,
                translate("Projet invalide"),
                translate("Ce dossier ne contient pas de projet PANDORA valide."),
            )
            return
        self._open_project_data(data)

    def _open_recent(self, data: dict):
        self._open_project_data(data)

    def _open_project_data(self, data: dict):
        project_mode = data.get("mode", "cinema")
        if project_mode == "live" and not self._allow_live:
            QMessageBox.warning(
                self,
                "PANDORA Live",
                translate("Le module Live n'est pas disponible dans cette édition."),
            )
            return
        # Un projet existant garde toujours son mode d'origine pour préserver ses données.
        if project_mode in _MODE_COLORS and project_mode != self._mode:
            self.set_mode(project_mode)
        path = data.get("_path", "")
        if path:
            project_api.add_to_recent(path)
        self.project_selected.emit(data)
