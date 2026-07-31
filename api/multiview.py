"""Atelier 7 vues — trois moteurs de VRAIES rotations de décor.

Réponse au constat 2026-07-23 : les moteurs d'ÉDITION 2D (Nano Banana,
Seedream…) n'ont aucune notion de pose caméra → les six vues dérivées d'un
décor se ressemblent toutes, quel que soit le prompt. Trois voies avec une
vraie géométrie, à comparer depuis l'onglet « 7 vues » de la page Décors :

1. ``QwenMultiAngleWorker``  — ``fal-ai/qwen-image-edit-2511-multiple-angles`` :
   LoRA entraîné sur des rendus 3D, ANGLES NUMÉRIQUES (horizontal 0-360°,
   vertical −30..90°, zoom 0-10). Un appel par vue dérivée (6).
2. ``SeedanceOrbitWorker``   — ``bytedance/seedance-2.0/image-to-video`` :
   orbite 360° lente autour du décor depuis l'image d'ensemble, puis frames
   extraites aux quarts de tour. Couvre les 4 faces murales SEULEMENT
   (Sol/Plafond sont hors d'une orbite horizontale).
3. ``HunyuanPanoramaWorker`` — ``fal-ai/hunyuan_world`` : panorama 360°
   équirectangulaire depuis l'image d'ensemble, puis les 6 vues sont des
   reprojections LOCALES (``core/panorama``) — géométrie cohérente par
   construction, aucune génération supplémentaire.

Signaux communs : ``progress(int, str)`` · ``view_done(dict)`` ·
``done(list)`` · ``failed(str)``. Sans clé fal.ai → ``done([])`` (mock,
cohérent avec le reste de l'app). Les dicts de vue ont la MÊME forme que
``GenerateRoomViewsWorker`` : ``{"label","code","path","thumbnail_path",
"prompt"}`` (+ ``is_panorama``/``is_orbit_video`` pour les artefacts).
"""

from __future__ import annotations

import os
import time

from PyQt6.QtCore import QThread, pyqtSignal

from core.config import load_config
from core.worker import humanize_api_error
from core.room_views import SIX_FACES


QWEN_ENDPOINT    = "fal-ai/qwen-image-edit-2511-multiple-angles"
HUNYUAN_ENDPOINT = "fal-ai/hunyuan_world"
ORBIT_ENDPOINT   = "bytedance/seedance-2.0/image-to-video"

# Angles numériques Qwen par code de vue PANDORA (schéma vérifié 2026-07-31 :
# horizontal 0=face, 90=droite, 180=arrière, 270=gauche ; vertical −30=contre-
# plongée … 90=vue d'oiseau). ⚠ Le LoRA ne monte pas au-delà de −30° vers le
# haut : le Plafond est APPROCHÉ (contre-plongée maximale + consigne texte).
QWEN_ANGLES: dict[str, dict] = {
    "avant":   {"horizontal_angle": 0,   "vertical_angle": 0},
    "droite":  {"horizontal_angle": 90,  "vertical_angle": 0},
    "arriere": {"horizontal_angle": 180, "vertical_angle": 0},
    "gauche":  {"horizontal_angle": 270, "vertical_angle": 0},
    "sol":     {"horizontal_angle": 0,   "vertical_angle": 90},
    "plafond": {"horizontal_angle": 0,   "vertical_angle": -30},
}

_QWEN_EXTRA: dict[str, str] = {
    "sol":     "top-down view of the floor of this exact location",
    "plafond": "looking up towards the ceiling of this exact location",
}

# Orbite : sens de rotation vers la DROITE ; la frame t=0 est l'angle de
# l'image maître (assimilé à « Avant »), puis un quart de tour par face.
ORBIT_FACES = ["avant", "droite", "arriere", "gauche"]
ORBIT_DURATION_S = 8       # 45°/s : assez lent pour une géométrie stable
ORBIT_RESOLUTION = "720p"  # image-to-video Seedance 2.0 plafonne à 720p

_LABELS = {code: label for label, code, _ in SIX_FACES}


def orbit_face_times(duration_s: float) -> dict[str, float]:
    """Temps d'extraction (s) des 4 faces sur une orbite 360° régulière.

    t=0 → Avant (angle de départ) puis un quart de tour par face ; la fin de
    la vidéo (retour à l'avant) n'est pas utilisée.
    """
    d = max(1.0, float(duration_s))
    return {code: (i / 4.0) * d for i, code in enumerate(ORBIT_FACES)}


def _dl(url: str) -> bytes:
    import requests
    return requests.get(url, timeout=300).content


