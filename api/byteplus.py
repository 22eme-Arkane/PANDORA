"""
api/byteplus.py — Seedance en DIRECT chez ByteDance (BytePlus ModelArk).

Tarif officiel, environ la MOITIÉ de fal (relevé du 04/10/2026, rapport
« Distributeurs vidéo IA low cost ») : un plan Seedance 2.5 de 30 s coûte
3,08 $ / 6,93 $ / 17,06 $ HT en 480p / 720p / 1080p, contre 6,60 / 14,19 /
34,92 $ chez fal. Chaque utilisateur ouvre SON compte BytePlus et colle SA
clé : il est client direct de ByteDance, PANDORA reste un logiciel.

Contrat (docs.byteplus.com/en/docs/modelark/create-video-generation-task-api) :
  POST https://ark.ap-southeast.bytepluses.com/api/v3/contents/generations/tasks
       en-tête Authorization: Bearer <clé>
       corps {model, content:[{type:"text"}, {type:"image_url", role}, …],
              resolution, ratio, duration, generate_audio, watermark, …}
  GET  …/tasks/{id} → status queued | running | succeeded | failed |
       cancelled | expired ; vidéo dans content.video_url (24 h, et 100
       téléchargements au plus en 2.5) ; usage.completion_tokens = jetons
       réellement facturés.

Pièges encodés ici :
  · ratio « adaptive » OBLIGATOIRE en image→vidéo, prolongation et montage :
    « 16:9 » y fait échouer la tâche après son démarrage ;
  · durée TOUJOURS explicite : le défaut −1 laisse le modèle choisir — et
    facturer — la durée ;
  · seed transmise en 2.5 seulement (champ `seed`, renvoyé par chaque tâche ;
    jamais en 2.0, non documentée) — pas encore vérifiée en réel le 05/10/2026 :
    la validation est stricte, un refus est gratuit et nommé ;
  · un refus de modération n'est PAS facturé ; le même filtre que chez fal
    s'applique (visages réels, droits d'auteur jugés sur la vidéo produite) ;
  · une clé valide ne suffit PAS : chaque modèle doit être ACTIVÉ dans la
    console, ce que BytePlus n'autorise qu'à partir de 30 $ de crédit (ou un
    AI Savings Plan / pack de ressources de 30 $). Sinon 404 « ModelNotOpen »
    sur chaque plan — cas réel de Matthieu le 05/10/2026, dont la clé passait
    le test. `probe_model` le vérifie gratuitement.
"""
from __future__ import annotations

import re as _re

import requests

from api.distrib_common import (connection_message, first_video_url, headers_json,
                                http_error_message, poll_until, probe_key)

PROVIDER = "BytePlus"
_BASE = "https://ark.ap-southeast.bytepluses.com/api/v3/contents/generations/tasks"

#: Clé moteur PANDORA → identifiant de modèle ModelArk (liste des modèles,
#: relevée le 04/10/2026).
MODEL_IDS = {
    "seedance-2.5":      "dreamina-seedance-2-5-260628",
    "seedance-2.0":      "dreamina-seedance-2-0-260128",
    "seedance-2.0-fast": "dreamina-seedance-2-0-fast-260128",
    "seedance-2.0-mini": "dreamina-seedance-2-0-mini-260615",
}

#: $ par MILLION de jetons (grille du 28/09/2026) : (sans vidéo d'entrée,
#: avec vidéo d'entrée), par moteur puis résolution.
_TOKEN_PRICE = {
    "seedance-2.5":      {"480p": (10.7, 6.4), "720p": (10.7, 6.4), "1080p": (11.7, 7.0)},
    "seedance-2.0":      {"480p": (7.0, 4.3), "720p": (7.0, 4.3), "1080p": (7.7, 4.7),
                          "4k": (4.0, 2.4)},
    "seedance-2.0-fast": {"480p": (5.6, 3.3), "720p": (5.6, 3.3)},
    "seedance-2.0-mini": {"480p": (3.5, 2.1), "720p": (3.5, 2.1)},
}

