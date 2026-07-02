"""
core/room_views.py — Les 6 vues d'une pièce (décor).

Idée : un personnage debout au CENTRE de la pièce qui pivote pour regarder
successivement les 6 faces du cube qui l'entoure — avant, arrière, gauche,
droite, sol, plafond. On génère une image par face, avec des prompts construits
automatiquement à partir de la description du décor, en imposant une cohérence
spatiale stricte (mêmes matières, couleurs, lumière, mobilier d'une vue à
l'autre). Objectif : maîtriser totalement la construction du lieu pour les
champs / contrechamps et les mouvements de caméra.
"""

# (libellé FR, code, direction de regard en anglais pour le prompt image)
SIX_FACES = [
    ("Avant",   "avant",   "looking straight AHEAD at the FRONT wall, eye level"),
    ("Arrière", "arriere", "turned 180 degrees, looking at the BACK wall, eye level"),
    ("Gauche",  "gauche",  "looking to the LEFT, at the LEFT wall, eye level"),
    ("Droite",  "droite",  "looking to the RIGHT, at the RIGHT wall, eye level"),
    ("Sol",     "sol",     "looking straight DOWN at the FLOOR"),
    ("Plafond", "plafond", "looking straight UP at the CEILING"),
]


# 7e vue — un plan d'ensemble qui regroupe les six faces (vue maîtresse).
OVERVIEW = ("Plan d'ensemble", "ensemble",
            "wide establishing 3/4 high-angle master view of the whole room")


# Nom ANGLAIS de chaque face pour le prompt image — les libellés français
# (« avant », « plafond »…) injectés tels quels dans un gabarit anglais
# dépendaient du traducteur aval pour être rattrapés (fragile).
_FACE_EN = {
    "avant":   "front wall",
    "arriere": "back wall",
    "gauche":  "left wall",
    "droite":  "right wall",
    "sol":     "floor",
    "plafond": "ceiling",
}


def build_six_view_prompts(base_prompt: str) -> list[tuple]:
    """À partir de la description du décor, renvoie [(label, code, prompt), …]
    pour les 6 faces. base_prompt peut être en français ou en anglais —
    la traduction en anglais est faite par le worker avant l'appel image."""
    base = (base_prompt or "").strip().rstrip(".")
    out = []
    for label, code, direction in SIX_FACES:
        face_en = _FACE_EN.get(code, "wall")
        if code in ("sol", "plafond"):
            # Sol / plafond : pas de « mur parallèle » — visée strictement verticale.
            vertical = "top-down" if code == "sol" else "bottom-up"
            prompt = (
                f"{base}. Interior view from the EXACT CENTER of the room: camera "
                f"placed at the dead center of the room, {direction}. "
                f"The {face_en} plane fills the frame completely, camera axis "
                f"perpendicular to the {face_en} — a strictly vertical {vertical} "
                f"shot, NOT an angled or oblique view. "
                f"Wide angle covering the whole {face_en} of the room. "
                f"SAME room as the other views — identical architecture, materials, "
                f"colors, lighting and furniture style, strict spatial consistency. "
                f"Empty location, no people, no characters."
            )
        else:
            prompt = (
                f"{base}. Interior view from the EXACT CENTER of the room, as if a "
                f"person standing in the middle turns to face one side: camera placed "
                f"at the dead center of the room, {direction}. "
                f"STRICTLY FRONTAL, straight-on, perpendicular ONE-POINT-PERSPECTIVE "
                f"shot facing the {face_en} flat-on — NOT a 3/4 view, NOT an "
                f"angled or oblique view, the wall is parallel to the camera and fills "
                f"the frame symmetrically. Wide angle covering the whole {face_en} "
                f"of the room. "
                f"SAME room as the other views — identical architecture, materials, "
                f"colors, lighting and furniture style, strict spatial consistency. "
                f"Empty location, no people, no characters."
            )
        out.append((label, code, prompt))
    return out


def build_overview_prompt(base_prompt: str) -> tuple:
    """7e vue : un plan d'ensemble qui regroupe les six faces — une vue maîtresse
    de toute la pièce en une seule image. Renvoie (label, code, prompt)."""
    base = (base_prompt or "").strip().rstrip(".")
    prompt = (
        f"{base}. Wide establishing shot of the ENTIRE room seen at once: "
        f"3/4 high-angle perspective showing the floor, the ceiling and all the "
        f"surrounding walls together in a single coherent view — a master plan "
        f"that ties together the six individual faces. SAME room as the other "
        f"views — identical architecture, materials, colors, lighting and "
        f"furniture style, strict spatial consistency. Empty location, no people."
    )
    return (OVERVIEW[0], OVERVIEW[1], prompt)


def build_seven_view_prompts(base_prompt: str) -> list[tuple]:
    """Les 7 vues : les 6 faces PUIS le plan d'ensemble (généré en dernier)."""
    return build_six_view_prompts(base_prompt) + [build_overview_prompt(base_prompt)]
