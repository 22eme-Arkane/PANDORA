"""
Nano Banana API — génération de portraits de personnages.

Pour activer le mode réel :
1. Entre ta clé API Nano Banana dans Paramètres
2. Remplace le bloc _real() ci-dessous avec l'endpoint Nano Banana

En mode mock (sans clé), le worker simule la génération sans appel réseau.
"""

import os
import time

from PyQt6.QtCore import QThread, pyqtSignal
from core.config import load_config, get_image_endpoint, get_image_price
from core.pandora_dirs import get_bin_dir
from core.worker import humanize_api_error


def analyze_style_for_image(image_path: str, anthropic_key: str) -> str:
    """
    Claude Haiku Vision — extrait les descripteurs de style pictural d'une image.
    Retourne une phrase courte (10-15 mots) à préfixer au prompt NB,
    ex. "photorealistic cinema, full color, dramatic cinematic lighting".
    Retourne "" en cas d'erreur.
    """
    try:
        import base64
        import anthropic as _anth
        _ext = os.path.splitext(image_path)[1].lower()
        _mime = {".jpg": "image/jpeg", ".jpeg": "image/jpeg",
                 ".png": "image/png", ".webp": "image/webp"}
        _media_type = _mime.get(_ext, "image/jpeg")
        with open(image_path, "rb") as _f:
            _b64 = base64.standard_b64encode(_f.read()).decode()
        client = _anth.Anthropic(api_key=anthropic_key)
        msg = client.messages.create(
            model="claude-haiku-4-5",
            max_tokens=80,
            messages=[{"role": "user", "content": [
                {"type": "image", "source": {"type": "base64",
                 "media_type": _media_type, "data": _b64}},
                {"type": "text", "text": (
                    "Describe the VISUAL/PICTURAL STYLE of this image in 10-15 English words "
                    "as an image generation prompt prefix. Include: rendering medium "
                    "(photorealistic live-action / 3D CGI / 2D anime / watercolor / "
                    "oil painting / illustration / etc.), color treatment "
                    "(full color / black and white / sepia / monochrome), and overall "
                    "aesthetic (cinematic / editorial / fantasy / sci-fi / impressionist / etc.). "
                    "DO NOT describe the scene content, subjects, characters, or objects. "
                    "ONLY describe the artistic/visual rendering style. "
                    "Output ONLY the style keywords comma-separated, no punctuation at end, "
                    "no explanation."
                )},
            ]}],
        )
        return msg.content[0].text.strip().rstrip(".,")
    except Exception:
        return ""


def analyze_fidelity_for_image(image_path: str, anthropic_key: str, subject_hint: str = "") -> str:
    """
    Claude Haiku Vision — décrit le sujet avec précision maximale pour reproduction fidèle.
    subject_hint : "accessory", "vehicle", "location", "outfit/makeup/hair", etc.
    Retourne une phrase (max 60 mots) à préfixer au prompt NB.
    Retourne "" en cas d'erreur.
    """
    try:
        import base64
        import anthropic as _anth
        _ext = os.path.splitext(image_path)[1].lower()
        _mime = {".jpg": "image/jpeg", ".jpeg": "image/jpeg",
                 ".png": "image/png", ".webp": "image/webp"}
        _media_type = _mime.get(_ext, "image/jpeg")
        with open(image_path, "rb") as _f:
            _b64 = base64.standard_b64encode(_f.read()).decode()
        client = _anth.Anthropic(api_key=anthropic_key)
        hint_line = f" The subject is a {subject_hint}." if subject_hint else ""
        msg = client.messages.create(
            model="claude-haiku-4-5",
            max_tokens=100,
            messages=[{"role": "user", "content": [
                {"type": "image", "source": {"type": "base64",
                 "media_type": _media_type, "data": _b64}},
                {"type": "text", "text": (
                    f"Describe this image's subject with maximum precision for exact reproduction.{hint_line} "
                    "Cover: exact materials, colors (use specific color names), shape, proportions, "
                    "textures, and the most distinctive identifying features. "
                    "Under 60 words. Output ONLY the description, no preamble, no explanation."
                )},
            ]}],
        )
        return msg.content[0].text.strip().rstrip(".")
    except Exception:
        return ""


def _extract_image_url(result) -> str:
    """Extrait l'URL de la première image d'une réponse fal.ai de manière sécurisée."""
    if not isinstance(result, dict):
        raise RuntimeError(f"Réponse API inattendue (type {type(result).__name__}) : {str(result)[:200]}")
    images = result.get("images")
    if not images:
        raise RuntimeError(f"Aucune image dans la réponse API : {str(result)[:200]}")
    url = images[0].get("url", "") if isinstance(images[0], dict) else ""
    if not url:
        raise RuntimeError("URL d'image manquante dans la réponse API.")
    return url


def _extract_image_urls(result) -> list:
    """Extrait toutes les URLs d'images d'une réponse fal.ai."""
    if not isinstance(result, dict):
        raise RuntimeError(f"Réponse API inattendue : {str(result)[:200]}")
    images = result.get("images") or []
    urls = [img.get("url", "") for img in images if isinstance(img, dict) and img.get("url")]
    if not urls:
        raise RuntimeError(f"Aucune URL d'image dans la réponse API : {str(result)[:200]}")
    return urls


def _project_images_dir(subdir: str) -> str:
    """Retourne le dossier images du projet courant pour le module donné."""
    try:
        if subdir == "castings":
            import core.casting as m; return m.images_dir()
        if subdir == "accessories":
            import core.accessories as m; return m.images_dir()
        if subdir == "hmc":
            import core.hmc as m; return m.images_dir()
        if subdir == "vehicles":
            import core.vehicles as m; return m.images_dir()
        if subdir == "decors":
            import core.decors as m; return m.images_dir()
        if subdir in ("live_castings", "live_accessories", "live_vehicles"):
            import core.live_assets as m; return m.images_dir_for_subdir(subdir)
    except Exception:
        pass
    return get_bin_dir(subdir)

# ── Prompt système pour optimisation Claude ───────────────────────────────────

_OPTIMIZE_SYSTEM = """\
LANGUE DE RÉPONSE : Réponds TOUJOURS en français, quelle que soit la langue du texte en entrée. Le prompt de sortie DOIT être rédigé en français — l'utilisateur doit pouvoir le lire et le vérifier. La traduction en anglais pour le modèle IA est effectuée automatiquement en aval, tu n'as PAS à le faire.

Tu es un expert en ingénierie de prompts pour la génération d'images IA en production cinématographique.

L'utilisateur fournit soit :
- Une description naturelle d'un personnage (ex : "homme grand, 40 ans, barbe grise, regard intense")
- Un prompt partiel qu'il veut améliorer

Dans les deux cas, transforme l'entrée en un prompt optimisé pour la génération d'images Nano Banana.

Exigences pour le prompt de sortie :
- Décris avec précision l'apparence physique : traits du visage, morphologie, couleur de peau, yeux, cheveux
- Décris le costume, les accessoires et la tenue vestimentaire avec précision (matières, couleurs, détails)
- Cadrage tête et épaules pour un portrait, corps entier si le costume ou l'équipement est important
- NE PAS imposer de type d'éclairage spécifique (pas de Rembrandt, pas de fond studio précis) — l'éclairage est défini par le style visuel du projet
- Si un style visuel est indiqué à la fin du message, adapte OBLIGATOIREMENT le prompt à ce style
- Qualité photo de casting professionnel film/TV

TERMES INTERDITS (ne jamais écrire) : "photorealistic", "ultra-detailed", "highly detailed", "8K", "4K", "HDR photo", "Unreal Engine", "Octane Render", "rendered". Ces mots poussent le modèle vers un rendu 3D/CGI plastique. Utilise à la place le vocabulaire cinématographique : prise de vue sur caméra de cinéma, optique spécifique, lumière naturelle ou d'ambiance, textures organiques, imperfections naturelles.

Retourne UNIQUEMENT le prompt optimisé en français. Pas d'explication, pas de préfixe, pas de guillemets.\
"""

_OPTIMIZE_CHARACTER_WITH_REF_SYSTEM = """\
LANGUE DE RÉPONSE : Réponds TOUJOURS en français, quelle que soit la langue du texte en entrée. Le prompt de sortie DOIT être rédigé en français — l'utilisateur doit pouvoir le lire et le vérifier. La traduction en anglais pour le modèle IA est effectuée automatiquement en aval, tu n'as PAS à le faire.

Tu es un expert en ingénierie de prompts pour la génération de portraits de personnages IA en production cinématographique.

L'utilisateur fournit une ou plusieurs photos de référence d'une personne réelle ET optionnellement une description du personnage.

Ta tâche :
1. ANALYSER la/les photo(s) de référence : décrire le visage avec précision — ethnie, teint, forme du visage, couleur et forme des yeux, nez, lèvres, mâchoire, pommettes, couleur des cheveux, texture, longueur. Sois extrêmement détaillé.
2. COMBINER cette description du visage avec la description du personnage fournie par l'utilisateur (costume, rôle, style, ambiance, etc.). Si aucune description n'est fournie, base-toi uniquement sur ce que tu observes.
3. PRODUIRE un prompt unique pour Nano Banana qui :
   - Commence par "CORRESPONDANCE FACIALE EXACTE :" suivi de la description détaillée du visage issue de la photo
   - Continue avec le costume, le contexte et l'ambiance du personnage
   - Précise l'éclairage cinématographique, la qualité photoréaliste, la qualité photo de casting film/TV
   - Reste sous 200 mots

Le visage sur la photo de référence est la SOURCE PRINCIPALE — la description du personnage définit uniquement le costume et le contexte. L'image générée DOIT ressembler à la personne sur la photo.

Retourne UNIQUEMENT le prompt optimisé en français. Pas d'explication, pas de préfixe, pas de guillemets.\
"""

_TEXTURE_ANALYSIS_SYSTEM = """\
You are a skin texture analyst for AI portrait generation via PuLID face-injection.
PuLID handles face GEOMETRY automatically from the reference photo.
Your role: extract ONLY surface texture details that PuLID cannot inject on its own.

Analyze the face in the photo. Output a single concise phrase (under 55 words) describing ONLY:
- Skin tone and undertones (e.g. "warm olive skin with golden undertones", "fair skin with cool pink undertones")
- Skin texture (e.g. "smooth", "slightly porous", "fine lines around eyes", "visible pores")
- Distinctive marks ONLY if prominent: beard/stubble color+density, freckles, moles, scars, dimples

DO NOT describe: face shape, jaw, cheekbones, eye shape, nose shape, hair color or style.
Output ONLY the texture phrase. No prefix, no explanation.\
"""

_COSTUME_FILTER_SYSTEM = """\
You receive a character description (may be in French or English).
Task: translate everything to English, then REMOVE all physical appearance descriptors.

REMOVE: hair color, hair style, hair length, eye color, skin color/tone, face shape,
jaw/cheekbone/nose/lip descriptions, height as exact measurement, body build descriptors.

KEEP: costume details, clothing items, accessories, profession/role, personality traits,
age as a general category (young adult / middle-aged / older), setting or period context.

Output ONLY the filtered English description. Under 80 words. No preamble.\
"""

_OPTIMIZE_VEHICLE_SYSTEM = """\
LANGUE DE RÉPONSE : Réponds TOUJOURS en français, quelle que soit la langue du texte en entrée. Le prompt de sortie DOIT être rédigé en français — l'utilisateur doit pouvoir le lire et le vérifier. La traduction en anglais pour le modèle IA est effectuée automatiquement en aval, tu n'as PAS à le faire.

Tu es un expert en ingénierie de prompts pour la photographie automobile IA en production cinématographique.

L'utilisateur décrit un véhicule (voiture, moto, camion, bateau, aéronef, etc.).
Transforme l'entrée en un prompt optimisé pour la génération d'images Nano Banana.

Exigences :
- Photographie automobile cinématographique haute qualité
- Fond uni blanc pur — absolument pas de route, de rue, d'environnement, de décor, de ciel
- Éclairage studio doux et uniforme, reflets nets sur la carrosserie
- AUCUNE personne, AUCUN conducteur, AUCUN piéton — le véhicule doit apparaître seul
- Angle 3/4 avant préféré — montrer le véhicule entier, sans rognage
- Qualité de référence département artistique film/TV professionnel
- Adapté comme référence visuelle pour la conception de production et Seedance 2.0

TERMES INTERDITS : "photorealistic", "ultra-detailed", "highly detailed", "8K", "Unreal Engine", "Octane Render".
CRITIQUE : Le véhicule doit être totalement isolé sur fond blanc. Aucun élément de fond.

Retourne UNIQUEMENT le prompt optimisé en français. Pas d'explication, pas de préfixe, pas de guillemets.\
"""

