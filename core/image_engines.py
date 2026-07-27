"""Catalogue CANONIQUE des moteurs de génération d'image de PANDORA.

But : une SEULE liste de moteurs partagée par TOUS les points de génération
d'image de l'app principale — les Moods (Storyboard Cinéma + Conducteur Live) et
les 5 dialogs d'éléments (Décor, Casting, Accessoire, HMC, Véhicule). Avant, chaque
endroit avait son propre sous-ensemble :
  - Moods        : « nb2 » / « flux » en dur ;
  - Éléments     : les 6 modèles de core/config.py (IMAGE_MODEL_*) ;
  - Studio IA    : les 13 moteurs de studio_images/engines.py (le vrai catalogue).

Ici on prend le catalogue Studio IA comme SOURCE (il est le plus complet et sait
déjà façonner les arguments par moteur via build_request), on écarte la sortie
vecteur SVG (Recraft Vector — réservée au Studio IA), et on RÉINTÈGRE les deux
moteurs qui n'existaient QUE côté éléments (GPT Image 2, FLUX.2 pro) pour ne rien
perdre. Résultat : l'UNION de tous les moteurs image de PANDORA, en raster.

Couplage : studio_images/ utilise des imports « à plat » (import engines) et doit
rester AUTONOME (il tourne sans core via studio_images/main.py). Le sens de la
dépendance est donc UNIQUEMENT core → studio_images, centralisé dans ce fichier
(même astuce sys.path que ui/tab_image.py, compatible frozen où studio_images est
embarqué à plat). Jamais l'inverse.
"""

import os
from collections import OrderedDict

# ── Accès au catalogue Studio IA (source unique, pas de duplication) ──────────

_STUDIO_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                           "studio_images")


def _load_studio_engines():
    """Charge studio_images/engines.py SANS toucher à sys.path.

    ⚠ On NE fait PAS `sys.path.insert(studio_images)` : ce dossier contient un
    `main.py` qui masquerait le `main.py` du projet (collision de nom → crash de
    l'excepthook, harnais rouge). engines.py est autonome (aucun import de module
    voisin) → on le charge directement depuis son chemin via importlib, dans un
    module privé isolé. En mode gelé (PyInstaller, source absente du disque),
    repli sur l'import à plat « engines » que le build déclare déjà."""
    path = os.path.join(_STUDIO_DIR, "engines.py")
    if os.path.isfile(path):
        try:
            import importlib.util
            spec = importlib.util.spec_from_file_location("_pandora_studio_engines", path)
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            return mod
        except Exception:
            pass
    try:
        import engines as _se  # frozen : studio_images embarqué à plat
        return _se
    except Exception:
        return None


_SE = _load_studio_engines()


# ── Moteurs présents UNIQUEMENT côté éléments (à réintégrer pour ne rien perdre) ─
# Repris de core/config.py (endpoints/labels/prix) — GPT Image 2 et FLUX.2 pro ne
# sont PAS dans le catalogue Studio IA. Sans eux, unifier sur le seul catalogue
# Studio IA ferait DISPARAÎTRE ces deux moteurs des dialogs d'éléments (régression).
_EXTRA_ENGINES = OrderedDict([
    ("gpt2", {
        "label":    "GPT Image 2  ·  OpenAI · suivi de prompt + texte  ·  ~$0.04",
        "endpoint": "openai/gpt-image-2",
        "kind":     "gpt2",
        "family":   "GPT Image",
        "slug":     "gpt-image-2",
        "output":   "raster",
        "refs":     {"max": 0, "hint": "❌ ce moteur ignore les images de référence"},
    }),
    ("flux2", {
        "label":    "FLUX.2 [pro]  ·  photoréalisme  ·  ~$0.03",
        "endpoint": "fal-ai/flux-2-pro",
        "kind":     "flux2",
        "family":   "FLUX",
        "slug":     "flux-2-pro",
        "output":   "raster",
        "refs":     {"max": 0, "hint": "❌ ce moteur ignore les images de référence"},
    }),
])

# Repli minimal si studio_images/engines.py est introuvable (jamais en pratique —
# il est bundlé). On garde au moins les Nano Banana pour que l'app fonctionne.
_FALLBACK = OrderedDict([
    ("nb2", {
        "label":    "Nano Banana 2  ·  polyvalent · refs · texte  ·  ~$0.08",
        "endpoint": "fal-ai/nano-banana-2",
        "edit":     "fal-ai/nano-banana-2/edit",
        "kind":     "nano",
        "family":   "Nano Banana",
        "slug":     "nano-banana-2",
        "output":   "raster",
        "refs":     {"max": 14, "hint": "✅ jusqu'à 14 références (sujet + style)"},
    }),
])


def _build_catalogue() -> "OrderedDict":
    """Catalogue fusionné, RASTER uniquement, dans l'ordre : Studio IA puis extras."""
    merged = OrderedDict()
    if _SE is not None:
        for k, v in _SE.ENGINES.items():
            if v.get("output") == "svg":
                continue  # vecteur SVG (Recraft Vector) réservé au Studio IA
            merged[k] = dict(v)
    else:
        merged.update(_FALLBACK)
    for k, v in _EXTRA_ENGINES.items():
        merged.setdefault(k, dict(v))
    return merged


ENGINES = _build_catalogue()

DEFAULT_ENGINE = "nb2"


# ── Introspection ─────────────────────────────────────────────────────────────

def label_for(key: str) -> str:
    return ENGINES.get(key, ENGINES.get(DEFAULT_ENGINE, {})).get("label", key)


