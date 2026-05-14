import os
from datetime import datetime
from PyQt6.QtWidgets import (
    QWidget, QDialog, QHBoxLayout, QVBoxLayout, QLabel, QPushButton,
    QScrollArea, QFileDialog, QFrame, QLineEdit,
    QMessageBox, QGraphicsDropShadowEffect,
)
from PyQt6.QtCore import Qt, pyqtSignal, QSize
from PyQt6.QtGui import QPixmap, QColor, QIcon
from ui.styles import CP, PANDORA_STYLESHEET
from ui.icons import badge_pixmap, load_icon
import core.project as project_api
from core.i18n import get_lang, set_lang, tr, LANGUAGES

import sys as _sys
_ASSETS = (os.path.join(_sys._MEIPASS, "assets") if getattr(_sys, "frozen", False)
           else os.path.join(os.path.dirname(os.path.dirname(__file__)), "assets"))


# ── Helpers ───────────────────────────────────────────────────────────────────

def _relative_time(iso_str: str) -> str:
    try:
        dt    = datetime.fromisoformat(iso_str)
        delta = datetime.now() - dt
        if delta.days == 0:
            h = delta.seconds // 3600
            if h == 0:
                m = delta.seconds // 60
                return "À l'instant" if m < 2 else f"Il y a {m} min"
            return f"Il y a {h}h"
        if delta.days == 1:
            return "Hier"
        if delta.days < 7:
            return f"Il y a {delta.days} jours"
        return iso_str[:10]
    except Exception:
        return ""


def _glow(widget: QWidget, color: str, radius: int = 22):
    fx = QGraphicsDropShadowEffect()
    fx.setBlurRadius(radius)
    fx.setColor(QColor(color))
    fx.setOffset(0, 0)
    widget.setGraphicsEffect(fx)


# ── Dialogue Nouveau Projet ───────────────────────────────────────────────────

class NewProjectDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Nouveau projet PANDORA")
        self.setFixedSize(500, 260)
        self.setStyleSheet(PANDORA_STYLESHEET + f"QDialog{{background:{CP['bg2']};}}")
        self._result_data = None

        lay = QVBoxLayout(self)
        lay.setContentsMargins(28, 24, 28, 24)
        lay.setSpacing(14)

        title = QLabel("Nouveau projet")
        title.setStyleSheet(
            f"color:{CP['text_primary']};font-size:18px;font-weight:700;background:transparent;"
        )
        lay.addWidget(title)

        def _lbl(text):
            l = QLabel(text)
            l.setStyleSheet(f"color:{CP['text_secondary']};font-size:11px;background:transparent;")
            return l

        def _input(placeholder):
            e = QLineEdit()
            e.setPlaceholderText(placeholder)
            e.setFixedHeight(38)
            e.setStyleSheet(
                f"QLineEdit{{background:{CP['bg3']};border:1px solid {CP['border']};"
                f"border-radius:6px;color:{CP['text_primary']};font-size:13px;padding:0 12px;}}"
                f"QLineEdit:focus{{border-color:{CP['accent']};}}"
            )
            return e

        lay.addWidget(_lbl("Nom du projet"))
        self._name = _input("Mon Film")
        lay.addWidget(self._name)

        lay.addWidget(_lbl("Emplacement"))
        loc_row = QHBoxLayout()
        loc_row.setSpacing(8)
        self._location = QLineEdit()
        self._location.setReadOnly(True)
        self._location.setFixedHeight(38)
        from core.config import load_config as _load_cfg
        _cfg = _load_cfg()
        _last = _cfg.get("last_project_location", "").strip()
        self._location.setText(_last or project_api._DEFAULT_DIR)
        self._location.setStyleSheet(
            f"QLineEdit{{background:{CP['bg3']};border:1px solid {CP['border']};"
            f"border-radius:6px;color:{CP['text_secondary']};"
            f"font-size:11px;font-family:'Consolas',monospace;padding:0 12px;}}"
        )
        btn_browse = QPushButton("Choisir…")
        btn_browse.setFixedSize(90, 38)
        btn_browse.setStyleSheet(
            f"QPushButton{{background:{CP['bg4']};color:{CP['text_secondary']};"
            f"border:1px solid {CP['border']};border-radius:6px;font-size:11px;font-weight:700;}}"
            f"QPushButton:hover{{background:{CP['border_bright']};color:{CP['text_primary']};}}"
        )
        btn_browse.clicked.connect(self._browse)
        loc_row.addWidget(self._location, 1)
        loc_row.addWidget(btn_browse)
        lay.addLayout(loc_row)

        lay.addStretch()

        btn_row = QHBoxLayout()
        btn_cancel = QPushButton("Annuler")
        btn_cancel.setFixedHeight(40)
        btn_cancel.setStyleSheet(
            f"QPushButton{{background:transparent;color:{CP['text_secondary']};"
            f"border:1px solid {CP['border']};border-radius:8px;font-size:12px;font-weight:700;padding:0 20px;}}"
            f"QPushButton:hover{{background:{CP['bg3']};color:{CP['text_primary']};}}"
        )
        btn_cancel.clicked.connect(self.reject)

        btn_create = QPushButton("✦  Créer le projet")
        btn_create.setFixedHeight(40)
        btn_create.setStyleSheet(
            f"QPushButton{{background:{CP['accent']};color:#07080f;border:none;"
            f"border-radius:8px;font-size:13px;font-weight:700;letter-spacing:1px;padding:0 24px;}}"
            f"QPushButton:hover{{background:#6eded6;}}"
            f"QPushButton:pressed{{background:{CP['accent_dim']};color:#fff;}}"
        )
        btn_create.clicked.connect(self._create)
        btn_create.setDefault(True)

        btn_row.addWidget(btn_cancel)
        btn_row.addStretch()
        btn_row.addWidget(btn_create)
        lay.addLayout(btn_row)

        self._name.setFocus()

    def _browse(self):
        path = QFileDialog.getExistingDirectory(
            self, "Choisir l'emplacement", self._location.text()
        )
        if path:
            self._location.setText(os.path.normpath(path))

    def _create(self):
        name = self._name.text().strip()
        if not name:
            self._name.setPlaceholderText("← Entre un nom de projet")
            return
        parent = self._location.text().strip() or project_api._DEFAULT_DIR
        try:
            self._result_data = project_api.create_project(name, parent)
            from core.config import load_config as _load_cfg, save_config as _save_cfg
            _cfg = _load_cfg()
            _cfg["last_project_location"] = parent
            _save_cfg(_cfg)
            self.accept()
        except Exception as e:
            QMessageBox.critical(self, "Erreur", f"Impossible de créer le projet :\n{e}")

    def get_project(self) -> dict | None:
        return self._result_data


# ── Carte projet récent ───────────────────────────────────────────────────────

