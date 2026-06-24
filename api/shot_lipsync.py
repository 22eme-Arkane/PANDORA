"""api/shot_lipsync.py — synchronisation labiale d'UN plan généré (storyboard).

Un SEUL QThread enchaîne les deux appels fal.ai séquentiellement (pas de workers
imbriqués → pas de risque de segfault) :

  1. Audio cible :
       a. override manuel (fichier attaché au plan : `lipsync_audio_path`), sinon
       b. TTS automatique depuis le dialogue du plan (ElevenLabs FR, fal.ai).
  2. Lip-sync : moteur choisi (Sync 2 Pro par défaut · Sync-3 · Sync 2 · LatentSync)
     via api.lipsync — interface video_url + audio_url commune.
  3. Démux ffmpeg → vidéo + audio séparés ; emit done(shot_id, video_path, audio_path).

Signaux : `done` (jamais `finished` — convention worker du projet), `failed`,
`progress`. Le signal natif QThread.finished reste libre pour le nettoyage.
"""

import os
import tempfile
from datetime import datetime

from PyQt6.QtCore import QThread, pyqtSignal


class ShotLipSyncWorker(QThread):
    done     = pyqtSignal(str, str, str)   # (shot_id, video_path, audio_path)
    failed   = pyqtSignal(str, str)        # (shot_id, message)
    progress = pyqtSignal(int, str)        # (pct, message)

    def __init__(self, shot: dict, video_url: str, output_dir: str,
                 engine: str = "", audio_path: str = "", voice: str = "Charlotte"):
        super().__init__()
        self._shot       = shot or {}
        self._shot_id    = (shot or {}).get("id", "")
        self._video_url  = video_url
        self._output_dir = output_dir
        self._engine     = engine
        self._audio_path = audio_path or (shot or {}).get("lipsync_audio_path", "")
        self._voice      = voice

    # ── Pipeline ───────────────────────────────────────────────────────────────
    def run(self):
        tmp_dir = tempfile.mkdtemp(prefix="pandora_shotls_")
        try:
            self._run(tmp_dir)
        except Exception as e:
            self.failed.emit(self._shot_id, str(e))
        finally:
            import shutil
            shutil.rmtree(tmp_dir, ignore_errors=True)

    def _run(self, tmp_dir: str):
        from core.config import load_config
        api_key = load_config().get("api_key", "").strip()
        if not api_key:
            self.failed.emit(self._shot_id, "Clé fal.ai manquante — lip-sync impossible.")
            return
        os.environ["FAL_KEY"] = api_key
        import fal_client
        fal_client.api_key = api_key

        from api.lipsync import (
            lipsync_endpoint, LIPSYNC_ENGINES, LIPSYNC_DEFAULT,
            get_lipsync_engine, _upload_audio_robust, demux_video_audio,
        )
        engine = self._engine or get_lipsync_engine()
        eng = LIPSYNC_ENGINES.get(engine) or LIPSYNC_ENGINES[LIPSYNC_DEFAULT]

        # ── 1. Audio cible ─────────────────────────────────────────────────────
        if self._audio_path and os.path.isfile(self._audio_path):
            self.progress.emit(8, "Audio (fichier attaché)…")
            audio_file = self._audio_path
        else:
            self.progress.emit(8, "Voix automatique (TTS) depuis le dialogue…")
            audio_file = self._synth_tts(fal_client, tmp_dir)
            if not audio_file:
                self.failed.emit(
                    self._shot_id,
                    "Aucun dialogue ni audio pour ce plan — rien à synchroniser. "
                    "Ajoute un dialogue (entre guillemets) ou attache un audio.")
                return

        # ── 2. Upload audio + lip-sync ─────────────────────────────────────────
        self.progress.emit(30, "Upload audio…")
        audio_url = _upload_audio_robust(fal_client, audio_file)

        self.progress.emit(45, f"Synchronisation labiale ({eng['name']})…")
        result = fal_client.subscribe(
            lipsync_endpoint(engine),
            arguments={"video_url": self._video_url, "audio_url": audio_url},
            with_logs=False,
        )
        out_url = ""
        if isinstance(result, dict):
            out_url = (result.get("video", {}) or {}).get("url", "") or result.get("video_url", "")
        if not out_url:
            self.failed.emit(self._shot_id,
                             f"Lip-sync ({eng['name']}) : pas de sortie — {str(result)[:160]}")
            return

        # ── 3. Téléchargement + démux ──────────────────────────────────────────
        self.progress.emit(75, "Téléchargement du clip synchronisé…")
        from davinci.importer import download_video
        os.makedirs(self._output_dir, exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        name = (self._shot.get("scene_title") or self._shot_id or "plan")
        safe = "".join(c for c in str(name) if c.isalnum() or c in " -_").strip() or "plan"
        ls_path = download_video(out_url, self._output_dir, f"{safe}_ls_{ts}.mp4")

        self.progress.emit(90, "Démultiplexage audio/vidéo…")
        video_out = ls_path.replace(".mp4", "_vid.mp4")
        audio_out = ls_path.replace(".mp4", "_aud.wav")
        if demux_video_audio(ls_path, video_out, audio_out) \
                and os.path.isfile(video_out) and os.path.isfile(audio_out):
            try:
                os.remove(ls_path)
            except OSError:
                pass
            self.progress.emit(100, "Lèvres synchronisées ✓")
            self.done.emit(self._shot_id, video_out, audio_out)
        else:
            self.progress.emit(100, "Lèvres synchronisées ✓")
            self.done.emit(self._shot_id, ls_path, "")

    # ── TTS automatique depuis le dialogue du plan ──────────────────────────────
    def _synth_tts(self, fal_client, tmp_dir: str) -> str:
        """Synthétise la voix du dialogue du plan (ElevenLabs FR). "" si pas de
        dialogue ou échec — le lip-sync n'a alors rien à caler."""
        from core.dialogue import extract_shot_dialogue
        text = extract_shot_dialogue(self._shot)
        if not text:
            return ""
        lang = (self._shot.get("dialogue_lang") or "fr").strip() or "fr"
        try:
            import requests
            result = fal_client.subscribe(
                "fal-ai/elevenlabs/tts/turbo-v2.5",
                arguments={"text": text, "voice": self._voice, "language_code": lang},
            )
            audio_url = ""
            if isinstance(result, dict):
                audio = result.get("audio", {})
                audio_url = audio.get("url", "") if isinstance(audio, dict) else ""
                if not audio_url:
                    audio_url = result.get("url", "")
            if not audio_url:
                return ""
            data = requests.get(audio_url, timeout=120).content
            out = os.path.join(tmp_dir, "dub.mp3")
            with open(out, "wb") as f:
                f.write(data)
            return out if os.path.getsize(out) > 0 else ""
        except Exception:
            return ""
