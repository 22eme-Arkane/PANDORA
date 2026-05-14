"""
api/video_engines.py — Moteurs vidéo alternatifs à Seedance 2.0.

Modèles fal.ai :
  - Kling v3 Pro I2V  : fal-ai/kling-video/v3/pro/image-to-video  — $0.112-0.196/s
  - Kling v3 Pro T2V  : fal-ai/kling-video/v3/pro/text-to-video   — $0.112-0.196/s
  - PixVerse v4.5 I2V : fal-ai/pixverse/v4.5/image-to-video       — $0.04-0.08/s

Tous héritent d'une interface commune : progress(int,str) + finished(dict) + failed(str).
"""

import os
import time

from PyQt6.QtCore import QThread, pyqtSignal
from core.config import load_config
from core.pandora_dirs import get_bin_dir


def _video_output_dir(cfg: dict | None = None) -> str:
    """Dossier de sortie des clips vidéo (même logique que Seedance)."""
    from core.config import get_output_dir
    return get_output_dir(cfg)


# ── Worker Kling v3 Pro ───────────────────────────────────────────────────────

class KlingWorker(QThread):
    """
    Génère une vidéo via Kling Video v3 Pro.

    Modes :
      mode="i2v"  → image-to-video  (start_image_url requis)
      mode="t2v"  → text-to-video   (prompt seul)
    """
    progress = pyqtSignal(int, str)
    finished = pyqtSignal(dict)
    failed   = pyqtSignal(str)

    # Tarifs indicatifs (source : fal.ai, mai 2025)
    _PRICE_NO_AUDIO   = 0.112   # $/s
    _PRICE_WITH_AUDIO = 0.168   # $/s

    def __init__(self, params: dict):
        """
        params attendus :
          prompt          (str)  requis
          image_url       (str)  requis si mode='i2v'
          end_image_url   (str)  optionnel
          duration        (int)  3-15, défaut 5
          generate_audio  (bool) défaut True
          negative_prompt (str)  optionnel
          cfg_scale       (float) 0-1, défaut 0.5
          shot_type       (str)  "customize" | "intelligent"
          mode            (str)  "i2v" | "t2v", défaut "i2v"
        """
        super().__init__()
        self.params = params

    def run(self):
        cfg = load_config()
        key = cfg.get("api_key", "").strip()
        if not key:
            self._mock()
        else:
            self._real(key)

    def _mock(self):
        mode = self.params.get("mode", "i2v").upper()
        dur  = self.params.get("duration", 5)
        steps = [
            (10, f"Kling v3 Pro {mode} — mode mock…"),
            (40, "Génération vidéo Kling (simulation)…"),
            (80, f"Vidéo {dur}s en cours…"),
            (100, "Terminé — mode mock (aucune clé fal.ai)"),
        ]
        for pct, msg in steps:
            self.progress.emit(pct, msg)
            time.sleep(0.5)
        self.finished.emit({"url": "", "duration": dur, "model": "kling-v3-pro", "credits_used": 0})

    def _real(self, key: str):
        try:
            import fal_client
            import requests
            from core.lang import translate_to_english

            os.environ["FAL_KEY"] = key

            mode      = self.params.get("mode", "i2v")
            dur       = int(self.params.get("duration", 5))
            with_audio = self.params.get("generate_audio", True)
            endpoint  = (
                "fal-ai/kling-video/v3/pro/image-to-video" if mode == "i2v"
                else "fal-ai/kling-video/v3/pro/text-to-video"
            )

            price_rate = self._PRICE_WITH_AUDIO if with_audio else self._PRICE_NO_AUDIO
            cost_est   = dur * price_rate

            self.progress.emit(10, f"Kling v3 Pro {mode.upper()} — {dur}s (~${cost_est:.2f})…")

            prompt_raw = self.params.get("prompt", "")
            prompt_en  = translate_to_english(prompt_raw) if prompt_raw else ""

            args: dict = {
                "prompt":          prompt_en,
                "duration":        str(dur),
                "generate_audio":  with_audio,
                "shot_type":       self.params.get("shot_type", "customize"),
            }
            if mode == "i2v":
                img_url = self.params.get("image_url", "")
                if not img_url:
                    raise ValueError("Kling I2V : image_url requis.")
                args["start_image_url"] = img_url
                if self.params.get("end_image_url"):
                    args["end_image_url"] = self.params["end_image_url"]
            if self.params.get("negative_prompt"):
                args["negative_prompt"] = self.params["negative_prompt"]
            if self.params.get("cfg_scale") is not None:
                args["cfg_scale"] = float(self.params["cfg_scale"])

            self.progress.emit(20, "Appel Kling v3 Pro (peut prendre 1-2 min)…")

            result = fal_client.subscribe(endpoint, arguments=args)

            if not isinstance(result, dict):
                raise RuntimeError(f"Réponse inattendue : {str(result)[:200]}")

            video = result.get("video") or {}
            url   = video.get("url", "") if isinstance(video, dict) else ""
            if not url:
                raise RuntimeError(f"URL vidéo manquante : {str(result)[:200]}")

            self.progress.emit(80, "Téléchargement de la vidéo…")
            data = requests.get(url, timeout=300).content

            out_dir  = _video_output_dir()
            ts       = int(time.time())
            filename = f"kling_v3_{mode}_{dur}s_{ts}.mp4"
            local    = os.path.join(out_dir, filename)
            with open(local, "wb") as f:
                f.write(data)

            self.progress.emit(100, f"Kling v3 Pro ✓  {dur}s · ~${cost_est:.2f}")
            self.finished.emit({
                "url":          url,
                "local_path":   local,
                "duration":     dur,
                "resolution":   "1080p",
                "model":        f"kling-v3-pro-{mode}",
                "credits_used": cost_est,
            })

        except Exception as e:
            self.failed.emit(f"Erreur Kling : {e}")


