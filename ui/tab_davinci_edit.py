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

from PyQt6.QtCore import Qt, QFileSystemWatcher, QThread, QSize, pyqtSignal
from PyQt6.QtGui import QPixmap, QColor, QPainter, QLinearGradient, QIcon
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QScrollArea, QTextEdit, QComboBox, QSpinBox, QButtonGroup,
    QRadioButton, QCheckBox, QFrame, QProgressBar, QMessageBox,
    QFileDialog,
)

from ui.styles import C
from ui.widgets import HelpBlock, section_label, combo, toggle_row
from ui.creative_panel import SeedanceCreativePanel
from ui.icons import claude_icon_pixmap, install_hover_icon, load_icon
from core.config import load_config, get_output_dir
from core.i18n import translate
from core.history import save_to_history
from core.worker import GenerationWorker, abandon_thread
from api.enhance import EnhanceWorker, _SYSTEM_DAVINCI_EDIT
from davinci.importer import import_result
from davinci.ping_worker import BridgePingWorker
from ui.tab_t2v import (
    _DaVinciBar, _ENGINES, _DAVINCI_ENGINES, _SEEDANCE_ENGINES,
    _FIXED_RES_ENGINES, _FIXED_RATIO_ENGINES, _ENGINE_RES_FORCED,
    _TEXT_FALLBACK_ENGINES, _ENGINE_RESOLUTIONS,
    _make_ext_worker, _norm_ext_result,
)


_INBOX = os.path.join(os.environ.get("TEMP", tempfile.gettempdir()), "pandora_clips_inbox.json")


# Modèles de prompt « Type de modification » (Modifier un clip). Cas les plus courants.
# Balises Seedance : @Video1 = clip d'origine (ajouté auto), @Image1 = image de
# référence. Structure « reprends tout de @Video1, ne change QUE X » → cible la
# modification sans tout régénérer. Texte FR traduit à l'affichage (i18n) et à l'envoi.
_MOD_TEMPLATES = {
    "bg": ("Reprends exactement @Video1 — mêmes personnages, mouvements, cadrage et "
           "lumière sur les sujets. Remplace UNIQUEMENT le décor / l'arrière-plan par "
           "celui de @Image1. Garde la même intégration lumineuse et les mêmes ombres "
           "sur les personnages. Ne change rien d'autre."),
    "face": ("Reprends exactement @Video1 — mêmes mouvements, cadrage, lumière, décor, "
             "vêtements et morphologie. Remplace UNIQUEMENT le visage et l'identité du "
             "personnage par celui de @Image1. Garde la même expression, la même "
             "direction du regard et le même éclairage sur le visage. Ne change rien d'autre."),
    "grade": ("Reprends exactement @Video1 — même scène, mouvements, cadrage et sujets, "
              "à l'identique. Change UNIQUEMENT l'étalonnage colorimétrique : [décris le "
              "look, ex. teal & orange cinématographique / heure dorée chaude / désaturé "
              "froid]. Ne modifie ni la composition ni les sujets."),
    "outfit": ("Reprends exactement @Video1 — mêmes personnages, visages, mouvements, "
               "cadrage, décor et lumière. Remplace UNIQUEMENT la tenue / les vêtements "
               "du personnage par celle de @Image1 (ou décris la tenue voulue). Garde la "
               "même morphologie et un tissu cohérent avec le mouvement. Ne change rien d'autre."),
}


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


# ── Worker extraction première frame ─────────────────────────────────────────

class _ThumbWorker(QThread):
    """Extrait la première image d'un clip vidéo (ffmpeg) sans bloquer l'UI."""
    done = pyqtSignal(int, object)  # index, QImage

    def __init__(self, index: int, path: str, parent=None):
        super().__init__(parent)
        self._index = index
        self._path  = path

    def run(self):
        from PyQt6.QtGui import QImage
        from core.video_utils import extract_first_frame, get_thumb_cache_path
        cache_path = get_thumb_cache_path(self._path)
        try:
            if not os.path.isfile(cache_path):
                ok = extract_first_frame(self._path, cache_path)
                if not ok:
                    return
            img = QImage(cache_path)
            if not img.isNull():
                self.done.emit(self._index, img)
        except Exception:
            pass


# ── Carré de référence visuelle (identique au widget Casting) ────────────────

class _DrawThumb(QWidget):
    """Vignette (lecture seule) de l'image annotée Draw-to-Video + croix pour la
    retirer. L'image N'EST PAS envoyée au modèle vidéo : elle confirme visuellement
    que le dessin sera pris en compte — Claude Vision le lit, décrit l'intention dans
    le prompt, puis le clip part PROPRE (sans les traits)."""
    removed = pyqtSignal()
    _SZ = 60

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(self._SZ, self._SZ)
        self.setVisible(False)
        self.setToolTip(translate(
            "Dessin Draw-to-Video — interprété par l'IA, jamais envoyé tel quel au modèle"))
        self._thumb = QLabel(self)
        self._thumb.setGeometry(0, 0, self._SZ, self._SZ)
        self._thumb.setScaledContents(True)
        self._thumb.setStyleSheet(f"border-radius:8px;border:1px solid {C['accent_dim']};")
        self._x = QPushButton("×", self)
        self._x.setFixedSize(16, 16)
        self._x.move(self._SZ - 18, 2)
        self._x.setCursor(Qt.CursorShape.PointingHandCursor)
        self._x.setStyleSheet(
            f"QPushButton{{background:{C['bg2']};color:{C['text_dim']};"
            f"border:1px solid {C['border']};border-radius:3px;font-size:9px;padding:0;}}"
            f"QPushButton:hover{{color:{C['red']};border-color:{C['red']};background:{C['bg3']};}}")
        self._x.clicked.connect(self.removed.emit)

    def set_image(self, path: str):
        if path and os.path.isfile(path):
            self._thumb.setPixmap(QPixmap(path).scaled(
                self._SZ, self._SZ,
                Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                Qt.TransformationMode.SmoothTransformation))
            self._x.raise_()
            self.setVisible(True)
        else:
            self.setVisible(False)


class _RefSquare(QWidget):
    """Carré 60×60 — affiche '+' vide ou la miniature de l'image chargée."""
    picked  = pyqtSignal(str)
    cleared = pyqtSignal()

    _SZ = 60

    def __init__(self, tooltip: str = "Ajouter une image de référence", parent=None):
        super().__init__(parent)
        self.setFixedSize(self._SZ, self._SZ)

        self._btn_pick = QPushButton("+", self)
        self._btn_pick.setFixedSize(self._SZ, self._SZ)
        self._btn_pick.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_pick.setToolTip(tooltip)
        self._btn_pick.setStyleSheet(f"""
            QPushButton{{
                background:transparent;color:{C['text_dim']};
                border:1px dashed {C['border_bright']};border-radius:8px;
                font-size:24px;font-weight:300;padding:0;
            }}
            QPushButton:hover{{
                color:{C['accent']};border-color:{C['accent']};
                background:rgba(78,205,196,0.08);
            }}
            QPushButton:pressed{{background:rgba(78,205,196,0.16);}}
        """)
        self._btn_pick.clicked.connect(self._on_pick)

        self._thumb = QLabel(self)
        self._thumb.setGeometry(0, 0, self._SZ, self._SZ)
        self._thumb.setScaledContents(True)
        self._thumb.setStyleSheet("border-radius:8px;")
        self._thumb.setVisible(False)

        self._btn_clear = QPushButton("×", self)
        self._btn_clear.setFixedSize(16, 16)
        self._btn_clear.move(self._SZ - 18, 2)
        self._btn_clear.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_clear.setStyleSheet(f"""
            QPushButton{{background:{C['bg2']};color:{C['text_dim']};
                border:1px solid {C['border']};border-radius:3px;font-size:9px;padding:0;}}
            QPushButton:hover{{color:{C['red']};border-color:{C['red']};background:{C['bg3']};}}
        """)
        self._btn_clear.setVisible(False)
        self._btn_clear.clicked.connect(self._on_clear)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.addWidget(self._btn_pick)

    def path(self) -> str:
        return getattr(self, "_path", "")

    def set_path(self, path: str):
        if path and os.path.isfile(path):
            self._path = path
            pix = QPixmap(path).scaled(
                self._SZ, self._SZ,
                Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                Qt.TransformationMode.SmoothTransformation,
            )
            self._thumb.setPixmap(pix)
            self._thumb.setVisible(True)
            self._btn_pick.setVisible(False)
            self._btn_clear.setVisible(True)
        else:
            self._clear_state()

    def _clear_state(self):
        self._path = ""
        self._thumb.setVisible(False)
        self._btn_pick.setVisible(True)
        self._btn_clear.setVisible(False)

    def _on_pick(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Choisir une image de référence", "",
            "Images (*.png *.jpg *.jpeg *.webp *.bmp);;Tous les fichiers (*)",
        )
        if path:
            self.set_path(path)
            self.picked.emit(path)

    def _on_clear(self):
        self._clear_state()
        self.cleared.emit()


