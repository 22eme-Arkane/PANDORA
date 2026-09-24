"""core/comfy_image.py — Générer une IMAGE avec ComfyUI, sur n'importe quel gabarit officiel.

Un gabarit d'image n'a pas de nœud unique où écrire, contrairement à H3
(core/comfy_h3). Il y en a 270, de dix familles : le contrat est donc lu dans
la STRUCTURE du graphe API (après conversion et aplatissement par
core/comfy_workflow), avec les définitions de nœuds du serveur :

  prompt   → on part de l'échantillonneur (l'entrée `positive` d'un KSampler,
             KSamplerAdvanced, SamplerCustom, ou du guide relié à un
             SamplerCustomAdvanced), on remonte la chaîne de conditionnement
             (ReferenceLatent, ConditioningZeroOut, FluxGuidance, combinaisons…)
             jusqu'au PREMIER nœud portant une entrée STRING multiligne :
             CLIPTextEncode.text, TextEncodeQwenImageEditPlus.prompt,
             CLIPTextEncodeFlux (clip_l ET t5xxl), etc. TOUTES ses entrées texte
             reçoivent le prompt. Le prompt négatif suit l'entrée `negative` ;
             s'il aboutit au même nœud (ou à un ConditioningZeroOut), il n'y en
             a pas.
  cadre    → tout nœud à entrées `width` + `height` INT littérales — ou reliées
             à un PrimitiveInt (entrées promues d'un sous-graphe) — hors nœuds
             qui traitent une IMAGE (les mises à l'échelle des références).
             Sur un gabarit d'édition, le cadre suit l'image : on ne touche à rien.
  seed     → `seed` / `noise_seed`, littéral ou via PrimitiveInt.
  refs     → les LoadImage du graphe élagué, dans l'ordre ; s'il en reste sans
             image, ils reçoivent la première (un gabarit à trois entrées ne
             doit pas partir avec l'image d'exemple, absente du serveur).
  sortie   → les nœuds `output_node` (SaveImage…) ; la première image de
             `/history`, servie par `/view` : une URL que les appelants
             téléchargent EXACTEMENT comme une URL fal.

`subscribe()` a la signature de fal_client.subscribe pour que core/image_call
le substitue sans que les points de génération changent (fiches, moods,
Studio Images). Prix : 0 $.
"""

from __future__ import annotations

import base64
import json
import os
import random
import time

from core import comfy as _cf
from core import comfy_workflow as _wf

_OBJ_CACHE: dict = {}          # base_url → (t, object_info)
_OBJ_TTL_S = 600
_POLL_S = 1.5
_MAX_WAIT_S = 3600


class NoPromptTarget(ValueError):
    pass


# ── Définitions ──────────────────────────────────────────────────────────────

def object_info(base: str) -> dict:
    now = time.time()
    t, oi = _OBJ_CACHE.get(base, (0, None))
    if oi is None or now - t > _OBJ_TTL_S:
        oi = _cf.fetch_object_info(base)
        _OBJ_CACHE[base] = (now, oi)
    return oi


def _inputs_spec(oi: dict, cls: str) -> dict:
    inp = (oi.get(cls) or {}).get("input") or {}
    out = {}
    for sect in ("required", "optional"):
        out.update(inp.get(sect) or {})
    return out


def _string_inputs(oi: dict, cls: str) -> list[str]:
    names = []
    for name, desc in _inputs_spec(oi, cls).items():
        if isinstance(desc, (list, tuple)) and desc and desc[0] == "STRING":
            extra = desc[1] if len(desc) > 1 and isinstance(desc[1], dict) else {}
            if extra.get("multiline"):
                names.append(name)
    return names


def _input_type(oi: dict, cls: str, name: str) -> str:
    desc = _inputs_spec(oi, cls).get(name)
    if isinstance(desc, (list, tuple)) and desc and isinstance(desc[0], str):
        return desc[0]
    return ""


def _has_image_input(oi: dict, cls: str) -> bool:
    return any(_input_type(oi, cls, n) == "IMAGE" for n in _inputs_spec(oi, cls))


# ── Analyse ──────────────────────────────────────────────────────────────────

