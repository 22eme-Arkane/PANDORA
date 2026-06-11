"""
api/tts.py — Workers audio pour la page Doublage.

Modèles fal.ai utilisés :
  - ElevenLabs Turbo v2.5 : fal-ai/elevenlabs/tts/turbo-v2.5 — $0.05/1000 chars, multilingue FR
  - Index TTS 2           : fal-ai/index-tts-2/text-to-speech — $0.002/s, clonage voix multilingue
  - SFX 1.6 (Mirelo AI)  : mirelo-ai/sfx1.6/text-to-audio    — $0.01/s, ambiances sonores
  - Kokoro TTS            : fal-ai/kokoro                     — $0.02/1000 chars (conservé pour pipeline)
  - Lux TTS               : fal-ai/lux-tts                    — $0.0014/1000 chars (conservé pour pipeline)
  - BiRefNet              : fal-ai/birefnet                   — détourage fond, PNG alpha
"""

import os
import time

from PyQt6.QtCore import QThread, pyqtSignal
from core.config import load_config
from core.pandora_dirs import get_bin_dir
from core.worker import humanize_api_error


# ── Voix Kokoro disponibles ───────────────────────────────────────────────────

KOKORO_VOICES = {
    # Anglais US (féminin)
    "af_heart":   "Heart (EN-US F)",
    "af_alloy":   "Alloy (EN-US F)",
    "af_bella":   "Bella (EN-US F)",
    "af_jessica": "Jessica (EN-US F)",
    "af_nicole":  "Nicole (EN-US F)",
    "af_nova":    "Nova (EN-US F)",
    "af_sarah":   "Sarah (EN-US F)",
    "af_sky":     "Sky (EN-US F)",
    # Anglais US (masculin)
    "am_adam":    "Adam (EN-US M)",
    "am_echo":    "Echo (EN-US M)",
    "am_eric":    "Eric (EN-US M)",
    "am_liam":    "Liam (EN-US M)",
    "am_michael": "Michael (EN-US M)",
    "am_onyx":    "Onyx (EN-US M)",
    # Anglais GB (féminin)
    "bf_alice":   "Alice (EN-GB F)",
    "bf_emma":    "Emma (EN-GB F)",
    "bf_isabella":"Isabella (EN-GB F)",
    "bf_lily":    "Lily (EN-GB F)",
    # Anglais GB (masculin)
    "bm_daniel":  "Daniel (EN-GB M)",
    "bm_fable":   "Fable (EN-GB M)",
    "bm_george":  "George (EN-GB M)",
    "bm_lewis":   "Lewis (EN-GB M)",
    # Espagnol
    "ef_dora":    "Dora (ES F)",
    "em_alex":    "Alex (ES M)",
    # Portugais BR
    "pf_dora":    "Dora (PT-BR F)",
    "pm_alex":    "Alex (PT-BR M)",
    # Italien
    "if_sara":    "Sara (IT F)",
    "im_nicola":  "Nicola (IT M)",
    # Japonais
    "jf_alpha":   "Alpha (JA F)",
    "jm_kumo":    "Kumo (JA M)",
    # Mandarin
    "zf_xiaobei": "Xiaobei (ZH F)",
    "zm_yunxi":   "Yunxi (ZH M)",
}

# Voix recommandées pour le doublage (claires, naturelles)
KOKORO_VOICES_RECOMMENDED = [
    "af_heart", "af_jessica", "af_nova", "af_sarah",
    "am_adam",  "am_eric",    "am_michael",
    "bf_alice", "bf_emma",    "bm_daniel", "bm_george",
]


def _audio_output_dir() -> str:
    """Dossier de sortie des fichiers audio."""
    try:
        from core.context import get_data_root
        root = get_data_root()
        d = os.path.join(root, "doublage", "audio")
    except Exception:
        d = get_bin_dir("doublage_audio")
    os.makedirs(d, exist_ok=True)
    return d


# ── Worker Kokoro TTS ─────────────────────────────────────────────────────────

