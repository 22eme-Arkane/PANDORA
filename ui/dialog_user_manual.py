"""Manuel d'utilisation complet de PANDORA — dialog navigable par sections."""
from PyQt6.QtWidgets import (
    QDialog, QHBoxLayout, QVBoxLayout, QLabel, QPushButton,
    QTextEdit, QWidget, QScrollArea,
)
from PyQt6.QtCore import Qt
from ui.styles import CP, PANDORA_STYLESHEET


# ── Helpers HTML ───────────────────────────────────────────────────────────────

def _h(text: str, level: int = 2) -> str:
    sizes = {1: "20px", 2: "15px", 3: "13px"}
    sz = sizes.get(level, "13px")
    return (
        f'<p style="margin:18px 0 6px 0;">'
        f'<span style="font-size:{sz};font-weight:800;color:{CP["text_primary"]};">{text}</span>'
        f'</p>'
    )


def _p(text: str) -> str:
    return (
        f'<p style="margin:4px 0 10px 0;color:{CP["text_secondary"]};'
        f'font-size:12px;line-height:1.65;">{text}</p>'
    )


def _ul(*items) -> str:
    lis = "".join(
        f'<li style="margin:3px 0;color:{CP["text_secondary"]};font-size:12px;line-height:1.6;">{i}</li>'
        for i in items
    )
    return f'<ul style="margin:4px 0 12px 16px;padding:0;">{lis}</ul>'


def _tip(text: str) -> str:
    return (
        f'<div style="background:rgba(78,205,196,0.08);border-left:3px solid {CP["accent"]};'
        f'border-radius:0 8px 8px 0;padding:10px 14px;margin:10px 0;">'
        f'<span style="color:{CP["accent"]};font-weight:700;font-size:11px;">💡 Conseil — </span>'
        f'<span style="color:{CP["text_secondary"]};font-size:11px;">{text}</span>'
        f'</div>'
    )


def _warn(text: str) -> str:
    return (
        f'<div style="background:rgba(255,140,66,0.08);border-left:3px solid {CP["orange"]};'
        f'border-radius:0 8px 8px 0;padding:10px 14px;margin:10px 0;">'
        f'<span style="color:{CP["orange"]};font-weight:700;font-size:11px;">⚠ Attention — </span>'
        f'<span style="color:{CP["text_secondary"]};font-size:11px;">{text}</span>'
        f'</div>'
    )


def _sep_html() -> str:
    return f'<hr style="border:none;border-top:1px solid {CP["border"]};margin:18px 0 14px 0;"/>'


def _kbd(key: str) -> str:
    return (
        f'<code style="background:{CP["bg3"]};border:1px solid {CP["border"]};'
        f'border-radius:3px;padding:1px 6px;font-size:10px;color:{CP["text_primary"]};">{key}</code>'
    )


# ── Sections ───────────────────────────────────────────────────────────────────

_SECTIONS = [
    # DÉMARRAGE
    ("🎬", "Bienvenue dans PANDORA"),
    ("📁", "Gestion des projets"),
    # PRÉ-PRODUCTION
    ("≡",  "Scénario"),
    ("⊞",  "Storyboard"),
    ("⊕",  "Castings"),
    ("◻",  "Décors"),
    ("◈",  "Accessoires"),
    ("✂",  "HMC"),
    ("🚗", "Véhicules"),
    ("◎",  "Image & Son"),
    # STUDIO IA
    ("✦",  "Studio IA"),
    ("🎨", "Style visuel"),
    ("🎙", "Doublage"),
    ("💰", "Tarifs IA"),
    # RÉFÉRENCE
    ("⚙",  "Paramètres"),
    ("⌨",  "Raccourcis & Astuces"),
]

# Groupes de navigation (nom du groupe, nombre de sections dans le groupe)
_GROUPS_FR = [
    ("DÉMARRAGE",       2),
    ("PRÉ-PRODUCTION",  8),
    ("STUDIO IA",       4),
    ("RÉFÉRENCE",       2),
]


def _s_welcome() -> str:
    return "".join([
        _h("Bienvenue dans PANDORA", 1),
        _p("PANDORA est un outil de pré-production cinéma conçu pour les réalisateurs, scénaristes et équipes créatives. Il centralise toute la pré-production et permet de générer des vidéos IA via <b>Seedance 2.0</b> de ByteDance, directement depuis l'interface."),
        _sep_html(),
        _h("Ce que PANDORA permet de faire"),
        _ul(
            "Rédiger et mettre en page votre scénario avec l'aide de <b>Claude IA</b> (Anthropic)",
            "Créer un storyboard plan par plan avec caméra, acteurs, décors et prompts",
            "Gérer le casting avec des <b>portraits générés par IA</b> (Nano Banana)",
            "Répertorier décors, accessoires, HMC et véhicules nécessaires au tournage",
            "Définir les préférences caméra et optique du film",
            "Choisir un <b>style visuel</b> qui influence toutes les générations IA",
            "Générer des vidéos IA : Seedance 2.0 (recommandé), Kling, Happy Horse, PixVerse…",
            "Sonoriser vos plans avec le <b>Sound Design</b> (Mirelo SFX : prompt → SFX, vidéo → bande-son)",
            "Monter vos clips en résolution avec l'<b>Upscaling</b> (Topaz / SeedVR2, ×2/×4)",
            "Importer automatiquement les vidéos dans <b>DaVinci Resolve</b> (Studio requis)",
        ),
        _sep_html(),
        _h("La nouvelle interface"),
        _p("Depuis la refonte, PANDORA s'organise comme DaVinci Resolve :"),
        _ul(
            "La <b>barre de navigation</b> est en <b>bas de la fenêtre</b> — les icônes des pages au centre, "
            "les drapeaux FR/EN à gauche, <b>Paramètres</b> tout à droite",
            "L'<b>assistant IA</b> vit à <b>gauche</b> de l'écran — la poignée <b>IA</b> l'ouvre et le ferme",
            "<b>☰ Manuel d'utilisation</b> (rouge) et <b>✉ Nous contacter</b> (vert) sont en <b>haut à gauche</b>",
            "Soutenir Pandora, Mises à jour et Sauvegarder restent en haut à droite",
            "Les pages occupent <b>toute la largeur de l'écran</b> ; Paramètres et les formulaires "
            "du Studio IA sont centrés pour rester lisibles",
        ),
        _sep_html(),
        _h("Workflow recommandé"),
        _ul(
            "<b>1.</b> Créez ou ouvrez un projet depuis la page Projets",
            "<b>2.</b> Rédigez votre scénario, mettez-le en page PANDORA avec Claude IA",
            "<b>3.</b> Choisissez un style visuel depuis l'éditeur de scénario",
            "<b>4.</b> Générez automatiquement personnages, décors, HMC, accessoires, véhicules depuis le scénario",
            "<b>5.</b> Générez le storyboard avec Claude IA, affinez plan par plan",
            "<b>6.</b> Configurez les moods Seedance pour chaque plan",
            "<b>7.</b> Lancez la génération vidéo depuis le storyboard ou le Studio IA",
            "<b>8.</b> Sonorisez (Sound Design) et montez en résolution (Upscaling) au besoin",
        ),
        _tip("PANDORA fonctionne sans aucune clé API en <b>mode démo (mock)</b> : les vidéos et portraits sont simulés localement. Ajoutez vos clés API dans Paramètres pour les générations réelles."),
        _sep_html(),
        _h("Clés API nécessaires"),
        _ul(
            "<b>fal.ai</b> — Seedance 2.0 (génération vidéo)",
            "<b>Anthropic</b> — Claude IA (scénario, storyboard, extraction d'éléments)",
            "<b>Nano Banana</b> — Génération de portraits de personnages",
        ),
    ])


def _s_projects() -> str:
    return "".join([
        _h("Gestion des projets", 1),
        _p("Chaque projet PANDORA est un <b>dossier</b> sur votre disque contenant toutes les données du film : scénario, storyboard, castings, décors, vidéos générées, etc."),
        _sep_html(),
        _h("Créer un nouveau projet"),
        _ul(
            "Cliquez sur <b>✦ Nouveau projet</b> dans la page Projets",
            "Choisissez un dossier de destination sur votre disque",
            "Donnez un nom au projet",
            "PANDORA crée automatiquement la structure de dossiers nécessaire",
        ),
        _h("Ouvrir un projet existant"),
        _ul(
            "Cliquez sur <b>Ouvrir un dossier…</b> pour naviguer vers un projet existant",
            "Ou cliquez directement sur un projet dans la liste des <b>Projets récents</b>",
            "Le projet en cours est toujours affiché en haut avec le badge <b>ACTUEL</b>",
        ),
        _h("Changer de projet"),
        _ul(
            "Rendez-vous dans la page <b>Projets</b> depuis la barre de navigation, en bas de la fenêtre",
            "Cliquez sur un projet récent pour basculer vers lui",
            "PANDORA sauvegarde automatiquement avant de changer",
        ),
        _sep_html(),
        _h("Structure d'un projet"),
        _p("Chaque projet stocke ses données dans un sous-dossier <b>data/</b> créé automatiquement :"),
        _ul(
            "<code>scenarios/</code> — Scénarios et leurs versions nommées",
            "<code>storyboard/</code> — Plans du découpage par version",
            "<code>castings/</code> — Personnages et portraits IA",
            "<code>decors/</code> — Lieux de tournage et images de repérage",
            "<code>accessories/</code> — Accessoires (props) avec références",
            "<code>hmc/</code> — Habillage, maquillage, coiffure",
            "<code>vehicles/</code> — Véhicules du tournage",
            "<code>Seedance/</code> — Vidéos générées par Seedance 2.0",
        ),
        _tip("Les projets récents sont mémorisés entre les sessions. Si un dossier est déplacé ou supprimé, PANDORA vous en informe et le retire automatiquement de la liste."),
    ])


def _s_scenario() -> str:
    return "".join([
        _h("Scénario", 1),
        _p("La page Scénario est le cœur de PANDORA. Rédigez votre script, structurez-le avec Claude IA, enrichissez-le avec des références visuelles, gérez des versions, et générez toute votre pré-production depuis un seul endroit."),
        _sep_html(),

        _h("L'éditeur de texte"),
        _ul(
            "Police <b>Courier New 14pt</b> — standard industrie pour les scénarios",
            "Le texte est centré dans une colonne, comme une vraie page de scénario imprimée",
            "La sauvegarde est <b>automatique</b> 3 secondes après chaque modification",
            "Cliquez sur <b>← Retour</b> pour revenir à la liste des scénarios sans perdre votre travail",
        ),

        _h("Style du film et durée (en haut de l'éditeur)"),
        _ul(
            "<b>Style visuel</b> — influence toutes les générations IA (portraits, décors, vidéos Seedance) — changez-le à tout moment",
            "<b>Durée du film</b> — durée totale estimée du projet en minutes et secondes",
        ),

        _sep_html(),
        _h("☁ Références visuelles — Analyser avec Claude"),
        _p("Importez des images dans votre session d'écriture. Claude les analyse et enrichit les descriptions de votre scénario en établissant des correspondances visuelles."),
        _ul(
            "Cliquez sur <b>☁ Analyser avec Claude</b> dans le panneau droit",
            "La bande d'images s'affiche en bas — cliquez sur <b>+</b> (toujours à gauche) pour ajouter vos références : photos de lieux, personnages, ambiances, moodboards…",
            "Claude analyse le contenu visuel : couleurs, textures, architecture, personnages, lumière",
            "L'analyse s'affiche en temps réel dans une fenêtre de prévisualisation streaming",
            "Cliquez <b>☁ Enrichir le scénario</b> : Claude compare les images avec votre scénario, identifie les correspondances (ex : samouraï dans l'image ↔ samouraï dans le texte, muraille de Chine ↔ décor architectural), et enrichit précisément les descriptions des éléments reconnus",
            "Les parties non reconnues ne sont pas modifiées — l'enrichissement est chirurgical",
        ),
        _tip("Ajoutez jusqu'à 10 images. Plus les images sont proches de vos personnages et décors réels, plus l'enrichissement sera précis et utile pour les prompts Seedance."),

        _sep_html(),
        _h("◈ Mise en page PANDORA"),
        _p("Reformate votre texte brut en format Pandora/Seedance — optimisé pour la génération vidéo IA, pas pour le format Hollywood classique."),
        _ul(
            "Cliquez sur <b>◈ Mise en page PANDORA</b> dans le panneau droit (section Claude IA)",
            "Claude reformate votre texte :",
            "→ En-têtes de scène : <code>INT. LIEU — HEURE</code> / <code>EXT. LIEU — HEURE</code>",
            "→ Titres de séquences : <code>—— SÉQUENCE 1 — TITRE ——</code>",
            "→ Noms de personnages en MAJUSCULES centrés avant les répliques",
            "→ Descriptions d'action enrichies, visuelles et <b>promptables</b> : spatiales, concrètes, avec mouvement et lumière",
            "→ Transitions expressives conservées (FONDU AU NOIR, etc.)",
            "Le résultat s'affiche en temps réel dans une fenêtre — cliquez <b>↩ Remplacer le texte</b> pour l'appliquer",
        ),
        _tip("La mise en page PANDORA n'est pas le format Hollywood standard. Elle est conçue pour que chaque ligne d'action puisse devenir un prompt Seedance efficace : descriptions visuelles précises, mouvements concrets, ambiances détaillées."),

        _sep_html(),
        _h("⊞ Proposer un arrangement"),
        _p("Claude analyse la structure de votre scénario et propose des améliorations ciblées. L'analyse s'ouvre en fenêtre streaming. Deux chemins disponibles après l'analyse."),
        _ul(
            "Cliquez <b>⊞ Proposer un arrangement</b> — l'analyse s'affiche en temps réel",
            "La fenêtre Studio de création s'ouvre — réglez l'<b>intensité</b> (1 à 10) directement dans le panneau dialogue :",
            "→ <b>1-2</b> : Corrections orthographiques et de ponctuation uniquement",
            "→ <b>3-4</b> : Restructuration douce, rythme de lecture amélioré",
            "→ <b>5-6</b> : Reformulation standard, cohérence narrative et dialogues",
            "→ <b>7-8</b> : Refonte de séquences, développement ou coupe de scènes",
            "→ <b>9-10</b> : Réécriture profonde — structure et contenu modifiés",
        ),
        _h("Après l'analyse — deux chemins"),
        _ul(
            "<b>✓ Appliquer les suggestions directement</b> : Claude réécrit le scénario en appliquant ses suggestions. Le résultat s'affiche en prévisualisation — cliquez <b>↩ Mettre à jour le scénario</b> pour remplacer.",
            "<b>☁ Session de co-écriture</b> : ouvre le Studio de co-écriture pour itérer interactivement avec Claude (voir section suivante).",
        ),

        _sep_html(),
        _h("☁ Studio de co-écriture — Session avec Claude"),
        _p("Un espace de dialogue interactif entre vous et Claude. Itérez sur votre scénario en échangeant des instructions précises, plan par plan ou scène par scène."),
        _h("Interface"),
        _ul(
            "Onglet <b>Analyse initiale</b> (panneau gauche) — les suggestions détaillées de Claude",
            "Onglet <b>Scénario remanié</b> (panneau gauche) — la version co-écrite, mise à jour à chaque échange",
            "Panneau <b>Dialogue</b> (droite) — vos instructions et les réponses de Claude en bulles de chat",
            f"Envoyez avec le bouton <b>Envoyer ☁</b> ou {_kbd('Ctrl+↵')}",
        ),
        _h("Chirurgie, pas réécriture"),
        _ul(
            "Claude ne modifie <b>que ce que vous demandez explicitement</b>",
            "Tout le reste du scénario est copié <b>mot pour mot</b> sans retouche",
            "Exemple : <i>« Change uniquement la dernière réplique de Marc »</i> → seule cette réplique change",
            "Si la demande est ambiguë, Claude pose une question avant de réécrire",
        ),
        _h("Navigation entre les versions"),
        _ul(
            "Chaque réponse de Claude crée une version dans l'historique",
            "Flèches <b>←</b> et <b>→</b> en haut de l'onglet Scénario remanié pour naviguer (ex : v 2/3)",
            "Revenez en arrière, comparez, repartez en avant — non destructif",
            "Si vous revenez à v2 et envoyez une nouvelle instruction, la v3 est remplacée",
        ),
        _h("Références visuelles dans la session"),
        _ul(
            "Ajoutez des images avec le bouton <b>+</b> dans la bande de références (panneau droit)",
            "Les images sont jointes à votre prochain message uniquement, puis effacées automatiquement",
            "Claude les analyse et intègre leurs détails visuels <b>uniquement dans les parties que vous demandez de modifier</b>",
            "Maximum 4 images par message — supprimez avec le bouton <b>✕</b> sur chaque miniature",
        ),
        _h("Appliquer le résultat"),
        _ul(
            "Cliquez <b>✓ Appliquer ce scénario au projet</b> pour remplacer le scénario dans l'éditeur",
            "Vous pouvez éditer manuellement l'onglet Scénario remanié avant d'appliquer",
            "Un badge <i>Édition manuelle active</i> s'affiche si vous avez modifié le texte à la main",
        ),

        _sep_html(),
        _h("↩ Undo / Redo"),
        _ul(
            "Chaque modification par Claude crée un <b>point de sauvegarde automatique</b>",
            f"Bouton <b>↩</b> (ou {_kbd('Ctrl+Z')}) pour annuler, <b>↪</b> (ou {_kbd('Ctrl+Y')}) pour rétablir",
            "L'historique est conservé toute la session — revenez aussi loin que nécessaire",
        ),

        _h("Versions nommées"),
        _ul(
            "Cliquez sur <b>✚</b> pour sauvegarder une version nommée à tout moment",
            "Sélectionnez une version dans le menu déroulant pour la charger instantanément",
            "Supprimez une version avec le bouton <b>✕</b>",
            "Exemple : <i>Ébauche 1</i>, <i>Après arrangement IA</i>, <i>Version finale</i>",
        ),

        _sep_html(),
        _h("☁ Générer depuis le scénario — Extraction automatique"),
        _p("Une fois le scénario rédigé et mis en page, Claude extrait automatiquement tous les éléments de production et les ajoute aux pages correspondantes. Utilisez les boutons individuels <b>ou</b> le bouton rouge <b>Tout Générer</b> en bas du panneau pour traiter tous les éléments en une seule passe :"),
        _ul(
            "<b>Générer les personnages</b> — identifie les noms en MAJUSCULES et crée les fiches de casting",
            "<b>Générer les décors</b> — extrait tous les lieux INT./EXT. présents dans le script",
            "<b>Générer les accessoires</b> — liste les props et équipements mentionnés dans les descriptions d'action",
            "<b>Générer le HMC</b> — identifie les descriptions de costumes, maquillage et coiffures",
            "<b>Générer les véhicules</b> — liste les véhicules nécessaires au tournage",
            "<b>Générer le storyboard</b> — crée un découpage plan par plan complet avec caméra, valeurs de plan et prompts Seedance",
        ),
        _p("Pour chaque catégorie (sauf storyboard), une fenêtre propose deux modes :"),
        _ul(
            "<b>Identifier seulement</b> — extrait et sauvegarde les fiches, sans générer d'images",
            "<b>Identifier et générer</b> — extrait les fiches ET lance Nano Banana pour créer une image de référence pour chaque élément en même temps",
        ),
        _tip("Mettez votre scénario en page PANDORA avec Claude <b>avant</b> de générer les éléments. Un scénario structuré (INT./EXT., noms de personnages cohérents en MAJUSCULES) donne des extractions nettement meilleures."),
        _warn("Si Claude ne répond pas ou génère des erreurs réseau, <b>désactivez votre VPN</b> — certains serveurs VPN sont bloqués par l'API Anthropic."),
    ])


