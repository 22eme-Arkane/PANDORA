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


def build_six_view_prompts(base_prompt: str) -> list[tuple]:
    """À partir de la description du décor, renvoie [(label, code, prompt), …]
    pour les 6 faces. base_prompt peut être en français ou en anglais —
    la traduction en anglais est faite par le worker avant l'appel image."""
    base = (base_prompt or "").strip().rstrip(".")
    out = []
    for label, code, direction in SIX_FACES:
        prompt = (
            f"{base}. Interior view from the EXACT CENTER of the room, as if a "
            f"person standing in the middle turns to face one side: camera placed "
            f"at the center of the room, {direction}, straight-on framing, wide "
            f"angle covering the whole {label.lower()} face of the room. "
            f"SAME room as the other views — identical architecture, materials, "
            f"colors, lighting and furniture style, strict spatial consistency. "
            f"Empty location, no people, no characters."
        )
        out.append((label, code, prompt))
    return out
