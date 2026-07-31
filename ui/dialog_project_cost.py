"""Fenêtre « Coût du projet » — chaque opération facturée, et le total.

Demande Matthieu 2026-07-31 : voir tout l'historique des générations du projet
— IA de texte, moteurs d'image, moteurs vidéo — avec le prix de chacune, et un
total en bas.

Les montants sont des ESTIMATIONS et la fenêtre le dit franchement : PANDORA
connaît les grilles annoncées par les fournisseurs, pas la facture réelle.
"""

from __future__ import annotations

import time

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QScrollArea,
    QWidget, QFrame, QComboBox,
)
from PyQt6.QtCore import Qt

from ui.styles import CP
from core.i18n import translate
from core import spend as _spend

_KIND_LABEL = {
    _spend.KIND_VIDEO: "Vidéo",
    _spend.KIND_IMAGE: "Image",
    _spend.KIND_TEXT:  "Texte (IA)",
    _spend.KIND_AUDIO: "Audio",
    _spend.KIND_OTHER: "Autre",
}
_KIND_ICON = {
    _spend.KIND_VIDEO: "🎬", _spend.KIND_IMAGE: "🖼",
    _spend.KIND_TEXT: "✍", _spend.KIND_AUDIO: "🎙", _spend.KIND_OTHER: "•",
}


class ProjectCostDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(translate("Coût du projet"))
        self.setMinimumSize(880, 620)
        self.setStyleSheet(f"QDialog{{background:{CP['bg1']};}}")

        self._items = _spend.load()

        root = QVBoxLayout(self)
        root.setContentsMargins(22, 18, 22, 16)
        root.setSpacing(10)

        title = QLabel("💰  " + translate("Coût du projet"))
        title.setStyleSheet(
            f"color:{CP['text_primary']};font-size:17px;font-weight:800;"
            f"letter-spacing:1px;background:transparent;")
        root.addWidget(title)

        sub = QLabel(translate(
            "Chaque opération facturée depuis la création du projet. Les montants "
            "sont ESTIMÉS d'après les grilles annoncées par les fournisseurs — un "
            "essai refusé, une remise ou un changement de tarif peuvent écarter ce "
            "total de votre relevé réel."))
        sub.setWordWrap(True)
        sub.setStyleSheet(
            f"color:{CP['text_dim']};font-size:10px;background:transparent;")
        root.addWidget(sub)

        # ── Filtre par famille ────────────────────────────────────────────────
        bar = QHBoxLayout()
        bar.setSpacing(8)
        _f = QLabel(translate("Afficher"))
        _f.setStyleSheet(f"color:{CP['text_secondary']};font-size:11px;"
                         f"background:transparent;")
        bar.addWidget(_f)
        self._filter = QComboBox()
        self._filter.addItem(translate("Tout"), "")
        for _k, _lbl in _KIND_LABEL.items():
            self._filter.addItem(translate(_lbl), _k)
        self._filter.setFixedHeight(28)
        self._filter.setStyleSheet(
            f"QComboBox{{background:{CP['bg3']};border:1px solid {CP['border']};"
            f"border-radius:6px;color:{CP['text_primary']};font-size:11px;padding:0 10px;}}"
            f"QComboBox QAbstractItemView{{background:{CP['bg3']};"
            f"border:1px solid {CP['border_bright']};color:{CP['text_primary']};"
            f"selection-background-color:{CP['accent_dim']};}}")
        self._filter.currentIndexChanged.connect(self._fill)
        bar.addWidget(self._filter)
        bar.addStretch()
        root.addLayout(bar)

        # ── Liste ─────────────────────────────────────────────────────────────
        _sc = QScrollArea()
        _sc.setWidgetResizable(True)
        _sc.setStyleSheet("QScrollArea{background:transparent;border:none;}")
        self._inner = QWidget()
        self._inner.setStyleSheet("background:transparent;")
        self._lay = QVBoxLayout(self._inner)
        self._lay.setContentsMargins(0, 0, 0, 0)
        self._lay.setSpacing(1)
        self._lay.setAlignment(Qt.AlignmentFlag.AlignTop)
        _sc.setWidget(self._inner)
        root.addWidget(_sc, 1)

        # ── Total ─────────────────────────────────────────────────────────────
        _sep = QFrame()
        _sep.setFixedHeight(1)
        _sep.setStyleSheet(f"background:{CP['border']};")
        root.addWidget(_sep)

        self._total_lbl = QLabel("")
        self._total_lbl.setStyleSheet(
            f"color:{CP['accent']};font-size:16px;font-weight:800;"
            f"background:transparent;")
        self._detail_lbl = QLabel("")
        self._detail_lbl.setWordWrap(True)
        self._detail_lbl.setStyleSheet(
            f"color:{CP['text_dim']};font-size:10px;background:transparent;")
        _foot = QHBoxLayout()
        _fcol = QVBoxLayout()
        _fcol.setSpacing(2)
        _fcol.addWidget(self._total_lbl)
        _fcol.addWidget(self._detail_lbl)
        _foot.addLayout(_fcol, 1)
        _btn = QPushButton(translate("Fermer"))
        _btn.setFixedHeight(32)
        _btn.setCursor(Qt.CursorShape.PointingHandCursor)
        _btn.setStyleSheet(
            f"QPushButton{{background:transparent;color:{CP['text_secondary']};"
            f"border:1px solid {CP['border']};border-radius:6px;"
            f"font-size:11px;padding:0 18px;}}"
            f"QPushButton:hover{{color:{CP['text_primary']};"
            f"border-color:{CP['border_bright']};}}")
        _btn.clicked.connect(self.accept)
        _foot.addWidget(_btn)
        root.addLayout(_foot)

        from ui.widgets import disable_default_buttons
        disable_default_buttons(self)
        self._fill()

    # ── Contenu ───────────────────────────────────────────────────────────────

    def _fill(self):
        while self._lay.count():
            _it = self._lay.takeAt(0)
            if _it.widget():
                _it.widget().deleteLater()

        _k = self._filter.currentData() or ""
        _items = [e for e in self._items if not _k or e.get("kind") == _k]

        if not _items:
            _e = QLabel(translate(
                "Aucune dépense enregistrée pour ce projet.\n\nLes générations "
                "lancées à partir de maintenant apparaîtront ici."))
            _e.setAlignment(Qt.AlignmentFlag.AlignCenter)
            _e.setStyleSheet(f"color:{CP['text_dim']};font-size:12px;"
                             f"background:transparent;padding:40px;")
            self._lay.addWidget(_e)
        else:
            for e in _items:
                self._lay.addWidget(self._row(e))

        _t = _spend.total_usd(_items)
        self._total_lbl.setText(
            translate("Total estimé") + f"   ${_t:,.2f}"
            + (f"   ({len(_items)} " + translate("opérations") + ")" if _items else ""))
        _par = _spend.totals_by_kind(_items)
        self._detail_lbl.setText("   ·   ".join(
            f"{translate(_KIND_LABEL.get(k, k))} ${c:,.2f} ({n})"
            for k, (n, c) in sorted(_par.items(), key=lambda kv: -kv[1][1])) or "")

    def _row(self, e: dict) -> QWidget:
        w = QFrame()
        w.setStyleSheet(
            f"QFrame{{background:transparent;border:none;"
            f"border-bottom:1px solid {CP['border']};}}"
            f"QFrame:hover{{background:{CP['bg2']};}}")
        lay = QHBoxLayout(w)
        lay.setContentsMargins(10, 7, 10, 7)
        lay.setSpacing(10)

        _ic = QLabel(_KIND_ICON.get(e.get("kind"), "•"))
        _ic.setFixedWidth(20)
        _ic.setStyleSheet("background:transparent;border:none;font-size:12px;")
        lay.addWidget(_ic)

        _col = QVBoxLayout()
        _col.setSpacing(1)
        _t = QLabel(e.get("label") or translate("Opération"))
        _t.setStyleSheet(f"color:{CP['text_primary']};font-size:12px;"
                         f"background:transparent;border:none;")
        _col.addWidget(_t)
        _bits = [b for b in (e.get("engine"), e.get("detail")) if b]
        _d = QLabel("  ·  ".join(_bits))
        _d.setStyleSheet(f"color:{CP['text_dim']};font-size:9px;"
                         f"font-family:'Consolas',monospace;"
                         f"background:transparent;border:none;")
        _col.addWidget(_d)
        lay.addLayout(_col, 1)

        try:
            _when = time.strftime("%d/%m/%Y  %H:%M",
                                  time.localtime(float(e.get("ts") or 0)))
        except Exception:
            _when = ""
        _dt = QLabel(_when)
        _dt.setStyleSheet(f"color:{CP['text_dim']};font-size:10px;"
                          f"background:transparent;border:none;")
        lay.addWidget(_dt)

        _c = float(e.get("cost_usd") or 0.0)
        _cl = QLabel(("≈ " if e.get("estimated") else "") + f"${_c:,.4f}".rstrip("0").rstrip(".")
                     if _c else "—")
        _cl.setFixedWidth(96)
        _cl.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        _cl.setStyleSheet(
            f"color:{CP['text_primary'] if _c else CP['text_dim']};font-size:12px;"
            f"font-weight:700;background:transparent;border:none;")
        lay.addWidget(_cl)
        return w
