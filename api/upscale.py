"""
api/upscale.py — Workers d'upscaling vidéo via fal.ai.

Modèles :
  - Topaz Video Upscale : fal-ai/topaz/upscale/video
        video_url (req), upscale_factor (1-4, déf. 2), model (déf. "Proteus"), options…
  - SeedVR2 Video       : fal-ai/seedvr/upscale/video   (~$0.001/MP)
        video_url (req)

Bascule mock ↔ réel selon la clé fal.ai (api_key). Upload du fichier local → URL fal,
puis téléchargement du résultat. Conçu pour être RÉUTILISÉ par Cinéma à terme.
"""

import os
import time

from PyQt6.QtCore import QThread, pyqtSignal

from core.config import load_config
from core.worker import humanize_api_error


# (label UI, clé interne)
UPSCALE_MODELS = [
    ("Topaz Video  (qualité maximale)",   "topaz"),
    ("SeedVR2  (rapide, ~$0.001/MP)",     "seedvr"),
]

# Modèles d'amélioration Topaz — (libellé affiché, valeur EXACTE de l'enum API).
# ⚠ Vu en réel (2026-06-11) : « Gaia »/« Artemis »/« Starlight » nus n'existent
# pas dans l'enum fal.ai → erreur immédiate. Valeurs valides (doc API) :
# Proteus, Artemis HQ/MQ/LQ, Nyx, Nyx Fast/XL/HF, Gaia HQ/CG/2, Starlight *.
TOPAZ_MODELS = [
    ("Proteus  (polyvalent — recommandé)",      "Proteus"),
    ("Artemis HQ  (footage propre)",            "Artemis HQ"),
    ("Artemis MQ  (footage moyen)",             "Artemis MQ"),
    ("Gaia HQ  (rendu naturel)",                "Gaia HQ"),
    ("Gaia CG  (rendu 3D / CG)",                "Gaia CG"),
    ("Nyx  (réduction de bruit)",               "Nyx"),
    ("Starlight Mini  (qualité max, lent)",     "Starlight Mini"),
]

_ENDPOINTS = {
    "topaz":  "fal-ai/topaz/upscale/video",
    "seedvr": "fal-ai/seedvr/upscale/video",
}


def _upscale_output_dir() -> str:
    """Dossier de sortie des vidéos upscalées."""
    try:
        from core.context import get_data_root
        d = os.path.join(get_data_root(), "upscaled")
    except Exception:
        from core.pandora_dirs import get_bin_dir
        d = get_bin_dir("upscaled")
    os.makedirs(d, exist_ok=True)
    return d


class UpscaleVideoWorker(QThread):
    """Upscale un clip vidéo via fal.ai (Topaz ou SeedVR2). Sortie = MP4 local."""
    progress = pyqtSignal(int, str)
    finished = pyqtSignal(str)      # chemin local du fichier upscalé
    failed   = pyqtSignal(str)

    def __init__(self, video_path: str, model: str = "topaz", upscale_factor: int = 2,
                 topaz_model: str = "Proteus", label: str = ""):
        super().__init__()
        self._video       = video_path
        self._model       = model if model in _ENDPOINTS else "topaz"
        self._factor      = int(upscale_factor)
        self._topaz_model = topaz_model or "Proteus"
        self._label       = label or "upscaled"

    def run(self):
        key = load_config().get("api_key", "").strip()
        if not key:
            self._mock()
        else:
            self._real(key)

    def _mock(self):
        for pct, msg in [
            (20, "Upscaling (mode mock)…"),
            (60, "Traitement de la vidéo…"),
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

            self.progress.emit(8, "Envoi de la vidéo à fal.ai…")
            video_url = fal_client.upload_file(self._video)

            args = {"video_url": video_url}
            if self._model == "topaz":
                args["upscale_factor"] = max(1, min(4, self._factor))
                args["model"] = self._topaz_model
            # SeedVR2 : seul video_url est documenté → on n'envoie rien d'autre.

            self.progress.emit(25, f"Upscaling ×{self._factor} ({self._model})…")
            result = fal_client.subscribe(_ENDPOINTS[self._model], arguments=args)

            out_url = self._extract_url(result)
            if not out_url:
                raise RuntimeError(f"URL vidéo manquante : {str(result)[:200]}")

            self.progress.emit(75, "Téléchargement de la vidéo upscalée…")
            data = requests.get(out_url, timeout=600).content

            # MÊME NOM que le fichier source (dossier différent) → « Relink Media »
            # direct dans DaVinci Resolve : on pointe le dossier data/upscaled/ et
            # toute la timeline se relinke en haute résolution. Un ré-upscale du
            # même clip remplace la version précédente.
            base = os.path.splitext(os.path.basename(self._video))[0]
            safe = "".join(c for c in base if c.isalnum() or c in " -_.()").strip() \
                or (self._label or "upscaled")
            path = os.path.join(_upscale_output_dir(), f"{safe}.mp4")
            with open(path, "wb") as f:
                f.write(data)

            self.progress.emit(100, "Upscalé ✓")
            self.finished.emit(path)

        except Exception as e:
            self.failed.emit(humanize_api_error(f"Erreur upscaling : {e}"))

    @staticmethod
    def _extract_url(result) -> str:
        if not isinstance(result, dict):
            return ""
        v = result.get("video")
        if isinstance(v, dict):
            return v.get("url", "")
        if isinstance(v, list) and v:
            first = v[0]
            return (first.get("url", "") if isinstance(first, dict)
                    else first if isinstance(first, str) else "")
        return result.get("url", "") or result.get("video_url", "")
