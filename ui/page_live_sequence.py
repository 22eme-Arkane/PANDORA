"""
ui/page_live_sequence.py — Page Séquences (Live ou Mapping) de PANDORA | Live.

Découpage type storyboard, paramétré par `kind` :
  - "live"    → Séquences Live    : valeurs de plan + mouvements
  - "mapping" → Séquences Mapping : source de mapping (façade) + raccord continu,
                caméra fixe (mouvements masqués)

Master-détail : liste des segments à gauche, éditeur à droite.
Données : core/live_sequences.py (isolé par projet).
"""

import os

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QLineEdit,
    QTextEdit, QComboBox, QSlider, QScrollArea, QFrame, QCheckBox, QFileDialog,
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPixmap

from ui.styles import CP
from core.i18n import translate
import core.live_sequences as lseq

_SHOT_SIZES = ["", "Plan d'ensemble", "Plan large", "Plan moyen",
               "Plan rapproché", "Gros plan", "Très gros plan"]
_MOVEMENTS  = ["", "Fixe", "Panoramique", "Travelling", "Zoom avant",
               "Zoom arrière", "Plongée", "Contre-plongée"]


class PageLiveSequence(QWidget):
    def __init__(self, kind: str):
        super().__init__()
        self._kind = kind if kind in ("live", "mapping") else "live"
        self._is_mapping = (self._kind == "mapping")
        self._data = lseq.load(self._kind)
        self._current_idx: int | None = None

        self.setStyleSheet(f"background:{CP['bg0']};")
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        if self._is_mapping:
            root.addWidget(self._build_mapping_bar())

        body = QHBoxLayout()
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(0)
        body.addWidget(self._build_list_panel())
        body.addWidget(self._build_editor_panel(), 1)
        _wrap = QWidget()
        _wrap.setLayout(body)
        root.addWidget(_wrap, 1)

        self._reload_list()
        self._set_editor_enabled(False)

    # ── Barre mapping (source + raccord) ───────────────────────────────────────

    def _build_mapping_bar(self) -> QWidget:
        bar = QFrame()
        bar.setStyleSheet(f"background:{CP['bg1']};border-bottom:1px solid {CP['border']};")
        lay = QHBoxLayout(bar)
        lay.setContentsMargins(20, 12, 20, 12)
        lay.setSpacing(14)

        lbl = QLabel(translate("Source de mapping :"))
        lbl.setStyleSheet(f"color:{CP['text_secondary']};font-size:12px;background:transparent;border:none;")
        lay.addWidget(lbl)

        self._map_thumb = QLabel()
        self._map_thumb.setFixedSize(72, 44)
        self._map_thumb.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._map_thumb.setStyleSheet(
            f"background:{CP['bg3']};border:1px solid {CP['border']};border-radius:6px;color:{CP['text_dim']};"
        )
        lay.addWidget(self._map_thumb)

        btn_pick = QPushButton(translate("Choisir la façade…"))
        btn_pick.setFixedHeight(32)
        btn_pick.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_pick.setStyleSheet(
            f"QPushButton{{background:transparent;color:{CP['accent2']};"
            f"border:1px solid {CP['accent2']};border-radius:7px;font-size:11px;font-weight:700;padding:0 14px;}}"
            f"QPushButton:hover{{background:rgba(124,107,255,0.12);}}"
        )
        btn_pick.clicked.connect(self._pick_mapping_source)
        lay.addWidget(btn_pick)

        self._cb_continuous = QCheckBox(translate("Raccord continu (un seul plan long)"))
        self._cb_continuous.setStyleSheet(f"color:{CP['text_secondary']};font-size:12px;background:transparent;")
        self._cb_continuous.stateChanged.connect(self._on_continuous_changed)
        lay.addWidget(self._cb_continuous)
        lay.addStretch()
        return bar

    def _refresh_mapping_bar(self):
        src = self._data.get("mapping_source", "")
        if src and os.path.isfile(src):
            self._map_thumb.setPixmap(QPixmap(src).scaled(
                72, 44, Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                Qt.TransformationMode.SmoothTransformation))
        else:
            self._map_thumb.setText(translate("Aucune"))
        self._cb_continuous.blockSignals(True)
        self._cb_continuous.setChecked(bool(self._data.get("continuous", True)))
        self._cb_continuous.blockSignals(False)

    def _pick_mapping_source(self):
        path, _ = QFileDialog.getOpenFileName(
            self, translate("Choisir la façade à mapper"), "",
            "Images (*.png *.jpg *.jpeg *.webp *.bmp)")
        if path:
            self._data["mapping_source"] = path
            lseq.save(self._kind, self._data)
            self._refresh_mapping_bar()

    def _on_continuous_changed(self):
        self._data["continuous"] = self._cb_continuous.isChecked()
        lseq.save(self._kind, self._data)

    # ── Liste des segments ─────────────────────────────────────────────────────

    def _build_list_panel(self) -> QWidget:
        panel = QWidget()
        panel.setFixedWidth(300)
        panel.setStyleSheet(f"background:{CP['bg1']};border-right:1px solid {CP['border']};")
        lay = QVBoxLayout(panel)
        lay.setContentsMargins(16, 18, 16, 16)
        lay.setSpacing(12)

        title = QLabel(translate("Séquences Mapping") if self._is_mapping else translate("Séquences Live"))
        title.setStyleSheet(
            f"color:{CP['text_primary']};font-size:18px;font-weight:800;background:transparent;border:none;"
        )
        lay.addWidget(title)

        btn_add = QPushButton("＋  " + translate("Ajouter un plan"))
        btn_add.setFixedHeight(36)
        btn_add.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_add.setStyleSheet(
            f"QPushButton{{background:transparent;color:{CP['accent2']};"
            f"border:1.5px solid {CP['accent2']};border-radius:8px;font-size:12px;font-weight:700;}}"
            f"QPushButton:hover{{background:rgba(124,107,255,0.12);}}"
        )
        btn_add.clicked.connect(self._on_add)
        lay.addWidget(btn_add)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet("QScrollArea{background:transparent;border:none;}")
        self._list_container = QWidget()
        self._list_container.setStyleSheet("background:transparent;")
        self._list_lay = QVBoxLayout(self._list_container)
        self._list_lay.setContentsMargins(0, 0, 0, 0)
        self._list_lay.setSpacing(6)
        self._list_lay.setAlignment(Qt.AlignmentFlag.AlignTop)
        scroll.setWidget(self._list_container)
        lay.addWidget(scroll, 1)
        return panel

    def _segments(self) -> list:
        return self._data.get("segments", [])

    def _reload_list(self):
        if self._is_mapping:
            self._refresh_mapping_bar()
        while self._list_lay.count():
            it = self._list_lay.takeAt(0)
            if it.widget():
                it.widget().deleteLater()
        segs = self._segments()
        if not segs:
            empty = QLabel(translate("Aucun plan. Cliquez « + » ou générez le découpage depuis le Conducteur."))
            empty.setWordWrap(True)
            empty.setStyleSheet(f"color:{CP['text_dim']};font-size:11px;background:transparent;")
            self._list_lay.addWidget(empty)
            return
        for i, seg in enumerate(segs):
            self._list_lay.addWidget(self._make_row(i, seg))

    def _make_row(self, idx: int, seg: dict) -> QWidget:
        row = QPushButton()
        row.setCursor(Qt.CursorShape.PointingHandCursor)
        row.setFixedHeight(50)
        active = (self._current_idx == idx)
        row.setStyleSheet(
            f"QPushButton{{background:{'rgba(124,107,255,0.15)' if active else CP['bg2']};"
            f"color:{CP['text_primary']};text-align:left;padding:0 12px;"
            f"border:1px solid {CP['accent2'] if active else CP['border']};border-radius:8px;"
            f"font-size:12px;font-weight:600;}}"
            f"QPushButton:hover{{border-color:{CP['border_bright']};}}"
        )
        action = (seg.get("action", "") or translate("(plan sans description)"))[:34]
        row.setText(f"{seg.get('number', idx + 1)}.  {action}")
        row.clicked.connect(lambda: self._select(idx))
        return row

    # ── Éditeur ────────────────────────────────────────────────────────────────

    def _build_editor_panel(self) -> QWidget:
        panel = QScrollArea()
        panel.setWidgetResizable(True)
        panel.setStyleSheet("QScrollArea{background:transparent;border:none;}")
        inner = QWidget()
        inner.setStyleSheet("background:transparent;")
        panel.setWidget(inner)
        lay = QVBoxLayout(inner)
        lay.setContentsMargins(32, 24, 32, 24)
        lay.setSpacing(14)

        def _lbl(t):
            l = QLabel(translate(t))
            l.setStyleSheet(f"color:{CP['text_secondary']};font-size:11px;background:transparent;border:none;")
            return l

        _field = (
            f"QLineEdit,QTextEdit,QComboBox{{background:{CP['bg3']};border:1px solid {CP['border']};"
            f"border-radius:6px;color:{CP['text_primary']};font-size:13px;padding:6px 10px;}}"
            f"QLineEdit:focus,QTextEdit:focus{{border-color:{CP['accent2']};}}"
            f"QComboBox QAbstractItemView{{background:{CP['bg3']};color:{CP['text_primary']};"
            f"selection-background-color:{CP['accent2']};}}"
        )

        self._ed_title = QLabel(translate("Aucun plan sélectionné"))
        self._ed_title.setStyleSheet(
            f"color:{CP['text_primary']};font-size:18px;font-weight:800;background:transparent;border:none;"
        )
        lay.addWidget(self._ed_title)

        lay.addWidget(_lbl("Action"))
        self._action = QLineEdit()
        self._action.setFixedHeight(38)
        self._action.setStyleSheet(_field)
        self._action.textChanged.connect(self._on_field_changed)
        lay.addWidget(self._action)

        # Valeur de plan + mouvement (masqués en mapping)
        self._row_film = QWidget()
        rf = QHBoxLayout(self._row_film)
        rf.setContentsMargins(0, 0, 0, 0)
        rf.setSpacing(16)
        col1 = QVBoxLayout(); col1.setSpacing(6)
        col1.addWidget(_lbl("Valeur de plan"))
        self._shot = QComboBox(); self._shot.setStyleSheet(_field)
        for s in _SHOT_SIZES:
            self._shot.addItem(translate(s) if s else "—", s)
        self._shot.currentIndexChanged.connect(self._on_field_changed)
        col1.addWidget(self._shot)
        rf.addLayout(col1, 1)
        col2 = QVBoxLayout(); col2.setSpacing(6)
        col2.addWidget(_lbl("Mouvement"))
        self._move = QComboBox(); self._move.setStyleSheet(_field)
        for m in _MOVEMENTS:
            self._move.addItem(translate(m) if m else "—", m)
        self._move.currentIndexChanged.connect(self._on_field_changed)
        col2.addWidget(self._move)
        rf.addLayout(col2, 1)
        lay.addWidget(self._row_film)
        self._row_film.setVisible(not self._is_mapping)

        # Durée
        self._dur_lbl = QLabel(translate("Durée :") + " 5 s")
        self._dur_lbl.setStyleSheet(f"color:{CP['text_secondary']};font-size:11px;background:transparent;")
        lay.addWidget(self._dur_lbl)
        self._dur = QSlider(Qt.Orientation.Horizontal)
        self._dur.setMinimum(4); self._dur.setMaximum(15); self._dur.setValue(5)
        self._dur.setStyleSheet(
            f"QSlider::groove:horizontal{{height:4px;background:{CP['bg3']};border-radius:2px;}}"
            f"QSlider::handle:horizontal{{width:14px;height:14px;background:{CP['accent2']};"
            f"border-radius:7px;margin:-5px 0;}}"
            f"QSlider::sub-page:horizontal{{background:{CP['accent2']};border-radius:2px;}}"
        )
        self._dur.valueChanged.connect(lambda v: self._dur_lbl.setText(translate("Durée :") + f" {v} s"))
        self._dur.valueChanged.connect(self._on_field_changed)
        lay.addWidget(self._dur)

        lay.addWidget(_lbl("Prompt"))
        self._prompt = QTextEdit()
        self._prompt.setMinimumHeight(80)
        self._prompt.setMaximumHeight(140)
        self._prompt.setStyleSheet(_field)
        self._prompt.textChanged.connect(self._on_field_changed)
        lay.addWidget(self._prompt)

        lay.addStretch()

        actions = QHBoxLayout(); actions.setSpacing(10)
        for label, slot in (("↑", self._move_up), ("↓", self._move_down)):
            b = QPushButton(label)
            b.setFixedSize(40, 36)
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.setStyleSheet(
                f"QPushButton{{background:{CP['bg2']};color:{CP['text_secondary']};"
                f"border:1px solid {CP['border']};border-radius:7px;font-size:14px;font-weight:700;}}"
                f"QPushButton:hover{{color:{CP['text_primary']};border-color:{CP['border_bright']};}}"
            )
            b.clicked.connect(slot)
            actions.addWidget(b)
        actions.addStretch()
        self._btn_delete = QPushButton(translate("Supprimer ce plan"))
        self._btn_delete.setFixedHeight(36)
        self._btn_delete.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_delete.setStyleSheet(
            f"QPushButton{{background:transparent;color:#e05c5c;border:1px solid rgba(224,92,92,0.5);"
            f"border-radius:7px;font-size:11px;font-weight:700;padding:0 16px;}}"
            f"QPushButton:hover{{background:rgba(224,92,92,0.10);}}"
        )
        self._btn_delete.clicked.connect(self._on_delete)
        actions.addWidget(self._btn_delete)
        lay.addLayout(actions)
        return panel

    # ── Sélection / édition ─────────────────────────────────────────────────────

    def _set_editor_enabled(self, on: bool):
        for w in (self._action, self._shot, self._move, self._dur, self._prompt, self._btn_delete):
            w.setEnabled(on)

    def _select(self, idx: int):
        segs = self._segments()
        if not (0 <= idx < len(segs)):
            return
        self._current_idx = idx
        seg = segs[idx]
        self._loading = True
        self._action.setText(seg.get("action", ""))
        self._shot.setCurrentIndex(max(0, _SHOT_SIZES.index(seg.get("shot_size", "")) if seg.get("shot_size", "") in _SHOT_SIZES else 0))
        self._move.setCurrentIndex(max(0, _MOVEMENTS.index(seg.get("camera_movement", "")) if seg.get("camera_movement", "") in _MOVEMENTS else 0))
        self._dur.setValue(int(seg.get("duration", 5) or 5))
        self._prompt.setPlainText(seg.get("prompt", ""))
        self._dur_lbl.setText(translate("Durée :") + f" {self._dur.value()} s")
        self._ed_title.setText(translate("Plan") + f" {seg.get('number', idx + 1)}")
        self._loading = False
        self._set_editor_enabled(True)
        self._reload_list()

    def _on_add(self):
        segs = self._segments()
        segs.append(lseq.new_segment(len(segs) + 1))
        self._data["segments"] = segs
        lseq.save(self._kind, self._data)
        self._reload_list()
        self._select(len(segs) - 1)

    def _on_field_changed(self):
        if getattr(self, "_loading", False) or self._current_idx is None:
            return
        seg = self._segments()[self._current_idx]
        seg["action"]          = self._action.text().strip()
        seg["shot_size"]       = self._shot.currentData() or ""
        seg["camera_movement"] = self._move.currentData() or ""
        seg["duration"]        = self._dur.value()
        seg["prompt"]          = self._prompt.toPlainText().strip()
        lseq.save(self._kind, self._data)

    def _on_delete(self):
        if self._current_idx is None:
            return
        segs = self._segments()
        del segs[self._current_idx]
        for i, s in enumerate(segs, 1):
            s["number"] = i
        self._data["segments"] = segs
        lseq.save(self._kind, self._data)
        self._current_idx = None
        self._set_editor_enabled(False)
        self._action.clear(); self._prompt.clear()
        self._ed_title.setText(translate("Aucun plan sélectionné"))
        self._reload_list()

    def _swap(self, i: int, j: int):
        segs = self._segments()
        if not (0 <= i < len(segs) and 0 <= j < len(segs)):
            return
        segs[i], segs[j] = segs[j], segs[i]
        for k, s in enumerate(segs, 1):
            s["number"] = k
        self._data["segments"] = segs
        lseq.save(self._kind, self._data)
        self._current_idx = j
        self._reload_list()
        self._select(j)

    def _move_up(self):
        if self._current_idx is not None:
            self._swap(self._current_idx, self._current_idx - 1)

    def _move_down(self):
        if self._current_idx is not None:
            self._swap(self._current_idx, self._current_idx + 1)
