"""
Clips générés ↔ plans du storyboard (module NEUTRE : Cinéma et Live).

Le Studio range chaque clip sous « SQ{séquence}_P{plan}_NN.mp4 » (ou
« P{plan}_NN.mp4 » sans séquence) dans le dossier vidéo du projet
(core.config.get_output_dir) ; NN est le numéro de prise (core.download).
Ce module retrouve les prises de chaque plan et prépare ce qu'un montage
attend : ordre du storyboard, sous-chutier par séquence, métadonnées
(scène, plan, prise, action) et une couleur par séquence.

Sert au « Monter dans DaVinci Resolve » (Cinéma), à l'import automatique après
génération (Cinéma) et à l'export de timeline XML (les deux éditions).
"""

import os
import re

# Nom d'un clip rangé par le Studio. Les sorties dérivées (« .lb.mp4 »…) ne
# correspondent pas : le motif exige « _NN.mp4 » en fin de nom.
_CLIP_RE = re.compile(r"^(?:SQ(?P<seq>\d+)_)?P(?P<num>\d+)_(?P<take>\d+)\.mp4$", re.I)

# Couleurs de clip acceptées par DaVinci Resolve (SetClipColor), une par séquence.
CLIP_COLORS = ("Orange", "Yellow", "Lime", "Teal", "Blue", "Purple",
               "Pink", "Apricot", "Olive", "Navy", "Violet", "Tan")


def _int(value) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def shot_title(shot: dict) -> str:
    """« SQ3_P16 », « P16 » ou « plan » — même règle que le Studio (tab_t2v)."""
    seq, num = _int(shot.get("seq_num")), _int(shot.get("number"))
    if seq and num:
        return f"SQ{seq}_P{num}"
    if num:
        return f"P{num}"
    return "plan"


def sequence_bin(shot: dict) -> str:
    """Sous-chutier de la séquence (« SQ03 ») — vide sans numéro de séquence."""
    seq = _int(shot.get("seq_num"))
    return f"SQ{seq:02d}" if seq else ""


def sequence_color(shot: dict) -> str:
    seq = _int(shot.get("seq_num"))
    return CLIP_COLORS[(seq - 1) % len(CLIP_COLORS)] if seq else ""


def parse_clip_name(filename: str) -> dict | None:
    """{"seq", "num", "take"} pour un nom de clip du Studio, sinon None."""
    m = _CLIP_RE.match(os.path.basename(filename or ""))
    if not m:
        return None
    return {"seq": _int(m.group("seq")), "num": _int(m.group("num")),
            "take": _int(m.group("take"))}


def takes_for_shot(shot: dict, video_dir: str) -> list[tuple[int, str]]:
    """[(n° de prise, chemin)] du plan, triées par prise croissante."""
    title = shot_title(shot)
    if title == "plan" or not video_dir or not os.path.isdir(video_dir):
        return []
    seq, num = _int(shot.get("seq_num")), _int(shot.get("number"))
    out = []
    for name in os.listdir(video_dir):
        info = parse_clip_name(name)
        if info and info["num"] == num and info["seq"] == seq:
            out.append((info["take"], os.path.join(video_dir, name)))
    out.sort()
    return out


def import_meta(shot: dict | None, path: str = "") -> tuple[str, dict, str]:
    """(sous-chutier, métadonnées, couleur) d'un clip pour le Media Pool.
    Le n° de prise vient du nom du fichier quand il suit le nommage du Studio."""
    shot = shot or {}
    info = parse_clip_name(path) or {}
    seq = _int(shot.get("seq_num")) or info.get("seq", 0)
    num = _int(shot.get("number")) or info.get("num", 0)
    meta = {}
    if seq:
        meta["Scene"] = str(seq)
    if num:
        meta["Shot"] = str(num)
    if info.get("take"):
        meta["Take"] = str(info["take"])
    action = str(shot.get("scene_title") or "").strip()
    if action:
        meta["Comments"] = action[:240]
    if shot.get("id"):
        meta["pandora_shot_id"] = str(shot["id"])
    probe = {"seq_num": seq}
    return sequence_bin(probe), meta, sequence_color(probe)


def storyboard_clips(shots: list[dict], video_dir: str) -> list[dict]:
    """Plans du storyboard DANS L'ORDRE, chacun avec sa DERNIÈRE prise.
    → [{"shot", "title", "path" ("" si aucun clip), "take", "takes", "bin",
        "meta", "color"}]"""
    out = []
    for shot in shots or []:
        takes = takes_for_shot(shot, video_dir)
        take, path = takes[-1] if takes else (0, "")
        bin_name, meta, color = import_meta(shot, path)
        out.append({"shot": shot, "title": shot_title(shot), "path": path, "take": take,
                    "takes": len(takes), "bin": bin_name, "meta": meta, "color": color})
    return out