class KokoroTTSWorker(QThread):
    """Génère un fichier audio WAV depuis un texte via Kokoro (fal-ai/kokoro)."""
    progress = pyqtSignal(int, str)
    finished = pyqtSignal(str)   # chemin local du fichier WAV
    failed   = pyqtSignal(str)

    def __init__(self, text: str, voice: str = "af_heart", speed: float = 1.0,
                 label: str = ""):
        super().__init__()
        self._text  = text
        self._voice = voice
        self._speed = speed
        self._label = label or "audio"

    def run(self):
        cfg = load_config()
        key = cfg.get("api_key", "").strip()
        if not key:
            self._mock()
        else:
            self._real(key)

    def _mock(self):
        steps = [
            (20, "Synthèse vocale (mode mock)…"),
            (60, "Génération de l'audio…"),
            (90, "Post-traitement…"),
            (100, "Terminé — mode mock (aucune clé fal.ai)"),
        ]
        for pct, msg in steps:
            self.progress.emit(pct, msg)
            time.sleep(0.4)
        self.finished.emit("")

    def _real(self, key: str):
        try:
            import fal_client
            import requests

            os.environ["FAL_KEY"] = key
            self.progress.emit(10, "Connexion Kokoro TTS…")

            n_chars = len(self._text)
            cost_est = n_chars / 1000 * 0.02
            self.progress.emit(20,
                f"Synthèse {n_chars} caractères (~${cost_est:.4f})…")

            result = fal_client.subscribe(
                "fal-ai/kokoro",
                arguments={
                    "prompt": self._text,
                    "voice":  self._voice,
                    "speed":  self._speed,
                },
            )

            audio = result.get("audio") if isinstance(result, dict) else None
            if not audio:
                raise RuntimeError(f"Réponse inattendue : {str(result)[:200]}")

            url = audio.get("url", "")
            if not url:
                raise RuntimeError("URL audio manquante dans la réponse.")

            self.progress.emit(70, "Téléchargement du fichier audio…")
            data = requests.get(url, timeout=120).content

            safe = "".join(c for c in self._label if c.isalnum() or c in " -_").strip() or "voice"
            ts   = int(time.time())
            path = os.path.join(_audio_output_dir(), f"{safe}_{ts}.wav")
            with open(path, "wb") as f:
                f.write(data)

            self.progress.emit(100, f"Audio généré ✓  (~${cost_est:.4f})")
            self.finished.emit(path)

        except Exception as e:
            self.failed.emit(humanize_api_error(f"Erreur Kokoro TTS : {e}"))


# ── Worker Lux TTS — clonage de voix ─────────────────────────────────────────

class LuxTTSWorker(QThread):
    """
    Clonage de voix via Lux TTS (fal-ai/lux-tts).
    Prend un échantillon audio de référence + un texte → audio 48kHz avec la voix clonée.
    Coût : ~$0.0014/1000 chars.
    """
    progress = pyqtSignal(int, str)
    finished = pyqtSignal(str)   # chemin local du fichier audio
    failed   = pyqtSignal(str)

    def __init__(self, text: str, voice_sample_path: str, label: str = ""):
        super().__init__()
        self._text              = text
        self._voice_sample_path = voice_sample_path
        self._label             = label or "lux_voice"

    def run(self):
        cfg = load_config()
        key = cfg.get("api_key", "").strip()
        if not key:
            self._mock()
        else:
            self._real(key)

    def _mock(self):
        steps = [
            (20, "Clonage voix (mode mock)…"),
            (60, "Synthèse vocale clonée…"),
            (90, "Finalisation…"),
            (100, "Terminé — mode mock (aucune clé fal.ai)"),
        ]
        for pct, msg in steps:
            self.progress.emit(pct, msg)
            time.sleep(0.4)
        self.finished.emit("")

    def _real(self, key: str):
        try:
            import fal_client
            import requests

            os.environ["FAL_KEY"] = key
            fal_client.api_key = key

            # Upload voice sample
            self.progress.emit(10, "Upload de l'échantillon vocal…")
            import sys, io as _io
            _cap = _io.StringIO()
            _old_out, _old_err = sys.stdout, sys.stderr
            sys.stdout = sys.stderr = _cap
            try:
                voice_url = fal_client.upload_file(self._voice_sample_path)
            finally:
                sys.stdout = _old_out
                sys.stderr = _old_err

            n_chars   = len(self._text)
            cost_est  = n_chars / 1000 * 0.0014
            self.progress.emit(30, f"Clonage vocal — {n_chars} caractères (~${cost_est:.4f})…")

            result = fal_client.subscribe(
                "fal-ai/lux-tts",
                arguments={
                    "audio_url": voice_url,
                    "prompt":    self._text,
                },
                with_logs=False,
            )

            audio_url = ""
            if isinstance(result, dict):
                audio_url = (
                    result.get("audio", {}).get("url", "")
                    or result.get("audio_url", "")
                )
            if not audio_url:
                raise RuntimeError(f"Réponse inattendue Lux TTS : {str(result)[:200]}")

            self.progress.emit(75, "Téléchargement du fichier audio…")
            data = requests.get(audio_url, timeout=120).content

            safe = "".join(c for c in self._label if c.isalnum() or c in " -_").strip() or "lux"
            ts   = int(time.time())
            path = os.path.join(_audio_output_dir(), f"{safe}_{ts}.wav")
            with open(path, "wb") as f:
                f.write(data)

            self.progress.emit(100, f"Voix clonée ✓  (~${cost_est:.4f})")
            self.finished.emit(path)

        except Exception as e:
            self.failed.emit(humanize_api_error(f"Erreur Lux TTS : {e}"))