def _s_storyboard() -> str:
    return "".join([
        _h("Storyboard", 1),
        _p("Le Storyboard liste tous les plans du film dans l'ordre chronologique. Chaque ligne représente un plan avec ses paramètres techniques et artistiques complets — caméra, éléments, mise en scène, prompt vidéo."),
        _sep_html(),

        _h("Colonnes du tableau"),
        _ul(
            "<b>Aperçu</b> — mood image Flux T2I du plan (cliquez pour générer ou choisir)",
            "<b>Séq</b> — numéro et nom de la séquence",
            "<b>Plan</b> — numéro du plan dans la séquence",
            "<b>Action</b> — titre de la scène / description de l'action",
            "<b>Mouvement</b> — mouvement caméra (Statique, Travelling, Panoramique, Zoom, Drone…)",
            "<b>Valeur</b> — taille de plan (Gros plan, Plan moyen, Plan américain, Plan d'ensemble…)",
            "<b>Focal</b> — focale de l'objectif en mm",
            "<b>Vitesse</b> — vitesse de prise de vue (normale, ralenti ×0.5, accéléré…)",
            "<b>Décor</b> — lieu de tournage assigné",
            "<b>Heure</b> — moment de la journée (Jour, Nuit, Aube, Crépuscule, Magie dorée…)",
            "<b>Accessoires</b> — props utilisés dans ce plan",
            "<b>Acteurs</b> — personnages présents dans le cadre",
            "<b>Axe</b> — angle de prise de vue (Face, 3/4, Latéral 90°, Dos, Plongée, Contre-plongée)",
            "<b>Durée</b> — durée prévue du plan en secondes (2 à 15 s)",
            "<b>Prompt</b> — prompt Seedance 2.0 pour la génération vidéo",
        ),

        _h("Modifier un plan"),
        _ul(
            "Cliquez directement sur <b>n'importe quelle cellule</b> pour modifier en ligne",
            "Cliquez sur <b>Éditer</b> à droite de la ligne pour ouvrir la fiche complète du plan",
            "La fiche donne accès à tous les champs : CAMÉRA, ÉLÉMENTS, MISE EN SCÈNE, DURÉE, COMMENTAIRES, PROMPT",
            "Glissez le grip <b>⠿</b> à gauche d'un plan pour le déplacer et réorganiser l'ordre",
        ),

        _h("Champs Mise en scène"),
        _ul(
            "<b>Axe caméra</b> — Face / 3/4 / Latéral 90° / Dos / Plongée / Contre-plongée",
            "<b>Placement caméra</b> — description libre du positionnement (hauteur, distance, support)",
            "<b>Placement acteurs</b> — placement des comédiens dans le cadre",
            "<b>Entrée (IN)</b> — personnages entrant dans le plan (pour la continuité de raccord)",
            "<b>Sortie (OUT)</b> — personnages quittant le plan",
            "<b>Micro</b> — placement du micro pour ce plan",
        ),

        _sep_html(),
        _h("Aperçu — Mood image par plan"),
        _p("Chaque plan peut avoir une <b>mood image</b> générée via Flux T2I — une visualisation rapide de l'ambiance avant de lancer la vidéo Seedance."),
        _ul(
            "Cliquez sur la cellule <b>Aperçu</b> d'un plan pour ouvrir le dialogue de mood",
            "Saisissez un prompt libre ou utilisez le prompt Seedance existant du plan",
            "Cliquez <b>Générer</b> — Flux Schnell génère plusieurs propositions rapidement",
            "Sélectionnez l'image qui correspond à votre vision : elle apparaît en miniature dans le tableau",
            "Régénérez autant de fois que nécessaire — Flux est très économique (~$0.003 / image)",
        ),
        _tip("Générez les moods <b>avant</b> de lancer les vidéos Seedance : visualisez l'ambiance de chaque plan et affinez les prompts sans frais vidéo."),

        _sep_html(),
        _h("⟳ Synchronisation — Cohérence des données"),
        _p("Le bouton <b>⟳ Synchronisation</b> dans la barre d'outils aligne automatiquement les prompts Seedance avec les données actuelles du casting, des décors, accessoires et véhicules."),
        _ul(
            "Utile après avoir renommé un personnage ou modifié les fiches de production",
            "Claude Haiku rapproche les noms légèrement différents — ex : <i>« Le Samouraï »</i> ↔ <i>« samouraï »</i>",
            "Garantit que chaque prompt référence les bons éléments avec leurs noms exacts",
        ),

        _h("✦ Générer les Moods — Aperçus visuels en batch"),
        _ul(
            "Cliquez sur <b>✦ Générer les Moods</b> dans la barre d'outils du storyboard",
            "Flux T2I génère une image de référence visuelle pour chaque plan en une seule passe",
            "Les images apparaissent dans la colonne Mood — visualisez l'ambiance de chaque plan avant de lancer Seedance",
            "Régénérez le mood d'un seul plan en cliquant directement sur sa cellule Mood",
        ),

        _h("▶ Générer une vidéo depuis un plan"),
        _ul(
            "Cliquez sur <b>▶ Générer</b> à droite d'un plan pour lancer la génération Seedance directement",
            "La vidéo est générée avec : prompt du plan + style visuel + mosaïques de références (personnages, décor, accessoires)",
            "Une fois terminée, la vidéo apparaît en miniature dans la colonne Aperçu",
            "Cliquez sur la miniature pour l'ouvrir, la copier ou l'importer dans DaVinci Resolve",
        ),

        _sep_html(),
        _h("Versions du storyboard"),
        _ul(
            "Gérez plusieurs versions : découpage principal, version courte, alternatives de montage…",
            "Menu déroulant en haut : créer, charger et supprimer des versions nommées",
            "La suppression de la <b>dernière version</b> est protégée — au moins une version doit toujours exister",
        ),

        _tip("Générez d'abord le storyboard complet depuis la page Scénario (Claude IA → Générer le storyboard), puis affinez plan par plan. La génération automatique crée un découpage cohérent que vous peaufinez ensuite."),
        _warn("La génération du storyboard via Claude peut prendre du temps selon la longueur du scénario. Si vous utilisez un <b>VPN</b>, désactivez-le — certains serveurs VPN bloquent la connexion avec l'API Anthropic (Claude)."),
    ])


def _s_castings() -> str:
    return "".join([
        _h("Castings — Personnages du film", 1),
        _p("La page Castings centralise tous les personnages avec leurs caractéristiques physiques et psychologiques, leurs portraits IA et leurs références visuelles. Les portraits sont automatiquement utilisés comme références dans les générations Seedance — c'est le mécanisme central de cohérence visuelle entre les plans."),
        _sep_html(),

        _h("Créer un personnage"),
        _ul(
            "Cliquez sur <b>✦ Créer un personnage</b>",
            "Remplissez : nom (en MAJUSCULES comme dans le scénario), rôle dans l'histoire, âge approximatif",
            "Décrivez la <b>physique</b> : taille, corpulence, couleur de peau, couleur des yeux, type de coiffure, particularités physiques",
            "Décrivez la <b>psychologie</b> : traits de personnalité, motivations, arcs narratifs, contradictions",
            "Ajoutez des notes de casting : type de comédien recherché, références d'acteurs connus",
            "Utilisez <b>↑ Import</b> pour importer des portraits existants (PNG, JPG) directement dans le casting sans passer par Nano Banana",
        ),
        _p("Via le Scénario, le bouton <b>Générer les personnages</b> propose deux modes : <b>Identifier seulement</b> (fiches sans image) ou <b>Identifier et générer</b> (fiches + portrait Nano Banana généré automatiquement pour chaque personnage)."),

        _sep_html(),
        _h("Générer un portrait IA (Nano Banana)"),
        _ul(
            "Ouvrez la fiche d'un personnage et cliquez sur <b>Générer un portrait</b>",
            "Choisissez le <b>style visuel</b> dans le menu déroulant (Film réaliste, Anime, Cyberpunk…) — il s'applique au rendu du portrait",
            "Nano Banana génère le portrait à partir de la description physique + le style sélectionné",
            "Plusieurs portraits sont proposés — sélectionnez celui qui correspond à votre vision",
            "Le portrait sélectionné devient la <b>référence visuelle officielle</b> du personnage",
            "Cliquez <b>Générer une variation</b> pour régénérer sans changer les paramètres",
            "Régénérez autant de fois que nécessaire — chaque génération produit des variantes différentes",
        ),
        _warn("La génération de portraits nécessite une clé API Nano Banana dans Paramètres. Sans clé, le mode mock génère des images placeholder colorées."),

        _sep_html(),
        _h("Impact sur les générations vidéo Seedance"),
        _p("Les portraits sont automatiquement injectés comme références visuelles dans Seedance 2.0 — le personnage garde le même visage et style visuel d'un plan à l'autre."),
        _ul(
            "Quand vous lancez une génération T2V depuis le storyboard :",
            "→ <b>Slot référence 1</b> : mosaïque des portraits des personnages assignés au plan",
            "→ <b>Slot référence 2</b> : image du décor assigné au plan",
            "→ <b>Slot référence 3</b> : mosaïque accessoires et véhicules assignés",
            "Ces références font basculer automatiquement Seedance de <i>text-to-video</i> vers <i>reference-to-video</i>",
            "Plus vos portraits sont précis, plus la cohérence visuelle entre les plans est forte",
        ),
        _tip("Assignez vos personnages à chaque plan du storyboard (fiche plan → champ Acteurs). Sans assignation, les portraits ne sont pas envoyés à Seedance et la cohérence visuelle n'est pas garantie."),

        _h("Assignation aux plans du storyboard"),
        _ul(
            "Depuis la fiche d'édition d'un plan → section ÉLÉMENTS → champ <b>Acteurs</b>",
            "Sélectionnez les personnages présents dans le cadre",
            "Leurs portraits sont inclus dans la mosaïque de référence Seedance pour ce plan",
            "Claude référence leurs noms exacts lors de la génération du storyboard et de l'arrangement",
        ),
    ])


