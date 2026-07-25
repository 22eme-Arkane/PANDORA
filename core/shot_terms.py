"""
core/shot_terms.py — Vocabulaire ANGLAIS des champs techniques d'un plan.

Point unique de vérité pour convertir les champs du Storyboard (valeur de plan,
axe caméra, mouvement, focale, distance, hauteur, vitesse, heure) en descripteurs
anglais utilisables dans un prompt de génération.

Pourquoi ici : ces tables vivaient dans `api/apercu.py` (moods Flux) et n'étaient
donc PAS accessibles au prompt vidéo — résultat, seules la focale et le mouvement
étaient injectés, l'axe, la valeur de plan, la distance, la hauteur et la vitesse
se perdaient entre le Storyboard et le moteur (constat Matthieu 2026-07-25).
`api/apercu.py` réexporte ces tables pour ne pas dupliquer le vocabulaire.

Tout est déterministe : aucune IA, aucun appel réseau.
"""

from __future__ import annotations

import re


# Valeur de plan (codes du Storyboard) → cadrage anglais.
SHOT_SIZE_EN = {
    "GP":     "extreme close-up, face filling the entire frame",
    "GM":     "medium close-up, head and shoulders framing",
    "PM":     "medium shot, waist up",
    "PP":     "cowboy shot, mid-thigh up",
    "PL":     "wide shot, full body visible",
    "PE":     "establishing shot, wide environmental view",
    "PTG":    "extreme wide shot, tiny subjects in vast landscape",
    "Insert": "insert shot, isolated detail close-up",
}

# Axe caméra → angle anglais.
CAMERA_AXIS_EN = {
    "Face":            "straight-on frontal angle, symmetrical framing",
    "3/4":             "three-quarter angle, slight diagonal",
    "Latéral 90°":     "side profile, 90-degree lateral angle",
    "Dos":             "shot from behind the subject",
    "Plongée":         "high angle shot, camera looking down on subject",
    "Contre-plongée":  "low angle shot, camera looking up, dramatic upward perspective",
}

# Mouvement caméra → description anglaise du déplacement.
MOVEMENT_EN = {
    "Panoramique horizontal": "horizontal pan",
    "Panoramique vertical":   "vertical tilt",
    "Travelling avant":       "dolly push in, camera moves forward",
    "Travelling arrière":     "dolly pull out, camera moves backward",
    "Travelling latéral":     "lateral tracking shot",
    "Zoom avant":             "zoom in",
    "Zoom arrière":           "zoom out",
    "Steadicam":              "smooth steadicam glide",
    "Grue / Drone":           "crane or drone aerial move",
    "Caméra portée":          "handheld camera, organic movement",
    "Plongée":                "downward tilt from high position",
    "Contre-plongée":         "upward tilt from low position",
}

# « Fixe » mérite une formulation ferme : les moteurs dérivent volontiers en
# travelling si rien n'est dit.
STATIC_EN = ("locked-off static camera, fixed tripod shot, "
             "absolutely no camera movement, no pan, no tilt, no dolly, no zoom")

# Vitesse de défilement.
SPEED_EN = {
    "Ralenti":  "slow motion",
    "Accéléré": "fast motion, sped-up action",
}

# Heure du plan → intention d'éclairage (mots-clés anglais).
SHOT_TIME_EN = {
    "Jour":              "strict daylight, natural midday sun, bright neutral light, "
                         "no golden hour, no sunset",
    "Nuit":              "nighttime scene, dark environment, night lighting, "
                         "no daylight, moonlight or artificial light",
    "Lever du soleil":   "sunrise, warm golden morning light, sun just above the "
                         "horizon, soft pink-orange sky",
    "Coucher du soleil": "sunset, golden hour, warm amber-orange light, sun low on "
                         "the horizon",
}


def distance_to_en(dist_str: str) -> str:
    """Distance sujet-caméra métrique → descripteur anglais."""
    s = (dist_str or "").strip()
    if not s:
        return ""
    try:
        m = float("".join(c for c in s if c.isdigit() or c == "."))
    except (ValueError, TypeError):
        return f"camera at {s} from subject"
    if m <= 0.5:
        return f"camera {m:g}m from subject, very close intimate distance"
    if m <= 1.5:
        return f"camera {m:g}m from subject, close conversational distance"
    if m <= 3:
        return f"camera {m:g}m from subject, natural social distance"
    if m <= 8:
        return f"camera {m:g}m from subject, observational distance"
    return f"camera {m:g}m from subject, distant detached viewpoint"


