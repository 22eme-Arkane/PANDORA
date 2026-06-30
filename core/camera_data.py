"""
Données de référence pour le matériel cinéma : corps de caméra, optiques, filtres, micros.
Utilisé par page_camera.py (page de sélection) et tab_t2v.py (prompt enrichi Seedance).
"""

# ── Corps de caméra par marque ─────────────────────────────────────────────────

CAMERA_BODIES: dict[str, list[str]] = {
    "ARRI": [
        "Alexa 65",
        "Alexa 35",
        "Alexa Mini LF",
        "Alexa Mini",
        "Alexa LF",
        "Alexa XT / SXT / Classic",
        "Arricam ST (35mm argentique)",
        "Arricam LT (35mm argentique)",
        "Arriflex 435 (35mm argentique)",
        "Arriflex 235 (35mm argentique)",
        "Arriflex 416 (16mm argentique)",
    ],
    "RED Digital Cinema": [
        "V-Raptor XL",
        "V-Raptor [X]",
        "Komodo-X",
        "Komodo",
        "Ranger Monstro",
        "Ranger Helium",
        "Ranger Gemini",
        "DSMC2 Monstro",
        "DSMC2 Helium",
        "DSMC2 Gemini",
        "DSMC2 Dragon",
        "Epic / Scarlet",
        "RED One",
    ],
    "Panavision": [
        "Millennium DXL2",
        "Panaflex Millennium XL2 (35mm argentique)",
        "Panaflex Platinum (35mm argentique)",
        "Panavision System 65 (65mm argentique)",
    ],
    "Sony CineAlta": [
        "Venice 2",
        "Venice",
        "Burano",
        "F65",
    ],
    "Canon Cinema EOS": [
        "EOS C700 FF",
        "EOS C500 Mark II",
        "EOS C300 Mark III",
        "EOS C400",
    ],
    "Blackmagic Design": [
        "URSA Cine 17K",
        "URSA Cine 12K",
        "URSA Mini Pro 12K",
        "URSA Mini Pro 4.6K G2",
        "Blackmagic Cinema Camera 6K",
    ],
    "Aaton": [
        "Penelope (35mm argentique)",
        "XTR Prod (16mm argentique)",
        "A-Minima (16mm argentique)",
    ],
    "IMAX": [
        "IMAX MSM 9802 (65/70mm argentique)",
        "IMAX MKIV (65/70mm argentique)",
        "IMAX MKIII (65/70mm argentique)",
    ],
}

# ── Optiques par marque / série ────────────────────────────────────────────────

OPTICS_DATA: dict[str, list[str]] = {
    "ARRI / Zeiss": [
        "Master Primes",
        "Ultra Primes",
        "Super Speeds (Vintage)",
    ],
    "ARRI": [
        "Signature Primes",
        "Master Macro 100mm T2.0",
    ],
    "Panavision": [
        "Primo Primes",
        "C-Series (Anamorphique)",
        "T-Series / G-Series (Anamorphique)",
        "Panaspeed",
        "Auto Panatar Macro / Primo Macro",
    ],
    "Cooke Optics": [
        "S4/i (Sphérique)",
        "S5/i (Sphérique)",
        "S7/i (Sphérique)",
        "Panchro/i Classic (Vintage moderne)",
        "Anamorphic/i (Anamorphique)",
        "Macro/i",
    ],
    "Angénieux": [
        "Optimo (Zooms de référence)",
        "Optimo Primes",
        "EZ Series",
    ],
    "Zeiss": [
        "Supreme Primes",
        "Supreme Primes Radiance",
        "Compact Primes CP.2",
        "Compact Primes CP.3",
        "Compact Prime Macro (CP.2 / CP.3)",
    ],
    "Leitz (Leica)": [
        "Summilux-C",
        "Summicron-C",
        "Thalia",
    ],
    "Fujinon": [
        "Premista (Zooms Plein Format)",
        "Cabrio",
        "Alura (Zooms / ARRI)",
    ],
    "Canon": [
        "CN-E Primes",
        "Sumire Primes",
    ],
    "Laowa (Venus Optics)": [
        "24mm Probe / PeriProbe",
        "24mm T8 2X Macro Pro2be",
        "Ranger Macro / APO Macro Cinema",
    ],
    "IB/E Optics": [
        "Raptor Macro 100mm",
        "Raptor Macro 150mm",
        "Raptor Macro 180mm",
    ],
    "Tokina Cinema": [
        "Vista Macro 100mm T2.9",
        "ATX Macro",
    ],
    "Infinity Photo-Optical": [
        "TS-160 Robusto (micro/macro)",
        "MikroMak Primes",
    ],
    "Vantage (Hawk)": [
        "Hawk Macro",
        "Hawk V-Series (Anamorphique)",
        "Hawk C-Series (Anamorphique)",
    ],
}

