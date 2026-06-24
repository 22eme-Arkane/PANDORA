"""Worker de synchronisation labiale (lip-sync) post-Seedance — multi-moteurs fal.ai.

Pipeline :
  1. Source audio : soit un audio CIBLE déjà prêt (TTS/doublage, fichier fourni),
     soit extraction de la piste d'un clip source DaVinci (ffmpeg) → .wav.
  2. Upload audio vers fal.ai → audio_url (robuste : non-ASCII + fallback data-URL).
  3. Appel du moteur lip-sync choisi (Sync 2 Pro par défaut · Sync-3 · Sync 2 ·
     LatentSync) — tous prennent la MÊME interface video_url + audio_url.
  4. Téléchargement du résultat lip-synced.
  5. Démultiplexage ffmpeg → vidéo muette + piste audio .wav.
  6. emit finished(video_path, audio_path)

Prérequis : ffmpeg disponible dans le PATH.

Moteurs (relevé fal.ai 2026-06-24) — interchangeables (video_url + audio_url) :
  · Sync 2 Pro  fal-ai/sync-lipsync/v2/pro  $5/min  studio, gros plans, émotion (DÉFAUT)
  · Sync-3      fal-ai/sync-lipsync/v3      $8/min  le + récent, frame-accurate
  · Sync 2      fal-ai/sync-lipsync/v2      $3/min  conversationnel
  · LatentSync  fal-ai/latentsync           éco     ByteDance, historique
"""

import os
import subprocess
import sys
import tempfile
from datetime import datetime

from PyQt6.QtCore import QThread, pyqtSignal
from core.video_utils import get_ffmpeg_exe

_NO_WINDOW = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0


# ── Catalogue des moteurs de synchronisation labiale ──────────────────────────
LIPSYNC_ENGINES: dict[str, dict] = {
    "sync2pro":   {"endpoint": "fal-ai/sync-lipsync/v2/pro", "name": "Sync 2 Pro", "price": "$5/min"},
    "sync3":      {"endpoint": "fal-ai/sync-lipsync/v3",     "name": "Sync-3",     "price": "$8/min"},
    "sync2":      {"endpoint": "fal-ai/sync-lipsync/v2",     "name": "Sync 2",     "price": "$3/min"},
    "latentsync": {"endpoint": "fal-ai/latentsync",          "name": "LatentSync", "price": "éco"},
}
LIPSYNC_ENGINE_ORDER = ["sync2pro", "sync3", "sync2", "latentsync"]
LIPSYNC_DEFAULT = "sync2pro"


def lipsync_endpoint(engine: str) -> str:
    """Endpoint fal.ai du moteur lip-sync (repli sur le défaut si inconnu)."""
    e = LIPSYNC_ENGINES.get(engine) or LIPSYNC_ENGINES[LIPSYNC_DEFAULT]
    return e["endpoint"]


def get_lipsync_engine() -> str:
    """Moteur lip-sync choisi (config.json → lipsync_engine) — défaut Sync 2 Pro."""
    try:
        from core.config import load_config
        e = (load_config().get("lipsync_engine") or "").strip()
        return e if e in LIPSYNC_ENGINES else LIPSYNC_DEFAULT
    except Exception:
        return LIPSYNC_DEFAULT


def ffmpeg_available() -> bool:
    exe = get_ffmpeg_exe()
    if exe != "ffmpeg":
        return os.path.isfile(exe)
    import shutil
    return shutil.which("ffmpeg") is not None


def _upload_audio_robust(fal_client, path: str) -> str:
    """Upload audio vers fal.ai sans casser sur les chemins NON-ASCII (projets
    accentués) ni sur un stockage refusé : upload en bytes, fallback data-URL.
    Même logique éprouvée que api/apercu._upload_ref_robust (incident moods)."""
    import io, base64, mimetypes
    ct = mimetypes.guess_type(path)[0] or "audio/wav"
    with open(path, "rb") as _f:
        data = _f.read()
    _cap = io.StringIO()
    _old_out, _old_err = sys.stdout, sys.stderr
    sys.stdout = sys.stderr = _cap
    try:
        try:
            return fal_client.upload(data, content_type=ct)
        except Exception:
            return f"data:{ct};base64,{base64.b64encode(data).decode()}"
    finally:
        sys.stdout, sys.stderr = _old_out, _old_err


def _run_ffmpeg(*args, timeout: int = 120) -> bool:
    try:
        r = subprocess.run(
            [get_ffmpeg_exe(), "-y", *args],
            capture_output=True, timeout=timeout,
            creationflags=_NO_WINDOW,
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


class LipSyncWorker(QThread):
    """
    Worker asynchrone pour le pipeline de synchronisation labiale complet.

    Paramètres :
        video_url         — URL fal.ai de la vidéo générée par Seedance
        source_video_path — Clip source dont EXTRAIRE l'audio (mode « Modifier depuis
                            DaVinci ») — ignoré si audio_path est fourni
        output_dir        — Dossier de destination des fichiers finaux
        shot_name         — Nom du plan (pour nommer les fichiers)
        engine            — Moteur lip-sync (clé LIPSYNC_ENGINES) ; "" → config/défaut
        audio_path        — Audio CIBLE déjà prêt (TTS/doublage/fichier) ; prioritaire
                            sur l'extraction depuis source_video_path

    Signaux :
        finished(video_path, audio_path) — vidéo muette + audio .wav (audio_path peut être "")
        failed(message)
        progress(pct, message)
    """

    finished = pyqtSignal(str, str)
    failed   = pyqtSignal(str)
    progress = pyqtSignal(int, str)

    def __init__(self, video_url: str, source_video_path: str = "",
                 output_dir: str = "", shot_name: str = "",
                 engine: str = "", audio_path: str = ""):
        super().__init__()
        self._video_url          = video_url
        self._source_video_path  = source_video_path
        self._output_dir         = output_dir
        self._shot_name          = shot_name or "lipsync"
        self._engine             = engine or get_lipsync_engine()
        self._audio_path         = audio_path

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

        # ── 1. Audio cible : fichier prêt (TTS/doublage) OU extraction du source ─
        if self._audio_path and os.path.isfile(self._audio_path):
            self.progress.emit(5, "Audio cible fourni…")
            wav_src = self._audio_path
        else:
            self.progress.emit(5, "Extraction audio source…")
            wav_src = os.path.join(tmp_dir, "source_audio.wav")
            if not extract_audio_wav(self._source_video_path, wav_src):
                self.failed.emit(
                    "Aucun audio à synchroniser : fournis une voix (doublage/TTS ou "
                    "fichier), ou un clip source avec piste audio (+ ffmpeg installé)."
                )
                return

        # ── 2. Upload audio vers fal.ai (robuste non-ASCII + fallback data-URL) ─
        self.progress.emit(20, "Upload audio vers fal.ai…")
        audio_url = _upload_audio_robust(fal_client, wav_src)

        # ── 3. Appel du moteur lip-sync choisi ─────────────────────────────────
        _eng = LIPSYNC_ENGINES.get(self._engine) or LIPSYNC_ENGINES[LIPSYNC_DEFAULT]
        self.progress.emit(35, f"Synchronisation labiale ({_eng['name']})…")
        result = fal_client.subscribe(
            lipsync_endpoint(self._engine),
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
            self.failed.emit(f"Lip-sync ({_eng['name']}) : URL de sortie manquante — {result}")
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


# Rétro-compat : l'ancien nom reste valide (« Modifier depuis DaVinci »).
LatentSyncWorker = LipSyncWorker
