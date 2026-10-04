"""
api/runware.py — Seedance via Runware (revendeur au prix officiel ByteDance).

Relevé du 04/10/2026 : 2.5 = 0,102 / 0,23 / 0,614 $/s (480p / 720p / 1080p) ;
2.0 = 0,07 / 0,16 / 0,40 / 0,856 $/s (4K). Recharge minimale 20 $, par carte.
Un plan 2.5 de 30 s en 720p : 6,90 $ (14,19 $ chez fal).

Contrat (runware.ai/docs/models/bytedance-seedance-2-5, relu le 04/10/2026) :
  POST https://api.runware.ai/v1    en-tête Authorization: Bearer <clé>
  corps = TABLEAU de tâches :
    [{"taskType": "videoInference", "taskUUID": <uuid4>,
      "model": "bytedance:seedance@2.5", "positivePrompt": …, "duration": 30,
      "width": 1280, "height": 720   (ou "resolution": "720p"),
      "outputFormat": "MP4", "deliveryMethod": "async", "includeCost": true,
      "settings": {"audio": true},
      "inputs": {"frameImages": [{"image": …, "frame": "first"}, …]
                 ou "referenceImages": […], "referenceVideos": […],
                    "referenceAudios": […]}}]
  Suivi : même URL, [{"taskType": "getResponse", "taskUUID": …}]
          → data[].status processing | success | error, videoURL, cost.

Pièges encodés ici :
  · « resolution » et « width/height » s'excluent ; avec frameImages, seule
    « resolution » est permise (le cadre suit la première image) ;
  · en texte→vidéo et en références on envoie width/height (table de la doc) :
    avec la seule résolution, le cadre suivrait les images de référence ;
  · la résolution part TOUJOURS : un oubli était facturé au palier par défaut ;
  · pas de seed en entrée sur la 2.x ; un échec n'est pas facturé.
"""
from __future__ import annotations

import uuid

import requests

from api.distrib_common import http_error_message, poll_until

PROVIDER = "Runware"
_URL = "https://api.runware.ai/v1"

MODEL_IDS = {
    "seedance-2.5": "bytedance:seedance@2.5",
    "seedance-2.0": "bytedance:seedance@2.0",
}

#: Dimensions acceptées (doc Runware), par résolution puis ratio.
_DIMS_25 = {
    "480p":  {"16:9": (854, 480), "4:3": (752, 560), "1:1": (640, 640),
              "3:4": (560, 752), "9:16": (480, 854), "21:9": (992, 432)},
    "720p":  {"16:9": (1280, 720), "4:3": (1112, 834), "1:1": (960, 960),
              "3:4": (834, 1112), "9:16": (720, 1280), "21:9": (1470, 630)},
    "1080p": {"16:9": (1920, 1080), "4:3": (1664, 1248), "1:1": (1440, 1440),
              "3:4": (1248, 1664), "9:16": (1080, 1920), "21:9": (2206, 946)},
}
_DIMS_20 = {
    "480p":  {"16:9": (864, 496), "4:3": (752, 560), "1:1": (640, 640),
              "3:4": (560, 752), "9:16": (496, 864), "21:9": (992, 432)},
    "720p":  _DIMS_25["720p"],
    "1080p": _DIMS_25["1080p"],
    "4k":    {"16:9": (3840, 2160), "4:3": (3326, 2494), "1:1": (2880, 2880),
              "3:4": (2496, 3328), "9:16": (2160, 3840), "21:9": (4398, 1886)},
}

_POLL_EVERY_S = 10


def _headers(api_key: str) -> dict:
    return {"Authorization": f"Bearer {api_key.strip()}",
            "Content-Type": "application/json"}


def test_key(api_key: str) -> tuple[bool, str]:
    """Interroge une tâche inexistante : aucune génération, aucun coût.
    Clé refusée = 401/403 ou code « invalidApiKey »."""
    try:
        r = requests.post(_URL, headers=_headers(api_key),
                          json=[{"taskType": "getResponse", "taskUUID": str(uuid.uuid4())}],
                          timeout=15)
    except requests.RequestException as e:
        return False, f"{PROVIDER} injoignable : {e}"
    if r.status_code in (401, 403) or "invalidapikey" in (r.text or "").lower():
        return False, f"Clé {PROVIDER} refusée — vérifie la clé."
    return True, f"Connexion {PROVIDER} OK — clé acceptée."


def dimensions(model: str, resolution: str, ratio: str) -> tuple[int, int] | None:
    table = _DIMS_25 if model == "seedance-2.5" else _DIMS_20
    return table.get((resolution or "").lower(), {}).get((ratio or "").strip())


