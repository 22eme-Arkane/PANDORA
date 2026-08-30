"""core/voice_auditions.py — Cache des extraits de voix (« écouter avant de choisir »).

fal.ai **n'expose aucun extrait pré-enregistré** : il n'existe ni endpoint
`/voices`, ni URL de démo par voix (vérifié le 2026-08-19 sur l'API et sur les
schémas OpenAPI). Un bouton « Écouter » ne peut donc pas se contenter de lire
un fichier distant : il faut faire dire une phrase à la voix, une fois.

D'où ce cache. Une voix auditionnée l'est **définitivement** et pour **tous les
projets** : le fichier vit dans le dossier global PANDORA, pas dans le projet
courant. Réécouter ne coûte plus rien, et c'est ce qui rend le bouton
utilisable sur les 113 voix d'Inworld sans y laisser un budget.

La phrase est FIXE et FRANÇAISE, à dessein : comparer deux voix n'a de sens que
sur le même texte, et c'est le français qu'il s'agit de juger.
"""

from __future__ import annotations

import hashlib
import os
import re

from core.pandora_dirs import get_bin_dir

# ~80 caractères. Contient des nasales (bonjour, avant), des accents aigus et
# graves, et une liaison — les trois endroits où une voix anglophone se trahit.
AUDITION_TEXT_FR = (
    "Bonjour. Voici ma voix : écoutez le grain, le rythme et l'accent "
    "avant de choisir."
)

# Version de la phrase : la changer invalide proprement tous les caches, sans
# avoir à les supprimer à la main (les anciens fichiers portent l'ancien nom).
_TEXT_TAG = hashlib.sha1(AUDITION_TEXT_FR.encode("utf-8")).hexdigest()[:6]

_SAFE = re.compile(r"[^A-Za-z0-9]+")


def cache_dir() -> str:
    """Dossier global des extraits — partagé par tous les projets.

    Créé à la demande, comme « doublage_audio » ou « music » : on n'ajoute pas
    d'entrée à SUBFOLDERS, pour ne pas créer chez tout le monde un dossier que
    seuls les utilisateurs du bouton « Écouter » rempliront.
    """
    return get_bin_dir("extraits_voix")


def _slug(s: str) -> str:
    """Nom de fichier lisible. Les voix portent des espaces, des parenthèses et
    des accents (« Hélène (fr) ») : on translittère grossièrement et on ajoute
    une empreinte, pour que deux voix distinctes ne se réduisent jamais au même
    fichier."""
    base = _SAFE.sub("-", s).strip("-").lower() or "voix"
    return f"{base[:40]}-{hashlib.sha1(s.encode('utf-8')).hexdigest()[:6]}"


def audition_path(engine: str, voice: str) -> str:
    """Chemin du fichier d'extrait pour un couple moteur/voix."""
    return os.path.join(cache_dir(),
                        f"{_slug(engine)}__{_slug(voice)}__{_TEXT_TAG}.mp3")


def is_cached(engine: str, voice: str) -> bool:
    """Vrai si l'extrait existe déjà — donc si le réécouter est gratuit.
    Un fichier vide compte comme absent : une génération interrompue ne doit
    pas se faire passer pour un extrait valable."""
    p = audition_path(engine, voice)
    try:
        return os.path.isfile(p) and os.path.getsize(p) > 0
    except OSError:
        return False


def cached_count() -> int:
    try:
        return sum(1 for f in os.listdir(cache_dir()) if f.endswith(".mp3"))
    except OSError:
        return 0


def clear_cache() -> int:
    """Supprime les extraits et renvoie le nombre de fichiers retirés.
    Ne touche QUE le dossier des extraits, jamais un rendu de projet."""
    n = 0
    d = cache_dir()
    for f in os.listdir(d):
        if f.endswith(".mp3"):
            try:
                os.remove(os.path.join(d, f))
                n += 1
            except OSError:
                pass
    return n
