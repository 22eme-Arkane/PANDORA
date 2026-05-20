"""
Onglet "Modifier depuis DaVinci Resolve" — AI Studio.

Workflow :
  1. Envoyer les clips depuis DaVinci via pandora_send (Espace de travail → Scripts)
  2. Écrire un prompt global ou par clip
  3. Injecter un template de style (optionnel)
  4. Lancer la file d'attente — uploade le clip entier en référence (ext/new_take)
"""

import json
import os
import tempfile

from PyQt6.QtCore import Qt, QFileSystemWatcher, pyqtSignal
from PyQt6.QtGui import QPixmap, QColor, QPainter, QLinearGradient
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QScrollArea, QTextEdit, QComboBox, QSpinBox, QButtonGroup,
    QRadioButton, QCheckBox, QFrame, QProgressBar, QMessageBox,
)

from ui.styles import C
from ui.widgets import HelpBlock, section_label, combo, toggle_row
from ui.creative_panel import SeedanceCreativePanel
from ui.icons import claude_icon_pixmap, install_hover_icon
from core.config import load_config, get_output_dir
from core.history import save_to_history
from core.worker import GenerationWorker
from api.enhance import EnhanceWorker, _SYSTEM_DAVINCI_EDIT
from davinci.importer import import_result
from davinci.ping_worker import BridgePingWorker
from ui.tab_t2v import (
    _DaVinciBar, _ENGINES, _DAVINCI_ENGINES, _SEEDANCE_ENGINES,
    _FIXED_RES_ENGINES, _FIXED_RATIO_ENGINES, _ENGINE_RES_FORCED,
    _TEXT_FALLBACK_ENGINES,
    _make_ext_worker, _norm_ext_result,
)


_INBOX = os.path.join(os.environ.get("TEMP", tempfile.gettempdir()), "pandora_clips_inbox.json")


# ── Placeholder coloré ────────────────────────────────────────────────────────

_THUMB_COLORS = [
    ("#1a1a4e", "#4ecdc4"), ("#1e0a2e", "#c77dff"),
    ("#0a2e1e", "#4ade80"), ("#2e1a0a", "#fb923c"),
    ("#2e0a1a", "#f472b6"), ("#0a1e2e", "#60a5fa"),
]


def _make_placeholder_pixmap(name: str, index: int, w: int = 100, h: int = 56) -> QPixmap:
    bg1, fg = _THUMB_COLORS[index % len(_THUMB_COLORS)]
    pix = QPixmap(w, h)
    pix.fill(QColor(bg1))
    painter = QPainter(pix)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    grad = QLinearGradient(0, 0, w, h)
    grad.setColorAt(0, QColor(bg1))
    grad.setColorAt(1, QColor(fg + "22"))
    painter.fillRect(0, 0, w, h, grad)
    initials = "".join(p[0].upper() for p in name.split()[:2]) or "?"
    painter.setPen(QColor(fg))
    font = painter.font()
    font.setPixelSize(18)
    font.setBold(True)
    painter.setFont(font)
    painter.drawText(0, 0, w, h, Qt.AlignmentFlag.AlignCenter, initials)
    painter.end()
    return pix


# ── Carte compacte d'un clip (style _ThumbCard de T2V) ───────────────────────

class ClipCard(QFrame):
    """Carte compacte — nom + checkbox include/exclude + badge index + statut génération."""
    focused       = pyqtSignal(int)
    check_changed = pyqtSignal(int, bool)  # index, checked

    _W    = 112
    _TH_W = 100
    _TH_H = 56

    def __init__(self, clip: dict, index: int, parent=None):
        super().__init__(parent)
        self._clip   = clip
        self._index  = index
        self._active = False

        self.setFixedSize(self._W, self._TH_H + 36)  # ~92px total
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(6, 4, 6, 4)
        lay.setSpacing(3)

        # Vignette 16:9
        self._thumb = QLabel()
        self._thumb.setFixedSize(self._TH_W, self._TH_H)
        self._thumb.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._thumb.setPixmap(
            _make_placeholder_pixmap(clip.get("name", "?"), index, self._TH_W, self._TH_H)
        )
        self._thumb.setStyleSheet("border-radius:4px;border:none;background:transparent;")
        lay.addWidget(self._thumb, 0, Qt.AlignmentFlag.AlignCenter)

        # Nom tronqué
        name    = clip.get("name", "—")
        display = name if len(name) <= 13 else name[:12] + "…"
        self._lbl = QLabel(display)
        self._lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lay.addWidget(self._lbl, 0, Qt.AlignmentFlag.AlignCenter)

        # Overlay : badge index (top-left)
        self._badge = QLabel(f"#{index + 1}", self)
        self._badge.setStyleSheet(
            "background:rgba(0,0,0,0.75);color:#fff;"
            "font-size:7px;font-weight:800;font-family:'Consolas',monospace;"
            "border-radius:3px;padding:1px 4px;border:none;"
        )
        self._badge.adjustSize()
        self._badge.move(5, 5)
        self._badge.raise_()

        # Overlay : checkbox include/exclude (top-right)
        self.check = QCheckBox(self)
        self.check.setChecked(True)
        self.check.setFixedSize(18, 18)
        self.check.move(self._W - 22, 4)
        self.check.stateChanged.connect(
            lambda state: self.check_changed.emit(self._index, bool(state))
        )
        self.check.setStyleSheet(
            f"QCheckBox::indicator{{width:16px;height:16px;border-radius:4px;"
            f"border:2px solid {C['accent']};background:{C['bg3']};}}"
            f"QCheckBox::indicator:checked{{background:{C['accent']};border-color:{C['accent']};}}"
        )
        self.check.raise_()

        # Overlay : statut génération (bottom)
        self._status_ov = QLabel("", self)
        self._status_ov.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._status_ov.setStyleSheet(
            "background:rgba(0,0,0,0.82);color:#fff;"
            "font-size:7px;font-weight:800;font-family:'Consolas',monospace;"
            "border-radius:3px;padding:1px 4px;border:none;"
        )
        self._status_ov.setVisible(False)

        self._apply_style()

    def _apply_style(self):
        if self._active:
            self.setStyleSheet(
                f"QFrame{{background:rgba(78,205,196,0.15);"
                f"border:2px solid {C['accent']};border-radius:8px;}}"
            )
            self._lbl.setStyleSheet(
                f"color:{C['accent']};font-size:9px;font-weight:700;background:transparent;"
            )
        else:
            self.setStyleSheet(
                f"QFrame{{background:{C['bg2']};border:1px solid {C['border']};"
                f"border-radius:8px;}}"
                f"QFrame:hover{{border-color:{C['border_bright']};}}"
            )
            self._lbl.setStyleSheet(
                f"color:{C['text_secondary']};font-size:9px;background:transparent;"
            )

    def set_active(self, v: bool):
        self._active = v
        self._apply_style()

    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            self.focused.emit(self._index)
        super().mousePressEvent(e)

    def set_status(self, text: str, color: str | None = None):
        if text:
            self._status_ov.setText(text)
            self._status_ov.setStyleSheet(
                f"background:rgba(0,0,0,0.82);color:{color or '#ffffff'};"
                "font-size:7px;font-weight:800;font-family:'Consolas',monospace;"
                "border-radius:3px;padding:1px 4px;border:none;"
            )
            self._status_ov.adjustSize()
            self._status_ov.move(5, self._TH_H - 14 + 4)
            self._status_ov.raise_()
            self._status_ov.setVisible(True)
        else:
            self._status_ov.setVisible(False)

    def clip(self) -> dict:
        return self._clip

    def is_checked(self) -> bool:
        return self.check.isChecked()

    def set_checked(self, v: bool):
        self.check.setChecked(v)


# ── Onglet principal ──────────────────────────────────────────────────────────

