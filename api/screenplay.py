"""
Workers Claude pour les opérations sur le scénario :
- Formatage en scénario classique
- Proposition d'arrangement narratif
- Session de chat interactif pour co-écriture arrangement
- Génération d'un découpage technique storyboard
- Extraction automatique : personnages, décors, accessoires, HMC
"""

import json
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
Tu es un scénariste professionnel spécialisé en mise en page de scénarios cinéma, \
travaillant dans l'outil de pré-production Pandora.

STRUCTURE OBLIGATOIRE :

—— SÉQUENCE N — TITRE COURT ——  (ligne de séparation avant chaque groupe de scènes liées)
INT./EXT. LIEU EXACT — MOMENT  (en-tête de scène, tout en MAJUSCULES)
Action en corps de texte, présent de l'indicatif, pas de technique caméra.
                    NOM DU PERSONNAGE
        Dialogue indenté.

RÈGLES DE MISE EN PAGE :
- Séquences : regroupe les scènes liées en séquences numérotées avec un titre court (2 à 4 mots). \
Format EXACT : —— SÉQUENCE N — TITRE ——  (tirets longs des DEUX côtés, aucune variante)
- En-têtes : INT./EXT. + lieu précis + JOUR / NUIT / AUBE / CRÉPUSCULE / SOIR
- Transitions : N'ajoute PAS de "COUPE SUR :" entre les scènes — la coupe est implicite en écriture \
moderne. Écris uniquement les transitions expressives si elles sont présentes dans le texte original : \
FONDU AU NOIR, FONDU ENCHAÎNÉ, IRIS OUT.
- Personnages : en MAJUSCULES centrés avant les répliques ; orthographe IDENTIQUE dans tout le document

RÈGLES CRITIQUES POUR PANDORA :
- Les noms de personnages doivent être STRICTEMENT IDENTIQUES à travers tout le document \
(même graphie, même casse) — ils sont utilisés pour l'auto-liaison avec le casting et le storyboard.
- Les en-têtes INT./EXT. doivent nommer le lieu clairement et précisément — \
ils alimentent l'extraction automatique des décors.
- Chaque séquence doit avoir un titre court et évocateur — \
il sera utilisé pour nommer les groupes de plans dans le storyboard.
- Les accessoires, véhicules et éléments visuels importants doivent apparaître \
explicitement dans les lignes d'action — ils seront extraits automatiquement.

Conserve TOUT le contenu narratif sans rien résumer ni couper.
Retourne uniquement le scénario formaté, sans commentaires ni explications.\
"""

_ARRANGE_SCREENPLAY_TMPL = """\
Tu es un consultant créatif, dramaturge et superviseur de production pour Pandora, \
un outil de pré-production cinéma qui génère des vidéos via Seedance 2.0 \
(IA vidéo ByteDance via fal.ai).

CONTEXTE TECHNIQUE IMPORTANT :
Le scénario analysé sera découpé en plans individuels de 2 à 15 secondes chacun, \
puis chaque plan sera généré par IA. Pour qu'un plan soit générable, il doit contenir :
- Une action visuelle principale clairement identifiable
- Un ou plusieurs personnages dans un décor précis
Les scènes trop longues, trop denses ou trop abstraites (état intérieur, ellipse, voix off pure) \
sont difficiles à traduire en vidéo IA et doivent être repensées ou complétées.

Analyse le scénario fourni et structure ta réponse en 6 sections :

### 1. Structure narrative
Analyse des actes, du rythme, des points de tension et de l'équilibre scènes/dialogues. \
Le scénario est-il bien découpable en plans courts ? Y a-t-il des séquences trop denses \
ou trop abstraites pour être traduites en vidéo IA ?

### 2. Points forts
Ce qui fonctionne bien — dramatiquement et visuellement. Sois précis et cite des exemples.

### 3. Points à améliorer
Problèmes de rythme, raccords, incohérences de personnages, scènes trop longues ou trop abstraites \
pour la génération vidéo. Cite les scènes concernées.

### 4. Proposition d'arrangement
Si la structure peut être améliorée : propose un ordre alternatif des séquences avec justification. \
Indique les séquences à couper, fusionner ou déplacer, et pourquoi. \
Si la structure est déjà optimale, dis-le explicitement.

### 5. Suggestions concrètes
5 à 7 pistes actionnables, priorisées par impact. Pour chaque suggestion : \
ce qu'il faut changer, pourquoi, et comment le formuler dans le scénario.

