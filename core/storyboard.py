import json
import os
import uuid
from datetime import datetime

from core.paths import APP_ROOT as _ROOT
_FALLBACK_SB_DIR = os.path.join(_ROOT, "data", "storyboard")


# Namespace du storyboard : permet à PANDORA | Live de réutiliser la même page
# Storyboard avec des données séparées (live_seq_live / live_seq_mapping) sans
# toucher au comportement Cinéma (défaut "storyboard").
_NAMESPACE = "storyboard"

def set_namespace(ns: str):
    global _NAMESPACE
    _NAMESPACE = ns or "storyboard"

def get_namespace() -> str:
    return _NAMESPACE

def _sb_dir() -> str:
    from core.context import get_data_root
    return os.path.join(get_data_root(), _NAMESPACE)

DEFAULT_VERSION_ID = "default"

CAMERA_MOVEMENTS = [
    "Fixe",
    "Panoramique horizontal",
    "Panoramique vertical",
    "Travelling avant",
    "Travelling arrière",
    "Travelling latéral",
    "Zoom avant",
    "Zoom arrière",
    "Steadicam",
    "Grue / Drone",
    "Caméra portée",
    "Plongée",
    "Contre-plongée",
]

OPTICS = [
    "Sphérique",
    "Anamorphique",
]

HEURE_PRESETS = ["Jour", "Nuit", "Lever du soleil", "Coucher du soleil"]

FOCALS = [
    "14mm",
    "18mm",
    "24mm",
    "28mm",
    "35mm",
    "40mm",
    "50mm",
    "65mm",
    "75mm",
    "85mm",
    "100mm",
    "135mm",
    "Autre",
]

# Distance sujet-caméra (métrique)
DISTANCES = [
    "",
    "0.3m",
    "0.5m",
    "0.7m",
    "1m",
    "1.2m",
    "1.5m",
    "2m",
    "2.5m",
    "3m",
    "4m",
    "5m",
    "6m",
    "7m",
    "8m",
    "10m",
    "12m",
    "15m",
    "20m",
    "30m",
    "50m",
    "100m",
]

# Valeurs de plan (shot sizes) — notation cinéma standard
SHOT_SIZES = [
    "GP",    # Gros Plan
    "GM",    # Grand Médium
    "PM",    # Plan Moyen
    "PP",    # Plan Poitrine
    "PL",    # Plan Large
    "PE",    # Plan d'Ensemble
    "PTG",   # Plan Très Général
    "Insert",
    "",
]

SHOT_SIZE_LABELS = {
    "GP":     "GP — Gros Plan",
    "GM":     "GM — Grand Médium",
    "PM":     "PM — Plan Moyen",
    "PP":     "PP — Plan Poitrine",
    "PL":     "PL — Plan Large",
    "PE":     "PE — Plan d'Ensemble",
    "PTG":    "PTG — Plan Très Général",
    "Insert": "Insert",
    "":       "—",
}

SPEEDS = [
    "Normale",
    "Ralenti",
    "Accéléré",
]


def _ensure():
    os.makedirs(_sb_dir(), exist_ok=True)


def _load_index() -> list[dict]:
    _ensure()
    index_file = os.path.join(_sb_dir(), "index.json")
    if not os.path.exists(index_file):
        return []
    with open(index_file, "r", encoding="utf-8") as f:
        return json.load(f)


def _save_index(index: list[dict]):
    _ensure()
    index_sorted = sorted(
        index,
        key=lambda s: (s.get("version_id", DEFAULT_VERSION_ID), s.get("number", 0)),
    )
    with open(os.path.join(_sb_dir(), "index.json"), "w", encoding="utf-8") as f:
        json.dump(index_sorted, f, ensure_ascii=False, indent=2)


# ── Version management ──────────────────────────────────────────────────────

def _load_versions() -> list[dict]:
    _ensure()
    versions_file = os.path.join(_sb_dir(), "versions.json")
    if not os.path.exists(versions_file):
        return []
    with open(versions_file, "r", encoding="utf-8") as f:
        return json.load(f)


