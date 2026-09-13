"""api/h3_local.py — MiniMax H3 sur la machine, via le serveur stable-diffusion.cpp.

Worker vidéo du Studio pour le moteur `minimax-h3-local`. Il parle au serveur
résident du projet communautaire `minimax-h3-local` (voir core/h3_local pour
l'API, les contraintes et la licence) :

    POST {url}/sdcpp/v1/vid_gen        → {"id": …}
    GET  {url}/sdcpp/v1/jobs/{id}      → status, queue_position, résultat

Le serveur rend un WebM en base64. PANDORA le convertit en MP4 avec le ffmpeg
qu'il embarque, parce que TOUT le reste de la chaîne — Vidéothèque, raccords,
import DaVinci — attend du MP4. Le WebM est conservé à côté, jamais supprimé.

Aucun coût : le journal reçoit une ligne à 0 $ pour que « Coût du projet »
reste complet sans inventer une facture (core/pricing porte l'entrée).
"""

from __future__ import annotations

import base64
import os
import subprocess
import time

from PyQt6.QtCore import pyqtSignal

from core import h3_local as _h3l
from api.video_engines import (
    _CancellableWorker, _video_output_dir, engine_prompt,
)
from core.worker import humanize_api_error

MODEL = "minimax-h3-local"
_POLL_S = 2.0
_MAX_WAIT_S = 3 * 3600   # un rendu Q8 à 768×1344 dépasse 28 min ; on laisse large


def _find_b64(job: dict) -> str:
    """Le WebM en base64, où que le serveur l'ait rangé.

    batch_gen.py lit `res["b64_json"]` sans dire ce qu'est `res` : on cherche
    aux emplacements plausibles plutôt que de parier sur un seul.
    """
    if not isinstance(job, dict):
        return ""
    for k in ("b64_json", "video", "output"):
        v = job.get(k)
        if isinstance(v, str) and len(v) > 100:
            return v
    for k in ("result", "output", "response"):
        v = job.get(k)
        if isinstance(v, dict):
            s = _find_b64(v)
            if s:
                return s
    data = job.get("data")
    if isinstance(data, list) and data and isinstance(data[0], dict):
        return _find_b64(data[0])
    return ""


def _to_mp4(webm: str) -> str:
    """WebM → MP4 (H.264 + AAC) avec le ffmpeg embarqué. Rend le chemin MP4,
    ou le WebM d'origine si la conversion est impossible — mieux vaut un
    fichier lisible dans un lecteur qu'aucun fichier."""
    try:
        from core.video_utils import get_ffmpeg_exe, _NO_WINDOW
        ff = get_ffmpeg_exe()
        if not ff:
            return webm
        mp4 = os.path.splitext(webm)[0] + ".mp4"
        subprocess.run(
            [ff, "-y", "-i", webm, "-c:v", "libx264", "-pix_fmt", "yuv420p",
             "-r", str(_h3l.FPS), "-c:a", "aac", "-movflags", "+faststart", mp4],
            check=True, capture_output=True, creationflags=_NO_WINDOW, timeout=600)
        return mp4 if os.path.isfile(mp4) else webm
    except Exception:
        return webm


