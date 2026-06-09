"""
api/live_screenplay.py — Génération du découpage Live/Mapping via Claude.

GenerateDecoupageWorker : transforme la trame du Conducteur en une liste de
segments, calibrée selon le mode :
  - "live"    → segments visuels d'une performance VJ (valeurs de plan, mouvement)
  - "mapping" → séquence CONTINUE sur une façade (caméra fixe, raccord, un seul plan long)

Sortie : list[dict] avec les clés action / shot_size / camera_movement / duration / prompt.
"""

import json
import re

from PyQt6.QtCore import QThread, pyqtSignal


_SYSTEM_LIVE = """\
Tu es un directeur artistique VJ. À partir de la trame fournie, produis le DÉCOUPAGE
d'une performance vidéo live (VJing) en une suite de plans/loops visuels.

Pour CHAQUE segment, donne :
- "action": description courte du visuel, en français (1 phrase).
- "shot_size": valeur de plan (ex: "Plan d'ensemble", "Plan large", "Plan moyen", "Gros plan", "Très gros plan") ou "".
- "camera_movement": mouvement (ex: "Fixe", "Panoramique", "Travelling", "Zoom avant", "Zoom arrière") ou "".
- "duration": durée en secondes (entier entre 4 et 15).
- "prompt": un prompt de génération en ANGLAIS pour un loop VJ (style "Seamless VJ loop, ...").

Réponds UNIQUEMENT avec un tableau JSON (aucun texte autour).
"""

_SYSTEM_MAPPING = """\
Tu es un concepteur de mapping vidéo (projection sur façade de bâtiment). À partir de
la trame fournie, produis le DÉCOUPAGE d'une séquence de mapping projetée sur une
façade VERROUILLÉE.

Contraintes IMPÉRATIVES :
- La caméra est TOTALEMENT FIXE (pas de mouvement, pas de zoom). camera_movement = "Fixe".
- La séquence est CONTINUE : chaque segment enchaîne le précédent comme un seul plan long.
- La géométrie de la façade reste identique ; seuls la lumière, les effets, les matières
  et le fond évoluent.

Pour CHAQUE segment, donne :
- "action": ce qui se passe sur la façade pendant ce segment, en français (1 phrase).
- "shot_size": "" (non pertinent en mapping).
- "camera_movement": "Fixe".
- "duration": durée en secondes (entier entre 4 et 15).
- "prompt": un prompt en ANGLAIS décrivant l'évolution sur la façade (sans mouvement de caméra).

Réponds UNIQUEMENT avec un tableau JSON (aucun texte autour).
"""


def _extract_json_array(text: str) -> list:
    """Extrait le premier tableau JSON d'un texte."""
    # Bloc ```json ... ``` éventuel
    m = re.search(r"```(?:json)?\s*(\[.*?\])\s*```", text, re.DOTALL)
    raw = m.group(1) if m else None
    if raw is None:
        start = text.find("[")
        end   = text.rfind("]")
        if start != -1 and end != -1 and end > start:
            raw = text[start:end + 1]
    if raw is None:
        return []
    try:
        data = json.loads(raw)
        return data if isinstance(data, list) else []
    except Exception:
        return []


def _normalize(seg: dict, mode: str) -> dict:
    try:
        dur = int(seg.get("duration", 5))
    except (TypeError, ValueError):
        dur = 5
    dur = max(4, min(15, dur))
    mv = seg.get("camera_movement", "") or ("Fixe" if mode == "mapping" else "")
    return {
        "action":          str(seg.get("action", "")).strip(),
        "shot_size":       "" if mode == "mapping" else str(seg.get("shot_size", "")).strip(),
        "camera_movement": "Fixe" if mode == "mapping" else str(mv).strip(),
        "duration":        dur,
        "prompt":          str(seg.get("prompt", "")).strip(),
        "image_path":      "",
    }


class GenerateDecoupageWorker(QThread):
    finished = pyqtSignal(list)   # list[dict] de segments
    failed   = pyqtSignal(str)

    def __init__(self, text: str, mode: str):
        super().__init__()
        self._text = text
        self._mode = mode if mode in ("live", "mapping") else "live"

    def run(self):
        text = (self._text or "").strip()
        if not text:
            self.failed.emit("La trame est vide — écrivez votre conducteur d'abord.")
            return
        try:
            from core.config import load_config
            key = load_config().get("anthropic_key", "").strip()
            if not key:
                self.failed.emit(
                    "Clé Anthropic (Claude) manquante — renseignez-la dans Paramètres "
                    "pour générer le découpage.")
                return
            import anthropic
            client = anthropic.Anthropic(api_key=key)
            system = _SYSTEM_MAPPING if self._mode == "mapping" else _SYSTEM_LIVE
            msg = client.messages.create(
                model="claude-sonnet-4-6",
                max_tokens=4000,
                system=system,
                messages=[{"role": "user", "content": text}],
            )
            out = "".join(
                block.text for block in msg.content if getattr(block, "type", "") == "text"
            )
            segments = [_normalize(s, self._mode) for s in _extract_json_array(out) if isinstance(s, dict)]
            if not segments:
                self.failed.emit("Découpage vide — réponse Claude non exploitable. Réessayez.")
                return
            self.finished.emit(segments)
        except Exception as e:
            from core.worker import humanize_api_error
            self.failed.emit(humanize_api_error(str(e)))
