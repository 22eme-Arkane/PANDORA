"""
core/download.py — Téléchargement local des clips générés (module NEUTRE).

Aucune dépendance DaVinci ni UI : les fichiers *_live doivent pouvoir
télécharger un résultat de génération SANS tirer le pont DaVinci dans leur
graphe d'import (séparation Cinéma/Live). davinci/importer.py délègue ici
puis ajoute, lui seul, l'import Media Pool côté Cinéma.
"""
import os
from datetime import datetime


def is_mock_url(url: str) -> bool:
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


def download_result(result: dict, dest_dir: str, shot_title: str = "",
                    filename: str | None = None) -> dict:
    """
    Télécharge le clip généré — SANS import DaVinci (davinci_imported=False).

    Même contrat de retour que davinci.importer.import_result :
        {"success": bool, "local_path": str, "mock": bool, "error": str,
         "davinci_imported": bool}
    """
    url = result.get("video_url", "")

    # Mode mock : pas de vrai fichier à télécharger
    if is_mock_url(url):
        return {"success": True, "local_path": "", "mock": True, "error": "",
                "davinci_imported": False}

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
        return {"success": False, "local_path": "", "mock": False, "error": str(e),
                "davinci_imported": False}

    return {"success": True, "local_path": local_path, "mock": False,
            "davinci_imported": False, "error": ""}
