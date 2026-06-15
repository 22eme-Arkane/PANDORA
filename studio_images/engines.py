"""
Catalogue des moteurs de génération d'image fal.ai + construction des arguments.

Chaque moteur a sa propre forme de paramètres (aspect_ratio enum, image_size objet,
resolution, paramètre de référence…). build_request() centralise la traduction
d'une demande générique (prompt, taille cible, résolution, références) vers les
arguments exacts attendus par l'endpoint choisi.

Schémas vérifiés sur fal.ai (juin 2026) :
- nano-banana-2 / pro : aspect_ratio enum, resolution (512x512|1K|2K|4K),
  num_images 1-4, output_format, refs via image_urls (endpoint /edit, jusqu'à 14)
- ideogram/v3         : image_size (enum ou {width,height}), rendering_speed,
  style (AUTO|GENERAL|REALISTIC|DESIGN), image_urls (refs de style)
- flux-pro/v1.1-ultra : aspect_ratio enum, output_format, image_url (1 réf)
- recraft/v4.1/*      : image_size ({width,height} jusqu'à 14142), colors
"""

# Ratios supportés par les moteurs basés sur aspect_ratio
NANO_ASPECTS = ["21:9", "16:9", "3:2", "4:3", "5:4", "1:1", "4:5", "3:4", "2:3", "9:16"]
FLUX_ASPECTS = ["21:9", "16:9", "4:3", "3:2", "1:1", "2:3", "3:4", "9:16", "9:21"]

# Catalogue — l'ordre définit l'affichage dans le sélecteur.
# "refs" : support des images de référence, vérifié sur la doc fal.ai (juin 2026)
#   - max  : nombre d'images réellement exploitées
#   - hint : message affiché sous la zone Références dans l'UI
ENGINES = {
    "nb2": {
        "label":    "Nano Banana 2  ·  polyvalent · refs · texte  ·  ~$0.08",
        "endpoint": "fal-ai/nano-banana-2",
        "edit":     "fal-ai/nano-banana-2/edit",
        "kind":     "nano",
        "output":   "raster",
        "refs":     {"max": 14, "hint": "✅ jusqu'à 14 références (sujet + style)"},
    },
    "nb_pro": {
        "label":    "Nano Banana Pro  ·  Gemini 3 · texte net · 14 refs  ·  ~$0.15",
        "endpoint": "fal-ai/nano-banana-pro",
        "edit":     "fal-ai/nano-banana-pro/edit",
        "kind":     "nano",
        "output":   "raster",
        "refs":     {"max": 14, "hint": "✅ jusqu'à 14 références (sujet + style)"},
    },
    "ideogram": {
        "label":    "Ideogram V3  ·  champion du TEXTE & logos  ·  ~$0.06",
        "endpoint": "fal-ai/ideogram/v3",
        "kind":     "ideogram",
        "output":   "raster",
        "refs":     {"max": 3, "hint": "⚠️ références de STYLE uniquement (pas le sujet)"},
    },
    "flux_ultra": {
        "label":    "FLUX1.1 Pro Ultra  ·  photoréaliste 2K  ·  ~$0.06",
        "endpoint": "fal-ai/flux-pro/v1.1-ultra",
        "kind":     "flux",
        "output":   "raster",
        "refs":     {"max": 1, "hint": "⚠️ 1 seule référence (image prompt / variation)"},
    },
    "recraft": {
        "label":    "Recraft V4.1  ·  branding / éditorial  ·  ~$0.04",
        "endpoint": "fal-ai/recraft/v4.1/text-to-image",
        "kind":     "recraft",
        "output":   "raster",
        "refs":     {"max": 0, "hint": "❌ ce moteur ignore les images de référence"},
    },
    "recraft_vector": {
        "label":    "Recraft V4.1 Vector  ·  LOGO SVG éditable  ·  ~$0.08",
        "endpoint": "fal-ai/recraft/v4.1/text-to-vector",
        "kind":     "recraft",
        "output":   "svg",
        "refs":     {"max": 0, "hint": "❌ ce moteur ignore les images de référence"},
    },
}


def label_for(key: str) -> str:
    return ENGINES.get(key, ENGINES["nb2"])["label"]


def ref_support(key: str) -> dict:
    """Retourne {max, hint} décrivant le support des références pour ce moteur."""
    return ENGINES.get(key, ENGINES["nb2"]).get("refs", {"max": 0, "hint": ""})


def _nearest_aspect(target: tuple, allowed: list) -> str:
    """Choisit le ratio autorisé le plus proche de la taille cible."""
    w, h = target
    r = w / h if h else 1.0

    def val(a):
        pw, ph = a.split(":")
        return int(pw) / int(ph)

    return min(allowed, key=lambda a: abs(val(a) - r))


def _size_obj(target: tuple) -> dict:
    w, h = target
    return {"width": int(w), "height": int(h)}


def build_request(engine_key: str, prompt: str, target: tuple,
                  resolution: str, ref_urls: list):
    """Retourne (endpoint, args, output_kind) pour le moteur demandé.

    output_kind : "raster" (png) ou "svg".
    target      : (largeur, hauteur) en pixels de la sortie souhaitée.
    ref_urls    : liste de data-URL base64 (peut être vide).
    """
    e = ENGINES.get(engine_key, ENGINES["nb2"])
    kind = e["kind"]
    refs = [u for u in (ref_urls or []) if u]

    if kind == "nano":
        args = {
            "prompt":        prompt,
            "num_images":    1,
            "aspect_ratio":  _nearest_aspect(target, NANO_ASPECTS),
            "resolution":    resolution,
            "output_format": "png",
        }
        if refs:
            return e["edit"], {**args, "image_urls": refs[:14]}, "raster"
        return e["endpoint"], args, "raster"

    if kind == "flux":
        args = {
            "prompt":        prompt,
            "num_images":    1,
            "aspect_ratio":  _nearest_aspect(target, FLUX_ASPECTS),
            "output_format": "png",
        }
        if refs:
            # image_prompt_strength par défaut = 0.1 (quasi nul) → on le remonte
            # pour que la référence influence réellement le rendu.
            args["image_url"] = refs[0]
            args["image_prompt_strength"] = 0.6
        return e["endpoint"], args, "raster"

    if kind == "ideogram":
        args = {
            "prompt":          prompt,
            "num_images":      1,
            "image_size":      _size_obj(target),
            "rendering_speed": "QUALITY",
        }
        if refs:
            args["image_urls"] = refs[:10]
        return e["endpoint"], args, "raster"

    # recraft (raster ou vector)
    args = {"prompt": prompt, "image_size": _size_obj(target)}
    return e["endpoint"], args, e["output"]
