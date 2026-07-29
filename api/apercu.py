"""Génération de Moods storyboard — outil de test de prompt et d'ambiance.

Flux t2i pur : on teste le prompt Seedance + les paramètres caméra du plan.
Aucune référence image injectée — la fidélité aux personnages/décors n'est pas
l'objectif ; c'est valider l'ambiance, l'éclairage et le prompt avant Seedance 2.0.
"""

import json
import os
import uuid
import requests
from PyQt6.QtCore import QThread, pyqtSignal
from core.worker import humanize_api_error


# ── Camera term mappings (Flux-native English) ────────────────────────────────

# Vocabulaire caméra PARTAGÉ avec le prompt vidéo (core/shot_terms.py) : ces
# tables vivaient ici et n'étaient donc pas accessibles au Studio IA, qui
# n'injectait que la focale et le mouvement (2026-07-25). Les convertisseurs
# _distance_to_en / _focal_to_en restent LOCAUX : ils sont calibrés pour Flux
# (plus de paliers) et ne doivent pas changer de rendu.
from core.shot_terms import (SHOT_SIZE_EN as _SHOT_SIZE_EN,
                             CAMERA_AXIS_EN as _CAMERA_AXIS_EN,
                             MOVEMENT_EN as _MOVEMENT_EN)


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

def _build_mood_prompt_live(shot: dict, engine_key: str = "") -> str:
    """Prompt mood pour PANDORA | Live (Séquences Live/Mapping).

    Différences voulues vs Cinéma :
      - AUCUN terme caméra (focale, valeur, axe, distance, mouvement) : en mapping
        le cadre est verrouillé par la photo de façade — ces termes polluent ;
      - PAS de titre de plan en français collé au prompt (mélange de langues) ;
      - PAS de « film grain » : le grain remonte les noirs purs de la projection ;
      - le prompt vidéo est temporel (« Opening… Then… final moment ») mais le mood
        est une IMAGE FIXE servant de KEYFRAME DE DÉBUT du plan → on demande
        explicitement l'état d'OUVERTURE.

    Depuis le 2026-07-25, le Live reçoit lui aussi la GRAMMAIRE du moteur (demande
    Matthieu) : brief à champs pour Nano Banana / GPT Image, prose sans interdit
    pour Seedream, JSON pour FLUX.2. Et les mots de qualité génériques qui traînaient
    ici (« ultra-detailed », « 4K ») disparaissent — ils sont interdits par la
    doctrine de prompt de PANDORA et dégradent la passe de raisonnement de Seedream.
    Le corps est en plus débarrassé de ce qui n'existe qu'en vidéo (mouvement de
    caméra, vitesse, durée, son), en anglais comme en français."""
    # UN seul prompt à sections : ne garder que la VIDÉO (retirer [🎵 SOUND DESIGN]) —
    # le son n'a aucune place dans une image fixe.
    from core.prompt_sections import video_of as _video_of
    from core.image_grammar import (build_image_prompt as _build,
                                    strip_video_terms as _strip_video)
    seedance = _video_of((shot.get("seedance_prompt") or "").strip())
    # ── Ne PAS décrire ce qu'on ne veut pas voir (2026-07-27) ─────────────────
    # Le mood est l'image de DÉPART du plan : seul l'ÉTAT 0 l'intéresse. On lui
    # envoyait pourtant la barre entière — TRANSFORMATION et ÉTAT 1 compris —
    # avant de demander, en une phrase, d'« ignorer l'évolution ». Un moteur
    # d'image ne sait pas ignorer : il rend ce qu'on lui décrit. Constat de
    # Matthieu, captures à l'appui : les moods rendaient le monde forestier
    # final alors que l'ÉTAT 0 dit « façade encore majoritairement givrée,
    # portail sombre ».
    # Les deux blocs temporels sont donc RETIRÉS, pas contredits. Le reste de la
    # barre — surface, noir, style, contraintes — décrit bien une image fixe.
    _blocs = {}
    try:
        from core.live_bar import parse_blocks as _pb
        _blocs = _pb(seedance) or {}
    except Exception:
        _blocs = {}
    # ── Le Mood rend l'état d'ARRIVÉE — pour TOUS les plans (2026-07-28) ──────
    # Décision Matthieu (deuxième passe, après essai d'un sélecteur
    # auto/début/fin retiré le jour même) : « c'est la fin de plan qui est
    # intéressante pour tous les plans. C'est l'action même du plan qui nous
    # intéresse, pas le début, qui est la continuité du plan précédent. »
    # La méthode deux plaques fait ARRIVER la vidéo sur son Mood → ÉTAT 1.
    # Toujours UN état à la fois, jamais la barre entière : décrire ce qu'on
    # ne veut pas voir est le plus sûr moyen de l'obtenir (constat du 27/07).
    _etat = "state_1" if _blocs.get("state_1") else \
        ("state_0" if _blocs.get("state_0") else "")
    if _etat:
        try:
            from core.live_bar import format_blocks as _fb
            body = _fb({k: v for k, v in _blocs.items()
                        if k in ("surface", _etat, "black", "style",
                                 "constraints")})
        except Exception:
            body = _strip_video(seedance)[0]
        # Plus rien à ignorer : la consigne négative disparaît avec les blocs.
        use_case = "Single cinematic still frame, sharp focus."
        return _build({"action": body, "use_case": use_case}, engine_key or "flux")
    if seedance:
        body = _strip_video(seedance)[0]
        use_case = (
            "Render the FINAL state of this sequence as ONE single still "
            "image — depict only the end state, after the transformation "
            "has fully completed. "
            "Single cinematic still frame, sharp focus."
        )
    else:
        body = (shot.get("scene_title") or "").strip()
        use_case = "Single cinematic still frame, sharp focus."
    return _build({"action": body, "use_case": use_case}, engine_key or "flux")


