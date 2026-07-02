"""
ui/assistant_panel.py — Panneau assistant pédagogique contextuel.

Panneau droit collapsible :
  - Tips statiques + guide complet par page (collapsibles)
  - Chat Claude Haiku pour les questions libres
  - Toggle strip 28px toujours visible
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTextEdit, QScrollArea,
)
from PyQt6.QtCore import Qt
from ui.styles import CP


# ── Corpus de contenu par page ─────────────────────────────────────────────────

CORPUS: dict[str, dict] = {
    "projects": {
        "title": "Projets",
        "context": "Gestion des projets de pré-production cinéma.",
        "tips": [
            "Chaque projet a son propre dossier de données isolé.",
            "Renommez un projet en cliquant sur son nom dans la fiche.",
            "Changez de projet depuis cette page sans quitter PANDORA.",
            "Les données sont sauvegardées automatiquement.",
        ],
        "guide": (
            "Créer un projet\n"
            "Cliquez sur '+ Nouveau projet', donnez un nom et choisissez "
            "l'emplacement. PANDORA crée automatiquement la structure de fichiers.\n\n"
            "Ouvrir un projet existant\n"
            "Cliquez sur un projet dans la liste. Toutes les pages se mettent "
            "à jour automatiquement avec les données du projet sélectionné.\n\n"
            "Renommer / supprimer\n"
            "Accédez à la fiche du projet pour renommer. La suppression retire "
            "le projet de la liste uniquement — vos fichiers restent sur le disque.\n\n"
            "Organisation des données\n"
            "Chaque projet stocke scénario, storyboard, castings, décors, "
            "accessoires, HMC, véhicules et clips générés dans son propre dossier."
        ),
    },
    "scenario": {
        "title": "Scénario",
        "context": "Éditeur de scénario avec Claude IA — mise en page, co-écriture, extraction d'éléments.",
        "tips": [
            "Injectez des références visuelles — Claude les analyse et enrichit votre scénario.",
            "'Mise en page PANDORA' structure le texte en blocs plans optimisés pour Seedance.",
            "'Analyse & co-écriture' ouvre le Studio de co-écriture interactif avec Claude.",
            "'Tout Générer' crée personnages, décors, accessoires, HMC, véhicules en une passe.",
            "Versions nommées (✚/✕) et undo/redo (↩/↪) pour revenir à n'importe quel état.",
        ],
        "guide": (
            "Éditeur de scénario\n"
            "Rédigez votre scénario directement dans l'éditeur. Vos modifications sont "
            "sauvegardées automatiquement. La barre du haut regroupe le choix du style "
            "visuel, la gestion des versions nommées (✚ ✕) et la durée du film.\n\n"
            "Références visuelles\n"
            "Ajoutez des images dans '◎ Références visuelles' — photos de lieux, "
            "personnages, moodboards. '◈ Analyser avec Claude' analyse ces images et "
            "enrichit votre scénario en s'inspirant de leurs ambiances et détails.\n\n"
            "Mise en page PANDORA\n"
            "'◈ Mise en page PANDORA' restructure votre texte en blocs plans lisibles "
            "par Seedance : en-têtes INT./EXT., titres de séquences, descriptions d'action. "
            "Format pensé pour la génération IA, pas pour le format Hollywood classique.\n\n"
            "Co-écriture avec Claude\n"
            "'⊞ Analyse & co-écriture' ouvre le Studio de co-écriture. Ajustez l'intensité "
            "(1-10) pour des suggestions légères ou profondes. Claude ne touche que ce que "
            "vous lui demandez — le reste de votre texte est préservé. Vous pouvez joindre "
            "des images à vos messages pour guider les suggestions.\n\n"
            "Générer depuis le scénario\n"
            "Extrayez automatiquement personnages, décors, accessoires, HMC, véhicules et "
            "storyboard depuis votre texte. Chaque extraction propose d'identifier uniquement "
            "ou de générer aussi les images de référence."
        ),
    },
    "storyboard": {
        "title": "Storyboard",
        "context": "Découpage plan par plan avec génération IA intégrée.",
        "tips": [
            "Double-cliquez sur un plan pour éditer : Caméra, Éléments, Mise en scène, Prompt.",
            "'⟳ Synchronisation' aligne les prompts avec les noms actuels du casting/décors.",
            "'✦ Générer les Moods' génère un aperçu visuel pour chaque plan en batch.",
            "Glissez-déposez les plans pour réorganiser le découpage.",
            "Assignez personnages et décors à chaque plan — ils servent de références Seedance.",
        ],
        "guide": (
            "Le tableau de plans\n"
            "Chaque ligne représente un plan de votre film. Vous y voyez d'un coup d'œil "
            "l'aperçu visuel, la séquence, le mouvement caméra, le décor, les personnages, "
            "la durée et le prompt de génération.\n\n"
            "Éditer un plan (double-clic)\n"
            "Ouvrez la fiche complète pour renseigner : les choix caméra (mouvement, valeur "
            "de plan, focale, vitesse), les éléments du plan (décor, personnages, accessoires, "
            "véhicules), la mise en scène (placement caméra et acteurs, axe, entrée/sortie), "
            "la durée et le prompt de génération.\n\n"
            "Synchronisation\n"
            "'⟳ Synchronisation' met à jour tous les prompts si vous avez renommé des "
            "personnages, décors ou accessoires — vos descriptions restent cohérentes.\n\n"
            "Aperçus visuels\n"
            "Cliquez sur la colonne Mood d'un plan pour générer un aperçu visuel. "
            "'✦ Générer les Moods' traite tous les plans en une fois.\n\n"
            "Génération Seedance\n"
            "Cliquez '▶' sur un plan pour lancer la génération. Si des personnages ou "
            "un décor sont assignés, leurs images sont automatiquement utilisées comme "
            "références visuelles pour plus de cohérence.\n\n"
            "Versions nommées\n"
            "Sauvegardez des versions de votre découpage à chaque étape clé pour "
            "pouvoir revenir en arrière à tout moment."
        ),
    },
    "castings": {
        "title": "Castings",
        "context": "Personnages du film — portraits et références Seedance.",
        "tips": [
            "Générez un portrait via Nano Banana depuis la fiche personnage.",
            "Les portraits servent de références visuelles dans Seedance.",
            "Assignez un personnage à un plan depuis le storyboard pour l'inclure dans la génération.",
            "La 'Fiche 4 vues' génère face, 3/4, profil et dos pour plus de cohérence.",
        ],
        "guide": (
            "Créer un personnage\n"
            "Cliquez '+ Ajouter'. Renseignez : nom, âge, rôle, description physique "
            "détaillée (cheveux, yeux, silhouette, traits distinctifs) et costume.\n\n"
            "Générer un portrait\n"
            "Dans la fiche, cliquez 'Générer portrait'. Nano Banana crée une image "
            "de référence. Plus la description physique est précise, plus le portrait "
            "sera fidèle au personnage imaginé.\n\n"
            "Fiche 4 vues\n"
            "Cliquez 'Générer fiche' pour obtenir face, 3/4, profil et dos. "
            "Cette fiche multi-vues donne à Seedance plus de cohérence sur plusieurs plans.\n\n"
            "Assigner à un plan\n"
            "Dans le storyboard, ouvrez un plan et sélectionnez les personnages présents "
            "dans 'Éléments'. Les portraits assignés sont envoyés automatiquement "
            "comme images de référence à Seedance.\n\n"
            "Style visuel\n"
            "Choisissez un style (cinéma, anime, photoréaliste…) pour orienter "
            "l'esthétique des portraits générés. Chaque personnage peut avoir son propre style."
        ),
    },
    "decors": {
        "title": "Décors",
        "context": "Lieux de tournage — visuels de référence pour Seedance.",
        "tips": [
            "Générez une image de référence du décor via Nano Banana.",
            "Chaque décor peut avoir son propre style visuel.",
            "'Sheet 4 vues' génère quatre angles différents du même lieu.",
            "L'image du décor est envoyée automatiquement comme référence visuelle à Seedance.",
        ],
        "guide": (
            "Créer un décor\n"
            "Cliquez '+ Ajouter'. Renseignez : nom, type (INT./EXT.), description "
            "détaillée (architecture, lumière, ambiance, époque, éléments présents).\n\n"
            "Générer l'image de référence\n"
            "Cliquez 'Générer image' pour créer une référence visuelle via Nano Banana. "
            "Soyez précis sur l'ambiance, la lumière et les détails architecturaux.\n\n"
            "Sheet 4 vues\n"
            "Génère quatre angles du décor (entrée, milieu, fond, détail). "
            "Utile pour les scènes complexes avec plusieurs axes caméra.\n\n"
            "Style d'image\n"
            "Chaque décor peut avoir son propre style (cinéma noir et blanc, "
            "photoréaliste, aquarelle…) indépendamment du style global du projet.\n\n"
            "Assigner à un plan\n"
            "Dans l'édition d'un plan storyboard, choisissez le décor dans 'Éléments'. "
            "Son image est envoyée automatiquement comme référence visuelle à Seedance."
        ),
    },
    "accessoires": {
        "title": "Accessoires",
        "context": "Props et objets — références visuelles pour la production.",
        "tips": [
            "Associez un style visuel spécifique à chaque accessoire.",
            "'Générer une variation' crée une alternative de l'image existante.",
            "Les accessoires assignés à un plan sont envoyés comme références visuelles à Seedance.",
            "Décrivez précisément matière, couleur et état (neuf, abîmé, vintage).",
        ],
        "guide": (
            "Créer un accessoire\n"
            "Décrivez précisément l'objet : type, matière, couleur, état (neuf, abîmé, "
            "vintage), époque et contexte d'utilisation. Plus la description est précise, "
            "plus la génération sera fidèle.\n\n"
            "Générer l'image\n"
            "Cliquez 'Générer image' pour créer une référence visuelle de l'accessoire. "
            "Utilisez 'Générer une variation' pour explorer d'autres interprétations.\n\n"
            "Nombre de générations\n"
            "Choisissez combien d'images générer en une fois. Naviguez entre les résultats "
            "avec les flèches du panneau de prévisualisation.\n\n"
            "Assigner à un plan\n"
            "Dans l'édition d'un plan, section 'Éléments', sélectionnez les accessoires "
            "présents. Leurs images sont envoyées à Seedance comme références visuelles."
        ),
    },
    "hmc": {
        "title": "HMC",
        "context": "Habillage, Maquillage, Coiffure — cohérence visuelle.",
        "tips": [
            "HMC = Habillage, Maquillage, Coiffure.",
            "Associez des éléments HMC à des personnages ou séquences.",
            "Générez une image de référence pour chaque élément.",
            "Partagez ces références avec l'équipe costume/maquillage.",
        ],
        "guide": (
            "Rôle du HMC\n"
            "Le HMC documente les éléments visuels portés par les personnages : "
            "vêtements, accessoires de mode, maquillage, coiffure. Indispensable "
            "pour la continuité entre les plans et les jours de tournage.\n\n"
            "Créer un élément HMC\n"
            "Renseignez : type (costume, maquillage, coiffure, bijou…), nom, "
            "description détaillée et le personnage associé.\n\n"
            "Image de référence\n"
            "Générez une image via Nano Banana pour visualiser l'élément. "
            "Ces images peuvent être partagées avec l'équipe costume/maquillage.\n\n"
            "Style d'image\n"
            "Choisissez un style adapté : 'Photoréaliste' pour un rendu proche "
            "du réel, 'Fashion plate' pour un rendu costume de théâtre."
        ),
    },
    "vehicles": {
        "title": "Véhicules",
        "context": "Véhicules du film — références visuelles pour la production.",
        "tips": [
            "Renseignez marque, modèle, année et couleur pour chaque véhicule.",
            "Générez une image de référence via Nano Banana.",
            "Les véhicules assignés à un plan sont envoyés comme références visuelles à Seedance.",
            "Précisez l'état (neuf, accidenté, modifié) dans la description.",
        ],
        "guide": (
            "Créer un véhicule\n"
            "Renseignez : marque, modèle, année, couleur, état (neuf, vieilli, "
            "modifié, accidenté) et toute particularité visuelle (autocollants, "
            "rouille, modification de carrosserie).\n\n"
            "Image de référence\n"
            "Nano Banana génère le véhicule sur fond neutre. Pour les véhicules "
            "historiques ou fictifs, la description est particulièrement importante.\n\n"
            "Assigner à un plan\n"
            "Dans l'édition d'un plan storyboard, sélectionnez le(s) véhicule(s) "
            "présent(s). Leurs images sont envoyées à Seedance comme références visuelles.\n\n"
            "Cohérence entre plans\n"
            "En assignant le même véhicule à plusieurs plans, vous garantissez "
            "une cohérence visuelle dans les séquences de poursuite ou de déplacement."
        ),
    },
    "camera": {
        "title": "Image & Son",
        "context": "Préférences caméra, optiques et chaîne son du projet.",
        "tips": [
            "Définissez la caméra principale, les optiques et le format d'image.",
            "Ces paramètres pré-remplissent les champs techniques du storyboard.",
            "Renseignez le micro et la chaîne son pour préparer le tournage.",
            "Le ratio d'image (1.85:1, 2.39:1) s'applique à tous les plans.",
        ],
        "guide": (
            "Caméra et capteur\n"
            "Choisissez votre caméra principale (ARRI, RED, Sony, Canon…) et le "
            "format de capteur. Ces informations pré-remplissent les champs techniques du storyboard.\n\n"
            "Optiques\n"
            "Renseignez la série d'optiques (Cooke, Leica, Zeiss, Master Prime…) "
            "et les focales disponibles. Le storyboard proposera ces focales dans ses menus.\n\n"
            "Format d'image\n"
            "Définissez le ratio : 1.33:1 (plein cadre), 1.78:1 (16:9), 1.85:1 (flat), "
            "2.39:1 (scope). S'applique à la génération Seedance et à l'export.\n\n"
            "Chaîne son\n"
            "Documentez micros, perches, enregistreurs. Ces notes préparent la "
            "coordination avec le chef opérateur son."
        ),
    },
    "doublage": {
        "title": "Doublage",
        "context": "Synthèse vocale et clonage vocal pour la post-production.",
        "tips": [
            "ElevenLabs génère des voix naturalistes multilingues depuis votre texte.",
            "F5-TTS clone n'importe quelle voix depuis un court échantillon audio.",
            "Le français est pris en charge par ElevenLabs ; F5-TTS fonctionne mieux en anglais.",
            "Les fichiers audio générés s'importent directement dans DaVinci Resolve.",
        ],
        "guide": (
            "Moteurs disponibles\n"
            "— ElevenLabs Turbo v2.5 : synthèse vocale de haute qualité avec "
            "sélection de voix préenregistrées (anglais, français et plus). "
            "Service payant, clé API requise.\n"
            "— F5-TTS Clonage : clone une voix depuis un échantillon audio de "
            "quelques secondes. Entraîné principalement sur l'anglais et le chinois "
            "— le français peut avoir un léger accent.\n\n"
            "Workflow recommandé\n"
            "1. Écrivez le texte à doubler dans l'éditeur.\n"
            "2. Choisissez un moteur : ElevenLabs pour la qualité FR, "
            "F5-TTS pour reproduire une voix spécifique.\n"
            "3. Générez et écoutez le rendu.\n"
            "4. Importez dans DaVinci Resolve pour synchroniser avec la vidéo.\n\n"
            "Détourage automatique\n"
            "Supprimez le fond d'une image ou d'une vidéo automatiquement pour "
            "créer des fonds transparents, sans avoir besoin de fond vert."
        ),
    },
    "seedance": {
        "title": "Studio IA",
        "context": ("Génération vidéo IA, sound design et upscaling — 7 onglets : "
                    "Storyboard, Modifier, Génération directe, Sound Design, "
                    "Upscaling, Vidéothèque, Historique."),
        "tips": [
            "Décrivez la scène en français, la traduction est automatique.",
            "Moteur recommandé : Seedance 2.0 — les meilleurs résultats du workflow.",
            "Si des personnages/décors sont assignés, le mode référence s'active.",
            "Le bouton '▶▶ Lancer la file d'attente' lance TOUTES les générations.",
            "'Ouvrir le dossier' est toujours actif — même avant de générer.",
        ],
        "guide": (
            "Générer depuis Storyboard\n"
            "Sélectionnez un ou plusieurs plans et cliquez '▶▶ Lancer la file "
            "d'attente'. Le prompt de chaque plan est traduit en anglais et les "
            "références (personnages, décor, accessoires) partent automatiquement. "
            "Le menu Moteur affiche les capacités réelles de chacun (raccord i2v, "
            "réfs) — Seedance 2.0 est marqué « recommandé » : c'est lui qui donne "
            "les meilleurs résultats sur ce workflow.\n\n"
            "Modifier des clips\n"
            "Importez des clips existants (ou recevez-les depuis DaVinci via "
            "pandora_send) et modifiez-les avec un prompt. Seedance préserve la "
            "structure visuelle ; LatentSync resynchronise les lèvres au besoin.\n\n"
            "Génération directe\n"
            "Accès direct aux moteurs (Seedance, Happy Horse, Kling, Veo 3.1, "
            "PixVerse, Sora 2…) avec leurs paramètres et tarifs spécifiques, "
            "sans passer par le storyboard.\n\n"
            "Sound Design (nouveau)\n"
            "Deux modes Mirelo SFX : un prompt son → SFX/ambiance, ou un clip "
            "vidéo → bande-son synchronisée sur l'image (~$0.01/s).\n\n"
            "Upscaling (nouveau)\n"
            "File d'attente de clips à monter en résolution (Topaz ou SeedVR2, "
            "×2/×4). La sortie garde le MÊME NOM que la source : dans DaVinci, "
            "un simple Relink Media remplace vos clips par la version haute "
            "résolution. 'Importer la Vidéothèque' charge tout en un clic.\n\n"
            "Vidéothèque\n"
            "Galerie de tous les clips générés. Cliquez pour prévisualiser, "
            "envoyer vers 'Modifier des clips' ou ouvrir le fichier.\n\n"
            "Tarifs\n"
            "La génération est facturée via fal.ai. Consultez le Manuel "
            "d'utilisation (en haut à gauche) pour le comparatif par moteur."
        ),
    },
    "settings": {
        "title": "Paramètres",
        "context": "Clés API et préférences globales de PANDORA.",
        "tips": [
            "Clé fal.ai : Seedance, Kling, Veo 3.1, PixVerse, Flux, SFX1.",
            "Clé Anthropic : assistant IA, scénario, traduction des prompts.",
            "Clé Nano Banana : portraits et images d'éléments.",
            "Le dossier de sortie définit où les vidéos sont enregistrées.",
        ],
        "guide": (
            "Clé fal.ai\n"
            "Créez un compte sur fal.ai et générez une clé API dans votre "
            "tableau de bord. Donne accès à tous les moteurs vidéo (Seedance, "
            "Kling, Veo, PixVerse, Sora, Wan…) et aux modèles d'image (Flux).\n\n"
            "Clé Anthropic\n"
            "Créez un compte sur console.anthropic.com. Utilisée pour : "
            "formatage du scénario, génération du storyboard, traduction des "
            "prompts, et l'assistant pédagogique.\n\n"
            "Clé Nano Banana\n"
            "Dédiée à la génération de portraits de personnages et d'images "
            "d'éléments (décors, accessoires, HMC, véhicules).\n\n"
            "Dossier de sortie\n"
            "Choisissez où vos vidéos générées seront enregistrées. Par défaut, "
            "elles sont sauvegardées dans votre dossier Vidéos, sous-dossier PANDORA. "
            "Vous pouvez rediriger vers votre NAS ou dossier de projet DaVinci.\n\n"
            "Mode sans clé\n"
            "Sans clé fal.ai, PANDORA fonctionne en mode démonstration — les générations "
            "sont simulées sans consommation de crédits, pour découvrir l'interface."
        ),
    },

    # ── PANDORA | Live ───────────────────────────────────────────────────────
    "live_conducteur": {
        "title": "Conducteur",
        "context": "Trame écrite de la performance — musiques du set, façade, IA.",
        "tips": [
            "Ajoutez les musiques du set : BPM, énergie et drops nourrissent l'IA.",
            "Mode Mapping : isolez la façade sur fond noir (détourage intégré).",
            "« Mise en page PANDORA » produit un PROMPT VIDÉO + un PROMPT SON par plan.",
            "« ⤢ Rouvrir la fenêtre » est tout en bas, sous « Tout générer ».",
        ],
        "guide": (
            "Le Conducteur\n"
            "Écrivez la trame du show (actes, moments, ambiances). L'IA s'appuie "
            "dessus pour l'arrangement, la mise en page et le découpage.\n\n"
            "Musiques du set\n"
            "Ajoutez vos morceaux : l'analyse locale extrait BPM, énergie et drops. "
            "Cette timeline musicale guide les durées des plans et les prompts son.\n\n"
            "Façade (mode Mapping)\n"
            "La photo de la façade isolée sur fond noir sert de canevas aux moods, "
            "de masque de confinement et de base au calage Resolume.\n\n"
            "Générer\n"
            "« Analyse & co-écriture » (analyse + suggestions affinables), « Mise en page "
            "PANDORA » (actes/plans + prompts), « Générer le découpage » (séquence "
            "Live ou Mapping), ou « ⚡ Tout générer » pour enchaîner."
        ),
    },
    "live_casting": {
        "title": "Casting",
        "context": "Performers de la performance, avec portraits IA.",
        "tips": [
            "Identifiés automatiquement depuis le Conducteur (« Générer les personnages »).",
            "Les portraits partent en référence à la génération des clips.",
        ],
        "guide": "",
    },
    "live_accessoires": {
        "title": "Accessoires",
        "context": "Objets de scène, avec images de référence IA.",
        "tips": [
            "Identifiés depuis le Conducteur ou ajoutés à la main.",
            "Envoyés en référence aux moteurs vidéo pour la cohérence.",
        ],
        "guide": "",
    },
    "live_vehicules": {
        "title": "Véhicules",
        "context": "Véhicules de la performance, avec images de référence IA.",
        "tips": [
            "Identifiés depuis le Conducteur ou ajoutés à la main.",
            "Envoyés en référence aux moteurs vidéo pour la cohérence.",
        ],
        "guide": "",
    },
    "live_studio": {
        "title": "Studio IA — Live",
        "context": ("Production des clips — 7 onglets : Séquences, Génération directe, "
                    "Modifier, Sound Design, Upscaling, Vidéothèque, Historique."),
        "tips": [
            "Conducteur visuel : clic = un plan, Ctrl/Maj/lasso = file d'attente.",
            "Moteur recommandé : Seedance 2.0 (capacités affichées dans le menu).",
            "'▶▶ Lancer la file d'attente' partout — annulable à tout moment.",
            "'Ouvrir le dossier' est toujours actif, même avant de générer.",
            "Vidéothèque : lecture, envoi vers Modifier / Upscaling / → Resolume.",
        ],
        "guide": (
            "Générer depuis Séquences\n"
            "Sélectionnez les plans dans le Conducteur visuel (Ctrl/Maj/lasso) et "
            "lancez la file. Mode Mapping : façade en référence, keyframes de moods "
            "(raccords exacts), contenu confiné dans la silhouette.\n\n"
            "Sound Design\n"
            "Le Conducteur charge le prompt SON et la durée de chaque plan ; chaque "
            "ambiance est conformée à la durée calée. Option « Assembler la "
            "bande-son (durée exacte) » : une piste = la timeline.\n\n"
            "Upscaling\n"
            "File en petits carrés, Topaz/SeedVR2, ×2/×4 — la sortie garde le même "
            "nom que la source (relink direct).\n\n"
            "Vidéothèque\n"
            "Tous les clips du projet ; « → Resolume » pré-charge la file du "
            "contrôleur."
        ),
    },
    "live_sequences": {
        "title": "Séquences",
        "context": "Découpage de la performance en plans calés sur la musique.",
        "tips": [
            "« Caler sur la musique » quantise les durées en MESURES (BPM du set).",
            "« Générer les Moods » crée une image d'ancrage par plan.",
            "Maj+clic = plage de plans, lasso souris = sélection visuelle.",
            "Colonnes dédiées : TC, Musique, BPM, Transition, Prompt vidéo/son.",
        ],
        "guide": (
            "Caler sur la musique\n"
            "Quantise la durée de chaque plan en MESURES du morceau assigné et "
            "attire les cuts sur les DROPS — calcul local, exact. Les clips générés "
            "sont ensuite conformés à ces durées (aucune dérive en timeline).\n\n"
            "Moods\n"
            "Une image d'ancrage par plan. En Mapping, le mood est généré SUR la "
            "façade et sert de keyframe de raccord entre plans."
        ),
    },
    "live_seq_mapping": {
        "title": "Séquences Mapping",
        "context": "Séquence continue projetée sur une façade (caméra fixe).",
        "tips": [
            "La façade isolée sur fond noir sert de canevas ET de masque.",
            "Raccords par keyframes : le mood du plan N+1 termine le plan N.",
            "Le contenu reste confiné dans la silhouette VISIBLE, à échelle exacte.",
            "« ▱ Calage Resolume » : preset Advanced Output + mire du bâtiment.",
        ],
        "guide": (
            "Le principe\n"
            "Une séquence continue sur façade VERROUILLÉE : caméra fixe, l'architecture "
            "visible reste à position et échelle exactes (la projection se superpose "
            "au vrai bâtiment). La façade peut disparaître, changer de matière ou "
            "être recouverte — jamais zoomer ni glisser.\n\n"
            "Calage Resolume\n"
            "Le polygone de la façade est extrait automatiquement du masque et écrit "
            "en preset Advanced Output, avec une mire de calage propre au bâtiment."
        ),
    },
    "mapping": {
        "title": "Mapping vidéo",
        "context": "Séquences projetées sur une façade (caméra fixe, raccords par keyframes).",
        "tips": [
            "La façade isolée sur fond noir (BiRefNet) sert de canevas ET de masque.",
            "« ▱ Calage Resolume » génère le preset Advanced Output + la mire du bâtiment.",
            "Le contenu reste confiné DANS la silhouette visible sur la photo.",
        ],
        "guide": "",
    },
    "resolume": {
        "title": "Resolume",
        "context": "Contrôleur Resolume — envoi des clips dans les slots via l'API REST.",
        "tips": [
            "Activez « Enable Webserver & REST API » dans Resolume (port 8080).",
            "Glissez-déposez les clips de la bibliothèque vers la grille de slots.",
            "« Une couche par acte » répartit SQ1/SQ2/… sur des couches distinctes.",
            "Le mode show enchaîne les clips au tempo (Play Once & Hold + Autopilot).",
        ],
        "guide": (
            "Connexion\n"
            "Resolume → Préférences → Webserver → « Enable Webserver & REST API » "
            "(port 8080), puis « Connecter » — le point passe au vert.\n\n"
            "Envoi du set\n"
            "« Envoyer vers Resolume » charge les clips dans les slots : tri naturel "
            "(SQ1_P1, SQ1_P2…), colonnes ajoutées automatiquement, BPM de la compo "
            "réglé sur le set. « Une couche par acte » répartit les séquences.\n\n"
            "Mode show\n"
            "Chaque clip passe en Play Once & Hold + Beat Snap + Autopilot Next : "
            "le set s'enchaîne seul, calé au tempo.\n\n"
            "Manipulation directe\n"
            "Drag & drop multi vers les slots, Maj+clic = vider un slot, "
            "« Vider la couche » dans l'en-tête de la grille."
        ),
    },
    "live_settings": {
        "title": "Paramètres",
        "context": "Connexion Resolume + clés API (partagées avec Cinéma) + assistant IA.",
        "tips": [
            "Hôte/port Resolume + test de connexion en tête de page.",
            "Les clés fal.ai et Anthropic sont partagées avec PANDORA | Cinéma.",
            "Choisissez l'assistant IA : Claude, Fable 5, Mistral ou Ollama local.",
        ],
        "guide": "",
    },
}

_DEFAULT_CORPUS = {
    "title": "PANDORA",
    "context": "Logiciel de pré-production cinéma pour DaVinci Resolve.",
    "tips": [
        "Naviguez entre les pages depuis la barre en BAS de la fenêtre (façon DaVinci).",
        "Les données sont sauvegardées automatiquement (Ctrl+S = sauvegarde manuelle).",
        "Manuel d'utilisation et Nous contacter : en haut à gauche de la fenêtre.",
        "Paramètres : tout en bas à droite, à côté des onglets.",
    ],
    "guide": (
        "Bienvenue dans PANDORA\n"
        "PANDORA est un outil de pré-production cinéma intégré à DaVinci Resolve. "
        "Il couvre l'ensemble du pipeline : scénario, storyboard, castings, décors, "
        "accessoires, HMC, véhicules, génération vidéo IA, sound design et upscaling.\n\n"
        "La nouvelle interface\n"
        "La navigation vit en BAS de la fenêtre, comme la barre de pages de DaVinci "
        "Resolve : les icônes des pages au centre, les drapeaux FR/EN à gauche, "
        "Paramètres tout à droite. Le Manuel d'utilisation (rouge) et Nous contacter "
        "(vert) sont en haut à gauche. Cet assistant vit à GAUCHE de l'écran — "
        "la poignée « IA » l'ouvre et le ferme. Les pages occupent toute la largeur.\n\n"
        "Démarrage rapide\n"
        "1. Créez ou ouvrez un projet depuis la page Projets.\n"
        "2. Rédigez votre scénario et utilisez l'IA pour le mettre en page.\n"
        "3. Générez le storyboard depuis le scénario.\n"
        "4. Ajoutez personnages, décors et accessoires avec images de référence.\n"
        "5. Générez vos clips vidéo depuis Studio IA (Seedance 2.0 recommandé).\n"
        "6. Sonorisez (Sound Design) et montez en résolution (Upscaling) au besoin."
    ),
}


# ── Panneau assistant ──────────────────────────────────────────────────────────

class AssistantPanel(QWidget):
    """Panneau assistant contextuel avec corpus par page et chat Haiku.
    header_height : hauteur de l'en-tête — Live passe 60 pour ALIGNER la ligne
    de l'assistant sur celle des bandeaux de pages (défaut 76 = Cinéma)."""

    def __init__(self, header_height: int = 76):
        super().__init__()
        self._history:  list[dict] = []
        self._worker    = None
        self._page_key  = ""
        self._corpus    = _DEFAULT_CORPUS
        self._ai_enabled: bool = False

        self.setFixedWidth(258)
        self.setStyleSheet(f"background:{CP['bg1']};")

        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)

        # ── En-tête ────────────────────────────────────────────────────────────
        header = QWidget()
        header.setFixedHeight(header_height)
        self._header = header
        header.setStyleSheet(
            f"background:{CP['bg2']};border-bottom:1px solid {CP['border']};"
        )
        hl = QHBoxLayout(header)
        hl.setContentsMargins(14, 0, 10, 0)
        hl.setSpacing(8)

        ico = QLabel("✦")
        ico.setStyleSheet(
            f"color:{CP['accent']};font-size:14px;background:transparent;"
        )
        hl.addWidget(ico)

        self._title_lbl = QLabel("Guide")
        self._title_lbl.setStyleSheet(
            f"color:{CP['text_primary']};font-size:13px;font-weight:700;"
            f"background:transparent;"
        )
        hl.addWidget(self._title_lbl)
        hl.addStretch()

        # Bascule à deux états : « Guide » (manuel hors-ligne complet, sans IA) ou
        # « IA » (discussion sur le logiciel). En mode IA, le guide est masqué et
        # remplacé par un court texte d'intro — il reste consultable en mode Guide.
        def _seg_btn(text):
            b = QPushButton(text)
            b.setFixedHeight(22)
            b.setMinimumWidth(44)
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            return b
        self._btn_mode_guide = _seg_btn("Guide")
        self._btn_mode_ia    = _seg_btn("IA")
        self._btn_mode_guide.setToolTip("Guide hors-ligne — aide & pédagogie, sans IA")
        self._btn_mode_ia.setToolTip(
            "Discuter avec l'IA au sujet du logiciel (utilise des crédits Anthropic)")
        self._btn_mode_guide.clicked.connect(lambda: self._set_mode(False))
        self._btn_mode_ia.clicked.connect(lambda: self._set_mode(True))
        hl.addWidget(self._btn_mode_guide)
        hl.addWidget(self._btn_mode_ia)

        btn_clear = QPushButton("✕")
        btn_clear.setFixedSize(20, 20)
        btn_clear.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_clear.setToolTip("Effacer la conversation")
        btn_clear.setStyleSheet(
            f"QPushButton{{background:transparent;color:{CP['text_dim']};"
            f"border:none;font-size:10px;font-weight:700;}}"
            f"QPushButton:hover{{color:{CP['text_primary']};}}"
        )
        btn_clear.clicked.connect(self._clear_chat)
        hl.addWidget(btn_clear)
        lay.addWidget(header)

        # ── Zone tips + guide (scrollable) ────────────────────────────────────
        self._tips_outer = QScrollArea()
        self._tips_outer.setWidgetResizable(True)
        self._tips_outer.setFrameStyle(0)
        self._tips_outer.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._tips_outer.setStyleSheet(
            f"QScrollArea{{background:transparent;"
            f"border:none;border-bottom:1px solid {CP['border']};}}"
            f"QScrollBar:vertical{{width:3px;background:transparent;}}"
            f"QScrollBar::handle:vertical{{background:{CP['border_bright']};"
            f"border-radius:1px;min-height:20px;}}"
            f"QScrollBar::add-line:vertical,QScrollBar::sub-line:vertical{{height:0px;}}"
        )

        tips_inner = QWidget()
        tips_inner.setStyleSheet("background:transparent;")
        tips_lay = QVBoxLayout(tips_inner)
        tips_lay.setContentsMargins(12, 10, 12, 10)
        tips_lay.setSpacing(6)

        self._page_lbl = QLabel("PANDORA")
        self._page_lbl.setStyleSheet(
            f"color:{CP['accent']};font-size:9px;font-weight:700;"
            f"letter-spacing:2px;background:transparent;"
        )
        tips_lay.addWidget(self._page_lbl)

        self._context_lbl = QLabel()
        self._context_lbl.setWordWrap(True)
        self._context_lbl.setStyleSheet(
            f"color:{CP['text_dim']};font-size:10px;font-style:italic;"
            f"background:transparent;"
        )
        tips_lay.addWidget(self._context_lbl)

        _sep = QLabel()
        _sep.setFixedHeight(1)
        _sep.setStyleSheet(f"background:{CP['border']};")
        tips_lay.addWidget(_sep)

        # ── CONSEILS — collapsible ─────────────────────────────────────────────
        self._conseils_open = True
        self._btn_conseils = QPushButton("▼  CONSEILS")
        self._btn_conseils.setFlat(True)
        self._btn_conseils.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_conseils.setStyleSheet(
            f"QPushButton{{background:transparent;color:{CP['text_dim']};"
            f"font-size:8px;font-weight:700;letter-spacing:2px;"
            f"border:none;text-align:left;padding:0;}}"
            f"QPushButton:hover{{color:{CP['accent']};}}"
        )
        self._btn_conseils.clicked.connect(self._toggle_conseils)
        tips_lay.addWidget(self._btn_conseils)

        self._tips_lbl = QLabel()
        self._tips_lbl.setWordWrap(True)
        self._tips_lbl.setStyleSheet(
            f"color:{CP['text_secondary']};font-size:10px;background:transparent;"
        )
        tips_lay.addWidget(self._tips_lbl)

        # ── GUIDE COMPLET — collapsible ────────────────────────────────────────
        _guide_sep = QLabel()
        _guide_sep.setFixedHeight(1)
        _guide_sep.setStyleSheet(f"background:{CP['border']};margin-top:2px;")
        tips_lay.addWidget(_guide_sep)

        self._guide_open = True
        self._btn_guide = QPushButton("▼  GUIDE COMPLET")
        self._btn_guide.setFlat(True)
        self._btn_guide.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_guide.setStyleSheet(
            f"QPushButton{{background:transparent;color:{CP['accent_dim']};"
            f"font-size:8px;font-weight:700;letter-spacing:2px;"
            f"border:none;text-align:left;padding:0;}}"
            f"QPushButton:hover{{color:{CP['accent']};}}"
        )
        self._btn_guide.clicked.connect(self._toggle_guide)
        tips_lay.addWidget(self._btn_guide)

        self._guide_lbl = QLabel()
        self._guide_lbl.setWordWrap(True)
        self._guide_lbl.setVisible(True)
        self._guide_lbl.setStyleSheet(
            f"color:{CP['text_secondary']};font-size:10px;background:transparent;"
            f"line-height:1.4;"
        )
        tips_lay.addWidget(self._guide_lbl)

        tips_lay.addStretch()
        self._tips_outer.setWidget(tips_inner)
        self._tips_outer.setMaximumHeight(16777215)
        lay.addWidget(self._tips_outer)

        # Texte d'intro affiché À LA PLACE du guide en mode IA (le guide complet
        # reste accessible en mode Guide — inutile de le tronquer/scroller ici).
        self._ia_intro = QLabel(
            "Vous êtes désormais en discussion avec l'IA au sujet du logiciel.\n\n"
            "Vous pouvez poser des questions pour la compréhension du logiciel.")
        self._ia_intro.setWordWrap(True)
        self._ia_intro.setStyleSheet(
            f"color:{CP['text_secondary']};font-size:11px;line-height:150%;"
            f"padding:14px 14px 6px 14px;background:transparent;")
        self._ia_intro.setVisible(False)
        lay.addWidget(self._ia_intro)

        # ── Zone de chat ───────────────────────────────────────────────────────
        chat_scroll = QScrollArea()
        chat_scroll.setWidgetResizable(True)
        chat_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        chat_scroll.setStyleSheet(
            f"QScrollArea{{background:{CP['bg1']};border:none;}}"
            f"QScrollBar:vertical{{width:4px;background:{CP['bg2']};}}"
            f"QScrollBar::handle:vertical{{background:{CP['border_bright']};border-radius:2px;}}"
        )
        self._chat_container = QWidget()
        self._chat_container.setStyleSheet(f"background:{CP['bg1']};")
        self._chat_lay = QVBoxLayout(self._chat_container)
        self._chat_lay.setContentsMargins(10, 14, 10, 8)
        self._chat_lay.setSpacing(8)
        self._chat_lay.addStretch()
        chat_scroll.setWidget(self._chat_container)
        self._chat_scroll = chat_scroll
        lay.addWidget(chat_scroll, 1)

        # ── Input ──────────────────────────────────────────────────────────────
        input_frame = QWidget()
        input_frame.setStyleSheet(
            f"background:{CP['bg2']};border-top:1px solid {CP['border']};"
        )
        input_lay = QVBoxLayout(input_frame)
        input_lay.setContentsMargins(10, 8, 10, 10)
        input_lay.setSpacing(6)

        self._disabled_notice = QLabel(
            "L'assistant IA est désactivé.\n"
            "Activez-le via « IA ○ » pour poser des questions.\n"
            "(Utilise des crédits Anthropic)"
        )
        self._disabled_notice.setWordWrap(True)
        self._disabled_notice.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._disabled_notice.setStyleSheet(
            f"color:{CP['text_dim']};font-size:10px;font-style:italic;"
            f"padding:8px 4px;background:transparent;"
        )
        input_lay.addWidget(self._disabled_notice)

        self._input = QTextEdit()
        self._input.setPlaceholderText("Posez une question sur cette page…")
        self._input.setFixedHeight(56)
        self._input.setStyleSheet(
            f"QTextEdit{{background:{CP['bg3']};border:1px solid {CP['border']};"
            f"border-radius:6px;color:{CP['text_primary']};font-size:11px;"
            f"padding:5px 8px;}}"
            f"QTextEdit:focus{{border-color:{CP['accent_dim']};}}"
        )
        self._input.setVisible(False)
        input_lay.addWidget(self._input)

        self._btn_ask = QPushButton("✦  Demander")
        self._btn_ask.setMinimumHeight(32)
        self._btn_ask.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_ask.setStyleSheet(
            f"QPushButton{{background:{CP['accent']};color:#07080f;"
            f"border:none;border-radius:6px;font-size:11px;font-weight:700;"
            f"padding:0 12px;}}"
            f"QPushButton:hover{{background:#6eded6;}}"
            f"QPushButton:pressed{{background:{CP['accent_dim']};color:#fff;}}"
            f"QPushButton:disabled{{background:{CP['bg3']};color:{CP['text_dim']};}}"
        )
        self._btn_ask.clicked.connect(self._on_ask)
        self._btn_ask.setVisible(False)
        input_lay.addWidget(self._btn_ask)

        self._input_frame = input_frame
        lay.addWidget(input_frame)

        self._update_tips()
        self._apply_ai_state()

    # ── API publique ───────────────────────────────────────────────────────────

    def set_context(self, page_key: str):
        if page_key == self._page_key:
            return
        self._page_key = page_key
        self._corpus   = CORPUS.get(page_key, _DEFAULT_CORPUS)
        self._update_tips()

    # ── Activation IA ─────────────────────────────────────────────────────────

    def _seg_style(self, active: bool) -> str:
        """Style d'un segment du bouton double Guide/IA (actif = accent plein)."""
        if active:
            return (f"QPushButton{{background:{CP['accent']};color:#07080f;"
                    f"border:1px solid {CP['accent']};border-radius:5px;"
                    f"font-size:9px;font-weight:800;padding:0 9px;}}")
        return (f"QPushButton{{background:transparent;color:{CP['text_dim']};"
                f"border:1px solid {CP['border']};border-radius:5px;"
                f"font-size:9px;font-weight:700;padding:0 9px;}}"
                f"QPushButton:hover{{color:{CP['accent']};border-color:{CP['accent_dim']};}}")

    def _set_mode(self, ia: bool):
        self._ai_enabled = ia
        self._apply_ai_state()

    def _toggle_ai(self):   # compat : ancien point d'entrée éventuel
        self._set_mode(not self._ai_enabled)

    def _apply_ai_state(self):
        on = self._ai_enabled
        self._btn_mode_guide.setStyleSheet(self._seg_style(not on))
        self._btn_mode_ia.setStyleSheet(self._seg_style(on))
        # Mode Guide : manuel complet visible (pas de troncature). Mode IA : guide
        # masqué, remplacé par le texte d'intro + la zone de discussion.
        self._tips_outer.setVisible(not on)
        self._ia_intro.setVisible(on)
        self._disabled_notice.setVisible(False)   # obsolète (bascule explicite)
        self._input_frame.setVisible(on)
        self._input.setVisible(on)
        self._btn_ask.setVisible(on)
        self._chat_scroll.setVisible(on)

    # ── Collapsibles ──────────────────────────────────────────────────────────

    def _toggle_conseils(self):
        self._conseils_open = not self._conseils_open
        self._tips_lbl.setVisible(self._conseils_open)
        self._btn_conseils.setText(
            ("▼" if self._conseils_open else "▶") + "  CONSEILS"
        )

    def _toggle_guide(self):
        self._guide_open = not self._guide_open
        self._guide_lbl.setVisible(self._guide_open)
        self._btn_guide.setText(
            ("▼" if self._guide_open else "▶") + "  GUIDE COMPLET"
        )

    # ── Interne ────────────────────────────────────────────────────────────────

    def _update_tips(self):
        from core.i18n import translate
        self._page_lbl.setText(translate(self._corpus["title"]).upper())
        self._context_lbl.setText(translate(self._corpus.get("context", "")))
        tips = self._corpus.get("tips", [])
        self._tips_lbl.setText("\n".join(f"· {translate(t)}" for t in tips))
        guide = self._corpus.get("guide", "")
        self._guide_lbl.setText(translate(guide))
        self._btn_guide.setVisible(bool(guide))

    def _on_ask(self):
        if not self._ai_enabled:
            return
        if self._worker and self._worker.isRunning():
            return
        question = self._input.toPlainText().strip()
        if not question:
            return

        self._add_bubble("user", question)
        self._input.clear()
        self._btn_ask.setEnabled(False)
        self._btn_ask.setText("…")

        from api.assistant import AssistantWorker
        self._worker = AssistantWorker(
            question=question,
            page_context=self._corpus.get("context", ""),
            history=list(self._history),
        )
        self._worker.finished.connect(self._on_answer)
        self._worker.failed.connect(self._on_error)
        self._worker.start()

        self._history.append({"role": "user", "content": question})

    def _on_answer(self, text: str):
        self._add_bubble("assistant", text)
        self._history.append({"role": "assistant", "content": text})
        self._btn_ask.setEnabled(True)
        self._btn_ask.setText("✦  Demander")

    def _on_error(self, err: str):
        self._add_bubble("assistant", f"Erreur : {err}")
        self._btn_ask.setEnabled(True)
        self._btn_ask.setText("✦  Demander")

    def _add_bubble(self, role: str, text: str):
        is_user = (role == "user")
        bubble = QWidget()
        bubble.setStyleSheet(
            f"background:{'rgba(78,205,196,0.10)' if is_user else CP['bg2']};"
            f"border-radius:8px;"
        )
        b_lay = QVBoxLayout(bubble)
        b_lay.setContentsMargins(10, 7, 10, 7)
        b_lay.setSpacing(3)

        lbl_role = QLabel("Vous" if is_user else "✦ Assistant")
        lbl_role.setStyleSheet(
            f"color:{CP['accent'] if is_user else CP['text_dim']};"
            f"font-size:9px;font-weight:700;letter-spacing:1px;background:transparent;"
        )
        b_lay.addWidget(lbl_role)

        lbl_text = QLabel(text)
        lbl_text.setWordWrap(True)
        lbl_text.setStyleSheet(
            f"color:{CP['text_primary']};font-size:11px;background:transparent;"
        )
        b_lay.addWidget(lbl_text)

        self._chat_lay.insertWidget(self._chat_lay.count() - 1, bubble)

        from PyQt6.QtCore import QTimer
        QTimer.singleShot(60, lambda: self._chat_scroll.verticalScrollBar().setValue(
            self._chat_scroll.verticalScrollBar().maximum()
        ))

    def _clear_chat(self):
        self._history.clear()
        while self._chat_lay.count() > 1:
            item = self._chat_lay.takeAt(0)
            if item and item.widget():
                item.widget().deleteLater()


