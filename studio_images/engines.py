"""
Catalogue des moteurs de génération d'image fal.ai + construction des arguments.

Chaque moteur a sa propre forme de paramètres (aspect_ratio enum, image_size objet,
resolution, paramètre de référence…). build_request() centralise la traduction
d'une demande générique (prompt, taille cible, résolution, références) vers les
arguments exacts attendus par l'endpoint choisi.

Schémas vérifiés sur fal.ai (juin 2026, relus le 2026-09-24) :
- nano-banana-2 / pro : aspect_ratio enum, resolution (512x512|1K|2K|4K),
  num_images 1-4, output_format, refs via image_urls (endpoint /edit, jusqu'à 14)
- ideogram/v3         : image_size (enum ou {width,height}), rendering_speed,
  style (AUTO|GENERAL|REALISTIC|DESIGN), image_urls (refs de style)
- flux-pro/v1.1-ultra : aspect_ratio enum, output_format, image_url (1 réf)
- recraft/v4.1/*      : image_size ({width,height} jusqu'à 14142), colors — 0,035 $
- seedream v5 flash   : image_size 1024²–2048², num_images 1-6, /edit ≤ 10 image_urls — 0,027 $
- qwen-image-2[/pro]  : image_size 512²–2048², num_images 1-4, negative_prompt,
  /edit 1-3 image_urls — 0,035 $ (Pro 0,075 $)
- kling-image/o3      : aspect_ratio enum, resolution 1K|2K|4K, num_images 1-9,
  /image-to-image ≤ 10 image_urls citées « @Image1 » — 0,028 $ (4K ×2)
"""

# Ratios supportés par les moteurs basés sur aspect_ratio
NANO_ASPECTS = ["21:9", "16:9", "3:2", "4:3", "5:4", "1:1", "4:5", "3:4", "2:3", "9:16"]
FLUX_ASPECTS = ["21:9", "16:9", "4:3", "3:2", "1:1", "2:3", "3:4", "9:16", "9:21"]

