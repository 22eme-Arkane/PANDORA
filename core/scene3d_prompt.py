"""core/scene3d_prompt.py — La scène 3D d'un plan, dite en mots pour le prompt.

Même rôle que staging.staging_actors_summary / staging.lighting_summary (sections
[🎭 MISE EN SCÈNE] et [💡 PLAN DE FEU]), mais calculé sur la vraie scène en mètres :

  - personnages : place dans le CADRE de la caméra du plan (gauche / centre / droite,
    premier plan / arrière-plan), orientation par rapport à la caméra (face, 3/4, profil,
    dos), distance ; puis leurs déplacements minutés (pistes de la frise) ;
  - lumière : pour chaque projecteur allumé, direction VUE DE LA CAMÉRA, hauteur,
    qualité (douce / dure selon la taille apparente de la source), couleur, et sa part
    réelle de lumière sur le visage (éclairement à 1 m de la bibliothèque d'ARKLIGHT,
    loi de l'inverse du carré, position dans le faisceau) ; on en déduit la principale,
    le débouchage, le contre-jour et le rapport de contraste ;
  - caméra : hauteur, focale et champ, distance au sujet, axe ; ses mouvements minutés
    (travelling, montée et descente sur le pied, panoramiques) ;
  - décor : mobilier, animaux, véhicules visibles, avec leur place dans le cadre.

Tout est en français (le prompt est traduit ensuite, comme le reste) et ne cite jamais
le matériel comme un objet à l'image : Seedance doit voir la LUMIÈRE, pas le projecteur.
"""
from __future__ import annotations

import math
import re

from core import scene3d as S

FACE_HEIGHT = 1.55   # hauteur du visage d'un adulte debout (m) quand la taille manque


# ---------------------------------------------------------------------- géométrie caméra
def _shot_camera(scene: dict) -> dict | None:
    objs = scene.get("objects") or []
    cid = (scene.get("pandora") or {}).get("shot_camera")
    cam = next((o for o in objs if o.get("id") == cid), None)
    return cam or next((o for o in objs if str(o.get("type", "")).startswith("camera")), None)


def _cam_frame(cam: dict):
    """Origine (œil), avant et droite de la caméra dans le plan du sol."""
    p = cam.get("position") or [0, 0, 4]
    rot = cam.get("rotation") or [0, math.pi, 0]
    lens = float((cam.get("props") or {}).get("lens") or 1.45)
    # Direction réelle au sol, même caméra basculée (rotation d'Euler XYZ de three.js)
    fx, _fy, fz = S.forward_from_rotation(rot)
    n = math.hypot(fx, fz)
    fwd = (fx / n, fz / n) if n > 1e-6 else (math.sin(float(rot[1])), math.cos(float(rot[1])))  # lacet 0 = +Z
    # droite de l'IMAGE (avant × haut) : caméra qui regarde -Z -> droite = +X
    right = (-fwd[1], fwd[0])
    return (float(p[0]), lens, float(p[2])), fwd, right


def _hfov(cam: dict) -> float:
    props = cam.get("props") or {}
    sw = {"s35": 24.89, "ff": 36.0, "m43": 17.3}.get(props.get("sensor") or "s35", 24.89)
    f = max(4.0, float(props.get("focal") or 35))
    return math.degrees(2 * math.atan(sw / (2 * f)))


def _people(scene: dict) -> list[dict]:
    return [o for o in scene.get("objects") or []
            if str(o.get("type", "")).startswith("person")]


def _face_point(o: dict) -> tuple[float, float, float]:
    p = o.get("position") or [0, 0, 0]
    h = float((o.get("props") or {}).get("height") or 0) / 100.0
    pose = (o.get("props") or {}).get("pose", "standing")
    face = (h * 0.93) if h > 0.5 else FACE_HEIGHT
    if pose == "sitting":
        face *= 0.72
    elif pose == "lying":
        face = 0.35
    return (float(p[0]), face, float(p[2]))


def subject_point(scene: dict) -> tuple[float, float, float]:
    """Visage du sujet : barycentre des personnages (sinon devant la caméra)."""
    faces = [_face_point(o) for o in _people(scene)]
    if faces:
        return tuple(sum(f[i] for f in faces) / len(faces) for i in range(3))
    cam = _shot_camera(scene)
    if cam:
        (cx, _, cz), fwd, _ = _cam_frame(cam)
        return (cx + fwd[0] * 3, FACE_HEIGHT, cz + fwd[1] * 3)
    return (0.0, FACE_HEIGHT, 0.0)


