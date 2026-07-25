"""
core/image_grammar.py — Grammaire de prompt par moteur IMAGE.

Pendant du volet vidéo (`core/engine_grammar.py`), pour tout ce qui produit une
IMAGE : portraits de casting, décors, accessoires, véhicules, HMC, moods du
storyboard, et l'onglet Image IA.

Trois grammaires (dossier de recherche fal.ai fourni par Matthieu, 25/07/2026 —
celui-ci s'appuie sur de vrais guides de prompting publiés par fal, pas sur des
reconstructions) :

  fields   — Nano Banana Pro, GPT Image 2 : brief de directeur artistique à champs
             nommés (Subject / Action / Setting / Style / Composition and camera /
             Lighting and color / Text / Constraints). Les NÉGATIFS sont supportés
             et attendus : la doc dit que la liste de contraintes n'est pas
             optionnelle.

  natural  — Seedream 5 : 2 à 4 phrases descriptives en langage naturel. Le modèle
             fait une passe de raisonnement avant de peindre.
             ⚠ ByteDance a RETIRÉ de l'API le prompt négatif, le seed, le guidance
             scale et le nombre de steps. On ne peut donc RIEN interdire : les
             contraintes doivent être converties en descriptions POSITIVES (occuper
             la place au lieu d'interdire) ou abandonnées. Les « quality boosters »
             (masterpiece, best quality, 8K) DÉGRADENT le résultat en distrayant la
             passe de raisonnement — ils sont retirés.

  json     — FLUX.2, Bria FIBO : objet à clés. Les négatifs sont mal gérés (ignorés).
             Les codes HEX sont lus s'ils sont précédés du mot « hex » ou « color ».

Règles communes : une image fige UN INSTANT (jamais une durée), aucun emoji ni
crochet dans le payload, pas de nom propre d'IP/studio (réutilise le filtre du volet
vidéo), et les adjectifs creux ne se rendent pas — « peinture écaillée » se dessine,
« magnifique » non.
"""

from __future__ import annotations

import re


# Clé de moteur image → grammaire.
_GRAMMAR_BY_ENGINE = {
    # Brief à champs (négatifs supportés)
    "nb2":              "fields",
    "nano_banana":      "fields",
    "nano_banana_pro":  "fields",
    "gpt_image_2":      "fields",
    "gpt-image-2":      "fields",
    # Langage naturel raisonné (AUCUN négatif possible)
    "seedream5":        "natural",
    "seedream5_pro":    "natural",
    "seedream5_lite":   "natural",
    "seedream":         "natural",
    # JSON structuré
    "flux2":            "json",
    "flux_2":           "json",
    "flux2_pro":        "json",
    "flux2_flex":       "json",
    "fibo":             "json",
}

GRAMMAR_LABELS = {
    "fields":  "brief à champs (Nano Banana Pro / GPT Image 2)",
    "natural": "langage naturel, sans négatif (Seedream 5)",
    "json":    "JSON structuré (FLUX.2)",
    "plain":   "prose descriptive",
}

# Moteurs SANS prompt négatif ni seed : l'API les a retirés.
NO_NEGATIVE_ENGINES = {"seedream5", "seedream5_pro", "seedream5_lite", "seedream"}


def grammar_for(engine_key: str) -> str:
    """Grammaire attendue par ce moteur image. Repli « plain »."""
    return _GRAMMAR_BY_ENGINE.get((engine_key or "").strip().lower(), "plain")


def grammar_label(engine_key: str) -> str:
    return GRAMMAR_LABELS.get(grammar_for(engine_key), GRAMMAR_LABELS["plain"])


def supports_negatives(engine_key: str) -> bool:
    """Ce moteur accepte-t-il des contraintes négatives ?

    False pour Seedream 5 (retirées de l'API) et pour le JSON de FLUX.2, qui les
    ignore. Dans ces cas il faut convertir les contraintes en positif."""
    g = grammar_for(engine_key)
    if (engine_key or "").strip().lower() in NO_NEGATIVE_ENGINES:
        return False
    return g == "fields"


# ── Contraintes ────────────────────────────────────────────────────────────────

# Valables pour toute image de production, quel que soit le sujet.
BASE_CONSTRAINTS = [
    "no text or lettering anywhere",
    "no watermark",
    "no extra fingers",
    "no lens flare",
    "no stock-photo polish",
]

# Contraintes CONTEXTUELLES — ajoutées seulement quand le cas se présente.
# ⚠ « no halo / no nimbus / no religious iconography » n'est PAS universel : le
# dossier le prescrit « tant que le personnage est celui-là ». L'ajouter partout
# polluerait les projets qui n'ont rien de religieux.
_RELIGIOUS_HINTS = (
    "jésus", "jesus", "christ", "vierge", "marie", "saint", "sainte", "apôtre",
    "apotre", "moïse", "moise", "bouddha", "buddha", "prophète", "prophete",
    "ange", "angel", "madone", "madonna",
)
RELIGIOUS_CONSTRAINTS = [
    "no halo", "no nimbus", "no religious iconography",
]
SOLO_CONSTRAINT = "no second person"