_OPTIMIZE_ACCESSORY_SYSTEM = """\
LANGUE DE RÉPONSE : Réponds TOUJOURS en français, quelle que soit la langue du texte en entrée. Le prompt de sortie DOIT être rédigé en français — l'utilisateur doit pouvoir le lire et le vérifier. La traduction en anglais pour le modèle IA est effectuée automatiquement en aval, tu n'as PAS à le faire.

Tu es un expert en ingénierie de prompts pour la photographie de produits IA en production cinématographique.

L'utilisateur décrit un accessoire ou un prop (bijou, arme, pièce de costume, etc.).
Transforme l'entrée en un prompt optimisé pour la génération d'images Nano Banana.

Exigences :
- Photographie de produit cinématographique haute qualité
- Fond uni blanc pur — absolument pas de scène, d'environnement, de texture, de décor
- Éclairage studio doux et uniforme, pas d'ombres dures
- AUCUNE personne, AUCUN modèle, AUCUN corps, AUCUN visage, AUCUNE main — l'objet doit apparaître seul
- Angles multiples suggérés (face, côté, gros plan détail)
- Qualité de référence prop professionnel film/TV
- Adapté comme référence visuelle pour la conception de production et Seedance 2.0

TERMES INTERDITS : "photorealistic", "ultra-detailed", "highly detailed", "8K", "Unreal Engine", "Octane Render".
CRITIQUE : Supprimer tout nom de personnage ou personne de l'entrée. La sortie doit montrer UNIQUEMENT l'objet isolé.

Retourne UNIQUEMENT le prompt optimisé en français. Pas d'explication, pas de préfixe, pas de guillemets.\
"""

_OPTIMIZE_HMC_SYSTEM = """\
LANGUE DE RÉPONSE : Réponds TOUJOURS en français, quelle que soit la langue du texte en entrée. Le prompt de sortie DOIT être rédigé en français — l'utilisateur doit pouvoir le lire et le vérifier. La traduction en anglais pour le modèle IA est effectuée automatiquement en aval, tu n'as PAS à le faire.

Tu es un expert en ingénierie de prompts pour la photographie mode/maquillage/coiffure IA en production cinématographique.

L'utilisateur décrit un costume (Habit), un look de maquillage (Maquillage) ou une coiffure (Coiffure).
Transforme l'entrée en un prompt optimisé pour la génération d'images Nano Banana.

Exigences :
- Photographie de mode/beauté cinématographique haute qualité
- Fond uni blanc pur — pas de scène, pas d'environnement, pas de décor
- Éclairage éditorial studio professionnel
- Pour Habit : vêtement complet sur un mannequin sans tête/sans visage ou à plat — AUCUNE personne, AUCUN visage, AUCUN individu reconnaissable, vêtement uniquement
- Pour Maquillage : gros plan sur une tête de mannequin de maquillage sans visage — absolument AUCUN vrai visage, AUCUN œil, AUCUNE bouche, AUCUNE personne reconnaissable — le mannequin doit être clairement sans traits, sur fond blanc pur
- Pour Coiffure : cheveux sur un mannequin perruque sans visage — AUCUNE personne reconnaissable, AUCUN visage, mèche uniquement
- Adapté comme référence de coiffage de personnage pour la production cinématographique

TERMES INTERDITS : "photorealistic", "ultra-detailed", "highly detailed", "8K", "Unreal Engine".
CRITIQUE : Supprimer tout nom de personnage ou personne spécifique de l'entrée.
Montrer uniquement le vêtement, le maquillage ou la coiffure en isolation complète.

Retourne UNIQUEMENT le prompt optimisé en français. Pas d'explication, pas de préfixe, pas de guillemets.\
"""

_OPTIMIZE_DECOR_SYSTEM = """\
LANGUE DE RÉPONSE : Réponds TOUJOURS en français, quelle que soit la langue du texte en entrée. Le prompt de sortie DOIT être rédigé en français — l'utilisateur doit pouvoir le lire et le vérifier. La traduction en anglais pour le modèle IA est effectuée automatiquement en aval, tu n'as PAS à le faire.

Tu es un expert en ingénierie de prompts pour la photographie de lieux et décors IA en production cinématographique.

L'utilisateur décrit un lieu de tournage ou un décor (intérieur, extérieur, paysage naturel, environnement urbain, etc.).
Transforme l'entrée en un prompt optimisé pour la génération d'images Nano Banana.

Exigences :
- Photographie architecturale ou de paysage cinématographique haute qualité
- Plan large d'établissement cinématographique — montrer l'espace et l'atmosphère complète
- Qualité de référence de lieu professionnel film/TV
- Éclairage cinématographique dramatique adapté au décor et à l'heure du jour
- Pour les intérieurs : plan large montrant la pièce/l'espace entier, les meubles, les accessoires, l'ambiance
- Pour les extérieurs : plan large d'établissement montrant l'environnement, le ciel, la profondeur, l'ambiance
- Inclure les conditions atmosphériques si pertinent (brouillard, pluie, heure dorée, etc.)
- AUCUNE personne, AUCUN personnage, AUCUNE silhouette dans le cadre
- Adapté comme référence de lieu pour la production cinématographique et Seedance 2.0

TERMES INTERDITS : "photorealistic", "ultra-detailed", "highly detailed", "8K", "Unreal Engine", "Octane Render".

Retourne UNIQUEMENT le prompt optimisé en français. Pas d'explication, pas de préfixe, pas de guillemets.\
"""

_OPTIMIZE_STYLE_REF_SYSTEM = """\
LANGUE DE RÉPONSE : Réponds TOUJOURS en français, quelle que soit la langue du texte en entrée. Le prompt de sortie DOIT être rédigé en français — l'utilisateur doit pouvoir le lire et le vérifier. La traduction en anglais pour le modèle IA est effectuée automatiquement en aval, tu n'as PAS à le faire.

Tu es un expert en ingénierie de prompts pour la génération d'images IA en production cinématographique.

L'utilisateur fournit UNE OU PLUSIEURS IMAGES DE RÉFÉRENCE dont le STYLE VISUEL doit être reproduit, ainsi qu'optionnellement une description de l'élément à générer.

Ta tâche :
1. ANALYSER le style visuel de l'image de référence : medium de rendu (illustration 2D, anime, cel-shading, aquarelle, peinture à l'huile, pastel, rendu 3D stylisé, esquisse au trait, photographie réelle, etc.), palette chromatique dominante, texture des surfaces, traitement des contours, atmosphère générale.
2. PRODUIRE un prompt qui :
   - REPRODUIT FIDÈLEMENT ce style visuel — si la référence est une illustration animée, le résultat DOIT être une illustration animée ; si c'est une aquarelle, le résultat DOIT être une aquarelle, etc.
   - N'impose JAMAIS un rendu photoréaliste si la référence est stylisée ou illustrative
   - Intègre la description de l'élément fournie par l'utilisateur dans ce style
   - Reste sous 180 mots

INTERDIT ABSOLU : Ne jamais transposer un style illustré, animé ou pictural vers le photoréalisme. Le style de la référence prime sur tout.

Retourne UNIQUEMENT le prompt optimisé en français. Pas d'explication, pas de préfixe, pas de guillemets.\
"""

# ── Optimiseur de prompt pour créatures non-humaines ─────────────────────────

_OPTIMIZE_CREATURE_SYSTEM = """\
LANGUE DE RÉPONSE : Réponds TOUJOURS en français, quelle que soit la langue du texte en entrée. Le prompt de sortie DOIT être rédigé en français — l'utilisateur doit pouvoir le lire et le vérifier. La traduction en anglais pour le modèle IA est effectuée automatiquement en aval, tu n'as PAS à le faire.

Tu es un expert en ingénierie de prompts pour la génération de créatures et entités non-humaines IA en production cinématographique.

L'utilisateur décrit une créature non-humaine (dragon, monstre, alien, démon, golem, bête, créature fantastique, robot organique, etc.).
Transforme l'entrée en un prompt optimisé pour la génération d'images Nano Banana.

Exigences ABSOLUES :
- Corps entier TOUJOURS — jamais de cadrage tête/épaules — la créature doit être visible de la tête aux pattes/pieds
- Fond blanc pur et uni — la créature doit être complètement isolée sur fond blanc, sans ombre portée
- AUCUN décor, AUCUN environnement, AUCUNE scène, AUCUN sol, AUCUN arrière-plan
- AUCUN personnage humain, AUCUN humain, AUCUNE silhouette humaine
- Décris avec précision l'anatomie complète : silhouette, membres, ailes (si applicable), queue, posture
- Décris les textures corporelles : écailles, fourrure, carapace, cristaux, chair, os — couleurs exactes et reflets
- Décris la tête : forme, yeux, gueule/bec/crocs, cornes, crêtes, éléments distinctifs
- Éclairage studio doux et uniforme — pas d'éclairage dramatique de scène
- Si un style visuel est indiqué (ex. Cyberpunk Néon), applique-le UNIQUEMENT aux couleurs, textures et matériaux de la créature — le fond reste blanc
- Qualité de référence département artistique film/TV, ultra-détaillé

CRITIQUE : La sortie est une CRÉATURE non-humaine isolée sur fond blanc. Jamais un humain, jamais une scène.

Retourne UNIQUEMENT le prompt optimisé en français. Pas d'explication, pas de préfixe, pas de guillemets.\
"""

# Mots-clés déclenchant le mode créature (FR + EN)
_CREATURE_KEYWORDS = {
    # Français
    "dragon", "monstre", "créature", "bête", "démon", "alien", "extraterrestre",
    "golem", "troll", "ogre", "géant", "elfe", "nain", "gnome", "orc", "gobelin",
    "loup-garou", "vampire", "zombie", "mort-vivant", "esprit", "fantôme", "démon",
    "chimère", "sphinx", "griffon", "licorne", "sirène", "hydre", "serpent géant",
    "kraken", "phénix", "banshee", "cyclope", "minotaure", "centaure", "manticore",
    "basilic", "wyvern", "liche",
    # Anglais
    "dragon", "monster", "creature", "beast", "demon", "daemon", "alien",
    "golem", "troll", "orc", "goblin", "ogre", "giant", "elf", "dwarf",
    "werewolf", "vampire", "zombie", "undead", "ghost", "phantom",
    "chimera", "griffin", "unicorn", "mermaid", "hydra", "kraken", "phoenix",
    "banshee", "cyclops", "minotaur", "centaur", "manticore", "basilisk", "wyvern",
    "lich", "gargoyle", "djinn", "genie",
}


def _get_lang() -> str:
    try:
        from core.i18n import get_lang
        return get_lang()
    except Exception:
        return "fr"


def _apply_lang_to_system(system: str, lang: str) -> str:
    """Replace French-output instructions with English-output instructions when lang=='en'."""
    if lang != "en":
        return system
    result = system.replace(
        "LANGUE DE RÉPONSE : Réponds TOUJOURS en français, quelle que soit la langue du texte en entrée. "
        "Le prompt de sortie DOIT être rédigé en français — l'utilisateur doit pouvoir le lire et le vérifier. "
        "La traduction en anglais pour le modèle IA est effectuée automatiquement en aval, tu n'as PAS à le faire.",
        "OUTPUT LANGUAGE: Always respond in English. The output prompt MUST be written in English — "
        "the user reads and verifies it directly. Do NOT translate to French or any other language."
    )
    result = result.replace(
        "Retourne UNIQUEMENT le prompt optimisé en français.",
        "Return ONLY the optimized prompt in English."
    )
    return result


def _build_image_args(prompt: str, aspect_ratio: str = "1:1",
                      resolution: str = "1K", cfg: dict | None = None,
                      num_images: int = 1) -> tuple[str, dict]:
    """Construit l'endpoint et les arguments API NB2/NB-Pro. Retourne (endpoint_id, args_dict)."""
    if cfg is None:
        cfg = load_config()
    endpoint = get_image_endpoint(cfg)
    args = {
        "prompt":           prompt,
        "num_images":       max(1, num_images),
        "aspect_ratio":     aspect_ratio,
        "resolution":       resolution,
        "output_format":    "png",
        "safety_tolerance": "6",
    }
    return endpoint, args


def _is_creature(text: str) -> bool:
    """Détecte si le texte décrit une créature non-humaine."""
    words = set(text.lower().replace(",", " ").replace(".", " ").split())
    return bool(words & _CREATURE_KEYWORDS)


