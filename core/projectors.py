"""
core/projectors.py — Catalogue des projecteurs de cinéma (Plan de feu).

Deux dimensions INDÉPENDANTES :
  - le RÔLE (fonction dans l'éclairage) : key, fill, back…  → PROJECTOR_ROLES
  - le MODÈLE réel, rangé par FAMILLE de matériel              → FAMILIES / FIXTURES

Une lumière du plan de feu porte donc : role + family + model (+ name, x, y, angle).
Catalogue volontairement LARGE et représentatif (pas exhaustif) — facile à enrichir.
"""

# ── Rôles d'éclairage (fonction) ──────────────────────────────────────────────
# (repris/aligné avec core.staging.PROJECTOR_TYPES)
PROJECTOR_ROLES = [
    ("key",       "Key light (principale)"),
    ("fill",      "Fill (déboucheur)"),
    ("back",      "Back / contre-jour"),
    ("rim",       "Rim (liseré)"),
    ("eye",       "Œil / accent"),
    ("background","Fond / décor"),
    ("practical", "Practical (source dans le décor)"),
    ("ambient",   "Ambiance / général"),
]


# ── Familles de matériel ──────────────────────────────────────────────────────
FAMILIES = [
    ("led_panel", "Panneau LED"),
    ("cob",       "Projecteur COB / Spot"),
    ("fresnel",   "Fresnel"),
    ("tube",      "Tube LED"),
    ("mat",       "Mat souple"),
    ("par_hmi",   "PAR / HMI"),
    ("profile",   "Découpe (profile)"),
    ("balloon",   "Ballon / Space light"),
    ("practical", "Practical / source décor"),
]


# ── Modèles réels par famille ─────────────────────────────────────────────────
FIXTURES = {
    "led_panel": [
        "ARRI SkyPanel S30-C", "ARRI SkyPanel S60-C", "ARRI SkyPanel S120-C",
        "ARRI SkyPanel S360-C", "ARRI Orbiter", "Aputure Nova P300c",
        "Aputure Nova P600c", "Litepanels Gemini 1x1", "Litepanels Gemini 2x1",
        "Creamsource Vortex8", "Creamsource Vortex4", "Kino Flo Celeb 450",
        "Nanlite PavoSlim 60C", "Godox KNOWLED P600R",
    ],
    "cob": [
        "Aputure LS 1200d Pro", "Aputure LS 600x Pro", "Aputure LS 600d Pro",
        "Aputure LS 300d II", "Aputure LS 300x", "Nanlite Forza 500 II",
        "Nanlite Forza 720", "Godox VL300", "Godox SL150 III",
        "Amaran 200d", "Amaran 300c",
    ],
    "fresnel": [
        "ARRI 150 (tungstène)", "ARRI 300 (tungstène)", "ARRI 650 (tungstène)",
        "ARRI 1K (tungstène)", "ARRI 2K (tungstène)", "ARRI L5-C (LED)",
        "ARRI L7-C (LED)", "ARRI L10-C (LED)", "Mole-Richardson Baby 1K",
        "Aputure LS 600d + Fresnel 2X",
    ],
    "tube": [
        "Astera Titan Tube", "Astera Helios Tube", "Astera PixelBrick",
        "Quasar Science Rainbow 2", "Quasar Science Double Rainbow",
        "DMG Dash", "Nanlite PavoTube II 30X", "Nanlite PavoTube II 15X",
        "Digital Sputnik Voyager",
    ],
    "mat": [
        "LiteGear LiteMat 2L", "LiteGear LiteMat 4", "LiteGear LiteMat Spectrum",
        "DMG Lumière SL1 Mix", "DMG Lumière MAXI Mix", "DMG Lumière MINI Mix",
        "Aputure F22c", "Aputure F21c",
    ],
    "par_hmi": [
        "ARRI M18", "ARRI M40", "ARRI M90", "ARRImax 18/12",
        "K5600 Joker-Bug 800", "K5600 Joker 400", "ARRI Compact 1200",
        "ARRI Compact 575",
    ],
    "profile": [
        "ETC Source Four 19°", "ETC Source Four 26°", "ETC Source Four 36°",
        "ETC Source Four LED Series 3", "ARRI L7-C + DoPchoice Snapbag",
        "Dedolight DLED4", "Aputure Spotlight Mount + 600x",
    ],
    "balloon": [
        "Airstar Crystal 1000", "Airstar Tube", "Space light 6x1K",
        "China ball / Lantern", "SoftSun 100K (très puissant)",
    ],
    "practical": [
        "Lampe de table", "Plafonnier", "Néon / tube fluo", "Bougie / flamme",
        "Écran (TV / téléphone)", "Enseigne lumineuse", "Lampadaire",
        "Phare de véhicule", "Feu / cheminée",
    ],
}


