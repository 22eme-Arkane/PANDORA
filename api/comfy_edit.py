"""api/comfy_edit.py — Worker « Modifier un clip » SUR VOTRE MACHINE (ComfyUI).

Même contrat que les workers fal de « Modifier un clip » (`progress`,
`finished(dict)`, `failed`) : le clip source part chez ComfyUI par un gabarit
officiel d'édition vidéo (core/comfy_video — Bernini-R, Capybara, VOID,
SeedVR2…), la vidéo rendue revient dans le dossier de sortie, et le résultat
porte `local_path` ET `video_url` (l'URL /view du serveur) pour que l'onglet
n'ait rien à savoir de ComfyUI. 0 $. Chantier du 24/09/2026.

params : engine (comfy_edit:<gabarit>), video_path, prompt (déjà en anglais
de préférence), negative, image_path (référence, si le gabarit en prend),
seed, engine_label.
"""

from __future__ import annotations

import os
import re
import time

from PyQt6.QtCore import pyqtSignal

from api.video_engines import _CancellableWorker, _video_output_dir
from core import comfy_video as _cv
from core.worker import humanize_api_error

#: Balises Seedance (@Video1, @Image1…) : sans sens pour un gabarit ComfyUI —
#: retirées du prompt, le clip et la référence entrent par leurs nœuds.
_TAG = re.compile(r"@(Video|Image|Audio|Element)\d*", re.I)
_TAG_WORDS = {"video": "the video", "image": "the reference image",
              "audio": "the audio", "element": "the reference element"}


def clean_prompt(text: str) -> str:
    t = _TAG.sub(lambda m: _TAG_WORDS.get(m.group(1).lower(), "the video"), text or "")
    return re.sub(r"\s{2,}", " ", t).strip()


class ComfyEditWorker(_CancellableWorker):
    progress = pyqtSignal(int, str)
    finished = pyqtSignal(dict)
    failed   = pyqtSignal(str)

    def __init__(self, params: dict):
        super().__init__()
        self.params = dict(params or {})
        self._label = self.params.get("engine_label") or "ComfyUI"

    def run(self):
        try:
            name = _cv.template_name(self.params.get("engine") or "") or self.params.get("template") or ""
            if not name:
                raise ValueError("Aucun gabarit ComfyUI d'édition vidéo choisi.")
            video_path = self.params.get("video_path") or ""
            if not (video_path and os.path.isfile(video_path)):
                raise RuntimeError("Clip source introuvable.")
            refs = [p for p in (self.params.get("image_path"), *(self.params.get("ref_images") or []))
                    if p and os.path.isfile(str(p))]
            t0 = time.time()

            def prog(msg: str):
                pct = 10 + min(75, int(time.time() - t0) // 6)
                self.progress.emit(pct, f"{self._label} — {msg}")

            prompt = clean_prompt(self.params.get("prompt") or "")
            # Les gabarits attendent l'anglais ; la traduction est celle de tous
            # les moteurs (core/lang) — sans clé IA, le texte part tel quel.
            if prompt:
                try:
                    from core.lang import translate_to_english
                    self.progress.emit(6, f"{self._label} — traduction du prompt…")
                    prompt = translate_to_english(prompt) or prompt
                except Exception:
                    pass
            res = _cv.subscribe(name, {
                "video_path": video_path,
                "prompt": prompt,
                "negative": self.params.get("negative") or "",
                "ref_urls": refs,
                "seed": self.params.get("seed"),
            }, progress=prog, is_cancelled=lambda: self._cancelled or self.isInterruptionRequested())
            if self._cancelled:
                return
            url = res["video"]["url"]
            self.progress.emit(90, f"{self._label} — rapatriement…")
            local = _cv.download(url, _video_output_dir(), f"comfy_edit_{int(time.time())}")
            self.progress.emit(100, f"{self._label} ✓  0 $")
            self.finished.emit({
                "video_url":    url,
                "url":          url,
                "local_path":   local,
                "prompt":       self.params.get("prompt") or "",
                "mode":         "t2v",
                "model":        f"comfy_edit:{name}",
                "credits_used": 0.0,
                "seed":         0,
            })
        except Exception as e:
            if not self._cancelled:
                self.failed.emit(humanize_api_error(f"Erreur {self._label} : {e}"))
