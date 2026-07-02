import os
from datetime import datetime

from davinci.bridge import resolve
# Téléchargement local = module neutre partagé (le Live l'utilise SANS passer
# par ce fichier, pour ne pas tirer davinci.bridge dans son graphe d'import).
from core.download import download_video, download_result, is_mock_url  # noqa: F401

_IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tiff", ".tif"}
_VIDEO_EXTS = {".mp4", ".mov", ".mxf", ".avi", ".mkv"}
_AUDIO_EXTS = {".wav", ".mp3", ".aac", ".m4a", ".ogg"}

# (data subfolder, DaVinci bin name)
_PROJECT_BINS = [
    ("castings/images",   "Castings"),
    ("decors/images",     "Décors"),
    ("accessories/images","Accessoires"),
    ("hmc/images",        "HMC"),
    ("vehicles/images",   "Véhicules"),
    ("scenarios",         "Scénario"),
    ("storyboard",        "Storyboard"),
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
    for subfolder, bin_name in _PROJECT_BINS:
        folder = os.path.join(data_root, subfolder)
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
                  import_to_davinci: bool = True) -> dict:
    """
    Télécharge le clip généré et l'importe optionnellement dans DaVinci.

    Retourne :
        {"success": bool, "local_path": str, "mock": bool, "error": str, "davinci_imported": bool}
    """
    # Téléchargement local = core.download (partagé avec le Live)
    ir = download_result(result, dest_dir, shot_title=shot_title, filename=filename)
    if not ir["success"] or ir["mock"]:
        return ir

    # Import DaVinci — directement dans le bin PANDORA (sans sous-dossier)
    if import_to_davinci and resolve.is_connected():
        ir["davinci_imported"] = resolve.import_media_to_bin(ir["local_path"], "")

    return ir