# Catalogue — l'ordre définit l'affichage dans le sélecteur.
# "refs"   : support des images de référence, vérifié sur la doc fal.ai (juin 2026)
#   - max  : nombre d'images réellement exploitées
#   - hint : message affiché sous la zone Références dans l'UI
# "family" : MARQUE du moteur. Sert au balayage « tous les moteurs », qui ne
#   retient QU'UN moteur par famille — une image par marque, pas une par version.
#   (À ne pas confondre avec "kind", qui décrit la FORME des arguments API :
#   Seedream 4.5, Z-Image et Qwen partagent kind="imgsize" sans être parents.)
# "slug"   : nom court sûr pour un nom de fichier. Il est ajouté À LA FIN du nom
#   de chaque image générée, pour savoir quel moteur l'a produite.
ENGINES = {
    "nb2": {
        "label":    "Nano Banana 2  ·  polyvalent · refs · texte  ·  ~$0.08",
        "endpoint": "fal-ai/nano-banana-2",
        "edit":     "fal-ai/nano-banana-2/edit",
        "kind":     "nano",
        "family":   "Nano Banana",
        "slug":     "nano-banana-2",
        "output":   "raster",
        "refs":     {"max": 14, "hint": "✅ jusqu'à 14 références (sujet + style)"},
    },
    "nb_pro": {
        "label":    "Nano Banana Pro  ·  Gemini 3 · texte net · 14 refs  ·  ~$0.15",
        "endpoint": "fal-ai/nano-banana-pro",
        "edit":     "fal-ai/nano-banana-pro/edit",
        "kind":     "nano",
        "family":   "Nano Banana",
        "slug":     "nano-banana-pro",
        "output":   "raster",
        "refs":     {"max": 14, "hint": "✅ jusqu'à 14 références (sujet + style)"},
    },
    "nb2_lite": {
        "label":    "Nano Banana 2 Lite  ·  Google · rapide <2 s · 1024²  ·  ~$0.02",
        "endpoint": "google/nano-banana-2-lite",
        "edit":     "google/nano-banana-lite/edit",
        "kind":     "nano_lite",
        "family":   "Nano Banana",
        "slug":     "nano-banana-2-lite",
        "output":   "raster",
        "refs":     {"max": 6, "hint": "✅ références via édition (sujet + style)"},
    },
    "seedream5_pro": {
        # ⚠ PRÉFIXE : Pro est exposé SANS « fal-ai/ » (vérifié le 2026-07-20 sur les
        # pages modèle fal.ai), contrairement à la version Lite juste en dessous qui
        # l'exige. Les deux conventions coexistent chez ByteDance — ne pas uniformiser.
        "label":    "Seedream 5.0 Pro  ·  ByteDance · édition ciblée · 10 refs  ·  ~$0.0675–0.135",
        "endpoint": "bytedance/seedream/v5/pro/text-to-image",
        "edit":     "bytedance/seedream/v5/pro/edit",
        "kind":     "seedream",
        "family":   "Seedream Pro",   # famille DISTINCTE de « Seedream » (choix Matthieu
                                      # 2026-07-20) → Pro ET Lite au balayage comparatif
        "slug":     "seedream-5-pro",
        "output":   "raster",
        "refs":     {"max": 10, "hint": "✅ jusqu'à 10 références (édition ciblée par région)"},
    },
    "seedream5": {
        "label":    "Seedream 5.0 Lite  ·  ByteDance · gén.+édition · 10 refs  ·  ~$0.035",
        "endpoint": "fal-ai/bytedance/seedream/v5/lite/text-to-image",
        "edit":     "fal-ai/bytedance/seedream/v5/lite/edit",
        "kind":     "seedream",
        "family":   "Seedream",
        "slug":     "seedream-5-lite",
        "output":   "raster",
        "refs":     {"max": 10, "hint": "✅ jusqu'à 10 références (édition multi-images)"},
    },
    "seedream45": {
        "label":    "Seedream 4.5  ·  ByteDance · text-to-image  ·  ~$0.03",
        "endpoint": "fal-ai/bytedance/seedream/v4.5/text-to-image",
        "kind":     "imgsize",
        "family":   "Seedream",
        "slug":     "seedream-4-5",
        "output":   "raster",
        "refs":     {"max": 0, "hint": "❌ ce moteur ignore les images de référence"},
    },
    "zimage": {
        "label":    "Z-Image Turbo  ·  Tongyi · photoréaliste rapide  ·  ~$0.005/MP",
        "endpoint": "fal-ai/z-image/turbo",
        "kind":     "imgsize",
        "family":   "Z-Image",
        "slug":     "z-image-turbo",
        "output":   "raster",
        "refs":     {"max": 0, "hint": "❌ ce moteur ignore les images de référence"},
    },
    "qwen_image": {
        "label":    "Qwen-Image  ·  rendu de texte complexe  ·  ~$0.02/MP",
        "endpoint": "fal-ai/qwen-image",
        "kind":     "imgsize",
        "family":   "Qwen",
        "slug":     "qwen-image",
        "output":   "raster",
        "refs":     {"max": 0, "hint": "❌ ce moteur ignore les images de référence"},
    },
    # ── Ajoutés le 2026-09-24 (fiches fal relues) ─────────────────────────────
    "qwen_image2": {
        # image_size 512²–2048², num_images 1-4, negative_prompt ; /edit = 1 à 3 refs.
        "label":    "Qwen-Image 2  ·  texte & édition · 3 refs  ·  ~$0.035",
        "endpoint": "fal-ai/qwen-image-2/text-to-image",
        "edit":     "fal-ai/qwen-image-2/edit",
        "kind":     "imgsize",
        "family":   "Qwen",
        "slug":     "qwen-image-2",
        "output":   "raster",
        "refs":     {"max": 3, "hint": "✅ jusqu'à 3 références (édition)"},
    },
    "qwen_image2_pro": {
        "label":    "Qwen-Image 2 Pro  ·  texte & détail  ·  ~$0.075",
        "endpoint": "fal-ai/qwen-image-2/pro/text-to-image",
        "kind":     "imgsize",
        "family":   "Qwen Pro",
        "slug":     "qwen-image-2-pro",
        "output":   "raster",
        "refs":     {"max": 0, "hint": "❌ ce moteur ignore les images de référence"},
    },
    "seedream5_flash": {
        # ⚠ Préfixe SANS « fal-ai/ », comme le Pro. image_size 1024²–2048²
        # (défaut auto_2K), num_images 1-6, /edit ≤ 10 refs (les 10 DERNIÈRES).
        "label":    "Seedream 5.0 Flash  ·  ByteDance · rapide · 10 refs  ·  ~$0.027",
        "endpoint": "bytedance/seedream/v5/flash/text-to-image",
        "edit":     "bytedance/seedream/v5/flash/edit",
        "kind":     "seedream",
        "family":   "Seedream Flash",
        "slug":     "seedream-5-flash",
        "output":   "raster",
        "refs":     {"max": 10, "hint": "✅ jusqu'à 10 références (édition)"},
    },
    "kling_image": {
        # aspect_ratio + resolution 1K/2K/4K (4K = prix double) ; /image-to-image
        # ≤ 10 refs citées « @Image1 » ; sortie `images`.
        "label":    "Kling Image O3  ·  Kuaishou · 10 refs @Image1  ·  ~$0.028",
        "endpoint": "fal-ai/kling-image/o3/text-to-image",
        "edit":     "fal-ai/kling-image/o3/image-to-image",
        "kind":     "kling_img",
        "family":   "Kling",
        "slug":     "kling-image-o3",
        "output":   "raster",
        "refs":     {"max": 10, "hint": "✅ jusqu'à 10 références (@Image1, @Image2…)"},
    },
    "ideogram": {
        "label":    "Ideogram V3  ·  champion du TEXTE & logos  ·  ~$0.06",
        "endpoint": "fal-ai/ideogram/v3",
        "kind":     "ideogram",
        "family":   "Ideogram",
        "slug":     "ideogram-v3",
        "output":   "raster",
        "refs":     {"max": 3, "hint": "⚠️ références de STYLE uniquement (pas le sujet)"},
    },
    "ideogram4": {
        "label":    "Ideogram V4  ·  texte net · affiches & logos  ·  ~$0.0075–0.025/MP",
        "endpoint": "ideogram/v4",
        "kind":     "ideogram",
        "family":   "Ideogram",
        "slug":     "ideogram-v4",
        "output":   "raster",
        "refs":     {"max": 3, "hint": "⚠️ références de STYLE uniquement (pas le sujet)"},
    },
    "flux_ultra": {
        "label":    "FLUX1.1 Pro Ultra  ·  photoréaliste 2K  ·  ~$0.06",
        "endpoint": "fal-ai/flux-pro/v1.1-ultra",
        "kind":     "flux",
        "family":   "FLUX",
        "slug":     "flux-1-1-pro-ultra",
        "output":   "raster",
        "refs":     {"max": 1, "hint": "⚠️ 1 seule référence (image prompt / variation)"},
    },
    "recraft": {
        # 0,035 $ l'image (fiche fal relue le 2026-09-24 ; c'était noté 0,04).
        "label":    "Recraft V4.1  ·  branding / éditorial  ·  ~$0.035",
        "endpoint": "fal-ai/recraft/v4.1/text-to-image",
        "kind":     "recraft",
        "family":   "Recraft",
        "slug":     "recraft-v4-1",
        "output":   "raster",
        "refs":     {"max": 0, "hint": "❌ ce moteur ignore les images de référence"},
    },
    "recraft_vector": {
        "label":    "Recraft V4.1 Vector  ·  LOGO SVG éditable  ·  ~$0.08",
        "endpoint": "fal-ai/recraft/v4.1/text-to-vector",
        "kind":     "recraft",
        "family":   "Recraft",
        "slug":     "recraft-v4-1-vector",
        "output":   "svg",
        "refs":     {"max": 0, "hint": "❌ ce moteur ignore les images de référence"},
    },
}

