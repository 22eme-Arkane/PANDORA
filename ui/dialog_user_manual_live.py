"""
ui/dialog_user_manual_live.py — Manuel d'utilisation de PANDORA | Live.

Divergence ASSUMÉE de Cinéma (2026-06-13) : sous-classe du dialogue Cinéma
(même squelette, même toggle FR/EN, même bouton Fermer rouge) qui remplace
UNIQUEMENT le contenu — sections dédiées au workflow Live / VJ / Mapping.
"""

from ui.dialog_user_manual import (   # noqa: F401
    UserManualDialog as _ManualBase,
    _h, _p, _ul, _tip, _warn, _sep_html,
)


# ── Sections FR ────────────────────────────────────────────────────────────────

_L_SECTIONS = [
    ("🎛", "Bienvenue dans PANDORA | Live"),
    ("✎",  "Conducteur"),
    ("▤",  "Séquences Live & Mapping"),
    ("☺",  "Casting · Accessoires · Véhicules"),
    ("✦",  "Studio IA"),
    ("♫",  "Sound Design"),
    ("⇪",  "Upscaling"),
    ("▶",  "Resolume"),
    ("⚙",  "Paramètres"),
]
_L_GROUPS_FR = [
    ("DÉMARRAGE", 1),
    ("CRÉATION",  3),
    ("PRODUCTION", 3),
    ("DIFFUSION", 1),
    ("RÉFÉRENCE", 1),
]


def _l_welcome() -> str:
    return "".join([
        _h("Bienvenue dans PANDORA | Live", 1),
        _p("PANDORA | Live est le module <b>performance</b> de PANDORA : il prépare des sets "
           "de loops vidéo IA pour le <b>VJing</b> et des séquences continues pour le "
           "<b>mapping vidéo</b> sur façade, calés sur la musique, puis les envoie dans "
           "<b>Resolume Arena</b>."),
        _sep_html(),
        _h("L'interface"),
        _ul(
            "La <b>barre de navigation</b> est en <b>bas de la fenêtre</b> (façon DaVinci) — "
            "drapeaux FR/EN à gauche, pages au centre, <b>Paramètres</b> tout à droite",
            "L'<b>assistant IA</b> vit à <b>gauche</b> — la poignée <b>IA</b> l'ouvre et le ferme",
            "<b>☰ Manuel</b> (rouge) et <b>✉ Nous contacter</b> (vert) en haut à gauche",
        ),
        _sep_html(),
        _h("Workflow recommandé"),
        _ul(
            "<b>1.</b> Écrivez votre <b>Conducteur</b> (la trame du show), ajoutez les musiques du set",
            "<b>2.</b> Mode Mapping : ajoutez la <b>façade du bâtiment</b> isolée sur fond noir",
            "<b>3.</b> <b>Générez le découpage</b> → Séquences Live ou Mapping",
            "<b>4.</b> <b>♫ Caler sur la musique</b> : durées quantisées en mesures, cuts sur les drops",
            "<b>5.</b> <b>✦ Générer les Moods</b>, puis les clips depuis le Studio IA",
            "<b>6.</b> Sound Design et Upscaling au besoin",
            "<b>7.</b> Envoyez le set dans <b>Resolume</b> (slots, BPM, mode show)",
        ),
        _tip("Sans clé fal.ai, tout fonctionne en mode démo (générations simulées). "
             "Les clés API sont partagées avec PANDORA | Cinéma."),
    ])


def _l_conducteur() -> str:
    return "".join([
        _h("Conducteur", 1),
        _p("Le Conducteur est la <b>trame écrite</b> de votre performance — l'équivalent "
           "live du scénario. Tout part de lui."),
        _sep_html(),
        _h("Panneau droit"),
        _ul(
            "<b>Références visuelles</b> — images d'inspiration analysées par l'IA "
            "(direction artistique réutilisable entre projets, chat DA intégré)",
            "<b>Référence bâtiment (façade)</b> — la photo de la façade pour le mapping ; "
            "isolez-la sur fond noir (détourage intégré) : elle sert de canevas aux moods, "
            "de masque de confinement et de base au <b>calage Resolume</b>",
            "<b>Musiques du set</b> — ajoutez vos morceaux : BPM, énergie et drops sont "
            "analysés et injectés dans l'IA",
            "<b>Proposer un arrangement</b> — analyse + suggestions, affinables en co-écriture",
            "<b>Mise en page PANDORA</b> — structure le conducteur en actes et plans avec "
            "PROMPT VIDÉO et PROMPT SON par plan",
            "<b>Générer le découpage</b> — crée la séquence (Live ou Mapping) plan par plan",
            "<b>⚡ Tout générer</b> — enchaîne tout ; <b>⤢ Rouvrir la fenêtre</b> est tout en bas",
        ),
        _tip("Mode Live = loops indépendants pour le VJing. Mode Mapping = séquence continue "
             "sur façade verrouillée (caméra fixe, raccords par keyframes). Le contenu mapping "
             "reste confiné dans la silhouette VISIBLE de la façade, à position et échelle exactes."),
    ])


