"""
api/distrib_probe.py — Ce que chaque distributeur peut RECEVOIR, vérifié sans
rien générer (sondes gratuites).

Deux faits suffisent, gardés 10 min en mémoire :
  · fal utilisable ? — jeton de dépôt fal (aucun fichier envoyé). Un compte
    fal bloqué faute de solde (« User is locked. Reason: Exhausted balance »,
    cas réel du 04/10/2026) ne peut ni générer, ni servir de relais ;
  · dépôt PiAPI ouvert ? — dépôt d'une image d'1 pixel (gratuit, effacée par
    PiAPI sous 24 h) ; refusé hors abonnement Creator.
D'où, pour chaque distributeur (can_receive) :
  · fal      : utilisable seulement si son compte l'est ;
  · BytePlus : images et sons DANS la requête ; une vidéo exige le relais fal ;
  · Runware  : images dans la requête ; vidéo / son par le relais fal ;
  · PiAPI    : tout fichier exige son dépôt OU le relais fal.

core/media_provider.route() s'en sert pour passer au distributeur suivant ;
le Studio, pour griser ce qu'aucun distributeur activé ne peut faire.
"""
from __future__ import annotations

import io
import time

import requests
from PyQt6.QtCore import QThread, pyqtSignal

_TTL_S = 600
_CACHE: dict[tuple, tuple[float, tuple]] = {}
_FAL_TOKEN_URL = "https://rest.fal.ai/storage/auth/token?storage_type=fal-cdn-v3"


def _cfg() -> dict:
    from core.config import load_config
    return load_config()


def _get(name: str, key: str):
    hit = _CACHE.get((name, key))
    if hit and time.monotonic() - hit[0] < _TTL_S:
        return hit[1]
    return None


def _put(name: str, key: str, value: tuple):
    # « On ne sait pas » (réseau) n'est pas retenu : on réessaiera.
    if value[0] is not None:
        _CACHE[(name, key)] = (time.monotonic(), value)
    return value


def fal_state(fal_key: str, network: bool = True) -> tuple[bool | None, str]:
    """(utilisable, raison) du compte fal ; None = inconnu."""
    if not fal_key:
        return False, "pas de clé fal.ai"
    known = _get("fal", fal_key)
    if known is not None or not network:
        return known or (None, "")
    try:
        r = requests.post(_FAL_TOKEN_URL, json={}, timeout=15,
                          headers={"Authorization": f"Key {fal_key}",
                                   "Content-Type": "application/json"})
    except requests.RequestException:
        return None, "fal.ai injoignable"
    if r.status_code < 400:
        return _put("fal", fal_key, (True, ""))
    low = (r.text or "").lower()
    if "exhausted balance" in low or "user is locked" in low:
        reason = "solde fal épuisé (quelques dollars rechargés sur fal.ai suffisent)"
    elif r.status_code in (401, 403):
        reason = "clé fal.ai refusée"
    else:
        reason = f"fal.ai a répondu {r.status_code}"
    return _put("fal", fal_key, (False, reason))


def piapi_upload_state(piapi_key: str, network: bool = True) -> tuple[bool | None, str]:
    """(dépôt ouvert, raison) du compte PiAPI ; None = inconnu."""
    from api import distrib_upload as du
    if not piapi_key:
        return False, "pas de clé PiAPI"
    if du._PIAPI_PLAN_REFUSED:
        return False, du._PIAPI_PLAN_REFUSED[0]
    known = _get("piapi_upload", piapi_key)
    if known is not None or not network:
        return known or (None, "")
    from PIL import Image
    buf = io.BytesIO()
    Image.new("RGB", (1, 1), (12, 14, 26)).save(buf, format="PNG")
    try:
        du.piapi_post("pandora_sonde.png", buf.getvalue(), piapi_key, timeout=20)
        return _put("piapi_upload", piapi_key, (True, ""))
    except du.UploadError as e:
        msg = str(e)
        if "injoignable" in msg:
            return None, msg
        return _put("piapi_upload", piapi_key, (False, msg))


def can_receive(provider: str, needs=(), network: bool = True,
                cfg: dict | None = None) -> tuple[bool | None, str]:
    """Ce distributeur peut-il servir une demande qui envoie ces fichiers ?
    (True | False | None = on ne sait pas, raison lisible)."""
    cfg = _cfg() if cfg is None else cfg
    needs = set(needs or ())
    fal_key = (cfg.get("api_key") or "").strip()

    def relay():
        ok, why = fal_state(fal_key, network)
        return (False, f"relais fal.ai impossible : {why}") if ok is False else (ok, why)

    if provider == "fal":
        ok, why = fal_state(fal_key, network)
        return (False, f"compte bloqué : {why}") if ok is False else (ok, why)
    if provider == "byteplus":
        return relay() if "video" in needs else (True, "")
    if provider == "runware":
        return relay() if ({"video", "audio"} & needs) else (True, "")
    if provider == "piapi":
        if not needs:
            return True, ""
        ok1, why1 = piapi_upload_state((cfg.get("piapi_key") or "").strip(), network)
        if ok1:
            return True, ""
        ok2, why2 = relay()
        if ok2:
            return True, ""
        if ok1 is False and ok2 is False:
            return False, "ne peut pas recevoir de fichiers (" + " ; ".join(
                w for w in (why1, why2) if w) + ")"
        return None, ""
    return True, ""


def needs_probe(cfg: dict | None = None) -> bool:
    """Un fait utile n'est pas encore connu (le Studio lance alors la sonde)."""
    cfg = _cfg() if cfg is None else cfg
    fal_key = (cfg.get("api_key") or "").strip()
    piapi_key = (cfg.get("piapi_key") or "").strip()
    if fal_key and _get("fal", fal_key) is None:
        return True
    from api import distrib_upload as du
    return bool(piapi_key) and not du._PIAPI_PLAN_REFUSED and _get("piapi_upload", piapi_key) is None


def facts(network: bool = True, cfg: dict | None = None) -> dict:
    """Les deux faits, pour l'affichage des Paramètres."""
    cfg = _cfg() if cfg is None else cfg
    return {"fal": fal_state((cfg.get("api_key") or "").strip(), network),
            "piapi_upload": piapi_upload_state((cfg.get("piapi_key") or "").strip(), network)}


def forget():
    """Oublie les résultats (clé changée, solde rechargé, « Vérifier »)."""
    _CACHE.clear()
    try:
        from api import distrib_upload as du
        du._PIAPI_PLAN_REFUSED.clear()
    except Exception:
        pass


#: Fils de sonde EN COURS, retenus ici jusqu'à leur fin : un QThread détruit
#: avec la fenêtre qui l'a lancé fait avorter le processus (« QThread:
#: Destroyed while thread is still running », 0xC0000409 — vécu au harnais
#: le 04/10/2026).
_RUNNING: list = []


def keep_alive(worker: QThread) -> QThread:
    """Retient `worker` jusqu'à la fin de son exécution (signal natif finished)."""
    _RUNNING.append(worker)

    def _drop(w=worker):
        if w in _RUNNING:
            _RUNNING.remove(w)
    worker.finished.connect(_drop)
    return worker


class FactsProbe(QThread):
    """Établit les deux faits en arrière-plan ; `done(faits)`."""
    done = pyqtSignal(dict)

    def run(self):
        try:
            res = facts(network=True)
        except Exception as e:
            res = {"fal": (None, str(e)[:120]), "piapi_upload": (None, "")}
        self.done.emit(res)