def context_constraints(subject_text: str = "", solo: bool = False) -> list[str]:
    """Contraintes contextuelles à ajouter aux contraintes de base.

    `subject_text` : nom/description du sujet — s'il évoque une figure religieuse,
    on ajoute l'anti-auréole (les modèles ajoutent un halo par défaut dès qu'ils
    reconnaissent le personnage, ce qui casse une intention comique).
    `solo` : le plan ne contient qu'un personnage → interdire un second."""
    out = []
    low = (subject_text or "").lower()
    if any(h in low for h in _RELIGIOUS_HINTS):
        out.extend(RELIGIOUS_CONSTRAINTS)
    if solo:
        out.append(SOLO_CONSTRAINT)
    return out


# Conversion des interdits en formulations POSITIVES, pour les moteurs qui ne
# savent pas interdire (Seedream 5). « On n'interdit pas, on occupe la place. »
_POSITIVE_REWRITES = {
    "no halo": "bare head, uncovered hair",
    "no nimbus": "plain sky directly behind the head",
    # ⚠ La réécriture ne doit contenir AUCUN « no » : sur un moteur sans négatif,
    # le mot serait lu comme un élément à représenter.
    "no religious iconography": "plain everyday setting",
    "no second person": "completely alone in the frame",
    "no visible lamp or light source in frame":
        "lit entirely by natural light coming from outside the frame",
    "no text or lettering anywhere": "clean surfaces without signage",
    "no watermark": "clean uncluttered image",
    "no lens flare": "clean optics",
    "no stock-photo polish": "raw, naturalistic rendering",
}


def to_positive(constraints: list[str]) -> list[str]:
    """Réécrit des contraintes négatives en descriptions positives.

    Celles qui n'ont pas d'équivalent positif utile (« no extra fingers ») sont
    ABANDONNÉES plutôt que traduites mot à mot : sur un moteur sans négatif, écrire
    « extra fingers » augmenterait la probabilité d'en voir."""
    out = []
    for c in constraints or []:
        v = _POSITIVE_REWRITES.get((c or "").strip().lower())
        if v and v not in out:
            out.append(v)
    return out


# « Quality boosters » : dégradent Seedream 5 (ils distraient la passe de
# raisonnement) et sont interdits par la doctrine de prompt de PANDORA.
_BOOSTERS_RE = re.compile(
    r"(?<![A-Za-zÀ-ÿ])(masterpiece|best quality|high quality|ultra[- ]?hd|8k|4k|"
    r"highly detailed|ultra[- ]?detailed|award[- ]winning|trending on artstation)"
    r"(?![A-Za-zÀ-ÿ])",
    re.IGNORECASE,
)


def strip_quality_boosters(text: str) -> tuple[str, list[str]]:
    """Retire les mots de qualité génériques. Retourne (texte, retirés)."""
    found = []
    for m in _BOOSTERS_RE.finditer(text or ""):
        v = m.group(0)
        if v.lower() not in {f.lower() for f in found}:
            found.append(v)
    if not found:
        return (text or ""), []
    out = _BOOSTERS_RE.sub("", text or "")
    out = re.sub(r"\s*,\s*,+", ", ", out)
    out = re.sub(r"[ \t]{2,}", " ", out)
    out = re.sub(r"\s+([,.;:])", r"\1", out)
    out = re.sub(r"^[\s,;:]+|[\s,;:]+$", "", out)
    return out.strip(), found


# ── Syntaxe des références multi-images ────────────────────────────────────────
# Cinq moteurs, cinq syntaxes NON interchangeables. C'est la première chose à
# encoder dans les adaptateurs (dossier fal.ai, §7).
_REF_SYNTAX = {
    "seedream5":       "figure",   # « Figure 1 », « Figure 2 » — positionnel
    "seedream5_pro":   "figure",
    "seedream5_lite":  "figure",
    "seedream":        "figure",
    "flux2":           "at",       # « @image1 »
    "flux_2":          "at",
    "flux2_pro":       "at",
    "flux2_flex":      "at",
    "nb2":             "natural",  # « the attached wireframe », « the first image »
    "nano_banana":     "natural",
    "nano_banana_pro": "natural",
    "gpt_image_2":     "ordinal",  # « the first image », « the second image »
    "gpt-image-2":     "ordinal",
}

_ORDINALS = ["first", "second", "third", "fourth", "fifth",
             "sixth", "seventh", "eighth", "ninth", "tenth"]


