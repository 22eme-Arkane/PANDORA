"""Internationalisation — traductions de l'interface utilisateur de PANDORA."""
import json
import os

from core.paths import APP_ROOT as _ROOT
_CFG  = os.path.join(_ROOT, "data", "config.json")

_LANG: str = "fr"

LANGUAGES: dict[str, str] = {
    "fr": "🇫🇷  FR — Français",
    "en": "🇬🇧  EN — English",
}

# ── Table de traduction (clés nommées) ────────────────────────────────────────

_T: dict[str, dict[str, str]] = {
    # ── Navigation latérale
    "nav.projects":    {"fr": "Projets",         "en": "Projects"},
    "nav.scenario":    {"fr": "Scénario",         "en": "Screenplay"},
    "nav.storyboard":  {"fr": "Storyboard",       "en": "Storyboard"},
    "nav.castings":    {"fr": "Castings",          "en": "Cast"},
    "nav.decors":      {"fr": "Décors",            "en": "Locations"},
    "nav.accessories": {"fr": "Accessoires",       "en": "Props"},
    "nav.hmc":         {"fr": "HMC",               "en": "HMC"},
    "nav.vehicles":    {"fr": "Véhicules",         "en": "Vehicles"},
    "nav.camera":      {"fr": "Image & Son",       "en": "Camera & Sound"},
    "nav.doublage":    {"fr": "Doublage",          "en": "Dubbing"},
    "nav.seedance":    {"fr": "Studio IA",          "en": "AI Studio"},
    "nav.settings":    {"fr": "Paramètres",        "en": "Settings"},

    # ── Topbar globale
    "btn.save":        {"fr": "Sauvegarder",       "en": "Save"},
    "btn.saved":       {"fr": "✓ Sauvegardé",      "en": "✓ Saved"},
    "btn.manual":      {"fr": "Manuel",             "en": "Manual"},
    "btn.contact":     {"fr": "Nous contacter",    "en": "Contact us"},
    "btn.support":     {"fr": "✦  Soutenir",       "en": "✦  Support"},

    # ── Dialogue de fermeture
    "quit.title":      {"fr": "Quitter PANDORA",   "en": "Quit PANDORA"},
    "quit.question":   {"fr": "Voulez-vous vraiment quitter le programme ?",
                        "en": "Are you sure you want to quit?"},
    "quit.sub":        {"fr": "Les données du storyboard et des fiches sont sauvegardées automatiquement.",
                        "en": "Storyboard and card data are saved automatically."},
    "quit.cancel":     {"fr": "Annuler",            "en": "Cancel"},
    "quit.nosave":     {"fr": "Quitter sans sauvegarder", "en": "Quit without saving"},
    "quit.savequit":   {"fr": "Sauvegarder et quitter",  "en": "Save and quit"},

    # ── Changement de langue
    "lang.title":      {"fr": "Langue changée",    "en": "Language changed"},
    "lang.restart":    {"fr": "Redémarrez PANDORA pour appliquer la nouvelle langue.",
                        "en": "Restart PANDORA to apply the new language."},
}


# ── Table de traduction directe FR → EN ───────────────────────────────────────
# Utilisée par retranslate_widget() pour tradure les strings hardcodées.

