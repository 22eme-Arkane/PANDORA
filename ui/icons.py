"""
Utilitaire de chargement et teinte des icônes PNG.
Les icônes doivent être blanches sur fond transparent.
"""

import os
import sys
from PyQt6.QtGui import QPixmap, QPainter, QColor, QIcon
from PyQt6.QtCore import Qt, QObject, QEvent, QSize

# En mode gelé (PyInstaller), les assets sont dans sys._MEIPASS (dossier _internal/).
if getattr(sys, "frozen", False):
    _ASSETS = os.path.join(sys._MEIPASS, "assets")
else:
    _ASSETS = os.path.join(os.path.dirname(os.path.dirname(__file__)), "assets")
_ICONS  = os.path.join(_ASSETS, "icons")


def _find(filename: str) -> str:
    """Recherche case-insensitive dans assets/icons/."""
    path = os.path.join(_ICONS, filename)
    if os.path.isfile(path):
        return path
    if os.path.isdir(_ICONS):
        low = filename.lower()
        for fn in os.listdir(_ICONS):
            if fn.lower() == low:
                return os.path.join(_ICONS, fn)
    return ""


def tint(pix: QPixmap, hex_color: str) -> QPixmap:
    """Teinte un pixmap avec la couleur donnée en préservant l'alpha."""
    if pix.isNull():
        return pix
    result = QPixmap(pix.size())
    result.setDevicePixelRatio(pix.devicePixelRatio())  # avant le painter = coords logiques
    result.fill(Qt.GlobalColor.transparent)
    p = QPainter(result)
    p.drawPixmap(0, 0, pix)
    p.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceIn)
    p.fillRect(result.rect(), QColor(hex_color))
    p.end()
    return result


def dim(pix: QPixmap, opacity: float = 0.45) -> QPixmap:
    """Crée une version semi-transparente d'un pixmap (pour état inactif)."""
    if pix.isNull():
        return pix
    result = QPixmap(pix.size())
    result.setDevicePixelRatio(pix.devicePixelRatio())  # avant le painter = coords logiques
    result.fill(Qt.GlobalColor.transparent)
    p = QPainter(result)
    p.setOpacity(opacity)
    p.drawPixmap(0, 0, pix)
    p.end()
    return result


def load_icon(filename: str, size: int = 20, color: str | None = None) -> QPixmap:
    """Charge une icône, la centre dans un carré transparent size×size et la teinte.
    Gère automatiquement le ratio HiDPI de l'écran."""
    from PyQt6.QtWidgets import QApplication
    app = QApplication.instance()
    dpr = app.devicePixelRatio() if app else 1.0
    phys = int(size * dpr)

    path = _find(filename)
    if not path:
        return QPixmap()
    pix = QPixmap(path)
    if pix.isNull():
        return QPixmap()
    scaled = pix.scaled(
        phys, phys,
        Qt.AspectRatioMode.KeepAspectRatio,
        Qt.TransformationMode.SmoothTransformation,
    )
    if scaled.width() == phys and scaled.height() == phys:
        out = tint(scaled, color) if color else scaled
    else:
        # Centre l'image sur un canvas carré transparent — évite l'écrasement des icônes non carrées
        canvas = QPixmap(phys, phys)
        canvas.fill(Qt.GlobalColor.transparent)
        p = QPainter(canvas)
        p.drawPixmap((phys - scaled.width()) // 2, (phys - scaled.height()) // 2, scaled)
        p.end()
        out = tint(canvas, color) if color else canvas
    out.setDevicePixelRatio(dpr)
    return out


def app_icon() -> QIcon:
    """Icône principale de l'application — charge le .ico pré-rendu (LANCZOS) en priorité."""
    # Le .ico contient des pixels pré-rendus à chaque taille via Pillow LANCZOS
    # → beaucoup plus net que rescaler un PNG via Qt bilinéaire
    ico_path = os.path.join(_ASSETS, "pandora_badge.ico")
    if os.path.isfile(ico_path):
        icon = QIcon(ico_path)
        if not icon.isNull():
            return icon
    # Fallback : scaling PNG si le .ico est absent (mode dev sans build)
    icon = QIcon()
    for name in ("app_icon.png", "pandora_badge.png"):
        path = os.path.join(_ASSETS, name)
        if not os.path.isfile(path):
            continue
        pix = QPixmap(path)
        if pix.isNull():
            continue
        for size in (16, 32, 48, 64, 128, 256):
            icon.addPixmap(
                pix.scaled(size, size,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation),
                QIcon.Mode.Normal,
                QIcon.State.Off,
            )
        return icon
    return icon


def badge_pixmap(size: int = 32) -> QPixmap:
    """Badge 'P' PANDORA."""
    path = os.path.join(_ASSETS, "pandora_badge.png")
    if not os.path.isfile(path):
        return QPixmap()
    return QPixmap(path).scaled(
        size, size,
        Qt.AspectRatioMode.KeepAspectRatio,
        Qt.TransformationMode.SmoothTransformation,
    )


def title_pixmap(width: int = 280) -> QPixmap:
    """Wordmark PANDORA (pandora_titles.png)."""
    path = os.path.join(_ASSETS, "pandora_titles.png")
    if not os.path.isfile(path):
        return QPixmap()
    pix = QPixmap(path)
    if pix.isNull():
        return QPixmap()
    return pix.scaledToWidth(width, Qt.TransformationMode.SmoothTransformation)


def _svg_to_pixmap(svg_path: str, size: int) -> QPixmap:
    """Rend un fichier SVG en QPixmap carré. Retourne QPixmap() si QtSvg absent."""
    try:
        from PyQt6.QtSvg import QSvgRenderer
    except ImportError:
        return QPixmap()
    renderer = QSvgRenderer(svg_path)
    if not renderer.isValid():
        return QPixmap()
    pix = QPixmap(size, size)
    pix.fill(Qt.GlobalColor.transparent)
    p = QPainter(pix)
    renderer.render(p)
    p.end()
    return pix


def claude_icon_pixmap(size: int = 16, color: str | None = None) -> QPixmap:
    """Logo Claude (claude-logo.svg) rendu en QPixmap, avec teinte optionnelle."""
    path = os.path.join(_ASSETS, "claude-logo.svg")
    if not os.path.isfile(path):
        return QPixmap()
    pix = _svg_to_pixmap(path, size)
    return tint(pix, color) if (color and not pix.isNull()) else pix


class _HoverIconFilter(QObject):
    """Event filter qui swape l'icône d'un bouton au survol."""
    def __init__(self, btn, pix_normal: QPixmap, pix_hover: QPixmap):
        super().__init__(btn)
        self._btn = btn
        self._n   = QIcon(pix_normal)
        self._h   = QIcon(pix_hover)

    def eventFilter(self, obj, event):
        if obj is self._btn:
            if event.type() == QEvent.Type.Enter:
                self._btn.setIcon(self._h)
            elif event.type() in (QEvent.Type.Leave, QEvent.Type.MouseButtonRelease):
                self._btn.setIcon(self._n)
        return False


def install_hover_icon(btn, pix_normal: QPixmap, pix_hover: QPixmap, icon_size: int = 16):
    """
    Attache un filtre de survol sur btn pour swaper l'icône entre pix_normal et pix_hover.
    Définit aussi l'icône initiale et l'iconSize. Le filtre est parented au bouton (pas de fuite).
    """
    btn.setIcon(QIcon(pix_normal))
    btn.setIconSize(QSize(icon_size, icon_size))
    btn.setText("")
    f = _HoverIconFilter(btn, pix_normal, pix_hover)
    btn.installEventFilter(f)
