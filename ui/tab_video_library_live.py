"""
ui/tab_video_library_live.py — Vidéothèque dédiée à PANDORA | Live.

Variante Live de la Vidéothèque : galerie des loops/vidéos générés, avec pour
chaque clip trois actions :
  ▶ Lire        — ouvre dans le lecteur par défaut
  ⤷ Modifier    — envoie le clip vers l'onglet « Modifier » (Live)
  → Resolume    — bascule vers l'onglet Resolume pour le charger dans un slot

Aucune dépendance DaVinci (contrairement à la Vidéothèque de Cinéma).
Réutilise le worker de miniatures de ui/tab_video_library.py.
"""

import os
from datetime import datetime

from PyQt6.QtCore import Qt, QUrl, pyqtSignal
from PyQt6.QtGui import QColor, QDesktopServices, QPixmap
from PyQt6.QtWidgets import (
    QComboBox, QFrame, QGridLayout, QHBoxLayout, QLabel,
    QPushButton, QScrollArea, QVBoxLayout, QWidget,
)

from ui.styles import C
from ui.widgets import HelpBlock
from core.i18n import translate
from ui.tab_video_library import _LibThumbWorker, _VIDEO_EXTS

_COLS = 4


def scan_live_clips() -> list:
    """Tous les clips vidéo du projet Live (Seedance, upscalés, sonorisés,
    dossier de sortie). Source UNIQUE — partagée avec le contrôleur Resolume."""
    import core.context as ctx
    import core.config as cfg
    dirs_to_scan: list[str] = []
    data_root   = ctx.get_data_root()
    project_dir = cfg.project_video_dir()
    if os.path.isdir(project_dir):
        dirs_to_scan.append(project_dir)
    # Sorties des onglets Upscaling et Sound Design (vidéos sonorisées)
    for sub in ("upscaled", "live_sound_design"):
        d = os.path.join(data_root, sub)
        if os.path.isdir(d):
            dirs_to_scan.append(d)
    output_dir = cfg.get_output_dir()
    if output_dir and os.path.isdir(output_dir):
        _norm = {os.path.normpath(x) for x in dirs_to_scan}
        if os.path.normpath(output_dir) not in _norm:
            dirs_to_scan.append(output_dir)

    paths: list[str] = []
    seen: set[str] = set()
    for d in dirs_to_scan:
        try:
            for fname in sorted(os.listdir(d)):
                if os.path.splitext(fname)[1].lower() not in _VIDEO_EXTS:
                    continue
                full = os.path.normpath(os.path.join(d, fname))
                if full not in seen and os.path.isfile(full):
                    seen.add(full)
                    paths.append(full)
        except OSError:
            pass
    return paths


# ── Carte vidéo Live ────────────────────────────────────────────────────────

