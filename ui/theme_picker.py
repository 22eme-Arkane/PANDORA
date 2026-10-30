"""ui/theme_picker.py — Le choix de l'apparence (Paramètres, Cinéma ET Live).

Un MENU DÉROULANT (Matthieu 27/10/2026 : « les apparences, il faut que ce soit un
menu déroulant dans les réglages ») : chaque thème de ui/themes avec un petit
aperçu de l'interface peint avec SA palette (barre latérale, panneau, bouton
d'accent, accent secondaire, lignes de texte), et sa phrase à côté. Un choix
enregistre `theme` dans la config — chargée ENTIÈRE puis réécrite (save_config
remplace tout le fichier) — et propose de redémarrer : le thème se lit au
démarrage.
"""
from __future__ import annotations

import sys

from PyQt6.QtCore import Qt, QRectF, QSize, pyqtSignal
from PyQt6.QtGui import QColor, QIcon, QPainter, QPainterPath, QPen, QPixmap
from PyQt6.QtWidgets import (QApplication, QComboBox, QHBoxLayout, QLabel, QMessageBox,
                             QPushButton, QVBoxLayout, QWidget)

from core.i18n import translate
from ui import themes
from ui.styles import CP


def paint_swatch(p: QPainter, r: QRectF, key: str) -> None:
    """Mini-interface peinte aux couleurs d'un thème, dans le rectangle `r`."""
    t = themes.THEMES[key]
    cp = t["cp"]
    s = r.height() / 64.0
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    clip = QPainterPath()
    clip.addRoundedRect(r, 7 * s, 7 * s)
    p.setClipPath(clip)
    p.fillRect(r, QColor(cp["bg1"]))
    side = QRectF(r.left(), r.top(), 22 * s, r.height())
    p.fillRect(side, QColor(cp["sidebar"]))
    for i, c in enumerate((t["nav_active"], cp["text_dim"], cp["text_dim"])):
        p.setBrush(QColor(c))
        p.setPen(Qt.PenStyle.NoPen)
        p.drawRoundedRect(QRectF(side.left() + 6 * s, r.top() + (9 + i * 15) * s,
                                 10 * s, 8 * s), 2 * s, 2 * s)
    panel = QRectF(side.right() + 8 * s, r.top() + 8 * s, r.width() - side.width() - 16 * s,
                   r.height() - 16 * s)
    p.setBrush(QColor(cp["bg3"]))
    p.setPen(QPen(QColor(cp["border_bright"]), max(1.0, s)))
    p.drawRoundedRect(panel, 5 * s, 5 * s)
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QColor(cp["text_primary"]))
    p.drawRoundedRect(QRectF(panel.left() + 8 * s, panel.top() + 8 * s, panel.width() * 0.45,
                             5 * s), 2 * s, 2 * s)
    p.setBrush(QColor(cp["text_secondary"]))
    p.drawRoundedRect(QRectF(panel.left() + 8 * s, panel.top() + 18 * s, panel.width() * 0.62,
                             4 * s), 2 * s, 2 * s)
    btn = QRectF(panel.left() + 8 * s, panel.bottom() - 17 * s, 44 * s, 11 * s)
    p.setBrush(QColor(cp["accent"]))
    p.drawRoundedRect(btn, 3 * s, 3 * s)
    p.setBrush(QColor(cp["on_accent"]))
    p.drawRoundedRect(QRectF(btn.left() + 9 * s, btn.center().y() - 1.5 * s, 26 * s, 3 * s),
                      1.5 * s, 1.5 * s)
    p.setBrush(QColor(cp["accent2"]))
    p.drawEllipse(QRectF(btn.right() + 8 * s, btn.top() + s, 9 * s, 9 * s))
    p.setBrush(QColor(cp["green"]))
    p.drawEllipse(QRectF(btn.right() + 22 * s, btn.top() + s, 9 * s, 9 * s))


_ICON_SIZE = QSize(64, 32)


def swatch_icon(key: str) -> QIcon:
    icon = QIcon()
    for dpr in (1.0, 2.0):
        pm = QPixmap(int(_ICON_SIZE.width() * dpr), int(_ICON_SIZE.height() * dpr))
        pm.setDevicePixelRatio(dpr)
        pm.fill(Qt.GlobalColor.transparent)
        p = QPainter(pm)
        paint_swatch(p, QRectF(0.5, 0.5, _ICON_SIZE.width() - 1.0, _ICON_SIZE.height() - 1.0),
                     key)
        p.end()
        icon.addPixmap(pm)
    return icon


def restart_app(parent=None) -> bool:
    """Ferme les fenêtres (chacune peut refuser) puis relance PANDORA."""
    from PyQt6.QtCore import QProcess
    app = QApplication.instance()
    if app is None:
        return False
    app.closeAllWindows()
    if any(w.isVisible() for w in app.topLevelWidgets() if w.isWindow()):
        return False                       # une fenêtre a refusé de se fermer
    args = sys.argv[1:] if getattr(sys, "frozen", False) else sys.argv
    if not QProcess.startDetached(sys.executable, list(args)):
        return False
    app.quit()
    return True