# Sheet suffix spécifique créatures — remplace "PERSON" par "creature"
_SHEET_SUFFIX_CREATURE = (
    "Character reference turnaround sheet — ONE single image containing 5 views "
    "of THE EXACT SAME CREATURE.\n"
    "Top row (left to right): "
    "full-body front view · full-body back view · "
    "full-body three-quarter left view · full-body three-quarter right view.\n"
    "Bottom center: close-up head portrait of the creature.\n"
    "CRITICAL: All 5 views MUST show the IDENTICAL creature — "
    "same body shape, same colors, same textures, same features, same proportions. "
    "Zero variation between views.\n"
    "Pure white seamless studio background throughout — no environment, no ground shadow, "
    "no scene, no backdrop details. Creature completely isolated on white.\n"
    "ABSOLUTELY NO HUMAN, no human face, no human silhouette anywhere in the image.\n"
    "Professional film/TV creature design reference sheet.\n"
    "ABSOLUTELY NO TEXT anywhere on the image — no labels, no names, no annotations, "
    "no view indicators, no watermarks, no captions, no numbers. "
    "Pure clean image only."
)


# ── Vues individuelles pour le pipeline 5-portraits-séparés ──────────────────
# (key, instruction_de_pose, use_pulid)
# use_pulid=True  → fal-ai/flux-pulid avec reference_image_url + id_weight 0.85
# use_pulid=False → fal-ai/flux/dev sans injection d'identité (vue dos : pas de visage)
_VIEW_DEFS = [
    # Syntaxe "Change the angle to..." — signal actif de recadrage (Gemini INSIGHT_1).
    # Ancrage "bords du cadre" renforcé (Gemini IMPROVEMENT_3) :
    #   pieds visibles en bas du cadre + vaste environnement au-dessus → force Flux à dézoomer
    #   avant que PuLID ne "tire" la caméra vers le visage.
    ("front",
     "Change the angle to a full-body FRONT VIEW. "
     "Camera is positioned at a distance. "
     "Subject's feet are visibly touching the ground at the bottom of the frame, "
     "vast environment visible above and around. "
     "Entire body from head to feet, standing pose, arms relaxed.",
     True),
    ("34",
     "Change the angle to a full-body THREE-QUARTER VIEW (45° left turn). "
     "Camera is positioned at a distance. "
     "Subject's feet are visibly touching the ground at the bottom of the frame, "
     "vast environment visible above and around. "
     "Entire body from head to feet, slight turn to the left.",
     True),
    ("profile",
     "Change the angle to a full-body SIDE PROFILE VIEW (90° left). "
     "Camera is positioned at a distance. "
     "Subject's feet are visibly touching the ground at the bottom of the frame, "
     "vast environment visible above and around. "
     "Entire body from head to feet, pure side angle.",
     True),
    ("back",
     "Change the angle to a full-body BACK VIEW. "
     "Camera is positioned at a distance. "
     "Subject's feet are visibly touching the ground at the bottom of the frame, "
     "vast environment visible above and around. "
     "Entire body from head to feet, subject fully turned away.",
     False),
    ("bust",
     "Change the angle to a close-up HEAD AND SHOULDERS portrait, front-facing. "
     "Tight framing showing face and upper chest only. Direct eye contact with camera.",
     True),
]

_INDIVIDUAL_PORTRAIT_SUFFIX = (
    "White seamless studio background. Professional film/TV casting photography reference. "
    "No text, no labels, no watermarks, no borders."
)

# ── Lignes automatiquement ajoutées au prompt envoyé à Nano Banana ────────────
_ITEM_LINE = (
    "Isolated product shot on a pure white seamless background. "
    "No person, no face, no character, no model. "
    "No scene, no environment, no backdrop. "
    "If the item is a garment, costume or wig, display it in ghost-mannequin style — "
    "worn three-dimensional shape with no visible person. "
    "Professional studio product photography, soft diffused lighting, "
    "true-to-life materials and colors, ultra-detailed textures, sharp focus."
)

_VEHICLE_LINE = (
    "Isolated automotive product shot on a pure white seamless background. "
    "No person, no driver, no road, no street, no environment, no sky, no backdrop. "
    "Professional studio automotive photography — 3/4 front angle, full vehicle visible, no cropping. "
    "Clean white studio backdrop, soft diffused lighting with subtle reflections."
)

# Suffix décors : image de lieu réaliste, pas de fond blanc
_DECOR_LINE = (
    "Cinematic location photograph. "
    "Wide establishing shot showing the full environment, architecture, landscape or set. "
    "Rich atmospheric lighting, depth and mood. "
    "No people, no characters, no figures anywhere in the frame. "
    "Professional film/TV location reference quality. "
    "NOT a product shot — NOT a white background — this is a real place, real light, real atmosphere. "
    "Ultra-detailed, sharp focus, high dynamic range, photorealistic."
)
_DECOR_SHEET_SUFFIX = (
    "Film production location reference sheet — ONE single image divided into 4 panels "
    "showing THE EXACT SAME LOCATION from different angles.\n"
    "Layout (2×2 grid):\n"
    "Top-left: FRONT VIEW — main camera angle, wide establishing shot.\n"
    "Top-right: BACK VIEW — reverse angle, shooting from the opposite direction.\n"
    "Bottom-left: LEFT SIDE VIEW — lateral 90° from the left.\n"
    "Bottom-right: RIGHT SIDE VIEW — lateral 90° from the right.\n"
    "CRITICAL: All 4 panels MUST show THE IDENTICAL LOCATION — "
    "same architecture, same materials, same props, same lighting, same atmosphere. "
    "Zero variation in appearance between panels.\n"
    "Real environment, real light, real textures. Wide angle photography. "
    "Professional film/TV location scouting reference sheet.\n"
    "ABSOLUTELY NO TEXT anywhere on the image — no labels, no view names (FRONT / BACK / LEFT / RIGHT), "
    "no annotations, no captions, no watermarks. Pure clean image only."
)

_SHEET_SUFFIX = (
    "Character reference turnaround sheet — ONE single image containing 5 views "
    "of THE EXACT SAME PERSON.\n"
    "Top row (left to right): "
    "full-body front view · full-body back view · "
    "full-body three-quarter left view · full-body three-quarter right view.\n"
    "Bottom center: close-up head-and-shoulders portrait.\n"
    "CRITICAL: All 5 views MUST show the IDENTICAL character — "
    "same face, same hair color and style, same costume, same body proportions. "
    "Zero variation in appearance between views.\n"
    "White seamless studio background throughout. "
    "Professional film/TV casting turnaround sheet.\n"
    "ABSOLUTELY NO TEXT anywhere on the image — no labels, no names, no annotations, "
    "no view indicators (FRONT / BACK / SIDE), no watermarks, no captions, no numbers. "
    "Pure clean image only. Exception: only if the prompt explicitly requests writing "
    "on clothing or props (e.g. text on a t-shirt or cap)."
)


# ── Worker : optimisation du prompt via Claude ────────────────────────────────

class OptimizePromptWorker(QThread):
    finished = pyqtSignal(str)
    failed   = pyqtSignal(str)

    def __init__(self, description: str, style_suffix: str = ""):
        super().__init__()
        self._desc         = description
        self._style_suffix = style_suffix

    def run(self):
        cfg = load_config()
        key = cfg.get("anthropic_key", "").strip()
        if not key:
            self.failed.emit("Clé API Anthropic manquante.\nConfigure-la dans Paramètres.")
            return
        try:
            import anthropic
            lang = _get_lang()
            client = anthropic.Anthropic(api_key=key)
            user_msg = self._desc
            if self._style_suffix:
                user_msg = f"{user_msg}\n\n[Style visuel du projet : {self._style_suffix}]"
            _base_sys = _OPTIMIZE_CREATURE_SYSTEM if _is_creature(self._desc) else _OPTIMIZE_SYSTEM
            system = _apply_lang_to_system(_base_sys, lang)
            msg = client.messages.create(
                model="claude-haiku-4-5",
                max_tokens=350,
                system=system,
                messages=[{"role": "user", "content": user_msg}],
            )
            self.finished.emit(msg.content[0].text.strip())
        except Exception as e:
            self.failed.emit(f"Erreur Anthropic : {e}")


# ── Worker : optimisation du prompt avec images de référence ─────────────────

class OptimizeWithReferencesWorker(QThread):
    finished = pyqtSignal(str)
    failed   = pyqtSignal(str)

    _SYSTEM = _OPTIMIZE_SYSTEM  # subclasses override to use their domain system prompt

    def __init__(self, text: str, image_paths: list, style_suffix: str = ""):
        super().__init__()
        self._text         = text
        self._paths        = image_paths
        self._style_suffix = style_suffix

    def run(self):
        cfg = load_config()
        key = cfg.get("anthropic_key", "").strip()
        if not key:
            self.failed.emit("Clé API Anthropic manquante.\nConfigure-la dans Paramètres.")
            return
        try:
            import anthropic, base64
            from pathlib import Path

            lang = _get_lang()
            client = anthropic.Anthropic(api_key=key)
            _mime = {
                "jpg": "image/jpeg", "jpeg": "image/jpeg",
                "png": "image/png",  "webp": "image/webp", "bmp": "image/bmp",
            }
            content = []
            for path in self._paths:
                with open(path, "rb") as f:
                    data = base64.standard_b64encode(f.read()).decode()
                mt = _mime.get(Path(path).suffix.lower().lstrip("."), "image/jpeg")
                content.append({
                    "type": "image",
                    "source": {"type": "base64", "media_type": mt, "data": data},
                })

            n = len(self._paths)
            if self._text:
                user_text = (
                    f"Current prompt: {self._text}\n\n"
                    f"Analyze these {n} reference image(s) and produce an optimized "
                    f"prompt incorporating visual details from the references."
                )
            else:
                user_text = (
                    f"Analyze these {n} reference image(s) and produce an optimized "
                    f"prompt based solely on what you observe."
                )
            content.append({"type": "text", "text": user_text})

            msg = client.messages.create(
                model="claude-haiku-4-5",
                max_tokens=350,
                system=_apply_lang_to_system(self._SYSTEM, lang),
                messages=[{"role": "user", "content": content}],
            )
            self.finished.emit(msg.content[0].text.strip())
        except Exception as e:
            self.failed.emit(f"Erreur Anthropic : {e}")


class OptimizeCharacterWithReferencesWorker(OptimizeWithReferencesWorker):
    """Optimise un prompt personnage en analysant le visage des photos de référence."""
    _SYSTEM = _OPTIMIZE_CHARACTER_WITH_REF_SYSTEM

    def run(self):
        cfg = load_config()
        key = cfg.get("anthropic_key", "").strip()
        if not key:
            self.failed.emit("Clé API Anthropic manquante.\nConfigure-la dans Paramètres.")
            return
        try:
            import anthropic, base64
            from pathlib import Path

            lang = _get_lang()
            client = anthropic.Anthropic(api_key=key)
            _mime = {
                "jpg": "image/jpeg", "jpeg": "image/jpeg",
                "png": "image/png",  "webp": "image/webp", "bmp": "image/bmp",
            }
            content = []
            for path in self._paths:
                if not os.path.isfile(path):
                    continue
                with open(path, "rb") as f:
                    data = base64.standard_b64encode(f.read()).decode()
                mt = _mime.get(Path(path).suffix.lower().lstrip("."), "image/jpeg")
                content.append({
                    "type": "image",
                    "source": {"type": "base64", "media_type": mt, "data": data},
                })

            if not content:
                self.failed.emit("Aucune image de référence valide trouvée.")
                return

            user_text = (
                f"Character description: {self._text}\n\n"
                if self._text else
                "No character description provided — base the prompt solely on the reference photo(s).\n\n"
            )
            user_text += (
                "Analyze the face(s) in the reference photo(s) above and produce an optimized "
                "Nano Banana prompt that will reproduce this person's face exactly."
            )
            if self._style_suffix:
                user_text += f"\n\n[Style visuel du projet : {self._style_suffix}]"
            content.append({"type": "text", "text": user_text})

            msg = client.messages.create(
                model="claude-opus-4-7",
                max_tokens=400,
                system=_apply_lang_to_system(self._SYSTEM, lang),
                messages=[{"role": "user", "content": content}],
            )
            self.finished.emit(msg.content[0].text.strip())
        except Exception as e:
            self.failed.emit(f"Erreur Anthropic : {e}")


