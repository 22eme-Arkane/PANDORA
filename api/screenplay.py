"""
Workers Claude pour les opérations sur le scénario :
- Formatage en scénario classique
- Proposition d'arrangement narratif
- Session de chat interactif pour co-écriture arrangement
- Génération d'un découpage technique storyboard
- Extraction automatique : personnages, décors, accessoires, HMC
"""

import json
import re
import unicodedata
from PyQt6.QtCore import QThread, pyqtSignal
from core.config import load_config

_MODEL            = "claude-sonnet-4-6"   # Sonnet pour format/arrange/apply — qualité créative
_MODEL_STORYBOARD = "claude-sonnet-4-6"   # Sonnet pour fiabilité JSON sur découpage long


def _get_lang() -> str:
    try:
        from core.i18n import get_lang
        return get_lang()
    except Exception:
        return "fr"


def _lang_hint(lang: str) -> str:
    """Instruction injected into user content to force Claude to respond in the right language."""
    if lang != "en":
        return ""
    return (
        "[LANGUAGE: Respond entirely in English. All free-form text fields "
        "(names, descriptions, titles, comments, prompts) must be in English. "
        "Do NOT respond in French.]\n\n"
    )


# ── Prompts système ───────────────────────────────────────────────────────────

_FORMAT_SCREENPLAY = """\
Tu es un superviseur de production expert travaillant pour Pandora, un outil de \
pré-production IA qui génère des clips vidéo via Seedance 2.0 (ByteDance/fal.ai).

Ton rôle : mettre en page le scénario fourni dans le FORMAT PANDORA COMPLET — \
un document de production intégré qui structure la production ET maximise la \
qualité des vidéos générées par IA.

════════════════════════════════════════════════════════
STRUCTURE OBLIGATOIRE DU FORMAT PANDORA
════════════════════════════════════════════════════════

Le document doit comporter exactement ces sections dans cet ordre :

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
1. EN-TÊTE
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
════════════════════════════════════════════════════════
[TITRE DU PROJET EN MAJUSCULES]
[Sous-titre ou accroche — format, durée totale]
════════════════════════════════════════════════════════

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
2. PERSONNAGES
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
════════════════════════════════════════════════════════
PERSONNAGES
════════════════════════════════════════════════════════

Un bloc par personnage :
NOM — Rôle ou fonction
Âge, physique détaillé (taille, corpulence, traits, cheveux, peau).
Tenue principale : description précise des vêtements, couleurs, matières.
Attitude, énergie, ce que le corps exprime.

RÈGLE : graphie du NOM strictement identique dans tout le document.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
3. DÉCORS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
════════════════════════════════════════════════════════
DÉCORS
════════════════════════════════════════════════════════

Un bloc par décor unique :
NOM DU DÉCOR — INT./EXT. — MOMENT (JOUR / NUIT / GOLDEN HOUR / etc.)
Description visuelle détaillée : architecture, matières, couleurs, lumière \
naturelle ou artificielle, objets présents, ambiance générale.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
4. SCÉNARIO — PLANS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
════════════════════════════════════════════════════════
SCÉNARIO
════════════════════════════════════════════════════════

Un bloc par plan, séparé par une ligne de tirets :

────────────────────────────────────────────────────────
PLAN N — [INT./EXT.] [NOM DU DÉCOR] — [MOMENT]
Séquence N — Plan N — Durée : Xs
────────────────────────────────────────────────────────

VALEUR DE PLAN : [Plan large / Plan moyen / Plan rapproché / Gros plan / Très gros plan]
MOUVEMENT CAMÉRA : [description précise du mouvement ou "Caméra fixe"]
AXE : [Face / Profil / 3/4 / Dos / Plongée / Contre-plongée — préciser si nécessaire]
FOCALE : [valeur mm — type optique si pertinent]
VITESSE : [Normale / Ralenti léger / Ralenti (120fps) / Accéléré]

[Description de l'action au présent de l'indicatif. Ce que la caméra voit \
exactement : position des personnages, gestes précis, expressions, matières, \
lumières, profondeur de champ, arrière-plan. Minimum 3 lignes par plan.]

[Son : ambiance, musique, effets — si notable]

PROMPT SEEDANCE :
[Prompt en anglais, 40-80 mots. Structure : shot type + sujet + action + \
environnement + lumière + style technique + mouvement caméra. \
Ne jamais inclure de dialogue ou voix off dans ce champ.]

════════════════════════════════════════════════════════
FIN — DURÉE TOTALE : Xs
════════════════════════════════════════════════════════

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
RÈGLES IMPÉRATIVES
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
- Conserver TOUT le contenu narratif sans rien résumer ni couper
- Noms de personnages : graphie STRICTEMENT IDENTIQUE dans tout le document
- Dialogues et voix off : inclus directement dans le bloc du plan concerné, \
  sous la description d'action, au format :
      NOM DU PERSONNAGE (V.O.) ou NOM DU PERSONNAGE
      "Texte du dialogue ou de la voix off."
- Prompts Seedance : en anglais, jamais de voix off ni dialogue dedans
- Descriptions visuelles : concret, dynamique, spécifique, spatial
  ("la soie noire trempée de pluie" et non "une belle robe")
  ("ses mains se crispent sur le fourreau" et non "il hésite")
- Accessoires, véhicules, costumes importants : citer explicitement \
  dans les descriptions — ils seront extraits automatiquement par Pandora
- Durées : estimer selon le rythme naturel de la scène (4s minimum par plan)
- Retourner uniquement le document mis en page, sans commentaires ni explications\
"""

_ARRANGE_SCREENPLAY_TMPL = """\
Tu es un consultant créatif et superviseur de production pour Pandora, \
un outil de pré-production IA qui génère des clips vidéo via Seedance 2.0 (ByteDance/fal.ai).

CONTEXTE TECHNIQUE CRUCIAL :
Ce scénario sera découpé en plans de 2 à 15 secondes, chacun envoyé à Seedance 2.0 sous forme de prompt vidéo. \
La qualité des clips dépend directement de la qualité visuelle des descriptions dans le scénario. \
Un bon scénario pour Pandora est un scénario dont chaque ligne d'action peut devenir un prompt efficace.

Un scénario optimal pour Pandora :
- Décrit ce que la caméra VOIT — personnages, costumes, décors, textures, lumières, mouvements
- Peut être découpé en plans courts (2-15s) sans perdre de sens visuel
- Évite les abstractions non visuelles (états intérieurs, ellipses non décrites, voix off sans image)
- Nomme les personnages et décors de façon stable et précise (pour les extractions automatiques)
- Intègre les éléments qui ont des références visuelles (personnages iconiques, décors marquants)

Analyse le scénario fourni et structure ta réponse en 6 sections :

### 1. Structure narrative et découpage IA
Rythme général, cohérence des séquences, équilibre action/dialogue. \
Le scénario est-il découpable en plans de 2-15s ? \
Y a-t-il des séquences trop longues, trop denses, ou qui créent des transitions visuellement problématiques ?

### 2. Qualité des descriptions visuelles pour Seedance
C'est la section la plus importante pour Pandora. Évalue la richesse "promptable" du scénario : \
Les personnages sont-ils décrits avec suffisamment de détails (apparence, costumes, expressions, postures) ? \
Les décors sont-ils assez précis et évocateurs ? \
Y a-t-il des scènes abstraites qui produiraient des clips génériques ou incohérents d'un plan à l'autre ? \
Cite les passages exacts à améliorer.

### 3. Points forts
Ce qui fonctionne bien — narrativement ET visuellement pour la génération IA. \
Cite les passages qui produiraient de bons prompts Seedance.

### 4. Proposition d'arrangement
Si la structure narrative ou le rythme visuel peut être amélioré : \
propose un ordre alternatif des séquences avec justification (impact dramatique ET impact IA). \
Indique les séquences à couper, fusionner, diviser ou déplacer. \
Si la structure est déjà optimale, dis-le explicitement.

### 5. Suggestions concrètes
5 à 7 pistes actionnables, priorisées par impact sur la qualité de génération. \
Pour chaque suggestion : (a) ce qu'il faut changer, \
(b) pourquoi ça améliore la génération Seedance, \
(c) exemple de reformulation si pertinent.

### 6. Inventaire complet des personnages
Liste TOUS les personnages sans exception : principaux, secondaires, figurants. \
Ne jamais regrouper sous une formule générique. \
Format par ligne : Nom/Fonction | Rôle (Principal / Secondaire / Figurant) | Scènes d'apparition

Respond in {LANG_INSTRUCTION}, in a structured, direct and constructive way.\
"""

_APPLY_ARRANGE = """\
Tu es un scénariste expert pour Pandora, un outil de pré-production IA \
qui génère des clips vidéo via Seedance 2.0 (ByteDance/fal.ai).

Tu appliques des suggestions d'arrangement à un scénario pour le rendre \
plus fort narrativement ET plus efficace pour la génération vidéo IA.

Tu reçois :
1. LE SCÉNARIO ORIGINAL — la matière de base à préserver et améliorer
2. L'ANALYSE ET LES SUGGESTIONS — le résultat de l'analyse créative et technique

RÈGLES D'APPLICATION :
- Préserve TOUT le contenu narratif essentiel : actions, dialogues, lieux, personnages
- Applique les suggestions pertinentes selon l'intensité indiquée
- Maintiens la structure Pandora : séquences (—— SÉQUENCE N — TITRE ——), \
en-têtes INT./EXT., noms de personnages en MAJUSCULES centrés
- Noms de personnages : graphie STRICTEMENT IDENTIQUE tout au long du document
- Enrichis les descriptions visuelles là où c'est pertinent : \
ajoute des détails de costume, d'expression, de texture, de lumière, de mouvement — \
tout ce qui rend les scènes plus "promptables" pour Seedance 2.0
- Chaque ligne d'action doit décrire ce que la caméra peut voir — \
traduis les états intérieurs en gestes, postures, expressions visibles
- Assure-toi que chaque scène contient au moins une action visuelle claire et concrète \
(le scénario sera découpé en plans de 2 à 15s)
- Ne résume pas, ne condense pas arbitrairement les dialogues importants

Retourne UNIQUEMENT le scénario réécrit en mise en page Pandora, sans commentaires ni explications.\
"""

