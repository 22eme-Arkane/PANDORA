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
                "Vérifiez que Resolume est lancé et que le Webserver est activé "
                "(Préférences → Webserver)."
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


# ── Carte clip bibliothèque ────────────────────────────────────────────────────

class _ClipCard(QWidget):
    selected = pyqtSignal(str)

    def __init__(self, path: str):
        super().__init__()
        self._path   = path
        self._is_sel = False
        self.setFixedHeight(50)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._apply_style(False)

        lay = QHBoxLayout(self)
        lay.setContentsMargins(10, 0, 10, 0)
        lay.setSpacing(10)

        ico = QLabel("▶")
        ico.setFixedSize(22, 22)
        ico.setAlignment(Qt.AlignmentFlag.AlignCenter)
        ico.setStyleSheet(
            f"color:{CP['accent']};font-size:11px;"
            f"background:rgba(78,205,196,0.10);border-radius:4px;"
        )
        lay.addWidget(ico)

        col = QVBoxLayout()
        col.setSpacing(2)

        name = QLabel(os.path.basename(path))
        name.setStyleSheet(
            f"color:{CP['text_primary']};font-size:10px;font-weight:600;background:transparent;"
        )
        size_mb = os.path.getsize(path) / 1_000_000 if os.path.isfile(path) else 0
        meta = QLabel(f"{size_mb:.1f} MB")
        meta.setStyleSheet(f"color:{CP['text_dim']};font-size:9px;background:transparent;")
        col.addWidget(name)
        col.addWidget(meta)
        lay.addLayout(col, 1)

    def _apply_style(self, sel: bool):
        if sel:
            self.setStyleSheet(
                f"background:rgba(78,205,196,0.15);"
                f"border:1px solid {CP['accent_dim']};border-radius:8px;"
            )
        else:
            self.setStyleSheet(
                f"background:{CP['bg2']};border:1px solid {CP['border']};border-radius:8px;"
            )

    def set_selected(self, v: bool):
        self._is_sel = v
        self._apply_style(v)

    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            self.selected.emit(self._path)

    def enterEvent(self, e):
        if not self._is_sel:
            self.setStyleSheet(
                f"background:{CP['bg3']};"
                f"border:1px solid {CP['border_bright']};border-radius:8px;"
            )

    def leaveEvent(self, e):
        if not self._is_sel:
            self._apply_style(False)


# ── Bouton slot Resolume ───────────────────────────────────────────────────────

