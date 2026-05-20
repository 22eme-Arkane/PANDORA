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
    ("✦",  "Seedance 2.0"),
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
            "Rédiger et formater votre scénario avec l'aide de <b>Claude IA</b> (Anthropic)",
            "Créer un storyboard plan par plan avec caméra, acteurs, décors et prompts",
            "Gérer le casting avec des <b>portraits générés par IA</b> (Nano Banana)",
            "Répertorier décors, accessoires, HMC et véhicules nécessaires au tournage",
            "Définir les préférences caméra et optique du film",
            "Choisir un <b>style visuel</b> qui influence toutes les générations IA",
            "Générer des vidéos Seedance 2.0 : T2V, I2V, Extension, Référence multimodale",
            "Importer automatiquement les vidéos dans <b>DaVinci Resolve</b> (Studio requis)",
        ),
        _sep_html(),
        _h("Workflow recommandé"),
        _ul(
            "<b>1.</b> Créez ou ouvrez un projet depuis la page Projets",
            "<b>2.</b> Rédigez votre scénario, formatez-le avec Claude IA",
            "<b>3.</b> Choisissez un style visuel depuis l'éditeur de scénario",
            "<b>4.</b> Générez automatiquement personnages, décors, HMC, accessoires, véhicules depuis le scénario",
            "<b>5.</b> Générez le storyboard avec Claude IA, affinez plan par plan",
            "<b>6.</b> Configurez les moods Seedance pour chaque plan",
            "<b>7.</b> Lancez la génération vidéo depuis le storyboard ou l'onglet Seedance 2.0",
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
            "Rendez-vous dans la page <b>Projets</b> depuis la barre latérale",
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
        _p("La page Scénario est le cœur de PANDORA. Rédigez votre script, formatez-le avec Claude IA, gérez des versions, et générez toute votre pré-production depuis un seul endroit."),
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
            "<b>Style visuel</b> — influence la génération de vidéos, portraits et décors (Film réaliste, Anime, Cyberpunk…)",
            "<b>Durée du film</b> — durée totale estimée du projet en minutes et secondes",
            "Ces paramètres sont visibles en permanence pour ne jamais les oublier",
        ),
        _sep_html(),
        _h("Mise en page scénario (Claude IA)"),
        _ul(
            "Cliquez sur <b>≡ Mise en page scénario</b> dans le panneau droit",
            "Claude reformate votre texte en mise en page cinéma standard :",
            "→ En-têtes de scène : <code>INT. LIEU — HEURE</code> / <code>EXT. LIEU — HEURE</code>",
            "→ Numéros et titres de séquences",
            "→ Dialogues indentés avec nom du personnage centré",
            "→ Transitions expressives conservées (FONDU AU NOIR, etc.) — pas de COUPE SUR implicite",
            "Le résultat s'affiche en bas — cliquez <b>↩ Remplacer le texte</b> pour l'appliquer",
            "Annulez immédiatement avec <b>↺ Annuler</b> si le résultat ne convient pas",
        ),
        _h("Arrangement IA (Claude IA)"),
        _ul(
            "Cliquez sur <b>⊞ Proposer un arrangement</b>",
            "Réglez l'<b>intensité</b> (1 à 10) selon le niveau de modification souhaité :",
            "→ <b>1-2</b> : Corrections orthographiques et de ponctuation uniquement",
            "→ <b>3-4</b> : Restructuration douce, rythme de lecture amélioré",
            "→ <b>5-6</b> : Reformulation standard, cohérence narrative et dialogues",
            "→ <b>7-8</b> : Refonte de séquences, développement ou coupe de scènes",
            "→ <b>9-10</b> : Réécriture radicale — structure profondément modifiée",
            "Claude analyse la structure et propose des améliorations avec explication",
            "Cliquez <b>✏ Modifier selon les suggestions</b> pour appliquer les changements",
        ),
        _h("Versions"),
        _ul(
            "Cliquez sur <b>✚</b> pour sauvegarder une version nommée de votre scénario",
            "Sélectionnez une version dans le menu déroulant pour la charger <b>instantanément</b>",
            "Supprimez une version avec le bouton <b>✕</b>",
            "Exemple d'usage : Version 1 (première ébauche), Version 2 (après arrangement IA), Version finale",
        ),
        _h("Undo / Redo"),
        _ul(
            "Chaque modification par Claude crée un <b>point de sauvegarde automatique</b>",
            f"Bouton <b>↩</b> (ou {_kbd('Ctrl+Z')}) pour annuler, <b>↪</b> (ou {_kbd('Ctrl+Y')}) pour rétablir",
            "L'historique d'annulation est conservé toute la session",
        ),
        _sep_html(),
        _h("Générer depuis le scénario (Claude IA)"),
        _p("Une fois le scénario rédigé, Claude peut extraire automatiquement tous les éléments de production et les ajouter aux pages correspondantes :"),
        _ul(
            "<b>Générer les personnages</b> — identifie et crée les fiches de tous les personnages",
            "<b>Générer les décors</b> — extrait tous les lieux INT./EXT. présents dans le script",
            "<b>Générer les accessoires</b> — liste les props et équipements mentionnés",
            "<b>Générer le HMC</b> — identifie costumes, maquillage et coiffures",
            "<b>Générer les véhicules</b> — liste les véhicules nécessaires au tournage",
            "<b>Générer le storyboard</b> — crée un découpage plan par plan complet avec caméra et prompts",
        ),
        _tip("Formatez votre scénario avec Claude <b>avant</b> de générer les éléments. Un scénario structuré (INT./EXT., noms de personnages cohérents) donne des extractions nettement meilleures."),
        _warn("Si Claude ne répond pas ou génère des erreurs réseau, <b>désactivez votre VPN</b> — certains serveurs VPN sont bloqués par l'API Anthropic."),
    ])


