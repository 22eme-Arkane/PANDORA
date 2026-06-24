"""
core/video_conform.py — Conformation des clips à leur durée musicale exacte.

Pourquoi : Seedance ne reçoit que des durées ENTIÈRES (« duration: "6" »), alors que
le calage musical produit des durées en mesures exactes (5.625 s à 128 BPM…). En
timeline linéaire (DaVinci), l'écart s'accumule de plan en plan → la vidéo dérive
de la musique. Ici on CONFORME chaque clip téléchargé à sa durée cible par un
RETIME LÉGER ffmpeg (setpts) :

  - préserve la PREMIÈRE et la DERNIÈRE frame → les raccords par keyframes restent
    exacts (un trim couperait la frame d'arrivée) ;
  - écart toléré ≤ MAX_DEVIATION (12 %) : au-delà on ne touche pas au clip
    (un retime fort se verrait) ;
  - l'audio éventuel est retimé en conséquence (atempo), sinon piste supprimée
    telle quelle.

Usage : conform_clip(path, target_s) — remplace le fichier EN PLACE si conformé.
"""

import os
import subprocess

from core.video_utils import get_ffmpeg_exe, get_ffprobe_exe, _NO_WINDOW

MAX_DEVIATION = 0.12   # 12 % d'écart max — au-delà, on laisse le clip intact
MIN_DELTA_S   = 0.05   # en-dessous de 50 ms d'écart, inutile de conformer


def probe_duration(path: str) -> float:
    """Durée réelle du fichier en secondes (0.0 si introuvable)."""
    try:
        r = subprocess.run(
            [get_ffprobe_exe(), "-v", "error", "-show_entries", "format=duration",
             "-of", "csv=p=0", path],
            capture_output=True, text=True, timeout=15, creationflags=_NO_WINDOW,
        )
        return float(r.stdout.strip()) if r.returncode == 0 else 0.0
    except Exception:
        return 0.0


def _has_audio(path: str) -> bool:
    try:
        r = subprocess.run(
            [get_ffprobe_exe(), "-v", "error", "-select_streams", "a",
             "-show_entries", "stream=codec_type", "-of", "csv=p=0", path],
            capture_output=True, text=True, timeout=15, creationflags=_NO_WINDOW,
        )
        return r.returncode == 0 and bool(r.stdout.strip())
    except Exception:
        return False


def conform_clip(path: str, target_s: float) -> dict:
    """Retime le clip pour qu'il dure EXACTEMENT target_s. Remplace le fichier en
    place. Retourne {"conformed": bool, "actual": float, "target": float, "reason": str}."""
    res = {"conformed": False, "actual": 0.0, "target": round(float(target_s or 0), 3),
           "reason": ""}
    if not path or not os.path.isfile(path) or not target_s or target_s <= 0:
        res["reason"] = "entrée invalide"
        return res

    actual = probe_duration(path)
    res["actual"] = round(actual, 3)
    if actual <= 0:
        res["reason"] = "durée réelle inconnue"
        return res
    delta = abs(actual - target_s)
    if delta < MIN_DELTA_S:
        res["reason"] = "déjà à la bonne durée"
        return res
    if delta / target_s > MAX_DEVIATION:
        res["reason"] = f"écart trop grand ({delta:.2f}s) — retime refusé"
        return res

    factor = target_s / actual          # setpts : >1 = ralentit, <1 = accélère
    base, ext = os.path.splitext(path)
    tmp = f"{base}_conform{ext or '.mp4'}"

    cmd = [get_ffmpeg_exe(), "-y", "-i", path,
           "-filter:v", f"setpts={factor:.6f}*PTS"]
    if _has_audio(path):
        # atempo = inverse du facteur vidéo (borné 0.5–2.0 par ffmpeg — ok ici, ±12 %)
        cmd += ["-filter:a", f"atempo={1.0 / factor:.6f}"]
    else:
        cmd += ["-an"]
    cmd += ["-t", f"{target_s:.3f}", tmp]

    try:
        proc = subprocess.run(cmd, capture_output=True, timeout=300,
                              creationflags=_NO_WINDOW)
        if proc.returncode != 0 or not os.path.isfile(tmp):
            res["reason"] = (proc.stderr or b"").decode(errors="replace")[-200:]
            return res
        os.replace(tmp, path)
        res["conformed"] = True
        return res
    except Exception as e:
        res["reason"] = str(e)[:200]
        try:
            if os.path.isfile(tmp):
                os.remove(tmp)
        except OSError:
            pass
        return res