_GENERATE_STORYBOARD_TMPL = """\
Tu es un assistant de découpage cinématographique. Ton rôle est de découper fidèlement le scénario en plans — tu ne réinventes rien, tu n'interprètes rien, tu retranscris.

RÈGLES ABSOLUES :
- Tout le contenu de "comments" et "seedance_prompt" doit être extrait directement du scénario.
- Les dialogues présents dans le scénario DOIVENT apparaître mot pour mot dans "comments" et "seedance_prompt".
- Aucune invention, aucune paraphrase libre, aucune interprétation créative.
- Le découpage doit être identique au scénario : même personnages, même lieux, mêmes actions, mêmes mots.

Retourne UNIQUEMENT un tableau JSON valide. Chaque élément du tableau représente un plan et contient exactement ces clés :
{
  "number": <int — numéro séquentiel du plan>,
  "seq_num": <int — numéro de la séquence contenant ce plan, extrait des titres "—— SÉQUENCE N — TITRE ——" du scénario. Ex : 1 pour SÉQUENCE 1, 3 pour SÉQUENCE 3. Si le scénario ne contient pas de marqueurs de séquence, utiliser 1 pour tous les plans.>,
  "seq_name": <str — titre de la séquence contenant ce plan, extrait du marqueur "—— SÉQUENCE N — TITRE ——". Ex : "LA FORTERESSE", "RETOUR AU VILLAGE". Chaîne vide si pas de marqueur de séquence.>,
  "scene_title": <str — titre court de la scène, extrait du scénario>,
  "decor_name": <str — nom exact du décor / lieu tel qu'il apparaît dans le scénario>,
  "shot_time": <str — exactement une valeur parmi : "Jour", "Nuit", "Lever du soleil", "Coucher du soleil">,
  "duration": <float — durée estimée en secondes, STRICTEMENT entre 2.0 et 15.0>,
  "character_names": <list[str] — noms exacts des personnages présents dans ce plan, tels qu'ils apparaissent dans le scénario>,
  "accessory_names": <list[str] — accessoires / props visibles dans ce plan, extraits du scénario>,
  "vehicle_names": <list[str] — véhicules présents dans ce plan, extraits du scénario>,
  "camera_movement": <str — exactement une valeur parmi : "Fixe", "Panoramique horizontal", "Panoramique vertical", "Travelling avant", "Travelling arrière", "Travelling latéral", "Zoom avant", "Zoom arrière", "Steadicam", "Grue / Drone", "Caméra portée", "Plongée", "Contre-plongée">,
  "shot_size": <str — valeur de plan cinéma, exactement une valeur parmi : "GP" (Gros Plan — visage remplissant le cadre), "GM" (Grand Médium — tête et épaules), "PM" (Plan Moyen — jusqu'à la ceinture), "PP" (Plan Poitrine — jusqu'aux mi-cuisses), "PL" (Plan Large — corps entier visible), "PE" (Plan d'Ensemble — personnage(s) dans l'environnement), "PTG" (Plan Très Grand Ensemble — sujet minuscule dans un vaste espace), "Insert" (Insert — détail isolé en très gros plan)>,
  "camera_axis": <str — angle de prise de vue, exactement une valeur parmi : "Face" (angle frontal, symétrique), "3/4" (angle trois-quarts, légère diagonale), "Latéral 90°" (profil strict), "Dos" (dans le dos du sujet), "Plongée" (caméra en hauteur, regardant vers le bas), "Contre-plongée" (caméra basse, regardant vers le haut), "Vue subjective" (point de vue d'un personnage — la caméra EST ses yeux)>,
  "camera_distance": <str — distance métrique estimée entre le sujet principal et la caméra, cohérente avec la valeur de plan. Exemples : GP≈"0.3m"-"0.7m", GM≈"0.7m"-"1.2m", PM≈"1.5m"-"2m", PP≈"2m"-"3m", PL≈"3m"-"6m", PE≈"6m"-"20m", PTG≈"20m"-"100m". Écrire la valeur avec l'unité (ex: "4m", "0.5m", "15m")>,
  "speed": <str — exactement une valeur parmi : "Normale", "Ralenti", "Accéléré">,
  "optic": <str — "Sphérique" ou "Anamorphique">,
  "focal": <str — focale adaptée à la valeur de plan et à l'effet souhaité, ex: "24mm", "35mm", "50mm", "85mm", "100mm">,
  "comments": <str — description factuelle et fidèle de ce qui se passe dans ce plan, extraite du scénario. OBLIGATOIRE : si ce plan contient un dialogue, le citer intégralement entre guillemets avec le nom du personnage (ex : MARC : « Je t'ai toujours aimée. »). INTERDIT : technique caméra, mouvements de caméra, focale, optique — ces éléments sont déjà dans les champs dédiés. AUTORISÉ : qui fait quoi, ce qu'on voit, ce qu'on entend, les dialogues exacts, l'ambiance du moment telle qu'écrite dans le scénario.>,
  "seedance_prompt": <str — DETAILED, dense video generation prompt in {PROMPT_LANG}. Seedance 2.0 yields far better results with RICH visual descriptions, so do NOT be brief. Mandatory structure, faithful to the screenplay: (1) characters present with their appearance/state as described in the screenplay, (2) exact location and environment description from the screenplay, (3) main action and — if dialogue present — the exact words spoken in quotes. THEN enrich the VISUAL rendering WITHOUT inventing any new story element: lighting (direction, quality, color temperature), color palette, textures and materials, mood and atmosphere, and quality cues such as cinematic, ultra-detailed, sharp, photorealistic. Write 3 to 5 rich sentences. NO camera technique (it lives in the dedicated fields); stay strictly faithful to what the screenplay describes.>,
  "sound_prompt": <str — SOUND DESIGN / SFX prompt in {PROMPT_LANG} describing the shot's sound ambience: ambient textures, sound effects, room tone, materials and rhythm of the scene, ready for a sound-effects generator. NO speech, NO voice, NO music score, NO BPM (dialogue lives in seedance_prompt; this is ambience/SFX only). 1 to 2 concise sentences faithful to what the screenplay describes.>
}

Contrainte absolue : duration ne peut jamais dépasser 15.0 secondes (limite de Seedance 2.0).
Retourne UNIQUEMENT le tableau JSON, sans aucun texte avant ou après.\
"""


_FORMAT_PANDORA = """\
Tu es un directeur de la photographie et superviseur de production travaillant avec Pandora, \
un outil de pré-production IA qui génère des clips vidéo via Seedance 2.0 (ByteDance/fal.ai).

Ton rôle : transformer le scénario fourni en mise en page PANDORA — un découpage plan par plan \
conçu pour piloter directement la génération vidéo IA.

FORMAT DE SORTIE OBLIGATOIRE :

—— SÉQUENCE N — TITRE COURT ——  (titre évocateur 2-4 mots, en MAJUSCULES)

P01 | Valeur de plan | Mouvement de caméra | Axe | ~Durée
INT./EXT. LIEU PRÉCIS — MOMENT
Description action : ce que la caméra voit, au présent, concret et visuel.
                NOM PERSONNAGE  (si dialogue, centré en MAJUSCULES)
        Réplique indentée.  (dialogue exact du scénario)
→ SEEDANCE: Prompt vidéo court, descriptif, sensoriel, en français.

P02 | ...
→ SEEDANCE: ...

RÈGLES DE NUMÉROTATION :
- Plans numérotés P01, P02, P03... en continu sur tout le scénario (jamais de réinitialisation par séquence)
- Chaque plan = 2 à 15 secondes maximum (limite absolue Seedance 2.0)
- Découper les scènes longues en plusieurs plans cohérents

VALEURS DE PLAN (utiliser ces termes exacts) :
Grand ensemble | Plan d'ensemble | Plan large | Plan moyen | Plan poitrine | Gros plan | Très gros plan | Insert

MOUVEMENTS (utiliser ces termes exacts) :
Fixe | Panoramique | Travelling avant | Travelling arrière | Travelling latéral | Zoom avant | Zoom arrière | Steadicam | Grue/Drone | Caméra portée

AXES (utiliser ces termes exacts) :
Face | 3/4 | Latéral | Dos | Plongée | Contre-plongée | Subjectif

DURÉE :
- Notation "~Xs" (ex: ~6s, ~10s)
- Maximum absolu : ~15s — si une scène dépasse 15s, la couper en plusieurs plans

RÈGLES POUR LA DESCRIPTION ACTION :
- Décrire UNIQUEMENT ce que la caméra peut voir : matières, textures, couleurs, lumières, gestes, postures, expressions
- Personnages cités par leur NOM uniquement — jamais de description physique (les refs images gèrent la cohérence visuelle)
- Si dialogue présent : le citer intégralement, NOM en MAJUSCULES centré + réplique indentée

RÈGLES POUR LE PROMPT SEEDANCE (après →) :
- Toujours en FRANÇAIS (traduction automatique gérée par Pandora avant envoi)
- Jamais de technique caméra (déjà dans la ligne P01) — décrire uniquement sujet, décor, action, ambiance
- Personnages cités par NOM uniquement — pas de description physique
- RICHE et TRÈS DÉTAILLÉ : Seedance 2.0 donne de bien meilleurs résultats avec des prompts denses — ne sois PAS bref. 3 à 5 phrases développées.
- Décrire précisément : personnage(s) (par NOM), lieu/environnement, action, lumière (direction, qualité, température de couleur), palette de couleurs, textures & matières, atmosphère/mood, et repères de qualité (cinématographique, ultra-détaillé, net, photoréaliste).
- Rester FIDÈLE au scénario : enrichir le rendu visuel mais n'inventer aucun élément narratif (personnages, lieux, événements).
- Structure recommandée : [personnage(s)] + [lieu/environnement] + [action] + [lumière/couleurs/textures/ambiance]
- Si dialogue : inclure la réplique exacte entre guillemets dans le prompt

RÈGLES GLOBALES :
- Conserver TOUT le contenu narratif du scénario original — aucune invention, aucune coupure arbitraire
- Noms de personnages : graphie STRICTEMENT IDENTIQUE partout
- Pas de commentaires ni d'explications hors format — retourner uniquement la mise en page PANDORA\
"""


