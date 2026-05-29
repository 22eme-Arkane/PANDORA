import json
import os
import uuid
from datetime import datetime

from core.paths import APP_ROOT as _ROOT
_REGISTRY     = os.path.join(_ROOT, "data", "recent_projects.json")
_DEFAULT_DIR  = os.path.join(os.path.expanduser("~"), "Documents", "PANDORA Projects")


# ── Registre des projets récents ──────────────────────────────────────────────

def _load_registry() -> list[str]:
    if not os.path.isfile(_REGISTRY):
        _migrate_legacy()
    if not os.path.isfile(_REGISTRY):
        return []
    try:
        with open(_REGISTRY, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []


def _migrate_legacy():
    """Migration one-shot depuis l'ancien dossier data/projects/."""
    old_dir = os.path.join(_ROOT, "data", "projects")
    if not os.path.isdir(old_dir):
        return
    paths = []
    for name in sorted(os.listdir(old_dir)):
        folder = os.path.join(old_dir, name)
        # Accept project.json (old) or any named .json (new)
        if os.path.isfile(os.path.join(folder, "project.json")) or any(
            f.endswith(".json") for f in os.listdir(folder) if os.path.isfile(os.path.join(folder, f))
        ):
            paths.append(os.path.normpath(folder))
    if paths:
        _save_registry(paths)


def _init_project_dirs(folder: str):
    """Crée les sous-dossiers data/ dans le dossier du projet."""
    for sub in (
        "storyboard",
        "storyboard/frames",
        "decors/images",
        "castings/images",
        "accessories/images",
        "vehicles/images",
        "scenarios",
        "hmc/images",
        "Seedance",
        "doublage",
    ):
        os.makedirs(os.path.join(folder, "data", sub), exist_ok=True)


def _save_registry(paths: list[str]):
    os.makedirs(os.path.dirname(_REGISTRY), exist_ok=True)
    with open(_REGISTRY, "w", encoding="utf-8") as f:
        json.dump(paths, f, indent=2, ensure_ascii=False)


def add_to_recent(path: str):
    """Ajoute un chemin de projet en tête du registre."""
    path  = os.path.normpath(path)
    paths = [p for p in _load_registry() if os.path.normpath(p) != path]
    paths.insert(0, path)
    _save_registry(paths[:20])


_last_pruned: list[str] = []


def get_last_pruned() -> list[str]:
    """Chemins des projets introuvables retirés lors du dernier appel à list_recent()."""
    return list(_last_pruned)


def list_recent(max_count: int = 9) -> list[dict]:
    """Retourne les projets récents valides, triés par ordre d'ouverture."""
    global _last_pruned
    paths   = _load_registry()
    result  = []
    valid   = []
    for p in paths:
        data = load_project(p)
        if data:
            result.append(data)
            valid.append(p)
    pruned = [p for p in paths if p not in valid]
    _last_pruned = pruned
    if pruned:
        _save_registry(valid)
    return result[:max_count]


def scan_folder(folder: str):
    """Scanne un dossier à la recherche de projets PANDORA non encore enregistrés.

    Chaque sous-dossier qui contient un fichier JSON valide (id + name) est ajouté
    en queue du registre s'il n'y était pas déjà.
    """
    if not os.path.isdir(folder):
        return
    current = {os.path.normpath(p) for p in _load_registry()}
    new_paths: list[str] = []
    try:
        entries = sorted(os.listdir(folder))
    except OSError:
        return
    for name in entries:
        sub = os.path.normpath(os.path.join(folder, name))
        if not os.path.isdir(sub) or sub in current:
            continue
        data = load_project(sub)
        if data:
            new_paths.append(sub)
            current.add(sub)           # évite les doublons dans la même passe
    if new_paths:
        merged = list(_load_registry()) + new_paths
        _save_registry(merged[:50])


# ── CRUD projets ──────────────────────────────────────────────────────────────

def create_project(name: str, parent_dir: str = "", mode: str = "cinema") -> dict:
    """Crée un nouveau projet dans parent_dir (défaut : Documents/PANDORA Projects)."""
    base = parent_dir.strip() or _DEFAULT_DIR
    os.makedirs(base, exist_ok=True)

    safe = "".join(c for c in name if c.isalnum() or c in " -_").strip() or "Projet"
    folder = os.path.join(base, safe)
    i = 2
    while os.path.exists(folder):
        folder = os.path.join(base, f"{safe}_{i}")
        i += 1
    os.makedirs(folder)
    _init_project_dirs(folder)

    # Ensure the style_refs write dir exists so custom categories are available immediately
    from core.paths import APP_ROOT as _pr
    os.makedirs(os.path.join(_pr, "assets", "style_refs"), exist_ok=True)

    now  = datetime.now().isoformat()
    data = {
        "id":          str(uuid.uuid4()),
        "name":        name,
        "mode":        mode,
        "created_at":  now,
        "modified_at": now,
        "thumbnail":   "",
        "_path":       folder,
    }
    _save(data)
    add_to_recent(folder)
    return data


def load_project(path: str) -> dict | None:
    """Charge un projet depuis son dossier. Retourne None si invalide."""
    if not os.path.isdir(path):
        return None
    # Scan root-level .json files for a valid project descriptor
    for fname in sorted(os.listdir(path)):
        if not fname.endswith(".json"):
            continue
        fpath = os.path.join(path, fname)
        if not os.path.isfile(fpath):
            continue
        try:
            with open(fpath, "r", encoding="utf-8") as f:
                data = json.load(f)
            if not isinstance(data, dict) or "id" not in data or "name" not in data:
                continue
            data["_path"] = path
            if not data.get("id"):
                data["id"] = str(uuid.uuid4())
            _save(data)  # renames to {safe_name}.json and removes project.json if needed
            return data
        except Exception:
            continue
    return None


def rename_project(data: dict, new_name: str) -> dict:
    """Renomme un projet (champ name uniquement — le dossier reste inchangé)."""
    old_safe = "".join(c for c in data.get("name", "") if c.isalnum() or c in " -_").strip() or "Projet"
    data["name"] = new_name.strip() or data["name"]
    data["modified_at"] = datetime.now().isoformat()
    _save(data)
    # Remove old JSON file if its name differs from the new one
    path = data.get("_path", "")
    if path:
        new_safe = "".join(c for c in data["name"] if c.isalnum() or c in " -_").strip() or "Projet"
        if old_safe != new_safe:
            old_file = os.path.join(path, f"{old_safe}.json")
            if os.path.isfile(old_file):
                try:
                    os.remove(old_file)
                except OSError:
                    pass
        add_to_recent(path)
    return data


def touch_project(data: dict):
    """Met à jour modified_at, sauvegarde, et remonte dans le registre."""
    data["modified_at"] = datetime.now().isoformat()
    _save(data)
    path = data.get("_path", "")
    if path:
        add_to_recent(path)


def _save(data: dict):
    path = data.get("_path", "")
    if not path:
        return
    name = data.get("name", "Projet")
    safe = "".join(c for c in name if c.isalnum() or c in " -_").strip() or "Projet"
    new_file = os.path.join(path, f"{safe}.json")
    payload = {k: v for k, v in data.items() if not k.startswith("_")}
    with open(new_file, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)
    # Remove legacy project.json if it differs from the new file
    legacy = os.path.join(path, "project.json")
    if os.path.isfile(legacy) and os.path.normpath(legacy) != os.path.normpath(new_file):
        try:
            os.remove(legacy)
        except OSError:
            pass
