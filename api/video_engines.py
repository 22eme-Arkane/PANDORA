"""
api/video_engines.py — Moteurs vidéo alternatifs à Seedance 2.0.

Modèles fal.ai (relevé fiche par fiche sur fal.ai le 2026-09-24 — `llms.txt`
de chaque endpoint ; les prix sont ceux publiés ce jour-là, à revérifier) :
  - Happy Horse 1.1 T2V/I2V : alibaba/happy-horse/v1.1/{text,image,reference}-to-video — $0.14-0.18/s
    (clé PANDORA « happy-horse-1.0 » CONSERVÉE : elle est enregistrée dans les
     plans et l'historique des projets existants — voir core/pricing)
  - Kling O3 4K T2V/I2V     : fal-ai/kling-video/o3/4k/{text,image}-to-video      — $0.42/s
  - Kling O3 Pro T2V/I2V    : fal-ai/kling-video/o3/pro/{text,image}-to-video     — $0.112 / $0.14 (audio)
  - Kling O3 Standard       : fal-ai/kling-video/o3/standard/{text,image}-to-video — $0.084 / $0.112 (audio)
  - Kling v3 Pro I2V         : fal-ai/kling-video/v3/pro/image-to-video            — $0.112 / $0.168 (audio)
  - Kling v3 Pro T2V         : fal-ai/kling-video/v3/pro/text-to-video             — $0.112 / $0.168 (audio)
  - Kling v3 4K T2V          : fal-ai/kling-video/v3/4k/text-to-video              — $0.28-0.39/s
  - PixVerse v6 T2V/I2V      : fal-ai/pixverse/v6/{text,image}-to-video            — $0.025-0.115/s
  - Veo 3.1 T2V/I2V          : fal-ai/veo3.1[/fast|/lite][/image-to-video]         — $0.20-0.60/s (Pro)
  - Sora 2 T2V/I2V           : fal-ai/sora-2/{text,image}-to-video[/pro]           — $0.10/s (Pro 0.30-0.70)
  - Wan 3.0 T2V/I2V          : alibaba/wan-3.0/{text,image}-to-video               — $0.05-0.20/s
  - LTX-2 / LTX-2.3          : fal-ai/ltx-2[.3]/{text,image}-to-video              — $0.06-0.32/s
  - Gemini Omni Flash 1.1    : google/gemini-omni-flash/v1.1/{text,image}-to-video — $0.03-0.30/s
  - Grok Imagine 1.5         : xai/grok-imagine-video/v1.5/{text,image}-to-video   — $0.08-0.25/s

⚠ Noms de champ qui ont MORDU (2026-09-24) : l'image de départ s'appelle
`image_url` chez Kling O3 (4K, Pro, Standard) et Kling v3 Turbo, mais
`start_image_url` chez Kling v3 Pro et Wan 3.0 ; PixVerse v6 dit
`generate_audio_switch`, pas `generate_audio` ; Veo veut la durée en « 8s » ;
Sora et LTX n'acceptent que quelques durées entières.

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


def engine_prompt(params: dict) -> str:
    """Prompt à envoyer au moteur.

    Si le Studio a produit un prompt FINAL (params["prompt_is_final"]) — déjà
    assemblé, traduit en anglais et dialogues calés sur la langue du plan — il part
    TEL QUEL. Le repasser au traducteur le réécrirait ET renverrait les répliques
    vers l'anglais, alors que l'écran affirme l'inverse (constat 2026-07-25 : les
    9 moteurs non-Seedance ignoraient ce drapeau, contrairement à api/real.py).
    Sinon : chemin historique (traduction vers l'anglais)."""
    raw = (params.get("prompt") or "")
    if params.get("prompt_is_final"):
        return raw
    if not raw:
        return ""
    from core.lang import translate_to_english
    return translate_to_english(raw)


def ensure_image_urls(fal_client, params: dict, emit_progress=None) -> None:
    """Adapte les params du workflow séquences/storyboard aux workers externes.

    Le workflow PANDORA fournit des CHEMINS LOCAUX (image_path = mood keyframe ou
    dernière frame de raccord, end_image_path = mood du plan suivant) ; les moteurs
    externes attendent des URLs. Uploade et bascule en i2v. Modifie params EN PLACE.
    """
    # Formulaires « Génération directe » (onglet Moteurs) : leurs sélecteurs
    # d'image mettent un CHEMIN LOCAL dans image_url / end_image_url (constat
    # 24/09/2026 — Kling, Kling O3, Happy Horse, PixVerse). Il partait tel quel
    # vers fal, qui ne peut pas lire « C:\… » : on l'uploade ici, une fois
    # pour tous les workers.
    for _k in ("image_url", "end_image_url"):
        _v = str(params.get(_k, "") or "")
        if _v and not _v.lower().startswith(("http://", "https://", "data:")) and os.path.isfile(_v):
            if emit_progress:
                emit_progress(6, "Upload de l'image de départ…" if _k == "image_url"
                              else "Upload de l'image de fin…")
            params[_k] = _fal_upload(fal_client, _v)
            if _k == "image_url":
                params["mode"] = "i2v"
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
    """Le moteur de vision sélectionné extrait les mots-clés de style d'une image.
    Retourne une chaîne EN (~12 mots) ou '' en cas d'erreur.

    Les blocs multimodaux passent par ``core.ai_provider`` : le profil ChatGPT
    n'effectue donc aucun appel Anthropic.
    """
    try:
        import base64
        from core.ai_provider import chat, key_error
        if key_error(task="vision"):
            return ""
        ext = os.path.splitext(image_path)[1].lower()
        mime = {".jpg": "image/jpeg", ".jpeg": "image/jpeg",
                ".png": "image/png",  ".webp": "image/webp"}.get(ext, "image/jpeg")
        with open(image_path, "rb") as f:
            b64 = base64.standard_b64encode(f.read()).decode()
        text = chat(
            "", [{"role": "user", "content": [
                {"type": "image", "source": {"type": "base64", "media_type": mime, "data": b64}},
                {"type": "text", "text": (
                    "Describe the visual style of this image in exactly 10-15 English words "
                    "as a video generation prompt prefix. Include: rendering medium, color treatment, "
                    "and film genre style. Output ONLY comma-separated keywords, no explanation."
                )},
            ]}], tier="utility", max_tokens=80, task="vision")
        return text.strip().rstrip(".")
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

    # Tarifs relevés sur fal.ai (fiche v3/pro, 2026-09-24) : 0,112 $/s sans
    # audio, 0,168 $/s avec — la grille core/pricing disait 0,15 « milieu ».
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

            os.environ["FAL_KEY"] = key
            # Workflow séquences : image_path/end_image_path locaux → URLs i2v
            ensure_image_urls(fal_client, self.params, self.progress.emit)

            mode      = self.params.get("mode", "i2v")
            dur       = int(self.params.get("duration", 5))
            with_audio = self.params.get("generate_audio", True)
            variant   = self.params.get("variant", "pro")
            # Palier TURBO (fal 2026-06-17) : même famille v3, rendu plus
            # rapide et moins cher — pro 0,14 $/s, standard 0,112 $/s (relevé
            # 2026-08-09). Il vit ici plutôt que dans un worker séparé : c'est
            # le MÊME contrat d'appel, seul le chemin change.
            _sub = {"turbo-pro": "turbo/pro", "turbo-standard": "turbo/standard"}
            if variant == "4k":
                endpoint = "fal-ai/kling-video/v3/4k/text-to-video"
            elif variant in _sub:
                _kind = "image-to-video" if mode == "i2v" else "text-to-video"
                endpoint = f"fal-ai/kling-video/v3/{_sub[variant]}/{_kind}"
            elif mode == "i2v":
                endpoint = "fal-ai/kling-video/v3/pro/image-to-video"
            else:
                endpoint = "fal-ai/kling-video/v3/pro/text-to-video"

            # Turbo est facturé à un tarif FIXE (pas de variation selon l'audio).
            _TURBO_RATE = {"turbo-pro": 0.14, "turbo-standard": 0.112}
            if variant in _TURBO_RATE:
                price_rate = _TURBO_RATE[variant]
            else:
                price_rate = self._PRICE_WITH_AUDIO if with_audio else self._PRICE_NO_AUDIO
            cost_est = dur * price_rate

            self.progress.emit(10, f"Kling v3 Pro {mode.upper()} — {dur}s (~${cost_est:.2f})…")

            prompt_raw = self.params.get("prompt", "")
            prompt_en  = engine_prompt(self.params)   # prompt FINAL respecté

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

            _turbo = variant in _sub
            args: dict = {
                "prompt":   prompt_en,
                "duration": str(dur),
            }
            if not _turbo:
                # Le schéma TURBO (fiche fal 2026-09-24) ne connaît que
                # prompt / image_url / duration : audio, prompt négatif,
                # cfg et shot_type n'y existent pas.
                args["generate_audio"] = with_audio
                args["shot_type"] = self.params.get("shot_type", "customize")
            if mode == "i2v":
                img_url = self.params.get("image_url", "")
                if not img_url:
                    raise ValueError("Kling I2V : image_url requis.")
                # ⚠ Deux noms pour le même champ chez Kling : `start_image_url`
                # sur v3 Pro, `image_url` sur v3 Turbo (fiches 2026-09-24).
                args["image_url" if _turbo else "start_image_url"] = img_url
                if self.params.get("end_image_url") and not _turbo:
                    args["end_image_url"] = self.params["end_image_url"]
            if self.params.get("negative_prompt") and not _turbo:
                args["negative_prompt"] = self.params["negative_prompt"]
            if self.params.get("cfg_scale") is not None and not _turbo:
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


# ── Worker PixVerse v6 Image-to-Video ────────────────────────────────────────

class PixVerseWorker(_CancellableWorker):
    """
    Génère une vidéo via PixVerse v6 Image-to-Video (fiche fal 2026-09-24).

    Remplace la v4.5 (retirée du catalogue fal). Même contrat d'appel côté
    PANDORA : image_url + prompt ; la v6 ajoute résolution 360p–1080p, durée
    1–15 s, audio optionnel (`generate_audio_switch`) et prompt négatif. Pas
    d'aspect_ratio : le cadre suit l'image.
    """
    progress = pyqtSignal(int, str)
    finished = pyqtSignal(dict)
    failed   = pyqtSignal(str)

    # $/s (sans audio, avec audio) — relevé fal 2026-09-24.
    _PRICE = {"360p": (0.025, 0.035), "540p": (0.035, 0.045),
              "720p": (0.045, 0.060), "1080p": (0.090, 0.115)}

    def __init__(self, params: dict):
        """
        params attendus :
          prompt          (str)  requis
          image_url       (str)  requis (ou image_path local — uploadé)
          duration        (int)  1-15, défaut 5
          resolution      (str)  "360p" | "540p" | "720p" | "1080p", défaut "720p"
          generate_audio  (bool) défaut False
          negative_prompt (str)  optionnel
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
            (15, "PixVerse v6 I2V — mode mock…"),
            (50, "Génération vidéo PixVerse (simulation)…"),
            (90, f"Vidéo {dur}s en cours…"),
            (100, "Terminé — mode mock (aucune clé fal.ai)"),
        ]
        for pct, msg in steps:
            self.progress.emit(pct, msg)
            time.sleep(0.5)
        self.finished.emit({"url": "", "duration": dur, "model": "pixverse-v6-i2v", "credits_used": 0})

    def _real(self, key: str):
        try:
            import fal_client
            import requests

            os.environ["FAL_KEY"] = key
            # Workflow séquences : image_path locale → URL
            ensure_image_urls(fal_client, self.params, self.progress.emit)

            dur   = max(1, min(15, int(self.params.get("duration", 5) or 5)))
            res   = (self.params.get("resolution", "720p") or "720p").split()[0]
            audio = bool(self.params.get("generate_audio", False))
            rate  = self._PRICE.get(res, self._PRICE["720p"])[1 if audio else 0]
            cost  = dur * rate

            self.progress.emit(10, f"PixVerse v6 I2V — {dur}s {res} (~${cost:.2f})…")

            img_url = self.params.get("image_url", "")
            if not img_url:
                raise ValueError("PixVerse : image_url requis.")

            prompt_raw = self.params.get("prompt", "")
            prompt_en  = engine_prompt(self.params)   # prompt FINAL respecté

            self.progress.emit(20, "Appel PixVerse v6 (environ 1 min)…")

            args = {
                "prompt":                prompt_en,
                "image_url":             img_url,
                "resolution":            res,
                "duration":              dur,
                "generate_audio_switch": audio,
            }
            if self.params.get("negative_prompt"):
                args["negative_prompt"] = self.params["negative_prompt"]
            result = fal_client.subscribe("fal-ai/pixverse/v6/image-to-video", arguments=args)

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
            local    = os.path.join(out_dir, f"pixverse_v6_i2v_{dur}s_{ts}.mp4")
            with open(local, "wb") as f:
                f.write(data)

            self.progress.emit(100, f"PixVerse v6 ✓  {dur}s {res} · ~${cost:.2f}")
            if not self._cancelled:
                self.finished.emit({
                    "url":          url,
                    "local_path":   local,
                    "duration":     dur,
                    "resolution":   res,
                    "model":        "pixverse-v6-i2v",
                    "credits_used": cost,
                })

        except Exception as e:
            if not self._cancelled:
                self.failed.emit(humanize_api_error(f"Erreur PixVerse : {e}"))


# ── Worker Veo 3.1 ────────────────────────────────────────────────────────────

class Veo3Worker(_CancellableWorker):
    """
    Génère une vidéo via Veo 3.1 (Google / fal-ai) — trois paliers, T2V et I2V.

    Relevé fal 2026-09-24 : facturé À LA SECONDE (et non « ~1 $ la vidéo »),
    selon résolution ET audio. L'ancien appel n'envoyait que le prompt : fal
    prenait 720p / 8 s / audio, soit 3,20 $ le clip pour un journal à 1 $.

      variant "pro"  : fal-ai/veo3.1[/image-to-video]        720p-1080p 0.20/0.40 · 4k 0.40/0.60
      variant "fast" : fal-ai/veo3.1/fast[/image-to-video]   720p-1080p 0.10/0.15 · 4k 0.30/0.35
      variant "lite" : fal-ai/veo3.1/lite[/image-to-video]   720p 0.03/0.05 · 1080p 0.05/0.08

    Durée « 4s » / « 6s » / « 8s » (chaîne), ratio 16:9 ou 9:16 seulement
    (« auto » en I2V), `generate_audio` vrai par défaut.
    """
    progress = pyqtSignal(int, str)
    finished = pyqtSignal(dict)
    failed   = pyqtSignal(str)

    # (sans audio, avec audio) par résolution et par palier.
    _PRICE = {
        "pro":  {"720p": (0.20, 0.40), "1080p": (0.20, 0.40), "4k": (0.40, 0.60)},
        "fast": {"720p": (0.10, 0.15), "1080p": (0.10, 0.15), "4k": (0.30, 0.35)},
        "lite": {"720p": (0.03, 0.05), "1080p": (0.05, 0.08)},
    }
    _ENDPOINT = {"pro": "fal-ai/veo3.1", "fast": "fal-ai/veo3.1/fast", "lite": "fal-ai/veo3.1/lite"}
    _MODEL    = {"pro": "veo-3.1", "fast": "veo-3.1-fast", "lite": "veo-3.1-lite"}
    _DURATIONS = (4, 6, 8)

    def __init__(self, params: dict):
        """
        params attendus :
          prompt         (str)  requis
          variant        (str)  "pro" | "fast" | "lite", défaut "pro"
          mode           (str)  "t2v" | "i2v" (image_url / image_path)
          duration       (int)  4 | 6 | 8 (arrondi au plus proche), défaut 8
          resolution     (str)  "720p" | "1080p" | "4k" (lite : pas de 4k)
          aspect_ratio   (str)  "16:9" | "9:16" (autre → 16:9)
          generate_audio (bool) défaut True
          negative_prompt (str) optionnel
        """
        super().__init__()
        self.params = params

    @classmethod
    def snap_duration(cls, seconds) -> int:
        try:
            v = float(seconds)
        except (TypeError, ValueError):
            return 8
        return min(cls._DURATIONS, key=lambda d: abs(d - v))

    @classmethod
    def price_per_second(cls, variant: str, resolution: str, audio: bool = True) -> float:
        table = cls._PRICE.get(variant or "pro", cls._PRICE["pro"])
        res = (resolution or "720p").lower().split()[0]
        if res not in table:
            res = "720p"
        return table[res][1 if audio else 0]

    def _variant(self) -> str:
        v = (self.params.get("variant") or "pro").lower()
        return v if v in self._ENDPOINT else "pro"

    def run(self):
        cfg = load_config()
        key = cfg.get("api_key", "").strip()
        if not key:
            self._mock()
        else:
            self._real(key)

    def _mock(self):
        dur = self.snap_duration(self.params.get("duration", 8))
        for pct, msg in [
            (10, f"Veo 3.1 ({self._variant()}) — mode mock…"),
            (50, "Génération vidéo Google (simulation)…"),
            (100, "Terminé — mode mock (aucune clé fal.ai)"),
        ]:
            self.progress.emit(pct, msg)
            time.sleep(0.5)
        self.finished.emit({
            "url": "", "duration": dur, "model": self._MODEL[self._variant()],
            "resolution": self.params.get("resolution", "720p"), "credits_used": 0,
        })

    def _real(self, key: str):
        try:
            import fal_client
            import requests

            os.environ["FAL_KEY"] = key
            # Workflow séquences : image_path locale → URL, mode i2v
            ensure_image_urls(fal_client, self.params, self.progress.emit)

            variant = self._variant()
            mode    = "i2v" if (self.params.get("mode") == "i2v" or self.params.get("image_url")) else "t2v"
            dur     = self.snap_duration(self.params.get("duration", 8))
            res     = (self.params.get("resolution", "720p") or "720p").lower().split()[0]
            if res not in self._PRICE[variant]:
                res = "720p"
            audio   = bool(self.params.get("generate_audio", True))
            rate    = self.price_per_second(variant, res, audio)
            cost    = dur * rate
            ratio   = self.params.get("aspect_ratio", "16:9")
            if ratio not in ("16:9", "9:16"):
                ratio = "16:9"

            prompt_raw = self.params.get("prompt", "")
            prompt_en  = engine_prompt(self.params)   # prompt FINAL respecté

            # ── Style prefix depuis image de référence (Veo ne prend pas d'image_refs) ──
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

            endpoint = self._ENDPOINT[variant] + ("/image-to-video" if mode == "i2v" else "")
            args: dict = {
                "prompt":         prompt_en,
                "aspect_ratio":   ratio,
                "duration":       f"{dur}s",
                "resolution":     res,
                "generate_audio": audio,
            }
            if mode == "i2v":
                args["image_url"] = self.params["image_url"]
            if self.params.get("negative_prompt"):
                args["negative_prompt"] = self.params["negative_prompt"]

            self.progress.emit(10, f"Veo 3.1 {variant} {mode.upper()} — {dur}s {res} (~${cost:.2f}, 2-3 min)…")

            result = fal_client.subscribe(endpoint, arguments=args, with_logs=False)

            if not isinstance(result, dict):
                raise RuntimeError(f"Réponse inattendue : {str(result)[:200]}")

            url = _extract_video_url(result)
            if not url:
                raise RuntimeError(f"URL vidéo manquante : {str(result)[:200]}")

            self.progress.emit(80, "Téléchargement de la vidéo…")
            data = requests.get(url, timeout=300).content

            out_dir  = _video_output_dir()
            ts       = int(time.time())
            local    = os.path.join(out_dir, f"veo31_{variant}_{mode}_{dur}s_{ts}.mp4")
            with open(local, "wb") as f:
                f.write(data)

            self.progress.emit(100, f"Veo 3.1 ✓  {dur}s · {res} · ~${cost:.2f}")
            if not self._cancelled:
                self.finished.emit({
                    "url":          url,
                    "local_path":   local,
                    "duration":     dur,
                    "resolution":   res,
                    "model":        f"{self._MODEL[variant]}-{mode}",
                    "credits_used": cost,
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

    # Tarifs Happy Horse 1.1 relevés sur fal.ai le 2026-08-09. Le 1080p passe de
    # $0.28 (1.0) à $0.18 : la montée de version le rend 36 % MOINS cher.
    _PRICE = {"720p": 0.14, "1080p": 0.18}

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

            os.environ["FAL_KEY"] = key
            # Workflow séquences : image_path/end_image_path locaux → URLs i2v
            ensure_image_urls(fal_client, self.params, self.progress.emit)

            mode     = self.params.get("mode", "t2v")
            dur      = int(self.params.get("duration", 5))
            res      = self.params.get("resolution", "720p")
            ratio    = self.params.get("aspect_ratio", "16:9")
            cost_est = dur * self._PRICE.get(res, 0.14)

            # Happy Horse 1.1 (fal, 2026-06-22) : chemins VERSIONNÉS. L'ancien
            # `alibaba/happy-horse/...` sans version pointait la 1.0.
            _ep_map = {
                "t2v": "alibaba/happy-horse/v1.1/text-to-video",
                "i2v": "alibaba/happy-horse/v1.1/image-to-video",
                "ref": "alibaba/happy-horse/v1.1/reference-to-video",
            }
            endpoint = _ep_map.get(mode, _ep_map["t2v"])

            self.progress.emit(5, f"Happy Horse 1.1 {mode.upper()} — {dur}s {res} (~${cost_est:.2f})…")

            prompt_raw = self.params.get("prompt", "")
            prompt_en  = engine_prompt(self.params)   # prompt FINAL respecté

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


# ── Worker Flux 3 (Black Forest Labs) ────────────────────────────────────────

class Flux3Worker(_CancellableWorker):
    """
    Génère une vidéo via Flux 3 (Black Forest Labs / fal.ai).
    Modes T2V, I2V et first-last-frame. Audio natif. 720p/1080p, 5–20 s.
    Pleine qualité ~$0.17-0.29/s · brouillon (draft) $0.06/s en 720p.

    ⚠ Particularités encodées depuis core/flux3_family (relevé 2026-08-09) :
      · PAS de reference-to-video : les images de cohérence casting/décor ne
        peuvent pas être envoyées — on le DIT au lieu de les perdre en silence ;
      · safety_tolerance sur une échelle 0–4 (Seedance : 1–6) → toujours clampé ;
      · en brouillon, la sortie inclut un draft_cache à CONSERVER : c'est lui
        (et lui seul) que draft-enhance sait affiner.
    """
    progress = pyqtSignal(int, str)
    finished = pyqtSignal(dict)
    failed   = pyqtSignal(str)

    def __init__(self, params: dict):
        """
        params attendus :
          prompt        (str)  requis
          mode          (str)  "t2v" | "i2v" | "flf"
          image_url     (str)  requis si i2v / flf (début)
          end_image_url (str)  requis si flf (fin)
          duration      (int)  5-20, défaut 5 (clampé par le moteur)
          resolution    (str)  "720p" | "1080p"
          aspect_ratio  (str)  cf. flux3_family.ASPECTS
          draft         (bool) palier brouillon 720p à $0.06/s
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
            (10, f"Flux 3 {mode} — mode mock…"),
            (50, "Génération vidéo (simulation)…"),
            (100, "Terminé — mode mock (aucune clé fal.ai)"),
        ]:
            self.progress.emit(pct, msg)
            time.sleep(0.4)
        self.finished.emit({"url": "", "duration": dur, "model": "flux-3",
                            "credits_used": 0})

    def _real(self, key: str):
        try:
            import fal_client
            import requests
            from core import flux3_family as f3

            os.environ["FAL_KEY"] = key
            ensure_image_urls(fal_client, self.params, self.progress.emit)

            mode  = self.params.get("mode", "t2v")
            draft = bool(self.params.get("draft", False))
            dur   = f3.clamp_duration(self.params.get("duration", 5))
            res   = "720p" if draft else f3.clamp_resolution(
                self.params.get("resolution", "720p"))
            ratio = self.params.get("aspect_ratio", "16:9")
            if ratio not in f3.ASPECTS:
                ratio = "16:9"
            rate     = f3.price_per_second(mode, res, draft)
            cost_est = int(dur) * rate

            endpoint = f3.endpoint(mode, draft=draft)
            _tier = "draft" if draft else res
            self.progress.emit(
                5, f"Flux 3 {mode.upper()} ({_tier}) — {dur}s (~${cost_est:.2f})…")

            prompt_en = engine_prompt(self.params)   # prompt FINAL respecté

            # Flux 3 n'a AUCUN mécanisme d'images de référence : prévenir vaut
            # mieux que perdre en silence (les fiches ne partiront pas).
            _refs = [p for p in self.params.get("ref_images", [])
                     if p and os.path.isfile(p)]
            if _refs:
                self.progress.emit(
                    6, f"⚠ {len(_refs)} image(s) de référence ignorée(s) — "
                       "Flux 3 n'accepte pas de références visuelles.")

            args: dict = {
                "prompt":         prompt_en,
                "duration":       str(dur),          # schéma fal : enum "5".."20"
                "aspect_ratio":   ratio,
                "generate_audio": bool(self.params.get("audio", True)),
                # Échelle PROPRE à Flux 3 (0-4) — un « 6 » recopié de Seedance
                # ferait refuser l'appel.
                "safety_tolerance": f3.clamp_safety(
                    self.params.get("safety_tolerance_override", 4)),
            }
            if not draft:
                args["resolution"] = res

            if mode in ("i2v", "flf"):
                img_url = self.params.get("image_url", "")
                if not img_url:
                    raise ValueError("Flux 3 I2V : image_url requis.")
                key_img = "start_image_url" if mode == "flf" else "image_url"
                args[key_img] = img_url
            if mode == "flf":
                end_url = self.params.get("end_image_url", "")
                if not end_url:
                    raise ValueError("Flux 3 first-last : end_image_url requis.")
                args["end_image_url"] = end_url

            # Suffixes hérités du tab T2V (même pipeline que les autres moteurs)
            for key_suf, sep in [("style_suffix", ", "), ("no_music_suffix", ", "),
                                 ("creative_suffix", ", ")]:
                v = self.params.get(key_suf, "")
                if v and args.get("prompt"):
                    args["prompt"] = args["prompt"] + sep + v

            self.progress.emit(20, "Appel Flux 3 (peut prendre 1-3 min)…")
            result = fal_client.subscribe(endpoint, arguments=args)
            if not isinstance(result, dict):
                raise RuntimeError(f"Réponse inattendue : {str(result)[:200]}")

            video = result.get("video") or {}
            url   = video.get("url", "") if isinstance(video, dict) else ""
            if not url:
                url = result.get("url", "")
            if not url:
                raise RuntimeError(f"URL vidéo manquante : {str(result)[:200]}")

            # Brouillon : le jeton d'affinage est la SEULE voie vers la pleine
            # qualité (draft-enhance ne prend pas d'URL vidéo) — on le conserve.
            _cache = result.get("draft_cache") or {}
            draft_cache_url = (_cache.get("url", "") if isinstance(_cache, dict)
                               else "") or result.get("draft_cache_url", "")

            self.progress.emit(80, "Téléchargement de la vidéo…")
            data = requests.get(url, timeout=300).content
            out_dir = _video_output_dir()
            ts      = int(time.time())
            _suffix = "draft_" if draft else ""
            local   = os.path.join(out_dir, f"flux3_{_suffix}{mode}_{dur}s_{ts}.mp4")
            with open(local, "wb") as f:
                f.write(data)

            self.progress.emit(100, f"Flux 3 ✓  {dur}s {_tier} · ~${cost_est:.2f}")
            if not self._cancelled:
                out = {
                    "url":          url,
                    "local_path":   local,
                    "duration":     int(dur),
                    "resolution":   res,
                    "model":        "flux-3-draft" if draft else "flux-3",
                    "credits_used": cost_est,
                }
                if draft_cache_url:
                    out["draft_cache_url"] = draft_cache_url
                self.finished.emit(out)

        except Exception as e:
            if not self._cancelled:
                self.failed.emit(humanize_api_error(f"Erreur Flux 3 : {e}"))


