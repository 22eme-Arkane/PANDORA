import os
from datetime import datetime
from PyQt6.QtWidgets import (
    QScrollArea, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QPushButton, QMessageBox, QCheckBox, QComboBox, QFrame, QLabel, QDialog, QLineEdit,
    QSlider, QSpinBox,
)
from PyQt6.QtCore import Qt, pyqtSignal, QThread
from PyQt6.QtGui import QPixmap, QIntValidator
from ui.styles import C
from ui.widgets import section_label, combo, toggle_row, prompt_block, ProgressBlock, HelpBlock, show_api_error
from core.history import save_to_history
from core.config import get_output_dir
from core.worker import GenerationWorker, abandon_thread
from core.i18n import translate
from api.enhance import EnhanceWorker
from davinci.bridge import resolve
from davinci.importer import import_result
import core.casting as casting_api
import core.accessories as acc_api
import core.vehicles as veh_api
import core.storyboard as sb_api

# ── Catalogue moteurs de génération — classement ELO Avril 2026 ──────────────
# Ordre : du plus performant au moins performant (ELO vidéo April 2026)

_ENGINES = [
    ("Seedance 2.0  (recommandée)", "seedance-2.0"),        # Défaut — optimisé dans Pandora
    ("Happy Horse 1.0  (prochainement)", "happy-horse-1.0"), # n°1 ELO — intégration en cours
    ("Kling v3 Pro  (prochainement)",    "kling-v3-pro"),    # n°3 ELO — 1080p + audio natif
    ("Kling O3 4K  (prochainement)",     "kling-o3-4k"),     # Variante 4K Kling
    ("Veo 3.1  (prochainement)",         "veo-3.1"),         # Google — audio natif
    ("Sora 2  (prochainement)",          "sora-2"),          # OpenAI — 1080p
    ("PixVerse v6  (prochainement)",     "pixverse-v6"),     # PixVerse — flexible
    ("Seedance 2.0 Fast",               "seedance-2.0-fast"), # Rapide — qualité réduite
]

_SEEDANCE_ENGINES    = {"seedance-2.0", "seedance-2.0-fast"}
_FIXED_RES_ENGINES   = {"veo-3.1", "kling-v3-pro", "kling-o3-4k", "sora-2"}
_FIXED_RATIO_ENGINES = {"veo-3.1", "kling-v3-pro", "kling-o3-4k"}
# Moteurs sans support natif d'images de référence (fallback texte uniquement)
_TEXT_FALLBACK_ENGINES = {"kling-v3-pro", "kling-o3-4k", "veo-3.1", "sora-2"}
_ENGINE_RES_FORCED   = {
    "veo-3.1":      "1080p",
    "kling-v3-pro": "1080p",
    "kling-o3-4k":  "4K",
    "sora-2":       "1080p",
}
# Résolutions disponibles par moteur — (label affiché, valeur API), premier = défaut
_ENGINE_RESOLUTIONS = {
    "seedance-2.0":      [("1080p  (~$0.60/s)", "1080p"), ("720p  (~$0.30/s)", "720p"), ("480p  (~$0.16/s)", "480p")],
    "seedance-2.0-fast": [("480p  (~$0.09/s)", "480p"),  ("720p  (~$0.18/s)", "720p")],
    "kling-v3-pro":      [("1080p", "1080p")],
    "kling-o3-4k":       [("4K",    "4K")],
    "veo-3.1":           [("1080p", "1080p")],
    "sora-2":            [("1080p", "1080p")],
    "pixverse-v6":       [("1080p  (~$0.115/s)", "1080p"), ("720p  (~$0.075/s)", "720p"), ("480p  (~$0.025/s)", "480p")],
    "happy-horse-1.0":   [("1080p  (~$0.28/s)", "1080p"),  ("720p  (~$0.14/s)", "720p")],
}
# Moteurs disponibles dans le tab DaVinci Edit (workflow testé et validé uniquement)
_DAVINCI_ENGINES = [e for e in _ENGINES if e[1] in _SEEDANCE_ENGINES]


def _make_ext_worker(model: str, params: dict):
    from api.video_engines import (
        Veo3Worker, KlingWorker, KlingO3Worker,
        HappyHorseWorker, PixVerseV6Worker, Sora2Worker,
    )
    p = dict(params)
    p.setdefault("mode", "t2v")
    mapping = {
        "veo-3.1":         Veo3Worker,
        "kling-v3-pro":    KlingWorker,
        "kling-o3-4k":     KlingO3Worker,
        "happy-horse-1.0": HappyHorseWorker,
        "pixverse-v6":     PixVerseV6Worker,
        "sora-2":          Sora2Worker,
    }
    cls = mapping.get(model)
    return cls(p) if cls else None


def _norm_ext_result(r: dict, prompt: str = "") -> dict:
    """Normalise le résultat d'un worker externe au format attendu par les onglets."""
    out = dict(r)
    out.setdefault("video_url", out.get("url", ""))
    out.setdefault("prompt", prompt)
    out.setdefault("seed", 0)
    out.setdefault("ref_images_attempted", 0)
    out.setdefault("ref_images_sent", 0)
    out.setdefault("gcs_blocked", False)
    return out
import core.decors as dec_api
import core.camera_prefs as cam_prefs
from core.camera_data import build_camera_prompt_suffix


# ── Thumb card ────────────────────────────────────────────────────────────────

class _ThumbCard(QFrame):
    toggled = pyqtSignal(bool)

    _SZ  = 80
    _IMG = 56

    def __init__(self, item_id: str, name: str, image_path: str = "", badge: str = "?",
                 overlay_text: str = ""):
        super().__init__()
        self._id       = item_id
        self._selected = False
        self.setFixedSize(self._SZ, self._SZ + 22)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(4, 4, 4, 4)
        lay.setSpacing(3)
        lay.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self._img = QLabel()
        self._img.setFixedSize(self._IMG, self._IMG)
        self._img.setAlignment(Qt.AlignmentFlag.AlignCenter)
        if image_path and os.path.isfile(image_path):
            pix = QPixmap(image_path).scaled(
                self._IMG, self._IMG,
                Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                Qt.TransformationMode.SmoothTransformation,
            )
            pix = pix.copy(
                (pix.width()  - self._IMG) // 2,
                (pix.height() - self._IMG) // 2,
                self._IMG, self._IMG,
            )
            self._img.setPixmap(pix)
            self._img.setStyleSheet("border-radius:6px;border:none;background:transparent;")
        else:
            self._img.setText(badge)
            self._img.setStyleSheet(
                f"background:{C['bg3']};border-radius:6px;border:none;"
                f"color:{C['text_dim']};font-size:20px;"
            )

        display = name if len(name) <= 10 else name[:9] + "…"
        self._lbl = QLabel(display)
        self._lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)

        lay.addWidget(self._img, 0, Qt.AlignmentFlag.AlignCenter)
        lay.addWidget(self._lbl, 0, Qt.AlignmentFlag.AlignCenter)

        if overlay_text:
            ov = QLabel(overlay_text, self)
            ov.setAlignment(Qt.AlignmentFlag.AlignCenter)
            ov.setStyleSheet(
                "background:rgba(0,0,0,0.72);color:#fff;"
                "font-size:7px;font-weight:800;font-family:'Consolas',monospace;"
                "border-radius:3px;padding:2px 4px;border:none;"
            )
            ov.adjustSize()
            ov.move(4, 4)
            ov.raise_()

        self._apply_style()

    def _apply_style(self):
        if self._selected:
            self.setStyleSheet(
                f"QFrame{{background:rgba(124,107,255,0.16);"
                f"border:2px solid {C['accent']};border-radius:10px;}}"
            )
            self._lbl.setStyleSheet(
                f"color:{C['accent']};font-size:9px;font-weight:700;background:transparent;"
            )
        else:
            self.setStyleSheet(
                f"QFrame{{background:{C['bg2']};"
                f"border:1px solid rgba(124,107,255,0.22);border-radius:10px;}}"
                f"QFrame:hover{{background:{C['bg3']};"
                f"border:1px solid rgba(124,107,255,0.58);}}"
            )
            self._lbl.setStyleSheet(
                f"color:{C['text_secondary']};font-size:9px;background:transparent;"
            )

    def set_selected(self, v: bool):
        self._selected = v
        self._apply_style()

    def is_selected(self) -> bool:
        return self._selected

    def item_id(self) -> str:
        return self._id

    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            self._selected = not self._selected
            self._apply_style()
            self.toggled.emit(self._selected)


# ── Casting selector ──────────────────────────────────────────────────────────

