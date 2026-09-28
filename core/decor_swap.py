"""core/decor_swap.py — « Changer le décor · acteurs intacts » (28/09/2026).

Pourquoi ce moteur existe
-------------------------
Relevé du compte fal de Matthieu (essais du 25/09/2026) : Seedance refuse les
visages de personnes réelles — HTTP 422 `content_policy_violation`, « likenesses
of real people », raison `partner_validation_failed` : c'est le filtre de
ByteDance, appliqué chez TOUS les distributeurs. Et tout éditeur génératif
(Kling, Wan, HappyHorse…) redessine l'image entière, visages compris : il rend
un visage ressemblant, pas le visage filmé.

Ici, AUCUN modèle génératif ne touche aux acteurs :
  1. détourage des acteurs par VEED sur fal (masque vidéo séparé, en H.264) ;
  2. un décor SANS personne : image ou vidéo générée d'après la consigne,
     l'image de référence telle quelle, ou un fichier fourni ;
  3. recomposition LOCALE par ffmpeg : les pixels des acteurs sont ceux du
     clip source (alphamerge), la piste son d'origine est gardée ;
  4. en option : harmonisation de la couleur des acteurs sur le décor (locale,
     gratuite) et rééclairage IA ID-V2V (génératif : visages ressemblants, plus
     identiques au pixel — d'où l'étiquette « expérimental »).

C'est la version conforme du masquage fait à la main dans After Effects le
25/09 : Seedance ne voit plus jamais un visage, il n'y a rien à contourner
(la règle 5.2 de BytePlus interdit le contournement « par lots ou de façon
automatisée » de sa revue des personnes réelles).

Ce module est PUR : ni Qt, ni réseau. Commandes ffmpeg, consignes, coûts,
choix du masque. Le worker `api/decor_swap.py` orchestre les appels.
"""

from __future__ import annotations

import json
import math
import os
import re
import subprocess

ENGINE_KEY = "decor-swap"

#: Fiches fal relues le 28/09/2026 (llms.txt de chaque endpoint).
MATTING_ENDPOINT = "veed/video-background-removal"
MATTING_PRICE_PER_30_FRAMES = 0.0225      # « Refine Foreground Edges » activé
RELIGHT_ENDPOINT = "fal-ai/id-v2v/relight"
RELIGHT_PRICE_PER_S = 0.20
RELIGHT_MAX_FRAMES = 241                  # num_frames : 17 à 241
RELIGHT_KEYFRAME_ENGINE = "nb2"           # rééclaire l'image clé (Nano Banana 2 /edit)

PLATE_GEN_IMAGE = "gen_image"
PLATE_GEN_VIDEO = "gen_video"
PLATE_REF_IMAGE = "ref_image"
PLATE_FILE = "file"

#: (libellé FR — traduit à l'affichage, clé). L'ordre est celui du sélecteur.
PLATE_MODES = [
    ("Image générée d'après la consigne", PLATE_GEN_IMAGE),
    ("Vidéo générée d'après la consigne (Seedance 2.0, décor animé)", PLATE_GEN_VIDEO),
    ("Image de référence telle quelle", PLATE_REF_IMAGE),
    ("Fichier fourni (image ou vidéo)…", PLATE_FILE),
]
PLATE_MODE_KEYS = tuple(k for _l, k in PLATE_MODES)

VIDEO_EXTS = (".mp4", ".mov", ".webm", ".m4v", ".mkv", ".avi", ".mxf")
IMAGE_EXTS = (".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tif", ".tiff")

#: Ratios qu'accepte Seedance 2.0 en texte → vidéo et image → vidéo.
SEEDANCE_ASPECTS = ("21:9", "16:9", "4:3", "1:1", "3:4", "9:16")


def is_video_file(path: str) -> bool:
    return os.path.splitext(str(path or ""))[1].lower() in VIDEO_EXTS


def is_image_file(path: str) -> bool:
    return os.path.splitext(str(path or ""))[1].lower() in IMAGE_EXTS


# ── Consignes ──────────────────────────────────────────────────────────────────

_TAGS = re.compile(r"@(Video|Image|Audio|Element)\d*", re.I)


def clean_user_prompt(text: str) -> str:
    """Retire les balises Seedance (@Video1, @Image1…) : le décor se génère seul,
    sans clip ni personnage à citer."""
    t = _TAGS.sub(" ", str(text or ""))
    return re.sub(r"\s{2,}", " ", t).strip(" ,;:.\n\t")


