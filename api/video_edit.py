"""api/video_edit.py — Éditeurs vidéo cloud (fal.ai) pour « Modifier un clip ».

Une TABLE, un worker. Chaque moteur déclare son point d'accès, ses champs et
son tarif ; `VideoEditWorker` fait le reste (mode simulation sans clé, envoi
du clip et des références sur le CDN fal, traduction du prompt, appel,
résultat au format des onglets : `video_url` — le téléchargement et le nommage
« <clip>_NN.mp4 » restent à core/download, comme pour Seedance et Pixverse).

Relevé fal.ai VÉRIFIÉ fiche par fiche le 24/09/2026 (id, champs, prix — voir
mémoire « modifier-un-clip-audit ») :
  Kling O3 Edit (Pro / Standard / 4K) et Kling O1 Edit : même grammaire de
    balises que Seedance (@Video1, @Image1…), durée de la source, 3–15 s.
  Wan 2.7 Edit : `duration: 0` = durée de la source, `audio_setting: origin`
    garde la piste, une image de référence.
  HappyHorse Video Edit : jusqu'à 5 références, sortie plafonnée à 15 s.
  Bernini-R Edit / Reference Edit : le même modèle que le gabarit ComfyUI
    local — ici sur fal, 0,08 $/s.
  FLUX.3 Edit Video (0,03 $/s, 720p, clips < 15 s), Gemini Omni Flash 1.1
    Edit (360p → 4K), Lucy Edit Pro (Decart).
Écartés : Grok edit (rabaisse à 854×480, 8 s), Luma Ray 3.2 (5 s ou 10 s
seulement), Gemini 1.0 (restriction EEE sur les vidéos téléversées).

Ajoutés le 14/11/2026 (demande Matthieu : « se rapprocher de Genjutsu de Higgsfield », visages
des acteurs), fiches relues le jour même :
  H3 Max Recast (MiniMax, fal `minimax/h3-max/recast`) : remplace les personnes du clip par 1 à 4
    photos — ordre gauche → droite —, garde mouvement, caméra, coupes et son. Avec les portraits
    du CASTING, les acteurs gardent les visages de leurs fiches. 5–30 s, plans ≤ 15 s.
  Lucy Restyle (Decart, fal) : restyle à 0,01 $/s (Lucy 2.5 / 2.6 n'existent qu'en flux WebRTC,
    sans envoi de fichier : inutilisables ici).
  Runway Aleph 2.0 — chez RUNWARE (`runway:aleph@2.0`, absent de fal) : on édite une image, le
    clip suit ; jusqu'à 5 images-clés. Durée et définition : celles du clip.
"""

from __future__ import annotations

import os
import re
import time

from PyQt6.QtCore import pyqtSignal

from api.video_engines import _CancellableWorker, _fal_upload, engine_prompt
from core.config import load_config
from core.worker import humanize_api_error

_SOURCE = [("Définition du clip source", "source")]