_FORMAT_PANDORA_EN = """\
You are a director of photography and production supervisor working with Pandora, \
an AI pre-production tool that generates video clips via Seedance 2.0 (ByteDance/fal.ai).

Your role: transform the provided screenplay into a PANDORA layout — a shot-by-shot breakdown \
designed to directly drive AI video generation.

MANDATORY OUTPUT FORMAT:

—— SEQUENCE N — SHORT TITLE ——  (evocative 2-4 word title, in CAPITALS)

P01 | Shot value | Camera movement | Axis | ~Duration
INT./EXT. SPECIFIC LOCATION — TIME
Action description: what the camera sees, in the present tense, concrete and visual.
                CHARACTER NAME  (if dialogue, centered in CAPITALS)
        Indented line.  (exact dialogue from the screenplay)
→ SEEDANCE: Short, descriptive, sensory video prompt, in English.

P02 | ...
→ SEEDANCE: ...

NUMBERING RULES:
- Shots numbered P01, P02, P03... continuously across the whole screenplay (never reset per sequence)
- Each shot = 2 to 15 seconds maximum (absolute Seedance 2.0 limit)
- Split long scenes into several coherent shots

SHOT VALUES (use these exact terms):
Extreme wide | Wide shot | Full shot | Medium shot | Chest shot | Close-up | Extreme close-up | Insert

MOVEMENTS (use these exact terms):
Static | Pan | Dolly in | Dolly out | Lateral tracking | Zoom in | Zoom out | Steadicam | Crane/Drone | Handheld

AXES (use these exact terms):
Front | 3/4 | Lateral | Back | High angle | Low angle | POV

DURATION:
- Notation "~Xs" (e.g. ~6s, ~10s)
- Absolute maximum: ~15s — if a scene exceeds 15s, split it into several shots

RULES FOR THE ACTION DESCRIPTION:
- Describe ONLY what the camera can see: materials, textures, colors, lights, gestures, postures, expressions
- Characters referred to by their NAME only — never a physical description (image refs handle visual consistency)
- If dialogue is present: quote it fully, NAME in CAPITALS centered + indented line

RULES FOR THE SEEDANCE PROMPT (after →):
- Always in ENGLISH
- Never camera technique (already in the P01 line) — describe only subject, setting, action, mood
- Characters referred to by NAME only — no physical description
- RICH and HIGHLY DETAILED: Seedance 2.0 yields far better results with dense prompts — do NOT be brief. 3 to 5 developed sentences.
- Describe precisely: character(s) (by NAME), location/environment, action, lighting (direction, quality, color temperature), color palette, textures & materials, mood/atmosphere, and quality cues (cinematic, ultra-detailed, sharp, photorealistic).
- Stay FAITHFUL to the screenplay: enrich the visual rendering but invent no new narrative element (characters, places, events).
- Recommended structure: [character(s)] + [location/environment] + [action] + [light/color/textures/mood]
- If dialogue: include the exact line in quotes within the prompt

GLOBAL RULES:
- Keep ALL the narrative content of the original screenplay — no invention, no arbitrary cuts
- Character names: STRICTLY IDENTICAL spelling everywhere
- No comments or explanations outside the format — return only the PANDORA layout\
"""


def _format_pandora_prompt(lang: str) -> str:
    """Sélectionne la version FR/EN du prompt de mise en page selon la langue de l'UI."""
    return _FORMAT_PANDORA_EN if lang == "en" else _FORMAT_PANDORA


def _arrange_screenplay_prompt(lang: str) -> str:
    lang_instruction = "English" if lang == "en" else "French (français)"
    return _ARRANGE_SCREENPLAY_TMPL.replace("{LANG_INSTRUCTION}", lang_instruction)


def _storyboard_prompt(lang: str) -> str:
    prompt_lang = "English" if lang == "en" else "French (français)"
    return _GENERATE_STORYBOARD_TMPL.replace("{PROMPT_LANG}", prompt_lang)


_EXTRACT_CHARACTERS = """\
Tu es un assistant de pré-production cinéma. Analyse le scénario fourni et identifie TOUS les personnages, sans exception.

Inclure OBLIGATOIREMENT :
- Les personnages principaux nommés
- Les personnages secondaires nommés
- Les figurants et personnages d'arrière-plan, même non nommés — donne-leur un nom de fonction descriptif (ex : "Soldat ennemi 1", "Passant", "Technicien radar", "Garde du corps")
- Tous les personnages mentionnés même brièvement

Retourne UNIQUEMENT un tableau JSON valide. Chaque élément représente un personnage :
{
  "name": <str — nom propre du personnage, ou fonction précise si non nommé>,
  "description": <str — description physique (apparence, morphologie, âge, traits distinctifs) et traits de caractère. 1-2 phrases MAX. La description doit servir de brief pour un casting visuel — apparence uniquement.>,
  "prompt": <str — description visuelle ENRICHIE en français pour la génération d'image IA par Nano Banana. Inclure OBLIGATOIREMENT : morphologie et silhouette, âge apparent, carnation et traits du visage (forme du visage, mâchoire, yeux, nez, lèvres), couleur et coupe de cheveux, tenue vestimentaire complète avec couleurs et matières, posture et attitude corporelle, éclairage cinématographique adapté au ton du film (ex : lumière froide de film noir, lumière chaude de comédie). 4-6 phrases détaillées, UNIQUEMENT des descripteurs VISUELS concrets. Exemple de qualité : "Homme de 35 ans, silhouette athlétique et nerveuse, 1m80, peau mate légèrement hâlée. Visage anguleux, mâchoire carrée marquée de barbe de 3 jours grise, regard sombre et légèrement absent sous des sourcils épais. Cheveux châtains courts, légèrement en désordre. Porte une veste de combat kaki délavée et tachée de boue, pantalon cargo beige aux genoux écorchés, casque M1 cabossé posé de travers. Posture droite mais fatiguée, épaules légèrement affaissées. Éclairage latéral naturel avec hautes lumières dorées de fin d'après-midi.">,
  "role": <str — exactement "Principal", "Secondaire" ou "Figurant">
}

Retourne UNIQUEMENT le tableau JSON, sans texte avant ou après.\
"""

_EXTRACT_DECORS = """\
Tu es un assistant de pré-production cinéma. Analyse le scénario fourni et identifie tous les décors distincts (lieux de tournage).

LANGUE : Toutes les valeurs textuelles du JSON doivent être rédigées en FRANÇAIS, quelle que soit la langue du scénario. La traduction en anglais pour le modèle IA est effectuée automatiquement en aval.

Retourne UNIQUEMENT un tableau JSON valide. Chaque élément représente un décor :
{
  "name": <str — nom court du décor en français, ex: "Salle à manger", "Forêt enneigée">,
  "description": <str — description en FRANÇAIS de l'ambiance, de l'époque, du style visuel, 1-2 phrases>,
  "prompt": <str — description visuelle ENRICHIE en français pour la génération d'image IA. Inclure OBLIGATOIREMENT : style architectural ou naturel précis (matériaux, époque, état dégradé/neuf), éclairage détaillé (heure du jour, source lumineuse, direction, intensité), palette de couleurs dominante, ambiance atmosphérique (météo, saison, humidité, fumée), détails de mise en scène caractéristiques (mobilier, végétation, objets), profondeur de champ suggérée. 4-6 phrases visuellement riches. Uniquement des descripteurs CONCRETS et VISUELS.>,
  "category": <str — exactement une valeur parmi : "Intérieur", "Extérieur", "Studio", "Urbain", "Rural", "Aquatique", "Aérien", "Fantastique", "Industriel", "Historique", "Autre">,
  "scene_headers": <list[str] — liste des en-têtes de scène exacts (lignes INT./EXT.) du scénario où ce décor apparaît, ex: ["INT. SALLE À MANGER — JOUR", "INT. SALLE À MANGER — NUIT"]>
}

Retourne UNIQUEMENT le tableau JSON, sans texte avant ou après.\
"""

_EXTRACT_ACCESSORIES = """\
Tu es un assistant de pré-production cinéma. Analyse le scénario fourni et identifie tous les accessoires (props) significatifs pour le tournage.

EXCLURE ABSOLUMENT : vêtements, costumes, uniformes, tenues, robes, manteaux, chaussures — ces éléments appartiennent à la section HMC (Habillage), PAS aux accessoires.
EXCLURE ÉGALEMENT : véhicules (voitures, motos, avions…) — ils ont leur propre section.

Inclure uniquement : objets physiques manipulables ou visibles dans le cadre (armes, bijoux, valises, documents, appareils électroniques, mobilier, outils, etc.).

Retourne UNIQUEMENT un tableau JSON valide. Chaque élément représente un accessoire :
{
  "name": <str — nom de l'accessoire>,
  "description": <str — description de l'objet et son rôle dans l'histoire, 1 phrase>,
  "prompt": <str — description visuelle ENRICHIE en français pour la génération d'image IA. Inclure : matière exacte (cuir vieilli, acier brossé, bois sombre...), couleur dominante et teintes secondaires, dimensions relatives, état de conservation (neuf/usé/endommagé/patiné), détails distinctifs (gravures, décorations, marques d'usure), contexte de présentation (posé sur une surface, tenu en main, éclairage). 2-3 phrases concrètes et visuelles.>,
  "category": <str — exactement une valeur parmi : "Bijoux", "Armes", "Électronique", "Mobilier", "Document", "Bagage", "Outil", "Autre…">
}

Retourne UNIQUEMENT le tableau JSON, sans texte avant ou après.\
"""

