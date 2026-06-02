import os
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame,
    QPushButton, QComboBox, QScrollArea, QCheckBox, QGridLayout,
    QTextEdit, QSlider, QProgressBar,
)
from PyQt6.QtCore import Qt, QTimer, QUrl
from core.i18n import translate
from PyQt6.QtGui import QDesktopServices
from ui.styles import CP
from ui.icons import load_icon
from ui.widgets import HelpBlock
from core.camera_data import (
    FILTERS_DATA,
    all_camera_brands, bodies_for_brand,
    all_optics_brands, series_for_brand,
    all_mic_categories, mics_for_category,
)
import core.camera_prefs as cam_prefs


def _label(text: str, size: int = 11, color: str | None = None, bold: bool = False) -> QLabel:
    lbl = QLabel(text)
    weight = "700;" if bold else "600;"
    lbl.setStyleSheet(
        f"color:{color or CP['text_secondary']};font-size:{size}px;"
        f"font-weight:{weight}background:transparent;border:none;"
    )
    return lbl


def _combo(items: list[str], placeholder: str = "") -> QComboBox:
    cb = QComboBox()
    if placeholder:
        cb.addItem(placeholder)
    cb.addItems(items)
    cb.setFixedHeight(36)
    cb.setStyleSheet(
        f"QComboBox{{background:{CP['bg3']};border:1px solid {CP['border']};"
        f"border-radius:6px;color:{CP['text_primary']};font-size:12px;padding:0 10px;}}"
        f"QComboBox:focus{{border-color:{CP['accent']};}}"
        f"QComboBox::drop-down{{border:none;width:20px;}}"
        f"QComboBox QAbstractItemView{{background:{CP['bg3']};border:1px solid {CP['border_bright']};"
        f"color:{CP['text_primary']};selection-background-color:{CP['accent_dim']};}}"
    )
    return cb


def _sep() -> QFrame:
    f = QFrame()
    f.setFixedHeight(1)
    f.setStyleSheet(f"background:{CP['border']};margin:4px 0;")
    return f


# ── Page Image & Son (caméra + micro fusionnés) ───────────────────────────────

