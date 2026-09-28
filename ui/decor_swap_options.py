"""ui/decor_swap_options.py — Réglages de « Changer le décor · acteurs intacts ».

Composant PARTAGÉ par « Modifier des clips » Cinéma (ui/tab_davinci_edit) et
Live (ui/tab_modify_live), comme ui/external_banner : une seule définition des
choix (core/decor_swap.PLATE_MODES) et un seul texte d'explication, pour que
les deux éditions disent la même chose de la même méthode.
"""

import os

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QCheckBox, QComboBox, QFileDialog, QFrame, QHBoxLayout, QLabel, QPushButton,
    QVBoxLayout, QWidget,
)

from core import decor_swap as ds
from core.i18n import translate
from ui.styles import C

_MODE_HINTS = {
    ds.PLATE_GEN_IMAGE: ("Le décor est généré d'après la consigne ; l'image de référence, "
                         "si vous en mettez une, lui sert de modèle."),
    ds.PLATE_GEN_VIDEO: ("Seedance 2.0 génère un décor animé SANS personne, de la durée du "
                         "plan (4 à 15 s, bouclé au-delà) ; l'image de référence, si vous "
                         "en mettez une, devient sa première image."),
    ds.PLATE_REF_IMAGE: "L'image de référence devient le décor, recadrée au format du plan (0 $).",
    ds.PLATE_FILE: ("Une image ou une vidéo de votre choix devient le décor, recadrée au "
                    "format du plan (0 $)."),
}


def _combo_css() -> str:
    return (f"QComboBox{{background:{C['bg2']};color:{C['text_primary']};"
            f"border:1px solid {C['border']};border-radius:6px;padding:4px 8px;font-size:11px;}}"
            f"QComboBox QAbstractItemView{{background:{C['bg2']};color:{C['text_primary']};"
            f"selection-background-color:{C['accent_dim']};}}")


def _label(text: str, color_key: str = "text_secondary", size: int = 11) -> QLabel:
    lbl = QLabel(text)
    lbl.setWordWrap(True)
    lbl.setStyleSheet(f"color:{C[color_key]};font-size:{size}px;background:transparent;border:none;")
    return lbl


