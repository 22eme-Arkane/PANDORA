"""core/spend.py — journal des DÉPENSES du projet, opération par opération.

Demande Matthieu 2026-07-31 : « savoir combien nous a coûté chaque opération »,
avec un total. PANDORA appelle des moteurs facturés à l'acte — vidéo Seedance,
images Nano Banana / Seedream, IA de texte — et rien ne gardait la trace de ce
que chaque clic a coûté. L'historique existant (`core/history`) est GLOBAL,
plafonné à cinquante entrées, et ne porte aucun montant : il ne pouvait pas
répondre à la question.

Le journal vit DANS le projet (`.cache/spend.json` via `core.project_layout`) :
le coût d'un film appartient au film, pas au poste de travail.

⚠ Les montants sont des ESTIMATIONS, et l'interface doit le dire. PANDORA
connaît la grille tarifaire annoncée par les fournisseurs, pas votre facture :
un essai refusé par un filtre de contenu, une remise, un changement de tarif ou
un distributeur alternatif peuvent écarter le total du relevé réel. C'est un
ordre de grandeur pour piloter un budget, pas une comptabilité.
"""

from __future__ import annotations

import json
import os
import time
import uuid

#: Familles d'opérations — sert au regroupement dans la fenêtre.
KIND_VIDEO = "video"
KIND_IMAGE = "image"
KIND_TEXT  = "texte"
KIND_AUDIO = "audio"
KIND_OTHER = "autre"

_FILE = "spend.json"
#: Plafond large : un long-métrage cumule des milliers d'opérations, et c'est
#: précisément l'historique complet qui est demandé. On borne quand même pour
#: qu'un fichier corrompu ou un emballement ne rende pas la fenêtre inutilisable.
_MAX = 20000


def _path() -> str:
    from core import project_layout as _pl
    return _pl.file(_FILE)


def load() -> list:
    """Toutes les dépenses du projet, la plus RÉCENTE en premier."""
    try:
        with open(_path(), encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, list) else []
    except Exception:
        return []


def record(kind: str, engine: str, label: str, cost_usd: float = 0.0,
           detail: str = "", estimated: bool = True) -> dict:
    """Note une opération facturée. Ne lève JAMAIS : une écriture de journal
    ratée ne doit pas faire échouer une génération que l'utilisateur a déjà
    payée."""
    entry = {
        "id":        uuid.uuid4().hex[:12],
        "ts":        time.time(),
        "kind":      (kind or KIND_OTHER),
        "engine":    (engine or "").strip(),
        "label":     (label or "").strip(),
        "detail":    (detail or "").strip(),
        "cost_usd":  round(float(cost_usd or 0.0), 4),
        "estimated": bool(estimated),
    }
    try:
        from core import project_layout as _pl
        items = load()
        items.insert(0, entry)
        if len(items) > _MAX:
            items = items[:_MAX]
        _p = _path()
        _pl.ensure_parent(_p)
        _tmp = _p + ".tmp"
        with open(_tmp, "w", encoding="utf-8") as f:
            json.dump(items, f, ensure_ascii=False, indent=1)
        os.replace(_tmp, _p)          # écriture atomique, comme la config
    except Exception:
        pass
    return entry


def total_usd(items: list | None = None) -> float:
    return round(sum(float(e.get("cost_usd") or 0.0)
                     for e in (items if items is not None else load())), 4)


def totals_by_kind(items: list | None = None) -> dict:
    """{famille: (nombre, montant)} — pour le pied de la fenêtre."""
    out: dict = {}
    for e in (items if items is not None else load()):
        _k = e.get("kind") or KIND_OTHER
        _n, _c = out.get(_k, (0, 0.0))
        out[_k] = (_n + 1, _c + float(e.get("cost_usd") or 0.0))
    return {k: (n, round(c, 4)) for k, (n, c) in out.items()}