class OptimizeVehicleWithReferencesWorker(OptimizeWithReferencesWorker):
    """Optimise un prompt véhicule avec images de référence (fond blanc, isolé)."""
    _SYSTEM = _OPTIMIZE_VEHICLE_SYSTEM


class OptimizeAccessoryWithReferencesWorker(OptimizeWithReferencesWorker):
    """Optimise un prompt accessoire/prop avec images de référence."""
    _SYSTEM = _OPTIMIZE_ACCESSORY_SYSTEM


class OptimizeHMCWithReferencesWorker(OptimizeWithReferencesWorker):
    """Optimise un prompt HMC avec images de référence."""
    _SYSTEM = _OPTIMIZE_HMC_SYSTEM


class OptimizeDecorWithReferencesWorker(OptimizeWithReferencesWorker):
    """Optimise un prompt décor/lieu avec images de référence."""
    _SYSTEM = _OPTIMIZE_DECOR_SYSTEM


class OptimizeStyleReferenceWorker(OptimizeWithReferencesWorker):
    """Extrait le style visuel de l'image de référence et génère un prompt qui le reproduit.
    Utilisé quand ref_usage == 'style' — tous types d'éléments (perso, décor, accessoire, etc.).
    Ne force jamais le photoréalisme si la référence est illustrée ou animée."""
    _SYSTEM = _OPTIMIZE_STYLE_REF_SYSTEM

    def run(self):
        cfg = load_config()
        key = cfg.get("anthropic_key", "").strip()
        if not key:
            self.failed.emit("Clé API Anthropic manquante.\nConfigure-la dans Paramètres.")
            return
        try:
            import anthropic, base64
            from pathlib import Path

            lang = _get_lang()
            client = anthropic.Anthropic(api_key=key)
            _mime = {
                "jpg": "image/jpeg", "jpeg": "image/jpeg",
                "png": "image/png",  "webp": "image/webp", "bmp": "image/bmp",
            }
            content = []
            for path in self._paths:
                if not os.path.isfile(path):
                    continue
                with open(path, "rb") as f:
                    data = base64.standard_b64encode(f.read()).decode()
                mt = _mime.get(Path(path).suffix.lower().lstrip("."), "image/jpeg")
                content.append({
                    "type": "image",
                    "source": {"type": "base64", "media_type": mt, "data": data},
                })

            if not content:
                self.failed.emit("Aucune image de référence valide trouvée.")
                return

            user_text = (
                "REFERENCE IMAGE(S) — STYLE ONLY: Extract ONLY the pictural/visual style "
                "of these reference images (rendering medium, color palette, lighting mood, "
                "texture, line treatment, overall artistic aesthetic). "
                "DO NOT describe, reproduce, or incorporate any scene content, subjects, "
                "characters, objects, or actions from the reference — extract ONLY the "
                "artistic/visual style.\n\n"
            )
            if self._text:
                user_text += (
                    f"ELEMENT TO STYLE (keep this concept intact, only change the visual style): "
                    f"{self._text}\n\n"
                )
            user_text += (
                "Apply the extracted pictural style to the element above, "
                "keeping the user's original concept and subject entirely unchanged. "
                "Output only the styled prompt."
            )
            content.append({"type": "text", "text": user_text})

            msg = client.messages.create(
                model="claude-haiku-4-5",
                max_tokens=350,
                system=_apply_lang_to_system(self._SYSTEM, lang),
                messages=[{"role": "user", "content": content}],
            )
            self.finished.emit(msg.content[0].text.strip())
        except Exception as e:
            self.failed.emit(f"Erreur Anthropic : {e}")


# ── Worker : génération du portrait via Nano Banana ───────────────────────────

_CLASSIC_PORTRAIT_SUFFIX = (
    "Single character portrait. White seamless studio background. "
    "Professional film/TV casting photograph. Head-and-shoulders or full-body framing. "
    "Natural skin texture, soft professional studio lighting, "
    "ultra-detailed, sharp focus. "
    "No text, no labels, no watermarks."
)

_EDITORIAL_PORTRAIT_SUFFIX = (
    "Close-up editorial portrait. Tight head-and-shoulders framing. "
    "Dramatic Rembrandt studio lighting, deep shadows, warm rim light. "
    "Film/TV casting photograph quality, natural skin texture and pores. "
    "White seamless background. No text, no labels."
)

_ACTION_POSE_SUFFIX = (
    "Full-body dynamic action pose. Expressive movement, mid-action. "
    "White seamless studio background, professional film production reference. "
    "Crisp motion, natural fabric and skin texture, ultra-detailed, sharp focus. "
    "No text, no labels."
)

_DUO_PORTRAIT_SUFFIX = (
    "Two characters side by side, full-body front view. "
    "White seamless studio background. Both characters fully visible, equal framing. "
    "Professional film/TV casting reference. "
    "Natural skin texture, soft studio lighting, ultra-detailed, sharp focus. "
    "No text, no labels."
)


class GeneratePortraitWorker(QThread):
    progress       = pyqtSignal(int, str)
    finished       = pyqtSignal(str, str)  # (portrait_path, sheet_path)
    multi_finished = pyqtSignal(list)      # list[str] — N>1 images
    failed         = pyqtSignal(str)

    # gen_mode values : "sheet_5views" | "classic" | "editorial" | "action" | "duo"
    def __init__(self, prompt: str, char_name: str, ref_paths: list | None = None,
                 gen_mode: str = "sheet_5views", model_key: str | None = None,
                 num_images: int = 1,
                 ref_usage: str = "inspiration",
                 style_ref_path: str = ""):
        super().__init__()
        self._prompt          = prompt
        self._name            = char_name
        self._ref_paths       = [p for p in (ref_paths or []) if p and os.path.isfile(p)]
        self._gen_mode        = gen_mode
        self._model_key       = model_key
        self._num_images      = max(1, num_images)
        self._ref_usage       = ref_usage
        self._style_ref_path  = style_ref_path

    def run(self):
        cfg = load_config()
        key = cfg.get("api_key", "").strip()
        if not key:
            self._mock()
        else:
            self._real(key)

    # ── Mock ──────────────────────────────────────────────────────────────────

    def _mock(self):
        _mode_labels = {
            "sheet_5views": "Character sheet 5 vues",
            "classic":      "Portrait classique",
            "editorial":    "Portrait éditorial",
            "action":       "Pose d'action",
            "duo":          "Portrait duo",
        }
        _lbl = _mode_labels.get(self._gen_mode, "Portrait")
        steps = [
            (15, "Connexion à Nano Banana (mode mock)…"),
            (50, f"Génération — {_lbl}…"),
            (85, "Post-traitement…"),
            (100, "Terminé — mode mock actif"),
        ]
        for pct, msg in steps:
            self.progress.emit(pct, msg)
            time.sleep(0.5)
        self.finished.emit("", "")

    # ── Réel ──────────────────────────────────────────────────────────────────

    def _real(self, key: str):
        try:
            import fal_client
            import requests
            from core.lang import translate_to_english

            os.environ["FAL_KEY"] = key

            safe = "".join(c for c in self._name if c.isalnum() or c in " -_").strip() or "character"
            ts   = int(time.time())
            dest = _project_images_dir("castings")

            # Traduit le prompt utilisateur (peut être en français) → anglais pour l'API
            prompt_en = translate_to_english(self._prompt) if self._prompt else ""

            # Vision analysis — style pictural
            if self._ref_usage == "style" and self._style_ref_path and os.path.isfile(self._style_ref_path):
                _nb_cfg = load_config()
                _nb_key = _nb_cfg.get("anthropic_key", "").strip()
                if _nb_key:
                    self.progress.emit(5, "Analyse du style de l'image de référence…")
                    _vs = analyze_style_for_image(self._style_ref_path, _nb_key)
                    if _vs:
                        prompt_en = f"{_vs}, {prompt_en}" if prompt_en else _vs

            cfg = load_config()
            if self._model_key:
                cfg = dict(cfg)
                cfg["image_model"] = self._model_key
            price = get_image_price(cfg)

            # Sélection du suffix + aspect_ratio selon le mode de génération
            _mode = self._gen_mode
            if _mode == "sheet_5views":
                _sfx        = _SHEET_SUFFIX_CREATURE if _is_creature(self._prompt) else _SHEET_SUFFIX
                _msg_start  = "Génération du character sheet 5 vues…"
                _ar         = "16:9"
            elif _mode == "editorial":
                _sfx        = _EDITORIAL_PORTRAIT_SUFFIX
                _msg_start  = "Génération du portrait éditorial…"
                _ar         = "1:1"
            elif _mode == "action":
                _sfx        = _ACTION_POSE_SUFFIX
                _msg_start  = "Génération de la pose d'action…"
                _ar         = "9:16"
            elif _mode == "duo":
                _sfx        = _DUO_PORTRAIT_SUFFIX
                _msg_start  = "Génération du portrait duo…"
                _ar         = "16:9"
            else:  # "classic"
                _sfx        = _SHEET_SUFFIX_CREATURE if _is_creature(self._prompt) else _CLASSIC_PORTRAIT_SUFFIX
                _msg_start  = "Génération du portrait classique…"
                _ar         = "2:3"

            # Si style extrait d'une image de référence, pas de suffix photoréaliste
            if self._ref_usage == "style" and self._style_ref_path and os.path.isfile(self._style_ref_path):
                _sfx = ""

            # Encode la première image de référence comme face anchor (NB2/NB-Pro only)
            ref_url = None
            _active_model = cfg.get("image_model", "nb2")
            if self._ref_paths and _active_model in ("nb2", "nb_pro"):
                self.progress.emit(8, "Encodage de la photo de référence…")
                try:
                    import base64, mimetypes
                    _mime = mimetypes.guess_type(self._ref_paths[0])[0] or "image/png"
                    with open(self._ref_paths[0], "rb") as _rf:
                        ref_url = f"data:{_mime};base64,{base64.b64encode(_rf.read()).decode()}"
                except Exception:
                    pass

            face_instruction = ""
            if ref_url:
                face_instruction = (
                    "CRITICAL FACE MATCH: The character's face, skin tone, eye color, "
                    "nose shape, jaw line, and all facial features MUST be an exact "
                    "reproduction of the person shown in the reference image. "
                    "The reference photo is the primary visual source — the character "
                    "description defines the costume and context only. "
                    "Do NOT invent a face. Use the reference face exactly.\n\n"
                )

            n = self._num_images
            full_prompt = f"{face_instruction}{prompt_en}\n\n{_sfx}"

            if n > 1:
                # N separate calls (num_images=1 each) — avoids API limit on batch size
                paths = []
                for i in range(n):
                    self.progress.emit(
                        10 + int(i / n * 70),
                        f"[{i+1}/{n}] {_msg_start}  ({price})"
                    )
                    _ep, _args = _build_image_args(full_prompt, _ar, "1K", cfg, 1)
                    if ref_url and _active_model in ("nb2", "nb_pro"):
                        _args["image_url"] = ref_url
                    _result = fal_client.subscribe(_ep, arguments=_args)
                    _url = _extract_image_url(_result)
                    data = requests.get(_url, timeout=120).content
                    p = os.path.join(dest, f"{safe}_{ts}_portrait_{i}.png")
                    with open(p, "wb") as f:
                        f.write(data)
                    paths.append(p)
                    self.progress.emit(
                        10 + int((i + 1) / n * 70),
                        f"Portrait {i+1}/{n} téléchargé…"
                    )
                self.progress.emit(100, f"{len(paths)} portraits générés !")
                self.multi_finished.emit(paths)
            else:
                self.progress.emit(10, f"{_msg_start}  ({price})")
                _ep, _args = _build_image_args(full_prompt, _ar, "1K", cfg, 1)
                if ref_url and _active_model in ("nb2", "nb_pro"):
                    _args["image_url"] = ref_url
                result = fal_client.subscribe(_ep, arguments=_args)
                self.progress.emit(80, "Téléchargement de l'image…")
                url  = _extract_image_url(result)
                data = requests.get(url, timeout=120).content
                sheet_path = os.path.join(dest, f"{safe}_{ts}_sheet.png")
                with open(sheet_path, "wb") as f:
                    f.write(data)
                self.progress.emit(100, "Portrait généré !")
                self.finished.emit("", sheet_path)

        except Exception as e:
            self.failed.emit(humanize_api_error(f"Erreur Nano Banana : {e}"))


# ── Storyboard sketch generation ─────────────────────────────────────────────

