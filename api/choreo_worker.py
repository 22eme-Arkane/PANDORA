"""api/choreo_worker.py — Appel de Claude chorégraphe (core/choreo) dans un fil.

Signaux : done(dict) = {"tracks", "notes", "warnings"} déjà VALIDÉS par core/choreo.parse ;
failed(str) = message lisible (humanize_ai_error). Tâche « choreography » de core/ai_provider
(Sonnet par défaut, réglable dans Paramètres comme les autres tâches).
"""
from __future__ import annotations

from PyQt6.QtCore import QThread, pyqtSignal


class ChoreoWorker(QThread):
    done = pyqtSignal(dict)
    failed = pyqtSignal(str)

    def __init__(self, scene: dict, request: str, shot: dict | None = None):
        super().__init__()
        self._scene = scene
        self._request = request
        self._shot = shot

    def run(self):
        from core import choreo
        from core.ai_provider import chat_ex, humanize_ai_error, key_error
        err = key_error(task=choreo.TASK)
        if err:
            self.failed.emit(err)
            return
        try:
            system, msgs = choreo.messages(self._scene, self._request, self._shot)
            res = chat_ex(system, msgs, tier="creative", max_tokens=6000, task=choreo.TASK)
            if res.get("truncated"):
                self.failed.emit("La réponse de l'IA a été coupée avant la fin : décrivez une "
                                 "mise en scène plus courte, ou moins de personnages à la fois.")
                return
            out = choreo.parse(res.get("text", ""), self._scene)
            if not out["tracks"]:
                self.failed.emit("L'IA n'a proposé aucune marque utilisable."
                                 + (" " + " ; ".join(out["warnings"][:3]) if out["warnings"] else ""))
                return
            self.done.emit(out)
        except ValueError as e:
            self.failed.emit(f"Réponse de l'IA illisible : {e}")
        except Exception as e:
            self.failed.emit(humanize_ai_error(str(e)))