# ── Icônes (assets/icons) par famille — badges circulaires du Plan de feu ─────
FAMILY_ICONS = {
    "led_panel": "led panel.png",
    "cob":       "Cobb light.png",
    "fresnel":   "Fresnel light.png",
    "tube":      "Les Tube.png",
    "mat":       "Soft mat light.png",
    "par_hmi":   "HMI light.png",
    "profile":   "Elipsoidal spotlight.png",
    "balloon":   "Pratical Balloon.png",
    "practical": "stage spotlight.png",
}


def family_icon(code: str) -> str:
    """Fichier d'icône (dans assets/icons) pour une famille de projecteur, ou ""."""
    return FAMILY_ICONS.get(code, "")


def families() -> list:
    """[(code, label), …] des familles ayant au moins un modèle."""
    return [(c, l) for c, l in FAMILIES if FIXTURES.get(c)]


def models(family_code: str) -> list:
    """Liste des modèles d'une famille."""
    return list(FIXTURES.get(family_code, []))


def family_label(family_code: str) -> str:
    return next((l for c, l in FAMILIES if c == family_code), family_code)


def role_label(role_code: str) -> str:
    return next((l for c, l in PROJECTOR_ROLES if c == role_code), role_code)


# ── Capacités réglables par projecteur (d'après les specs constructeur) ──────────
# « color » décrit le système de couleur, donc les réglages disponibles :
#   full     → RGBWW : intensité + CCT (plage) + teinte (hue/sat) + ±vert
#   bicolor  → blanc variable : intensité + CCT (plage) + ±vert
#   daylight → 5600 K fixe (HMI/LED jour) : intensité + gélatines
#   tungsten → 3200 K fixe : intensité + gélatines
#   source   → source pratique du décor (CCT caractéristique) : intensité (lueur)
# cct = (min, max) en kelvins, ou (k, k) si fixe. beam = (min,max)° de faisceau,
# ou None pour les sources douces/surfaciques. cri = IRC/TLCI indicatif.
_CAP_DEFAULT = {"color": "bicolor", "cct": (2700, 6500), "dimmable": True,
                "beam": None, "cri": 95}

_CAP_FAMILY = {
    "led_panel": {"color": "full",     "cct": (2800, 10000), "beam": None, "cri": 95},
    "cob":       {"color": "daylight", "cct": (5600, 5600),  "beam": (15, 55), "cri": 96},
    "fresnel":   {"color": "tungsten", "cct": (3200, 3200),  "beam": (15, 60), "cri": 100},
    "tube":      {"color": "full",     "cct": (1750, 10000), "beam": None, "cri": 96},
    "mat":       {"color": "full",     "cct": (2700, 6500),  "beam": None, "cri": 96},
    "par_hmi":   {"color": "daylight", "cct": (5600, 5600),  "beam": (10, 60), "cri": 90},
    "profile":   {"color": "tungsten", "cct": (3200, 3200),  "beam": (19, 50), "cri": 100},
    "balloon":   {"color": "daylight", "cct": (5600, 5600),  "beam": None, "cri": 90},
    "practical": {"color": "source",   "cct": (3000, 3000),  "beam": None, "cri": 80},
}