def plate_prompt_en(description_en: str, video: bool = False) -> str:
    """Consigne ANGLAISE du décor vide. L'absence de personnes est une exigence de
    la méthode (le filtre de ByteDance n'a alors aucun visage à examiner), et la
    caméra fixe évite un décor qui bouge sous des acteurs immobiles."""
    base = (description_en or "").strip().rstrip(".") or "a neutral, softly lit film set"
    tail = ("Empty set: no people, no person, no human figure, no character, "
            "no silhouette, no crowd. Static camera, locked-off shot, eye-level, "
            "natural perspective, photorealistic, cinematic lighting.")
    if video:
        tail += (" Only subtle ambient motion (lights, reflections, air, particles); "
                 "no camera movement, no cuts.")
    return f"{base}. {tail}"


RELIGHT_KEYFRAME_PROMPT = (
    "Relight the people in this image so that their lighting, shadows, contrast and "
    "color temperature match the background scene around them. Keep every face, "
    "identity, expression, pose, hair, clothing and the framing exactly the same. "
    "Do not change the background and do not add anything.")


def relight_prompt_en(description_en: str) -> str:
    base = (description_en or "").strip().rstrip(".") or "the scene"
    return (f"The same people and performance, now lit consistently with {base}. "
            "Keep identities, expressions, gaze, lip movements and motion unchanged.")


# ── Coûts (estimations, affichées et journalisées comme telles) ────────────────

def matting_cost(frames: int) -> float:
    """VEED : 0,0225 $ par tranche de 30 images, bords affinés (fiche fal)."""
    return math.ceil(max(1, int(frames or 0)) / 30) * MATTING_PRICE_PER_30_FRAMES


def relight_cost(seconds: float) -> float:
    return max(0.0, float(seconds or 0.0)) * RELIGHT_PRICE_PER_S


_PRICE = re.compile(r"\$\s*([0-9]+(?:[.,][0-9]+)?)")


def price_from_hint(hint: str, default: float = 0.08) -> float:
    """Prix lu dans « ~$0.08 ». Le « $ » est OBLIGATOIRE : sans lui, « Seedream
    5.0 » se lisait 5 $ l'image (piège relevé le 30/08/2026)."""
    m = _PRICE.search(str(hint or ""))
    if not m:
        return default
    try:
        return float(m.group(1).replace(",", "."))
    except ValueError:
        return default


def image_price(engine_key: str) -> float:
    try:
        from core import image_engines as _ie
        if _ie.is_comfy(engine_key):
            return 0.0
        return price_from_hint(_ie.price_hint(engine_key))
    except Exception:
        return 0.08


# ── Résultats fal ──────────────────────────────────────────────────────────────

def matting_args(video_url: str) -> dict:
    """Deux vidéos H.264 (image et masque) plutôt qu'un VP9 avec alpha : le masque
    se lit sans décodeur libvpx, et la fiche recommande le H.264 pour la qualité."""
    return {"video_url": video_url, "output_codec": "h264",
            "refine_foreground_edges": True, "subject_is_person": True}


def output_urls(result) -> list:
    """URLs des fichiers rendus : `video` est une LISTE chez VEED, un objet ailleurs."""
    if not isinstance(result, dict):
        return []
    v = result.get("video")
    items = v if isinstance(v, list) else [v]
    out = []
    for it in items:
        if isinstance(it, dict) and it.get("url"):
            out.append(str(it["url"]))
        elif isinstance(it, str) and it.startswith("http"):
            out.append(it)
    return out


def first_image_url(result) -> str:
    if isinstance(result, dict):
        imgs = result.get("images")
        if isinstance(imgs, list) and imgs and isinstance(imgs[0], dict) and imgs[0].get("url"):
            return str(imgs[0]["url"])
        img = result.get("image")
        if isinstance(img, dict) and img.get("url"):
            return str(img["url"])
    raise RuntimeError(f"Réponse sans image : {str(result)[:200]}")


_ALPHA_NAMES = ("alpha", "mask", "matte")


def pick_alpha(paths: list, saturation_of=None) -> str:
    """Le fichier MASQUE parmi les sorties de VEED (image + masque, ordre non
    documenté). D'abord le nom (« alpha », « mask », « matte »), sinon le moins
    saturé — un masque est gris, saturation ≈ 0 —, sinon le dernier."""
    paths = [p for p in (paths or []) if p]
    if not paths:
        return ""
    if len(paths) == 1:
        return paths[0]
    named = [p for p in paths if any(n in os.path.basename(p).lower() for n in _ALPHA_NAMES)]
    if len(named) == 1:
        return named[0]
    if saturation_of is not None:
        scored = []
        for p in paths:
            try:
                scored.append((float(saturation_of(p)), p))
            except Exception:
                continue
        if scored:
            return min(scored)[1]
    return paths[-1]


# ── Sondes et harmonisation ────────────────────────────────────────────────────

def _run(cmd: list, timeout: int = 900) -> subprocess.CompletedProcess:
    from core.video_utils import _NO_WINDOW
    return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout,
                          creationflags=_NO_WINDOW)


