"""
Page Projets — refonte 2026-07-23 (maquette Matthieu) : grille de GRANDES
vignettes (l'image = premier mood généré du storyboard du projet, recalculée à
chaque affichage — si le 1er plan change, la vignette suit), titre + date de
dernière ouverture en surimpression, boutons « ＋ Nouveau projet » / « 📁 Ouvrir
un projet… » centrés en tête, champ de recherche, caption « PROJETS RÉCENTS ».
Partagée par PANDORA Cinéma et PANDORA | Live (les projets sont filtrés par
mode). Signal : switch_requested(dict).
"""
import json
import os
from datetime import datetime

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QLineEdit,
    QScrollArea, QGridLayout, QFileDialog, QMenu,
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QPixmap
from ui.styles import CP
from core.i18n import translate, get_lang
import core.project as project_api


# ── Vignette : premier mood généré du storyboard du projet ────────────────────

def _project_thumb(path: str) -> str:
    """Chemin de la PREMIÈRE image du storyboard du projet (image_path du 1er
    plan qui en a une, sinon premier aperçu actif), "" si aucune. Lecture
    DIRECTE des JSON du projet — sans toucher au contexte global."""
    if not path:
        return ""
    sb_dir = os.path.join(path, "data", "storyboard")
    try:
        with open(os.path.join(sb_dir, "index.json"), encoding="utf-8") as fh:
            data = json.load(fh)
        shots = data.get("shots", []) if isinstance(data, dict) else data
        for s in shots or []:
            ip = (s or {}).get("image_path", "")
            if ip and os.path.isfile(ip):
                return ip
            if ip:
                rel = os.path.join(path, ip)
                if os.path.isfile(rel):
                    return rel
    except Exception:
        pass
    # Repli : premier aperçu actif trouvé dans storyboard/apercus/*/apercus.json
    try:
        ap_root = os.path.join(sb_dir, "apercus")
        for sid in sorted(os.listdir(ap_root)):
            try:
                with open(os.path.join(ap_root, sid, "apercus.json"),
                          encoding="utf-8") as fh:
                    ap = json.load(fh)
                paths = ap.get("paths", [])
                if paths:
                    idx = min(int(ap.get("active_idx", 0)), len(paths) - 1)
                    cand = paths[idx]
                    if cand and os.path.isfile(cand):
                        return cand
            except Exception:
                continue
    except Exception:
        pass
    return ""


def _last_opened(iso: str) -> str:
    lbl = "Last opened:" if get_lang() == "en" else "Dernière ouverture :"
    try:
        return f"{lbl} {datetime.fromisoformat(iso).strftime('%d/%m/%Y')}"
    except Exception:
        return lbl + " —"


# ── Carte projet (grande vignette, texte en surimpression) ────────────────────

