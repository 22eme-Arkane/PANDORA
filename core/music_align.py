"""
core/music_align.py — Calage déterministe du découpage sur la musique (PANDORA | Live).

Pourquoi : injecter la timeline (BPM, drops) dans Claude donne l'INTENTION, mais un
LLM ne fait pas d'arithmétique fiable — les cuts ne tombent ni sur les mesures ni
sur les drops. Ici le calage est fait en Python, exactement :

  1. chaque durée de plan est QUANTISÉE au multiple de MESURE le plus proche
     (1 mesure = 4 temps = 240/BPM secondes), bornée [min_s, max_s] ;
  2. chaque CUT cumulé est ATTIRÉ sur le drop le plus proche du morceau courant
     (tolérance ±1 mesure) — les ruptures visuelles tombent sur les ruptures sonores.

Le morceau d'un plan = sa colonne « Musique » (music_track) si renseignée, sinon le
morceau couvrant sa position dans le set (morceaux enchaînés dans l'ordre).
"""

from __future__ import annotations


def bar_seconds(bpm: float, beats_per_bar: int = 4) -> float:
    """Durée d'une mesure en secondes (0 si BPM inconnu)."""
    try:
        bpm = float(bpm)
    except (TypeError, ValueError):
        return 0.0
    return (beats_per_bar * 60.0 / bpm) if bpm > 0 else 0.0


def _track_starts(tracks: list) -> list:
    """Temps de début absolu de chaque morceau (enchaînés dans l'ordre du set)."""
    starts, cum = [], 0.0
    for t in tracks:
        starts.append(cum)
        try:
            cum += float(t.get("duration", 0) or 0)
        except (TypeError, ValueError):
            pass
    return starts


def _track_for(shot: dict, tracks: list, starts: list, at_time: float):
    """(track, start_abs) du plan : par nom (colonne Musique), sinon par position."""
    name = (shot.get("music_track") or "").strip()
    if name:
        for t, s in zip(tracks, starts):
            if t.get("name") == name:
                return t, s
    for t, s in reversed(list(zip(tracks, starts))):
        dur = float(t.get("duration", 0) or 0)
        if at_time >= s and (dur <= 0 or at_time < s + dur):
            return t, s
    return (tracks[-1], starts[-1]) if tracks else (None, 0.0)


def assign_tracks_to_shots(shots: list, tracks: list) -> list:
    """Assigne AUTOMATIQUEMENT chaque plan au morceau couvrant sa position dans
    le set (morceaux enchaînés dans l'ordre, timeline cumulée des durées de plans).
    Ne modifie RIEN — retourne [{"id", "number", "track"}] pour les plans dont la
    colonne Musique change. Le BPM de la ligne en dérive (colonne calculée)."""
    tracks = [t for t in (tracks or []) if t.get("name")]
    if not tracks or not shots:
        return []
    starts = _track_starts(tracks)

    def _num(s):
        try:
            return int(s.get("number") or 0)
        except (TypeError, ValueError):
            return 0

    out, cum = [], 0.0
    for shot in sorted(shots, key=_num):
        track, _start = _track_for({}, tracks, starts, cum)  # par position uniquement
        name = (track or {}).get("name", "")
        if name and (shot.get("music_track") or "") != name:
            out.append({"id": shot.get("id", ""),
                        "number": shot.get("number", 0),
                        "track": name})
        try:
            cum += float(shot.get("duration", 5.0) or 5.0)
        except (TypeError, ValueError):
            cum += 5.0
    return out


