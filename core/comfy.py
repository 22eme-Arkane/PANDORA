"""core/comfy.py — ComfyUI comme moteur de rendu : réglage, détection, protocole.

ComfyUI tourne en serveur local et s'adresse en HTTP :

    GET  /system_stats            → vivant ? (et version, VRAM)
    GET  /object_info             → définitions de TOUS les nœuds installés
    POST /upload/image            → dépose une image d'entrée (multipart)
    POST /prompt                  → {"prompt": <workflow API>, "client_id": …}
                                    → {"prompt_id": …}
    GET  /queue                   → files en attente / en cours
    GET  /history/{prompt_id}     → {prompt_id: {"status": …, "outputs": {…}}}
    GET  /view?filename=…&subfolder=…&type=output → le fichier produit

Décisions (Matthieu, 2026-09-13) : ComfyUI est un moteur DE PLUS et le rendu
local PAR DÉFAUT ; H3 y tourne ; c'est l'utilisateur qui l'installe, et quand
le moteur est choisi sans serveur joignable, une fenêtre le guide.

PANDORA n'embarque rien de ComfyUI. Il se connecte, guide, et convertit.

Module PUR pour tout ce qui est calcul ; les deux fonctions réseau (`ping`,
`fetch_object_info`) n'utilisent que la bibliothèque standard et ne lèvent
jamais.
"""

from __future__ import annotations

import json
import os
import subprocess
import urllib.error
import urllib.request
import uuid

from core.config import load_config

CONFIG_KEY = "comfy_url"
#: ComfyUI classique écoute sur 8188 ; ComfyUI Desktop choisit souvent 8000.
#: On sonde les deux quand rien n'est réglé, pour que « ça marche » sans
#: demander à l'utilisateur de connaître un numéro de port.
CANDIDATE_URLS = ("http://127.0.0.1:8188", "http://127.0.0.1:8000")
DEFAULT_URL = CANDIDATE_URLS[0]
DOWNLOAD_URL = "https://www.comfy.org/download"
DOCS_H3_URL = "https://docs.comfy.org/tutorials/video/minimax/minimax-h3"

#: Version minimale portant les nœuds MiniMax H3 (docs.comfy.org).
MIN_VERSION_FOR_H3 = "0.30.0"


# ── Réglage ──────────────────────────────────────────────────────────────────

def normalize_url(url: str) -> str:
    u = (url or "").strip().rstrip("/")
    if not u:
        return ""
    if not u.startswith(("http://", "https://")):
        u = "http://" + u
    return u


def get_url(cfg: dict | None = None) -> str:
    """Adresse réglée, ou la première candidate — sans sonder."""
    cfg = cfg if cfg is not None else load_config()
    return normalize_url(cfg.get(CONFIG_KEY, "")) or DEFAULT_URL


def set_url(url: str) -> str:
    """Relit la config ENTIÈRE avant d'écrire : save_config remplace le
    fichier, un dict partiel effacerait les clés API."""
    from core.config import save_config
    cfg = load_config()
    cfg[CONFIG_KEY] = normalize_url(url)
    save_config(cfg)
    return cfg[CONFIG_KEY] or DEFAULT_URL


# ── Détection ────────────────────────────────────────────────────────────────