def _s_decors() -> str:
    return "".join([
        _h("Décors — Lieux de tournage", 1),
        _p("La page Décors centralise tous les lieux de tournage avec leurs caractéristiques techniques, artistiques et logistiques."),
        _sep_html(),
        _h("Créer un décor"),
        _ul(
            "Cliquez sur <b>✦ Créer un décor</b>",
            "Remplissez : nom du lieu, catégorie, description et ambiance recherchée",
            "Notez les <b>contraintes techniques</b> : permis de tournage, accessibilité, lumière naturelle disponible",
            "Ajoutez des <b>images de référence</b> : photos de repérage, moodboards",
        ),
        _h("Catégories de décors"),
        _ul(
            "<b>Intérieur</b> — appartements, bureaux, restaurants, bâtiments publics",
            "<b>Extérieur</b> — rues, parcs, campagne, plages, forêts, architecture",
            "<b>Studio</b> — tournage en studio avec décors construits",
            "<b>Véhicule</b> — intérieur de voiture, train, avion, bateau",
        ),
        _h("Assigner aux plans du storyboard"),
        _ul(
            "Chaque plan peut être assigné à un décor depuis la fiche d'édition du plan",
            "Le décor apparaît dans la colonne Décor du storyboard",
            "Les prompts Seedance intègrent automatiquement la description du décor",
        ),
        _tip("Générez les décors depuis votre scénario (Scénario → Claude IA → Générer les décors). Claude identifie tous les lieux INT./EXT. et crée les fiches correspondantes."),
    ])


def _s_accessories() -> str:
    return "".join([
        _h("Accessoires — Props & matériel", 1),
        _p("La page Accessoires liste tous les props, équipements et matériels nécessaires au tournage, avec leurs références visuelles et informations logistiques."),
        _sep_html(),
        _h("Créer un accessoire"),
        _ul(
            "Cliquez sur <b>✦ Créer un accessoire</b>",
            "Remplissez : nom, description précise, quantité nécessaire",
            "Ajoutez des <b>images de référence</b> pour guider les achats et la régie",
            "Notez le budget estimé, le fournisseur ou la disponibilité",
        ),
        _h("Utilisation en production"),
        _ul(
            "Assignez les accessoires aux plans du storyboard pour un suivi précis",
            "La liste des accessoires par plan aide la régie à préparer chaque journée de tournage",
            "Les accessoires peuvent aussi être assignés aux personnages (qui porte quoi)",
        ),
        _tip("Générez la liste d'accessoires depuis votre scénario (Scénario → Claude IA → Générer les accessoires). Claude analyse le script et identifie tous les objets mentionnés."),
    ])


def _s_hmc() -> str:
    return "".join([
        _h("HMC — Habillage, Maquillage, Coiffure", 1),
        _p("La page HMC centralise toutes les informations de costumes, maquillage et coiffure pour chaque personnage et chaque scène, avec les références visuelles nécessaires aux équipes artistiques."),
        _sep_html(),
        _h("Catégories HMC"),
        _ul(
            "<b>Habillage</b> — costumes complets, tenues spécifiques, chaussures, accessoires vestimentaires",
            "<b>Maquillage</b> — maquillage de base, effets, vieillissement, blessures, effets spéciaux",
            "<b>Coiffure</b> — coupes, couleurs, coiffages, perruques, extensions, postiches",
            "<b>Effets spéciaux</b> — prothèses, latex, effets de blessures, transformations",
        ),
        _h("Créer une fiche HMC"),
        _ul(
            "Cliquez sur <b>✦ Créer un élément HMC</b>",
            "Associez la fiche à un personnage du casting",
            "Décrivez le look avec précision pour guider les cheffes costumière et maquilleuse",
            "Ajoutez des images de référence : Pinterest, photos de tournages similaires, lookbooks",
            "Précisez les contraintes : allergies, temps de mise en place, entretien",
        ),
        _tip("Générez automatiquement les fiches HMC depuis votre scénario (Scénario → Claude IA → Générer le HMC). Claude identifie les descriptions de costumes et de maquillage dans le script."),
    ])


def _s_vehicles() -> str:
    return "".join([
        _h("Véhicules — Parc automobile & transport", 1),
        _p("La page Véhicules liste tous les véhicules nécessaires au tournage : voitures de protagonistes, véhicules d'époque, motos, camions, engins spéciaux, etc."),
        _sep_html(),
        _h("Créer une fiche véhicule"),
        _ul(
            "Cliquez sur <b>✦ Créer un véhicule</b>",
            "Remplissez : type de véhicule, marque, modèle, année, couleur",
            "Notez les <b>modifications nécessaires</b> : peinture, immatriculation, équipements",
            "Indiquez les contraintes de disponibilité, location ou achat",
            "Ajoutez des images de référence pour faciliter la recherche",
        ),
        _h("Génération automatique"),
        _ul(
            "Depuis Scénario → Claude IA → <b>Générer les véhicules</b>",
            "Claude identifie tous les véhicules mentionnés dans le script",
            "Les fiches sont pré-remplies avec les informations disponibles dans le texte",
        ),
    ])


def _s_camera() -> str:
    return "".join([
        _h("Image & Son — Caméra et optique", 1),
        _p("La page Image & Son permet de configurer les préférences de caméra, d'optique et de son pour votre film. Ces paramètres influencent les suggestions de plans dans le storyboard et enrichissent les prompts Seedance 2.0."),
        _sep_html(),
        _h("Corps de caméra"),
        _ul(
            "Sélectionnez la caméra principale de votre film (ARRI Alexa, RED, Sony FX3, Canon EOS, Blackmagic…)",
            "Ce choix contextualise les suggestions de valeurs de plan et de focales",
            "Il est intégré dans les prompts vidéo Seedance pour un rendu cinématographique cohérent",
        ),
        _h("Optiques disponibles"),
        _ul(
            "Configurez votre kit optique : focales fixes (primes) et zooms disponibles",
            "Ces données servent à suggérer des focales adaptées dans chaque plan du storyboard",
            "Exemples : 24mm (grand angle), 35mm (reportage), 50mm (standard), 85mm (portrait), 135mm (télé)",
        ),
        _h("Paramètres son"),
        _ul(
            "Notez le type de microphone principal : perche, lavalier HF, micro canon",
            "Ces informations sont accessibles dans les fiches de plans (champ Micro)",
            "Utile pour les briefs avec les preneurs de son",
        ),
        _tip("Les préférences caméra sont sauvegardées par projet. Vous pouvez avoir des configurations différentes pour chaque film."),
    ])


def _s_seedance() -> str:
    return "".join([
        _h("Studio IA — Génération vidéo, son et upscaling", 1),
        _p("Le Studio IA regroupe toute la production en <b>7 onglets</b> : "
           "<b>Générer depuis Storyboard</b> · <b>Modifier des clips</b> · <b>Génération directe</b> · "
           "<b>Sound Design</b> · <b>Upscaling</b> · <b>Vidéothèque</b> · <b>Historique</b>. "
           "Le moteur principal est <b>Seedance 2.0</b> (ByteDance, via fal.ai) — marqué "
           "<b>« recommandé »</b> dans le sélecteur de moteurs : c'est lui qui donne les meilleurs "
           "résultats sur le workflow storyboard. Le bouton de génération s'appelle partout "
           "<b>▶▶ Lancer la file d'attente</b>, et <b>Ouvrir le dossier</b> est toujours actif, "
           "même avant la première génération."),
        _sep_html(),
        _h("Les 4 modes de génération"),
        _ul(
            "<b>Text-to-Video (T2V)</b> — génère une vidéo depuis un prompt texte uniquement",
            "<b>Image-to-Video (I2V)</b> — anime une image statique selon un prompt de mouvement",
            "<b>Extension de clip</b> — prolonge une vidéo existante de manière naturelle",
            "<b>Référence multimodale</b> — génère depuis plusieurs images de référence combinées",
        ),
        _sep_html(),
        _h("Text-to-Video (T2V)"),
        _ul(
            "Entrez votre prompt en <b>français</b> — PANDORA le traduit automatiquement en anglais via Claude Haiku",
            "Choisissez la résolution (480p, 720p, 1080p) et la durée (jusqu'à 10 secondes)",
            "Cliquez <b>✦ Générer</b> pour lancer la génération",
            "La progression s'affiche en temps réel (0% → 100%)",
            "La vidéo générée est automatiquement sauvegardée dans le dossier du projet",
        ),
        _h("Image-to-Video (I2V)"),
        _ul(
            "Importez une image de départ (PNG, JPG, WEBP — jusqu'à 10 Mo)",
            "Écrivez un prompt décrivant le mouvement souhaité (lent zoom avant, panoramique droite…)",
            "Seedance 2.0 anime l'image selon votre description",
            "Idéal pour animer des portraits de personnages, des moodboards ou des concepts arts",
        ),
        _h("Extension de clip"),
        _ul(
            "Importez une vidéo existante (générée ou externe)",
            "Seedance 2.0 génère une continuation naturelle du mouvement et de l'action",
            "Utile pour allonger des plans générés ou créer des séquences continues",
        ),
        _h("Référence multimodale"),
        _ul(
            "Importez plusieurs images de référence : personnage, décor, ambiance, style",
            "Écrivez un prompt combinant ces références visuelles",
            "Seedance génère une vidéo cohérente intégrant toutes les références",
            "Idéal pour des scènes complexes avec personnage + décor + atmosphère définis",
        ),
        _sep_html(),
        _h("Lipsync natif — Dialogue dans les guillemets"),
        _ul(
            'Seedance 2.0 supporte la <b>synchronisation labiale native</b> en Text-to-Video',
            'Placez les dialogues entre guillemets doubles dans le prompt pour activer l\'audio et le lipsync :',
            '<code>A woman looks at the camera and says "Hello, welcome to our film."</code>',
            'PANDORA protège automatiquement les guillemets français « » pendant la traduction',
            'Durée recommandée : 5-10 s pour un court dialogue, 10-15 s pour un monologue',
        ),
        _sep_html(),
        _h("Moteur de génération — 8 moteurs disponibles"),
        _p("Dans les onglets <b>Générer depuis Storyboard</b> et <b>Modifier des clips</b>, "
           "le menu <b>Moteur de génération</b> donne accès aux moteurs vidéo IA compatibles. "
           "Chaque libellé affiche les capacités réellement utilisées par le workflow "
           "(<i>raccord i2v · réfs</i>) et <b>Seedance 2.0 est marqué « recommandé »</b> — "
           "les autres moteurs ne donnent pas encore d'aussi bons résultats. "
           "Le moteur sélectionné s'applique à toute la file d'attente."),
        _ul(
            "<b>Seedance 2.0</b> (ByteDance) — T2V + I2V + Extension · jusqu'à 15 s · lipsync · <i>par défaut · n°2 ELO</i> · $0.02-0.06/s",
            "<b>Happy Horse 1.0</b> (Alibaba) — T2V + I2V · 720p/1080p · <i>n°1 ELO Avril 2026</i> · $0.14-0.28/s",
            "<b>Kling v3 Pro</b> (Kwai) — T2V + I2V · 1080p · audio natif · <i>n°3 ELO</i> · $0.112-0.196/s",
            "<b>Kling O3 4K</b> — T2V + I2V · résolution 4K · ~$0.42/s",
            "<b>Veo 3.1</b> (Google) — T2V · 1080p · audio natif · ~$1.00/vidéo",
            "<b>Sora 2</b> (OpenAI) — T2V · 1080p · durée fixe · ~$0.40/vidéo",
            "<b>PixVerse v6</b> — T2V · 360p à 1080p · $0.025-0.115/s · économique",
            "<b>Seedance 2.0 Fast</b> — Version rapide · économique · $0.09/s",
        ),
        _tip("Seedance 2.0 est le moteur par défaut — le plus optimisé dans Pandora (références, lipsync, storyboard). "
             "Classement ELO vidéo Avril 2026. "
             "La résolution et le ratio se règlent automatiquement selon le moteur choisi. "
             "Kling O3 4K passe automatiquement en 4K ; Veo 3.1 et Sora 2 verrouillent le 1080p."),
        _p("L'onglet <b>Génération directe</b> donne accès à ces 8 moteurs avec des formulaires "
           "dédiés (image de départ, paramètres avancés…) sans intégration storyboard."),
        _sep_html(),
        _h("Bascule automatique T2V → Référence"),
        _p("Dans l'onglet <b>Générer depuis Storyboard</b>, si des références visuelles sont disponibles (personnages, décors, accessoires assignés au plan), PANDORA bascule automatiquement de <i>text-to-video</i> vers <i>reference-to-video</i> — sans aucune action de votre part."),
        _ul(
            "Slot 1 : mosaïque des <b>portraits des personnages</b> assignés au plan",
            "Slot 2 : <b>image du décor</b> assigné au plan",
            "Slot 3 : mosaïque <b>accessoires + véhicules</b> assignés au plan",
            "La bascule est silencieuse — le mode affiché reste T2V mais le mode réel est Référence",
            "Plus les fiches (casting, décors, accessoires) sont complètes, plus les générations sont cohérentes",
        ),
        _tip("Pour que la bascule fonctionne, assignez des personnages, décors et accessoires à chaque plan du storyboard. Sans assignation, aucune référence n'est envoyée et Seedance reste en T2V pur."),
        _sep_html(),
        _h("Mode Mock vs Mode Réel"),
        _ul(
            "<b>Mode Mock</b> (sans clé fal.ai) — simulation locale avec barre de progression animée. Génère un placeholder vidéo. Parfait pour tester le workflow sans frais.",
            "<b>Mode Réel</b> (avec clé fal.ai) — vrai appel à l'API Seedance 2.0. Génération vidéo réelle. Facturation selon votre usage sur fal.ai.",
        ),
        _warn("Sans clé API fal.ai dans Paramètres, toutes les générations Seedance fonctionnent en mode mock. Les vidéos placeholder ne sont pas sauvegardées."),
        _sep_html(),
        _h("Historique des générations"),
        _ul(
            "Les 50 dernières générations réelles sont conservées dans l'historique",
            "Accédez à toutes les vidéos depuis l'onglet <b>Historique</b> du Studio IA",
            "Les vidéos sont stockées dans <code>data/Seedance/</code> du dossier projet",
        ),
        _tip("Les prompts sont automatiquement traduits en anglais avant envoi à Seedance 2.0. Rédigez vos prompts en français — la traduction est transparente et optimisée."),
        _sep_html(),
        _h("Sound Design — Mirelo SFX (nouveau)"),
        _p("L'onglet <b>Sound Design</b> sonorise vos plans via Mirelo SFX 1.6 (~$0.01/s) :"),
        _ul(
            "<b>Prompt → SFX</b> — décrivez l'ambiance ou les effets sonores (en anglais de "
            "préférence) et obtenez un fichier audio prêt pour la timeline",
            "<b>Vidéo → bande-son</b> — donnez un clip vidéo : Mirelo génère une bande-son "
            "<b>synchronisée sur l'image</b> (prompt optionnel pour orienter le style)",
            "Les fichiers générés sont listés en bas de l'onglet avec un bouton <b>Lire</b>",
            "<b>Ouvrir le dossier</b> ouvre la destination (<code>data/sound_design/</code>), "
            "même avant la première génération",
        ),
        _sep_html(),
        _h("Upscaling — Topaz / SeedVR2 (nouveau)"),
        _p("L'onglet <b>Upscaling</b> monte vos clips en résolution, en lot :"),
        _ul(
            "<b>Ajouter des clips</b> ou <b>⇪ Importer la Vidéothèque</b> remplit la file "
            "d'attente — affichée en <b>petits carrés</b> avec vignettes (clic droit = retirer)",
            "Choisissez le moteur (<b>Topaz Video</b> qualité max, <b>SeedVR2</b> rapide) "
            "et le facteur <b>×2</b> (480p→~1080p) ou <b>×4</b> (480p→~4K)",
            "<b>▶▶ Lancer la file d'attente</b> traite tous les clips, un par un — "
            "annulable à tout moment (les clips restants sont conservés)",
            "La sortie garde le <b>même nom que la source</b> : dans DaVinci, un simple "
            "<b>Relink Media</b> remplace vos clips par la version haute résolution",
        ),
        _tip("Workflow économique : générez tout en 480p (rapide et peu cher), montez le film, "
             "puis upscalez uniquement les plans retenus en ×2 ou ×4."),
        _sep_html(),
        _h("Modifier des clips — Génération batch"),
        _p("L'onglet <b>Modifier des clips</b> permet de transformer en masse des clips de votre timeline DaVinci avec Seedance 2.0. Chaque clip est uploadé comme référence vidéo et Seedance génère une version modifiée selon votre prompt."),
        _ul(
            "<b>1.</b> Dans DaVinci : clic droit sur un clip → <b>Flag</b> → couleur pour le sélectionner "
            "(sans flag = toute la timeline est envoyée)",
            "<b>2.</b> DaVinci → <b>Espace de travail → Scripts → pandora_send</b> "
            "(ou votre raccourci clavier personnalisé)",
            "<b>3.</b> PANDORA affiche les clips reçus dans l'onglet <b>Modifier des clips</b>",
            "<b>4.</b> Écrivez un <b>prompt global</b> (même prompt pour tous les clips) "
            "ou un <b>prompt par clip</b> (cliquez sur chaque vignette pour le personnaliser)",
            "<b>5.</b> Cliquez <b>▶▶ Lancer la file d'attente</b> — traitement séquentiel, 1 clip à la fois",
            "Les vidéos générées sont importées automatiquement dans le <b>Media Pool de DaVinci</b>",
            "Utilisez le spinbox <b>×N</b> pour générer plusieurs prises par clip",
        ),
        _warn(
            "Format requis par Seedance 2.0 pour les clips de référence : "
            "<b>720p maximum · moins de 50 MB · H.264 MP4 ou MOV</b>. "
            "Depuis DaVinci : Fichier → Exporter → sélectionner H.264 Master à 720p "
            "avant d'envoyer vos clips via pandora_send."
        ),
        _h("ADN visuel — Seed Lock"),
        _ul(
            "<b>🔒 ADN visuel — garder pour tous les plans</b> : verrouille le seed Seedance "
            "pour maintenir la cohérence visuelle entre tous les clips de la file d'attente",
            "Activé <b>automatiquement</b> quand plusieurs clips sont cochés",
            "Chaque clip modifié utilise le même seed → style et palette cohérents malgré des angles différents",
            "Décochez si vous souhaitez une variation aléatoire par clip",
        ),
        _h("Bridge DaVinci"),
        _ul(
            "Le bridge est nécessaire pour l'<b>import automatique dans le Media Pool</b>",
            "Si le bridge n'est pas connecté, PANDORA propose : "
            "<i>Fermer</i> / <i>↻ Vérifier la connexion</i> / <i>Générer sans import</i>",
            "Pour connecter : DaVinci Resolve → Espace de travail → Scripts → <b>seedance_bridge</b>",
            "Laissez la fenêtre PANDORA Bridge ouverte pendant toute votre session",
        ),
        _tip(
            "Prompt efficace pour la modification : soyez précis sur ce que vous voulez <i>garder</i> "
            "et ce que vous voulez <i>changer</i>. Ex : "
            "<i>« same scene, same characters and camera movement, replace background with a luxury restaurant, "
            "keep lighting mood »</i>"
        ),
    ])


