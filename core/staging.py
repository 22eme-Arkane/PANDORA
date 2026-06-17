"""
core/staging.py — Mise en scène & Plan de feu (vue de dessus, par plan).

Pour chaque plan du storyboard, on mémorise un « plan d'architecte » vu de haut :
fond (image générée du décor en plan), position/orientation de la CAMÉRA, position
des PERSONNAGES et des ÉLÉMENTS, et — pour le Plan de feu — les LUMIÈRES (type de
projecteur + direction). Coordonnées normalisées 0..1 (indépendantes de la taille
d'affichage). Sert à : préciser l'axe caméra, éviter les personnages mal placés,
réutiliser un décor déjà généré, et réadapter les prompts (synchronisation).

Stockage par projet : <data_root>/staging/index.json (+ images du plan).
"""

import os
import json

# Types de projecteurs pour le Plan de feu (nom, libellé).
PROJECTOR_TYPES = [
    ("key",      "Key light (principale)"),
    ("fill",     "Fill (déboucheur)"),
    ("back",     "Back / contre-jour"),
    ("rim",      "Rim (liseré)"),
    ("spot",     "Spot / découpe"),
    ("fresnel",  "Fresnel"),
    ("softbox",  "Softbox / diffus"),
    ("practical","Practical (source dans le décor)"),
    ("ambient",  "Ambiance / fond"),
]

# Axes caméra dérivés de l'angle (degrés, 0 = vers le haut de l'image, horaire).
# Pour cohérence avec storyboard.camera_axis.
def axis_from_angle(angle: float) -> str:
    a = angle % 360
    if a < 45 or a >= 315:
        return "Face"
    if a < 135:
        return "Latéral 90°"
    if a < 225:
        return "Dos"
    return "Latéral 90°"


def _dir() -> str:
    from core.context import get_data_root
    d = os.path.join(get_data_root(), "staging")
    os.makedirs(d, exist_ok=True)
    return d


def images_dir() -> str:
    d = os.path.join(_dir(), "plans")
    os.makedirs(d, exist_ok=True)
    return d


def _index_path() -> str:
    return os.path.join(_dir(), "index.json")


