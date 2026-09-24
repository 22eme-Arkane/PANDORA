"""core/comfy_catalog.py — Les moteurs d'IMAGES que ComfyUI apporte à PANDORA.

Le paquet de gabarits officiels livré avec ComfyUI (Comfy-Org/workflow_templates)
compte plus de 270 workflows d'image ouverts — Z-Image, Flux.2 (Klein, Dev),
Flux.1, Qwen-Image (+ Edit), Krea-2, SDXL, SD3.5, HiDream, Chroma, Lumina,
OmniGen2, FireRed… Décision Matthieu (24/09/2026) : TOUS, y compris les plus
lourds, pour les essayer sur d'autres machines — pas seulement ceux qui
tiennent sur 8 Go.

Une liste écrite à la main serait fausse à la prochaine version de ComfyUI :
le catalogue est LU chez le serveur (`GET /templates/index.json`, servi par
ComfyUI lui-même), filtré (images, sources ouvertes, pas les nœuds API
payants), puis mis en CACHE dans le dossier des modules de PANDORA pour être
disponible serveur éteint. studio_images/engines.py lit ce cache à
l'importation et expose chaque gabarit comme un moteur `kind="comfy"` —
d'où il rejoint automatiquement le catalogue canonique (core/image_engines)
et tous les sélecteurs d'images de l'application. Le poids annoncé par
l'index (modèles à télécharger) figure dans le libellé.

Module PUR sauf `refresh()` (une requête HTTP) — à appeler depuis un worker.
"""

from __future__ import annotations

import json
import os
import urllib.request

CACHE_NAME = "comfy_image_catalog.json"
PREFIX = "comfy:"

#: Familles mises en tête (ordre du sélecteur) ; le reste suit, alphabétique.
_PRIORITY = ("z_image", "flux2_klein", "qwen_image", "flux2", "krea2", "flux_dev",
             "flux_kontext", "sdxl", "sd3", "hidream", "chroma", "lumina", "omnigen",
             "firered", "hunyuan")


def cache_path() -> str:
    from core.externals import externals_dir
    return os.path.join(externals_dir(), CACHE_NAME)


#: Catégories de l'index qui sont de la GÉNÉRATION d'image. « Image Tools »
#: (agrandisseurs, détourage, profondeur) n'en est pas ; les catégories
#: « Product & Ads », « Character & Fashion »… sont bâties sur des nœuds API
#: payants. ⚠ `mediaType` de l'index décrit la VIGNETTE, pas le workflow :
#: filtrer dessus laissait passer 3D, vidéo, audio et LLM (constat 24/09/2026).
IMAGE_CATEGORIES = ("Image",)


def _is_local_image_template(t: dict, category: str = "") -> bool:
    name = str(t.get("name") or "")
    if not name or name.startswith("api_"):
        return False
    if category and category not in IMAGE_CATEGORIES:
        return False
    if t.get("openSource") is False:
        return False
    return True


def _priority(name: str) -> tuple:
    for i, frag in enumerate(_PRIORITY):
        if frag in name:
            return (i, name)
    return (len(_PRIORITY), name)


def _normalize(t: dict, category: str) -> dict:
    tags = [str(x) for x in (t.get("tags") or [])]
    title = str(t.get("title") or t.get("name"))
    edit = ("Image Edit" in tags) or ("Edit" in title) or ("Style Reference" in title)
    return {
        "name": t.get("name"),
        "title": title,
        "category": category,
        "tags": tags,
        "size": int(t.get("size") or 0),
        "edit": bool(edit),
        "models": [str(m) for m in (t.get("models") or [])],
        "min_version": str(t.get("minComfyUIVersion") or ""),
        "description": str(t.get("description") or "")[:200],
    }


def parse_index(index: list) -> list[dict]:
    """L'index brut de ComfyUI → entrées normalisées, triées familles d'abord."""
    out, seen = [], set()
    for cat in index or []:
        ctitle = str(cat.get("title") or cat.get("moduleName") or "")
        for t in cat.get("templates") or []:
            if not _is_local_image_template(t, ctitle) or t["name"] in seen:
                continue
            seen.add(t["name"])
            out.append(_normalize(t, ctitle))
    out.sort(key=lambda e: _priority(e["name"]))
    return out


