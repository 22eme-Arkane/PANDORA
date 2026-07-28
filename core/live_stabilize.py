"""Stabilisation façade des clips de mapping (Live).

Les modèles vidéo ne garantissent jamais une fixité au pixel près : même avec
la méthode deux plaques et le verrou géométrique, Seedance laisse de légères
dérives d'échelle et de position sur la façade (constat Matthieu 2026-07-28).
On ne les supprime pas à la source — on les ANNULE en post : chaque image est
recalée sur la géométrie de la PREMIÈRE, qui est la plaque de départ du plan,
donc la géométrie vraie par construction.

Méthode : features ORB appariées entre images CONSÉCUTIVES — le contenu
projeté évolue lentement, donc d'une image à l'autre l'appariement est fiable,
alors que la première et la dernière n'ont parfois plus rien en commun (c'est
le principe même d'une barre de mapping). La transformation par pas est une
SIMILARITÉ estimée par RANSAC (translation + rotation + échelle) : c'est la
famille des dérives Seedance ; une homographie complète sur-ajusterait sur le
contenu mouvant. Les pas sont COMPOSÉS pour ramener chaque image à la
géométrie de l'image 0.

Garde-fous : une estimation aberrante (trop peu d'appariements, pas au-delà du
plausible) vaut identité — mieux vaut une image non corrigée qu'une image
projetée n'importe où. Écriture via ffmpeg (même exécutable que le recalage de
core/video_conform) ; l'audio éventuel du clip source est recopié tel quel.
"""

from __future__ import annotations

import os
import subprocess

from core.video_utils import get_ffmpeg_exe, _NO_WINDOW

# Au-delà, une « correction » mesurée contre l'ANCRE n'est pas une dérive
# Seedance mais une erreur d'appariement : on la rejette (identité).
_MAX_SCALE_DEV  = 0.06      # 6 % d'échelle cumulée vs l'ancre
_MAX_SHIFT_PX   = 50.0      # translation cumulée vs l'ancre
_MIN_MATCHES    = 12


def _identity():
    import numpy as np
    return np.eye(2, 3, dtype=np.float64)


def _compose(a, b):
    """a · b pour des matrices affines 2×3 (b est appliquée en premier)."""
    import numpy as np
    _a = np.vstack([a, [0.0, 0.0, 1.0]])
    _b = np.vstack([b, [0.0, 0.0, 1.0]])
    return (_a @ _b)[:2]


def _step_transform(prev_gray, gray, orb, matcher):
    """Similarité qui RAMÈNE l'image courante sur la précédente — None si peu fiable."""
    import cv2
    import numpy as np
    k1, d1 = orb.detectAndCompute(prev_gray, None)
    k2, d2 = orb.detectAndCompute(gray, None)
    if d1 is None or d2 is None or len(k1) < _MIN_MATCHES or len(k2) < _MIN_MATCHES:
        return None
    pairs = matcher.knnMatch(d2, d1, k=2)
    good = [p[0] for p in pairs
            if len(p) == 2 and p[0].distance < 0.75 * p[1].distance]
    if len(good) < _MIN_MATCHES:
        return None
    # queryIdx → image courante (d2), trainIdx → image précédente (d1) :
    # la similarité estimée envoie les coordonnées courantes sur les précédentes.
    p_cur  = np.float32([k2[m.queryIdx].pt for m in good])
    p_prev = np.float32([k1[m.trainIdx].pt for m in good])
    M, _inl = cv2.estimateAffinePartial2D(p_cur, p_prev, method=cv2.RANSAC,
                                          ransacReprojThreshold=3.0)
    if M is None:
        return None
    _scale = float(np.hypot(M[0, 0], M[0, 1]))
    if abs(_scale - 1.0) > _MAX_SCALE_DEV:
        return None
    if abs(float(M[0, 2])) > _MAX_SHIFT_PX or abs(float(M[1, 2])) > _MAX_SHIFT_PX:
        return None
    return M


