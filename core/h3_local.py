"""core/h3_local.py — MiniMax H3 en local : réglages et détection du serveur.

PANDORA n'embarque NI les poids NI le moteur : il parle à un serveur que
l'utilisateur installe lui-même — le projet communautaire
`ksl16012001/minimax-h3-local` (stable-diffusion.cpp + GGUF, tourne sur une
carte 8 Go), qui expose une API HTTP :

    POST /sdcpp/v1/vid_gen   → {"id": …}
    GET  /sdcpp/v1/jobs/{id} → {"status": "completed"|"failed"|"cancelled"|…,
                                 "queue_position": n, "result": {"b64_json": …}}

Ce module est PUR (aucun Qt) : lecture du réglage, normalisation de l'URL,
sonde de disponibilité, et construction de la requête — cette dernière isolée
pour être testée sans serveur.

⚠ LICENCE — à afficher, jamais à cacher. Les poids H3 sont publiés sous la
« MiniMax H3 Community License », qui EXCLUT l'Union européenne, le
Royaume-Uni, la Corée et les États-Unis (« You may not use, reproduce, modify,
distribute, or display the MiniMax H3 Works or any of their Outputs or results
outside the Applicable Territory. »). Décision Matthieu 2026-09-13 : PANDORA
intègre le branchement et laisse chacun juge — mais l'interface DOIT le dire.
PANDORA ne distribue rien de MiniMax : seulement un client HTTP.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request

from core.config import load_config

DEFAULT_URL = "http://127.0.0.1:1234"
CONFIG_KEY = "h3_local_url"

#: Contraintes du moteur (README + NOTES du projet communautaire, 2026-09-13).
FPS = 24                      # sortie fixe
MULTIPLE = 32                 # largeur et hauteur : multiples de 32
FRAMES_STEP, FRAMES_BASE = 17, 5   # nombre d'images « 17k + 5 »
CFG_SCALE = 1.0               # imposé par le modèle distillé
DEFAULT_STEPS = 8             # 8 pas avec le LoRA turbo — le réglage « 8 Go »

#: Préréglages de CADRE, mesurés sur RTX 3070 8 Go (NOTES.md du projet).
#: Donnés en petit côté × grand côté : l'ORIENTATION vient du ratio choisi dans
#: le formulaire (16:9 → paysage, 9:16 → portrait), sinon le menu « Format »
#: contredirait le préréglage. La DURÉE vient du curseur, pas d'ici.
#: Temps indicatifs pour 2,3 s, serveur résident, DiT Q3 + LoRA turbo, 8 pas —
#: « qualité » = DiT Q8, 25 pas : ~28 min, c'est le prix du 768p sur 8 Go.
PRESETS = {
    "rapide":  {"short": 384, "long": 672,  "steps": 8,  "label": "Rapide — 384×672 · ~1,5 min pour 2,3 s"},
    "qualite": {"short": 768, "long": 1344, "steps": 25, "label": "Qualité — 768×1344 · ~28 min pour 2,3 s"},
}
DEFAULT_PRESET = "rapide"

_LANDSCAPE = ("16:9", "21:9", "4:3")
_PORTRAIT = ("9:16", "3:4")


def frame_for(preset: str, aspect_ratio: str) -> tuple[int, int]:
    """(largeur, hauteur) d'un préréglage orienté par le ratio.

    Le modèle n'a que deux tailles de canevas éprouvées sur 8 Go ; on ne
    fabrique pas un 21:9 exact, on oriente le canevas — et on le dit dans le
    libellé du formulaire. 1:1 prend le petit côté des deux côtés.
    """
    p = PRESETS.get((preset or "").strip().lower()) or PRESETS[DEFAULT_PRESET]
    r = (aspect_ratio or "16:9").strip()
    if r == "1:1":
        return p["short"], p["short"]
    if r in _PORTRAIT:
        return p["short"], p["long"]
    return p["long"], p["short"]          # paysage par défaut


def steps_for(preset: str) -> int:
    p = PRESETS.get((preset or "").strip().lower()) or PRESETS[DEFAULT_PRESET]
    return int(p.get("steps") or DEFAULT_STEPS)

LICENSE_NOTICE = (
    "Les poids MiniMax H3 sont publiés sous la « MiniMax H3 Community "
    "License », qui exclut l'Union européenne, le Royaume-Uni, la Corée du "
    "Sud et les États-Unis : y faire tourner le modèle — ou en utiliser les "
    "sorties — n'est pas autorisé sans accord écrit de MiniMax. PANDORA ne "
    "distribue ni les poids ni le moteur ; il se connecte au serveur que "
    "vous installez. L'installer et l'utiliser relève de votre seule "
    "responsabilité."
)


# ── Réglage ──────────────────────────────────────────────────────────────────

def normalize_url(url: str) -> str:
    u = (url or "").strip().rstrip("/")
    if not u:
        return DEFAULT_URL
    if not u.startswith(("http://", "https://")):
        u = "http://" + u
    return u


def get_url(cfg: dict | None = None) -> str:
    cfg = cfg if cfg is not None else load_config()
    return normalize_url(cfg.get(CONFIG_KEY, ""))


def set_url(url: str) -> str:
    """Enregistre l'adresse et la renvoie normalisée. Relit la config entière
    avant d'écrire : `save_config` REMPLACE le fichier (voir mémoire projet),
    un dict partiel effacerait les clés API."""
    from core.config import save_config
    cfg = load_config()
    val = (url or "").strip()
    cfg[CONFIG_KEY] = "" if (not val or normalize_url(val) == DEFAULT_URL) else normalize_url(val)
    save_config(cfg)
    return normalize_url(cfg[CONFIG_KEY])


# ── Sonde ────────────────────────────────────────────────────────────────────

def ping(url: str = "", timeout: float = 2.0) -> tuple[bool, str]:
    """(joignable, message). Ne lève jamais.

    On interroge la racine : le serveur y sert sa petite interface. Un 404
    compte comme joignable — c'est un serveur HTTP qui répond, et c'est tout
    ce qu'on veut savoir ici.
    """
    base = normalize_url(url) if url else get_url()
    try:
        with urllib.request.urlopen(base + "/", timeout=timeout) as r:
            return True, f"Serveur H3 local joignable ({r.status})"
    except urllib.error.HTTPError as e:
        return True, f"Serveur H3 local joignable ({e.code})"
    except Exception as e:
        return False, f"Serveur H3 local injoignable sur {base} — {e.__class__.__name__}"


# ── Requête ──────────────────────────────────────────────────────────────────

def snap_dimension(px) -> int:
    """Multiple de 32 le plus proche, jamais en dessous de 32."""
    try:
        v = int(px)
    except (TypeError, ValueError):
        v = MULTIPLE
    return max(MULTIPLE, int(round(v / MULTIPLE)) * MULTIPLE)


def snap_frames(frames) -> int:
    """Nombre d'images « 17k + 5 » le plus proche (contrainte du VAE vidéo)."""
    try:
        f = int(frames)
    except (TypeError, ValueError):
        f = FRAMES_BASE + FRAMES_STEP * 3
    k = max(1, int(round((f - FRAMES_BASE) / FRAMES_STEP)))
    return FRAMES_BASE + FRAMES_STEP * k


