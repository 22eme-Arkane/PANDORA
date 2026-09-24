"""ui/external_autostart.py — Le serveur local démarre TOUT SEUL au moment de générer.

Constat Matthieu (24/09/2026, capture) : « installé mais ne tourne pas » puis
un bouton « Lancer » dans une fenêtre pleine d'étapes — trop complexe pour
quelqu'un qui ne connaît pas. Ici, quand un moteur a besoin d'un module qui
est INSTALLÉ mais ARRÊTÉ (ComfyUI Desktop, serveur MiniMax H3 local, Ollama,
LM Studio, Jan, llama.cpp), PANDORA le lance lui-même, attend qu'il réponde
en affichant le temps qui passe, puis continue la génération. La fenêtre
d'installation (ui/dialog_external) ne s'ouvre plus que si le module n'est
PAS installé, si le démarrage automatique est désactivé dans les Paramètres,
ou si le serveur n'a pas répondu dans le délai.

`ensure_ready(clé, parent) -> bool` est ce que les onglets appellent à la
place de « ouvrir la fenêtre et demander un clic ». Composant NEUTRE
(Cinéma et Live).
"""

from __future__ import annotations

import time

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QLabel, QProgressBar, QPushButton

from core import externals as _ex
from core.i18n import translate
from ui.styles import CP
from ui.widgets import disable_default_buttons

CONFIG_KEY = "externals_autostart"

#: Délai d'attente par module (s) : un serveur qui charge 25 Go de poids (H3
#: local) ou télécharge un modèle au premier lancement (llama.cpp) met des
#: minutes ; une application (Ollama, Jan) répond en quelques secondes.
TIMEOUTS_S = {"comfyui": 180, "h3_local": 900, "ollama": 60, "lmstudio": 90,
              "jan": 90, "llamacpp": 900, "vllm": 30}
POLL_MS = 3000


def autostart_enabled() -> bool:
    try:
        from core.config import load_config
        return bool(load_config().get(CONFIG_KEY, True))
    except Exception:
        return True


def _btn(text: str, accent: str) -> QPushButton:
    b = QPushButton(text)
    b.setFixedHeight(34)
    b.setCursor(Qt.CursorShape.PointingHandCursor)
    b.setStyleSheet(
        f"QPushButton{{background:transparent;border:1px solid {accent};border-radius:8px;"
        f"color:{accent};font-size:12px;padding:0 16px;}}"
        f"QPushButton:hover{{background:{CP['bg3']};}}")
    return b


