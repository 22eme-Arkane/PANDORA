from PyQt6.QtCore import QThread, pyqtSignal
from core.config import load_config

_SYSTEM_DAVINCI_EDIT = (
    "You are an expert Seedance 2.0 reference-to-video prompt engineer. "
    "The source clip is provided as @Video1. "
    "Your task: rewrite the user's modification request into an optimized prompt.\n\n"
    "Rules:\n"
    "- Write in English only\n"
    "- Stay under 400 characters\n"
    "- Start with '@Video1' to reference the source clip\n"
    "- Preserve explicitly: characters, faces, camera movement, lighting mood unless user asks to change them\n"
    "- Describe ONLY what changes: replace/transform specific elements (background, props, effects, time of day)\n"
    "- Use cinematic vocabulary: seamless transition, same framing, matching camera angle, etc.\n"
    "- Output ONLY the enhanced prompt — no explanation, no quotes"
)

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

    def __init__(self, prompt: str, system: str | None = None):
        super().__init__()
        self._prompt = prompt
        self._system = system if system is not None else _SYSTEM

    def run(self):
        from core.ai_provider import complete, key_error
        err = key_error("enhance")
        if err:
            self.failed.emit(err)
            return
        try:
            enhanced = complete(self._system, self._prompt,
                                tier="utility", max_tokens=300, task="enhance").strip()
            self.finished.emit(enhanced)
        except Exception as e:
            self.failed.emit(str(e)[:200])


class EnhanceShotActionWorker(QThread):
    finished = pyqtSignal(str)
    failed   = pyqtSignal(str)

    def __init__(self, text: str):
        super().__init__()
        self._text = text

    def run(self):
        from core.ai_provider import complete, key_error
        err = key_error("enhance")
        if err:
            self.failed.emit(err)
            return
        try:
            try:
                from core.i18n import get_lang
                lang = get_lang()
            except Exception:
                lang = "fr"
            self.finished.emit(complete(_system_action(lang), self._text,
                                        tier="utility", max_tokens=200, task="enhance").strip())
        except Exception as e:
            self.failed.emit(str(e)[:200])