# Overrides PAR MODÈLE (sous-chaîne, minuscule, 1er match gagne — du + spécifique
# au + générique). Capture les différences réelles au sein d'une même famille.
_CAP_MODEL = [
    # — COB : daylight (d) · bicolore (x) · couleur (c) —
    ("ls 600x",        {"color": "bicolor",  "cct": (2700, 6500)}),
    ("ls 300x",        {"color": "bicolor",  "cct": (2700, 6500)}),
    ("amaran 300c",    {"color": "full",     "cct": (2500, 7500)}),
    ("amaran 200d",    {"color": "daylight", "cct": (5600, 5600)}),
    ("nanlite forza",  {"color": "daylight", "cct": (5600, 5600)}),
    ("godox vl300",    {"color": "daylight", "cct": (5600, 5600)}),
    ("godox sl150",    {"color": "daylight", "cct": (5600, 5600)}),
    ("ls 1200d",       {"color": "daylight", "cct": (5600, 5600)}),
    ("ls 600d",        {"color": "daylight", "cct": (5600, 5600)}),
    ("ls 300d",        {"color": "daylight", "cct": (5600, 5600)}),
    # — Fresnel LED ARRI L-series = couleur ; reste = tungstène (défaut famille) —
    ("l5-c",           {"color": "full",     "cct": (2800, 10000)}),
    ("l7-c",           {"color": "full",     "cct": (2800, 10000)}),
    ("l10-c",          {"color": "full",     "cct": (2800, 10000)}),
    ("600d + fresnel", {"color": "daylight", "cct": (5600, 5600)}),
    # — Panneaux LED : Kino Celeb = bicolore tunable —
    ("celeb 450",      {"color": "bicolor",  "cct": (2700, 5500)}),
    # — Mats souples : LiteMat 2L / 4 = bicolore ; Mix/Spectrum/F-c = couleur —
    ("litemat 2l",     {"color": "bicolor",  "cct": (2900, 6500)}),
    ("litemat 4",      {"color": "bicolor",  "cct": (2900, 6500)}),
    # — Découpes : ETC LED couleur ; Dedolight bicolore ; Source Four = tungstène —
    ("source four led", {"color": "full",    "cct": (2700, 6500)}),
    ("dedolight dled4", {"color": "bicolor", "cct": (2700, 6500)}),
    ("spotlight mount", {"color": "bicolor", "cct": (2700, 6500)}),
    # — Ballons / space lights —
    ("softsun",        {"color": "daylight", "cct": (5600, 5600)}),
    ("china ball",     {"color": "tungsten", "cct": (3200, 3200)}),
    ("lantern",        {"color": "tungsten", "cct": (3200, 3200)}),
    ("space light",    {"color": "tungsten", "cct": (3200, 3200)}),
    # — Practicals : CCT caractéristique de la source —
    ("bougie",         {"color": "source", "cct": (1800, 1800)}),
    ("flamme",         {"color": "source", "cct": (1800, 1800)}),
    ("feu",            {"color": "source", "cct": (1900, 1900)}),
    ("cheminée",       {"color": "source", "cct": (1900, 1900)}),
    ("néon",           {"color": "source", "cct": (5000, 5000)}),
    ("fluo",           {"color": "source", "cct": (4300, 4300)}),
    ("écran",          {"color": "source", "cct": (6500, 6500)}),
    ("tv",             {"color": "source", "cct": (6500, 6500)}),
    ("téléphone",      {"color": "source", "cct": (6500, 6500)}),
    ("enseigne",       {"color": "source", "cct": (5000, 5000)}),
    ("lampadaire",     {"color": "source", "cct": (2200, 2200)}),
    ("phare",          {"color": "source", "cct": (4500, 4500)}),
    ("plafonnier",     {"color": "source", "cct": (3500, 3500)}),
    ("lampe",          {"color": "source", "cct": (2700, 2700)}),
]

# Préréglages de gélatine (fixtures à blanc fixe) — code + libellé FR (effet prompt).
GEL_PRESETS = [
    ("",           "Aucune"),
    ("ctb_full",   "CTB pleine (tungstène → jour, bleu froid)"),
    ("ctb_half",   "1/2 CTB (refroidit légèrement)"),
    ("cto_full",   "CTO pleine (jour → tungstène, ambre chaud)"),
    ("cto_half",   "1/2 CTO (réchauffe légèrement)"),
    ("plus_green", "Plus Green (correction fluo)"),
    ("minus_green","Minus Green / magenta"),
    ("straw",      "Paille (warm doré)"),
    ("steel_blue", "Steel Blue (bleu nuit)"),
    ("congo",      "Congo (bleu profond / nuit américaine)"),
    ("rose",       "Rose (peau / romantique)"),
    ("red",        "Rouge"),
    ("amber",      "Ambre"),
    ("cyan",       "Cyan"),
]


def capabilities(family: str, model: str = "") -> dict:
    """Capacités réglables d'un projecteur (défaut famille + overrides modèle)."""
    cap = dict(_CAP_FAMILY.get(family, _CAP_DEFAULT))
    ml = (model or "").lower()
    for kw, override in _CAP_MODEL:
        if kw in ml:
            cap.update(override)
            break
    # Découpe ellipsoïdale : faisceau FIXE déduit du degré dans le nom (19°/26°/36°).
    import re as _re
    m = _re.search(r"(\d{2})\s*°", model or "")
    if family == "profile" and m:
        deg = int(m.group(1))
        cap["beam"] = (deg, deg)
    # Capacités dérivées : effets dynamiques (LED couleur/bicolore) et accessoire
    # louver / nid d'abeille (toutes sauf sources pratiques et ballons diffus).
    cap["effects"] = cap["color"] in ("full", "bicolor")
    cap["louver"]  = cap["color"] != "source" and family != "balloon"
    return cap


