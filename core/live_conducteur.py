"""
core/live_conducteur.py — Données du « Conducteur » PANDORA | Live.

Le Conducteur est l'équivalent Live du scénario : on y écrit la trame de la
performance, et on choisit son MODE :
  - "live"    → la trame sera découpée en Séquences Live
  - "mapping" → la trame sera découpée en Séquences Mapping (façade verrouillée)

Stockage : <data_root>/live_conducteur/index.json   (isolé par projet)
Aucune dépendance UI.
"""

import os
import json

import core.context as ctx


def _path() -> str:
    d = os.path.join(ctx.get_data_root(), "live_conducteur")
    os.makedirs(d, exist_ok=True)
    return os.path.join(d, "index.json")


def _default() -> dict:
    return {"text": "", "mode": "live"}


def load() -> dict:
    p = _path()
    if not os.path.isfile(p):
        return _default()
    try:
        with open(p, "r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict):
            return _default()
        data.setdefault("text", "")
        data.setdefault("mode", "live")
        return data
    except Exception:
        return _default()


def save(text: str, mode: str):
    with open(_path(), "w", encoding="utf-8") as f:
        json.dump({"text": text, "mode": mode if mode in ("live", "mapping") else "live"},
                  f, ensure_ascii=False, indent=2)
