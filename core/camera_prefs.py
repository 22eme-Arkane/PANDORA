"""
Préférences caméra/optiques/filtres/micro par projet.
Structure stockée dans data/camera_prefs.json.
"""
import json
import os

from core.paths import APP_ROOT as _ROOT
_DATA_DIR   = os.path.join(_ROOT, "data")
_PREFS_FILE = os.path.join(_DATA_DIR, "camera_prefs.json")

_DEFAULTS: dict = {
    # Caméra
    "camera_brand":   "",
    "camera_body":    "",
    # Optiques
    "optics_brand":   "",
    "optics_series":  "",
    # Filtres (liste de strings)
    "filters":        [],
    # Microphone
    "mic_category":   "",
    "mic_model":      "",
    # Mouvement de caméra
    "shot_movement":  "",
}


def _all_prefs() -> dict:
    """Charge l'intégralité du fichier (keyed par project_id)."""
    os.makedirs(_DATA_DIR, exist_ok=True)
    if not os.path.isfile(_PREFS_FILE):
        return {}
    try:
        with open(_PREFS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _save_all(data: dict):
    os.makedirs(_DATA_DIR, exist_ok=True)
    with open(_PREFS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def get_camera_prefs() -> dict:
    """Retourne les préférences caméra du projet courant."""
    from core.context import get_project_id
    pid = get_project_id() or "__default__"
    all_p = _all_prefs()
    prefs = dict(_DEFAULTS)
    prefs.update(all_p.get(pid, {}))
    return prefs


def save_camera_prefs(prefs: dict):
    """Sauvegarde les préférences caméra pour le projet courant."""
    from core.context import get_project_id
    pid = get_project_id() or "__default__"
    all_p = _all_prefs()
    all_p[pid] = prefs
    _save_all(all_p)


def get_prompt_suffix() -> str:
    """Retourne le suffixe English pour le prompt Seedance (caméra + optiques + filtres)."""
    from core.camera_data import build_camera_prompt_suffix
    return build_camera_prompt_suffix(get_camera_prefs())