_FR_TO_EN: dict[str, str] = {

    # ── Communs ────────────────────────────────────────────────────────────────
    "Annuler":              "Cancel",
    "Sauvegarder":          "Save",
    "💾  Sauvegarder":      "💾  Save",
    "Fermer":               "Close",
    "Supprimer":            "Delete",
    "Ajouter":              "Add",
    "Modifier":             "Edit",
    "Éditer":               "Edit",
    "Importer":             "Import",
    "Exporter":             "Export",
    "Générer":              "Generate",
    "Générer tout":         "Generate all",
    "OK":                   "OK",
    "Oui":                  "Yes",
    "Non":                  "No",
    "Confirmer":            "Confirm",
    "Retour":               "Back",
    "Suivant":              "Next",
    "Précédent":            "Previous",
    "Terminer":             "Done",
    "Valider":              "Validate",
    "Appliquer":            "Apply",
    "Réinitialiser":        "Reset",
    "Chargement…":          "Loading…",
    "Chargement...":        "Loading...",
    "Génération en cours…": "Generating…",
    "Génération en cours...": "Generating...",
    "Terminé":              "Done",
    "Erreur":               "Error",
    "Succès":               "Success",
    "Attention":            "Warning",
    "Information":          "Information",
    "Aucun résultat":       "No results",
    "Rechercher…":          "Search…",
    "Rechercher...":        "Search...",
    "Nom":                  "Name",
    "Description":          "Description",
    "Notes":                "Notes",
    "Image":                "Image",
    "Date":                 "Date",
    "Statut":               "Status",
    "Type":                 "Type",
    "Durée":                "Duration",
    "Résolution":           "Resolution",
    "Modèle":               "Model",
    "Prompt":               "Prompt",
    "Nouveau":              "New",
    "Ouvrir":               "Open",
    "Parcourir…":           "Browse…",
    "Parcourir...":         "Browse...",
    "Copier":               "Copy",
    "Coller":               "Paste",
    "Couper":               "Cut",
    "Sélectionner":         "Select",
    "Tout sélectionner":    "Select all",
    "Désélectionner":       "Deselect",
    "Actualiser":           "Refresh",
    "Recharger":            "Reload",

    # ── Navigation ─────────────────────────────────────────────────────────────
    "Projets":              "Projects",
    "Scénario":             "Screenplay",
    "Storyboard":           "Storyboard",
    "Castings":             "Cast",
    "Décors":               "Locations",
    "Accessoires":          "Props",
    "HMC":                  "HMC",
    "Véhicules":            "Vehicles",
    "Image & Son":          "Camera & Sound",
    "Doublage":             "Dubbing",
    "Seedance 2.0":         "Seedance 2.0",
    "Paramètres":           "Settings",

    # ── Page Projets ───────────────────────────────────────────────────────────
    "Nouveau projet":             "New project",
    "✦  Nouveau projet":          "✦  New project",
    "Ouvrir un projet":           "Open a project",
    "Ouvrir un dossier…":         "Open a folder…",
    "Créer un projet":            "Create a project",
    "Nom du projet":              "Project name",
    "Emplacement":                "Location",
    "Projets récents":            "Recent projects",
    "PROJETS RÉCENTS":            "RECENT PROJECTS",
    "PROJET ACTUEL":              "CURRENT PROJECT",
    "Aucun projet récent":        "No recent projects",
    "Aucun autre projet récent.": "No other recent project.",
    "Créer":                      "Create",

    # ── Splash ────────────────────────────────────────────────────────────────
    "Suite de pré-production IA":                         "AI pre-production suite",
    "  NOUVEAU PROJET":                                   "  NEW PROJECT",
    "  OUVRIR UN PROJET":                                 "  OPEN PROJECT",
    "Aucun projet récent.\nCrée ton premier projet →":    "No recent projects.\nCreate your first project →",

    # ── Dates relatives ───────────────────────────────────────────────────────
    "Aujourd'hui":          "Today",
    "Hier":                 "Yesterday",

    # ── Page Scénario ──────────────────────────────────────────────────────────
    "Nouveau scénario":          "New screenplay",
    "Importer un fichier":       "Import a file",
    "Scénarios récents":         "Recent screenplays",
    "Écrire depuis zéro":        "Write from scratch",
    "Aucun scénario récent.":    "No recent screenplay.",
    "↩  Annuler":           "↩  Undo",
    "↪  Refaire":           "↪  Redo",
    "✚ Nouvelle version":   "✚ New version",
    "⤓ Charger":            "⤓ Load",
    "✕ Supprimer":          "✕ Delete",
    "Mettre en page":       "Format",
    "Analyser et arranger": "Analyze & arrange",
    "☁ Claude IA":          "☁ Claude AI",
    "☁ Générer depuis le scénario": "☁ Generate from screenplay",
    "Génération automatique depuis le scénario": "Auto-generate from screenplay",
    "Personnages":          "Characters",
    "Lieux / Décors":       "Locations / Sets",
    "Intensité d'arrangement": "Arrangement intensity",
    "Version":              "Version",
    "Versions":             "Versions",
    "Éditeur":              "Editor",
    "Résultat":             "Result",
    "Analyse":              "Analysis",
    "Scénario":             "Screenplay",

    # ── Page Storyboard ────────────────────────────────────────────────────────
    "✚ Nouveau plan":           "✚ New shot",
    "✚  Ajouter un plan":       "✚  Add shot",
    "Ajouter un plan":          "Add shot",
    "Aperçu IA":                "AI Preview",
    "Générer les prompts":      "Generate prompts",
    "Générer les sketches":     "Generate sketches",
    "Exporter CSV":             "Export CSV",
    "Créer un storyboard":      "Create a storyboard",
    "Plan":                     "Shot",
    "PLAN":                     "SHOT",
    "Séquence":                 "Sequence",
    "Action":                   "Action",
    "ACTION":                   "ACTION",
    "MISE EN SCÈNE":            "STAGING",
    "MISE EN SCENE":            "STAGING",
    "Mouvement":                "Movement",
    "MOUVEMENT":                "MOVEMENT",
    "Valeur":                   "Size",
    "VALEUR":                   "SIZE",
    "Focal":                    "Focal",
    "FOCALE":                   "FOCAL",
    "Vitesse":                  "Speed",
    "VITESSE":                  "SPEED",
    "Décor":                    "Location",
    "DÉCORS":                   "LOCATIONS",
    "DECORS":                   "LOCATIONS",
    "Heure":                    "Time",
    "ACCESSOIRES":              "PROPS",
    "Acteurs":                  "Characters",
    "ACTEURS":                  "CAST",
    "Axe":                      "Axis",
    "AXE":                      "AXIS",
    "PROMPT":                   "PROMPT",
    "Aperçu":                   "Preview",
    "Éditer":                   "Edit",
    "Suppr":                    "Del",
    "Valider":                  "Confirm",

    # ── Page Castings ──────────────────────────────────────────────────────────
    "✚ Nouveau personnage":     "✚ New character",
    "Créer un personnage":      "Create a character",
    "Générer les personnages":  "Generate characters",
    "Modifier le personnage":   "Edit character",
    "Nouveau personnage":       "New character",
    "Image actuelle":           "Current image",
    "Modifier image":           "Change image",
    "Générer un portrait":      "Generate portrait",
    "Sauvegarder le personnage": "Save character",
    "Rendre non modifiable":    "Make non-editable",
    "Exporter cette image":     "Export this image",
    "Portrait généré":          "Generated portrait",
    "Utiliser cette image":     "Use this image",
    "Supprimer cette image":    "Delete this image",
    "Prompt pour tous réseaux": "Prompt for all networks",
    "🔍  Rechercher un personnage…": "🔍  Search characters…",
    "Rechercher un personnage…": "Search characters…",
    "Castings — Personnages du film": "Cast — Film characters",
    "▸ Créez une fiche par personnage : nom, rôle, description physique et psychologique.":
        "▸ Create a card per character: name, role, physical and psychological description.",
    "▸ Générez un portrait IA via Nano Banana en un clic (clé API requise dans Paramètres).":
        "▸ Generate an AI portrait via Nano Banana in one click (API key required in Settings).",
    "▸ Plusieurs portraits peuvent être générés pour un même personnage — choisissez le meilleur.":
        "▸ Multiple portraits can be generated for the same character — choose the best.",
    "▸ Les personnages sont réutilisés dans le storyboard et injectés comme références visuelles dans Seedance.":
        "▸ Characters are reused in the storyboard and injected as visual references in Seedance.",
    "▸ Filtrez et recherchez par nom ou rôle depuis la barre d'outils.":
        "▸ Filter and search by name or role from the toolbar.",

    # ── Dialogue personnage ─────────────────────────────────────────────────────
    "Éditer le personnage":     "Edit character",
    "Nouveau personnage":       "New character",
    "Prénom":                   "First name",
    "Nom de famille":           "Last name",
    "Surnom":                   "Nickname",
    "Rôle dans l'histoire":     "Role in the story",
    "Genre":                    "Gender",
    "Homme":                    "Male",
    "Femme":                    "Female",
    "Non-binaire":              "Non-binary",
    "Âge":                      "Age",
    "Traits de caractère":      "Character traits",
    "Biographie":               "Biography",
    "Apparence physique":       "Physical appearance",
    "Générer le portrait":      "Generate portrait",
    "✂ Supprimer le fond":      "✂ Remove background",
    "🖼 Générer depuis photo":   "🖼 Generate from photo",
    "Importer une photo":       "Import photo",
    "Importer":                 "Import",
    "Portrait":                 "Portrait",
    "Character sheet":          "Character sheet",

    # ── Dialogue décor ──────────────────────────────────────────────────────────
    "Créer un décor":           "Create a location",
    "Éditer le décor":          "Edit location",
    "Modifier le décor":        "Edit location",
    "Nouveau décor":            "New location",
    "Lieu":                     "Place",
    "Période":                  "Period",
    "Atmosphère":               "Atmosphere",
    "Générer le décor":         "Generate location",
    "Générer décor":            "Generate location",
    "🔍  Rechercher un décor…":  "🔍  Search locations…",
    "Rechercher un décor…":     "Search locations…",

    # ── Dialogue accessoire ─────────────────────────────────────────────────────
    "Créer un accessoire":      "Create a prop",
    "Éditer l'accessoire":      "Edit prop",
    "Modifier l'accessoire":    "Edit prop",
    "Nouvel accessoire":        "New prop",
    "Catégorie":                "Category",
    "Matière":                  "Material",
    "Couleur":                  "Color",
    "Générer l'accessoire":     "Generate prop",
    "🔍  Rechercher un accessoire…": "🔍  Search props…",
    "Rechercher un accessoire…": "Search props…",

    # ── Dialogue HMC ────────────────────────────────────────────────────────────
    "Créer un élément HMC":     "Create HMC item",
    "Éditer HMC":               "Edit HMC",
    "Modifier HMC":             "Edit HMC",
    "Nouveau HMC":              "New HMC",
    "Nouvel élément HMC":       "New HMC item",
    "Aucun élément HMC":        "No HMC items",
    "Cliquez sur Créer un élément pour commencer.": "Click Create an item to get started.",
    "Habillage":                "Costume",
    "Maquillage":               "Makeup",
    "Coiffure":                 "Hair",
    "Personnage associé":       "Associated character",
    "🔍  Rechercher…":           "🔍  Search…",
    "Rechercher…":              "Search…",

    # ── Dialogue véhicule ────────────────────────────────────────────────────────
    "Créer un véhicule":        "Create a vehicle",
    "Éditer le véhicule":       "Edit vehicle",
    "Modifier le véhicule":     "Edit vehicle",
    "Nouveau véhicule":         "New vehicle",
    "Aucun véhicule":           "No vehicles",
    "Cliquez sur Créer un véhicule pour commencer.": "Click Create a vehicle to get started.",
    "Marque":                   "Brand",
    "Année":                    "Year",
    "Immatriculation":          "License plate",
    "Générer le véhicule":      "Generate vehicle",
    "🔍  Rechercher un véhicule…": "🔍  Search vehicles…",
    "Rechercher un véhicule…":  "Search vehicles…",

    # ── Dialogue plan storyboard ─────────────────────────────────────────────────
    "Éditer le plan":           "Edit shot",
    "CAMÉRA":                   "CAMERA",
    "ÉLÉMENTS":                 "ELEMENTS",
    "MISE EN SCÈNE":            "STAGING",
    "DURÉE":                    "DURATION",
    "COMMENTAIRES":             "NOTES",
    "PROMPT SEEDANCE":          "SEEDANCE PROMPT",
    "Mouvement caméra":         "Camera movement",
    "Valeur de plan":           "Shot size",
    "Focale":                   "Focal length",
    "Optique":                  "Lens",
    "Vitesse tournage":         "Shooting speed",
    "Heure du plan":            "Shot time",
    "Axe caméra":               "Camera axis",
    "Placement caméra":         "Camera placement",
    "Placement acteurs":        "Actor placement",
    "Entrée dans le plan":      "Entering the shot",
    "Sortie du plan":           "Exiting the shot",
    "Placement micro":          "Mic placement",
    "Face":                     "Front",
    "Latéral 90°":              "Side 90°",
    "Dos":                      "Back",
    "Plongée":                  "High angle",
    "Contre-plongée":           "Low angle",
    "Générer la vidéo":         "Generate video",
    "Envoyer à Seedance":       "Send to Seedance",

    # ── Page Paramètres ─────────────────────────────────────────────────────────
    "Connexion DaVinci Resolve":    "DaVinci Resolve Connection",
    "Clés API":                     "API Keys",
    "Clé API fal.ai":               "fal.ai API Key",
    "Clé Anthropic":                "Anthropic API Key",
    "Clé Nano Banana":              "Nano Banana API Key",
    "Dossier de sortie":            "Output folder",
    "Langue":                       "Language",
    "Sauvegarder les paramètres":   "Save settings",
    "Modèle de génération d'images": "Image Generation Model",
    "Utilisé pour les portraits (Castings), décors, accessoires, HMC et véhicules.":
        "Used for portraits (Cast), locations, props, HMC and vehicles.",
    "Tester API fal.ai":            "Test fal.ai API",
    "Tester API Anthropic":         "Test Anthropic API",
    "fal.ai — Seedance 2.0 (vidéo)  ·  Nano Banana (portraits, accessoires, HMC)":
        "fal.ai — Seedance 2.0 (video)  ·  Nano Banana (portraits, props, HMC)",
    "Anthropic — Claude  (optimisation prompts, scénario, storyboard)":
        "Anthropic — Claude  (prompt optimization, screenplay, storyboard)",
    "⇗  Obtenir une clé fal.ai":    "⇗  Get a fal.ai key",
    "⇗  Obtenir une clé Anthropic": "⇗  Get an Anthropic key",
    "Guide de connexion DaVinci Resolve": "DaVinci Resolve connection guide",
    "Comment obtenir les clés API": "How to get API keys",
    "Recommandé — Gemini 3.1 Flash · rapide · $0.08/image":
        "Recommended — Gemini 3.1 Flash · fast · $0.08/image",
    "Haute qualité — Gemini 3 Pro · $0.15/image · plus lent":
        "High quality — Gemini 3 Pro · $0.15/image · slower",
    "Ultra-rapide — idéal pour sketches storyboard · ~$0.003/image":
        "Ultra-fast — ideal for storyboard sketches · ~$0.003/image",
    "Texte dans l'image parfait — logos, inscriptions · ~$0.21/image":
        "Perfect in-image text — logos, signs · ~$0.21/image",
    "Sauvegardé":                   "Saved",
    "Configuration sauvegardée ✓":  "Configuration saved ✓",
    "Clé manquante":                "Missing key",
    "Entre ta clé API Anthropic d'abord !": "Enter your Anthropic API key first!",
    "✓ Connexion OK":               "✓ Connection OK",
    "Clé Anthropic valide !":       "Anthropic API key is valid!",
    "Clé invalide":                 "Invalid key",
    "La clé API Anthropic est incorrecte.": "The Anthropic API key is incorrect.",
    "anthropic manquant":           "anthropic missing",
    "Installe le client :\n\npip install anthropic": "Install the client:\n\npip install anthropic",

    # ── Page Paramètres supplémentaires ───────────────────────────────────────
    "Vérification Backend DANGER":   "Backend Check DANGER",
    "Manuel d'utilisation":          "User manual",
    "Financer le plugin":            "Fund the plugin",
    "Test backend API":              "Test backend API",
    "Test DaVinci Resolve API":      "Test DaVinci Resolve API",
    "Save":                          "Save",

    # ── Page Doublage ──────────────────────────────────────────────────────────
    "Doublage & Post-Production Audio":  "Dubbing & Audio Post-Production",
    "En développement...":              "Under development...",
    "Synthèse vocale IA, assignation aux personnages, Sound FX et Ambiences... en cours de développement.":
        "AI voice synthesis, character assignment, Sound FX and Ambiences... under development.",
    "Synthèse Vocale IA — Kokoro TTS":  "AI Voice Synthesis — Kokoro TTS",
    "Génère des voix naturelles en anglais, espagnol, portugais, italien, japonais et mandarin."
    "  ·  $0.02 / 1 000 caractères":
        "Generates natural voices in English, Spanish, Portuguese, Italian, Japanese and Mandarin."
        "  ·  $0.02 / 1,000 characters",
    "Texte à synthétiser :":        "Text to synthesize:",
    "Voix :":                       "Voice:",
    "Vitesse : 1.0×":               "Speed: 1.0×",
    "🎙  Générer la voix":           "🎙  Generate voice",
    "Fichiers Audio Générés":        "Generated Audio Files",
    "Aucun fichier généré pour l'instant.": "No files generated yet.",
    "▶  Lire":                       "▶  Play",
    "Ouvrir le dossier":             "Open folder",
    "Suppression de Fond — BiRefNet": "Background Removal — BiRefNet",
    "Supprime automatiquement le fond d'une photo de personnage ou de décor."
    "  Résultat PNG avec canal alpha transparent.":
        "Automatically removes the background from a character or location photo."
        "  Result: PNG with transparent alpha channel.",
    "── Recommandées ──":            "── Recommended ──",
    "── Toutes les voix ──":         "── All voices ──",
    "Entrez ici le texte à synthétiser…\n\n"
    "Conseil : pour un résultat optimal, écrivez en anglais. "
    "Le texte sera lu tel quel par la voix sélectionnée.":
        "Enter the text to synthesize here…\n\n"
        "Tip: for best results, write in English. "
        "The text will be read as-is by the selected voice.",
    "Sélectionner une image…":       "Select an image…",
    "Aucune image sélectionnée":     "No image selected",
    "✂ Supprimer le fond":           "✂ Remove background",
    "Lipsync — Conseil":             "Lipsync — Tip",
    "Lipsync via Seedance T2V":      "Lipsync via Seedance T2V",
    "→ Aller à Seedance 2.0":        "→ Go to Seedance 2.0",

    # ── Studio IA (AI Studio) ────────────────────────────────────────────────────
    "Outils génériques":             "Generic tools",
    "Audio prompt":                  "Audio prompt",
    "Musique générée":               "Generated music",
    "Sons libres":                   "Free sounds",
    "Export vers Media Pool":        "Export to Media Pool",
    "Générer les ressources":        "Generate assets",
    "Génération directe":            "Direct generation",
    "Générer un fichier avec Seedance 2.0": "Generate a file with Seedance 2.0",

    # ── Seedance / Onglets vidéo ────────────────────────────────────────────────
    "Text-to-Video":                 "Text-to-Video",
    "Image-to-Video":                "Image-to-Video",
    "Extension":                     "Extension",
    "Référence":                     "Reference",
    "Kling & PixVerse":              "Kling & PixVerse",
    "Historique":                    "History",
    "Prompt négatif":                "Negative prompt",
    "Image de départ":               "Start image",
    "Image de fin":                  "End image",
    "Image source":                  "Source image",
    "Vidéo source":                  "Source video",
    "Audio":                         "Audio",
    "Générer l'audio":               "Generate audio",
    "Moteur vidéo":                  "Video engine",
    "Sélectionner une image":        "Select an image",
    "Choisir une image…":            "Choose an image…",
    "Parcourir":                     "Browse",

    # ── Tab Kling & PixVerse ─────────────────────────────────────────────────────
    "Kling v3 Pro I2V":              "Kling v3 Pro I2V",
    "Kling v3 Pro T2V":              "Kling v3 Pro T2V",
    "PixVerse v4.5 I2V":             "PixVerse v4.5 I2V",
    "Prompt (en anglais)":           "Prompt (in English)",
    "Prompt négatif (en anglais)":   "Negative prompt (in English)",
    "Durée (secondes)":              "Duration (seconds)",
    "Générer avec l'audio":          "Generate with audio",
    "🎬  Générer":                   "🎬  Generate",
    "Résultat":                      "Result",
    "Ouvrir dans l'explorateur":     "Open in explorer",

    # ── Page Image & Son ─────────────────────────────────────────────────────────
    "Image & Son":                        "Camera & Sound",
    "Caméra":                             "Camera",
    "Sons":                               "Sound",
    "Optique":                            "Lens",
    "Son":                                "Sound",
    "Format":                             "Format",
    "Ratio":                              "Ratio",
    "FPS":                                "FPS",
    "ISO":                                "ISO",
    "Profondeur de champ":               "Depth of field",
    "Balance des blancs":                "White balance",
    "Choisis la caméra...":              "Choose a camera...",
    "Choisis le modèle...":              "Choose a model...",
    "Filtres/lumières globaux pour ce tournage": "Global filters/lighting for this shoot",

    # ── Page Style ────────────────────────────────────────────────────────────────
    "Style visuel":                  "Visual style",
    "Ambiance":                      "Mood",
    "Références":                    "References",
    "Palette de couleurs":           "Color palette",

    # ── Splash / Projets ─────────────────────────────────────────────────────────
    "Bienvenue dans PANDORA":        "Welcome to PANDORA",
    "Sélectionnez ou créez un projet": "Select or create a project",
    "Créer un nouveau projet":       "Create a new project",
    "Parcourir…":                    "Browse…",
    "Derniers projets":              "Recent projects",
    "Aucun projet récent.":          "No recent project.",
    "Ouvrir ce projet":              "Open this project",
    "Supprimer de la liste":         "Remove from list",

    # ── Topbar PandoraWindow ──────────────────────────────────────────────────────
    "Manuel d'utilisation":          "User manual",
    "Nous contacter":                "Contact us",
    "✦  Soutenir":                   "✦  Support",

    # ── Messages d'état / progression ─────────────────────────────────────────────
    "Connexion en cours…":           "Connecting…",
    "Connexion réussie":             "Connection successful",
    "Connexion échouée":             "Connection failed",
    "Génération terminée":           "Generation complete",
    "Erreur de génération":          "Generation error",
    "Fichier sauvegardé":            "File saved",
    "Importation réussie":           "Import successful",
    "Suppression réussie":           "Deletion successful",
    "Aucun élément":                 "No items",
    "En cours…":                     "In progress…",
    "Terminé !":                     "Done!",
    "Annulé":                        "Cancelled",
    "Traduction en cours…":          "Translating…",
    "Optimisation du prompt…":       "Optimizing prompt…",
    "Upload en cours…":              "Uploading…",

    # ── Storyboard — colonnes ──────────────────────────────────────────────────────
    "Séq":                           "Seq",
    "Mouvement":                     "Move",
    "Valeur":                        "Size",
    "Focal":                         "Focal",
    "Vitesse":                       "Speed",
    "Heure":                         "Time",
    "Axe":                           "Axis",
    "Durée":                         "Dur.",

    # ── Manuel d'utilisation sections ─────────────────────────────────────────────
    "Bienvenue":                     "Welcome",
    "Démarrage rapide":              "Quick start",
    "Génération vidéo":              "Video generation",
    "Portraits & Images":            "Portraits & Images",
    "Storyboard":                    "Storyboard",
    "Scénario":                      "Screenplay",
    "Doublage & Tarifs IA":          "Dubbing & AI Pricing",
    "DaVinci Resolve":               "DaVinci Resolve",
    "Tarifs":                        "Pricing",

    # ── Divers / HelpBlock ─────────────────────────────────────────────────────────
    "Aucun décor trouvé.":           "No location found.",
    "Aucun accessoire trouvé.":      "No prop found.",
    "Aucun véhicule trouvé.":        "No vehicle found.",
    "Aucun HMC trouvé.":             "No HMC found.",
    "Aucun personnage trouvé.":      "No character found.",
    "Aucun plan.":                   "No shot.",
    "Aucune version.":               "No version.",
    "Choisir un fichier":            "Choose a file",
    "Tous les fichiers":             "All files",
    "Images":                        "Images",
    "Vidéos":                        "Videos",
    "Fichiers audio":                "Audio files",
    "Sauvegarder sous":              "Save as",
    "Fermer la fenêtre":             "Close window",
    "Aide":                          "Help",
    "À propos":                      "About",
    "Version":                       "Version",
    "Licence":                       "License",

    # ── Splash "Pandora" ────────────────────────────────────────────────────────
    "Pré-production cinéma":         "Film pre-production",
    "Propulsé par Seedance 2.0":     "Powered by Seedance 2.0",

    # ── Dialog Galerie ────────────────────────────────────────────────────────────
    "Galerie":                       "Gallery",
    "Précédent":                     "Previous",
    "Suivant":                       "Next",
    "Télécharger":                   "Download",
    "Utiliser cette image":          "Use this image",

    # ── Tooltips fréquents ─────────────────────────────────────────────────────────
    "Undo":                          "Undo",
    "Redo":                          "Redo",
    "Copier le prompt":              "Copy prompt",
    "Voir l'image":                  "View image",
    "Supprimer l'image":             "Delete image",

    # ── Boutons avec icônes ────────────────────────────────────────────────────
    "🎨  Générer l'image":              "🎨  Generate image",
    "✓  Sauvegarder le décor":          "✓  Save location",
    "✓  Sauvegarder l'accessoire":      "✓  Save prop",
    "✓  Sauvegarder":                   "✓  Save",
    "✓  Confirmer":                     "✓  Confirm",
    "✓  Choisir cette image":           "✓  Choose this image",
    "↩  Recommencer":                   "↩  Retry",
    "✓  Utiliser cette image":          "✓  Use this image",
    "⎘  Copier":                        "⎘  Copy",
    "🗺  Sheet 4 vues":                  "🗺  4-view sheet",
    "✓  Sauvegarder le plan":           "✓  Save shot",
    "✓  Sauvegarder le HMC":            "✓  Save HMC",
    "✓  Sauvegarder le véhicule":       "✓  Save vehicle",
    "✓  Sauvegarder le personnage":     "✓  Save character",
    "🖼  Importer une photo":            "🖼  Import photo",
    "📁  Importer une image":            "📁  Import image",
    "🎨  Générer":                       "🎨  Generate",
    "✚ Assigner":                       "✚ Assign",

    # ── Section labels ────────────────────────────────────────────────────────
    "Nom du décor":                     "Location name",
    "Nom de l'accessoire":              "Prop name",
    "Nom de l'élément HMC":             "HMC item name",
    "Prompt pour Nano Banana":          "Nano Banana prompt",
    "Références visuelles":             "Visual references",
    "Claude analyse les images pour enrichir le prompt":
        "Claude analyzes images to enrich the prompt",
    "Style d'image":                    "Image style",
    "IDENTIFICATION":                   "IDENTIFICATION",
    "TECHNIQUE CAMÉRA":                 "CAMERA TECHNIQUE",
    "LIEU & TEMPS":                     "PLACE & TIME",
    "NOTES & PROMPT":                   "NOTES & PROMPT",
    "Nombre d'images à générer (1–4)":  "Number of images to generate (1–4)",
    "Assigner à des personnages":       "Assign to characters",
    "Sélectionne les personnages":      "Select characters",
    "Personnages assignés":             "Assigned characters",
    "Aucun personnage assigné":         "No characters assigned",
    "Référence visuelle (optionnelle)": "Visual reference (optional)",

    # ── Combo items ───────────────────────────────────────────────────────────
    "Image unique":                     "Single image",
    "Sheet 4 vues (avant · arrière · gauche · droite)":
        "4-view sheet (front · back · left · right)",
    "Nano Banana 2  —  rapide  ·  $0.08":   "Nano Banana 2  —  fast  ·  $0.08",
    "Nano Banana Pro  —  qualité  ·  $0.15": "Nano Banana Pro  —  quality  ·  $0.15",
    "— Style du projet —":              "— Project style —",
    "— Aucun —":                        "— None —",
    "— Sélectionner —":                 "— Select —",

    # ── Status messages ───────────────────────────────────────────────────────
    "Mode mock : aucune image générée (clé fal.ai absente)":
        "Mock mode: no image generated (fal.ai key missing)",
    "Image ajoutée ✓":                  "Image added ✓",
    "Image importée ✓":                 "Image imported ✓",
    "Optimisation en cours…":           "Optimizing…",
    "Optimisation en cours...":         "Optimizing...",
    "Prompt optimisé ✓":                "Prompt optimized ✓",
    "Prompt enrichi ✓":                 "Prompt enriched ✓",
    "Suppression du fond en cours…":    "Removing background…",
    "Fond supprimé (mode mock)":        "Background removed (mock mode)",
    "Fond supprimé ✓":                  "Background removed ✓",
    "Génération en cours…":             "Generating…",
    "Analyse en cours…":                "Analyzing…",
    "Sauvegarde en cours…":             "Saving…",

    # ── Error / validation messages ───────────────────────────────────────────
    "Nom manquant":                     "Name missing",
    "Entre le nom du décor.":           "Enter the location name.",
    "Entre le nom de l'accessoire.":    "Enter the prop name.",
    "Entre le nom de l'élément HMC.":   "Enter the HMC item name.",
    "Entre le nom du véhicule.":        "Enter the vehicle name.",
    "Entre le nom du personnage.":      "Enter the character name.",
    "Génère ou importe une image d'abord.": "Generate or import an image first.",
    "Aucune image sélectionnée.":       "No image selected.",
    "Clé API manquante":                "Missing API key",
    "Configure ta clé fal.ai dans Paramètres.": "Configure your fal.ai key in Settings.",

    # ── Dialog titles ─────────────────────────────────────────────────────────
    "Aperçu du décor":                  "Location preview",
    "Aperçu du personnage":             "Character preview",
    "Aperçu du HMC":                    "HMC preview",
    "Aperçu du véhicule":               "Vehicle preview",
    "Aperçu de l'accessoire":           "Prop preview",
    "Images de référence":              "Reference images",
    "Nouveau plan":                     "New shot",
    "Générer une variation":            "Generate a variation",
    "Générer à nouveau":                "Generate again",
    "Générer avec HMC":                 "Generate with HMC",
    "Configurer les clés API":          "Configure API keys",
    "Choisir un portrait":              "Choose a portrait",
    "Choisir une image":                "Choose an image",
    "Comment obtenir les clés API":     "How to get API keys",
    "Guide de connexion DaVinci":       "DaVinci connection guide",
    "Manuel d'utilisation PANDORA":     "PANDORA user manual",
    "Soutenir le projet":               "Support the project",

    # ── Long strings ─────────────────────────────────────────────────────────
    "Mode mock — aucune image réelle générée\n(configure ta clé fal.ai dans Paramètres)":
        "Mock mode — no real image generated\n(configure your fal.ai key in Settings)",
    "Aucune image\ngénérée":            "No image\ngenerated",
    "Aucune image générée pour ce personnage.\nLance une génération depuis le dialogue d'édition.":
        "No image generated for this character.\nStart a generation from the edit dialog.",
    "Aucun personnage créé.\nCrée des personnages dans l'onglet Castings d'abord.":
        "No characters created.\nCreate characters in the Cast tab first.",
    "Les modifications sont bidirectionnelles : la fiche personnage sera mise à jour automatiquement.":
        "Changes are bidirectional: the character card will be updated automatically.",

    # ── Contact dialog ────────────────────────────────────────────────────────
    "Signaler un bug — objet : Bug":    "Report a bug — subject: Bug",
    "Décrivez le problème et les étapes pour le reproduire.":
        "Describe the issue and the steps to reproduce it.",
    "Demande de fonctionnalité — objet : Feature":
        "Feature request — subject: Feature",
    "Nous contacter":                   "Contact us",

    # ── Api help dialog ───────────────────────────────────────────────────────
    "fal.ai — Seedance 2.0 & Nano Banana": "fal.ai — Seedance 2.0 & Nano Banana",
    "Vidéo  ·  Images IA":             "Video  ·  AI Images",
    "⇗  Ouvrir fal.ai/dashboard/keys": "⇗  Open fal.ai/dashboard/keys",
    "⇗  Ouvrir console.anthropic.com": "⇗  Open console.anthropic.com",

    # ── DaVinci help dialog ───────────────────────────────────────────────────
    "Connexion DaVinci Resolve":        "DaVinci Resolve Connection",
    "DaVinci Resolve — Studio requis":  "DaVinci Resolve — Studio required",
    "Intégration DaVinci Resolve":      "DaVinci Resolve Integration",

    # ── Dialogs aperçu / preview ──────────────────────────────────────────────
    "Image précédente":                 "Previous image",
    "Image suivante":                   "Next image",
    "Supprimer de la liste":            "Remove from list",
    "Définir comme portrait actif":     "Set as active portrait",
    "Portrait actif":                   "Active portrait",

    # ── Arrangement session ───────────────────────────────────────────────────
    "Session d'arrangement":            "Arrangement session",
    "Appliquer les modifications":      "Apply changes",
    "Ignorer":                          "Ignore",
    "Déplacer":                         "Move",
    "Couper en deux":                   "Split in two",
    "Fusionner avec le suivant":        "Merge with next",

    # ── User manual ───────────────────────────────────────────────────────────
    "Table des matières":               "Table of contents",
    "Introduction":                     "Introduction",
    "Premiers pas":                     "Getting started",

    # ── Funding dialog ────────────────────────────────────────────────────────
    "Financer le plugin":               "Fund the plugin",
    "Soutenir PANDORA":                 "Support PANDORA",
    "Payer par carte":                  "Pay by card",
    "Payer en crypto":                  "Pay in crypto",
    "Retour":                           "Back",
    "← Retour":                         "← Back",
    "Merci pour votre soutien. ◈ 22eme ARKANE": "Thank you for your support. ◈ 22eme ARKANE",
    "✓  Copié !":                       "✓  Copied!",

    # ── Contact dialog (manquants) ─────────────────────────────────────────────
    "Partagez vos retours, idées de fonctionnalités ou impressions.":
        "Share your feedback, feature ideas or impressions.",

    # ── Page Paramètres — en-têtes majuscules ──────────────────────────────────
    "CLÉS API":                         "API KEYS",
    "CONNEXION DAVINCI RESOLVE":        "DAVINCI RESOLVE CONNECTION",

    # ── Page Image & Son ──────────────────────────────────────────────────────
    "CORPS DE CAMÉRA":                  "CAMERA BODY",
    "OPTIQUES":                         "LENSES",
    "FILTRES":                          "FILTERS",
    "MICROPHONE":                       "MICROPHONE",
    "— Choisir la marque —":            "— Choose brand —",
    "— Choisir le modèle —":            "— Choose model —",
    "— Choisir la série —":             "— Choose series —",
    "— Choisir la catégorie —":         "— Choose category —",
    "Série":                            "Series",
    "Suffixe Seedance généré :":        "Generated Seedance suffix:",
    "Sauvegardé ✓":                     "Saved ✓",
    "Sélectionnez un ou plusieurs filtres utilisés sur ce tournage.":
        "Select one or more filters used for this shoot.",
    "Choisissez le microphone principal utilisé pour ce tournage.":
        "Choose the main microphone for this shoot.",
    "▶  FILTRES":                       "▶  FILTERS",
    "▼  FILTRES":                       "▼  FILTERS",
    "Image & Son — Préférences caméra et optique":
        "Camera & Sound — Camera and lens preferences",

    # ── Dialogue plan storyboard (manquants) ──────────────────────────────────
    "Séq.":                             "Seq.",
    "Nom de séquence":                  "Sequence name",
    "Description de l'action":         "Action description",
    "Acteurs / Personnages":            "Actors / Characters",
    "Durée du plan":                    "Shot duration",
    "Prompt Seedance 2.0":              "Seedance 2.0 Prompt",
    "IN — dans le cadre":               "IN — in the shot",
    "OUT — hors-champ":                 "OUT — off screen",
    "Micro — on entend":                "Mic — we hear",
    "Dist. sujet":                      "Subj. dist.",
    "Amélioration en cours…":           "Enhancing…",
    "Description améliorée ✓":         "Description improved ✓",
    "Écris une description avant d'améliorer.": "Write a description first.",
    "Écris un prompt avant d'améliorer.":       "Write a prompt first.",
    "— Aucun décor —":                  "— No location —",
    "Aucun accessoire":                 "No props",
    "Aucun personnage":                 "No characters",

    # ── Dialogue personnage (manquants) ──────────────────────────────────────
    "Nom du personnage":                "Character name",
    "Rôle":                            "Role",
    "Style de génération :":           "Generation style:",
    "Utilisées par Claude pour enrichir le prompt":
        "Used by Claude to enrich the prompt",
    "⚠ Mode mock actif\n(clé fal.ai non configurée)":
        "⚠ Mock mode active\n(fal.ai key not configured)",
    "Sélectionner les éléments HMC":   "Select HMC items",
    "ASSIGNÉS À CE PERSONNAGE":         "ASSIGNED TO THIS CHARACTER",
    "AUTRES ÉLÉMENTS HMC":              "OTHER HMC ITEMS",
    "✓  Générer avec la sélection":    "✓  Generate with selection",
    "🎨  Générer le portrait":          "🎨  Generate portrait",
    "🎨  Générer une variation":        "🎨  Generate a variation",
    "🎲  Générer une variation":        "🎲  Generate a variation",
    "🖼  Générer depuis photo":         "🖼  Generate from photo",
    "📁  Importer une image":           "📁  Import image",
    "✓  Active":                        "✓  Active",
    "ACTIF":                            "ACTIVE",
    "✕ Ne pas utiliser":               "✕ Don't use",
    "✓ Utiliser":                       "✓ Use",
    "🗑  Supprimer cette image":        "🗑  Delete this image",
    "Aucun accessoire assigné.":        "No prop assigned.",
    "Aucun élément HMC assigné.":       "No HMC item assigned.",
    "Aucun HMC assigné — ajoutes-en dans l'onglet HMC pour personnaliser le look.":
        "No HMC assigned — add some in the HMC tab to customize the look.",
    "Aucune image générée.\nClique sur « Générer le portrait ».":
        "No image generated.\nClick 'Generate portrait'.",
    "Aucune image":                     "No image",
    "Castings → Personnages du film":   "Cast → Film characters",

    # ── Dialogue décor / accessoire / HMC / véhicule (manquants) ──────────────
    "Utilisé dans les séquences :":     "Used in sequences:",
    "Utilisé dans les plans :":         "Used in shots:",
    "Aucun plan dans le storyboard":    "No shot in storyboard",
    "Aucune séquence dans le storyboard": "No sequence in storyboard",
    "✂  Supprimer le fond":             "✂  Remove background",
    "Génération du sheet 4 vues…":      "Generating 4-view sheet…",
    "🖼  Image unique":                 "🖼  Single image",
    "🗺  Sheet 4 vues  (avant · arrière · gauche · droite)":
        "🗺  4-view sheet  (front · back · left · right)",
    "Mode":                             "Mode",
    "Nouvel accessoire":                "New prop",
    "Modifier l'élément HMC":          "Edit HMC item",
    "Choisir des personnages…":         "Choose characters…",
    "Aperçu accessoire":                "Prop preview",
    "Aperçu HMC":                       "HMC preview",
    "Aperçu véhicule":                  "Vehicle preview",
    "Image générée":                    "Generated image",
    "Image non utilisée — clique Générer pour réessayer.":
        "Image not used — click Generate to retry.",

    # ── Panel Contrôles créatifs ───────────────────────────────────────────────
    "▶  Contrôles créatifs":            "▶  Creative controls",
    "▼  Contrôles créatifs":            "▼  Creative controls",
    "▶  Liberté créative":              "▶  Creative freedom",
    "▼  Liberté créative":              "▼  Creative freedom",
    "Contrôles créatifs":               "Creative controls",
    "Liberté créative":                 "Creative freedom",

    # ── Studio IA — onglet T2V / I2V / Edit ──────────────────────────────────
    "Style de film":                    "Film style",
    "STORYBOARD":                       "STORYBOARD",
    "Caméra · Optiques · Micro":        "Camera · Lenses · Mic",
    "Caméra dynamique":                 "Dynamic camera",
    "Audio natif":                      "Native audio",
    "Sous-titres":                      "Subtitles",
    "Import auto · Media Pool":         "Auto import · Media Pool",
    "MODÈLE":                           "MODEL",
    "RATIO":                            "RATIO",
    "RÉSOLUTION":                       "RESOLUTION",
    "Générer le clip":                  "Generate clip",
    "🎬  Générer le clip":              "🎬  Generate clip",
    "Modifier un clip existant":        "Edit an existing clip",
    "CLIP SOURCE":                      "SOURCE CLIP",
    "CLIP SÉLECTIONNÉ":                 "SELECTED CLIP",
    "Durée à ajouter":                  "Duration to add",
    "PROMPT (OPTIONNEL)":               "PROMPT (OPTIONAL)",
    "Import auto dans Media Pool":      "Auto import to Media Pool",
    "Générer un nouveau rush":          "Generate a new take",
    "GÉNÉRATIONS RÉCENTES":             "RECENT GENERATIONS",
    "Casting":                          "Cast",
    "Mood":                             "Mood",

    # ── Pandora sidebar buttons ────────────────────────────────────────────────
    "☰  Manuel d'utilisation":          "☰  User manual",
    "✉  Nous contacter":                "✉  Contact us",

    # ── Storyboard page ────────────────────────────────────────────────────────
    "＋  Ajouter un plan":              "＋  Add shot",
    "Suppr.":                           "Del.",
    "✦  Générer les Moods":             "✦  Generate Moods",
    "⏹  Arrêter":                       "⏹  Stop",
    "Ouvrir →":                         "Open →",
    "＋ Créer un storyboard":           "＋ Create storyboard",
    "Tout":                             "All",
    "Aucun":                            "None",
    "Sans Mood":                        "No Mood",
    "✦  Générer":                       "✦  Generate",
    "Cliquer\npour Mood":               "Click\nfor Mood",

    # ── Scenario page ──────────────────────────────────────────────────────────
    "⤢  Rouvrir la fenêtre":            "⤢  Reopen window",
    "↩  Remplacer le texte":            "↩  Replace text",
    "↺  Annuler":                       "↺  Cancel",
    "→  Voir dans le Storyboard":       "→  View in Storyboard",
    "Identifier  →":                    "Identify  →",
    "🎨  Nano Banana  →":               "🎨  Nano Banana  →",
    "▶  Légende niveaux 1-10":          "▶  Levels 1-10 guide",
    "▼  Légende niveaux 1-10":          "▼  Levels 1-10 guide",
    "✓  Appliquer ce scénario au projet": "✓  Apply this screenplay",

    # ── Tab T2V / I2V ─────────────────────────────────────────────────────────
    "▶  Générer le clip":               "▶  Generate clip",
    "▶  Animer l'image":                "▶  Animate image",
    "Non, annuler":                     "No, cancel",
    "Oui, ajouter":                     "Yes, add",
    "Connecter":                        "Connect",
    "⚙  Contrôles créatifs    ▶":       "⚙  Creative controls    ▶",
    "— Non défini —":                   "— Undefined —",

    # ── Tab Extension / Reference ─────────────────────────────────────────────
    "◈  Utiliser le clip DaVinci":      "◈  Use DaVinci clip",
    "Effacer":                          "Clear",
    "◎  Générer un nouveau rush":       "◎  Generate a new take",
    "▶  Générer depuis références":     "▶  Generate from references",
    "✦ Améliorer":                      "✦ Enhance",

    # ── Tab video engines ─────────────────────────────────────────────────────
    "Choisir…":                         "Choose…",
    "▶  Générer":                       "▶  Generate",

    # ── Settings tab ──────────────────────────────────────────────────────────
    "Tester API":                       "Test API",

    # ── Tab T2V — HelpBlock ───────────────────────────────────────────────────
    "Seedance 2.0 — Générer un clip vidéo IA":
        "Seedance 2.0 — Generate an AI video clip",
    "▸ Storyboard : sélectionnez un plan pour pré-remplir le prompt, la durée et la caméra automatiquement.":
        "▸ Storyboard: select a shot to auto-fill the prompt, duration and camera settings.",
    "▸ Batch : cochez plusieurs plans pour les générer en file d'attente.":
        "▸ Batch: check multiple shots to queue them for sequential generation.",
    "▸ Casting : ajoutez des personnages pour injecter leurs portraits comme images de référence visuelles.":
        "▸ Cast: add characters to inject their portraits as visual reference images.",
    "▸ Style de film : choisissez un preset ou importez une image de référence pour définir l'esthétique du clip.":
        "▸ Film style: pick a preset or import a reference image to define the clip's visual aesthetic.",
    "▸ Continuité : la dernière frame du plan précédent s'injecte automatiquement comme image de départ.":
        "▸ Continuity: the last frame of the previous shot is automatically injected as the starting image.",
    "▸ Seed : verrouillez un seed pour garantir la cohérence visuelle entre plusieurs clips.":
        "▸ Seed: lock a seed value to ensure visual consistency across multiple clips.",
    "▸ Contrôles créatifs : réglez l'interprétation, le rythme, la fidélité et la tolérance de contenu.":
        "▸ Creative controls: adjust interpretation, rhythm, fidelity and content tolerance.",
    "▸ Mode mock : sans clé fal.ai configurée, la génération est simulée localement (aucun crédit consommé).":
        "▸ Mock mode: without a fal.ai key, generation is simulated locally (no credits used).",
}


