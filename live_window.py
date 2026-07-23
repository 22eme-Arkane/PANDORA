"""
live_window.py — Fenêtre PANDORA | Live (performance live / VJ / mapping).

Agencement : topbar globale + stack de pages (pleine largeur) + panneau assistant,
et une BARRE DE NAVIGATION BASSE façon DaVinci Resolve (icônes de pages au centre,
drapeaux de langue à gauche, Manuel/Contact à droite) — demande Matthieu 2026-06-12 :
récupérer toute la largeur de l'écran pour les pages.

Pages :
  - studio    : Studio IA (génération de loops) — réutilise SeedanceWidget  → ui/seedance_widget.py
  - sequences : Séquences (storyboard Live, placeholder)                    → ui/page_live_sequences.py
  - mapping   : Mapping vidéo (placeholder, à venir)                        → ui/page_mapping.py
  - resolume  : Contrôle Resolume (existant, conservé en onglet)            → ui/page_live.py
  - settings  : Paramètres Live                                            → ui/page_live_settings.py

Le sélecteur de styles VJ (core/vj_styles.py, 20 styles) sera intégré DANS le
Studio IA à la génération (à brancher) — pas en page autonome.

⚠  Le mapping, les séquences et la connexion Resolume temps réel ne sont PAS
   développés cette session — voir les TODO dans les pages concernées.
"""

from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QVBoxLayout,
    QLabel, QStackedWidget, QFrame, QPushButton, QStyle,
)
from PyQt6.QtCore import Qt, pyqtSignal, QSize
from PyQt6.QtGui import QIcon, QShortcut, QKeySequence, QColor, QPixmap, QImage

from ui.styles import CP, PANDORA_STYLESHEET
from ui.icons import app_icon, load_icon, dim
from ui.assistant_panel import AssistantPanel, AssistantToggleStrip
from core.i18n import get_lang, set_lang, retranslate_widget, translate, tr


def _neon_foreground(pixmap: QPixmap, color: str = "#25d366") -> QPixmap:
    """Extrait uniquement le dessin clair d'un badge et le colore en néon.

    Les icônes historiques embarquent parfois un carré bleu marine. Teinter le
    pixmap complet colorerait aussi ce carré ; on transforme donc la luminance en
    alpha afin que seul le pictogramme intérieur reste visible.
    (Copie Live de la recette pandora_window — séparation Cinéma/Live.)"""
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


# ── Item de navigation Live (barre BASSE, façon pages DaVinci Resolve) ────────