def _is_link(v) -> bool:
    return isinstance(v, list) and len(v) == 2 and isinstance(v[0], str)


def _text_node_upstream(api: dict, oi: dict, start_link, polarity: str = "positive",
                        max_hops: int = 24):
    """Remonte un lien de conditionnement jusqu'au premier nœud à texte, en
    gardant sa POLARITÉ : un nœud qui porte à la fois `positive` et `negative`
    (ControlNetApply*, InpaintModelConditioning, InstructPixToPix…) laisse
    passer les deux — on suit la sienne. Suivre toujours la première entrée
    envoyait le négatif sur le prompt positif (24 gabarits sans prompt, 24/09/2026)."""
    seen = set()
    link = start_link
    for _ in range(max_hops):
        if not _is_link(link):
            return None
        nid = link[0]
        if nid in seen or nid not in api:
            return None
        seen.add(nid)
        cls = api[nid]["class_type"]
        if cls == "ConditioningZeroOut":
            return ("zero", nid)
        if _string_inputs(oi, cls):
            return ("text", nid)
        ins = api[nid].get("inputs") or {}
        if cls == "ComfySwitchNode":
            # Aiguillage V3 (HiDream O1 : « amélioration du prompt » ou non) :
            # on suit la branche choisie par `switch` (à défaut, on_true).
            sw = ins.get("switch")
            branch = "on_false" if sw is False else "on_true"
            link = ins.get(branch) if _is_link(ins.get(branch)) else ins.get("on_false")
            continue
        conds = [(name, val) for name, val in ins.items()
                 if _is_link(val) and _input_type(oi, cls, name) == "CONDITIONING"]
        if not conds:
            return None
        named = dict(conds)
        if polarity in named:
            link = named[polarity]
        elif polarity == "negative" and any(n.startswith("negative") for n, _v in conds):
            link = next(v for n, v in conds if n.startswith("negative"))
        elif polarity == "negative" and "conditioning_1" in named and "conditioning" in named:
            link = named["conditioning_1"]           # sous-graphe « positif, négatif » aplati
        else:
            link = conds[0][1]
    return None


def _primitive_source(api: dict, val):
    """Si `val` est un lien vers un PrimitiveInt/Float/String, rend son id."""
    if _is_link(val) and val[0] in api and api[val[0]]["class_type"] in (
            "PrimitiveInt", "PrimitiveFloat", "PrimitiveStringMultiline", "PrimitiveString"):
        return val[0]
    return None