def _fmt_m(v: float) -> str:
    v = round(v * 2) / 2 if v >= 2 else round(v, 1)
    return f"{v:.1f}".rstrip("0").rstrip(".").replace(".", ",") + " m"


# ---------------------------------------------------------------------- personnages
def _frame_place(cam, point) -> tuple[str, str, float]:
    """(côté du cadre, profondeur, distance) d'un point vu par la caméra du plan."""
    (cx, _, cz), fwd, right = _cam_frame(cam)
    dx, dz = point[0] - cx, point[2] - cz
    depth = dx * fwd[0] + dz * fwd[1]
    lateral = dx * right[0] + dz * right[1]
    dist = math.hypot(dx, dz)
    if depth <= 0.1:
        return "hors champ (derrière la caméra)", "", dist
    half = math.radians(_hfov(cam) / 2)
    x = (lateral / depth) / math.tan(half)          # -1 = bord gauche, +1 = bord droit
    if abs(x) > 1.05:
        side = "hors champ " + ("à droite" if x > 0 else "à gauche")
    elif x < -0.33:
        side = "à gauche du cadre"
    elif x > 0.33:
        side = "à droite du cadre"
    else:
        side = "au centre du cadre"
    return side, "", dist


def _depth_word(dist: float, nearest: float) -> str:
    if dist <= nearest + 0.6:
        return "au premier plan"
    if dist <= nearest + 2.5:
        return "au second plan"
    return "à l'arrière-plan"


def _orientation(cam, o) -> str:
    """Comment le personnage se présente à la caméra (face, 3/4, profil, dos)."""
    (cx, _, cz), _f, _r = _cam_frame(cam)
    p = o.get("position") or [0, 0, 0]
    yaw = float((o.get("rotation") or [0, 0, 0])[1])
    facing = (math.sin(yaw), math.cos(yaw))
    to_cam = (cx - float(p[0]), cz - float(p[2]))
    n = math.hypot(*to_cam) or 1e-6
    cosang = max(-1.0, min(1.0, (facing[0] * to_cam[0] + facing[1] * to_cam[1]) / n))
    a = math.degrees(math.acos(cosang))
    if a <= 25:
        return "face caméra"
    if a <= 65:
        return "de 3/4 face"
    if a <= 115:
        return "de profil"
    if a <= 155:
        return "de 3/4 dos"
    return "de dos"


_POSE_WORDS = {"sitting": "assis", "lying": "allongé", "walking": "en marche", "crossed": "bras croisés",
               "phone": "au téléphone", "pointing": "qui montre du doigt", "handsup": "bras levés"}
_FEMININE = {"assis": "assise", "allongé": "allongée"}


def _pose_word(o: dict, pose: str) -> str:
    w = _POSE_WORDS.get(pose or "", "")
    return _FEMININE.get(w, w) if o.get("type") == "person-woman" else w


def actors_summary(scene: dict) -> str:
    """Placement des personnages vus par la caméra du plan (section [MISE EN SCÈNE])."""
    cam = _shot_camera(scene)
    people = _people(scene)
    if not cam:
        return ""
    if not people:
        return motion_summary(scene)      # un animal ou un véhicule peut bouger seul dans le plan
    places = [(o, *_frame_place(cam, _face_point(o))) for o in people]
    nearest = min((d for _o, _s, _x, d in places), default=0.0)
    bits = []
    for o, side, _x, dist in places:
        words = [o.get("name") or "Personnage"]
        pose = _pose_word(o, (o.get("props") or {}).get("pose", ""))
        if pose:
            words.append(pose)
        if side.startswith("hors champ"):
            words.append(side)
        else:
            words.append(f"{_depth_word(dist, nearest)} {side}")
            words.append(_orientation(cam, o))
            words.append(f"à {_fmt_m(dist)} de la caméra")
        bits.append(", ".join(words))
    out = "Personnages (vus par la caméra du plan) : " + " ; ".join(bits) + "."
    moves = motion_summary(scene)
    return f"{out} {moves}" if moves else out


