"""
api/video_engines.py — Moteurs vidéo alternatifs à Seedance 2.0.

Modèles fal.ai :
  - Happy Horse 1.0 T2V/I2V : alibaba/happy-horse/{text,image,reference}-to-video — $0.14-0.28/s
  - Kling O3 4K T2V/I2V     : fal-ai/kling-video/o3/4k/{text,image}-to-video      — $0.42/s
  - Kling v3 Pro I2V         : fal-ai/kling-video/v3/pro/image-to-video            — $0.112-0.196/s
  - Kling v3 Pro T2V         : fal-ai/kling-video/v3/pro/text-to-video             — $0.112-0.196/s
  - Kling v3 4K T2V          : fal-ai/kling-video/v3/4k/text-to-video              — $0.28-0.39/s
  - PixVerse v6 T2V          : fal-ai/pixverse/v6/text-to-video                    — $0.025-0.115/s
  - PixVerse v4.5 I2V        : fal-ai/pixverse/v4.5/image-to-video                 — $0.04-0.08/s
  - Veo 3.1 T2V              : fal-ai/veo3.1                                        — ~$1.00/vidéo
  - Sora 2 T2V               : fal-ai/sora-2/text-to-video                         — $0.10/s

Tous héritent d'une interface commune : progress(int,str) + finished(dict) + failed(str).
"""

import os
import time

from PyQt6.QtCore import QThread, pyqtSignal
from core.config import load_config
from core.worker import humanize_api_error
from core.pandora_dirs import get_bin_dir


def _video_output_dir(cfg: dict | None = None) -> str:
    """Dossier de sortie des clips vidéo (même logique que Seedance)."""
    from core.config import get_output_dir
    return get_output_dir(cfg)


# ── Utilitaires partagés (refs, upload, style) ────────────────────────────────

def _fal_upload(fal_client, path: str) -> str:
    """Upload un fichier local vers le CDN fal.ai.
    Gère les paths non-ASCII et supprime les warnings de retry fal_client.
    """
    import sys, io, mimetypes
    _cap = io.StringIO()
    _old_out, _old_err = sys.stdout, sys.stderr
    sys.stdout = sys.stderr = _cap
    try:
        try:
            path.encode("ascii")
        except (UnicodeEncodeError, UnicodeDecodeError):
            ct = mimetypes.guess_type(path)[0] or "application/octet-stream"
            with open(path, "rb") as _f:
                return fal_client.upload(_f.read(), content_type=ct)
        return fal_client.upload_file(path)
    finally:
        sys.stdout = _old_out
        sys.stderr = _old_err


def ensure_image_urls(fal_client, params: dict, emit_progress=None) -> None:
    """Adapte les params du workflow séquences/storyboard aux workers externes.

    Le workflow PANDORA fournit des CHEMINS LOCAUX (image_path = mood keyframe ou
    dernière frame de raccord, end_image_path = mood du plan suivant) ; les moteurs
    externes attendent des URLs. Uploade et bascule en i2v. Modifie params EN PLACE.
    """
    img = params.get("image_path", "")
    if img and os.path.isfile(img) and not params.get("image_url"):
        if emit_progress:
            emit_progress(6, "Upload de l'image de départ…")
        params["image_url"] = _fal_upload(fal_client, img)
        params["mode"] = "i2v"
    end = params.get("end_image_path", "")
    if end and os.path.isfile(end) and not params.get("end_image_url"):
        if emit_progress:
            emit_progress(8, "Upload de l'image de fin (keyframe)…")
        params["end_image_url"] = _fal_upload(fal_client, end)


def _analyze_style_ref(image_path: str) -> str:
    """Claude Haiku Vision → extrait les mots-clés de style d'une image.
    Retourne une chaîne EN (~12 mots) ou '' en cas d'erreur.

    VISION : volontairement sur Anthropic, hors couche core/ai_provider
    (le sélecteur d'assistant IA ne couvre que le texte en v1).
    """
    try:
        import base64, anthropic as _anthropic, mimetypes
        from core.config import load_config as _lc
        key = _lc().get("anthropic_key", "").strip()
        if not key:
            return ""
        ext = os.path.splitext(image_path)[1].lower()
        mime = {".jpg": "image/jpeg", ".jpeg": "image/jpeg",
                ".png": "image/png",  ".webp": "image/webp"}.get(ext, "image/jpeg")
        with open(image_path, "rb") as f:
            b64 = base64.standard_b64encode(f.read()).decode()
        client = _anthropic.Anthropic(api_key=key)
        msg = client.messages.create(
            model="claude-haiku-4-5", max_tokens=80,
            messages=[{"role": "user", "content": [
                {"type": "image", "source": {"type": "base64", "media_type": mime, "data": b64}},
                {"type": "text", "text": (
                    "Describe the visual style of this image in exactly 10-15 English words "
                    "as a video generation prompt prefix. Include: rendering medium, color treatment, "
                    "and film genre style. Output ONLY comma-separated keywords, no explanation."
                )},
            ]}],
        )
        return msg.content[0].text.strip().rstrip(".")
    except Exception:
        return ""


def _process_ref_images(fal_client, params: dict, emit_progress) -> tuple[list, list, str]:
    """Upload les ref_images locales et retourne (urls, roles, style_prefix).

    Utilisé par tous les workers qui supportent des images de référence.
    - urls  : liste des CDN URLs uploadées
    - roles : rôles correspondants ("style", "character", "decor", "accessory")
    - style_prefix : mots-clés extraits de l'image de style (ou '' si absent)
    """
    raw_images = [p for p in params.get("ref_images", []) if p and os.path.isfile(p)][:9]
    raw_roles  = params.get("ref_image_roles", [])
    # Aligne les rôles sur les images valides
    roles = []
    images = []
    for i, p in enumerate(raw_images):
        images.append(p)
        roles.append(raw_roles[i] if i < len(raw_roles) else "")

    # Style en premier pour la priorité d'attention
    pairs = sorted(zip(images, roles), key=lambda x: 0 if x[1] == "style" else 1)
    images = [p for p, _ in pairs]
    roles  = [r for _, r in pairs]

    style_prefix = ""
    if any(r == "style" for r in roles):
        style_path = next(p for p, r in zip(images, roles) if r == "style")
        style_prefix = _analyze_style_ref(style_path)

    uploaded_urls: list[str] = []
    uploaded_roles: list[str] = []
    for i, (path, role) in enumerate(zip(images, roles)):
        try:
            emit_progress(8 + i, f"Upload {role or 'ref'} : {os.path.basename(path)}…")
            url = _fal_upload(fal_client, path)
            uploaded_urls.append(url)
            uploaded_roles.append(role)
        except Exception:
            pass  # image ignorée, on continue

    return uploaded_urls, uploaded_roles, style_prefix


