import os
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTextEdit, QLineEdit, QFrame, QScrollArea, QFileDialog,
    QMessageBox, QStackedWidget, QApplication, QProgressBar, QSpinBox,
    QComboBox, QSlider, QCheckBox, QInputDialog,
)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QPixmap, QFont, QColor
from ui.styles import CP
from ui.widgets import HelpBlock
import core.scenario as scenario_api
from ui.icons import load_icon, claude_icon_pixmap, install_hover_icon


_INTENSITY_LEGEND = [
    ("1",    "Orthographe & ponctuation uniquement"),
    ("2",    "Corrections légères de formulation"),
    ("3",    "Resserrement du rythme"),
    ("4",    "Restructuration douce de paragraphes"),
    ("5",    "Reformulation standard — ton amélioré"),
    ("6",    "Cohérence narrative & dialogues"),
    ("7",    "Refonte de séquences"),
    ("8",    "Développement ou coupe de scènes"),
    ("9",    "Réécriture forte — structure modifiée"),
    ("10",   "Réécriture radicale — scènes retravaillées"),
]

def _intensity_label(v: int) -> str:
    if v <= 2:   return "Léger — corrections orthographiques et de forme"
    if v <= 4:   return "Modéré — restructuration douce, rythme"
    if v <= 6:   return "Standard — reformulation, cohérence, dialogues"
    if v <= 8:   return "Fort — refonte de séquences et de scènes"
    return           "Radical — réécriture complète du scénario"




def _sep():
    f = QFrame()
    f.setFixedHeight(1)
    f.setStyleSheet(f"background:{CP['border']};")
    return f


# ── Page Scénario (landing + éditeur) ────────────────────────────────────────

