"""
api/piapi.py — Génération Seedance 2 via PiAPI (distributeur low cost).

Doc vérifiée le 2026-07-16 : https://piapi.ai/docs/seedance-api/seedance-2
  POST https://api.piapi.ai/api/v1/task            (header X-API-Key)
  GET  https://api.piapi.ai/api/v1/task/{task_id}  (polling)
  body : {"model": "seedance", "task_type": "seedance-2[-fast]",
          "input": {prompt, mode, duration, aspect_ratio, resolution,
                    image_urls, video_urls, audio_urls, audio}}
  statuts : Pending → Staged → Processing → Completed | Failed
  sortie  : data.output.video (URL mp4)

Mapping des modes PANDORA → PiAPI :
  t2v → text_to_video · i2v → first_last_frames (keyframes début[/fin])
  ref/ext → omni_reference (images/vidéo/audio de référence)

⚠ Les fichiers locaux sont uploadés par l'appelant (CDN fal.ai) AVANT cet
appel — ce module ne reçoit que des URLs publiques, jamais de chemins.
Grille (indicative) : seedance-2 0.10/0.20/0.50 $/s (480/720/1080p) ;
fast 0.08/0.16 $/s (480/720p) — voir core/media_provider.
"""

import time

import requests

_BASE = "https://api.piapi.ai/api/v1/task"
_POLL_EVERY_S = 6          # PiAPI recommande un polling doux
_TIMEOUT_S    = 60 * 12    # une génération Seedance ne dépasse pas ~10 min

_MODE_MAP = {
    "t2v": "text_to_video",
    "i2v": "first_last_frames",
    "ref": "omni_reference",
    "ext": "omni_reference",
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


def build_input(mode: str, args: dict) -> dict:
    """Traduit les `args` préparés par api/real.py (format fal) vers le
    champ `input` PiAPI. Ne lève jamais : les champs absents sont ignorés."""
    inp: dict = {
        "prompt":       args.get("prompt", ""),
        "mode":         _MODE_MAP.get(mode, "text_to_video"),
        "resolution":   args.get("resolution", "720p"),
        "aspect_ratio": args.get("aspect_ratio", "16:9"),
        "audio":        bool(args.get("generate_audio", True)),
    }
    try:
        inp["duration"] = max(4, min(15, int(args.get("duration", 10))))
    except (TypeError, ValueError):
        inp["duration"] = 10

    if mode == "i2v":
        # first_last_frames : [départ] ou [départ, fin]
        urls = [u for u in (args.get("image_url"), args.get("end_image_url")) if u]
        if urls:
            inp["image_urls"] = urls
    else:
        if args.get("image_urls"):
            inp["image_urls"] = list(args["image_urls"])[:9]
        if args.get("video_urls"):
            inp["video_urls"] = list(args["video_urls"])
        if args.get("audio_urls"):
            inp["audio_urls"] = list(args["audio_urls"])
    return inp


def run_piapi(mode: str, fast: bool, args: dict, api_key: str,
              emit_progress, is_cancelled) -> dict:
    """Crée la tâche Seedance 2 chez PiAPI puis attend le résultat.

    Retourne un dict au MÊME format que le résultat fal de run_real :
    {"request_id": …, "video": {"url": …}, "seed": 0}. Lève RuntimeError
    avec un message humain en cas d'échec (affiché via humanize_api_error)."""
    payload = {
        "model":     "seedance",
        "task_type": "seedance-2-fast" if fast else "seedance-2",
        "input":     build_input(mode, args),
    }

    emit_progress(14, "Envoi à PiAPI (Seedance 2)…")
    try:
        r = requests.post(_BASE, headers=_headers(api_key), json=payload,
                          timeout=45)
    except requests.RequestException as e:
        raise RuntimeError(f"PiAPI injoignable : {e}")
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

    # ── Polling ───────────────────────────────────────────────────────────────
    started = time.monotonic()
    pct = 16
    while True:
        if is_cancelled():
            return {}
        if time.monotonic() - started > _TIMEOUT_S:
            raise RuntimeError("PiAPI : délai dépassé (12 min) — la tâche "
                               f"{task_id} n'a pas abouti.")
        time.sleep(_POLL_EVERY_S)
        try:
            rr = requests.get(f"{_BASE}/{task_id}", headers=_headers(api_key),
                              timeout=30)
            d = (rr.json().get("data") or {}) if rr.ok else {}
        except (requests.RequestException, ValueError):
            continue  # erreur réseau passagère → on repollera
        status = (d.get("status") or "").lower()
        if status == "completed":
            video_url = (d.get("output") or {}).get("video", "")
            if not video_url:
                raise RuntimeError("PiAPI : tâche terminée mais sans vidéo "
                                   "dans la réponse.")
            return {"request_id": task_id, "video": {"url": video_url},
                    "seed": 0}
        if status == "failed":
            _err = ((d.get("error") or {}).get("message")
                    if isinstance(d.get("error"), dict) else d.get("error"))
            raise RuntimeError(f"PiAPI : génération échouée — "
                               f"{_err or 'raison non précisée'}")
        pct = min(pct + 3, 88)
        _lbl = {"pending": "En file d'attente PiAPI…",
                "staged": "Préparation PiAPI…",
                "processing": "Génération en cours (PiAPI)…"}.get(
                    status, "Génération en cours (PiAPI)…")
        emit_progress(pct, _lbl)
