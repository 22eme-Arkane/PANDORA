"""
core/ref_library.py — Bibliothèque GLOBALE d'analyses de références visuelles (Live).

Une analyse de moodboard (101 images décodées + synthèse de direction artistique)
coûte cher à produire : on la sauvegarde pour la réutiliser d'un projet à l'autre.

Stockage : <APP_ROOT>/data/live_ref_library/<slug>.json — global, PAS par projet
(c'est tout l'intérêt : mêmes références visuelles → même direction artistique).

Format d'une entrée :
{
  "name":     "Océan originel",
  "mode":     "live" | "mapping",
  "analysis": "<texte complet : analyses par image + synthèse DA>",
  "images":   ["C:/.../ref1.jpg", ...],   # chemins d'origine (restaurés s'ils existent)
  "date":     "2026-06-11 14:32",
}
"""

import json
import os
import re
import time

from core.paths import APP_ROOT

# Surchargé par les tests (harnais headless) pour ne pas toucher la vraie bibliothèque.
LIB_DIR_OVERRIDE: str | None = None


def _lib_dir() -> str:
    d = LIB_DIR_OVERRIDE or os.path.join(APP_ROOT, "data", "live_ref_library")
    os.makedirs(d, exist_ok=True)
    return d


def _slug(name: str) -> str:
    s = re.sub(r"[^\w\- ]", "", name, flags=re.UNICODE).strip().replace(" ", "_")
    return s[:60] or "analyse"


def save_analysis(name: str, analysis: str, images: list, mode: str = "live") -> str:
    """Sauvegarde (ou écrase si même nom) ; renvoie le chemin du fichier."""
    name = (name or "").strip() or "Analyse sans titre"
    entry = {
        "name":     name,
        "mode":     mode if mode in ("live", "mapping") else "live",
        "analysis": analysis or "",
        "images":   [p for p in (images or []) if p],
        "date":     time.strftime("%Y-%m-%d %H:%M"),
    }
    path = os.path.join(_lib_dir(), _slug(name) + ".json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(entry, f, ensure_ascii=False, indent=2)
    return path


def list_analyses() -> list:
    """Toutes les analyses sauvegardées, la plus récente en premier."""
    out = []
    d = _lib_dir()
    for fn in os.listdir(d):
        if not fn.endswith(".json"):
            continue
        try:
            with open(os.path.join(d, fn), encoding="utf-8") as f:
                e = json.load(f)
            e["_file"] = os.path.join(d, fn)
            out.append(e)
        except Exception:
            continue
    out.sort(key=lambda e: e.get("date", ""), reverse=True)
    return out


def load_analysis(file_path: str) -> dict | None:
    try:
        with open(file_path, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def delete_analysis(file_path: str) -> bool:
    try:
        os.remove(file_path)
        return True
    except OSError:
        return False