class TabDavinciEdit(QScrollArea):
    generation_done = pyqtSignal(dict)

    def __init__(self):
        super().__init__()
        self.setWidgetResizable(True)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        self._clip_cards:       list[ClipCard]            = []
        self._clips_data:       list[dict]               = []
        self._per_clip_prompts: dict[int, str]           = {}
        self._active_clip_idx:  int | None               = None
        self._worker:           GenerationWorker | None  = None
        self._ping_worker:      BridgePingWorker | None  = None
        self._lipsync_worker                             = None
        self._enhance_worker_global:   EnhanceWorker | None = None
        self._enhance_worker_per_clip: EnhanceWorker | None = None
        self._bridge_connected  = False
        self._style_suffix      = ""
        self._style_key         = ""
        self._style_ref_path    = ""
        self._queue:            list[tuple[int, int]]    = []
        self._queue_pos         = 0
        self._last_seed:        int | None               = None

        container = QWidget()
        self.setWidget(container)
        self._lay = QVBoxLayout(container)
        self._lay.setContentsMargins(20, 20, 20, 20)
        self._lay.setSpacing(16)

        self._build_ui()

        self._watcher = QFileSystemWatcher()
        if os.path.isfile(_INBOX):
            self._watcher.addPath(_INBOX)
        self._watcher.fileChanged.connect(self._on_inbox_changed)

    # ── Sections collapsibles ─────────────────────────────────────────────────

    def _make_section(self, title: str) -> tuple[QWidget, QVBoxLayout]:
        wrapper = QWidget()
        wl = QVBoxLayout(wrapper)
        wl.setContentsMargins(0, 0, 0, 0)
        wl.setSpacing(0)

        header = QPushButton(f"▼  {title}")
        header.setFlat(True)
        header.setFixedHeight(32)
        header.setCursor(Qt.CursorShape.PointingHandCursor)
        header.setStyleSheet(
            f"QPushButton{{color:{C['text_secondary']};font-size:11px;font-weight:700;"
            f"background:{C['bg1']};border:none;border-top:1px solid {C['border']};"
            f"text-align:left;padding:0 4px;}}"
            f"QPushButton:hover{{color:{C['text_primary']};}}"
        )
        wl.addWidget(header)

        body = QWidget()
        body_lay = QVBoxLayout(body)
        body_lay.setContentsMargins(0, 8, 0, 12)
        body_lay.setSpacing(8)
        wl.addWidget(body)

        def _toggle(_, h=header, b=body, t=title):
            visible = not b.isVisible()
            b.setVisible(visible)
            h.setText(f"{'▼' if visible else '▶'}  {t}")

        header.clicked.connect(_toggle)
        return wrapper, body_lay

    # ── Construction UI ───────────────────────────────────────────────────────

    def _build_ui(self):
        lay = self._lay
        _rb_ss = (
            f"QRadioButton{{color:{C['text_primary']};font-size:11px;spacing:8px;}}"
            f"QRadioButton::indicator{{width:14px;height:14px;border-radius:7px;"
            f"border:2px solid {C['accent']};background:transparent;}}"
            f"QRadioButton::indicator:checked{{background:{C['accent']};"
            f"border:2px solid {C['accent']};}}"
            f"QRadioButton::indicator:unchecked:hover{{border-color:{C['text_primary']};}}"
        )

        # ── Bloc d'aide ──────────────────────────────────────────────────────
        lay.addWidget(HelpBlock("Modifier depuis DaVinci Resolve — Génération batch", [
            "▸ Sélectionner des clips spécifiques : clic droit sur chaque clip → Flag → n'importe quelle couleur.",
            "  pandora_send n'envoie que les clips flaggés (toutes couleurs). Sans flag = toute la timeline.",
            "▸ Envoyez vos clips : Espace de travail → Scripts → pandora_send",
            "  (ou votre raccourci clavier — Personnalisation du clavier → pandora_send).",
            "▸ Écrivez un prompt global ou un prompt différent par clip.",
            "▸ Cliquez sur « Lancer la file d'attente » : chaque clip est uploadé comme référence",
            "  vidéo (@Video1) et Seedance génère une nouvelle version selon votre prompt,",
            "  séquentiellement (1 clip à la fois), N prises par clip.",
            "▸ Les vidéos générées sont automatiquement importées dans le Media Pool de DaVinci.",
            "",
            "⚠  Format requis par Seedance 2.0 pour l'upload de référence vidéo :",
            "  • Résolution : 720p maximum",
            "  • Taille : moins de 50 MB",
            "  • Format : H.264 MP4 ou MOV recommandé",
            "  → Depuis DaVinci : Fichier → Exporter → sélectionner H.264 Master à 720p",
            "    avant d'envoyer les clips via pandora_send.",
        ], C))

        # ── Statut bridge ────────────────────────────────────────────────────
        status_row = QHBoxLayout()
        self._lbl_status = QLabel("○  Bridge non connecté")
        self._lbl_status.setStyleSheet(
            f"color:{C['text_dim']};font-size:10px;font-family:'Consolas',monospace;"
        )
        btn_refresh = QPushButton("↻  Actualiser")
        btn_refresh.setFixedHeight(24)
        btn_refresh.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_refresh.setStyleSheet(
            f"QPushButton{{background:transparent;color:{C['text_dim']};"
            f"border:1px solid {C['border']};border-radius:5px;"
            f"font-size:10px;padding:0 10px;}}"
            f"QPushButton:hover{{color:{C['text_primary']};border-color:{C['border_bright']};}}"
        )
        btn_refresh.clicked.connect(self._ping_bridge)
        status_row.addWidget(self._lbl_status)
        status_row.addSpacing(8)
        status_row.addWidget(btn_refresh)
        status_row.addStretch()
        lay.addLayout(status_row)

        self._lbl_bridge_help = QLabel(
            "Pour connecter le bridge : dans DaVinci Resolve Studio →\n"
            "Espace de travail → Scripts → seedance_bridge\n"
            "Laissez la fenêtre PANDORA Bridge ouverte pendant votre session."
        )
        self._lbl_bridge_help.setStyleSheet(
            f"color:{C['red']};font-size:10px;font-family:'Consolas',monospace;"
            f"background:rgba(255,79,106,0.08);border:1px solid rgba(255,79,106,0.25);"
            f"border-radius:6px;padding:8px 12px;"
        )
        lay.addWidget(self._lbl_bridge_help)

        # ── Style de film (identique à T2V) ──────────────────────────────────
        import core.style as _style_mod
        from PyQt6.QtGui import QColor as _QColor

        self._film_style_frame = QFrame()
        self._film_style_frame.setStyleSheet(
            f"QFrame{{background:rgba(124,107,255,0.08);"
            f"border:1px solid {C['accent_dim']};border-radius:8px;}}"
        )
        _fs_outer = QHBoxLayout(self._film_style_frame)
        _fs_outer.setContentsMargins(14, 12, 14, 12)
        _fs_outer.setSpacing(12)

        _fs_left = QVBoxLayout()
        _fs_left.setContentsMargins(0, 0, 0, 0)
        _fs_left.setSpacing(6)

        _fs_lbl = QLabel("Style de film")
        _fs_lbl.setStyleSheet(
            f"color:{C['accent']};font-size:11px;font-weight:700;background:transparent;border:none;"
        )
        _fs_left.addWidget(_fs_lbl)

        self._film_style_combo = QComboBox()
        self._film_style_combo.addItem("— Non défini —", "")
        _cur_grp = None
        for _s in _style_mod.STYLES:
            _g = _s.get("group", "")
            if _g != _cur_grp:
                _cur_grp = _g
                _gi = next((g for g in _style_mod.GROUPS if g["key"] == _g), None)
                if _gi:
                    self._film_style_combo.addItem(
                        f"  {_gi['icon']}  {_gi['name'].upper()}", "__sep__"
                    )
                    _sep = self._film_style_combo.model().item(self._film_style_combo.count() - 1)
                    _sep.setEnabled(False)
                    _sep.setForeground(_QColor(C.get("accent", "#7c6bff")))
            self._film_style_combo.addItem(f"    {_s['icon']}  {_s['name']}", _s["key"])
        self._film_style_combo.setFixedHeight(30)
        self._film_style_combo.setStyleSheet(
            f"QComboBox{{background:rgba(124,107,255,0.12);border:1px solid {C['accent_dim']};"
            f"border-radius:5px;color:{C['accent']};font-size:11px;font-weight:700;padding:0 8px;}}"
            f"QComboBox:focus{{border-color:{C['accent']};}}"
            f"QComboBox::drop-down{{border:none;width:18px;}}"
            f"QComboBox QAbstractItemView{{background:{C['bg2']};border:1px solid {C['border_bright']};"
            f"color:{C['text_primary']};selection-background-color:{C['accent_dim']};"
            f"font-size:11px;padding:4px;}}"
        )
        self._film_style_combo.currentIndexChanged.connect(self._on_film_style_changed)
        _fs_left.addWidget(self._film_style_combo)

        self._style_ref_override_lbl = QLabel("selon image de référence")
        self._style_ref_override_lbl.setFixedHeight(30)
        self._style_ref_override_lbl.setAlignment(
            Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft
        )
        self._style_ref_override_lbl.setStyleSheet(
            f"color:{C['accent']};font-size:10px;font-weight:700;font-style:italic;"
            f"background:rgba(78,205,196,0.09);border:1px solid rgba(78,205,196,0.32);"
            f"border-radius:5px;padding:0 8px;"
        )
        self._style_ref_override_lbl.setVisible(False)
        _fs_left.addWidget(self._style_ref_override_lbl)

        self._btn_style_gallery = QPushButton("\U0001f5bc  Template de style")
        self._btn_style_gallery.setFixedHeight(28)
        self._btn_style_gallery.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_style_gallery.setStyleSheet(
            f"QPushButton{{background:rgba(124,107,255,0.10);color:{C['accent']};"
            f"border:1px solid {C['accent_dim']};border-radius:5px;"
            f"font-size:10px;font-weight:700;padding:0 12px;}}"
            f"QPushButton:hover{{background:rgba(124,107,255,0.20);border-color:{C['accent']};}}"
            f"QPushButton:pressed{{background:rgba(124,107,255,0.28);}}"
        )
        self._btn_style_gallery.clicked.connect(self._on_style_gallery)
        _style_btn_row = QHBoxLayout()
        _style_btn_row.setContentsMargins(0, 0, 268, 0)
        _style_btn_row.addStretch()
        _style_btn_row.addWidget(self._btn_style_gallery)
        _style_btn_row.addStretch()
        _fs_left.addLayout(_style_btn_row)
        _fs_outer.addLayout(_fs_left, 1)

        self._style_ref_preview_frame = QFrame()
        self._style_ref_preview_frame.setVisible(False)
        self._style_ref_preview_frame.setFixedWidth(170)
        self._style_ref_preview_frame.setStyleSheet(
            f"QFrame{{background:{C['bg2']};border:1px solid {C['border_bright']};border-radius:8px;}}"
        )
        _pf_lay = QVBoxLayout(self._style_ref_preview_frame)
        _pf_lay.setContentsMargins(8, 8, 8, 8)
        _pf_lay.setSpacing(6)
        self._style_ref_thumb = QLabel()
        self._style_ref_thumb.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._style_ref_thumb.setMinimumHeight(90)
        self._style_ref_thumb.setStyleSheet(
            f"background:{C['bg3']};border-radius:6px;border:none;"
        )
        _pf_lay.addWidget(self._style_ref_thumb, 1)
        self._style_ref_clear_btn = QPushButton("× Retirer")
        self._style_ref_clear_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._style_ref_clear_btn.setFixedHeight(24)
        self._style_ref_clear_btn.setStyleSheet(
            f"QPushButton{{background:transparent;color:{C['text_dim']};"
            f"border:1px solid {C['border']};border-radius:4px;font-size:10px;padding:0 8px;}}"
            f"QPushButton:hover{{color:{C['red']};border-color:{C['red']};}}"
        )
        self._style_ref_clear_btn.clicked.connect(self._on_style_ref_clear)
        _pf_lay.addWidget(self._style_ref_clear_btn)
        _fs_outer.addWidget(self._style_ref_preview_frame)
        lay.addWidget(self._film_style_frame)

        # ── Bouton ADN visuel ─────────────────────────────────────────────────
        self._seed_lock_btn = QPushButton("🔓  ADN visuel — aléatoire")
        self._seed_lock_btn.setCheckable(True)
        self._seed_lock_btn.setFixedHeight(26)
        self._seed_lock_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._seed_lock_btn.setStyleSheet(
            f"QPushButton{{background:transparent;border:1px solid {C['border']};"
            f"border-radius:6px;font-size:10px;font-weight:600;color:{C['text_dim']};"
            f"padding:0 10px;}}"
            f"QPushButton:checked{{background:rgba(124,107,255,0.12);"
            f"border-color:{C['accent']};color:{C['accent']};}}"
            f"QPushButton:hover{{background:{C['bg3']};}}"
        )
        self._seed_lock_btn.toggled.connect(self._on_seed_toggle)
        _adn_row = QHBoxLayout()
        _adn_row.setContentsMargins(0, 0, 268, 0)
        _adn_row.addStretch()
        _adn_row.addWidget(self._seed_lock_btn)
        _adn_row.addStretch()
        lay.addLayout(_adn_row)

        # ── Section : Clips importés ──────────────────────────────────────────
        sec_clips, body_clips = self._make_section("Clips importés")

        sel_row = QHBoxLayout()
        _btn_ss = (
            f"QPushButton{{background:{C['bg3']};color:{C['text_secondary']};"
            f"border:1px solid {C['border']};border-radius:5px;font-size:10px;padding:0 10px;}}"
            f"QPushButton:hover{{background:{C['bg2']};}}"
        )
        for lbl_txt, state in (("Tout sélectionner", True), ("Tout désélectionner", False)):
            b = QPushButton(lbl_txt)
            b.setFixedHeight(26)
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.setStyleSheet(_btn_ss)
            b.clicked.connect(lambda _, s=state: self._set_all_checked(s))
            sel_row.addWidget(b)
        btn_clear = QPushButton("✕  Vider la liste")
        btn_clear.setFixedHeight(26)
        btn_clear.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_clear.setStyleSheet(
            f"QPushButton{{background:transparent;color:{C['text_dim']};"
            f"border:1px solid {C['border']};border-radius:5px;font-size:10px;padding:0 10px;}}"
            f"QPushButton:hover{{color:{C['red']};border-color:{C['red']};}}"
        )
        btn_clear.clicked.connect(self._clear_clips)
        sel_row.addWidget(btn_clear)
        sel_row.addStretch()
        body_clips.addLayout(sel_row)

        # Scroll horizontal pour les cartes
        self._clips_inner = QWidget()
        self._clips_inner.setStyleSheet("background:transparent;")
        self._clips_hbox = QHBoxLayout(self._clips_inner)
        self._clips_hbox.setContentsMargins(0, 0, 8, 0)
        self._clips_hbox.setSpacing(8)
        self._clips_hbox.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)

        self._clips_scroll = QScrollArea()
        self._clips_scroll.setWidget(self._clips_inner)
        self._clips_scroll.setWidgetResizable(True)
        self._clips_scroll.setFixedHeight(ClipCard._TH_H + 52)
        self._clips_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._clips_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self._clips_scroll.setStyleSheet("QScrollArea{background:transparent;border:none;}")
        self._clips_scroll.setVisible(False)
        body_clips.addWidget(self._clips_scroll)

        self._lbl_empty = QLabel(
            "Aucun clip — lancez pandora_send dans DaVinci (Espace de travail → Scripts)"
        )
        self._lbl_empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._lbl_empty.setStyleSheet(f"color:{C['text_dim']};font-size:11px;padding:20px;")
        body_clips.addWidget(self._lbl_empty)
        lay.addWidget(sec_clips)

        # ── Section : Prompt de modification ──────────────────────────────────
        sec_prompt, body_prompt = self._make_section("Prompt de modification")

        mode_row = QHBoxLayout()
        mode_row.setSpacing(24)
        self._rb_global   = QRadioButton("Prompt global")
        self._rb_per_clip = QRadioButton("Prompt par clip")
        self._rb_global.setChecked(True)
        self._rb_group = QButtonGroup(self)
        self._rb_group.addButton(self._rb_global,   0)
        self._rb_group.addButton(self._rb_per_clip, 1)
        for rb in (self._rb_global, self._rb_per_clip):
            rb.setStyleSheet(_rb_ss)
        self._rb_global.toggled.connect(self._on_prompt_mode_changed)
        mode_row.addWidget(self._rb_global)
        mode_row.addWidget(self._rb_per_clip)
        mode_row.addStretch()
        body_prompt.addLayout(mode_row)

        # Prompt global — frame avec bouton Claude
        _pg_frame = QFrame()
        _pg_frame.setStyleSheet(
            f"QFrame{{background:{C['bg2']};border:1px solid {C['border']};border-radius:10px;}}"
        )
        _pg_lay = QVBoxLayout(_pg_frame)
        _pg_lay.setContentsMargins(14, 8, 14, 10)
        _pg_lay.setSpacing(4)

        _pg_header = QHBoxLayout()
        _pg_header.setContentsMargins(0, 0, 0, 0)
        _pg_header.setSpacing(6)
        self._pg_counter = QLabel("0")
        self._pg_counter.setStyleSheet(
            f"color:{C['text_dim']};font-size:10px;font-family:'Consolas',monospace;"
            f"border:none;background:transparent;"
        )
        self._btn_enhance_global = QPushButton()
        self._btn_enhance_global.setFixedSize(26, 26)
        self._btn_enhance_global.setToolTip(
            "Optimiser avec Claude\nAméliore le prompt de modification pour Seedance 2.0."
        )
        self._btn_enhance_global.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_enhance_global.setStyleSheet(
            "QPushButton{background:transparent;border:none;border-radius:5px;padding:0;}"
            "QPushButton:hover{background:rgba(124,107,255,0.12);}"
            "QPushButton:pressed{background:rgba(124,107,255,0.20);}"
            "QPushButton:disabled{opacity:0.3;}"
        )
        _pn = claude_icon_pixmap(15, C["text_dim"])
        _ph = claude_icon_pixmap(15, C["accent"])
        if not _pn.isNull():
            install_hover_icon(self._btn_enhance_global, _pn, _ph, icon_size=15)
        else:
            self._btn_enhance_global.setText("☁")
        self._btn_enhance_global.clicked.connect(self._on_enhance_global)
        _pg_header.addWidget(self._pg_counter)
        _pg_header.addStretch()
        _pg_header.addWidget(self._btn_enhance_global)
        _pg_lay.addLayout(_pg_header)

        _pg_sep = QFrame()
        _pg_sep.setFrameShape(QFrame.Shape.HLine)
        _pg_sep.setStyleSheet(f"background:{C['border']};max-height:1px;border:none;")
        _pg_lay.addWidget(_pg_sep)

        self._prompt_global = QTextEdit()
        self._prompt_global.setPlaceholderText(
            "Décris la modification souhaitée…\n"
            "ex: same scene but background replaced by a futuristic city at night, cinematic lighting"
        )
        self._prompt_global.setMinimumHeight(70)
        self._prompt_global.setStyleSheet(
            "QTextEdit{background:transparent;border:none;border-radius:0;"
            f"color:{C['text_primary']};font-size:12px;font-family:'Segoe UI',sans-serif;padding:0;}}"
        )
        self._prompt_global.textChanged.connect(
            lambda: self._pg_counter.setText(str(len(self._prompt_global.toPlainText())))
        )
        _pg_lay.addWidget(self._prompt_global)
        body_prompt.addWidget(_pg_frame)

        # Panneau per-clip (masqué par défaut)
        self._per_clip_panel = QFrame()
        self._per_clip_panel.setVisible(False)
        self._per_clip_panel.setStyleSheet(
            f"QFrame{{background:{C['bg2']};border:1px solid {C['border']};border-radius:10px;}}"
        )
        _pp_outer = QVBoxLayout(self._per_clip_panel)
        _pp_outer.setContentsMargins(12, 10, 12, 12)
        _pp_outer.setSpacing(8)

        # Scroll de cartes miroir (identique à "Clips importés")
        self._pc_inner = QWidget()
        self._pc_inner.setStyleSheet("background:transparent;")
        self._pc_hbox = QHBoxLayout(self._pc_inner)
        self._pc_hbox.setContentsMargins(0, 0, 8, 0)
        self._pc_hbox.setSpacing(8)
        self._pc_hbox.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)

        self._pc_scroll = QScrollArea()
        self._pc_scroll.setWidget(self._pc_inner)
        self._pc_scroll.setWidgetResizable(True)
        self._pc_scroll.setFixedHeight(ClipCard._TH_H + 52)
        self._pc_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._pc_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self._pc_scroll.setStyleSheet("QScrollArea{background:transparent;border:none;}")
        _pp_outer.addWidget(self._pc_scroll)

        # Label clip sélectionné
        self._per_clip_title = QLabel("← Sélectionne un clip pour écrire son prompt")
        self._per_clip_title.setStyleSheet(
            f"color:{C['text_dim']};font-size:10px;font-style:italic;background:transparent;"
            f"border:none;"
        )
        _pp_outer.addWidget(self._per_clip_title)

        # Textarea prompt per-clip — frame avec bouton Claude
        _pc_frame = QFrame()
        _pc_frame.setStyleSheet(
            f"QFrame{{background:{C['bg3']};border:1px solid {C['border']};border-radius:8px;}}"
        )
        _pc_lay = QVBoxLayout(_pc_frame)
        _pc_lay.setContentsMargins(10, 6, 10, 8)
        _pc_lay.setSpacing(4)

        _pc_header = QHBoxLayout()
        _pc_header.setContentsMargins(0, 0, 0, 0)
        _pc_header.setSpacing(6)
        self._pc_counter = QLabel("0")
        self._pc_counter.setStyleSheet(
            f"color:{C['text_dim']};font-size:10px;font-family:'Consolas',monospace;"
            f"border:none;background:transparent;"
        )
        self._btn_enhance_per_clip = QPushButton()
        self._btn_enhance_per_clip.setFixedSize(26, 26)
        self._btn_enhance_per_clip.setToolTip(
            "Optimiser avec Claude\nAméliore le prompt de modification pour Seedance 2.0."
        )
        self._btn_enhance_per_clip.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_enhance_per_clip.setStyleSheet(
            "QPushButton{background:transparent;border:none;border-radius:5px;padding:0;}"
            "QPushButton:hover{background:rgba(124,107,255,0.12);}"
            "QPushButton:pressed{background:rgba(124,107,255,0.20);}"
            "QPushButton:disabled{opacity:0.3;}"
        )
        _pcn = claude_icon_pixmap(15, C["text_dim"])
        _pch = claude_icon_pixmap(15, C["accent"])
        if not _pcn.isNull():
            install_hover_icon(self._btn_enhance_per_clip, _pcn, _pch, icon_size=15)
        else:
            self._btn_enhance_per_clip.setText("☁")
        self._btn_enhance_per_clip.clicked.connect(self._on_enhance_per_clip)
        _pc_header.addWidget(self._pc_counter)
        _pc_header.addStretch()
        _pc_header.addWidget(self._btn_enhance_per_clip)
        _pc_lay.addLayout(_pc_header)

        _pc_sep = QFrame()
        _pc_sep.setFrameShape(QFrame.Shape.HLine)
        _pc_sep.setStyleSheet(f"background:{C['border']};max-height:1px;border:none;")
        _pc_lay.addWidget(_pc_sep)

        self._per_clip_prompt = QTextEdit()
        self._per_clip_prompt.setPlaceholderText(
            "Prompt spécifique à ce clip…\n"
            "ex: same scene but background replaced by a futuristic city at night"
        )
        self._per_clip_prompt.setMinimumHeight(60)
        self._per_clip_prompt.setStyleSheet(
            "QTextEdit{background:transparent;border:none;border-radius:0;"
            f"color:{C['text_primary']};font-size:12px;font-family:'Segoe UI',sans-serif;padding:0;}}"
        )
        self._per_clip_prompt.textChanged.connect(self._on_per_clip_prompt_changed)
        self._per_clip_prompt.textChanged.connect(
            lambda: self._pc_counter.setText(str(len(self._per_clip_prompt.toPlainText())))
        )
        _pc_lay.addWidget(self._per_clip_prompt)
        _pp_outer.addWidget(_pc_frame)

        body_prompt.addWidget(self._per_clip_panel)

        lay.addWidget(sec_prompt)

        # ── Resynchroniser les lèvres (LatentSync) ────────────────────────────
        from api.lipsync import ffmpeg_available as _ffmpeg_ok
        self._lipsync_toggle_row = toggle_row(
            "Resynchroniser les lèvres",
            "Synchronisation labiale LatentSync — aligne les lèvres sur l'audio source du clip",
            False,
        )
        self._cb_lipsync = self._lipsync_toggle_row.findChild(QCheckBox)
        if not _ffmpeg_ok():
            self._cb_lipsync.setEnabled(False)
            self._lipsync_toggle_row.setToolTip(
                "ffmpeg non détecté — installez ffmpeg et ajoutez-le au PATH pour activer LatentSync."
            )
        else:
            self._lipsync_toggle_row.setToolTip(
                "Après génération Seedance, resynchronise les lèvres de l'acteur\n"
                "avec l'audio source du clip DaVinci (fal-ai/latentsync).\n"
                "Importe la vidéo lip-synced + la piste audio séparément dans DaVinci."
            )
        lay.addWidget(self._lipsync_toggle_row)

        # ── Contrôles créatifs ────────────────────────────────────────────────
        self._creative = SeedanceCreativePanel()
        lay.addWidget(self._creative)

        # ── Section : Paramètres ──────────────────────────────────────────────
        sec_params, body_params = self._make_section("Paramètres")

        from PyQt6.QtWidgets import QGridLayout as _QGrid
        params_grid = _QGrid()
        params_grid.setSpacing(12)

        self._cb_model = combo(_DAVINCI_ENGINES)
        self._cb_model.currentIndexChanged.connect(self._on_engine_changed)
        self._cb_ratio = combo(["16:9 — Paysage", "9:16 — Portrait", "4:3", "3:4"])
        self._cb_res   = combo(["1080p", "720p", "480p"])

        for (row, col), lbl, widget in [
            ((0, 0), "Moteur de génération", self._cb_model),
            ((0, 1), "Ratio",                self._cb_ratio),
            ((1, 0), "Résolution",           self._cb_res),
        ]:
            g = QWidget()
            l = QVBoxLayout(g)
            l.setContentsMargins(0, 0, 0, 0)
            l.setSpacing(6)
            l.addWidget(section_label(lbl))
            l.addWidget(widget)
            params_grid.addWidget(g, row, col)

        body_params.addLayout(params_grid)

        # ── Banner compatibilité références (moteurs texte-seul) ─────────────
        self._ref_compat_banner = QLabel(
            "⚠  Ce moteur ne supporte pas les images de référence nativement. "
            "Vos personnages, décors et accessoires seront convertis en mots-clés de style "
            "via Claude Vision et ajoutés au prompt texte."
        )
        self._ref_compat_banner.setWordWrap(True)
        self._ref_compat_banner.setStyleSheet(
            "background:rgba(255,79,106,0.12);"
            f"color:{C['red']};"
            "border:1px solid rgba(255,79,106,0.45);"
            "border-radius:6px;padding:8px 12px;font-size:11px;font-weight:600;"
        )
        self._ref_compat_banner.setVisible(False)
        body_params.addWidget(self._ref_compat_banner)

        lay.addWidget(sec_params)

        # ── Section : File d'attente ──────────────────────────────────────────
        sec_queue, body_queue = self._make_section("File d'attente")

        self._lbl_queue_info = QLabel("Aucune génération en cours.")
        self._lbl_queue_info.setStyleSheet(f"color:{C['text_dim']};font-size:11px;")
        body_queue.addWidget(self._lbl_queue_info)

        self._progress = QProgressBar()
        self._progress.setFixedHeight(6)
        self._progress.setTextVisible(False)
        self._progress.setRange(0, 100)
        self._progress.setValue(0)
        self._progress.setStyleSheet(
            f"QProgressBar{{background:{C['bg3']};border-radius:3px;border:none;}}"
            f"QProgressBar::chunk{{background:{C['accent']};border-radius:3px;}}"
        )
        self._progress.setVisible(False)
        body_queue.addWidget(self._progress)

        self._lbl_progress = QLabel("")
        self._lbl_progress.setStyleSheet(
            f"color:{C['text_dim']};font-size:10px;font-family:'Consolas',monospace;"
        )
        body_queue.addWidget(self._lbl_progress)

        self._cb_import = QCheckBox("Import auto dans DaVinci Media Pool après génération")
        self._cb_import.setChecked(False)
        self._cb_import.setEnabled(False)
        self._cb_import.setToolTip(
            "DaVinci Resolve Studio requis — connectez le bridge pour activer cette option"
        )
        self._cb_import.setStyleSheet(f"color:{C['text_secondary']};font-size:11px;")
        body_queue.addWidget(self._cb_import)

        # Stage label (visible uniquement pendant la file LatentSync)
        self._lbl_lipsync_stage = QLabel("")
        self._lbl_lipsync_stage.setVisible(False)
        self._lbl_lipsync_stage.setStyleSheet(
            f"color:{C['accent']};font-size:10px;font-family:'Consolas',monospace;"
            f"background:rgba(78,205,196,0.08);border:1px solid {C['accent']}33;"
            f"border-radius:4px;padding:4px 10px;"
        )
        body_queue.addWidget(self._lbl_lipsync_stage)

        self._btn_generate = QPushButton("▶▶  Lancer la file d'attente")
        self._btn_generate.setMinimumHeight(46)
        self._btn_generate.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_generate.setStyleSheet(f"""
            QPushButton{{
                background:{C['accent']};color:#07080f;border:none;
                border-radius:8px;font-size:13px;font-weight:700;
                letter-spacing:1px;padding:0 24px;
            }}
            QPushButton:hover{{background:#6eded6;}}
            QPushButton:pressed{{background:{C['accent_dim']};color:#ffffff;}}
            QPushButton:disabled{{background:{C['bg3']};color:{C['text_dim']};}}
        """)
        self._btn_generate.clicked.connect(self._check_bridge_then_start)

        self._btn_cancel = QPushButton("Annuler")
        self._btn_cancel.setVisible(False)
        self._btn_cancel.setFixedWidth(100)
        self._btn_cancel.setStyleSheet(f"""
            QPushButton{{background:{C['bg3']};color:{C['text_secondary']};
            border:1px solid {C['border']};border-radius:8px;font-size:12px;
            font-weight:700;padding:13px;}}
            QPushButton:hover{{background:{C['border']};color:{C['text_primary']};}}
        """)
        self._btn_cancel.clicked.connect(self._cancel_queue)

        _x = QLabel("×")
        _x.setFixedWidth(14)
        _x.setStyleSheet(f"color:{C['text_dim']};font-size:13px;background:transparent;border:none;")
        self._spin_prises = QSpinBox()
        self._spin_prises.setRange(1, 10)
        self._spin_prises.setValue(1)
        self._spin_prises.setFixedSize(54, 46)
        self._spin_prises.setToolTip("Nombre de prises par clip (1–10)")
        self._spin_prises.setStyleSheet(
            f"QSpinBox{{background:{C['bg3']};border:1px solid {C['border']};"
            f"border-radius:8px;color:{C['text_primary']};font-size:13px;font-weight:700;"
            f"padding:0 4px;}}"
            f"QSpinBox::up-button,QSpinBox::down-button{{width:16px;border:none;"
            f"background:{C['bg3']};border-radius:3px;}}"
        )

        btn_row = QHBoxLayout()
        btn_row.setContentsMargins(0, 0, 0, 0)
        btn_row.setSpacing(8)
        btn_row.addWidget(self._btn_generate)
        btn_row.addWidget(_x)
        btn_row.addWidget(self._spin_prises)
        btn_row.addWidget(self._btn_cancel)
        body_queue.addLayout(btn_row)

        self._davinci_bar = _DaVinciBar()
        body_queue.addWidget(self._davinci_bar)

        self._btn_open_folder = QPushButton("📁  Ouvrir le dossier des vidéos")
        self._btn_open_folder.setVisible(False)
        self._btn_open_folder.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_open_folder.setStyleSheet(f"""
            QPushButton{{background:transparent;color:{C['text_secondary']};
            border:1px solid {C['border']};border-radius:8px;font-size:11px;
            padding:6px 14px;}}
            QPushButton:hover{{background:{C['bg3']};color:{C['text_primary']};}}
        """)
        self._btn_open_folder.clicked.connect(self._open_output_folder)

        _folder_row = QHBoxLayout()
        _folder_row.setContentsMargins(0, 0, 268, 0)
        _folder_row.addStretch()
        _folder_row.addWidget(self._btn_open_folder)
        _folder_row.addStretch()
        body_queue.addLayout(_folder_row)
        lay.addWidget(sec_queue)
        lay.addStretch()

    # ── Ping bridge ───────────────────────────────────────────────────────────

    def _ping_bridge(self):
        if self._ping_worker and self._ping_worker.isRunning():
            return
        self._ping_worker = BridgePingWorker()
        self._ping_worker.result.connect(self._on_ping_result)
        self._ping_worker.start()
        if os.path.isfile(_INBOX) and _INBOX not in self._watcher.files():
            self._watcher.addPath(_INBOX)

    def _on_ping_result(self, connected: bool, timeline_name: str):
        self._bridge_connected = connected
        if connected:
            tl_part = f" — Timeline : {timeline_name}" if timeline_name else ""
            self._lbl_status.setText(f"● Bridge connecté{tl_part}")
            self._lbl_status.setStyleSheet(
                f"color:{C['green']};font-size:10px;font-family:'Consolas',monospace;"
            )
            self._lbl_bridge_help.setVisible(False)
        else:
            self._lbl_status.setText("○  Bridge non connecté")
            self._lbl_status.setStyleSheet(
                f"color:{C['text_dim']};font-size:10px;font-family:'Consolas',monospace;"
            )
            self._lbl_bridge_help.setVisible(True)
        self._cb_import.setEnabled(connected)
        if not connected:
            self._cb_import.setChecked(False)
            self._cb_import.setToolTip(
                "DaVinci Resolve Studio requis — connectez le bridge pour activer cette option"
            )
        else:
            self._cb_import.setToolTip("")

    # ── Inbox (écrit par pandora_send.py dans DaVinci) ───────────────────────

    def _on_inbox_changed(self, path: str):
        from PyQt6.QtCore import QTimer
        QTimer.singleShot(200, self._read_inbox)

    def _read_inbox(self):
        if not os.path.isfile(_INBOX):
            return
        try:
            with open(_INBOX, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            return
        clips   = data.get("clips", [])
        tl_name = data.get("timeline", "")
        if not clips:
            return
        if _INBOX not in self._watcher.files():
            self._watcher.addPath(_INBOX)
        self._lbl_status.setText(
            f"● Script DaVinci — Timeline : {tl_name} — {len(clips)} clip(s) reçu(s)"
        )
        self._lbl_status.setStyleSheet(
            f"color:{C['green']};font-size:10px;font-family:'Consolas',monospace;"
        )
        self._lbl_bridge_help.setVisible(False)
        self._load_clips(clips)

    # ── Chargement des clips ──────────────────────────────────────────────────

    def _load_clips(self, clips: list):
        for hbox in (self._clips_hbox, self._pc_hbox):
            while hbox.count():
                it = hbox.takeAt(0)
                if it.widget():
                    it.widget().deleteLater()

        self._clip_cards.clear()
        self._clips_data       = clips
        self._per_clip_prompts.clear()
        self._active_clip_idx  = None

        self._per_clip_title.setText("← Sélectionne un clip pour écrire son prompt")
        self._per_clip_prompt.blockSignals(True)
        self._per_clip_prompt.clear()
        self._per_clip_prompt.blockSignals(False)

        if not clips:
            self._lbl_empty.setVisible(True)
            self._clips_scroll.setVisible(False)
            return

        self._lbl_empty.setVisible(False)
        self._clips_scroll.setVisible(True)

        for i, clip in enumerate(clips):
            card = ClipCard(clip, i)
            card.focused.connect(self._on_card_focused)
            card.check_changed.connect(self._on_card_check_changed)
            if i > 0:
                sep = QFrame()
                sep.setFixedSize(1, ClipCard._TH_H)
                sep.setStyleSheet(f"background:{C['border']};")
                self._clips_hbox.addWidget(sep, 0, Qt.AlignmentFlag.AlignVCenter)
            self._clips_hbox.addWidget(card)
            self._clip_cards.append(card)

            card2 = ClipCard(clip, i)
            card2.focused.connect(self._on_card_focused)
            if i > 0:
                sep2 = QFrame()
                sep2.setFixedSize(1, ClipCard._TH_H)
                sep2.setStyleSheet(f"background:{C['border']};")
                self._pc_hbox.addWidget(sep2, 0, Qt.AlignmentFlag.AlignVCenter)
            self._pc_hbox.addWidget(card2)

        self._clips_hbox.addStretch()
        self._pc_hbox.addStretch()

        # Verrouille l'ADN visuel par défaut si plusieurs clips
        self._update_seed_lock_default()

        if self._rb_per_clip.isChecked():
            self._on_card_focused(0)

    def _get_pc_cards(self) -> list[ClipCard]:
        return [
            self._pc_hbox.itemAt(i).widget()
            for i in range(self._pc_hbox.count())
            if isinstance(self._pc_hbox.itemAt(i).widget(), ClipCard)
        ]

    # ── Per-clip prompt ───────────────────────────────────────────────────────

    def _on_card_focused(self, idx: int):
        if not self._rb_per_clip.isChecked():
            return
        # Sauvegarde le prompt courant
        if self._active_clip_idx is not None:
            self._per_clip_prompts[self._active_clip_idx] = (
                self._per_clip_prompt.toPlainText()
            )
        # Désactive la carte précédente dans le panneau per-clip
        pc_cards = self._get_pc_cards()
        if self._active_clip_idx is not None and self._active_clip_idx < len(pc_cards):
            pc_cards[self._active_clip_idx].set_active(False)
        # Active la nouvelle carte
        self._active_clip_idx = idx
        if idx < len(pc_cards):
            pc_cards[idx].set_active(True)
        # Mise à jour label + textarea
        if idx < len(self._clip_cards):
            name = self._clip_cards[idx].clip().get("name", f"Clip {idx + 1}")
            self._per_clip_title.setText(f"▸  Prompt pour : {name}")
        self._per_clip_prompt.blockSignals(True)
        self._per_clip_prompt.setPlainText(self._per_clip_prompts.get(idx, ""))
        self._per_clip_prompt.blockSignals(False)

    def _on_per_clip_prompt_changed(self):
        if self._active_clip_idx is not None:
            self._per_clip_prompts[self._active_clip_idx] = (
                self._per_clip_prompt.toPlainText()
            )

    # ── Enhance Claude — prompt global ────────────────────────────────────────

    def _on_enhance_global(self):
        prompt = self._prompt_global.toPlainText().strip()
        if not prompt:
            QMessageBox.warning(self, "Prompt vide", "Écris un prompt à améliorer !")
            return
        self._btn_enhance_global.setEnabled(False)
        self._enhance_worker_global = EnhanceWorker(prompt, system=_SYSTEM_DAVINCI_EDIT)
        self._enhance_worker_global.finished.connect(self._on_enhance_global_done)
        self._enhance_worker_global.failed.connect(self._on_enhance_global_failed)
        self._enhance_worker_global.start()

    def _on_enhance_global_done(self, enhanced: str):
        self._prompt_global.setPlainText(enhanced)
        self._btn_enhance_global.setEnabled(True)

    def _on_enhance_global_failed(self, error: str):
        self._btn_enhance_global.setEnabled(True)
        QMessageBox.warning(self, "Amélioration impossible", error)

    # ── Enhance Claude — prompt per-clip ──────────────────────────────────────

    def _on_enhance_per_clip(self):
        prompt = self._per_clip_prompt.toPlainText().strip()
        if not prompt:
            QMessageBox.warning(self, "Prompt vide", "Écris un prompt à améliorer !")
            return
        self._btn_enhance_per_clip.setEnabled(False)
        self._enhance_worker_per_clip = EnhanceWorker(prompt, system=_SYSTEM_DAVINCI_EDIT)
        self._enhance_worker_per_clip.finished.connect(self._on_enhance_per_clip_done)
        self._enhance_worker_per_clip.failed.connect(self._on_enhance_per_clip_failed)
        self._enhance_worker_per_clip.start()

    def _on_enhance_per_clip_done(self, enhanced: str):
        self._per_clip_prompt.setPlainText(enhanced)
        self._btn_enhance_per_clip.setEnabled(True)

    def _on_enhance_per_clip_failed(self, error: str):
        self._btn_enhance_per_clip.setEnabled(True)
        QMessageBox.warning(self, "Amélioration impossible", error)

    # ── Mode prompt ───────────────────────────────────────────────────────────

    def _on_prompt_mode_changed(self, checked: bool):
        is_global = self._rb_global.isChecked()
        self._prompt_global.setVisible(is_global)
        self._per_clip_panel.setVisible(not is_global)
        if not is_global and self._clip_cards and self._active_clip_idx is None:
            self._on_card_focused(0)

    # ── Sélection ─────────────────────────────────────────────────────────────

    def _set_all_checked(self, state: bool):
        for card in self._clip_cards:
            card.set_checked(state)

    def _clear_clips(self):
        self._load_clips([])

    # ── Style de film ─────────────────────────────────────────────────────────

    def _on_film_style_changed(self, idx: int):
        import core.style as style_api
        key = self._film_style_combo.currentData()
        if not key or key == "__sep__":
            self._style_key    = ""
            self._style_suffix = ""
            return
        self._style_key = key
        entry = next((s for s in style_api.STYLES if s["key"] == key), None)
        self._style_suffix = entry.get("video_suffix", "") if entry else ""

    def _on_style_gallery(self):
        import core.style as style_api
        from ui.dialog_style_gallery import StyleGalleryDialog
        dlg = StyleGalleryDialog(
            self,
            current_style_key=self._style_key,
            current_ref_image=self._style_ref_path,
        )
        if dlg.exec() != StyleGalleryDialog.DialogCode.Accepted:
            return
        if dlg.was_cleared():
            self._on_style_ref_clear()
            return
        chosen = dlg.result_path()
        if not chosen:
            return
        self._style_ref_path = chosen
        self._style_key      = dlg._current_key
        style_entry = next((s for s in style_api.STYLES if s["key"] == self._style_key), None)
        self._style_suffix   = style_entry.get("video_suffix", "") if style_entry else ""
        for i in range(self._film_style_combo.count()):
            if self._film_style_combo.itemData(i) == self._style_key:
                self._film_style_combo.blockSignals(True)
                self._film_style_combo.setCurrentIndex(i)
                self._film_style_combo.blockSignals(False)
                break
        self._style_ref_override_lbl.setVisible(True)
        self._film_style_combo.setVisible(False)
        pix = QPixmap(chosen)
        if not pix.isNull():
            self._style_ref_thumb.setPixmap(
                pix.scaled(154, 100,
                           Qt.AspectRatioMode.KeepAspectRatio,
                           Qt.TransformationMode.SmoothTransformation)
            )
        self._style_ref_preview_frame.setVisible(True)

    def _on_style_ref_clear(self):
        self._style_key      = ""
        self._style_ref_path = ""
        self._style_suffix   = ""
        self._style_ref_thumb.setPixmap(QPixmap())
        self._style_ref_preview_frame.setVisible(False)
        self._style_ref_override_lbl.setVisible(False)
        self._film_style_combo.setCurrentIndex(0)
        self._film_style_combo.setVisible(True)

    # ── Modèle / ratio ────────────────────────────────────────────────────────

    def _get_model(self) -> str:
        return self._cb_model.currentData() or "seedance-2.0"

    def _on_engine_changed(self):
        key = self._get_model()
        fixed_res = key in _FIXED_RES_ENGINES
        self._cb_res.setEnabled(not fixed_res)
        self._cb_ratio.setEnabled(key not in _FIXED_RATIO_ENGINES)
        if fixed_res:
            self._cb_res.setCurrentText(_ENGINE_RES_FORCED.get(key, "1080p"))
        if hasattr(self, "_ref_compat_banner"):
            self._ref_compat_banner.setVisible(key in _TEXT_FALLBACK_ENGINES)

    def _get_aspect_ratio(self) -> str:
        return self._cb_ratio.currentText().split(" ")[0]

    # ── ADN visuel (seed) ─────────────────────────────────────────────────────

    def _update_seed_lock_default(self):
        """Coche le verrou ADN si plusieurs clips sont sélectionnés."""
        n_checked = sum(1 for c in self._clip_cards if c.is_checked())
        if n_checked > 1 and not self._seed_lock_btn.isChecked():
            self._seed_lock_btn.setChecked(True)

    def _on_card_check_changed(self, _index: int, _checked: bool):
        self._update_seed_lock_default()

    def _on_seed_toggle(self, checked: bool):
        if checked:
            self._seed_lock_btn.setText("🔒  ADN visuel — garder pour tous les plans")
        else:
            self._seed_lock_btn.setText("🔓  ADN visuel — aléatoire")
            self._last_seed = None

    def _get_seed(self) -> int | None:
        if not self._seed_lock_btn.isChecked():
            return None
        return self._last_seed

    # ── File d'attente ────────────────────────────────────────────────────────

    def _check_bridge_then_start(self):
        """Vérifie la connexion bridge puis lance la file si ok, sinon propose un dialog."""
        if self._bridge_connected:
            self._start_queue()
            return
        from PyQt6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton
        from PyQt6.QtCore import Qt as _Qt
        dlg = QDialog(self)
        dlg.setWindowTitle("Bridge non connecté")
        dlg.setFixedWidth(420)
        dlg.setStyleSheet(f"background:{C['bg1']};color:{C['text_primary']};")
        vlay = QVBoxLayout(dlg)
        vlay.setSpacing(12)
        vlay.setContentsMargins(20, 20, 20, 20)
        lbl = QLabel(
            "○  Le bridge DaVinci n'est pas connecté.\n\n"
            "Les vidéos générées ne seront pas importées\n"
            "automatiquement dans le Media Pool.\n\n"
            "Pour connecter le bridge :\n"
            "DaVinci Resolve → Espace de travail → Scripts → seedance_bridge\n"
            "Laissez la fenêtre PANDORA Bridge ouverte."
        )
        lbl.setStyleSheet(f"color:{C['text_secondary']};font-size:11px;line-height:1.5;")
        lbl.setWordWrap(True)
        vlay.addWidget(lbl)
        row = QHBoxLayout()
        row.setSpacing(8)
        btn_close = QPushButton("Fermer")
        btn_close.setFixedHeight(34)
        btn_close.setStyleSheet(
            f"QPushButton{{background:{C['bg3']};color:{C['text_secondary']};"
            f"border:1px solid {C['border']};border-radius:7px;font-size:12px;padding:0 16px;}}"
            f"QPushButton:hover{{background:{C['border']};color:{C['text_primary']};}}"
        )
        btn_close.clicked.connect(dlg.reject)
        btn_retry = QPushButton("↻  Vérifier la connexion")
        btn_retry.setFixedHeight(34)
        btn_retry.setStyleSheet(
            f"QPushButton{{background:{C['bg3']};color:{C['accent']};"
            f"border:1px solid {C['accent']};border-radius:7px;font-size:12px;padding:0 16px;}}"
            f"QPushButton:hover{{background:rgba(78,220,196,0.12);}}"
        )
        def _retry():
            if self._ping_worker and self._ping_worker.isRunning():
                return
            self._ping_worker = BridgePingWorker()
            def _on_retry_result(connected, tl):
                self._on_ping_result(connected, tl)
                if connected:
                    dlg.accept()
                    self._start_queue()
            self._ping_worker.result.connect(_on_retry_result)
            self._ping_worker.start()
        btn_retry.clicked.connect(_retry)
        btn_continue = QPushButton("Générer sans import")
        btn_continue.setFixedHeight(34)
        btn_continue.setStyleSheet(
            f"QPushButton{{background:{C['accent']};color:#07080f;"
            f"border:none;border-radius:7px;font-size:12px;font-weight:700;padding:0 16px;}}"
            f"QPushButton:hover{{background:#6eded6;}}"
        )
        btn_continue.clicked.connect(dlg.accept)
        btn_continue.clicked.connect(self._start_queue)
        row.addWidget(btn_close)
        row.addWidget(btn_retry)
        row.addStretch()
        row.addWidget(btn_continue)
        vlay.addLayout(row)
        dlg.exec()

    def _start_queue(self):
        if self._worker and self._worker.isRunning():
            QMessageBox.warning(self, "Génération en cours",
                                "Une génération est déjà en cours. Attendez qu'elle se termine.")
            return

        checked = [(i, card) for i, card in enumerate(self._clip_cards) if card.is_checked()]
        if not checked:
            QMessageBox.warning(self, "Aucun clip sélectionné",
                                "Cochez au moins un clip avant de lancer la file d'attente.")
            return

        # Validation du format : H.264 720p, fichier < 50 MB
        invalid_clips = []
        for clip_idx, _card in checked:
            clip = self._clips_data[clip_idx]
            fp = clip.get("file_path", "")
            name = clip.get("name", f"Clip {clip_idx + 1}")
            if fp and os.path.isfile(fp):
                size_mb = os.path.getsize(fp) / (1024 * 1024)
                if size_mb > 50:
                    invalid_clips.append(f"{name}  ({size_mb:.0f} MB)")
                    continue
                res = clip.get("resolution", "")
                if res:
                    try:
                        parts = res.replace(" ", "").lower().split("x")
                        if len(parts) == 2:
                            h = int(parts[1])
                            if h > 720:
                                invalid_clips.append(f"{name}  ({res})")
                    except (ValueError, IndexError):
                        pass
        if invalid_clips:
            QMessageBox.warning(
                self,
                "Format non supporté",
                "Pour le moment, seuls les clips exportés en H.264 720p (ou inférieur) "
                "et inférieurs à 50 MB peuvent être envoyés à Seedance.\n\n"
                "Veuillez ré-exporter les clips suivants depuis DaVinci Resolve "
                "en H.264 720p avant de relancer :\n\n"
                + "\n".join(f"  • {c}" for c in invalid_clips)
            )
            return

        # Sauvegarde le prompt per-clip courant avant de lancer
        if self._rb_per_clip.isChecked() and self._active_clip_idx is not None:
            self._per_clip_prompts[self._active_clip_idx] = (
                self._per_clip_prompt.toPlainText()
            )

        n_prises = self._spin_prises.value()
        self._queue = []
        for (clip_idx, _card) in checked:
            for p in range(n_prises):
                self._queue.append((clip_idx, p))

        self._queue_pos = 0

        # Seed fixé UNE SEULE FOIS pour toute la file si verrou activé
        if self._seed_lock_btn.isChecked():
            if not self._last_seed:
                import random
                self._last_seed = random.randint(1, 999_999_999)
        else:
            self._last_seed = None

        total = len(self._queue)
        n_clips = len(checked)
        n_prises = self._spin_prises.value()
        self._lbl_queue_info.setText(
            f"File d'attente : {n_clips} clip(s) × {n_prises} prise(s) = {total} génération(s)  —  "
            f"traitement séquentiel, 1 clip à la fois"
        )
        self._progress.setVisible(True)
        self._progress.setValue(0)
        self._btn_generate.setEnabled(False)
        self._btn_cancel.setVisible(True)

        for card in self._clip_cards:
            card.set_status("")

        self._process_next()

    def _process_next(self):
        if self._queue_pos >= len(self._queue):
            self._on_queue_done()
            return

        clip_idx, prise_idx = self._queue[self._queue_pos]
        card = self._clip_cards[clip_idx]
        clip = card.clip()
        n_prises = self._spin_prises.value()
        card.set_status(f"P{prise_idx + 1}/{n_prises}…", C["accent"])

        if self._rb_per_clip.isChecked():
            base_prompt = self._per_clip_prompts.get(clip_idx, "").strip()
        else:
            base_prompt = self._prompt_global.toPlainText().strip()

        creative_suffix = self._creative.get_creative_suffix()
        prompt = " ".join(p for p in [base_prompt, creative_suffix, self._style_suffix] if p)

        seed = self._get_seed()

        video_path = clip.get("file_path", "")
        has_video = bool(video_path and os.path.isfile(video_path))

        # Inject @Video1 so Seedance knows to reference the uploaded clip
        if has_video and "@Video1" not in prompt:
            prompt = f"@Video1 {prompt}" if prompt else "@Video1"

        params = {
            "mode":         "ext" if has_video else "t2v",
            "direction":    "new_take",
            "prompt":       prompt,
            "model":        self._get_model(),
            "duration":     5,
            "resolution":   self._cb_res.currentText(),
            "aspect_ratio": self._get_aspect_ratio(),
        }
        if has_video:
            params["video_path"] = video_path
        if seed:
            params["seed"] = seed

        _model_key = self._get_model()
        if _model_key in _SEEDANCE_ENGINES:
            self._worker = GenerationWorker(params)
            self._worker.finished.connect(
                lambda r, ci=clip_idx, pi=prise_idx: self._on_clip_done(r, ci, pi)
            )
        else:
            self._worker = _make_ext_worker(_model_key, params)
            if self._worker is None:
                self._on_clip_failed(f"Moteur inconnu : {_model_key}", clip_idx, prise_idx)
                return
            _raw = params.get("prompt", "")
            self._worker.finished.connect(
                lambda r, ci=clip_idx, pi=prise_idx, p=_raw:
                    self._on_clip_done(_norm_ext_result(r, p), ci, pi)
            )
        self._worker.progress.connect(self._on_progress)
        self._worker.failed.connect(
            lambda e, ci=clip_idx, pi=prise_idx: self._on_clip_failed(e, ci, pi)
        )
        self._worker.start()

        total = len(self._queue)
        done  = self._queue_pos
        self._progress.setValue(int(done / total * 100))
        self._lbl_progress.setText(
            f"[{done + 1}/{total}]  {clip.get('name', '?')}  — prise {prise_idx + 1}"
        )

    def _on_progress(self, pct: int, msg: str):
        txt  = self._lbl_progress.text()
        base = txt.split("—")[0] if "—" in txt else txt
        self._lbl_progress.setText(f"{base}— {pct}%  {msg}")
        total = len(self._queue)
        if total > 0:
            bar_pct = int((self._queue_pos / total) * 100 + (1 / total) * pct)
            self._progress.setValue(bar_pct)

    def _on_clip_done(self, result: dict, clip_idx: int, prise_idx: int):
        card = self._clip_cards[clip_idx]
        n_pr = self._spin_prises.value()
        card.set_status(f"P{prise_idx + 1}/{n_pr} ✓", C["green"])

        seed_used = result.get("seed", 0)
        if seed_used and seed_used > 0 and self._seed_lock_btn.isChecked():
            self._last_seed = seed_used

        # ── LatentSync branch ─────────────────────────────────────────────────
        if self._cb_lipsync.isChecked() and self._cb_lipsync.isEnabled():
            video_url   = result.get("video_url", "")
            source_path = self._clips_data[clip_idx].get("file_path", "")
            mock_url    = not video_url or "mock" in video_url or not video_url.startswith("http")
            if video_url and not mock_url and source_path and os.path.isfile(source_path):
                self._start_lipsync(result, clip_idx, prise_idx)
                return  # la file avancera depuis _on_lipsync_done/_on_lipsync_failed

        self._import_and_advance(result, clip_idx, prise_idx)

    def _start_lipsync(self, seedance_result: dict, clip_idx: int, prise_idx: int):
        from api.lipsync import LatentSyncWorker
        card      = self._clip_cards[clip_idx]
        n_pr      = self._spin_prises.value()
        clip_name = card.clip().get("name", "") if card else ""
        card.set_status(f"P{prise_idx + 1}/{n_pr} ↷ LS…", C["accent"])

        self._lbl_lipsync_stage.setText("● Étape 2/3 — Synchronisation LatentSync…")
        self._lbl_lipsync_stage.setVisible(True)

        self._lipsync_worker = LatentSyncWorker(
            video_url         = seedance_result.get("video_url", ""),
            source_video_path = self._clips_data[clip_idx].get("file_path", ""),
            output_dir        = get_output_dir(),
            shot_name         = clip_name,
        )
        self._lipsync_worker.progress.connect(self._on_lipsync_progress)
        self._lipsync_worker.finished.connect(
            lambda vp, ap: self._on_lipsync_done(seedance_result, clip_idx, prise_idx, vp, ap)
        )
        self._lipsync_worker.failed.connect(
            lambda err: self._on_lipsync_failed(seedance_result, clip_idx, prise_idx, err)
        )
        self._lipsync_worker.start()

    def _on_lipsync_progress(self, pct: int, msg: str):
        self._lbl_lipsync_stage.setText(f"● Étape 2/3 — LatentSync  {pct}%  {msg}")

    def _on_lipsync_done(self, seedance_result: dict, clip_idx: int, prise_idx: int,
                          video_path: str, audio_path: str):
        from davinci.importer import import_audio_to_bin
        card     = self._clip_cards[clip_idx]
        n_pr     = self._spin_prises.value()
        do_import = self._cb_import.isChecked()

        self._lbl_lipsync_stage.setText("● Étape 3/3 — Import DaVinci…")

        # Import vidéo lip-synced
        dav_ok = False
        if do_import and video_path and os.path.isfile(video_path):
            from davinci.bridge import resolve as _resolve
            if _resolve.is_connected():
                dav_ok = _resolve.import_media_to_bin(video_path, "")
                # Import piste audio séparée
                if audio_path and os.path.isfile(audio_path):
                    import_audio_to_bin(audio_path)

        if dav_ok:
            card.set_status(f"P{prise_idx + 1}/{n_pr} ↷ → DaVinci", C["green"])
        elif video_path:
            card.set_status(f"P{prise_idx + 1}/{n_pr} ↷ ✓ sauvegardé", C["green"])
        else:
            card.set_status(f"P{prise_idx + 1}/{n_pr} ↷ ✓", C["green"])

        self._lbl_lipsync_stage.setVisible(False)

        hist_entry = {
            "mode":       "t2v",
            "prompt":     seedance_result.get("prompt", ""),
            "model":      self._get_model(),
            "video_path": video_path,
            "duration":   seedance_result.get("duration", ""),
        }
        save_to_history(hist_entry)
        self.generation_done.emit(hist_entry)
        self._advance_queue()

    def _on_lipsync_failed(self, seedance_result: dict, clip_idx: int, prise_idx: int, error: str):
        card = self._clip_cards[clip_idx]
        n_pr = self._spin_prises.value()
        card.set_status(f"P{prise_idx + 1}/{n_pr} ↷ ✗", C["red"])
        self._lbl_lipsync_stage.setVisible(False)
        # Fallback : import Seedance result normalement
        self._import_and_advance(seedance_result, clip_idx, prise_idx)

    def _import_and_advance(self, result: dict, clip_idx: int, prise_idx: int):
        card      = self._clip_cards[clip_idx]
        n_pr      = self._spin_prises.value()
        clip_name = card.clip().get("name", "") if card else ""
        do_import = self._cb_import.isChecked()
        local_path = ""
        try:
            ir = import_result(result, get_output_dir(), shot_title=clip_name,
                               import_to_davinci=do_import)
        except Exception as exc:
            ir = {"success": False, "local_path": "", "mock": False,
                  "davinci_imported": False, "error": str(exc)}
        if ir.get("mock"):
            card.set_status(f"P{prise_idx + 1}/{n_pr} ✓ (mock)", C["green"])
        elif ir.get("success"):
            local_path = ir.get("local_path", "")
            if ir.get("davinci_imported"):
                card.set_status(f"P{prise_idx + 1}/{n_pr} ✓ → DaVinci", C["green"])
            else:
                card.set_status(f"P{prise_idx + 1}/{n_pr} ✓ sauvegardé", C["green"])
        else:
            err = ir.get("error", "erreur inconnue")
            card.set_status(f"P{prise_idx + 1}/{n_pr} ✗ {err[:40]}", C["red"])

        hist_entry = {
            "mode":       "t2v",
            "prompt":     result.get("prompt", ""),
            "model":      self._get_model(),
            "video_path": local_path,
            "duration":   result.get("duration", ""),
        }
        save_to_history(hist_entry)
        self.generation_done.emit(hist_entry)
        self._advance_queue()

    def _advance_queue(self):
        self._queue_pos += 1
        total = len(self._queue)
        done  = self._queue_pos
        self._lbl_queue_info.setText(f"File : {total} génération(s) — {done} terminée(s)")
        self._progress.setValue(int(done / total * 100))
        self._process_next()

    def _on_clip_failed(self, error: str, clip_idx: int, prise_idx: int):
        card = self._clip_cards[clip_idx]
        n_pr = self._spin_prises.value()
        card.set_status(f"P{prise_idx + 1}/{n_pr} ✗", C["red"])
        self._queue_pos += 1
        self._lbl_lipsync_stage.setVisible(False)
        self._process_next()

    def _cancel_queue(self):
        if self._lipsync_worker:
            try:
                self._lipsync_worker.finished.disconnect()
                self._lipsync_worker.failed.disconnect()
                self._lipsync_worker.progress.disconnect()
            except Exception:
                pass
            self._lipsync_worker.quit()
            self._lipsync_worker = None
        if self._worker:
            try:
                self._worker.finished.disconnect()
                self._worker.failed.disconnect()
                self._worker.progress.disconnect()
            except Exception:
                pass
            if hasattr(self._worker, "cancel"):
                self._worker.cancel()
            else:
                self._worker.quit()
                self._worker.terminate()
            self._worker = None
        self._queue_pos = len(self._queue)
        self._lbl_queue_info.setText("File annulée.")
        self._lbl_progress.setText("")
        self._lbl_lipsync_stage.setVisible(False)
        self._progress.setVisible(False)
        self._btn_generate.setEnabled(True)
        self._btn_cancel.setVisible(False)

    def _open_output_folder(self):
        import subprocess as _sp
        folder = get_output_dir()
        os.makedirs(folder, exist_ok=True)
        _sp.Popen(["explorer", folder])

    def _on_queue_done(self):
        self._btn_generate.setEnabled(True)
        self._btn_cancel.setVisible(False)
        self._btn_open_folder.setVisible(True)
        self._lbl_lipsync_stage.setVisible(False)
        total = len(self._queue)
        self._lbl_queue_info.setText(f"File terminée — {total} génération(s) complétée(s).")
        self._progress.setValue(100)
        self._lbl_progress.setText("")
