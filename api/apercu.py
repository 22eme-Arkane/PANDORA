"""Génération de Moods storyboard — outil de test de prompt et d'ambiance.

Flux t2i pur : on teste le prompt Seedance + les paramètres caméra du plan.
Aucune référence image injectée — la fidélité aux personnages/décors n'est pas
l'objectif ; c'est valider l'ambiance, l'éclairage et le prompt avant Seedance 2.0.
"""

import os
import uuid
import requests
from PyQt6.QtCore import QThread, pyqtSignal
from core.worker import humanize_api_error


# ── Camera term mappings (Flux-native English) ────────────────────────────────

_SHOT_SIZE_EN = {
    "GP":     "extreme close-up, face filling the entire frame",
    "GM":     "medium close-up, head and shoulders framing",
    "PM":     "medium shot, waist up",
    "PP":     "cowboy shot, mid-thigh up",
    "PL":     "wide shot, full body visible",
    "PE":     "establishing shot, wide environmental view",
    "PTG":    "extreme wide shot, tiny subjects in vast landscape",
    "Insert": "insert shot, isolated detail close-up",
}

_CAMERA_AXIS_EN = {
    "Face":          "straight-on frontal angle, symmetrical framing",
    "3/4":           "three-quarter angle, slight diagonal",
    "Latéral 90°":   "side profile, 90-degree lateral angle",
    "Dos":           "shot from behind the subject",
    "Plongée":       "high angle shot, camera looking down on subject",
    "Contre-plongée":"low angle shot, camera looking up, dramatic upward perspective",
}

_MOVEMENT_EN = {
    "Panoramique horizontal": "horizontal pan",
    "Panoramique vertical":   "vertical tilt",
    "Travelling avant":       "dolly push in, camera moves forward",
    "Travelling arrière":     "dolly pull out, camera moves backward",
    "Travelling latéral":     "lateral tracking shot",
    "Zoom avant":             "zoom in",
    "Zoom arrière":           "zoom out",
    "Steadicam":              "smooth steadicam glide",
    "Grue / Drone":           "crane or drone aerial move",
    "Caméra portée":          "handheld camera, organic movement",
    "Plongée":                "downward tilt from high position",
    "Contre-plongée":         "upward tilt from low position",
}


def _distance_to_en(dist_str: str) -> str:
    """Converts a metric subject-to-camera distance to Flux-friendly English descriptor."""
    try:
        num_str = "".join(c for c in dist_str if c.isdigit() or c == ".")
        m = float(num_str)
    except (ValueError, TypeError):
        return f"camera at {dist_str} from subject"
    if m <= 0.5:
        return f"camera {dist_str} from subject, extreme close proximity, macro-like framing"
    if m <= 1.0:
        return f"camera {dist_str} from subject, very close intimate distance"
    if m <= 2.0:
        return f"camera {dist_str} from subject, close proximity"
    if m <= 4.0:
        return f"camera {dist_str} from subject, short conversational distance"
    if m <= 8.0:
        return f"camera {dist_str} from subject, medium distance"
    if m <= 20.0:
        return f"camera {dist_str} from subject, long distance"
    return f"camera {dist_str} from subject, very long distance, subject far from camera"


def _focal_to_en(focal_str: str) -> str:
    """Converts a focal length string to Flux-friendly English visual descriptor."""
    try:
        mm = int("".join(c for c in focal_str if c.isdigit()))
    except (ValueError, TypeError):
        return f"{focal_str} lens"
    if mm <= 14:
        return f"{mm}mm ultra-wide angle lens, extreme perspective distortion, vast environmental scale"
    if mm <= 21:
        return f"{mm}mm wide angle lens, strong perspective, expansive environmental framing"
    if mm <= 28:
        return f"{mm}mm wide angle lens, natural wide perspective, slight distortion"
    if mm <= 40:
        return f"{mm}mm slightly wide lens, natural human perspective, minimal distortion"
    if mm <= 60:
        return f"{mm}mm normal lens, neutral perspective, true-to-life proportions"
    if mm <= 90:
        return f"{mm}mm portrait lens, shallow depth of field, softly blurred background"
    if mm <= 150:
        return f"{mm}mm telephoto lens, compressed perspective, isolated subject, background bokeh"
    return f"{mm}mm long telephoto, heavily compressed depth, subject isolated from background"


# ── Prompt builder ────────────────────────────────────────────────────────────