#: Plafonds de références par famille (images, vidéos, audios).
_REF_CAPS = {"seedance-2.5": (30, 10, 10)}
_REF_CAPS_2_0 = (9, 3, 3)

_POLL_EVERY_S = 15          # 20 interrogations/s autorisées ; le script officiel attend 30 s
_EXPIRES_AFTER_S = 3600     # tâche abandonnée par BytePlus si elle n'a pas démarré en 1 h


#: Page de la console où l'on active les modèles, et conditions de BytePlus
#: (doc « Activate, use, and cancel Dreamina Seedance 2.5 and 2.0 series
#: models », mise à jour du 28/09/2026).
ACTIVATION_URL = ("https://ai.byteplus.com/ark/region:ap-southeast-1/openManagement"
                  "?LLM=%7B%7D&advancedActiveKey=model")
NOT_ACTIVATED = (
    "Seedance n'est pas activé sur ton compte BytePlus. BytePlus exige au moins 30 $ "
    "de crédit (ou un AI Savings Plan, ou un pack de ressources de 30 $), puis "
    "l'activation des modèles dans la console ModelArk (« Model activation »).")
#: Raison courte, affichée quand l'ordre de priorité passe au distributeur suivant.
NOT_ACTIVATED_SHORT = "Seedance non activé sur ton compte (30 $ de crédit, puis « Model activation »)"


def _headers(api_key: str) -> dict:
    return headers_json(Authorization=f"Bearer {api_key.strip()}")


def _error_code(resp) -> str:
    try:
        data = resp.json()
    except ValueError:
        return ""
    err = data.get("error") if isinstance(data, dict) else None
    return str((err or {}).get("code") or "") if isinstance(err, dict) else ""


def probe_model(api_key: str, engine: str) -> tuple[bool | None, str]:
    """Le modèle `engine` est-il ACTIVÉ sur ce compte ? (True | False | None =
    on ne sait pas, raison). Sonde GRATUITE : le corps est invalide à plusieurs
    titres (contenu vide, résolution, ratio et durée hors grille), si bien
    qu'aucune tâche ne peut naître ; BytePlus contrôle l'activation AVANT de
    lire le corps (vérifié le 05/10/2026 : 404 « ModelNotOpen » sur un compte
    sans activation). Un modèle activé répond donc 400 de validation. Si une
    tâche apparaissait malgré tout, elle serait annulée sur-le-champ."""
    model_id = MODEL_IDS.get(engine)
    if not model_id or not (api_key or "").strip():
        return None, ""
    body = {"model": model_id, "content": [],
            "resolution": "pandora-sonde", "ratio": "pandora-sonde", "duration": 0}
    try:
        r = requests.post(_BASE, headers=_headers(api_key), json=body, timeout=15)
    except requests.RequestException:
        return None, ""
    try:
        task_id = (r.json() or {}).get("id") if r.status_code < 400 else None
    except (ValueError, AttributeError):
        task_id = None
    if task_id:
        try:
            requests.delete(f"{_BASE}/{task_id}", headers=_headers(api_key), timeout=15)
        except requests.RequestException:
            pass
        return True, ""
    if r.status_code == 401:
        return False, "clé BytePlus refusée"
    if _error_code(r) == "ModelNotOpen":
        return False, NOT_ACTIVATED_SHORT
    if r.status_code in (400, 422):
        return True, ""
    return None, ""