def _save_versions(versions: list[dict]):
    _ensure()
    with open(os.path.join(_sb_dir(), "versions.json"), "w", encoding="utf-8") as f:
        json.dump(versions, f, ensure_ascii=False, indent=2)


def list_versions() -> list[dict]:
    """Returns versions for the current project. Prunes empty auto-created placeholders."""
    from core.context import get_project_id
    pid = get_project_id()
    all_versions = _load_versions()

    versions = [v for v in all_versions if v.get("project_id") == pid] if pid else all_versions

    index = _load_index()
    for v in versions:
        v["shot_count"] = sum(
            1 for s in index
            if s.get("version_id") == v["id"] and (not pid or s.get("project_id") == pid)
        )

    # Supprimer les versions vides auto-créées ("Storyboard principal" sans plans)
    # — jamais si c'est la seule version restante (évite de tout perdre)
    to_prune = [v for v in versions if v.get("name") == "Storyboard principal" and v["shot_count"] == 0]
    if to_prune and len(versions) > len(to_prune):
        prune_ids = {v["id"] for v in to_prune}
        cleaned = [v for v in all_versions if v.get("id") not in prune_ids]
        _save_versions(cleaned)
        versions = [v for v in versions if v.get("id") not in prune_ids]

    return versions


def create_version(name: str) -> dict:
    from core.context import get_project_id
    versions = _load_versions()
    v = {
        "id": str(uuid.uuid4()),
        "name": name,
        "created_at": datetime.now().isoformat(),
    }
    pid = get_project_id()
    if pid:
        v["project_id"] = pid
    versions.append(v)
    _save_versions(versions)
    return v


def delete_version(version_id: str):
    versions = _load_versions()
    versions = [v for v in versions if v.get("id") != version_id]
    _save_versions(versions)
    index = _load_index()
    index = [s for s in index if s.get("version_id", DEFAULT_VERSION_ID) != version_id]
    _save_index(index)
    # list_versions() will auto-create a fresh default on next call if none remain


def clear_version_shots(version_id: str = DEFAULT_VERSION_ID):
    """Supprime tous les plans d'une version sans supprimer la version elle-même."""
    from core.context import get_project_id
    pid = get_project_id()
    index = _load_index()
    index = [
        s for s in index
        if not (
            s.get("version_id", DEFAULT_VERSION_ID) == version_id
            and (not pid or s.get("project_id") == pid)
        )
    ]
    _save_index(index)


# ── Snapshot management ─────────────────────────────────────────────────────
# Snapshots = named, timestamped copies of a storyboard version's shots.
# Independent from "workspace" versions — each workspace can have many snapshots.

def _load_snapshots() -> list[dict]:
    _ensure()
    f = os.path.join(_sb_dir(), "snapshots.json")
    if not os.path.exists(f):
        return []
    with open(f, "r", encoding="utf-8") as fp:
        return json.load(fp)


