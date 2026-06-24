"""Global project context — thread-safe single-project state."""
import os
import sys

_project_id:   str = ""
_project_path: str = ""

if getattr(sys, "frozen", False):
    _PLUGIN_ROOT = os.path.join(os.environ.get("LOCALAPPDATA", os.path.expanduser("~")), "PANDORA")
else:
    _PLUGIN_ROOT = os.path.dirname(os.path.dirname(__file__))


def get_project_id() -> str:
    return _project_id


def set_project_id(pid: str):
    global _project_id
    _project_id = pid or ""


def get_project_path() -> str:
    return _project_path


def set_project_path(ppath: str):
    global _project_path
    _project_path = ppath or ""


def get_data_root() -> str:
    """Returns <project_path>/data if a project is open, else the plugin's data/ folder."""
    p = _project_path
    if p:
        return os.path.join(p, "data")
    return os.path.join(_PLUGIN_ROOT, "data")


def get_project_name() -> str:
    """Nom lisible du projet courant (depuis son descripteur racine, sans effet de
    bord), ou "" si aucun projet n'est ouvert. Repli sur le nom du dossier."""
    p = _project_path
    if not p or not os.path.isdir(p):
        return ""
    import json
    try:
        for fname in sorted(os.listdir(p)):
            if not fname.endswith(".json"):
                continue
            fpath = os.path.join(p, fname)
            if not os.path.isfile(fpath):
                continue
            try:
                with open(fpath, "r", encoding="utf-8") as f:
                    data = json.load(f)
            except Exception:
                continue
            if isinstance(data, dict) and data.get("id") and data.get("name"):
                return str(data["name"]).strip()
    except OSError:
        pass
    return os.path.basename(os.path.normpath(p))