class H3LocalWorker(_CancellableWorker):
    """Génère un plan sur le serveur H3 local. Même contrat que les workers fal :
    progress(int, str), finished(dict), failed(str)."""

    progress = pyqtSignal(int, str)
    finished = pyqtSignal(dict)
    failed   = pyqtSignal(str)

    def __init__(self, params: dict):
        super().__init__()
        self.params = params

    # ── Paramètres → requête ─────────────────────────────────────────────────

    def _dimensions(self) -> tuple[int, int, int]:
        """(largeur, hauteur, images).

        Cadre = préréglage orienté par le ratio du formulaire ; durée = le
        curseur, seule source du nombre d'images. Des champs libres
        width/height/frames (appel programmatique) priment s'ils sont fournis.
        """
        p = self.params
        preset = (p.get("resolution") or _h3l.DEFAULT_PRESET).split()[0].lower()
        w, h = _h3l.frame_for(preset, p.get("aspect_ratio") or "16:9")
        if p.get("width") and p.get("height"):
            w, h = p["width"], p["height"]
        if p.get("frames"):
            f = p["frames"]
        else:
            f = _h3l.frames_for_seconds(p.get("duration") or 2.3)
        return _h3l.snap_dimension(w), _h3l.snap_dimension(h), _h3l.snap_frames(f)

    def _steps(self) -> int:
        if self.params.get("steps"):
            return int(self.params["steps"])
        preset = (self.params.get("resolution") or _h3l.DEFAULT_PRESET).split()[0].lower()
        return _h3l.steps_for(preset)

    @staticmethod
    def _b64_of(path: str) -> str:
        if not path or not os.path.isfile(path):
            return ""
        with open(path, "rb") as f:
            return base64.b64encode(f.read()).decode("ascii")

    def _init_image_b64(self) -> str:
        if self.params.get("mode") != "i2v":
            return ""
        return self._b64_of(self.params.get("image_path") or "")

    def _end_image_b64(self) -> str:
        """Dernière image (raccord) — `end_image` seul est accepté par le
        serveur, mais dans PANDORA il n'a de sens qu'en I2V."""
        if self.params.get("mode") != "i2v":
            return ""
        return self._b64_of(self.params.get("end_image_path") or "")

    # ── Exécution ────────────────────────────────────────────────────────────

    def run(self):
        try:
            import requests

            url = _h3l.get_url()
            ok, msg = _h3l.ping(url)
            if not ok:
                raise RuntimeError(
                    msg + ". Lancez start_server.ps1 du projet minimax-h3-local, "
                          "ou corrigez l'adresse dans Paramètres.")

            w, h, frames = self._dimensions()
            secs = _h3l.seconds_of(frames)
            prompt_en = engine_prompt(self.params)
            body = _h3l.build_request(
                prompt_en, w, h, frames,
                steps=self._steps(),
                seed=self.params.get("seed"),
                init_image_b64=self._init_image_b64(),
                end_image_b64=self._end_image_b64(),
            )
            mode = "i2v" if body.get(_h3l.INIT_IMAGE_FIELD) else "t2v"
            if self.params.get("mode") == "i2v" and mode == "t2v":
                raise ValueError("H3 local I2V : image de départ requise.")

            self.progress.emit(
                8, f"H3 local — {w}×{h} · {frames} images ({secs} s) · envoi…")
            r = requests.post(f"{url}/sdcpp/v1/vid_gen", json=body, timeout=60)
            r.raise_for_status()
            jid = (r.json() or {}).get("id")
            if not jid:
                raise RuntimeError(f"Le serveur n'a pas rendu d'identifiant de tâche : {r.text[:200]}")

            t0 = time.time()
            last_pos = None
            while True:
                if self._cancelled or self.isInterruptionRequested():
                    try:
                        requests.post(f"{url}/sdcpp/v1/jobs/{jid}/cancel", timeout=5)
                    except Exception:
                        pass
                    return
                if time.time() - t0 > _MAX_WAIT_S:
                    raise RuntimeError("Délai dépassé : le serveur H3 local ne répond plus.")
                j = requests.get(f"{url}/sdcpp/v1/jobs/{jid}", timeout=30).json() or {}
                st = str(j.get("status", "")).lower()
                if st == _h3l.JOB_DONE:
                    break
                if st in _h3l.JOB_FAILED:
                    raise RuntimeError(
                        f"Tâche {st} côté serveur : {str(j.get('error') or j)[:200]}")
                pos = j.get("queue_position")
                if pos != last_pos:
                    last_pos = pos
                elapsed = int(time.time() - t0)
                pct = 15 + min(70, int(elapsed / max(60, secs * 45) * 70))
                extra = f" · file : {pos}" if pos not in (None, 0) else ""
                self.progress.emit(pct, f"H3 local — rendu en cours ({elapsed} s){extra}…")
                time.sleep(_POLL_S)

            b64 = _find_b64(j)
            if not b64:
                raise RuntimeError(f"Vidéo absente de la réponse : {str(j)[:200]}")

            self.progress.emit(90, "H3 local — écriture du fichier…")
            out_dir = _video_output_dir()
            ts = int(time.time())
            webm = os.path.join(out_dir, f"{MODEL}_{mode}_{secs}s_{ts}.webm")
            with open(webm, "wb") as f:
                f.write(base64.b64decode(b64))
            local = _to_mp4(webm)

            self.progress.emit(100, f"H3 local ✓  {secs} s · 0 $")
            if not self._cancelled:
                self.finished.emit({
                    "url":          "",
                    "local_path":   local,
                    "duration":     secs,
                    "resolution":   f"{w}x{h}",
                    "model":        f"{MODEL}-{mode}",
                    "credits_used": 0.0,
                })
        except Exception as e:
            if not self._cancelled:
                self.failed.emit(humanize_api_error(f"Erreur H3 local : {e}"))