def _build_mood_prompt_live(shot: dict) -> str:
    """Prompt mood pour PANDORA | Live (Séquences Live/Mapping).

    Différences voulues vs Cinéma :
      - AUCUN terme caméra (focale, valeur, axe, distance, mouvement) : en mapping
        le cadre est verrouillé par la photo de façade — ces termes polluent ;
      - PAS de titre de plan en français collé au prompt (mélange de langues) ;
      - PAS de « film grain » : le grain remonte les noirs purs de la projection ;
      - le prompt vidéo est temporel (« Opening… Then… final moment ») mais le mood
        est une IMAGE FIXE servant de KEYFRAME DE DÉBUT du plan → on demande
        explicitement l'état d'OUVERTURE."""
    seedance = (shot.get("seedance_prompt") or "").strip()
    parts = []
    if seedance:
        parts.append(seedance)
        parts.append(
            "Render the OPENING state of this sequence as ONE single still image — "
            "depict only the initial state described above, ignore the later "
            "evolution (the 'then' / 'final moment' parts)"
        )
    else:
        action = (shot.get("scene_title") or "").strip()
        if action:
            parts.append(action)
    parts.append("single cinematic still frame, ultra-detailed, sharp focus, 4K")
    return ". ".join(p for p in parts if p)


def build_mood_prompt(shot: dict, film_style: str = "") -> str:
    """Construit le prompt Flux à partir des données du plan storyboard.

    Sensible au contexte : en Séquences Live/Mapping (namespace live_seq_*),
    délègue au builder Live (pas de termes caméra, pas de grain, état d'ouverture).
    Comportement Cinéma inchangé."""
    try:
        import core.storyboard as _sb
        if _sb.get_namespace().startswith("live_seq_"):
            return _build_mood_prompt_live(shot)
    except Exception:
        pass

    parts: list[str] = []

    if film_style:
        parts.append(film_style)

    # Shot size — must come first so Flux frames the composition correctly
    shot_size = (shot.get("shot_size") or "").strip()
    if shot_size and shot_size in _SHOT_SIZE_EN:
        parts.append(_SHOT_SIZE_EN[shot_size])

    # Focal length — strong visual signal for Flux
    focal = (shot.get("focal") or "").strip()
    if focal:
        parts.append(_focal_to_en(focal))

    # Subject-to-camera distance — helps Flux understand spatial scale
    distance = (shot.get("camera_distance") or "").strip()
    if distance:
        parts.append(_distance_to_en(distance))

    # Camera axis
    axis = (shot.get("camera_axis") or "").strip()
    if axis and axis in _CAMERA_AXIS_EN:
        parts.append(_CAMERA_AXIS_EN[axis])

    # Prompt Seedance — core content
    seedance = (shot.get("seedance_prompt") or "").strip()
    if seedance:
        parts.append(seedance)

    # Description de l'action
    scene_title = (shot.get("scene_title") or "").strip()
    if scene_title:
        parts.append(scene_title)

    # Lieu + heure
    decor_name = (shot.get("decor_name") or "").strip()
    shot_time  = (shot.get("shot_time") or "").strip()
    loc_tokens = [t for t in [decor_name, shot_time] if t]
    if loc_tokens:
        parts.append(", ".join(loc_tokens))

    # Camera movement
    movement = (shot.get("camera_movement") or "").strip()
    if movement and movement != "Fixe" and movement in _MOVEMENT_EN:
        parts.append(_MOVEMENT_EN[movement])

    # Qualité
    parts.append(
        "cinematic still frame, 4K, sharp focus, film grain, "
        "professional cinematography, high quality"
    )

    return ". ".join(p for p in parts if p)


# ── Génération effective ──────────────────────────────────────────────────────

def _resolve_building_ref() -> str:
    """Façade du projet à utiliser pour les moods — uniquement en Séquence Mapping."""
    try:
        import core.storyboard as sb
        if sb.get_namespace() == "live_seq_mapping":
            from core.live_building import get_building_ref
            return get_building_ref()
    except Exception:
        pass
    return ""