# ── Worker BiRefNet — détourage fond ─────────────────────────────────────────

class RemoveBackgroundWorker(QThread):
    """Supprime le fond d'une image via BiRefNet (fal-ai/birefnet) → PNG alpha."""
    progress = pyqtSignal(int, str)
    finished = pyqtSignal(str)   # chemin local du PNG sans fond
    failed   = pyqtSignal(str)

    def __init__(self, image_path: str, out_dir: str = ""):
        super().__init__()
        self._path    = image_path
        self._out_dir = out_dir

    def run(self):
        cfg = load_config()
        key = cfg.get("api_key", "").strip()
        if not key:
            self._mock()
        else:
            self._real(key)

    def _mock(self):
        steps = [
            (30, "Détourage fond (mode mock)…"),
            (80, "Suppression du fond…"),
            (100, "Terminé — mode mock"),
        ]
        for pct, msg in steps:
            self.progress.emit(pct, msg)
            time.sleep(0.3)
        self.finished.emit("")

    def _real(self, key: str):
        try:
            import fal_client
            import requests
            import base64, mimetypes
            from pathlib import Path

            os.environ["FAL_KEY"] = key
            self.progress.emit(10, "Encodage de l'image…")

            # Encode locally as data URL — avoids fal_client.upload_file() which requires GCS
            _mime = mimetypes.guess_type(self._path)[0] or "image/png"
            with open(self._path, "rb") as _f:
                _b64 = base64.b64encode(_f.read()).decode()
            image_url = f"data:{_mime};base64,{_b64}"
            self.progress.emit(30, "Détourage du fond (BiRefNet)…")

            result = fal_client.subscribe(
                "fal-ai/birefnet",
                arguments={"image_url": image_url},
            )

            if not isinstance(result, dict):
                raise RuntimeError(f"Réponse inattendue : {str(result)[:200]}")

            # BiRefNet retourne "image" ou "images"
            out_url = (
                result.get("image", {}).get("url") or
                (result.get("images") or [{}])[0].get("url") or
                ""
            )
            if not out_url:
                raise RuntimeError(f"URL image manquante : {str(result)[:200]}")

            self.progress.emit(70, "Téléchargement du résultat…")
            data = requests.get(out_url, timeout=120).content

            src = Path(self._path)
            out_dir = self._out_dir or str(src.parent)
            os.makedirs(out_dir, exist_ok=True)
            out_path = os.path.join(out_dir, f"{src.stem}_nobg.png")
            with open(out_path, "wb") as f:
                f.write(data)

            self.progress.emit(100, "Fond supprimé ✓")
            self.finished.emit(out_path)

        except Exception as e:
            self.failed.emit(humanize_api_error(f"Erreur BiRefNet : {e}"))