# ── Carte compacte d'un clip (style _ThumbCard de T2V) ───────────────────────

class ClipCard(QFrame):
    """Carte compacte — vignette + nom + badge index + statut génération.
    Sélection par CLIC (contour lumineux) + Ctrl/Maj pour la multi-sélection,
    comme dans « Générer depuis Storyboard » (plus de case à cocher)."""
    focused = pyqtSignal(int)

    _W    = 112
    _TH_W = 100
    _TH_H = 56

    def __init__(self, clip: dict, index: int, parent=None):
        super().__init__(parent)
        self._clip     = clip
        self._index    = index
        self._active   = False
        self._selected = False

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
        if self._active or self._selected:
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

    def set_selected(self, v: bool):
        self._selected = v
        self._apply_style()

    def is_selected(self) -> bool:
        return self._selected

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

    def set_thumb_pixmap(self, pix: QPixmap):
        self._thumb.setPixmap(pix)


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
        self._selected_clips:   set[int]                 = set()  # clips sélectionnés (clic+glow)
        self._sel_anchor:       int | None               = None   # ancre pour Maj+clic
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
        self._global_ref_image: str                      = ""
        self._per_clip_ref_images: dict[int, str]        = {}
        self._draw_images:      dict[int, str]           = {}   # Draw-to-Video : image annotée par clip
        self._draw_overlays:    dict[int, str]           = {}   # calque de dessin seul (ré-édition)
        self._draw_frames:      dict[int, int]           = {}   # index d'image dessinée (ré-édition)
        self._mock_count:       int                      = 0
        self._failed_clips:     list[tuple[int, str]]    = []
        self._thumb_workers:    list[_ThumbWorker]       = []

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
            "  • Résolution : 1080p maximum",
            "  • Taille : moins de 50 MB",
            "  • Format : H.264 MP4 ou MOV recommandé",
            "  → Depuis DaVinci : Fichier → Exporter → sélectionner H.264 Master à 1080p",
            "    avant d'envoyer les clips via pandora_send.",
        ], C))

        # ── Référence visuelle (template de style) ────────────────────────────
        self._film_style_frame = QFrame()
        self._film_style_frame.setStyleSheet(
            f"QFrame{{background:rgba(124,107,255,0.08);"
            f"border:1px solid {C['accent_dim']};border-radius:8px;}}"
        )
        _fs_outer = QVBoxLayout(self._film_style_frame)
        _fs_outer.setContentsMargins(14, 12, 14, 12)
        _fs_outer.setSpacing(8)
        _fs_outer.setAlignment(Qt.AlignmentFlag.AlignHCenter)

        _fs_lbl = QLabel("Choisir une référence visuelle")
        _fs_lbl.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        _fs_lbl.setStyleSheet(
            f"color:{C['accent']};font-size:11px;font-weight:700;background:transparent;border:none;"
        )
        _fs_outer.addWidget(_fs_lbl)

        # Rectangle fixe — toujours visible
        _preview_h_row = QHBoxLayout()
        _preview_h_row.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        _preview_frame_ref = QFrame()
        _preview_frame_ref.setFixedSize(160, 140)
        _preview_frame_ref.setStyleSheet(
            f"QFrame{{background:{C['bg2']};border:1px solid {C['border_bright']};border-radius:8px;}}"
        )
        _pf_lay = QVBoxLayout(_preview_frame_ref)
        _pf_lay.setContentsMargins(4, 4, 4, 4)
        _pf_lay.setSpacing(0)
        self._style_ref_thumb = QLabel()
        self._style_ref_thumb.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._style_ref_thumb.setStyleSheet("background:transparent;border:none;")
        _pf_lay.addWidget(self._style_ref_thumb)
        _preview_h_row.addWidget(_preview_frame_ref)
        _fs_outer.addLayout(_preview_h_row)

        # Bouton "Template de style" — centré, toujours visible
        _gal_row = QHBoxLayout()
        _gal_row.setAlignment(Qt.AlignmentFlag.AlignHCenter)
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
        _gal_row.addWidget(self._btn_style_gallery)
        _fs_outer.addLayout(_gal_row)

        # Bouton "Retirer" — caché jusqu'à sélection
        _clear_ref_row = QHBoxLayout()
        _clear_ref_row.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        self._style_ref_clear_btn = QPushButton("× Retirer")
        self._style_ref_clear_btn.setFixedHeight(24)
        self._style_ref_clear_btn.setVisible(False)
        self._style_ref_clear_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._style_ref_clear_btn.setStyleSheet(
            f"QPushButton{{background:transparent;color:{C['text_dim']};"
            f"border:1px solid {C['border']};border-radius:4px;font-size:10px;padding:0 8px;}}"
            f"QPushButton:hover{{color:{C['red']};border-color:{C['red']};}}"
        )
        self._style_ref_clear_btn.clicked.connect(self._on_style_ref_clear)
        _clear_ref_row.addWidget(self._style_ref_clear_btn)
        _fs_outer.addLayout(_clear_ref_row)

        # ── ADN visuel — centré sous le template ─────────────────────────────
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
        _adn_row.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        _adn_row.addWidget(self._seed_lock_btn)

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
        self._btn_import_files = QPushButton("📁  Importer des fichiers vidéo")
        self._btn_import_files.setFixedHeight(26)
        self._btn_import_files.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_import_files.setStyleSheet(
            f"QPushButton{{background:transparent;color:{C['accent']};"
            f"border:1px solid {C['accent']};border-radius:5px;"
            f"font-size:10px;font-weight:600;padding:0 12px;}}"
            f"QPushButton:hover{{background:rgba(78,205,196,0.10);}}"
        )
        self._btn_import_files.clicked.connect(self._on_import_files)
        sel_row.addWidget(self._btn_import_files)
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
        self._clips_scroll.setStyleSheet(
            f"QScrollArea{{background:transparent;border:none;}}"
            f"QScrollBar:horizontal{{background:{C['bg1']};height:4px;border-radius:2px;margin:0;}}"
            f"QScrollBar::handle:horizontal{{background:{C['border_bright']};border-radius:2px;min-width:30px;}}"
            f"QScrollBar::add-line:horizontal,QScrollBar::sub-line:horizontal{{width:0px;}}"
        )
        self._clips_scroll.setVisible(False)
        body_clips.addWidget(self._clips_scroll)

        self._lbl_empty = QLabel(
            "Aucun clip — lancez pandora_send dans DaVinci (Espace de travail → Scripts)"
        )
        self._lbl_empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._lbl_empty.setStyleSheet(f"color:{C['text_dim']};font-size:11px;padding:20px;")
        body_clips.addWidget(self._lbl_empty)

        # ── En-tête repliable (comme Générer depuis Storyboard / Live) ────────
        self._film_style_frame.setVisible(False)
        self._btn_style_toggle = QPushButton("▸  Choisir les références")
        self._btn_style_toggle.setCheckable(True)
        self._btn_style_toggle.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_style_toggle.setStyleSheet(
            f"QPushButton{{background:{C['bg2']};color:{C['text_secondary']};"
            f"border:1px solid {C['border']};border-radius:8px;text-align:left;"
            f"font-size:11px;font-weight:700;padding:8px 14px;}}"
            f"QPushButton:hover{{background:{C['bg3']};color:{C['text_primary']};}}"
            f"QPushButton:checked{{color:{C['accent']};border-color:{C['accent_dim']};}}")

        def _toggle_style(checked):
            self._film_style_frame.setVisible(checked)
            self._btn_style_toggle.setText(
                ("▾  " if checked else "▸  ") + "Choisir les références")
        self._btn_style_toggle.toggled.connect(_toggle_style)
        lay.addWidget(self._btn_style_toggle)
        lay.addWidget(self._film_style_frame)
        lay.addWidget(sec_clips)
        lay.addLayout(_adn_row)

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
        self._pg_frame = QFrame()
        self._pg_frame.setStyleSheet(
            f"QFrame{{background:{C['bg2']};border:1px solid {C['border']};border-radius:10px;}}"
        )
        _pg_lay = QVBoxLayout(self._pg_frame)
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
        # « Améliorer le prompt » (☁) RETIRÉ — fonction jugée inutile/instable.
        self._btn_enhance_global.setVisible(False)
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

        # Draw-to-Video — bouton LOGO « Dessiner sur la vidéo » placé à DROITE du
        # rectangle de prompt (badge couleur affiché tel quel, sans teinte ; repli
        # texte si l'asset est introuvable). Le clic ouvre le dialogue Draw-to-Video.
        self._btn_draw = QPushButton()
        self._btn_draw.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_draw.setToolTip(translate("Dessiner sur la vidéo") + " — " + translate(
            "Draw-to-Video : choisis un clip, dessine les zones de l'effet "
            "(feu, fumée…), puis génère — l'effet est appliqué là où tu as dessiné."))
        _draw_pix = load_icon("draw_to_video.png", 56)   # badge couleur → pas de teinte
        if not _draw_pix.isNull():
            self._btn_draw.setIcon(QIcon(_draw_pix))
            self._btn_draw.setIconSize(QSize(56, 56))
            self._btn_draw.setFixedSize(60, 60)
            self._btn_draw.setStyleSheet(
                "QPushButton{background:transparent;border:none;border-radius:12px;padding:2px;}"
                "QPushButton:hover{background:rgba(78,205,196,0.14);}")
        else:
            self._btn_draw.setText("✏  " + translate("Dessiner sur la vidéo"))
            self._btn_draw.setFixedHeight(34)
            self._btn_draw.setStyleSheet(
                f"QPushButton{{background:transparent;color:{C['accent']};"
                f"border:1px solid {C['accent']};border-radius:8px;font-size:11px;font-weight:700;padding:0 14px;}}"
                f"QPushButton:hover{{background:rgba(78,205,196,0.12);}}")
        self._btn_draw.clicked.connect(self._on_draw_to_video)

        _pg_prompt_row = QHBoxLayout()
        _pg_prompt_row.setContentsMargins(0, 0, 0, 0)
        _pg_prompt_row.setSpacing(8)
        _pg_prompt_row.addWidget(self._prompt_global, 1)
        _pg_prompt_row.addWidget(self._btn_draw, 0, Qt.AlignmentFlag.AlignTop)
        _pg_lay.addLayout(_pg_prompt_row)

        # ── Type de modification : insère un modèle de prompt prêt à l'emploi ──
        _mod_row = QHBoxLayout()
        _mod_row.setContentsMargins(0, 10, 0, 0)
        _mod_row.setSpacing(8)
        _mod_lbl = QLabel(translate("Type de modification"))
        _mod_lbl.setStyleSheet(
            f"color:{C['text_secondary']};font-size:11px;background:transparent;border:none;")
        self._mod_combo = QComboBox()
        self._mod_combo.addItem(translate("✎ Insérer un modèle…"), "")
        self._mod_combo.addItem(translate("Changer le décor (arrière-plan)"), "bg")
        self._mod_combo.addItem(translate("Changer un visage"), "face")
        self._mod_combo.addItem(translate("Changer l'étalonnage (couleurs)"), "grade")
        self._mod_combo.addItem(translate("Changer la tenue (vêtements)"), "outfit")
        self._mod_combo.setStyleSheet(
            f"QComboBox{{background:{C['bg2']};color:{C['text_primary']};"
            f"border:1px solid {C['border']};border-radius:6px;padding:4px 8px;font-size:11px;}}"
            f"QComboBox QAbstractItemView{{background:{C['bg2']};color:{C['text_primary']};"
            f"selection-background-color:{C['accent_dim']};}}")
        self._mod_combo.setToolTip(translate(
            "Insère un modèle de prompt (balises @Video1 = clip d'origine, "
            "@Image1 = image de référence) — à compléter ensuite."))
        self._mod_combo.activated.connect(self._on_mod_template)
        _mod_row.addWidget(_mod_lbl)
        _mod_row.addWidget(self._mod_combo, 1)
        _pg_lay.addLayout(_mod_row)

        # Ref image — prompt global (carré Casting style)
        _pg_ref_hdr = QHBoxLayout()
        _pg_ref_hdr.setContentsMargins(0, 8, 0, 4)
        _pg_ref_lbl = QLabel("Image de référence")
        _pg_ref_lbl.setStyleSheet(
            f"color:{C['text_dim']};font-size:10px;background:transparent;border:none;"
        )
        _pg_ref_hdr.addWidget(_pg_ref_lbl)
        _pg_ref_hdr.addStretch()
        _pg_lay.addLayout(_pg_ref_hdr)
        _pg_ref_row = QHBoxLayout()
        _pg_ref_row.setContentsMargins(0, 0, 0, 0)
        _pg_ref_row.setSpacing(8)
        self._global_ref_square = _RefSquare(tooltip="Image de référence globale (appliquée à tous les clips)")
        self._global_ref_square.picked.connect(lambda p: setattr(self, '_global_ref_image', p))
        self._global_ref_square.cleared.connect(lambda: setattr(self, '_global_ref_image', ''))
        _pg_ref_row.addWidget(self._global_ref_square)
        _pg_ref_row.addStretch()
        # Vignette du dessin Draw-to-Video (à droite) — confirme que le dessin est pris
        # en compte (croix pour le retirer). Non envoyé au modèle (lu par Claude Vision).
        self._draw_thumb_g_lbl = QLabel(translate("Dessin Draw-to-Video"))
        self._draw_thumb_g_lbl.setStyleSheet(
            f"color:{C['text_dim']};font-size:10px;background:transparent;border:none;")
        self._draw_thumb_g_lbl.setVisible(False)
        _pg_ref_row.addWidget(self._draw_thumb_g_lbl, 0, Qt.AlignmentFlag.AlignVCenter)
        self._draw_thumb_g = _DrawThumb()
        self._draw_thumb_g.removed.connect(self._on_clear_draw)
        _pg_ref_row.addWidget(self._draw_thumb_g)
        _pg_lay.addLayout(_pg_ref_row)
        body_prompt.addWidget(self._pg_frame)

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
        self._pc_scroll.setStyleSheet(
            f"QScrollArea{{background:transparent;border:none;}}"
            f"QScrollBar:horizontal{{background:{C['bg1']};height:4px;border-radius:2px;margin:0;}}"
            f"QScrollBar::handle:horizontal{{background:{C['border_bright']};border-radius:2px;min-width:30px;}}"
            f"QScrollBar::add-line:horizontal,QScrollBar::sub-line:horizontal{{width:0px;}}"
        )
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
        # « Améliorer le prompt » (☁) RETIRÉ — fonction jugée inutile/instable.
        self._btn_enhance_per_clip.setVisible(False)
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
        # Draw-to-Video — MÊME logo, MÊME emplacement que le prompt global : bouton
        # LOGO 60×60 à DROITE du rectangle de prompt (et plus dans l'en-tête).
        self._btn_draw_pc = QPushButton()
        self._btn_draw_pc.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_draw_pc.setToolTip(translate("Dessiner sur la vidéo") + " — " + translate(
            "Draw-to-Video : choisis un clip, dessine les zones de l'effet "
            "(feu, fumée…), puis génère — l'effet est appliqué là où tu as dessiné."))
        _pc_draw_pix = load_icon("draw_to_video.png", 56)
        if not _pc_draw_pix.isNull():
            self._btn_draw_pc.setIcon(QIcon(_pc_draw_pix))
            self._btn_draw_pc.setIconSize(QSize(56, 56))
            self._btn_draw_pc.setFixedSize(60, 60)
            self._btn_draw_pc.setStyleSheet(
                "QPushButton{background:transparent;border:none;border-radius:12px;padding:2px;}"
                "QPushButton:hover{background:rgba(78,205,196,0.14);}")
        else:
            self._btn_draw_pc.setText("✏  " + translate("Dessiner sur la vidéo"))
            self._btn_draw_pc.setFixedHeight(34)
            self._btn_draw_pc.setStyleSheet(
                f"QPushButton{{background:transparent;color:{C['accent']};"
                f"border:1px solid {C['accent']};border-radius:8px;font-size:11px;font-weight:700;padding:0 14px;}}"
                f"QPushButton:hover{{background:rgba(78,205,196,0.12);}}")
        self._btn_draw_pc.clicked.connect(self._on_draw_to_video)
        _pc_prompt_row = QHBoxLayout()
        _pc_prompt_row.setContentsMargins(0, 0, 0, 0)
        _pc_prompt_row.setSpacing(8)
        _pc_prompt_row.addWidget(self._per_clip_prompt, 1)
        _pc_prompt_row.addWidget(self._btn_draw_pc, 0, Qt.AlignmentFlag.AlignTop)
        _pc_lay.addLayout(_pc_prompt_row)

        # Ref image — prompt par clip (carré Casting style)
        _pc_ref_hdr = QHBoxLayout()
        _pc_ref_hdr.setContentsMargins(0, 8, 0, 4)
        _pc_ref_lbl = QLabel("Image de référence (ce clip)")
        _pc_ref_lbl.setStyleSheet(
            f"color:{C['text_dim']};font-size:10px;background:transparent;border:none;"
        )
        _pc_ref_hdr.addWidget(_pc_ref_lbl)
        _pc_ref_hdr.addStretch()
        _pc_lay.addLayout(_pc_ref_hdr)
        _pc_ref_row = QHBoxLayout()
        _pc_ref_row.setContentsMargins(0, 0, 0, 0)
        _pc_ref_row.setSpacing(8)
        self._per_clip_ref_square = _RefSquare(tooltip="Image de référence pour ce clip uniquement")
        self._per_clip_ref_square.picked.connect(self._on_per_clip_ref_picked)
        self._per_clip_ref_square.cleared.connect(self._on_per_clip_ref_cleared)
        _pc_ref_row.addWidget(self._per_clip_ref_square)
        _pc_ref_row.addStretch()
        self._draw_thumb_p_lbl = QLabel(translate("Dessin Draw-to-Video"))
        self._draw_thumb_p_lbl.setStyleSheet(
            f"color:{C['text_dim']};font-size:10px;background:transparent;border:none;")
        self._draw_thumb_p_lbl.setVisible(False)
        _pc_ref_row.addWidget(self._draw_thumb_p_lbl, 0, Qt.AlignmentFlag.AlignVCenter)
        self._draw_thumb_p = _DrawThumb()
        self._draw_thumb_p.removed.connect(self._on_clear_draw)
        _pc_ref_row.addWidget(self._draw_thumb_p)
        _pc_lay.addLayout(_pc_ref_row)
        _pp_outer.addWidget(_pc_frame)

        body_prompt.addWidget(self._per_clip_panel)

        lay.addWidget(sec_prompt)

        # ── RENDU & AUDIO (section repliable) ──────────────────────────────────
        from api.lipsync import ffmpeg_available as _ffmpeg_ok
        self._ra_container = QFrame()
        self._ra_container.setObjectName("ra_container")
        self._ra_container.setStyleSheet(
            f"QFrame#ra_container{{background:{C['bg2']};border:1px solid {C['border']};"
            f"border-radius:8px;}}")
        _ra_lay = QVBoxLayout(self._ra_container)
        _ra_lay.setContentsMargins(0, 0, 0, 0)
        _ra_lay.setSpacing(1)

        self._ra_open = False   # replié par défaut
        self._ra_toggle_btn = QPushButton("▶  RENDU & AUDIO")
        self._ra_toggle_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._ra_toggle_btn.setStyleSheet(
            f"QPushButton{{background:transparent;color:{C['accent']};border:none;"
            f"text-align:left;font-size:9px;letter-spacing:2px;"
            f"font-family:'Consolas',monospace;font-weight:700;padding:8px 14px 6px 14px;}}"
            f"QPushButton:hover{{color:{C['accent_dim']};}}")
        _ra_lay.addWidget(self._ra_toggle_btn)

        self._ra_body = QWidget()
        self._ra_body.setStyleSheet("background:transparent;border:none;")
        _ra_body_lay = QVBoxLayout(self._ra_body)
        _ra_body_lay.setContentsMargins(0, 0, 0, 0)
        _ra_body_lay.setSpacing(1)
        self._ra_body.setVisible(False)
        _ra_lay.addWidget(self._ra_body)

        def _toggle_ra(*_a):
            self._ra_open = not self._ra_open
            self._ra_body.setVisible(self._ra_open)
            self._ra_toggle_btn.setText(("▼" if self._ra_open else "▶") + "  RENDU & AUDIO")
        self._ra_toggle_btn.clicked.connect(_toggle_ra)

        # Options RENDU & AUDIO — mêmes que « Générer depuis le storyboard » (libellés
        # identiques → i18n partagée). Câblées dans _process_next (prompt + params).
        self._audio_toggle_row = toggle_row(
            "Audio natif", "Seedance génère le son ambiant et les effets sonores du clip", True)
        self._audio_cb = self._audio_toggle_row.findChild(QCheckBox)
        _ra_body_lay.addWidget(self._audio_toggle_row)

        self._music_toggle_row = toggle_row(
            "Musique générée",
            "Coché → piste musicale présente · Décoché → « no background music » injecté", False)
        self._music_cb = self._music_toggle_row.findChild(QCheckBox)
        _ra_body_lay.addWidget(self._music_toggle_row)

        self._subtitle_toggle_row = toggle_row(
            "Sous-titres",
            "Coché → sous-titres incrustés · Décoché → « no subtitles » injecté", False)
        self._subtitle_cb = self._subtitle_toggle_row.findChild(QCheckBox)
        _ra_body_lay.addWidget(self._subtitle_toggle_row)

        self._film_anchor_toggle_row = toggle_row(
            "Prise de vue réelle",
            "Ancre le rendu dans le filmage réel — ARRI 35mm, grain argentique, peau naturelle, no CGI, no 3D  ·  Automatiquement ignoré si le style 'Film réaliste' ou 'Photoréaliste' est actif (déjà inclus)",
            False)
        self._film_anchor_cb = self._film_anchor_toggle_row.findChild(QCheckBox)
        _ra_body_lay.addWidget(self._film_anchor_toggle_row)

        self._dyn_cam_toggle_row = toggle_row(
            "Caméra dynamique", "Changement d'angle toutes les 2 secondes", False)
        self._dyn_cam_cb = self._dyn_cam_toggle_row.findChild(QCheckBox)
        _ra_body_lay.addWidget(self._dyn_cam_toggle_row)

        # Resynchroniser les lèvres (LatentSync) — DANS le corps de RENDU & AUDIO.
        self._lipsync_toggle_row = toggle_row(
            "Resynchroniser les lèvres",
            "Synchronisation labiale LatentSync — ⚠ réencode (qualité moindre) + audio sur piste séparée",
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
                "⚠ Réencode via LatentSync → qualité moindre que le clip Seedance brut.\n"
                "Importe la vidéo lip-synced + la piste audio séparément dans DaVinci.\n"
                "Décoche pour garder le clip Seedance brut (un seul fichier, pleine qualité)."
            )
        _ra_body_lay.addWidget(self._lipsync_toggle_row)
        lay.addWidget(self._ra_container)

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
        _def_key = self._cb_model.currentData() or "seedance-2.0"
        _def_res = _ENGINE_RESOLUTIONS.get(_def_key, [("1080p", "1080p"), ("720p", "720p"), ("480p", "480p")])
        self._cb_res = combo(_def_res)

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
        self._btn_generate.clicked.connect(self._start_with_credit_check)

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
        # stretch=1 → le bouton prend toute la largeur disponible (aligné à gauche,
        # le « ×N » et Annuler restent à droite) au lieu de se réduire à son texte.
        btn_row.addWidget(self._btn_generate, 1)
        btn_row.addWidget(_x)
        btn_row.addWidget(self._spin_prises)
        btn_row.addWidget(self._btn_cancel)
        body_queue.addLayout(btn_row)

        # ── Ouvrir le dossier — pleine largeur, style « ghost » uniforme ; la
        #    barre DaVinci passe DESSOUS (comme Générer depuis Storyboard) ─────
        self._btn_open_folder = QPushButton(translate("Ouvrir le dossier des vidéos"))
        self._btn_open_folder.setFixedHeight(30)
        self._btn_open_folder.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_open_folder.setToolTip(translate("Ouvre le dossier de destination des clips."))
        self._btn_open_folder.setStyleSheet(
            f"QPushButton{{background:transparent;color:{C['text_secondary']};"
            f"border:1px solid {C['border']};border-radius:7px;"
            f"font-size:11px;font-weight:700;padding:0 14px;}}"
            f"QPushButton:hover{{background:{C['bg3']};color:{C['text_primary']};"
            f"border-color:{C['border_bright']};}}"
            f"QPushButton:pressed{{background:{C['bg3']};}}"
        )
        self._btn_open_folder.clicked.connect(self._open_output_folder)
        body_queue.addWidget(self._btn_open_folder)

        self._davinci_bar = _DaVinciBar()
        body_queue.addWidget(self._davinci_bar)
        lay.addWidget(sec_queue)

        # ── Encart prix (même que "Générer depuis Storyboard") ────────────────
        price_frame = QFrame()
        price_frame.setStyleSheet(
            f"QFrame{{background:rgba(245,197,24,0.05);"
            f"border:1px solid rgba(245,197,24,0.18);border-radius:8px;}}"
        )
        price_h = QHBoxLayout(price_frame)
        price_h.setContentsMargins(14, 8, 14, 8)
        price_h.setSpacing(12)
        price_lbl = QLabel(
            "💰  Génération facturée via fal.ai (Seedance 2.0)"
            "  ·  Tarifs détaillés dans le Manuel d'utilisation"
        )
        price_lbl.setWordWrap(True)
        price_lbl.setStyleSheet(
            f"color:{C['text_dim']};font-size:9px;"
            f"font-family:'Consolas',monospace;background:transparent;"
        )
        price_h.addWidget(price_lbl, 1)
        btn_tarifs = QPushButton("📖  Tarifs")
        btn_tarifs.setFixedSize(72, 24)
        btn_tarifs.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_tarifs.setStyleSheet(
            f"QPushButton{{background:transparent;color:{C['text_secondary']};"
            f"border:1px solid {C['border_bright']};border-radius:5px;"
            f"font-size:9px;font-weight:700;padding:0;}}"
            f"QPushButton:hover{{background:rgba(245,197,24,0.12);"
            f"color:#f5c518;border-color:rgba(245,197,24,0.50);}}"
        )
        btn_tarifs.clicked.connect(self._open_manual_tarifs)
        price_h.addWidget(btn_tarifs)
        lay.addWidget(price_frame)

        lay.addStretch()

    def _open_manual_tarifs(self):
        from ui.dialog_user_manual import UserManualDialog
        UserManualDialog(self.window(), start_section=13).exec()

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
        self._load_clips(clips)

    # ── Chargement des clips ──────────────────────────────────────────────────

    def _load_clips(self, clips: list):
        # Les images Draw-to-Video sont indexées par position : la liste de clips
        # change → on repart à zéro (indices obsolètes).
        self._draw_images = {}
        self._draw_overlays = {}
        self._draw_frames = {}
        # Durée de régénération calée sur le clip source (par index), réutilisée par
        # le lip-sync pour aligner l'audio sur la vidéo.
        self._gen_durations = {}
        # Déconnecte les workers de miniatures précédents pour éviter les callbacks périmés
        for w in self._thumb_workers:
            try:
                w.done.disconnect()
            except Exception:
                pass
        self._thumb_workers.clear()

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
            card.focused.connect(self._on_card_selected)
            if i > 0:
                sep = QFrame()
                sep.setFixedSize(1, ClipCard._TH_H)
                sep.setStyleSheet(f"background:{C['border']};")
                self._clips_hbox.addWidget(sep, 0, Qt.AlignmentFlag.AlignVCenter)
            self._clips_hbox.addWidget(card)
            self._clip_cards.append(card)

            # Extraction de la première frame si le clip est un fichier local
            fp = clip.get("file_path", "")
            if fp and os.path.isfile(fp):
                tw = _ThumbWorker(i, fp, self)
                tw.done.connect(self._on_thumb_ready)
                tw.start()
                self._thumb_workers.append(tw)

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

        # Tous les clips SÉLECTIONNÉS par défaut (contour lumineux) — « générer tout ».
        self._selected_clips = set(range(len(self._clip_cards)))
        self._sel_anchor = None
        for c in self._clip_cards:
            c.set_selected(True)

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

    def _on_thumb_ready(self, index: int, img):
        from PyQt6.QtGui import QImage  # noqa (type hint)
        pix = QPixmap.fromImage(img).scaled(
            ClipCard._TH_W, ClipCard._TH_H,
            Qt.AspectRatioMode.KeepAspectRatioByExpanding,
            Qt.TransformationMode.SmoothTransformation,
        )
        if index < len(self._clip_cards):
            self._clip_cards[index].set_thumb_pixmap(pix)
        pc_cards = self._get_pc_cards()
        if index < len(pc_cards):
            pc_cards[index].set_thumb_pixmap(pix)

    # ── Per-clip prompt ───────────────────────────────────────────────────────

    def _on_card_selected(self, idx: int):
        """Clic sur une vignette : sélection avec contour lumineux + Ctrl/Maj pour la
        multi-sélection (comme « Générer depuis Storyboard »). Le clip cliqué devient
        aussi l'actif (aperçu per-clip + cible du dessin)."""
        from PyQt6.QtWidgets import QApplication
        mods  = QApplication.keyboardModifiers()
        shift = bool(mods & Qt.KeyboardModifier.ShiftModifier)
        ctrl  = bool(mods & Qt.KeyboardModifier.ControlModifier)
        n = len(self._clip_cards)
        if shift and self._sel_anchor is not None and 0 <= self._sel_anchor < n:
            lo, hi = sorted((self._sel_anchor, idx))
            self._selected_clips |= set(range(lo, hi + 1))
        elif ctrl:
            if idx in self._selected_clips:
                self._selected_clips.discard(idx)
            else:
                self._selected_clips.add(idx)
            self._sel_anchor = idx
        else:
            self._selected_clips = {idx}
            self._sel_anchor = idx
        for i, card in enumerate(self._clip_cards):
            card.set_selected(i in self._selected_clips)
        self._on_card_focused(idx)          # actif (aperçu per-clip + dessin)
        self._update_seed_lock_default()

    def _on_card_focused(self, idx: int):
        # Sauvegarde le prompt du clip actif AVANT de changer (mode per-clip).
        if self._rb_per_clip.isChecked() and self._active_clip_idx is not None:
            self._per_clip_prompts[self._active_clip_idx] = (
                self._per_clip_prompt.toPlainText()
            )
        # Glow « actif » sur la carte du panneau per-clip (ancienne → nouvelle).
        pc_cards = self._get_pc_cards()
        if self._active_clip_idx is not None and self._active_clip_idx < len(pc_cards):
            pc_cards[self._active_clip_idx].set_active(False)
        # L'ACTIF est TOUJOURS mis à jour — nécessaire au dessin (Draw-to-Video),
        # même en mode prompt global (avant, l'actif restait None → dessin refusé).
        self._active_clip_idx = idx
        if idx < len(pc_cards):
            pc_cards[idx].set_active(True)
        if not self._rb_per_clip.isChecked():
            return
        # Mise à jour label + textarea (mode prompt per-clip)
        if idx < len(self._clip_cards):
            name = self._clip_cards[idx].clip().get("name", f"Clip {idx + 1}")
            self._per_clip_title.setText(f"▸  Prompt pour : {name}")
        self._per_clip_prompt.blockSignals(True)
        self._per_clip_prompt.setPlainText(self._per_clip_prompts.get(idx, ""))
        self._per_clip_prompt.blockSignals(False)
        self._refresh_per_clip_ref_ui(idx)

    def _refresh_per_clip_ref_ui(self, idx: int):
        ref = self._per_clip_ref_images.get(idx, "")
        self._per_clip_ref_square.set_path(ref)
        self._refresh_draw_thumb()

    def _refresh_draw_thumb(self):
        """Affiche/masque la vignette du dessin Draw-to-Video du clip ACTIF (les deux
        modes de prompt). Le dessin n'est jamais envoyé tel quel au modèle."""
        idx = self._active_clip_idx
        p = self._draw_images.get(idx, "") if idx is not None else ""
        for thumb, lbl in (
            (getattr(self, "_draw_thumb_g", None), getattr(self, "_draw_thumb_g_lbl", None)),
            (getattr(self, "_draw_thumb_p", None), getattr(self, "_draw_thumb_p_lbl", None)),
        ):
            if thumb is not None:
                thumb.set_image(p)
            if lbl is not None:
                lbl.setVisible(bool(p))

    def _on_clear_draw(self):
        """Croix de la vignette : retire le dessin Draw-to-Video du clip actif."""
        idx = self._active_clip_idx
        if idx is None:
            return
        self._draw_images.pop(idx, None)
        self._draw_overlays.pop(idx, None)
        self._draw_frames.pop(idx, None)
        self._refresh_draw_thumb()

    def _on_per_clip_prompt_changed(self):
        if self._active_clip_idx is not None:
            self._per_clip_prompts[self._active_clip_idx] = (
                self._per_clip_prompt.toPlainText()
            )

    # ── Import de fichiers vidéo ──────────────────────────────────────────────

    def _on_import_files(self):
        paths, _ = QFileDialog.getOpenFileNames(
            self,
            "Importer des fichiers vidéo",
            "",
            "Vidéos (*.mp4 *.mov *.avi *.mkv *.webm);;Tous les fichiers (*)",
        )
        if not paths:
            return
        new_clips = [
            {"name": os.path.splitext(os.path.basename(p))[0], "file_path": p}
            for p in paths
        ]
        self._load_clips(self._clips_data + new_clips)

    def add_clips_from_paths(self, paths: list[str]):
        """Ajoute des clips directement depuis la Vidéothèque (sans dialog)."""
        new_clips = [
            {"name": os.path.splitext(os.path.basename(p))[0], "file_path": p}
            for p in paths if os.path.isfile(p)
        ]
        if new_clips:
            self._load_clips(self._clips_data + new_clips)

    # ── Ref image — prompt global ─────────────────────────────────────────────
    # (géré par _global_ref_square.picked / cleared via lambda)

    # ── Ref image — prompt par clip ───────────────────────────────────────────

    def _on_per_clip_ref_picked(self, path: str):
        if self._active_clip_idx is not None:
            self._per_clip_ref_images[self._active_clip_idx] = path

    def _on_per_clip_ref_cleared(self):
        if self._active_clip_idx is not None:
            self._per_clip_ref_images.pop(self._active_clip_idx, None)

    # ── Draw-to-Video ─────────────────────────────────────────────────────────

    def _draw_dir(self) -> str:
        try:
            from core.context import get_data_root
            d = os.path.join(get_data_root(), "draw_to_video")
        except Exception:
            from core.pandora_dirs import get_bin_dir
            d = get_bin_dir("draw_to_video")
        os.makedirs(d, exist_ok=True)
        return d

    def _on_draw_to_video(self):
        idx = self._active_clip_idx
        if idx is None and len(self._clips_data) == 1:
            idx = 0
        if idx is None or idx >= len(self._clips_data):
            QMessageBox.information(
                self, "Draw-to-Video",
                "Sélectionne d'abord un clip (clique sur sa vignette).")
            return
        clip = self._clips_data[idx]
        path = clip.get("file_path", "")
        if not (path and os.path.isfile(path)):
            QMessageBox.warning(self, "Draw-to-Video", "Clip introuvable sur le disque.")
            return
        from ui.dialog_draw_video import DrawVideoDialog
        # Ré-édition : si ce clip a déjà un dessin, on le rouvre éditable (calque +
        # time code mémorisés) au lieu de repartir d'un schéma vierge.
        dlg = DrawVideoDialog(
            path, self._draw_dir(), self,
            prev_overlay=self._draw_overlays.get(idx, ""),
            prev_frame=self._draw_frames.get(idx, 0))
        if dlg.exec() == DrawVideoDialog.DialogCode.Accepted:
            rp = dlg.result_path()
            if rp and os.path.isfile(rp):
                self._draw_images[idx] = rp
                self._draw_overlays[idx] = dlg.overlay_path()
                self._draw_frames[idx] = dlg.frame_index()
                # Le clip dessiné devient ACTIF — sinon, en mono-clip non explicitement
                # sélectionné, `idx` venait du repli (=0) mais `_active_clip_idx` restait
                # None → la vignette (qui suit _active_clip_idx) ne s'affichait pas.
                self._active_clip_idx = idx
                # Plus de pop-up : la vignette du dessin (à droite du prompt) confirme
                # visuellement que l'opération est prise en compte.
                self._refresh_draw_thumb()

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
        self._pg_frame.setVisible(is_global)
        self._per_clip_panel.setVisible(not is_global)
        if not is_global and self._clip_cards and self._active_clip_idx is None:
            self._on_card_focused(0)

    # ── Sélection ─────────────────────────────────────────────────────────────

    def _set_all_checked(self, state: bool):
        # « Tout sélectionner » / « Tout désélectionner » (contour lumineux).
        self._selected_clips = set(range(len(self._clip_cards))) if state else set()
        self._sel_anchor = None
        for card in self._clip_cards:
            card.set_selected(state)
        self._update_seed_lock_default()

    def _clear_clips(self):
        self._load_clips([])

    # ── Template de style ─────────────────────────────────────────────────────

    def _set_style_ref_image(self, path: str):
        self._style_ref_path = path
        has = bool(path and os.path.isfile(path))
        if has:
            pix = QPixmap(path).scaled(
                152, 132,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            self._style_ref_thumb.setPixmap(pix)
        else:
            self._style_ref_thumb.setPixmap(QPixmap())
        self._style_ref_clear_btn.setVisible(has)

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
        self._style_key    = dlg._current_key
        style_entry = next((s for s in style_api.STYLES if s["key"] == self._style_key), None)
        self._style_suffix = style_entry.get("video_suffix", "") if style_entry else ""
        self._set_style_ref_image(chosen)

    def _on_style_ref_clear(self):
        self._style_key    = ""
        self._style_suffix = ""
        self._set_style_ref_image("")

    # ── Modèle / ratio ────────────────────────────────────────────────────────

    def _get_model(self) -> str:
        return self._cb_model.currentData() or "seedance-2.0"

    def _on_engine_changed(self):
        key = self._get_model()
        fixed_res = key in _FIXED_RES_ENGINES
        self._cb_ratio.setEnabled(key not in _FIXED_RATIO_ENGINES)
        options = _ENGINE_RESOLUTIONS.get(key, [("1080p", "1080p"), ("720p", "720p"), ("480p", "480p")])
        prev = self._cb_res.currentData() or self._cb_res.currentText()
        self._cb_res.blockSignals(True)
        self._cb_res.clear()
        for r in options:
            if isinstance(r, tuple):
                self._cb_res.addItem(r[0], r[1])
            else:
                self._cb_res.addItem(r, r)
        idx = self._cb_res.findData(prev)
        self._cb_res.setCurrentIndex(max(0, idx))
        self._cb_res.blockSignals(False)
        self._cb_res.setEnabled(not fixed_res)
        if hasattr(self, "_ref_compat_banner"):
            self._ref_compat_banner.setVisible(key in _TEXT_FALLBACK_ENGINES)

    def _get_aspect_ratio(self) -> str:
        return self._cb_ratio.currentText().split(" ")[0]

    # ── ADN visuel (seed) ─────────────────────────────────────────────────────

    def _update_seed_lock_default(self):
        """Coche le verrou ADN si plusieurs clips sont sélectionnés."""
        if len(self._selected_clips) > 1 and not self._seed_lock_btn.isChecked():
            self._seed_lock_btn.setChecked(True)

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

    # ── Credit guard (identique à T2V) ───────────────────────────────────────

    def _start_with_credit_check(self):
        from core.config import load_config as _lc
        if not _lc().get("api_key", "").strip():
            reply = QMessageBox.question(
                self,
                "Mode simulation — aucune clé fal.ai",
                "Aucune clé API fal.ai n'est configurée.\n\n"
                "La génération va tourner en mode simulation :\n"
                "les vidéos seront fictives et aucun fichier ne sera créé.\n\n"
                "Pour générer de vraies vidéos, ajoutez votre clé fal.ai\n"
                "dans Paramètres, puis relancez.\n\n"
                "Continuer en mode simulation ?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if reply != QMessageBox.StandardButton.Yes:
                return
        self._check_bridge_then_start()

    def _check_bridge_then_start(self):
        """Vérifie la connexion bridge puis lance la file si ok, sinon propose un dialog."""
        if not self._cb_import.isChecked():
            self._start_queue()
            return
        if self._bridge_connected:
            self._start_queue()
            return
        from PyQt6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton
        from PyQt6.QtCore import Qt as _Qt
        dlg = QDialog(self)
        dlg.setWindowTitle("Bridge non connecté")
        dlg.setMinimumWidth(500)
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
        btn_continue = QPushButton("Continuer")
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

        selected = [(i, card) for i, card in enumerate(self._clip_cards)
                    if i in self._selected_clips]
        if not selected:   # aucune sélection explicite → on prend tous les clips
            selected = list(enumerate(self._clip_cards))
        if not selected:
            QMessageBox.warning(self, "Aucun clip",
                                "Importez et sélectionnez au moins un clip avant de lancer la file.")
            return

        # Validation du format : H.264 720p, fichier < 50 MB
        invalid_clips = []
        for clip_idx, _card in selected:
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
                            if h > 1080:
                                invalid_clips.append(f"{name}  ({res})")
                    except (ValueError, IndexError):
                        pass
        if invalid_clips:
            QMessageBox.warning(
                self,
                "Format non supporté",
                "Pour le moment, seuls les clips exportés en H.264 1080p (ou inférieur) "
                "et inférieurs à 50 MB peuvent être envoyés à Seedance.\n\n"
                "Veuillez ré-exporter les clips suivants depuis DaVinci Resolve "
                "en H.264 1080p avant de relancer :\n\n"
                + "\n".join(f"  • {c}" for c in invalid_clips)
            )
            return

        # Info CONVERSION : prévenir quand un clip sera transcodé avant l'envoi
        # (format/codec non H.264, ou entrelacé → désentrelacé en progressif).
        will_transcode = []
        for clip_idx, _card in selected:
            fp = self._clips_data[clip_idx].get("file_path", "")
            try:
                from core.video_utils import video_needs_transcode
                why = video_needs_transcode(fp)
            except Exception:
                why = ""
            if why:
                nm = self._clips_data[clip_idx].get("name", f"Clip {clip_idx + 1}")
                will_transcode.append(f"  • {nm} — {why}")
        if will_transcode:
            resp = QMessageBox.question(
                self, translate("Conversion avant envoi"),
                translate("Ce(s) clip(s) seront convertis en H.264 PROGRESSIF (1080p max) "
                          "avant l'envoi au moteur — désentrelacés si besoin, pour éviter "
                          "les problèmes de trames :") + "\n\n"
                + "\n".join(will_transcode) + "\n\n"
                + translate("Pour la MEILLEURE qualité, exporte plutôt tes clips depuis ton "
                            "logiciel de montage en H.264 progressif, 1080p maximum — c'est le "
                            "format adapté à tous les moteurs de génération.") + "\n\n"
                + translate("Continuer avec la conversion automatique (FFmpeg) ?"),
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.Yes)
            if resp != QMessageBox.StandardButton.Yes:
                return

        # Sauvegarde le prompt per-clip courant avant de lancer
        if self._rb_per_clip.isChecked() and self._active_clip_idx is not None:
            self._per_clip_prompts[self._active_clip_idx] = (
                self._per_clip_prompt.toPlainText()
            )

        n_prises = self._spin_prises.value()
        self._queue = []
        for (clip_idx, _card) in selected:
            for p in range(n_prises):
                self._queue.append((clip_idx, p))

        self._queue_pos   = 0
        self._mock_count  = 0
        self._failed_clips = []

        # Seed fixé UNE SEULE FOIS pour toute la file si verrou activé
        if self._seed_lock_btn.isChecked():
            if not self._last_seed:
                import random
                self._last_seed = random.randint(1, 999_999_999)
        else:
            self._last_seed = None

        total = len(self._queue)
        n_clips = len(selected)
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

    def _on_mod_template(self, idx: int):
        """Insère le modèle de prompt « Type de modification » choisi dans le prompt
        global (action : le sélecteur revient ensuite sur l'invite). Non destructif :
        ajoute à la suite du texte existant. Balises Seedance @Video1/@Image1."""
        key = self._mod_combo.itemData(idx)
        if not key:
            return
        tpl = translate(_MOD_TEMPLATES.get(key, ""))
        if not tpl:
            return
        cur = self._prompt_global.toPlainText().strip()
        self._prompt_global.setPlainText((cur + "\n" + tpl) if cur else tpl)
        self._mod_combo.setCurrentIndex(0)

    def _source_gen_duration(self, clip_idx: int) -> int:
        """Durée de régénération Seedance calée sur le clip SOURCE (sondée par ffprobe,
        bornée 4–15 s — contrainte API). Repli 5 s si la durée est introuvable."""
        try:
            clip = self._clips_data[clip_idx]
            from core.video_utils import video_duration_s
            d = video_duration_s(clip.get("file_path", ""))
            if d and d > 0:
                return max(4, min(15, round(d)))
        except Exception:
            pass
        return 5

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

        # Draw-to-Video : l'image annotée (traits colorés) sert de GUIDE de repérage.
        # Elle n'est PAS envoyée à Seedance (sinon les traits seraient reproduits dans
        # la vidéo) : côté worker, Claude Vision la lit pour réécrire le prompt en
        # décrivant OÙ appliquer l'effet, puis seuls le clip d'origine + ce prompt
        # partent. → params["draw_guidance_path"] plus bas.
        _draw_img = self._draw_images.get(clip_idx, "")

        seed = self._get_seed()

        video_path = clip.get("file_path", "")
        has_video = bool(video_path and os.path.isfile(video_path))

        # Inject @Video1 so Seedance knows to reference the uploaded clip
        if has_video and "@Video1" not in prompt:
            prompt = f"@Video1 {prompt}" if prompt else "@Video1"

        # ── RENDU & AUDIO : injections de prompt (mêmes options que le storyboard) ─
        if getattr(self, "_dyn_cam_cb", None) and self._dyn_cam_cb.isChecked():
            prompt = (f"{prompt}, change the camera angle every 2 seconds "
                      "alternating between several types of shots")
        if getattr(self, "_film_anchor_cb", None) and self._film_anchor_cb.isChecked():
            import core.style as _style_api
            if _style_api.get_style_key() not in {"realistic"}:   # déjà inclus si réaliste
                prompt = (f"{prompt}, shot on ARRI Alexa 35mm film, photorealistic live action footage, "
                          "real human actors, authentic film grain, natural skin texture and pores, "
                          "no CGI, no 3D render, no computer animation, no digital art, "
                          "organic depth of field, natural practical lighting")
        if getattr(self, "_subtitle_cb", None) and not self._subtitle_cb.isChecked():
            prompt = f"{prompt}, no subtitles"

        # Durée calée sur le clip SOURCE (Seedance n'accepte que 4–15 s) → la version
        # régénérée respecte la longueur de l'original au lieu d'un 5 s figé.
        gen_dur = self._source_gen_duration(clip_idx)
        self._gen_durations[clip_idx] = gen_dur

        params = {
            "mode":         "ext" if has_video else "t2v",
            "direction":    "new_take",
            "prompt":       prompt,
            "model":        self._get_model(),
            "duration":     gen_dur,
            # RENDU & AUDIO : son natif + « no music » (suffixe ajouté après traduction)
            "audio":        (self._audio_cb.isChecked()
                             if getattr(self, "_audio_cb", None) else True),
            "no_music_suffix": ("" if (getattr(self, "_music_cb", None)
                                       and self._music_cb.isChecked())
                                else "no music, no background music, no soundtrack, "
                                     "no musical score, natural ambient sound only"),
            "resolution":   (self._cb_res.currentData() or self._cb_res.currentText().split()[0]),
            "aspect_ratio": self._get_aspect_ratio(),
        }
        if has_video:
            params["video_path"] = video_path
        if seed:
            params["seed"] = seed
        # Draw-to-Video : image annotée transmise comme GUIDE (analysée par Claude
        # Vision côté worker), JAMAIS uploadée comme référence à Seedance.
        if _draw_img and os.path.isfile(_draw_img):
            params["draw_guidance_path"] = _draw_img

        ref_images = []
        if self._global_ref_image and os.path.isfile(self._global_ref_image):
            ref_images.append(self._global_ref_image)
        per_ref = self._per_clip_ref_images.get(clip_idx, "")
        if per_ref and os.path.isfile(per_ref) and per_ref not in ref_images:
            ref_images.append(per_ref)
        # NB : l'image annotée Draw-to-Video N'EST PAS ajoutée aux références
        # (elle partirait sinon à Seedance → traits visibles). Elle est passée via
        # params["draw_guidance_path"] et analysée par Claude Vision côté worker.
        if ref_images:
            params["ref_images"] = ref_images

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
            # Cale l'audio sur la durée EXACTE de la vidéo régénérée (= durée du clip
            # source, bornée 4–15 s) → son et image synchrones, durée de sortie nette.
            target_duration   = self._gen_durations.get(clip_idx, 0.0),
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
            self._mock_count += 1
            card.set_status(f"P{prise_idx + 1}/{n_pr} ✓ (simulation)", C["green"])
        elif ir.get("success"):
            local_path = ir.get("local_path", "")
            if ir.get("davinci_imported"):
                card.set_status(f"P{prise_idx + 1}/{n_pr} ✓ → DaVinci", C["green"])
            else:
                card.set_status(f"P{prise_idx + 1}/{n_pr} ✓ sauvegardé", C["green"])
            if local_path:
                card.setToolTip(f"Fichier : {local_path}")
        else:
            err = ir.get("error", "erreur inconnue")
            card.set_status(f"P{prise_idx + 1}/{n_pr} ✗ {err[:40]}", C["red"])
            self._failed_clips.append((clip_idx, err))

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

    @staticmethod
    def _humanize_error(error: str) -> str:
        e = error.lower()
        is_validation = any(k in e for k in ("'loc'", '"loc"', "[{", "unprocessable", "422"))
        if is_validation:
            if any(k in e for k in ("duration", "too short", "minimum", "length", "second")):
                return "Durée du clip trop courte"
            return "Clip refusé par Seedance (durée trop courte ?)"
        if "401" in e or "403" in e or "unauthorized" in e or "forbidden" in e:
            return "Clé API invalide ou expirée"
        if "timeout" in e or "timed out" in e:
            return "Délai d'attente dépassé"
        if "connection" in e or "connexion" in e:
            return "Erreur de connexion réseau"
        return error[:80] if error else "erreur inconnue"

    def _on_clip_failed(self, error: str, clip_idx: int, prise_idx: int):
        card = self._clip_cards[clip_idx]
        n_pr = self._spin_prises.value()
        short_err = self._humanize_error(error)
        card.set_status(f"P{prise_idx + 1}/{n_pr} ✗ {short_err}", C["red"])
        self._failed_clips.append((clip_idx, error))
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
                abandon_thread(self._worker)
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
        self._lbl_lipsync_stage.setVisible(False)
        total = len(self._queue)
        self._lbl_queue_info.setText(f"File terminée — {total} génération(s) complétée(s).")
        self._progress.setValue(100)
        self._lbl_progress.setText("")
        if self._failed_clips:
            clip_names = []
            for ci, err in self._failed_clips:
                name = self._clips_data[ci].get("name", f"Clip {ci + 1}") if ci < len(self._clips_data) else f"Clip {ci + 1}"
                clip_names.append(f"  • {name} : {err}")
            QMessageBox.warning(
                self,
                f"{len(self._failed_clips)} génération(s) échouée(s)",
                f"{len(self._failed_clips)} clip(s) n'ont pas pu être générés :\n\n"
                + "\n".join(clip_names),
            )
        elif self._mock_count > 0:
            QMessageBox.warning(
                self,
                "Simulation — aucun fichier créé",
                f"{self._mock_count} génération(s) sur {total} étaient des simulations.\n\n"
                "Aucune vraie vidéo n'a été créée ni sauvegardée.\n\n"
                "Pour générer de vraies vidéos :\n"
                "  • Configurez votre clé fal.ai dans Paramètres\n"
                "  • Rechargez votre compte sur fal.ai/dashboard si nécessaire",
            )
