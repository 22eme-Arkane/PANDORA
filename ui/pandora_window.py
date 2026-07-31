from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QVBoxLayout,
    QLabel, QStackedWidget, QFrame, QPushButton, QStyle,
)
from PyQt6.QtCore import Qt, pyqtSignal, QSize
from PyQt6.QtGui import QShortcut, QKeySequence, QColor, QPixmap, QImage
from ui.styles import CP, PANDORA_STYLESHEET
from ui.seedance_widget import SeedanceWidget
from ui.page_stub import PageStub
from ui.page_settings import SettingsPage
from ui.page_castings import PageCastings
from ui.page_accessories import PageAccessories
from ui.page_hmc import PageHMC
from ui.page_vehicles import PageVehicles
from ui.page_camera import PageCamera
from ui.decors_hub import DecorsHub
from ui.page_scenario import PageScenario
from ui.page_storyboard import PageStoryboard
from ui.page_doublage import PageDoublage
from ui.tab_image import TabImage
from ui.icons import load_icon, badge_pixmap, app_icon, dim, tint
from ui.assistant_panel import AssistantPanel, AssistantToggleStrip
from core.i18n import tr, get_lang, set_lang, retranslate_widget, translate


def _get_nav_items():
    return [
        # Onglet Projets RÉINTRODUIT à gauche de Scénario (demande Matthieu
        # 2026-07-23) : la page de démarrage n'est plus qu'un lanceur d'édition.
        ("projets.png",    tr("nav.projects"),    "projects"),
        ("scenario.png",   tr("nav.scenario"),    "scenario"),
        ("storyboard.png", tr("nav.storyboard"),  "storyboard"),
        None,
        ("castings.png",   tr("nav.castings"),    "castings"),
        ("decors.png",     tr("nav.decors"),      "decors"),
        ("accesoires.png", tr("nav.accessories"), "accessoires"),
        ("HMC.png",        tr("nav.hmc"),         "hmc"),
        ("vehicule.png",   tr("nav.vehicles"),    "vehicles"),
        None,
        ("plan_de_feu.png", tr("nav.plan_de_feu"), "plan_de_feu"),
        # « Image & Son » RETIRÉ (décision Matthieu 2026-07-31 : « il ne sert
        # pas »). Pour le remettre : décommenter la ligne ci-dessous ET remettre
        # `_FEATURE_ENABLED = True` dans core/camera_prefs.py — sans quoi la
        # page s'afficherait mais ne mémoriserait plus rien.
        # ("camera.png",     tr("nav.camera"),      "camera"),
        ("doublage.png",   tr("nav.doublage"),    "doublage"),
        None,
        ("draw_to_video.png", tr("nav.image_ia"), "image_ia"),
        ("seedance.png",   tr("nav.video_ia"),    "seedance"),
        ("settings.png",   tr("nav.settings"),    "settings"),
    ]
    # NB : « Coût du projet » N'EST PAS dans cette liste. Ce n'est pas une page
    # de travail mais un relevé qu'on consulte : c'est un bouton discret posé à
    # côté de Paramètres, dans la zone droite de la barre (voir `_Sidebar`).


def _get_nav_groups():
    """Navigation globale unique validée pour la V2 de PANDORA.

    ⚠ Le nombre de groupes est dicté par les séparateurs de `_get_nav_items`,
    pas par cette liste de titres : ajouter un séparateur sans ajouter de titre
    faisait PLANTER l'application au démarrage sur un IndexError (régression du
    2026-07-31, en ajoutant « Coût du projet »). Les intitulés ne sont plus
    affichés depuis 2026-07-23 — ils ne servent que d'info-bulle — donc un
    groupe sans titre est parfaitement légitime : il dessine simplement un
    séparateur de plus. On indexe donc SANS jamais dépasser."""
    groups, current = [], []
    labels = [translate("ÉCRITURE"), translate("PRÉPARATION VISUELLE"),
              translate("TECHNIQUE"), tr("nav.group_studio_ia")]

    def _label() -> str:
        return labels[len(groups)] if len(groups) < len(labels) else ""

    for entry in _get_nav_items():
        if entry is None:
            groups.append((_label(), current))
            current = []
        elif entry[2] != "settings":
            current.append(entry)
    if current:
        groups.append((_label(), current))
    return groups

# Fallback texte si le PNG est absent
_FALLBACK = {
    "projets.png":     "▤",
    "univers.png":     "◈",
    "scenario.png":    "≡",
    "storyboard.png":  "⊞",
    "mise_en_scene.png": "▦",
    "plan_de_feu.png": "💡",
    "castings.png":    "⊕",
    "decors.png":      "◻",
    "accesoires.png":  "◈",
    "vehicule.png":    "🚗",
    "HMC.png":         "✂",
    "camera.png":      "◎",
    "doublage.png":    "🎙",
    "draw_to_video.png":"◈",
    "seedance.png":    "✦",
    "settings.png":    "⚙",
}

