"""ui/aiodos_panel.py — Section « AIODOS » des Paramètres (Cinéma ET Live).

Composant NEUTRE, instancié tel quel par les deux pages Paramètres, comme
ui/comfy_row.py. La logique vit dans core/aiodos.py ; ici, l'affichage et les
fils de travail — aucun appel à AIODOS sur le fil de l'interface.

  · l'état d'AIODOS, relu quand la section devient visible (jamais au
    lancement de PANDORA) ;
  · « Lancer AIODOS », « Se connecter à AIODOS » (la demande d'accès : le code
    à 6 chiffres en grand, « Annuler »), « Se déconnecter » — toujours sur un
    clic. Connecté mais un droit de SCOPES décoché sur la carte d'AIODOS : le
    même bouton devient « Demander l'accès manquant » (la carte montre la
    différence, la même clé reçoit le droit). Les lieux de calcul d'un accès
    déjà donné, eux, ne changent qu'en se déconnectant puis se reconnectant ;
  · « Calcul des gabarits ComfyUI » : Ce PC / Mes machines · AIODOS ;
  · ce que PANDORA envoie à AIODOS, dit en clair.
"""
from __future__ import annotations

from PyQt6.QtCore import Qt, QThread, QTimer, pyqtSignal
from PyQt6.QtWidgets import (
    QDialog, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget,
)

from core.i18n import translate
from ui.comfy_choice import ComputeCombo, compute_label, hub
from ui.styles import CP

#: Les fils en cours, gardés jusqu'à leur fin (un QThread détruit en marche
#: fait tomber l'application). Les fils FINIS sont oubliés au fil suivant —
#: jamais dans leur signal `finished`, émis alors que le fil tourne encore.
_RUNNING: list = []


def _keep(worker: QThread) -> QThread:
    def alive(t):
        try:
            return t.isRunning()
        except RuntimeError:
            return False
    _RUNNING[:] = [t for t in _RUNNING if alive(t)]
    _RUNNING.append(worker)
    return worker


class _CallWorker(QThread):
    """Un appel bloquant à core/aiodos, hors du fil de l'interface."""
    done = pyqtSignal(object)
    failed = pyqtSignal(str)

    def __init__(self, fn):
        super().__init__()
        self._fn = fn

    def run(self):
        try:
            self.done.emit(self._fn(self))
        except Exception as e:
            from core import aiodos
            self.failed.emit(aiodos.humanize(e))


class _ConnectWorker(QThread):
    code = pyqtSignal(str)
    done = pyqtSignal(object)
    failed = pyqtSignal(str)

    def run(self):
        from core import aiodos
        try:
            self.done.emit(aiodos.connect(on_code=self.code.emit,
                                          cancel=self.isInterruptionRequested))
        except Exception as e:
            if not self.isInterruptionRequested():
                self.failed.emit(aiodos.humanize(e))


def _btn(text: str, primary: bool = False) -> QPushButton:
    b = QPushButton(translate(text))
    b.setFixedHeight(34)
    b.setCursor(Qt.CursorShape.PointingHandCursor)
    if primary:
        b.setStyleSheet(
            f"QPushButton{{background:{CP['accent']};color:#07080f;border:none;"
            f"border-radius:6px;font-size:12px;font-weight:700;padding:0 18px;}}"
            f"QPushButton:hover{{background:{CP['accent_dim']};color:#fff;}}"
            f"QPushButton:disabled{{background:{CP['bg3']};color:{CP['text_dim']};}}")
    else:
        b.setStyleSheet(
            f"QPushButton{{background:transparent;color:{CP['text_secondary']};"
            f"border:1px solid {CP['border']};border-radius:6px;"
            f"font-size:12px;font-weight:600;padding:0 18px;}}"
            f"QPushButton:hover{{background:{CP['bg3']};color:{CP['text_primary']};}}"
            f"QPushButton:disabled{{color:{CP['text_dim']};}}")
    return b


def _note(text: str) -> QLabel:
    lbl = QLabel(translate(text))
    lbl.setWordWrap(True)
    lbl.setStyleSheet(f"color:{CP['text_dim']};font-size:10px;background:transparent;border:none;")
    return lbl


