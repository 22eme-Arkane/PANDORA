import json
import os
import uuid
from datetime import datetime

from core.paths import APP_ROOT as _ROOT


def _acc_dir() -> str:
    from core.context import get_data_root
    return os.path.join(get_data_root(), "accessories")

CATEGORIES = [
    "Bijoux", "Armes", "Électronique", "Mobilier",
    "Vêtement", "Véhicule", "Document", "Autre…",
]


def _ensure():
    os.makedirs(_acc_dir(), exist_ok=True)
    os.makedirs(os.path.join(_acc_dir(), "images"), exist_ok=True)


def images_dir() -> str:
    _ensure()
    return os.path.join(_acc_dir(), "images")


def _all_accessories() -> list[dict]:
    index_file = os.path.join(_acc_dir(), "index.json")
    if not os.path.isfile(index_file):
        return []
    try:
        with open(index_file, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []


def list_accessories() -> list[dict]:
    items = _all_accessories()
    from core.context import get_project_id
    pid = get_project_id()
    if pid:
        return [a for a in items if a.get("project_id") == pid]
    return items


def save_accessory(data: dict) -> dict:
    from core.context import get_project_id
    _ensure()
    pid = get_project_id()
    if pid and not data.get("project_id"):
        data["project_id"] = pid
    items = _all_accessories()
    if not data.get("id"):
        data["id"] = str(uuid.uuid4())
    if not data.get("created_at"):
        data["created_at"] = datetime.now().isoformat()
    data["updated_at"] = datetime.now().isoformat()
    data.setdefault("assigned_to", [])

    idx = next((i for i, a in enumerate(items) if a.get("id") == data["id"]), None)
    if idx is not None:
        items[idx] = data
    else:
        items.append(data)

    with open(os.path.join(_acc_dir(), "index.json"), "w", encoding="utf-8") as f:
        json.dump(items, f, indent=2, ensure_ascii=False)
    return data


def delete_accessory(acc_id: str):
    _ensure()
    items = [a for a in _all_accessories() if a.get("id") != acc_id]
    with open(os.path.join(_acc_dir(), "index.json"), "w", encoding="utf-8") as f:
        json.dump(items, f, indent=2, ensure_ascii=False)


def get_accessory(acc_id: str) -> dict | None:
    return next((a for a in _all_accessories() if a.get("id") == acc_id), None)


def assign_to_character(acc_id: str, char_id: str):
    """Lie un accessoire à un personnage (bidirectionnel)."""
    import core.casting as casting_api
    acc = get_accessory(acc_id)
    if not acc:
        return
    if char_id not in acc.get("assigned_to", []):
        acc.setdefault("assigned_to", []).append(char_id)
        save_accessory(acc)
    char = casting_api.get_character(char_id)
    if char:
        if acc_id not in char.get("accessory_ids", []):
            char.setdefault("accessory_ids", []).append(acc_id)
            casting_api.save_character(char)


def unassign_from_character(acc_id: str, char_id: str):
    """Retire le lien entre un accessoire et un personnage."""
    import core.casting as casting_api
    acc = get_accessory(acc_id)
    if acc:
        acc["assigned_to"] = [c for c in acc.get("assigned_to", []) if c != char_id]
        save_accessory(acc)
    char = casting_api.get_character(char_id)
    if char:
        char["accessory_ids"] = [a for a in char.get("accessory_ids", []) if a != acc_id]
        casting_api.save_character(char)
