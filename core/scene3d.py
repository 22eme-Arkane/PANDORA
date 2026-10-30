"""core/scene3d.py — Scène 3D d'un plan (onglet « 3D » : lumière, mise en scène, décor).

Demande Matthieu (29/10/2026) : un vrai outil 3D qui reprend le plan de feu d'ARKLIGHT
PC, avec une mise en scène (déplacements des personnages, caméra) qui enrichit le prompt
et peut servir de référence vidéo à Seedance (prévisualisation, Blender).

UNE scène par plan, et c'est la SEULE vérité : la vue 3D, le plan vu de dessus, le prompt,
la prévisualisation et Blender lisent et écrivent cette même scène (jamais une copie à
part qui finirait par dire « à gauche » quand la 3D montre la droite).

Format : celui d'ARKLIGHT (mètres, y vers le haut, le sol en x/z ; projecteurs, objets
de décor et de grip, plan 2D), plus une clé « pandora » propre à PANDORA :
    {
      "v": 1, "shot_id": "…", "duration": 5.0,
      "shot_camera": "<id de l'objet caméra du plan>",
      "underlay_path": "<plan du décor vu de dessus>", "span_m": 10.0,
      "tracks": {"<id objet>": [{"t": 0.0, "p": [x, y, z], "yaw": 0.0, "pose": "…"}]},
      "analysis": {...}   # écrit par la vue (données de la bibliothèque d'ARKLIGHT)
    }
Repères : un personnage regarde +Z quand son lacet vaut 0 ; la caméra « Face » de
l'ancien plan (bas de l'image) est du côté +Z et regarde vers -Z (lacet π).

Stockage : <projet>/01_writing/staging/scenes/<plan>.json (à côté de l'ancien index de
mise en scène 2D, qui reste lu pour les plans sans scène 3D).
"""
from __future__ import annotations

import json
import math
import os
import re
import tempfile

SCENE_VERSION = 1

# Ancien plan de feu (famille de matériel / rôle) -> modèle réel de la bibliothèque d'ARKLIGHT
_FAMILY_TO_TYPE = {
    "led_panel": "arri.skypanel-s60c",
    "cob": "aputure.ls-600d-pro",
    "fresnel": "arri.l7-c",
    "tube": "astera.ax1",
    "mat": "litegear.litemat-plus-4",
    "par_hmi": "arri.m18",
    "profile": "dedolight.dled4-bi",
    "balloon": "arri.skypanel-s360c",
    "practical": "astera.nyx",
}
_ROLE_TO_TYPE = {
    "key": "arri.skypanel-s60c", "fill": "aputure.nova-p300c", "back": "aputure.ls-600d-pro",
    "rim": "aputure.ls-300x", "eye": "dmg-lumiere.sl1-mix", "background": "arri.l7-c",
    "practical": "astera.nyx", "ambient": "arri.skypanel-s360c",
    # anciens codes de staging.PROJECTOR_TYPES
    "spot": "dedolight.dled4-bi", "fresnel": "arri.l7-c", "softbox": "aputure.ls-600d-pro",
}
# Modèles nommés de l'ancien plan de feu -> identifiant ARKLIGHT (mots-clés, minuscules)
_MODEL_HINTS = (
    ("s360", "arri.skypanel-s360c"), ("s120", "arri.skypanel-s120c"), ("s60", "arri.skypanel-s60c"),
    ("s30", "arri.skypanel-s30c"), ("l10", "arri.l10-c"), ("l7", "arri.l7-c"), ("l5", "arri.l5-c"),
    ("1200d", "aputure.ls-1200d-pro"), ("600x", "aputure.ls-600x-pro"), ("600d", "aputure.ls-600d-pro"),
    ("300x", "aputure.ls-300x"), ("nova", "aputure.nova-p300c"), ("m18", "arri.m18"),
    ("joker", "k5600.joker2-800"), ("baby 1k", "mole.baby-1k"), ("650", "arri.650-plus"),
    ("titan", "astera.ax1"), ("helios", "astera.ax2-100"), ("pixelbrick", "astera.pixelbrick"),
    ("sl1", "dmg-lumiere.sl1-mix"), ("maxi", "dmg-lumiere.maxi-mix"), ("litemat", "litegear.litemat-plus-4"),
    ("celeb", "kino-flo.celeb-450-led-dmx"), ("dled", "dedolight.dled4-bi"),
)