# ── Worker Flux 3 — AFFINAGE d'un brouillon ──────────────────────────────────

class Flux3EnhanceWorker(_CancellableWorker):
    """Rend en pleine qualité 1080p un brouillon Flux 3 déjà généré.

    C'est la seconde moitié du palier brouillon : on sort tout le film à
    0,06 $/s, on regarde, et on ne paie le prix fort QUE sur les plans gardés.

    ⚠ L'affinage ne prend PAS une URL de vidéo : il consomme le
    `draft_cache_url` (paquet chiffré) renvoyé par le brouillon. Sans ce jeton,
    il faut tout regénérer — d'où le message explicite plutôt qu'un échec API
    obscur. Il ne prend pas non plus de prompt : le cache porte le seed et le
    mouvement, l'affinage rejoue le MÊME plan en meilleure qualité (corriger le
    texte impose de refaire un brouillon).
    """
    progress = pyqtSignal(int, str)
    finished = pyqtSignal(dict)
    failed   = pyqtSignal(str)

    def __init__(self, params: dict):
        """params : draft_cache_url (requis) · duration (info coût) ·
        safety_tolerance_override (0-4)."""
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
        for pct, msg in [(10, "Flux 3 — affinage (mock)…"),
                         (60, "Rendu pleine qualité (simulation)…"),
                         (100, "Terminé — mode mock (aucune clé fal.ai)")]:
            self.progress.emit(pct, msg)
            time.sleep(0.4)
        self.finished.emit({"url": "", "duration": dur, "model": "flux-3-enhance",
                            "credits_used": 0})

    def _real(self, key: str):
        try:
            import fal_client
            import requests
            from core import flux3_family as f3

            cache_url = (self.params.get("draft_cache_url") or "").strip()
            if not cache_url:
                raise ValueError(
                    "Affinage impossible : ce clip n'a pas de jeton de brouillon "
                    "(draft_cache). Seul un clip produit en mode BROUILLON peut "
                    "être affiné — sinon, relancez une génération.")

            os.environ["FAL_KEY"] = key
            dur      = int(self.params.get("duration", 5) or 5)
            cost_est = dur * f3.enhance_price_per_second()

            self.progress.emit(
                5, f"Flux 3 — affinage 1080p, {dur}s (~${cost_est:.2f})…")

            args = {
                "draft_cache_url": cache_url,
                "safety_tolerance": f3.clamp_safety(
                    self.params.get("safety_tolerance_override", 4)),
            }
            self.progress.emit(20, "Appel Flux 3 draft-enhance (1-3 min)…")
            result = fal_client.subscribe(f3.ENHANCE_ENDPOINT, arguments=args)
            if not isinstance(result, dict):
                raise RuntimeError(f"Réponse inattendue : {str(result)[:200]}")

            video = result.get("video") or {}
            url   = video.get("url", "") if isinstance(video, dict) else ""
            if not url:
                url = result.get("url", "")
            if not url:
                raise RuntimeError(f"URL vidéo manquante : {str(result)[:200]}")

            self.progress.emit(80, "Téléchargement de la vidéo affinée…")
            data  = requests.get(url, timeout=300).content
            ts    = int(time.time())
            local = os.path.join(_video_output_dir(), f"flux3_enhanced_{dur}s_{ts}.mp4")
            with open(local, "wb") as f:
                f.write(data)

            self.progress.emit(100, f"Flux 3 affiné ✓  {dur}s 1080p · ~${cost_est:.2f}")
            if not self._cancelled:
                self.finished.emit({
                    "url":          url,
                    "local_path":   local,
                    "duration":     dur,
                    "resolution":   "1080p",
                    "model":        "flux-3-enhance",
                    "credits_used": cost_est,
                })
        except Exception as e:
            if not self._cancelled:
                self.failed.emit(humanize_api_error(f"Erreur Flux 3 (affinage) : {e}"))


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
            prompt_en  = engine_prompt(self.params)   # prompt FINAL respecté

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
                # ⚠ Fiche fal 2026-09-24 : le champ s'appelle `image_url` (pas
                # `start_image_url` comme sur Kling v3 Pro) — l'ancien nom aurait
                # valu un rejet « image_url required » à CHAQUE envoi i2v.
                args["image_url"] = img_url
                if self.params.get("end_image_url"):
                    args["end_image_url"] = self.params["end_image_url"]

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

    # $/s (sans audio, avec audio) — fiche fal 2026-09-24. L'ancienne grille
    # (0,075 en 720p) était celle d'un relevé antérieur, faux aux deux tiers.
    _PRICE_TABLE = {"360p": (0.025, 0.035), "540p": (0.035, 0.045),
                    "720p": (0.045, 0.060), "1080p": (0.090, 0.115)}
    # Vue « avec audio » (le pire cas) pour ce qui lit encore _PRICE.
    _PRICE = {k: v[1] for k, v in _PRICE_TABLE.items()}

    def __init__(self, params: dict):
        """
        params attendus :
          prompt          (str)  requis
          resolution      (str)  "360p" | "540p" | "720p" | "1080p", défaut "720p"
          duration        (int)  1-15, défaut 5
          generate_audio  (bool) défaut False  → envoyé comme `generate_audio_switch`
          aspect_ratio    (str)  16:9 · 4:3 · 1:1 · 3:4 · 9:16 · 2:3 · 3:2 · 21:9
          negative_prompt (str)  optionnel
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

            os.environ["FAL_KEY"] = key
            # Workflow séquences : image_path/end_image_path locaux → URLs i2v
            ensure_image_urls(fal_client, self.params, self.progress.emit)

            dur      = max(1, min(15, int(self.params.get("duration", 5) or 5)))
            res      = (self.params.get("resolution", "720p") or "720p").split()[0]
            ratio    = self.params.get("aspect_ratio", "16:9")
            audio    = bool(self.params.get("generate_audio", False))
            cost_est = dur * self._PRICE_TABLE.get(res, self._PRICE_TABLE["720p"])[1 if audio else 0]

            self.progress.emit(10, f"PixVerse v6 — {dur}s {res} (~${cost_est:.2f})…")

            prompt_raw = self.params.get("prompt", "")
            prompt_en  = engine_prompt(self.params)   # prompt FINAL respecté

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

            # ⚠ Le champ audio s'appelle `generate_audio_switch` chez PixVerse
            # (fiches T2V, I2V et reference-to-video, 2026-09-24) : sous
            # `generate_audio` il était simplement ignoré — audio jamais produit.
            args: dict = {
                "prompt":                prompt_en,
                "resolution":            res,
                "duration":              dur,
                "aspect_ratio":          ratio,
                "generate_audio_switch": audio,
            }
            if self.params.get("negative_prompt"):
                args["negative_prompt"] = self.params["negative_prompt"]
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
    PRICE_BY_RES    = {}      # {résolution: $/s} quand le tarif dépend de la résolution
    FLAT_PRICE      = 0.0     # $/vidéo (modèles à prix fixe, ex. Hailuo)
    AUDIO           = False   # envoie generate_audio
    AUDIO_FIELD     = "generate_audio"   # nom du champ audio (Wan 3.0 : « audio »)
    AUDIO_DEFAULT   = True    # valeur si l'appelant ne dit rien
    AUDIO_PRICE_OFF = {}      # {résolution: $/s} SANS audio, si le tarif en dépend
    END_FRAME       = False   # supporte end_image_url (raccords / keyframes)
    IMAGE_FIELD     = "image_url"   # nom du champ image de départ (Wan 3.0 : start_image_url)
    SEND_RESOLUTION = False
    RESOLUTIONS     = ()      # valeurs acceptées ; hors liste → la première (rien = tout passe)
    SEND_RATIO      = False
    RATIOS          = ()      # ratios acceptés ; hors liste → 16:9 (rien = tout passe)
    RATIO_T2V_ONLY  = False   # aspect_ratio absent du schéma I2V → ne pas l'envoyer
    SEND_DURATION   = False
    DURATIONS       = ()      # durées acceptées (Sora 4/8/12…, LTX 6/8/10) ; rien = libre
    DUR_MIN, DUR_MAX = 0, 0   # bornes si DURATIONS est vide (0 = pas de borne)
    DUR_STR         = True    # duration en str (famille ByteDance) sinon int
    DEFAULT_DUR     = 5

    def __init__(self, params: dict):
        super().__init__()
        self.params = params

    # ── Hooks (identité par défaut ; les familles à table les surchargent) ──

    def _resolution_arg(self, res: str) -> str:
        """Valeur de `resolution` envoyée à fal pour une résolution PANDORA."""
        if self.RESOLUTIONS and res not in self.RESOLUTIONS:
            return self.RESOLUTIONS[0]
        return res

    def _extra_args(self, mode: str) -> dict:
        """Champs supplémentaires propres au moteur."""
        return {}

    def _price_per_s(self, res: str) -> float:
        """$/s pour cette résolution (les tables de famille varient par palier)."""
        if self.PRICE_BY_RES:
            r = self._resolution_arg(res)
            audio_on = self.params.get("generate_audio", self.AUDIO_DEFAULT) if self.AUDIO else True
            if not audio_on and self.AUDIO_PRICE_OFF:
                return self.AUDIO_PRICE_OFF.get(r, next(iter(self.AUDIO_PRICE_OFF.values())))
            return self.PRICE_BY_RES.get(r, next(iter(self.PRICE_BY_RES.values())))
        return self.PRICE_PER_S

    def _snap_duration(self, dur: int) -> int:
        """Durée ramenée à ce que l'endpoint accepte (liste fermée ou bornes)."""
        if self.DURATIONS:
            return min(self.DURATIONS, key=lambda d: abs(d - dur))
        if self.DUR_MIN:
            dur = max(self.DUR_MIN, dur)
        if self.DUR_MAX:
            dur = min(self.DUR_MAX, dur)
        return dur

    def _ratio_arg(self, ratio: str) -> str:
        if self.RATIOS and ratio not in self.RATIOS:
            return "16:9" if "16:9" in self.RATIOS else self.RATIOS[0]
        return ratio

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

            os.environ["FAL_KEY"] = key
            # Workflow / formulaire I2V : image_path/end_image_path locaux → URLs.
            ensure_image_urls(fal_client, self.params, self.progress.emit)

            mode = self.params.get("mode", "t2v")
            if mode == "i2v" and not self.ENDPOINT_I2V:
                mode = "t2v"
            endpoint = self.ENDPOINT_I2V if (mode == "i2v" and self.ENDPOINT_I2V) else self.ENDPOINT_T2V

            try:
                dur = int(round(float(self.params.get("duration", self.DEFAULT_DUR) or self.DEFAULT_DUR)))
            except (TypeError, ValueError):
                dur = self.DEFAULT_DUR
            dur = self._snap_duration(dur)

            prompt_raw = self.params.get("prompt", "")
            prompt_en  = engine_prompt(self.params)   # prompt FINAL respecté
            style_kw   = _style_prefix_from_refs(self.params)
            if style_kw:
                prompt_en = f"{style_kw}, {prompt_en}" if prompt_en else style_kw

            args: dict = {"prompt": prompt_en}
            res = (self.params.get("resolution", "720p") or "720p").split()[0]
            if self.SEND_RESOLUTION:
                # Hook : un moteur peut renommer la résolution (« 768p » PANDORA
                # → « 768P » fal chez MiniMax) ou la borner à sa liste.
                args["resolution"] = self._resolution_arg(res)
            # Certains schémas I2V n'ont PAS aspect_ratio (le cadre suit
            # l'image) et rejettent le champ : RATIO_T2V_ONLY le retient.
            if self.SEND_RATIO and not (mode == "i2v" and self.RATIO_T2V_ONLY):
                args["aspect_ratio"] = self._ratio_arg(self.params.get("aspect_ratio", "16:9"))
            if self.SEND_DURATION:
                args["duration"] = str(dur) if self.DUR_STR else dur
            if self.AUDIO:
                args[self.AUDIO_FIELD] = bool(self.params.get("generate_audio", self.AUDIO_DEFAULT))
            if mode == "i2v":
                img_url = self.params.get("image_url", "")
                if not img_url:
                    raise ValueError(f"{self.MODEL} I2V : image de départ requise.")
                args[self.IMAGE_FIELD] = img_url
                if self.END_FRAME and self.params.get("end_image_url"):
                    args["end_image_url"] = self.params["end_image_url"]
            # Champs propres au moteur (ex. prompt_expansion_mode, REQUIS chez
            # H3 Max : l'omettre est un rejet 422 — leçon du Doublage).
            args.update(self._extra_args(mode) or {})

            _pps = self._price_per_s(res)
            cost = dur * _pps if _pps else self.FLAT_PRICE
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
    """LTX-2 (Lightricks) — 1080p/1440p/2160p + audio. T2V + I2V.

    Fiche fal 2026-09-24 : durée 6 / 8 / 10 s (entier), PAS d'aspect_ratio,
    `generate_audio` vrai par défaut. 0,06 $/s en 1080p, 0,12 en 1440p, 0,24
    en 2160p — l'ancien 0,04 « 4K » et la durée « 5 » en chaîne étaient faux."""
    ENDPOINT_T2V    = "fal-ai/ltx-2/text-to-video"
    ENDPOINT_I2V    = "fal-ai/ltx-2/image-to-video"
    MODEL           = "ltx-2"
    PRICE_PER_S     = 0.06
    PRICE_BY_RES    = {"1080p": 0.06, "1440p": 0.12, "2160p": 0.24}
    AUDIO           = True
    SEND_RESOLUTION = True
    RESOLUTIONS     = ("1080p", "1440p", "2160p")
    SEND_DURATION   = True
    DURATIONS       = (6, 8, 10)
    DUR_STR         = False
    DEFAULT_DUR     = 6

    def _resolution_arg(self, res: str) -> str:
        # Les menus PANDORA disent « 4K » : c'est le 2160p de LTX.
        r = (res or "").lower()
        if r in ("4k", "2160p"):
            return "2160p"
        if r in ("2k", "1440p"):
            return "1440p"
        return "1080p"