# ── Base annulable ────────────────────────────────────────────────────────────

class _CancellableWorker(QThread):
    """Base commune à tous les workers vidéo externes.

    Expose cancel() : déconnecte les signaux côté tab, arrête le thread.
    Les sous-classes vérifient self._cancelled avant d'émettre finished/failed.
    """

    def __init__(self):
        super().__init__()
        self._cancelled = False

    def cancel(self):
        # Annulation coopérative : les sous-classes vérifient self._cancelled avant
        # d'émettre. On coupe les signaux + quit sans terminate() (qui corromprait l'état).
        self._cancelled = True
        try:
            self.blockSignals(True)
        except Exception:
            pass
        self.requestInterruption()
        self.quit()
        self.wait(2000)


# ── Worker Kling v3 Pro ───────────────────────────────────────────────────────

class KlingWorker(_CancellableWorker):
    """
    Génère une vidéo via Kling Video v3 Pro.

    Modes :
      mode="i2v"  → image-to-video  (start_image_url requis)
      mode="t2v"  → text-to-video   (prompt seul)
    """
    progress = pyqtSignal(int, str)
    finished = pyqtSignal(dict)
    failed   = pyqtSignal(str)

    # Tarifs indicatifs (source : fal.ai, mai 2025)
    _PRICE_NO_AUDIO   = 0.112   # $/s
    _PRICE_WITH_AUDIO = 0.168   # $/s

    def __init__(self, params: dict):
        """
        params attendus :
          prompt          (str)  requis
          image_url       (str)  requis si mode='i2v'
          end_image_url   (str)  optionnel
          duration        (int)  3-15, défaut 5
          generate_audio  (bool) défaut True
          negative_prompt (str)  optionnel
          cfg_scale       (float) 0-1, défaut 0.5
          shot_type       (str)  "customize" | "intelligent"
          mode            (str)  "i2v" | "t2v", défaut "i2v"
        """
        super().__init__()
        self.params = params

    def run(self):
        cfg = load_config()
        key = cfg.get("api_key", "").strip()
        if not key:
            self._mock()
        else:
            self._real(key)

    def _mock(self):
        mode = self.params.get("mode", "i2v").upper()
        dur  = self.params.get("duration", 5)
        steps = [
            (10, f"Kling v3 Pro {mode} — mode mock…"),
            (40, "Génération vidéo Kling (simulation)…"),
            (80, f"Vidéo {dur}s en cours…"),
            (100, "Terminé — mode mock (aucune clé fal.ai)"),
        ]
        for pct, msg in steps:
            self.progress.emit(pct, msg)
            time.sleep(0.5)
        self.finished.emit({"url": "", "duration": dur, "model": "kling-v3-pro", "credits_used": 0})

    def _real(self, key: str):
        try:
            import fal_client
            import requests
            from core.lang import translate_to_english

            os.environ["FAL_KEY"] = key
            # Workflow séquences : image_path/end_image_path locaux → URLs i2v
            ensure_image_urls(fal_client, self.params, self.progress.emit)

            mode      = self.params.get("mode", "i2v")
            dur       = int(self.params.get("duration", 5))
            with_audio = self.params.get("generate_audio", True)
            variant   = self.params.get("variant", "pro")
            if variant == "4k":
                endpoint = "fal-ai/kling-video/v3/4k/text-to-video"
            elif mode == "i2v":
                endpoint = "fal-ai/kling-video/v3/pro/image-to-video"
            else:
                endpoint = "fal-ai/kling-video/v3/pro/text-to-video"

            price_rate = self._PRICE_WITH_AUDIO if with_audio else self._PRICE_NO_AUDIO
            cost_est   = dur * price_rate

            self.progress.emit(10, f"Kling v3 Pro {mode.upper()} — {dur}s (~${cost_est:.2f})…")

            prompt_raw = self.params.get("prompt", "")
            prompt_en  = translate_to_english(prompt_raw) if prompt_raw else ""

            # ── Style prefix depuis image de référence (Kling T2V ne supporte pas image_refs) ──
            ref_images = [p for p in self.params.get("ref_images", []) if p and os.path.isfile(p)]
            ref_roles  = self.params.get("ref_image_roles", [])
            if ref_images:
                style_path = next(
                    (p for p, r in zip(ref_images, ref_roles + [""] * 9) if r == "style"),
                    ref_images[0],
                )
                style_kw = _analyze_style_ref(style_path)
                if style_kw:
                    prompt_en = f"{style_kw}, {prompt_en}"

            args: dict = {
                "prompt":          prompt_en,
                "duration":        str(dur),
                "generate_audio":  with_audio,
                "shot_type":       self.params.get("shot_type", "customize"),
            }
            if mode == "i2v":
                img_url = self.params.get("image_url", "")
                if not img_url:
                    raise ValueError("Kling I2V : image_url requis.")
                args["start_image_url"] = img_url
                if self.params.get("end_image_url"):
                    args["end_image_url"] = self.params["end_image_url"]
            if self.params.get("negative_prompt"):
                args["negative_prompt"] = self.params["negative_prompt"]
            if self.params.get("cfg_scale") is not None:
                args["cfg_scale"] = float(self.params["cfg_scale"])

            self.progress.emit(20, "Appel Kling v3 Pro (peut prendre 1-2 min)…")

            result = fal_client.subscribe(endpoint, arguments=args)

            if not isinstance(result, dict):
                raise RuntimeError(f"Réponse inattendue : {str(result)[:200]}")

            video = result.get("video") or {}
            url   = video.get("url", "") if isinstance(video, dict) else ""
            if not url:
                raise RuntimeError(f"URL vidéo manquante : {str(result)[:200]}")

            self.progress.emit(80, "Téléchargement de la vidéo…")
            data = requests.get(url, timeout=300).content

            out_dir  = _video_output_dir()
            ts       = int(time.time())
            filename = f"kling_v3_{mode}_{dur}s_{ts}.mp4"
            local    = os.path.join(out_dir, filename)
            with open(local, "wb") as f:
                f.write(data)

            self.progress.emit(100, f"Kling v3 Pro ✓  {dur}s · ~${cost_est:.2f}")
            if not self._cancelled:
                self.finished.emit({
                    "url":          url,
                    "local_path":   local,
                    "duration":     dur,
                    "resolution":   "1080p",
                    "model":        f"kling-v3-pro-{mode}",
                    "credits_used": cost_est,
                })

        except Exception as e:
            if not self._cancelled:
                self.failed.emit(humanize_api_error(f"Erreur Kling : {e}"))