class ProjectCard(QWidget):
    clicked = pyqtSignal(dict)

    def __init__(self, data: dict):
        super().__init__()
        self._data = data
        self.setFixedSize(188, 172)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        self._s_normal = (
            f"QWidget#card{{background:{CP['bg2']};border:1px solid {CP['border']};"
            f"border-radius:10px;}}"
        )
        self._s_hover = (
            f"QWidget#card{{background:{CP['bg3']};border:1px solid {CP['border_bright']};"
            f"border-radius:10px;}}"
        )
        self.setObjectName("card")
        self.setStyleSheet(self._s_normal)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)

        # Miniature
        thumb = QLabel()
        thumb.setFixedHeight(104)
        thumb.setAlignment(Qt.AlignmentFlag.AlignCenter)
        thumb.setStyleSheet(
            f"background:{CP['bg3']};border-radius:9px 9px 0 0;"
            f"font-size:32px;color:{CP['text_dim']};"
        )
        thumb_path = data.get("thumbnail", "")
        if thumb_path and os.path.isfile(thumb_path):
            pix = QPixmap(thumb_path).scaled(
                188, 104,
                Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                Qt.TransformationMode.SmoothTransformation,
            )
            thumb.setPixmap(pix)
        else:
            thumb.setText("🎬")
        lay.addWidget(thumb)

        # Info
        info = QWidget()
        info.setStyleSheet("background:transparent;")
        il = QVBoxLayout(info)
        il.setContentsMargins(12, 8, 12, 10)
        il.setSpacing(3)

        name_lbl = QLabel(data.get("name", "Projet").upper())
        name_lbl.setStyleSheet(
            f"color:{CP['text_primary']};font-size:11px;font-weight:700;"
            f"letter-spacing:0.5px;background:transparent;border:none;"
        )
        name_lbl.setWordWrap(True)

        time_str = _relative_time(data.get("modified_at", ""))
        time_lbl = QLabel(f"Modifié  {time_str}" if time_str else "")
        time_lbl.setStyleSheet(
            f"color:{CP['text_dim']};font-size:9px;"
            f"font-family:'Consolas',monospace;background:transparent;border:none;"
        )

        il.addWidget(name_lbl)
        il.addWidget(time_lbl)
        lay.addWidget(info)

    def enterEvent(self, e):
        self.setStyleSheet(self._s_hover)

    def leaveEvent(self, e):
        self.setStyleSheet(self._s_normal)

    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self._data)


# ── Panneau gauche ────────────────────────────────────────────────────────────

