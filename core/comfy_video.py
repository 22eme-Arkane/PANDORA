"""core/comfy_video.py — Modifier un clip SUR VOTRE MACHINE avec un gabarit ComfyUI.

Le pendant vidéo de core/comfy_image : les gabarits officiels d'ÉDITION vidéo
(Bernini-R, Capybara « Video Edit », inpainting VOID, agrandissement SeedVR2…)
ont tous la même forme — un clip qui entre par `LoadVideo`, une consigne dans
un nœud de texte (ou aucune : agrandisseur), une vidéo qui sort par `SaveVideo`.
Le contrat est LU dans la structure (core/comfy_image.analyze + `load_videos`),
jamais écrit à la main : le catalogue (core/comfy_catalog, catégories « Video »
et « Video Tools ») suit les mises à jour de ComfyUI.

`subscribe("<gabarit>", {...})` rend `{"video": {"url": /view…}}` — la même
forme qu'un moteur fal, pour que « Modifier un clip » n'ait rien à savoir de
ComfyUI. 0 $.

Appelé depuis un worker (réseau + attente). Chantier du 24/09/2026.
"""

from __future__ import annotations

import os

from core import comfy as _cf
from core import comfy_image as _ci
from core import comfy_workflow as _wf

PREFIX = "comfy_edit:"
_VIDEO_EXT = (".mp4", ".webm", ".mov", ".mkv", ".gif", ".webp", ".avi")


def engine_key(name: str) -> str:
    return PREFIX + name


def is_edit_engine(key: str) -> bool:
    return str(key or "").startswith(PREFIX)


def template_name(key: str) -> str:
    return str(key or "")[len(PREFIX):] if is_edit_engine(key) else ""


def subscribe(template_name: str, arguments: dict | None = None, progress=None,
              is_cancelled=None) -> dict:
    """arguments : video_path (clip source, OBLIGATOIRE), prompt, negative,
    ref_urls (images : data-URL / chemins / http — LoadImage du gabarit),
    seed, workflow (dict déjà chargé, optionnel)."""
    args = dict(arguments or {})
    base = _cf.discover()
    if not base:
        raise RuntimeError("ComfyUI injoignable. Lancez ComfyUI Desktop (ou corrigez l'adresse "
                           "dans Paramètres), puis relancez.")
    if progress:
        progress("ComfyUI — lecture du gabarit…")
    wf = args.get("workflow") or _ci.load_template(base, template_name)
    oi = _ci.object_info(base)
    api = _wf.to_api(wf, oi)
    info = _ci.analyze(api, oi)
    if not info.get("load_videos"):
        raise RuntimeError("Ce gabarit ne prend pas de clip en entrée (aucun nœud LoadVideo).")
    if progress:
        progress("ComfyUI — envoi du clip…")
    vid_name = _ci.upload_video(base, str(args.get("video_path") or ""))
    names = []
    refs = [r for r in (args.get("ref_urls") or []) if r]
    if refs and info["load_images"]:
        if progress:
            progress("ComfyUI — envoi des références…")
        names = [_ci.upload_ref(base, r, i) for i, r in enumerate(refs[:len(info["load_images"])])]
    prompt = str(args.get("prompt") or "")
    _ci.fill(api, oi, info, prompt, str(args.get("negative") or ""),
             None, None, args.get("seed"), names, [vid_name],
             require_prompt=bool(prompt) and bool(info["prompt_nodes"]))
    api = _wf.prune_unreachable(api, oi)
    missing = _wf.missing_models(api, oi)
    if missing:
        lines = "\n".join(f"  • {f}  →  models/{d}" for f, d, _c in missing)
        raise RuntimeError("Fichiers de modèles absents de ComfyUI :\n" + lines
                           + "\nParamètres → Modules externes → ComfyUI → « Télécharger les modèles "
                             "de ce gabarit », puis relancez.")
    if progress:
        progress("ComfyUI — envoi du workflow…")
    pid = _ci.queue(base, api)
    entry = _ci.wait(base, pid, progress, is_cancelled)
    files = [f for f in _cf.outputs_of(entry) if f["filename"].lower().endswith(_VIDEO_EXT)]
    if not files:
        raise RuntimeError("Le gabarit s'est terminé sans produire de vidéo.")
    it = files[0]
    url = _cf.view_url(base, it)
    return {"video": {"url": url, "file_name": it["filename"]}, "video_url": url,
            "engine": engine_key(template_name), "credits_used": 0.0}


def download(url: str, dest_dir: str, stem: str) -> str:
    """Rapatrie la sortie (`/view`) dans le dossier de sortie vidéo ; WebM/GIF →
    MP4 par ffmpeg (api/h3_local._to_mp4) comme le worker H3."""
    import requests
    ext = os.path.splitext(url.split("filename=")[-1].split("&")[0])[1].lower() or ".mp4"
    os.makedirs(dest_dir, exist_ok=True)
    local = os.path.join(dest_dir, f"{stem}{ext}")
    data = requests.get(url, timeout=600).content
    with open(local, "wb") as f:
        f.write(data)
    if ext in (".webm", ".gif", ".webp"):
        from api.h3_local import _to_mp4
        local = _to_mp4(local)
    return local