class AutoStartDialog(QDialog):
    """Sonde → lance → attend. `ready` dit si le module répond à la fin."""

    def __init__(self, key: str, parent=None, poll_ms: int = POLL_MS):
        super().__init__(parent)
        self._key = key
        self._ext = _ex.EXTERNALS[key]
        self.ready = False
        self.launched = False
        self._t0 = time.time()
        self._timeout = TIMEOUTS_S.get(key, 120)
        self._poll_ms = poll_ms
        self._status_worker = None
        self._launch_worker = None
        self._cancelled = False
        self.setWindowTitle(f"{self._ext.name} — " + translate("démarrage"))
        self.setMinimumWidth(520)
        self.setStyleSheet(f"QDialog{{background:{CP['bg1']};}}")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(24, 20, 24, 18)
        lay.setSpacing(10)
        title = QLabel(translate("Démarrage de") + f" {self._ext.name}")
        title.setStyleSheet(f"color:{CP['text_primary']};font-size:15px;font-weight:700;background:transparent;")
        lay.addWidget(title)
        self._state = QLabel(translate("Vérification du module…"))
        self._state.setWordWrap(True)
        self._state.setStyleSheet(f"color:{CP['text_secondary']};font-size:12px;background:transparent;")
        lay.addWidget(self._state)
        self._bar = QProgressBar()
        self._bar.setRange(0, 0)                       # « occupé » : on ne sait pas la durée
        self._bar.setFixedHeight(8)
        self._bar.setTextVisible(False)
        self._bar.setStyleSheet(
            f"QProgressBar{{background:{CP['bg3']};border:none;border-radius:4px;}}"
            f"QProgressBar::chunk{{background:{CP['accent']};border-radius:4px;}}")
        lay.addWidget(self._bar)
        self._elapsed = QLabel("")
        self._elapsed.setStyleSheet(f"color:{CP['text_dim']};font-size:10px;background:transparent;")
        lay.addWidget(self._elapsed)
        row = QHBoxLayout()
        b_guide = _btn(translate("Ouvrir le guide…"), CP["accent2"])
        b_guide.clicked.connect(self._open_guide)
        row.addWidget(b_guide)
        row.addStretch()
        b_cancel = _btn(translate("Annuler"), CP["text_dim"])
        b_cancel.clicked.connect(self._cancel)
        row.addWidget(b_cancel)
        lay.addLayout(row)
        disable_default_buttons(self)
        self._tick = QTimer(self)
        self._tick.setInterval(1000)
        self._tick.timeout.connect(self._refresh_elapsed)
        self._tick.start()
        QTimer.singleShot(0, self._probe)

    # ── Étapes ───────────────────────────────────────────────────────────────

    def _probe(self):
        if self._cancelled:
            return
        from api.external_install import ExternalStatusWorker
        self._status_worker = ExternalStatusWorker([self._key], self)
        self._status_worker.result.connect(self._on_status)
        self._status_worker.start()

    def _on_status(self, key: str, st):
        if key != self._key or self._cancelled:
            return
        if st.running:
            self.ready = True
            self._state.setText("✓  " + translate("Le serveur répond."))
            QTimer.singleShot(250, self.accept)
            return
        if not st.installed or not autostart_enabled():
            # Rien à lancer soi-même : la fenêtre d'installation guide.
            self._open_guide(st)
            return
        if not self.launched:
            self.launched = True
            self._launch()
            return
        if time.time() - self._t0 > self._timeout:
            self._state.setText("⚠  " + translate("Le serveur n'a pas répondu dans le délai."))
            self._open_guide(st)
            return
        QTimer.singleShot(self._poll_ms, self._probe)

    def _launch(self):
        from api.external_install import ExternalInstallWorker
        self._state.setText(translate("Lancement de") + f" {self._ext.name}…")
        self._launch_worker = ExternalInstallWorker(self._key, "launch", None, self)
        self._launch_worker.progress.connect(lambda _p, msg: self._state.setText(msg))
        self._launch_worker.done.connect(lambda _r: QTimer.singleShot(self._poll_ms, self._probe))
        self._launch_worker.failed.connect(self._on_launch_failed)
        self._launch_worker.start()

    def _on_launch_failed(self, msg: str):
        self._state.setText("⚠  " + translate(msg))
        self._open_guide()

    def _open_guide(self, st=None):
        if self._cancelled:
            return
        self._tick.stop()
        from ui.dialog_external import ExternalDialog
        dlg = ExternalDialog(self._key, self, status=st)
        dlg.exec()
        self.ready = dlg.is_ready()
        self.accept() if self.ready else self.reject()

    def _cancel(self):
        self._cancelled = True
        self._tick.stop()
        self.reject()

    def _refresh_elapsed(self):
        s = int(time.time() - self._t0)
        self._elapsed.setText(translate("écoulé :") + f" {s} s  ·  " + translate("délai maxi") + f" {self._timeout} s")

    def closeEvent(self, event):
        self._cancelled = True
        self._tick.stop()
        for w in (self._status_worker, self._launch_worker):
            if w is not None:
                try:
                    if w.isRunning():
                        w.wait(3000)
                except RuntimeError:
                    pass
        super().closeEvent(event)


def ensure_ready(key: str, parent=None) -> bool:
    """Vrai si le module répond à la fin — lancé et attendu ici s'il ne faisait
    que dormir. À appeler seulement quand une sonde rapide a échoué (sinon
    la fenêtre clignoterait pour rien)."""
    if key not in _ex.EXTERNALS:
        return False
    dlg = AutoStartDialog(key, parent)
    dlg.exec()
    return bool(dlg.ready)
