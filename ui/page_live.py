"""
ui/page_live.py — Contrôleur Resolume (PANDORA | Live).

Intégration Resolume Arena/Avenue via l'API REST du Webserver (port 8080,
à activer dans Resolume : Préférences → Webserver).
  - Bibliothèque = les clips du PROJET (Vidéothèque : Seedance/upscalés/sonorisés)
  - Grille de composition couches × colonnes (réelle si connecté, mock sinon)
  - Chargement d'un clip dans un slot (clic gauche) · déclenchement (clic droit)
  - ENVOI EN FILE : la Vidéothèque pousse ses clips ici (queue_paths) — chaque
    clip remplit un slot consécutif de la couche choisie ; BPM compo optionnel
    depuis le set analysé du Conducteur (PushToResolumeWorker).
"""

import os

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QScrollArea, QLineEdit, QFrame, QGridLayout, QSpinBox,
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from ui.styles import CP
from core.i18n import translate


# ── Workers QThread ────────────────────────────────────────────────────────────

class _ConnectWorker(QThread):
    success = pyqtSignal(dict)
    failed  = pyqtSignal(str)

    def __init__(self, host: str, port: int):
        super().__init__()
        self._host = host
        self._port = port

    def run(self):
        from resolume.client import ResolumeClient
        info = ResolumeClient(self._host, self._port).get_product_info()
        if info:
            self.success.emit(info)
        else:
            self.failed.emit(
                f"Impossible de joindre Resolume sur {self._host}:{self._port}. "
                "Vérifiez que Resolume est lancé et que « Enable Webserver & REST API » "
                "est coché (Préférences → Webserver)."
            )


class _LayersWorker(QThread):
    done = pyqtSignal(list)

    def __init__(self, host: str, port: int):
        super().__init__()
        self._host = host
        self._port = port

    def run(self):
        from resolume.client import ResolumeClient
        self.done.emit(ResolumeClient(self._host, self._port).get_layers())


class _LoadWorker(QThread):
    success = pyqtSignal(int, int)
    failed  = pyqtSignal(str)

    def __init__(self, host: str, port: int, layer: int, col: int, path: str):
        super().__init__()
        self._host  = host
        self._port  = port
        self._layer = layer
        self._col   = col
        self._path  = path

    def run(self):
        from resolume.client import ResolumeClient
        if ResolumeClient(self._host, self._port).load_clip(self._layer, self._col, self._path):
            self.success.emit(self._layer, self._col)
        else:
            self.failed.emit(f"Chargement échoué → slot {self._layer}:{self._col}")


class _ClearWorker(QThread):
    """Vide un ou plusieurs slots d'une couche (POST /clear par slot)."""
    done = pyqtSignal(int)   # nombre de slots vidés

    def __init__(self, host: str, port: int, layer: int, cols: list):
        super().__init__()
        self._host, self._port = host, port
        self._layer = layer
        self._cols  = list(cols or [])

    def run(self):
        from resolume.client import ResolumeClient
        client = ResolumeClient(self._host, self._port)
        n = 0
        for col in self._cols:
            if client.clear_clip(self._layer, col):
                n += 1
        self.done.emit(n)


class _TriggerWorker(QThread):
    done = pyqtSignal(bool)

    def __init__(self, host: str, port: int, layer: int, col: int):
        super().__init__()
        self._host  = host
        self._port  = port
        self._layer = layer
        self._col   = col

    def run(self):
        from resolume.client import ResolumeClient
        self.done.emit(ResolumeClient(self._host, self._port).trigger_clip(self._layer, self._col))


# ── Miniatures mi-clip ─────────────────────────────────────────────────────────

class _MidThumbWorker(QThread):
    """Extrait la frame du MILIEU de chaque clip (ffmpeg) — pas la première :
    les plans ouvrent/ferment souvent au noir (demande Matthieu). Cache disque."""
    thumb_ready = pyqtSignal(str, str)   # (clip_path, png_path)

    def __init__(self, paths: list):
        super().__init__()
        self._paths = list(paths or [])

    @staticmethod
    def cache_path(path: str) -> str:
        import hashlib
        from core.context import get_data_root
        d = os.path.join(get_data_root(), ".thumbs_mid")
        os.makedirs(d, exist_ok=True)
        try:
            mtime = int(os.path.getmtime(path))
        except OSError:
            mtime = 0
        h = hashlib.md5(f"{path}|{mtime}".encode("utf-8")).hexdigest()[:16]
        return os.path.join(d, f"{h}.png")

    def run(self):
        import subprocess
        try:
            from core.video_utils import get_ffmpeg_exe
            ff = get_ffmpeg_exe()
        except Exception:
            ff = "ffmpeg"
        try:
            from core.video_conform import probe_duration
        except Exception:
            probe_duration = None
        flags = 0x08000000 if os.name == "nt" else 0
        for p in self._paths:
            if self.isInterruptionRequested():
                return
            out = self.cache_path(p)
            if os.path.isfile(out):
                self.thumb_ready.emit(p, out)
                continue
            mid = 0.0
            if probe_duration is not None:
                try:
                    mid = max(0.0, (probe_duration(p) or 0) / 2.0)
                except Exception:
                    mid = 0.0
            cmd = [ff, "-y", "-ss", f"{mid:.2f}", "-i", p,
                   "-frames:v", "1", "-vf", "scale=320:-1", out]
            try:
                subprocess.run(cmd, capture_output=True, creationflags=flags,
                               timeout=30)
            except Exception:
                continue
            if os.path.isfile(out):
                self.thumb_ready.emit(p, out)


class _SlotThumbWorker(QThread):
    """Récupère les vignettes des clips CHARGÉS dans Arena (GET /thumbnail)."""
    thumb_ready = pyqtSignal(int, int, bytes)   # (layer, col, png_bytes)

    def __init__(self, host: str, port: int, slots: list):
        super().__init__()
        self._host, self._port = host, port
        self._slots = list(slots or [])

    def run(self):
        from resolume.client import ResolumeClient
        client = ResolumeClient(self._host, self._port)
        for layer, col in self._slots:
            if self.isInterruptionRequested():
                return
            data = client.get_clip_thumbnail(layer, col)
            if data:
                self.thumb_ready.emit(layer, col, data)


# ── Carte clip bibliothèque ────────────────────────────────────────────────────