# ── Ordre du menu (demande Matthieu 2026-07-23) ──────────────────────────────
# Seedream 5 Pro EN TÊTE (moteur par défaut — celui qui marche le mieux), puis
# Recraft, puis Nano Banana 2 ; le reste garde l'ordre historique.
_TOP_ENGINES = ["seedream5_pro", "recraft", "nb2"]
ENGINES = {k: ENGINES[k] for k in
           (_TOP_ENGINES + [k for k in ENGINES if k not in _TOP_ENGINES])}


# ── Moteurs ComfyUI (24/09/2026) — les gabarits d'images officiels, en local ─
# Le cache est écrit par core/comfy_catalog quand ComfyUI répond (index lu
# chez le serveur) ; ce module reste AUTONOME (pas d'import de core) et se
# contente de le lire. Chaque gabarit devient un moteur kind="comfy", endpoint
# « comfy:<nom> », 0 $ — routé vers ComfyUI par core/image_call.
def _comfy_cache_path() -> str:
    import os
    base = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~")
    return os.path.join(base, "PANDORA", "externals", "comfy_image_catalog.json")


def _comfy_engine(entry: dict) -> dict:
    name = str(entry.get("name") or "")
    edit = bool(entry.get("edit"))
    loads = int(entry.get("loads") or (1 if edit else 0))
    size = int(entry.get("size") or 0)
    poids = f"{size / 1e9:.0f} Go" if size >= 1e9 else (f"{size / 1e6:.0f} Mo" if size else "?")
    return {
        # « $0 » en queue : la mention de prix se LIT dans le libellé (price_hint).
        "label":    f"ComfyUI · {entry.get('title') or name}  ·  "
                    f"{'édition · réfs' if edit else 'texte → image'} · {poids} sur votre GPU  ·  $0",
        "endpoint": "comfy:" + name,
        "kind":     "comfy",
        "family":   "ComfyUI",
        # Le nom du gabarit est unique par construction : le slug le garde en
        # entier (abrégé, deux gabarits se confondaient — test « slugs uniques »).
        "slug":     "comfy-" + name.lower().replace("_", "-"),
        "output":   "raster",
        "refs":     ({"max": loads, "hint": f"✅ {loads} image(s) de référence = entrées du gabarit"} if loads
                     else {"max": 0, "hint": "❌ gabarit texte → image : les références sont ignorées"}),
        "comfy":    {"name": name, "edit": edit, "size": size},
    }


