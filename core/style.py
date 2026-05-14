"""Per-project visual style configuration."""

import json
import os

from core.paths import APP_ROOT as _ROOT
_STYLES_FILE = os.path.join(_ROOT, "data", "project_styles.json")

# ── Group catalogue ───────────────────────────────────────────────────────────

GROUPS = [
    {"key": "cinema_live", "name": "Cinéma live",        "icon": "🎬"},
    {"key": "animation",   "name": "Animation",          "icon": "✏"},
    {"key": "genre",       "name": "Genre",              "icon": "🎭"},
    {"key": "arts",        "name": "Arts visuels",       "icon": "🎨"},
    {"key": "tendances",   "name": "Tendances modernes", "icon": "📱"},
    {"key": "hybride",     "name": "Hybride",            "icon": "∞"},
]

# ── Style catalogue ───────────────────────────────────────────────────────────

STYLES = [

    # ── CINÉMA LIVE ───────────────────────────────────────────────────────────
    {
        "key":          "photorealistic",
        "group":        "cinema_live",
        "name":         "Photoréaliste",
        "icon":         "📸",
        "description":  "Rendu photographique maximal — studio ou extérieur, netteté absolue, sans filtre cinéma",
        "image_suffix": "hyperrealistic photography, photorealistic rendering, ultra-sharp focus, detailed skin texture, studio quality lighting, real person, no illustration, no artistic stylization, no film grain, no cinematic filter, 8K resolution",
        "video_suffix": "photorealistic footage, hyperrealistic cinematography, ultra-sharp pristine image quality, no film grain, no color grading filter, natural true-to-life colors, documentary realism",
        "color":        "#dfe6e9",
    },
    {
        "key":          "realistic",
        "group":        "cinema_live",
        "name":         "Film réaliste",
        "icon":         "🎬",
        "description":  "Acteurs réels, photographie cinématographique naturaliste",
        "image_suffix": "realistic photographic style, real person, cinematic film photography, natural lighting, photorealistic",
        "video_suffix": "shot on ARRI Alexa 35, photorealistic live action footage, real human actors, no CGI, no computer graphics, no digital animation, no synthetic rendering, authentic film grain, organic skin texture, true-to-life colors, natural practical lighting, live action cinema",
        "color":        "#4ecdc4",
    },
    {
        "key":          "documentary",
        "group":        "cinema_live",
        "name":         "Documentaire",
        "icon":         "📹",
        "description":  "Style journalistique, lumière naturelle, caméra à l'épaule",
        "image_suffix": "documentary photography, candid portrait, natural available light, photojournalism, raw authentic",
        "video_suffix": "documentary film style, handheld camera, natural lighting, journalistic footage, observational cinema verité",
        "color":        "#f7b731",
    },
    {
        "key":          "noir",
        "group":        "cinema_live",
        "name":         "Film noir",
        "icon":         "🕵",
        "description":  "Noir et blanc, ombres dramatiques, atmosphère néo-noir",
        "image_suffix": "film noir portrait, black and white photography, dramatic chiaroscuro shadows, high contrast, moody atmosphere",
        "video_suffix": "film noir style, black and white, dramatic chiaroscuro shadows, high contrast, neo-noir atmosphere, venetian blind light patterns, moody",
        "color":        "#8395a7",
    },
    {
        "key":          "western",
        "group":        "cinema_live",
        "name":         "Western",
        "icon":         "🤠",
        "description":  "Grand Ouest, lumière solaire rasante, poussière et ocre",
        "image_suffix": "western film portrait, sun-scorched skin, dusty warm ochre tones, golden hour backlighting, Sergio Leone cinematic, weathered texture, photorealistic",
        "video_suffix": "spaghetti western cinematic, harsh desert sun, golden ochre palette, dust and dry wind, Leone extreme close-ups and wide angles, authentic film grain, no CGI",
        "color":        "#e17055",
    },
    {
        "key":          "historical",
        "group":        "cinema_live",
        "name":         "Historique",
        "icon":         "🏛",
        "description":  "Films d'époque, costumes historiques, lumière à la bougie",
        "image_suffix": "historical period film portrait, authentic costume drama, candlelight and natural window light, period-accurate wardrobe, cinematic period photography",
        "video_suffix": "period drama costume film, historical setting, authentic wardrobe and props, candlelight and natural window light, Ridley Scott grandeur, no modern elements",
        "color":        "#b8a89a",
    },
    {
        "key":          "war_film",
        "group":        "cinema_live",
        "name":         "Film de guerre",
        "icon":         "⚔",
        "description":  "Grisaille désaturée, grain intense, urgence et chaos",
        "image_suffix": "war film soldier portrait, desaturated gritty tones, heavy film grain, exhausted war-worn look, Saving Private Ryan cinematic style",
        "video_suffix": "war film cinematic, Saving Private Ryan handheld intensity, desaturated muddy palette, heavy grain, smoke and practical lighting, chaos and urgency, no CGI",
        "color":        "#636e72",
    },
    {
        "key":          "thriller",
        "group":        "cinema_live",
        "name":         "Thriller",
        "icon":         "🔪",
        "description":  "Palette froide désaturée, tension psychologique, Fincher",
        "image_suffix": "psychological thriller portrait, cold desaturated teal-gray palette, hard rim shadows, David Fincher cinematic style, controlled unsettling stillness",
        "video_suffix": "psychological thriller, cold teal-gray desaturated palette, David Fincher precision, clinical tension, controlled shadows, slow dread, no warmth",
        "color":        "#5f6caf",
    },
    {
        "key":          "romcom",
        "group":        "cinema_live",
        "name":         "Comédie / Romcom",
        "icon":         "💛",
        "description":  "Tons chauds pastels, lumière douce, énergie légère et joyeuse",
        "image_suffix": "romantic comedy portrait, warm pastel tones, soft golden light, joyful expression, bright airy photography, cheerful lifestyle",
        "video_suffix": "romantic comedy film style, warm pastel palette, soft diffused sunlight, bright airy visuals, lighthearted joyful energy, clean uplifting composition",
        "color":        "#fdcb6e",
    },
    {
        "key":          "road_movie",
        "group":        "cinema_live",
        "name":         "Road movie",
        "icon":         "🛣",
        "description":  "Grands espaces, lumière naturelle brute, grain indie",
        "image_suffix": "road movie portrait, open highway natural light, indie film grain, wanderlust melancholy, golden vast landscape backdrop, raw authentic photography",
        "video_suffix": "road movie indie cinematic, wide open landscapes, natural golden light, Super 16mm grain, wanderlust mood, vast highways, raw and free spirit",
        "color":        "#e8a020",
    },

    # ── ANIMATION ─────────────────────────────────────────────────────────────
    {
        "key":          "animation_3d",
        "group":        "animation",
        "name":         "Animation 3D",
        "icon":         "🧊",
        "description":  "Images de synthèse, rendu CGI photoréaliste ou stylisé",
        "image_suffix": "3D CGI character design, computer animation render, Pixar DreamWorks style, 3D model, digital art",
        "video_suffix": "3D CGI animation, computer-generated imagery, animated film, Pixar-style render, digital 3D, no live action",
        "color":        "#7c6bff",
    },
    {
        "key":          "cartoon_2d",
        "group":        "animation",
        "name":         "Dessin animé 2D",
        "icon":         "✏",
        "description":  "Animation traditionnelle, illustration cartoon colorée",
        "image_suffix": "2D cartoon character illustration, hand-drawn animation style, flat graphic design, comic art, colorful bold lines",
        "video_suffix": "2D cartoon animation, hand-drawn illustrated style, traditional animation, flat colors, no live action no CGI",
        "color":        "#ff6b9d",
    },
    {
        "key":          "anime",
        "group":        "animation",
        "name":         "Anime",
        "icon":         "⛩",
        "description":  "Animation japonaise, esthétique manga et anime",
        "image_suffix": "anime character design, Japanese animation style, manga art, cel-shaded, large expressive eyes, clean ink lines",
        "video_suffix": "anime animation, Japanese animation style, manga-inspired visual, cel-shaded, studio Ghibli quality, no live action",
        "color":        "#fd9644",
    },
    {
        "key":          "stop_motion",
        "group":        "animation",
        "name":         "Stop-motion",
        "icon":         "🪆",
        "description":  "Animation image par image, marionnettes, maquettes et clay",
        "image_suffix": "stop motion puppet character design, claymation style, Laika studios aesthetic, miniature scale model, handcrafted texture",
        "video_suffix": "stop motion claymation animation, frame-by-frame puppet movement, miniature handcrafted sets, Laika Wallace and Gromit aesthetic",
        "color":        "#ffa502",
    },

    # ── GENRE ─────────────────────────────────────────────────────────────────
    {
        "key":          "fantasy",
        "group":        "genre",
        "name":         "Fantasy épique",
        "icon":         "🐉",
        "description":  "Mondes fantastiques, magie, épopée héroïque",
        "image_suffix": "epic fantasy character design, magical world, heroic detailed costume, fantasy art illustration, painterly digital art",
        "video_suffix": "epic fantasy film, magical world, heroic adventure, fantasy landscape, cinematic grandeur, Lord of the Rings scale",
        "color":        "#a29bfe",
    },
    {
        "key":          "fairy_tale",
        "group":        "genre",
        "name":         "Conte / Fable",
        "icon":         "🧚",
        "description":  "Forêt enchantée, magie douce, pastel féérique",
        "image_suffix": "fairy tale character illustration, enchanted forest soft pastel light, gentle magical glow, whimsical dreamlike, Studio Ghibli warmth and innocence",
        "video_suffix": "fairy tale magical film, enchanted soft pastel world, gentle magic and wonder, warm dreamy light, Ghibli-inspired whimsy, no dark or violent imagery",
        "color":        "#fd79a8",
    },
    {
        "key":          "scifi",
        "group":        "genre",
        "name":         "Sci-fi spatiale",
        "icon":         "🚀",
        "description":  "Space opera, technologies avancées, chrome et blanc pur",
        "image_suffix": "sci-fi character design, futuristic space opera costume, chrome and white minimal surfaces, clean futuristic aesthetic, Blade Runner 2049 Denis Villeneuve",
        "video_suffix": "science fiction space opera cinematic, clean futuristic world, advanced technology, chrome white surfaces, Interstellar 2001 grandeur, sweeping spacecraft",
        "color":        "#00d2d3",
    },
    {
        "key":          "cyberpunk",
        "group":        "genre",
        "name":         "Cyberpunk néon",
        "icon":         "🌆",
        "description":  "Tokyo nocturne, néons violets et cyan, pluie et chrome",
        "image_suffix": "cyberpunk neon portrait, wet rain-soaked neon-lit Tokyo night, purple and cyan light reflections, chrome surfaces, Blade Runner 1982 aesthetic, dystopian",
        "video_suffix": "cyberpunk neon cinematic, rain and neon reflections, dark rainy dystopian streets, purple cyan magenta lights, Blade Runner original gritty urban, no daylight",
        "color":        "#a855f7",
    },
    {
        "key":          "horror",
        "group":        "genre",
        "name":         "Horreur",
        "icon":         "👁",
        "description":  "Atmosphère sombre et oppressante, tension, effets pratiques",
        "image_suffix": "horror film character, dark disturbing atmosphere, eerie unsettling lighting, deep shadows and fog, practical makeup effects",
        "video_suffix": "horror film style, dark oppressive atmosphere, tension and dread, unsettling visuals, practical effects, deep shadows, no comfort",
        "color":        "#ff4757",
    },
    {
        "key":          "steampunk",
        "group":        "genre",
        "name":         "Steampunk",
        "icon":         "⚙",
        "description":  "Vapeur, cuivre et laiton, mécanique victorienne",
        "image_suffix": "steampunk character portrait, Victorian brass and copper gears, steam pipes, elaborate mechanical costume, sepia amber tones, industrial fantasy detail",
        "video_suffix": "steampunk cinematic, Victorian industrial world, steam and brass machinery, amber sepia warm palette, clockwork mechanisms, Jules Verne H.G. Wells aesthetic",
        "color":        "#b8860b",
    },
    {
        "key":          "surrealism",
        "group":        "genre",
        "name":         "Surréalisme",
        "icon":         "🌊",
        "description":  "Rêve éveillé, physique impossible, Dalí et Magritte",
        "image_suffix": "surrealist portrait, dreamlike impossible scene, Salvador Dalí René Magritte aesthetic, melting distorted reality, dream logic, hyperreal oil painting quality",
        "video_suffix": "surrealist cinematic dream, impossible physics and melting reality, Dalí aesthetic, hypnotic dream logic, unexpected surreal imagery and transformations",
        "color":        "#e056fd",
    },
    {
        "key":          "musical",
        "group":        "genre",
        "name":         "Comédie musicale",
        "icon":         "🎭",
        "description":  "Costumes spectaculaires, couleurs vives, mise en scène théâtrale",
        "image_suffix": "musical theater spectacular costume, vibrant oversaturated colors, stage theatrical makeup, glamorous dramatic portrait",
        "video_suffix": "musical film, vibrant saturated colors, theatrical staging, choreographed performance, Broadway aesthetic, showstopper energy",
        "color":        "#ff6348",
    },

    # ── ARTS VISUELS ──────────────────────────────────────────────────────────
    {
        "key":          "watercolor",
        "group":        "arts",
        "name":         "Aquarelle",
        "icon":         "💧",
        "description":  "Lavis d'aquarelle poétique, textures papier, doux et lumineux",
        "image_suffix": "watercolor painting portrait, soft watercolor wash texture, paper grain visible, transparent color layers, delicate brush strokes, artistic illustration",
        "video_suffix": "watercolor animated style, soft flowing watercolor washes, paper texture visible, transparent color bleeds, gentle painterly motion",
        "color":        "#74b9ff",
    },
    {
        "key":          "oil_painting",
        "group":        "arts",
        "name":         "Peinture à l'huile",
        "icon":         "🖼",
        "description":  "Impressionniste ou réaliste, matière riche et texture peinte",
        "image_suffix": "oil painting portrait, impasto thick brush strokes, rich oil paint texture, old master painting quality, museum fine art, Rembrandt Vermeer Sargent",
        "video_suffix": "oil painting animated style, impasto brush strokes visible, rich painted canvas textures, old master cinematic quality, moving painted world",
        "color":        "#c0392b",
    },
    {
        "key":          "comics_bd",
        "group":        "arts",
        "name":         "BD franco-belge",
        "icon":         "📖",
        "description":  "Ligne claire, Moebius, Hergé — aplats nets, contours précis",
        "image_suffix": "Franco-Belgian comic book illustration, ligne claire style, Moebius Hergé aesthetic, clean precise ink outlines, flat color fills, bold graphic design",
        "video_suffix": "Franco-Belgian comic animation, ligne claire visual style, clean ink outlines flat colors, graphic novel in motion, Moebius-inspired world",
        "color":        "#f9ca24",
    },
    {
        "key":          "art_nouveau",
        "group":        "arts",
        "name":         "Art Nouveau",
        "icon":         "🌿",
        "description":  "Mucha, Klimt — arabesques organiques, dorures décoratives",
        "image_suffix": "Art Nouveau portrait illustration, Alphonse Mucha Klimt style, flowing organic decorative lines, gold ornamental borders, floral botanical motifs, Belle Époque elegance",
        "video_suffix": "Art Nouveau animated style, Mucha Klimt aesthetic, flowing organic ornamental lines, gold and jewel tones, decorative Belle Époque motion",
        "color":        "#c9a84c",
    },
    {
        "key":          "ink_wash",
        "group":        "arts",
        "name":         "Encre & lavis",
        "icon":         "🖋",
        "description":  "Croquis à l'encre, lavis monochrome, art conceptuel",
        "image_suffix": "ink wash portrait, gestural brush ink strokes, monochrome sumi-e calligraphic style, black ink on white paper, concept art sketch quality",
        "video_suffix": "ink wash animated style, gestural black ink brush strokes, monochrome fluid motion, sumi-e Japanese calligraphic aesthetic",
        "color":        "#2d3436",
    },
    {
        "key":          "low_poly",
        "group":        "arts",
        "name":         "Low poly",
        "icon":         "🔷",
        "description":  "Polygones géométriques, facettes triangulées, flat 3D",
        "image_suffix": "low poly 3D art, geometric triangulated polygon facets, flat shaded faces, clean modern digital illustration, vibrant limited color palette",
        "video_suffix": "low poly 3D animation, geometric polygon world, triangulated flat shading, clean modern digital motion design, vibrant geometric animation",
        "color":        "#00cec9",
    },
    {
        "key":          "pixel_art",
        "group":        "arts",
        "name":         "Pixel art",
        "icon":         "👾",
        "description":  "Rétro gaming 8-bit/16-bit, sprites pixelisés, palette limitée",
        "image_suffix": "pixel art character sprite, 16-bit retro game aesthetic, crisp pixel grid, limited color palette, SNES Super Nintendo era style, clean pixelated illustration",
        "video_suffix": "pixel art animation, 16-bit retro video game style, crisp pixel sprites, limited palette, classic SNES game motion, no smooth gradients",
        "color":        "#6c5ce7",
    },

    # ── TENDANCES MODERNES ────────────────────────────────────────────────────
    {
        "key":          "lo_fi_retro",
        "group":        "tendances",
        "name":         "Lo-fi rétro",
        "icon":         "📼",
        "description":  "Super 8, grain argentique, couleurs passées, VHS et Kodachrome",
        "image_suffix": "Super 8 analog film photography, heavy grain and light leaks, faded Kodachrome saturated colors, vintage 1970s aesthetic, nostalgic retro portrait",
        "video_suffix": "Super 8 analog film footage, heavy grain and color fading, light leaks, Kodachrome warm palette, 70s-80s nostalgic home movie look, retro VHS artifact",
        "color":        "#e67e22",
    },
    {
        "key":          "luxury_ad",
        "group":        "tendances",
        "name":         "Publicité luxe",
        "icon":         "💎",
        "description":  "Parfum, haute couture — ultra-léché, lumière spéculaire",
        "image_suffix": "luxury fashion advertising photography, perfume campaign editorial portrait, high specular specular reflections, ultra-clean minimal, fashion editorial, Dior Chanel Hermès aesthetic",
        "video_suffix": "luxury brand commercial film, perfume advertisement style, ultra-clean minimal slow visuals, high specular light, slow motion elegance, Dior Chanel campaign quality",
        "color":        "#d4af37",
    },
    {
        "key":          "nature_doc",
        "group":        "tendances",
        "name":         "Nature documentaire",
        "icon":         "🌍",
        "description":  "BBC Earth, National Geographic, lumières naturelles riches",
        "image_suffix": "nature documentary wildlife photography, BBC Earth Planet Earth quality, rich natural golden light, ultra-sharp pristine environment, National Geographic standard",
        "video_suffix": "BBC Earth nature documentary, pristine stabilized natural cinematography, ultra-sharp rich natural colors, Planet Earth David Attenborough quality, no humans",
        "color":        "#00b894",
    },
    {
        "key":          "found_footage",
        "group":        "tendances",
        "name":         "Found footage",
        "icon":         "📷",
        "description":  "Caméscope tremblant, VHS brut, réalisme documentaire immersif",
        "image_suffix": "found footage still frame, consumer camcorder capture, date time stamp overlay, low resolution analog grain, raw unfiltered documentary",
        "video_suffix": "found footage film, shaky handheld consumer camcorder, VHS degraded quality, date stamp overlay, raw unedited realism, Blair Witch Cloverfield intensity",
        "color":        "#55efc4",
    },
    {
        "key":          "clip_video",
        "group":        "tendances",
        "name":         "Clip vidéo",
        "icon":         "📱",
        "description":  "Clips courts sans dialogue, générés sans audio intégré",
        "image_suffix": "clean cinematic commercial photography, advertising quality, crisp and vibrant colors",
        "video_suffix": "short video clip, no dialogue, clean cinematic visuals, advertising quality footage",
        "no_audio":     True,
        "color":        "#1e90ff",
    },

    # ── HYBRIDE ───────────────────────────────────────────────────────────────
    {
        "key":          "multi_style",
        "group":        "hybride",
        "name":         "Multi-style",
        "icon":         "🎨",
        "description":  "Fusion créative — mêle live action et animation, réaliste et cartoon…",
        "image_suffix": "mixed media hybrid visual style, combining live action photography and illustrated animation",
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


def is_no_audio() -> bool:
    """Returns True if the selected style disables audio generation (e.g. Clip vidéo)."""
    style = get_style()
    return bool(style and style.get("no_audio"))


# ── Style reference images ─────────────────────────────────────────────────────

_STYLE_REFS_DIR = os.path.join(_ROOT, "assets", "style_refs")
_IMG_EXTS = {".jpg", ".jpeg", ".png", ".webp"}


def get_style_ref_images_for_key(key: str) -> list[str]:
    """Lists available reference images for a given style key from assets/style_refs/{key}/."""
    folder = os.path.join(_STYLE_REFS_DIR, key)
    if not os.path.isdir(folder):
        return []
    return sorted([
        os.path.join(folder, f)
        for f in os.listdir(folder)
        if os.path.splitext(f)[1].lower() in _IMG_EXTS
    ])


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
