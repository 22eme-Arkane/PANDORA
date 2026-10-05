"""
api/piapi.py — Génération Seedance via PiAPI (distributeur low cost).

Docs relues le 04/10/2026 :
  https://piapi.ai/docs/seedance-api/seedance-2   (2.0, fast, mini)
  https://piapi.ai/docs/seedance-api/seedance-25  (2.5)
  POST https://api.piapi.ai/api/v1/task            (en-tête X-API-Key)
  GET  https://api.piapi.ai/api/v1/task/{task_id}  (suivi)
  corps : {"model": "seedance", "task_type": …, "input": {…}}
  statuts : Pending → Staged → Processing → Completed | Failed
  sortie  : data.output.video (URL mp4)

Seedance 2.0 / fast (task_type « seedance-2 », « seedance-2-fast ») :
  input = prompt, mode (text_to_video | first_last_frames | omni_reference),
  duration 4–15, aspect_ratio, resolution, image_urls (≤ 9), video_urls (≤ 3),
  audio_urls (≤ 3), audio (booléen).
Seedance 2.5 (task_type « seedance-2.5 ») — schéma DIFFÉRENT :
  PAS de champ « mode » ni d'interrupteur du son ; duration 4–30 ;
  image_urls ≤ 30, video_urls ≤ 10, audio_urls ≤ 10 ;
  omni_reference_task_type (auto | reference | edit | extend), aspect_ratio
  « adaptive » obligatoire en modification / prolongation. Sans champ de
  première / dernière image, l'image→vidéo n'existe pas en 2.5 chez PiAPI
  (core/media_provider ne le couvre donc pas).

Les images sont désignées dans le prompt par « @image1, @image2… » (minuscules
dans la doc PiAPI) : les jetons « @Image1 » écrits pour fal sont convertis.

⚠ PiAPI n'accepte QUE des URL publiques : les fichiers locaux sont déposés par
api/distrib_upload (dépôt éphémère PiAPI, sinon relais fal) AVANT cet appel.
Grille (04/10/2026) : 2.0 0,10 / 0,20 / 0,50 $/s (480 / 720 / 1080p) ;
fast 0,048 / 0,096 ; 2.5 0,15 / 0,35 / 0,80 — voir core/media_provider.
"""

import re

import requests

from api.distrib_common import connection_message, poll_until

_BASE = "https://api.piapi.ai/api/v1/task"
_POLL_EVERY_S = 6          # PiAPI recommande un suivi doux

_MODE_MAP = {
    "t2v": "text_to_video",
    "i2v": "first_last_frames",
    "ref": "omni_reference",
    "ext": "omni_reference",
}

_TASK_TYPES = {
    "seedance-2.0":      "seedance-2",
    "seedance-2.0-fast": "seedance-2-fast",
    "seedance-2.5":      "seedance-2.5",
}


def _headers(api_key: str) -> dict:
    return {"X-API-Key": api_key, "Content-Type": "application/json"}


def test_key(api_key: str) -> tuple[bool, str]:
    """Teste la clé PiAPI : une création de tâche VIDE doit répondre 400
    (clé valide, corps invalide) et non 401/403 (clé refusée).
    Aucune génération n'est lancée — donc aucun coût."""
    try:
        r = requests.post(_BASE, headers=_headers(api_key.strip()),
                          json={}, timeout=15)
        if r.status_code in (401, 403):
            return False, "Clé PiAPI refusée (401/403) — vérifie la clé."
        return True, "Connexion PiAPI OK — clé acceptée."
    except requests.RequestException as e:
        return False, f"PiAPI injoignable : {e}"


def piapi_prompt(prompt: str) -> str:
    """« @Image1 » (convention fal) → « @image1 » (convention PiAPI)."""
    return re.sub(r"@Image(\d+)", r"@image\1", prompt or "")


