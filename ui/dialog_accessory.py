import os
from PyQt6.QtWidgets import (
    QDialog, QWidget, QHBoxLayout, QVBoxLayout, QLabel, QPushButton,
    QLineEdit, QTextEdit, QComboBox, QProgressBar, QFileDialog,
    QMessageBox, QFrame, QScrollArea, QCheckBox, QSpinBox,
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPixmap
from ui.styles import CP, PANDORA_STYLESHEET
from ui.icons import claude_icon_pixmap, install_hover_icon
from ui.creative_panel import NanoBananaControlsPanel
from core.i18n import translate, to_source
import core.accessories as acc_api
from core.accessories import CATEGORIES
from api.nano_banana import (
    OptimizeAccessoryPromptWorker, OptimizeAccessoryWithReferencesWorker,
    OptimizeStyleReferenceWorker, GenerateItemWorker,
)


def _lbl(text, size=11, color=None):
    l = QLabel(text)
    l.setStyleSheet(
        f"color:{color or CP['text_secondary']};font-size:{size}px;background:transparent;border:none;"
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


def _input(placeholder=""):
    e = QLineEdit()
    e.setPlaceholderText(placeholder)
    e.setFixedHeight(36)
    e.setStyleSheet(
        f"QLineEdit{{background:{CP['bg3']};border:1px solid {CP['border']};"
        f"border-radius:6px;color:{CP['text_primary']};font-size:12px;padding:0 10px;}}"
        f"QLineEdit:focus{{border-color:{CP['accent']};}}"
    )
    return e


class AccessoryDialog(QDialog):

    def __init__(self, parent=None, item: dict | None = None):
        super().__init__(parent)
        self._item             = item or {}
        self._image_path       = self._item.get("image_path", "")
        self._ref_paths        = list(self._item.get("ref_paths", []))
        self._assigned_shots   = list(self._item.get("assigned_shots", []))
        # Auto-detect shots from storyboard (source of truth for accessory_ids)
        acc_id = self._item.get("id", "")
        if acc_id:
            import core.storyboard as sb_api
            for shot in sb_api.list_shots():
                if acc_id in shot.get("accessory_ids", []):
                    sid = shot.get("id", "")
                    if sid and sid not in self._assigned_shots:
                        self._assigned_shots.append(sid)
        self._assigned_sequences = [x for x in self._item.get("assigned_sequences", []) if isinstance(x, int)]
        self._generated_images: list = list(self._item.get("generated_images", []))
        if self._image_path and self._image_path not in self._generated_images and os.path.isfile(self._image_path):
            self._generated_images.insert(0, self._image_path)
        self._preview_idx: int = (
            self._generated_images.index(self._image_path)
            if self._image_path in self._generated_images else 0
        )
        self._worker_opt       = None
        self._worker_refs      = None
        self._worker_gen       = None
        self._saved_data       = None

        self.setWindowTitle("Créer un accessoire" if not item else "Modifier l'accessoire")
        self.setStyleSheet(PANDORA_STYLESHEET + f"QDialog{{background:{CP['bg1']};}}")
        from ui.widgets import fit_dialog_to_screen
        fit_dialog_to_screen(self, 0.68, 0.82, 740, 480)

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

    # ── Formulaire ────────────────────────────────────────────────────────────

    def _build_form(self):
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

        title = QLabel("Nouvel accessoire" if not self._item else "Modifier l'accessoire")
        title.setStyleSheet(
            f"color:{CP['text_primary']};font-size:18px;font-weight:700;background:transparent;"
        )
        lay.addWidget(title)
        lay.addSpacing(2)

        # Nom + Catégorie
        row = QHBoxLayout()
        row.setSpacing(12)

        col_name = QVBoxLayout()
        col_name.setSpacing(4)
        col_name.addWidget(_lbl("Nom de l'accessoire"))
        self._name = _input("Ex: Montre en or victorienne")
        self._name.setText(self._item.get("name", ""))
        col_name.addWidget(self._name)

        col_cat = QVBoxLayout()
        col_cat.setSpacing(4)
        col_cat.addWidget(_lbl("Catégorie"))
        self._cat = QComboBox()
        self._cat.setEditable(True)
        self._cat.addItems(CATEGORIES)
        self._cat.setCurrentText(self._item.get("category", CATEGORIES[0]))
        self._cat.setFixedHeight(36)
        self._cat.setStyleSheet(
            f"QComboBox{{background:{CP['bg3']};border:1px solid {CP['border']};"
            f"border-radius:6px;color:{CP['text_primary']};font-size:12px;padding:0 10px;}}"
            f"QComboBox:focus{{border-color:{CP['accent']};}}"
            f"QComboBox::drop-down{{border:none;width:20px;}}"
            f"QComboBox QAbstractItemView{{background:{CP['bg3']};border:1px solid {CP['border_bright']};"
            f"color:{CP['text_primary']};selection-background-color:{CP['accent_dim']};}}"
        )
        col_cat.addWidget(self._cat)

        row.addLayout(col_name, 2)
        row.addLayout(col_cat, 1)
        lay.addLayout(row)

        # ── Avertissement contenu ─────────────────────────────────────────────
        warn = QLabel(
            "⚠  Nano Banana applique des filtres de contenu (ByteDance / fal.ai). "
            "Certains sujets peuvent être refusés ou modifiés. Reformule le prompt en cas d'erreur."
        )
        warn.setWordWrap(True)
        warn.setStyleSheet(
            f"color:{CP['orange']};font-size:10px;font-family:'Consolas',monospace;"
            f"background:rgba(255,140,66,0.08);border:1px solid rgba(255,140,66,0.25);"
            f"border-radius:6px;padding:8px 10px;"
        )
        lay.addWidget(warn)

        # Prompt + cloud
        ph = QHBoxLayout()
        ph.setContentsMargins(0, 0, 0, 0)
        ph.addWidget(_lbl("Prompt pour Nano Banana"))
        ph.addStretch()

        self._btn_cloud = QPushButton()
        self._btn_cloud.setFixedSize(26, 26)
        self._btn_cloud.setToolTip("Optimiser avec Claude\nAdapté aux accessoires de production cinéma.")
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
        # « Améliorer le prompt » (☁) RETIRÉ — fonction jugée inutile/instable.
        # _btn_cloud reste créé (non affiché) pour ne casser aucune autre référence.
        self._btn_cloud.setVisible(False)
        lay.addLayout(ph)

        self._prompt = QTextEdit()
        self._prompt.setPlaceholderText(
            "Décris l'accessoire…\nEx: Victorian gold pocket watch, ornate engravings, worn patina.\n\n"
            "Clique sur ☁ pour optimiser via Claude."
        )
        self._prompt.setPlainText(self._item.get("prompt", ""))
        self._prompt.setFixedHeight(110)
        self._prompt.setStyleSheet(
            f"QTextEdit{{background:{CP['bg3']};border:1px solid {CP['border']};"
            f"border-radius:6px;color:{CP['text_primary']};font-size:12px;padding:8px;}}"
            f"QTextEdit:focus{{border-color:{CP['accent']};}}"
        )
        lay.addWidget(self._prompt)

        # Références visuelles
        rh = QHBoxLayout()
        rh.addWidget(_lbl("Références visuelles"))
        rh.addStretch()
        self._refs_hint_lbl = _lbl("Claude enrichit le prompt", size=10, color=CP["text_dim"])
        rh.addWidget(self._refs_hint_lbl)
        lay.addLayout(rh)

        self._refs_scroll = QScrollArea()
        self._refs_scroll.setFixedHeight(80)
        self._refs_scroll.setWidgetResizable(True)
        self._refs_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self._refs_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._refs_scroll.setStyleSheet(f"""
            QScrollArea{{background:{CP['bg2']};border:1px solid {CP['border']};border-radius:8px;}}
            QScrollBar:horizontal{{height:4px;background:{CP['bg3']};border-radius:2px;}}
            QScrollBar::handle:horizontal{{background:{CP['border_bright']};border-radius:2px;min-width:20px;}}
            QScrollBar::add-line:horizontal,QScrollBar::sub-line:horizontal{{width:0;}}
        """)
        self._refs_container = QWidget()
        self._refs_container.setStyleSheet(f"background:{CP['bg2']};")
        self._refs_layout = QHBoxLayout(self._refs_container)
        self._refs_layout.setContentsMargins(8, 8, 8, 8)
        self._refs_layout.setSpacing(8)
        self._refs_scroll.setWidget(self._refs_container)
        self._refresh_refs()
        lay.addWidget(self._refs_scroll)

        # Usage des références
        _ur = QHBoxLayout()
        _ur.setSpacing(8)
        _ur_lbl = _lbl("Usage des références")
        _ur_lbl.setFixedWidth(130)
        _ur.addWidget(_ur_lbl)
        self._ref_usage_combo = QComboBox()
        self._ref_usage_combo.addItem("🌟  Inspiration  —  Claude enrichit le prompt", "inspiration")
        self._ref_usage_combo.addItem("🎨  Style pictural  —  extrait et applique le style visuel", "style")
        self._ref_usage_combo.addItem("🎯  Fidélité exacte  —  reproduit l'objet précisément", "fidelity")
        self._ref_usage_combo.setFixedHeight(30)
        self._ref_usage_combo.setStyleSheet(_combo_ss())
        _saved_usage = self._item.get("ref_usage_key", "inspiration")
        for _i in range(self._ref_usage_combo.count()):
            if self._ref_usage_combo.itemData(_i) == _saved_usage:
                self._ref_usage_combo.setCurrentIndex(_i)
                break
        self._ref_usage_combo.currentIndexChanged.connect(self._on_ref_usage_changed)
        _ur.addWidget(self._ref_usage_combo, 1)
        lay.addLayout(_ur)

        # Style d'image
        style_row = QHBoxLayout()
        style_row.setSpacing(8)
        style_lbl = _lbl("Style d'image")
        style_lbl.setFixedWidth(130)
        style_row.addWidget(style_lbl)
        import core.style as _style_mod
        from PyQt6.QtGui import QColor as _QColor
        self._style_combo = QComboBox()
        self._style_combo.addItem("— Style du projet —", "")
        _cur_grp = None
        for _s in _style_mod.STYLES:
            _g = _s.get("group", "")
            if _g != _cur_grp:
                _cur_grp = _g
                _gi = next((g for g in _style_mod.GROUPS if g["key"] == _g), None)
                if _gi:
                    self._style_combo.addItem(
                        f"  {_gi['icon']}  {translate(_gi['name']).upper()}", "__sep__"
                    )
                    _sep_item = self._style_combo.model().item(
                        self._style_combo.count() - 1
                    )
                    _sep_item.setEnabled(False)
                    _sep_item.setForeground(_QColor(CP.get("accent2", "#7c6bff")))
            self._style_combo.addItem(f"    {_s['icon']}  {translate(_s['name'])}", _s["key"])
        saved_key = self._item.get("accessory_style_key", "") or _style_mod.get_style_key()
        if saved_key:
            for _i in range(self._style_combo.count()):
                if self._style_combo.itemData(_i) == saved_key:
                    self._style_combo.setCurrentIndex(_i)
                    break
        self._style_combo.setFixedHeight(36)
        self._style_combo.setStyleSheet(
            f"QComboBox{{background:{CP['bg3']};border:1px solid {CP['border']};"
            f"border-radius:6px;color:{CP['text_primary']};font-size:11px;padding:0 8px;}}"
            f"QComboBox:focus{{border-color:{CP['accent']};}}"
            f"QComboBox::drop-down{{border:none;width:20px;}}"
            f"QComboBox QAbstractItemView{{background:{CP['bg3']};border:1px solid {CP['border_bright']};"
            f"color:{CP['text_primary']};selection-background-color:{CP['accent_dim']};"
            f"font-size:11px;padding:4px;}}"
        )
        style_row.addWidget(self._style_combo, 1)
        lay.addLayout(style_row)
        self._on_ref_usage_changed()
        self._style_combo.currentIndexChanged.connect(self._update_suffix_edit)
        _sfx_lbl = QLabel("↓  Suffix de style injecté (modifiable) :")
        _sfx_lbl.setStyleSheet(
            f"color:{CP['text_dim']};font-size:9px;background:transparent;border:none;"
        )
        lay.addWidget(_sfx_lbl)
        self._suffix_edit = QTextEdit()
        self._suffix_edit.setFixedHeight(54)
        self._suffix_edit.setStyleSheet(
            f"QTextEdit{{background:{CP['bg2']};border:1px solid {CP['border']};"
            f"border-radius:6px;color:#ff8c69;font-size:9px;"
            f"font-family:'Consolas',monospace;padding:4px;}}"
            f"QTextEdit:focus{{border-color:{CP['accent']};}}"
        )
        self._suffix_edit.setPlaceholderText(
            "Vide — sélectionnez un Style d'image ci-dessus ou définissez le Style du projet"
        )
        self._suffix_edit.setToolTip(
            "Suffixe de style ajouté automatiquement au prompt (affiché en orange).\n"
            "Inclut la caméra/optique définie dans Image & Son si configurée.\n"
            "Modifiable librement — ce texte est envoyé tel quel à l'API."
        )
        lay.addWidget(self._suffix_edit)
        self._update_suffix_edit()

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

        # Bouton générer
        _gen_row = QHBoxLayout()
        _gen_row.setSpacing(8)
        btn_gen = QPushButton("🎨  Générer l'image")
        btn_gen.setFixedHeight(40)
        btn_gen.setStyleSheet(
            f"QPushButton{{background:{CP['accent']};color:#07080f;"
            f"border:none;border-radius:8px;font-size:12px;font-weight:700;}}"
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
        self._spinbox_count.setToolTip("Nombre d'images à générer (1–4)")
        self._spinbox_count.setStyleSheet(
            f"QSpinBox{{background:{CP['bg3']};border:1px solid {CP['border']};"
            f"border-radius:6px;color:{CP['text_primary']};font-size:12px;font-weight:700;"
            f"padding:0 4px;}}"
            f"QSpinBox::up-button,QSpinBox::down-button{{width:16px;border:none;"
            f"background:{CP['bg4']};border-radius:3px;}}"
        )
        _gen_row.addWidget(self._spinbox_count)

        price_lbl = QLabel("💰  Nano Banana (fal.ai) : ~0,03–0,05 $ / image")
        price_lbl.setStyleSheet(
            f"color:{CP['text_dim']};font-size:9px;"
            f"font-family:'Consolas',monospace;background:transparent;"
        )

        self._progress = QProgressBar()
        self._progress.setRange(0, 100)
        self._progress.setFixedHeight(4)
        self._progress.setVisible(False)
        self._progress.setStyleSheet(
            f"QProgressBar{{background:{CP['bg3']};border:none;border-radius:2px;}}"
            f"QProgressBar::chunk{{background:qlineargradient(x1:0,y1:0,x2:1,y2:0,"
            f"stop:0 {CP['accent_dim']},stop:1 {CP['accent']});border-radius:2px;}}"
        )

        self._status = QLabel("")
        self._status.setWordWrap(True)
        self._status.setStyleSheet(
            f"color:{CP['text_dim']};font-size:10px;font-family:'Consolas',monospace;background:transparent;"
        )

        lay.addStretch()

        scroll.setWidget(w)
        outer_lay.addWidget(scroll, 1)

        # ── Barre d'action fixe (toujours visible — pas besoin de scroller) ──
        _action = QWidget()
        _action.setStyleSheet(f"background:{CP['bg1']};border-top:1px solid {CP['border']};")
        _action_lay = QVBoxLayout(_action)
        _action_lay.setContentsMargins(28, 10, 24, 4)
        _action_lay.setSpacing(6)
        _action_lay.addLayout(_gen_row)
        _action_lay.addWidget(price_lbl)
        _action_lay.addWidget(self._progress)
        _action_lay.addWidget(self._status)
        outer_lay.addWidget(_action)

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

        btn_save = QPushButton("✓  Sauvegarder l'accessoire")
        btn_save.setFixedHeight(40)
        btn_save.setStyleSheet(
            f"QPushButton{{background:{CP['accent2']};color:#ffffff;"
            f"border:none;border-radius:8px;font-size:12px;font-weight:700;padding:0 18px;}}"
            f"QPushButton:hover{{background:#9d8fff;}}"
        )
        btn_save.clicked.connect(self._on_save)

        btn_row.addWidget(btn_cancel)
        btn_row.addStretch()
        btn_row.addWidget(btn_save)
        outer_lay.addWidget(btn_bar)

        return outer

    # ── Panneau droit ─────────────────────────────────────────────────────────

    def _build_preview(self):
        w = QWidget()
        w.setFixedWidth(280)
        w.setStyleSheet(f"background:{CP['bg0']};")

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet("QScrollArea{background:transparent;border:none;}")

        inner = QWidget()
        inner.setStyleSheet("background:transparent;")
        lay = QVBoxLayout(inner)
        lay.setContentsMargins(20, 24, 20, 24)
        lay.setSpacing(12)

        lay.addWidget(_lbl("Aperçu", color=CP["text_secondary"]))

        self._preview = QLabel()
        self._preview.setFixedSize(240, 240)
        self._preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._preview.setStyleSheet(
            f"background:{CP['bg2']};border:1px solid {CP['border']};"
            f"border-radius:12px;color:{CP['text_dim']};font-size:13px;"
        )
        self._preview.setText("Aucune image\ngénérée")
        self._preview.setWordWrap(True)
        self._preview.setCursor(Qt.CursorShape.PointingHandCursor)
        self._preview.mousePressEvent = lambda e: self._show_fullsize()
        lay.addWidget(self._preview)

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
        self._preview_counter.setStyleSheet(f"color:{CP['text_dim']};font-size:10px;background:transparent;")
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
        lay.addLayout(nav_row)

        self._btn_activate = QPushButton("✓  Activer")
        self._btn_activate.setFixedHeight(30)
        self._btn_activate.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_activate.setVisible(False)
        self._btn_activate.clicked.connect(self._activate_current)
        lay.addWidget(self._btn_activate)

        self._refresh_preview_nav()

        _act_row = QHBoxLayout()
        _act_row.setSpacing(6)
        self._btn_del_img = QPushButton("🗑  Supprimer cette image")
        self._btn_del_img.setFixedHeight(28)
        self._btn_del_img.setVisible(False)
        self._btn_del_img.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_del_img.setStyleSheet(
            f"QPushButton{{background:transparent;color:{CP['red']};"
            f"border:1px solid rgba(255,79,106,0.40);border-radius:7px;"
            f"font-size:10px;font-weight:600;padding:0 8px;}}"
            f"QPushButton:hover{{background:rgba(255,79,106,0.12);border-color:{CP['red']};}}"
        )
        self._btn_del_img.clicked.connect(self._on_delete_current_image)
        _act_row.addWidget(self._btn_del_img, 1)

        self._btn_panel_variation = QPushButton("🎲  Variation")
        self._btn_panel_variation.setFixedHeight(28)
        self._btn_panel_variation.setVisible(False)
        self._btn_panel_variation.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_panel_variation.setStyleSheet(
            f"QPushButton{{background:{CP['bg3']};color:{CP['text_secondary']};"
            f"border:1px solid {CP['border']};border-radius:7px;"
            f"font-size:10px;font-weight:600;padding:0 8px;}}"
            f"QPushButton:hover{{background:{CP['bg4']};color:{CP['text_primary']};"
            f"border-color:{CP['border_bright']};}}"
            f"QPushButton:disabled{{opacity:0.4;}}"
        )
        self._btn_panel_variation.clicked.connect(self._on_generate)
        _act_row.addWidget(self._btn_panel_variation, 1)
        lay.addLayout(_act_row)

        lay.addSpacing(4)

        # Utilisé dans les séquences
        lay.addWidget(_lbl("Utilisé dans les séquences :", color=CP["text_secondary"]))
        self._seqs_scroll = QScrollArea()
        self._seqs_scroll.setFixedHeight(100)
        self._seqs_scroll.setWidgetResizable(True)
        self._seqs_scroll.setStyleSheet(
            f"QScrollArea{{background:{CP['bg2']};border:1px solid {CP['border']};"
            f"border-radius:6px;}}"
        )
        self._seqs_inner = QWidget()
        self._seqs_inner.setStyleSheet("background:transparent;")
        self._seqs_lay = QVBoxLayout(self._seqs_inner)
        self._seqs_lay.setContentsMargins(8, 8, 8, 8)
        self._seqs_lay.setSpacing(4)
        self._seqs_scroll.setWidget(self._seqs_inner)
        lay.addWidget(self._seqs_scroll)

        lay.addSpacing(4)

        # Utilisé dans les plans
        lay.addWidget(_lbl("Utilisé dans les plans :", color=CP["text_secondary"]))
        self._shots_scroll = QScrollArea()
        self._shots_scroll.setFixedHeight(120)
        self._shots_scroll.setWidgetResizable(True)
        self._shots_scroll.setStyleSheet(
            f"QScrollArea{{background:{CP['bg2']};border:1px solid {CP['border']};"
            f"border-radius:6px;}}"
        )
        self._shots_inner = QWidget()
        self._shots_inner.setStyleSheet("background:transparent;")
        self._shots_lay = QVBoxLayout(self._shots_inner)
        self._shots_lay.setContentsMargins(8, 8, 8, 8)
        self._shots_lay.setSpacing(4)
        self._shots_scroll.setWidget(self._shots_inner)
        lay.addWidget(self._shots_scroll)
        self._refresh_shots_list()
        self._refresh_sequences_list()

        lay.addStretch()

        if self._image_path and os.path.isfile(self._image_path):
            self._load_preview(self._image_path)

        scroll.setWidget(inner)
        outer = QVBoxLayout(w)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(scroll)
        return w

    # ── Références ────────────────────────────────────────────────────────────

    def _refresh_refs(self):
        while self._refs_layout.count():
            item = self._refs_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        for path in self._ref_paths:
            self._refs_layout.addWidget(self._make_ref_thumb(path))

        btn_add = QPushButton("+")
        btn_add.setFixedSize(60, 60)
        btn_add.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_add.setToolTip("Ajouter des images de référence")
        btn_add.setStyleSheet(f"""
            QPushButton{{background:transparent;color:{CP['text_dim']};
                border:1px dashed {CP['border_bright']};border-radius:8px;
                font-size:24px;font-weight:300;padding:0;}}
            QPushButton:hover{{color:{CP['accent']};border-color:{CP['accent']};
                background:rgba(78,205,196,0.08);}}
        """)
        btn_add.clicked.connect(self._on_add_refs)
        self._refs_layout.addWidget(btn_add)
        self._refs_layout.addStretch()

    def _make_ref_thumb(self, path):
        c = QWidget()
        c.setFixedSize(68, 60)
        lbl = QLabel(c)
        lbl.setGeometry(0, 0, 60, 60)
        pix = QPixmap(path)
        if not pix.isNull():
            pix = pix.scaled(60, 60, Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                             Qt.TransformationMode.SmoothTransformation)
            pix = pix.copy((pix.width()-60)//2, (pix.height()-60)//2, 60, 60)
            lbl.setPixmap(pix)
        else:
            lbl.setStyleSheet(f"background:{CP['bg3']};border-radius:6px;")
        btn = QPushButton("×", c)
        btn.setGeometry(48, 0, 20, 20)
        btn.setStyleSheet(
            "QPushButton{background:#992222;color:#fff;border:none;"
            "border-radius:10px;font-size:12px;font-weight:700;padding:0;}"
            "QPushButton:hover{background:#cc3333;}"
        )
        btn.clicked.connect(lambda checked=False, p=path: self._remove_ref(p))
        return c

    def _remove_ref(self, path):
        if path in self._ref_paths:
            self._ref_paths.remove(path)
            self._refresh_refs()

    def _on_ref_usage_changed(self):
        usage = self._ref_usage_combo.currentData() if hasattr(self, "_ref_usage_combo") else "inspiration"
        is_style = usage == "style"
        if hasattr(self, "_style_combo"):
            combo = self._style_combo
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
        if hasattr(self, "_refs_hint_lbl"):
            hints = {
                "inspiration": "Claude enrichit le prompt",
                "style":       "1re image → style visuel extrait par IA",
                "fidelity":    "1re image → objet décrit pour reproduction fidèle",
            }
            self._refs_hint_lbl.setText(hints.get(usage, ""))

    # ── Actions ───────────────────────────────────────────────────────────────

    def _on_optimize(self):
        text = self._prompt.toPlainText().strip()
        if not text:
            self._status.setText("Décris l'accessoire avant d'optimiser.")
            return
        self._btn_cloud.setEnabled(False)
        ref_usage = self._ref_usage_combo.currentData() if hasattr(self, "_ref_usage_combo") else "inspiration"
        valid_refs = [p for p in self._ref_paths if p and os.path.isfile(p)]
        if ref_usage == "style" and valid_refs:
            self._status.setText("Analyse du style de référence en cours…")
            self._worker_opt = OptimizeStyleReferenceWorker(text, valid_refs)
        else:
            self._status.setText("Optimisation en cours…")
            self._worker_opt = OptimizeAccessoryPromptWorker(text)
        self._worker_opt.finished.connect(lambda p: (self._prompt.setPlainText(p),
                                                      self._btn_cloud.setEnabled(True),
                                                      self._status.setText(translate("Prompt optimisé ✓"))))
        self._worker_opt.failed.connect(lambda e: (self._btn_cloud.setEnabled(True),
                                                    self._status.setText(f"Erreur : {e[:80]}")))
        self._worker_opt.start()

    def _on_add_refs(self):
        from ui.dialog_image_library import ImageLibraryDialog
        paths = ImageLibraryDialog.pick(self)
        if not paths:
            return
        for p in paths:
            if p not in self._ref_paths:
                self._ref_paths.append(p)
        self._refresh_refs()
        usage = self._ref_usage_combo.currentData() if hasattr(self, "_ref_usage_combo") else "inspiration"
        if usage != "inspiration":
            _hints = {"style": "Style pictural — analysé à la génération ✓",
                      "fidelity": "Fidélité exacte — analysée à la génération ✓"}
            self._status.setText(_hints.get(usage, f"{len(self._ref_paths)} référence(s) ajoutée(s)."))
            return
        from core.config import load_config
        if load_config().get("anthropic_key", "").strip():
            self._btn_cloud.setEnabled(False)
            self._status.setText(f"Analyse de {len(self._ref_paths)} référence(s) via Claude…")
            self._worker_refs = OptimizeAccessoryWithReferencesWorker(
                self._prompt.toPlainText().strip(), self._ref_paths
            )
            self._worker_refs.finished.connect(lambda p: (self._prompt.setPlainText(p),
                                                           self._btn_cloud.setEnabled(True),
                                                           self._status.setText("Prompt enrichi ✓")))
            self._worker_refs.failed.connect(lambda e: (self._btn_cloud.setEnabled(True),
                                                         self._status.setText(f"Erreur : {e[:80]}")))
            self._worker_refs.start()
        else:
            self._status.setText(
                f"{len(self._ref_paths)} référence(s) ajoutée(s). "
                "Configurez la clé Anthropic pour optimiser via Claude."
            )

    def _update_suffix_edit(self):
        if not hasattr(self, "_suffix_edit"):
            return
        import core.style as _style_mod
        from core.camera_prefs import get_camera_prefs
        prefs = get_camera_prefs()
        cam = prefs.get("camera_body", "").strip()
        optic = prefs.get("optics_series", "").strip()
        has_cam = bool(cam or optic)
        sk = self._style_combo.currentData() if hasattr(self, "_style_combo") else ""
        if sk and sk != "__sep__":
            _s = next((s for s in _style_mod.STYLES if s["key"] == sk), None)
            if _s:
                sfx = _s.get("image_suffix_no_cam", _s["image_suffix"]) if has_cam else _s["image_suffix"]
            else:
                sfx = _style_mod.get_image_suffix_no_cam() if has_cam else _style_mod.get_image_suffix()
        else:
            sfx = _style_mod.get_image_suffix_no_cam() if has_cam else _style_mod.get_image_suffix()
        cam_parts = []
        if cam:
            cam_parts.append(f"shot on {cam}")
        if optic:
            cam_parts.append(f"{optic} lenses")
        if cam_parts:
            cam_str = ', '.join(cam_parts)
            sfx = f"{sfx}\n{cam_str}" if sfx else cam_str
        self._suffix_edit.setPlainText(sfx)

    def _on_generate(self):
        prompt = self._prompt.toPlainText().strip()
        if not prompt:
            self._status.setText("Remplis le prompt d'abord.")
            return
        self._btn_gen.setEnabled(False)
        self._progress.setVisible(True)
        _usage      = self._ref_usage_combo.currentData() if hasattr(self, "_ref_usage_combo") else "inspiration"
        _valid_refs = [p for p in self._ref_paths if p and os.path.isfile(p)]
        _style_ref  = _valid_refs[0] if _valid_refs else ""
        import core.style as style_api
        if _usage == "style":
            suffix = ""
        else:
            suffix = self._suffix_edit.toPlainText().strip() if hasattr(self, "_suffix_edit") else style_api.get_image_suffix()
        full_prompt = f"{prompt}, {suffix}" if suffix else prompt
        _cs = self._creative.get_prompt_suffix()
        if _cs:
            full_prompt = f"{full_prompt}, {_cs}"
        name = self._name.text().strip() or "accessoire"
        _mk  = self._model_combo.currentData() if hasattr(self, "_model_combo") else None
        _num = self._spinbox_count.value() if hasattr(self, "_spinbox_count") else 1
        self._worker_gen = GenerateItemWorker(
            full_prompt, name, subdir="accessories",
            model_key=_mk, num_images=_num,
            ref_usage=_usage, style_ref_path=_style_ref,
            subject_hint="prop / accessory",
        )
        self._worker_gen.progress.connect(lambda pct, msg: (self._progress.setValue(pct),
                                                              self._status.setText(translate(msg))))
        self._worker_gen.finished.connect(self._on_gen_done)
        if hasattr(self._worker_gen, "multi_finished"):
            self._worker_gen.multi_finished.connect(self._on_multi_gen_done)
        self._worker_gen.failed.connect(self._on_gen_fail)
        self._worker_gen.start()

    def _on_gen_done(self, path):
        self._btn_gen.setEnabled(True)
        self._progress.setVisible(False)
        if not path:
            self._status.setText("Mode mock : aucune image générée (clé fal.ai absente)")
            return
        from ui.dialog_portrait_result import GenerationResultDialog
        dlg = GenerationResultDialog(self, portrait_path=path, title="Image générée")
        dlg.retry_requested.connect(self._on_generate)
        dlg.exec()
        if dlg.was_used():
            self._image_path = path
            if path not in self._generated_images:
                self._generated_images.append(path)
            self._preview_idx = self._generated_images.index(path)
            self._load_preview(path)
            self._refresh_preview_nav()
            self._status.setText(translate("Image ajoutée ✓"))
        else:
            self._status.setText("Image non utilisée — clique Générer pour réessayer.")

    def _on_multi_gen_done(self, paths: list):
        self._btn_gen.setEnabled(True)
        self._progress.setVisible(False)
        valid = [p for p in paths if p and os.path.isfile(p)]
        if not valid:
            self._status.setText("Mode mock : aucune image générée (clé fal.ai absente)")
            return
        for p in valid:
            if p not in self._generated_images:
                self._generated_images.append(p)
        self._preview_idx = self._generated_images.index(valid[0])
        self._image_path  = valid[0]
        self._load_preview(valid[0])
        self._refresh_preview_nav()
        n = len(valid)
        self._status.setText(
            f"{n} image{'s' if n > 1 else ''} importée{'s' if n > 1 else ''} — "
            f"supprime les non désirées avec ‹ ›"
        )

    def _on_delete_current_image(self):
        if not self._generated_images:
            return
        self._generated_images.pop(self._preview_idx)
        n = len(self._generated_images)
        if n == 0:
            self._preview_idx = 0
            self._image_path = ""
            self._preview.clear()
            self._preview.setText("Aucune image\ngénérée")
        else:
            self._preview_idx = min(self._preview_idx, n - 1)
            self._image_path = self._generated_images[self._preview_idx]
            self._load_preview(self._image_path)
        self._refresh_preview_nav()

    def _navigate_preview(self, delta: int):
        n = len(self._generated_images)
        if n <= 1:
            return
        self._preview_idx = (self._preview_idx + delta) % n
        path = self._generated_images[self._preview_idx]
        self._image_path = path
        self._load_preview(path)
        self._refresh_preview_nav()

    def _activate_current(self):
        if not self._generated_images:
            return
        path = self._generated_images[min(self._preview_idx, len(self._generated_images) - 1)]
        self._image_path = path
        self._load_preview(path)
        self._refresh_preview_nav()
        self._status.setText("Image active ✓")

    def _refresh_preview_nav(self):
        n = len(self._generated_images)
        has = n > 1
        self._btn_prev.setVisible(has)
        self._btn_next.setVisible(has)
        self._preview_counter.setText(f"{self._preview_idx + 1} / {n}" if n else "")
        self._preview_counter.setVisible(n > 0)
        has_any = n > 0
        if hasattr(self, "_btn_panel_variation"):
            self._btn_panel_variation.setVisible(has_any)
        if hasattr(self, "_btn_del_img"):
            self._btn_del_img.setVisible(has_any)
        if hasattr(self, "_btn_activate"):
            self._btn_activate.setVisible(has_any)
            if has_any:
                cur = self._generated_images[min(self._preview_idx, n - 1)]
                if cur == self._image_path:
                    self._btn_activate.setText("✓  Active")
                    self._btn_activate.setStyleSheet(
                        f"QPushButton{{background:rgba(61,220,151,0.15);color:{CP['green']};"
                        f"border:1px solid rgba(61,220,151,0.40);border-radius:7px;"
                        f"font-size:11px;font-weight:700;padding:0 6px;}}"
                        f"QPushButton:hover{{background:rgba(61,220,151,0.25);}}"
                    )
                else:
                    self._btn_activate.setText("✓  Activer")
                    self._btn_activate.setStyleSheet(
                        f"QPushButton{{background:{CP['accent2']};color:#fff;"
                        f"border:none;border-radius:7px;"
                        f"font-size:11px;font-weight:700;padding:0 6px;}}"
                        f"QPushButton:hover{{background:#9d8fff;}}"
                        f"QPushButton:pressed{{background:{CP['accent2_dim']};}}"
                    )

    def _on_gen_fail(self, err):
        self._btn_gen.setEnabled(True)
        self._progress.setVisible(False)
        self._status.setText(f"Erreur : {err[:100]}")

    def _show_fullsize(self):
        if not self._generated_images:
            return
        try:
            from ui.dialog_character import _FullscreenDialog
            entries = [{"portrait": p, "sheet": ""} for p in self._generated_images]
            dlg = _FullscreenDialog(
                self, entries, start_idx=self._preview_idx, active_idx=self._preview_idx,
            )
            dlg.setWindowTitle("Aperçu accessoire")
            dlg.exec()
            deleted = dlg.deleted_indices()
            if deleted:
                self._generated_images = [p for i, p in enumerate(self._generated_images)
                                           if i not in deleted]
                if not self._generated_images:
                    self._image_path = ""
                    self._preview.setPixmap(QPixmap())
                    self._preview.setText("Aucune image\ngénérée")
                    self._preview_idx = 0
                    self._refresh_preview_nav()
                    return
                self._preview_idx = min(self._preview_idx, len(self._generated_images) - 1)
            entry, _ = dlg.chosen_entry()
            if entry is not None:
                chosen_path = entry.get("portrait", "")
                if chosen_path and chosen_path in self._generated_images:
                    self._preview_idx = self._generated_images.index(chosen_path)
                    self._image_path  = chosen_path
            path = self._generated_images[self._preview_idx] if self._generated_images else ""
            if path:
                self._load_preview(path)
                if self._image_path not in self._generated_images:
                    self._image_path = path
            self._refresh_preview_nav()
        except Exception as _e:
            import traceback
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.critical(self, "Erreur aperçu",
                                 f"Impossible d'ouvrir la prévisualisation :\n{_e}\n\n{traceback.format_exc()}")

    def _load_preview(self, path):
        pix = QPixmap(path)
        if not pix.isNull():
            pix = pix.scaled(240, 240, Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                             Qt.TransformationMode.SmoothTransformation)
            pix = pix.copy((pix.width()-240)//2, (pix.height()-240)//2, 240, 240)
            self._preview.setPixmap(pix)
            self._preview.setText("")

    def _refresh_shots_list(self):
        while self._shots_lay.count():
            item = self._shots_lay.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        import core.storyboard as sb_api
        shots = sb_api.list_shots()
        if not shots:
            lbl = QLabel("Aucun plan dans le storyboard")
            lbl.setStyleSheet(f"color:{CP['text_dim']};font-size:10px;background:transparent;")
            self._shots_lay.addWidget(lbl)
            return
        self._shot_checks: dict[str, QCheckBox] = {}
        for shot in shots:
            sid  = shot.get("id", "")
            num  = shot.get("number", "?")
            name = shot.get("scene_title", "") or f"Plan {num}"
            _lbl = f"Plan {num} — {name}"
            if len(_lbl) > 45:
                _lbl = _lbl[:44] + "…"
            cb   = QCheckBox(_lbl)
            cb.setChecked(sid in self._assigned_shots)
            cb.setStyleSheet(
                f"QCheckBox{{color:{CP['text_secondary']};font-size:10px;background:transparent;}}"
                f"QCheckBox::indicator{{width:14px;height:14px;border:1px solid {CP['border_bright']};"
                f"border-radius:3px;background:{CP['bg3']};}}"
                f"QCheckBox::indicator:checked{{background:{CP['accent']};border-color:{CP['accent']};}}"
            )
            self._shot_checks[sid] = cb
            self._shots_lay.addWidget(cb)
        self._shots_lay.addStretch()

    def _refresh_sequences_list(self):
        while self._seqs_lay.count():
            item = self._seqs_lay.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        import core.storyboard as sb_api
        shots = sb_api.list_shots()
        seen: dict[int, str] = {}
        for shot in shots:
            seq_num = shot.get("seq_num", 1)
            if seq_num not in seen:
                seen[seq_num] = shot.get("seq_name", "") or ""
        if not seen:
            lbl = QLabel("Aucune séquence dans le storyboard")
            lbl.setStyleSheet(f"color:{CP['text_dim']};font-size:10px;background:transparent;")
            self._seqs_lay.addWidget(lbl)
            return
        self._seq_checks: dict[int, QCheckBox] = {}
        for seq_num in sorted(seen.keys()):
            seq_name = seen[seq_num]
            label = f"Séq. {seq_num}" + (f" — {seq_name}" if seq_name else "")
            cb = QCheckBox(label)
            cb.setChecked(seq_num in self._assigned_sequences)
            cb.setStyleSheet(
                f"QCheckBox{{color:{CP['text_secondary']};font-size:10px;background:transparent;}}"
                f"QCheckBox::indicator{{width:14px;height:14px;border:1px solid {CP['border_bright']};"
                f"border-radius:3px;background:{CP['bg3']};}}"
                f"QCheckBox::indicator:checked{{background:{CP['accent2']};border-color:{CP['accent2']};}}"
            )
            cb.stateChanged.connect(lambda state, sn=seq_num: self._on_seq_toggle(sn, state == 2))
            self._seq_checks[seq_num] = cb
            self._seqs_lay.addWidget(cb)
        self._seqs_lay.addStretch()

    def _on_seq_toggle(self, seq_num: int, checked: bool):
        import core.storyboard as sb_api
        for shot in sb_api.list_shots():
            if shot.get("seq_num") == seq_num:
                sid = shot.get("id", "")
                if hasattr(self, "_shot_checks") and sid in self._shot_checks:
                    self._shot_checks[sid].setChecked(checked)

    def _on_save(self):
        name = self._name.text().strip()
        if not name:
            QMessageBox.warning(self, "Nom manquant", "Entre le nom de l'accessoire.")
            return
        if hasattr(self, "_shot_checks"):
            self._assigned_shots = [sid for sid, cb in self._shot_checks.items() if cb.isChecked()]
        if hasattr(self, "_seq_checks"):
            self._assigned_sequences = [sn for sn, cb in self._seq_checks.items() if cb.isChecked()]
        data = dict(self._item)
        data.update({
            "name":                name,
            "category":            to_source(self._cat.currentText()),
            "prompt":              self._prompt.toPlainText().strip(),
            "image_path":          self._image_path,
            "generated_images":    self._generated_images,
            "ref_paths":           self._ref_paths,
            "assigned_shots":      self._assigned_shots,
            "assigned_sequences":  self._assigned_sequences,
            "accessory_style_key": self._style_combo.currentData() if hasattr(self, "_style_combo") else "",
            "ref_usage_key":       self._ref_usage_combo.currentData() if hasattr(self, "_ref_usage_combo") else "inspiration",
        })
        self._saved_data = acc_api.save_accessory(data)

        self.accept()

    def get_item(self):
        return self._saved_data