def _l_sequences() -> str:
    return "".join([
        _h("Séquences Live & Mapping", 1),
        _p("Le tableau des plans du show — l'équivalent live du storyboard, avec des "
           "colonnes dédiées : <b>TC</b> (timecode cumulé), <b>Musique</b>, <b>BPM</b>, "
           "<b>Transition</b>, <b>Prompt vidéo / son</b>."),
        _sep_html(),
        _h("Boutons clés (à gauche de la barre)"),
        _ul(
            "<b>✦ Générer les Moods</b> — une image d'ancrage par plan (mode Mapping : "
            "générée SUR la façade, elle sert ensuite de keyframe)",
            "<b>♫ Caler sur la musique</b> — quantise les durées en MESURES du morceau "
            "assigné et attire les cuts sur les DROPS (calcul local, exact)",
        ),
        _h("Au quotidien"),
        _ul(
            "Glissez les lignes pour réordonner, étirez les colonnes, double-cliquez pour éditer",
            "Chaque plan a un champ <b>🔊 Son</b> (prompt sound design) → bouton <b>➤ SFX</b>",
            "Les clips générés sont <b>conformés</b> à la durée calée (ffmpeg) — pas de dérive en timeline",
            "<b>▱ Calage Resolume</b> (mode Mapping) : génère le preset Advanced Output + la mire",
        ),
    ])


def _l_elements() -> str:
    return "".join([
        _h("Casting · Accessoires · Véhicules", 1),
        _p("Les éléments récurrents de la performance : performers, objets de scène, véhicules. "
           "Identifiés automatiquement depuis le Conducteur ou ajoutés à la main, avec images "
           "de référence générées par IA."),
        _ul(
            "Ces fiches partent comme <b>références visuelles</b> à la génération des clips",
            "Plus les fiches sont complètes, plus les clips sont cohérents d'un plan à l'autre",
        ),
    ])


def _l_studio() -> str:
    return "".join([
        _h("Studio IA", 1),
        _p("La production des clips, en <b>7 onglets</b> : <b>Générer depuis Séquences</b> · "
           "<b>Génération directe</b> · <b>Modifier des clips</b> · <b>Sound Design</b> · "
           "<b>Upscaling</b> · <b>Vidéothèque</b> · <b>Historique</b>."),
        _sep_html(),
        _h("Générer depuis Séquences"),
        _ul(
            "Le <b>Conducteur visuel</b> liste les plans : clic = un plan, Ctrl/Maj+clic ou "
            "lasso souris = plusieurs → la file se construit",
            "Sélecteur <b>Séquences Live / Séquences Mapping</b> en tête d'onglet",
            "Mode Mapping : façade en référence, keyframes de moods (raccords exacts), "
            "nuit + noirs purs imposés, contenu confiné dans la silhouette",
            "<b>▶▶ Lancer la file d'attente</b> — annulable à tout moment ; "
            "<b>Ouvrir le dossier</b> toujours actif",
            "Moteurs affichés avec leurs capacités réelles — <b>Seedance 2.0 recommandé</b>",
        ),
        _h("Vidéothèque"),
        _ul(
            "Tous les clips du projet : lecture, envoi vers Modifier / Upscaling / <b>→ Resolume</b>",
        ),
    ])


def _l_sound() -> str:
    return "".join([
        _h("Sound Design — Mirelo SFX", 1),
        _p("Sonorise la performance (~$0.01/s) :"),
        _ul(
            "<b>Depuis les Séquences</b> — le Conducteur visuel charge le PROMPT SON et la durée "
            "de chaque plan ; multi-sélection → file d'attente, chaque clip part avec SON prompt",
            "<b>Prompt → SFX</b> — un prompt texte → fichier audio",
            "<b>Loop vidéo → bande-son</b> — un clip → bande-son synchronisée sur l'image",
            "Chaque ambiance est <b>conformée à la durée calée</b> de son plan dès sa génération",
            "Option RENDU <b>« Assembler la bande-son (durée exacte) »</b> : une seule piste "
            "calée — durée totale = somme des plans = la timeline, micro-fondus aux jonctions",
        ),
    ])


