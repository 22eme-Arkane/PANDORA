"""Per-project visual style configuration."""

import json
import os
import sys

from core.paths import APP_ROOT as _ROOT
_STYLES_FILE = os.path.join(_ROOT, "data", "project_styles.json")

# ── Group catalogue ───────────────────────────────────────────────────────────

GROUPS = [
    {"key": "cinema",    "name": "Cinéma",            "icon": "🎬"},
    {"key": "animation", "name": "Animation",          "icon": "✏"},
    {"key": "arts",      "name": "Arts & Esthétiques", "icon": "🎨"},
    {"key": "hybride",   "name": "Hybride",            "icon": "∞"},
]

# ── Style catalogue ───────────────────────────────────────────────────────────

STYLES = [

    # ── CINÉMA ────────────────────────────────────────────────────────────────
    {
        "key":             "realistic",
        "group":           "cinema",
        "name":            "Film réaliste",
        "icon":            "🎬",
        "description":     "Acteurs réels, photographie cinématographique naturaliste — ARRI Alexa, lumière naturelle",
        "image_suffix":    "Shot on Arri Alexa 65, 35mm prime, naturalistic lighting, subtle color grading, realistic textures, highly grounded",
        "image_suffix_no_cam": "Naturalistic lighting, subtle color grading, realistic textures, highly grounded",
        "video_suffix":        "shot on ARRI Alexa 35mm, 35mm film photography, photorealistic live action footage, real human actors and real faces, authentic film grain, natural skin texture and pores, no CGI, no 3D render, no computer animation, no synthetic rendering, no digital art, organic depth of field, natural practical lighting, true-to-life skin tones, live action cinema",
        "video_suffix_no_cam": "photorealistic live action footage, real human actors and real faces, authentic film grain, natural skin texture and pores, no CGI, no 3D render, no computer animation, no synthetic rendering, no digital art, organic depth of field, natural practical lighting, true-to-life skin tones, live action cinema",
        "color":        "#4ecdc4",
    },
    {
        "key":          "documentary",
        "group":        "cinema",
        "name":         "Documentaire",
        "icon":         "📹",
        "description":  "Style journalistique, lumière naturelle, caméra à l'épaule",
        "image_suffix": "ENG style footage, handheld camera, run-and-gun lighting, raw uncolorized look, 16mm film grain, direct cinema",
        "video_suffix": "documentary film style, handheld camera, natural lighting, journalistic footage, observational cinema verité",
        "color":        "#f7b731",
    },
    {
        "key":          "social_drama",
        "group":        "cinema",
        "name":         "Drame social",
        "icon":         "🏭",
        "description":  "Réalisme social, lumière froide naturelle, Ken Loach / Dardenne Brothers",
        "image_suffix":    "Desaturated palette, gritty realism, overcast natural lighting, shallow depth of field, Cooke S4 lenses, muted tones",
        "image_suffix_no_cam": "Desaturated palette, gritty realism, overcast natural lighting, shallow depth of field, muted tones",
        "video_suffix": "social drama film, cold natural interior lighting, handheld observational camera, raw authentic performances, Ken Loach Dardenne Brothers style, no glamour no filters, muted desaturated realism, working class environments",
        "color":        "#636e72",
    },
    {
        "key":          "noir",
        "group":        "cinema",
        "name":         "Film noir",
        "icon":         "🕵",
        "description":  "Noir et blanc, ombres dramatiques, atmosphère néo-noir",
        "image_suffix": "High contrast black and white, deep shadows, chiaroscuro lighting, hard key light, practical rim lights, 1940s cinematic",
        "video_suffix": "film noir style, black and white, dramatic chiaroscuro shadows, high contrast, neo-noir atmosphere, venetian blind light patterns, moody",
        "color":        "#8395a7",
    },
    {
        "key":          "thriller",
        "group":        "cinema",
        "name":         "Thriller",
        "icon":         "🔪",
        "description":  "Palette froide désaturée, tension psychologique, Fincher",
        "image_suffix": "Cool color temperature, low key lighting, anamorphic lens flares, tense atmosphere, deep shadows, teal and orange grading",
        "video_suffix": "psychological thriller, cold teal-gray desaturated palette, David Fincher precision, clinical tension, controlled shadows, slow dread, no warmth",
        "color":        "#5f6caf",
    },
    {
        "key":          "horror",
        "group":        "cinema",
        "name":         "Horreur",
        "icon":         "👁",
        "description":  "Atmosphère sombre et oppressante, tension, effets pratiques",
        "image_suffix": "Underexposed, harsh shadows, unsettling Dutch angles, high contrast, muted colors, prominent film grain, macabre",
        "video_suffix": "horror film style, dark oppressive atmosphere, tension and dread, unsettling visuals, practical effects, deep shadows, no comfort",
        "color":        "#ff4757",
    },
    {
        "key":          "western",
        "group":        "cinema",
        "name":         "Western",
        "icon":         "🤠",
        "description":  "Grand désert américain, lumière dure, Sergio Leone — gros plans intenses",
        "image_suffix": "Warm golden hour lighting, harsh sunlight, sepia-toned grading, anamorphic widescreen, dusty atmosphere, deep focus",
        "video_suffix": "Western film, vast desert plains and dusty frontier towns, harsh noon sunlight, extreme close-ups on eyes and hands, Sergio Leone cinematography, warm amber and ochre palette, tense standoff atmosphere, wide establishing shots of landscapes",
        "color":        "#e17055",
    },
    {
        "key":          "war",
        "group":        "cinema",
        "name":         "Guerre",
        "icon":         "⚔",
        "description":  "Champ de bataille désaturé, caméra portée, Saving Private Ryan / Dunkirk",
        "image_suffix": "Bleach bypass look, desaturated greens and browns, handheld shaky cam, high shutter speed, gritty textures, atmospheric smoke",
        "video_suffix": "war film cinematography, desaturated battlefield footage, smoke and dust in air, handheld shaky camera, Saving Private Ryan realism, muted olive grey palette, chaos and tension, documentary urgency, no glamour",
        "color":        "#6d7d8b",
    },
    {
        "key":          "action",
        "group":        "cinema",
        "name":         "Film d'action",
        "icon":         "💥",
        "description":  "Caméra dynamique, coupes rapides, effets pratiques, Christopher Nolan / Michael Bay",
        "image_suffix": "High contrast, saturated colors, kinetic camera movement, sharp focus, dynamic motion blur, blockbuster grading",
        "video_suffix": "action film cinematography, fast dynamic cuts, kinetic handheld camera, explosive practical effects, high contrast dramatic lighting, intense pacing, Christopher Nolan style, motion blur on action, adrenaline energy",
        "color":        "#ff6348",
    },
    {
        "key":          "musical",
        "group":        "cinema",
        "name":         "Comédie musicale",
        "icon":         "🎭",
        "description":  "Couleurs vibrantes, éclairages théâtraux, chorégraphie — La La Land / Moulin Rouge",
        "image_suffix": "Vibrant color palette, high key lighting, theatrical spotlights, glamorous diffusion filters, bright energetic atmosphere",
        "video_suffix": "musical film, vibrant saturated colors, theatrical stage lighting with golden spotlights, expressive dance and movement, La La Land Moulin Rouge aesthetic, joyful kinetic energy, sweeping choreography, warm glowing palette",
        "color":        "#fd79a8",
    },
    {
        "key":          "romantic_comedy",
        "group":        "cinema",
        "name":         "Comédie romantique",
        "icon":         "💕",
        "description":  "Lumière dorée douce, palette pastel, Paris ou New York — Richard Curtis / Nora Ephron",
        "image_suffix": "Soft warm lighting, pastel palette, glowing highlights, soft focus background, flattering beauty lighting",
        "video_suffix": "romantic comedy film, warm golden soft lighting, bright pastel color palette, joyful lighthearted atmosphere, Paris or New York cityscape, Richard Curtis Nora Ephron style, natural performances, feel-good warmth, no dark shadows",
        "color":        "#ff9ff3",
    },
    {
        "key":          "scifi",
        "group":        "cinema",
        "name":         "Sci-fi spatiale",
        "icon":         "🚀",
        "description":  "Space opera, technologies avancées, chrome et blanc pur",
        "image_suffix":    "Clean sterile lighting, anamorphic blue lens flares, high contrast neon accents, deep blacks, Panavision lenses",
        "image_suffix_no_cam": "Clean sterile lighting, anamorphic blue lens flares, high contrast neon accents, deep blacks",
        "video_suffix": "science fiction space opera cinematic, clean futuristic world, advanced technology, chrome white surfaces, Interstellar 2001 grandeur, sweeping spacecraft",
        "color":        "#00d2d3",
    },
    {
        "key":          "fantasy",
        "group":        "cinema",
        "name":         "Fantasy épique",
        "icon":         "🐉",
        "description":  "Mondes fantastiques, magie, épopée héroïque",
        "image_suffix": "Lush saturated colors, volumetric god rays, sweeping wide angles, golden hour, high dynamic range, majestic",
        "video_suffix": "epic fantasy film, magical world, heroic adventure, fantasy landscape, cinematic grandeur, Lord of the Rings scale",
        "color":        "#a29bfe",
    },
    {
        "key":          "luxury_ad",
        "group":        "cinema",
        "name":         "Publicité luxe",
        "icon":         "💎",
        "description":  "Parfum, haute couture — ultra-léché, lumière spéculaire",
        "image_suffix": "Macro shots, perfect symmetry, highly polished, glossy reflections, softbox lighting, ultra-sharp focus, premium commercial",
        "video_suffix": "luxury brand commercial film, perfume advertisement style, ultra-clean minimal slow visuals, high specular light, slow motion elegance, Dior Chanel campaign quality",
        "color":        "#d4af37",
    },

    # ── ANIMATION ─────────────────────────────────────────────────────────────
    {
        "key":          "animation_3d",
        "group":        "animation",
        "name":         "Animation 3D",
        "icon":         "🧊",
        "description":  "Images de synthèse, rendu CGI photoréaliste ou stylisé",
        "image_suffix": "Pixar style 3D animation, subsurface scattering, raytraced lighting, vibrant colors, stylized proportions, clean render",
        "video_suffix": "3D CGI animation, computer-generated imagery, animated film, Pixar-style render, digital 3D, no live action",
        "color":        "#7c6bff",
    },
    {
        "key":          "cartoon_2d",
        "group":        "animation",
        "name":         "Dessin animé 2D",
        "icon":         "✏",
        "description":  "Animation traditionnelle, illustration cartoon colorée",
        "image_suffix": "Classic 2D cel animation, flat colors, clear line art, expressive features, traditional frame-by-frame look",
        "video_suffix": "2D cartoon animation, hand-drawn illustrated style, traditional animation, flat colors, no live action no CGI",
        "color":        "#ff6b9d",
    },
    {
        "key":          "anime",
        "group":        "animation",
        "name":         "Anime",
        "icon":         "⛩",
        "description":  "Animation japonaise, esthétique manga et anime",
        "image_suffix": "Studio Ghibli aesthetic, highly detailed background, vibrant painted skies, cel-shaded characters, cinematic anime lighting",
        "video_suffix": "anime animation, Japanese animation style, manga-inspired visual, cel-shaded, studio Ghibli quality, no live action",
        "color":        "#fd9644",
    },

    # ── ARTS & ESTHÉTIQUES ────────────────────────────────────────────────────
    {
        "key":          "cyberpunk",
        "group":        "arts",
        "name":         "Cyberpunk néon",
        "icon":         "🌆",
        "description":  "Tokyo nocturne, néons violets et cyan, pluie et chrome",
        "image_suffix": "Neon lighting, cyan and magenta palette, rain-slicked streets, glowing practicals, high contrast night scene",
        "video_suffix": "cyberpunk neon cinematic, rain and neon reflections, dark rainy dystopian streets, purple cyan magenta lights, Blade Runner original gritty urban, no daylight",
        "color":        "#a855f7",
    },
    {
        "key":          "lo_fi_retro",
        "group":        "arts",
        "name":         "Lo-fi rétro",
        "icon":         "📼",
        "description":  "Super 8, grain argentique, couleurs passées, VHS et Kodachrome",
        "image_suffix": "VHS tracking artifacts, chromatic aberration, faded colors, heavy grain, soft focus, 1980s camcorder aesthetic",
        "video_suffix": "Super 8 analog film footage, heavy grain and color fading, light leaks, Kodachrome warm palette, 70s-80s nostalgic home movie look, retro VHS artifact",
        "color":        "#e67e22",
    },
    {
        "key":          "watercolor",
        "group":        "arts",
        "name":         "Aquarelle",
        "icon":         "💧",
        "description":  "Lavis d'aquarelle poétique, textures papier, doux et lumineux",
        "image_suffix": "Watercolor painting style, soft washed out colors, visible paper texture, fluid brushstrokes, translucent",
        "video_suffix": "watercolor animated style, soft flowing watercolor washes, paper texture visible, transparent color bleeds, gentle painterly motion",
        "color":        "#74b9ff",
    },
    {
        "key":          "oil_painting",
        "group":        "arts",
        "name":         "Peinture à l'huile",
        "icon":         "🖼",
        "description":  "Impressionniste ou réaliste, matière riche et texture peinte",
        "image_suffix": "Classical oil painting, impasto brushstrokes, chiaroscuro lighting, rich deep colors, canvas texture",
        "video_suffix": "oil painting animated style, impasto brush strokes visible, rich painted canvas textures, old master cinematic quality, moving painted world",
        "color":        "#c0392b",
    },
    {
        "key":          "comics_bd",
        "group":        "arts",
        "name":         "BD franco-belge",
        "icon":         "📖",
        "description":  "Ligne claire, Moebius, Hergé — aplats nets, contours précis",
        "image_suffix": "Ligne claire style, clean ink lines, flat bold coloring, detailed environments, European comic book art",
        "video_suffix": "Franco-Belgian comic animation, ligne claire visual style, clean ink outlines flat colors, graphic novel in motion, Moebius-inspired world",
        "color":        "#f9ca24",
    },

    # ── HYBRIDE ───────────────────────────────────────────────────────────────
    {
        "key":          "brand_cinema",
        "group":        "hybride",
        "name":         "Cinéma de marque",
        "icon":         "🎞",
        "description":  "Film réaliste premium — grain 35mm, noirs profonds, lumière dramatique maîtrisée. Entre auteur et haute publicité.",
        "image_suffix":        "cinematic brand photography, motivated dramatic lighting, deep rich blacks, subtle 35mm film grain, slightly desaturated premium color grade, anamorphic lens bokeh, high production value, emotionally charged photorealism, Shot on ARRI Alexa 35mm anamorphic",
        "image_suffix_no_cam": "cinematic brand photography, motivated dramatic lighting, deep rich blacks, subtle 35mm film grain, slightly desaturated premium color grade, anamorphic lens bokeh, high production value, emotionally charged photorealism",
        "video_suffix":        "brand cinema film style, cinematic motivated dramatic lighting, deep rich blacks, subtle 35mm film grain, slightly desaturated premium color grading, anamorphic lens flares and bokeh, luxury production value, emotional photorealism, art house meets premium commercial, real human actors, live action, no CGI, no 3D render",
        "video_suffix_no_cam": "brand cinema film style, cinematic motivated dramatic lighting, deep rich blacks, subtle 35mm film grain, slightly desaturated premium color grading, anamorphic lens flares and bokeh, luxury production value, emotional photorealism, art house meets premium commercial, real human actors, live action, no CGI, no 3D render",
        "color":        "#c9913d",
    },
    {
        "key":          "multi_style",
        "group":        "hybride",
        "name":         "Multi-style",
        "icon":         "🎨",
        "description":  "Fusion créative — mêle live action et animation, réaliste et cartoon…",
        "image_suffix": "Mixed media, collaged styles, blending 2D and 3D elements, surrealistic juxtaposition, experimental visual art",
        "video_suffix": "mixed media hybrid film, blending live action and animation, creative visual fusion",
        "color":        "#2ed573",
    },
]


