"""core/dialogue.py — extraction du dialogue parlé d'un plan storyboard.

Le dialogue d'un plan est le texte entre guillemets de son prompt (la même
convention que le lipsync natif Seedance et la protection de traduction de
core/lang.py). Utilisé par la synchronisation labiale (api/shot_lipsync) pour
produire la voix cible quand aucun audio manuel n'est fourni.

Pur (aucune dépendance UI / réseau) → testable hors ligne.
"""

import re

# Paires de guillemets reconnues (français, anglais, simples typographiques).
_QUOTE_PAIRS = [
    ("«", "»"),
    ("“", "”"),
    ("\"", "\""),
    ("‘", "’"),
]


def extract_dialogue_lines(text: str) -> list[str]:
    """Renvoie la liste des répliques entre guillemets trouvées dans `text`,
    dans l'ordre, nettoyées (sans guillemets, espaces externes retirés)."""
    if not text:
        return []
    out: list[str] = []
    for op, cl in _QUOTE_PAIRS:
        if op == cl:  # guillemets droits "…" : appariement glouton non imbriqué
            pattern = re.escape(op) + r"([^" + re.escape(op) + r"]+)" + re.escape(cl)
        else:
            pattern = re.escape(op) + r"(.+?)" + re.escape(cl)
        for m in re.findall(pattern, text):
            line = m.strip()
            if line and line not in out:
                out.append(line)
    return out


def extract_shot_dialogue(shot: dict) -> str:
    """Dialogue parlé d'un plan, prêt pour la synthèse vocale (TTS).

    Cherche, dans l'ordre : un champ `dialogue` explicite, sinon les répliques
    entre guillemets du `seedance_prompt`, sinon des `comments`. Plusieurs
    répliques sont jointes par un espace. Renvoie "" si aucun dialogue."""
    if not isinstance(shot, dict):
        return ""
    explicit = (shot.get("dialogue") or "").strip()
    if explicit:
        return explicit
    for field in ("seedance_prompt", "comments", "scene_title"):
        lines = extract_dialogue_lines(shot.get(field) or "")
        if lines:
            return " ".join(lines)
    return ""