class _LiveNavItem(QWidget):
    """Icône au-dessus d'un libellé court, centré — comme la barre de pages de
    DaVinci Resolve (Media/Cut/Edit…). Actif = pastille accent."""
    nav_clicked = pyqtSignal(str)

    def __init__(self, icon: str, label: str, key: str, icon_file: str = ""):
        super().__init__()
        self._key    = key
        self._active = False
        self.setFixedHeight(54)
        self.setMinimumWidth(72)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        # Fond stylable sur le QWidget lui-même (pastille active / hover)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setObjectName("LiveNavItem")

        lay = QVBoxLayout(self)
        lay.setContentsMargins(12, 5, 12, 4)
        lay.setSpacing(2)
        lay.setAlignment(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter)

        # Icône : PNG des logos Cinéma si disponible (logos dédiés Live à venir),
        # sinon repli sur le glyphe texte.
        # Onglet ACTIF : vert « Nous contacter » (#25d366) à 75 % d'opacité —
        # remplace l'ancienne pastille accent (demande Matthieu 2026-07-23,
        # parité pandora_window.NavItem).
        self._use_png = False
        self._pix_on = self._pix_off = self._pix_accent = None
        if icon_file:
            _pix = load_icon(icon_file, 24)
            if not _pix.isNull():
                self._use_png = True
                self._pix_on     = _pix
                self._pix_off    = dim(_pix, 0.55)
                self._pix_accent = dim(_neon_foreground(_pix, "#25d366"), 0.75)

        self._ico = QLabel("" if self._use_png else icon)
        self._ico.setFixedSize(24, 24)
        self._ico.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._ico.setStyleSheet("background:transparent;border:none;font-size:14px;")
        if self._use_png:
            self._ico.setPixmap(self._pix_off)

        self._lbl = QLabel(label)
        self._lbl.setAlignment(Qt.AlignmentFlag.AlignHCenter)

        lay.addWidget(self._ico, alignment=Qt.AlignmentFlag.AlignHCenter)
        lay.addWidget(self._lbl)

        self._apply(False)

    def _bg(self, css: str):
        self.setStyleSheet(f"QWidget#LiveNavItem{{{css}border-radius:8px;}}")

    def _apply(self, active: bool):
        if active:
            # Plus de pastille : libellé + pictogramme intérieur en VERT
            # « Nous contacter » (#25d366) à 75 % d'opacité (2026-07-23).
            self._bg("background:transparent;border:1px solid transparent;")
            if self._use_png:
                self._ico.setPixmap(self._pix_accent)
            else:
                self._ico.setStyleSheet(
                    "color:rgba(37,211,102,0.75);font-size:14px;"
                    "background:transparent;border:none;"
                )
            self._lbl.setStyleSheet(
                "color:rgba(37,211,102,0.75);font-size:10px;font-weight:700;"
                "letter-spacing:0.3px;background:transparent;border:none;"
            )
        else:
            self._bg("background:transparent;border:1px solid transparent;")
            if self._use_png:
                self._ico.setPixmap(self._pix_off)
            else:
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
            # Survol léger (parité Cinéma 2026-07-23) : pas de carte autour de
            # l'onglet, seuls pictogramme et libellé gagnent en contraste.
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


# ── Barre de navigation BASSE (taskbar façon DaVinci Resolve) ─────────────────

# Onglets retirés pour le moment (code conservé) : "Outils Mapping" (page_mapping).
# (glyphe de repli, libellé FR, clé, PNG — logos Cinéma réutilisés en attendant
#  des logos dédiés Live : Conducteur→scenario.png, Séquences→storyboard.png)
# L'ordre gauche→droite reprend l'ancien ordre haut→bas du dashboard latéral.
# « Projets » RETIRÉ de la nav basse (2026-07-23, parité Cinéma) : le retour aux
# projets passe par le logo PANDORA → page de démarrage (home_requested).
# « Image IA » AJOUTÉ à côté de « Studio IA » (réutilise ui/tab_image.py).
_NAV_ITEMS = [
    # Onglet Projets RÉINTRODUIT à gauche du Conducteur (demande Matthieu
    # 2026-07-23) : la page de démarrage n'est plus qu'un lanceur d'édition.
    ("❐", "Projets",             "projects",    "projets.png"),
    ("✎", "Conducteur",          "conducteur",  "scenario.png"),
    None,
    ("▤", "Séquences Live",      "seq_live",    "storyboard.png"),
    ("▥", "Séquences Mapping",   "seq_mapping", "storyboard.png"),
    None,
    ("☺", "Casting",             "casting",     "castings.png"),
    ("❖", "Accessoires",         "accessoires", "accesoires.png"),
    ("⛟", "Véhicules",           "vehicules",   "vehicule.png"),
    None,
    ("▶", "Resolume",            "resolume",    "Live.png"),
    None,
    ("◈", "Image IA",            "image_ia",    "draw_to_video.png"),
    ("✦", "Studio IA",           "studio",      "seedance.png"),
    ("⚙", "Paramètres",          "settings",    "settings.png"),
]