_EXTRACT_HMC = """\
Tu es un assistant de pré-production cinéma. Analyse le scénario fourni et identifie tous les éléments de Habillage, Maquillage et Coiffure (HMC) pour chaque personnage.

Types à détecter :

HABIT (vêtements, costumes, tenues) :
- Uniformes militaires, tenues de combat, équipements tactiques
- Vêtements civils distinctifs, robes, costumes de scène
- Tenues de camouflage, combinaisons, armures
- Tout autre vêtement ou costume porté par un personnage

MAQUILLAGE (produit physique appliqué volontairement sur le visage/corps) :
- Peintures de guerre, camouflage de combat appliqué sur le visage
- Cicatrices prothétiques, tatouages visibles, marques corporelles artificielles
- Maquillage de scène, effets de vieillissement, prothèses
- Blessures maquillées, faux sang, ecchymoses artificielles

EXCLURE ABSOLUMENT du MAQUILLAGE : expressions faciales, émotions, regards, pleurs, sourires, grimaces, froncements de sourcils — ce sont des états émotionnels ou musculaires, PAS du maquillage. Ne jamais créer une fiche HMC pour une émotion ou une expression.

COIFFURE (coupe, style, couleur de cheveux ou barbe) :
- Coupes spécifiques (rase, militaire, longue, tressée, etc.)
- Barbes, moustaches, favoris, sideburns
- Couleur ou décoloration des cheveux
- Perruques, postiche, rajouts
- Chignons, tresses, styles distinctifs

Crée une fiche HMC par type ET par personnage. Si un personnage a un uniforme ET une peinture de guerre ET une coupe militaire, crée 3 fiches séparées.

Retourne UNIQUEMENT un tableau JSON valide. Chaque élément représente un item HMC :
{
  "name": <str — nom court descriptif, ex: "Uniforme de combat de Viktor", "Peintures de guerre de Raven", "Coupe rase militaire de Raven">,
  "description": <str — description précise et visuelle, 1-2 phrases>,
  "prompt": <str — description visuelle ENRICHIE en français pour la génération d'image IA. Inclure : tissu ou matière précis (coton, cuir, laine...), couleurs exactes, coupe et style (militaire, civil, époque), état (neuf/usé/sali), détails distinctifs (insignes, broderies, déchirures, taches). 2-3 phrases visuellement précises.>,
  "hmc_type": <str — exactement "Habit", "Maquillage" ou "Coiffure">,
  "character_name": <str — nom exact du personnage concerné>
}

Retourne UNIQUEMENT le tableau JSON, sans texte avant ou après.\
"""

_EXTRACT_VEHICLES = """\
Tu es un assistant de pré-production cinéma. Analyse le scénario fourni et identifie tous les véhicules significatifs (voitures, motos, camions, bateaux, avions, trains, vélos, etc.).

Retourne UNIQUEMENT un tableau JSON valide. Chaque élément représente un véhicule :
{
  "name": <str — nom du véhicule, ex: "La DS noire de Viktor", "Camion militaire">,
  "description": <str — description de l'aspect visuel et du rôle dans l'histoire, 1-2 phrases>,
  "prompt": <str — description visuelle ENRICHIE en français pour la génération d'image IA. Inclure : marque et modèle si connu ou type précis, couleur de carrosserie, état (neuf/patiné/endommagé/militaire), époque, détails distinctifs (chromés, rayures, logos, équipements spéciaux), contexte d'éclairage et environnement immédiat. 2-3 phrases concrètes.>,
  "category": <str — exactement une valeur parmi : "Voiture", "Moto", "Camion", "Bateau", "Avion", "Train", "Vélo", "Autre">
}

Retourne UNIQUEMENT le tableau JSON, sans texte avant ou après.\
"""


# ── JSON helpers ─────────────────────────────────────────────────────────────

def _parse_shots_robust(json_str: str) -> list:
    """Parse a JSON array of shots, with fallback for malformed LLM output."""
    try:
        return json.loads(json_str)
    except json.JSONDecodeError:
        pass

    shots = []
    depth = 0
    start = None
    i = 0
    in_string = False
    escape_next = False

    while i < len(json_str):
        c = json_str[i]
        if escape_next:
            escape_next = False
        elif c == '\\' and in_string:
            escape_next = True
        elif c == '"':
            in_string = not in_string
        elif not in_string:
            if c == '{':
                if depth == 0:
                    start = i
                depth += 1
            elif c == '}':
                depth -= 1
                if depth == 0 and start is not None:
                    try:
                        obj = json.loads(json_str[start:i + 1])
                        if isinstance(obj, dict):
                            shots.append(obj)
                    except json.JSONDecodeError:
                        pass
                    start = None
        i += 1

    return shots


def _fmt_err(e: Exception) -> str:
    """Formats an Anthropic/network exception into a readable French message."""
    msg = str(e)
    low = msg.lower()
    if "connection" in low or "connect" in low or "network" in low or "ssl" in low:
        return (
            "Erreur de connexion au serveur Anthropic.\n"
            "Vérifiez votre connexion internet.\n"
            "Si vous utilisez un VPN ou proxy, désactivez-le et réessayez.\n\n"
            f"Détail : {msg}"
        )
    if "401" in msg or "authentication" in low or "api_key" in low:
        return (
            "Clé API Anthropic invalide ou expirée.\n"
            "Vérifiez la clé dans l'onglet Paramètres.\n\n"
            f"Détail : {msg}"
        )
    if "429" in msg or "rate" in low:
        return (
            "Limite de requêtes Anthropic atteinte. Attendez quelques secondes et réessayez.\n\n"
            f"Détail : {msg}"
        )
    return f"Erreur Anthropic : {msg}"


# ── Workers ───────────────────────────────────────────────────────────────────

class FormatScreenplayWorker(QThread):
    chunk    = pyqtSignal(str)
    finished = pyqtSignal(str)
    failed   = pyqtSignal(str)

    def __init__(self, text: str):
        super().__init__()
        self._text = text

    def run(self):
        from core.ai_provider import stream as ai_stream, key_error
        err = key_error()
        if err:
            self.failed.emit(err)
            return
        try:
            lang = _get_lang()
            full_text = ai_stream(_FORMAT_SCREENPLAY, _lang_hint(lang) + self._text,
                                  on_chunk=self.chunk.emit,
                                  tier="creative", max_tokens=8192)
            self.finished.emit(full_text.strip())
        except Exception as e:
            self.failed.emit(_fmt_err(e))


class FormatPandoraWorker(QThread):
    chunk    = pyqtSignal(str)
    finished = pyqtSignal(str)
    failed   = pyqtSignal(str)

    def __init__(self, text: str):
        super().__init__()
        self._text = text

    def run(self):
        from core.ai_provider import stream as ai_stream, key_error
        err = key_error()
        if err:
            self.failed.emit(err)
            return
        try:
            lang = _get_lang()
            full_text = ai_stream(_format_pandora_prompt(lang),
                                  _lang_hint(lang) + self._text,
                                  on_chunk=self.chunk.emit,
                                  tier="creative", max_tokens=16000)
            self.finished.emit(full_text.strip())
        except Exception as e:
            self.failed.emit(_fmt_err(e))


def _intensity_analyse_hint(intensity: int, lang: str = "fr") -> str:
    if lang == "en":
        if intensity <= 3:
            return (
                f"[ARRANGEMENT INTENSITY: {intensity}/10 — LIGHT. "
                "Identify only critical issues. "
                "Preserve the existing structure and choices as much as possible. "
                "Your suggestions must be minimal and non-invasive.]"
            )
        if intensity <= 6:
            return (
                f"[ARRANGEMENT INTENSITY: {intensity}/10 — MODERATE. "
                "Propose balanced improvements: fix pacing, "
                "improve a few scenes, refine dialogues. "
                "Keep the core structure in place.]"
            )
        return (
            f"[ARRANGEMENT INTENSITY: {intensity}/10 — STRONG. "
            "Propose significant restructuring. "
            "Don't hesitate to reorder, condense or expand sequences "
            "to maximize dramatic impact. "
            + ("Treat this text as a rough draft to be radically transformed." if intensity == 10 else "")
            + "]"
        )
    if intensity <= 3:
        return (
            f"[INTENSITÉ D'ARRANGEMENT : {intensity}/10 — LÉGER. "
            "Identifie uniquement les problèmes critiques. "
            "Préserve au maximum la structure et les choix existants. "
            "Tes suggestions doivent être minimales et non invasives.]"
        )
    if intensity <= 6:
        return (
            f"[INTENSITÉ D'ARRANGEMENT : {intensity}/10 — MODÉRÉ. "
            "Propose des améliorations équilibrées : corrige le rythme, "
            "améliore quelques scènes, affine les dialogues. "
            "Garde l'essentiel de la structure en place.]"
        )
    return (
        f"[INTENSITÉ D'ARRANGEMENT : {intensity}/10 — FORT. "
        "Propose des restructurations significatives. "
        "N'hésite pas à réordonner, condenser ou développer des séquences "
        "pour maximiser l'impact dramatique. "
        + ("Traite ce texte comme un premier jet à transformer radicalement." if intensity == 10 else "")
        + "]"
    )


def _intensity_apply_hint(intensity: int, lang: str = "fr") -> str:
    if lang == "en":
        if intensity <= 3:
            return (
                f"[APPLICATION INTENSITY: {intensity}/10 — LIGHT. "
                "Apply only the strictly necessary corrections. "
                "Preserve virtually all of the original text, its structure and phrasing. "
                "Fix only obvious errors.]"
            )
        if intensity <= 6:
            return (
                f"[APPLICATION INTENSITY: {intensity}/10 — MODERATE. "
                "Apply suggestions with restraint: restructure a few scenes, "
                "improve pacing and dialogues, without distorting the project.]"
            )
        return (
            f"[APPLICATION INTENSITY: {intensity}/10 — STRONG. "
            "Apply suggestions ambitiously. "
            "Restructure, reorder, condense or expand freely to maximize effectiveness. "
            + ("This text is a rough draft: transform it radically." if intensity == 10 else "")
            + "]"
        )
    if intensity <= 3:
        return (
            f"[INTENSITÉ D'APPLICATION : {intensity}/10 — LÉGER. "
            "N'applique que les corrections minimales indispensables. "
            "Conserve pratiquement tout le texte original, sa structure et ses formulations. "
            "Corrige uniquement les erreurs manifestes.]"
        )
    if intensity <= 6:
        return (
            f"[INTENSITÉ D'APPLICATION : {intensity}/10 — MODÉRÉ. "
            "Applique les suggestions avec mesure : restructure quelques scènes, "
            "améliore le rythme et les dialogues, sans dénaturer le projet.]"
        )
    return (
        f"[INTENSITÉ D'APPLICATION : {intensity}/10 — FORT. "
        "Applique les suggestions de façon ambitieuse. "
        "Restructure, réordonne, condense ou développe librement pour maximiser l'efficacité. "
        + ("Ce texte est un brouillon : transforme-le radicalement." if intensity == 10 else "")
        + "]"
    )