def _l_upscale() -> str:
    return "".join([
        _h("Upscaling — Topaz / SeedVR2", 1),
        _ul(
            "<b>Ajouter des clips</b> ou <b>⇪ Importer la Vidéothèque</b> — file en petits "
            "carrés avec vignettes mi-clip (clic droit = retirer)",
            "Moteur <b>Topaz</b> (qualité max, modèles Gaia/Artemis…) ou <b>SeedVR2</b> (rapide), "
            "facteur <b>×2</b> ou <b>×4</b>",
            "<b>▶▶ Lancer la file d'attente</b> — annulable, les clips restants sont conservés",
            "La sortie garde le <b>même nom</b> que la source → relink direct",
        ),
        _tip("Workflow économique : générez le set en 480p, validez, puis upscalez en ×2/×4."),
    ])


def _l_resolume() -> str:
    return "".join([
        _h("Resolume — envoi du set", 1),
        _p("Le contrôleur pilote <b>Resolume Arena</b> via son API REST. Dans Resolume : "
           "Préférences → Webserver → <b>« Enable Webserver & REST API »</b> (port 8080)."),
        _sep_html(),
        _h("Utilisation"),
        _ul(
            "<b>Connecter</b> (en haut à gauche) — le point vert confirme la liaison",
            "La <b>bibliothèque</b> (à droite) liste les clips du projet — vignettes "
            "<b>mi-clip</b>, modes Détails / Grandes vignettes, lecture par double-clic",
            "<b>Glissez-déposez</b> un ou plusieurs clips vers les slots de la grille "
            "(multi-sélection : Ctrl/Maj+clic) ; Maj+clic sur un slot = le vider",
            "<b>Envoyer vers Resolume</b> — tri naturel (SQ1_P1, SQ1_P2…), colonnes étendues "
            "automatiquement, BPM de la compo réglé sur le set",
            "<b>Une couche par acte</b> — SQ1 → couche 1, SQ2 → couche 2…",
            "<b>Mode show</b> — Play Once & Hold + Beat Snap + Autopilot : le set s'enchaîne "
            "seul au tempo",
            "<b>▱ Calage Resolume</b> — preset Advanced Output (polygone de façade auto) + "
            "mire de calage du bâtiment, prêts dans le menu Presets d'Arena",
        ),
    ])


def _l_settings() -> str:
    return "".join([
        _h("Paramètres", 1),
        _ul(
            "<b>Connexion Resolume</b> — hôte (localhost) et port (8080) + test de connexion",
            "<b>Clés API</b> — partagées avec PANDORA | Cinéma : fal.ai (vidéo, SFX, upscale), "
            "Anthropic (assistant, traduction, découpage)",
            "<b>Assistant IA</b> — Claude, Fable 5, Mistral ou Ollama local",
            "<b>Sauvegarder</b> applique le tout",
        ),
    ])


_L_BUILDERS = [
    _l_welcome, _l_conducteur, _l_sequences, _l_elements,
    _l_studio, _l_sound, _l_upscale, _l_resolume, _l_settings,
]


# ── Sections EN ────────────────────────────────────────────────────────────────

_L_SECTIONS_EN = [
    ("🎛", "Welcome to PANDORA | Live"),
    ("✎",  "Rundown"),
    ("▤",  "Live & Mapping sequences"),
    ("☺",  "Cast · Props · Vehicles"),
    ("✦",  "AI Studio"),
    ("♫",  "Sound Design"),
    ("⇪",  "Upscaling"),
    ("▶",  "Resolume"),
    ("⚙",  "Settings"),
]
_L_GROUPS_EN = [
    ("GET STARTED", 1),
    ("CREATION",  3),
    ("PRODUCTION", 3),
    ("SHOW", 1),
    ("REFERENCE", 1),
]