# ── ElevenLabs TTS Turbo v2.5 — voix multilingues ────────────────────────────

ELEVENLABS_VOICES = [
    "Charlotte", "River", "Alice", "Matilda", "Sarah", "Laura",
    "Aria", "Jessica", "Lily", "Callum", "Daniel", "George",
    "Brian", "Charlie", "Chris", "Eric", "Liam", "Roger", "Will", "Bill",
]

ELEVENLABS_VOICES_FR = [
    "Charlotte", "River", "Alice", "Matilda", "Lily",
    "Daniel", "George", "Brian",
]


class ElevenLabsWorker(QThread):
    """
    Génère un fichier audio via ElevenLabs TTS Turbo v2.5 (fal-ai).
    Supporte le français via language_code='fr'.
    Coût : ~$0.05/1000 chars.
    """
    progress = pyqtSignal(int, str)
    finished = pyqtSignal(str)
    failed   = pyqtSignal(str)

    def __init__(self, text: str, voice: str = "Charlotte",
                 language_code: str = "fr", speed: float = 1.0,
                 label: str = ""):
        super().__init__()
        self._text          = text
        self._voice         = voice
        self._language_code = language_code
        self._speed         = max(0.7, min(1.2, speed))
        self._label         = label or "elevenlabs"

    def run(self):
        cfg = load_config()
        key = cfg.get("api_key", "").strip()
        if not key:
            self._mock()
        else:
            self._real(key)

    def _mock(self):
        for pct, msg in [
            (20, "ElevenLabs TTS (mode mock)…"),
            (60, "Génération de l'audio…"),
            (100, "Terminé — mode mock (aucune clé fal.ai)"),
        ]:
            self.progress.emit(pct, msg)
            time.sleep(0.4)
        self.finished.emit("")

    def _real(self, key: str):
        try:
            import fal_client
            import requests

            os.environ["FAL_KEY"] = key
            self.progress.emit(10, "Connexion ElevenLabs TTS…")

            n_chars  = len(self._text)
            cost_est = n_chars / 1000 * 0.05
            self.progress.emit(20, f"Synthèse {n_chars} caractères (~${cost_est:.4f})…")

            args: dict = {
                "text":  self._text,
                "voice": self._voice,
                "speed": self._speed,
            }
            if self._language_code:
                args["language_code"] = self._language_code

            result = fal_client.subscribe(
                "fal-ai/elevenlabs/tts/turbo-v2.5",
                arguments=args,
            )

            audio_url = ""
            if isinstance(result, dict):
                audio = result.get("audio", {})
                audio_url = audio.get("url", "") if isinstance(audio, dict) else ""
                if not audio_url:
                    audio_url = result.get("url", "")
            if not audio_url:
                raise RuntimeError(f"URL audio manquante : {str(result)[:200]}")

            self.progress.emit(70, "Téléchargement du fichier audio…")
            data = requests.get(audio_url, timeout=120).content

            safe = "".join(c for c in self._label if c.isalnum() or c in " -_").strip() or "eleven"
            ts   = int(time.time())
            path = os.path.join(_audio_output_dir(), f"{safe}_{ts}.mp3")
            with open(path, "wb") as f:
                f.write(data)

            self.progress.emit(100, f"Audio généré ✓  (~${cost_est:.4f})")
            self.finished.emit(path)

        except Exception as e:
            self.failed.emit(humanize_api_error(f"Erreur ElevenLabs : {e}"))


# ── Index TTS 2 — clonage de voix multilingue ────────────────────────────────