class LTX23Worker(LTX2Worker):
    """LTX-2.3 Pro (Lightricks, fal 2026-09-24) — même contrat que LTX-2, plus
    l'image de fin en I2V et un ratio 16:9 / 9:16 en T2V. 0,08 / 0,16 / 0,32 $/s."""
    ENDPOINT_T2V    = "fal-ai/ltx-2.3/text-to-video"
    ENDPOINT_I2V    = "fal-ai/ltx-2.3/image-to-video"
    MODEL           = "ltx-2.3"
    PRICE_PER_S     = 0.08
    PRICE_BY_RES    = {"1080p": 0.08, "1440p": 0.16, "2160p": 0.32}
    END_FRAME       = True
    SEND_RATIO      = True
    RATIOS          = ("16:9", "9:16")
    RATIO_T2V_ONLY  = True    # en I2V le schéma dit « auto » : on laisse faire


class Wan27Worker(_SimpleFalVideoWorker):
    """Wan 2.7 (Alibaba) — T2V. Fiche fal 2026-09-24 : 720p 0,10 $/s, 1080p
    0,15 $/s (défaut fal = 1080p : on ENVOIE la résolution choisie), durée
    2–15 s entière, prompt négatif."""
    ENDPOINT_T2V    = "fal-ai/wan/v2.7/text-to-video"
    MODEL           = "wan-2.7"
    PRICE_PER_S     = 0.10
    PRICE_BY_RES    = {"720p": 0.10, "1080p": 0.15}
    SEND_RESOLUTION = True
    RESOLUTIONS     = ("720p", "1080p")
    SEND_RATIO      = True
    RATIOS          = ("16:9", "9:16", "1:1", "4:3", "3:4")
    SEND_DURATION   = True
    DUR_MIN, DUR_MAX = 2, 15
    DUR_STR         = False
    DEFAULT_DUR     = 5

    def _extra_args(self, mode: str) -> dict:
        neg = (self.params.get("negative_prompt") or "").strip()
        return {"negative_prompt": neg[:500]} if neg else {}