def _save_snapshots(data: list[dict]):
    _ensure()
    with open(os.path.join(_sb_dir(), "snapshots.json"), "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def list_snapshots(version_id: str = DEFAULT_VERSION_ID) -> list[dict]:
    from core.context import get_project_id
    pid = get_project_id()
    return [
        s for s in _load_snapshots()
        if s.get("version_id") == version_id
        and (not pid or s.get("project_id") == pid)
    ]


def save_snapshot(name: str, version_id: str = DEFAULT_VERSION_ID) -> dict:
    import copy
    from core.context import get_project_id
    pid = get_project_id()
    shots = list_shots(version_id)
    all_snaps = _load_snapshots()
    existing = list_snapshots(version_id)
    num = (existing[-1]["num"] + 1) if existing else 1
    snap = {
        "id":         str(uuid.uuid4()),
        "num":        num,
        "name":       name,
        "version_id": version_id,
        "saved_at":   datetime.now().isoformat(),
        "shots":      copy.deepcopy(shots),
    }
    if pid:
        snap["project_id"] = pid
    all_snaps.append(snap)
    _save_snapshots(all_snaps)
    return snap


def restore_snapshot(snapshot_id: str, version_id: str = DEFAULT_VERSION_ID):
    """Replace all shots of version_id with the snapshot's saved shots."""
    from core.context import get_project_id
    pid = get_project_id()
    all_snaps = _load_snapshots()
    snap = next((s for s in all_snaps if s["id"] == snapshot_id), None)
    if not snap:
        return
    index = _load_index()
    index = [
        s for s in index
        if not (
            s.get("version_id", DEFAULT_VERSION_ID) == version_id
            and (not pid or s.get("project_id") == pid)
        )
    ]
    for shot in snap["shots"]:
        shot = dict(shot)
        shot["version_id"] = version_id
        if pid:
            shot["project_id"] = pid
        index.append(shot)
    _save_index(index)


def delete_snapshot(snapshot_id: str):
    all_snaps = _load_snapshots()
    all_snaps = [s for s in all_snaps if s["id"] != snapshot_id]
    _save_snapshots(all_snaps)


# ── Shot management ─────────────────────────────────────────────────────────

def list_shots(version_id: str | None = None) -> list[dict]:
    """If version_id is None, returns all shots for the current project."""
    from core.context import get_project_id
    pid = get_project_id()
    index = _load_index()
    if pid:
        index = [s for s in index if s.get("project_id") == pid]
    if version_id is None:
        return index
    return [s for s in index if s.get("version_id", DEFAULT_VERSION_ID) == version_id]


def get_shot(shot_id: str) -> dict | None:
    index = _load_index()
    for shot in index:
        if shot.get("id") == shot_id:
            return shot
    return None


def save_shot(data: dict, version_id: str = DEFAULT_VERSION_ID) -> dict:
    from core.context import get_project_id
    _ensure()
    pid = get_project_id()
    if pid and not data.get("project_id"):
        data["project_id"] = pid
    index = _load_index()
    now = datetime.now().isoformat()

    duration = data.get("duration", 5.0)
    try:
        duration = float(duration)
    except (TypeError, ValueError):
        duration = 5.0
    data["duration"] = min(duration, 15.0)

    if not data.get("id"):
        data["id"] = str(uuid.uuid4())
        data["created_at"] = now
        data["updated_at"] = now
        data.setdefault("version_id", version_id)
        vid = data["version_id"]
        version_shots = [s for s in index if s.get("version_id", DEFAULT_VERSION_ID) == vid]
        data.setdefault("number", len(version_shots) + 1)
        data.setdefault("scenario_id", "")
        data.setdefault("scene_title", "")
        data.setdefault("decor_id", "")
        data.setdefault("decor_name", "")
        data.setdefault("character_ids", [])
        data.setdefault("character_names", [])
        data.setdefault("accessory_ids", [])
        data.setdefault("accessory_names", [])
        data.setdefault("vehicle_ids", [])
        data.setdefault("vehicle_names", [])
        data.setdefault("camera_movement", "Fixe")
        data.setdefault("shot_size", "")
        data.setdefault("camera_axis", "")
        data.setdefault("camera_distance", "")
        data.setdefault("speed", "Normale")
        data.setdefault("optic", "Sphérique")
        data.setdefault("focal", "35mm")
        data.setdefault("seq_num", 1)
        data.setdefault("seq_name", "")
        if not data.get("shot_in_seq"):
            _seq = data.get("seq_num", 1)
            same_seq = [s for s in index
                        if s.get("version_id", DEFAULT_VERSION_ID) == vid
                        and s.get("seq_num") == _seq]
            data["shot_in_seq"] = len(same_seq) + 1
        data.setdefault("comments", "")
        data.setdefault("shot_time", "")
        data.setdefault("image_path", "")
        data.setdefault("seedance_prompt", "")
        data.setdefault("sound_prompt", "")
        data.setdefault("dialogue_lang", "en")   # langue des dialogues (envoi Seedance)
        data.setdefault("last_frame_path", "")
        index.append(data)
    else:
        data["updated_at"] = now
        replaced = False
        for i, shot in enumerate(index):
            if shot.get("id") == data["id"]:
                if "version_id" not in data:
                    data["version_id"] = shot.get("version_id", DEFAULT_VERSION_ID)
                index[i] = data
                replaced = True
                break
        if not replaced:
            data.setdefault("created_at", now)
            data.setdefault("version_id", version_id)
            vid = data["version_id"]
            version_shots = [s for s in index if s.get("version_id", DEFAULT_VERSION_ID) == vid]
            data.setdefault("number", len(version_shots) + 1)
            index.append(data)

    _save_index(index)
    return data


def reorder_shots(version_id: str, ordered_ids: list[str]):
    """Reassigns `number` and `shot_in_seq` to all shots of a version per the given order."""
    index = _load_index()
    by_id = {s["id"]: s for s in index if s.get("version_id", DEFAULT_VERSION_ID) == version_id}
    seq_counters: dict = {}
    for pos, sid in enumerate(ordered_ids):
        if sid in by_id:
            shot = by_id[sid]
            shot["number"] = pos + 1
            seq = shot.get("seq_num", 1)
            seq_counters[seq] = seq_counters.get(seq, 0) + 1
            shot["shot_in_seq"] = seq_counters[seq]
    _save_index(index)


def delete_shot(shot_id: str):
    index = _load_index()
    index = [s for s in index if s.get("id") != shot_id]
    _save_index(index)


def duplicate_shot(shot_id: str) -> dict | None:
    """Duplique un plan : copie profonde insérée JUSTE APRÈS l'original, nouvel id,
    titre suffixé « (copie) ». Renumérote la version. Renvoie le nouveau plan (ou None)."""
    import copy
    index = _load_index()
    src = next((s for s in index if s.get("id") == shot_id), None)
    if not src:
        return None
    now = datetime.now().isoformat()
    dup = copy.deepcopy(src)
    dup["id"]         = str(uuid.uuid4())
    dup["created_at"] = now
    dup["updated_at"] = now
    if dup.get("scene_title"):
        dup["scene_title"] = f"{dup['scene_title']} (copie)"
    pos = index.index(src)
    index.insert(pos + 1, dup)
    _save_index(index)
    # Renumérote la version pour une numérotation contiguë (la copie suit l'original).
    vid = src.get("version_id", DEFAULT_VERSION_ID)
    ordered = [s["id"] for s in index if s.get("version_id", DEFAULT_VERSION_ID) == vid]
    reorder_shots(vid, ordered)
    return dup


# ── Column order ──────────────────────────────────────────────────────────────

def load_col_order(n_cols: int, default: list | None = None) -> list:
    """Load column visual order from project config. Falls back to `default`
    (or the natural 0..n-1 order). A saved order is only accepted if it contains
    exactly the same set of indices as `default` — sinon on retombe sur le défaut
    (gère l'ajout d'une colonne : un ordre enregistré plus court est ignoré)."""
    _ensure()
    path = os.path.join(_sb_dir(), "col_order.json")
    if default is None:
        default = list(range(n_cols))
    if not os.path.exists(path):
        return list(default)
    try:
        with open(path, encoding="utf-8") as f:
            order = json.load(f)
        if isinstance(order, list) and sorted(order) == sorted(default):
            return order
    except Exception:
        pass
    return list(default)


def save_col_order(order: list) -> None:
    """Persist column visual order for the current project."""
    _ensure()
    path = os.path.join(_sb_dir(), "col_order.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(order, f)


# ── Aperçu storage ────────────────────────────────────────────────────────────

def get_apercu_dir(shot_id: str) -> str:
    return os.path.join(_sb_dir(), "apercus", shot_id)


def load_apercus(shot_id: str) -> dict:
    """Returns {"paths": [...], "active_idx": 0}"""
    path = os.path.join(get_apercu_dir(shot_id), "apercus.json")
    if not os.path.exists(path):
        return {"paths": [], "active_idx": 0}
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {"paths": [], "active_idx": 0}


def save_apercus(shot_id: str, paths: list, active_idx: int) -> None:
    d = get_apercu_dir(shot_id)
    os.makedirs(d, exist_ok=True)
    with open(os.path.join(d, "apercus.json"), "w", encoding="utf-8") as f:
        json.dump({"paths": paths, "active_idx": active_idx}, f, indent=2)


# ── Sauvegarde / ouverture PHYSIQUE (fichiers nommés, dossier « Storyboard ») ───
# Déjà dans le dossier du projet → pas de sous-dossier projet.

def _saves_dir() -> str:
    from core.context import get_data_root
    d = os.path.join(get_data_root(), "Storyboard")
    os.makedirs(d, exist_ok=True)
    return d


def _safe_name(name: str) -> str:
    s = "".join(c for c in (name or "") if c.isalnum() or c in " -_").strip()
    return s[:80] or "storyboard"


def list_saved() -> list[str]:
    """Noms des storyboards sauvegardés (fichiers .json du dossier Storyboard)."""
    try:
        return sorted(f[:-5] for f in os.listdir(_saves_dir()) if f.endswith(".json"))
    except Exception:
        return []


def export_storyboard(name: str, version_id: str = DEFAULT_VERSION_ID) -> str:
    """Sauvegarde physique des plans (version courante) sous
    <projet>/data/Storyboard/<nom>.json."""
    shots = [{k: v for k, v in s.items() if not k.startswith("_")}
             for s in list_shots(version_id)]
    payload = {
        "saved_name": name,
        "saved_at": datetime.now().isoformat(timespec="seconds"),
        "shots": shots,
    }
    path = os.path.join(_saves_dir(), _safe_name(name) + ".json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    return path


def import_storyboard(name: str, version_id: str = DEFAULT_VERSION_ID) -> int:
    """Recharge un storyboard sauvegardé : REMPLACE les plans de la version
    courante du projet. Retourne le nombre de plans importés."""
    from core.context import get_project_id
    path = os.path.join(_saves_dir(), _safe_name(name) + ".json")
    if not os.path.isfile(path):
        return 0
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    shots = data.get("shots", []) or []
    pid = get_project_id()
    index = _load_index()
    # Retire les plans de cette version (pour ce projet)
    index = [s for s in index if not (
        s.get("version_id", DEFAULT_VERSION_ID) == version_id
        and (not pid or s.get("project_id") == pid))]
    for s in shots:
        s = dict(s)
        s["version_id"] = version_id
        if pid:
            s["project_id"] = pid
        if not s.get("id"):
            s["id"] = str(uuid.uuid4())
        index.append(s)
    _save_index(index)
    return len(shots)


def saves_dir() -> str:
    """Dossier par défaut des storyboards sauvegardés (pour la boîte de dialogue)."""
    return _saves_dir()


def export_storyboard_to(path: str, version_id: str = DEFAULT_VERSION_ID) -> str:
    """Sauvegarde les plans (version courante) vers un fichier CHOISI par
    l'utilisateur (boîte de dialogue Windows). Chargeable depuis tout projet."""
    shots = [{k: v for k, v in s.items() if not k.startswith("_")}
             for s in list_shots(version_id)]
    payload = {
        "saved_name": os.path.splitext(os.path.basename(path))[0],
        "saved_at": datetime.now().isoformat(timespec="seconds"),
        "shots": shots,
    }
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    return path


def import_storyboard_from(path: str, version_id: str = DEFAULT_VERSION_ID) -> int:
    """Recharge un storyboard depuis un fichier CHOISI : REMPLACE les plans de la
    version courante. Retourne le nombre de plans importés."""
    from core.context import get_project_id
    if not path or not os.path.isfile(path):
        return 0
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    shots = data.get("shots", []) or []
    pid = get_project_id()
    index = _load_index()
    index = [s for s in index if not (
        s.get("version_id", DEFAULT_VERSION_ID) == version_id
        and (not pid or s.get("project_id") == pid))]
    for s in shots:
        s = dict(s)
        s["version_id"] = version_id
        if pid:
            s["project_id"] = pid
        if not s.get("id"):
            s["id"] = str(uuid.uuid4())
        index.append(s)
    _save_index(index)
    return len(shots)
