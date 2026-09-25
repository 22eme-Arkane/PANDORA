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

Moteurs — interchangeables (même contrat : video_url + audio_url) :
  · Sync 2 Pro  fal-ai/sync-lipsync/v2/pro  $5/min     studio, gros plans (DÉFAUT)
  · Sync-3      fal-ai/sync-lipsync/v3      $8/min     le + récent, frame-accurate
  · VEED v2     veed/lipsync/v2             ~$4.20/min 0,07 $/s (relevé 2026-08-12)
  · PixVerse    fal-ai/pixverse/lipsync     ~$2.40/min 0,04 $/s (fiche fal 2026-09-24)
  · Sync 2      fal-ai/sync-lipsync/v2      $3/min     conversationnel
  · Kling       fal-ai/kling-video/lipsync/audio-to-video  ~$0.84/min  0,014 $/s
                                            (arrondi aux 5 s ; vidéo 2–10 s, 720p/1080p)
  · LatentSync  fal-ai/latentsync           éco        ByteDance, historique

⚠ VEED, PixVerse et Kling facturent À LA SECONDE de vidéo là où les Sync
annoncent un tarif à la minute — le $/min affiché est une conversion, pas une
grille officielle. Schémas d'entrée vérifiés identiques (video_url + audio_url,
sortie `video.url`) : ils se substituent aux autres sans adapter le worker.
⚠ Kling n'accepte qu'un clip de 2 à 10 s (100 Mo, 720p/1080p) et un audio de
2 à 60 s : au-delà, c'est fal qui refuse — le message remonte tel quel.
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
    # « tag » : ce qui distingue le moteur, affiché dans les menus (25/09/2026 —
    # Matthieu ne voyait qu'une « vieille version » : le menu ne disait ni
    # l'année ni la spécialité de chacun).
    "sync2pro":   {"endpoint": "fal-ai/sync-lipsync/v2/pro", "name": "Sync 2 Pro", "price": "$5/min",
                   "tag": "studio, gros plans"},
    "sync3":      {"endpoint": "fal-ai/sync-lipsync/v3",     "name": "Sync-3",     "price": "$8/min",
                   "tag": "2026 · le plus récent, image par image"},
    "veed2":      {"endpoint": "veed/lipsync/v2",            "name": "VEED v2",    "price": "~$4.20/min",
                   "tag": "polyvalent"},
    "sync2":      {"endpoint": "fal-ai/sync-lipsync/v2",     "name": "Sync 2",     "price": "$3/min",
                   "tag": "conversationnel"},
    # Ajoutés le 2026-09-24 (fiches fal) — même contrat video_url + audio_url.
    "pixverse":   {"endpoint": "fal-ai/pixverse/lipsync",    "name": "PixVerse Lipsync", "price": "~$2.40/min",
                   "tag": "2026"},
    "kling":      {"endpoint": "fal-ai/kling-video/lipsync/audio-to-video",
                   "name": "Kling Lipsync", "price": "~$0.84/min", "tag": "2026 · clips de 2 à 10 s"},
    "latentsync": {"endpoint": "fal-ai/latentsync",          "name": "LatentSync", "price": "$0.20 / clip",
                   "tag": "éco (2025) · jusqu'à 40 s"},
}


def engine_label(key: str) -> str:
    """« Sync-3 · $8/min — 2026 · le plus récent… » pour un menu."""
    e = LIPSYNC_ENGINES.get(key) or LIPSYNC_ENGINES[LIPSYNC_DEFAULT]
    tag = e.get("tag", "")
    return f"{e['name']} · {e['price']}" + (f" — {tag}" if tag else "")
# Ordre = du plus cher au plus économique (VEED se place entre Sync 2 Pro et
# Sync 2 : 0,07 $/s ≈ 4,20 $/min ; PixVerse 0,04 $/s ; Kling 0,014 $/s).
LIPSYNC_ENGINE_ORDER = ["sync2pro", "sync3", "veed2", "sync2", "pixverse", "kling", "latentsync"]
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


