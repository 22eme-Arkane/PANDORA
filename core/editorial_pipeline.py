"""Contrat du flux éditorial PANDORA.

Le pipeline est volontairement explicite :
Scénario -> Note de réalisation -> Découpage -> Storyboard.

Ce module ne touche jamais au disque. Il calcule les empreintes et la provenance
afin que les interfaces puissent signaler une étape devenue obsolète sans
réinterpréter silencieusement le travail de l'utilisateur.
"""

from __future__ import annotations

import hashlib
from datetime import datetime


SCHEMA_VERSION = 3


def _text(value) -> str:
    return str(value or "").replace("\r\n", "\n").replace("\r", "\n").strip()


def content_hash(value) -> str:
    return hashlib.sha256(_text(value).encode("utf-8")).hexdigest() if _text(value) else ""


def screenplay_text(data: dict) -> str:
    return _text(data.get("formatted_content") or data.get("raw_content"))


def ensure_metadata(data: dict | None) -> dict:
    """Retourne une copie avec métadonnées à jour, sans valider une étape."""
    out = dict(data or {})
    meta = dict(out.get("editorial_pipeline") or {})
    screenplay = screenplay_text(out)
    note = _text(out.get("direction_note"))
    decoupage = _text(out.get("decoupage_content") or out.get("layout_content"))

    meta.update({
        "schema": SCHEMA_VERSION,
        "screenplay_hash": content_hash(screenplay),
        "direction_note_hash": content_hash(note),
        "decoupage_hash": content_hash(decoupage),
    })

    # Migration douce : un ancien découpage existant est considéré valide par
    # rapport aux documents actuellement chargés. Les futures modifications
    # seront ensuite détectées par comparaison d'empreintes.
    if decoupage and not meta.get("decoupage_source_screenplay_hash"):
        meta["decoupage_source_screenplay_hash"] = meta["screenplay_hash"]
        meta["decoupage_source_note_hash"] = meta["direction_note_hash"]
        meta.setdefault("decoupage_built_at", out.get("updated_at", ""))

    out["editorial_pipeline"] = meta
    return out


def mark_decoupage_built(data: dict | None, decoupage: str | None = None) -> dict:
    out = ensure_metadata(data)
    if decoupage is not None:
        out["decoupage_content"] = _text(decoupage)
        out["layout_content"] = out["decoupage_content"]
        out = ensure_metadata(out)
    meta = dict(out["editorial_pipeline"])
    meta["decoupage_source_screenplay_hash"] = meta.get("screenplay_hash", "")
    meta["decoupage_source_note_hash"] = meta.get("direction_note_hash", "")
    meta["decoupage_built_at"] = datetime.now().isoformat(timespec="seconds")
    out["editorial_pipeline"] = meta
    return out


def mark_storyboard_built(data: dict | None) -> dict:
    out = ensure_metadata(data)
    meta = dict(out["editorial_pipeline"])
    meta["storyboard_source_decoupage_hash"] = meta.get("decoupage_hash", "")
    meta["storyboard_built_at"] = datetime.now().isoformat(timespec="seconds")
    out["editorial_pipeline"] = meta
    return out


def status(data: dict | None) -> str:
    out = ensure_metadata(data)
    meta = out["editorial_pipeline"]
    if not screenplay_text(out):
        return "screenplay_empty"
    if not meta.get("decoupage_hash"):
        return "decoupage_missing"
    if (meta.get("decoupage_source_screenplay_hash") != meta.get("screenplay_hash")
            or meta.get("decoupage_source_note_hash") != meta.get("direction_note_hash")):
        return "decoupage_stale"
    storyboard_source = meta.get("storyboard_source_decoupage_hash", "")
    if not storyboard_source:
        return "storyboard_missing"
    if storyboard_source != meta.get("decoupage_hash"):
        return "storyboard_stale"
    return "current"

