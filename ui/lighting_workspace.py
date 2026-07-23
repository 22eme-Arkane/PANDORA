"""Composants de la nouvelle interface du Plan de feu.

Ce module reste volontairement visuel : le modèle, la persistance et la
synchronisation Storyboard restent dans ``core.staging`` et ``PageLighting``.
"""

from __future__ import annotations

import os

from PyQt6.QtCore import Qt, QSize, pyqtSignal
from PyQt6.QtGui import QIcon, QPixmap
from PyQt6.QtWidgets import (
    QButtonGroup, QCheckBox, QComboBox, QDoubleSpinBox, QFrame, QHBoxLayout,
    QLabel, QLineEdit, QPushButton, QScrollArea, QSlider, QSpinBox, QToolButton,
    QVBoxLayout, QWidget,
)

import core.projectors as projectors
import core.storyboard as storyboard
from core.i18n import translate
from ui.icons import load_icon
from ui.styles import CP


def active_mood_path(shot_id: str) -> str:
    """Retourne le mood actif d'un plan, sans modifier les données."""
    try:
        data = storyboard.load_apercus(shot_id)
        paths = [p for p in data.get("paths", []) if p and os.path.isfile(p)]
        if not paths:
            return ""
        idx = max(0, min(int(data.get("active_idx", 0) or 0), len(paths) - 1))
        return paths[idx]
    except Exception:
        return ""


def sequence_label(shot: dict) -> str:
    num = shot.get("seq_num") or shot.get("sequence") or ""
    name = (shot.get("seq_name") or "").strip()
    if num and name:
        return f"S{num} · {name}"
    if num:
        return f"S{num}"
    return name or translate("Sans séquence")


