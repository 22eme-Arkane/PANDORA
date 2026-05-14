import os
from datetime import datetime

from davinci.bridge import resolve

_IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tiff", ".tif"}
_VIDEO_EXTS = {".mp4", ".mov", ".mxf", ".avi", ".mkv"}

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


def _is_mock_url(url: str) -> bool:
    return not url or "mock" in url or not url.startswith("http")


def download_video(url: str, dest_dir: str, filename: str | None = None) -> str:
    """Télécharge une vidéo depuis url vers dest_dir. Retourne le chemin local."""
    import requests
    os.makedirs(dest_dir, exist_ok=True)
    if filename is None:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"seedance_{ts}.mp4"
    dest = os.path.join(dest_dir, filename)
    r = requests.get(url, stream=True, timeout=120)
    r.raise_for_status()
    with open(dest, "wb") as f:
        for chunk in r.iter_content(chunk_size=65536):
            f.write(chunk)
    return dest


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


def import_result(result: dict, dest_dir: str, shot_title: str = "",
                  filename: str | None = None,
                  import_to_davinci: bool = True) -> dict:
    """
    Télécharge le clip généré et l'importe optionnellement dans DaVinci.

    Retourne :
        {"success": bool, "local_path": str, "mock": bool, "error": str, "davinci_imported": bool}
    """
    url = result.get("video_url", "")

    # Mode mock : pas de vrai fichier à télécharger
    if _is_mock_url(url):
        return {"success": True, "local_path": "", "mock": True, "error": ""}

    try:
        mode = result.get("mode", "clip")
        if filename:
            os.makedirs(dest_dir, exist_ok=True)
            name = filename
        elif shot_title:
            os.makedirs(dest_dir, exist_ok=True)
            import glob
            existing = [
                f for f in glob.glob(os.path.join(dest_dir, f"{shot_title}_*.mp4"))
                if not f.endswith(".lb.mp4")
            ]
            gen_idx = len(existing) + 1
            name = f"{shot_title}_{gen_idx:02d}.mp4"
        else:
            ts   = datetime.now().strftime("%Y%m%d_%H%M%S")
            name = f"seedance_{mode}_{ts}.mp4"
        local_path = download_video(url, dest_dir, name)
    except Exception as e:
        return {"success": False, "local_path": "", "mock": False, "error": str(e)}

    # Import DaVinci — uniquement si demandé et connecté
    ok = False
    if import_to_davinci and resolve.is_connected():
        ok = import_to_media_pool(local_path)

    return {"success": True, "local_path": local_path, "mock": False,
            "davinci_imported": ok, "error": ""}
