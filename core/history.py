import json
import os

from core.paths import APP_ROOT as _ROOT
_DATA_DIR = os.path.join(_ROOT, "data")
_HISTORY_FILE = os.path.join(_DATA_DIR, "history.json")
_MAX_ENTRIES = 50


def load_history() -> list:
    os.makedirs(_DATA_DIR, exist_ok=True)
    if os.path.exists(_HISTORY_FILE):
        with open(_HISTORY_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return []


def save_to_history(entry: dict):
    history = load_history()
    history.insert(0, entry)
    history = history[:_MAX_ENTRIES]
    with open(_HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(history, f, ensure_ascii=False, indent=2)