def _s_storyboard() -> str:
    return "".join([
        _h("Storyboard", 1),
        _p("Le Storyboard liste tous les plans du film dans l'ordre chronologique. Chaque ligne représente un plan avec ses paramètres techniques et artistiques complets."),
        _sep_html(),
        _h("Colonnes du tableau"),
        _ul(
            "<b>Aperçu</b> — mood image du plan générée via Flux T2I (cliquez sur la cellule pour en générer ou en choisir une)",
            "<b>Séq</b> — numéro et nom de la séquence",
            "<b>Plan</b> — numéro du plan dans la séquence",
            "<b>Action</b> — titre de la scène / description de l'action",
            "<b>Mouvement</b> — mouvement caméra (Statique, Travelling, Panoramique, Zoom…)",
            "<b>Valeur</b> — taille de plan (Gros plan, Plan américain, Plan d'ensemble…)",
            "<b>Focal</b> — focale de l'objectif (en mm)",
            "<b>Vitesse</b> — vitesse de prise de vue (normale, ralenti, accéléré…)",
            "<b>Décor</b> — lieu de tournage assigné",
            "<b>Heure</b> — moment de la journée (Jour, Nuit, Aube, Crépuscule…)",
            "<b>Accessoires</b> — props utilisés dans ce plan",
            "<b>Acteurs</b> — personnages présents dans le cadre",
            "<b>Axe</b> — angle de prise de vue (Face, 3/4, Latéral, Dos, Plongée…)",
            "<b>Durée</b> — durée prévue du plan en secondes",
            "<b>Prompt</b> — prompt Seedance 2.0 pour la génération vidéo",
        ),
        _h("Modifier un plan"),
        _ul(
            "Cliquez directement sur <b>n'importe quelle cellule</b> pour modifier en ligne",
            "Cliquez sur <b>Éditer</b> pour ouvrir la fiche complète du plan",
            "La fiche donne accès à tous les champs : CAMÉRA, ÉLÉMENTS, MISE EN SCÈNE, DURÉE, COMMENTAIRES, PROMPT",
            "Glissez le grip <b>⠿</b> à gauche d'un plan pour le déplacer et réorganiser le découpage",
        ),
        _h("Champs Mise en scène"),
        _ul(
            "<b>Axe caméra</b> — Face / 3/4 / Latéral 90° / Dos / Plongée / Contre-plongée",
            "<b>Placement caméra</b> — description libre du positionnement (hauteur, distance, support)",
            "<b>Placement acteurs</b> — description du placement des comédiens dans le cadre",
            "<b>Entrée (IN)</b> — personnages entrant dans le plan",
            "<b>Sortie (OUT)</b> — personnages quittant le plan",
            "<b>Micro</b> — placement du micro pour ce plan",
        ),
        _h("Génération des Moods (Prompt Seedance)"),
        _ul(
            "Cliquez sur <b>✦ Générer les Moods</b> pour générer automatiquement les prompts Seedance",
            "Claude analyse chaque plan (valeur, mouvement, personnages, décor) et crée un prompt optimisé",
            "Les prompts intègrent le style visuel sélectionné et les préférences caméra",
            "Régénérez le prompt d'un seul plan depuis sa fiche d'édition",
        ),
        _h("Envoyer vers Seedance 2.0"),
        _ul(
            "Cliquez sur le bouton <b>▶ Générer</b> sur un plan pour lancer la génération vidéo",
            "La vidéo apparaît dans la colonne Aperçu une fois générée",
            "Accédez à l'onglet <b>Seedance 2.0</b> pour un contrôle complet de la génération",
        ),
        _h("Versions du storyboard"),
        _ul(
            "Gérez plusieurs versions : découpage final, version courte, alternatives de montage…",
            "Menu déroulant en haut : créer, charger et supprimer des versions",
        ),
        _tip("Générez d'abord votre storyboard complet avec Claude IA depuis la page Scénario, puis affinez plan par plan. La génération automatique crée un découpage cohérent que vous peaufinez ensuite."),
    ])