def mood_intent(shot: dict, film_style: str = "") -> dict:
    """Intention structurée d'un Mood Cinéma — indépendante du moteur.

    C'est la matière première : `core/image_grammar.build_image_prompt()` la rend
    ensuite dans la grammaire du moteur choisi (brief à champs pour Nano Banana /
    GPT Image, prose raisonnée sans interdit pour Seedream, JSON pour FLUX.2,
    prose simple pour Flux / Z-Image / Qwen / Ideogram / Recraft).

    Ce qui n'entre PAS dans l'intention (décision Matthieu 2026-07-25) : le
    MOUVEMENT de caméra, la HAUTEUR de caméra, la VITESSE et la durée. Une image
    fige un instant — ces champs ne décrivent que la vidéo, et les écrire pousse le
    moteur au flou de filé ou à une composition « en cours de travelling ».
    Ce qui reste : valeur de plan, axe, focale, profondeur de champ, distance —
    ce sont des propriétés d'une image fixe."""
    from core.image_grammar import strip_video_terms as _strip_video
    from core.shot_terms import (focal_to_en as _focal_only, dof_to_en as _dof_en,
                                 SHOT_TIME_EN as _TIME_EN)

    # Style : la section [🎨 STYLE VISUEL] du prompt (capturée à la création du
    # storyboard, éditable dans le plan) PRIME sur le suffixe projet passé en
    # argument — jamais les deux, sinon le style apparaîtrait en double (2026-07-24).
    seedance_raw = (shot.get("seedance_prompt") or "").strip()
    try:
        from core.prompt_sections import style_of as _style_of
        _style_txt = (_style_of(seedance_raw) or film_style or "").strip()
    except Exception:
        _style_txt = (film_style or "").strip()

    # ── Caméra : uniquement ce qui existe sur une image fixe ──────────────────
    cam: list[str] = []
    shot_size = (shot.get("shot_size") or "").strip()
    if shot_size in _SHOT_SIZE_EN:
        cam.append(_SHOT_SIZE_EN[shot_size])
    axis = (shot.get("camera_axis") or "").strip()
    if axis in _CAMERA_AXIS_EN:
        cam.append(_CAMERA_AXIS_EN[axis])
    # Focale : la focale SEULE. C'est la colonne « P. de champ » qui dit si le
    # fond est flou — l'ancien convertisseur y ajoutait « shallow depth of field »
    # et contredisait le réglage explicite du plan.
    focal = (shot.get("focal") or "").strip()
    if focal:
        cam.append(_focal_only(focal))
    _dof = _dof_en(shot.get("depth_of_field", ""))
    if _dof:
        cam.append(_dof)
    distance = (shot.get("camera_distance") or "").strip()
    if distance:
        cam.append(_distance_to_en(distance))

    # ── Corps du plan : le prompt vidéo, aplati et débarrassé du vidéo-only ───
    seedance = seedance_raw
    if seedance:
        try:
            from core.prompt_sections import is_structured as _ps_is, parse as _ps_parse
            if _ps_is(seedance):
                _sec = _ps_parse(seedance)
                seedance = ". ".join(v.strip().rstrip(".")
                                     for k, v in _sec.items()
                                     if k not in ("sound", "style") and v)
        except Exception:
            pass
        seedance = _strip_video(seedance)[0]

    action_parts = [p.rstrip(" .") for p in
                    (seedance, (shot.get("scene_title") or "").strip()) if p.strip()]

    # Personnages présents → sujet explicite du brief.
    _chars = shot.get("character_names") or []
    if isinstance(_chars, str):
        _chars = [c.strip() for c in _chars.split(",") if c.strip()]
    subject = ", ".join(str(c).strip() for c in _chars if str(c).strip())

    return {
        "subject":     subject,
        "action":      ". ".join(action_parts),
        "setting":     (shot.get("decor_name") or "").strip(),
        "lighting":    _TIME_EN.get((shot.get("shot_time") or "").strip(), ""),
        "camera":      ", ".join(cam),
        "style":       _style_txt,
        # Le style du Mood est en tête depuis toujours et le rendu convient —
        # on ne déplace pas ce qui marche (voir image_grammar.build_image_prompt).
        "style_first": True,
        "use_case":    "Cinematic still frame from a film storyboard — "
                       "one single frozen instant, sharp focus.",
    }


def build_mood_prompt(shot: dict, film_style: str = "", engine_key: str = "") -> str:
    """Prompt d'un Mood, écrit dans la grammaire du moteur `engine_key`.

    Sensible au contexte : en Séquences Live/Mapping (namespace live_seq_*),
    délègue au builder Live (pas de termes caméra, pas de grain, UN seul état
    de la barre — l'ARRIVÉE, décision Matthieu 2026-07-28).
    `engine_key` vide → même repli que `run_mood` (Nano Banana 2 en Cinéma, Flux
    en Live) : le prompt est ainsi toujours écrit pour le moteur qui le recevra."""
    _live = False
    try:
        import core.storyboard as _sb
        _live = _sb.get_namespace().startswith("live_seq_")
    except Exception:
        pass
    if not (engine_key or "").strip():
        engine_key = "nb2" if _is_cinema_mood() else "flux"
    if _live:
        return _build_mood_prompt_live(shot, engine_key)
    from core.image_grammar import build_image_prompt as _build
    return _build(mood_intent(shot, film_style), engine_key)


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


# ── Consignes MAPPING partagées Flux ↔ Nano Banana 2 ──────────────────────────
# Mêmes directives quel que soit le moteur choisi pour le Mood (façade = canvas de nuit,
# fond noir, visibilité pilotée par le prompt) → rendus comparables Flux vs NB2.
_MAPPING_NIGHT_LOCK = (
    " | NIGHT projection mapping render: convert the scene to deep night — "
    "pitch-black night sky, NO daylight, no sun; same framing, scale and viewpoint "
    "as the source photo. The building is a projection CANVAS: render the projected "
    "content described above ON it — the content may light up only parts of it, "
    "transform its material, or completely cover and hide the facade, exactly as "
    "described. Unlit areas fall to pure black. "
    "CRITICAL — VISIBILITY IS DRIVEN BY THE PROMPT, NOT BY THE SOURCE PHOTO: only "
    "what the prompt describes as lit or projected is visible. ANY facade element "
    "the prompt describes as hidden, off, unlit, dark or NOT visible (for example a "
    "door, a window, a metal structure, a stage) MUST be rendered as PURE BLACK "
    "#000000 and MUST NOT appear in the image, even though it is present in the "
    "source photo. Do NOT preserve architectural details the prompt excludes — the "
    "prompt's darkness overrides the source image; when in doubt, an element that "
    "is not explicitly lit stays pure black. "
    "Remove every surrounding element "
    "(other buildings, street objects, trees, people, ground, sky) and replace the "
    "entire background with PURE BLACK #000000."
)

# Priorité façade quand une/des image(s) de RÉFÉRENCE accompagne(nt) la façade (la
# façade est TOUJOURS la 1ʳᵉ image ; les réfs n'enrichissent que l'inspiration).
# Nombre maximal d'images d'INSPIRATION envoyées avec une façade de mapping.
# Chaque image ajoutée pèse face au texte : dix inspirations contre une façade et
# un prompt, et c'est l'inspiration qui gagne. Deux suffisent à donner une
# palette et une matière (constat Matthieu, 2026-07-27).
_MAX_INSPIRATION_MAPPING = 2

def _avec_directive_en_tete(prompt: str, directive: str) -> str:
    """Consigne d'abord, description ensuite — pour les appels à IMAGES.

    Sur un endpoint /edit, le modèle part des images : la consigne qui dit quoi
    faire de chacune doit arriver AVANT le prompt. Placée en queue elle se lit
    comme une remarque ; placée en tête, c'est un ordre. Constat de Matthieu
    (2026-07-27) : « les variations ressemblent toujours aux images de référence
    et jamais aux prompts ».
    """
    _d = (directive or "").lstrip(" |").strip()
    _p = (prompt or "").strip()
    if not _d:
        return _p
    if not _p:
        return _d
    return f"{_d}\n\n{_p}"


