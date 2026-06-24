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


def axis_from_placement(rec: dict) -> str:
    """Axe caméra déduit de la POSITION de la caméra par rapport au centre des
    acteurs (le « devant » du sujet = vers le bas du plan, comme la caméra Face par
    défaut). DÉPLACER la caméra change donc l'axe — contrairement à axis_from_angle
    qui ne dépend que de la rotation. Renvoie Face / 3/4 / Latéral 90° / Dos."""
    import math
    cam = rec.get("camera") or {}
    actors = [a for a in (rec.get("actors") or []) if isinstance(a, dict)]
    if actors:
        cx = sum(a.get("x", 0.5) for a in actors) / len(actors)
        cy = sum(a.get("y", 0.5) for a in actors) / len(actors)
    else:
        cx, cy = 0.5, 0.5
    dx = cam.get("x", 0.5) - cx
    dy = cam.get("y", 0.85) - cy
    if abs(dx) < 1e-4 and abs(dy) < 1e-4:
        return axis_from_angle(cam.get("angle", 0))
    # 0° = caméra DEVANT le sujet (sous lui, dy>0) ; ±90° = de côté ; ±180° = derrière.
    a = abs(math.degrees(math.atan2(dx, dy)))
    if a <= 30:
        return "Face"
    if a >= 150:
        return "Dos"
    if 65 <= a <= 115:
        return "Latéral 90°"
    return "3/4"


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


# Angle caméra (sur le plan vu de dessus) dérivé de l'axe choisi au découpage.
_AXIS_TO_CAMERA = {
    "Face":            (0.5, 0.85,   0.0),   # bas, regarde vers le haut (face au sujet)
    "3/4":             (0.78, 0.80,  35.0),
    "Latéral 90°":     (0.85, 0.5,   90.0),
    "Latéral":         (0.85, 0.5,   90.0),
    "Dos":             (0.5, 0.15,  180.0),   # haut, regarde vers le bas (de dos)
    "Plongée":         (0.5, 0.85,   0.0),    # vertical → la HAUTEUR gère le reste
    "Contre-plongée":  (0.5, 0.85,   0.0),
}


def seed_record_for_shot(shot: dict) -> dict:
    """Construit une mise en scène INITIALE pour un plan, depuis ses données du
    storyboard (déjà extraites du scénario) : acteurs répartis + caméra placée selon
    l'axe (camera_axis). L'utilisateur ajuste ensuite. Aucune lumière (Plan de feu
    se règle à part), aucun élément (le placement précis vient de l'analyse vision)."""
    rec = _default()
    names = [n for n in (shot.get("character_names") or []) if n][:6]
    n = len(names) or 1
    # Acteurs répartis horizontalement, légèrement vers l'avant (y=0.55).
    rec["actors"] = [
        {"name": nm, "x": round(0.5 + (i - (n - 1) / 2) * 0.16, 3), "y": 0.55}
        for i, nm in enumerate(names)
    ]
    axis = (shot.get("camera_axis") or "Face").strip()
    cx, cy, ang = _AXIS_TO_CAMERA.get(axis, _AXIS_TO_CAMERA["Face"])
    rec["camera"] = {"x": cx, "y": cy, "angle": ang}
    # Hauteur caméra si déjà saisie sur le plan (« 1,7 m » → 1.7).
    h = _parse_meters(shot.get("camera_height"))
    if h > 0:
        rec["camera"]["height"] = h
    return rec


def ensure_seeded(shots: list) -> int:
    """À la génération du storyboard/décor : crée une mise en scène INITIALE (acteurs
    + caméra) pour chaque plan qui n'en a pas encore. Ne touche jamais un plan déjà
    mis en scène. Renvoie le nombre de plans semés."""
    idx = _load()
    n = 0
    for s in shots or []:
        sid = s.get("id")
        if not sid or sid in idx:
            continue
        rec = seed_record_for_shot(s)
        rec["_actors_seeded"] = True
        idx[sid] = rec
        n += 1
    if n:
        _save(idx)
    return n


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