def run_generation(prompt: str, output_dir: str, api_key: str, progress_cb,
                   building_ref: str = "", inspiration_ref: str = "") -> str:
    """Génère une image et retourne son chemin. Lève une exception si erreur.

    - `building_ref` (façade, mapping) : Flux Kontext ÉDITE la façade (géométrie
      conservée) ;
    - `inspiration_ref` : image d'INSPIRATION (direction artistique à transposer,
      jamais collée). Avec façade → Kontext multi-images (l'univers de
      l'inspiration est projeté SUR la façade) ; sans façade → Kontext
      réinterprète l'inspiration pour dépeindre le plan ;
    - sinon Flux t2i classique."""
    os.makedirs(output_dir, exist_ok=True)

    # ── Mode simulation ───────────────────────────────────────────────────────
    if not api_key:
        import time
        progress_cb("Simulation (pas de clé fal.ai)…")
        time.sleep(1.5)
        try:
            from PIL import Image, ImageDraw
            import random
            bg  = (random.randint(20, 50), random.randint(25, 55), random.randint(35, 70))
            img = Image.new("RGB", (896, 504), color=bg)
            draw = ImageDraw.Draw(img)
            draw.rectangle([0, 0, 895, 503], outline=(80, 80, 80), width=2)
            draw.text((20, 20), "MOOD — SIMULATION", fill=(200, 200, 200))
            draw.text((20, 50), prompt[:120], fill=(140, 140, 140))
            out = os.path.join(output_dir, f"{uuid.uuid4().hex}.jpg")
            img.save(out, "JPEG", quality=85)
            return out
        except Exception:
            return ""

    # ── Appel fal.ai ─────────────────────────────────────────────────────────
    import fal_client
    os.environ["FAL_KEY"] = api_key

    _has_facade = building_ref and os.path.isfile(building_ref)
    _has_inspi  = inspiration_ref and os.path.isfile(inspiration_ref)

    # Directive impérative mapping : conversion NUIT + isolation sur FOND NOIR PUR
    # (le mapping se projette de nuit ; la photo de façade est prise de jour).
    _night_lock = (
        " | NIGHT projection mapping render: convert the scene to deep night — "
        "pitch-black night sky, NO daylight, no sun; same framing, scale and viewpoint "
        "as the source photo. The building is a projection CANVAS: render the projected "
        "content described above ON it — the content may light up only parts of it, "
        "transform its material, or completely cover and hide the facade, exactly as "
        "described. Unlit areas fall to pure black. Remove every surrounding element "
        "(other buildings, street objects, trees, people, ground, sky) and replace the "
        "entire background with PURE BLACK #000000."
    )

    if _has_facade and _has_inspi:
        # Mapping + image d'inspiration : Kontext multi-images — l'univers de la
        # 2ᵉ image (DA) est TRANSPOSÉ en visuels projetés sur la 1ʳᵉ (façade).
        kontext_prompt = (
            prompt
            + " | The FIRST image is the building facade — the projection canvas: keep its "
            "exact framing, scale and viewpoint. Use the SECOND image purely as artistic "
            "INSPIRATION: transpose its universe — palette, light, materials, motifs, "
            "figures, rendering style — into the projected visuals. Do NOT paste, collage "
            "or copy the second image literally."
            + _night_lock
        )
        progress_cb("Envoi de la façade et de l'inspiration à fal.ai…")
        urls = [_upload_ref_robust(fal_client, building_ref),
                _upload_ref_robust(fal_client, inspiration_ref)]
        progress_cb("Mood inspiré sur la façade (Kontext multi)…")
        result = fal_client.subscribe(
            "fal-ai/flux-pro/kontext/max/multi",
            arguments={
                "prompt":         kontext_prompt,
                "image_urls":     urls,
                "guidance_scale": 3.5,
                "aspect_ratio":   "16:9",
            },
        )
    elif _has_facade:
        # Mapping : on édite la façade (géométrie conservée) via Flux Kontext.
        kontext_prompt = prompt + _night_lock
        progress_cb("Envoi de la façade à fal.ai…")
        facade_url = _upload_ref_robust(fal_client, building_ref)
        progress_cb("Génération du Mood nocturne sur la façade (Kontext)…")
        result = fal_client.subscribe(
            "fal-ai/flux-pro/kontext",
            arguments={
                "prompt":              kontext_prompt,
                "image_url":           facade_url,
                "guidance_scale":      3.5,
                "num_inference_steps": 28,
            },
        )
    elif _has_inspi:
        # Sans façade (Cinéma / Live hors mapping) : Kontext réinterprète
        # l'inspiration pour dépeindre le plan — la DA est gardée, pas le contenu.
        kontext_prompt = (
            prompt
            + " | Use this image purely as artistic INSPIRATION: repaint and reimagine it "
            "to depict the scene described above, keeping its palette, light, materials "
            "and rendering style. Do not keep its literal content unless it serves the scene."
        )
        progress_cb("Envoi de l'image d'inspiration à fal.ai…")
        inspi_url = _upload_ref_robust(fal_client, inspiration_ref)
        progress_cb("Mood inspiré de l'image (Kontext)…")
        result = fal_client.subscribe(
            "fal-ai/flux-pro/kontext",
            arguments={
                "prompt":              kontext_prompt,
                "image_url":           inspi_url,
                "guidance_scale":      3.5,
                "num_inference_steps": 28,
            },
        )
    else:
        progress_cb("Génération du Mood via Flux…")
        result = fal_client.subscribe(
            "fal-ai/flux/dev",
            arguments={
                "prompt":                prompt,
                "num_inference_steps":   28,
                "guidance_scale":        3.5,
                "num_images":            1,
                "image_size":            "landscape_16_9",
                "enable_safety_checker": False,
            },
        )
    image_url = result["images"][0]["url"]
    progress_cb("Téléchargement de l'image…")
    resp = requests.get(image_url, timeout=60)
    out  = os.path.join(output_dir, f"{uuid.uuid4().hex}.jpg")
    with open(out, "wb") as f:
        f.write(resp.content)
    return out