class AiodosConnectDialog(QDialog):
    """La demande d'accès : le code à 6 chiffres, le même que sur la carte
    d'AIODOS, et « Annuler ». Le fil de connexion vit le temps de la fenêtre."""

    def __init__(self, parent=None, upgrade: bool = False):
        super().__init__(parent)
        self.setWindowTitle(translate("Demander l'accès manquant" if upgrade
                                      else "Se connecter à AIODOS"))
        self.setModal(True)
        self.setMinimumWidth(460)
        self.setStyleSheet(f"QDialog{{background:{CP['bg1']};}}")
        self.result_status = None
        lay = QVBoxLayout(self)
        lay.setContentsMargins(26, 22, 26, 20)
        lay.setSpacing(12)
        intro = QLabel(translate(
            "AIODOS va afficher la demande du droit qui manque à PANDORA. Vérifiez que le "
            "code y est le même, puis autorisez-le." if upgrade else
            "AIODOS va afficher une demande d'accès de PANDORA. Vérifiez que le code "
            "y est le même, puis autorisez PANDORA."))
        intro.setWordWrap(True)
        intro.setStyleSheet(f"color:{CP['text_secondary']};font-size:12px;background:transparent;")
        lay.addWidget(intro)
        self._code = QLabel("— — —")
        self._code.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._code.setStyleSheet(
            f"color:{CP['accent']};font-size:38px;font-weight:700;letter-spacing:6px;"
            f"font-family:'Consolas',monospace;background:{CP['bg2']};"
            f"border:1px solid {CP['border']};border-radius:10px;padding:14px;")
        lay.addWidget(self._code)
        self._state = QLabel(translate("Demande en cours…"))
        self._state.setWordWrap(True)
        self._state.setStyleSheet(f"color:{CP['text_dim']};font-size:11px;background:transparent;")
        lay.addWidget(self._state)
        row = QHBoxLayout()
        row.addStretch(1)
        self._cancel = _btn("Annuler")
        self._cancel.clicked.connect(self.reject)
        row.addWidget(self._cancel)
        lay.addLayout(row)
        from ui.widgets import disable_default_buttons
        disable_default_buttons(self)

        self._worker = _ConnectWorker()
        self._worker.code.connect(self._on_code)
        self._worker.done.connect(self._on_done)
        self._worker.failed.connect(self._on_failed)
        _keep(self._worker).start()

    def _on_code(self, code: str):
        self._code.setText(str(code or "").strip() or "— — —")
        self._state.setText(translate("Autorisez PANDORA dans la fenêtre d'AIODOS."))

    def _on_done(self, status):
        self.result_status = status
        self._worker = None
        self.accept()

    def _on_failed(self, msg: str):
        self._worker = None
        self._state.setText(msg)
        self._state.setStyleSheet("color:#f0b429;font-size:11px;background:transparent;")
        self._cancel.setText(translate("Fermer"))

    def reject(self):
        if self._worker is not None:
            from core.worker import abandon_thread
            abandon_thread(self._worker)      # la demande s'arrête (cancel), sans terminate
            self._worker = None
        super().reject()


