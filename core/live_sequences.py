"""
core/live_sequences.py — Données des séquences PANDORA | Live.

Deux types (kind) :
  - "live"    → Séquences Live    (découpage type storyboard)
  - "mapping" → Séquences Mapping (séquence continue mappée sur un bâtiment)

Chaque séquence = un dict :
  {
    "kind": "live" | "mapping",
    "segments": [ {id, number, action, shot_size, camera_movement, duration, prompt, image_path}, ... ],
    "mapping_source": "",   # mapping uniquement : chemin de l'image (façade)
    "continuous": True,     # mapping uniquement : raccord continu (un seul plan long)
  }

Stockage : <data_root>/live_seq_<kind>/index.json
Isolé par projet. Aucune dépendance UI.
"""

import os
import json
import uuid

import core.context as ctx

_KINDS = ("live", "mapping")


def _base_dir(kind: str) -> str:
    d = os.path.join(ctx.get_data_root(), f"live_seq_{kind}")
    os.makedirs(d, exist_ok=True)
    return d


def _index_path(kind: str) -> str:
    return os.path.join(_base_dir(kind), "index.json")


def _default(kind: str) -> dict:
    return {"kind": kind, "segments": [], "mapping_source": "", "continuous": True}


def load(kind: str) -> dict:
    path = _index_path(kind)
    if not os.path.isfile(path):
        return _default(kind)
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict):
            return _default(kind)
        data.setdefault("kind", kind)
        data.setdefault("segments", [])
        data.setdefault("mapping_source", "")
        data.setdefault("continuous", True)
        return data
    except Exception:
        return _default(kind)


def save(kind: str, data: dict):
    data = dict(data or {})
    data["kind"] = kind
    with open(_index_path(kind), "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def new_segment(number: int = 1) -> dict:
    return {
        "id": uuid.uuid4().hex[:12],
        "number": number,
        "action": "",
        "shot_size": "",
        "camera_movement": "",
        "duration": 5,
        "prompt": "",
        "image_path": "",
    }


def set_segments(kind: str, segments: list):
    """Remplace tous les segments (renumérote 1..N) et sauvegarde."""
    data = load(kind)
    for i, s in enumerate(segments, 1):
        s["number"] = i
        s.setdefault("id", uuid.uuid4().hex[:12])
    data["segments"] = segments
    save(kind, data)
    return data
