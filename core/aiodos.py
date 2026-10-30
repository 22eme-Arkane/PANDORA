"""core/aiodos.py — PANDORA × AIODOS : la puissance de calcul mise en commun.

AIODOS (22eme Arkane) relie par Internet les machines de personnes qui ne se
connaissent pas pour mettre leur puissance en commun ; le réseau local et les
machines de l'utilisateur viennent ensuite. Les travaux de PANDORA, eux, restent
là où PANDORA le demande (réglage « Calcul » ; références et clips jamais
ailleurs que sur ce PC et mes machines). Demande de Matthieu
(22/10/2026) : « intégrer AIODOS à PANDORA, qui permet de partager la puissance
et donc de créer des images ou des vidéos avec le soutien de plusieurs machines.
AIODOS n'est pas fini, et doit se mettre à jour même une fois intégré ».

D'où le choix : PANDORA n'EMBARQUE PAS AIODOS. Il parle à l'AIODOS installé, qui
continue de se mettre à jour seul (versions signées, transmises de machine en
machine), par sa passerelle locale 127.0.0.1:11435, avec le client officiel
aiodos-client (Apache-2.0, copié dans aiodos_client/ ; tools/update_aiodos_client.py
le rafraîchit depuis le dépôt d'AIODOS). Le client lit ce qu'AIODOS annonce
savoir faire (`features`) et lève NotSupported pour le reste : une mise à jour
d'AIODOS ne peut pas casser PANDORA.

Recette suivie : docs/integrer-aiodos.md § 13 du dépôt AIODOS.
  · la clé de l'appli dans %LOCALAPPDATA%\\PANDORA\\aiodos.key, chiffrée par
    DPAPI (fichier en 0600 hors de Windows) ; config.json ne garde que
    `aiodos_url` (vide = découverte automatique) et `aiodos_where` ;
  · l'accès se demande sur un CLIC (« Se connecter à AIODOS »), jamais au
    lancement de PANDORA ;
  · les erreurs se traitent par leur code, le message (en français ou en
    anglais) est fait pour l'utilisateur.

Aucun Qt ici : les appels bloquants se font depuis des QThread (ui/aiodos_panel).
"""
from __future__ import annotations

import os
import sys
import threading
import time

APP_NAME = "PANDORA"
APP_ID = "arkane.pandora"
#: Droits demandés : la conversation (IA texte) et les travaux ComfyUI.
SCOPES = ("chat", "engines:comfyui")
#: Ce que chaque droit permet, dit à l'utilisateur (droit manquant).
SCOPE_LABELS = {"chat": "IA texte", "engines:comfyui": "images et vidéos (gabarits ComfyUI)"}
#: Les cercles de calcul, dits à l'utilisateur (« friend » : nom d'un lieu de travail).
PLACE_NAMES = {"here": "ce PC", "mine": "mes machines", "friends": "amis", "friend": "amis",
               "public": "réseau public"}
#: Cercles de calcul demandés par défaut : ce PC et mes machines. Les amis et le
#: réseau public ne reçoivent jamais les fiches ni les visages de PANDORA.
WHERE_DEFAULT = ("here", "mine")
PURPOSE = ("Calculer les images et les vidéos de PANDORA (gabarits ComfyUI) sur tes "
           "machines, et traduire ou composer ses prompts.")

#: Réglage « Calcul » des gabarits ComfyUI : ce PC (ComfyUI local, comme avant),
#: mes machines par AIODOS, ou le réseau public d'AIODOS (27/10/2026 : les lieux
#: cochés dans l'onglet AIODOS, réseau public compris).
COMPUTE_LOCAL = "local"
COMPUTE_AIODOS = "aiodos"
COMPUTE_PUBLIC = "aiodos_public"
COMPUTE_MODES = (COMPUTE_LOCAL, COMPUTE_AIODOS, COMPUTE_PUBLIC)
COMPUTE_KEY = "comfy_compute"
#: Où télécharger AIODOS (bouton « Installer AIODOS » de l'onglet quand il manque).
#: ⚠ Le dépôt n'est pas encore public (27/10/2026) : Matthieu préviendra ; vérifier
#: alors que ce lien mène bien à la dernière version.
DOWNLOAD_URL = "https://github.com/AIODOS/aiodos/releases/latest"

_client = None
_client_sig = None
_lock = threading.Lock()
_status_cache: tuple[float, object] | None = None


# ── Réglages ─────────────────────────────────────────────────────────────────

