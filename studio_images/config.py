"""
Configuration de Studio Images — application autonome ET onglet « Image IA »
embarqué dans PANDORA | Cinéma.

Stocke les clés API et préférences dans config.json (dossier inscriptible —
voir user_data_dir). Au premier lancement, pré-remplit les clés depuis la config
de PANDORA si elle existe — pour ne pas avoir à les ressaisir.
"""

import json
import os
import sys


def user_data_dir() -> str:
    """Dossier INSCRIPTIBLE des données Studio Images (config, refs, prompts).

    - Build gelé (PyInstaller, embarqué dans PANDORA) : le dossier de
      l'application est en lecture seule (Program Files) → on écrit dans
      %LOCALAPPDATA%\\PANDORA\\studio_images\\.
    - Dev / app autonome (`python studio_images/main.py`) : le dossier
      studio_images/ lui-même, comme avant.
    """
    if getattr(sys, "frozen", False):
        if sys.platform == "darwin":
            base = os.path.expanduser(
                "~/Library/Application Support/PANDORA/studio_images")
        else:
            base = os.path.join(
                os.environ.get("LOCALAPPDATA", os.path.expanduser("~")),
                "PANDORA", "studio_images")
    else:
        base = os.path.dirname(os.path.abspath(__file__))
    try:
        os.makedirs(base, exist_ok=True)
    except Exception:
        pass
    return base


def _pandora_config_path() -> str:
    """config.json de PANDORA — emplacement réel selon dev vs. gelé.
    Sert à pré-remplir les clés API au premier lancement."""
    if getattr(sys, "frozen", False):
        if sys.platform == "darwin":
            return os.path.expanduser(
                "~/Library/Application Support/PANDORA/data/config.json")
        return os.path.join(
            os.environ.get("LOCALAPPDATA", os.path.expanduser("~")),
            "PANDORA", "data", "config.json")
    # dev : un niveau au-dessus de studio_images/
    return os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "data", "config.json")


_HERE = user_data_dir()
_CONFIG_FILE = os.path.join(_HERE, "config.json")
# config.json de PANDORA (pour récupérer les clés au premier lancement)
_PANDORA_CONFIG = _pandora_config_path()

# Formats de sortie : (label, (largeur, hauteur) pixels d'export)
# L'aspect_ratio est dérivé de la taille par chaque moteur (engines.py).
# "free" = taille personnalisée saisie dans l'UI (voir custom_size).
FORMATS = {
    # Réseaux / vidéo
    "thumbnail": ("Vignette YouTube 1280×720",   (1280, 720)),
    "banner":    ("Bannière YouTube 2560×1440",  (2560, 1440)),
    "wide":      ("Paysage HD 1920×1080",        (1920, 1080)),
    "uhd4k":     ("4K UHD 3840×2160",            (3840, 2160)),
    "square":    ("Carré réseaux 1080×1080",     (1080, 1080)),
    "story":     ("Story / Reel 1080×1920",      (1080, 1920)),
    "poster":    ("Affiche 1080×1350",           (1080, 1350)),
    "logo_sq":   ("Logo carré 1024×1024",        (1024, 1024)),
    "logo_wide": ("Logo / bandeau 1600×400",     (1600, 400)),
    # Formats classiques (référence Photoshop / impression)
    "dci4k":     ("Cinéma DCI 4K 4096×2160",     (4096, 2160)),
    "a4_port":   ("A4 portrait 2480×3508 (300dpi)", (2480, 3508)),
    "a4_land":   ("A4 paysage 3508×2480 (300dpi)",  (3508, 2480)),
    "letter":    ("US Letter 2550×3300 (300dpi)",   (2550, 3300)),
    "hd_sd":     ("SD 1024×768 (4:3)",           (1024, 768)),
    "free":      ("Personnalisé…",               (1024, 1024)),
}

_DEFAULTS = {
    "anthropic_key": "",
    "fal_key":       "",
    "image_model":   "nb_pro",     # clé de engines.ENGINES
    "resolution":    "Personnaliser",  # Personnaliser (= taille du format) | 512x512 | 1K | 2K | 4K
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
    # Migration one-shot : nouveau défaut de résolution = « Personnaliser »
    # (= taille exacte du format), pour lever le doublon format ↔ résolution.
    if not cfg.get("_res_personnaliser_done"):
        cfg["resolution"] = "Personnaliser"
        cfg["_res_personnaliser_done"] = True
        save_config(cfg)
    # Migration one-shot : Largeur/Hauteur deviennent la source de vérité (toujours
    # visibles, pré-remplies par le template) → on les aligne sur le format courant
    # pour un premier affichage cohérent. Le combo de résolution (4K/2K/1K) est retiré.
    if not cfg.get("_dims_from_format_done"):
        fmt = cfg.get("format", "thumbnail")
        if fmt in FORMATS and fmt != "free":
            cfg["custom_w"], cfg["custom_h"] = FORMATS[fmt][1]
        cfg["_dims_from_format_done"] = True
        save_config(cfg)
    return cfg


def save_config(cfg: dict):
    try:
        with open(_CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(cfg, f, indent=2, ensure_ascii=False)
    except Exception:
        pass