def _le_welcome() -> str:
    return "".join([
        _h("Welcome to PANDORA | Live", 1),
        _p("PANDORA | Live is PANDORA's <b>performance</b> module: it builds AI video loop "
           "sets for <b>VJing</b> and continuous sequences for facade <b>video mapping</b>, "
           "beat-aligned to your music, then sends them to <b>Resolume Arena</b>."),
        _sep_html(),
        _h("The interface"),
        _ul(
            "The <b>navigation bar</b> sits at the <b>bottom of the window</b> (DaVinci-style) — "
            "FR/EN flags on the left, pages in the center, <b>Settings</b> at the far right",
            "The <b>AI assistant</b> lives on the <b>left</b> — the <b>IA</b> handle toggles it",
            "<b>☰ Manual</b> (red) and <b>✉ Contact us</b> (green) at the top left",
        ),
        _sep_html(),
        _h("Recommended workflow"),
        _ul(
            "<b>1.</b> Write your <b>Rundown</b> (the show outline), add the set's music tracks",
            "<b>2.</b> Mapping mode: add the <b>building facade</b> isolated on black",
            "<b>3.</b> <b>Generate the breakdown</b> → Live or Mapping sequences",
            "<b>4.</b> <b>♫ Align to music</b>: durations quantized to bars, cuts on the drops",
            "<b>5.</b> <b>✦ Generate Moods</b>, then the clips from the AI Studio",
            "<b>6.</b> Sound Design and Upscaling as needed",
            "<b>7.</b> Send the set to <b>Resolume</b> (slots, BPM, show mode)",
        ),
        _tip("Without a fal.ai key everything runs in demo mode (simulated generations). "
             "API keys are shared with PANDORA | Cinéma."),
    ])


def _le_conducteur() -> str:
    return "".join([
        _h("Rundown", 1),
        _p("The Rundown is the <b>written outline</b> of your performance — the live "
           "equivalent of a screenplay. Everything starts here."),
        _sep_html(),
        _h("Right panel"),
        _ul(
            "<b>Visual references</b> — inspiration images analysed by the AI "
            "(reusable art direction, built-in AD chat)",
            "<b>Building reference (facade)</b> — the facade photo for mapping; isolate it "
            "on black (built-in cutout): it becomes the mood canvas, the confinement mask "
            "and the basis of the <b>Resolume calibration</b>",
            "<b>Set music</b> — add your tracks: BPM, energy and drops are analysed and "
            "injected into the AI",
            "<b>Suggest an arrangement</b> — analysis + suggestions, refinable in co-writing",
            "<b>PANDORA layout</b> — structures the rundown into acts and shots with a "
            "VIDEO PROMPT and a SOUND PROMPT per shot",
            "<b>Generate the breakdown</b> — creates the sequence (Live or Mapping) shot by shot",
            "<b>⚡ Generate everything</b> — runs it all; <b>⤢ Reopen window</b> sits at the bottom",
        ),
        _tip("Live mode = independent loops for VJing. Mapping mode = continuous sequence on a "
             "locked facade (fixed camera, keyframe joins). Mapping content stays inside the "
             "VISIBLE silhouette of the facade, at exact position and scale."),
    ])


def _le_sequences() -> str:
    return "".join([
        _h("Live & Mapping sequences", 1),
        _p("The show's shot table — the live equivalent of the storyboard, with dedicated "
           "columns: <b>TC</b> (cumulative timecode), <b>Music</b>, <b>BPM</b>, "
           "<b>Transition</b>, <b>Video / sound prompt</b>."),
        _sep_html(),
        _h("Key buttons (left of the bar)"),
        _ul(
            "<b>✦ Generate Moods</b> — one anchor image per shot (Mapping mode: generated "
            "ON the facade, later used as a keyframe)",
            "<b>♫ Align to music</b> — quantizes durations to the BARS of the assigned track "
            "and pulls cuts onto the DROPS (local, exact computation)",
        ),
        _h("Day to day"),
        _ul(
            "Drag rows to reorder, resize columns, double-click to edit",
            "Each shot has a <b>🔊 Sound</b> field (sound design prompt) → <b>➤ SFX</b> button",
            "Generated clips are <b>conformed</b> to the aligned duration (ffmpeg) — no timeline drift",
            "<b>▱ Resolume calibration</b> (Mapping mode): generates the Advanced Output preset + the test card",
        ),
    ])


def _le_elements() -> str:
    return "".join([
        _h("Cast · Props · Vehicles", 1),
        _p("The recurring elements of the performance: performers, stage props, vehicles. "
           "Auto-identified from the Rundown or added by hand, with AI-generated reference images."),
        _ul(
            "These cards are sent as <b>visual references</b> when generating clips",
            "The more complete the cards, the more consistent the clips from shot to shot",
        ),
    ])


