"""ui/previs_render.py — Prévisualisation vidéo d'un plan, rendue depuis sa caméra (Plan de feu).

Demande Matthieu (29-30/10/2026) : une maquette 3D du plan (caméra, placements, déplacements
des personnages) envoyée à Seedance comme vidéo de RÉFÉRENCE, sans Blender.

Une vue 3D CACHÉE (même moteur que le Plan de feu, jamais affichée) charge la scène du plan,
regarde par la caméra du plan et rejoue la frise image par image ; ffmpeg assemble les images
en MP4 H.264 1280×720 à 24 i/s — format accepté en référence par Seedance 2.0 et 2.5 chez tous
les distributeurs (848×480 et 640×360 sont refusés). Les faisceaux dans la brume, les pieds de
projecteurs et les étiquettes sont retirés : la référence ne doit montrer que l'espace, la
caméra et les personnages.
"""
from __future__ import annotations

import base64
import json
import os
import re
import shutil
import tempfile

from PyQt6.QtCore import QObject, QProcess, Qt, QTimer, pyqtSignal

WIDTH, HEIGHT, FPS = 1280, 720, 24


class PrevisRenderer(QObject):
    """Rend la prévisualisation d'une scène. Signaux : progress(%, texte), done(chemin), failed(texte)."""

    progress = pyqtSignal(int, str)
    done = pyqtSignal(str)
    failed = pyqtSignal(str)

    def __init__(self, scene: dict, out_path: str, parent=None):
        super().__init__(parent)
        self._scene = json.loads(json.dumps(scene))
        env = self._scene.setdefault("environment", {})
        env.update({"haze": 0, "stands": False, "labels": False, "labelPatch": False})
        self._out = out_path
        self._dir = tempfile.mkdtemp(prefix="pandora_previs_")
        self._view = None
        self._loaded = False
        self._chars = False
        self._started = False
        self._n = 0
        self._got = 0
        self._finished = False
        self._watchdog = QTimer(self)
        self._watchdog.setSingleShot(True)
        self._watchdog.timeout.connect(lambda: self._fail("La vue 3D ne répond pas (délai dépassé)."))

    # ---------------------------------------------------------------- déroulé
    def start(self) -> None:
        from ui.scene3d_web import Scene3DView, unavailable_reason
        why = unavailable_reason()
        if why:
            self._fail(why)
            return
        self._view = Scene3DView()
        # jamais à l'écran, mais une vraie surface : la caméra du plan voit en 16/9 exact
        self._view.setAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen, True)
        self._view.resize(WIDTH, HEIGHT)
        self._view.page_event.connect(self._on_event)
        self._view.set_scene(self._scene)
        self._view.show()
        self.progress.emit(2, "Préparation de la scène…")
        self._watchdog.start(60000)

    def _on_event(self, ev: dict) -> None:
        kind = ev.get("kind")
        if kind == "loaded":
            self._loaded = True
        elif kind == "actions":
            self._chars = True
        elif kind == "error" and ev.get("op") in ("characters", "load", "page"):
            self._fail(str(ev.get("message") or "erreur de la vue 3D"))
            return
        elif kind == "frame":
            self._frame(ev)
            return
        elif kind == "capture_done":
            self._encode()
            return
        if self._loaded and self._chars and not self._started:
            self._started = True
            # une image de plus pour laisser la vue se poser (ombres, textures)
            QTimer.singleShot(400, lambda: self._view.send("capture", fps=FPS, width=WIDTH, height=HEIGHT))
            self.progress.emit(5, "Rendu des images…")

    def _frame(self, ev: dict) -> None:
        try:
            data = str(ev.get("data") or "")
            raw = base64.b64decode(data.split(",", 1)[1])
            i = int(ev.get("i", 0))
            self._n = int(ev.get("n", 1))
            with open(os.path.join(self._dir, f"f{i:05d}.jpg"), "wb") as f:
                f.write(raw)
            self._got += 1
            self._watchdog.start(30000)
            if self._got % 6 == 0 or self._got == self._n:
                self.progress.emit(5 + int(85 * self._got / max(1, self._n)),
                                   f"Image {self._got} / {self._n}")
        except Exception as e:   # image illisible : la prévisu ne vaut rien
            self._fail(f"Image illisible : {e}")

    def _encode(self) -> None:
        """ffmpeg en processus à part (QProcess) : un plan de 30 s fait 720 images, leur
        assemblage ne doit pas figer PANDORA ; la progression suit les images encodées."""
        self._watchdog.stop()
        if self._got < self._n or self._n == 0:
            self._fail(f"Images manquantes ({self._got} / {self._n}).")
            return
        self.progress.emit(92, "Assemblage de la vidéo…")
        try:
            from core.video_utils import get_ffmpeg_exe
            ffmpeg = get_ffmpeg_exe()
            os.makedirs(os.path.dirname(self._out), exist_ok=True)
        except Exception as e:
            self._fail(f"Assemblage impossible : {e}")
            return
        self._tmp_out = self._out + ".part.mp4"
        args = ["-y", "-loglevel", "error", "-nostats", "-progress", "pipe:1",
                "-framerate", str(FPS), "-i", os.path.join(self._dir, "f%05d.jpg"),
                "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "18", "-preset", "medium",
                "-movflags", "+faststart", "-an", self._tmp_out]
        self._proc = QProcess(self)
        self._proc.readyReadStandardOutput.connect(self._encode_progress)
        self._proc.finished.connect(self._encoded)
        self._proc.errorOccurred.connect(self._encode_error)
        self._watchdog.start(600000)
        self._proc.start(ffmpeg, args)

    def _encode_progress(self) -> None:
        try:
            txt = bytes(self._proc.readAllStandardOutput()).decode("ascii", "ignore")
            frames = [int(v) for v in re.findall(r"^frame=(\d+)", txt, re.M)]
            if frames and self._n:
                k = min(self._n, frames[-1])
                self.progress.emit(92 + int(7 * k / self._n), "Assemblage de la vidéo…")
        except Exception:
            pass

    def _encode_error(self, err) -> None:
        if err == QProcess.ProcessError.FailedToStart:
            self._fail("Assemblage impossible : ffmpeg ne démarre pas.")

    def _encoded(self, code: int, _status) -> None:
        if self._finished:
            return
        try:
            if code != 0 or not os.path.isfile(self._tmp_out):
                err = bytes(self._proc.readAllStandardError()).decode("utf-8", "ignore").strip()
                raise RuntimeError((err or "ffmpeg a échoué")[-300:])
            os.replace(self._tmp_out, self._out)
        except Exception as e:
            self._fail(f"Assemblage impossible : {e}")
            return
        self._finish()
        self.progress.emit(100, "Prévisualisation prête.")
        self.done.emit(self._out)

    # ---------------------------------------------------------------- fin
    def _fail(self, msg: str) -> None:
        if self._finished:
            return
        self._finish()
        self.failed.emit(msg)

    def _finish(self) -> None:
        self._finished = True
        self._watchdog.stop()
        proc = getattr(self, "_proc", None)
        if proc is not None and proc.state() != QProcess.ProcessState.NotRunning:
            proc.kill()                      # délai dépassé ou abandon : ffmpeg ne survit pas
            proc.waitForFinished(2000)
        tmp = getattr(self, "_tmp_out", "")
        if tmp and os.path.isfile(tmp):      # vidéo à moitié écrite (jamais prise pour la bonne)
            try:
                os.remove(tmp)
            except OSError:
                pass
        if self._view is not None:
            self._view.hide()
            self._view.deleteLater()
            self._view = None
        shutil.rmtree(self._dir, ignore_errors=True)
