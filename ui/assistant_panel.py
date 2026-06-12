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
            "'Proposer un arrangement' ouvre le Studio de co-écriture interactif avec Claude.",
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
            "'⊞ Proposer un arrangement' ouvre le Studio de co-écriture. Ajustez l'intensité "
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
        "context": "Génération vidéo IA — 13 moteurs dont Seedance, Kling, Veo 3.1.",
        "tips": [
            "T2V : décrivez la scène en français, la traduction est automatique.",
            "Si des personnages/décors sont assignés, le mode référence s'active.",
            "Génération directe : 13 moteurs (Kling v3 Pro, Veo 3.1, Sora 2…).",
            "La vidéothèque centralise tous les clips avec prévisualisation.",
            "Cochez 'Import auto' pour envoyer les clips dans DaVinci Resolve.",
        ],
        "guide": (
            "Générer depuis Storyboard\n"
            "Sélectionnez un plan et cliquez '▶▶ Lancer'. Le prompt du plan est "
            "utilisé, traduit en anglais, et les références (personnages, décor) "
            "sont envoyées automatiquement. Quand des références visuelles sont disponibles, "
            "elles guident Seedance pour une cohérence visuelle accrue.\n\n"
            "Modifier des clips\n"
            "Importez des clips existants et modifiez-les avec un prompt. "
            "Seedance applique la modification en préservant la structure visuelle. "
            "LatentSync resynchronise les lèvres sur une nouvelle piste audio.\n\n"
            "Génération directe\n"
            "Accès aux 13 moteurs (Seedance, Happy Horse, Kling, Veo 3.1, "
            "PixVerse, Sora 2…) avec leurs paramètres et tarifs spécifiques.\n\n"
            "Vidéothèque\n"
            "Galerie de tous les clips générés pour ce projet. Cliquez sur un clip "
            "pour le prévisualiser, l'envoyer dans 'Modifier des clips', ou l'ouvrir.\n\n"
            "Tarifs\n"
            "La génération est facturée via fal.ai. Seedance 2.0 est le moteur "
            "recommandé pour la cohérence visuelle. Consultez le Manuel pour le "
            "comparatif des tarifs par moteur."
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
    "live_studio": {
        "title": "Studio IA — Live",
        "context": "Génération de loops vidéo optimisés pour Resolume.",
        "tips": [
            "Onglet « Génération directe » : choisissez un moteur et lancez un loop.",
            "Un sélecteur de 20 styles VJ sera intégré à la génération.",
            "Mode loop Resolume : la première image rejoint la dernière (boucle parfaite).",
            "Sans clé fal.ai, la génération est simulée (mode démo).",
        ],
        "guide": "",
    },
    "live_sequences": {
        "title": "Séquences",
        "context": "Enchaînements de loops pour le live (équivalent storyboard).",
        "tips": [
            "Composez des séquences de loops par segment.",
            "À venir : style par segment, durées, transitions, export Resolume.",
        ],
        "guide": "",
    },
    "mapping": {
        "title": "Mapping vidéo",
        "context": "Mapping vidéo (à venir).",
        "tips": [
            "Préparation assistée du mapping de projection.",
        ],
        "guide": "",
    },
    "resolume": {
        "title": "Resolume",
        "context": "Contrôle de composition Resolume — expérimental.",
        "tips": [
            "Onglet conservé pour évaluation — non prioritaire.",
        ],
        "guide": "",
    },
    "live_settings": {
        "title": "Paramètres",
        "context": "Paramètres du module Live.",
        "tips": [],
        "guide": "",
    },
}

_DEFAULT_CORPUS = {
    "title": "PANDORA",
    "context": "Logiciel de pré-production cinéma pour DaVinci Resolve.",
    "tips": [
        "Naviguez entre les sections depuis la barre latérale gauche.",
        "Les données sont sauvegardées automatiquement.",
        "Utilisez Ctrl+S pour une sauvegarde manuelle.",
    ],
    "guide": (
        "Bienvenue dans PANDORA\n"
        "PANDORA est un outil de pré-production cinéma intégré à DaVinci Resolve. "
        "Il couvre l'ensemble du pipeline de pré-production : scénario, storyboard, "
        "castings, décors, accessoires, HMC, véhicules et génération vidéo IA.\n\n"
        "Démarrage rapide\n"
        "1. Créez ou ouvrez un projet depuis la page Projets.\n"
        "2. Rédigez votre scénario et utilisez Claude IA pour le formater.\n"
        "3. Générez le storyboard depuis le scénario.\n"
        "4. Ajoutez personnages, décors et accessoires avec images de référence.\n"
        "5. Générez vos clips vidéo depuis Studio IA."
    ),
}