# ── Toggle strip ───────────────────────────────────────────────────────────────

class AssistantToggleStrip(QWidget):
    """Bande verticale 28px pour ouvrir/fermer le panneau assistant.
    side="right" (défaut — Cinéma) ou "left" (Live) : flèches en miroir."""

    def __init__(self, panel: AssistantPanel, side: str = "right"):
        super().__init__()
        self._panel  = panel
        self._side   = "left" if side == "left" else "right"
        self._open   = panel.isVisible()
        self.setFixedWidth(42)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setToolTip("Ouvrir / fermer le Guide (aide & pédagogie d'utilisation)")
        self.setStyleSheet(f"background:{CP['bg1']};")

        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)
        lay.addStretch()

        self._ia_lbl = QLabel("GUIDE")
        self._ia_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._ia_lbl.setFixedWidth(42)
        self._ia_lbl.setStyleSheet(
            f"color:{CP['accent']};font-size:7px;font-weight:900;"
            f"letter-spacing:0.5px;background:transparent;"
        )
        lay.addWidget(self._ia_lbl)

        lay.addSpacing(6)

        self._arrow = QLabel(self._arrow_char())
        self._arrow.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._arrow.setFixedWidth(42)
        self._arrow.setStyleSheet(
            f"color:{CP['accent']};font-size:18px;font-weight:700;background:transparent;"
        )
        lay.addWidget(self._arrow)
        lay.addStretch()

    def _arrow_char(self) -> str:
        if self._side == "left":
            return "❯" if self._open else "❮"
        return "❮" if self._open else "❯"

    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            self._open = not self._open
            self._panel.setVisible(self._open)
            self._arrow.setText(self._arrow_char())

    def enterEvent(self, e):
        self._ia_lbl.setStyleSheet(
            f"color:#ffffff;font-size:7px;font-weight:900;"
            f"letter-spacing:0.5px;background:transparent;"
        )
        self._arrow.setStyleSheet(
            f"color:#ffffff;font-size:18px;font-weight:700;background:transparent;"
        )

    def leaveEvent(self, e):
        self._ia_lbl.setStyleSheet(
            f"color:{CP['accent']};font-size:7px;font-weight:900;"
            f"letter-spacing:0.5px;background:transparent;"
        )
        self._arrow.setStyleSheet(
            f"color:{CP['accent']};font-size:18px;font-weight:700;background:transparent;"
        )
