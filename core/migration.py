"""One-time migration: assigns all legacy data to the oldest (first-created) project.

v2 replaces v1: it resets all project_id fields and re-tags everything with the
oldest project, so the result is correct even if v1 ran with the wrong project ID.
"""

import json
import os

from core.paths import APP_ROOT as _ROOT
_FLAG_V1   = os.path.join(_ROOT, "data", "migrated_v1.flag")
_FLAG_V2   = os.path.join(_ROOT, "data", "migrated_v2.flag")


def _oldest_project_id() -> str:
    """ID of the earliest-created project from the registry."""
    registry = os.path.join(_ROOT, "data", "recent_projects.json")
    if not os.path.isfile(registry):
        return ""
    try:
        with open(registry, "r", encoding="utf-8") as f:
            paths = json.load(f)
    except Exception:
        return ""

    best_id = best_date = ""
    for p in paths:
        pfile = os.path.join(p, "project.json")
        if not os.path.isfile(pfile):
            continue
        try:
            with open(pfile, "r", encoding="utf-8") as f:
                proj = json.load(f)
        except Exception:
            continue
        pid  = proj.get("id", "")
        date = proj.get("created_at", "")
        if pid and date and (best_date == "" or date < best_date):
            best_date, best_id = date, pid
    return best_id


def migrate_legacy_data(project_id: str = ""):
    """Assign all data items to the oldest project (idempotent, runs once).

    v2 resets *every* project_id before re-tagging, so it also fixes items that
    were incorrectly tagged by an earlier (v1) migration run.
    """
    if os.path.exists(_FLAG_V2):
        return

    target_id = _oldest_project_id() or project_id
    if not target_id:
        return

    _reset_and_tag(os.path.join(_ROOT, "data", "scenarios",   "index.json"),    target_id)
    _reset_and_tag(os.path.join(_ROOT, "data", "castings",    "index.json"),    target_id)
    _reset_and_tag(os.path.join(_ROOT, "data", "accessories", "index.json"),    target_id)
    _reset_and_tag(os.path.join(_ROOT, "data", "decors",      "index.json"),    target_id)
    _reset_and_tag(os.path.join(_ROOT, "data", "hmc",         "index.json"),    target_id)
    _reset_and_tag(os.path.join(_ROOT, "data", "storyboard",  "index.json"),    target_id)
    _reset_and_tag(os.path.join(_ROOT, "data", "storyboard",  "versions.json"), target_id)

    os.makedirs(os.path.dirname(_FLAG_V2), exist_ok=True)
    with open(_FLAG_V2, "w", encoding="utf-8") as f:
        f.write(target_id)


def _reset_and_tag(path: str, project_id: str):
    """Overwrite every item's project_id with project_id."""
    if not os.path.isfile(path):
        return
    try:
        with open(path, "r", encoding="utf-8") as f:
            items = json.load(f)
        for item in items:
            if isinstance(item, dict):
                item["project_id"] = project_id
        with open(path, "w", encoding="utf-8") as f:
            json.dump(items, f, indent=2, ensure_ascii=False)
    except Exception:
        pass
