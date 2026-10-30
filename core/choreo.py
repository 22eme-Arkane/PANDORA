"""core/choreo.py — Claude chorégraphe : la mise en scène décrite en mots devient des marques.

Demande Matthieu (29/10/2026) : « vous décrivez l'action ou la chorégraphie, Claude remplit la
frise ». Claude ne touche JAMAIS au moteur 3D : il reçoit la scène du plan résumée (personnages,
caméra, décor, en mètres) et le catalogue des actions, et répond par des DONNÉES — des marques
{t, p, yaw, action} — que l'on vérifie une à une avant de les poser sur la frise (la recherche du
29/10 déconseille de faire écrire du code 3D à une IA : gestes faux, résultats imprévisibles).

Pur Python, sans interface : core/choreo.py construit la demande et valide la réponse ;
ui/page_3d.py lance l'appel (tâche « choreography » de core/ai_provider) dans un fil.
"""
from __future__ import annotations

import json
import math
import re

TASK = "choreography"
MAX_RANGE_M = 30.0          # au-delà, une marque est hors du plateau
MOVABLE_CATS = ("person", "camera", "dolly")

SYSTEM = """Tu es le chorégraphe d'un logiciel de pré-production de cinéma. On te donne la
scène 3D d'UN plan (positions en mètres) et ce que le réalisateur veut voir. Tu réponds par les
MARQUES de chaque personnage (et de la caméra si on te demande un mouvement de caméra) sur la
durée du plan. Ta réponse est UNIQUEMENT un objet JSON valide, sans texte autour.

REPÈRE
- Sol = plan x/z en mètres, y vers le haut (les personnages ont toujours y = 0).
- Lacet (yaw, radians) : 0 = regarde vers +z ; pour regarder dans la direction (dx, dz), yaw = atan2(dx, dz).
- La caméra du plan regarde selon son lacet ; pour elle, la DROITE DE L'IMAGE est la direction
  (-cos(yaw), sin(yaw)) et la gauche son opposé. « Entre par la gauche » = part d'une position
  hors du champ côté gauche de l'image.

MARQUES
- Une marque = {"t": secondes, "p": [x, 0, z], "yaw": radians (facultatif), "action": "id"}.
- La première marque de chaque personnage est à t = 0 : sa position de départ.
- L'action d'une marque vaut jusqu'à la marque suivante. Entre deux marques à des positions
  différentes, le personnage se déplace en ligne droite, tourné dans le sens de la marche :
  donne alors à la marque de départ une action de déplacement (ou aucune : marche / course
  choisie selon la vitesse). Vitesses réalistes : marche 1,1-1,5 m/s, course 2,5-4 m/s.
- Pour une action sur place (s'asseoir, parler, frapper…), pose deux marques à la même
  position : la première porte l'action, la suivante marque sa fin (ou laisse-la courir
  jusqu'à la fin du plan). Une action jouée une fois (s'assoit, jab…) dure environ 1 à 2 s.
- Caméra : "p" reste [x, 0, z] et sa marque peut porter "lens" (hauteur de l'objectif en mètres,
  de 0,2 à 6 : c'est ainsi qu'elle monte et descend sur son pied) et "pitch" (radians, positif =
  l'objectif descend). Son lacet ne suit pas le déplacement : un travelling garde son orientation.
- N'utilise QUE les identifiants d'action du catalogue fourni, et QUE les identifiants
  d'objets fournis. Ne crée pas de personnage.
- Reste dans le plateau (sol fourni), évite de traverser les meubles, et garde dans le
  cadre de la caméra ce que le réalisateur veut voir.

RÉPONSE
{"notes": "une phrase en français qui résume la mise en scène",
 "tracks": {"<id objet>": [ {marque}, … ], …}}
Les personnages que la demande ne concerne pas sont simplement absents de "tracks"."""


def _r(v, n=3):
    return round(float(v), n)


def _catalog_brief(actions: dict) -> list[dict]:
    return [{"id": a["id"], "fr": a.get("fr", ""), "deplacement": bool(a.get("move")),
             "une_fois": bool(a.get("once"))} for a in actions.values()]


def movable(scene: dict) -> dict:
    """Objets que Claude peut faire bouger : personnages et caméra du plan (id -> objet)."""
    cam_id = (scene.get("pandora") or {}).get("shot_camera")
    out = {}
    for o in scene.get("objects") or []:
        t = str(o.get("type", ""))
        if t.startswith("person") or o.get("id") == cam_id:
            out[o.get("id")] = o
    return out


