"""Identité visuelle canonique des entités PANDORA.

L'image active est la source de vérité. La description canonique est liée à son
empreinte ; elle devient automatiquement périmée lorsque l'utilisateur choisit une
autre image. Le module est pur et ne lance aucun appel réseau.
"""

from __future__ import annotations

import hashlib
import os
from datetime import datetime, timezone


VISUAL_IDENTITY_VERSION = 1


def image_fingerprint(path: str) -> str:
    if not path or not os.path.isfile(path):
        return ""
    digest = hashlib.sha256()
    try:
        with open(path, "rb") as fh:
            for chunk in iter(lambda: fh.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()
    except OSError:
        return ""


def identity_matches_image(identity: dict | None, image_path: str) -> bool:
    identity = identity or {}
    expected = str(identity.get("image_hash") or "")
    return bool(expected and expected == image_fingerprint(image_path)
                and identity.get("status") == "ready"
                and str(identity.get("canonical_description") or "").strip())


def pending_identity(image_path: str, source: str = "selected",
                     previous: dict | None = None) -> dict:
    """Invalide une ancienne analyse dès que l'image active change."""
    current_hash = image_fingerprint(image_path)
    previous = dict(previous or {})
    if identity_matches_image(previous, image_path):
        return previous
    return {
        "version": VISUAL_IDENTITY_VERSION,
        "status": "pending" if current_hash else "missing",
        "source": source,
        "image_path": image_path or "",
        "image_hash": current_hash,
        "canonical_description": "",
        "invariants": {},
        "variable_appearance": {},
        "excluded_observations": [],
        "analyzed_at": "",
        "analysis_model": "",
    }


def ready_identity(image_path: str, source: str, analysis: dict,
                   analysis_model: str = "") -> dict:
    return {
        "version": VISUAL_IDENTITY_VERSION,
        "status": "ready",
        "source": source or "selected",
        "image_path": image_path or "",
        "image_hash": image_fingerprint(image_path),
        "canonical_description": str(analysis.get("canonical_description") or "").strip(),
        "invariants": analysis.get("invariants") if isinstance(analysis.get("invariants"), dict) else {},
        "variable_appearance": (
            analysis.get("variable_appearance")
            if isinstance(analysis.get("variable_appearance"), dict) else {}
        ),
        "excluded_observations": (
            analysis.get("excluded_observations")
            if isinstance(analysis.get("excluded_observations"), list) else []
        ),
        "analyzed_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "analysis_model": analysis_model or "",
    }


def canonical_description(item: dict | None) -> str:
    """Description exacte de l'image active, ou repli legacy avant toute analyse.

    Dès qu'une identité est suivie, un état périmé/en attente ne doit surtout pas
    réinjecter la description d'une ancienne image dans les prompts.
    """
    item = item or {}
    identity = item.get("visual_identity") or {}
    image_path = str(item.get("image_path") or "")
    if identity_matches_image(identity, image_path):
        return str(identity.get("canonical_description") or "").strip()
    if identity:
        return ""
    return " ".join(str(item.get(k) or "").strip() for k in (
        "physical_description", "description", "prompt", "appearance"
    ) if str(item.get(k) or "").strip())


def prepare_identity_for_save(identity: dict | None, image_path: str,
                              source: str = "selected") -> dict:
    """Empêche qu'une description d'une ancienne image soit persistée comme active."""
    if identity_matches_image(identity, image_path):
        return dict(identity or {})
    return pending_identity(image_path, source, identity)