class CastingSelector(QWidget):
    context_changed = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self._selected_char_ids: set[str]       = set()
        self._char_data_map:     dict[str, dict] = {}
        self._char_cards:        dict[str, _ThumbCard] = {}
        self._item_cards:        dict[str, _ThumbCard] = {}
        self._items_meta:        dict[str, dict]        = {}
        self._selected_items:    set[str]               = set()
        self._vehicle_cards:     dict[str, _ThumbCard] = {}
        self._vehicles_meta:     dict[str, dict]        = {}
        self._selected_vehicles: set[str]               = set()
        self._decor_cards:       dict[str, _ThumbCard] = {}
        self._decors_meta:       dict[str, dict]        = {}
        self._selected_decor_id: str | None             = None

        # Active shot context for auto-select & warnings
        self._active_shot: dict | None = None

        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(4)

        # ── Helper: crée un en-tête collapsible ───────────────────────────────
        def _section_toggle(title: str) -> tuple:
            btn = QPushButton(f"▶  {title}")
            btn.setCheckable(True)
            btn.setChecked(False)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setStyleSheet(
                f"QPushButton{{background:transparent;color:{C['text_secondary']};"
                f"font-size:10px;font-weight:700;letter-spacing:0.3px;"
                f"border:none;text-align:left;padding:2px 0;}}"
                f"QPushButton:hover{{color:{C['text_primary']};}}"
            )
            content = QWidget()
            content.setVisible(False)
            content.setStyleSheet("background:transparent;")
            def _toggle(checked, b=btn, c=content, t=title):
                c.setVisible(checked)
                b.setText(f"{'▼' if checked else '▶'}  {t}")
            btn.toggled.connect(_toggle)
            return btn, content

        _cb_ss = (
            f"QCheckBox{{color:{C['text_dim']};font-size:9px;background:transparent;"
            f"spacing:3px;}}"
            f"QCheckBox:hover{{color:{C['text_secondary']};}}"
            f"QCheckBox::indicator{{width:11px;height:11px;border:1px solid {C['border']};"
            f"border-radius:2px;background:{C['bg3']};}}"
            f"QCheckBox::indicator:checked{{background:{C['accent_dim']};"
            f"border-color:{C['accent']};}}"
        )

        # ── Characters section ────────────────────────────────────────────────
        self._char_toggle, char_content = _section_toggle("Casting")
        self._no_char_ref_cb = QCheckBox("⊘ Ne pas envoyer")
        self._no_char_ref_cb.setToolTip("Exclure les images de personnages des références visuelles")
        self._no_char_ref_cb.setStyleSheet(_cb_ss)
        _char_hrow = QHBoxLayout()
        _char_hrow.setContentsMargins(0, 0, 0, 0)
        _char_hrow.setSpacing(6)
        _char_hrow.addWidget(self._char_toggle)
        _char_hrow.addWidget(self._no_char_ref_cb)
        _char_hrow.addStretch()
        lay.addLayout(_char_hrow)

        self._char_inner = QWidget()
        self._char_inner.setStyleSheet("background:transparent;")
        self._char_hbox = QHBoxLayout(self._char_inner)
        self._char_hbox.setContentsMargins(0, 0, 8, 0)
        self._char_hbox.setSpacing(8)
        self._char_hbox.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)

        char_scroll = QScrollArea()
        char_scroll.setWidget(self._char_inner)
        char_scroll.setWidgetResizable(True)
        char_scroll.setFixedHeight(116)
        char_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        char_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        char_scroll.setStyleSheet("QScrollArea{background:transparent;border:none;}")
        char_content_lay = QVBoxLayout(char_content)
        char_content_lay.setContentsMargins(0, 0, 0, 0)
        char_content_lay.setSpacing(0)
        char_content_lay.addWidget(char_scroll)
        lay.addWidget(char_content)

        # ── Items section (accessories) ───────────────────────────────────────
        self._items_toggle, items_content = _section_toggle("Accessoires")
        self._no_item_ref_cb = QCheckBox("⊘ Ne pas envoyer")
        self._no_item_ref_cb.setToolTip("Exclure les images d'accessoires des références visuelles")
        self._no_item_ref_cb.setStyleSheet(_cb_ss)
        _items_hrow = QHBoxLayout()
        _items_hrow.setContentsMargins(0, 0, 0, 0)
        _items_hrow.setSpacing(6)
        _items_hrow.addWidget(self._items_toggle)
        _items_hrow.addWidget(self._no_item_ref_cb)
        _items_hrow.addStretch()
        lay.addLayout(_items_hrow)

        self._items_inner = QWidget()
        self._items_inner.setStyleSheet("background:transparent;")
        self._items_hbox = QHBoxLayout(self._items_inner)
        self._items_hbox.setContentsMargins(0, 0, 8, 0)
        self._items_hbox.setSpacing(8)
        self._items_hbox.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)

        items_scroll = QScrollArea()
        items_scroll.setWidget(self._items_inner)
        items_scroll.setWidgetResizable(True)
        items_scroll.setFixedHeight(116)
        items_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        items_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        items_scroll.setStyleSheet("QScrollArea{background:transparent;border:none;}")
        items_content_lay = QVBoxLayout(items_content)
        items_content_lay.setContentsMargins(0, 0, 0, 0)
        items_content_lay.setSpacing(0)
        items_content_lay.addWidget(items_scroll)
        lay.addWidget(items_content)

        # ── Vehicles section ──────────────────────────────────────────────────
        self._veh_toggle, veh_content = _section_toggle("Véhicules")
        self._no_veh_ref_cb = QCheckBox("⊘ Ne pas envoyer")
        self._no_veh_ref_cb.setToolTip("Exclure les images de véhicules des références visuelles")
        self._no_veh_ref_cb.setStyleSheet(_cb_ss)
        _veh_hrow = QHBoxLayout()
        _veh_hrow.setContentsMargins(0, 0, 0, 0)
        _veh_hrow.setSpacing(6)
        _veh_hrow.addWidget(self._veh_toggle)
        _veh_hrow.addWidget(self._no_veh_ref_cb)
        _veh_hrow.addStretch()
        lay.addLayout(_veh_hrow)

        self._veh_inner = QWidget()
        self._veh_inner.setStyleSheet("background:transparent;")
        self._veh_hbox = QHBoxLayout(self._veh_inner)
        self._veh_hbox.setContentsMargins(0, 0, 8, 0)
        self._veh_hbox.setSpacing(8)
        self._veh_hbox.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)

        veh_scroll = QScrollArea()
        veh_scroll.setWidget(self._veh_inner)
        veh_scroll.setWidgetResizable(True)
        veh_scroll.setFixedHeight(116)
        veh_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        veh_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        veh_scroll.setStyleSheet("QScrollArea{background:transparent;border:none;}")
        veh_content_lay = QVBoxLayout(veh_content)
        veh_content_lay.setContentsMargins(0, 0, 0, 0)
        veh_content_lay.setSpacing(0)
        veh_content_lay.addWidget(veh_scroll)
        lay.addWidget(veh_content)

        # ── Décors section ────────────────────────────────────────────────────
        self._decor_toggle, decor_content = _section_toggle("Décors")
        self._no_decor_ref_cb = QCheckBox("⊘ Ne pas envoyer")
        self._no_decor_ref_cb.setToolTip("Exclure l'image de décor des références visuelles")
        self._no_decor_ref_cb.setStyleSheet(_cb_ss)

        _decor_hrow = QHBoxLayout()
        _decor_hrow.setContentsMargins(0, 0, 0, 0)
        _decor_hrow.setSpacing(6)
        _decor_hrow.addWidget(self._decor_toggle)
        _decor_hrow.addWidget(self._no_decor_ref_cb)
        _decor_hrow.addStretch()
        lay.addLayout(_decor_hrow)

        self._decor_inner = QWidget()
        self._decor_inner.setStyleSheet("background:transparent;")
        self._decor_hbox = QHBoxLayout(self._decor_inner)
        self._decor_hbox.setContentsMargins(0, 0, 8, 0)
        self._decor_hbox.setSpacing(8)
        self._decor_hbox.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)

        decor_scroll = QScrollArea()
        decor_scroll.setWidget(self._decor_inner)
        decor_scroll.setWidgetResizable(True)
        decor_scroll.setFixedHeight(116)
        decor_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        decor_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        decor_scroll.setStyleSheet("QScrollArea{background:transparent;border:none;}")
        decor_content_lay = QVBoxLayout(decor_content)
        decor_content_lay.setContentsMargins(0, 0, 0, 0)
        decor_content_lay.setSpacing(4)
        decor_content_lay.addWidget(decor_scroll)

        # Checkbox "Mode ancré" — remplace l'ancien bouton isolé
        self._decor_mode_cb = QCheckBox(
            "🏛  Mode ancré — Seedance traite le décor comme un espace 3D réel "
            "(conserve l'architecture et les angles du lieu)"
        )
        self._decor_mode_cb.setChecked(True)  # ancré par défaut
        self._decor_mode_cb.setStyleSheet(_cb_ss)
        self._decor_mode_cb.toggled.connect(self._on_decor_mode_toggled)
        decor_content_lay.addWidget(self._decor_mode_cb)

        lay.addWidget(decor_content)

        # ── Context summary ───────────────────────────────────────────────────
        self._ctx_lbl = QLabel("")
        self._ctx_lbl.setStyleSheet(
            f"color:{C['accent']};font-size:9px;"
            f"font-family:'Consolas',monospace;background:transparent;"
        )
        self._ctx_lbl.setWordWrap(True)
        lay.addWidget(self._ctx_lbl)

        self._load_chars()
        self._load_vehicles()
        self._load_decors()
        self._update_items_placeholder()

    # ── Load ──────────────────────────────────────────────────────────────────

    def _load_chars(self):
        while self._char_hbox.count():
            it = self._char_hbox.takeAt(0)
            if it.widget():
                it.widget().deleteLater()
        self._char_cards.clear()

        chars = casting_api.list_characters()
        if not chars:
            lbl = QLabel("Aucun personnage — crée-en un dans Castings.")
            lbl.setStyleSheet(f"color:{C['text_dim']};font-size:10px;background:transparent;")
            self._char_hbox.addWidget(lbl)
            self._char_hbox.addStretch()
            return

        for char in chars:
            card = _ThumbCard(
                char["id"],
                char.get("name", "?"),
                char.get("image_path", ""),
                "⊕",
            )
            card.toggled.connect(
                lambda sel, cid=char["id"], cname=char.get("name",""):
                    self._on_char_toggled(cid, cname, sel)
            )
            self._char_cards[char["id"]] = card
            self._char_hbox.addWidget(card)
        self._char_hbox.addStretch()

    def _load_items(self, shot_acc_ids: set | None = None):
        while self._items_hbox.count():
            it = self._items_hbox.takeAt(0)
            if it.widget():
                it.widget().deleteLater()
        self._item_cards.clear()
        self._items_meta.clear()

        items: list[dict] = []
        seen_ids: set[str] = set()

        # Accessories linked to selected characters
        for char_data in self._char_data_map.values():
            acc_ids = char_data.get("accessory_ids", [])
            for acc in acc_api.list_accessories():
                if acc["id"] in acc_ids and acc["id"] not in seen_ids:
                    items.append({**acc, "_kind": "acc"})
                    seen_ids.add(acc["id"])

        # Accessories assigned to the shot (not necessarily linked to a character)
        if shot_acc_ids:
            all_accs = {a["id"]: a for a in acc_api.list_accessories()}
            for aid in shot_acc_ids:
                if aid not in seen_ids and aid in all_accs:
                    items.append({**all_accs[aid], "_kind": "acc"})
                    seen_ids.add(aid)

        if not items:
            if not self._char_data_map and not shot_acc_ids:
                self._update_items_placeholder()
            else:
                lbl = QLabel("Aucun accessoire assigné aux personnages sélectionnés.")
                lbl.setStyleSheet(f"color:{C['text_dim']};font-size:10px;background:transparent;")
                self._items_hbox.addWidget(lbl)
                self._items_hbox.addStretch()
            return

        for item in items:
            kind  = item.get("_kind", "acc")
            badge = "◈" if kind == "acc" else "✂"
            card  = _ThumbCard(
                item["id"],
                item.get("name", "?"),
                item.get("image_path", ""),
                badge,
            )
            iname = item.get("name", "")
            card.toggled.connect(
                lambda sel, iid=item["id"], iname=iname: self._on_item_toggled(iid, iname, sel)
            )
            self._item_cards[item["id"]]  = card
            self._items_meta[item["id"]] = item
            self._items_hbox.addWidget(card)
        self._items_hbox.addStretch()

    def _load_vehicles(self):
        while self._veh_hbox.count():
            it = self._veh_hbox.takeAt(0)
            if it.widget():
                it.widget().deleteLater()
        self._vehicle_cards.clear()
        self._vehicles_meta.clear()

        vehicles = veh_api.list_vehicles()
        if not vehicles:
            lbl = QLabel("Aucun véhicule — crée-en un dans Véhicules.")
            lbl.setStyleSheet(f"color:{C['text_dim']};font-size:10px;background:transparent;")
            self._veh_hbox.addWidget(lbl)
            self._veh_hbox.addStretch()
            return

        for veh in vehicles:
            card = _ThumbCard(
                veh["id"],
                veh.get("name", "?"),
                veh.get("image_path", ""),
                "🚗",
            )
            vname = veh.get("name", "")
            card.toggled.connect(
                lambda sel, vid=veh["id"], vname=vname: self._on_vehicle_toggled(vid, vname, sel)
            )
            self._vehicle_cards[veh["id"]] = card
            self._vehicles_meta[veh["id"]] = veh
            self._veh_hbox.addWidget(card)
        self._veh_hbox.addStretch()

    def _load_decors(self):
        while self._decor_hbox.count():
            it = self._decor_hbox.takeAt(0)
            if it.widget():
                it.widget().deleteLater()
        self._decor_cards.clear()
        self._decors_meta.clear()

        decors = dec_api.list_decors()
        if not decors:
            lbl = QLabel("Aucun décor — crée-en un dans Décors.")
            lbl.setStyleSheet(f"color:{C['text_dim']};font-size:10px;background:transparent;")
            self._decor_hbox.addWidget(lbl)
            self._decor_hbox.addStretch()
            return

        for decor in decors:
            card = _ThumbCard(
                decor["id"],
                decor.get("name", "?"),
                decor.get("image_path", ""),
                "◻",
            )
            dname = decor.get("name", "")
            card.toggled.connect(
                lambda sel, did=decor["id"], dname=dname: self._on_decor_toggled(did, dname, sel)
            )
            self._decor_cards[decor["id"]] = card
            self._decors_meta[decor["id"]] = decor
            self._decor_hbox.addWidget(card)
        self._decor_hbox.addStretch()

    def _on_decor_mode_toggled(self, checked: bool):
        pass  # état lu directement via get_decor_ref_free()

    def get_decor_ref_free(self) -> bool:
        return not self._decor_mode_cb.isChecked()

    def _update_items_placeholder(self):
        while self._items_hbox.count():
            it = self._items_hbox.takeAt(0)
            if it.widget():
                it.widget().deleteLater()
        lbl = QLabel("Sélectionne un personnage pour voir ses accessoires.")
        lbl.setStyleSheet(f"color:{C['text_dim']};font-size:10px;background:transparent;")
        self._items_hbox.addWidget(lbl)
        self._items_hbox.addStretch()

    # ── Warning dialog ────────────────────────────────────────────────────────

    def _warn_not_in_shot(self, entity_name: str, entity_type: str) -> bool:
        """Returns True if user confirms adding entity not present in shot."""
        dlg = QDialog(self)
        dlg.setWindowTitle("Entité absente du plan")
        dlg.setFixedSize(380, 180)
        lay = QVBoxLayout(dlg)
        lay.setContentsMargins(20, 18, 20, 18)
        lay.setSpacing(10)

        lbl = QLabel(
            f"<b>{entity_name}</b> ({entity_type}) n'est pas présent(e) dans ce plan.<br><br>"
            "Voulez-vous l'ajouter quand même ? Cela modifiera le contenu envoyé à Seedance."
        )
        lbl.setWordWrap(True)
        lbl.setStyleSheet(f"color:{C['text_primary']};font-size:11px;background:transparent;")
        lay.addWidget(lbl)
        lay.addStretch()

        btn_row = QHBoxLayout()
        btn_no = QPushButton("Non, annuler")
        btn_no.setFixedHeight(34)
        btn_no.setStyleSheet(
            f"QPushButton{{background:transparent;color:{C['text_secondary']};"
            f"border:1px solid {C['border']};border-radius:7px;font-size:11px;padding:0 14px;}}"
            f"QPushButton:hover{{background:{C['bg3']};}}"
        )
        btn_no.clicked.connect(dlg.reject)
        btn_yes = QPushButton("Oui, ajouter")
        btn_yes.setFixedHeight(34)
        btn_yes.setStyleSheet(
            f"QPushButton{{background:{C['accent']};color:#07080f;"
            f"border:none;border-radius:7px;font-size:11px;font-weight:700;padding:0 14px;}}"
            f"QPushButton:hover{{background:#6eded6;}}"
        )
        btn_yes.clicked.connect(dlg.accept)
        btn_row.addWidget(btn_no)
        btn_row.addStretch()
        btn_row.addWidget(btn_yes)
        lay.addLayout(btn_row)

        return dlg.exec() == QDialog.DialogCode.Accepted

    # ── Handlers ──────────────────────────────────────────────────────────────

    def _on_char_toggled(self, char_id: str, char_name: str, selected: bool):
        if selected and self._active_shot is not None:
            shot_chars = [n.lower() for n in self._active_shot.get("character_names", [])]
            if shot_chars and char_name.lower() not in shot_chars:
                if not self._warn_not_in_shot(char_name, "personnage"):
                    # Revert selection
                    card = self._char_cards.get(char_id)
                    if card:
                        card.set_selected(False)
                    return

        if selected:
            fresh = casting_api.get_character(char_id)
            self._selected_char_ids.add(char_id)
            self._char_data_map[char_id] = fresh or {}
        else:
            self._selected_char_ids.discard(char_id)
            self._char_data_map.pop(char_id, None)

        self._selected_items.clear()
        self._load_items()
        self._update_context()

    def _on_item_toggled(self, item_id: str, item_name: str, selected: bool):
        if selected and self._active_shot is not None:
            shot_items = [n.lower() for n in self._active_shot.get("accessory_names", [])]
            if shot_items and item_name.lower() not in shot_items:
                if not self._warn_not_in_shot(item_name, "accessoire"):
                    card = self._item_cards.get(item_id)
                    if card:
                        card.set_selected(False)
                    return

        if selected:
            self._selected_items.add(item_id)
        else:
            self._selected_items.discard(item_id)
        self._update_context()

    def _on_vehicle_toggled(self, veh_id: str, veh_name: str, selected: bool):
        if selected and self._active_shot is not None:
            shot_vehs = [n.lower() for n in self._active_shot.get("vehicle_names", [])]
            if shot_vehs and veh_name.lower() not in shot_vehs:
                if not self._warn_not_in_shot(veh_name, "véhicule"):
                    card = self._vehicle_cards.get(veh_id)
                    if card:
                        card.set_selected(False)
                    return

        if selected:
            self._selected_vehicles.add(veh_id)
        else:
            self._selected_vehicles.discard(veh_id)
        self._update_context()

    def _on_decor_toggled(self, decor_id: str, decor_name: str, selected: bool):
        if selected and self._active_shot is not None:
            shot_decor_id = self._active_shot.get("decor_id", "")
            if shot_decor_id and decor_id != shot_decor_id:
                if not self._warn_not_in_shot(decor_name, "décor"):
                    card = self._decor_cards.get(decor_id)
                    if card:
                        card.set_selected(False)
                    return

        # Single-select: deselect all other décors
        for did, card in self._decor_cards.items():
            if did != decor_id:
                card.set_selected(False)

        self._selected_decor_id = decor_id if selected else None
        self._update_context()

    def _update_context(self):
        ctx = self.get_context()
        if ctx:
            skip = {"", "[COHÉRENCE VISUELLE — maintenir l'apparence identique pour TOUS les éléments ci-dessous tout au long de ce plan]"}
            lines = [
                l.split(":")[0].strip()  # show entity names only in the label
                for l in ctx.splitlines()
                if l and l not in skip and not l.startswith("CRITICAL")
            ]
            self._ctx_lbl.setText("  ·  ".join(lines))
        else:
            self._ctx_lbl.setText("")
        self.context_changed.emit(ctx)

    def get_context_parts(self) -> dict:
        """Returns structured data for display in the injection banner."""
        _eff_decor_id = self._selected_decor_id or (self._active_shot or {}).get("decor_id", "")
        _decor_name = (
            self._decors_meta.get(_eff_decor_id, {}).get("name", "")
            if _eff_decor_id else (self._active_shot or {}).get("decor_name", "")
        )
        return {
            "char_names":    [d.get("name", "") for d in self._char_data_map.values()],
            "item_names":    [self._items_meta.get(i, {}).get("name", "") for i in self._selected_items],
            "vehicle_names": [self._vehicles_meta.get(v, {}).get("name", "") for v in self._selected_vehicles],
            "decor_name":    _decor_name,
        }

    # ── Auto-select from shot ─────────────────────────────────────────────────

    def set_active_shot(self, shot: dict):
        """Auto-selects characters and vehicles matching this shot. Clears if shot is {}."""
        self._active_shot = shot if shot else None

        if not shot:
            # Clear all selections
            for card in self._char_cards.values():
                card.set_selected(False)
            self._selected_char_ids.clear()
            self._char_data_map.clear()
            for card in self._vehicle_cards.values():
                card.set_selected(False)
            self._selected_vehicles.clear()
            self._selected_items.clear()
            self._update_items_placeholder()
            for card in self._decor_cards.values():
                card.set_selected(False)
            self._selected_decor_id = None
            self._update_context()
            self._char_toggle.setChecked(False)
            self._items_toggle.setChecked(False)
            self._veh_toggle.setChecked(False)
            self._decor_toggle.setChecked(False)
            return

        shot_char_names = [n.lower() for n in (shot.get("character_names") or [])]
        shot_veh_names  = [n.lower() for n in (shot.get("vehicle_names")  or [])]

        def _name_matches(db_name: str, shot_names: list) -> bool:
            """Correspondance insensible à la casse et aux noms partiels."""
            c = db_name.lower().strip()
            if not c:
                return False
            return any(c == s or c in s or s in c for s in shot_names)

        # Auto-select characters
        self._selected_char_ids.clear()
        self._char_data_map.clear()
        for card in self._char_cards.values():
            card.set_selected(False)

        chars = casting_api.list_characters()
        for char in chars:
            if _name_matches(char.get("name", ""), shot_char_names):
                cid = char["id"]
                card = self._char_cards.get(cid)
                if card:
                    card.set_selected(True)
                self._selected_char_ids.add(cid)
                self._char_data_map[cid] = char

        if self._selected_char_ids:
            self._char_toggle.setChecked(True)

        # Reload items based on selected characters + shot accessories
        self._selected_items.clear()
        shot_acc_ids = set(shot.get("accessory_ids") or [])
        self._load_items(shot_acc_ids=shot_acc_ids)
        # Auto-select accessories assigned to the shot
        for aid in shot_acc_ids:
            if aid in self._item_cards:
                self._item_cards[aid].set_selected(True)
                self._selected_items.add(aid)

        if self._item_cards:
            self._items_toggle.setChecked(True)

        # Auto-select vehicles
        for card in self._vehicle_cards.values():
            card.set_selected(False)
        self._selected_vehicles.clear()

        for vid, meta in self._vehicles_meta.items():
            if _name_matches(meta.get("name", ""), shot_veh_names):
                card = self._vehicle_cards.get(vid)
                if card:
                    card.set_selected(True)
                self._selected_vehicles.add(vid)

        if self._selected_vehicles:
            self._veh_toggle.setChecked(True)

        # Auto-select décor
        for card in self._decor_cards.values():
            card.set_selected(False)
        self._selected_decor_id = None
        decor_id = shot.get("decor_id", "")
        if decor_id and decor_id in self._decor_cards:
            self._decor_cards[decor_id].set_selected(True)
            self._selected_decor_id = decor_id
            self._decor_toggle.setChecked(True)
        elif not decor_id:
            self._decor_toggle.setChecked(False)

        self._update_context()

    # ── Public ────────────────────────────────────────────────────────────────

    @staticmethod
    def _short(text: str, max_len: int = 180) -> str:
        """Truncate a description to keep prompt length manageable."""
        text = text.strip()
        return text[:max_len] + "…" if len(text) > max_len else text

    def get_context(self) -> str:
        has_chars    = bool(self._char_data_map)
        has_items    = bool(self._selected_items)
        has_vehicles = bool(self._selected_vehicles)
        has_decor    = bool(
            self._active_shot and (
                self._active_shot.get("decor_name") or self._active_shot.get("decor_id")
            )
        )
        if not has_chars and not has_items and not has_vehicles and not has_decor:
            return ""

        lines = [
            "[COHÉRENCE VISUELLE — maintenir l'apparence identique pour TOUS les éléments ci-dessous tout au long de ce plan]"
        ]

        # ── Characters ────────────────────────────────────────────────────────
        for char_data in self._char_data_map.values():
            name  = char_data.get("name", "")
            role  = char_data.get("role", "")
            line  = f'Personnage "{name}"'
            if role:
                line += f" ({role})"
            # N'inclure la description texte que si aucune image de référence n'existe.
            # Quand une image est présente, Seedance voit déjà le personnage visuellement —
            # la description texte est redondante et peut déclencher les filtres de contenu.
            has_image = bool(
                (char_data.get("image_path") and os.path.isfile(char_data.get("image_path", "")))
                or
                (char_data.get("sheet_path") and os.path.isfile(char_data.get("sheet_path", "")))
            )
            if not has_image:
                prompt = char_data.get("prompt", "").strip()
                if prompt:
                    line += f": {self._short(prompt)}"
            lines.append(line)

        # ── Accessories & HMC ────────────────────────────────────────────────
        for iid in self._selected_items:
            meta  = self._items_meta.get(iid, {})
            kind  = meta.get("_kind", "acc")
            iname = meta.get("name", "")
            if kind == "hmc":
                htype = meta.get("hmc_type", "Costume/HMC")
                line  = f'{htype} "{iname}"'
            else:
                cat  = meta.get("category", "")
                line = f'Accessoire "{iname}"' + (f" ({cat})" if cat else "")
            has_image = bool(
                meta.get("image_path") and os.path.isfile(meta.get("image_path", ""))
            )
            if not has_image:
                desc = self._short(meta.get("prompt") or meta.get("description") or "")
                if desc:
                    line += f": {desc}"
            lines.append(line)

        # ── Vehicles ─────────────────────────────────────────────────────────
        for vid in self._selected_vehicles:
            meta  = self._vehicles_meta.get(vid, {})
            vname = meta.get("name", "")
            cat   = meta.get("category", "")
            line  = f'Véhicule "{vname}"' + (f" ({cat})" if cat else "")
            has_image = bool(
                meta.get("image_path") and os.path.isfile(meta.get("image_path", ""))
            )
            if not has_image:
                desc = self._short(meta.get("prompt") or meta.get("description") or "")
                if desc:
                    line += f": {desc}"
            lines.append(line)

        # ── Décor sélectionné (manuel ou depuis le plan) ──────────────────────
        _eff_decor_id = self._selected_decor_id or (
            (self._active_shot or {}).get("decor_id", "") if not self._selected_decor_id else ""
        )
        if not _eff_decor_id and self._active_shot:
            _eff_decor_id = self._active_shot.get("decor_id", "")
        if _eff_decor_id:
            meta = self._decors_meta.get(_eff_decor_id)
            if not meta and self._active_shot:
                try:
                    import core.decors as _dec
                    meta = _dec.get_decor(_eff_decor_id)
                except Exception:
                    meta = None
            if meta:
                decor_name = meta.get("name", "")
                has_decor_image = bool(
                    meta.get("image_path") and os.path.isfile(meta.get("image_path", ""))
                )
                line = f'Décor "{decor_name}"'
                if not has_decor_image:
                    desc = self._short(meta.get("prompt") or meta.get("description") or "")
                    if desc:
                        line += f": {desc}"
                lines.append(line)
        elif self._active_shot and self._active_shot.get("decor_name") and not _eff_decor_id:
            lines.append(f'Décor "{self._active_shot["decor_name"]}"')

        lines.append(
            "CRITIQUE : Chaque personnage doit correspondre EXACTEMENT à la description ci-dessus "
            "— visage, coiffure, costume et traits physiques identiques. "
            "Le lieu doit correspondre exactement. Aucune dérive visuelle autorisée."
        )

        return "\n".join(lines) + "\n\n"

    def get_selected_images(self) -> list[str]:
        """Returns image paths of all selected entities (for thumbnail strip)."""
        paths = []
        for cid in self._selected_char_ids:
            char = self._char_data_map.get(cid, {})
            p = char.get("image_path", "")
            if p and os.path.isfile(p):
                paths.append(p)
        for iid in self._selected_items:
            meta = self._items_meta.get(iid, {})
            p = meta.get("image_path", "")
            if p and os.path.isfile(p):
                paths.append(p)
        for vid in self._selected_vehicles:
            meta = self._vehicles_meta.get(vid, {})
            p = meta.get("image_path", "")
            if p and os.path.isfile(p):
                paths.append(p)
        return paths

    def get_ref_images(self) -> list[str]:
        """Returns reference image paths for Seedance (priority: chars → decor → vehicles → accessories)."""
        paths = []
        # 1. Characters — face/appearance is most critical for consistency
        for cid in self._selected_char_ids:
            char = self._char_data_map.get(cid, {})
            p = char.get("sheet_path", "") or char.get("image_path", "")
            if p and os.path.isfile(p):
                paths.append(p)
        # 2. Decor — visual location reference (prefer manually selected, fallback to shot)
        _ref_decor_id = self._selected_decor_id or (self._active_shot or {}).get("decor_id", "")
        if _ref_decor_id:
            meta = self._decors_meta.get(_ref_decor_id)
            if not meta:
                try:
                    import core.decors as _dec
                    meta = _dec.get_decor(_ref_decor_id)
                except Exception:
                    meta = None
            if meta:
                p = meta.get("image_path", "")
                if p and os.path.isfile(p):
                    paths.append(p)
        # 3. Vehicles
        for vid in self._selected_vehicles:
            meta = self._vehicles_meta.get(vid, {})
            p = meta.get("image_path", "")
            if p and os.path.isfile(p):
                paths.append(p)
        # 4. Accessories & HMC
        for iid in self._selected_items:
            meta = self._items_meta.get(iid, {})
            p = meta.get("image_path", "")
            if p and os.path.isfile(p):
                paths.append(p)
        return paths

    def get_chars_without_images(self) -> list[str]:
        """Returns names of selected characters that have no usable portrait image."""
        missing = []
        for cid in self._selected_char_ids:
            char = self._char_data_map.get(cid, {})
            p = char.get("sheet_path", "") or char.get("image_path", "")
            if not p or not os.path.isfile(p):
                missing.append(char.get("name", f"#{cid[:6]}"))
        return missing

    def has_char_with_image(self) -> bool:
        """Returns True if at least one selected character has a usable portrait."""
        for cid in self._selected_char_ids:
            char = self._char_data_map.get(cid, {})
            p = char.get("sheet_path", "") or char.get("image_path", "")
            if p and os.path.isfile(p):
                return True
        return False

    def get_ref_mosaics(self, output_dir: str = "") -> tuple[list[str], list[str]]:
        """Returns (paths, roles) — parallel lists for Seedance reference images.
        Respects per-section 'Ne pas envoyer' checkboxes."""
        from core.mosaic import build_ref_mosaics

        # Respect per-section exclusion checkboxes
        no_char  = getattr(self, "_no_char_ref_cb",  None) and self._no_char_ref_cb.isChecked()
        no_item  = getattr(self, "_no_item_ref_cb",  None) and self._no_item_ref_cb.isChecked()
        no_veh   = getattr(self, "_no_veh_ref_cb",   None) and self._no_veh_ref_cb.isChecked()
        no_decor = getattr(self, "_no_decor_ref_cb", None) and self._no_decor_ref_cb.isChecked()

        decor_image_path = ""
        if not no_decor:
            _mosaic_decor_id = self._selected_decor_id or (self._active_shot or {}).get("decor_id", "")
            if _mosaic_decor_id:
                meta = self._decors_meta.get(_mosaic_decor_id)
                if not meta:
                    try:
                        import core.decors as _dec
                        meta = _dec.get_decor(_mosaic_decor_id)
                    except Exception:
                        meta = None
                if meta:
                    decor_image_path = meta.get("image_path", "")

        # HMC items are NOT sent to Seedance — they feed character generation only
        acc_only = set() if no_item else {
            iid for iid in self._selected_items
            if self._items_meta.get(iid, {}).get("_kind") != "hmc"
        }
        selected_vehicles = set() if no_veh else self._selected_vehicles
        char_data_map = {} if no_char else self._char_data_map

        return build_ref_mosaics(
            char_data_map=char_data_map,
            decor_image_path=decor_image_path,
            items_meta=self._items_meta,
            selected_items=acc_only,
            vehicles_meta=self._vehicles_meta,
            selected_vehicles=selected_vehicles,
            output_dir=output_dir,
        )

    def refresh(self):
        prev_chars  = set(self._selected_char_ids)
        prev_vehs   = set(self._selected_vehicles)
        prev_decor  = self._selected_decor_id
        self._load_chars()
        self._load_vehicles()
        self._load_decors()
        self._selected_char_ids.clear()
        self._char_data_map.clear()
        for cid in prev_chars:
            if cid in self._char_cards:
                self._char_cards[cid].set_selected(True)
                fresh = casting_api.get_character(cid)
                self._selected_char_ids.add(cid)
                self._char_data_map[cid] = fresh or {}
        if self._char_data_map:
            self._load_items()
        else:
            self._selected_items.clear()
            self._update_items_placeholder()
        self._selected_vehicles.clear()
        for vid in prev_vehs:
            if vid in self._vehicle_cards:
                self._vehicle_cards[vid].set_selected(True)
                self._selected_vehicles.add(vid)
        self._selected_decor_id = None
        if prev_decor and prev_decor in self._decor_cards:
            self._decor_cards[prev_decor].set_selected(True)
            self._selected_decor_id = prev_decor
        self._update_context()