class _LeftPanel(QWidget):
    new_project  = pyqtSignal()
    open_project = pyqtSignal()
    lang_changed = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self.setFixedWidth(390)
        self.setStyleSheet(f"background:{CP['bg1']};")

        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)

        # ── Logo ──────────────────────────────────────────────────────────────
        logo_area = QWidget()
        logo_area.setStyleSheet("background:transparent;")
        ll = QVBoxLayout(logo_area)
        ll.setContentsMargins(40, 44, 40, 0)
        ll.setSpacing(6)
        ll.setAlignment(Qt.AlignmentFlag.AlignHCenter)

        # Badge "P"
        pix_badge = badge_pixmap(72)
        badge_lbl = QLabel()
        badge_lbl.setFixedSize(72, 72)
        badge_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        if not pix_badge.isNull():
            badge_lbl.setPixmap(pix_badge)
            badge_lbl.setStyleSheet("background:transparent;border:none;")
        else:
            badge_lbl.setText("P")
            badge_lbl.setStyleSheet(
                f"background:qlineargradient(x1:0,y1:0,x2:1,y2:1,"
                f"stop:0 {CP['accent']},stop:1 {CP['accent2']});"
                f"border-radius:18px;color:#07080f;font-size:34px;font-weight:900;"
            )
        ll.addWidget(badge_lbl, 0, Qt.AlignmentFlag.AlignHCenter)

        # Wordmark
        img_lbl = QLabel("PANDORA")
        img_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        img_lbl.setStyleSheet(
            f"color:{CP['text_primary']};font-size:28px;font-weight:800;"
            f"letter-spacing:8px;background:transparent;border:none;"
        )
        ll.addWidget(img_lbl)

        tagline = QLabel("by 22eme ARKANE")
        tagline.setAlignment(Qt.AlignmentFlag.AlignCenter)
        tagline.setStyleSheet(
            f"color:{CP['text_dim']};font-size:10px;font-family:'Consolas',monospace;"
            f"letter-spacing:2px;background:transparent;border:none;"
        )
        ll.addWidget(tagline)
        lay.addWidget(logo_area)

        lay.addStretch()

        # ── Carte boutons ─────────────────────────────────────────────────────
        card = QFrame()
        card.setStyleSheet(
            f"QFrame{{background:{CP['bg2']};border:1px solid {CP['border']};"
            f"border-radius:14px;}}"
        )
        cl = QVBoxLayout(card)
        cl.setContentsMargins(28, 28, 28, 28)
        cl.setSpacing(14)

        sub = QLabel("Suite de pré-production IA")
        sub.setAlignment(Qt.AlignmentFlag.AlignCenter)
        sub.setStyleSheet(
            f"color:{CP['text_secondary']};font-size:11px;background:transparent;border:none;"
        )
        cl.addWidget(sub)
        cl.addSpacing(6)

        btn_new = QPushButton("  NOUVEAU PROJET")
        btn_new.setFixedHeight(52)
        btn_new.setStyleSheet(
            f"QPushButton{{background:transparent;color:{CP['accent']};"
            f"border:1.5px solid {CP['accent']};border-radius:10px;"
            f"font-size:13px;font-weight:700;letter-spacing:1.5px;}}"
            f"QPushButton:hover{{background:rgba(78,205,196,0.1);}}"
            f"QPushButton:pressed{{background:rgba(78,205,196,0.2);}}"
        )
        btn_new.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_new.clicked.connect(self.new_project)
        pix_new = load_icon("new_project.png", 20, CP["accent"])
        if not pix_new.isNull():
            from PyQt6.QtGui import QIcon as _QIcon
            btn_new.setIcon(_QIcon(pix_new))
        _glow(btn_new, CP["accent"], 18)
        cl.addWidget(btn_new)

        btn_open = QPushButton("  OUVRIR UN PROJET")
        btn_open.setFixedHeight(52)
        btn_open.setStyleSheet(
            f"QPushButton{{background:transparent;color:{CP['accent2']};"
            f"border:1.5px solid {CP['accent2']};border-radius:10px;"
            f"font-size:13px;font-weight:700;letter-spacing:1.5px;}}"
            f"QPushButton:hover{{background:rgba(124,107,255,0.1);}}"
            f"QPushButton:pressed{{background:rgba(124,107,255,0.2);}}"
        )
        btn_open.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_open.clicked.connect(self.open_project)
        pix_open = load_icon("open_project.png", 20, CP["accent2"])
        if not pix_open.isNull():
            from PyQt6.QtGui import QIcon as _QIcon
            btn_open.setIcon(_QIcon(pix_open))
        _glow(btn_open, CP["accent2"], 18)
        cl.addWidget(btn_open)

        card_wrap = QWidget()
        card_wrap.setStyleSheet("background:transparent;")
        cw = QHBoxLayout(card_wrap)
        cw.setContentsMargins(28, 0, 28, 0)
        cw.addWidget(card)
        lay.addWidget(card_wrap)

        lay.addStretch()

        # ── Bas de page ───────────────────────────────────────────────────────
        # Sélecteur de langue
        self._splash_lang_btns: dict[str, QPushButton] = {}
        lang_row = QHBoxLayout()
        lang_row.setSpacing(6)
        lang_row.setAlignment(Qt.AlignmentFlag.AlignCenter)
        _flag_map = {"fr": "Fr.png", "en": "En.png"}
        _cur = get_lang()
        for code, flag_file in _flag_map.items():
            btn = QPushButton()
            btn.setFixedSize(32, 32)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setToolTip("Français" if code == "fr" else "English")
            _pix = load_icon(flag_file, 24)
            if not _pix.isNull():
                btn.setIcon(QIcon(_pix))
                btn.setIconSize(QSize(24, 24))
                btn.setText("")
            else:
                btn.setText("FR" if code == "fr" else "EN")
            _active = (code == _cur)
            self._set_splash_lang_btn_style(btn, _active)
            btn.clicked.connect(lambda checked, c=code: self._on_splash_lang(c))
            lang_row.addWidget(btn)
            self._splash_lang_btns[code] = btn
        lay.addLayout(lang_row)

        ver = QLabel("v2.0 — alpha")
        ver.setAlignment(Qt.AlignmentFlag.AlignCenter)
        ver.setStyleSheet(
            f"color:{CP['text_dim']};font-size:9px;font-family:'Consolas',monospace;"
            f"background:transparent;border:none;"
        )
        lay.addWidget(ver)
        lay.addSpacing(16)

    @staticmethod
    def _set_splash_lang_btn_style(btn: QPushButton, active: bool):
        bg = "rgba(78,205,196,0.15)" if active else "transparent"
        border = f"1px solid {CP['accent']}" if active else "1px solid transparent"
        btn.setStyleSheet(
            f"QPushButton{{background:{bg};border:{border};"
            f"border-radius:6px;font-size:9px;font-weight:700;color:{CP['text_secondary']};}}"
            f"QPushButton:hover{{background:rgba(255,255,255,0.08);"
            f"border:1px solid {CP['border_bright']};}}"
        )

    def _on_splash_lang(self, code: str):
        if code == get_lang():
            return
        set_lang(code)
        for c, btn in self._splash_lang_btns.items():
            self._set_splash_lang_btn_style(btn, c == code)
        self.lang_changed.emit(code)


