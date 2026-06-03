from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QVBoxLayout,
    QLabel, QStackedWidget, QFrame, QPushButton,
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QShortcut, QKeySequence
from ui.styles import CP, PANDORA_STYLESHEET
from ui.seedance_widget import SeedanceWidget
from ui.page_stub import PageStub
from ui.page_settings import SettingsPage
from ui.page_castings import PageCastings
from ui.page_accessories import PageAccessories
from ui.page_hmc import PageHMC
from ui.page_vehicles import PageVehicles
from ui.page_projects import PageProjects
from ui.page_camera import PageCamera
from ui.page_decors import PageDecors
from ui.page_scenario import PageScenario
from ui.page_storyboard import PageStoryboard
from ui.page_doublage import PageDoublage
from ui.icons import load_icon, badge_pixmap, app_icon, dim, tint
from ui.assistant_panel import AssistantPanel, AssistantToggleStrip
from core.i18n import tr, get_lang, set_lang, retranslate_widget, translate


def _get_nav_items():
    return [
        ("projets.png",    tr("nav.projects"),    "projects"),
        None,
        ("scenario.png",   tr("nav.scenario"),    "scenario"),
        ("storyboard.png", tr("nav.storyboard"),  "storyboard"),
        None,
        ("castings.png",   tr("nav.castings"),    "castings"),
        ("decors.png",     tr("nav.decors"),      "decors"),
        ("accesoires.png", tr("nav.accessories"), "accessoires"),
        ("HMC.png",        tr("nav.hmc"),         "hmc"),
        ("vehicule.png",   tr("nav.vehicles"),    "vehicles"),
        None,
        ("camera.png",     tr("nav.camera"),      "camera"),
        ("doublage.png",   tr("nav.doublage"),    "doublage"),
        None,
        ("seedance.png",   tr("nav.seedance"),    "seedance"),
        ("settings.png",   tr("nav.settings"),    "settings"),
    ]

# Fallback texte si le PNG est absent
_FALLBACK = {
    "projets.png":     "▤",
    "univers.png":     "◈",
    "scenario.png":    "≡",
    "storyboard.png":  "⊞",
    "castings.png":    "⊕",
    "decors.png":      "◻",
    "accesoires.png":  "◈",
    "vehicule.png":    "🚗",
    "HMC.png":         "✂",
    "camera.png":      "◎",
    "doublage.png":    "🎙",
    "seedance.png":    "✦",
    "settings.png":    "⚙",
}

# Toutes les icônes sont affichées telles quelles (sans re-teintage QPainter)
_COLOR_ICONS: frozenset[str] = frozenset({
    "projets.png", "scenario.png", "storyboard.png", "castings.png",
    "decors.png", "accesoires.png", "HMC.png", "vehicule.png",
    "camera.png", "doublage.png", "seedance.png", "settings.png",
})


