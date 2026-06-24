"""
core/decor_sync.py — Continuité de décor entre plans du même axe.

Quand un plan est généré, on peut figer son DÉCOR (fond, personnage retiré) et le
réutiliser comme image de référence pour les plans suivants tournés dans le MÊME
décor et le MÊME axe caméra. Évite que le décor change d'un champ/contrechamp à
l'autre (ex. scène autour d'une table : on revient sur le perso 1 → même décor).

Clé = (décor, axe). Stockage par projet : <data_root>/decor_sync/index.json + PNG.
"""

import os
import json
import shutil


def _dir() -> str:
    from core.context import get_data_root
    d = os.path.join(get_data_root(), "decor_sync")
    os.makedirs(d, exist_ok=True)
    return d


def _index_path() -> str:
    return os.path.join(_dir(), "index.json")


def _load() -> dict:
    try:
        with open(_index_path(), encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _save(data: dict) -> None:
    try:
        with open(_index_path(), "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


def _key(decor, axis) -> str:
    decor = str(decor or "").strip().lower()
    axis = str(axis or "").strip().lower()
    return f"{decor}::{axis}"


def get_synced_bg(decor, axis) -> str | None:
    """Renvoie le chemin du fond figé pour (décor, axe), ou None s'il n'existe pas."""
    if not decor or not axis:
        return None
    p = _load().get(_key(decor, axis), "")
    return p if p and os.path.isfile(p) else None


def set_synced_bg(decor, axis, src_path: str) -> str:
    """Enregistre src_path comme fond de référence pour (décor, axe) ; renvoie le
    chemin stocké (copie locale) ou "" en cas d'échec."""
    if not decor or not axis or not src_path or not os.path.isfile(src_path):
        return ""
    safe = "".join(c for c in _key(decor, axis) if c.isalnum() or c in " -_") \
        .replace(" ", "_").strip("_") or "decor"
    dst = os.path.join(_dir(), f"bg_{safe}.png")
    try:
        if os.path.abspath(src_path) != os.path.abspath(dst):
            shutil.copy2(src_path, dst)
        idx = _load()
        idx[_key(decor, axis)] = dst
        _save(idx)
        return dst
    except Exception:
        return ""


def clear() -> None:
    """Vide le cache de fonds synchronisés du projet courant."""
    _save({})