class PageScenario(QWidget):
    navigate_requested = pyqtSignal(str, str)  # (page_key, extra_arg)
    style_changed      = pyqtSignal(str)        # style key — propagate to all pages

    def __init__(self):
        super().__init__()
        self.setStyleSheet(f"background:{CP['bg0']};")
        self._current: dict | None = None   # scenario data being edited
        self._worker = None
        self._last_storyboard_version_id = ""
        self._undo_stack: list[str] = []
        self._redo_stack: list[str] = []
        self._last_analysis: str = ""
        self._last_format_result: str = ""
        self._last_result_kind: str = ""   # "format" | "arrange"
        self._autosave_timer = QTimer()
        self._autosave_timer.setSingleShot(True)
        self._autosave_timer.setInterval(3000)
        self._autosave_timer.timeout.connect(self._autosave)

        self._stack = QStackedWidget()
        self._stack.setStyleSheet(f"background:{CP['bg0']};")

        self._landing = self._build_landing()
        self._editor  = self._build_editor()
        self._stack.addWidget(self._landing)   # index 0
        self._stack.addWidget(self._editor)    # index 1

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        root.addWidget(self._stack)

    # ── Landing ───────────────────────────────────────────────────────────────

    def _build_landing(self):
        w = QWidget()
        w.setStyleSheet(f"background:{CP['bg0']};")

        outer = QVBoxLayout(w)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # Top bar
        topbar = QWidget()
        topbar.setFixedHeight(60)
        topbar.setStyleSheet(f"background:{CP['bg1']};")
        tl = QHBoxLayout(topbar)
        tl.setContentsMargins(32, 0, 32, 0)
        tl.setSpacing(10)

        _ico = QLabel()
        _ico.setFixedSize(28, 28)
        _ico.setAlignment(Qt.AlignmentFlag.AlignCenter)
        _ico.setStyleSheet("background:transparent;")
        _ico_pix = load_icon("scenario.png", 28)
        if not _ico_pix.isNull():
            _ico.setPixmap(_ico_pix)
        tl.addWidget(_ico)

        title_lbl = QLabel("Scénario")
        title_lbl.setStyleSheet(
            f"color:{CP['text_primary']};font-size:22px;font-weight:700;background:transparent;"
        )
        tl.addWidget(title_lbl)
        tl.addStretch()
        outer.addWidget(topbar)
        outer.addWidget(_sep())

        # Scroll content
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea{background:transparent;border:none;}")

        content = QWidget()
        content.setStyleSheet("background:transparent;")
        lay = QVBoxLayout(content)
        lay.setContentsMargins(56, 48, 56, 48)
        lay.setSpacing(32)

        lay.addWidget(HelpBlock("Scénario — Éditeur et assistant Claude IA", [
            "▸ Rédigez ou collez votre scénario, puis utilisez Claude pour le formater en mise en page cinéma standard.",
            "▸ Arrangement IA : Claude analyse la structure narrative et propose des améliorations (intensité réglable 1-10).",
            "▸ Générez automatiquement depuis le scénario : personnages, décors, accessoires, HMC, véhicules et storyboard.",
            "▸ Versions : sauvegardez plusieurs versions nommées et basculez entre elles à tout moment.",
            "▸ Undo/Redo : chaque modification par Claude est annulable — les boutons ↩ ↪ conservent l'historique manuel.",
            "▸ Style de film : le style sélectionné ici se propage à Seedance 2.0 et aux générations d'éléments.",
        ], CP))

        # Hero actions
        hero = QHBoxLayout()
        hero.setSpacing(20)

        def _action_card(icon, title, sub, color, callback):
            card = QWidget()
            card.setFixedSize(240, 140)
            card.setCursor(Qt.CursorShape.PointingHandCursor)
            card.setStyleSheet(
                f"QWidget{{background:{CP['bg2']};border:1px solid {CP['border']};"
                f"border-radius:14px;}}"
                f"QWidget:hover{{border-color:{color};background:{CP['bg3']};}}"
            )
            cl = QVBoxLayout(card)
            cl.setContentsMargins(22, 20, 22, 20)
            cl.setSpacing(8)
            ico = QLabel(icon)
            ico.setStyleSheet(f"font-size:28px;background:transparent;border:none;")
            t = QLabel(title)
            t.setStyleSheet(
                f"color:{CP['text_primary']};font-size:14px;font-weight:700;"
                f"background:transparent;border:none;"
            )
            s = QLabel(sub)
            s.setWordWrap(True)
            s.setStyleSheet(
                f"color:{CP['text_dim']};font-size:10px;"
                f"background:transparent;border:none;"
            )
            cl.addWidget(ico)
            cl.addWidget(t)
            cl.addWidget(s)
            card.mousePressEvent = lambda e, cb=callback: cb()
            return card

        hero.addWidget(_action_card(
            "✦", "Nouveau scénario", "Écrire depuis zéro",
            CP["accent"], self._new_scenario,
        ))
        hero.addWidget(_action_card(
            "⇪", "Importer un fichier", ".txt / .docx / .pdf",
            CP["accent2"], self._import_scenario,
        ))
        hero.addStretch()
        lay.addLayout(hero)

        # Recent scenarios
        sep2 = QFrame()
        sep2.setFixedHeight(1)
        sep2.setStyleSheet(f"background:{CP['border']};")
        lay.addWidget(sep2)

        lbl_recent = QLabel("Scénarios récents")
        lbl_recent.setStyleSheet(
            f"color:{CP['text_secondary']};font-size:12px;font-weight:700;"
            f"letter-spacing:0.5px;background:transparent;"
        )
        lay.addWidget(lbl_recent)

        self._recent_container = QWidget()
        self._recent_container.setStyleSheet("background:transparent;")
        self._recent_lay = QVBoxLayout(self._recent_container)
        self._recent_lay.setContentsMargins(0, 0, 0, 0)
        self._recent_lay.setSpacing(8)
        lay.addWidget(self._recent_container)
        lay.addStretch()

        scroll.setWidget(content)
        outer.addWidget(scroll, 1)
        return w

    def _refresh_recent(self):
        while self._recent_lay.count():
            item = self._recent_lay.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        scenarios = scenario_api.list_scenarios()
        if not scenarios:
            lbl = QLabel("Aucun scénario récent.")
            lbl.setStyleSheet(
                f"color:{CP['text_dim']};font-size:12px;background:transparent;"
            )
            self._recent_lay.addWidget(lbl)
            return

        for sc in scenarios[:10]:
            self._recent_lay.addWidget(self._make_recent_card(sc))

    def _make_recent_card(self, sc: dict) -> QWidget:
        card = QWidget()
        card.setFixedHeight(64)
        card.setCursor(Qt.CursorShape.PointingHandCursor)
        card.setStyleSheet(
            f"QWidget{{background:{CP['bg2']};border:1px solid {CP['border']};"
            f"border-radius:10px;}}"
            f"QWidget:hover{{border-color:{CP['border_bright']};background:{CP['bg3']};}}"
        )
        cl = QHBoxLayout(card)
        cl.setContentsMargins(16, 0, 16, 0)
        cl.setSpacing(16)

        icon = QLabel("≡")
        icon.setFixedSize(32, 32)
        icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon.setStyleSheet(
            f"color:{CP['accent2']};font-size:18px;background:rgba(124,107,255,0.12);"
            f"border:1px solid {CP['accent2_dim']};border-radius:8px;"
        )
        cl.addWidget(icon)

        info = QVBoxLayout()
        info.setSpacing(2)
        title_lbl = QLabel(sc.get("title") or "Scénario sans titre")
        title_lbl.setStyleSheet(
            f"color:{CP['text_primary']};font-size:12px;font-weight:700;background:transparent;border:none;"
        )
        updated = sc.get("updated_at", sc.get("created_at", ""))[:10]
        sub_lbl = QLabel(f"Modifié le {updated}" if updated else "")
        sub_lbl.setStyleSheet(
            f"color:{CP['text_dim']};font-size:10px;font-family:'Consolas',monospace;"
            f"background:transparent;border:none;"
        )
        info.addWidget(title_lbl)
        info.addWidget(sub_lbl)
        cl.addLayout(info, 1)

        btn_del = QPushButton("✕")
        btn_del.setFixedSize(28, 28)
        btn_del.setStyleSheet(
            f"QPushButton{{background:transparent;color:{CP['text_dim']};border:none;"
            f"border-radius:4px;font-size:13px;font-weight:700;}}"
            f"QPushButton:hover{{color:{CP['red']};background:rgba(255,79,106,0.1);}}"
        )
        sc_id = sc.get("id", "")
        btn_del.clicked.connect(lambda checked=False, sid=sc_id: self._delete_scenario(sid))
        cl.addWidget(btn_del)

        card.mousePressEvent = lambda e, s=sc: self._open_scenario(s)
        return card

    # ── Editor ────────────────────────────────────────────────────────────────

    def _build_editor(self):
        w = QWidget()
        w.setStyleSheet(f"background:{CP['bg0']};")

        outer = QVBoxLayout(w)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # Top bar
        topbar = QWidget()
        topbar.setFixedHeight(56)
        topbar.setStyleSheet(f"background:{CP['bg1']};")
        tl = QHBoxLayout(topbar)
        tl.setContentsMargins(16, 0, 16, 0)
        tl.setSpacing(12)

        btn_back = QPushButton("← Retour")
        btn_back.setFixedHeight(34)
        btn_back.setStyleSheet(
            f"QPushButton{{background:transparent;color:{CP['text_secondary']};"
            f"border:1px solid {CP['border']};border-radius:6px;font-size:11px;font-weight:700;padding:0 12px;}}"
            f"QPushButton:hover{{background:{CP['bg2']};color:{CP['text_primary']};}}"
        )
        btn_back.clicked.connect(self._go_landing)
        tl.addWidget(btn_back)

        _undo_redo_ss = (
            f"QPushButton{{background:transparent;color:{CP['text_dim']};"
            f"border:1px solid {CP['border']};border-radius:6px;"
            f"font-size:13px;font-weight:700;padding:0 10px;}}"
            f"QPushButton:hover:enabled{{background:{CP['bg2']};color:{CP['text_primary']};"
            f"border-color:{CP['border_bright']};}}"
            f"QPushButton:disabled{{color:{CP['bg3']};border-color:{CP['bg3']};}}"
        )
        self._btn_undo = QPushButton("↩")
        self._btn_undo.setFixedSize(34, 34)
        self._btn_undo.setToolTip("Annuler (Ctrl+Z)")
        self._btn_undo.setEnabled(False)
        self._btn_undo.setStyleSheet(_undo_redo_ss)
        self._btn_undo.clicked.connect(self._on_undo)
        tl.addWidget(self._btn_undo)

        self._btn_redo = QPushButton("↪")
        self._btn_redo.setFixedSize(34, 34)
        self._btn_redo.setToolTip("Rétablir (Ctrl+Y)")
        self._btn_redo.setEnabled(False)
        self._btn_redo.setStyleSheet(_undo_redo_ss)
        self._btn_redo.clicked.connect(self._on_redo)
        tl.addWidget(self._btn_redo)

        self._title_edit = QLineEdit()
        self._title_edit.setPlaceholderText("Titre du scénario…")
        self._title_edit.setFixedHeight(34)
        self._title_edit.setFixedWidth(160)
        self._title_edit.setStyleSheet(
            f"QLineEdit{{background:{CP['bg2']};border:1px solid {CP['border']};"
            f"border-radius:6px;color:{CP['text_primary']};font-size:13px;font-weight:600;padding:0 12px;}}"
            f"QLineEdit:focus{{border-color:{CP['accent2_dim']};}}"
        )
        self._title_edit.textChanged.connect(self._schedule_autosave)
        self._title_edit.textChanged.connect(self._adjust_title_width)
        tl.addWidget(self._title_edit)

        # ── Versions (top bar, juste à droite du titre) ───────────────────────
        _ver_sep = QFrame()
        _ver_sep.setFixedSize(1, 24)
        _ver_sep.setStyleSheet(f"background:{CP['border']};")
        tl.addWidget(_ver_sep)

        self._version_combo = QComboBox()
        self._version_combo.setFixedHeight(30)
        self._version_combo.setMinimumWidth(150)
        self._version_combo.setMaximumWidth(200)
        self._version_combo.setPlaceholderText("Versions…")
        self._version_combo.setStyleSheet(
            f"QComboBox{{background:{CP['bg2']};border:1px solid {CP['border']};"
            f"border-radius:6px;color:{CP['text_secondary']};font-size:10px;padding:0 8px;}}"
            f"QComboBox:focus{{border-color:{CP['accent2_dim']};}}"
            f"QComboBox::drop-down{{border:none;width:16px;}}"
            f"QComboBox::down-arrow{{image:none;border-left:4px solid transparent;"
            f"border-right:4px solid transparent;border-top:5px solid {CP['text_dim']};"
            f"margin-right:4px;}}"
            f"QComboBox QAbstractItemView{{background:{CP['bg2']};border:1px solid {CP['border_bright']};"
            f"selection-background-color:{CP['accent2_dim']};color:{CP['text_primary']};"
            f"font-size:10px;padding:4px;}}"
        )
        self._version_combo.currentIndexChanged.connect(self._on_version_selected)
        self._version_combo.activated.connect(self._on_version_activated)
        tl.addWidget(self._version_combo)

        _ver_btn_ss = (
            f"QPushButton{{background:transparent;color:{CP['text_dim']};"
            f"border:1px solid {CP['border']};border-radius:6px;"
            f"font-size:11px;font-weight:700;padding:0 8px;}}"
            f"QPushButton:hover:enabled{{background:{CP['bg2']};color:{CP['text_primary']};"
            f"border-color:{CP['border_bright']};}}"
            f"QPushButton:disabled{{color:{CP['bg3']};border-color:{CP['bg3']};}}"
        )
        self._btn_save_version = QPushButton("✚")
        self._btn_save_version.setFixedSize(30, 30)
        self._btn_save_version.setToolTip("Sauvegarder une version")
        self._btn_save_version.setStyleSheet(_ver_btn_ss)
        self._btn_save_version.clicked.connect(self._save_version)
        tl.addWidget(self._btn_save_version)

        # ⤓ button removed — selecting from the combo now loads the version directly

        self._btn_del_version = QPushButton("✕")
        self._btn_del_version.setFixedSize(30, 30)
        self._btn_del_version.setToolTip("Supprimer la version sélectionnée")
        self._btn_del_version.setEnabled(False)
        self._btn_del_version.setStyleSheet(
            _ver_btn_ss
            + f"QPushButton:hover:enabled{{color:{CP['red']};border-color:{CP['red']};"
            f"background:rgba(255,79,106,0.1);}}"
        )
        self._btn_del_version.clicked.connect(self._delete_version)
        tl.addWidget(self._btn_del_version)
        tl.addStretch(1)

        _ver_sep2 = QFrame()
        _ver_sep2.setFixedSize(1, 24)
        _ver_sep2.setStyleSheet(f"background:{CP['border']};")
        tl.addWidget(_ver_sep2)

        self._save_indicator = QLabel("")
        self._save_indicator.setFixedWidth(80)
        self._save_indicator.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self._save_indicator.setStyleSheet(
            f"color:{CP['text_dim']};font-size:10px;font-family:'Consolas',monospace;background:transparent;"
        )
        tl.addWidget(self._save_indicator)


        outer.addWidget(topbar)
        outer.addWidget(_sep())
        outer.addWidget(self._build_film_strip())

        # Main area
        main = QHBoxLayout()
        main.setContentsMargins(0, 0, 0, 0)
        main.setSpacing(0)

        # Text editor — page de scénario pleine largeur avec marges latérales
        self._editor_text = QTextEdit()
        self._editor_text.setPlaceholderText(
            "Écris ton scénario ici…\n\n"
            "INT. LIEU — JOUR\n\n"
            "Description de la scène…\n\n"
            "PERSONNAGE\n"
            "Dialogue du personnage."
        )
        _tw_font = QFont("Courier New", 14)
        _tw_font.setStyleHint(QFont.StyleHint.TypeWriter)
        self._editor_text.setFont(_tw_font)
        self._editor_text.setStyleSheet(
            f"QTextEdit{{background:{CP['bg0']};border:none;"
            f"color:{CP['text_primary']};padding:32px 120px;}}"
        )
        self._editor_text.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        # Alignement centré par défaut — style mise en page scénario cinéma
        from PyQt6.QtGui import QTextOption
        _opt = QTextOption()
        _opt.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        self._editor_text.document().setDefaultTextOption(_opt)
        self._editor_text.textChanged.connect(self._schedule_autosave)
        self._editor_text.textChanged.connect(self._update_dur_estimate)
        main.addWidget(self._editor_text, 1)

        # Right panel
        right_sep = QFrame()
        right_sep.setFixedWidth(1)
        right_sep.setStyleSheet(f"background:{CP['border']};")
        main.addWidget(right_sep)

        main.addWidget(self._build_right_panel())

        outer.addLayout(main, 1)
        return w

    def _build_film_strip(self) -> QWidget:
        """Bande de configuration — Style visuel et Durée du film (visible en permanence au-dessus de l'éditeur)."""
        strip = QWidget()
        strip.setFixedHeight(46)
        strip.setStyleSheet(
            f"background:{CP['bg1']};border-bottom:1px solid {CP['border']};"
        )
        sl = QHBoxLayout(strip)
        sl.setContentsMargins(24, 0, 24, 0)
        sl.setSpacing(10)

        # ── Style visuel ──────────────────────────────────────────────────────
        _style_lbl = QLabel("Style visuel")
        _style_lbl.setStyleSheet(
            f"color:{CP['text_dim']};font-size:10px;font-weight:600;"
            f"letter-spacing:0.5px;background:transparent;"
        )
        sl.addWidget(_style_lbl)

        import core.style as _sc_style_mod
        self._film_style_combo = QComboBox()
        self._film_style_combo.addItem("— Style visuel —", "")
        _cur_grp_sc = None
        for _s in _sc_style_mod.STYLES:
            _g = _s.get("group", "")
            if _g != _cur_grp_sc:
                _cur_grp_sc = _g
                _gi = next((g for g in _sc_style_mod.GROUPS if g["key"] == _g), None)
                if _gi:
                    self._film_style_combo.addItem(
                        f"  {_gi['icon']}  {_gi['name'].upper()}", "__sep__"
                    )
                    _sep_i = self._film_style_combo.model().item(
                        self._film_style_combo.count() - 1
                    )
                    _sep_i.setEnabled(False)
                    _sep_i.setForeground(QColor(CP.get("accent2", CP.get("accent", "#7c6bff"))))
            self._film_style_combo.addItem(f"    {_s['icon']}  {_s['name']}", _s["key"])
        self._film_style_combo.setFixedHeight(30)
        self._film_style_combo.setMinimumWidth(160)
        self._film_style_combo.setStyleSheet(
            f"QComboBox{{background:{CP['bg2']};border:1px solid {CP['border']};"
            f"border-radius:5px;color:{CP['text_primary']};font-size:10px;padding:0 6px;}}"
            f"QComboBox:focus{{border-color:{CP.get('accent2_dim', CP['border_bright'])};}}"
            f"QComboBox::drop-down{{border:none;width:18px;}}"
            f"QComboBox QAbstractItemView{{background:{CP['bg2']};color:{CP['text_primary']};"
            f"selection-background-color:{CP.get('accent2_dim', CP['bg3'])};border:1px solid {CP['border']};}}"
        )
        self._film_style_combo.currentIndexChanged.connect(self._schedule_autosave)
        self._film_style_combo.currentIndexChanged.connect(self._on_scenario_style_changed)
        sl.addWidget(self._film_style_combo)

        _vs = QFrame()
        _vs.setFrameShape(QFrame.Shape.VLine)
        _vs.setFixedHeight(20)
        _vs.setStyleSheet(f"color:{CP['border']};background:{CP['border']};")
        sl.addWidget(_vs)

        # ── Durée du film ─────────────────────────────────────────────────────
        self._dur_defined_check = QCheckBox("Durée cible :")
        self._dur_defined_check.setChecked(False)
        self._dur_defined_check.setFixedHeight(28)
        self._dur_defined_check.setStyleSheet(
            f"QCheckBox{{color:{CP['text_dim']};font-size:10px;font-weight:600;"
            f"letter-spacing:0.5px;background:transparent;spacing:5px;}}"
            f"QCheckBox::indicator{{width:13px;height:13px;"
            f"border:1px solid {CP['border_bright']};border-radius:3px;"
            f"background:{CP['bg2']};}}"
            f"QCheckBox::indicator:checked{{background:{CP['accent2']};"
            f"border-color:{CP['accent2']};}}"
        )
        sl.addWidget(self._dur_defined_check)

        _spin_ss = (
            f"QSpinBox{{background:{CP['bg2']};border:1px solid {CP['border']};"
            f"border-radius:5px;color:{CP['text_primary']};font-size:11px;"
            f"padding:0 4px;min-width:44px;max-width:56px;}}"
            f"QSpinBox:focus{{border-color:{CP['accent2_dim']};}}"
            f"QSpinBox::up-button, QSpinBox::down-button{{width:14px;}}"
        )
        self._dur_min = QSpinBox()
        self._dur_min.setRange(0, 600)
        self._dur_min.setValue(90)
        self._dur_min.setSuffix("m")
        self._dur_min.setFixedHeight(30)
        self._dur_min.setStyleSheet(_spin_ss)
        self._dur_min.valueChanged.connect(self._schedule_autosave)
        sl.addWidget(self._dur_min)

        self._dur_sec = QSpinBox()
        self._dur_sec.setRange(0, 59)
        self._dur_sec.setValue(0)
        self._dur_sec.setSuffix("s")
        self._dur_sec.setFixedHeight(30)
        self._dur_sec.setStyleSheet(_spin_ss)
        self._dur_sec.valueChanged.connect(self._schedule_autosave)
        sl.addWidget(self._dur_sec)

        # Durée estimée (mise à jour live au fil de la frappe)
        self._dur_estimate_lbl = QLabel("Estimé : —")
        self._dur_estimate_lbl.setStyleSheet(
            f"color:{CP['accent']};font-size:10px;font-family:'Consolas',monospace;"
            f"background:transparent;"
        )
        sl.addWidget(self._dur_estimate_lbl)

        # Connexions
        self._dur_defined_check.toggled.connect(self._on_dur_defined_toggled)
        self._on_dur_defined_toggled(False)  # non défini par défaut

        sl.addStretch()
        return strip

    def _build_right_panel(self):
        from PyQt6.QtWidgets import QScrollArea, QSizePolicy

        w = QWidget()
        w.setFixedWidth(300)
        w.setStyleSheet(f"background:{CP['bg1']};")

        root_lay = QVBoxLayout(w)
        root_lay.setContentsMargins(0, 0, 0, 0)
        root_lay.setSpacing(0)

        # ── helper: ai_btn ────────────────────────────────────────────────────
        def _ai_btn(icon, label, sub, callback):
            btn = QPushButton()
            btn.setFixedHeight(52)
            btn.setStyleSheet(
                f"QPushButton{{background:{CP['bg2']};border:1px solid {CP['border']};"
                f"border-radius:8px;text-align:left;padding:0 10px;}}"
                f"QPushButton:hover{{border-color:{CP['accent2_dim']};background:{CP['bg3']};}}"
                f"QPushButton:pressed{{background:{CP['bg4']};}}"
                f"QPushButton:disabled{{opacity:0.4;}}"
            )
            bl = QVBoxLayout(btn)
            bl.setContentsMargins(6, 6, 6, 6)
            bl.setSpacing(1)
            title_row = QHBoxLayout()
            title_row.setSpacing(6)
            ico_lbl = QLabel(icon)
            ico_lbl.setStyleSheet(
                f"color:{CP['accent2']};font-size:13px;background:transparent;border:none;"
            )
            txt_lbl = QLabel(label)
            txt_lbl.setStyleSheet(
                f"color:{CP['text_primary']};font-size:10px;font-weight:700;"
                f"background:transparent;border:none;"
            )
            title_row.addWidget(ico_lbl)
            title_row.addWidget(txt_lbl)
            title_row.addStretch()
            sub_lbl = QLabel(sub)
            sub_lbl.setStyleSheet(
                f"color:{CP['text_dim']};font-size:8px;background:transparent;border:none;"
            )
            bl.addLayout(title_row)
            bl.addWidget(sub_lbl)
            btn.clicked.connect(callback)
            return btn

        # ── helper: section toggle header ─────────────────────────────────────
        _toggle_ss = (
            f"QPushButton{{background:{CP['bg2']};color:{CP['text_secondary']};"
            f"border:none;border-bottom:1px solid {CP['border']};"
            f"font-size:10px;font-weight:700;text-align:left;"
            f"padding:7px 16px;letter-spacing:0.4px;}}"
            f"QPushButton:hover{{background:{CP['bg3']};color:{CP['text_primary']};}}"
        )

        def _make_toggle(title: str, container: QWidget, expanded: bool = True):
            btn = QPushButton(f"{'▼' if expanded else '▶'}  {title}")
            btn.setCheckable(True)
            btn.setChecked(expanded)
            btn.setStyleSheet(_toggle_ss)
            container.setVisible(expanded)
            def _tog(checked, b=btn, c=container, t=title):
                c.setVisible(checked)
                b.setText(f"{'▼' if checked else '▶'}  {t}")
            btn.toggled.connect(_tog)
            return btn

        def _section_container():
            c = QWidget()
            c.setStyleSheet(f"background:{CP['bg1']};")
            lay = QVBoxLayout(c)
            lay.setContentsMargins(16, 8, 16, 8)
            lay.setSpacing(6)
            return c, lay

        # ══════════════════════════════════════════════════════════════════════
        # Scroll area — contient les trois sections repliables
        # ══════════════════════════════════════════════════════════════════════
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet(
            "QScrollArea{border:none;background:transparent;}"
            f"QScrollBar:vertical{{background:{CP['bg2']};width:4px;border-radius:2px;}}"
            f"QScrollBar::handle:vertical{{background:{CP['border_bright']};border-radius:2px;}}"
            f"QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical{{height:0;}}"
        )

        scroll_content = QWidget()
        scroll_content.setStyleSheet(f"background:{CP['bg1']};")
        sc_lay = QVBoxLayout(scroll_content)
        sc_lay.setContentsMargins(0, 0, 0, 0)
        sc_lay.setSpacing(0)

        # ── Section 1 : Claude IA ─────────────────────────────────────────────
        c_ia, l_ia = _section_container()

        self._btn_format = _ai_btn(
            "≡", "Mise en page scénario", "Format standard INT./EXT.", self._on_format,
        )
        self._btn_arrange = _ai_btn(
            "⊞", "Proposer un arrangement", "Analyse structure + suggestions", self._on_arrange,
        )
        l_ia.addWidget(self._btn_format)
        l_ia.addWidget(self._btn_arrange)

        # Intensité
        _intens_row = QWidget()
        _intens_row.setStyleSheet("background:transparent;")
        _ir = QVBoxLayout(_intens_row)
        _ir.setContentsMargins(2, 2, 2, 0)
        _ir.setSpacing(3)

        _intens_header = QHBoxLayout()
        _intens_title = QLabel("Intensité d'arrangement")
        _intens_title.setStyleSheet(
            f"color:{CP['text_secondary']};font-size:9px;font-weight:600;background:transparent;"
        )
        self._arrange_intensity_lbl = QLabel("5")
        self._arrange_intensity_lbl.setFixedWidth(18)
        self._arrange_intensity_lbl.setAlignment(Qt.AlignmentFlag.AlignRight)
        self._arrange_intensity_lbl.setStyleSheet(
            f"color:{CP['accent2']};font-size:10px;font-weight:700;background:transparent;"
        )
        _intens_header.addWidget(_intens_title)
        _intens_header.addStretch()
        _intens_header.addWidget(self._arrange_intensity_lbl)

        self._arrange_intensity = QSlider(Qt.Orientation.Horizontal)
        self._arrange_intensity.setRange(1, 10)
        self._arrange_intensity.setValue(5)
        self._arrange_intensity.setFixedHeight(16)
        self._arrange_intensity.setStyleSheet(f"""
            QSlider::groove:horizontal {{
                height: 4px; background: {CP['bg3']}; border-radius: 2px;
            }}
            QSlider::handle:horizontal {{
                background: {CP['accent2']}; width: 12px; height: 12px;
                margin: -4px 0; border-radius: 6px;
            }}
            QSlider::sub-page:horizontal {{
                background: {CP['accent2_dim']}; border-radius: 2px;
            }}
        """)

        _intens_ends = QHBoxLayout()
        for _t, _align in [("1", Qt.AlignmentFlag.AlignLeft), ("10", Qt.AlignmentFlag.AlignRight)]:
            _l = QLabel(_t)
            _l.setStyleSheet(f"color:{CP['text_dim']};font-size:8px;background:transparent;")
            _intens_ends.addWidget(_l)
            if _t == "1":
                _intens_ends.addStretch()

        self._arrange_intensity_desc = QLabel(_intensity_label(5))
        self._arrange_intensity_desc.setWordWrap(True)
        self._arrange_intensity_desc.setStyleSheet(
            f"color:{CP['accent2']};font-size:8px;font-style:italic;background:transparent;"
        )
        self._arrange_intensity.valueChanged.connect(
            lambda v: (
                self._arrange_intensity_lbl.setText(str(v)),
                self._arrange_intensity_desc.setText(_intensity_label(v)),
            )
        )

        # Légende 1-10 (repliable)
        _leg_container = QWidget()
        _leg_container.setStyleSheet("background:transparent;")
        _leg_lay = QVBoxLayout(_leg_container)
        _leg_lay.setContentsMargins(0, 4, 0, 0)
        _leg_lay.setSpacing(1)
        _legend_frame = QFrame()
        _legend_frame.setStyleSheet(
            f"QFrame{{background:{CP['bg2']};border:1px solid {CP['border']};"
            f"border-radius:6px;}}"
        )
        _lf_lay = QVBoxLayout(_legend_frame)
        _lf_lay.setContentsMargins(8, 5, 8, 5)
        _lf_lay.setSpacing(1)
        for _lvl, _txt in _INTENSITY_LEGEND:
            _row = QHBoxLayout()
            _row.setSpacing(5)
            _n = QLabel(_lvl)
            _n.setFixedWidth(18)
            _n.setStyleSheet(
                f"color:{CP['accent2']};font-size:7px;font-weight:700;"
                f"background:transparent;border:none;"
            )
            _d = QLabel(_txt)
            _d.setStyleSheet(
                f"color:{CP['text_dim']};font-size:7px;background:transparent;border:none;"
            )
            _row.addWidget(_n)
            _row.addWidget(_d, 1)
            _lf_lay.addLayout(_row)
        _leg_lay.addWidget(_legend_frame)

        _btn_toggle_legend = QPushButton("▶  Légende niveaux 1-10")
        _btn_toggle_legend.setCheckable(True)
        _btn_toggle_legend.setChecked(False)
        _btn_toggle_legend.setStyleSheet(
            f"QPushButton{{background:transparent;color:{CP['text_dim']};"
            f"border:none;font-size:8px;font-weight:600;text-align:left;padding:2px 0;}}"
            f"QPushButton:hover{{color:{CP['text_secondary']};}}"
        )
        _leg_container.setVisible(False)
        def _tog_leg(checked, b=_btn_toggle_legend, c=_leg_container):
            c.setVisible(checked)
            b.setText(f"{'▼' if checked else '▶'}  Légende niveaux 1-10")
        _btn_toggle_legend.toggled.connect(_tog_leg)

        _ir.addLayout(_intens_header)
        _ir.addWidget(self._arrange_intensity)
        _ir.addLayout(_intens_ends)
        _ir.addWidget(self._arrange_intensity_desc)
        _ir.addWidget(_btn_toggle_legend)
        _ir.addWidget(_leg_container)
        l_ia.addWidget(_intens_row)

        tog_ia = _make_toggle("☁  Claude IA", c_ia, expanded=True)
        sc_lay.addWidget(tog_ia)
        sc_lay.addWidget(c_ia)

        # ── Section 2 : Générer depuis le scénario (repliée par défaut) ───────
        c_gen, l_gen = _section_container()

        self._btn_gen_characters = _ai_btn(
            "◎", "Générer les personnages", "Identifier les personnages depuis le scénario",
            self._on_gen_characters,
        )
        self._btn_gen_decors = _ai_btn(
            "⌂", "Générer les décors", "Identifier les décors depuis le scénario",
            self._on_gen_decors,
        )
        self._btn_gen_accessories = _ai_btn(
            "⊡", "Générer les accessoires", "Identifier les accessoires depuis le scénario",
            self._on_gen_accessories,
        )
        self._btn_gen_hmc = _ai_btn(
            "✂", "Générer le HMC", "Identifier les éléments HMC depuis le scénario",
            self._on_gen_hmc,
        )
        self._btn_gen_vehicles = _ai_btn(
            "🚗", "Générer les véhicules", "Identifier les véhicules depuis le scénario",
            self._on_gen_vehicles,
        )
        self._btn_storyboard = _ai_btn(
            "⊕", "Générer le storyboard", "Importe les plans dans Storyboard",
            self._on_storyboard,
        )
        for _b in (
            self._btn_gen_characters, self._btn_gen_decors, self._btn_gen_accessories,
            self._btn_gen_hmc, self._btn_gen_vehicles, self._btn_storyboard,
        ):
            l_gen.addWidget(_b)

        _red = CP.get("red", "#ff4f6a")
        # ── Bouton Tout Générer (placé dans la zone basse dédiée, créé ici pour _set_ai_busy) ──
        self._btn_generate_all = QPushButton()
        self._btn_generate_all.setFixedHeight(60)
        self._btn_generate_all.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_generate_all.setStyleSheet(
            f"QPushButton{{background:{CP['bg2']};border:1.5px solid {_red};"
            f"border-radius:8px;text-align:left;padding:0 10px;}}"
            f"QPushButton:hover{{background:rgba(255,79,106,0.08);border-color:{_red};}}"
            f"QPushButton:pressed{{background:rgba(255,79,106,0.16);}}"
            f"QPushButton:disabled{{opacity:0.35;border-color:{CP['border']};}}"
        )
        self._btn_generate_all.clicked.connect(self._on_generate_all)
        tog_gen = _make_toggle("☁  Générer depuis le scénario", c_gen, expanded=True)
        sc_lay.addWidget(tog_gen)
        sc_lay.addWidget(c_gen)

        sc_lay.addStretch()
        scroll.setWidget(scroll_content)
        root_lay.addWidget(scroll, 1)

        # ══════════════════════════════════════════════════════════════════════
        # Zone basse fixe — progress + Résultat Claude
        # ══════════════════════════════════════════════════════════════════════
        bottom = QWidget()
        bottom.setStyleSheet(f"background:{CP['bg1']};")
        b_lay = QVBoxLayout(bottom)
        b_lay.setContentsMargins(16, 8, 16, 12)
        b_lay.setSpacing(6)

        self._ai_progress_lbl = QLabel("")
        self._ai_progress_lbl.setWordWrap(True)
        self._ai_progress_lbl.setStyleSheet(
            f"color:{CP['text_dim']};font-size:10px;font-family:'Consolas',monospace;"
            f"background:transparent;"
        )
        b_lay.addWidget(self._ai_progress_lbl)

        b_lay.addWidget(_sep())

        self._ai_progress_bar = QProgressBar()
        self._ai_progress_bar.setRange(0, 0)
        self._ai_progress_bar.setFixedHeight(4)
        self._ai_progress_bar.setTextVisible(False)
        self._ai_progress_bar.setVisible(False)
        self._ai_progress_bar.setStyleSheet(
            f"QProgressBar{{background:{CP['bg3']};border:none;border-radius:2px;}}"
            f"QProgressBar::chunk{{background:{CP['accent2']};border-radius:2px;}}"
        )
        b_lay.addWidget(self._ai_progress_bar)

        self._result_area = QTextEdit()
        self._result_area.setReadOnly(True)
        self._result_area.setMinimumHeight(80)
        self._result_area.setMaximumHeight(160)
        self._result_area.setVisible(False)
        self._result_area.setStyleSheet(
            f"QTextEdit{{background:{CP['bg2']};border:1px solid {CP['border']};"
            f"border-radius:8px;color:{CP['text_secondary']};font-size:11px;padding:12px;}}"
        )
        b_lay.addWidget(self._result_area)

        self._btn_reopen_window = QPushButton("⤢  Rouvrir la fenêtre")
        self._btn_reopen_window.setFixedHeight(30)
        self._btn_reopen_window.setVisible(False)
        self._btn_reopen_window.setStyleSheet(
            f"QPushButton{{background:transparent;color:{CP['accent2']};"
            f"border:1px solid {CP['accent2_dim']};border-radius:6px;"
            f"font-size:10px;font-weight:700;padding:0 8px;}}"
            f"QPushButton:hover{{background:rgba(124,107,255,0.12);}}"
        )
        self._btn_reopen_window.clicked.connect(self._open_result_window)
        b_lay.addWidget(self._btn_reopen_window)

        self._btn_undo_action = QPushButton("↺  Annuler")
        self._btn_undo_action.setFixedHeight(30)
        self._btn_undo_action.setVisible(False)
        self._btn_undo_action.setStyleSheet(
            f"QPushButton{{background:transparent;color:{CP['text_secondary']};"
            f"border:1px solid {CP['border']};border-radius:6px;font-size:10px;font-weight:700;padding:0 8px;}}"
            f"QPushButton:hover{{background:rgba(255,79,106,0.10);color:{CP['red']};border-color:{CP['red']};}}"
        )
        self._btn_undo_action.clicked.connect(self._undo_ai_action)
        b_lay.addWidget(self._btn_undo_action)

        self._btn_goto_storyboard = QPushButton("→  Voir dans le Storyboard")
        self._btn_goto_storyboard.setFixedHeight(30)
        self._btn_goto_storyboard.setVisible(False)
        self._btn_goto_storyboard.setStyleSheet(
            f"QPushButton{{background:rgba(78,205,196,0.10);color:{CP['accent']};"
            f"border:1px solid {CP['accent_dim']};border-radius:6px;"
            f"font-size:10px;font-weight:700;padding:0 8px;}}"
            f"QPushButton:hover{{background:rgba(78,205,196,0.22);}}"
        )
        self._btn_goto_storyboard.clicked.connect(
            lambda: self.navigate_requested.emit("storyboard", self._last_storyboard_version_id)
        )
        b_lay.addWidget(self._btn_goto_storyboard)

        root_lay.addWidget(bottom)

        # ══════════════════════════════════════════════════════════════════════
        # Zone basse : Génération complète — isolée visuellement
        # ══════════════════════════════════════════════════════════════════════
        gen_all_zone = QWidget()
        gen_all_zone.setStyleSheet(
            f"background:{CP['bg1']};"
        )
        ga_lay = QVBoxLayout(gen_all_zone)
        ga_lay.setContentsMargins(16, 10, 16, 12)
        ga_lay.setSpacing(8)

        self._gen_all_progress_bar = QProgressBar()
        self._gen_all_progress_bar.setRange(0, 0)
        self._gen_all_progress_bar.setFixedHeight(4)
        self._gen_all_progress_bar.setTextVisible(False)
        self._gen_all_progress_bar.setVisible(False)
        self._gen_all_progress_bar.setStyleSheet(
            f"QProgressBar{{background:{CP['bg3']};border:none;border-radius:2px;}}"
            f"QProgressBar::chunk{{background:{CP.get('red','#ff4f6a')};border-radius:2px;}}"
        )
        ga_lay.addWidget(self._gen_all_progress_bar)

        self._gen_all_status_lbl = QLabel("")
        self._gen_all_status_lbl.setVisible(False)
        self._gen_all_status_lbl.setWordWrap(True)
        self._gen_all_status_lbl.setStyleSheet(
            f"color:{CP['text_dim']};font-size:9px;font-family:'Consolas',monospace;"
            f"background:transparent;"
        )
        ga_lay.addWidget(self._gen_all_status_lbl)

        _ga_btn_lay = QVBoxLayout(self._btn_generate_all)
        _ga_btn_lay.setContentsMargins(6, 6, 6, 6)
        _ga_btn_lay.setSpacing(1)
        _ga_btn_row = QHBoxLayout()
        _ga_btn_row.setSpacing(6)
        _ga_btn_ico = QLabel("⚡")
        _ga_btn_ico.setStyleSheet(
            f"color:{CP.get('red','#ff4f6a')};font-size:14px;background:transparent;border:none;"
        )
        _ga_btn_txt = QLabel("Tout générer")
        _ga_btn_txt.setStyleSheet(
            f"color:{CP.get('red','#ff4f6a')};font-size:10px;font-weight:700;"
            f"background:transparent;border:none;"
        )
        _ga_btn_row.addWidget(_ga_btn_ico)
        _ga_btn_row.addWidget(_ga_btn_txt)
        _ga_btn_row.addStretch()
        _ga_btn_sub = QLabel(
            "Personnages · Décors · Accessoires · HMC · Véhicules"
            " · Storyboard · Images · Moods"
        )
        _ga_btn_sub.setStyleSheet(
            f"color:{CP['text_dim']};font-size:8px;background:transparent;border:none;"
        )
        _ga_btn_lay.addLayout(_ga_btn_row)
        _ga_btn_lay.addWidget(_ga_btn_sub)
        ga_lay.addWidget(self._btn_generate_all)

        root_lay.addWidget(gen_all_zone)
        return w

    # ── Navigation ────────────────────────────────────────────────────────────

    def _go_landing(self):
        self._manual_save()
        self._stack.setCurrentIndex(0)
        self._refresh_recent()

    def _go_editor(self):
        self._result_area.clear()
        self._result_area.setVisible(False)
        self._btn_reopen_window.setVisible(False)
        self._btn_undo_action.setVisible(False)
        self._btn_goto_storyboard.setVisible(False)
        self._ai_progress_lbl.setText("")
        self._ai_progress_bar.setVisible(False)
        self._last_analysis = ""
        self._last_format_result = ""
        self._last_result_kind = ""
        self._stack.setCurrentIndex(1)

    def _set_editor_text(self, text: str):
        """setPlainText + re-applique l'alignement centré sur tous les blocs."""
        self._editor_text.setPlainText(text)
        self._apply_center_alignment()

    def _apply_center_alignment(self):
        """Applique AlignHCenter à tous les blocs du document sans polluer le undo Qt."""
        from PyQt6.QtGui import QTextCursor, QTextBlockFormat
        doc = self._editor_text.document()
        doc.setUndoRedoEnabled(False)
        cursor = self._editor_text.textCursor()
        cursor.select(QTextCursor.SelectionType.Document)
        fmt = QTextBlockFormat()
        fmt.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        cursor.mergeBlockFormat(fmt)
        cursor.clearSelection()
        cursor.movePosition(QTextCursor.MoveOperation.Start)
        self._editor_text.setTextCursor(cursor)
        doc.setUndoRedoEnabled(True)

    def _new_scenario(self):
        from core import context as _ctx
        import core.project as _project
        _pdata = _project.load_project(_ctx.get_project_path())
        _pname = _pdata.get("name", "") if _pdata else ""
        self._current = {}
        self._undo_stack.clear()
        self._redo_stack.clear()
        self._btn_undo.setEnabled(False)
        self._btn_redo.setEnabled(False)
        self._title_edit.setText(_pname)
        self._set_editor_text("")
        self._dur_defined_check.setChecked(False)
        self._dur_min.setValue(90)
        self._dur_sec.setValue(0)
        self._on_dur_defined_toggled(False)
        self._film_style_combo.setCurrentIndex(0)   # "— Style visuel —"
        self._refresh_version_combo()
        self._go_editor()

    def _open_scenario(self, sc: dict):
        self._current = sc
        self._undo_stack.clear()
        self._redo_stack.clear()
        self._btn_undo.setEnabled(False)
        self._btn_redo.setEnabled(False)
        self._title_edit.setText(sc.get("title", ""))
        content = sc.get("formatted_content") or sc.get("raw_content", "")
        self._set_editor_text(content)
        dur         = sc.get("duration_secs", 0)
        dur_defined = sc.get("duration_defined", False) or dur > 0
        self._dur_defined_check.setChecked(dur_defined)
        self._dur_min.setValue(dur // 60 if dur > 0 else 90)
        self._dur_sec.setValue(dur % 60 if dur > 0 else 0)
        self._on_dur_defined_toggled(dur_defined)
        film_style = sc.get("film_style", "")
        idx = self._film_style_combo.findData(film_style) if film_style else -1
        self._film_style_combo.setCurrentIndex(idx if idx > 0 else 0)
        self._refresh_version_combo()
        self._go_editor()

    def _import_scenario(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Importer un scénario", "",
            "Textes (*.txt *.docx *.pdf)"
        )
        if not path:
            return
        try:
            text = scenario_api.read_file(path)
        except Exception as e:
            QMessageBox.warning(self, "Erreur d'import", str(e))
            return
        name = os.path.splitext(os.path.basename(path))[0]
        self._current = {"file_path": path}
        self._title_edit.setText(name)
        self._set_editor_text(text)
        self._go_editor()

    def _delete_scenario(self, scenario_id: str):
        reply = QMessageBox.question(
            self, "Supprimer",
            "Supprimer ce scénario ?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            scenario_api.delete_scenario(scenario_id)
            self._refresh_recent()

    # ── Style propagation ─────────────────────────────────────────────────────

    def _on_scenario_style_changed(self, _idx: int):
        key = self._film_style_combo.currentData() or ""
        if key and key != "__sep__":
            import core.style as _style_mod
            _style_mod.set_style(key, _style_mod.get_style_custom())
            self.style_changed.emit(key)

    # ── Save ─────────────────────────────────────────────────────────────────

    def _adjust_title_width(self, text: str = ""):
        fm = self._title_edit.fontMetrics()
        text = text or self._title_edit.text() or self._title_edit.placeholderText()
        w = fm.horizontalAdvance(text) + 28  # 28 = left+right padding
        self._title_edit.setFixedWidth(max(160, min(w, 480)))

    def _schedule_autosave(self):
        self._autosave_timer.start()

    def _autosave(self):
        if self._stack.currentIndex() == 1:
            self._save(silent=True)

    def _manual_save(self):
        self._save(silent=False)

    # ── Durée ─────────────────────────────────────────────────────────────────

    def _on_dur_defined_toggled(self, checked: bool):
        """Affiche/masque les spinboxes durée selon la case à cocher."""
        self._dur_min.setVisible(checked)
        self._dur_sec.setVisible(checked)
        self._schedule_autosave()

    @staticmethod
    def _estimate_duration(text: str) -> tuple[int, int]:
        """Estime la durée de projection depuis le nombre de mots.

        Règle : ~180 mots/min (mélange dialogues 130wpm + action 250wpm).
        Retourne (minutes, secondes).
        """
        words = len(text.split())
        if words < 10:
            return 0, 0
        total_secs = int(words / 180 * 60)
        return total_secs // 60, total_secs % 60

    def _update_dur_estimate(self):
        """Met à jour le label d'estimation live."""
        text = self._editor_text.toPlainText()
        mins, secs = self._estimate_duration(text)
        if mins == 0 and secs == 0:
            self._dur_estimate_lbl.setText("Estimé : —")
        elif mins == 0:
            self._dur_estimate_lbl.setText(f"Estimé : ~{secs}s")
        elif secs == 0:
            self._dur_estimate_lbl.setText(f"Estimé : ~{mins}m")
        else:
            self._dur_estimate_lbl.setText(f"Estimé : ~{mins}m{secs:02d}")

    def _save(self, silent=False):
        text = self._editor_text.toPlainText().strip()
        title = self._title_edit.text().strip()
        if not text and not title:
            return
        data = dict(self._current or {})
        dur_defined    = self._dur_defined_check.isChecked()
        dur_secs       = (self._dur_min.value() * 60 + self._dur_sec.value()) if dur_defined else 0
        film_style_key = self._film_style_combo.currentData() or ""
        data.update({
            "title":             title or "Scénario sans titre",
            "raw_content":       text,
            "formatted_content": text,   # keep in sync so reload always shows current content
            "duration_secs":     dur_secs,
            "duration_defined":  dur_defined,
            "film_style":        film_style_key if film_style_key not in ("", "__sep__") else "",
        })
        self._current = scenario_api.save_scenario(data)
        if not silent:
            self._save_indicator.setText("Sauvegardé ✓")
            QTimer.singleShot(2000, lambda: self._save_indicator.setText(""))
        else:
            self._save_indicator.setText("✓")
            QTimer.singleShot(1500, lambda: self._save_indicator.setText(""))

    # ── Claude actions ────────────────────────────────────────────────────────

    def _get_text(self) -> str:
        return self._editor_text.toPlainText().strip()

    def _set_ai_busy(self, busy: bool):
        for btn in (
            self._btn_format, self._btn_arrange, self._btn_storyboard,
            self._btn_gen_characters, self._btn_gen_decors,
            self._btn_gen_accessories, self._btn_gen_hmc, self._btn_gen_vehicles,
            self._btn_generate_all,
        ):
            btn.setEnabled(not busy)
        self._ai_progress_bar.setVisible(busy)

    def _on_format(self):
        text = self._get_text()
        if not text:
            self._ai_progress_lbl.setText("Écris d'abord un texte à formater.")
            return
        from api.screenplay import FormatScreenplayWorker
        self._set_ai_busy(True)
        self._ai_progress_lbl.setText("Formatage en cours via Claude…")
        self._btn_reopen_window.setVisible(False)
        self._btn_undo_action.setVisible(False)
        self._result_area.clear()
        self._result_area.setVisible(False)
        self._worker = FormatScreenplayWorker(text)
        self._worker.finished.connect(self._on_format_done)
        self._worker.failed.connect(self._on_ai_fail)
        self._worker.start()

    def _on_format_done(self, result: str):
        self._set_ai_busy(False)
        self._ai_progress_lbl.setText("Formatage terminé ✓")
        self._last_format_result = result
        self._last_result_kind = "format"
        self._btn_reopen_window.setVisible(True)
        self._open_simple_result_window(result)

    def _on_arrange(self):
        text = self._get_text()
        if not text:
            self._ai_progress_lbl.setText("Écris d'abord un texte à analyser.")
            return
        from api.screenplay import ArrangeScreenplayWorker
        from core.casting import list_characters
        from core.decors import list_decors
        self._set_ai_busy(True)
        self._ai_progress_lbl.setText("Analyse en cours via Claude…")
        self._btn_reopen_window.setVisible(False)
        self._btn_undo_action.setVisible(False)
        self._result_area.clear()
        self._result_area.setVisible(True)
        self._result_area.setPlaceholderText("Analyse en cours…")
        dur_secs  = (self._dur_min.value() * 60 + self._dur_sec.value()) if self._dur_defined_check.isChecked() else 0
        intensity = self._arrange_intensity.value()
        try:
            project_context = {
                "characters": list_characters(),
                "decors":     list_decors(),
            }
        except Exception:
            project_context = {}
        self._worker = ArrangeScreenplayWorker(text, dur_secs, intensity, project_context)
        self._worker.chunk.connect(self._on_arrange_chunk)
        self._worker.finished.connect(self._on_arrange_done)
        self._worker.failed.connect(self._on_ai_fail)
        self._worker.start()

    def _on_arrange_chunk(self, text: str):
        cursor = self._result_area.textCursor()
        cursor.movePosition(cursor.MoveOperation.End)
        cursor.insertText(text)
        self._result_area.setTextCursor(cursor)

    def _on_arrange_done(self, result: str):
        self._result_area.setVisible(False)
        self._result_area.clear()
        self._set_ai_busy(False)
        self._last_analysis = result
        self._last_result_kind = "arrange"
        # Durée estimée affichée dans le statut
        text = self._editor_text.toPlainText()
        mins, secs = self._estimate_duration(text)
        if mins or secs:
            est = f"~{mins}m{secs:02d}" if mins else f"~{secs}s"
            self._ai_progress_lbl.setText(f"Analyse terminée ✓  ·  Durée estimée : {est}")
        else:
            self._ai_progress_lbl.setText("Analyse terminée ✓")
        self._btn_reopen_window.setVisible(True)
        self._open_arrange_session(result)

    def _on_modify_arrange(self):
        original    = self._get_text()
        suggestions = self._last_analysis
        if not original:
            self._ai_progress_lbl.setText("Aucun texte à modifier.")
            return
        if not suggestions:
            self._ai_progress_lbl.setText("Lance d'abord « Proposer un arrangement ».")
            return
        from api.screenplay import ApplyArrangeWorker
        self._set_ai_busy(True)
        self._ai_progress_lbl.setText("Application des suggestions via Claude…")
        self._btn_undo_action.setVisible(False)
        intensity = self._arrange_intensity.value()
        self._worker = ApplyArrangeWorker(original, suggestions, intensity)
        self._worker.finished.connect(self._on_modify_done)
        self._worker.failed.connect(self._on_ai_fail)
        self._worker.start()

    def _on_modify_done(self, result: str):
        self._set_ai_busy(False)
        self._ai_progress_lbl.setText("Scénario modifié selon les suggestions ✓")
        self._push_undo()
        self._set_editor_text(result)
        if self._current is not None:
            self._current["formatted_content"] = result
        self._btn_undo_action.setVisible(True)

    def _on_storyboard(self):
        text = self._get_text()
        if not text:
            self._ai_progress_lbl.setText("Écris d'abord un scénario à découper.")
            return
        import core.storyboard as sb_api
        existing = sb_api.list_shots(sb_api.DEFAULT_VERSION_ID)
        if existing:
            reply = QMessageBox.question(
                self, "Remplacer le storyboard",
                f"Un storyboard existe déjà ({len(existing)} plan{'s' if len(existing) > 1 else ''}).\n"
                "Souhaitez-vous le remplacer par un nouveau découpage ?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if reply != QMessageBox.StandardButton.Yes:
                return
        dur_secs = (self._dur_min.value() * 60 + self._dur_sec.value()) if self._dur_defined_check.isChecked() else 0
        sc_id = (self._current or {}).get("id", "")
        from ui.dialog_storyboard_generate import StoryboardGenerateDialog
        dlg = StoryboardGenerateDialog(text, dur_secs, sc_id, parent=self)
        if dlg.exec() == StoryboardGenerateDialog.DialogCode.Accepted and dlg._shots:
            count = len(dlg._shots)
            self._ai_progress_lbl.setText(f"{count} plans importés dans le Storyboard ✓")
            self._btn_goto_storyboard.setVisible(True)

    # ── Handlers extraction ───────────────────────────────────────────────────

    def _start_extraction(self, worker_cls, label: str) -> object | None:
        text = self._get_text()
        if not text:
            self._ai_progress_lbl.setText("Écris d'abord un scénario.")
            return None
        self._ai_progress_bar.setRange(0, 0)
        self._set_ai_busy(True)
        self._ai_progress_lbl.setText(f"{label} via Claude…")
        self._show_log(
            f"{label} en cours d'analyse…\n\n"
            "Veuillez patienter, le chargement peut être long.\n"
            "\nRendez-vous dans l'onglet correspondant pour compléter les fiches manuellement."
        )
        self._btn_undo_action.setVisible(False)
        w = worker_cls(text)
        self._worker = w
        w.failed.connect(self._on_ai_fail)
        return w

    def _on_gen_characters(self):
        text = self._get_text()
        if not text:
            self._ai_progress_lbl.setText("Écris d'abord un scénario.")
            return
        from ui.dialog_extract_generate import ExtractGenerateDialog
        dlg = ExtractGenerateDialog.for_characters(text, self)
        dlg.exec()

    def _on_gen_decors(self):
        text = self._get_text()
        if not text:
            self._ai_progress_lbl.setText("Écris d'abord un scénario.")
            return
        from ui.dialog_extract_generate import ExtractGenerateDialog
        dlg = ExtractGenerateDialog.for_decors(text, self)
        dlg.exec()

    def _on_gen_accessories(self):
        text = self._get_text()
        if not text:
            self._ai_progress_lbl.setText("Écris d'abord un scénario.")
            return
        from ui.dialog_extract_generate import ExtractGenerateDialog
        dlg = ExtractGenerateDialog.for_accessories(text, self)
        dlg.exec()

    def _on_gen_hmc(self):
        text = self._get_text()
        if not text:
            self._ai_progress_lbl.setText("Écris d'abord un scénario.")
            return
        from ui.dialog_extract_generate import ExtractGenerateDialog
        dlg = ExtractGenerateDialog.for_hmc(text, self)
        dlg.exec()

    def _on_gen_vehicles(self):
        text = self._get_text()
        if not text:
            self._ai_progress_lbl.setText("Écris d'abord un scénario.")
            return
        from ui.dialog_extract_generate import ExtractGenerateDialog
        dlg = ExtractGenerateDialog.for_vehicles(text, self)
        dlg.exec()

    def _on_ai_fail(self, err: str):
        self._set_ai_busy(False)
        self._ai_progress_bar.setRange(0, 0)
        self._ai_progress_lbl.setText(f"Erreur : {err[:120]}")

    def _open_result_window(self):
        if self._last_result_kind == "arrange" and self._last_analysis:
            self._open_arrange_session(self._last_analysis)
        elif self._last_result_kind == "format" and self._last_format_result:
            self._open_simple_result_window(self._last_format_result)

    def _open_arrange_session(self, analysis_text: str):
        """Ouvre le studio de co-écriture interactif Claude × Réalisateur."""
        from ui.dialog_arrange_session import ArrangeSessionDialog
        original   = self._get_text()
        intensity  = self._arrange_intensity.value()
        dlg = ArrangeSessionDialog(self, original, analysis_text, intensity)
        dlg.exec()
        if dlg.was_applied():
            final = dlg.final_screenplay()
            if final:
                self._push_undo()
                self._set_editor_text(final)
                if self._current is not None:
                    self._current["formatted_content"] = final
                self._ai_progress_lbl.setText("Scénario co-écrit appliqué ✓")
                self._btn_undo_action.setVisible(True)

    def _open_simple_result_window(self, text: str):
        """Fenêtre pour les résultats de formatage — avec bouton Remplacer intégré."""
        from PyQt6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QTextEdit
        dlg = QDialog(self)
        dlg.setWindowTitle("Résultat Claude — Mise en page")
        dlg.resize(900, 680)
        dlg.setStyleSheet(f"QDialog{{background:{CP['bg1']};}}")
        lay = QVBoxLayout(dlg)
        lay.setContentsMargins(20, 20, 20, 20)
        lay.setSpacing(12)
        te = QTextEdit()
        te.setReadOnly(True)
        te.setPlainText(text)
        _f = QFont("Courier New", 12)
        _f.setStyleHint(QFont.StyleHint.TypeWriter)
        te.setFont(_f)
        te.setStyleSheet(
            f"QTextEdit{{background:{CP['bg2']};border:1px solid {CP['border']};"
            f"border-radius:8px;color:{CP['text_primary']};font-size:12px;padding:16px;}}"
        )
        lay.addWidget(te, 1)
        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)

        btn_close = QPushButton("Fermer")
        btn_close.setFixedHeight(36)
        btn_close.setStyleSheet(
            f"QPushButton{{background:{CP['bg3']};color:{CP['text_secondary']};"
            f"border:1px solid {CP['border']};border-radius:7px;font-size:11px;font-weight:600;padding:0 20px;}}"
            f"QPushButton:hover{{background:{CP['bg4']};color:{CP['text_primary']};}}"
        )
        btn_close.clicked.connect(dlg.accept)

        btn_apply = QPushButton("↩  Remplacer le texte")
        btn_apply.setFixedHeight(36)
        btn_apply.setStyleSheet(
            f"QPushButton{{background:{CP['accent2']};color:#fff;"
            f"border:none;border-radius:7px;font-size:11px;font-weight:700;padding:0 20px;}}"
            f"QPushButton:hover{{background:#9d8fff;}}"
        )

        def _do_apply():
            self._push_undo()
            self._set_editor_text(text)
            if self._current is not None:
                self._current["formatted_content"] = text
            self._ai_progress_lbl.setText("Texte remplacé ✓")
            self._btn_undo_action.setVisible(True)
            self._btn_reopen_window.setVisible(False)
            self._last_format_result = ""
            self._last_result_kind = ""
            dlg.accept()

        btn_apply.clicked.connect(_do_apply)

        btn_row.addWidget(btn_close)
        btn_row.addStretch()
        btn_row.addWidget(btn_apply)
        lay.addLayout(btn_row)
        dlg.exec()

    def _show_log(self, text: str):
        """Affiche un texte de journal dans la zone de résultat (extractions, storyboard…)."""
        self._result_area.setPlainText(text)
        self._result_area.setVisible(True)

    def _apply_result(self):
        result = self._last_format_result
        if result:
            self._push_undo()
            self._set_editor_text(result)
            if self._current is not None:
                self._current["formatted_content"] = result
            self._ai_progress_lbl.setText("Texte remplacé ✓")
            self._btn_reopen_window.setVisible(False)
            self._btn_undo_action.setVisible(True)
            self._last_format_result = ""
            self._last_result_kind = ""

    def _undo_ai_action(self):
        self._on_undo()
        self._btn_undo_action.setVisible(False)
        self._ai_progress_lbl.setText("Action annulée ✓")

    # ── Undo / Redo ───────────────────────────────────────────────────────────

    def _push_undo(self):
        content = self._editor_text.toPlainText()
        self._undo_stack.append(content)
        self._redo_stack.clear()
        self._btn_undo.setEnabled(True)
        self._btn_redo.setEnabled(False)

    def _on_undo(self):
        if not self._undo_stack:
            return
        self._redo_stack.append(self._editor_text.toPlainText())
        self._set_editor_text(self._undo_stack.pop())
        self._btn_undo.setEnabled(bool(self._undo_stack))
        self._btn_redo.setEnabled(True)

    def _on_redo(self):
        if not self._redo_stack:
            return
        self._undo_stack.append(self._editor_text.toPlainText())
        self._set_editor_text(self._redo_stack.pop())
        self._btn_undo.setEnabled(True)
        self._btn_redo.setEnabled(bool(self._redo_stack))

    # ── Versions ──────────────────────────────────────────────────────────────

    def _refresh_version_combo(self):
        self._version_combo.blockSignals(True)
        self._version_combo.clear()
        versions = (self._current or {}).get("versions", [])
        for v in versions:
            saved_at = v.get("saved_at", "")[:16].replace("T", " ")
            name = v.get("name", "").strip()
            label = name if name else f"Version {v['num']}  —  {saved_at}"
            self._version_combo.addItem(label)
        has = bool(versions)
        self._btn_del_version.setEnabled(has)
        self._version_combo.blockSignals(False)

    def _on_version_selected(self, idx: int):
        versions = (self._current or {}).get("versions", [])
        has = bool(versions) and idx >= 0
        self._btn_del_version.setEnabled(has)

    def _on_version_activated(self, idx: int):
        """Charge immédiatement la version sélectionnée par l'utilisateur dans la combo."""
        versions = (self._current or {}).get("versions", [])
        if idx < 0 or idx >= len(versions):
            return
        target = versions[idx]["content"]
        if self._editor_text.toPlainText().strip() == target.strip():
            return  # déjà affiché
        self._push_undo()
        self._set_editor_text(target)
        v = versions[idx]
        label = v.get("name", "").strip() or f"Version {v['num']}"
        self._ai_progress_lbl.setText(f"{label} chargée ✓")

    def _save_version(self):
        if self._current is None:
            self._save(silent=False)
        content = self._editor_text.toPlainText().strip()
        if not content:
            return
        name, ok = QInputDialog.getText(
            self, "Nouvelle version", "Nom de la version :", text=""
        )
        if not ok:
            return
        from datetime import datetime
        versions = list((self._current or {}).get("versions", []))
        num = (versions[-1]["num"] + 1) if versions else 1
        versions.append({
            "num":      num,
            "name":     name.strip(),
            "content":  content,
            "saved_at": datetime.now().isoformat(timespec="seconds"),
        })
        if self._current is None:
            self._current = {}
        self._current["versions"] = versions
        import core.scenario as scenario_api
        self._current = scenario_api.save_scenario(self._current)
        self._refresh_version_combo()
        self._version_combo.setCurrentIndex(len(versions) - 1)
        label = name.strip() if name.strip() else f"Version {num}"
        self._ai_progress_lbl.setText(f"{label} sauvegardée ✓")

    def _load_version(self):
        idx = self._version_combo.currentIndex()
        versions = (self._current or {}).get("versions", [])
        if idx < 0 or idx >= len(versions):
            return
        from PyQt6.QtWidgets import QMessageBox
        reply = QMessageBox.question(
            self, "Charger la version",
            f"Remplacer le texte actuel par la Version {versions[idx]['num']} ?\n"
            "Le contenu actuel sera conservé dans l'historique Annuler.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        self._push_undo()
        self._set_editor_text(versions[idx]["content"])
        self._ai_progress_lbl.setText(f"Version {versions[idx]['num']} chargée ✓")

    def _delete_version(self):
        idx = self._version_combo.currentIndex()
        versions = list((self._current or {}).get("versions", []))
        if idx < 0 or idx >= len(versions):
            return
        v = versions[idx]
        label = v.get("name", "").strip() or f"Version {v['num']}"
        from PyQt6.QtWidgets import QMessageBox
        reply = QMessageBox.question(
            self, "Supprimer la version",
            f"Supprimer définitivement « {label} » ?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        versions.pop(idx)
        if self._current is not None:
            self._current["versions"] = versions
            import core.scenario as scenario_api
            self._current = scenario_api.save_scenario(self._current)
        self._refresh_version_combo()
        self._ai_progress_lbl.setText(f"« {label} » supprimée ✓")

    # ── Tout Générer — pipeline complet ──────────────────────────────────────────

    def _on_generate_all(self):
        """Fenêtre de confirmation, puis pipeline complet si accepté."""
        if not self._get_text():
            self._ai_progress_lbl.setText("Écris d'abord un scénario.")
            return

        # Comptage des éléments existants pour l'estimation
        def _count(mod_fn):
            try: return len(mod_fn())
            except Exception: return 0
        import core.casting as _ca_m
        import core.decors as _dc_m
        import core.accessories as _ac_m
        import core.hmc as _hm_m
        import core.vehicles as _ve_m
        import core.storyboard as _sb_m
        n_chars  = _count(_ca_m.list_characters)
        n_decors = _count(_dc_m.list_decors)
        n_acc    = _count(_ac_m.list_accessories)
        n_hmc    = _count(_hm_m.list_hmc_items)
        n_veh    = _count(_ve_m.list_vehicles)
        n_shots  = _count(_sb_m.list_shots)
        n_elems  = n_chars + n_decors + n_acc + n_hmc + n_veh

        from PyQt6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout as _QHB, QLabel as _QL, QPushButton as _QPB, QFrame as _QF
        dlg = QDialog(self)
        dlg.setWindowTitle("Tout Générer — Confirmation")
        dlg.setFixedWidth(560)
        dlg.setStyleSheet(f"QDialog{{background:{CP['bg1']};}}")
        lay = QVBoxLayout(dlg)
        lay.setContentsMargins(28, 28, 28, 24)
        lay.setSpacing(14)

        _red = CP.get("red", "#ff4f6a")
        t = _QL("⚡  Génération complète du projet")
        t.setStyleSheet(
            f"color:{_red};font-size:16px;font-weight:800;background:transparent;"
        )
        lay.addWidget(t)

        body = _QL(
            "Vous êtes sur le point de lancer la génération complète :\n\n"
            "  ☁  Extraction depuis le scénario (Claude IA)\n"
            "       personnages · décors · accessoires · HMC · véhicules · storyboard\n\n"
            "  ◉  Génération d'images (Nano Banana)\n"
            "       1 image par personnage · 1 image par décor · 1 image par accessoire\n"
            "       1 image par élément HMC · 1 image par véhicule\n\n"
            "  ◈  Génération des Moods storyboard (Flux IA)\n"
            "       1 aperçu par plan storyboard"
        )
        body.setWordWrap(True)
        body.setStyleSheet(
            f"color:{CP['text_primary']};font-size:11px;background:transparent;"
        )
        lay.addWidget(body)

        _s1 = _QF(); _s1.setFixedHeight(1)
        _s1.setStyleSheet(f"background:{CP['border']};")
        lay.addWidget(_s1)

        if n_elems > 0 or n_shots > 0:
            min_c = n_elems * 0.039 + n_shots * 0.06
            max_c = n_elems * 0.15  + n_shots * 0.06
            cost_txt = (
                f"Éléments actuels : {n_chars} personnages · {n_decors} décors · "
                f"{n_acc} accessoires · {n_hmc} HMC · {n_veh} véhicules\n"
                f"Plans storyboard : {n_shots}\n"
                f"Estimation (éléments actuels) : ~${min_c:.2f} — ~${max_c:.2f}\n"
                f"L'extraction peut créer plus d'éléments — le coût final sera plus élevé."
            )
        else:
            cost_txt = (
                "Estimation (sans données actuelles) :\n"
                "  • Images Nano Banana : ~$0.039/image (standard) — $0.15/image (Pro)\n"
                "  • Moods Flux IA : ~$0.06/image\n"
                "  • Extraction Claude IA : < $0.05"
            )

        cost_lbl = _QL(cost_txt)
        cost_lbl.setWordWrap(True)
        cost_lbl.setStyleSheet(
            f"color:{CP['text_secondary']};font-size:10px;font-family:'Consolas',monospace;"
            f"background:{CP['bg2']};border:1px solid {CP['border']};border-radius:6px;"
            f"padding:10px;"
        )
        lay.addWidget(cost_lbl)

        warn = _QL(
            "⚠  Les tarifs sont indicatifs et peuvent varier.\n"
            "Consultez fal.ai pour vérifier les prix actuels avant de lancer."
        )
        warn.setWordWrap(True)
        warn.setStyleSheet(
            f"color:{CP['text_dim']};font-size:10px;font-style:italic;background:transparent;"
        )
        lay.addWidget(warn)

        advice = _QL(
            "💡  La méthode la moins coûteuse\n\n"
            "Identifiez vos éléments manuellement et créez-les un à un dans les onglets "
            "dédiés : Castings pour les personnages, Décors, Accessoires, HMC, Véhicules. "
            "Vous gardez ainsi la main sur chaque génération d'image et ne payez que "
            "ce que vous validez.\n\n"
            "« Tout générer » est pratique pour un premier jet rapide, mais chaque image "
            "générée automatiquement est facturée — le coût peut rapidement devenir élevé "
            "si le scénario contient de nombreux éléments."
        )
        advice.setWordWrap(True)
        advice.setStyleSheet(
            f"color:{CP.get('accent','#7c6af7')};font-size:10px;"
            f"background:rgba(124,106,247,0.08);border:1px solid rgba(124,106,247,0.30);"
            f"border-radius:6px;padding:10px;"
        )
        lay.addWidget(advice)

        _s2 = _QF(); _s2.setFixedHeight(1)
        _s2.setStyleSheet(f"background:{CP.get('red','#ff4f6a')};")
        lay.addWidget(_s2)

        warn_delete = _QL(
            "⚠  ATTENTION — SUPPRESSION PRÉALABLE\n\n"
            "Avant de régénérer, cette opération va d'abord supprimer\n"
            "TOUS les personnages, décors, accessoires, HMC, véhicules\n"
            "et plans storyboard existants.\n\n"
            "Cette action est irréversible. Partez d'un scénario finalisé."
        )
        warn_delete.setWordWrap(True)
        warn_delete.setStyleSheet(
            f"color:{CP.get('red','#ff4f6a')};font-size:10px;font-weight:700;"
            f"background:rgba(255,79,106,0.08);border:1px solid rgba(255,79,106,0.35);"
            f"border-radius:6px;padding:10px;"
        )
        lay.addWidget(warn_delete)

        btn_row = _QHB()
        btn_cancel = _QPB("Annuler")
        btn_cancel.setFixedHeight(38)
        btn_cancel.setStyleSheet(
            f"QPushButton{{background:{CP['bg3']};color:{CP['text_secondary']};"
            f"border:1px solid {CP['border']};border-radius:7px;"
            f"font-size:11px;font-weight:600;padding:0 20px;}}"
            f"QPushButton:hover{{background:{CP['bg4']};color:{CP['text_primary']};}}"
        )
        btn_cancel.clicked.connect(dlg.reject)
        btn_launch = _QPB("⚡  Lancer la génération complète")
        btn_launch.setFixedHeight(38)
        btn_launch.setStyleSheet(
            f"QPushButton{{background:transparent;color:{_red};"
            f"border:1.5px solid {_red};border-radius:7px;"
            f"font-size:11px;font-weight:700;padding:0 20px;}}"
            f"QPushButton:hover{{background:rgba(255,79,106,0.12);}}"
        )
        btn_launch.clicked.connect(dlg.accept)
        btn_row.addWidget(btn_cancel)
        btn_row.addStretch()
        btn_row.addWidget(btn_launch)
        lay.addLayout(btn_row)

        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        self._gen_all_start()

    def _gen_all_start(self):
        text = self._get_text()

        # ── Supprimer tous les éléments existants ─────────────────────────────
        try:
            import core.casting as _ca_m
            import core.decors as _dc_m
            import core.accessories as _ac_m
            import core.hmc as _hm_m
            import core.vehicles as _ve_m
            import core.storyboard as _sb_m
            for c in _ca_m.list_characters(): _ca_m.delete_character(c["id"])
            for d in _dc_m.list_decors():     _dc_m.delete_decor(d["id"])
            for a in _ac_m.list_accessories():_ac_m.delete_accessory(a["id"])
            for h in _hm_m.list_hmc_items():  _hm_m.delete_hmc_item(h["id"])
            for v in _ve_m.list_vehicles():   _ve_m.delete_vehicle(v["id"])
            _sb_m.clear_version_shots()
        except Exception:
            pass

        # ── Extraction + génération images : une fenêtre par catégorie ─────────
        from ui.dialog_extract_generate import ExtractGenerateDialog
        from PyQt6.QtCore import QTimer
        for make_dlg in [
            lambda: ExtractGenerateDialog.for_characters(text, self),
            lambda: ExtractGenerateDialog.for_decors(text, self),
            lambda: ExtractGenerateDialog.for_accessories(text, self),
            lambda: ExtractGenerateDialog.for_hmc(text, self),
            lambda: ExtractGenerateDialog.for_vehicles(text, self),
        ]:
            dlg = make_dlg()
            dlg._auto_close = True
            QTimer.singleShot(150, lambda d=dlg: d._start(generate=True))
            if not dlg.exec():  # 0 = fermé/annulé — stoppe toute la séquence
                return

        # ── Storyboard + moods en arrière-plan ────────────────────────────────
        self._gen_all_workers: list = []
        self._gen_all_elements: dict = {
            "chars": [], "decors": [], "accessories": [], "hmc": [], "vehicles": [],
        }
        self._gen_all_shots: list = []
        self._gen_all_image_queue: list = []
        self._gen_all_error_count = 0
        self._gen_all_queue = [
            self._gen_all_step_storyboard,
            self._gen_all_step_moods,
        ]
        self._set_ai_busy(True)
        self._ai_progress_lbl.setText("Génération complète — Storyboard…")
        if hasattr(self, "_gen_all_progress_bar"):
            self._gen_all_progress_bar.setVisible(True)
            self._gen_all_status_lbl.setVisible(True)
            self._gen_all_status_lbl.setText("Génération du storyboard…")
        self._gen_all_run_next()

    def _gen_all_run_next(self):
        if not self._gen_all_queue:
            self._gen_all_finish()
            return
        self._gen_all_queue.pop(0)()

    def _gen_all_step_error(self, error: str, phase: str):
        self._gen_all_error_count += 1
        self._ai_progress_lbl.setText(f"⚠ Erreur {phase} : {error[:80]} — poursuite…")
        if hasattr(self, "_gen_all_status_lbl"):
            self._gen_all_status_lbl.setText(f"⚠ Erreur {phase} : {error[:80]}")
        self._gen_all_run_next()

    # ── Extractions ───────────────────────────────────────────────────────────

    def _gen_all_step_chars(self):
        from api.screenplay import ExtractCharactersWorker
        self._ai_progress_lbl.setText("Génération complète [1/8] — Personnages…")
        w = ExtractCharactersWorker(self._get_text())
        w.finished.connect(self._gen_all_chars_done)
        w.failed.connect(lambda e: self._gen_all_step_error(e, "Personnages"))
        self._gen_all_workers.append(w); w.start()

    def _gen_all_chars_done(self, items: list):
        import core.casting as casting_api
        for item in items:
            if not item.get("name"): continue
            s = casting_api.save_character({
                "name": item.get("name", ""), "description": item.get("description", ""),
                "role": item.get("role", "Secondaire"), "image_path": "",
                "accessory_ids": [], "hmc_ids": [],
            })
            self._gen_all_elements["chars"].append(s)
        self._gen_all_run_next()

    def _gen_all_step_decors(self):
        from api.screenplay import ExtractDecorsWorker
        self._ai_progress_lbl.setText("Génération complète [2/8] — Décors…")
        w = ExtractDecorsWorker(self._get_text())
        w.finished.connect(self._gen_all_decors_done)
        w.failed.connect(lambda e: self._gen_all_step_error(e, "Décors"))
        self._gen_all_workers.append(w); w.start()

    def _gen_all_decors_done(self, items: list):
        import core.decors as decors_api
        for item in items:
            if not item.get("name"): continue
            s = decors_api.save_decor({
                "name": item.get("name", ""), "prompt": item.get("description", ""),
                "category": item.get("category", "Autre"), "image_path": "", "ref_paths": [],
            })
            self._gen_all_elements["decors"].append(s)
        self._gen_all_run_next()

    def _gen_all_step_accessories(self):
        from api.screenplay import ExtractAccessoriesWorker
        self._ai_progress_lbl.setText("Génération complète [3/8] — Accessoires…")
        w = ExtractAccessoriesWorker(self._get_text())
        w.finished.connect(self._gen_all_accessories_done)
        w.failed.connect(lambda e: self._gen_all_step_error(e, "Accessoires"))
        self._gen_all_workers.append(w); w.start()

    def _gen_all_accessories_done(self, items: list):
        import core.accessories as acc_api
        for item in items:
            if not item.get("name"): continue
            s = acc_api.save_accessory({
                "name": item.get("name", ""), "description": item.get("description", ""),
                "category": item.get("category", "Autre…"), "image_path": "",
            })
            self._gen_all_elements["accessories"].append(s)
        self._gen_all_run_next()

    def _gen_all_step_hmc(self):
        from api.screenplay import ExtractHMCWorker
        self._ai_progress_lbl.setText("Génération complète [4/8] — HMC…")
        w = ExtractHMCWorker(self._get_text())
        w.finished.connect(self._gen_all_hmc_done)
        w.failed.connect(lambda e: self._gen_all_step_error(e, "HMC"))
        self._gen_all_workers.append(w); w.start()

    def _gen_all_hmc_done(self, items: list):
        import core.hmc as hmc_api
        for item in items:
            if not item.get("name"): continue
            s = hmc_api.save_hmc_item({
                "name": item.get("name", ""), "description": item.get("description", ""),
                "hmc_type": item.get("hmc_type", "Habit"), "image_path": "",
                "character_name": item.get("character_name", ""),
            })
            self._gen_all_elements["hmc"].append(s)
        self._gen_all_run_next()

    def _gen_all_step_vehicles(self):
        from api.screenplay import ExtractVehiclesWorker
        self._ai_progress_lbl.setText("Génération complète [5/8] — Véhicules…")
        w = ExtractVehiclesWorker(self._get_text())
        w.finished.connect(self._gen_all_vehicles_done)
        w.failed.connect(lambda e: self._gen_all_step_error(e, "Véhicules"))
        self._gen_all_workers.append(w); w.start()

    def _gen_all_vehicles_done(self, items: list):
        import core.vehicles as veh_api
        for item in items:
            if not item.get("name"): continue
            s = veh_api.save_vehicle({
                "name": item.get("name", ""), "description": item.get("description", ""),
                "category": item.get("category", "Autre"), "image_path": "",
            })
            self._gen_all_elements["vehicles"].append(s)
        self._gen_all_run_next()

    def _gen_all_step_storyboard(self):
        from api.screenplay import GenerateStoryboardWorker
        self._ai_progress_lbl.setText("Génération complète [6/8] — Storyboard…")
        dur = (
            self._dur_min.value() * 60 + self._dur_sec.value()
        ) if self._dur_defined_check.isChecked() else 0
        w = GenerateStoryboardWorker(self._get_text(), dur)
        w.finished.connect(self._gen_all_storyboard_done)
        w.failed.connect(lambda e: self._gen_all_step_error(e, "Storyboard"))
        self._gen_all_workers.append(w); w.start()

    def _gen_all_storyboard_done(self, shots: list):
        try:
            import core.storyboard as sb_api
            sc_id = (self._current or {}).get("id", "")
            vid = sb_api.DEFAULT_VERSION_ID
            sb_api.clear_version_shots(vid)
            for shot in shots:
                try:
                    shot["scenario_id"] = sc_id
                    shot["version_id"] = vid
                    saved = sb_api.save_shot(shot)
                    self._gen_all_shots.append(saved)
                except Exception:
                    self._gen_all_error_count += 1
        except Exception as e:
            self._gen_all_error_count += 1
            self._ai_progress_lbl.setText(f"Erreur storyboard : {str(e)[:80]}")
        self._gen_all_run_next()

    # ── Images ────────────────────────────────────────────────────────────────

    def _gen_all_step_images(self):
        self._ai_progress_lbl.setText("Génération complète [7/8] — Images…")
        self._gen_all_image_queue = (
            [("character",  c) for c in self._gen_all_elements["chars"]]
            + [("decor",    d) for d in self._gen_all_elements["decors"]]
            + [("accessory", a) for a in self._gen_all_elements["accessories"]]
            + [("hmc",       h) for h in self._gen_all_elements["hmc"]]
            + [("vehicle",   v) for v in self._gen_all_elements["vehicles"]]
        )
        self._gen_all_image_total = len(self._gen_all_image_queue)
        self._gen_all_image_done  = 0
        self._gen_all_next_image()

    def _gen_all_next_image(self):
        if not self._gen_all_image_queue:
            self._gen_all_run_next()
            return

        item_type, item = self._gen_all_image_queue.pop(0)
        self._gen_all_image_done += 1
        n, t = self._gen_all_image_done, self._gen_all_image_total
        self._ai_progress_lbl.setText(
            f"Génération complète [7/8] — Image {n}/{t} "
            f"({item_type} : {item.get('name','?')[:28]})"
        )

        from api.nano_banana import GeneratePortraitWorker, GenerateItemWorker, GenerateDecorSheetWorker

        if item_type == "character":
            prompt = item.get("description") or item.get("name", "")
            w = GeneratePortraitWorker(prompt, item.get("name", ""),
                                       gen_mode="classic", num_images=1)
            def _done_portrait(p, _s, _i=item):
                img = p or _s  # portrait_path toujours "", sheet_path = image réelle
                if img:
                    import core.casting as _c; _i["image_path"] = img; _c.save_character(_i)
                self._gen_all_next_image()
            w.finished.connect(_done_portrait)
            w.failed.connect(lambda _e: (
                self.__dict__.update({"_gen_all_error_count": self._gen_all_error_count + 1}),
                self._gen_all_next_image(),
            ))
        else:
            _subdir_map = {
                "decor": ("decors", "decors", "location"),
                "accessory": ("accessories", "accessories", "accessory"),
                "hmc": ("hmc", "hmc", "outfit/makeup/hair"),
                "vehicle": ("vehicles", "vehicles", "vehicle"),
            }
            _api_map = {
                "decor": "core.decors",
                "accessory": "core.accessories",
                "hmc": "core.hmc",
                "vehicle": "core.vehicles",
            }
            _save_map = {
                "decor": "save_decor",
                "accessory": "save_accessory",
                "hmc": "save_hmc_item",
                "vehicle": "save_vehicle",
            }
            subdir, _, hint = _subdir_map.get(item_type, ("accessories", "", ""))
            prompt_key = "prompt" if item_type == "decor" else "description"
            prompt = item.get(prompt_key) or item.get("name", "")
            _mod  = _api_map.get(item_type, "core.accessories")
            _sfn  = _save_map.get(item_type, "save_accessory")
            if item_type == "decor":
                w = GenerateDecorSheetWorker(prompt, item.get("name", ""), num_images=1)
            else:
                w = GenerateItemWorker(prompt, item.get("name", ""),
                                       subdir=subdir, num_images=1, subject_hint=hint)
            def _done_item(p, _i=item, _m=_mod, _f=_sfn):
                if p:
                    import importlib; m = importlib.import_module(_m)
                    _i["image_path"] = p; getattr(m, _f)(_i)
                self._gen_all_next_image()
            w.finished.connect(_done_item)
            w.failed.connect(lambda _e: (
                self.__dict__.update({"_gen_all_error_count": self._gen_all_error_count + 1}),
                self._gen_all_next_image(),
            ))

        self._gen_all_workers.append(w)
        w.start()

    # ── Moods ─────────────────────────────────────────────────────────────────

    def _gen_all_step_moods(self):
        self._ai_progress_lbl.setText("Génération complète [8/8] — Moods…")
        shots = self._gen_all_shots
        if not shots:
            try:
                import core.storyboard as sb_api
                shots = sb_api.list_shots()
            except Exception:
                pass
        if not shots:
            self._gen_all_run_next()
            return
        from api.apercu import MoodBatchWorker
        w = MoodBatchWorker(shots)
        w.shot_progress.connect(lambda cur, tot, msg:
            self._ai_progress_lbl.setText(
                f"Génération complète [8/8] — Mood {cur}/{tot} : {msg}"
            )
        )
        w.shot_failed.connect(lambda _sid, _e:
            self.__dict__.update({"_gen_all_error_count": self._gen_all_error_count + 1})
        )
        w.all_done.connect(self._gen_all_run_next)
        self._gen_all_workers.append(w); w.start()

    def _gen_all_finish(self):
        self._set_ai_busy(False)
        errs = self._gen_all_error_count
        try:
            import core.casting as _ca_m, core.decors as _dc_m
            import core.accessories as _ac_m, core.hmc as _hm_m, core.vehicles as _ve_m
            n_chars  = len(_ca_m.list_characters())
            n_decors = len(_dc_m.list_decors())
            n_acc    = len(_ac_m.list_accessories())
            n_hmc    = len(_hm_m.list_hmc_items())
            n_veh    = len(_ve_m.list_vehicles())
        except Exception:
            n_chars = n_decors = n_acc = n_hmc = n_veh = 0
        msg = (
            f"✓  Génération complète terminée — "
            f"{n_chars} personnages · {n_decors} décors · "
            f"{n_acc} accessoires · {n_hmc} HMC · {n_veh} véhicules · "
            f"{len(self._gen_all_shots)} plans"
        )
        if errs:
            msg += f" ({errs} erreur{'s' if errs > 1 else ''})"
        self._ai_progress_lbl.setText(msg)
        if hasattr(self, "_gen_all_progress_bar"):
            self._gen_all_progress_bar.setVisible(False)
            self._gen_all_status_lbl.setText(msg)
        self._btn_goto_storyboard.setVisible(True)
        self._gen_all_workers.clear()

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    def showEvent(self, e):
        super().showEvent(e)
        if self._stack.currentIndex() == 0:
            self._refresh_recent()