def load_comfy_engines() -> dict:
    """{clé: moteur} depuis le cache — vide si ComfyUI n'a jamais répondu."""
    import json
    try:
        with open(_comfy_cache_path(), encoding="utf-8") as f:
            entries = json.load(f).get("templates") or []
    except Exception:
        return {}
    out = {}
    for e in entries:
        if e.get("name"):
            out["comfy:" + e["name"]] = _comfy_engine(e)
    return out


ENGINES.update(load_comfy_engines())


def refresh_comfy_engines() -> int:
    """Relit le cache (après un rafraîchissement par core/comfy_catalog) et met
    le catalogue à jour en place — les sélecteurs repeuplés ensuite le voient."""
    fresh = load_comfy_engines()
    for k in [k for k in ENGINES if k.startswith("comfy:") and k not in fresh]:
        del ENGINES[k]
    ENGINES.update(fresh)
    return len(fresh)

# Moteur par défaut d'une nouvelle installation (la préférence sauvegardée de
# l'utilisateur prime toujours).
DEFAULT_ENGINE = "seedream5_pro"


def label_for(key: str) -> str:
    return ENGINES.get(key, ENGINES["nb2"])["label"]


def short_label(key: str) -> str:
    """Nom lisible du moteur, sans les mentions techniques ni le prix.
    « Nano Banana 2  ·  polyvalent · … · ~$0.08 » → « Nano Banana 2 »."""
    return label_for(key).split("·")[0].strip()