_FACADE_PRIORITY_DIRECTIVE = (
    " | ABSOLUTE PRIORITY: the FIRST image is the building facade and it is the "
    "MANDATORY projection canvas. Keep its EXACT geometry, framing, scale, "
    "perspective and viewpoint — the output MUST be THIS facade with the content "
    "projected onto it. The following reference image(s) are ONLY a loose ARTISTIC "
    "INSPIRATION to enrich the projected content: draw from their palette, light, "
    "materials, mood and motifs, but they MUST NOT become the subject, MUST NOT "
    "replace the facade, MUST NOT change the framing, and MUST NOT be pasted, "
    "collaged or copied. The facade always stays the base; the references only "
    "flavour what is projected onto it."
)


def _conform_mood_definition(path: str, aspect_ratio: str = "",
                             resolution: str = "") -> str:
    """Ramène l'image téléchargée à la définition PROMISE par le sélecteur.

    Constat Matthieu (2026-07-29, Forcalquier) : « Générer les moods » réglé
    sur 1280×720, fichier reçu en 1368×768. Les moteurs à enum (Nano Banana :
    1K/2K/4K) et Kontext (aucune dimension acceptée) choisissent LEURS
    dimensions. En mapping c'est double peine : l'écart de résolution entre
    keyframes revient par la porte du Mood, et le ratio approximatif du
    moteur (1368/768 = 1,781) étire la façade à la génération vidéo 16:9
    exacte.

    Redimensionnement LANCZOS EN PLACE, uniquement si le moteur a rendu le
    format demandé (±1 %) : un AUTRE format signifie que le moteur a recadré
    ou réinterprété — l'étirer au forceps abîmerait la géométrie au lieu de
    la réparer, l'image repart telle quelle. Ne lève jamais.
    """
    try:
        from PIL import Image
        from core.image_resolution import target_for
        tw, th = target_for(aspect_ratio or "16:9", resolution or "")
        with Image.open(path) as im:
            w, h = im.size
            if (w, h) == (tw, th) or not (w and h):
                return path
            if abs((w * th) / float(h * tw) - 1.0) > 0.01:
                return path
            im.convert("RGB").resize((tw, th), Image.LANCZOS).save(path)
        return path
    except Exception:
        return path


def run_generation(prompt: str, output_dir: str, api_key: str, progress_cb,
                   building_ref: str = "", inspiration_ref: str = "",
                   aspect_ratio: str = "", resolution: str = "") -> str:
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

    # Directive impérative mapping (nuit + fond noir + exclusion) : constante PARTAGÉE
    # avec Nano Banana 2 → mêmes consignes quel que soit le moteur.
    _night_lock = _MAPPING_NIGHT_LOCK

    if _has_facade and _has_inspi:
        # Mapping + image(s) de référence : Kontext multi-images. ⚠ La FAÇADE (1ʳᵉ image)
        # est la PRIORITÉ ABSOLUE ; la/les référence(s) n'enrichissent que l'inspiration.
        kontext_prompt = prompt + _FACADE_PRIORITY_DIRECTIVE + _night_lock
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
                "aspect_ratio":   aspect_ratio or "16:9",
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
    # Kontext n'accepte aucune dimension : il rend SES tailles (~1 Mpx).
    return _conform_mood_definition(out, aspect_ratio, resolution)


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


def current_mood_is_mapping() -> bool:
    """True si le contexte courant est une séquence MAPPING FAÇADE (une façade de
    projet est résolue) → le sélecteur de moteur doit se restreindre aux moteurs
    capables d'éditer une image de référence (préservation de géométrie)."""
    return bool(_resolve_building_ref())


def mood_engine_choices(is_mapping: bool | None = None) -> list:
    """[(key, label)] des moteurs proposables pour un Mood dans le contexte courant.

    - Mapping façade → UNIQUEMENT les moteurs qui ÉDITENT une image de référence
      (préservent la géométrie du bâtiment) : Flux Kontext + famille Nano Banana +
      Seedream 5 Pro/Lite (choix Matthieu 2026-07-20) ;
    - sinon → tout le catalogue image raster de PANDORA (core/image_engines).
    « flux » = chemin Flux historique (Kontext en mapping, t2i sinon)."""
    from core import image_engines as _ie
    if is_mapping is None:
        is_mapping = current_mood_is_mapping()
    if is_mapping:
        out = [("flux", "Flux Kontext  ·  édite la façade (géométrie gardée)")]
        out += [(k, _ie.label_for(k)) for k in _ie.edit_capable_engines()]
        return out
    return [(k, _ie.label_for(k)) for k in _ie.raster_engines()]


def _shot_ref_images(shot: dict, include_chars: bool = True,
                     include_decor: bool = True, include_props: bool = True,
                     include_vehicles: bool = True, include_hmc: bool = True) -> list:
    """Images de COHÉRENCE du plan : personnages, décor, accessoires, véhicules, HMC.

    Les accessoires, véhicules et HMC assignés au plan n'étaient PAS envoyés — seuls
    les portraits et le décor l'étaient — alors que le storyboard les référence et
    que la fenêtre de génération ne proposait même pas de les inclure (constat
    Matthieu 2026-07-25). Un accessoire qui a une fiche image doit se retrouver dans
    le Mood, sinon le moteur le réinvente à chaque plan.

    Ordre stable : personnages → décor → accessoires → véhicules → HMC. Chaque
    catégorie peut être exclue depuis la fenêtre « Générer les Moods »."""
    refs: list = []

    def _first_image(item: dict) -> str:
        """Première image utilisable d'une fiche, quel que soit son champ."""
        cands = [item.get("image_path"), item.get("sheet_path"),
                 item.get("portrait_path"), item.get("portrait")]
        cands += (item.get("generated_images") or [])[:1]
        for p in cands:
            if p and os.path.isfile(p):
                return p
        return ""

    if include_chars:
        try:
            import core.casting as cast
            for cid in (shot.get("character_ids") or []):
                p = _first_image(cast.get_character(cid) or {})
                if p:
                    refs.append(p)
        except Exception:
            pass
    if include_decor:
        try:
            import core.decors as dec
            did = shot.get("decor_id")
            if did:
                p = _first_image(dec.get_decor(did) or {})
                if p:
                    refs.append(p)
        except Exception:
            pass

    # Accessoires / véhicules / HMC : même mécanique, une entrée par module.
    for _flag, _mod_name, _getter, _ids_key in (
            (include_props,    "core.accessories", "get_accessory", "accessory_ids"),
            (include_vehicles, "core.vehicles",    "get_vehicle",   "vehicle_ids"),
            (include_hmc,      "core.hmc",         "get_hmc_item",  "hmc_ids")):
        if not _flag:
            continue
        try:
            _mod = __import__(_mod_name, fromlist=["_"])
            _get = getattr(_mod, _getter, None)
            if _get is None:
                continue
            for _iid in (shot.get(_ids_key) or []):
                p = _first_image(_get(_iid) or {})
                if p:
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

