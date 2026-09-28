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


def _target_name(dest_dir: str, shot_title: str, filename: str | None, mode: str) -> str:
    """Nom du clip rangé : « <plan>_NN.mp4 » (numéro suivant), sinon horodaté."""
    os.makedirs(dest_dir, exist_ok=True)
    if filename:
        return filename
    if shot_title:
        import glob
        existing = [
            f for f in glob.glob(os.path.join(dest_dir, f"{shot_title}_*.mp4"))
            if not f.endswith(".lb.mp4")
        ]
        return f"{shot_title}_{len(existing) + 1:02d}.mp4"
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"seedance_{mode}_{ts}.mp4"


def download_result(result: dict, dest_dir: str, shot_title: str = "",
                    filename: str | None = None) -> dict:
    """
    Télécharge le clip généré — SANS import DaVinci (davinci_imported=False).

    Un résultat peut aussi être un FICHIER LOCAL déjà produit (`local_file` :
    recomposition ffmpeg de « Changer le décor », 28/09/2026) : il est alors
    déplacé et nommé exactement comme un clip téléchargé. Sans cette branche,
    son `video_url` vide le faisait passer pour une simulation.

    Même contrat de retour que davinci.importer.import_result :
        {"success": bool, "local_path": str, "mock": bool, "error": str,
         "davinci_imported": bool}
    """
    mode = result.get("mode", "clip")
    local_src = str(result.get("local_file") or "")
    if local_src and os.path.isfile(local_src):
        try:
            import shutil
            dest = os.path.join(dest_dir, _target_name(dest_dir, shot_title, filename, mode))
            shutil.move(local_src, dest)
        except Exception as e:
            return {"success": False, "local_path": "", "mock": False, "error": str(e),
                    "davinci_imported": False}
        return {"success": True, "local_path": dest, "mock": False,
                "davinci_imported": False, "error": ""}

    url = result.get("video_url", "")

    # Mode mock : pas de vrai fichier à télécharger
    if is_mock_url(url):
        return {"success": True, "local_path": "", "mock": True, "error": "",
                "davinci_imported": False}

    try:
        name = _target_name(dest_dir, shot_title, filename, mode)
        local_path = download_video(url, dest_dir, name)
    except Exception as e:
        return {"success": False, "local_path": "", "mock": False, "error": str(e),
                "davinci_imported": False}

    return {"success": True, "local_path": local_path, "mock": False,
            "davinci_imported": False, "error": ""}