_STORYBOARD_SKETCH_SUFFIX = (
    "Hand-drawn storyboard frame. Rough pencil sketch style. Black and white. "
    "Simple gestural line art. Quick directorial thumbnail composition. "
    "Film production storyboard drawing. No color, no rendering, no texture fills. "
    "No text, no labels, no annotations, no watermarks."
)

_FOCAL_FRAMING = [
    (100, "extreme close-up"),
    (65,  "close-up shot"),
    (40,  "medium shot"),
    (28,  "medium-wide shot"),
    (18,  "wide shot"),
    (0,   "extreme wide establishing shot"),
]


def _shot_to_sketch_prompt(shot: dict) -> str:
    """Builds an image-generation prompt from shot data for storyboard sketch style."""
    focal_str = shot.get("focal", "") or ""
    focal_num = 0
    try:
        focal_num = int(focal_str.replace("mm", "").strip())
    except (ValueError, AttributeError):
        pass

    framing = "scene"
    for threshold, label in _FOCAL_FRAMING:
        if focal_num >= threshold:
            framing = label
            break

    chars    = ", ".join(shot.get("character_names", []) or [])
    scene    = (shot.get("scene_title", "") or "").strip()
    action   = (shot.get("comments", "") or "").strip()[:200]
    decor    = (shot.get("decor_name", "") or "").strip()
    movement = (shot.get("camera_movement", "") or "").strip()
    axis     = (shot.get("camera_axis", "") or "").strip()

    parts = [framing]
    if chars:
        parts.append(chars)
    if scene:
        parts.append(scene)
    if action and action != scene:
        parts.append(action)
    if decor:
        parts.append(f"setting: {decor}")
    if movement and movement not in ("Fixe", ""):
        parts.append(f"camera {movement}")
    if axis:
        parts.append(f"{axis} axis")

    return ", ".join(parts)


class GenerateStoryboardSketchesWorker(QThread):
    """Generates Nano Banana storyboard sketch images for a batch of shots."""
    shot_done = pyqtSignal(str, str)   # (shot_id, local_image_path)
    progress  = pyqtSignal(int, str)
    finished  = pyqtSignal()
    failed    = pyqtSignal(str)

    def __init__(self, shots: list):
        super().__init__()
        self._shots = shots

    def run(self):
        from core.context import get_data_root
        total = len(self._shots)
        if total == 0:
            self.finished.emit()
            return

        img_dir = os.path.join(get_data_root(), "storyboard", "images")
        os.makedirs(img_dir, exist_ok=True)

        cfg = load_config()
        key = cfg.get("api_key", "").strip()

        for i, shot in enumerate(self._shots):
            if self.isInterruptionRequested():
                break
            plan = shot.get("number", i + 1)
            self.progress.emit(int(i / total * 100), f"Plan {plan} ({i + 1}/{total})…")

            path = self._real(shot, key, img_dir, i) if key else self._mock(shot)
            if path:
                self.shot_done.emit(shot.get("id", ""), path)

        self.progress.emit(100, f"{total} aperçu(s) générés ✓")
        self.finished.emit()

    def _mock(self, shot: dict) -> str:
        time.sleep(0.2)
        return ""

    def _real(self, shot: dict, key: str, img_dir: str, idx: int) -> str:
        try:
            import fal_client
            import requests
            from core.lang import translate_to_english

            os.environ["FAL_KEY"] = key

            raw_prompt = _shot_to_sketch_prompt(shot)
            prompt_en  = translate_to_english(raw_prompt)
            full_prompt = f"{prompt_en}\n\n{_STORYBOARD_SKETCH_SUFFIX}"

            # Sketches storyboard → Flux Schnell par défaut (~$0.003 vs $0.08)
            result = fal_client.subscribe(
                "fal-ai/flux/schnell",
                arguments={
                    "prompt":               full_prompt,
                    "num_images":           1,
                    "image_size":           {"width": 1024, "height": 576},
                    "num_inference_steps":  4,
                    "output_format":        "png",
                },
            )
            url  = _extract_image_url(result)
            data = requests.get(url, timeout=120).content

            plan_num = shot.get("number", idx + 1)
            shot_id  = (shot.get("id", "") or str(idx))[:8]
            fname    = f"sketch_{plan_num:03d}_{shot_id}_{int(time.time())}.png"
            path     = os.path.join(img_dir, fname)
            with open(path, "wb") as f:
                f.write(data)
            return path
        except Exception:
            return ""


class GeneratePortraitWithFaceIDWorker(QThread):
    """
    Two-step face-faithful generation:
    Step 1 → fal-ai/instant-id   : encode face identity → portrait with exact face
    Step 2 → fal-ai/nano-banana-2 : use that portrait as style anchor → 5-view character sheet

    Falls back to direct nano-banana-2 if InstantID fails.
    """
    progress = pyqtSignal(int, str)
    finished = pyqtSignal(str, str)  # (portrait_path, sheet_path)
    failed   = pyqtSignal(str)

    def __init__(self, photo_path: str, prompt: str, char_name: str):
        super().__init__()
        self._photo_path = photo_path
        self._prompt     = prompt
        self._name       = char_name

    def run(self):
        cfg = load_config()
        key = cfg.get("api_key", "").strip()
        if not key:
            self._mock()
        else:
            self._real(key)

    def _mock(self):
        steps = [
            (5,  "Upload de la photo (mode mock)…"),
            (12, "Analyse du visage (mode mock)…"),
            (20, "Génération 5 portraits en parallèle (mock)…"),
            (36, "Vue face générée (1/5)…"),
            (52, "Vue 3/4 générée (2/5)…"),
            (64, "Vue profil générée (3/5)…"),
            (74, "Vue dos générée (4/5)…"),
            (84, "Vue buste générée (5/5)…"),
            (92, "Assemblage du character sheet…"),
            (100, "Terminé — mode mock actif"),
        ]
        for pct, msg in steps:
            self.progress.emit(pct, msg)
            time.sleep(0.3)
        self.finished.emit("", "")

    # ── Analyse texture via Claude Haiku (IMPROVEMENT 1) ────────────────────
    # Remplace l'ancien _analyze_face() Opus 4.7 — inutile + coûteux.
    # Extrait UNIQUEMENT la texture cutanée (ton, pores, barbe, taches) que
    # PuLID ne peut pas injecter tout seul (il gère la géométrie, pas la texture).

    def _analyze_texture(self) -> str | None:
        """Extrait la texture cutanée via Claude Haiku (pas la géométrie)."""
        cfg = load_config()
        anthropic_key = cfg.get("anthropic_key", "").strip()
        if not anthropic_key:
            return None
        try:
            import anthropic, base64 as _b64
            from pathlib import Path

            client = anthropic.Anthropic(api_key=anthropic_key)
            ext  = Path(self._photo_path).suffix.lower().lstrip(".")
            mime = {
                "jpg": "image/jpeg", "jpeg": "image/jpeg",
                "png": "image/png",  "webp": "image/webp", "bmp": "image/bmp",
            }.get(ext, "image/jpeg")
            with open(self._photo_path, "rb") as f:
                raw = _b64.standard_b64encode(f.read()).decode()

            msg = client.messages.create(
                model="claude-haiku-4-5",
                max_tokens=120,
                system=_TEXTURE_ANALYSIS_SYSTEM,
                messages=[{
                    "role": "user",
                    "content": [
                        {"type": "image", "source": {"type": "base64", "media_type": mime, "data": raw}},
                        {"type": "text",  "text": "Extract skin texture details only."},
                    ],
                }],
            )
            return msg.content[0].text.strip()
        except Exception:
            return None

    def _clean_prompt(self, char_prompt_en: str) -> str | None:
        """Filtre char_prompt_en via Claude Haiku — supprime les descripteurs physiques
        (cheveux, yeux, morphologie) qui entrent en compétition avec l'embedding PuLID.
        Garde : costume, rôle, contexte, période."""
        cfg = load_config()
        anthropic_key = cfg.get("anthropic_key", "").strip()
        if not anthropic_key:
            return None
        try:
            import anthropic
            client = anthropic.Anthropic(api_key=anthropic_key)
            msg = client.messages.create(
                model="claude-haiku-4-5",
                max_tokens=120,
                system=_COSTUME_FILTER_SYSTEM,
                messages=[{"role": "user", "content": char_prompt_en}],
            )
            return msg.content[0].text.strip()
        except Exception:
            return None

    # ── Génération réelle ─────────────────────────────────────────────────────
    #
    # Pipeline recommandé (Gemini) — 5 portraits séparés + face-swap individuel :
    #   1. Upload photo → CDN URL
    #   2. Claude → description faciale textuelle (enrichit le prompt de chaque vue)
    #   3. ThreadPoolExecutor → 5 appels nano-banana-2 en parallèle (1 vue = 1 image)
    #      Pour chaque vue avec visage visible : face-swap immédiat (visage plein cadre)
    #   4. Assemblage Pillow local → canvas 16:9 (4 vues ligne 1 + buste centré ligne 2)

    def _real(self, key: str):
        try:
            import fal_client
            import requests
            import threading
            from pathlib import Path
            from concurrent.futures import ThreadPoolExecutor, as_completed
            from core.lang import translate_to_english

            os.environ["FAL_KEY"] = key

            if not os.path.isfile(self._photo_path):
                self.failed.emit(
                    f"Photo introuvable : {os.path.basename(self._photo_path)}\n"
                    "Le fichier a peut-être été déplacé ou supprimé."
                )
                return

            safe = "".join(c for c in self._name if c.isalnum() or c in " -_").strip() or "character"
            ts   = int(time.time())
            dest = _project_images_dir("castings")

            # ── Étape 1 : Encodage photo ─────────────────────────────────────
            self.progress.emit(5, "Encodage de la photo de référence…")
            import base64, mimetypes as _mt
            ext  = Path(self._photo_path).suffix.lower().lstrip(".")
            mime = {
                "jpg": "image/jpeg", "jpeg": "image/jpeg",
                "png": "image/png",  "webp": "image/webp", "bmp": "image/bmp",
            }.get(ext, "image/jpeg")
            with open(self._photo_path, "rb") as f:
                photo_bytes = f.read()
            photo_url = f"data:{mime};base64,{base64.b64encode(photo_bytes).decode()}"

            # ── Étape 2 : Texture + nettoyage prompt en parallèle (Haiku × 2) ────
            # IMPROVEMENT 1 (Gemini) : PuLID gère la géométrie faciale lui-même.
            # On extrait uniquement la texture cutanée (ce que PuLID ne peut pas injecter)
            # et on filtre char_prompt_en pour retirer les descripteurs physiques
            # (cheveux, yeux, morphologie) qui entrent en compétition avec PuLID.
            self.progress.emit(12, "Analyse texture + filtrage prompt (Claude Haiku)…")
            char_prompt_en = translate_to_english(self._prompt) if self._prompt else ""

            with ThreadPoolExecutor(max_workers=2) as _claude_ex:
                _tf = _claude_ex.submit(self._analyze_texture)
                _cf = _claude_ex.submit(self._clean_prompt, char_prompt_en)

            texture_details = _tf.result() or ""
            cleaned_subject  = _cf.result() or char_prompt_en

            if texture_details:
                self.progress.emit(15, f"Texture : {texture_details[:60]}…")
            else:
                self.progress.emit(15, "Texture non extraite — prompt brut utilisé.")

            # ── Étape 3 : Pipeline Anchor Portrait (recommandé par Gemini) ──────
            #
            # Problème : photo réelle → espace IA = gap de domaine → face perdue.
            # Solution  : générer le buste EN PREMIER (photo réelle → IA via PuLID),
            #             puis utiliser CE buste (déjà dans l'espace IA) comme référence
            #             pour les 4 vues corps entier → cohérence garantie.
            #
            # Séquence :
            #   1. Buste   → flux-pulid(photo_réelle, id_weight=0.85) — référence visuelle
            #   2. Upload buste → bust_url (ou fallback photo_url si échec upload)
            #   3. Corps   → flux-pulid(bust_url, id_weight=0.78) × 4 en parallèle
            #   4. Assemblage Pillow

            gen_logs: list[str] = []

            def _gen_view(view_key: str, view_instr: str, use_pulid: bool,
                          ref_url: str = "", texture_det: str = "",
                          cleaned_subj: str = "") -> bytes:
                """Génère une vue via flux-pulid (ref_url) ou flux/dev (dos/fallback)."""
                use_pulid_eff = use_pulid and bool(ref_url)
                endpoint      = "fal-ai/flux-pulid" if use_pulid_eff else "fal-ai/flux/dev"

                if view_key == "bust":
                    _id_weight = 0.85   # photo réelle → buste IA, max fidélité
                    _guidance  = 2.2    # IMPROVEMENT 2 : buste plus fidèle à ref
                elif view_key == "back":
                    _id_weight = 0.0    # pas de visage visible
                    _guidance  = 2.5
                else:
                    _id_weight = 0.78   # buste IA → corps entier (domaine unifié)
                    _guidance  = 2.5    # IMPROVEMENT 2 : moins d'hallucination texte

                # IMPROVEMENT 1 (Gemini) : prompt structuré Action → Subject → Texture → Quality.
                # PuLID gère la géométrie faciale — on lui donne texture cutanée + costume filtré.
                _subj = cleaned_subj or char_prompt_en
                if texture_det:
                    full_prompt = (
                        f"Action: {view_instr}. "
                        f"Subject: A high fidelity portrait of a character, {_subj}. "
                        f"Facial texture: {texture_det}. "
                        f"{_INDIVIDUAL_PORTRAIT_SUFFIX}"
                    )
                else:
                    full_prompt = (
                        f"Action: {view_instr}. "
                        f"Subject: {_subj}. "
                        f"{_INDIVIDUAL_PORTRAIT_SUFFIX}"
                    )

                args = {
                    "prompt":              full_prompt,
                    "num_images":          1,
                    "image_size":          {"width": 1024, "height": 1024},
                    "num_inference_steps": 35,   # IMPROVEMENT 2 : +5 steps
                    "guidance_scale":      _guidance,
                }
                if use_pulid_eff:
                    args["reference_image_url"] = ref_url
                    args["id_weight"]           = _id_weight

                result = fal_client.subscribe(endpoint, arguments=args)
                _imgs = result.get("images") if isinstance(result, dict) else None
                if not _imgs:
                    raise RuntimeError(
                        f"{endpoint} : aucune image pour '{view_key}' — "
                        f"réponse : {str(result)[:120]}"
                    )
                img_url = _imgs[0].get("url", "")
                if not img_url:
                    raise RuntimeError(f"{endpoint} : URL manquante pour '{view_key}'")

                mode = "PuLID" if use_pulid_eff else "Flux/dev"
                gen_logs.append(f"[{view_key}] ✓ {mode} (ref={'buste' if ref_url != photo_url else 'photo'})")
                return requests.get(img_url, timeout=120).content

            view_bytes: dict[str, bytes | None] = {}

            # ── 3a. Buste en premier (photo réelle → IA) ─────────────────────
            self.progress.emit(18, "Génération du buste de référence…")
            bust_vdef = next(vd for vd in _VIEW_DEFS if vd[0] == "bust")
            bust_bytes: bytes | None = None
            try:
                bust_bytes = _gen_view(bust_vdef[0], bust_vdef[1], bust_vdef[2], photo_url,
                                       texture_details, cleaned_subject)
                view_bytes["bust"] = bust_bytes
                self.progress.emit(32, "Buste généré ✓ — upload comme ancre identité…")
            except Exception as _be:
                view_bytes["bust"] = None
                self.progress.emit(32, f"⚠ Buste échoué ({str(_be)[:60]}) — fallback photo.")

            # ── 3b. Encode buste → data URL pour les vues corps entier ─────
            body_ref_url = photo_url  # fallback si encodage échoue
            if bust_bytes:
                try:
                    import base64
                    body_ref_url = f"data:image/png;base64,{base64.b64encode(bust_bytes).decode()}"
                    self.progress.emit(36, "Ancre encodée — génération des 4 vues…")
                except Exception:
                    self.progress.emit(36, "⚠ Encodage ancre échoué — utilisation photo originale.")

            # ── 3c. 4 vues corps entier en parallèle (buste IA comme référence) ──
            self.progress.emit(38, "Génération des 4 vues corps entier en parallèle…")
            body_defs = [(vk, vi, afs) for vk, vi, afs in _VIEW_DEFS if vk != "bust"]
            n_done = 0
            with ThreadPoolExecutor(max_workers=4) as executor:
                futures = {
                    executor.submit(
                        _gen_view, vk, vi, afs,
                        body_ref_url if afs else "",  # back (afs=False) → pas de ref
                        texture_details, cleaned_subject
                    ): vk
                    for vk, vi, afs in body_defs
                }
                for future in as_completed(futures):
                    vk = futures[future]
                    n_done += 1
                    pct = 38 + int(n_done / 4 * 42)  # 38 % → 80 %
                    try:
                        view_bytes[vk] = future.result()
                        self.progress.emit(pct, f"Vue {vk} générée ({n_done}/4)…")
                    except Exception as _ve:
                        view_bytes[vk] = None
                        self.progress.emit(pct,
                            f"⚠ Vue {vk} échouée ({str(_ve)[:60]}) — ignorée.")

            for _log in gen_logs:
                self.progress.emit(81, f"Anchor Portrait — {_log}")

            # ── Étape 4 : Assemblage Pillow local → canvas 16:9 ──────────────
            self.progress.emit(82, "Assemblage du character sheet…")
            from PIL import Image
            import io

            # Layout : ligne 1 → front | 3/4 | profil | dos  (4 cases)
            #          ligne 2 → buste centré
            ROW1_ORDER = ["front", "34", "profile", "back"]
            BUST_KEY   = "bust"
            CW, CH     = 2048, 1152  # canvas 16:9
            MARGIN     = 20
            GAP        = 12

            canvas = Image.new("RGB", (CW, CH), (18, 18, 28))

            n_row1  = len(ROW1_ORDER)
            cell_w  = (CW - 2 * MARGIN - (n_row1 - 1) * GAP) // n_row1
            cell_h  = cell_w  # cases carrées
            row1_y  = MARGIN

            for i, vk in enumerate(ROW1_ORDER):
                data = view_bytes.get(vk)
                if not data:
                    continue
                img = Image.open(io.BytesIO(data)).convert("RGB")
                img = img.resize((cell_w, cell_h), Image.LANCZOS)
                canvas.paste(img, (MARGIN + i * (cell_w + GAP), row1_y))

            row2_y  = row1_y + cell_h + GAP
            bust_h  = CH - row2_y - MARGIN
            bust_w  = bust_h
            bust_x  = (CW - bust_w) // 2
            bust_data = view_bytes.get(BUST_KEY)
            if bust_data:
                img = Image.open(io.BytesIO(bust_data)).convert("RGB")
                img = img.resize((bust_w, bust_h), Image.LANCZOS)
                canvas.paste(img, (bust_x, row2_y))

            sheet_path = os.path.join(dest, f"{safe}_{ts}_sheet.png")
            canvas.save(sheet_path, "PNG")

            n_ok = sum(1 for vk in _VIEW_DEFS if view_bytes.get(vk[0]))
            self.progress.emit(100,
                f"Character sheet généré — {n_ok}/5 vues · visage fixé par PuLID ✓")
            self.finished.emit("", sheet_path)

        except Exception as e:
            self.failed.emit(humanize_api_error(f"Erreur génération portrait : {e}"))