# ── Storyboard selector ───────────────────────────────────────────────────────

class StoryboardSelector(QWidget):
    shot_selected  = pyqtSignal(dict)
    shots_selected = pyqtSignal(list)

    def __init__(self):
        super().__init__()
        self._selected_shot_id:  str | None    = None
        self._selected_shot_ids: set[str]      = set()
        self._shot_cards:        dict[str, _ThumbCard] = {}
        self._shots_meta:        dict[str, dict]       = {}

        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(8)

        lay.addWidget(section_label("Storyboard"))

        self._inner = QWidget()
        self._inner.setStyleSheet("background:transparent;")
        self._hbox = QHBoxLayout(self._inner)
        self._hbox.setContentsMargins(4, 4, 12, 4)
        self._hbox.setSpacing(10)
        self._hbox.setAlignment(
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
        )

        scroll = QScrollArea()
        scroll.setWidget(self._inner)
        scroll.setWidgetResizable(True)
        scroll.setFixedHeight(120)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll.setStyleSheet(
            f"QScrollArea{{background:rgba(124,107,255,0.04);"
            f"border:1px solid rgba(124,107,255,0.18);border-radius:10px;}}"
            f"QScrollBar:horizontal{{height:4px;background:{C['bg2']};"
            f"border-radius:2px;margin:0;}}"
            f"QScrollBar::handle:horizontal{{background:rgba(124,107,255,0.40);"
            f"border-radius:2px;min-width:30px;}}"
            f"QScrollBar::add-line:horizontal,QScrollBar::sub-line:horizontal{{width:0;}}"
        )
        lay.addWidget(scroll)

        # Lasso : cliquer-glisser sur le fond de la bande = sélection rectangle
        from PyQt6.QtWidgets import QRubberBand
        self._rubber = QRubberBand(QRubberBand.Shape.Rectangle, self._inner)
        self._rubber_origin = None
        self._last_clicked_id: str | None = None   # ancre du Maj+clic (plage)
        self._inner.installEventFilter(self)

        self._load_shots()

    def eventFilter(self, obj, ev):
        from PyQt6.QtCore import QEvent, QRect
        if obj is self._inner:
            t = ev.type()
            if (t == QEvent.Type.MouseButtonPress
                    and ev.button() == Qt.MouseButton.LeftButton
                    and self._inner.childAt(ev.position().toPoint()) is None):
                self._rubber_origin = ev.position().toPoint()
                self._rubber.setGeometry(QRect(self._rubber_origin, self._rubber_origin))
                self._rubber.show()
                return True
            if t == QEvent.Type.MouseMove and self._rubber_origin is not None:
                self._rubber.setGeometry(
                    QRect(self._rubber_origin, ev.position().toPoint()).normalized())
                return True
            if t == QEvent.Type.MouseButtonRelease and self._rubber_origin is not None:
                rect = self._rubber.geometry()
                self._rubber.hide()
                self._rubber_origin = None
                self._apply_lasso(rect)
                return True
        return super().eventFilter(obj, ev)

    def _apply_lasso(self, rect):
        """Sélectionne tous les plans dont la vignette croise le rectangle."""
        hits = [sid for sid, card in self._shot_cards.items()
                if rect.intersects(card.geometry())]
        if not hits:
            return
        self._selected_shot_ids = set(hits)
        for sid, card in self._shot_cards.items():
            card.set_selected(sid in self._selected_shot_ids)
        self._emit_selection()

    def _shot_order(self) -> list:
        def _num(s):
            try:
                return int(s.get("number") or 0)
            except (TypeError, ValueError):
                return 0
        return [s["id"] for s in sorted(self._shots_meta.values(), key=_num)]

    def _emit_selection(self):
        count = len(self._selected_shot_ids)
        if count == 1:
            self._selected_shot_id = next(iter(self._selected_shot_ids))
            fresh = sb_api.get_shot(self._selected_shot_id)
            if fresh:
                self._shots_meta[self._selected_shot_id] = fresh
            self.shot_selected.emit(self._shots_meta.get(self._selected_shot_id, {}))
        elif count == 0:
            self._selected_shot_id = None
            self.shot_selected.emit({})
        else:
            self._selected_shot_id = None
            shots_list = sorted(
                [self._shots_meta.get(sid, {}) for sid in self._selected_shot_ids],
                key=lambda s: int(s.get("number") or 0) if s.get("number") is not None else 0,
            )
            self.shot_selected.emit({})
            self.shots_selected.emit(shots_list)

    def _load_shots(self):
        while self._hbox.count():
            it = self._hbox.takeAt(0)
            if it.widget():
                it.widget().deleteLater()
        self._shot_cards.clear()
        self._shots_meta.clear()

        shots = sb_api.list_shots()
        if not shots:
            lbl = QLabel("Aucun plan — crée-en un dans le Storyboard.")
            lbl.setStyleSheet(f"color:{C['text_dim']};font-size:10px;background:transparent;")
            self._hbox.addWidget(lbl)
            self._hbox.addStretch()
            return

        # Build décor image cache for thumbnail fallback
        decor_imgs: dict[str, str] = {}
        try:
            for d in dec_api.list_decors():
                if d.get("id"):
                    decor_imgs[d["id"]] = d.get("image_path", "")
        except Exception:
            pass

        total = len(shots)
        for i, shot in enumerate(shots):
            num   = shot.get("number", "?")
            title = shot.get("scene_title", "") or shot.get("decor_name", "")
            badge = f"#{num}"

            # Shot image: own first, then décor fallback
            img_path = shot.get("image_path", "")
            if not img_path:
                img_path = decor_imgs.get(shot.get("decor_id", ""), "")

            overlay = f"Plan {num}\n{i + 1} sur {total}"

            card = _ThumbCard(shot["id"], title or badge, img_path, badge,
                              overlay_text=overlay)
            card.toggled.connect(
                lambda sel, sid=shot["id"]: self._on_shot_toggled(sid, sel)
            )
            self._shot_cards[shot["id"]] = card
            self._shots_meta[shot["id"]] = shot
            self._hbox.addWidget(card)
        self._hbox.addStretch()

    def _on_shot_toggled(self, shot_id: str, selected: bool):
        from PyQt6.QtWidgets import QApplication
        mods  = QApplication.keyboardModifiers()
        shift = bool(mods & Qt.KeyboardModifier.ShiftModifier)
        ctrl  = bool(mods & Qt.KeyboardModifier.ControlModifier)

        if shift and self._last_clicked_id in self._shots_meta:
            # Maj+clic : sélectionne TOUTE LA PLAGE entre le dernier clic et ici
            order = self._shot_order()
            try:
                i1, i2 = order.index(self._last_clicked_id), order.index(shot_id)
            except ValueError:
                i1 = i2 = order.index(shot_id) if shot_id in order else 0
            self._selected_shot_ids |= set(order[min(i1, i2):max(i1, i2) + 1])
        elif ctrl:
            if selected:
                self._selected_shot_ids.add(shot_id)
            else:
                self._selected_shot_ids.discard(shot_id)
            self._last_clicked_id = shot_id
        else:
            self._selected_shot_ids = {shot_id} if selected else set()
            self._last_clicked_id = shot_id

        for sid, card in self._shot_cards.items():
            card.set_selected(sid in self._selected_shot_ids)
        self._emit_selection()

    def get_selected_shot(self) -> dict | None:
        if self._selected_shot_id:
            return self._shots_meta.get(self._selected_shot_id)
        return None

    def get_selected_shots(self) -> list[dict]:
        return sorted(
            [self._shots_meta.get(sid, {}) for sid in self._selected_shot_ids],
            key=lambda s: s.get("number", 0),
        )

    def refresh(self):
        prev_ids = set(self._selected_shot_ids)
        self._load_shots()
        self._selected_shot_ids.clear()
        self._selected_shot_id = None
        for sid in prev_ids:
            if sid in self._shot_cards:
                self._shot_cards[sid].set_selected(True)
                self._selected_shot_ids.add(sid)
        if len(self._selected_shot_ids) == 1:
            self._selected_shot_id = next(iter(self._selected_shot_ids))


# ── DaVinci status bar ────────────────────────────────────────────────────────

class _DaVinciBar(QWidget):
    connection_changed = pyqtSignal(bool)

    def __init__(self):
        super().__init__()
        self._prev_connected: bool | None = None
        self.setFixedHeight(36)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(8)

        logo = QLabel("DaVinci Resolve Studio")
        logo.setStyleSheet(
            f"color:{C['text_secondary']};font-size:11px;font-weight:700;background:transparent;"
        )
        lay.addWidget(logo)

        self._btn_connect = QPushButton("Connecter")
        self._btn_connect.setFixedHeight(28)
        self._btn_connect.setStyleSheet(
            f"QPushButton{{background:transparent;color:{C['accent']};"
            f"border:1px solid {C['accent_dim']};border-radius:6px;"
            f"font-size:10px;font-weight:700;padding:0 10px;}}"
            f"QPushButton:hover{{background:rgba(78,205,196,0.12);}}"
        )
        self._btn_connect.clicked.connect(self._on_connect)
        lay.addWidget(self._btn_connect)

        self._dot = QLabel("●")
        self._dot.setStyleSheet(f"color:{C['red']};font-size:10px;background:transparent;")
        lay.addWidget(self._dot)

        self._status_lbl = QLabel("Non connecté")
        self._status_lbl.setStyleSheet(
            f"color:{C['text_dim']};font-size:10px;background:transparent;"
        )
        lay.addWidget(self._status_lbl)
        lay.addStretch()

        self._refresh()

    def _refresh(self):
        connected = resolve.is_connected()
        if connected:
            self._dot.setStyleSheet(f"color:{C['green']};font-size:10px;background:transparent;")
            self._status_lbl.setText("Connecté")
            self._status_lbl.setStyleSheet(
                f"color:{C['green']};font-size:10px;background:transparent;"
            )
            self._btn_connect.setText("✓ Connecté")
            self._btn_connect.setEnabled(False)
        else:
            self._dot.setStyleSheet(f"color:{C['red']};font-size:10px;background:transparent;")
            self._status_lbl.setText("Non connecté")
            self._status_lbl.setStyleSheet(
                f"color:{C['text_dim']};font-size:10px;background:transparent;"
            )
            self._btn_connect.setText("Connecter")
            self._btn_connect.setEnabled(True)
        if connected != self._prev_connected:
            self._prev_connected = connected
            self.connection_changed.emit(connected)

    def _on_connect(self):
        ok, msg = resolve.connect()
        self._refresh()
        if not ok:
            QMessageBox.warning(self, "Connexion impossible", msg)


# ── Thumbnail strip ───────────────────────────────────────────────────────────

class _ThumbnailStrip(QWidget):
    _SZ = 32

    def __init__(self):
        super().__init__()
        self.setFixedHeight(self._SZ + 4)
        self._lay = QHBoxLayout(self)
        self._lay.setContentsMargins(0, 2, 0, 2)
        self._lay.setSpacing(4)
        self._lay.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)

    def update_images(self, paths: list[str], count_label: QLabel | None = None):
        while self._lay.count():
            it = self._lay.takeAt(0)
            if it.widget():
                it.widget().deleteLater()

        shown = 0
        for path in paths[:8]:
            if not os.path.isfile(path):
                continue
            lbl = QLabel()
            lbl.setFixedSize(self._SZ, self._SZ)
            pix = QPixmap(path).scaled(
                self._SZ, self._SZ,
                Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                Qt.TransformationMode.SmoothTransformation,
            )
            pix = pix.copy(
                (pix.width()  - self._SZ) // 2,
                (pix.height() - self._SZ) // 2,
                self._SZ, self._SZ,
            )
            lbl.setPixmap(pix)
            lbl.setStyleSheet("border-radius:4px;border:1px solid rgba(78,205,196,0.3);")
            self._lay.addWidget(lbl)
            shown += 1

        if shown == 0:
            self.setVisible(False)
        else:
            self.setVisible(True)
            self._lay.addStretch()


# ── Continuity / Raccord bar ──────────────────────────────────────────────────

class _ContinuityBar(QFrame):
    """Shows previous-shot context and optionally injects a raccord prefix into the prompt."""

    def __init__(self):
        super().__init__()
        self._prev_shot: dict | None = None
        self.setVisible(False)
        self.setStyleSheet(
            f"QFrame{{background:rgba(124,107,255,0.08);"
            f"border:1px solid rgba(124,107,255,0.28);border-radius:8px;}}"
        )
        outer = QVBoxLayout(self)
        outer.setContentsMargins(12, 8, 12, 8)
        outer.setSpacing(6)

        # ── Rangée 1 : info raccord + checkbox prompt ─────────────────────────
        row1 = QHBoxLayout()
        row1.setContentsMargins(0, 0, 0, 0)
        row1.setSpacing(10)

        icon = QLabel("⟳")
        icon.setFixedWidth(18)
        icon.setStyleSheet(
            f"color:{C['accent']};font-size:15px;font-weight:700;"
            f"background:transparent;border:none;"
        )
        row1.addWidget(icon)

        col = QVBoxLayout()
        col.setSpacing(2)
        self._title_lbl = QLabel("Raccord automatique")
        self._title_lbl.setStyleSheet(
            f"color:{C['accent']};font-size:9px;font-weight:800;"
            f"letter-spacing:0.5px;background:transparent;border:none;"
        )
        self._info_lbl = QLabel("")
        self._info_lbl.setStyleSheet(
            f"color:{C['text_secondary']};font-size:10px;background:transparent;border:none;"
        )
        col.addWidget(self._title_lbl)
        col.addWidget(self._info_lbl)
        row1.addLayout(col, 1)

        self._cb = QCheckBox("Inclure dans le prompt")
        self._cb.setChecked(True)
        self._cb.setStyleSheet(
            f"QCheckBox{{color:{C['text_dim']};font-size:10px;background:transparent;border:none;}}"
            f"QCheckBox::indicator{{width:14px;height:14px;border-radius:3px;"
            f"border:1px solid {C['border_bright']};}}"
            f"QCheckBox::indicator:checked{{background:{C['accent']};border-color:{C['accent']};}}"
        )
        row1.addWidget(self._cb)
        outer.addLayout(row1)

        # ── Rangée 2 : continuer depuis la dernière frame (I2V) ───────────────
        self._i2v_row = QHBoxLayout()
        self._i2v_row_widget = QWidget()
        self._i2v_row_widget.setStyleSheet("background:transparent;")
        self._i2v_row_widget.setVisible(False)
        i2v_inner = QHBoxLayout(self._i2v_row_widget)
        i2v_inner.setContentsMargins(28, 0, 0, 0)
        i2v_inner.setSpacing(8)

        frame_icon = QLabel("🎬")
        frame_icon.setFixedWidth(18)
        frame_icon.setStyleSheet(
            "background:transparent;border:none;font-size:11px;"
        )
        i2v_inner.addWidget(frame_icon)

        self._i2v_cb = QCheckBox("Continuer depuis la dernière frame du plan précédent (I2V)")
        self._i2v_cb.setChecked(False)
        self._i2v_cb.setStyleSheet(
            f"QCheckBox{{color:{C['accent']};font-size:10px;font-weight:600;"
            f"background:transparent;border:none;}}"
            f"QCheckBox::indicator{{width:14px;height:14px;border-radius:3px;"
            f"border:1px solid {C['border_bright']};}}"
            f"QCheckBox::indicator:checked{{background:{C['accent']};border-color:{C['accent']};}}"
        )
        i2v_inner.addWidget(self._i2v_cb, 1)

        self._i2v_thumb = QLabel()
        self._i2v_thumb.setFixedSize(36, 20)
        self._i2v_thumb.setScaledContents(True)
        self._i2v_thumb.setStyleSheet(
            f"border:1px solid rgba(124,107,255,0.4);border-radius:3px;background:transparent;"
        )
        self._i2v_thumb.setVisible(False)
        i2v_inner.addWidget(self._i2v_thumb)

        outer.addWidget(self._i2v_row_widget)

    def update_shot(self, current_shot: dict, all_shots: list):
        """Finds the shot just before current_shot and updates display."""
        if not current_shot or not all_shots:
            self.setVisible(False)
            self._i2v_row_widget.setVisible(False)
            self._prev_shot = None
            return

        def _num(s):
            try: return int(s.get("number") or 0)
            except (TypeError, ValueError): return 0
        curr_num = _num(current_shot)
        prev: dict | None = None
        for s in sorted(all_shots, key=_num):
            if _num(s) < curr_num:
                prev = s

        if prev is None:
            self.setVisible(False)
            self._i2v_row_widget.setVisible(False)
            self._prev_shot = None
            return

        self._prev_shot = prev
        parts = [f"Plan {prev.get('number', '?')}"]
        if prev.get("decor_name"):
            parts.append(f"◻ {prev['decor_name']}")
        if prev.get("shot_time"):
            parts.append(prev["shot_time"])
        chars = prev.get("character_names", [])
        if chars:
            parts.append("👤 " + ", ".join(chars))

        self._info_lbl.setText("Raccord depuis : " + "  ·  ".join(parts))

        # Rangée I2V : visible seulement si le plan précédent a une dernière frame
        frame_path = prev.get("last_frame_path", "")
        if frame_path and os.path.isfile(frame_path):
            pix = QPixmap(frame_path)
            if not pix.isNull():
                self._i2v_thumb.setPixmap(pix)
                self._i2v_thumb.setVisible(True)
            self._i2v_row_widget.setVisible(True)
        else:
            self._i2v_thumb.setVisible(False)
            self._i2v_row_widget.setVisible(False)

        self.setVisible(True)

    def build_continuity_prefix(self) -> str:
        """Returns an English raccord context prefix for the Seedance prompt, or ''."""
        if not self._cb.isChecked() or not self._prev_shot:
            return ""
        s = self._prev_shot
        lines = []

        # ── Location ──────────────────────────────────────────────────────────
        decor_name = s.get("decor_name", "")
        decor_id   = s.get("decor_id", "")
        if decor_name or decor_id:
            desc = ""
            if decor_id:
                try:
                    import core.decors as _dec
                    d = _dec.get_decor(decor_id)
                    if d:
                        decor_name = decor_name or d.get("name", "")
                        raw = (d.get("prompt") or d.get("description") or "").strip()
                        desc = raw[:160] + "…" if len(raw) > 160 else raw
                except Exception:
                    pass
            loc = f'Location "{decor_name}"'
            if desc:
                loc += f": {desc}"
            lines.append(loc)

        if s.get("shot_time"):
            lines.append(f"Time of day: {s['shot_time'].lower()}")

        # ── Characters with visual descriptions ───────────────────────────────
        char_ids = s.get("character_ids", [])
        if char_ids:
            try:
                import core.casting as _cast
                for cid in char_ids:
                    char = _cast.get_character(cid)
                    if not char:
                        continue
                    cname  = char.get("name", "")
                    cprompt = (char.get("prompt") or "").strip()
                    desc = cprompt[:160] + "…" if len(cprompt) > 160 else cprompt
                    line = f'Character "{cname}"'
                    if desc:
                        line += f": {desc} — identical costume and appearance"
                    else:
                        line += " — identical costume and appearance"
                    lines.append(line)
            except Exception:
                char_names = s.get("character_names", [])
                if char_names:
                    lines.append(
                        f"Characters: {', '.join(char_names)} — identical costumes, hairstyle, and appearance"
                    )

        # ── Vehicles ──────────────────────────────────────────────────────────
        veh_names = s.get("vehicle_names", [])
        if veh_names:
            lines.append(f"Vehicles: {', '.join(veh_names)} — same vehicle(s) as previous shot")

        prev_num = s.get("number", "?")
        body = "\n".join(f"  • {l}" for l in lines)
        prefix = (
            f"[SHOT CONTINUITY — this shot follows shot {prev_num}]\n"
            f"MAINTAIN EXACT VISUAL CONSISTENCY with the previous shot:\n"
            f"{body}\n"
            f"Seamless visual edit: same set dressing, same lighting, "
            f"no costume or location changes between cuts.\n"
        )
        return prefix

    def get_prev_last_frame(self) -> str:
        """Returns last_frame_path of previous shot if raccord is enabled, else ''."""
        if not self._cb.isChecked() or not self._prev_shot:
            return ""
        return self._prev_shot.get("last_frame_path", "")

    def get_i2v_frame(self) -> str:
        """Returns last_frame_path of prev shot when I2V continuity checkbox is enabled, else ''."""
        if not self._i2v_row_widget.isVisible() or not self._i2v_cb.isChecked():
            return ""
        if not self._prev_shot:
            return ""
        path = self._prev_shot.get("last_frame_path", "")
        return path if path and os.path.isfile(path) else ""


# ── Camera & optics picker (compact, for Seedance tab) ────────────────────────