def test_key(api_key: str) -> tuple[bool | None, str]:
    """Clé valide = création refusée pour corps invalide (4xx), pas 401/403.
    Puis les modèles : une clé acceptée sans Seedance activé rend None (« clé
    bonne, compte pas prêt ») — le test disait « OK » alors qu'aucun plan ne
    pouvait partir (05/10/2026)."""
    ok, msg = probe_key(PROVIDER, _BASE, _headers(api_key), {})
    if not ok:
        return ok, msg
    states = {e: probe_model(api_key, e)[0] for e in ("seedance-2.5", "seedance-2.0")}

    def _names(flag):
        return " et ".join(f"Seedance {e.split('-')[1]}" for e, v in states.items() if v is flag)
    if all(v is False for v in states.values()):
        return None, "Clé BytePlus acceptée. " + NOT_ACTIVATED
    if any(v is True for v in states.values()):
        text = f"Connexion BytePlus OK — clé acceptée. Activé : {_names(True)}."
        if any(v is False for v in states.values()):
            text += f" Non activé : {_names(False)} (« Model activation » dans la console)."
        return True, text
    return True, msg


def _ratio(value: str) -> str:
    v = (value or "").strip().lower()
    return "adaptive" if v in ("", "auto", "adaptive") else v


def build_body(mode: str, model: str, args: dict) -> dict:
    """Traduit les `args` préparés par api/real.py (format fal) vers le corps
    ModelArk. Ne lève jamais : les champs absents sont ignorés."""
    engine = model if model in MODEL_IDS else "seedance-2.0"
    max_img, max_vid, max_aud = _REF_CAPS.get(engine, _REF_CAPS_2_0)
    content: list[dict] = []
    if args.get("prompt"):
        content.append({"type": "text", "text": args["prompt"]})

    body: dict = {
        "model":          MODEL_IDS[engine],
        "resolution":     (args.get("resolution") or "720p").lower(),
        "generate_audio": bool(args.get("generate_audio", True)),
        "watermark":      False,
        "execution_expires_after": _EXPIRES_AFTER_S,
    }
    try:
        body["duration"] = int(args.get("duration", 5))
    except (TypeError, ValueError):
        body["duration"] = 5

    if mode == "i2v":
        if args.get("image_url"):
            content.append({"type": "image_url", "image_url": {"url": args["image_url"]},
                            "role": "first_frame"})
        if args.get("end_image_url"):
            content.append({"type": "image_url", "image_url": {"url": args["end_image_url"]},
                            "role": "last_frame"})
        body["ratio"] = "adaptive"     # « 16:9 » ferait échouer la tâche
    else:
        for u in list(args.get("image_urls") or [])[:max_img]:
            content.append({"type": "image_url", "image_url": {"url": u},
                            "role": "reference_image"})
        for u in list(args.get("video_urls") or [])[:max_vid]:
            content.append({"type": "video_url", "video_url": {"url": u},
                            "role": "reference_video"})
        for u in list(args.get("audio_urls") or [])[:max_aud]:
            content.append({"type": "audio_url", "audio_url": {"url": u},
                            "role": "reference_audio"})
        if mode == "ext":
            body["ratio"] = "adaptive"
            # Le type de tâche n'existe qu'en 2.5 (doc ModelArk) ; la 2.0
            # prolonge à partir de la vidéo de référence, comme chez fal.
            if engine == "seedance-2.5":
                editing = (args.get("task") == "editing")
                body["omni_reference_task_type"] = "edit" if editing else "extend"
                if editing:
                    body["duration"] = -1   # la modification garde la durée du clip source
        else:
            body["ratio"] = _ratio(args.get("aspect_ratio", "16:9"))
    # Seed (05/10/2026) : la 2.5 la lit — champ `seed` de l'API, renvoyé dans
    # chaque tâche. Elle part seulement quand PANDORA la demande (reprise d'un
    # plan, ADN visuel verrouillé) ; jamais en 2.0, non documentée pour cette série.
    seed = args.get("seed")
    if engine == "seedance-2.5" and isinstance(seed, int) and not isinstance(seed, bool) \
            and seed > 0:
        body["seed"] = seed
    body["content"] = content
    return body


