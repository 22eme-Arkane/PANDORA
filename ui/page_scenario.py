import os
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTextEdit, QLineEdit, QFrame, QScrollArea, QFileDialog,
    QMessageBox, QStackedWidget, QApplication, QProgressBar, QSpinBox,
    QComboBox, QSlider, QCheckBox, QInputDialog,
)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from core.i18n import translate
from core.worker import abandon_thread
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
        self._arrange_intensity_value: int = 5  # managed inside ArrangeSessionDialog
        self._last_result_kind: str = ""   # "format" | "arrange" | "refs"
        self._last_ref_analysis: str = ""
        self._ref_images: list[str] = []
        self._ref_enriched: bool = False   # scénario déjà enrichi avec l'analyse courante ?
        # Musiques du set (clip) — analysées (BPM/énergie/drops) pour caler le
        # découpage, exactement comme dans PANDORA | Live (moteur partagé librosa).
        self._music_tracks: list[dict] = []   # [{path,name,bpm,duration,energy,drops}]
        self._music_worker = None
        self._music_mode: str = "clip"        # "film" (moments clés) | "clip" (début→fin)
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
        topbar.setFixedHeight(60)   # hauteur STANDARD des bandeaux (alignement assistant)
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

        # ── Sauvegarder / Ouvrir le scénario (fichiers physiques, dossier Scénario) ──
        _scn_sep = QFrame()
        _scn_sep.setFixedSize(1, 24)
        _scn_sep.setStyleSheet(f"background:{CP['border']};")
        tl.addWidget(_scn_sep)

        _yellow, _blue = "#f5c518", "#4aa3ff"
        self._btn_scn_save = QPushButton("💾  Sauvegarder")
        self._btn_scn_save.setFixedHeight(30)
        self._btn_scn_save.setToolTip("Sauvegarder ce scénario sous un nom (dossier Scénario du projet)")
        self._btn_scn_save.setStyleSheet(
            f"QPushButton{{background:transparent;color:{_yellow};"
            f"border:1px solid {_yellow};border-radius:6px;font-size:10px;font-weight:700;padding:0 12px;}}"
            f"QPushButton:hover{{background:rgba(245,197,24,0.12);}}"
        )
        self._btn_scn_save.clicked.connect(self._on_save_scenario_file)
        tl.addWidget(self._btn_scn_save)

        self._btn_scn_open = QPushButton("📂  Ouvrir")
        self._btn_scn_open.setFixedHeight(30)
        self._btn_scn_open.setToolTip("Ouvrir un scénario sauvegardé")
        self._btn_scn_open.setStyleSheet(
            f"QPushButton{{background:transparent;color:{_blue};"
            f"border:1px solid {_blue};border-radius:6px;font-size:10px;font-weight:700;padding:0 12px;}}"
            f"QPushButton:hover{{background:rgba(74,163,255,0.12);}}"
        )
        self._btn_scn_open.clicked.connect(self._on_open_scenario_file)
        tl.addWidget(self._btn_scn_open)

        # ── Style visuel (top bar, après les boutons de version) ──────────────
        _style_sep_top = QFrame()
        _style_sep_top.setFixedSize(1, 24)
        _style_sep_top.setStyleSheet(f"background:{CP['border']};")
        tl.addWidget(_style_sep_top)

        import core.style as _sc_style_mod
        self._film_style_combo = QComboBox()
        self._film_style_combo.addItem("— Style —", "")
        _cur_grp_sc = None
        for _s in _sc_style_mod.STYLES:
            _g = _s.get("group", "")
            if _g != _cur_grp_sc:
                _cur_grp_sc = _g
                _gi = next((g for g in _sc_style_mod.GROUPS if g["key"] == _g), None)
                if _gi:
                    self._film_style_combo.addItem(
                        f"  {_gi['icon']}  {translate(_gi['name']).upper()}", "__sep__"
                    )
                    _sep_i = self._film_style_combo.model().item(
                        self._film_style_combo.count() - 1
                    )
                    _sep_i.setEnabled(False)
                    _sep_i.setForeground(QColor(CP.get("accent2", CP.get("accent", "#7c6bff"))))
            self._film_style_combo.addItem(f"    {_s['icon']}  {translate(_s['name'])}", _s["key"])
        self._film_style_combo.setFixedHeight(30)
        self._film_style_combo.setMinimumWidth(140)
        self._film_style_combo.setMaximumWidth(200)
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
        tl.addWidget(self._film_style_combo)

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
        self._editor_text.setPlaceholderText(translate(
            "Écris ton scénario ici…\n\n"
            "INT. LIEU — JOUR\n\n"
            "Description de la scène…\n\n"
            "PERSONNAGE\n"
            "Dialogue du personnage."
        ))
        _tw_font = QFont("Courier New", 14)
        _tw_font.setStyleHint(QFont.StyleHint.TypeWriter)
        self._editor_text.setFont(_tw_font)
        self._editor_text.setStyleSheet(
            f"QTextEdit{{background:{CP['bg0']};border:none;"
            f"color:{CP['text_primary']};}}"
        )
        # Marges DANS le document (pas en padding CSS : le padding repoussait la
        # scrollbar à 120 px du bord — refonte 2026-06-12, portée depuis Live)
        self._editor_text.document().setDocumentMargin(48)
        self._editor_text.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        # Colonne de lecture centrée (largeur max) : texte aligné à GAUCHE dans une
        # colonne centrée sur la page → lignes lisibles au lieu de traverser tout
        # l'écran (retour Matthieu 2026-07-06 : « bloc indigeste, lignes trop longues »).
        from ui.widgets import install_reading_column
        install_reading_column(self._editor_text, max_width=820, center=True)
        self._editor_text.textChanged.connect(self._schedule_autosave)
        self._editor_text.textChanged.connect(self._update_dur_estimate)

        # ── Deux onglets : Scénario (édition) / Mise en page PANDORA (optimisé) ──
        # Comme dans PANDORA | Live : la mise en page PANDORA s'écrit dans son
        # propre onglet et NE touche JAMAIS au scénario.
        from PyQt6.QtWidgets import QTabWidget
        self._editor_tabs = QTabWidget()
        # documentMode=False : sinon la barre d'onglets occupe toute la largeur et
        # « alignment:center » n'a aucun effet (onglets collés à gauche).
        self._editor_tabs.setDocumentMode(False)
        self._editor_tabs.tabBar().setExpanding(False)
        self._editor_tabs.setStyleSheet(
            # Ligne de base sous la barre d'onglets sur TOUTE la largeur : les
            # onglets centrés « reposent » dessus au lieu de flotter au milieu.
            f"QTabWidget::pane{{border:none;border-top:1px solid {CP['border']};}}"
            # Onglets CENTRÉS dans la fenêtre (esprit du dashboard du bas)
            "QTabWidget::tab-bar{alignment:center;}"
            # Fond transparent : pas de pastille grise isolée sur le bg0.
            f"QTabBar::tab{{background:transparent;color:{CP['text_secondary']};"
            f"padding:6px 18px;border:none;font-size:11px;font-weight:700;}}"
            f"QTabBar::tab:selected{{color:{CP['accent']};"
            f"border-bottom:2px solid {CP['accent']};}}"
            f"QTabBar::tab:disabled{{color:{CP['text_dim']};}}"
        )
        self._editor_tabs.addTab(self._editor_text, translate("Scénario"))

        self._layout_view = QTextEdit()
        # Éditable : la mise en page PANDORA peut être retouchée à la main (les
        # éditions sont persistées via autosave → champ layout_content).
        self._layout_view.setReadOnly(False)
        self._layout_view.setFont(_tw_font)
        self._layout_view.setStyleSheet(
            f"QTextEdit{{background:{CP['bg0']};border:none;color:{CP['text_primary']};}}"
        )
        # Même présentation que l'onglet Scénario : colonne de lecture centrée
        # (texte aligné à gauche, colonne centrée sur la page) — les deux onglets
        # sont identiques et lisibles.
        self._layout_view.document().setDocumentMargin(48)
        self._layout_view.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        install_reading_column(self._layout_view, max_width=820, center=True)
        self._layout_view.setPlaceholderText(translate(
            "Clique « Mise en page PANDORA » (panneau de droite) pour générer ici la "
            "version optimisée pour les moteurs. Ton scénario, lui, reste intact "
            "dans l'onglet Scénario."
        ))
        self._layout_view.textChanged.connect(self._schedule_autosave)
        self._editor_tabs.addTab(self._layout_view, translate("Mise en page PANDORA"))
        self._editor_tabs.setTabEnabled(1, False)   # grisé tant qu'aucune mise en page

        main.addWidget(self._editor_tabs, 1)

        # Right panel
        right_sep = QFrame()
        right_sep.setFixedWidth(1)
        right_sep.setStyleSheet(f"background:{CP['border']};")
        main.addWidget(right_sep)

        main.addWidget(self._build_right_panel())

        outer.addLayout(main, 1)
        return w

    def _build_film_strip(self) -> QWidget:
        """Bande de configuration — Durée du film (visible en permanence au-dessus de l'éditeur)."""
        strip = QWidget()
        strip.setFixedHeight(46)
        strip.setStyleSheet(
            f"background:{CP['bg1']};border-bottom:1px solid {CP['border']};"
        )
        sl = QHBoxLayout(strip)
        sl.setContentsMargins(24, 0, 24, 0)
        sl.setSpacing(10)

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
            btn.setFixedHeight(58)   # 2 lignes de description (word-wrap) sans troncature
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
            txt_lbl = QLabel(translate(label))   # translate() rebaptise aussi « Claude »
            txt_lbl.setStyleSheet(
                f"color:{CP['text_primary']};font-size:10px;font-weight:700;"
                f"background:transparent;border:none;"
            )
            title_row.addWidget(ico_lbl)
            title_row.addWidget(txt_lbl)
            title_row.addStretch()
            sub_lbl = QLabel(translate(sub))
            sub_lbl.setWordWrap(True)   # 2 lignes au lieu de tronquer la description
            sub_lbl.setStyleSheet(
                f"color:{CP['text_dim']};font-size:8px;background:transparent;border:none;"
            )
            bl.addLayout(title_row)
            bl.addWidget(sub_lbl)
            btn.clicked.connect(callback)
            return btn

        # ── helper: section toggle header ─────────────────────────────────────
        # En-têtes de SECTION (« menu ») distincts des sous-items (« sous-menu »)
        # par la COULEUR SEULE : fond plus sombre + texte teal en MAJUSCULES.
        # (Barre d'accent gauche RETIRÉE le 2026-07-03 — demande Matthieu : les
        # « crochets » sur le bord faisaient brouillon ; la distinction voulue
        # était un simple changement de couleur.)
        _toggle_ss = (
            f"QPushButton{{background:{CP['bg3']};color:{CP['accent']};"
            f"border:none;"
            f"border-top:1px solid {CP['border']};border-bottom:1px solid {CP['border']};"
            f"font-size:11px;font-weight:800;text-align:left;"
            f"padding:9px 16px;letter-spacing:0.8px;}}"
            f"QPushButton:hover{{background:{CP['bg4']};color:{CP['text_primary']};}}"
            f"QPushButton:checked{{background:{CP['bg3']};color:{CP['accent']};}}"
        )

        def _make_toggle(title: str, container: QWidget, expanded: bool = True):
            _t = translate(title)
            btn = QPushButton(f"{'▼' if expanded else '▶'}  {_t}")
            btn.setCheckable(True)
            btn.setChecked(expanded)
            btn.setStyleSheet(_toggle_ss)
            container.setVisible(expanded)
            def _tog(checked, b=btn, c=container, t=_t):
                c.setVisible(checked)
                b.setText(f"{'▼' if checked else '▶'}  {t}")
            btn.toggled.connect(_tog)
            return btn

        def _section_container():
            c = QWidget()
            c.setStyleSheet(f"background:{CP['bg1']};")
            lay = QVBoxLayout(c)
            # Marges horizontales à 0 : les cartes vont jusqu'au bord, alignées
            # sur les en-têtes de section pleine largeur (pas de retrait de 16 px).
            # Marges verticales resserrées (retour Matthieu : trop d'espace entre
            # l'ajout de morceau, l'analyse et les en-têtes de section).
            lay.setContentsMargins(0, 4, 0, 4)
            lay.setSpacing(4)
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

        # ── Section 0 : Références visuelles ──────────────────────────────────
        c_refs, l_refs = _section_container()

        _refs_scroll = QScrollArea()
        _refs_scroll.setFixedHeight(68)
        _refs_scroll.setWidgetResizable(True)
        _refs_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        _refs_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        _refs_scroll.setStyleSheet(
            "QScrollArea{border:none;background:transparent;}"
            f"QScrollBar:horizontal{{background:{CP['bg2']};height:3px;border-radius:2px;}}"
            f"QScrollBar::handle:horizontal{{background:{CP['border_bright']};border-radius:2px;}}"
            f"QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal{{width:0;}}"
        )
        self._refs_container_w = QWidget()
        self._refs_container_w.setStyleSheet(f"background:{CP['bg2']};border-radius:8px;")
        self._refs_hbox = QHBoxLayout(self._refs_container_w)
        self._refs_hbox.setContentsMargins(8, 4, 8, 4)
        self._refs_hbox.setSpacing(8)
        _refs_scroll.setWidget(self._refs_container_w)
        l_refs.addWidget(_refs_scroll)

        self._btn_analyze_refs = _ai_btn(
            "🔍", "Analyser avec Claude",
            "Décrypte les images pour enrichir le scénario",
            self._on_analyze_refs,
        )
        l_refs.addWidget(self._btn_analyze_refs)

        tog_refs = _make_toggle("🎨  Références visuelles", c_refs, expanded=False)

        self._refresh_refs_display()

        # ── Section 0bis : Musiques du set (clip) ─────────────────────────────
        # Comme dans PANDORA | Live : on ajoute des morceaux, librosa analyse
        # BPM + énergie + drops → timeline injectée dans Claude pour caler le
        # découpage du storyboard sur la musique (clips).
        c_music, l_music = _section_container()

        _music_scroll = QScrollArea()
        _music_scroll.setFixedHeight(68)
        _music_scroll.setWidgetResizable(True)
        _music_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        _music_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        _music_scroll.setStyleSheet(
            "QScrollArea{border:none;background:transparent;}"
            f"QScrollBar:horizontal{{background:{CP['bg2']};height:3px;border-radius:2px;}}"
            f"QScrollBar::handle:horizontal{{background:{CP['border_bright']};border-radius:2px;}}"
            f"QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal{{width:0;}}"
        )
        self._music_container_w = QWidget()
        self._music_container_w.setStyleSheet(f"background:{CP['bg2']};border-radius:8px;")
        self._music_hbox = QHBoxLayout(self._music_container_w)
        self._music_hbox.setContentsMargins(8, 4, 8, 4)
        self._music_hbox.setSpacing(8)
        _music_scroll.setWidget(self._music_container_w)
        l_music.addWidget(_music_scroll)

        self._btn_analyze_music = _ai_btn(
            "♫", "Analyser la musique (BPM + drops)",
            "Cale le découpage sur la musique (tempo + temps forts)",
            self._on_analyze_music,
        )
        l_music.addWidget(self._btn_analyze_music)

        tog_music = _make_toggle("♫  Musique du film", c_music, expanded=False)

        self._refresh_music_display()

        # ── Section : Scénario (analyse + co-écriture du scénario) ─────────────
        c_scen, l_scen = _section_container()

        self._btn_arrange = _ai_btn(
            "🔎", "Analyse", "Analyse la structure narrative du scénario", self._on_arrange,
        )
        self._btn_coecriture = _ai_btn(
            "💬", "Co-écriture", "Dialogue avec l'assistant pour réécrire le scénario", self._on_coecriture,
        )
        l_scen.addWidget(self._btn_arrange)
        l_scen.addWidget(self._btn_coecriture)
        tog_scen = _make_toggle("📖  Scénario", c_scen, expanded=True)

        # ── Section : Finalisation (mise en page + co-écriture des plans) ──────
        # Étape à ne pas sauter : préparer/optimiser les plans AVANT de générer le
        # storyboard. « Mise en page PANDORA » structure le scénario en plans ;
        # « Co-écriture des plans » les réécrit un par un (fenêtre dédiée).
        c_final, l_final = _section_container()

        self._btn_format = _ai_btn(
            "📝", "Mise en page PANDORA", "Structure le scénario en blocs plans optimisés pour PANDORA", self._on_format,
        )
        self._btn_plan_coedit = _ai_btn(
            "✍", "Co-écriture des plans", "Réécrire/enrichir chaque plan un par un avant le storyboard", self._on_plan_coedit,
        )
        l_final.addWidget(self._btn_format)
        l_final.addWidget(self._btn_plan_coedit)
        tog_final = _make_toggle("🎯  Finalisation", c_final, expanded=True)

        # ── Section 2 : Générer depuis le scénario (repliée par défaut) ───────
        c_gen, l_gen = _section_container()

        self._btn_gen_characters = _ai_btn(
            "🎭", "Générer les personnages", "Identifier les personnages depuis le scénario",
            self._on_gen_characters,
        )
        self._btn_gen_decors = _ai_btn(
            "🏠", "Générer les décors + plan",
            "Identifier les décors depuis le scénario et générer leur plan vu de dessus "
            "(Mise en scène / Plan de feu)",
            self._on_gen_decors,
        )
        self._btn_gen_accessories = _ai_btn(
            "🧰", "Générer les accessoires", "Identifier les accessoires depuis le scénario",
            self._on_gen_accessories,
        )
        self._btn_gen_hmc = _ai_btn(
            "💄", "Générer le HMC", "Identifier les éléments HMC depuis le scénario",
            self._on_gen_hmc,
        )
        self._btn_gen_vehicles = _ai_btn(
            "🚗", "Générer les véhicules", "Identifier les véhicules depuis le scénario",
            self._on_gen_vehicles,
        )
        self._btn_storyboard = _ai_btn(
            "🎬", "Générer le storyboard", "Importe les plans dans Storyboard",
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
        tog_gen = _make_toggle("⚡  Générer depuis le scénario", c_gen, expanded=True)

        # ── Ordre visuel du panneau droit (haut → bas), demande Matthieu 2026-07-06 :
        # Scénario, Finalisation, Musique, Références, Générer (bas).
        for _tog, _cont in (
            (tog_scen,  c_scen),
            (tog_final, c_final),
            (tog_music, c_music),
            (tog_refs,  c_refs),
            (tog_gen,   c_gen),
        ):
            sc_lay.addWidget(_tog)
            sc_lay.addWidget(_cont)

        sc_lay.addStretch()
        scroll.setWidget(scroll_content)
        root_lay.addWidget(scroll, 1)

        # ══════════════════════════════════════════════════════════════════════
        # Zone basse fixe — progress + Résultat Claude
        # ══════════════════════════════════════════════════════════════════════
        bottom = QWidget()
        bottom.setStyleSheet(f"background:{CP['bg1']};")
        b_lay = QVBoxLayout(bottom)
        b_lay.setContentsMargins(0, 8, 0, 12)   # aligné bord à bord avec les sections
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
        ga_lay.setContentsMargins(0, 10, 0, 12)   # « Tout générer » aligné bord à bord
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
        _ga_btn_sub.setWordWrap(True)   # sinon tronqué (liste plus longue que le bouton)
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
        """Écrit le texte dans l'éditeur (colonne de lecture bornée, texte CENTRÉ façon
        Word, respiration entre paragraphes)."""
        self._editor_text.setPlainText(text)
        from ui.widgets import apply_paragraph_spacing
        apply_paragraph_spacing(self._editor_text)

    def _apply_layout(self, text: str):
        """Écrit la Mise en page PANDORA dans son onglet dédié — le Scénario
        (onglet 1) reste INTACT. Active l'onglet et l'affiche."""
        if not text:
            return
        self._layout_view.setPlainText(text)
        from ui.widgets import apply_paragraph_spacing
        apply_paragraph_spacing(self._layout_view)   # centré + respiration (façon Word)
        if hasattr(self, "_editor_tabs"):
            self._editor_tabs.setTabEnabled(1, True)
            self._editor_tabs.setCurrentIndex(1)
        if self._current is not None:
            self._current["layout_content"] = text

    def _clear_layout(self):
        """Vide la Mise en page PANDORA et désactive son onglet."""
        if hasattr(self, "_layout_view"):
            self._layout_view.clear()
        if hasattr(self, "_editor_tabs"):
            self._editor_tabs.setTabEnabled(1, False)
            self._editor_tabs.setCurrentIndex(0)

    def _restore_layout(self, text: str):
        """Recharge la Mise en page PANDORA depuis le scénario (onglet activé si présente)."""
        if not hasattr(self, "_layout_view"):
            return
        self._layout_view.setPlainText(text or "")
        from ui.widgets import apply_paragraph_spacing
        apply_paragraph_spacing(self._layout_view)   # centré + respiration (façon Word)
        if hasattr(self, "_editor_tabs"):
            self._editor_tabs.setTabEnabled(1, bool((text or "").strip()))
            self._editor_tabs.setCurrentIndex(0)

    def _new_scenario(self):
        from core import context as _ctx
        import core.project as _project
        _pdata = _project.load_project(_ctx.get_project_path())
        _pname = _pdata.get("name", "") if _pdata else ""
        self._current = {}
        self._undo_stack.clear()
        self._redo_stack.clear()
        self._title_edit.setText(_pname)
        self._set_editor_text("")
        self._clear_layout()
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
        self._title_edit.setText(sc.get("title", ""))
        content = sc.get("formatted_content") or sc.get("raw_content", "")
        self._set_editor_text(content)
        # Mise en page PANDORA — restaurée dans son onglet dédié (scénario intact)
        self._restore_layout(sc.get("layout_content", ""))
        dur         = sc.get("duration_secs", 0)
        dur_defined = sc.get("duration_defined", False) or dur > 0
        self._dur_defined_check.setChecked(dur_defined)
        self._dur_min.setValue(dur // 60 if dur > 0 else 90)
        self._dur_sec.setValue(dur % 60 if dur > 0 else 0)
        self._on_dur_defined_toggled(dur_defined)
        film_style = sc.get("film_style", "")
        idx = self._film_style_combo.findData(film_style) if film_style else -1
        self._film_style_combo.setCurrentIndex(idx if idx > 0 else 0)
        self._music_tracks = list(sc.get("music_tracks") or [])
        self._music_mode = sc.get("music_mode") or "clip"
        if hasattr(self, "_music_hbox"):
            self._refresh_music_display()
        # Analyse d'arrangement persistée → « Analyse & co-écriture » la rouvrira
        # sans nouvel appel API (et le bouton Rouvrir refonctionne au redémarrage).
        saved_analysis = (sc.get("arrange_analysis") or "").strip()
        if saved_analysis:
            self._last_analysis = saved_analysis
            self._last_result_kind = "arrange"
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
        _est = translate("Estimé :")
        if mins == 0 and secs == 0:
            self._dur_estimate_lbl.setText(translate("Estimé : —"))
        elif mins == 0:
            self._dur_estimate_lbl.setText(f"{_est} ~{secs}s")
        elif secs == 0:
            self._dur_estimate_lbl.setText(f"{_est} ~{mins}m")
        else:
            self._dur_estimate_lbl.setText(f"{_est} ~{mins}m{secs:02d}")

    # ── Musiques du set (clip) — analyse BPM/drops, comme PANDORA | Live ────────

    def _refresh_music_display(self):
        while self._music_hbox.count():
            item = self._music_hbox.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        btn_add = QPushButton("+")
        btn_add.setFixedSize(60, 60)
        btn_add.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_add.setToolTip(translate(
            "Ajouter des morceaux (mp3/wav…)\nClaude calera le découpage sur leur BPM et leurs drops."))
        btn_add.setStyleSheet(f"""
            QPushButton{{
                background:transparent;color:{CP['text_dim']};
                border:1px dashed {CP['border_bright']};border-radius:8px;
                font-size:24px;font-weight:300;padding:0;
            }}
            QPushButton:hover{{color:{CP['accent']};border-color:{CP['accent']};
                background:rgba(78,205,196,0.08);}}
            QPushButton:pressed{{background:rgba(78,205,196,0.16);}}
        """)
        btn_add.clicked.connect(self._on_add_music)
        self._music_hbox.addWidget(btn_add)
        for i, t in enumerate(self._music_tracks):
            self._music_hbox.addWidget(self._make_music_chip(i, t))
        self._music_hbox.addStretch()

    def _make_music_chip(self, index: int, track: dict) -> QWidget:
        container = QWidget()
        container.setFixedSize(132, 60)
        container.setStyleSheet(
            f"background:{CP['bg3']};border:1px solid {CP['border']};border-radius:8px;")
        lay = QVBoxLayout(container)
        lay.setContentsMargins(8, 6, 8, 6)
        lay.setSpacing(1)
        name = track.get("name", "?")
        short = name if len(name) <= 16 else name[:15] + "…"
        name_lbl = QLabel("♫ " + short)
        name_lbl.setToolTip(name)
        name_lbl.setStyleSheet(
            f"color:{CP['text_primary']};font-size:9px;font-weight:700;"
            "background:transparent;border:none;")
        bpm = track.get("bpm", 0)
        if bpm:
            info = f"{bpm:.0f} BPM · {int(track.get('duration',0)//60)}:{int(track.get('duration',0)%60):02d}  ✎"
            info_color = CP["accent"]
        else:
            info = translate("non analysé") + "  ✎"
            info_color = CP["text_dim"]
        info_btn = QPushButton(info)
        info_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        info_btn.setToolTip(translate("Corriger le BPM (tap-tempo, ÷2 / ×2)"))
        info_btn.setStyleSheet(
            f"QPushButton{{color:{info_color};font-size:8px;font-weight:700;"
            f"background:transparent;border:none;text-align:left;padding:0;}}"
            f"QPushButton:hover{{color:{CP['accent']};}}")
        info_btn.clicked.connect(lambda checked=False, i=index: self._edit_bpm(i))
        energy = track.get("energy", "")
        en_lbl = QLabel(energy[:16] if energy else "")
        en_lbl.setStyleSheet(
            f"color:{CP['text_dim']};font-size:8px;background:transparent;border:none;")
        lay.addWidget(name_lbl)
        lay.addWidget(info_btn)
        lay.addWidget(en_lbl)
        btn_rm = QPushButton("✕", container)
        btn_rm.setGeometry(114, 2, 16, 16)
        btn_rm.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_rm.setStyleSheet(
            f"QPushButton{{background:{CP['bg2']};color:{CP['text_primary']};"
            f"border:1px solid {CP['border_bright']};border-radius:3px;"
            f"font-size:9px;font-weight:700;padding:0;}}"
            f"QPushButton:hover{{background:{CP['red']};color:#fff;border-color:{CP['red']};}}"
        )
        btn_rm.clicked.connect(lambda checked=False, i=index: self._remove_music(i))
        return container

    def _remove_music(self, index: int):
        if 0 <= index < len(self._music_tracks):
            self._music_tracks.pop(index)
            self._refresh_music_display()
            self._save(silent=True)

    def _edit_bpm(self, index: int):
        """Correction manuelle du BPM : spinbox + ÷2 / ×2 (erreurs d'octave) + tap-tempo.
        librosa confond parfois 64↔128 BPM → indispensable pour caler le découpage."""
        if not (0 <= index < len(self._music_tracks)):
            return
        import time
        from PyQt6.QtWidgets import (
            QDialog, QVBoxLayout, QHBoxLayout, QLabel, QDoubleSpinBox, QPushButton,
        )
        track = self._music_tracks[index]
        dlg = QDialog(self)
        dlg.setWindowTitle(translate("Corriger le BPM"))
        dlg.setFixedWidth(360)
        dlg.setStyleSheet(f"QDialog{{background:{CP['bg1']};}}")
        lay = QVBoxLayout(dlg)
        lay.setContentsMargins(20, 18, 20, 18)
        lay.setSpacing(12)

        head = QLabel("♫ " + track.get("name", "?"))
        head.setStyleSheet(
            f"color:{CP['text_primary']};font-size:12px;font-weight:700;background:transparent;")
        head.setWordWrap(True)
        lay.addWidget(head)

        row = QHBoxLayout()
        row.setSpacing(8)
        spin = QDoubleSpinBox()
        spin.setRange(30.0, 300.0)
        spin.setDecimals(1)
        spin.setSingleStep(0.5)
        spin.setValue(float(track.get("bpm", 0) or 120.0))
        spin.setSuffix(" BPM")
        spin.setStyleSheet(
            f"QDoubleSpinBox{{background:{CP['bg2']};color:{CP['text_primary']};"
            f"border:1px solid {CP['border']};border-radius:6px;padding:6px 8px;font-size:13px;}}")
        row.addWidget(spin, 1)

        def _mk(txt, fn):
            b = QPushButton(txt)
            b.setFixedSize(44, 34)
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.setStyleSheet(
                f"QPushButton{{background:{CP['bg2']};color:{CP['text_secondary']};"
                f"border:1px solid {CP['border']};border-radius:6px;font-size:11px;font-weight:700;}}"
                f"QPushButton:hover{{background:{CP['bg3']};color:{CP['text_primary']};"
                f"border-color:{CP['border_bright']};}}")
            b.clicked.connect(fn)
            return b
        row.addWidget(_mk("÷2", lambda: spin.setValue(round(spin.value() / 2, 1))))
        row.addWidget(_mk("×2", lambda: spin.setValue(round(spin.value() * 2, 1))))
        lay.addLayout(row)

        # ── Tap-tempo ─────────────────────────────────────────────────────────
        taps: list = []
        tap_lbl = QLabel(translate("Tape en rythme sur la musique…"))
        tap_lbl.setStyleSheet(f"color:{CP['text_dim']};font-size:9px;background:transparent;")
        btn_tap = QPushButton(translate("⊙  Tap tempo"))
        btn_tap.setFixedHeight(40)
        btn_tap.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_tap.setStyleSheet(
            f"QPushButton{{background:transparent;color:{CP['accent']};"
            f"border:1px solid {CP['accent_dim']};border-radius:7px;font-size:12px;font-weight:700;}}"
            f"QPushButton:hover{{background:rgba(78,205,196,0.10);}}"
            f"QPushButton:pressed{{background:rgba(78,205,196,0.20);}}")

        def _on_tap():
            t = time.perf_counter()
            if taps and (t - taps[-1]) > 2.0:
                taps.clear()   # pause trop longue → on repart
            taps.append(t)
            if len(taps) > 8:
                del taps[0]
            if len(taps) >= 2:
                intervals = [taps[i + 1] - taps[i] for i in range(len(taps) - 1)]
                avg = sum(intervals) / len(intervals)
                if avg > 0:
                    val = 60.0 / avg
                    spin.setValue(round(val, 1))
                    tap_lbl.setText(f"{len(taps)} taps → {val:.1f} BPM")
            else:
                tap_lbl.setText(translate("Continue à taper…"))
        btn_tap.clicked.connect(_on_tap)
        lay.addWidget(btn_tap)
        lay.addWidget(tap_lbl)

        brow = QHBoxLayout()
        brow.setSpacing(8)
        brow.addStretch()
        btn_cancel = QPushButton(translate("Annuler"))
        btn_cancel.setFixedHeight(34)
        btn_cancel.setStyleSheet(
            f"QPushButton{{background:transparent;color:{CP['text_secondary']};"
            f"border:1px solid {CP['border']};border-radius:7px;font-size:11px;font-weight:700;padding:0 16px;}}"
            f"QPushButton:hover{{background:{CP['bg2']};color:{CP['text_primary']};}}")
        btn_cancel.clicked.connect(dlg.reject)
        btn_ok = QPushButton(translate("Valider"))
        btn_ok.setFixedHeight(34)
        btn_ok.setStyleSheet(
            f"QPushButton{{background:{CP['accent']};color:#07080f;border:none;"
            f"border-radius:7px;font-size:11px;font-weight:700;padding:0 18px;}}"
            f"QPushButton:hover{{background:#6eded6;}}")
        btn_ok.clicked.connect(dlg.accept)
        brow.addWidget(btn_cancel)
        brow.addWidget(btn_ok)
        lay.addLayout(brow)

        # Sans ça, Entrée dans le spinbox clique « ÷2 » (1er bouton autoDefault)
        # → le BPM saisi est silencieusement divisé par 2.
        from ui.widgets import disable_default_buttons
        disable_default_buttons(dlg)

        if dlg.exec() == QDialog.DialogCode.Accepted:
            track["bpm"] = round(spin.value(), 1)
            self._refresh_music_display()
            self._save(silent=True)
            self._ai_progress_lbl.setText(
                f"BPM ← {track['bpm']:.0f} — {track.get('name','')}")

    def _on_add_music(self):
        paths, _ = QFileDialog.getOpenFileNames(
            self, translate("Ajouter des morceaux"), "",
            "Audio (*.mp3 *.wav *.flac *.ogg *.m4a *.aac);;Tous les fichiers (*)",
        )
        existing = {t.get("path") for t in self._music_tracks}
        added = 0
        for p in paths:
            if p and p not in existing:
                self._music_tracks.append({
                    "path": p, "name": os.path.basename(p),
                    "bpm": 0, "duration": 0, "energy": "", "drops": [],
                })
                added += 1
        if added:
            self._refresh_music_display()
            self._save(silent=True)
            self._ai_progress_lbl.setText(translate(
                "Morceau(x) ajouté(s) — clique « Analyser le set » pour détecter BPM et drops."))

    def _choose_music_mode(self) -> str:
        """Popup AVANT l'analyse : musique de FILM (intégrée à des moments clés)
        ou de CLIP (du début à la fin du scénario). Renvoie "film" / "clip" / ""."""
        from PyQt6.QtWidgets import QDialog, QVBoxLayout, QLabel, QPushButton
        dlg = QDialog(self)
        dlg.setWindowTitle(translate("Type de musique"))
        dlg.setStyleSheet(f"QDialog{{background:{CP['bg1']};}}")
        dlg.setFixedWidth(460)
        lay = QVBoxLayout(dlg)
        lay.setContentsMargins(22, 20, 22, 20)
        lay.setSpacing(12)

        title = QLabel("♫  " + translate("Comment intégrer cette musique ?"))
        title.setStyleSheet(
            f"color:{CP['text_primary']};font-size:14px;font-weight:700;background:transparent;")
        lay.addWidget(title)

        choice = {"v": "", "cur": getattr(self, "_music_mode", "clip")}

        def _card(icon, name, desc, val):
            b = QPushButton()
            b.setAutoDefault(False)
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.setMinimumHeight(66)
            _hl = (val == choice["cur"])
            b.setStyleSheet(
                f"QPushButton{{background:{CP['bg2']};text-align:left;padding:8px 12px;"
                f"border:1px solid {CP['accent'] if _hl else CP['border']};border-radius:8px;}}"
                f"QPushButton:hover{{border-color:{CP['accent_dim']};background:{CP['bg3']};}}")
            bl = QVBoxLayout(b)
            bl.setContentsMargins(6, 6, 6, 6)
            bl.setSpacing(2)
            t = QLabel(f"{icon}  {translate(name)}")
            t.setStyleSheet(
                f"color:{CP['text_primary']};font-size:12px;font-weight:700;"
                f"background:transparent;border:none;")
            d = QLabel(translate(desc))
            d.setWordWrap(True)
            d.setStyleSheet(
                f"color:{CP['text_dim']};font-size:10px;background:transparent;border:none;")
            bl.addWidget(t)
            bl.addWidget(d)
            def _pick():
                choice["v"] = val
                dlg.accept()
            b.clicked.connect(_pick)
            return b

        lay.addWidget(_card(
            "🎬", "Musique de film",
            "Intégrée à des MOMENTS CLÉS du film (climax, transitions) — pas en continu.",
            "film"))
        lay.addWidget(_card(
            "🎞️", "Musique de clip",
            "Couvre le scénario du DÉBUT À LA FIN — le découpage suit la musique.",
            "clip"))

        cancel = QPushButton(translate("Annuler"))
        cancel.setAutoDefault(False)
        cancel.setFixedHeight(32)
        cancel.setStyleSheet(
            f"QPushButton{{background:transparent;color:{CP['text_dim']};"
            f"border:1px solid {CP['border']};border-radius:7px;font-size:11px;padding:0 16px;}}"
            f"QPushButton:hover{{color:{CP['text_primary']};border-color:{CP['text_primary']};}}")
        cancel.clicked.connect(dlg.reject)
        lay.addWidget(cancel)

        dlg.exec()
        return choice["v"]

    def _on_analyze_music(self):
        if not self._music_tracks:
            self._ai_progress_lbl.setText(translate(
                "Ajoute d'abord des morceaux dans « Musique du film »."))
            return
        mode = self._choose_music_mode()
        if not mode:
            return   # annulé : on ne lance pas l'analyse
        self._music_mode = mode
        self._save(silent=True)
        from core.music_analysis import AnalyzeMusicWorker
        _kind = translate("film") if mode == "film" else translate("clip")
        self._ai_progress_lbl.setText(
            translate("Analyse audio en cours (BPM + drops)…") + f"  [{_kind}]")
        self._music_worker = AnalyzeMusicWorker(self._music_tracks)
        self._open_music_analysis_window(self._music_worker)

    def _open_music_analysis_window(self, worker):
        """Fenêtre d'analyse musicale (comme l'arrangement Claude) : progression
        visible + prévisualisation de la timeline + choix Appliquer / Annuler."""
        from PyQt6.QtWidgets import (
            QDialog, QVBoxLayout, QHBoxLayout, QTextEdit, QProgressBar, QPushButton,
        )
        from core.worker import abandon_thread
        dlg = QDialog(self)
        dlg.setWindowTitle(translate("Analyse musicale du film"))
        dlg.resize(720, 600)
        dlg.setStyleSheet(
            f"QDialog{{background:{CP['bg1']};}}"
            f"QLabel{{background:transparent;color:{CP['text_primary']};}}")
        lay = QVBoxLayout(dlg)
        lay.setContentsMargins(22, 20, 22, 20)
        lay.setSpacing(12)

        hdr = QHBoxLayout()
        title_lbl = QLabel("♫  " + translate("Analyse musicale du film"))
        title_lbl.setStyleSheet(f"color:{CP['text_primary']};font-size:14px;font-weight:700;")
        status_lbl = QLabel(translate("Analyse en cours…"))
        status_lbl.setStyleSheet(
            f"color:{CP['accent']};font-size:10px;font-family:'Consolas',monospace;")
        hdr.addWidget(title_lbl)
        hdr.addStretch()
        hdr.addWidget(status_lbl)
        lay.addLayout(hdr)

        bar = QProgressBar()
        bar.setRange(0, 0)   # indéterminé jusqu'au 1er morceau
        bar.setTextVisible(False)
        bar.setFixedHeight(5)
        bar.setStyleSheet(
            f"QProgressBar{{background:{CP['bg3']};border:none;border-radius:2px;}}"
            f"QProgressBar::chunk{{background:{CP['accent']};border-radius:2px;}}")
        lay.addWidget(bar)

        te = QTextEdit()
        te.setReadOnly(True)
        te.setPlaceholderText(translate("L'analyse apparaît au fil de l'écoute…"))
        te.setStyleSheet(
            f"QTextEdit{{background:{CP['bg2']};border:1px solid {CP['border']};"
            f"border-radius:8px;color:{CP['text_primary']};font-size:11px;"
            f"font-family:'Consolas',monospace;padding:14px;}}")
        lay.addWidget(te, 1)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)
        btn_cancel = QPushButton(translate("Annuler"))
        btn_cancel.setFixedHeight(36)
        btn_cancel.setStyleSheet(
            f"QPushButton{{background:{CP['bg3']};color:{CP['red']};"
            f"border:1px solid {CP['red']};border-radius:7px;font-size:11px;font-weight:600;padding:0 20px;}}"
            f"QPushButton:hover{{background:rgba(255,79,106,0.12);}}")
        btn_apply = QPushButton(translate("✓  Appliquer l'analyse"))
        btn_apply.setFixedHeight(36)
        btn_apply.setEnabled(False)
        btn_apply.setStyleSheet(
            f"QPushButton{{background:{CP['accent']};color:#07080f;border:none;"
            f"border-radius:7px;font-size:11px;font-weight:700;padding:0 22px;}}"
            f"QPushButton:hover{{background:#6eded6;}}"
            f"QPushButton:disabled{{background:{CP['bg3']};color:{CP['text_dim']};"
            f"border:1px solid {CP['border']};}}")
        btn_row.addWidget(btn_cancel)
        btn_row.addStretch()
        btn_row.addWidget(btn_apply)
        lay.addLayout(btn_row)

        _pending = [None]
        _active  = [True]

        def _stop():
            if _active[0]:
                _active[0] = False
                worker.quit()
                abandon_thread(worker)

        def _mmss(s):
            s = max(0, int(s))
            return f"{s // 60}:{s % 60:02d}"

        def _on_prog(i, total, name):
            if not _active[0]:
                return
            bar.setRange(0, total)
            bar.setValue(i)
            status_lbl.setText(f"{i}/{total}")
            te.append(f"[{i}/{total}] {name} — {translate('analyse…')}")

        def _on_done(tracks):
            _active[0] = False
            _pending[0] = tracks
            bar.setRange(0, 100)
            bar.setValue(100)
            status_lbl.setText(translate("Analyse terminée"))
            status_lbl.setStyleSheet(
                f"color:{CP['green']};font-size:10px;font-family:'Consolas',monospace;")
            from core.music_analysis import build_set_timeline
            lines = []
            for t in tracks:
                if t.get("bpm"):
                    lines.append(f"♫ {t.get('name','?')} — {t['bpm']:.0f} BPM · "
                                 f"{_mmss(t.get('duration', 0))}")
                    if t.get("energy"):
                        lines.append(f"   {translate('énergie')} {t['energy']}")
                    drops = t.get("drops", [])
                    if drops:
                        lines.append("   drops: " + ", ".join(_mmss(d) for d in drops))
                else:
                    lines.append(f"♫ {t.get('name','?')} — {translate('non analysé')}")
                lines.append("")
            tl = build_set_timeline(tracks)
            te.setPlainText("\n".join(lines) + (("\n" + tl) if tl else ""))
            btn_apply.setEnabled(True)
            btn_apply.setFocus()

        def _on_fail(msg):
            _active[0] = False
            status_lbl.setText(translate("Erreur"))
            status_lbl.setStyleSheet(
                f"color:{CP['red']};font-size:10px;font-family:'Consolas',monospace;")
            bar.setRange(0, 100)
            bar.setValue(0)
            te.setPlainText(f"{translate('Erreur')} : {msg}")

        def _apply():
            if _pending[0] is not None:
                self._music_tracks = _pending[0]
                self._refresh_music_display()
                self._save(silent=True)
                n = sum(1 for t in _pending[0] if t.get("bpm"))
                self._ai_progress_lbl.setText(
                    f"{n} " + translate("morceau(x) analysé(s) — timeline musicale prête ✓"))
            dlg.accept()

        def _cancel():
            _stop()
            self._ai_progress_lbl.setText(translate("Analyse musicale annulée."))
            dlg.reject()

        btn_cancel.clicked.connect(_cancel)
        btn_apply.clicked.connect(_apply)
        dlg.rejected.connect(_stop)

        worker.progress.connect(_on_prog)
        worker.finished.connect(_on_done)
        worker.failed.connect(_on_fail)
        worker.start()
        dlg.exec()

    def _text_with_music(self) -> str:
        """Scénario + timeline musicale (si analysée) à injecter dans Claude."""
        text = self._get_text()
        from core.music_analysis import build_set_timeline
        timeline = build_set_timeline(self._music_tracks, mode=getattr(self, "_music_mode", "clip"))
        return (timeline + "\n\n" + text) if timeline else text

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
            "layout_content":    self._layout_view.toPlainText() if hasattr(self, "_layout_view") else "",
            "music_tracks":      self._music_tracks,
            "music_mode":        self._music_mode,
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

    # ── Sauvegarde / ouverture physique du scénario (dossier « Scénario ») ──────

    def _on_save_scenario_file(self):
        from PyQt6.QtWidgets import QFileDialog, QMessageBox
        import core.scenario as scenario_api
        import os
        text  = self._get_text()
        title = self._title_edit.text().strip()
        if not text and not title:
            QMessageBox.information(self, "Sauvegarder", "Le scénario est vide.")
            return
        # Boîte de dialogue Windows : choisir où enregistrer (défaut = dossier
        # Scénario, nom de fichier = nom du projet).
        from core import context as _ctx
        suggested = scenario_api._safe_name(_ctx.get_project_name() or title or "Scénario") + ".json"
        start = os.path.join(scenario_api.saves_dir(), suggested)
        path, _ = QFileDialog.getSaveFileName(
            self, translate("Sauvegarder le scénario"), start,
            "Scénario PANDORA (*.json)")
        if not path:
            return
        if not path.lower().endswith(".json"):
            path += ".json"
        dur_defined = self._dur_defined_check.isChecked()
        dur_secs    = (self._dur_min.value() * 60 + self._dur_sec.value()) if dur_defined else 0
        data = dict(self._current or {})
        data.update({
            "title":             title or os.path.splitext(os.path.basename(path))[0],
            "raw_content":       text,
            "formatted_content": text,
            "layout_content":    self._layout_view.toPlainText() if hasattr(self, "_layout_view") else "",
            "duration_secs":     dur_secs,
            "duration_defined":  dur_defined,
            "film_style":        self._film_style_combo.currentData() or "",
        })
        try:
            scenario_api.export_scenario_to(path, data)
            self._ai_progress_lbl.setText("Scénario sauvegardé ✓")
        except Exception as e:
            QMessageBox.critical(self, "Erreur", f"Échec de la sauvegarde : {e}")

    def _on_open_scenario_file(self):
        from PyQt6.QtWidgets import QFileDialog, QMessageBox
        import core.scenario as scenario_api
        path, _ = QFileDialog.getOpenFileName(
            self, translate("Ouvrir un scénario"), scenario_api.saves_dir(),
            "Scénario PANDORA (*.json)")
        if not path:
            return
        data = scenario_api.import_scenario_from(path)
        if not data:
            QMessageBox.warning(self, "Ouvrir", "Fichier introuvable ou illisible.")
            return
        self._open_scenario(data)
        self._ai_progress_lbl.setText("Scénario ouvert ✓")

    # ── Références visuelles ─────────────────────────────────────────────────

    def _refresh_refs_display(self):
        while self._refs_hbox.count():
            item = self._refs_hbox.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        # Bouton « + » TOUJOURS un carré 60×60 à gauche (raccord avec Live ;
        # plus de long rectangle pleine largeur quand la zone est vide).
        btn_add = QPushButton("+")
        btn_add.setFixedSize(60, 60)
        btn_add.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_add.setToolTip("Ajouter des images de référence\nClaude les analysera pour enrichir les descriptions.")
        btn_add.setStyleSheet(f"""
            QPushButton{{
                background:transparent;color:{CP['text_dim']};
                border:1px dashed {CP['border_bright']};border-radius:8px;
                font-size:24px;font-weight:300;padding:0;
            }}
            QPushButton:hover{{color:{CP['accent']};border-color:{CP['accent']};
                background:rgba(78,205,196,0.08);}}
            QPushButton:pressed{{background:rgba(78,205,196,0.16);}}
        """)
        btn_add.clicked.connect(self._on_add_refs)
        self._refs_hbox.addWidget(btn_add)
        for path in self._ref_images:
            self._refs_hbox.addWidget(self._make_ref_thumbnail(path))
        self._refs_hbox.addStretch()

    def _make_ref_thumbnail(self, path: str) -> QWidget:
        container = QWidget()
        container.setFixedSize(68, 60)
        lbl = QLabel(container)
        lbl.setGeometry(0, 0, 60, 60)
        lbl.setStyleSheet("border-radius:6px;")
        pix = QPixmap(path)
        if not pix.isNull():
            pix = pix.scaled(60, 60, Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                             Qt.TransformationMode.SmoothTransformation)
            lbl.setPixmap(pix)
        btn_rm = QPushButton("✕", container)
        btn_rm.setGeometry(50, 0, 16, 16)
        btn_rm.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_rm.setStyleSheet(
            f"QPushButton{{background:{CP['bg3']};color:{CP['text_primary']};"
            f"border:1px solid {CP['border_bright']};border-radius:3px;"
            f"font-size:9px;font-weight:700;padding:0;}}"
            f"QPushButton:hover{{background:{CP['red']};color:#fff;border-color:{CP['red']};}}"
        )
        btn_rm.clicked.connect(lambda checked=False, p=path: self._remove_ref(p))
        return container

    def _remove_ref(self, path: str):
        if path in self._ref_images:
            self._ref_images.remove(path)
            self._refresh_refs_display()

    def _on_add_refs(self):
        # Porte unique : bibliothèque globale (avec « Parcourir le disque… » intégré)
        from ui.dialog_image_library import ImageLibraryDialog
        paths = ImageLibraryDialog.pick(self)
        for p in paths:
            if p not in self._ref_images:
                self._ref_images.append(p)
        if paths:
            self._refresh_refs_display()
            self._ai_progress_lbl.setText(
                f"{len(self._ref_images)} image(s) ajoutée(s) — clique « Analyser » pour enrichir le prompt."
            )

    def _on_analyze_refs(self):
        if not self._ref_images:
            self._ai_progress_lbl.setText("Ajoute d'abord des images dans la section Références visuelles.")
            return
        from api.screenplay import AnalyzeReferencesWorker
        scenario_text = self._get_text() if self._current else ""
        self._worker = AnalyzeReferencesWorker(
            ref_paths=self._ref_images,
            scenario_text=scenario_text,
        )
        self._worker.failed.connect(self._on_refs_failed)
        self._set_ai_busy(True)
        self._ai_progress_lbl.setText("Analyse des images en cours…")
        # Le worker démarre à l'intérieur de _open_refs_window, après connexion des signaux
        self._open_refs_window(worker=self._worker)

    def _on_refs_failed(self, msg: str):
        self._set_ai_busy(False)
        self._ai_progress_lbl.setText(f"Erreur : {msg}")

    def _set_ai_busy(self, busy: bool):
        for btn in (
            self._btn_format, self._btn_arrange, self._btn_coecriture,
            self._btn_plan_coedit, self._btn_storyboard,
            self._btn_gen_characters, self._btn_gen_decors,
            self._btn_gen_accessories, self._btn_gen_hmc, self._btn_gen_vehicles,
            self._btn_generate_all, self._btn_analyze_refs,
        ):
            btn.setEnabled(not busy)
        self._ai_progress_bar.setVisible(busy)

    def _on_format(self):
        text = self._get_text()
        if not text:
            self._ai_progress_lbl.setText("Écris d'abord un texte à mettre en page.")
            return
        from api.screenplay import FormatPandoraWorker
        self._set_ai_busy(True)
        self._ai_progress_lbl.setText("Mise en page PANDORA en cours via Claude…")
        self._btn_reopen_window.setVisible(False)
        self._btn_undo_action.setVisible(False)
        self._result_area.clear()
        self._result_area.setVisible(False)
        self._worker = FormatPandoraWorker(text)
        self._worker.failed.connect(self._on_ai_fail)
        self._open_format_window(worker=self._worker)

    def _on_coecriture(self):
        """Co-écriture du SCÉNARIO — ouvre directement le studio de co-écriture."""
        text = self._get_text()
        if not text:
            self._ai_progress_lbl.setText("Écris d'abord un scénario à co-écrire.")
            return
        analysis = (getattr(self, "_last_analysis", "")
                    or ((self._current or {}).get("arrange_analysis") or "")).strip()
        self._open_arrange_session(analysis)

    def _on_plan_coedit(self):
        """Co-écriture des PLANS — réécrire/enrichir la mise en page plan par plan."""
        layout = self._layout_view.toPlainText().strip() if hasattr(self, "_layout_view") else ""
        if not layout:
            self._ai_progress_lbl.setText(
                "Génère d'abord « Mise en page PANDORA », puis co-écris les plans.")
            return
        from ui.dialog_plan_coedit import PlanCoEditDialog
        dlg = PlanCoEditDialog(self, layout, edition="cinema")
        dlg.exec()
        if dlg.was_applied():
            self._apply_layout(dlg.result_layout())
            self._ai_progress_lbl.setText("Plans co-écrits appliqués à la mise en page ✓")

    def _on_arrange(self):
        text = self._get_text()
        if not text:
            self._ai_progress_lbl.setText("Écris d'abord un texte à analyser.")
            return
        # Analyse déjà faite et SAUVEGARDÉE → on la rouvre telle quelle : aucun
        # nouvel appel API, aucun crédit consommé. « Relancer l'analyse » vit
        # dans la fenêtre pour qui veut vraiment refaire une passe.
        saved = ((self._current or {}).get("arrange_analysis") or "").strip()
        if saved:
            self._last_analysis = saved
            self._last_result_kind = "arrange"
            self._btn_reopen_window.setVisible(True)
            self._open_arrange_window(analysis=saved)
            return
        self._start_arrange_analysis()

    def _start_arrange_analysis(self):
        """Lance une NOUVELLE analyse (appel API) et ouvre la fenêtre en streaming."""
        text = self._get_text()
        if not text:
            return
        from api.screenplay import ArrangeScreenplayWorker
        from core.casting import list_characters
        from core.decors import list_decors
        self._set_ai_busy(True)
        self._ai_progress_lbl.setText(translate("Analyse en cours via Claude…"))
        self._btn_reopen_window.setVisible(False)
        self._btn_undo_action.setVisible(False)
        self._result_area.clear()
        self._result_area.setVisible(False)
        dur_secs  = (self._dur_min.value() * 60 + self._dur_sec.value()) if self._dur_defined_check.isChecked() else 0
        intensity = self._arrange_intensity_value
        try:
            project_context = {"characters": list_characters(), "decors": list_decors()}
        except Exception:
            project_context = {}
        self._worker = ArrangeScreenplayWorker(text, dur_secs, intensity, project_context,
                                               ref_analysis=self._last_ref_analysis)
        self._worker.failed.connect(self._on_ai_fail)
        self._open_arrange_window(worker=self._worker)

    def _on_modify_arrange(self):
        original    = self._get_text()
        suggestions = self._last_analysis
        if not original:
            self._ai_progress_lbl.setText("Aucun texte à modifier.")
            return
        if not suggestions:
            self._ai_progress_lbl.setText("Lance d'abord « Analyse & co-écriture ».")
            return
        from api.screenplay import ApplyArrangeWorker
        self._set_ai_busy(True)
        self._ai_progress_lbl.setText("Application des suggestions via Claude…")
        self._btn_undo_action.setVisible(False)
        intensity = self._arrange_intensity_value
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
        # Timeline musicale injectée (si un set a été analysé) → découpage calé sur
        # le BPM et les drops, comme dans PANDORA | Live.
        dlg = StoryboardGenerateDialog(self._text_with_music(), dur_secs, sc_id, parent=self)
        if dlg.exec() == StoryboardGenerateDialog.DialogCode.Accepted and dlg._shots:
            count = len(dlg._shots)
            # Mise en scène INITIALE auto (acteurs + caméra depuis l'axe du plan) —
            # l'utilisateur ajuste ensuite dans Mise en scène / Plan de feu.
            try:
                import core.staging as _stg
                _stg.ensure_seeded(sb_api.list_shots(sb_api.DEFAULT_VERSION_ID))
            except Exception:
                pass
            # Coloration AUTO des plans récurrents (baseline déterministe ; l'analyse
            # IA fine se relance depuis le bouton « Plans récurrents » du Storyboard).
            try:
                import core.recurrence as _rec
                _rec.detect_and_apply(sb_api.DEFAULT_VERSION_ID)
            except Exception:
                pass
            self._ai_progress_lbl.setText(f"{count} {translate('plans importés dans le Storyboard ✓')}")
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
        if dlg._page_key and dlg.result() == dlg.DialogCode.Accepted:
            self.navigate_requested.emit(dlg._page_key, "")

    def _on_gen_decors(self):
        text = self._get_text()
        if not text:
            self._ai_progress_lbl.setText("Écris d'abord un scénario.")
            return
        from ui.dialog_extract_generate import ExtractGenerateDialog
        dlg = ExtractGenerateDialog.for_decors(text, self)
        dlg.exec()
        if dlg._page_key and dlg.result() == dlg.DialogCode.Accepted:
            self.navigate_requested.emit(dlg._page_key, "")

    def _on_gen_accessories(self):
        text = self._get_text()
        if not text:
            self._ai_progress_lbl.setText("Écris d'abord un scénario.")
            return
        from ui.dialog_extract_generate import ExtractGenerateDialog
        dlg = ExtractGenerateDialog.for_accessories(text, self)
        dlg.exec()
        if dlg._page_key and dlg.result() == dlg.DialogCode.Accepted:
            self.navigate_requested.emit(dlg._page_key, "")  # "accessoires"

    def _on_gen_hmc(self):
        text = self._get_text()
        if not text:
            self._ai_progress_lbl.setText("Écris d'abord un scénario.")
            return
        from ui.dialog_extract_generate import ExtractGenerateDialog
        dlg = ExtractGenerateDialog.for_hmc(text, self)
        dlg.exec()
        if dlg._page_key and dlg.result() == dlg.DialogCode.Accepted:
            self.navigate_requested.emit(dlg._page_key, "")

    def _on_gen_vehicles(self):
        text = self._get_text()
        if not text:
            self._ai_progress_lbl.setText("Écris d'abord un scénario.")
            return
        from ui.dialog_extract_generate import ExtractGenerateDialog
        dlg = ExtractGenerateDialog.for_vehicles(text, self)
        dlg.exec()
        if dlg._page_key and dlg.result() == dlg.DialogCode.Accepted:
            self.navigate_requested.emit(dlg._page_key, "")

    def _on_ai_fail(self, err: str):
        self._set_ai_busy(False)
        self._ai_progress_bar.setRange(0, 0)
        self._ai_progress_lbl.setText(f"Erreur : {err[:120]}")

    def _open_result_window(self):
        if self._last_result_kind == "arrange" and self._last_analysis:
            self._open_arrange_window(analysis=self._last_analysis)
        elif self._last_result_kind == "format" and self._last_format_result:
            self._open_format_window(text=self._last_format_result)
        elif self._last_result_kind == "refs" and self._last_ref_analysis:
            self._open_refs_window(self._last_ref_analysis)

    # ── Dialog Mise en page (streaming) ──────────────────────────────────────

    def _open_format_window(self, text: str = "", worker=None):
        """Dialog de mise en page — streaming immédiat si worker fourni, statique sinon."""
        from PyQt6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QTextEdit
        streaming = worker is not None
        dlg = QDialog(self)
        dlg.setWindowTitle(translate("Mise en page PANDORA — Aperçu Claude"))
        dlg.resize(900, 680)
        dlg.setStyleSheet(
            f"QDialog{{background:{CP['bg1']};}}"
            f"QLabel{{background:transparent;color:{CP['text_primary']};}}"
        )
        lay = QVBoxLayout(dlg)
        lay.setContentsMargins(22, 20, 22, 20)
        lay.setSpacing(12)

        hdr = QHBoxLayout()
        title_lbl = QLabel(translate("◈  Mise en page PANDORA — Aperçu"))
        title_lbl.setStyleSheet(f"color:{CP['text_primary']};font-size:14px;font-weight:700;")
        status_lbl = QLabel(translate("Mise en page en cours…") if streaming else translate("Mise en page terminée"))
        status_lbl.setStyleSheet(
            f"color:{CP['accent'] if streaming else CP['text_dim']};"
            f"font-size:10px;font-family:'Consolas',monospace;"
        )
        hdr.addWidget(title_lbl)
        hdr.addStretch()
        hdr.addWidget(status_lbl)
        lay.addLayout(hdr)

        te = QTextEdit()
        te.setReadOnly(True)
        if text:
            te.setPlainText(text)
        else:
            te.setPlaceholderText(translate("Le scénario mis en page apparaît ici au fil de la génération…"))
        _f = QFont("Courier New", 11)
        _f.setStyleHint(QFont.StyleHint.TypeWriter)
        te.setFont(_f)
        te.setStyleSheet(
            f"QTextEdit{{background:{CP['bg2']};border:1px solid {CP['border']};"
            f"border-radius:8px;color:{CP['text_primary']};font-size:11px;padding:16px;}}"
        )
        lay.addWidget(te, 1)

        _ghost_ss = (
            f"QPushButton{{background:{CP['bg3']};color:{CP['text_secondary']};"
            f"border:1px solid {CP['border']};border-radius:7px;font-size:11px;font-weight:600;padding:0 20px;}}"
            f"QPushButton:hover{{background:{CP['bg4']};color:{CP['text_primary']};}}"
        )
        _cancel_ss = (
            f"QPushButton{{background:{CP['bg3']};color:{CP['red']};"
            f"border:1px solid {CP['red']};border-radius:7px;font-size:11px;font-weight:600;padding:0 20px;}}"
            f"QPushButton:hover{{background:rgba(255,79,106,0.12);}}"
        )
        _streaming_active = [streaming]

        def _stop_worker():
            if _streaming_active[0] and worker is not None:
                _streaming_active[0] = False
                worker.quit()
                abandon_thread(worker)
                self._set_ai_busy(False)
                self._ai_progress_lbl.setText("Mise en page annulée.")
                btn_close.setText(translate("Fermer"))
                btn_close.setStyleSheet(_ghost_ss)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)
        btn_close = QPushButton(translate("Annuler") if streaming else translate("Fermer"))
        btn_close.setFixedHeight(36)
        btn_close.setStyleSheet(_cancel_ss if streaming else _ghost_ss)

        def _on_close_btn():
            _stop_worker()
            dlg.accept()

        btn_close.clicked.connect(_on_close_btn)
        dlg.rejected.connect(_stop_worker)

        btn_apply = QPushButton(translate("◈  Mettre dans « Mise en page PANDORA »"))
        btn_apply.setFixedHeight(36)
        btn_apply.setEnabled(not streaming)
        btn_apply.setStyleSheet(
            f"QPushButton{{background:{CP['accent2']};color:#fff;"
            f"border:none;border-radius:7px;font-size:11px;font-weight:700;padding:0 20px;}}"
            f"QPushButton:hover{{background:#9d8fff;}}"
            f"QPushButton:pressed{{background:#6a5acd;}}"
            f"QPushButton:disabled{{background:{CP['bg3']};color:{CP['text_dim']};"
            f"border:1px solid {CP['border']};}}"
        )
        _final_text = [text]

        def _do_apply():
            result = _final_text[0].strip()
            if not result:
                return
            # La mise en page va dans son onglet dédié — le scénario reste intact.
            self._apply_layout(result)
            self._ai_progress_lbl.setText("Mise en page PANDORA générée ✓ (onglet dédié)")
            dlg.accept()

        btn_apply.clicked.connect(_do_apply)
        btn_row.addWidget(btn_close)
        btn_row.addStretch()
        btn_row.addWidget(btn_apply)
        lay.addLayout(btn_row)

        if streaming:
            def _on_chunk(chunk: str):
                cursor = te.textCursor()
                cursor.movePosition(cursor.MoveOperation.End)
                cursor.insertText(chunk)
                te.setTextCursor(cursor)

            def _on_done(result: str):
                _streaming_active[0] = False
                btn_close.setText(translate("Fermer"))
                btn_close.setStyleSheet(_ghost_ss)
                _final_text[0] = result
                self._set_ai_busy(False)
                self._last_format_result = result
                self._last_result_kind = "format"
                self._btn_reopen_window.setVisible(True)
                self._ai_progress_lbl.setText("Mise en page PANDORA terminée ✓")
                status_lbl.setText(translate("Mise en page PANDORA terminée"))
                status_lbl.setStyleSheet(
                    f"color:{CP['text_dim']};font-size:10px;font-family:'Consolas',monospace;"
                )
                btn_apply.setEnabled(True)

            def _on_failed(msg: str):
                _streaming_active[0] = False
                btn_close.setText(translate("Fermer"))
                btn_close.setStyleSheet(_ghost_ss)
                self._set_ai_busy(False)
                self._ai_progress_lbl.setText(f"Erreur : {msg[:120]}")
                status_lbl.setText("Erreur")
                status_lbl.setStyleSheet(
                    f"color:{CP['red']};font-size:10px;font-family:'Consolas',monospace;"
                )
                te.setPlainText(f"Erreur lors de la mise en page :\n{msg}")

            worker.chunk.connect(_on_chunk)
            worker.finished.connect(_on_done)
            worker.failed.connect(_on_failed)
            worker.start()

        dlg.exec()

    # ── Dialog Arrangement (streaming + appliquer direct) ─────────────────────

    def _open_arrange_window(self, analysis: str = "", worker=None):
        """Dialog d'arrangement — streaming si worker fourni, statique (rouvrir) sinon.

        Quand l'analyse est complète, deux boutons :
          - « Session de co-écriture » → ArrangeSessionDialog
          - « Appliquer les suggestions » → ApplyArrangeWorker en streaming dans le même dialog
        """
        from PyQt6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QTextEdit
        streaming = worker is not None
        dlg = QDialog(self)
        dlg.setWindowTitle(translate("Arrangement — Analyse Claude"))
        dlg.resize(900, 700)
        dlg.setStyleSheet(
            f"QDialog{{background:{CP['bg1']};}}"
            f"QLabel{{background:transparent;color:{CP['text_primary']};}}"
        )
        lay = QVBoxLayout(dlg)
        lay.setContentsMargins(22, 20, 22, 20)
        lay.setSpacing(12)

        hdr = QHBoxLayout()
        title_lbl = QLabel(translate("◈  Arrangement — Analyse"))
        title_lbl.setStyleSheet(f"color:{CP['text_primary']};font-size:14px;font-weight:700;")
        status_lbl = QLabel(translate("Analyse en cours…") if streaming else translate("Analyse terminée"))
        status_lbl.setStyleSheet(
            f"color:{CP['accent'] if streaming else CP['text_dim']};"
            f"font-size:10px;font-family:'Consolas',monospace;"
        )
        hdr.addWidget(title_lbl)
        hdr.addStretch()
        hdr.addWidget(status_lbl)
        lay.addLayout(hdr)

        te = QTextEdit()
        te.setReadOnly(True)
        if analysis:
            te.setPlainText(analysis)
        else:
            te.setPlaceholderText(translate("L'analyse apparaît ici au fil de la génération…"))
        te.setStyleSheet(
            f"QTextEdit{{background:{CP['bg2']};border:1px solid {CP['border']};"
            f"border-radius:8px;color:{CP['text_primary']};font-size:11px;padding:14px;}}"
        )
        lay.addWidget(te, 1)

        # ── Boutons ──────────────────────────────────────────────────────────
        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)

        _ghost_ss = (
            f"QPushButton{{background:{CP['bg3']};color:{CP['text_secondary']};"
            f"border:1px solid {CP['border']};border-radius:7px;font-size:11px;font-weight:600;padding:0 20px;}}"
            f"QPushButton:hover{{background:{CP['bg4']};color:{CP['text_primary']};}}"
        )
        _cancel_ss = (
            f"QPushButton{{background:{CP['bg3']};color:{CP['red']};"
            f"border:1px solid {CP['red']};border-radius:7px;font-size:11px;font-weight:600;padding:0 20px;}}"
            f"QPushButton:hover{{background:rgba(255,79,106,0.12);}}"
        )
        _streaming_active = [streaming]
        _apply_worker = [None]      # worker de phase 2 (ApplyArrangeWorker)

        def _stop_worker():
            if _streaming_active[0]:
                _streaming_active[0] = False
                if worker is not None:
                    worker.quit()
                    abandon_thread(worker)
                if _apply_worker[0] is not None:
                    _apply_worker[0].quit()
                    abandon_thread(_apply_worker[0])
                    _apply_worker[0] = None
                self._set_ai_busy(False)
                self._ai_progress_lbl.setText("Arrangement annulé.")
                btn_close.setText(translate("Fermer"))
                btn_close.setStyleSheet(_ghost_ss)

        btn_close = QPushButton(translate("Annuler") if streaming else translate("Fermer"))
        btn_close.setFixedHeight(36)
        btn_close.setStyleSheet(_cancel_ss if streaming else _ghost_ss)

        def _on_close_btn():
            _stop_worker()
            dlg.accept()

        btn_close.clicked.connect(_on_close_btn)
        dlg.rejected.connect(_stop_worker)

        btn_session = QPushButton(translate("☁  Session de co-écriture"))
        btn_session.setFixedHeight(36)
        btn_session.setEnabled(not streaming)
        btn_session.setToolTip("Dialogue interactif avec Claude pour affiner l'arrangement.")
        btn_session.setStyleSheet(
            f"QPushButton{{background:{CP['bg3']};color:{CP['accent']};"
            f"border:1px solid {CP['accent_dim']};border-radius:7px;font-size:11px;font-weight:600;padding:0 20px;}}"
            f"QPushButton:hover{{background:rgba(78,205,196,0.10);color:{CP['accent']};}}"
            f"QPushButton:disabled{{background:{CP['bg2']};color:{CP['text_dim']};"
            f"border:1px solid {CP['border']};}}"
        )

        btn_direct = QPushButton(translate("✓  Appliquer les suggestions"))
        btn_direct.setFixedHeight(36)
        btn_direct.setEnabled(not streaming)
        btn_direct.setToolTip(translate(
            "Claude réécrit le scénario en appliquant directement les suggestions.\n"
            "Le résultat apparaît ici pour prévisualisation avant d'être appliqué."
        ))
        btn_direct.setStyleSheet(
            f"QPushButton{{background:{CP['accent2']};color:#fff;"
            f"border:none;border-radius:7px;font-size:11px;font-weight:700;padding:0 20px;}}"
            f"QPushButton:hover{{background:#9d8fff;}}"
            f"QPushButton:pressed{{background:#6a5acd;}}"
            f"QPushButton:disabled{{background:{CP['bg3']};color:{CP['text_dim']};"
            f"border:1px solid {CP['border']};}}"
        )

        btn_update = QPushButton("↩  Mettre à jour le scénario")
        btn_update.setFixedHeight(36)
        btn_update.setEnabled(False)
        btn_update.setVisible(False)
        btn_update.setStyleSheet(
            f"QPushButton{{background:{CP['accent2']};color:#fff;"
            f"border:none;border-radius:7px;font-size:11px;font-weight:700;padding:0 20px;}}"
            f"QPushButton:hover{{background:#9d8fff;}}"
            f"QPushButton:disabled{{background:{CP['bg3']};color:{CP['text_dim']};"
            f"border:1px solid {CP['border']};}}"
        )

        # ↻ Relancer : refaire une VRAIE analyse (appel API) — visible seulement
        # quand on a rouvert une analyse sauvegardée (pas pendant un streaming).
        btn_relaunch = QPushButton(translate("↻  Relancer l'analyse"))
        btn_relaunch.setFixedHeight(36)
        btn_relaunch.setVisible(not streaming)
        btn_relaunch.setToolTip(translate(
            "Refait une analyse complète (consomme des crédits API)."))
        btn_relaunch.setStyleSheet(_ghost_ss)

        def _do_relaunch():
            dlg.accept()
            self._start_arrange_analysis()

        btn_relaunch.clicked.connect(_do_relaunch)

        btn_row.addWidget(btn_close)
        btn_row.addWidget(btn_relaunch)
        btn_row.addStretch()
        btn_row.addWidget(btn_session)
        btn_row.addWidget(btn_direct)
        btn_row.addWidget(btn_update)
        lay.addLayout(btn_row)

        _final_analysis = [analysis]
        _rewritten      = [""]

        # ── Phase 2 : Appliquer les suggestions ──────────────────────────────
        def _do_apply_direct():
            from api.screenplay import ApplyArrangeWorker
            analysis_txt = _final_analysis[0]
            original     = self._get_text()
            if not analysis_txt or not original:
                return
            intensity = self._arrange_intensity_value
            w = ApplyArrangeWorker(original, analysis_txt, intensity)
            _apply_worker[0] = w
            _streaming_active[0] = True
            btn_close.setText("Annuler")
            btn_close.setStyleSheet(_cancel_ss)

            title_lbl.setText("✦  Application des suggestions")
            status_lbl.setText("Réécriture en cours…")
            status_lbl.setStyleSheet(
                f"color:{CP['accent']};font-size:10px;font-family:'Consolas',monospace;"
            )
            te.clear()
            te.setPlaceholderText(translate("Le scénario réécrit apparaît ici…"))
            _f = QFont("Courier New", 11)
            _f.setStyleHint(QFont.StyleHint.TypeWriter)
            te.setFont(_f)
            btn_direct.setEnabled(False)
            btn_direct.setVisible(False)
            btn_session.setEnabled(False)
            btn_session.setVisible(False)
            self._set_ai_busy(True)

            def _on_apply_chunk(chunk: str):
                if not _streaming_active[0]:
                    return
                cursor = te.textCursor()
                cursor.movePosition(cursor.MoveOperation.End)
                cursor.insertText(chunk)
                te.setTextCursor(cursor)
                _rewritten[0] += chunk

            def _on_apply_done(result: str):
                if not _streaming_active[0]:
                    return
                _streaming_active[0] = False
                _apply_worker[0] = None
                btn_close.setText(translate("Fermer"))
                btn_close.setStyleSheet(_ghost_ss)
                _rewritten[0] = result
                self._set_ai_busy(False)
                status_lbl.setText("Réécriture terminée ✓")
                status_lbl.setStyleSheet(
                    f"color:{CP['green']};font-size:10px;font-family:'Consolas',monospace;"
                )
                btn_update.setEnabled(True)
                btn_update.setVisible(True)

            def _on_apply_failed(msg: str):
                from core.ai_provider import humanize_ai_error
                msg = humanize_ai_error(msg)
                _streaming_active[0] = False
                _apply_worker[0] = None
                btn_close.setText(translate("Fermer"))
                btn_close.setStyleSheet(_ghost_ss)
                self._set_ai_busy(False)
                status_lbl.setText("Erreur")
                status_lbl.setStyleSheet(
                    f"color:{CP['red']};font-size:10px;font-family:'Consolas',monospace;"
                )
                te.setPlainText(f"Erreur lors de l'application :\n{msg}")

            def _do_update():
                result = _rewritten[0].strip()
                if not result:
                    return
                self._push_undo()
                self._set_editor_text(result)
                if self._current is not None:
                    self._current["formatted_content"] = result
                self._ai_progress_lbl.setText("Scénario réécrit et appliqué ✓")
                self._btn_undo_action.setVisible(True)
                dlg.accept()

            btn_update.clicked.connect(_do_update)
            w.chunk.connect(_on_apply_chunk)
            w.finished.connect(_on_apply_done)
            w.failed.connect(_on_apply_failed)
            w.start()

        def _do_open_session():
            dlg.accept()
            self._open_arrange_session(_final_analysis[0])

        btn_session.clicked.connect(_do_open_session)
        btn_direct.clicked.connect(_do_apply_direct)

        # ── Connexions streaming (phase analyse) ──────────────────────────────
        if streaming:
            def _on_chunk(chunk: str):
                if not _streaming_active[0]:
                    return
                cursor = te.textCursor()
                cursor.movePosition(cursor.MoveOperation.End)
                cursor.insertText(chunk)
                te.setTextCursor(cursor)

            def _on_done(result: str):
                _streaming_active[0] = False
                btn_close.setText(translate("Fermer"))
                btn_close.setStyleSheet(_ghost_ss)
                _final_analysis[0] = result
                self._set_ai_busy(False)
                self._last_analysis = result
                self._last_result_kind = "arrange"
                # Analyse PERSISTÉE avec le scénario : re-cliquer sur le bouton
                # la rouvrira sans nouvel appel API (crédits préservés).
                if self._current is not None:
                    self._current["arrange_analysis"] = result
                    self._save(silent=True)
                btn_relaunch.setVisible(True)
                self._btn_reopen_window.setVisible(True)
                text = self._editor_text.toPlainText()
                mins, secs = self._estimate_duration(text)
                if mins or secs:
                    est = f"~{mins}m{secs:02d}" if mins else f"~{secs}s"
                    self._ai_progress_lbl.setText(f"Analyse terminée ✓  ·  Durée estimée : {est}")
                else:
                    self._ai_progress_lbl.setText("Analyse terminée ✓")
                status_lbl.setText("Analyse terminée")
                status_lbl.setStyleSheet(
                    f"color:{CP['text_dim']};font-size:10px;font-family:'Consolas',monospace;"
                )
                btn_session.setEnabled(True)
                btn_direct.setEnabled(True)

            def _on_failed(msg: str):
                from core.ai_provider import humanize_ai_error
                msg = humanize_ai_error(msg)
                _streaming_active[0] = False
                btn_close.setText(translate("Fermer"))
                btn_close.setStyleSheet(_ghost_ss)
                self._set_ai_busy(False)
                self._ai_progress_lbl.setText(f"Erreur : {msg[:120]}")
                status_lbl.setText("Erreur")
                status_lbl.setStyleSheet(
                    f"color:{CP['red']};font-size:10px;font-family:'Consolas',monospace;"
                )
                te.setPlainText(f"Erreur lors de l'analyse :\n{msg}")

            worker.chunk.connect(_on_chunk)
            worker.finished.connect(_on_done)
            worker.failed.connect(_on_failed)
            worker.start()

        dlg.exec()

    def _open_arrange_session(self, analysis_text: str):
        """Ouvre le studio de co-écriture interactif Claude × Réalisateur."""
        from ui.dialog_arrange_session import ArrangeSessionDialog
        original   = self._get_text()
        intensity  = self._arrange_intensity_value
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

    def _open_refs_window(self, analysis: str = "", worker=None):
        """Fenêtre d'analyse des références visuelles.

        Modes :
          - worker fourni  → streaming en temps réel (ouverture immédiate)
          - analysis fourni → ré-ouverture avec texte complet (bouton Rouvrir)
        """
        from PyQt6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QTextEdit, QScrollArea

        streaming = worker is not None

        dlg = QDialog(self)
        dlg.setWindowTitle(translate("Références visuelles — Analyse Claude"))
        dlg.resize(860, 640)
        dlg.setStyleSheet(
            f"QDialog{{background:{CP['bg1']};}}"
            f"QLabel{{background:transparent;color:{CP['text_primary']};}}"
        )
        lay = QVBoxLayout(dlg)
        lay.setContentsMargins(22, 20, 22, 20)
        lay.setSpacing(14)

        # ── En-tête ──────────────────────────────────────────────────────────
        hdr = QHBoxLayout()
        title_lbl = QLabel(translate("◎  Analyse des références visuelles"))
        title_lbl.setStyleSheet(
            f"color:{CP['text_primary']};font-size:14px;font-weight:700;"
        )
        self._refs_status_lbl = QLabel(
            translate("Analyse en cours…") if streaming else f"{len(self._ref_images)} {translate('image(s) analysée(s)')}"
        )
        self._refs_status_lbl.setStyleSheet(
            f"color:{CP['accent'] if streaming else CP['text_dim']};"
            f"font-size:10px;font-family:'Consolas',monospace;"
        )
        hdr.addWidget(title_lbl)
        hdr.addStretch()
        hdr.addWidget(self._refs_status_lbl)
        lay.addLayout(hdr)

        # ── Thumbnails ───────────────────────────────────────────────────────
        if self._ref_images:
            thumb_scroll = QScrollArea()
            thumb_scroll.setFixedHeight(100)
            thumb_scroll.setWidgetResizable(True)
            thumb_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
            thumb_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
            thumb_scroll.setStyleSheet(
                "QScrollArea{border:none;background:transparent;}"
                f"QScrollBar:horizontal{{background:{CP['bg2']};height:9px;border-radius:4px;}}"
                f"QScrollBar::handle:horizontal{{background:{CP['border_bright']};"
                f"border-radius:4px;min-width:40px;}}"
                f"QScrollBar::handle:horizontal:hover{{background:{CP['accent']};}}"
                f"QScrollBar::add-line:horizontal,QScrollBar::sub-line:horizontal{{width:0;}}"
            )
            thumb_scroll.setFrameStyle(0)
            # Molette → défilement horizontal de la bande de miniatures
            from ui.widgets import WheelHScroller
            WheelHScroller.attach(thumb_scroll)
            thumb_ctn = QWidget()
            thumb_ctn.setStyleSheet("background:transparent;")
            thumb_hbox = QHBoxLayout(thumb_ctn)
            thumb_hbox.setContentsMargins(0, 0, 0, 0)
            thumb_hbox.setSpacing(8)
            for path in self._ref_images:
                lbl_img = QLabel()
                lbl_img.setFixedSize(80, 80)
                lbl_img.setAlignment(Qt.AlignmentFlag.AlignCenter)
                lbl_img.setStyleSheet(
                    f"background:{CP['bg2']};border:1px solid {CP['border']};border-radius:6px;"
                )
                pix = QPixmap(path)
                if not pix.isNull():
                    pix = pix.scaled(78, 78, Qt.AspectRatioMode.KeepAspectRatio,
                                     Qt.TransformationMode.SmoothTransformation)
                    lbl_img.setPixmap(pix)
                else:
                    lbl_img.setText("?")
                thumb_hbox.addWidget(lbl_img)
            thumb_hbox.addStretch()
            thumb_scroll.setWidget(thumb_ctn)
            lay.addWidget(thumb_scroll)

        # ── Texte d'analyse ──────────────────────────────────────────────────
        te = QTextEdit()
        te.setReadOnly(True)
        if analysis:
            te.setPlainText(analysis)
        else:
            te.setPlaceholderText(translate("L'analyse apparaît ici au fil de la génération…"))
        te.setStyleSheet(
            f"QTextEdit{{background:{CP['bg2']};border:1px solid {CP['border']};"
            f"border-radius:8px;color:{CP['text_primary']};font-size:11px;padding:14px;}}"
        )
        lay.addWidget(te, 1)

        # ── Boutons ──────────────────────────────────────────────────────────
        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)

        _refs_ghost_ss = (
            f"QPushButton{{background:{CP['bg3']};color:{CP['text_secondary']};"
            f"border:1px solid {CP['border']};border-radius:7px;"
            f"font-size:11px;font-weight:600;padding:0 20px;}}"
            f"QPushButton:hover{{background:{CP['bg4']};color:{CP['text_primary']};}}"
        )
        _refs_cancel_ss = (
            f"QPushButton{{background:{CP['bg3']};color:{CP['red']};"
            f"border:1px solid {CP['red']};border-radius:7px;font-size:11px;font-weight:600;padding:0 20px;}}"
            f"QPushButton:hover{{background:rgba(255,79,106,0.12);}}"
        )
        _refs_streaming_active = [streaming]

        def _stop_refs_worker():
            if _refs_streaming_active[0]:
                _refs_streaming_active[0] = False
                if worker is not None:
                    worker.quit()
                    abandon_thread(worker)
                if _enrich_worker[0] is not None:
                    _enrich_worker[0].quit()
                    abandon_thread(_enrich_worker[0])
                    _enrich_worker[0] = None
                self._set_ai_busy(False)
                self._ai_progress_lbl.setText("Analyse annulée.")
                btn_close.setText(translate("Fermer"))
                btn_close.setStyleSheet(_refs_ghost_ss)

        btn_close = QPushButton(translate("Annuler") if streaming else translate("Fermer"))
        btn_close.setFixedHeight(36)
        btn_close.setStyleSheet(_refs_cancel_ss if streaming else _refs_ghost_ss)

        def _on_close_btn():
            _stop_refs_worker()
            dlg.accept()

        btn_close.clicked.connect(_on_close_btn)
        dlg.rejected.connect(_stop_refs_worker)

        _ghost_btn_ss = (
            f"QPushButton{{background:{CP['bg3']};color:{CP['text_dim']};"
            f"border:1px solid {CP['border']};border-radius:7px;"
            f"font-size:11px;font-weight:600;padding:0 20px;}}"
            f"QPushButton:hover{{background:{CP['bg4']};color:{CP['text_primary']};}}"
            f"QPushButton:disabled{{background:{CP['bg2']};color:{CP['text_dim']};"
            f"border:1px solid {CP['border']};}}"
        )
        _accent_btn_ss = (
            f"QPushButton{{background:{CP['accent']};color:#07080f;"
            f"border:none;border-radius:7px;font-size:11px;font-weight:700;padding:0 20px;}}"
            f"QPushButton:hover{{background:#6eded6;}}"
            f"QPushButton:pressed{{background:{CP['accent_dim']};color:#fff;}}"
            f"QPushButton:disabled{{background:{CP['bg3']};color:{CP['text_dim']};"
            f"border:1px solid {CP['border']};}}"
        )

        btn_enrich = QPushButton(translate("◎  Enrichir le scénario"))
        btn_enrich.setFixedHeight(36)
        btn_enrich.setEnabled(not streaming)
        btn_enrich.setToolTip(
            "Claude croise l'analyse visuelle avec le scénario et enrichit\n"
            "les descriptions correspondantes (personnages, décors, ambiances)."
        )
        btn_enrich.setStyleSheet(_accent_btn_ss)
        # Petit signe « déjà enrichi » (retour Matthieu 2026-07-06) : si le scénario a
        # déjà été enrichi avec l'analyse courante, on le montre sur le bouton — on peut
        # toujours cliquer pour ré-enrichir. Réinitialisé à chaque nouvelle analyse.
        if getattr(self, "_ref_enriched", False) and not streaming:
            btn_enrich.setText(translate("✓  Scénario déjà enrichi"))
            btn_enrich.setToolTip(translate(
                "Déjà enrichi avec l'analyse courante — clique pour ré-enrichir."))
            btn_enrich.setStyleSheet(
                f"QPushButton{{background:{CP['bg3']};color:{CP['green']};"
                f"border:1px solid {CP['green']};border-radius:7px;font-size:11px;"
                f"font-weight:600;padding:0 20px;}}"
                f"QPushButton:hover{{background:{CP['bg4']};}}")

        btn_apply = QPushButton("✓  Appliquer au scénario")
        btn_apply.setFixedHeight(36)
        btn_apply.setEnabled(False)
        btn_apply.setVisible(False)
        btn_apply.setToolTip("Remplace le scénario actuel par la version enrichie.")
        btn_apply.setStyleSheet(_accent_btn_ss)

        _final_analysis = [analysis]   # analyse visuelle complète
        _enrich_worker  = [None]        # worker d'enrichissement en cours

        def _do_enrich():
            txt = _final_analysis[0]
            if not txt:
                return
            scenario_text = self._get_text() if self._current else ""
            if not scenario_text.strip():
                return

            from api.screenplay import EnrichScenarioWithRefsWorker
            w = EnrichScenarioWithRefsWorker(scenario_text, txt)
            _enrich_worker[0] = w
            _refs_streaming_active[0] = True
            btn_close.setText("Annuler")
            btn_close.setStyleSheet(_refs_cancel_ss)

            # ── Bascule en phase "enrichissement" ─────────────────────────────
            title_lbl.setText("✦  Enrichissement du scénario")
            self._refs_status_lbl.setText("Enrichissement en cours…")
            self._refs_status_lbl.setStyleSheet(
                f"color:{CP['accent']};font-size:10px;font-family:'Consolas',monospace;"
            )
            te.clear()
            te.setPlaceholderText(translate("Le scénario enrichi apparaît ici au fil de la génération…"))
            btn_enrich.setEnabled(False)   # grisé pendant le traitement — mais JAMAIS masqué

            _enriched = [""]

            def _on_enrich_done(res: dict):
                _refs_streaming_active[0] = False
                btn_close.setText(translate("Fermer"))
                btn_close.setStyleSheet(_refs_ghost_ss)
                # Édition CHIRURGICALE : on n'applique que les passages renvoyés
                # ({find, replace}) ; tout le reste du scénario reste MOT POUR MOT.
                from core.text_edits import apply_find_replace_edits
                edits = (res or {}).get("edits", [])
                new_text, applied, missed = apply_find_replace_edits(scenario_text, edits)
                if applied:
                    _enriched[0] = new_text
                    te.setPlainText(new_text)
                    msg = translate("{n} passage(s) enrichi(s) ✓").format(n=len(applied))
                    if missed:
                        msg += translate(" · {n} non localisé(s)").format(n=len(missed))
                    self._refs_status_lbl.setText(msg)
                    self._refs_status_lbl.setStyleSheet(
                        f"color:{CP['green']};font-size:10px;font-family:'Consolas',monospace;")
                    btn_apply.setEnabled(True)
                    btn_apply.setVisible(True)
                    btn_enrich.setEnabled(True)   # reste visible — on peut ré-enrichir
                else:
                    # Aucun passage localisé → on remet l'analyse + le bouton « Enrichir »
                    # pour réessayer (sinon le bouton disparaissait — dead-end).
                    te.setPlainText(txt)
                    self._refs_status_lbl.setText(translate("Aucun passage à enrichir localisé"))
                    self._refs_status_lbl.setStyleSheet(
                        f"color:{CP['text_dim']};font-size:10px;font-family:'Consolas',monospace;")
                    btn_enrich.setEnabled(True)
                    btn_enrich.setVisible(True)

            def _on_enrich_failed(msg: str):
                _refs_streaming_active[0] = False
                btn_close.setText(translate("Fermer"))
                btn_close.setStyleSheet(_refs_ghost_ss)
                te.setPlainText(f"Erreur lors de l'enrichissement :\n{msg}")
                self._refs_status_lbl.setText("Erreur")
                self._refs_status_lbl.setStyleSheet(
                    f"color:{CP['red']};font-size:10px;font-family:'Consolas',monospace;"
                )
                # Erreur → on remet le bouton « Enrichir » pour réessayer.
                btn_enrich.setEnabled(True)
                btn_enrich.setVisible(True)

            def _do_apply():
                result = _enriched[0].strip()
                if not result:
                    return
                self._push_undo()
                self._set_editor_text(result)
                self._ref_enriched = True    # marqueur « déjà enrichi »
                if self._current is not None:
                    self._current["formatted_content"] = result
                self._ai_progress_lbl.setText("Scénario enrichi par les références visuelles ✓")
                self._btn_undo_action.setVisible(True)
                dlg.accept()

            try:
                btn_apply.clicked.disconnect()   # évite un double « Appliquer » si on ré-enrichit
            except Exception:
                pass
            btn_apply.setVisible(False)
            btn_apply.clicked.connect(_do_apply)
            w.done.connect(_on_enrich_done)
            w.failed.connect(_on_enrich_failed)
            w.start()

        btn_enrich.clicked.connect(_do_enrich)

        btn_row.addWidget(btn_close)
        btn_row.addStretch()
        btn_row.addWidget(btn_enrich)
        btn_row.addWidget(btn_apply)
        lay.addLayout(btn_row)

        # ── Connexions streaming ──────────────────────────────────────────────
        if streaming:
            def _on_chunk(text: str):
                cursor = te.textCursor()
                cursor.movePosition(cursor.MoveOperation.End)
                cursor.insertText(text)
                te.setTextCursor(cursor)

            def _on_done(result: str):
                _refs_streaming_active[0] = False
                btn_close.setText(translate("Fermer"))
                btn_close.setStyleSheet(_refs_ghost_ss)
                _final_analysis[0] = result
                self._set_ai_busy(False)
                self._last_result_kind = "refs"
                self._last_ref_analysis = result
                self._ref_enriched = False    # nouvelle analyse → scénario pas encore enrichi avec
                n = len(self._ref_images)
                self._ai_progress_lbl.setText(f"Analyse terminée — {n} image(s).")
                self._btn_reopen_window.setVisible(True)
                self._refs_status_lbl.setText(f"{n} image(s) analysée(s)")
                self._refs_status_lbl.setStyleSheet(
                    f"color:{CP['text_dim']};font-size:10px;font-family:'Consolas',monospace;"
                )
                btn_enrich.setEnabled(True)

            def _on_failed(msg: str):
                _refs_streaming_active[0] = False
                btn_close.setText(translate("Fermer"))
                btn_close.setStyleSheet(_refs_ghost_ss)
                self._set_ai_busy(False)
                self._ai_progress_lbl.setText(f"Erreur : {msg}")
                self._refs_status_lbl.setText("Erreur")
                self._refs_status_lbl.setStyleSheet(
                    f"color:{CP['red']};font-size:10px;font-family:'Consolas',monospace;"
                )
                te.setPlainText(f"Erreur lors de l'analyse :\n{msg}")

            worker.chunk.connect(_on_chunk)
            worker.done.connect(_on_done)
            worker.failed.connect(_on_failed)
            worker.start()  # démarre après connexion des signaux — aucun chunk ne peut être perdu

        dlg.exec()

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

        btn_apply = QPushButton(translate("↩  Remplacer le texte"))
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

    def _on_undo(self):
        if not self._undo_stack:
            return
        self._redo_stack.append(self._editor_text.toPlainText())
        self._set_editor_text(self._undo_stack.pop())

    def _on_redo(self):
        if not self._redo_stack:
            return
        self._undo_stack.append(self._editor_text.toPlainText())
        self._set_editor_text(self._redo_stack.pop())

    # ── Versions ──────────────────────────────────────────────────────────────

    def _refresh_version_combo(self):
        # Contrôles « Versions » remplacés par Sauvegarder/Ouvrir — no-op si absents.
        if not hasattr(self, "_version_combo"):
            return
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
        t = _QL(translate("⚡  Génération complète du projet"))
        t.setStyleSheet(
            f"color:{_red};font-size:16px;font-weight:800;background:transparent;"
        )
        lay.addWidget(t)

        body = _QL(translate(
            "Vous êtes sur le point de lancer la génération complète :\n\n"
            "  ☁  Extraction depuis le scénario (Claude IA)\n"
            "       personnages · décors · accessoires · HMC · véhicules · storyboard\n\n"
            "  ◉  Génération d'images (Nano Banana)\n"
            "       1 image par personnage · 1 image par décor · 1 image par accessoire\n"
            "       1 image par élément HMC · 1 image par véhicule\n\n"
            "  ◈  Génération des Moods storyboard (Flux IA)\n"
            "       1 aperçu par plan storyboard"
        ))
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
            _lbl_cur   = translate('Éléments actuels :')
            _lbl_pers  = translate('personnages')
            _lbl_dec   = translate('décors')
            _lbl_acc   = translate('accessoires')
            _lbl_veh   = translate('véhicules')
            _lbl_plans = translate('Plans storyboard :')
            _lbl_est   = translate('Estimation (éléments actuels) :')
            _lbl_more  = translate("L'extraction peut créer plus d'éléments — le coût final sera plus élevé.")
            cost_txt = (
                f"{_lbl_cur} {n_chars} {_lbl_pers} · {n_decors} {_lbl_dec} · "
                f"{n_acc} {_lbl_acc} · {n_hmc} HMC · {n_veh} {_lbl_veh}\n"
                f"{_lbl_plans} {n_shots}\n"
                f"{_lbl_est} ~${min_c:.2f} — ~${max_c:.2f}\n"
                f"{_lbl_more}"
            )
        else:
            cost_txt = translate(
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

        warn = _QL(translate(
            "⚠  Les tarifs sont indicatifs et peuvent varier.\n"
            "Consultez fal.ai pour vérifier les prix actuels avant de lancer."
        ))
        warn.setWordWrap(True)
        warn.setStyleSheet(
            f"color:{CP['text_dim']};font-size:10px;font-style:italic;background:transparent;"
        )
        lay.addWidget(warn)

        advice = _QL(translate(
            "💡  La méthode la moins coûteuse\n\n"
            "Identifiez vos éléments manuellement et créez-les un à un dans les onglets "
            "dédiés : Castings pour les personnages, Décors, Accessoires, HMC, Véhicules. "
            "Vous gardez ainsi la main sur chaque génération d'image et ne payez que "
            "ce que vous validez.\n\n"
            "« Tout générer » est pratique pour un premier jet rapide, mais chaque image "
            "générée automatiquement est facturée — le coût peut rapidement devenir élevé "
            "si le scénario contient de nombreux éléments."
        ))
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

        warn_delete = _QL(translate(
            "⚠  ATTENTION — SUPPRESSION PRÉALABLE\n\n"
            "Avant de régénérer, cette opération va d'abord supprimer\n"
            "TOUS les personnages, décors, accessoires, HMC, véhicules\n"
            "et plans storyboard existants.\n\n"
            "Cette action est irréversible. Partez d'un scénario finalisé."
        ))
        warn_delete.setWordWrap(True)
        warn_delete.setStyleSheet(
            f"color:{CP.get('red','#ff4f6a')};font-size:10px;font-weight:700;"
            f"background:rgba(255,79,106,0.08);border:1px solid rgba(255,79,106,0.35);"
            f"border-radius:6px;padding:10px;"
        )
        lay.addWidget(warn_delete)

        btn_row = _QHB()
        btn_cancel = _QPB(translate("Annuler"))
        btn_cancel.setFixedHeight(38)
        btn_cancel.setStyleSheet(
            f"QPushButton{{background:{CP['bg3']};color:{CP['text_secondary']};"
            f"border:1px solid {CP['border']};border-radius:7px;"
            f"font-size:11px;font-weight:600;padding:0 20px;}}"
            f"QPushButton:hover{{background:{CP['bg4']};color:{CP['text_primary']};}}"
        )
        btn_cancel.clicked.connect(dlg.reject)
        btn_launch = _QPB(translate("⚡  Lancer la génération complète"))
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
        _el: dict = {}
        try:
            import core.casting as _ca_sb, core.decors as _dc_sb
            import core.accessories as _ac_sb, core.vehicles as _ve_sb
            chars = [c["name"] for c in _ca_sb.list_characters() if c.get("name")]
            decs  = [d["name"] for d in _dc_sb.list_decors()     if d.get("name")]
            accs  = [a["name"] for a in _ac_sb.list_accessories() if a.get("name")]
            vehs  = [v["name"] for v in _ve_sb.list_vehicles()    if v.get("name")]
            if chars: _el["characters"]  = chars
            if decs:  _el["decors"]      = decs
            _el["accessories"] = accs   # toujours transmis (liste vide = contrainte explicite)
            if vehs:  _el["vehicles"]    = vehs
        except Exception:
            pass
        w = GenerateStoryboardWorker(self._text_with_music(), dur, _el or None)
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
                    shot.pop("merged", None)       # champs de travail P2 (non persistés)
                    shot.pop("merged_note", None)
                    saved = sb_api.save_shot(shot)
                    self._gen_all_shots.append(saved)
                except Exception:
                    self._gen_all_error_count += 1
        except Exception as e:
            self._gen_all_error_count += 1
            self._ai_progress_lbl.setText(f"Erreur storyboard : {str(e)[:80]}")
        # Mise en scène INITIALE auto (acteurs + caméra) pour les plans générés.
        try:
            import core.staging as _stg
            _stg.ensure_seeded(self._gen_all_shots)
        except Exception:
            pass
        # Coloration AUTO des plans récurrents (baseline déterministe).
        try:
            import core.recurrence as _rec
            _rec.detect_and_apply(sb_api.DEFAULT_VERSION_ID)
        except Exception:
            pass
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
        self._ai_progress_lbl.setText(translate(msg))
        if hasattr(self, "_gen_all_progress_bar"):
            self._gen_all_progress_bar.setVisible(False)
            self._gen_all_status_lbl.setText(translate(msg))
        self._btn_goto_storyboard.setVisible(True)
        self._gen_all_workers.clear()

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    def showEvent(self, e):
        super().showEvent(e)
        if self._stack.currentIndex() == 0:
            self._refresh_recent()
        else:
            self._reload_if_empty_editor()

    def _reload_if_empty_editor(self):
        """Éditeur ouvert mais sans CONTENU → afficher un scénario qui a du contenu sur
        disque (ex. scénario reconstruit par la synchro Storyboard, ou rempli pendant
        que l'éditeur vide était affiché). On teste UNIQUEMENT le contenu, PAS le titre :
        un éditeur intitulé « Scénario » mais vide doit quand même se recharger (c'était
        le bug « rien dans Scénario après réécriture »). On ne recharge jamais si du
        TEXTE est déjà saisi → aucune perte de saisie en cours."""
        if self._editor_text.toPlainText().strip():
            return
        import core.scenario as scenario_api

        def _has(sc):
            return bool((sc.get("formatted_content") or sc.get("raw_content") or "").strip())

        cur_id = (self._current or {}).get("id")
        fresh = scenario_api.get_scenario(cur_id) if cur_id else None
        if fresh and _has(fresh):
            self._open_scenario(fresh)
            return
        scs = [s for s in scenario_api.list_scenarios() if _has(s)]
        if scs:
            self._open_scenario(scs[0])
