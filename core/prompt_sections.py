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
# La section STYLE VISUEL vient EN DERNIER : elle porte le style d'image du projet
# (mots-clés) + les spécifications de la note de réalisation, capturés à la création
# du storyboard. Elle est VISIBLE dans le prompt et lue par le Mood. Pour le moteur
# vidéo, elle est retirée AVANT la traduction (pour préserver les mots-clés anglais
# exacts) puis RÉ-APPLIQUÉE telle quelle EN FIN de prompt : Seedance suit mieux le
# style visuel placé en fin de prompt (demande Matthieu 2026-07-24). Aucun doublon :
# la ré-application remplace le get_video_suffix() séparé pour les plans de storyboard.
SECTIONS = [
    ("action",    "[🎬 ACTION]"),
    ("staging",   "[🎭 MISE EN SCÈNE]"),
    ("ambiance",  "[🌐 AMBIANCE]"),
    ("decor",     "[🏠 DÉCOR]"),
    ("lighting",  "[💡 PLAN DE FEU]"),
    ("technique", "[🖼️ TECHNIQUE]"),
    ("sound",     "[🎵 SOUND DESIGN]"),
    ("style",     "[🎨 STYLE VISUEL]"),
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
          lighting: str = "", technique: str = "", sound: str = "",
          style: str = "") -> str:
    """Assemble un prompt structuré (sections non vides uniquement).

    `style` (nouveau, 2026-07-24) = section [🎨 STYLE VISUEL] en tête. La plupart
    des appelants historiques ne le passent pas — préférez `rebuild()` pour ne
    jamais PERDRE une section lors d'une réécriture partielle."""
    vals = {"style": style, "action": action, "staging": staging, "ambiance": ambiance,
            "decor": decor, "lighting": lighting, "technique": technique, "sound": sound}
    parts = []
    for key, label in SECTIONS:
        v = (vals.get(key) or "").strip()
        if v:
            parts.append(f"{label}\n{v}")
    return "\n\n".join(parts)


def rebuild(prompt: str, **overrides) -> str:
    """Ré-assemble un prompt en NE remplaçant que les sections données, toutes les
    autres (y compris [🎨 STYLE VISUEL]) étant préservées à l'identique. À préférer
    à build() pour toute réécriture partielle : un appelant n'a plus à réénumérer
    chaque section (et donc ne peut plus en oublier une)."""
    sec = parse(prompt)
    for k, v in overrides.items():
        if k in sec:
            sec[k] = v
    return build(**sec)


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
        seg = prompt[start:end].strip()
        # FUSIONNER au lieu d'écraser : le texte AVANT la 1re étiquette (contexte
        # casting [COHÉRENCE VISUELLE], préfixes cadrage/mouvement/continuité) était
        # PERDU dès qu'une section [ACTION] existait — il reste désormais en tête.
        out[key] = f"{out[key]}\n{seg}".strip() if (out[key] and seg) else (out[key] or seg)
    return out


def strip_for_video(prompt: str) -> str:
    """Retire le bloc SOUND DESIGN (le son part au Sound Design, jamais au modèle
    vidéo). Le STYLE VISUEL, lui, est CONSERVÉ : il est souvent écrit en français
    (note de réalisation) et DOIT donc passer par la traduction et figurer dans le
    prompt final envoyé au moteur (demande Matthieu 2026-07-24). Le style n'est
    consommé séparément (get_video_suffix) que pour les prompts SANS section style.
    Prompt non structuré → renvoyé inchangé."""
    if not is_structured(prompt):
        return prompt
    s = parse(prompt)
    # sound NON transmis (défaut vide de build()) ; style CONSERVÉ.
    return build(action=s["action"], staging=s["staging"], ambiance=s["ambiance"],
                 decor=s["decor"], lighting=s["lighting"], technique=s["technique"],
                 style=s["style"])


def strip_for_composer(prompt: str) -> str:
    """Corps destiné au COMPOSEUR : retire SOUND **et** STYLE. Le composeur reçoit le
    style à part (bloc [STYLE VIDÉO]) pour le rendre en anglais EN FIN de prose ; le
    laisser aussi dans le corps le dupliquerait. Prompt non structuré → inchangé."""
    if not is_structured(prompt):
        return prompt
    s = parse(prompt)
    return build(action=s["action"], staging=s["staging"], ambiance=s["ambiance"],
                 decor=s["decor"], lighting=s["lighting"], technique=s["technique"])


def sound_of(prompt: str) -> str:
    """Texte de la section SOUND DESIGN (vide si absente)."""
    return parse(prompt).get("sound", "") if is_structured(prompt) else ""


def style_of(prompt: str) -> str:
    """Texte de la section STYLE VISUEL (vide si absente)."""
    return parse(prompt).get("style", "") if is_structured(prompt) else ""


def video_with_sound(video: str, sound: str) -> str:
    """Compose UN prompt Live unique : la VIDÉO (corps) suivie d'une section
    [🎵 SOUND DESIGN] si `sound` non vide. Sans son → renvoie la vidéo telle quelle.
    Le son reste extractible par sound_of() et retiré du prompt vidéo par video_of()
    (le moteur vidéo ne reçoit jamais le son : séparation image/son)."""
    video = (video or "").strip()
    sound = (sound or "").strip()
    if not sound:
        return video
    return f"{video}\n\n{_LABELS['sound']}\n{sound}"


def video_of(prompt: str) -> str:
    """Partie VIDÉO d'un prompt Live composé (le corps AVANT [🎵 SOUND DESIGN]).
    Prompt non structuré → renvoyé inchangé. Sert à n'envoyer QUE le visuel au
    moteur vidéo (le son part au Sound Design)."""
    if not is_structured(prompt):
        return prompt
    return parse(prompt).get("action", "").strip()


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
