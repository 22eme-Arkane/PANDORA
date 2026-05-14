"""
api/tts.py — Workers audio pour la page Doublage.

Modèles fal.ai utilisés :
  - Kokoro TTS       : fal-ai/kokoro          — $0.02/1000 chars
  - BiRefNet         : fal-ai/birefnet         — détourage fond, PNG alpha
"""

import os
import time

from PyQt6.QtCore import QThread, pyqtSignal
from core.config import load_config
from core.pandora_dirs import get_bin_dir


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
            self.failed.emit(f"Erreur Kokoro TTS : {e}")


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
            self.failed.emit(f"Erreur BiRefNet : {e}")