def brief(scene: dict, shot: dict | None = None) -> dict:
    """Résumé compact de la scène pour Claude (jamais la scène brute : pas de réglages DMX)."""
    from core import scene3d_prompt as P
    p = scene.get("pandora") or {}
    cam = P._shot_camera(scene)
    span = float(p.get("span_m") or 10.0)
    people, decor = [], []
    for o in scene.get("objects") or []:
        pos = [_r(c, 2) for c in (o.get("position") or [0, 0, 0])]
        yaw = _r((o.get("rotation") or [0, 0, 0])[1], 3)
        if str(o.get("type", "")).startswith("person"):
            people.append({"id": o.get("id"), "nom": o.get("name", ""),
                           "silhouette": o.get("type", "").replace("person-", ""),
                           "p": pos, "yaw": yaw,
                           "marques_actuelles": p.get("tracks", {}).get(o.get("id"), [])})
        elif o is not cam:
            decor.append({"id": o.get("id"), "nom": o.get("name", ""), "type": o.get("type", ""), "p": pos})
    out = {
        "duree_s": float(p.get("duration") or 5),
        "sol": {"x": [-span / 2, span / 2], "z": [-span / 2, span / 2]},
        "personnages": people,
        "decor": decor,
    }
    if cam:
        props = cam.get("props") or {}
        out["camera"] = {"id": cam.get("id"), "p": [_r(c, 2) for c in cam.get("position") or [0, 0, 0]],
                         "yaw": _r((cam.get("rotation") or [0, 0, 0])[1], 3),
                         "hauteur_objectif_m": float(props.get("lens") or 1.45),
                         "focale_mm": int(float(props.get("focal") or 35)),
                         "champ_horizontal_deg": round(P._hfov(cam)),
                         "placement_actuel": P.actors_summary(scene)}
    if shot:
        out["plan"] = {"titre": shot.get("scene_title", ""), "valeur": shot.get("shot_size", ""),
                       "axe": shot.get("camera_axis", "")}
    return out


def messages(scene: dict, request: str, shot: dict | None = None) -> tuple[str, list]:
    """(système, messages) de l'appel — la scène et le catalogue en JSON, la demande en clair."""
    from core.scene3d_prompt import actions
    user = ("SCÈNE DU PLAN :\n" + json.dumps(brief(scene, shot), ensure_ascii=False)
            + "\n\nACTIONS DISPONIBLES :\n" + json.dumps(_catalog_brief(actions()), ensure_ascii=False)
            + "\n\nCE QUE LE RÉALISATEUR VEUT :\n" + (request or "").strip())
    return SYSTEM, [{"role": "user", "content": user}]


def _extract_json(text: str) -> dict:
    """L'objet JSON de la réponse (tolère un bloc ```json``` ou une phrase autour)."""
    t = (text or "").strip()
    m = re.search(r"```(?:json)?\s*(\{.*\})\s*```", t, re.S)
    if m:
        t = m.group(1)
    a, b = t.find("{"), t.rfind("}")
    if a < 0 or b <= a:
        raise ValueError("la réponse ne contient pas de JSON")
    return json.loads(t[a:b + 1])


def parse(text: str, scene: dict) -> dict:
    """Réponse de Claude -> {"tracks": {id: marques}, "notes": str, "warnings": [str]}.
    Tout ce qui est douteux est écarté ET signalé : objet inconnu, action hors catalogue,
    temps ou position hors du plan."""
    from core.scene3d_prompt import actions
    data = _extract_json(text)
    acts = actions()
    objs = movable(scene)
    duration = float((scene.get("pandora") or {}).get("duration") or 5)
    warnings: list[str] = []
    tracks: dict = {}
    for oid, marks in (data.get("tracks") or {}).items():
        o = objs.get(oid)
        if o is None:
            warnings.append(f"objet inconnu ou immobile ignoré : {oid}")
            continue
        person = str(o.get("type", "")).startswith("person")
        clean = []
        for mk in marks if isinstance(marks, list) else []:
            try:
                t = float(mk.get("t"))
                p = [float(c) for c in mk.get("p")][:3]
            except (TypeError, ValueError, AttributeError):
                warnings.append(f"{o.get('name') or oid} : marque illisible ignorée")
                continue
            if len(p) != 3 or not all(math.isfinite(c) for c in p) or max(abs(p[0]), abs(p[2])) > MAX_RANGE_M:
                warnings.append(f"{o.get('name') or oid} : marque hors du plateau ignorée")
                continue
            if not (-0.01 <= t <= duration + 0.01):
                warnings.append(f"{o.get('name') or oid} : marque à {t:g} s hors de la durée du plan")
                continue
            is_cam = str(o.get("type", "")).startswith("camera")
            out = {"t": _r(min(max(t, 0.0), duration)), "p": [_r(p[0]), 0.0 if person or is_cam else _r(p[1]), _r(p[2])]}
            for key in ("yaw", "lens", "pitch") if is_cam else ("yaw",):
                if mk.get(key) is not None:
                    try:
                        val = float(mk[key])
                        out[key] = _r(min(6.0, max(0.2, val)) if key == "lens" else val)
                    except (TypeError, ValueError):
                        pass
            act = str(mk.get("action") or "").strip()
            if act:
                if act in acts and person:
                    out["action"] = act
                elif person:
                    warnings.append(f"{o.get('name') or oid} : action inconnue « {act} » ignorée")
            clean.append(out)
        clean.sort(key=lambda m: m["t"])
        merged = []
        for mk in clean:      # deux marques au même instant : la dernière l'emporte
            if merged and abs(merged[-1]["t"] - mk["t"]) < 0.06:
                merged[-1] = mk
            else:
                merged.append(mk)
        if merged and merged[0]["t"] > 0.05:
            start = {"t": 0.0, "p": [_r(c) for c in (o.get("position") or [0, 0, 0])]}
            merged.insert(0, start)
        if len(merged) >= 2:
            tracks[oid] = merged
    return {"tracks": tracks, "notes": str(data.get("notes") or "").strip()[:400], "warnings": warnings}