class Wan30Worker(_SimpleFalVideoWorker):
    """Wan 3.0 (Alibaba, fal 2026-09-24) — T2V + I2V (première/dernière image),
    2 à 30 s d'un bloc, audio natif (`audio`), 480p/720p/1080p à 0,05 / 0,10 /
    0,20 $/s. ⚠ image de départ = `start_image_url`."""
    ENDPOINT_T2V    = "alibaba/wan-3.0/text-to-video"
    ENDPOINT_I2V    = "alibaba/wan-3.0/image-to-video"
    MODEL           = "wan-3.0"
    PRICE_PER_S     = 0.10
    PRICE_BY_RES    = {"480p": 0.05, "720p": 0.10, "1080p": 0.20}
    AUDIO           = True
    AUDIO_FIELD     = "audio"
    END_FRAME       = True
    IMAGE_FIELD     = "start_image_url"
    SEND_RESOLUTION = True
    RESOLUTIONS     = ("720p", "480p", "1080p")
    SEND_RATIO      = True
    RATIOS          = ("16:9", "4:3", "1:1", "3:4", "9:16", "adaptive")
    SEND_DURATION   = True
    DUR_MIN, DUR_MAX = 2, 30
    DUR_STR         = False
    DEFAULT_DUR     = 5


class Hailuo23Worker(_SimpleFalVideoWorker):
    """MiniMax Hailuo 2.3 Pro — audio natif, prix fixe ~$0.49/vidéo. T2V."""
    ENDPOINT_T2V = "fal-ai/minimax/hailuo-2.3/pro/text-to-video"
    MODEL        = "hailuo-2.3-pro"
    FLAT_PRICE   = 0.49
    DEFAULT_DUR  = 6