# ── Ligne projet (vue liste) ──────────────────────────────────────────────────

class _ProjectRow(QWidget):
    clicked = pyqtSignal(dict)

    def __init__(self, data: dict):
        super().__init__()
        self._data = data
        self.setFixedHeight(58)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._s_normal = (
            f"QWidget#row{{background:{CP['bg1']};border:1px solid {CP['border']};"
            f"border-radius:10px;}}"
        )
        self._s_hover = (
            f"QWidget#row{{background:{CP['bg2']};border:1px solid {CP['border_bright']};"
            f"border-radius:10px;}}"
        )
        self.setObjectName("row")
        self.setStyleSheet(self._s_normal)

        lay = QHBoxLayout(self)
        lay.setContentsMargins(14, 0, 16, 0)
        lay.setSpacing(14)

        # Icône
        ico = QLabel("🎬")
        ico.setFixedSize(34, 34)
        ico.setAlignment(Qt.AlignmentFlag.AlignCenter)
        ico.setStyleSheet(
            f"background:{CP['bg3']};border-radius:7px;font-size:16px;border:none;"
        )
        thumb_path = data.get("thumbnail", "")
        if thumb_path and os.path.isfile(thumb_path):
            pix = QPixmap(thumb_path).scaled(
                34, 34,
                Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                Qt.TransformationMode.SmoothTransformation,
            )
            ico.setPixmap(pix)
            ico.setText("")
        lay.addWidget(ico)

        # Nom
        name_lbl = QLabel(data.get("name", "Projet"))
        name_lbl.setStyleSheet(
            f"color:{CP['text_primary']};font-size:13px;font-weight:700;"
            f"background:transparent;border:none;"
        )
        lay.addWidget(name_lbl, 1)

        # Date — toujours visible à droite avec largeur fixe
        time_str = _relative_time(data.get("modified_at", ""))
        time_lbl = QLabel(f"Ouvert {time_str}" if time_str else "")
        time_lbl.setFixedWidth(130)
        time_lbl.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        time_lbl.setStyleSheet(
            f"color:{CP['text_dim']};font-size:10px;"
            f"font-family:'Consolas',monospace;background:transparent;border:none;"
        )
        lay.addWidget(time_lbl)

    def enterEvent(self, e):
        self.setStyleSheet(self._s_hover)

    def leaveEvent(self, e):
        self.setStyleSheet(self._s_normal)

    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self._data)


# ── Panneau droit (projets récents) ──────────────────────────────────────────

