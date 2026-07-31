"""
Préférences caméra/optiques/filtres/micro par projet.
Structure stockée dans data/camera_prefs.json.

⚠ FONCTIONNALITÉ RETIRÉE (décision Matthieu 2026-07-31 : « on peut enlever
l'onglet Image & Son et supprimer cette fonctionnalité, il ne sert pas »).

Le module RESTE en place, et c'est volontaire : dix endroits le lisent — les
cinq fiches d'éléments (personnage, décor, accessoire, HMC, véhicule) et le
Studio IA des DEUX éditions, où le sélecteur de focale s'appuie dessus.
Supprimer le fichier aurait cassé la focale du Cinéma et du Live d'un coup.

À la place, un drapeau : `_FEATURE_ENABLED = False` fait répondre les
préférences VIDES à tout le monde — exactement l'état d'un projet neuf qui
n'a jamais ouvert la page, cas déjà géré partout. Plus aucune caméra, optique
ni micro n'entre dans un prompt, et rien n'est écrit sur le disque.

Pour la remettre : repasser le drapeau à True et décommenter l'entrée de
navigation dans `ui/pandora_window.py`. Les `camera_prefs.json` existants ne
sont pas effacés — les réglages d'un projet reviendraient tels quels.
"""
import json
import os

from core.paths import APP_ROOT as _ROOT
_DATA_DIR   = os.path.join(_ROOT, "data")
_PREFS_FILE = os.path.join(_DATA_DIR, "camera_prefs.json")

#: Interrupteur unique de la fonctionnalité « Image & Son ». Voir l'en-tête.
_FEATURE_ENABLED = False

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
    """Retourne les préférences caméra du projet courant.

    Fonctionnalité retirée → préférences VIDES pour tout le monde, sans même
    lire le fichier : un projet qui avait réglé une caméra ne doit pas continuer
    à l'injecter dans ses prompts alors que la page qui permettait de la changer
    n'existe plus. Les appelants reçoivent le dictionnaire complet (clés
    présentes, valeurs vides), donc aucun d'eux n'a à être modifié."""
    if not _FEATURE_ENABLED:
        return dict(_DEFAULTS)
    from core.context import get_project_id
    pid = get_project_id() or "__default__"
    all_p = _all_prefs()
    prefs = dict(_DEFAULTS)
    prefs.update(all_p.get(pid, {}))
    return prefs


def save_camera_prefs(prefs: dict):
    """Sauvegarde les préférences caméra pour le projet courant.

    Sans effet tant que la fonctionnalité est retirée — plus rien ne doit
    écrire dans camera_prefs.json, y compris un reliquat d'auto-save."""
    if not _FEATURE_ENABLED:
        return
    from core.context import get_project_id
    pid = get_project_id() or "__default__"
    all_p = _all_prefs()
    all_p[pid] = prefs
    _save_all(all_p)


def get_prompt_suffix() -> str:
    """Retourne le suffixe English pour le prompt Seedance (caméra + optiques + filtres)."""
    from core.camera_data import build_camera_prompt_suffix
    return build_camera_prompt_suffix(get_camera_prefs())