# ── Génération mood NANO BANANA 2 (Cinéma) ────────────────────────────────────
# En CINÉMA, les moods passent par Nano Banana 2 (cohérence de personnage, jusqu'à
# 14 réfs) en envoyant les PORTRAITS des personnages assignés + l'IMAGE DU DÉCOR du
# plan → rendu le plus proche du plan final. Le LIVE garde Flux (run_generation,
# façade/mapping). Distinction par le namespace storyboard (« live_* » = Live).

def _is_cinema_mood() -> bool:
    try:
        import core.storyboard as sb
        return not (sb.get_namespace() or "").startswith("live")
    except Exception:
        return True


def _shot_ref_images(shot: dict, include_chars: bool = True,
                     include_decor: bool = True) -> list:
    """Portraits des personnages assignés + image du décor du plan (réfs NB2).
    `include_chars` / `include_decor` permettent d'exclure une catégorie (options
    de la fenêtre « Générer les Moods »)."""
    refs: list = []
    if include_chars:
        try:
            import core.casting as cast
            for cid in (shot.get("character_ids") or []):
                c = cast.get_character(cid) or {}
                cands = [c.get("image_path"), c.get("portrait_path"), c.get("portrait")]
                cands += (c.get("generated_images") or [])[:1]
                for p in cands:
                    if p and os.path.isfile(p):
                        refs.append(p)
                        break
        except Exception:
            pass
    if include_decor:
        try:
            import core.decors as dec
            did = shot.get("decor_id")
            if did:
                p = (dec.get_decor(did) or {}).get("image_path") or ""
                if p and os.path.isfile(p):
                    refs.append(p)
        except Exception:
            pass
    seen, out = set(), []
    for r in refs:
        if r not in seen:
            seen.add(r)
            out.append(r)
    return out[:14]


# Consigne d'édition NB2 : les références (portraits persos + image décor, souvent un
# PLAN D'ENSEMBLE) servent UNIQUEMENT à garder la même pièce et les mêmes personnages.
# Elles ne doivent PAS dicter le cadrage : le mood doit être le PLAN PRÉVU, vu depuis
# l'intérieur du décor, personnages placés dedans — pas une copie du plan d'ensemble.
_MOOD_REF_DIRECTIVE = (
    "IMPORTANT — the reference images are ONLY for consistency: keep the SAME room "
    "(its architecture, materials, colours, furniture and lighting mood) and the SAME "
    "characters (faces, hair, costumes). They are NOT a composition to copy. Generate "
    "the SPECIFIC shot described above, taken FROM INSIDE this room: place the "
    "character(s) within the set, interacting with it, and use the camera position, "
    "angle and framing of the prompt (shot size, focal length, axis). Do NOT reproduce "
    "the wide establishing / overview framing of the reference image — move the camera "
    "into the scene and produce exactly the planned shot."
)

# Consigne spécifique au PLAN D'ARCHITECTE (vue de dessus) envoyé en DERNIÈRE référence :
# c'est un repère d'agencement (géométrie de la pièce), pas une image à reproduire.
_FLOOR_PLAN_DIRECTIVE = (
    "ADDITIONAL — the LAST reference image is a TOP-DOWN ARCHITECTURAL FLOOR PLAN of "
    "this room (a 2D schematic seen from above, NOT a photo). Use it ONLY as a spatial "
    "guide: respect the room's layout and proportions, the position of the walls, doors, "
    "windows and main furniture shown in the plan, so the generated room stays faithful "
    "to this architecture. Do NOT draw, render or include the floor plan itself in the "
    "image — it is a geometry reference only."
)