class _RightPanel(QWidget):
    project_selected = pyqtSignal(dict)

    def __init__(self):
        super().__init__()
        self.setStyleSheet(f"background:{CP['bg0']};")

        lay = QVBoxLayout(self)
        lay.setContentsMargins(32, 32, 32, 24)
        lay.setSpacing(0)

        hdr = QLabel("PROJETS RÉCENTS")
        hdr.setStyleSheet(
            f"color:{CP['text_secondary']};font-size:10px;font-weight:700;"
            f"letter-spacing:3px;font-family:'Consolas',monospace;"
            f"background:transparent;border:none;"
        )
        lay.addWidget(hdr)
        lay.addSpacing(20)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet("QScrollArea{background:transparent;border:none;}")

        self._container = QWidget()
        self._container.setStyleSheet("background:transparent;")
        self._vlay = QVBoxLayout(self._container)
        self._vlay.setContentsMargins(0, 0, 0, 0)
        self._vlay.setSpacing(8)
        self._vlay.setAlignment(Qt.AlignmentFlag.AlignTop)
        scroll.setWidget(self._container)
        lay.addWidget(scroll)

        self.refresh()

    def refresh(self):
        while self._vlay.count():
            item = self._vlay.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        projects = project_api.list_recent(20)
        pruned = project_api.get_last_pruned()
        if pruned:
            n = len(pruned)
            warn = QLabel(
                f"⚠  {n} projet{'s' if n > 1 else ''} récent{'s' if n > 1 else ''} "
                f"introuvable{'s' if n > 1 else ''} (dossier{'s' if n > 1 else ''} déplacé{'s' if n > 1 else ''} ou supprimé{'s' if n > 1 else ''})."
            )
            warn.setWordWrap(True)
            warn.setStyleSheet(
                f"color:{CP['text_secondary']};font-size:11px;"
                f"background:rgba(255,180,0,0.08);border:1px solid rgba(255,180,0,0.25);"
                f"border-radius:6px;padding:6px 10px;"
            )
            self._vlay.addWidget(warn)

        if not projects:
            empty = QLabel("Aucun projet récent.\nCrée ton premier projet →")
            empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
            empty.setStyleSheet(
                f"color:{CP['text_dim']};font-size:13px;"
                f"background:transparent;border:none;"
            )
            self._vlay.addWidget(empty)
            return

        for data in projects:
            row = _ProjectRow(data)
            row.clicked.connect(self.project_selected)
            self._vlay.addWidget(row)


# ── Fenêtre splash principale ─────────────────────────────────────────────────

class SplashWindow(QWidget):
    project_selected = pyqtSignal(dict)

    def __init__(self):
        super().__init__()
        self.setWindowTitle("PANDORA — by 22eme ARKANE")
        self.setFixedSize(1100, 700)
        self.setStyleSheet(PANDORA_STYLESHEET)

        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)

        self._left  = _LeftPanel()
        self._right = _RightPanel()

        sep = QFrame()
        sep.setFixedWidth(1)
        sep.setStyleSheet(f"background:{CP['border']};")

        self._left.new_project.connect(self._on_new)
        self._left.open_project.connect(self._on_open)
        self._left.lang_changed.connect(self._on_lang_changed)
        self._right.project_selected.connect(self._on_card)

        lay.addWidget(self._left)
        lay.addWidget(sep)
        lay.addWidget(self._right, 1)

    def _on_new(self):
        dlg = NewProjectDialog(self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            data = dlg.get_project()
            if data:
                self.project_selected.emit(data)

    def _on_open(self):
        folder = QFileDialog.getExistingDirectory(
            self, "Ouvrir un projet PANDORA", ""
        )
        if not folder:
            return
        data = project_api.load_project(folder)
        if data:
            project_api.add_to_recent(folder)
            self.project_selected.emit(data)
        else:
            QMessageBox.warning(
                self, "Projet invalide",
                f"Aucun fichier projet trouvé dans :\n{folder}\n\n"
                "Sélectionne le dossier d'un projet PANDORA existant."
            )

    def _on_lang_changed(self, _code: str):
        from core.i18n import retranslate_widget
        retranslate_widget(self)

    def _on_card(self, data: dict):
        project_api.add_to_recent(data["_path"])
        self.project_selected.emit(data)
