import json
import os
import uuid
from datetime import datetime

from core.paths import APP_ROOT as _ROOT


def _veh_dir() -> str:
    from core.context import get_data_root
    return os.path.join(get_data_root(), "vehicles")

CATEGORIES = [
    "Voiture", "Moto", "Camion", "Bateau",
    "Avion", "Train", "Vélo", "Autre",
]


def _ensure():
    os.makedirs(_veh_dir(), exist_ok=True)
    os.makedirs(os.path.join(_veh_dir(), "images"), exist_ok=True)


def images_dir() -> str:
    _ensure()
    return os.path.join(_veh_dir(), "images")


def _all_vehicles() -> list[dict]:
    index_file = os.path.join(_veh_dir(), "index.json")
    if not os.path.isfile(index_file):
        return []
    try:
        with open(index_file, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []


def list_vehicles() -> list[dict]:
    items = _all_vehicles()
    from core.context import get_project_id
    pid = get_project_id()
    if pid:
        return [v for v in items if v.get("project_id") == pid]
    return items


def save_vehicle(data: dict) -> dict:
    from core.context import get_project_id
    _ensure()
    pid = get_project_id()
    if pid and not data.get("project_id"):
        data["project_id"] = pid
    items = _all_vehicles()
    if not data.get("id"):
        data["id"] = str(uuid.uuid4())
    if not data.get("created_at"):
        data["created_at"] = datetime.now().isoformat()
    data["updated_at"] = datetime.now().isoformat()
    data.setdefault("assigned_to", [])

    idx = next((i for i, v in enumerate(items) if v.get("id") == data["id"]), None)
    if idx is not None:
        items[idx] = data
    else:
        items.append(data)

    with open(os.path.join(_veh_dir(), "index.json"), "w", encoding="utf-8") as f:
        json.dump(items, f, indent=2, ensure_ascii=False)
    return data


def delete_vehicle(veh_id: str):
    _ensure()
    items = [v for v in _all_vehicles() if v.get("id") != veh_id]
    with open(os.path.join(_veh_dir(), "index.json"), "w", encoding="utf-8") as f:
        json.dump(items, f, indent=2, ensure_ascii=False)


def get_vehicle(veh_id: str) -> dict | None:
    return next((v for v in _all_vehicles() if v.get("id") == veh_id), None)
