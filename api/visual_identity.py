"""Analyse Vision de l'image active d'un personnage, décor ou élément."""

from __future__ import annotations

import base64
import json
import os
from pathlib import Path

from PyQt6.QtCore import QThread, pyqtSignal

from core.visual_identity import ready_identity


_TYPE_RULES = {
    "character": (
        "Décris l'identité permanente : visage, âge apparent, carnation, morphologie, "
        "cheveux et signes distinctifs. Sépare costume/coiffure/maquillage variables. "
        "N'intègre jamais pose, expression momentanée, fond ou lumière photographique."
    ),
    "decor": (
        "Décris la géographie stable, l'architecture, les matières, la palette et les "
        "repères spatiaux. Sépare météo, heure et éclairage momentanés."
    ),
    "accessory": (
        "Décris forme, proportions, matières, couleurs, usure et marques distinctives. "
        "Ignore le fond, la main qui le tient et la lumière photographique."
    ),
    "vehicle": (
        "Décris silhouette, type, proportions, matières, couleurs, état et marques "
        "distinctives. Ignore route, conducteur, fond et lumière photographique."
    ),
    "hmc": (
        "Décris précisément le costume, maquillage ou la coiffure : coupe, construction, "
        "matières, couleurs, usure et détails distinctifs. Ignore la pose et le fond."
    ),
}

_SYSTEM = """Tu es le superviseur de continuité visuelle de PANDORA.
Analyse uniquement ce qui est réellement visible dans l'image active. N'invente ni
marque, ni origine, ni biographie. La description servira de verrou d'identité dans
des prompts vidéo : elle doit être précise, stable, factuelle et réutilisable sous
d'autres angles.

Retourne uniquement un objet JSON valide :
{
  "canonical_description": "description compacte en français, 80 à 180 mots",
  "invariants": {"cle": "valeur factuelle"},
  "variable_appearance": {"cle": "valeur visible mais modifiable entre les plans"},
  "excluded_observations": ["pose, fond ou lumière à ne pas figer"]
}
"""


def _image_content(path: str) -> dict:
    # Redimensionnée + réencodée JPEG avant envoi : l'API vision refuse les images
    # trop lourdes (~5 Mo) — un portrait Nano Banana PNG brut dépassait la limite
    # → erreur 400 invalid_request_error (vécu 2026-07-23).
    try:
        from api.element_chat import image_block
        return image_block(path, max_px=1024)
    except Exception:
        mime = {
            ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png",
            ".webp": "image/webp", ".bmp": "image/bmp",
        }.get(Path(path).suffix.lower(), "image/jpeg")
        with open(path, "rb") as fh:
            data = base64.standard_b64encode(fh.read()).decode("ascii")
        return {"type": "image", "source": {"type": "base64", "media_type": mime, "data": data}}


def _parse_json(raw: str) -> dict:
    text = (raw or "").strip()
    if "```" in text:
        for part in text.split("```"):
            candidate = part.lstrip("json").strip()
            if candidate.startswith("{"):
                text = candidate
                break
    obj = json.loads(text)
    if not isinstance(obj, dict) or not str(obj.get("canonical_description") or "").strip():
        raise ValueError("L'analyse visuelle n'a pas produit de description canonique.")
    return obj


class VisualIdentityWorker(QThread):
    done = pyqtSignal(dict)
    failed = pyqtSignal(str)

    def __init__(self, entity_type: str, image_path: str, source: str = "selected",
                 current_description: str = ""):
        super().__init__()
        self._entity_type = entity_type if entity_type in _TYPE_RULES else "accessory"
        self._image_path = image_path
        self._source = source
        self._current_description = current_description

    def run(self):
        if not self._image_path or not os.path.isfile(self._image_path):
            self.failed.emit("Image active introuvable.")
            return
        try:
            from core.ai_provider import ai_name_for_task, chat, humanize_ai_error, key_error
            err = key_error("vision")
            if err:
                self.failed.emit(err)
                return
            rule = _TYPE_RULES[self._entity_type]
            existing = self._current_description.strip()
            user_text = (
                f"TYPE D'ENTITÉ : {self._entity_type}\n"
                f"RÈGLE SPÉCIFIQUE : {rule}\n"
                "L'image jointe est la source de vérité."
            )
            if existing:
                user_text += ("\nDESCRIPTION EXISTANTE (simple contexte, à corriger si elle "
                              f"contredit l'image) :\n{existing}")
            content = [_image_content(self._image_path), {"type": "text", "text": user_text}]
            raw = chat(_SYSTEM, [{"role": "user", "content": content}],
                       tier="utility", max_tokens=1000, task="vision")
            analysis = _parse_json(raw)
            self.done.emit(ready_identity(
                self._image_path, self._source, analysis, ai_name_for_task("vision")
            ))
        except Exception as exc:
            try:
                from core.ai_provider import humanize_ai_error
                message = humanize_ai_error(str(exc))
            except Exception:
                message = str(exc)
            self.failed.emit(message)