def _on_image(scene: dict) -> set:
    """Identifiants des éléments visibles à l'image (mobilier, décor, animaux, véhicules…), selon
    la bibliothèque (analyse écrite par la vue 3D) : ni le matériel de plateau, ni le grip."""
    ana = (scene.get("pandora") or {}).get("analysis") or {}
    return {o.get("id") for o in ana.get("objects") or []}


def decor_summary(scene: dict) -> str:
    """Ce qu'on a posé dans le décor, vu par la caméra du plan (ce qui est hors champ est tu)."""
    cam = _shot_camera(scene)
    visible = _on_image(scene)
    if not cam or not visible:
        return ""
    items = [o for o in scene.get("objects") or [] if o.get("id") in visible]
    places = [(o, *_frame_place(cam, (float((o.get("position") or [0, 0, 0])[0]), 1.0,
                                      float((o.get("position") or [0, 0, 0])[2])))) for o in items]
    places = [x for x in places if not x[1].startswith("hors champ")]
    if not places:
        return ""
    nearest = min(d for _o, _s, _x, d in places)
    bits = [f"{o.get('name') or 'Élément'} {_depth_word(dist, nearest)} {side}, à {_fmt_m(dist)} de la caméra"
            for o, side, _x, dist in places]
    return "Éléments du décor : " + " ; ".join(bits) + "."


_ACTIONS: dict | None = None


def actions() -> dict:
    """Catalogue des actions des personnages (scene3d_web/characters/actions.json) — le MÊME
    fichier que celui de la vue 3D : l'animation jouée et le verbe écrit ne divergent jamais."""
    global _ACTIONS
    if _ACTIONS is None:
        import json
        import os
        from core.paths import assets_root
        try:
            with open(os.path.join(assets_root(), "scene3d_web", "characters", "actions.json"),
                      encoding="utf-8") as f:
                _ACTIONS = {a["id"]: a for a in json.load(f).get("actions", [])}
        except (OSError, ValueError, KeyError):
            _ACTIONS = {}
    return _ACTIONS


_FEM_WORDS = (("assis", "assise"), ("accroupi", "accroupie"), ("projeté", "projetée"))


def _agree(o: dict, verb: str) -> str:
    if o.get("type") != "person-woman":
        return verb
    for m, f in _FEM_WORDS:
        verb = re.sub(rf"\b{m}\b", f, verb)
    return verb


def _auto_action(moving: bool, speed: float) -> str:
    if not moving:
        return ""
    return "sprint" if speed > 4.2 else "jog" if speed > 2.0 else "walk"


def motion_summary(scene: dict) -> str:
    """Mise en scène minutée d'après les marques de la frise : « Paul, de 0 s à 2,2 s, marche sur
    2,3 m, entre dans le champ par la gauche, puis de 2,2 s à 2,6 s s'assoit »."""
    tracks = (scene.get("pandora") or {}).get("tracks") or {}
    if not tracks:
        return ""
    cam = _shot_camera(scene)
    acts = actions()
    by_id = {o.get("id"): o for o in scene.get("objects") or []}
    duration = float((scene.get("pandora") or {}).get("duration") or 0)
    bits = []
    for oid, keys in tracks.items():
        o = by_id.get(oid)
        keys = sorted((k for k in keys or [] if isinstance(k, dict) and k.get("p")),
                      key=lambda k: float(k.get("t", 0)))
        if not o or len(keys) < 2 or o is cam:
            continue
        person = str(o.get("type", "")).startswith("person")
        if not person and oid not in _on_image(scene):
            continue                  # matériel de plateau, grip : jamais à l'image
        steps = []
        for a, b in zip(keys, keys[1:]):
            pa, pb = a["p"], b["p"]
            d = math.hypot(pb[0] - pa[0], pb[2] - pa[2])
            dt = max(0.05, float(b.get("t", 0)) - float(a.get("t", 0)))
            moving = d >= 0.2
            act = acts.get(a.get("action") or _auto_action(moving, d / dt), {}) if person else {}
            when = f"de {_fmt_s(a.get('t', 0))} à {_fmt_s(b.get('t', 0))}"
            note = str(a.get("note") or "").strip()
            if moving:
                verb = (act.get("verb") if act.get("move") else
                        (acts.get(_auto_action(True, d / dt), {}).get("verb") or "se déplace")) if person else "se déplace"
                path = _path_phrase(cam, pa, pb) if cam else ""
                # une action sur place se joue d'abord, puis le personnage repart (comme dans la vue)
                lead = f"{_agree(o, act['verb'])}, puis " if act and not act.get("move") and act.get("verb") else ""
                steps.append(f"{when} {lead}{_agree(o, verb)} sur {_fmt_m(d)}" + (f", {path}" if path else "")
                             + (f" ({note})" if note else ""))
            elif act.get("verb"):
                steps.append(f"{when} {_agree(o, act['verb'])}" + (f" ({note})" if note else ""))
            elif note:
                steps.append(f"{when} {note}")
        last = keys[-1]
        tail = acts.get(last.get("action") or "", {}) if person else {}
        if tail.get("verb") and (not duration or float(last.get("t", 0)) < duration - 0.05):
            steps.append(f"à partir de {_fmt_s(last.get('t', 0))} {_agree(o, tail['verb'])}")
        if steps:
            bits.append(f"{o.get('name') or 'Personnage'}, " + ", puis ".join(steps))
    return ("Déplacements : " + " ; ".join(bits) + ".") if bits else ""