# ---------------------------------------------------------------------- stockage
def scenes_dir() -> str:
    from core import staging
    d = os.path.join(staging._dir(), "scenes")
    os.makedirs(d, exist_ok=True)
    return d


def _safe(shot_id: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", str(shot_id or "")).strip("._") or "plan"


def path(shot_id: str) -> str:
    return os.path.join(scenes_dir(), _safe(shot_id) + ".json")


def previs_path(shot_id: str) -> str:
    """Vidéo de prévisualisation du plan (rendue depuis la caméra du plan) : chemin cible."""
    d = os.path.join(os.path.dirname(scenes_dir()), "previs")
    os.makedirs(d, exist_ok=True)
    return os.path.join(d, _safe(shot_id) + ".mp4")


def previs_for(shot_id: str) -> str:
    """Prévisualisation existante du plan, ou "" (le Studio l'envoie à Seedance si demandé)."""
    if not shot_id:
        return ""
    try:
        p = previs_path(shot_id)
    except OSError:
        return ""
    return p if os.path.isfile(p) and os.path.getsize(p) > 0 else ""


def exists(shot_id: str) -> bool:
    return bool(shot_id) and os.path.isfile(path(shot_id))


def load(shot_id: str) -> dict | None:
    """Scène 3D enregistrée d'un plan, ou None."""
    if not shot_id:
        return None
    try:
        with open(path(shot_id), encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else None
    except (OSError, ValueError):
        return None


def save(shot_id: str, scene: dict) -> None:
    """Enregistre la scène (écriture atomique : jamais de fichier à moitié écrit)."""
    if not shot_id or not isinstance(scene, dict):
        return
    scene = clean_for_disk(scene)
    scene.setdefault("pandora", {})["shot_id"] = shot_id
    target = path(shot_id)
    fd, tmp = tempfile.mkstemp(prefix=".scene_", suffix=".json", dir=os.path.dirname(target))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(scene, f, ensure_ascii=False, indent=1)
        os.replace(tmp, target)
    finally:
        if os.path.exists(tmp):
            os.remove(tmp)


def clean_for_disk(scene: dict) -> dict:
    """Retire ce qui ne vaut que pour la session (URL du plan du décor servie à la vue)."""
    scene = json.loads(json.dumps(scene))
    under = ((scene.get("plot") or {}).get("underlay") or None)
    if isinstance(under, dict) and str(under.get("url", "")).startswith("pandora3d:"):
        under["url"] = ""
    return scene


# ---------------------------------------------------------------------- géométrie
def yaw_facing(src, dst) -> float:
    """Lacet d'un objet en `src` qui regarde `dst` (sol x/z ; 0 = vers +Z)."""
    return round(math.atan2(dst[0] - src[0], dst[2] - src[2]), 4)


def forward_from_rotation(rot) -> tuple[float, float, float]:
    """Axe +Z local après une rotation d'Euler three.js (ordre XYZ) : sens du faisceau."""
    a, b = float(rot[0]), float(rot[1])
    return (math.sin(b), -math.cos(b) * math.sin(a), math.cos(b) * math.cos(a))


def aim_rotation(src, dst) -> list[float]:
    """Rotation (Euler XYZ de three.js) d'un projecteur en `src` dont l'axe +Z vise `dst` :
    même calcul que Object3D.lookAt d'ARKLIGHT (axe haut = +Y)."""
    z = [dst[i] - src[i] for i in range(3)]
    n = math.sqrt(sum(c * c for c in z)) or 1e-9
    z = [c / n for c in z]
    up = (0.0, 1.0, 0.0)
    x = [up[1] * z[2] - up[2] * z[1], up[2] * z[0] - up[0] * z[2], up[0] * z[1] - up[1] * z[0]]
    nx = math.sqrt(sum(c * c for c in x))
    if nx < 1e-6:                      # visée verticale : n'importe quel axe x convient
        x = [1.0, 0.0, 0.0]
    else:
        x = [c / nx for c in x]
    y = [z[1] * x[2] - z[2] * x[1], z[2] * x[0] - z[0] * x[2], z[0] * x[1] - z[1] * x[0]]
    b = math.asin(max(-1.0, min(1.0, z[0])))
    if abs(z[0]) < 0.9999999:
        a = math.atan2(-z[1], z[2])
        c = math.atan2(-y[0], x[0])
    else:
        a = math.atan2(y[2], y[1])
        c = 0.0
    return [round(a, 4), round(b, 4), round(c, 4)]


def _legacy_to_m(item: dict, span: float) -> tuple[float, float]:
    """Coordonnées 0..1 de l'ancien plan vu de dessus -> mètres (centre du plan = origine)."""
    return (round((float(item.get("x", 0.5)) - 0.5) * span, 3),
            round((float(item.get("y", 0.5)) - 0.5) * span, 3))


def legacy_light_type(light: dict) -> str:
    """Modèle ARKLIGHT le plus proche d'un projecteur de l'ancien plan de feu."""
    model = str(light.get("model") or "").lower()
    for key, tid in _MODEL_HINTS:
        if key in model:
            return tid
    return (_FAMILY_TO_TYPE.get(str(light.get("family") or ""))
            or _ROLE_TO_TYPE.get(str(light.get("type") or ""))
            or "arri.skypanel-s60c")


_WOMAN = re.compile(r"\b(femme|fille|mère|soeur|sœur|épouse|actrice|elle|madame|mme|grand-mère|"
                    r"woman|female|she|her|mother|sister|wife|actress|lady)\b", re.I)


def _character_build(name: str) -> tuple[str, dict]:
    """Mannequin selon la fiche du casting (lue dans sa description) ; homme par défaut."""
    try:
        from core import casting
        chars = casting.list_characters()
    except Exception:
        chars = []
    rec = next((c for c in chars or [] if isinstance(c, dict)
                and str(c.get("name", "")).strip().lower() == str(name).strip().lower()), None)
    text = " ".join(str((rec or {}).get(k, "")) for k in ("role", "description", "prompt"))
    m = re.search(r"\b(\d{1,2})\s*ans\b", text)
    if (m and int(m.group(1)) < 13) or (not m and re.search(r"\b(enfant|fillette|gamin|child|kid)\b", text, re.I)):
        return "person-child", {}
    if _WOMAN.search(text):
        return "person-woman", {}
    return "person-man", {}


# Élément de décor de l'ancien plan (nommé librement) -> objet de la bibliothèque d'ARKLIGHT
_PROP_HINTS = (
    (r"canap|sofa", "sofa-3"), (r"fauteuil|armchair", "armchair"), (r"tabouret de bar", "bar-stool"),
    (r"tabouret|stool", "stool"), (r"chaise|chair", "chair"), (r"table basse|coffee", "coffee-table"),
    (r"table ronde|guéridon", "table-round"), (r"bureau|desk", "desk"), (r"table", "table-rect"),
    (r"lit double|grand lit", "bed-double"), (r"\blit\b|bed", "bed-single"), (r"chevet", "nightstand"),
    (r"armoire|wardrobe", "wardrobe"), (r"commode|dresser", "dresser"), (r"biblioth|étagère|shel", "bookcase"),
    (r"comptoir|bar\b|counter", "bar-counter"), (r"cuisine|kitchen", "kitchen"), (r"frigo|réfrig|fridge", "fridge"),
    (r"télé|\btv\b|écran", "tv"), (r"piano", "piano"), (r"lampadaire|lampe", "floor-lamp"), (r"plante|plant", "plant"),
    (r"tapis|rug", "rug"), (r"paravent", "screen-divider"), (r"fenêtre|window", "wall-window"),
    (r"porte|door", "door"), (r"escalier|stairs", "stairs"), (r"colonne|pilier", "column"), (r"rideau|drape", "drape"),
    (r"\bmur\b|wall", "wall-flat"), (r"arbre|tree", "tree"), (r"buisson|bush", "bush"), (r"rocher|rock", "rock"),
    (r"réverbère|lampadaire de rue", "streetlamp"), (r"banc|bench", "bench"), (r"poubelle", "bin"),
    (r"valise|suitcase", "suitcase"), (r"carton|box", "cardboard"), (r"caisse|crate", "crate"),
    (r"bouteille|bottle", "bottle"), (r"verre|glass", "wine-glass"), (r"tasse|mug|café", "mug"),
    (r"livre|book", "books"), (r"ordinateur|laptop", "laptop"), (r"guitare|guitar", "guitar"),
    (r"micro", "mic-stand"),
)


def prop_type_for(name: str) -> str:
    """Objet ARKLIGHT le plus proche d'un élément de décor nommé (caisse par défaut)."""
    low = str(name or "").lower()
    for pat, tid in _PROP_HINTS:
        if re.search(pat, low):
            return tid
    return "crate"


# ---------------------------------------------------------------------- scène initiale
def seed_from_shot(shot: dict, legacy: dict | None = None) -> dict:
    """Scène INITIALE d'un plan : reprise de l'ancien plan de feu s'il existe (personnages,
    caméra, projecteurs, plan du décor), sinon personnages du découpage devant la caméra.
    Les projecteurs et objets restent « nus » : la vue les complète avec les réglages
    par défaut de la bibliothèque d'ARKLIGHT (hydratation)."""
    from core import staging
    shot = shot or {}
    rec = legacy if legacy is not None else (staging.get(shot.get("id", "")) if shot.get("id") else None)
    has_legacy = bool(rec and (rec.get("actors") or rec.get("lights") or rec.get("plan_image")
                               or rec.get("_actors_seeded")))
    if not has_legacy:
        rec = staging.seed_record_for_shot(shot)
    span = staging.plan_span_m(rec)

    objects, fixtures = [], []
    # caméra du plan
    cam = rec.get("camera") or {"x": 0.5, "y": 0.85, "angle": 0.0}
    cx, cz = _legacy_to_m(cam, span)
    if abs(cx) < 0.05 and abs(cz) < 0.05:
        cz = 4.0
    focal = _focal_mm(shot)
    lens = float(cam.get("height") or staging._parse_meters(shot.get("camera_height")) or 1.45)
    # personnages
    actors = [a for a in (rec.get("actors") or []) if isinstance(a, dict)]
    if not actors:
        names = [n for n in (shot.get("character_names") or []) if n][:6]
        actors = [{"name": n, "x": 0.5 + (i - (len(names) - 1) / 2) * 0.12, "y": 0.5}
                  for i, n in enumerate(names)]
    floor = [_legacy_to_m(a, span) for a in actors]
    centre = _centroid([(x, 0.0, z) for x, z in floor]) or (0.0, 0.0, 0.0)
    # Angle de l'ancien plan (0 = vers le haut, horaire) -> lacet ; s'il ne regarde pas
    # du tout vers les personnages (caméra semée par l'axe du découpage), on la tourne vers eux.
    yaw = math.pi - math.radians(float(cam.get("angle", 0.0)))
    toward = yaw_facing((cx, 0, cz), centre)
    if abs(math.remainder(yaw - toward, 2 * math.pi)) > math.radians(60):
        yaw = toward
    objects.append({"id": "cam_shot", "type": "camera-tripod", "name": _t("Caméra du plan"),
                    "position": [cx, 0, cz], "rotation": [0, round(yaw, 4), 0],
                    "props": {"focal": focal, "sensor": "s35", "lens": round(min(2.2, max(0.5, lens)), 2)},
                    "pandora": {"kind": "shot_camera"}})
    for i, a in enumerate(actors):
        ax, az = _legacy_to_m(a, span)
        typ, props = _character_build(a.get("name", ""))
        if typ != "person-child" and a.get("gender") in ("female", "male"):   # choisi sur l'ancien plan
            typ = "person-woman" if a["gender"] == "female" else "person-man"
        # Face au « devant » du décor (+Z, le bas de l'ancien plan), PAS vers la caméra :
        # c'est la place de la caméra qui fait l'axe du découpage (Face, 3/4, Dos…).
        objects.append({"id": f"act_{i + 1}", "type": typ, "name": a.get("name") or _t("Comédien"),
                        "position": [ax, 0, az], "rotation": [0, 0, 0],
                        "props": props, "pandora": {"kind": "character", "name": a.get("name", "")}})
    # éléments du décor posés sur l'ancien plan : repères au sol (cube de décor)
    for i, p in enumerate(rec.get("props") or []):
        if not isinstance(p, dict):
            continue
        px, pz = _legacy_to_m(p, span)
        objects.append({"id": f"prop_{i + 1}", "type": prop_type_for(p.get("name", "")),
                        "name": p.get("name") or _t("Élément"), "position": [px, 0, pz],
                        "rotation": [0, 0, 0], "pandora": {"kind": "prop", "name": p.get("name", "")}})
    # projecteurs
    subject = _centroid([o["position"] for o in objects if o["pandora"]["kind"] == "character"]) or (0.0, 0.0, 0.0)
    for i, l in enumerate(rec.get("lights") or []):
        if not isinstance(l, dict):
            continue
        lx, lz = _legacy_to_m(l, span)
        s = l.get("settings") or {}
        h = float(s.get("height") or 2.4)
        manual = {"intensity": round(max(0.0, min(1.0, float(s.get("intensity", 70)) / 100.0)), 3)}
        if s.get("saturation"):
            manual.update(mode="hsi", hue=float(s.get("hue", 0)), sat=round(float(s["saturation"]) / 100.0, 3))
        else:
            manual.update(mode="cct", cct=int(s.get("cct") or 5600))
        pos = [lx, round(h, 2), lz]
        fixtures.append({"id": f"lum_{i + 1}", "type": legacy_light_type(l),
                         "name": l.get("name") or l.get("model") or _t("Projecteur"),
                         "position": pos, "rotation": aim_rotation(pos, (subject[0], 1.5, subject[2])),
                         "state": {"power": bool(s.get("on", True)), "manual": manual},
                         "pandora": {"role": l.get("type", "")}})
    pandora = {"v": SCENE_VERSION, "shot_id": shot.get("id", ""), "duration": _duration(shot),
               "shot_camera": "cam_shot", "span_m": span, "tracks": {},
               "from_legacy": has_legacy}
    plan_image = floor_plan_for(shot, rec)
    if plan_image:
        pandora["underlay_path"] = plan_image
    return {"version": 1, "name": shot.get("number") or shot.get("id") or "",
            "environment": {"floor": True, "cyc": False, "stands": True, "haze": 0.15,
                            "ambient": 0.06, "exposure": 1},
            "fixtures": fixtures, "objects": objects, "groups": [],
            "plot": {"items": [], "underlay": None, "background": None, "title": {}},
            "pandora": pandora}


def floor_plan_for(shot: dict, rec: dict | None = None) -> str:
    """Plan vu de dessus du décor du plan (celui choisi sur l'ancien plan de feu, sinon
    celui du décor assigné au storyboard), ou ""."""
    try:
        from core import decors as decors_api
        override = (rec or {}).get("plan_decor_id", "")
        if override == "__none__":
            return ""
        fp = ((decors_api.get_decor(override) or {}).get("floor_plan", "") if override
              else decors_api.floor_plan_for_shot(shot or {}))
    except Exception:
        fp = ""
    if not fp:
        fp = (rec or {}).get("plan_image") or ""
        if fp and not os.path.isabs(fp):
            from core import staging
            fp = os.path.join(staging.images_dir(), fp)
    return fp if fp and os.path.isfile(fp) else ""


def _movement_track(movement: str, cam: dict, duration: float) -> list | None:
    """Keyframes de la caméra pour un mouvement du storyboard (None : pas de déplacement à montrer,
    comme un plan fixe, un zoom ou une caméra portée). Amplitudes modestes, à ajuster sur la frise."""
    fx, fy, fz = forward_from_rotation(cam.get("rotation") or [0, 0, 0])
    n = math.hypot(fx, fz) or 1.0
    fwd = (fx / n, fz / n)
    right = (-fwd[1], fwd[0])
    yaw = math.atan2(fwd[0], fwd[1])
    pitch = math.asin(max(-1.0, min(1.0, -fy)))
    lens = float((cam.get("props") or {}).get("lens") or 1.45)
    p = [float(c) for c in (cam.get("position") or [0, 0, 0])]
    dist = max(0.8, min(4.0, 0.35 * duration))
    dx, dz, dyaw, dpitch, dlens = 0.0, 0.0, 0.0, 0.0, 0.0
    m = (movement or "").strip().lower()
    if m in ("travelling avant", "steadicam"):
        dx, dz = fwd[0] * dist, fwd[1] * dist
    elif m == "travelling arrière":
        dx, dz = -fwd[0] * dist, -fwd[1] * dist
    elif m == "travelling latéral":
        dx, dz = right[0] * dist, right[1] * dist
    elif m == "panoramique horizontal":
        dyaw = -math.radians(25)
    elif m == "panoramique vertical":
        dpitch = -math.radians(12)
    elif m == "grue / drone":
        dlens, dpitch = 1.5, math.radians(10)
    elif m == "drone fpv":
        dx, dz, dlens = fwd[0] * dist * 2, fwd[1] * dist * 2, 1.0
    else:
        return None

    def key(t, x, z, y, a, h):
        return {"t": round(t, 3), "p": [round(x, 3), 0.0, round(z, 3)], "yaw": round(y, 3),
                "lens": round(h, 3), "pitch": round(a, 3), "roll": 0.0}
    return [key(0.0, p[0], p[2], yaw, pitch, lens),
            key(duration, p[0] + dx, p[2] + dz, yaw + dyaw, pitch + dpitch, lens + dlens)]


def apply_camera_movement(shot: dict, scene: dict) -> bool:
    """Reprend le mouvement de caméra du storyboard en keyframes (Matthieu 30/10/2026). Ne touche
    jamais une piste retouchée à la main ; True si la piste de la caméra a changé."""
    pd = scene.setdefault("pandora", {})
    movement = str((shot or {}).get("camera_movement") or "")
    duration = float(pd.get("duration") or _duration(shot))
    seed = f"{movement}|{duration:g}"
    if pd.get("move_seed") == seed:
        return False
    objs = scene.get("objects") or []
    cam = next((o for o in objs if o.get("id") == pd.get("shot_camera")), None) or \
        next((o for o in objs if str(o.get("type", "")).startswith("camera")), None)
    if cam is None:
        return False
    pd["move_seed"] = seed
    tracks = pd.setdefault("tracks", {})
    cid = cam.get("id")
    cur = tracks.get(cid)
    if cur and cur != pd.get("move_track"):
        return False                     # retouchée à la main : elle prime
    new = _movement_track(movement, cam, duration)
    if new == cur:
        return False
    if new:
        tracks[cid] = new
    else:
        tracks.pop(cid, None)
    pd["move_track"] = new
    return True


def ensure(shot: dict) -> dict:
    """Scène du plan : l'enregistrée, sinon une scène initiale (non enregistrée tant que
    la vue ne l'a pas complétée — c'est elle qui renvoie la version hydratée)."""
    sid = (shot or {}).get("id", "")
    scene = load(sid)
    if scene is None:
        scene = seed_from_shot(shot)
    p = scene.setdefault("pandora", {})
    p.setdefault("duration", _duration(shot))
    p.setdefault("tracks", {})
    apply_camera_movement(shot, scene)
    return scene


def underlay_for_view(scene: dict, url: str) -> dict | None:
    """Fond de plan (plan du décor vu de dessus) posé au sol, à l'échelle du décor."""
    p = scene.get("pandora") or {}
    path_ = p.get("underlay_path") or ""
    if not url or not path_:
        return None
    try:
        from PIL import Image
        with Image.open(path_) as im:
            aspect = im.width / max(1, im.height)
    except Exception:
        aspect = 16 / 9
    return {"url": url, "width": float(p.get("span_m") or 10.0), "aspect": round(aspect, 4),
            "x": 0, "z": 0, "rotation": 0, "opacity": 0.85, "floor3d": True}


# ---------------------------------------------------------------------- aides
def _centroid(points):
    pts = [p for p in points if p]
    if not pts:
        return None
    return tuple(round(sum(p[i] for p in pts) / len(pts), 3) for i in range(3))


def _focal_mm(shot: dict) -> int:
    m = re.search(r"(\d+(?:[.,]\d+)?)", str((shot or {}).get("focal") or "35"))
    try:
        return int(round(float(m.group(1).replace(",", ".")))) if m else 35
    except ValueError:
        return 35


def _duration(shot: dict) -> float:
    try:
        return max(1.0, float(str((shot or {}).get("duration") or 5).replace(",", ".")))
    except ValueError:
        return 5.0


def _t(fr: str) -> str:
    try:
        from core.i18n import get_lang, _FR_TO_EN
        return _FR_TO_EN.get(fr, fr) if get_lang() == "en" else fr
    except Exception:
        return fr