def _table_row(cols: list[str], header: bool = False) -> str:
    color = CP["text_primary"] if header else CP["text_secondary"]
    bg    = CP["bg3"] if header else "transparent"
    tds   = "".join(
        f'<td style="padding:5px 10px;border:1px solid {CP["border"]};">'
        f'<span style="color:{color};font-size:11px;font-family:\'Consolas\',monospace;">'
        f'{c}</span></td>'
        for c in cols
    )
    return f'<tr style="background:{bg};">{tds}</tr>'


def _s_doublage() -> str:
    return "".join([
        _h("Doublage — Synthèse vocale & outils audio IA", 1),
        _sep_html(),
        _h("Synthèse vocale — Kokoro TTS"),
        _p("La page Doublage propose une synthèse vocale IA de haute qualité via Kokoro TTS (fal.ai). Générez des voix naturelles pour vos dialogues, narrations ou animatiques."),
        _ul(
            "<b>10+ langues</b> : anglais US/GB, espagnol, portugais, italien, japonais, mandarin",
            "<b>30+ voix</b> différentes classées par genre et langue",
            "<b>Vitesse réglable</b> : de 0.5× (ralenti) à 2.0× (accéléré)",
            "Les fichiers WAV sont sauvegardés dans <code>data/doublage/audio/</code>",
            "Tarif : <b>$0.02 / 1 000 caractères</b>",
        ),
        _h("Suppression de fond — BiRefNet"),
        _p("BiRefNet supprime automatiquement le fond d'une image et exporte un PNG avec canal alpha transparent. Idéal pour isoler des personnages ou des éléments de décor."),
        _ul(
            "Import : PNG, JPG, JPEG, WEBP, BMP",
            "Export : PNG avec transparence (fond supprimé)",
            "Résultat sauvegardé dans le même dossier que l'image source",
            "Tarif : au calcul GPU (quelques centimes par image)",
        ),
        _h("Lipsync natif — Seedance T2V"),
        _ul(
            'Placez les dialogues entre guillemets dans le prompt Seedance T2V pour activer le lipsync',
            '<code>A character says "Welcome to our world."</code>',
            "Seedance génère automatiquement l'audio synchronisé avec le mouvement des lèvres",
        ),
        _tip("La page Doublage sera enrichie dans une prochaine version avec des fonctionnalités supplémentaires de lip sync et de traitement audio avancé."),
    ])


def _s_tarifs() -> str:
    table_image = "".join([
        '<table style="border-collapse:collapse;width:100%;margin:10px 0 16px 0;">',
        _table_row(["Modèle", "Technologie", "Usage", "Prix"], header=True),
        _table_row(["Nano Banana 2", "Gemini 3.1 Flash", "Portraits, décors, HMC, accessoires", "$0.08 / image"]),
        _table_row(["Nano Banana Pro", "Gemini 3 Pro", "Portraits haute qualité", "$0.15 / image"]),
        _table_row(["Flux Schnell", "Black Forest Labs", "Sketches storyboard ultra-rapides", "~$0.003 / image"]),
        _table_row(["GPT Image 2", "OpenAI", "Images avec texte (logos, panneaux)", "~$0.21 / image"]),
        "</table>",
    ])
    table_video = "".join([
        '<table style="border-collapse:collapse;width:100%;margin:10px 0 16px 0;">',
        _table_row(["Moteur (ELO Avr. 2026)", "Mode", "Résolution", "Audio natif", "Prix"], header=True),
        _table_row(["Seedance 2.0 ★ (défaut)", "T2V + I2V + Extension", "jusqu'à 1080p", "✓ (lipsync)", "$0.02-0.06/s"]),
        _table_row(["#1 Happy Horse 1.0", "T2V + I2V", "720p / 1080p", "✗", "$0.14-0.28/s"]),
        _table_row(["#3 Kling v3 Pro", "T2V + I2V", "1080p", "✓", "$0.112-0.196/s"]),
        _table_row(["Kling O3 4K", "T2V + I2V", "4K", "✗", "~$0.42/s"]),
        _table_row(["Veo 3.1", "T2V", "1080p", "✓", "~$1.00/vidéo"]),
        _table_row(["Sora 2", "T2V", "1080p", "✗", "~$0.40/vidéo"]),
        _table_row(["PixVerse v6", "T2V", "360p → 1080p", "✗", "$0.025-0.115/s"]),
        _table_row(["Seedance 2.0 Fast", "T2V", "jusqu'à 720p", "✓", "~$0.09/s"]),
        "</table>",
    ])
    table_audio = "".join([
        '<table style="border-collapse:collapse;width:100%;margin:10px 0 16px 0;">',
        _table_row(["Service", "Technologie", "Langues", "Prix"], header=True),
        _table_row(["Kokoro TTS", "fal-ai/kokoro", "EN, ES, PT, IT, JA, ZH", "$0.02 / 1 000 car."]),
        _table_row(["BiRefNet", "fal-ai/birefnet", "—", "Au calcul"]),
        "</table>",
    ])
    return "".join([
        _h("Tarifs IA — Comparatif des coûts", 1),
        _p("Tous les tarifs sont en <b>USD</b> et basés sur l'usage réel sur fal.ai. En mode mock (sans clé), aucune facturation n'a lieu."),
        _sep_html(),
        _h("Génération d'images"),
        table_image,
        _h("Génération vidéo"),
        table_video,
        _h("Audio & Utilitaires"),
        table_audio,
        _tip("Tous les tarifs sont indicatifs et peuvent évoluer. Consultez fal.ai pour les tarifs en vigueur."),
        _warn("En mode mock (sans clé fal.ai), aucune facturation n'a lieu. Ajoutez votre clé dans Paramètres pour les générations réelles."),
    ])


def _s_style() -> str:
    return "".join([
        _h("Style visuel — Univers cinématographique", 1),
        _p("Le style visuel définit l'esthétique globale de votre film. Il influence la génération de portraits (Nano Banana), de décors, d'accessoires et de vidéos (Seedance 2.0) pour une cohérence visuelle complète."),
        _sep_html(),
        _h("Accéder au style visuel"),
        _ul(
            "Depuis l'<b>éditeur de Scénario</b> — combo déroulant dans la barre du haut, à côté des boutons de versions (✚ ✕)",
            "Depuis la page <b>Style visuel</b> dans la barre de navigation — vue complète avec toutes les cartes",
        ),
        _h("20 styles organisés en 4 catégories"),
        _ul(
            "<b>🎬 Cinéma</b> — Film réaliste, Documentaire, Drame social, Film noir, Thriller, Horreur, Western, Film de guerre, Film d'action, Comédie musicale, Comédie romantique, Science-fiction, Fantasy, Publicité luxe",
            "<b>✏ Animation</b> — Animation 3D (CGI), Dessin animé 2D, Anime japonais",
            "<b>🎨 Arts & Esthétiques</b> — Cyberpunk néon, Lo-fi rétro (Super 8), Aquarelle, Peinture à l'huile, BD franco-belge (Moebius)",
            "<b>∞ Hybride</b> — Multi-style (fusion créative personnalisée)",
        ),
        _h("Description libre du style"),
        _ul(
            "Disponible en bas de la page Style visuel",
            "Permet de préciser ou personnaliser le style sélectionné",
            "Exemple : <i>« Mélange de prises de vue réelles et d'effets d'animation 2D, style Roger Rabbit »</i>",
            "Cette description est ajoutée aux prompts de génération pour plus de précision",
        ),
        _h("Impact sur les générations"),
        _ul(
            "<b>Portraits Nano Banana</b> — le style est intégré à l'image générée",
            "<b>Vidéos Seedance 2.0</b> — un suffix vidéo correspondant est ajouté automatiquement à chaque prompt",
            "<b>Décors et accessoires</b> — le rendu visuel suit l'esthétique choisie",
        ),
        _h("Images de référence par style"),
        _ul(
            "Chaque style peut avoir des <b>images de référence</b> qui sont envoyées à Seedance avec chaque génération",
            "Dans la galerie de styles, cliquez sur <b>+ Ajouter une image</b> pour importer vos propres références",
            "Les références importées sont sauvegardées dans <code>%LOCALAPPDATA%\\PANDORA\\assets\\style_refs\\</code>",
            "Elles complètent les références visuelles intégrées — plus la référence est précise, plus le rendu est cohérent",
        ),
        _tip("Choisissez votre style <b>avant</b> de générer quoi que ce soit. Il se propage automatiquement à toutes les pages et s'applique à toutes les nouvelles générations."),
    ])


def _s_settings() -> str:
    return "".join([
        _h("Paramètres — Configuration de PANDORA", 1),
        _p("La page Paramètres centralise toutes les clés API, les préférences de sortie et la configuration de l'intégration DaVinci Resolve."),
        _sep_html(),
        _h("Clé API fal.ai — Seedance 2.0"),
        _ul(
            "Créez un compte sur <b>fal.ai</b>",
            "Allez dans votre espace personnel → API Keys → Create new key",
            "Copiez la clé générée et collez-la dans le champ <b>Clé fal.ai</b>",
            "Cliquez <b>Enregistrer</b>",
            "Sans cette clé : mode mock (simulation locale, aucune vidéo réelle générée)",
        ),
        _h("Clé API Anthropic — Claude IA"),
        _ul(
            "Créez un compte sur <b>console.anthropic.com</b>",
            "API Keys → Create Key — donnez-lui un nom",
            "Collez la clé dans le champ <b>Clé Anthropic</b>",
            "Sans cette clé : toutes les fonctions Claude IA sont désactivées (formatage scénario, arrangement, génération storyboard, extraction d'éléments)",
        ),
        _h("Clé API Nano Banana — Portraits IA"),
        _ul(
            "Créez un compte sur la plateforme Nano Banana",
            "Récupérez votre clé API dans votre espace personnel",
            "Collez-la dans le champ <b>Clé Nano Banana</b>",
            "Sans cette clé : portraits en mode mock (images placeholder colorées)",
        ),
        _h("DaVinci Resolve — Connexion bridge"),
        _ul(
            "Cliquez sur <b>Installer bridge</b> pour copier le script dans le dossier Scripts de DaVinci",
            "Ouvrez DaVinci Resolve avec un projet chargé",
            "Dans DaVinci : <b>Espace de travail → Scripts → seedance_bridge</b>",
            "Le script lance un serveur TCP local (port 19876)",
            "Cliquez sur <b>Connecter</b> dans PANDORA — le voyant passe au vert ●",
        ),
        _warn("Si Claude ne répond pas, <b>désactivez votre VPN</b> — certains serveurs VPN sont bloqués par l'API Anthropic."),
        _warn("Le scripting Python de DaVinci (import Media Pool, lecture timeline) est réservé à <b>DaVinci Resolve Studio</b> (version payante). La version gratuite ne supporte pas ces fonctions."),
        _h("Dossier de sortie"),
        _ul(
            "Par défaut, les vidéos sont sauvegardées dans <code>data/Seedance/</code> du projet en cours",
            "Configurez un dossier de sortie alternatif si nécessaire",
        ),
    ])