# ── Worker PixVerse v4.5 ──────────────────────────────────────────────────────

class PixVerseWorker(_CancellableWorker):
    """
    Génère une vidéo via PixVerse v4.5 Image-to-Video.

    Le modèle PixVerse est moins cher que Kling/Seedance mais sans audio natif.
    Idéal pour des itérations rapides et économiques.
    """
    progress = pyqtSignal(int, str)
    finished = pyqtSignal(dict)
    failed   = pyqtSignal(str)

    # Tarifs indicatifs
    _PRICE_720P  = 0.04   # $/s (5s = $0.20)
    _PRICE_1080P = 0.08   # $/s (5s = $0.40)

    def __init__(self, params: dict):
        """
        params attendus :
          prompt      (str)  requis
          image_url   (str)  requis
          duration    (int)  5 (seule option actuellement)
          resolution  (str)  "720p" | "1080p", défaut "720p"
        """
        super().__init__()
        self.params = params

    def run(self):
        cfg = load_config()
        key = cfg.get("api_key", "").strip()
        if not key:
            self._mock()
        else:
            self._real(key)

    def _mock(self):
        dur = self.params.get("duration", 5)
        steps = [
            (15, "PixVerse v4.5 — mode mock…"),
            (50, "Génération vidéo PixVerse (simulation)…"),
            (90, f"Vidéo {dur}s en cours…"),
            (100, "Terminé — mode mock (aucune clé fal.ai)"),
        ]
        for pct, msg in steps:
            self.progress.emit(pct, msg)
            time.sleep(0.5)
        self.finished.emit({"url": "", "duration": dur, "model": "pixverse-v4.5", "credits_used": 0})

    def _real(self, key: str):
        try:
            import fal_client
            import requests
            from core.lang import translate_to_english

            os.environ["FAL_KEY"] = key

            dur  = int(self.params.get("duration", 5))
            res  = self.params.get("resolution", "720p")
            rate = self._PRICE_1080P if res == "1080p" else self._PRICE_720P
            cost = dur * rate

            self.progress.emit(10, f"PixVerse v4.5 I2V — {dur}s {res} (~${cost:.2f})…")

            img_url = self.params.get("image_url", "")
            if not img_url:
                raise ValueError("PixVerse : image_url requis.")

            prompt_raw = self.params.get("prompt", "")
            prompt_en  = translate_to_english(prompt_raw) if prompt_raw else ""

            self.progress.emit(20, "Appel PixVerse v4.5 (environ 1 min)…")

            result = fal_client.subscribe(
                "fal-ai/pixverse/v4.5/image-to-video",
                arguments={
                    "prompt":    prompt_en,
                    "image_url": img_url,
                },
            )

            if not isinstance(result, dict):
                raise RuntimeError(f"Réponse inattendue : {str(result)[:200]}")

            video = result.get("video") or {}
            url   = video.get("url", "") if isinstance(video, dict) else ""
            if not url:
                url = result.get("url", "")
            if not url:
                raise RuntimeError(f"URL vidéo manquante : {str(result)[:200]}")

            self.progress.emit(80, "Téléchargement…")
            data = requests.get(url, timeout=300).content

            out_dir  = _video_output_dir()
            ts       = int(time.time())
            local    = os.path.join(out_dir, f"pixverse_{dur}s_{ts}.mp4")
            with open(local, "wb") as f:
                f.write(data)

            self.progress.emit(100, f"PixVerse ✓  {dur}s {res} · ~${cost:.2f}")
            self.finished.emit({
                "url":          url,
                "local_path":   local,
                "duration":     dur,
                "resolution":   res,
                "model":        "pixverse-v4.5-i2v",
                "credits_used": cost,
            })

        except Exception as e:
            self.failed.emit(humanize_api_error(f"Erreur PixVerse : {e}"))


# ── Worker Veo 3.1 ────────────────────────────────────────────────────────────

class Veo3Worker(_CancellableWorker):
    """
    Génère une vidéo via Veo 3.1 (Google / fal-ai).
    Vidéo 8 secondes · 1080p · audio natif · ~$1.00 / vidéo.
    """
    progress = pyqtSignal(int, str)
    finished = pyqtSignal(dict)
    failed   = pyqtSignal(str)

    def __init__(self, params: dict):
        super().__init__()
        self.params = params

    def run(self):
        cfg = load_config()
        key = cfg.get("api_key", "").strip()
        if not key:
            self._mock()
        else:
            self._real(key)

    def _mock(self):
        for pct, msg in [
            (10, "Veo 3.1 — mode mock…"),
            (50, "Génération vidéo Google (simulation)…"),
            (100, "Terminé — mode mock (aucune clé fal.ai)"),
        ]:
            self.progress.emit(pct, msg)
            time.sleep(0.5)
        self.finished.emit({
            "url": "", "duration": 8, "model": "veo-3.1",
            "resolution": "1080p", "credits_used": 0,
        })

    def _real(self, key: str):
        try:
            import fal_client
            import requests
            from core.lang import translate_to_english

            os.environ["FAL_KEY"] = key

            prompt_raw = self.params.get("prompt", "")
            prompt_en  = translate_to_english(prompt_raw) if prompt_raw else ""

            # ── Style prefix depuis image de référence (Veo 3.1 ne supporte pas image_refs) ──
            ref_images = [p for p in self.params.get("ref_images", []) if p and os.path.isfile(p)]
            ref_roles  = self.params.get("ref_image_roles", [])
            if ref_images:
                style_path = next(
                    (p for p, r in zip(ref_images, ref_roles + [""] * 9) if r == "style"),
                    ref_images[0],
                )
                style_kw = _analyze_style_ref(style_path)
                if style_kw:
                    prompt_en = f"{style_kw}, {prompt_en}"

            self.progress.emit(10, "Veo 3.1 — soumission (peut prendre 2-3 min)…")

            result = fal_client.subscribe(
                "fal-ai/veo3.1",
                arguments={"prompt": prompt_en},
                with_logs=False,
            )

            if not isinstance(result, dict):
                raise RuntimeError(f"Réponse inattendue : {str(result)[:200]}")

            video     = result.get("video") or {}
            url       = (video.get("url", "") if isinstance(video, dict)
                         else result.get("url", ""))
            duration  = (video.get("duration", 8) if isinstance(video, dict) else 8)
            if not url:
                raise RuntimeError(f"URL vidéo manquante : {str(result)[:200]}")

            self.progress.emit(80, "Téléchargement de la vidéo…")
            data = requests.get(url, timeout=300).content

            out_dir  = _video_output_dir()
            ts       = int(time.time())
            local    = os.path.join(out_dir, f"veo31_{ts}.mp4")
            with open(local, "wb") as f:
                f.write(data)

            self.progress.emit(100, f"Veo 3.1 ✓  {duration}s · 1080p")
            if not self._cancelled:
                self.finished.emit({
                    "url":          url,
                    "local_path":   local,
                    "duration":     duration,
                    "resolution":   "1080p",
                    "model":        "veo-3.1",
                    "credits_used": 1.0,
                })

        except Exception as e:
            if not self._cancelled:
                self.failed.emit(humanize_api_error(f"Erreur Veo 3.1 : {e}"))


