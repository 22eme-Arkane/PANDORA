"""
core/live_chain.py — Mode de génération du MAPPING Live : frame vidéo ou chaîne d'images.

Spec Matthieu 2026-07-30, contre la DÉRIVE D'ÉCHELLE de la façade :

  · MODE_FRAMES (« r2v » dans la spec, défaut) — comportement historique : le plan N
    part de la DERNIÈRE FRAME VIDÉO extraite du clip N-1. C'est cette frame qui
    transporte le rognage Seedance de plan en plan (effet boule de neige mesuré le
    2026-07-29 sur Forcalquier).
  · MODE_CHAIN (« i2v_chain ») — chaîne d'images : le plan N part du MOOD du plan
    N-1 (une image générée, jamais passée par la vidéo) et arrive sur SON mood. La
    chaîne ne ré-ingère plus aucune frame produite par le moteur vidéo → le rognage
    ne peut plus s'accumuler, par construction. Le plan 1 part d'une image de
    départ dédiée (plaque d'ÉTAT 0), générée avec les moods.

Modèle ASYMÉTRIQUE (décision Matthieu) : seul le plan 1 possède une image de
départ propre, rangée en SIDECAR dans son dossier d'aperçus — jamais dans la
galerie, dont l'image ACTIVE reste la plaque d'ARRIVÉE. Le départ des plans N>1
n'est PAS stocké : il est résolu DYNAMIQUEMENT à l'envoi (zéro invalidation à
gérer quand on régénère, insère ou réordonne des plans).

Un SEUL champ persisté par projet (`live_gen_mode.json`), lu et écrit par les
deux UI (RENDU & AUDIO du Studio IA, section Mode de la page Séquence) — jamais
d'état dupliqué. Ne s'applique qu'aux séquences MAPPING ; le Live scène reste
intact. Les identifiants « r2v »/« i2v_chain » viennent de la spec : « r2v »
désigne le comportement historique même si, techniquement, l'envoi avec
keyframes passe déjà par image-to-video.
"""

import os
import json

MODE_FRAMES = "r2v"        # historique : raccord par frame vidéo extraite
MODE_CHAIN  = "i2v_chain"  # chaîne d'images : mood N-1 → mood N

_MODES = (MODE_FRAMES, MODE_CHAIN)


def _path() -> str:
    from core.context import get_data_root
    return os.path.join(get_data_root(), "live_gen_mode.json")


def get_gen_mode() -> str:
    """Mode de génération mapping du projet courant. Ne lève jamais."""
    try:
        with open(_path(), encoding="utf-8") as f:
            m = (json.load(f).get("mode") or "").strip()
        return m if m in _MODES else MODE_FRAMES
    except Exception:
        return MODE_FRAMES


def set_gen_mode(mode: str) -> None:
    """Écrit le champ partagé. Valeur inconnue → défaut (jamais d'état invalide)."""
    try:
        p = _path()
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "w", encoding="utf-8") as f:
            json.dump({"mode": mode if mode in _MODES else MODE_FRAMES}, f)
    except Exception:
        pass


# ── Image de départ du plan 1 (sidecar) ───────────────────────────────────────

def _start_sidecar(shot_id: str) -> str:
    import core.storyboard as sb
    return os.path.join(sb.get_apercu_dir(shot_id), "start_image.json")


def get_start_image(shot_id: str) -> str:
    """Chemin de l'image de départ (état 0) du plan — "" si absente."""
    if not shot_id:
        return ""
    try:
        with open(_start_sidecar(shot_id), encoding="utf-8") as f:
            p = json.load(f).get("path", "")
        return p if p and os.path.isfile(p) else ""
    except Exception:
        return ""


def set_start_image(shot_id: str, path: str) -> None:
    if not shot_id:
        return
    try:
        p = _start_sidecar(shot_id)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "w", encoding="utf-8") as f:
            json.dump({"path": path or ""}, f)
    except Exception:
        pass


# ── Résolution de la chaîne ───────────────────────────────────────────────────

def _num(s: dict) -> int:
    try:
        return int(s.get("number") or 0)
    except (TypeError, ValueError):
        return 0


def previous_shot(shot: dict):
    """Plan précédent dans l'ordre des numéros — None si premier (ou introuvable).

    L'appelant doit avoir posé le namespace de séquence (live_seq_mapping) :
    toute la chaîne d'envoi le repose avant lecture (règle 2026-07-27)."""
    import core.storyboard as sb
    cur = _num(shot or {})
    prev = None
    try:
        for s in sorted(sb.list_shots(), key=_num):
            if _num(s) < cur:
                prev = s
            else:
                break
    except Exception:
        prev = None
    return prev


def active_mood(shot: dict) -> str:
    """Mood ACTIF d'un plan (la plaque validée à l'écran) — "" si aucun."""
    import core.storyboard as sb
    try:
        ap = sb.load_apercus((shot or {}).get("id", ""))
        paths = [p for p in ap.get("paths", []) if os.path.isfile(p)]
        if not paths:
            return ""
        idx = min(ap.get("active_idx", 0), len(paths) - 1)
        return paths[idx]
    except Exception:
        return ""


def chain_start_for(shot: dict) -> str:
    """DÉPART du plan en mode chaîne — toujours une IMAGE générée, jamais une
    frame vidéo : mood actif du plan précédent, ou image de départ dédiée pour
    le premier plan. "" si indisponible (l'envoi retombe alors sur le mood du
    plan comme seul point d'ancrage, comme aujourd'hui pour un plan 1)."""
    prev = previous_shot(shot)
    if prev is not None:
        return active_mood(prev)
    return get_start_image((shot or {}).get("id", ""))