def _load() -> dict:
    try:
        with open(_index_path(), encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _save(data: dict) -> None:
    try:
        with open(_index_path(), "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


def _default() -> dict:
    return {
        "plan_image": "",
        "camera":     {"x": 0.5, "y": 0.85, "angle": 0.0},
        "actors":     [],   # [{name, x, y}]
        "props":      [],   # [{name, x, y}]
        "lights":     [],   # [{name, type, x, y, angle}]
    }


def get(shot_id: str) -> dict:
    """Mise en scène d'un plan (dict complet, valeurs par défaut si absent)."""
    if not shot_id:
        return _default()
    rec = _load().get(shot_id)
    if not rec:
        return _default()
    base = _default()
    base.update(rec)
    return base


def save(shot_id: str, data: dict) -> None:
    if not shot_id:
        return
    idx = _load()
    idx[shot_id] = data
    _save(idx)


def staging_saves_dir(mode: str = "staging") -> str:
    """Dossier par défaut des sauvegardes de mise en scène / plan de feu (pour la
    boîte de dialogue Windows)."""
    from core.context import get_data_root
    sub = "Mise en scène" if mode == "staging" else "Plan de feu"
    d = os.path.join(get_data_root(), sub)
    os.makedirs(d, exist_ok=True)
    return d


def export_staging_to(path: str) -> str:
    """Exporte TOUTE la mise en scène / plan de feu (tous les plans) vers un fichier
    CHOISI par l'utilisateur — rechargeable ensuite dans n'importe quel projet."""
    payload = {"staging": _load()}
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    return path


def import_staging_from(path: str) -> int:
    """Recharge une mise en scène depuis un fichier CHOISI : REMPLACE l'index
    courant. Retourne le nombre de plans importés."""
    if not path or not os.path.isfile(path):
        return 0
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    stg = data.get("staging", data) if isinstance(data, dict) else {}
    if not isinstance(stg, dict):
        return 0
    _save(stg)
    return len(stg)


def summary(shot_id: str) -> str:
    """Résumé textuel de la mise en scène — injecté dans la synchronisation des
    prompts pour réadapter au placement et à la lumière."""
    rec = get(shot_id)
    parts = []
    cam = rec.get("camera") or {}
    if cam:
        parts.append(f"caméra axe {axis_from_angle(cam.get('angle', 0))}")
    actors = rec.get("actors") or []
    if actors:
        parts.append("acteurs : " + ", ".join(
            f"{a.get('name','?')} ({_zone(a)})" for a in actors))
    props = rec.get("props") or []
    if props:
        parts.append("éléments : " + ", ".join(p.get("name", "?") for p in props))
    lights = rec.get("lights") or []
    if lights:
        parts.append("lumières : " + ", ".join(
            f"{l.get('name','?')} [{l.get('type','')}]" for l in lights))
    return " · ".join(parts)


def _zone(item: dict) -> str:
    x, y = item.get("x", 0.5), item.get("y", 0.5)
    h = "gauche" if x < 0.4 else ("droite" if x > 0.6 else "centre")
    v = "fond" if y < 0.4 else ("avant" if y > 0.6 else "milieu")
    return f"{v}-{h}"


def staging_summary(shot_id: str) -> str:
    """Résumé MISE EN SCÈNE seule (caméra + personnages + éléments) — pour la
    section [MISE EN SCÈNE] du prompt structuré."""
    rec = get(shot_id)
    parts = []
    cam = rec.get("camera") or {}
    if cam:
        parts.append(f"Caméra : axe {axis_from_angle(cam.get('angle', 0))}, "
                     f"placée en {_zone(cam)}.")
    actors = rec.get("actors") or []
    if actors:
        parts.append("Personnages : " + ", ".join(
            f"{a.get('name','?')} en {_zone(a)}" for a in actors) + ".")
    props = rec.get("props") or []
    if props:
        parts.append("Éléments : " + ", ".join(
            f"{p.get('name','?')} en {_zone(p)}" for p in props) + ".")
    return " ".join(parts)


def staging_actors_summary(shot_id: str) -> str:
    """Placement des PERSONNAGES (+ éléments) SEUL — pour la section [MISE EN SCÈNE]
    du prompt. La caméra, elle, part dans les champs TECHNIQUES du plan
    (camera_axis / camera_placement) — cf. PageStaging._sync_to_storyboard."""
    rec = get(shot_id)
    parts = []
    actors = rec.get("actors") or []
    if actors:
        parts.append("Personnages : " + ", ".join(
            f"{a.get('name','?')} en {_zone(a)}" for a in actors) + ".")
    props = rec.get("props") or []
    if props:
        parts.append("Éléments : " + ", ".join(
            f"{p.get('name','?')} en {_zone(p)}" for p in props) + ".")
    return " ".join(parts)


def camera_placement(shot_id: str) -> str:
    """Zone de placement de la caméra (ex. « avant-centre ») — pour le champ
    technique camera_placement du storyboard."""
    rec = get(shot_id)
    cam = rec.get("camera") or {}
    return _zone(cam) if cam else ""


def lighting_summary(shot_id: str) -> str:
    """Résumé PLAN DE FEU (lumières : rôle, modèle, position, direction) — pour la
    section [PLAN DE FEU] du prompt structuré."""
    rec = get(shot_id)
    lights = rec.get("lights") or []
    if not lights:
        return ""
    try:
        import core.projectors as proj
        role_lbl = proj.role_label
    except Exception:
        role_lbl = lambda c: c
    bits = []
    for l in lights:
        desc = role_lbl(l.get("type", "")) or l.get("type", "lumière")
        model = (l.get("model") or "").strip()
        if model:
            desc += f" ({model})"
        desc += f", {_zone(l)}"
        bits.append(desc)
    return ("Éclairage : " + " ; ".join(bits) + ". "
            "IMPORTANT : les projecteurs / sources d'éclairage ne sont PAS visibles "
            "dans le plan — ils décrivent uniquement la lumière et l'ambiance, "
            "n'affiche aucun appareil d'éclairage à l'image.")
