"""
live_window.py — Fenêtre PANDORA | Live (performance live / VJ / mapping).

Même agencement que PandoraWindow (Cinéma) :
  sélecteur de langue + sidebar de navigation + stack de pages + panneau assistant.

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
from PyQt6.QtGui import QIcon

from ui.styles import CP, PANDORA_STYLESHEET
from ui.icons import app_icon, load_icon
from ui.assistant_panel import AssistantPanel, AssistantToggleStrip
from core.i18n import get_lang, set_lang, retranslate_widget, translate


# ── Item de navigation Live ───────────────────────────────────────────────────

class _LiveNavItem(QWidget):
    nav_clicked = pyqtSignal(str)

    def __init__(self, icon: str, label: str, key: str):
        super().__init__()
        self._key    = key
        self._active = False
        self.setFixedHeight(54)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        outer = QHBoxLayout(self)
        outer.setContentsMargins(10, 3, 8, 3)
        outer.setSpacing(10)
        outer.setAlignment(Qt.AlignmentFlag.AlignVCenter)

        self._ico = QLabel(icon)
        self._ico.setFixedSize(30, 30)
        self._ico.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._ico.setStyleSheet("background:transparent;border:none;font-size:16px;")

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
        accent = CP["accent2"]
        if active:
            self._frame.setStyleSheet(
                f"QFrame{{background:rgba(124,107,255,0.18);"
                f"border:1px solid rgba(124,107,255,0.32);border-radius:8px;}}"
            )
            self._ico.setStyleSheet(
                f"color:{accent};font-size:16px;background:transparent;border:none;"
            )
            self._lbl.setStyleSheet(
                f"color:{accent};font-size:16px;font-weight:700;"
                f"letter-spacing:0.4px;background:transparent;border:none;"
            )
        else:
            self._frame.setStyleSheet(
                "QFrame{background:transparent;border:none;border-radius:8px;}"
            )
            self._ico.setStyleSheet(
                f"color:{CP['text_dim']};font-size:16px;background:transparent;border:none;"
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


# ── Sidebar Live ──────────────────────────────────────────────────────────────

# (icône emoji, libellé FR, clé)
_NAV_ITEMS = [
    ("✦", "Studio IA",  "studio"),
    ("▤", "Séquences",  "sequences"),
    ("◳", "Mapping",    "mapping"),
    ("▦", "Resolume",   "resolume"),
    None,
    ("⚙", "Paramètres", "settings"),
]


class _LiveSidebar(QWidget):
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

        # ── En-tête : badge + sélecteur de langue ─────────────────────────────
        header = QWidget()
        header.setFixedHeight(76)
        header.setStyleSheet(
            f"background:{CP['bg1']};border:none;border-bottom:1px solid {CP['border']};"
        )
        hl = QHBoxLayout(header)
        hl.setContentsMargins(14, 0, 14, 0)
        hl.setSpacing(10)

        badge = QLabel("◈")
        badge.setFixedSize(38, 38)
        badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        badge.setStyleSheet(
            f"background:qlineargradient(x1:0,y1:0,x2:1,y2:1,"
            f"stop:0 {CP['accent2']},stop:1 #a060ff);"
            f"border-radius:10px;color:#fff;font-size:18px;font-weight:900;border:none;"
        )
        hl.addWidget(badge)

        title_col = QVBoxLayout()
        title_col.setSpacing(1)
        t1 = QLabel("PANDORA")
        t1.setStyleSheet(
            f"color:{CP['text_primary']};font-size:13px;font-weight:800;"
            f"letter-spacing:2px;background:transparent;border:none;"
        )
        t2 = QLabel("| Live")
        t2.setStyleSheet(
            f"color:{CP['accent2']};font-size:11px;font-weight:700;"
            f"letter-spacing:1px;background:transparent;border:none;"
        )
        title_col.addWidget(t1)
        title_col.addWidget(t2)
        hl.addLayout(title_col, 1)

        self._lang_btns: dict[str, QPushButton] = {}
        _flag_map = {"fr": "Fr.png", "en": "En.png"}
        _cur_lang = get_lang()
        for code, flag_file in _flag_map.items():
            btn = QPushButton()
            btn.setFixedSize(30, 30)
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
            hl.addWidget(btn)
            self._lang_btns[code] = btn

        lay.addWidget(header)
        lay.addSpacing(6)

        # ── Items de navigation ───────────────────────────────────────────────
        self._items: dict[str, _LiveNavItem] = {}
        for entry in _NAV_ITEMS:
            if entry is None:
                lay.addStretch()
                sep = QFrame()
                sep.setFixedHeight(1)
                sep.setStyleSheet(f"background:{CP['border']};margin:0 12px;")
                lay.addWidget(sep)
                lay.addSpacing(4)
                continue
            icon, label, key = entry
            item = _LiveNavItem(icon, translate(label), key)
            item.nav_clicked.connect(self.nav_clicked)
            self._items[key] = item
            lay.addWidget(item)

        lay.addSpacing(4)

        # ── Boutons bas : Manuel / Contact ────────────────────────────────────
        _sep_bottom = QFrame()
        _sep_bottom.setFixedHeight(1)
        _sep_bottom.setStyleSheet(f"background:{CP['border']};margin:0 12px;")
        lay.addWidget(_sep_bottom)

        _ss_yellow = (
            "QPushButton{background:transparent;color:#c8a400;"
            "border:1px solid rgba(200,164,0,0.35);border-radius:6px;"
            "font-size:10px;font-weight:700;text-align:left;padding:0 14px;}"
            "QPushButton:hover{background:rgba(245,197,24,0.10);color:#f5c518;"
            "border-color:rgba(245,197,24,0.60);}"
            "QPushButton:pressed{background:rgba(245,197,24,0.18);}"
        )

        self._btn_manual = QPushButton("☰  " + translate("Manuel d'utilisation"))
        self._btn_manual.setFixedHeight(34)
        self._btn_manual.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_manual.setStyleSheet(_ss_yellow)
        self._btn_manual.clicked.connect(self.manual_requested.emit)
        lay.addWidget(self._btn_manual)

        lay.addSpacing(6)

        self._btn_contact = QPushButton("✉  " + translate("Nous contacter"))
        self._btn_contact.setFixedHeight(34)
        self._btn_contact.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_contact.setStyleSheet(_ss_yellow)
        self._btn_contact.clicked.connect(self.contact_requested.emit)
        lay.addWidget(self._btn_contact)

        lay.addSpacing(6)

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
        "studio":    "live_studio",
        "sequences": "live_sequences",
        "mapping":   "mapping",
        "resolume":  "resolume",
        "settings":  "live_settings",
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

        body = QWidget()
        body.setStyleSheet("background:transparent;")
        body_lay = QHBoxLayout(body)
        body_lay.setContentsMargins(0, 0, 0, 0)
        body_lay.setSpacing(0)

        self._sidebar = _LiveSidebar()
        self._stack   = QStackedWidget()
        self._stack.setStyleSheet(f"background:{CP['bg0']};")

        self._assistant        = AssistantPanel()
        self._assistant.setVisible(True)
        self._assistant_toggle = AssistantToggleStrip(self._assistant)

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

        self._navigate("studio")

    def _build_pages(self):
        # Studio IA Live (dédié) — Génération directe (+ styles VJ), Générer depuis
        # Séquences (placeholder), Vidéothèque, Historique. Pas de DaVinci.
        # TODO : mode loop Resolume (première image = dernière).
        from ui.live_studio_widget import LiveStudioWidget
        studio = LiveStudioWidget()
        studio.open_resolume.connect(lambda: self._navigate("resolume"))
        self._pages["studio"] = studio

        from ui.page_live_sequences import PageLiveSequences
        self._pages["sequences"] = PageLiveSequences()

        from ui.page_mapping import PageMapping
        self._pages["mapping"] = PageMapping()

        # Page Resolume existante — conservée dans un onglet (évaluation)
        from ui.page_live import PageLive
        self._pages["resolume"] = PageLive()

        from ui.page_live_settings import PageLiveSettings
        self._pages["settings"] = PageLiveSettings()

        for key in ("studio", "sequences", "mapping", "resolume", "settings"):
            self._stack.addWidget(self._pages[key])

    def _navigate(self, key: str):
        if key not in self._pages:
            return
        self._stack.setCurrentWidget(self._pages[key])
        self._sidebar.set_active(key)
        # Contexte de l'assistant
        ctx = self._ASSIST_CTX.get(key)
        if ctx and hasattr(self._assistant, "set_context"):
            self._assistant.set_context(ctx)

    # ── Handlers ────────────────────────────────────────────────────────────────

    def _on_manual(self):
        from ui.dialog_user_manual import UserManualDialog
        UserManualDialog(self).exec()

    def _on_contact(self):
        from ui.dialog_contact import ContactDialog
        ContactDialog(self).exec()

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
