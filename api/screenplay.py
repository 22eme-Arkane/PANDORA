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

_MODEL            = "claude-sonnet-5"     # Sonnet 5 — format/arrange/apply + analyses vision
_MODEL_STORYBOARD = "claude-sonnet-5"     # Sonnet 5 (storyboard JSON ; routage réel via ai_provider task)
# Sonnet 5 active la réflexion adaptative si `thinking` est omis → on la désactive sur
# les appels DIRECTS (vision) pour ne pas rogner la sortie (max_tokens serrés).
_NO_THINK = {"type": "disabled"}


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
Tu es un script editor pour Pandora.

Ta seule mission est de remettre en forme le SCÉNARIO fourni comme un scénario
narratif propre. Tu ne réalises jamais le découpage technique à cette étape.

SÉPARATION ABSOLUE DES DOCUMENTS :
- SCÉNARIO : récit, actions jouables, lieux, personnages et dialogues uniquement.
- NOTE DE RÉALISATION : style d'image, références, temporalité, lumière, son,
  rythme de montage et intentions de caméra.
- DÉCOUPAGE : plans, durées, prompts visuels et propositions caméra.
- STORYBOARD : réglages techniques validés et images.

RÈGLES :
- Conserver intégralement le sens, les actions et les dialogues du texte source.
- Organiser le texte en séquences avec des en-têtes INT./EXT., lieu et moment.
- Écrire les actions au présent, sans enrichissement visuel inventé.
- Garder la graphie des noms strictement cohérente.
- Ne produire aucun numéro de plan, aucune durée, aucune focale, aucune valeur de
  plan, aucun axe, aucun mouvement caméra et aucun prompt de génération.
- Ne produire aucune fiche personnage ou fiche décor dans le scénario.
- Si le texte contient des consignes de réalisation, ne pas les intégrer au récit :
  les regrouper à la fin sous « À TRANSFÉRER DANS LA NOTE DE RÉALISATION ».
- Ne jamais employer « PROMPT SEEDANCE », « PROMPT », « P01 » ou une structure
  compacte de plan dans ce document.
- Retourner uniquement le scénario remis en forme, sans commentaire extérieur.
"""

_ARRANGE_SCREENPLAY_TMPL = """\
Tu es un consultant dramaturgique et co-scénariste pour Pandora.

SÉPARATION ABSOLUE DES DOCUMENTS :
- Le SCÉNARIO contient le récit, les actions, les lieux et les dialogues.
- La NOTE DE RÉALISATION contient style d'image, temporalité, lumière, durée des
  plans, rythme de montage, valeurs, axes et mouvements caméra.
- Le DÉCOUPAGE PANDORA transformera plus tard le scénario en plans.
N'encourage jamais l'ajout d'une intention technique ou visuelle de fabrication dans
le scénario. Classe-la dans la section 6 destinée à la Note de réalisation.

Analyse le scénario fourni. Commence par un court paragraphe « EN BREF » (3 à 5
lignes, sans numéro) qui résume ton diagnostic global en langage simple — c'est la
première chose que le réalisateur lit. Puis structure ta réponse en 7 sections,
numérotées EXACTEMENT « ### 1 » à « ### 7 » dans cet ordre (la section 6 est
extraite automatiquement vers la Note de réalisation et la section 7 alimente le
casting : ne les renumérote jamais, ne les fusionne jamais). Sois COMPLET dans
chaque section — aucune limite de longueur :

### 1. Structure narrative
Rythme dramatique, cohérence des séquences, progression et équilibre action/dialogue.

### 2. Lisibilité des actions
Évalue si l'action dramatique est compréhensible et jouable. Ne demande pas de
textures, focales, lumières ou descriptions physiques destinées au moteur vidéo.

### 3. Points forts
Ce qui fonctionne bien narrativement, dans les personnages, les situations et les dialogues.

### 4. Proposition d'arrangement
Si la structure narrative peut être améliorée : \
propose un ordre alternatif des séquences avec justification dramatique. \
Indique les séquences à couper, fusionner, diviser ou déplacer. \
Si la structure est déjà optimale, dis-le explicitement.

### 5. Suggestions concrètes pour le scénario
5 à 7 pistes actionnables, priorisées par impact narratif. \
Pour chaque suggestion : (a) ce qu'il faut changer, \
(b) pourquoi cela améliore le récit, \
(c) exemple de reformulation si pertinent.

### 6. Intentions à placer dans la Note de réalisation
Liste séparée de toutes les informations de style, rythme de montage, temporalité,
durée des plans, caméra, lumière, son et continuité évoquées ou suggérées.
N'en insère aucune dans les suggestions de réécriture du scénario.

### 7. Inventaire complet des personnages
Liste TOUS les personnages sans exception : principaux, secondaires, figurants. \
Ne jamais regrouper sous une formule générique. \
Format par ligne : Nom/Fonction | Rôle (Principal / Secondaire / Figurant) | Scènes d'apparition

Respond in {LANG_INSTRUCTION}, in a structured, direct and constructive way.\
"""

_APPLY_ARRANGE = """\
Tu es un scénariste expert pour Pandora.

Tu appliques des suggestions d'arrangement pour rendre le scénario plus fort
narrativement. Le découpage et la préparation vidéo sont des documents séparés.

Tu reçois :
1. LE SCÉNARIO ORIGINAL — la matière de base à préserver et améliorer
2. L'ANALYSE ET LES SUGGESTIONS — le résultat de l'analyse créative et technique

RÈGLES D'APPLICATION :
- Préserve TOUT le contenu narratif essentiel : actions, dialogues, lieux, personnages
- Applique les suggestions pertinentes selon l'intensité indiquée
- Maintiens la structure Pandora : séquences (—— SÉQUENCE N — TITRE ——), \
en-têtes INT./EXT., noms de personnages en MAJUSCULES centrés
- Noms de personnages : graphie STRICTEMENT IDENTIQUE tout au long du document
- Les actions peuvent être rendues concrètes et jouables, sans les transformer en plans
- N'ajoute jamais style d'image, focale, valeur/axe/mouvement caméra, lumière de
  fabrication, durée de plan ou rythme de montage au texte du scénario
- Ignore, lors de la réécriture, les suggestions explicitement destinées à la
  Note de réalisation
- Ne résume pas, ne condense pas arbitrairement les dialogues importants

Retourne UNIQUEMENT le scénario réécrit, sans commentaires ni explications.\
"""

_GENERATE_STORYBOARD_TMPL = """\
Tu es un assistant de découpage cinématographique. Ton rôle est de découper fidèlement le scénario en plans — tu ne réinventes rien, tu n'interprètes rien, tu retranscris.