# ── Effets dynamiques (fixtures à LED couleur : SkyPanel, Titan…) ───────────────
# code + libellé FR + description (prompt). « à la place » des réglages statiques.
EFFECTS = [
    ("",          "Aucun effet",     ""),
    ("candle",    "Bougie",          "vacillement chaud et irrégulier de flamme de bougie"),
    ("fire",      "Feu / flammes",   "lueur de feu mouvante, oranges et rouges qui dansent"),
    ("tv",        "Téléviseur",      "scintillement bleuté de téléviseur, variations rapides"),
    ("lightning", "Orage / éclairs", "éclairs d'orage, flashs blancs brefs et intenses"),
    ("police",    "Gyrophare",       "gyrophare : flashs alternés bleu et rouge"),
    ("paparazzi", "Paparazzi",       "flashs d'appareils photo, éclats blancs aléatoires"),
    ("pulse",     "Pulsation",       "pulsation lumineuse rythmée (battement)"),
    ("club",      "Club / disco",    "ambiance club, couleurs changeantes rythmées"),
    ("strobe",    "Stroboscope",     "stroboscope rapide, flashs saccadés"),
    ("fireworks", "Feux d'artifice", "reflets de feux d'artifice, éclats colorés intermittents"),
]


def effect_label(code: str) -> str:
    return next((l for c, l, _ in EFFECTS if c == code), code)


def effect_desc(code: str) -> str:
    return next((d for c, _, d in EFFECTS if c == code), "")