# ── Filtres par marque ─────────────────────────────────────────────────────────

FILTERS_DATA: dict[str, list[str]] = {
    "Tiffen": [
        "Black Pro-Mist",
        "Pro-Mist",
        "Glimmerglass",
        "Black Glimmerglass",
        "Pearlescent",
        "Black Pearlescent",
        "Satin",
        "Black Satin",
        "NATural ND",
        "IRND",
        "Ultra Pola (Polarisant)",
    ],
    "Schneider Optics": [
        "Hollywood Black Magic",
        "Classic Soft",
        "Radiant Soft",
        "True-Net",
        "Rhodium FSND",
        "Platinum IRND",
        "True-Pol (Polarisant)",
    ],
    "ARRI": [
        "FSND (Full Spectrum Neutral Density)",
    ],
    "Formatt-Hitech": [
        "Firecrest IRND",
        "Firecrest Ultra",
    ],
    "NiSi": [
        "Allure Mist Black",
        "Allure Mist White",
        "Cinema Nano IRND",
        "Allure Streak (Flares)",
    ],
    "Lindsey Optics": [
        "Brilliant IRND",
        "Brilliant-Pol",
        "Brilliant² Rota-Pol",
    ],
    "Revar Cine": [
        "Rota Pola (Polarisant rotatif)",
        "Anamorphic Flare Streak",
    ],
}

# ── Microphones par catégorie ──────────────────────────────────────────────────

MIC_DATA: dict[str, list[str]] = {
    "Schoeps (Perche)": [
        "MK 41 (Supercardioid)",
        "MK 4 (Cardioid)",
        "MK 8 (Bidirectionnel)",
        "CMIT 5U (Shotgun)",
    ],
    "Sennheiser (Perche)": [
        "MKH 50 (Supercardioid)",
        "MKH 60 (Shotgun court)",
        "MKH 70 (Shotgun long)",
        "MKH 416 (Référence shotgun)",
        "MKH 8050",
        "MKH 8060",
    ],
    "Neumann (Perche)": [
        "KM 184 (Cardioid)",
        "TLM 103",
        "TLM 170 R",
        "U87 Ai",
    ],
    "DPA (Perche / Lavalier)": [
        "4017B (Shotgun)",
        "4011A (Cardioid)",
        "4060 (Omni miniature)",
        "4061 (Omni miniature)",
        "6060 (Subminiature lavalier)",
    ],
    "Sanken (Lavalier)": [
        "CS-3e (Shotgun)",
        "COS-11D (Lavalier)",
        "CUB-01 (Lavalier miniature)",
    ],
    "Lectrosonics (Sans fil)": [
        "SMQv (Émetteur bodypack)",
        "SSM (Émetteur miniature)",
        "SRc / SRb (Récepteur double)",
        "DCHR (Récepteur)",
    ],
    "Zaxcom (Sans fil)": [
        "ZHD600 (Émetteur)",
        "MAXX (Enregistreur mixeur)",
        "Nova (Enregistreur mixeur)",
    ],
    "Wisycom (Sans fil)": [
        "MTP40S (Émetteur bodypack)",
        "MCR42 (Récepteur double)",
        "MCR54 (Récepteur quad)",
    ],
    "Sound Devices (Enregistreurs)": [
        "MixPre-10M",
        "888",
        "702T",
        "Scorpio",
    ],
    "Aaton (Enregistreurs)": [
        "CanTar X3",
        "CanTar Mini",
    ],
}

# ── Mouvements de plan ────────────────────────────────────────────────────────

SHOT_MOVEMENTS: list[str] = [
    "Trépied",
    "Travelling",
    "Steadycam",
    "Fixe",
    "Grue",
    "Drone",
    "Sous-Marin",
    "Panoramique",
]

_MOVEMENT_EN: dict[str, str] = {
    "Trépied":     "tripod shot",
    "Travelling":  "tracking shot",
    "Steadycam":   "steadicam shot",
    "Fixe":        "static shot",
    "Grue":        "crane shot",
    "Drone":       "drone aerial shot",
    "Sous-Marin":  "underwater shot",
    "Panoramique": "pan shot",
}

