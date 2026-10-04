import os
from datetime import datetime

from davinci.bridge import resolve
# Téléchargement local = module neutre partagé (le Live l'utilise SANS passer
# par ce fichier, pour ne pas tirer davinci.bridge dans son graphe d'import).
from core.download import download_video, download_result, is_mock_url  # noqa: F401

_IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tiff", ".tif"}
_VIDEO_EXTS = {".mp4", ".mov", ".mxf", ".avi", ".mkv"}
_AUDIO_EXTS = {".wav", ".mp3", ".aac", ".m4a", ".ogg"}

# (clé core/project_layout, sous-dossier optionnel, nom du bin DaVinci).
# Arborescence 2026-07-30 : les dossiers sont résolus par le layout (cible
# 01_writing/02_elements, repli legacy) — l'ancien littéral figé sautait
# SILENCIEUSEMENT tout dossier renommé (isdir → continue).
_PROJECT_BINS = [
    ("castings",   "images", "Castings"),
    ("decors",     "images", "Décors"),
    ("accessories","images", "Accessoires"),
    ("hmc",        "images", "HMC"),
    ("vehicles",   "images", "Véhicules"),
    ("screenplay", "",       "Scénario"),
    ("storyboard", "",       "Storyboard"),
]


def sync_project_to_davinci() -> tuple[int, int]:
    """
    Importe tous les fichiers médias du projet courant dans les bins DaVinci correspondants.
    Retourne (fichiers_importés, erreurs).
    Silencieux si DaVinci n'est pas connecté ou sans projet ouvert.
    """
    if not resolve.is_connected():
        return 0, 0
    from core.context import get_data_root
    data_root = get_data_root()
    if not os.path.isdir(data_root):
        return 0, 0

    imported = 0
    errors = 0
    from core import project_layout as _pl
    for key, extra, bin_name in _PROJECT_BINS:
        folder = _pl.dir(key, data_root)
        if extra:
            folder = os.path.join(folder, extra)
        if not os.path.isdir(folder):
            continue
        for fname in os.listdir(folder):
            ext = os.path.splitext(fname)[1].lower()
            if ext not in _IMAGE_EXTS and ext not in _VIDEO_EXTS:
                continue
            fpath = os.path.join(folder, fname)
            try:
                ok = resolve.import_media_to_bin(fpath, bin_name)
                if ok:
                    imported += 1
                else:
                    errors += 1
            except Exception:
                errors += 1
    return imported, errors


def import_image_to_bin(image_path: str, sub_bin: str) -> bool:
    """
    Importe une image locale dans PANDORA > sub_bin du Media Pool DaVinci.
    Crée le bin PANDORA et le sous-bin si nécessaire.
    Retourne False silencieusement si DaVinci n'est pas connecté.
    """
    if not os.path.isfile(image_path):
        return False
    if not resolve.is_connected():
        return False
    return resolve.import_media_to_bin(image_path, sub_bin)


def import_to_media_pool(file_path: str) -> bool:
    """Importe un fichier local dans le Media Pool du projet DaVinci courant."""
    return resolve.import_media(file_path)


def import_audio_to_bin(audio_path: str) -> bool:
    """
    Importe une piste audio (.wav, .mp3, …) dans le bin PANDORA du Media Pool.
    Retourne False silencieusement si DaVinci n'est pas connecté.
    """
    if not audio_path or not os.path.isfile(audio_path):
        return False
    ext = os.path.splitext(audio_path)[1].lower()
    if ext not in _AUDIO_EXTS:
        return False
    if not resolve.is_connected():
        return False
    return resolve.import_media_to_bin(audio_path, "")


def import_result(result: dict, dest_dir: str, shot_title: str = "",
                  filename: str | None = None,
                  import_to_davinci: bool = True, shot: dict | None = None) -> dict:
    """
    Télécharge le clip généré et l'importe optionnellement dans DaVinci
    (appel bloquant : préférer import_clip_async depuis l'interface).

    Retourne :
        {"success": bool, "local_path": str, "mock": bool, "error": str,
         "davinci_imported": bool, "davinci_error": str}
    """
    # Téléchargement local = core.download (partagé avec le Live)
    ir = download_result(result, dest_dir, shot_title=shot_title, filename=filename)
    ir.setdefault("davinci_error", "")
    if not ir["success"] or ir["mock"]:
        return ir

    # Import DaVinci — chutier PANDORA, sous-chutier de la séquence quand le
    # plan est connu ; l'erreur du pont est gardée (elle était avalée).
    if import_to_davinci and resolve.is_connected():
        from core.timeline_clips import import_meta
        sub_bin, meta, color = import_meta(shot, ir["local_path"])
        ok, err = resolve.import_clip(ir["local_path"], sub_bin, meta, color)
        ir["davinci_imported"] = ok
        ir["davinci_error"] = err
    return ir


def import_clip_async(path: str, shot: dict | None = None, on_done=None):
    """Importe `path` dans DaVinci SANS bloquer l'interface.
    on_done(ok: bool, erreur: str, sous_chutier: str) est appelé sur le thread de
    l'interface. Rangement : PANDORA/SQnn, métadonnées scène / plan / prise /
    action, couleur de la séquence (core.timeline_clips)."""
    from core.timeline_clips import import_meta
    from davinci.jobs import run_job, notify
    sub_bin, meta, color = import_meta(shot, path)

    def work():
        if not resolve.is_connected():
            return {"ok": False, "error": resolve.explain().split("\n")[0]}
        ok, err = resolve.import_clip(path, sub_bin, meta, color)
        return {"ok": ok, "error": err}

    def finished(res):
        notify()
        if on_done is not None:
            res = res if isinstance(res, dict) else {}
            on_done(bool(res.get("ok")), str(res.get("error") or ""), sub_bin)

    return run_job(work, finished)