# ── Worker Happy Horse 1.0 ────────────────────────────────────────────────────

class HappyHorseWorker(_CancellableWorker):
    """
    Génère une vidéo via Happy Horse 1.0 (Alibaba / fal.ai).
    #1 Video Arena · modes T2V, I2V, Ref-to-Video.
    720p : $0.14/s · 1080p : $0.28/s
    """
    progress = pyqtSignal(int, str)
    finished = pyqtSignal(dict)
    failed   = pyqtSignal(str)

    _PRICE = {"720p": 0.14, "1080p": 0.28}

    def __init__(self, params: dict):
        """
        params attendus :
          prompt       (str)  requis
          mode         (str)  "t2v" | "i2v" | "ref"
          image_url    (str)  requis si mode i2v ou ref
          duration     (int)  3-15, défaut 5
          resolution   (str)  "720p" | "1080p", défaut "720p"
          aspect_ratio (str)  "16:9" | "9:16" | "1:1", défaut "16:9"
        """
        super().__init__()
        self.params = params

    def run(self):
        cfg = load_config()
        key = cfg.get("api_key", "").strip()
        if not key:
            self._mock()
        else:
            self._real(key)

    def _mock(self):
        mode = self.params.get("mode", "t2v").upper()
        dur  = self.params.get("duration", 5)
        for pct, msg in [
            (10, f"Happy Horse 1.0 {mode} — mode mock…"),
            (40, "Génération vidéo (simulation)…"),
            (80, f"Vidéo {dur}s en cours…"),
            (100, "Terminé — mode mock (aucune clé fal.ai)"),
        ]:
            self.progress.emit(pct, msg)
            time.sleep(0.5)
        self.finished.emit({"url": "", "duration": dur, "model": "happy-horse-1.0", "credits_used": 0})

    def _real(self, key: str):
        try:
            import fal_client
            import requests
            from core.lang import translate_to_english

            os.environ["FAL_KEY"] = key
            # Workflow séquences : image_path/end_image_path locaux → URLs i2v
            ensure_image_urls(fal_client, self.params, self.progress.emit)

            mode     = self.params.get("mode", "t2v")
            dur      = int(self.params.get("duration", 5))
            res      = self.params.get("resolution", "720p")
            ratio    = self.params.get("aspect_ratio", "16:9")
            cost_est = dur * self._PRICE.get(res, 0.14)

            _ep_map = {
                "t2v": "alibaba/happy-horse/text-to-video",
                "i2v": "alibaba/happy-horse/image-to-video",
                "ref": "alibaba/happy-horse/reference-to-video",
            }
            endpoint = _ep_map.get(mode, _ep_map["t2v"])

            self.progress.emit(5, f"Happy Horse 1.0 {mode.upper()} — {dur}s {res} (~${cost_est:.2f})…")

            prompt_raw = self.params.get("prompt", "")
            prompt_en  = translate_to_english(prompt_raw) if prompt_raw else ""

            # ── Références visuelles (personnages, décor, style, accessoires) ──
            # Happy Horse reference-to-video accepte jusqu'à 9 images via image_urls.
            # Les images sont référencées positionnellement dans le prompt (character1, character2…).
            ref_images = [p for p in self.params.get("ref_images", []) if p and os.path.isfile(p)]
            ref_roles  = self.params.get("ref_image_roles", [])

            uploaded_urls:  list[str] = []
            uploaded_roles: list[str] = []
            style_prefix = ""

            if ref_images and mode == "t2v":
                # Basculer en reference-to-video
                mode     = "ref"
                endpoint = _ep_map["ref"]
                self.progress.emit(6, "Références visuelles détectées — mode Reference-to-Video…")

                uploaded_urls, uploaded_roles, style_prefix = _process_ref_images(
                    fal_client, self.params, self.progress.emit
                )

            args: dict = {
                "prompt":       prompt_en,
                "duration":     dur,
                "resolution":   res,
                "aspect_ratio": ratio,
            }

            if uploaded_urls:
                args["image_urls"] = uploaded_urls
                # Injections de prompt pour Happy Horse (positional: character1, character2…)
                additions: list[str] = []
                for idx, role in enumerate(uploaded_roles, start=1):
                    if role == "style":
                        additions.append(
                            f"character{idx}: this is a STYLE REFERENCE — "
                            f"replicate its rendering medium, color treatment, film grain and "
                            f"cinematographic aesthetic across the entire video."
                        )
                    elif role == "character":
                        additions.append(
                            f"character{idx}: these are the film characters — "
                            f"match their face, skin tone, hair and clothing exactly."
                        )
                    elif role == "decor":
                        additions.append(
                            f"character{idx}: this is the filming location — "
                            f"use this spatial layout and architecture as the scene background."
                        )
                    elif role == "accessory":
                        additions.append(
                            f"character{idx}: these are the props/accessories — "
                            f"include them in the scene."
                        )
                if additions:
                    args["prompt"] = prompt_en + ". " + " ".join(additions)

            # Préfixe style depuis l'analyse vision Claude (si image de style présente)
            if style_prefix:
                args["prompt"] = f"{style_prefix}, {args['prompt']}"

            # Suffixes style/audio hérités du tab T2V (même pipeline que Seedance)
            for key_suf, sep in [("style_suffix", ", "), ("no_music_suffix", ", "),
                                  ("char_consistency_suffix", ", "), ("creative_suffix", ", ")]:
                v = self.params.get(key_suf, "")
                if v and args.get("prompt"):
                    args["prompt"] = args["prompt"] + sep + v

            if mode in ("i2v",) and not uploaded_urls:
                img_url = self.params.get("image_url", "")
                if not img_url:
                    raise ValueError("Happy Horse I2V : image_url requis.")
                args["image_url"] = img_url

            if self.params.get("seed"):
                args["seed"] = int(self.params["seed"])

            self.progress.emit(20, "Appel Happy Horse 1.0 (peut prendre 1-3 min)…")

            result = fal_client.subscribe(endpoint, arguments=args)

            if not isinstance(result, dict):
                raise RuntimeError(f"Réponse inattendue : {str(result)[:200]}")

            video = result.get("video") or {}
            url   = video.get("url", "") if isinstance(video, dict) else ""
            if not url:
                url = result.get("url", "")
            if not url:
                raise RuntimeError(f"URL vidéo manquante : {str(result)[:200]}")

            self.progress.emit(80, "Téléchargement de la vidéo…")
            data = requests.get(url, timeout=300).content

            out_dir = _video_output_dir()
            ts      = int(time.time())
            local   = os.path.join(out_dir, f"happy_horse_{mode}_{dur}s_{ts}.mp4")
            with open(local, "wb") as f:
                f.write(data)

            self.progress.emit(100, f"Happy Horse ✓  {dur}s {res} · ~${cost_est:.2f}")
            if not self._cancelled:
                self.finished.emit({
                    "url":          url,
                    "local_path":   local,
                    "duration":     dur,
                    "resolution":   res,
                    "model":        f"happy-horse-1.0-{mode}",
                    "credits_used": cost_est,
                    "ref_images_sent": len(uploaded_urls),
                    "ref_images_attempted": len(ref_images),
                })

        except Exception as e:
            if not self._cancelled:
                self.failed.emit(humanize_api_error(f"Erreur Happy Horse : {e}"))