def analyze(api: dict, oi: dict) -> dict:
    """Où écrire dans ce graphe : prompts, cadre, seeds, références, sorties."""
    prompt_nodes: list[str] = []
    negative_nodes: list[str] = []
    arrivals: dict[str, list[int]] = {}       # nœud texte → [positifs, négatifs]
    # Points de départ = les échantillonneurs et guides : un nœud à entrée
    # `model` qui reçoit du conditionnement (KSampler, CFGGuider, BasicGuider,
    # DualCFGGuider — cond1/cond2 —, SamplerCustom…). Jamais un intermédiaire
    # (ReferenceLatent, ConditioningZeroOut…), qui ferait passer le négatif
    # pour du positif. `negative` mène au prompt négatif ; TOUTE autre entrée
    # de conditionnement mène au prompt.
    for nid, n in api.items():
        ins = n.get("inputs") or {}
        cls = n["class_type"]
        if "model" not in ins:
            continue
        for name, val in ins.items():
            if not _is_link(val) or _input_type(oi, cls, name) != "CONDITIONING":
                continue
            polarity = "negative" if name == "negative" else "positive"
            found = _text_node_upstream(api, oi, val, polarity)
            if not found or found[0] != "text":
                continue
            arrivals.setdefault(found[1], [0, 0])[1 if polarity == "negative" else 0] += 1
            bucket = negative_nodes if polarity == "negative" else prompt_nodes
            if found[1] not in bucket:
                bucket.append(found[1])
    # Nœud atteint des DEUX côtés — trois cas relevés (24/09/2026) :
    #   · il a un champ « negative… » (TextEncodeMageFlow) : il porte les deux
    #     textes, il reste un nœud de prompt ;
    #   · le positif y arrive plus souvent (HiDream E1.1 : cond1 + cond2 + le
    #     négatif sur le MÊME encodeur — le schéma instruct-pix2pix) : prompt ;
    #   · à égalité (OmniGen2 : cond2 = le négatif) : c'est le négatif si son
    #     texte d'origine y ressemble (« blurry, low quality… »), sinon le prompt.
    for nid in [n for n in prompt_nodes if n in negative_nodes]:
        cls = api[nid]["class_type"]
        pos, neg = arrivals.get(nid, [0, 0])
        if any("negative" in s.lower() for s in _string_inputs(oi, cls)) or pos > neg or \
                (pos == neg and not _looks_negative(api[nid]["inputs"], _string_inputs(oi, cls))):
            negative_nodes.remove(nid)
        else:
            prompt_nodes.remove(nid)

    size_targets: list[tuple[str, str]] = []     # (nid, "width"/"height") — littéraux ou primitives
    seed_targets: list[tuple[str, str]] = []
    for nid, n in api.items():
        cls = n["class_type"]
        ins = n.get("inputs") or {}
        if "width" in ins and "height" in ins and not _has_image_input(oi, cls) \
                and _input_type(oi, cls, "width") == "INT":
            for dim in ("width", "height"):
                v = ins[dim]
                if not _is_link(v):
                    size_targets.append((nid, dim))
                else:
                    src = _primitive_source(api, v)
                    if src:
                        size_targets.append((src, "value"))
        for sname in ("seed", "noise_seed"):
            if sname in ins:
                v = ins[sname]
                if not _is_link(v):
                    seed_targets.append((nid, sname))
                else:
                    src = _primitive_source(api, v)
                    if src:
                        seed_targets.append((src, "value"))
    loads = sorted((nid for nid, n in api.items() if n["class_type"] == "LoadImage"), key=_natural)
    # Gabarits VIDÉO (édition, agrandissement… — core/comfy_video) : le clip
    # source entre par un nœud LoadVideo (entrée `file`, déposée par /upload/image).
    videos = sorted((nid for nid, n in api.items() if n["class_type"] == "LoadVideo"), key=_natural)
    outputs = [nid for nid, n in api.items() if (oi.get(n["class_type"]) or {}).get("output_node")]
    return {
        "prompt_nodes": prompt_nodes, "negative_nodes": negative_nodes,
        "size_targets": sorted(set(size_targets)), "seed_targets": sorted(set(seed_targets)),
        "load_images": loads, "load_videos": videos, "outputs": outputs,
    }


_NEGATIVE_WORDS = ("blurry", "low quality", "lowres", "deformed", "ugly", "bad anatomy",
                   "watermark", "worst quality", "distorted", "jpeg artifacts", "bad hands")


def _looks_negative(inputs: dict, string_names: list[str]) -> bool:
    """Le texte d'origine du gabarit ressemble-t-il à un prompt négatif ?"""
    text = " ".join(str(inputs.get(n) or "") for n in string_names).lower()
    return any(w in text for w in _NEGATIVE_WORDS)


def _natural(nid: str):
    return tuple(int(p) if p.isdigit() else p for p in str(nid).replace(":", ".").split("."))


