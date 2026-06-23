"""
core/element_io.py — Sauvegarde / ouverture sur fichier des listes d'éléments.

Donne aux pages Castings, Décors, Accessoires, HMC et Véhicules deux boutons
« Sauvegarder » / « Ouvrir » à côté de la barre de recherche, sur le MÊME
principe que le save/open du storyboard (core.storyboard.export_storyboard_to /
import_storyboard_from) : un fichier .json portable, l'ouverture REMPLACE les
éléments du projet courant (la confirmation est gérée côté UI).

Module GÉNÉRIQUE : il ne connaît aucun module métier en dur. Chaque page lui
passe les callables de son module (list_fn / save_fn / delete_fn). Un seul
fichier, zéro duplication — conforme à la doctrine d'architecture modulaire.

Comme pour le storyboard, seules les MÉTADONNÉES JSON sont sauvegardées : les
images restent référencées par leur chemin (non copiées). Les fonctions delete_*
des modules ne suppriment que l'entrée d'index, jamais les fichiers image —
l'ouverture (remplacement) ne détruit donc aucune image sur le disque.
"""

import json
import os
from datetime import datetime

# Type machine (pandora_kind) → libellé lisible. Sert au contrôle de cohérence à
# l'ouverture (on n'ouvre pas un fichier « casting » dans la page Décors) ET au
# nom de fichier suggéré.
KIND_LABELS = {
    "casting":     "casting",
    "decors":      "décors",
    "accessories": "accessoires",
    "hmc":         "HMC",
    "vehicles":    "véhicules",
}


def file_suffix(kind: str) -> str:
    """Suffixe ASCII pour le nom de fichier suggéré (sans accents)."""
    return {
        "casting":     "casting",
        "decors":      "decors",
        "accessories": "accessoires",
        "hmc":         "hmc",
        "vehicles":    "vehicules",
    }.get(kind, kind or "elements")


# Dossier de sauvegarde DÉDIÉ par type (créé à la demande) — comme le storyboard
# enregistre dans <data_root>/Storyboard/. Évite d'atterrir dans la racine du projet.
_KIND_FOLDER = {
    "casting":     "Casting",
    "decors":      "Décors",
    "accessories": "Accessoires",
    "hmc":         "HMC",
    "vehicles":    "Véhicules",
}


def saves_dir(kind: str) -> str:
    """Dossier d'enregistrement/ouverture par défaut pour ce type, sous le projet
    courant (<data_root>/<Type>/). Créé s'il n'existe pas."""
    from core.context import get_data_root
    d = os.path.join(get_data_root(), _KIND_FOLDER.get(kind, "Éléments"))
    os.makedirs(d, exist_ok=True)
    return d


def export_items(path: str, kind: str, items: list) -> str:
    """Écrit la liste d'éléments (déjà filtrée projet) vers `path`.
    Les clés privées (préfixe `_`) sont retirées."""
    clean = [{k: v for k, v in (it or {}).items() if not k.startswith("_")}
             for it in (items or [])]
    payload = {
        "pandora_kind": kind,
        "saved_at": datetime.now().isoformat(timespec="seconds"),
        "count": len(clean),
        "items": clean,
    }
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    return path


def read_items(path: str, kind: str = "") -> list:
    """Lit un fichier PANDORA d'éléments et renvoie la liste d'items.
    Lève ValueError si le fichier est invalide ou d'un type incompatible."""
    if not path or not os.path.isfile(path):
        raise ValueError("Fichier introuvable.")
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, dict) or "items" not in data:
        raise ValueError("Fichier PANDORA invalide.")
    file_kind = data.get("pandora_kind", "")
    if kind and file_kind and file_kind != kind:
        a = KIND_LABELS.get(file_kind, file_kind)
        b = KIND_LABELS.get(kind, kind)
        raise ValueError(f"Ce fichier contient des « {a} », pas des « {b} ».")
    items = data.get("items", [])
    return items if isinstance(items, list) else []


def import_items(path, kind, list_fn, save_fn, delete_fn, *, replace=True) -> int:
    """Charge les éléments d'un fichier dans le projet courant.

    replace=True (défaut) : remplace les éléments du projet courant (supprime
    d'abord ceux listés par list_fn — déjà filtrés projet). delete_fn ne touche
    que l'index, jamais les fichiers image.

    Chaque item reçoit un nouvel id (attribué par save_fn) pour éviter toute
    collision ; project_id est réattribué au projet courant par save_fn.
    Retourne le nombre d'éléments chargés.
    """
    items = read_items(path, kind)
    if replace:
        for it in list(list_fn() or []):
            iid = (it or {}).get("id")
            if iid:
                delete_fn(iid)
    n = 0
    for it in items:
        it = dict(it or {})
        it.pop("id", None)          # nouvel id attribué par save_fn
        it.pop("project_id", None)  # rattaché au projet courant par save_fn
        save_fn(it)
        n += 1
    return n