def build_task(mode: str, model: str, args: dict, task_uuid: str = "") -> dict:
    """Traduit les `args` préparés par api/real.py (format fal) en tâche
    Runware. Ne lève jamais : les champs absents sont ignorés."""
    engine = model if model in MODEL_IDS else "seedance-2.0"
    res = (args.get("resolution") or "720p").lower()
    try:
        duration = int(args.get("duration", 5))
    except (TypeError, ValueError):
        duration = 5
    duration = max(4, min(30 if engine == "seedance-2.5" else 15, duration))
    task: dict = {
        "taskType":       "videoInference",
        "taskUUID":       task_uuid or str(uuid.uuid4()),
        "model":          MODEL_IDS[engine],
        "positivePrompt": args.get("prompt", ""),
        "duration":       duration,
        "outputFormat":   "MP4",
        "deliveryMethod": "async",
        "includeCost":    True,
        "settings":       {"audio": bool(args.get("generate_audio", True))},
    }
    inputs: dict = {}
    if mode == "i2v":
        frames = [{"image": args["image_url"], "frame": "first"}] if args.get("image_url") else []
        if args.get("end_image_url"):
            frames.append({"image": args["end_image_url"], "frame": "last"})
        if frames:
            inputs["frameImages"] = frames
        task["resolution"] = res          # width/height interdits avec frameImages
    else:
        cap = 30 if engine == "seedance-2.5" else 9
        vcap = 10 if engine == "seedance-2.5" else 3
        if args.get("image_urls"):
            inputs["referenceImages"] = list(args["image_urls"])[:cap]
        if args.get("video_urls"):
            inputs["referenceVideos"] = list(args["video_urls"])[:vcap]
        if args.get("audio_urls"):
            inputs["referenceAudios"] = list(args["audio_urls"])[:vcap]
        dims = dimensions(engine, res, args.get("aspect_ratio", "16:9"))
        if dims:
            task["width"], task["height"] = dims
        else:
            task["resolution"] = res
    if inputs:
        task["inputs"] = inputs
    return task


def _first_error(body) -> str:
    if isinstance(body, dict):
        errs = body.get("errors") or body.get("error")
        if isinstance(errs, list) and errs and isinstance(errs[0], dict):
            e = errs[0]
            return " — ".join(x for x in (str(e.get("code") or ""),
                                           str(e.get("message") or "")) if x)
        if isinstance(errs, dict):
            return " — ".join(x for x in (str(errs.get("code") or ""),
                                           str(errs.get("message") or "")) if x)
    return ""


def run(mode: str, model: str, args: dict, api_key: str,
        emit_progress, is_cancelled) -> dict:
    """Crée la tâche chez Runware puis attend le résultat.

    Rend le MÊME format que le résultat fal de run_real :
    {"request_id", "video": {"url"}, "seed", "cost_usd"}. Lève RuntimeError
    avec un message humain en cas d'échec."""
    task = build_task(mode, model, args)
    task_uuid = task["taskUUID"]
    emit_progress(14, "Envoi à Runware…")
    try:
        r = requests.post(_URL, headers=_headers(api_key), json=[task], timeout=120)
    except requests.RequestException as e:
        raise RuntimeError(f"Runware injoignable : {e}")
    try:
        body = r.json()
    except ValueError:
        body = {}
    if r.status_code >= 400 or _first_error(body):
        detail = _first_error(body)
        if r.status_code in (401, 403) or "invalidapikey" in detail.lower():
            raise RuntimeError(f"Clé Runware refusée — vérifie-la dans Paramètres. {detail}")
        raise RuntimeError(f"Runware a refusé la tâche ({r.status_code}) : "
                           f"{detail or http_error_message(PROVIDER, r)}")

    def _check():
        rr = requests.post(_URL, headers=_headers(api_key),
                           json=[{"taskType": "getResponse", "taskUUID": task_uuid}],
                           timeout=30)
        if rr.status_code >= 500:
            return "wait", "Runware répond lentement…"
        b = rr.json()
        err = _first_error(b)
        if err:
            return "fail", f"Runware : génération échouée — {err}"
        for item in (b.get("data") or []) if isinstance(b, dict) else []:
            if item.get("taskUUID") not in (None, task_uuid):
                continue
            status = (item.get("status") or "").lower()
            if status == "success" and item.get("videoURL"):
                return "done", item
            if status == "error":
                return "fail", ("Runware : génération échouée — "
                                f"{item.get('message') or item.get('error') or 'raison non précisée'}")
            if isinstance(item.get("progress"), (int, float)):
                return "wait", f"Génération en cours (Runware, {int(item['progress'])} %)…"
        return "wait", "Génération en cours (Runware)…"

    item = poll_until(_check, emit_progress, is_cancelled, PROVIDER, every_s=_POLL_EVERY_S)
    if item is None:
        return {}
    cost = item.get("cost")
    return {"request_id": task_uuid, "video": {"url": item.get("videoURL", "")},
            "seed": item.get("seed", 0) or 0,
            "cost_usd": float(cost) if isinstance(cost, (int, float)) else None}
