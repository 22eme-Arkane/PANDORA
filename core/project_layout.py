"""
core/project_layout.py — LA source de vérité de l'arborescence d'un projet.

Spec Matthieu 2026-07-30 : noms de dossiers en ANGLAIS standard cinéma,
préfixes numériques pour forcer l'ordre du flux de travail dans l'explorateur,
caches regroupés hors des données. Décision d'implémentation (cartographie
étape 0) : les CLÉS LOGIQUES internes (namespaces « storyboard »,
« live_seq_mapping », clés d'assets…) ne changent PAS — seul le dossier disque
change, via la table ci-dessous. C'est ce qui évite de toucher aux ~80
littéraux de namespace et à `_resolve_building_ref`.

Structure cible :

    <Projet>/data/
    ├── 01_writing/      screenplay(/saves), storyboard(/saves), staging(/saves)
    ├── 02_elements/     characters, sets, props, hmc, vehicles (+ saves/)
    ├── 03_production/   videos, music, dubbing, sound_design, upscaled
    ├── 04_live/         sequences_live, sequences_mapping, facade/,
    │                    characters, props, vehicles (assets Live)
    └── .cache/          thumbs_mid, transcode, mapping, decor_sync_frames

RÈGLE DE RÉSOLUTION (pattern éprouvé « Seedance » → « Studio IA »,
core/config.py) : `dir(key)` rend le NOUVEAU chemin si son dossier existe —
sinon le chemin LEGACY s'il existe — sinon le nouveau (qui sera créé au
premier makedirs). Un projet d'avant la migration continue donc de
fonctionner tel quel ; un projet migré (ou neuf) utilise la cible. La
MIGRATION (core/project_migrate.py) déplace physiquement legacy → nouveau et
réécrit les chemins absolus persistés dans les JSON — 449 occurrences
mesurées sur le seul Forcalquier : sans réécriture, un déplacement casserait
toutes les vignettes en silence.

⚠ Ne JAMAIS créer le nouveau dossier avant d'avoir testé le legacy : un
makedirs prématuré rend le dossier legacy invisible et « perd » les données
(piège documenté du renommage Studio IA).
"""

from __future__ import annotations

import os

# Version d'arborescence : 1 = historique (implicite, aucun marqueur),
# 2 = structure 01_writing…04_live. Écrite dans le descripteur projet
# ({safe}.json, champ « layout_version ») par la migration.
LAYOUT_VERSION = 2

# clé logique → (chemin relatif CIBLE, chemins relatifs LEGACY, par priorité).
# Les clés logiques sont les identifiants INTERNES existants (namespaces,
# clés d'assets, noms de modules) — elles ne changent jamais.
LAYOUT = {
    # ── 01_writing ───────────────────────────────────────────────────────────
    "screenplay":        ("01_writing/screenplay",          ("scenarios",)),
    "screenplay_saves":  ("01_writing/screenplay/saves",    ("Scénario",)),
    "storyboard":        ("01_writing/storyboard",          ("storyboard",)),
    # ⚠ « Storyboard » (saves) et « storyboard » (données) sont UN SEUL dossier
    # physique sur NTFS : le legacy des saves pointe donc sur le même dossier
    # que les données — la migration sépare les .json de sauvegarde vers saves/.
    "storyboard_saves":  ("01_writing/storyboard/saves",    ("Storyboard",)),
    "staging":           ("01_writing/staging",             ("staging",)),
    "staging_saves":     ("01_writing/staging/saves",       ("Mise en scène",)),
    "lighting_saves":    ("01_writing/staging/lighting_saves", ("Plan de feu",)),

    # ── 02_elements ──────────────────────────────────────────────────────────
    "castings":          ("02_elements/characters",         ("castings",)),
    "decors":            ("02_elements/sets",               ("decors",)),
    "accessories":       ("02_elements/props",              ("accessories",)),
    "hmc":               ("02_elements/hmc",                ("hmc",)),
    "vehicles":          ("02_elements/vehicles",           ("vehicles",)),
    # Sauvegardes portables des 5 familles (element_io) — DANS leur catégorie.
    "castings_saves":    ("02_elements/characters/saves",   ("Casting",)),
    "decors_saves":      ("02_elements/sets/saves",         ("Décors",)),
    "accessories_saves": ("02_elements/props/saves",        ("Accessoires",)),
    "hmc_saves":         ("02_elements/hmc/saves",          ("HMC",)),
    "vehicles_saves":    ("02_elements/vehicles/saves",     ("Véhicules",)),
    "elements_saves":    ("02_elements/saves",              ("Éléments",)),

    # ── 03_production ────────────────────────────────────────────────────────
    # Vidéos : DEUX legacy dans l'ordre historique (Studio IA, puis Seedance).
    "videos":            ("03_production/videos",           ("Studio IA", "Seedance")),
    "music":             ("03_production/music",            ("music",)),
    "dubbing":           ("03_production/dubbing",          ("doublage",)),
    "sound_design":      ("03_production/sound_design",     ("live_sound_design", "sound_design")),
    "upscaled":          ("03_production/upscaled",         ("upscaled",)),
    "draw_to_video":     ("03_production/draw_to_video",    ("draw_to_video",)),

    # ── 04_live ──────────────────────────────────────────────────────────────
    "live_seq_live":     ("04_live/sequences_live",         ("live_seq_live",)),
    "live_seq_mapping":  ("04_live/sequences_mapping",      ("live_seq_mapping",)),
    "facade":            ("04_live/facade",                 ()),
    "live_castings":     ("04_live/characters",             ("live_castings",)),
    "live_accessories":  ("04_live/props",                  ("live_accessories",)),
    "live_vehicles":     ("04_live/vehicles",               ("live_vehicles",)),
    "live_conducteur":   ("04_live/conducteur",             ("live_conducteur",)),

    # ── .cache (jamais dans une sauvegarde/export) ───────────────────────────
    "cache_thumbs":      (".cache/thumbs_mid",              (".thumbs_mid",)),
    "cache_transcode":   (".cache/transcode",               (".transcode",)),
    "cache_mapping":     (".cache/mapping",                 ("mapping",)),
    "cache_decor_sync":  (".cache/decor_sync",              ("decor_sync",)),
}