def fill(api: dict, oi: dict, info: dict, prompt: str, negative: str = "",
         width: int | None = None, height: int | None = None, seed: int | None = None,
         ref_names: list[str] | None = None, video_names: list[str] | None = None,
         require_prompt: bool = True) -> None:
    """`require_prompt=False` : un gabarit SANS nœud de prompt (agrandisseur
    vidéo, interpolation…) reste remplissable — le texte est alors ignoré."""
    if not info["prompt_nodes"] and require_prompt:
        raise NoPromptTarget("Ce gabarit n'a aucun nœud de prompt reconnu : PANDORA ne saurait pas où écrire.")
    for nid in info["prompt_nodes"]:
        for name in _string_inputs(oi, api[nid]["class_type"]):
            # Un champ « negative_prompt » sur le nœud de prompt reçoit le négatif.
            api[nid]["inputs"][name] = (negative or "") if "negative" in name.lower() else prompt
    for nid in info["negative_nodes"]:
        for name in _string_inputs(oi, api[nid]["class_type"]):
            api[nid]["inputs"][name] = negative or ""
    if width and height and not ref_names:
        for nid, name in info["size_targets"]:
            if name == "value":
                # PrimitiveInt promu : lequel est la largeur ? Celui relié à `width`.
                api[nid]["inputs"]["value"] = width if _feeds(api, nid, "width") else height
            else:
                api[nid]["inputs"][name] = width if name == "width" else height
    s = int(seed) if seed is not None else random.randint(1, 2 ** 48)
    for nid, name in info["seed_targets"]:
        api[nid]["inputs"][name] = s
    refs = list(ref_names or [])
    if refs:
        for i, nid in enumerate(info["load_images"]):
            api[nid]["inputs"]["image"] = refs[i] if i < len(refs) else refs[0]
    vids = list(video_names or [])
    if vids:
        for i, nid in enumerate(info.get("load_videos") or []):
            api[nid]["inputs"]["file"] = vids[i] if i < len(vids) else vids[0]


def _feeds(api: dict, src_id: str, input_name: str) -> bool:
    for n in api.values():
        for name, val in (n.get("inputs") or {}).items():
            if name == input_name and _is_link(val) and val[0] == src_id:
                return True
    return False


# ── Gabarit ──────────────────────────────────────────────────────────────────

def template_dir() -> str:
    from core.externals import externals_dir
    d = os.path.join(externals_dir(), "comfy_templates")
    os.makedirs(d, exist_ok=True)
    return d


def load_template(base: str, name: str) -> dict:
    """Le gabarit officiel, servi par ComfyUI (mis en cache localement)."""
    import urllib.request
    path = os.path.join(template_dir(), f"{name}.json")
    try:
        with urllib.request.urlopen(f"{base}/templates/{name}.json", timeout=20) as r:
            data = r.read()
        with open(path, "wb") as f:
            f.write(data)
        return json.loads(data.decode("utf-8", "replace"))
    except Exception:
        if os.path.isfile(path):
            return _wf.load(path)
        raise


# ── Protocole ────────────────────────────────────────────────────────────────

def _ref_bytes(ref) -> bytes:
    """Une référence telle que les appelants la donnent : data-URL base64,
    chemin local, ou URL http (téléversée chez fal par le workflow des moods)."""
    s = str(ref or "")
    if s.startswith("data:"):
        return base64.b64decode(s.split(",", 1)[1])
    if s.startswith(("http://", "https://")):
        import requests
        return requests.get(s, timeout=120).content
    with open(s, "rb") as f:
        return f.read()


def upload_ref(base: str, ref, index: int) -> str:
    import requests
    data = _ref_bytes(ref)
    name = f"pandora_ref_{int(time.time())}_{index}.png"
    r = requests.post(f"{base}/upload/image", files={"image": (name, data)},
                      data={"overwrite": "true", "subfolder": "pandora"}, timeout=120)
    r.raise_for_status()
    j = r.json() or {}
    sub = j.get("subfolder") or ""
    return f"{sub}/{j.get('name') or name}" if sub else (j.get("name") or name)


def upload_video(base: str, path: str) -> str:
    """Dépose un clip dans le dossier d'entrée de ComfyUI (même point d'accès
    que les images — LoadVideo lit `input/`) ; rend le nom attendu par `file`."""
    import requests
    if not (path and os.path.isfile(path)):
        raise RuntimeError(f"Clip source introuvable : {path}")
    name = f"pandora_clip_{int(time.time())}_{os.path.basename(path)}"
    with open(path, "rb") as f:
        r = requests.post(f"{base}/upload/image", files={"image": (name, f)},
                          data={"overwrite": "true", "subfolder": "pandora"}, timeout=600)
    r.raise_for_status()
    j = r.json() or {}
    sub = j.get("subfolder") or ""
    return f"{sub}/{j.get('name') or name}" if sub else (j.get("name") or name)