def run_ffmpeg(cmd: list, timeout: int = 1800) -> None:
    r = _run(cmd, timeout)
    if r.returncode != 0:
        tail = " ".join((r.stderr or "").strip().splitlines()[-3:])
        raise RuntimeError(f"ffmpeg a échoué : {tail[:300]}")


def _fps_value(txt: str) -> float:
    try:
        if "/" in str(txt):
            n, d = str(txt).split("/", 1)
            return float(n) / float(d) if float(d) else 0.0
        return float(txt)
    except (TypeError, ValueError, ZeroDivisionError):
        return 0.0


def probe(path: str) -> dict:
    """{width, height, fps, fps_str, duration, frames, has_audio} du clip, par ffprobe."""
    from core.video_utils import get_ffprobe_exe
    out = {"width": 0, "height": 0, "fps": 0.0, "fps_str": "", "duration": 0.0,
           "frames": 0, "has_audio": False}
    if not (path and os.path.isfile(path)):
        return out
    try:
        r = _run([get_ffprobe_exe(), "-v", "error", "-show_entries",
                  "stream=codec_type,width,height,avg_frame_rate,r_frame_rate,nb_frames"
                  ":format=duration", "-of", "json", path], timeout=30)
        data = json.loads(r.stdout or "{}")
    except Exception:
        return out
    streams = data.get("streams") or []
    v = next((s for s in streams if s.get("codec_type") == "video"), None)
    out["has_audio"] = any(s.get("codec_type") == "audio" for s in streams)
    try:
        out["duration"] = float((data.get("format") or {}).get("duration") or 0.0)
    except (TypeError, ValueError):
        pass
    if v:
        out["width"] = int(v.get("width") or 0)
        out["height"] = int(v.get("height") or 0)
        fps_str = v.get("avg_frame_rate") or ""
        if _fps_value(fps_str) <= 0:
            fps_str = v.get("r_frame_rate") or ""
        out["fps"] = _fps_value(fps_str) or 25.0
        out["fps_str"] = fps_str if _fps_value(fps_str) > 0 else "25"
        try:
            out["frames"] = int(v.get("nb_frames") or 0)
        except (TypeError, ValueError):
            out["frames"] = 0
    if not out["frames"] and out["duration"] and out["fps"]:
        out["frames"] = int(round(out["duration"] * out["fps"]))
    return out


def aspect_label(width: int, height: int, allowed=SEEDANCE_ASPECTS) -> str:
    if not width or not height:
        return "16:9"
    r = width / height

    def _v(a: str) -> float:
        w, h = a.split(":")
        return float(w) / float(h)
    return min(allowed, key=lambda a: abs(_v(a) - r))


def video_saturation(path: str, frames: int = 8) -> float:
    """Saturation moyenne (signalstats SATAVG) des premières images : ≈ 0 pour un masque."""
    from core.video_utils import get_ffmpeg_exe
    r = _run([get_ffmpeg_exe(), "-hide_banner", "-i", path, "-frames:v", str(frames),
              "-vf", "signalstats,metadata=print:key=lavfi.signalstats.SATAVG",
              "-f", "null", "-"], timeout=120)
    vals = [float(x) for x in re.findall(r"SATAVG=([0-9.]+)", (r.stderr or "") + (r.stdout or ""))]
    if not vals:
        raise RuntimeError("signalstats illisible")
    return sum(vals) / len(vals)


def mask_coverage(mask_png: str) -> float:
    """Part de l'image couverte par le masque (0–1). Sert à refuser un détourage
    qui n'a trouvé personne AVANT de livrer un décor vide."""
    from PIL import Image
    with Image.open(mask_png) as im:
        g = im.convert("L")
        hist = g.histogram()
    total = sum(hist) or 1
    return sum(hist[128:]) / total


def region_means(image_path: str, mask_path: str = "") -> tuple:
    """Moyenne RGB d'une image, sur la zone blanche du masque s'il est donné."""
    from PIL import Image, ImageStat
    with Image.open(image_path) as im:
        rgb = im.convert("RGB")
        mask = None
        if mask_path:
            with Image.open(mask_path) as mk:
                mask = mk.convert("L").resize(rgb.size).point(lambda v: 255 if v >= 128 else 0)
        st = ImageStat.Stat(rgb, mask=mask) if mask is not None else ImageStat.Stat(rgb)
        return tuple(float(x) for x in st.mean[:3])