def _upload_ref_robust(fal_client, path: str) -> str:
    """Upload une image de référence pour NB2, de façon robuste.

    `fal_client.upload_file()` échoue sur deux cas réels rencontrés :
      • chemins NON-ASCII (ex. projet « Un zombie à table ») → codec interne ;
      • backend de stockage indisponible → erreur « Invalid storage type » / GCS
        (déjà contourné par data-URL dans api/tts.py pour BiRefNet).

    On tente d'abord l'upload en BYTES (gère le non-ASCII), puis on bascule sur une
    DATA-URL base64 si le stockage refuse. Les avertissements bruyants de fal_client
    ('Upload failed to fal_v3, falling back to cdn') sont capturés.
    """
    import sys, io, base64, mimetypes
    ct = mimetypes.guess_type(path)[0] or "image/png"
    with open(path, "rb") as _f:
        data = _f.read()
    _cap = io.StringIO()
    _old_out, _old_err = sys.stdout, sys.stderr
    sys.stdout = sys.stderr = _cap
    try:
        try:
            return fal_client.upload(data, content_type=ct)
        except Exception:
            # Stockage fal refusé (Invalid storage type / GCS) → data-URL inline.
            return f"data:{ct};base64,{base64.b64encode(data).decode()}"
    finally:
        sys.stdout, sys.stderr = _old_out, _old_err


def run_generation_nb2(prompt: str, output_dir: str, api_key: str, progress_cb,
                       ref_images: list | None = None, floor_plan: str = "") -> str:
    """Mood via Nano Banana 2 : édition avec réfs (persos + décor) si disponibles,
    sinon génération texte NB2. Aspect 16:9, comme le mood Flux.

    Si `floor_plan` (plan d'architecte vu de dessus) est fourni, il est envoyé EN
    DERNIÈRE référence avec une consigne dédiée : repère d'agencement de la pièce,
    pas une image à reproduire."""
    import fal_client
    os.environ["FAL_KEY"] = api_key
    os.makedirs(output_dir, exist_ok=True)
    refs = [r for r in (ref_images or []) if r and os.path.isfile(r)]
    _fp = floor_plan if (floor_plan and os.path.isfile(floor_plan)) else ""
    # Le plan d'architecte part EN DERNIER (la consigne cible « la dernière image »).
    refs = (refs[:13] + [_fp]) if _fp else refs[:14]
    if refs:
        progress_cb(f"Nano Banana 2 — {len(refs)} référence(s)"
                    + (" + plan d'architecte" if _fp else " (persos + décor)") + "…")
        urls = [_upload_ref_robust(fal_client, r) for r in refs]
        directive = _MOOD_REF_DIRECTIVE + (("\n\n" + _FLOOR_PLAN_DIRECTIVE) if _fp else "")
        result = fal_client.subscribe("fal-ai/nano-banana-2/edit", arguments={
            "prompt": prompt + "\n\n" + directive, "image_urls": urls,
            "num_images": 1, "aspect_ratio": "16:9", "resolution": "1K",
            "output_format": "png", "safety_tolerance": "6",
        })
    else:
        progress_cb("Nano Banana 2…")
        result = fal_client.subscribe("fal-ai/nano-banana-2", arguments={
            "prompt": prompt, "num_images": 1,
            "aspect_ratio": "16:9", "resolution": "1K", "output_format": "png",
        })
    imgs = (result or {}).get("images") or []
    image_url = (imgs[0].get("url") if imgs and isinstance(imgs[0], dict)
                 else (imgs[0] if imgs else ""))
    if not image_url:
        raise RuntimeError("Nano Banana 2 : aucune image renvoyée")
    progress_cb("Téléchargement de l'image…")
    resp = requests.get(image_url, timeout=120)
    out = os.path.join(output_dir, f"{uuid.uuid4().hex}.png")
    with open(out, "wb") as f:
        f.write(resp.content)
    return out


