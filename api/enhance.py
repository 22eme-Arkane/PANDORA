from PyQt6.QtCore import QThread, pyqtSignal
from core.config import load_config

_SYSTEM_SEEDANCE = (
    "You are an expert Seedance 2.0 video prompt engineer. "
    "Rewrite the user's prompt to maximize cinematic video quality.\n\n"
    "Rules:\n"
    "- Write in English only\n"
    "- Stay under 400 characters\n"
    "- Be specific: camera movement, lens, lighting, mood, color palette, subject action\n"
    "- Use cinematic vocabulary: tracking shot, golden hour, bokeh, dutch angle, rack focus, etc.\n"
    "- Preserve the original scene intent\n"
    "- Output ONLY the enhanced prompt — no explanation, no quotes"
)

def _system_action(lang: str = "fr") -> str:
    output_lang = "English" if lang == "en" else "French"
    return (
        "You are a professional script supervisor and storyboard artist. "
        "Rewrite the user's shot action description for a storyboard.\n\n"
        f"Rules:\n"
        f"- Write in {output_lang}\n"
        "- One clear sentence, present tense\n"
        "- Describe who does what and where (subject + action + setting)\n"
        "- Stay under 120 characters — concise and precise\n"
        "- Do NOT describe camera movements or technical parameters\n"
        "- Output ONLY the rewritten description — no explanation, no quotes"
    )

_SYSTEM_ACTION = _system_action("fr")

# Keep backward compat alias
_SYSTEM = _SYSTEM_SEEDANCE


class EnhanceWorker(QThread):
    finished = pyqtSignal(str)
    failed   = pyqtSignal(str)

    def __init__(self, prompt: str):
        super().__init__()
        self._prompt = prompt

    def run(self):
        cfg = load_config()
        key = cfg.get("anthropic_key", "").strip()
        if not key:
            self.failed.emit(
                "Clé API Anthropic manquante.\n"
                "Configure-la dans l'onglet Config → Clé API Anthropic."
            )
            return
        try:
            import anthropic
            client = anthropic.Anthropic(api_key=key)
            msg = client.messages.create(
                model="claude-haiku-4-5",
                max_tokens=300,
                system=_SYSTEM,
                messages=[{"role": "user", "content": self._prompt}],
            )
            enhanced = msg.content[0].text.strip()
            self.finished.emit(enhanced)
        except ImportError:
            self.failed.emit(
                "Module 'anthropic' manquant.\n"
                "Installe-le : pip install anthropic"
            )
        except Exception as e:
            self.failed.emit(str(e)[:200])


class EnhanceShotActionWorker(QThread):
    finished = pyqtSignal(str)
    failed   = pyqtSignal(str)

    def __init__(self, text: str):
        super().__init__()
        self._text = text

    def run(self):
        cfg = load_config()
        key = cfg.get("anthropic_key", "").strip()
        if not key:
            self.failed.emit(
                "Clé API Anthropic manquante.\n"
                "Configure-la dans l'onglet Config → Clé API Anthropic."
            )
            return
        try:
            import anthropic
            try:
                from core.i18n import get_lang
                lang = get_lang()
            except Exception:
                lang = "fr"
            client = anthropic.Anthropic(api_key=key)
            msg = client.messages.create(
                model="claude-haiku-4-5",
                max_tokens=200,
                system=_system_action(lang),
                messages=[{"role": "user", "content": self._text}],
            )
            self.finished.emit(msg.content[0].text.strip())
        except ImportError:
            self.failed.emit(
                "Module 'anthropic' manquant.\n"
                "Installe-le : pip install anthropic"
            )
        except Exception as e:
            self.failed.emit(str(e)[:200])
