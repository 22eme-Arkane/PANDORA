"""
API Seedance 2.0 via fal.ai — appel réel.

Endpoints confirmés :
  T2V  → bytedance/seedance-2.0/text-to-video
  I2V  → bytedance/seedance-2.0/image-to-video
  REF  → bytedance/seedance-2.0/reference-to-video
  EXT  → bytedance/seedance-2.0/reference-to-video  (via video_urls)

Fast : préfixe bytedance/seedance-2.0/fast/...

Auth : variable d'environnement FAL_KEY (lue automatiquement par fal_client)
       ou injectée depuis config.json.

Tarifs : ~$0.30/s (standard) · ~$0.24/s (fast) en 720p
"""

import os
import mimetypes as _mimetypes
import threading as _threading
from datetime import datetime


def _fal_upload(fal_client, path: str) -> str:
    """
    Upload a file to fal.ai.
    - Non-ASCII paths → bytes upload (avoids fal_client's internal ASCII codec error).
    - stdout/stderr are captured during the call to suppress fal_client's internal
      "Upload failed to fal_v3, falling back to cdn" retry warnings.
    """
    import sys, io
    _cap = io.StringIO()
    _old_out, _old_err = sys.stdout, sys.stderr
    sys.stdout = sys.stderr = _cap
    try:
        try:
            path.encode("ascii")
        except (UnicodeEncodeError, UnicodeDecodeError):
            ct = _mimetypes.guess_type(path)[0] or "application/octet-stream"
            with open(path, "rb") as _f:
                return fal_client.upload(_f.read(), content_type=ct)
        return fal_client.upload_file(path)
    finally:
        sys.stdout = _old_out
        sys.stderr = _old_err


def _analyze_style_ref(image_path: str, anthropic_key: str) -> str:
    """
    Uses Claude Haiku Vision to extract style descriptors from a reference image.
    Returns a short English string (10-15 words) to prepend to the video prompt,
    e.g. "photorealistic cinema, black and white, 35mm film grain, dramatic lighting".
    Returns "" on any error.
    """
    try:
        import base64
        import anthropic as _anthropic

        _ext = os.path.splitext(image_path)[1].lower()
        _mime_map = {
            ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
            ".png": "image/png",  ".webp": "image/webp",
        }
        _media_type = _mime_map.get(_ext, "image/jpeg")

        with open(image_path, "rb") as _f:
            _img_b64 = base64.standard_b64encode(_f.read()).decode("utf-8")

        _client = _anthropic.Anthropic(api_key=anthropic_key)
        _msg = _client.messages.create(
            model="claude-haiku-4-5",
            max_tokens=80,
            messages=[{
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": _media_type,
                            "data": _img_b64,
                        },
                    },
                    {
                        "type": "text",
                        "text": (
                            "Describe the visual style of this image in exactly 10-15 English words "
                            "as a video generation prompt prefix. "
                            "Include: rendering medium (photorealistic live-action / 3D CGI / 2D anime / "
                            "watercolor / oil painting / illustration / etc.), color treatment "
                            "(full color / black and white / sepia / monochrome), and film genre style "
                            "(cinematic / documentary / animation / fantasy / sci-fi / noir / etc.). "
                            "Output ONLY the style keywords comma-separated, no punctuation at end, "
                            "no explanation."
                        ),
                    },
                ],
            }],
        )
        return _msg.content[0].text.strip().rstrip(".")
    except Exception:
        return ""