class _ClipCard(QWidget):
    selected = pyqtSignal(str)

    def __init__(self, path: str, view_mode: str = "detail"):
        super().__init__()
        self._path      = path
        self._mode      = view_mode
        self._is_sel    = False
        self._drag_from = None
        self.drag_provider = None        # posé par la page : sélection multiple
        self.setObjectName("clipcard")   # style SCOPÉ — sinon la bordure
        self.setCursor(Qt.CursorShape.OpenHandCursor)   # cascade sur les enfants
        self.setToolTip(os.path.basename(path)
                        + "\nClic : sélectionner (Ctrl = multi · Maj = plage)"
                        + "\nGlisser-déposer sur un slot pour charger.")
        self._apply_style(False)

        base = os.path.basename(path)
        size_mb = os.path.getsize(path) / 1_000_000 if os.path.isfile(path) else 0

        self._thumb = QLabel()
        self._thumb.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._thumb.setStyleSheet(
            f"background:{CP['bg0']};border:none;border-radius:4px;"
            f"color:{CP['text_dim']};font-size:9px;")
        self._thumb.setText("▶")

        name = QLabel(base if len(base) <= 26 else base[:25] + "…")
        name.setStyleSheet(
            f"color:{CP['text_primary']};font-size:10px;font-weight:600;"
            f"background:transparent;border:none;")
        meta = QLabel(f"{size_mb:.1f} MB")
        meta.setStyleSheet(
            f"color:{CP['text_dim']};font-size:9px;background:transparent;border:none;")

        play = QPushButton("▶")
        play.setFixedSize(22, 22)
        play.setCursor(Qt.CursorShape.PointingHandCursor)
        play.setToolTip("Lire le clip (lecteur par défaut) — ou double-clic sur la carte")
        play.setStyleSheet(
            f"QPushButton{{background:rgba(78,205,196,0.14);color:{CP['accent']};"
            f"border:1px solid {CP['accent_dim']};border-radius:11px;"
            f"font-size:10px;font-weight:700;}}"
            f"QPushButton:hover{{background:{CP['accent']};color:#07080f;}}")
        play.clicked.connect(self._play)

        if view_mode == "large":
            # Grande vignette (frame du milieu) au-dessus du nom
            self.setFixedHeight(168)
            lay = QVBoxLayout(self)
            lay.setContentsMargins(8, 8, 8, 6)
            lay.setSpacing(4)
            self._thumb.setFixedHeight(122)
            self._thumb_size = (216, 122)
            lay.addWidget(self._thumb)
            row = QHBoxLayout()
            row.addWidget(play)
            row.addWidget(name, 1)
            row.addWidget(meta)
            lay.addLayout(row)
        else:
            # Détails : petite vignette à gauche
            self.setFixedHeight(50)
            lay = QHBoxLayout(self)
            lay.setContentsMargins(8, 4, 10, 4)
            lay.setSpacing(10)
            self._thumb.setFixedSize(70, 40)
            self._thumb_size = (70, 40)
            lay.addWidget(self._thumb)
            col = QVBoxLayout()
            col.setSpacing(1)
            col.addWidget(name)
            col.addWidget(meta)
            lay.addLayout(col, 1)
            lay.addWidget(play)

    def _play(self):
        """Prévisualise le clip dans le lecteur par défaut."""
        from PyQt6.QtGui import QDesktopServices
        from PyQt6.QtCore import QUrl
        QDesktopServices.openUrl(QUrl.fromLocalFile(self._path))

    def mouseDoubleClickEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            self._play()

    def set_thumb(self, png_path: str):
        from PyQt6.QtGui import QPixmap
        pix = QPixmap(png_path)
        if pix.isNull():
            return
        w, h = self._thumb_size
        self._thumb.setPixmap(pix.scaled(
            w, h, Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation))

    def _apply_style(self, sel: bool):
        # Sélection BIEN visible : cadre accent 2px — autour de la VIGNETTE en
        # mode grandes vignettes, autour de toute la carte en mode détails.
        if sel:
            self.setStyleSheet(
                f"QWidget#clipcard{{background:rgba(78,205,196,0.15);"
                f"border:2px solid {CP['accent']};border-radius:8px;}}"
            )
        else:
            self.setStyleSheet(
                f"QWidget#clipcard{{background:{CP['bg2']};"
                f"border:1px solid {CP['border']};border-radius:8px;}}"
            )
        if hasattr(self, "_thumb") and self._mode == "large":
            self._thumb.setStyleSheet(
                f"background:{CP['bg0']};border-radius:4px;color:{CP['text_dim']};"
                f"font-size:9px;border:2px solid "
                + (CP['accent'] if sel else "transparent") + ";")

    def set_selected(self, v: bool):
        self._is_sel = v
        self._apply_style(v)

    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            self._drag_from = e.position().toPoint()
            self.selected.emit(self._path)

    def mouseMoveEvent(self, e):
        # Glisser-déposer vers un slot de la grille Resolume (multi-sélection OK)
        if (self._drag_from is not None
                and (e.position().toPoint() - self._drag_from).manhattanLength() > 12):
            from PyQt6.QtGui import QDrag
            from PyQt6.QtCore import QMimeData
            drag = QDrag(self)
            mime = QMimeData()
            paths = self.drag_provider(self._path) if self.drag_provider else [self._path]
            mime.setText("\n".join(paths))
            drag.setMimeData(mime)
            pm = self._thumb.pixmap()
            if pm is not None and not pm.isNull():
                drag.setPixmap(pm.scaledToWidth(90))
            self._drag_from = None
            drag.exec(Qt.DropAction.CopyAction)

    def mouseReleaseEvent(self, e):
        self._drag_from = None

    def enterEvent(self, e):
        if not self._is_sel:
            self.setStyleSheet(
                f"QWidget#clipcard{{background:{CP['bg3']};"
                f"border:1px solid {CP['border_bright']};border-radius:8px;}}"
            )

    def leaveEvent(self, e):
        if not self._is_sel:
            self._apply_style(False)


# ── Bouton slot Resolume ───────────────────────────────────────────────────────

class _SlotBtn(QPushButton):
    load_req    = pyqtSignal(int, int)
    trigger_req = pyqtSignal(int, int)
    drop_req    = pyqtSignal(int, int, str)   # dépôt d'un clip (chemin)
    clear_req   = pyqtSignal(int, int)        # Maj+clic = vider le slot

    def __init__(self, layer: int, col: int, clip_name: str = ""):
        super().__init__()
        self._layer = layer
        self._col   = col
        self.setFixedSize(104, 60)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setAcceptDrops(True)
        self.set_clip(clip_name)

    def set_thumb(self, png_bytes: bytes):
        """Vignette du clip chargé (servie par Arena)."""
        from PyQt6.QtGui import QPixmap, QIcon
        pix = QPixmap()
        if not pix.loadFromData(png_bytes) or pix.isNull():
            return
        from PyQt6.QtCore import QSize
        self.setIcon(QIcon(pix))
        self.setIconSize(QSize(92, 40))
        if self._clip:
            self.setText(self._clip[:12] + ("…" if len(self._clip) > 12 else ""))

    def dragEnterEvent(self, e):
        first = e.mimeData().text().splitlines()[0] if e.mimeData().hasText() else ""
        if os.path.splitext(first)[1].lower() in (".mp4", ".mov", ".webm",
                                                  ".m4v", ".gif", ".png", ".jpg"):
            e.acceptProposedAction()

    def dropEvent(self, e):
        self.drop_req.emit(self._layer, self._col, e.mimeData().text())
        e.acceptProposedAction()

    def set_clip(self, name: str):
        self._clip = name
        if name:
            self.setText(name[:16] + ("…" if len(name) > 16 else ""))
            self.setToolTip(f"{name}\nClic : charger la sélection · Clic droit : déclencher\n"
                            f"Maj+clic : vider · Glisser un clip ici pour le charger")
            self.setStyleSheet(
                f"QPushButton{{background:rgba(78,205,196,0.12);color:{CP['accent']};"
                f"border:1px solid {CP['accent_dim']};border-radius:6px;"
                f"font-size:8px;font-weight:600;padding:3px;}}"
                f"QPushButton:hover{{background:rgba(78,205,196,0.22);}}"
            )
        else:
            self.setText(f"{self._layer} : {self._col}")
            self.setIcon(__import__("PyQt6.QtGui", fromlist=["QIcon"]).QIcon())
            self.setToolTip(f"Slot {self._layer}:{self._col} — vide\n"
                            f"Clic : charger la sélection · Glisser un clip ici")
            self.setStyleSheet(
                f"QPushButton{{background:{CP['bg3']};color:{CP['text_dim']};"
                f"border:1px solid {CP['border']};border-radius:6px;"
                f"font-size:9px;padding:3px;}}"
                f"QPushButton:hover{{background:{CP['bg4']};"
                f"border-color:{CP['border_bright']};}}"
            )

    def mousePressEvent(self, e):
        from PyQt6.QtWidgets import QApplication
        if e.button() == Qt.MouseButton.LeftButton:
            if QApplication.keyboardModifiers() & Qt.KeyboardModifier.ShiftModifier:
                self.clear_req.emit(self._layer, self._col)   # Maj+clic = vider
            else:
                self.load_req.emit(self._layer, self._col)
        elif e.button() == Qt.MouseButton.RightButton:
            self.trigger_req.emit(self._layer, self._col)
        super().mousePressEvent(e)


