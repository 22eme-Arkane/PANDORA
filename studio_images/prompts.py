"""
Bibliothèque de prompts — sauvegarde globale des prompts qui marchent bien.

Stockée dans studio_images/prompts.json (liste de {name, prompt}), partagée
entre tous les projets : un bon prompt se réutilise partout.
"""

import json
import os

# Même dossier inscriptible que config.json (frozen → %LOCALAPPDATA%\PANDORA\…).
try:
    from config import user_data_dir as _user_data_dir
except Exception:
    def _user_data_dir() -> str:
        return os.path.dirname(os.path.abspath(__file__))

_FILE = os.path.join(_user_data_dir(), "prompts.json")


def load_prompts() -> list:
    """Retourne la liste [{name, prompt}] (vide si aucun)."""
    if os.path.isfile(_FILE):
        try:
            with open(_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, list):
                return data
        except Exception:
            pass
    return []


def _write(items: list):
    try:
        with open(_FILE, "w", encoding="utf-8") as f:
            json.dump(items, f, indent=2, ensure_ascii=False)
    except Exception:
        pass


def save_prompt(name: str, text: str):
    """Ajoute le prompt, ou met à jour s'il existe déjà sous ce nom."""
    name = (name or "").strip()
    if not name or not (text or "").strip():
        return
    items = load_prompts()
    for it in items:
        if it.get("name") == name:
            it["prompt"] = text
            _write(items)
            return
    items.append({"name": name, "prompt": text})
    _write(items)


def delete_prompt(name: str):
    items = [it for it in load_prompts() if it.get("name") != name]
    _write(items)