def _s_shortcuts() -> str:
    return "".join([
        _h("Raccourcis & Astuces", 1),
        _sep_html(),
        _h("Raccourcis clavier"),
        _ul(
            f"{_kbd('Ctrl+Z')} — Annuler dans l'éditeur scénario (historique manuel)",
            f"{_kbd('Ctrl+Y')} — Rétablir dans l'éditeur scénario",
            f"{_kbd('Ctrl+S')} — Sauvegarder le scénario en cours (depuis l'éditeur)",
        ),
        _sep_html(),
        _h("Astuces pour de meilleurs prompts Seedance"),
        _ul(
            "Soyez <b>précis sur la mise en scène</b> : caméra, lumière, angle, décor",
            "Évitez les dialogues dans les prompts T2V — Seedance génère de l'image, pas du son synchronisé",
            "Mentionnez le style filmique : <i>cinematic, shot on ARRI, handheld camera</i>",
            "Pour I2V, décrivez le mouvement : <i>slowly zooms in, pans left, dolly forward</i>",
            "Gardez les prompts entre <b>50 et 150 mots</b> pour un résultat optimal",
            "Évitez les listes — rédigez des phrases fluides et descriptives",
        ),
        _h("Astuces pour le storyboard"),
        _ul(
            "Générez d'abord le storyboard complet avec Claude, puis affinez plan par plan",
            "Utilisez les champs Mise en scène (axe, placements) pour les briefs d'équipe",
            "Les champs IN/OUT facilitent la continuité et le raccord entre les plans",
            "La <b>valeur de plan</b> (gros plan, plan large…) influence directement le prompt Seedance généré",
            "Assignez les décors à chaque plan — ils enrichissent les prompts automatiquement",
        ),
        _h("Astuces pour les portraits"),
        _ul(
            "Décrivez avec précision : <b>âge, traits physiques, couleur de peau, couleur des yeux, type de coiffure</b>",
            "Précisez l'expression souhaitée : souriant, sérieux, mélancolique, intense",
            "Mentionnez le style de portrait : photo de casting professionnelle, portrait cinématographique",
            "Générez 3-4 variantes — la diversité de propositions permet de trouver la meilleure",
        ),
        _h("Workflow optimisé"),
        _ul(
            "Commencez toujours par rédiger un scénario, même partiel — toutes les autres pages s'alimentent depuis lui",
            "Choisissez le style visuel <b>tôt</b> — il influence l'ensemble des générations IA",
            "Laissez Claude générer automatiquement les éléments, puis affinez chaque fiche manuellement",
            "Générez les Moods (prompts Seedance) du storyboard <b>avant</b> de lancer les vidéos",
            "Utilisez les versions du scénario pour conserver des alternatives sans rien effacer",
        ),
        _tip("PANDORA est conçu pour un travail <b>itératif</b>. Générez, affinez, régénérez. Chaque itération améliore la cohérence de votre projet."),
    ])


_BUILDERS = [
    _s_welcome, _s_projects,                                    # DÉMARRAGE
    _s_scenario, _s_storyboard, _s_castings, _s_decors,        # PRÉ-PRODUCTION
    _s_accessories, _s_hmc, _s_vehicles, _s_camera,
    _s_seedance, _s_style, _s_doublage, _s_tarifs,             # STUDIO IA
    _s_settings, _s_shortcuts,                                  # RÉFÉRENCE
]

_SECTIONS_EN = [
    # GET STARTED
    ("🎬", "Welcome to PANDORA"),
    ("📁", "Project management"),
    # PRE-PRODUCTION
    ("≡",  "Screenplay"),
    ("⊞",  "Storyboard"),
    ("⊕",  "Cast"),
    ("◻",  "Locations"),
    ("◈",  "Props"),
    ("✂",  "HMC"),
    ("🚗", "Vehicles"),
    ("◎",  "Camera & Sound"),
    # AI STUDIO
    ("✦",  "AI Studio"),
    ("🎨", "Visual style"),
    ("🎙", "Dubbing"),
    ("💰", "AI Pricing"),
    # REFERENCE
    ("⚙",  "Settings"),
    ("⌨",  "Shortcuts & Tips"),
]

_GROUPS_EN = [
    ("GET STARTED",    2),
    ("PRE-PRODUCTION", 8),
    ("AI STUDIO",      4),
    ("REFERENCE",      2),
]


def _e_welcome() -> str:
    return "".join([
        _h("Welcome to PANDORA", 1),
        _p("PANDORA is a cinema pre-production tool designed for directors, screenwriters and creative teams. It centralizes your entire pre-production workflow and lets you generate AI videos via <b>Seedance 2.0</b> by ByteDance, directly from the interface."),
        _sep_html(),
        _h("What PANDORA does"),
        _ul(
            "Write and apply <b>PANDORA layout</b> to your screenplay with <b>Claude AI</b> (Anthropic)",
            "Create a shot-by-shot storyboard with camera, actors, locations and prompts",
            "Manage your cast with <b>AI-generated portraits</b> (Nano Banana)",
            "Catalogue locations, props, HMC and vehicles needed for the shoot",
            "Define camera and lens preferences for the film",
            "Choose a <b>visual style</b> that influences all AI generations",
            "Generate AI videos: Seedance 2.0 (recommended), Kling, Happy Horse, PixVerse…",
            "Add sound to your shots with <b>Sound Design</b> (Mirelo SFX: prompt → SFX, video → soundtrack)",
            "Upscale your clips with <b>Upscaling</b> (Topaz / SeedVR2, ×2/×4)",
            "Automatically import videos into <b>DaVinci Resolve</b> (Studio required)",
        ),
        _sep_html(),
        _h("The new interface"),
        _p("Since the redesign, PANDORA is organized like DaVinci Resolve:"),
        _ul(
            "The <b>navigation bar</b> sits at the <b>bottom of the window</b> — page icons in the "
            "center, FR/EN flags on the left, <b>Settings</b> at the far right",
            "The <b>AI assistant</b> lives on the <b>left</b> side — the <b>IA</b> handle opens and closes it",
            "<b>☰ User manual</b> (red) and <b>✉ Contact us</b> (green) are at the <b>top left</b>",
            "Support Pandora, Updates and Save remain at the top right",
            "Pages use the <b>full width of the screen</b>; Settings and the AI Studio forms "
            "are centered for readability",
        ),
        _sep_html(),
        _h("Recommended workflow"),
        _ul(
            "<b>1.</b> Create or open a project from the Projects page",
            "<b>2.</b> Write your screenplay, apply PANDORA layout with Claude AI",
            "<b>3.</b> Choose a visual style from the screenplay editor",
            "<b>4.</b> Auto-generate characters, locations, HMC, props and vehicles from the screenplay",
            "<b>5.</b> Generate the storyboard with Claude AI, refine shot by shot",
            "<b>6.</b> Configure Seedance Moods for each shot",
            "<b>7.</b> Launch video generation from the storyboard or the AI Studio",
            "<b>8.</b> Add sound (Sound Design) and upscale (Upscaling) as needed",
        ),
        _tip("PANDORA works without any API key in <b>demo (mock) mode</b>: videos and portraits are simulated locally. Add your API keys in Settings for real generations."),
        _sep_html(),
        _h("Required API keys"),
        _ul(
            "<b>fal.ai</b> — Seedance 2.0 (video generation)",
            "<b>Anthropic</b> — Claude AI (screenplay, storyboard, element extraction)",
            "<b>Nano Banana</b> — AI character portrait generation",
        ),
    ])


def _e_projects() -> str:
    return "".join([
        _h("Project management", 1),
        _p("Each PANDORA project is a <b>folder</b> on your disk containing all the film's data: screenplay, storyboard, cast, locations, generated videos, etc."),
        _sep_html(),
        _h("Create a new project"),
        _ul(
            "Click <b>✦ New project</b> on the Projects page",
            "Choose a destination folder on your disk",
            "Give the project a name",
            "PANDORA automatically creates the required folder structure",
        ),
        _h("Open an existing project"),
        _ul(
            "Click <b>Open folder…</b> to browse to an existing project",
            "Or click directly on a project in the <b>Recent projects</b> list",
            "The current project is always shown at the top with the <b>CURRENT</b> badge",
        ),
        _h("Switch project"),
        _ul(
            "Go to the <b>Projects</b> page from the navigation bar at the bottom of the window",
            "Click on a recent project to switch to it",
            "PANDORA saves automatically before switching",
        ),
        _sep_html(),
        _h("Project structure"),
        _p("Each project stores its data in a <b>data/</b> subfolder created automatically:"),
        _ul(
            "<code>scenarios/</code> — Screenplays and their named versions",
            "<code>storyboard/</code> — Shots by storyboard version",
            "<code>castings/</code> — Characters and AI portraits",
            "<code>decors/</code> — Shooting locations and scouting images",
            "<code>accessories/</code> — Props with references",
            "<code>hmc/</code> — Costume, makeup, hair",
            "<code>vehicles/</code> — Production vehicles",
            "<code>Seedance/</code> — Videos generated by Seedance 2.0",
        ),
        _tip("Recent projects are remembered between sessions. If a folder is moved or deleted, PANDORA informs you and removes it from the list automatically."),
    ])


def _e_scenario() -> str:
    return "".join([
        _h("Screenplay", 1),
        _p("The Screenplay page is the heart of PANDORA. Write your script, structure it with Claude AI, enrich it with visual references, manage versions, and generate your entire pre-production from a single place."),
        _sep_html(),

        _h("The text editor"),
        _ul(
            "<b>Courier New 14pt</b> font — industry standard for screenplays",
            "Text is centred in a column, like a real printed screenplay page",
            "Saving is <b>automatic</b> 3 seconds after each change",
            "Click <b>← Back</b> to return to the screenplay list without losing your work",
        ),

        _h("Film style and duration (above the editor)"),
        _ul(
            "<b>Visual style</b> — influences all AI generations (portraits, locations, Seedance videos) — change at any time",
            "<b>Film duration</b> — estimated total project duration in minutes and seconds",
        ),

        _sep_html(),
        _h("☁ Visual references — Analyse with Claude"),
        _p("Import images into your writing session. Claude analyses them and enriches your screenplay descriptions by establishing visual correspondences."),
        _ul(
            "Click <b>☁ Analyse with Claude</b> in the right panel",
            "The image strip appears below — click <b>+</b> (always on the left) to add references: location photos, characters, moods, moodboards…",
            "Claude analyses the visual content: colours, textures, architecture, characters, lighting",
            "The analysis streams in real time in a preview window",
            "Click <b>☁ Enrich screenplay</b>: Claude compares the images with your screenplay, finds correspondences (e.g. samurai in image ↔ samurai in text), and enriches the matching descriptions precisely",
            "Unrecognised parts are not modified — enrichment is surgical",
        ),
        _tip("Add up to 10 images. The closer the images are to your actual characters and locations, the more precise and useful the enrichment will be for Seedance prompts."),

        _sep_html(),
        _h("≡ Format screenplay"),
        _p("Reformats your raw text into Pandora/Seedance layout — optimised for AI video generation, not for classic Hollywood format."),
        _ul(
            "Click <b>≡ Format screenplay</b> in the right panel",
            "Claude reformats your text:",
            "→ Scene headings: <code>INT. LOCATION — TIME</code> / <code>EXT. LOCATION — TIME</code>",
            "→ Sequence titles: <code>—— SEQUENCE 1 — TITLE ——</code>",
            "→ Character names in CAPS centred before dialogue",
            "→ Action descriptions enriched, visual and <b>promptable</b>: spatial, concrete, with movement and light",
            "→ Expressive transitions preserved (FADE TO BLACK, etc.)",
            "The result streams in real time in a preview window — click <b>↩ Replace text</b> to apply",
        ),
        _tip("Pandora format is not standard Hollywood. It is designed so that every action line can become an effective Seedance prompt: precise visual descriptions, concrete movements, detailed atmospheres."),

        _sep_html(),
        _h("⊞ Suggest arrangement"),
        _p("Claude analyses your screenplay structure and proposes targeted improvements. The analysis opens in a streaming window. Two paths available after analysis."),
        _ul(
            "Set the <b>intensity</b> (1 to 10) before launching:",
            "→ <b>1-2</b>: Spelling and punctuation corrections only",
            "→ <b>3-4</b>: Gentle restructuring, improved reading rhythm",
            "→ <b>5-6</b>: Standard reformulation, narrative consistency and dialogue",
            "→ <b>7-8</b>: Scene restructuring, developing or cutting scenes",
            "→ <b>9-10</b>: Deep rewrite — structure and content modified",
            "Click <b>⊞ Suggest arrangement</b> — the analysis streams in real time",
        ),
        _h("After analysis — two paths"),
        _ul(
            "<b>✓ Apply suggestions directly</b>: Claude rewrites the screenplay applying its suggestions. The result appears in a preview — click <b>↩ Update screenplay</b> to replace it.",
            "<b>☁ Co-writing session</b>: opens the Co-writing Studio for interactive iteration with Claude (see section below).",
        ),

        _sep_html(),
        _h("☁ Co-writing Studio — Session with Claude"),
        _p("An interactive dialogue space between you and Claude. Iterate on your screenplay with precise instructions, shot by shot or scene by scene."),
        _h("Interface"),
        _ul(
            "<b>Initial analysis</b> tab (left panel) — Claude's detailed suggestions",
            "<b>Revised screenplay</b> tab (left panel) — the co-written version, updated with each exchange",
            "<b>Dialogue</b> panel (right) — your instructions and Claude's responses as chat bubbles",
            f"Send with <b>Send ☁</b> button or {_kbd('Ctrl+↵')}",
        ),
        _h("Surgery, not rewriting"),
        _ul(
            "Claude only modifies <b>what you explicitly ask for</b>",
            "Everything else is copied <b>word for word</b> without any touch-up",
            "Example: <i>« Change only Marc's last line »</i> → only that line changes",
            "If the request is ambiguous, Claude asks a question before rewriting",
        ),
        _h("Version navigation"),
        _ul(
            "Each Claude response creates a version in the history",
            "<b>←</b> and <b>→</b> arrows above the revised screenplay to navigate (e.g. v 2/3)",
            "Go back, compare, go forward — non-destructive",
            "If you go back to v2 and send a new instruction, v3 is replaced",
        ),
        _h("Visual references in the session"),
        _ul(
            "Add images with the <b>+</b> button in the references strip (right panel)",
            "Images are attached to your next message only, then cleared automatically",
            "Claude analyses them and integrates their visual details <b>only in the parts you ask to modify</b>",
            "Maximum 4 images per message — remove with the <b>✕</b> button on each thumbnail",
        ),
        _h("Applying the result"),
        _ul(
            "Click <b>✓ Apply this screenplay to project</b> to replace the screenplay in the editor",
            "You can manually edit the Revised screenplay tab before applying",
            "A badge <i>Manual editing active</i> appears if you have modified the text by hand",
        ),

        _sep_html(),
        _h("↩ Undo / Redo"),
        _ul(
            "Each Claude modification creates an <b>automatic save point</b>",
            f"Button <b>↩</b> (or {_kbd('Ctrl+Z')}) to undo, <b>↪</b> (or {_kbd('Ctrl+Y')}) to redo",
            "History is kept throughout the session — go back as far as needed",
        ),

        _h("Named versions"),
        _ul(
            "Click <b>✚</b> to save a named version at any time",
            "Select a version from the dropdown to load it instantly",
            "Delete a version with the <b>✕</b> button",
            "Example: <i>Draft 1</i>, <i>After AI arrangement</i>, <i>Final version</i>",
        ),

        _sep_html(),
        _h("☁ Generate from screenplay — Auto-extraction"),
        _p("Once the screenplay is written and formatted, Claude automatically extracts all production elements and adds them to the corresponding pages:"),
        _ul(
            "<b>Generate characters</b> — identifies CAPS names and creates casting cards",
            "<b>Generate locations</b> — extracts all INT./EXT. locations in the script",
            "<b>Generate props</b> — lists props and equipment mentioned in action lines",
            "<b>Generate HMC</b> — identifies costume, makeup and hair descriptions",
            "<b>Generate vehicles</b> — lists vehicles needed for the shoot",
            "<b>Generate storyboard</b> — creates a complete shot-by-shot breakdown with camera, shot sizes and Seedance prompts",
        ),
        _tip("Format your screenplay with Claude <b>before</b> generating elements. A structured screenplay (INT./EXT., consistent CAPS character names) gives much better extractions."),
        _warn("If Claude does not respond or returns network errors, <b>disable your VPN</b> — some VPN servers are blocked by the Anthropic API."),
    ])


