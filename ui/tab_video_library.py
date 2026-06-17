"""Vidéothèque — bibliothèque de toutes les vidéos générées pour le projet."""

import os
from datetime import datetime

from PyQt6.QtCore import Qt, QThread, QUrl, pyqtSignal
from PyQt6.QtGui import QColor, QDesktopServices, QImage, QPixmap
from PyQt6.QtWidgets import (
    QComboBox, QFrame, QGridLayout, QHBoxLayout, QLabel,
    QPushButton, QScrollArea, QVBoxLayout, QWidget,
)

from ui.styles import C
from ui.widgets import HelpBlock

_VIDEO_EXTS = {".mp4", ".mov", ".avi", ".mkv", ".webm"}
_COLS = 4


# ── Worker extraction première frame ─────────────────────────────────────────

class _LibThumbWorker(QThread):
    done   = pyqtSignal(str, object)  # path, QImage
    failed = pyqtSignal(str)          # path — extraction impossible

    def __init__(self, path: str, parent=None):
        super().__init__(parent)
        self._path = path

    def run(self):
        from core.video_utils import extract_first_frame, get_thumb_cache_path
        cache_path = get_thumb_cache_path(self._path)
        try:
            if not os.path.isfile(cache_path):
                ok = extract_first_frame(self._path, cache_path)
                if not ok:
                    self.failed.emit(self._path)
                    return
            img = QImage(cache_path)
            if img.isNull():
                self.failed.emit(self._path)
                return
            self.done.emit(self._path, img)
        except Exception:
            self.failed.emit(self._path)


# ── Carte vidéo ───────────────────────────────────────────────────────────────

class _VideoCard(QFrame):
    play_requested = pyqtSignal(str)
    edit_requested = pyqtSignal(str)

    _TH_W = 160
    _TH_H = 90

    def __init__(self, path: str, parent=None):
        super().__init__(parent)
        self._path = path

        self.setFixedWidth(180)
        self.setStyleSheet(
            f"QFrame{{background:{C['bg2']};border:1px solid {C['border']};"
            f"border-radius:8px;}}"
            f"QFrame:hover{{border-color:{C['border_bright']};}}"
        )

        lay = QVBoxLayout(self)
        lay.setContentsMargins(8, 8, 8, 8)
        lay.setSpacing(4)

        # Vignette (placeholder gris foncé)
        self._thumb = QLabel()
        self._thumb.setFixedSize(self._TH_W, self._TH_H)
        self._thumb.setAlignment(Qt.AlignmentFlag.AlignCenter)
        ph = QPixmap(self._TH_W, self._TH_H)
        ph.fill(QColor(C["bg3"]))
        self._thumb.setPixmap(ph)
        self._thumb.setStyleSheet("border-radius:4px;border:none;background:transparent;")
        lay.addWidget(self._thumb, 0, Qt.AlignmentFlag.AlignCenter)

        # Nom de fichier
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

        # Date + taille
        try:
            mtime    = os.path.getmtime(path)
            date_str = datetime.fromtimestamp(mtime).strftime("%d/%m  %H:%M")
            size_mb  = os.path.getsize(path) / 1_000_000
            size_str = f"{size_mb:.1f} Mo"
        except OSError:
            date_str = "—"
            size_str = "—"

        lbl_meta = QLabel(f"{date_str}  ·  {size_str}")
        lbl_meta.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl_meta.setStyleSheet(
            f"color:{C['text_dim']};font-size:8px;font-family:'Consolas',monospace;"
            f"background:transparent;border:none;"
        )
        lay.addWidget(lbl_meta)

        # Boutons
        _ss_base = (
            f"QPushButton{{background:{C['bg3']};color:{C['text_secondary']};"
            f"border:1px solid {C['border']};border-radius:4px;"
            f"font-size:9px;font-weight:600;padding:3px 6px;}}"
            f"QPushButton:hover{{background:{C['bg2']};"
            f"border-color:{C['border_bright']};color:{C['text_primary']};}}"
        )
        _ss_edit = (
            f"QPushButton{{background:rgba(78,205,196,0.08);color:{C['accent']};"
            f"border:1px solid {C['accent_dim']};border-radius:4px;"
            f"font-size:9px;font-weight:700;padding:3px 6px;}}"
            f"QPushButton:hover{{background:rgba(78,205,196,0.18);"
            f"border-color:{C['accent']};}}"
        )

        btn_row = QHBoxLayout()
        btn_row.setContentsMargins(0, 2, 0, 0)
        btn_row.setSpacing(4)

        btn_play = QPushButton("▶  Lire")
        btn_play.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_play.setStyleSheet(_ss_base)
        btn_play.clicked.connect(lambda: self.play_requested.emit(self._path))
        btn_row.addWidget(btn_play)

        btn_edit = QPushButton("⤷ Modifier")
        btn_edit.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_edit.setToolTip("Envoyer vers « Modifier depuis DaVinci Resolve »")
        btn_edit.setStyleSheet(_ss_edit)
        btn_edit.clicked.connect(lambda: self.edit_requested.emit(self._path))
        btn_row.addWidget(btn_edit)

        lay.addLayout(btn_row)

    def set_thumb_pixmap(self, pix: QPixmap):
        self._thumb.setPixmap(pix)