class _LiveVideoCard(QFrame):
    play_requested     = pyqtSignal(str)
    modify_requested   = pyqtSignal(str)
    resolume_requested = pyqtSignal(str)
    upscale_requested  = pyqtSignal(str)

    _TH_W = 160
    _TH_H = 90

    def __init__(self, path: str, parent=None):
        super().__init__(parent)
        self._path = path
        self.setFixedWidth(180)
        self.setStyleSheet(
            f"QFrame{{background:{C['bg2']};border:1px solid {C['border']};border-radius:8px;}}"
            f"QFrame:hover{{border-color:{C['border_bright']};}}"
        )

        lay = QVBoxLayout(self)
        lay.setContentsMargins(8, 8, 8, 8)
        lay.setSpacing(4)

        self._thumb = QLabel()
        self._thumb.setFixedSize(self._TH_W, self._TH_H)
        self._thumb.setAlignment(Qt.AlignmentFlag.AlignCenter)
        ph = QPixmap(self._TH_W, self._TH_H)
        ph.fill(QColor(C["bg3"]))
        self._thumb.setPixmap(ph)
        self._thumb.setStyleSheet("border-radius:4px;border:none;background:transparent;")
        lay.addWidget(self._thumb, 0, Qt.AlignmentFlag.AlignCenter)

        name    = os.path.splitext(os.path.basename(path))[0]
        display = name if len(name) <= 22 else name[:21] + "…"
        lbl_name = QLabel(display)
        lbl_name.setToolTip(name)
        lbl_name.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl_name.setStyleSheet(
            f"color:{C['text_primary']};font-size:9px;font-weight:600;"
            f"background:transparent;border:none;"
        )
        lay.addWidget(lbl_name)

        try:
            mtime    = os.path.getmtime(path)
            date_str = datetime.fromtimestamp(mtime).strftime("%d/%m  %H:%M")
            size_mb  = os.path.getsize(path) / 1_000_000
            meta     = f"{date_str}  ·  {size_mb:.1f} Mo"
        except OSError:
            meta = "—"
        lbl_meta = QLabel(meta)
        lbl_meta.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl_meta.setStyleSheet(
            f"color:{C['text_dim']};font-size:8px;font-family:'Consolas',monospace;"
            f"background:transparent;border:none;"
        )
        lay.addWidget(lbl_meta)

        _ss_base = (
            f"QPushButton{{background:{C['bg3']};color:{C['text_secondary']};"
            f"border:1px solid {C['border']};border-radius:4px;"
            f"font-size:9px;font-weight:600;padding:3px 4px;}}"
            f"QPushButton:hover{{background:{C['bg2']};"
            f"border-color:{C['border_bright']};color:{C['text_primary']};}}"
        )
        _ss_accent = (
            f"QPushButton{{background:rgba(78,205,196,0.08);color:{C['accent']};"
            f"border:1px solid {C['accent_dim']};border-radius:4px;"
            f"font-size:9px;font-weight:700;padding:3px 4px;}}"
            f"QPushButton:hover{{background:rgba(78,205,196,0.18);border-color:{C['accent']};}}"
        )
        _ss_violet = (
            f"QPushButton{{background:rgba(124,107,255,0.10);color:{C['accent']};"
            f"border:1px solid rgba(124,107,255,0.45);border-radius:4px;"
            f"font-size:9px;font-weight:700;padding:3px 4px;}}"
            f"QPushButton:hover{{background:rgba(124,107,255,0.20);border-color:{C['accent']};}}"
        )

        row1 = QHBoxLayout()
        row1.setContentsMargins(0, 2, 0, 0)
        row1.setSpacing(4)
        btn_play = QPushButton("▶  " + translate("Lire"))
        btn_play.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_play.setStyleSheet(_ss_base)
        btn_play.clicked.connect(lambda: self.play_requested.emit(self._path))
        row1.addWidget(btn_play)
        btn_mod = QPushButton("⤷ " + translate("Modifier"))
        btn_mod.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_mod.setToolTip(translate("Envoyer vers l'onglet Modifier (Live)"))
        btn_mod.setStyleSheet(_ss_accent)
        btn_mod.clicked.connect(lambda: self.modify_requested.emit(self._path))
        row1.addWidget(btn_mod)
        lay.addLayout(row1)

        row2 = QHBoxLayout()
        row2.setContentsMargins(0, 0, 0, 0)
        row2.setSpacing(4)
        btn_res = QPushButton("→ Resolume")
        btn_res.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_res.setToolTip(translate("Charger ce clip dans Resolume"))
        btn_res.setStyleSheet(_ss_violet)
        btn_res.clicked.connect(lambda: self.resolume_requested.emit(self._path))
        row2.addWidget(btn_res)
        btn_up = QPushButton("⇪ " + translate("Upscale"))
        btn_up.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_up.setToolTip(translate("Envoyer vers l'onglet Upscaling (Live)"))
        btn_up.setStyleSheet(_ss_accent)
        btn_up.clicked.connect(lambda: self.upscale_requested.emit(self._path))
        row2.addWidget(btn_up)
        lay.addLayout(row2)

    def set_thumb_pixmap(self, pix: QPixmap):
        self._thumb.setPixmap(pix)


# ── Onglet Vidéothèque Live ─────────────────────────────────────────────────

