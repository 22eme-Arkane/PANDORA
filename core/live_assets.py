"""
core/live_assets.py — Données « assets » dédiées à PANDORA | Live.

Gère Casting / Accessoires / Véhicules **propres au Live**, isolés du Cinéma :
chaque type a son propre dossier dans le projet courant, distinct des modules
Cinéma (castings/, accessories/, vehicles/).

  kind ∈ {"casting", "accessoires", "vehicules"}
  Dossiers :  <data_root>/live_castings | live_accessories | live_vehicles
              ├── index.json   (métadonnées)
              └── images/       (images générées / ajoutées)

Aucune dépendance UI.
"""

import os
import json
import uuid
from datetime import datetime

import core.context as ctx

_FOLDERS = {
    "casting":     "live_castings",
    "accessoires": "live_accessories",
    "vehicules":   "live_vehicles",
}


# ── Chemins ─────────────────────────────────────────────────────────────────

def subdir(kind: str) -> str:
    """Nom de sous-dossier (= subdir passé au worker Nano Banana)."""
    return _FOLDERS.get(kind, f"live_{kind}")


def _base_dir(kind: str) -> str:
    d = os.path.join(ctx.get_data_root(), subdir(kind))
    os.makedirs(d, exist_ok=True)
    return d


def images_dir(kind: str) -> str:
    d = os.path.join(_base_dir(kind), "images")
    os.makedirs(d, exist_ok=True)
    return d


def images_dir_for_subdir(sub: str) -> str:
    """Utilisé par api/nano_banana._project_images_dir pour les subdirs Live."""
    d = os.path.join(ctx.get_data_root(), sub, "images")
    os.makedirs(d, exist_ok=True)
    return d


def _index_path(kind: str) -> str:
    return os.path.join(_base_dir(kind), "index.json")


# ── CRUD ────────────────────────────────────────────────────────────────────

def list_assets(kind: str) -> list:
    path = _index_path(kind)
    if not os.path.isfile(path):
        return []
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, list) else data.get("items", [])
    except Exception:
        return []


def _save_all(kind: str, items: list):
    with open(_index_path(kind), "w", encoding="utf-8") as f:
        json.dump(items, f, ensure_ascii=False, indent=2)


def get_asset(kind: str, asset_id: str) -> dict | None:
    return next((a for a in list_assets(kind) if a.get("id") == asset_id), None)


def upsert_asset(kind: str, asset: dict) -> dict:
    """Crée (si pas d'id) ou met à jour un asset. Retourne l'asset (avec id)."""
    items = list_assets(kind)
    if not asset.get("id"):
        asset["id"] = uuid.uuid4().hex[:12]
        asset.setdefault("created_at", datetime.now().isoformat())
        items.append(asset)
    else:
        for i, a in enumerate(items):
            if a.get("id") == asset["id"]:
                items[i] = asset
                break
        else:
            items.append(asset)
    _save_all(kind, items)
    return asset


def delete_asset(kind: str, asset_id: str):
    items = [a for a in list_assets(kind) if a.get("id") != asset_id]
    _save_all(kind, items)