def ref_token(engine_key: str, index: int) -> str:
    """Désignation TEXTUELLE de la n-ième image de référence (index 1-based) pour
    ce moteur. Chaîne vide si le moteur n'attend aucune mention textuelle."""
    if index < 1:
        return ""
    kind = _REF_SYNTAX.get((engine_key or "").strip().lower(), "")
    if kind == "figure":
        return f"Figure {index}"
    if kind == "at":
        return f"@image{index}"
    if kind == "ordinal":
        return f"the {_ORDINALS[index - 1]} image" if index <= len(_ORDINALS) else \
               f"image {index}"
    if kind == "natural":
        return f"the {_ORDINALS[index - 1]} attached image" if index <= len(_ORDINALS) \
               else f"attached image {index}"
    return ""


def ref_syntax_label(engine_key: str) -> str:
    """Libellé lisible de la syntaxe de référence (affichage UI)."""
    kind = _REF_SYNTAX.get((engine_key or "").strip().lower(), "")
    return {
        "figure":  "« Figure 1 », « Figure 2 » (positionnel)",
        "at":      "« @image1 », « @image2 »",
        "ordinal": "« the first image », « the second image »",
        "natural": "langage naturel (« the first attached image »)",
    }.get(kind, "aucune mention textuelle")


# ── Assemblage ─────────────────────────────────────────────────────────────────

_FIELD_ORDER = [
    ("subject",   "Subject"),
    ("action",    "Action"),
    ("setting",   "Setting"),
    ("style",     "Style"),
    ("camera",    "Composition and camera"),
    ("lighting",  "Lighting and color"),
    ("text",      "Text"),
]


def _tidy(text: str) -> str:
    """Ponctuation propre après retrait de morceaux (boosters, noms d'IP)."""
    out = re.sub(r"\s*,\s*(,\s*)+", ", ", text or "")
    out = re.sub(r"[ 	]{2,}", " ", out)
    out = re.sub(r"\s+([,.;:])", r"", out)
    out = re.sub(r"(?m)^[ 	,;:]+", "", out)
    out = re.sub(r"(?m)[ 	,;:]+$", "", out)
    return out.strip()


def build_image_prompt(intent: dict, engine_key: str) -> str:
    """Assemble le prompt image dans la grammaire du moteur.

    `intent` : dict à clés subject / action / setting / style / camera / lighting /
    text / use_case / constraints (liste). Les clés absentes sont ignorées.
    L'ACTION doit décrire UN INSTANT figé — une image n'a pas de durée."""
    intent = dict(intent or {})
    g = grammar_for(engine_key)
    # Les mots de qualité génériques sont retirés de TOUTES les grammaires : ils
    # dégradent Seedream (ils distraient sa passe de raisonnement) et la doctrine
    # de prompt de PANDORA les interdit partout (ils poussent au rendu CGI).
    for _k in ("subject", "action", "setting", "style", "camera", "lighting"):
        if intent.get(_k):
            intent[_k] = strip_quality_boosters(str(intent[_k]))[0]
    use_case = (intent.get("use_case") or "").strip()
    cons = [c for c in (intent.get("constraints") or []) if str(c).strip()]

    if g == "natural":
        # 2-4 phrases, aucun négatif : les contraintes deviennent des descriptions
        # positives, et les mots de qualité sont retirés.
        parts = [(intent.get(k) or "").strip()
                 for k in ("subject", "action", "setting", "lighting", "camera", "style")]
        body = ". ".join(p.rstrip(" .") for p in parts if p)
        pos = to_positive(cons)
        if pos:
            body = f"{body}, {', '.join(pos)}" if body else ", ".join(pos)
        if use_case:
            body = f"{body}. {use_case}" if body else use_case
        body = _tidy(body)
        return (body + ".") if body and not body.endswith(".") else body

    if g == "json":
        import json as _json
        payload = {k: v for k, v in {
            "scene":    (intent.get("setting") or "").strip(),
            "subject":  (intent.get("subject") or "").strip(),
            "action":   (intent.get("action") or "").strip(),
            "style":    (intent.get("style") or "").strip(),
            "lighting": (intent.get("lighting") or "").strip(),
            "camera":   (intent.get("camera") or "").strip(),
            "mood":     use_case,
        }.items() if v}
        pal = intent.get("color_palette") or []
        if pal:
            # Les HEX ne sont lus que précédés de « hex » ou « color ».
            payload["color_palette"] = [f"hex {c}" if not str(c).lower().startswith("hex")
                                        else str(c) for c in pal]
        return _json.dumps(payload, ensure_ascii=False, indent=2)

    # fields (et repli plain) : brief à champs, contraintes en bloc final explicite.
    lines = []
    if use_case:
        lines.append(use_case)
        lines.append("")
    for key, label in _FIELD_ORDER:
        v = (intent.get(key) or "").strip()
        if v:
            lines.append(f"{label}: {v}")
    if cons:
        if supports_negatives(engine_key) or g == "plain":
            lines.append("Constraints: " + ", ".join(cons))
        else:
            pos = to_positive(cons)
            if pos:
                lines.append("Constraints: " + ", ".join(pos))
    return "\n".join(lines).strip()
