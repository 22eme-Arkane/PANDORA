import json
import os
import uuid
from datetime import datetime

from core.paths import APP_ROOT as _ROOT


def _dec_dir() -> str:
    from core.context import get_data_root
    return os.path.join(get_data_root(), "decors")

CATEGORIES = [
    "Intérieur",
    "Extérieur",
    "Studio",
    "Urbain",
    "Rural",
    "Aquatique",
    "Aérien",
    "Fantastique",
    "Industriel",
    "Historique",
    "Autre",
]


def _ensure():
    os.makedirs(_dec_dir(), exist_ok=True)
    os.makedirs(os.path.join(_dec_dir(), "images"), exist_ok=True)


def images_dir() -> str:
    _ensure()
    return os.path.join(_dec_dir(), "images")


def _load_index() -> list[dict]:
    _ensure()
    index_file = os.path.join(_dec_dir(), "index.json")
    if not os.path.exists(index_file):
        return []
    with open(index_file, "r", encoding="utf-8") as f:
        return json.load(f)


def _save_index(index: list[dict]):
    _ensure()
    with open(os.path.join(_dec_dir(), "index.json"), "w", encoding="utf-8") as f:
        json.dump(index, f, ensure_ascii=False, indent=2)


def list_decors() -> list[dict]:
    from core.context import get_project_id
    pid = get_project_id()
    index = _load_index()
    if pid:
        return [d for d in index if d.get("project_id") == pid]
    return index


def get_decor(decor_id: str) -> dict | None:
    index = _load_index()
    for decor in index:
        if decor.get("id") == decor_id:
            return decor
    return None


def save_decor(data: dict) -> dict:
    from core.context import get_project_id
    _ensure()
    pid = get_project_id()
    if pid and not data.get("project_id"):
        data["project_id"] = pid
    index = _load_index()
    now = datetime.now().isoformat()

    if not data.get("id"):
        data["id"] = str(uuid.uuid4())
        data["created_at"] = now
        data["updated_at"] = now
        data.setdefault("name", "")
        data.setdefault("category", "Autre")
        data.setdefault("prompt", "")
        data.setdefault("image_path", "")
        data.setdefault("floor_plan", "")   # plan vu de dessus (Mise en scène / Plan de feu)
        data.setdefault("ref_paths", [])
        data.setdefault("assigned_to", [])
        data.setdefault("assigned_sequences", [])
        data.setdefault("assigned_shots", [])
        index.append(data)
    else:
        data["updated_at"] = now
        replaced = False
        for i, decor in enumerate(index):
            if decor.get("id") == data["id"]:
                index[i] = data
                replaced = True
                break
        if not replaced:
            data.setdefault("created_at", now)
            index.append(data)

    _save_index(index)
    return data


def delete_decor(decor_id: str):
    index = _load_index()
    index = [d for d in index if d.get("id") != decor_id]
    _save_index(index)


def set_floor_plan(decor_id: str, path: str) -> bool:
    """Associe un plan vu de dessus (image) à un décor — source unique partagée
    par la page Décors, la Mise en scène et le Plan de feu. True si écrit."""
    index = _load_index()
    for decor in index:
        if decor.get("id") == decor_id:
            decor["floor_plan"] = path or ""
            decor["updated_at"] = datetime.now().isoformat()
            _save_index(index)
            return True
    return False


def floor_plan_for_shot(shot: dict) -> str:
    """Plan vu de dessus à utiliser pour un plan du storyboard : celui de son
    décor assigné (decor_id), sinon vide."""
    did = (shot or {}).get("decor_id")
    if not did:
        return ""
    dec = get_decor(did)
    return (dec or {}).get("floor_plan", "") if dec else ""