def _cam_frame(rec):
    """Repère caméra normalisé : origine = caméra, avant = vers le sujet,
    droite = image-droite. Sans caméra : avant = bas de l'image, droite = x croissant."""
    import math
    cam = rec.get("camera") or {}
    if cam:
        cx, cy = cam.get("x", .5), cam.get("y", .5)
        sx, sy = _subject_pos(rec)
        fx, fy = sx - cx, sy - cy
        fn = math.hypot(fx, fy) or 1e-6
        fx, fy = fx / fn, fy / fn
        return (cx, cy), (fx, fy), (-fy, fx)
    return (0.5, 0.5), (0.0, 1.0), (1.0, 0.0)


def _actor_placement_phrase(rec, actor) -> str:
    """Placement d'un acteur EXPRIMÉ PAR RAPPORT à l'élément de décor le plus
    proche et VU DE LA CAMÉRA (« à droite de la table », « devant le comptoir »,
    « à la table, à gauche »). Sans élément posé : zone du cadre vue caméra
    (« au premier plan à gauche »). Recalculé en direct si on déplace l'acteur,
    l'élément OU la caméra → le prompt reflète exactement la mise en scène."""
    import math
    ax, ay = actor.get("x", .5), actor.get("y", .5)
    (cx, cy), (fx, fy), (rx, ry) = _cam_frame(rec)

    props = rec.get("props") or []
    if props:
        prop = min(props, key=lambda p: math.hypot(ax - p.get("x", .5), ay - p.get("y", .5)))
        px, py = prop.get("x", .5), prop.get("y", .5)
        name = (prop.get("name") or "l'élément").strip()
        dist = math.hypot(ax - px, ay - py)
        vx, vy = ax - px, ay - py                 # élément → acteur
        lat = vx * rx + vy * ry                    # + = image-droite
        dep = vx * fx + vy * fy                    # + = plus loin que l'élément (derrière)
        side  = "à droite" if lat > 0.04 else ("à gauche" if lat < -0.04 else "")
        depth = "devant" if dep < -0.04 else ("derrière" if dep > 0.04 else "")
        if dist < 0.09:                            # collé à l'élément → « à la table »
            return f"à {name}" + (f", {side}" if side else "")
        side_p = f"{side} de {name}" if side else ""
        if side_p and depth:
            return f"{side_p}, {depth}"            # « à droite de la table, devant »
        if side_p:
            return side_p
        if depth:
            return f"{depth} {name}"               # « devant la table »
        return f"près de {name}"

    # Aucun élément posé → zone du cadre, vue caméra.
    vx, vy = ax - cx, ay - cy
    lat = vx * rx + vy * ry
    h = "à gauche" if lat < -0.05 else ("à droite" if lat > 0.05 else "au centre")
    dcam = math.hypot(vx, vy)
    sx, sy = _subject_pos(rec)
    dsub = math.hypot(sx - cx, sy - cy) or 1e-6
    r = dcam / dsub
    v = ("au premier plan" if r < 0.8
         else ("à l'arrière-plan" if r > 1.25 else "au milieu du cadre"))
    if v == "au milieu du cadre" and h == "au centre":
        return "au centre du cadre"
    return f"{v} {h}"


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
            f"{a.get('name','?')} {_actor_placement_phrase(rec, a)}" for a in actors) + ".")
    props = rec.get("props") or []
    if props:
        parts.append("Éléments du décor : " + ", ".join(
            f"{p.get('name','?')} ({_zone(p)})" for p in props) + ".")
    return " ".join(parts)