def _e_storyboard() -> str:
    return "".join([
        _h("Storyboard", 1),
        _p("The Storyboard lists all shots in chronological order. Each row represents a shot with its complete technical and artistic parameters — camera, elements, staging, video prompt."),
        _sep_html(),

        _h("Table columns"),
        _ul(
            "<b>Preview</b> — Flux T2I mood image (click to generate or pick one)",
            "<b>Seq</b> — sequence number and name",
            "<b>Shot</b> — shot number within the sequence",
            "<b>Action</b> — scene title / action description",
            "<b>Movement</b> — camera movement (Static, Tracking, Pan, Zoom, Drone…)",
            "<b>Size</b> — shot size (Close-up, Medium, American, Wide…)",
            "<b>Focal</b> — lens focal length in mm",
            "<b>Speed</b> — shooting speed (normal, slow motion ×0.5, time lapse…)",
            "<b>Location</b> — assigned shooting location",
            "<b>Time</b> — time of day (Day, Night, Dawn, Dusk, Golden hour…)",
            "<b>Props</b> — props used in this shot",
            "<b>Actors</b> — characters present in frame",
            "<b>Axis</b> — camera angle (Face, 3/4, Lateral 90°, Back, High angle, Low angle)",
            "<b>Duration</b> — planned shot duration in seconds (2 to 15 s)",
            "<b>Prompt</b> — Seedance 2.0 prompt for video generation",
        ),

        _h("Edit a shot"),
        _ul(
            "Click directly on <b>any cell</b> to edit inline",
            "Click <b>Edit</b> on the right of a row to open the full shot card",
            "The card gives access to all fields: CAMERA, ELEMENTS, STAGING, DURATION, COMMENTS, PROMPT",
            "Drag the <b>⠿</b> grip on the left of a shot to reorder the breakdown",
        ),

        _h("Staging fields"),
        _ul(
            "<b>Camera axis</b> — Face / 3/4 / Lateral 90° / Back / High angle / Low angle",
            "<b>Camera placement</b> — free description of positioning (height, distance, support)",
            "<b>Actor placement</b> — where actors are placed in frame",
            "<b>Entry (IN)</b> — characters entering the shot (for continuity)",
            "<b>Exit (OUT)</b> — characters leaving the shot",
            "<b>Mic</b> — microphone placement for this shot",
        ),

        _sep_html(),
        _h("Preview — Mood image per shot"),
        _p("Each shot can have a <b>mood image</b> generated via Flux T2I — a quick visualisation of the atmosphere before launching the Seedance video."),
        _ul(
            "Click the <b>Preview</b> cell of a shot to open the mood dialogue",
            "Enter a free prompt or use the existing Seedance prompt for the shot",
            "Click <b>Generate</b> — Flux Schnell produces several proposals quickly",
            "Select the image that matches your vision — it appears as a thumbnail in the table",
            "Regenerate as many times as needed — Flux is very economical (~$0.003 / image)",
        ),
        _tip("Generate moods <b>before</b> launching Seedance videos: visualise the atmosphere of each shot and refine prompts without video costs."),

        _sep_html(),
        _h("✦ Generate Seedance Moods — Auto prompts"),
        _ul(
            "Click <b>✦ Generate Moods</b> in the storyboard toolbar",
            "Claude analyses each shot (size, movement, characters, location, time) and writes an optimised Seedance prompt",
            "Prompts integrate the selected <b>visual style</b> and <b>camera preferences</b> (focal length, camera body)",
            "Regenerate the prompt for a single shot from its edit card without affecting others",
        ),

        _h("▶ Generate a video from a shot"),
        _ul(
            "Click <b>▶ Generate</b> on the right of a shot to launch Seedance directly",
            "The video is generated with: shot prompt + visual style + reference mosaics (characters, location, props)",
            "Once done, the video appears as a thumbnail in the Preview column",
            "Click the thumbnail to open, copy or import it into DaVinci Resolve",
        ),

        _sep_html(),
        _h("Storyboard versions"),
        _ul(
            "Manage multiple versions: main breakdown, short version, editing alternatives…",
            "Dropdown at the top: create, load and delete named versions",
            "Deleting the <b>last version</b> is protected — at least one version must always exist",
        ),

        _tip("Generate the complete storyboard from the Screenplay page first (Claude AI → Generate storyboard), then refine shot by shot. The auto-generation creates a coherent breakdown that you then polish."),
    ])


def _e_castings() -> str:
    return "".join([
        _h("Cast — Film characters", 1),
        _p("The Cast page centralises all characters with their physical and psychological characteristics, AI portraits and visual references. Portraits are automatically used as visual references in Seedance generations — the central mechanism for visual consistency between shots."),
        _sep_html(),

        _h("Create a character"),
        _ul(
            "Click <b>✦ Create a character</b>",
            "Fill in: name (in CAPS as it appears in the screenplay), role in the story, approximate age",
            "Describe the <b>physical appearance</b>: height, build, skin tone, eye colour, hair type, distinctive features",
            "Describe the <b>psychology</b>: personality traits, motivations, character arcs, contradictions",
            "Add casting notes: actor type sought, references to known actors",
        ),

        _sep_html(),
        _h("Generate an AI portrait (Nano Banana)"),
        _ul(
            "Open a character card and click <b>Generate portrait</b>",
            "Choose the <b>visual style</b> from the dropdown (Realistic film, Anime, Cyberpunk…) — it applies to the portrait render",
            "Nano Banana generates the portrait from the physical description + selected style",
            "Several portraits are proposed — select the one matching your vision",
            "The selected portrait becomes the character's <b>official visual reference</b>",
            "Click <b>Generate a variation</b> to regenerate without changing parameters",
            "Regenerate as many times as needed — each generation produces different variants",
        ),
        _warn("Portrait generation requires a Nano Banana API key in Settings. Without a key, mock mode generates coloured placeholder images."),

        _sep_html(),
        _h("Impact on Seedance video generation"),
        _p("Portraits are automatically injected as visual references into Seedance 2.0 — the character keeps the same face and visual style from shot to shot."),
        _ul(
            "When you launch a T2V generation from the storyboard:",
            "→ <b>Reference slot 1</b>: mosaic of portraits of characters assigned to the shot",
            "→ <b>Reference slot 2</b>: image of the location assigned to the shot",
            "→ <b>Reference slot 3</b>: mosaic of props and vehicles assigned",
            "These references automatically switch Seedance from <i>text-to-video</i> to <i>reference-to-video</i>",
            "The more precise your portraits, the stronger the visual consistency between shots",
        ),
        _tip("Assign characters to each storyboard shot (shot card → ELEMENTS → Actors field). Without assignment, portraits are not sent to Seedance and visual consistency is not guaranteed."),

        _h("Assignment to storyboard shots"),
        _ul(
            "From the shot edit card → ELEMENTS section → <b>Actors</b> field",
            "Select the characters present in frame",
            "Their portraits are included in the Seedance reference mosaic for that shot",
            "Claude references their exact names during storyboard generation and arrangement",
        ),
    ])


def _e_decors() -> str:
    return "".join([
        _h("Locations — Shooting locations", 1),
        _p("The Locations page centralises all shooting locations with their technical, artistic and logistical characteristics."),
        _sep_html(),
        _h("Create a location"),
        _ul(
            "Click <b>✦ Create a location</b>",
            "Fill in: location name, category, description and desired atmosphere",
            "Note <b>technical constraints</b>: shooting permits, accessibility, available natural light",
            "Add <b>reference images</b>: scouting photos, moodboards",
        ),
        _h("Location categories"),
        _ul(
            "<b>Interior</b> — apartments, offices, restaurants, public buildings",
            "<b>Exterior</b> — streets, parks, countryside, beaches, forests, architecture",
            "<b>Studio</b> — studio shoot with built sets",
            "<b>Vehicle</b> — interior of car, train, plane, boat",
        ),
        _h("Assign to storyboard shots"),
        _ul(
            "Each shot can be assigned a location from the shot edit card",
            "The location appears in the Location column of the storyboard",
            "Seedance prompts automatically integrate the location description",
        ),
        _tip("Auto-generate locations from your screenplay (Screenplay → Claude AI → Generate locations). Claude identifies all INT./EXT. locations and creates the corresponding cards."),
    ])


def _e_accessories() -> str:
    return "".join([
        _h("Props — Props & equipment", 1),
        _p("The Props page lists all props, equipment and materials needed for the shoot, with their visual references and logistical information."),
        _sep_html(),
        _h("Create a prop"),
        _ul(
            "Click <b>✦ Create a prop</b>",
            "Fill in: name, precise description, required quantity",
            "Add <b>reference images</b> to guide purchasing and production management",
            "Note estimated budget, supplier or availability",
        ),
        _h("Use in production"),
        _ul(
            "Assign props to storyboard shots for precise tracking",
            "The list of props per shot helps the props department prepare each shooting day",
            "Props can also be assigned to characters (who carries what)",
        ),
        _tip("Auto-generate the props list from your screenplay (Screenplay → Claude AI → Generate props). Claude analyses the script and identifies all mentioned objects."),
    ])


def _e_hmc() -> str:
    return "".join([
        _h("HMC — Costume, Makeup, Hair", 1),
        _p("The HMC page centralises all costume, makeup and hair information for each character and each scene, with the visual references needed by the artistic teams."),
        _sep_html(),
        _h("HMC categories"),
        _ul(
            "<b>Costume</b> — complete outfits, specific clothing, shoes, fashion accessories",
            "<b>Makeup</b> — base makeup, effects, ageing, injuries, special effects",
            "<b>Hair</b> — cuts, colours, styling, wigs, extensions, hairpieces",
            "<b>Special effects</b> — prosthetics, latex, injury effects, transformations",
        ),
        _h("Create an HMC card"),
        _ul(
            "Click <b>✦ Create an HMC item</b>",
            "Link the card to a cast character",
            "Describe the look precisely to guide the costume designer and makeup artist",
            "Add reference images: Pinterest, similar production photos, lookbooks",
            "Specify constraints: allergies, application time, maintenance",
        ),
        _tip("Auto-generate HMC cards from your screenplay (Screenplay → Claude AI → Generate HMC). Claude identifies costume and makeup descriptions in the script."),
    ])


def _e_vehicles() -> str:
    return "".join([
        _h("Vehicles — Vehicle fleet & transport", 1),
        _p("The Vehicles page lists all vehicles needed for the shoot: protagonist's cars, period vehicles, motorcycles, trucks, special equipment, etc."),
        _sep_html(),
        _h("Create a vehicle card"),
        _ul(
            "Click <b>✦ Create a vehicle</b>",
            "Fill in: vehicle type, make, model, year, colour",
            "Note <b>required modifications</b>: paint, registration, equipment",
            "Indicate availability constraints, rental or purchase",
            "Add reference images to facilitate the search",
        ),
        _h("Auto-generation"),
        _ul(
            "From Screenplay → Claude AI → <b>Generate vehicles</b>",
            "Claude identifies all vehicles mentioned in the script",
            "Cards are pre-filled with information available in the text",
        ),
    ])


def _e_camera() -> str:
    return "".join([
        _h("Camera & Sound — Camera and lenses", 1),
        _p("The Camera & Sound page lets you configure camera, lens and sound preferences for your film. These settings influence shot suggestions in the storyboard and enrich Seedance 2.0 prompts."),
        _sep_html(),
        _h("Camera body"),
        _ul(
            "Select your film's main camera (ARRI Alexa, RED, Sony FX3, Canon EOS, Blackmagic…)",
            "This choice contextualises shot size and focal length suggestions",
            "It is integrated into Seedance video prompts for a coherent cinematic look",
        ),
        _h("Available lenses"),
        _ul(
            "Configure your lens kit: available prime lenses and zooms",
            "This data is used to suggest suitable focal lengths for each storyboard shot",
            "Examples: 24mm (wide angle), 35mm (reportage), 50mm (standard), 85mm (portrait), 135mm (telephoto)",
        ),
        _h("Sound settings"),
        _ul(
            "Note the main microphone type: boom, wireless lavalier, shotgun mic",
            "This information is accessible in shot cards (Mic field)",
            "Useful for briefing the sound recordist",
        ),
        _tip("Camera preferences are saved per project. You can have different configurations for each film."),
    ])