def camera_motion_summary(scene: dict) -> str:
    """Mouvement de la caméra du plan d'après ses keyframes : travelling avant / arrière / latéral,
    montée et descente sur le pied, panoramique horizontal et vertical, en restant dans le repère de
    la caméra (ce que verra le spectateur). Une valeur absente d'une keyframe reprend la précédente."""
    cam = _shot_camera(scene)
    if not cam:
        return ""
    keys = sorted((k for k in ((scene.get("pandora") or {}).get("tracks") or {}).get(cam.get("id"), [])
                   if isinstance(k, dict) and k.get("p")), key=lambda k: float(k.get("t", 0)))
    if len(keys) < 2:
        return ""
    steps = []
    lens = float((cam.get("props") or {}).get("lens") or 1.45)
    pitch = 0.0
    for a, b in zip(keys, keys[1:]):
        lens_a = float(a.get("lens", lens))
        lens_b = float(b.get("lens", lens_a))
        lens = lens_b
        pitch_a = float(a.get("pitch", pitch))
        pitch_b = float(b.get("pitch", pitch_a))
        pitch = pitch_b
        yaw_a = float(a.get("yaw", (cam.get("rotation") or [0, 0, 0])[1]))
        yaw_b = float(b.get("yaw", yaw_a))
        fwd = (math.sin(yaw_a), math.cos(yaw_a))
        right = (-fwd[1], fwd[0])
        dx, dz = b["p"][0] - a["p"][0], b["p"][2] - a["p"][2]
        along, side = dx * fwd[0] + dz * fwd[1], dx * right[0] + dz * right[1]
        turn = math.degrees(math.remainder(yaw_b - yaw_a, 2 * math.pi))
        parts = []
        if abs(along) >= 0.2:
            parts.append(f"travelling {'avant' if along > 0 else 'arrière'} de {_fmt_m(abs(along))}")
        if abs(side) >= 0.2:
            parts.append(f"travelling latéral vers la {'droite' if side > 0 else 'gauche'} de {_fmt_m(abs(side))}")
        if abs(turn) >= 5:
            # lacet croissant = rotation vers la gauche de l'image (repère y vers le haut)
            parts.append(f"panoramique vers la {'gauche' if turn > 0 else 'droite'} de {abs(turn):.0f}°")
        rise = lens_b - lens_a
        if abs(rise) >= 0.05:
            parts.append(f"{'montée' if rise > 0 else 'descente'} de la caméra de {_fmt_m(abs(rise))} "
                         f"(de {_fmt_m(lens_a)} à {_fmt_m(lens_b)} du sol)")
        tilt = math.degrees(pitch_b - pitch_a)     # tangage positif : l'objectif descend
        if abs(tilt) >= 3:
            parts.append(f"panoramique vertical vers le {'bas' if tilt > 0 else 'haut'} de {abs(tilt):.0f}°")
        if parts:
            steps.append(f"de {_fmt_s(a.get('t', 0))} à {_fmt_s(b.get('t', 0))}, " + " et ".join(parts))
    return ("Mouvement de caméra : " + " ; puis ".join(steps) + ".") if steps else ""


