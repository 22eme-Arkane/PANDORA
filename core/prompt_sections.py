"""
core/prompt_sections.py — Prompts storyboard structurés en SECTIONS.

Un prompt est découpé en blocs étiquetés, plus clairs à éditer et mieux suivis
par Seedance. Format des étiquettes : crochets + emoji + titre en MAJUSCULES.

    [🎬 ACTION]
    ce qui se passe dans le plan
    [🎭 MISE EN SCÈNE]
    personnages PRÉSENTS (jamais les hors-champ) + placement + qui fait face à qui
    [🌐 AMBIANCE]
    atmosphère / mood / repères de qualité
    [🏠 DÉCOR]
    description du lieu / environnement
    [💡 PLAN DE FEU]
    intention de lumière (les sources ne sont PAS visibles à l'image)
    [🖼️ TECHNIQUE]
    valeur de plan, mouvement, objectif/optique, vitesse (depuis les champs caméra)
    [🎵 SOUND DESIGN]
    ambiance sonore / SFX

⚠ Le bloc SOUND DESIGN sert à la clarté et alimente l'onglet Sound Design, mais
n'est PAS envoyé au modèle vidéo (séparation image/son) : `strip_for_video()`.

Le parsing est tolérant : il reconnaît les anciennes étiquettes sans emoji
(`[ACTION]`, `[MISE EN SCÈNE]`, `[PLAN DE FEU]`, `[SOUND DESIGN]`) comme les
nouvelles, en normalisant (emojis et accents retirés). Rétro-compatible.
"""

import re
import unicodedata

# (clé, étiquette affichée — crochets + emoji + titre MAJUSCULE)
SECTIONS = [
    ("action",    "[🎬 ACTION]"),
    ("staging",   "[🎭 MISE EN SCÈNE]"),
    ("ambiance",  "[🌐 AMBIANCE]"),
    ("decor",     "[🏠 DÉCOR]"),
    ("lighting",  "[💡 PLAN DE FEU]"),
    ("technique", "[🖼️ TECHNIQUE]"),
    ("sound",     "[🎵 SOUND DESIGN]"),
]
_LABELS = {k: lbl for k, lbl in SECTIONS}

# Note standard rappelant que les sources d'éclairage ne sont pas dans le cadre.
LIGHTING_NOTE = ("Les sources d'éclairage ne sont PAS visibles à l'image — "
                 "il s'agit uniquement d'une intention de lumière et d'ambiance.")

# N'importe quelle ligne « [ ... ] » seule est une étiquette candidate.
_TAG_RE = re.compile(r"^[ \t]*\[[ \t]*(.+?)[ \t]*\][ \t]*$", re.MULTILINE)


def _norm_label(s: str) -> str:
    """Normalise une étiquette : retire emojis/symboles et accents, MAJUSCULES,
    espaces compactés. « 🎭 Mise en scène » et « MISE EN SCÈNE » → « MISE EN SCENE »."""
    s = unicodedata.normalize("NFD", s or "")
    s = "".join(c for c in s if not unicodedata.combining(c))      # retire accents
    s = "".join(c if (c.isalpha() or c.isspace()) else " " for c in s)  # retire emojis/ponctuation
    return " ".join(s.upper().split())


# Titre normalisé → clé de section (couvre anciens ET nouveaux libellés).
_NORM_TO_KEY = {_norm_label(lbl): key for key, lbl in SECTIONS}


def build(action: str = "", staging: str = "", ambiance: str = "", decor: str = "",
          lighting: str = "", technique: str = "", sound: str = "") -> str:
    """Assemble un prompt structuré (sections non vides uniquement)."""
    vals = {"action": action, "staging": staging, "ambiance": ambiance,
            "decor": decor, "lighting": lighting, "technique": technique, "sound": sound}
    parts = []
    for key, label in SECTIONS:
        v = (vals.get(key) or "").strip()
        if v:
            parts.append(f"{label}\n{v}")
    return "\n\n".join(parts)


def _recognized_tags(prompt: str) -> list:
    """[(match, key), …] des étiquettes reconnues dans l'ordre d'apparition."""
    out = []
    for m in _TAG_RE.finditer(prompt or ""):
        key = _NORM_TO_KEY.get(_norm_label(m.group(1)))
        if key:
            out.append((m, key))
    return out


def is_structured(prompt: str) -> bool:
    return bool(_recognized_tags(prompt))


def parse(prompt: str) -> dict:
    """Découpe un prompt structuré en dict {action, staging, ambiance, decor,
    lighting, technique, sound}. Si aucune étiquette reconnue : tout le texte est
    considéré comme « action »."""
    out = {k: "" for k, _ in SECTIONS}
    if not prompt:
        return out
    tags = _recognized_tags(prompt)
    if not tags:
        out["action"] = prompt.strip()
        return out
    # texte avant la 1re étiquette → action
    if tags[0][0].start() > 0:
        head = prompt[:tags[0][0].start()].strip()
        if head:
            out["action"] = head
    for i, (m, key) in enumerate(tags):
        start = m.end()
        end = tags[i + 1][0].start() if i + 1 < len(tags) else len(prompt)
        out[key] = prompt[start:end].strip()
    return out


def strip_for_video(prompt: str) -> str:
    """Retire le bloc SOUND DESIGN (non envoyé au modèle vidéo). Conserve les
    autres sections telles quelles. Prompt non structuré → renvoyé inchangé."""
    if not is_structured(prompt):
        return prompt
    s = parse(prompt)
    return build(action=s["action"], staging=s["staging"], ambiance=s["ambiance"],
                 decor=s["decor"], lighting=s["lighting"], technique=s["technique"],
                 sound="")


def sound_of(prompt: str) -> str:
    """Texte de la section SOUND DESIGN (vide si absente)."""
    return parse(prompt).get("sound", "") if is_structured(prompt) else ""


# ── Section TECHNIQUE déterministe (depuis les champs caméra d'un plan) ──────────

# Valeurs de plan (codes JSON) → libellés lisibles pour la section [🖼️ TECHNIQUE].
_SHOT_SIZE_FR = {
    "GP": "gros plan", "GM": "grand médium", "PM": "plan moyen", "PP": "plan poitrine",
    "PL": "plan large", "PE": "plan d'ensemble", "PTG": "plan très grand ensemble",
    "Insert": "insert",
}


def technique_line(shot: dict) -> str:
    """Texte de la section TECHNIQUE, construit depuis les champs caméra du plan
    (valeur de plan, mouvement, objectif/optique, vitesse). Déterministe — pas d'IA."""
    bits = []
    sz = (shot.get("shot_size") or "").strip()
    sz = _SHOT_SIZE_FR.get(sz, sz)
    if sz:
        bits.append(sz)
    mov = (shot.get("camera_movement") or "").strip()
    if mov:
        bits.append("caméra fixe" if mov.lower() == "fixe" else mov.lower())
    foc = (shot.get("focal") or "").strip()
    opt = (shot.get("optic") or "").strip().lower()
    lens = " ".join(x for x in [(f"objectif {foc}" if foc else ""), opt] if x).strip()
    if lens:
        bits.append(lens)
    spd = (shot.get("speed") or "").strip()
    if spd and spd.lower() != "normale":
        bits.append(spd.lower())
    line = ", ".join(bits)
    return (line[0].upper() + line[1:] + ".") if line else ""