def short_label(key: str) -> str:
    """« Nano Banana 2  ·  polyvalent · … · ~$0.08 » → « Nano Banana 2 »."""
    return label_for(key).split("·")[0].strip() or key


def slug_for(key: str) -> str:
    return ENGINES.get(key, {}).get("slug", "moteur")


def family_of(key: str) -> str:
    return ENGINES.get(key, {}).get("family", key)


def ref_support(key: str) -> dict:
    return ENGINES.get(key, {}).get("refs", {"max": 0, "hint": ""})


def raster_engines() -> list:
    """Clés de TOUS les moteurs raster (ordre du catalogue) — la liste à proposer
    dans les sélecteurs des Moods et des dialogs d'éléments."""
    return list(ENGINES.keys())


def engine_choices() -> list:
    """[(key, label)] pour peupler un QComboBox — ordre du catalogue."""
    return [(k, ENGINES[k]["label"]) for k in ENGINES]


def edit_capable_engines() -> list:
    """Moteurs qui savent ÉDITER une image de référence (endpoint /edit) — c.-à-d.
    ceux qui peuvent générer SUR une façade en préservant sa géométrie (mapping Live).
    = familles Nano Banana + Seedream 5 (Pro/Lite). Sert à filtrer le sélecteur de
    Mood quand on est en séquence mapping (choix Matthieu 2026-07-20)."""
    return [k for k, v in ENGINES.items() if v.get("edit")]


def reference_engine_choices() -> list:
    """[(key, label)] limité aux moteurs réellement compatibles avec le raccord
    multi-images du workflow « 7 vues ».

    Le plan d'architecture reprend le plan d'ensemble, puis chaque face reprend
    le plan d'ensemble ET le plan vu de dessus. Un simple moteur text-to-image ne
    convient donc pas : il faut impérativement un endpoint d'édition acceptant des
    images de référence. Les labels restent ceux du catalogue canonique afin que
    le prix indicatif et le nombre de références soient visibles dans le dialogue.
    """
    return [(k, ENGINES[k]["label"]) for k in edit_capable_engines()]


def is_edit_capable(key: str) -> bool:
    return bool(ENGINES.get(key, {}).get("edit"))


def is_nano(key: str) -> bool:
    return ENGINES.get(key, {}).get("kind") in ("nano", "nano_lite")


def nano_endpoints(key: str) -> tuple:
    """(endpoint_texte, endpoint_edit) d'un moteur de la famille Nano Banana."""
    e = ENGINES.get(key, {})
    return e.get("endpoint", "fal-ai/nano-banana-2"), e.get("edit", "fal-ai/nano-banana-2/edit")


def price_hint(key: str) -> str:
    """Extrait la mention de prix « ~$0.08 » du label, ou "" si absente."""
    lbl = label_for(key)
    if "$" in lbl:
        return lbl[lbl.rindex("·") + 1:].strip() if "·" in lbl else ""
    return ""


# ── Construction des arguments d'appel (délègue à studio_images.build_request) ──

def ar_to_target(aspect_ratio: str, resolution: str = "") -> tuple:
    """Ratio « 16:9 » → taille cible (w, h), au ratio EXACT.

    Calculé par `core.image_resolution` depuis le 2026-07-27, là où une table
    figée héritée des buckets SDXL donnait des ratios FAUX : « 16:9 » valait
    (1344, 768), soit 1,750 au lieu de 1,7778. Toute image générée était donc
    légèrement étirée — et un Mood étiré, servant d'image de départ à une
    génération vidéo, déforme la façade du bâtiment qu'on projette.

    `resolution` vide = palier par défaut (1920 × 1080 en 16:9).
    """
    from core.image_resolution import DEFAULT_KEY, target_for
    return target_for(aspect_ratio, resolution or DEFAULT_KEY)


def _target_to_size_enum(target: tuple) -> str:
    """(w, h) → enum image_size fal.ai (GPT Image 2 / FLUX.2 pro)."""
    w, h = target
    r = (w / h) if h else 1.0
    if abs(r - 1.0) < 0.12:
        return "square_hd"
    return "landscape_16_9" if r > 1.0 else "portrait_16_9"


def build_request(engine_key: str, prompt: str, target: tuple,
                  resolution: str, ref_urls: list):
    """(endpoint, args, output_kind) pour n'importe quel moteur du catalogue.

    Délègue à studio_images.engines.build_request pour les moteurs du catalogue
    Studio IA, et gère localement les deux extras (GPT Image 2, FLUX.2 pro) dont
    les schémas viennent de l'ancien câblage des éléments (nano_banana._build_image_args).
    ref_urls : data-URL/URLs de référence (peut être vide ; ignorées si non supportées).
    """
    refs = [u for u in (ref_urls or []) if u]

    if engine_key in _EXTRA_ENGINES:
        size_enum = _target_to_size_enum(target)
        if engine_key == "gpt2":
            return "openai/gpt-image-2", {
                "prompt": prompt, "image_size": size_enum,
                "num_images": 1, "quality": "high", "output_format": "png",
            }, "raster"
        # flux2
        return "fal-ai/flux-2-pro", {
            "prompt": prompt, "image_size": size_enum,
            "output_format": "png", "safety_tolerance": "5",
        }, "raster"

    if _SE is not None and engine_key in _SE.ENGINES:
        return _SE.build_request(engine_key, prompt, target, resolution, refs)

    # Moteur inconnu → repli Nano Banana 2 texte.
    return "fal-ai/nano-banana-2", {
        "prompt": prompt, "num_images": 1, "aspect_ratio": "16:9",
        "resolution": resolution, "output_format": "png",
    }, "raster"