class _ProjectCard(QWidget):
    clicked = pyqtSignal(dict)
    rename_requested = pyqtSignal(dict)

    _W, _H = 420, 236

    def __init__(self, data: dict, is_current: bool = False):
        super().__init__()
        self._data = data
        self._is_current = is_current
        self.setFixedSize(self._W, self._H)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)

        # Visuel = premier mood du storyboard (recadré cover), sinon placeholder.
        # Deux pixmaps précalculés : normal + zoom 1.06 (survol néon, 2026-07-23).
        self._img = QLabel()
        self._img.setFixedSize(self._W, self._H)
        self._img.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._rest_border = f"1px solid {CP['accent'] if is_current else CP['border']}"
        self._img.setStyleSheet(
            f"background:{CP['bg2']};border:{self._rest_border};border-radius:12px;"
            f"color:{CP['text_dim']};font-size:40px;"
        )
        self._pix_normal = self._pix_zoom = None
        thumb = _project_thumb(data.get("_path", ""))
        if thumb:
            pix = QPixmap(thumb)
            if not pix.isNull():
                def _cover(scale: float) -> QPixmap:
                    w2, h2 = int(self._W * scale), int(self._H * scale)
                    p2 = pix.scaled(w2, h2,
                                    Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                                    Qt.TransformationMode.SmoothTransformation)
                    return p2.copy((p2.width() - self._W) // 2,
                                   (p2.height() - self._H) // 2, self._W, self._H)
                self._pix_normal = _cover(1.0)
                self._pix_zoom = _cover(1.06)
                self._img.setPixmap(self._pix_normal)
        if self._img.pixmap() is None or self._img.pixmap().isNull():
            self._img.setText("🎬")
        lay.addWidget(self._img)

        # Surimpression bas : titre + dernière ouverture (fond sombre translucide).
        overlay = QWidget(self._img)
        overlay.setGeometry(1, self._H - 64, self._W - 2, 63)
        overlay.setStyleSheet(
            "background:rgba(7,9,15,0.62);"
            "border-bottom-left-radius:12px;border-bottom-right-radius:12px;"
        )
        ov = QVBoxLayout(overlay)
        ov.setContentsMargins(16, 8, 16, 8)
        ov.setSpacing(2)
        name = QLabel(data.get("name", "Projet"))
        name.setStyleSheet(
            f"color:{CP['text_primary']};font-size:15px;font-weight:700;"
            "background:transparent;border:none;"
        )
        sub = QLabel(_last_opened(data.get("modified_at", "")))
        sub.setStyleSheet(
            f"color:{CP['text_secondary']};font-size:10px;"
            "background:transparent;border:none;"
        )
        ov.addWidget(name)
        ov.addWidget(sub)

    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self._data)
            e.accept()
            return
        super().mousePressEvent(e)

    def enterEvent(self, e):
        # Survol : léger ZOOM du visuel + encadré NÉON violet (demande 2026-07-23).
        if self._pix_zoom is not None:
            self._img.setPixmap(self._pix_zoom)
        self._img.setStyleSheet(
            f"background:{CP['bg2']};border:1.5px solid {CP['accent2']};"
            f"border-radius:12px;color:{CP['text_dim']};font-size:40px;"
        )

    def leaveEvent(self, e):
        if self._pix_normal is not None:
            self._img.setPixmap(self._pix_normal)
        self._img.setStyleSheet(
            f"background:{CP['bg2']};border:{self._rest_border};border-radius:12px;"
            f"color:{CP['text_dim']};font-size:40px;"
        )

    def contextMenuEvent(self, e):
        # Renommer — proposé sur le projet OUVERT uniquement (comportement historique).
        if not self._is_current:
            return
        menu = QMenu(self)
        menu.setStyleSheet(
            f"QMenu{{background:{CP['bg2']};border:1px solid {CP['border_bright']};"
            f"border-radius:8px;padding:6px;}}"
            f"QMenu::item{{color:{CP['text_primary']};padding:7px 18px;font-size:11px;}}"
            f"QMenu::item:selected{{background:{CP['accent_dim']};}}"
        )
        act = menu.addAction("✎  " + translate("Renommer le projet"))
        act.triggered.connect(lambda: self.rename_requested.emit(self._data))
        menu.exec(e.globalPos())


# ── Page ──────────────────────────────────────────────────────────────────────

