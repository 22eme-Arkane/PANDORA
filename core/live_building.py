"""
core/live_building.py — Référence visuelle du BÂTIMENT / FAÇADE pour PANDORA | Live.

Une seule image par projet : la façade sur laquelle le mapping est projeté. Elle est
choisie dans le Conducteur (section « Référence bâtiment ») et réutilisée par la
génération des moods en mode Mapping (Flux Kontext : édite la façade en gardant sa
géométrie). Persistée dans le dossier de données du projet courant.
"""

import os
import json


def _path() -> str:
    from core.context import get_data_root
    return os.path.join(get_data_root(), "live_building_ref.json")


def get_building_ref() -> str:
    """Chemin de l'image de façade du projet courant (vide si aucune)."""
    try:
        with open(_path(), encoding="utf-8") as f:
            p = json.load(f).get("path", "")
        return p if p and os.path.isfile(p) else ""
    except Exception:
        return ""


def set_building_ref(path: str) -> None:
    try:
        p = _path()
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "w", encoding="utf-8") as f:
            json.dump({"path": path or ""}, f)
    except Exception:
        pass


def clear_building_ref() -> None:
    set_building_ref("")
