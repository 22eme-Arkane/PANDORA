"""
ui/dialog_arrange_session.py — Studio de co-écriture Claude × Réalisateur.

Fenêtre ouverte depuis la page Scénario quand l'utilisateur clique sur
"Afficher les résultats en grand" après un arrangement Claude.

Layout :
  ┌───────────────────────────────────────────────────────────────────┐
  │  ☁ Studio de Création — Arrangement IA                           │
  ├────────────────────────────┬──────────────────────────────────────┤
  │  Analyse  │  Scénario      │  Dialogue avec Claude               │
  │           │  remanié       │  ┌──────────────────────────────┐   │
  │  [texte   │  [prévisual.   │  │  bulles de chat              │   │
  │   analyse]│   screenplay]  │  └──────────────────────────────┘   │
  │           │                │  ┌──────────────────────────────┐   │
  │           │                │  │ Votre message...              │   │
  │           │                │  └──────────────────────────────┘   │
  │           │                │  [Envoyer à Claude ☁]               │
  ├────────────────────────────┴──────────────────────────────────────┤
  │  [✓ Appliquer ce scénario]         [Copier]        [Fermer]       │
  └───────────────────────────────────────────────────────────────────┘
"""

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTextEdit, QSplitter, QTabWidget, QWidget, QProgressBar,
    QFrame, QScrollArea, QApplication, QFileDialog, QSlider,
)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QFont, QColor, QTextCursor, QPixmap
from ui.styles import CP
from core.i18n import translate


# ── Helpers ────────────────────────────────────────────────────────────────────

def _btn(label: str, style: str = "ghost", min_h: int = 36) -> QPushButton:
    b = QPushButton(label)
    b.setMinimumHeight(min_h)
    b.setCursor(Qt.CursorShape.PointingHandCursor)
    if style == "accent":
        b.setStyleSheet(
            f"QPushButton{{background:{CP['accent']};color:#07080f;border:none;"
            f"border-radius:8px;font-size:12px;font-weight:700;padding:0 20px;}}"
            f"QPushButton:hover{{background:#6eded6;}}"
            f"QPushButton:pressed{{background:{CP['accent_dim']};color:#fff;}}"
            f"QPushButton:disabled{{background:{CP['bg3']};color:{CP['text_dim']};}}"
        )
    elif style == "purple":
        b.setStyleSheet(
            f"QPushButton{{background:{CP['accent2']};color:#fff;border:none;"
            f"border-radius:8px;font-size:12px;font-weight:700;padding:0 20px;}}"
            f"QPushButton:hover{{background:#9d8fff;}}"
            f"QPushButton:pressed{{background:rgba(124,107,255,0.7);}}"
            f"QPushButton:disabled{{background:{CP['bg3']};color:{CP['text_dim']};}}"
        )
    else:
        b.setStyleSheet(
            f"QPushButton{{background:transparent;color:{CP['text_secondary']};"
            f"border:1px solid {CP['border']};border-radius:8px;"
            f"font-size:11px;font-weight:600;padding:0 16px;}}"
            f"QPushButton:hover{{background:{CP['bg3']};color:{CP['text_primary']};"
            f"border-color:{CP['border_bright']};}}"
            f"QPushButton:disabled{{color:{CP['text_dim']};border-color:{CP['border']};}}"
        )
    return b


def _section_lbl(text: str) -> QLabel:
    lbl = QLabel(translate(text).upper())
    lbl.setStyleSheet(
        f"color:{CP['accent']};font-size:9px;font-weight:700;"
        f"letter-spacing:3px;font-family:'Consolas',monospace;background:transparent;"
    )
    return lbl


def _sep() -> QFrame:
    f = QFrame()
    f.setFixedHeight(1)
    f.setStyleSheet(f"background:{CP['border']};")
    return f


_MONO = QFont("Courier New", 11)
_MONO.setStyleHint(QFont.StyleHint.TypeWriter)


def _intensity_label(v: int) -> str:
    if v <= 2:   return translate("Minimal — uniquement ce qui est demandé, rien d'autre")
    if v <= 4:   return translate("Précis — modifie exactement les zones indiquées")
    if v <= 6:   return translate("Ciblé — suit l'instruction, affine légèrement le style dans la zone")
    if v <= 8:   return translate("Créatif — enrichit et reformule, retouche les passages adjacents")
    return           translate("Libre — réécrit dans son style, transforme le rythme et l'écriture")


