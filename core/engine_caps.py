"""
core/engine_caps.py — Capacités des moteurs vidéo vis-à-vis du workflow PANDORA.

Source de vérité PARTAGÉE (Cinéma + Live) pour « Générer depuis Séquences » /
« Générer depuis Storyboard ». Le workflow repose sur :
  - i2v        : image de DÉPART (mood keyframe, raccord dernière frame) ;
  - end_frame  : image de FIN (raccords par keyframes : mood N → mood N+1) ;
  - refs       : images de référence (façade, casting, style).

Capacités relevées sur NOS workers intégrés (api/real.py, api/video_engines.py) —
pas sur les specs marketing : un moteur n'est « compatible » que si notre code
sait réellement lui envoyer les images.

  refs : "full"  = multi-images avec rôles (Seedance ref-to-video, Happy Horse 9 imgs)
         "style" = 1 image d'ancrage de style seulement
         "none"  = aucune image de référence
"""

ENGINE_CAPS = {
    #                      i2v    end_frame  refs
    "seedance-2.0":      {"i2v": True,  "end_frame": True,  "refs": "full"},
    "seedance-2.0-fast": {"i2v": True,  "end_frame": True,  "refs": "full"},
    "kling-v3-pro":      {"i2v": True,  "end_frame": True,  "refs": "style"},
    "kling-o3-4k":       {"i2v": True,  "end_frame": False, "refs": "none"},
    "happy-horse-1.0":   {"i2v": True,  "end_frame": False, "refs": "full"},
    "pixverse-v6":       {"i2v": True,  "end_frame": False, "refs": "style"},
    # ÉCARTÉS du workflow séquences : text-to-video pur dans notre intégration
    # (aucune image acceptée → ni raccords ni keyframes ni façade possibles).
    "veo-3.1":           {"i2v": False, "end_frame": False, "refs": "none"},
    "sora-2":            {"i2v": False, "end_frame": False, "refs": "none"},
}


def workflow_compatible(key: str) -> bool:
    """True si le moteur peut suivre le workflow séquences (au minimum l'i2v)."""
    caps = ENGINE_CAPS.get(key)
    return bool(caps and (caps["i2v"] or caps["refs"] != "none"))


def caps_hint(key: str) -> str:
    """Suffixe court de capacités pour le libellé du combo."""
    caps = ENGINE_CAPS.get(key)
    if not caps:
        return ""
    bits = []
    if caps["end_frame"]:
        bits.append("keyframes")
    elif caps["i2v"]:
        bits.append("i2v début")
    if caps["refs"] == "full":
        bits.append("réfs")
    elif caps["refs"] == "style":
        bits.append("réf style")
    return " · ".join(bits)


def sequence_engines(all_engines: list) -> list:
    """Filtre une liste [(label, key)] aux moteurs compatibles workflow, en
    annotant le libellé avec les capacités réelles."""
    out = []
    for label, key in all_engines:
        if not workflow_compatible(key):
            continue   # écarté : t2v pur, incompatible avec moods/raccords/façade
        base = label.split("  (")[0].strip()
        hint = caps_hint(key)
        out.append((f"{base}  ({hint})" if hint else base, key))
    return out