def cost_from_usage(model: str, resolution: str, tokens, with_video: bool) -> float | None:
    """Coût réel (USD HT) à partir des jetons renvoyés par BytePlus."""
    try:
        t = float(tokens)
    except (TypeError, ValueError):
        return None
    rates = _TOKEN_PRICE.get(model, {}).get((resolution or "").lower())
    if not rates or t <= 0:
        return None
    return round(t * rates[1 if with_video else 0] / 1_000_000, 4)


def run(mode: str, model: str, args: dict, api_key: str,
        emit_progress, is_cancelled) -> dict:
    """Crée la tâche chez BytePlus puis attend le résultat.

    Rend le MÊME format que le résultat fal de run_real :
    {"request_id", "video": {"url"}, "seed", "cost_usd"}. Lève RuntimeError
    avec un message humain en cas d'échec."""
    body = build_body(mode, model, args)
    emit_progress(14, "Envoi à BytePlus ModelArk (officiel ByteDance)…")
    try:
        r = requests.post(_BASE, headers=_headers(api_key), json=body, timeout=60)
    except requests.RequestException as e:
        raise RuntimeError(connection_message(PROVIDER, e))
    if r.status_code >= 400:
        if _error_code(r) == "ModelNotOpen":
            # Retenu : le plan suivant passera directement au distributeur
            # suivant de l'ordre, sans redemander.
            try:
                from api.distrib_probe import note_byteplus_not_activated
                note_byteplus_not_activated(api_key, model)
            except Exception:
                pass
            raise RuntimeError(f"BytePlus : {NOT_ACTIVATED} Rien n'a été généré ni facturé.")
        if "seed" in body and _re.search(r"\bseed\b", r.text or "", _re.I):
            # La seed de la 2.5 n'avait jamais été essayée en réel : si BytePlus
            # la refuse, on le dit (« seedance » ne compte pas, d'où le \b).
            raise RuntimeError(
                f"BytePlus refuse la seed pour {model} : {http_error_message(PROVIDER, r)} "
                f"Rien n'a été généré ni facturé. Déverrouille l'ADN visuel (🔓) pour "
                f"générer sans seed.")
        raise RuntimeError(http_error_message(PROVIDER, r))
    try:
        task_id = (r.json() or {}).get("id", "")
    except ValueError:
        task_id = ""
    if not task_id:
        raise RuntimeError(f"BytePlus : réponse sans identifiant de tâche — {r.text[:200]}")

    _labels = {"queued": "En file d'attente BytePlus…",
               "running": "Génération en cours (BytePlus)…"}

    def _check():
        rr = requests.get(f"{_BASE}/{task_id}", headers=_headers(api_key), timeout=30)
        if rr.status_code >= 500:
            return "wait", "BytePlus répond lentement…"
        if rr.status_code >= 400:
            return "fail", http_error_message(PROVIDER, rr)
        d = rr.json() or {}
        status = (d.get("status") or "").lower()
        if status == "succeeded":
            return "done", d
        if status in ("failed", "cancelled", "expired"):
            err = d.get("error") or {}
            detail = " — ".join(x for x in (str(err.get("code") or ""),
                                            str(err.get("message") or "")) if x)
            return "fail", f"BytePlus : génération {status} — {detail or 'raison non précisée'}"
        return "wait", _labels.get(status, "Génération en cours (BytePlus)…")

    d = poll_until(_check, emit_progress, is_cancelled, PROVIDER, every_s=_POLL_EVERY_S)
    if d is None:
        return {}
    video_url = ((d.get("content") or {}).get("video_url")) or first_video_url(d.get("content"))
    if not video_url:
        raise RuntimeError("BytePlus : tâche terminée mais sans vidéo dans la réponse.")
    usage = d.get("usage") or {}
    cost = cost_from_usage(model, body.get("resolution", ""),
                           usage.get("completion_tokens") or usage.get("total_tokens"),
                           with_video=bool(args.get("video_urls")))
    return {"request_id": task_id, "video": {"url": video_url}, "seed": d.get("seed", 0) or 0,
            "cost_usd": cost}