def _e_seedance() -> str:
    return "".join([
        _h("AI Studio — Video generation, sound and upscaling", 1),
        _p("The AI Studio gathers all production in <b>7 tabs</b>: "
           "<b>Generate from Storyboard</b> · <b>Edit clips</b> · <b>Direct generation</b> · "
           "<b>Sound Design</b> · <b>Upscaling</b> · <b>Video library</b> · <b>History</b>. "
           "The main engine is <b>Seedance 2.0</b> (ByteDance, via fal.ai) — marked "
           "<b>“recommended”</b> in the engine selector: it gives the best results on the "
           "storyboard workflow. The generation button is named <b>▶▶ Start the queue</b> "
           "everywhere, and <b>Open folder</b> is always active, even before the first generation."),
        _sep_html(),
        _h("The 4 generation modes"),
        _ul(
            "<b>Text-to-Video (T2V)</b> — generates a video from a text prompt only",
            "<b>Image-to-Video (I2V)</b> — animates a still image according to a movement prompt",
            "<b>Clip Extension</b> — naturally extends an existing video",
            "<b>Multimodal Reference</b> — generates from several combined reference images",
        ),
        _sep_html(),
        _h("Text-to-Video (T2V)"),
        _ul(
            "Enter your prompt in <b>French</b> — PANDORA automatically translates it to English via Claude Haiku",
            "Choose resolution (480p, 720p, 1080p) and duration (up to 10 seconds)",
            "Click <b>✦ Generate</b> to start generation",
            "Progress is shown in real time (0% → 100%)",
            "The generated video is automatically saved in the project folder",
        ),
        _h("Image-to-Video (I2V)"),
        _ul(
            "Import a starting image (PNG, JPG, WEBP — up to 10 MB)",
            "Write a prompt describing the desired movement (slow zoom in, pan right…)",
            "Seedance 2.0 animates the image according to your description",
            "Ideal for animating character portraits, moodboards or concept art",
        ),
        _h("Clip Extension"),
        _ul(
            "Import an existing video (generated or external)",
            "Seedance 2.0 generates a natural continuation of the movement and action",
            "Useful for extending generated shots or creating continuous sequences",
        ),
        _h("Multimodal Reference"),
        _ul(
            "Import several reference images: character, location, atmosphere, style",
            "Write a prompt combining these visual references",
            "Seedance generates a coherent video integrating all references",
            "Ideal for complex scenes with defined character + location + atmosphere",
        ),
        _sep_html(),
        _h("Native lipsync — Dialogue in quotes"),
        _ul(
            'Seedance 2.0 supports <b>native lip sync</b> in Text-to-Video',
            'Place dialogue in double quotes in the prompt to activate audio and lip sync:',
            '<code>A woman looks at the camera and says "Hello, welcome to our film."</code>',
            'PANDORA automatically protects French quotes « » during translation',
            'Recommended duration: 5-10 s for short dialogue, 10-15 s for a monologue',
        ),
        _sep_html(),
        _h("Generation engine — 8 engines available"),
        _p("In the <b>Generate from Storyboard</b> and <b>Edit clips</b> tabs, "
           "the <b>Generation engine</b> menu gives access to the compatible AI video engines. "
           "Each label shows the capabilities actually used by the workflow "
           "(<i>i2v continuity · refs</i>) and <b>Seedance 2.0 is marked “recommended”</b> — "
           "the other engines do not yet deliver results as good. "
           "The selected engine applies to the entire queue."),
        _ul(
            "<b>Seedance 2.0</b> (ByteDance) — T2V + I2V + Extension · up to 15 s · lipsync · <i>default · #2 ELO</i> · $0.02-0.06/s",
            "<b>Happy Horse 1.0</b> (Alibaba) — T2V + I2V · 720p/1080p · <i>#1 ELO April 2026</i> · $0.14-0.28/s",
            "<b>Kling v3 Pro</b> (Kwai) — T2V + I2V · 1080p · native audio · <i>#3 ELO</i> · $0.112-0.196/s",
            "<b>Kling O3 4K</b> — T2V + I2V · 4K resolution · ~$0.42/s",
            "<b>Veo 3.1</b> (Google) — T2V · 1080p · native audio · ~$1.00/video",
            "<b>Sora 2</b> (OpenAI) — T2V · 1080p · fixed duration · ~$0.40/video",
            "<b>PixVerse v6</b> — T2V · 360p to 1080p · $0.025-0.115/s · economical",
            "<b>Seedance 2.0 Fast</b> — Fast version · economical · $0.09/s",
        ),
        _tip("Seedance 2.0 is the default engine — most optimized in Pandora (references, lipsync, storyboard). "
             "ELO video ranking, April 2026. "
             "Resolution and ratio are set automatically based on the chosen engine. "
             "Kling O3 4K automatically switches to 4K; Veo 3.1 and Sora 2 lock to 1080p."),
        _p("The <b>Direct generation</b> tab gives access to all 8 engines with dedicated forms "
           "(start image, advanced parameters…) without storyboard integration."),
        _sep_html(),
        _h("Automatic T2V → Reference switch"),
        _p("In the <b>Generate from Storyboard</b> tab, if visual references are available (characters, locations, props assigned to the shot), PANDORA automatically switches from <i>text-to-video</i> to <i>reference-to-video</i> — with no action on your part."),
        _ul(
            "Slot 1: mosaic of <b>character portraits</b> assigned to the shot",
            "Slot 2: <b>location image</b> assigned to the shot",
            "Slot 3: <b>props + vehicles</b> mosaic assigned to the shot",
            "The switch is silent — the displayed mode stays T2V but the actual mode is Reference",
            "The more complete your cards (cast, locations, props), the more coherent the generations",
        ),
        _tip("For the switch to work, assign characters, locations and props to each storyboard shot. Without assignment, no references are sent and Seedance stays in pure T2V."),
        _sep_html(),
        _h("Mock mode vs Real mode"),
        _ul(
            "<b>Mock mode</b> (without fal.ai key) — local simulation with animated progress bar. Generates a video placeholder. Perfect for testing the workflow without cost.",
            "<b>Real mode</b> (with fal.ai key) — real Seedance 2.0 API call. Real video generation. Billing according to your usage on fal.ai.",
        ),
        _warn("Without a fal.ai API key in Settings, all Seedance generations run in mock mode. Placeholder videos are not saved."),
        _sep_html(),
        _h("Generation history"),
        _ul(
            "The last 50 real generations are kept in history",
            "Access all videos from the <b>History</b> tab of the AI Studio",
            "Videos are stored in <code>data/Seedance/</code> of the project folder",
        ),
        _tip("Prompts are automatically translated to English before being sent to Seedance 2.0. Write your prompts in French — translation is transparent and optimised."),
        _sep_html(),
        _h("Sound Design — Mirelo SFX (new)"),
        _p("The <b>Sound Design</b> tab adds sound to your shots via Mirelo SFX 1.6 (~$0.01/s):"),
        _ul(
            "<b>Prompt → SFX</b> — describe the ambience or sound effects (preferably in "
            "English) and get an audio file ready for the timeline",
            "<b>Video → soundtrack</b> — give it a video clip: Mirelo generates a soundtrack "
            "<b>synchronized to the picture</b> (optional prompt to guide the style)",
            "Generated files are listed at the bottom of the tab with a <b>Play</b> button",
            "<b>Open folder</b> opens the destination (<code>data/sound_design/</code>), "
            "even before the first generation",
        ),
        _sep_html(),
        _h("Upscaling — Topaz / SeedVR2 (new)"),
        _p("The <b>Upscaling</b> tab upscales your clips in batch:"),
        _ul(
            "<b>Add clips</b> or <b>⇪ Import the Video library</b> fills the queue — "
            "shown as <b>small cards</b> with thumbnails (right-click = remove)",
            "Choose the engine (<b>Topaz Video</b> max quality, <b>SeedVR2</b> fast) "
            "and the factor <b>×2</b> (480p→~1080p) or <b>×4</b> (480p→~4K)",
            "<b>▶▶ Start the queue</b> processes every clip, one at a time — "
            "cancellable at any moment (remaining clips are kept)",
            "The output keeps the <b>same name as the source</b>: in DaVinci, a simple "
            "<b>Relink Media</b> swaps your clips for the high-resolution version",
        ),
        _tip("Budget workflow: generate everything in 480p (fast and cheap), edit the film, "
             "then upscale only the selected shots at ×2 or ×4."),
        _sep_html(),
        _h("Edit clips — Batch generation"),
        _p("The <b>Edit clips</b> tab lets you bulk-transform clips from your DaVinci timeline with Seedance 2.0. Each clip is uploaded as a video reference and Seedance generates a modified version based on your prompt."),
        _ul(
            "<b>1.</b> In DaVinci: right-click a clip → <b>Flag</b> → color to select it "
            "(no flag = entire timeline is sent)",
            "<b>2.</b> DaVinci → <b>Workspace → Scripts → pandora_send</b> "
            "(or your custom keyboard shortcut)",
            "<b>3.</b> PANDORA displays the received clips in the <b>Edit clips</b> tab",
            "<b>4.</b> Write a <b>global prompt</b> (same for all clips) "
            "or a <b>per-clip prompt</b> (click each thumbnail to customise)",
            "<b>5.</b> Click <b>▶▶ Launch queue</b> — sequential processing, 1 clip at a time",
            "Generated videos are automatically imported into DaVinci's <b>Media Pool</b>",
            "Use the <b>×N</b> spinbox to generate multiple takes per clip",
        ),
        _warn(
            "Format required by Seedance 2.0 for reference clips: "
            "<b>720p maximum · less than 50 MB · H.264 MP4 or MOV</b>. "
            "From DaVinci: File → Export → select H.264 Master at 720p "
            "before sending your clips via pandora_send."
        ),
        _h("Visual DNA — Seed Lock"),
        _ul(
            "<b>🔒 Visual DNA — keep for all shots</b>: locks the Seedance seed "
            "to maintain visual consistency across all clips in the queue",
            "<b>Automatically enabled</b> when multiple clips are checked",
            "Each modified clip uses the same seed → coherent style and palette despite different camera angles",
            "Uncheck if you want random variation per clip",
        ),
        _h("DaVinci Bridge"),
        _ul(
            "The bridge is required for <b>automatic import into the Media Pool</b>",
            "If the bridge is not connected, PANDORA offers: "
            "<i>Close</i> / <i>↻ Check connection</i> / <i>Generate without import</i>",
            "To connect: DaVinci Resolve → Workspace → Scripts → <b>seedance_bridge</b>",
            "Keep the PANDORA Bridge window open throughout your session",
        ),
        _tip(
            "Effective modification prompt: be precise about what you want to <i>keep</i> "
            "and what you want to <i>change</i>. E.g.: "
            "<i>\"same scene, same characters and camera movement, replace background with a luxury restaurant, "
            "keep lighting mood\"</i>"
        ),
    ])


def _e_doublage() -> str:
    return "".join([
        _h("Dubbing — AI voice & audio tools", 1),
        _sep_html(),
        _h("Text-to-Speech — Kokoro TTS"),
        _p("The Dubbing page offers high-quality AI text-to-speech via Kokoro TTS (fal.ai). Generate natural voices for your dialogue, narration or animatics."),
        _ul(
            "<b>10+ languages</b>: US/UK English, Spanish, Portuguese, Italian, Japanese, Mandarin",
            "<b>30+ voices</b> classified by gender and language",
            "<b>Adjustable speed</b>: from 0.5× (slow) to 2.0× (fast)",
            "WAV files saved in <code>data/doublage/audio/</code>",
            "Rate: <b>$0.02 / 1,000 characters</b>",
        ),
        _h("Background removal — BiRefNet"),
        _p("BiRefNet automatically removes the background of an image and exports a PNG with a transparent alpha channel. Ideal for isolating characters or location elements."),
        _ul(
            "Import: PNG, JPG, JPEG, WEBP, BMP",
            "Export: PNG with transparency (background removed)",
            "Result saved in the same folder as the source image",
            "Rate: per GPU compute (a few cents per image)",
        ),
        _h("Native lipsync — Seedance T2V"),
        _ul(
            'Place dialogue in quotes in the Seedance T2V prompt to activate lip sync',
            '<code>A character says "Welcome to our world."</code>',
            'Seedance automatically generates audio synchronised with lip movement',
        ),
        _tip("The Dubbing page will be expanded in a future version with additional lip sync and advanced audio processing features."),
    ])


def _e_pricing() -> str:
    table_image = "".join([
        '<table style="border-collapse:collapse;width:100%;margin:10px 0 16px 0;">',
        _table_row(["Model", "Technology", "Usage", "Price"], header=True),
        _table_row(["Nano Banana 2", "Gemini 3.1 Flash", "Portraits, locations, HMC, props", "$0.08 / image"]),
        _table_row(["Nano Banana Pro", "Gemini 3 Pro", "High quality portraits", "$0.15 / image"]),
        _table_row(["Flux Schnell", "Black Forest Labs", "Ultra-fast storyboard sketches", "~$0.003 / image"]),
        _table_row(["GPT Image 2", "OpenAI", "Images with text (logos, signs)", "~$0.21 / image"]),
        "</table>",
    ])
    table_video = "".join([
        '<table style="border-collapse:collapse;width:100%;margin:10px 0 16px 0;">',
        _table_row(["Engine (ELO Apr. 2026)", "Mode", "Resolution", "Native audio", "Price"], header=True),
        _table_row(["Seedance 2.0 ★ (default)", "T2V + I2V + Extension", "up to 1080p", "✓ (lipsync)", "$0.02-0.06/s"]),
        _table_row(["#1 Happy Horse 1.0", "T2V + I2V", "720p / 1080p", "✗", "$0.14-0.28/s"]),
        _table_row(["#3 Kling v3 Pro", "T2V + I2V", "1080p", "✓", "$0.112-0.196/s"]),
        _table_row(["Kling O3 4K", "T2V + I2V", "4K", "✗", "~$0.42/s"]),
        _table_row(["Veo 3.1", "T2V", "1080p", "✓", "~$1.00/video"]),
        _table_row(["Sora 2", "T2V", "1080p", "✗", "~$0.40/video"]),
        _table_row(["PixVerse v6", "T2V", "360p → 1080p", "✗", "$0.025-0.115/s"]),
        _table_row(["Seedance 2.0 Fast", "T2V", "up to 720p", "✓", "~$0.09/s"]),
        "</table>",
    ])
    table_audio = "".join([
        '<table style="border-collapse:collapse;width:100%;margin:10px 0 16px 0;">',
        _table_row(["Service", "Technology", "Languages", "Price"], header=True),
        _table_row(["Kokoro TTS", "fal-ai/kokoro", "EN, ES, PT, IT, JA, ZH", "$0.02 / 1,000 chars"]),
        _table_row(["BiRefNet", "fal-ai/birefnet", "—", "Per compute"]),
        "</table>",
    ])
    return "".join([
        _h("AI Pricing — Cost overview", 1),
        _p("All prices are in <b>USD</b> and based on actual usage on fal.ai. In mock mode (no key), no billing occurs."),
        _sep_html(),
        _h("Image generation"),
        table_image,
        _h("Video generation"),
        table_video,
        _h("Audio & Utilities"),
        table_audio,
        _tip("All prices are indicative and subject to change. Check fal.ai for current rates."),
        _warn("In mock mode (without fal.ai key), no billing occurs. Add your key in Settings for real generations."),
    ])