class GeminiOmniFlashWorker(_SimpleFalVideoWorker):
    """Gemini Omni Flash (Google) — audio natif, physique améliorée. T2V + I2V.
    Params : prompt, aspect_ratio, duration. ~$0.125/s @720p."""
    ENDPOINT_T2V  = "google/gemini-omni-flash"
    ENDPOINT_I2V  = "google/gemini-omni-flash/image-to-video"
    MODEL         = "gemini-omni-flash"
    PRICE_PER_S   = 0.125
    AUDIO         = True
    SEND_RATIO    = True
    SEND_DURATION = True
    DUR_STR       = False
    DEFAULT_DUR   = 5


class GeminiOmniFlash11Worker(_SimpleFalVideoWorker):
    """Gemini Omni Flash 1.1 (Google, fal 2026-09-24) — T2V + I2V avec image de
    fin, 3–10 s, 360p/720p/1080p/4k à 0,03 / 0,10 / 0,15 / 0,30 $/s. Pas de
    champ audio (le son est natif), ratio 16:9 ou 9:16."""
    ENDPOINT_T2V    = "google/gemini-omni-flash/v1.1/text-to-video"
    ENDPOINT_I2V    = "google/gemini-omni-flash/v1.1/image-to-video"
    MODEL           = "gemini-omni-flash-1.1"
    PRICE_PER_S     = 0.10
    PRICE_BY_RES    = {"720p": 0.10, "360p": 0.03, "1080p": 0.15, "4k": 0.30}
    END_FRAME       = True
    SEND_RESOLUTION = True
    RESOLUTIONS     = ("720p", "360p", "1080p", "4k")
    SEND_RATIO      = True
    RATIOS          = ("16:9", "9:16")
    SEND_DURATION   = True
    DUR_MIN, DUR_MAX = 3, 10
    DUR_STR         = False
    DEFAULT_DUR     = 8


