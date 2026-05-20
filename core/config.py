import json
import os
import sys

# En mode gelé (PyInstaller installé dans Program Files), les données utilisateur
# vont dans %LOCALAPPDATA%\PANDORA\ (répertoire accessible en écriture sans UAC).
if getattr(sys, "frozen", False):
    _ROOT = os.path.join(os.environ.get("LOCALAPPDATA", os.path.expanduser("~")), "PANDORA")
else:
    _ROOT = os.path.dirname(os.path.dirname(__file__))

_DATA_DIR = os.path.join(_ROOT, "data")
_CONFIG_FILE = os.path.join(_DATA_DIR, "config.json")

_DEFAULTS = {
    "api_key":               "",
    "anthropic_key":         "",
    "default_model":         "seedance-2.0",
    "default_duration":      "10",
    "default_resolution":    "720p",
    "output_dir":            "",   # vide = ~/Videos/PANDORA/
    "last_project_location": "",   # dernier dossier parent utilisé pour créer un projet
    # Modèle de génération d'images (castings, décors, accessoires, HMC, véhicules)
    "image_model":           "nb2",     # nb2 | nb_pro
    # Moteur vidéo alternatif (en plus de Seedance 2.0)
    "video_engine_alt":      "kling",   # kling | pixverse
    # Nano Banana Key (optionnel — même clé fal.ai si vide)
    "nano_banana_key":       "",
    # Charte d'utilisation — True = acceptée par l'utilisateur
    "eula_accepted":         False,
    # Guide de démarrage — True = afficher au premier lancement
    "show_api_guide":        True,
}

# ── Mapping modèle image → endpoint fal.ai ────────────────────────────────────
IMAGE_MODEL_ENDPOINTS = {
    "nb2":    "fal-ai/nano-banana-2",
    "nb_pro": "fal-ai/nano-banana-pro",
}

IMAGE_MODEL_LABELS = {
    "nb2":    "Nano Banana 2  —  Gemini 3.1 Flash  ·  $0.08/img",
    "nb_pro": "Nano Banana Pro  —  Gemini 3 Pro  ·  $0.15/img",
}

IMAGE_MODEL_PRICES = {
    "nb2":    "$0.08",
    "nb_pro": "$0.15",
}


def get_image_endpoint(cfg: dict | None = None) -> str:
    """Retourne l'endpoint fal.ai du modèle image sélectionné dans la config."""
    if cfg is None:
        cfg = load_config()
    return IMAGE_MODEL_ENDPOINTS.get(cfg.get("image_model", "nb2"), IMAGE_MODEL_ENDPOINTS["nb2"])


def get_image_price(cfg: dict | None = None) -> str:
    """Retourne le prix formaté du modèle image sélectionné."""
    if cfg is None:
        cfg = load_config()
    return IMAGE_MODEL_PRICES.get(cfg.get("image_model", "nb2"), "$0.08")


def get_output_dir(cfg: dict | None = None) -> str:
    """Retourne le dossier de sortie des clips Seedance.

    Quand un projet est ouvert : <projet>/data/Seedance/
    Sinon : PANDORA/Seedance 2.0/ (dossier global)
    """
    from core.context import get_project_path
    project_path = get_project_path()
    if project_path:
        path = os.path.join(project_path, "data", "Seedance")
        os.makedirs(path, exist_ok=True)
        return path
    from core.pandora_dirs import get_bin_dir
    return get_bin_dir("seedance", cfg)


def load_config() -> dict:
    os.makedirs(_DATA_DIR, exist_ok=True)
    if os.path.exists(_CONFIG_FILE):
        with open(_CONFIG_FILE, "r") as f:
            return json.load(f)
    return dict(_DEFAULTS)


def save_config(cfg: dict):
    os.makedirs(_DATA_DIR, exist_ok=True)
    with open(_CONFIG_FILE, "w") as f:
        json.dump(cfg, f, indent=2)
