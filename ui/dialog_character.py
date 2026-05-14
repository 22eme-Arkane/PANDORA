import os
from PyQt6.QtWidgets import (
    QDialog, QWidget, QHBoxLayout, QVBoxLayout, QLabel, QPushButton,
    QLineEdit, QTextEdit, QComboBox, QProgressBar, QFileDialog,
    QMessageBox, QFrame, QScrollArea, QGridLayout, QCheckBox, QSpinBox,
)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QPixmap, QPixmapCache, QColor
from ui.styles import CP, PANDORA_STYLESHEET
from ui.icons import claude_icon_pixmap, install_hover_icon
from ui.creative_panel import NanoBananaControlsPanel
import core.casting as casting_api
from api.nano_banana import (
    OptimizePromptWorker, GeneratePortraitWorker,
    GeneratePortraitWithFaceIDWorker, OptimizeCharacterWithReferencesWorker,
    OptimizeStyleReferenceWorker, GeneratePortraitNB2EditWorker,
)

_ROLES = [
    "Lead Actor", "Lead Actress", "Supporting Actor", "Supporting Actress",
    "Lead Villain", "Antagonist", "Director", "Cinematographer",
    "Production Designer", "Costume Designer", "Sound Mixer",
    "VFX Lead", "Script Supervisor", "Animator", "Narrator", "Autre…",
]


def _lbl(text: str, size: int = 11, color: str | None = None) -> QLabel:
    l = QLabel(text)
    col = color or CP["text_secondary"]
    l.setStyleSheet(
        f"color:{col};font-size:{size}px;background:transparent;border:none;"
    )
    return l


def _combo_ss():
    return (
        f"QComboBox{{background:{CP['bg3']};border:1px solid {CP['border']};"
        f"border-radius:6px;color:{CP['text_primary']};font-size:11px;padding:0 8px;}}"
        f"QComboBox:focus{{border-color:{CP['accent_dim']};}}"
        f"QComboBox:disabled{{color:{CP['text_dim']};border-color:{CP['border']};"
        f"background:{CP['bg2']};}}"
        f"QComboBox::drop-down{{border:none;width:20px;}}"
        f"QComboBox QAbstractItemView{{background:{CP['bg3']};border:1px solid {CP['border_bright']};"
        f"color:{CP['text_primary']};selection-background-color:{CP['accent_dim']};font-size:11px;padding:4px;}}"
    )


def _input(placeholder: str = "", password: bool = False) -> QLineEdit:
    e = QLineEdit()
    e.setPlaceholderText(placeholder)
    e.setFixedHeight(36)
    if password:
        e.setEchoMode(QLineEdit.EchoMode.Password)
    e.setStyleSheet(
        f"QLineEdit{{background:{CP['bg3']};border:1px solid {CP['border']};"
        f"border-radius:6px;color:{CP['text_primary']};font-size:12px;padding:0 10px;}}"
        f"QLineEdit:focus{{border-color:{CP['accent']};}}"
    )
    return e


class _VariationChoiceDialog(QDialog):
    """Choix entre Générer à nouveau et Générer avec HMC."""

    REGENERATE = 1
    WITH_HMC   = 2

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Générer une variation")
        self.setFixedSize(370, 240)
        self.setStyleSheet(PANDORA_STYLESHEET + f"QDialog{{background:{CP['bg1']};}}")
        self._choice = 0

        lay = QVBoxLayout(self)
        lay.setContentsMargins(24, 20, 24, 20)
        lay.setSpacing(10)

        title = QLabel("Générer une variation")
        title.setStyleSheet(
            f"color:{CP['text_primary']};font-size:14px;font-weight:700;background:transparent;"
        )
        lay.addWidget(title)

        _ss_card = (
            f"QPushButton{{background:{CP['bg2']};border:1px solid {CP['border']};"
            f"border-radius:10px;text-align:left;padding:0;}}"
            f"QPushButton:hover{{background:{CP['bg3']};border-color:{CP['border_bright']};}}"
            f"QPushButton:pressed{{background:{CP['bg4']};}}"
        )

        def _card(icon: str, title_txt: str, sub_txt: str, cb) -> QPushButton:
            btn = QPushButton()
            btn.setFixedHeight(62)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setStyleSheet(_ss_card)
            btn.clicked.connect(cb)
            inner = QHBoxLayout(btn)
            inner.setContentsMargins(14, 0, 14, 0)
            inner.setSpacing(12)
            ico = QLabel(icon)
            ico.setFixedSize(34, 34)
            ico.setAlignment(Qt.AlignmentFlag.AlignCenter)
            ico.setStyleSheet(
                f"background:{CP['bg3']};border-radius:8px;font-size:18px;border:none;"
            )
            col = QVBoxLayout()
            col.setSpacing(2)
            t = QLabel(title_txt)
            t.setStyleSheet(
                f"color:{CP['text_primary']};font-size:12px;font-weight:700;"
                f"background:transparent;border:none;"
            )
            s = QLabel(sub_txt)
            s.setStyleSheet(
                f"color:{CP['text_dim']};font-size:9px;background:transparent;border:none;"
            )
            col.addWidget(t)
            col.addWidget(s)
            inner.addWidget(ico)
            inner.addLayout(col, 1)
            return btn

        lay.addWidget(_card(
            "🔄", "Générer à nouveau",
            "Relance une génération avec le même prompt.",
            self._choose_regen,
        ))
        lay.addWidget(_card(
            "✨", "Générer avec HMC",
            "Ajoute des costumes, maquillage ou coiffure au personnage.",
            self._choose_hmc,
        ))

        btn_cancel = QPushButton("Annuler")
        btn_cancel.setFixedHeight(34)
        btn_cancel.setStyleSheet(
            f"QPushButton{{background:transparent;color:{CP['text_dim']};"
            f"border:1px solid {CP['border']};border-radius:7px;"
            f"font-size:11px;font-weight:700;}}"
            f"QPushButton:hover{{background:{CP['bg2']};color:{CP['text_secondary']};}}"
        )
        btn_cancel.clicked.connect(self.reject)
        lay.addWidget(btn_cancel)

        from core.i18n import retranslate_widget
        retranslate_widget(self)

    def _choose_regen(self):
        self._choice = self.REGENERATE
        self.accept()

    def _choose_hmc(self):
        self._choice = self.WITH_HMC
        self.accept()

    def choice(self) -> int:
        return self._choice


class _HMCSelectorDialog(QDialog):
    """Sélection des éléments HMC à intégrer dans la génération.
    Deux sections : éléments assignés au personnage / tous les autres.
    """

    _TYPES  = ["Habit", "Maquillage", "Coiffure"]
    _ICONS  = {"Habit": "👗", "Maquillage": "💄", "Coiffure": "💇"}
    _COLORS = {"Habit": "#e8b860", "Maquillage": "#e06eb4", "Coiffure": "#8e7fff"}

    def __init__(self, parent=None, char_id: str = ""):
        super().__init__(parent)
        self.setWindowTitle("Générer avec HMC")
        self.setFixedSize(560, 580)
        self.setStyleSheet(PANDORA_STYLESHEET + f"QDialog{{background:{CP['bg1']};}}")
        self._checks: dict[str, QCheckBox] = {}

        lay = QVBoxLayout(self)
        lay.setContentsMargins(24, 20, 24, 20)
        lay.setSpacing(10)

        title = QLabel("Sélectionner les éléments HMC")
        title.setStyleSheet(
            f"color:{CP['text_primary']};font-size:14px;font-weight:700;background:transparent;"
        )
        lay.addWidget(title)

        import core.hmc as hmc_api
        all_items  = hmc_api.list_hmc_items()
        assigned   = [h for h in all_items if char_id in h.get("assigned_to", [])] if char_id else []
        assigned_ids = {h["id"] for h in assigned}
        others     = [h for h in all_items if h["id"] not in assigned_ids]

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet("QScrollArea{background:transparent;border:none;}")

        inner = QWidget()
        inner.setStyleSheet("background:transparent;")
        inner_lay = QVBoxLayout(inner)
        inner_lay.setContentsMargins(0, 0, 4, 0)
        inner_lay.setSpacing(5)

        # ── Section 1 : Assignés ───────────────────────────────────────────
        self._section_header(inner_lay, "Assignés à ce personnage", CP["accent"])
        if not assigned:
            self._empty_msg(inner_lay, "Aucun élément HMC assigné à ce personnage.")
        else:
            self._add_grouped(inner_lay, assigned)

        inner_lay.addSpacing(8)

        # ── Section 2 : Autres ─────────────────────────────────────────────
        self._section_header(inner_lay, "Autres éléments HMC", CP["text_secondary"])
        if not others:
            self._empty_msg(inner_lay, "Aucun autre élément HMC disponible.")
        else:
            self._add_grouped(inner_lay, others)

        inner_lay.addStretch()
        scroll.setWidget(inner)
        lay.addWidget(scroll, 1)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(10)

        btn_gen = QPushButton("✓  Générer avec la sélection")
        btn_gen.setFixedHeight(40)
        btn_gen.setStyleSheet(
            f"QPushButton{{background:{CP['accent']};color:#07080f;"
            f"border:none;border-radius:8px;font-size:12px;font-weight:700;padding:0 18px;}}"
            f"QPushButton:hover{{background:#6eded6;}}"
            f"QPushButton:pressed{{background:{CP['accent_dim']};color:#fff;}}"
        )
        btn_gen.clicked.connect(self.accept)

        btn_cancel = QPushButton("Annuler")
        btn_cancel.setFixedHeight(40)
        btn_cancel.setStyleSheet(
            f"QPushButton{{background:transparent;color:{CP['text_secondary']};"
            f"border:1px solid {CP['border']};border-radius:8px;"
            f"font-size:12px;font-weight:700;padding:0 18px;}}"
            f"QPushButton:hover{{background:{CP['bg3']};color:{CP['text_primary']};}}"
        )
        btn_cancel.clicked.connect(self.reject)

        btn_row.addWidget(btn_gen, 1)
        btn_row.addWidget(btn_cancel)
        lay.addLayout(btn_row)

        from core.i18n import retranslate_widget
        retranslate_widget(self)

    def _section_header(self, lay: QVBoxLayout, text: str, color: str):
        w = QWidget()
        w.setStyleSheet("background:transparent;border:none;")
        hl = QHBoxLayout(w)
        hl.setContentsMargins(0, 4, 0, 2)
        hl.setSpacing(8)
        lbl = QLabel(text.upper())
        lbl.setStyleSheet(
            f"color:{color};font-size:9px;font-weight:700;"
            f"font-family:'Consolas',monospace;background:transparent;border:none;"
            f"letter-spacing:0.8px;"
        )
        line = QFrame()
        line.setFixedHeight(1)
        line.setStyleSheet(f"background:{CP['border']};border:none;")
        hl.addWidget(lbl)
        hl.addWidget(line, 1)
        lay.addWidget(w)

    def _empty_msg(self, lay: QVBoxLayout, msg: str):
        lbl = QLabel(msg)
        lbl.setWordWrap(True)
        lbl.setStyleSheet(
            f"color:{CP['text_dim']};font-size:10px;background:transparent;"
            f"border:none;padding:4px 2px;"
        )
        lay.addWidget(lbl)

    def _add_grouped(self, lay: QVBoxLayout, items: list):
        for hmc_type in self._TYPES:
            group = [h for h in items if h.get("hmc_type") == hmc_type]
            if not group:
                continue
            # Type badge
            type_w = QLabel(f"  {self._ICONS.get(hmc_type, '✂')}  {hmc_type}")
            type_w.setStyleSheet(
                f"color:{self._COLORS.get(hmc_type, CP['text_secondary'])};"
                f"font-size:9px;font-weight:700;background:transparent;"
                f"border:none;padding:3px 0 1px 0;"
            )
            lay.addWidget(type_w)
            for item in group:
                lay.addWidget(self._item_row(item))

    def _item_row(self, item: dict) -> QFrame:
        hid = item["id"]
        row = QFrame()
        row.setStyleSheet(
            f"QFrame{{background:{CP['bg2']};border:1px solid {CP['border']};border-radius:6px;}}"
        )
        rl = QHBoxLayout(row)
        rl.setContentsMargins(10, 7, 10, 7)
        rl.setSpacing(10)

        cb = QCheckBox()
        cb.setStyleSheet(
            f"QCheckBox::indicator{{width:16px;height:16px;border-radius:4px;"
            f"border:2px solid {CP['border_bright']};background:{CP['bg3']};}}"
            f"QCheckBox::indicator:checked{{background:{CP['accent']};border-color:{CP['accent']};}}"
        )
        self._checks[hid] = cb
        rl.addWidget(cb)

        hmc_type = item.get("hmc_type", "")
        ico = QLabel(self._ICONS.get(hmc_type, "✂"))
        ico.setFixedSize(26, 26)
        ico.setAlignment(Qt.AlignmentFlag.AlignCenter)
        ico.setStyleSheet(
            f"background:{CP['bg3']};border-radius:5px;font-size:13px;border:none;"
        )
        rl.addWidget(ico)

        col = QVBoxLayout()
        col.setSpacing(1)
        name_lbl = QLabel(item.get("name", "—"))
        name_lbl.setStyleSheet(
            f"color:{CP['text_primary']};font-size:11px;font-weight:700;"
            f"background:transparent;border:none;"
        )
        type_lbl = QLabel(hmc_type)
        type_lbl.setStyleSheet(
            f"color:{self._COLORS.get(hmc_type, CP['text_dim'])};font-size:9px;"
            f"background:transparent;border:none;"
        )
        col.addWidget(name_lbl)
        col.addWidget(type_lbl)
        rl.addLayout(col, 1)
        return row

    def selected_ids(self) -> set:
        return {hid for hid, cb in self._checks.items() if cb.isChecked()}