def _analyze_draw_guidance(image_path: str, user_instruction: str, anthropic_key: str) -> str:
    """Draw-to-Video : Claude Haiku Vision lit une image annotée (traits colorés
    tracés par l'utilisateur pour REPÉRER des zones) + son instruction, et renvoie
    UNE instruction d'édition vidéo claire en anglais qui nomme les objets/zones
    marqués par leur position réelle, SANS mentionner les traits (qui ne sont JAMAIS
    envoyés au modèle vidéo → ils n'apparaissent pas). Retourne "" en cas d'erreur.
    """
    try:
        import base64
        import anthropic as _anthropic

        _ext = os.path.splitext(image_path)[1].lower()
        _mime_map = {
            ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
            ".png": "image/png",  ".webp": "image/webp",
        }
        _media_type = _mime_map.get(_ext, "image/png")
        with open(image_path, "rb") as _f:
            _img_b64 = base64.standard_b64encode(_f.read()).decode("utf-8")

        _client = _anthropic.Anthropic(api_key=anthropic_key)
        _msg = _client.messages.create(
            model="claude-haiku-4-5",
            max_tokens=300,
            messages=[{
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {"type": "base64", "media_type": _media_type, "data": _img_b64},
                    },
                    {
                        "type": "text",
                        "text": (
                            "A user drew colored marks (e.g. red strokes) on this video "
                            "frame to indicate WHERE to apply an edit. Their instruction "
                            f"(may be in French): \"{user_instruction}\".\n\n"
                            "Rewrite their instruction as ONE precise, self-contained "
                            "English video-editing prompt that:\n"
                            "- names the exact objects/regions the marks cover, using their "
                            "real position in the frame (e.g. 'the two white plates on the "
                            "center-right of the table'), or — if the user sketched a new "
                            "element — describes that element and where to place it;\n"
                            "- does NOT mention the marks, strokes, drawings or their colors "
                            "(they will NOT be visible to the video model and must not appear);\n"
                            "- keeps the rest of the scene unchanged.\n"
                            "Output ONLY the rewritten instruction, no preamble."
                        ),
                    },
                ],
            }],
        )
        return _msg.content[0].text.strip()
    except Exception:
        return ""