class _CameraOpticsPicker(QFrame):
    """Compact focal picker for the Studio IA tab. Camera/optics/mic come from Image & Son."""

    def __init__(self):
        super().__init__()
        self._focal_from_shot: bool = False
        self.setStyleSheet("QFrame{background:transparent;border:none;}")
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 2, 0, 2)
        lay.setSpacing(8)

        # Focal is defined in the storyboard — no override in Studio IA
        from core.storyboard import FOCALS
        self._cb_focal = combo(["— Aucune —"] + FOCALS)
        self._cb_focal.setVisible(False)
        self._focal_lbl = QLabel("Focale :")
        self._focal_lbl.setVisible(False)
        lay.addStretch()

    def _on_focal_changed(self):
        self._focal_from_shot = False
        self._update_focal_style()

    def _update_focal_style(self):
        color = C['accent'] if self._focal_from_shot else C['text_secondary']
        self._focal_lbl.setStyleSheet(
            f"color:{color};font-size:11px;font-weight:600;background:transparent;border:none;"
        )

    def set_focal_from_shot(self, focal: str):
        """Sets focal from storyboard shot (shown in red). Empty string clears the shot focal."""
        self._cb_focal.blockSignals(True)
        if focal:
            idx = self._cb_focal.findText(focal)
            if idx >= 0:
                self._cb_focal.setCurrentIndex(idx)
                self._focal_from_shot = True
            else:
                self._cb_focal.setCurrentIndex(0)
                self._focal_from_shot = False
        else:
            self._cb_focal.setCurrentIndex(0)
            self._focal_from_shot = False
        self._cb_focal.blockSignals(False)
        self._update_focal_style()

    def get_suffix(self) -> str:
        """Returns the English suffix (camera + optics + filters) to append to the Seedance prompt."""
        prefs = cam_prefs.get_camera_prefs()
        return build_camera_prompt_suffix(prefs)

    def refresh(self):
        pass  # camera/optics/mic come from Image & Son; no labels to refresh here


# ── Seed widget ───────────────────────────────────────────────────────────────

class _SeedWidget(QFrame):
    """Compact seed lock — keeps the same visual 'DNA' across shots when locked."""

    def __init__(self):
        super().__init__()
        self._locked = False
        self.setStyleSheet(
            f"QFrame{{background:{C['bg2']};border:1px solid {C['border']};border-radius:8px;}}"
        )
        lay = QHBoxLayout(self)
        lay.setContentsMargins(12, 8, 12, 8)
        lay.setSpacing(8)

        self._lock_btn = QPushButton("🔓")
        self._lock_btn.setFixedSize(28, 28)
        self._lock_btn.setCheckable(True)
        self._lock_btn.setToolTip(
            "Verrouiller la graine visuelle — même apparence pour tous les plans"
        )
        self._lock_btn.setStyleSheet(
            f"QPushButton{{background:transparent;border:1px solid {C['border']};"
            f"border-radius:6px;font-size:13px;color:{C['text_dim']};}}"
            f"QPushButton:checked{{background:rgba(124,107,255,0.18);"
            f"border-color:{C['accent']};color:{C['accent']};}}"
            f"QPushButton:hover{{background:{C['bg3']};}}"
        )
        self._lock_btn.toggled.connect(self._on_toggle)
        lay.addWidget(self._lock_btn)

        col = QVBoxLayout()
        col.setSpacing(1)
        lbl_title = QLabel("Graine visuelle (Seed)")
        lbl_title.setStyleSheet(
            f"color:{C['text_secondary']};font-size:10px;font-weight:700;"
            f"background:transparent;border:none;"
        )
        self._lbl_hint = QLabel("Aléatoire — résultats variables à chaque génération")
        self._lbl_hint.setStyleSheet(
            f"color:{C['text_dim']};font-size:9px;background:transparent;border:none;"
        )
        col.addWidget(lbl_title)
        col.addWidget(self._lbl_hint)
        lay.addLayout(col, 1)

        self._seed_input = QLineEdit()
        self._seed_input.setPlaceholderText("0 – 999 999 999")
        self._seed_input.setFixedWidth(118)
        self._seed_input.setFixedHeight(26)
        self._seed_input.setValidator(QIntValidator(0, 999_999_999))
        self._seed_input.setEnabled(False)
        self._seed_input.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._seed_input.setStyleSheet(
            f"QLineEdit{{background:{C['bg3']};color:{C['text_primary']};"
            f"border:1px solid {C['border']};border-radius:5px;padding:3px 6px;"
            f"font-size:11px;font-family:'Consolas',monospace;}}"
            f"QLineEdit:enabled{{border-color:{C['accent']};}}"
            f"QLineEdit:disabled{{color:{C['text_dim']};}}"
        )
        lay.addWidget(self._seed_input)

    def _on_toggle(self, checked: bool):
        self._locked = checked
        self._lock_btn.setText("🔒" if checked else "🔓")
        self._seed_input.setEnabled(checked)
        if checked:
            self._lbl_hint.setText("Verrouillée — même ADN visuel pour tous les plans")
            self._lbl_hint.setStyleSheet(
                f"color:{C['accent']};font-size:9px;background:transparent;border:none;"
            )
        else:
            self._lbl_hint.setText("Aléatoire — résultats variables à chaque génération")
            self._lbl_hint.setStyleSheet(
                f"color:{C['text_dim']};font-size:9px;background:transparent;border:none;"
            )

    def get_seed(self) -> int | None:
        """Returns the locked seed value, or None if unlocked."""
        if not self._locked:
            return None
        text = self._seed_input.text().strip()
        if text:
            try:
                return int(text)
            except ValueError:
                pass
        return None

    def set_last_seed(self, seed: int):
        """After generation, record the seed that was used."""
        if seed and seed > 0:
            self._seed_input.setText(str(seed))


# ── GCS warning bar ───────────────────────────────────────────────────────────

class _GCSWarningBar(QFrame):
    """Shown after a generation when ref image uploads failed due to GCS being unavailable."""

    def __init__(self):
        super().__init__()
        self.setVisible(False)
        self.setStyleSheet(
            "QFrame{background:rgba(255,160,50,0.10);"
            "border:1px solid rgba(255,160,50,0.38);border-radius:8px;}"
        )
        lay = QHBoxLayout(self)
        lay.setContentsMargins(12, 8, 12, 8)
        lay.setSpacing(10)

        icon = QLabel("⚠")
        icon.setFixedWidth(18)
        icon.setStyleSheet(
            "color:#ffa032;font-size:15px;font-weight:700;"
            "background:transparent;border:none;"
        )
        lay.addWidget(icon)

        col = QVBoxLayout()
        col.setSpacing(2)
        self._t1 = QLabel("Images de référence non transmises à Seedance")
        self._t1.setStyleSheet(
            "color:#ffa032;font-size:10px;font-weight:800;"
            "letter-spacing:0.3px;background:transparent;border:none;"
        )
        self._t2 = QLabel(
            "L'upload des images de référence (personnages, décors, véhicules) a échoué. "
            "Vérifie que ta clé fal.ai est correcte dans les Paramètres du plugin."
        )
        self._t2.setWordWrap(True)
        self._t2.setStyleSheet(
            f"color:{C['text_secondary']};font-size:10px;background:transparent;border:none;"
        )
        self._t3 = QLabel("")
        self._t3.setWordWrap(True)
        self._t3.setVisible(False)
        self._t3.setStyleSheet(
            "color:#ffa032;font-size:9px;font-family:'Consolas',monospace;"
            "background:transparent;border:none;"
        )
        col.addWidget(self._t1)
        col.addWidget(self._t2)
        col.addWidget(self._t3)
        lay.addLayout(col, 1)

        close = QPushButton("✕")
        close.setFixedSize(20, 20)
        close.setStyleSheet(
            f"QPushButton{{background:transparent;color:{C['text_dim']};"
            f"border:none;font-size:11px;font-weight:700;border-radius:4px;}}"
            f"QPushButton:hover{{color:{C['text_primary']};background:{C['bg3']};}}"
        )
        close.clicked.connect(lambda: self.setVisible(False))
        lay.addWidget(close)

    def show_warning(self, sent: int = 0, attempted: int = 0, detail: str = ""):
        if attempted > 0 and sent > 0:
            self._t1.setText(
                f"Images de référence partiellement transmises ({sent}/{attempted})"
            )
            self._t2.setText(
                "Certaines images de référence n'ont pas pu être uploadées — "
                "la génération a été lancée avec les images disponibles."
            )
        else:
            self._t1.setText("Images de référence non transmises à Seedance")
            self._t2.setText(
                "L'upload des images de référence (personnages, décors, véhicules) a échoué. "
                "Vérifie que ta clé fal.ai est correcte dans les Paramètres du plugin."
            )
        if detail:
            self._t3.setText(f"Détail : {detail}")
            self._t3.setVisible(True)
        else:
            self._t3.setVisible(False)
        self.setVisible(True)


# ── Creative control panel ────────────────────────────────────────────────────

_CREATIVE_DEFS = [
    # (key, group, fr_label, left_pole, right_pole, {pos: english_phrase})
    # pos=3 is neutral → no injection
    ("prompt_adherence", "RÉALISATION", "Interprétation", "Créatif", "Littéral", {
        1: "experimental free cinematic interpretation, prioritize visual impact over literal faithfulness",
        2: "loose creative adaptation, loosely inspired by the prompt",
        4: "close to the prompt with minor artistic liberties",
        5: "strictly faithful to the prompt description, literal visual rendering",
    }),
    ("camera_motion", "RÉALISATION", "Caméra", "Fixe", "Dynamique", {
        1: "completely static camera, locked tripod, absolutely no camera movement",
        2: "very subtle camera movement, nearly static",
        4: "active camera movement, noticeable dynamic motion",
        5: "highly dynamic handheld camera, fast kinetic movement",
    }),
    ("motion_strength", "RÉALISATION", "Mouvement", "Subtil", "Intense", {
        1: "minimal movement, near-static scene, very subtle micro-motions only",
        2: "gentle subtle motion, low scene dynamics, soft gentle movement",
        4: "strong visual dynamics, active motion, significant scene transformation",
        5: "maximum motion intensity, extreme visual transformation, full kinetic energy",
    }),
    ("drama_level", "RÉALISATION", "Atmosphère", "Calme", "Dramatique", {
        1: "calm peaceful atmosphere, minimal drama, serene quiet mood",
        2: "relaxed tone, mild gentle tension",
        4: "strong dramatic tension, intense cinematic atmosphere",
        5: "strong drama, high tension, deeply intense cinematic atmosphere",
    }),
    ("action_pace", "RÉALISATION", "Rythme", "Lent", "Rapide", {
        1: "very slow contemplative rhythm, long slow takes",
        2: "slow calm pace, deliberate unhurried timing",
        4: "fast-paced energetic rhythm, quick action",
        5: "very fast pace, high-energy rapid action sequence",
    }),
    ("lighting_contrast", "RÉALISATION", "Lumière", "Douce", "Contrastée", {
        1: "very soft diffused lighting, no harsh shadows, flat even illumination",
        2: "soft natural lighting, gentle soft shadows",
        4: "strong contrast, deep shadows, crisp bright highlights",
        5: "strong high contrast, dramatic chiaroscuro lighting",
    }),
    ("decor_fidelity", "FIDÉLITÉ", "Décor", "Libre", "Exact", {
        1: "creative setting interpretation, atmospheric impression only",
        2: "loosely inspired by the described location",
        4: "close match to the described decor and location",
        5: "exact decor reproduction, strict match to every described location detail",
    }),
    ("character_fidelity", "FIDÉLITÉ", "Personnages", "Libres", "Stricts", {
        1: "flexible character appearance, general type only",
        2: "loosely matching character description",
        4: "close match to character description and appearance",
        5: "strict character fidelity, exact match to described physical appearance",
    }),
    ("temporal_coherence", "FIDÉLITÉ", "Cohérence", "Variable", "Stable", {
        1: "allow temporal discontinuities and dreamlike visual transitions",
        2: "slightly loose temporal flow, some visual variation allowed",
        4: "strong temporal coherence, smooth consistent motion flow",
        5: "maximum temporal stability, perfectly consistent motion, no flickering",
    }),
    ("realism", "ESTHÉTIQUE", "Rendu", "Stylisé", "Réaliste", {
        1: "highly stylized surreal aesthetic, artistic painterly visual treatment",
        2: "stylized look with graphic or painterly quality",
        4: "mostly realistic with subtle cinematic treatment",
        5: "photorealistic documentary-style natural rendering",
    }),
    ("visual_density", "ESTHÉTIQUE", "Composition", "Épurée", "Riche", {
        1: "minimalist composition, clean empty frame, single subject focus",
        2: "simple clean composition, few visual elements",
        4: "rich detailed composition, many visual elements",
        5: "very dense visual composition, richly layered detail",
    }),
    ("depth_of_field", "ESTHÉTIQUE", "Prof. de champ", "Net", "Flou", {
        1: "deep focus, everything sharp, infinite depth of field, all elements crisp",
        2: "moderate depth of field, slight background softness",
        4: "shallow depth of field, soft blurred background, subject isolation, cinematic bokeh",
        5: "extreme shallow depth of field, heavy bokeh, strong background blur, wide-aperture lens",
    }),
    ("saturation", "ESTHÉTIQUE", "Saturation", "Désaturé", "Éclatant", {
        1: "desaturated palette, muted dull tones, near-monochromatic, low chroma",
        2: "subdued colors, soft muted tones, slightly desaturated palette",
        4: "vivid saturated colors, rich chromatic intensity, punchy color grading",
        5: "hyper-saturated, extremely vivid colors, intense high-chroma palette",
    }),
]

# Slider position (1-5) → Seedance safety_tolerance API value
_SAFETY_MAP = {1: 1, 2: 2, 3: 3, 4: 5, 5: 6}

_CREATIVE_PHRASES = {d[0]: d[5] for d in _CREATIVE_DEFS}


class _CreativeControlPanel(QFrame):
    """Collapsible panel — creative & fidelity controls for Seedance generation."""

    def __init__(self):
        super().__init__()
        self.setObjectName("creative_panel")
        self.setStyleSheet(
            f"QFrame#creative_panel{{background:{C['bg1']};"
            f"border:1px solid {C['border']};border-radius:10px;}}"
        )
        self._expanded = False
        self._sliders: dict[str, QSlider] = {}
        self._safety_slider: QSlider | None = None
        self._safety_val_lbl: QLabel | None = None

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ── Toggle header ──────────────────────────────────────────────────────
        self._header = QPushButton("⚙  Contrôles créatifs    ▶")
        self._header.setCursor(Qt.CursorShape.PointingHandCursor)
        self._header.setFixedHeight(36)
        self._header.setStyleSheet(
            f"QPushButton{{background:transparent;border:none;"
            f"color:{C['text_secondary']};font-size:11px;font-weight:700;"
            f"text-align:left;padding:0 14px;}}"
            f"QPushButton:hover{{color:{C['text_primary']};}}"
        )
        self._header.clicked.connect(self._toggle)
        root.addWidget(self._header)

        # ── Collapsible body ───────────────────────────────────────────────────
        self._body = QWidget()
        self._body.setVisible(False)
        body_lay = QVBoxLayout(self._body)
        body_lay.setContentsMargins(14, 4, 14, 12)
        body_lay.setSpacing(4)

        current_group = None
        for key, group, fr_label, left_pole, right_pole, _ in _CREATIVE_DEFS:
            if group != current_group:
                current_group = group
                if body_lay.count() > 0:
                    body_lay.addSpacing(6)
                g_lbl = QLabel(group)
                g_lbl.setStyleSheet(
                    f"color:{C['text_dim']};font-size:9px;font-weight:700;"
                    f"font-family:'Consolas',monospace;letter-spacing:1px;background:transparent;"
                )
                body_lay.addWidget(g_lbl)
            body_lay.addLayout(self._make_slider_row(key, fr_label, left_pole, right_pole))

        # Separator + safety tolerance
        sep = QFrame()
        sep.setFixedHeight(1)
        sep.setStyleSheet(f"background:{C['border']};")
        body_lay.addSpacing(8)
        body_lay.addWidget(sep)
        body_lay.addSpacing(6)

        ct_lbl = QLabel("CONTENU")
        ct_lbl.setStyleSheet(
            f"color:{C['text_dim']};font-size:9px;font-weight:700;"
            f"font-family:'Consolas',monospace;letter-spacing:1px;background:transparent;"
        )
        body_lay.addWidget(ct_lbl)
        body_lay.addLayout(self._make_safety_row())

        # Reset button
        body_lay.addSpacing(8)
        reset_row = QHBoxLayout()
        reset_row.addStretch()
        reset_btn = QPushButton("↺  Réinitialiser")
        reset_btn.setFixedHeight(26)
        reset_btn.setStyleSheet(
            f"QPushButton{{background:{C['bg3']};border:1px solid {C['border']};"
            f"border-radius:6px;color:{C['text_dim']};font-size:10px;padding:0 12px;}}"
            f"QPushButton:hover{{color:{C['text_primary']};border-color:{C['border_bright']};}}"
        )
        reset_btn.clicked.connect(self._reset)
        reset_row.addWidget(reset_btn)
        body_lay.addLayout(reset_row)

        root.addWidget(self._body)

    # ── Helpers ───────────────────────────────────────────────────────────────

    @staticmethod
    def _slider_style() -> str:
        return (
            f"QSlider::groove:horizontal{{height:4px;background:{C['bg3']};border-radius:2px;}}"
            f"QSlider::handle:horizontal{{width:12px;height:12px;margin:-4px 0;"
            f"background:{C['accent']};border-radius:6px;}}"
            f"QSlider::sub-page:horizontal{{background:{C['accent_dim']};border-radius:2px;}}"
        )

    def _make_slider_row(self, key: str, fr_label: str,
                          left_pole: str, right_pole: str) -> QHBoxLayout:
        row = QHBoxLayout()
        row.setSpacing(8)
        row.setContentsMargins(0, 0, 0, 0)

        lbl = QLabel(fr_label)
        lbl.setFixedWidth(82)
        lbl.setStyleSheet(f"color:{C['text_secondary']};font-size:10px;background:transparent;")
        row.addWidget(lbl)

        left_lbl = QLabel(left_pole)
        left_lbl.setFixedWidth(46)
        left_lbl.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        left_lbl.setStyleSheet(f"color:{C['text_dim']};font-size:9px;background:transparent;")
        row.addWidget(left_lbl)

        slider = QSlider(Qt.Orientation.Horizontal)
        slider.setRange(1, 5)
        slider.setValue(3)
        slider.setFixedHeight(18)
        slider.setStyleSheet(self._slider_style())
        self._sliders[key] = slider
        row.addWidget(slider, 1)

        right_lbl = QLabel(right_pole)
        right_lbl.setFixedWidth(56)
        right_lbl.setStyleSheet(f"color:{C['text_dim']};font-size:9px;background:transparent;")
        row.addWidget(right_lbl)

        val_lbl = QLabel("·")
        val_lbl.setFixedWidth(16)
        val_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        val_lbl.setStyleSheet(
            f"color:{C['accent']};font-size:9px;font-weight:700;"
            f"font-family:'Consolas',monospace;background:transparent;"
        )
        row.addWidget(val_lbl)
        slider.valueChanged.connect(
            lambda v, lbl=val_lbl: lbl.setText("·" if v == 3 else str(v))
        )
        return row

    def _make_safety_row(self) -> QHBoxLayout:
        row = QHBoxLayout()
        row.setSpacing(8)
        row.setContentsMargins(0, 0, 0, 0)

        lbl = QLabel("Tolérance")
        lbl.setFixedWidth(82)
        lbl.setStyleSheet(f"color:{C['text_secondary']};font-size:10px;background:transparent;")
        row.addWidget(lbl)

        left_lbl = QLabel("Strict")
        left_lbl.setFixedWidth(46)
        left_lbl.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        left_lbl.setStyleSheet(f"color:{C['text_dim']};font-size:9px;background:transparent;")
        row.addWidget(left_lbl)

        self._safety_slider = QSlider(Qt.Orientation.Horizontal)
        self._safety_slider.setRange(1, 5)
        self._safety_slider.setValue(5)
        self._safety_slider.setFixedHeight(18)
        self._safety_slider.setStyleSheet(self._slider_style())
        row.addWidget(self._safety_slider, 1)

        right_lbl = QLabel("Permissif")
        right_lbl.setFixedWidth(56)
        right_lbl.setStyleSheet(f"color:{C['text_dim']};font-size:9px;background:transparent;")
        row.addWidget(right_lbl)

        self._safety_val_lbl = QLabel("6")
        self._safety_val_lbl.setFixedWidth(16)
        self._safety_val_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._safety_val_lbl.setStyleSheet(
            f"color:{C['accent']};font-size:9px;font-weight:700;"
            f"font-family:'Consolas',monospace;background:transparent;"
        )
        row.addWidget(self._safety_val_lbl)
        self._safety_slider.valueChanged.connect(
            lambda v: self._safety_val_lbl.setText(str(_SAFETY_MAP[v]))
        )
        return row

    # ── Public API ────────────────────────────────────────────────────────────

    def _toggle(self):
        self._expanded = not self._expanded
        self._body.setVisible(self._expanded)
        arrow = "▼" if self._expanded else "▶"
        self._header.setText(f"⚙  Contrôles créatifs    {arrow}")

    def _reset(self):
        for slider in self._sliders.values():
            slider.setValue(3)
        if self._safety_slider:
            self._safety_slider.setValue(5)

    def get_creative_suffix(self) -> str:
        parts = []
        for key, slider in self._sliders.items():
            v = slider.value()
            if v == 3:
                continue
            phrase = _CREATIVE_PHRASES.get(key, {}).get(v, "")
            if phrase:
                parts.append(phrase)
        return ", ".join(parts)

    def get_safety_tolerance(self) -> int:
        return _SAFETY_MAP[self._safety_slider.value()] if self._safety_slider else 6


# ── Prompt preview — translate worker ─────────────────────────────────────────

class _PreviewTranslateWorker(QThread):
    done = pyqtSignal(str)

    def __init__(self, text: str):
        super().__init__()
        self._text = text

    def run(self):
        try:
            from core.lang import translate_to_english
            result = translate_to_english(self._text)
            self.done.emit(result or self._text)
        except Exception:
            self.done.emit(self._text)