RÈGLES ABSOLUES :
- Tout le contenu descriptif ("comments" et les champs de sections "action"/"staging"/"ambiance"/"decor"/"lighting"/"sound_prompt") doit être extrait directement du scénario.
- Les dialogues présents dans le scénario DOIVENT apparaître mot pour mot dans "comments" ET dans le champ "action".
- Aucune invention narrative, aucune paraphrase libre, aucune interprétation créative : mêmes personnages, mêmes lieux, mêmes actions, mêmes mots.
- N'inclus dans un plan (et dans "character_names" / "staging") QUE les personnages réellement présents et visibles dans CE plan — JAMAIS un personnage hors champ, hors cadre, ou déjà sorti de la scène.
- DÉCOUPAGE FIDÈLE : crée UN plan par BEAT D'ACTION distinct (un changement d'action, de cadre, d'intention ou de réplique de dialogue = un nouveau plan). Respecte le nombre de moments distincts que contient le scénario — ne réduis JAMAIS arbitrairement le nombre de plans.
- FUSION INTERDITE EN SILENCE : ne regroupe JAMAIS plusieurs beats distincts dans un seul plan sans le signaler. Si — et seulement si — deux beats forment une action strictement continue dans le même cadre et qu'un seul plan est réellement justifié, tu DOIS marquer ce plan avec "merged": true et "merged_note" décrivant brièvement ce qui a été fusionné. Par défaut "merged": false.
{MERGE_POLICY}
Retourne UNIQUEMENT un tableau JSON valide. Chaque élément du tableau représente un plan et contient exactement ces clés :
{
  "number": <int — numéro séquentiel du plan>,
  "seq_num": <int — numéro de la séquence contenant ce plan, extrait des titres "—— SÉQUENCE N — TITRE ——" du scénario. Ex : 1 pour SÉQUENCE 1, 3 pour SÉQUENCE 3. Si le scénario ne contient pas de marqueurs de séquence, utiliser 1 pour tous les plans.>,
  "seq_name": <str — titre de la séquence contenant ce plan, extrait du marqueur "—— SÉQUENCE N — TITRE ——". Ex : "LA FORTERESSE", "RETOUR AU VILLAGE". Chaîne vide si pas de marqueur de séquence.>,
  "scene_title": <str — titre court de la scène, extrait du scénario>,
  "decor_name": <str — nom exact du décor / lieu tel qu'il apparaît dans le scénario>,
  "shot_time": <str — exactement une valeur parmi : "Jour", "Nuit", "Lever du soleil", "Coucher du soleil">,
  "duration": <float — durée estimée en secondes, STRICTEMENT entre 2.0 et 15.0>,
  "character_names": <list[str] — noms exacts des personnages réellement présents ET visibles dans ce plan, tels qu'ils apparaissent dans le scénario. EXCLURE tout personnage hors champ / hors cadre / déjà sorti.>,
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
  "action": <str — {PROMPT_LANG}. L'ACTION concrète et visible du plan, fidèle au scénario : qui fait quoi, ce qu'on voit bouger. Si dialogue présent, citer la réplique EXACTE entre guillemets avec le nom du personnage. 1 à 3 phrases. Personnages cités par leur NOM (la cohérence visuelle est gérée par les images de référence).>,
  "staging": <str — {PROMPT_LANG}. MISE EN SCÈNE : indique d'abord le nombre de personnages PRÉSENTS et visibles dans ce plan (JAMAIS un personnage hors champ), puis leur position approximative déduite du scénario (gauche/droite/centre, premier/arrière-plan) et qui fait face à qui. Si le scénario ne précise pas le placement, décris AU MINIMUM : qui est au premier plan / à l'arrière-plan, qui fait face à qui, et l'ancrage à UN élément du décor mentionné dans la scène (table, porte, fenêtre…). N'invente pas de géométrie chiffrée (pas de distances ni d'angles inventés). Personnages par leur NOM.>,
  "ambiance": <str — {PROMPT_LANG}. AMBIANCE : atmosphère, mood et émotion du plan tels que décrits ou impliqués par le scénario. N'AJOUTE PAS de mots de qualité génériques (PAS de « cinématographique », « ultra-détaillé », « photoréaliste », « 4K », etc.) — le style visuel est géré séparément.>,
  "decor": <str — {PROMPT_LANG}. DÉCOR : UNIQUEMENT le lieu et son environnement FIXE (architecture, matières, époque, mobilier fixe, murs/sol, végétation, palette). N'inclus NI personnage, NI véhicule, NI accessoire mobile, NI intention d'éclairage — chacun a sa propre section. Le décor seul.>,
  "lighting": <str — {PROMPT_LANG}. PLAN DE FEU : INTENTION d'éclairage cohérente avec le scénario — direction de la lumière, qualité (douce/dure), température de couleur, contraste, sources pratiques motivées (lustre, fenêtre, bougie…). NE mentionne AUCUN projecteur ni appareil d'éclairage visible : c'est une intention de lumière, pas du matériel à l'image.>,
  "sound_prompt": <str — SOUND DESIGN / SFX prompt in {PROMPT_LANG} describing the shot's sound ambience: ambient textures, sound effects, room tone, materials and rhythm of the scene, ready for a sound-effects generator. NO speech, NO voice, NO music score, NO BPM (dialogue lives in the "action" field; this is ambience/SFX only). You MAY place the main sound events approximately in time within the shot (e.g. "around 1s", "mid-shot"). 1 to 3 concise sentences faithful to what the screenplay describes.>,
  "merged": <bool — true UNIQUEMENT si ce plan regroupe plusieurs beats d'action distincts du scénario (voir RÈGLES ABSOLUES). false par défaut>,
  "merged_note": <str — si merged=true, description COURTE des beats fusionnés et de la raison ; sinon chaîne vide "">,
  "source_excerpt": <str — extrait EXACT du scénario couvert par ce plan (citation fidèle, dialogues inclus mot pour mot) ; si la source est un Découpage PANDORA, recopie sa SOURCE SCÉNARIO telle quelle>,
  "rhythm": <str — tempo du plan, point de coupe et relation aux plans voisins ; si la source est un Découpage PANDORA, recopie son champ RYTHME ; sinon déduis-le sobrement du scénario>,
  "intention": <str — fonction dramatique et visuelle du plan en une ou deux phrases ; si la source est un Découpage PANDORA, recopie son champ INTENTION>
}

Contrainte absolue : duration ne peut jamais dépasser 15.0 secondes (limite de Seedance 2.0).
Retourne UNIQUEMENT le tableau JSON, sans aucun texte avant ou après.\
"""


_FORMAT_PANDORA = """\
Tu es le monteur et réalisateur associé de PANDORA. Tu prépares le passage du scénario
au storyboard, sans réécrire le scénario et sans produire une fausse page de scénario.

AUTORITÉ DES SOURCES :
- Le SCÉNARIO est la seule vérité narrative. Garde les actions, dialogues, lieux et noms.
- La NOTE DE RÉALISATION porte le style, la temporalité, le rythme, les durées, la
  lumière, la palette et la grammaire caméra. Applique-la aux fiches sans la recopier
  dans l'extrait narratif.
- Ne mélange jamais narration, intention, prompt visuel et réglages caméra.

OBJECTIF : créer des FICHES DE PLANS éditoriales. Chaque fiche doit permettre au
réalisateur de comprendre le rôle du plan, d'écrire ou corriger son prompt, de créer un
mood, puis de transmettre des données séparées au Storyboard.

FORMAT OBLIGATOIRE — respecte exactement les libellés et l'ordre :

DÉCOUPAGE PANDORA 2

SÉQUENCE 1 — TITRE COURT

PLAN 01
SOURCE SCÉNARIO : Extrait exact et autonome du scénario couvert par ce plan, dialogues
inclus mot pour mot. Aucune technique, aucun enrichissement visuel.
INTENTION : Fonction dramatique et visuelle du plan en une ou deux phrases.
RYTHME : Tempo, point de coupe et relation au plan précédent/suivant.
DURÉE : 6s
PROMPT VISUEL : Prompt moteur-agnostique très détaillé en français. Décris uniquement
ce que l'image doit montrer : action fidèle, espace, lumière, palette, matières,
atmosphère. N'invente aucun événement. Les personnages sont cités par leur nom.
PERSONNAGES : Noms exacts séparés par des virgules, ou —
DÉCOR : Nom exact du décor, ou —
ACCESSOIRES : Noms séparés par des virgules, ou —
VÉHICULES : Noms séparés par des virgules, ou —
HMC : Éléments visibles séparés par des virgules, ou —
VALEUR PROPOSÉE : Une valeur de plan PANDORA, ou —
AXE PROPOSÉ : Un axe PANDORA, ou —
MOUVEMENT PROPOSÉ : Un mouvement PANDORA, ou —
FOCALE PROPOSÉE : Une focale indicative, ou —
MOOD : À CRÉER

PLAN 02
Répète ici tous les champs de PLAN 01 avec le contenu réel du deuxième plan.

RÈGLES DE DÉCOUPAGE :
- Un plan par beat d'action, changement de point de vue, geste décisif ou réplique qui
  exige une réaction distincte. Si tu dois fusionner deux beats, DIS-LE explicitement
  dans l'INTENTION du plan concerné — jamais de fusion silencieuse.
- Numérotation PLAN 01, PLAN 02… continue ; titres de séquence séparés.
- Durée entre 2 et 15 secondes. La durée sert au rythme, pas à imposer un moteur.
- SOURCE SCÉNARIO est une citation/extraction fidèle, pas une réécriture enrichie.
- INTENTION explique pourquoi le plan existe ; PROMPT VISUEL décrit l'image à produire.
- Le PROMPT VISUEL peut inclure les indications de caméra (valeur, mouvement, focale,
  angle) quand elles servent l'image. Renseigne AUSSI les champs proposés dédiés :
  le Storyboard les reprend et l'utilisateur pourra les modifier là-bas.
- Les descriptions physiques précises viendront des identités visuelles de Casting,
  Décors, Accessoires, Véhicules et HMC. Ici, liste les noms exacts uniquement.
- Chaque PLAN doit contenir la totalité des champs. N'écris jamais « même structure »,
  des points de suspension ou un champ implicite.
- Retourne uniquement le document, sans markdown, sans commentaire et sans ancien
  format compact « P01 | … ».\
"""


_FORMAT_PANDORA_EN = """\
You are PANDORA's picture editor and associate director. Prepare the transition from
screenplay to storyboard without rewriting the screenplay or imitating screenplay pages.

SOURCE AUTHORITY:
- The SCREENPLAY is the only narrative truth. Preserve actions, dialogue, locations and names.
- The DIRECTOR'S NOTE owns style, time treatment, pace, shot duration, lighting, palette
  and camera grammar. Apply it without copying it into the narrative excerpt.
- Never mix narrative source, intent, visual prompt and camera settings.

GOAL: create editorial SHOT SHEETS. Each sheet must let the director understand why the
shot exists, edit its prompt, create a mood, then send separate data to the Storyboard.

MANDATORY FORMAT — keep these labels and this order exactly:

DÉCOUPAGE PANDORA 2

SEQUENCE 1 — SHORT TITLE

PLAN 01
SCREENPLAY SOURCE: Exact self-contained screenplay excerpt covered by this shot,
including verbatim dialogue. No technique and no visual embellishment.
INTENT: Dramatic and visual purpose of the shot in one or two sentences.
RHYTHM: Pace, cut point and relationship to the adjacent shots.
DURATION: 6s
VISUAL PROMPT: Highly detailed, engine-agnostic English prompt. Describe only what the
image should show: faithful action, space, light, palette, materials and atmosphere.
Invent no event. Refer to characters by their exact names.
CHARACTERS: Exact names separated by commas, or —
SET: Exact set name, or —
PROPS: Names separated by commas, or —
VEHICLES: Names separated by commas, or —
HMC: Visible elements separated by commas, or —
SUGGESTED SHOT SIZE: A PANDORA shot size, or —
SUGGESTED AXIS: A PANDORA axis, or —
SUGGESTED MOVEMENT: A PANDORA movement, or —
SUGGESTED FOCAL LENGTH: An indicative focal length, or —
MOOD: TO CREATE

PLAN 02
Repeat every PLAN 01 field here with the real content of the second shot.

BREAKDOWN RULES:
- One shot per action beat, point-of-view change, decisive gesture, or line requiring a
  separate reaction. If two beats must be merged, SAY SO explicitly in the shot's
  INTENT — never merge silently.
- Continuous PLAN 01, PLAN 02… numbering; separate sequence headings.
- Duration from 2 to 15 seconds. Duration expresses pace, not a provider constraint.
- SCREENPLAY SOURCE is a faithful extraction, not an embellished rewrite.
- INTENT says why the shot exists; VISUAL PROMPT says what image should be produced.
- VISUAL PROMPT may include camera indications (shot size, movement, focal length,
  angle) whenever they serve the image. ALSO fill the dedicated suggested fields:
  the Storyboard reuses them and the user can still edit them there.
- Exact physical descriptions will come from the visual identities in Casting, Sets,
  Props, Vehicles and HMC. Only list exact entity names here.
- Every PLAN must contain every field. Never output “same structure”, ellipses or an
  implicit field.
- Return only the document, with no markdown, no commentary and no legacy compact
  ``P01 | …`` format.\
"""


def _format_pandora_prompt(lang: str) -> str:
    """Sélectionne le contrat FR/EN du Découpage PANDORA 2."""
    return _FORMAT_PANDORA_EN if lang == "en" else _FORMAT_PANDORA


def _arrange_screenplay_prompt(lang: str) -> str:
    lang_instruction = "English" if lang == "en" else "French (français)"
    return _ARRANGE_SCREENPLAY_TMPL.replace("{LANG_INSTRUCTION}", lang_instruction)


def _storyboard_prompt(lang: str, strict_no_merge: bool = False) -> str:
    prompt_lang = "English" if lang == "en" else "French (français)"
    if strict_no_merge:
        merge_policy = (
            "- MODE STRICT ACTIVÉ (demande de l'utilisateur) : INTERDICTION TOTALE DE "
            "FUSIONNER des plans. Chaque beat d'action distinct DOIT devenir un plan "
            "séparé, même si l'action est continue. Ne produis AUCUN plan avec "
            'merged=true — sépare tout ce qui peut l\'être.'
        )
    else:
        merge_policy = ""
    return (_GENERATE_STORYBOARD_TMPL
            .replace("{PROMPT_LANG}", prompt_lang)
            .replace("{MERGE_POLICY}", merge_policy))


# Section TECHNIQUE déterministe (champs caméra) — centralisée dans prompt_sections
# pour être partagée par le découpage ET le dialogue de plan (mise à jour instantanée).
from core.prompt_sections import technique_line as _technique_line  # noqa: E402


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
  "description": <str — description PUREMENT PHYSIQUE : apparence, morphologie, âge apparent, traits du visage, cheveux, tenue. 1-2 phrases MAX. INTERDIT ABSOLU dans ce champ : psychologie, caractère, relations (père, sœur, ami…), motivations, événements du scénario — RIEN de narratif. Ce champ sert de brief pour un casting visuel : uniquement ce qui se VOIT.>,
  "personality": <str — traits de caractère, attitude et relations importantes du personnage, 1 phrase. Ce champ n'est JAMAIS utilisé pour la génération d'image — il sert au jeu d'acteur et au doublage.>,
  "prompt": <str — description visuelle ENRICHIE en français pour la génération d'image IA par Nano Banana. Inclure OBLIGATOIREMENT : morphologie et silhouette, âge apparent, carnation et traits du visage (forme du visage, mâchoire, yeux, nez, lèvres), couleur et coupe de cheveux, tenue vestimentaire complète avec couleurs et matières, posture corporelle. LUMIÈRE : neutre de studio de casting — AUCUN décor, AUCUN arrière-plan, AUCUNE source lumineuse du film (le style visuel et l'éclairage du film sont ajoutés séparément en aval). INTERDIT ABSOLU : psychologie, relations, motivations, backstory, événements du scénario (« influencé par », « cherche à venger »…), émotions narratives — UNIQUEMENT ce qu'un photographe de casting peut VOIR. 4-6 phrases détaillées, UNIQUEMENT des descripteurs VISUELS concrets. Exemple de qualité : "Homme de 35 ans, silhouette athlétique et nerveuse, 1m80, peau mate légèrement hâlée. Visage anguleux, mâchoire carrée marquée de barbe de 3 jours grise, sourcils épais. Cheveux châtains courts, légèrement en désordre. Porte une veste de combat kaki délavée et tachée de boue, pantalon cargo beige aux genoux écorchés, casque M1 cabossé posé de travers. Posture droite mais fatiguée, épaules légèrement affaissées.">,
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
  "prompt": <str — description visuelle ENRICHIE en français du LIEU SEUL pour la génération d'image IA. Inclure : style architectural ou naturel précis (matériaux, époque, état dégradé/neuf), palette de couleurs dominante, ambiance atmosphérique du lieu (météo, saison, humidité, fumée), mobilier FIXE et végétation, profondeur de champ suggérée. INTERDIT : AUCUNE intention d'éclairage (pas de projecteur, pas de direction ni d'intensité de lumière), AUCUN personnage ni figure humaine, AUCUN véhicule, aucun accessoire mobile — décor VIDE uniquement. 4-6 phrases, descripteurs CONCRETS et VISUELS du lieu.>,
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
    """Formate une erreur du fournisseur IA réellement sélectionné."""
    from core.ai_provider import ai_name_for_task, humanize_ai_error
    msg = str(e)
    low = msg.lower()
    if "connection" in low or "connect" in low or "network" in low or "ssl" in low:
        return (
            f"Erreur de connexion à {ai_name_for_task('screenplay')}.\n"
            "Vérifiez votre connexion internet.\n"
            "Si vous utilisez un VPN ou proxy, désactivez-le et réessayez.\n\n"
            f"Détail : {msg}"
        )
    if "401" in msg or "authentication" in low or "api_key" in low:
        return humanize_ai_error(msg)
    if "429" in msg or "rate" in low:
        return humanize_ai_error(msg)
    return f"Erreur {ai_name_for_task('screenplay')} : {msg}"


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
        err = key_error("screenplay")
        if err:
            self.failed.emit(err)
            return
        try:
            lang = _get_lang()
            full_text = ai_stream(_FORMAT_SCREENPLAY, _lang_hint(lang) + self._text,
                                  on_chunk=self.chunk.emit,
                                  tier="creative", max_tokens=8192, task="screenplay")
            self.finished.emit(full_text.strip())
        except Exception as e:
            self.failed.emit(_fmt_err(e))


class FormatPandoraWorker(QThread):
    chunk    = pyqtSignal(str)
    finished = pyqtSignal(str)
    failed   = pyqtSignal(str)

    def __init__(self, text: str, direction_note: str = ""):
        super().__init__()
        self._text = text
        self._direction_note = direction_note or ""

    # Un long métrage ne tient PAS dans une seule réponse : à 16000 tokens, le
    # modèle s'arrêtait net au milieu du document (28 plans pour la moitié d'un
    # scénario, constat Matthieu 2026-07-25) et PANDORA enregistrait ce demi-
    # découpage sans rien dire — chaque plan produit était valide, donc le contrat
    # passait. Six continuations = jusqu'à 112 000 tokens de sortie.
    _DECOUPAGE_MAX_ROUNDS = 6

    def _decoupage_call(self, system: str, user_content: str) -> str:
        """Un découpage COMPLET, ou une erreur explicite — jamais un demi-document.

        Passe par la boucle anti-troncature (core.ai_provider) : dès que la réponse
        est coupée par la limite de longueur, la suite est demandée et recollée."""
        from core.ai_provider import chat_until_complete_ex
        res = chat_until_complete_ex(
            system, [{"role": "user", "content": user_content}],
            tier="creative", max_tokens=16000, task="decoupage",
            max_rounds=self._DECOUPAGE_MAX_ROUNDS)
        if res.get("truncated"):
            raise ValueError(
                "Le découpage est INCOMPLET : le moteur IA a atteint sa limite de "
                f"longueur même après {self._DECOUPAGE_MAX_ROUNDS} reprises "
                "automatiques. Rien n'a été enregistré — un découpage partiel serait "
                "pire qu'aucun. Découpez le scénario en parties et relancez, ou "
                "choisissez un moteur à plus grande sortie dans Paramètres › "
                "Moteur IA par tâche › Découpage.")
        return (res.get("text") or "").strip()

    def run(self):
        from core.ai_provider import key_error
        from core.decoupage_document import is_v2_document, validate_v2_document
        err = key_error("screenplay")
        if err:
            self.failed.emit(err)
            return
        try:
            lang = _get_lang()
            from core.direction_note import note_for_ai
            note = note_for_ai(self._direction_note)
            screenplay_label = "SCREENPLAY" if lang == "en" else "SCÉNARIO"
            note_label = "DIRECTOR'S NOTE" if lang == "en" else "NOTE DE RÉALISATION"
            user_content = f"[{screenplay_label} — SOURCE NARRATIVE]\n{self._text}"
            if note:
                user_content += f"\n\n[{note_label} — INTENTIONS DE FABRICATION]\n{note}"
            system = _format_pandora_prompt(lang)

            # Ne jamais afficher le flux brut : certains modèles peuvent commencer par
            # reproduire l'ancien contrat avant de se corriger. La fenêtre ne reçoit que
            # le document final une fois le contrat éditorial v2 validé.
            # task="decoupage" : depuis que le storyboard est une conversion
            # déterministe des fiches, le Découpage est l'étape créative pivot
            # → routée sur le modèle de tête (Opus 4.8) du profil (2026-07-23).
            full_text = self._decoupage_call(system, _lang_hint(lang) + user_content)

            issues = validate_v2_document(full_text) if is_v2_document(full_text) else [
                "structure_v2_non_reconnue"
            ]
            if issues:
                correction = (
                    "\n\nCORRECTION OBLIGATOIRE : ta réponse précédente a utilisé une "
                    "structure obsolète ou incomplète. Recommence entièrement. La première "
                    "ligne doit être exactement « DÉCOUPAGE PANDORA 2 » et chaque PLAN doit "
                    "contenir tous les champs obligatoires. Le format compact P01 | … et les "
                    "lignes → PROMPT: sont interdits. Ne commente pas la correction."
                )
                full_text = self._decoupage_call(system + correction,
                                                 _lang_hint(lang) + user_content)
                issues = (validate_v2_document(full_text)
                          if is_v2_document(full_text)
                          else ["structure_v2_non_reconnue"])

            if issues:
                raise ValueError(
                    "Le moteur IA n'a pas respecté le contrat Découpage PANDORA 2 "
                    f"({', '.join(issues[:8])}). Aucun ancien découpage n'a été enregistré."
                )
            self.finished.emit(full_text)
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
        err = key_error("screenplay")
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
            # 16000 tokens (au lieu de 4096, 2026-07-23) : l'analyse porte 7
            # sections dont l'inventaire COMPLET des personnages — l'ancien
            # plafond tronquait les sections 6/7 sur les longs scénarios.
            full_text = ai_stream(_arrange_screenplay_prompt(lang), user_content,
                                  on_chunk=self.chunk.emit,
                                  tier="creative", max_tokens=16000, task="screenplay")
            self.finished.emit(full_text)
        except Exception as e:
            self.failed.emit(_fmt_err(e))


class ApplyArrangeWorker(QThread):
    """Applique les suggestions d'arrangement au scénario original via Claude."""
    chunk    = pyqtSignal(str)
    finished = pyqtSignal(str)
    failed   = pyqtSignal(str)

    def __init__(self, original_text: str, suggestions: str, intensity: int = 5,
                 refs_analysis: str = ""):
        super().__init__()
        self._text        = original_text
        self._suggestions = suggestions
        self._intensity   = max(1, min(10, intensity))
        self._refs        = refs_analysis or ""

    def run(self):
        from core.ai_provider import stream as ai_stream, key_error
        err = key_error("screenplay")
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
            # La direction artistique (analyse des références visuelles) nourrit
            # l'application des suggestions si présente — parité Live 2026-07-13.
            if self._refs.strip():
                user_content += (
                    "\n\nDIRECTION ARTISTIQUE (références visuelles — inspiration "
                    "à transposer, jamais à copier) :\n" + self._refs.strip()
                )
            full_text = ai_stream(_APPLY_ARRANGE, user_content,
                                  on_chunk=self.chunk.emit,
                                  tier="creative", max_tokens=8192, task="screenplay")
            self.finished.emit(full_text.strip())
        except Exception as e:
            self.failed.emit(_fmt_err(e))


class GenerateStoryboardWorker(QThread):
    """Génère un découpage technique storyboard depuis un texte de scénario."""
    finished = pyqtSignal(list)   # liste de dicts (plans)
    failed   = pyqtSignal(str)

    def __init__(self, text: str, duration_secs: int = 0,
                 element_names: dict | None = None, strict_no_merge: bool = False):
        super().__init__()
        self._text            = text
        self._duration_secs   = duration_secs
        self._element_names   = element_names or {}
        # P2 : relance en mode « séparer » quand l'utilisateur refuse une fusion.
        self._strict_no_merge = strict_no_merge

    def run(self):
        # Depuis le 2026-07-23 (décision Matthieu) : le passage Découpage →
        # Storyboard repasse par l'IA — elle relit les fiches, met chaque
        # information dans la bonne case JSON et complète les champs manquants.
        # Garde-fous conservés : nombre de plans respecté (1 fiche = 1 plan),
        # fusion jamais silencieuse (merged/merged_note + accord utilisateur),
        # PROMPT VISUEL repris comme base sans être réécrit. En cas d'échec IA
        # sur un découpage structuré, REPLI sur la conversion déterministe
        # (aucune perte : l'ancien chemin reste le filet de sécurité).
        from core.decoupage_layout import (is_structured_layout,
                                           layout_segments_to_cinema_shots)
        self._structured_fallback = None
        if is_structured_layout(self._text):
            try:
                self._structured_fallback = layout_segments_to_cinema_shots(self._text) or None
            except Exception:
                self._structured_fallback = None
        from core.ai_provider import (complete as ai_complete, key_error,
                                      ai_name_for_task)
        # Nom du moteur réellement choisi pour le découpage (Paramètres → par tâche)
        ai_name = lambda: ai_name_for_task("storyboard_gen")
        err = key_error("storyboard_gen")
        if err:
            if self._structured_fallback:
                # Pas de clé pour l'IA → conversion déterministe (filet).
                self.finished.emit(self._structured_fallback)
                return
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
            if self._structured_fallback:
                _n = len(self._structured_fallback)
                _fiche_rules = (
                    f"[SOURCE = DÉCOUPAGE PANDORA VALIDÉ — {_n} fiches PLAN.\n"
                    " - Produis EXACTEMENT un objet JSON par fiche, dans le même ordre"
                    " (1 fiche = 1 plan — n'en supprime ni n'en ajoute aucun).\n"
                    " - Le PROMPT VISUEL de chaque fiche est la BASE des champs"
                    " action/staging/ambiance/decor/lighting : répartis son contenu dans"
                    " les bonnes cases SANS le réécrire ni le résumer ; complète"
                    " uniquement ce qui manque.\n"
                    " - Reprends fidèlement les champs de la fiche : DURÉE, VALEUR/AXE/"
                    "MOUVEMENT/FOCALE proposés, PERSONNAGES, DÉCOR, ACCESSOIRES,"
                    " VÉHICULES, SÉQUENCE — et recopie SOURCE SCÉNARIO → source_excerpt,"
                    " RYTHME → rhythm, INTENTION → intention.\n"
                    " - Toute fusion doit être déclarée (merged:true + merged_note) —"
                    " jamais silencieuse.]\n\n"
                )
                user_content = _lang_hint(lang) + names_block + _fiche_rules + self._text
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
            raw = ai_complete(_storyboard_prompt(lang, self._strict_no_merge), user_content,
                              tier="creative", max_tokens=16000, task="storyboard_gen").strip()
            start = raw.find("[")
            end   = raw.rfind("]") + 1
            if start == -1 or end == 0:
                if self._structured_fallback:
                    self.finished.emit(self._structured_fallback)
                    return
                self.failed.emit(f"Réponse {ai_name()} invalide — pas de tableau JSON trouvé.")
                return

            json_str = raw[start:end]
            shots = _parse_shots_robust(json_str)

            if not shots:
                if self._structured_fallback:
                    self.finished.emit(self._structured_fallback)
                    return
                self.failed.emit(f"Aucun plan extrait — la réponse {ai_name()} était mal formée.")
                return

            # Assemble le prompt structuré en 7 sections étiquetées. L'IA renvoie
            # des morceaux (action/staging/ambiance/decor/lighting + sound_prompt) ;
            # Python construit le format exact ([🎬 ACTION]…). La TECHNIQUE vient des
            # champs caméra. La MISE EN SCÈNE / le PLAN DE FEU sont un premier jet,
            # raffinés ensuite par les pages dédiées (synchro).
            from core.prompt_sections import build as _ps_build, LIGHTING_NOTE as _LN
            for s in shots:
                # Plancher ET plafond appliqués (2-15 s — le prompt l'exige, le
                # code le garantit désormais aussi, 2026-07-23).
                s["duration"] = min(max(float(s.get("duration", 8.0)), 2.0), 15.0)
                s.setdefault("character_ids", [])
                s.setdefault("accessory_ids", [])
                s.setdefault("decor_id",      "")
                # P2 : conserve le drapeau de fusion pour que l'UI puisse demander
                # confirmation (« Garder fusionné / Séparer »). Défaut = non fusionné.
                s["merged"]      = bool(s.get("merged", False))
                s["merged_note"] = (s.get("merged_note") or "").strip()
                # Repli : si l'IA a ignoré les champs de sections, récupérer l'ancien
                # prompt à plat (ou les commentaires) comme ACTION.
                _action = (s.get("action") or "").strip() \
                    or (s.get("seedance_prompt") or "").strip() \
                    or (s.get("comments") or "").strip()
                _light = (s.get("lighting") or "").strip()
                if _light:
                    _light = f"{_light} {_LN}"
                s["seedance_prompt"] = _ps_build(
                    action=_action, staging=(s.get("staging") or "").strip(),
                    ambiance=(s.get("ambiance") or "").strip(),
                    decor=(s.get("decor") or "").strip(),
                    lighting=_light, technique=_technique_line(s),
                    sound=(s.get("sound_prompt") or "").strip(),
                )
                for _k in ("action", "staging", "ambiance", "decor", "lighting"):
                    s.pop(_k, None)

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
            if self._structured_fallback:
                # L'IA a échoué mais le découpage structuré reste convertible :
                # on livre la conversion déterministe plutôt qu'une erreur.
                self.finished.emit(self._structured_fallback)
                return
            self.failed.emit(_fmt_err(e))


# ── Workers d'extraction ──────────────────────────────────────────────────────

def _extract_worker(system_prompt: str, text: str, max_tokens: int = 16000) -> list:
    # 16000 tokens par défaut (2026-07-23) : un gros casting/inventaire ne doit
    # jamais revenir tronqué — le coût ne dépend que de la sortie réelle.
    """Shared extraction logic: call the AI provider, return parsed JSON list."""
    from core.ai_provider import complete as ai_complete, key_error
    err = key_error("extraction")
    if err:
        raise ValueError(err)
    lang = _get_lang()
    raw = ai_complete(system_prompt, _lang_hint(lang) + text,
                      tier="creative", max_tokens=max_tokens, task="extraction").strip()
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


_RECURRENT_SYSTEM = (
    "Tu es un assistant de découpage cinéma. On te donne les plans d'un storyboard, "
    "groupés par SÉQUENCE. Identifie les CONFIGURATIONS CAMÉRA RÉCURRENTES : des plans "
    "qui reviennent sur EXACTEMENT le même cadrage — même décor, même axe caméra et "
    "même acteur à la même position dans le cadre (typiquement un champ/contrechamp qui "
    "alterne entre deux cadrages fixes, ou un plan de coupe qui revient). "
    "Un GROUPE = au moins 2 plans de la MÊME séquence partageant cette configuration. "
    "Ne groupe JAMAIS des plans de séquences différentes ; ignore les plans uniques. "
    "Réponds UNIQUEMENT par du JSON, sans aucun texte autour : "
    '{"groups": [[3,5,7],[4,6]]} où chaque sous-liste contient les NUMÉROS de plan '
    "d'un même groupe récurrent."
)


class AnalyzeRecurrentShotsWorker(QThread):
    """Analyse le storyboard (Claude Haiku) pour repérer les CONFIGURATIONS CAMÉRA
    RÉCURRENTES par séquence (même décor + axe + acteur à la même position,
    champ/contrechamp) et colorer chaque groupe d'une couleur distincte. Repli
    déterministe (core.recurrence.group_recurrent) sans clé IA ou en cas d'échec."""
    done   = pyqtSignal(int)     # nombre de groupes récurrents colorés (PAS « finished »)
    failed = pyqtSignal(str)

    def __init__(self, version_id: str | None = None):
        super().__init__()
        self._vid = version_id

    def run(self):
        try:
            import core.storyboard as sb
            import core.recurrence as rec
            vid = self._vid or sb.DEFAULT_VERSION_ID
            shots = sb.list_shots(vid)
            groups = None
            try:
                groups = self._ai_groups(shots)
            except Exception:
                groups = None
            if not groups:
                groups = rec.group_recurrent(shots)   # repli déterministe
            self.done.emit(rec.apply_groups(groups, vid))
        except Exception as e:
            self.failed.emit(_fmt_err(e))

    def _ai_groups(self, shots: list):
        from core.ai_provider import complete as ai_complete, key_error
        if key_error("extraction"):
            return None
        num2id, lines_by_seq, order = {}, {}, []
        for s in shots:
            try:
                num = int(s.get("number") or 0)
            except (TypeError, ValueError):
                continue
            if not num or not s.get("id"):
                continue
            num2id[num] = s["id"]
            seq = s.get("seq_num", 1)
            if seq not in lines_by_seq:
                lines_by_seq[seq] = []
                order.append(seq)
            lines_by_seq[seq].append(
                f"- Plan {num} | décor: {s.get('decor_name', '?') or '?'} "
                f"| axe: {s.get('camera_axis', '?') or '?'} "
                f"| valeur: {s.get('shot_size', '?') or '?'} "
                f"| acteurs: {', '.join(s.get('character_names', []) or []) or '—'} "
                f"| placement caméra: {s.get('camera_placement', '') or '—'} "
                f"| placement acteurs: {s.get('actor_placement', '') or '—'}")
        if not num2id:
            return None
        user = "\n\n".join(f"SÉQUENCE {seq}\n" + "\n".join(lines_by_seq[seq])
                           for seq in order)
        raw = ai_complete(_RECURRENT_SYSTEM, user, tier="creative",
                          max_tokens=8192, task="extraction").strip()
        start, end = raw.find("{"), raw.rfind("}") + 1
        if start == -1 or end <= 0:
            return None
        data = json.loads(raw[start:end])
        out = []
        for grp in data.get("groups", []):
            if not isinstance(grp, list):
                continue
            ids, seen = [], set()
            for n in grp:
                try:
                    nn = int(n)
                except (TypeError, ValueError):
                    continue
                sid = num2id.get(nn)
                if sid and sid not in seen:
                    seen.add(sid)
                    ids.append(sid)
            if len(ids) >= 2:
                out.append(ids)
        return out or None


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
        from core.ai_provider import key_error
        err = key_error(task="vision")
        if err:
            self.failed.emit(err)
            return
        try:
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

            from core.ai_provider import chat_stream
            full_text = chat_stream(
                self._SYSTEM, [{"role": "user", "content": content}],
                on_chunk=self.chunk.emit, tier="creative", max_tokens=8192,
                task="vision")
            self.done.emit(full_text.strip())
        except Exception as e:
            self.failed.emit(_fmt_err(e))


class EnrichScenarioWithRefsWorker(QThread):
    """Compatibilité historique pour les anciens appels d'enrichissement narratif.

    Le flux principal Cinéma ne l'utilise plus : la direction artistique issue des
    références est désormais enregistrée dans la note de réalisation, séparément
    du scénario.
    """
    chunk  = pyqtSignal(str)
    done   = pyqtSignal(dict)
    failed = pyqtSignal(str)

    _SYSTEM = """\
Tu es un scénariste expert spécialisé dans l'enrichissement de scénarios cinéma \
à partir de références visuelles.

Tu reçois :
1. Un scénario existant
2. Une analyse visuelle d'images de référence (personnages, décors, ambiances, lumières, textures)

Ta mission : ENRICHIR le scénario en intégrant les détails visuels des références \
là où ils correspondent à des éléments déjà présents dans le texte.

CHIRURGIE STRICTE :
- Ne réécris PAS le scénario de zéro — n'enrichis QUE les passages qui ont un \
équivalent dans les références.
- Ne renvoie QUE les passages modifiés (édits ciblés). Tout ce que tu ne renvoies \
pas reste MOT POUR MOT.
- Conserve rigoureusement la structure narrative, le rythme, le ton, les événements \
et les en-têtes de scène (INT./EXT.).
- Intègre les détails de façon naturelle dans le flux du texte (pas de liste, pas de bloc séparé).
- Garde le français.

FORMAT DE RÉPONSE — JSON STRICT, sans markdown, sans texte hors JSON :
{ "edits": [ {"find": "<extrait EXACT et VERBATIM du scénario original, copié \
caractère pour caractère, assez long pour être unique — une phrase ou un paragraphe \
entier>", "replace": "<ce même passage réécrit, enrichi>", "summary": "<résumé court \
en français de ce qui change>"} ] }
- « find » doit exister TEL QUEL dans le scénario (ne le reformule pas, ne corrige \
pas les espaces). « replace » contient le passage entier réécrit.
- « edits » est une liste VIDE [] s'il n'y a rien à enrichir.
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
                max_tokens=8192,
                thinking=_NO_THINK,
                system=self._SYSTEM,
                messages=[{"role": "user", "content": user_content}],
            ) as stream:
                for text in stream.text_stream:
                    full_text += text
                    self.chunk.emit(text)
            from core.text_edits import parse_edits
            self.done.emit({"edits": parse_edits(full_text), "raw": full_text.strip()})
        except Exception as e:
            self.failed.emit(_fmt_err(e))


_REFS_CHAT_SYSTEM = (
    "Tu es conseiller en direction artistique pour un FILM. "
    "Tu disposes de l'ANALYSE du moodboard de référence (décodage complet : "
    "composition, style d'image, lumière, palette, matières) et du SCÉNARIO "
    "du film. L'utilisateur dialogue avec toi pour décider comment TRANSPOSER "
    "cette direction artistique dans sa NOTE DE RÉALISATION, son découpage, "
    "son storyboard et ses plans. Le scénario reste le document narratif.\n"
    "Règles :\n"
    "• Réponds en français, concret et actionnable — propose des formulations "
    "prêtes à coller dans la note de réalisation ou dans les prompts quand c'est utile ;\n"
    "• Ne propose d'altérer le scénario que si l'utilisateur demande explicitement "
    "une modification narrative ;\n"
    "• La DA est une inspiration à transposer, jamais à copier ;\n"
    "• Raisonne en séquences et en plans de cinéma (valeurs de plan, focales, "
    "lumière, palette) ;\n"
    "• Reste dans ton rôle : direction artistique et image."
)


class RefsChatWorker(QThread):
    """Un tour de dialogue direction artistique (streaming) dans la fenêtre
    Références visuelles — équivalent Cinéma de api.live_refs.RefsChatWorker.
    messages = historique [{role, content}] complet, dernier message = question
    de l'utilisateur. Signaux : chunk/done/failed (« done », jamais « finished »)."""
    done   = pyqtSignal(str)
    failed = pyqtSignal(str)
    chunk  = pyqtSignal(str)

    def __init__(self, messages: list, analysis: str, scenario_text: str = ""):
        super().__init__()
        self._messages = list(messages or [])
        self._analysis = analysis or ""
        self._text     = scenario_text or ""

    def run(self):
        from core.ai_provider import chat_stream, key_error
        # Chat de conseil DA = tâche « assistant » (dialogue conseil), comme en Live.
        err = key_error("assistant")
        if err:
            self.failed.emit(err)
            return
        if not self._messages:
            self.failed.emit("Aucun message à envoyer.")
            return
        try:
            ctx_doc = f"ANALYSE DES RÉFÉRENCES (direction artistique) :\n{self._analysis}"
            if self._text.strip():
                ctx_doc += f"\n\nSCÉNARIO ACTUEL :\n{self._text.strip()}"
            # Le contexte documentaire est préfixé au premier message utilisateur
            # (les providers locaux n'aiment pas les très longs system prompts).
            messages = [dict(m) for m in self._messages]
            first = messages[0]
            messages[0] = {"role": first["role"],
                           "content": f"{ctx_doc}\n\n---\n\n{first['content']}"}
            # 8192 tokens : une réponse séquence par séquence dépasse largement 2048.
            full = chat_stream(_REFS_CHAT_SYSTEM, messages, on_chunk=self.chunk.emit,
                               tier="creative", max_tokens=8192, task="assistant")
            self.done.emit(full.strip())
        except Exception as e:
            from core.worker import humanize_api_error
            self.failed.emit(humanize_api_error(str(e)))


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


def _reassign_named(shot: dict, items: list, search_text: str,
                    id_field: str, name_field: str, label: str) -> None:
    """Ré-assigne une catégorie multi-éléments (accessoires / véhicules) d'un plan
    par correspondance de nom : ajoute ceux cités dans le titre/prompt et corrige
    les noms renommés. Les changements sont poussés dans shot['_reassigned'].
    Symétrique de la logique personnages, factorisée pour accessoires + véhicules."""
    existing = set(shot.get(id_field) or [])
    for it in items:
        name = it.get("name")
        iid  = it.get("id")
        if not name or not iid:
            continue
        if iid in existing:
            # ID déjà présent — corriger le nom affiché si c'est un variant fuzzy.
            cur = shot.get(name_field) or []
            if name not in cur:
                for i, old in enumerate(cur):
                    if _same_name(old, name) and old != name:
                        cur[i] = name
                        shot["_reassigned"].append(f"{label} : {old} → {name}")
                        break
            continue
        if _name_in_text(name, search_text):
            shot.setdefault(id_field, [])
            shot.setdefault(name_field, [])
            if iid not in shot[id_field]:
                shot[id_field].append(iid)
                names = shot[name_field]
                replaced = False
                for i, old in enumerate(names):
                    if _same_name(old, name) and old != name:
                        names[i] = name
                        shot["_reassigned"].append(f"{label} : {old} → {name}")
                        replaced = True
                        break
                if not replaced:
                    names.append(name)
                    shot["_reassigned"].append(f"{label} : {name}")
            existing.add(iid)


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

MISE EN SCÈNE & PLAN DE FEU :
- Si un plan contient le champ "mise_en_scene" (non-vide), il décrit le placement réel
  vu de dessus : axe caméra, position des acteurs (fond/milieu/avant × gauche/centre/droite)
  et éclairage (lumières + type de projecteur).
- Réécris alors le prompt pour COLLER à ce placement : qui est à gauche/droite/au fond,
  l'axe caméra indiqué, et l'ambiance lumineuse décrite (direction et type des sources).
- N'invente pas de positions absentes ; respecte exactement ce qui est fourni.

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

    def __init__(self, shots: list, options: dict | None = None):
        super().__init__()
        self._shots = [dict(s) for s in shots]
        # Options sélectionnées dans la fenêtre de synchronisation.
        #   reassign        : ré-assignation noms (personnages / décors / accessoires)
        #   resync_decors   : re-synchroniser les décors (assignation + nom à jour)
        #   rewrite_prompts : réécriture IA des prompts incohérents
        o = options or {}
        self._opt_reassign  = o.get("reassign", True)
        self._opt_decors    = o.get("resync_decors", True)
        self._opt_prompts   = o.get("rewrite_prompts", True)
        # Synchronisation par catégorie (parallèle à « re-synchroniser les décors »).
        self._opt_casting     = o.get("sync_casting", False)
        self._opt_accessories = o.get("sync_accessories", False)
        self._opt_vehicles    = o.get("sync_vehicles", False)
        # Sections structurées du prompt (mise en scène / plan de feu).
        self._opt_staging   = o.get("sync_staging", False)
        self._opt_lighting  = o.get("sync_lighting", False)

    def run(self):
        try:
            self._run()
        except Exception as e:
            self.failed.emit(f"Erreur synchronisation : {e}")

    def _finish(self):
        """Assemble (si demandé) le prompt en SECTIONS étiquetées — [ACTION] +
        [MISE EN SCÈNE] + [PLAN DE FEU] + [SOUND DESIGN] — puis émet finished.
        Déterministe : la mise en scène / le plan de feu viennent des données."""
        if self._opt_staging or self._opt_lighting:
            import core.staging as _staging
            from core.prompt_sections import rebuild as _rebuild, parse as _parse
            for shot in self._shots:
                sid = shot.get("id", "")
                cur = (shot.get("seedance_prompt") or "").strip()
                sec = _parse(cur)                       # récupère l'action si déjà structuré
                action = sec.get("action") or cur
                staging_txt = _staging.staging_summary(sid) if self._opt_staging else sec.get("staging", "")
                light_txt   = _staging.lighting_summary(sid) if self._opt_lighting else sec.get("lighting", "")
                sound_txt   = sec.get("sound") or (shot.get("sound_prompt") or "").strip()
                if not (staging_txt or light_txt):
                    continue
                # rebuild() préserve [🎨 STYLE VISUEL] et toute section non réécrite.
                new = _rebuild(cur, action=action, staging=staging_txt,
                               lighting=light_txt, sound=sound_txt)
                if new and new != cur:
                    shot["seedance_prompt"] = new
                    shot["_prompt_changed"] = True
                    if not shot.get("_reason"):
                        shot["_reason"] = "sections mise en scène / plan de feu"
        self.progress.emit(100, "Synchronisation terminée")
        self.finished.emit(self._shots)

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
        vehicles    = veh_api.list_vehicles()

        char_by_id   = {c["id"]: c for c in characters}
        char_by_name = {c["name"].lower(): c for c in characters if c.get("name")}
        decor_by_id  = {d["id"]: d for d in decors}
        decor_by_name = {d["name"].lower(): d for d in decors if d.get("name")}
        acc_by_name  = {a["name"].lower(): a for a in accessories if a.get("name")}

        # Initialisation des champs meta sur tous les plans (toujours)
        for shot in self._shots:
            shot["_reassigned"]     = []
            shot["_prompt_changed"] = False
            shot["_old_prompt"]     = shot.get("seedance_prompt", "")
            shot["_reason"]         = ""

        do_names  = self._opt_reassign or self._opt_casting
        do_decors = self._opt_reassign or self._opt_decors
        do_acc    = self._opt_reassign or self._opt_accessories
        do_veh    = self._opt_vehicles  # véhicules : non couverts par « Réassigner les noms »

        if do_names or do_decors or do_acc or do_veh:
            self.progress.emit(15, "Phase 1 — ré-assignation des éléments par nom…")

        # ── Phase 1 : name matching ────────────────────────────────────────────
        for shot in self._shots:
            search_text = (
                (shot.get("scene_title") or "") + " " +
                (shot.get("seedance_prompt") or "")
            ).lower()

            # ── Re-synchronisation des décors : rafraîchir le nom si la fiche a
            #    été renommée (decor_id présent mais decor_name obsolète).
            if self._opt_decors and shot.get("decor_id") in decor_by_id:
                _d = decor_by_id[shot["decor_id"]]
                if _d.get("name") and shot.get("decor_name") != _d["name"]:
                    _old = shot.get("decor_name") or "—"
                    shot["decor_name"] = _d["name"]
                    shot["_reassigned"].append(f"décor : {_old} → {_d['name']}")

            # Accessoires / véhicules : ré-assignation par nom — indépendante du
            # casting/décor, donc traitée pour TOUS les plans (même si do_names off).
            if do_acc:
                _reassign_named(shot, accessories, search_text,
                                "accessory_ids", "accessory_names", "accessoire")
            if do_veh:
                _reassign_named(shot, vehicles, search_text,
                                "vehicle_ids", "vehicle_names", "véhicule")

            if not do_names:
                # Seuls les décors sont traités si la ré-assignation des noms est désactivée.
                if do_decors and not shot.get("decor_id"):
                    for decor in decors:
                        if not decor.get("name"):
                            continue
                        if _name_in_text(decor["name"], search_text):
                            shot["decor_id"]   = decor["id"]
                            shot["decor_name"] = decor["name"]
                            shot["_reassigned"].append(f"décor : {decor['name']}")
                            break
                continue

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

            if do_decors and not shot.get("decor_id"):
                for decor in decors:
                    if not decor.get("name"):
                        continue
                    if _name_in_text(decor["name"], search_text):
                        shot["decor_id"]   = decor["id"]
                        shot["decor_name"] = decor["name"]
                        shot["_reassigned"].append(f"décor : {decor['name']}")
                        break

        # ── Phase 2 désactivée : on s'arrête après la ré-assignation ──────────
        if not self._opt_prompts:
            self._finish()   # assemble les sections (mise en scène / plan de feu) si demandé
            return

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

        import core.staging as _staging

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

            try:
                stg_summary = _staging.summary(shot.get("id", ""))
            except Exception:
                stg_summary = ""

            has_elements = bool(chars or decor_el or acc_els)
            prompt = (shot.get("seedance_prompt") or "").strip()
            # On traite le plan s'il a des éléments OU une mise en scène définie.
            if (not has_elements and not stg_summary) or not prompt:
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
            if stg_summary:
                entry["mise_en_scene"] = stg_summary
            shots_payload.append(entry)

        if not shots_payload:
            self.progress.emit(60, "Aucun prompt à réécrire — assemblage des sections…")
            self._finish()
            return

        from core.ai_provider import complete as ai_complete, key_error, ai_name
        err = key_error("sync")
        if err:
            self.failed.emit(err)
            return

        payload_str = json.dumps({"shots": shots_payload}, ensure_ascii=False, indent=2)

        self.progress.emit(50, f"{ai_name()} analyse {len(shots_payload)} plan(s)…")

        raw = ai_complete(_SYNC_STORYBOARD_SYSTEM, payload_str,
                          tier="utility", max_tokens=8192, task="sync").strip()
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

        self.progress.emit(90, "Assemblage des sections…")
        self._finish()


# ── Réécriture du scénario depuis le storyboard ───────────────────────────────

_REWRITE_SCENARIO_SYSTEM = """\
Tu es un scénariste professionnel. On te fournit un découpage technique (storyboard) \
sous forme de liste de plans, dans l'ordre, groupés par séquence. À partir de ces plans, \
reconstitue un SCÉNARIO littéraire complet et cohérent, au format cinéma français standard.

RÈGLES :
- Respecte STRICTEMENT l'ordre des séquences et des plans fournis.
- Pour chaque séquence, écris un en-tête de scène (ex. « SÉQUENCE 1 — INT. SALON — JOUR ») \
en t'appuyant sur le décor et l'heure indiqués.
- Transforme les actions, descriptions et intentions des plans en prose d'action fluide \
(présent de narration), sans jargon technique (pas de « plan large », « travelling »…).
- Si des dialogues sont présents (texte entre guillemets dans les prompts/commentaires), \
intègre-les en format dialogue avec le nom du personnage en majuscules.
- N'invente pas d'événements majeurs absents du storyboard, mais lie les plans entre eux \
de façon naturelle et lisible.
- Conserve les noms exacts des personnages et des lieux.
- Écris en français.
- Réponds UNIQUEMENT avec le texte du scénario, sans préambule, sans markdown, sans commentaire.
"""


class RewriteScreenplayFromStoryboardWorker(QThread):
    """Reconstruit un scénario littéraire à partir du découpage storyboard (Claude).

    Émet finished(str) avec le texte du scénario reconstruit. Ne touche à AUCUNE
    donnée : la sauvegarde (en nouvelle version) est gérée par l'appelant.
    """
    progress = pyqtSignal(int, str)
    finished = pyqtSignal(str)
    failed   = pyqtSignal(str)

    def __init__(self, shots: list):
        super().__init__()
        self._shots = [dict(s) for s in shots]

    def run(self):
        try:
            self._run()
        except Exception as e:
            self.failed.emit(f"Erreur réécriture scénario : {e}")

    def _run(self):
        from core.ai_provider import complete as ai_complete, key_error, ai_name

        err = key_error("sync")
        if err:
            self.failed.emit(err)
            return

        self.progress.emit(10, "Lecture du storyboard…")

        # Groupe les plans par séquence dans l'ordre rencontré.
        seqs: list[dict] = []
        seq_index: dict[str, dict] = {}
        for shot in self._shots:
            sn = str(shot.get("seq_num") or "1").strip() or "1"
            if sn not in seq_index:
                grp = {
                    "seq_num":  sn,
                    "seq_name": shot.get("seq_name", ""),
                    "shots":    [],
                }
                seq_index[sn] = grp
                seqs.append(grp)
            seq_index[sn]["shots"].append({
                "number":     shot.get("number", ""),
                "action":     shot.get("scene_title", ""),
                "decor":      shot.get("decor_name", ""),
                "heure":      shot.get("shot_time", ""),
                "personnages": shot.get("character_names", []),
                "accessoires": shot.get("accessory_names", []),
                "commentaire": shot.get("comments", ""),
                "prompt":      shot.get("seedance_prompt", ""),
            })

        if not seqs:
            self.failed.emit("Aucun plan dans le storyboard.")
            return

        payload = json.dumps({"sequences": seqs}, ensure_ascii=False, indent=2)

        self.progress.emit(45, f"{ai_name()} réécrit le scénario…")

        text = ai_complete(_REWRITE_SCENARIO_SYSTEM, payload,
                           tier="creative", max_tokens=8192, task="sync").strip()

        # Nettoyage d'un éventuel bloc markdown.
        if text.startswith("```"):
            parts = text.split("```")
            text = max((p for p in parts), key=len).strip()
            for pre in ("text", "txt", "markdown"):
                if text.lower().startswith(pre):
                    text = text[len(pre):].lstrip()

        if not text:
            self.failed.emit("Le scénario reconstruit est vide.")
            return

        self.progress.emit(100, "Scénario reconstruit")
        self.finished.emit(text)


# ── Chat Storyboard — modification du découpage par conversation ──────────────

# Champs du plan que le chat est autorisé à modifier (liste blanche stricte).
STORYBOARD_CHAT_FIELDS = [
    "scene_title", "seedance_prompt", "sound_prompt",
    "camera_movement", "shot_size", "focal", "speed",
    "decor_name", "shot_time", "duration", "comments",
    "camera_axis", "camera_placement", "actor_placement",
    "character_names", "accessory_names", "dialogue_lang",
    # 2026-07-23 (audit « la main sur le tableau ») : champs qui manquaient à la
    # liste blanche — les éditions dessus étaient ignorées EN SILENCE.
    "optic", "camera_height", "camera_distance", "seq_name",
    "vehicle_names", "chars_in", "chars_out", "mic_placement",
]

_STORYBOARD_CHAT_SYSTEM = """\
Tu es l'assistant de découpage d'un réalisateur, branché en direct sur son STORYBOARD.
Tu reçois le storyboard complet (liste de plans en JSON) et un message du réalisateur.

TON RÔLE :
- Si le réalisateur POSE UNE QUESTION ou demande une analyse → réponds en texte, AUCUNE modification.
- Si le réalisateur DEMANDE UNE MODIFICATION → applique EXACTEMENT ce qu'il demande, RIEN DE PLUS.

RÈGLE D'OR — CHIRURGIE STRICTE :
- Ne modifie QUE ce qui est explicitement demandé. Si on te demande de changer une seule
  phrase de dialogue dans le plan 3, tu ne touches QUE cette phrase, dans CE plan.
- Tout le reste du champ (et tous les autres plans) est conservé MOT POUR MOT.
- N'invente jamais une modification que le réalisateur n'a pas demandée.
- Ne reformule pas, ne « améliore » pas, ne corrige pas hors de la zone ciblée.
- En cas de doute sur le plan ou le champ visé, NE MODIFIE RIEN et demande une précision.

IDENTIFICATION DES PLANS :
- Réfère-toi aux plans par leur "number" (numéro affiché). Utilise "id" dans ta réponse JSON.

CHAMPS MODIFIABLES (aucun autre) :
%s

FORMAT DE RÉPONSE — JSON STRICT, sans markdown, sans texte hors JSON :
{
  "reply": "<ta réponse en français au réalisateur, courte et claire>",
  "edits": [
    {"id": "<id du plan>", "number": "<numéro affiché>", "field": "<champ>",
     "value": "<nouvelle valeur COMPLÈTE du champ>", "summary": "<résumé court FR de ce qui change>"}
  ]
}
- "edits" est une liste VIDE [] si aucune modification n'est demandée.
- "value" doit contenir la valeur ENTIÈRE du champ après modification (pas un fragment).
- Garde la même langue que le contenu d'origine du champ.
""" % ("\n".join(f"  - {f}" for f in STORYBOARD_CHAT_FIELDS))


class StoryboardChatWorker(QThread):
    """Chat connecté au storyboard : lit tout le découpage, répond au réalisateur
    et renvoie des éditions CHIRURGICALES (uniquement ce qui est demandé).

    finished(dict) → {"reply": str, "edits": [ {id, number, field, value, summary} ]}
    """
    finished = pyqtSignal(dict)
    failed   = pyqtSignal(str)

    def __init__(self, message: str, shots: list, history: list | None = None):
        super().__init__()
        self._message = message
        self._shots   = [dict(s) for s in shots]
        self._history = list(history or [])

    def run(self):
        try:
            self._run()
        except Exception as e:
            self.failed.emit(f"Erreur chat storyboard : {e}")

    def _run(self):
        from core.ai_provider import chat as ai_chat, key_error
        err = key_error("storyboard_chat")
        if err:
            self.failed.emit(err)
            return

        # Payload : uniquement les champs utiles + id/number pour cibler les plans.
        payload_shots = []
        for s in self._shots:
            entry = {"id": s.get("id", ""), "number": s.get("number", "")}
            for f in STORYBOARD_CHAT_FIELDS:
                if f in s and s.get(f) not in (None, ""):
                    entry[f] = s.get(f)
            payload_shots.append(entry)

        sb_json = json.dumps({"shots": payload_shots}, ensure_ascii=False)
        user_msg = (
            f"STORYBOARD ACTUEL :\n{sb_json}\n\n"
            f"MESSAGE DU RÉALISATEUR :\n{self._message}"
        )

        messages = self._history + [{"role": "user", "content": user_msg}]
        # 16000 (plafond « sortie complète ») : à 8192, une demande en LOT
        # (« ajoute X dans tous les prompts ») dépassait le budget → JSON tronqué
        # → zéro édition appliquée, sans message (incident vécu, audit 2026-07-23).
        raw = ai_chat(_STORYBOARD_CHAT_SYSTEM, messages,
                      tier="creative", max_tokens=16000, task="storyboard_chat").strip()

        # Nettoyage markdown éventuel.
        if "```" in raw:
            for part in raw.split("```"):
                cand = part.lstrip("json").strip()
                if cand.startswith("{"):
                    raw = cand
                    break

        try:
            result = json.loads(raw)
        except json.JSONDecodeError:
            # Parsing TOLÉRANT : certains moteurs entourent le JSON de prose →
            # on tente l'objet englobant par équilibrage d'accolades.
            result = None
            start = raw.find("{")
            if start != -1:
                depth = 0
                for i in range(start, len(raw)):
                    if raw[i] == "{":
                        depth += 1
                    elif raw[i] == "}":
                        depth -= 1
                        if depth == 0:
                            try:
                                result = json.loads(raw[start:i + 1])
                            except json.JSONDecodeError:
                                result = None
                            break
            if result is None:
                # Réponse tronquée ou mal formée → ne JAMAIS échouer en silence :
                # si le moteur avait commencé des éditions, le dire clairement.
                reply = raw
                if '"edits"' in raw:
                    reply += ("\n\n⚠ Les modifications n'ont PAS pu être appliquées "
                              "(réponse tronquée ou mal formée). Réduis le périmètre "
                              "(ex. « plans 1 à 10 ») puis réessaie.")
                self.finished.emit({"reply": reply, "edits": []})
                return

        reply = str(result.get("reply", "")).strip()
        edits = result.get("edits", []) or []
        # Filtre les éditions sur la liste blanche des champs.
        clean_edits = [
            e for e in edits
            if isinstance(e, dict) and e.get("field") in STORYBOARD_CHAT_FIELDS
        ]
        self.finished.emit({"reply": reply, "edits": clean_edits})


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
        "SÉPARATION ABSOLUE : le scénario contient uniquement récit, actions jouables, "
        "lieux et dialogues. Style d'image, temporalité de fabrication, lumière, rythme "
        "de montage, durée/valeur/axe/mouvement des plans et continuité technique vont "
        "dans la NOTE DE RÉALISATION, jamais dans le scénario.\n\n"
        "RÉFÉRENCES VISUELLES : Si des images sont jointes, leurs intentions esthétiques "
        "vont dans la Note de réalisation. Seuls les faits narratifs explicitement demandés "
        "peuvent modifier le scénario.\n\n"
        "FORMAT DE RÉPONSE OBLIGATOIRE :\n"
        "Ta réponse doit contenir EXACTEMENT trois parties séparées par ces marqueurs :\n\n"
        "══════════ MESSAGE ══════════\n"
        "[Message conversationnel : indique précisément CE QUE TU AS CHANGÉ et où — "
        "2 à 4 lignes max, ton direct et collaboratif. Si la portée est ambiguë, pose une question.]\n"
        "══════════ SCÉNARIO ══════════\n"
        "[Le scénario complet : séquences, en-têtes INT./EXT., actions et dialogues. "
        "Aucune instruction de plan ou de style de fabrication.]\n"
        "══════════ NOTE DE RÉALISATION ══════════\n"
        "[La note complète mise à jour. Reprends la note fournie et ajoute uniquement "
        "les intentions techniques convenues. Si rien ne change, recopie-la.]\n\n"
        "RÈGLES :\n"
        "- « Ne touche pas X » ou « garde X intact » → X est copié mot pour mot, sans exception\n"
        "- « Développe Y » → ajoute du contenu cohérent UNIQUEMENT dans Y\n"
        "- « Coupe Z » → supprime Z proprement, le reste est intact\n"
        "- Les noms de personnages restent IDENTIQUES dans tout le document\n"
        "- N'invente rien qui ne soit pas dans l'original ou explicitement demandé"
    )