# ── Worker Kling O3 4K ────────────────────────────────────────────────────────

class KlingO3Worker(_CancellableWorker):
    """
    Génère une vidéo via Kling O3 4K (ByteDance / fal.ai).
    Résolution 4K · modes T2V et I2V.
    ~$0.42/s
    """
    progress = pyqtSignal(int, str)
    finished = pyqtSignal(dict)
    failed   = pyqtSignal(str)

    _PRICE = 0.42

    def __init__(self, params: dict):
        """
        params attendus :
          prompt         (str)  requis
          mode           (str)  "t2v" | "i2v"
          image_url      (str)  requis si mode i2v
          duration       (int)  3-15, défaut 5
          generate_audio (bool) défaut False
        """
        super().__init__()
        self.params = params

    def run(self):
        cfg = load_config()
        key = cfg.get("api_key", "").strip()
        if not key:
            self._mock()
        else:
            self._real(key)

    def _mock(self):
        mode = self.params.get("mode", "t2v").upper()
        dur  = self.params.get("duration", 5)
        for pct, msg in [
            (10, f"Kling O3 4K {mode} — mode mock…"),
            (40, "Génération vidéo 4K (simulation)…"),
            (80, f"Vidéo {dur}s en cours…"),
            (100, "Terminé — mode mock (aucune clé fal.ai)"),
        ]:
            self.progress.emit(pct, msg)
            time.sleep(0.5)
        self.finished.emit({"url": "", "duration": dur, "model": "kling-o3-4k", "credits_used": 0})

    def _real(self, key: str):
        try:
            import fal_client
            import requests
            from core.lang import translate_to_english

            os.environ["FAL_KEY"] = key
            # Workflow séquences : image_path/end_image_path locaux → URLs i2v
            ensure_image_urls(fal_client, self.params, self.progress.emit)

            mode       = self.params.get("mode", "t2v")
            dur        = int(self.params.get("duration", 5))
            with_audio = self.params.get("generate_audio", False)
            cost_est   = dur * self._PRICE

            endpoint = (
                "fal-ai/kling-video/o3/4k/image-to-video"
                if mode == "i2v"
                else "fal-ai/kling-video/o3/4k/text-to-video"
            )

            self.progress.emit(10, f"Kling O3 4K {mode.upper()} — {dur}s (~${cost_est:.2f})…")

            prompt_raw = self.params.get("prompt", "")
            prompt_en  = translate_to_english(prompt_raw) if prompt_raw else ""

            # ── Style prefix depuis image de référence (Kling O3 ne supporte pas image_refs) ──
            ref_images = [p for p in self.params.get("ref_images", []) if p and os.path.isfile(p)]
            ref_roles  = self.params.get("ref_image_roles", [])
            if ref_images:
                style_path = next(
                    (p for p, r in zip(ref_images, ref_roles + [""] * 9) if r == "style"),
                    ref_images[0],
                )
                style_kw = _analyze_style_ref(style_path)
                if style_kw:
                    prompt_en = f"{style_kw}, {prompt_en}"

            args: dict = {
                "prompt":         prompt_en,
                "duration":       str(dur),
                "generate_audio": with_audio,
            }
            if mode == "i2v":
                img_url = self.params.get("image_url", "")
                if not img_url:
                    raise ValueError("Kling O3 I2V : image_url requis.")
                args["start_image_url"] = img_url

            self.progress.emit(20, "Appel Kling O3 4K (peut prendre 2-4 min)…")

            result = fal_client.subscribe(endpoint, arguments=args)

            if not isinstance(result, dict):
                raise RuntimeError(f"Réponse inattendue : {str(result)[:200]}")

            video = result.get("video") or {}
            url   = video.get("url", "") if isinstance(video, dict) else ""
            if not url:
                url = result.get("url", "")
            if not url:
                raise RuntimeError(f"URL vidéo manquante : {str(result)[:200]}")

            self.progress.emit(80, "Téléchargement de la vidéo 4K…")
            data = requests.get(url, timeout=600).content

            out_dir  = _video_output_dir()
            ts       = int(time.time())
            local    = os.path.join(out_dir, f"kling_o3_{mode}_{dur}s_{ts}.mp4")
            with open(local, "wb") as f:
                f.write(data)

            self.progress.emit(100, f"Kling O3 4K ✓  {dur}s · ~${cost_est:.2f}")
            if not self._cancelled:
                self.finished.emit({
                    "url":          url,
                    "local_path":   local,
                    "duration":     dur,
                    "resolution":   "4K",
                    "model":        f"kling-o3-4k-{mode}",
                    "credits_used": cost_est,
                })

        except Exception as e:
            if not self._cancelled:
                self.failed.emit(humanize_api_error(f"Erreur Kling O3 : {e}"))