# Toutes les icônes sont affichées telles quelles (sans re-teintage QPainter) :
# ce sont des badges colorés (carré bleu marine + dessin blanc), pas des
# silhouettes — les teinter les écraserait en un aplat uni.
_COLOR_ICONS: frozenset[str] = frozenset({
    "projets.png", "scenario.png", "storyboard.png", "mise_en_scene.png",
    "castings.png", "decors.png", "accesoires.png", "HMC.png", "vehicule.png",
    "camera.png", "plan_de_feu.png", "doublage.png", "draw_to_video.png",
    "seedance.png", "settings.png",
})


def _neon_foreground(pixmap: QPixmap, color: str = "#f5c518") -> QPixmap:
    """Extrait uniquement le dessin clair d'un badge et le colore en néon.

    Les icônes historiques embarquent parfois un carré bleu marine. Teinter le
    pixmap complet colorerait aussi ce carré ; on transforme donc la luminance en
    alpha afin que seul le pictogramme intérieur reste visible.
    """
    if pixmap.isNull():
        return pixmap
    src = pixmap.toImage().convertToFormat(QImage.Format.Format_ARGB32)
    out = src.copy()
    neon = QColor(color)
    for y in range(src.height()):
        for x in range(src.width()):
            px = src.pixelColor(x, y)
            lum = int(0.2126 * px.red() + 0.7152 * px.green() + 0.0722 * px.blue())
            # Seuil doux : supprime le fond sombre, conserve les traits anti-aliasés.
            alpha = max(0, min(255, (lum - 42) * 3)) * px.alpha() // 255
            out.setPixelColor(x, y, QColor(neon.red(), neon.green(), neon.blue(), alpha))
    return QPixmap.fromImage(out)


class NavItem(QWidget):
    """Item de la barre de navigation BASSE (refonte 2026-06-12, portée depuis
    PANDORA | Live) : icône au-dessus d'un libellé court, centré, façon barre
    de pages DaVinci Resolve. Actif = pastille accent (teal Cinéma)."""
    nav_clicked = pyqtSignal(str)

    def __init__(self, icon_file: str, label: str, key: str):
        super().__init__()
        self._key      = key
        self._active   = False
        self._ico_file = icon_file
        self.setFixedHeight(54)
        self.setMinimumWidth(64)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setObjectName("NavItem")

        _pix_raw  = load_icon(icon_file, 24)
        _is_color = icon_file in _COLOR_ICONS
        # Onglet ACTIF : vert « Nous contacter » (#25d366) à 75 % d'opacité —
        # remplace le jaune néon (demande Matthieu 2026-07-22).
        if not _pix_raw.isNull():
            if _is_color:
                # Fond coloré propre — on préserve les couleurs d'origine
                self._pix_white  = _pix_raw
                self._pix_accent = dim(_neon_foreground(_pix_raw, "#25d366"), 0.75)
            else:
                # Silhouette sur transparent — on normalise en blanc
                self._pix_white  = tint(_pix_raw, "#ffffff")
                self._pix_accent = dim(tint(_pix_raw, "#25d366"), 0.75)
        else:
            self._pix_white  = _pix_raw
            self._pix_accent = _pix_raw
        self._pix_on  = self._pix_white
        self._pix_off = dim(self._pix_white, 0.55)
        self._use_png = not _pix_raw.isNull()

        lay = QVBoxLayout(self)
        lay.setContentsMargins(7, 3, 7, 3)
        lay.setSpacing(2)
        lay.setAlignment(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter)

        self._ico = QLabel()
        self._ico.setFixedSize(24, 24)
        self._ico.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._ico.setStyleSheet("background:transparent;border:none;")

        self._lbl = QLabel(label)
        self._lbl.setAlignment(Qt.AlignmentFlag.AlignHCenter)

        lay.addWidget(self._ico, alignment=Qt.AlignmentFlag.AlignHCenter)
        lay.addWidget(self._lbl)

        self._apply(False)

    def _bg(self, css: str):
        self.setStyleSheet(f"QWidget#NavItem{{{css}border-radius:8px;}}")

    def _apply(self, active: bool):
        if active:
            self._bg("background:transparent;border:1px solid transparent;")
            if self._use_png:
                self._ico.setPixmap(self._pix_accent)  # vert contact sur fond actif
            else:
                self._ico.setText(_FALLBACK.get(self._ico_file, "●"))
                self._ico.setStyleSheet(
                    "color:rgba(37,211,102,0.75);font-size:14px;background:transparent;border:none;"
                )
            self._lbl.setStyleSheet(
                "color:rgba(37,211,102,0.75);font-size:10px;font-weight:700;"
                f"letter-spacing:0.3px;background:transparent;border:none;"
            )
        else:
            self._bg("background:transparent;border:1px solid transparent;")
            if self._use_png:
                self._ico.setPixmap(self._pix_off)  # blanc dim
            else:
                self._ico.setText(_FALLBACK.get(self._ico_file, "●"))
                self._ico.setStyleSheet(
                    f"color:{CP['text_dim']};font-size:14px;background:transparent;border:none;"
                )
            self._lbl.setStyleSheet(
                f"color:{CP['text_secondary']};font-size:10px;font-weight:600;"
                f"letter-spacing:0.2px;background:transparent;border:none;"
            )

    def setActive(self, active: bool):
        self._active = active
        self._apply(active)

    def enterEvent(self, e):
        if not self._active:
            # Le survol ne dessine plus de carte autour de l'onglet. La barre
            # conserve ainsi sa légèreté : seuls le pictogramme et le libellé
            # gagnent en contraste, tandis que l'état actif reste jaune néon.
            self._bg("background:transparent;border:1px solid transparent;")
            if self._use_png:
                self._ico.setPixmap(self._pix_on)
            self._lbl.setStyleSheet(
                f"color:{CP['text_primary']};font-size:10px;font-weight:600;"
                f"background:transparent;border:none;"
            )

    def leaveEvent(self, e):
        if not self._active:
            self._apply(False)

    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            self.nav_clicked.emit(self._key)