# ── Mouvement caméra du STORYBOARD → directive EXPLICITE pour Seedance ───────────
# « Fixe » formulé fortement : sans ça, le modèle dérive souvent en travelling/grue.
_SHOT_MOVEMENT_EN: dict[str, str] = {
    "Fixe":                   "locked-off static camera, fixed tripod shot, absolutely no camera movement, no pan, no tilt, no dolly, no zoom",
    "Panoramique horizontal": "smooth horizontal panning camera movement",
    "Panoramique vertical":   "smooth vertical tilting camera movement",
    "Travelling avant":       "smooth dolly-in, camera tracking forward toward the subject",
    "Travelling arrière":     "smooth dolly-out, camera tracking backward away from the subject",
    "Travelling latéral":     "lateral tracking shot, camera dollying sideways",
    "Zoom avant":             "slow zoom in",
    "Zoom arrière":           "slow zoom out",
    "Steadicam":              "smooth flowing steadicam camera movement",
    "Grue / Drone":           "sweeping crane / drone aerial camera movement",
    "Drone FPV":              "immersive FPV drone shot, first-person-view racing drone flight, fast and agile with rapid acceleration, swooping dives, rolls and tight banking turns, low-altitude proximity fly-through weaving close to subjects and obstacles, continuous momentum and speed, ultra-wide action-camera perspective, dynamic and visceral",
    "Caméra portée":          "handheld camera, subtle organic shake",
    "Plongée":                "high-angle shot looking down on the subject",
    "Contre-plongée":         "low-angle shot looking up at the subject",
}


def shot_movement_to_prompt(movement: str) -> str:
    """Mouvement caméra d'un plan storyboard → directive EXPLICITE (anglais) pour
    Seedance. Renvoie "" si inconnu/vide. « Fixe » est formulé fortement pour que
    le modèle ne dérive pas en mouvement de caméra."""
    return _SHOT_MOVEMENT_EN.get((movement or "").strip(), "")

# ── Helpers ────────────────────────────────────────────────────────────────────

def all_camera_brands() -> list[str]:
    return list(CAMERA_BODIES.keys())


def bodies_for_brand(brand: str) -> list[str]:
    return CAMERA_BODIES.get(brand, [])


def all_optics_brands() -> list[str]:
    return list(OPTICS_DATA.keys())


def series_for_brand(brand: str) -> list[str]:
    return OPTICS_DATA.get(brand, [])


def all_filter_brands() -> list[str]:
    return list(FILTERS_DATA.keys())


def filters_for_brand(brand: str) -> list[str]:
    return FILTERS_DATA.get(brand, [])


def all_mic_categories() -> list[str]:
    return list(MIC_DATA.keys())


def mics_for_category(category: str) -> list[str]:
    return MIC_DATA.get(category, [])


_FOCAL_FRAMING: list[tuple[int, str]] = [
    (8,   "extreme wide angle fisheye shot"),
    (14,  "ultra wide angle shot"),
    (18,  "wide establishing shot"),
    (24,  "wide shot"),
    (35,  "medium wide shot"),
    (50,  "medium shot"),
    (65,  "medium close-up"),
    (85,  "close-up shot"),
    (135, "tight close-up"),
    (200, "extreme close-up"),
]


def focal_to_framing_prefix(focal: str) -> str:
    """Converts a focal string like '85mm' to a Seedance-friendly framing keyword.
    Returns empty string if focal can't be parsed."""
    import re
    m = re.match(r"(\d+)", focal.strip())
    if not m:
        return ""
    mm = int(m.group(1))
    # Walk thresholds: return the label whose breakpoint is closest
    closest_label = ""
    closest_dist  = 9999
    for threshold, label in _FOCAL_FRAMING:
        dist = abs(threshold - mm)
        if dist < closest_dist:
            closest_dist  = dist
            closest_label = label
    return closest_label


def build_camera_prompt_suffix(prefs: dict) -> str:
    """
    Builds an English Seedance prompt suffix from camera preferences.
    Example: "Shot on ARRI Alexa 35, Cooke S4/i lenses, Tiffen Black Pro-Mist filter"
    """
    parts = []
    body = prefs.get("camera_body", "").strip()
    if body:
        parts.append(f"shot on {body}")

    optics = prefs.get("optics_series", "").strip()
    if optics:
        brand  = prefs.get("optics_brand", "").strip()
        label  = f"{brand} {optics}" if brand else optics
        parts.append(f"{label} lenses")

    filters = prefs.get("filters", [])
    if filters:
        filter_str = ", ".join(filters)
        parts.append(f"{filter_str} filter{'s' if len(filters) > 1 else ''}")

    mic = " ".join(filter(None, [
        prefs.get("mic_category", "").strip(),
        prefs.get("mic_model", "").strip(),
    ]))
    if mic:
        parts.append(f"audio with {mic}")

    movement = prefs.get("shot_movement", "").strip()
    if movement:
        parts.append(_MOVEMENT_EN.get(movement, movement))

    return ", ".join(parts)