class IndexTTS2Worker(QThread):
    """
    Clonage de voix multilingue via Index TTS 2 (fal-ai/index-tts-2).
    Supporte le français nativement.
    Coût : ~$0.002/s de son généré.
    """
    progress = pyqtSignal(int, str)
    finished = pyqtSignal(str)
    failed   = pyqtSignal(str)

    def __init__(self, text: str, voice_sample_path: str, label: str = "", language: str = "fr"):
        super().__init__()
        self._text              = text
        self._voice_sample_path = voice_sample_path
        self._label             = label or "indextts2"
        self._language          = language or "fr"

    def run(self):
        cfg = load_config()
        key = cfg.get("api_key", "").strip()
        if not key:
            self._mock()
        else:
            self._real(key)

    def _mock(self):
        for pct, msg in [
            (20, "Clonage voix Index TTS 2 (mode mock)…"),
            (60, "Synthèse vocale clonée…"),
            (100, "Terminé — mode mock (aucune clé fal.ai)"),
        ]:
            self.progress.emit(pct, msg)
            time.sleep(0.4)
        self.finished.emit("")

    def _real(self, key: str):
        try:
            import fal_client
            import requests

            os.environ["FAL_KEY"] = key
            fal_client.api_key = key

            # Upload voice sample
            self.progress.emit(10, "Upload de l'échantillon vocal…")
            import sys, io as _io
            _cap = _io.StringIO()
            _old_out, _old_err = sys.stdout, sys.stderr
            sys.stdout = sys.stderr = _cap
            try:
                voice_url = fal_client.upload_file(self._voice_sample_path)
            finally:
                sys.stdout = _old_out
                sys.stderr = _old_err

            self.progress.emit(30, "Clonage vocal Index TTS 2…")

            result = fal_client.subscribe(
                "fal-ai/index-tts-2/text-to-speech",
                arguments={
                    "prompt":    self._text,
                    "audio_url": voice_url,
                    "language":  self._language,
                },
                with_logs=False,
            )

            audio_url = ""
            if isinstance(result, dict):
                audio = result.get("audio", {})
                audio_url = audio.get("url", "") if isinstance(audio, dict) else ""
                if not audio_url:
                    audio_url = result.get("audio_url", "") or result.get("url", "")
            if not audio_url:
                raise RuntimeError(f"URL audio manquante : {str(result)[:200]}")

            self.progress.emit(75, "Téléchargement du fichier audio…")
            data = requests.get(audio_url, timeout=120).content

            safe = "".join(c for c in self._label if c.isalnum() or c in " -_").strip() or "indextts2"
            ts   = int(time.time())
            path = os.path.join(_audio_output_dir(), f"{safe}_{ts}.wav")
            with open(path, "wb") as f:
                f.write(data)

            self.progress.emit(100, "Voix clonée ✓  (~$0.002/s)")
            self.finished.emit(path)

        except Exception as e:
            self.failed.emit(humanize_api_error(f"Erreur Index TTS 2 : {e}"))


# ── F5-TTS — Clonage voix multilingue (FR/EN/ES/ZH…) ────────────────────────

class F5TTSWorker(QThread):
    """
    Clonage de voix multilingue via F5-TTS (fal-ai/f5-tts).
    Langue détectée automatiquement depuis le texte — pas de paramètre language.
    Supporte FR, EN, ES, DE, IT, ZH et plus.
    Coût : ~$0.003/s estimé.
    """
    progress = pyqtSignal(int, str)
    finished = pyqtSignal(str)
    failed   = pyqtSignal(str)

    def __init__(self, text: str, voice_sample_path: str, label: str = ""):
        super().__init__()
        self._text              = text
        self._voice_sample_path = voice_sample_path
        self._label             = label or "f5tts"

    def run(self):
        cfg = load_config()
        key = cfg.get("api_key", "").strip()
        if not key:
            self._mock()
        else:
            self._real(key)

    def _mock(self):
        for pct, msg in [
            (20, "Clonage voix F5-TTS (mode mock)…"),
            (60, "Synthèse vocale multilingue…"),
            (100, "Terminé — mode mock (aucune clé fal.ai)"),
        ]:
            self.progress.emit(pct, msg)
            time.sleep(0.4)
        self.finished.emit("")

    def _real(self, key: str):
        try:
            import fal_client
            import requests

            os.environ["FAL_KEY"] = key
            fal_client.api_key = key

            self.progress.emit(10, "Upload de l'échantillon vocal…")
            import sys, io as _io
            _cap = _io.StringIO()
            _old_out, _old_err = sys.stdout, sys.stderr
            sys.stdout = sys.stderr = _cap
            try:
                voice_url = fal_client.upload_file(self._voice_sample_path)
            finally:
                sys.stdout = _old_out
                sys.stderr = _old_err

            self.progress.emit(30, "Clonage vocal F5-TTS (détection langue auto)…")

            result = fal_client.subscribe(
                "fal-ai/f5-tts",
                arguments={
                    "gen_text":      self._text,
                    "ref_audio_url": voice_url,
                    "model_type":    "F5-TTS",
                    "remove_silence": True,
                },
                with_logs=False,
            )

            audio_url = ""
            if isinstance(result, dict):
                audio_obj = result.get("audio_url", {})
                audio_url = audio_obj.get("url", "") if isinstance(audio_obj, dict) else ""
                if not audio_url:
                    audio_url = result.get("url", "")
            if not audio_url:
                raise RuntimeError(f"URL audio manquante : {str(result)[:200]}")

            self.progress.emit(75, "Téléchargement du fichier audio…")
            data = requests.get(audio_url, timeout=120).content

            safe = "".join(c for c in self._label if c.isalnum() or c in " -_").strip() or "f5tts"
            ts   = int(time.time())
            path = os.path.join(_audio_output_dir(), f"{safe}_{ts}.wav")
            with open(path, "wb") as f:
                f.write(data)

            self.progress.emit(100, "Voix clonée ✓  (F5-TTS multilingue)")
            self.finished.emit(path)

        except Exception as e:
            self.failed.emit(humanize_api_error(f"Erreur F5-TTS : {e}"))