def _cfg() -> dict:
    try:
        from core.config import load_config
        return load_config() or {}
    except Exception:
        return {}


def key_path() -> str:
    """Le coffre de la clé : HORS de config.json et du dossier de données copié
    entre machines (jamais dans Documents ni OneDrive)."""
    if sys.platform == "darwin":
        root = os.path.expanduser("~/Library/Application Support/PANDORA")
    else:
        root = os.path.join(os.environ.get("LOCALAPPDATA") or os.path.expanduser("~"), "PANDORA")
    return os.path.join(root, "aiodos.key")


def where() -> list[str]:
    raw = _cfg().get("aiodos_where")
    if isinstance(raw, (list, tuple)):
        circles = [str(c) for c in raw if str(c) in ("here", "mine", "friends", "public")]
        if circles:
            return circles
    return list(WHERE_DEFAULT)


def default_compute_mode(cfg: dict | None = None) -> str:
    """Sans choix enregistré : le réseau public d'AIODOS s'il est coché dans
    l'onglet AIODOS (Matthieu 27/10/2026 : « c'est celui-là qui doit être par
    défaut, pas ce PC »), sinon ce PC."""
    raw = (cfg if cfg is not None else _cfg()).get("aiodos_where")
    return (COMPUTE_PUBLIC if isinstance(raw, (list, tuple)) and "public" in raw
            else COMPUTE_LOCAL)


def compute_mode() -> str:
    cfg = _cfg()
    mode = str(cfg.get(COMPUTE_KEY) or "")
    return mode if mode in COMPUTE_MODES else default_compute_mode(cfg)


def uses_aiodos(mode: str | None = None) -> bool:
    """Le calcul passe-t-il par AIODOS (mes machines ou réseau public) ?"""
    return (mode or compute_mode()) in (COMPUTE_AIODOS, COMPUTE_PUBLIC)


def job_where(mode: str | None = None):
    """Les cercles d'un travail (X-Aiodos-Where, qui resserre sans jamais élargir
    l'accord). « Mes machines » : ce PC et mes machines, dans ce que l'accord
    permet. « Réseau public » : None = tout ce que l'accord permet (amis et
    public compris) — AIODOS laisse de côté les cercles qu'il ne sert pas
    encore aux travaux ComfyUI, et le dit (`where_effective`, `where_reason`,
    montrés après l'envoi). Les travaux sensibles restent toujours chez moi
    (client)."""
    if (mode or compute_mode()) != COMPUTE_AIODOS:
        return None
    granted = set(getattr(status(), "where", ()) or ())
    circles = [c for c in ("here", "mine") if not granted or c in granted]
    return circles or None


def places_text(circles) -> str:
    """« ce PC + mes machines » (traduit) ; « — » sans cercle."""
    from core.i18n import translate as _t
    names = [_t(PLACE_NAMES.get(str(c), str(c))) for c in circles or ()]
    return " + ".join(dict.fromkeys(names)) or "—"


#: Ce qu'AIODOS a dit du réseau public pour les gabarits ComfyUI, lu dans
#: `where_effective` d'un travail lancé en « Réseau public » : None (rien vu
#: encore), False (laissé de côté), True (il y a calculé). Tant qu'il ne l'a pas
#: pris, le choix « Réseau public » porte la mention « pas encore pour ComfyUI ».
_PUBLIC_COMFY = {"served": None}


def note_where_effective(circles) -> None:
    """Retient ce qu'AIODOS a retenu pour un travail lancé en « Réseau public »
    (jamais pour un travail sensible : celui-là reste chez moi de toute façon)."""
    _PUBLIC_COMFY["served"] = "public" in {str(c) for c in circles or ()}


def public_comfy_served() -> bool:
    """AIODOS a-t-il déjà fait calculer un gabarit par le réseau public ?"""
    return _PUBLIC_COMFY["served"] is True


def set_compute_mode(mode: str) -> None:
    """Enregistre le réglage « Calcul ». save_config REMPLACE tout le fichier :
    on repart toujours de la configuration complète."""
    if mode not in COMPUTE_MODES:
        raise ValueError(mode)
    from core.config import load_config, save_config
    cfg = load_config()
    if cfg.get(COMPUTE_KEY) == mode:
        return
    cfg[COMPUTE_KEY] = mode
    save_config(cfg)


# ── Client ───────────────────────────────────────────────────────────────────