def slug_for(key: str) -> str:
    """Nom court sûr pour un nom de fichier (suffixe des images générées)."""
    return ENGINES.get(key, ENGINES["nb2"]).get("slug", "moteur")


def family_of(key: str) -> str:
    e = ENGINES.get(key, ENGINES["nb2"])
    return e.get("family", key)


def sweep_engines() -> list:
    """Moteurs du balayage « générer avec tous les moteurs » : UN par famille.

    On retient le PREMIER moteur de chaque famille dans l'ordre du catalogue →
    une image par marque (Nano Banana, Seedream, Z-Image, Qwen, Ideogram, FLUX,
    Recraft) et non une par version, comme demandé. Réordonner ENGINES change
    donc le représentant retenu.

    Effet de bord voulu : Recraft V4.1 Vector (sortie SVG) est écarté, la famille
    Recraft étant déjà représentée par sa version raster — le balayage ne produit
    que des images comparables entre elles."""
    seen, out = set(), []
    for key in ENGINES:
        fam = family_of(key)
        if fam not in seen:
            seen.add(fam)
            out.append(key)
    return out


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

    if kind == "comfy":
        # ComfyUI (core/comfy_image) : prompt, cadre exact, références telles
        # quelles (data-URL / chemin / http) ; le gabarit fait le reste.
        w, h = target
        _max = int(e.get("refs", {}).get("max") or 0)
        return e["endpoint"], {
            "prompt": prompt, "width": int(w), "height": int(h),
            "ref_urls": refs[:_max] if _max else [],
        }, "raster"

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

    if kind == "nano_lite":
        # Nano Banana 2 Lite : 1024² fixe, 14 ratios, <2 s. Schéma minimal
        # (pas de 'resolution' — anti-400) ; refs via endpoint /edit.
        args = {
            "prompt":        prompt,
            "num_images":    1,
            "aspect_ratio":  _nearest_aspect(target, NANO_ASPECTS),
            "output_format": "png",
        }
        if refs and e.get("edit"):
            return e["edit"], {**args, "image_urls": refs[:6]}, "raster"
        return e["endpoint"], args, "raster"

    if kind in ("seedream", "imgsize"):
        # Modèles DiT (Seedream 5/4.5, Z-Image Turbo, Qwen-Image) : image_size en
        # objet {width,height} + num_images. Seedream 5.0 Lite/Pro/Flash et
        # Qwen-Image 2 ont un endpoint /edit qui accepte des images de référence
        # (plafond = refs.max du moteur). Schémas best-effort fal.ai.
        args = {
            "prompt":     prompt,
            "num_images": 1,
            "image_size": _size_obj(target),
        }
        if refs and e.get("edit"):
            _max = int(e.get("refs", {}).get("max") or 10)
            return e["edit"], {**args, "image_urls": refs[:_max]}, "raster"
        return e["endpoint"], args, "raster"

    if kind == "kling_img":
        # Kling Image O3 (fal 2026-09-24) : ratio enum + resolution 1K/2K/4K
        # (le 4K coûte le double : réservé aux cibles > 2560 px). Avec des
        # références → image-to-image, jusqu'à 10 images citées « @Image1 ».
        w, h = target
        res = "4K" if max(w, h) > 2560 else ("2K" if max(w, h) > 1024 else "1K")
        args = {
            "prompt":        prompt,
            "num_images":    1,
            "aspect_ratio":  _nearest_aspect(target, ["21:9", "16:9", "3:2", "4:3", "1:1", "3:4", "2:3", "9:16"]),
            "resolution":    res,
            "output_format": "png",
        }
        if refs and e.get("edit"):
            return e["edit"], {**args, "image_urls": refs[:10]}, "raster"
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