class PageCamera(QWidget):

    def __init__(self):
        super().__init__()
        self.setStyleSheet(f"background:{CP['bg0']};")

        self._filter_checks: dict[str, QCheckBox] = {}

        self._autosave_timer = QTimer()
        self._autosave_timer.setSingleShot(True)
        self._autosave_timer.setInterval(400)
        self._autosave_timer.timeout.connect(self._autosave)

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        root.addWidget(self._build_topbar())

        sep = QFrame()
        sep.setFixedHeight(1)
        sep.setStyleSheet(f"background:{CP['border']};")
        root.addWidget(sep)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet("QScrollArea{background:transparent;border:none;}")

        container = QWidget()
        container.setStyleSheet("background:transparent;")
        lay = QVBoxLayout(container)
        lay.setContentsMargins(32, 28, 32, 40)
        lay.setSpacing(20)

        lay.addWidget(HelpBlock("Image & Son", [
            "▸ Bloc 1 — Réglages techniques : corps de caméra, optiques, filtres et microphone.",
            "  Ces préférences sont injectées dans les prompts Seedance pour guider le rendu visuel.",
            "▸ Bloc 2 — Sound Design : génère des ambiances sonores IA (Mirelo AI SFX 1.6 · $0.01/s).",
            "  L'audio généré est automatiquement importé dans le Media Pool de DaVinci Resolve.",
        ], CP))

        # ══════════════════════════════════════════════════════════════════════
        # BLOC 1 — Réglages techniques (caméra, optiques, micro → prompts)
        # ══════════════════════════════════════════════════════════════════════
        bloc1 = QFrame()
        bloc1.setStyleSheet(
            f"QFrame{{background:{CP['bg1']};border:1px solid {CP['border']};"
            f"border-radius:12px;}}"
        )
        b1_lay = QVBoxLayout(bloc1)
        b1_lay.setContentsMargins(22, 18, 22, 18)
        b1_lay.setSpacing(14)

        # — En-tête bloc 1 ————————————————————————————————————————————————————
        b1_hdr = QHBoxLayout()
        b1_title = QLabel("Réglages techniques")
        b1_title.setStyleSheet(
            f"color:{CP['text_primary']};font-size:15px;font-weight:700;"
            f"background:transparent;border:none;"
        )
        b1_sub = QLabel("Corps de caméra · Optiques · Filtres · Microphone")
        b1_sub.setStyleSheet(
            f"color:{CP['text_dim']};font-size:10px;font-family:'Consolas',monospace;"
            f"letter-spacing:0.3px;background:transparent;border:none;"
        )
        b1_col = QVBoxLayout()
        b1_col.setSpacing(3)
        b1_col.addWidget(b1_title)
        b1_col.addWidget(b1_sub)
        b1_hdr.addLayout(b1_col, 1)
        b1_lay.addLayout(b1_hdr)

        b1_desc = QLabel(
            "Ces paramètres s'injectent automatiquement dans les prompts de génération vidéo "
            "pour reproduire le rendu d'un équipement spécifique — corps de caméra, gamme "
            "d'optiques, filtres et microphone du tournage."
        )
        b1_desc.setWordWrap(True)
        b1_desc.setStyleSheet(
            f"color:{CP['text_secondary']};font-size:11px;"
            f"background:transparent;border:none;"
        )
        b1_lay.addWidget(b1_desc)

        b1_lay.addWidget(_sep())

        # — Corps de caméra ————————————————————————————————————————————————————
        b1_lay.addWidget(_label("CORPS DE CAMÉRA", size=10, color=CP["text_dim"], bold=True))

        cam_grid = QGridLayout()
        cam_grid.setSpacing(12)
        cam_grid.addWidget(_label("Marque"), 0, 0)
        cam_grid.addWidget(_label("Modèle"), 0, 1)

        self._cb_cam_brand = _combo(all_camera_brands(), "— Choisir la marque —")
        self._cb_cam_body  = _combo([], "— Choisir le modèle —")
        self._cb_cam_brand.currentTextChanged.connect(self._on_cam_brand_changed)
        self._cb_cam_body.currentTextChanged.connect(self._schedule_save)

        cam_grid.addWidget(self._cb_cam_brand, 1, 0)
        cam_grid.addWidget(self._cb_cam_body,  1, 1)
        b1_lay.addLayout(cam_grid)

        # — Optiques ———————————————————————————————————————————————————————————
        b1_lay.addWidget(_sep())
        b1_lay.addWidget(_label("OPTIQUES", size=10, color=CP["text_dim"], bold=True))

        opt_grid = QGridLayout()
        opt_grid.setSpacing(12)
        opt_grid.addWidget(_label("Marque"), 0, 0)
        opt_grid.addWidget(_label("Série"), 0, 1)

        self._cb_opt_brand  = _combo(all_optics_brands(), "— Choisir la marque —")
        self._cb_opt_series = _combo([], "— Choisir la série —")
        self._cb_opt_brand.currentTextChanged.connect(self._on_opt_brand_changed)
        self._cb_opt_series.currentTextChanged.connect(self._schedule_save)

        opt_grid.addWidget(self._cb_opt_brand,  1, 0)
        opt_grid.addWidget(self._cb_opt_series, 1, 1)
        b1_lay.addLayout(opt_grid)

        # — Filtres (dépliable) ————————————————————————————————————————————————
        b1_lay.addWidget(_sep())

        filter_header = QHBoxLayout()
        filter_header.setSpacing(0)
        self._btn_filter_toggle = QPushButton("▶  FILTRES")
        self._btn_filter_toggle.setCheckable(True)
        self._btn_filter_toggle.setChecked(False)
        self._btn_filter_toggle.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_filter_toggle.setStyleSheet(
            f"QPushButton{{background:transparent;color:{CP['text_dim']};"
            f"font-size:10px;font-weight:700;letter-spacing:0.5px;"
            f"border:none;text-align:left;padding:0;}}"
            f"QPushButton:hover{{color:{CP['text_secondary']};}}"
        )
        self._btn_filter_toggle.toggled.connect(self._on_filter_toggle)
        self._filter_count_lbl = QLabel("")
        self._filter_count_lbl.setStyleSheet(
            f"color:{CP['text_dim']};font-size:10px;background:transparent;border:none;"
        )
        filter_header.addWidget(self._btn_filter_toggle)
        filter_header.addSpacing(8)
        filter_header.addWidget(self._filter_count_lbl)
        filter_header.addStretch()
        b1_lay.addLayout(filter_header)

        self._filter_container = QWidget()
        self._filter_container.setStyleSheet("background:transparent;")
        self._filter_container.setVisible(False)
        self._filter_lay = QVBoxLayout(self._filter_container)
        self._filter_lay.setContentsMargins(0, 4, 0, 4)
        self._filter_lay.setSpacing(6)
        self._filter_lay.addWidget(_label(
            "Sélectionnez un ou plusieurs filtres utilisés sur ce tournage.",
            size=10, color=CP["text_dim"]
        ))
        self._build_filter_checkboxes()
        b1_lay.addWidget(self._filter_container)

        # — Microphone ————————————————————————————————————————————————————————
        b1_lay.addWidget(_sep())
        b1_lay.addWidget(_label("MICROPHONE", size=10, color=CP["text_dim"], bold=True))
        b1_lay.addWidget(_label(
            "Microphone principal du tournage — injecté dans les paramètres sonores des prompts.",
            size=10, color=CP["text_dim"]
        ))

        mic_grid = QGridLayout()
        mic_grid.setSpacing(12)
        mic_grid.addWidget(_label("Catégorie"), 0, 0)
        mic_grid.addWidget(_label("Modèle"), 0, 1)

        self._cb_mic_cat   = _combo(all_mic_categories(), "— Choisir la catégorie —")
        self._cb_mic_model = _combo([], "— Choisir le modèle —")
        self._cb_mic_cat.currentTextChanged.connect(self._on_mic_cat_changed)
        self._cb_mic_model.currentTextChanged.connect(self._schedule_save)

        mic_grid.addWidget(self._cb_mic_cat,   1, 0)
        mic_grid.addWidget(self._cb_mic_model, 1, 1)
        b1_lay.addLayout(mic_grid)

        # — Suffixe prompt preview ————————————————————————————————————————————
        b1_lay.addWidget(_sep())

        preview_row = QHBoxLayout()
        preview_row.setSpacing(10)
        preview_row.addWidget(_label("Suffixe Seedance généré :", size=10, color=CP["text_secondary"]))
        self._preview_lbl = QLabel("—")
        self._preview_lbl.setWordWrap(True)
        self._preview_lbl.setStyleSheet(
            f"color:{CP['accent']};font-size:10px;font-family:'Consolas',monospace;"
            f"background:rgba(78,205,196,0.06);border:1px solid {CP['accent_dim']};"
            f"border-radius:6px;padding:6px 10px;"
        )
        preview_row.addWidget(self._preview_lbl, 1)
        b1_lay.addLayout(preview_row)

        lay.addWidget(bloc1)

        # ══════════════════════════════════════════════════════════════════════
        # BLOC 2 — Sound Design (génération d'ambiances → import DaVinci)
        # ══════════════════════════════════════════════════════════════════════
        bloc2 = QFrame()
        bloc2.setStyleSheet(
            f"QFrame{{background:{CP['bg1']};border:1px solid {CP['border']};"
            f"border-radius:12px;}}"
        )
        b2_lay = QVBoxLayout(bloc2)
        b2_lay.setContentsMargins(22, 20, 22, 20)
        b2_lay.setSpacing(14)

        # — En-tête bloc 2 ————————————————————————————————————————————————————
        b2_hdr = QHBoxLayout()
        b2_icon = QLabel("🎵")
        b2_icon.setStyleSheet(
            "font-size:26px;background:transparent;border:none;"
        )
        b2_icon.setFixedWidth(38)
        b2_hdr.addWidget(b2_icon, 0, Qt.AlignmentFlag.AlignTop)

        b2_col = QVBoxLayout()
        b2_col.setSpacing(4)
        b2_title = QLabel("Sound Design")
        b2_title.setStyleSheet(
            f"color:{CP['accent2']};font-size:18px;font-weight:700;"
            f"background:transparent;border:none;"
        )
        b2_sub = QLabel("Génération d'ambiances sonores & bruitages IA")
        b2_sub.setStyleSheet(
            f"color:{CP['text_dim']};font-size:10px;font-family:'Consolas',monospace;"
            f"letter-spacing:0.3px;background:transparent;border:none;"
        )
        b2_col.addWidget(b2_title)
        b2_col.addWidget(b2_sub)
        b2_hdr.addLayout(b2_col, 1)

        badge_sfx = QLabel("SFX 1.6 · $0.01/s")
        badge_sfx.setStyleSheet(
            f"color:{CP['accent2']};font-size:9px;font-weight:700;font-family:'Consolas',monospace;"
            f"background:rgba(122,90,248,0.12);border:1px solid rgba(122,90,248,0.35);"
            f"border-radius:4px;padding:3px 8px;"
        )
        b2_hdr.addWidget(badge_sfx, 0, Qt.AlignmentFlag.AlignTop)

        b2_lay.addLayout(b2_hdr)

        b2_desc = QLabel(
            "Générez des sons d'atmosphère, d'ambiance et de bruitage réalistes à partir "
            "d'une simple description texte. Idéal pour enrichir votre montage : "
            "paysages sonores, ambiances intérieures, bruits de fond de scène.\n\n"
            "L'audio généré est automatiquement importé dans le Media Pool de DaVinci Resolve "
            "et prêt à être glissé sur votre timeline pour améliorer l'immersion de votre animatique."
        )
        b2_desc.setWordWrap(True)
        b2_desc.setStyleSheet(
            f"color:{CP['text_secondary']};font-size:11px;line-height:1.5;"
            f"background:transparent;border:none;"
        )
        b2_lay.addWidget(b2_desc)

        b2_lay.addWidget(_sep())

        self._sfx_prompt = QTextEdit()
        self._sfx_prompt.setPlaceholderText(
            "Décrivez l'ambiance à générer…\n"
            "ex: Forêt la nuit, grillons, vent léger dans les feuilles\n"
            "ex: Café animé, conversations lointaines, tasses qui tintent\n"
            "ex: Pluie sur un toit en tôle, tonnerre au loin"
        )
        self._sfx_prompt.setMinimumHeight(90)
        self._sfx_prompt.setMaximumHeight(130)
        self._sfx_prompt.setStyleSheet(
            f"QTextEdit{{background:{CP['bg3']};border:1px solid {CP['border']};"
            f"border-radius:8px;color:{CP['text_primary']};font-size:12px;"
            f"font-family:'Segoe UI',sans-serif;padding:8px;}}"
            f"QTextEdit:focus{{border-color:{CP['accent2']};}}"
        )
        b2_lay.addWidget(self._sfx_prompt)

        sfx_dur_row = QHBoxLayout()
        sfx_dur_row.setSpacing(12)
        self._sfx_dur_lbl = _label("Durée : 10 s  (~$0.10)", size=11, color=CP["text_secondary"])
        self._sfx_dur_slider = QSlider(Qt.Orientation.Horizontal)
        self._sfx_dur_slider.setMinimum(3)
        self._sfx_dur_slider.setMaximum(30)
        self._sfx_dur_slider.setValue(10)
        self._sfx_dur_slider.setStyleSheet(
            f"QSlider::groove:horizontal{{height:4px;background:{CP['bg3']};border-radius:2px;}}"
            f"QSlider::handle:horizontal{{width:14px;height:14px;"
            f"background:{CP['accent2']};border-radius:7px;margin:-5px 0;}}"
            f"QSlider::sub-page:horizontal{{background:rgba(122,90,248,0.45);border-radius:2px;}}"
        )
        self._sfx_dur_slider.valueChanged.connect(self._on_sfx_dur_changed)
        sfx_dur_row.addWidget(self._sfx_dur_lbl)
        sfx_dur_row.addWidget(self._sfx_dur_slider, 1)
        b2_lay.addLayout(sfx_dur_row)

        self._sfx_progress = QProgressBar()
        self._sfx_progress.setFixedHeight(4)
        self._sfx_progress.setTextVisible(False)
        self._sfx_progress.setRange(0, 100)
        self._sfx_progress.setValue(0)
        self._sfx_progress.setVisible(False)
        self._sfx_progress.setStyleSheet(
            f"QProgressBar{{background:{CP['bg3']};border-radius:2px;border:none;}}"
            f"QProgressBar::chunk{{background:{CP['accent2']};border-radius:2px;}}"
        )
        b2_lay.addWidget(self._sfx_progress)

        self._sfx_status_lbl = _label("", size=10, color=CP["text_dim"])
        self._sfx_status_lbl.setVisible(False)
        b2_lay.addWidget(self._sfx_status_lbl)

        sfx_btn_row = QHBoxLayout()
        sfx_btn_row.addStretch()
        self._btn_sfx = QPushButton("🎵  Générer l'ambiance")
        self._btn_sfx.setFixedHeight(42)
        self._btn_sfx.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_sfx.setStyleSheet(
            f"QPushButton{{background:{CP['accent2']};color:#ffffff;"
            f"border:none;border-radius:8px;font-size:12px;font-weight:700;padding:0 20px;}}"
            f"QPushButton:hover{{background:#9a7aff;}}"
            f"QPushButton:disabled{{background:{CP['bg3']};color:{CP['text_dim']};}}"
        )
        self._btn_sfx.clicked.connect(self._on_sfx_generate)
        sfx_btn_row.addWidget(self._btn_sfx)
        b2_lay.addLayout(sfx_btn_row)

        self._sfx_result_lbl = _label("", size=10, color=CP["accent2"])
        self._sfx_result_lbl.setVisible(False)
        b2_lay.addWidget(self._sfx_result_lbl)

        self._sfx_worker = None

        # bloc2 (Sound Design) temporairement masqué — API SFX instable
        # lay.addWidget(bloc2)
        lay.addStretch()

        scroll.setWidget(container)
        root.addWidget(scroll, 1)

        self._load_prefs()

    def _build_topbar(self):
        bar = QWidget()
        bar.setFixedHeight(60)
        bar.setStyleSheet(f"background:{CP['bg1']};")
        lay = QHBoxLayout(bar)
        lay.setContentsMargins(32, 0, 32, 0)
        lay.setSpacing(10)

        _ico = QLabel()
        _ico.setFixedSize(28, 28)
        _ico.setAlignment(Qt.AlignmentFlag.AlignCenter)
        _ico.setStyleSheet("background:transparent;")
        _ico_pix = load_icon("camera.png", 28)
        if not _ico_pix.isNull():
            _ico.setPixmap(_ico_pix)
        lay.addWidget(_ico)

        title = QLabel("Image & Son")
        title.setStyleSheet(
            f"color:{CP['text_primary']};font-size:20px;font-weight:700;background:transparent;"
        )
        lay.addWidget(title)
        lay.addStretch()

        self._save_lbl = QLabel("")
        self._save_lbl.setStyleSheet(
            f"color:{CP['text_dim']};font-size:10px;font-family:'Consolas',monospace;"
            f"background:transparent;border:none;"
        )
        lay.addWidget(self._save_lbl)
        return bar

    def _build_filter_checkboxes(self):
        while self._filter_lay.count() > 1:
            it = self._filter_lay.takeAt(1)
            if it.widget():
                it.widget().deleteLater()
        self._filter_checks.clear()

        for brand, flist in FILTERS_DATA.items():
            brand_lbl = _label(brand, size=10, color=CP["text_secondary"], bold=True)
            self._filter_lay.addWidget(brand_lbl)

            row_w = QWidget()
            row_w.setStyleSheet("background:transparent;")
            row_lay = QHBoxLayout(row_w)
            row_lay.setContentsMargins(8, 0, 0, 0)
            row_lay.setSpacing(14)

            for fname in flist:
                key = f"{brand} — {fname}"
                cb = QCheckBox(fname)
                cb.setStyleSheet(
                    f"QCheckBox{{color:{CP['text_primary']};font-size:11px;background:transparent;}}"
                    f"QCheckBox::indicator{{width:14px;height:14px;border-radius:3px;"
                    f"border:1px solid {CP['border_bright']};}}"
                    f"QCheckBox::indicator:checked{{background:{CP['accent']};border-color:{CP['accent']};}}"
                )
                cb.stateChanged.connect(self._on_filter_changed)
                self._filter_checks[key] = cb
                row_lay.addWidget(cb)
            row_lay.addStretch()
            self._filter_lay.addWidget(row_w)

    def _on_filter_toggle(self, checked: bool):
        self._filter_container.setVisible(checked)
        self._btn_filter_toggle.setText("▼  FILTRES" if checked else "▶  FILTRES")

    def _on_filter_changed(self):
        count = sum(1 for cb in self._filter_checks.values() if cb.isChecked())
        self._filter_count_lbl.setText(f"({count} sélectionné{'s' if count > 1 else ''})" if count else "")
        self._update_preview()
        self._schedule_save()

    def _on_cam_brand_changed(self, brand: str):
        self._cb_cam_body.blockSignals(True)
        self._cb_cam_body.clear()
        self._cb_cam_body.addItem("— Choisir le modèle —")
        if brand and not brand.startswith("—"):
            self._cb_cam_body.addItems(bodies_for_brand(brand))
        self._cb_cam_body.blockSignals(False)
        self._update_preview()
        self._schedule_save()

    def _on_opt_brand_changed(self, brand: str):
        self._cb_opt_series.blockSignals(True)
        self._cb_opt_series.clear()
        self._cb_opt_series.addItem("— Choisir la série —")
        if brand and not brand.startswith("—"):
            self._cb_opt_series.addItems(series_for_brand(brand))
        self._cb_opt_series.blockSignals(False)
        self._update_preview()
        self._schedule_save()

    def _on_mic_cat_changed(self, cat: str):
        self._cb_mic_model.blockSignals(True)
        self._cb_mic_model.clear()
        self._cb_mic_model.addItem("— Choisir le modèle —")
        if cat and not cat.startswith("—"):
            self._cb_mic_model.addItems(mics_for_category(cat))
        self._cb_mic_model.blockSignals(False)
        self._schedule_save()

    def _selected_filters(self) -> list[str]:
        return [fname.split(" — ", 1)[1] for fname, cb in self._filter_checks.items()
                if cb.isChecked()]

    def _update_preview(self):
        from core.camera_data import build_camera_prompt_suffix
        suffix = build_camera_prompt_suffix(self._collect())
        self._preview_lbl.setText(suffix or "—")

    def _collect(self) -> dict:
        cam_brand   = self._cb_cam_brand.currentText()
        cam_body    = self._cb_cam_body.currentText()
        opt_brand   = self._cb_opt_brand.currentText()
        opt_series  = self._cb_opt_series.currentText()
        mic_cat     = self._cb_mic_cat.currentText()
        mic_model   = self._cb_mic_model.currentText()
        return {
            "camera_brand":  "" if cam_brand.startswith("—")  else cam_brand,
            "camera_body":   "" if cam_body.startswith("—")   else cam_body,
            "optics_brand":  "" if opt_brand.startswith("—")  else opt_brand,
            "optics_series": "" if opt_series.startswith("—") else opt_series,
            "filters":       self._selected_filters(),
            "mic_category":  "" if mic_cat.startswith("—")    else mic_cat,
            "mic_model":     "" if mic_model.startswith("—")  else mic_model,
        }

    def _load_prefs(self):
        p = cam_prefs.get_camera_prefs()

        # Cam brand/body
        brand = p.get("camera_brand", "")
        if brand:
            idx = self._cb_cam_brand.findText(brand)
            if idx >= 0:
                self._cb_cam_brand.setCurrentIndex(idx)
                self._on_cam_brand_changed(brand)
                body = p.get("camera_body", "")
                if body:
                    bidx = self._cb_cam_body.findText(body)
                    if bidx >= 0:
                        self._cb_cam_body.setCurrentIndex(bidx)

        # Optics
        obrand = p.get("optics_brand", "")
        if obrand:
            idx = self._cb_opt_brand.findText(obrand)
            if idx >= 0:
                self._cb_opt_brand.setCurrentIndex(idx)
                self._on_opt_brand_changed(obrand)
                series = p.get("optics_series", "")
                if series:
                    sidx = self._cb_opt_series.findText(series)
                    if sidx >= 0:
                        self._cb_opt_series.setCurrentIndex(sidx)

        # Filters
        saved_filters = p.get("filters", [])
        for fname, cb in self._filter_checks.items():
            cb.blockSignals(True)
            cb.setChecked(fname.split(" — ", 1)[1] in saved_filters)
            cb.blockSignals(False)
        count = len(saved_filters)
        self._filter_count_lbl.setText(
            f"({count} sélectionné{'s' if count > 1 else ''})" if count else ""
        )

        # Mic
        cat = p.get("mic_category", "")
        if cat:
            idx = self._cb_mic_cat.findText(cat)
            if idx >= 0:
                self._cb_mic_cat.setCurrentIndex(idx)
                self._on_mic_cat_changed(cat)
                model = p.get("mic_model", "")
                if model:
                    midx = self._cb_mic_model.findText(model)
                    if midx >= 0:
                        self._cb_mic_model.setCurrentIndex(midx)

        self._update_preview()

    def _schedule_save(self, *_):
        self._autosave_timer.start()

    def _autosave(self):
        existing = cam_prefs.get_camera_prefs()
        existing.update(self._collect())
        cam_prefs.save_camera_prefs(existing)
        self._save_lbl.setText("Sauvegardé ✓")
        QTimer.singleShot(2000, lambda: self._save_lbl.setText(""))

    def refresh(self):
        self._load_prefs()

    # ── SFX 1.6 ──────────────────────────────────────────────────────────────

    def _on_sfx_dur_changed(self, v: int):
        self._sfx_dur_lbl.setText(f"Durée : {v} s  (~${v * 0.01:.2f})")

    def _on_sfx_generate(self):
        text = self._sfx_prompt.toPlainText().strip()
        if not text:
            return
        from api.tts import SFX1Worker
        dur   = self._sfx_dur_slider.value()
        label = text[:30].strip().replace(" ", "_")
        self._sfx_worker = SFX1Worker(text, duration=float(dur), label=label)
        self._sfx_worker.progress.connect(self._on_sfx_progress)
        self._sfx_worker.finished.connect(self._on_sfx_done)
        self._sfx_worker.failed.connect(self._on_sfx_failed)
        self._btn_sfx.setEnabled(False)
        self._sfx_progress.setVisible(True)
        self._sfx_progress.setValue(0)
        self._sfx_status_lbl.setVisible(True)
        self._sfx_status_lbl.setText("Initialisation…")
        self._sfx_result_lbl.setVisible(False)
        self._sfx_worker.start()

    def _on_sfx_progress(self, pct: int, msg: str):
        self._sfx_progress.setValue(pct)
        self._sfx_status_lbl.setText(translate(msg))

    def _on_sfx_done(self, path: str):
        self._btn_sfx.setEnabled(True)
        self._sfx_progress.setValue(100)
        if path and os.path.isfile(path):
            self._sfx_result_lbl.setText(f"✓  {os.path.basename(path)}")
            self._sfx_result_lbl.setVisible(True)
            self._sfx_result_lbl.mousePressEvent = lambda _: QDesktopServices.openUrl(
                QUrl.fromLocalFile(os.path.dirname(path))
            )
            self._sfx_result_lbl.setCursor(Qt.CursorShape.PointingHandCursor)
            # Import auto dans DaVinci (silencieux si non connecté)
            try:
                from davinci.importer import import_audio_to_bin
                imported = import_audio_to_bin(path)
            except Exception:
                imported = False
            if imported:
                self._sfx_status_lbl.setText("✓  Ambiance générée · importée dans DaVinci")
            else:
                self._sfx_status_lbl.setText("✓  Ambiance générée")
        else:
            self._sfx_status_lbl.setText("✓  Terminé (mode mock — aucune clé fal.ai)")

    def _on_sfx_failed(self, err: str):
        self._btn_sfx.setEnabled(True)
        self._sfx_progress.setVisible(False)
        self._sfx_status_lbl.setText(f"⚠  {err[:120]}")
