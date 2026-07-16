"""ui/chooser.py — Fenêtre de choix PANDORA | Cinéma / Live."""

import os
import sys

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QGraphicsDropShadowEffect,
)
from PyQt6.QtCore import Qt, pyqtSignal, QSize
from PyQt6.QtGui import QColor, QIcon, QPixmap
from ui.styles import CP, PANDORA_STYLESHEET
from ui.icons import badge_pixmap, load_icon, app_icon
from core.i18n import get_lang, set_lang

_ASSETS = (os.path.join(sys._MEIPASS, "assets") if getattr(sys, "frozen", False)
           else os.path.join(os.path.dirname(os.path.dirname(__file__)), "assets"))


def _glow(widget: QWidget, color: str, radius: int = 22):
    fx = QGraphicsDropShadowEffect()
    fx.setBlurRadius(radius)
    fx.setColor(QColor(color))
    fx.setOffset(0, 0)
    widget.setGraphicsEffect(fx)


def _load_logo(filename: str, max_w: int = 180, max_h: int = 90) -> QPixmap:
    """Charge un logo depuis assets/icons/, redimensionné pour tenir dans max_w×max_h."""
    path = os.path.join(_ASSETS, "icons", filename)
    if not os.path.isfile(path):
        return QPixmap()
    pix = QPixmap(path)
    if pix.isNull():
        return QPixmap()
    return pix.scaled(max_w, max_h,
                      Qt.AspectRatioMode.KeepAspectRatio,
                      Qt.TransformationMode.SmoothTransformation)


class _ModuleBtn(QWidget):
    clicked = pyqtSignal()

    def __init__(self, icon_char: str, label: str, subtitle: str, accent: str,
                 img_normal: str = "", img_active: str = ""):
        super().__init__()
        self._accent = accent
        self.setFixedSize(230, 280)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setObjectName("module_btn")
        self._s_normal = (
            f"QWidget#module_btn{{background:{CP['bg2']};"
            f"border:1.5px solid {CP['border']};border-radius:18px;}}"
        )
        self._s_hover = (
            f"QWidget#module_btn{{background:{accent}10;"
            f"border:1.5px solid {accent};border-radius:18px;}}"
        )
        self.setStyleSheet(self._s_normal)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(20, 28, 20, 24)
        lay.setSpacing(12)
        lay.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # ── Image / icône ──────────────────────────────────────────────────────
        self._ico_lbl = QLabel()
        self._ico_lbl.setFixedSize(182, 90)
        self._ico_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._ico_lbl.setStyleSheet("background:transparent;border:none;")

        self._pix_normal = _load_logo(img_normal) if img_normal else QPixmap()
        self._pix_active = _load_logo(img_active) if img_active else QPixmap()

        if not self._pix_normal.isNull():
            self._ico_lbl.setPixmap(self._pix_normal)
        elif not self._pix_active.isNull():
            self._ico_lbl.setPixmap(self._pix_active)
        else:
            self._ico_lbl.setText(icon_char)
            self._ico_lbl.setStyleSheet(
                f"background:{accent}18;border-radius:14px;"
                f"font-size:40px;border:none;"
            )

        _glow(self._ico_lbl, accent, 28)
        lay.addWidget(self._ico_lbl, 0, Qt.AlignmentFlag.AlignCenter)

        # ── Label ──────────────────────────────────────────────────────────────
        lbl = QLabel(label)
        lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl.setStyleSheet(
            f"color:{CP['text_primary']};font-size:20px;font-weight:800;"
            f"letter-spacing:2px;background:transparent;border:none;"
        )
        lay.addWidget(lbl)

        # ── Sous-titre ─────────────────────────────────────────────────────────
        sub = QLabel(subtitle)
        sub.setAlignment(Qt.AlignmentFlag.AlignCenter)
        sub.setWordWrap(True)
        sub.setStyleSheet(
            f"color:{CP['text_dim']};font-size:10px;"
            f"font-family:'Consolas',monospace;background:transparent;border:none;"
        )
        lay.addWidget(sub)

    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()

    def set_coming_soon(self):
        """Rend le bouton visible mais non-interactif (mode 'Prochainement')."""
        self._coming_soon = True
        self.setCursor(Qt.CursorShape.ArrowCursor)
        dim = CP["text_dim"]
        self._s_normal = (
            f"QWidget#module_btn{{background:{CP['bg2']};"
            f"border:1.5px solid {dim};border-radius:18px;opacity:0.5;}}"
        )
        self._s_hover = self._s_normal
        self.setStyleSheet(self._s_normal)
        if hasattr(self, '_ico_lbl') and self._ico_lbl.graphicsEffect():
            self._ico_lbl.graphicsEffect().setColor(QColor(dim))

    def enterEvent(self, e):
        if getattr(self, "_coming_soon", False):
            return
        self.setStyleSheet(self._s_hover)
        if not self._pix_active.isNull():
            self._ico_lbl.setPixmap(self._pix_active)

    def leaveEvent(self, e):
        if getattr(self, "_coming_soon", False):
            return
        self.setStyleSheet(self._s_normal)
        pix = self._pix_normal if not self._pix_normal.isNull() else self._pix_active
        if not pix.isNull():
            self._ico_lbl.setPixmap(pix)