def stabilize_clip(video_path: str, out_path: str = "",
                   progress_cb=None, cancelled=None) -> dict:
    """Recale chaque image sur la géométrie de la première. Jamais d'exception.

    Retourne {"ok", "out", "frames", "max_correction_px"} — ou {"ok": False,
    "error": …}. `progress_cb(pourcent)` optionnel ; `cancelled()` optionnel,
    interrogé à chaque image (le fichier partiel est alors supprimé).
    """
    import cv2
    import numpy as np
    try:
        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            return {"ok": False, "error": "vidéo illisible"}
        fps = float(cap.get(cv2.CAP_PROP_FPS) or 0.0) or 24.0
        w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH) or 0)
        h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0)
        total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
        if not w or not h:
            cap.release()
            return {"ok": False, "error": "dimensions illisibles"}
        out_path = out_path or (os.path.splitext(video_path)[0] + "_stab.mp4")

        # L'estimation se fait en résolution réduite (les dérives sont globales,
        # la demi-résolution suffit et divise le temps par ~4) ; la CORRECTION,
        # elle, s'applique à pleine résolution.
        down = 0.5 if max(w, h) > 960 else 1.0

        orb = cv2.ORB_create(nfeatures=2000)
        matcher = cv2.BFMatcher(cv2.NORM_HAMMING)

        ff = subprocess.Popen(
            [get_ffmpeg_exe(), "-y",
             "-f", "rawvideo", "-pix_fmt", "bgr24", "-s", f"{w}x{h}",
             "-r", f"{fps:.6f}", "-i", "pipe:0",
             "-i", video_path,
             "-map", "0:v", "-map", "1:a?",
             "-c:v", "libx264", "-preset", "medium", "-crf", "17",
             "-pix_fmt", "yuv420p", "-c:a", "copy",
             out_path],
            stdin=subprocess.PIPE, stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL, creationflags=_NO_WINDOW)

        # La dérive PAR IMAGE est sub-pixel — sous la résolution d'un
        # appariement image-à-image, qui n'intégrerait que du bruit. On mesure
        # donc chaque image contre une ANCRE (l'image 0 au départ) : la dérive
        # cumulée depuis l'ancre est grande, donc mesurable. Quand le contenu
        # projeté s'est trop éloigné de l'ancre pour s'apparier, on ré-ancre
        # sur l'image précédente, dont la correction est déjà connue — l'erreur
        # d'intégration ne s'accumule qu'à ces ré-ancrages, rares.
        cum = _identity()
        anchor_small = None
        anchor_to_0 = _identity()
        prev_small = None
        prev_cum = _identity()
        max_corr = 0.0
        i = 0
        while True:
            if cancelled is not None and cancelled():
                try:
                    ff.stdin.close()
                    ff.wait(timeout=10)
                except Exception:
                    ff.kill()
                cap.release()
                try:
                    os.remove(out_path)
                except OSError:
                    pass
                return {"ok": False, "error": "annulé"}
            ok, frame = cap.read()
            if not ok:
                break
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            small = (cv2.resize(gray, None, fx=down, fy=down,
                                interpolation=cv2.INTER_AREA)
                     if down != 1.0 else gray)
            if anchor_small is None:
                anchor_small = small
            else:
                M = _step_transform(anchor_small, small, orb, matcher)
                if M is None and prev_small is not None:
                    anchor_small = prev_small
                    anchor_to_0 = prev_cum
                    M = _step_transform(anchor_small, small, orb, matcher)
                if M is not None:
                    Mf = M.copy()
                    Mf[:, 2] /= down    # translations estimées en réduit
                    cum = _compose(anchor_to_0, Mf)
                # sinon : la dernière correction connue reste appliquée.
            prev_small = small
            prev_cum = cum.copy()

            _s = float(np.hypot(cum[0, 0], cum[0, 1]))
            _corr = (float(np.hypot(cum[0, 2], cum[1, 2]))
                     + abs(_s - 1.0) * max(w, h) / 2.0)
            max_corr = max(max_corr, _corr)
            if _corr > 0.05:
                frame = cv2.warpAffine(
                    frame, cum, (w, h), flags=cv2.INTER_LANCZOS4,
                    borderMode=cv2.BORDER_CONSTANT, borderValue=(0, 0, 0))
            ff.stdin.write(frame.tobytes())
            i += 1
            if progress_cb is not None and total:
                try:
                    progress_cb(min(99, int(i * 100 / total)))
                except Exception:
                    pass
        cap.release()
        ff.stdin.close()
        ff.wait()
        if ff.returncode != 0 or not os.path.isfile(out_path):
            return {"ok": False, "error": "encodage ffmpeg échoué"}
        if progress_cb is not None:
            try:
                progress_cb(100)
            except Exception:
                pass
        return {"ok": True, "out": out_path, "frames": i,
                "max_correction_px": round(max_corr, 2)}
    except Exception as exc:
        return {"ok": False, "error": str(exc)[:200]}