class Seedance20MiniWorker(_SimpleFalVideoWorker):
    """Seedance 2.0 Mini (ByteDance) — i2v + end_image_url (raccords/keyframes de
    moods) + audio natif. T2V + I2V. ⚠ préfixe `bytedance/...`. 480p/720p, ~$0.155/s @720p."""
    ENDPOINT_T2V    = "bytedance/seedance-2.0/mini/text-to-video"
    ENDPOINT_I2V    = "bytedance/seedance-2.0/mini/image-to-video"
    MODEL           = "seedance-2.0-mini"
    PRICE_PER_S     = 0.155
    AUDIO           = True
    END_FRAME       = True
    SEND_RESOLUTION = True
    SEND_DURATION   = True
    DUR_STR         = True
    DEFAULT_DUR     = 5


class GrokVideoWorker(_SimpleFalVideoWorker):
    """Grok Imagine Video (xAI) — audio, résolutions 480p/720p. T2V + I2V.
    Params : prompt, image_url, duration, resolution. $0.05/s 480p, $0.07/s 720p."""
    ENDPOINT_T2V    = "xai/grok-imagine-video/text-to-video"
    ENDPOINT_I2V    = "xai/grok-imagine-video/image-to-video"
    MODEL           = "grok-video"
    PRICE_PER_S     = 0.07
    AUDIO           = True
    SEND_RESOLUTION = True
    SEND_DURATION   = True
    DUR_STR         = False
    DEFAULT_DUR     = 5


