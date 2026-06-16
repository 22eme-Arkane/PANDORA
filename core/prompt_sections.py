"""
core/prompt_sections.py — Prompts storyboard structurés en SECTIONS.

Un prompt peut être découpé en blocs étiquetés, plus clairs à éditer et mieux
suivis par Seedance :

    [ACTION]
    ce qui se passe dans le plan
    [MISE EN SCÈNE]
    placement des personnages (in/off, assis/debout…) et de la caméra
    [PLAN DE FEU]
    description de la lumière et de l'ambiance
    [SOUND DESIGN]
    ambiance sonore / SFX

⚠ Le bloc SOUND DESIGN sert à la clarté et alimente l'onglet Sound Design, mais
n'est PAS envoyé au modèle vidéo (séparation image/son) : `strip_for_video()`.
"""

import re

# (clé, étiquette affichée)
SECTIONS = [
    ("action",   "ACTION"),
    ("staging",  "MISE EN SCÈNE"),
    ("lighting", "PLAN DE FEU"),
    ("sound",    "SOUND DESIGN"),
]
_LABELS = {k: lbl for k, lbl in SECTIONS}
_ALL_LABELS = [lbl for _, lbl in SECTIONS]
_TAG_RE = re.compile(r"^\s*\[(" + "|".join(re.escape(l) for l in _ALL_LABELS) + r")\]\s*$",
                     re.MULTILINE)


def build(action: str = "", staging: str = "", lighting: str = "", sound: str = "") -> str:
    """Assemble un prompt structuré (sections non vides uniquement)."""
    vals = {"action": action, "staging": staging, "lighting": lighting, "sound": sound}
    parts = []
    for key, label in SECTIONS:
        v = (vals.get(key) or "").strip()
        if v:
            parts.append(f"[{label}]\n{v}")
    return "\n\n".join(parts)


def is_structured(prompt: str) -> bool:
    return bool(prompt and _TAG_RE.search(prompt))


def parse(prompt: str) -> dict:
    """Découpe un prompt structuré en {action, staging, lighting, sound}.
    Si aucune étiquette : tout le texte est considéré comme « action »."""
    out = {k: "" for k, _ in SECTIONS}
    if not prompt:
        return out
    if not is_structured(prompt):
        out["action"] = prompt.strip()
        return out
    label_to_key = {lbl: k for k, lbl in SECTIONS}
    pos, cur = [], None
    matches = list(_TAG_RE.finditer(prompt))
    # texte avant la 1re étiquette → action
    if matches and matches[0].start() > 0:
        head = prompt[:matches[0].start()].strip()
        if head:
            out["action"] = head
    for i, m in enumerate(matches):
        key = label_to_key[m.group(1)]
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(prompt)
        out[key] = prompt[start:end].strip()
    return out


def strip_for_video(prompt: str) -> str:
    """Retire le bloc SOUND DESIGN (non envoyé au modèle vidéo). Conserve les
    autres sections telles quelles. Prompt non structuré → renvoyé inchangé."""
    if not is_structured(prompt):
        return prompt
    sec = parse(prompt)
    return build(sec["action"], sec["staging"], sec["lighting"], "")


def sound_of(prompt: str) -> str:
    """Texte de la section SOUND DESIGN (vide si absente)."""
    return parse(prompt).get("sound", "") if is_structured(prompt) else ""