# ── Page principale ────────────────────────────────────────────────────────────

class PageLive(QWidget):
    """Page PANDORA | Live — contrôle Resolume Arena/Avenue."""

    def __init__(self):
        super().__init__()
        from resolume.client import get_resolume_config
        self._host, self._port = get_resolume_config()
        self._connected     = False
        self._selected_clip = ""
        self._pending_paths: list[str] = []   # file reçue de la Vidéothèque
        self._push_worker   = None
        self._slot_widgets: dict[tuple, _SlotBtn] = {}
        self._clip_cards:   list[_ClipCard]       = []
        self._workers:      list                  = []

        self.setStyleSheet(f"background:{CP['bg0']};")
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        root.addWidget(self._build_topbar())
        root.addWidget(self._build_body(), 1)
        root.addWidget(self._build_statusbar())

        self._refresh_library()

    # ── UI builders ────────────────────────────────────────────────────────────

    def _build_topbar(self) -> QWidget:
        bar = QWidget()
        bar.setFixedHeight(60)   # hauteur STANDARD des bandeaux (alignement assistant)
        bar.setStyleSheet(
            f"background:{CP['bg1']};border-bottom:2px solid {CP['border_bright']};"
        )
        lay = QHBoxLayout(bar)
        lay.setContentsMargins(20, 0, 20, 0)
        lay.setSpacing(12)

        title = QLabel("🎛  " + translate("CONTRÔLEUR RESOLUME"))
        title.setStyleSheet(
            f"color:{CP['text_primary']};font-size:13px;font-weight:800;"
            f"letter-spacing:2px;background:transparent;border:none;"
        )
        lay.addWidget(title)

        self._dot = QLabel("●")
        self._dot.setStyleSheet(f"color:{CP['text_dim']};font-size:12px;background:transparent;border:none;")
        lay.addWidget(self._dot)

        self._host_input = QLineEdit(self._host)
        self._host_input.setFixedSize(130, 28)
        self._host_input.setStyleSheet(
            f"QLineEdit{{background:{CP['bg3']};border:1px solid {CP['border']};"
            f"border-radius:5px;color:{CP['text_primary']};font-size:11px;padding:0 8px;}}"
        )
        lay.addWidget(self._host_input)

        port_sep = QLabel(":")
        port_sep.setStyleSheet(f"color:{CP['text_dim']};background:transparent;border:none;")
        lay.addWidget(port_sep)

        self._port_spin = QSpinBox()
        self._port_spin.setRange(1024, 65535)
        self._port_spin.setValue(self._port)
        self._port_spin.setButtonSymbols(QSpinBox.ButtonSymbols.NoButtons)
        self._port_spin.setFixedSize(64, 28)
        self._port_spin.setStyleSheet(
            f"QSpinBox{{background:{CP['bg3']};border:1px solid {CP['border']};"
            f"border-radius:5px;color:{CP['text_primary']};font-size:11px;padding:0 4px;}}"
        )
        lay.addWidget(self._port_spin)

        self._btn_connect = QPushButton("Connecter")
        self._btn_connect.setFixedHeight(28)
        self._btn_connect.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_connect.setStyleSheet(
            f"QPushButton{{background:transparent;color:{CP['accent2']};"
            f"border:1px solid rgba(124,107,255,0.5);border-radius:5px;"
            f"font-size:11px;font-weight:700;padding:0 12px;}}"
            f"QPushButton:hover{{background:rgba(124,107,255,0.12);}}"
            f"QPushButton:disabled{{color:{CP['text_dim']};border-color:{CP['border']};}}"
        )
        self._btn_connect.clicked.connect(self._on_connect)
        lay.addWidget(self._btn_connect)
        lay.addStretch()   # tout est regroupé à gauche (demande Matthieu)

        return bar

    def _build_body(self) -> QWidget:
        body = QWidget()
        body.setStyleSheet("background:transparent;")
        lay = QHBoxLayout(body)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)

        # ── Bibliothèque gauche ────────────────────────────────────────────────
        # Bordure GAUCHE 2px : ferme visuellement le contrôleur Resolume par
        # rapport au dashboard (demande Matthieu) — même trait que la topbar.
        lib = QWidget()
        lib.setMinimumWidth(264)
        lib.setStyleSheet(
            f"QWidget{{background:{CP['bg1']};}}"
        )
        lib_lay = QVBoxLayout(lib)
        lib_lay.setContentsMargins(12, 14, 12, 14)
        lib_lay.setSpacing(8)

        lib_hdr = QLabel("BIBLIOTHÈQUE PANDORA")
        lib_hdr.setStyleSheet(
            f"color:{CP['text_dim']};font-size:9px;font-weight:700;"
            f"letter-spacing:2px;background:transparent;"
        )
        lib_lay.addWidget(lib_hdr)

        self._selected_lbl = QLabel("Aucun clip sélectionné")
        self._selected_lbl.setWordWrap(True)
        self._selected_lbl.setStyleSheet(
            f"color:{CP['text_dim']};font-size:9px;font-style:italic;background:transparent;border:none;"
        )
        lib_lay.addWidget(self._selected_lbl)

        # Affichage : détails (liste) ou grandes vignettes (frame du MILIEU du clip)
        from PyQt6.QtWidgets import QComboBox
        view_row = QHBoxLayout()
        view_row.setSpacing(6)
        _v_lbl = QLabel(translate("Affichage :"))
        _v_lbl.setStyleSheet(
            f"color:{CP['text_dim']};font-size:9px;background:transparent;border:none;")
        view_row.addWidget(_v_lbl)
        self._view_combo = QComboBox()
        self._view_combo.addItem(translate("Détails"), "detail")
        self._view_combo.addItem(translate("Grandes vignettes"), "large")
        self._view_combo.setFixedHeight(24)
        self._view_combo.setStyleSheet(
            f"QComboBox{{background:{CP['bg3']};border:1px solid {CP['border']};"
            f"border-radius:4px;color:{CP['text_primary']};font-size:10px;padding:0 8px;}}"
            f"QComboBox::drop-down{{border:none;width:16px;}}"
            f"QComboBox QAbstractItemView{{background:{CP['bg3']};"
            f"border:1px solid {CP['border_bright']};color:{CP['text_primary']};}}")
        self._view_combo.currentIndexChanged.connect(self._refresh_library)
        view_row.addWidget(self._view_combo, 1)
        lib_lay.addLayout(view_row)

        lib_scroll = QScrollArea()
        self._lib_scroll = lib_scroll
        lib_scroll.setMinimumHeight(220)
        lib_scroll.setWidgetResizable(True)
        lib_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        lib_scroll.setStyleSheet("QScrollArea{background:transparent;border:none;}")
        self._lib_container = QWidget()
        self._lib_container.setStyleSheet("background:transparent;")
        self._lib_lay = QVBoxLayout(self._lib_container)
        self._lib_lay.setContentsMargins(0, 0, 0, 0)
        self._lib_lay.setSpacing(6)
        self._lib_lay.setAlignment(Qt.AlignmentFlag.AlignTop)
        lib_scroll.setWidget(self._lib_container)
        lib_lay.addWidget(lib_scroll, 1)

        btn_refresh = QPushButton("↺  " + translate("Actualiser la bibliothèque"))
        btn_refresh.setFixedHeight(28)
        btn_refresh.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_refresh.setToolTip(translate("Re-scanne les clips du projet."))
        btn_refresh.setStyleSheet(
            f"QPushButton{{background:transparent;color:{CP['text_primary']};"
            f"border:1px solid {CP['border']};border-radius:5px;"
            f"font-size:10px;font-weight:700;}}"
            f"QPushButton:hover{{background:{CP['bg2']};border-color:{CP['border_bright']};}}"
        )
        btn_refresh.clicked.connect(self._refresh_library)
        lib_lay.addWidget(btn_refresh)

        # ── Envoi en file (Vidéothèque → slots consécutifs) ────────────────────
        push_hdr = QLabel("ENVOI EN FILE")
        push_hdr.setStyleSheet(
            f"color:{CP['text_dim']};font-size:9px;font-weight:700;"
            f"letter-spacing:2px;background:transparent;padding-top:8px;"
        )
        lib_lay.addWidget(push_hdr)

        self._push_info = QLabel(translate("Toute la bibliothèque"))
        self._push_info.setWordWrap(True)
        self._push_info.setStyleSheet(
            f"color:{CP['text_secondary']};font-size:9px;background:transparent;"
        )
        lib_lay.addWidget(self._push_info)

        push_row = QHBoxLayout()
        push_row.setSpacing(6)
        for lbl_txt, attr, default, mx in (("Couche", "_push_layer", 1, 99),
                                           ("Colonne", "_push_col", 1, 256)):
            lbl = QLabel(lbl_txt)
            lbl.setStyleSheet(
                f"color:{CP['text_secondary']};font-size:10px;"
                f"background:transparent;border:none;")
            push_row.addWidget(lbl)
            spin = QSpinBox()
            spin.setRange(1, mx)
            spin.setValue(default)
            spin.setButtonSymbols(QSpinBox.ButtonSymbols.NoButtons)
            spin.setAlignment(Qt.AlignmentFlag.AlignCenter)
            spin.setFixedSize(40, 26)
            spin.setStyleSheet(
                f"QSpinBox{{background:{CP['bg3']};border:1px solid {CP['border']};"
                f"border-radius:4px;color:{CP['text_primary']};font-size:11px;"
                f"font-weight:700;padding:0 2px;}}")
            push_row.addWidget(spin)
            setattr(self, attr, spin)
        push_row.addStretch()
        lib_lay.addLayout(push_row)

        from PyQt6.QtWidgets import QCheckBox
        self._push_bpm_cb = QCheckBox(translate("Régler le BPM de la composition"))
        self._push_bpm_cb.setStyleSheet(
            f"QCheckBox{{color:{CP['text_secondary']};font-size:9px;background:transparent;}}")
        _bpm = self._conductor_bpm()
        if _bpm > 0:
            self._push_bpm_cb.setText(
                translate("Régler le BPM de la composition") + f" ({_bpm:g})")
            self._push_bpm_cb.setChecked(True)
        else:
            self._push_bpm_cb.setEnabled(False)
            self._push_bpm_cb.setToolTip(translate(
                "Analyse d'abord le set dans le Conducteur (« Analyser le set »)."))
        lib_lay.addWidget(self._push_bpm_cb)

        self._acte_layers_cb = QCheckBox(translate("Une couche par acte (SQ1 → couche 1…)"))
        self._acte_layers_cb.setStyleSheet(
            f"QCheckBox{{color:{CP['text_secondary']};font-size:9px;background:transparent;}}")
        self._acte_layers_cb.setToolTip(translate(
            "Répartit les clips par acte : tous les SQ1 sur la 1re couche,\n"
            "les SQ2 sur la suivante, etc. (colonnes redémarrent à 1 par couche).\n"
            "Décoché : tout sur la couche choisie, colonnes consécutives."))
        lib_lay.addWidget(self._acte_layers_cb)

        self._show_mode_cb = QCheckBox(translate("Mode show (enchaînement auto, calé mesure)"))
        self._show_mode_cb.setStyleSheet(
            f"QCheckBox{{color:{CP['text_secondary']};font-size:9px;background:transparent;}}")
        self._show_mode_cb.setToolTip(translate(
            "Chaque clip est réglé : Play Once & Hold (joue une fois, tient sa\n"
            "dernière frame), Beat Snap 1 mesure, Autopilot « clip suivant ».\n"
            "Déclenche le 1er clip : toute la séquence se joue seule, au tempo."))
        lib_lay.addWidget(self._show_mode_cb)

        self._btn_push = QPushButton("⇪  " + translate("Envoyer vers Resolume"))
        self._btn_push.setFixedHeight(34)
        self._btn_push.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_push.setStyleSheet(
            f"QPushButton{{background:{CP['accent']};color:#07080f;"
            f"border:none;border-radius:6px;font-size:10px;font-weight:700;}}"
            f"QPushButton:hover{{background:#6eded6;}}"
            f"QPushButton:disabled{{background:{CP['bg3']};color:{CP['text_dim']};"
            f"border:1px solid {CP['border']};}}"
        )
        self._btn_push.clicked.connect(self._on_push_queue)
        lib_lay.addWidget(self._btn_push)

        self._btn_push_cancel = QPushButton("■  " + translate("Annuler l'envoi"))
        self._btn_push_cancel.setFixedHeight(28)
        self._btn_push_cancel.setVisible(False)
        self._btn_push_cancel.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_push_cancel.setStyleSheet(
            f"QPushButton{{background:{CP['bg3']};color:{CP['red']};"
            f"border:1px solid {CP['red']};border-radius:6px;"
            f"font-size:10px;font-weight:700;}}"
            f"QPushButton:hover{{background:rgba(255,79,106,0.12);}}"
        )
        self._btn_push_cancel.clicked.connect(self._on_push_cancel)
        lib_lay.addWidget(self._btn_push_cancel)

        self._btn_calage = QPushButton("▱  " + translate("Calage Resolume"))
        self._btn_calage.setFixedHeight(30)
        self._btn_calage.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_calage.setToolTip(translate(
            "Extrait automatiquement le polygone de la façade et génère :\n"
            "• un preset Advanced Output (menu Presets de Resolume)\n"
            "• une mire de calage PNG spécifique au bâtiment.\n"
            "Le calage manuel des points devient une simple vérification."))
        self._btn_calage.setStyleSheet(
            f"QPushButton{{background:transparent;color:{CP['accent2']};"
            f"border:1px solid rgba(124,107,255,0.5);border-radius:6px;"
            f"font-size:10px;font-weight:700;}}"
            f"QPushButton:hover{{background:rgba(124,107,255,0.10);}}"
        )
        self._btn_calage.clicked.connect(self._on_generate_calage)
        lib_lay.addWidget(self._btn_calage)

        # Colonne SCROLLABLE : plus aucun bouton tronqué en bas (vu en réel :
        # « Calage Resolume » coupé), et bordures gauche/droite pleine hauteur.
        lib_scroll_col = QScrollArea()
        lib_scroll_col.setWidget(lib)
        lib_scroll_col.setWidgetResizable(True)
        lib_scroll_col.setFixedWidth(286)
        lib_scroll_col.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        lib_scroll_col.setStyleSheet(
            f"QScrollArea{{background:{CP['bg1']};"
            f"border-left:2px solid {CP['border_bright']};"
            f"border-right:1px solid {CP['border']};border-top:none;border-bottom:none;}}"
            f"QScrollBar:vertical{{background:{CP['bg2']};width:6px;border-radius:3px;}}"
            f"QScrollBar::handle:vertical{{background:{CP['border_bright']};"
            f"border-radius:3px;min-height:30px;}}"
            f"QScrollBar::add-line:vertical,QScrollBar::sub-line:vertical{{height:0;}}"
        )
        lay.addWidget(lib_scroll_col)

        # ── Grille Resolume ────────────────────────────────────────────────────
        grid_area = QWidget()
        grid_area.setStyleSheet("background:transparent;")
        ga_lay = QVBoxLayout(grid_area)
        ga_lay.setContentsMargins(16, 14, 16, 14)
        ga_lay.setSpacing(10)

        grid_hdr = QHBoxLayout()
        self._grid_title = QLabel("COMPOSITION RESOLUME")
        self._grid_title.setStyleSheet(
            f"color:{CP['text_dim']};font-size:9px;font-weight:700;"
            f"letter-spacing:2px;background:transparent;"
        )
        grid_hdr.addWidget(self._grid_title)
        _hint = QLabel(translate("glisser un clip sur un slot · clic droit : déclencher · Maj+clic : vider"))
        _hint.setStyleSheet(
            f"color:{CP['text_dim']};font-size:9px;background:transparent;border:none;")
        grid_hdr.addWidget(_hint)
        grid_hdr.addStretch()
        self._btn_clear_layer = QPushButton("🗑  " + translate("Vider la couche"))
        self._btn_clear_layer.setFixedHeight(24)
        self._btn_clear_layer.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_clear_layer.setToolTip(translate(
            "Vide TOUS les slots de la couche choisie\n(spin « Couche » de l'envoi en file)."))
        self._btn_clear_layer.setStyleSheet(
            f"QPushButton{{background:transparent;color:{CP['red']};"
            f"border:1px solid {CP['red']};border-radius:4px;font-size:9px;"
            f"font-weight:700;padding:0 10px;}}"
            f"QPushButton:hover{{background:rgba(255,79,106,0.12);}}")
        self._btn_clear_layer.clicked.connect(self._on_clear_layer)
        grid_hdr.addWidget(self._btn_clear_layer)

        # Config grille (visible en mode mock)
        self._grid_config = QWidget()
        gc_lay = QHBoxLayout(self._grid_config)
        gc_lay.setContentsMargins(0, 0, 0, 0)
        gc_lay.setSpacing(8)

        for lbl_text, attr, default, max_val in [
            ("Couches :", "_spin_layers", 4, 8),
            ("Colonnes :", "_spin_cols", 8, 16),
        ]:
            lbl = QLabel(lbl_text)
            lbl.setStyleSheet(f"color:{CP['text_secondary']};font-size:10px;background:transparent;border:none;")
            gc_lay.addWidget(lbl)
            spin = QSpinBox()
            spin.setRange(1, max_val)
            spin.setValue(default)
            spin.setButtonSymbols(QSpinBox.ButtonSymbols.NoButtons)
            spin.setAlignment(Qt.AlignmentFlag.AlignCenter)
            spin.setFixedSize(40, 24)
            spin.setStyleSheet(
                f"QSpinBox{{background:{CP['bg3']};border:1px solid {CP['border']};"
                f"border-radius:4px;color:{CP['text_primary']};font-size:10px;padding:0 2px;}}"
            )
            gc_lay.addWidget(spin)
            setattr(self, attr, spin)

        btn_apply = QPushButton("Appliquer")
        btn_apply.setFixedHeight(24)
        btn_apply.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_apply.setStyleSheet(
            f"QPushButton{{background:transparent;color:{CP['text_dim']};"
            f"border:1px solid {CP['border']};border-radius:4px;"
            f"font-size:9px;padding:0 8px;}}"
            f"QPushButton:hover{{color:{CP['text_primary']};border-color:{CP['border_bright']};}}"
        )
        btn_apply.clicked.connect(self._rebuild_grid)
        gc_lay.addWidget(btn_apply)
        grid_hdr.addWidget(self._grid_config)

        ga_lay.addLayout(grid_hdr)

        grid_scroll = QScrollArea()
        grid_scroll.setWidgetResizable(True)
        grid_scroll.setStyleSheet(f"QScrollArea{{background:{CP['bg0']};border:none;}}")
        self._grid_w = QWidget()
        self._grid_w.setStyleSheet(f"background:{CP['bg0']};")
        self._grid_layout = QGridLayout(self._grid_w)
        self._grid_layout.setSpacing(6)
        self._grid_layout.setContentsMargins(0, 0, 0, 0)
        grid_scroll.setWidget(self._grid_w)
        ga_lay.addWidget(grid_scroll, 1)

        lay.addWidget(grid_area, 1)
        return body

    def _build_statusbar(self) -> QWidget:
        bar = QWidget()
        bar.setFixedHeight(30)
        bar.setStyleSheet(
            f"background:{CP['bg1']};border-top:1px solid {CP['border']};"
        )
        lay = QHBoxLayout(bar)
        lay.setContentsMargins(16, 0, 16, 0)
        lay.setSpacing(16)

        self._status_lbl = QLabel(
            "Déconnecté · Clic gauche sur un slot = charger le clip sélectionné · "
            "Clic droit = déclencher (nécessite connexion)"
        )
        self._status_lbl.setStyleSheet(
            f"color:{CP['text_secondary']};font-size:10px;"
            f"font-family:'Consolas',monospace;background:transparent;border:none;"
        )
        lay.addWidget(self._status_lbl, 1)
        return bar

    # ── Connexion Resolume ─────────────────────────────────────────────────────

    def _on_connect(self):
        self._host = self._host_input.text().strip() or "localhost"
        self._port = self._port_spin.value()
        self._btn_connect.setEnabled(False)
        self._btn_connect.setText("Connexion…")
        self._dot.setStyleSheet(f"color:#f5a623;font-size:12px;background:transparent;")

        w = _ConnectWorker(self._host, self._port)
        w.success.connect(self._on_connected)
        w.failed.connect(self._on_connect_failed)
        w.finished.connect(w.deleteLater)
        self._workers.append(w)
        w.start()

    def _on_connected(self, info: dict):
        product = info.get("product", "Resolume")
        version = info.get("version", "")
        self._connected = True
        self._dot.setStyleSheet(f"color:#4caf50;font-size:12px;background:transparent;")
        self._btn_connect.setEnabled(True)
        self._btn_connect.setText("Déconnecter")
        try:
            self._btn_connect.clicked.disconnect()
        except RuntimeError:
            pass
        self._btn_connect.clicked.connect(self._on_disconnect)
        self._grid_config.setVisible(False)
        self._status_lbl.setText(
            f"Connecté : {product} {version} · {self._host}:{self._port}"
        )
        self._fetch_layers()

    def _on_connect_failed(self, err: str):
        self._connected = False
        self._dot.setStyleSheet(f"color:{CP['text_dim']};font-size:12px;background:transparent;")
        self._btn_connect.setEnabled(True)
        self._btn_connect.setText("Connecter")
        self._status_lbl.setText(f"✗  {err}")

    def _on_disconnect(self):
        self._connected = False
        self._dot.setStyleSheet(f"color:{CP['text_dim']};font-size:12px;background:transparent;")
        self._btn_connect.setText("Connecter")
        try:
            self._btn_connect.clicked.disconnect()
        except RuntimeError:
            pass
        self._btn_connect.clicked.connect(self._on_connect)
        self._grid_config.setVisible(True)
        self._status_lbl.setText("Déconnecté")
        self._rebuild_grid()

    def _fetch_layers(self):
        w = _LayersWorker(self._host, self._port)
        w.done.connect(self._on_layers_fetched)
        w.finished.connect(w.deleteLater)
        self._workers.append(w)
        w.start()

    def _on_layers_fetched(self, layers: list):
        self._clear_grid()
        if not layers:
            lbl = QLabel("Aucune couche détectée dans Resolume.")
            lbl.setStyleSheet(
                f"color:{CP['text_dim']};font-size:12px;background:transparent;"
            )
            self._grid_layout.addWidget(lbl, 0, 0)
            return

        max_cols = max((len(layer.clips) for layer in layers), default=8)

        # Colonne headers
        for j in range(1, max_cols + 1):
            lbl = QLabel(str(j))
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lbl.setFixedSize(104, 20)
            lbl.setStyleSheet(
                f"color:{CP['text_dim']};font-size:9px;font-weight:700;"
                f"font-family:'Consolas',monospace;background:transparent;"
            )
            self._grid_layout.addWidget(lbl, 0, j)

        for i, layer in enumerate(layers, 1):
            # Resolume nomme ses couches avec le joker « # » (= numéro auto)
            _name = (layer.name or "").replace("#", str(i)).strip() or f"Couche {i}"
            lyr_lbl = QLabel(_name[:14])
            lyr_lbl.setToolTip(_name)
            lyr_lbl.setFixedSize(86, 60)
            lyr_lbl.setAlignment(
                Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
            )
            lyr_lbl.setStyleSheet(
                f"color:{CP['text_secondary']};font-size:10px;font-weight:700;"
                f"background:transparent;border:none;padding-right:8px;"
            )
            self._grid_layout.addWidget(lyr_lbl, i, 0)

            for clip in layer.clips:
                btn = _SlotBtn(clip.layer, clip.col, clip.name)
                btn.load_req.connect(self._on_slot_load)
                btn.trigger_req.connect(self._on_slot_trigger)
                btn.drop_req.connect(self._on_slot_drop)
                btn.clear_req.connect(self._on_slot_clear)
                self._slot_widgets[(clip.layer, clip.col)] = btn
                self._grid_layout.addWidget(btn, i, clip.col)

        # Vignettes des clips chargés (servies par Arena)
        loaded = [(l.index, c.col) for l in layers for c in l.clips if c.name]
        if loaded and self._connected:
            if getattr(self, "_slot_thumb_worker", None) is not None:
                from core.worker import abandon_thread
                abandon_thread(self._slot_thumb_worker)
            self._slot_thumb_worker = _SlotThumbWorker(self._host, self._port, loaded)
            self._slot_thumb_worker.thumb_ready.connect(self._on_slot_thumb)
            self._slot_thumb_worker.start()

    def _on_slot_thumb(self, layer: int, col: int, data: bytes):
        btn = self._slot_widgets.get((layer, col))
        if btn:
            btn.set_thumb(data)

    # ── Grille mock ────────────────────────────────────────────────────────────

    def _rebuild_grid(self):
        self._clear_grid()
        n_layers = self._spin_layers.value()
        n_cols   = self._spin_cols.value()

        for j in range(1, n_cols + 1):
            lbl = QLabel(str(j))
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lbl.setFixedSize(104, 20)
            lbl.setStyleSheet(
                f"color:{CP['text_dim']};font-size:9px;font-weight:700;"
                f"font-family:'Consolas',monospace;background:transparent;"
            )
            self._grid_layout.addWidget(lbl, 0, j)

        for i in range(1, n_layers + 1):
            lyr_lbl = QLabel(f"Couche {i}")
            lyr_lbl.setFixedSize(86, 60)
            lyr_lbl.setAlignment(
                Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
            )
            lyr_lbl.setStyleSheet(
                f"color:{CP['text_secondary']};font-size:10px;font-weight:700;"
                f"background:transparent;border:none;padding-right:8px;"
            )
            self._grid_layout.addWidget(lyr_lbl, i, 0)

            for j in range(1, n_cols + 1):
                btn = _SlotBtn(i, j)
                btn.load_req.connect(self._on_slot_load)
                btn.trigger_req.connect(self._on_slot_trigger)
                btn.drop_req.connect(self._on_slot_drop)
                btn.clear_req.connect(self._on_slot_clear)
                self._slot_widgets[(i, j)] = btn
                self._grid_layout.addWidget(btn, i, j)

    def _clear_grid(self):
        self._slot_widgets.clear()
        while self._grid_layout.count():
            item = self._grid_layout.takeAt(0)
            if item and item.widget():
                item.widget().deleteLater()

    # ── Bibliothèque ───────────────────────────────────────────────────────────

    def _refresh_library(self):
        # Anti-résidus de peinture : détacher AVANT deleteLater (vu en réel au
        # passage Détails ↔ Grandes vignettes)
        for c in self._clip_cards:
            c.hide()
            c.setParent(None)
            c.deleteLater()
        self._clip_cards.clear()
        while self._lib_lay.count():
            item = self._lib_lay.takeAt(0)
            w = item.widget() if item else None
            if w:
                w.hide()
                w.setParent(None)
                w.deleteLater()

        # Mêmes sources que la Vidéothèque du Studio (clips du PROJET)
        from ui.tab_video_library_live import scan_live_clips
        clips = scan_live_clips()
        clips.sort(
            key=lambda p: os.path.getmtime(p) if os.path.isfile(p) else 0,
            reverse=True
        )
        clips = clips[:80]

        if not clips:
            lbl = QLabel("Aucun clip dans le projet —\ngénère depuis le Studio IA.")
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lbl.setStyleSheet(
                f"color:{CP['text_dim']};font-size:10px;background:transparent;"
            )
            self._lib_lay.addWidget(lbl)
        else:
            view = (self._view_combo.currentData() or "detail"
                    if hasattr(self, "_view_combo") else "detail")
            for path in clips:
                card = _ClipCard(path, view_mode=view)
                card.selected.connect(self._on_clip_selected)
                # Drag multi : si la carte fait partie de la sélection, tout part
                card.drag_provider = self._drag_paths
                self._clip_cards.append(card)
                self._lib_lay.addWidget(card)
            # Anti-résidus : remonte la liste en haut après reconstruction
            if hasattr(self, "_lib_scroll"):
                self._lib_scroll.verticalScrollBar().setValue(0)
            # Vignettes = frame du MILIEU du clip (les plans ouvrent/ferment au noir)
            if getattr(self, "_thumb_worker", None) is not None:
                from core.worker import abandon_thread
                abandon_thread(self._thumb_worker)
            self._thumb_worker = _MidThumbWorker(clips)
            self._thumb_worker.thumb_ready.connect(self._on_lib_thumb)
            self._thumb_worker.start()

        if not self._connected:
            self._rebuild_grid()

    def _on_lib_thumb(self, clip_path: str, png_path: str):
        for card in self._clip_cards:
            if getattr(card, "_path", "") == clip_path:
                card.set_thumb(png_path)
                break

    # ── Interactions ───────────────────────────────────────────────────────────

    def _on_clip_selected(self, path: str):
        """Sélection multiple : clic = seul · Ctrl = ajouter/retirer · Maj = plage."""
        from PyQt6.QtWidgets import QApplication
        mods  = QApplication.keyboardModifiers()
        order = [c._path for c in self._clip_cards]
        sel   = getattr(self, "_selected_paths", [])
        if mods & Qt.KeyboardModifier.ShiftModifier and self._selected_clip in order:
            i1, i2 = order.index(self._selected_clip), order.index(path)
            rng = order[min(i1, i2):max(i1, i2) + 1]
            sel = list(dict.fromkeys(sel + rng))
        elif mods & Qt.KeyboardModifier.ControlModifier:
            if path in sel:
                sel = [p for p in sel if p != path]
            else:
                sel = sel + [path]
            self._selected_clip = path
        else:
            sel = [path]
            self._selected_clip = path
        self._selected_paths = sel
        for card in self._clip_cards:
            card.set_selected(card._path in sel)
        n = len(sel)
        if not self._pending_paths and hasattr(self, "_push_info"):
            self._push_info.setText(
                translate("Envoi : le clip sélectionné") + f" ({os.path.basename(path)})"
                if n <= 1 else f"{translate('Envoi :')} {n} {translate('clips sélectionnés')}")
        self._selected_lbl.setText(os.path.basename(path) if n <= 1
                                   else f"{n} clips sélectionnés")
        self._selected_lbl.setStyleSheet(
            f"color:{CP['accent']};font-size:9px;background:transparent;"
        )
        self._status_lbl.setText(
            f"Clip sélectionné : {os.path.basename(path)} · "
            "Clic gauche sur un slot pour le charger"
        )

    def _on_slot_load(self, layer: int, col: int):
        if not self._selected_clip:
            self._status_lbl.setText(
                "Sélectionnez d'abord un clip dans la bibliothèque gauche."
            )
            return

        clip_name = os.path.basename(self._selected_clip)

        if self._connected:
            self._status_lbl.setText(f"Chargement de '{clip_name}' → slot {layer}:{col}…")
            w = _LoadWorker(self._host, self._port, layer, col, self._selected_clip)
            w.success.connect(lambda l, c, n=clip_name: self._on_load_done(l, c, n))
            w.failed.connect(lambda e: self._status_lbl.setText(f"✗  {e}"))
            w.finished.connect(w.deleteLater)
            self._workers.append(w)
            w.start()
        else:
            self._on_load_done(layer, col, clip_name)

    def _on_load_done(self, layer: int, col: int, clip_name: str):
        btn = self._slot_widgets.get((layer, col))
        if btn:
            btn.set_clip(clip_name)
        suffix = "" if self._connected else " (mock — Resolume non connecté)"
        self._status_lbl.setText(f"✓  '{clip_name}' → slot {layer}:{col}{suffix}")

    def _drag_paths(self, origin_path: str) -> list:
        """Chemins à glisser : la sélection multiple si la carte en fait partie."""
        sel = getattr(self, "_selected_paths", [])
        if origin_path in sel and len(sel) > 1:
            order = [c._path for c in self._clip_cards]
            return [p for p in order if p in sel]
        return [origin_path]

    def _on_slot_drop(self, layer: int, col: int, text: str):
        """Dépôt d'un (ou plusieurs) clips sur un slot — slots consécutifs."""
        paths = [p for p in text.splitlines() if os.path.isfile(p)]
        if not paths:
            return
        if len(paths) == 1 and not self._connected:
            self._on_load_done(layer, col, os.path.basename(paths[0]))
            return
        if not self._connected:
            self._status_lbl.setText("✗  Connexion requise pour déposer plusieurs clips.")
            return
        from api.resolume_push import PushToResolumeWorker
        clips = [{"path": p, "name": os.path.splitext(os.path.basename(p))[0]}
                 for p in paths]
        w = PushToResolumeWorker(clips, layer=layer, start_column=col,
                                 host=self._host, port=self._port)
        self._workers.append(w)
        w.progress.connect(lambda _p, msg: self._status_lbl.setText(msg))
        w.finished.connect(lambda r: (self._status_lbl.setText(
            f"✓  {r.get('sent', 0)} clip(s) déposé(s) (couche {layer}, colonnes {col}+)"),
            self._fetch_layers()))
        w.failed.connect(lambda e: self._status_lbl.setText(f"✗  {e}"))
        w.start()

    def _on_slot_clear(self, layer: int, col: int):
        """Maj+clic sur un slot = le vider."""
        if not self._connected:
            self._status_lbl.setText("✗  Connexion requise pour vider un slot.")
            return
        w = _ClearWorker(self._host, self._port, layer, [col])
        w.done.connect(lambda n, l=layer, c=col: (
            self._status_lbl.setText(f"✓  Slot {l}:{c} vidé"), self._fetch_layers()))
        w.finished.connect(w.deleteLater)
        self._workers.append(w)
        w.start()

    def _on_clear_layer(self):
        """Vide TOUTE la couche choisie (spin Couche de l'envoi en file)."""
        if not self._connected:
            self._status_lbl.setText("✗  Connexion requise pour vider une couche.")
            return
        layer = self._push_layer.value()
        from PyQt6.QtWidgets import QMessageBox
        reply = QMessageBox.question(
            self, translate("Vider la couche"),
            translate("Vider TOUS les slots de la couche") + f" {layer} ?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        cols = [c for (l, c) in self._slot_widgets if l == layer]
        w = _ClearWorker(self._host, self._port, layer, sorted(cols))
        w.done.connect(lambda n, l=layer: (
            self._status_lbl.setText(f"✓  Couche {l} vidée ({n} slot(s))"),
            self._fetch_layers()))
        w.finished.connect(w.deleteLater)
        self._workers.append(w)
        w.start()

    def _on_slot_trigger(self, layer: int, col: int):
        if not self._connected:
            self._status_lbl.setText(
                "✗  Connexion à Resolume requise pour déclencher un clip."
            )
            return
        self._status_lbl.setText(f"Déclenchement slot {layer}:{col}…")
        w = _TriggerWorker(self._host, self._port, layer, col)
        w.done.connect(
            lambda ok, l=layer, c=col: self._status_lbl.setText(
                f"✓  Slot {l}:{c} déclenché" if ok else f"✗  Déclenchement échoué ({l}:{c})"
            )
        )
        w.finished.connect(w.deleteLater)
        self._workers.append(w)
        w.start()

    # ── Envoi en file (Vidéothèque → slots consécutifs) ────────────────────────

    def _conductor_bpm(self) -> float:
        """BPM du premier morceau analysé du conducteur (0 si aucun)."""
        try:
            import core.scenario as _sc
            for sc in _sc.list_scenarios():
                for t in sc.get("music_tracks", []) or []:
                    if isinstance(t, dict) and t.get("bpm"):
                        return float(t["bpm"])
        except Exception:
            pass
        return 0.0

    def queue_paths(self, paths: list):
        """Reçoit une file de clips (Vidéothèque « → Resolume »)."""
        self._pending_paths = [p for p in (paths or []) if p and os.path.isfile(p)]
        n = len(self._pending_paths)
        if n:
            self._push_info.setText(
                f"{n} " + translate("clip(s) reçus de la Vidéothèque"))
            self._push_info.setStyleSheet(
                f"color:{CP['accent']};font-size:9px;background:transparent;")
        else:
            self._push_info.setText(translate("Toute la bibliothèque"))
            self._push_info.setStyleSheet(
                f"color:{CP['text_secondary']};font-size:9px;background:transparent;")

    def _on_push_queue(self):
        """Envoie la file (ou toute la bibliothèque) vers les slots consécutifs."""
        # Priorité : file reçue de la Vidéothèque > clip sélectionné > toute la
        # bibliothèque (retour Matthieu : « ça envoie tous les plans » — la
        # sélection est désormais respectée et l'étiquette l'annonce).
        _sel = [p for p in getattr(self, "_selected_paths", []) if os.path.isfile(p)]
        if self._pending_paths:
            paths = list(self._pending_paths)
        elif _sel:
            paths = _sel
        elif self._selected_clip and os.path.isfile(self._selected_clip):
            paths = [self._selected_clip]
        else:
            paths = [c._path for c in self._clip_cards
                     if os.path.isfile(getattr(c, "_path", ""))]
        if not paths:
            self._status_lbl.setText("✗  Aucun clip à envoyer.")
            return
        # Ordre des colonnes = ordre NATUREL des noms (SQ1_P1 < SQ1_P2 < SQ7_P21),
        # pas l'ordre d'affichage de la bibliothèque (date) — vu en réel : le set
        # arrivait mélangé (SQ1_P2 avant SQ1_P1).
        import re as _re

        def _natural(p):
            base = os.path.basename(p).lower()
            return [int(t) if t.isdigit() else t for t in _re.split(r"(\d+)", base)]

        paths = sorted(paths, key=_natural)
        clips = [{"path": p, "name": os.path.splitext(os.path.basename(p))[0]}
                 for p in paths]

        # Répartition par acte : SQ1 → couche de départ, SQ2 → suivante, etc.
        if self._acte_layers_cb.isChecked():
            base_layer = self._push_layer.value()
            sq_order: list = []
            col_counter: dict = {}
            for c in clips:
                m = _re.search(r"sq(\d+)", c["name"].lower())
                sq = int(m.group(1)) if m else 0
                if sq not in sq_order:
                    sq_order.append(sq)
                lay = base_layer + sq_order.index(sq)
                col_counter[lay] = col_counter.get(lay, self._push_col.value() - 1) + 1
                c["layer"] = lay
                c["column"] = col_counter[lay]
        bpm = self._conductor_bpm() if self._push_bpm_cb.isChecked() else 0.0
        from api.resolume_push import PushToResolumeWorker
        self._host = self._host_input.text().strip() or self._host
        self._port = self._port_spin.value()
        w = PushToResolumeWorker(clips, layer=self._push_layer.value(),
                                 start_column=self._push_col.value(),
                                 bpm=bpm, host=self._host, port=self._port,
                                 show_mode=self._show_mode_cb.isChecked())
        self._push_worker = w
        self._btn_push.setEnabled(False)
        self._btn_push_cancel.setVisible(True)
        w.progress.connect(lambda _p, msg: self._status_lbl.setText(msg))
        w.finished.connect(self._on_push_done)
        w.failed.connect(self._on_push_failed)
        w.start()

    def _on_push_cancel(self):
        """Arrêt de l'envoi : le worker s'interrompt au prochain clip (parqué)."""
        if self._push_worker is not None:
            from core.worker import abandon_thread
            abandon_thread(self._push_worker)   # requestInterruption + signaux coupés
            self._push_worker = None
        self._btn_push.setEnabled(True)
        self._btn_push_cancel.setVisible(False)
        self._status_lbl.setText("■  Envoi vers Resolume annulé.")
        if self._connected:
            self._fetch_layers()   # la grille reflète les clips déjà chargés

    def _on_push_done(self, result: dict):
        self._btn_push.setEnabled(True)
        self._btn_push_cancel.setVisible(False)
        sent   = result.get("sent", 0)
        failed = result.get("failed", [])
        msg = (f"✓  {sent} clip(s) chargé(s) dans Resolume "
               f"(couche {result.get('layer', 1)}, colonnes "
               f"{result.get('first_column', 1)}+)")
        if failed:
            msg += f" · ⚠ {len(failed)} échec(s) : {', '.join(failed[:4])}"
        self._status_lbl.setText(msg)
        self._pending_paths = []
        self._push_info.setText(translate("Toute la bibliothèque"))
        if self._connected:
            self._fetch_layers()   # la grille reflète les nouveaux slots

    def _on_push_failed(self, msg: str):
        self._btn_push.setEnabled(True)
        self._btn_push_cancel.setVisible(False)
        self._status_lbl.setText(f"✗  {msg}")

    def _on_generate_calage(self):
        """Assistant de calage (aussi accessible depuis le Conducteur)."""
        from core.live_building import get_building_ref
        ref = get_building_ref()
        if not (ref and os.path.isfile(ref)):
            self._status_lbl.setText("✗  " + translate(
                "Choisis d'abord la façade du bâtiment (Conducteur → Référence bâtiment)."))
            return
        try:
            from core.live_mapping import generate_full_calage
            from core.context import get_data_root
            import core.scenario as _sc
            scs = _sc.list_scenarios()
            name = next((s.get("title", "") for s in scs if s.get("title")), "facade")
            res = generate_full_calage(ref, name, get_data_root())
            self._status_lbl.setText(
                f"▱  {translate('Calage généré')} ✓ — {len(res['points'])} points · "
                f"preset « {res['preset_name']} » (Advanced Output → Presets) · "
                f"mire : {os.path.basename(res['mire_path'])}")
            try:
                os.startfile(res["mire_path"])
            except OSError:
                pass
        except ValueError:
            self._status_lbl.setText("✗  " + translate(
                "Façade non détectée — utilise « Isoler (fond noir) » d'abord."))
        except Exception as e:
            self._status_lbl.setText(f"✗  {str(e)[:120]}")