class ArrangeScreenplayWorker(QThread):
    finished = pyqtSignal(str)
    failed   = pyqtSignal(str)
    chunk    = pyqtSignal(str)

    def __init__(self, text: str, duration_secs: int = 0, intensity: int = 5,
                 project_context: dict | None = None, ref_analysis: str = ""):
        super().__init__()
        self._text            = text
        self._duration_secs   = duration_secs
        self._intensity       = max(1, min(10, intensity))
        self._project_context = project_context or {}
        self._ref_analysis    = ref_analysis

    def run(self):
        from core.ai_provider import stream as ai_stream, key_error
        err = key_error()
        if err:
            self.failed.emit(err)
            return
        try:
            lang = _get_lang()
            prefixes = [_intensity_analyse_hint(self._intensity, lang)]
            if self._duration_secs > 0:
                mins, secs = divmod(self._duration_secs, 60)
                dur_str = f"{mins}min {secs:02d}s" if mins else f"{secs}s"
                if lang == "en":
                    prefixes.append(
                        f"[TARGET DURATION: {dur_str} = {self._duration_secs} seconds maximum."
                        f" Take this constraint into account in your pacing and structure suggestions.]"
                    )
                else:
                    prefixes.append(
                        f"[DURÉE CIBLE : {dur_str} = {self._duration_secs} secondes maximum."
                        f" Tiens compte de cette contrainte dans tes suggestions de rythme et structure.]"
                    )

            chars  = self._project_context.get("characters", [])
            decors = self._project_context.get("decors", [])
            if chars or decors:
                if lang == "en":
                    ctx = ["[ELEMENTS ALREADY REGISTERED IN PANDORA — reference these exact names in your suggestions]"]
                    if chars:
                        ctx.append("Cast characters:")
                        for c in chars:
                            role = c.get("role", "")
                            ctx.append(f"  · {c.get('name', '')} ({role})" if role else f"  · {c.get('name', '')}")
                    if decors:
                        ctx.append("Registered locations:")
                        for d in decors:
                            cat = d.get("category", "")
                            ctx.append(f"  · {d.get('name', '')} ({cat})" if cat else f"  · {d.get('name', '')}")
                else:
                    ctx = ["[ÉLÉMENTS DÉJÀ ENREGISTRÉS DANS PANDORA — référence ces noms exacts dans tes suggestions]"]
                    if chars:
                        ctx.append("Personnages du casting :")
                        for c in chars:
                            role = c.get("role", "")
                            ctx.append(f"  · {c.get('name', '')} ({role})" if role else f"  · {c.get('name', '')}")
                    if decors:
                        ctx.append("Décors enregistrés :")
                        for d in decors:
                            cat = d.get("category", "")
                            ctx.append(f"  · {d.get('name', '')} ({cat})" if cat else f"  · {d.get('name', '')}")
                prefixes.append("\n".join(ctx))

            if self._ref_analysis.strip():
                if lang == "en":
                    prefixes.append(
                        "[VISUAL REFERENCES ANALYSIS — Factor in these visual descriptions "
                        "for narrative coherence, visual consistency and scene pacing suggestions]\n"
                        + self._ref_analysis.strip()
                    )
                else:
                    prefixes.append(
                        "[ANALYSE DES RÉFÉRENCES VISUELLES — Intègre ces descriptions dans tes "
                        "suggestions d'arrangement : cohérence visuelle, décors, ambiances, rythme]\n"
                        + self._ref_analysis.strip()
                    )

            user_content = _lang_hint(lang) + "\n\n".join(prefixes) + "\n\n" + self._text
            full_text = ai_stream(_arrange_screenplay_prompt(lang), user_content,
                                  on_chunk=self.chunk.emit,
                                  tier="creative", max_tokens=4096)
            self.finished.emit(full_text)
        except Exception as e:
            self.failed.emit(_fmt_err(e))


class ApplyArrangeWorker(QThread):
    """Applique les suggestions d'arrangement au scénario original via Claude."""
    chunk    = pyqtSignal(str)
    finished = pyqtSignal(str)
    failed   = pyqtSignal(str)

    def __init__(self, original_text: str, suggestions: str, intensity: int = 5):
        super().__init__()
        self._text        = original_text
        self._suggestions = suggestions
        self._intensity   = max(1, min(10, intensity))

    def run(self):
        from core.ai_provider import stream as ai_stream, key_error
        err = key_error()
        if err:
            self.failed.emit(err)
            return
        try:
            lang = _get_lang()
            if lang == "en":
                user_content = (
                    f"{_lang_hint(lang)}"
                    f"{_intensity_apply_hint(self._intensity, lang)}\n\n"
                    f"ORIGINAL SCREENPLAY:\n{self._text}\n\n"
                    f"ARRANGEMENT SUGGESTIONS:\n{self._suggestions}"
                )
            else:
                user_content = (
                    f"{_intensity_apply_hint(self._intensity, lang)}\n\n"
                    f"SCÉNARIO ORIGINAL :\n{self._text}\n\n"
                    f"SUGGESTIONS D'ARRANGEMENT :\n{self._suggestions}"
                )
            full_text = ai_stream(_APPLY_ARRANGE, user_content,
                                  on_chunk=self.chunk.emit,
                                  tier="creative", max_tokens=8192)
            self.finished.emit(full_text.strip())
        except Exception as e:
            self.failed.emit(_fmt_err(e))


class GenerateStoryboardWorker(QThread):
    """Génère un découpage technique storyboard depuis un texte de scénario."""
    finished = pyqtSignal(list)   # liste de dicts (plans)
    failed   = pyqtSignal(str)

    def __init__(self, text: str, duration_secs: int = 0,
                 element_names: dict | None = None):
        super().__init__()
        self._text          = text
        self._duration_secs = duration_secs
        self._element_names = element_names or {}

    def run(self):
        from core.ai_provider import complete as ai_complete, key_error, ai_name
        err = key_error()
        if err:
            self.failed.emit(err)
            return
        try:
            lang = _get_lang()

            # Bloc noms exacts — injecté AVANT le scénario pour ancrer les noms
            names_block = ""
            en = self._element_names

            # Charge les accessoires depuis la DB si non fournis explicitement
            acc_constraint: list | None = en.get("accessories") if en else None
            if acc_constraint is None:
                try:
                    import core.accessories as _acc_m
                    acc_constraint = [a["name"] for a in _acc_m.list_accessories() if a.get("name")]
                except Exception:
                    acc_constraint = None

            # Charge les personnages depuis la DB si non fournis explicitement
            char_constraint: list | None = en.get("characters") if en else None
            if char_constraint is None:
                try:
                    import core.casting as _cast_m
                    char_constraint = [c["name"] for c in _cast_m.list_characters() if c.get("name")]
                except Exception:
                    char_constraint = None

            lines = [
                "[NOMS EXACTS DES ÉLÉMENTS PANDORA — utilise EXACTEMENT ces noms "
                "dans character_names, decor_name, accessory_names et vehicle_names :]"
            ]
            if char_constraint:
                lines.append(
                    "Personnages (casse OBLIGATOIRE — copie exacte) : "
                    + ", ".join(char_constraint)
                )
            if en and en.get("decors"):
                lines.append("Décors : " + ", ".join(en["decors"]))
            if acc_constraint:
                lines.append(
                    "Accessoires (LISTE EXHAUSTIVE — n'utilise AUCUN autre nom) : "
                    + ", ".join(acc_constraint)
                )
            elif acc_constraint is not None:
                # Liste vide explicitement chargée depuis la DB = aucun accessoire défini
                lines.append(
                    "[CONTRAINTE ABSOLUE : accessory_names = [] pour TOUS les plans"
                    " — aucun accessoire n'est défini dans ce projet]"
                )
            if en and en.get("vehicles"):
                lines.append("Véhicules : " + ", ".join(en["vehicles"]))
            if len(lines) > 1:
                names_block = "\n".join(lines) + "\n\n"

            user_content = _lang_hint(lang) + names_block + self._text
            if self._duration_secs > 0:
                mins, secs = divmod(self._duration_secs, 60)
                dur_str = f"{mins}min {secs:02d}s" if mins else f"{secs}s"
                if lang == "en":
                    budget_hint = (
                        f"[TOTAL DURATION BUDGET: {dur_str} = {self._duration_secs} seconds."
                        f" The sum of all 'duration' values must be LESS THAN OR EQUAL TO {self._duration_secs} seconds."
                        f" Distribute this budget wisely — short shots for action, longer for atmosphere and dialogue.]\n\n"
                    )
                else:
                    budget_hint = (
                        f"[BUDGET DURÉE TOTAL : {dur_str} = {self._duration_secs} secondes."
                        f" La somme de toutes les valeurs 'duration' des plans doit être"
                        f" INFÉRIEURE OU ÉGALE à {self._duration_secs} secondes."
                        f" Répartis intelligemment ce budget — plans courts pour les actions,"
                        f" plans plus longs pour les atmosphères et dialogues.]\n\n"
                    )
                user_content = _lang_hint(lang) + names_block + budget_hint + self._text
            raw = ai_complete(_storyboard_prompt(lang), user_content,
                              tier="creative", max_tokens=16000).strip()
            start = raw.find("[")
            end   = raw.rfind("]") + 1
            if start == -1 or end == 0:
                self.failed.emit(f"Réponse {ai_name()} invalide — pas de tableau JSON trouvé.")
                return

            json_str = raw[start:end]
            shots = _parse_shots_robust(json_str)

            if not shots:
                self.failed.emit(f"Aucun plan extrait — la réponse {ai_name()} était mal formée.")
                return

            for s in shots:
                s["duration"] = min(float(s.get("duration", 8.0)), 15.0)
                s.setdefault("character_ids", [])
                s.setdefault("accessory_ids", [])
                s.setdefault("decor_id",      "")

            # Résolution automatique decor_name → decor_id
            try:
                import core.decors as _dec_m
                _all_decors  = _dec_m.list_decors()
                _dec_by_name = {
                    d["name"].strip().lower(): d
                    for d in _all_decors if d.get("name") and d.get("id")
                }
                for s in shots:
                    if not s.get("decor_id") and s.get("decor_name"):
                        _match = _dec_by_name.get(s["decor_name"].strip().lower())
                        if _match:
                            s["decor_id"] = _match["id"]
            except Exception:
                pass

            # Résolution automatique character_names → character_ids
            try:
                import core.casting as _cast_m
                _all_chars   = _cast_m.list_characters()
                _char_by_name = {
                    c["name"].strip().lower(): c
                    for c in _all_chars if c.get("name") and c.get("id")
                }
                for s in shots:
                    if not s.get("character_ids") and s.get("character_names"):
                        s["character_ids"] = [
                            _char_by_name[n.strip().lower()]["id"]
                            for n in s["character_names"]
                            if n.strip().lower() in _char_by_name
                        ]
            except Exception:
                pass

            self.finished.emit(shots)
        except Exception as e:
            self.failed.emit(_fmt_err(e))


