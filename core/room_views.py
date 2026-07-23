"""Construction des prompts des sept vues cohérentes d'un décor.

Un décor intérieur est décrit comme une pièce et ses quatre murs. Un décor
extérieur est décrit comme un site observé depuis un point fixe : avant,
arrière, gauche, droite, sol et ciel. Les deux cas ne doivent jamais partager
les mots ``room``, ``wall`` ou ``ceiling`` car les générateurs d'images les
interprètent littéralement.
"""

from __future__ import annotations

import unicodedata


SIX_FACES = [
    ("Avant", "avant", "looking straight AHEAD at the FRONT wall, eye level"),
    ("Arrière", "arriere", "turned 180 degrees, looking at the BACK wall, eye level"),
    ("Gauche", "gauche", "looking to the LEFT, at the LEFT wall, eye level"),
    ("Droite", "droite", "looking to the RIGHT, at the RIGHT wall, eye level"),
    ("Sol", "sol", "looking straight DOWN at the FLOOR"),
    ("Plafond", "plafond", "looking straight UP at the CEILING"),
]

OVERVIEW = ("Plan d'ensemble", "ensemble")

_INTERIOR_DIRECTIONS = {
    "avant": "looking straight AHEAD at the FRONT wall, eye level",
    "arriere": "turned 180 degrees, looking at the BACK wall, eye level",
    "gauche": "looking to the LEFT, at the LEFT wall, eye level",
    "droite": "looking to the RIGHT, at the RIGHT wall, eye level",
    "sol": "looking straight DOWN at the FLOOR",
    "plafond": "looking straight UP at the CEILING",
}

_FACE_EN = {
    "avant": "front wall",
    "arriere": "back wall",
    "gauche": "left wall",
    "droite": "right wall",
    "sol": "floor",
    "plafond": "ceiling",
}

_EXTERIOR_DIRECTIONS = {
    "avant": "looking FORWARD at eye level (0 degrees, the primary direction)",
    "arriere": "rotated exactly 180 degrees and looking BACKWARD at eye level",
    "gauche": "rotated exactly 90 degrees counter-clockwise and looking LEFT at eye level",
    "droite": "rotated exactly 90 degrees clockwise and looking RIGHT at eye level",
    "sol": "looking vertically DOWN at the natural ground directly below the observation point",
    "plafond": "looking vertically UP at the OPEN SKY directly above the observation point",
}


def _plain(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value or "")
    return "".join(c for c in normalized if not unicodedata.combining(c)).lower()


def is_exterior_category(category: str) -> bool:
    """True pour les libellés français/anglais désignant un extérieur."""
    value = _plain(category)
    return any(token in value for token in ("exterieur", "exterior", "outdoor"))


def extract_base_prompt(prompt: str) -> str:
    """Retire les anciennes consignes de vue déjà stockées dans les projets.

    Avant cette correction, la vue d'ensemble sauvegardait son prompt complet.
    Une variation pouvait donc réutiliser « ENTIRE room » comme description de
    base d'une vallée. On tronque uniquement aux marqueurs générés par PANDORA.
    """
    text = (prompt or "").strip()
    lowered = text.lower()
    markers = (
        "wide establishing shot of the entire room",
        "interior view from the exact center of the room",
        "wide high-angle establishing master view of the entire outdoor site",
        "outdoor natural location photographed from the same fixed central observation point",
    )
    positions = [lowered.find(marker) for marker in markers if lowered.find(marker) >= 0]
    if positions:
        text = text[:min(positions)].rstrip(" .,:;—-\n")
    return text