class AiodosPanel(QWidget):
    """État + actions + réglage « Calcul ». Auto-enregistré."""

    #: Émis après chaque lecture d'état : le résumé (déjà traduit) de la section.
    summary_changed = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet("background:transparent;")
        self._status = None
        self._busy = False
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(10)

        # Relecture du 28/10/2026 : AIODOS relie D'ABORD des inconnus par Internet.
        lay.addWidget(_note(
            "AIODOS (22eme Arkane) relie par Internet les machines de personnes qui ne se "
            "connaissent pas, pour mettre leur puissance en commun ; vos propres machines "
            "et le réseau local viennent ensuite. Installé, il prête par défaut une part de "
            "ce PC au réseau public (60 % de sa puissance au plus, jamais sur batterie ; "
            "tout se coupe dans ses Réglages). Les travaux de PANDORA restent là où vous le "
            "choisissez ci-dessous : par défaut ce PC, et une référence ou un clip jamais "
            "ailleurs que sur vos machines. AIODOS se met à jour seul : PANDORA lui parle "
            "sans l'embarquer."))

        self._state = QLabel(translate("État d'AIODOS : non vérifié."))
        self._state.setWordWrap(True)
        self._state.setStyleSheet(
            f"color:{CP['text_secondary']};font-size:12px;background:transparent;border:none;")
        lay.addWidget(self._state)

        row = QHBoxLayout()
        row.setSpacing(8)
        self._btn_launch = _btn("Lancer AIODOS")
        self._btn_launch.clicked.connect(self._launch)
        self._btn_connect = _btn("Se connecter à AIODOS", primary=True)
        self._btn_connect.clicked.connect(self._connect)
        self._btn_disconnect = _btn("Se déconnecter")
        self._btn_disconnect.clicked.connect(self._disconnect)
        self._btn_refresh = _btn("Actualiser")
        self._btn_refresh.clicked.connect(self.refresh)
        for b in (self._btn_launch, self._btn_connect, self._btn_disconnect, self._btn_refresh):
            row.addWidget(b)
        row.addStretch(1)
        lay.addLayout(row)

        crow = QHBoxLayout()
        crow.setSpacing(8)
        lbl = QLabel(translate("Calcul des gabarits ComfyUI"))
        lbl.setStyleSheet(f"color:{CP['text_secondary']};font-size:12px;background:transparent;")
        crow.addWidget(lbl)
        self._compute = ComputeCombo(height=32)
        hub.compute_changed.connect(self._on_compute_changed)
        self._compute.setMinimumWidth(230)
        crow.addWidget(self._compute)
        crow.addStretch(1)
        lay.addLayout(crow)

        lay.addWidget(_note(
            "Un droit décoché sur la carte d'accord d'AIODOS (les images et vidéos, par "
            "exemple) se redemande ici : « Demander l'accès manquant ». Les lieux de calcul "
            "d'un accès déjà donné ne changent pas ainsi : pour les modifier, « Se "
            "déconnecter », puis « Se connecter à AIODOS »."))
        lay.addWidget(_note(
            "Ce que PANDORA envoie à AIODOS : le graphe du gabarit, le prompt et les images "
            "ou le clip qu'il lit. Avec une image de référence ou un clip, le calcul reste "
            "sur ce PC et vos machines, jamais chez des amis ni sur le réseau public. La clé "
            "d'accès est gardée chiffrée sur ce PC (jamais dans config.json)."))
        self._apply(None)

    # ── État ────────────────────────────────────────────────────────────────

    def showEvent(self, event):
        super().showEvent(event)
        if self._status is None and not self._busy:
            QTimer.singleShot(0, self.refresh)

    def refresh(self):
        if self._busy:
            return
        self._set_busy(True, translate("Lecture de l'état d'AIODOS…"))

        def call(_w):
            from core import aiodos
            aiodos.forget_status()
            return aiodos.status(max_age=0)
        self._run(call, self._on_status)

    def _on_status(self, st):
        self._set_busy(False)
        self._apply(st)

    def _apply(self, st):
        from core import aiodos
        self._status = st
        state = getattr(st, "state", None)
        ok = state == "ready"
        # Connecté, mais un droit de SCOPES décoché sur la carte d'AIODOS
        # (engines:comfyui…) : le bouton reste, pour le redemander.
        missing = aiodos.missing_scopes(st) if ok else []
        if st is None:
            text = translate("État d'AIODOS : non vérifié.")
        else:
            text = str(getattr(st, "message", "") or state)
            extra = []
            if getattr(st, "version", None):
                extra.append(translate("version {v}").format(v=st.version))
            if ok:
                circles = [c for c in (getattr(st, "where", ()) or ())]
                if circles:
                    extra.append(aiodos.places_text(circles))
            if missing:
                extra.append(translate("droit manquant : {what}").format(
                    what=", ".join(translate(aiodos.SCOPE_LABELS.get(s, s)) for s in missing)))
            if extra:
                text += "  ·  " + "  ·  ".join(extra)
        self._state.setText(("✓  " if ok and not missing else "") + text)
        self._state.setStyleSheet(
            f"color:{CP['accent'] if ok and not missing else (CP['text_secondary'] if st is None else '#f0b429')};"
            "font-size:12px;background:transparent;border:none;")
        installed = st is not None and state != "not_installed"
        self._btn_launch.setVisible(state == "not_running")
        self._btn_connect.setText(translate("Demander l'accès manquant" if missing
                                            else "Se connecter à AIODOS"))
        self._btn_connect.setVisible(installed and (bool(missing) or state not in (
            "ready", "too_old", "not_aiodos")))
        self._btn_disconnect.setVisible(state in ("ready", "revoked", "untrusted", "other_account"))
        if st is None:
            summary = ""
        elif ok and missing:
            summary = translate("connecté · droit manquant")
        elif ok:
            summary = translate("connecté") + " · " + compute_label()
        elif state == "not_installed":
            summary = translate("non installé")
        else:
            summary = translate("non connecté")
        self.summary_changed.emit(summary)

    def _on_compute_changed(self, _mode: str):
        try:
            self._apply(self._status)
        except (RuntimeError, AttributeError):            # panneau détruit
            pass

    # ── Actions (sur un clic seulement) ─────────────────────────────────────

    def _launch(self):
        self._set_busy(True, translate("Lancement d'AIODOS…"))

        def call(w):
            from core import aiodos
            return aiodos.launch(cancel=w.isInterruptionRequested)
        self._run(call, self._on_status)

    def _connect(self):
        from core import aiodos
        dlg = AiodosConnectDialog(self, upgrade=bool(aiodos.missing_scopes(self._status)
                                                     if self._status is not None else False))
        dlg.exec()
        self.refresh()

    def _disconnect(self):
        self._set_busy(True, translate("Déconnexion…"))

        def call(_w):
            from core import aiodos
            aiodos.disconnect()
            return aiodos.status(max_age=0)
        self._run(call, self._on_status)

    # ── Outils ──────────────────────────────────────────────────────────────

    def _run(self, fn, on_done):
        w = _CallWorker(fn)
        w.done.connect(on_done)
        w.failed.connect(self._on_failed)
        _keep(w).start()

    def _on_failed(self, msg: str):
        self._set_busy(False)
        self._state.setText(msg)
        self._state.setStyleSheet("color:#f0b429;font-size:12px;background:transparent;border:none;")

    def _set_busy(self, busy: bool, text: str = ""):
        self._busy = busy
        for b in (self._btn_launch, self._btn_connect, self._btn_disconnect, self._btn_refresh):
            b.setEnabled(not busy)
        if busy and text:
            self._state.setText(text)
            self._state.setStyleSheet(
                f"color:{CP['text_dim']};font-size:12px;background:transparent;border:none;")