#: key → fiche. `tags` : le moteur comprend @Video1/@Image1 (sinon les balises
#: sont retirées) ; `refs` : nombre max d'images de référence ; `res` : options
#: de résolution (libellé, valeur API) ; `price` : $/s par valeur de résolution.
EDIT_ENGINES: dict[str, dict] = {
    "kling-o3-edit-pro": {
        "label": "Kling O3 Edit Pro  (~$0.168/s · @Video1 @Image1)",
        "endpoint": "fal-ai/kling-video/o3/pro/video-to-video/edit",
        "price": {"source": 0.168}, "res": _SOURCE, "refs": 4, "tags": True,
        "fields": {"image_urls": "image_urls", "keep_audio": True},
        "limits": "3–15 s · 720–3840 px · ≤200 Mo",
    },
    "kling-o3-edit-std": {
        "label": "Kling O3 Edit Standard  (~$0.126/s · @Video1 @Image1)",
        "endpoint": "fal-ai/kling-video/o3/standard/video-to-video/edit",
        "price": {"source": 0.126}, "res": _SOURCE, "refs": 4, "tags": True,
        "fields": {"image_urls": "image_urls", "keep_audio": True},
        "limits": "3–15 s · 720–3840 px · ≤200 Mo",
    },
    "kling-o3-edit-4k": {
        "label": "Kling O3 Edit 4K  (~$0.42/s · @Video1 @Image1)",
        "endpoint": "fal-ai/kling-video/o3/4k/video-to-video/edit",
        "price": {"source": 0.42}, "res": _SOURCE, "refs": 4, "tags": True,
        "fields": {"image_urls": "image_urls", "keep_audio": True},
        "limits": "3–15 s · 720–3840 px · ≤200 Mo",
    },
    "kling-o1-edit": {
        "label": "Kling O1 Edit  (~$0.168/s · @Video1 @Image1)",
        "endpoint": "fal-ai/kling-video/o1/video-to-video/edit",
        "price": {"source": 0.168}, "res": _SOURCE, "refs": 4, "tags": True,
        "fields": {"image_urls": "image_urls", "keep_audio": True},
        "limits": "3–10 s · 720–2160 px · ≤200 Mo",
    },
    "wan-2.7-edit": {
        "label": "Wan 2.7 Edit  (~$0.10/s 720p · $0.15/s 1080p)",
        "endpoint": "fal-ai/wan/v2.7/edit-video",
        "price": {"720p": 0.10, "1080p": 0.15},
        "res": [("1080p", "1080p"), ("720p", "720p")], "refs": 1, "tags": False,
        "fields": {"image_url": "reference_image_url", "resolution": True,
                   "extra": {"duration": 0, "audio_setting": "origin"}},
        "limits": "2–10 s · ≤100 Mo",
    },
    "happy-horse-edit": {
        "label": "HappyHorse Video Edit  (~$0.14/s 720p · $0.28/s 1080p)",
        "endpoint": "alibaba/happy-horse/video-edit",
        "price": {"720p": 0.14, "1080p": 0.28},
        "res": [("1080p", "1080p"), ("720p", "720p")], "refs": 5, "tags": False,
        "fields": {"image_urls": "reference_image_urls", "resolution": True,
                   "extra": {"audio_setting": "origin"}},
        "limits": "3–60 s en entrée · sortie ≤15 s · ≤100 Mo",
    },
    "bernini-r-edit": {
        "label": "Bernini-R Edit  (~$0.08/s · même modèle que ComfyUI local)",
        "endpoint": "fal-ai/bernini-r/edit-video",
        "endpoint_refs": "fal-ai/bernini-r/reference-edit-video",
        "price": {"source": 0.08}, "res": _SOURCE, "refs": 5, "tags": False,
        "fields": {"image_urls": "reference_image_urls", "negative": "negative_prompt"},
        "limits": "848 px max par défaut",
    },
    "flux-3-edit": {
        "label": "FLUX.3 Edit Video [FAST]  (~$0.03/s · 720p)",
        "endpoint": "blackforestlabs/flux-3/edit-video",
        "price": {"source": 0.03}, "res": _SOURCE, "refs": 0, "tags": False,
        "fields": {"extra": {"safety_tolerance": "4"}},
        "limits": "clip < 15 s · < 50 Mo · sortie 720p",
    },
    "gemini-omni-1.1-edit": {
        "label": "Gemini Omni Flash 1.1 Edit  (~$0.10/s 720p · $0.30/s 4K)",
        "endpoint": "google/gemini-omni-flash/v1.1/edit",
        "price": {"360p": 0.03, "720p": 0.10, "1080p": 0.15, "4k": 0.30},
        "res": [("1080p", "1080p"), ("720p", "720p"), ("4K", "4k"), ("360p", "360p")],
        "refs": 0, "tags": False, "fields": {"resolution": True}, "limits": "",
    },
    "lucy-edit-pro": {
        "label": "Lucy Edit Pro (Decart)  (~$0.15/s 720p · $0.10/s 480p)",
        "endpoint": "decart/lucy-edit/pro",
        "price": {"720p": 0.15, "480p": 0.10},
        "res": [("720p", "720p"), ("480p", "480p")], "refs": 0, "tags": False,
        "fields": {"resolution": True, "extra": {"enhance_prompt": True}}, "limits": "",
    },
    "h3-max-recast": {
        "label": "H3 Max Recast · remplacer les acteurs par leurs photos  (~$0.17/s 1080p · $0.085/s 768p)",
        "endpoint": "minimax/h3-max/recast",
        "price": {"1080P": 0.17, "768P": 0.085},
        "res": [("1080p", "1080P"), ("768p", "768P")], "refs": 4, "tags": False,
        "needs_refs": True, "prompt_optional": True,
        "fields": {"image_urls": "reference_image_urls", "resolution": True},
        "limits": "5–30 s (plans ≤ 15 s) · 1 à 4 photos, de gauche à droite",
    },
    "lucy-restyle": {
        "label": "Lucy Restyle (Decart)  (~$0.01/s · 720p)",
        "endpoint": "decart/lucy-restyle",
        "price": {"720p": 0.01},
        "res": [("720p", "720p")], "refs": 0, "tags": False,
        "fields": {"resolution": True, "extra": {"enhance_prompt": True}},
        "limits": "jusqu'à 30 min",
    },
    "aleph-2": {
        "label": "Runway Aleph 2 · via Runware  (~$0.28/s · images-clés)",
        "provider": "runware", "model": "runway:aleph@2.0",
        "endpoint": "runware · runway:aleph@2.0",          # informatif : pas d'appel fal
        "price": {"source": 0.28}, "res": _SOURCE, "refs": 5, "tags": False,
        "fields": {}, "limits": "2–30 s · ≤ 32 Mo · 1080p",
    },
}

