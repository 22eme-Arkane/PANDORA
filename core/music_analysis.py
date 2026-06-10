"""
core/music_analysis.py — Analyse locale des musiques du set (PANDORA | Live).

Claude ne peut pas écouter l'audio (API = texte + images). On analyse donc la musique
LOCALEMENT avec librosa pour produire, par morceau :
  - durée
  - BPM (tempo) — corrigeable côté UI (erreurs d'octave possibles)
  - profil d'énergie compact (mini sparkline ▁▂▃…█)
  - temps forts (drops / montées) en secondes

`build_set_timeline(tracks)` transforme ces données en un bloc TEXTE injecté dans Claude
pour caler le conducteur / la mise en page / le découpage sur la musique.

⚠️ librosa est volumineux (+~250 Mo) — réservé au build Live, JAMAIS dans le build Cinéma.
L'import est PARESSEUX (uniquement dans le worker) pour ne rien charger au démarrage.
"""

import os

from PyQt6.QtCore import QThread, pyqtSignal

_BARS = "▁▂▃▄▅▆▇█"


def _mmss(secs: float) -> str:
    secs = max(0, int(round(secs)))
    return f"{secs // 60}:{secs % 60:02d}"


def analyze_file(path: str) -> dict:
    """Analyse un fichier audio → dict {path,name,bpm,duration,energy,drops}.
    Lève une exception si librosa indisponible ou fichier illisible."""
    import numpy as np
    import librosa

    # Mono, sr réduit (22050) : suffisant pour tempo/énergie et plus rapide.
    y, sr = librosa.load(path, sr=22050, mono=True)
    duration = float(librosa.get_duration(y=y, sr=sr))

    # Tempo (BPM) — librosa 0.11 peut renvoyer un ndarray → on prend le 1er scalaire.
    tempo, _beats = librosa.beat.beat_track(y=y, sr=sr)
    bpm = float(np.atleast_1d(tempo)[0])

    # Enveloppe d'énergie (RMS).
    rms = librosa.feature.rms(y=y)[0]
    times = librosa.times_like(rms, sr=sr)
    dt = float(times[1] - times[0]) if len(times) > 1 else 0.05

    # Lissage ~2 s.
    win = max(1, int(round(2.0 / dt)))
    if win > 1 and len(rms) >= win:
        kernel = np.ones(win) / win
        sm = np.convolve(rms, kernel, mode="same")
    else:
        sm = rms
    peak = float(sm.max()) if sm.size else 0.0
    norm = sm / (peak + 1e-9)

    # Profil compact (24 caractères sparkline).
    n_points = 24
    if norm.size:
        idx = np.linspace(0, norm.size - 1, num=min(n_points, norm.size)).astype(int)
        energy = "".join(_BARS[min(7, int(norm[i] * 7.999))] for i in idx)
    else:
        energy = ""

    # Détection des temps forts : sauts positifs d'énergie (dérivée lissée) vers un
    # niveau haut. find_peaks (scipy, dépendance de librosa) ; fallback manuel sinon.
    drops: list[float] = []
    try:
        from scipy.signal import find_peaks
        d = np.diff(sm, prepend=sm[:1])
        dn = d / (np.abs(d).max() + 1e-9)
        min_gap = max(1, int(round(8.0 / dt)))   # ≥ 8 s entre deux drops
        peaks, _ = find_peaks(dn, height=0.22, distance=min_gap)
        drops = [float(times[p]) for p in peaks if norm[p] > 0.5][:10]
    except Exception:
        drops = []

    return {
        "path":     path,
        "name":     os.path.basename(path),
        "bpm":      round(bpm, 1),
        "duration": duration,
        "energy":   energy,
        "drops":    drops,
    }


def build_set_timeline(tracks: list) -> str:
    """Construit le bloc texte injecté dans Claude depuis les morceaux ANALYSÉS."""
    analyzed = [t for t in (tracks or []) if t.get("bpm")]
    if not analyzed:
        return ""
    lines = ["[TIMELINE MUSICALE DU SET — cale le rythme du découpage sur ces données]"]
    total = 0.0
    for i, t in enumerate(analyzed, 1):
        dur = float(t.get("duration", 0) or 0)
        total += dur
        bpm = t.get("bpm", 0)
        drops = ", ".join(_mmss(d) for d in t.get("drops", [])) or "—"
        lines.append(f"Track {i} — « {t.get('name','?')} » — {_mmss(dur)} — {bpm:.0f} BPM")
        if t.get("energy"):
            lines.append(f"  Énergie (début→fin): {t['energy']}")
        lines.append(f"  Temps forts (drops/montées): {drops}")
    lines.append(f"Durée totale du set : {_mmss(total)} ({len(analyzed)} morceau(x)).")
    lines.append(
        "CONSIGNE : place les ruptures et les temps forts du découpage sur ces drops ; "
        "dimensionne les loops en mesures sur le BPM (ex. 4 mesures à 128 BPM = 7,5 s) "
        "pour rester synchronisable dans Resolume."
    )
    return "\n".join(lines)


class AnalyzeMusicWorker(QThread):
    """Analyse une liste de morceaux en tâche de fond.
    progress(index, total, nom) ; finished(list[dict] enrichis) ; failed(str)."""
    progress = pyqtSignal(int, int, str)
    finished = pyqtSignal(list)
    failed   = pyqtSignal(str)

    def __init__(self, tracks: list):
        super().__init__()
        # Copie défensive ; on ré-analyse tout (BPM/énergie/drops) à chaque passe.
        self._tracks = [dict(t) for t in (tracks or [])]

    def run(self):
        if not self._tracks:
            self.failed.emit("Aucune musique à analyser — ajoute d'abord des morceaux.")
            return
        try:
            import librosa  # noqa: F401  (vérifie la disponibilité tôt)
        except Exception:
            self.failed.emit(
                "Module d'analyse audio (librosa) indisponible dans cette version. "
                "L'analyse musicale n'est active que dans le build PANDORA | Live."
            )
            return
        total = len(self._tracks)
        out: list[dict] = []
        for i, t in enumerate(self._tracks, 1):
            path = t.get("path", "")
            name = t.get("name") or os.path.basename(path)
            self.progress.emit(i, total, name)
            if not path or not os.path.isfile(path):
                # On conserve le morceau mais sans analyse.
                out.append({**t, "bpm": 0, "duration": 0, "energy": "", "drops": []})
                continue
            try:
                out.append(analyze_file(path))
            except Exception as e:
                out.append({**t, "name": name, "bpm": 0, "duration": 0,
                            "energy": "", "drops": [], "error": str(e)})
        self.finished.emit(out)