class DecorSwapOptions(QFrame):
    """Choix du nouveau décor + options de recomposition. `options()` rend le
    dict attendu par api/decor_swap.DecorSwapWorker."""

    changed = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._plate_file = ""
        self.setObjectName("decorSwapOptions")
        self.setStyleSheet(
            f"QFrame#decorSwapOptions{{background:transparent;"
            f"border:1px solid {C['accent_dim']};border-radius:8px;}}")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(12, 10, 12, 10)
        lay.setSpacing(8)

        title = _label(translate("CHANGER LE DÉCOR · ACTEURS INTACTS"), "accent", 10)
        title.setStyleSheet(title.styleSheet() + "font-weight:700;letter-spacing:1px;")
        lay.addWidget(title)
        lay.addWidget(_label(translate(
            "Les acteurs sont détourés puis recomposés tels quels sur le nouveau décor : "
            "aucun modèle génératif ne touche à leurs visages, à leurs lèvres ni au son. "
            "Décrivez dans la consigne le décor seul, sans les personnages.")))

        # Nouveau décor
        row = QHBoxLayout()
        row.setSpacing(8)
        row.addWidget(_label(translate("Nouveau décor")), 0)
        self._mode = QComboBox()
        self._mode.setMinimumHeight(28)
        self._mode.setStyleSheet(_combo_css())
        for lbl, key in ds.PLATE_MODES:
            self._mode.addItem(translate(lbl), key)
        row.addWidget(self._mode, 1)
        lay.addLayout(row)
        self._mode_hint = _label("", "text_secondary", 10)
        lay.addWidget(self._mode_hint)

        # Moteur d'image (décor généré en image)
        self._eng_row = QWidget()
        er = QHBoxLayout(self._eng_row)
        er.setContentsMargins(0, 0, 0, 0)
        er.setSpacing(8)
        er.addWidget(_label(translate("Moteur d'image")), 0)
        self._engine = QComboBox()
        self._engine.setMinimumHeight(28)
        self._engine.setStyleSheet(_combo_css())
        try:
            from core import image_engines as _ie
            for key, lbl in _ie.engine_choices():
                self._engine.addItem(lbl, key)
            _i = self._engine.findData(_ie.DEFAULT_ENGINE)
            if _i >= 0:
                self._engine.setCurrentIndex(_i)
        except Exception:
            self._engine.addItem("Nano Banana 2", "nb2")
        er.addWidget(self._engine, 1)
        lay.addWidget(self._eng_row)

        # Fichier fourni (image ou vidéo)
        self._file_row = QWidget()
        fr = QHBoxLayout(self._file_row)
        fr.setContentsMargins(0, 0, 0, 0)
        fr.setSpacing(8)
        self._btn_file = QPushButton(translate("Choisir le décor…"))
        self._btn_file.setMinimumHeight(28)
        self._btn_file.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_file.setStyleSheet(
            f"QPushButton{{background:transparent;color:{C['accent']};"
            f"border:1px solid {C['accent_dim']};border-radius:6px;padding:0 10px;font-size:11px;}}"
            f"QPushButton:hover{{border-color:{C['accent']};}}")
        self._btn_file.clicked.connect(self._pick_file)
        fr.addWidget(self._btn_file, 0)
        self._file_lbl = _label(translate("Aucun fichier choisi"), "text_dim", 10)
        fr.addWidget(self._file_lbl, 1)
        lay.addWidget(self._file_row)

        # Recomposition
        _cb_css = f"QCheckBox{{color:{C['text_secondary']};font-size:11px;background:transparent;}}"
        self._harmonize = QCheckBox(translate(
            "Harmoniser la couleur des acteurs avec le décor (local, gratuit)"))
        self._harmonize.setChecked(True)
        self._harmonize.setStyleSheet(_cb_css)
        lay.addWidget(self._harmonize)
        self._relight = QCheckBox(translate(
            "Rééclairage IA des acteurs, expérimental (ID-V2V · ~0,20 $/s · sortie 720p · "
            "visages ressemblants, plus identiques au pixel)"))
        self._relight.setChecked(False)
        self._relight.setStyleSheet(_cb_css)
        lay.addWidget(self._relight)

        lay.addWidget(_label(translate(
            "Détourage VEED ~0,02 $/s · décor : image ~0,03 à 0,08 $, vidéo Seedance "
            "~0,30 $/s, ou 0 $ avec votre image ou votre fichier. Limites : les ombres "
            "portées des acteurs disparaissent, et le décor ne suit pas un mouvement de "
            "caméra."), "text_secondary", 10))

        self._mode.currentIndexChanged.connect(self._refresh)
        for w in (self._engine, ):
            w.currentIndexChanged.connect(lambda *_a: self.changed.emit())
        self._harmonize.toggled.connect(lambda *_a: self.changed.emit())
        self._relight.toggled.connect(lambda *_a: self.changed.emit())
        self._refresh()

    # ── État ────────────────────────────────────────────────────────────────

    def plate_mode(self) -> str:
        return str(self._mode.currentData() or ds.PLATE_GEN_IMAGE)

    def set_plate_mode(self, key: str):
        i = self._mode.findData(key)
        if i >= 0:
            self._mode.setCurrentIndex(i)

    def plate_file(self) -> str:
        p = self._plate_file or ""
        return p if os.path.isfile(p) else ""

    def set_plate_file(self, path: str):
        self._plate_file = str(path or "")
        self._file_lbl.setText(os.path.basename(self._plate_file) if self._plate_file
                               else translate("Aucun fichier choisi"))
        self.changed.emit()

    def options(self) -> dict:
        return {
            "plate_mode":   self.plate_mode(),
            "image_engine": str(self._engine.currentData() or ""),
            "plate_file":   self.plate_file(),
            "harmonize":    self._harmonize.isChecked(),
            "relight":      self._relight.isChecked(),
        }

    # ── Interne ─────────────────────────────────────────────────────────────

    def _refresh(self, *_a):
        mode = self.plate_mode()
        self._eng_row.setVisible(mode == ds.PLATE_GEN_IMAGE)
        self._file_row.setVisible(mode == ds.PLATE_FILE)
        self._mode_hint.setText(translate(_MODE_HINTS.get(mode, "")))
        self.changed.emit()

    def _pick_file(self):
        exts = " ".join(f"*{e}" for e in ds.IMAGE_EXTS + ds.VIDEO_EXTS)
        path, _ = QFileDialog.getOpenFileName(
            self, translate("Choisir le décor (image ou vidéo)"), "",
            f"{translate('Images et vidéos')} ({exts});;{translate('Tous les fichiers (*)')}")
        if path:
            self.set_plate_file(path)