class GrokVideo15Worker(_SimpleFalVideoWorker):
    """Grok Imagine Video 1.5 (xAI, fal 2026-09-24) — T2V + I2V, 1–15 s,
    480p/720p/1080p à 0,08 / 0,14 / 0,25 $/s. Ratio en T2V seulement (l'I2V
    suit l'image) ; pas de champ audio (le son est compris)."""
    ENDPOINT_T2V    = "xai/grok-imagine-video/v1.5/text-to-video"
    ENDPOINT_I2V    = "xai/grok-imagine-video/v1.5/image-to-video"
    MODEL           = "grok-video-1.5"
    PRICE_PER_S     = 0.14
    PRICE_BY_RES    = {"720p": 0.14, "480p": 0.08, "1080p": 0.25}
    SEND_RESOLUTION = True
    RESOLUTIONS     = ("720p", "480p", "1080p")
    SEND_RATIO      = True
    RATIOS          = ("16:9", "4:3", "3:2", "1:1", "2:3", "3:4", "9:16")
    RATIO_T2V_ONLY  = True
    SEND_DURATION   = True
    DUR_MIN, DUR_MAX = 1, 15
    DUR_STR         = False
    DEFAULT_DUR     = 6


class KlingO3ProWorker(_SimpleFalVideoWorker):
    """Kling O3 Pro (fal 2026-09-24) — T2V (16:9 · 9:16 · 1:1) + I2V avec
    image de fin, 3–15 s (chaîne), audio optionnel (faux par défaut) :
    0,112 $/s sans, 0,14 $/s avec. ⚠ image de départ = `image_url`."""
    ENDPOINT_T2V    = "fal-ai/kling-video/o3/pro/text-to-video"
    ENDPOINT_I2V    = "fal-ai/kling-video/o3/pro/image-to-video"
    MODEL           = "kling-o3-pro"
    PRICE_PER_S     = 0.14
    PRICE_BY_RES    = {"1080p": 0.14}
    AUDIO           = True
    AUDIO_DEFAULT   = False
    AUDIO_PRICE_OFF = {"1080p": 0.112}
    END_FRAME       = True
    SEND_RATIO      = True
    RATIOS          = ("16:9", "9:16", "1:1")
    RATIO_T2V_ONLY  = True
    SEND_DURATION   = True
    DUR_MIN, DUR_MAX = 3, 15
    DUR_STR         = True
    DEFAULT_DUR     = 5

    def _extra_args(self, mode: str) -> dict:
        return {"shot_type": self.params.get("shot_type", "customize")}


class KlingO3StandardWorker(KlingO3ProWorker):
    """Kling O3 Standard — même contrat que le Pro, 0,084 $/s sans audio,
    0,112 $/s avec (fiches fal 2026-09-24)."""
    ENDPOINT_T2V    = "fal-ai/kling-video/o3/standard/text-to-video"
    ENDPOINT_I2V    = "fal-ai/kling-video/o3/standard/image-to-video"
    MODEL           = "kling-o3-standard"
    PRICE_PER_S     = 0.112
    PRICE_BY_RES    = {"1080p": 0.112}
    AUDIO_PRICE_OFF = {"1080p": 0.084}