def _get_json(url: str, timeout: float = 3.0):
    with urllib.request.urlopen(url, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8", "replace"))


def ping(url: str = "", timeout: float = 2.0) -> tuple[bool, str, dict]:
    """(joignable, message, infos). Ne lève jamais.

    `/system_stats` est l'endpoint le plus léger de ComfyUI et renvoie la
    version : on en profite pour dire si elle porte les nœuds H3.
    """
    base = normalize_url(url) if url else get_url()
    try:
        j = _get_json(base + "/system_stats", timeout)
        sysinfo = (j or {}).get("system") or {}
        ver = str(sysinfo.get("comfyui_version") or "")
        devs = (j or {}).get("devices") or []
        vram = ""
        if devs and isinstance(devs[0], dict) and devs[0].get("vram_total"):
            vram = f" · VRAM {devs[0]['vram_total'] / 2**30:.0f} Go"
        return True, f"ComfyUI {ver or '?'} joignable sur {base}{vram}", {
            "url": base, "version": ver, "vram_total": devs[0].get("vram_total") if devs else None}
    except urllib.error.HTTPError as e:
        return True, f"Serveur joignable sur {base} ({e.code})", {"url": base, "version": ""}
    except Exception as e:
        return False, f"ComfyUI injoignable sur {base} — {e.__class__.__name__}", {"url": base}


def discover(cfg: dict | None = None, timeout: float = 1.0) -> str:
    """URL d'un ComfyUI vivant : l'adresse réglée d'abord, puis les candidates.
    Chaîne vide si rien ne répond."""
    tried = []
    configured = normalize_url((cfg if cfg is not None else load_config()).get(CONFIG_KEY, ""))
    for u in ([configured] if configured else []) + list(CANDIDATE_URLS):
        if u in tried:
            continue
        tried.append(u)
        if ping(u, timeout)[0]:
            return u
    return ""


def desktop_installed() -> bool:
    """Vrai si ComfyUI Desktop est présent — lancé, ou installé sans tourner.
    Sert à la fenêtre d'installation : le message n'est pas le même selon
    qu'il faut installer ou simplement démarrer."""
    try:
        out = subprocess.run(["tasklist", "/FO", "CSV"], capture_output=True,
                             text=True, errors="replace", timeout=10).stdout
        if "comfy desktop.exe" in out.lower():
            return True
    except Exception:
        pass
    la = os.environ.get("LOCALAPPDATA", "")
    for d in (os.path.join(la, "Comfy-Desktop"),
              os.path.join(la, "Programs", "@comfyorgcomfyui-electron"),
              os.path.join(os.path.expanduser("~"), "Documents", "ComfyUI")):
        if d and os.path.isdir(d):
            return True
    return False


def version_ok(version: str, minimum: str = MIN_VERSION_FOR_H3) -> bool:
    def parts(v):
        try:
            return tuple(int(x) for x in v.strip().lstrip("v").split(".")[:3])
        except Exception:
            return ()
    a, b = parts(version), parts(minimum)
    return bool(a) and a >= b


def fetch_object_info(url: str = "", timeout: float = 30.0) -> dict:
    """Définitions de nœuds. Lève en cas d'échec : sans elles, aucune
    conversion de workflow n'est possible et il faut le dire."""
    base = normalize_url(url) if url else get_url()
    return _get_json(base + "/object_info", timeout) or {}


# ── Protocole ────────────────────────────────────────────────────────────────

def new_client_id() -> str:
    return "pandora-" + uuid.uuid4().hex[:12]


def prompt_payload(api_workflow: dict, client_id: str = "") -> dict:
    return {"prompt": api_workflow, "client_id": client_id or new_client_id()}


def history_status(entry: dict) -> tuple[str, str]:
    """(état, message) d'une entrée de /history : « success », « error » ou
    « running ». ComfyUI range l'issue sous `status.status_str` et les
    messages d'erreur dans `status.messages`."""
    st = (entry or {}).get("status") or {}
    s = str(st.get("status_str") or "").lower()
    if st.get("completed") and s in ("", "success"):
        return "success", ""
    if s == "error":
        msgs = st.get("messages") or []
        detail = ""
        for m in msgs:
            if isinstance(m, (list, tuple)) and len(m) > 1 and isinstance(m[1], dict):
                detail = str(m[1].get("exception_message") or m[1].get("message") or detail)
        return "error", detail or "erreur d'exécution côté ComfyUI"
    if s == "success":
        return "success", ""
    return "running", ""


_VIDEO_EXT = (".mp4", ".webm", ".mov", ".mkv", ".gif", ".webp")


def outputs_of(entry: dict) -> list[dict]:
    """Fichiers produits, vidéos d'abord. Chaque item : filename, subfolder,
    type — exactement ce que /view attend. Les nœuds de sortie rangent leurs
    fichiers sous des clés variées (images, gifs, videos, audio) : on lit tout
    ce qui a la forme d'un fichier."""
    found: list[dict] = []
    for _nid, out in ((entry or {}).get("outputs") or {}).items():
        if not isinstance(out, dict):
            continue
        for _key, items in out.items():
            if not isinstance(items, list):
                continue
            for it in items:
                if isinstance(it, dict) and it.get("filename"):
                    found.append({"filename": it["filename"],
                                  "subfolder": it.get("subfolder", ""),
                                  "type": it.get("type", "output")})
    found.sort(key=lambda f: 0 if f["filename"].lower().endswith(_VIDEO_EXT) else 1)
    return found


def view_url(base: str, item: dict) -> str:
    from urllib.parse import urlencode
    q = urlencode({"filename": item["filename"], "subfolder": item.get("subfolder", ""),
                   "type": item.get("type", "output")})
    return normalize_url(base) + "/view?" + q