_ZONE = {"à gauche du cadre": "la gauche du cadre", "à droite du cadre": "la droite du cadre",
         "au centre du cadre": "le centre du cadre"}


def _path_phrase(cam, pa, pb) -> str:
    """Trajet vu de la caméra : entrée, sortie, traversée, approche ou recul."""
    sa = _frame_place(cam, (pa[0], FACE_HEIGHT, pa[2]))[0]
    sb = _frame_place(cam, (pb[0], FACE_HEIGHT, pb[2]))[0]
    (cx, _, cz), _f, _r = _cam_frame(cam)
    da, db = math.hypot(pa[0] - cx, pa[2] - cz), math.hypot(pb[0] - cx, pb[2] - cz)
    out_a, out_b = sa.startswith("hors champ"), sb.startswith("hors champ")
    if out_a and not out_b:
        side = "par la gauche" if "gauche" in sa else "par la droite" if "droite" in sa else "depuis l'avant-plan"
        return f"entre dans le champ {side} et s'arrête vers {_ZONE.get(sb, 'le cadre')}"
    if out_b and not out_a:
        side = "par la gauche" if "gauche" in sb else "par la droite" if "droite" in sb else "par l'avant-plan"
        return f"sort du champ {side}"
    if out_a and out_b:
        return "hors champ"
    parts = []
    if sa != sb:
        parts.append(f"traverse de {_ZONE.get(sa, sa)} vers {_ZONE.get(sb, sb)}")
    if db < da - 0.6:
        parts.append("s'approche de la caméra")
    elif db > da + 0.6:
        parts.append("s'éloigne de la caméra")
    return " et ".join(parts) or f"reste vers {_ZONE.get(sb, 'le cadre')}"


def _fmt_s(t) -> str:
    v = round(float(t or 0), 1)
    return (f"{v:.1f}".rstrip("0").rstrip(".").replace(".", ",")) + " s"


# ---------------------------------------------------------------------- lumière
def _light_data(scene: dict) -> list[dict]:
    """Projecteurs avec les données physiques écrites par la vue (analyse) ; repli
    raisonnable si l'analyse manque (scène jamais ouverte dans la vue 3D)."""
    ana = {f.get("id"): f for f in ((scene.get("pandora") or {}).get("analysis") or {}).get("fixtures") or []}
    out = []
    for f in scene.get("fixtures") or []:
        a = dict(ana.get(f.get("id")) or {})
        st = f.get("state") or {}
        man = st.get("manual") or {}
        a.setdefault("name", f.get("name", ""))
        a.setdefault("power", st.get("power", True))
        a.setdefault("intensity", float(man.get("intensity", 0.6)))
        a.setdefault("mode", man.get("mode", "cct"))
        a.setdefault("cct", man.get("cct", 5600) if a["mode"] == "cct" else None)
        a.setdefault("hue", man.get("hue") if a["mode"] == "hsi" else None)
        a.setdefault("sat", man.get("sat") if a["mode"] == "hsi" else None)
        a.setdefault("lux_at_1m", 8000)
        a.setdefault("beam_deg", 50)
        a.setdefault("size_m", 0.3)
        a.setdefault("soft", False)
        a["position"] = f.get("position") or a.get("position") or [0, 2, 3]
        a["rotation"] = f.get("rotation") or a.get("rotation") or [0, 0, 0]
        a["role"] = (f.get("pandora") or {}).get("role", "")
        out.append(a)
    return out


def _lux_at(light: dict, point) -> float:
    """Éclairement (lux) reçu au point : inverse du carré × position dans le faisceau."""
    p = light["position"]
    v = (point[0] - p[0], point[1] - p[1], point[2] - p[2])
    d = math.sqrt(sum(c * c for c in v)) or 1e-6
    fwd = S.forward_from_rotation(light["rotation"])
    cosang = max(-1.0, min(1.0, sum(fwd[i] * v[i] for i in range(3)) / d))
    off = math.degrees(math.acos(cosang))
    half = max(5.0, float(light.get("beam_deg") or 50) / 2)
    k = 1.0 if off <= half else math.exp(-((off - half) / (0.35 * half)) ** 2)
    return float(light.get("lux_at_1m") or 0) * float(light.get("intensity") or 0) * k / (d * d)