class _SlotBtn(QPushButton):
    load_req    = pyqtSignal(int, int)
    trigger_req = pyqtSignal(int, int)

    def __init__(self, layer: int, col: int, clip_name: str = ""):
        super().__init__()
        self._layer = layer
        self._col   = col
        self.setFixedSize(104, 60)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.set_clip(clip_name)

    def set_clip(self, name: str):
        self._clip = name
        if name:
            self.setText(name[:16] + ("…" if len(name) > 16 else ""))
            self.setToolTip(name)
            self.setStyleSheet(
                f"QPushButton{{background:rgba(78,205,196,0.12);color:{CP['accent']};"
                f"border:1px solid {CP['accent_dim']};border-radius:6px;"
                f"font-size:8px;font-weight:600;padding:3px;}}"
                f"QPushButton:hover{{background:rgba(78,205,196,0.22);}}"
            )
        else:
            self.setText(f"{self._layer} : {self._col}")
            self.setToolTip(f"Slot {self._layer}:{self._col} — vide\nClic gauche : charger · Clic droit : déclencher")
            self.setStyleSheet(
                f"QPushButton{{background:{CP['bg3']};color:{CP['text_dim']};"
                f"border:1px solid {CP['border']};border-radius:6px;"
                f"font-size:9px;padding:3px;}}"
                f"QPushButton:hover{{background:{CP['bg4']};"
                f"border-color:{CP['border_bright']};}}"
            )

    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
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
        bar.setFixedHeight(48)
        bar.setStyleSheet(
            f"background:{CP['bg1']};border-bottom:1px solid {CP['border']};"
        )
        lay = QHBoxLayout(bar)
        lay.setContentsMargins(20, 0, 20, 0)
        lay.setSpacing(12)

        conn_lbl = QLabel("Resolume")
        conn_lbl.setStyleSheet(
            f"color:{CP['text_dim']};font-size:11px;font-weight:600;"
            f"letter-spacing:1px;background:transparent;"
        )
        lay.addWidget(conn_lbl)

        self._dot = QLabel("●")
        self._dot.setStyleSheet(f"color:{CP['text_dim']};font-size:12px;background:transparent;")
        lay.addWidget(self._dot)

        self._host_input = QLineEdit(self._host)
        self._host_input.setFixedSize(130, 28)
        self._host_input.setStyleSheet(
            f"QLineEdit{{background:{CP['bg3']};border:1px solid {CP['border']};"
            f"border-radius:5px;color:{CP['text_primary']};font-size:11px;padding:0 8px;}}"
        )
        lay.addWidget(self._host_input)

        port_sep = QLabel(":")
        port_sep.setStyleSheet(f"color:{CP['text_dim']};background:transparent;")
        lay.addWidget(port_sep)

        self._port_spin = QSpinBox()
        self._port_spin.setRange(1024, 65535)
        self._port_spin.setValue(self._port)
        self._port_spin.setFixedSize(76, 28)
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

        return bar

    def _build_body(self) -> QWidget:
        body = QWidget()
        body.setStyleSheet("background:transparent;")
        lay = QHBoxLayout(body)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)

        # ── Bibliothèque gauche ────────────────────────────────────────────────
        lib = QWidget()
        lib.setFixedWidth(240)
        lib.setStyleSheet(
            f"background:{CP['bg1']};border-right:1px solid {CP['border']};"
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
            f"color:{CP['text_dim']};font-size:9px;font-style:italic;background:transparent;"
        )
        lib_lay.addWidget(self._selected_lbl)

        lib_scroll = QScrollArea()
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

        btn_refresh = QPushButton("↺  Actualiser")
        btn_refresh.setFixedHeight(28)
        btn_refresh.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_refresh.setStyleSheet(
            f"QPushButton{{background:transparent;color:{CP['text_secondary']};"
            f"border:1px solid {CP['border']};border-radius:5px;"
            f"font-size:10px;font-weight:700;}}"
            f"QPushButton:hover{{background:{CP['bg2']};}}"
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
                                           ("Col.", "_push_col", 1, 256)):
            lbl = QLabel(lbl_txt)
            lbl.setStyleSheet(
                f"color:{CP['text_secondary']};font-size:9px;background:transparent;")
            push_row.addWidget(lbl)
            spin = QSpinBox()
            spin.setRange(1, mx)
            spin.setValue(default)
            spin.setFixedSize(48, 24)
            spin.setStyleSheet(
                f"QSpinBox{{background:{CP['bg3']};border:1px solid {CP['border']};"
                f"border-radius:4px;color:{CP['text_primary']};font-size:10px;padding:0 2px;}}")
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

        self._btn_push = QPushButton("⇪  " + translate("Envoyer vers Resolume"))
        self._btn_push.setFixedHeight(30)
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

        lay.addWidget(lib)

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
        grid_hdr.addStretch()

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
            lbl.setStyleSheet(f"color:{CP['text_secondary']};font-size:10px;background:transparent;")
            gc_lay.addWidget(lbl)
            spin = QSpinBox()
            spin.setRange(1, max_val)
            spin.setValue(default)
            spin.setFixedSize(52, 24)
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
            f"color:{CP['text_dim']};font-size:9px;"
            f"font-family:'Consolas',monospace;background:transparent;"
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
            lyr_lbl = QLabel(layer.name[:14])
            lyr_lbl.setFixedSize(72, 60)
            lyr_lbl.setAlignment(
                Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
            )
            lyr_lbl.setStyleSheet(
                f"color:{CP['text_secondary']};font-size:10px;font-weight:600;"
                f"background:transparent;padding-right:6px;"
            )
            self._grid_layout.addWidget(lyr_lbl, i, 0)

            for clip in layer.clips:
                btn = _SlotBtn(clip.layer, clip.col, clip.name)
                btn.load_req.connect(self._on_slot_load)
                btn.trigger_req.connect(self._on_slot_trigger)
                self._slot_widgets[(clip.layer, clip.col)] = btn
                self._grid_layout.addWidget(btn, i, clip.col)

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
            lyr_lbl.setFixedSize(72, 60)
            lyr_lbl.setAlignment(
                Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
            )
            lyr_lbl.setStyleSheet(
                f"color:{CP['text_secondary']};font-size:10px;font-weight:600;"
                f"background:transparent;padding-right:6px;"
            )
            self._grid_layout.addWidget(lyr_lbl, i, 0)

            for j in range(1, n_cols + 1):
                btn = _SlotBtn(i, j)
                btn.load_req.connect(self._on_slot_load)
                btn.trigger_req.connect(self._on_slot_trigger)
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
        for c in self._clip_cards:
            c.deleteLater()
        self._clip_cards.clear()
        while self._lib_lay.count():
            item = self._lib_lay.takeAt(0)
            if item and item.widget():
                item.widget().deleteLater()

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
            for path in clips:
                card = _ClipCard(path)
                card.selected.connect(self._on_clip_selected)
                self._clip_cards.append(card)
                self._lib_lay.addWidget(card)

        if not self._connected:
            self._rebuild_grid()

    # ── Interactions ───────────────────────────────────────────────────────────

    def _on_clip_selected(self, path: str):
        self._selected_clip = path
        for card in self._clip_cards:
            card.set_selected(card._path == path)
        self._selected_lbl.setText(os.path.basename(path))
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
        paths = self._pending_paths or [c._path for c in self._clip_cards
                                        if os.path.isfile(getattr(c, "_path", ""))]
        if not paths:
            self._status_lbl.setText("✗  Aucun clip à envoyer.")
            return
        # L'ordre Vidéothèque/bibliothèque = ordre des colonnes (P1, P2…)
        clips = [{"path": p, "name": os.path.splitext(os.path.basename(p))[0]}
                 for p in paths]
        bpm = self._conductor_bpm() if self._push_bpm_cb.isChecked() else 0.0
        from api.resolume_push import PushToResolumeWorker
        self._host = self._host_input.text().strip() or self._host
        self._port = self._port_spin.value()
        w = PushToResolumeWorker(clips, layer=self._push_layer.value(),
                                 start_column=self._push_col.value(),
                                 bpm=bpm, host=self._host, port=self._port)
        self._push_worker = w
        self._btn_push.setEnabled(False)
        w.progress.connect(lambda _p, msg: self._status_lbl.setText(msg))
        w.finished.connect(self._on_push_done)
        w.failed.connect(self._on_push_failed)
        w.start()

    def _on_push_done(self, result: dict):
        self._btn_push.setEnabled(True)
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
        self._status_lbl.setText(f"✗  {msg}")