def _s_castings() -> str:
    return "".join([
        _h("Castings — Personnages du film", 1),
        _p("La page Castings centralise tous les personnages avec leurs caractéristiques, leurs références visuelles et leurs portraits générés par IA."),
        _sep_html(),
        _h("Créer un personnage"),
        _ul(
            "Cliquez sur <b>✦ Créer un personnage</b>",
            "Remplissez : nom, rôle dans l'histoire, âge approximatif",
            "Décrivez la <b>physique</b> : taille, corpulence, couleur de peau, couleur des yeux, coiffure",
            "Décrivez la <b>psychologie</b> : traits de personnalité, motivations, arcs narratifs",
            "Ajoutez des notes de casting pour guider la recherche de comédiens",
        ),
        _h("Générer un portrait IA (Nano Banana)"),
        _ul(
            "Ouvrez la fiche d'un personnage et cliquez sur <b>Générer un portrait</b>",
            "Nano Banana génère plusieurs portraits basés sur la description physique",
            "Sélectionnez le portrait qui correspond le mieux à votre vision",
            "Le portrait sélectionné devient la <b>référence visuelle officielle</b> du personnage",
            "Régénérez autant de fois que nécessaire pour obtenir le résultat souhaité",
        ),
        _warn("La génération de portraits nécessite une clé API Nano Banana dans Paramètres. Sans clé, le mode mock génère des images placeholder colorées."),
        _h("Impact sur les autres pages"),
        _ul(
            "Les personnages apparaissent dans les listes de sélection du storyboard",
            "Leurs portraits sont injectés comme <b>références visuelles dans Seedance 2.0</b>",
            "Claude référence leurs noms exacts lors de l'arrangement et de la génération storyboard",
        ),
        _tip("Générez les personnages automatiquement depuis votre scénario (Scénario → Claude IA → Générer les personnages). Claude identifie tous les personnages nommés dans le script."),
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
        _h("Seedance 2.0 — Génération vidéo IA", 1),
        _p("Seedance 2.0 est le moteur de génération vidéo de ByteDance, accessible via fal.ai. PANDORA propose 4 modes de génération vidéo adaptés à chaque usage."),
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
        _p("Dans les onglets <b>Créer un nouveau clip</b> et <b>Modifier depuis DaVinci Resolve</b>, "
           "le menu <b>Moteur de génération</b> donne accès à 8 moteurs vidéo IA. "
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
            "Accédez à toutes les vidéos depuis le panneau Historique de l'onglet Seedance",
            "Les vidéos sont stockées dans <code>data/Seedance/</code> du dossier projet",
        ),
        _tip("Les prompts sont automatiquement traduits en anglais avant envoi à Seedance 2.0. Rédigez vos prompts en français — la traduction est transparente et optimisée."),
        _sep_html(),
        _h("Modifier depuis DaVinci Resolve — Génération batch"),
        _p("L'onglet <b>Modifier depuis DaVinci Resolve</b> permet de transformer en masse des clips de votre timeline DaVinci avec Seedance 2.0. Chaque clip est uploadé comme référence vidéo et Seedance génère une version modifiée selon votre prompt."),
        _ul(
            "<b>1.</b> Dans DaVinci : clic droit sur un clip → <b>Flag</b> → couleur pour le sélectionner "
            "(sans flag = toute la timeline est envoyée)",
            "<b>2.</b> DaVinci → <b>Espace de travail → Scripts → pandora_send</b> "
            "(ou votre raccourci clavier personnalisé)",
            "<b>3.</b> PANDORA affiche les clips reçus dans l'onglet <b>Modifier depuis DaVinci Resolve</b>",
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
            "Depuis l'<b>éditeur de Scénario</b> — bande de configuration en haut de l'éditeur (visible en permanence)",
            "Depuis la page <b>Style visuel</b> dans la barre latérale — vue complète avec toutes les cartes",
        ),
        _h("30+ styles organisés en 6 catégories"),
        _ul(
            "<b>Cinéma live</b> — Film réaliste, Documentaire, Film noir, Western, Historique, Film de guerre, Thriller, Comédie, Road movie",
            "<b>Animation</b> — Animation 3D (CGI), Dessin animé 2D, Anime japonais, Stop-motion",
            "<b>Genre</b> — Fantasy épique, Conte/Fable, Sci-fi spatiale, Cyberpunk néon, Horreur, Steampunk, Surréalisme, Comédie musicale",
            "<b>Arts visuels</b> — Aquarelle, Peinture à l'huile, BD franco-belge (Moebius), Art Nouveau, Encre & lavis, Low poly, Pixel art",
            "<b>Tendances modernes</b> — Lo-fi rétro (Super 8), Publicité luxe, Nature documentaire (BBC Earth), Found footage, Clip vidéo",
            "<b>Hybride</b> — Multi-style (fusion créative personnalisée)",
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
    ("✦",  "Seedance 2.0"),
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
            "Write and format your screenplay with the help of <b>Claude AI</b> (Anthropic)",
            "Create a shot-by-shot storyboard with camera, actors, locations and prompts",
            "Manage your cast with <b>AI-generated portraits</b> (Nano Banana)",
            "Catalogue locations, props, HMC and vehicles needed for the shoot",
            "Define camera and lens preferences for the film",
            "Choose a <b>visual style</b> that influences all AI generations",
            "Generate Seedance 2.0 videos: T2V, I2V, Extension, Multimodal Reference",
            "Automatically import videos into <b>DaVinci Resolve</b> (Studio required)",
        ),
        _sep_html(),
        _h("Recommended workflow"),
        _ul(
            "<b>1.</b> Create or open a project from the Projects page",
            "<b>2.</b> Write your screenplay, format it with Claude AI",
            "<b>3.</b> Choose a visual style from the screenplay editor",
            "<b>4.</b> Auto-generate characters, locations, HMC, props and vehicles from the screenplay",
            "<b>5.</b> Generate the storyboard with Claude AI, refine shot by shot",
            "<b>6.</b> Configure Seedance Moods for each shot",
            "<b>7.</b> Launch video generation from the storyboard or the Seedance 2.0 tab",
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
            "Go to the <b>Projects</b> page from the sidebar",
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
        _p("The Screenplay page is the heart of PANDORA. Write your script, format it with Claude AI, manage versions, and generate your entire pre-production from a single place."),
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
            "<b>Visual style</b> — influences video, portrait and location generation (Realistic film, Anime, Cyberpunk…)",
            "<b>Film duration</b> — estimated total project duration in minutes and seconds",
            "These settings are always visible so you never forget them",
        ),
        _sep_html(),
        _h("Screenplay formatting (Claude AI)"),
        _ul(
            "Click <b>≡ Format screenplay</b> in the right panel",
            "Claude reformats your text into standard cinema layout:",
            "→ Scene headings: <code>INT. LOCATION — TIME</code> / <code>EXT. LOCATION — TIME</code>",
            "→ Sequence numbers and titles",
            "→ Indented dialogue with centred character name",
            "→ Expressive transitions preserved (FADE TO BLACK, etc.) — no implicit CUT TO",
            "The result appears below — click <b>↩ Replace text</b> to apply it",
            "Immediately undo with <b>↺ Cancel</b> if the result doesn't suit you",
        ),
        _h("AI arrangement (Claude AI)"),
        _ul(
            "Click <b>⊞ Suggest arrangement</b>",
            "Set the <b>intensity</b> (1 to 10) for the desired level of modification:",
            "→ <b>1-2</b>: Spelling and punctuation corrections only",
            "→ <b>3-4</b>: Gentle restructuring, improved reading rhythm",
            "→ <b>5-6</b>: Standard reformulation, narrative consistency and dialogue",
            "→ <b>7-8</b>: Scene restructuring, developing or cutting scenes",
            "→ <b>9-10</b>: Radical rewrite — structure deeply modified",
            "Claude analyses the structure and suggests improvements with explanation",
            "Click <b>✏ Apply suggestions</b> to apply the changes",
        ),
        _h("Versions"),
        _ul(
            "Click <b>✚</b> to save a named version of your screenplay",
            "Select a version from the dropdown to load it <b>instantly</b>",
            "Delete a version with the <b>✕</b> button",
            "Example: Version 1 (first draft), Version 2 (after AI arrangement), Final version",
        ),
        _h("Undo / Redo"),
        _ul(
            "Each Claude modification creates an <b>automatic save point</b>",
            f"Button <b>↩</b> (or {_kbd('Ctrl+Z')}) to undo, <b>↪</b> (or {_kbd('Ctrl+Y')}) to redo",
            "The undo history is kept throughout the session",
        ),
        _sep_html(),
        _h("Generate from screenplay (Claude AI)"),
        _p("Once the screenplay is written, Claude can automatically extract all production elements and add them to the corresponding pages:"),
        _ul(
            "<b>Generate characters</b> — identifies and creates cards for all characters",
            "<b>Generate locations</b> — extracts all INT./EXT. locations in the script",
            "<b>Generate props</b> — lists props and equipment mentioned",
            "<b>Generate HMC</b> — identifies costumes, makeup and hair",
            "<b>Generate vehicles</b> — lists vehicles needed for the shoot",
            "<b>Generate storyboard</b> — creates a complete shot-by-shot breakdown with camera and prompts",
        ),
        _tip("Format your screenplay with Claude <b>before</b> generating elements. A structured screenplay (INT./EXT., consistent character names) gives much better extractions."),
        _warn("If Claude does not respond or returns network errors, <b>disable your VPN</b> — some VPN servers are blocked by the Anthropic API."),
    ])