# ── Worker PixVerse v4.5 ──────────────────────────────────────────────────────

class PixVerseWorker(QThread):
    """
    Génère une vidéo via PixVerse v4.5 Image-to-Video.

    Le modèle PixVerse est moins cher que Kling/Seedance mais sans audio natif.
    Idéal pour des itérations rapides et économiques.
    """
    progress = pyqtSignal(int, str)
    finished = pyqtSignal(dict)
    failed   = pyqtSignal(str)

    # Tarifs indicatifs
    _PRICE_720P  = 0.04   # $/s (5s = $0.20)
    _PRICE_1080P = 0.08   # $/s (5s = $0.40)

    def __init__(self, params: dict):
        """
        params attendus :
          prompt      (str)  requis
          image_url   (str)  requis
          duration    (int)  5 (seule option actuellement)
          resolution  (str)  "720p" | "1080p", défaut "720p"
        """
        super().__init__()
        self.params = params

    def run(self):
        cfg = load_config()
        key = cfg.get("api_key", "").strip()
        if not key:
            self._mock()
        else:
            self._real(key)

    def _mock(self):
        dur = self.params.get("duration", 5)
        steps = [
            (15, "PixVerse v4.5 — mode mock…"),
            (50, "Génération vidéo PixVerse (simulation)…"),
            (90, f"Vidéo {dur}s en cours…"),
            (100, "Terminé — mode mock (aucune clé fal.ai)"),
        ]
        for pct, msg in steps:
            self.progress.emit(pct, msg)
            time.sleep(0.5)
        self.finished.emit({"url": "", "duration": dur, "model": "pixverse-v4.5", "credits_used": 0})

    def _real(self, key: str):
        try:
            import fal_client
            import requests
            from core.lang import translate_to_english

            os.environ["FAL_KEY"] = key

            dur  = int(self.params.get("duration", 5))
            res  = self.params.get("resolution", "720p")
            rate = self._PRICE_1080P if res == "1080p" else self._PRICE_720P
            cost = dur * rate

            self.progress.emit(10, f"PixVerse v4.5 I2V — {dur}s {res} (~${cost:.2f})…")

            img_url = self.params.get("image_url", "")
            if not img_url:
                raise ValueError("PixVerse : image_url requis.")

            prompt_raw = self.params.get("prompt", "")
            prompt_en  = translate_to_english(prompt_raw) if prompt_raw else ""

            self.progress.emit(20, "Appel PixVerse v4.5 (environ 1 min)…")

            result = fal_client.subscribe(
                "fal-ai/pixverse/v4.5/image-to-video",
                arguments={
                    "prompt":    prompt_en,
                    "image_url": img_url,
                },
            )

            if not isinstance(result, dict):
                raise RuntimeError(f"Réponse inattendue : {str(result)[:200]}")

            video = result.get("video") or {}
            url   = video.get("url", "") if isinstance(video, dict) else ""
            if not url:
                url = result.get("url", "")
            if not url:
                raise RuntimeError(f"URL vidéo manquante : {str(result)[:200]}")

            self.progress.emit(80, "Téléchargement…")
            data = requests.get(url, timeout=300).content

            out_dir  = _video_output_dir()
            ts       = int(time.time())
            local    = os.path.join(out_dir, f"pixverse_{dur}s_{ts}.mp4")
            with open(local, "wb") as f:
                f.write(data)

            self.progress.emit(100, f"PixVerse ✓  {dur}s {res} · ~${cost:.2f}")
            self.finished.emit({
                "url":          url,
                "local_path":   local,
                "duration":     dur,
                "resolution":   res,
                "model":        "pixverse-v4.5-i2v",
                "credits_used": cost,
            })

        except Exception as e:
            self.failed.emit(f"Erreur PixVerse : {e}")