# ── Bulle de chat HTML ────────────────────────────────────────────────────────

def _bubble_html(text: str, role: str) -> str:
    """Génère une bulle de chat HTML. role = 'user' | 'claude'."""
    text_esc = (
        text.replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace("\n", "<br>")
    )
    if role == "user":
        bg      = f"rgba(124,107,255,0.14)"
        border  = f"rgba(124,107,255,0.35)"
        label   = "Vous"
        lbl_col = CP["accent2"]
        align   = "right"
        margin  = "margin-left:60px;margin-right:0;"
    else:
        bg      = f"rgba(78,205,196,0.08)"
        border  = f"rgba(78,205,196,0.25)"
        label   = "Claude IA"
        lbl_col = CP["accent"]
        align   = "left"
        margin  = "margin-right:60px;margin-left:0;"
    return (
        f'<div style="text-align:{align};{margin}margin-bottom:14px;">'
        f'<span style="font-size:9px;font-weight:700;color:{lbl_col};">{label}</span><br>'
        f'<span style="display:inline-block;background:{bg};border:1px solid {border};'
        f'border-radius:10px;padding:10px 14px;font-size:12px;line-height:1.55;'
        f'color:{CP["text_primary"]};">'
        f'{text_esc}</span></div>'
    )


# ── Dialog principal ───────────────────────────────────────────────────────────