def _exterior_face_prompt(base: str, code: str) -> str:
    direction = _EXTERIOR_DIRECTIONS[code]
    vertical = code in ("sol", "plafond")
    subject = "natural terrain" if code == "sol" else "open sky"
    framing = (
        f"The {subject} fills the frame in a strictly vertical view, not an angled view."
        if vertical else
        "Use a genuinely new horizontal camera orientation; visible landmarks and "
        "their positions must change consistently with that rotation."
    )
    return (
        f"{base}. OUTDOOR natural location photographed from the SAME fixed central "
        f"observation point, {direction}. {framing} Preserve the exact same site, "
        f"terrain, geology, vegetation, weather, time of day, light direction and "
        f"spatial landmarks across all views. The reference master image defines "
        f"location identity and layout only, NOT camera composition: reconstruct the "
        f"requested orientation and DO NOT duplicate the master shot. No room, no "
        f"interior, no walls, no ceiling, no furniture, no invented building or "
        f"architecture unless a structure is explicitly present in the location "
        f"description. Empty location, no people, no characters."
    )


def _interior_face_prompt(base: str, code: str) -> str:
    direction = _INTERIOR_DIRECTIONS[code]
    face_en = _FACE_EN[code]
    if code in ("sol", "plafond"):
        vertical = "top-down" if code == "sol" else "bottom-up"
        return (
            f"{base}. Interior view from the EXACT CENTER of the room: camera placed "
            f"at the dead center of the room, {direction}. The {face_en} plane fills "
            f"the frame completely, camera axis perpendicular to the {face_en} — a "
            f"strictly vertical {vertical} shot, NOT an angled or oblique view. Wide "
            f"angle covering the whole {face_en} of the room. SAME room as the other "
            f"views — identical architecture, materials, colors, lighting and "
            f"furniture style, strict spatial consistency. Empty location, no people, "
            f"no characters."
        )
    return (
        f"{base}. Interior view from the EXACT CENTER of the room, as if a person "
        f"standing in the middle turns to face one side: camera placed at the dead "
        f"center of the room, {direction}. STRICTLY FRONTAL, straight-on, perpendicular "
        f"ONE-POINT-PERSPECTIVE shot facing the {face_en} flat-on — NOT a 3/4 view, "
        f"NOT an angled or oblique view. Wide angle covering the whole {face_en}. SAME "
        f"room as the other views — identical architecture, materials, colors, "
        f"lighting and furniture style, strict spatial consistency. The reference "
        f"master defines identity and layout only: do not duplicate its composition. "
        f"Empty location, no people, no characters."
    )


def build_six_view_prompts(base_prompt: str, category: str = "") -> list[tuple]:
    """Renvoie les six prompts, adaptés à un intérieur ou un extérieur."""
    base = (base_prompt or "").strip().rstrip(".")
    exterior = is_exterior_category(category)
    builder = _exterior_face_prompt if exterior else _interior_face_prompt
    return [(label, code, builder(base, code)) for label, code, _ in SIX_FACES]


def build_overview_prompt(base_prompt: str, category: str = "") -> tuple:
    """Renvoie la vue maîtresse sans imposer une architecture aux extérieurs."""
    base = (base_prompt or "").strip().rstrip(".")
    if is_exterior_category(category):
        prompt = (
            f"{base}. Wide high-angle establishing master view of the ENTIRE OUTDOOR "
            f"site, clearly showing the horizon, terrain relief, paths, geology, "
            f"vegetation and the relative positions of all natural landmarks in one "
            f"coherent image. This image is the spatial reference for later rotated "
            f"views. Outdoor natural location: no room, no interior, no walls, no "
            f"ceiling, no furniture, and no invented building or architecture unless "
            f"explicitly required by the description. Empty location, no people."
        )
    else:
        prompt = (
            f"{base}. Wide establishing shot of the ENTIRE room seen at once: 3/4 "
            f"high-angle perspective showing the floor, the ceiling and all the "
            f"surrounding walls together in a single coherent view — a master plan "
            f"that ties together the six individual faces. SAME room as the other "
            f"views — identical architecture, materials, colors, lighting and "
            f"furniture style, strict spatial consistency. Empty location, no people."
        )
    return (OVERVIEW[0], OVERVIEW[1], prompt)


def build_seven_view_prompts(base_prompt: str, category: str = "") -> list[tuple]:
    return build_six_view_prompts(base_prompt, category) + [
        build_overview_prompt(base_prompt, category)
    ]