class ThemePicker(QWidget):
    """Le menu déroulant des apparences et la phrase du thème choisi.
    `chosen(key)` après chaque choix enregistré."""
    chosen = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        from core.config import load_config
        self._saved = themes.normalize(load_config().get("theme"))
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(8)
        lay = QHBoxLayout()
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(12)
        outer.addLayout(lay)
        self.combo = QComboBox()
        self.combo.setFixedHeight(40)
        self.combo.setMinimumWidth(240)
        self.combo.setIconSize(_ICON_SIZE)
        self.combo.setCursor(Qt.CursorShape.PointingHandCursor)
        self.combo.setStyleSheet(
            f"QComboBox{{background:{CP['bg2']};border:1px solid {CP['border']};"
            f"border-radius:8px;color:{CP['text_primary']};font-size:12px;padding:0 10px;}}"
            f"QComboBox:hover{{border-color:{CP['border_bright']};}}"
            f"QComboBox::drop-down{{border:none;width:22px;}}"
            f"QComboBox QAbstractItemView{{background:{CP['bg3']};"
            f"border:1px solid {CP['border_bright']};color:{CP['text_primary']};"
            f"selection-background-color:{CP['accent_dim']};outline:none;}}")
        for key in themes.ORDER:
            t = themes.THEMES[key]
            self.combo.addItem(swatch_icon(key), translate(t["name"]), key)
            self.combo.setItemData(self.combo.count() - 1, translate(t["desc"]),
                                   Qt.ItemDataRole.ToolTipRole)
        i = self.combo.findData(self._saved)
        self.combo.setCurrentIndex(i if i >= 0 else 0)
        lay.addWidget(self.combo)
        self.desc = QLabel()
        self.desc.setWordWrap(True)
        self.desc.setStyleSheet(
            f"color:{CP['text_secondary']};font-size:11px;background:transparent;border:none;")
        lay.addWidget(self.desc, 1)
        # Redémarrage nécessaire : dit en ROUGE, avec son bouton, tant que le
        # thème enregistré n'est pas celui affiché (Matthieu 27/10/2026 : « il
        # faut que ce soit prononcé », un petit texte gris passait inaperçu).
        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(10)
        self.notice = QLabel(translate(
            "Redémarrez PANDORA pour appliquer ce thème."))
        self.notice.setStyleSheet(
            f"color:{CP['red']};font-size:12px;font-weight:700;background:transparent;")
        self.btn_restart = QPushButton(translate("Redémarrer maintenant"))
        self.btn_restart.setFixedHeight(30)
        self.btn_restart.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_restart.setStyleSheet(
            f"QPushButton{{background:transparent;color:{CP['red']};"
            f"border:1px solid {CP['red']};border-radius:7px;font-size:11px;"
            f"font-weight:700;padding:0 14px;}}"
            f"QPushButton:hover{{background:rgba(255,79,106,0.12);}}")
        self.btn_restart.clicked.connect(lambda: restart_app(self))
        row.addWidget(self.notice)
        row.addWidget(self.btn_restart)
        row.addStretch(1)
        outer.addLayout(row)
        self._show_desc()
        self._sync_notice()
        self.combo.currentIndexChanged.connect(self._on_index)

    def current(self) -> str:
        return self._saved

    def needs_restart(self) -> bool:
        return self._saved != themes.current_key()

    def _sync_notice(self) -> None:
        need = self.needs_restart()
        self.notice.setVisible(need)
        self.btn_restart.setVisible(need)

    def select(self, key: str) -> None:
        """Choisir un thème comme au clic dans le menu."""
        i = self.combo.findData(themes.normalize(key))
        if i >= 0:
            if i == self.combo.currentIndex():
                self._pick(self.combo.itemData(i))
            else:
                self.combo.setCurrentIndex(i)

    def _show_desc(self) -> None:
        key = self.combo.currentData() or themes.DEFAULT
        self.desc.setText(translate(themes.THEMES[key]["desc"]))

    def _on_index(self, _i: int) -> None:
        self._show_desc()
        key = self.combo.currentData()
        if key:
            self._pick(key)

    def _pick(self, key: str):
        if key == self._saved:
            return
        from core.config import load_config, save_config
        cfg = load_config()
        cfg["theme"] = key
        save_config(cfg)
        self._saved = key
        self._sync_notice()
        self.chosen.emit(key)
        if key == themes.current_key():
            return                         # retour au thème déjà affiché
        box = QMessageBox(self)
        box.setWindowTitle(translate("Thème enregistré"))
        box.setText(translate("Le thème « {name} » sera appliqué au redémarrage de PANDORA.")
                    .format(name=translate(themes.THEMES[key]["name"])))
        now = box.addButton(translate("Redémarrer maintenant"), QMessageBox.ButtonRole.AcceptRole)
        box.addButton(translate("Plus tard"), QMessageBox.ButtonRole.RejectRole)
        box.exec()
        if box.clickedButton() is now:
            restart_app(self)
