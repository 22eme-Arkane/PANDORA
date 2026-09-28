"""api/decor_swap.py — Worker « Changer le décor · acteurs intacts » (28/09/2026).

Enchaîne, dans un QThread, les étapes décrites dans core/decor_swap :
détourage VEED (fal) → décor sans personne → recomposition ffmpeg locale
→ rééclairage ID-V2V en option. Le résultat est un FICHIER LOCAL
(`local_file`), rangé ensuite par core/download comme un clip téléchargé.

Signaux : progress(int, str), done(dict), failed(str) — `done` et non
`finished`, qui masquerait le signal natif du QThread (règle maison).
Sans clé fal : simulation, comme les autres moteurs (`mock: True`).
Annulation coopérative : cancel() ou requestInterruption() (abandon_thread) ;
aucun signal n'est émis après.
"""

from __future__ import annotations

import os
import shutil
import tempfile
import time
import uuid
from urllib.parse import urlparse

from PyQt6.QtCore import QThread, pyqtSignal

from core import decor_swap as ds


class DecorSwapWorker(QThread):
    """params : video_path, prompt (le décor voulu), ref_image, plate_mode
    (core/decor_swap.PLATE_MODE_KEYS), image_engine, plate_file, harmonize,
    harmonize_strength, relight."""

    progress = pyqtSignal(int, str)
    done     = pyqtSignal(dict)
    failed   = pyqtSignal(str)

    LABEL = "Changer le décor"

    def __init__(self, params: dict):
        super().__init__()
        self.params = dict(params or {})
        self._cancelled = False
        self._tmp = ""

    # ── Cycle de vie ────────────────────────────────────────────────────────

    def cancel(self):
        self._cancelled = True

    def _stop(self) -> bool:
        try:
            return self._cancelled or self.isInterruptionRequested()
        except RuntimeError:
            return True

    def _say(self, pct: int, msg: str):
        if not self._stop():
            self.progress.emit(int(pct), msg)

    def run(self):
        try:
            result = self._run()
            if result is not None and not self._stop():
                self.done.emit(result)
        except Exception as e:
            if not self._stop():
                from core.worker import humanize_api_error
                self.failed.emit(humanize_api_error(f"{self.LABEL} : {e}"))
        finally:
            if self._tmp:
                shutil.rmtree(self._tmp, ignore_errors=True)

    # ── Étapes ──────────────────────────────────────────────────────────────

    def _inputs(self) -> tuple:
        """Vérifie tout ce qui ne coûte rien AVANT le premier appel payant."""
        p = self.params
        src = str(p.get("video_path") or "")
        if not (src and os.path.isfile(src)):
            raise RuntimeError("Clip source introuvable.")
        mode = str(p.get("plate_mode") or ds.PLATE_GEN_IMAGE)
        if mode not in ds.PLATE_MODE_KEYS:
            raise ValueError(f"Mode de décor inconnu : {mode}")
        ref = str(p.get("ref_image") or "")
        if ref and not os.path.isfile(ref):
            ref = ""
        plate_file = str(p.get("plate_file") or "")
        if mode == ds.PLATE_REF_IMAGE and not ref:
            raise RuntimeError("ajoutez l'image du nouveau décor en « Image de référence ».")
        if mode == ds.PLATE_FILE and not (plate_file and os.path.isfile(plate_file)):
            raise RuntimeError("choisissez le fichier du nouveau décor (image ou vidéo).")
        if mode == ds.PLATE_FILE and not (ds.is_video_file(plate_file) or ds.is_image_file(plate_file)):
            raise RuntimeError("le décor fourni doit être une image ou une vidéo.")
        info = ds.probe(src)
        if not (info["width"] and info["height"]):
            raise RuntimeError("clip illisible (ffprobe).")
        return src, mode, ref, plate_file, info

    def _run(self):
        p = self.params
        src, mode, ref, plate_file, info = self._inputs()
        from core.config import load_config
        key = str(load_config().get("api_key") or "").strip()
        if not key:
            for pct, msg in [(20, f"{self.LABEL} (mode mock)…"),
                             (100, "Terminé — mode mock (aucune clé fal.ai)")]:
                self._say(pct, msg)
                time.sleep(0.3)
            return {"video_url": "", "mock": True, "prompt": p.get("prompt", ""),
                    "mode": "edit", "model": ds.ENGINE_KEY, "credits_used": 0.0}

        os.environ["FAL_KEY"] = key
        import fal_client
        from api.video_engines import _fal_upload
        from core.video_utils import get_ffmpeg_exe
        ff = get_ffmpeg_exe()
        self._tmp = tempfile.mkdtemp(prefix="pandora_decor_")
        cost = 0.0
        desc_en = self._english(ds.clean_user_prompt(p.get("prompt", "")))

        # 1. Détourage des acteurs (VEED) — seul appel qui voit les visages, et
        #    il ne les redessine pas : il rend un masque.
        self._say(4, "Détourage des acteurs — envoi du clip…")
        src_url = _fal_upload(fal_client, src)
        if self._stop():
            return None
        self._say(10, "Détourage des acteurs (VEED)…")
        res = fal_client.subscribe(ds.MATTING_ENDPOINT, arguments=ds.matting_args(src_url))
        urls = ds.output_urls(res)
        if not urls:
            raise RuntimeError(f"détourage : aucun fichier rendu ({str(res)[:160]})")
        files = [self._download(u, f"matte{i}") for i, u in enumerate(urls)]
        alpha = ds.pick_alpha(files, saturation_of=ds.video_saturation)
        if len(files) == 1 and alpha.lower().endswith(".webm"):
            alpha = self._vp9_alpha(ff, alpha)
        cost += ds.matting_cost(info["frames"])
        mid = max(0.0, float(info["duration"] or 0.0) / 2.0)
        mask_png = os.path.join(self._tmp, "mask_mid.png")
        ds.run_ffmpeg(ds.frame_command(ff, alpha, mid, mask_png))
        if ds.mask_coverage(mask_png) < 0.003:
            raise RuntimeError("le détourage n'a trouvé personne dans le clip : rien à recomposer.")
        if self._stop():
            return None

        # 2. Le décor, SANS personne.
        self._say(35, "Nouveau décor…")
        plate, plate_is_video, c = self._make_plate(mode, desc_en, ref, plate_file, info,
                                                    fal_client, _fal_upload)
        cost += c
        if self._stop():
            return None

        # 3. Recomposition locale (pixels des acteurs = source).
        gains = None
        if p.get("harmonize", True):
            try:
                gains = self._gains(ff, src, mask_png, plate, plate_is_video, mid,
                                    float(p.get("harmonize_strength") or 0.5))
            except Exception:
                gains = None
        self._say(75, "Recomposition des acteurs sur le décor (ffmpeg)…")
        out = os.path.join(self._tmp, "composite.mp4")
        ds.run_ffmpeg(ds.composite_command(
            ff, src, alpha, plate, out, width=info["width"], height=info["height"],
            fps_str=info["fps_str"], plate_is_video=plate_is_video, gains=gains))
        if self._stop():
            return None

        # 4. Rééclairage IA (option, expérimental). Un échec ne perd pas le
        #    travail déjà payé : on livre la recomposition et on le dit.
        note = ""
        if p.get("relight"):
            if info["frames"] > ds.RELIGHT_MAX_FRAMES:
                note = "rééclairage IA ignoré : plan de plus de 241 images"
            else:
                try:
                    self._say(82, "Rééclairage IA des acteurs (ID-V2V, expérimental)…")
                    out, c = self._relight(ff, out, src, info, desc_en, fal_client, _fal_upload)
                    cost += c
                except Exception as e:
                    note = f"rééclairage IA échoué, recomposition livrée sans : {str(e)[:120]}"
        if self._stop():
            return None

        final = self._keep(out)
        self._say(100, f"{self.LABEL} ✓  ~${cost:.2f}" + (f"  ·  {note}" if note else ""))
        return {
            "local_file":   final,
            "video_url":    "",
            "prompt":       p.get("prompt", ""),
            "mode":         "edit",
            "model":        ds.ENGINE_KEY,
            "duration":     round(float(info["duration"] or 0.0), 2),
            "resolution":   "source",
            "credits_used": round(cost, 4),
            "cost_usd":     round(cost, 4),
            "seed":         0,
            "note":         note,
        }

    # ── Aides ───────────────────────────────────────────────────────────────

    @staticmethod
    def _english(text: str) -> str:
        """Le décor en anglais pour les moteurs ; en cas d'échec du fournisseur IA
        texte, le texte d'origine part tel quel (translate_to_english ne lève pas)."""
        if not text:
            return ""
        try:
            from core.lang import translate_to_english
            return translate_to_english(text) or text
        except Exception:
            return text

    def _download(self, url: str, stem: str) -> str:
        from core.download import download_video
        base = os.path.basename(urlparse(url).path) or "fichier.mp4"
        return download_video(url, self._tmp, f"{stem}_{base}")

    def _keep(self, path: str) -> str:
        """Sort le résultat du dossier temporaire (nettoyé en fin de run)."""
        d = os.path.join(tempfile.gettempdir(), "pandora_decor_out")
        os.makedirs(d, exist_ok=True)
        dest = os.path.join(d, f"decor_{uuid.uuid4().hex[:10]}.mp4")
        shutil.move(path, dest)
        return dest

    def _vp9_alpha(self, ff: str, webm: str) -> str:
        """Repli si VEED rend un seul VP9 avec alpha : on en extrait le masque."""
        out = os.path.join(self._tmp, "alpha_from_vp9.mp4")
        ds.run_ffmpeg([ff, "-y", "-hide_banner", "-loglevel", "error",
                       "-c:v", "libvpx-vp9", "-i", webm,
                       "-vf", "alphaextract,format=gray", "-c:v", "libx264",
                       "-pix_fmt", "yuv420p", "-crf", "12", out])
        return out

    def _make_plate(self, mode, desc_en, ref, plate_file, info, fal_client, up) -> tuple:
        """(chemin, est_une_vidéo, coût) du décor."""
        if mode == ds.PLATE_REF_IMAGE:
            return ref, False, 0.0
        if mode == ds.PLATE_FILE:
            return plate_file, ds.is_video_file(plate_file), 0.0
        w, h = int(info["width"]), int(info["height"])
        if mode == ds.PLATE_GEN_IMAGE:
            from core import image_engines as ie
            from core.image_call import subscribe
            eng = str(self.params.get("image_engine") or ie.DEFAULT_ENGINE)
            if eng not in ie.ENGINES:
                eng = ie.DEFAULT_ENGINE
            target = ie.ar_to_target(ds.aspect_label(
                w, h, ("21:9", "16:9", "3:2", "4:3", "1:1", "3:4", "2:3", "9:16")), "")
            refs = []
            if ref:
                if ie.is_comfy(eng):
                    refs = [ref]
                elif int(ie.ref_support(eng).get("max") or 0) > 0:
                    refs = [up(fal_client, ref)]
            endpoint, args, _kind = ie.build_request(
                eng, ds.plate_prompt_en(desc_en, video=False), target,
                "2K" if h > 720 else "1K", refs)
            self._say(40, f"Nouveau décor : image ({ie.short_label(eng)})…")
            res = subscribe(endpoint, args)
            path = self._download(ds.first_image_url(res), "plate")
            return path, False, ds.image_price(eng)
        # Vidéo Seedance 2.0 SANS personne : le filtre de ByteDance n'a aucun
        # visage à examiner. Image de référence → image → vidéo.
        from api.real import run_real
        from core import pricing
        dur = max(4, min(15, int(round(float(info["duration"] or 5.0)))))
        vres = "1080p" if h > 720 else "720p"
        params = {"mode": "i2v" if ref else "t2v", "model": "seedance-2.0",
                  "prompt": ds.plate_prompt_en(desc_en, video=True), "prompt_is_final": True,
                  "duration": dur, "resolution": vres, "aspect_ratio": ds.aspect_label(w, h),
                  "audio": False}
        if ref:
            params["image_path"] = ref
        self._say(40, "Nouveau décor : vidéo Seedance 2.0 (sans personne)…")
        res = run_real(params, lambda pct, msg: self._say(40 + int(int(pct) * 0.3),
                                                          f"Nouveau décor : {msg}"), self._stop)
        url = str((res or {}).get("video_url") or "")
        if not url.startswith("http"):
            raise RuntimeError("décor vidéo : aucune URL rendue.")
        path = self._download(url, "plate")
        return path, True, float(pricing.estimate("seedance-2.0", vres, dur)[0])

    def _gains(self, ff, src, mask_png, plate, plate_is_video, t, strength) -> tuple:
        src_png = os.path.join(self._tmp, "src_mid.png")
        ds.run_ffmpeg(ds.frame_command(ff, src, t, src_png))
        plate_png = plate
        if plate_is_video:
            plate_png = os.path.join(self._tmp, "plate_mid.png")
            pd = ds.probe(plate).get("duration") or 0.0
            ds.run_ffmpeg(ds.frame_command(ff, plate, min(t, max(0.0, pd - 0.1)), plate_png))
        return ds.harmonize_gains(ds.region_means(src_png, mask_png),
                                  ds.region_means(plate_png), strength)

    def _relight(self, ff, video, src, info, desc_en, fal_client, up) -> tuple:
        """ID-V2V : une image clé rééclairée (Nano Banana 2 /edit), propagée au plan.
        La vidéo rendue est muette : la piste du source revient, durée recalée."""
        from core import image_engines as ie
        from core.image_call import subscribe
        first = os.path.join(self._tmp, "relight_first.png")
        ds.run_ffmpeg(ds.frame_command(ff, video, 0.0, first))
        frame_url = up(fal_client, first)
        eng = ds.RELIGHT_KEYFRAME_ENGINE
        endpoint, args, _k = ie.build_request(eng, ds.RELIGHT_KEYFRAME_PROMPT,
                                              (int(info["width"]), int(info["height"])),
                                              "1K", [frame_url])
        key_url = ds.first_image_url(subscribe(endpoint, args))
        cost = ds.image_price(eng)
        self._say(88, "Rééclairage IA : propagation au plan…")
        video_url = up(fal_client, video)
        res = fal_client.subscribe(ds.RELIGHT_ENDPOINT, arguments={
            "prompt": ds.relight_prompt_en(desc_en),
            "video_url": video_url,
            "image_url": key_url,
            "resolution": "720p",
            "num_frames": int(min(ds.RELIGHT_MAX_FRAMES, max(17, int(info["frames"] or 17)))),
            "enable_safety_checker": False,
        })
        urls = ds.output_urls(res)
        if not urls:
            raise RuntimeError(f"aucune vidéo rendue ({str(res)[:120]})")
        relit = self._download(urls[0], "relit")
        cost += ds.relight_cost(info["duration"])
        rd = float(ds.probe(relit).get("duration") or 0.0)
        speed = (rd / float(info["duration"])) if (rd and info["duration"]) else 1.0
        out = os.path.join(self._tmp, "relit_audio.mp4")
        ds.run_ffmpeg(ds.remux_audio_command(ff, relit, src, out, speed))
        return out, cost