def build_input(mode: str, args: dict, model: str = "seedance-2.0") -> dict:
    """Traduit les `args` préparés par api/real.py (format fal) vers le
    champ `input` PiAPI. Ne lève jamais : les champs absents sont ignorés."""
    is_25 = (model == "seedance-2.5")
    inp: dict = {
        "prompt":       piapi_prompt(args.get("prompt", "")),
        "resolution":   args.get("resolution", "720p"),
        "aspect_ratio": args.get("aspect_ratio", "16:9"),
    }
    if not is_25:
        inp["mode"] = _MODE_MAP.get(mode, "text_to_video")
        inp["audio"] = bool(args.get("generate_audio", True))
    try:
        inp["duration"] = max(4, min(30 if is_25 else 15, int(args.get("duration", 10))))
    except (TypeError, ValueError):
        inp["duration"] = 10

    max_img, max_vid, max_aud = (30, 10, 10) if is_25 else (9, 3, 3)
    if mode == "i2v" and not is_25:
        # first_last_frames : [départ] ou [départ, fin]
        urls = [u for u in (args.get("image_url"), args.get("end_image_url")) if u]
        if urls:
            inp["image_urls"] = urls
    else:
        if args.get("image_urls"):
            inp["image_urls"] = list(args["image_urls"])[:max_img]
        if args.get("video_urls"):
            inp["video_urls"] = list(args["video_urls"])[:max_vid]
        if args.get("audio_urls"):
            inp["audio_urls"] = list(args["audio_urls"])[:max_aud]
    if is_25 and mode == "ext":
        editing = (args.get("task") == "editing")
        inp["omni_reference_task_type"] = "edit" if editing else "extend"
        inp["aspect_ratio"] = "adaptive"
        if editing:
            inp["duration"] = -1     # la modification garde la durée du clip source
    return inp


def run(mode: str, model: str, args: dict, api_key: str,
        emit_progress, is_cancelled) -> dict:
    """Crée la tâche Seedance chez PiAPI puis attend le résultat.

    Retourne un dict au MÊME format que le résultat fal de run_real :
    {"request_id": …, "video": {"url": …}, "seed": 0}. Lève RuntimeError
    avec un message humain en cas d'échec (affiché via humanize_api_error)."""
    task_type = _TASK_TYPES.get(model, "seedance-2")
    payload = {"model": "seedance", "task_type": task_type,
               "input": build_input(mode, args, model)}

    emit_progress(14, f"Envoi à PiAPI ({task_type})…")
    try:
        r = requests.post(_BASE, headers=_headers(api_key), json=payload,
                          timeout=45)
    except requests.RequestException as e:
        raise RuntimeError(connection_message("PiAPI", e))
    if r.status_code in (401, 403):
        raise RuntimeError("Clé PiAPI refusée — vérifie la clé dans "
                           "Paramètres → avancés.")
    try:
        data = r.json().get("data") or {}
    except ValueError:
        data = {}
    task_id = data.get("task_id", "")
    if r.status_code >= 400 or not task_id:
        _msg = ""
        try:
            _msg = r.json().get("message", "")
        except ValueError:
            pass
        raise RuntimeError(f"PiAPI a refusé la tâche ({r.status_code}) : "
                           f"{_msg or r.text[:200]}")

    _labels = {"pending": "En file d'attente PiAPI…",
               "staged": "Préparation PiAPI…",
               "processing": "Génération en cours (PiAPI)…"}

    def _check():
        rr = requests.get(f"{_BASE}/{task_id}", headers=_headers(api_key), timeout=30)
        if not rr.ok:
            return "wait", "PiAPI répond lentement…"
        d = rr.json().get("data") or {}
        status = (d.get("status") or "").lower()
        if status == "completed":
            video_url = (d.get("output") or {}).get("video", "")
            if not video_url:
                return "fail", "PiAPI : tâche terminée mais sans vidéo dans la réponse."
            return "done", video_url
        if status == "failed":
            _err = d.get("error")
            if isinstance(_err, dict):
                _err = " — ".join(x for x in (str(_err.get("code") or ""),
                                              str(_err.get("message") or ""),
                                              str(_err.get("raw_message") or "")) if x)
            return "fail", f"PiAPI : génération échouée — {_err or 'raison non précisée'}"
        return "wait", _labels.get(status, "Génération en cours (PiAPI)…")

    video_url = poll_until(_check, emit_progress, is_cancelled, "PiAPI",
                           every_s=_POLL_EVERY_S)
    if video_url is None:
        return {}
    return {"request_id": task_id, "video": {"url": video_url}, "seed": 0}


def run_piapi(mode: str, fast: bool, args: dict, api_key: str,
              emit_progress, is_cancelled) -> dict:
    """Ancien point d'entrée (Seedance 2.0 / fast), conservé pour les appelants
    existants : délègue à run()."""
    return run(mode, "seedance-2.0-fast" if fast else "seedance-2.0", args, api_key,
               emit_progress, is_cancelled)