# ── Workers d'extraction ──────────────────────────────────────────────────────

def _extract_worker(system_prompt: str, text: str, max_tokens: int = 4096) -> list:
    """Shared extraction logic: call the AI provider, return parsed JSON list."""
    from core.ai_provider import complete as ai_complete, key_error
    err = key_error()
    if err:
        raise ValueError(err)
    lang = _get_lang()
    raw = ai_complete(system_prompt, _lang_hint(lang) + text,
                      tier="creative", max_tokens=max_tokens).strip()
    start = raw.find("[")
    end   = raw.rfind("]") + 1
    if start == -1 or end == 0:
        return []
    return _parse_shots_robust(raw[start:end])


class ExtractCharactersWorker(QThread):
    """Extrait les personnages du scénario et les enregistre dans Casting."""
    finished = pyqtSignal(list)
    failed   = pyqtSignal(str)

    def __init__(self, text: str):
        super().__init__()
        self._text = text

    def run(self):
        try:
            items = _extract_worker(_EXTRACT_CHARACTERS, self._text)
            self.finished.emit(items)
        except Exception as e:
            self.failed.emit(_fmt_err(e))


class ExtractDecorsWorker(QThread):
    """Extrait les décors du scénario et les enregistre dans Décors."""
    finished = pyqtSignal(list)
    failed   = pyqtSignal(str)

    def __init__(self, text: str):
        super().__init__()
        self._text = text

    def run(self):
        try:
            items = _extract_worker(_EXTRACT_DECORS, self._text)
            self.finished.emit(items)
        except Exception as e:
            self.failed.emit(_fmt_err(e))


class ExtractAccessoriesWorker(QThread):
    """Extrait les accessoires du scénario et les enregistre dans Accessoires."""
    finished = pyqtSignal(list)
    failed   = pyqtSignal(str)

    def __init__(self, text: str):
        super().__init__()
        self._text = text

    def run(self):
        try:
            items = _extract_worker(_EXTRACT_ACCESSORIES, self._text)
            self.finished.emit(items)
        except Exception as e:
            self.failed.emit(_fmt_err(e))


class ExtractHMCWorker(QThread):
    """Extrait les éléments HMC du scénario et les enregistre dans HMC."""
    finished = pyqtSignal(list)
    failed   = pyqtSignal(str)

    def __init__(self, text: str):
        super().__init__()
        self._text = text

    def run(self):
        try:
            items = _extract_worker(_EXTRACT_HMC, self._text)
            self.finished.emit(items)
        except Exception as e:
            self.failed.emit(_fmt_err(e))


class ExtractVehiclesWorker(QThread):
    """Extrait les véhicules du scénario et les enregistre dans Véhicules."""
    finished = pyqtSignal(list)
    failed   = pyqtSignal(str)

    def __init__(self, text: str):
        super().__init__()
        self._text = text

    def run(self):
        try:
            items = _extract_worker(_EXTRACT_VEHICLES, self._text)
            self.finished.emit(items)
        except Exception as e:
            self.failed.emit(_fmt_err(e))


class AnalyzeReferencesWorker(QThread):
    """Analyse multimodale d'images de référence via Claude Sonnet.
    Retourne une description enrichie des personnages/décors/ambiances détectés."""
    chunk  = pyqtSignal(str)
    done   = pyqtSignal(str)
    failed = pyqtSignal(str)

    _SYSTEM = (
        "Tu es un superviseur artistique pour Pandora, un outil de pré-production cinéma. "
        "On te fournit une ou plusieurs images de référence visuelle (personnages, décors, ambiances, "
        "objets, costumes, etc.). Tu dois analyser chaque image et produire une description "
        "précise et détaillée en français, orientée prompt de génération vidéo IA. "
        "Pour chaque image, identifie : les personnages visibles (apparence, vêtements, attitude), "
        "les décors (lieu, éclairage, époque, style architectural), l'ambiance générale "
        "(heure du jour, météo, palette de couleurs, mood), les accessoires ou props importants. "
        "Formate le résultat ainsi :\n"
        "**IMAGE N** (si plusieurs images)\n"
        "• **Personnages** : ...\n"
        "• **Décor** : ...\n"
        "• **Ambiance** : ...\n"
        "• **Accessoires/Props** : ...\n"
        "• **Prompt enrichi suggéré** : (un prompt court en anglais, optimisé pour Seedance 2.0)\n\n"
        "Sois précis, concis et orienté production cinéma. "
        "Si le scénario est fourni, mets les descriptions en rapport avec l'univers du film."
    )

    def __init__(self, ref_paths: list[str], scenario_text: str = ""):
        super().__init__()
        self._paths   = ref_paths
        self._scenario = scenario_text

    def run(self):
        import base64
        import mimetypes
        cfg = load_config()
        key = cfg.get("anthropic_key", "").strip()
        if not key:
            self.failed.emit("Clé API Anthropic manquante.\nConfigure-la dans Paramètres.")
            return
        try:
            # VISION (images) : volontairement sur Anthropic, hors couche ai_provider —
            # les autres fournisseurs gèrent la vision différemment (périmètre v1 = texte).
            import anthropic
            client = anthropic.Anthropic(api_key=key)

            content: list = []
            for i, path in enumerate(self._paths):
                if not __import__("os").path.isfile(path):
                    continue
                # Redimensionne AVANT l'envoi (fix « 413 request_too_large » avec
                # plusieurs photos pleine résolution) — voir core/image_payload.
                from core.image_payload import encode_image_for_vision
                mime, data = encode_image_for_vision(path)
                if len(self._paths) > 1:
                    content.append({
                        "type": "text",
                        "text": f"Image {i + 1} :",
                    })
                content.append({
                    "type": "image",
                    "source": {"type": "base64", "media_type": mime, "data": data},
                })

            if not content:
                self.failed.emit("Aucune image valide à analyser.")
                return

            user_text = "Analyse ces images de référence pour le film."
            if self._scenario.strip():
                excerpt = self._scenario.strip()[:1500]
                user_text += (
                    f"\n\nExtrait du scénario (contexte) :\n{excerpt}"
                )
            content.append({"type": "text", "text": user_text})

            full_text = ""
            with client.messages.stream(
                model=_MODEL,
                max_tokens=2048,
                system=self._SYSTEM,
                messages=[{"role": "user", "content": content}],
            ) as stream:
                for text in stream.text_stream:
                    full_text += text
                    self.chunk.emit(text)
            self.done.emit(full_text.strip())
        except Exception as e:
            self.failed.emit(_fmt_err(e))


class EnrichScenarioWithRefsWorker(QThread):
    """Enrichit le scénario en croisant son texte avec l'analyse visuelle des références.

    Claude identifie les correspondances (personnages, décors, ambiances) et enrichit
    uniquement les passages du scénario qui ont un équivalent dans les images analysées.
    """
    chunk  = pyqtSignal(str)
    done   = pyqtSignal(str)
    failed = pyqtSignal(str)

    _SYSTEM = """\
Tu es un scénariste expert spécialisé dans l'enrichissement de scénarios cinéma \
à partir de références visuelles.

Tu reçois :
1. Un scénario existant
2. Une analyse visuelle d'images de référence (personnages, décors, ambiances, lumières, textures)

Ta mission : enrichir le scénario en intégrant les détails visuels des références \
là où ils correspondent à des éléments déjà présents dans le texte.

Règles strictes :
- Ne réécris PAS le scénario de zéro — tu enrichis uniquement ce qui est déjà là
- Identifie les correspondances : si une référence montre un samouraï et que le scénario \
mentionne un samouraï, enrichis la description de ce personnage avec les détails visuels \
(armure, texture, couleurs, posture, éclairage)
- Idem pour les décors : si une référence montre une architecture symétrique et infinie \
et que le scénario se déroule dans un lieu similaire, enrichis ce lieu avec ces détails visuels
- Conserve rigoureusement la structure narrative, le rythme, le ton et les événements du scénario
- Intègre les détails visuels de façon naturelle dans le flux du texte existant \
(pas de liste, pas de bloc séparé)
- Si un élément du scénario n'a aucune correspondance dans les références, laisse-le intact
- Retourne UNIQUEMENT le scénario enrichi, sans commentaire ni explication préalable
"""

    def __init__(self, scenario_text: str, ref_analysis: str):
        super().__init__()
        self._scenario = scenario_text
        self._analysis = ref_analysis

    def run(self):
        try:
            from anthropic import Anthropic
            cfg = load_config()
            key = cfg.get("anthropic_key", "")
            if not key:
                self.failed.emit("Clé Anthropic manquante (configurable dans Paramètres).")
                return
            client = Anthropic(api_key=key)
            lang = _get_lang()
            user_content = (
                _lang_hint(lang)
                + "=== SCÉNARIO À ENRICHIR ===\n"
                + self._scenario.strip()
                + "\n\n=== ANALYSE DES RÉFÉRENCES VISUELLES ===\n"
                + self._analysis.strip()
            )
            full_text = ""
            with client.messages.stream(
                model=_MODEL,
                max_tokens=4096,
                system=self._SYSTEM,
                messages=[{"role": "user", "content": user_content}],
            ) as stream:
                for text in stream.text_stream:
                    full_text += text
                    self.chunk.emit(text)
            self.done.emit(full_text.strip())
        except Exception as e:
            self.failed.emit(_fmt_err(e))


# ── Helpers correspondance de noms (fuzzy / normalisé) ───────────────────────