def _e_storyboard() -> str:
    return "".join([
        _h("Storyboard", 1),
        _p("The Storyboard lists all the shots of the film in chronological order. Each row represents a shot with its complete technical and artistic parameters."),
        _sep_html(),
        _h("Table columns"),
        _ul(
            "<b>Preview</b> — shot mood image generated via Flux T2I (click the cell to generate or pick one)",
            "<b>Seq</b> — sequence number and name",
            "<b>Shot</b> — shot number within the sequence",
            "<b>Action</b> — scene title / action description",
            "<b>Movement</b> — camera movement (Static, Tracking, Pan, Zoom…)",
            "<b>Size</b> — shot size (Close-up, American shot, Wide shot…)",
            "<b>Focal</b> — lens focal length (in mm)",
            "<b>Speed</b> — shooting speed (normal, slow motion, time lapse…)",
            "<b>Location</b> — assigned shooting location",
            "<b>Time</b> — time of day (Day, Night, Dawn, Dusk…)",
            "<b>Props</b> — props used in this shot",
            "<b>Actors</b> — characters present in frame",
            "<b>Axis</b> — camera angle (Face, 3/4, Lateral, Back, High angle…)",
            "<b>Duration</b> — planned shot duration in seconds",
            "<b>Prompt</b> — Seedance 2.0 prompt for video generation",
        ),
        _h("Edit a shot"),
        _ul(
            "Click directly on <b>any cell</b> to edit inline",
            "Click <b>Edit</b> to open the full shot card",
            "The card gives access to all fields: CAMERA, ELEMENTS, STAGING, DURATION, COMMENTS, PROMPT",
            "Drag the <b>⠿</b> grip on the left of a shot to move it and reorder the breakdown",
        ),
        _h("Staging fields"),
        _ul(
            "<b>Camera axis</b> — Face / 3/4 / Lateral 90° / Back / High angle / Low angle",
            "<b>Camera placement</b> — free description of positioning (height, distance, support)",
            "<b>Actor placement</b> — description of where actors are in frame",
            "<b>Entry (IN)</b> — characters entering the shot",
            "<b>Exit (OUT)</b> — characters leaving the shot",
            "<b>Mic</b> — microphone placement for this shot",
        ),
        _h("Mood generation (Seedance Prompt)"),
        _ul(
            "Click <b>✦ Generate Moods</b> to automatically generate Seedance prompts",
            "Claude analyses each shot (size, movement, characters, location) and creates an optimised prompt",
            "Prompts integrate the selected visual style and camera preferences",
            "Regenerate the prompt for a single shot from its edit card",
        ),
        _h("Send to Seedance 2.0"),
        _ul(
            "Click the <b>▶ Generate</b> button on a shot to launch video generation",
            "The video appears in the Preview column once generated",
            "Go to the <b>Seedance 2.0</b> tab for full generation control",
        ),
        _h("Storyboard versions"),
        _ul(
            "Manage multiple versions: final breakdown, short version, editing alternatives…",
            "Dropdown at the top: create, load and delete versions",
        ),
        _tip("Generate the complete storyboard with Claude AI from the Screenplay page first, then refine shot by shot. The auto-generation creates a coherent breakdown that you then polish."),
    ])