### 6. Inventaire complet des personnages
Liste TOUS les personnages sans exception : principaux, secondaires, figurants, silhouettes. \
Ne jamais regrouper sous une formule générique ("les soldats", "ses alliés", "les gardes"). \
Citer CHAQUE personnage par son nom ou sa fonction précise.
Format par ligne : Nom/Fonction | Rôle (Principal / Secondaire / Figurant) | Scènes d'apparition

Respond in {LANG_INSTRUCTION}, in a structured, direct and constructive way.\
"""

_APPLY_ARRANGE = """\
Tu es un scénariste et dramaturge professionnel qui applique des suggestions d'arrangement \
à un scénario existant pour le rendre plus fort et plus adapté à la production vidéo IA.

Tu reçois :
1. LE SCÉNARIO ORIGINAL — la matière de base à préserver et améliorer
2. L'ANALYSE ET LES SUGGESTIONS — le résultat de l'analyse dramaturgique

RÈGLES D'APPLICATION :
- Préserve TOUT le contenu narratif essentiel : actions, dialogues, lieux, personnages
- Applique les suggestions pertinentes selon l'intensité indiquée
- Maintiens la mise en page standard : séquences numérotées (—— SÉQUENCE N — TITRE ——), \
en-têtes INT./EXT., noms de personnages en MAJUSCULES centrés
- Les noms de personnages doivent être STRICTEMENT IDENTIQUES tout au long du document
- Assure-toi que chaque scène contient des actions visuelles claires et concrètes \
(le scénario sera découpé en plans IA de 2 à 15s — pas de scènes trop abstraites)
- Ne résume pas, ne condense pas arbitrairement les dialogues importants

Retourne UNIQUEMENT le scénario réécrit en mise en page standard, sans commentaires ni explications.\
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
  "seedance_prompt": <str — video generation prompt in {PROMPT_LANG}. Mandatory structure: (1) characters present with their appearance/state as described in the screenplay, (2) exact location and environment description from the screenplay, (3) main action and — if dialogue present — the exact words spoken in quotes. NO camera technique, NO creative interpretation — only what is written in the screenplay.>
}

Contrainte absolue : duration ne peut jamais dépasser 15.0 secondes (limite de Seedance 2.0).
Retourne UNIQUEMENT le tableau JSON, sans aucun texte avant ou après.\
"""


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
  "description": <str — description physique (apparence, morphologie, âge, traits distinctifs) et traits de caractère. 1-2 phrases MAX. EXCLURE ABSOLUMENT : actions du personnage, interactions avec d'autres personnages, relations, événements du scénario. La description doit servir de brief pour un casting visuel — apparence uniquement.>,
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
    finished = pyqtSignal(str)
    failed   = pyqtSignal(str)

    def __init__(self, text: str):
        super().__init__()
        self._text = text

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
            msg = client.messages.create(
                model=_MODEL,
                max_tokens=8192,
                system=_FORMAT_SCREENPLAY,
                messages=[{"role": "user", "content": _lang_hint(lang) + self._text}],
            )
            self.finished.emit(msg.content[0].text)
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
                 project_context: dict | None = None):
        super().__init__()
        self._text            = text
        self._duration_secs   = duration_secs
        self._intensity       = max(1, min(10, intensity))
        self._project_context = project_context or {}

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

            user_content = _lang_hint(lang) + "\n\n".join(prefixes) + "\n\n" + self._text
            full_text = ""
            with client.messages.stream(
                model=_MODEL,
                max_tokens=4096,
                system=_arrange_screenplay_prompt(lang),
                messages=[{"role": "user", "content": user_content}],
            ) as stream:
                for text in stream.text_stream:
                    full_text += text
                    self.chunk.emit(text)
            self.finished.emit(full_text)
        except Exception as e:
            self.failed.emit(_fmt_err(e))


class ApplyArrangeWorker(QThread):
    """Applique les suggestions d'arrangement au scénario original via Claude."""
    finished = pyqtSignal(str)
    failed   = pyqtSignal(str)

    def __init__(self, original_text: str, suggestions: str, intensity: int = 5):
        super().__init__()
        self._text        = original_text
        self._suggestions = suggestions
        self._intensity   = max(1, min(10, intensity))

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
            msg = client.messages.create(
                model=_MODEL,
                max_tokens=8192,
                system=_APPLY_ARRANGE,
                messages=[{"role": "user", "content": user_content}],
            )
            self.finished.emit(msg.content[0].text)
        except Exception as e:
            self.failed.emit(_fmt_err(e))


