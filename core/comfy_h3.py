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
  cadre    → width/height du nœud H3 (multiples de 32), dans les DEUX modes.
             ⚠ Le gabarit I2V officiel relie le cadre à un ResolutionSelector
             « 1:1 (Square) » à 0,4 MP — PAS à l'image (le ImageScaleToTotalPixels
             → GetImageSize du fichier est débranché) : sans littéraux, un mood
             16:9 serait rendu carré (constat 14/09/2026, ComfyUI 0.35.1). En
             I2V le cadre suit donc le ratio de l'image de départ ; le T2V
             officiel tourne à 0,4 MP (≈ 832×480), d'où le palier 480p par défaut
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
#: Petit côté du cadre H3 par palier PANDORA. Le grand côté se déduit du
#: ratio, au multiple de 32 INFÉRIEUR : 1344 pour 16:9 en 768p (la valeur du
#: gabarit officiel), 832 en 480p (ce que rend le ResolutionSelector officiel
#: à 0,4 MP). 848 (la valeur d'abord retenue) n'est pas un multiple de 32.
SHORT_SIDE = {"480p": 480, "768p": 768}
#: (petit côté, grand côté 16:9) par palier — forme historique, gardée pour
#: les lecteurs qui ne veulent qu'un ordre de grandeur.
FRAMES = {"480p": (480, 832), "768p": (768, 1344)}
#: Au-delà de 21:9 le modèle n'est pas entraîné : on borne le grand côté.
_MAX_RATIO = 2.5

END_IMAGE_NODE = "pandora_end_frame"


def _snap32(x: float) -> int:
    return max(32, int(x // 32) * 32)


def _parse_ratio(text) -> tuple[float, bool]:
    """(grand/petit, paysage ?) depuis « 16:9 » ; repli 16:9 paysage."""
    try:
        a, b = (float(x) for x in str(text).strip().split(":")[:2])
        if a <= 0 or b <= 0:
            raise ValueError
    except Exception:
        return 16 / 9, True
    return max(a, b) / min(a, b), a >= b


class NoPromptTarget(ValueError):
    """Le workflow n'a aucun nœud où écrire le texte du plan."""


def snap_frames(seconds) -> int:
    """« 17k+5 » images à 24 fps — la formule du ComfyMathExpression officiel."""
    try:
        f = max(5, int(round(float(seconds) * FPS)))
    except (TypeError, ValueError):
        f = 124
    return f + (5 - (f % 17)) % 17


def _short_side(resolution: str) -> int:
    return SHORT_SIDE.get((resolution or "480p").lower().split()[0], SHORT_SIDE["480p"])


def frame_for(resolution: str, aspect_ratio: str) -> tuple[int, int]:
    """(largeur, hauteur) pour un palier et un ratio « a:b » quelconque."""
    short = _short_side(resolution)
    ratio, landscape = _parse_ratio(aspect_ratio or "16:9")
    long_ = _snap32(short * min(_MAX_RATIO, max(1.0, ratio)))
    return (long_, short) if landscape else (short, long_)


def frame_for_image(resolution: str, path: str) -> tuple[int, int] | None:
    """Cadre qui garde l'orientation ET le ratio de l'image de départ (I2V),
    ou None si l'image est illisible."""
    try:
        from PIL import Image
        with Image.open(path) as im:
            iw, ih = im.size
    except Exception:
        return None
    if not iw or not ih:
        return None
    return frame_for(resolution, f"{iw}:{ih}")


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

    # Cadre dans les DEUX modes (voir l'en-tête : le gabarit I2V officiel le
    # relie à un sélecteur 1:1, pas à l'image). En I2V il suit l'image de départ.
    res = params.get("resolution") or "480p"
    wh = None
    if (params.get("mode") or "t2v") == "i2v" and params.get("image_path"):
        wh = frame_for_image(res, params["image_path"])
    if wh is None:
        wh = frame_for(res, params.get("aspect_ratio") or "16:9")
    for cls in H3_NODES:
        if _wf.find(api, cls):
            plan += [(cls, "width", wh[0]), (cls, "height", wh[1])]
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
