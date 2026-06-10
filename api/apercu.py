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
        urls = [fal_client.upload_file(building_ref),
                fal_client.upload_file(inspiration_ref)]
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
        facade_url = fal_client.upload_file(building_ref)
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
        inspi_url = fal_client.upload_file(inspiration_ref)
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
            path = run_generation(prompt, self._out_dir, self._api_key,
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

    def __init__(self, shots: list):
        super().__init__()
        self._shots      = shots
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

                    path = run_generation(prompt, out_dir, self._api_key, _prog,
                                          self._building_ref)

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
