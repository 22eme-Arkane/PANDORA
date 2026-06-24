"""Face / background swap vidéo via Pixverse Swap (fal-ai/pixverse/swap).

CHIRURGICAL : garde le métrage d'origine et ne change QUE le visage (`mode="person"`)
ou le fond (`mode="background"`) — bien plus fidèle que de régénérer tout le plan via
Seedance (qui dérive et perd en qualité). Conserve l'audio d'origine.

⚠ Plafonné à 720p par l'API Pixverse (pas de 1080p).

Le worker émet `finished(dict)` au MÊME format qu'une génération Seedance
(`{"video_url": ...}`) → il se branche directement sur le flux `_on_clip_done` /
`import_result` de « Modifier un clip » (téléchargement + import DaVinci + lip-sync
optionnel inchangés). En mode mock (pas de clé fal.ai), `video_url=""` → `import_result`
le détecte comme mock.
"""
import os
import time

from PyQt6.QtCore import QThread, pyqtSignal

from core.config import load_config
from core.worker import humanize_api_error

_PX_RESOLUTIONS = ("360p", "540p", "720p")   # 1080p NON supporté par Pixverse Swap


class PixverseSwapWorker(QThread):
    """Remplace le visage (ou le fond) d'une vidéo par une image de référence.

    video_path  : clip source (le métrage à conserver).
    image_path  : image cible (nouveau visage en mode 'person', nouveau fond en 'background').
    mode        : 'person' | 'object' | 'background'.
    resolution  : '360p' | '540p' | '720p' (clampé).
    keep_audio  : conserve la piste audio d'origine (original_sound_switch).
    """
    progress = pyqtSignal(int, str)
    finished = pyqtSignal(dict)   # {"video_url": str, "prompt": str, "mode": "t2v"}
    failed   = pyqtSignal(str)

    def __init__(self, video_path: str, image_path: str, mode: str = "person",
                 resolution: str = "720p", keep_audio: bool = True, prompt: str = ""):
        super().__init__()
        self._video      = video_path
        self._image      = image_path
        self._mode       = mode if mode in ("person", "object", "background") else "person"
        self._res        = resolution if resolution in _PX_RESOLUTIONS else "720p"
        self._keep_audio = bool(keep_audio)
        self._prompt     = prompt or ""

    def run(self):
        cfg = load_config()
        key = cfg.get("api_key", "").strip()
        if not key:
            for pct, msg in [(20, "Pixverse Swap (mode mock)…"),
                             (100, "Terminé — mode mock (aucune clé fal.ai)")]:
                self.progress.emit(pct, msg)
                time.sleep(0.3)
            self.finished.emit({"video_url": "", "mock": True,
                                "prompt": self._prompt, "mode": "t2v"})
            return
        try:
            import fal_client
            os.environ["FAL_KEY"] = key
            if not (self._video and os.path.isfile(self._video)):
                raise RuntimeError("Clip source introuvable.")
            if not (self._image and os.path.isfile(self._image)):
                raise RuntimeError("Image de référence manquante.")

            self.progress.emit(8, "Envoi du clip à fal.ai…")
            v_url = fal_client.upload_file(self._video)
            self.progress.emit(18, "Envoi de l'image de référence…")
            i_url = fal_client.upload_file(self._image)

            self.progress.emit(28, f"Pixverse Swap ({self._mode}, {self._res})…")
            args = {
                "video_url":             v_url,
                "image_url":             i_url,
                "mode":                  self._mode,
                "resolution":            self._res,
                "original_sound_switch": self._keep_audio,
            }
            result = fal_client.subscribe("fal-ai/pixverse/swap", arguments=args)

            out_url = ""
            if isinstance(result, dict):
                v = result.get("video")
                if isinstance(v, dict):
                    out_url = v.get("url", "")
                elif isinstance(v, list) and v:
                    first = v[0]
                    out_url = (first.get("url", "") if isinstance(first, dict)
                               else first if isinstance(first, str) else "")
                elif isinstance(v, str):
                    out_url = v
                if not out_url:
                    out_url = result.get("video_url", "") or result.get("url", "")
            if not out_url:
                raise RuntimeError(f"URL vidéo manquante : {str(result)[:200]}")

            self.progress.emit(100, "Swap terminé ✓")
            self.finished.emit({"video_url": out_url, "prompt": self._prompt, "mode": "t2v"})
        except Exception as e:
            self.failed.emit(humanize_api_error(f"Erreur Pixverse Swap : {e}"))
