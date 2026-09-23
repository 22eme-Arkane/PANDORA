"""ui/external_banner.py — Bandeau sous le choix du moteur.

Dès qu'un moteur qui dépend d'un module externe (core/externals) est
sélectionné, le bandeau sonde le module hors du thread de l'interface et,
s'il manque quelque chose, le dit sans bloquer : « ComfyUI Desktop n'est pas
installé sur cet ordinateur — PANDORA peut l'installer. » avec un bouton qui
ouvre la fenêtre du module (ui/dialog_external). Rien n'apparaît pour les
moteurs fal, ni quand le module est prêt.

Composant NEUTRE : les deux Studios et les deux onglets Moteurs l'insèrent
tel quel et appellent `set_engine(clé)` à chaque changement de moteur.
"""

from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton

from core import externals as _ex
from core.i18n import translate
from ui.styles import CP

_AMBER = "#f0b429"


class ExternalBanner(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._key = ""
        self._status: _ex.Status | None = None
        self._worker = None
        self.setStyleSheet(
            f"QFrame{{background:rgba(240,180,41,0.08);border:1px solid rgba(240,180,41,0.55);"
            f"border-radius:6px;}}")
        lay = QHBoxLayout(self)
        lay.setContentsMargins(12, 8, 12, 8)
        lay.setSpacing(10)
        self._lbl = QLabel("")
        self._lbl.setWordWrap(True)
        self._lbl.setStyleSheet(f"color:{_AMBER};font-size:11px;font-weight:600;background:transparent;border:none;")
        lay.addWidget(self._lbl, 1)
        self._btn = QPushButton(translate("Installer / Guide…"))
        self._btn.setFixedHeight(30)
        self._btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn.setStyleSheet(
            f"QPushButton{{background:{_AMBER};border:none;border-radius:6px;color:#0c0e1a;"
            f"font-size:11px;font-weight:700;padding:0 14px;}}"
            f"QPushButton:hover{{background:rgba(240,180,41,0.85);}}")
        self._btn.clicked.connect(self._open)
        lay.addWidget(self._btn)
        self.setVisible(False)

    # ── API ──────────────────────────────────────────────────────────────────

    def set_engine(self, engine_key: str):
        """Le moteur sélectionné vient de changer."""
        ext = _ex.for_engine(engine_key or "")
        if ext is None:
            self._key, self._status = "", None
            self.setVisible(False)
            return
        if ext.key != self._key:
            self._status = None
        self._key = ext.key
        self.refresh()

    def refresh(self):
        if not self._key:
            return
        from api.external_install import ExternalStatusWorker
        self._worker = ExternalStatusWorker([self._key], self)
        self._worker.result.connect(self._on_status)
        self._worker.start()

    # ── Slots ────────────────────────────────────────────────────────────────

    def _on_status(self, key: str, st):
        if key != self._key or self.sender() is not self._worker:
            return                                  # résultat d'un moteur précédent
        self._status = st
        if st.ready:
            self.setVisible(False)
            return
        name = _ex.EXTERNALS[key].name
        if not st.installed:
            text = f"{name} " + translate("n'est pas installé sur cet ordinateur") + " — " + translate("PANDORA peut l'installer.")
            self._btn.setText(translate("Installer / Guide…"))
        elif not st.running:
            text = f"{name} " + translate("est installé mais ne tourne pas") + "."
            self._btn.setText(translate("Lancer / Guide…"))
        else:
            text = f"{name} " + translate("tourne — il manque des fichiers de modèle") + f" ({len(st.missing)})."
            self._btn.setText(translate("Télécharger / Guide…"))
        self._lbl.setText("⚠  " + text)
        self.setVisible(True)

    def _open(self):
        if not self._key:
            return
        from ui.dialog_external import ExternalDialog
        dlg = ExternalDialog(self._key, self, status=self._status)
        dlg.exec()
        self.refresh()
