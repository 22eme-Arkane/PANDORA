"""
core/prompt_form.py — Forme d'écriture des prompts vidéo, réglable pour ESSAI.

POURQUOI
--------
PANDORA écrit le prompt de chaque plan sous une forme choisie par
`core/engine_grammar` : fiche technique étiquetée (`Camera:` / `Lighting:`)
pour Seedance, directive courte pour Kling, phrase continue pour Veo…

Le relevé documentaire du 2026-08-09 (voir `docs/grammaires_moteurs_video_*`)
affirme au contraire que presque tous ces moteurs attendent une **phrase
cinématographique continue** — Seedance et Kling compris. Mais sa confiance
était *moyenne* précisément sur ces deux-là, et la table actuelle a produit des
plans qui fonctionnent.

On ne tranche donc pas sur une lecture : **on essaie**. Ce module permet de
forcer la forme depuis le Storyboard, générer deux fois le même plan, et
comparer les rendus.

CE QUE ÇA CHANGE
----------------
UNIQUEMENT la forme du texte envoyé au moteur. Ni le contenu du plan, ni les
images de référence, ni les réglages caméra. Le même plan, dit autrement.

VALEURS
-------
· "auto"      → la table `engine_grammar` décide (comportement d'origine)
· "fields"    → fiche technique étiquetée
· "sentence"  → phrase cinématographique continue
· "directive" → directive d'action courte
· "dense"     → prose dense sans étiquettes

Le réglage vit DANS le projet (`<projet>/data/prompt_form.json`) : un essai sur
un film ne doit pas déteindre sur les autres. Hors projet, aucune écriture.
"""
from __future__ import annotations

import json
import os

_FILENAME = "prompt_form.json"
AUTO = "auto"

# Formes proposées à l'essai — libellé court, explication, exemple réel.
FORMS = [
    (AUTO, "Automatique (recommandé par le moteur)",
     "PANDORA choisit la forme d'après le moteur visé. C'est le comportement "
     "d'origine."),
    ("fields", "Fiche technique",
     "Une ligne par poste : Camera:, Subject:, Action:, Lighting:, Style:."),
    ("sentence", "Phrase de réalisateur",
     "Une phrase continue qui décrit le plan comme on le dirait à un chef "
     "opérateur, puis une phrase de détails."),
    ("directive", "Directive courte",
     "Ce qui bouge, où va la caméra. Rien d'autre."),
    ("dense", "Prose dense",
     "Un bloc serré, sans étiquettes et sans remplissage."),
]

_VALID = {k for k, _l, _d in FORMS}


def label_of(key: str) -> str:
    for k, lab, _d in FORMS:
        if k == key:
            return lab
    return FORMS[0][1]


def description_of(key: str) -> str:
    for k, _l, desc in FORMS:
        if k == key:
            return desc
    return FORMS[0][2]


def _path() -> str:
    """Chemin dans le projet courant, ou "" hors projet.

    ⚠ On teste `get_project_path()` et PAS `get_data_root()` : sans projet,
    ce dernier retombe sur le `data/` de l'application et le réglage fuirait
    hors de tout projet (même piège que core/target_engine).
    """
    try:
        from core.context import get_project_path, get_data_root
        if not get_project_path():
            return ""
        root = get_data_root()
    except Exception:
        return ""
    return os.path.join(root, _FILENAME) if root else ""


def get_form() -> str:
    """Forme forcée, ou "auto". Ne lève jamais."""
    p = _path()
    if not p or not os.path.isfile(p):
        return AUTO
    try:
        with open(p, "r", encoding="utf-8") as f:
            v = str((json.load(f) or {}).get("form") or "").strip()
        return v if v in _VALID else AUTO
    except (OSError, json.JSONDecodeError, ValueError):
        return AUTO


def set_form(form: str) -> str:
    """Enregistre la forme (écriture atomique). Retourne la valeur retenue."""
    v = (form or "").strip()
    if v not in _VALID:
        v = AUTO
    p = _path()
    if not p:
        return v
    try:
        os.makedirs(os.path.dirname(p), exist_ok=True)
        tmp = p + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump({"form": v}, f, ensure_ascii=False, indent=2)
        os.replace(tmp, p)
    except OSError:
        pass
    return v


def is_forced() -> bool:
    """True si l'utilisateur impose une forme (essai en cours)."""
    return get_form() != AUTO