def _lang() -> str:
    try:
        from core.i18n import get_lang
        return "en" if get_lang() == "en" else "fr"
    except Exception:
        return "fr"


def _keystore():
    from aiodos_client import Keystore
    if os.name == "nt":
        return Keystore.dpapi(key_path())
    return Keystore.file(key_path())


def client():
    """Le client AIODOS de PANDORA (un seul, partagé entre threads : il n'a pas
    d'état global). Reconstruit si l'adresse ou la langue changent."""
    global _client, _client_sig
    from core.version import VERSION
    url = (_cfg().get("aiodos_url") or "").strip() or None
    sig = (url, _lang())
    with _lock:
        if _client is None or _client_sig != sig:
            from aiodos_client import Aiodos
            _client = Aiodos(app=APP_NAME, app_id=APP_ID, version=VERSION, lang=sig[1],
                             keystore=_keystore(), url=url)
            _client_sig = sig
        return _client


def reset() -> None:
    """Oublie le client et l'état en cache (changement de réglage, essais)."""
    global _client, _client_sig, _status_cache
    with _lock:
        _client = None
        _client_sig = None
        _status_cache = None


def status(max_age: float = 4.0):
    """L'état d'AIODOS pour PANDORA (aiodos_client.Status) — ne lève jamais.
    Gardé `max_age` secondes : les menus le consultent souvent."""
    global _status_cache
    now = time.monotonic()
    cached = _status_cache
    if cached and now - cached[0] < max_age:
        return cached[1]
    try:
        st = client().status()
    except Exception as e:                     # client introuvable, réglage faux…
        from types import SimpleNamespace
        st = SimpleNamespace(state="not_installed", message=f"AIODOS : {e}", features=(),
                             scopes=(), where=(), version=None, user_code=None)
    _status_cache = (now, st)
    return st


def forget_status() -> None:
    global _status_cache
    _status_cache = None


def is_installed() -> bool:
    return status().state != "not_installed"


def ready_for_comfy() -> tuple[bool, str]:
    """AIODOS peut-il calculer un gabarit ComfyUI de PANDORA ? (oui, "") ou
    (non, la raison lisible avec le geste qui la règle)."""
    from core.i18n import translate as _t
    st = status()
    if st.state != "ready":
        return False, _t("AIODOS n'est pas prêt : {message} Paramètres → AIODOS.").format(
            message=(st.message or st.state).rstrip(".") + ".")
    feats = set(st.features or ())
    if "engines.comfyui" not in feats or "jobs" not in feats:
        return False, _t("Cette version d'AIODOS ne calcule pas encore les gabarits ComfyUI : "
                         "laissez-la se mettre à jour, ou choisissez « Calcul : Ce PC ».")
    if "engines:comfyui" not in set(st.scopes or ()):
        return False, _t("PANDORA n'a pas le droit de faire calculer ses gabarits par AIODOS : "
                         "Paramètres → AIODOS → « Demander l'accès manquant ».")
    return True, ""


def ready_for_chat() -> tuple[bool, str]:
    from core.i18n import translate as _t
    st = status()
    if st.state != "ready":
        return False, _t("AIODOS n'est pas prêt : {message} Paramètres → AIODOS.").format(
            message=(st.message or st.state).rstrip(".") + ".")
    if "chat" not in set(st.scopes or ()):
        return False, _t("PANDORA n'a pas le droit de converser avec AIODOS : Paramètres → AIODOS "
                         "→ « Demander l'accès manquant ».")
    return True, ""


def missing_scopes(st=None) -> list[str]:
    """Les droits de SCOPES que l'accès actuel n'a pas — l'utilisateur a pu en
    décocher sur la carte d'accord d'AIODOS (par exemple `engines:comfyui`).
    [] si PANDORA n'est pas connecté. Le même `connect()` les redemande : la
    carte d'AIODOS montre la différence, la même clé les reçoit."""
    st = st if st is not None else status()
    if getattr(st, "state", None) != "ready":
        return []
    have = set(getattr(st, "scopes", ()) or ())
    return [s for s in SCOPES if s not in have]


def where_differs(chosen, st=None) -> bool:
    """Les lieux cochés dans PANDORA diffèrent-ils de ceux de l'accès déjà donné ?
    Ni `connect()` (qui rend l'accès actuel quand les droits y sont), ni une
    demande de droits en plus ne changent les lieux d'un accès existant : il faut
    « Se déconnecter », puis « Se connecter à AIODOS »."""
    st = st if st is not None else status()
    if getattr(st, "state", None) != "ready":
        return False
    granted = {str(c) for c in getattr(st, "where", ()) or ()}
    return bool(granted) and {str(c) for c in chosen or ()} != granted


