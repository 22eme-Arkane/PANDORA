"""
Structure de dossiers PANDORA — racine + sous-dossiers par onglet.

{output_dir}/PANDORA/{nom_onglet}/

Le parent `output_dir` est lu depuis config.json.
Par défaut : ~/Videos/PANDORA/
"""
import os

# (clé interne, nom du dossier / bin DaVinci)
SUBFOLDERS = [
    ("castings",    "Castings"),
    ("scenario",    "Scénario"),
    ("storyboard",  "Storyboard"),
    ("decors",      "Décors"),
    ("hmc",         "HMC"),
    ("accessoires", "Accessoires"),
    ("vehicles",    "Véhicules"),
    ("seedance",    "Seedance 2.0"),
]

_KEY_TO_NAME = dict(SUBFOLDERS)
BIN_NAMES    = [name for _, name in SUBFOLDERS]


def get_pandora_root(cfg: dict | None = None) -> str:
    """Retourne le chemin absolu de PANDORA/ (ne crée pas le dossier)."""
    from core.config import load_config
    if cfg is None:
        cfg = load_config()
    parent = cfg.get("output_dir", "").strip()
    if not parent:
        parent = os.path.join(os.path.expanduser("~"), "Videos")
    return os.path.join(parent, "PANDORA")


def get_bin_dir(key: str, cfg: dict | None = None) -> str:
    """Retourne (et crée si besoin) le sous-dossier PANDORA pour la clé donnée."""
    name = _KEY_TO_NAME.get(key, key)
    path = os.path.join(get_pandora_root(cfg), name)
    os.makedirs(path, exist_ok=True)
    return path


def create_all_dirs(cfg: dict | None = None) -> str:
    """Crée PANDORA/ et tous ses sous-dossiers. Retourne le chemin PANDORA/."""
    root = get_pandora_root(cfg)
    os.makedirs(root, exist_ok=True)
    for _, name in SUBFOLDERS:
        os.makedirs(os.path.join(root, name), exist_ok=True)
    return root