# ── Panneau assistant ──────────────────────────────────────────────────────────

class AssistantPanel(QWidget):
    """Panneau assistant contextuel avec corpus par page et chat Haiku."""

    def __init__(self):
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
        header.setFixedHeight(76)
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

        self._title_lbl = QLabel("Assistant")
        self._title_lbl.setStyleSheet(
            f"color:{CP['text_primary']};font-size:13px;font-weight:700;"
            f"background:transparent;"
        )
        hl.addWidget(self._title_lbl)
        hl.addStretch()

        self._btn_ai_toggle = QPushButton("IA ○")
        self._btn_ai_toggle.setFixedHeight(22)
        self._btn_ai_toggle.setMinimumWidth(46)
        self._btn_ai_toggle.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_ai_toggle.setToolTip(
            "Activer l'assistant IA — utilise des crédits Anthropic\n"
            "(désactivé par défaut)"
        )
        self._btn_ai_toggle.setStyleSheet(
            f"QPushButton{{background:transparent;color:{CP['text_dim']};"
            f"border:1px solid {CP['border']};border-radius:5px;"
            f"font-size:9px;font-weight:700;padding:0 6px;}}"
            f"QPushButton:hover{{border-color:{CP['border_bright']};"
            f"color:{CP['text_secondary']};}}"
        )
        self._btn_ai_toggle.clicked.connect(self._toggle_ai)
        hl.addWidget(self._btn_ai_toggle)

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

    def _toggle_ai(self):
        self._ai_enabled = not self._ai_enabled
        self._apply_ai_state()

    def _apply_ai_state(self):
        on = self._ai_enabled
        self._btn_ai_toggle.setText("IA ●" if on else "IA ○")
        self._btn_ai_toggle.setStyleSheet(
            f"QPushButton{{background:{'rgba(78,205,196,0.15)' if on else 'transparent'};"
            f"color:{CP['accent'] if on else CP['text_dim']};"
            f"border:1px solid {CP['accent'] if on else CP['border']};border-radius:5px;"
            f"font-size:9px;font-weight:700;padding:0 6px;}}"
            f"QPushButton:hover{{border-color:{CP['accent_dim']};color:{CP['accent']};}}"
        )
        self._disabled_notice.setVisible(not on)
        self._input.setVisible(on)
        self._btn_ask.setVisible(on)
        self._chat_scroll.setVisible(on)
        self._tips_outer.setMaximumHeight(260 if on else 16777215)

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
        self.setFixedWidth(28)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setToolTip("Ouvrir / fermer l'assistant pédagogique")
        self.setStyleSheet(f"background:{CP['bg1']};")

        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)
        lay.addStretch()

        self._ia_lbl = QLabel("IA")
        self._ia_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._ia_lbl.setFixedWidth(28)
        self._ia_lbl.setStyleSheet(
            f"color:{CP['accent']};font-size:9px;font-weight:900;"
            f"letter-spacing:1px;background:transparent;"
        )
        lay.addWidget(self._ia_lbl)

        lay.addSpacing(6)

        self._arrow = QLabel(self._arrow_char())
        self._arrow.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._arrow.setFixedWidth(28)
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
            f"color:#ffffff;font-size:9px;font-weight:900;"
            f"letter-spacing:1px;background:transparent;"
        )
        self._arrow.setStyleSheet(
            f"color:#ffffff;font-size:18px;font-weight:700;background:transparent;"
        )

    def leaveEvent(self, e):
        self._ia_lbl.setStyleSheet(
            f"color:{CP['accent']};font-size:9px;font-weight:900;"
            f"letter-spacing:1px;background:transparent;"
        )
        self._arrow.setStyleSheet(
            f"color:{CP['accent']};font-size:18px;font-weight:700;background:transparent;"
        )