def _is_public_url(url: str) -> bool:
    u = (url or "").strip().lower()
    if not u.startswith(("http://", "https://")):
        return False
    return not any(h in u for h in ("://localhost", "://127.0.0.1", "://0.0.0.0", "://[::1]"))


def ensure_public_video_url(fal_client, video_url: str, tmp_dir: str) -> str:
    """URL de vidéo que fal peut LIRE. Un résultat ComfyUI (« Modifier un clip »
    sur la machine) est une URL /view du serveur local, et un fichier déjà
    téléchargé est un chemin : dans les deux cas le moteur de lip-sync ne
    verrait rien — on rapatrie puis on dépose chez fal (25/09/2026)."""
    url = (video_url or "").strip()
    if _is_public_url(url):
        return url
    local = url
    if url.lower().startswith(("http://", "https://")):
        import requests
        local = os.path.join(tmp_dir, "source_video.mp4")
        with requests.get(url, stream=True, timeout=600) as r:
            r.raise_for_status()
            with open(local, "wb") as f:
                for chunk in r.iter_content(1 << 20):
                    f.write(chunk)
    if not (local and os.path.isfile(local)):
        raise RuntimeError("Vidéo à synchroniser introuvable (ni URL publique, ni fichier local).")
    _cap = io.StringIO() if False else None
    return fal_client.upload_file(local)


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


def conform_audio_duration(wav_in: str, wav_out: str, dur: float) -> bool:
    """Cale un WAV à EXACTEMENT `dur` secondes : complète au silence si trop court
    (`apad`), coupe si trop long (`atrim`) → l'audio adopte la durée de la vidéo
    régénérée (son et image synchrones, durée de sortie nette)."""
    if not dur or dur <= 0:
        return False
    ok = _run_ffmpeg(
        "-i", wav_in,
        "-af", f"apad,atrim=0:{dur:g}",
        "-acodec", "pcm_s16le", "-ar", "44100", "-ac", "1",
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
                 engine: str = "", audio_path: str = "",
                 target_duration: float = 0.0):
        super().__init__()
        self._video_url          = video_url
        self._source_video_path  = source_video_path
        self._output_dir         = output_dir
        self._shot_name          = shot_name or "lipsync"
        self._engine             = engine or get_lipsync_engine()
        self._audio_path         = audio_path
        # Si > 0 : on cale l'audio à cette durée (= durée de la vidéo régénérée)
        # avant le lip-sync → son et image synchrones, durée de sortie nette.
        self._target_duration    = float(target_duration or 0.0)

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

        # ── 1b. Alignement durée : cale l'audio sur la durée de la vidéo régénérée
        #        (son et image synchrones, durée de sortie nette). No-op si non demandé.
        if self._target_duration and self._target_duration > 0:
            wav_conf = os.path.join(tmp_dir, "audio_conformed.wav")
            if conform_audio_duration(wav_src, wav_conf, self._target_duration):
                wav_src = wav_conf

        # ── 2. Upload audio vers fal.ai (robuste non-ASCII + fallback data-URL) ─
        self.progress.emit(20, "Upload audio vers fal.ai…")
        audio_url = _upload_audio_robust(fal_client, wav_src)
        # La vidéo aussi doit être lisible par fal (résultat ComfyUI local,
        # fichier déjà téléchargé) — sinon rien n'est déposé, elle est reprise.
        video_url = ensure_public_video_url(fal_client, self._video_url, tmp_dir)

        # ── 3. Appel du moteur lip-sync choisi ─────────────────────────────────
        _eng = LIPSYNC_ENGINES.get(self._engine) or LIPSYNC_ENGINES[LIPSYNC_DEFAULT]
        self.progress.emit(35, f"Synchronisation labiale ({_eng['name']})…")
        result = fal_client.subscribe(
            lipsync_endpoint(self._engine),
            arguments={
                "video_url": video_url,
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