class _LiveSidebar(QWidget):
    """Barre de navigation BASSE — taskbar façon DaVinci Resolve / Windows :
    drapeaux de langue à gauche, icônes de pages au centre, Paramètres en bas
    à droite (Manuel et Nous contacter vivent dans la topbar, en haut à
    gauche). Toute la largeur de l'écran revient aux pages."""
    nav_clicked           = pyqtSignal(str)
    manual_requested      = pyqtSignal()
    contact_requested     = pyqtSignal()
    lang_change_requested = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self.setFixedHeight(64)
        # Sélecteur CIBLÉ : une règle sans sélecteur se propage aux enfants
        # stylés → traits au-dessus des groupes (retour Matthieu 2026-07-23).
        self.setObjectName("LiveBottomBar")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setStyleSheet(
            f"QWidget#LiveBottomBar{{background:{CP['sidebar']};border-top:1px solid {CP['border']};}}"
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
                btn.setIcon(QIcon(_flag_pix))
                btn.setIconSize(QSize(22, 22))
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

        # ── Centre : items de navigation (séparateurs verticaux entre groupes).
        # Paramètres est extrait du groupe central : il vit en BAS À DROITE.
        self._items: dict[str, _LiveNavItem] = {}
        _settings_entry = None
        _pending_sep = False
        for entry in _NAV_ITEMS:
            if entry is None:
                _pending_sep = True
                continue
            icon, label, key, icon_file = entry
            if key == "settings":
                _settings_entry = entry
                continue
            if _pending_sep and self._items:
                lay.addSpacing(4)
                lay.addWidget(_vsep())
                lay.addSpacing(4)
            _pending_sep = False
            item = _LiveNavItem(icon, translate(label), key, icon_file=icon_file)
            item.nav_clicked.connect(self.nav_clicked)
            self._items[key] = item
            lay.addWidget(item)

        lay.addStretch()
        lay.addWidget(_vsep())
        lay.addSpacing(4)

        # ── Droite : Paramètres tout au bord ──────────────────────────────────
        # (Manuel d'utilisation et Nous contacter vivent dans la topbar, en
        # haut à gauche)
        if _settings_entry:
            icon, label, key, icon_file = _settings_entry
            lay.addSpacing(4)
            item = _LiveNavItem(icon, translate(label), key, icon_file=icon_file)
            item.nav_clicked.connect(self.nav_clicked)
            self._items[key] = item
            lay.addWidget(item)

    @staticmethod
    def _apply_lang_btn_style(btn: QPushButton, active: bool):
        bg = "rgba(124,107,255,0.18)" if active else "transparent"
        border = f"1px solid {CP['accent2']}" if active else "1px solid transparent"
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


# ── Fenêtre principale ────────────────────────────────────────────────────────

class LiveWindow(QMainWindow):
    """Fenêtre principale du mode PANDORA | Live."""
    closed           = pyqtSignal()
    switch_requested = pyqtSignal(dict)
    home_requested   = pyqtSignal()       # retour à la page de démarrage (logo)

    # nav key → clé de corpus de l'assistant
    _ASSIST_CTX = {
        "conducteur":  "live_conducteur",
        "casting":     "live_casting",
        "accessoires": "live_accessoires",
        "vehicules":   "live_vehicules",
        "seq_live":    "live_sequences",
        "seq_mapping": "live_seq_mapping",
        "studio":      "live_studio",
        "mapping":     "mapping",
        "resolume":    "resolume",
        "settings":    "live_settings",
    }

    def __init__(self, project: dict | None = None, is_secondary: bool = False):
        super().__init__()
        self._project = project or {}
        # Fenêtre secondaire (P5 « 2 écrans ») : copie du Live sur le même projet,
        # navigation indépendante ; NE relance PAS le check MAJ et se ferme seule.
        self._is_secondary = is_secondary
        self._secondary_wins: list = []

        # Contexte projet (si un projet Live est ouvert)
        try:
            import core.context as _ctx
            if self._project.get("id"):
                _ctx.set_project_id(self._project.get("id", ""))
                _ctx.set_project_path(self._project.get("_path", ""))
        except Exception:
            pass

        _name = self._project.get("name", "")
        _suffix = "   ·   Écran 2" if is_secondary else ""
        self.setWindowTitle(
            (f"PANDORA | Live — {_name}" if _name else "PANDORA | Live") + _suffix)
        self.setMinimumSize(1100, 720)
        self.setStyleSheet(PANDORA_STYLESHEET)

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

        self._sidebar = _LiveSidebar()   # barre de navigation BASSE (taskbar)
        # Disquette de sauvegarde dans la barre basse, à droite des drapeaux de
        # langue et de leur séparateur (index 4 du layout — demande 2026-07-23).
        self._sidebar.layout().insertWidget(4, self._btn_save_global)
        self._stack   = QStackedWidget()
        self._stack.setStyleSheet(f"background:{CP['bg0']};")

        from ui.live_pages import AssistantPanelLive
        # header_height=40 (2026-07-23) : la ligne sous l'en-tête GUIDE tombe
        # EXACTEMENT sur la ligne de la première rangée des pages (barres
        # d'outils Conducteur/Séquences à 40 px — parité Cinéma).
        self._assistant        = AssistantPanelLive(header_height=40)
        self._assistant.setVisible(False)   # assistant IA fermé par défaut
        self._assistant_toggle = AssistantToggleStrip(self._assistant, side="left")

        # Nav en BAS (façon DaVinci Resolve) : les pages récupèrent toute la
        # largeur de l'écran — plus de colonne latérale.
        # Assistant IA à GAUCHE (poignée au bord, panneau, puis les pages) ;
        # à DROITE, une colonne permanente de la largeur de la poignée fermée
        # — symétrie demandée (retour 2026-06-12).
        # À DROITE : Chat Storyboard (IA) en miroir de l'assistant — visible
        # uniquement sur les pages Séquences (porté du Cinéma). Ailleurs, un spacer
        # permanent de la largeur de la poignée préserve la symétrie.
        from ui.storyboard_chat import StoryboardChatPanel, StoryboardChatToggleStrip
        self._sb_chat_panel = StoryboardChatPanel(
            shots_provider=self._sb_chat_shots,
            on_applied=self._sb_chat_applied,
            header_height=40,   # aligné sur la barre d'outils des Séquences (2026-07-23)
        )
        self._sb_chat_panel.setVisible(False)
        self._sb_chat_toggle = StoryboardChatToggleStrip(self._sb_chat_panel)
        self._sb_chat_toggle.setVisible(False)

        self._right_spacer = QWidget()
        # même largeur que la poignée IA (fixée à 28 px) — symétrie exacte
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

        self._navigate("conducteur")

        _sc = QShortcut(QKeySequence("Ctrl+S"), self)
        _sc.activated.connect(self._on_global_save_click)

        from PyQt6.QtCore import QTimer
        if not self._is_secondary:
            QTimer.singleShot(900, self._start_update_check)

    def open_secondary_window(self):
        """P5 — ouvre une 2ᵉ fenêtre Live (même projet, navigation indépendante),
        placée sur le 2ᵉ écran s'il existe (ex. contrôleur d'un côté, mapping de
        l'autre). Appelée depuis Paramètres Live."""
        from PyQt6.QtWidgets import QApplication
        from PyQt6.QtCore import Qt
        win = LiveWindow(self._project, is_secondary=True)
        win.setWindowModality(Qt.WindowModality.NonModal)
        win.setWindowFlag(Qt.WindowType.Window, True)
        self._secondary_wins.append(win)
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
            win.move(self.x() + 60, self.y() + 60)
        win.show()
        win.raise_()
        win.activateWindow()
        return win

    def changeEvent(self, event):
        # P5 — au retour de focus, recharge la page visible (données fichier partagées
        # entre les 2 fenêtres) via _navigate (qui rétablit aussi le namespace storyboard).
        from PyQt6.QtCore import QEvent
        super().changeEvent(event)
        if event.type() == QEvent.Type.ActivationChange and self.isActiveWindow():
            key = getattr(self, "_current_nav", None)
            if key:
                try:
                    self._navigate(key)
                except Exception:
                    pass

    # ── Topbar globale (logo + Soutenir / Mises à jour / Sauvegarder) ────────────

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

        # ── Nous contacter (VERT) — le Manuel rejoint les Paramètres Live
        # (retrait topbar 2026-07-23, parité Cinéma) ───────────────────────────
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

        # ── Zone cliquable sous le logo : retour à la page de démarrage ───────
        # (le retour aux projets passe par ici depuis le retrait de l'onglet
        # « Projets » de la nav basse — 2026-07-23, parité Cinéma)
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

        # ── Couche 1 : logo PANDORA centré ────────────────────────────────────
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
            "QPushButton{background:transparent;color:#c8a400;"
            "border:1px solid rgba(200,164,0,0.35);"
            "border-radius:5px;font-size:10px;font-weight:700;padding:0 10px;}"
            "QPushButton:hover{background:rgba(245,197,24,0.10);color:#f5c518;"
            "border-color:rgba(245,197,24,0.60);}"
            "QPushButton:pressed{background:rgba(245,197,24,0.18);}"
        )
        btn_support.clicked.connect(self._on_funding)
        # « Soutenir Pandora » collé au bord droit du cadre (2026-07-23) : la
        # disquette a migré dans la barre basse, « Mises à jour » est retiré
        # (parité Cinéma) — plus de séparateur ici.
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
        # Insertion différée dans la barre basse (voir __init__).

        _lr_lay.addWidget(_right, 1)

        bar_lay.addWidget(_lr)
        bar_lay.addWidget(_center)
        bar_lay.setCurrentIndex(1)
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

    def _on_global_save(self):
        conducteur = self._pages.get("conducteur")
        if conducteur and hasattr(conducteur, "_save"):
            try:
                conducteur._save(silent=True)
            except Exception:
                pass

    def _on_funding(self):
        try:
            from ui.dialog_funding import FundingDialog
            FundingDialog(self).exec()
        except Exception as e:
            from PyQt6.QtWidgets import QMessageBox
            _msg = translate("Impossible d'ouvrir la fenêtre de soutien.")
            QMessageBox.warning(self, "PANDORA", f"{_msg}\n\n{e}")

    # ── Bannière + vérification de mise à jour ───────────────────────────────────

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

    def _start_update_check(self):
        try:
            from api.update_check import UpdateCheckWorker
            self._update_worker = UpdateCheckWorker()
            self._update_worker.update_available.connect(self._on_update_available)
            self._update_worker.no_update.connect(lambda: None)
            self._update_worker.check_failed.connect(lambda: None)
            self._update_worker.start()
        except Exception:
            pass

    def _manual_update_check(self):
        # Le bouton « Mises à jour » a quitté la topbar (2026-07-23, parité
        # Cinéma) — la méthode reste utilisable par un futur point d'entrée.
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

    # Largeur (retours 2026-06-12) : TOUTES les pages s'étirent jusqu'aux
    # bords — seul le Studio IA centre/plafonne le contenu de ses onglets
    # formulaire (voir LiveStudioWidget._clamp_content_width).

    def _build_pages(self):
        # Toutes les pages ci-dessous sont des VERSIONS LIVE INDÉPENDANTES
        # (sous-classes dédiées, voir ui/live_pages.py) → modifiables sans toucher Cinéma.
        from ui.live_pages import (
            ConducteurPage, SequenceLivePage, SequenceMappingPage,
            CastingLivePage, AccessoiresLivePage, VehiculesLivePage,
        )

        # « Projets » a quitté la nav basse (2026-07-23, parité Cinéma) : le
        # retour aux projets passe par le logo → page de démarrage.

        # ── Conducteur (version Live du Scénario) ───────────────────────────────
        # Page Projets (réintroduite 2026-07-23) — même page que le Cinéma ; le
        # switch recrée la fenêtre via main._on_switch.
        from ui.page_projects import PageProjects
        _projects = PageProjects(self._project)
        # Un projet sans champ « mode » reste dans l'édition courante (Live).
        _projects.switch_requested.connect(
            lambda d: self.switch_requested.emit({**d, "mode": d.get("mode", "live")}))
        self._pages["projects"] = _projects

        conducteur = ConducteurPage()
        conducteur.navigate_requested.connect(lambda key, extra=None: self._navigate(key))
        self._pages["conducteur"] = conducteur

        # ── Séquences Live + Mapping (versions Live du Storyboard) ──────────────
        self._pages["seq_live"]    = SequenceLivePage()
        self._pages["seq_mapping"] = SequenceMappingPage()
        # « ➤ SFX » d'un plan → Studio IA, onglet Sound Design pré-rempli
        for _sk in ("seq_live", "seq_mapping"):
            self._pages[_sk].sound_to_studio.connect(self._open_sound_design)

        # ── Casting / Accessoires / Véhicules (versions Live) ──────────────────
        self._pages["casting"]     = CastingLivePage()
        self._pages["accessoires"] = AccessoiresLivePage()
        self._pages["vehicules"]   = VehiculesLivePage()

        # ── Image IA — destination globale autonome (2026-07-23, parité
        # Cinéma) : réutilise le panneau partagé Studio Images ───────────────────
        from ui.tab_image import TabImage
        image_ia = TabImage()
        self._pages["image_ia"] = image_ia

        # ── Studio IA Live (dédié) ──────────────────────────────────────────────
        from ui.live_studio_widget import LiveStudioWidget
        studio = LiveStudioWidget()
        studio.open_resolume.connect(lambda: self._navigate("resolume"))
        self._pages["studio"] = studio

        # ── Contrôleur Resolume (réactivé — chantier 2026-06-11) ───────────────
        from ui.page_live import PageLive
        resolume = PageLive()
        self._pages["resolume"] = resolume
        # Vidéothèque « → Resolume » : la file de clips arrive pré-chargée
        studio.tab_library.send_to_resolume.connect(
            lambda paths: (resolume.queue_paths(paths), self._navigate("resolume")))

        from ui.page_live_settings import PageLiveSettings
        settings = PageLiveSettings()
        settings.manual_requested.connect(self._on_manual)
        self._pages["settings"] = settings
        # Paramètres pleine largeur (2026-07-23, parité Cinéma) : la barre de
        # défilement est collée au bord DROIT de la fenêtre ; le centrage du
        # contenu (max 1360) est géré À L'INTÉRIEUR de PageLiveSettings.
        self._settings_wrap = settings

        for key in ("projects", "conducteur", "seq_live", "seq_mapping", "casting",
                    "accessoires", "vehicules", "image_ia", "studio",
                    "resolume", "settings"):
            self._stack.addWidget(self._settings_wrap if key == "settings"
                                  else self._pages[key])

    # Les pages copiées de Cinéma émettent parfois les clés Cinéma → on les
    # ré-aiguille vers les clés Live correspondantes.
    _NAV_ALIASES = {
        "castings":   "casting",
        "vehicles":   "vehicules",
        "scenario":   "conducteur",
        "storyboard": "seq_live",
    }

    def _navigate(self, key: str):
        key = self._NAV_ALIASES.get(key, key)
        if key not in self._pages:
            return
        self._current_nav = key   # mémorisé pour le rafraîchissement au retour de focus
        page = self._pages[key]
        # Storyboard partagé : bascule le namespace selon la séquence (Live/Mapping),
        # ou revient au namespace par défaut "storyboard" pour les autres pages.
        import core.storyboard as _sb
        _live_ns = getattr(page, "_live_ns", None)
        _sb.set_namespace(_live_ns or "storyboard")
        # Rafraîchit TOUTE page qui le supporte (comme Cinéma) : indispensable pour
        # que casting / accessoires / véhicules / séquences affichent les éléments
        # générés depuis le Conducteur ou ajoutés manuellement.
        if hasattr(page, "refresh"):
            try:
                page.refresh()
            except Exception:
                pass
        self._stack.setCurrentWidget(self._settings_wrap if key == "settings" else page)
        self._sidebar.set_active(key)
        # Contexte de l'assistant
        ctx = self._ASSIST_CTX.get(key)
        if ctx and hasattr(self._assistant, "set_context"):
            self._assistant.set_context(ctx)
        self._update_sb_chat(key)

    # ── Chat Storyboard (IA, à droite) — porté du Cinéma ──────────────────────────

    def _sb_chat_shots(self) -> list:
        page = self._pages.get(getattr(self, "_current_nav", ""))
        return list(getattr(page, "_all_shots", []) or [])

    def _sb_chat_applied(self):
        page = self._pages.get(getattr(self, "_current_nav", ""))
        if page and hasattr(page, "_on_chat_applied"):
            page._on_chat_applied()

    def _update_sb_chat(self, key: str):
        """Le chat storyboard n'est actif que sur les pages Séquences ; ailleurs on
        rend le spacer pour garder la symétrie avec la poignée IA de gauche."""
        is_seq = key in ("seq_live", "seq_mapping")
        self._sb_chat_toggle.setVisible(is_seq)
        if not is_seq:
            self._sb_chat_panel.setVisible(False)
            self._sb_chat_toggle._open = False
            self._sb_chat_toggle._arrow.setText(self._sb_chat_toggle._arrow_char())
        # Le Studio IA (« studio ») et Image IA ont leur PROPRE poignée droite
        # (chat Image IA) : on masque le spacer sur ces pages pour que la poignée
        # « IA » soit COLLÉE au bord droit, comme « GUIDE » à gauche (retour
        # Matthieu 2026-07-05 ; « image_ia » ajouté 2026-07-23).
        # « conducteur » ajouté (2026-07-23) : sa poignée ASSISTANT est collée au
        # bord droit, comme Studio IA et Image IA (parité Cinéma).
        self._right_spacer.setVisible(not is_seq and key not in ("studio", "image_ia", "conducteur"))

    # ── Handlers ────────────────────────────────────────────────────────────────

    def _open_sound_design(self, prompt: str, duration: float):
        """« ➤ SFX » d'un plan de séquence → Studio IA, onglet Sound Design pré-rempli."""
        self._navigate("studio")
        studio = self._pages.get("studio")
        if studio and hasattr(studio, "open_sound_design"):
            studio.open_sound_design(prompt, duration)

    def _on_manual(self):
        from ui.live_pages import UserManualDialogLive
        UserManualDialogLive(self).exec()

    def _on_contact(self):
        from ui.live_pages import ContactDialogLive
        ContactDialogLive(self).exec()

    def _on_lang_change(self, new_lang: str):
        if new_lang == get_lang():
            return
        set_lang(new_lang)
        self._sidebar.set_lang_active(new_lang)
        retranslate_widget(self)
        # Pages avec retranslate personnalisé (textes construits depuis des données)
        for page in self._pages.values():
            if hasattr(page, "retranslate"):
                page.retranslate()

    def closeEvent(self, e):
        # Fenêtre secondaire (P5) : se ferme seule, sans émettre `closed`
        # (qui gère la fermeture globale / retour au sélecteur côté fenêtre principale).
        if getattr(self, "_is_secondary", False):
            e.accept()
            return
        # Confirmation de fermeture PARTAGÉE avec le Cinéma (demande de sauvegarde).
        from ui.quit_dialog import confirm_quit
        result = confirm_quit(self)
        if result == 0:          # Annuler → rester ouvert
            e.ignore()
            return
        if result == 1:          # Sauvegarder et quitter
            try:
                self._on_global_save()
            except Exception:
                pass
        self.closed.emit()
        e.accept()