class ArrangeSessionDialog(QDialog):
    """Studio de co-écriture interactif Claude × Réalisateur."""

    def __init__(
        self,
        parent,
        original_screenplay: str,
        analysis_result: str,
        intensity: int = 5,
        refs_analysis: str = "",
    ):
        super().__init__(parent)
        self.setWindowTitle("☁  Studio de Création — Co-écriture avec Claude")
        self.setStyleSheet(f"QDialog{{background:{CP['bg0']};}}")
        from ui.widgets import fit_dialog_to_screen
        fit_dialog_to_screen(self, 0.82, 0.88, 800, 540)

        self._original    = original_screenplay
        self._analysis    = analysis_result
        self._intensity   = intensity
        # Direction artistique (analyse des références visuelles) — injectée dans
        # chaque tour de co-écriture si présente (parité Live 2026-07-13).
        self._refs_analysis = refs_analysis or ""
        self._history: list[dict] = []
        self._worker      = None
        self._screenplay  = ""          # version remaniée courante
        self._applied     = False       # True si l'utilisateur a appliqué
        self._ref_images: list[str] = []
        self._screenplay_versions: list[str] = []
        self._version_idx: int = -1

        self._build_ui()
        self._show_initial_analysis()

        from core.i18n import retranslate_widget
        retranslate_widget(self)

    # ── Construction de l'UI ──────────────────────────────────────────────────

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ── Header ─────────────────────────────────────────────────────────
        header = QWidget()
        header.setFixedHeight(54)
        header.setStyleSheet(
            f"background:{CP['bg1']};border-bottom:1px solid {CP['border']};"
        )
        h_lay = QHBoxLayout(header)
        h_lay.setContentsMargins(24, 0, 24, 0)
        h_lay.setSpacing(10)

        ico = QLabel("☁")
        ico.setStyleSheet(f"font-size:22px;color:{CP['accent']};background:transparent;")
        h_lay.addWidget(ico)

        title = QLabel("Studio de Création — Co-écriture avec Claude")
        title.setStyleSheet(
            f"color:{CP['text_primary']};font-size:16px;font-weight:700;"
            f"background:transparent;"
        )
        h_lay.addWidget(title)
        h_lay.addStretch()

        self._progress_bar = QProgressBar()
        self._progress_bar.setFixedSize(120, 4)
        self._progress_bar.setTextVisible(False)
        self._progress_bar.setRange(0, 0)
        self._progress_bar.setStyleSheet(
            f"QProgressBar{{background:{CP['bg3']};border-radius:2px;border:none;}}"
            f"QProgressBar::chunk{{background:{CP['accent']};border-radius:2px;}}"
        )
        self._progress_bar.hide()
        h_lay.addWidget(self._progress_bar)

        self._status_lbl = QLabel("")
        self._status_lbl.setStyleSheet(
            f"color:{CP['text_dim']};font-size:10px;font-family:'Consolas',monospace;"
            f"background:transparent;"
        )
        h_lay.addWidget(self._status_lbl)

        root.addWidget(header)

        # ── Corps : splitter horizontal ─────────────────────────────────────
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setStyleSheet(
            f"QSplitter::handle{{background:{CP['border']};width:1px;}}"
        )
        root.addWidget(splitter, 1)

        # Panneau gauche : onglets Analyse / Scénario remanié
        left = self._build_left_panel()
        splitter.addWidget(left)

        # Panneau droit : chat
        right = self._build_right_panel()
        splitter.addWidget(right)

        splitter.setSizes([620, 420])
        splitter.setCollapsible(0, False)
        splitter.setCollapsible(1, False)

        # ── Barre d'actions ─────────────────────────────────────────────────
        footer = QWidget()
        footer.setFixedHeight(58)
        footer.setStyleSheet(
            f"background:{CP['bg1']};border-top:1px solid {CP['border']};"
        )
        f_lay = QHBoxLayout(footer)
        f_lay.setContentsMargins(24, 0, 24, 0)
        f_lay.setSpacing(10)

        self._btn_apply = _btn("✓  Appliquer ce scénario au projet", "accent", 38)
        self._btn_apply.setEnabled(False)
        self._btn_apply.setToolTip(
            "Remplace le scénario de l'éditeur par la version co-écrite avec Claude"
        )
        self._btn_apply.clicked.connect(self._on_apply)

        self._btn_copy = _btn("⎘  Copier", "ghost", 38)
        self._btn_copy.setToolTip("Copier le scénario remanié dans le presse-papier")
        self._btn_copy.setEnabled(False)
        self._btn_copy.clicked.connect(self._on_copy)

        btn_close = _btn("Fermer", "ghost", 38)
        btn_close.clicked.connect(self.reject)

        f_lay.addWidget(self._btn_apply)
        f_lay.addWidget(self._btn_copy)
        f_lay.addStretch()
        f_lay.addWidget(btn_close)

        root.addWidget(footer)

    def _build_left_panel(self) -> QWidget:
        w = QWidget()
        w.setStyleSheet(f"background:{CP['bg0']};")
        lay = QVBoxLayout(w)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)

        self._tabs = QTabWidget()
        self._tabs.setStyleSheet(f"""
            QTabWidget::pane {{
                border:none;background:{CP['bg0']};
            }}
            QTabBar::tab {{
                background:{CP['bg2']};color:{CP['text_dim']};
                border:1px solid {CP['border']};border-bottom:none;
                border-radius:6px 6px 0 0;
                padding:7px 18px;font-size:11px;font-weight:600;
                margin-right:2px;
            }}
            QTabBar::tab:selected {{
                background:{CP['bg0']};color:{CP['text_primary']};
                border-bottom:none;
            }}
            QTabBar::tab:hover:!selected {{
                color:{CP['text_secondary']};background:{CP['bg3']};
            }}
        """)

        # Onglet 1 — Analyse initiale
        self._analysis_edit = QTextEdit()
        self._analysis_edit.setReadOnly(True)
        self._analysis_edit.setFont(_MONO)
        self._analysis_edit.setStyleSheet(
            f"QTextEdit{{background:{CP['bg0']};border:none;"
            f"color:{CP['text_secondary']};font-size:11px;padding:20px;}}"
        )
        self._tabs.addTab(self._analysis_edit, "☁  Analyse initiale")

        # Onglet 2 — Scénario remanié (live preview)
        self._screenplay_edit = QTextEdit()
        self._screenplay_edit.setReadOnly(False)   # éditable à la main si besoin
        self._screenplay_edit.setFont(_MONO)
        self._screenplay_edit.setStyleSheet(
            f"QTextEdit{{background:{CP['bg0']};border:none;"
            f"color:{CP['text_primary']};font-size:12px;padding:20px;}}"
        )
        self._screenplay_edit.setPlaceholderText(
            "Le scénario remanié apparaîtra ici après votre première instruction à Claude…\n\n"
            "Utilisez la zone de dialogue à droite pour co-écrire avec Claude."
        )
        self._screenplay_edit.textChanged.connect(self._on_screenplay_edited)

        tab2_widget = QWidget()
        tab2_widget.setStyleSheet(f"background:{CP['bg0']};")
        t2_lay = QVBoxLayout(tab2_widget)
        t2_lay.setContentsMargins(0, 0, 0, 0)
        t2_lay.setSpacing(0)

        # ── Barre de navigation entre versions ────────────────────────────────
        _arrow_ss = (
            f"QPushButton{{background:transparent;color:{CP['text_secondary']};"
            f"border:1px solid {CP['border']};border-radius:5px;"
            f"font-size:14px;font-weight:700;padding:0;}}"
            f"QPushButton:hover{{background:{CP['bg3']};color:{CP['text_primary']};"
            f"border-color:{CP['border_bright']};}}"
            f"QPushButton:disabled{{color:{CP['bg3']};border-color:{CP['bg3']};}}"
        )
        self._ver_nav_bar = QWidget()
        self._ver_nav_bar.setFixedHeight(30)
        self._ver_nav_bar.setStyleSheet(
            f"background:{CP['bg1']};border-bottom:1px solid {CP['border']};"
        )
        vnav = QHBoxLayout(self._ver_nav_bar)
        vnav.setContentsMargins(12, 0, 12, 0)
        vnav.setSpacing(8)

        self._btn_prev_ver = QPushButton("←")
        self._btn_prev_ver.setFixedSize(26, 22)
        self._btn_prev_ver.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_prev_ver.setEnabled(False)
        self._btn_prev_ver.setStyleSheet(_arrow_ss)
        self._btn_prev_ver.clicked.connect(self._nav_version_prev)

        self._ver_lbl = QLabel("v 1/1")
        self._ver_lbl.setStyleSheet(
            f"color:{CP['text_dim']};font-size:9px;font-weight:600;"
            f"font-family:'Consolas',monospace;background:transparent;"
        )
        self._ver_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self._btn_next_ver = QPushButton("→")
        self._btn_next_ver.setFixedSize(26, 22)
        self._btn_next_ver.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_next_ver.setEnabled(False)
        self._btn_next_ver.setStyleSheet(_arrow_ss)
        self._btn_next_ver.clicked.connect(self._nav_version_next)

        vnav.addStretch()
        vnav.addWidget(self._btn_prev_ver)
        vnav.addWidget(self._ver_lbl)
        vnav.addWidget(self._btn_next_ver)
        vnav.addStretch()

        self._ver_nav_bar.hide()
        t2_lay.addWidget(self._ver_nav_bar)
        t2_lay.addWidget(self._screenplay_edit, 1)

        # Badge "modifié à la main"
        self._manual_edit_lbl = QLabel("✏  Édition manuelle active")
        self._manual_edit_lbl.setAlignment(Qt.AlignmentFlag.AlignRight)
        self._manual_edit_lbl.setStyleSheet(
            f"color:{CP['orange']};font-size:9px;font-family:'Consolas',monospace;"
            f"background:{CP['bg1']};padding:2px 10px;"
            f"border-top:1px solid {CP['border']};"
        )
        self._manual_edit_lbl.hide()
        t2_lay.addWidget(self._manual_edit_lbl)

        self._tabs.addTab(tab2_widget, "✦  Scénario remanié")
        self._tabs.setTabEnabled(1, False)          # désactivé jusqu'au premier échange

        lay.addWidget(self._tabs)
        return w

    def _build_right_panel(self) -> QWidget:
        w = QWidget()
        w.setStyleSheet(f"background:{CP['bg1']};")
        lay = QVBoxLayout(w)
        lay.setContentsMargins(20, 18, 20, 18)
        lay.setSpacing(14)

        lay.addWidget(_section_lbl("Dialogue avec Claude"))

        # Historique du chat
        self._chat_view = QTextEdit()
        self._chat_view.setReadOnly(True)
        self._chat_view.setStyleSheet(
            f"QTextEdit{{background:{CP['bg2']};border:1px solid {CP['border']};"
            f"border-radius:10px;color:{CP['text_primary']};font-size:12px;padding:12px;}}"
        )
        self._chat_view.setMinimumHeight(200)
        lay.addWidget(self._chat_view, 1)

        # Hint initial
        self._chat_hint = QLabel(
            "💬  Dites à Claude ce que vous voulez changer.\n"
            "Ex : « Garde la scène 3 intacte », « Rends les dialogues plus percutants »,\n"
            "« Développe l'acte 2 », « Coupe toutes les voix off »…"
        )
        self._chat_hint.setWordWrap(True)
        self._chat_hint.setStyleSheet(
            f"color:{CP['text_dim']};font-size:10px;font-style:italic;"
            f"background:transparent;"
        )
        lay.addWidget(self._chat_hint)

        # ── Références visuelles ──────────────────────────────────────────────
        lay.addWidget(_section_lbl("Références visuelles"))

        refs_scroll = QScrollArea()
        refs_scroll.setFixedHeight(72)
        refs_scroll.setWidgetResizable(True)
        refs_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        refs_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        refs_scroll.setFrameStyle(0)
        refs_scroll.setStyleSheet(
            "QScrollArea{border:none;background:transparent;}"
            f"QScrollBar:horizontal{{background:{CP['bg2']};height:3px;border-radius:2px;}}"
            f"QScrollBar::handle:horizontal{{background:{CP['border_bright']};border-radius:2px;}}"
            f"QScrollBar::add-line:horizontal,QScrollBar::sub-line:horizontal{{width:0;}}"
        )
        self._refs_ctn = QWidget()
        self._refs_ctn.setStyleSheet("background:transparent;")
        self._refs_hbox = QHBoxLayout(self._refs_ctn)
        self._refs_hbox.setContentsMargins(0, 0, 0, 0)
        self._refs_hbox.setSpacing(6)
        refs_scroll.setWidget(self._refs_ctn)
        lay.addWidget(refs_scroll)

        self._refs_hint = QLabel("📎  Joindre des images pour enrichir les descriptions — max 4")
        self._refs_hint.setStyleSheet(
            f"color:{CP['text_dim']};font-size:9px;font-style:italic;background:transparent;"
        )
        lay.addWidget(self._refs_hint)

        self._refresh_refs_strip()

        # ── Intensité d'arrangement ───────────────────────────────────────────
        _ih = QHBoxLayout()
        _ih.setSpacing(6)
        _ititle = QLabel("Intensité d'arrangement")
        _ititle.setStyleSheet(
            f"color:{CP['text_secondary']};font-size:9px;font-weight:600;background:transparent;"
        )
        self._intensity_lbl = QLabel(str(self._intensity))
        self._intensity_lbl.setFixedWidth(16)
        self._intensity_lbl.setAlignment(Qt.AlignmentFlag.AlignRight)
        self._intensity_lbl.setStyleSheet(
            f"color:{CP['accent2']};font-size:10px;font-weight:700;background:transparent;"
        )
        _ih.addWidget(_ititle)
        _ih.addStretch()
        _ih.addWidget(self._intensity_lbl)

        self._intensity_slider = QSlider(Qt.Orientation.Horizontal)
        self._intensity_slider.setRange(1, 10)
        self._intensity_slider.setValue(self._intensity)
        self._intensity_slider.setFixedHeight(16)
        self._intensity_slider.setStyleSheet(f"""
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
        self._intensity_desc = QLabel(_intensity_label(self._intensity))
        self._intensity_desc.setWordWrap(True)
        self._intensity_desc.setStyleSheet(
            f"color:{CP['accent2']};font-size:8px;font-style:italic;background:transparent;"
        )
        def _on_intensity(v):
            self._intensity = v
            self._intensity_lbl.setText(str(v))
            self._intensity_desc.setText(_intensity_label(v))
        self._intensity_slider.valueChanged.connect(_on_intensity)

        lay.addLayout(_ih)
        lay.addWidget(self._intensity_slider)
        lay.addWidget(self._intensity_desc)

        lay.addWidget(_section_lbl("Votre instruction"))


        # Zone de saisie
        self._input_edit = QTextEdit()
        self._input_edit.setMaximumHeight(110)
        self._input_edit.setMinimumHeight(70)
        self._input_edit.setPlaceholderText(
            "Entrez votre instruction ici…\n"
            "Ex : « Ne change pas le flashback de la scène 4 »"
        )
        self._input_edit.setStyleSheet(
            f"QTextEdit{{background:{CP['bg2']};border:1px solid {CP['border']};"
            f"border-radius:8px;color:{CP['text_primary']};font-size:12px;padding:10px 12px;}}"
            f"QTextEdit:focus{{border-color:{CP['accent_dim']};}}"
        )
        # Ctrl+Enter → envoyer
        self._input_edit.installEventFilter(self)
        lay.addWidget(self._input_edit)

        send_row = QHBoxLayout()
        send_row.setSpacing(8)

        self._btn_send = _btn("Envoyer à Claude  ☁", "purple", 38)
        self._btn_send.clicked.connect(self._on_send)
        send_row.addWidget(self._btn_send, 1)

        self._btn_reset = _btn("✕ Effacer", "ghost", 38)
        self._btn_reset.setFixedWidth(80)
        self._btn_reset.setToolTip("Efface le champ de saisie")
        self._btn_reset.clicked.connect(lambda: self._input_edit.clear())
        send_row.addWidget(self._btn_reset)

        lay.addLayout(send_row)

        # Bouton « Générer le scénario » : réécriture COMPLÈTE volontaire. Le chat
        # ci-dessus reste CHIRURGICAL (il n'édite que les passages concernés) → ce
        # bouton est le SEUL à réécrire tout le scénario, quand on le décide.
        self._btn_generate = _btn("✎  Générer le scénario", "ghost", 34)
        self._btn_generate.setToolTip(
            "Réécrit le scénario COMPLET en intégrant toute la discussion "
            "(coûteux en tokens — le chat ne modifie que les passages demandés).")
        self._btn_generate.clicked.connect(self._on_generate_full)
        lay.addWidget(self._btn_generate)

        # Raccourci info
        shortcut_lbl = QLabel("Ctrl+↵ pour envoyer")
        shortcut_lbl.setStyleSheet(
            f"color:{CP['text_dim']};font-size:9px;font-family:'Consolas',monospace;"
            f"background:transparent;"
        )
        lay.addWidget(shortcut_lbl)

        return w

    # ── Références visuelles ──────────────────────────────────────────────────

    def _refresh_refs_strip(self):
        while self._refs_hbox.count():
            item = self._refs_hbox.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        btn_add = QPushButton("＋")
        btn_add.setFixedSize(58, 58)
        btn_add.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_add.setToolTip("Ajouter des images de référence (max 4)")
        btn_add.setEnabled(len(self._ref_images) < 4)
        btn_add.setStyleSheet(
            f"QPushButton{{background:{CP['bg2']};color:{CP['text_dim']};"
            f"border:2px dashed {CP['border']};border-radius:6px;"
            f"font-size:22px;font-weight:300;}}"
            f"QPushButton:hover{{background:{CP['bg3']};color:{CP['text_secondary']};"
            f"border-color:{CP['border_bright']};}}"
            f"QPushButton:disabled{{color:{CP['text_dim']};border-color:{CP['border']};}}"
        )
        btn_add.clicked.connect(self._on_add_refs)
        self._refs_hbox.addWidget(btn_add)

        for path in self._ref_images:
            cell = QWidget()
            cell.setFixedSize(58, 58)
            cell.setStyleSheet("background:transparent;")

            thumb = QLabel(cell)
            thumb.setFixedSize(58, 58)
            thumb.setScaledContents(True)
            thumb.setStyleSheet(
                f"border-radius:6px;border:1px solid {CP['border']};"
                f"background:{CP['bg2']};"
            )
            px = QPixmap(path)
            if not px.isNull():
                thumb.setPixmap(px)
            else:
                thumb.setText("?")
                thumb.setAlignment(Qt.AlignmentFlag.AlignCenter)

            btn_rm = QPushButton("✕", cell)
            btn_rm.setFixedSize(16, 16)
            btn_rm.move(42, 0)
            btn_rm.setCursor(Qt.CursorShape.PointingHandCursor)
            btn_rm.setStyleSheet(
                f"QPushButton{{background:{CP['bg3']};color:{CP['text_primary']};"
                f"border:1px solid {CP['border_bright']};border-radius:4px;"
                f"font-size:9px;font-weight:700;padding:0;}}"
                f"QPushButton:hover{{background:{CP['red']};color:#fff;border-color:{CP['red']};}}"
            )
            btn_rm.clicked.connect(lambda checked, p=path: self._remove_ref(p))

            self._refs_hbox.addWidget(cell)

        self._refs_hbox.addStretch()

    def _on_add_refs(self):
        if len(self._ref_images) >= 4:
            return
        from ui.dialog_image_library import ImageLibraryDialog
        paths = ImageLibraryDialog.pick(self)
        if not paths:
            return
        remaining = 4 - len(self._ref_images)
        for p in paths[:remaining]:
            if p not in self._ref_images:
                self._ref_images.append(p)
        self._refresh_refs_strip()

    def _remove_ref(self, path: str):
        if path in self._ref_images:
            self._ref_images.remove(path)
        self._refresh_refs_strip()

    # ── État initial ──────────────────────────────────────────────────────────

    def _show_initial_analysis(self):
        """Affiche l'analyse Claude dans l'onglet 1 et ouvre le chat avec le 1er message."""
        self._analysis_edit.setPlainText(self._analysis)

        # Premier message Claude dans le chat = l'analyse initiale (résumé court)
        intro = translate(
            "J'ai analysé votre scénario et rédigé des suggestions détaillées "
            "(visibles dans l'onglet « Analyse initiale »).\n\n"
            "Dites-moi ce que vous souhaitez modifier, affiner ou conserver — "
            "je produirai alors une version remaniée de votre scénario en direct. "
            "Nous pouvons itérer autant de fois que nécessaire."
        )
        self._append_chat_bubble(intro, "claude")

    # ── Chat ─────────────────────────────────────────────────────────────────

    def _append_chat_bubble(self, text: str, role: str):
        html = _bubble_html(text, role)
        cursor = self._chat_view.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        self._chat_view.setTextCursor(cursor)
        self._chat_view.insertHtml(html)
        self._chat_view.insertPlainText("\n")
        # Scroll to bottom
        sb = self._chat_view.verticalScrollBar()
        sb.setValue(sb.maximum())

    def _on_send(self):
        msg = self._input_edit.toPlainText().strip()
        if not msg:
            return
        self._input_edit.clear()
        self._chat_hint.hide()
        self._append_chat_bubble(msg, "user")
        self._history.append({"role": "user", "content": msg})
        images = list(self._ref_images)
        self._ref_images.clear()
        self._refresh_refs_strip()
        self._start_worker(msg, ref_images=images)

    def _start_worker(self, user_message: str, ref_images: list | None = None,
                      surgical: bool = True):
        from api.screenplay import ArrangeChatWorker

        if self._worker and self._worker.isRunning():
            self._worker.quit()

        self._set_busy(True, "Rédaction en cours…" if surgical else "Génération complète…")

        # Le chat CHIRURGICAL édite la version COURANTE (dernière obtenue) — pas
        # l'original figé : les modifs s'enchaînent.
        base = self._screenplay or self._original
        self._worker = ArrangeChatWorker(
            original=base,
            analysis=self._analysis,
            history=self._history[:-1] if surgical else list(self._history),
            user_message=user_message,
            intensity=self._intensity,
            ref_images=ref_images or [],
            refs_analysis=self._refs_analysis,
            surgical=surgical,
        )
        self._worker.message_ready.connect(self._on_message_ready)
        if surgical:
            self._worker.edits_ready.connect(self._on_edits_ready)
        else:
            self._worker.screenplay_ready.connect(self._on_screenplay_ready)
        self._worker.failed.connect(self._on_failed)
        self._worker.start()

    def _on_message_ready(self, text: str):
        self._append_chat_bubble(text, "claude")
        self._history.append({"role": "assistant", "content": text})
        self._set_busy(False, "")

    def _on_edits_ready(self, edits: list):
        """Chat CHIRURGICAL : applique les éditions ciblées à la version courante
        (aucune réécriture totale). Liste vide = simple question/réponse."""
        self._set_busy(False, "")
        if not edits:
            return   # pure Q&R : le message a déjà été affiché par _on_message_ready
        from core.text_edits import apply_find_replace_edits
        base = self._screenplay or self._original
        new_text, applied, missed = apply_find_replace_edits(base, edits)
        if not applied:
            self._append_chat_bubble(
                "⚠ Aucune modification appliquée : le passage visé n'a pas été "
                "retrouvé tel quel dans le scénario.", "claude")
            return
        self._on_screenplay_ready(new_text)   # nouvelle version + prévisualisation
        summary = "✎ " + " · ".join((a.get("summary") or "passage modifié") for a in applied)
        if missed:
            summary += f"  ({len(missed)} passage(s) non retrouvé(s))"
        self._append_chat_bubble(summary, "claude")

    def _on_generate_full(self):
        """Bouton « Générer le scénario » : réécriture COMPLÈTE volontaire, qui intègre
        toute la discussion. Coûteux en tokens → action délibérée, distincte du chat."""
        if not (self._screenplay or self._original).strip():
            return
        if self._worker and self._worker.isRunning():
            return
        self._append_chat_bubble("↻ Génération du scénario complet (intègre la discussion)…",
                                 "user")
        instruction = (
            "Produis maintenant la version COMPLÈTE du scénario en intégrant toutes les "
            "modifications qu'on a discutées jusqu'ici. Conserve la mise en page Pandora "
            "(séquences, en-têtes INT./EXT., noms de personnages en MAJUSCULES).")
        self._start_worker(instruction, surgical=False)

    def _on_screenplay_ready(self, text: str):
        # Tronquer l'historique forward si on est revenu en arrière
        if self._version_idx < len(self._screenplay_versions) - 1:
            self._screenplay_versions = self._screenplay_versions[:self._version_idx + 1]
        self._screenplay_versions.append(text)
        self._version_idx = len(self._screenplay_versions) - 1

        self._screenplay = text
        self._screenplay_edit.blockSignals(True)
        self._screenplay_edit.setPlainText(text)
        self._screenplay_edit.blockSignals(False)
        self._manual_edit_lbl.hide()
        self._update_version_nav()

        # Activer l'onglet scénario et basculer dessus
        self._tabs.setTabEnabled(1, True)
        self._tabs.setCurrentIndex(1)

        # Activer les boutons d'action
        self._btn_apply.setEnabled(True)
        self._btn_copy.setEnabled(True)

    def _nav_version_prev(self):
        if self._version_idx > 0:
            self._version_idx -= 1
            self._load_version(self._version_idx)

    def _nav_version_next(self):
        if self._version_idx < len(self._screenplay_versions) - 1:
            self._version_idx += 1
            self._load_version(self._version_idx)

    def _load_version(self, idx: int):
        text = self._screenplay_versions[idx]
        self._screenplay = text
        self._screenplay_edit.blockSignals(True)
        self._screenplay_edit.setPlainText(text)
        self._screenplay_edit.blockSignals(False)
        self._manual_edit_lbl.hide()
        self._update_version_nav()

    def _update_version_nav(self):
        n = len(self._screenplay_versions)
        if n == 0:
            self._ver_nav_bar.hide()
            return
        self._ver_nav_bar.show()
        self._ver_lbl.setText(f"v {self._version_idx + 1} / {n}")
        self._btn_prev_ver.setEnabled(self._version_idx > 0)
        self._btn_next_ver.setEnabled(self._version_idx < n - 1)

    def _on_failed(self, err: str):
        self._set_busy(False, "")
        error_msg = f"⚠  Erreur Claude : {err}"
        self._append_chat_bubble(error_msg, "claude")
        if self._history and self._history[-1]["role"] == "assistant":
            pass
        else:
            self._history.append({"role": "assistant", "content": error_msg})

    # ── Busy state ───────────────────────────────────────────────────────────

    def _set_busy(self, busy: bool, status: str = ""):
        self._btn_send.setEnabled(not busy)
        self._btn_apply.setEnabled(not busy and bool(self._screenplay))
        self._progress_bar.setVisible(busy)
        self._status_lbl.setText(status)
        if busy:
            # Placeholder animé dans le chat
            self._append_chat_bubble("…", "claude")

    # ── Actions boutons ───────────────────────────────────────────────────────

    def _on_apply(self):
        screenplay = self._screenplay_edit.toPlainText().strip()
        if screenplay:
            self._screenplay = screenplay
            self._applied = True
            self.accept()

    def _on_copy(self):
        text = self._screenplay_edit.toPlainText().strip()
        if text:
            QApplication.clipboard().setText(text)
            self._btn_copy.setText("✓  Copié !")
            QTimer.singleShot(1800, lambda: self._btn_copy.setText("⎘  Copier"))

    def _on_screenplay_edited(self):
        """Signale que l'utilisateur a modifié manuellement le scénario."""
        if self._screenplay_edit.toPlainText() != self._screenplay:
            self._manual_edit_lbl.show()
            self._btn_apply.setEnabled(True)

    # ── Données résultantes ───────────────────────────────────────────────────

    def final_screenplay(self) -> str:
        """Retourne le scénario final (version remaniée ou édition manuelle)."""
        return self._screenplay_edit.toPlainText().strip()

    def was_applied(self) -> bool:
        return self._applied

    # ── Keyboard shortcut Ctrl+Enter ─────────────────────────────────────────

    def eventFilter(self, obj, event):
        from PyQt6.QtCore import QEvent
        from PyQt6.QtGui import QKeyEvent
        if obj is self._input_edit and event.type() == QEvent.Type.KeyPress:
            if isinstance(event, QKeyEvent):
                if (event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter)
                        and event.modifiers() == Qt.KeyboardModifier.ControlModifier):
                    self._on_send()
                    return True
        return super().eventFilter(obj, event)
