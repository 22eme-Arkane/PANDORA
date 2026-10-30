"""ui/dialog_whats_new.py — La fenêtre « Nouveautés » (Cinéma ET Live).

Ouverte d'elle-même à la première ouverture / création d'un projet après une mise
à jour (main.py → maybe_show), et à la demande depuis les Paramètres. À gauche les
versions, la plus récente en tête ; à droite les nouveautés de celle choisie. La
case « Ne plus afficher » vaut jusqu'à la version suivante (core/release_notes).
"""
from __future__ import annotations

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QColor, QPalette, QTextBlockFormat, QTextCursor
from PyQt6.QtWidgets import (QCheckBox, QDialog, QHBoxLayout, QLabel, QListWidget,
                             QListWidgetItem, QPushButton, QTextBrowser, QVBoxLayout)

from core import release_notes as rn
from core.i18n import get_lang, translate
from core.version import VERSION
from ui.styles import CP
from ui.widgets import disable_default_buttons


def _airy(doc) -> None:
    """Le Markdown de Qt colle les paragraphes et creuse les listes : un peu
    d'air entre les blocs, un interligne plus ouvert, des puces moins en retrait."""
    doc.setIndentWidth(18)
    blk = doc.begin()
    while blk.isValid():
        fmt = blk.blockFormat()
        fmt.setBottomMargin(5 if blk.textList() else 10)
        fmt.setLineHeight(125, QTextBlockFormat.LineHeightTypes.ProportionalHeight.value)
        QTextCursor(blk).setBlockFormat(fmt)
        blk = blk.next()


class WhatsNewDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._lang = "en" if get_lang() == "en" else "fr"
        self._entries = rn.entries(self._lang)
        self.setWindowTitle(translate("Nouveautés de PANDORA"))
        self.setMinimumSize(860, 620)
        self.setStyleSheet(f"QDialog{{background:{CP['bg1']};}}")

        root = QVBoxLayout(self)
        root.setContentsMargins(22, 20, 22, 16)
        root.setSpacing(12)

        title = QLabel(translate("Nouveautés de PANDORA"))
        title.setStyleSheet(f"color:{CP['text_primary']};font-size:20px;font-weight:700;"
                            "letter-spacing:0.5px;background:transparent;")
        sub = QLabel(translate("Version {v} — et l'historique des versions précédentes.")
                     .format(v=VERSION))
        sub.setStyleSheet(f"color:{CP['text_secondary']};font-size:12px;background:transparent;")
        root.addWidget(title)
        root.addWidget(sub)

        body = QHBoxLayout()
        body.setSpacing(12)
        self.versions = QListWidget()
        self.versions.setFixedWidth(184)
        self.versions.setStyleSheet(
            f"QListWidget{{background:{CP['bg2']};border:1px solid {CP['border']};"
            f"border-radius:8px;padding:4px;outline:none;color:{CP['text_secondary']};"
            "font-size:12px;}"
            "QListWidget::item{padding:7px 8px;border-radius:6px;}"
            f"QListWidget::item:hover{{background:{CP['bg3']};color:{CP['text_primary']};}}"
            f"QListWidget::item:selected{{background:{CP['bg4']};color:{CP['accent']};"
            "font-weight:700;}")
        for e in self._entries:
            label = e["version"]
            if e["version"] == VERSION:
                label += "  ·  " + translate("cette version")
            item = QListWidgetItem(f"{label}\n{rn.format_date(e['date'], self._lang)}")
            item.setData(Qt.ItemDataRole.UserRole, e["version"])
            self.versions.addItem(item)
        body.addWidget(self.versions)

        self.text = QTextBrowser()
        self.text.setOpenExternalLinks(True)
        self.text.setStyleSheet(
            f"QTextBrowser{{background:{CP['bg2']};border:1px solid {CP['border']};"
            f"border-radius:8px;padding:14px 18px;color:{CP['text_primary']};font-size:13px;}}")
        pal = self.text.palette()
        pal.setColor(QPalette.ColorRole.Link, QColor(CP["accent"]))
        self.text.setPalette(pal)
        body.addWidget(self.text, 1)
        root.addLayout(body, 1)

        foot = QHBoxLayout()
        self.hide_box = QCheckBox(translate("Ne plus afficher jusqu'à la prochaine version"))
        self.hide_box.setChecked(rn.is_hidden())
        self.hide_box.setStyleSheet(f"color:{CP['text_secondary']};font-size:12px;"
                                    "background:transparent;")
        foot.addWidget(self.hide_box)
        foot.addStretch()
        self.btn_close = QPushButton(translate("Fermer"))
        self.btn_close.setMinimumSize(120, 36)
        self.btn_close.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_close.clicked.connect(self.accept)
        foot.addWidget(self.btn_close)
        root.addLayout(foot)

        self.versions.currentRowChanged.connect(self._show)
        if self._entries:
            self.versions.setCurrentRow(0)
        else:
            self.text.setPlainText(translate("Aucune note de version n'est disponible."))
        disable_default_buttons(self)

    def _show(self, row: int):
        if not 0 <= row < len(self._entries):
            return
        e = self._entries[row]
        head = translate("Version {v}").format(v=e["version"])
        self.text.setMarkdown(f"## {head}\n\n*{rn.format_date(e['date'], self._lang)}*\n\n"
                              f"{e['body']}\n")
        _airy(self.text.document())
        self.text.verticalScrollBar().setValue(0)

    def done(self, code: int):
        try:
            rn.set_hidden(self.hide_box.isChecked())
        except Exception:
            pass
        super().done(code)


def open_whats_new(parent=None) -> WhatsNewDialog:
    dlg = WhatsNewDialog(parent)
    dlg.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)
    dlg.open()
    return dlg


_pending = False


def maybe_show(parent=None, delay_ms: int = 450) -> bool:
    """À l'ouverture d'un projet : la fenêtre, une fois par session, sauf si
    cette version est masquée. Rend vrai si elle est programmée. Une fenêtre
    fermée avant l'échéance (bascule de projet) ne compte pas comme vue."""
    global _pending
    if _pending or not rn.should_show():
        return False
    _pending = True

    def _go():
        global _pending
        _pending = False
        try:
            if parent is not None and not parent.isVisible():
                return
            rn.mark_shown()
            open_whats_new(parent)
        except RuntimeError:            # fenêtre détruite entre-temps
            pass
    QTimer.singleShot(delay_ms, _go)
    return True