class _H3FalWorker(_SimpleFalVideoWorker):
    """MiniMax H3 sur fal — base des trois paliers (relevé 2026-09-13).

    Tout ce qui est propre au moteur vient de core/h3_family : chemins, noms de
    résolution (« 768p » → « 768P »), durée 5–15 s, tarif par palier ET par
    résolution, mode de réécriture du prompt. Le schéma I2V n'a pas
    d'aspect_ratio (le cadre suit l'image) : RATIO_T2V_ONLY le retient.
    """
    TIER            = "minimax-h3"
    SEND_RESOLUTION = True
    SEND_RATIO      = True
    RATIO_T2V_ONLY  = True
    SEND_DURATION   = True
    DUR_STR         = False   # entier chez MiniMax
    END_FRAME       = True    # image_url + end_image_url (première/dernière image)
    DEFAULT_DUR     = 5

    def _resolution_arg(self, res: str) -> str:
        from core import h3_family as _h3
        return _h3.fal_resolution(self.TIER, res)

    def _price_per_s(self, res: str) -> float:
        from core import h3_family as _h3
        return _h3.price_per_second(self.TIER, res)

    def _extra_args(self, mode: str) -> dict:
        from core import h3_family as _h3
        out = {}
        wanted = self.params.get("prompt_expansion_mode", "")
        # Requis sur Max/Turbo, optionnel sur H3 : on l'envoie toujours borné
        # aux valeurs du palier — un mode inconnu serait un 422.
        if wanted or self.TIER in _h3.EXPANSION_REQUIRED:
            out["prompt_expansion_mode"] = _h3.clamp_expansion(self.TIER, wanted)
        return out


class H3Worker(_H3FalWorker):
    """MiniMax H3 — 480P/768P natifs, 2K/4K = upscale du 768P. ~$0.06/s en 768p."""
    TIER         = "minimax-h3"
    ENDPOINT_T2V = "minimax/h3/text-to-video"
    ENDPOINT_I2V = "minimax/h3/image-to-video"
    MODEL        = "minimax-h3"


class H3MaxWorker(_H3FalWorker):
    """MiniMax H3 Max — 1080P par raffinement latent. prompt_expansion_mode requis."""
    TIER         = "minimax-h3-max"
    ENDPOINT_T2V = "minimax/h3-max/text-to-video"
    ENDPOINT_I2V = "minimax/h3-max/image-to-video"
    MODEL        = "minimax-h3-max"


class H3MaxTurboWorker(_H3FalWorker):
    """MiniMax H3 Max Turbo — même palier, moitié prix."""
    TIER         = "minimax-h3-max-turbo"
    ENDPOINT_T2V = "minimax/h3-max-turbo/text-to-video"
    ENDPOINT_I2V = "minimax/h3-max-turbo/image-to-video"
    MODEL        = "minimax-h3-max-turbo"


class Sora2Worker(_CancellableWorker):
    """
    Génère une vidéo via Sora 2 (OpenAI / fal.ai) — T2V et I2V, deux paliers.

    Fiches fal 2026-09-24 : durée 4 / 8 / 12 / 16 / 20 s (entier — l'ancien
    appel n'en envoyait pas et restait à 4 s), ratio 16:9 ou 9:16, résolution
    « 720p » (Sora 2) ou 720p / 1080p / true_1080p (Sora 2 Pro).
      Sora 2     : $0.10/s
      Sora 2 Pro : $0.30/s 720p · $0.50/s 1080p (1792×1024) · $0.70/s true_1080p (1920×1080)
    """
    progress = pyqtSignal(int, str)
    finished = pyqtSignal(dict)
    failed   = pyqtSignal(str)

    _DURATIONS = (4, 8, 12, 16, 20)
    _PRICE = {
        "std": {"720p": 0.10, "1080p": 0.10},
        "pro": {"720p": 0.30, "1080p": 0.50, "true_1080p": 0.70},
    }
    _MODEL = {"std": "sora-2", "pro": "sora-2-pro"}

    def __init__(self, params: dict):
        """
        params attendus :
          prompt       (str)  requis
          variant      (str)  "std" | "pro", défaut "std"
          mode         (str)  "t2v" | "i2v" (image_url / image_path)
          aspect_ratio (str)  "16:9" | "9:16" (autre → 16:9)
          duration     (int)  4 | 8 | 12 | 16 | 20 (arrondi au plus proche)
          resolution   (str)  "720p" | "1080p" | "true_1080p" (Pro)
        """
        super().__init__()
        self.params = params

    @classmethod
    def snap_duration(cls, seconds) -> int:
        try:
            v = float(seconds)
        except (TypeError, ValueError):
            return 4
        return min(cls._DURATIONS, key=lambda d: abs(d - v))

    def _variant(self) -> str:
        return "pro" if (self.params.get("variant") or "").lower() == "pro" else "std"

    def run(self):
        cfg = load_config()
        key = cfg.get("api_key", "").strip()
        if not key:
            self._mock()
        else:
            self._real(key)

    def _mock(self):
        dur = self.snap_duration(self.params.get("duration", 4))
        for pct, msg in [
            (10, "Sora 2 — mode mock…"),
            (50, "Génération vidéo OpenAI (simulation)…"),
            (100, "Terminé — mode mock (aucune clé fal.ai)"),
        ]:
            self.progress.emit(pct, msg)
            time.sleep(0.5)
        self.finished.emit({"url": "", "duration": dur, "model": self._MODEL[self._variant()],
                            "credits_used": 0})

    def _real(self, key: str):
        try:
            import fal_client
            import requests

            os.environ["FAL_KEY"] = key
            ensure_image_urls(fal_client, self.params, self.progress.emit)

            variant = self._variant()
            mode    = "i2v" if (self.params.get("mode") == "i2v" or self.params.get("image_url")) else "t2v"
            dur     = self.snap_duration(self.params.get("duration", 4))
            ratio   = self.params.get("aspect_ratio", "16:9")
            if ratio not in ("16:9", "9:16"):
                ratio = "16:9"
            res     = (self.params.get("resolution", "720p") or "720p").lower().split()[0]
            table   = self._PRICE[variant]
            if res not in table:
                res = "720p"
            if variant == "std":
                # Sora 2 (non Pro) : la fiche ne documente que « 720p ».
                res = "720p"
            rate    = table[res]
            cost    = dur * rate
            prompt_raw = self.params.get("prompt", "")
            prompt_en  = engine_prompt(self.params)   # prompt FINAL respecté

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

            endpoint = ("fal-ai/sora-2/image-to-video" if mode == "i2v"
                        else "fal-ai/sora-2/text-to-video") + ("/pro" if variant == "pro" else "")
            args: dict = {
                "prompt":       prompt_en,
                "aspect_ratio": ratio,
                "duration":     dur,
                "resolution":   res,
            }
            if mode == "i2v":
                args["image_url"] = self.params["image_url"]

            self.progress.emit(10, f"Sora 2{' Pro' if variant == 'pro' else ''} {mode.upper()} — {dur}s {res} (~${cost:.2f})…")

            result = fal_client.subscribe(endpoint, arguments=args, with_logs=False)

            if not isinstance(result, dict):
                raise RuntimeError(f"Réponse inattendue : {str(result)[:200]}")

            url = _extract_video_url(result)
            if not url:
                raise RuntimeError(f"URL vidéo manquante : {str(result)[:200]}")

            self.progress.emit(80, "Téléchargement de la vidéo…")
            data = requests.get(url, timeout=300).content

            out_dir  = _video_output_dir()
            ts       = int(time.time())
            local    = os.path.join(out_dir, f"sora2{'pro' if variant == 'pro' else ''}_{mode}_{dur}s_{ts}.mp4")
            with open(local, "wb") as f:
                f.write(data)

            self.progress.emit(100, f"Sora 2 ✓  {dur}s · {res} · ~${cost:.2f}")
            if not self._cancelled:
                self.finished.emit({
                    "url":          url,
                    "local_path":   local,
                    "duration":     dur,
                    "resolution":   res,
                    "model":        f"{self._MODEL[variant]}-{mode}",
                    "credits_used": cost,
                })

        except Exception as e:
            if not self._cancelled:
                self.failed.emit(humanize_api_error(f"Erreur Sora 2 : {e}"))