def focal_to_en(focal_str: str) -> str:
    """Focale → rendu optique anglais (compression, profondeur de champ)."""
    s = (focal_str or "").strip()
    if not s:
        return ""
    try:
        mm = float("".join(c for c in s if c.isdigit() or c == "."))
    except (ValueError, TypeError):
        return f"{s} lens"
    if mm <= 18:
        return f"{mm:g}mm ultra wide-angle lens, strong perspective distortion, deep focus"
    if mm <= 35:
        return f"{mm:g}mm wide-angle lens, expansive field of view, deep depth of field"
    if mm <= 55:
        return f"{mm:g}mm standard lens, natural human perspective"
    if mm <= 100:
        return f"{mm:g}mm portrait lens, shallow depth of field, softly blurred background"
    return f"{mm:g}mm telephoto lens, compressed perspective, very shallow depth of field"


def height_to_en(height_str: str) -> str:
    """Hauteur de caméra → position anglaise. Champ jamais converti auparavant."""
    s = (height_str or "").strip()
    if not s or s in {"—", "-"}:
        return ""
    try:
        m = float("".join(c for c in s if c.isdigit() or c == "."))
    except (ValueError, TypeError):
        return f"camera at {s} height"
    if m <= 0.4:
        return f"camera {m:g}m high, ground-level viewpoint"
    if m <= 1.1:
        return f"camera {m:g}m high, low waist-level viewpoint"
    if m <= 1.8:
        return f"camera {m:g}m high, eye-level viewpoint"
    if m <= 3:
        return f"camera {m:g}m high, slightly elevated viewpoint"
    return f"camera {m:g}m high, high overhead viewpoint"


def speed_to_en(speed: str) -> str:
    """Vitesse → anglais. « Normale » ne produit rien (c'est le défaut)."""
    return SPEED_EN.get((speed or "").strip(), "")


# Profondeur de champ EXPLICITE (colonne du Storyboard).
DOF_EN = {
    "Très courte": "extremely shallow depth of field, strong background blur",
    "Courte":      "shallow depth of field, softly blurred background",
    "Moyenne":     "moderate depth of field",
    "Grande":      "deep focus, foreground and background both sharp",
    "Hyperfocale": "hyperfocal deep focus, everything sharp from foreground to infinity",
}


def dof_to_en(dof: str) -> str:
    """Profondeur de champ → anglais. Vide = déduite de la focale."""
    return DOF_EN.get((dof or "").strip(), "")


# La focale porte déjà une mention de profondeur de champ (« 85mm portrait lens,
# shallow depth of field… »). Quand l'utilisateur règle une profondeur EXPLICITE,
# c'est elle qui fait foi : on retire la mention déduite pour éviter deux
# indications contradictoires dans le même prompt.
_DOF_IN_FOCAL_RE = re.compile(
    r",\s*(?:very\s+)?(?:shallow|deep)\s+depth of field(?:[^,]*)?"
    r"|,\s*softly blurred background"
    r"|,\s*compressed perspective"
    r"|,\s*deep focus",
    re.IGNORECASE,
)


def _focal_without_dof(focal_en: str) -> str:
    """Retire de la description de focale ce qui parle de profondeur de champ."""
    return _DOF_IN_FOCAL_RE.sub("", focal_en or "").strip().rstrip(",")


def camera_terms(shot: dict) -> list[str]:
    """Tous les termes CAMÉRA d'un plan, en anglais, dans l'ordre de lecture d'un
    chef opérateur : valeur → axe → focale → distance → hauteur → mouvement →
    vitesse. Retourne une liste de fragments non vides (jamais None)."""
    if not isinstance(shot, dict):
        return []
    out = []
    _sz = (shot.get("shot_size") or "").strip()
    if _sz in SHOT_SIZE_EN:
        out.append(SHOT_SIZE_EN[_sz])
    _ax = (shot.get("camera_axis") or "").strip()
    if _ax in CAMERA_AXIS_EN:
        out.append(CAMERA_AXIS_EN[_ax])
    _dof = dof_to_en(shot.get("depth_of_field", ""))
    _foc = focal_to_en(shot.get("focal", ""))
    if _dof and _foc:
        _foc = _focal_without_dof(_foc)   # la valeur explicite fait foi
    for _v in (_foc, _dof,
               distance_to_en(shot.get("camera_distance", "")),
               height_to_en(shot.get("camera_height", ""))):
        if _v:
            out.append(_v)
    _mv = (shot.get("camera_movement") or "").strip()
    if _mv:
        out.append(STATIC_EN if _mv.lower() == "fixe" else MOVEMENT_EN.get(_mv, _mv))
    _sp = speed_to_en(shot.get("speed", ""))
    if _sp:
        out.append(_sp)
    return out