class GenerateStoryboardWorker(QThread):
    """Génère un découpage technique storyboard depuis un texte de scénario."""
    finished = pyqtSignal(list)   # liste de dicts (plans)
    failed   = pyqtSignal(str)

    def __init__(self, text: str, duration_secs: int = 0):
        super().__init__()
        self._text          = text
        self._duration_secs = duration_secs

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
            user_content = _lang_hint(lang) + self._text
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
                user_content = _lang_hint(lang) + budget_hint + self._text
            msg = client.messages.create(
                model=_MODEL_STORYBOARD,
                max_tokens=16000,
                system=_storyboard_prompt(lang),
                messages=[{"role": "user", "content": user_content}],
            )
            raw = msg.content[0].text.strip()
            start = raw.find("[")
            end   = raw.rfind("]") + 1
            if start == -1 or end == 0:
                self.failed.emit("Réponse Claude invalide — pas de tableau JSON trouvé.")
                return

            json_str = raw[start:end]
            shots = _parse_shots_robust(json_str)

            if not shots:
                self.failed.emit("Aucun plan extrait — la réponse Claude était mal formée.")
                return

            for s in shots:
                s["duration"] = min(float(s.get("duration", 8.0)), 15.0)
                s.setdefault("character_ids", [])
                s.setdefault("accessory_ids", [])
                s.setdefault("decor_id",      "")
            self.finished.emit(shots)
        except Exception as e:
            self.failed.emit(_fmt_err(e))


# ── Workers d'extraction ──────────────────────────────────────────────────────

def _extract_worker(system_prompt: str, text: str, max_tokens: int = 4096) -> list:
    """Shared extraction logic: call Claude, return parsed JSON list."""
    cfg = load_config()
    key = cfg.get("anthropic_key", "").strip()
    if not key:
        raise ValueError("Clé API Anthropic manquante.\nConfigure-la dans Paramètres.")
    lang = _get_lang()
    import anthropic
    client = anthropic.Anthropic(api_key=key)
    msg = client.messages.create(
        model=_MODEL,
        max_tokens=max_tokens,
        system=system_prompt,
        messages=[{"role": "user", "content": _lang_hint(lang) + text}],
    )
    raw = msg.content[0].text.strip()
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


# ── Session de chat interactif — co-écriture arrangement ──────────────────────

_ARRANGE_CHAT_SYSTEM = """\
Tu es un co-auteur et dramaturge professionnel qui travaille en dialogue avec le réalisateur \
pour affiner et co-écrire le scénario. Tu as déjà analysé le scénario et proposé un arrangement.

Tu reçois maintenant des instructions du réalisateur pour modifier, affiner ou valider tes propositions. \
Ton rôle est de répondre de façon collaborative, créative et bienveillante.

FORMAT DE RÉPONSE OBLIGATOIRE :
Ta réponse doit contenir EXACTEMENT deux parties séparées par la ligne marqueur ci-dessous :

══════════ MESSAGE ══════════
[Ton message conversationnel : réponse directe à l'instruction, explications, questions, \
commentaires créatifs — 2 à 6 lignes max, ton chaleureux et collaboratif]
══════════ SCÉNARIO ══════════
[Le scénario COMPLET remanié, intégrant toutes les instructions de la conversation, \
en mise en page cinéma standard avec séquences numérotées (—— SÉQUENCE N — TITRE ——), \
en-têtes INT./EXT., noms de personnages en MAJUSCULES centrés avant les répliques.
Conserve TOUT le contenu narratif. N'invente rien qui n'est pas dans l'original ou demandé explicitement.]

RÈGLES :
- Si l'instruction dit "ne change pas X" → X reste EXACTEMENT comme dans l'original
- Si l'instruction demande de développer une scène → ajoute du contenu cohérent
- Si l'instruction demande de couper → supprime proprement sans laisser d'incohérences
- Les noms de personnages doivent être IDENTIQUES dans tout le document
- Intègre TOUTES les instructions précédentes de la conversation, pas seulement la dernière\
"""


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
    ):
        super().__init__()
        self._original     = original
        self._analysis     = analysis
        self._history      = history        # [{"role": "user"/"assistant", "content": str}]
        self._user_message = user_message
        self._intensity    = intensity

    def run(self):
        try:
            cfg = load_config()
            key = cfg.get("anthropic_key", "").strip()
            if not key:
                self.failed.emit("Clé API Anthropic manquante — configure-la dans Paramètres.")
                return

            import anthropic
            lang = _get_lang()
            client = anthropic.Anthropic(api_key=key)

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

            # Message courant
            if not messages:
                messages.append({
                    "role": "user",
                    "content": context_block + "\n\n" + self._user_message,
                })
            else:
                messages.append({"role": "user", "content": self._user_message})

            response = client.messages.create(
                model=_MODEL,
                max_tokens=8192,
                system=_ARRANGE_CHAT_SYSTEM,
                messages=messages,
            )
            raw = response.content[0].text.strip()

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