def _arrange_chat_surgical_system(intensity: int) -> str:
    """System prompt de co-écriture CHIRURGICALE : l'IA RÉPOND au réalisateur ET
    renvoie des ÉDITIONS CIBLÉES (find/replace) — jamais le scénario complet. On ne
    renvoie que ce qui change → tokens économisés, pas de réécriture surprise.
    Question/discussion sans changement → « edits » : []."""
    if intensity <= 4:
        creativity = ("Reste au plus près du texte : dans « replace », ne change que ce "
                      "qui est demandé, garde le style et la ponctuation d'origine.")
    elif intensity <= 8:
        creativity = ("Tu peux reformuler et enrichir le passage ciblé dans « replace », "
                      "sans déborder hors de la zone demandée.")
    else:
        creativity = ("Pleine liberté créative sur les passages ciblés dans « replace » "
                      "— mais uniquement là où c'est demandé.")
    return (
        "Tu es un co-auteur dans Pandora, un outil de pré-production IA. Tu dialogues "
        "avec le réalisateur pour affiner un scénario EXISTANT, SANS jamais le réécrire "
        "en entier.\n\n"
        "CHIRURGIE STRICTE :\n"
        "- QUESTION ou discussion (aucun changement demandé) → réponds dans « message » "
        "et renvoie « edits » : [].\n"
        "- DEMANDE de modification → ne renvoie QUE les passages à changer, en éditions "
        "find/replace. Tout ce que tu ne renvoies pas reste MOT POUR MOT. Ne réécris "
        "JAMAIS le scénario complet.\n"
        "- « find » = extrait EXACT et VERBATIM du scénario actuel (caractère pour "
        "caractère, assez long pour être unique). Ne le reformule pas, ne corrige pas ses "
        "espaces. « replace » = ce même passage réécrit.\n"
        f"- {creativity}\n"
        "- Respecte « ne touche pas à X » / « garde X » sans exception.\n"
        "- SÉPARATION ABSOLUE : style d'image, temporalité, lumière, montage, rythme, "
        "durée/valeur/axe/mouvement des plans et continuité technique ne sont JAMAIS "
        "des éditions du scénario. Place-les dans « note_append ».\n"
        "- Une demande peut produire à la fois des « edits » narratifs et un "
        "« note_append » technique. Ne mélange pas les deux.\n"
        "- IMPÉRATIF : si le réalisateur demande un changement, renvoie les éditions "
        "correspondantes dans « edits » DANS CETTE RÉPONSE. Ne dis JAMAIS que tu as "
        "modifié (ou que tu vas modifier) sans renvoyer l'édition — pas de promesse "
        "pour plus tard.\n\n"
        "RÉFÉRENCES VISUELLES : leurs intentions esthétiques vont dans "
        "« note_append » ; elles ne gonflent jamais le texte narratif.\n\n"
        "FORMAT — JSON STRICT, sans markdown, sans texte hors JSON :\n"
        '{ "message": "<ta réponse, claire et AÉRÉE : phrases courtes, paragraphes '
        "séparés par une ligne vide (\\n\\n), liste à puces si utile ; pour une simple "
        'confirmation d\'édition, 1-3 lignes suffisent ; pose une question si la '
        'portée est ambiguë>", '
        '"edits": [ {"find": "<extrait exact>", "replace": "<réécrit>", '
        '"summary": "<résumé court>"} ], '
        '"note_append": "<intentions techniques structurées à ajouter à la note, ou vide>" }'
    )