def run_real(params: dict, emit_progress, is_cancelled) -> dict:
    import fal_client

    # Injecte la clé API dans l'environnement si présente dans la config
    from core.config import load_config
    api_key = load_config().get("api_key", "").strip()
    if api_key:
        os.environ["FAL_KEY"] = api_key

    mode  = params.get("mode", "t2v")
    model = params.get("model", "seedance-2.0")
    fast  = "fast" in model.lower()
    base  = "bytedance/seedance-2.0/fast" if fast else "bytedance/seedance-2.0"

    # ── Endpoints ─────────────────────────────────────────────────────────────
    endpoints = {
        "t2v": f"{base}/text-to-video",
        "i2v": f"{base}/image-to-video",
        "ref": f"{base}/reference-to-video",
        "ext": f"{base}/reference-to-video",
    }
    endpoint = endpoints.get(mode, endpoints["t2v"])

    # Auto-switch to ref endpoint when reference images are provided for t2v
    _raw_ref_images = params.get("ref_images", [])
    _raw_ref_roles  = params.get("ref_image_roles", [])
    # Filter valid paths while keeping roles aligned
    ref_images: list[str] = []
    ref_roles:  list[str] = []
    for _p, _r in zip(_raw_ref_images, _raw_ref_roles + [""] * len(_raw_ref_images)):
        if _p and os.path.isfile(_p):
            ref_images.append(_p)
            ref_roles.append(_r)
    # Paths without a role entry (shouldn't happen but safety net)
    for _p in _raw_ref_images[len(_raw_ref_roles):]:
        if _p and os.path.isfile(_p):
            ref_images.append(_p)
            ref_roles.append("")
    # Seedance reference-to-video accepte jusqu'à 9 images (image_urls). On passe de
    # 4 à 9 pour laisser la place aux images de RÉFÉRENCE (inspiration) par plan, en
    # plus des mosaïques (personnages/décor/accessoires) + style + mood.
    ref_images = ref_images[:9]
    ref_roles  = ref_roles[:9]

    # ── Clip source : transcodage H.264 automatique si nécessaire ───────────────
    # (MXF/ProRes/HEVC → H.264 ; > 1080p → downscale lanczos ; RÉELLEMENT
    # entrelacée → yadif). No-op TOTAL si déjà mp4/H.264 yuv420p progressif
    # ≤ 1080p, ou si ffmpeg est absent — jamais de ré-encodage inutile.
    _vp = params.get("video_path", "")
    if _vp and os.path.isfile(_vp):
        try:
            from core.video_utils import ensure_engine_video
            _vp2 = ensure_engine_video(_vp, emit=lambda m: emit_progress(2, m))
            if _vp2 and _vp2 != _vp:
                params = dict(params)
                params["video_path"] = _vp2
        except Exception:
            pass

    _auto_ref = mode == "t2v" and bool(ref_images)  # track auto-switch to restore on upload failure
    if _auto_ref:
        mode = "ref"
        endpoint = endpoints["ref"]

    _ref_images_sent      = 0   # count of successfully uploaded reference images
    # Compteur d'alerte UI : rempli UNIQUEMENT par le mode "ref", le seul qui
    # consomme ref_images. En i2v (keyframes mapping) la liste est ignorée —
    # compter ici déclenchait une fausse alerte « non transmises » alors que
    # les images i2v partent par image_url/end_image_url.
    _ref_images_attempted = 0
    _gcs_blocked          = False  # set True if ALL uploads fail (no images transmitted)
    _gcs_error_detail     = ""    # first upload error message for diagnostics

    # ── Arguments communs ─────────────────────────────────────────────────────
    duration = params.get("duration", 10)
    # Seedance API requires duration as a string in ['auto','4'..'15'] — minimum 4 s
    try:
        _dur_int = max(4, min(15, int(duration)))
    except (TypeError, ValueError):
        _dur_int = 10
    duration = _dur_int  # keep as int for result dict

    # Traduit le prompt utilisateur vers l'anglais si nécessaire
    from core.lang import translate_to_english
    from core.config import load_config as _lc
    _cfg           = _lc()
    _has_anthropic = bool(_cfg.get("anthropic_key", "").strip())
    _anthropic_key = _cfg.get("anthropic_key", "").strip()
    _raw_prompt = params.get("prompt", "")
    # Prompt structuré en sections : le bloc [SOUND DESIGN] n'est PAS envoyé au
    # modèle vidéo (séparation image/son). Les autres sections sont conservées.
    try:
        from core.prompt_sections import strip_for_video as _strip_sound_section
        _raw_prompt = _strip_sound_section(_raw_prompt)
    except Exception:
        pass
    # Draw-to-Video : si une image annotée (traits de repérage) est fournie, Claude
    # Vision la lit pour RÉÉCRIRE l'instruction en décrivant les zones/objets marqués
    # SANS les traits. L'image annotée n'est JAMAIS envoyée à Seedance → les traits
    # n'apparaissent pas ; seul le clip d'origine + ce prompt partent.
    _draw_guidance = params.get("draw_guidance_path", "")
    if _draw_guidance and os.path.isfile(_draw_guidance) and _anthropic_key:
        emit_progress(4, "Analyse du dessin (repérage des zones)…")
        _drawn = _analyze_draw_guidance(_draw_guidance, _raw_prompt, _anthropic_key)
        if _drawn:
            _raw_prompt = _drawn
    if _raw_prompt and not _has_anthropic:
        emit_progress(3, "⚠ Clé Anthropic manquante — prompt envoyé sans traduction")
    else:
        emit_progress(3, "Traduction du prompt…")
    _prompt_en = translate_to_english(_raw_prompt) if _raw_prompt else ""
    # Compress very long prompts via Mandarin (3× more compact than English)
    if len(_prompt_en) > 2000:
        from core.lang import translate_to_chinese
        emit_progress(4, "Prompt long — compression en mandarin…")
        _prompt_zh = translate_to_chinese(_prompt_en)
        if _prompt_zh and len(_prompt_zh) < len(_prompt_en):
            _prompt_en = _prompt_zh

    # Langue des dialogues (colonne « Langues » du storyboard) : à l'ENVOI
    # uniquement, on traduit les dialogues entre guillemets vers la langue
    # choisie pour ce plan (par défaut anglais). Le prompt à l'écran reste tel quel.
    _dialogue_lang = (params.get("dialogue_lang", "en") or "en")
    # ' n'est un guillemet de dialogue que détaché des lettres (pas « It's »).
    import re as _re
    _has_quotes = (any(q in _prompt_en for q in ('"', "«", "“", "‘"))
                   or bool(_re.search(r"(?<![A-Za-zÀ-ÿ])'[^']{1,300}'(?![A-Za-zÀ-ÿ])",
                                      _prompt_en)))
    if _prompt_en and _has_anthropic and _has_quotes:
        from core.lang import translate_dialogues_to
        emit_progress(5, "Traduction des dialogues…")
        _prompt_en = translate_dialogues_to(_prompt_en, _dialogue_lang)

    # ── Vision analysis of style reference image ───────────────────────────────
    # Claude Haiku reads the style image and extracts visual style keywords
    # (e.g. "photorealistic cinema, black and white, 35mm film grain").
    # These are PREPENDED to the prompt so Seedance reads them first — the
    # highest-attention position, before the user's scene description.
    _style_ref_for_vision = next(
        (p for p, r in zip(ref_images, ref_roles) if r == "style"), ""
    )
    if _style_ref_for_vision and _anthropic_key:
        emit_progress(4, "Analyse de l'image de style…")
        _vision_style = _analyze_style_ref(_style_ref_for_vision, _anthropic_key)
        if _vision_style:
            _prompt_en = f"{_vision_style}, {_prompt_en}" if _prompt_en else _vision_style

    # Lighting constraint — prepended so Seedance reads it first (highest attention weight)
    _time_suffix = params.get("time_suffix", "")
    if _time_suffix and _prompt_en:
        _prompt_en = f"{_time_suffix}, {_prompt_en}"

    # Append style + audio suffixes after translation so exact English keywords are preserved
    _style_suffix = params.get("style_suffix", "")
    if _style_suffix and _prompt_en:
        _prompt_en = f"{_prompt_en}, {_style_suffix}"
    _no_music_suffix = params.get("no_music_suffix", "")
    if _no_music_suffix and _prompt_en:
        _prompt_en = f"{_prompt_en}, {_no_music_suffix}"
    # Character consistency — appended after translation to preserve exact Seedance keywords
    _char_suffix = params.get("char_consistency_suffix", "")
    if _char_suffix and _prompt_en:
        _prompt_en = f"{_prompt_en}, {_char_suffix}"
    # Creative controls — appended last so they override any conflicting phrasing above
    _creative_suffix = params.get("creative_suffix", "")
    if _creative_suffix and _prompt_en:
        _prompt_en = f"{_prompt_en}, {_creative_suffix}"

    _raw_res = params.get("resolution", "720p") or "720p"
    _res_clean = _raw_res.split()[0]  # strip price label: "720p (~$0.30/s)" → "720p"

    args = {
        "prompt":           _prompt_en,
        "resolution":       _res_clean,
        "duration":         str(_dur_int),
        "aspect_ratio":     params.get("aspect_ratio", "16:9"),
        "generate_audio":   params.get("audio", True),
        "safety_tolerance": params.get("safety_tolerance_override", "6"),
    }
    if params.get("seed"):
        args["seed"] = params["seed"]

    # ── Upload fichiers locaux → CDN fal.ai ───────────────────────────────────
    emit_progress(5, "Upload des fichiers vers fal.ai…")

    if mode == "i2v":
        path = params.get("image_path", "")
        if path and os.path.isfile(path):
            try:
                emit_progress(8, f"Upload image : {os.path.basename(path)}…")
                args["image_url"] = _fal_upload(fal_client,path)
            except Exception as _e:
                _e_str = str(_e)
                if "gcs" in _e_str.lower() or "storage target" in _e_str.lower():
                    # Fallback bytes bruts
                    try:
                        import mimetypes
                        _ct = mimetypes.guess_type(path)[0] or "image/png"
                        with open(path, "rb") as _f:
                            args["image_url"] = fal_client.upload(_f.read(), content_type=_ct)
                    except Exception:
                        _gcs_blocked = True
                        mode = "t2v"
                        endpoint = endpoints["t2v"]
                        emit_progress(9, "⚠ Image non uploadée (erreur stockage) — passage en mode texte seul")
                else:
                    mode = "t2v"
                    endpoint = endpoints["t2v"]
                    emit_progress(9, "⚠ Upload image échoué — passage en mode texte seul")
        if mode == "i2v":  # only if upload succeeded
            end_path = params.get("end_image_path", "")
            if end_path and os.path.isfile(end_path):
                try:
                    args["end_image_url"] = _fal_upload(fal_client,end_path)
                except Exception:
                    pass

    elif mode == "ref":
        _ref_images_attempted = len(ref_images)
        image_path = params.get("image_path", "")
        video_path = params.get("video_path", "")
        audio_path = params.get("audio_path", "")
        _style_ref_path_param = params.get("style_ref_path", "")

        # ── Build ordered upload list ─────────────────────────────────────────────
        # Upload order (strict priority for @ImageN weight):
        #   1. style ref  → always @Image1, regardless of other images present
        #   2. i2v frame  → continuity/first-frame image (if any)
        #   3. other refs → characters, decor, accessories
        _paired = list(zip(ref_images, ref_roles))
        _style_pairs   = [(p, r) for p, r in _paired if r == "style"]
        _content_pairs = [(p, r) for p, r in _paired if r != "style"]
        _i2v_pair      = [(image_path, "i2v")] if image_path and os.path.isfile(image_path) else []
        # style FIRST → i2v frame → content refs
        _upload_queue  = _style_pairs + _i2v_pair + _content_pairs

        # Upload all in order; track positions for @ImageN injection
        uploaded_urls:  list[str] = []
        uploaded_roles: list[str] = []

        def _try_upload(path: str, role: str, progress_n: int):
            """Upload one file; GCS fallback on error. Appends to uploaded_urls/roles."""
            nonlocal _gcs_error_detail
            try:
                emit_progress(progress_n, f"Upload {role} : {os.path.basename(path)}…")
                uploaded_urls.append(_fal_upload(fal_client, path))
                uploaded_roles.append(role)
            except Exception as _ue:
                _ue_str = str(_ue)
                if "gcs" in _ue_str.lower() or "storage target" in _ue_str.lower():
                    try:
                        _ct = _mimetypes.guess_type(path)[0] or "image/png"
                        with open(path, "rb") as _f:
                            uploaded_urls.append(fal_client.upload(_f.read(), content_type=_ct))
                        uploaded_roles.append(role)
                    except Exception as _fb:
                        _gcs_error_detail = _gcs_error_detail or f"GCS + fallback échoués : {_fb}"
                else:
                    _gcs_error_detail = _gcs_error_detail or _ue_str

        for _pp, _pr in _upload_queue:
            if len(uploaded_urls) >= 9:
                break
            _try_upload(_pp, _pr, 7 + len(uploaded_urls))

        _ref_images_sent = len(uploaded_urls)
        if _ref_images_sent == 0 and _ref_images_attempted > 0:
            _gcs_blocked = True

        if uploaded_urls:
            args["image_urls"] = uploaded_urls
            # Build @ImageN mentions with role-appropriate instructions
            # Style ref gets a dominant instruction; content images get context-only cues.
            _prompt_additions: list[str] = []
            for _idx, _role in enumerate(uploaded_roles, start=1):
                if _role == "style":
                    _prompt_additions.append(
                        f"STYLE REFERENCE @Image{_idx}: Replicate its rendering medium "
                        f"(photorealistic / animated / illustrated / etc.), color treatment, "
                        f"film grain, color grade and cinematographic aesthetic across the ENTIRE "
                        f"video. Override any default 3D CGI look — use exactly the visual medium "
                        f"and artistic style shown in @Image{_idx}. This is the top-priority style directive."
                    )
                elif _role == "character":
                    _prompt_additions.append(
                        f"@Image{_idx} shows the characters — "
                        f"match their face, skin tone, hair and clothing exactly, "
                        f"reinterpreted in the film's visual style."
                    )
                elif _role == "decor":
                    if params.get("decor_ref_free", False):
                        _prompt_additions.append(
                            f"VISUAL ATMOSPHERE @Image{_idx}: Draw inspiration from the mood, "
                            f"color palette, and aesthetic of this location — but reinterpret "
                            f"the space freely. Do not replicate the exact architecture or layout. "
                            f"Use the image as a stylistic reference only."
                        )
                    else:
                        _prompt_additions.append(
                            f"FILMING LOCATION @Image{_idx}: This is the physical space the camera "
                            f"moves through — NOT a static backdrop or background plate. "
                            f"The camera explores this environment freely: tracking shots, pans, "
                            f"depth reveals, different angles and viewpoints within the space. "
                            f"Preserve the architectural character and atmosphere of the location "
                            f"while showing it from multiple perspectives."
                        )
                elif _role == "accessory":
                    _prompt_additions.append(
                        f"@Image{_idx} shows props and accessories — "
                        f"include them in the scene reinterpreted in the film's visual style."
                    )
                elif _role == "mood":
                    _prompt_additions.append(
                        f"MOOD / LOOK REFERENCE @Image{_idx}: This is the VALIDATED mood "
                        f"frame for this exact shot. Match its composition, framing, camera "
                        f"angle, subject placement, lighting and color grade as closely as "
                        f"possible — animate this precise image into motion. Highest-priority "
                        f"directive for visual cohesion with the planned shot."
                    )
                elif _role == "reference":
                    _prompt_additions.append(
                        f"INSPIRATION REFERENCE @Image{_idx}: Loosely draw inspiration from "
                        f"this image — its atmosphere, mood, composition, shapes and overall "
                        f"design language. Do NOT copy it literally, do NOT reproduce it "
                        f"exactly; reinterpret its spirit freely within this shot's own action, "
                        f"framing and visual style."
                    )

            if _prompt_additions:
                args["prompt"] = args["prompt"] + ". " + " ".join(_prompt_additions)
        elif _auto_ref:
            mode = "t2v"
            endpoint = endpoints["t2v"]
        if not _auto_ref:
            if video_path and os.path.isfile(video_path):
                try:
                    emit_progress(12, f"Upload vidéo : {os.path.basename(video_path)}…")
                    args["video_urls"] = [_fal_upload(fal_client, video_path)]
                except Exception:
                    pass
            if audio_path and os.path.isfile(audio_path):
                try:
                    emit_progress(14, f"Upload audio : {os.path.basename(audio_path)}…")
                    args["audio_urls"] = [_fal_upload(fal_client, audio_path)]
                except Exception:
                    pass

    elif mode == "ext":
        video_path = params.get("video_path", "")
        direction  = params.get("direction", "after")
        ext_refs   = [p for p in params.get("ref_images", []) if p and os.path.isfile(p)][:3]

        endpoint = f"{base}/reference-to-video"

        _video_upload_ok = False
        if direction == "new_take":
            if video_path and os.path.isfile(video_path):
                try:
                    emit_progress(8, f"Upload clip référence : {os.path.basename(video_path)}…")
                    args["video_urls"] = [_fal_upload(fal_client, video_path)]
                    _video_upload_ok = True
                except Exception as _vu:
                    _vu_str = str(_vu)
                    if "gcs" in _vu_str.lower() or "storage target" in _vu_str.lower():
                        try:
                            _ct = _mimetypes.guess_type(video_path)[0] or "video/mp4"
                            with open(video_path, "rb") as _vf:
                                args["video_urls"] = [fal_client.upload(_vf.read(), content_type=_ct)]
                            _video_upload_ok = True
                        except Exception as _fb:
                            emit_progress(9, f"⚠ Upload clip échoué ({_fb}) — génération sans référence vidéo")
                    else:
                        emit_progress(9, f"⚠ Upload clip échoué ({_vu_str[:60]}) — génération sans référence vidéo")
            else:
                emit_progress(8, "⚠ Fichier clip introuvable — génération sans référence vidéo")
        else:
            if video_path and os.path.isfile(video_path):
                try:
                    emit_progress(8, f"Upload clip : {os.path.basename(video_path)}…")
                    args["video_urls"] = [_fal_upload(fal_client, video_path)]
                    _video_upload_ok = True
                except Exception as _vu:
                    _vu_str = str(_vu)
                    if "gcs" in _vu_str.lower() or "storage target" in _vu_str.lower():
                        try:
                            _ct = _mimetypes.guess_type(video_path)[0] or "video/mp4"
                            with open(video_path, "rb") as _vf:
                                args["video_urls"] = [fal_client.upload(_vf.read(), content_type=_ct)]
                            _video_upload_ok = True
                        except Exception as _fb:
                            emit_progress(9, f"⚠ Upload clip échoué ({_fb}) — génération sans référence vidéo")
                    else:
                        emit_progress(9, f"⚠ Upload clip échoué ({_vu_str[:60]}) — génération sans référence vidéo")
            args.pop("video_url", None)
            if direction == "before":
                hint = "Extend the beginning of this scene:"
            else:
                hint = "Seamlessly continue this scene after the last frame:"
            args["prompt"] = f"{hint} {args['prompt']}".strip() if args.get("prompt") else hint

        # Images de référence supplémentaires (photo acteur, style…)
        if ext_refs:
            uploaded_refs = []
            for i, p in enumerate(ext_refs):
                try:
                    emit_progress(9 + i, f"Upload image de référence {i + 1}/{len(ext_refs)}…")
                    uploaded_refs.append(_fal_upload(fal_client, p))
                except Exception:
                    pass
            if uploaded_refs:
                args["image_urls"] = uploaded_refs

    # ── Appel API avec callbacks de progression ───────────────────────────────
    emit_progress(12, "Envoi à l'API Seedance 2.0…")
    _pct = [12]

    # Ticker : incrémente doucement la barre pendant l'attente serveur (Seedance
    # ne renvoie des logs qu'en fin de génération — sans ça la barre reste figée).
    _api_done = _threading.Event()
    _TICK_MSGS = [
        "Génération en cours…",
        "Rendu vidéo…",
        "Synthèse du clip…",
        "Génération en cours…",
    ]

    def _ticker():
        _i = 0
        while not _api_done.wait(timeout=9):
            if is_cancelled():
                break
            if _pct[0] < 88:
                _pct[0] = min(_pct[0] + 2, 88)
            emit_progress(_pct[0], _TICK_MSGS[_i % len(_TICK_MSGS)])
            _i += 1

    _tick_thread = _threading.Thread(target=_ticker, daemon=True)
    _tick_thread.start()

    def on_queue_update(update):
        if is_cancelled():
            return
        if isinstance(update, fal_client.InProgress):
            for log in update.logs:
                msg = log.get("message", "")
                _pct[0] = min(_pct[0] + 7, 92)
                emit_progress(_pct[0], msg or "Génération en cours…")

    try:
        result = fal_client.subscribe(
            endpoint,
            arguments=args,
            with_logs=True,
            on_queue_update=on_queue_update,
        )
    except Exception as e:
        _api_done.set()
        err = str(e)
        if "content_policy_violation" in err or "sensitive content" in err:
            raise RuntimeError(
                "Prompt refusé par Seedance (contenu sensible).\n\n"
                "Le modèle a détecté du contenu violent, explicite ou contraire\n"
                "à la politique de ByteDance/fal.ai.\n\n"
                "Astuces :\n"
                "• Reformule ton prompt pour supprimer les éléments bloquants.\n"
                "• Si le problème vient d'une image de visage (célébrité, droits d'auteur) :\n"
                "  remplace-la par un plan corps entier — le visage occupe\n"
                "  moins de pixels et passe plus facilement la censure.\n"
                "• Essaie en mode Standard plutôt que Fast."
            )
        raise
    finally:
        _api_done.set()

    if is_cancelled():
        return {}

    emit_progress(98, "Finalisation…")

    return {
        "request_id":            result.get("request_id", ""),
        "video_url":             result.get("video", {}).get("url", ""),
        "duration":              duration,
        "resolution":            params.get("resolution", "720p"),
        "model":                 model,
        "prompt":                params.get("prompt", ""),
        "mode":                  mode,
        "generated_at":          datetime.now().isoformat(),
        "credits_used":          0,
        "seed":                  result.get("seed", 0),
        "ref_images_attempted":  _ref_images_attempted,
        "ref_images_sent":       _ref_images_sent,
        "gcs_blocked":           _gcs_blocked,
        "gcs_error_detail":      _gcs_error_detail,
    }