def harmonize_gains(fg_rgb, plate_rgb, strength: float = 0.5) -> tuple:
    """Gains R, G, B à appliquer aux acteurs pour les rapprocher du décor : la
    dominante de couleur d'abord, un peu de luminosité ensuite. Bornés — une
    harmonisation, pas un étalonnage : les visages restent ceux du tournage."""
    try:
        fg = [max(0.0, float(x)) for x in fg_rgb][:3]
        pl = [max(0.0, float(x)) for x in plate_rgb][:3]
    except (TypeError, ValueError):
        return (1.0, 1.0, 1.0)
    fg_l, pl_l = sum(fg) / 3.0, sum(pl) / 3.0
    if fg_l < 1.0 or pl_l < 1.0 or len(fg) < 3 or len(pl) < 3:
        return (1.0, 1.0, 1.0)
    s = max(0.0, min(1.0, float(strength)))
    bright = min(1.15, max(0.85, (pl_l / fg_l) ** (0.5 * s)))
    gains = []
    for c in range(3):
        fg_n, pl_n = fg[c] / fg_l, pl[c] / pl_l
        g = (pl_n / fg_n) ** s if fg_n > 0 and pl_n > 0 else 1.0
        g = min(1.25, max(0.8, g)) * bright
        gains.append(round(min(1.35, max(0.7, g)), 4))
    return tuple(gains)


# ── Commandes ffmpeg ───────────────────────────────────────────────────────────

def composite_command(ffmpeg: str, source: str, alpha: str, plate: str, out: str, *,
                      width: int, height: int, fps_str: str, plate_is_video: bool,
                      gains=None, feather: float = 0.8, crf: int = 14) -> list:
    """Acteurs du SOURCE (pixels d'origine) posés sur le décor par leur masque.

    - le décor est mis à la taille du source en « cover » (rognage centré) ;
    - une vidéo de décor plus courte que le plan est bouclée ;
    - le masque est adouci d'un flou léger (bords) ;
    - sans gains, les pixels des acteurs ne subissent aucune conversion de
      couleur : seul l'encodage H.264 final (CRF 14, quasi sans perte) les touche.
    """
    fps = str(fps_str or "25")
    w, h = int(width), int(height)
    cmd = [ffmpeg, "-y", "-hide_banner", "-loglevel", "error",
           "-i", source, "-i", alpha]
    if plate_is_video:
        cmd += ["-stream_loop", "-1", "-i", plate]
    else:
        cmd += ["-loop", "1", "-framerate", fps, "-i", plate]
    blur = f",gblur=sigma={feather:g}" if feather and feather > 0 else ""
    parts = [
        f"[2:v]scale={w}:{h}:force_original_aspect_ratio=increase:flags=lanczos,"
        f"crop={w}:{h},setsar=1,fps={fps},format=yuv420p[bg]",
        f"[1:v]scale={w}:{h}:flags=bicubic,setsar=1,fps={fps},format=gray{blur}[m]",
        f"[0:v]setsar=1,fps={fps}[src]",
        "[src][m]alphamerge[fg0]",
    ]
    if gains and any(abs(float(g) - 1.0) > 0.004 for g in gains):
        r, g, b = (float(x) for x in gains[:3])
        parts.append(f"[fg0]colorchannelmixer=rr={r:.4f}:gg={g:.4f}:bb={b:.4f}[fg]")
    else:
        parts.append("[fg0]null[fg]")
    parts.append("[bg][fg]overlay=0:0:shortest=1:format=auto,format=yuv420p[v]")
    cmd += ["-filter_complex", ";".join(parts),
            "-map", "[v]", "-map", "0:a?",
            "-c:v", "libx264", "-preset", "medium", "-crf", str(int(crf)),
            "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "320k",
            "-shortest", "-movflags", "+faststart", out]
    return cmd


def remux_audio_command(ffmpeg: str, video: str, audio_source: str, out: str,
                        speed: float = 1.0) -> list:
    """Remet la piste son du clip source sous une vidéo rendue sans son (ID-V2V).
    `speed` ≠ 1 recale la durée de l'image sur celle du son (setpts)."""
    cmd = [ffmpeg, "-y", "-hide_banner", "-loglevel", "error", "-i", video, "-i", audio_source]
    if abs(float(speed) - 1.0) > 0.03:
        cmd += ["-filter:v", f"setpts={1.0 / float(speed):.6f}*PTS",
                "-c:v", "libx264", "-preset", "medium", "-crf", "14", "-pix_fmt", "yuv420p"]
    else:
        cmd += ["-c:v", "copy"]
    cmd += ["-map", "0:v:0", "-map", "1:a?", "-c:a", "aac", "-b:a", "320k",
            "-shortest", "-movflags", "+faststart", out]
    return cmd


def frame_command(ffmpeg: str, video: str, seconds: float, out_png: str) -> list:
    return [ffmpeg, "-y", "-hide_banner", "-loglevel", "error",
            "-ss", f"{max(0.0, float(seconds)):.3f}", "-i", video,
            "-frames:v", "1", out_png]