def _parse_surgical_reply_with_note(raw: str) -> tuple[str, list, str]:
    """Extrait (message, edits, note_append) d'une réponse chirurgicale JSON.
    Tolérant au markdown / JSON partiel ; « edits » via parse_edits (robuste)."""
    import json as _json, re as _re
    from core.text_edits import parse_edits
    edits = parse_edits(raw)
    message = ""
    note_append = ""
    s = (raw or "").strip()
    if "```" in s:
        for part in s.split("```"):
            cand = part.lstrip("json").strip()
            if cand.startswith("{"):
                s = cand
                break
    try:
        obj = _json.loads(s)
        if isinstance(obj, dict):
            message = str(obj.get("message", "")).strip()
            note_append = str(obj.get("note_append", "") or "").strip()
    except Exception:
        m = _re.search(r'"message"\s*:\s*"((?:[^"\\]|\\.)*)"', s)
        if m:
            try:
                message = _json.loads('"' + m.group(1) + '"')
            except Exception:
                message = m.group(1).strip()
    return message, edits, note_append


def _parse_surgical_reply(raw: str) -> tuple[str, list]:
    """Compatibilité Live et extensions 1.3.x : message + éditions uniquement."""
    message, edits, _note = _parse_surgical_reply_with_note(raw)
    return message, edits


