"""
core/image_library.py — Bibliothèque GLOBALE d'images de référence (Cinéma + Live).

Une seule bibliothèque, partagée entre TOUS les projets et TOUTES les pages
(références du scénario/conducteur, casting, décors, accessoires, HMC,
véhicules, templates Studio IA). On la remplit une fois, on pioche partout.

Principe clé : les images sont COPIÉES dans la bibliothèque — plus jamais de
chemin cassé parce qu'un fichier a bougé sur le disque dur.

Stockage : <APP_ROOT>/data/image_library/
  index.json            # [{key, name, created}]
  <key>/*.jpg|png|webp  # les images de la collection
"""

import json
import os
import re
import shutil
import time

from core.paths import APP_ROOT

_IMG_EXTS = (".png", ".jpg", ".jpeg", ".webp", ".bmp")

# Surchargé par les harnais de tests pour ne pas toucher la vraie bibliothèque.
LIB_DIR_OVERRIDE: str | None = None


def _lib_dir() -> str:
    d = LIB_DIR_OVERRIDE or os.path.join(APP_ROOT, "data", "image_library")
    os.makedirs(d, exist_ok=True)
    return d


def _index_path() -> str:
    return os.path.join(_lib_dir(), "index.json")


def _read_index() -> list:
    try:
        with open(_index_path(), encoding="utf-8") as f:
            idx = json.load(f)
        return idx if isinstance(idx, list) else []
    except Exception:
        return []


def _write_index(idx: list) -> None:
    with open(_index_path(), "w", encoding="utf-8") as f:
        json.dump(idx, f, ensure_ascii=False, indent=2)


def _slug(name: str) -> str:
    s = re.sub(r"[^\w\- ]", "", name, flags=re.UNICODE).strip().replace(" ", "_")
    return s[:48] or "collection"


# ── Collections ───────────────────────────────────────────────────────────────

def list_collections() -> list:
    """[{key, name, created, count, cover}] — ordre de l'index (création)."""
    out = []
    for c in _read_index():
        key = c.get("key", "")
        imgs = list_images(key)
        out.append({
            "key":     key,
            "name":    c.get("name", key),
            "created": c.get("created", ""),
            "count":   len(imgs),
            "cover":   imgs[0] if imgs else "",
        })
    return out


def create_collection(name: str) -> str:
    """Crée une collection (clé unique dérivée du nom) ; renvoie sa clé."""
    name = (name or "").strip() or "Collection"
    idx = _read_index()
    base = _slug(name)
    key, i = base, 1
    existing = {c.get("key") for c in idx}
    while key in existing:
        key = f"{base}_{i}"
        i += 1
    os.makedirs(os.path.join(_lib_dir(), key), exist_ok=True)
    idx.append({"key": key, "name": name, "created": time.strftime("%Y-%m-%d %H:%M")})
    _write_index(idx)
    return key


def rename_collection(key: str, new_name: str) -> bool:
    idx = _read_index()
    for c in idx:
        if c.get("key") == key:
            c["name"] = (new_name or "").strip() or c.get("name", key)
            _write_index(idx)
            return True
    return False


def delete_collection(key: str) -> bool:
    """Supprime la collection ET ses images (elles appartiennent à la bibliothèque)."""
    idx = [c for c in _read_index() if c.get("key") != key]
    _write_index(idx)
    d = os.path.join(_lib_dir(), key)
    if os.path.isdir(d):
        shutil.rmtree(d, ignore_errors=True)
    return True


# ── Images ────────────────────────────────────────────────────────────────────

def list_images(key: str) -> list:
    """Chemins des images d'une collection, triés par nom."""
    d = os.path.join(_lib_dir(), key)
    if not key or not os.path.isdir(d):
        return []
    return sorted(
        os.path.join(d, fn) for fn in os.listdir(d)
        if fn.lower().endswith(_IMG_EXTS)
    )


def add_images(key: str, paths: list) -> list:
    """COPIE des fichiers dans la collection (dédoublonnage de nom) ;
    renvoie les chemins des copies."""
    d = os.path.join(_lib_dir(), key)
    if not key:
        return []
    os.makedirs(d, exist_ok=True)
    added = []
    for src in paths or []:
        if not (src and os.path.isfile(src)):
            continue
        fname = os.path.basename(src)
        dst = os.path.join(d, fname)
        if os.path.abspath(src) == os.path.abspath(dst):
            added.append(dst)
            continue
        base, ext = os.path.splitext(fname)
        i = 1
        while os.path.exists(dst):
            dst = os.path.join(d, f"{base}_{i}{ext}")
            i += 1
        try:
            shutil.copy2(src, dst)
            added.append(dst)
        except OSError:
            continue
    return added


def remove_image(path: str) -> bool:
    """Retire une image de la bibliothèque (sécurisé : uniquement dans _lib_dir)."""
    try:
        if os.path.commonpath([os.path.abspath(path),
                               os.path.abspath(_lib_dir())]) != os.path.abspath(_lib_dir()):
            return False
        os.remove(path)
        return True
    except (OSError, ValueError):
        return False
