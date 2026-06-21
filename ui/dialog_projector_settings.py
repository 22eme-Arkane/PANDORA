"""
ui/dialog_projector_settings.py — Réglages d'un projecteur du Plan de feu.

Ouverte par clic droit → « Réglages du projecteur ». Les contrôles affichés
DÉPENDENT des capacités RÉELLES du modèle (core.projectors.capabilities) :
  · full     → intensité + température (CCT) + teinte (hue/sat) + ±vert
  · bicolor  → intensité + température (CCT) + ±vert
  · daylight → intensité + CCT fixe + gélatine
  · tungsten → intensité + CCT fixe + gélatine
  · source   → intensité (lueur) + CCT caractéristique (pratique du décor)

result_data() → dict de réglages, ou None si annulé.
"""

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QComboBox, QSlider,
    QFrame, QCheckBox,
)
from PyQt6.QtCore import Qt
from ui.styles import CP
from core.i18n import translate
import core.projectors as proj


class ProjectorSettingsDialog(QDialog):
    def __init__(self, parent=None, light: dict | None = None):
        super().__init__(parent)
        self._light = dict(light or {})
        self._cap = proj.capabilities(self._light.get("family", ""),
                                      self._light.get("model", ""))
        self._s = dict(proj.default_settings(self._light.get("family", ""),
                                             self._light.get("model", "")))
        self._s.update(self._light.get("settings") or {})
        self._result = None

        self.setWindowTitle(translate("Réglages du projecteur"))
        self.setMinimumWidth(440)
        self.setStyleSheet(f"background:{CP['bg1']};")

        root = QVBoxLayout(self)
        root.setContentsMargins(20, 18, 20, 18)
        root.setSpacing(12)

        # ── En-tête : nom + modèle + capacités ────────────────────────────────
        name = self._light.get("name") or self._light.get("model") or translate("Projecteur")
        title = QLabel("💡  " + name)
        title.setStyleSheet(
            f"color:{CP['text_primary']};font-size:15px;font-weight:700;background:transparent;")
        root.addWidget(title)

        model = self._light.get("model", "")
        fam   = proj.family_label(self._light.get("family", ""))
        lo, hi = self._cap["cct"]
        color_lbl = {
            "full": "couleur RGBWW", "bicolor": "blanc variable (bicolore)",
            "daylight": "lumière du jour (5600 K fixe)", "tungsten": "tungstène (3200 K fixe)",
            "source": "source pratique du décor",
        }.get(self._cap["color"], self._cap["color"])
        cct_txt = f"{lo}–{hi} K" if lo != hi else f"{lo} K"
        sub = QLabel(f"{model} · {fam} · {color_lbl} · {cct_txt} · IRC ~{self._cap['cri']}")
        sub.setWordWrap(True)
        sub.setStyleSheet(f"color:{CP['text_dim']};font-size:10px;background:transparent;")
        root.addWidget(sub)

        sep = QFrame(); sep.setFixedHeight(1); sep.setStyleSheet(f"background:{CP['border']};")
        root.addWidget(sep)

        # ── Intensité (toujours) ──────────────────────────────────────────────
        self._sl_int = self._slider_row(root, translate("Intensité"), 0, 100,
                                        int(self._s.get("intensity", 100)), suffix=" %")

        # ── Effet dynamique (LED couleur) — REMPLACE la couleur statique ───────
        self._fx_combo = self._effect_row(root) if self._cap.get("effects") else None

        # ── Température de couleur ─────────────────────────────────────────────
        self._sl_cct = None
        if self._cap["color"] in ("full", "bicolor") and lo != hi:
            self._sl_cct = self._slider_row(
                root, translate("Température"), lo, hi, int(self._s.get("cct", lo)),
                suffix=" K", step=50, fmt=lambda v: f"{v} K — {proj.kelvin_label(v)}")
        else:
            fixed = QLabel(f"{translate('Température')} : {lo} K — {proj.kelvin_label(lo)}"
                           + (f"  ({translate('fixe')})" if self._cap["color"] != "source" else ""))
            fixed.setStyleSheet(f"color:{CP['text_secondary']};font-size:11px;background:transparent;")
            root.addWidget(fixed)

        # ── Couleur / teinte selon le système du projecteur ───────────────────
        self._sl_hue = self._sl_sat = self._sl_gm = None
        self._gel_combo = None
        if self._cap["color"] == "full":
            self._sl_hue = self._slider_row(
                root, translate("Teinte"), 0, 360, int(self._s.get("hue", 0)),
                suffix="°", fmt=lambda v: f"{v}° — {proj._hue_label(v)}")
            self._sl_sat = self._slider_row(root, translate("Saturation"), 0, 100,
                                            int(self._s.get("saturation", 0)), suffix=" %")
            self._sl_gm = self._gm_row(root)
        elif self._cap["color"] == "bicolor":
            self._sl_gm = self._gm_row(root)
        elif self._cap["color"] in ("daylight", "tungsten"):
            self._gel_combo = self._gel_row(root)

        # ── Hauteur + inclinaison (direction VERTICALE de la lumière) ─────────
        self._sl_height = self._slider_row(
            root, translate("Hauteur"), 0, 24, int(round(float(self._s.get("height", 2.5)) * 2)),
            fmt=lambda v: f"{v / 2:g} m")
        self._sl_tilt = self._slider_row(
            root, translate("Inclinaison"), 0, 90, int(self._s.get("tilt", 90)),
            fmt=lambda v: (f"{v}° — horizontale" if v >= 85 else
                           (f"{v}° — légère plongée" if v >= 70 else
                            (f"{v}° — plongée" if v >= 40 else f"{v}° — forte plongée"))))
        self._louver_cb = None
        if self._cap.get("louver"):
            self._louver_cb = self._check_row(
                root, translate("Louver / nid d'abeille (faisceau resserré)"),
                bool(self._s.get("louver", False)))

        # ── Faisceau (fresnels zoomables, découpes, PAR/HMI) ──────────────────
        self._sl_beam = None
        beam = self._cap.get("beam")
        if beam:
            blo, bhi = beam
            if blo != bhi:
                self._sl_beam = self._slider_row(
                    root, translate("Faisceau"), blo, bhi, int(self._s.get("beam") or (blo + bhi) // 2),
                    suffix="°")
            else:
                fb = QLabel(f"{translate('Faisceau')} : {blo}°  ({translate('fixe')})")
                fb.setStyleSheet(f"color:{CP['text_secondary']};font-size:11px;background:transparent;")
                root.addWidget(fb)

        # Un effet actif REMPLACE les réglages de couleur statiques (CCT/teinte/gel).
        if self._fx_combo is not None:
            self._fx_combo.currentIndexChanged.connect(self._apply_fx_state)
            self._apply_fx_state()

        # ── Boutons ───────────────────────────────────────────────────────────
        btns = QHBoxLayout()
        btns.addStretch()
        cancel = QPushButton(translate("Annuler"))
        cancel.setStyleSheet(
            f"QPushButton{{background:{CP['bg3']};color:{CP['text_secondary']};"
            f"border:1px solid {CP['border']};border-radius:7px;font-size:12px;padding:7px 16px;}}"
            f"QPushButton:hover{{background:{CP['bg2']};}}")
        cancel.clicked.connect(self.reject)
        ok = QPushButton(translate("Valider"))
        ok.setStyleSheet(
            f"QPushButton{{background:{CP['accent']};color:#07080f;border:none;"
            f"border-radius:7px;font-size:12px;font-weight:700;padding:7px 18px;}}"
            f"QPushButton:hover{{background:#6eded6;}}")
        ok.clicked.connect(self._accept)
        btns.addWidget(cancel)
        btns.addWidget(ok)
        root.addLayout(btns)

    # ── Widgets ──────────────────────────────────────────────────────────────
    def _slider_row(self, root, label, lo, hi, val, suffix="", step=1, fmt=None):
        row = QVBoxLayout(); row.setSpacing(2)
        head = QHBoxLayout()
        lbl = QLabel(label)
        lbl.setStyleSheet(f"color:{CP['text_secondary']};font-size:11px;background:transparent;")
        val_lbl = QLabel("")
        val_lbl.setStyleSheet(f"color:{CP['accent']};font-size:11px;font-weight:700;background:transparent;")
        head.addWidget(lbl); head.addStretch(); head.addWidget(val_lbl)
        row.addLayout(head)
        sl = QSlider(Qt.Orientation.Horizontal)
        sl.setRange(lo, hi)
        if step > 1:
            sl.setSingleStep(step); sl.setPageStep(step)
        sl.setValue(max(lo, min(hi, val)))
        sl.setStyleSheet(
            f"QSlider::groove:horizontal{{height:4px;background:{CP['bg3']};border-radius:2px;}}"
            f"QSlider::handle:horizontal{{width:14px;margin:-6px 0;border-radius:7px;"
            f"background:{CP['accent']};}}"
            f"QSlider::sub-page:horizontal{{background:{CP['accent_dim']};border-radius:2px;}}")
        def _upd(v, _vl=val_lbl, _f=fmt, _sx=suffix):
            _vl.setText(_f(v) if _f else f"{v}{_sx}")
        sl.valueChanged.connect(_upd)
        _upd(sl.value())
        row.addWidget(sl)
        root.addLayout(row)
        return sl

    def _gm_row(self, root):
        # ±vert : -100 magenta … 0 neutre … +100 vert
        return self._slider_row(
            root, translate("Correction vert / magenta"), -100, 100,
            int(self._s.get("green_magenta", 0)),
            fmt=lambda v: ("neutre" if v == 0 else
                           (f"+{v} vert" if v > 0 else f"{v} magenta")))

    def _combo_style(self):
        return (
            f"QComboBox{{background:{CP['bg2']};color:{CP['text_primary']};"
            f"border:1px solid {CP['border']};border-radius:6px;padding:6px 10px;font-size:12px;}}"
            f"QComboBox QAbstractItemView{{background:{CP['bg3']};color:{CP['text_primary']};"
            f"selection-background-color:{CP['accent_dim']};}}")

    def _gel_row(self, root):
        lbl = QLabel(translate("Gélatine"))
        lbl.setStyleSheet(f"color:{CP['text_secondary']};font-size:11px;background:transparent;")
        root.addWidget(lbl)
        combo = QComboBox()
        for code, label in proj.GEL_PRESETS:
            combo.addItem(translate(label), code)
        i = combo.findData(self._s.get("gel", ""))
        if i >= 0:
            combo.setCurrentIndex(i)
        combo.setStyleSheet(self._combo_style())
        root.addWidget(combo)
        return combo

    def _effect_row(self, root):
        lbl = QLabel(translate("Effet dynamique"))
        lbl.setStyleSheet(f"color:{CP['text_secondary']};font-size:11px;background:transparent;")
        root.addWidget(lbl)
        combo = QComboBox()
        for code, label, _desc in proj.EFFECTS:
            combo.addItem(translate(label), code)
        i = combo.findData(self._s.get("effect", ""))
        if i >= 0:
            combo.setCurrentIndex(i)
        combo.setStyleSheet(self._combo_style())
        root.addWidget(combo)
        return combo

    def _check_row(self, root, label, checked):
        cb = QCheckBox(label)
        cb.setChecked(checked)
        cb.setStyleSheet(
            f"QCheckBox{{color:{CP['text_secondary']};font-size:11px;background:transparent;spacing:8px;}}"
            f"QCheckBox::indicator{{width:16px;height:16px;}}")
        root.addWidget(cb)
        return cb

    def _apply_fx_state(self):
        """Un effet actif REMPLACE les réglages de couleur → on les désactive."""
        active = bool(self._fx_combo and (self._fx_combo.currentData() or ""))
        for w in (self._sl_cct, self._sl_hue, self._sl_sat, self._sl_gm, self._gel_combo):
            if w is not None:
                w.setEnabled(not active)

    def _accept(self):
        s = dict(self._s)
        s["on"] = s.get("on", True)
        s["intensity"] = self._sl_int.value()
        if self._sl_cct is not None:
            s["cct"] = self._sl_cct.value()
        if self._sl_hue is not None:
            s["hue"] = self._sl_hue.value()
        if self._sl_sat is not None:
            s["saturation"] = self._sl_sat.value()
        if self._sl_gm is not None:
            s["green_magenta"] = self._sl_gm.value()
        if self._gel_combo is not None:
            s["gel"] = self._gel_combo.currentData() or ""
        if self._sl_beam is not None:
            s["beam"] = self._sl_beam.value()
        s["height"] = self._sl_height.value() / 2     # demi-mètres → mètres
        s["tilt"]   = self._sl_tilt.value()
        if self._louver_cb is not None:
            s["louver"] = self._louver_cb.isChecked()
        if self._fx_combo is not None:
            s["effect"] = self._fx_combo.currentData() or ""
        self._result = s
        self.accept()

    def result_data(self):
        return self._result
