"""
Projets Studio Images — sauvegarde/reprise d'une session de création.

Un projet = un dossier sous <output_dir>/Projets/<slug>/ contenant :
  - project.json : nom, dates, réglages, fil de discussion (historique chat)
  - les images générées dans ce projet (PNG/SVG)

Le fil de discussion est stocké au schéma interne de chat.py (chemins d'images,
pas de base64) → sérialisable en JSON et ré-envoyable à Claude tel quel.
"""

import json
import os
import re

from config import load_config, default_output_dir


def projects_root() -> str:
    out = load_config().get("output_dir") or default_output_dir()
    root = os.path.join(out, "Projets")
    os.makedirs(root, exist_ok=True)
    return root


def _slug(name: str) -> str:
    s = re.sub(r"[^\w\- ]", "", name, flags=re.UNICODE).strip().replace(" ", "_")
    return s[:60] or "projet"


def project_dir(pid: str) -> str:
    d = os.path.join(projects_root(), pid)
    os.makedirs(d, exist_ok=True)
    return d


def _json_path(pid: str) -> str:
    return os.path.join(project_dir(pid), "project.json")


def list_projects() -> list:
    """Retourne [{id, name, updated}] trié par date de mise à jour décroissante."""
    items = []
    root = projects_root()
    for pid in os.listdir(root):
        jp = os.path.join(root, pid, "project.json")
        if os.path.isfile(jp):
            try:
                with open(jp, "r", encoding="utf-8") as f:
                    data = json.load(f)
                items.append({"id": pid,
                              "name": data.get("name", pid),
                              "updated": data.get("updated", 0)})
            except Exception:
                pass
    items.sort(key=lambda x: x["updated"], reverse=True)
    return items


def _unique_id(name: str) -> str:
    base = _slug(name)
    pid = base
    n = 2
    while os.path.exists(os.path.join(projects_root(), pid)):
        pid = f"{base}_{n}"
        n += 1
    return pid


def create_project(name: str, now: int) -> str:
    pid = _unique_id(name)
    data = {
        "name":      name.strip() or pid,
        "created":   now,
        "updated":   now,
        "settings":  {},
        "history":   [],
        "last_image": "",
    }
    save_project(pid, data)
    return pid


def load_project(pid: str) -> dict:
    with open(_json_path(pid), "r", encoding="utf-8") as f:
        return json.load(f)


def save_project(pid: str, data: dict):
    with open(_json_path(pid), "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
