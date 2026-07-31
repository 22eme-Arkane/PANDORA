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
    _note_spend(entry)


def _note_spend(entry: dict):
    """Reporte la génération dans le journal de dépenses du PROJET.

    Point de branchement unique : les douze appels à `save_to_history` couvrent
    toutes les générations vidéo (T2V, I2V, Extension, Référence, DaVinci,
    Live). Le coût est ESTIMÉ avec la même grille que l'estimation affichée
    avant de lancer — c'est le seul chiffre que PANDORA connaisse, la facture
    réelle appartient au fournisseur. Ne lève jamais : un journal muet ne doit
    pas faire échouer une génération déjà payée."""
    try:
        from core import pricing, spend
        _model = (entry.get("model") or entry.get("engine") or "").strip()
        _res   = (entry.get("resolution") or "").strip()
        try:
            _dur = float(entry.get("duration") or 0)
        except (TypeError, ValueError):
            _dur = 0.0
        _cost, _mode = pricing.estimate(_model, _res, _dur, 1)
        _bits = [b for b in (_res, f"{_dur:g}s" if _dur else "") if b]
        spend.record(
            spend.KIND_VIDEO, _model or "moteur vidéo",
            (entry.get("prompt") or entry.get("title") or "Génération vidéo")[:90],
            _cost, "  ·  ".join(_bits))
    except Exception:
        pass


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