def queue(base: str, api: dict) -> str:
    import requests
    r = requests.post(f"{base}/prompt", json=_cf.prompt_payload(api, _cf.new_client_id()), timeout=60)
    if r.status_code >= 400:
        try:
            j = r.json()
            err = (j.get("error") or {}).get("message") or ""
            det = "; ".join(f"{k}: {v.get('errors', [{}])[0].get('message', '')}"
                            for k, v in list((j.get("node_errors") or {}).items())[:3] if isinstance(v, dict))
            raise RuntimeError(f"ComfyUI a refusé le workflow — {err} {det}".strip())
        except ValueError:
            r.raise_for_status()
    pid = (r.json() or {}).get("prompt_id")
    if not pid:
        raise RuntimeError(f"ComfyUI n'a pas rendu d'identifiant : {r.text[:200]}")
    return pid


def wait(base: str, pid: str, progress=None, is_cancelled=None) -> dict:
    import requests
    t0 = time.time()
    while True:
        if is_cancelled and is_cancelled():
            try:
                requests.post(f"{base}/interrupt", timeout=5)
                requests.post(f"{base}/queue", json={"delete": [pid]}, timeout=5)
            except Exception:
                pass
            raise RuntimeError("Génération annulée.")
        if time.time() - t0 > _MAX_WAIT_S:
            raise RuntimeError("Délai dépassé : ComfyUI ne répond plus.")
        h = requests.get(f"{base}/history/{pid}", timeout=30).json() or {}
        entry = h.get(pid)
        if entry:
            state, msg = _cf.history_status(entry)
            if state == "success":
                return entry
            if state == "error":
                raise RuntimeError(f"Échec côté ComfyUI : {msg}")
        if progress:
            progress(f"ComfyUI — rendu en cours ({int(time.time() - t0)} s)…")
        time.sleep(_POLL_S)


# ── Point d'entrée « comme fal » ─────────────────────────────────────────────

def subscribe(template_name: str, arguments: dict | None = None, progress=None,
              is_cancelled=None) -> dict:
    """Même forme de retour que fal_client.subscribe : {"images": [{"url": …}]}.
    arguments : prompt, negative, width, height, seed, ref_urls (data-URL /
    chemins / http), workflow (dict déjà chargé, optionnel)."""
    args = dict(arguments or {})
    base = _cf.discover()
    if not base:
        raise RuntimeError("ComfyUI injoignable. Lancez ComfyUI Desktop (ou corrigez l'adresse "
                           "dans Paramètres), puis relancez.")
    if progress:
        progress("ComfyUI — lecture du gabarit…")
    wf = args.get("workflow") or load_template(base, template_name)
    oi = object_info(base)
    api = _wf.to_api(wf, oi)
    info = analyze(api, oi)
    refs = [r for r in (args.get("ref_urls") or []) if r]
    names = []
    if refs and info["load_images"]:
        if progress:
            progress("ComfyUI — envoi des références…")
        names = [upload_ref(base, r, i) for i, r in enumerate(refs[:len(info["load_images"])])]
    fill(api, oi, info, str(args.get("prompt") or ""), str(args.get("negative") or ""),
         args.get("width"), args.get("height"), args.get("seed"), names)
    api = _wf.prune_unreachable(api, oi)
    missing = _wf.missing_models(api, oi)
    if missing:
        lines = "\n".join(f"  • {f}  →  models/{d}" for f, d, _c in missing)
        raise RuntimeError("Fichiers de modèles absents de ComfyUI :\n" + lines
                           + "\nParamètres → Modules externes → ComfyUI, ou laissez ComfyUI les "
                             "télécharger en ouvrant le gabarit une fois.")
    if progress:
        progress("ComfyUI — envoi du workflow…")
    pid = queue(base, api)
    entry = wait(base, pid, progress, is_cancelled)
    files = [f for f in _cf.outputs_of(entry) if not f["filename"].lower().endswith(
        (".mp4", ".webm", ".mov", ".mkv"))]
    if not files:
        raise RuntimeError("Le gabarit s'est terminé sans produire d'image.")
    return {"images": [{"url": _cf.view_url(base, it), "content_type": "image/png",
                        "file_name": it["filename"]} for it in files],
            "seed": None, "engine": "comfy:" + template_name}