ENGINE_ORDER = list(EDIT_ENGINES)

_TAG = re.compile(r"@(Video|Image|Audio|Element)\d*", re.I)
_TAG_WORDS = {"video": "the video", "image": "the reference image",
              "audio": "the audio", "element": "the reference element"}


def strip_tags(text: str) -> str:
    """@Video1 → « the video »… pour les moteurs qui n'ont pas la grammaire Seedance."""
    t = _TAG.sub(lambda m: _TAG_WORDS.get(m.group(1).lower(), "the video"), text or "")
    return re.sub(r"\s{2,}", " ", t).strip()


def is_edit_engine(key: str) -> bool:
    return str(key or "") in EDIT_ENGINES


def price_table() -> dict:
    """Grille $/s par moteur (core/pricing la lit — UNE source)."""
    return {k: dict(v["price"]) for k, v in EDIT_ENGINES.items()}


def build_args(key: str, prompt_en: str, video_url: str, ref_urls: list[str],
               resolution: str = "", negative: str = "") -> tuple[str, dict]:
    """(endpoint, arguments) pour un moteur de la table — PUR, testable sans réseau."""
    spec = EDIT_ENGINES[key]
    f = spec.get("fields") or {}
    prompt = prompt_en if spec.get("tags") else strip_tags(prompt_en)
    args: dict = {"video_url": video_url}
    if prompt or not spec.get("prompt_optional"):
        args["prompt"] = prompt
    refs = [u for u in (ref_urls or []) if u][: int(spec.get("refs") or 0)]
    endpoint = spec["endpoint"]
    if refs:
        if f.get("image_urls"):
            args[f["image_urls"]] = refs
        elif f.get("image_url"):
            args[f["image_url"]] = refs[0]
        if spec.get("endpoint_refs"):
            endpoint = spec["endpoint_refs"]
    if f.get("keep_audio") is not None:
        args["keep_audio"] = bool(f["keep_audio"])
    if f.get("resolution") and resolution and resolution != "source":
        args["resolution"] = resolution
    if f.get("negative") and negative:
        args[f["negative"]] = negative
    for k, v in (f.get("extra") or {}).items():
        args[k] = v
    return endpoint, args


def _extract_video_url(result) -> str:
    if not isinstance(result, dict):
        return ""
    v = result.get("video")
    if isinstance(v, dict) and v.get("url"):
        return str(v["url"])
    if isinstance(v, str):
        return v
    return str(result.get("video_url") or result.get("url") or "")