class NavItem(QWidget):
    nav_clicked = pyqtSignal(str)

    def __init__(self, icon_file: str, label: str, key: str):
        super().__init__()
        self._key      = key
        self._active   = False
        self._ico_file = icon_file
        self.setFixedHeight(54)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        _pix_raw  = load_icon(icon_file, 30)
        _is_color = icon_file in _COLOR_ICONS
        if not _pix_raw.isNull():
            if _is_color:
                # Fond coloré propre — on préserve les couleurs d'origine
                self._pix_white  = _pix_raw
                self._pix_accent = _pix_raw
            else:
                # Silhouette sur transparent — on normalise en blanc
                self._pix_white  = tint(_pix_raw, "#ffffff")
                self._pix_accent = tint(_pix_raw, CP['accent'])
        else:
            self._pix_white  = _pix_raw
            self._pix_accent = _pix_raw
        self._pix_on  = self._pix_white
        self._pix_off = dim(self._pix_white, 0.55)
        self._use_png = not _pix_raw.isNull()

        outer = QHBoxLayout(self)
        outer.setContentsMargins(10, 3, 8, 3)
        outer.setSpacing(10)
        outer.setAlignment(Qt.AlignmentFlag.AlignVCenter)

        # ── Icône — entité indépendante, jamais de bordure ────────────────────
        self._ico = QLabel()
        self._ico.setFixedSize(30, 30)
        self._ico.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._ico.setStyleSheet("background:transparent;border:none;")

        # ── Frame label — seul élément qui reçoit la bordure hover/actif ──────
        self._frame = QFrame()
        self._frame.setFixedHeight(36)
        fl = QHBoxLayout(self._frame)
        fl.setContentsMargins(10, 0, 10, 0)
        fl.setSpacing(0)

        self._lbl = QLabel(label)
        fl.addWidget(self._lbl)
        fl.addStretch()

        outer.addWidget(self._ico)
        outer.addWidget(self._frame, 1)

        self._apply(False)

    def _apply(self, active: bool):
        if active:
            self._frame.setStyleSheet(
                f"QFrame{{background:rgba(78,205,196,0.18);"
                f"border:1px solid rgba(78,205,196,0.32);border-radius:8px;}}"
            )
            if self._use_png:
                self._ico.setPixmap(self._pix_accent)  # teal sur fond actif
                self._ico.setStyleSheet("background:transparent;border:none;")
            else:
                self._ico.setText(_FALLBACK.get(self._ico_file, "●"))
                self._ico.setStyleSheet(
                    f"color:{CP['accent']};font-size:15px;background:transparent;border:none;"
                )
            self._lbl.setStyleSheet(
                f"color:{CP['accent']};font-size:16px;font-weight:700;"
                f"letter-spacing:0.4px;background:transparent;border:none;"
            )
        else:
            self._frame.setStyleSheet(
                "QFrame{background:transparent;border:none;border-radius:8px;}"
            )
            if self._use_png:
                self._ico.setPixmap(self._pix_off)  # blanc dim
                self._ico.setStyleSheet("background:transparent;border:none;")
            else:
                self._ico.setText(_FALLBACK.get(self._ico_file, "●"))
                self._ico.setStyleSheet(
                    f"color:{CP['text_dim']};font-size:15px;background:transparent;border:none;"
                )
            self._lbl.setStyleSheet(
                f"color:{CP['text_secondary']};font-size:16px;font-weight:600;"
                f"letter-spacing:0.3px;background:transparent;border:none;"
            )

    def setActive(self, active: bool):
        self._active = active
        self._apply(active)

    def enterEvent(self, e):
        if not self._active:
            self._frame.setStyleSheet(
                "QFrame{background:rgba(255,255,255,0.05);"
                "border:1px solid rgba(255,255,255,0.08);border-radius:8px;}"
            )
            if self._use_png:
                self._ico.setPixmap(self._pix_on)
            self._lbl.setStyleSheet(
                f"color:{CP['text_primary']};font-size:16px;font-weight:600;"
                f"background:transparent;border:none;"
            )

    def leaveEvent(self, e):
        if not self._active:
            self._apply(False)

    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            self.nav_clicked.emit(self._key)


class _Sidebar(QWidget):
    nav_clicked           = pyqtSignal(str)
    manual_requested      = pyqtSignal()
    contact_requested     = pyqtSignal()
    lang_change_requested = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self.setFixedWidth(268)
        self.setStyleSheet(
            f"background:{CP['sidebar']};border-right:1px solid {CP['border']};"
        )

        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(2)

        # ── Sélecteur de langue (remplace l'ancien logo) ───────────────────────
        logo_strip = QWidget()
        logo_strip.setFixedHeight(76)
        logo_strip.setStyleSheet(
            f"background:{CP['bg1']};"
            f"border:none;border-bottom:1px solid {CP['border']};"
        )
        ll = QHBoxLayout(logo_strip)
        ll.setContentsMargins(14, 0, 14, 0)
        ll.setSpacing(8)

        self._lang_btns: dict[str, QPushButton] = {}
        _flag_map = {"fr": "Fr.png", "en": "En.png"}
        _cur_lang = get_lang()
        for code, flag_file in _flag_map.items():
            btn = QPushButton()
            btn.setFixedSize(34, 34)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setToolTip("Français" if code == "fr" else "English")
            _flag_pix = load_icon(flag_file, 24)
            if not _flag_pix.isNull():
                from PyQt6.QtGui import QIcon as _QIcon
                from PyQt6.QtCore import QSize as _QSize
                btn.setIcon(_QIcon(_flag_pix))
                btn.setIconSize(_QSize(24, 24))
                btn.setText("")
            else:
                btn.setText("FR" if code == "fr" else "EN")
            self._apply_lang_btn_style(btn, code == _cur_lang)
            btn.clicked.connect(lambda checked, c=code: self.lang_change_requested.emit(c))
            ll.addWidget(btn)
            self._lang_btns[code] = btn

        ll.addStretch()
        lay.addWidget(logo_strip)

        lay.addSpacing(6)

        # ── Nav items ─────────────────────────────────────────────────────────
        self._items: dict[str, NavItem] = {}
        for entry in _get_nav_items():
            if entry is None:
                # Séparateur inter-groupe
                lay.addSpacing(2)
                _gsep = QFrame()
                _gsep.setFixedHeight(1)
                _gsep.setStyleSheet(
                    f"background:rgba(255,255,255,0.07);margin:0 20px;"
                )
                lay.addWidget(_gsep)
                lay.addSpacing(2)
                continue

            icon_file, label, key = entry
            if key == "settings":
                lay.addStretch()
                sep = QFrame()
                sep.setFixedHeight(1)
                sep.setStyleSheet(f"background:{CP['border']};margin:0 12px;")
                lay.addWidget(sep)
                lay.addSpacing(4)

            item = NavItem(icon_file, label, key)
            item.nav_clicked.connect(self.nav_clicked)
            self._items[key] = item
            lay.addWidget(item)

        lay.addSpacing(4)

        # ── Boutons fixes en bas de la sidebar ────────────────────────────────
        _sep_bottom = QFrame()
        _sep_bottom.setFixedHeight(1)
        _sep_bottom.setStyleSheet(f"background:{CP['border']};margin:0 12px;")
        lay.addWidget(_sep_bottom)

        _ss_yellow = (
            "QPushButton{"
            "background:transparent;color:#c8a400;"
            "border:1px solid rgba(200,164,0,0.35);"
            "border-radius:6px;font-size:10px;font-weight:700;"
            "text-align:left;padding:0 14px;}"
            "QPushButton:hover{"
            "background:rgba(245,197,24,0.10);color:#f5c518;"
            "border-color:rgba(245,197,24,0.60);}"
            "QPushButton:pressed{background:rgba(245,197,24,0.18);}"
        )

        btn_manual = QPushButton("☰  Manuel d'utilisation")
        btn_manual.setFixedHeight(34)
        btn_manual.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_manual.setStyleSheet(_ss_yellow)
        btn_manual.clicked.connect(self.manual_requested.emit)
        lay.addWidget(btn_manual)

        lay.addSpacing(6)

        btn_contact = QPushButton("✉  Nous contacter")
        btn_contact.setFixedHeight(34)
        btn_contact.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_contact.setStyleSheet(_ss_yellow)
        btn_contact.clicked.connect(self.contact_requested.emit)
        lay.addWidget(btn_contact)

        lay.addSpacing(6)

    @staticmethod
    def _apply_lang_btn_style(btn: QPushButton, active: bool):
        bg = "rgba(78,205,196,0.15)" if active else "transparent"
        border = f"1px solid {CP['accent']}" if active else "1px solid transparent"
        btn.setStyleSheet(
            f"QPushButton{{background:{bg};border:{border};"
            f"border-radius:6px;font-size:9px;font-weight:700;color:{CP['text_secondary']};}}"
            f"QPushButton:hover{{background:rgba(255,255,255,0.08);"
            f"border:1px solid {CP['border_bright']};}}"
        )

    def set_lang_active(self, code: str):
        for c, btn in self._lang_btns.items():
            self._apply_lang_btn_style(btn, c == code)

    def set_active(self, key: str):
        for k, item in self._items.items():
            item.setActive(k == key)


