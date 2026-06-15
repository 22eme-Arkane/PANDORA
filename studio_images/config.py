"""
Configuration de Studio Images — application autonome.

Stocke les clés API et préférences dans studio_images/config.json.
Au premier lancement, pré-remplit les clés depuis la config de PANDORA
(../data/config.json) si elle existe — pour ne pas avoir à les ressaisir.
"""

import json
import os

_HERE = os.path.dirname(os.path.abspath(__file__))
_CONFIG_FILE = os.path.join(_HERE, "config.json")
# config.json de PANDORA (un niveau au-dessus de ce dossier)
_PANDORA_CONFIG = os.path.join(os.path.dirname(_HERE), "data", "config.json")

# Formats de sortie : (label, (largeur, hauteur) pixels d'export)
# L'aspect_ratio est dérivé de la taille par chaque moteur (engines.py).
# "free" = taille personnalisée saisie dans l'UI (voir custom_size).
FORMATS = {
    "thumbnail": ("Vignette YouTube 1280×720",   (1280, 720)),
    "banner":    ("Bannière YouTube 2560×1440",  (2560, 1440)),
    "logo_sq":   ("Logo carré 1024×1024",        (1024, 1024)),
    "logo_wide": ("Logo / bandeau 1600×400",     (1600, 400)),
    "poster":   ("Affiche 1080×1350",            (1080, 1350)),
    "wide":      ("Paysage 1920×1080",           (1920, 1080)),
    "square":    ("Carré réseaux 1080×1080",     (1080, 1080)),
    "story":     ("Story / Reel 1080×1920",      (1080, 1920)),
    "free":      ("Personnalisé…",               (1024, 1024)),
}

_DEFAULTS = {
    "anthropic_key": "",
    "fal_key":       "",
    "image_model":   "nb_pro",     # clé de engines.ENGINES
    "resolution":    "2K",         # 512x512 | 1K | 2K | 4K (moteurs Nano Banana)
    "format":        "thumbnail",  # clé de FORMATS
    "custom_w":      1024,
    "custom_h":      1024,
    "count":         1,            # nombre d'images générées par lot (1-4)
    "output_dir":    "",           # vide → ~/Pictures/Studio Images
}


def default_output_dir() -> str:
    return os.path.join(os.path.expanduser("~"), "Pictures", "Studio Images")


def refs_dir() -> str:
    """Dossier où sont copiées les images de référence (persistées entre sessions)."""
    d = os.path.join(_HERE, "refs")
    os.makedirs(d, exist_ok=True)
    return d


def _import_from_pandora() -> dict:
    """Récupère les clés depuis la config PANDORA si disponible."""
    out = {}
    try:
        if os.path.isfile(_PANDORA_CONFIG):
            with open(_PANDORA_CONFIG, "r", encoding="utf-8") as f:
                pc = json.load(f)
            if pc.get("anthropic_key"):
                out["anthropic_key"] = pc["anthropic_key"]
            if pc.get("api_key"):  # clé fal.ai dans PANDORA
                out["fal_key"] = pc["api_key"]
    except Exception:
        pass
    return out


def load_config() -> dict:
    cfg = dict(_DEFAULTS)
    if os.path.isfile(_CONFIG_FILE):
        try:
            with open(_CONFIG_FILE, "r", encoding="utf-8") as f:
                cfg.update(json.load(f))
        except Exception:
            pass
    else:
        # Premier lancement : récupère les clés de PANDORA et persiste
        cfg.update(_import_from_pandora())
        save_config(cfg)
    if not cfg.get("output_dir"):
        cfg["output_dir"] = default_output_dir()
    return cfg


def save_config(cfg: dict):
    try:
        with open(_CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(cfg, f, indent=2, ensure_ascii=False)
    except Exception:
        pass
