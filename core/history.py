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


def find_entry_by_path(path: str) -> dict | None:
    """Entrée d'historique (avec GRAINE > 0) correspondant au fichier `path`, ou None.
    Match par chemin exact puis par nom de fichier. Sert à « Reprendre en HD » depuis
    la Vidéothèque : récupérer la graine + le prompt du clip pour le régénérer (parité
    avec le bouton « ↑ HD » de l'Historique)."""
    if not path:
        return None
    base = os.path.basename(path)
    for e in load_history():
        lp = e.get("local_path") or e.get("path") or ""
        if not lp:
            continue
        try:
            seed = int(e.get("seed") or 0)
        except (TypeError, ValueError):
            seed = 0
        if seed > 0 and (lp == path or os.path.basename(lp) == base):
            return e
    return None
