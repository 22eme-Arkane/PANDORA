import json
import os
import uuid
from datetime import datetime

from core.paths import APP_ROOT as _ROOT


def _cast_dir() -> str:
    from core.context import get_data_root
    return os.path.join(get_data_root(), "castings")


def _ensure():
    os.makedirs(_cast_dir(), exist_ok=True)
    os.makedirs(os.path.join(_cast_dir(), "images"), exist_ok=True)


def images_dir() -> str:
    _ensure()
    return os.path.join(_cast_dir(), "images")


def _all_characters() -> list[dict]:
    index_file = os.path.join(_cast_dir(), "index.json")
    if not os.path.isfile(index_file):
        return []
    try:
        with open(index_file, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []


def list_characters() -> list[dict]:
    index_file = os.path.join(_cast_dir(), "index.json")
    if not os.path.isfile(index_file):
        return []
    try:
        with open(index_file, "r", encoding="utf-8") as f:
            chars = json.load(f)
    except Exception:
        return []
    from core.context import get_project_id
    pid = get_project_id()
    if pid:
        return [c for c in chars if c.get("project_id") == pid]
    return chars


def save_character(data: dict) -> dict:
    from core.context import get_project_id
    _ensure()
    pid = get_project_id()
    if pid and not data.get("project_id"):
        data["project_id"] = pid
    chars = _all_characters()
    if not data.get("id"):
        data["id"] = str(uuid.uuid4())
    if not data.get("created_at"):
        data["created_at"] = datetime.now().isoformat()
    data["updated_at"] = datetime.now().isoformat()

    idx = next((i for i, c in enumerate(chars) if c.get("id") == data["id"]), None)
    if idx is not None:
        chars[idx] = data
    else:
        chars.append(data)

    with open(os.path.join(_cast_dir(), "index.json"), "w", encoding="utf-8") as f:
        json.dump(chars, f, indent=2, ensure_ascii=False)
    return data


def delete_character(char_id: str):
    _ensure()
    chars = [c for c in _all_characters() if c.get("id") != char_id]
    with open(os.path.join(_cast_dir(), "index.json"), "w", encoding="utf-8") as f:
        json.dump(chars, f, indent=2, ensure_ascii=False)


def get_character(char_id: str) -> dict | None:
    return next((c for c in _all_characters() if c.get("id") == char_id), None)
