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