# ── Worker PixVerse v6 ────────────────────────────────────────────────────────

class PixVerseV6Worker(_CancellableWorker):
    """
    Génère une vidéo via PixVerse v6 Text-to-Video.
    Résolutions 360p–1080p · avec ou sans audio natif.
    $0.025–$0.115/s selon résolution.
    """
    progress = pyqtSignal(int, str)
    finished = pyqtSignal(dict)
    failed   = pyqtSignal(str)

    _PRICE = {"360p": 0.025, "540p": 0.05, "720p": 0.075, "1080p": 0.115}

    def __init__(self, params: dict):
        """
        params attendus :
          prompt         (str)  requis
          resolution     (str)  "360p" | "540p" | "720p" | "1080p", défaut "720p"
          duration       (int)  3-8, défaut 5
          generate_audio (bool) défaut False
          aspect_ratio   (str)  "16:9" | "9:16" | "1:1", défaut "16:9"
        """
        super().__init__()
        self.params = params

    def run(self):
        cfg = load_config()
        key = cfg.get("api_key", "").strip()
        if not key:
            self._mock()
        else:
            self._real(key)

    def _mock(self):
        dur = self.params.get("duration", 5)
        res = self.params.get("resolution", "720p")
        for pct, msg in [
            (15, f"PixVerse v6 — mode mock ({res})…"),
            (50, "Génération vidéo (simulation)…"),
            (90, f"Vidéo {dur}s en cours…"),
            (100, "Terminé — mode mock (aucune clé fal.ai)"),
        ]:
            self.progress.emit(pct, msg)
            time.sleep(0.5)
        self.finished.emit({"url": "", "duration": dur, "model": "pixverse-v6", "credits_used": 0})

    def _real(self, key: str):
        try:
            import fal_client
            import requests
            from core.lang import translate_to_english

            os.environ["FAL_KEY"] = key
            # Workflow séquences : image_path/end_image_path locaux → URLs i2v
            ensure_image_urls(fal_client, self.params, self.progress.emit)

            dur      = int(self.params.get("duration", 5))
            res      = self.params.get("resolution", "720p")
            ratio    = self.params.get("aspect_ratio", "16:9")
            audio    = self.params.get("generate_audio", False)
            cost_est = dur * self._PRICE.get(res, 0.075)

            self.progress.emit(10, f"PixVerse v6 — {dur}s {res} (~${cost_est:.2f})…")

            prompt_raw = self.params.get("prompt", "")
            prompt_en  = translate_to_english(prompt_raw) if prompt_raw else ""

            # ── Références visuelles (PixVerse v6 reference-to-video) ────────────
            ref_images = [p for p in self.params.get("ref_images", []) if p and os.path.isfile(p)]
            ref_roles  = self.params.get("ref_image_roles", [])
            uploaded_refs: list[dict] = []
            style_prefix = ""
            endpoint = "fal-ai/pixverse/v6/text-to-video"

            if ref_images:
                endpoint = "fal-ai/pixverse/v6/reference-to-video"
                self.progress.emit(6, "Références détectées — mode Reference-to-Video PixVerse…")
                _pv_type_map = {
                    "style":     "style_reference",
                    "character": "character_reference",
                    "decor":     "scene_reference",
                    "accessory": "subject_reference",
                }
                pairs = sorted(
                    zip(ref_images, ref_roles + [""] * len(ref_images)),
                    key=lambda x: 0 if x[1] == "style" else 1,
                )
                for i, (path, role) in enumerate(list(pairs)[:9]):
                    try:
                        self.progress.emit(8 + i, f"Upload {role or 'ref'} : {os.path.basename(path)}…")
                        cdn_url  = _fal_upload(fal_client, path)
                        ref_name = "style" if role == "style" else f"ref{i + 1}"
                        pv_type  = _pv_type_map.get(role, "subject_reference")
                        if role == "style":
                            style_prefix = _analyze_style_ref(path)
                        uploaded_refs.append({
                            "image_url": cdn_url,
                            "type":      pv_type,
                            "ref_name":  ref_name,
                        })
                    except Exception:
                        pass

                # Inject @ref_name mentions into prompt
                ref_additions = []
                for ref in uploaded_refs:
                    rname = ref["ref_name"]
                    rtype = ref["type"]
                    if rtype == "character_reference":
                        ref_additions.append(f"featuring @{rname}")
                    elif rtype == "style_reference":
                        ref_additions.append(f"in @{rname} visual style")
                    elif rtype == "scene_reference":
                        ref_additions.append(
                            f"filmed in the location shown in @{rname} — "
                            f"camera moves freely through this space, exploring different angles"
                        )
                    elif rtype == "subject_reference":
                        ref_additions.append(f"with @{rname}")
                if ref_additions:
                    prompt_en = prompt_en + ", " + ", ".join(ref_additions)

            if style_prefix:
                prompt_en = f"{style_prefix}, {prompt_en}"

            self.progress.emit(20, "Appel PixVerse v6 (environ 1 min)…")

            args: dict = {
                "prompt":         prompt_en,
                "resolution":     res,
                "duration":       dur,
                "aspect_ratio":   ratio,
                "generate_audio": audio,
            }
            if uploaded_refs:
                args["image_references"] = uploaded_refs

            result = fal_client.subscribe(endpoint, arguments=args)

            if not isinstance(result, dict):
                raise RuntimeError(f"Réponse inattendue : {str(result)[:200]}")

            video = result.get("video") or {}
            url   = video.get("url", "") if isinstance(video, dict) else ""
            if not url:
                url = result.get("url", "")
            if not url:
                raise RuntimeError(f"URL vidéo manquante : {str(result)[:200]}")

            self.progress.emit(80, "Téléchargement de la vidéo…")
            data = requests.get(url, timeout=300).content

            out_dir  = _video_output_dir()
            ts       = int(time.time())
            mode_tag = "ref" if uploaded_refs else "t2v"
            local    = os.path.join(out_dir, f"pixverse_v6_{mode_tag}_{dur}s_{ts}.mp4")
            with open(local, "wb") as f:
                f.write(data)

            self.progress.emit(100, f"PixVerse v6 ✓  {dur}s {res} · ~${cost_est:.2f}")
            if not self._cancelled:
                self.finished.emit({
                    "url":                  url,
                    "local_path":           local,
                    "duration":             dur,
                    "resolution":           res,
                    "model":                f"pixverse-v6-{mode_tag}",
                    "credits_used":         cost_est,
                    "ref_images_sent":      len(uploaded_refs),
                    "ref_images_attempted": len(ref_images),
                })

        except Exception as e:
            if not self._cancelled:
                self.failed.emit(humanize_api_error(f"Erreur PixVerse v6 : {e}"))


