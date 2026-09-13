"""
ui/comfy_row.py — Rangée « ComfyUI » des Paramètres.

Composant NEUTRE (ni Cinéma ni Live), instancié tel quel par les deux pages
Paramètres, comme ui/projects_location_row.py et ui/h3_local_row.py. La
logique vit dans core/comfy.py ; ici, uniquement l'affichage.

Deux réglages : l'adresse du serveur (détection automatique si vide) et le
workflow personnalisé — le fichier .json qu'utilise le moteur « ComfyUI ·
Workflow personnalisé » de l'onglet Moteurs. Choisir le fichier ici plutôt
que dans le formulaire du moteur garde ce formulaire identique aux autres.
"""
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton, QFileDialog,
)

from core import comfy as _cf
from core.config import load_config, save_config
from core.i18n import translate
from ui.styles import CP

WORKFLOW_KEY = "comfy_custom_workflow"


def _field(placeholder: str, text: str) -> QLineEdit:
    f = QLineEdit()
    f.setFixedHeight(38)
    f.setPlaceholderText(placeholder)
    f.setText(text or "")
    f.setStyleSheet(
        f"QLineEdit{{background:{CP['bg3']};border:1px solid {CP['border']};"
        f"border-radius:6px;color:{CP['text_primary']};font-size:11px;"
        f"font-family:'Consolas',monospace;padding:0 12px;}}"
        f"QLineEdit:focus{{border-color:{CP['accent']};}}")
    return f


def _btn(text: str) -> QPushButton:
    b = QPushButton(text)
    b.setFixedHeight(38)
    b.setCursor(Qt.CursorShape.PointingHandCursor)
    b.setStyleSheet(
        f"QPushButton{{background:transparent;color:{CP['text_secondary']};"
        f"border:1px solid {CP['border']};border-radius:6px;"
        f"font-size:12px;font-weight:600;padding:0 18px;}}"
        f"QPushButton:hover{{background:{CP['bg3']};color:{CP['text_primary']};}}")
    return b


class ComfyRow(QWidget):
    """Adresse + Tester, workflow personnalisé + Parcourir, état. Auto-enregistrée."""

    changed = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet("background:transparent;")
        cfg = load_config()

        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(6)

        row = QHBoxLayout(); row.setSpacing(8)
        self._url = _field(translate("Adresse du serveur (vide = détection automatique sur ")
                           + ", ".join(u.split("//")[1] for u in _cf.CANDIDATE_URLS) + ")",
                           cfg.get(_cf.CONFIG_KEY, ""))
        self._url.editingFinished.connect(self._on_url_edited)
        row.addWidget(self._url, 1)
        b = _btn(translate("Tester")); b.clicked.connect(self._probe)
        row.addWidget(b)
        lay.addLayout(row)

        self._state = QLabel(translate("Non vérifié — cliquez sur « Tester »."))
        self._state.setWordWrap(True)
        self._state.setStyleSheet(f"color:{CP['text_dim']};font-size:10px;background:transparent;border:none;")
        lay.addWidget(self._state)

        row2 = QHBoxLayout(); row2.setSpacing(8)
        self._wf = _field(translate("Workflow personnalisé (.json exporté de ComfyUI) — pour le moteur « ComfyUI · Workflow personnalisé »"),
                          cfg.get(WORKFLOW_KEY, ""))
        self._wf.editingFinished.connect(self._on_wf_edited)
        row2.addWidget(self._wf, 1)
        b2 = _btn(translate("Parcourir…")); b2.clicked.connect(self._browse)
        row2.addWidget(b2)
        lay.addLayout(row2)

        hint = QLabel(translate(
            "ComfyUI Desktop s'installe depuis comfy.org ; PANDORA n'embarque ni le "
            "moteur ni les modèles. Les gabarits MiniMax H3 fournis avec ComfyUI "
            "(Bibliothèque › Vidéo) téléchargent eux-mêmes leurs modèles."))
        hint.setWordWrap(True)
        hint.setStyleSheet(f"color:{CP['text_dim']};font-size:10px;background:transparent;border:none;")
        lay.addWidget(hint)

    # ── Actions ─────────────────────────────────────────────────────────────

    def _probe(self):
        typed = self._url.text().strip()
        base = _cf.normalize_url(typed) if typed else _cf.discover()
        ok, msg, info = _cf.ping(base) if base else (False, translate("Aucun ComfyUI trouvé sur les adresses usuelles."), {})
        extra = ""
        if ok and info.get("version") and not _cf.version_ok(info["version"]):
            extra = "  ·  " + translate("trop ancien pour H3 (0.30.0 minimum)")
        self._state.setText(("✓  " if ok else "") + translate(msg) + extra)
        self._state.setStyleSheet(
            f"color:{CP['text_dim'] if ok else '#f0b429'};font-size:10px;background:transparent;border:none;")

    def _on_url_edited(self):
        try:
            self.changed.emit(_cf.set_url(self._url.text()))
        except Exception:
            pass

    def _on_wf_edited(self):
        self._save_wf(self._wf.text().strip())

    def _browse(self):
        path, _ = QFileDialog.getOpenFileName(
            self, translate("Choisir un workflow ComfyUI"), "", "Workflow ComfyUI (*.json)")
        if path:
            self._wf.setText(path)
            self._save_wf(path)

    def _save_wf(self, path: str):
        try:
            cfg = load_config()
            cfg[WORKFLOW_KEY] = path
            save_config(cfg)
        except Exception:
            pass