class LightingShotCard(QWidget):
    """Carte compacte d'un plan avec le mood actif."""

    def __init__(self, shot: dict, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.setStyleSheet("background:transparent;border:none;")

        row = QHBoxLayout(self)
        row.setContentsMargins(7, 6, 7, 6)
        row.setSpacing(9)

        thumb = QLabel()
        thumb.setFixedSize(72, 50)
        thumb.setAlignment(Qt.AlignmentFlag.AlignCenter)
        path = active_mood_path(shot.get("id", ""))
        if path:
            pix = QPixmap(path).scaled(
                72, 50, Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                Qt.TransformationMode.SmoothTransformation,
            )
            pix = pix.copy(max(0, (pix.width() - 72) // 2),
                           max(0, (pix.height() - 50) // 2), 72, 50)
            thumb.setPixmap(pix)
            thumb.setStyleSheet(f"background:{CP['bg3']};border-radius:5px;")
        else:
            thumb.setText("MOOD")
            thumb.setStyleSheet(
                f"background:{CP['bg3']};border:1px solid {CP['border']};"
                f"border-radius:5px;color:{CP['text_dim']};font-size:8px;font-weight:700;"
            )
        row.addWidget(thumb)

        info = QVBoxLayout()
        info.setSpacing(2)
        num = shot.get("number", "?")
        seq = sequence_label(shot)
        title = (shot.get("scene_title") or shot.get("name") or translate("Plan")).strip()
        top = QLabel(f"{seq}  ·  P{num}")
        top.setStyleSheet(
            f"color:{CP['text_primary']};font-size:10px;font-weight:800;"
            "background:transparent;border:none;"
        )
        name = QLabel(title[:34])
        name.setStyleSheet(
            f"color:{CP['text_secondary']};font-size:9px;font-weight:600;"
            "background:transparent;border:none;"
        )
        tags = []
        if shot.get("shot_size"):
            tags.append(str(shot["shot_size"]))
        if shot.get("focal"):
            tags.append(str(shot["focal"]))
        if shot.get("duration"):
            tags.append(f"{shot['duration']}s")
        meta = QLabel("   ".join(tags) or translate("Plan du storyboard"))
        meta.setStyleSheet(
            f"color:{CP['accent_dim']};font-size:8px;background:transparent;border:none;"
        )
        info.addWidget(top)
        info.addWidget(name)
        info.addWidget(meta)
        row.addLayout(info, 1)


class LightingToolbar(QFrame):
    """Barre d'outils verticale, entièrement reliée au canevas."""

    tool_changed = pyqtSignal(str)
    add_light_requested = pyqtSignal()
    add_actor_requested = pyqtSignal()
    place_camera_requested = pyqtSignal()
    fit_requested = pyqtSignal()
    zoom_requested = pyqtSignal(float)
    grid_requested = pyqtSignal(bool)
    clear_requested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedWidth(46)
        self.setObjectName("LightingToolbar")
        self.setStyleSheet(
            f"QFrame#LightingToolbar{{background:{CP['bg1']};"
            f"border:1px solid {CP['border']};border-radius:8px;}}"
        )
        lay = QVBoxLayout(self)
        lay.setContentsMargins(5, 6, 5, 6)
        lay.setSpacing(4)

        group = QButtonGroup(self)
        group.setExclusive(True)
        for key, glyph, tip in (
            ("move", "↖", translate("Sélectionner et déplacer")),
            ("pan", "✥", translate("Déplacer le plan")),
            ("rotate", "↻", translate("Orienter un projecteur")),
        ):
            btn = self._button(glyph, tip, checkable=True)
            btn.clicked.connect(lambda checked=False, k=key: self.tool_changed.emit(k))
            group.addButton(btn)
            lay.addWidget(btn)
            if key == "move":
                btn.setChecked(True)

        lay.addWidget(self._separator())
        add = self._button("", translate("Ajouter un projecteur"))
        pix = load_icon("Fresnel light.png", 22)
        if not pix.isNull():
            add.setIcon(QIcon(pix)); add.setIconSize(QSize(22, 22))
        else:
            add.setText("＋")
        add.clicked.connect(self.add_light_requested)
        lay.addWidget(add)

        actor = self._button("", translate("Ajouter un acteur"))
        pix = load_icon("Acteur.png", 22)
        if not pix.isNull():
            actor.setIcon(QIcon(pix)); actor.setIconSize(QSize(22, 22))
        else:
            actor.setText("♙")
        actor.clicked.connect(self.add_actor_requested)
        lay.addWidget(actor)

        camera = self._button("", translate("Placer ou déplacer la caméra"))
        pix = load_icon("camera_mise en scene.png", 22)
        if not pix.isNull():
            camera.setIcon(QIcon(pix)); camera.setIconSize(QSize(22, 22))
        else:
            camera.setText("▣")
        camera.clicked.connect(self.place_camera_requested)
        lay.addWidget(camera)

        grid = self._button("▦", translate("Afficher ou masquer la grille"), checkable=True)
        grid.setChecked(True)
        grid.toggled.connect(self.grid_requested)
        lay.addWidget(grid)

        fit = self._button("⛶", translate("Adapter le plan à la fenêtre"))
        fit.clicked.connect(self.fit_requested)
        lay.addWidget(fit)
        zin = self._button("＋", translate("Zoom avant"))
        zin.clicked.connect(lambda: self.zoom_requested.emit(1.18))
        lay.addWidget(zin)
        zout = self._button("−", translate("Zoom arrière"))
        zout.clicked.connect(lambda: self.zoom_requested.emit(0.84))
        lay.addWidget(zout)

        lay.addStretch()
        clear = self._button("⌫", translate("Tout supprimer"), danger=True)
        clear.clicked.connect(self.clear_requested)
        self.clear_button = clear
        lay.addWidget(clear)

    def _button(self, text: str, tip: str, *, checkable=False, danger=False) -> QToolButton:
        btn = QToolButton()
        btn.setText(text)
        btn.setToolTip(tip)
        btn.setCheckable(checkable)
        btn.setFixedSize(34, 34)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        color = CP.get("red", "#ff4f6a") if danger else CP["text_secondary"]
        btn.setStyleSheet(
            f"QToolButton{{background:transparent;color:{color};border:1px solid transparent;"
            "border-radius:6px;font-size:17px;font-weight:700;}"
            f"QToolButton:hover{{background:rgba(255,255,255,0.06);"
            f"border-color:{CP['border_bright']};color:{CP['text_primary']};}}"
            f"QToolButton:checked{{background:rgba(78,205,196,0.15);"
            f"border-color:{CP['accent']};color:{CP['accent']};}}"
        )
        return btn

    @staticmethod
    def _separator() -> QFrame:
        sep = QFrame()
        sep.setFixedHeight(1)
        sep.setStyleSheet("background:rgba(255,255,255,0.08);")
        return sep


class _ProjectorCard(QFrame):
    changed = pyqtSignal(object)
    advanced_requested = pyqtSignal(object)
    delete_requested = pyqtSignal(object)

    def __init__(self, light: dict, index: int, parent=None):
        super().__init__(parent)
        self.light = light
        defaults = projectors.default_settings(light.get("family", ""), light.get("model", ""))
        defaults.update(light.get("settings") or {})
        self.settings = defaults
        light["settings"] = self.settings
        self.setObjectName("ProjectorCard")
        self.setStyleSheet(
            "QFrame#ProjectorCard{background:#151a2b;border:1px solid #252c43;"
            "border-radius:8px;}"
        )

        root = QVBoxLayout(self)
        root.setContentsMargins(10, 9, 10, 10)
        root.setSpacing(8)
        head = QHBoxLayout()
        icon = QLabel()
        icon.setFixedSize(24, 24)
        pix = load_icon(projectors.family_icon(light.get("family", "")), 22)
        if not pix.isNull():
            icon.setPixmap(pix)
        else:
            icon.setText("◉")
        icon.setStyleSheet("background:transparent;border:none;")
        head.addWidget(icon)
        title = QLabel((light.get("name") or f"{translate('Projecteur')} {index + 1}").upper())
        title.setStyleSheet(
            "color:#f5b942;font-size:10px;font-weight:800;background:transparent;border:none;"
        )
        head.addWidget(title, 1)
        power = QCheckBox()
        power.setChecked(bool(self.settings.get("on", True)))
        power.setToolTip(translate("Allumer ou éteindre le projecteur"))
        power.toggled.connect(self._set_power)
        head.addWidget(power)
        root.addLayout(head)

        model = QLabel(light.get("model") or projectors.family_label(light.get("family", "")))
        model.setWordWrap(True)
        model.setStyleSheet(
            f"color:{CP['text_dim']};font-size:9px;background:transparent;border:none;"
        )
        root.addWidget(model)

        self._slider(root, translate("Intensité"), 0, 100,
                     int(self.settings.get("intensity", 100)), "intensity", "%")

        cap = projectors.capabilities(light.get("family", ""), light.get("model", ""))
        modes = cap.get("color_modes", ())
        if len(modes) > 1:
            self._combo(root, translate("Mode couleur"), modes,
                        self.settings.get("color_mode", modes[0]), "color_mode")
        lo, hi = cap["cct"]
        if lo != hi:
            self._slider(root, translate("Température"), lo, hi,
                         int(self.settings.get("cct", lo)), "cct", " K")
        else:
            self._fixed_row(root, translate("Température"), f"{lo} K")

        if cap.get("color") == "full":
            self._slider(root, translate("Teinte"), 0, 360,
                         int(self.settings.get("hue", 0)), "hue", "°")
            self._slider(root, translate("Saturation"), 0, 100,
                         int(self.settings.get("saturation", 0)), "saturation", "%")
        if cap.get("green_magenta"):
            self._slider(root, translate("Vert / Magenta"), -100, 100,
                         int(self.settings.get("green_magenta", 0)), "green_magenta", "%")

        beam = cap.get("beam")
        if cap.get("accessories"):
            labels = [label for label, _angle in cap["accessories"]]
            self._combo(root, translate("Optique / accessoire"), labels,
                        self.settings.get("accessory", labels[0]), "accessory")
            self._fixed_row(root, translate("Angle effectif"),
                            f"{projectors.effective_beam(self.light):g}°")
        elif beam and cap.get("beam_control") == "focus" and beam[0] != beam[1]:
            self._slider(root, translate("Angle de faisceau"), beam[0], beam[1],
                         int(self.settings.get("beam") or sum(beam) // 2), "beam", "°")
        elif beam:
            self._fixed_row(root, translate("Angle de faisceau"), f"{beam[0]}°")

        hrow = QHBoxLayout()
        hl = QLabel(translate("Hauteur"))
        hl.setStyleSheet(self._label_style())
        height = QDoubleSpinBox()
        height.setRange(0.0, 12.0); height.setSingleStep(0.1); height.setSuffix(" m")
        height.setValue(float(self.settings.get("height", 2.5) or 0.0))
        height.setStyleSheet(self._input_style())
        height.valueChanged.connect(lambda value: self._set("height", float(value)))
        hrow.addWidget(hl); hrow.addStretch(); hrow.addWidget(height)
        root.addLayout(hrow)

        self._slider(root, translate("Inclinaison"), 0, 90,
                     int(self.settings.get("tilt", 90)), "tilt", "°")

        if cap.get("pixels", 1) > 1:
            count = int(cap["pixels"])
            pixel_modes = [str(v) for v in sorted({1, min(4, count), min(8, count), count})]
            self._combo(root, translate("Groupes de pixels"), pixel_modes,
                        str(self.settings.get("pixel_mode", count)), "pixel_mode", cast=int)

        if cap.get("strobe"):
            lo_strobe, hi_strobe = cap["strobe"]
            self._slider(root, translate("Stroboscope"), lo_strobe, hi_strobe,
                         int(self.settings.get("strobe_hz", 0)), "strobe_hz", " Hz")

        if cap.get("effects"):
            effect_labels = [label for _code, label, _desc in projectors.EFFECTS]
            current_code = self.settings.get("effect", "")
            current_label = projectors.effect_label(current_code)
            self._combo(root, translate("Effet"), effect_labels, current_label, "effect",
                        values=[code for code, _label, _desc in projectors.EFFECTS])

        notes = QLineEdit(light.get("notes", ""))
        notes.setPlaceholderText(translate("Notes d'éclairage…"))
        notes.setStyleSheet(self._input_style())
        notes.textChanged.connect(self._set_notes)
        root.addWidget(notes)

        actions = QHBoxLayout()
        advanced = QPushButton(translate("Réglages avancés"))
        advanced.setCursor(Qt.CursorShape.PointingHandCursor)
        advanced.setStyleSheet(self._small_button_style())
        advanced.clicked.connect(lambda: self.advanced_requested.emit(self.light))
        delete = QPushButton("✕")
        delete.setToolTip(translate("Supprimer"))
        delete.setFixedWidth(30)
        delete.setCursor(Qt.CursorShape.PointingHandCursor)
        delete.setStyleSheet(self._small_button_style(danger=True))
        delete.clicked.connect(lambda: self.delete_requested.emit(self.light))
        actions.addWidget(advanced, 1); actions.addWidget(delete)
        root.addLayout(actions)

    def _slider(self, root, label, lo, hi, value, key, suffix):
        head = QHBoxLayout()
        lbl = QLabel(label); lbl.setStyleSheet(self._label_style())
        val = QLabel(f"{value}{suffix}")
        val.setStyleSheet(
            f"color:{CP['accent']};font-size:9px;font-weight:700;"
            "background:transparent;border:none;"
        )
        head.addWidget(lbl); head.addStretch(); head.addWidget(val)
        root.addLayout(head)
        slider = QSlider(Qt.Orientation.Horizontal)
        slider.setTickPosition(QSlider.TickPosition.NoTicks)
        slider.setRange(int(lo), int(hi)); slider.setValue(max(int(lo), min(int(hi), int(value))))
        slider.setStyleSheet(
            "QSlider{background:transparent;border:none;outline:none;min-height:18px;}"
            f"QSlider::groove:horizontal{{height:3px;margin:0 7px;"
            f"background:{CP['bg4']};border:0;border-radius:1px;}}"
            "QSlider::handle:horizontal{width:14px;margin:-6px -7px;"
            "border:0;border-radius:7px;background:#f5b942;}"
            "QSlider::sub-page:horizontal{background:rgba(245,185,66,0.62);"
            "border:0;border-radius:1px;}"
            f"QSlider::add-page:horizontal{{background:{CP['bg4']};"
            "border:0;border-radius:1px;}"
        )
        slider.valueChanged.connect(lambda v, lab=val, sx=suffix: lab.setText(f"{v}{sx}"))
        slider.valueChanged.connect(lambda v, k=key: self._set(k, int(v)))
        root.addWidget(slider)

    def _fixed_row(self, root, label, value):
        row = QHBoxLayout()
        lbl = QLabel(label); lbl.setStyleSheet(self._label_style())
        val = QLabel(value); val.setStyleSheet(
            f"color:{CP['text_secondary']};font-size:9px;"
            "background:transparent;border:none;"
        )
        row.addWidget(lbl); row.addStretch(); row.addWidget(val); root.addLayout(row)

    def _combo(self, root, label, labels, current, key, *, values=None, cast=None):
        row = QHBoxLayout()
        lbl = QLabel(label); lbl.setStyleSheet(self._label_style())
        combo = QComboBox()
        for idx, text in enumerate(labels):
            combo.addItem(str(text), (values[idx] if values else text))
        current_idx = combo.findText(str(current))
        if current_idx < 0:
            current_idx = combo.findData(current)
        combo.setCurrentIndex(max(0, current_idx))
        combo.setStyleSheet(
            f"QComboBox{{background:{CP['bg3']};color:{CP['text_primary']};"
            f"border:1px solid {CP['border']};border-radius:5px;padding:4px 7px;font-size:9px;}}"
            f"QComboBox:hover,QComboBox:focus{{border-color:{CP['border_bright']};}}"
            "QComboBox::drop-down{border:none;width:22px;}"
        )
        def changed(_idx):
            value = combo.currentData()
            if cast:
                value = cast(value)
            self._set(key, value)
        combo.currentIndexChanged.connect(changed)
        row.addWidget(lbl); row.addStretch(); row.addWidget(combo, 1)
        root.addLayout(row)

    def _set_power(self, value: bool):
        self._set("on", bool(value))

    def _set(self, key: str, value):
        self.settings[key] = value
        self.changed.emit(self.light)

    def _set_notes(self, value: str):
        self.light["notes"] = value
        self.changed.emit(self.light)

    @staticmethod
    def _label_style():
        return f"color:{CP['text_secondary']};font-size:9px;background:transparent;border:none;"

    @staticmethod
    def _input_style():
        return (
            f"QLineEdit,QDoubleSpinBox{{background:{CP['bg3']};color:{CP['text_primary']};"
            f"border:1px solid {CP['border']};border-radius:5px;padding:4px 7px;font-size:9px;}}"
        )

    @staticmethod
    def _small_button_style(danger=False):
        color = CP.get("red", "#ff4f6a") if danger else CP["text_secondary"]
        return (
            f"QPushButton{{background:transparent;color:{color};border:1px solid {CP['border']};"
            "border-radius:5px;padding:5px 7px;font-size:9px;font-weight:700;}"
            "QPushButton:hover{background:rgba(255,255,255,0.06);border-color:rgba(255,255,255,0.22);}"
        )


class LightingInspectorToggle(QWidget):
    """Poignée latérale identique au principe de la poignée GUIDE."""

    toggled = pyqtSignal(bool)

    def __init__(self, *, opened=True, parent=None):
        super().__init__(parent)
        self._open = bool(opened)
        self.setFixedWidth(42)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setToolTip(translate("Ouvrir ou fermer les réglages du plateau"))
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        # Mêmes couleurs que la poignée GUIDE (demande Matthieu 2026-07-22).
        self.setStyleSheet(f"background:{CP['bg1']};")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)
        lay.addStretch()
        label = QLabel(translate("RÉGLAGES"))
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        label.setStyleSheet(
            f"color:{CP['accent']};font-size:7px;font-weight:900;letter-spacing:.5px;"
            "background:transparent;border:none;"
        )
        lay.addWidget(label)
        lay.addSpacing(6)
        self._arrow = QLabel()
        self._arrow.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._arrow.setStyleSheet(
            f"color:{CP['accent']};font-size:18px;font-weight:700;"
            "background:transparent;border:none;"
        )
        lay.addWidget(self._arrow)
        lay.addStretch()
        self._update_arrow()

    def _update_arrow(self):
        # Fermée → flèche vers l'EXTÉRIEUR de l'écran (❯, panneau au bord droit) ;
        # ouverte → vers l'INTÉRIEUR (❮). Demande Matthieu 2026-07-22.
        self._arrow.setText("❮" if self._open else "❯")

    def set_open(self, opened: bool):
        self._open = bool(opened)
        self._update_arrow()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._open = not self._open
            self._update_arrow()
            self.toggled.emit(self._open)
            event.accept()
            return
        super().mousePressEvent(event)


class LightingInspector(QWidget):
    """Inspecteur repliable des projecteurs du plan courant."""

    changed = pyqtSignal(object)
    advanced_requested = pyqtSignal(object)
    delete_requested = pyqtSignal(object)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedWidth(318)
        self.setObjectName("LightingInspector")
        self.setStyleSheet(
            "QWidget#LightingInspector{"
            "background:qlineargradient(x1:0,y1:0,x2:1,y2:0,"
            "stop:0 #14192a,stop:1 #101525);"
            "border-left:1px solid rgba(121,98,255,0.42);}" 
        )
        root = QVBoxLayout(self)
        root.setContentsMargins(9, 10, 9, 10)
        root.setSpacing(8)
        title = QLabel(translate("RÉGLAGES DES PROJECTEURS"))
        title.setStyleSheet(
            "color:#f5b942;font-size:10px;font-weight:800;letter-spacing:1px;"
            "background:transparent;border:none;"
        )
        root.addWidget(title)
        sub = QLabel(translate("Les modifications sont enregistrées et synchronisées automatiquement."))
        sub.setWordWrap(True)
        sub.setStyleSheet(f"color:{CP['text_dim']};font-size:8px;background:transparent;border:none;")
        root.addWidget(sub)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet("QScrollArea{background:transparent;border:none;}")
        self._content = QWidget()
        self._content.setStyleSheet("background:transparent;")
        self._layout = QVBoxLayout(self._content)
        self._layout.setContentsMargins(0, 0, 2, 0)
        self._layout.setSpacing(8)
        self._layout.addStretch()
        scroll.setWidget(self._content)
        root.addWidget(scroll, 1)

    def set_lights(self, lights: list[dict]):
        while self._layout.count():
            item = self._layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        if not lights:
            empty = QLabel(translate("Aucun projecteur sur ce plan.\nUtilisez ＋ dans la barre d'outils pour en ajouter un."))
            empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
            empty.setWordWrap(True)
            empty.setStyleSheet(
                f"color:{CP['text_dim']};font-size:10px;padding:28px 14px;"
                f"background:{CP['bg2']};border:1px dashed {CP['border']};border-radius:8px;"
            )
            self._layout.addWidget(empty)
        for idx, light in enumerate(lights):
            card = _ProjectorCard(light, idx)
            card.changed.connect(self.changed)
            card.advanced_requested.connect(self.advanced_requested)
            card.delete_requested.connect(self.delete_requested)
            self._layout.addWidget(card)
        self._layout.addStretch()