def _e_castings() -> str:
    return "".join([
        _h("Cast — Film characters", 1),
        _p("The Cast page centralises all characters with their characteristics, visual references and AI-generated portraits."),
        _sep_html(),
        _h("Create a character"),
        _ul(
            "Click <b>✦ Create a character</b>",
            "Fill in: name, role in the story, approximate age",
            "Describe the <b>physical appearance</b>: height, build, skin tone, eye colour, hairstyle",
            "Describe the <b>psychology</b>: personality traits, motivations, character arcs",
            "Add casting notes to guide the actor search",
        ),
        _h("Generate an AI portrait (Nano Banana)"),
        _ul(
            "Open a character card and click <b>Generate portrait</b>",
            "Nano Banana generates several portraits based on the physical description",
            "Select the portrait that best matches your vision",
            "The selected portrait becomes the character's <b>official visual reference</b>",
            "Regenerate as many times as needed to get the desired result",
        ),
        _warn("Portrait generation requires a Nano Banana API key in Settings. Without a key, mock mode generates coloured placeholder images."),
        _h("Impact on other pages"),
        _ul(
            "Characters appear in the storyboard selection lists",
            "Their portraits are injected as <b>visual references in Seedance 2.0</b>",
            "Claude references their exact names during arrangement and storyboard generation",
        ),
        _tip("Auto-generate characters from your screenplay (Screenplay → Claude AI → Generate characters). Claude identifies all named characters in the script."),
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
        _h("Seedance 2.0 — AI video generation", 1),
        _p("Seedance 2.0 is ByteDance's video generation engine, accessible via fal.ai. PANDORA offers 4 video generation modes adapted to every use case."),
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
        _p("In the <b>Create a new clip</b> and <b>Edit from DaVinci Resolve</b> tabs, "
           "the <b>Generation engine</b> menu gives access to 8 AI video engines. "
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
            "Access all videos from the History panel of the Seedance tab",
            "Videos are stored in <code>data/Seedance/</code> of the project folder",
        ),
        _tip("Prompts are automatically translated to English before being sent to Seedance 2.0. Write your prompts in French — translation is transparent and optimised."),
        _sep_html(),
        _h("Edit from DaVinci Resolve — Batch generation"),
        _p("The <b>Edit from DaVinci Resolve</b> tab lets you bulk-transform clips from your DaVinci timeline with Seedance 2.0. Each clip is uploaded as a video reference and Seedance generates a modified version based on your prompt."),
        _ul(
            "<b>1.</b> In DaVinci: right-click a clip → <b>Flag</b> → color to select it "
            "(no flag = entire timeline is sent)",
            "<b>2.</b> DaVinci → <b>Workspace → Scripts → pandora_send</b> "
            "(or your custom keyboard shortcut)",
            "<b>3.</b> PANDORA displays the received clips in the <b>Edit from DaVinci Resolve</b> tab",
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
            "From the <b>Visual style</b> page in the sidebar — full view with all cards",
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
        self.resize(1080, 700)
        self.setMinimumSize(860, 560)
        self.setStyleSheet(PANDORA_STYLESHEET + f"QDialog{{background:{CP['bg0']};}}")

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