def _strip_accents(text: str) -> str:
    """Lowercase + supprime les accents (NFD decomposition)."""
    nfkd = unicodedata.normalize("NFD", text.lower())
    return "".join(c for c in nfkd if not unicodedata.combining(c))


_FRENCH_ARTICLES_RE = re.compile(
    r"^(le |la |les |l’|l'|un |une |des |du |de la |de |d’|d')"
)


def _normalize_catalog_name(name: str) -> str:
    """Normalise un nom de catalogue : accents supprimés + article initial retiré."""
    s = _strip_accents(name.strip())
    s = _FRENCH_ARTICLES_RE.sub("", s).strip()
    return s


def _same_name(n1: str, n2: str) -> bool:
    """True si deux noms référencent le même élément après normalisation."""
    return _normalize_catalog_name(n1) == _normalize_catalog_name(n2)


def _name_in_text(catalog_name: str, search_text: str) -> bool:
    """True si catalog_name (ou sa forme normalisée) est présent dans search_text.

    Gère :
    - "Le Samouraï" ↔ "samouraï"  (article + accent)
    - "Inspector Tanaka" ↔ "Tanaka"  (token overlap, token len > 3)
    """
    norm_name = _normalize_catalog_name(catalog_name)
    norm_text = _strip_accents(search_text)

    if norm_name in norm_text:
        return True

    # Token overlap : TOUS les tokens significatifs du nom doivent être dans le texte
    # (évite les faux positifs quand deux persos partagent un mot, ex. "démon")
    name_tokens = [t for t in norm_name.split() if len(t) > 3]
    if not name_tokens:
        return False
    text_tokens = set(re.split(r"\W+", norm_text))
    return all(token in text_tokens for token in name_tokens)


# ── Synchronisation storyboard ↔ casting / décors / accessoires ───────────────

_SYNC_STORYBOARD_SYSTEM = """\
Tu es un superviseur storyboard pour une production cinématographique.
Pour chaque plan dans le JSON fourni, vérifie si le champ "current_prompt" reflète \
fidèlement les descriptions actuelles des éléments assignés (personnages, décor, accessoires).

RÈGLES :
- Si le prompt est déjà cohérent avec toutes les descriptions actuelles → changed: false, prompt inchangé
- Si un élément a des traits/descriptions qui ne correspondent plus au prompt \
(traits physiques différents, style modifié, costume changé, nouveau nom de lieu…) → réécris le prompt
- CONSERVE : intention cinématographique, mouvement caméra, valeur de plan, action dramatique, atmosphère
- MODIFIE UNIQUEMENT : la description des personnages, du lieu, des costumes/accessoires pour \
coller aux données actuelles
- Garde le même registre et la même langue que le prompt original
- Sois précis dans "reason" (15 mots max, en français)

COHÉRENCE LUMIÈRE PAR SÉQUENCE :
- Si un plan contient le champ "seq_lighting_ref" (non-vide), sa lumière et son atmosphère \
doivent être cohérentes avec ce prompt de référence de séquence.
- Si le plan actuel ne mentionne pas de lumière mais que seq_lighting_ref en décrit une \
(ex. "lumière dorée, ciel orageux"), ajoute ces conditions lumineuses au prompt réécrit.
- Ne force jamais une lumière si seq_lighting_ref n'en mentionne pas.
- La lumière est une donnée de continuité : elle ne doit pas changer entre les plans \
d'une même séquence sauf si une intention dramatique explicite l'impose.

- Réponds UNIQUEMENT en JSON valide, sans markdown, sans texte hors JSON

FORMAT OBLIGATOIRE :
{"shots":[{"id":"...","prompt":"...","changed":true,"reason":"..."},...]}
"""


class SyncStoryboardWorker(QThread):
    """Synchronise les prompts Seedance avec les descriptions actuelles du casting.

    Phase 1 (sans IA) : ré-assignation par correspondance de noms dans scene_title/prompt.
    Phase 2 (Claude Haiku) : réécriture des prompts qui ne reflètent plus les descriptions.

    Chaque shot retourné dans finished() porte des champs meta (préfixe _) :
      _reassigned     : list[str]  — noms d'éléments nouvellement assignés
      _prompt_changed : bool       — True si le prompt a été réécrit
      _old_prompt     : str        — prompt original avant sync
      _reason         : str        — raison courte de la modification
    """
    progress = pyqtSignal(int, str)
    finished = pyqtSignal(list)
    failed   = pyqtSignal(str)

    def __init__(self, shots: list):
        super().__init__()
        self._shots = [dict(s) for s in shots]

    def run(self):
        try:
            self._run()
        except Exception as e:
            self.failed.emit(f"Erreur synchronisation : {e}")

    def _run(self):
        import core.casting as casting_api
        import core.decors as decors_api
        import core.accessories as acc_api
        import core.hmc as hmc_api
        import core.vehicles as veh_api

        self.progress.emit(5, "Chargement du casting et des éléments…")

        characters  = casting_api.list_characters()
        decors      = decors_api.list_decors()
        accessories = acc_api.list_accessories()

        char_by_id   = {c["id"]: c for c in characters}
        char_by_name = {c["name"].lower(): c for c in characters if c.get("name")}
        decor_by_id  = {d["id"]: d for d in decors}
        decor_by_name = {d["name"].lower(): d for d in decors if d.get("name")}
        acc_by_name  = {a["name"].lower(): a for a in accessories if a.get("name")}

        self.progress.emit(15, "Phase 1 — ré-assignation des éléments par nom…")

        # ── Phase 1 : name matching ────────────────────────────────────────────
        for shot in self._shots:
            shot["_reassigned"]     = []
            shot["_prompt_changed"] = False
            shot["_old_prompt"]     = shot.get("seedance_prompt", "")
            shot["_reason"]         = ""

            search_text = (
                (shot.get("scene_title") or "") + " " +
                (shot.get("seedance_prompt") or "")
            ).lower()

            existing_char_ids = set(shot.get("character_ids") or [])
            for char in characters:
                if not char.get("name"):
                    continue
                canonical = char["name"]
                if char["id"] in existing_char_ids:
                    # ID déjà présent — corriger le nom affiché si c'est un variant fuzzy
                    cur_names = shot.get("character_names") or []
                    if canonical not in cur_names:
                        for i, old in enumerate(cur_names):
                            if _same_name(old, canonical) and old != canonical:
                                cur_names[i] = canonical
                                shot["_reassigned"].append(
                                    f"personnage : {old} → {canonical}"
                                )
                                break
                    continue
                if _name_in_text(canonical, search_text):
                    existing_char_ids.add(char["id"])
                    shot.setdefault("character_ids", [])
                    shot.setdefault("character_names", [])
                    if char["id"] not in shot["character_ids"]:
                        shot["character_ids"].append(char["id"])
                        # Remplace l'ancien variant fuzzy si présent, sinon ajoute
                        old_names = shot["character_names"]
                        replaced = False
                        for i, old in enumerate(old_names):
                            if _same_name(old, canonical) and old != canonical:
                                old_names[i] = canonical
                                shot["_reassigned"].append(
                                    f"personnage : {old} → {canonical}"
                                )
                                replaced = True
                                break
                        if not replaced:
                            old_names.append(canonical)
                            shot["_reassigned"].append(f"personnage : {canonical}")

            if not shot.get("decor_id"):
                for decor in decors:
                    if not decor.get("name"):
                        continue
                    if _name_in_text(decor["name"], search_text):
                        shot["decor_id"]   = decor["id"]
                        shot["decor_name"] = decor["name"]
                        shot["_reassigned"].append(f"décor : {decor['name']}")
                        break

        self.progress.emit(30, "Phase 2 — préparation des données pour Claude Haiku…")

        # ── Phase 2 : build Claude payload ────────────────────────────────────

        def _cdesc(cid):
            c = char_by_id.get(cid, {})
            return {
                "name":        c.get("name", ""),
                "description": (c.get("description") or c.get("prompt") or "").strip(),
            }

        def _ddesc(did):
            d = decor_by_id.get(did, {})
            return {
                "name":        d.get("name", ""),
                "description": (d.get("prompt") or d.get("description") or "").strip(),
            }

        # ── Référence lumière par séquence ────────────────────────────────────────
        # Pour chaque seq_num, on retient le premier prompt non vide comme référence
        # lumineuse/atmosphérique — transmis à Claude pour assurer la continuité.
        seq_ref: dict[str, str] = {}
        for shot in self._shots:
            sn = str(shot.get("seq_num") or "").strip()
            if sn and sn not in seq_ref:
                p = (shot.get("seedance_prompt") or "").strip()
                if p:
                    seq_ref[sn] = p[:300]  # 300 chars suffisent pour la lumière

        shots_payload = []
        for shot in self._shots:
            chars = [_cdesc(cid) for cid in (shot.get("character_ids") or [])
                     if cid in char_by_id and char_by_id[cid].get("description") or char_by_id[cid].get("prompt")]
            decor_el = _ddesc(shot["decor_id"]) if shot.get("decor_id") and shot["decor_id"] in decor_by_id else None
            acc_els  = [
                {"name": n, "description": acc_by_name.get(n.lower(), {}).get("description", "")}
                for n in (shot.get("accessory_names") or [])
                if acc_by_name.get(n.lower(), {}).get("description")
            ]

            has_elements = bool(chars or decor_el or acc_els)
            prompt = (shot.get("seedance_prompt") or "").strip()
            if not has_elements or not prompt:
                continue

            sn = str(shot.get("seq_num") or "").strip()
            entry = {
                "id":            shot.get("id", ""),
                "scene_title":   shot.get("scene_title", ""),
                "current_prompt": prompt,
                "assigned_elements": {
                    "characters":  chars,
                    "decor":       decor_el,
                    "accessories": acc_els,
                },
            }
            if sn and sn in seq_ref:
                entry["seq_lighting_ref"] = seq_ref[sn]
            shots_payload.append(entry)

        if not shots_payload:
            self.progress.emit(100, "Aucun prompt à synchroniser (aucun élément assigné avec description)")
            self.finished.emit(self._shots)
            return

        from core.ai_provider import complete as ai_complete, key_error, ai_name
        err = key_error()
        if err:
            self.failed.emit(err)
            return

        payload_str = json.dumps({"shots": shots_payload}, ensure_ascii=False, indent=2)

        self.progress.emit(50, f"{ai_name()} analyse {len(shots_payload)} plan(s)…")

        raw = ai_complete(_SYNC_STORYBOARD_SYSTEM, payload_str,
                          tier="utility", max_tokens=8192).strip()
        # Nettoyer le markdown si Claude en ajoute malgré les instructions
        if "```" in raw:
            parts = raw.split("```")
            for part in parts:
                candidate = part.lstrip("json").strip()
                if candidate.startswith("{"):
                    raw = candidate
                    break

        try:
            result = json.loads(raw)
        except json.JSONDecodeError as e:
            raise ValueError(
                f"Réponse JSON invalide de Claude ({e}). "
                f"Essayez avec moins de plans simultanément."
            )

        self.progress.emit(85, "Application des résultats…")

        updated_map = {s["id"]: s for s in result.get("shots", [])}
        for shot in self._shots:
            upd = updated_map.get(shot.get("id", ""))
            if upd and upd.get("changed"):
                shot["_prompt_changed"] = True
                shot["_reason"]         = upd.get("reason", "")
                shot["seedance_prompt"] = upd.get("prompt", shot.get("seedance_prompt", ""))

        self.progress.emit(100, "Synchronisation terminée")
        self.finished.emit(self._shots)


