"""ui/choreo_dialog.py — Fenêtre « Mise en scène par l'IA » du Plan de feu (Claude chorégraphe).

On décrit l'action du plan en mots ; l'IA (tâche « choreography ») propose les keyframes des
personnages — et de la caméra si on lui demande un mouvement ; PANDORA les vérifie puis les pose
sur la frise. « Revenir aux keyframes d'avant » annule la proposition. La dernière demande et le
résumé de l'IA sont gardés avec la scène du plan : rouvrir la fenêtre les retrouve, sans
relancer l'appel (rien n'est refacturé sans un clic sur « Mettre en scène »).
"""
from __future__ import annotations

import time

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (QDialog, QHBoxLayout, QLabel, QPlainTextEdit, QPushButton,
                             QVBoxLayout)

from core.i18n import translate
from ui.styles import CP
from ui.widgets import disable_default_buttons


class ChoreoDialog(QDialog):
    """apply_tracks(dict) : keyframes à poser (ou à rétablir) ; remember(dict) : à garder avec la scène."""

    apply_tracks = pyqtSignal(dict)
    remember = pyqtSignal(dict)

    def __init__(self, scene: dict, shot: dict | None, parent=None):
        super().__init__(parent)
        self.setWindowTitle(translate("Mise en scène par l'IA"))
        self.setMinimumWidth(620)
        self._scene = scene
        self._shot = shot or {}
        self._worker = None
        self._undo: dict | None = None
        lay = QVBoxLayout(self)
        intro = QLabel(translate(
            "Décrivez ce qui se passe pendant le plan : qui entre, d'où, où il va, ce qu'il fait, "
            "à quel moment. L'IA pose les keyframes des personnages sur la frise ; vous les ajustez "
            "ensuite dans la vue."))
        intro.setWordWrap(True)
        intro.setStyleSheet(f"color:{CP['text_secondary']};font-size:11px;")
        lay.addWidget(intro)
        self.text = QPlainTextEdit()
        self.text.setMinimumHeight(140)
        last = ((scene.get("pandora") or {}).get("choreo") or {})
        self.text.setPlainText(last.get("request") or self._default_request())
        lay.addWidget(self.text)
        self.result = QLabel(last.get("notes", ""))
        self.result.setWordWrap(True)
        self.result.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.result.setStyleSheet(f"color:{CP['text_primary']};font-size:11px;")
        lay.addWidget(self.result)
        row = QHBoxLayout()
        self.btn_undo = QPushButton(translate("Revenir aux keyframes d'avant"))
        self.btn_undo.setVisible(False)
        self.btn_undo.clicked.connect(self._revert)
        row.addWidget(self.btn_undo)
        row.addStretch(1)
        self.btn_run = QPushButton(translate("Mettre en scène"))
        self.btn_run.clicked.connect(self._run)
        row.addWidget(self.btn_run)
        close = QPushButton(translate("Fermer"))
        close.clicked.connect(self.close)
        row.addWidget(close)
        lay.addLayout(row)
        disable_default_buttons(self)

    def _default_request(self) -> str:
        """Point de départ : l'action du plan au storyboard (section [🎬 ACTION] du prompt)."""
        try:
            from core.prompt_sections import parse
            action = parse(self._shot.get("seedance_prompt", "") or "").get("action", "")
        except Exception:
            action = ""
        return (action or self._shot.get("scene_title", "") or "").strip()

    def _run(self):
        request = self.text.toPlainText().strip()
        if not request or self._worker is not None:
            return
        from api.choreo_worker import ChoreoWorker
        self.btn_run.setEnabled(False)
        self.result.setText(translate("L'IA met le plan en scène…"))
        w = ChoreoWorker(self._scene, request, self._shot)
        w.done.connect(lambda out: self._done(request, out))
        w.failed.connect(self._failed)
        self._worker = w
        w.start()

    def _done(self, request: str, out: dict):
        self._park()
        tracks = out.get("tracks") or {}
        prev = (self._scene.get("pandora") or {}).get("tracks") or {}
        self._undo = {oid: list(prev.get(oid) or []) for oid in tracks}
        self.apply_tracks.emit(tracks)
        names = {o.get("id"): o.get("name") for o in self._scene.get("objects") or []}
        lines = [out.get("notes") or translate("Mise en scène posée sur la frise.")]
        lines.append(translate("Keyframes posées : ") + ", ".join(
            f"{names.get(k) or k} ({len(v)})" for k, v in tracks.items()))
        if out.get("warnings"):
            lines.append(translate("Écarté : ") + " ; ".join(out["warnings"][:4]))
        self.result.setText("\n".join(lines))
        self.btn_undo.setVisible(True)
        self.remember.emit({"request": request, "notes": out.get("notes", ""), "at": int(time.time())})

    def _failed(self, msg: str):
        self._park()
        self.result.setText(translate("Mise en scène impossible : ") + msg)

    def _park(self):
        from core.worker import abandon_thread
        if self._worker is not None:
            abandon_thread(self._worker)
        self._worker = None
        self.btn_run.setEnabled(True)

    def _revert(self):
        if self._undo is not None:
            self.apply_tracks.emit(self._undo)
            self._undo = None
            self.btn_undo.setVisible(False)
            self.result.setText(translate("Keyframes d'avant rétablies."))