def _direction(cam, subject, light) -> tuple[str, float, str]:
    """Direction d'un projecteur vue de la caméra : (libellé, angle 0=face/180=contre, côté)."""
    (cx, _, cz), _f, right = _cam_frame(cam)
    to_cam = (cx - subject[0], cz - subject[2])
    to_l = (light[0] - subject[0], light[2] - subject[2])
    n1, n2 = math.hypot(*to_cam) or 1e-6, math.hypot(*to_l) or 1e-6
    cosang = max(-1.0, min(1.0, (to_cam[0] * to_l[0] + to_cam[1] * to_l[1]) / (n1 * n2)))
    phi = math.degrees(math.acos(cosang))
    sd = (to_l[0] * right[0] + to_l[1] * right[1]) / n2
    side = "droit" if sd > 0.15 else ("gauche" if sd < -0.15 else "")
    sfx = f" côté {side} de l'image" if side else ""
    if phi <= 25:
        return "de face, depuis l'axe de la caméra", phi, side
    if phi <= 65:
        return f"de 3/4 face{sfx}", phi, side
    if phi <= 115:
        return f"latérale (90°){sfx}", phi, side
    if phi <= 155:
        return f"de 3/4 arrière{sfx}", phi, side
    return "depuis l'arrière du sujet, face à la caméra", phi, side


def _height_word(light_pos, subject) -> str:
    dy = light_pos[1] - subject[1]
    d = math.hypot(light_pos[0] - subject[0], light_pos[2] - subject[2]) or 1e-6
    el = math.degrees(math.atan2(dy, d))
    if el >= 60:
        return "tombant presque à la verticale (douche de lumière)"
    if el >= 30:
        return "en plongée marquée"
    if el >= 10:
        return "légèrement plongeante"
    if el >= -10:
        return "à hauteur du visage"
    return "venant du bas (contre-plongée)"


def _quality(light: dict, dist: float) -> str:
    size = float(light.get("size_m") or 0.2)
    apparent = size / max(0.3, dist)          # taille apparente (radians, approx.)
    if (light.get("soft") and apparent >= 0.12) or apparent >= 0.3:
        return "douce, ombres fondues"
    if apparent >= 0.1 or light.get("soft"):
        return "semi-douce"
    return "dure, ombres nettes"


def _color(light: dict) -> str:
    try:
        from core.projectors import kelvin_label, _hue_label
    except Exception:
        kelvin_label = lambda k: f"{k} K"          # noqa: E731
        _hue_label = lambda h: f"teinte {h}°"      # noqa: E731
    if light.get("mode") == "hsi" and float(light.get("sat") or 0) > 0.15:
        sat = float(light.get("sat") or 0)
        return f"colorée {_hue_label(int(light.get('hue') or 0))}" + (" saturée" if sat > 0.7 else " pastel")
    cct = int(light.get("cct") or 5600)
    out = f"{cct} K ({kelvin_label(cct)})"
    if light.get("gel"):
        out += f", gélatine {light['gel']}"
    return out