class PageProjects(QWidget):
    """Page de gestion des projets — signal switch_requested(dict) émis quand on change de projet."""
    switch_requested = pyqtSignal(dict)

    def __init__(self, current_project: dict):
        super().__init__()
        self._current = current_project or {}
        self._mode = self._current.get("mode", "cinema") or "cinema"
        self.setStyleSheet(f"background:{CP['bg0']};")

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ── Bandeau PLEINE LARGEUR (maquette) : Nouveau (violet) + Ouvrir ─────
        # Sélecteur ciblé OBLIGATOIRE (leçon du dashboard : une règle sans
        # sélecteur se propage aux enfants stylés).
        head = QWidget()
        head.setObjectName("ProjectsHeader")
        head.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        head.setStyleSheet(
            f"QWidget#ProjectsHeader{{background:{CP['bg1']};"
            f"border-bottom:1px solid {CP['border']};}}")
        hl = QHBoxLayout(head)
        hl.setContentsMargins(32, 16, 32, 16)
        hl.setSpacing(12)
        hl.addStretch(1)

        btn_new = QPushButton("＋  " + translate("Nouveau projet"))
        btn_new.setFixedHeight(42)
        btn_new.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_new.setStyleSheet(
            f"QPushButton{{background:{CP['accent2']};color:#fff;border:none;"
            f"border-radius:8px;font-size:13px;font-weight:700;padding:0 24px;}}"
            f"QPushButton:hover{{background:#9d8fff;}}"
            f"QPushButton:pressed{{background:#6a5acd;}}"
        )
        btn_new.clicked.connect(self._on_new)
        hl.addWidget(btn_new)

        btn_open = QPushButton("📁  " + translate("Ouvrir un projet…"))
        btn_open.setFixedHeight(42)
        btn_open.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_open.setStyleSheet(
            f"QPushButton{{background:transparent;color:{CP['text_primary']};"
            f"border:1px solid {CP['border_bright']};border-radius:8px;"
            f"font-size:13px;font-weight:700;padding:0 22px;}}"
            f"QPushButton:hover{{background:{CP['bg2']};}}"
        )
        btn_open.clicked.connect(self._on_open)
        hl.addWidget(btn_open)
        hl.addStretch(1)
        root.addWidget(head)

        # ── Recherche centrée ────────────────────────────────────────────────
        search_row = QHBoxLayout()
        search_row.setContentsMargins(32, 10, 32, 4)
        search_row.addStretch(1)
        self._search = QLineEdit()
        self._search.setPlaceholderText(translate("Rechercher un projet"))
        self._search.setFixedSize(540, 40)
        self._search.setClearButtonEnabled(True)
        self._search.setStyleSheet(
            f"QLineEdit{{background:{CP['bg1']};border:1px solid {CP['border']};"
            f"border-radius:10px;color:{CP['text_primary']};font-size:12px;padding:0 16px;}}"
            f"QLineEdit:focus{{border-color:{CP['accent_dim']};}}"
        )
        self._search.textChanged.connect(self._on_search_changed)
        search_row.addWidget(self._search)
        search_row.addStretch(1)
        root.addLayout(search_row)

        self._page = 0

        # ── Grille à POSITIONS FIXES (retour Matthieu 2026-07-23) : 3 colonnes
        # ancrées — 2 projets occupent les 2 emplacements de GAUCHE, aux mêmes
        # places et tailles que la page précédente. Le bloc (largeur fixe) est
        # centré ; les flèches ▲/▼ collent à la grille.
        _nav_ss = (
            f"QPushButton{{background:{CP['bg2']};color:{CP['text_secondary']};"
            f"border:1px solid {CP['border']};border-radius:8px;"
            f"font-size:10px;padding:0;}}"
            f"QPushButton:hover{{color:{CP['text_primary']};"
            f"border-color:{CP['accent2']};}}")

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet("QScrollArea{background:transparent;border:none;}")

        _content = QWidget()
        _content.setStyleSheet("background:transparent;")
        _cv = QVBoxLayout(_content)
        _cv.setContentsMargins(0, 8, 0, 8)
        _cv.setSpacing(10)
        # Bloc CENTRÉ VERTICALEMENT dans l'espace disponible (retour 2026-07-23).
        _cv.addStretch(1)

        _GRID_W = 3 * _ProjectCard._W + 2 * 18
        # « PROJETS RÉCENTS » aligné sur le bord GAUCHE de la première vignette
        # (wrapper à la largeur de la grille, centré comme elle).
        self._recents_lbl = QLabel(translate("PROJETS RÉCENTS"))
        self._recents_lbl.setStyleSheet(
            f"color:{CP['text_dim']};font-size:10px;letter-spacing:2px;"
            f"font-family:'Consolas',monospace;font-weight:700;background:transparent;"
        )
        _cap_wrap = QWidget()
        _cap_wrap.setFixedWidth(_GRID_W)
        _cap_wrap.setStyleSheet("background:transparent;")
        _cap_lay = QHBoxLayout(_cap_wrap)
        _cap_lay.setContentsMargins(0, 0, 0, 0)
        _cap_lay.addWidget(self._recents_lbl)
        _cap_lay.addStretch(1)
        _cv.addWidget(_cap_wrap, 0, Qt.AlignmentFlag.AlignHCenter)

        self._btn_page_up = QPushButton("▲")
        self._btn_page_up.setFixedSize(72, 24)
        self._btn_page_up.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_page_up.setStyleSheet(_nav_ss)
        self._btn_page_up.clicked.connect(lambda: self._change_page(-1))
        _cv.addWidget(self._btn_page_up, 0, Qt.AlignmentFlag.AlignHCenter)

        self._grid_container = QWidget()
        self._grid_container.setStyleSheet("background:transparent;")
        self._grid_container.setFixedWidth(_GRID_W)
        self._grid = QGridLayout(self._grid_container)
        self._grid.setSpacing(18)
        self._grid.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        self._grid.setContentsMargins(0, 0, 0, 0)
        _cv.addWidget(self._grid_container, 0, Qt.AlignmentFlag.AlignHCenter)

        self._btn_page_down = QPushButton("▼")
        self._btn_page_down.setFixedSize(72, 24)
        self._btn_page_down.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_page_down.setStyleSheet(_nav_ss)
        self._btn_page_down.clicked.connect(lambda: self._change_page(+1))
        _cv.addWidget(self._btn_page_down, 0, Qt.AlignmentFlag.AlignHCenter)
        _cv.addStretch(1)   # symétrique du ressort haut → bloc au milieu

        scroll.setWidget(_content)
        root.addWidget(scroll, 1)

        self._rebuild_grid()

    # ── Données / grille ─────────────────────────────────────────────────────

    def refresh(self):
        """Recharge la grille (appelé à chaque affichage de la page) — la
        vignette suit donc automatiquement le premier plan du storyboard."""
        self._rebuild_grid()

    def _projects(self) -> list:
        current_path = self._current.get("_path", "")
        recents = list(project_api.list_recent())
        # Projet OUVERT en tête (liseré accent), puis les autres récents du MÊME mode.
        out = []
        if current_path:
            cur = next((p for p in recents if p.get("_path", "") == current_path),
                       self._current)
            out.append(cur)
        out += [p for p in recents if p.get("_path", "") != current_path]
        return [p for p in out if (p.get("mode", "cinema") or "cinema") == self._mode]

    _PER_PAGE = 6   # 3 colonnes × 2 lignes, centrées (demande Matthieu 2026-07-23)

    def _on_search_changed(self, _t: str):
        self._page = 0
        self._rebuild_grid()

    def _change_page(self, step: int):
        self._page = max(0, self._page + step)
        self._rebuild_grid()

    def _rebuild_grid(self):
        while self._grid.count():
            item = self._grid.takeAt(0)
            w = item.widget()
            if w is not None:
                # setParent(None) AVANT deleteLater : sans ça, la carte retirée
                # reste peinte jusqu'au prochain tour de boucle (carte fantôme
                # au changement de page — vécu 2026-07-23).
                w.setParent(None)
                w.deleteLater()

        projects = self._projects()
        q = (self._search.text() or "").strip().lower()
        if q:
            projects = [p for p in projects if q in p.get("name", "").lower()]

        # Pagination 6 par page — flèches ⌃/⌄ visibles selon la position.
        total = len(projects)
        max_page = max(0, (total - 1) // self._PER_PAGE)
        self._page = min(self._page, max_page)
        self._btn_page_up.setVisible(self._page > 0)
        self._btn_page_down.setVisible(self._page < max_page)
        page_items = projects[self._page * self._PER_PAGE:
                              (self._page + 1) * self._PER_PAGE]

        pruned = project_api.get_last_pruned()
        row0 = 0
        if pruned:
            n = len(pruned)
            warn = QLabel(
                f"⚠  {n} projet{'s' if n > 1 else ''} introuvable{'s' if n > 1 else ''} "
                f"retiré{'s' if n > 1 else ''} de la liste (dossier déplacé ou supprimé)."
            )
            warn.setWordWrap(True)
            warn.setStyleSheet(
                f"color:{CP['text_secondary']};font-size:11px;"
                f"background:rgba(255,180,0,0.08);border:1px solid rgba(255,180,0,0.25);"
                f"border-radius:6px;padding:6px 10px;"
            )
            self._grid.addWidget(warn, 0, 0, 1, 3)
            row0 = 1

        if not page_items:
            empty = QLabel(translate(
                "Aucun projet récent.\nCrée ton premier projet avec « ＋ Nouveau projet »."))
            empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
            empty.setStyleSheet(
                f"color:{CP['text_dim']};font-size:13px;background:transparent;padding:48px 0;")
            self._grid.addWidget(empty, row0, 0, 1, 3)
            return

        current_path = self._current.get("_path", "")
        for i, data in enumerate(page_items):
            card = _ProjectCard(
                data, is_current=bool(current_path)
                and data.get("_path", "") == current_path)
            card.clicked.connect(self._on_switch)
            card.rename_requested.connect(lambda _d: self._on_rename())
            self._grid.addWidget(card, row0 + i // 3, i % 3)

    # ── Actions ───────────────────────────────────────────────────────────────

    def _on_switch(self, data: dict):
        # Re-cliquer le projet déjà ouvert : rien à recharger.
        if data.get("_path", "") and data.get("_path", "") == self._current.get("_path", ""):
            return
        project_api.add_to_recent(data.get("_path", ""))
        self.switch_requested.emit(data)

    def _on_open(self):
        folder = QFileDialog.getExistingDirectory(
            self, translate("Ouvrir un projet PANDORA"), ""
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
                self, translate("Dossier invalide"),
                translate("Ce dossier ne contient pas de projet PANDORA valide.")
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
        self._rebuild_grid()
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