def probe_entries(base_url: str, entries: list[dict], object_info: dict | None = None) -> list[dict]:
    """Ne garde que ce que PANDORA sait PILOTER : chaque gabarit est chargé chez
    le serveur, converti, analysé (core/comfy_image) — il faut un nœud de
    prompt et une sortie ; les gabarits bâtis sur des nœuds API (payants,
    `api_node` dans /object_info) sont écartés. Le nombre d'images d'entrée
    (LoadImage) devient le nombre de références acceptées."""
    from core import comfy_image as _ci
    from core import comfy_workflow as _wf
    oi = object_info or _ci.object_info(base_url)
    kept = []
    for e in entries:
        try:
            wf = _ci.load_template(base_url, e["name"])
            flat = _wf.flatten(wf)
            classes = {n.get("type") for n in flat.get("nodes", [])}
            if any((oi.get(c) or {}).get("api_node") for c in classes):
                continue
            api = _wf.to_api(wf, oi)
            info = _ci.analyze(api, oi)
            if not info["prompt_nodes"] or not info["outputs"]:
                continue
            e = dict(e)
            e["loads"] = len(info["load_images"])
            e["edit"] = bool(info["load_images"]) or e.get("edit", False)
            e["negative"] = bool(info["negative_nodes"])
            e["sized"] = bool(info["size_targets"])
            kept.append(e)
        except Exception:
            continue
    return kept


def refresh(base_url: str, timeout: float = 15.0, probe: bool = True) -> list[dict]:
    """Relit l'index chez ComfyUI, sonde les gabarits (probe) et réécrit le
    cache. Lève si l'index est injoignable."""
    with urllib.request.urlopen(base_url.rstrip("/") + "/templates/index.json", timeout=timeout) as r:
        index = json.loads(r.read().decode("utf-8", "replace"))
    entries = parse_index(index)
    if probe:
        entries = probe_entries(base_url, entries)
    path = cache_path()
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump({"base_url": base_url, "templates": entries}, f, ensure_ascii=False, indent=1)
    os.replace(tmp, path)
    return entries


def load_cached() -> list[dict]:
    try:
        with open(cache_path(), encoding="utf-8") as f:
            return list(json.load(f).get("templates") or [])
    except Exception:
        return []


# ── Gabarits VIDÉO à entrée vidéo : « Modifier un clip » en local ────────────
# Catégories « Video » et « Video Tools » de l'index ; on ne garde que ce qui
# PREND un clip (LoadVideo) et en rend un — édition (Bernini-R, Capybara…),
# inpainting (VOID), agrandissement (SeedVR2), interpolation. Les gabarits qui
# exigent une détection ou un masque à décrire (SCAIL-2, VACE, Wan Animate)
# entrent aussi : PANDORA remplit ce qu'il reconnaît, le reste garde la valeur
# du gabarit — l'utilisateur voit le titre et choisit.

VIDEO_CACHE_NAME = "comfy_video_catalog.json"
VIDEO_CATEGORIES = ("Video", "Video Tools")
_VIDEO_PRIORITY = ("video_edit", "editing", "inpaint", "upscale", "character", "animate",
                   "vace", "interpolation")


def video_cache_path() -> str:
    from core.externals import externals_dir
    return os.path.join(externals_dir(), VIDEO_CACHE_NAME)


def _video_kind(t: dict) -> str:
    tags = " ".join(str(x) for x in (t.get("tags") or [])).lower()
    name = str(t.get("name") or "").lower()
    if "video edit" in tags or "video_edit" in name or "editing" in name:
        return "edit"
    if "inpaint" in tags or "inpaint" in name:
        return "inpaint"
    if "upscale" in tags or "upscale" in name:
        return "upscale"
    if "interpolation" in tags:
        return "interpolation"
    if "character" in tags or "motion" in tags or "animate" in name or "vace" in name:
        return "character"
    return "other"


def _video_priority(e: dict) -> tuple:
    order = ("edit", "inpaint", "upscale", "character", "interpolation", "other")
    k = e.get("kind", "other")
    return (order.index(k) if k in order else len(order), e.get("name", ""))


def parse_video_index(index: list) -> list[dict]:
    out, seen = [], set()
    for cat in index or []:
        ctitle = str(cat.get("title") or cat.get("moduleName") or "")
        if ctitle not in VIDEO_CATEGORIES:
            continue
        for t in cat.get("templates") or []:
            name = str(t.get("name") or "")
            if not name or name.startswith("api_") or t.get("openSource") is False or name in seen:
                continue
            seen.add(name)
            e = _normalize(t, ctitle)
            e["kind"] = _video_kind(t)
            out.append(e)
    out.sort(key=_video_priority)
    return out


