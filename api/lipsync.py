"""Worker LatentSync — resynchronisation labiale post-Seedance.

Pipeline :
  1. Extraction audio de la source DaVinci (ffmpeg) → .wav temporaire
  2. Upload audio .wav vers fal.ai → audio_url
  3. Appel fal-ai/latentsync (video_url Seedance + audio_url)
  4. Téléchargement du résultat lip-synced
  5. Démultiplexage ffmpeg → vidéo muette + piste audio .wav
  6. emit finished(video_path, audio_path)

Prérequis : ffmpeg disponible dans le PATH.
"""

import os
import subprocess
import tempfile
from datetime import datetime

from PyQt6.QtCore import QThread, pyqtSignal


def ffmpeg_available() -> bool:
    try:
        r = subprocess.run(
            ["ffmpeg", "-version"],
            capture_output=True, timeout=5,
        )
        return r.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        return False


def _run_ffmpeg(*args, timeout: int = 120) -> bool:
    try:
        r = subprocess.run(
            ["ffmpeg", "-y", *args],
            capture_output=True, timeout=timeout,
        )
        return r.returncode == 0
    except Exception:
        return False


def extract_audio_wav(video_path: str, wav_out: str) -> bool:
    """Extrait la piste audio d'une vidéo source en WAV 44 100 Hz mono."""
    ok = _run_ffmpeg(
        "-i", video_path,
        "-vn", "-acodec", "pcm_s16le", "-ar", "44100", "-ac", "1",
        wav_out,
    )
    return ok and os.path.isfile(wav_out) and os.path.getsize(wav_out) > 0


def demux_video_audio(input_path: str, video_out: str, audio_out: str) -> bool:
    """Sépare vidéo muette + piste audio WAV depuis un MP4 lip-synced."""
    ok_v = _run_ffmpeg(
        "-i", input_path,
        "-an", "-c:v", "copy",
        video_out,
    )
    ok_a = _run_ffmpeg(
        "-i", input_path,
        "-vn", "-acodec", "pcm_s16le", "-ar", "44100", "-ac", "1",
        audio_out,
    )
    return ok_v and ok_a


class LatentSyncWorker(QThread):
    """
    Worker asynchrone pour le pipeline LatentSync complet.

    Paramètres :
        video_url         — URL fal.ai de la vidéo générée par Seedance
        source_video_path — Chemin local du clip DaVinci source (pour extraire l'audio)
        output_dir        — Dossier de destination des fichiers finaux
        shot_name         — Nom du plan (pour nommer les fichiers)

    Signaux :
        finished(video_path, audio_path) — vidéo muette + audio .wav (audio_path peut être "")
        failed(message)
        progress(pct, message)
    """

    finished = pyqtSignal(str, str)
    failed   = pyqtSignal(str)
    progress = pyqtSignal(int, str)

    def __init__(self, video_url: str, source_video_path: str,
                 output_dir: str, shot_name: str = ""):
        super().__init__()
        self._video_url          = video_url
        self._source_video_path  = source_video_path
        self._output_dir         = output_dir
        self._shot_name          = shot_name or "lipsync"

    def run(self):
        tmp_dir = tempfile.mkdtemp(prefix="pandora_lipsync_")
        try:
            self._run(tmp_dir)
        except Exception as e:
            self.failed.emit(str(e))
        finally:
            # Nettoyage des temporaires
            import shutil
            try:
                shutil.rmtree(tmp_dir, ignore_errors=True)
            except Exception:
                pass

    def _run(self, tmp_dir: str):
        from core.config import load_config
        cfg = load_config()
        api_key = cfg.get("api_key", "").strip()
        if not api_key:
            self.failed.emit("Clé fal.ai non configurée (page Paramètres).")
            return

        os.environ.setdefault("FAL_KEY", api_key)
        import fal_client
        fal_client.api_key = api_key

        # ── 1. Extraction audio source ────────────────────────────────────────
        self.progress.emit(5, "Extraction audio source…")
        wav_src = os.path.join(tmp_dir, "source_audio.wav")
        if not extract_audio_wav(self._source_video_path, wav_src):
            self.failed.emit(
                "Impossible d'extraire l'audio du clip source.\n"
                "Vérifiez que ffmpeg est installé et que le clip contient une piste audio."
            )
            return

        # ── 2. Upload audio vers fal.ai ────────────────────────────────────────
        self.progress.emit(20, "Upload audio vers fal.ai…")
        import sys, io
        _cap = io.StringIO()
        _old_out, _old_err = sys.stdout, sys.stderr
        sys.stdout = sys.stderr = _cap
        try:
            audio_url = fal_client.upload_file(wav_src)
        finally:
            sys.stdout = _old_out
            sys.stderr = _old_err

        # ── 3. Appel LatentSync ───────────────────────────────────────────────
        self.progress.emit(35, "Synchronisation LatentSync…")
        result = fal_client.subscribe(
            "fal-ai/latentsync",
            arguments={
                "video_url": self._video_url,
                "audio_url": audio_url,
            },
            with_logs=False,
        )
        lipsync_url = ""
        if isinstance(result, dict):
            lipsync_url = (
                result.get("video", {}).get("url", "")
                or result.get("video_url", "")
            )
        if not lipsync_url:
            self.failed.emit(f"LatentSync : URL de sortie manquante — {result}")
            return

        # ── 4. Téléchargement résultat ────────────────────────────────────────
        self.progress.emit(70, "Téléchargement vidéo lip-synced…")
        from davinci.importer import download_video
        os.makedirs(self._output_dir, exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        lipsync_path = download_video(
            lipsync_url,
            self._output_dir,
            f"{self._shot_name}_ls_{ts}.mp4",
        )

        # ── 5. Démultiplexage vidéo + audio ───────────────────────────────────
        self.progress.emit(88, "Démultiplexage audio/vidéo…")
        video_out = lipsync_path.replace(".mp4", "_vid.mp4")
        audio_out = lipsync_path.replace(".mp4", "_aud.wav")
        ok = demux_video_audio(lipsync_path, video_out, audio_out)

        self.progress.emit(100, "Terminé.")
        if ok and os.path.isfile(video_out) and os.path.isfile(audio_out):
            # Supprime le fichier combiné (on garde seulement les fichiers séparés)
            try:
                os.remove(lipsync_path)
            except OSError:
                pass
            self.finished.emit(video_out, audio_out)
        else:
            # Fallback : on renvoie le fichier combiné (pas de piste audio séparée)
            self.finished.emit(lipsync_path, "")