# ── Accès (appelés depuis un QThread : bloquants) ────────────────────────────

def launch(cancel=None):
    """Lance AIODOS (sur un clic de l'utilisateur seulement) ; rend l'état."""
    st = client().launch(cancel=cancel)
    forget_status()
    return st


def connect(on_code=None, cancel=None):
    """Demande l'accès : AIODOS montre une carte avec le même code à 6 chiffres
    que PANDORA (`on_code`), l'utilisateur autorise ou refuse. Rend l'état."""
    result = client().connect(scopes=list(SCOPES), where=where(), purpose=PURPOSE,
                              on_code=on_code, cancel=cancel)
    forget_status()
    return result


def disconnect() -> None:
    try:
        client().disconnect()
    finally:
        forget_status()


# ── Erreurs ──────────────────────────────────────────────────────────────────

#: Code d'erreur d'AIODOS → le geste à faire DANS PANDORA. Le message d'AIODOS
#: (déjà dans la langue de l'interface) passe devant.
_ADVICE = {
    "needs_access": "Paramètres → AIODOS → « Se connecter à AIODOS ».",
    "invalid_api_key": "Paramètres → AIODOS → « Se connecter à AIODOS ».",
    "key_revoked": "L'accès de PANDORA a été retiré dans AIODOS : reconnectez-vous depuis Paramètres → AIODOS.",
    "key_expired": "L'accès de PANDORA a expiré : reconnectez-vous depuis Paramètres → AIODOS.",
    "scope_denied": "Paramètres → AIODOS → « Demander l'accès manquant » pour demander ce droit.",
    "where_denied": "Ce lieu de calcul n'est pas autorisé dans AIODOS (Réglages → Applications et autres outils).",
    "unreachable": "Lancez AIODOS : Paramètres → AIODOS → « Lancer AIODOS ».",
    "engine_unavailable": "Ouvrez ComfyUI et accordez-le dans AIODOS (Réglages → Moteurs des applications) sur au moins une machine.",
    "engine_failed": "Ouvrez ComfyUI et accordez-le dans AIODOS (Réglages → Moteurs des applications) sur au moins une machine.",
    "peer_failed": "Une machine a décroché : relancez dans un instant.",
    "model_unavailable": "Installez-les dans le ComfyUI de cette machine, ou choisissez « Calcul : Ce PC » si ce PC les a.",
    "quota_exceeded": "La réserve de fichiers d'AIODOS est pleine : onglet AIODOS → « Récupérer » ou « Oublier » les travaux finis.",
    "rate_limited": "AIODOS est occupé : réessayez dans un instant.",
    "busy": "AIODOS est occupé : réessayez dans un instant.",
    "input_too_large": "Un fichier dépasse 100 Mo, la limite d'un envoi à AIODOS : réduisez le clip.",
    "not_supported": "Cette fonction arrivera avec une prochaine version d'AIODOS ou de PANDORA.",
}


def humanize(exc) -> str:
    """Erreur du client AIODOS → message pour l'utilisateur (le message d'AIODOS,
    puis le geste à faire dans PANDORA)."""
    from core.i18n import translate as _t
    code = str(getattr(exc, "code", "") or "")
    msg = str(getattr(exc, "message", "") or exc or "").strip()
    hint = str(getattr(exc, "hint", "") or "").strip()
    parts = [f"AIODOS — {msg}" if msg else "AIODOS"]
    if hint and hint not in msg:
        parts.append(hint)
    advice = _ADVICE.get(code)
    if code == "model_unavailable":
        detail = getattr(exc, "detail", None) or {}
        models = detail.get("models") if isinstance(detail, dict) else None
        machine = detail.get("machine") if isinstance(detail, dict) else None
        names = [str(m.get("name") if isinstance(m, dict) else m) for m in (models or ())]
        # Le message d'AIODOS les nomme déjà, en général : pas deux fois la liste.
        if names and not all(n in msg for n in names):
            parts.append(_t("Modèle(s) manquant(s) : {names}{where}.").format(
                names=", ".join(names),
                where=(_t(" sur {machine}").format(machine=machine) if machine else "")))
    if advice:
        parts.append(_t(advice))
    return "\n".join(parts)
