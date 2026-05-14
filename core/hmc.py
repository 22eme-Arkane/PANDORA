import json
import os
import uuid
from datetime import datetime

from core.paths import APP_ROOT as _ROOT


def _hmc_dir() -> str:
    from core.context import get_data_root
    return os.path.join(get_data_root(), "hmc")

TYPES = ["Habit", "Maquillage", "Coiffure"]


def _ensure():
    os.makedirs(_hmc_dir(), exist_ok=True)
    os.makedirs(os.path.join(_hmc_dir(), "images"), exist_ok=True)


def images_dir() -> str:
    _ensure()
    return os.path.join(_hmc_dir(), "images")


def _all_hmc_items() -> list[dict]:
    index_file = os.path.join(_hmc_dir(), "index.json")
    if not os.path.isfile(index_file):
        return []
    try:
        with open(index_file, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []


def list_hmc_items() -> list[dict]:
    items = _all_hmc_items()
    from core.context import get_project_id
    pid = get_project_id()
    if pid:
        return [h for h in items if h.get("project_id") == pid]
    return items


def save_hmc_item(data: dict) -> dict:
    from core.context import get_project_id
    _ensure()
    pid = get_project_id()
    if pid and not data.get("project_id"):
        data["project_id"] = pid
    items = _all_hmc_items()
    if not data.get("id"):
        data["id"] = str(uuid.uuid4())
    if not data.get("created_at"):
        data["created_at"] = datetime.now().isoformat()
    data["updated_at"] = datetime.now().isoformat()
    data.setdefault("assigned_to", [])
    data.setdefault("hmc_type", "Habit")

    idx = next((i for i, h in enumerate(items) if h.get("id") == data["id"]), None)
    if idx is not None:
        items[idx] = data
    else:
        items.append(data)

    with open(os.path.join(_hmc_dir(), "index.json"), "w", encoding="utf-8") as f:
        json.dump(items, f, indent=2, ensure_ascii=False)
    return data


def delete_hmc_item(item_id: str):
    _ensure()
    items = [h for h in _all_hmc_items() if h.get("id") != item_id]
    with open(os.path.join(_hmc_dir(), "index.json"), "w", encoding="utf-8") as f:
        json.dump(items, f, indent=2, ensure_ascii=False)


def get_hmc_item(item_id: str) -> dict | None:
    return next((h for h in _all_hmc_items() if h.get("id") == item_id), None)


def assign_to_character(item_id: str, char_id: str):
    """Lie un item HMC à un personnage (bidirectionnel)."""
    import core.casting as casting_api
    item = get_hmc_item(item_id)
    if not item:
        return
    if char_id not in item.get("assigned_to", []):
        item.setdefault("assigned_to", []).append(char_id)
        save_hmc_item(item)
    char = casting_api.get_character(char_id)
    if char:
        if item_id not in char.get("hmc_ids", []):
            char.setdefault("hmc_ids", []).append(item_id)
            casting_api.save_character(char)


def unassign_from_character(item_id: str, char_id: str):
    """Retire le lien entre un item HMC et un personnage."""
    import core.casting as casting_api
    item = get_hmc_item(item_id)
    if item:
        item["assigned_to"] = [c for c in item.get("assigned_to", []) if c != char_id]
        save_hmc_item(item)
    char = casting_api.get_character(char_id)
    if char:
        char["hmc_ids"] = [h for h in char.get("hmc_ids", []) if h != item_id]
        casting_api.save_character(char)
