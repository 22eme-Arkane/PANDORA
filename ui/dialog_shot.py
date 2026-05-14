from PyQt6.QtWidgets import (
    QDialog, QWidget, QHBoxLayout, QVBoxLayout, QLabel, QPushButton,
    QLineEdit, QTextEdit, QComboBox, QScrollArea,
    QFrame, QCheckBox, QSlider,
)
from PyQt6.QtCore import Qt
from ui.styles import CP, PANDORA_STYLESHEET
from ui.icons import claude_icon_pixmap, install_hover_icon
import core.storyboard as sb_api
from core.storyboard import CAMERA_MOVEMENTS, OPTICS, FOCALS, DISTANCES, SHOT_SIZES, SHOT_SIZE_LABELS, SPEEDS, HEURE_PRESETS


def _lbl(text, size=11, color=None):
    l = QLabel(text)
    l.setStyleSheet(
        f"color:{color or CP['text_secondary']};font-size:{size}px;background:transparent;border:none;"
    )
    return l


def _sep():
    f = QFrame()
    f.setFixedHeight(1)
    f.setStyleSheet(f"background:{CP['border']};")
    return f


def _combo(items: list[str], current: str = "") -> QComboBox:
    cb = QComboBox()
    cb.addItems(items)
    if current in items:
        cb.setCurrentText(current)
    cb.setFixedHeight(34)
    cb.setStyleSheet(
        f"QComboBox{{background:{CP['bg3']};border:1px solid {CP['border']};"
        f"border-radius:6px;color:{CP['text_primary']};font-size:12px;padding:0 10px;}}"
        f"QComboBox::drop-down{{border:none;width:20px;}}"
        f"QComboBox QAbstractItemView{{background:{CP['bg3']};border:1px solid {CP['border_bright']};"
        f"color:{CP['text_primary']};selection-background-color:{CP['accent_dim']};}}"
    )
    return cb


_FIELD_STYLE = (
    f"QLineEdit{{background:{CP['bg3']};border:1px solid {CP['border']};"
    f"border-radius:6px;color:{CP['text_primary']};font-size:12px;padding:0 10px;}}"
    f"QLineEdit:focus{{border-color:{CP['accent']};}}"
)

_TEXTAREA_STYLE = (
    f"QTextEdit{{background:{CP['bg3']};border:1px solid {CP['border']};"
    f"border-radius:6px;color:{CP['text_primary']};font-size:12px;padding:8px;}}"
    f"QTextEdit:focus{{border-color:{CP['accent']};}}"
)

_CB_STYLE = (
    f"QCheckBox{{color:{CP['text_secondary']};font-size:10px;background:transparent;}}"
    f"QCheckBox::indicator{{width:14px;height:14px;border:1px solid {CP['border_bright']};"
    f"border-radius:3px;background:{CP['bg3']};}}"
    f"QCheckBox::indicator:checked{{background:{CP['accent']};border-color:{CP['accent']};}}"
)

_CHECKLIST_STYLE = (
    f"QScrollArea{{background:{CP['bg2']};border:1px solid {CP['border']};border-radius:6px;}}"
)


