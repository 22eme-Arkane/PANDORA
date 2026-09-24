"""
api/upscale.py — Workers d'upscaling vidéo via fal.ai.

Modèles :
  - Topaz Video Upscale : fal-ai/topaz/upscale/video
        video_url (req), upscale_factor (1-4, déf. 2), model (déf. "Proteus"), options…
  - Topaz Astra 2       : topaz/upscale/video/creative   (fiche fal 2026-09-24)
        video_url (req), upscale_factor (1-4), prompt, creativity/realism/sharp (0-1),
        target_fps, H264_output — génératif : ~3 $ les 10 s jusqu'en 1080p, 5 $ en 4K (30 fps)
  - SeedVR2 Video       : fal-ai/seedvr/upscale/video   (~$0.001/MP)
        video_url (req), upscale_mode "factor"|"target", upscale_factor (1-10),
        target_resolution 720p…2160p (relevé 2026-09-24 : le facteur est bien accepté)

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
    # Topaz Astra 2 (fal `topaz/upscale/video/creative`, 24/09/2026) : upscale
    # GÉNÉRATIF qui réinvente le détail — ~0,30 $/s jusqu'en 1080p à 30 fps.
    ("Topaz Astra 2  (génératif, ~$0.30/s)", "topaz_creative"),
    ("SeedVR2  (rapide, ~$0.001/MP)",     "seedvr"),
    # SeedVR2 3B sur la machine (gabarit officiel ComfyUI « Video Upscale: SeedVR2
    # 3B Int8 », 4 Go) — 0 $, ComfyUI Desktop doit tourner (24/09/2026).
    ("SeedVR2 sur votre GPU  (ComfyUI · 0 $)", "seedvr_local"),
]

#: Gabarit ComfyUI du mode local (catalogue vidéo — core/comfy_catalog).
SEEDVR_LOCAL_TEMPLATE = "utility_seedvr2_3b_int8_upscale_video"

# Modèles d'amélioration Topaz — (libellé affiché, valeur EXACTE de l'enum API).
# ⚠ Vu en réel (2026-06-11) : « Gaia »/« Artemis »/« Starlight » nus n'existent
# pas dans l'enum fal.ai → erreur immédiate. Enum complet vérifié sur la doc
# fal.ai (2026-06-16) : Proteus, Artemis HQ/MQ/LQ, Nyx, Nyx Fast/XL/HF,
# Gaia HQ/CG/2, Starlight Precise 1/2/2.5, Starlight HQ/Mini/Sharp, Starlight Fast 1/2.
# ⚠ « Astra » n'est PAS dans l'enum vidéo fal.ai → non disponible.
TOPAZ_MODELS = [
    ("Proteus  (polyvalent — recommandé)",            "Proteus"),
    ("Artemis HQ  (footage propre)",                  "Artemis HQ"),
    ("Artemis MQ  (footage moyen)",                   "Artemis MQ"),
    ("Artemis LQ  (footage dégradé)",                 "Artemis LQ"),
    ("Nyx  (réduction de bruit)",                     "Nyx"),
    ("Nyx Fast  (bruit, rapide)",                     "Nyx Fast"),
    ("Nyx XL  (bruit, haute déf.)",                   "Nyx XL"),
    ("Nyx HF  (bruit hautes fréquences)",             "Nyx HF"),
    ("Gaia HQ  (rendu naturel)",                      "Gaia HQ"),
    ("Gaia CG  (rendu 3D / CG)",                      "Gaia CG"),
    ("Gaia 2  (génératif, naturel)",                  "Gaia 2"),
    ("Starlight Mini  (génératif, rapide)",           "Starlight Mini"),
    ("Starlight HQ  (génératif, qualité)",            "Starlight HQ"),
    ("Starlight Sharp  (génératif, net)",             "Starlight Sharp"),
    ("Starlight Precise 1  (génératif, fidèle)",      "Starlight Precise 1"),
    ("Starlight Precise 2  (génératif v2, fidèle)",   "Starlight Precise 2"),
    ("Starlight Precise 2.5  (génératif, dernier)",   "Starlight Precise 2.5"),
    ("Starlight Fast 1  (génératif, rapide)",         "Starlight Fast 1"),
    ("Starlight Fast 2  (génératif v2, rapide)",      "Starlight Fast 2"),
]

_ENDPOINTS = {
    "topaz":          "fal-ai/topaz/upscale/video",
    "topaz_creative": "topaz/upscale/video/creative",
    "seedvr":         "fal-ai/seedvr/upscale/video",
}


def _upscale_output_dir() -> str:
    """Dossier de sortie des vidéos upscalées : 03_production/upscaled, repli
    legacy « upscaled » (arborescence 2026-07-30). ⚠ Le NOM DE FICHIER reste
    strictement celui de la source (contrat Relink DaVinci) — seul le dossier
    est résolu par le layout."""
    try:
        from core import project_layout as _pl
        d = _pl.dir("upscaled")
    except Exception:
        from core.pandora_dirs import get_bin_dir
        d = get_bin_dir("upscaled")
    os.makedirs(d, exist_ok=True)
    return d


class UpscaleVideoWorker(QThread):
    """Upscale un clip vidéo via fal.ai (Topaz, Topaz Astra 2, SeedVR2) ou en
    local (SeedVR2 sur ComfyUI). Sortie = MP4 local."""
    progress = pyqtSignal(int, str)
    finished = pyqtSignal(str)      # chemin local du fichier upscalé
    failed   = pyqtSignal(str)

    def __init__(self, video_path: str, model: str = "topaz", upscale_factor: int = 2,
                 topaz_model: str = "Proteus", label: str = ""):
        super().__init__()
        self._video       = video_path
        self._model       = model if (model in _ENDPOINTS or model == "seedvr_local") else "topaz"
        self._factor      = int(upscale_factor)
        self._topaz_model = topaz_model or "Proteus"
        self._label       = label or "upscaled"
        self._cancelled   = False

    def cancel(self):
        self._cancelled = True

    def run(self):
        if self._model == "seedvr_local":
            self._local()                      # aucune clé : c'est votre carte qui travaille
            return
        key = load_config().get("api_key", "").strip()
        if not key:
            self._mock()
        else:
            self._real(key)

    def _output_path(self) -> str:
        # MÊME NOM que le fichier source (dossier différent) → « Relink Media »
        # direct dans DaVinci Resolve (contrat commun à tous les modes).
        base = os.path.splitext(os.path.basename(self._video))[0]
        safe = "".join(c for c in base if c.isalnum() or c in " -_.()").strip() \
            or (self._label or "upscaled")
        return os.path.join(_upscale_output_dir(), f"{safe}.mp4")

    def _local(self):
        """SeedVR2 par le gabarit officiel ComfyUI (core/comfy_video) — 0 $."""
        try:
            import requests
            from core import comfy_video as _cv
            if not self._video or not os.path.isfile(self._video):
                raise RuntimeError("Vidéo introuvable.")
            res = _cv.subscribe(SEEDVR_LOCAL_TEMPLATE, {"video_path": self._video, "prompt": ""},
                                progress=lambda m: self.progress.emit(30, m),
                                is_cancelled=lambda: self._cancelled)
            self.progress.emit(80, "Téléchargement de la vidéo upscalée…")
            data = requests.get(res["video"]["url"], timeout=600).content
            target = self._output_path()
            ext = (os.path.splitext(res["video"].get("file_name", "") or "")[1] or ".mp4").lower()
            raw = target if ext == ".mp4" else target[:-4] + ext
            with open(raw, "wb") as f:
                f.write(data)
            if ext != ".mp4":
                # WebM/GIF du gabarit → MP4 (ffmpeg embarqué), nom source conservé.
                from api.h3_local import _to_mp4
                out = _to_mp4(raw)
                if out and out != target:
                    os.replace(out, target)
            path = target
            self.progress.emit(100, "Upscalé ✓  0 $")
            if not self._cancelled:
                self.finished.emit(path)
        except Exception as e:
            if not self._cancelled:
                self.failed.emit(humanize_api_error(f"Erreur upscaling local : {e}"))

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
            elif self._model == "topaz_creative":
                # Astra 2 (fiche fal 2026-09-24) : facteur 1-4, réglages neutres
                # (créativité et netteté 0,5) — le prompt guide le détail inventé.
                args["upscale_factor"] = max(1, min(4, self._factor))
                args["creativity"] = 0.5
                args["sharp"] = 0.5
            elif self._model == "seedvr":
                # Fiche fal 2026-09-24 : upscale_mode « factor » + facteur 1-10.
                # Avant, seul video_url partait et fal appliquait son ×2 quel
                # que soit le ×4 demandé dans le menu.
                args["upscale_mode"] = "factor"
                args["upscale_factor"] = max(1, min(10, self._factor))

            self.progress.emit(25, f"Upscaling ×{self._factor} ({self._model})…")
            result = fal_client.subscribe(_ENDPOINTS[self._model], arguments=args)

            out_url = self._extract_url(result)
            if not out_url:
                raise RuntimeError(f"URL vidéo manquante : {str(result)[:200]}")

            self.progress.emit(75, "Téléchargement de la vidéo upscalée…")
            data = requests.get(out_url, timeout=600).content

            # MÊME NOM que le fichier source (dossier différent) → « Relink Media »
            # direct dans DaVinci Resolve : on pointe le dossier upscaled/ et
            # toute la timeline se relinke en haute résolution. Un ré-upscale du
            # même clip remplace la version précédente.
            path = self._output_path()
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
