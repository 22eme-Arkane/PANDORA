"""api/voice_changer.py — Conversion de timbre (ElevenLabs Voice Changer).

Le problème du français mal prononcé vient de la PROSODIE : un modèle entraîné
surtout sur de l'anglais place mal les liaisons, les nasales et l'accent
tonique. Aucun réglage de voix ne corrige cela complètement.

Le Voice Changer contourne le problème au lieu de l'affronter : c'est Matthieu
qui dit la réplique, en français, avec la bonne intonation — le modèle ne
change que le TIMBRE. L'accent ne peut pas être faux, puisqu'il vient d'un
locuteur natif.

Point d'entrée : ``fal-ai/elevenlabs/voice-changer``
  - requis   : ``audio_url``
  - options  : ``voice`` (défaut « Rachel »), ``output_format``,
               ``remove_background_noise``, ``seed``

Schéma relevé le 2026-08-19 sur l'OpenAPI de fal. Le tarif n'est pas publié
par l'API : l'interface annonce « tarif non relevé » plutôt qu'un chiffre
inventé.
"""

import os
import time

from PyQt6.QtCore import QThread, pyqtSignal

from core.config import load_config
from core.worker import humanize_api_error

# Voix cibles — même catalogue que le TTS ElevenLabs, pour ne pas présenter
# deux listes différentes du même fournisseur dans la même page.
from core.speech_engines import voices_for as _voices_for

ENDPOINT = "fal-ai/elevenlabs/voice-changer"

OUTPUT_FORMATS = [
    ("MP3 44,1 kHz · 128 kbps  (défaut)", "mp3_44100_128"),
    ("MP3 44,1 kHz · 192 kbps  (qualité)", "mp3_44100_192"),
    ("PCM 48 kHz  (montage)",              "pcm_48000"),
    ("PCM 44,1 kHz",                       "pcm_44100"),
]


def target_voices() -> list[tuple[str, str, bool]]:
    """Voix cibles disponibles → (libellé, valeur, est_francophone)."""
    return _voices_for("elevenlabs-v3")


class VoiceChangerWorker(QThread):
    """Convertit le timbre d'un enregistrement, en gardant son interprétation.

    Bascule mock ↔ réel selon la présence de la clé fal.ai, comme les autres
    workers audio de la page Doublage.
    """

    progress = pyqtSignal(int, str)
    finished = pyqtSignal(str)
    failed   = pyqtSignal(str)

    def __init__(self, audio_path: str, voice: str = "",
                 output_format: str = "mp3_44100_128",
                 remove_noise: bool = False, label: str = ""):
        super().__init__()
        self._audio_path = audio_path
        self._voice      = voice or "Charlotte"
        self._format     = output_format or "mp3_44100_128"
        self._remove     = bool(remove_noise)
        self._label      = label or "voice_changer"

    def run(self):
        key = load_config().get("api_key", "").strip()
        if not key:
            self._mock()
        else:
            self._real(key)

    def _mock(self):
        for pct, msg in [
            (20, "Voice Changer (mode mock)…"),
            (60, f"Conversion vers « {self._voice} »…"),
            (100, "Terminé — mode mock (aucune clé fal.ai)"),
        ]:
            self.progress.emit(pct, msg)
            time.sleep(0.4)
        self.finished.emit("")

    def _real(self, key: str):
        try:
            import fal_client
            import requests

            if not self._audio_path or not os.path.isfile(self._audio_path):
                raise RuntimeError(
                    "Aucun enregistrement à convertir — choisissez d'abord un "
                    "fichier audio."
                )

            os.environ["FAL_KEY"] = key

            self.progress.emit(12, "Envoi de l'enregistrement…")
            audio_url = fal_client.upload_file(self._audio_path)

            self.progress.emit(30, f"Conversion vers « {self._voice} »…")
            args = {
                "audio_url":               audio_url,
                "voice":                   self._voice,
                "output_format":           self._format,
                "remove_background_noise": self._remove,
            }
            result = fal_client.subscribe(ENDPOINT, arguments=args)

            out_url = ""
            if isinstance(result, dict):
                audio = result.get("audio")
                if isinstance(audio, dict):
                    out_url = audio.get("url", "")
                elif isinstance(audio, str):
                    out_url = audio
                if not out_url:
                    out_url = result.get("audio_url", "") or result.get("url", "")
            if not out_url:
                raise RuntimeError(f"URL audio manquante : {str(result)[:200]}")

            self.progress.emit(75, "Téléchargement du fichier converti…")
            data = requests.get(out_url, timeout=300).content

            from api.tts import _audio_output_dir
            ext  = ".wav" if self._format.startswith("pcm") else ".mp3"
            safe = "".join(c for c in self._label
                           if c.isalnum() or c in " -_").strip() or "voix"
            path = os.path.join(_audio_output_dir(),
                                f"{safe}_{int(time.time())}{ext}")
            with open(path, "wb") as f:
                f.write(data)

            self.progress.emit(100, "Timbre converti ✓")
            self.finished.emit(path)

        except Exception as e:
            self.failed.emit(humanize_api_error(f"Erreur Voice Changer : {e}"))