def lighting_summary(scene: dict) -> str:
    """Section [PLAN DE FEU] : chaque source dite par rapport à la caméra, puis le bilan."""
    cam = _shot_camera(scene)
    subject = subject_point(scene)
    lights = [l for l in _light_data(scene) if l.get("power", True) and float(l.get("intensity") or 0) > 0.02]
    if not lights:
        return ""
    for l in lights:
        l["_lux"] = _lux_at(l, subject)
        l["_dist"] = math.dist(l["position"], subject)
        if cam:
            l["_dir"], l["_phi"], l["_side"] = _direction(cam, subject, l["position"])
        else:
            l["_dir"], l["_phi"], l["_side"] = "", 0.0, ""
    lit = [l for l in lights if l["_lux"] >= 1.0]
    if not lit:
        return ("Éclairage : les sources posées n'atteignent pas les personnages (hors faisceau "
                "ou trop loin) ; image sombre, éclairée seulement par l'ambiance.")
    front = [l for l in lit if l["_phi"] <= 115]
    back = [l for l in lit if l["_phi"] > 115]
    key = max(front or lit, key=lambda l: l["_lux"])
    fills = [l for l in front if l is not key]
    fill_lux = sum(l["_lux"] for l in fills)

    def role(l):
        r = l.get("role") or ""
        named = {"key": "lumière principale", "fill": "débouchage", "back": "contre-jour",
                 "rim": "liseré", "eye": "lumière d'œil", "background": "lumière du fond",
                 "practical": "source dans le décor", "ambient": "ambiance générale"}
        if r in named:
            return named[r]
        if l is key:
            return "lumière principale"
        if l in back:
            return "contre-jour" if l["_phi"] > 155 else "liseré (3/4 arrière)"
        return "débouchage" if l["_lux"] < key["_lux"] * 0.7 else "seconde source principale"

    order = [key] + sorted([l for l in lit if l is not key], key=lambda l: -l["_lux"])
    bits = []
    for l in order[:6]:
        share = 100 * l["_lux"] / max(1e-6, key["_lux"])
        strength = "" if l is key else (f", environ {share:.0f} % de la principale" if share < 95 else ", aussi forte que la principale")
        bits.append(f"{role(l)} {l['_dir']}, {_height_word(l['position'], subject)}, "
                    f"{_quality(l, l['_dist'])}, {_color(l)}{strength}")
    # bilan : contraste et dominante
    if fill_lux > 0:
        ratio = (key["_lux"] + fill_lux) / max(1e-6, fill_lux)
        if ratio < 2.5:
            contrast = f"contraste doux (rapport principale/débouchage ≈ 1:{ratio:.0f}, image claire et peu modelée)"
        elif ratio < 5:
            contrast = f"modelé marqué (rapport ≈ 1:{ratio:.0f})"
        else:
            contrast = f"fort contraste, côté ombre très sombre (rapport ≈ 1:{ratio:.0f})"
    else:
        contrast = "sans débouchage : le côté ombre du visage tombe dans le noir (clair-obscur)"
    total = key["_lux"] + fill_lux
    level = ("basse lumière, ambiance sombre" if total < 120 else
             "lumière franche et lumineuse" if total > 2000 else "exposition équilibrée")
    warm = [l for l in lit if l.get("mode") == "cct" and int(l.get("cct") or 5600) <= 3600]
    cold = [l for l in lit if l.get("mode") == "cct" and int(l.get("cct") or 5600) >= 6000]
    mix = ""
    if warm and cold:
        mix = " ; mélange de températures : sources chaudes et sources froides dans la même image"
    text = ("Éclairage (directions VUES DE LA CAMÉRA) : " + " ; ".join(bits) + ". "
            f"Bilan : {contrast}, {level}{mix}. ")
    text += ("IMPORTANT : aucun projecteur ni appareil d'éclairage n'est visible à l'image — "
             "ces lignes décrivent uniquement la lumière, sa direction et son caractère.")
    return text


# ---------------------------------------------------------------------- caméra
def camera_summary(scene: dict) -> str:
    cam = _shot_camera(scene)
    if not cam:
        return ""
    props = cam.get("props") or {}
    subject = subject_point(scene)
    (cx, lens, cz), _f, _r = _cam_frame(cam)
    dist = math.hypot(subject[0] - cx, subject[2] - cz)
    dy = lens - subject[1]
    tilt = math.degrees(math.atan2(dy, max(0.3, dist)))
    # caméra réellement basculée : son axe décide, pas la seule différence de hauteur
    aim = S.forward_from_rotation(cam.get("rotation") or [0, 0, 0])[1]
    if abs(aim) > math.sin(math.radians(3)):
        tilt = math.degrees(math.asin(max(-1.0, min(1.0, -aim))))
    angle = ("caméra en plongée" if tilt > 12 else "caméra en contre-plongée" if tilt < -12
             else "caméra à hauteur des yeux")
    out = (f"Caméra à {_fmt_m(lens)} du sol, objectif {int(float(props.get('focal') or 35))} mm "
           f"(champ horizontal {_hfov(cam):.0f}°), à {_fmt_m(dist)} du sujet, {angle}.")
    move = camera_motion_summary(scene)
    return f"{out} {move}" if move else out