class _Sidebar(QWidget):
    """Barre de navigation BASSE (refonte 2026-06-12, portée depuis Live) —
    taskbar façon DaVinci Resolve : drapeaux de langue à gauche, icônes de
    pages au centre, Paramètres en bas à droite (Manuel et Nous contacter
    vivent dans la topbar). Toute la largeur de l'écran revient aux pages."""
    nav_clicked           = pyqtSignal(str)
    manual_requested      = pyqtSignal()
    contact_requested     = pyqtSignal()
    lang_change_requested = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        # 64 px : les intitulés de groupe (ÉCRITURE, PRÉPARATION VISUELLE…) sont
        # retirés (demande Matthieu 2026-07-23) — la barre reprend une hauteur
        # compacte, seuls les pictogrammes + libellés restent.
        self.setFixedHeight(64)
        # Sélecteur CIBLÉ obligatoire : une règle sans sélecteur se propage aux
        # ENFANTS stylés → chaque groupe repeignait le border-top, d'où les
        # « traits au-dessus des logos » (retour Matthieu 2026-07-23).
        self.setObjectName("PandoraBottomBar")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setStyleSheet(
            f"QWidget#PandoraBottomBar{{background:{CP['sidebar']};"
            f"border-top:1px solid {CP['border']};}}"
        )

        lay = QHBoxLayout(self)
        lay.setContentsMargins(10, 4, 10, 4)
        lay.setSpacing(4)
        lay.setAlignment(Qt.AlignmentFlag.AlignVCenter)

        def _vsep() -> QFrame:
            f = QFrame()
            f.setFixedSize(1, 32)
            f.setStyleSheet("background:rgba(255,255,255,0.08);")
            return f

        # ── Gauche : sélecteur de langue (drapeaux) ───────────────────────────
        self._lang_btns: dict[str, QPushButton] = {}
        _flag_map = {"fr": "Fr.png", "en": "En.png"}
        _cur_lang = get_lang()
        for code, flag_file in _flag_map.items():
            btn = QPushButton()
            btn.setFixedSize(32, 32)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setToolTip("Français" if code == "fr" else "English")
            _flag_pix = load_icon(flag_file, 22)
            if not _flag_pix.isNull():
                from PyQt6.QtGui import QIcon as _QIcon
                from PyQt6.QtCore import QSize as _QSize
                btn.setIcon(_QIcon(_flag_pix))
                btn.setIconSize(_QSize(22, 22))
                btn.setText("")
            else:
                btn.setText("FR" if code == "fr" else "EN")
            self._apply_lang_btn_style(btn, code == _cur_lang)
            btn.clicked.connect(lambda checked, c=code: self.lang_change_requested.emit(c))
            lay.addWidget(btn)
            self._lang_btns[code] = btn

        lay.addSpacing(4)
        lay.addWidget(_vsep())
        lay.addStretch()

        # ── Centre : quatre groupes lisibles. Paramètres reste seul à droite.
        self._items: dict[str, NavItem] = {}
        for group_index, (group_label, entries) in enumerate(_get_nav_groups()):
            if group_index:
                lay.addWidget(_vsep())
            group = QWidget()
            group.setStyleSheet("background:transparent;")
            gl = QVBoxLayout(group)
            gl.setContentsMargins(2, 0, 2, 0)
            gl.setSpacing(0)
            # Intitulés de groupe RETIRÉS (2026-07-23) — les séparateurs verticaux
            # suffisent à distinguer les familles. group_label reste disponible
            # comme info-bulle du groupe.
            group.setToolTip(group_label)
            row = QHBoxLayout()
            row.setContentsMargins(0, 0, 0, 0)
            row.setSpacing(1)
            for icon_file, label, key in entries:
                item = NavItem(icon_file, label, key)
                item.nav_clicked.connect(self.nav_clicked)
                self._items[key] = item
                row.addWidget(item)
            gl.addLayout(row)
            lay.addWidget(group)

        lay.addStretch()

        # ── « Coût du projet » — juste avant Paramètres ───────────────────────
        # Bouton DISCRET (demande Matthieu 2026-07-31) : même forme que « Nous
        # contacter » — bordure fine, fond transparent — mais dans le gris des
        # libellés de la barre, sans émoticône. Ce n'est pas une étape du
        # travail, ça ne doit pas attirer l'œil plus que Paramètres.
        self._btn_cost = QPushButton(tr("nav.cost"))
        self._btn_cost.setFixedHeight(26)
        self._btn_cost.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_cost.setStyleSheet(
            f"QPushButton{{background:transparent;color:{CP['text_secondary']};"
            f"border:1px solid {CP['border']};border-radius:5px;"
            f"font-size:10px;font-weight:600;padding:0 10px;}}"
            f"QPushButton:hover{{color:{CP['text_primary']};"
            f"border-color:{CP['border_bright']};"
            f"background:rgba(255,255,255,0.05);}}"
            f"QPushButton:pressed{{background:rgba(255,255,255,0.09);}}")
        self._btn_cost.clicked.connect(lambda: self.nav_clicked.emit("cost"))
        lay.addWidget(self._btn_cost)

        # Séparateur ENTRE le coût et Paramètres (demande Matthieu) : le coût
        # se rattache visuellement aux onglets de travail, Paramètres reste
        # isolé tout au bord.
        lay.addSpacing(4)
        lay.addWidget(_vsep())
        lay.addSpacing(4)

        # ── Droite : Paramètres tout au bord ──────────────────────────────────
        icon_file, label, key = next(e for e in _get_nav_items()
                                     if e is not None and e[2] == "settings")
        item = NavItem(icon_file, label, key)
        item.nav_clicked.connect(self.nav_clicked)
        self._items[key] = item
        lay.addWidget(item)

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
    home_requested = pyqtSignal()         # retour à la page de démarrage

    def __init__(self, project: dict, is_secondary: bool = False):
        super().__init__()
        self._project = project
        # Fenêtre secondaire (P5 « 2 écrans ») : copie de PANDORA sur le même projet,
        # navigation indépendante. Elle NE relance PAS l'onboarding / le check MAJ et
        # sa fermeture ne propose PAS de quitter le programme (elle se ferme seule).
        self._is_secondary   = is_secondary
        self._secondary_wins: list = []

        # Set project context before any page loads data
        import core.context as _ctx
        from core.migration import migrate_legacy_data
        pid = project.get("id", "")
        _ctx.set_project_id(pid)
        _ctx.set_project_path(project.get("_path", ""))
        migrate_legacy_data(pid)  # no-op after first run; always uses oldest project
        # Réinitialise le namespace storyboard (PANDORA | Live peut l'avoir changé)
        import core.storyboard as _sb_ns
        _sb_ns.set_namespace("storyboard")

        _title_suffix = "   ·   Écran 2" if is_secondary else ""
        self.setWindowTitle(f"PANDORA — {project.get('name', 'Projet')}{_title_suffix}")
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

        self._sidebar = _Sidebar()   # barre de navigation BASSE (refonte 2026-06-12)
        # Disquette de sauvegarde dans la barre basse, à droite des drapeaux de
        # langue et de leur séparateur (index 4 du layout — demande 2026-07-23).
        self._sidebar.layout().insertWidget(4, self._btn_save_global)
        self._stack   = QStackedWidget()
        self._stack.setStyleSheet(f"background:{CP['bg0']};")

        # header_height=40 (2026-07-23) : la ligne sous l'en-tête GUIDE tombe
        # EXACTEMENT sur la ligne de la première rangée des pages (barre d'outils
        # texte du Scénario et barre d'outils du Storyboard, toutes deux à 40 px).
        self._assistant         = AssistantPanel(header_height=40)
        self._assistant.setVisible(False)   # replié par défaut (ouvrir via la poignée « IA »)
        self._assistant_toggle  = AssistantToggleStrip(self._assistant, side="left")

        # Assistant IA à GAUCHE (poignée au bord, panneau, puis les pages) ;
        # à DROITE, le Chat Storyboard en MIROIR (panneau puis poignée au bord),
        # visible uniquement sur la page Storyboard ; ailleurs une colonne
        # permanente (spacer) de la largeur de la poignée préserve la symétrie.
        # La nav vit en BAS — les pages prennent toute la largeur.
        from ui.storyboard_chat import StoryboardChatPanel, StoryboardChatToggleStrip
        self._sb_chat_panel = StoryboardChatPanel(
            shots_provider=self._sb_chat_shots,
            on_applied=self._sb_chat_applied,
            header_height=40,   # aligné sur la barre d'outils du Storyboard (2026-07-23)
        )
        self._sb_chat_panel.setVisible(False)            # fermé par défaut
        self._sb_chat_toggle = StoryboardChatToggleStrip(self._sb_chat_panel)
        self._sb_chat_toggle.setVisible(False)           # visible sur Storyboard seulement

        self._right_spacer = QWidget()
        self._right_spacer.setFixedWidth(self._assistant_toggle.maximumWidth())
        self._right_spacer.setStyleSheet(f"background:{CP['bg1']};")

        body_lay.addWidget(self._assistant_toggle)
        body_lay.addWidget(self._assistant)
        body_lay.addWidget(self._stack, 1)
        body_lay.addWidget(self._sb_chat_panel)
        body_lay.addWidget(self._sb_chat_toggle)
        body_lay.addWidget(self._right_spacer)
        outer.addWidget(body, 1)
        outer.addWidget(self._sidebar)

        self._pages: dict[str, QWidget] = {}
        self._build_pages()

        self._sidebar.nav_clicked.connect(self._navigate)
        self._sidebar.manual_requested.connect(self._on_manual)
        self._sidebar.contact_requested.connect(self._on_contact)
        self._sidebar.lang_change_requested.connect(self._on_lang_change)
        self._navigate("scenario")

        from PyQt6.QtCore import QTimer
        if not self._is_secondary:
            QTimer.singleShot(900, self._maybe_show_onboarding)

        _sc = QShortcut(QKeySequence("Ctrl+S"), self)
        _sc.activated.connect(self._on_global_save_click)

    def open_secondary_window(self):
        """P5 — ouvre une 2ᵉ fenêtre PANDORA (même projet, navigation indépendante),
        placée sur le 2ᵉ écran s'il existe. Utile pour travailler le Storyboard à
        droite pendant qu'on écrit le Scénario à gauche. Appelée depuis Paramètres."""
        from PyQt6.QtWidgets import QApplication
        win = PandoraWindow(self._project, is_secondary=True)
        # Fenêtre INDÉPENDANTE et NON modale : elle ne doit jamais bloquer l'autre
        # écran ni faire sonner l'alerte « une fenêtre est ouverte ». Top-level sans
        # parent + modalité explicitement désactivée.
        win.setWindowModality(Qt.WindowModality.NonModal)
        win.setWindowFlag(Qt.WindowType.Window, True)
        self._secondary_wins.append(win)
        # Nettoyage de la référence anti-GC à la fermeture de la 2ᵉ fenêtre.
        win.destroyed.connect(
            lambda *_a, w=win: self._secondary_wins.remove(w)
            if w in self._secondary_wins else None
        )
        screens = QApplication.screens()
        primary = self.screen()
        target  = next((s for s in screens if s is not primary), None)
        if target is not None:
            geo = target.availableGeometry()
            win.move(geo.left() + 40, geo.top() + 40)
            win.resize(min(1400, geo.width() - 80), min(900, geo.height() - 80))
        else:
            # Un seul écran : décalage pour ne pas recouvrir la 1ʳᵉ fenêtre.
            win.move(self.x() + 60, self.y() + 60)
        win.show()
        win.raise_()
        win.activateWindow()
        return win

    def _build_pages(self):
        # Page Projets (réintroduite 2026-07-23) : ouvrir/créer un projet depuis
        # la fenêtre — le switch recrée la fenêtre via main._on_switch.
        from ui.page_projects import PageProjects
        projects = PageProjects(self._project)
        # Un projet sans champ « mode » reste dans l'édition courante.
        projects.switch_requested.connect(
            lambda d: self.switch_requested.emit({**d, "mode": d.get("mode", "cinema")}))
        self._pages["projects"] = projects
        self._stack.addWidget(projects)

        scenario = PageScenario()
        scenario.navigate_requested.connect(
            lambda key, extra: self._navigate(key, extra)
        )
        scenario.style_changed.connect(self._on_scenario_style_changed)
        self._pages["scenario"] = scenario
        self._stack.addWidget(scenario)
        # pulse() : anime le splash de chargement pendant la construction
        # (événements d'entrée exclus — voir ui/loading_splash).
        from ui.loading_splash import pulse
        pulse()

        storyboard = PageStoryboard()
        self._pages["storyboard"] = storyboard
        self._stack.addWidget(storyboard)
        pulse()

        from ui.page_staging import PageLighting
        plan_de_feu = PageLighting()
        self._pages["plan_de_feu"] = plan_de_feu
        # Compatibilité : les anciens raccourcis « Mise en scène » ouvrent le
        # plateau unifié sans recréer une seconde page ni un second état.
        self._pages["mise_en_scene"] = plan_de_feu
        self._stack.addWidget(plan_de_feu)
        pulse()

        # Deux onglets depuis le 2026-07-31 : « Décors » (page classique) et
        # « 7 vues » (atelier de rotations) — voir ui/decors_hub.py.
        decors = DecorsHub()
        self._pages["decors"] = decors
        self._stack.addWidget(decors)
        pulse()

        # Page « Image & Son » plus construite — voir la nav ci-dessus. La
        # classe reste importée et intacte ; rien d'autre ne la référence.
        # camera = PageCamera()
        # self._pages["camera"] = camera
        # self._stack.addWidget(camera)

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
        pulse()

        doublage = PageDoublage()
        self._pages["doublage"] = doublage
        self._stack.addWidget(doublage)

        # Image IA est une destination globale autonome. Le panneau partagé
        # reste la source unique de l'app Studio Images et de PANDORA.
        image_ia = TabImage()
        self._pages["image_ia"] = image_ia
        self._stack.addWidget(image_ia)
        pulse()

        settings = SettingsPage()
        settings.manual_requested.connect(self._on_manual)
        self._pages["settings"] = settings
        # Paramètres pleine largeur depuis le 2026-07-22 : la barre de défilement
        # doit être collée au bord DROIT de la fenêtre. Le centrage du contenu
        # (largeur max 1360) est géré À L'INTÉRIEUR de SettingsPage.
        self._settings_wrap = settings
        self._stack.addWidget(self._settings_wrap)

        seedance = SeedanceWidget()
        self._pages["seedance"] = seedance
        self._stack.addWidget(seedance)
        pulse()

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
        _llay = QHBoxLayout(_left)
        _llay.setContentsMargins(0, 0, 0, 0)
        _llay.setSpacing(0)
        _llay.setAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)

        # ── Nous contacter — le manuel rejoint la page Paramètres ─────────────
        _ss_contact_green = (
            "QPushButton{background:transparent;color:#25d366;"
            "border:1px solid rgba(37,211,102,0.35);border-radius:5px;"
            "font-size:10px;font-weight:700;padding:0 10px;}"
            "QPushButton:hover{background:rgba(37,211,102,0.10);color:#2ee27a;"
            "border-color:rgba(37,211,102,0.60);}"
            "QPushButton:pressed{background:rgba(37,211,102,0.18);}"
        )
        self._btn_contact_top = QPushButton("✉  " + translate("Nous contacter"))
        self._btn_contact_top.clicked.connect(self._on_contact)
        self._btn_contact_top.setStyleSheet(_ss_contact_green)
        for _b in (self._btn_contact_top,):
            _b.setFixedHeight(26)
            _b.setCursor(Qt.CursorShape.PointingHandCursor)
            _llay.addWidget(_b)
            _llay.addSpacing(6)

        _lr_lay.addWidget(_left, 1)
        self._home_hit = QPushButton()
        self._home_hit.setFixedSize(190, 58)
        self._home_hit.setToolTip(translate("Retour à l'accueil"))
        self._home_hit.setCursor(Qt.CursorShape.PointingHandCursor)
        self._home_hit.setStyleSheet("QPushButton{background:transparent;border:none;}")
        self._home_hit.clicked.connect(self.home_requested)
        _lr_lay.addWidget(self._home_hit)

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
        # « Soutenir Pandora » collé au bord droit du cadre (2026-07-23) : la
        # disquette a migré dans la barre basse, plus de séparateur ici.
        _rlay.addWidget(btn_support)
        _lr_lay.setContentsMargins(12, 0, 4, 0)

        # ── Sauvegarder : icône seule — créée ici, AFFICHÉE dans la barre basse
        # (à droite des drapeaux de langue, demande Matthieu 2026-07-23) ─────────
        self._btn_save_global = QPushButton()
        self._btn_save_global.setIcon(
            self.style().standardIcon(QStyle.StandardPixmap.SP_DialogSaveButton))
        self._btn_save_global.setIconSize(QSize(15, 15))
        self._btn_save_global.setToolTip(tr("btn.save"))
        self._btn_save_global.setFixedSize(30, 26)
        self._btn_save_global.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_save_global.setStyleSheet(
            f"QPushButton{{background:transparent;color:{CP['text_dim']};"
            f"border:1px solid {CP['border']};border-radius:5px;"
            f"font-size:14px;font-weight:700;padding:0;}}"
            f"QPushButton:hover{{background:{CP['bg3']};color:{CP['text_primary']};"
            f"border-color:{CP['border_bright']};}}"
            f"QPushButton:pressed{{background:{CP['bg4']};}}"
        )
        self._btn_save_global.clicked.connect(self._on_global_save_click)
        # Insertion différée dans la barre basse (voir _install_save_in_sidebar).

        _lr_lay.addWidget(_right, 1)

        bar_lay.addWidget(_lr)       # couche 0 — gauche/droite
        bar_lay.addWidget(_center)   # couche 1 — logo centré, passe-transparent
        bar_lay.setCurrentIndex(1)   # couche 1 au-dessus (z-order)
        return bar

    def _on_global_save_click(self):
        self._on_global_save()
        self._btn_save_global.setIcon(
            self.style().standardIcon(QStyle.StandardPixmap.SP_DialogApplyButton))
        self._btn_save_global.setStyleSheet(
            f"QPushButton{{background:transparent;color:{CP['accent']};"
            f"border:1px solid {CP['accent_dim']};border-radius:5px;"
            f"font-size:14px;font-weight:700;padding:0;}}"
        )
        from PyQt6.QtCore import QTimer
        QTimer.singleShot(1400, self._reset_save_btn_global)

    def _reset_save_btn_global(self):
        self._btn_save_global.setIcon(
            self.style().standardIcon(QStyle.StandardPixmap.SP_DialogSaveButton))
        self._btn_save_global.setStyleSheet(
            f"QPushButton{{background:transparent;color:{CP['text_dim']};"
            f"border:1px solid {CP['border']};border-radius:5px;"
            f"font-size:14px;font-weight:700;padding:0;}}"
            f"QPushButton:hover{{background:{CP['bg3']};color:{CP['text_primary']};"
            f"border-color:{CP['border_bright']};}}"
            f"QPushButton:pressed{{background:{CP['bg4']};}}"
        )

    def _refresh_page(self, page):
        """Rafraîchit une page, avec coalescence pour les ateliers plus lourds."""
        if not hasattr(page, "refresh"):
            return
        if not getattr(page, "DEFER_NAV_REFRESH", False):
            page.refresh()
            return
        if getattr(page, "_pandora_refresh_pending", False):
            return
        page._pandora_refresh_pending = True

        def _run():
            page._pandora_refresh_pending = False
            # Une navigation plus récente a pu changer la page entre-temps.
            current = self._stack.currentWidget()
            if current is page:
                page.refresh()

        from PyQt6.QtCore import QTimer
        QTimer.singleShot(0, _run)

    def _navigate(self, key: str, extra: str = ""):
        if key == "mise_en_scene":
            key = "plan_de_feu"

        # « Coût du projet » n'est pas une page mais une FENÊTRE : on l'ouvre et
        # on laisse la navigation où elle était, sinon un simple coup d'œil au
        # budget ferait perdre l'écran de travail en cours.
        if key == "cost":
            try:
                from ui.dialog_project_cost import ProjectCostDialog
                ProjectCostDialog(self).exec()
            except Exception as e:
                from PyQt6.QtWidgets import QMessageBox
                QMessageBox.warning(self, translate("Coût du projet"),
                                    translate("Impossible d'ouvrir le coût du "
                                              "projet : ") + str(e)[:200])
            self._sidebar.set_active(getattr(self, "_current_nav", "") or "")
            return

        self._current_nav = key   # mémorisé pour le rafraîchissement au retour de focus
        page = self._pages.get(key)
        if page:
            # Paramètres vit dans son conteneur centré
            self._stack.setCurrentWidget(
                self._settings_wrap if key == "settings" else page)
            if extra and hasattr(page, "open_version"):
                page.open_version(extra)
            else:
                self._refresh_page(page)
            if get_lang() != "fr":
                retranslate_widget(page)
        self._sidebar.set_active(key)
        self._assistant.set_context(key)
        self._update_sb_chat(key)

    def changeEvent(self, event):
        # P5 — 2 fenêtres sur le même projet (données fichier PARTAGÉES) : quand une
        # fenêtre reprend le focus, on recharge la page visible depuis le disque pour
        # refléter ce qui a été fait dans l'autre fenêtre (ex. storyboard généré à
        # gauche → visible en cliquant sur la fenêtre de droite), sans changer d'onglet.
        from PyQt6.QtCore import QEvent
        super().changeEvent(event)
        if event.type() == QEvent.Type.ActivationChange and self.isActiveWindow():
            self._refresh_on_focus()

    def _refresh_on_focus(self):
        key = getattr(self, "_current_nav", None)
        if not key:
            return
        # Contexte projet GLOBAL partagé : le réaffirmer avant de recharger (l'autre
        # fenêtre a pu le laisser cohérent — même projet — mais on sécurise).
        page = self._pages.get(key)
        if page is not None and hasattr(page, "refresh"):
            try:
                self._refresh_page(page)
            except Exception:
                pass

    # ── Chat Storyboard (à droite, miroir de l'assistant) ─────────────────────────

    def _sb_chat_shots(self) -> list:
        page = self._pages.get("storyboard")
        return list(getattr(page, "_all_shots", []) or [])

    def _sb_chat_applied(self):
        page = self._pages.get("storyboard")
        if page and hasattr(page, "_on_chat_applied"):
            page._on_chat_applied()

    def _update_sb_chat(self, key: str):
        """Le chat storyboard n'est actif que sur la page Storyboard ; ailleurs,
        on rend le spacer pour garder la symétrie avec la poignée IA de gauche."""
        is_sb = (key == "storyboard")
        self._sb_chat_toggle.setVisible(is_sb)
        if not is_sb:
            self._sb_chat_panel.setVisible(False)
            self._sb_chat_toggle._open = False
            self._sb_chat_toggle._arrow.setText(self._sb_chat_toggle._arrow_char())
        # Image IA a sa PROPRE poignée droite (chat de création) : on masque le
        # spacer pour que cette poignée soit COLLÉE
        # au bord droit, exactement comme la poignée « GUIDE » l'est à gauche
        # (retour Matthieu 2026-07-05).
        # « scenario » ajouté (2026-07-23) : sa poignée ASSISTANT est collée au
        # bord droit, comme les poignées d'Image IA et du Plan de feu.
        # Pages à POIGNÉE droite propre (ASSISTANT / IA / RÉGLAGES / FICHE) : le
        # spacer de symétrie disparaît pour que la poignée COLLE au bord —
        # étendu aux 5 pages éléments le 2026-07-23 (les fiches étaient décalées).
        self._right_spacer.setVisible(not is_sb and key not in (
            "image_ia", "plan_de_feu", "scenario",
            "castings", "decors", "accessoires", "hmc", "vehicles"))

    def _refresh_project_page(self):
        """Le choix de projet vit désormais uniquement sur la page de démarrage."""
        self.home_requested.emit()

    def _on_scenario_style_changed(self, key: str):
        """Propagate scenario style change to all relevant pages."""
        seedance = self._pages.get("seedance")
        if seedance and hasattr(seedance, "refresh"):
            seedance.refresh()   # syncs T2V film_style_combo via _refresh_style_badge

    def closeEvent(self, e):
        # Fenêtre secondaire (P5) : elle se ferme seule, sans proposer de quitter
        # tout le programme ni resauvegarder (la fenêtre principale s'en charge).
        if getattr(self, "_is_secondary", False):
            e.accept()
            return
        # Confirmation de fermeture PARTAGÉE Cinéma ↔ Live (demande de sauvegarde).
        from ui.quit_dialog import confirm_quit
        result = confirm_quit(self)
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
            _msg = translate("Impossible d'ouvrir la fenêtre de soutien.")
            QMessageBox.warning(self, "PANDORA", f"{_msg}\n\n{e}")

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
        button = getattr(self, "_btn_update_header", None)
        if button is not None:
            button.setEnabled(False)
            button.setText("Vérification…")
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
        button = getattr(self, "_btn_update_header", None)
        if button is not None:
            button.setEnabled(True)
            button.setText("↑  Mises à jour")

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
        except (TypeError, RuntimeError):
            # PyQt6 lève TypeError si le signal n'a aucune connexion (1er appel).
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
            "mise_en_scene": "nav.mise_en_scene",
            "castings":   "nav.castings",
            "decors":     "nav.decors",
            "accessoires":"nav.accessories",
            "hmc":        "nav.hmc",
            "vehicles":   "nav.vehicles",
            "camera":     "nav.camera",
            "plan_de_feu": "nav.plan_de_feu",
            "doublage":   "nav.doublage",
            "image_ia":   "nav.image_ia",
            "seedance":   "nav.video_ia",
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