# ── API publique ───────────────────────────────────────────────────────────────

def tr(key: str) -> str:
    """Retourne la chaîne traduite dans la langue courante (fallback FR)."""
    entry = _T.get(key, {})
    return entry.get(_LANG, entry.get("fr", key))


def translate(text: str) -> str:
    """Traduit une chaîne FR directe dans la langue courante.
    Retourne le texte inchangé si pas de traduction ou si langue = FR."""
    if _LANG == "fr" or not text:
        return text
    return _FR_TO_EN.get(text, text)


def get_lang() -> str:
    return _LANG


def set_lang(lang: str) -> None:
    global _LANG
    if lang not in LANGUAGES:
        return
    _LANG = lang
    try:
        cfg: dict = {}
        if os.path.isfile(_CFG):
            with open(_CFG, "r", encoding="utf-8") as f:
                cfg = json.load(f)
        cfg["ui_language"] = lang
        os.makedirs(os.path.dirname(_CFG), exist_ok=True)
        with open(_CFG, "w", encoding="utf-8") as f:
            json.dump(cfg, f, indent=2, ensure_ascii=False)
    except Exception:
        pass


def load_saved_lang() -> None:
    """Appelé au démarrage pour restaurer la langue préférée de l'utilisateur."""
    global _LANG
    try:
        if os.path.isfile(_CFG):
            with open(_CFG, "r", encoding="utf-8") as f:
                cfg = json.load(f)
            lang = cfg.get("ui_language", "fr")
            if lang in LANGUAGES:
                _LANG = lang
    except Exception:
        pass