# ── Storage ───────────────────────────────────────────────────────────────────

def _load() -> dict:
    if not os.path.isfile(_STYLES_FILE):
        return {}
    try:
        with open(_STYLES_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _save(data: dict):
    os.makedirs(os.path.dirname(_STYLES_FILE), exist_ok=True)
    with open(_STYLES_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)



# ── Public API ────────────────────────────────────────────────────────────────

def get_style_key() -> str:
    from core.context import get_project_id
    pid = get_project_id()
    if not pid:
        return ""
    return _load().get(pid, {}).get("key", "")


def get_style_custom() -> str:
    """User-written custom style description (used to enrich Multi-style)."""
    from core.context import get_project_id
    pid = get_project_id()
    if not pid:
        return ""
    return _load().get(pid, {}).get("custom", "")


def set_style(style_key: str, custom: str = ""):
    from core.context import get_project_id
    pid = get_project_id()
    if not pid:
        return
    data = _load()
    data[pid] = {"key": style_key, "custom": custom}
    _save(data)


def get_style() -> dict | None:
    key = get_style_key()
    if not key:
        return None
    return next((s for s in STYLES if s["key"] == key), None)


def get_image_suffix() -> str:
    """Suffix appended to image generation prompts (characters, HMC, décors, accessoires)."""
    style = get_style()
    if not style:
        return ""
    parts = [style["image_suffix"]]
    custom = get_style_custom()
    if custom:
        parts.append(custom)
    return ", ".join(parts)


def get_image_suffix_no_cam() -> str:
    """Image suffix with camera/optic brand refs stripped — used when Image & Son overrides camera."""
    style = get_style()
    if not style:
        return ""
    parts = [style.get("image_suffix_no_cam", style["image_suffix"])]
    custom = get_style_custom()
    if custom:
        parts.append(custom)
    return ", ".join(parts)


def get_video_suffix() -> str:
    """Suffix appended to video generation prompts (Seedance 2.0)."""
    style = get_style()
    if not style:
        return ""
    parts = [style["video_suffix"]]
    custom = get_style_custom()
    if custom:
        parts.append(custom)
    return ", ".join(parts)


def get_video_suffix_no_cam() -> str:
    """Video suffix with camera/optic brand refs stripped — used when Image & Son overrides camera."""
    style = get_style()
    if not style:
        return ""
    parts = [style.get("video_suffix_no_cam", style["video_suffix"])]
    custom = get_style_custom()
    if custom:
        parts.append(custom)
    return ", ".join(parts)


def is_no_audio() -> bool:
    """Returns True if the selected style disables audio generation (e.g. Clip vidéo)."""
    style = get_style()
    return bool(style and style.get("no_audio"))


# ── Style reference images ─────────────────────────────────────────────────────

_STYLE_REFS_DIR = os.path.join(_ROOT, "assets", "style_refs")
_IMG_EXTS = {".jpg", ".jpeg", ".png", ".webp"}


def get_style_ref_images_for_key(key: str) -> list[str]:
    """Lists reference images for a given style key — checks user dir + bundled assets."""
    folders = [os.path.join(_STYLE_REFS_DIR, key)]
    if getattr(sys, "frozen", False):
        bundled = os.path.join(sys._MEIPASS, "assets", "style_refs", key)
        if bundled not in folders:
            folders.append(bundled)
    paths, seen = [], set()
    for folder in folders:
        if os.path.isdir(folder):
            for f in sorted(os.listdir(folder)):
                if os.path.splitext(f)[1].lower() in _IMG_EXTS and f not in seen:
                    seen.add(f)
                    paths.append(os.path.join(folder, f))
    return paths


def get_style_ref_image_for_key(key: str) -> str:
    """Returns the saved ref image for a given style key in the current project."""
    from core.context import get_project_id
    pid = get_project_id()
    if not pid or not key:
        return ""
    path = _load().get(pid, {}).get("ref_images", {}).get(key, "")
    return path if path and os.path.isfile(path) else ""


def set_style_ref_image_for_key(key: str, path: str):
    """Saves the selected ref image for a given style key in the current project."""
    from core.context import get_project_id
    pid = get_project_id()
    if not pid:
        return
    data = _load()
    if pid not in data:
        data[pid] = {}
    if "ref_images" not in data[pid]:
        data[pid]["ref_images"] = {}
    data[pid]["ref_images"][key] = path
    _save(data)


def get_style_ref_image() -> str:
    """Convenience: ref image for the current project's current style."""
    key = get_style_key()
    return get_style_ref_image_for_key(key) if key else ""
