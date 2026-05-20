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
        cfg = load_config()
        key = cfg.get("anthropic_key", "").strip()
        if not key:
            time.sleep(0.2)
            self.finished.emit(
                "Configurez votre clé Anthropic dans Paramètres pour activer l'assistant."
            )
            return
        try:
            import anthropic
            client = anthropic.Anthropic(api_key=key)

            # Garder les 3 derniers échanges (6 messages max)
            recent = list(self._history[-6:])
            recent.append({"role": "user", "content": self._question})

            resp = client.messages.create(
                model="claude-haiku-4-5",
                max_tokens=250,
                system=(
                    "Tu es l'assistant intégré de PANDORA, un logiciel de pré-production "
                    "cinéma pour DaVinci Resolve. Tu réponds en français, de façon concise "
                    "(2-3 phrases maximum, pas de liste à puces). Tu donnes des réponses "
                    "pratiques et directes, sans formules d'introduction. "
                    f"Contexte de la page active : {self._page_context}"
                ),
                messages=recent,
            )
            self.finished.emit(resp.content[0].text.strip())
        except Exception as e:
            self.failed.emit(f"Erreur assistant : {e}")
