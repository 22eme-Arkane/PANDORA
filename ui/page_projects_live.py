"""
Page Projets — affichée dans PandoraWindow quand l'utilisateur clique sur "Projets".
Permet de voir le projet actuel, d'en ouvrir un autre ou d'en créer un nouveau.
"""
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QScrollArea, QFrame, QFileDialog,
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QPixmap
from ui.styles import CP
from ui.icons import load_icon
from core.i18n import translate
import core.project as project_api
from datetime import datetime


def _rel_time(iso: str) -> str:
    from core.i18n import get_lang
    try:
        dt = datetime.fromisoformat(iso)
        diff = datetime.now() - dt
        d = diff.days
        en = get_lang() == "en"
        if d == 0:
            h = diff.seconds // 3600
            if en:
                return "Today" if h == 0 else f"{h}h ago"
            return "Aujourd'hui" if h == 0 else f"Il y a {h}h"
        if d == 1:
            return "Yesterday" if en else "Hier"
        if d < 7:
            return f"{d} days ago" if en else f"Il y a {d} jours"
        return dt.strftime("%d/%m/%Y")
    except Exception:
        return ""


class _ProjectCard(QWidget):
    clicked = pyqtSignal(dict)

    def __init__(self, data: dict, is_current: bool = False):
        super().__init__()
        self._data = data
        self.setFixedHeight(80)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        accent = CP["accent"] if is_current else CP["border"]
        self.setStyleSheet(
            f"QWidget{{background:{CP['bg2']};border:1px solid {accent};"
            f"border-radius:10px;}}"
        )

        lay = QHBoxLayout(self)
        lay.setContentsMargins(16, 0, 16, 0)
        lay.setSpacing(14)

        # Icône
        ico = QLabel("📁")
        ico.setFixedSize(40, 40)
        ico.setAlignment(Qt.AlignmentFlag.AlignCenter)
        ico.setStyleSheet(
            f"background:{CP['bg3']};border-radius:8px;font-size:20px;"
        )
        lay.addWidget(ico)

        # Texte
        col = QVBoxLayout()
        col.setSpacing(3)
        name = QLabel(data.get("name", "Projet"))
        style = f"color:{CP['accent']};font-weight:700;" if is_current else f"color:{CP['text_primary']};font-weight:700;"
        name.setStyleSheet(f"{style}font-size:13px;background:transparent;border:none;")

        sub_parts = []
        path = data.get("_path", "")
        if path:
            sub_parts.append(path)
        mod = data.get("modified_at", "")
        if mod:
            sub_parts.append(_rel_time(mod))
        sub = QLabel("  ·  ".join(sub_parts))
        sub.setStyleSheet(
            f"color:{CP['text_dim']};font-size:10px;font-family:'Consolas',monospace;"
            f"background:transparent;border:none;"
        )

        col.addWidget(name)
        col.addWidget(sub)
        lay.addLayout(col, 1)

        if is_current:
            badge = QLabel("ACTUEL")
            badge.setStyleSheet(
                f"color:{CP['accent']};font-size:9px;font-weight:700;letter-spacing:1px;"
                f"background:rgba(78,205,196,0.12);border:1px solid {CP['accent_dim']};"
                f"border-radius:4px;padding:3px 8px;"
            )
            lay.addWidget(badge)

    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self._data)

    def enterEvent(self, e):
        self.setStyleSheet(
            f"QWidget{{background:{CP['bg3']};border:1px solid {CP['accent_dim']};border-radius:10px;}}"
        )

    def leaveEvent(self, e):
        self.setStyleSheet(
            f"QWidget{{background:{CP['bg2']};border:1px solid {CP['border']};border-radius:10px;}}"
        )