def _first_image_url(result) -> str:
    """URL de la 1re image — accepte {images:[{url}]} ET {image:{url}}."""
    if isinstance(result, dict):
        images = result.get("images")
        if isinstance(images, list) and images and isinstance(images[0], dict):
            u = images[0].get("url", "")
            if u:
                return u
        image = result.get("image")
        if isinstance(image, dict) and image.get("url"):
            return image["url"]
    raise RuntimeError(f"Réponse API sans image : {str(result)[:200]}")


class _MultiviewBase(QThread):
    """Socle commun : clé, upload de l'image maître, sauvegarde + aperçus."""

    progress  = pyqtSignal(int, str)
    view_done = pyqtSignal(dict)
    done      = pyqtSignal(list)
    failed    = pyqtSignal(str)

    def __init__(self, image_path: str, decor_name: str, base_prompt: str = ""):
        super().__init__()
        self._image_path = image_path or ""
        self._name       = decor_name or "decor"
        self._base       = base_prompt or ""

    # ── helpers partagés ──────────────────────────────────────────────────────
    def _key(self) -> str:
        return load_config().get("api_key", "").strip()

    def _out_dir(self) -> str:
        from api.nano_banana import _project_images_dir
        return _project_images_dir("decors")

    def _safe(self) -> str:
        return ("".join(c for c in self._name if c.isalnum() or c in " -_")
                .strip() or "decor")

    def _save(self, data: bytes, code: str, ext: str = "png") -> tuple[str, str]:
        """Écrit l'image et prépare l'aperçu léger. → (chemin, aperçu)."""
        path = os.path.join(self._out_dir(),
                            f"{self._safe()}_{code}_{int(time.time())}.{ext}")
        with open(path, "wb") as f:
            f.write(data)
        thumb = ""
        try:
            from core.image_preview import make_preview
            thumb = make_preview(path, max_size=(512, 512))
        except Exception:
            pass
        return path, thumb

    def _upload_master(self, fal_client) -> str:
        from api.real import _fal_upload
        return _fal_upload(fal_client, self._image_path)

    def _entry(self, code: str, path: str, thumb: str, prompt: str) -> dict:
        return {"label": _LABELS.get(code, code), "code": code, "path": path,
                "thumbnail_path": thumb, "prompt": prompt}

    def _base_en(self) -> str:
        if not self._base:
            return ""
        try:
            from core.lang import translate_to_english
            return translate_to_english(self._base)
        except Exception:
            return self._base


class QwenMultiAngleWorker(_MultiviewBase):
    """Six vues dérivées par angles numériques (un appel Qwen par vue)."""

    def __init__(self, image_path: str, decor_name: str, base_prompt: str = "",
                 zoom: float = 0.0):
        super().__init__(image_path, decor_name, base_prompt)
        self._zoom = max(0.0, min(10.0, float(zoom)))

    def run(self):
        if not self._key():
            self.done.emit([])   # mock
            return
        if not (self._image_path and os.path.isfile(self._image_path)):
            self.failed.emit("Le décor n'a pas d'image d'ensemble à faire pivoter.")
            return
        try:
            import fal_client
            os.environ["FAL_KEY"] = self._key()
            self.progress.emit(4, "Upload de l'image d'ensemble…")
            master_url = self._upload_master(fal_client)
        except Exception as e:
            self.failed.emit(humanize_api_error(f"Upload impossible : {e}"))
            return

        out: list[dict] = []
        last_err = ""
        codes = [code for _l, code, _d in SIX_FACES]
        for i, code in enumerate(codes):
            if self.isInterruptionRequested():
                break
            self.progress.emit(8 + int(i / len(codes) * 88),
                               f"[{i + 1}/6] Vue « {_LABELS[code]} » (angles)…")
            extra = _QWEN_EXTRA.get(
                code, "same location seen from this new camera angle")
            prompt = f"{extra}, same scene, empty location, no people"
            args = {
                "image_urls": [master_url],
                "zoom": self._zoom,
                "additional_prompt": prompt,
                **QWEN_ANGLES[code],
            }
            try:
                res = fal_client.subscribe(QWEN_ENDPOINT, arguments=args)
                path, thumb = self._save(_dl(_first_image_url(res)), code)
                entry = self._entry(code, path, thumb, prompt)
                out.append(entry)
                self.view_done.emit(entry)
            except Exception as e:
                last_err = str(e)
            time.sleep(0.6)   # espacement anti-saturation, comme les 7 vues
        if not out and last_err:
            self.failed.emit(humanize_api_error(
                f"Aucune vue générée (angles Qwen) : {last_err}"))
            return
        self._last_error = last_err
        self.progress.emit(100, "Vues terminées")
        self.done.emit(out)