def align_shots_to_music(shots: list, tracks: list,
                         min_s: float = 2.0, max_s: float = 15.0,
                         beats_per_bar: int = 4,
                         snap_tolerance_bars: float = 1.0) -> list:
    """Calcule les nouvelles durées calées. Ne modifie RIEN — retourne :
    [{"id", "number", "old", "new", "snapped_drop": bool, "bpm": float}]
    `shots` : plans triés par number (duration, music_track, id, number).
    `tracks` : morceaux analysés du conducteur (name, bpm, duration, drops)."""
    analyzed = [t for t in (tracks or []) if t.get("bpm")]
    if not analyzed or not shots:
        return []
    starts = _track_starts(analyzed)

    def _num(s):
        try:
            return int(s.get("number") or 0)
        except (TypeError, ValueError):
            return 0

    out, cum = [], 0.0
    for shot in sorted(shots, key=_num):
        try:
            old = float(shot.get("duration", 5.0) or 5.0)
        except (TypeError, ValueError):
            old = 5.0
        track, t_start = _track_for(shot, analyzed, starts, cum)
        bpm = float(track.get("bpm", 0) or 0) if track else 0.0
        bar = bar_seconds(bpm, beats_per_bar)

        if bar <= 0:
            cum += old
            continue

        # 1) Quantise la durée en mesures entières (≥ 1 mesure, bornée min/max)
        n_bars = max(1, round(old / bar))
        new = n_bars * bar
        while new < min_s:
            n_bars += 1
            new = n_bars * bar
        while new > max_s and n_bars > 1:
            n_bars -= 1
            new = n_bars * bar
        new = min(new, max_s)

        # 2) Attire le cut (fin du plan) sur le drop le plus proche
        snapped = False
        drops_abs = [t_start + float(d) for d in (track.get("drops") or [])]
        if drops_abs:
            end = cum + new
            nearest = min(drops_abs, key=lambda d: abs(d - end))
            if abs(nearest - end) <= snap_tolerance_bars * bar:
                cand = nearest - cum
                if min_s <= cand <= max_s and cand >= bar * 0.5:
                    new = cand
                    snapped = True

        # 3 décimales : préserve l'exactitude des multiples de mesure
        # (ex. 3 mesures à 128 BPM = 5.625 s — un arrondi à 2 décimales fausserait le calage)
        new = round(new, 3)
        out.append({
            "id":           shot.get("id", ""),
            "number":       shot.get("number", 0),
            "old":          round(old, 2),
            "new":          new,
            "snapped_drop": snapped,
            "bpm":          bpm,
        })
        cum += new
    return out


def set_duration_seconds(tracks: list) -> float:
    """Durée totale du set = somme des durées des morceaux du conducteur."""
    total = 0.0
    for t in (tracks or []):
        try:
            total += float(t.get("duration", 0) or 0)
        except (TypeError, ValueError):
            pass
    return total


def conform_durations_to_set(segments: list, set_duration: float,
                             min_s: int = 2, max_s: int = 15,
                             tolerance_s: float = 2.0) -> dict:
    """Conforme la SOMME des durées des plans à la durée du set — répartition au
    PRORATA en secondes entières, bornes [min_s, max_s] respectées. Modifie les
    segments EN PLACE. Retourne {"adjusted", "old_sum", "new_sum", "target"}.

    Pourquoi : la mise en page co-écrite écrit des durées plausibles plan par plan,
    mais un LLM n'additionne pas juste — constat « Mapping Nicolas » (2026-07-13) :
    29 plans totalisaient 3:55 pour un set de 4:28 → 33 s manquaient à l'export.
    La consigne au modèle réduit l'écart ; CETTE conformation le supprime."""
    segs = [s for s in (segments or []) if isinstance(s, dict)]
    res = {"adjusted": False, "old_sum": 0.0, "new_sum": 0.0, "target": 0}
    if not segs or not set_duration or set_duration <= 0:
        return res
    durs = []
    for s in segs:
        try:
            durs.append(max(0.0, float(s.get("duration", 0) or 0)))
        except (TypeError, ValueError):
            durs.append(0.0)
    old_sum = sum(durs)
    res["old_sum"] = round(old_sum, 2)
    res["new_sum"] = res["old_sum"]
    n = len(segs)
    # Cible atteignable : bornée par n×min et n×max (sinon on fait au plus près).
    target = int(round(set_duration))
    target = max(n * min_s, min(target, n * max_s))
    res["target"] = target
    if old_sum <= 0 or abs(old_sum - target) <= tolerance_s:
        return res
    factor = target / old_sum
    scaled = [min(max(d * factor, float(min_s)), float(max_s)) for d in durs]
    base = [int(x) for x in scaled]   # plancher entier
    rest = target - sum(base)
    # +1 s aux plus grands restes fractionnaires (avec marge), −1 s aux plus petits.
    order_up   = sorted(range(n), key=lambda i: scaled[i] - base[i], reverse=True)
    order_down = sorted(range(n), key=lambda i: scaled[i] - base[i])
    k = 0
    while rest > 0 and k < 10 * n:
        i = order_up[k % n]
        if base[i] < max_s:
            base[i] += 1
            rest -= 1
        k += 1
    k = 0
    while rest < 0 and k < 10 * n:
        i = order_down[k % n]
        if base[i] > min_s:
            base[i] -= 1
            rest += 1
        k += 1
    for s, d in zip(segs, base):
        s["duration"] = int(d)
    res["adjusted"] = True
    res["new_sum"] = float(sum(base))
    return res