class PageProjects(QWidget):
    """Page de gestion des projets — signal switch_requested(dict) émis quand on change de projet."""
    switch_requested = pyqtSignal(dict)

    def __init__(self, current_project: dict):
        super().__init__()
        self._current = current_project
        self.setStyleSheet(f"background:{CP['bg0']};")

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        root.addWidget(self._build_topbar())

        sep = QFrame()
        sep.setFixedHeight(1)
        sep.setStyleSheet(f"background:{CP['border']};")
        root.addWidget(sep)

        root.addWidget(self._build_content(), 1)

    # ── Topbar ────────────────────────────────────────────────────────────────

    def _build_topbar(self):
        bar = QWidget()
        bar.setFixedHeight(60)
        bar.setStyleSheet(f"background:{CP['bg1']};")
        lay = QHBoxLayout(bar)
        lay.setContentsMargins(32, 0, 32, 0)
        lay.setSpacing(10)

        _ico = QLabel()
        _ico.setFixedSize(28, 28)
        _ico.setAlignment(Qt.AlignmentFlag.AlignCenter)
        _ico.setStyleSheet("background:transparent;")
        _ico_pix = load_icon("projets.png", 28)
        if not _ico_pix.isNull():
            _ico.setPixmap(_ico_pix)
        lay.addWidget(_ico)

        title = QLabel("Projets")
        title.setStyleSheet(
            f"color:{CP['text_primary']};font-size:22px;font-weight:700;background:transparent;"
        )
        lay.addWidget(title)
        lay.addStretch()

        btn_open = QPushButton("Ouvrir un dossier…")
        btn_open.setFixedHeight(36)
        btn_open.setStyleSheet(
            f"QPushButton{{background:transparent;color:{CP['text_secondary']};"
            f"border:1px solid {CP['border']};border-radius:8px;font-size:12px;font-weight:700;padding:0 16px;}}"
            f"QPushButton:hover{{background:{CP['bg2']};color:{CP['text_primary']};}}"
        )
        btn_open.clicked.connect(self._on_open)
        lay.addWidget(btn_open)

        btn_new = QPushButton("✦  Nouveau projet")
        btn_new.setFixedHeight(36)
        btn_new.setStyleSheet(
            f"QPushButton{{background:{CP['accent']};color:#07080f;"
            f"border:none;border-radius:8px;font-size:12px;font-weight:700;padding:0 18px;}}"
            f"QPushButton:hover{{background:#6eded6;}}"
        )
        btn_new.clicked.connect(self._on_new)
        lay.addWidget(btn_new)
        return bar

    # ── Contenu ───────────────────────────────────────────────────────────────

    def _build_content(self):
        w = QWidget()
        w.setStyleSheet("background:transparent;")
        lay = QVBoxLayout(w)
        lay.setContentsMargins(40, 32, 40, 32)
        lay.setSpacing(24)

        # Projet actuel
        sec_lbl = QLabel("PROJET ACTUEL")
        sec_lbl.setStyleSheet(
            f"color:{CP['text_dim']};font-size:9px;letter-spacing:2px;"
            f"font-family:'Consolas',monospace;font-weight:600;background:transparent;"
        )
        lay.addWidget(sec_lbl)

        cur_card = _ProjectCard(self._current, is_current=True)
        lay.addWidget(cur_card)

        btn_rename = QPushButton("✎  Renommer ce projet…")
        btn_rename.setFixedHeight(30)
        btn_rename.setStyleSheet(
            f"QPushButton{{background:transparent;color:{CP['text_secondary']};"
            f"border:1px solid {CP['border']};border-radius:7px;"
            f"font-size:11px;font-weight:600;padding:0 14px;}}"
            f"QPushButton:hover{{background:{CP['bg2']};color:{CP['text_primary']};"
            f"border-color:{CP['border_bright']};}}"
        )
        btn_rename.clicked.connect(self._on_rename)
        rename_row = QHBoxLayout()
        rename_row.addWidget(btn_rename)
        rename_row.addStretch()
        lay.addLayout(rename_row)

        # Séparateur
        sep = QFrame()
        sep.setFixedHeight(1)
        sep.setStyleSheet(f"background:{CP['border']};")
        lay.addWidget(sep)

        # Récents
        recents_lbl = QLabel("PROJETS RÉCENTS")
        recents_lbl.setStyleSheet(
            f"color:{CP['text_dim']};font-size:9px;letter-spacing:2px;"
            f"font-family:'Consolas',monospace;font-weight:600;background:transparent;"
        )
        lay.addWidget(recents_lbl)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea{background:transparent;border:none;}")

        container = QWidget()
        container.setStyleSheet("background:transparent;")
        clayout = QVBoxLayout(container)
        clayout.setContentsMargins(0, 0, 0, 0)
        clayout.setSpacing(10)

        current_path = self._current.get("_path", "")
        recents = project_api.list_recent()
        pruned = project_api.get_last_pruned()
        others = [p for p in recents if p.get("_path", "") != current_path]

        if pruned:
            n = len(pruned)
            warn = QLabel(
                f"⚠  {n} projet{'s' if n > 1 else ''} introuvable{'s' if n > 1 else ''} "
                f"retiré{'s' if n > 1 else ''} de la liste (dossier{'s' if n > 1 else ''} déplacé{'s' if n > 1 else ''} ou supprimé{'s' if n > 1 else ''})."
            )
            warn.setWordWrap(True)
            warn.setStyleSheet(
                f"color:{CP['text_secondary']};font-size:11px;"
                f"background:rgba(255,180,0,0.08);border:1px solid rgba(255,180,0,0.25);"
                f"border-radius:6px;padding:6px 10px;"
            )
            clayout.addWidget(warn)

        if not others:
            empty = QLabel("Aucun autre projet récent.")
            empty.setStyleSheet(
                f"color:{CP['text_dim']};font-size:12px;background:transparent;padding:12px 0;"
            )
            clayout.addWidget(empty)
        else:
            for data in others:
                card = _ProjectCard(data)
                card.clicked.connect(self._on_switch)
                clayout.addWidget(card)

        clayout.addStretch()
        scroll.setWidget(container)
        lay.addWidget(scroll, 1)

        return w

    # ── Actions ───────────────────────────────────────────────────────────────

    def _on_switch(self, data: dict):
        project_api.add_to_recent(data.get("_path", ""))
        self.switch_requested.emit(data)

    def _on_open(self):
        folder = QFileDialog.getExistingDirectory(
            self, "Ouvrir un projet PANDORA", ""
        )
        if not folder:
            return
        data = project_api.load_project(folder)
        if data:
            project_api.add_to_recent(folder)
            self.switch_requested.emit(data)
        else:
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.warning(
                self, "Dossier invalide",
                "Ce dossier ne contient pas de projet PANDORA valide."
            )

    def _on_rename(self):
        from PyQt6.QtWidgets import QInputDialog
        current_name = self._current.get("name", "")
        new_name, ok = QInputDialog.getText(
            self, translate("Renommer le projet"), translate("Nouveau nom :"), text=current_name
        )
        if not ok or not new_name.strip() or new_name.strip() == current_name:
            return
        project_api.rename_project(self._current, new_name.strip())
        w = self.window()
        if hasattr(w, "_refresh_project_page"):
            w._refresh_project_page()

    def _on_new(self):
        from ui.splash import NewProjectDialog
        dlg = NewProjectDialog(self)
        if dlg.exec() == NewProjectDialog.DialogCode.Accepted:
            data = dlg.get_project()
            if data:
                self.switch_requested.emit(data)
