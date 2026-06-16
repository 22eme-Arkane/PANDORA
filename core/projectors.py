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