# ── SFX 1.6 — Ambiances sonores ──────────────────────────────────────────────

class SFX1Worker(QThread):
    """
    Génère des ambiances sonores depuis un texte via SFX 1.6 (Mirelo AI).
    Coût : ~$0.01/s de son généré.
    """
    progress = pyqtSignal(int, str)
    finished = pyqtSignal(str)
    failed   = pyqtSignal(str)

    def __init__(self, text: str, duration: float = 10.0, label: str = "",
                 out_dir: str = ""):
        super().__init__()
        self._text     = text
        self._duration = float(duration)
        self._label    = label or "sfx"
        self._out_dir  = out_dir   # vide = dossier Doublage par défaut

    def run(self):
        cfg = load_config()
        key = cfg.get("api_key", "").strip()
        if not key:
            self._mock()
        else:
            self._real(key)

    def _mock(self):
        for pct, msg in [
            (20, "Ambiance SFX 1.6 (mode mock)…"),
            (60, "Création sonore…"),
            (100, "Terminé — mode mock (aucune clé fal.ai)"),
        ]:
            self.progress.emit(pct, msg)
            time.sleep(0.4)
        self.finished.emit("")

    def _real(self, key: str):
        try:
            import fal_client
            import requests

            os.environ["FAL_KEY"] = key
            cost_est = self._duration * 0.01
            self.progress.emit(10, f"SFX 1.6 — {self._duration}s (~${cost_est:.2f})…")

            result = fal_client.subscribe(
                "mirelo-ai/sfx1.6/text-to-audio",
                arguments={
                    "text_prompt": self._text,
                    "duration":    self._duration,
                },
            )

            audio_url = ""
            if isinstance(result, dict):
                audio = result.get("audio", {})
                # ⚠ Schéma réel de l'API (vu en réel : 12 générations payées et
                # perdues) : "audio" est une LISTE d'objets [{url, file_name…}]
                if isinstance(audio, list) and audio:
                    first = audio[0]
                    audio_url = (first.get("url", "") if isinstance(first, dict)
                                 else first if isinstance(first, str) else "")
                elif isinstance(audio, dict):
                    audio_url = audio.get("url", "") or audio.get("ref", "")
                elif isinstance(audio, str):
                    audio_url = audio
                if not audio_url:
                    audio_url = (result.get("url", "") or result.get("ref", "")
                                 or result.get("audio_url", ""))
            if not audio_url:
                raise RuntimeError(f"URL audio manquante : {str(result)[:200]}")

            self.progress.emit(70, "Téléchargement de l'ambiance…")
            data = requests.get(audio_url, timeout=120).content

            safe = "".join(c for c in self._label if c.isalnum() or c in " -_").strip() or "sfx"
            ts   = int(time.time())
            out_dir = self._out_dir or _audio_output_dir()
            os.makedirs(out_dir, exist_ok=True)
            path = os.path.join(out_dir, f"{safe}_{ts}.wav")
            with open(path, "wb") as f:
                f.write(data)

            self.progress.emit(100, f"Ambiance générée ✓  {self._duration}s · ~${cost_est:.2f}")
            self.finished.emit(path)

        except Exception as e:
            self.failed.emit(humanize_api_error(f"Erreur SFX 1.6 : {e}"))