# Keep alias for backward compatibility
GeneratePortraitFromPhotoWorker = GeneratePortraitWithFaceIDWorker


# ── Workers spécialisés accessoires / HMC ────────────────────────────────────


def _run_optimize_worker(self, system_const, finished_signal, failed_signal):
    """Shared run logic for simple single-text optimize workers."""
    cfg = load_config()
    key = cfg.get("anthropic_key", "").strip()
    if not key:
        failed_signal.emit("Clé API Anthropic manquante.\nConfigure-la dans Paramètres.")
        return
    try:
        import anthropic
        lang = _get_lang()
        client = anthropic.Anthropic(api_key=key)
        msg = client.messages.create(
            model="claude-haiku-4-5",
            max_tokens=350,
            system=_apply_lang_to_system(system_const, lang),
            messages=[{"role": "user", "content": self._desc}],
        )
        finished_signal.emit(msg.content[0].text.strip())
    except Exception as e:
        failed_signal.emit(f"Erreur Anthropic : {e}")


class OptimizeDecorPromptWorker(OptimizePromptWorker):
    """Optimise un prompt de décor (lieu de tournage) via Claude."""
    def run(self):
        _run_optimize_worker(self, _OPTIMIZE_DECOR_SYSTEM, self.finished, self.failed)


class OptimizeAccessoryPromptWorker(OptimizePromptWorker):
    """Optimise un prompt d'accessoire via Claude."""
    def run(self):
        _run_optimize_worker(self, _OPTIMIZE_ACCESSORY_SYSTEM, self.finished, self.failed)


class OptimizeHMCPromptWorker(OptimizePromptWorker):
    """Optimise un prompt HMC (Habit/Maquillage/Coiffure) via Claude."""
    def run(self):
        _run_optimize_worker(self, _OPTIMIZE_HMC_SYSTEM, self.finished, self.failed)


class OptimizeVehiclePromptWorker(OptimizePromptWorker):
    """Optimise un prompt de véhicule via Claude (fond blanc, isolé, pas de personnage)."""
    def run(self):
        _run_optimize_worker(self, _OPTIMIZE_VEHICLE_SYSTEM, self.finished, self.failed)


