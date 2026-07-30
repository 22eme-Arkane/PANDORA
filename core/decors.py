import json
import os
import uuid
from datetime import datetime

from core.paths import APP_ROOT as _ROOT


def _dec_dir() -> str:
    # Arborescence 2026-07-30 : cible 02_elements/sets, repli legacy
    # « decors » pour les projets non migrés (core/project_layout).
    from core import project_layout as _pl
    return _pl.dir("decors")

CATEGORIES = [
    "Intérieur",
    "Extérieur",
    "Studio",
    "Urbain",
    "Rural",
    "Aquatique",
    "Aérien",
    "Fantastique",
    "Industriel",
    "Historique",
    "Autre",
]


def _ensure():
    os.makedirs(_dec_dir(), exist_ok=True)
    os.makedirs(os.path.join(_dec_dir(), "images"), exist_ok=True)


def images_dir() -> str:
    _ensure()
    return os.path.join(_dec_dir(), "images")


def _load_index() -> list[dict]:
    _ensure()
    index_file = os.path.join(_dec_dir(), "index.json")
    if not os.path.exists(index_file):
        return []
    with open(index_file, "r", encoding="utf-8") as f:
        return json.load(f)


def _save_index(index: list[dict]):
    _ensure()
    with open(os.path.join(_dec_dir(), "index.json"), "w", encoding="utf-8") as f:
        json.dump(index, f, ensure_ascii=False, indent=2)


def list_decors() -> list[dict]:
    from core.context import get_project_id
    pid = get_project_id()
    index = _load_index()
    if pid:
        return [d for d in index if d.get("project_id") == pid]
    return index


def group_by_room(decors: list[dict]) -> list[tuple]:
    """Regroupe les décors par pièce (`room_group`) en conservant l'ordre d'arrivée.
    Renvoie [(room_group, [décors]), …] ; les décors sans groupe sont réunis sous
    la clé "" (groupe « libre », affiché sans bandeau dans la page Décors)."""
    groups: dict[str, list] = {}
    order: list[str] = []
    for d in decors or []:
        g = d.get("room_group", "") or ""
        if g not in groups:
            groups[g] = []
            order.append(g)
        groups[g].append(d)
    return [(g, groups[g]) for g in order]


def get_decor(decor_id: str) -> dict | None:
    index = _load_index()
    for decor in index:
        if decor.get("id") == decor_id:
            return decor
    return None


def save_decor(data: dict) -> dict:
    from core.context import get_project_id
    _ensure()
    pid = get_project_id()
    if pid and not data.get("project_id"):
        data["project_id"] = pid
    index = _load_index()
    now = datetime.now().isoformat()

    if not data.get("id"):
        data["id"] = str(uuid.uuid4())
        data["created_at"] = now
        data["updated_at"] = now
        data.setdefault("name", "")
        data.setdefault("category", "Autre")
        data.setdefault("prompt", "")
        data.setdefault("image_path", "")
        data.setdefault("thumbnail_path", "")  # aperçu léger préparé pendant la génération
        data.setdefault("floor_plan", "")   # plan vu de dessus (Mise en scène / Plan de feu)
        data.setdefault("floor_plan_thumbnail", "")
        data.setdefault("generated_images", [])  # galerie d'images de CE décor
        data.setdefault("room_views", [])        # (legacy) galerie 7 vues d'un décor unique
        data.setdefault("room_view", "")         # face de la pièce (Avant/Arrière/…/Ensemble)
        data.setdefault("room_group", "")        # pièce d'appartenance : les 7 vues d'une
        #                                           même pièce partagent ce nom → regroupées
        #                                           dans un bandeau dépliable (page Décors).
        data.setdefault("ref_paths", [])
        data.setdefault("assigned_to", [])
        data.setdefault("assigned_sequences", [])
        data.setdefault("assigned_shots", [])
        index.append(data)
    else:
        data["updated_at"] = now
        replaced = False
        for i, decor in enumerate(index):
            if decor.get("id") == data["id"]:
                index[i] = data
                replaced = True
                break
        if not replaced:
            data.setdefault("created_at", now)
            index.append(data)

    _save_index(index)
    return data


def delete_decor(decor_id: str):
    index = _load_index()
    index = [d for d in index if d.get("id") != decor_id]
    _save_index(index)


def set_floor_plan(decor_id: str, path: str) -> bool:
    """Associe un plan vu de dessus (image) à un décor — source unique partagée
    par la page Décors, la Mise en scène et le Plan de feu. True si écrit."""
    index = _load_index()
    for decor in index:
        if decor.get("id") == decor_id:
            decor["floor_plan"] = path or ""
            decor["updated_at"] = datetime.now().isoformat()
            _save_index(index)
            return True
    return False


def floor_plan_for_shot(shot: dict) -> str:
    """Résout le plan vu de dessus d'un plan du storyboard.

    Les anciens storyboards n'ont pas toujours ``decor_id`` renseigné, même si
    le décor et son plan d'architecte ont déjà été générés. On tente donc, dans
    l'ordre : identifiant explicite, nom du décor, assignation plan/séquence, puis
    décor unique du projet. Cette fonction ne modifie jamais les données.
    """
    shot = shot or {}
    decors = list_decors()

    did = str(shot.get("decor_id") or "").strip()
    if did:
        dec = next((d for d in decors if d.get("id") == did), None)
        if dec and dec.get("floor_plan"):
            return dec["floor_plan"]

    def norm(value) -> str:
        import unicodedata
        text = unicodedata.normalize("NFKD", str(value or ""))
        return " ".join("".join(c for c in text if not unicodedata.combining(c)).casefold().split())

    decor_name = norm(shot.get("decor_name") or shot.get("location") or shot.get("decor"))
    if decor_name:
        named = [d for d in decors if d.get("floor_plan") and
                 (norm(d.get("name")) == decor_name or decor_name in norm(d.get("name"))
                  or norm(d.get("name")) in decor_name)]
        if len(named) == 1:
            return named[0]["floor_plan"]

    shot_id = str(shot.get("id") or "")
    seq_values = {norm(shot.get("seq_num")), norm(shot.get("sequence")),
                  norm(shot.get("seq_name")), norm(shot.get("scene_title"))}
    seq_values.discard("")
    assigned = []
    for decor in decors:
        if not decor.get("floor_plan"):
            continue
        if shot_id and shot_id in (decor.get("assigned_shots") or []):
            assigned.append(decor)
            continue
        decor_sequences = {norm(v) for v in (decor.get("assigned_sequences") or [])}
        if seq_values.intersection(decor_sequences):
            assigned.append(decor)
    if len(assigned) == 1:
        return assigned[0]["floor_plan"]

    with_plan = [d for d in decors if d.get("floor_plan")]
    groups = {d.get("room_group") or d.get("group_id") or d.get("id") for d in with_plan}
    if with_plan and len(groups) == 1:
        return with_plan[0]["floor_plan"]
    return ""