# ── Tab T2V ───────────────────────────────────────────────────────────────────

class TabT2V(QScrollArea):
    generation_done = pyqtSignal(dict)

    def __init__(self):
        super().__init__()
        self.setWidgetResizable(True)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._worker = None
        self._enhance_worker = None
        self._active_shot_title: str = ""
        self._active_shot: dict | None = None
        self._batch_queue:   list[dict] = []
        self._batch_total:   int        = 0
        self._batch_idx:     int        = 0
        self._is_batch_mode: bool       = False
        self._last_seed:     int | None = None

        container = QWidget()
        self.setWidget(container)
        lay = QVBoxLayout(container)
        lay.setContentsMargins(20, 20, 20, 20)
        lay.setSpacing(16)

        lay.addWidget(HelpBlock("Studio IA — Générer un clip vidéo IA", [
            "▸ Storyboard : sélectionnez un plan pour pré-remplir le prompt, la durée et la caméra automatiquement.",
            "▸ Batch : cochez plusieurs plans pour les générer en file d'attente.",
            "▸ Casting : ajoutez des personnages pour injecter leurs portraits comme images de référence visuelles.",
            "▸ Style de film : choisissez un preset ou importez une image de référence pour définir l'esthétique du clip.",
            "▸ Continuité : la dernière frame du plan précédent s'injecte automatiquement comme image de départ.",
            "▸ Seed : verrouillez un seed pour garantir la cohérence visuelle entre plusieurs clips.",
            "▸ Contrôles créatifs : réglez l'interprétation, le rythme, la fidélité et la tolérance de contenu.",
            "▸ Mode mock : sans clé fal.ai configurée, la génération est simulée localement (aucun crédit consommé).",
        ], C))

        # ── Référence visuelle (template de style) ────────────────────────────
        self._film_style_frame = QFrame()
        self._film_style_frame.setStyleSheet(
            f"QFrame{{background:rgba(124,107,255,0.08);"
            f"border:1px solid {C['accent_dim']};border-radius:8px;}}"
        )
        _fs_outer = QVBoxLayout(self._film_style_frame)
        _fs_outer.setContentsMargins(14, 12, 14, 12)
        _fs_outer.setSpacing(8)
        _fs_outer.setAlignment(Qt.AlignmentFlag.AlignHCenter)

        _fs_lbl = QLabel("Choisir une référence visuelle")
        _fs_lbl.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        _fs_lbl.setStyleSheet(
            f"color:{C['accent']};font-size:11px;font-weight:700;"
            f"background:transparent;border:none;"
        )
        _fs_outer.addWidget(_fs_lbl)

        # Rectangle fixe — toujours visible, jamais redimensionné
        self._style_ref_path: str = ""
        _preview_frame = QFrame()
        _preview_frame.setFixedSize(160, 140)
        _preview_frame.setStyleSheet(
            f"QFrame{{background:{C['bg2']};border:1px solid {C['border_bright']};"
            f"border-radius:8px;}}"
        )
        _pf_lay = QVBoxLayout(_preview_frame)
        _pf_lay.setContentsMargins(4, 4, 4, 4)
        _pf_lay.setSpacing(0)

        self._style_ref_thumb = QLabel()
        self._style_ref_thumb.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._style_ref_thumb.setStyleSheet("background:transparent;border:none;")
        _pf_lay.addWidget(self._style_ref_thumb, 1)

        _rect_row = QHBoxLayout()
        _rect_row.addStretch()
        _rect_row.addWidget(_preview_frame)
        _rect_row.addStretch()
        _fs_outer.addLayout(_rect_row)

        # Bouton "Template de style" — toujours visible
        self._btn_style_gallery = QPushButton("🖼  Template de style")
        self._btn_style_gallery.setFixedHeight(28)
        self._btn_style_gallery.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_style_gallery.setStyleSheet(
            f"QPushButton{{background:rgba(124,107,255,0.10);"
            f"color:{C['accent']};border:1px solid {C['accent_dim']};"
            f"border-radius:5px;font-size:10px;font-weight:700;padding:0 12px;}}"
            f"QPushButton:hover{{background:rgba(124,107,255,0.20);"
            f"border-color:{C['accent']};}}"
            f"QPushButton:pressed{{background:rgba(124,107,255,0.28);}}"
        )
        self._btn_style_gallery.clicked.connect(self._on_style_gallery)
        _btn_row = QHBoxLayout()
        _btn_row.addStretch()
        _btn_row.addWidget(self._btn_style_gallery)
        _btn_row.addStretch()
        _fs_outer.addLayout(_btn_row)

        # Bouton "Retirer" — visible seulement quand un template est sélectionné
        self._style_ref_clear_btn = QPushButton("× Retirer")
        self._style_ref_clear_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._style_ref_clear_btn.setFixedHeight(24)
        self._style_ref_clear_btn.setVisible(False)
        self._style_ref_clear_btn.setStyleSheet(
            f"QPushButton{{background:transparent;color:{C['text_dim']};"
            f"border:1px solid {C['border']};border-radius:4px;"
            f"font-size:10px;padding:0 8px;}}"
            f"QPushButton:hover{{color:{C['red']};border-color:{C['red']};}}"
            f"QPushButton:pressed{{color:rgba(230,80,80,0.7);}}"
        )
        self._style_ref_clear_btn.clicked.connect(self._on_style_ref_clear)
        _clear_row = QHBoxLayout()
        _clear_row.addStretch()
        _clear_row.addWidget(self._style_ref_clear_btn)
        _clear_row.addStretch()
        _fs_outer.addLayout(_clear_row)

        lay.addWidget(self._film_style_frame)

        # ── Storyboard selector ───────────────────────────────────────────────
        self._storyboard = StoryboardSelector()
        self._storyboard.shot_selected.connect(self._on_shot_selected)
        self._storyboard.shots_selected.connect(self._on_shots_selected)
        lay.addWidget(self._storyboard)

        # Checkbox globale — désactive l'envoi de TOUTES les images de référence
        self._no_ref_global_cb = QCheckBox("⊘  Ne pas envoyer les images de référence")
        self._no_ref_global_cb.setToolTip(
            "Quand cochée, aucune image de référence (personnages, décors, accessoires, "
            "véhicules) n'est envoyée à Seedance — génération texte uniquement."
        )
        self._no_ref_global_cb.setStyleSheet(
            f"QCheckBox{{color:{C['text_dim']};font-size:10px;background:transparent;spacing:5px;}}"
            f"QCheckBox:hover{{color:{C['text_secondary']};}}"
            f"QCheckBox::indicator{{width:13px;height:13px;border:1px solid {C['border']};"
            f"border-radius:3px;background:{C['bg3']};}}"
            f"QCheckBox::indicator:checked{{background:{C['accent_dim']};"
            f"border-color:{C['accent']};}}"
        )
        lay.addWidget(self._no_ref_global_cb)

        # Description du plan sélectionné
        self._shot_desc_lbl = QLabel("")
        self._shot_desc_lbl.setWordWrap(True)
        self._shot_desc_lbl.setVisible(False)
        self._shot_desc_lbl.setStyleSheet(
            f"color:{C['text_secondary']};font-size:11px;font-style:italic;"
            f"background:transparent;border:none;padding:2px 0 4px 0;"
        )
        lay.addWidget(self._shot_desc_lbl)

        # ── Durée + ADN visuel (sur la même ligne) ───────────────────────────
        _dur_outer = QHBoxLayout()
        _dur_outer.setContentsMargins(0, 0, 0, 0)
        _dur_outer.setSpacing(8)

        _dur_lbl_w = QLabel("Durée :")
        _dur_lbl_w.setStyleSheet(
            f"color:{C['text_secondary']};font-size:10px;font-weight:600;"
            f"background:transparent;border:none;"
        )
        _dur_outer.addWidget(_dur_lbl_w)
        self.cb_dur = combo(["4 s", "5 s", "8 s", "10 s", "12 s", "15 s"])
        self.cb_dur.setFixedWidth(100)
        _dur_outer.addWidget(self.cb_dur)
        self._dur_lock_lbl = QLabel("")
        self._dur_lock_lbl.setStyleSheet(
            f"color:{C['red']};font-size:9px;font-family:'Consolas',monospace;"
            f"background:transparent;border:none;"
        )
        _dur_outer.addWidget(self._dur_lock_lbl)

        _dur_outer.addStretch()
        lay.addLayout(_dur_outer)

        self._seed_lock_btn = QPushButton("🔓  ADN visuel — aléatoire")
        self._seed_lock_btn.setCheckable(True)
        self._seed_lock_btn.setFixedHeight(26)
        self._seed_lock_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._seed_lock_btn.setToolTip(
            "Verrouiller l'ADN visuel — même empreinte visuelle pour tous les plans"
        )
        self._seed_lock_btn.setStyleSheet(
            f"QPushButton{{background:transparent;border:1px solid {C['border']};"
            f"border-radius:6px;font-size:10px;font-weight:600;color:{C['text_dim']};"
            f"padding:0 10px;}}"
            f"QPushButton:checked{{background:rgba(124,107,255,0.12);"
            f"border-color:{C['accent']};color:{C['accent']};}}"
            f"QPushButton:hover{{background:{C['bg3']};}}"
        )
        self._seed_lock_btn.toggled.connect(self._on_seed_toggle)
        _t2v_adn_row = QHBoxLayout()
        _t2v_adn_row.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        _t2v_adn_row.addWidget(self._seed_lock_btn)
        lay.addLayout(_t2v_adn_row)

        # ── Panel multi-sélection (visible uniquement lors d'une sélection multiple) ──
        self._multi_panel = QFrame()
        self._multi_panel.setVisible(False)
        if hasattr(self, "_multi_seed_lbl"):
            self._multi_seed_lbl.setVisible(False)
        self._multi_panel.setStyleSheet(
            f"QFrame{{background:rgba(124,107,255,0.07);"
            f"border:1px solid {C['accent_dim']};border-radius:10px;}}"
        )
        _mp_lay = QVBoxLayout(self._multi_panel)
        _mp_lay.setContentsMargins(20, 18, 20, 18)
        _mp_lay.setSpacing(10)
        _mp_header = QHBoxLayout()
        _mp_icon = QLabel("📋")
        _mp_icon.setFixedSize(32, 32)
        _mp_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        _mp_icon.setStyleSheet("font-size:18px;background:transparent;border:none;")
        self._multi_count_lbl = QLabel("0 plans sélectionnés")
        self._multi_count_lbl.setStyleSheet(
            f"color:{C['accent']};font-size:14px;font-weight:700;"
            f"background:transparent;border:none;"
        )
        _mp_header.addWidget(_mp_icon)
        _mp_header.addWidget(self._multi_count_lbl)
        _mp_header.addStretch()
        _mp_lay.addLayout(_mp_header)
        _mp_body1 = QLabel("Vous allez générer plusieurs plans en file d'attente.")
        _mp_body1.setWordWrap(True)
        _mp_body1.setStyleSheet(
            f"color:{C['text_secondary']};font-size:11px;background:transparent;border:none;"
        )
        _mp_lay.addWidget(_mp_body1)
        _mp_body2 = QLabel(
            "Chaque plan possède ses propres paramètres prédéfinis "
            "(prompt, focale, durée, casting…). "
            "Vous ne pouvez pas modifier les paramètres individuellement "
            "lors d'une sélection multiple."
        )
        _mp_body2.setWordWrap(True)
        _mp_body2.setStyleSheet(
            f"color:{C['text_dim']};font-size:10px;font-family:'Consolas',monospace;"
            f"background:transparent;border:none;"
        )
        _mp_lay.addWidget(_mp_body2)

        self._multi_seed_lbl = QLabel("")
        self._multi_seed_lbl.setWordWrap(True)
        self._multi_seed_lbl.setVisible(False)
        self._multi_seed_lbl.setStyleSheet(
            f"color:{C['accent']};font-size:10px;font-weight:700;"
            f"font-family:'Consolas',monospace;background:transparent;border:none;"
        )
        _mp_lay.addWidget(self._multi_seed_lbl)
        lay.addWidget(self._multi_panel)

        # ── Zone d'édition (masquée lors d'une sélection multiple) ───────────
        self._edit_zone = QWidget()
        self._edit_zone.setStyleSheet("background:transparent;")
        _ez_lay = QVBoxLayout(self._edit_zone)
        _ez_lay.setContentsMargins(0, 0, 0, 0)
        _ez_lay.setSpacing(16)

        sep = QFrame()
        sep.setFixedHeight(1)
        sep.setStyleSheet(f"background:{C['border']};")
        _ez_lay.addWidget(sep)

        # ── Continuity / Raccord bar ──────────────────────────────────────────
        self._continuity_bar = _ContinuityBar()
        _ez_lay.addWidget(self._continuity_bar)

        # ── Casting selector ──────────────────────────────────────────────────
        self._casting = CastingSelector()
        self._casting.context_changed.connect(self._on_context_changed)
        _ez_lay.addWidget(self._casting)

        sep2 = QFrame()
        sep2.setFixedHeight(1)
        sep2.setStyleSheet(f"background:{C['border']};")
        _ez_lay.addWidget(sep2)

        # ── Camera & Optics picker ────────────────────────────────────────────
        self._camera_picker = _CameraOpticsPicker()
        self._camera_picker._cb_focal.currentIndexChanged.connect(self._update_injection_banner)
        _ez_lay.addWidget(self._camera_picker)

        # ── Prompt ────────────────────────────────────────────────────────────
        _ez_lay.addWidget(section_label("Prompt"))

        # ── Ref mode badge (teal) — visible quand Seedance passera en mode Référence ──
        self._ref_mode_banner = QFrame()
        self._ref_mode_banner.setStyleSheet(
            f"QFrame{{background:rgba(78,205,196,0.09);"
            f"border:1px solid rgba(78,205,196,0.32);border-radius:6px;}}"
        )
        _rm_lay = QHBoxLayout(self._ref_mode_banner)
        _rm_lay.setContentsMargins(10, 6, 10, 6)
        _rm_lay.setSpacing(0)
        self._ref_mode_lbl = QLabel("")
        self._ref_mode_lbl.setWordWrap(True)
        self._ref_mode_lbl.setStyleSheet(
            f"color:{C['accent']};font-size:9px;font-weight:700;"
            f"font-family:'Consolas',monospace;background:transparent;border:none;"
        )
        _rm_lay.addWidget(self._ref_mode_lbl, 1)
        self._ref_mode_banner.setVisible(False)
        _ez_lay.addWidget(self._ref_mode_banner)

        prompt_frame, self.prompt_ta, self._btn_enhance, self._enhance_auto_cb = prompt_block(
            "Décris ta scène... ex: plan cinématique d'une forêt brumeuse au lever du soleil"
        )
        self._btn_enhance.clicked.connect(self._on_enhance)
        self.prompt_ta.textChanged.connect(self._on_prompt_text_changed)
        _ez_lay.addWidget(prompt_frame)

        # ── Thumbnail strip ───────────────────────────────────────────────────
        self._thumb_strip = _ThumbnailStrip()
        self._thumb_strip.setVisible(False)
        _ez_lay.addWidget(self._thumb_strip)

        # ── Prompt preview (prompt exact envoyé à Seedance) ───────────────────
        self._prompt_preview = self._build_prompt_preview()
        _ez_lay.addWidget(self._prompt_preview)

        # ── Rendu & Audio (toujours visible, y compris en multi-sélection) ───
        self._options_container = QFrame()
        self._options_container.setStyleSheet(
            f"QFrame#options_container{{background:{C['bg2']};border:1px solid {C['border']};"
            f"border-radius:8px;padding:0px;}}"
        )
        self._options_container.setObjectName("options_container")
        _raccords_lay = QVBoxLayout(self._options_container)
        _raccords_lay.setContentsMargins(0, 0, 0, 0)
        _raccords_lay.setSpacing(1)

        _raccords_header = QWidget()
        _raccords_header.setStyleSheet("background:transparent;border:none;")
        _raccords_header_lay = QHBoxLayout(_raccords_header)
        _raccords_header_lay.setContentsMargins(14, 8, 14, 6)
        _raccords_title = QLabel("RENDU & AUDIO")
        _raccords_title.setStyleSheet(
            f"color:{C['accent']};font-size:9px;letter-spacing:2px;"
            f"font-family:'Consolas',monospace;font-weight:700;"
            f"background:transparent;border:none;"
        )
        _raccords_header_lay.addWidget(_raccords_title)
        _raccords_header_lay.addStretch()
        _raccords_lay.addWidget(_raccords_header)

        def _raccord_toggle(title, subtitle, checked):
            w = QFrame()
            w.setStyleSheet(
                f"QFrame{{background:transparent;border:none;border-top:1px solid {C['border']};"
                f"border-radius:0px;padding:4px;}}"
                f"QCheckBox{{color:{C['text_secondary']};background:transparent;border:none;}}"
                f"QCheckBox::indicator{{width:16px;height:16px;"
                f"border:1px solid {C['border_bright']};border-radius:4px;background:{C['bg3']};}}"
                f"QCheckBox::indicator:checked{{background:{C['accent']};border-color:{C['accent']};}}"
                f"QCheckBox::indicator:unchecked:hover{{border-color:{C['accent_dim']};}}"
            )
            lay = QHBoxLayout(w)
            lay.setContentsMargins(14, 8, 14, 8)
            col = QVBoxLayout()
            col.setSpacing(2)
            t = QLabel(title)
            t.setStyleSheet(f"color:{C['text_secondary']};font-size:12px;font-weight:600;border:none;")
            col.addWidget(t)
            if subtitle:
                s = QLabel(subtitle)
                s.setStyleSheet(
                    f"color:{C['text_dim']};font-size:10px;font-family:'Consolas',monospace;border:none;"
                )
                col.addWidget(s)
            cb = QCheckBox()
            cb.setChecked(checked)
            lay.addLayout(col)
            lay.addStretch()
            lay.addWidget(cb)
            return w, cb

        self._audio_toggle_row, _audio_cb_inner = _raccord_toggle(
            "Audio natif", "Seedance génère le son ambiant et les effets sonores du clip", True
        )
        self._audio_cb = _audio_cb_inner
        _raccords_lay.addWidget(self._audio_toggle_row)

        self._music_toggle_row, _music_cb_inner = _raccord_toggle(
            "Musique générée", "Coché → piste musicale présente · Décoché → « no background music » injecté", False
        )
        self._music_cb = _music_cb_inner
        self._music_cb.stateChanged.connect(self._update_injection_banner)
        self._music_cb.stateChanged.connect(self._refresh_prompt_preview)
        _raccords_lay.addWidget(self._music_toggle_row)

        self._subtitle_toggle_row, _subtitle_cb_inner = _raccord_toggle(
            "Sous-titres", "Coché → sous-titres incrustés · Décoché → « no subtitles » injecté", False
        )
        self._subtitle_cb = _subtitle_cb_inner
        self._subtitle_cb.stateChanged.connect(self._refresh_prompt_preview)
        _raccords_lay.addWidget(self._subtitle_toggle_row)

        self._film_anchor_toggle_row, _film_anchor_cb_inner = _raccord_toggle(
            "Prise de vue réelle",
            "Ancre le rendu dans le filmage réel — ARRI 35mm, grain argentique, peau naturelle, no CGI, no 3D  ·  Automatiquement ignoré si le style 'Film réaliste' ou 'Photoréaliste' est actif (déjà inclus)",
            False,
        )
        self._film_anchor_cb = _film_anchor_cb_inner
        self._film_anchor_cb.stateChanged.connect(self._refresh_prompt_preview)
        _raccords_lay.addWidget(self._film_anchor_toggle_row)

        self._raccord_auto_toggle_row, _raccord_auto_cb_inner = _raccord_toggle(
            "Raccord automatique",
            "Utilise la dernière frame du plan précédent comme point de départ (I2V) — enchaîne les plans comme un Extend",
            False,
        )
        self._raccord_auto_cb = _raccord_auto_cb_inner
        _raccords_lay.addWidget(self._raccord_auto_toggle_row)

        self._dyn_cam_toggle_row = toggle_row(
            "Caméra dynamique",
            "Changement d'angle toutes les 2 secondes",
            False,
        )
        self._dyn_cam_cb = self._dyn_cam_toggle_row.findChild(QCheckBox)
        self._dyn_cam_cb.stateChanged.connect(self._refresh_prompt_preview)
        self._dyn_cam_toggle_row.setVisible(True)  # caché quand shot actif
        _raccords_lay.addWidget(self._dyn_cam_toggle_row)  # → RENDU & AUDIO, après Raccord automatique

        lay.addWidget(self._edit_zone)

        # ── Rendu & Audio (toujours visible, y compris multi-sélection) ───────
        lay.addWidget(self._options_container)

        # ── Contrôles créatifs ────────────────────────────────────────────────
        self._creative = _CreativeControlPanel()
        lay.addWidget(self._creative)

        # ── Paramètres de génération (toujours visibles, y compris en multi-sélection) ──
        grid = QGridLayout()
        grid.setSpacing(12)
        # Moteurs ouverts à TOUS ceux compatibles avec le workflow storyboard —
        # les t2v purs (Veo, Sora) sont écartés. use_keyframes=False : le Cinéma
        # n'envoie JAMAIS de keyframes de moods (mécanisme Live/Mapping), les
        # libellés n'affichent donc que raccord i2v + réfs. Seedance 2.0 marqué
        # « recommandé » — les autres moteurs ne donnent pas encore d'aussi
        # bons résultats sur ce workflow.
        from core.engine_caps import sequence_engines
        self.cb_model = combo(sequence_engines(_ENGINES, use_keyframes=False,
                                               recommended=("seedance-2.0",)))
        self.cb_model.currentIndexChanged.connect(self._on_engine_changed)
        self.cb_ratio = combo(["16:9 — Paysage", "9:16 — Portrait", "4:3", "3:4"])
        # Résolutions initiales pour Seedance 2.0 (moteur par défaut)
        _default_key = self.cb_model.currentData() or "seedance-2.0"
        _default_res = _ENGINE_RESOLUTIONS.get(_default_key, ["1080p", "720p", "480p"])
        self.cb_res = combo(_default_res)

        for (row, col), lbl, widget in [
            ((0, 0), "Moteur de génération", self.cb_model),
            ((0, 1), "Ratio",      self.cb_ratio),
            ((1, 0), "Résolution", self.cb_res),
        ]:
            g = QWidget()
            l = QVBoxLayout(g)
            l.setContentsMargins(0, 0, 0, 0)
            l.setSpacing(6)
            l.addWidget(section_label(lbl))
            l.addWidget(widget)
            grid.addWidget(g, row, col)
        lay.addLayout(grid)

        # ── Banner compatibilité références (moteurs texte-seul) ───────────────
        self._ref_compat_banner = QLabel(
            "⚠  Ce moteur ne supporte pas les images de référence nativement. "
            "Vos personnages, décors et accessoires seront convertis en mots-clés de style "
            "via Claude Vision et ajoutés au prompt texte."
        )
        self._ref_compat_banner.setWordWrap(True)
        self._ref_compat_banner.setStyleSheet(
            "background:rgba(255,79,106,0.12);"
            f"color:{C['red']};"
            "border:1px solid rgba(255,79,106,0.45);"
            "border-radius:6px;padding:8px 12px;font-size:11px;font-weight:600;"
        )
        self._ref_compat_banner.setVisible(False)
        lay.addWidget(self._ref_compat_banner)

        self._davinci_bar = _DaVinciBar()

        # ── GCS warning (shown after failed uploads) ───────────────────────────
        self._gcs_warning = _GCSWarningBar()
        lay.addWidget(self._gcs_warning)

        self.progress = ProgressBlock()
        lay.addWidget(self.progress)

        self.btn_generate = QPushButton("▶▶  Lancer la file d'attente")
        self.btn_generate.setMinimumHeight(46)
        self.btn_generate.clicked.connect(self._start_with_credit_check)
        self._billing_worker = None
        self._balance_lbl = QLabel("")
        self._balance_lbl.setStyleSheet(
            f"color:{C['text_dim']};font-size:9px;"
            f"font-family:'Consolas',monospace;background:transparent;"
        )

        _rep_lbl = QLabel("×")
        _rep_lbl.setFixedWidth(14)
        _rep_lbl.setStyleSheet(f"color:{C['text_dim']};font-size:13px;background:transparent;")
        self._spinbox_repeat = QSpinBox()
        self._spinbox_repeat.setRange(1, 10)
        self._spinbox_repeat.setValue(1)
        self._spinbox_repeat.setFixedSize(54, 46)
        self._spinbox_repeat.setToolTip(
            "Nombre de générations (1–10)\n"
            "En mode multi-plan, répète chaque plan N fois."
        )
        self._spinbox_repeat.setStyleSheet(f"""
            QSpinBox{{background:{C['bg3']};border:1px solid {C['border']};
            border-radius:8px;color:{C['text_primary']};font-size:13px;font-weight:700;
            padding:0 4px;}}
            QSpinBox::up-button,QSpinBox::down-button{{width:16px;border:none;
            background:{C['bg3']};border-radius:3px;}}
        """)

        self.btn_cancel = QPushButton("Annuler")
        self.btn_cancel.setVisible(False)
        self.btn_cancel.setFixedWidth(100)
        self.btn_cancel.setStyleSheet(f"""
            QPushButton{{background:{C['bg3']};color:{C['text_secondary']};
            border:1px solid {C['border']};border-radius:8px;font-size:12px;
            font-weight:700;padding:13px;}}
            QPushButton:hover{{background:{C['border']};color:{C['text_primary']};}}
        """)
        self.btn_cancel.clicked.connect(self.cancel_generation)

        self._import_cb = QCheckBox("Import auto dans DaVinci Media Pool après génération")
        _dv_ok = resolve.is_connected()
        self._import_cb.setChecked(_dv_ok)
        self._import_cb.setEnabled(_dv_ok)
        self._import_cb.setToolTip(
            "" if _dv_ok
            else "DaVinci Resolve Studio requis — connectez le bridge pour activer cette option"
        )
        self._import_cb.setStyleSheet(f"color:{C['text_secondary']};font-size:11px;")
        lay.addWidget(self._import_cb)

        btn_row = QHBoxLayout()
        btn_row.setContentsMargins(0, 0, 0, 0)
        btn_row.setSpacing(8)
        btn_row.addWidget(self.btn_generate, 1)
        btn_row.addWidget(_rep_lbl)
        btn_row.addWidget(self._spinbox_repeat)
        btn_row.addWidget(self.btn_cancel)
        lay.addLayout(btn_row)

        balance_row = QHBoxLayout()
        balance_row.setContentsMargins(0, 0, 0, 0)
        balance_row.addStretch()
        balance_row.addWidget(self._balance_lbl)
        lay.addLayout(balance_row)

        # ── Ouvrir le dossier des vidéos (toujours visible) ──────────────────
        self._btn_open_folder = QPushButton("📁  Ouvrir le dossier des vidéos")
        self._btn_open_folder.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_open_folder.setStyleSheet(f"""
            QPushButton{{background:transparent;color:{C['text_secondary']};
            border:1px solid {C['border']};border-radius:8px;font-size:11px;
            padding:6px 14px;}}
            QPushButton:hover{{background:{C['bg3']};color:{C['text_primary']};}}
        """)
        self._btn_open_folder.clicked.connect(self._open_output_folder)

        _dav_row = QHBoxLayout()
        _dav_row.setContentsMargins(0, 0, 0, 0)
        _dav_row.setSpacing(10)
        _dav_row.addWidget(self._davinci_bar, 1)
        _dav_row.addWidget(self._btn_open_folder)
        lay.addLayout(_dav_row)
        self._davinci_bar.connection_changed.connect(self._on_davinci_connection_changed)

        # ── Encart prix (sous la barre DaVinci) ───────────────────────────────
        price_frame = QFrame()
        price_frame.setStyleSheet(
            f"QFrame{{background:rgba(245,197,24,0.05);"
            f"border:1px solid rgba(245,197,24,0.18);border-radius:8px;}}"
        )
        price_h = QHBoxLayout(price_frame)
        price_h.setContentsMargins(14, 8, 14, 8)
        price_h.setSpacing(12)
        price_lbl = QLabel(
            "💰  Génération facturée via fal.ai (Seedance 2.0)"
            "  ·  Tarifs détaillés dans le Manuel d'utilisation"
        )
        price_lbl.setWordWrap(True)
        price_lbl.setStyleSheet(
            f"color:{C['text_dim']};font-size:9px;"
            f"font-family:'Consolas',monospace;background:transparent;"
        )
        price_h.addWidget(price_lbl, 1)
        btn_tarifs = QPushButton("📖  Tarifs")
        btn_tarifs.setFixedSize(72, 24)
        btn_tarifs.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_tarifs.setStyleSheet(
            f"QPushButton{{background:transparent;color:{C['text_secondary']};"
            f"border:1px solid {C['border_bright']};border-radius:5px;"
            f"font-size:9px;font-weight:700;padding:0;}}"
            f"QPushButton:hover{{background:rgba(245,197,24,0.12);"
            f"color:#f5c518;border-color:rgba(245,197,24,0.50);}}"
        )
        btn_tarifs.clicked.connect(self._open_manual_tarifs)
        price_h.addWidget(btn_tarifs)
        lay.addWidget(price_frame)

        lay.addStretch()

        self._refresh_style_badge()

    # ── Storyboard + context handlers ─────────────────────────────────────────

    def _on_shot_selected(self, shot: dict):
        try:
            self._on_shot_selected_impl(shot)
        except Exception as exc:
            import traceback
            print(f"[T2V] _on_shot_selected error: {exc}\n{traceback.format_exc()}", flush=True)

    def _on_shot_selected_impl(self, shot: dict):
        # Reset multi-select UI
        self._multi_panel.setVisible(False)
        if hasattr(self, "_multi_seed_lbl"):
            self._multi_seed_lbl.setVisible(False)
        self._edit_zone.setVisible(True)
        self._camera_picker._cb_focal.setEnabled(True)
        # Retire le placeholder "— s" inséré lors de la multi-sélection
        self.cb_dur.blockSignals(True)
        if self.cb_dur.itemText(0) == "— s":
            self.cb_dur.removeItem(0)
        self.cb_dur.blockSignals(False)
        if not self._is_batch_mode:
            self.btn_generate.setText("▶▶  Lancer la file d'attente")

        if not shot:
            self._active_shot_title = ""
            self._active_shot = None
            self._active_shot_apercus = []
            self._camera_picker.set_focal_from_shot("")
            self._casting.set_active_shot({})
            self._continuity_bar.update_shot({}, [])
            self.cb_dur.setEnabled(True)
            self.cb_dur.setToolTip("")
            if hasattr(self, "_dur_lock_lbl"):
                self._dur_lock_lbl.setText("")
            self._shot_desc_lbl.setVisible(False)
            self._shot_desc_lbl.setText("")
            if hasattr(self, "_dyn_cam_toggle_row"):
                self._dyn_cam_toggle_row.setVisible(True)
            self._update_injection_banner()
            self._refresh_prompt_preview()
            return

        # Hide dynamic camera option when a storyboard shot is active
        if hasattr(self, "_dyn_cam_toggle_row"):
            self._dyn_cam_toggle_row.setVisible(False)
            if self._dyn_cam_cb:
                self._dyn_cam_cb.setChecked(False)

        # Show shot description below the storyboard strip
        _desc = (shot.get("description") or shot.get("comments") or "").strip()
        if _desc:
            _num = shot.get("number", "")
            _title = shot.get("scene_title") or shot.get("decor_name") or ""
            _prefix = f"Plan {_num}" + (f" — {_title}" if _title else "") + " : "
            _max = 200
            _text = _desc if len(_desc) <= _max else _desc[:_max].rstrip() + "…"
            self._shot_desc_lbl.setText(_prefix + _text)
            self._shot_desc_lbl.setVisible(True)
        else:
            self._shot_desc_lbl.setVisible(False)
            self._shot_desc_lbl.setText("")

        # Update raccord bar with all shots in the current storyboard
        all_shots = sb_api.list_shots()
        self._continuity_bar.update_shot(shot, all_shots)

        # Auto-set duration from shot
        dur = shot.get("duration")
        if dur is not None:
            try:
                self._set_duration_from_shot(float(dur))
            except (TypeError, ValueError):
                pass

        # Store shot title for file naming — format SQ{seq}_P{num}
        try:
            _seq = int(shot.get("seq_num", 0))
        except (TypeError, ValueError):
            _seq = 0
        try:
            _num = int(shot.get("number", 0))
        except (TypeError, ValueError):
            _num = 0
        if _seq and _num:
            self._active_shot_title = f"SQ{_seq}_P{_num}"
        elif _num:
            self._active_shot_title = f"P{_num}"
        else:
            self._active_shot_title = "plan"

        # Track active shot for last-frame extraction
        self._active_shot = shot

        # Auto-set focal from shot before set_active_shot so the banner is consistent
        self._camera_picker.set_focal_from_shot(shot.get("focal", ""))

        # Load aperçu/mood images for thumbnail strip
        _apercu_data = sb_api.load_apercus(shot.get("id", ""))
        self._active_shot_apercus = [
            p for p in _apercu_data.get("paths", []) if os.path.isfile(p)
        ]

        # Auto-select entities from shot
        self._casting.set_active_shot(shot)

        # Fill prompt
        if shot.get("seedance_prompt"):
            self.prompt_ta.setPlainText(shot["seedance_prompt"])
            self._update_injection_banner()
            return
        _num   = shot.get("number", "")
        _title = shot.get("scene_title") or shot.get("decor_name") or ""
        parts  = []
        header = f"Plan {_num}" if _num else "Plan"
        if _title:
            header += f" — {_title}"
        parts.append(header)
        char_names = shot.get("character_names", [])
        if char_names:
            parts.append(f"Personnages : {', '.join(char_names)}")
        if shot.get("decor_name"):
            parts.append(f"Décor : {shot['decor_name']}")
        if shot.get("shot_time"):
            parts.append(f"Heure : {shot['shot_time']}")
        if shot.get("camera_movement"):
            parts.append(f"Mouvement : {shot['camera_movement']}")
        if shot.get("focal"):
            parts.append(f"Focale : {shot['focal']}")
        if shot.get("comments"):
            parts.append(shot["comments"])
        self.prompt_ta.setPlainText("\n".join(parts))
        self._update_injection_banner()
        self._refresh_prompt_preview()

    def _on_shots_selected(self, shots: list):
        count = len(shots)
        if count < 2:
            return
        self._multi_count_lbl.setText(f"{count} plans sélectionnés")
        self._multi_panel.setVisible(True)
        self._edit_zone.setVisible(False)
        self._shot_desc_lbl.setVisible(False)
        self.cb_dur.blockSignals(True)
        self.cb_dur.insertItem(0, "— s")
        self.cb_dur.setCurrentIndex(0)
        self.cb_dur.blockSignals(False)
        self.cb_dur.setEnabled(False)
        self.cb_dur.setToolTip("🔒 Paramètres propres à chaque plan")
        if hasattr(self, "_dur_lock_lbl"):
            self._dur_lock_lbl.setText("🔒 Paramètres propres à chaque plan")
        self._camera_picker._cb_focal.setEnabled(False)

        # Auto-verrouille l'ADN visuel pour cohérence entre les clips
        if not self._seed_lock_btn.isChecked():
            self._seed_lock_btn.setChecked(True)
        if self._last_seed is None:
            import random
            self._last_seed = random.randint(1, 999_999_999)
        if hasattr(self, "_multi_seed_lbl"):
            self._multi_seed_lbl.setText("🔒  ADN visuel verrouillé — cohérence visuelle activée")
            self._multi_seed_lbl.setVisible(True)

        if not self._is_batch_mode:
            self.btn_generate.setText("▶▶  Lancer la file d'attente")

    def _on_context_changed(self, _ctx: str):
        casting_images = self._casting.get_selected_images()
        self._thumb_strip.update_images(casting_images)
        self._update_injection_banner()
        self._refresh_prompt_preview()

    # ── Prompt preview ────────────────────────────────────────────────────────

    def _build_prompt_preview(self) -> QFrame:
        from PyQt6.QtCore import QTimer as _QTimer
        self._preview_translate_timer = _QTimer(self)
        self._preview_translate_timer.setSingleShot(True)
        self._preview_translate_timer.setInterval(1600)
        self._preview_translate_timer.timeout.connect(self._start_preview_translate)
        self._preview_translate_worker = None
        self._preview_translated_text: str | None = None
        self._preview_expanded = False  # collapsed by default

        frame = QFrame()
        frame.setStyleSheet(
            f"QFrame{{background:{C['bg2']};border:1px solid rgba(255,79,106,0.45);"
            f"border-radius:10px;}}"
        )
        lay = QVBoxLayout(frame)
        lay.setContentsMargins(14, 0, 14, 0)
        lay.setSpacing(0)

        # ── Header cliquable ──────────────────────────────────────────────────
        hdr_w = QWidget()
        hdr_w.setCursor(Qt.CursorShape.PointingHandCursor)
        hdr_w.setStyleSheet("background:transparent;")
        hdr_lay = QHBoxLayout(hdr_w)
        hdr_lay.setContentsMargins(0, 9, 0, 9)
        hdr_lay.setSpacing(6)

        self._preview_arrow = QLabel("▶")
        self._preview_arrow.setStyleSheet(
            f"color:{C['red']};font-size:9px;background:transparent;border:none;"
        )
        _h_lbl = QLabel("◈  PANDORA — Prompt envoyé à Seedance")
        _h_lbl.setStyleSheet(
            f"color:{C['red']};font-size:10px;font-weight:700;"
            f"background:transparent;border:none;"
        )
        self._preview_spinner = QLabel()
        self._preview_spinner.setStyleSheet(
            f"color:{C['text_dim']};font-size:9px;font-style:italic;"
            f"background:transparent;border:none;"
        )
        self._preview_spinner.setVisible(False)
        _note = QLabel("traduit auto · sans upload images")
        _note.setStyleSheet(
            f"color:{C['text_dim']};font-size:9px;background:transparent;border:none;"
        )
        hdr_lay.addWidget(self._preview_arrow)
        hdr_lay.addWidget(_h_lbl)
        hdr_lay.addStretch()
        hdr_lay.addWidget(self._preview_spinner)
        hdr_lay.addWidget(_note)
        lay.addWidget(hdr_w)

        # ── Corps (masqué par défaut) ─────────────────────────────────────────
        self._preview_body_container = QWidget()
        self._preview_body_container.setStyleSheet("background:transparent;")
        self._preview_body_container.setVisible(False)
        body_lay = QVBoxLayout(self._preview_body_container)
        body_lay.setContentsMargins(0, 0, 0, 10)
        body_lay.setSpacing(6)

        _sep = QFrame()
        _sep.setFrameShape(QFrame.Shape.HLine)
        _sep.setStyleSheet("background:rgba(255,79,106,0.30);max-height:1px;")
        body_lay.addWidget(_sep)

        self._preview_body = QLabel("(prompt vide)")
        self._preview_body.setWordWrap(True)
        self._preview_body.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )
        self._preview_body.setStyleSheet(
            f"color:{C['text_secondary']};font-size:10px;"
            f"font-family:'Consolas',monospace;"
            f"background:transparent;border:none;"
        )
        body_lay.addWidget(self._preview_body)
        lay.addWidget(self._preview_body_container)

        def _toggle():
            self._preview_expanded = not self._preview_expanded
            self._preview_arrow.setText("▼" if self._preview_expanded else "▶")
            self._preview_body_container.setVisible(self._preview_expanded)
            if self._preview_expanded:
                self._refresh_prompt_preview()

        hdr_w.mousePressEvent = lambda e: _toggle()

        return frame

    def _on_prompt_text_changed(self):
        self._preview_translated_text = None
        self._refresh_prompt_preview()
        self._preview_translate_timer.start()

    def _refresh_prompt_preview(self, *_):
        if not hasattr(self, "_preview_body") or not self._preview_expanded:
            return
        text = self._build_full_preview_text(self._preview_translated_text)
        self._preview_body.setText(text)

    def _start_preview_translate(self):
        prompt_fr = self.prompt_ta.toPlainText().strip()
        if not prompt_fr:
            return
        # Anti-crash : un QThread basé sur run() n'a pas de boucle d'événements, donc
        # quit() est INOPÉRANT. Réassigner la variable laissait l'ancien thread être
        # collecté par le GC PENDANT qu'il tournait → « QThread: Destroyed while
        # thread is still running » → plantage de l'app (typiquement en sélectionnant
        # des plans coup sur coup). abandon_thread() le garde référencé + bloque ses
        # signaux jusqu'à sa fin.
        if self._preview_translate_worker is not None:
            from core.worker import abandon_thread
            abandon_thread(self._preview_translate_worker)
            self._preview_translate_worker = None
        self._preview_spinner.setText("⟳  traduction…")
        self._preview_spinner.setVisible(True)
        self._preview_translate_worker = _PreviewTranslateWorker(prompt_fr)
        self._preview_translate_worker.done.connect(self._on_preview_translated)
        self._preview_translate_worker.start()

    def _on_preview_translated(self, translated: str):
        self._preview_spinner.setVisible(False)
        self._preview_translated_text = translated
        self._refresh_prompt_preview()

    def _build_full_preview_text(self, translated_user: str | None = None) -> str:
        """Builds the complete preview text shown in the ◈ PANDORA block."""
        lines = []

        # ── PROMPT ────────────────────────────────────────────────────────────
        user_text = translated_user if translated_user is not None else self.prompt_ta.toPlainText().strip()
        if not user_text:
            import core.style as _sa_e
            _cam_e = self._camera_picker.get_suffix() if hasattr(self, "_camera_picker") else ""
            _vs_e = _sa_e.get_video_suffix_no_cam() if _cam_e else _sa_e.get_video_suffix()
            if not _vs_e and not _cam_e:
                return "(prompt vide — aucun style ni caméra configurés)"
            _hint = ["(prompt vide — éléments qui seront ajoutés à votre texte :)"]
            if _cam_e:
                _hint.append(f"+ Caméra : {_cam_e}")
            if _vs_e:
                _hint.append(f"+ Style : {_vs_e}")
            return "\n".join(_hint)

        context = self._casting.get_context()
        fp = (context + user_text) if context else user_text

        if self._active_shot:
            _focal = self._active_shot.get("focal", "")
            if _focal:
                from core.camera_data import focal_to_framing_prefix
                _fr = focal_to_framing_prefix(_focal)
                if _fr:
                    fp = f"{_fr} — {fp}"

        if (hasattr(self, "_dyn_cam_cb") and self._dyn_cam_cb
                and self._dyn_cam_cb.isChecked() and not self._active_shot):
            fp = (f"{fp}, change the camera angle every 2 seconds "
                  "alternating between several types of shots")
        else:
            cam = self._camera_picker.get_suffix()
            if cam:
                fp = f"{fp}, {cam}"

        import core.style as _style_api_prev
        _film_anchor_active_prev = hasattr(self, "_film_anchor_cb") and self._film_anchor_cb and self._film_anchor_cb.isChecked()
        _film_covered_prev = _style_api_prev.get_style_key() in {"realistic"}
        if _film_anchor_active_prev and not _film_covered_prev:
            fp = (f"{fp}, shot on ARRI Alexa 35mm film, photorealistic live action footage, "
                  "real human actors, authentic film grain, natural skin texture and pores, "
                  "no CGI, no 3D render, no computer animation, no digital art, "
                  "organic depth of field, natural practical lighting")

        cont = self._continuity_bar.build_continuity_prefix()
        if cont:
            fp = f"{cont}\n{fp}"

        if not (hasattr(self, "_subtitle_cb") and self._subtitle_cb
                and self._subtitle_cb.isChecked()):
            fp = f"{fp}, no subtitles"

        fp = (f"{fp}, 4K ultra HD, rich detail, sharp clarity, "
              "cinematic textures, stable picture")

        _SHOT_TIME_EN = {
            "Jour":            "strict daylight, natural midday sun, bright neutral light, no golden hour, no sunset",
            "Nuit":            "nighttime scene, dark environment, night lighting, no daylight, moonlight or artificial light",
            "Lever du soleil": "sunrise, warm golden morning light, sun just above the horizon, soft pink-orange sky",
            "Coucher du soleil": "sunset, golden hour, warm amber-orange light, sun low on the horizon",
        }
        _st = (self._active_shot.get("shot_time") if self._active_shot else "") or ""
        ts = _SHOT_TIME_EN.get(_st, "")
        if ts:
            fp = f"{ts}, {fp}"

        import core.style as _sa
        _prev_cam = self._camera_picker.get_suffix() if hasattr(self, "_camera_picker") else ""
        vs = _sa.get_video_suffix_no_cam() if _prev_cam else _sa.get_video_suffix()
        if vs:
            fp = f"{fp}, {vs}"

        music_on = (hasattr(self, "_music_cb") and self._music_cb
                    and self._music_cb.isChecked())
        if not music_on:
            fp = (f"{fp}, no music, no background music, no soundtrack, "
                  "no musical score, natural ambient sound only")

        cs = self._creative.get_creative_suffix()
        if cs:
            fp = f"{fp}, {cs}"

        _pfx = "━━━ PROMPT " + ("(traduit) " if translated_user is not None else "(traduction…) ") + "━━━"
        lines.append(_pfx)
        lines.append(fp)

        # ── IMAGES ENVOYÉES ───────────────────────────────────────────────────
        img_lines = []

        # Personnages
        char_entries = []
        for cid in self._casting._selected_char_ids:
            char_data = self._casting._char_data_map.get(cid, {})
            name = char_data.get("name", "?")
            img = char_data.get("sheet_path", "") or char_data.get("image_path", "")
            if img and os.path.isfile(img):
                char_entries.append(f"{name} [{os.path.basename(img)}]")
            else:
                char_entries.append(f"{name} [⚠ sans portrait]")
        if char_entries:
            img_lines.append(f"Personnages : {' · '.join(char_entries)}")

        # Décor
        _eff_decor_id = self._casting._selected_decor_id or (self._active_shot or {}).get("decor_id", "")
        _decor_meta = self._casting._decors_meta.get(_eff_decor_id, {}) if _eff_decor_id else {}
        _decor_name = _decor_meta.get("name", "") or (self._active_shot or {}).get("decor_name", "")
        _decor_img  = _decor_meta.get("image_path", "")
        if _decor_name:
            _di = f" [{os.path.basename(_decor_img)}]" if _decor_img and os.path.isfile(_decor_img) else ""
            img_lines.append(f"Décor : {_decor_name}{_di}")

        # Accessoires, HMC, Véhicules
        acc_e, hmc_e, veh_e = [], [], []
        for iid in self._casting._selected_items:
            m = self._casting._items_meta.get(iid, {})
            n = m.get("name", "?")
            i = m.get("image_path", "")
            _ie = f" [{os.path.basename(i)}]" if i and os.path.isfile(i) else ""
            kind = m.get("_kind", "")
            (hmc_e if kind == "hmc" else acc_e).append(f"{n}{_ie}")
        for vid in self._casting._selected_vehicles:
            m = self._casting._vehicles_meta.get(vid, {})
            n = m.get("name", "?")
            i = m.get("image_path", "")
            _ie = f" [{os.path.basename(i)}]" if i and os.path.isfile(i) else ""
            veh_e.append(f"{n}{_ie}")
        if acc_e:
            img_lines.append(f"Accessoires : {' · '.join(acc_e)}")
        if hmc_e:
            img_lines.append(f"HMC : {' · '.join(hmc_e)}")
        if veh_e:
            img_lines.append(f"Véhicules : {' · '.join(veh_e)}")

        # Style de film (image de référence)
        _sref = getattr(self, "_style_ref_path", "")
        if _sref and os.path.isfile(_sref):
            img_lines.append(f"Template visuel : [{os.path.basename(_sref)}] → analysé par Claude Vision")

        if img_lines:
            lines.append("")
            lines.append("━━━ IMAGES ENVOYÉES ━━━")
            lines.extend(img_lines)

        # ── PARAMÈTRES ────────────────────────────────────────────────────────
        param_lines = []

        # Caméra
        if hasattr(self, "_camera_picker"):
            _prefs = cam_prefs.get_camera_prefs()
            _body = _prefs.get("camera_body", "").strip()
            if _body:
                _brand = _prefs.get("camera_brand", "").strip()
                param_lines.append(f"Caméra : {(_brand + ' ' + _body).strip()}")
            _opts = _prefs.get("optics_series", "").strip()
            if _opts:
                _ob = _prefs.get("optics_brand", "").strip()
                param_lines.append(f"Optiques : {(_ob + ' ' + _opts).strip()}")
            _filters = _prefs.get("filters", [])
            if _filters:
                param_lines.append(f"Filtre(s) : {', '.join(_filters)}")
            _mic = " ".join(filter(None, [_prefs.get("mic_category","").strip(), _prefs.get("mic_model","").strip()]))
            if _mic:
                param_lines.append(f"Micro : {_mic}")
            _shot_focal = (self._active_shot or {}).get("focal", "")
            if _shot_focal:
                from core.camera_data import focal_to_framing_prefix
                _framing = focal_to_framing_prefix(_shot_focal)
                _fstr = f" → « {_framing} »" if _framing else ""
                param_lines.append(f"Focale : {_shot_focal}{_fstr}  ← storyboard")

        # Son
        audio_on = (hasattr(self, "_audio_cb") and self._audio_cb and self._audio_cb.isChecked())
        subtitle_on = (hasattr(self, "_subtitle_cb") and self._subtitle_cb and self._subtitle_cb.isChecked())
        snd = []
        snd.append(f"Audio natif : {'✓' if audio_on else '✗'}")
        snd.append(f"Musique : {'✓' if music_on else '✗ → no background music injecté'}")
        snd.append(f"Sous-titres : {'✓' if subtitle_on else '✗ → no subtitles injecté'}")
        param_lines.append("Son : " + "  ·  ".join(snd))

        # Template / style vidéo
        if vs:
            _sname = (_sa.get_style() or {}).get("label", "Style")
            _vshort = vs[:80] + ("…" if len(vs) > 80 else "")
            param_lines.append(f"Template : {_sname} → « {_vshort} »")

        # ADN visuel
        seed = self._get_seed()
        if seed is not None:
            param_lines.append(f"ADN visuel : {seed} 🔒")

        # Contrôles créatifs
        if cs:
            _cs_short = cs[:100] + ("…" if len(cs) > 100 else "")
            param_lines.append(f"Créatifs : {_cs_short}")

        if param_lines:
            lines.append("")
            lines.append("━━━ PARAMÈTRES ━━━")
            lines.extend(param_lines)

        return "\n".join(lines)

    def _assemble_preview_prompt(self, translated_user: str | None = None) -> str:
        return self._build_full_preview_text(translated_user)

    def _update_injection_banner(self, *_):
        if not hasattr(self, "_ref_mode_banner"):
            return

        ref_imgs = self._casting.get_ref_images()
        chars_missing = self._casting.get_chars_without_images()
        style_ref_path = getattr(self, "_style_ref_path", "")
        style_ref_active = bool(style_ref_path and os.path.isfile(style_ref_path))

        lines = []
        if ref_imgs or style_ref_active:
            total = len(ref_imgs) + (1 if style_ref_active else 0)
            ctx_parts = self._casting.get_context_parts()
            char_with_img = [
                d.get("name", "") for cid, d in self._casting._char_data_map.items()
                if os.path.isfile(d.get("sheet_path", "") or d.get("image_path", "") or "")
            ]
            slots = []
            if char_with_img:
                slots.append(f"Perso. : {', '.join(char_with_img)}")
            if ctx_parts.get("decor_name"):
                slots.append(f"Décor : {ctx_parts['decor_name']}")
            others = [*ctx_parts.get("vehicle_names", []),
                      *[self._casting._items_meta.get(i, {}).get("name", "")
                        for i in self._casting._selected_items]]
            others = [o for o in others if o]
            if others:
                slots.append(f"Autres : {', '.join(others)}")
            if style_ref_active:
                slots.append(f"Style : {os.path.basename(style_ref_path)}")
            txt = f"◈ MODE RÉFÉRENCE ACTIF — {total} image(s) envoyée(s) à Seedance"
            if slots:
                txt += "\n   " + "  ·  ".join(slots)
            lines.append(txt)

        if chars_missing:
            names = ", ".join(f'"{n}"' for n in chars_missing)
            s = "s" if len(chars_missing) > 1 else ""
            lines.append(
                f"⚠ Portrait{s} manquant{s} : {names} — Seedance génère un personnage aléatoire sans portrait."
            )

        if lines:
            self._ref_mode_lbl.setText("\n".join(lines))
            self._ref_mode_banner.setVisible(True)
        else:
            self._ref_mode_banner.setVisible(False)

    # ── Generation ────────────────────────────────────────────────────────────

    _DUR_OPTIONS = [4, 5, 8, 10, 12, 15]

    def _get_duration(self) -> int:
        idx = self.cb_dur.currentIndex()
        return self._DUR_OPTIONS[idx] if 0 <= idx < len(self._DUR_OPTIONS) else 5

    def _set_duration_from_shot(self, seconds: float):
        """Sets the duration combo to the option closest to the shot's duration, then locks it."""
        best_idx = min(range(len(self._DUR_OPTIONS)),
                       key=lambda i: abs(self._DUR_OPTIONS[i] - seconds))
        self.cb_dur.setCurrentIndex(best_idx)
        self.cb_dur.setEnabled(False)
        self.cb_dur.setToolTip("🔒 Durée définie par le storyboard")
        if hasattr(self, "_dur_lock_lbl"):
            self._dur_lock_lbl.setText(f"🔒 {self._DUR_OPTIONS[best_idx]}s — depuis storyboard")

    def _get_model(self) -> str:
        return self.cb_model.currentData() or "seedance-2.0"

    def _on_engine_changed(self):
        key = self._get_model()
        fixed_res = key in _FIXED_RES_ENGINES
        self.cb_ratio.setEnabled(key not in _FIXED_RATIO_ENGINES)
        # Mise à jour des options de résolution selon le moteur
        options = _ENGINE_RESOLUTIONS.get(key, [("1080p", "1080p"), ("720p", "720p"), ("480p", "480p")])
        prev = self.cb_res.currentData() or self.cb_res.currentText()
        self.cb_res.blockSignals(True)
        self.cb_res.clear()
        for r in options:
            if isinstance(r, tuple):
                self.cb_res.addItem(r[0], r[1])
            else:
                self.cb_res.addItem(r, r)
        # Restaurer la sélection précédente (par valeur API), sinon premier item
        idx = self.cb_res.findData(prev)
        self.cb_res.setCurrentIndex(max(0, idx))
        self.cb_res.blockSignals(False)
        self.cb_res.setEnabled(not fixed_res)
        if hasattr(self, "_ref_compat_banner"):
            self._ref_compat_banner.setVisible(key in _TEXT_FALLBACK_ENGINES)

    def _on_seed_toggle(self, checked: bool):
        if checked:
            self._seed_lock_btn.setText("🔒  ADN visuel — garder pour tous les plans")
        else:
            self._seed_lock_btn.setText("🔓  ADN visuel — aléatoire")
            self._last_seed = None
        self._update_injection_banner()

    def _get_seed(self) -> int | None:
        if not self._seed_lock_btn.isChecked():
            return None
        return self._last_seed


    def _check_davinci_connection(self) -> bool:
        """Returns True if ok to proceed, False if user cancelled."""
        if resolve.is_connected():
            return True
        # Tentative silencieuse avant d'afficher le dialogue — couvre les faux
        # négatifs transitoires (ping raté après un import dans on_finished).
        ok_silent, _ = resolve.connect()
        if ok_silent:
            self._davinci_bar._refresh()
            return True
        reply = QMessageBox.question(
            self, "DaVinci non connecté",
            "Vous n'êtes pas connecté à DaVinci Resolve.\n\n"
            "Voulez-vous tenter la connexion avant de générer ?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No |
            QMessageBox.StandardButton.Cancel,
        )
        if reply == QMessageBox.StandardButton.Cancel:
            return False
        if reply == QMessageBox.StandardButton.Yes:
            ok, msg = resolve.connect()
            self._davinci_bar._refresh()
            if not ok:
                QMessageBox.warning(self, "Connexion impossible", msg)
        return True

    # ── Garde-fou crédit fal.ai ───────────────────────────────────────────────

    def _start_with_credit_check(self):
        from api.billing import BillingCheckWorker, get_cached_balance
        cached = get_cached_balance()
        if cached is not None:
            self._on_billing_result(*cached)
            return
        self.btn_generate.setEnabled(False)
        self.btn_generate.setText("Vérification du solde…")
        self._billing_worker = BillingCheckWorker()
        self._billing_worker.result.connect(self._on_billing_result)
        self._billing_worker.failed.connect(self._on_billing_failed)
        self._billing_worker.start()

    def _on_billing_result(self, balance: float, currency: str):
        self.btn_generate.setEnabled(True)
        self.btn_generate.setText("▶▶  Lancer la file d'attente")
        from api.billing import WARN_THRESHOLD, BLOCK_THRESHOLD, _DASHBOARD_URL
        sym = "$" if currency.upper() == "USD" else currency
        # Mise à jour du label de solde
        if balance <= 1.0:
            color = C['red']
        elif balance < WARN_THRESHOLD:
            color = "#f5c518"
        else:
            color = C['text_dim']
        self._balance_lbl.setText(f"Solde fal.ai : {sym}{balance:.2f}")
        self._balance_lbl.setStyleSheet(
            f"color:{color};font-size:9px;"
            f"font-family:'Consolas',monospace;background:transparent;"
        )
        # Blocage si solde épuisé
        if balance <= BLOCK_THRESHOLD:
            from PyQt6.QtWidgets import QDialog, QVBoxLayout, QLabel, QPushButton, QHBoxLayout
            from PyQt6.QtGui import QDesktopServices
            from PyQt6.QtCore import QUrl
            dlg = QDialog(self)
            dlg.setWindowTitle("Solde insuffisant — fal.ai")
            dlg.setMinimumWidth(420)
            dlg.setStyleSheet(f"background:{C['bg1']};")
            v = QVBoxLayout(dlg)
            v.setContentsMargins(24, 20, 24, 20)
            v.setSpacing(14)
            ico = QLabel("⛔")
            ico.setAlignment(Qt.AlignmentFlag.AlignCenter)
            ico.setStyleSheet("font-size:36px;background:transparent;")
            v.addWidget(ico)
            title = QLabel("Solde fal.ai insuffisant")
            title.setAlignment(Qt.AlignmentFlag.AlignCenter)
            title.setStyleSheet(f"color:{C['red']};font-size:15px;font-weight:700;background:transparent;")
            v.addWidget(title)
            msg = QLabel(
                f"Votre solde actuel est de <b>{sym}{balance:.2f}</b>.<br><br>"
                "La génération a été annulée pour éviter un débit imprévu.<br>"
                "Rechargez votre compte fal.ai pour continuer."
            )
            msg.setWordWrap(True)
            msg.setAlignment(Qt.AlignmentFlag.AlignCenter)
            msg.setStyleSheet(f"color:{C['text_secondary']};font-size:12px;background:transparent;")
            v.addWidget(msg)
            h = QHBoxLayout()
            btn_dash = QPushButton("🔗  Recharger sur fal.ai →")
            btn_dash.setMinimumHeight(36)
            btn_dash.setCursor(Qt.CursorShape.PointingHandCursor)
            btn_dash.setStyleSheet(
                f"QPushButton{{background:{C['accent']};color:#07080f;"
                f"border:none;border-radius:8px;font-size:12px;font-weight:700;padding:0 16px;}}"
                f"QPushButton:hover{{background:#6eded6;}}"
            )
            btn_dash.clicked.connect(lambda: QDesktopServices.openUrl(QUrl(_DASHBOARD_URL)))
            btn_close = QPushButton("Fermer")
            btn_close.setMinimumHeight(36)
            btn_close.setStyleSheet(
                f"QPushButton{{background:{C['bg3']};color:{C['text_secondary']};"
                f"border:1px solid {C['border']};border-radius:8px;font-size:12px;padding:0 16px;}}"
                f"QPushButton:hover{{background:{C['border']};}}"
            )
            btn_close.clicked.connect(dlg.accept)
            h.addWidget(btn_dash)
            h.addWidget(btn_close)
            v.addLayout(h)
            dlg.exec()
            return
        # Avertissement si solde faible
        if balance < WARN_THRESHOLD:
            from PyQt6.QtWidgets import QDialog, QVBoxLayout, QLabel, QPushButton, QHBoxLayout
            from PyQt6.QtGui import QDesktopServices
            from PyQt6.QtCore import QUrl
            dlg = QDialog(self)
            dlg.setWindowTitle("Solde faible — fal.ai")
            dlg.setMinimumWidth(420)
            dlg.setStyleSheet(f"background:{C['bg1']};")
            v = QVBoxLayout(dlg)
            v.setContentsMargins(24, 20, 24, 20)
            v.setSpacing(14)
            ico = QLabel("⚠️")
            ico.setAlignment(Qt.AlignmentFlag.AlignCenter)
            ico.setStyleSheet("font-size:32px;background:transparent;")
            v.addWidget(ico)
            title = QLabel("Solde fal.ai faible")
            title.setAlignment(Qt.AlignmentFlag.AlignCenter)
            title.setStyleSheet(f"color:#f5c518;font-size:15px;font-weight:700;background:transparent;")
            v.addWidget(title)
            msg = QLabel(
                f"Votre solde actuel est de <b>{sym}{balance:.2f}</b>.<br><br>"
                "Il reste peu de crédit — une longue génération pourrait dépasser ce solde.<br>"
                "Vérifiez votre compte avant de lancer une série de clips."
            )
            msg.setWordWrap(True)
            msg.setAlignment(Qt.AlignmentFlag.AlignCenter)
            msg.setStyleSheet(f"color:{C['text_secondary']};font-size:12px;background:transparent;")
            v.addWidget(msg)
            h = QHBoxLayout()
            btn_dash = QPushButton("🔗  Voir mon compte fal.ai")
            btn_dash.setMinimumHeight(36)
            btn_dash.setCursor(Qt.CursorShape.PointingHandCursor)
            btn_dash.setStyleSheet(
                f"QPushButton{{background:rgba(245,197,24,0.15);color:#f5c518;"
                f"border:1px solid rgba(245,197,24,0.4);border-radius:8px;"
                f"font-size:12px;font-weight:700;padding:0 16px;}}"
                f"QPushButton:hover{{background:rgba(245,197,24,0.25);}}"
            )
            btn_dash.clicked.connect(lambda: QDesktopServices.openUrl(QUrl(_DASHBOARD_URL)))
            btn_go = QPushButton("▶  Générer quand même")
            btn_go.setMinimumHeight(36)
            btn_go.setStyleSheet(
                f"QPushButton{{background:{C['bg3']};color:{C['text_secondary']};"
                f"border:1px solid {C['border']};border-radius:8px;font-size:12px;padding:0 16px;}}"
                f"QPushButton:hover{{background:{C['border']};}}"
            )
            btn_go.clicked.connect(dlg.accept)
            btn_cancel = QPushButton("Annuler")
            btn_cancel.setMinimumHeight(36)
            btn_cancel.setStyleSheet(
                f"QPushButton{{background:transparent;color:{C['text_dim']};"
                f"border:none;font-size:12px;padding:0 10px;}}"
                f"QPushButton:hover{{color:{C['text_primary']};}}"
            )
            btn_cancel.clicked.connect(dlg.reject)
            h.addWidget(btn_dash)
            h.addWidget(btn_go)
            h.addWidget(btn_cancel)
            v.addLayout(h)
            if not dlg.exec():
                return
        self.start_generation()

    def _on_billing_failed(self, _err: str):
        # Fail-open : on ne bloque pas si l'API billing est inaccessible
        self.btn_generate.setEnabled(True)
        self.btn_generate.setText("▶▶  Lancer la file d'attente")
        self.start_generation()

    def _on_davinci_connection_changed(self, connected: bool):
        self._import_cb.setEnabled(connected)
        if not connected:
            self._import_cb.setChecked(False)
            self._import_cb.setToolTip(
                "DaVinci Resolve Studio requis — connectez le bridge pour activer cette option"
            )
        else:
            self._import_cb.setChecked(True)
            self._import_cb.setToolTip("")

    def _start_batch_generation(self, shots: list):
        count = len(shots)
        dlg = QMessageBox(self)
        dlg.setWindowTitle(translate("Génération en série"))
        dlg.setText(
            f"{translate('Vous avez sélectionné')} {count} {translate('plans.')}\n\n"
            + translate(
                "La génération sera lancée en file d'attente — un clip après l'autre.\n\n"
                "⚠  Chaque plan consomme des crédits fal.ai."
            )
        )
        dlg.setStandardButtons(
            QMessageBox.StandardButton.Ok | QMessageBox.StandardButton.Cancel
        )
        dlg.setDefaultButton(QMessageBox.StandardButton.Cancel)
        if dlg.exec() != QMessageBox.StandardButton.Ok:
            return
        repeat = self._spinbox_repeat.value() if hasattr(self, "_spinbox_repeat") else 1
        expanded = [s for s in shots for _ in range(repeat)]
        self._batch_queue   = expanded
        self._batch_total   = len(expanded)
        self._batch_idx     = 0
        self._is_batch_mode = True
        self._repeat_remaining = 0  # géré par l'expansion de la queue en batch
        self._process_next_batch_shot()

    def _process_next_batch_shot(self):
        if not self._batch_queue:
            return
        shot = self._batch_queue.pop(0)
        self._batch_idx += 1
        self._on_shot_selected(shot)
        self.btn_generate.setText(
            f"▶  Plan {self._batch_idx}/{self._batch_total} en cours…"
        )
        from PyQt6.QtCore import QTimer
        QTimer.singleShot(120, self.start_generation)

    def start_generation(self):
        if not self._is_batch_mode:
            selected = self._storyboard.get_selected_shots()
            if len(selected) > 1:
                self._start_batch_generation(selected)
                return
            # Clip unique — initialise le compteur uniquement au tout premier lancement
            if not hasattr(self, "_repeat_remaining") or self._repeat_remaining <= 0:
                self._repeat_remaining = (
                    self._spinbox_repeat.value()
                    if hasattr(self, "_spinbox_repeat") else 1
                )

        prompt = self.prompt_ta.toPlainText().strip()
        if not prompt:
            QMessageBox.warning(self, "Prompt vide", "Écris un prompt avant de générer !")
            return

        if self._import_cb and self._import_cb.isChecked():
            if not self._check_davinci_connection():
                return

        context     = self._casting.get_context()
        full_prompt = (context + prompt) if context else prompt

        # Framing prefix from shot focal — must come first so Seedance obeys the frame type
        if self._active_shot:
            _focal = self._active_shot.get("focal", "")
            if _focal:
                from core.camera_data import focal_to_framing_prefix
                _framing = focal_to_framing_prefix(_focal)
                if _framing:
                    full_prompt = f"{_framing} — {full_prompt}"

        import core.style as style_api
        _style_ref_active = bool(
            getattr(self, "_style_ref_path", "") and os.path.isfile(self._style_ref_path)
        )
        # video_suffix stays active even with a style ref image: text keywords + visual
        # reference are complementary — the image shows the look, the text names it.
        cam_suffix = self._camera_picker.get_suffix()
        # When Image & Son has a camera, use the no-cam variant of the style suffix
        # to avoid duplicate/conflicting camera body references in the prompt.
        video_suffix = (
            style_api.get_video_suffix_no_cam() if cam_suffix
            else style_api.get_video_suffix()
        )

        # Caméra dynamique (mode libre sans shot storyboard)
        if (hasattr(self, "_dyn_cam_cb") and self._dyn_cam_cb.isChecked()
                and not self._active_shot):
            full_prompt = (
                f"{full_prompt}, change the camera angle every 2 seconds "
                "alternating between several types of shots"
            )
        elif cam_suffix:
            full_prompt = f"{full_prompt}, {cam_suffix}"

        # Prise de vue réelle — ancrage filmique anti-CGI/3D
        # (ignoré si le style actif couvre déjà le registre live-action)
        _film_anchor_active = hasattr(self, "_film_anchor_cb") and self._film_anchor_cb.isChecked()
        _film_already_covered = style_api.get_style_key() in {"realistic"}
        if _film_anchor_active and not _film_already_covered:
            full_prompt = (
                f"{full_prompt}, shot on ARRI Alexa 35mm film, photorealistic live action footage, "
                "real human actors, authentic film grain, natural skin texture and pores, "
                "no CGI, no 3D render, no computer animation, no digital art, "
                "organic depth of field, natural practical lighting"
            )

        continuity = self._continuity_bar.build_continuity_prefix()
        if continuity:
            full_prompt = f"{continuity}\n{full_prompt}"

        audio_on = (
            self._audio_cb.isChecked()
            if (hasattr(self, "_audio_cb") and self._audio_cb)
            else True
        )

        music_on = (
            self._music_cb.isChecked()
            if (hasattr(self, "_music_cb") and self._music_cb)
            else False
        )
        # no_music_suffix is passed separately so it's appended after translate_to_english()
        # — stronger multi-phrase instruction resists Seedance's tendency to add music
        no_music_suffix = (
            "" if music_on
            else "no music, no background music, no soundtrack, no musical score, natural ambient sound only"
        )

        subtitle_on = (
            self._subtitle_cb.isChecked()
            if (hasattr(self, "_subtitle_cb") and self._subtitle_cb)
            else False
        )
        if not subtitle_on:
            full_prompt = f"{full_prompt}, no subtitles"

        # Build composite reference mosaics — Seedance only
        _is_seedance = self._get_model() in _SEEDANCE_ENGINES
        from core.context import get_data_root as _get_data_root
        _ref_dir = os.path.join(_get_data_root(), "seedance_refs")
        _no_ref_global = getattr(self, "_no_ref_global_cb", None) and self._no_ref_global_cb.isChecked()
        if not _is_seedance or _no_ref_global:
            ref_images, ref_image_roles = [], []
        else:
            ref_images, ref_image_roles = self._casting.get_ref_mosaics(output_dir=_ref_dir)
        if _is_seedance and hasattr(self, "_style_ref_path") and self._style_ref_path and os.path.isfile(self._style_ref_path):
            ref_images = ref_images + [self._style_ref_path]
            ref_image_roles = ref_image_roles + ["style"]

        # Quality suffix — always appended
        full_prompt = (
            f"{full_prompt}, 4K ultra HD, rich detail, sharp clarity, "
            "cinematic textures, stable picture"
        )
        # Heure du plan → suffixe d'éclairage en anglais, ajouté APRÈS traduction
        # pour que les mots-clés Seedance ne soient pas altérés par Claude Haiku
        _SHOT_TIME_EN = {
            "Jour":             "strict daylight, natural midday sun, bright neutral light, no golden hour, no sunset",
            "Nuit":             "nighttime scene, dark environment, night lighting, no daylight, moonlight or artificial light",
            "Lever du soleil":  "sunrise, warm golden morning light, sun just above the horizon, soft pink-orange sky",
            "Coucher du soleil":"sunset, golden hour, warm amber-orange light, sun low on the horizon",
        }
        _shot_time = (self._active_shot.get("shot_time") if self._active_shot else "") or ""
        time_suffix = _SHOT_TIME_EN.get(_shot_time, "")

        # Cohérence personnage — uniquement quand des personnages avec image sont présents
        _has_char_ref = "character" in ref_image_roles
        char_consistency_suffix = (
            "exact same person as the reference image, "
            "identical face features, same skin tone, same hair color and style, "
            "same clothing, strict visual consistency"
            if _has_char_ref else ""
        )

        # ADN visuel
        seed = self._get_seed()

        # I2V continuité depuis la dernière frame du plan précédent
        i2v_frame = self._continuity_bar.get_i2v_frame()
        # Raccord automatique — force I2V avec la dernière frame du plan précédent
        if not i2v_frame and getattr(self, "_raccord_auto_cb", None) and self._raccord_auto_cb.isChecked():
            _prev = getattr(self._continuity_bar, "_prev_shot", None)
            if _prev:
                _prev_frame = _prev.get("last_frame_path", "")
                if _prev_frame and os.path.isfile(_prev_frame):
                    i2v_frame = _prev_frame

        params = {
            "mode":                    "i2v" if i2v_frame else "t2v",
            "prompt":                  full_prompt,
            "style_suffix":            video_suffix,
            "no_music_suffix":         no_music_suffix,
            "time_suffix":             time_suffix,
            "char_consistency_suffix":  char_consistency_suffix,
            "creative_suffix":          self._creative.get_creative_suffix(),
            "safety_tolerance_override": str(self._creative.get_safety_tolerance()),
            "model":          self._get_model(),
            "duration":       self._get_duration(),
            "resolution":     (self.cb_res.currentData() or self.cb_res.currentText()),
            "aspect_ratio":   self.cb_ratio.currentText().split(" ")[0],
            "shot_title":     self._active_shot_title,
            "audio":          audio_on,
            "ref_images":      ref_images,
            "ref_image_roles": ref_image_roles,
            "style_ref_path":  self._style_ref_path if _style_ref_active else "",
            "decor_ref_free":  self._casting.get_decor_ref_free(),
        }
        if seed is not None:
            params["seed"] = seed
        if i2v_frame:
            params["image_path"] = i2v_frame

        self.btn_generate.setEnabled(False)
        self.btn_cancel.setVisible(True)
        self.progress.reset()
        self.progress.setVisible(True)

        _model_key = self._get_model()
        if _model_key in _SEEDANCE_ENGINES:
            self._worker = GenerationWorker(params)
            self._worker.finished.connect(self.on_finished)
        else:
            self._worker = _make_ext_worker(_model_key, params)
            if self._worker is None:
                self.on_failed(f"Moteur inconnu : {_model_key}")
                return
            _raw = params.get("prompt", "")
            self._worker.finished.connect(
                lambda r, p=_raw: self.on_finished(_norm_ext_result(r, p))
            )
        self._worker.progress.connect(self.on_progress)
        self._worker.failed.connect(self.on_failed)
        self._worker.start()

    def cancel_generation(self):
        if self._worker:
            # Déconnecter les signaux en premier pour ignorer les émissions tardives
            for sig in ("finished", "failed", "progress"):
                try:
                    getattr(self._worker, sig).disconnect()
                except RuntimeError:
                    pass
            if hasattr(self._worker, "cancel"):
                self._worker.cancel()
            else:
                self._worker.quit()
                abandon_thread(self._worker)
            self._worker = None
        if self._is_batch_mode:
            self._batch_queue.clear()
            self._is_batch_mode = False
        self._repeat_remaining = 0
        self._reset_ui()
        self.progress.setVisible(False)

    def on_progress(self, pct: int, msg: str):
        repeat_total = (
            self._spinbox_repeat.value()
            if hasattr(self, "_spinbox_repeat") else 1
        )
        remaining = getattr(self, "_repeat_remaining", 0)
        if not self._is_batch_mode and repeat_total > 1:
            current = max(1, repeat_total - remaining + 1)
            self.progress.update(pct, f"[{current}/{repeat_total}] {msg}")
        else:
            self.progress.update(pct, msg)

    def on_finished(self, result: dict):
        self.progress.set_done()
        self.progress.update(100, "Vidéo prête !")
        self._reset_ui()
        self._davinci_bar._refresh()

        entry = {**result, "status": "done"}
        save_to_history(entry)
        self.generation_done.emit(entry)

        davinci_msg = ""
        local_path = ""
        _import_checked = bool(self._import_cb and self._import_cb.isChecked())

        # Toujours sauvegarder localement, que le bridge soit connecté ou non.
        # import_to_davinci=True uniquement si la case est cochée ET bridge connecté.
        self.progress.update(100, "Sauvegarde du clip…")
        shot_title = result.get("shot_title") or self._active_shot_title
        ir = import_result(result, get_output_dir(), shot_title=shot_title,
                           import_to_davinci=_import_checked)
        if ir["mock"]:
            if _import_checked:
                davinci_msg = "\n\n◈ Import DaVinci : simulé (mode mock)"
        elif ir["success"]:
            local_path = ir.get("local_path", "")
            if ir.get("davinci_imported"):
                davinci_msg = f"\n\n◈ Sauvegardé + importé dans le Media Pool ✓\n{local_path}"
            else:
                davinci_msg = f"\n\n◈ Vidéo sauvegardée :\n{local_path}"
        else:
            davinci_msg = f"\n\n◈ Téléchargement échoué : {ir['error']}"

        # ADN visuel : mémorise le seed utilisé pour les prochaines générations
        seed_used = result.get("seed", 0)
        if seed_used and seed_used > 0:
            self._last_seed = seed_used

        # Alerte GCS si des images de référence n'ont pas pu être uploadées
        _attempted = result.get("ref_images_attempted", 0)
        _sent      = result.get("ref_images_sent", 0)
        _detail    = result.get("gcs_error_detail", "")
        if _attempted > 0 and _sent < _attempted:
            self._gcs_warning.show_warning(sent=_sent, attempted=_attempted, detail=_detail)

        # Extract frames for storyboard thumbnail (first) and raccord continuity (last)
        if local_path and os.path.isfile(local_path) and self._active_shot:
            shot_id = self._active_shot.get("id", "")
            if shot_id:
                try:
                    from core.video_utils import extract_first_frame, extract_last_frame
                    from core.context import get_data_root
                    frames_dir = os.path.join(get_data_root(), "storyboard", "frames")
                    os.makedirs(frames_dir, exist_ok=True)

                    # First frame → storyboard thumbnail (image_path), always updated
                    first_path = os.path.join(frames_dir, f"{shot_id}_first_frame.png")
                    updated = dict(self._active_shot)
                    if extract_first_frame(local_path, first_path):
                        updated["image_path"] = first_path

                    # Last frame → raccord continuity
                    last_path = os.path.join(frames_dir, f"{shot_id}_last_frame.png")
                    if extract_last_frame(local_path, last_path):
                        updated["last_frame_path"] = last_path

                    sb_api.save_shot(updated)
                    self._active_shot = updated
                except Exception:
                    pass

        if self._batch_queue:
            from PyQt6.QtCore import QTimer
            QTimer.singleShot(300, self._process_next_batch_shot)
        elif self._is_batch_mode:
            self._is_batch_mode = False
            self._multi_panel.setVisible(False)
            if hasattr(self, "_multi_seed_lbl"):
                self._multi_seed_lbl.setVisible(False)
            self._edit_zone.setVisible(True)
            self._camera_picker._cb_focal.setEnabled(True)
            self.cb_dur.blockSignals(True)
            if self.cb_dur.itemText(0) == "— s":
                self.cb_dur.removeItem(0)
            self.cb_dur.blockSignals(False)
            self.btn_generate.setText("▶▶  Lancer la file d'attente")
            QMessageBox.information(
                self, f"✓ {self._batch_total} clips générés",
                f"Génération en série terminée !\n\n{self._batch_total} clips générés avec succès."
            )
        elif getattr(self, "_repeat_remaining", 0) > 0:
            self._repeat_remaining -= 1
            repeat_total = (
                self._spinbox_repeat.value()
                if hasattr(self, "_spinbox_repeat") else 1
            )
            if self._repeat_remaining > 0:
                repeat_done = repeat_total - self._repeat_remaining + 1
                self.progress.update(0, f"Répétition {repeat_done}/{repeat_total}…")
                from PyQt6.QtCore import QTimer
                QTimer.singleShot(300, self.start_generation)
            else:
                self._repeat_remaining = 0
                QMessageBox.information(
                    self, "✓ Génération terminée",
                    f"{repeat_total} clip{'s' if repeat_total > 1 else ''} généré{'s' if repeat_total > 1 else ''} avec succès !\n\n"
                    f"Modèle : {result['model']}\n"
                    f"Durée : {result['duration']}s · {result['resolution']}\n"
                    f"Crédits : {result['credits_used']}"
                    + davinci_msg
                )
        else:
            self._repeat_remaining = 0
            QMessageBox.information(
                self, "✓ Génération terminée",
                f"Clip généré avec succès !\n\n"
                f"Modèle : {result['model']}\n"
                f"Durée : {result['duration']}s · {result['resolution']}\n"
                f"Crédits : {result['credits_used']}"
                + davinci_msg
            )

    def on_failed(self, error: str):
        self.progress.set_error(error)
        show_api_error(self, error)
        self._reset_ui()
        entry = {
            "mode":         "t2v",
            "prompt":       self.prompt_ta.toPlainText().strip(),
            "status":       "error",
            "error":        error,
            "generated_at": datetime.now().isoformat(),
        }
        save_to_history(entry)
        self.generation_done.emit(entry)
        if self._is_batch_mode:
            done = self._batch_idx - 1
            remaining = len(self._batch_queue)
            self._batch_queue.clear()
            self._is_batch_mode = False
            self._multi_panel.setVisible(False)
            if hasattr(self, "_multi_seed_lbl"):
                self._multi_seed_lbl.setVisible(False)
            self._edit_zone.setVisible(True)
            self._camera_picker._cb_focal.setEnabled(True)
            self.cb_dur.blockSignals(True)
            if self.cb_dur.itemText(0) == "— s":
                self.cb_dur.removeItem(0)
            self.cb_dur.blockSignals(False)
            self.btn_generate.setText("▶▶  Lancer la file d'attente")
            QMessageBox.critical(
                self, "Erreur — génération en série interrompue",
                f"Erreur sur le plan {self._batch_idx}/{self._batch_total} :\n\n{error}\n\n"
                f"{done} clip(s) généré(s) avant l'erreur. {remaining} plan(s) annulé(s)."
            )
        else:
            QMessageBox.critical(self, "Erreur de génération", f"Une erreur est survenue :\n\n{error}")

    def _on_enhance(self):
        prompt = self.prompt_ta.toPlainText().strip()
        if not prompt:
            QMessageBox.warning(self, "Prompt vide", "Écris un prompt à améliorer !")
            return
        self._btn_enhance.setEnabled(False)
        if hasattr(self._btn_enhance, "_loading"):
            self._btn_enhance._loading.setVisible(True)
        self._enhance_worker = EnhanceWorker(prompt)
        self._enhance_worker.finished.connect(self._on_enhance_done)
        self._enhance_worker.failed.connect(self._on_enhance_failed)
        self._enhance_worker.start()

    def _on_enhance_done(self, enhanced: str):
        self.prompt_ta.setPlainText(enhanced)
        self._btn_enhance.setEnabled(True)
        if hasattr(self._btn_enhance, "_loading"):
            self._btn_enhance._loading.setVisible(False)

    def _on_enhance_failed(self, error: str):
        self._btn_enhance.setEnabled(True)
        if hasattr(self._btn_enhance, "_loading"):
            self._btn_enhance._loading.setVisible(False)
        QMessageBox.warning(self, "Amélioration impossible", error)

    def _reset_ui(self):
        self.btn_generate.setEnabled(True)
        self.btn_generate.setText("▶▶  Lancer la file d'attente")
        self.btn_cancel.setVisible(False)

    def refresh(self):
        self._casting.refresh()
        self._storyboard.refresh()
        self._davinci_bar._refresh()
        self._camera_picker.refresh()
        self._refresh_style_badge()

    def _open_output_folder(self):
        from core.config import get_output_dir
        import subprocess as _sp
        folder = get_output_dir()
        os.makedirs(folder, exist_ok=True)
        _sp.Popen(["explorer", folder])

    def _open_manual_tarifs(self):
        from ui.dialog_user_manual import UserManualDialog
        UserManualDialog(self.window(), start_section=13).exec()

    def _refresh_style_badge(self):
        import core.style as style_api
        no_audio = style_api.is_no_audio()
        self._refresh_prompt_preview()
        if hasattr(self, "_audio_toggle_row") and self._audio_toggle_row:
            self._audio_toggle_row.setEnabled(not no_audio)
            if no_audio and self._audio_cb:
                self._audio_cb.setChecked(False)
        if hasattr(self, "_music_toggle_row") and self._music_toggle_row:
            self._music_toggle_row.setEnabled(not no_audio)
            if no_audio and self._music_cb:
                self._music_cb.setChecked(False)
        if hasattr(self, "_import_cb") and self._import_cb:
            self._import_cb.setEnabled(not no_audio)
            if no_audio:
                self._import_cb.setChecked(False)

    def _on_film_style_changed(self, idx: int):
        pass  # combo supprimé — plus utilisé

    def _set_style_ref_image(self, path: str):
        self._style_ref_path = path
        has = bool(path and os.path.isfile(path))
        if has:
            pix = QPixmap(path).scaled(
                152, 132,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            self._style_ref_thumb.setPixmap(pix)
        else:
            self._style_ref_thumb.setPixmap(QPixmap())
        self._style_ref_clear_btn.setVisible(has)
        self._update_injection_banner()

    def _on_style_gallery(self):
        from ui.dialog_style_gallery import StyleGalleryDialog
        dlg = StyleGalleryDialog(self, current_style_key="", current_ref_image=self._style_ref_path)
        if dlg.exec() == StyleGalleryDialog.DialogCode.Accepted:
            chosen = dlg.result_path()
            self._set_style_ref_image(chosen)

    def _on_style_ref_clear(self):
        self._set_style_ref_image("")