# ── Session de chat interactif — co-écriture arrangement ──────────────────────

def _arrange_chat_system(intensity: int) -> str:
    """Génère le system prompt de co-écriture adapté à l'intensité (1-10)."""
    if intensity <= 2:
        rule = (
            f"━━━ INTENSITÉ MINIMALE ({intensity}/10) — MODIFICATION CHIRURGICALE STRICTE ━━━\n"
            "Modifie UNIQUEMENT ce que le réalisateur demande, mot pour mot.\n"
            "Si la demande cible une réplique, seule cette réplique change — rien avant, rien après.\n"
            "Tout le reste est copié CARACTÈRE PAR CARACTÈRE depuis la version précédente.\n"
            "Aucune amélioration, aucune correction, aucune retouche hors de la zone ciblée."
        )
    elif intensity <= 4:
        rule = (
            f"━━━ INTENSITÉ PRÉCISE ({intensity}/10) — CHIRURGIE CIBLÉE ━━━\n"
            "Tu ne modifies QUE ce que le réalisateur demande EXPLICITEMENT.\n"
            "Tout le reste du scénario est copié MOT POUR MOT — sans reformulation, sans retouche.\n"
            "Tu peux uniquement harmoniser la ponctuation dans la phrase ciblée pour la cohérence."
        )
    elif intensity <= 6:
        rule = (
            f"━━━ INTENSITÉ CIBLÉE ({intensity}/10) — MODIFICATION PRÉCISE ━━━\n"
            "Tu modifies les zones que le réalisateur demande. Tout le reste est conservé.\n"
            "Tu peux légèrement affiner le style dans la zone ciblée pour assurer la cohérence de ton.\n"
            "Ne retouche pas les passages non mentionnés, même si tu penses pouvoir les améliorer."
        )
    elif intensity <= 8:
        rule = (
            f"━━━ INTENSITÉ CRÉATIVE ({intensity}/10) — RÉÉCRITURE DES ZONES CIBLÉES ━━━\n"
            "Tu modifies les zones demandées avec liberté créative : reformule, enrichis, améliore le rythme.\n"
            "Tu peux retoucher les passages adjacents pour assurer la fluidité narrative.\n"
            "Les zones non mentionnées sont conservées, avec d'éventuelles harmonisations stylistiques légères."
        )
    else:
        rule = (
            f"━━━ INTENSITÉ LIBRE ({intensity}/10) — CO-ÉCRITURE COMPLÈTE ━━━\n"
            "Tu réécris dans l'esprit des instructions du réalisateur, avec pleine liberté créative.\n"
            "Tu peux transformer le style, le rythme, les dialogues et la structure dans l'ensemble du scénario.\n"
            "Respecte scrupuleusement ce que le réalisateur demande de conserver explicitement."
        )
    return (
        "Tu es un co-auteur travaillant dans Pandora, un outil de pré-production IA. "
        "Tu dialogues avec le réalisateur pour affiner le scénario.\n\n"
        f"{rule}\n\n"
        "RÉFÉRENCES VISUELLES : Si des images sont jointes, intègre leurs détails visuels "
        "UNIQUEMENT dans les parties que le réalisateur demande de modifier.\n\n"
        "FORMAT DE RÉPONSE OBLIGATOIRE :\n"
        "Ta réponse doit contenir EXACTEMENT deux parties séparées par ces marqueurs :\n\n"
        "══════════ MESSAGE ══════════\n"
        "[Message conversationnel : indique précisément CE QUE TU AS CHANGÉ et où — "
        "2 à 4 lignes max, ton direct et collaboratif. Si la portée est ambiguë, pose une question.]\n"
        "══════════ SCÉNARIO ══════════\n"
        "[Le scénario complet. Mise en page Pandora : séquences (—— SÉQUENCE N — TITRE ——), "
        "en-têtes INT./EXT., noms de personnages en MAJUSCULES avant les répliques.]\n\n"
        "RÈGLES :\n"
        "- « Ne touche pas X » ou « garde X intact » → X est copié mot pour mot, sans exception\n"
        "- « Développe Y » → ajoute du contenu cohérent UNIQUEMENT dans Y\n"
        "- « Coupe Z » → supprime Z proprement, le reste est intact\n"
        "- Les noms de personnages restent IDENTIQUES dans tout le document\n"
        "- N'invente rien qui ne soit pas dans l'original ou explicitement demandé"
    )


class ArrangeChatWorker(QThread):
    """Co-écriture interactive du scénario avec Claude.

    Signals :
        message_ready(str)   — réponse conversationnelle de Claude (à afficher dans le chat)
        screenplay_ready(str) — scénario remanié complet (à afficher dans la prévisualisation)
        failed(str)           — message d'erreur
    """
    message_ready    = pyqtSignal(str)
    screenplay_ready = pyqtSignal(str)
    failed           = pyqtSignal(str)

    _MARKER_MSG  = "══════════ MESSAGE ══════════"
    _MARKER_SCR  = "══════════ SCÉNARIO ══════════"

    def __init__(
        self,
        original: str,
        analysis: str,
        history: list[dict],
        user_message: str,
        intensity: int = 5,
        ref_images: list | None = None,
    ):
        super().__init__()
        self._original     = original
        self._analysis     = analysis
        self._history      = history        # [{"role": "user"/"assistant", "content": str}]
        self._user_message = user_message
        self._intensity    = intensity
        self._ref_images   = ref_images or []

    def run(self):
        try:
            from core.ai_provider import chat as ai_chat, key_error
            err = key_error()
            if err:
                self.failed.emit(err)
                return

            lang = _get_lang()

            if lang == "en":
                context_block = (
                    f"{_lang_hint(lang)}"
                    f"ORIGINAL SCREENPLAY:\n{self._original}\n\n"
                    f"INITIAL ANALYSIS (intensity {self._intensity}/10):\n{self._analysis}"
                )
            else:
                context_block = (
                    f"SCÉNARIO ORIGINAL :\n{self._original}\n\n"
                    f"ANALYSE INITIALE (intensité {self._intensity}/10) :\n{self._analysis}"
                )

            # Construction des messages : on insère le contexte dans le premier message user
            messages = []
            for i, msg in enumerate(self._history):
                if i == 0 and msg["role"] == "user":
                    messages.append({
                        "role": "user",
                        "content": context_block + "\n\n" + msg["content"],
                    })
                else:
                    messages.append(msg)

            # Message courant — multimodal si images jointes
            if self._ref_images:
                import base64, os as _os
                _MT = {"jpg":"image/jpeg","jpeg":"image/jpeg","png":"image/png",
                       "webp":"image/webp","gif":"image/gif"}
                cur_content: list = []
                for path in self._ref_images[:4]:
                    try:
                        with open(path, "rb") as fh:
                            data = base64.b64encode(fh.read()).decode()
                        ext = _os.path.splitext(path)[1].lower().lstrip(".")
                        mt  = _MT.get(ext, "image/jpeg")
                        cur_content.append({"type": "image",
                                            "source": {"type": "base64",
                                                       "media_type": mt,
                                                       "data": data}})
                    except Exception:
                        pass
                text_prefix = context_block + "\n\n" if not messages else ""
                cur_content.append({"type": "text",
                                    "text": text_prefix + self._user_message})
                messages.append({"role": "user", "content": cur_content})
            else:
                if not messages:
                    messages.append({
                        "role": "user",
                        "content": context_block + "\n\n" + self._user_message,
                    })
                else:
                    messages.append({"role": "user", "content": self._user_message})

            if self._ref_images:
                # VISION (images jointes) : direct Anthropic — hors couche ai_provider
                # (les autres fournisseurs gèrent la vision différemment ; périmètre v1 = texte).
                import anthropic
                from core.config import load_config as _lc
                client = anthropic.Anthropic(api_key=_lc().get("anthropic_key", "").strip())
                response = client.messages.create(
                    model=_MODEL,
                    max_tokens=8192,
                    system=_arrange_chat_system(self._intensity),
                    messages=messages,
                )
                raw = response.content[0].text.strip()
            else:
                raw = ai_chat(_arrange_chat_system(self._intensity), messages,
                              tier="creative", max_tokens=8192).strip()

            # Split sur les marqueurs
            chat_msg   = ""
            screenplay = ""
            if self._MARKER_SCR in raw:
                parts      = raw.split(self._MARKER_SCR, 1)
                screenplay = parts[1].strip()
                # Extraire le message du premier bloc
                first      = parts[0]
                if self._MARKER_MSG in first:
                    chat_msg = first.split(self._MARKER_MSG, 1)[1].strip()
                else:
                    chat_msg = first.strip()
            elif self._MARKER_MSG in raw:
                chat_msg = raw.split(self._MARKER_MSG, 1)[1].strip()
            else:
                # Réponse sans format — tout considéré comme message
                chat_msg = raw

            if chat_msg:
                self.message_ready.emit(chat_msg)
            if screenplay:
                self.screenplay_ready.emit(screenplay)

        except Exception as e:
            self.failed.emit(_fmt_err(e))
