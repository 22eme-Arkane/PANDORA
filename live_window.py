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
    QLabel, QStackedWidget, QFrame, QPushButton,
)
from PyQt6.QtCore import Qt, pyqtSignal, QSize
from PyQt6.QtGui import QIcon, QShortcut, QKeySequence

from ui.styles import CP, PANDORA_STYLESHEET
from ui.icons import app_icon, load_icon
from ui.assistant_panel import AssistantPanel, AssistantToggleStrip
from core.i18n import get_lang, set_lang, retranslate_widget, translate, tr


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
        self._use_png = False
        self._pix_on = self._pix_off = None
        if icon_file:
            from ui.icons import dim
            _pix = load_icon(icon_file, 24)
            if not _pix.isNull():
                self._use_png = True
                self._pix_on  = _pix
                self._pix_off = dim(_pix, 0.55)

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
        accent = CP["accent2"]
        if active:
            self._bg("background:rgba(124,107,255,0.16);"
                     "border:1px solid rgba(124,107,255,0.30);")
            if self._use_png:
                self._ico.setPixmap(self._pix_on)
            else:
                self._ico.setStyleSheet(
                    f"color:{accent};font-size:14px;background:transparent;border:none;"
                )
            self._lbl.setStyleSheet(
                f"color:{accent};font-size:10px;font-weight:700;"
                f"letter-spacing:0.3px;background:transparent;border:none;"
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
            self._bg("background:rgba(255,255,255,0.05);"
                     "border:1px solid rgba(255,255,255,0.08);")
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
_NAV_ITEMS = [
    ("⊞", "Projets",             "projects",    "projets.png"),
    None,
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
        self.setStyleSheet(
            f"background:{CP['sidebar']};border-top:1px solid {CP['border']};"
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

    def __init__(self, project: dict | None = None):
        super().__init__()
        self._project = project or {}

        # Contexte projet (si un projet Live est ouvert)
        try:
            import core.context as _ctx
            if self._project.get("id"):
                _ctx.set_project_id(self._project.get("id", ""))
                _ctx.set_project_path(self._project.get("_path", ""))
        except Exception:
            pass

        _name = self._project.get("name", "")
        self.setWindowTitle(f"PANDORA | Live — {_name}" if _name else "PANDORA | Live")
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
        self._stack   = QStackedWidget()
        self._stack.setStyleSheet(f"background:{CP['bg0']};")

        from ui.live_pages import AssistantPanelLive
        self._assistant        = AssistantPanelLive()
        self._assistant.setVisible(False)   # assistant IA fermé par défaut
        self._assistant_toggle = AssistantToggleStrip(self._assistant, side="left")

        # Nav en BAS (façon DaVinci Resolve) : les pages récupèrent toute la
        # largeur de l'écran — plus de colonne latérale.
        # Assistant IA à GAUCHE (poignée au bord, panneau, puis les pages) ;
        # à DROITE, une colonne permanente de la largeur de la poignée fermée
        # — symétrie demandée (retour 2026-06-12).
        self._right_spacer = QWidget()
        # même largeur que la poignée IA (fixée à 28 px) — symétrie exacte
        self._right_spacer.setFixedWidth(self._assistant_toggle.maximumWidth())
        self._right_spacer.setStyleSheet(f"background:{CP['bg1']};")
        body_lay.addWidget(self._assistant_toggle)
        body_lay.addWidget(self._assistant)
        body_lay.addWidget(self._stack, 1)
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
        QTimer.singleShot(900, self._start_update_check)

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

        # ── Manuel + Nous contacter — en haut à gauche (demandes 2026-06-12) ──
        _ss_yellow_top = (
            "QPushButton{background:transparent;color:#c8a400;"
            "border:1px solid rgba(200,164,0,0.35);border-radius:5px;"
            "font-size:10px;font-weight:700;padding:0 10px;}"
            "QPushButton:hover{background:rgba(245,197,24,0.10);color:#f5c518;"
            "border-color:rgba(245,197,24,0.60);}"
            "QPushButton:pressed{background:rgba(245,197,24,0.18);}"
        )
        self._btn_manual_top = QPushButton("☰  " + translate("Manuel d'utilisation"))
        self._btn_manual_top.clicked.connect(self._on_manual)
        self._btn_contact_top = QPushButton("✉  " + translate("Nous contacter"))
        self._btn_contact_top.clicked.connect(self._on_contact)
        for _b in (self._btn_manual_top, self._btn_contact_top):
            _b.setFixedHeight(26)
            _b.setCursor(Qt.CursorShape.PointingHandCursor)
            _b.setStyleSheet(_ss_yellow_top)
            _llay.addWidget(_b)
            _llay.addSpacing(6)

        _lr_lay.addWidget(_left, 1)

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

        bar_lay.addWidget(_lr)
        bar_lay.addWidget(_center)
        bar_lay.setCurrentIndex(1)
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

    # Largeur de lecture commune à toutes les pages formulaire (retour
    # 2026-06-12 : en plein écran, boutons/encadrés étirés jusqu'aux bords =
    # illisible). Même valeur que les onglets du Studio IA.
    _PAGE_MAX_W = 1360
    # Pages dont la largeur est FONCTIONNELLE — jamais plafonnées : tableaux,
    # contrôleur, Studio (gère ses onglets lui-même) ; et (retour 2026-06-12)
    # Conducteur/Casting/Accessoires/Véhicules prennent TOUTE la fenêtre — le
    # panneau droit du Conducteur (Références/IA/Générer) reste collé au bord
    # droit, comme la poignée du menu IA.
    _FULL_WIDTH_PAGES = {"seq_live", "seq_mapping", "resolume", "studio",
                         "conducteur", "casting", "accessoires", "vehicules"}

    def _clamp_wrap(self, page: QWidget) -> QWidget:
        """Centre la page dans un conteneur : elle s'étend jusqu'à _PAGE_MAX_W,
        le fond remplit les côtés."""
        page.setMaximumWidth(self._PAGE_MAX_W)
        wrap = QWidget()
        wrap.setStyleSheet(f"background:{CP['bg0']};")
        hl = QHBoxLayout(wrap)
        hl.setContentsMargins(0, 0, 0, 0)
        hl.setSpacing(0)
        hl.addStretch(1)
        hl.addWidget(page, 4)
        hl.addStretch(1)
        return wrap

    def _build_pages(self):
        # Toutes les pages ci-dessous sont des VERSIONS LIVE INDÉPENDANTES
        # (sous-classes dédiées, voir ui/live_pages.py) → modifiables sans toucher Cinéma.
        from ui.live_pages import (
            ProjetsLivePage, ConducteurPage, SequenceLivePage, SequenceMappingPage,
            CastingLivePage, AccessoiresLivePage, VehiculesLivePage,
        )

        # ── Projets ─────────────────────────────────────────────────────────────
        projects = ProjetsLivePage(self._project)
        projects.switch_requested.connect(self.switch_requested)
        self._pages["projects"] = projects

        # ── Conducteur (version Live du Scénario) ───────────────────────────────
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
        self._pages["settings"] = PageLiveSettings()

        self._stack_widgets: dict[str, QWidget] = {}
        for key in ("projects", "conducteur", "seq_live", "seq_mapping", "casting",
                    "accessoires", "vehicules", "studio", "resolume", "settings"):
            page = self._pages[key]
            w = page if key in self._FULL_WIDTH_PAGES else self._clamp_wrap(page)
            self._stack_widgets[key] = w
            self._stack.addWidget(w)

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
        # Le stack contient le conteneur centré (pages plafonnées) ou la page brute
        self._stack.setCurrentWidget(self._stack_widgets.get(key, page))
        self._sidebar.set_active(key)
        # Contexte de l'assistant
        ctx = self._ASSIST_CTX.get(key)
        if ctx and hasattr(self._assistant, "set_context"):
            self._assistant.set_context(ctx)

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
        self.closed.emit()
        e.accept()