class _FullscreenDialog(QDialog):
    """Aperçu plein écran avec navigation, suppression et sélection."""

    _IMG_W, _IMG_H = 860, 510
    _AW,    _AH    = 52,  88

    def __init__(self, parent, generated_images: list, start_idx: int,
                 active_idx: int = -1, fallback_path: str = "",
                 extra_buttons: list | None = None):
        super().__init__(parent)
        self.setWindowTitle("Aperçu du personnage")
        self.setFixedSize(900, 700)
        self.setStyleSheet(PANDORA_STYLESHEET + f"QDialog{{background:{CP['bg0']};}}")

        # _data: list of [original_idx, entry_dict, display_path]
        self._data: list[list] = []
        for i, entry in enumerate(generated_images):
            s = entry.get("sheet", "")
            p = entry.get("portrait", "")
            path = s if (s and os.path.isfile(s)) else (p if (p and os.path.isfile(p)) else "")
            self._data.append([i, entry, path])

        if not self._data and fallback_path and os.path.isfile(fallback_path):
            self._data = [[0, {"portrait": fallback_path, "sheet": ""}, fallback_path]]

        self._deleted_origs: set[int] = set()
        self._used_entry:    dict | None = None
        self._active_orig:   int         = active_idx  # orig_idx of currently active image

        n = len(self._data)
        self._idx = max(0, min(start_idx, n - 1)) if n > 0 else 0

        lay = QVBoxLayout(self)
        lay.setContentsMargins(20, 16, 20, 16)
        lay.setSpacing(10)

        # ── Image + arrows ─────────────────────────────────────────────────
        container = QWidget()
        container.setFixedSize(self._IMG_W, self._IMG_H)
        container.setStyleSheet(f"background:{CP['bg2']};border-radius:10px;")

        self._img_lbl = QLabel(container)
        self._img_lbl.setGeometry(0, 0, self._IMG_W, self._IMG_H)
        self._img_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._img_lbl.setStyleSheet("background:transparent;")
        self._img_lbl.setText("Aucune image")

        _a = "border:none;color:#fff;font-size:30px;font-weight:900;"
        self._btn_left = QPushButton("‹", container)
        self._btn_left.setGeometry(0, (self._IMG_H - self._AH) // 2, self._AW, self._AH)
        self._btn_left.setStyleSheet(
            f"QPushButton{{{_a}background:rgba(0,0,0,0.40);"
            f"border-top-right-radius:8px;border-bottom-right-radius:8px;}}"
            f"QPushButton:hover{{background:rgba(0,0,0,0.65);}}"
        )
        self._btn_left.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_left.clicked.connect(lambda: self._navigate(-1))

        self._btn_right = QPushButton("›", container)
        self._btn_right.setGeometry(self._IMG_W - self._AW, (self._IMG_H - self._AH) // 2, self._AW, self._AH)
        self._btn_right.setStyleSheet(
            f"QPushButton{{{_a}background:rgba(0,0,0,0.40);"
            f"border-top-left-radius:8px;border-bottom-left-radius:8px;}}"
            f"QPushButton:hover{{background:rgba(0,0,0,0.65);}}"
        )
        self._btn_right.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_right.clicked.connect(lambda: self._navigate(1))

        lay.addWidget(container, alignment=Qt.AlignmentFlag.AlignCenter)

        # ── Thumbnails ─────────────────────────────────────────────────────
        self._thumb_scroll = QScrollArea()
        self._thumb_scroll.setFixedHeight(84)
        self._thumb_scroll.setWidgetResizable(True)
        self._thumb_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self._thumb_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._thumb_scroll.setStyleSheet(f"""
            QScrollArea{{background:transparent;border:none;}}
            QScrollBar:horizontal{{height:4px;background:{CP['bg3']};border-radius:2px;margin:0;}}
            QScrollBar::handle:horizontal{{background:{CP['border_bright']};border-radius:2px;min-width:20px;}}
            QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal{{width:0;}}
        """)
        self._thumb_widget = QWidget()
        self._thumb_widget.setStyleSheet("background:transparent;")
        self._thumb_lay = QHBoxLayout(self._thumb_widget)
        self._thumb_lay.setContentsMargins(0, 6, 0, 6)
        self._thumb_lay.setSpacing(8)
        self._thumb_lay.setAlignment(Qt.AlignmentFlag.AlignLeft)
        self._thumb_scroll.setWidget(self._thumb_widget)
        lay.addWidget(self._thumb_scroll)

        # ── Buttons ────────────────────────────────────────────────────────
        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)

        self._btn_del = QPushButton("🗑  Supprimer cette image")
        self._btn_del.setFixedHeight(34)
        self._btn_del.setEnabled(bool(self._data))
        self._btn_del.setStyleSheet(
            f"QPushButton{{background:transparent;color:{CP['red']};"
            f"border:1px solid rgba(255,79,106,0.35);border-radius:7px;"
            f"font-size:10px;font-weight:700;padding:0 12px;}}"
            f"QPushButton:hover{{background:rgba(255,79,106,0.12);border-color:{CP['red']};}}"
            f"QPushButton:disabled{{opacity:0.30;}}"
        )
        self._btn_del.clicked.connect(self._on_delete)
        btn_row.addWidget(self._btn_del)

        for _lbl_txt, _cb in (extra_buttons or []):
            _btn_extra = QPushButton(_lbl_txt)
            _btn_extra.setFixedHeight(34)
            _btn_extra.setEnabled(bool(self._data))
            _btn_extra.setStyleSheet(
                f"QPushButton{{background:transparent;color:{CP['accent']};"
                f"border:1px solid {CP['accent_dim']};border-radius:7px;"
                f"font-size:10px;font-weight:700;padding:0 12px;}}"
                f"QPushButton:hover{{background:{CP['accent_dim']};color:#07080f;}}"
                f"QPushButton:disabled{{opacity:0.30;}}"
            )
            _btn_extra.clicked.connect(_cb)
            btn_row.addWidget(_btn_extra)

        btn_row.addStretch()

        self._btn_use = QPushButton()
        self._btn_use.setFixedHeight(34)
        self._btn_use.setEnabled(bool(self._data))
        self._btn_use.clicked.connect(self._on_use)
        btn_row.addWidget(self._btn_use)

        btn_close = QPushButton("Fermer")
        btn_close.setFixedHeight(34)
        btn_close.setStyleSheet(
            f"QPushButton{{background:transparent;color:{CP['text_secondary']};"
            f"border:1px solid {CP['border']};border-radius:7px;"
            f"font-size:11px;font-weight:700;padding:0 16px;}}"
            f"QPushButton:hover{{background:{CP['bg3']};color:{CP['text_primary']};}}"
        )
        btn_close.clicked.connect(self.reject)
        btn_row.addWidget(btn_close)

        lay.addLayout(btn_row)

        # ── Initial state ──────────────────────────────────────────────────
        self._thumb_frames: list[QFrame] = []
        self._rebuild_thumbs()
        if self._data:
            self._load_image(self._idx)
            self._update_arrows()
            self._update_use_btn()

    # ── Thumb management ───────────────────────────────────────────────────

    def _rebuild_thumbs(self):
        while self._thumb_lay.count():
            item = self._thumb_lay.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        self._thumb_frames = []
        for i, (orig_i, entry, path) in enumerate(self._data):
            frame = QFrame()
            frame.setFixedSize(68, 68)
            frame.setCursor(Qt.CursorShape.PointingHandCursor)
            frame.mousePressEvent = lambda e, idx=i: self._jump_to(idx)

            lbl = QLabel(frame)
            lbl.setGeometry(3, 3, 60, 60)
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lbl.mousePressEvent = lambda e, idx=i: self._jump_to(idx)

            pix = QPixmap(path) if (path and os.path.isfile(path)) else QPixmap()
            if not pix.isNull():
                pix = pix.scaled(60, 60, Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                                  Qt.TransformationMode.SmoothTransformation)
                pix = pix.copy((pix.width()-60)//2, (pix.height()-60)//2, 60, 60)
                lbl.setPixmap(pix)
            else:
                lbl.setStyleSheet(f"color:{CP['text_dim']};font-size:18px;background:transparent;")
                lbl.setText("?")

            num = QLabel(f"{orig_i+1}", frame)
            num.setGeometry(2, 2, 18, 18)
            num.setAlignment(Qt.AlignmentFlag.AlignCenter)
            num.setStyleSheet(
                "color:#fff;background:rgba(0,0,0,0.55);border-radius:3px;"
                "font-size:8px;font-weight:700;border:none;"
            )
            num.mousePressEvent = lambda e, idx=i: self._jump_to(idx)

            self._thumb_frames.append(frame)
            self._thumb_lay.addWidget(frame)

        if not self._data:
            no_img = QLabel("Aucune image")
            no_img.setStyleSheet(f"color:{CP['text_dim']};font-size:11px;background:transparent;")
            self._thumb_lay.addWidget(no_img)

        self._thumb_lay.addStretch()
        self._update_thumbs()

    def _update_thumbs(self):
        for i, frame in enumerate(self._thumb_frames):
            if i >= len(self._data):
                continue
            orig_i     = self._data[i][0]
            is_active  = orig_i == self._active_orig
            is_current = i == self._idx
            if is_current:
                border = CP["accent2"]
            elif is_active:
                border = CP["green"]
            else:
                border = CP["border"]
            frame.setStyleSheet(
                f"QFrame{{background:{CP['bg2']};border:2px solid {border};border-radius:8px;}}"
            )

    def _update_arrows(self):
        multi = len(self._data) > 1
        self._btn_left.setVisible(multi)
        self._btn_right.setVisible(multi)

    def _update_use_btn(self):
        has = bool(self._data)
        self._btn_use.setEnabled(has)
        if not has:
            self._btn_use.setText("Utiliser")
            return
        orig_i = self._data[self._idx][0]
        if orig_i == self._active_orig:
            self._btn_use.setText("✓  Active")
            self._btn_use.setStyleSheet(
                f"QPushButton{{background:rgba(61,220,151,0.15);color:{CP['green']};"
                f"border:1px solid rgba(61,220,151,0.40);border-radius:7px;"
                f"font-size:11px;font-weight:700;padding:0 14px;}}"
                f"QPushButton:hover{{background:rgba(61,220,151,0.25);}}"
                f"QPushButton:pressed{{background:rgba(61,220,151,0.35);}}"
            )
        else:
            self._btn_use.setText("✓  Utiliser")
            self._btn_use.setStyleSheet(
                f"QPushButton{{background:{CP['accent2']};color:#fff;"
                f"border:none;border-radius:7px;"
                f"font-size:11px;font-weight:700;padding:0 14px;}}"
                f"QPushButton:hover{{background:#9d8fff;}}"
                f"QPushButton:pressed{{background:{CP['accent2_dim']};}}"
            )

    # ── Navigation ─────────────────────────────────────────────────────────

    def _load_image(self, idx: int):
        if not (0 <= idx < len(self._data)):
            self._img_lbl.setPixmap(QPixmap())
            self._img_lbl.setText("Aucune image")
            return
        path = self._data[idx][2]
        if not path or not os.path.isfile(path):
            self._img_lbl.setPixmap(QPixmap())
            self._img_lbl.setText("Image non disponible")
            return
        pix = QPixmap(path)
        if not pix.isNull():
            pix = pix.scaled(self._IMG_W, self._IMG_H, Qt.AspectRatioMode.KeepAspectRatio,
                              Qt.TransformationMode.SmoothTransformation)
            self._img_lbl.setPixmap(pix)
            self._img_lbl.setText("")
        else:
            self._img_lbl.setText("Impossible de charger l'image.")

    def _navigate(self, delta: int):
        n = len(self._data)
        if n <= 1:
            return
        self._idx = (self._idx + delta) % n
        self._load_image(self._idx)
        self._update_thumbs()
        self._update_use_btn()

    def _jump_to(self, idx: int):
        if idx == self._idx or not (0 <= idx < len(self._data)):
            return
        self._idx = idx
        self._load_image(idx)
        self._update_thumbs()
        self._update_use_btn()

    # ── Actions ────────────────────────────────────────────────────────────

    def _on_delete(self):
        n = len(self._data)
        if n == 0:
            return
        orig_i = self._data[self._idx][0]
        self._deleted_origs.add(orig_i)
        if orig_i == self._active_orig:
            self._active_orig = -1
        self._data.pop(self._idx)
        n -= 1
        if n == 0:
            self.reject()
            return
        self._idx = min(self._idx, n - 1)
        self._rebuild_thumbs()
        self._load_image(self._idx)
        self._update_arrows()
        self._update_use_btn()

    def _on_use(self):
        if 0 <= self._idx < len(self._data):
            self._used_entry  = self._data[self._idx][1]
            self._active_orig = self._data[self._idx][0]
            self._update_thumbs()
            self._update_use_btn()
            self.accept()

    def chosen_entry(self) -> tuple:
        if self._used_entry is not None:
            for orig_i, entry, _ in self._data:
                if entry is self._used_entry:
                    return entry, orig_i
        return None, -1

    def deleted_indices(self) -> set[int]:
        return self._deleted_origs


class CharacterDialog(QDialog):

    def __init__(self, parent=None, character: dict | None = None):
        super().__init__(parent)
        if character and character.get("id"):
            fresh = casting_api.get_character(character["id"])
            self._char = fresh if fresh else character
        else:
            self._char = character or {}
        self._image_path  = self._char.get("image_path", "")
        self._sheet_path  = self._char.get("sheet_path", "")
        self._ref_paths   = list(self._char.get("ref_paths", []))
        self._worker_opt  = None
        self._worker_refs = None
        self._worker_gen  = None
        self._saved_data         = None
        self._generated_images   = list(self._char.get("generated_images", []))
        # Init _preview_idx to whichever entry matches _image_path / _sheet_path
        self._preview_idx = 0
        for _i, _e in enumerate(self._generated_images):
            _p, _s = _e.get("portrait", ""), _e.get("sheet", "")
            if (self._image_path and (_p == self._image_path or _s == self._image_path)) or \
               (self._sheet_path and (_s == self._sheet_path or _p == self._sheet_path)):
                self._preview_idx = _i
                break
        self._active_acc_ids     = set(self._char.get("accessory_ids", []))
        self._active_hmc_ids     = set(self._char.get("hmc_ids", []))
        self._hmc_for_gen:   set[str] = set()  # HMC to apply to next generation

        self.setWindowTitle("Créer un personnage" if not character else "Modifier le personnage")
        from PyQt6.QtWidgets import QApplication as _QApp
        _geo = _QApp.primaryScreen().availableGeometry()
        self.resize(min(max(900, int(_geo.width() * 0.70)), 1200),
                    min(max(680, int(_geo.height() * 0.82)), 900))
        self.setMinimumSize(840, 600)
        self.setStyleSheet(PANDORA_STYLESHEET + f"QDialog{{background:{CP['bg1']};}}")

        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        root.addWidget(self._build_form(), 1)

        sep = QFrame()
        sep.setFixedWidth(1)
        sep.setStyleSheet(f"background:{CP['border']};")
        root.addWidget(sep)

        root.addWidget(self._build_preview(), 0)

        from core.i18n import retranslate_widget
        retranslate_widget(self)

    # ── Panneau gauche (formulaire) ───────────────────────────────────────────

    def _build_form(self) -> QWidget:
        outer = QWidget()
        outer.setStyleSheet(f"background:{CP['bg1']};")
        outer_lay = QVBoxLayout(outer)
        outer_lay.setContentsMargins(0, 0, 0, 0)
        outer_lay.setSpacing(0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet(f"""
            QScrollArea{{background:{CP['bg1']};border:none;}}
            QScrollBar:vertical{{width:6px;background:{CP['bg2']};border-radius:3px;margin:0;}}
            QScrollBar::handle:vertical{{background:{CP['border_bright']};border-radius:3px;min-height:20px;}}
            QScrollBar::add-line:vertical,QScrollBar::sub-line:vertical{{height:0;}}
        """)

        w = QWidget()
        w.setStyleSheet(f"background:{CP['bg1']};")
        lay = QVBoxLayout(w)
        lay.setContentsMargins(28, 24, 24, 24)
        lay.setSpacing(10)

        title = QLabel("Nouveau personnage" if not self._char else "Modifier le personnage")
        title.setStyleSheet(
            f"color:{CP['text_primary']};font-size:18px;font-weight:700;background:transparent;"
        )
        lay.addWidget(title)
        lay.addSpacing(2)

        row = QHBoxLayout()
        row.setSpacing(12)

        col_name = QVBoxLayout()
        col_name.setSpacing(4)
        col_name.addWidget(_lbl("Nom du personnage"))
        self._name = _input("Ex: Marcus Thorne")
        self._name.setText(self._char.get("name", ""))
        col_name.addWidget(self._name)

        col_role = QVBoxLayout()
        col_role.setSpacing(4)
        col_role.addWidget(_lbl("Rôle"))
        self._role = QComboBox()
        self._role.setEditable(True)
        self._role.addItems(_ROLES)
        current_role = self._char.get("role", "")
        if current_role and current_role not in _ROLES:
            self._role.insertItem(0, current_role)
        self._role.setCurrentText(current_role or _ROLES[0])
        self._role.setFixedHeight(36)
        self._role.setStyleSheet(
            f"QComboBox{{background:{CP['bg3']};border:1px solid {CP['border']};"
            f"border-radius:6px;color:{CP['text_primary']};font-size:12px;padding:0 10px;}}"
            f"QComboBox:focus{{border-color:{CP['accent']};}}"
            f"QComboBox::drop-down{{border:none;width:20px;}}"
            f"QComboBox QAbstractItemView{{background:{CP['bg3']};"
            f"border:1px solid {CP['border_bright']};color:{CP['text_primary']};"
            f"selection-background-color:{CP['accent_dim']};}}"
        )
        col_role.addWidget(self._role)

        row.addLayout(col_name, 2)
        row.addLayout(col_role, 1)
        lay.addLayout(row)

        warn = QLabel(
            "⚠  Seedance 2.0 et Nano Banana appliquent des filtres de contenu (ByteDance / fal.ai). "
            "Certains sujets peuvent être refusés ou modifiés. Reformule le prompt en cas d'erreur."
        )
        warn.setWordWrap(True)
        warn.setStyleSheet(
            f"color:{CP['orange']};font-size:10px;font-family:'Consolas',monospace;"
            f"background:rgba(255,140,66,0.08);border:1px solid rgba(255,140,66,0.25);"
            f"border-radius:6px;padding:8px 10px;"
        )
        lay.addWidget(warn)

        prompt_header = QHBoxLayout()
        prompt_header.setContentsMargins(0, 0, 0, 0)
        prompt_header.setSpacing(8)
        prompt_header.addWidget(_lbl("Prompt pour Nano Banana"))
        prompt_header.addStretch()

        self._btn_cloud = QPushButton()
        self._btn_cloud.setFixedSize(26, 26)
        self._btn_cloud.setToolTip(
            "Optimiser avec Claude\n"
            "Améliore ou génère le prompt via l'API Anthropic\n"
            "pour de meilleurs résultats avec Nano Banana."
        )
        self._btn_cloud.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_cloud.setStyleSheet("""
            QPushButton{background:transparent;border:none;border-radius:5px;padding:0;}
            QPushButton:hover{background:rgba(78,205,196,0.12);}
            QPushButton:pressed{background:rgba(78,205,196,0.22);}
            QPushButton:disabled{opacity:0.3;}
        """)
        pix_n = claude_icon_pixmap(15, CP["text_dim"])
        pix_h = claude_icon_pixmap(15, CP["accent"])
        if not pix_n.isNull():
            install_hover_icon(self._btn_cloud, pix_n, pix_h, icon_size=15)
        else:
            self._btn_cloud.setText("☁")
        self._btn_cloud.clicked.connect(self._on_optimize)
        prompt_header.addWidget(self._btn_cloud)
        lay.addLayout(prompt_header)

        self._prompt = QTextEdit()
        self._prompt.setPlaceholderText(
            "Décris le personnage ou écris directement le prompt…\n"
            "Ex : Middle-aged man, dark hair, strong jaw, Mediterranean features, "
            "navy suit, confident expression.\n\n"
            "Clique sur ☁ pour optimiser via Claude."
        )
        self._prompt.setPlainText(
            self._char.get("prompt", "") or self._char.get("description", "")
        )
        self._prompt.setFixedHeight(130)
        self._prompt.setStyleSheet(
            f"QTextEdit{{background:{CP['bg3']};border:1px solid {CP['border']};"
            f"border-radius:6px;color:{CP['text_primary']};font-size:12px;padding:8px;}}"
            f"QTextEdit:focus{{border-color:{CP['accent']};}}"
        )
        lay.addWidget(self._prompt)

        refs_header = QHBoxLayout()
        refs_header.setContentsMargins(0, 0, 0, 0)
        refs_header.addWidget(_lbl("Références visuelles"))
        refs_header.addStretch()
        self._refs_hint_lbl = _lbl("Utilisées par Claude pour enrichir le prompt", size=10, color=CP["text_dim"])
        refs_header.addWidget(self._refs_hint_lbl)
        lay.addLayout(refs_header)

        self._refs_scroll = QScrollArea()
        self._refs_scroll.setFixedHeight(80)
        self._refs_scroll.setWidgetResizable(True)
        self._refs_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self._refs_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._refs_scroll.setStyleSheet(f"""
            QScrollArea{{
                background:{CP['bg2']};border:1px solid {CP['border']};
                border-radius:8px;
            }}
            QScrollBar:horizontal{{
                height:4px;background:{CP['bg3']};border-radius:2px;margin:0;
            }}
            QScrollBar::handle:horizontal{{
                background:{CP['border_bright']};border-radius:2px;min-width:20px;
            }}
            QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal{{width:0;}}
        """)
        self._refs_container = QWidget()
        self._refs_container.setStyleSheet(f"background:{CP['bg2']};")
        self._refs_layout = QHBoxLayout(self._refs_container)
        self._refs_layout.setContentsMargins(8, 8, 8, 8)
        self._refs_layout.setSpacing(8)
        self._refs_scroll.setWidget(self._refs_container)
        self._refresh_refs_display()
        lay.addWidget(self._refs_scroll)

        # Usage des références visuelles
        _ur = QHBoxLayout()
        _ur.setSpacing(8)
        _ur_lbl = _lbl("Usage des références")
        _ur_lbl.setFixedWidth(150)
        _ur.addWidget(_ur_lbl)
        self._ref_usage_combo = QComboBox()
        self._ref_usage_combo.addItem("🌟  Inspiration  —  Claude enrichit le prompt", "inspiration")
        self._ref_usage_combo.addItem("🎨  Style pictural  —  extrait et applique le style visuel", "style")
        self._ref_usage_combo.addItem("🧑  Référence de visage  —  génère le portrait avec ce visage", "face")
        self._ref_usage_combo.setFixedHeight(30)
        self._ref_usage_combo.setStyleSheet(_combo_ss())
        _saved_usage = self._char.get("ref_usage_key", "inspiration")
        for _i in range(self._ref_usage_combo.count()):
            if self._ref_usage_combo.itemData(_i) == _saved_usage:
                self._ref_usage_combo.setCurrentIndex(_i)
                break
        self._ref_usage_combo.currentIndexChanged.connect(self._on_ref_usage_changed)
        _ur.addWidget(self._ref_usage_combo, 1)
        lay.addLayout(_ur)

        # Style d'image pour la génération
        _style_row = QHBoxLayout()
        _style_row.setSpacing(8)
        _style_lbl_w = QLabel("Style d'image :")
        _style_lbl_w.setStyleSheet(
            f"color:{CP['text_secondary']};font-size:11px;background:transparent;border:none;"
        )
        _style_lbl_w.setFixedWidth(150)
        _style_row.addWidget(_style_lbl_w)
        import core.style as _style_mod
        self._portrait_style_combo = QComboBox()
        self._portrait_style_combo.addItem("— Aucun —", "")
        _cur_grp = None
        for _s in _style_mod.STYLES:
            _g = _s.get("group", "")
            if _g != _cur_grp:
                _cur_grp = _g
                _gi = next((g for g in _style_mod.GROUPS if g["key"] == _g), None)
                if _gi:
                    self._portrait_style_combo.addItem(
                        f"  {_gi['icon']}  {_gi['name'].upper()}", "__sep__"
                    )
                    _sep_item = self._portrait_style_combo.model().item(
                        self._portrait_style_combo.count() - 1
                    )
                    _sep_item.setEnabled(False)
                    _sep_item.setForeground(QColor(CP.get("accent", "#7c6bff")))
            self._portrait_style_combo.addItem(f"    {_s['icon']}  {_s['name']}", _s["key"])
        self._portrait_style_combo.setFixedHeight(32)
        self._portrait_style_combo.setStyleSheet(
            f"QComboBox{{background:{CP['bg3']};border:1px solid {CP['border']};"
            f"border-radius:6px;color:{CP['text_primary']};font-size:11px;padding:0 8px;}}"
            f"QComboBox:focus{{border-color:{CP['accent']};}}"
            f"QComboBox::drop-down{{border:none;width:18px;}}"
            f"QComboBox QAbstractItemView{{background:{CP['bg2']};border:1px solid {CP['border_bright']};"
            f"color:{CP['text_primary']};selection-background-color:{CP['accent_dim']};"
            f"font-size:11px;padding:4px;}}"
        )
        # Pré-sélectionner le style du projet par défaut
        _default_key = _style_mod.get_style_key()
        if _default_key:
            for _i in range(self._portrait_style_combo.count()):
                if self._portrait_style_combo.itemData(_i) == _default_key:
                    self._portrait_style_combo.setCurrentIndex(_i)
                    break
        _style_row.addWidget(self._portrait_style_combo, 1)
        lay.addLayout(_style_row)
        self._on_ref_usage_changed()

        # ── Style de génération ───────────────────────────────────────────────
        _gen_mode_row = QHBoxLayout()
        _gen_mode_row.setSpacing(8)
        _gen_mode_lbl = QLabel("Style de génération :")
        _gen_mode_lbl.setStyleSheet(
            f"color:{CP['text_secondary']};font-size:11px;background:transparent;border:none;"
        )
        _gen_mode_lbl.setFixedWidth(150)
        _gen_mode_row.addWidget(_gen_mode_lbl)
        self._gen_mode_combo = QComboBox()
        _GEN_MODES = [
            ("🎬  Character Sheet 5 vues",          "sheet_5views"),
            ("📷  Portrait classique",               "classic"),
            ("🎭  Portrait éditorial (buste serré)", "editorial"),
            ("⚡  Pose d'action dynamique",          "action"),
            ("👥  Duo / Groupe",                     "duo"),
            ("🖼  Avec photo de référence (PuLID)",  "photo_ref"),
        ]
        for _label, _key in _GEN_MODES:
            self._gen_mode_combo.addItem(_label, _key)
        self._gen_mode_combo.setFixedHeight(32)
        self._gen_mode_combo.setStyleSheet(
            f"QComboBox{{background:{CP['bg3']};border:1px solid {CP['border']};"
            f"border-radius:6px;color:{CP['text_primary']};font-size:11px;padding:0 8px;}}"
            f"QComboBox:focus{{border-color:{CP['accent']};}}"
            f"QComboBox::drop-down{{border:none;width:20px;}}"
            f"QComboBox QAbstractItemView{{background:{CP['bg3']};"
            f"border:1px solid {CP['border_bright']};color:{CP['text_primary']};"
            f"selection-background-color:{CP['accent_dim']};font-size:11px;padding:4px;}}"
        )
        self._gen_mode_combo.currentIndexChanged.connect(self._on_gen_mode_changed)
        _gen_mode_row.addWidget(self._gen_mode_combo, 1)
        lay.addLayout(_gen_mode_row)

        self._gen_mode_hint = QLabel("")
        self._gen_mode_hint.setWordWrap(True)
        self._gen_mode_hint.setStyleSheet(
            f"color:{CP['text_dim']};font-size:10px;background:transparent;border:none;"
        )
        lay.addWidget(self._gen_mode_hint)
        self._on_gen_mode_changed(0)

        sep_c = QFrame(); sep_c.setFixedHeight(1)
        sep_c.setStyleSheet(f"background:{CP['border']};")
        lay.addWidget(sep_c)
        self._creative = NanoBananaControlsPanel()
        lay.addWidget(self._creative)

        # Modèle Nano Banana
        _m_row = QHBoxLayout()
        _m_row.setSpacing(8)
        _m_lbl = _lbl("Modèle")
        _m_lbl.setFixedWidth(60)
        _m_row.addWidget(_m_lbl)
        self._model_combo = QComboBox()
        self._model_combo.addItem("Nano Banana 2  —  rapide  ·  $0.08", "nb2")
        self._model_combo.addItem("Nano Banana Pro  —  qualité  ·  $0.15", "nb_pro")
        from core.config import load_config as _lc_m
        if _lc_m().get("image_model", "nb2") == "nb_pro":
            self._model_combo.setCurrentIndex(1)
        self._model_combo.setFixedHeight(30)
        self._model_combo.setStyleSheet(
            f"QComboBox{{background:{CP['bg3']};border:1px solid {CP['border']};"
            f"border-radius:6px;color:{CP['text_primary']};font-size:11px;padding:0 8px;}}"
            f"QComboBox::drop-down{{border:none;width:20px;}}"
            f"QComboBox QAbstractItemView{{background:{CP['bg3']};border:1px solid {CP['border_bright']};"
            f"color:{CP['text_primary']};selection-background-color:{CP['accent_dim']};}}"
        )
        _m_row.addWidget(self._model_combo, 1)
        lay.addLayout(_m_row)

        _gen_row = QHBoxLayout()
        _gen_row.setSpacing(8)
        btn_gen = QPushButton("🎨  Générer le portrait")
        btn_gen.setFixedHeight(40)
        btn_gen.setStyleSheet(
            f"QPushButton{{background:{CP['accent']};color:#07080f;"
            f"border:none;border-radius:8px;font-size:12px;font-weight:700;letter-spacing:0.5px;}}"
            f"QPushButton:hover{{background:#6eded6;}}"
            f"QPushButton:pressed{{background:{CP['accent_dim']};color:#fff;}}"
            f"QPushButton:disabled{{background:{CP['bg3']};color:{CP['text_dim']};}}"
        )
        btn_gen.clicked.connect(self._on_generate)
        self._btn_gen = btn_gen
        _gen_row.addWidget(btn_gen, 1)
        _x_lbl = QLabel("×")
        _x_lbl.setFixedWidth(14)
        _x_lbl.setStyleSheet(f"color:{CP['text_dim']};font-size:12px;background:transparent;")
        _gen_row.addWidget(_x_lbl)
        self._spinbox_count = QSpinBox()
        self._spinbox_count.setRange(1, 4)
        self._spinbox_count.setValue(1)
        self._spinbox_count.setFixedSize(50, 40)
        self._spinbox_count.setToolTip("Nombre de portraits à générer (1–4) — choisir parmi les résultats")
        self._spinbox_count.setStyleSheet(
            f"QSpinBox{{background:{CP['bg3']};border:1px solid {CP['border']};"
            f"border-radius:6px;color:{CP['text_primary']};font-size:12px;font-weight:700;"
            f"padding:0 4px;}}"
            f"QSpinBox::up-button,QSpinBox::down-button{{width:16px;border:none;"
            f"background:{CP['bg4']};border-radius:3px;}}"
        )
        _gen_row.addWidget(self._spinbox_count)
        lay.addLayout(_gen_row)

        from core.config import get_image_price, load_config as _lc
        _cfg  = _lc()
        _price = get_image_price(_cfg)
        price_lbl = QLabel(
            f"Génération du character sheet  ·  {_price} / image"
            f"  ·  Voir le Manuel d'utilisation pour tous les tarifs"
        )
        price_lbl.setWordWrap(True)
        price_lbl.setStyleSheet(
            f"color:{CP['text_dim']};font-size:9px;"
            f"font-family:'Consolas',monospace;background:transparent;"
        )
        lay.addWidget(price_lbl)

        self._progress = QProgressBar()
        self._progress.setRange(0, 100)
        self._progress.setValue(0)
        self._progress.setFixedHeight(4)
        self._progress.setVisible(False)
        self._progress.setStyleSheet(
            f"QProgressBar{{background:{CP['bg3']};border:none;border-radius:2px;}}"
            f"QProgressBar::chunk{{background:qlineargradient(x1:0,y1:0,x2:1,y2:0,"
            f"stop:0 {CP['accent_dim']},stop:1 {CP['accent']});border-radius:2px;}}"
        )
        lay.addWidget(self._progress)

        self._status = QLabel("")
        self._status.setWordWrap(True)
        self._status.setStyleSheet(
            f"color:{CP['text_dim']};font-size:10px;font-family:'Consolas',monospace;background:transparent;"
        )
        lay.addWidget(self._status)

        lay.addStretch()

        scroll.setWidget(w)
        outer_lay.addWidget(scroll, 1)

        btn_bar = QWidget()
        btn_bar.setStyleSheet(f"background:{CP['bg1']};border-top:1px solid {CP['border']};")
        btn_row = QHBoxLayout(btn_bar)
        btn_row.setContentsMargins(28, 12, 24, 12)
        btn_row.setSpacing(10)

        btn_cancel = QPushButton("Annuler")
        btn_cancel.setFixedHeight(40)
        btn_cancel.setStyleSheet(
            f"QPushButton{{background:transparent;color:{CP['text_secondary']};"
            f"border:1px solid {CP['border']};border-radius:8px;font-size:12px;font-weight:700;padding:0 18px;}}"
            f"QPushButton:hover{{background:{CP['bg3']};color:{CP['text_primary']};}}"
        )
        btn_cancel.clicked.connect(self.reject)

        btn_save = QPushButton("✓  Sauvegarder le personnage")
        btn_save.setFixedHeight(40)
        btn_save.setStyleSheet(
            f"QPushButton{{background:{CP['accent2']};color:#ffffff;"
            f"border:none;border-radius:8px;font-size:12px;font-weight:700;padding:0 18px;}}"
            f"QPushButton:hover{{background:#9d8fff;}}"
            f"QPushButton:pressed{{background:{CP['accent2_dim']};}}"
        )
        btn_save.clicked.connect(self._on_save)

        btn_row.addWidget(btn_cancel)
        btn_row.addStretch()
        btn_row.addWidget(btn_save)
        outer_lay.addWidget(btn_bar)

        return outer

    # ── Panneau droit — portrait ──────────────────────────────────────────────

    _PREV_W = 274
    _PREV_H = 480

    def _build_preview(self) -> QWidget:
        w = QWidget()
        w.setFixedWidth(306)
        w.setStyleSheet(f"background:{CP['bg0']};")

        outer = QVBoxLayout(w)
        outer.setContentsMargins(16, 16, 16, 16)
        outer.setSpacing(0)

        # ── Portrait — cliquable pour plein écran ─────────────────────────────
        self._preview = QLabel()
        self._preview.setFixedSize(self._PREV_W, self._PREV_H)
        self._preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._preview_style_idle = (
            f"background:{CP['bg2']};border:1px solid {CP['border']};"
            f"border-radius:12px;color:{CP['text_dim']};font-size:13px;"
        )
        self._preview_style_hover = (
            f"background:{CP['bg2']};border:2px solid {CP['accent']};"
            f"border-radius:12px;color:{CP['text_dim']};font-size:13px;"
        )
        self._preview.setStyleSheet(self._preview_style_idle)
        self._preview.setText("Aucun portrait\ngénéré")
        self._preview.setWordWrap(True)
        self._preview.setCursor(Qt.CursorShape.PointingHandCursor)
        self._preview.mousePressEvent = lambda e: self._show_fullsize()
        self._preview.enterEvent = lambda e: self._preview.setStyleSheet(self._preview_style_hover)
        self._preview.leaveEvent = lambda e: self._preview.setStyleSheet(self._preview_style_idle)
        outer.addWidget(self._preview)
        outer.addSpacing(8)

        self._preview_name = QLabel(self._char.get("name", ""))
        self._preview_name.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._preview_name.setStyleSheet(
            f"color:{CP['text_primary']};font-size:13px;font-weight:700;"
            f"background:transparent;border:none;"
        )
        outer.addWidget(self._preview_name)

        self._preview_role = QLabel(self._char.get("role", ""))
        self._preview_role.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._preview_role.setStyleSheet(
            f"color:{CP['text_secondary']};font-size:11px;"
            f"background:transparent;border:none;"
        )
        outer.addWidget(self._preview_role)
        outer.addSpacing(6)

        _nav_ss = (
            f"QPushButton{{background:{CP['bg3']};color:{CP['text_secondary']};"
            f"border:1px solid {CP['border']};border-radius:5px;font-size:13px;font-weight:700;}}"
            f"QPushButton:hover{{color:{CP['text_primary']};border-color:{CP['border_bright']};}}"
        )
        nav_row = QHBoxLayout()
        nav_row.setSpacing(6)
        self._btn_prev = QPushButton("‹")
        self._btn_prev.setFixedSize(26, 22)
        self._btn_prev.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_prev.setStyleSheet(_nav_ss)
        self._btn_prev.clicked.connect(lambda: self._navigate_preview(-1))
        self._preview_counter = QLabel("")
        self._preview_counter.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._preview_counter.setStyleSheet(
            f"color:{CP['text_dim']};font-size:10px;background:transparent;border:none;"
        )
        self._btn_next = QPushButton("›")
        self._btn_next.setFixedSize(26, 22)
        self._btn_next.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_next.setStyleSheet(_nav_ss)
        self._btn_next.clicked.connect(lambda: self._navigate_preview(1))
        nav_row.addStretch()
        nav_row.addWidget(self._btn_prev)
        nav_row.addWidget(self._preview_counter)
        nav_row.addWidget(self._btn_next)
        nav_row.addStretch()
        outer.addLayout(nav_row)

        outer.addStretch()

        # ── Actions en bas ────────────────────────────────────────────────────
        _s_neutral = (
            f"QPushButton{{background:transparent;color:{CP['text_dim']};"
            f"border:1px solid {CP['border']};border-radius:6px;"
            f"font-size:10px;font-weight:700;padding:0 10px;}}"
            f"QPushButton:hover{{background:{CP['bg2']};color:{CP['text_secondary']};"
            f"border-color:{CP['border_bright']};}}"
            f"QPushButton:disabled{{opacity:0.30;}}"
        )

        # Bouton variation
        self._btn_gen_from = QPushButton("🎨  Générer une variation")
        self._btn_gen_from.setFixedHeight(32)
        self._btn_gen_from.setEnabled(False)
        self._btn_gen_from.setToolTip("Générer de nouvelles images à partir de celle-ci")
        self._btn_gen_from.setStyleSheet(_s_neutral)
        self._btn_gen_from.clicked.connect(self._on_variation_click)
        outer.addWidget(self._btn_gen_from)

        # Bouton NB2 Edit — portrait depuis photo de référence
        self._btn_nb2edit = QPushButton("🖼  Générer depuis photo")
        self._btn_nb2edit.setFixedHeight(32)
        self._btn_nb2edit.setEnabled(bool(self._image_path and os.path.isfile(self._image_path)))
        self._btn_nb2edit.setToolTip(
            "Génère un portrait stylisé à partir de la photo importée\n"
            "via NB2 Edit (fal-ai/nano-banana-2/edit)  ·  $0.08"
        )
        self._btn_nb2edit.setStyleSheet(_s_neutral)
        self._btn_nb2edit.clicked.connect(self._on_nb2edit)
        outer.addWidget(self._btn_nb2edit)

        outer.addSpacing(4)

        # Ligne 3 : Importer une image (import direct, sans génération)
        self._btn_import_photo = QPushButton("📁  Importer une image")
        self._btn_import_photo.setFixedHeight(32)
        self._btn_import_photo.setStyleSheet(_s_neutral)
        self._btn_import_photo.setToolTip(
            "Utiliser directement une photo comme portrait du personnage,\n"
            "sans passer par la génération Nano Banana."
        )
        self._btn_import_photo.clicked.connect(self._import_photo_as_character)
        outer.addWidget(self._btn_import_photo)

        if self._image_path and os.path.isfile(self._image_path):
            self._load_preview(self._image_path)
        elif self._sheet_path and os.path.isfile(self._sheet_path):
            self._load_preview(self._sheet_path)

        self._refresh_preview_nav()
        return w

    def _set_nav(self, idx: int):
        pass

    def _update_nav_label(self, idx: int, text: str):
        pass

    def _build_gallery_tab(self) -> QWidget:
        w = QWidget()
        w.setStyleSheet(f"background:{CP['bg0']};")
        lay = QVBoxLayout(w)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(4)

        from core.config import load_config
        cfg = load_config()
        if not cfg.get("api_key", "").strip():
            mock_lbl = QLabel("⚠ Mode mock actif\n(clé fal.ai non configurée)")
            mock_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            mock_lbl.setWordWrap(True)
            mock_lbl.setStyleSheet(
                f"color:{CP['orange']};font-size:10px;font-family:'Consolas',monospace;"
                f"background:rgba(255,140,66,0.08);border:1px solid rgba(255,140,66,0.25);"
                f"border-radius:6px;padding:8px;"
            )
            lay.addWidget(mock_lbl)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea{background:transparent;border:none;}")

        self._gallery_container = QWidget()
        self._gallery_container.setStyleSheet("background:transparent;")
        self._gallery_grid = QGridLayout(self._gallery_container)
        self._gallery_grid.setSpacing(8)
        self._gallery_grid.setContentsMargins(0, 0, 0, 0)
        self._gallery_grid.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)

        scroll.setWidget(self._gallery_container)
        lay.addWidget(scroll)

        self._refresh_gallery_tab(update_tab_title=False)
        return w

    def _build_accessories_tab(self) -> QWidget:
        w = QWidget()
        w.setStyleSheet(f"background:{CP['bg0']};")
        lay = QVBoxLayout(w)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea{background:transparent;border:none;}")

        self._acc_container = QWidget()
        self._acc_container.setStyleSheet("background:transparent;")
        self._acc_inner = QVBoxLayout(self._acc_container)
        self._acc_inner.setContentsMargins(0, 0, 0, 0)
        self._acc_inner.setSpacing(6)

        scroll.setWidget(self._acc_container)
        lay.addWidget(scroll)
        self._refresh_acc_tab(update_title=False)
        return w

    def _build_hmc_tab(self) -> QWidget:
        w = QWidget()
        w.setStyleSheet(f"background:{CP['bg0']};")
        lay = QVBoxLayout(w)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea{background:transparent;border:none;}")

        self._hmc_container = QWidget()
        self._hmc_container.setStyleSheet("background:transparent;")
        self._hmc_inner = QVBoxLayout(self._hmc_container)
        self._hmc_inner.setContentsMargins(0, 0, 0, 0)
        self._hmc_inner.setSpacing(6)

        scroll.setWidget(self._hmc_container)
        lay.addWidget(scroll)
        self._refresh_hmc_tab(update_title=False)
        return w

    # ── Gestion des références visuelles ─────────────────────────────────────

    def _refresh_refs_display(self):
        while self._refs_layout.count():
            item = self._refs_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        for path in self._ref_paths:
            self._refs_layout.addWidget(self._make_thumbnail(path))

        btn_add = QPushButton("+")
        btn_add.setFixedSize(60, 60)
        btn_add.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_add.setToolTip("Ajouter des images de référence\nClaude les analysera pour enrichir le prompt.")
        btn_add.setStyleSheet(f"""
            QPushButton{{
                background:transparent;color:{CP['text_dim']};
                border:1px dashed {CP['border_bright']};border-radius:8px;
                font-size:24px;font-weight:300;padding:0;
            }}
            QPushButton:hover{{
                color:{CP['accent']};border-color:{CP['accent']};
                background:rgba(78,205,196,0.08);
            }}
            QPushButton:pressed{{background:rgba(78,205,196,0.16);}}
        """)
        btn_add.clicked.connect(self._on_add_refs)
        self._refs_layout.addWidget(btn_add)
        self._refs_layout.addStretch()

    def _make_thumbnail(self, path: str) -> QWidget:
        container = QWidget()
        container.setFixedSize(68, 60)

        lbl = QLabel(container)
        lbl.setGeometry(0, 0, 60, 60)
        lbl.setStyleSheet("border-radius:6px;")
        pix = QPixmap(path)
        if not pix.isNull():
            pix = pix.scaled(
                60, 60,
                Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                Qt.TransformationMode.SmoothTransformation,
            )
            pix = pix.copy(
                (pix.width() - 60) // 2,
                (pix.height() - 60) // 2,
                60, 60,
            )
            lbl.setPixmap(pix)
        else:
            lbl.setStyleSheet(
                f"background:{CP['bg3']};border-radius:6px;"
                f"color:{CP['text_dim']};font-size:10px;"
            )
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lbl.setText("?")

        btn_rm = QPushButton("×", container)
        btn_rm.setGeometry(48, 0, 20, 20)
        btn_rm.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_rm.setToolTip("Retirer cette référence")
        btn_rm.setStyleSheet(
            "QPushButton{background:#992222;color:#fff;border:none;"
            "border-radius:10px;font-size:12px;font-weight:700;padding:0;}"
            "QPushButton:hover{background:#cc3333;}"
        )
        btn_rm.clicked.connect(lambda checked=False, p=path: self._remove_ref(p))

        return container

    def _remove_ref(self, path: str):
        if path in self._ref_paths:
            self._ref_paths.remove(path)
            self._refresh_refs_display()
            n = len(self._ref_paths)
            self._status.setText(
                f"Référence retirée — {n} référence(s) restante(s)." if n
                else "Toutes les références ont été retirées."
            )

    # ── Actions ───────────────────────────────────────────────────────────────

    def _on_gen_mode_changed(self, idx: int = 0):
        _hints = {
            "sheet_5views": "Nano Banana génère un turnaround 5 vues en une seule image (front, dos, 3/4, profil, buste).",
            "classic":      "Portrait unique — cadrage libre, corps entier ou buste selon le prompt.",
            "editorial":    "Buste serré, éclairage Rembrandt dramatique — idéal pour les fiches de casting.",
            "action":       "Personnage en pose d'action dynamique, format vertical.",
            "duo":          "Deux personnages côte à côte — décris les deux dans le prompt.",
            "photo_ref":    "⚠ Nécessite une photo de référence (section « Références visuelles »). "
                            "Pipeline flux-pulid : buste fidèle à la photo, puis 4 vues corps entier. "
                            "Méthode encore en amélioration — fidélité variable sur les vues corps entier.",
        }
        key = self._gen_mode_combo.currentData() if hasattr(self, "_gen_mode_combo") else ""
        self._gen_mode_hint.setText(_hints.get(key, ""))
        # Signale si le mode photo_ref est sélectionné sans référence
        if key == "photo_ref" and hasattr(self, "_status"):
            valid_refs = [p for p in self._ref_paths if p and os.path.isfile(p)]
            if not valid_refs:
                self._status.setText("ℹ Mode photo de référence sélectionné — ajoute une photo ci-dessus.")

    def _on_optimize(self):
        text = self._prompt.toPlainText().strip()
        valid_refs = [p for p in self._ref_paths if p and os.path.isfile(p)]

        if not text and not valid_refs:
            self._status.setText("Écris une description ou ajoute une photo de référence.")
            return

        self._btn_cloud.setEnabled(False)

        import core.style as _style_mod
        _portrait_key = self._portrait_style_combo.currentData() if hasattr(self, "_portrait_style_combo") else ""
        if _portrait_key:
            _ps = next((s for s in _style_mod.STYLES if s["key"] == _portrait_key), None)
            _style_suffix = _ps["image_suffix"] if _ps else _style_mod.get_image_suffix()
        else:
            _style_suffix = _style_mod.get_image_suffix()

        ref_usage = self._ref_usage_combo.currentData() if hasattr(self, "_ref_usage_combo") else "face"
        if valid_refs and ref_usage == "style":
            self._status.setText("Analyse du style de référence en cours…")
            self._worker_opt = OptimizeStyleReferenceWorker(text, valid_refs)
        elif valid_refs:
            self._status.setText("Analyse du visage en cours…")
            self._worker_opt = OptimizeCharacterWithReferencesWorker(text, valid_refs, style_suffix=_style_suffix)
        else:
            self._status.setText("Optimisation en cours…")
            self._worker_opt = OptimizePromptWorker(text, style_suffix=_style_suffix)

        self._worker_opt.finished.connect(self._on_optimize_done)
        self._worker_opt.failed.connect(self._on_optimize_fail)
        self._worker_opt.start()

    def _on_optimize_done(self, prompt: str):
        self._prompt.setPlainText(prompt)
        self._btn_cloud.setEnabled(True)
        self._status.setText("Prompt optimisé ✓")

    def _on_optimize_fail(self, err: str):
        self._btn_cloud.setEnabled(True)
        self._status.setText(f"Erreur : {err[:80]}")

    def _on_ref_usage_changed(self):
        usage = self._ref_usage_combo.currentData() if hasattr(self, "_ref_usage_combo") else "inspiration"
        is_style = usage == "style"
        if hasattr(self, "_portrait_style_combo"):
            combo = self._portrait_style_combo
            if is_style:
                if not hasattr(self, "_saved_style_idx"):
                    self._saved_style_idx = combo.currentIndex()
                if combo.itemData(0) != "__style_ref__":
                    combo.insertItem(0, "🎨  Style extrait de la référence", "__style_ref__")
                combo.setCurrentIndex(0)
                combo.setEnabled(False)
                combo.setToolTip("Désactivé — le style est extrait de l'image de référence")
            else:
                combo.setEnabled(True)
                combo.setToolTip("")
                if combo.itemData(0) == "__style_ref__":
                    combo.removeItem(0)
                if hasattr(self, "_saved_style_idx"):
                    saved_i = self._saved_style_idx
                    if 0 <= saved_i < combo.count():
                        combo.setCurrentIndex(saved_i)
                    del self._saved_style_idx
        if hasattr(self, "_gen_mode_combo"):
            if is_style:
                if not hasattr(self, "_saved_gen_mode_idx"):
                    self._saved_gen_mode_idx = self._gen_mode_combo.currentIndex()
                for i in range(self._gen_mode_combo.count()):
                    if self._gen_mode_combo.itemData(i) == "classic":
                        self._gen_mode_combo.setCurrentIndex(i)
                        break
            else:
                if hasattr(self, "_saved_gen_mode_idx"):
                    saved = self._saved_gen_mode_idx
                    if 0 <= saved < self._gen_mode_combo.count():
                        self._gen_mode_combo.setCurrentIndex(saved)
                    del self._saved_gen_mode_idx

        if hasattr(self, "_refs_hint_lbl"):
            hints = {
                "inspiration": "Utilisées par Claude pour enrichir le prompt",
                "style":       "1re image → style visuel extrait par IA",
                "face":        "1re image → visage de référence pour le portrait",
            }
            self._refs_hint_lbl.setText(hints.get(usage, ""))

    def _on_add_refs(self):
        paths, _ = QFileDialog.getOpenFileNames(
            self, "Sélectionner des images de référence", "",
            "Images (*.png *.jpg *.jpeg *.webp *.bmp)"
        )
        if not paths:
            return

        added = 0
        for p in paths:
            if p not in self._ref_paths:
                self._ref_paths.append(p)
                added += 1
        self._refresh_refs_display()

        usage = self._ref_usage_combo.currentData() if hasattr(self, "_ref_usage_combo") else "inspiration"
        if usage != "inspiration":
            _hints = {
                "style": "Style pictural — analysé à la génération ✓",
                "face":  "Référence de visage — appliquée à la génération ✓",
            }
            self._status.setText(_hints.get(usage, f"{len(self._ref_paths)} référence(s) ajoutée(s)."))
            return

        n = len(self._ref_paths)
        self._status.setText(
            f"{n} référence(s) ajoutée(s). Cliquez ☁ pour optimiser via Claude."
        )

    def _on_refs_done(self, prompt: str):
        self._prompt.setPlainText(prompt)
        self._btn_cloud.setEnabled(True)
        self._status.setText("Prompt enrichi avec les références ✓")

    def _on_refs_fail(self, err: str):
        self._btn_cloud.setEnabled(True)
        self._status.setText(f"Erreur Claude : {err[:80]}")

    def _on_generate(self):
        self._start_generation()

    def _start_generation(self, hmc_ids: set | None = None):
        prompt = self._prompt.toPlainText().strip()
        if not prompt:
            self._status.setText("Remplis le prompt d'abord.")
            return

        self._btn_gen.setEnabled(False)
        self._progress.setVisible(True)
        self._progress.setValue(0)

        import core.style as style_api
        import core.hmc as hmc_api
        _ref_usage   = self._ref_usage_combo.currentData() if hasattr(self, "_ref_usage_combo") else "inspiration"
        _valid_refs  = [p for p in self._ref_paths if p and os.path.isfile(p)]
        _style_ref   = _valid_refs[0] if _valid_refs else ""
        if _ref_usage == "style":
            suffix = ""
        else:
            portrait_key = self._portrait_style_combo.currentData() if hasattr(self, "_portrait_style_combo") else ""
            if portrait_key:
                _ps = next((s for s in style_api.STYLES if s["key"] == portrait_key), None)
                suffix = _ps["image_suffix"] if _ps else style_api.get_image_suffix()
            else:
                suffix = style_api.get_image_suffix()
        full_prompt = f"{prompt}, {suffix}" if suffix else prompt
        _cs = self._creative.get_prompt_suffix()
        if _cs:
            full_prompt = f"{full_prompt}, {_cs}"

        ids_to_use = hmc_ids if hmc_ids is not None else set()
        hmc_parts = []
        for hid in ids_to_use:
            item = hmc_api.get_hmc_item(hid)
            if item:
                hmc_type = item.get("hmc_type", "Look")
                desc = item.get("prompt") or item.get("description") or item.get("name", "")
                if desc:
                    hmc_parts.append(f"{hmc_type}: {desc}")
        if hmc_parts:
            full_prompt = f"{full_prompt}. {'. '.join(hmc_parts)}"

        name     = self._name.text().strip() or "character"
        gen_mode = self._gen_mode_combo.currentData() if hasattr(self, "_gen_mode_combo") else "sheet_5views"
        ref_paths = _valid_refs

        _model_key  = self._model_combo.currentData() if hasattr(self, "_model_combo") else None
        _num_images = self._spinbox_count.value() if hasattr(self, "_spinbox_count") else 1
        if _ref_usage == "face":
            if not ref_paths:
                self._status.setText("⚠ Ajoute au moins une image de référence pour ce mode.")
                self._btn_gen.setEnabled(True)
                self._progress.setVisible(False)
                return
            self._worker_gen = GeneratePortraitWithFaceIDWorker(ref_paths[0], full_prompt, name)
        elif gen_mode == "photo_ref":
            if not ref_paths:
                self._status.setText("⚠ Ajoute au moins une photo de référence pour ce mode.")
                self._btn_gen.setEnabled(True)
                self._progress.setVisible(False)
                return
            self._worker_gen = GeneratePortraitWithFaceIDWorker(ref_paths[0], full_prompt, name)
        else:
            self._worker_gen = GeneratePortraitWorker(
                full_prompt, name, gen_mode=gen_mode,
                model_key=_model_key, num_images=_num_images,
                ref_usage=_ref_usage, style_ref_path=_style_ref,
            )
        self._worker_gen.progress.connect(self._on_gen_progress)
        self._worker_gen.finished.connect(self._on_gen_done)
        if hasattr(self._worker_gen, "multi_finished"):
            self._worker_gen.multi_finished.connect(self._on_multi_gen_done)
        self._worker_gen.failed.connect(self._on_gen_fail)
        self._worker_gen.start()

    def _on_variation_click(self):
        choice_dlg = _VariationChoiceDialog(self)
        if not choice_dlg.exec():
            return
        if choice_dlg.choice() == _VariationChoiceDialog.REGENERATE:
            self._start_generation()
        elif choice_dlg.choice() == _VariationChoiceDialog.WITH_HMC:
            hmc_dlg = _HMCSelectorDialog(self, char_id=self._char.get("id", ""))
            if not hmc_dlg.exec():
                return
            self._start_generation(hmc_ids=hmc_dlg.selected_ids())

    def _on_gen_progress(self, pct: int, msg: str):
        self._progress.setValue(pct)
        self._status.setText(msg)

    def _on_gen_done(self, portrait_path: str, sheet_path: str):
        self._btn_gen.setEnabled(True)
        if hasattr(self, "_btn_search_photo"):
            self._btn_search_photo.setEnabled(True)
        self._progress.setVisible(False)

        if not portrait_path and not sheet_path:
            self._status.setText("Mode mock : aucune image générée (clé fal.ai absente)")
            return

        from ui.dialog_portrait_result import GenerationResultDialog
        dlg = GenerationResultDialog(self, portrait_path, sheet_path, "Portrait généré")
        dlg.retry_requested.connect(self._on_generate)
        dlg.exec()

        if dlg.was_used():
            if sheet_path and os.path.isfile(sheet_path):
                self._sheet_path = sheet_path
                self._image_path = sheet_path  # toujours mettre à jour vers la nouvelle image
            if portrait_path and os.path.isfile(portrait_path):
                self._image_path = portrait_path  # portrait prime sur sheet si disponible
            self._generated_images.append({"portrait": portrait_path, "sheet": sheet_path})
            self._preview_idx = len(self._generated_images) - 1
            self._refresh_gallery_tab()
            preview = sheet_path if (sheet_path and os.path.isfile(sheet_path)) else portrait_path
            if preview and os.path.isfile(preview):
                self._load_preview(preview)
            self._refresh_preview_nav()
            self._status.setText("Portrait ajouté ✓")
            self._set_nav(0)
        else:
            self._status.setText("Image non utilisée — clique Générer pour réessayer.")

    def _on_multi_gen_done(self, paths: list):
        self._btn_gen.setEnabled(True)
        if hasattr(self, "_btn_search_photo"):
            self._btn_search_photo.setEnabled(True)
        self._progress.setVisible(False)
        valid = [p for p in paths if p and os.path.isfile(p)]
        if not valid:
            self._status.setText("Mode mock : aucune image générée (clé fal.ai absente)")
            return
        first_new = len(self._generated_images)
        for p in valid:
            self._generated_images.append({"portrait": "", "sheet": p})
        self._preview_idx = first_new
        self._sheet_path  = valid[0]
        self._image_path  = valid[0]
        self._refresh_gallery_tab()
        self._load_preview(valid[0])
        self._refresh_preview_nav()
        self._set_nav(0)
        n = len(valid)
        self._status.setText(
            f"{n} portrait{'s' if n > 1 else ''} importé{'s' if n > 1 else ''} — "
            f"supprime les non désirés dans la galerie →"
        )

    def _on_gen_fail(self, err: str):
        self._btn_gen.setEnabled(True)
        if hasattr(self, "_btn_search_photo"):
            self._btn_search_photo.setEnabled(True)
        self._progress.setVisible(False)
        self._status.setText(f"Erreur : {err[:100]}")

    def _load_preview(self, path: str):
        QPixmapCache.remove(path)   # bust cache — file may have been overwritten
        pix = QPixmap(path)
        if not pix.isNull():
            # Letterbox : image complète visible sans rognage.
            # Le QLabel (AlignCenter) centre automatiquement dans l'espace restant.
            pix = pix.scaled(
                self._PREV_W, self._PREV_H,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            self._preview.setPixmap(pix)
            self._preview.setText("")

    def _refresh_preview_nav(self):
        has_image = bool(
            (self._image_path and os.path.isfile(self._image_path)) or
            (self._sheet_path and os.path.isfile(self._sheet_path))
        )
        if hasattr(self, "_btn_gen_from"):
            self._btn_gen_from.setEnabled(has_image)
        n = len(self._generated_images)
        has_multi = n > 1
        if hasattr(self, "_btn_prev"):
            self._btn_prev.setVisible(has_multi)
            self._btn_next.setVisible(has_multi)
            idx = max(0, min(self._preview_idx, n - 1)) if n else 0
            self._preview_counter.setText(f"{idx + 1} / {n}" if n else "")

    def _navigate_preview(self, delta: int):
        n = len(self._generated_images)
        if n == 0:
            return
        self._preview_idx = (self._preview_idx + delta) % n
        entry = self._generated_images[self._preview_idx]
        p = entry.get("portrait", "")
        s = entry.get("sheet", "")
        display = s if (s and os.path.isfile(s)) else p if (p and os.path.isfile(p)) else ""
        if display:
            self._load_preview(display)
        self._refresh_preview_nav()

    def _use_current_preview(self):
        n = len(self._generated_images)
        if n == 0:
            return
        idx = max(0, min(self._preview_idx, n - 1))
        entry = self._generated_images[idx]
        p = entry.get("portrait", "")
        s = entry.get("sheet", "")
        if p and os.path.isfile(p):
            self._image_path = p
        if s and os.path.isfile(s):
            self._sheet_path = s
        preview = s if (s and os.path.isfile(s)) else p
        if preview and os.path.isfile(preview):
            self._load_preview(preview)
        self._refresh_preview_nav()
        self._refresh_gallery_tab()
        self._status.setText("Image active ✓")

    def _search_photo_for_cheat(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Choisir une photo", "",
            "Images (*.png *.jpg *.jpeg *.webp *.bmp)"
        )
        if not path or not os.path.isfile(path):
            return
        self._start_generation_from_photo(path)

    def _start_generation_from_photo(self, photo_path: str):
        self._btn_gen.setEnabled(False)
        self._btn_search_photo.setEnabled(False)
        self._progress.setVisible(True)
        self._progress.setValue(0)
        self._status.setText("Préparation de la photo…")

        prompt = self._prompt.toPlainText().strip()
        name   = self._name.text().strip() or "character"

        self._worker_gen = GeneratePortraitWithFaceIDWorker(photo_path, prompt, name)
        self._worker_gen.progress.connect(self._on_gen_progress)
        self._worker_gen.finished.connect(self._on_gen_done)
        self._worker_gen.failed.connect(self._on_gen_fail)
        self._worker_gen.start()

    def _import_photo_as_character(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Importer une photo comme personnage", "",
            "Images (*.png *.jpg *.jpeg *.webp *.bmp)"
        )
        if not path or not os.path.isfile(path):
            return
        self._image_path = path
        self._sheet_path = ""
        for entry in self._generated_images:
            if entry.get("portrait") == path:
                break
        else:
            self._generated_images.append({"portrait": path, "sheet": ""})
        self._preview_idx = len(self._generated_images) - 1
        self._load_preview(path)
        self._refresh_preview_nav()
        self._refresh_gallery_tab()
        self._status.setText("Photo importée comme personnage ✓")
        # Active les boutons qui dépendent d'une image existante
        if hasattr(self, "_btn_remove_bg"):
            self._btn_remove_bg.setEnabled(True)
        if hasattr(self, "_btn_nb2edit"):
            self._btn_nb2edit.setEnabled(True)

    # ── BiRefNet — suppression de fond ───────────────────────────────────────

    def _on_remove_bg(self):
        path = self._image_path
        if not path or not os.path.isfile(path):
            QMessageBox.warning(self, "Pas d'image", "Importe d'abord une image.")
            return
        self._trigger_remove_bg_on(path)

    def _trigger_remove_bg_on(self, path: str):
        if not path or not os.path.isfile(path):
            QMessageBox.warning(self, "Pas d'image", "Image introuvable.")
            return
        if hasattr(self, "_biref_worker") and self._biref_worker and self._biref_worker.isRunning():
            return
        from api.tts import RemoveBackgroundWorker
        out_dir = os.path.dirname(path)
        self._biref_worker = RemoveBackgroundWorker(path, out_dir)
        self._biref_worker.progress.connect(lambda pct, msg: self._status.setText(msg))
        self._biref_worker.finished.connect(self._on_bg_removed)
        self._biref_worker.failed.connect(lambda e: QMessageBox.critical(self, "Erreur BiRefNet", e))
        self._biref_worker.start()
        self._status.setText("Suppression du fond en cours…")
        if hasattr(self, "_btn_remove_bg"):
            self._btn_remove_bg.setEnabled(False)

    def _on_bg_removed(self, path: str):
        if hasattr(self, "_btn_remove_bg"):
            self._btn_remove_bg.setEnabled(True)
        if not path or not os.path.isfile(path):
            self._status.setText("Fond supprimé (mode mock)")
            return
        self._image_path = path
        self._generated_images.append({"portrait": path, "sheet": ""})
        self._preview_idx = len(self._generated_images) - 1
        self._load_preview(path)
        self._refresh_preview_nav()
        self._refresh_gallery_tab()
        self._status.setText(f"Fond supprimé ✓  →  {os.path.basename(path)}")

    # ── NB2 Edit — portrait depuis photo de référence ─────────────────────────

    def _on_nb2edit(self):
        path = self._image_path
        if not path or not os.path.isfile(path):
            QMessageBox.warning(self, "Pas d'image", "Importe d'abord une photo de référence.")
            return
        if hasattr(self, "_nb2edit_worker") and self._nb2edit_worker and self._nb2edit_worker.isRunning():
            return
        name   = self._char.get("name", "") or "personnage"
        prompt = self._char.get("prompt", "") or self._char.get("description", "") or name
        self._nb2edit_worker = GeneratePortraitNB2EditWorker([path], prompt, name)
        self._nb2edit_worker.progress.connect(self._on_nb2edit_progress)
        self._nb2edit_worker.finished.connect(self._on_nb2edit_done)
        self._nb2edit_worker.failed.connect(self._on_nb2edit_failed)
        self._nb2edit_worker.start()
        self._progress.setVisible(True)
        self._progress.setValue(0)
        if hasattr(self, "_btn_nb2edit"):
            self._btn_nb2edit.setEnabled(False)

    def _on_nb2edit_progress(self, pct: int, msg: str):
        self._progress.setValue(pct)
        self._status.setText(msg)

    def _on_nb2edit_done(self, path: str):
        self._progress.setVisible(False)
        if hasattr(self, "_btn_nb2edit"):
            self._btn_nb2edit.setEnabled(True)
        if not path or not os.path.isfile(path):
            self._status.setText("NB2 Edit (mode mock — aucune clé fal.ai)")
            return
        self._image_path = path
        self._generated_images.append({"portrait": path, "sheet": ""})
        self._preview_idx = len(self._generated_images) - 1
        self._load_preview(path)
        self._refresh_preview_nav()
        self._refresh_gallery_tab()
        self._status.setText(f"Portrait NB2 Edit généré ✓  →  {os.path.basename(path)}")

    def _on_nb2edit_failed(self, err: str):
        self._progress.setVisible(False)
        if hasattr(self, "_btn_nb2edit"):
            self._btn_nb2edit.setEnabled(True)
        self._status.setText(f"✗  {err[:100]}")
        QMessageBox.critical(self, "Erreur NB2 Edit", err)

    def _show_fullsize(self):
        fallback = self._sheet_path or self._image_path
        # Derive the real active index from _image_path/_sheet_path, not _preview_idx,
        # because _preview_idx is a navigation cursor and may lag behind _image_path.
        _active_idx = self._preview_idx
        for _i, _e in enumerate(self._generated_images):
            _p, _s = _e.get("portrait", ""), _e.get("sheet", "")
            if (self._image_path and (_p == self._image_path or _s == self._image_path)) or \
               (self._sheet_path and (_s == self._sheet_path or _p == self._sheet_path)):
                _active_idx = _i
                break
        start = max(0, min(_active_idx, len(self._generated_images) - 1)) \
            if self._generated_images else 0

        _dlg_ref: list = []

        def _remove_bg_from_fullscreen():
            d = _dlg_ref[0] if _dlg_ref else None
            if d and 0 <= d._idx < len(d._data):
                _path = d._data[d._idx][2]
                d.accept()
                self._trigger_remove_bg_on(_path)

        def _variation_from_fullscreen():
            d = _dlg_ref[0] if _dlg_ref else None
            if d:
                d.accept()
            self._on_variation_click()

        dlg = _FullscreenDialog(
            self, self._generated_images, start,
            active_idx=_active_idx, fallback_path=fallback,
            extra_buttons=[
                ("🎨  Générer une variation", _variation_from_fullscreen),
                ("✂  Supprimer le fond",     _remove_bg_from_fullscreen),
            ],
        )
        _dlg_ref.append(dlg)
        dlg.exec()

        _changed = bool(dlg.deleted_indices())

        for orig_i in sorted(dlg.deleted_indices(), reverse=True):
            if 0 <= orig_i < len(self._generated_images):
                entry = self._generated_images[orig_i]
                p = entry.get("portrait", "")
                s = entry.get("sheet", "")
                if (p and p == self._image_path) or (s and s == self._sheet_path):
                    self._image_path = ""
                    self._sheet_path = ""
                    self._preview.clear()
                    self._preview.setText("Aucun portrait\ngénéré")
                self._generated_images.pop(orig_i)

        self._preview_idx = min(self._preview_idx, max(0, len(self._generated_images) - 1))

        entry, orig_i = dlg.chosen_entry()
        if entry is not None:
            _changed = True
            p = entry.get("portrait", "")
            s = entry.get("sheet", "")
            if p and os.path.isfile(p):
                self._image_path = p
            if s and os.path.isfile(s):
                self._sheet_path = s
                if not self._image_path:
                    self._image_path = s
            for new_i, e in enumerate(self._generated_images):
                if e is entry:
                    self._preview_idx = new_i
                    break
            preview = s if (s and os.path.isfile(s)) else p
            if preview and os.path.isfile(preview):
                self._load_preview(preview)
            self._status.setText(f"Version {orig_i + 1} sélectionnée ✓")

        # Si l'image active a été supprimée et qu'aucune n'a été choisie,
        # auto-sélectionner la première image restante
        if not self._image_path and self._generated_images:
            _changed = True
            ne = self._generated_images[self._preview_idx]
            _np = ne.get("portrait", "")
            _ns = ne.get("sheet", "")
            if _np and os.path.isfile(_np):
                self._image_path = _np
            if _ns and os.path.isfile(_ns):
                self._sheet_path = _ns
                if not self._image_path:
                    self._image_path = _ns
            _prev = _ns if (_ns and os.path.isfile(_ns)) else _np
            if _prev and os.path.isfile(_prev):
                self._load_preview(_prev)

        self._refresh_gallery_tab()
        self._refresh_preview_nav()

        if _changed and self._char.get("id"):
            _auto = dict(self._char)
            _auto.update({
                "image_path":       self._image_path,
                "sheet_path":       self._sheet_path,
                "generated_images": self._generated_images,
            })
            self._char = casting_api.save_character(_auto)

    def _refresh_gallery_tab(self, update_tab_title: bool = True):
        if not hasattr(self, "_gallery_grid"):
            return
        if update_tab_title:
            self._update_nav_label(0, f"Images ({len(self._generated_images)})")

        while self._gallery_grid.count():
            item = self._gallery_grid.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        COLS = 2
        total = len(self._generated_images)
        for i, entry in enumerate(self._generated_images):
            card = self._make_gallery_card(entry, i, total=total)
            self._gallery_grid.addWidget(card, i // COLS, i % COLS)

        if not self._generated_images:
            empty = QLabel("Aucune image générée.\nClique sur « Générer le portrait ».")
            empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
            empty.setWordWrap(True)
            empty.setStyleSheet(
                f"color:{CP['text_dim']};font-size:10px;background:transparent;padding:24px;"
            )
            self._gallery_grid.addWidget(empty, 0, 0, 1, COLS)

    def _make_gallery_card(self, entry: dict, idx: int, total: int = 1) -> QWidget:
        portrait = entry.get("portrait", "")
        sheet    = entry.get("sheet", "")
        is_active = (
            (portrait and portrait == self._image_path) or
            (sheet    and sheet    == self._sheet_path)
        )

        card = QWidget()
        card.setFixedSize(130, 170)
        border = CP["accent"] if is_active else CP["border"]
        card.setStyleSheet(
            f"QWidget{{background:{CP['bg2']};border:2px solid {border};border-radius:8px;}}"
        )

        cly = QVBoxLayout(card)
        cly.setContentsMargins(5, 5, 5, 5)
        cly.setSpacing(4)

        thumb = QLabel()
        thumb.setFixedSize(118, 108)
        thumb.setAlignment(Qt.AlignmentFlag.AlignCenter)
        thumb.setStyleSheet(
            f"background:{CP['bg3']};border-radius:5px;border:none;"
        )
        display = sheet if (sheet and os.path.isfile(sheet)) else portrait
        if display and os.path.isfile(display):
            pix = QPixmap(display).scaled(
                118, 108,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            thumb.setPixmap(pix)
        else:
            thumb.setText("?")
            thumb.setStyleSheet(
                f"color:{CP['text_dim']};background:{CP['bg3']};border-radius:5px;"
                f"border:none;font-size:18px;"
            )
        cly.addWidget(thumb)

        if is_active:
            badge = QLabel("ACTIF")
            badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
            badge.setFixedHeight(14)
            badge.setStyleSheet(
                f"color:#07080f;background:{CP['accent']};border-radius:3px;"
                f"font-size:8px;font-weight:700;border:none;"
            )
            cly.addWidget(badge)

        if is_active:
            btn_use = QPushButton("✕ Ne pas utiliser")
            btn_use.setFixedHeight(28)
            btn_use.setStyleSheet(
                f"QPushButton{{background:transparent;color:{CP['orange']};"
                f"border:1px solid rgba(255,140,66,0.4);border-radius:4px;"
                f"font-size:9px;font-weight:700;padding:0;}}"
                f"QPushButton:hover{{background:rgba(255,140,66,0.15);"
                f"color:{CP['orange']};border-color:{CP['orange']};}}"
                f"QPushButton:disabled{{opacity:0.30;}}"
            )
            btn_use.clicked.connect(self._gallery_unuse)
        else:
            btn_use = QPushButton("✓ Utiliser")
            btn_use.setFixedHeight(28)
            btn_use.setStyleSheet(
                f"QPushButton{{background:transparent;color:{CP['accent']};"
                f"border:1px solid {CP['accent_dim']};border-radius:4px;"
                f"font-size:9px;font-weight:700;padding:0;}}"
                f"QPushButton:hover{{background:{CP['accent']};color:#07080f;}}"
                f"QPushButton:disabled{{opacity:0.30;}}"
            )
            btn_use.clicked.connect(lambda checked=False, e=entry: self._gallery_use(e))
        cly.addWidget(btn_use)

        btn_del = QPushButton("Supprimer")
        btn_del.setFixedHeight(22)
        btn_del.setStyleSheet(
            f"QPushButton{{background:transparent;color:{CP['text_dim']};"
            f"border:1px solid {CP['border']};border-radius:4px;"
            f"font-size:8px;font-weight:700;padding:0;}}"
            f"QPushButton:hover{{background:rgba(255,79,106,0.12);"
            f"color:{CP['red']};border-color:{CP['red']};}}"
            f"QPushButton:disabled{{opacity:0.30;}}"
        )
        btn_del.clicked.connect(lambda checked=False, i=idx: self._gallery_delete(i))
        cly.addWidget(btn_del)

        return card

    def _gallery_use(self, entry: dict):
        p = entry.get("portrait", "")
        s = entry.get("sheet", "")
        # Reset first — avoids stale paths from the previously active entry
        self._image_path = ""
        self._sheet_path = ""
        if p and os.path.isfile(p):
            self._image_path = p
        if s and os.path.isfile(s):
            self._sheet_path = s
            if not self._image_path:
                self._image_path = s
        preview = s if (s and os.path.isfile(s)) else p
        if preview and os.path.isfile(preview):
            self._load_preview(preview)
        self._refresh_gallery_tab()
        self._refresh_preview_nav()

    def _gallery_unuse(self):
        self._image_path = ""
        self._sheet_path = ""
        self._preview.clear()
        self._preview.setText("Aucun portrait\ngénéré")
        self._refresh_gallery_tab()
        self._refresh_preview_nav()

    def _gallery_delete(self, idx: int):
        if not (0 <= idx < len(self._generated_images)):
            return
        entry = self._generated_images[idx]
        p = entry.get("portrait", "")
        s = entry.get("sheet", "")
        was_active = (
            (p and p == self._image_path) or
            (s and s == self._sheet_path)
        )
        self._generated_images.pop(idx)
        if was_active:
            if self._generated_images:
                new_idx = min(idx, len(self._generated_images) - 1)
                self._preview_idx = new_idx
                ne = self._generated_images[new_idx]
                np_, ns_ = ne.get("portrait", ""), ne.get("sheet", "")
                self._image_path = np_ if (np_ and os.path.isfile(np_)) else ""
                self._sheet_path = ns_ if (ns_ and os.path.isfile(ns_)) else ""
                display = ns_ if (ns_ and os.path.isfile(ns_)) else np_
                if display and os.path.isfile(display):
                    self._load_preview(display)
            else:
                self._image_path = ""
                self._sheet_path = ""
                self._preview.clear()
                self._preview.setText("Aucun portrait\ngénéré")
                self._preview_idx = 0
        else:
            if idx <= self._preview_idx and self._preview_idx > 0:
                self._preview_idx -= 1
        self._refresh_gallery_tab()
        self._refresh_preview_nav()
        self._status.setText("Image supprimée.")

    # ── Onglet Accessoires ────────────────────────────────────────────────────

    def _refresh_acc_tab(self, update_title: bool = True):
        if not hasattr(self, "_acc_inner"):
            return
        import core.accessories as acc_api
        char_id = self._char.get("id", "")

        # Collect all accessories assigned to this character
        all_accs = acc_api.list_accessories()
        assigned = [a for a in all_accs if char_id in a.get("assigned_to", [])]
        # Also include any orphaned active ones not in assigned_to
        assigned_ids = {a["id"] for a in assigned}
        for aid in list(self._active_acc_ids):
            if aid not in assigned_ids:
                a = acc_api.get_accessory(aid)
                if a:
                    assigned.append(a)

        if update_title:
            active_count = sum(1 for a in assigned if a["id"] in self._active_acc_ids)
            self._update_nav_label(1, f"Acc. ({active_count})")

        while self._acc_inner.count():
            it = self._acc_inner.takeAt(0)
            if it.widget():
                it.widget().deleteLater()

        if not assigned:
            empty = QLabel("Aucun accessoire assigné.")
            empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
            empty.setWordWrap(True)
            empty.setStyleSheet(
                f"color:{CP['text_dim']};font-size:11px;background:transparent;padding:24px;"
            )
            self._acc_inner.addWidget(empty)
        else:
            for acc in assigned:
                aid = acc["id"]
                is_active = aid in self._active_acc_ids
                row = self._make_item_row(
                    acc, "accessory", is_active,
                    on_use    = lambda _, i=aid: self._acc_use(i),
                    on_unuse  = lambda _, i=aid: self._acc_unuse(i),
                    on_remove = lambda _, i=aid: self._acc_remove(i),
                )
                self._acc_inner.addWidget(row)

        self._acc_inner.addStretch()

    def _acc_use(self, acc_id: str):
        self._active_acc_ids.add(acc_id)
        self._refresh_acc_tab()

    def _acc_unuse(self, acc_id: str):
        self._active_acc_ids.discard(acc_id)
        self._refresh_acc_tab()

    def _acc_remove(self, acc_id: str):
        self._active_acc_ids.discard(acc_id)
        import core.accessories as acc_api
        char_id = self._char.get("id", "")
        acc = acc_api.get_accessory(acc_id)
        if acc and char_id:
            acc["assigned_to"] = [a for a in acc.get("assigned_to", []) if a != char_id]
            acc_api.save_accessory(acc)
        self._refresh_acc_tab()

    # ── Onglet HMC ────────────────────────────────────────────────────────────

    def _refresh_hmc_tab(self, update_title: bool = True):
        if not hasattr(self, "_hmc_inner"):
            return
        import core.hmc as hmc_api
        char_id = self._char.get("id", "")

        all_items = hmc_api.list_hmc_items()
        assigned = [h for h in all_items if char_id in h.get("assigned_to", [])]
        assigned_ids = {h["id"] for h in assigned}
        for hid in list(self._active_hmc_ids):
            if hid not in assigned_ids:
                h = hmc_api.get_hmc_item(hid)
                if h:
                    assigned.append(h)

        if update_title:
            active_count = sum(1 for h in assigned if h["id"] in self._active_hmc_ids)
            self._update_nav_label(2, f"HMC ({active_count})")

        while self._hmc_inner.count():
            it = self._hmc_inner.takeAt(0)
            if it.widget():
                it.widget().deleteLater()

        if not assigned:
            empty = QLabel("Aucun élément HMC assigné.")
            empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
            empty.setWordWrap(True)
            empty.setStyleSheet(
                f"color:{CP['text_dim']};font-size:11px;background:transparent;padding:24px;"
            )
            self._hmc_inner.addWidget(empty)
        else:
            for item in assigned:
                hid = item["id"]
                is_active = hid in self._active_hmc_ids
                row = self._make_item_row(
                    item, "hmc", is_active,
                    on_use    = lambda _, i=hid: self._hmc_use(i),
                    on_unuse  = lambda _, i=hid: self._hmc_unuse(i),
                    on_remove = lambda _, i=hid: self._hmc_remove(i),
                )
                self._hmc_inner.addWidget(row)

        self._hmc_inner.addStretch()

    def _hmc_use(self, hmc_id: str):
        self._active_hmc_ids.add(hmc_id)
        self._refresh_hmc_tab()

    def _hmc_unuse(self, hmc_id: str):
        self._active_hmc_ids.discard(hmc_id)
        self._refresh_hmc_tab()

    def _hmc_remove(self, hmc_id: str):
        self._active_hmc_ids.discard(hmc_id)
        import core.hmc as hmc_api
        char_id = self._char.get("id", "")
        item = hmc_api.get_hmc_item(hmc_id)
        if item and char_id:
            item["assigned_to"] = [a for a in item.get("assigned_to", []) if a != char_id]
            hmc_api.save_hmc_item(item)
        self._refresh_hmc_tab()

    # ── Ligne d'item partagée (Acc + HMC) ────────────────────────────────────

    def _make_item_row(self, item: dict, kind: str, is_active: bool,
                       on_use=None, on_unuse=None, on_remove=None) -> QFrame:
        row = QFrame()
        row.setStyleSheet(
            f"QFrame{{background:{CP['bg2']};border:1px solid {CP['border']};border-radius:6px;}}"
        )
        rl = QHBoxLayout(row)
        rl.setContentsMargins(8, 6, 8, 6)
        rl.setSpacing(8)

        thumb = QLabel()
        thumb.setFixedSize(36, 36)
        thumb.setAlignment(Qt.AlignmentFlag.AlignCenter)
        img = item.get("image_path", "")
        if img and os.path.isfile(img):
            pix = QPixmap(img).scaled(
                36, 36,
                Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                Qt.TransformationMode.SmoothTransformation,
            )
            pix = pix.copy((pix.width()-36)//2, (pix.height()-36)//2, 36, 36)
            thumb.setPixmap(pix)
            thumb.setStyleSheet("background:transparent;border-radius:4px;border:none;")
        else:
            icon = {"accessory": "👜", "hmc": "👗"}.get(kind, "📦")
            thumb.setText(icon)
            thumb.setStyleSheet(
                f"background:{CP['bg3']};border-radius:4px;border:none;font-size:16px;"
            )
        rl.addWidget(thumb)

        col = QVBoxLayout()
        col.setSpacing(2)
        name_lbl = QLabel(item.get("name", "—"))
        name_lbl.setStyleSheet(
            f"color:{CP['text_primary']};font-size:11px;font-weight:700;"
            f"background:transparent;border:none;"
        )
        sub = item.get("category") or item.get("hmc_type") or ""
        sub_lbl = QLabel(sub)
        sub_lbl.setStyleSheet(
            f"color:{CP['text_secondary']};font-size:9px;background:transparent;border:none;"
        )
        col.addWidget(name_lbl)
        col.addWidget(sub_lbl)
        rl.addLayout(col, 1)

        # 3-button column
        btn_col = QVBoxLayout()
        btn_col.setSpacing(3)
        btn_col.setContentsMargins(0, 0, 0, 0)

        if is_active:
            btn_toggle = QPushButton("✕ Ne pas utiliser")
            btn_toggle.setFixedHeight(22)
            btn_toggle.setStyleSheet(
                f"QPushButton{{background:transparent;color:{CP['orange']};"
                f"border:1px solid rgba(255,140,66,0.4);border-radius:4px;"
                f"font-size:8px;font-weight:700;padding:0 4px;}}"
                f"QPushButton:hover{{background:rgba(255,140,66,0.15);"
                f"color:{CP['orange']};border-color:{CP['orange']};}}"
            )
            if on_unuse:
                btn_toggle.clicked.connect(on_unuse)
        else:
            btn_toggle = QPushButton("✓ Utiliser")
            btn_toggle.setFixedHeight(22)
            btn_toggle.setStyleSheet(
                f"QPushButton{{background:transparent;color:{CP['accent']};"
                f"border:1px solid {CP['accent_dim']};border-radius:4px;"
                f"font-size:8px;font-weight:700;padding:0 4px;}}"
                f"QPushButton:hover{{background:{CP['accent']};color:#07080f;}}"
            )
            if on_use:
                btn_toggle.clicked.connect(on_use)
        btn_col.addWidget(btn_toggle)

        btn_del = QPushButton("Supprimer")
        btn_del.setFixedHeight(20)
        btn_del.setStyleSheet(
            f"QPushButton{{background:transparent;color:{CP['text_dim']};"
            f"border:1px solid {CP['border']};border-radius:4px;"
            f"font-size:8px;font-weight:700;padding:0 4px;}}"
            f"QPushButton:hover{{background:rgba(255,79,106,0.12);"
            f"color:{CP['red']};border-color:{CP['red']};}}"
        )
        if on_remove:
            btn_del.clicked.connect(on_remove)
        btn_col.addWidget(btn_del)

        rl.addLayout(btn_col)

        return row

    # ── HMC look selector (génération) ───────────────────────────────────────

    def _refresh_hmc_gen_section(self):
        while self._hmc_gen_hbox.count():
            it = self._hmc_gen_hbox.takeAt(0)
            if it.widget():
                it.widget().deleteLater()

        import core.hmc as hmc_api
        char_id = self._char.get("id", "")
        all_items = hmc_api.list_hmc_items()
        assigned = [h for h in all_items if char_id in h.get("assigned_to", [])]
        assigned_ids = {h["id"] for h in assigned}
        for hid in list(self._active_hmc_ids):
            if hid not in assigned_ids:
                h = hmc_api.get_hmc_item(hid)
                if h:
                    assigned.append(h)

        if not assigned:
            hint = QLabel("Aucun HMC assigné — ajoutes-en dans l'onglet HMC pour personnaliser le look.")
            hint.setWordWrap(True)
            hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
            hint.setStyleSheet(
                f"color:{CP['text_dim']};font-size:10px;background:transparent;border:none;"
            )
            self._hmc_gen_hbox.addWidget(hint)
            self._hmc_gen_hbox.addStretch()
            return

        _icons = {"Habit": "👗", "Maquillage": "💄", "Coiffure": "💇"}
        _ss_off = (
            f"QPushButton{{background:{CP['bg3']};color:{CP['text_dim']};"
            f"border:1px solid {CP['border']};border-radius:6px;"
            f"font-size:8px;font-weight:600;padding:2px;text-align:center;}}"
            f"QPushButton:hover{{background:{CP['bg2']};color:{CP['text_secondary']};"
            f"border-color:{CP['border_bright']};}}"
            f"QPushButton:checked{{background:rgba(78,205,196,0.18);color:{CP['accent']};"
            f"border:1px solid rgba(78,205,196,0.40);}}"
            f"QPushButton:checked:hover{{background:rgba(78,205,196,0.28);}}"
        )
        for item in assigned:
            hid = item["id"]
            icon = _icons.get(item.get("hmc_type", ""), "✂")
            short_name = item.get("name", "?")
            short_name = short_name if len(short_name) <= 9 else short_name[:8] + "…"
            btn = QPushButton(f"{icon}\n{short_name}")
            btn.setFixedSize(64, 54)
            btn.setCheckable(True)
            btn.setChecked(hid in self._hmc_for_gen)
            btn.setToolTip(
                f"{item.get('hmc_type', 'HMC')} : {item.get('name', '')}\n"
                f"{item.get('prompt') or item.get('description', '')}"
            )
            btn.setStyleSheet(_ss_off)
            btn.clicked.connect(lambda checked, h=hid: self._toggle_hmc_for_gen(h, checked))
            self._hmc_gen_hbox.addWidget(btn)

        self._hmc_gen_hbox.addStretch()

    def _toggle_hmc_for_gen(self, hmc_id: str, selected: bool):
        if selected:
            self._hmc_for_gen.add(hmc_id)
        else:
            self._hmc_for_gen.discard(hmc_id)

    def _on_save(self):
        name = self._name.text().strip()
        if not name:
            QMessageBox.warning(self, "Nom manquant", "Entre le nom du personnage.")
            return

        data = dict(self._char)
        data.update({
            "name":             name,
            "role":             self._role.currentText(),
            "prompt":           self._prompt.toPlainText().strip(),
            "image_path":       self._image_path,
            "sheet_path":       self._sheet_path,
            "ref_paths":        self._ref_paths,
            "generated_images": self._generated_images,
            "accessory_ids":    list(self._active_acc_ids),
            "hmc_ids":          list(self._active_hmc_ids),
            "ref_usage_key":    self._ref_usage_combo.currentData() if hasattr(self, "_ref_usage_combo") else "inspiration",
        })
        self._saved_data = casting_api.save_character(data)

        if self._image_path and os.path.isfile(self._image_path):
            from davinci.importer import import_image_to_bin
            import_image_to_bin(self._image_path, "Castings")

        self.accept()

    def get_character(self) -> dict | None:
        return self._saved_data
