"""
api/assistant.py — Worker Claude Haiku pour l'assistant pédagogique contextuel.

Coût indicatif : ~$0.003 / réponse (250 tokens output).
"""

import time
from PyQt6.QtCore import QThread, pyqtSignal
from core.config import load_config


class AssistantWorker(QThread):
    """Répond à une question contextuelle via Claude Haiku."""
    finished = pyqtSignal(str)
    failed   = pyqtSignal(str)

    def __init__(self, question: str, page_context: str, history: list):
        super().__init__()
        self._question     = question
        self._page_context = page_context
        self._history      = history   # [{"role": "user"/"assistant", "content": str}]

    def run(self):
        from core.ai_provider import chat, key_error
        if key_error("assistant"):
            time.sleep(0.2)
            self.finished.emit(
                "Configurez votre clé IA dans Paramètres pour activer l'assistant."
            )
            return
        try:
            # Garder les 3 derniers échanges (6 messages max)
            recent = list(self._history[-6:])
            recent.append({"role": "user", "content": self._question})

            out = chat(
                (
                    "Tu es l'assistant intégré de PANDORA, un logiciel de pré-production "
                    "cinéma pour DaVinci Resolve. Tu réponds en français, de façon concise "
                    "(2-3 phrases maximum, pas de liste à puces). Tu donnes des réponses "
                    "pratiques et directes, sans formules d'introduction. "
                    f"Contexte de la page active : {self._page_context}"
                ),
                recent, tier="creative", max_tokens=250, task="assistant",
            )
            self.finished.emit(out.strip())
        except Exception as e:
            self.failed.emit(f"Erreur assistant : {e}")