class GenerateDecorSheetWorker(QThread):
    """Génère un sheet 4 vues (avant, arrière, gauche, droite) d'un décor via Nano Banana."""
    progress       = pyqtSignal(int, str)
    finished       = pyqtSignal(str)    # N=1: chemin local du sheet
    multi_finished = pyqtSignal(list)   # N>1: liste de chemins
    failed         = pyqtSignal(str)

    def __init__(self, prompt: str, decor_name: str, model_key: str | None = None,
                 num_images: int = 1):
        super().__init__()
        self._prompt     = prompt
        self._name       = decor_name
        self._model_key  = model_key
        self._num_images = max(1, num_images)

    def run(self):
        cfg = load_config()
        key = cfg.get("api_key", "").strip()
        if not key:
            self._mock()
        else:
            self._real(key)

    def _mock(self):
        steps = [
            (20,  "Connexion à Nano Banana (mode mock)…"),
            (50,  "Génération du sheet 4 vues (mock)…"),
            (85,  "Post-traitement…"),
            (100, "Terminé — mode mock actif"),
        ]
        for pct, msg in steps:
            self.progress.emit(pct, msg)
            time.sleep(0.5)
        if self._num_images > 1:
            self.multi_finished.emit([""] * self._num_images)
        else:
            self.finished.emit("")

    def _real(self, key: str):
        try:
            import fal_client
            import requests
            from core.lang import translate_to_english

            os.environ["FAL_KEY"] = key

            prompt_en   = translate_to_english(self._prompt) if self._prompt else ""
            full_prompt = f"{prompt_en}\n\n{_DECOR_SHEET_SUFFIX}"

            cfg   = load_config()
            price = get_image_price(cfg)
            _decor_model    = self._model_key or cfg.get("image_model", "nb2")
            from core.config import IMAGE_MODEL_ENDPOINTS
            _decor_endpoint = IMAGE_MODEL_ENDPOINTS.get(_decor_model, "fal-ai/nano-banana-2")
            dest = _project_images_dir("decors")
            safe = "".join(c for c in self._name if c.isalnum() or c in " -_").strip() or "decor"

            paths = []
            for i in range(self._num_images):
                pct_start = 10 + i * (65 // self._num_images)
                self.progress.emit(pct_start,
                                   f"Sheet {i+1}/{self._num_images}…  ({price})")
                result = fal_client.subscribe(
                    _decor_endpoint,
                    arguments={
                        "prompt":           full_prompt,
                        "num_images":       1,
                        "aspect_ratio":     "1:1",
                        "resolution":       "1K",
                        "output_format":    "png",
                        "safety_tolerance": "6",
                    },
                )
                url  = _extract_image_url(result)
                self.progress.emit(pct_start + 20, f"Téléchargement sheet {i+1}…")
                data = requests.get(url, timeout=120).content
                sheet_path = os.path.join(dest, f"{safe}_{int(time.time())}_{i}_sheet.png")
                with open(sheet_path, "wb") as f:
                    f.write(data)
                paths.append(sheet_path)

            self.progress.emit(100, f"{len(paths)} sheet(s) généré(s) !")
            if len(paths) == 1:
                self.finished.emit(paths[0])
            else:
                self.multi_finished.emit(paths)

        except Exception as e:
            self.failed.emit(humanize_api_error(f"Erreur Nano Banana : {e}"))


class GenerateItemWorker(QThread):
    """Génère une ou plusieurs images (accessoire, HMC, décor ou véhicule) via Nano Banana."""
    progress       = pyqtSignal(int, str)
    finished       = pyqtSignal(str)    # N=1: chemin local de l'image
    multi_finished = pyqtSignal(list)   # N>1: liste de chemins
    failed         = pyqtSignal(str)

    def __init__(self, prompt: str, item_name: str, subdir: str = "accessories",
                 model_key: str | None = None, num_images: int = 1,
                 ref_usage: str = "inspiration",
                 style_ref_path: str = "",
                 subject_hint: str = ""):
        super().__init__()
        self._prompt          = prompt
        self._name            = item_name
        self._subdir          = subdir
        self._model_key       = model_key
        self._num_images      = max(1, num_images)
        self._ref_usage       = ref_usage       # "inspiration" | "style" | "fidelity"
        self._style_ref_path  = style_ref_path  # premier chemin ref pour analyse Vision
        self._subject_hint    = subject_hint    # hint pour fidelity ("vehicle", "decor", etc.)

    def _dest_dir(self) -> str:
        return _project_images_dir(self._subdir)

    def run(self):
        cfg = load_config()
        key = cfg.get("api_key", "").strip()
        if not key:
            self._mock()
        else:
            self._real(key)

    def _mock(self):
        steps = [
            (20,  "Connexion à Nano Banana (mode mock)…"),
            (55,  "Génération de l'image…"),
            (85,  "Post-traitement…"),
            (100, "Terminé — mode mock actif"),
        ]
        for pct, msg in steps:
            self.progress.emit(pct, msg)
            time.sleep(0.5)
        self.finished.emit("")

    def _real(self, key: str):
        try:
            import fal_client
            import requests
            from core.lang import translate_to_english

            os.environ["FAL_KEY"] = key

            is_decor   = self._subdir == "decors"
            is_vehicle = self._subdir == "vehicles"
            if is_decor:
                prompt_suffix = _DECOR_LINE
                aspect_ratio  = "16:9"
            elif is_vehicle:
                prompt_suffix = _VEHICLE_LINE
                aspect_ratio  = "16:9"
            else:
                prompt_suffix = _ITEM_LINE
                aspect_ratio  = "1:1"

            # Traduit le prompt utilisateur (peut être en français) → anglais pour l'API
            prompt_en = translate_to_english(self._prompt) if self._prompt else ""

            # ── Analyse Vision selon le mode d'usage des références ──────────────
            _ref_path = self._style_ref_path
            if _ref_path and os.path.isfile(_ref_path):
                _nb_cfg = load_config()
                _nb_key = _nb_cfg.get("anthropic_key", "").strip()
                if _nb_key:
                    if self._ref_usage == "style":
                        self.progress.emit(5, "Analyse du style de l'image de référence…")
                        _vs = analyze_style_for_image(_ref_path, _nb_key)
                        if _vs:
                            # Préfixe → poids d'attention maximal dans le modèle image
                            prompt_en = f"{_vs}, {prompt_en}" if prompt_en else _vs
                        # Pas de style_suffix : la référence visuelle fournit le style
                        prompt_suffix = ""
                    elif self._ref_usage == "fidelity":
                        self.progress.emit(5, "Analyse de fidélité de l'image de référence…")
                        _fd = analyze_fidelity_for_image(_ref_path, _nb_key, self._subject_hint)
                        if _fd:
                            prompt_en = f"EXACT REPRODUCTION: {_fd}. {prompt_en}" if prompt_en else f"EXACT REPRODUCTION: {_fd}"
                        # Style suffix appliqué normalement pour fidelity

            cfg   = load_config()
            if self._model_key:
                cfg = dict(cfg)
                cfg["image_model"] = self._model_key
            price = get_image_price(cfg)
            n = self._num_images
            full_prompt = f"{prompt_en}\n\n{prompt_suffix}" if prompt_suffix else prompt_en

            safe = "".join(c for c in self._name if c.isalnum() or c in " -_").strip() or "item"
            ts   = int(time.time())

            if n > 1:
                # N separate calls (num_images=1 each) — avoids API limit on batch size
                paths = []
                for i in range(n):
                    self.progress.emit(
                        10 + int(i / n * 80),
                        f"[{i+1}/{n}] Génération de l'image…  ({price})"
                    )
                    _ep, _args = _build_image_args(full_prompt, aspect_ratio, "1K", cfg, 1)
                    _result = fal_client.subscribe(_ep, arguments=_args)
                    _url = _extract_image_url(_result)
                    self.progress.emit(10 + int((i + 0.7) / n * 80),
                                       f"Téléchargement {i+1}/{n}…")
                    data = requests.get(_url, timeout=120).content
                    p = os.path.join(self._dest_dir(), f"{safe}_{ts}_{i}.png")
                    with open(p, "wb") as f:
                        f.write(data)
                    paths.append(p)
                self.progress.emit(100, f"{len(paths)} images générées !")
                self.multi_finished.emit(paths)
            else:
                msg_gen = "Génération de l'image…"
                self.progress.emit(10, f"{msg_gen}  ({price})")
                _ep, _args = _build_image_args(full_prompt, aspect_ratio, "1K", cfg, 1)
                result = fal_client.subscribe(_ep, arguments=_args)
                url  = _extract_image_url(result)
                self.progress.emit(70, "Téléchargement de l'image…")
                data = requests.get(url, timeout=120).content
                path = os.path.join(self._dest_dir(), f"{safe}_{ts}.png")
                with open(path, "wb") as f:
                    f.write(data)
                self.progress.emit(100, f"Image générée !  ({price})")
                self.finished.emit(path)

        except Exception as e:
            self.failed.emit(humanize_api_error(f"Erreur Nano Banana : {e}"))


# ── Les 6 vues d'une pièce (décor) ─────────────────────────────────────────────

class GenerateRoomViewsWorker(QThread):
    """Génère les vues d'une pièce dans un ORDRE qui maximise le raccord :
      1. le PLAN D'ENSEMBLE (vue maîtresse 3/4) ;
      2. le PLAN D'ARCHITECTURE vu de dessus (contexte : tous les éléments) ;
      3. les 6 FACES (avant · arrière · gauche · droite · sol · plafond), générées
         en INJECTANT le plan d'architecture + le plan d'ensemble comme références
         (NB2 edit) → mêmes objets, mêmes positions d'une vue à l'autre.

    Émet views_finished avec [{"label","code","path","prompt"[, "is_floor_plan"]}].
    Les 7 vues (ensemble + 6 faces) deviennent des DÉCORS ; l'entrée
    `is_floor_plan` (le plan vu de dessus) sert de plan partagé (decor.floor_plan)."""
    progress       = pyqtSignal(int, str)
    views_finished = pyqtSignal(list)   # [{"label","code","path"}, …] (7 vues)
    failed         = pyqtSignal(str)

    def __init__(self, base_prompt: str, decor_name: str,
                 model_key: str | None = None, style_suffix: str = ""):
        super().__init__()
        self._base         = base_prompt
        self._name         = decor_name
        self._model_key    = model_key
        self._style_suffix = style_suffix
        # Diagnostic lisible par le dialogue après views_finished.
        self._faces_ok     = 0
        self._faces_total  = 6
        self._last_error   = ""

    def run(self):
        cfg = load_config()
        key = cfg.get("api_key", "").strip()
        if not key:
            self._mock()
        else:
            self._real(key)

    def _mock(self):
        from core.room_views import build_seven_view_prompts
        views = build_seven_view_prompts("")
        for i, (label, _c, _d) in enumerate(views):
            self.progress.emit(int((i + 1) / len(views) * 100),
                               f"[{i+1}/7] {label} (mode mock)…")
            time.sleep(0.3)
        self.views_finished.emit([])

    def _real(self, key: str):
        try:
            import fal_client
            import requests
            import base64, mimetypes
            from core.lang import translate_to_english
            from core.room_views import build_six_view_prompts, build_overview_prompt

            os.environ["FAL_KEY"] = key
            cfg = load_config()
            if self._model_key:
                cfg = dict(cfg)
                cfg["image_model"] = self._model_key
            price = get_image_price(cfg)
            base_en = translate_to_english(self._base) if self._base else ""

            safe = "".join(c for c in self._name if c.isalnum() or c in " -_").strip() or "decor"
            ts   = int(time.time())
            out: list[dict] = []

            def _save(data: bytes, code: str) -> str:
                p = os.path.join(_project_images_dir("decors"), f"{safe}_{code}_{ts}.png")
                with open(p, "wb") as f:
                    f.write(data)
                return p

            def _dataurl(path: str) -> str:
                mime = mimetypes.guess_type(path)[0] or "image/png"
                with open(path, "rb") as f:
                    return f"data:{mime};base64,{base64.b64encode(f.read()).decode()}"

            def _gen_text(prompt: str, aspect: str) -> bytes:
                _ep, _args = _build_image_args(prompt, aspect, "1K", cfg, 1)
                _res = fal_client.subscribe(_ep, arguments=_args)
                return requests.get(_extract_image_url(_res), timeout=120).content

            def _gen_edit(prompt: str, ref_urls: list, aspect: str) -> bytes:
                _res = fal_client.subscribe("fal-ai/nano-banana-2/edit", arguments={
                    "prompt":           prompt,
                    "image_urls":       ref_urls,
                    "num_images":       1,
                    "aspect_ratio":     aspect,
                    "resolution":       "1K",
                    "output_format":    "png",
                    "safety_tolerance": "6",
                })
                return requests.get(_extract_image_url(_res), timeout=120).content

            # ⚠ RÉSILIENCE : chaque vue est isolée. Une vue qui échoue ne doit PAS
            # faire perdre les autres (sinon on se retrouve avec « 1 décor + le plan »).

            # 1) PLAN D'ENSEMBLE d'abord (vue maîtresse) ─────────────────────────
            self.progress.emit(8, f"[1/8] Plan d'ensemble…  ({price})")
            ov_label, ov_code, ov_prompt = build_overview_prompt(base_en)
            full_ov = ov_prompt
            if self._style_suffix:
                full_ov = f"{full_ov}, {self._style_suffix}"
            full_ov = f"{full_ov}\n\n{_DECOR_LINE}"
            ov_path = ""
            try:
                ov_path = _save(_gen_text(full_ov, "16:9"), ov_code)
                out.append({"label": ov_label, "code": ov_code, "path": ov_path, "prompt": ov_prompt})
            except Exception:
                pass

            # 2) PLAN D'ARCHITECTURE vu de dessus (contexte : tous les éléments) ──
            self.progress.emit(20, "[2/8] Plan d'architecture (vue de dessus)…")
            fp_prompt = _floor_plan_prompt(base_en or "an interior room")
            fp_path = ""
            try:
                fp_path = _save(_gen_text(fp_prompt, "1:1"), "floorplan")
                out.append({"label": "Plan (vue de dessus)", "code": "floorplan",
                            "path": fp_path, "prompt": fp_prompt, "is_floor_plan": True})
            except Exception:
                pass

            # 3) Les 6 FACES — en INJECTANT plan d'architecture + plan d'ensemble si
            #    disponibles (NB2 edit, raccord). REPLI : génération texte simple si
            #    l'édition échoue → on a TOUJOURS les 6 vues.
            ref_urls = [_dataurl(p) for p in (fp_path, ov_path) if p and os.path.isfile(p)]
            consistency = (
                "CRITICAL CONSISTENCY: the provided images are a top-down architectural "
                "floor plan and a wide establishing view of THIS exact room. Reproduce "
                "the SAME room — same walls, furniture, props, materials, colors and "
                "their RELATIVE POSITIONS. Strict spatial continuity with the references."
            )
            faces = build_six_view_prompts(base_en)
            # ⚠ Si l'édition NB2 échoue UNE fois, on la désactive pour les faces
            # suivantes : 6 appels edit qui échouent saturent l'API et font capoter
            # les replis texte (symptôme « seul le plan d'ensemble + le plan »).
            edit_disabled = not ref_urls
            last_err = ""
            n_faces_ok = 0
            for i, (label, code, fprompt) in enumerate(faces):
                self.progress.emit(
                    30 + int(i / len(faces) * 66),
                    f"[{i+3}/8] Vue « {label} »…  ({price})"
                )
                base_full = fprompt
                if self._style_suffix:
                    base_full = f"{base_full}, {self._style_suffix}"
                data = None
                # a) tentative edit (raccord) — best-effort, désactivée au 1er échec.
                if not edit_disabled:
                    try:
                        data = _gen_edit(f"{base_full}\n\n{consistency}\n\n{_DECOR_LINE}",
                                         ref_urls, "16:9")
                    except Exception as e:
                        last_err = str(e)
                        edit_disabled = True
                        data = None
                # b) repli texte ROBUSTE (3 essais, backoff) — même génération que le
                #    plan d'ensemble, donc fiable ; le backoff absorbe les limites de débit.
                if data is None:
                    for _attempt in range(3):
                        try:
                            data = _gen_text(f"{base_full}\n\n{_DECOR_LINE}", "16:9")
                            break
                        except Exception as e:
                            last_err = str(e)
                            data = None
                            time.sleep(4 * (_attempt + 1))   # 4s, 8s, 12s
                    if data is None:
                        continue   # cette face échoue vraiment, on garde les autres
                p = _save(data, code)
                # Prompt PAR VUE renvoyé (cadrage compris) → régénération fidèle.
                out.append({"label": label, "code": code, "path": p, "prompt": fprompt})
                n_faces_ok += 1

            # Diagnostic remonté au dialogue (faces manquantes + dernière erreur API).
            self._faces_ok    = n_faces_ok
            self._faces_total = len(faces)
            self._last_error  = last_err
            if n_faces_ok < len(faces):
                self.progress.emit(100, f"⚠ {n_faces_ok}/{len(faces)} faces générées — {last_err[:90]}")
            else:
                self.progress.emit(100, "Pièce générée (plan + 7 vues raccord) !")
            self.views_finished.emit(out)
        except Exception as e:
            self.failed.emit(humanize_api_error(f"Erreur Nano Banana : {e}"))


# ── NB2 Edit — Portrait avec photo de référence ───────────────────────────────

class GeneratePortraitNB2EditWorker(QThread):
    """
    Génère un portrait de personnage en utilisant une ou plusieurs photos
    de référence via l'endpoint fal-ai/nano-banana-2/edit (image_urls[]).

    Avantage vs PuLID : plus simple, plus rapide, respecte l'esthétique
    du style global (NB2 applique le style prompt sur la référence).
    Idéal quand on a déjà une photo et qu'on veut un portrait stylisé.
    """
    progress = pyqtSignal(int, str)
    finished = pyqtSignal(str)
    failed   = pyqtSignal(str)

    def __init__(self, ref_paths: list[str], prompt: str, name: str):
        """
        ref_paths : liste de chemins d'images locales (1–14 références)
        prompt    : description textuelle du personnage (FR accepté)
        name      : nom du personnage (pour le nom de fichier)
        """
        super().__init__()
        self._refs   = ref_paths[:14]
        self._prompt = prompt
        self._name   = name

    def run(self):
        cfg = load_config()
        key = cfg.get("api_key", "").strip()
        if not key:
            self._mock()
        else:
            self._real(key)

    def _mock(self):
        steps = [
            (10, "Upload des références (mode mock)…"),
            (40, "Génération NB2 Edit (simulation)…"),
            (80, "Post-traitement…"),
            (100, "Terminé — mode mock (aucune clé fal.ai)"),
        ]
        for pct, msg in steps:
            self.progress.emit(pct, msg)
            time.sleep(0.35)
        self.finished.emit("")

    def _real(self, key: str):
        try:
            import fal_client
            import requests
            import base64, mimetypes
            from core.lang import translate_to_english

            os.environ["FAL_KEY"] = key

            self.progress.emit(5, f"Encodage de {len(self._refs)} référence(s)…")

            image_urls: list[str] = []
            for i, path in enumerate(self._refs, 1):
                self.progress.emit(
                    5 + int(i / len(self._refs) * 25),
                    f"Encodage référence {i}/{len(self._refs)}…",
                )
                mime = mimetypes.guess_type(path)[0] or "image/png"
                with open(path, "rb") as _f:
                    b64 = base64.b64encode(_f.read()).decode()
                image_urls.append(f"data:{mime};base64,{b64}")

            prompt_en = translate_to_english(self._prompt) if self._prompt else ""
            full_prompt = (
                f"{prompt_en}. "
                "Professional character portrait, studio lighting, cinematic quality, "
                "sharp focus, detailed features."
            )

            self.progress.emit(35, "Génération NB2 Edit (~$0.08)…")

            result = fal_client.subscribe(
                "fal-ai/nano-banana-2/edit",
                arguments={
                    "prompt":           full_prompt,
                    "image_urls":       image_urls,
                    "num_images":       1,
                    "aspect_ratio":     "2:3",
                    "resolution":       "1K",
                    "output_format":    "png",
                    "safety_tolerance": "6",
                },
            )

            url  = _extract_image_url(result)
            self.progress.emit(80, "Téléchargement du portrait…")
            data = requests.get(url, timeout=180).content

            import core.casting as casting_api
            out_dir = casting_api.images_dir()
            safe    = "".join(c for c in self._name if c.isalnum() or c in " -_").strip() or "portrait"
            path    = os.path.join(out_dir, f"{safe}_nb2edit_{int(time.time())}.png")
            with open(path, "wb") as f:
                f.write(data)

            self.progress.emit(100, "Portrait généré ✓  (NB2 Edit · $0.08)")
            self.finished.emit(path)

        except Exception as e:
            self.failed.emit(humanize_api_error(f"Erreur NB2 Edit : {e}"))


# ── Nettoyage de fond — efface les personnes, garde le décor (continuité d'axe) ──

class CleanBackgroundWorker(QThread):
    """À partir d'une frame d'un plan généré, efface les personnages et reconstruit
    la pièce vide via NB2 edit (Gemini). Sert de fond de référence réutilisable pour
    les plans du même décor + même axe (voir core/decor_sync). finished("") en mock."""
    progress = pyqtSignal(int, str)
    finished = pyqtSignal(str)
    failed   = pyqtSignal(str)

    def __init__(self, frame_path: str, out_dir: str = ""):
        super().__init__()
        self._frame   = frame_path
        self._out_dir = out_dir

    def run(self):
        cfg = load_config()
        key = cfg.get("api_key", "").strip()
        if not key or not self._frame or not os.path.isfile(self._frame):
            self.finished.emit("")   # mock / pas de clé → pas de fond synchronisé
            return
        try:
            import fal_client
            import requests
            import base64

            os.environ["FAL_KEY"] = key
            self.progress.emit(20, "Nettoyage du fond (suppression du personnage)…")
            with open(self._frame, "rb") as f:
                b64 = base64.b64encode(f.read()).decode()
            data_url = f"data:image/png;base64,{b64}"
            prompt = (
                "Remove ALL people and characters from this image. Reconstruct the "
                "empty room/background exactly as it is — identical architecture, "
                "furniture, materials, colors, lighting and camera angle. "
                "Photorealistic, no people, no characters, empty location."
            )
            result = fal_client.subscribe(
                "fal-ai/nano-banana-2/edit",
                arguments={
                    "prompt":        prompt,
                    "image_urls":    [data_url],
                    "num_images":    1,
                    "resolution":    "1K",
                    "output_format": "png",
                },
            )
            url  = _extract_image_url(result)
            data = requests.get(url, timeout=180).content
            out_dir = self._out_dir or _project_images_dir("decors")
            path = os.path.join(out_dir, f"bg_clean_{int(time.time())}.png")
            with open(path, "wb") as f:
                f.write(data)
            self.progress.emit(100, "Fond synchronisé prêt ✓")
            self.finished.emit(path)
        except Exception as e:
            self.failed.emit(humanize_api_error(f"Erreur nettoyage fond : {e}"))


# ── Plan d'architecte vu de dessus — base de la Mise en scène ────────────────────

class GenerateFloorPlanWorker(QThread):
    """Génère un PLAN VU DE DESSUS (style plan d'architecte) du décor — base sur
    laquelle on place caméra, personnages, éléments (et lumières pour le Plan de
    feu). finished(path) ; "" en mock."""
    progress = pyqtSignal(int, str)
    finished = pyqtSignal(str)
    failed   = pyqtSignal(str)

    def __init__(self, decor_prompt: str, decor_name: str = "plan"):
        super().__init__()
        self._prompt = decor_prompt
        self._name   = decor_name

    def run(self):
        cfg = load_config()
        key = cfg.get("api_key", "").strip()
        if not key:
            self.finished.emit("")   # mock → canvas vierge éditable
            return
        try:
            import fal_client
            import requests
            from core.lang import translate_to_english
            from core.staging import images_dir

            os.environ["FAL_KEY"] = key
            self.progress.emit(15, "Génération du plan vu de dessus…")
            base_en = translate_to_english(self._prompt) if self._prompt else "an interior room"
            prompt = (
                f"TOP-DOWN architectural floor plan (bird's eye view, seen from directly "
                f"above) of: {base_en}. Clean schematic blueprint / architect plan style: "
                f"walls, doors, windows and furniture drawn from above with simple lines and "
                f"flat tones, neutral background, clear and uncluttered, no people, no camera, "
                f"no text labels. Square framing."
            )
            ep, args = _build_image_args(prompt, "1:1", "1K", cfg, 1)
            result = fal_client.subscribe(ep, arguments=args)
            url  = _extract_image_url(result)
            data = requests.get(url, timeout=180).content
            safe = "".join(c for c in self._name if c.isalnum() or c in " -_").strip() or "plan"
            path = os.path.join(images_dir(), f"{safe}_floorplan_{int(time.time())}.png")
            with open(path, "wb") as f:
                f.write(data)
            self.progress.emit(100, "Plan généré ✓")
            self.finished.emit(path)
        except Exception as e:
            self.failed.emit(humanize_api_error(f"Erreur plan vu de dessus : {e}"))


def _floor_plan_prompt(base_en: str) -> str:
    """Prompt commun (plan d'architecte vu de dessus)."""
    return (
        f"TOP-DOWN architectural floor plan (bird's eye view, seen from directly "
        f"above) of: {base_en}. Clean schematic blueprint / architect plan style: "
        f"walls, doors, windows and furniture drawn from above with simple lines and "
        f"flat tones, neutral background, clear and uncluttered, no people, no camera, "
        f"no text labels. Square framing."
    )


class GenerateFloorPlansWorker(QThread):
    """Génère EN LOT les plans vus de dessus (un par job). Sert à l'automatisation
    lors de la génération/identification des décors depuis le scénario.

    jobs : liste de {"id": <opaque>, "prompt": str, "name": str}.
    Émet plan_done(job_id, path) pour chaque job (path="" si mock/échec), puis
    finished(n) avec le nombre de plans réellement générés.
    """
    progress  = pyqtSignal(int, str)
    plan_done = pyqtSignal(str, str)   # job_id, path ("" si non généré)
    finished  = pyqtSignal(int)

    def __init__(self, jobs: list):
        super().__init__()
        self._jobs = list(jobs or [])

    def run(self):
        cfg = load_config()
        key = cfg.get("api_key", "").strip()
        n = len(self._jobs)
        if not key:
            # Mode mock : aucun plan généré (cohérent avec le reste de l'app).
            for j in self._jobs:
                self.plan_done.emit(str(j.get("id", "")), "")
            self.finished.emit(0)
            return
        try:
            import fal_client
            import requests
            from core.lang import translate_to_english
            from core.staging import images_dir
            os.environ["FAL_KEY"] = key
        except Exception as e:
            self.failed_safe(e, n)
            return

        made = 0
        for i, j in enumerate(self._jobs):
            jid = str(j.get("id", ""))
            try:
                self.progress.emit(int((i / max(1, n)) * 100),
                                   f"Plan {i + 1}/{n} — {j.get('name', '')}")
                base = j.get("prompt") or j.get("name") or "an interior room"
                base_en = translate_to_english(base) if base else "an interior room"
                ep, args = _build_image_args(_floor_plan_prompt(base_en), "1:1", "1K", cfg, 1)
                result = fal_client.subscribe(ep, arguments=args)
                url  = _extract_image_url(result)
                data = requests.get(url, timeout=180).content
                safe = "".join(c for c in j.get("name", "plan")
                               if c.isalnum() or c in " -_").strip() or "plan"
                path = os.path.join(images_dir(), f"{safe}_floorplan_{int(time.time())}_{i}.png")
                with open(path, "wb") as f:
                    f.write(data)
                made += 1
                self.plan_done.emit(jid, path)
            except Exception:
                self.plan_done.emit(jid, "")
        self.progress.emit(100, "Plans terminés")
        self.finished.emit(made)

    def failed_safe(self, e, n):
        for j in self._jobs:
            self.plan_done.emit(str(j.get("id", "")), "")
        self.finished.emit(0)