def _e_style() -> str:
    return "".join([
        _h("Visual style — Cinematic universe", 1),
        _p("The visual style defines the overall aesthetic of your film. It influences portrait generation (Nano Banana), locations, props and video (Seedance 2.0) for complete visual consistency."),
        _sep_html(),
        _h("Access the visual style"),
        _ul(
            "From the <b>Screenplay editor</b> — configuration strip above the editor (always visible)",
            "From the <b>Visual style</b> page in the navigation bar — full view with all cards",
        ),
        _h("30+ styles organised in 6 categories"),
        _ul(
            "<b>Live cinema</b> — Realistic film, Documentary, Film noir, Western, Historical, War film, Thriller, Comedy, Road movie",
            "<b>Animation</b> — 3D animation (CGI), 2D cartoon, Japanese anime, Stop-motion",
            "<b>Genre</b> — Epic fantasy, Fairy tale/Fable, Space sci-fi, Neon cyberpunk, Horror, Steampunk, Surrealism, Musical",
            "<b>Visual arts</b> — Watercolour, Oil painting, Franco-Belgian comics (Moebius), Art Nouveau, Ink & wash, Low poly, Pixel art",
            "<b>Modern trends</b> — Lo-fi retro (Super 8), Luxury advertising, Nature documentary (BBC Earth), Found footage, Music video",
            "<b>Hybrid</b> — Multi-style (personalised creative fusion)",
        ),
        _h("Free style description"),
        _ul(
            "Available at the bottom of the Visual style page",
            "Lets you specify or customise the selected style",
            "Example: <i>\"Mix of live footage and 2D animation effects, Roger Rabbit style\"</i>",
            "This description is added to generation prompts for more precision",
        ),
        _h("Impact on generations"),
        _ul(
            "<b>Nano Banana portraits</b> — the style is integrated into the generated image",
            "<b>Seedance 2.0 videos</b> — a corresponding video suffix is automatically added to each prompt",
            "<b>Locations and props</b> — the visual rendering follows the chosen aesthetic",
        ),
        _h("Reference images per style"),
        _ul(
            "Each style can have <b>reference images</b> that are sent to Seedance with every generation",
            "In the style gallery, click <b>+ Add image</b> to import your own references",
            "Imported references are saved in <code>%LOCALAPPDATA%\\PANDORA\\assets\\style_refs\\</code>",
            "They complement the built-in visual references — the more precise the reference, the more consistent the result",
        ),
        _tip("Choose your style <b>before</b> generating anything. It propagates automatically to all pages and applies to all new generations."),
    ])


def _e_settings() -> str:
    return "".join([
        _h("Settings — PANDORA configuration", 1),
        _p("The Settings page centralises all API keys, output preferences and DaVinci Resolve integration configuration."),
        _sep_html(),
        _h("fal.ai API key — Seedance 2.0"),
        _ul(
            "Create an account on <b>fal.ai</b>",
            "Go to your personal space → API Keys → Create new key",
            "Copy the generated key and paste it in the <b>fal.ai key</b> field",
            "Click <b>Save</b>",
            "Without this key: mock mode (local simulation, no real video generated)",
        ),
        _h("Anthropic API key — Claude AI"),
        _ul(
            "Create an account on <b>console.anthropic.com</b>",
            "API Keys → Create Key — give it a name",
            "Paste the key in the <b>Anthropic key</b> field",
            "Without this key: all Claude AI functions are disabled (screenplay formatting, arrangement, storyboard generation, element extraction)",
        ),
        _h("Nano Banana API key — AI portraits"),
        _ul(
            "Create an account on the Nano Banana platform",
            "Retrieve your API key from your personal space",
            "Paste it in the <b>Nano Banana key</b> field",
            "Without this key: portraits in mock mode (coloured placeholder images)",
        ),
        _h("DaVinci Resolve — Bridge connection"),
        _ul(
            "Click <b>Install bridge</b> to copy the script to DaVinci's Scripts folder",
            "Open DaVinci Resolve with a project loaded",
            "In DaVinci: <b>Workspace → Scripts → seedance_bridge</b>",
            "The script launches a local TCP server (port 19876)",
            "Click <b>Connect</b> in PANDORA — the indicator turns green ●",
        ),
        _warn("If Claude does not respond, <b>disable your VPN</b> — some VPN servers are blocked by the Anthropic API."),
        _warn("DaVinci Python scripting (Media Pool import, timeline reading) is reserved for <b>DaVinci Resolve Studio</b> (paid version). The free version does not support these functions."),
        _h("Output folder"),
        _ul(
            "By default, videos are saved in <code>data/Seedance/</code> of the current project",
            "Configure an alternative output folder if needed",
        ),
    ])


def _e_shortcuts() -> str:
    return "".join([
        _h("Shortcuts & Tips", 1),
        _sep_html(),
        _h("Keyboard shortcuts"),
        _ul(
            f"{_kbd('Ctrl+Z')} — Undo in the screenplay editor (manual history)",
            f"{_kbd('Ctrl+Y')} — Redo in the screenplay editor",
            f"{_kbd('Ctrl+S')} — Save the current screenplay (from the editor)",
        ),
        _sep_html(),
        _h("Tips for better Seedance prompts"),
        _ul(
            "Be <b>precise about staging</b>: camera, lighting, angle, location",
            "Avoid dialogue in T2V prompts — Seedance generates image, not synchronised sound",
            "Mention the film style: <i>cinematic, shot on ARRI, handheld camera</i>",
            "For I2V, describe the movement: <i>slowly zooms in, pans left, dolly forward</i>",
            "Keep prompts between <b>50 and 150 words</b> for optimal results",
            "Avoid lists — write fluid, descriptive sentences",
        ),
        _h("Tips for the storyboard"),
        _ul(
            "Generate the full storyboard with Claude first, then refine shot by shot",
            "Use the Staging fields (axis, placements) for team briefings",
            "The IN/OUT fields facilitate continuity and shot matching",
            "The <b>shot size</b> (close-up, wide shot…) directly influences the generated Seedance prompt",
            "Assign locations to each shot — they automatically enrich the prompts",
        ),
        _h("Tips for portraits"),
        _ul(
            "Describe precisely: <b>age, physical traits, skin tone, eye colour, hair type</b>",
            "Specify the desired expression: smiling, serious, melancholic, intense",
            "Mention the portrait style: professional casting photo, cinematic portrait",
            "Generate 3-4 variants — diversity of proposals lets you find the best one",
        ),
        _h("Optimised workflow"),
        _ul(
            "Always start by writing a screenplay, even partially — all other pages feed from it",
            "Choose the visual style <b>early</b> — it influences all AI generations",
            "Let Claude auto-generate elements, then refine each card manually",
            "Generate Moods (Seedance prompts) for the storyboard <b>before</b> launching videos",
            "Use screenplay versions to keep alternatives without deleting anything",
        ),
        _tip("PANDORA is designed for <b>iterative</b> work. Generate, refine, regenerate. Each iteration improves the coherence of your project."),
    ])


_BUILDERS_EN = [
    _e_welcome, _e_projects,                                    # GET STARTED
    _e_scenario, _e_storyboard, _e_castings, _e_decors,        # PRE-PRODUCTION
    _e_accessories, _e_hmc, _e_vehicles, _e_camera,
    _e_seedance, _e_style, _e_doublage, _e_pricing,            # AI STUDIO
    _e_settings, _e_shortcuts,                                  # REFERENCE
]


# ── Dialogue ───────────────────────────────────────────────────────────────────

class UserManualDialog(QDialog):

    def __init__(self, parent=None, start_section: int = 0):
        super().__init__(parent)
        from core.i18n import get_lang
        self._lang = get_lang()
        self._current_idx = start_section

        self.setWindowTitle("Manuel d'utilisation — PANDORA")
        self.setStyleSheet(PANDORA_STYLESHEET + f"QDialog{{background:{CP['bg0']};}}")
        from ui.widgets import fit_dialog_to_screen
        fit_dialog_to_screen(self, 0.70, 0.84, 760, 480)

        main = QHBoxLayout(self)
        main.setContentsMargins(0, 0, 0, 0)
        main.setSpacing(0)

        # ── Panneau gauche — navigation ───────────────────────────────────────
        nav_panel = QWidget()
        nav_panel.setFixedWidth(220)
        nav_panel.setStyleSheet(
            f"background:{CP['bg1']};border-right:1px solid {CP['border']};"
        )
        nav_lay = QVBoxLayout(nav_panel)
        nav_lay.setContentsMargins(0, 0, 0, 0)
        nav_lay.setSpacing(0)

        # Header avec toggle de langue
        hdr = QWidget()
        hdr.setFixedHeight(60)
        hdr.setStyleSheet(f"background:{CP['bg0']};border-bottom:1px solid {CP['border']};")
        hl = QHBoxLayout(hdr)
        hl.setContentsMargins(12, 0, 12, 0)
        hl.setSpacing(6)
        self._hdr_lbl = QLabel("Manuel" if self._lang == "fr" else "Manual")
        self._hdr_lbl.setStyleSheet(
            f"color:{CP['text_primary']};font-size:13px;font-weight:800;background:transparent;"
        )
        hl.addWidget(self._hdr_lbl, 1)

        _btn_ss = (
            f"QPushButton{{background:{CP['bg3']};color:{CP['text_secondary']};"
            f"border:1px solid {CP['border']};border-radius:5px;"
            f"font-size:10px;font-weight:800;padding:2px 6px;}}"
            f"QPushButton:checked{{background:{CP['accent']};color:#07080f;"
            f"border-color:{CP['accent']};}}"
            f"QPushButton:hover{{border-color:{CP['border_bright']};}}"
        )
        self._btn_fr = QPushButton("FR")
        self._btn_fr.setFixedSize(30, 22)
        self._btn_fr.setCheckable(True)
        self._btn_fr.setStyleSheet(_btn_ss)
        self._btn_fr.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_fr.clicked.connect(lambda: self._set_lang("fr"))
        self._btn_en = QPushButton("EN")
        self._btn_en.setFixedSize(30, 22)
        self._btn_en.setCheckable(True)
        self._btn_en.setStyleSheet(_btn_ss)
        self._btn_en.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_en.clicked.connect(lambda: self._set_lang("en"))
        (self._btn_fr if self._lang == "fr" else self._btn_en).setChecked(True)
        hl.addWidget(self._btn_fr)
        hl.addWidget(self._btn_en)
        nav_lay.addWidget(hdr)

        scroll_nav = QScrollArea()
        scroll_nav.setWidgetResizable(True)
        scroll_nav.setStyleSheet("QScrollArea{background:transparent;border:none;}")
        scroll_nav.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        nav_content = QWidget()
        nav_content.setStyleSheet("background:transparent;")
        self._nc_lay = QVBoxLayout(nav_content)
        self._nc_lay.setContentsMargins(8, 8, 8, 8)
        self._nc_lay.setSpacing(2)

        self._nav_btns: list[QPushButton] = []
        self._build_nav_buttons()

        scroll_nav.setWidget(nav_content)
        nav_lay.addWidget(scroll_nav, 1)

        self._close_btn = QPushButton("Fermer" if self._lang == "fr" else "Close")
        self._close_btn.setFixedHeight(38)
        self._close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._close_btn.setStyleSheet(
            f"QPushButton{{background:{CP['bg3']};color:{CP['text_secondary']};"
            f"border:1px solid {CP['border']};border-radius:8px;"
            f"font-size:12px;font-weight:700;margin:8px;}}"
            f"QPushButton:hover{{background:{CP['bg4']};color:{CP['text_primary']};}}"
        )
        self._close_btn.clicked.connect(self.accept)
        nav_lay.addWidget(self._close_btn)

        main.addWidget(nav_panel)

        # ── Zone de contenu droite ─────────────────────────────────────────────
        self._content = QTextEdit()
        self._content.setReadOnly(True)
        self._content.setStyleSheet(
            f"QTextEdit{{background:{CP['bg0']};border:none;"
            f"color:{CP['text_secondary']};font-size:12px;padding:32px 48px;}}"
            f"QScrollBar:vertical{{background:{CP['bg2']};width:6px;border-radius:3px;}}"
            f"QScrollBar::handle:vertical{{background:{CP['border_bright']};border-radius:3px;}}"
            f"QScrollBar::add-line:vertical,QScrollBar::sub-line:vertical{{height:0;}}"
        )
        main.addWidget(self._content, 1)

        self._show_section(self._current_idx)

    def _build_nav_buttons(self):
        # Supprimer tous les widgets existants (boutons + labels de groupe)
        while self._nc_lay.count():
            item = self._nc_lay.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()
        self._nav_btns.clear()

        _btn_nav_ss = (
            f"QPushButton{{background:transparent;color:{CP['text_secondary']};"
            f"border:none;border-radius:6px;text-align:left;"
            f"font-size:11px;font-weight:600;padding:0 10px;}}"
            f"QPushButton:hover{{background:rgba(255,255,255,0.05);"
            f"color:{CP['text_primary']};}}"
            f"QPushButton:checked{{background:rgba(78,205,196,0.15);"
            f"color:{CP['accent']};font-weight:700;"
            f"border:1px solid rgba(78,205,196,0.25);}}"
        )
        _grp_ss = (
            f"color:{CP['text_dim']};font-size:9px;letter-spacing:2px;font-weight:700;"
            f"font-family:'Consolas',monospace;background:transparent;"
            f"padding:10px 10px 3px 12px;"
        )

        groups   = _GROUPS_FR   if self._lang == "fr" else _GROUPS_EN
        sections = _SECTIONS    if self._lang == "fr" else _SECTIONS_EN
        sec_idx  = 0
        for group_name, group_count in groups:
            grp_lbl = QLabel(group_name)
            grp_lbl.setStyleSheet(_grp_ss)
            self._nc_lay.addWidget(grp_lbl)
            for _ in range(group_count):
                icon, label = sections[sec_idx]
                btn = QPushButton(f"  {icon}  {label}")
                btn.setFixedHeight(34)
                btn.setCursor(Qt.CursorShape.PointingHandCursor)
                btn.setCheckable(True)
                btn.setStyleSheet(_btn_nav_ss)
                btn.clicked.connect(lambda _, idx=sec_idx: self._show_section(idx))
                self._nc_lay.addWidget(btn)
                self._nav_btns.append(btn)
                sec_idx += 1
        self._nc_lay.addStretch()

    def _set_lang(self, lang: str):
        if self._lang == lang:
            return
        self._lang = lang
        self._btn_fr.setChecked(lang == "fr")
        self._btn_en.setChecked(lang == "en")
        self._hdr_lbl.setText("Manuel" if lang == "fr" else "Manual")
        self._close_btn.setText("Fermer" if lang == "fr" else "Close")
        self._build_nav_buttons()
        self._show_section(self._current_idx)

    def _show_section(self, idx: int):
        self._current_idx = idx
        for i, btn in enumerate(self._nav_btns):
            btn.setChecked(i == idx)
        builders = _BUILDERS if self._lang == "fr" else _BUILDERS_EN
        html = builders[idx]()
        self._content.setHtml(
            f'<html><body style="background:{CP["bg0"]};'
            f'font-family:\'Segoe UI\',Arial,sans-serif;margin:0;padding:0;">'
            f'{html}</body></html>'
        )
        self._content.verticalScrollBar().setValue(0)
