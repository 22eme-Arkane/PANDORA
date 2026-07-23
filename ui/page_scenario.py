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
from ui.styles import CP, COMBO_ARROW_URL as _ARROW_URL
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


class _PanelToggle(QWidget):
    """Poignée latérale repliable du panneau droit — même principe visuel que la
    poignée GUIDE et que « RÉGLAGES » du Plan de feu (demande Matthieu 2026-07-22)."""

    toggled = pyqtSignal(bool)

    def __init__(self, label: str = "ASSISTANT", *, opened=True, parent=None):
        super().__init__(parent)
        self._open = bool(opened)
        self.setFixedWidth(42)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setToolTip(translate("Ouvrir ou fermer le panneau"))
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        # Mêmes couleurs que la poignée GUIDE (cohérence 2026-07-22).
        self.setStyleSheet(f"background:{CP['bg1']};")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)
        lay.addStretch()
        text = QLabel(translate(label))
        text.setAlignment(Qt.AlignmentFlag.AlignCenter)
        # letter-spacing 0 : « ASSISTANT » (9 caractères) doit tenir dans 42 px.
        text.setStyleSheet(
            f"color:{CP['accent']};font-size:7px;font-weight:900;"
            "background:transparent;border:none;"
        )
        lay.addWidget(text)
        lay.addSpacing(6)
        self._arrow = QLabel()
        self._arrow.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._arrow.setStyleSheet(
            f"color:{CP['accent']};font-size:18px;font-weight:700;"
            "background:transparent;border:none;"
        )
        lay.addWidget(self._arrow)
        lay.addStretch()
        self._update_arrow()

    def _update_arrow(self):
        # Fermée → flèche vers l'EXTÉRIEUR (❯, panneau au bord droit) ;
        # ouverte → vers l'INTÉRIEUR (❮) — même logique que RÉGLAGES et les
        # chats. (Brièvement inversée le 2026-07-23, puis RESTAURÉE le même
        # jour à la demande de Matthieu : c'était le bon sens.)
        self._arrow.setText("❮" if self._open else "❯")

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._open = not self._open
            self._update_arrow()
            self.toggled.emit(self._open)
            event.accept()
            return
        super().mousePressEvent(event)


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
            "▸ Rédigez le scénario, consignez les intentions dans la Note de réalisation, puis créez le Découpage PANDORA.",
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

        # Champ titre RETIRÉ de l'affichage (demande Matthieu 2026-07-22) mais le
        # widget reste vivant : il porte le titre du scénario pour l'autosave, les
        # analyses et le harnais. Parenté à la topbar pour éviter toute fenêtre
        # fantôme, jamais ajouté au layout.
        self._title_edit = QLineEdit(topbar)
        self._title_edit.setPlaceholderText("Titre du scénario…")
        self._title_edit.textChanged.connect(self._schedule_autosave)
        self._title_edit.hide()

        # ── Sauvegarder / Ouvrir le scénario (fichiers physiques, dossier Scénario)
        # — tout à gauche de la barre, sous « Nous contacter » (2026-07-22) ──
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

        self._btn_scn_open = QPushButton("📂  Ouvrir")
        self._btn_scn_open.setFixedHeight(30)
        self._btn_scn_open.setToolTip("Ouvrir un scénario sauvegardé")
        self._btn_scn_open.setStyleSheet(
            f"QPushButton{{background:transparent;color:{_blue};"
            f"border:1px solid {_blue};border-radius:6px;font-size:10px;font-weight:700;padding:0 12px;}}"
            f"QPushButton:hover{{background:rgba(74,163,255,0.12);}}"
        )
        self._btn_scn_open.clicked.connect(self._on_open_scenario_file)

        # ── Bouton « Action » (demande Matthieu 2026-07-22) : Sauvegarder et Ouvrir
        # regroupés dans un menu déroulant, tout à gauche sous « Nous contacter ».
        # Les deux boutons d'origine restent vivants mais cachés (parenté topbar,
        # jamais de fenêtre fantôme) ; le menu se recale dessus à chaque ouverture.
        from PyQt6.QtWidgets import QMenu
        for _b in (self._btn_scn_save, self._btn_scn_open):
            _b.setParent(topbar)
            _b.hide()

        self._btn_scn_actions = QPushButton("☰  Action")
        self._btn_scn_actions.setFixedHeight(30)
        self._btn_scn_actions.setStyleSheet(
            f"QPushButton{{background:transparent;color:{CP['accent']};"
            f"border:1px solid {CP['accent']};border-radius:6px;"
            f"font-size:10px;font-weight:700;padding:0 12px;}}"
            f"QPushButton:hover{{background:rgba(78,205,196,0.12);}}"
            f"QPushButton:pressed{{background:rgba(78,205,196,0.22);}}"
            f"QPushButton::menu-indicator{{image:none;width:0;}}"
        )
        _scn_menu = QMenu(self._btn_scn_actions)
        _scn_menu.setStyleSheet(
            f"QMenu{{background:{CP['bg2']};border:1px solid {CP['border_bright']};"
            f"border-radius:8px;padding:6px;}}"
            f"QMenu::item{{color:{CP['text_primary']};padding:7px 18px;font-size:11px;}}"
            f"QMenu::item:selected{{background:{CP['accent_dim']};color:{CP['text_primary']};}}"
        )
        _scn_menu.setToolTipsVisible(True)
        self._scn_actions_pairs = [
            (_scn_menu.addAction(""), self._btn_scn_save),
            (_scn_menu.addAction(""), self._btn_scn_open),
        ]
        for _act, _src in self._scn_actions_pairs:
            _act.triggered.connect(_src.click)
        # « Tout générer » vit DANS le menu Action (demande Matthieu 2026-07-23 :
        # retiré du bas du panneau mais accessible pour qui veut encore l'utiliser).
        # Libellé fixe : le bouton source n'a pas de text() (contenu par layout).
        self._act_gen_all = _scn_menu.addAction("⚡  " + translate("Tout générer"))
        self._act_gen_all.setToolTip(
            "Personnages · Décors · Accessoires · HMC · Véhicules · Storyboard · Images · Moods")
        # .click() sur le bouton caché : respecte l'état désactivé (_set_ai_busy).
        self._act_gen_all.triggered.connect(lambda: self._btn_generate_all.click())
        def _sync_scn_actions_menu():
            for _act, _src in self._scn_actions_pairs:
                _act.setText(_src.text())
                _act.setToolTip(_src.toolTip())
                _act.setEnabled(_src.isEnabled())
            self._act_gen_all.setEnabled(
                hasattr(self, "_btn_generate_all") and self._btn_generate_all.isEnabled())
        _scn_menu.aboutToShow.connect(_sync_scn_actions_menu)
        self._btn_scn_actions.setMenu(_scn_menu)
        # Le bouton « Action » vit désormais dans la barre d'outils texte (même
        # ligne que Gras/Italique…, demande Matthieu 2026-07-22) — pas ici.

        tl.addStretch(1)

        # Le statut du flux éditorial (« Storyboard à créer »…) et l'indicateur
        # « Sauvegardé ✓ » sont RETIRÉS de la barre (demande Matthieu 2026-07-22).
        # _save_indicator reste vivant et caché : du code de sauvegarde écrit
        # dedans ; parenté à la topbar pour éviter toute fenêtre fantôme.
        self._save_indicator = QLabel("", topbar)
        self._save_indicator.hide()

        # La barre du haut n'est PLUS affichée (2026-07-22) : « Action » a rejoint
        # la barre d'outils texte et il ne restait ici que des widgets cachés.
        # On la garde vivante et invisible : elle héberge _title_edit,
        # _save_indicator et les boutons Sauvegarder/Ouvrir du menu Action.
        topbar.setParent(w)
        topbar.hide()

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
        from ui.widgets import install_reading_column, scrollbar_on_left
        install_reading_column(self._editor_text, max_width=820, center=True)
        # Scrollbar verticale au bord GAUCHE (côté GUIDE), texte toujours LTR.
        scrollbar_on_left(self._editor_text)
        self._editor_text.textChanged.connect(self._schedule_autosave)
        self._editor_text.textChanged.connect(self._update_dur_estimate)

        # ── Trois documents distincts : Scénario / Note / Découpage PANDORA ──
        # Les intentions de fabrication ne polluent plus le texte narratif.
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

        self._direction_note_edit = QTextEdit()
        self._direction_note_edit.setFont(_tw_font)
        self._direction_note_edit.setStyleSheet(
            f"QTextEdit{{background:{CP['bg0']};border:none;color:{CP['text_primary']};}}"
        )
        self._direction_note_edit.document().setDocumentMargin(48)
        self._direction_note_edit.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        install_reading_column(self._direction_note_edit, max_width=820, center=True)
        scrollbar_on_left(self._direction_note_edit)
        self._direction_note_edit.setPlaceholderText(translate(
            "Note destinée au découpage : style visuel, temporalité, rythme de montage, "
            "durée des plans, grammaire caméra, continuité, son et contraintes."
        ))
        self._direction_note_edit.textChanged.connect(self._schedule_autosave)
        self._editor_tabs.addTab(self._direction_note_edit, translate("Note de réalisation"))

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
        scrollbar_on_left(self._layout_view)
        self._layout_view.setPlaceholderText(translate(
            "Clique « Créer le découpage PANDORA » pour générer des fiches de plans : "
            "source narrative, intention, rythme, prompt visuel, continuité et propositions "
            "caméra. Ton scénario et ta note de réalisation restent intacts."
        ))
        self._layout_view.textChanged.connect(self._schedule_autosave)
        self._editor_tabs.addTab(self._layout_view, translate("Découpage"))
        self._editor_tabs.setTabEnabled(2, False)   # grisé tant qu'aucun découpage

        # Colonne éditeur : barre d'outils texte AU-DESSUS des onglets
        # Scénario / Note de réalisation / Découpage (demande Matthieu 2026-07-22).
        _editor_col_w = QWidget()
        _editor_col = QVBoxLayout(_editor_col_w)
        _editor_col.setContentsMargins(0, 0, 0, 0)
        _editor_col.setSpacing(0)
        _editor_col.addWidget(self._build_text_toolbar())
        _editor_col.addWidget(self._editor_tabs, 1)
        main.addWidget(_editor_col_w, 1)

        # Panneau droit REPLIABLE. La poignée ASSISTANT est TOUT À DROITE de la
        # fenêtre, comme GUIDE l'est à gauche (demande Matthieu 2026-07-23) : le
        # panneau se déplie à sa gauche, la poignée reste collée au bord.
        self._right_panel_w = self._build_right_panel()
        main.addWidget(self._right_panel_w)
        self._panel_toggle = _PanelToggle("ASSISTANT", opened=True)
        self._panel_toggle.toggled.connect(self._on_right_panel_toggled)
        main.addWidget(self._panel_toggle)

        outer.addLayout(main, 1)
        # La bande « Durée cible » du bas a été SUPPRIMÉE (2026-07-23) : la durée
        # vit dans le panneau droit, sous Style — la page descend jusqu'au dock.
        return w

    def _build_text_toolbar(self) -> QWidget:
        """Barre d'outils texte (demande Matthieu 2026-07-22) : police, gras /
        italique / souligné, alignement gauche / centré / droite et plein écran.
        Agit sur l'onglet actif (Scénario, Note de réalisation ou Découpage)."""
        from PyQt6.QtWidgets import QFontComboBox
        from PyQt6.QtGui import QPainter, QPixmap, QIcon

        bar = QWidget()
        bar.setFixedHeight(40)
        bar.setStyleSheet(f"background:{CP['bg1']};border-bottom:1px solid {CP['border']};")
        tl = QHBoxLayout(bar)
        tl.setContentsMargins(16, 0, 16, 0)
        tl.setSpacing(6)

        # « Action » tout à gauche, sur la MÊME ligne que les outils de mise en
        # forme (demande Matthieu 2026-07-22 — une ligne de moins). Le bouton est
        # créé dans le bloc topbar caché, juste réinséré ici.
        tl.addWidget(self._btn_scn_actions)
        tl.addStretch(1)

        self._font_combo = QFontComboBox()
        self._font_combo.setFixedHeight(26)
        self._font_combo.setFixedWidth(170)
        self._font_combo.setToolTip("Police")
        self._font_combo.setEditable(False)   # menu déroulant au CLIC sur tout le champ
        self._font_combo.setCurrentFont(QFont("Courier New"))
        self._font_combo.setStyleSheet(
            f"QFontComboBox{{background:{CP['bg2']};border:1px solid {CP['border']};"
            f"border-radius:5px;color:{CP['text_primary']};font-size:10px;padding:0 6px;}}"
            f"QFontComboBox::drop-down{{border:none;width:16px;}}"
            f'QFontComboBox::down-arrow{{image:url("{_ARROW_URL}");width:10px;height:6px;'
            f"margin-right:4px;}}"
            f"QFontComboBox QAbstractItemView{{background:{CP['bg2']};color:{CP['text_primary']};"
            f"selection-background-color:{CP.get('accent2_dim', CP['bg3'])};border:1px solid {CP['border']};}}"
        )
        self._font_combo.currentFontChanged.connect(self._on_toolbar_font)
        tl.addWidget(self._font_combo)

        _fmt_ss = (
            # padding:0 obligatoire : le style global de l'app donne un padding aux
            # QPushButton qui viderait ces boutons de 26 px (texte clippé).
            f"QPushButton{{background:transparent;color:{CP['text_secondary']};"
            f"border:1px solid {CP['border']};border-radius:5px;font-size:12px;font-weight:700;padding:0;}}"
            f"QPushButton:hover{{color:{CP['text_primary']};background:{CP['bg2']};}}"
            f"QPushButton:checked{{color:{CP['accent']};border-color:{CP['accent']};"
            f"background:rgba(78,205,196,0.10);}}"
        )

        def _fmt_btn(txt, tip):
            b = QPushButton(txt)
            b.setCheckable(True)
            b.setFixedSize(26, 26)
            b.setToolTip(tip)
            b.setStyleSheet(_fmt_ss)
            return b

        def _tb_sep():
            s = QFrame()
            s.setFixedSize(1, 20)
            s.setStyleSheet(f"background:{CP['border']};")
            return s

        tl.addWidget(_tb_sep())

        self._btn_fmt_bold = _fmt_btn("B", "Gras")
        self._btn_fmt_italic = _fmt_btn("I", "Italique")
        _fi = self._btn_fmt_italic.font(); _fi.setItalic(True)
        self._btn_fmt_italic.setFont(_fi)
        self._btn_fmt_under = _fmt_btn("U", "Souligner")
        _fu = self._btn_fmt_under.font(); _fu.setUnderline(True)
        self._btn_fmt_under.setFont(_fu)
        self._btn_fmt_bold.toggled.connect(self._on_toolbar_bold)
        self._btn_fmt_italic.toggled.connect(self._on_toolbar_italic)
        self._btn_fmt_under.toggled.connect(self._on_toolbar_underline)
        tl.addWidget(self._btn_fmt_bold)
        tl.addWidget(self._btn_fmt_italic)
        tl.addWidget(self._btn_fmt_under)

        tl.addWidget(_tb_sep())

        # Icônes d'alignement dessinées en Qt (nettes à toute résolution — même
        # principe que les glyphes filaires de la page de démarrage).
        def _align_icon(mode: str) -> QIcon:
            pm = QPixmap(18, 18)
            pm.fill(Qt.GlobalColor.transparent)
            p = QPainter(pm)
            p.setPen(QColor(CP['text_secondary']))
            widths = (14, 9, 14, 9)
            for i, _w in enumerate(widths):
                y = 3 + i * 4
                if mode == "left":
                    x = 2
                elif mode == "center":
                    x = (18 - _w) // 2
                else:
                    x = 16 - _w
                p.drawLine(x, y, x + _w, y)
            p.end()
            return QIcon(pm)

        self._btn_align_left = _fmt_btn("", "Aligner à gauche")
        self._btn_align_left.setIcon(_align_icon("left"))
        self._btn_align_center = _fmt_btn("", "Centrer")
        self._btn_align_center.setIcon(_align_icon("center"))
        self._btn_align_right = _fmt_btn("", "Aligner à droite")
        self._btn_align_right.setIcon(_align_icon("right"))
        self._btn_align_left.clicked.connect(lambda: self._on_toolbar_align("left"))
        self._btn_align_center.clicked.connect(lambda: self._on_toolbar_align("center"))
        self._btn_align_right.clicked.connect(lambda: self._on_toolbar_align("right"))
        tl.addWidget(self._btn_align_left)
        tl.addWidget(self._btn_align_center)
        tl.addWidget(self._btn_align_right)

        tl.addStretch(1)

        # La barre reflète l'état du curseur de l'onglet actif.
        for _ed in (self._editor_text, self._direction_note_edit, self._layout_view):
            _ed.cursorPositionChanged.connect(self._sync_text_toolbar)
        self._editor_tabs.currentChanged.connect(self._sync_text_toolbar)
        return bar

    # ── Barre d'outils texte : actions ────────────────────────────────────────

    def _active_text_edit(self) -> QTextEdit:
        idx = self._editor_tabs.currentIndex() if hasattr(self, "_editor_tabs") else 0
        return (self._editor_text, self._direction_note_edit, self._layout_view)[max(0, idx)]

    def _on_toolbar_font(self, font):
        from PyQt6.QtGui import QTextCharFormat
        ed = self._active_text_edit()
        fmt = QTextCharFormat()
        fmt.setFontFamilies([font.family()])
        cur = ed.textCursor()
        cur.mergeCharFormat(fmt)
        ed.mergeCurrentCharFormat(fmt)
        ed.setFocus()

    def _on_toolbar_bold(self, checked: bool):
        ed = self._active_text_edit()
        ed.setFontWeight(QFont.Weight.Bold if checked else QFont.Weight.Normal)
        ed.setFocus()

    def _on_toolbar_italic(self, checked: bool):
        ed = self._active_text_edit()
        ed.setFontItalic(checked)
        ed.setFocus()

    def _on_toolbar_underline(self, checked: bool):
        ed = self._active_text_edit()
        ed.setFontUnderline(checked)
        ed.setFocus()

    def _on_toolbar_align(self, mode: str):
        ed = self._active_text_edit()
        flags = {
            "left":   Qt.AlignmentFlag.AlignLeft,
            "center": Qt.AlignmentFlag.AlignCenter,
            "right":  Qt.AlignmentFlag.AlignRight,
        }
        ed.setAlignment(flags[mode])
        self._sync_text_toolbar()
        ed.setFocus()

    def _on_right_panel_toggled(self, opened: bool):
        """Replie/déplie le panneau droit (poignée latérale ASSISTANT)."""
        if hasattr(self, "_right_panel_w"):
            self._right_panel_w.setVisible(bool(opened))

    def _sync_text_toolbar(self):
        """Recale les boutons de la barre sur le format au curseur de l'onglet actif."""
        if not hasattr(self, "_btn_fmt_bold"):
            return
        ed = self._active_text_edit()
        for _b, _on in (
            (self._btn_fmt_bold,   ed.fontWeight() >= QFont.Weight.Bold),
            (self._btn_fmt_italic, ed.fontItalic()),
            (self._btn_fmt_under,  ed.fontUnderline()),
            (self._btn_align_left,   ed.alignment() & Qt.AlignmentFlag.AlignLeft),
            (self._btn_align_center, ed.alignment() & Qt.AlignmentFlag.AlignHCenter),
            (self._btn_align_right,  ed.alignment() & Qt.AlignmentFlag.AlignRight),
        ):
            _b.blockSignals(True)
            _b.setChecked(bool(_on))
            _b.blockSignals(False)
        self._font_combo.blockSignals(True)
        _fam = ed.currentFont().family()
        if _fam:
            self._font_combo.setCurrentFont(QFont(_fam))
        self._font_combo.blockSignals(False)

    def _build_film_strip(self) -> QWidget:
        """Rangée « Durée cible » — dans le panneau droit, entre Style et
        Ajouter des références (demande Matthieu 2026-07-23)."""
        strip = QWidget()
        # 40 px + ligne basse : le bas de la rangée Durée cible tombe sur la même
        # ligne que la barre d'outils texte de l'éditeur (alignement 2026-07-23).
        strip.setFixedHeight(40)
        strip.setStyleSheet(f"background:{CP['bg1']};border-bottom:1px solid {CP['border']};")
        sl = QHBoxLayout(strip)
        sl.setContentsMargins(10, 2, 10, 2)
        sl.setSpacing(6)

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
        def _ai_btn(icon, label, sub, callback, color=None, radius=0):
            # color → bouton MIS EN AVANT (cadre + icône + libellé colorés), façon
            # « Tout générer » mais dans une AUTRE couleur.
            # radius=0 par défaut (demande Matthieu 2026-07-22 : rectangles à bords
            # droits, seuls « Valider et envoyer au Storyboard » et « Tout générer »
            # gardent leurs arrondis).
            # Test « contenu centré » du 2026-07-23 : REFUSÉ par Matthieu après
            # essai (retour à l'alignement GAUCHE) — mais on GARDE les hauteurs
            # compactes (46/50), les marges resserrées et les libellés courts.
            btn = QPushButton()
            btn.setFixedHeight(50 if color else 46)
            _bd  = color or CP['border']
            _hov = color or CP['accent2_dim']
            btn.setStyleSheet(
                f"QPushButton{{background:{CP['bg2']};border:{'1.5px' if color else '1px'} solid {_bd};"
                f"border-radius:{radius}px;text-align:left;padding:0 10px;}}"
                f"QPushButton:hover{{border-color:{_hov};background:{CP['bg3']};}}"
                f"QPushButton:pressed{{background:{CP['bg4']};}}"
                f"QPushButton:disabled{{opacity:0.4;}}"
            )
            bl = QVBoxLayout(btn)
            bl.setContentsMargins(6, 4, 6, 4)
            bl.setSpacing(1)
            title_row = QHBoxLayout()
            title_row.setSpacing(6)
            ico_lbl = QLabel(icon)
            ico_lbl.setStyleSheet(
                f"color:{color or CP['accent2']};font-size:{'14px' if color else '13px'};"
                f"background:transparent;border:none;"
            )
            txt_lbl = QLabel(translate(label))   # translate() rebaptise aussi « Claude »
            txt_lbl.setStyleSheet(
                f"color:{color or CP['text_primary']};font-size:10px;font-weight:700;"
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
            # border-radius:0 explicite : sans lui, le style global QPushButton
            # arrondit les en-têtes de section (demande Matthieu 2026-07-22).
            f"QPushButton{{background:{CP['bg3']};color:{CP['accent']};"
            f"border:none;border-radius:0px;"
            f"border-top:1px solid {CP['border']};border-bottom:1px solid {CP['border']};"
            # Centrage testé puis refusé le 2026-07-23 → alignement GAUCHE
            # conservé ; padding compact 7 px gardé.
            f"font-size:11px;font-weight:800;text-align:left;"
            f"padding:7px 16px;letter-spacing:0.8px;}}"
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
            f"QScrollArea{{border:none;background:{CP['bg1']};}}"
            f"QScrollBar:vertical{{background:{CP['bg2']};width:4px;border-radius:2px;}}"
            f"QScrollBar::handle:vertical{{background:{CP['border_bright']};border-radius:2px;}}"
            f"QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical{{height:0;}}"
        )
        # Le fond bg1 remplit le panneau JUSQU'EN BAS même quand le contenu
        # compacté est plus court que la fenêtre (retour Matthieu 2026-07-23 :
        # « les menus sont rétrécis ») — viewport peint explicitement.
        scroll.viewport().setStyleSheet(f"background:{CP['bg1']};")

        scroll_content = QWidget()
        # WA_StyledBackground : sans lui, un QWidget ne peint PAS son fond de
        # stylesheet → le bas du panneau restait noir une fois le contenu
        # compacté (retour Matthieu 2026-07-23).
        scroll_content.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        scroll_content.setStyleSheet(f"background:{CP['bg1']};")
        sc_lay = QVBoxLayout(scroll_content)
        # Marge droite 8 px (TEST 2026-07-23) : petit espace libre entre les
        # rectangles et la barre de défilement (avant : 0, cartes collées).
        sc_lay.setContentsMargins(0, 0, 8, 0)
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
        self._refs_container_w.setStyleSheet(f"background:{CP['bg2']};border-radius:0px;")
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

        self._btn_load_analysis = _ai_btn(
            "📂", "Charger une analyse",
            "Recharge une analyse sauvegardée — réutilisable entre projets",
            self._on_load_saved_analysis,
        )
        l_refs.addWidget(self._btn_load_analysis)

        tog_refs = _make_toggle("🎨  Ajouter des références", c_refs, expanded=False)

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
        self._music_container_w.setStyleSheet(f"background:{CP['bg2']};border-radius:0px;")
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

        # 🎵 (émoji pleine largeur, comme 🎨/📖/🎯/⚡) — le glyphe étroit « ♫ »
        # décalait le libellé par rapport aux autres sections (retour 2026-07-23).
        tog_music = _make_toggle("🎵  Musique", c_music, expanded=False)

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

        # ── Section : Découpage (création + affinage plan par plan) ──────
        # Étape à ne pas sauter : préparer/optimiser les plans AVANT de générer le
        # storyboard. « Mise en page PANDORA » structure le scénario en plans ;
        # « Co-écriture des plans » les réécrit un par un (fenêtre dédiée).
        c_final, l_final = _section_container()

        self._btn_format = _ai_btn(
            "📝", "Créer le découpage PANDORA", "Transforme le scénario et la note en plans sans réécrire le récit", self._on_format,
        )
        self._btn_plan_coedit = _ai_btn(
            "✍", "Affiner le découpage", "Co-écrire chaque plan avant de l'envoyer au Storyboard", self._on_plan_coedit,
        )
        l_final.addWidget(self._btn_format)
        l_final.addWidget(self._btn_plan_coedit)
        tog_final = _make_toggle("🎯  Découpage", c_final, expanded=True)

        # ── Section 2 : Générer depuis le scénario (repliée par défaut) ───────
        c_gen, l_gen = _section_container()

        self._btn_gen_characters = _ai_btn(
            "🎭", "Générer les personnages", "Identifier les personnages depuis le scénario",
            self._on_gen_characters,
        )
        # Renommé + description raccourcie (demande Matthieu 2026-07-23) — le
        # plan vu de dessus est toujours généré, simplement plus mentionné ici.
        self._btn_gen_decors = _ai_btn(
            "🏠", "Générer les décors",
            "Identifier les décors depuis le scénario",
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
        # « Générer le storyboard » (ancien nom repris le 2026-07-23) : dans la
        # section Générer, derrière « Générer les véhicules » ; garde ses arrondis.
        # ROUGE + éclair (demande Matthieu 2026-07-23) : il reprend l'identité
        # visuelle de l'ex-« Tout générer », masqué pour le moment.
        self._btn_storyboard = _ai_btn(
            "⚡", "Générer le storyboard", "Construit le storyboard depuis le découpage — ou le scénario",
            self._on_storyboard, color=CP.get("red", "#ff4f6a"), radius=8,
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

        # ── Style pictural du film — SECTION REPLIABLE comme les autres du
        # panneau (demande Matthieu 2026-07-23), tout en haut ──
        import core.style as _sc_style_mod
        c_style, l_style = _section_container()
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
        self._film_style_combo.setStyleSheet(
            f"QComboBox{{background:{CP['bg2']};border:1px solid {CP['border']};"
            f"border-radius:0px;color:{CP['text_primary']};font-size:10px;padding:0 6px;}}"
            f"QComboBox:focus{{border-color:{CP.get('accent2_dim', CP['border_bright'])};}}"
            f"QComboBox::drop-down{{border:none;width:18px;}}"
            f"QComboBox QAbstractItemView{{background:{CP['bg2']};color:{CP['text_primary']};"
            f"selection-background-color:{CP.get('accent2_dim', CP['bg3'])};border:1px solid {CP['border']};}}"
        )
        self._film_style_combo.currentIndexChanged.connect(self._schedule_autosave)
        self._film_style_combo.currentIndexChanged.connect(self._on_scenario_style_changed)
        l_style.addWidget(self._film_style_combo)
        tog_style = _make_toggle("🎭  Style", c_style, expanded=False)

        # ── Durée cible en tête du panneau ──
        sc_lay.addWidget(self._build_film_strip())

        # ── Ordre visuel du panneau droit (haut → bas), demande Matthieu 2026-07-23
        # (2e passe) : Durée cible, Scénario, Découpage, Générer depuis le scénario,
        # Ajouter des références, Musique, et Style EN DERNIER.
        for _tog, _cont in (
            (tog_scen,  c_scen),
            (tog_final, c_final),
            (tog_gen,   c_gen),
            (tog_refs,  c_refs),
            (tog_music, c_music),
            (tog_style, c_style),
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
        # Marges resserrées (retour Matthieu 2026-07-23) : les ANNOTATIONS
        # (« Découpage PANDORA créé ✓ »…) vivent SOUS la ligne, dans l'espace
        # qu'occupait la zone « Tout générer » — le panneau y gagne en hauteur.
        b_lay.setContentsMargins(0, 0, 0, 6)
        b_lay.setSpacing(6)

        b_lay.addWidget(_sep())

        self._ai_progress_lbl = QLabel("")
        self._ai_progress_lbl.setWordWrap(True)
        self._ai_progress_lbl.setStyleSheet(
            f"color:{CP['text_dim']};font-size:10px;font-family:'Consolas',monospace;"
            f"background:transparent;"
        )
        b_lay.addWidget(self._ai_progress_lbl)

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
            f"border-radius:0px;color:{CP['text_secondary']};font-size:11px;padding:12px;}}"
        )
        b_lay.addWidget(self._result_area)

        # RETIRÉ de l'affichage (demande Matthieu 2026-07-22) : analyse et co-écriture
        # se rouvrent depuis leurs boutons dédiés — ce raccourci n'a plus de raison
        # d'être. Le widget reste vivant (nombreux appels setVisible), jamais montré.
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
            f"border:1px solid {CP['border']};border-radius:0px;font-size:10px;font-weight:700;padding:0 8px;}}"
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
        # Marges 0 (2026-07-23) : « Tout générer » étant masqué, cette zone ne
        # doit plus réserver de rectangle vide sous la ligne — l'espace revient
        # aux sections du panneau. (Les marges reviendront avec le bouton.)
        ga_lay.setContentsMargins(0, 0, 0, 0)
        ga_lay.setSpacing(0)

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
        # « Tout générer » MASQUÉ pour le moment (demande Matthieu 2026-07-23) —
        # widget vivant : _set_ai_busy et _on_generate_all restent branchés.
        self._btn_generate_all.hide()

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
        """Écrit le Découpage PANDORA dans son onglet dédié. Le Scénario et
        la Note de réalisation restent intacts."""
        if not text:
            return
        from core.decoupage_layout import canonicalize_layout
        text = canonicalize_layout(text)
        self._layout_view.setPlainText(text)
        from ui.widgets import apply_paragraph_spacing
        apply_paragraph_spacing(self._layout_view)   # centré + respiration (façon Word)
        if hasattr(self, "_editor_tabs"):
            self._editor_tabs.setTabEnabled(2, True)
            self._editor_tabs.setCurrentIndex(2)
        if self._current is not None:
            from core.editorial_pipeline import mark_decoupage_built
            self._current = mark_decoupage_built(self._current, text)
        self._refresh_pipeline_status()

    def _clear_layout(self):
        """Vide le Découpage PANDORA et désactive son onglet."""
        if hasattr(self, "_layout_view"):
            self._layout_view.clear()
        if hasattr(self, "_editor_tabs"):
            self._editor_tabs.setTabEnabled(2, False)
            self._editor_tabs.setCurrentIndex(0)
        self._refresh_pipeline_status()

    def _restore_layout(self, text: str):
        """Recharge le Découpage PANDORA (onglet activé lorsqu'il existe)."""
        if not hasattr(self, "_layout_view"):
            return
        self._layout_view.setPlainText(text or "")
        from ui.widgets import apply_paragraph_spacing
        apply_paragraph_spacing(self._layout_view)   # centré + respiration (façon Word)
        if hasattr(self, "_editor_tabs"):
            self._editor_tabs.setTabEnabled(2, bool((text or "").strip()))
            self._editor_tabs.setCurrentIndex(0)
        self._refresh_pipeline_status()

    def _refresh_pipeline_status(self):
        if not hasattr(self, "_pipeline_status_lbl"):
            return
        data = dict(self._current or {})
        if hasattr(self, "_editor_text"):
            data["formatted_content"] = self._editor_text.toPlainText()
        if hasattr(self, "_direction_note_edit"):
            data["direction_note"] = self._direction_note_edit.toPlainText()
        if hasattr(self, "_layout_view"):
            data["decoupage_content"] = self._layout_view.toPlainText()
        from core.editorial_pipeline import status
        labels = {
            "screenplay_empty":  ("Scénario à écrire", CP["text_dim"]),
            "decoupage_missing": ("Découpage à créer", CP["orange"]),
            "decoupage_stale":   ("Découpage à actualiser", CP["red"]),
            "storyboard_missing":("Storyboard à créer", CP["orange"]),
            "storyboard_stale":  ("Storyboard à actualiser", CP["red"]),
            "current":           ("Flux éditorial à jour", CP["green"]),
        }
        text, color = labels[status(data)]
        self._pipeline_status_lbl.setText(text)
        self._pipeline_status_lbl.setStyleSheet(
            f"color:{color};font-size:9px;font-family:'Consolas',monospace;"
            "background:transparent;"
        )

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
        from core.direction_note import empty_note
        self._direction_note_edit.setPlainText(empty_note())
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
        # Restaure la mise en forme visuelle si elle correspond toujours au texte
        # (sinon le texte brut prévaut : une réécriture IA invalide l'ancien HTML).
        _html = sc.get("formatted_html") or ""
        if _html:
            from PyQt6.QtGui import QTextDocument
            _tmp = QTextDocument()
            _tmp.setHtml(_html)
            if _tmp.toPlainText() == self._editor_text.toPlainText():
                self._editor_text.setHtml(_html)
                from ui.widgets import apply_paragraph_spacing
                apply_paragraph_spacing(self._editor_text)
        self._direction_note_edit.setPlainText(sc.get("direction_note", ""))
        # Découpage PANDORA — migration automatique depuis l'ancien layout_content.
        self._restore_layout(sc.get("decoupage_content") or sc.get("layout_content", ""))
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
        # Références visuelles : restaurées avec le projet (après _go_editor,
        # qui remet _last_result_kind/_btn_reopen_window à zéro) — parité Live.
        _ri = sc.get("ref_images", [])
        self._ref_images = ([p for p in _ri if isinstance(p, str) and os.path.isfile(p)]
                            if isinstance(_ri, list) else [])
        self._refresh_refs_display()
        self._last_ref_analysis = sc.get("ref_analysis", "") or ""
        self._ref_enriched = bool(sc.get("ref_enriched", False)) and bool(self._last_ref_analysis)
        if self._last_ref_analysis:
            self._last_result_kind = "refs"
            self._btn_reopen_window.setVisible(False)   # bouton retiré (2026-07-22)
            self._ai_progress_lbl.setText(translate("Analyse des références disponible ✓"))

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
        """Affiche/masque les spinboxes durée selon la case à cocher.
        L'ESTIMATION disparaît quand la durée cible est active (retour Matthieu
        2026-07-23) — la rangée garde ainsi la même largeur au lieu de pousser
        le panneau (spinboxes + estimation ne tiennent pas ensemble en 300 px)."""
        self._dur_min.setVisible(checked)
        self._dur_sec.setVisible(checked)
        if hasattr(self, "_dur_estimate_lbl"):
            self._dur_estimate_lbl.setVisible(not checked)
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
        """Source du découpage (Mise en page PANDORA sinon scénario) + timeline musicale
        (si analysée) à injecter dans Claude."""
        text = self._decoupage_base()
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
            "direction_note":    self._direction_note_edit.toPlainText() if hasattr(self, "_direction_note_edit") else "",
            "decoupage_content": self._layout_view.toPlainText() if hasattr(self, "_layout_view") else "",
            "layout_content":    self._layout_view.toPlainText() if hasattr(self, "_layout_view") else "",
            "music_tracks":      self._music_tracks,
            "music_mode":        self._music_mode,
            "ref_images":        [p for p in self._ref_images if os.path.isfile(p)],
            "ref_analysis":      self._last_ref_analysis,
            "ref_enriched":      self._ref_enriched,
            # Mise en forme visuelle (gras/italique/police/alignements) de l'onglet
            # Scénario — les traitements IA restent sur le texte brut.
            "formatted_html":    self._editor_text.toHtml(),
        })
        self._current = scenario_api.save_scenario(data)
        self._refresh_pipeline_status()
        if not silent:
            self._save_indicator.setText("Sauvegardé ✓")
            QTimer.singleShot(2000, lambda: self._save_indicator.setText(""))
        else:
            self._save_indicator.setText("✓")
            QTimer.singleShot(1500, lambda: self._save_indicator.setText(""))

    # ── Claude actions ────────────────────────────────────────────────────────

    def _get_text(self) -> str:
        return self._editor_text.toPlainText().strip()

    def _decoupage_base(self) -> str:
        """Source du découpage (règle 2026-07-09, AUTOMATIQUE — aucun choix manuel) :
        le « Découpage PANDORA » (decoupage_content) s'il existe, sinon le scénario/
        conducteur brut. Vaut pour TOUS les points de lancement (page + « Tout générer »)."""
        layout = self._layout_view.toPlainText().strip() if hasattr(self, "_layout_view") else ""
        return layout or self._get_text()

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
            "direction_note":    self._direction_note_edit.toPlainText() if hasattr(self, "_direction_note_edit") else "",
            "decoupage_content": self._layout_view.toPlainText() if hasattr(self, "_layout_view") else "",
            "layout_content":    self._layout_view.toPlainText() if hasattr(self, "_layout_view") else "",
            "duration_secs":     dur_secs,
            "duration_defined":  dur_defined,
            "film_style":        self._film_style_combo.currentData() or "",
            "formatted_html":    self._editor_text.toHtml(),
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
        # Une analyse existe déjà → on la rouvre (avec chat + bouton Relancer),
        # plutôt que de relancer une requête par image sans prévenir.
        if self._last_ref_analysis:
            self._open_refs_window(self._last_ref_analysis)
            return
        self._start_refs_analysis()

    def _start_refs_analysis(self):
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

    def _on_load_saved_analysis(self):
        """Menu des analyses sauvegardées (bibliothèque globale, entre projets)."""
        from PyQt6.QtWidgets import QMenu
        from core import ref_library
        entries = ref_library.list_analyses()
        menu = QMenu(self)
        menu.setStyleSheet(
            f"QMenu{{background:{CP['bg2']};color:{CP['text_primary']};"
            f"border:1px solid {CP['border_bright']};border-radius:6px;padding:4px;}}"
            f"QMenu::item{{padding:6px 14px;border-radius:4px;}}"
            f"QMenu::item:selected{{background:{CP['bg4']};}}"
        )
        if not entries:
            act = menu.addAction(translate("Aucune analyse sauvegardée"))
            act.setEnabled(False)
        for e in entries:
            lbl = (f"{e.get('name', '?')}  —  {e.get('mode', 'cinema')} · "
                   f"{len(e.get('images', []))} img · {e.get('date', '')}")
            act = menu.addAction(lbl)
            act.triggered.connect(lambda checked=False, ee=e: self._apply_saved_analysis(ee))
        btn = self._btn_load_analysis
        menu.exec(btn.mapToGlobal(btn.rect().bottomLeft()))

    def _apply_saved_analysis(self, e: dict):
        """Recharge une analyse : état + persistance projet + fenêtre (avec chat)."""
        txt = e.get("analysis", "")
        if not txt:
            return
        self._last_ref_analysis = txt
        self._last_result_kind = "refs"
        self._btn_reopen_window.setVisible(False)   # bouton retiré (2026-07-22)
        imgs = [p for p in e.get("images", [])
                if isinstance(p, str) and os.path.isfile(p)]
        if imgs:
            self._ref_images = imgs
            self._refresh_refs_display()
        if self._current is not None:
            self._save(silent=True)
        self._ai_progress_lbl.setText(f"{translate('Analyse chargée')} : {e.get('name', '')} ✓")
        self._open_refs_window(txt)

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
            self._ai_progress_lbl.setText("Écris d'abord un scénario à découper.")
            return
        from api.screenplay import FormatPandoraWorker
        from core.ai_provider import ai_name_for_task
        self._set_ai_busy(True)
        # 'decoupage' (et pas 'screenplay') : depuis le routage du 2026-07-23 le
        # Découpage tourne sur Opus 4.8 — le libellé doit nommer le VRAI moteur.
        self._ai_progress_lbl.setText(
            f"Découpage PANDORA en cours via {ai_name_for_task('decoupage')}…")
        self._btn_reopen_window.setVisible(False)
        self._btn_undo_action.setVisible(False)
        self._result_area.clear()
        self._result_area.setVisible(False)
        note = self._direction_note_edit.toPlainText().strip()
        self._worker = FormatPandoraWorker(text, direction_note=note)
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
        """Co-écriture des PLANS — affiner le découpage plan par plan."""
        layout = self._layout_view.toPlainText().strip() if hasattr(self, "_layout_view") else ""
        if not layout:
            self._ai_progress_lbl.setText(
                "Crée d'abord le Découpage PANDORA, puis affine les plans.")
            return
        from ui.dialog_plan_coedit import PlanCoEditDialog
        dlg = PlanCoEditDialog(self, layout, edition="cinema")
        # AUTO-SAVE : chaque modification est écrite en DIRECT dans le Découpage —
        # plus aucune perte possible, même en fermant. (Connecté AVANT exec().)
        dlg.layout_committed.connect(self._on_plan_coedit_autosave)
        dlg.exec()
        if dlg.was_applied():
            self._apply_layout(dlg.result_layout())
            self._ai_progress_lbl.setText("Découpage affiné et sauvegardé ✓")

    def _on_plan_coedit_autosave(self, layout_text: str):
        """Auto-save de la co-écriture : réécrit et persiste le Découpage PANDORA
        à CHAQUE modification du dialogue. Silencieux (pas de bascule d'onglet)."""
        if not layout_text or not hasattr(self, "_layout_view"):
            return
        self._layout_view.setPlainText(layout_text)
        try:
            from ui.widgets import apply_paragraph_spacing
            apply_paragraph_spacing(self._layout_view)
        except Exception:
            pass
        if self._current is not None:
            self._current["decoupage_content"] = layout_text
            self._current["layout_content"] = layout_text
        try:
            self._save(silent=True)
        except Exception:
            pass

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
            self._btn_reopen_window.setVisible(False)   # bouton retiré (2026-07-22)
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
        # La direction artistique (analyse des refs) nourrit l'application si présente
        self._worker = ApplyArrangeWorker(original, suggestions, intensity,
                                          refs_analysis=self._last_ref_analysis)
        self._worker.finished.connect(self._on_modify_done)
        self._worker.failed.connect(self._on_ai_fail)
        self._worker.start()

    def _on_modify_done(self, result: str):
        self._set_ai_busy(False)
        self._push_undo()
        self._set_editor_text(result)
        if self._current is not None:
            self._current["formatted_content"] = result
        note_added = self._merge_analysis_direction_note(self._last_analysis)
        self._ai_progress_lbl.setText(
            translate("Scénario modifié et intentions ajoutées à la note ✓")
            if note_added else
            translate("Scénario modifié selon les suggestions ✓")
        )
        self._btn_undo_action.setVisible(True)

    def _merge_analysis_direction_note(self, analysis: str) -> bool:
        """Range la section 6 d'une analyse dans le document Note de réalisation.

        Cette opération est déterministe et ne déclenche aucun nouvel appel IA.
        Seule la section issue de la dernière analyse est remplacée : les notes
        rédigées manuellement et les autres sections restent intactes.
        """
        from core.direction_note import append_to_note, extract_from_analysis
        from core.i18n import get_lang

        addition = extract_from_analysis(analysis)
        if not addition or not hasattr(self, "_direction_note_edit"):
            return False
        title = ("INTENTIONS FROM SCREENPLAY ANALYSIS" if get_lang() == "en"
                 else "INTENTIONS ISSUES DE L’ANALYSE DU SCÉNARIO")
        current = self._direction_note_edit.toPlainText()
        merged = append_to_note(current, title, addition, replace=True)
        if merged.strip() == current.strip():
            return False
        self._direction_note_edit.blockSignals(True)
        self._direction_note_edit.setPlainText(merged)
        self._direction_note_edit.blockSignals(False)
        if self._current is not None:
            self._current["direction_note"] = merged
            self._save(silent=True)
        return True

    def _on_storyboard(self):
        _src = self._get_text()
        _lay = self._layout_view.toPlainText().strip() if hasattr(self, "_layout_view") else ""
        if not _src and not _lay:
            self._ai_progress_lbl.setText("Écris d'abord un scénario à découper.")
            return
        # DÉBLOQUÉ (décision Matthieu 2026-07-23) : sans découpage, le storyboard
        # se génère directement depuis le SCÉNARIO par l'IA. Le découpage reste le
        # chemin recommandé mais n'est plus un prérequis.
        # Un découpage produit depuis une ancienne version du scénario ou de la
        # note de réalisation ne doit jamais alimenter silencieusement le
        # Storyboard. L'utilisateur garde la main sur sa validation éditoriale.
        from core.editorial_pipeline import status as editorial_status
        _pipeline_data = dict(self._current or {})
        _pipeline_data.update({
            "formatted_content": _src,
            "direction_note": (
                self._direction_note_edit.toPlainText()
                if hasattr(self, "_direction_note_edit") else ""
            ),
            "decoupage_content": _lay,
            "layout_content": _lay,
        })
        if _lay and editorial_status(_pipeline_data) == "decoupage_stale":
            # CONFIRMATION au lieu d'un blocage (décision Matthieu 2026-07-23) :
            # l'utilisateur comprend ce qui se passe et garde la main.
            _rep = QMessageBox.question(
                self,
                "Découpage à actualiser",
                "Le scénario ou la note de réalisation a changé depuis la création "
                "du Découpage.\n\nContinuer quand même avec ce découpage ?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if _rep != QMessageBox.StandardButton.Yes:
                self._ai_progress_lbl.setText("Génération annulée — actualise le Découpage.")
                return
        # Source AUTOMATIQUE (règle 2026-07-09) : Mise en page PANDORA si elle existe,
        # sinon le scénario. Mise en page STRUCTURÉE (« PLAN n — … ») → conversion
        # DÉTERMINISTE dans le worker (prompts co-écrits repris tels quels, zéro IA) :
        # aucun avertissement. On n'avertit QUE si la mise en page n'est pas parsable
        # et repasserait donc par l'IA qui REFORMULE (règle portée du Live 2026-07-13).
        if _lay:
            from core.decoupage_layout import is_structured_layout
            if not is_structured_layout(_lay):
                # CONFIRMATION au lieu d'un blocage (2026-07-23) : l'IA peut
                # réinterpréter un découpage non structuré, mais jamais en silence.
                _rep = QMessageBox.question(
                    self,
                    "Découpage non structuré",
                    "Le document n'est pas reconnu comme un Découpage PANDORA "
                    "structuré (fiches PLAN 01, PLAN 02…).\n\n"
                    "L'IA devra l'interpréter pour construire le storyboard. "
                    "Continuer ?",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                )
                if _rep != QMessageBox.StandardButton.Yes:
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
        # le BPM et les drops, comme dans PANDORA | Live. Source via _decoupage_base()
        # (mise en page si présente, sinon scénario).
        dlg = StoryboardGenerateDialog(self._text_with_music(), dur_secs, sc_id, parent=self)
        if dlg.exec() == StoryboardGenerateDialog.DialogCode.Accepted and dlg._shots:
            count = len(dlg._shots)
            if sc_id:
                synced = scenario_api.mark_storyboard_synced(sc_id)
                if synced:
                    self._current = synced
                    self._refresh_pipeline_status()
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
            self._btn_goto_storyboard.setVisible(False)   # bouton retiré (2026-07-22)

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
        """Aperçu du découpage — affiché seulement après validation du contrat v2."""
        from PyQt6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QTextEdit
        streaming = worker is not None
        dlg = QDialog(self)
        from core.ai_provider import ai_name_for_task
        dlg.setWindowTitle(
            f"{translate('Découpage PANDORA — Aperçu')} — "
            f"{ai_name_for_task('decoupage')}")
        dlg.resize(900, 680)
        dlg.setStyleSheet(
            f"QDialog{{background:{CP['bg1']};}}"
            f"QLabel{{background:transparent;color:{CP['text_primary']};}}"
        )
        lay = QVBoxLayout(dlg)
        lay.setContentsMargins(22, 20, 22, 20)
        lay.setSpacing(12)

        hdr = QHBoxLayout()
        title_lbl = QLabel(translate("◈  Découpage PANDORA — Aperçu"))
        title_lbl.setStyleSheet(f"color:{CP['text_primary']};font-size:14px;font-weight:700;")
        status_lbl = QLabel(translate("Découpage en cours…") if streaming else translate("Découpage terminé"))
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
            te.setPlaceholderText(translate(
                "Pandora construit et valide les fiches du Découpage PANDORA 2…"))
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
                self._ai_progress_lbl.setText("Découpage annulé.")
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

        btn_apply = QPushButton(translate("◈  Enregistrer dans « Découpage PANDORA »"))
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
            from core.decoupage_layout import validate_layout
            issues = validate_layout(result)
            if issues:
                QMessageBox.warning(
                    dlg,
                    "Découpage incomplet",
                    "Ce résultat ne peut pas encore être validé.\n\n"
                    "Chaque fiche PLAN 01, PLAN 02… doit séparer la source du scénario, "
                    "l'intention, une durée compatible et le PROMPT VISUEL.\n\n"
                    f"Points à corriger : {', '.join(issues[:8])}",
                )
                return
            # Le découpage va dans son onglet dédié — le scénario reste intact.
            self._apply_layout(result)
            self._ai_progress_lbl.setText("Découpage PANDORA créé ✓ (onglet dédié)")
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
                # Le worker ne diffuse plus les fragments non validés : on remplace
                # l'attente par le document v2 complet et seulement celui-ci.
                te.setPlainText(result)
                self._set_ai_busy(False)
                self._last_format_result = result
                self._last_result_kind = "format"
                self._btn_reopen_window.setVisible(False)   # bouton retiré (2026-07-22)
                self._ai_progress_lbl.setText("Découpage PANDORA terminé ✓")
                status_lbl.setText(translate("Découpage PANDORA terminé"))
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
                te.setPlainText(f"Erreur lors du découpage :\n{msg}")

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
        # Migration douce des analyses déjà sauvegardées : leur section 6 rejoint
        # la note dès la réouverture, sans nouvel appel IA et sans doublon.
        if analysis and worker is None:
            self._merge_analysis_direction_note(analysis)
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
            w = ApplyArrangeWorker(original, analysis_txt, intensity,
                                   refs_analysis=self._last_ref_analysis)
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
                note_added = self._merge_analysis_direction_note(_final_analysis[0])
                self._ai_progress_lbl.setText(
                    translate("Scénario appliqué et intentions ajoutées à la note ✓")
                    if note_added else
                    translate("Scénario réécrit et appliqué ✓")
                )
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
                note_added = self._merge_analysis_direction_note(result)
                btn_relaunch.setVisible(True)
                self._btn_reopen_window.setVisible(False)   # bouton retiré (2026-07-22)
                text = self._editor_text.toPlainText()
                mins, secs = self._estimate_duration(text)
                if mins or secs:
                    est = f"~{mins}m{secs:02d}" if mins else f"~{secs}s"
                    suffix = (translate(" · intentions ajoutées à la note")
                              if note_added else "")
                    self._ai_progress_lbl.setText(
                        f"{translate('Analyse terminée')} ✓  ·  "
                        f"{translate('Durée estimée')} : {est}{suffix}")
                else:
                    self._ai_progress_lbl.setText(
                        translate("Analyse terminée et intentions ajoutées à la note ✓")
                        if note_added else translate("Analyse terminée ✓"))
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
        """Ouvre le studio de co-écriture — REPREND la session persistée si elle existe."""
        from ui.dialog_arrange_session import ArrangeSessionDialog
        original   = self._get_text()
        intensity  = self._arrange_intensity_value
        saved = (self._current or {}).get("arrange_session") or None
        dlg = ArrangeSessionDialog(self, original, analysis_text, intensity,
                                   refs_analysis=self._last_ref_analysis,
                                   direction_note=self._direction_note_edit.toPlainText(),
                                   session_state=saved)
        # Autosave crash-proof : la session (conversation + scénario remanié) est
        # persistée dans le projet à CHAQUE tour — connecté AVANT exec() → plus
        # aucune perte, même si l'app plante ; réouverture = reprise à l'identique.
        dlg.session_committed.connect(self._on_arrange_session_autosave)
        dlg.exec()
        if dlg.was_applied():
            final = dlg.final_screenplay()
            if final:
                self._push_undo()
                self._set_editor_text(final)
                if self._current is not None:
                    self._current["formatted_content"] = final
                    self._save(silent=True)   # « Appliquer » → sauvegarde immédiate
                self._ai_progress_lbl.setText("Scénario co-écrit appliqué ✓")
                self._btn_undo_action.setVisible(True)
        # La note est un document autonome : elle est conservée même si aucune
        # réécriture narrative n'a été appliquée.
        note = dlg.final_direction_note()
        if note != self._direction_note_edit.toPlainText().strip():
            self._direction_note_edit.setPlainText(note)
            if self._current is not None:
                self._current["direction_note"] = note
                self._save(silent=True)

    def _on_arrange_session_autosave(self, state: dict):
        """Persiste la session de co-écriture dans le projet (reprise ultérieure)."""
        if self._current is not None:
            self._current["arrange_session"] = state
            if isinstance(state.get("direction_note"), str):
                self._current["direction_note"] = state["direction_note"]
                if hasattr(self, "_direction_note_edit"):
                    self._direction_note_edit.blockSignals(True)
                    self._direction_note_edit.setPlainText(state["direction_note"])
                    self._direction_note_edit.blockSignals(False)
            self._save(silent=True)

    def _open_refs_window(self, analysis: str = "", worker=None):
        """Fenêtre d'analyse des références visuelles.

        Modes :
          - worker fourni  → streaming en temps réel (ouverture immédiate)
          - analysis fourni → ré-ouverture avec texte complet (bouton Rouvrir)
        """
        from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QTextEdit,
                                     QScrollArea, QLineEdit, QMenu, QInputDialog)
        from core.ai_provider import ai_name

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
            if _chat_worker[0] is not None:
                _chat_worker[0].quit()
                abandon_thread(_chat_worker[0])
                _chat_worker[0] = None
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

        btn_enrich = QPushButton(translate("◎  Ajouter à la note de réalisation"))
        btn_enrich.setFixedHeight(36)
        btn_enrich.setEnabled(not streaming)
        btn_enrich.setToolTip(
            "Ajoute l'analyse du moodboard à la note de réalisation, sans modifier\n"
            "le scénario narratif."
        )
        btn_enrich.setStyleSheet(_accent_btn_ss)
        # Petit signe « déjà enrichi » (retour Matthieu 2026-07-06) : si le scénario a
        # déjà été enrichi avec l'analyse courante, on le montre sur le bouton — on peut
        # toujours cliquer pour ré-enrichir. Réinitialisé à chaque nouvelle analyse.
        if getattr(self, "_ref_enriched", False) and not streaming:
            btn_enrich.setText(translate("✓  Analyse déjà ajoutée à la note"))
            btn_enrich.setToolTip(translate(
                "Déjà ajoutée avec l'analyse courante — clique pour la réajouter."))
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
        _chat_worker    = [None]        # tour de dialogue DA en cours
        _chat_msgs: list = []           # historique du dialogue [{role, content}]

        def _do_enrich():
            txt = _final_analysis[0]
            if not txt:
                return
            from core.direction_note import append_to_note
            current_note = self._direction_note_edit.toPlainText()
            updated = append_to_note(
                current_note,
                "Références visuelles",
                txt,
                replace=True,
            )
            self._direction_note_edit.setPlainText(updated)
            self._ref_enriched = True
            if self._current is not None:
                self._current["direction_note"] = updated
            self._editor_tabs.setCurrentIndex(1)
            self._ai_progress_lbl.setText(
                "Références ajoutées à la note de réalisation ✓")
            self._schedule_autosave()
            dlg.accept()

        btn_enrich.clicked.connect(_do_enrich)

        # ── Dialogue direction artistique ─────────────────────────────────────
        chat_view = QTextEdit()
        chat_view.setReadOnly(True)
        chat_view.setVisible(False)
        chat_view.setFixedHeight(170)
        chat_view.setStyleSheet(
            f"QTextEdit{{background:{CP['bg3']};border:1px solid {CP['border']};"
            f"border-radius:8px;color:{CP['text_primary']};font-size:11px;padding:12px;}}"
        )
        lay.addWidget(chat_view)

        chat_row = QHBoxLayout()
        chat_row.setSpacing(8)
        chat_in = QLineEdit()
        chat_in.setFixedHeight(34)
        chat_in.setPlaceholderText(
            f"{translate('Discuter de la direction artistique avec')} {ai_name()}…")
        chat_in.setStyleSheet(
            f"QLineEdit{{background:{CP['bg2']};border:1px solid {CP['border']};"
            f"border-radius:7px;color:{CP['text_primary']};font-size:11px;padding:0 12px;}}"
            f"QLineEdit:focus{{border-color:{CP['accent']};}}"
            f"QLineEdit:disabled{{color:{CP['text_dim']};}}"
        )
        btn_send = QPushButton(translate("Envoyer"))
        btn_send.setFixedHeight(34)
        btn_send.setStyleSheet(_accent_btn_ss)
        chat_row.addWidget(chat_in, 1)
        chat_row.addWidget(btn_send)
        lay.addLayout(chat_row)

        def _set_chat_enabled(on: bool):
            chat_in.setEnabled(on)
            btn_send.setEnabled(on)

        _set_chat_enabled(not streaming and bool(_final_analysis[0]))

        def _append_chat(text: str):
            cursor = chat_view.textCursor()
            cursor.movePosition(cursor.MoveOperation.End)
            cursor.insertText(text)
            chat_view.setTextCursor(cursor)
            chat_view.ensureCursorVisible()

        def _send_chat():
            q = chat_in.text().strip()
            if not q or _chat_worker[0] is not None or not _final_analysis[0]:
                return
            chat_view.setVisible(True)
            _append_chat(("\n" if _chat_msgs else "")
                         + f"▶ {translate('Vous')} — {q}\n\n◆ {ai_name()} :\n")
            chat_in.clear()
            _set_chat_enabled(False)
            _chat_msgs.append({"role": "user", "content": q})
            from api.screenplay import RefsChatWorker
            w = RefsChatWorker(_chat_msgs, _final_analysis[0],
                               self._get_text() if self._current else "")
            _chat_worker[0] = w

            def _chat_done(result: str):
                _chat_msgs.append({"role": "assistant", "content": result})
                _append_chat("\n")
                # ANTI-CRASH : ne jamais lâcher la dernière référence d'un QThread
                # qui se termine encore — on le parque jusqu'à extinction réelle.
                abandon_thread(_chat_worker[0])
                _chat_worker[0] = None
                _set_chat_enabled(True)
                chat_in.setFocus()

            def _chat_failed(msg: str):
                if _chat_msgs and _chat_msgs[-1].get("role") == "user":
                    _chat_msgs.pop()   # la question peut être renvoyée telle quelle
                _append_chat(f"\n⚠ {msg}\n")
                abandon_thread(_chat_worker[0])
                _chat_worker[0] = None
                _set_chat_enabled(True)

            w.chunk.connect(_append_chat)
            w.done.connect(_chat_done)
            w.failed.connect(_chat_failed)
            w.start()

        btn_send.clicked.connect(_send_chat)
        chat_in.returnPressed.connect(_send_chat)

        # ── Relancer / Bibliothèque ───────────────────────────────────────────
        btn_relaunch = QPushButton(translate("↻  Relancer l'analyse"))
        btn_relaunch.setFixedHeight(36)
        btn_relaunch.setStyleSheet(_ghost_btn_ss)
        btn_relaunch.setToolTip(translate(
            "Refait l'analyse complète des images (une requête par image)."))
        btn_relaunch.setEnabled(not streaming and bool(self._ref_images))

        def _do_relaunch():
            n = len(self._ref_images)
            if not n:
                self._refs_status_lbl.setText(translate(
                    "Aucune image dans la section Références visuelles."))
                return
            _q = translate("Relancer l'analyse complète ?")
            reply = QMessageBox.question(
                dlg, translate("Relancer l'analyse"),
                f"{_q}\n{n} image(s) → {n} {translate('requête(s) IA')}.",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if reply != QMessageBox.StandardButton.Yes:
                return
            self._last_ref_analysis = ""
            self._ref_enriched = False
            dlg.accept()
            self._start_refs_analysis()

        btn_relaunch.clicked.connect(_do_relaunch)

        # Nouvelle analyse : vide les images ET l'analyse pour repartir de zéro
        # (le « Relancer » ci-dessus garde les MÊMES images).
        btn_new = QPushButton(translate("✚  Nouvelle analyse"))
        btn_new.setFixedHeight(36)
        btn_new.setStyleSheet(_ghost_btn_ss)
        btn_new.setToolTip(translate("Vide les images ET l'analyse pour repartir de zéro."))
        btn_new.setEnabled(not streaming)

        def _do_new_analysis():
            reply = QMessageBox.question(
                dlg, translate("Nouvelle analyse"),
                translate("Vider les images et l'analyse pour repartir de zéro ?"),
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if reply != QMessageBox.StandardButton.Yes:
                return
            self._ref_images = []
            self._last_ref_analysis = ""
            self._ref_enriched = False
            self._refresh_refs_display()
            self._schedule_autosave()
            dlg.accept()

        btn_new.clicked.connect(_do_new_analysis)

        btn_save_lib = QPushButton(translate("💾  Sauvegarder"))
        btn_save_lib.setFixedHeight(36)
        btn_save_lib.setStyleSheet(_ghost_btn_ss)
        btn_save_lib.setToolTip(translate(
            "Sauvegarde cette analyse dans la bibliothèque globale\n"
            "pour la réutiliser dans d'autres projets."))
        btn_save_lib.setEnabled(not streaming and bool(_final_analysis[0]))

        def _do_save_lib():
            txt = _final_analysis[0]
            if not txt:
                return
            default = self._title_edit.text().strip() or translate("Analyse sans titre")
            name, ok = QInputDialog.getText(
                dlg, translate("Sauvegarder l'analyse"),
                translate("Nom de l'analyse :"), text=default)
            if not ok or not name.strip():
                return
            from core import ref_library
            ref_library.save_analysis(name.strip(), txt, self._ref_images, "cinema")
            self._refs_status_lbl.setText(translate("Analyse sauvegardée dans la bibliothèque ✓"))

        btn_save_lib.clicked.connect(_do_save_lib)

        btn_lib = QPushButton(translate("📂  Bibliothèque"))
        btn_lib.setFixedHeight(36)
        btn_lib.setStyleSheet(_ghost_btn_ss)
        btn_lib.setToolTip(translate(
            "Charge une analyse sauvegardée — mêmes références visuelles,\n"
            "même direction artistique, sans refaire l'analyse."))
        btn_lib.setEnabled(not streaming)

        def _load_lib_entry(e: dict):
            txt = e.get("analysis", "")
            if not txt:
                return
            _final_analysis[0] = txt
            te.setPlainText(txt)
            self._last_ref_analysis = txt
            self._last_result_kind = "refs"
            self._btn_reopen_window.setVisible(False)   # bouton retiré (2026-07-22)
            imgs = [p for p in e.get("images", [])
                    if isinstance(p, str) and os.path.isfile(p)]
            if imgs:
                self._ref_images = imgs
                self._refresh_refs_display()
            btn_enrich.setEnabled(True)
            btn_enrich.setVisible(True)
            btn_save_lib.setEnabled(True)
            btn_relaunch.setEnabled(bool(self._ref_images))
            _set_chat_enabled(True)
            if self._current is not None:
                self._save(silent=True)
            self._refs_status_lbl.setText(
                f"{translate('Analyse chargée')} : {e.get('name', '')} ✓")
            self._refs_status_lbl.setStyleSheet(
                f"color:{CP['green']};font-size:10px;font-family:'Consolas',monospace;")

        def _delete_lib_entry(e: dict):
            from core import ref_library
            if ref_library.delete_analysis(e.get("_file", "")):
                self._refs_status_lbl.setText(translate("Analyse supprimée de la bibliothèque."))

        def _open_lib_menu():
            from core import ref_library
            entries = ref_library.list_analyses()
            menu = QMenu(dlg)
            menu.setStyleSheet(
                f"QMenu{{background:{CP['bg2']};color:{CP['text_primary']};"
                f"border:1px solid {CP['border_bright']};border-radius:6px;padding:4px;}}"
                f"QMenu::item{{padding:6px 14px;border-radius:4px;}}"
                f"QMenu::item:selected{{background:{CP['bg4']};}}"
            )
            if not entries:
                act = menu.addAction(translate("Aucune analyse sauvegardée"))
                act.setEnabled(False)
            for e in entries:
                lbl = (f"{e.get('name', '?')}  —  {e.get('mode', 'cinema')} · "
                       f"{len(e.get('images', []))} img · {e.get('date', '')}")
                act = menu.addAction(lbl)
                act.triggered.connect(lambda checked=False, ee=e: _load_lib_entry(ee))
            if entries:
                menu.addSeparator()
                sub = menu.addMenu(translate("Supprimer une analyse"))
                for e in entries:
                    act = sub.addAction(e.get("name", "?"))
                    act.triggered.connect(lambda checked=False, ee=e: _delete_lib_entry(ee))
            menu.exec(btn_lib.mapToGlobal(btn_lib.rect().bottomLeft()))

        btn_lib.clicked.connect(_open_lib_menu)

        btn_row.addWidget(btn_close)
        btn_row.addWidget(btn_relaunch)
        btn_row.addWidget(btn_new)
        btn_row.addWidget(btn_save_lib)
        btn_row.addWidget(btn_lib)
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
                self._btn_reopen_window.setVisible(False)   # bouton retiré (2026-07-22)
                self._refs_status_lbl.setText(f"{n} image(s) analysée(s)")
                self._refs_status_lbl.setStyleSheet(
                    f"color:{CP['text_dim']};font-size:10px;font-family:'Consolas',monospace;"
                )
                btn_enrich.setEnabled(True)
                btn_relaunch.setEnabled(bool(self._ref_images))
                btn_save_lib.setEnabled(True)
                btn_lib.setEnabled(True)
                _set_chat_enabled(True)
                # Persistance immédiate : l'analyse (et les refs) survivent à la fermeture
                if self._current is not None:
                    self._save(silent=True)

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

        # Entrée dans le champ de chat = ENVOYER — jamais le bouton par défaut Qt
        from ui.widgets import disable_default_buttons
        disable_default_buttons(dlg)
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
                    import core.casting as _c
                    _i["image_path"] = img
                    _c.save_character(_i)
                    self._gen_all_analyze_identity("character", _i, img, _c.save_character)
                else:
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
            def _done_item(p, _i=item, _m=_mod, _f=_sfn, _t=item_type):
                if p:
                    import importlib; m = importlib.import_module(_m)
                    _i["image_path"] = p
                    _save = getattr(m, _f)
                    _save(_i)
                    self._gen_all_analyze_identity(_t, _i, p, _save)
                else:
                    self._gen_all_next_image()
            w.finished.connect(_done_item)
            w.failed.connect(lambda _e: (
                self.__dict__.update({"_gen_all_error_count": self._gen_all_error_count + 1}),
                self._gen_all_next_image(),
            ))

        self._gen_all_workers.append(w)
        w.start()

    def _gen_all_analyze_identity(self, item_type: str, item: dict, image_path: str,
                                  save_callable):
        """Dans le mode Tout générer, l'image produite est analysée avant de passer
        à l'entité suivante. Le Storyboard récupère ainsi la description réelle de
        l'image, pas seulement le prompt qui avait servi à la créer."""
        from api.visual_identity import VisualIdentityWorker
        from core.visual_identity import pending_identity
        item["visual_identity"] = pending_identity(image_path, "generated")
        save_callable(item)
        desc = item.get("description") or item.get("prompt") or ""
        worker = VisualIdentityWorker(item_type, image_path, "generated", desc)

        def _ready(identity: dict):
            item["visual_identity"] = identity
            save_callable(item)
            self._gen_all_next_image()

        def _failed(_message: str):
            # L'image et le statut pending restent persistés ; le dialogue de
            # l'entité relancera automatiquement l'analyse à sa prochaine ouverture.
            self._gen_all_next_image()

        worker.done.connect(_ready)
        worker.failed.connect(_failed)
        self._gen_all_workers.append(worker)
        worker.start()

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
        self._btn_goto_storyboard.setVisible(False)   # bouton retiré (2026-07-22)
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