class TabVideoLibraryLive(QScrollArea):
    send_to_modify   = pyqtSignal(list)  # list[str]
    send_to_resolume = pyqtSignal(list)  # list[str]
    send_to_upscale  = pyqtSignal(list)  # list[str]

    _SORT_OPTIONS = [
        ("Date (récent → ancien)",   "date_desc"),
        ("Date (ancien → récent)",   "date_asc"),
        ("Nom (A → Z)",              "name_asc"),
        ("Taille (grande → petite)", "size_desc"),
    ]

    def __init__(self):
        super().__init__()
        self.setWidgetResizable(True)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        self._cards: dict[str, _LiveVideoCard] = {}
        self._thumb_workers: list = []
        self._sort_key = "date_desc"

        container = QWidget()
        self.setWidget(container)
        lay = QVBoxLayout(container)
        lay.setContentsMargins(20, 20, 20, 20)
        lay.setSpacing(14)

        lay.addWidget(HelpBlock(translate("Vidéothèque Live — loops & vidéos générés"), [
            translate("▸ Retrouvez ici tous les loops et vidéos générés pour ce live."),
            translate("▸ ▶ Lire ouvre la vidéo dans votre lecteur par défaut."),
            translate("▸ ⤷ Modifier envoie le clip vers l'onglet « Modifier »."),
            translate("▸ → Resolume bascule vers l'onglet Resolume pour le charger dans un slot."),
        ], C))

        top_bar = QHBoxLayout()
        top_bar.setSpacing(8)
        lbl_sort = QLabel(translate("Tri :"))
        lbl_sort.setStyleSheet(
            f"color:{C['text_secondary']};font-size:11px;background:transparent;border:none;"
        )
        top_bar.addWidget(lbl_sort)
        self._sort_combo = QComboBox()
        self._sort_combo.setFixedHeight(28)
        for label, key in self._SORT_OPTIONS:
            self._sort_combo.addItem(translate(label), key)
        self._sort_combo.setStyleSheet(
            f"QComboBox{{background:{C['bg2']};border:1px solid {C['border']};"
            f"border-radius:5px;color:{C['text_primary']};font-size:11px;"
            f"padding:3px 8px;min-height:0;}}"
            f"QComboBox::drop-down{{border:none;width:18px;}}"
            f"QComboBox QAbstractItemView{{background:{C['bg3']};"
            f"border:1px solid {C['border_bright']};color:{C['text_primary']};"
            f"selection-background-color:{C['accent_dim']};}}"
        )
        self._sort_combo.currentIndexChanged.connect(self._on_sort_changed)
        top_bar.addWidget(self._sort_combo)
        top_bar.addStretch()

        btn_refresh = QPushButton("↻  " + translate("Actualiser"))
        btn_refresh.setFixedHeight(28)
        btn_refresh.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_refresh.setStyleSheet(
            f"QPushButton{{background:transparent;color:{C['text_dim']};"
            f"border:1px solid {C['border']};border-radius:5px;font-size:10px;padding:0 10px;}}"
            f"QPushButton:hover{{color:{C['text_primary']};border-color:{C['border_bright']};}}"
        )
        btn_refresh.clicked.connect(self.refresh)
        top_bar.addWidget(btn_refresh)

        self._btn_folder = QPushButton("📁  " + translate("Ouvrir le dossier"))
        self._btn_folder.setFixedHeight(28)
        self._btn_folder.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_folder.setStyleSheet(
            f"QPushButton{{background:transparent;color:{C['accent']};"
            f"border:1px solid {C['accent_dim']};border-radius:5px;"
            f"font-size:10px;font-weight:600;padding:0 12px;}}"
            f"QPushButton:hover{{background:rgba(78,205,196,0.10);}}"
        )
        self._btn_folder.clicked.connect(self._open_output_folder)
        top_bar.addWidget(self._btn_folder)
        lay.addLayout(top_bar)

        self._lbl_count = QLabel()
        self._lbl_count.setStyleSheet(
            f"color:{C['text_secondary']};font-size:11px;background:transparent;border:none;"
        )
        lay.addWidget(self._lbl_count)

        self._grid_widget = QWidget()
        self._grid_widget.setStyleSheet("background:transparent;")
        self._grid = QGridLayout(self._grid_widget)
        self._grid.setContentsMargins(0, 0, 0, 0)
        self._grid.setSpacing(12)
        self._grid.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        lay.addWidget(self._grid_widget)

        self._lbl_empty = QLabel(translate(
            "Aucune vidéo générée pour ce live.\n"
            "Lancez une génération depuis « Génération directe »."
        ))
        self._lbl_empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._lbl_empty.setStyleSheet(f"color:{C['text_dim']};font-size:12px;padding:40px;")
        lay.addWidget(self._lbl_empty)
        lay.addStretch()

        self.refresh()

    # ── Refresh / scan ──────────────────────────────────────────────────────

    def list_all_clips(self) -> list:
        """Tous les chemins de clips de la Vidéothèque (pour l'onglet Upscaling)."""
        try:
            return list(self._scan_videos())
        except Exception:
            return []

    def refresh(self):
        for w in self._thumb_workers:
            try:
                w.done.disconnect()
            except Exception:
                pass
        self._thumb_workers.clear()
        self._cards.clear()
        while self._grid.count():
            item = self._grid.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        paths = self._scan_videos()
        if not paths:
            self._lbl_count.setText("")
            self._lbl_empty.setVisible(True)
            self._grid_widget.setVisible(False)
            return

        n = len(paths)
        self._lbl_count.setText(f"{n} " + translate("vidéo(s)"))
        self._lbl_empty.setVisible(False)
        self._grid_widget.setVisible(True)

        for i, path in enumerate(paths):
            card = _LiveVideoCard(path)
            card.play_requested.connect(self._on_play)
            card.modify_requested.connect(lambda p: self.send_to_modify.emit([p]))
            card.resolume_requested.connect(lambda p: self.send_to_resolume.emit([p]))
            card.upscale_requested.connect(lambda p: self.send_to_upscale.emit([p]))
            self._cards[path] = card
            row, col = divmod(i, _COLS)
            self._grid.addWidget(card, row, col)

            tw = _LibThumbWorker(path, self)
            tw.done.connect(self._on_thumb_ready)
            tw.start()
            self._thumb_workers.append(tw)

    def _scan_videos(self) -> list[str]:
        return self._sort_paths(scan_live_clips())

    def _sort_paths(self, paths: list[str]) -> list[str]:
        k = self._sort_key
        def _mtime(p):
            try: return os.path.getmtime(p)
            except OSError: return 0
        def _size(p):
            try: return os.path.getsize(p)
            except OSError: return 0
        if k == "date_desc": return sorted(paths, key=_mtime, reverse=True)
        if k == "date_asc":  return sorted(paths, key=_mtime)
        if k == "name_asc":  return sorted(paths, key=lambda p: os.path.basename(p).lower())
        if k == "size_desc": return sorted(paths, key=_size, reverse=True)
        return paths

    def _get_output_dir(self) -> str:
        import core.config as cfg
        output_dir = cfg.get_output_dir()
        if output_dir and os.path.isdir(output_dir):
            return output_dir
        return cfg.project_video_dir()

    # ── Slots ───────────────────────────────────────────────────────────────

    def _on_sort_changed(self):
        self._sort_key = self._sort_combo.currentData()
        self.refresh()

    def _on_thumb_ready(self, path: str, img):
        pix = QPixmap.fromImage(img).scaled(
            _LiveVideoCard._TH_W, _LiveVideoCard._TH_H,
            Qt.AspectRatioMode.KeepAspectRatioByExpanding,
            Qt.TransformationMode.SmoothTransformation,
        )
        if path in self._cards:
            self._cards[path].set_thumb_pixmap(pix)

    def _on_play(self, path: str):
        QDesktopServices.openUrl(QUrl.fromLocalFile(path))

    def _open_output_folder(self):
        folder = self._get_output_dir()
        os.makedirs(folder, exist_ok=True)
        QDesktopServices.openUrl(QUrl.fromLocalFile(folder))
