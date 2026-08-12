"""
core/projects_location.py — Emplacement des projets PANDORA (disque externe, NAS…).

POURQUOI CE MODULE
------------------
L'emplacement était déjà choisissable, mais UNIQUEMENT dans la fenêtre
« Nouveau projet » : une fois le premier projet créé, plus personne ne savait
où le changer. Ce module en fait un réglage nommé, lisible depuis les
Paramètres des DEUX éditions (Cinéma et Live).

CE QUE LE RÉGLAGE FAIT — et ce qu'il ne fait PAS
------------------------------------------------
Il pilote la clé `last_project_location` de config.json, qui sert à deux
choses et deux seulement :
  1. le dossier PRÉ-REMPLI dans « Nouveau projet » → les projets suivants
     naissent là ;
  2. l'un des dossiers RESCANNÉS au démarrage → les projets qui s'y trouvent
     réapparaissent seuls dans la liste des récents.

Il ne DÉPLACE aucun projet existant : un projet est un dossier autonome, on le
déplace avec l'explorateur de fichiers, puis « Ouvrir un projet » une fois.

TRAVAIL SUR DEUX MACHINES (station de montage + portable)
---------------------------------------------------------
config.json est LOCAL à chaque machine. C'est un avantage ici : si le disque
externe est E: sur la station et F: sur le portable, chaque machine garde son
propre chemin vers le MÊME disque, et rien ne casse. Les projets, eux, sont
autonomes et se lisent des deux côtés.

Emplacement UNIQUE pour les deux éditions : un projet porte son mode
("cinema"/"live") dans son propre fichier, et la page de démarrage filtre
là-dessus. Deux dossiers séparés n'apporteraient rien et obligeraient à régler
la même chose deux fois.
"""
import os


def default_root() -> str:
    """Dossier projets par défaut (~/Documents/PANDORA Projects)."""
    from core import project as _project
    return _project._DEFAULT_DIR


def get_projects_root(cfg: dict | None = None) -> str:
    """Dossier où naissent les nouveaux projets. Jamais vide."""
    if cfg is None:
        from core.config import load_config
        cfg = load_config()
    path = str(cfg.get("last_project_location") or "").strip()
    return path or default_root()


def is_default(path: str | None = None) -> bool:
    """True si l'emplacement est celui d'origine (aucun choix explicite)."""
    if path is None:
        path = get_projects_root()
    return os.path.normpath(path) == os.path.normpath(default_root())


def is_available(path: str | None = None) -> bool:
    """True si le dossier existe RÉELLEMENT maintenant.

    Sur un disque externe débranché, le chemin reste enregistré mais devient
    introuvable : l'interface doit le dire au lieu de laisser croire que les
    projets ont disparu.
    """
    if path is None:
        path = get_projects_root()
    try:
        return bool(path) and os.path.isdir(path)
    except OSError:
        return False


def set_projects_root(path: str) -> str:
    """Enregistre l'emplacement (lecture-modification-écriture de la config).

    ⚠ On relit TOUJOURS la config avant d'écrire : `save_config` remplace le
    fichier entier, donc écrire un dict partiel effacerait les clés API et les
    préférences IA. Retourne le chemin normalisé effectivement enregistré.
    """
    from core.config import load_config, save_config
    path = os.path.normpath(str(path or "").strip())
    if not path:
        return get_projects_root()
    cfg = load_config()
    cfg["last_project_location"] = path
    save_config(cfg)
    return path