def retranslate_widget(widget) -> None:
    """Walk the widget tree and translate known French strings.

    Handles: QLabel, QPushButton, QCheckBox, QGroupBox, QTabWidget,
    QComboBox items, QAbstractItemView headers.
    No-op when language is French (source language).
    """
    if _LANG == "fr":
        return
    _retranslate_recursive(widget)


def _retranslate_recursive(widget) -> None:
    """Parcourt récursivement l'arbre de widgets et traduit les textes connus."""
    try:
        from PyQt6.QtWidgets import (
            QLabel, QPushButton, QCheckBox, QRadioButton,
            QGroupBox, QTabWidget, QComboBox, QLineEdit, QTextEdit,
            QTreeWidget, QTableWidget,
        )

        # Window title (QDialog, QMainWindow, QWidget avec titre)
        if hasattr(widget, "windowTitle") and hasattr(widget, "setWindowTitle"):
            t = widget.windowTitle()
            if t:
                nt = translate(t)
                if nt != t:
                    widget.setWindowTitle(nt)

        # QLabel
        if isinstance(widget, QLabel):
            t = widget.text()
            nt = translate(t)
            if nt != t:
                widget.setText(nt)

        # QPushButton / QCheckBox / QRadioButton
        elif isinstance(widget, (QPushButton, QCheckBox, QRadioButton)):
            t = widget.text()
            nt = translate(t)
            if nt != t:
                widget.setText(nt)

        # QGroupBox
        elif isinstance(widget, QGroupBox):
            t = widget.title()
            nt = translate(t)
            if nt != t:
                widget.setTitle(nt)

        # QTabWidget — traduit les noms d'onglets
        elif isinstance(widget, QTabWidget):
            for i in range(widget.count()):
                t = widget.tabText(i)
                nt = translate(t)
                if nt != t:
                    widget.setTabText(i, nt)

        # QComboBox — traduit les items
        elif isinstance(widget, QComboBox):
            for i in range(widget.count()):
                t = widget.itemText(i)
                nt = translate(t)
                if nt != t:
                    widget.setItemText(i, nt)
            pt = widget.placeholderText() if hasattr(widget, "placeholderText") else ""
            if pt:
                npt = translate(pt)
                if npt != pt:
                    widget.setPlaceholderText(npt)

        # QLineEdit — traduit le placeholder
        if isinstance(widget, QLineEdit):
            pt = widget.placeholderText()
            if pt:
                npt = translate(pt)
                if npt != pt:
                    widget.setPlaceholderText(npt)

        # QTextEdit — traduit le placeholder
        if isinstance(widget, QTextEdit):
            pt = widget.placeholderText()
            if pt:
                npt = translate(pt)
                if npt != pt:
                    widget.setPlaceholderText(npt)

        # QTreeWidget / QTableWidget — traduit les headers
        if isinstance(widget, (QTreeWidget, QTableWidget)):
            if hasattr(widget, "horizontalHeaderItem"):
                for i in range(widget.columnCount()):
                    item = widget.horizontalHeaderItem(i)
                    if item:
                        t = item.text()
                        nt = translate(t)
                        if nt != t:
                            item.setText(nt)

        # Tooltip
        tip = widget.toolTip() if hasattr(widget, "toolTip") else ""
        if tip:
            nt = translate(tip)
            if nt != tip:
                widget.setToolTip(nt)

        # Récursion sur les enfants
        for child in widget.children():
            if hasattr(child, "children"):
                _retranslate_recursive(child)

    except Exception:
        pass