def _le_studio() -> str:
    return "".join([
        _h("AI Studio", 1),
        _p("Clip production, in <b>7 tabs</b>: <b>Generate from Sequences</b> · "
           "<b>Direct generation</b> · <b>Edit clips</b> · <b>Sound Design</b> · "
           "<b>Upscaling</b> · <b>Video library</b> · <b>History</b>."),
        _sep_html(),
        _h("Generate from Sequences"),
        _ul(
            "The <b>visual Rundown</b> lists the shots: click = one shot, Ctrl/Shift+click or "
            "mouse lasso = several → the queue builds itself",
            "<b>Live / Mapping sequences</b> selector at the top of the tab",
            "Mapping mode: facade as reference, mood keyframes (exact joins), night + pure "
            "blacks enforced, content confined to the silhouette",
            "<b>▶▶ Start the queue</b> — cancellable at any time; <b>Open folder</b> always active",
            "Engines listed with their real capabilities — <b>Seedance 2.0 recommended</b>",
        ),
        _h("Video library"),
        _ul(
            "All the project's clips: play, send to Edit / Upscaling / <b>→ Resolume</b>",
        ),
    ])


def _le_sound() -> str:
    return "".join([
        _h("Sound Design — Mirelo SFX", 1),
        _p("Add sound to the performance (~$0.01/s):"),
        _ul(
            "<b>From the Sequences</b> — the visual Rundown loads each shot's SOUND PROMPT and "
            "duration; multi-selection → queue, each clip leaves with ITS own prompt",
            "<b>Prompt → SFX</b> — a text prompt → audio file",
            "<b>Video loop → soundtrack</b> — a clip → soundtrack synchronized to the picture",
            "Each ambience is <b>conformed to the aligned duration</b> of its shot on generation",
            "OUTPUT option <b>“Assemble the soundtrack (exact duration)”</b>: one single aligned "
            "track — total duration = sum of the shots = the timeline, micro-fades at junctions",
        ),
    ])


def _le_upscale() -> str:
    return "".join([
        _h("Upscaling — Topaz / SeedVR2", 1),
        _ul(
            "<b>Add clips</b> or <b>⇪ Import the Video library</b> — queue of small cards "
            "with mid-clip thumbnails (right-click = remove)",
            "<b>Topaz</b> engine (max quality, Gaia/Artemis models…) or <b>SeedVR2</b> (fast), "
            "factor <b>×2</b> or <b>×4</b>",
            "<b>▶▶ Start the queue</b> — cancellable, remaining clips are kept",
            "The output keeps the <b>same name</b> as the source → direct relink",
        ),
        _tip("Budget workflow: generate the set in 480p, validate, then upscale at ×2/×4."),
    ])


def _le_resolume() -> str:
    return "".join([
        _h("Resolume — sending the set", 1),
        _p("The controller drives <b>Resolume Arena</b> through its REST API. In Resolume: "
           "Preferences → Webserver → <b>“Enable Webserver & REST API”</b> (port 8080)."),
        _sep_html(),
        _h("Usage"),
        _ul(
            "<b>Connect</b> (top left) — the green dot confirms the link",
            "The <b>library</b> (right) lists the project's clips — <b>mid-clip</b> thumbnails, "
            "Details / Large thumbnails modes, double-click to play",
            "<b>Drag & drop</b> one or several clips onto the slot grid "
            "(multi-selection: Ctrl/Shift+click); Shift+click a slot = clear it",
            "<b>Send to Resolume</b> — natural sort (SQ1_P1, SQ1_P2…), columns extended "
            "automatically, composition BPM set from the set",
            "<b>One layer per act</b> — SQ1 → layer 1, SQ2 → layer 2…",
            "<b>Show mode</b> — Play Once & Hold + Beat Snap + Autopilot: the set plays "
            "itself at tempo",
            "<b>▱ Resolume calibration</b> — Advanced Output preset (auto facade polygon) + "
            "building test card, ready in Arena's Presets menu",
        ),
    ])


def _le_settings() -> str:
    return "".join([
        _h("Settings", 1),
        _ul(
            "<b>Resolume connection</b> — host (localhost) and port (8080) + connection test",
            "<b>API keys</b> — shared with PANDORA | Cinéma: fal.ai (video, SFX, upscale), "
            "Anthropic (assistant, translation, breakdown)",
            "<b>AI assistant</b> — Claude, Fable 5, Mistral or local Ollama",
            "<b>Save</b> applies everything",
        ),
    ])


_L_BUILDERS_EN = [
    _le_welcome, _le_conducteur, _le_sequences, _le_elements,
    _le_studio, _le_sound, _le_upscale, _le_resolume, _le_settings,
]


class UserManualDialog(_ManualBase):
    """Manuel PANDORA | Live — même dialogue que Cinéma, contenu Live."""
    SECTIONS_FR = _L_SECTIONS
    GROUPS_FR   = _L_GROUPS_FR
    BUILDERS_FR = _L_BUILDERS
    SECTIONS_EN = _L_SECTIONS_EN
    GROUPS_EN   = _L_GROUPS_EN
    BUILDERS_EN = _L_BUILDERS_EN