def staging_actors_summary(shot_id: str) -> str:
    """Placement des PERSONNAGES (+ éléments) SEUL — pour la section [MISE EN SCÈNE]
    du prompt. Chaque personnage est situé PAR RAPPORT aux éléments du décor posés
    sur le plan (« à droite de la table ») et vu de la caméra — pas en zone abstraite.
    La caméra, elle, part dans les champs TECHNIQUES du plan (camera_axis /
    camera_placement) — cf. PageStaging._sync_to_storyboard."""
    rec = get(shot_id)
    parts = []
    actors = rec.get("actors") or []
    if actors:
        parts.append("Personnages : " + ", ".join(
            f"{a.get('name','?')} {_actor_placement_phrase(rec, a)}" for a in actors) + ".")
    props = rec.get("props") or []
    if props:
        parts.append("Éléments du décor en place : "
                     + ", ".join(p.get("name", "?") for p in props) + ".")
    return " ".join(parts)


def camera_placement(shot_id: str) -> str:
    """Zone de placement de la caméra (ex. « avant-centre ») — pour le champ
    technique camera_placement du storyboard."""
    rec = get(shot_id)
    cam = rec.get("camera") or {}
    return _zone(cam) if cam else ""


def _parse_meters(s) -> float:
    """Extrait une distance en mètres d'une chaîne comme « 4m », « 12,5 m »."""
    import re
    m = re.search(r"(\d+(?:[.,]\d+)?)", str(s or ""))
    if not m:
        return 0.0
    try:
        return float(m.group(1).replace(",", "."))
    except ValueError:
        return 0.0


def _subject_pos(rec) -> tuple:
    """Position du SUJET éclairé : barycentre des acteurs (sinon accessoires,
    sinon centre du plan)."""
    for key in ("actors", "props"):
        pts = [(it.get("x", .5), it.get("y", .5)) for it in (rec.get(key) or [])]
        if pts:
            return (sum(p[0] for p in pts) / len(pts), sum(p[1] for p in pts) / len(pts))
    return (0.5, 0.5)


DEFAULT_PLAN_SPAN_M = 10.0   # largeur réelle supposée d'un plan de décor (mètres)


def plan_span_m(rec) -> float:
    """Échelle RÉELLE du plan : largeur du décor en mètres (override possible par
    rec['plan_span_m']). Échelle UNIQUE servant à la fois aux distances du plan de
    feu ET à la distance caméra écrite dans le storyboard → tout est cohérent."""
    try:
        v = float(rec.get("plan_span_m") or 0)
    except (TypeError, ValueError):
        v = 0.0
    return v if v > 0 else DEFAULT_PLAN_SPAN_M


def _plan_scale(rec) -> float:
    """Mètres par unité normalisée (coords 0..1 → la largeur réelle du plan)."""
    return plan_span_m(rec)


def camera_distance_m(rec) -> float:
    """Distance RÉELLE caméra → sujet (mètres), dérivée de la position de la caméra
    sur le plan et de l'échelle réelle du décor. Écrite dans le storyboard (colonne
    DIST.) quand on déplace la caméra."""
    import math
    cam = rec.get("camera") or {}
    if not cam:
        return 0.0
    subject = _subject_pos(rec)
    d = math.hypot(cam.get("x", .5) - subject[0], cam.get("y", .5) - subject[1])
    return round(d * _plan_scale(rec) * 2) / 2


def _cam_relative_dir(cam, subject, light) -> str:
    """Direction d'un projecteur EXPRIMÉE PAR RAPPORT À L'AXE CAMÉRA (frontal /
    3/4 / latéral / contre-jour, côté caméra gauche ou droite — du point de vue
    de l'image). Si la caméra bouge, cette direction change."""
    import math
    cx, cy = cam.get("x", .5), cam.get("y", .5)
    sx, sy = subject
    lx, ly = light
    fx, fy = sx - cx, sy - cy            # caméra → sujet (direction de visée)
    fn = math.hypot(fx, fy) or 1e-6
    fx, fy = fx / fn, fy / fn
    rx, ry = -fy, fx                      # « droite caméra » (image, y vers le bas)
    dx, dy = lx - sx, ly - sy            # sujet → projecteur
    dn = math.hypot(dx, dy) or 1e-6
    ux, uy = dx / dn, dy / dn
    cosang = max(-1.0, min(1.0, ux * (-fx) + uy * (-fy)))
    phi = math.degrees(math.acos(cosang))   # 0 = face caméra, 180 = contre-jour
    sd = ux * rx + uy * ry
    side = "droite" if sd > 0.15 else ("gauche" if sd < -0.15 else "")
    sfx = (" " + side) if side else ""
    if phi <= 25:
        return "en lumière frontale (face caméra)"
    if phi <= 65:
        return f"en 3/4 face côté caméra{sfx}"
    if phi <= 115:
        return f"en latéral (90°) côté caméra{sfx}"
    if phi <= 155:
        return f"en 3/4 arrière contre-jour côté caméra{sfx}"
    return "en contre-jour (derrière le sujet)"


