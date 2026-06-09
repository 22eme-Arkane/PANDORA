"""
core/vj_styles.py — Catalogue de styles VJ pour PANDORA | Live.

Données pures (aucune dépendance UI). Ces 20 styles servent de SÉLECTEUR dans le
Studio IA Live : l'utilisateur choisit un style, son `prompt` (en anglais) est
injecté dans la génération du loop.

Chaque preset :
  - key            : identifiant stable
  - name / name_en : nom affiché (FR / EN)
  - desc / desc_en : description courte du style (FR / EN)
  - prompt         : prompt de génération en ANGLAIS (loop VJ), envoyé au moteur

Source : carte mentale PANDORA | Live (20 styles VJ).

TODO (futur) : vignette/preview par style, tags pour le filtrage, moteur préféré.
"""

from core.i18n import get_lang


_STYLES: list[dict] = [
    {
        "key": "techno_minimal",
        "name": "Techno Minimal & Vectoriel", "name_en": "Minimal Techno & Vector",
        "desc": "Lignes épurées, contrastes violents, structures géométriques chirurgicales.",
        "desc_en": "Clean lines, harsh contrast, surgical geometric structures.",
        "prompt": "Seamless VJ loop, ultra-minimalist white vector lines shifting on a "
                  "pure black background, mathematical symmetry, 3D wireframe grid moving "
                  "forward, sharp contrast, hypnotic rhythm, 8k, perfect loop.",
    },
    {
        "key": "cyberpunk_retro",
        "name": "Cyberpunk & Rétro-Futuriste", "name_en": "Cyberpunk & Retro-Futuristic",
        "desc": "Villes dystopiques, néons omniprésents, câbles, pluie, noir/violet/cyan.",
        "desc_en": "Dystopian cities, pervasive neon, cables, rain, black/violet/cyan.",
        "prompt": "VJ loop, dark cyberpunk city alley, glowing neon signs in violet and "
                  "deep cyan, flying drones, rain reflections on asphalt, fast forward "
                  "camera movement, dark synthwave aesthetic, seamless looping.",
    },
    {
        "key": "glitch_datamosh",
        "name": "Glitch Art & Datamoshing", "name_en": "Glitch Art & Datamoshing",
        "desc": "Esthétique du bug numérique, distorsions VHS, artefacts de compression.",
        "desc_en": "Digital-bug aesthetic, VHS distortion, compression artifacts.",
        "prompt": "Experimental VJ loop, heavy datamoshing effect, RGB split, analog VHS "
                  "glitch, texture distortion, abstract shifting colors melting into each "
                  "other, strobe light flashes, raw digital noise, seamless.",
    },
    {
        "key": "psychedelic_fractal",
        "name": "Psychédélique & Fractal", "name_en": "Psychedelic & Fractal",
        "desc": "Tunnels infinis, géométrie sacrée, kaléidoscopes ultra-saturés.",
        "desc_en": "Infinite tunnels, sacred geometry, ultra-saturated kaleidoscopes.",
        "prompt": "Hypnotic VJ loop, infinite Mandelbrot fractal zoom, sacred geometry "
                  "shifting patterns, kaleidoscopic motion, ultra-saturated neon colors, "
                  "psychedelic fluid dynamics, seamless transition.",
    },
    {
        "key": "liquid_chrome",
        "name": "Chrome Fluide & Métal Liquide", "name_en": "Liquid Chrome & Metal",
        "desc": "Matières métalliques en fusion, mercure, reflets haut de gamme.",
        "desc_en": "Molten metallic materials, mercury, high-end reflections.",
        "prompt": "Abstract VJ loop, molten liquid chrome spinning in zero gravity, deep "
                  "violet and metallic silver reflections, 3D fluid simulation, smooth "
                  "morphing shapes, dark ambient lighting, raytracing, perfect loop.",
    },
    {
        "key": "organic_hightech",
        "name": "Organique High-Tech", "name_en": "Organic High-Tech",
        "desc": "Plantes virtuelles, structures osseuses/minérales mêlées à la tech.",
        "desc_en": "Virtual plants, bone/mineral structures blended with tech.",
        "prompt": "VJ loop, bioluminescent alien roots growing in dark space, glowing "
                  "particles pulsing along veins, cybernetic organic structure, macro shot, "
                  "deep blue and emerald green accents, seamless motion.",
    },
    {
        "key": "op_art",
        "name": "Kinetic & Op Art", "name_en": "Kinetic & Op Art",
        "desc": "Illusions d'optique noir et blanc, motifs qui créent du mouvement.",
        "desc_en": "Black-and-white optical illusions, motion from pure contrast.",
        "prompt": "VJ loop, black and white optical illusion, moiré pattern shifting, "
                  "concentric geometric rings expanding, stark contrast, kinetic art, "
                  "hypnotic dizzying effect, perfect loop.",
    },
    {
        "key": "dark_synth_occult",
        "name": "Dark Synth & Occulte", "name_en": "Dark Synth & Occult",
        "desc": "Imagerie sombre, symboles ésotériques 3D, cathédrales industrielles.",
        "desc_en": "Dark imagery, 3D esoteric symbols, industrial cathedrals.",
        "prompt": "Dark VJ loop, slow cinematic camera tracking through a brutalist concrete "
                  "temple, glowing red neon runes on walls, heavy smoke, occult industrial "
                  "aesthetic, deep shadows, atmospheric, seamless.",
    },
    {
        "key": "vaporwave_lofi",
        "name": "Vaporwave & Lo-Fi 3D", "name_en": "Vaporwave & Lo-Fi 3D",
        "desc": "Statues antiques, nostalgie Internet 95, palmiers et teintes pastel.",
        "desc_en": "Antique statues, '95 internet nostalgia, palms and pastels.",
        "prompt": "Vaporwave VJ loop, 3D marble glitch statue flying over a wireframe grid "
                  "ocean, pink sunset sky, low-poly palm trees, windows 95 aesthetic, lo-fi "
                  "textures, nostalgic dream, seamless loop.",
    },
    {
        "key": "point_cloud",
        "name": "Particules & Point Cloud", "name_en": "Particles & Point Cloud",
        "desc": "Ambiance spatiale, constellations, fumée volumétrique, data viz.",
        "desc_en": "Space ambience, constellations, volumetric smoke, data viz.",
        "prompt": "VJ loop, flying through a dense gold and deep blue particle cloud, plexus "
                  "effect, interconnected lines forming abstract shapes, cosmic dust, fast "
                  "fly-through camera, 3D data visualization, seamless.",
    },
    {
        "key": "acid_rave_90s",
        "name": "Acid Rave 90s", "name_en": "Acid Rave 90s",
        "desc": "Rave primitive : smileys, logos 3D low-poly, lasers fluo, typo brutale.",
        "desc_en": "Primitive rave: smileys, low-poly 3D logos, neon lasers, brutal type.",
        "prompt": "VJ loop, 90s rave aesthetic, low-poly 3D spinning chrome smiley faces, "
                  "bright green and hot pink laser beams cutting through thick fog, fast "
                  "strobe flashes, retro techno visual, seamless.",
    },
    {
        "key": "brutalism_industrial",
        "name": "Brutalisme Industriel", "name_en": "Industrial Brutalism",
        "desc": "Blocs de béton massifs, usines désaffectées — techno berlinoise.",
        "desc_en": "Massive concrete blocks, derelict factories — Berlin techno.",
        "prompt": "Dark VJ loop, massive brutalist concrete structures shifting and "
                  "interlocking, overhead cinematic drone shot, chromatic industrial "
                  "shadows, stark gray and deep charcoal tones, heavy atmospheric smoke, "
                  "seamless loop.",
    },
    {
        "key": "deconstructed_club",
        "name": "Deconstructed Club & Y2K Grunge", "name_en": "Deconstructed Club & Y2K Grunge",
        "desc": "Barbelés 3D, chaînes chrome, cuir/plastique brillant — avant-garde.",
        "desc_en": "3D barbed wire, chrome chains, glossy leather/plastic — avant-garde.",
        "prompt": "Abstract VJ loop, deconstructed club aesthetic, 3D shiny metallic barbed "
                  "wire spinning, transparent plastic textures morphing, liquid oil spills, "
                  "high gloss, dark purple and iridescent lighting, edgy, seamless.",
    },
    {
        "key": "solarpunk",
        "name": "Solarpunk & Éco-Futurisme", "name_en": "Solarpunk & Eco-Futurism",
        "desc": "Cités vertes, cascades numériques, tech propre — house ensoleillée.",
        "desc_en": "Green cities, digital waterfalls, clean tech — sunny house.",
        "prompt": "Utopian VJ loop, solarpunk architecture integrated with lush green "
                  "waterfalls, glowing solar panels shaped like leaves, golden hour sunlight "
                  "flare, flying white futuristic drones, clean and organic, seamless "
                  "tracking shot.",
    },
    {
        "key": "ascii_typo",
        "name": "Typographique & ASCII Art", "name_en": "Typographic & ASCII Art",
        "desc": "Flux de code, lettres formant des images, hacks d'écran au rythme du kick.",
        "desc_en": "Code streams, letters forming images, screen hacks on the kick.",
        "prompt": "VJ loop, matrix ASCII art code rain falling, flickering green typography "
                  "on absolute black background, digital terminal screen glitch, binary code "
                  "patterns shifting, hypnotic text animation, seamless loop.",
    },
    {
        "key": "xray_biotech",
        "name": "Rayon X & Cyber-Biologie", "name_en": "X-Ray & Cyber-Biology",
        "desc": "Scans 3D, squelettes translucides, imagerie thermique, cellules.",
        "desc_en": "3D scans, translucent skeletons, thermal imaging, cells.",
        "prompt": "Experimental VJ loop, glowing 3D translucent human skeleton wireframe "
                  "rotating, deep neon blue and bright orange thermal camera palette, "
                  "medical scan aesthetic, rhythmic pulse distortion, seamless.",
    },
    {
        "key": "warp_drive",
        "name": "Hyper-Vitesse & Warp Drive", "name_en": "Hyperspeed & Warp Drive",
        "desc": "Passage en vitesse lumière, traînées d'étoiles, lignes convergentes.",
        "desc_en": "Lightspeed jump, star trails, converging light lines.",
        "prompt": "High-speed VJ loop, forward movement into a cosmic wormhole, hyperdrive "
                  "starfield effect, long neon light streaks stretching past the camera, "
                  "deep space travel, adrenaline aesthetic, perfect seamless loop.",
    },
    {
        "key": "anime_core",
        "name": "Anime Core & Manga Vapor", "name_en": "Anime Core & Manga Vapor",
        "desc": "Cel-shading rétro/moderne, mechas, courses moto, filtres VHS.",
        "desc_en": "Retro/modern cel-shading, mechs, bike chases, VHS filters.",
        "prompt": "90s anime aesthetic VJ loop, retro mecha cockpit controls flashing, "
                  "cybernetic eyes opening, neon pink and electric blue cel-shaded lines, "
                  "fast action cuts, lofi grain overlay, seamless motion.",
    },
    {
        "key": "dada_collage",
        "name": "Collage Dadaïste & Surréalisme Pop", "name_en": "Dada Collage & Pop Surrealism",
        "desc": "Découpages vintage, objets flottants — électro-swing, sets éclectiques.",
        "desc_en": "Vintage cut-outs, floating objects — electro-swing, eclectic sets.",
        "prompt": "Surreal VJ loop, vintage magazine collage animation, giant eyes floating "
                  "in a checkerboard sky, flying retro TVs displaying static noise, dadaism "
                  "aesthetic, choppy stop-motion rhythm, seamless loop.",
    },
    {
        "key": "macro_mineral",
        "name": "Micro-Détails & Macro Minérale", "name_en": "Micro-Detail & Mineral Macro",
        "desc": "Gros plans extrêmes : cristaux, or fondu, bulles — hypnotique et texturé.",
        "desc_en": "Extreme close-ups: crystals, molten gold, bubbles — hypnotic texture.",
        "prompt": "Macro VJ loop, close-up of colorful iridescent bismuth crystals growing "
                  "in real-time, metallic prism reflections, rainbow color palette shifting, "
                  "liquid geometry, sharp focus, abstract luxury texture, seamless.",
    },
]


# ── API ─────────────────────────────────────────────────────────────────────

def get_styles() -> list[dict]:
    """Retourne la liste complète des presets de styles VJ."""
    return list(_STYLES)


def get_style(key: str) -> dict | None:
    """Retourne un preset par sa clé, ou None."""
    return next((s for s in _STYLES if s["key"] == key), None)


def localized_name(style: dict) -> str:
    """Nom du style dans la langue courante."""
    return style.get("name_en", style["name"]) if get_lang() == "en" else style["name"]


def localized_desc(style: dict) -> str:
    """Description du style dans la langue courante."""
    return style.get("desc_en", style.get("desc", "")) if get_lang() == "en" else style.get("desc", "")
