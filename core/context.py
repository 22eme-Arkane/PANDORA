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