class SeedanceOrbitWorker(_MultiviewBase):
    """Orbite 360° Seedance depuis l'ensemble → frames aux quarts de tour."""

    def run(self):
        if not self._key():
            self.done.emit([])   # mock
            return
        if not (self._image_path and os.path.isfile(self._image_path)):
            self.failed.emit("Le décor n'a pas d'image d'ensemble à faire pivoter.")
            return
        try:
            import fal_client
            os.environ["FAL_KEY"] = self._key()
            self.progress.emit(4, "Upload de l'image d'ensemble…")
            master_url = self._upload_master(fal_client)
            prompt = (
                "slow smooth 360-degree orbit around the entire location, the "
                "camera circles the whole scene at constant height and constant "
                "speed, full revolution, no zoom, no cuts, the scene itself is "
                "perfectly static, nothing moves, empty location, no people"
            )
            self.progress.emit(
                12, f"Orbite 360° Seedance ({ORBIT_DURATION_S} s, {ORBIT_RESOLUTION})…")
            res = fal_client.subscribe(ORBIT_ENDPOINT, arguments={
                "prompt":         prompt,
                "image_url":      master_url,
                "resolution":     ORBIT_RESOLUTION,
                "duration":       str(ORBIT_DURATION_S),
                "aspect_ratio":   "16:9",
                "generate_audio": False,
            })
            video_url = ((res or {}).get("video") or {}).get("url", "")
            if not video_url:
                raise RuntimeError(f"Réponse sans vidéo : {str(res)[:200]}")
            self.progress.emit(58, "Téléchargement de l'orbite…")
            video_path = os.path.join(
                self._out_dir(), f"{self._safe()}_orbit_{int(time.time())}.mp4")
            with open(video_path, "wb") as f:
                f.write(_dl(video_url))
        except Exception as e:
            self.failed.emit(humanize_api_error(f"Orbite Seedance échouée : {e}"))
            return

        from core.video_utils import extract_frame_at
        out: list[dict] = []
        times = orbit_face_times(ORBIT_DURATION_S)
        for i, code in enumerate(ORBIT_FACES):
            self.progress.emit(62 + int(i / len(ORBIT_FACES) * 34),
                               f"Frame « {_LABELS[code]} » ({times[code]:.1f}s)…")
            frame = os.path.join(
                self._out_dir(),
                f"{self._safe()}_{code}_{int(time.time())}_{i}.png")
            if extract_frame_at(video_path, times[code], frame):
                thumb = ""
                try:
                    from core.image_preview import make_preview
                    thumb = make_preview(frame, max_size=(512, 512))
                except Exception:
                    pass
                entry = self._entry(code, frame, thumb,
                                    f"orbit frame at {times[code]:.1f}s")
                out.append(entry)
                self.view_done.emit(entry)
        # La vidéo d'orbite est un artefact utile (visite du décor) → gardée.
        out.append({"label": "Orbite 360°", "code": "orbit", "path": video_path,
                    "thumbnail_path": "", "prompt": "", "is_orbit_video": True})
        self.progress.emit(100, "Vues terminées")
        self.done.emit(out)


class HunyuanPanoramaWorker(_MultiviewBase):
    """Panorama 360° Hunyuan World → 6 reprojections locales (gratuites)."""

    def run(self):
        if not self._key():
            self.done.emit([])   # mock
            return
        if not (self._image_path and os.path.isfile(self._image_path)):
            self.failed.emit("Le décor n'a pas d'image d'ensemble à faire pivoter.")
            return
        try:
            import fal_client
            os.environ["FAL_KEY"] = self._key()
            self.progress.emit(4, "Upload de l'image d'ensemble…")
            master_url = self._upload_master(fal_client)
            base_en = self._base_en() or "the same location, empty, no people"
            self.progress.emit(15, "Panorama 360° Hunyuan World…")
            res = fal_client.subscribe(HUNYUAN_ENDPOINT, arguments={
                "image_url": master_url,
                "prompt":    base_en,
            })
            pano_path, pano_thumb = self._save(
                _dl(_first_image_url(res)), "panorama")
        except Exception as e:
            self.failed.emit(humanize_api_error(f"Panorama Hunyuan échoué : {e}"))
            return

        out: list[dict] = [{
            "label": "Panorama 360°", "code": "panorama", "path": pano_path,
            "thumbnail_path": pano_thumb, "prompt": "", "is_panorama": True,
        }]
        try:
            from core.panorama import render_views
            self.progress.emit(70, "Reprojection des 6 vues (local)…")
            views = render_views(pano_path, self._out_dir(), self._safe())
        except Exception as e:
            self.failed.emit(humanize_api_error(
                f"Reprojection du panorama échouée : {e}"))
            return
        for code, path in views:
            thumb = ""
            try:
                from core.image_preview import make_preview
                thumb = make_preview(path, max_size=(512, 512))
            except Exception:
                pass
            entry = self._entry(code, path, thumb,
                                f"reprojection {code} du panorama 360°")
            out.append(entry)
            self.view_done.emit(entry)
        self.progress.emit(100, "Vues terminées")
        self.done.emit(out)