def probe_video_entries(base_url: str, entries: list[dict], object_info: dict | None = None) -> list[dict]:
    """Ne garde que ce qui PREND un clip et en REND un ; note s'il y a une
    consigne texte (`prompted`) et combien d'images de référence (`loads`)."""
    from core import comfy_image as _ci
    from core import comfy_workflow as _wf
    oi = object_info or _ci.object_info(base_url)
    kept = []
    for e in entries:
        try:
            wf = _ci.load_template(base_url, e["name"])
            flat = _wf.flatten(wf)
            classes = {n.get("type") for n in flat.get("nodes", [])}
            if any((oi.get(c) or {}).get("api_node") for c in classes):
                continue
            api = _wf.to_api(wf, oi)
            info = _ci.analyze(api, oi)
            if not info.get("load_videos") or not info["outputs"]:
                continue
            e = dict(e)
            e["loads"] = len(info["load_images"])
            e["prompted"] = bool(info["prompt_nodes"])
            e["negative"] = bool(info["negative_nodes"])
            kept.append(e)
        except Exception:
            continue
    return kept


def refresh_video(base_url: str, timeout: float = 15.0, probe: bool = True) -> list[dict]:
    with urllib.request.urlopen(base_url.rstrip("/") + "/templates/index.json", timeout=timeout) as r:
        index = json.loads(r.read().decode("utf-8", "replace"))
    entries = parse_video_index(index)
    if probe:
        entries = probe_video_entries(base_url, entries)
    path = video_cache_path()
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump({"base_url": base_url, "templates": entries}, f, ensure_ascii=False, indent=1)
    os.replace(tmp, path)
    return entries


def load_cached_video() -> list[dict]:
    try:
        with open(video_cache_path(), encoding="utf-8") as f:
            return list(json.load(f).get("templates") or [])
    except Exception:
        return []


_KIND_LABEL = {"edit": "édition", "inpaint": "inpainting", "upscale": "agrandissement",
               "character": "personnage / mouvement", "interpolation": "interpolation", "other": "outil"}


def video_engine_label(entry: dict) -> str:
    """Libellé du sélecteur « Modifier un clip » : ComfyUI · titre · genre · poids · 0 $."""
    return (f"ComfyUI · {entry.get('title') or entry['name']}  ·  {_KIND_LABEL.get(entry.get('kind'), 'outil')}"
            f" · {gb(int(entry.get('size') or 0))} sur votre GPU  ·  0 $")


def engine_key(name: str) -> str:
    return PREFIX + name


def is_comfy_engine(key: str) -> bool:
    return str(key or "").startswith(PREFIX)


def template_name(key: str) -> str:
    return str(key or "")[len(PREFIX):] if is_comfy_engine(key) else ""


def gb(size: int) -> str:
    return f"{size / 1e9:.0f} Go" if size >= 1e9 else (f"{size / 1e6:.0f} Mo" if size else "?")


def as_engine(entry: dict) -> dict:
    """Une entrée du cache → un moteur du catalogue studio_images/engines."""
    name = entry["name"]
    edit = bool(entry.get("edit"))
    loads = int(entry.get("loads") or (1 if edit else 0))
    return {
        # « $0 » en queue : la mention de prix se LIT dans le libellé (core/image_engines
        # price_hint, api/apercu _image_price_hint) — « 0 $ » n'y était pas lisible.
        "label":    f"ComfyUI · {entry.get('title') or name}  ·  {'édition · réfs' if edit else 'texte → image'}"
                    f" · {gb(int(entry.get('size') or 0))} sur votre GPU  ·  $0",
        "endpoint": engine_key(name),
        "kind":     "comfy",
        "family":   "ComfyUI",
        "slug":     "comfy-" + name.lower().replace("_", "-"),
        "output":   "raster",
        "refs":     ({"max": loads, "hint": f"✅ {loads} image(s) de référence = entrées du gabarit"} if loads
                     else {"max": 0, "hint": "❌ gabarit texte → image : les références sont ignorées"}),
        "comfy":    {"name": name, "edit": edit, "size": int(entry.get("size") or 0),
                     "min_version": entry.get("min_version", ""), "category": entry.get("category", "")},
    }