def lighting_summary(shot_id: str) -> str:
    """Résumé PLAN DE FEU — pour la section [PLAN DE FEU] du prompt.
    Le placement de CHAQUE projecteur est exprimé RELATIVEMENT À L'AXE CAMÉRA
    (frontal / latéral / contre-jour, côté caméra gauche-droite), avec des DISTANCES
    chiffrées aux acteurs (échelle RÉELLE du décor). Les projecteurs ÉTEINTS sont
    exclus. Si la caméra bouge, la direction de la lumière change → résumé recalculé."""
    import math
    rec = get(shot_id)
    # Projecteurs ALLUMÉS uniquement (éteint = grisé + exclu du prompt).
    lights = [l for l in (rec.get("lights") or [])
              if (l.get("settings") or {}).get("on", True)]
    if not lights:
        return ""
    try:
        import core.projectors as proj
    except Exception:
        proj = None
    role_lbl = proj.role_label if proj else (lambda c: c)

    cam     = rec.get("camera") or {}
    actors  = rec.get("actors") or []
    subject = _subject_pos(rec)
    scale   = _plan_scale(rec)

    def _dist_m(a, b):
        return round(math.hypot(a[0] - b[0], a[1] - b[1]) * scale * 2) / 2

    def _fmt_m(v):
        return f"{v:.1f}".rstrip("0").rstrip(".").replace(".", ",") + " m"

    bits = []
    for l in lights:
        lp   = (l.get("x", .5), l.get("y", .5))
        desc = role_lbl(l.get("type", "")) or l.get("type", "lumière")
        model = (l.get("model") or "").strip()
        if model:
            desc += f" ({model})"
        # Direction RELATIVE À LA CAMÉRA (pas au décor).
        desc += ", " + (_cam_relative_dir(cam, subject, lp) if cam else _zone(l))
        # Distances CHIFFRÉES aux acteurs (ou au sujet si aucun acteur nommé).
        named = [(a.get("name", ""), (a.get("x", .5), a.get("y", .5)))
                 for a in actors if a.get("name")]
        if named:
            desc += ", à " + ", ".join(f"{_fmt_m(_dist_m(lp, ap))} de {nm}"
                                       for nm, ap in named[:3])
        else:
            desc += f", à {_fmt_m(_dist_m(lp, subject))} du sujet"
        # Réglages réalistes du projecteur (intensité, température, teinte, ±vert,
        # gélatine, faisceau) selon ses capacités → injectés dans le prompt.
        if proj:
            st = proj.describe_settings(l)
            if st:
                desc += f" — {st}"
            # AMBIANCE (mood) calquée sur le type de projecteur — en plus du
            # technique, ce que Seedance doit ressentir (chaleur, douceur, couleur).
            try:
                amb = proj.ambiance_phrase(l)
            except Exception:
                amb = ""
            if amb:
                desc += f" — ambiance : {amb}"
        bits.append(desc)
    return ("Éclairage (placements RELATIFS À L'AXE CAMÉRA) : " + " ; ".join(bits) + ". "
            "IMPORTANT : les projecteurs / sources d'éclairage ne sont PAS visibles "
            "dans le plan — ils décrivent uniquement la lumière, sa direction par "
            "rapport à la caméra et l'ambiance ; n'affiche aucun appareil d'éclairage à l'image.")