# ── Onglet principal ──────────────────────────────────────────────────────────

class TabVideoLibrary(QScrollArea):
    send_to_davinci_edit = pyqtSignal(list)  # list[str]

    _SORT_OPTIONS = [
        ("Date (récent → ancien)",    "date_desc"),
        ("Date (ancien → récent)",    "date_asc"),
        ("Nom (A → Z)",               "name_asc"),
        ("Taille (grande → petite)",  "size_desc"),
    ]

    def __init__(self):
        super().__init__()
        self.setWidgetResizable(True)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        self._cards:         dict[str, _VideoCard]   = {}
        self._thumb_workers: list[_LibThumbWorker]   = []
        self._sort_key = "date_desc"

        container = QWidget()
        self.setWidget(container)
        lay = QVBoxLayout(container)
        lay.setContentsMargins(20, 20, 20, 20)
        lay.setSpacing(14)

        lay.addWidget(HelpBlock("Vidéothèque — bibliothèque des vidéos générées", [
            "▸ Retrouvez ici toutes les vidéos générées pour ce projet.",
            "▸ Cliquez sur ▶ Lire pour ouvrir dans votre lecteur vidéo par défaut.",
            "▸ Cliquez sur ⤷ Modifier pour envoyer vers « Modifier depuis DaVinci Resolve ».",
            "▸ Le bouton 📁 ouvre directement le dossier de destination dans l'explorateur.",
        ], C))

        # ── Barre de contrôle ────────────────────────────────────────────────
        top_bar = QHBoxLayout()
        top_bar.setSpacing(8)

        lbl_sort = QLabel("Tri :")
        lbl_sort.setStyleSheet(
            f"color:{C['text_secondary']};font-size:11px;background:transparent;border:none;"
        )
        top_bar.addWidget(lbl_sort)

        self._sort_combo = QComboBox()
        self._sort_combo.setFixedHeight(28)
        for label, key in self._SORT_OPTIONS:
            self._sort_combo.addItem(label, key)
        self._sort_combo.setStyleSheet(
            f"QComboBox{{background:{C['bg2']};border:1px solid {C['border']};"
            f"border-radius:5px;color:{C['text_primary']};font-size:11px;"
            f"padding:3px 8px;min-height:0;}}"
            f"QComboBox::drop-down{{border:none;width:18px;}}"
            f"QComboBox::down-arrow{{border-left:3px solid transparent;"
            f"border-right:3px solid transparent;"
            f"border-top:4px solid {C['text_dim']};margin-right:6px;}}"
            f"QComboBox QAbstractItemView{{background:{C['bg3']};"
            f"border:1px solid {C['border_bright']};color:{C['text_primary']};"
            f"selection-background-color:{C['accent_dim']};}}"
        )
        self._sort_combo.currentIndexChanged.connect(self._on_sort_changed)
        top_bar.addWidget(self._sort_combo)
        top_bar.addStretch()

        _btn_ss = (
            f"QPushButton{{background:transparent;color:{C['text_dim']};"
            f"border:1px solid {C['border']};border-radius:5px;"
            f"font-size:10px;padding:0 10px;}}"
            f"QPushButton:hover{{color:{C['text_primary']};border-color:{C['border_bright']};}}"
        )

        btn_refresh = QPushButton("↻  Actualiser")
        btn_refresh.setFixedHeight(28)
        btn_refresh.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_refresh.setStyleSheet(_btn_ss)
        btn_refresh.clicked.connect(self.refresh)
        top_bar.addWidget(btn_refresh)

        self._btn_diag = QPushButton("⚠  Diagnostic miniatures")
        self._btn_diag.setFixedHeight(28)
        self._btn_diag.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_diag.setToolTip("Ouvrir le log d'erreurs d'extraction dans le Bloc-notes")
        self._btn_diag.setStyleSheet(
            f"QPushButton{{background:transparent;color:#c8a400;"
            f"border:1px solid rgba(200,164,0,0.35);border-radius:5px;"
            f"font-size:10px;padding:0 10px;}}"
            f"QPushButton:hover{{background:rgba(245,197,24,0.10);"
            f"border-color:rgba(245,197,24,0.60);}}"
        )
        self._btn_diag.setVisible(False)
        self._btn_diag.clicked.connect(self._open_diag_log)
        top_bar.addWidget(self._btn_diag)

        self._btn_folder = QPushButton("📁  Ouvrir le dossier")
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

        # Label chemin
        self._lbl_path = QLabel()
        self._lbl_path.setStyleSheet(
            f"color:{C['text_dim']};font-size:9px;font-family:'Consolas',monospace;"
            f"background:transparent;border:none;"
        )
        lay.addWidget(self._lbl_path)

        # Compteur vidéos
        self._lbl_count = QLabel()
        self._lbl_count.setStyleSheet(
            f"color:{C['text_secondary']};font-size:11px;background:transparent;border:none;"
        )
        lay.addWidget(self._lbl_count)

        # Grille de cartes
        self._grid_widget = QWidget()
        self._grid_widget.setStyleSheet("background:transparent;")
        self._grid = QGridLayout(self._grid_widget)
        self._grid.setContentsMargins(0, 0, 0, 0)
        self._grid.setSpacing(12)
        self._grid.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        lay.addWidget(self._grid_widget)

        # État vide
        self._lbl_empty = QLabel(
            "Aucune vidéo générée dans ce projet.\n"
            "Lancez une génération depuis « Générer depuis Storyboard » ou « Modifier des clips »."
        )
        self._lbl_empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._lbl_empty.setStyleSheet(
            f"color:{C['text_dim']};font-size:12px;padding:40px;"
        )
        lay.addWidget(self._lbl_empty)
        lay.addStretch()

        self.refresh()

    # ── Refresh ───────────────────────────────────────────────────────────────

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

        paths      = self._scan_videos()
        output_dir = self._get_output_dir()
        self._lbl_path.setText(f"Dossier : {output_dir}")

        if not paths:
            self._lbl_count.setText("")
            self._lbl_empty.setVisible(True)
            self._grid_widget.setVisible(False)
            return

        n = len(paths)
        self._lbl_count.setText(f"{n} vidéo{'s' if n > 1 else ''}")
        self._lbl_empty.setVisible(False)
        self._grid_widget.setVisible(True)

        for i, path in enumerate(paths):
            card = _VideoCard(path)
            card.play_requested.connect(self._on_play)
            card.edit_requested.connect(self._on_send_to_edit)
            self._cards[path] = card
            row, col = divmod(i, _COLS)
            self._grid.addWidget(card, row, col)

            tw = _LibThumbWorker(path, self)
            tw.done.connect(self._on_thumb_ready)
            tw.failed.connect(self._on_thumb_failed)
            tw.start()
            self._thumb_workers.append(tw)

    # ── Scan ─────────────────────────────────────────────────────────────────

    def list_all_clips(self) -> list[str]:
        """Tous les clips de la Vidéothèque — pont « Importer la Vidéothèque »
        de l'onglet Upscaling (même API que la Vidéothèque Live)."""
        return self._scan_videos()

    def _scan_videos(self) -> list[str]:
        import core.context as ctx
        import core.config  as cfg

        dirs_to_scan: list[str] = []

        data_root   = ctx.get_data_root()
        project_dir = cfg.project_video_dir()
        if os.path.isdir(project_dir):
            dirs_to_scan.append(project_dir)

        output_dir = cfg.get_output_dir()
        if output_dir and os.path.isdir(output_dir):
            norm_out = os.path.normpath(output_dir)
            if not dirs_to_scan or norm_out != os.path.normpath(dirs_to_scan[0]):
                dirs_to_scan.append(output_dir)

        paths: list[str] = []
        seen:  set[str]  = set()
        for d in dirs_to_scan:
            try:
                for fname in sorted(os.listdir(d)):
                    ext  = os.path.splitext(fname)[1].lower()
                    if ext not in _VIDEO_EXTS:
                        continue
                    full = os.path.normpath(os.path.join(d, fname))
                    if full not in seen and os.path.isfile(full):
                        seen.add(full)
                        paths.append(full)
            except OSError:
                pass

        return self._sort_paths(paths)

    def _sort_paths(self, paths: list[str]) -> list[str]:
        k = self._sort_key
        def _mtime(p):
            try: return os.path.getmtime(p)
            except OSError: return 0
        def _size(p):
            try: return os.path.getsize(p)
            except OSError: return 0
        if k == "date_desc":
            return sorted(paths, key=_mtime, reverse=True)
        if k == "date_asc":
            return sorted(paths, key=_mtime)
        if k == "name_asc":
            return sorted(paths, key=lambda p: os.path.basename(p).lower())
        if k == "size_desc":
            return sorted(paths, key=_size, reverse=True)
        return paths

    def _get_output_dir(self) -> str:
        import core.config  as cfg
        output_dir = cfg.get_output_dir()
        if output_dir and os.path.isdir(output_dir):
            return output_dir
        return cfg.project_video_dir()

    # ── Slots ────────────────────────────────────────────────────────────────

    def _on_sort_changed(self):
        self._sort_key = self._sort_combo.currentData()
        self.refresh()

    def _on_thumb_ready(self, path: str, img):
        pix = QPixmap.fromImage(img).scaled(
            _VideoCard._TH_W, _VideoCard._TH_H,
            Qt.AspectRatioMode.KeepAspectRatioByExpanding,
            Qt.TransformationMode.SmoothTransformation,
        )
        if path in self._cards:
            self._cards[path].set_thumb_pixmap(pix)

    def _open_diag_log(self):
        import tempfile as _tf
        import subprocess as _sp
        log = os.path.join(_tf.gettempdir(), "pandora_thumb_errors.txt")
        if os.path.isfile(log):
            try:
                _sp.Popen(["notepad.exe", log])
            except Exception:
                QDesktopServices.openUrl(QUrl.fromLocalFile(log))
        else:
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.information(None, "Diagnostic", "Aucun log d'erreur trouvé.")

    def _on_thumb_failed(self, path: str):
        """Affiche une icône vidéo générique quand la première frame ne peut pas être extraite."""
        if path not in self._cards:
            return
        self._btn_diag.setVisible(True)
        w, h = _VideoCard._TH_W, _VideoCard._TH_H
        ph = QPixmap(w, h)
        ph.fill(QColor(C["bg3"]))
        from PyQt6.QtGui import QPainter, QFont, QColor as _QColor
        painter = QPainter(ph)
        painter.setPen(_QColor(C["border_bright"]))
        font = QFont()
        font.setPixelSize(32)
        painter.setFont(font)
        painter.drawText(ph.rect(), Qt.AlignmentFlag.AlignCenter, "▶")
        painter.setPen(_QColor(C["text_dim"]))
        font2 = QFont()
        font2.setPixelSize(9)
        painter.setFont(font2)
        painter.drawText(
            0, h - 18, w, 18, Qt.AlignmentFlag.AlignCenter, "aperçu indisponible"
        )
        painter.end()
        self._cards[path].set_thumb_pixmap(ph)

    def _on_play(self, path: str):
        QDesktopServices.openUrl(QUrl.fromLocalFile(path))

    def _on_send_to_edit(self, path: str):
        self.send_to_davinci_edit.emit([path])

    def _open_output_folder(self):
        folder = self._get_output_dir()
        os.makedirs(folder, exist_ok=True)
        QDesktopServices.openUrl(QUrl.fromLocalFile(folder))