def frames_for_seconds(seconds) -> int:
    try:
        s = float(seconds)
    except (TypeError, ValueError):
        s = 2.3
    return snap_frames(int(round(s * FPS)))


def build_request(prompt: str, width: int, height: int, frames: int,
                  steps: int = DEFAULT_STEPS, seed: int | None = None,
                  init_image_b64: str = "", end_image_b64: str = "",
                  lora: list | None = None) -> dict:
    """Corps JSON de POST /sdcpp/v1/vid_gen.

    Forme relevée dans batch_gen.py du projet communautaire, champs image
    confirmés par examples/server/api.md de stable-diffusion.cpp (2026-09-13) :
    `init_image` et `end_image` acceptent une chaîne base64 ou une data URL.
    """
    body: dict = {
        "prompt": prompt or "",
        "width": snap_dimension(width),
        "height": snap_dimension(height),
        "video_frames": snap_frames(frames),
        "fps": FPS,
        "sample_params": {
            "sample_steps": max(1, int(steps or DEFAULT_STEPS)),
            "guidance": {"txt_cfg": CFG_SCALE, "img_cfg": CFG_SCALE},
        },
        "vae_tiling_params": {"enabled": True, "temporal_tiling": True},
        "output_format": "webm",
    }
    if seed is not None:
        body["seed"] = int(seed)
    if init_image_b64:
        body[INIT_IMAGE_FIELD] = init_image_b64
    if end_image_b64:
        body[END_IMAGE_FIELD] = end_image_b64
    if lora:
        body["lora"] = list(lora)
    return body


#: Champs image de /sdcpp/v1/vid_gen — source : examples/server/api.md de
#: stable-diffusion.cpp (« base64 string, or a data URL such as
#: data:image/png;base64,… », 3 canaux). `end_image` seul = dernière image
#: imposée, les deux = première/dernière (FL2VA).
INIT_IMAGE_FIELD = "init_image"
END_IMAGE_FIELD = "end_image"

#: États d'une tâche côté serveur (async_jobs.cpp). Tout ce qui n'est pas
#: terminal est « en cours » : on ne dépend pas d'un libellé intermédiaire.
JOB_DONE = "completed"
JOB_FAILED = ("failed", "cancelled", "error")


def seconds_of(frames) -> float:
    return round(snap_frames(frames) / FPS, 2)


def to_json(body: dict) -> bytes:
    return json.dumps(body).encode("utf-8")