def _sfx_output_dir() -> str:
    """Dossier de sortie du sound design Live (vidéos sonorisées)."""
    try:
        from core.context import get_data_root
        d = os.path.join(get_data_root(), "live_sound_design")
    except Exception:
        d = get_bin_dir("live_sound_design")
    os.makedirs(d, exist_ok=True)
    return d


class SFX1VideoWorker(QThread):
    """
    SFX 1.6 video-to-video (Mirelo AI) : ajoute une bande-son SYNCHRONISÉE à un loop
    vidéo. Sortie = MP4 (loop + son généré). ~$0.01/s.
    Endpoint : mirelo-ai/sfx1.6/video-to-video
      Entrée  : video_url (requis), text_prompt (optionnel), duration (1–60, défaut 10)
      Sortie  : { "video": [ { "url": ... } ] }
    """
    progress = pyqtSignal(int, str)
    finished = pyqtSignal(str)
    failed   = pyqtSignal(str)

    def __init__(self, video_path: str, text_prompt: str = "",
                 duration: float = 10.0, label: str = ""):
        super().__init__()
        self._video    = video_path
        self._prompt   = text_prompt or ""
        self._duration = float(duration)
        self._label    = label or "sfx_video"

    def run(self):
        cfg = load_config()
        key = cfg.get("api_key", "").strip()
        if not key:
            self._mock()
        else:
            self._real(key)

    def _mock(self):
        for pct, msg in [
            (20, "Bande-son SFX 1.6 (mode mock)…"),
            (60, "Synchronisation sur la vidéo…"),
            (100, "Terminé — mode mock (aucune clé fal.ai)"),
        ]:
            self.progress.emit(pct, msg)
            time.sleep(0.4)
        self.finished.emit("")

    def _real(self, key: str):
        try:
            import fal_client
            import requests

            if not self._video or not os.path.isfile(self._video):
                raise RuntimeError("Vidéo introuvable.")
            os.environ["FAL_KEY"] = key
            cost_est = self._duration * 0.01

            self.progress.emit(8, "Envoi de la vidéo à fal.ai…")
            video_url = fal_client.upload_file(self._video)

            self.progress.emit(25, f"SFX 1.6 vidéo — {self._duration:.0f}s (~${cost_est:.2f})…")
            args = {"video_url": video_url, "duration": self._duration}
            if self._prompt.strip():
                args["text_prompt"] = self._prompt.strip()
            result = fal_client.subscribe("mirelo-ai/sfx1.6/video-to-video", arguments=args)

            out_url = ""
            if isinstance(result, dict):
                vids = result.get("video")
                if isinstance(vids, list) and vids:
                    first = vids[0]
                    out_url = (first.get("url", "") if isinstance(first, dict)
                               else first if isinstance(first, str) else "")
                elif isinstance(vids, dict):
                    out_url = vids.get("url", "")
                if not out_url:
                    out_url = result.get("url", "") or result.get("video_url", "")
            if not out_url:
                raise RuntimeError(f"URL vidéo manquante : {str(result)[:200]}")

            self.progress.emit(75, "Téléchargement de la vidéo sonorisée…")
            data = requests.get(out_url, timeout=300).content

            safe = "".join(c for c in self._label if c.isalnum() or c in " -_").strip() or "sfx_video"
            ts   = int(time.time())
            path = os.path.join(_sfx_output_dir(), f"{safe}_{ts}.mp4")
            with open(path, "wb") as f:
                f.write(data)

            self.progress.emit(100, f"Bande-son générée ✓  ~${cost_est:.2f}")
            self.finished.emit(path)

        except Exception as e:
            self.failed.emit(humanize_api_error(f"Erreur SFX 1.6 vidéo : {e}"))