class ChooserWindow(QWidget):
    cinema_requested = pyqtSignal()
    live_requested   = pyqtSignal()
    lang_changed     = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self.setWindowTitle("PANDORA — by 22eme ARKANE")
        self.setFixedSize(720, 560)
        self.setStyleSheet(PANDORA_STYLESHEET)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(60, 48, 60, 36)
        lay.setSpacing(0)
        lay.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # ── Logo PANDORA ───────────────────────────────────────────────────────
        logo_area = QWidget()
        logo_area.setStyleSheet("background:transparent;")
        ll = QVBoxLayout(logo_area)
        ll.setContentsMargins(0, 0, 0, 0)
        ll.setSpacing(4)
        ll.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # Logo PANDORA officiel (app_icon = pandora_badge.ico) — le MÊME que le splash,
        # la fenêtre principale et l'icône Windows (le chooser utilisait encore l'ancien
        # badge « P » brut de pandora_badge.png).
        pix_badge = app_icon().pixmap(52, 52)
        badge_lbl = QLabel()
        badge_lbl.setFixedSize(52, 52)
        badge_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        if not pix_badge.isNull():
            badge_lbl.setPixmap(pix_badge)
            badge_lbl.setStyleSheet("background:transparent;border:none;")
        else:
            badge_lbl.setText("P")
            badge_lbl.setStyleSheet(
                f"background:qlineargradient(x1:0,y1:0,x2:1,y2:1,"
                f"stop:0 {CP['accent']},stop:1 {CP['accent2']});"
                f"border-radius:13px;color:#07080f;font-size:24px;font-weight:900;"
            )
        ll.addWidget(badge_lbl, 0, Qt.AlignmentFlag.AlignCenter)

        wordmark = QLabel("PANDORA")
        wordmark.setAlignment(Qt.AlignmentFlag.AlignCenter)
        wordmark.setStyleSheet(
            f"color:{CP['text_primary']};font-size:24px;font-weight:800;"
            f"letter-spacing:8px;background:transparent;border:none;"
        )
        ll.addWidget(wordmark)

        tagline = QLabel("by 22eme ARKANE")
        tagline.setAlignment(Qt.AlignmentFlag.AlignCenter)
        tagline.setStyleSheet(
            f"color:{CP['text_dim']};font-size:9px;font-family:'Consolas',monospace;"
            f"letter-spacing:2px;background:transparent;border:none;"
        )
        ll.addWidget(tagline)

        lay.addWidget(logo_area)
        lay.addSpacing(18)

        choose_lbl = QLabel("Choisissez votre espace de travail")
        choose_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        choose_lbl.setStyleSheet(
            f"color:{CP['text_secondary']};font-size:12px;"
            f"background:transparent;border:none;"
        )
        lay.addWidget(choose_lbl)
        lay.addSpacing(28)

        # ── Deux boutons ───────────────────────────────────────────────────────
        btns_row = QHBoxLayout()
        btns_row.setSpacing(36)
        btns_row.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # Sous-titres courts — formulations de Matthieu (2026-07-16), après
        # deux itérations : « Créez un film/une vidéo » vs « live/mapping ».
        self._btn_cinema = _ModuleBtn(
            "🎬", "Cinéma",
            "Créez un film ou une vidéo\ngénérés par IA",
            CP["accent"],
            img_normal="Cinéma_désactiver.png",
            img_active="cinéma.png",
        )
        self._btn_live = _ModuleBtn(
            "◈", "Live",
            "Créez un live vidéo ou\nun mapping générés par IA",
            CP["accent2"],
            img_normal="live_desactiver.png",
            img_active="Live.png",
        )
        self._btn_cinema.clicked.connect(self.cinema_requested)
        self._btn_live.clicked.connect(self.live_requested)

        btns_row.addWidget(self._btn_cinema)
        btns_row.addWidget(self._btn_live)
        lay.addLayout(btns_row)

        lay.addStretch()

        # ── Boutons de langue ──────────────────────────────────────────────────
        self._lang_btns: dict[str, QPushButton] = {}
        lang_row = QHBoxLayout()
        lang_row.setSpacing(6)
        lang_row.setAlignment(Qt.AlignmentFlag.AlignCenter)
        _cur = get_lang()
        for code, flag_file, tooltip in (
            ("fr", "Fr.png", "Français"),
            ("en", "En.png", "English"),
        ):
            btn = QPushButton()
            btn.setFixedSize(32, 32)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setToolTip(tooltip)
            _pix = load_icon(flag_file, 24)
            if not _pix.isNull():
                btn.setIcon(QIcon(_pix))
                btn.setIconSize(QSize(24, 24))
                btn.setText("")
            else:
                btn.setText("FR" if code == "fr" else "EN")
            self._set_lang_btn_style(btn, code == _cur)
            btn.clicked.connect(lambda checked, c=code: self._on_lang(c))
            lang_row.addWidget(btn)
            self._lang_btns[code] = btn
        lay.addLayout(lang_row)

        lay.addSpacing(8)

        # ── Version ────────────────────────────────────────────────────────────
        from core.version import VERSION as _V
        ver = QLabel(f"v{_V}")
        ver.setAlignment(Qt.AlignmentFlag.AlignCenter)
        ver.setStyleSheet(
            f"color:{CP['text_dim']};font-size:9px;font-family:'Consolas',monospace;"
            f"background:transparent;border:none;"
        )
        lay.addWidget(ver)

    @staticmethod
    def _set_lang_btn_style(btn: QPushButton, active: bool):
        bg = "rgba(78,205,196,0.15)" if active else "transparent"
        border = f"1px solid {CP['accent']}" if active else "1px solid transparent"
        btn.setStyleSheet(
            f"QPushButton{{background:{bg};border:{border};"
            f"border-radius:6px;font-size:9px;font-weight:700;color:{CP['text_secondary']};}}"
            f"QPushButton:hover{{background:rgba(255,255,255,0.08);"
            f"border:1px solid {CP['border_bright']};}}"
        )

    def _on_lang(self, code: str):
        if code == get_lang():
            return
        set_lang(code)
        for c, btn in self._lang_btns.items():
            self._set_lang_btn_style(btn, c == code)
        self.lang_changed.emit(code)