# Fichiers isolés de la racine de data/ → regroupés sous 04_live/facade/.
FACADE_FILES = {
    "live_building_ref.json": "04_live/facade/live_building_ref.json",
    "facade_desc.json":       "04_live/facade/facade_desc.json",
    "live_gen_mode.json":     "04_live/live_gen_mode.json",
    "facade_fond_noir.jpg":   "04_live/facade/facade_fond_noir.jpg",
    # Journal des dépenses du projet (fenêtre « Coût du projet », 2026-07-31).
    # Rangé à la racine de data/ : ce n'est ni de l'écriture, ni des éléments,
    # ni de la production — c'est un relevé qui porte sur le projet entier.
    "spend.json":             "spend.json",
}


def rel(key: str) -> str:
    """Chemin relatif CIBLE d'une clé logique (séparateurs de l'OS)."""
    return LAYOUT[key][0].replace("/", os.sep)


def dir(key: str, data_root: str = "") -> str:
    """Dossier ABSOLU résolu d'une clé logique, avec repli legacy.

    Nouveau chemin si son dossier EXISTE ; sinon premier legacy existant ;
    sinon le nouveau (destination des créations). Ne crée rien — les
    appelants gardent leurs makedirs, qui matérialisent la CIBLE pour tout
    projet neuf ou migré."""
    if not data_root:
        from core.context import get_data_root
        data_root = get_data_root()
    target_rel, legacy_rels = LAYOUT[key]
    target = os.path.join(data_root, target_rel.replace("/", os.sep))
    if os.path.isdir(target):
        return target
    for _l in legacy_rels:
        legacy = os.path.join(data_root, _l)
        if os.path.isdir(legacy):
            return legacy
    return target


def file(name: str, data_root: str = "") -> str:
    """Fichier isolé (FACADE_FILES) résolu : cible si elle existe, sinon
    l'emplacement legacy (racine de data/) s'il existe, sinon la cible."""
    if not data_root:
        from core.context import get_data_root
        data_root = get_data_root()
    target = os.path.join(data_root, FACADE_FILES[name].replace("/", os.sep))
    if os.path.isfile(target):
        return target
    legacy = os.path.join(data_root, name)
    if os.path.isfile(legacy):
        return legacy
    return target


def ensure_parent(path: str) -> str:
    """makedirs du dossier parent d'un fichier cible — pour les écritures."""
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
    except OSError:
        pass
    return path


def is_migrated(data_root: str = "") -> bool:
    """Un projet est « migré » si sa racine 01_writing existe (marqueur
    physique — le descripteur projet porte en plus layout_version)."""
    if not data_root:
        from core.context import get_data_root
        data_root = get_data_root()
    return os.path.isdir(os.path.join(data_root, "01_writing"))
