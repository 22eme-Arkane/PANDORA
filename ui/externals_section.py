"""ui/externals_section.py — Section « Modules externes » des Paramètres.

Un tableau de bord : pour chaque module de core/externals, son état (sondé
hors du thread de l'interface à l'affichage de la page), et les actions —
« Installer / Guide… » ouvre la fenêtre du module (ui/dialog_external),
« Lancer » démarre ce qui est installé mais arrêté, « Vérifier » resonde.

Composant NEUTRE, inséré tel quel par les deux pages Paramètres (comme
ui/comfy_row.py). Les rangées d'adresse de serveur (ComfyRow, H3LocalRow)
restent : elles règlent l'adresse, ici on voit l'ensemble.
"""

from __future__ import annotations

import time

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QFrame

from core import externals as _ex
from core.i18n import translate
from ui.styles import CP

_AMBER = "#f0b429"
_REFRESH_EVERY_S = 30


def _btn(text: str) -> QPushButton:
    b = QPushButton(text)
    b.setFixedHeight(32)
    b.setCursor(Qt.CursorShape.PointingHandCursor)
    b.setStyleSheet(
        f"QPushButton{{background:transparent;color:{CP['text_secondary']};"
        f"border:1px solid {CP['border']};border-radius:6px;"
        f"font-size:11px;font-weight:600;padding:0 14px;}}"
        f"QPushButton:hover{{background:{CP['bg3']};color:{CP['text_primary']};}}")
    return b


class _Row(QFrame):
    def __init__(self, ext: _ex.External, owner: "ExternalsSection"):
        super().__init__()
        self._ext, self._owner = ext, owner
        self._status: _ex.Status | None = None
        self.setStyleSheet(f"QFrame{{background:{CP['bg2']};border:1px solid {CP['border']};border-radius:8px;}}")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(14, 10, 14, 10)
        lay.setSpacing(4)
        head = QHBoxLayout()
        name = QLabel(ext.name)
        name.setStyleSheet(f"color:{CP['text_primary']};font-size:12px;font-weight:700;background:transparent;border:none;")
        head.addWidget(name)
        head.addStretch()
        self._state = QLabel(translate("Non vérifié"))
        self._state.setStyleSheet(f"color:{CP['text_dim']};font-size:10px;background:transparent;border:none;")
        head.addWidget(self._state)
        lay.addLayout(head)
        purpose = QLabel(translate(ext.purpose))
        purpose.setWordWrap(True)
        purpose.setStyleSheet(f"color:{CP['text_secondary']};font-size:10px;background:transparent;border:none;")
        lay.addWidget(purpose)
        acts = QHBoxLayout()
        acts.setSpacing(8)
        self._b_open = _btn(translate("Installer / Guide…"))
        self._b_open.clicked.connect(self._open)
        acts.addWidget(self._b_open)
        self._b_launch = _btn("▶  " + translate("Lancer"))
        self._b_launch.clicked.connect(self._launch)
        self._b_launch.setVisible(False)
        acts.addWidget(self._b_launch)
        b_check = _btn(translate("Vérifier"))
        b_check.clicked.connect(self._owner.refresh)
        acts.addWidget(b_check)
        acts.addStretch()
        lay.addLayout(acts)

    def apply(self, st: _ex.Status):
        self._status = st
        if not st.checked:
            txt, color = translate("Non vérifié"), CP["text_dim"]
        elif st.ready:
            txt, color = "✓  " + translate(st.detail), CP["accent"]
        else:
            txt, color = "⚠  " + translate(st.detail), _AMBER
        self._state.setText(txt)
        self._state.setStyleSheet(f"color:{color};font-size:10px;background:transparent;border:none;")
        self._b_launch.setVisible(st.installed and not st.running)
        self._b_open.setText(translate("Ouvrir…") if st.ready else translate("Installer / Guide…"))

    def _open(self):
        from ui.dialog_external import ExternalDialog
        ExternalDialog(self._ext.key, self, status=self._status).exec()
        self._owner.refresh(force=True)

    def _launch(self):
        from api.external_install import ExternalInstallWorker
        w = ExternalInstallWorker(self._ext.key, "launch", None, self)
        w.done.connect(self._owner.on_launched)
        w.failed.connect(self._owner.on_launch_failed)
        self._owner._launchers.append(w)              # référence anti-GC
        self._state.setText(translate("Lancement…"))
        w.start()


class ExternalsSection(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet("background:transparent;")
        self._rows: dict[str, _Row] = {}
        self._worker = None
        self._launchers: list = []
        self._last = 0.0
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(8)
        hint = QLabel(translate(
            "Ce que PANDORA utilise mais n'embarque pas : installé chez vous, sous vos yeux. "
            "Rien n'est téléchargé ni lancé sans un clic."))
        hint.setWordWrap(True)
        hint.setStyleSheet(f"color:{CP['text_dim']};font-size:10px;background:transparent;")
        lay.addWidget(hint)
        # Démarrage automatique (24/09/2026) : un module installé mais arrêté
        # est lancé par PANDORA au moment de générer, sans fenêtre ni clic.
        from PyQt6.QtWidgets import QCheckBox
        from ui.widgets import toggle_row
        self._auto_row = toggle_row(
            translate("Démarrer automatiquement les serveurs locaux"),
            translate("Au moment de générer : ComfyUI Desktop, MiniMax H3 local, Ollama, LM Studio… "
                      "sont lancés par PANDORA s'ils sont installés mais arrêtés. Décoché : la fenêtre "
                      "du module s'ouvre et vous cliquez « Lancer »."),
            _ex.autostart_enabled())
        self._auto_cb = self._auto_row.findChild(QCheckBox)
        self._auto_cb.toggled.connect(self._on_auto_toggled)
        lay.addWidget(self._auto_row)
        for ext in _ex.EXTERNALS.values():
            row = _Row(ext, self)
            self._rows[ext.key] = row
            lay.addWidget(row)

    def _on_auto_toggled(self, checked: bool):
        # Relit la config ENTIÈRE avant d'écrire : save_config remplace le fichier.
        try:
            from core.config import load_config, save_config
            cfg = load_config()
            cfg["externals_autostart"] = bool(checked)
            save_config(cfg)
        except Exception:
            pass

    def showEvent(self, event):
        super().showEvent(event)
        self.refresh()

    def refresh(self, force: bool = False):
        if not force and time.time() - self._last < _REFRESH_EVERY_S:
            return
        if self._worker is not None and self._worker.isRunning():
            return
        self._last = time.time()
        from api.external_install import ExternalStatusWorker
        self._worker = ExternalStatusWorker(list(self._rows), self)
        self._worker.result.connect(self._on_status)
        self._worker.start()

    def _on_status(self, key: str, st):
        row = self._rows.get(key)
        if row is not None:
            row.apply(st)

    def on_launched(self, _result: dict):
        self.refresh(force=True)

    def on_launch_failed(self, msg: str):
        for row in self._rows.values():
            if row._state.text() == translate("Lancement…"):
                row._state.setText("⚠  " + translate(msg))
        self.refresh(force=True)
