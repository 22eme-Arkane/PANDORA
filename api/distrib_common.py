"""
api/distrib_common.py — Outils communs aux distributeurs vidéo alternatifs
(BytePlus, Runware, Segmind ; PiAPI garde sa boucle historique).

Tous suivent le même moule asynchrone que fal : une requête crée une tâche,
puis on interroge son état jusqu'à un statut final. Le rappel HTTP (webhook)
proposé partout est inutile à un logiciel de bureau sans adresse publique.

Rapport de référence : reports/Distributeurs vidéo IA low cost.md (04/10/2026).
"""
from __future__ import annotations

import time

import requests

#: Un plan de 30 s en 1080p a été observé jusqu'à ~13,5 min chez les
#: revendeurs (Segmind : 123 à 808 s). 25 min laisse de la marge sans
#: confondre une file chargée avec un échec.
POLL_TIMEOUT_S = 25 * 60

_VIDEO_EXT = (".mp4", ".mov", ".webm", ".m4v")


def headers_json(**extra) -> dict:
    h = {"Content-Type": "application/json"}
    h.update({k: v for k, v in extra.items() if v})
    return h


def first_video_url(obj) -> str:
    """Première URL vidéo trouvée dans une réponse JSON, quelle que soit sa
    profondeur (les distributeurs ne rangent pas la vidéo au même endroit).
    Priorité aux URL qui se terminent par une extension vidéo."""
    found: list[str] = []

    def _walk(o):
        if isinstance(o, str):
            if o.startswith(("http://", "https://")):
                found.append(o)
        elif isinstance(o, dict):
            for v in o.values():
                _walk(v)
        elif isinstance(o, (list, tuple)):
            for v in o:
                _walk(v)

    _walk(obj)
    for u in found:
        if u.split("?", 1)[0].lower().endswith(_VIDEO_EXT):
            return u
    return found[0] if found else ""


def http_error_message(provider: str, resp) -> str:
    """Message lisible d'une réponse HTTP en erreur : on garde le code ET le
    texte du distributeur — c'est lui qui dit pourquoi (modération, crédits,
    paramètre refusé)."""
    detail = ""
    try:
        data = resp.json()
        err = data.get("error") if isinstance(data, dict) else None
        if isinstance(err, dict):
            detail = " — ".join(x for x in (str(err.get("code") or ""),
                                            str(err.get("message") or "")) if x)
        elif isinstance(data, dict):
            errs = data.get("errors")
            if isinstance(errs, list) and errs and isinstance(errs[0], dict):
                detail = " — ".join(x for x in (str(errs[0].get("code") or ""),
                                                str(errs[0].get("message") or "")) if x)
            detail = detail or str(data.get("message") or data.get("detail") or "")
    except ValueError:
        pass
    detail = detail or (resp.text or "")[:300]
    if resp.status_code in (401, 403):
        return (f"Clé {provider} refusée ({resp.status_code}) — vérifie-la dans "
                f"Paramètres. {detail}").strip()
    if resp.status_code == 429:
        return f"{provider} : trop de requêtes (429) — réessaie dans un instant. {detail}".strip()
    return f"{provider} a refusé la requête ({resp.status_code}) : {detail}".strip()


def poll_until(check, emit_progress, is_cancelled, label: str,
               every_s: float = 10.0, timeout_s: float = POLL_TIMEOUT_S,
               start_pct: int = 16):
    """Interroge jusqu'à un état final.

    `check()` rend ("done", valeur) | ("fail", message) | ("wait", libellé).
    Rend la valeur finale, ou None si l'utilisateur a annulé. Une erreur
    réseau passagère ne fait PAS échouer la génération : on réinterroge."""
    started = time.monotonic()
    pct = start_pct
    while True:
        if is_cancelled():
            return None
        if time.monotonic() - started > timeout_s:
            raise RuntimeError(f"{label} : délai dépassé ({int(timeout_s // 60)} min) — "
                               "la tâche n'a pas abouti.")
        time.sleep(every_s)
        if is_cancelled():
            return None
        try:
            state, value = check()
        except (requests.RequestException, ValueError):
            continue
        if state == "done":
            return value
        if state == "fail":
            raise RuntimeError(value)
        pct = min(pct + 2, 90)
        emit_progress(pct, value or f"Génération en cours ({label})…")


def probe_key(provider: str, url: str, headers: dict, body) -> tuple[bool, str]:
    """Teste une clé SANS rien générer : une création au corps invalide doit
    répondre 4xx de validation (clé acceptée) et non 401/403 (clé refusée).
    Aucune tâche n'est créée, donc aucun coût."""
    try:
        r = requests.post(url, headers=headers, json=body, timeout=15)
    except requests.RequestException as e:
        return False, f"{provider} injoignable : {e}"
    if r.status_code in (401, 403):
        return False, f"Clé {provider} refusée ({r.status_code}) — vérifie la clé."
    return True, f"Connexion {provider} OK — clé acceptée."