class PandoraWindow(QMainWindow):
    switch_requested = pyqtSignal(dict)   # émis quand l'utilisateur change de projet

    def __init__(self, project: dict):
        super().__init__()
        self._project = project

        # Set project context before any page loads data
        import core.context as _ctx
        from core.migration import migrate_legacy_data
        pid = project.get("id", "")
        _ctx.set_project_id(pid)
        _ctx.set_project_path(project.get("_path", ""))
        migrate_legacy_data(pid)  # no-op after first run; always uses oldest project

        self.setWindowTitle(f"PANDORA — {project.get('name', 'Projet')}")
        self.setMinimumSize(1100, 720)
        self.setStyleSheet(PANDORA_STYLESHEET)

        from ui.icons import app_icon
        icon = app_icon()
        if not icon.isNull():
            self.setWindowIcon(icon)

        central = QWidget()
        self.setCentralWidget(central)

        outer = QVBoxLayout(central)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        outer.addWidget(self._build_global_topbar())

        self._update_banner = self._build_update_banner()
        outer.addWidget(self._update_banner)

        body = QWidget()
        body.setStyleSheet("background:transparent;")
        body_lay = QHBoxLayout(body)
        body_lay.setContentsMargins(0, 0, 0, 0)
        body_lay.setSpacing(0)

        self._sidebar = _Sidebar()
        self._stack   = QStackedWidget()
        self._stack.setStyleSheet(f"background:{CP['bg0']};")

        self._assistant         = AssistantPanel()
        self._assistant.setVisible(True)
        self._assistant_toggle  = AssistantToggleStrip(self._assistant)

        body_lay.addWidget(self._sidebar)
        body_lay.addWidget(self._stack, 1)
        body_lay.addWidget(self._assistant)
        body_lay.addWidget(self._assistant_toggle)
        outer.addWidget(body, 1)

        self._pages: dict[str, QWidget] = {}
        self._build_pages()

        self._sidebar.nav_clicked.connect(self._navigate)
        self._sidebar.manual_requested.connect(self._on_manual)
        self._sidebar.contact_requested.connect(self._on_contact)
        self._sidebar.lang_change_requested.connect(self._on_lang_change)
        self._navigate("scenario")

        from PyQt6.QtCore import QTimer
        QTimer.singleShot(900, self._maybe_show_onboarding)

        _sc = QShortcut(QKeySequence("Ctrl+S"), self)
        _sc.activated.connect(self._on_global_save_click)

    def _build_pages(self):
        scenario = PageScenario()
        scenario.navigate_requested.connect(
            lambda key, extra: self._navigate(key, extra)
        )
        scenario.style_changed.connect(self._on_scenario_style_changed)
        self._pages["scenario"] = scenario
        self._stack.addWidget(scenario)

        storyboard = PageStoryboard()
        self._pages["storyboard"] = storyboard
        self._stack.addWidget(storyboard)

        decors = PageDecors()
        self._pages["decors"] = decors
        self._stack.addWidget(decors)

        camera = PageCamera()
        self._pages["camera"] = camera
        self._stack.addWidget(camera)

        projects = PageProjects(self._project)
        projects.switch_requested.connect(self.switch_requested)
        self._pages["projects"] = projects
        self._stack.addWidget(projects)

        castings = PageCastings()
        self._pages["castings"] = castings
        self._stack.addWidget(castings)

        accessories = PageAccessories()
        self._pages["accessoires"] = accessories
        self._stack.addWidget(accessories)

        hmc = PageHMC()
        self._pages["hmc"] = hmc
        self._stack.addWidget(hmc)

        vehicles = PageVehicles()
        self._pages["vehicles"] = vehicles
        self._stack.addWidget(vehicles)

        doublage = PageDoublage()
        self._pages["doublage"] = doublage
        self._stack.addWidget(doublage)

        settings = SettingsPage()
        self._pages["settings"] = settings
        self._stack.addWidget(settings)

        seedance = SeedanceWidget()
        self._pages["seedance"] = seedance
        self._stack.addWidget(seedance)

    def showEvent(self, event):
        super().showEvent(event)
        from PyQt6.QtCore import QTimer
        QTimer.singleShot(0, self._refresh_taskbar_icon)

    def _refresh_taskbar_icon(self):
        """Re-applique l'icône via Win32 SendMessage(WM_SETICON) après création du HWND.
        Qt ne propage pas toujours l'icône vers la barre des tâches Windows au premier show."""
        try:
            import sys
            import ctypes
            import os
            if sys.platform != "win32":
                return
            hwnd = int(self.winId())
            if not hwnd:
                return
            if getattr(sys, "frozen", False):
                ico_path = os.path.join(sys._MEIPASS, "assets", "pandora_badge.ico")
            else:
                ico_path = os.path.join(
                    os.path.dirname(os.path.dirname(__file__)), "assets", "pandora_badge.ico"
                )
            if not os.path.isfile(ico_path):
                return
            IMAGE_ICON    = 1
            LR_LOADFROMFILE = 0x00000010
            WM_SETICON    = 0x0080
            hicon_big   = ctypes.windll.user32.LoadImageW(
                None, ico_path, IMAGE_ICON, 48, 48, LR_LOADFROMFILE)
            hicon_small = ctypes.windll.user32.LoadImageW(
                None, ico_path, IMAGE_ICON, 16, 16, LR_LOADFROMFILE)
            if hicon_big:
                ctypes.windll.user32.SendMessageW(hwnd, WM_SETICON, 1, hicon_big)
            if hicon_small:
                ctypes.windll.user32.SendMessageW(hwnd, WM_SETICON, 0, hicon_small)
        except Exception:
            pass

    def _build_global_topbar(self) -> QWidget:
        from PyQt6.QtWidgets import QStackedLayout

        bar = QWidget()
        bar.setFixedHeight(70)
        bar.setObjectName("GlobalTopBar")
        bar.setStyleSheet(
            f"QWidget#GlobalTopBar{{background:{CP['bg1']};"
            f"border-bottom:1px solid {CP['border']};}}"
        )

        bar_lay = QStackedLayout(bar)
        bar_lay.setContentsMargins(0, 0, 0, 0)
        bar_lay.setSpacing(0)
        bar_lay.setStackingMode(QStackedLayout.StackingMode.StackAll)

        # ── Couche 0 : gauche vide + droite boutons ───────────────────────────
        _lr = QWidget()
        _lr.setStyleSheet("background:transparent;")
        _lr_lay = QHBoxLayout(_lr)
        _lr_lay.setContentsMargins(12, 0, 12, 0)
        _lr_lay.setSpacing(0)

        _left = QWidget()
        _left.setStyleSheet("background:transparent;")
        _lr_lay.addWidget(_left, 1)   # stretch — remplit tout l'espace à gauche

        _right = QWidget()
        _right.setStyleSheet("background:transparent;")
        _rlay = QHBoxLayout(_right)
        _rlay.setContentsMargins(0, 0, 0, 0)
        _rlay.setSpacing(0)
        _rlay.setAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight)

        # ── Couche 1 : logo PANDORA — centré géométriquement dans toute la barre
        _center = QWidget()
        _center.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        _center.setStyleSheet("background:transparent;")
        _clay = QHBoxLayout(_center)
        _clay.setContentsMargins(0, 0, 0, 0)
        _clay.setSpacing(0)
        _clay.setAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignHCenter)

        badge_lbl = QLabel()
        badge_lbl.setFixedSize(44, 44)
        badge_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        badge_lbl.setStyleSheet("background:transparent;border:none;")
        pix_badge = app_icon().pixmap(44, 44)
        if not pix_badge.isNull():
            badge_lbl.setPixmap(pix_badge)
        else:
            badge_lbl.setText("P")
            badge_lbl.setStyleSheet(
                f"background:qlineargradient(x1:0,y1:0,x2:1,y2:1,"
                f"stop:0 {CP['accent']},stop:1 {CP['accent2']});"
                f"border-radius:10px;color:#07080f;font-size:20px;font-weight:900;"
            )
        _clay.addWidget(badge_lbl)
        _clay.addSpacing(10)

        title_lbl = QLabel("PANDORA")
        title_lbl.setStyleSheet(
            f"color:{CP['text_primary']};font-size:15px;font-weight:800;"
            f"letter-spacing:3px;background:transparent;border:none;"
        )
        _clay.addWidget(title_lbl)

        def _vsep():
            f = QFrame()
            f.setFixedSize(1, 20)
            f.setStyleSheet(f"background:{CP['border']};")
            return f

        # ── Soutenir Pandora ──────────────────────────────────────────────────
        btn_support = QPushButton(tr("btn.support") + "  Pandora")
        btn_support.setFixedHeight(26)
        btn_support.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_support.setStyleSheet(
            "QPushButton{"
            "background:transparent;color:#c8a400;"
            "border:1px solid rgba(200,164,0,0.35);"
            "border-radius:5px;font-size:10px;font-weight:700;padding:0 10px;"
            "}"
            "QPushButton:hover{"
            "background:rgba(245,197,24,0.10);color:#f5c518;"
            "border-color:rgba(245,197,24,0.60);"
            "}"
            "QPushButton:pressed{background:rgba(245,197,24,0.18);}"
        )
        btn_support.clicked.connect(self._on_funding)
        _rlay.addWidget(btn_support)

        _rlay.addSpacing(6)
        _rlay.addWidget(_vsep())
        _rlay.addSpacing(6)

        # ── Vérifier les mises à jour ─────────────────────────────────────────
        self._btn_update_header = QPushButton("↑  Mises à jour")
        self._btn_update_header.setFixedHeight(26)
        self._btn_update_header.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_update_header.setToolTip("Vérifier les mises à jour de PANDORA")
        self._btn_update_header.setStyleSheet(
            f"QPushButton{{background:transparent;color:{CP['accent']};"
            f"border:1px solid rgba(78,205,196,0.38);border-radius:5px;"
            f"font-size:10px;font-weight:700;padding:0 10px;}}"
            f"QPushButton:hover{{background:rgba(78,205,196,0.09);"
            f"border-color:rgba(78,205,196,0.70);}}"
            f"QPushButton:pressed{{background:rgba(78,205,196,0.16);}}"
            f"QPushButton:disabled{{color:{CP['text_dim']};"
            f"border-color:{CP['border']};}}"
        )
        self._btn_update_header.clicked.connect(self._manual_update_check)
        _rlay.addWidget(self._btn_update_header)

        _rlay.addSpacing(6)
        _rlay.addWidget(_vsep())
        _rlay.addSpacing(6)

        # ── Sauvegarder ───────────────────────────────────────────────────────
        self._btn_save_global = QPushButton(tr("btn.save"))
        self._btn_save_global.setFixedHeight(26)
        self._btn_save_global.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_save_global.setStyleSheet(
            f"QPushButton{{background:transparent;color:{CP['text_dim']};"
            f"border:1px solid {CP['border']};border-radius:5px;"
            f"font-size:10px;font-weight:700;padding:0 12px;}}"
            f"QPushButton:hover{{background:{CP['bg3']};color:{CP['text_primary']};"
            f"border-color:{CP['border_bright']};}}"
            f"QPushButton:pressed{{background:{CP['bg4']};}}"
        )
        self._btn_save_global.clicked.connect(self._on_global_save_click)
        _rlay.addWidget(self._btn_save_global)

        _lr_lay.addWidget(_right)

        bar_lay.addWidget(_lr)       # couche 0 — gauche/droite
        bar_lay.addWidget(_center)   # couche 1 — logo centré, passe-transparent
        bar_lay.setCurrentIndex(1)   # couche 1 au-dessus (z-order)
        return bar

    def _on_global_save_click(self):
        self._on_global_save()
        self._btn_save_global.setText(tr("btn.saved"))
        self._btn_save_global.setStyleSheet(
            f"QPushButton{{background:transparent;color:{CP['accent']};"
            f"border:1px solid {CP['accent_dim']};border-radius:5px;"
            f"font-size:10px;font-weight:700;padding:0 12px;}}"
        )
        from PyQt6.QtCore import QTimer
        QTimer.singleShot(1400, self._reset_save_btn_global)

    def _reset_save_btn_global(self):
        self._btn_save_global.setText(tr("btn.save"))
        self._btn_save_global.setStyleSheet(
            f"QPushButton{{background:transparent;color:{CP['text_dim']};"
            f"border:1px solid {CP['border']};border-radius:5px;"
            f"font-size:10px;font-weight:700;padding:0 12px;}}"
            f"QPushButton:hover{{background:{CP['bg3']};color:{CP['text_primary']};"
            f"border-color:{CP['border_bright']};}}"
            f"QPushButton:pressed{{background:{CP['bg4']};}}"
        )

    def _navigate(self, key: str, extra: str = ""):
        page = self._pages.get(key)
        if page:
            self._stack.setCurrentWidget(page)
            if extra and hasattr(page, "open_version"):
                page.open_version(extra)
            elif hasattr(page, "refresh"):
                page.refresh()
            if get_lang() != "fr":
                retranslate_widget(page)
        self._sidebar.set_active(key)
        self._assistant.set_context(key)

    def _refresh_project_page(self):
        """Reconstruit la page Projets après un renommage du projet courant."""
        old = self._pages.get("projects")
        if old:
            self._stack.removeWidget(old)
            old.deleteLater()
        from ui.page_projects import PageProjects
        projects = PageProjects(self._project)
        projects.switch_requested.connect(self.switch_requested)
        self._pages["projects"] = projects
        self._stack.addWidget(projects)
        self._stack.setCurrentWidget(projects)
        # Update sidebar title if it displays the project name
        if hasattr(self._sidebar, "set_project_name"):
            self._sidebar.set_project_name(self._project.get("name", ""))

    def _on_scenario_style_changed(self, key: str):
        """Propagate scenario style change to all relevant pages."""
        seedance = self._pages.get("seedance")
        if seedance and hasattr(seedance, "refresh"):
            seedance.refresh()   # syncs T2V film_style_combo via _refresh_style_badge

    def closeEvent(self, e):
        from PyQt6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton
        dlg = QDialog(self)
        dlg.setWindowTitle("Quitter PANDORA")
        dlg.setFixedSize(560, 310)
        dlg.setStyleSheet(PANDORA_STYLESHEET + f"QDialog{{background:{CP['bg1']};}}")

        lay = QVBoxLayout(dlg)
        lay.setContentsMargins(28, 24, 28, 22)
        lay.setSpacing(14)

        lbl = QLabel("Voulez-vous vraiment quitter le programme ?")
        lbl.setWordWrap(True)
        lbl.setStyleSheet(
            f"color:{CP['text_primary']};font-size:14px;font-weight:600;background:transparent;"
        )
        lay.addWidget(lbl)

        sub = QLabel("Les données du storyboard et des fiches sont sauvegardées automatiquement.")
        sub.setWordWrap(True)
        sub.setStyleSheet(
            f"color:{CP['text_dim']};font-size:10px;background:transparent;"
        )
        lay.addWidget(sub)

        # ── Séparateur ────────────────────────────────────────────────────────
        _sep = QFrame()
        _sep.setFixedHeight(1)
        _sep.setStyleSheet("background:rgba(200,164,0,0.22);margin:0 0;")
        lay.addWidget(_sep)

        # ── Callout soutien PANDORA ───────────────────────────────────────────
        _don_frame = QWidget()
        _don_frame.setStyleSheet(
            "background:rgba(200,164,0,0.06);border-radius:8px;"
        )
        _don_lay = QVBoxLayout(_don_frame)
        _don_lay.setContentsMargins(14, 12, 14, 12)
        _don_lay.setSpacing(8)

        _don_lbl = QLabel(
            "❤  PANDORA est gratuit. Il fonctionne grâce au soutien de la communauté."
        )
        _don_lbl.setWordWrap(True)
        _don_lbl.setStyleSheet("color:#c8a400;font-size:11px;font-weight:600;background:transparent;")
        _don_lay.addWidget(_don_lbl)

        _don_sub = QLabel(
            "Si ce logiciel vous est utile, un don — même modeste — nous aide à continuer à le développer."
        )
        _don_sub.setWordWrap(True)
        _don_sub.setStyleSheet(f"color:{CP['text_dim']};font-size:10px;background:transparent;")
        _don_lay.addWidget(_don_sub)

        _don_btn_row = QHBoxLayout()
        _don_btn_row.setSpacing(0)
        _don_btn_row.addStretch()
        _ss_don = (
            "QPushButton{"
            "background:transparent;color:#c8a400;"
            "border:1px solid rgba(200,164,0,0.50);"
            "border-radius:6px;font-size:10px;font-weight:700;padding:0 14px;}"
            "QPushButton:hover{"
            "background:rgba(245,197,24,0.12);color:#f5c518;"
            "border-color:rgba(245,197,24,0.70);}"
            "QPushButton:pressed{background:rgba(245,197,24,0.20);}"
        )
        _btn_don = QPushButton("❤  Soutenir PANDORA  →")
        _btn_don.setFixedHeight(30)
        _btn_don.setCursor(Qt.CursorShape.PointingHandCursor)
        _btn_don.setStyleSheet(_ss_don)

        def _open_funding(dlg=dlg):
            from ui.dialog_funding import FundingDialog
            FundingDialog(dlg).exec()

        _btn_don.clicked.connect(_open_funding)
        _don_btn_row.addWidget(_btn_don)
        _don_lay.addLayout(_don_btn_row)
        lay.addWidget(_don_frame)
        lay.addStretch()

        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)

        _ss_cancel = (
            f"QPushButton{{background:transparent;color:{CP['text_secondary']};"
            f"border:1px solid {CP['border']};border-radius:7px;"
            f"font-size:11px;font-weight:700;padding:0 14px;}}"
            f"QPushButton:hover{{background:{CP['bg2']};color:{CP['text_primary']};}}"
        )
        _ss_quit = (
            f"QPushButton{{background:transparent;color:{CP['red']};"
            f"border:1px solid rgba(255,79,106,0.45);border-radius:7px;"
            f"font-size:11px;font-weight:700;padding:0 14px;}}"
            f"QPushButton:hover{{background:rgba(255,79,106,0.14);}}"
        )
        _ss_save = (
            f"QPushButton{{background:{CP['accent']};color:#07080f;"
            f"border:none;border-radius:7px;"
            f"font-size:11px;font-weight:700;padding:0 14px;}}"
            f"QPushButton:hover{{background:#6eded6;}}"
        )

        btn_cancel   = QPushButton("Annuler")
        btn_cancel.setFixedHeight(36)
        btn_cancel.setStyleSheet(_ss_cancel)
        btn_cancel.clicked.connect(dlg.reject)

        btn_quit     = QPushButton("Quitter sans sauvegarder")
        btn_quit.setFixedHeight(36)
        btn_quit.setStyleSheet(_ss_quit)
        btn_quit.clicked.connect(lambda: dlg.done(2))

        btn_save_quit = QPushButton("Sauvegarder et quitter")
        btn_save_quit.setFixedHeight(36)
        btn_save_quit.setStyleSheet(_ss_save)
        btn_save_quit.clicked.connect(lambda: dlg.done(1))

        btn_row.addWidget(btn_cancel)
        btn_row.addStretch()
        btn_row.addWidget(btn_quit)
        btn_row.addSpacing(4)
        btn_row.addWidget(btn_save_quit)
        lay.addLayout(btn_row)

        retranslate_widget(dlg)
        result = dlg.exec()
        if result == 0:
            e.ignore()
        else:
            if result == 1:
                scenario = self._pages.get("scenario")
                if scenario and hasattr(scenario, "_save"):
                    scenario._save(silent=True)
            e.accept()

    def _on_global_save(self):
        scenario = self._pages.get("scenario")
        if scenario and hasattr(scenario, "_save"):
            scenario._save(silent=True)

    def _on_funding(self):
        try:
            from ui.dialog_funding import FundingDialog
            FundingDialog(self).exec()
        except Exception as e:
            import traceback; traceback.print_exc()
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.warning(self, "PANDORA", f"Impossible d'ouvrir la fenêtre de soutien.\n\n{e}")

    def _on_contact(self):
        from ui.dialog_contact import ContactDialog
        ContactDialog(self).exec()

    def _on_manual(self):
        from ui.dialog_user_manual import UserManualDialog
        UserManualDialog(self).exec()

    def _build_update_banner(self) -> QWidget:
        banner = QWidget()
        banner.setFixedHeight(36)
        banner.setStyleSheet(
            f"background:rgba(78,205,196,0.10);"
            f"border-bottom:1px solid rgba(78,205,196,0.25);"
        )
        lay = QHBoxLayout(banner)
        lay.setContentsMargins(20, 0, 12, 0)
        lay.setSpacing(12)

        icon = QLabel("✦")
        icon.setStyleSheet(
            f"color:{CP['accent']};font-size:12px;background:transparent;border:none;"
        )
        lay.addWidget(icon)

        self._update_banner_lbl = QLabel()
        self._update_banner_lbl.setStyleSheet(
            f"color:{CP['text_primary']};font-size:11px;font-weight:600;"
            f"background:transparent;border:none;"
        )
        lay.addWidget(self._update_banner_lbl, 1)

        self._update_dl_btn = QPushButton("Télécharger  →")
        self._update_dl_btn.setFixedHeight(22)
        self._update_dl_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._update_dl_btn.setStyleSheet(
            f"QPushButton{{background:transparent;color:{CP['accent']};"
            f"border:1px solid rgba(78,205,196,0.45);border-radius:4px;"
            f"font-size:10px;font-weight:700;padding:0 10px;}}"
            f"QPushButton:hover{{background:rgba(78,205,196,0.15);}}"
        )
        lay.addWidget(self._update_dl_btn)

        btn_close = QPushButton("✕")
        btn_close.setFixedSize(22, 22)
        btn_close.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_close.setStyleSheet(
            f"QPushButton{{background:transparent;color:{CP['text_dim']};"
            f"border:none;font-size:10px;font-weight:700;}}"
            f"QPushButton:hover{{color:{CP['text_primary']};}}"
        )
        btn_close.clicked.connect(lambda: banner.setVisible(False))
        lay.addWidget(btn_close)

        banner.setVisible(False)
        return banner

    def _manual_update_check(self):
        self._btn_update_header.setEnabled(False)
        self._btn_update_header.setText("Vérification…")
        from api.update_check import UpdateCheckWorker
        self._manual_update_worker = UpdateCheckWorker()
        self._manual_update_worker.update_available.connect(self._on_update_available)
        self._manual_update_worker.update_available.connect(
            lambda v, u: self._reset_update_btn()
        )
        self._manual_update_worker.no_update.connect(self._on_no_update_manual)
        self._manual_update_worker.check_failed.connect(self._on_update_check_failed)
        self._manual_update_worker.start()

    def _reset_update_btn(self):
        self._btn_update_header.setEnabled(True)
        self._btn_update_header.setText("↑  Mises à jour")

    def _on_no_update_manual(self):
        self._reset_update_btn()
        from PyQt6.QtWidgets import QMessageBox
        QMessageBox.information(self, translate("Mises à jour"), translate("PANDORA est à jour."))

    def _on_update_check_failed(self):
        self._reset_update_btn()

    def _maybe_show_onboarding(self):
        from core.config import load_config
        from PyQt6.QtCore import QTimer
        cfg = load_config()
        if cfg.get("show_api_guide", True):
            from ui.dialog_onboarding import OnboardingDialog
            dlg = OnboardingDialog(
                navigate_to_settings_fn=lambda: self._navigate("settings"),
                parent=self,
            )
            dlg.exec()
        QTimer.singleShot(400, self._start_update_check)

    def _start_update_check(self):
        from api.update_check import UpdateCheckWorker
        self._update_worker = UpdateCheckWorker()
        self._update_worker.update_available.connect(self._on_update_available)
        self._update_worker.no_update.connect(lambda: None)
        self._update_worker.check_failed.connect(lambda: None)
        self._update_worker.start()

    def _on_update_available(self, version: str, url: str):
        self._update_banner_lbl.setText(
            f"Nouvelle version disponible : v{version} — Mettez à jour PANDORA pour bénéficier des dernières améliorations."
        )
        try:
            self._update_dl_btn.clicked.disconnect()
        except RuntimeError:
            pass
        self._update_dl_btn.clicked.connect(lambda: self._open_url(url))
        self._update_banner.setVisible(True)

    @staticmethod
    def _open_url(url: str):
        from PyQt6.QtGui import QDesktopServices
        from PyQt6.QtCore import QUrl
        QDesktopServices.openUrl(QUrl(url))

    def _on_lang_change(self, new_lang: str):
        if new_lang == get_lang():
            return
        set_lang(new_lang)
        self._sidebar.set_lang_active(new_lang)
        retranslate_widget(self)
        _NAV_TR = {
            "projects":   "nav.projects",
            "scenario":   "nav.scenario",
            "storyboard": "nav.storyboard",
            "castings":   "nav.castings",
            "decors":     "nav.decors",
            "accessoires":"nav.accessories",
            "hmc":        "nav.hmc",
            "vehicles":   "nav.vehicles",
            "camera":     "nav.camera",
            "doublage":   "nav.doublage",
            "seedance":   "nav.seedance",
            "settings":   "nav.settings",
        }
        for key, item in self._sidebar._items.items():
            tr_key = _NAV_TR.get(key)
            if tr_key:
                item._lbl.setText(tr(tr_key))
        # Restart message (task 6)
        from PyQt6.QtWidgets import QMessageBox
        QMessageBox.information(
            self, tr("lang.title"), tr("lang.restart")
        )