def default_settings(family: str, model: str = "") -> dict:
    """Réglages par défaut cohérents avec les capacités (CCT au milieu de plage)."""
    cap = capabilities(family, model)
    lo, hi = cap["cct"]
    cct = lo if lo == hi else (5600 if (lo <= 5600 <= hi) else (lo + hi) // 2)
    beam = cap["beam"]
    return {
        "on":            True,    # allumé ; éteint → grisé + exclu du prompt
        "intensity":     100,
        "cct":           cct,
        "hue":           0,       # 0 = blanc (pas de teinte)
        "saturation":    0,       # 0..100
        "green_magenta": 0,       # -100 (magenta) .. +100 (vert)
        "gel":           "",
        "beam":          (beam[0] + beam[1]) // 2 if beam else 0,
        "height":        2.5,     # hauteur en mètres (du sol)
        "tilt":          90,      # inclinaison : 90 = horizontale ; < = plongée
        "louver":        False,   # louver / nid d'abeille (faisceau resserré)
        "effect":        "",      # effet dynamique (remplace la couleur statique)
    }


_KELVIN_LABELS = [
    (2000, "très chaud (bougie/sodium)"), (3300, "tungstène chaud"),
    (4500, "blanc neutre"), (5800, "lumière du jour"),
    (7000, "blanc froid"), (20000, "bleuté froid"),
]


def kelvin_label(cct: int) -> str:
    for k, lbl in _KELVIN_LABELS:
        if cct <= k:
            return lbl
    return "bleuté froid"


def _hue_label(hue: int) -> str:
    # Libellés TRANCHÉS (une seule couleur, jamais « rose/rouge ») pour éviter
    # toute imprécision dans le prompt.
    table = [(15, "rouge"), (40, "orange"), (65, "jaune"), (155, "vert"),
             (195, "cyan"), (255, "bleu"), (290, "violet"), (335, "magenta"), (360, "rouge")]
    for h, lbl in table:
        if hue <= h:
            return lbl
    return "rouge"


def describe_settings(light: dict) -> str:
    """Phrase FR décrivant les réglages d'un projecteur, pour le prompt
    [💡 PLAN DE FEU]. Reste fidèle aux capacités du modèle."""
    cap = capabilities(light.get("family", ""), light.get("model", ""))
    s = light.get("settings") or {}
    if not s.get("on", True):
        return "ÉTEINT (n'éclaire pas)"
    parts = []
    inten = s.get("intensity", 100)
    if inten != 100:
        parts.append(f"intensité {inten} %")
    # Effet dynamique → REMPLACE la couleur statique (bougie, gyrophare…).
    eff = s.get("effect", "")
    has_tint = cap["color"] == "full" and s.get("saturation", 0) > 0
    if eff and cap.get("effects"):
        parts.append(f"EFFET {effect_label(eff).lower()} ({effect_desc(eff)})")
    elif has_tint:
        # Une TEINTE colorée remplace la température : on n'écrit PAS le CCT, sinon
        # « lumière rouge » + « tungstène » se contredisent. Lumière colorée nette.
        parts.append(f"lumière colorée {_hue_label(s.get('hue', 0))} saturée à {s.get('saturation')} %")
        gm = s.get("green_magenta", 0)
        if gm:
            parts.append(("correction verte" if gm > 0 else "correction magenta") + f" {abs(gm)} %")
    else:
        cct = s.get("cct") or cap["cct"][0]
        parts.append(f"{cct} K ({kelvin_label(cct)})")
        gm = s.get("green_magenta", 0)
        if gm:
            parts.append(("correction verte" if gm > 0 else "correction magenta") + f" {abs(gm)} %")
        gel = s.get("gel", "")
        if gel:
            lbl = next((l for c, l in GEL_PRESETS if c == gel), gel)
            parts.append(f"gélatine {lbl}")
    # Hauteur + inclinaison (déterminent la direction verticale de la lumière).
    h = s.get("height")
    if h:
        parts.append(f"à {h:g} m de haut")
    tilt = s.get("tilt", 90)
    if tilt >= 85:
        parts.append("à hauteur du sujet (horizontale)")
    elif tilt >= 70:
        parts.append(f"inclinée à {tilt}° (légère plongée)")
    elif tilt >= 40:
        parts.append(f"inclinée à {tilt}° (plongée)")
    else:
        parts.append(f"inclinée à {tilt}° (forte plongée, quasi top light)")
    if s.get("louver") and cap.get("louver"):
        parts.append("avec louver / nid d'abeille (faisceau resserré, peu de débordement)")
    beam = s.get("beam", 0)
    if beam and cap.get("beam"):
        kind = "serré" if beam <= 25 else ("large" if beam >= 45 else "moyen")
        parts.append(f"faisceau {beam}° ({kind})")
    return ", ".join(parts)


# ── Ambiance / mood (en plus des termes techniques) ───────────────────────────
# Qualité de lumière propre à CHAQUE famille de projecteur — ce que Seedance doit
# « ressentir » (le modèle ne connaît pas les termes techniques type « SkyPanel S60 »,
# mais comprend « lumière douce et enveloppante »).
_FAMILY_QUALITY = {
    "led_panel": "lumière douce et enveloppante (grand panneau)",
    "mat":       "lumière très douce et diffuse, sans ombre dure",
    "cob":       "lumière franche et directionnelle",
    "fresnel":   "lumière modelée à la décroissance douce",
    "tube":      "accent lumineux linéaire et précis",
    "par_hmi":   "lumière vive et puissante, type lumière du jour",
    "profile":   "faisceau net aux bords découpés",
    "balloon":   "nappe de lumière douce tombant d'en haut",
    "practical": "source d'appoint intégrée au décor",
}


def ambiance_phrase(light: dict) -> str:
    """Phrase d'AMBIANCE (mood) calquée sur le TYPE de projecteur + ses réglages,
    en complément des termes techniques de describe_settings. Décrit ce que la
    lumière PRODUIT (chaleur, douceur/contraste, couleur), pas le matériel.
    Vide si le projecteur est éteint."""
    s = light.get("settings") or {}
    if not s.get("on", True):
        return ""
    fam = (light.get("family") or "").strip()
    cap = capabilities(fam, light.get("model", ""))
    quality = _FAMILY_QUALITY.get(fam, "lumière")

    eff = s.get("effect", "")
    if eff and cap.get("effects"):
        mood = f"ambiance {effect_label(eff).lower()}"
    elif cap.get("color") == "full" and s.get("saturation", 0) > 0:
        mood = f"ambiance colorée {_hue_label(s.get('hue', 0))}, atmosphère stylisée"
    else:
        cct = s.get("cct") or cap["cct"][0]
        if cct <= 3500:
            mood = "ambiance chaude et intime"
        elif cct >= 5600:
            mood = "ambiance froide, presque clinique"
        else:
            mood = "ambiance neutre et naturelle"

    # Douceur des ombres : familles douces (panneau/mat/ballon) sans louver →
    # ombres délicates ; sinon faisceau plus contrasté.
    soft = (fam in ("led_panel", "mat", "balloon")) and not s.get("louver")
    contrast = ("lumière douce aux ombres délicates" if soft
                else "lumière plus contrastée aux ombres marquées")
    return f"{mood}, {quality}, {contrast}"