# ── Worker Sora 2 ─────────────────────────────────────────────────────────────

def _style_prefix_from_refs(params: dict) -> str:
    """Préfixe de style EN extrait d'une image de référence (vision Claude), ou ''."""
    ref_images = [p for p in params.get("ref_images", []) if p and os.path.isfile(p)]
    ref_roles  = params.get("ref_image_roles", [])
    if not ref_images:
        return ""
    style_path = next(
        (p for p, r in zip(ref_images, ref_roles + [""] * 9) if r == "style"),
        ref_images[0],
    )
    return _analyze_style_ref(style_path)


def _extract_video_url(result) -> str:
    """Extrait l'URL vidéo d'une réponse fal.ai (formes variables selon moteur)."""
    if not isinstance(result, dict):
        return ""
    v = result.get("video")
    if isinstance(v, dict):
        return v.get("url", "")
    if isinstance(v, list) and v:
        first = v[0]
        return (first.get("url", "") if isinstance(first, dict)
                else first if isinstance(first, str) else "")
    return result.get("url", "") or result.get("video_url", "")


class _SimpleFalVideoWorker(_CancellableWorker):
    """Base générique pour les moteurs vidéo fal.ai « standards » (T2V + I2V option).

    Gère : bascule mock/réel, traduction du prompt, préfixe de style depuis une
    image de référence, upload des images de départ/fin (ensure_image_urls →
    image_url/end_image_url), construction d'args minimale pilotée par flags pour
    éviter les erreurs de paramètres inconnus, téléchargement et émission du dict.

    Les sous-classes ne déclarent que des attributs de classe.
    """
    progress = pyqtSignal(int, str)
    finished = pyqtSignal(dict)
    failed   = pyqtSignal(str)

    ENDPOINT_T2V    = ""
    ENDPOINT_I2V    = ""      # "" → moteur text-to-video uniquement
    MODEL           = "video"
    PRICE_PER_S     = 0.0     # $/s estimé (0 → utilise FLAT_PRICE)
    FLAT_PRICE      = 0.0     # $/vidéo (modèles à prix fixe, ex. Hailuo)
    AUDIO           = False   # envoie generate_audio
    END_FRAME       = False   # supporte end_image_url (raccords / keyframes)
    SEND_RESOLUTION = False
    SEND_RATIO      = False
    SEND_DURATION   = False
    DUR_STR         = True    # duration en str (famille ByteDance) sinon int
    DEFAULT_DUR     = 5

    def __init__(self, params: dict):
        super().__init__()
        self.params = params

    def run(self):
        key = load_config().get("api_key", "").strip()
        if not key:
            self._mock()
        else:
            self._real(key)

    def _mock(self):
        dur = self.params.get("duration", self.DEFAULT_DUR)
        for pct, msg in [
            (12, f"{self.MODEL} — mode mock…"),
            (55, "Génération vidéo (simulation)…"),
            (100, "Terminé — mode mock (aucune clé fal.ai)"),
        ]:
            self.progress.emit(pct, msg)
            time.sleep(0.4)
        self.finished.emit({"url": "", "duration": dur, "model": self.MODEL, "credits_used": 0})

    def _real(self, key: str):
        try:
            import fal_client
            import requests
            from core.lang import translate_to_english

            os.environ["FAL_KEY"] = key
            # Workflow / formulaire I2V : image_path/end_image_path locaux → URLs.
            ensure_image_urls(fal_client, self.params, self.progress.emit)

            mode = self.params.get("mode", "t2v")
            if mode == "i2v" and not self.ENDPOINT_I2V:
                mode = "t2v"
            endpoint = self.ENDPOINT_I2V if (mode == "i2v" and self.ENDPOINT_I2V) else self.ENDPOINT_T2V

            try:
                dur = int(self.params.get("duration", self.DEFAULT_DUR) or self.DEFAULT_DUR)
            except (TypeError, ValueError):
                dur = self.DEFAULT_DUR

            prompt_raw = self.params.get("prompt", "")
            prompt_en  = translate_to_english(prompt_raw) if prompt_raw else ""
            style_kw   = _style_prefix_from_refs(self.params)
            if style_kw:
                prompt_en = f"{style_kw}, {prompt_en}" if prompt_en else style_kw

            args: dict = {"prompt": prompt_en}
            if self.SEND_RESOLUTION:
                res = (self.params.get("resolution", "720p") or "720p").split()[0]
                args["resolution"] = res
            if self.SEND_RATIO:
                args["aspect_ratio"] = self.params.get("aspect_ratio", "16:9")
            if self.SEND_DURATION:
                args["duration"] = str(dur) if self.DUR_STR else dur
            if self.AUDIO:
                args["generate_audio"] = self.params.get("generate_audio", True)
            if mode == "i2v":
                img_url = self.params.get("image_url", "")
                if not img_url:
                    raise ValueError(f"{self.MODEL} I2V : image de départ requise.")
                args["image_url"] = img_url
                if self.END_FRAME and self.params.get("end_image_url"):
                    args["end_image_url"] = self.params["end_image_url"]

            cost = dur * self.PRICE_PER_S if self.PRICE_PER_S else self.FLAT_PRICE
            self.progress.emit(15, f"{self.MODEL} {mode.upper()} (peut prendre 1-3 min)…")

            result = fal_client.subscribe(endpoint, arguments=args)
            url = _extract_video_url(result)
            if not url:
                raise RuntimeError(f"URL vidéo manquante : {str(result)[:200]}")

            self.progress.emit(80, "Téléchargement de la vidéo…")
            data = requests.get(url, timeout=600).content

            out_dir = _video_output_dir()
            ts      = int(time.time())
            safe    = "".join(c for c in self.MODEL if c.isalnum() or c in "-_") or "video"
            local   = os.path.join(out_dir, f"{safe}_{mode}_{dur}s_{ts}.mp4")
            with open(local, "wb") as f:
                f.write(data)

            self.progress.emit(100, f"{self.MODEL} ✓  {dur}s · ~${cost:.2f}")
            if not self._cancelled:
                self.finished.emit({
                    "url":          url,
                    "local_path":   local,
                    "duration":     dur,
                    "resolution":   self.params.get("resolution", "720p"),
                    "model":        f"{self.MODEL}-{mode}",
                    "credits_used": cost,
                })

        except Exception as e:
            if not self._cancelled:
                self.failed.emit(humanize_api_error(f"Erreur {self.MODEL} : {e}"))