class VideoEditWorker(_CancellableWorker):
    """params : engine (clé de EDIT_ENGINES), video_path, prompt, ref_images,
    resolution, duration (durée source, pour l'estimation), negative, engine_label."""
    progress = pyqtSignal(int, str)
    finished = pyqtSignal(dict)
    failed   = pyqtSignal(str)

    def __init__(self, params: dict):
        super().__init__()
        self.params = dict(params or {})
        self._key = str(self.params.get("engine") or "")
        self._spec = EDIT_ENGINES.get(self._key) or {}
        self._label = self.params.get("engine_label") or self._spec.get("label", self._key).split("  (")[0]

    def run(self):
        try:
            if not self._spec:
                raise ValueError(f"Moteur d'édition inconnu : {self._key}")
            video_path = self.params.get("video_path") or ""
            if not (video_path and os.path.isfile(video_path)):
                raise RuntimeError("Clip source introuvable.")
            key = load_config().get("api_key", "").strip()
            try:
                dur = float(self.params.get("duration") or 0)
            except (TypeError, ValueError):
                dur = 0.0
            res = str(self.params.get("resolution") or "source").split()[0]
            rate = self._spec["price"].get(res) or next(iter(self._spec["price"].values()))
            cost = round(dur * rate, 3) if dur else 0.0
            n_refs = len([p for p in (self.params.get("ref_images") or []) if p and os.path.isfile(p)])
            if self._spec.get("needs_refs") and not n_refs:
                raise RuntimeError(f"{self._label} : il faut au moins une photo de référence "
                                   "(portraits du casting ou image de référence).")
            if self._spec.get("provider") == "runware":
                return self._run_runware(key, dur, cost)
            if not key:
                for pct, msg in [(20, f"{self._label} (mode mock)…"),
                                 (100, "Terminé — mode mock (aucune clé fal.ai)")]:
                    self.progress.emit(pct, msg)
                    time.sleep(0.3)
                if not self._cancelled:
                    self.finished.emit({"video_url": "", "mock": True, "prompt": self.params.get("prompt", ""),
                                        "mode": "t2v", "model": self._key, "credits_used": 0.0})
                return
            import fal_client
            os.environ["FAL_KEY"] = key
            self.progress.emit(6, f"{self._label} — traduction du prompt…")
            prompt_en = engine_prompt(self.params)
            self.progress.emit(10, f"{self._label} — envoi du clip…")
            video_url = _fal_upload(fal_client, video_path)
            refs = []
            for i, p in enumerate([p for p in (self.params.get("ref_images") or []) if p and os.path.isfile(p)]):
                if i >= int(self._spec.get("refs") or 0):
                    break
                self.progress.emit(14 + i, f"{self._label} — envoi de la référence {i + 1}…")
                refs.append(_fal_upload(fal_client, p))
            endpoint, args = build_args(self._key, prompt_en, video_url, refs, res,
                                        self.params.get("negative") or "")
            self.progress.emit(25, f"{self._label} — édition en cours (peut prendre 1–5 min)…")
            result = fal_client.subscribe(endpoint, arguments=args)
            url = _extract_video_url(result)
            if not url:
                raise RuntimeError(f"URL vidéo manquante : {str(result)[:200]}")
            self.progress.emit(100, f"{self._label} ✓  ~${cost:.2f}")
            if not self._cancelled:
                self.finished.emit({
                    "video_url":    url,
                    "url":          url,
                    "prompt":       self.params.get("prompt", ""),
                    "mode":         "t2v",
                    "model":        self._key,
                    "duration":     dur,
                    "resolution":   res,
                    "credits_used": cost,
                    "seed":         (result.get("seed") if isinstance(result, dict) else 0) or 0,
                })
        except Exception as e:
            if not self._cancelled:
                self.failed.emit(humanize_api_error(f"Erreur {self._label} : {e}"))

    def _run_runware(self, fal_key: str, dur: float, cost: float) -> None:
        """Aleph 2 chez Runware : le clip passe par le relais fal (Runware ne reçoit pas de
        vidéo en ligne), les images-clés en data URI ; puis la tâche et son suivi."""
        from api import runware
        from api.distrib_upload import Uploader
        from core.media_provider import provider_key
        rw_key = provider_key("runware")
        if not rw_key:
            raise RuntimeError("Aleph 2 passe par Runware : saisissez la clé Runware dans "
                               "Paramètres → Distributeurs.")
        relay = None
        if fal_key:
            import fal_client
            os.environ["FAL_KEY"] = fal_key
            relay = lambda p: _fal_upload(fal_client, p)   # noqa: E731
        up = Uploader("runware", rw_key, fal_relay=relay)
        self.progress.emit(6, f"{self._label} — traduction du prompt…")
        prompt_en = strip_tags(engine_prompt(self.params))
        self.progress.emit(10, f"{self._label} — envoi du clip…")
        video_url = up.send(self.params["video_path"])
        frames = [up.send(p) for p in (self.params.get("ref_images") or []) if p and os.path.isfile(p)][:5]
        task = runware.edit_task(self._spec["model"], prompt_en, video_url, frames)
        result = runware.run_task(task, rw_key, self.progress.emit, lambda: self._cancelled)
        url = _extract_video_url(result)
        if not url:
            if self._cancelled:
                return
            raise RuntimeError("Runware n'a pas rendu de vidéo.")
        real = result.get("cost_usd")
        cost = float(real) if isinstance(real, (int, float)) else cost
        self.progress.emit(100, f"{self._label} ✓  ~${cost:.2f}")
        if not self._cancelled:
            self.finished.emit({"video_url": url, "url": url, "prompt": self.params.get("prompt", ""),
                                "mode": "t2v", "model": self._key, "duration": dur,
                                "resolution": "source", "credits_used": cost, "seed": 0})