class ShotDialog(QDialog):

    def __init__(self, parent=None, shot: dict | None = None):
        super().__init__(parent)
        self._shot                  = shot or {}
        self._saved_data            = None
        self._worker_enhance_action   = None
        self._worker_enhance_seedance = None

        seq = self._shot.get("seq_num", "")
        siq = self._shot.get("shot_in_seq", "")
        if seq and siq and shot:
            self.setWindowTitle(f"SQ{seq} — P{siq}")
        elif shot:
            self.setWindowTitle(f"P{self._shot.get('number', '?')}")
        else:
            self.setWindowTitle("Nouveau plan")

        self.setMinimumSize(640, 560)
        self.resize(720, 700)
        self.setStyleSheet(PANDORA_STYLESHEET + f"QDialog{{background:{CP['bg1']};}}")

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        root.addWidget(self._build_form(), 1)
        root.addWidget(self._build_btn_bar())

        from core.i18n import retranslate_widget
        retranslate_widget(self)

    # ── Form ──────────────────────────────────────────────────────────────────

    def _build_form(self):
        outer = QWidget()
        outer.setStyleSheet(f"background:{CP['bg1']};")
        ol = QVBoxLayout(outer)
        ol.setContentsMargins(0, 0, 0, 0)
        ol.setSpacing(0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet("QScrollArea{background:transparent;border:none;}")

        inner = QWidget()
        inner.setStyleSheet("background:transparent;")
        lay = QVBoxLayout(inner)
        lay.setContentsMargins(28, 24, 28, 16)
        lay.setSpacing(14)

        # ── Header ────────────────────────────────────────────────────────────
        is_new = not bool(self._shot.get("id"))
        _seq = self._shot.get("seq_num", "")
        _siq = self._shot.get("shot_in_seq", "")
        if _seq and _siq and not is_new:
            header_text = f"SQ{_seq} — P{_siq}"
        elif not is_new:
            header_text = f"P{self._shot.get('number', '?')}"
        else:
            header_text = "Nouveau plan"
        header_lbl = QLabel(header_text)
        header_lbl.setStyleSheet(
            f"color:{CP['text_primary']};font-size:18px;font-weight:700;background:transparent;"
        )
        lay.addWidget(header_lbl)

        # ── IDENTIFICATION ────────────────────────────────────────────────────
        lay.addWidget(_lbl("IDENTIFICATION", color=CP["accent"], size=9))
        lay.addWidget(_sep())

        # Séq | Plan | Nom de séquence
        row_id = QHBoxLayout()
        row_id.setSpacing(8)

        col_seq = QVBoxLayout()
        col_seq.setSpacing(4)
        col_seq.addWidget(_lbl("Séq."))
        self._seq_num = QLineEdit(str(self._shot.get("seq_num", "")))
        self._seq_num.setPlaceholderText("1")
        self._seq_num.setFixedSize(52, 34)
        self._seq_num.setToolTip("Numéro de séquence")
        self._seq_num.setStyleSheet(_FIELD_STYLE)
        col_seq.addWidget(self._seq_num)

        col_siq = QVBoxLayout()
        col_siq.setSpacing(4)
        col_siq.addWidget(_lbl("Plan"))
        self._shot_in_seq = QLineEdit(str(self._shot.get("shot_in_seq", "")))
        self._shot_in_seq.setPlaceholderText("1")
        self._shot_in_seq.setFixedSize(52, 34)
        self._shot_in_seq.setToolTip("N° du plan dans la séquence — ex: 3 → Plan 1/3")
        self._shot_in_seq.setStyleSheet(_FIELD_STYLE)
        col_siq.addWidget(self._shot_in_seq)

        col_seq_name = QVBoxLayout()
        col_seq_name.setSpacing(4)
        col_seq_name.addWidget(_lbl("Nom de séquence"))
        self._seq_name = QLineEdit(self._shot.get("seq_name", ""))
        self._seq_name.setPlaceholderText("Ex: Prison, Voiture Nuit, Concert…")
        self._seq_name.setFixedHeight(34)
        self._seq_name.setStyleSheet(_FIELD_STYLE)
        col_seq_name.addWidget(self._seq_name)

        row_id.addLayout(col_seq)
        row_id.addLayout(col_siq)
        row_id.addLayout(col_seq_name, 1)
        lay.addLayout(row_id)

        # Action
        col_action = QVBoxLayout()
        col_action.setSpacing(4)
        action_header = QHBoxLayout()
        action_header.setSpacing(6)
        action_header.addWidget(_lbl("Description de l'action"))
        action_header.addStretch()
        self._btn_enhance_action = QPushButton()
        self._btn_enhance_action.setFixedSize(26, 26)
        self._btn_enhance_action.setToolTip(
            "Améliorer avec Claude\n"
            "Reformule la description en une phrase claire (FR, présent, <120 car.)"
        )
        self._btn_enhance_action.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_enhance_action.setStyleSheet("""
            QPushButton{background:transparent;border:none;border-radius:5px;padding:0;}
            QPushButton:hover{background:rgba(78,205,196,0.12);}
            QPushButton:pressed{background:rgba(78,205,196,0.22);}
            QPushButton:disabled{opacity:0.3;}
        """)
        _pix_n = claude_icon_pixmap(15, CP["text_dim"])
        _pix_h = claude_icon_pixmap(15, CP["accent"])
        if not _pix_n.isNull():
            install_hover_icon(self._btn_enhance_action, _pix_n, _pix_h, icon_size=15)
        else:
            self._btn_enhance_action.setText("☁")
        self._btn_enhance_action.clicked.connect(self._on_enhance_action)
        action_header.addWidget(self._btn_enhance_action)
        col_action.addLayout(action_header)
        self._scene_title = QLineEdit(self._shot.get("scene_title", ""))
        self._scene_title.setPlaceholderText("Ex: Le chanteur est assis sur la banquette…")
        self._scene_title.setFixedHeight(34)
        self._scene_title.setStyleSheet(_FIELD_STYLE)
        col_action.addWidget(self._scene_title)
        lay.addLayout(col_action)

        # ── TECHNIQUE CAMÉRA ──────────────────────────────────────────────────
        lay.addSpacing(4)
        lay.addWidget(_lbl("TECHNIQUE CAMÉRA", color=CP["accent"], size=9))
        lay.addWidget(_sep())

        row_cam = QHBoxLayout()
        row_cam.setSpacing(10)

        col_move = QVBoxLayout()
        col_move.setSpacing(4)
        col_move.addWidget(_lbl("Mouvement"))
        self._cam_move = _combo(CAMERA_MOVEMENTS, self._shot.get("camera_movement", "Fixe"))
        col_move.addWidget(self._cam_move)

        col_size = QVBoxLayout()
        col_size.setSpacing(4)
        col_size.addWidget(_lbl("Valeur de plan"))
        self._shot_size = QComboBox()
        for key in SHOT_SIZES:
            self._shot_size.addItem(SHOT_SIZE_LABELS.get(key, key), key)
        cur_size = self._shot.get("shot_size", "")
        for i in range(self._shot_size.count()):
            if self._shot_size.itemData(i) == cur_size:
                self._shot_size.setCurrentIndex(i)
                break
        self._shot_size.setFixedHeight(34)
        self._shot_size.setStyleSheet(
            f"QComboBox{{background:{CP['bg3']};border:1px solid {CP['border']};"
            f"border-radius:6px;color:{CP['text_primary']};font-size:12px;padding:0 8px;}}"
            f"QComboBox::drop-down{{border:none;width:18px;}}"
            f"QComboBox QAbstractItemView{{background:{CP['bg3']};border:1px solid {CP['border_bright']};"
            f"color:{CP['text_primary']};selection-background-color:{CP['accent_dim']};}}"
        )
        col_size.addWidget(self._shot_size)

        col_focal = QVBoxLayout()
        col_focal.setSpacing(4)
        col_focal.addWidget(_lbl("Focale"))
        self._focal = _combo(FOCALS, self._shot.get("focal", "35mm"))
        col_focal.addWidget(self._focal)

        col_dist = QVBoxLayout()
        col_dist.setSpacing(4)
        col_dist.addWidget(_lbl("Dist. sujet"))
        self._camera_distance = _combo(DISTANCES, self._shot.get("camera_distance", ""))
        self._camera_distance.setEditable(True)
        self._camera_distance.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        _cur_dist = self._shot.get("camera_distance", "")
        if _cur_dist:
            self._camera_distance.setCurrentText(_cur_dist)
        col_dist.addWidget(self._camera_distance)

        col_optic = QVBoxLayout()
        col_optic.setSpacing(4)
        col_optic.addWidget(_lbl("Optique"))
        self._optic = _combo(OPTICS, self._shot.get("optic", "Sphérique"))
        col_optic.addWidget(self._optic)

        col_speed = QVBoxLayout()
        col_speed.setSpacing(4)
        col_speed.addWidget(_lbl("Vitesse"))
        self._speed = _combo(SPEEDS, self._shot.get("speed", "Normale"))
        col_speed.addWidget(self._speed)

        row_cam.addLayout(col_move, 2)
        row_cam.addLayout(col_size, 1)
        row_cam.addLayout(col_focal, 1)
        row_cam.addLayout(col_dist, 1)
        row_cam.addLayout(col_optic, 1)
        row_cam.addLayout(col_speed, 1)
        lay.addLayout(row_cam)

        # ── LIEU & TEMPS ──────────────────────────────────────────────────────
        lay.addSpacing(4)
        lay.addWidget(_lbl("LIEU & TEMPS", color=CP["accent"], size=9))
        lay.addWidget(_sep())

        row_lieu = QHBoxLayout()
        row_lieu.setSpacing(12)

        col_decor = QVBoxLayout()
        col_decor.setSpacing(4)
        col_decor.addWidget(_lbl("Décor"))
        self._decor_combo = QComboBox()
        self._decor_combo.setFixedHeight(34)
        self._decor_combo.setEditable(True)
        self._decor_combo.setStyleSheet(
            f"QComboBox{{background:{CP['bg3']};border:1px solid {CP['border']};"
            f"border-radius:6px;color:{CP['text_primary']};font-size:12px;padding:0 10px;}}"
            f"QComboBox::drop-down{{border:none;width:20px;}}"
            f"QComboBox QAbstractItemView{{background:{CP['bg3']};border:1px solid {CP['border_bright']};"
            f"color:{CP['text_primary']};selection-background-color:{CP['accent_dim']};}}"
        )
        self._decor_id_map: dict[str, str] = {}
        self._populate_decors()
        col_decor.addWidget(self._decor_combo)

        col_time = QVBoxLayout()
        col_time.setSpacing(4)
        col_time.addWidget(_lbl("Heure"))
        self._time_combo = QComboBox()
        self._time_combo.setEditable(True)
        for p in HEURE_PRESETS:
            self._time_combo.addItem(p)
        cur_ht = self._shot.get("shot_time", "")
        if cur_ht and cur_ht not in HEURE_PRESETS:
            self._time_combo.setCurrentText(cur_ht)
        elif cur_ht:
            self._time_combo.setCurrentText(cur_ht)
        else:
            self._time_combo.setCurrentIndex(-1)
        self._time_combo.lineEdit().setPlaceholderText("ex : 14h30, Jour…")
        self._time_combo.setStyleSheet(
            f"QComboBox{{background:{CP['bg3']};border:1px solid {CP['border']};"
            f"border-radius:6px;color:{CP['text_primary']};font-size:11px;padding:5px 8px;}}"
            f"QComboBox::drop-down{{border:none;width:20px;}}"
            f"QComboBox QAbstractItemView{{background:{CP['bg3']};border:1px solid {CP['border_bright']};"
            f"color:{CP['text_primary']};selection-background-color:{CP['accent_dim']};}}"
        )
        col_time.addWidget(self._time_combo)

        row_lieu.addLayout(col_decor, 2)
        row_lieu.addLayout(col_time, 1)
        lay.addLayout(row_lieu)

        # ── ÉLÉMENTS ──────────────────────────────────────────────────────────
        lay.addSpacing(4)
        lay.addWidget(_lbl("ÉLÉMENTS", color=CP["accent"], size=9))
        lay.addWidget(_sep())

        row_elems = QHBoxLayout()
        row_elems.setSpacing(12)

        # Accessoires
        acc_col = QVBoxLayout()
        acc_col.setSpacing(4)
        acc_col.addWidget(_lbl("Accessoires"))
        acc_scroll = QScrollArea()
        acc_scroll.setFixedHeight(96)
        acc_scroll.setWidgetResizable(True)
        acc_scroll.setStyleSheet(_CHECKLIST_STYLE)
        acc_inner = QWidget()
        acc_inner.setStyleSheet("background:transparent;")
        self._acc_lay = QVBoxLayout(acc_inner)
        self._acc_lay.setContentsMargins(8, 8, 8, 8)
        self._acc_lay.setSpacing(4)
        self._acc_checks: dict[str, QCheckBox] = {}
        self._populate_accessories()
        acc_scroll.setWidget(acc_inner)
        acc_col.addWidget(acc_scroll)
        row_elems.addLayout(acc_col, 1)

        # Acteurs
        char_col = QVBoxLayout()
        char_col.setSpacing(4)
        char_col.addWidget(_lbl("Acteurs / Personnages"))
        char_scroll = QScrollArea()
        char_scroll.setFixedHeight(96)
        char_scroll.setWidgetResizable(True)
        char_scroll.setStyleSheet(_CHECKLIST_STYLE)
        char_inner = QWidget()
        char_inner.setStyleSheet("background:transparent;")
        self._char_lay = QVBoxLayout(char_inner)
        self._char_lay.setContentsMargins(8, 8, 8, 8)
        self._char_lay.setSpacing(4)
        self._char_checks: dict[str, QCheckBox] = {}
        self._populate_characters()
        char_scroll.setWidget(char_inner)
        char_col.addWidget(char_scroll)
        row_elems.addLayout(char_col, 1)

        lay.addLayout(row_elems)

        # Véhicules
        veh_col = QVBoxLayout()
        veh_col.setSpacing(4)
        veh_col.addWidget(_lbl("Véhicules"))
        veh_scroll = QScrollArea()
        veh_scroll.setFixedHeight(80)
        veh_scroll.setWidgetResizable(True)
        veh_scroll.setStyleSheet(_CHECKLIST_STYLE)
        veh_inner = QWidget()
        veh_inner.setStyleSheet("background:transparent;")
        self._veh_lay = QVBoxLayout(veh_inner)
        self._veh_lay.setContentsMargins(8, 8, 8, 8)
        self._veh_lay.setSpacing(4)
        self._veh_checks: dict[str, QCheckBox] = {}
        self._populate_vehicles()
        veh_scroll.setWidget(veh_inner)
        veh_col.addWidget(veh_scroll)
        lay.addLayout(veh_col)

        # ── MISE EN SCÈNE ─────────────────────────────────────────────────────
        lay.addSpacing(4)
        lay.addWidget(_lbl("MISE EN SCÈNE", color=CP["accent"], size=9))
        lay.addWidget(_sep())

        # Axe caméra + Placement caméra
        row_scene1 = QHBoxLayout()
        row_scene1.setSpacing(10)

        col_axis = QVBoxLayout()
        col_axis.setSpacing(4)
        col_axis.addWidget(_lbl("Axe caméra"))
        self._camera_axis = _combo(
            ["—", "Face", "3/4", "Latéral 90°", "Dos", "Plongée", "Contre-plongée", "Vue subjective"],
            self._shot.get("camera_axis", "—"),
        )
        col_axis.addWidget(self._camera_axis)

        col_cam_pos = QVBoxLayout()
        col_cam_pos.setSpacing(4)
        col_cam_pos.addWidget(_lbl("Placement caméra"))
        self._camera_placement = QLineEdit(self._shot.get("camera_placement", ""))
        self._camera_placement.setPlaceholderText("Ex: Face table côté Raoul, légère 3/4…")
        self._camera_placement.setFixedHeight(34)
        self._camera_placement.setStyleSheet(_FIELD_STYLE)
        col_cam_pos.addWidget(self._camera_placement)

        row_scene1.addLayout(col_axis, 1)
        row_scene1.addLayout(col_cam_pos, 2)
        lay.addLayout(row_scene1)

        # Placement acteurs
        col_actors = QVBoxLayout()
        col_actors.setSpacing(4)
        col_actors.addWidget(_lbl("Placement acteurs"))
        self._actor_placement = QLineEdit(self._shot.get("actor_placement", ""))
        self._actor_placement.setPlaceholderText(
            "Ex: PÈRE + MÈRE côté gauche, SARAH + RAOUL côté droit"
        )
        self._actor_placement.setFixedHeight(34)
        self._actor_placement.setStyleSheet(_FIELD_STYLE)
        col_actors.addWidget(self._actor_placement)
        lay.addLayout(col_actors)

        # IN / OUT + Micro
        row_scene2 = QHBoxLayout()
        row_scene2.setSpacing(10)

        col_in = QVBoxLayout()
        col_in.setSpacing(4)
        col_in.addWidget(_lbl("IN — dans le cadre"))
        self._chars_in = QLineEdit(self._shot.get("chars_in", ""))
        self._chars_in.setPlaceholderText("Ex: RAOUL (gros plan)")
        self._chars_in.setFixedHeight(34)
        self._chars_in.setStyleSheet(_FIELD_STYLE)
        col_in.addWidget(self._chars_in)

        col_out = QVBoxLayout()
        col_out.setSpacing(4)
        col_out.addWidget(_lbl("OUT — hors-champ"))
        self._chars_out = QLineEdit(self._shot.get("chars_out", ""))
        self._chars_out.setPlaceholderText("Ex: SARAH (amorce épaule), PÈRE hors-champ")
        self._chars_out.setFixedHeight(34)
        self._chars_out.setStyleSheet(_FIELD_STYLE)
        col_out.addWidget(self._chars_out)

        col_mic = QVBoxLayout()
        col_mic.setSpacing(4)
        col_mic.addWidget(_lbl("Micro — on entend"))
        self._mic_placement = QLineEdit(self._shot.get("mic_placement", ""))
        self._mic_placement.setPlaceholderText("Ex: RAOUL (perche)")
        self._mic_placement.setFixedHeight(34)
        self._mic_placement.setStyleSheet(_FIELD_STYLE)
        col_mic.addWidget(self._mic_placement)

        row_scene2.addLayout(col_in, 2)
        row_scene2.addLayout(col_out, 2)
        row_scene2.addLayout(col_mic, 1)
        lay.addLayout(row_scene2)

        # ── DURÉE ─────────────────────────────────────────────────────────────
        lay.addSpacing(4)
        lay.addWidget(_lbl("DURÉE", color=CP["accent"], size=9))
        lay.addWidget(_sep())

        dur_header = QHBoxLayout()
        dur_header.addWidget(_lbl("Durée du plan"))
        dur_header.addStretch()
        self._dur_lbl = QLabel(f"{self._shot.get('duration', 5.0):.1f}s")
        self._dur_lbl.setStyleSheet(
            f"color:{CP['accent']};font-size:13px;font-weight:700;font-family:'Consolas',monospace;"
            f"background:transparent;border:none;"
        )
        dur_header.addWidget(self._dur_lbl)
        dur_header.addWidget(_lbl("/ 15.0s max", size=10, color=CP["text_dim"]))
        lay.addLayout(dur_header)

        self._dur_slider = QSlider(Qt.Orientation.Horizontal)
        self._dur_slider.setRange(10, 150)
        dur_val = int(float(self._shot.get("duration", 5.0)) * 10)
        self._dur_slider.setValue(max(10, min(150, dur_val)))
        self._dur_slider.setStyleSheet(
            f"QSlider::groove:horizontal{{height:4px;background:{CP['bg3']};border-radius:2px;}}"
            f"QSlider::handle:horizontal{{width:16px;height:16px;margin:-6px 0;"
            f"background:{CP['accent']};border-radius:8px;}}"
            f"QSlider::sub-page:horizontal{{background:{CP['accent']};border-radius:2px;}}"
        )
        self._dur_slider.valueChanged.connect(
            lambda v: self._dur_lbl.setText(f"{v / 10:.1f}s")
        )
        lay.addWidget(self._dur_slider)

        # ── NOTES & PROMPT ────────────────────────────────────────────────────
        lay.addSpacing(4)
        lay.addWidget(_lbl("NOTES & PROMPT", color=CP["accent"], size=9))
        lay.addWidget(_sep())

        lay.addWidget(_lbl("Description"))
        self._comments = QTextEdit()
        self._comments.setPlainText(self._shot.get("comments", ""))
        self._comments.setFixedHeight(68)
        self._comments.setStyleSheet(_TEXTAREA_STYLE)
        lay.addWidget(self._comments)

        seedance_header = QHBoxLayout()
        seedance_header.setSpacing(6)
        seedance_header.addWidget(_lbl("Prompt Seedance 2.0"))
        seedance_header.addStretch()
        self._btn_enhance_seedance = QPushButton()
        self._btn_enhance_seedance.setFixedSize(26, 26)
        self._btn_enhance_seedance.setToolTip(
            "Améliorer avec Claude\n"
            "Réécrit le prompt en anglais cinématographique optimisé Seedance 2.0 (<400 car.)"
        )
        self._btn_enhance_seedance.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_enhance_seedance.setStyleSheet("""
            QPushButton{background:transparent;border:none;border-radius:5px;padding:0;}
            QPushButton:hover{background:rgba(78,205,196,0.12);}
            QPushButton:pressed{background:rgba(78,205,196,0.22);}
            QPushButton:disabled{opacity:0.3;}
        """)
        _pix_n2 = claude_icon_pixmap(15, CP["text_dim"])
        _pix_h2 = claude_icon_pixmap(15, CP["accent"])
        if not _pix_n2.isNull():
            install_hover_icon(self._btn_enhance_seedance, _pix_n2, _pix_h2, icon_size=15)
        else:
            self._btn_enhance_seedance.setText("☁")
        self._btn_enhance_seedance.clicked.connect(self._on_enhance_seedance)
        seedance_header.addWidget(self._btn_enhance_seedance)
        lay.addLayout(seedance_header)
        self._seedance_prompt = QTextEdit()
        self._seedance_prompt.setPlainText(self._shot.get("seedance_prompt", ""))
        self._seedance_prompt.setFixedHeight(68)
        self._seedance_prompt.setStyleSheet(
            _TEXTAREA_STYLE.replace(CP["accent"], CP["accent2_dim"])
        )
        lay.addWidget(self._seedance_prompt)

        self._enhance_status = QLabel("")
        self._enhance_status.setWordWrap(True)
        self._enhance_status.setStyleSheet(
            f"color:{CP['text_dim']};font-size:10px;background:transparent;border:none;"
        )
        lay.addWidget(self._enhance_status)

        lay.addStretch()
        scroll.setWidget(inner)
        ol.addWidget(scroll, 1)
        return outer

    # ── Bottom bar ────────────────────────────────────────────────────────────

    def _build_btn_bar(self):
        bar = QWidget()
        bar.setStyleSheet(f"background:{CP['bg2']};border-top:1px solid {CP['border']};")
        bl = QHBoxLayout(bar)
        bl.setContentsMargins(28, 14, 28, 14)
        bl.setSpacing(10)

        btn_cancel = QPushButton("Annuler")
        btn_cancel.setFixedHeight(38)
        btn_cancel.setStyleSheet(
            f"QPushButton{{background:transparent;color:{CP['text_secondary']};"
            f"border:1px solid {CP['border']};border-radius:8px;font-size:12px;font-weight:700;padding:0 16px;}}"
            f"QPushButton:hover{{background:{CP['bg3']};color:{CP['text_primary']};}}"
        )
        btn_cancel.clicked.connect(self.reject)

        btn_save = QPushButton("✓  Sauvegarder le plan")
        btn_save.setFixedHeight(38)
        btn_save.setStyleSheet(
            f"QPushButton{{background:{CP['accent']};color:#07080f;"
            f"border:none;border-radius:8px;font-size:12px;font-weight:700;padding:0 18px;}}"
            f"QPushButton:hover{{background:#6eded6;}}"
        )
        btn_save.clicked.connect(self._on_save)

        bl.addWidget(btn_cancel)
        bl.addStretch()
        bl.addWidget(btn_save)
        return bar

    # ── Populators ────────────────────────────────────────────────────────────

    def _populate_decors(self):
        import core.decors as decors_api
        decors = decors_api.list_decors()
        self._decor_combo.clear()
        self._decor_combo.addItem("— Aucun décor —", "")
        self._decor_id_map = {}
        current_id   = self._shot.get("decor_id", "")
        current_name = self._shot.get("decor_name", "")
        for d in decors:
            did  = d.get("id", "")
            name = d.get("name", "")
            self._decor_combo.addItem(name, did)
            self._decor_id_map[did] = name
            if did == current_id:
                self._decor_combo.setCurrentText(name)
        if not current_id and current_name:
            self._decor_combo.setCurrentText(current_name)

    def _populate_accessories(self):
        import core.accessories as acc_api
        accs     = acc_api.list_accessories()
        selected = self._shot.get("accessory_ids", [])
        if not accs:
            lbl = QLabel("Aucun accessoire")
            lbl.setStyleSheet(f"color:{CP['text_dim']};font-size:10px;background:transparent;")
            self._acc_lay.addWidget(lbl)
            return
        for a in accs:
            aid  = a.get("id", "")
            name = a.get("name", "?")
            cb   = QCheckBox(name)
            cb.setChecked(aid in selected)
            cb.setStyleSheet(_CB_STYLE)
            self._acc_checks[aid] = cb
            self._acc_lay.addWidget(cb)
        self._acc_lay.addStretch()

    def _populate_characters(self):
        import core.casting as casting_api
        chars    = casting_api.list_characters()
        selected = self._shot.get("character_ids", [])
        if not chars:
            lbl = QLabel("Aucun personnage")
            lbl.setStyleSheet(f"color:{CP['text_dim']};font-size:10px;background:transparent;")
            self._char_lay.addWidget(lbl)
            return
        for c in chars:
            cid  = c.get("id", "")
            name = c.get("name", "?")
            cb   = QCheckBox(name)
            cb.setChecked(cid in selected)
            cb.setStyleSheet(_CB_STYLE)
            self._char_checks[cid] = cb
            self._char_lay.addWidget(cb)
        self._char_lay.addStretch()

    def _populate_vehicles(self):
        import core.vehicles as veh_api
        vehs     = veh_api.list_vehicles()
        selected = self._shot.get("vehicle_ids", [])
        if not vehs:
            lbl = QLabel("Aucun véhicule")
            lbl.setStyleSheet(f"color:{CP['text_dim']};font-size:10px;background:transparent;")
            self._veh_lay.addWidget(lbl)
            return
        for v in vehs:
            vid   = v.get("id", "")
            name  = v.get("name", "?")
            cat   = v.get("category", "")
            label = f"{name}  ({cat})" if cat else name
            cb    = QCheckBox(label)
            cb.setChecked(vid in selected)
            cb.setStyleSheet(_CB_STYLE)
            self._veh_checks[vid] = cb
            self._veh_lay.addWidget(cb)
        self._veh_lay.addStretch()

    # ── Enhance (Claude) ──────────────────────────────────────────────────────

    def _on_enhance_action(self):
        from api.enhance import EnhanceShotActionWorker
        text = self._scene_title.text().strip()
        if not text:
            self._enhance_status.setText("Écris une description avant d'améliorer.")
            return
        self._btn_enhance_action.setEnabled(False)
        self._btn_enhance_seedance.setEnabled(False)
        self._enhance_status.setText("Amélioration en cours…")
        self._worker_enhance_action = EnhanceShotActionWorker(text)
        self._worker_enhance_action.finished.connect(self._on_enhance_action_done)
        self._worker_enhance_action.failed.connect(self._on_enhance_fail)
        self._worker_enhance_action.start()

    def _on_enhance_action_done(self, result: str):
        self._scene_title.setText(result)
        self._btn_enhance_action.setEnabled(True)
        self._btn_enhance_seedance.setEnabled(True)
        self._enhance_status.setText("Description améliorée ✓")

    def _on_enhance_seedance(self):
        from api.enhance import EnhanceWorker
        text = self._seedance_prompt.toPlainText().strip()
        if not text:
            self._enhance_status.setText("Écris un prompt avant d'améliorer.")
            return
        self._btn_enhance_action.setEnabled(False)
        self._btn_enhance_seedance.setEnabled(False)
        self._enhance_status.setText("Optimisation en cours…")
        self._worker_enhance_seedance = EnhanceWorker(text)
        self._worker_enhance_seedance.finished.connect(self._on_enhance_seedance_done)
        self._worker_enhance_seedance.failed.connect(self._on_enhance_fail)
        self._worker_enhance_seedance.start()

    def _on_enhance_seedance_done(self, result: str):
        self._seedance_prompt.setPlainText(result)
        self._btn_enhance_action.setEnabled(True)
        self._btn_enhance_seedance.setEnabled(True)
        self._enhance_status.setText("Prompt optimisé ✓")

    def _on_enhance_fail(self, err: str):
        self._btn_enhance_action.setEnabled(True)
        self._btn_enhance_seedance.setEnabled(True)
        self._enhance_status.setText(f"Erreur : {err[:80]}")

    # ── Save ──────────────────────────────────────────────────────────────────

    def _on_save(self):
        # Characters
        char_ids   = [cid for cid, cb in self._char_checks.items() if cb.isChecked()]
        char_names = []
        import core.casting as casting_api
        for cid in char_ids:
            ch = casting_api.get_character(cid)
            if ch:
                char_names.append(ch.get("name", cid))

        # Accessories
        acc_ids   = [aid for aid, cb in self._acc_checks.items() if cb.isChecked()]
        acc_names = []
        import core.accessories as acc_api
        for aid in acc_ids:
            ac = acc_api.get_accessory(aid)
            if ac:
                acc_names.append(ac.get("name", aid))

        # Vehicles
        veh_ids   = [vid for vid, cb in self._veh_checks.items() if cb.isChecked()]
        veh_names = []
        import core.vehicles as veh_api
        for vid in veh_ids:
            vh = veh_api.get_vehicle(vid)
            if vh:
                veh_names.append(vh.get("name", vid))

        # Décor
        decor_idx  = self._decor_combo.currentIndex()
        decor_id   = self._decor_combo.itemData(decor_idx) if decor_idx >= 0 else ""
        decor_name = self._decor_combo.currentText() if decor_idx > 0 else ""

        # Seq notation
        try:
            seq_num = int(self._seq_num.text().strip())
        except ValueError:
            seq_num = self._shot.get("seq_num", 1)
        try:
            shot_in_seq = int(self._shot_in_seq.text().strip())
        except ValueError:
            shot_in_seq = self._shot.get("shot_in_seq", 1)

        duration = self._dur_slider.value() / 10.0

        data = dict(self._shot)
        data.update({
            "number":          self._shot.get("number", 0),
            "scene_title":     self._scene_title.text().strip(),
            "seq_num":         seq_num,
            "seq_name":        self._seq_name.text().strip(),
            "shot_in_seq":     shot_in_seq,
            "decor_id":        decor_id or "",
            "decor_name":      decor_name,
            "shot_time":       self._time_combo.currentText().strip(),
            "duration":        duration,
            "character_ids":   char_ids,
            "character_names": char_names,
            "accessory_ids":   acc_ids,
            "accessory_names": acc_names,
            "vehicle_ids":     veh_ids,
            "vehicle_names":   veh_names,
            "camera_movement":  self._cam_move.currentText(),
            "optic":            self._optic.currentText(),
            "focal":            self._focal.currentText(),
            "camera_distance":  self._camera_distance.currentText(),
            "shot_size":       self._shot_size.currentData() or "",
            "speed":           self._speed.currentText(),
            "comments":          self._comments.toPlainText().strip(),
            "seedance_prompt":   self._seedance_prompt.toPlainText().strip(),
            "image_path":        self._shot.get("image_path", ""),
            "camera_axis":       self._camera_axis.currentText() if self._camera_axis.currentText() != "—" else "",
            "camera_placement":  self._camera_placement.text().strip(),
            "actor_placement":   self._actor_placement.text().strip(),
            "chars_in":          self._chars_in.text().strip(),
            "chars_out":         self._chars_out.text().strip(),
            "mic_placement":     self._mic_placement.text().strip(),
        })
        self._saved_data = sb_api.save_shot(data)
        self.accept()

    def get_shot(self):
        return self._saved_data