class ArrangeChatWorker(QThread):
    """Co-écriture interactive du scénario avec Claude.

    Deux modes :
      - surgical=False (défaut) : réécriture COMPLÈTE — émet message_ready + screenplay_ready
        (utilisé par le bouton « Générer le scénario »).
      - surgical=True : chat CHIRURGICAL — émet message_ready + edits_ready(list) : l'IA
        répond et ne renvoie que des éditions find/replace ciblées (pas de réécriture
        totale → tokens économisés).

    Signals :
        message_ready(str)    — réponse conversationnelle de Claude
        screenplay_ready(str) — scénario remanié complet (mode non chirurgical)
        edits_ready(list)     — éditions ciblées [{find, replace, summary}] (mode chirurgical)
        failed(str)           — message d'erreur
    """
    message_ready    = pyqtSignal(str)
    screenplay_ready = pyqtSignal(str)
    edits_ready      = pyqtSignal(list)
    direction_note_ready = pyqtSignal(str)
    failed           = pyqtSignal(str)

    _MARKER_MSG  = "══════════ MESSAGE ══════════"
    _MARKER_SCR  = "══════════ SCÉNARIO ══════════"
    _MARKER_NOTE = "══════════ NOTE DE RÉALISATION ══════════"

    def __init__(
        self,
        original: str,
        analysis: str,
        history: list[dict],
        user_message: str,
        intensity: int = 5,
        ref_images: list | None = None,
        refs_analysis: str = "",
        direction_note: str = "",
        surgical: bool = False,
    ):
        super().__init__()
        self._original     = original
        self._analysis     = analysis
        self._history      = history        # [{"role": "user"/"assistant", "content": str}]
        self._user_message = user_message
        self._intensity    = intensity
        self._ref_images   = ref_images or []
        self._refs         = refs_analysis or ""
        self._direction_note = direction_note or ""
        self._surgical     = surgical

    def run(self):
        try:
            from core.ai_provider import chat as ai_chat, key_error
            err = key_error("screenplay")
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
            if self._refs.strip():
                context_block += (
                    "\n\n[DIRECTION ARTISTIQUE — issue de l'analyse des images "
                    "de référence. Inspiration à transposer, jamais à copier : "
                    "ancre les ambiances, matières et lumières du scénario "
                    "dans cette direction.]\n" + self._refs.strip()
                )
            context_block += (
                "\n\n[NOTE DE RÉALISATION ACTUELLE — document séparé du scénario]\n"
                + (self._direction_note.strip() or "(vide)")
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

            _sys    = (_arrange_chat_surgical_system(self._intensity) if self._surgical
                       else _arrange_chat_system(self._intensity))
            # CHIRURGICAL : 8192 — 4096 TRONQUAIT le JSON dès que plusieurs passages
            # longs étaient réécrits → 0 édition récupérée (constat Matthieu 2026-07-13).
            # COMPLET : 16000 — 8192 TRONQUAIT la FIN des longs scénarios (constat
            # Matthieu 2026-07-20 : « toute la fin était perdue ») ; parité avec le Live.
            # ANTI-TRONCATURE (2026-07-21) : la coupe par limite est désormais DÉTECTÉE
            # (stop_reason) et la suite demandée automatiquement → plus aucune perte,
            # quel que soit la longueur du scénario (chat_until_complete, ×5 max).
            _maxtok = 8192 if self._surgical else 16000
            if self._ref_images:
                # Le routeur convertit les blocs image pour Anthropic, OpenAI et
                # serveurs compatibles, avec la même continuation anti-troncature.
                from core.ai_provider import chat_until_complete as ai_chat_full
                raw = ai_chat_full(_sys, messages, tier="creative",
                                   max_tokens=_maxtok, task="screenplay",
                                   max_rounds=5).strip()
            else:
                from core.ai_provider import chat_until_complete as ai_chat_full
                raw = ai_chat_full(_sys, messages,
                                   tier="creative", max_tokens=_maxtok,
                                   task="screenplay").strip()

            # ── Mode CHIRURGICAL : message + ÉDITIONS ciblées (aucune réécriture totale) ──
            if self._surgical:
                message, edits, note_append = _parse_surgical_reply_with_note(raw)
                if not message:
                    message = "Modifications proposées." if edits else (raw.strip() or "…")
                self.message_ready.emit(message)
                if note_append:
                    self.direction_note_ready.emit(note_append)
                self.edits_ready.emit(edits)
                return

            # ── Mode COMPLET : message + scénario réécrit entier (marqueurs) ──
            chat_msg   = ""
            screenplay = ""
            direction_note = ""
            if self._MARKER_NOTE in raw:
                raw, direction_note = raw.split(self._MARKER_NOTE, 1)
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
            if direction_note:
                self.direction_note_ready.emit(direction_note.strip())

        except Exception as e:
            self.failed.emit(_fmt_err(e))