class Seedance15Worker(_SimpleFalVideoWorker):
    """Seedance 1.5 Pro (ByteDance) — audio natif + start/end frame. T2V + I2V.
    ⚠ Préfixe `fal-ai/bytedance/...` (≠ Seedance 2.0 en `bytedance/...`). 720p, 4-12 s."""
    ENDPOINT_T2V    = "fal-ai/bytedance/seedance/v1.5/pro/text-to-video"
    ENDPOINT_I2V    = "fal-ai/bytedance/seedance/v1.5/pro/image-to-video"
    MODEL           = "seedance-1.5-pro"
    PRICE_PER_S     = 0.052
    AUDIO           = True
    END_FRAME       = True
    SEND_RESOLUTION = True
    SEND_RATIO      = True
    SEND_DURATION   = True
    DUR_STR         = True
    DEFAULT_DUR     = 5


class LTX2Worker(_SimpleFalVideoWorker):
    """LTX-2 (Lightricks) — 4K natif + audio stéréo. T2V + I2V."""
    ENDPOINT_T2V = "fal-ai/ltx-2/text-to-video"
    ENDPOINT_I2V = "fal-ai/ltx-2/image-to-video"
    MODEL        = "ltx-2"
    PRICE_PER_S  = 0.04
    SEND_RATIO   = True
    DEFAULT_DUR  = 5


class Wan27Worker(_SimpleFalVideoWorker):
    """Wan 2.7 (Alibaba) — first/last frame, leader Wan-Bench. T2V."""
    ENDPOINT_T2V = "fal-ai/wan/v2.7/text-to-video"
    MODEL        = "wan-2.7"
    SEND_RATIO   = True
    DEFAULT_DUR  = 5


class Hailuo23Worker(_SimpleFalVideoWorker):
    """MiniMax Hailuo 2.3 Pro — audio natif, prix fixe ~$0.49/vidéo. T2V."""
    ENDPOINT_T2V = "fal-ai/minimax/hailuo-2.3/pro/text-to-video"
    MODEL        = "hailuo-2.3-pro"
    FLAT_PRICE   = 0.49
    DEFAULT_DUR  = 6


class Sora2Worker(_CancellableWorker):
    """
    Génère une vidéo via Sora 2 (OpenAI / fal.ai).
    Durée fixe 4 s · $0.10/s (~$0.40 par vidéo).
    """
    progress = pyqtSignal(int, str)
    finished = pyqtSignal(dict)
    failed   = pyqtSignal(str)

    def __init__(self, params: dict):
        """
        params attendus :
          prompt       (str)  requis
          aspect_ratio (str)  "16:9" | "9:16" | "1:1", défaut "16:9"
        """
        super().__init__()
        self.params = params

    def run(self):
        cfg = load_config()
        key = cfg.get("api_key", "").strip()
        if not key:
            self._mock()
        else:
            self._real(key)

    def _mock(self):
        for pct, msg in [
            (10, "Sora 2 — mode mock…"),
            (50, "Génération vidéo OpenAI (simulation)…"),
            (100, "Terminé — mode mock (aucune clé fal.ai)"),
        ]:
            self.progress.emit(pct, msg)
            time.sleep(0.5)
        self.finished.emit({"url": "", "duration": 4, "model": "sora-2", "credits_used": 0})

    def _real(self, key: str):
        try:
            import fal_client
            import requests
            from core.lang import translate_to_english

            os.environ["FAL_KEY"] = key

            ratio      = self.params.get("aspect_ratio", "16:9")
            prompt_raw = self.params.get("prompt", "")
            prompt_en  = translate_to_english(prompt_raw) if prompt_raw else ""

            # ── Style prefix depuis image de référence (Sora 2 ne supporte pas image_refs) ──
            ref_images = [p for p in self.params.get("ref_images", []) if p and os.path.isfile(p)]
            ref_roles  = self.params.get("ref_image_roles", [])
            if ref_images:
                style_path = next(
                    (p for p, r in zip(ref_images, ref_roles + [""] * 9) if r == "style"),
                    ref_images[0],
                )
                style_kw = _analyze_style_ref(style_path)
                if style_kw:
                    prompt_en = f"{style_kw}, {prompt_en}"

            self.progress.emit(10, "Sora 2 — soumission (~$0.40 / vidéo)…")

            result = fal_client.subscribe(
                "fal-ai/sora-2/text-to-video",
                arguments={
                    "prompt":       prompt_en,
                    "aspect_ratio": ratio,
                },
                with_logs=False,
            )

            if not isinstance(result, dict):
                raise RuntimeError(f"Réponse inattendue : {str(result)[:200]}")

            video    = result.get("video") or {}
            url      = video.get("url", "") if isinstance(video, dict) else ""
            duration = video.get("duration", 4) if isinstance(video, dict) else 4
            if not url:
                url = result.get("url", "")
            if not url:
                raise RuntimeError(f"URL vidéo manquante : {str(result)[:200]}")

            self.progress.emit(80, "Téléchargement de la vidéo…")
            data = requests.get(url, timeout=300).content

            out_dir  = _video_output_dir()
            ts       = int(time.time())
            local    = os.path.join(out_dir, f"sora2_{ts}.mp4")
            with open(local, "wb") as f:
                f.write(data)

            self.progress.emit(100, f"Sora 2 ✓  {duration}s · ~$0.40")
            if not self._cancelled:
                self.finished.emit({
                    "url":          url,
                    "local_path":   local,
                    "duration":     duration,
                    "resolution":   "1080p",
                    "model":        "sora-2",
                    "credits_used": 0.40,
                })

        except Exception as e:
            if not self._cancelled:
                self.failed.emit(humanize_api_error(f"Erreur Sora 2 : {e}"))