# Consigne dédiée aux images de RÉFÉRENCE ajoutées PAR PLAN (colonne « Référence » du
# storyboard). Sémantique OPPOSÉE à _MOOD_REF_DIRECTIVE : ce ne sont NI la pièce NI les
# personnages à reproduire, seulement une inspiration artistique lâche (ambiance, palette,
# lumière, composition). Miroir du rôle « reference » de la génération vidéo (api/real.py).
_INSPIRATION_REF_DIRECTIVE = (
    "ARTISTIC INSPIRATION — the artistic-inspiration reference image(s) provided are NOT "
    "the room and NOT the characters, and must NOT be reproduced or copied literally. Draw "
    "only LOOSE inspiration from them: overall mood, colour palette, lighting, texture and "
    "compositional energy. The actual scene, room and characters come from the prompt (and "
    "from the consistency references, if any) — never from these inspiration images."
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


def compose_mood_inputs(shot: dict, film_style: str = "",
                        building_ref: str = "", is_mapping=None) -> tuple:
    """(fiche, moment, kind, surface) — ce que le COMPOSITEUR doit voir.

    Point d'entrée PARTAGÉ par la fenêtre Mood et par le lot « Action → Générer
    les Moods » : deux constructions parallèles divergeraient, et l'utilisateur
    obtiendrait deux prompts différents pour le même plan selon le bouton
    cliqué — exactement ce qui est arrivé côté vidéo.

    Deux natures de fiche :

      · MAPPING — la barre ENTIÈRE, transformation et état d'arrivée compris. Le
        compositeur ne peut résoudre la contradiction « le STYLE décrit l'arrivée
        alors que l'instant demandé est le départ » que s'il VOIT les deux.
        L'instant à rendre lui est dit à part.

      · CINÉMA — l'intention structurée du plan (`mood_intent`), qui porte la
        valeur de plan, l'axe, la focale, la profondeur de champ et l'heure. La
        rendre en lignes nommées plutôt qu'en prose lui donne des champs à
        traiter, pas un bloc à deviner.
    """
    # `is_mapping` explicite quand l'appelant le sait mieux que nous : la fenêtre
    # Mood se fie au NAMESPACE de séquence, alors qu'ici on ne verrait que le
    # fichier de façade. Une séquence de mapping dont la photo n'est pas encore
    # configurée reste une séquence de mapping — sa barre a des états.
    if is_mapping is None:
        is_mapping = bool(building_ref and os.path.isfile(building_ref))

    if is_mapping:
        from core.prompt_sections import video_of as _video_of
        fiche = _video_of((shot.get("seedance_prompt") or "").strip())
        moment = ""
        try:
            from core.live_bar import parse_blocks
            _b = parse_blocks(fiche) or {}
            # L'état rendu est l'ARRIVÉE, pour tous les plans (décision
            # Matthieu 2026-07-28) — repli sur l'ouverture si la barre n'a pas
            # d'ÉTAT 1.
            if _b.get("state_1"):
                moment = ("The state to render is the FINAL state of the shot, "
                          "after the transformation has fully completed: "
                          + _b["state_1"])
            elif _b.get("state_0"):
                moment = ("The state to render is the OPENING state of the shot, "
                          "before any transformation: " + _b["state_0"])
        except Exception:
            pass
        surface = ""
        try:
            from core.live_building import describe_facade
            surface = describe_facade() or ""
        except Exception:
            surface = ""
        return fiche, moment, "mood_mapping", surface

    _intent = mood_intent(shot, film_style)
    _lignes = []
    for _cle, _lbl in (("subject", "SUJET"), ("action", "ACTION"),
                       ("setting", "DÉCOR"), ("camera", "CAMÉRA"),
                       ("lighting", "LUMIÈRE"), ("style", "STYLE")):
        _v = (_intent.get(_cle) or "").strip()
        if _v:
            _lignes.append(f"{_lbl} : {_v}")
    return "\n".join(_lignes), "", "mood", ""


def _ref_roles(shot: dict, building_ref: str = "", is_mapping=None) -> list:
    """Rôle de CHAQUE image jointe, dans l'ordre où `run_mood` les envoie.

    Le compositeur écrivait jusqu'ici comme s'il n'y avait que du texte : deux
    phrases pour Seedream, conformément à sa doc… face à deux images. Le modèle
    n'avait presque rien à rendre et recopiait ce qu'il voyait — l'image
    d'inspiration se retrouvait PLAQUÉE sur la façade au lieu de l'inspirer
    (constat Matthieu, 2026-07-27).

    ⚠ L'ordre doit suivre EXACTEMENT celui de `run_generation_nb2` et
    `run_generation_engine` : « Figure 1 » désigne une position, pas un rôle. Une
    liste décalée dirait au moteur que l'inspiration est le canevas.
    """
    if is_mapping is None:
        is_mapping = bool(building_ref and os.path.isfile(building_ref))
    _insp = [p for p in ((shot or {}).get("reference_images") or [])
             if p and os.path.isfile(p)]
    roles = []
    if is_mapping and building_ref and os.path.isfile(building_ref):
        roles.append("CANEVAS OBLIGATOIRE — la photo de la façade réelle. Sa "
                     "géométrie, son cadrage, son échelle et son point de vue "
                     "sont intouchables ; le contenu se projette DESSUS.")
    for _ in _insp:
        roles.append("INSPIRATION ARTISTIQUE seulement — palette, lumière, "
                     "matière, motifs. Ne jamais la recopier, ne jamais en "
                     "faire le sujet, ne jamais la coller sur la façade.")
    return roles


def _compose_cache_path(shot_id: str) -> str:
    """Le cache vit À CÔTÉ des moods du plan, pas en mémoire.

    Une composition est un aller-retour IA FACTURÉ. Le garder sur l'instance du
    dialogue le faisait mourir à la fermeture de la fenêtre : rouvrir le même
    plan sans rien changer repayait (constat Matthieu, 2026-07-27).
    """
    import core.storyboard as sb
    return os.path.join(sb.get_apercu_dir(shot_id), "prompt_cache.json")


def compose_cache_key(fiche: str, moment: str, surface: str, style: str,
                      engine: str, kind: str) -> str:
    """Empreinte des entrées. Une seule change → recomposition.

    C'est ce qui répond à « garder la composition tant que rien n'a bougé » : le
    prompt du storyboard entre dans la fiche, donc l'éditer change la clé. La
    CONSIGNE du compositeur est une entrée comme les autres (audit 2026-07-28) :
    un correctif de consigne recompose les plans déjà en cache — sans quoi il ne
    les atteindrait jamais.
    """
    import hashlib
    try:
        import api.image_prompt as _ip
        _rev = _ip.grammar_fingerprint()
    except Exception:
        _rev = ""
    _payload = " ".join(" ".join((x or "").split())
                             for x in (fiche, moment, surface, style, engine,
                                       kind, _rev))
    return hashlib.sha1(_payload.encode("utf-8")).hexdigest()


def _compose_cache_read(shot_id: str) -> dict:
    try:
        with open(_compose_cache_path(shot_id), encoding="utf-8") as f:
            _d = json.load(f)
        return _d if isinstance(_d, dict) else {}
    except Exception:
        return {}


def _compose_cache_write(shot_id: str, key: str, prompt: str, why: str):
    """Range la composition. Plafonné : un plan qu'on retravaille longtemps ne
    doit pas laisser grossir son cache indéfiniment."""
    try:
        _d = _compose_cache_read(shot_id)
        _d[key] = {"prompt": prompt, "why": why}
        if len(_d) > 12:
            for _old in list(_d)[:len(_d) - 12]:
                _d.pop(_old, None)
        _p = _compose_cache_path(shot_id)
        os.makedirs(os.path.dirname(_p), exist_ok=True)
        with open(_p, "w", encoding="utf-8") as f:
            json.dump(_d, f, ensure_ascii=False, indent=1)
    except Exception:
        pass


def compose_mood_prompt(shot: dict, film_style: str = "", engine: str = "",
                        building_ref: str = "", is_mapping=None,
                        force_fresh: bool = False) -> tuple:
    """(prompt, composé, raison, depuis_le_cache) — repli déterministe garanti.

    Le repli n'est pas une option de secours mais la moitié du contrat : sans clé,
    sans crédits ou sur un refus du contrôle, le Mood doit quand même partir —
    sur l'assemblage déterministe, exactement comme avant ce chantier.

    `force_fresh` (bouton « Réinitialiser ») : saute la LECTURE du cache —
    l'écriture reste. Un refus du contrôle y est mémorisé ; sans ce drapeau,
    « Réinitialiser » resservait la même erreur à l'identique, sans jamais
    redonner sa chance à l'IA (constat Matthieu 2026-07-28).
    """
    _repli = build_mood_prompt(shot, film_style, engine)
    _sid = (shot or {}).get("id", "")
    try:
        fiche, moment, kind, surface = compose_mood_inputs(
            shot, film_style, building_ref, is_mapping)
    except Exception as exc:
        return _repli, False, str(exc)[:200], False
    if not (fiche or "").strip():
        return _repli, False, "fiche vide", False

    _key = compose_cache_key(fiche, moment, surface, film_style, engine, kind)
    if _sid and not force_fresh:
        _hit = _compose_cache_read(_sid).get(_key)
        if isinstance(_hit, dict) and (_hit.get("prompt") or "").strip():
            _why = _hit.get("why") or ""
            return _hit["prompt"], (not _why), _why, True

    try:
        from core import ai_provider
        _ke = ai_provider.key_error(task="video_prompt")
        if _ke:
            # Pas de clé : rien à mémoriser, ça se corrige dans les Paramètres.
            return _repli, False, _ke, False
    except Exception:
        pass
    try:
        import api.image_prompt as _ip
        # `source_ref` = le repli déterministe, c'est-à-dire EXACTEMENT la
        # matière à rendre pour l'instant demandé. C'est la seule référence
        # honnête pour juger d'une perte : la fiche entière contient aussi ce
        # qu'on lui demande volontairement d'écarter.
        out = _ip.compose(fiche, engine=engine, kind=kind, moment=moment,
                          surface=surface, style_suffix=film_style,
                          refs=_ref_roles(shot, building_ref, is_mapping),
                          source_ref=_repli)
        if out:
            if _sid:
                _compose_cache_write(_sid, _key, out, "")
            return out, True, "", False
        # Global de module : le lire IMMÉDIATEMENT après le retour.
        _why = _ip.LAST_COMPOSE_ERROR or "composition refusée"
        # Un refus du CONTRÔLE est reproductible — inutile de le repayer. Un
        # incident réseau, non : il doit être retenté au passage suivant.
        try:
            if _sid and _ip.is_deterministic_refusal(_why):
                _compose_cache_write(_sid, _key, _repli, _why)
        except Exception:
            pass
        return _repli, False, _why, False
    except Exception as exc:
        return _repli, False, str(exc)[:200], False


def _res_enum_for(resolution: str) -> str:
    """Palier PANDORA → enum `resolution` fal.ai. « 1K » si le module manque.

    Isolé pour que les deux chemins de génération (Nano Banana natif et
    catalogue générique) traduisent le palier de la MÊME façon : deux
    conversions parallèles divergeraient au premier palier ajouté.
    """
    try:
        from core.image_resolution import nano_enum
        return nano_enum(resolution)
    except Exception:
        return "1K"


def run_generation_nb2(prompt: str, output_dir: str, api_key: str, progress_cb,
                       ref_images: list | None = None, floor_plan: str = "",
                       inspiration_refs: list | None = None, facade_ref: str = "",
                       engine_key: str = "nb2", resolution: str = "",
                       aspect_ratio: str = "") -> str:
    """Mood via la famille Nano Banana : édition avec réfs si disponibles, sinon
    génération texte. Aspect 16:9, comme le mood Flux.

    `resolution` : palier PANDORA (« 720p » … « 4k »), vide = défaut 1080p. Les
    Nano Banana couplent aspect_ratio + resolution (enum 1K/2K/4K) et rendent
    LEURS dimensions — mesuré le 2026-07-29 : 1368×768 pour un 16:9 en 1K,
    ratio 1,781 ≠ 16/9. L'image téléchargée est donc CONFORMÉE à la définition
    promise avant d'être rendue à l'appelant.

    `engine_key` : « nb2 » (défaut) ou « nb_pro » — mêmes consignes/args, seul
    l'endpoint change (Nano Banana 2 ↔ Nano Banana Pro). Nano Banana 2 Lite a un
    schéma d'args différent (anti-400) → routé par le chemin générique, pas ici.

    - `facade_ref` (MAPPING) : si fourni, la FAÇADE est le canvas (1ʳᵉ image) et NB2
      reçoit EXACTEMENT les mêmes consignes mapping que Flux (nuit, fond noir, visibilité
      pilotée par le prompt) ; les `inspiration_refs` enrichissent l'inspiration. Les
      familles cohérence/plan d'architecte (Cinéma) sont ignorées dans ce mode.
    - Sinon (CINÉMA), trois familles dans CET ordre (NB2 ne numérote pas les images →
      l'ordre + les consignes désignent chaque plage) :
      1. `ref_images`      : cohérence (portraits persos + image décor) → même pièce/persos ;
      2. `inspiration_refs`: images de RÉFÉRENCE du plan → inspiration lâche, jamais copiée ;
      3. `floor_plan`      : plan d'architecte vu de dessus, EN DERNIER."""
    import fal_client
    os.environ["FAL_KEY"] = api_key
    os.makedirs(output_dir, exist_ok=True)
    inspiration = [r for r in (inspiration_refs or []) if r and os.path.isfile(r)]
    _facade = facade_ref if (facade_ref and os.path.isfile(facade_ref)) else ""
    # Endpoints selon le moteur Nano Banana choisi (nb2 / nb_pro) — mêmes args.
    try:
        from core.image_engines import nano_endpoints as _ne
        _ep_text, _ep_edit = _ne(engine_key)
    except Exception:
        _ep_text, _ep_edit = "fal-ai/nano-banana-2", "fal-ai/nano-banana-2/edit"
    _res_enum = _res_enum_for(resolution)
    # Le Mood a toujours été en 16:9 : c'est le format de la vidéo qu'il alimente.
    # Il reste le défaut — un Mood dans un autre format que la génération vidéo
    # se ferait étirer, ce que tout ce chantier vient justement de supprimer.
    _ar = aspect_ratio or "16:9"

    if _facade:
        # ── MODE MAPPING : la FAÇADE est le canvas prioritaire (1ʳᵉ image) ; MÊMES
        # consignes que Flux (façade = base, réfs = inspiration lâche, nuit/fond noir).
        refs = [_facade] + inspiration[:_MAX_INSPIRATION_MAPPING]
        _tag = "façade" + (f" + {len(inspiration)} inspiration(s)" if inspiration else "")
        progress_cb(f"Nano Banana 2 — {_tag} (mapping)…")
        urls = [_upload_ref_robust(fal_client, r) for r in refs]
        directive = (_FACADE_PRIORITY_DIRECTIVE if inspiration else "") + _MAPPING_NIGHT_LOCK
        result = fal_client.subscribe(_ep_edit, arguments={
            "prompt": _avec_directive_en_tete(prompt, directive), "image_urls": urls,
            "num_images": 1, "aspect_ratio": _ar, "resolution": _res_enum,
            "output_format": "png", "safety_tolerance": "6",
        })
    else:
        # ── MODE CINÉMA : cohérence (persos/décor) + inspiration + plan d'architecte ──
        consistency = [r for r in (ref_images or []) if r and os.path.isfile(r)]
        _fp = floor_plan if (floor_plan and os.path.isfile(floor_plan)) else ""
        # Cap total 14 : le plan d'architecte garde toujours le dernier slot s'il est présent.
        _budget = 14 - (1 if _fp else 0)
        _ordered = (consistency + inspiration)[:_budget]
        n_cons = min(len(consistency), _budget)
        n_insp = max(0, len(_ordered) - n_cons)
        refs = _ordered + ([_fp] if _fp else [])
        if refs:
            _tags = []
            if n_cons: _tags.append("persos/décor")
            if n_insp: _tags.append("inspiration")
            if _fp:    _tags.append("plan d'architecte")
            progress_cb(f"Nano Banana 2 — {len(refs)} référence(s) (" + ", ".join(_tags) + ")…")
            urls = [_upload_ref_robust(fal_client, r) for r in refs]
            # Directives conditionnelles + préambule d'ORDRE seulement si plusieurs familles
            # coexistent (sinon prompt identique à l'existant → aucun changement de rendu).
            _parts = []
            if (1 if n_cons else 0) + (1 if n_insp else 0) + (1 if _fp else 0) > 1:
                _seg = []
                if n_cons: _seg.append(f"the first {n_cons} reference image(s) are for CONSISTENCY (room/characters)")
                if n_insp: _seg.append(f"the next {n_insp} are ARTISTIC INSPIRATION only")
                if _fp:    _seg.append("the LAST image is a top-down floor plan")
                _parts.append("IMAGE ORDER — " + "; ".join(_seg) + ".")
            if n_cons: _parts.append(_MOOD_REF_DIRECTIVE)
            if n_insp: _parts.append(_INSPIRATION_REF_DIRECTIVE)
            if _fp:    _parts.append(_FLOOR_PLAN_DIRECTIVE)
            directive = "\n\n".join(_parts)
            result = fal_client.subscribe(_ep_edit, arguments={
                "prompt": prompt + (("\n\n" + directive) if directive else ""), "image_urls": urls,
                "num_images": 1, "aspect_ratio": _ar, "resolution": _res_enum,
                "output_format": "png", "safety_tolerance": "6",
            })
        else:
            progress_cb("Nano Banana 2…")
            result = fal_client.subscribe(_ep_text, arguments={
                "prompt": prompt, "num_images": 1,
                "aspect_ratio": _ar, "resolution": _res_enum, "output_format": "png",
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
    return _conform_mood_definition(out, _ar, resolution)


# ── Génération mood GÉNÉRIQUE — n'importe quel moteur du catalogue ─────────────
# Tout moteur image de PANDORA (Recraft, Z-Image, Qwen, Ideogram, FLUX 1.1 Ultra,
# Seedream 5 Pro/Lite, GPT Image 2, FLUX.2…) via core/image_engines.build_request.
# Les moteurs qui savent éditer une image reçoivent les références disponibles
# (façade en mapping ; cohérence persos/décor + inspiration + plan d'architecte en
# Cinéma) ; ceux qui les ignorent génèrent depuis le prompt seul (+ style du film).

def run_generation_engine(engine_key: str, prompt: str, output_dir: str,
                          api_key: str, progress_cb,
                          ref_images: list | None = None, facade_ref: str = "",
                          inspiration_refs: list | None = None,
                          floor_plan: str = "", is_mapping: bool = False,
                          resolution: str = "", aspect_ratio: str = "") -> str:
    from core import image_engines as _ie
    os.makedirs(output_dir, exist_ok=True)
    label = _ie.short_label(engine_key)

    # ── Mock (pas de clé fal.ai) : vignette de simulation, comme le mood Flux ──
    if not api_key:
        import time
        progress_cb(f"Simulation {label} (pas de clé fal.ai)…")
        time.sleep(1.0)
        try:
            from PIL import Image, ImageDraw
            import random
            bg  = (random.randint(20, 50), random.randint(25, 55), random.randint(35, 70))
            img = Image.new("RGB", (896, 504), color=bg)
            d = ImageDraw.Draw(img)
            d.rectangle([0, 0, 895, 503], outline=(80, 80, 80), width=2)
            d.text((20, 20), f"MOOD — SIMULATION ({label})", fill=(200, 200, 200))
            d.text((20, 50), prompt[:120], fill=(140, 140, 140))
            out = os.path.join(output_dir, f"{uuid.uuid4().hex}.png")
            img.save(out, "PNG")
            return out
        except Exception:
            return ""

    import fal_client
    os.environ["FAL_KEY"] = api_key

    max_refs = _ie.ref_support(engine_key).get("max", 0)
    ref_paths, directive = [], ""

    if max_refs > 0:
        if is_mapping and facade_ref and os.path.isfile(facade_ref):
            insp = [r for r in (inspiration_refs or []) if r and os.path.isfile(r)]
            # Plafond d'INSPIRATIONS en mapping : chaque image ajoutée pèse dans
            # la balance face au texte. Seedream accepte dix références — dix
            # inspirations contre une façade et un prompt, c'est l'inspiration
            # qui gagne. Deux suffisent à donner une palette et une matière.
            ref_paths = [facade_ref] + insp[:_MAX_INSPIRATION_MAPPING]
            directive = (_FACADE_PRIORITY_DIRECTIVE if insp else "") + _MAPPING_NIGHT_LOCK
        else:
            cons = [r for r in (ref_images or []) if r and os.path.isfile(r)]
            insp = [r for r in (inspiration_refs or []) if r and os.path.isfile(r)]
            fp   = [floor_plan] if (floor_plan and os.path.isfile(floor_plan)) else []
            ref_paths = cons + insp + fp
            _parts = []
            if cons: _parts.append(_MOOD_REF_DIRECTIVE)
            if insp: _parts.append(_INSPIRATION_REF_DIRECTIVE)
            if fp:   _parts.append(_FLOOR_PLAN_DIRECTIVE)
            directive = "\n\n".join(_parts)
        ref_paths = ref_paths[:max_refs]
    elif is_mapping:
        # Moteur sans référence en mapping (le sélecteur filtre déjà, mais on
        # force au moins le rendu nocturne fond noir par sécurité).
        directive = _MAPPING_NIGHT_LOCK

    ref_urls    = [_upload_ref_robust(fal_client, p) for p in ref_paths]
    full_prompt = (_avec_directive_en_tete(prompt, directive) if is_mapping
                   else prompt + (("\n\n" + directive) if directive else ""))

    progress_cb(f"Génération du Mood via {label}"
                + (f" ({len(ref_urls)} réf.)" if ref_urls else "") + "…")
    endpoint, args, _kind = _ie.build_request(
        engine_key, full_prompt,
        _ie.ar_to_target(aspect_ratio or "16:9", resolution),
        _res_enum_for(resolution), ref_urls)
    result = fal_client.subscribe(endpoint, arguments=args)

    imgs = (result or {}).get("images") or []
    image_url = (imgs[0].get("url") if imgs and isinstance(imgs[0], dict)
                 else (imgs[0] if imgs else ""))
    if not image_url:
        raise RuntimeError(f"{label} : aucune image renvoyée")
    progress_cb("Téléchargement de l'image…")
    resp = requests.get(image_url, timeout=120)
    out = os.path.join(output_dir, f"{uuid.uuid4().hex}.png")
    with open(out, "wb") as f:
        f.write(resp.content)
    # Même les moteurs à dimensions explicites peuvent arrondir (multiples de
    # 32, plafonds de surface) : la promesse du sélecteur est tenue ICI.
    return _conform_mood_definition(out, aspect_ratio, resolution)


def run_mood(shot: dict, prompt: str, output_dir: str, api_key: str, progress_cb,
             building_ref: str = "", inspiration_ref: str = "",
             options: dict | None = None) -> str:
    """Dispatcher mood. `options["engine"]` = clé du catalogue image PANDORA
    (core/image_engines). Routage :
      - famille Nano Banana (nb2 / nb_pro) → chemin réglé (réfs persos/décor, façade
        mapping, plan d'architecte) ;
      - « flux » (héritage) → Flux Kontext (mapping) / t2i ;
      - tout autre moteur → chemin générique (build_request + réfs si le moteur les
        gère : Recraft/Z-Image/Qwen/Ideogram/FLUX Ultra/Seedream 5…).
    `options` aussi : chars / decor / floor_plan (réfs envoyées aux moteurs à réfs),
    et `resolution` (palier « 720p » … « 4k », vide = 1080p par défaut).

    Le palier voyage dans `options` plutôt qu'en paramètre nommé : c'est déjà le
    sac à dos des réglages de génération, et l'ajouter là évite de toucher les
    signatures des workers et de leurs appelants, Cinéma comme Live.
    """
    opts = options or {}
    _res = (opts.get("resolution") or "").strip()
    _ar  = (opts.get("aspect_ratio") or "").strip()
    engine = (opts.get("engine") or "").strip().lower()
    if not engine:
        engine = "nb2" if _is_cinema_mood() else "flux"
    _is_mapping = bool(building_ref and os.path.isfile(building_ref))

    # Images de RÉFÉRENCE du plan (colonne « Référence ») : inspiration auto au Mood.
    # « ◎ Mood inspiré d'une image » (inspiration_ref) passe en TÊTE, prioritaire.
    _inspo = [p for p in (shot.get("reference_images") or []) if p and os.path.isfile(p)]
    if inspiration_ref and os.path.isfile(inspiration_ref):
        _inspo = [inspiration_ref] + [p for p in _inspo if p != inspiration_ref]

    # Cohérence Cinéma (persos/décor) + plan d'architecte — utiles aux moteurs à réfs.
    def _consistency():
        return _shot_ref_images(shot,
                                include_chars=opts.get("chars", True),
                                include_decor=opts.get("decor", True),
                                include_props=opts.get("props", True),
                                include_vehicles=opts.get("vehicles", True),
                                include_hmc=opts.get("hmc", True))

    def _floor():
        if not opts.get("floor_plan", True):
            return ""
        try:
            from core.decors import floor_plan_for_shot
            return floor_plan_for_shot(shot) or ""
        except Exception:
            return ""

    # ── Famille Nano Banana (nb2 / nb_pro) : chemin réglé (réfs riches) ──────────
    if engine in ("nb2", "nb_pro"):
        if _is_mapping:
            return run_generation_nb2(prompt, output_dir, api_key, progress_cb,
                                      inspiration_refs=_inspo, facade_ref=building_ref,
                                      engine_key=engine, resolution=_res,
                                      aspect_ratio=_ar)
        return run_generation_nb2(prompt, output_dir, api_key, progress_cb,
                                  _consistency(), floor_plan=_floor(),
                                  inspiration_refs=_inspo, engine_key=engine,
                                  resolution=_res, aspect_ratio=_ar)

    # ── Flux héritage (Kontext mapping / t2i depuis le prompt) ──────────────────
    if engine == "flux":
        _insp = _inspo[0] if _inspo else ""
        return run_generation(prompt, output_dir, api_key, progress_cb, building_ref,
                              inspiration_ref=_insp, aspect_ratio=_ar,
                              resolution=_res)

    # ── Tout autre moteur du catalogue → chemin générique ───────────────────────
    return run_generation_engine(
        engine, prompt, output_dir, api_key, progress_cb,
        ref_images=_consistency(), facade_ref=building_ref,
        inspiration_refs=_inspo, floor_plan=_floor(), is_mapping=_is_mapping,
        resolution=_res, aspect_ratio=_ar)


# ── Worker unitaire ───────────────────────────────────────────────────────────

class MoodGenerationWorker(QThread):
    progress = pyqtSignal(str)
    finished = pyqtSignal(str)
    multi_finished = pyqtSignal(list)   # N > 1 — mêmes signaux que Nano Banana
    failed   = pyqtSignal(str)

    def __init__(self, shot: dict, output_dir: str, custom_prompt: str = "",
                 inspiration_ref: str = "", options: dict | None = None,
                 variations: int = 1):
        super().__init__()
        # Une variation = un appel. Aucun moteur du catalogue ne rend N moods en
        # un envoi (num_images vaut 1 partout dans ce fichier), donc on boucle.
        self._variations = max(1, int(variations or 1))
        self._shot          = shot
        self._out_dir       = output_dir
        self._custom_prompt = custom_prompt
        self._inspiration   = inspiration_ref
        self._options       = options or {}   # {"engine": "flux"|"nb2"} — choix du moteur
        from core.config import load_config
        import core.style as style_api
        self._api_key    = load_config().get("api_key", "").strip()
        self._film_style = style_api.get_image_suffix() or ""
        # Le namespace storyboard est un état GLOBAL de module, et un autre
        # onglet le déplace sans le restaurer. On le PHOTOGRAPHIE ici, sur le
        # thread UI où il est encore juste, pour le reposer dans run() : sans ça
        # `get_apercu_dir` écrit les moods sous la mauvaise séquence, et
        # `_resolve_building_ref` — qui exige EXACTEMENT « live_seq_mapping » —
        # renvoie "" , donc la façade n'est plus envoyée du tout et le moteur
        # invente le bâtiment. Un lot de N variations dure N fois plus longtemps,
        # donc laisse N fois plus d'occasions à la dérive de se produire.
        try:
            import core.storyboard as _sb0
            self._namespace = _sb0.get_namespace()
        except Exception:
            self._namespace = ""
        self._building_ref = _resolve_building_ref()

    def run(self):
        # Le namespace photographié à la construction est REPOSÉ ici : ce thread
        # ne doit dépendre d'aucun onglet ouvert entre-temps.
        try:
            import core.storyboard as _sb0
            if self._namespace and _sb0.get_namespace() != self._namespace:
                _sb0.set_namespace(self._namespace)
        except Exception:
            pass
        # WYSIWYG : si la fenêtre a fourni un prompt, c'est EXACTEMENT lui qui part
        # (il a déjà été écrit dans la grammaire du moteur choisi et montré à
        # l'écran). Sinon on le construit ici, pour le même moteur.
        prompt = (
            self._custom_prompt
            if self._custom_prompt
            else build_mood_prompt(self._shot, self._film_style,
                                   (self._options.get("engine") or "").strip())
        )
        n = self._variations
        paths, last_err = [], ""
        for k in range(n):
            if self.isInterruptionRequested():
                break
            try:
                def _prog(msg, _k=k):
                    self.progress.emit(f"[{_k + 1}/{n}] {msg}" if n > 1 else msg)

                path = run_mood(self._shot, prompt, self._out_dir, self._api_key,
                                _prog, self._building_ref,
                                inspiration_ref=self._inspiration,
                                options=self._options)
                if path:
                    paths.append(path)
            except Exception as e:
                # Un échec en cours de série ne doit pas jeter les variations
                # déjà obtenues : on retient la raison et on rend ce qu'on a.
                last_err = humanize_api_error(str(e))
        if not paths:
            self.failed.emit(last_err or "aucune variation générée")
        elif len(paths) == 1:
            self.finished.emit(paths[0])
        else:
            self.multi_finished.emit(paths)


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
        # Le namespace storyboard est un état GLOBAL de module, et un autre
        # onglet le déplace sans le restaurer. On le PHOTOGRAPHIE ici, sur le
        # thread UI où il est encore juste, pour le reposer dans run() : sans ça
        # `get_apercu_dir` écrit les moods sous la mauvaise séquence, et
        # `_resolve_building_ref` — qui exige EXACTEMENT « live_seq_mapping » —
        # renvoie "" , donc la façade n'est plus envoyée du tout et le moteur
        # invente le bâtiment. Un lot de N variations dure N fois plus longtemps,
        # donc laisse N fois plus d'occasions à la dérive de se produire.
        try:
            import core.storyboard as _sb0
            self._namespace = _sb0.get_namespace()
        except Exception:
            self._namespace = ""
        self._building_ref = _resolve_building_ref()

    def cancel(self):
        self._cancelled     = True
        self._was_cancelled = True

    def run(self):
        import core.storyboard as sb_api
        # Le namespace photographié à la construction est REPOSÉ ici : ce thread
        # ne doit dépendre d'aucun onglet ouvert entre-temps.
        try:
            import core.storyboard as _sb0
            if self._namespace and _sb0.get_namespace() != self._namespace:
                _sb0.set_namespace(self._namespace)
        except Exception:
            pass
        total = len(self._shots)
        try:
            _vars = max(1, int(self._options.get("variations") or 1))
        except (TypeError, ValueError):
            _vars = 1

        try:
            for i, shot in enumerate(self._shots):
                if self._cancelled:
                    return

                num   = shot.get("number", i + 1)
                title = (shot.get("scene_title") or f"Plan {num}").strip()
                self.shot_progress.emit(i + 1, total, f"Plan {num} — {title[:40]}")

                try:
                    # Composition IA du prompt final — UNE fois par plan, avant
                    # la boucle des variations : les variations partagent le même
                    # prompt, seul le tirage change. Composer par variation
                    # multiplierait la facture sans rien apporter.
                    _eng = (self._options.get("engine") or "").strip()
                    prompt, _compose_ok, _compose_why, _from_cache = \
                        compose_mood_prompt(shot, self._film_style, _eng,
                                            self._building_ref)
                    if _compose_why:
                        # Le repli doit se LIRE : un lot qui retombe en silence
                        # sur le prompt déterministe donne des rendus différents
                        # de ceux de la fenêtre Mood, sans que rien ne l'explique.
                        self.shot_progress.emit(
                            i + 1, total, f"⚠ {_compose_why[:70]}")
                    out_dir = sb_api.get_apercu_dir(shot["id"])

                    def _prog(msg, _i=i, _t=total):
                        self.shot_progress.emit(_i + 1, _t, msg)

                    # `shot_done` reste émis UNE fois par plan, avec la dernière
                    # variation : les pages s'en servent pour rafraîchir une
                    # vignette, pas pour compter. Multiplier l'émission
                    # fausserait leur décompte de plans traités.
                    last = ""
                    _idx_premiere = -1
                    for k in range(_vars):
                        if self._cancelled:
                            break

                        def _progv(msg, _i=i, _t=total, _k=k):
                            self.shot_progress.emit(
                                _i + 1, _t,
                                f"[variation {_k + 1}/{_vars}] {msg}" if _vars > 1 else msg)

                        path = run_mood(shot, prompt, out_dir, self._api_key,
                                        _progv, self._building_ref,
                                        options=self._options)
                        if path and os.path.isfile(path):
                            existing = sb_api.load_apercus(shot["id"])
                            paths    = [p for p in existing.get("paths", [])
                                        if os.path.isfile(p)]
                            paths.append(path)
                            if _idx_premiere < 0:
                                _idx_premiere = len(paths) - 1
                            # Le mood ACTIF est celui qui servira d'image de départ
                            # à la vidéo. Sur une série, il se posait sur la
                            # DERNIÈRE variation générée — donc sur un tirage
                            # aléatoire que personne n'avait regardé : quatre
                            # variations demandées, c'est la quatrième qui pilotait
                            # le rendu, bonne ou mauvaise. On garde la PREMIÈRE,
                            # comme le fait déjà la fenêtre Mood ; les autres sont
                            # là pour être comparées et choisies à l'œil.
                            sb_api.save_apercus(shot["id"], paths, _idx_premiere)
                            last = path

                    self.shot_done.emit(shot["id"], last)

                except Exception as e:
                    self.shot_failed.emit(shot["id"], str(e))

        finally:
            self.all_done.emit()