def axis_label(scene: dict) -> str:
    """Axe caméra du storyboard (Face / 3/4 / Latéral 90° / Dos) d'après la scène."""
    cam = _shot_camera(scene)
    people = _people(scene)
    if not cam or not people:
        return ""
    o = people[0]
    o_word = _orientation(cam, o)
    return {"face caméra": "Face", "de 3/4 face": "3/4", "de profil": "Latéral 90°",
            "de 3/4 dos": "Dos", "de dos": "Dos"}.get(o_word, "")


# ---------------------------------------------------------------------- inscription
def staging_text(scene: dict) -> str:
    """Section [🎭 MISE EN SCÈNE] : caméra et ses mouvements, personnages et leurs actions, décor."""
    parts = [camera_summary(scene), actors_summary(scene), decor_summary(scene)]
    return " ".join(p for p in parts if p)


def texts(scene: dict) -> dict:
    """Ce que « Inscrire dans le storyboard » écrira pour cette scène."""
    try:
        return {"staging": staging_text(scene), "lighting": lighting_summary(scene)}
    except Exception:
        return {}


def _shot_fields(scene: dict) -> dict:
    cam = _shot_camera(scene)
    if not cam:
        return {}
    props = cam.get("props") or {}
    subject = subject_point(scene)
    pos = cam.get("position") or [0, 0, 0]
    dist = ((subject[0] - pos[0]) ** 2 + (subject[2] - pos[2]) ** 2) ** 0.5
    return {"camera_axis": axis_label(scene),
            "camera_distance": f"{round(dist * 2) / 2:g}m",
            "camera_height": f"{float(props.get('lens') or 1.45):g} m",
            "focal": f"{int(props.get('focal') or 35)}mm"}


def pending(shot: dict, scene: dict) -> bool:
    """La scène dit-elle autre chose que le prompt du plan ? (bouton « Inscrire » actif)"""
    from core.prompt_sections import parse
    sec = parse(shot.get("seedance_prompt", "") or "")
    t = texts(scene)
    if any(t.get(k) and t.get(k) != sec.get(s, "") for k, s in (("staging", "staging"), ("lighting", "lighting"))):
        return True
    return any(v and shot.get(k) != v for k, v in _shot_fields(scene).items())


def write_to_shot(shot: dict, scene: dict) -> bool:
    """Écrit la scène dans le plan (sections du prompt + champs techniques) et retient ce qui a été
    inscrit dans la scène. True si le plan a changé : à enregistrer par l'appelant. Seule cette
    fonction écrit : le prompt ne bouge jamais tout seul (Matthieu, 30/10/2026)."""
    from core.prompt_sections import build, parse
    t = texts(scene)
    cur = shot.get("seedance_prompt", "") or ""
    sec = parse(cur)
    changed = False
    for key, sect in (("staging", "staging"), ("lighting", "lighting")):
        val = t.get(key, "")
        if val and val != sec.get(sect, ""):
            sec[sect] = val
            changed = True
    for k, v in _shot_fields(scene).items():
        if v and shot.get(k) != v:
            shot[k] = v
            changed = True
    scene.setdefault("pandora", {})["inscribed"] = {"actors": t.get("staging", ""), "lighting": t.get("lighting", "")}
    if not changed:
        return False
    sec["action"] = sec.get("action") or cur
    sec["sound"] = sec.get("sound", "") or (shot.get("sound_prompt") or "")
    shot["seedance_prompt"] = build(**sec)
    return True


# ---------------------------------------------------------------------- par plan
def for_shot(shot_id: str) -> dict | None:
    """Textes du plan si une scène 3D existe : {"actors", "lighting", "camera"}, sinon None. Une fois
    le plan inscrit, ce sont les textes INSCRITS qui valent, pas la scène en cours de travail : une
    recomposition du prompt n'y fait pas entrer des modifications qu'on n'a pas voulu inscrire."""
    scene = S.load(shot_id)
    if scene is None:
        return None
    done = (scene.get("pandora") or {}).get("inscribed")
    if isinstance(done, dict):
        return {"actors": done.get("actors", ""), "lighting": done.get("lighting", ""), "camera": ""}
    try:
        return {"actors": staging_text(scene), "lighting": lighting_summary(scene), "camera": ""}
    except Exception:
        return None