def run_mood(shot: dict, prompt: str, output_dir: str, api_key: str, progress_cb,
             building_ref: str = "", inspiration_ref: str = "",
             options: dict | None = None) -> str:
    """Dispatcher mood. `options` (fenêtre « Générer les Moods ») :
        engine     : "nb2" | "flux"  (défaut : NB2 en Cinéma, Flux en Live)
        chars      : envoyer les réfs personnages (NB2)
        decor      : envoyer la réf décor (NB2)
        floor_plan : envoyer le plan d'architecte (NB2)
    NB2 = réfs persos/décor + plan d'architecte ; Flux = t2i depuis le prompt."""
    opts = options or {}
    engine = (opts.get("engine") or "").strip().lower()
    if engine not in ("nb2", "flux"):
        engine = "nb2" if _is_cinema_mood() else "flux"

    if engine == "nb2":
        refs = _shot_ref_images(shot,
                                include_chars=opts.get("chars", True),
                                include_decor=opts.get("decor", True))
        _fp = ""
        if opts.get("floor_plan", True):
            try:
                from core.decors import floor_plan_for_shot
                _fp = floor_plan_for_shot(shot) or ""
            except Exception:
                _fp = ""
        return run_generation_nb2(prompt, output_dir, api_key, progress_cb, refs,
                                  floor_plan=_fp)
    # Flux : mood t2i depuis le prompt (façade/inspiration seulement si fournies — Live).
    return run_generation(prompt, output_dir, api_key, progress_cb, building_ref,
                          inspiration_ref=inspiration_ref)


# ── Worker unitaire ───────────────────────────────────────────────────────────

class MoodGenerationWorker(QThread):
    progress = pyqtSignal(str)
    finished = pyqtSignal(str)
    failed   = pyqtSignal(str)

    def __init__(self, shot: dict, output_dir: str, custom_prompt: str = "",
                 inspiration_ref: str = ""):
        super().__init__()
        self._shot          = shot
        self._out_dir       = output_dir
        self._custom_prompt = custom_prompt
        self._inspiration   = inspiration_ref
        from core.config import load_config
        import core.style as style_api
        self._api_key    = load_config().get("api_key", "").strip()
        self._film_style = style_api.get_image_suffix() or ""
        self._building_ref = _resolve_building_ref()

    def run(self):
        prompt = (
            self._custom_prompt
            if self._custom_prompt
            else build_mood_prompt(self._shot, self._film_style)
        )
        try:
            path = run_mood(self._shot, prompt, self._out_dir, self._api_key,
                            self.progress.emit, self._building_ref,
                            inspiration_ref=self._inspiration)
            self.finished.emit(path)
        except Exception as e:
            self.failed.emit(humanize_api_error(str(e)))


# ── Worker batch ──────────────────────────────────────────────────────────────

class MoodBatchWorker(QThread):
    shot_progress = pyqtSignal(int, int, str)   # (current, total, message)
    shot_done     = pyqtSignal(str, str)         # (shot_id, image_path)
    shot_failed   = pyqtSignal(str, str)         # (shot_id, error)
    all_done      = pyqtSignal()

    def __init__(self, shots: list, options: dict | None = None):
        super().__init__()
        self._shots      = shots
        self._options    = options or {}
        self._cancelled  = False
        self._was_cancelled = False
        from core.config import load_config
        import core.style as style_api
        self._api_key    = load_config().get("api_key", "").strip()
        self._film_style = style_api.get_image_suffix() or ""
        self._building_ref = _resolve_building_ref()

    def cancel(self):
        self._cancelled     = True
        self._was_cancelled = True

    def run(self):
        import core.storyboard as sb_api
        total = len(self._shots)

        try:
            for i, shot in enumerate(self._shots):
                if self._cancelled:
                    return

                num   = shot.get("number", i + 1)
                title = (shot.get("scene_title") or f"Plan {num}").strip()
                self.shot_progress.emit(i + 1, total, f"Plan {num} — {title[:40]}")

                try:
                    prompt  = build_mood_prompt(shot, self._film_style)
                    out_dir = sb_api.get_apercu_dir(shot["id"])

                    def _prog(msg, _i=i, _t=total):
                        self.shot_progress.emit(_i + 1, _t, msg)

                    path = run_mood(shot, prompt, out_dir, self._api_key, _prog,
                                    self._building_ref, options=self._options)

                    if path and os.path.isfile(path):
                        existing = sb_api.load_apercus(shot["id"])
                        paths    = [p for p in existing.get("paths", []) if os.path.isfile(p)]
                        paths.append(path)
                        sb_api.save_apercus(shot["id"], paths, len(paths) - 1)

                    self.shot_done.emit(shot["id"], path or "")

                except Exception as e:
                    self.shot_failed.emit(shot["id"], str(e))

        finally:
            self.all_done.emit()
