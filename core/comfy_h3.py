"""core/comfy_h3.py — Où PANDORA écrit dans un workflow ComfyUI.

Un workflow est un graphe ; PANDORA n'en connaît que quelques nœuds, ceux où
le plan doit entrer : le texte, les images, le cadre, la durée, la seed. Ce
module décide, par CLASSE de nœud, quelle entrée reçoit quoi — et ne touche à
rien d'autre. Un gabarit reste le gabarit de son auteur.

Contrat relevé sur les gabarits OFFICIELS (Comfy-Org/workflow_templates,
video_minimax_h3_{t2v,i2v,r2v}, 2026-09-13) et les sources de ComfyUI
(comfy_extras/nodes_minimax_h3.py, nodes_primitive.py) :

  prompt   → MiniMaxH3ImageToVideo.prompt ou MiniMaxH3ReferenceToVideo.prompt
             (pas CLIPTextEncode : H3 encode son texte lui-même), repli
             PrimitiveStringMultiline.value, puis CLIPTextEncode.text
  durée    → PrimitiveFloat.value EN SECONDES : un ComfyMathExpression du
             gabarit calcule ensuite « 17k+5 » images à 24 fps — on ne touche
             pas à `length`, qui est relié à ce calcul
  cadre    → width/height du nœud H3 (pas 32 obligé, min 32) — en T2V seulement :
             en I2V le gabarit déduit le cadre de l'image d'entrée
  seed     → RandomNoise.noise_seed ; le gabarit est en « fixed » et rendrait
             la MÊME vidéo à chaque clic : sans seed fournie, on en tire une
  images   → LoadImage.image (la 1re du fichier = départ) ; la dernière image
             passe par un LoadImage SYNTHÉTIQUE relié à `last_frame`, que le
             gabarit laisse libre

Module PUR.
"""

from __future__ import annotations

import os
import random

from core import comfy_workflow as _wf

#: Nœuds H3 apportés par ComfyUI ≥ 0.30 (relevé 13/09/2026).
H3_NODES = ("MiniMaxH3ImageToVideo", "MiniMaxH3ReferenceToVideo", "EmptyMiniMaxH3LatentAV")
#: Où le prompt peut entrer, par ordre de préférence.
PROMPT_TARGETS = (("MiniMaxH3ImageToVideo", "prompt"), ("MiniMaxH3ReferenceToVideo", "prompt"),
                  ("PrimitiveStringMultiline", "value"), ("CLIPTextEncode", "text"))

#: Gabarits PANDORA (assets/comfy_workflows) par clé de moteur.
TEMPLATES = {
    "comfy_h3_t2v": "minimax_h3_t2v.json",
    "comfy_h3_i2v": "minimax_h3_i2v.json",
}

FPS = 24
FRAMES_STEP, FRAMES_BASE = 17, 5
#: Cadres natifs H3 par résolution PANDORA, en (petit côté, grand côté),
#: multiples de 32 — ceux des gabarits officiels pour 768p.
FRAMES = {"480p": (480, 848), "768p": (768, 1344)}
_LANDSCAPE = ("16:9", "21:9", "4:3")

END_IMAGE_NODE = "pandora_end_frame"


class NoPromptTarget(ValueError):
    """Le workflow n'a aucun nœud où écrire le texte du plan."""


def snap_frames(seconds) -> int:
    """« 17k+5 » images à 24 fps — la formule du ComfyMathExpression officiel."""
    try:
        f = max(5, int(round(float(seconds) * FPS)))
    except (TypeError, ValueError):
        f = 124
    return f + (5 - (f % 17)) % 17


def frame_for(resolution: str, aspect_ratio: str) -> tuple[int, int]:
    short, long_ = FRAMES.get((resolution or "768p").lower().split()[0], FRAMES["768p"])
    r = (aspect_ratio or "16:9").strip()
    if r == "1:1":
        return short, short
    if r in _LANDSCAPE:
        return long_, short
    return short, long_


def template_path(engine_key: str) -> str:
    name = TEMPLATES.get(engine_key, "")
    return os.path.join(_wf.workflows_dir(), name) if name else ""


def prepare_params(params: dict, engine_key: str) -> dict:
    """Complète `params` pour ComfyWorker selon le moteur choisi : chemin du
    gabarit (ou du workflow personnalisé réglé dans les Paramètres) et libellé."""
    if engine_key == "comfy_custom":
        from core.config import load_config
        params["workflow_path"] = (load_config().get("comfy_custom_workflow") or "").strip()
        params["engine_label"] = "ComfyUI · workflow personnalisé"
    else:
        params["workflow_path"] = template_path(engine_key)
        params["engine_label"] = "ComfyUI · MiniMax H3"
    params.setdefault("mode", "i2v" if engine_key.endswith("_i2v") else "t2v")
    return params


def fill_plan(api: dict, params: dict, prompt_en: str) -> list[tuple[str, str, object]]:
    """Liste de (classe, entrée, valeur), uniquement pour les classes PRÉSENTES.
    Lève NoPromptTarget si aucun nœud ne peut recevoir le texte : envoyer le
    gabarit tel quel rendrait la vidéo de l'exemple, pas celle du plan."""
    plan: list[tuple[str, str, object]] = []

    target = next(((c, i) for c, i in PROMPT_TARGETS if _wf.find(api, c)), None)
    if target is None:
        raise NoPromptTarget(
            "Ce workflow n'a aucun nœud de prompt reconnu (MiniMaxH3*, "
            "PrimitiveStringMultiline ou CLIPTextEncode) : PANDORA ne saurait "
            "pas où écrire votre description.")
    plan.append((target[0], target[1], prompt_en))

    seed = params.get("seed")
    seed = int(seed) if seed is not None else random.randint(1, 2**48)
    if _wf.find(api, "RandomNoise"):
        plan.append(("RandomNoise", "noise_seed", seed))
    for cls, name in (("KSampler", "seed"), ("KSamplerAdvanced", "noise_seed")):
        if _wf.find(api, cls):
            plan.append((cls, name, seed))

    if params.get("duration") and _wf.find(api, "PrimitiveFloat"):
        plan.append(("PrimitiveFloat", "value", float(params["duration"])))
    elif params.get("duration"):
        length = snap_frames(params["duration"])
        for cls in H3_NODES:
            if _wf.find(api, cls):
                plan.append((cls, "length", length))

    if (params.get("mode") or "t2v") != "i2v":
        w, h = frame_for(params.get("resolution") or "768p", params.get("aspect_ratio") or "16:9")
        for cls in H3_NODES:
            if _wf.find(api, cls):
                plan += [(cls, "width", w), (cls, "height", h)]
    return plan


def apply_images(api: dict, params: dict) -> None:
    """Image de départ → premier LoadImage ; image de fin → LoadImage
    synthétique relié à `last_frame` du nœud H3 s'il est libre."""
    start = params.get("_comfy_image") or ""
    end = params.get("_comfy_end_image") or ""
    loaders = _wf.find(api, "LoadImage")
    if start and loaders:
        _wf.set_input(api, loaders[0], "image", start)
    if not end:
        return
    h3 = next((nid for cls in ("MiniMaxH3ImageToVideo",) for nid in _wf.find(api, cls)), None)
    if h3 is None:
        return
    if api[h3].get("inputs", {}).get("last_frame") is None:
        api[END_IMAGE_NODE] = {"class_type": "LoadImage", "inputs": {"image": end}}
        _wf.set_input(api, h3, "last_frame", [END_IMAGE_NODE, 0])
