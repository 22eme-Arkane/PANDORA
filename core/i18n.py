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
    "nav.mise_en_scene": {"fr": "Mise en scène",  "en": "Staging"},
    "nav.castings":    {"fr": "Castings",          "en": "Cast"},
    "nav.decors":      {"fr": "Décors",            "en": "Locations"},
    "nav.accessories": {"fr": "Accessoires",       "en": "Props"},
    "nav.hmc":         {"fr": "HMC",               "en": "HMC"},
    "nav.vehicles":    {"fr": "Véhicules",         "en": "Vehicles"},
    "nav.camera":      {"fr": "Image & Son",       "en": "Camera & Sound"},
    "nav.plan_de_feu": {"fr": "Plan de feu",       "en": "Lighting plan"},
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

    # ── PANDORA | Live ───────────────────────────────────────────────────────
    # Sélecteur de module (chooser)
    "Choisissez votre espace de travail":  "Choose your workspace",
    "Cinéma":                              "Cinema",
    "Live":                                "Live",
    "Prochainement":                       "Coming soon",
    "Pré-production IA\nScénario · Storyboard · DaVinci":
        "AI pre-production\nScreenplay · Storyboard · DaVinci",
    "Performance live\nVJ · Mapping":      "Live performance\nVJ · Mapping",
    # Splash (mode Live)
    "‹  Retour":                           "‹  Back",
    "Performance live · Mapping · VJ":     "Live performance · Mapping · VJ",
    "PROJETS RÉCENTS — LIVE":              "RECENT PROJECTS — LIVE",
    "PROJETS RÉCENTS — CINÉMA":            "RECENT PROJECTS — CINEMA",
    # Sidebar Live
    "Styles VJ":                           "VJ Styles",
    "Mapping":                             "Mapping",
    "Resolume":                            "Resolume",
    # Page Bibliothèque de styles VJ
    "Bibliothèque de styles VJ":           "VJ Style Library",
    "Presets visuels prêts à générer pour vos performances live.":
        "Visual presets ready to generate for your live performances.",
    "styles":                              "styles",
    "Sélectionnez un style et cliquez Générer.":
        "Select a style and click Generate.",
    "Boucle":                              "Loop",
    "Génération (démo) :":                 "Generation (demo):",
    "câblage des moteurs vidéo à venir.":  "video engine wiring coming soon.",
    # Page Mapping (placeholder)
    "Mapping vidéo":                       "Video Mapping",
    "Bientôt disponible":                  "Coming soon",
    "Le mapping assistera la préparation de vos projections : import d'une "
    "photo du lieu, détection automatique des zones, puis export vers votre "
    "logiciel de mapping. Cette partie sera développée prochainement.":
        "Mapping will assist the preparation of your projections: import a photo "
        "of the venue, automatically detect zones, then export to your mapping "
        "software. This part will be developed soon.",
    # Assistant — corpus Live
    "Styles VJ — Bibliothèque":            "VJ Styles — Library",
    "Galerie de presets visuels pour le live et le VJing.":
        "Gallery of visual presets for live and VJing.",
    "Chaque carte est un style prêt à générer.":
        "Each card is a style ready to generate.",
    "La génération réutilisera les moteurs vidéo de PANDORA (Seedance, Kling…).":
        "Generation will reuse PANDORA's video engines (Seedance, Kling…).",
    "Les styles en boucle sont pensés pour tourner en continu.":
        "Looping styles are designed to run continuously.",
    "Mapping vidéo (à venir).":            "Video mapping (coming soon).",
    "Préparation assistée du mapping de projection.":
        "Assisted preparation of projection mapping.",
    "Contrôle de composition Resolume — expérimental.":
        "Resolume composition control — experimental.",
    # Vidéothèque Live
    "Vidéothèque":                         "Video library",
    "Historique":                          "History",
    "Lire":                                "Play",
    "Vidéothèque Live — loops & vidéos générés":
        "Live Library — generated loops & videos",
    "▸ Retrouvez ici tous les loops et vidéos générés pour ce live.":
        "▸ Find here all the loops and videos generated for this live set.",
    "▸ ▶ Lire ouvre la vidéo dans votre lecteur par défaut.":
        "▸ ▶ Play opens the video in your default player.",
    "▸ ⤷ Modifier envoie le clip vers l'onglet « Modifier ».":
        "▸ ⤷ Edit sends the clip to the “Edit” tab.",
    "▸ → Resolume bascule vers l'onglet Resolume pour le charger dans un slot.":
        "▸ → Resolume switches to the Resolume tab to load it into a slot.",
    "Envoyer vers l'onglet Modifier (Live)":  "Send to the Edit tab (Live)",
    "Charger ce clip dans Resolume":          "Load this clip into Resolume",
    "Tri :":                               "Sort:",
    "vidéo(s)":                            "video(s)",
    "Aucune vidéo générée pour ce live.\nLancez une génération depuis « Génération directe ».":
        "No video generated for this live set.\nStart a generation from “Direct generation”.",
    # Onglet Modifier (Live)
    "Modifier un clip (Live)":             "Edit a clip (Live)",
    "▸ Envoyez un clip depuis la Vidéothèque (⤷ Modifier).":
        "▸ Send a clip from the Library (⤷ Edit).",
    "▸ Choisissez un style, écrivez la modification souhaitée, puis générez.":
        "▸ Pick a style, write the desired change, then generate.",
    "▸ Le clip source est utilisé comme référence — Seedance en produit une nouvelle version.":
        "▸ The source clip is used as reference — Seedance produces a new version.",
    "Clip à modifier":                     "Clip to edit",
    "Aucun clip — envoyez-en un depuis la Vidéothèque.":
        "No clip — send one from the Library.",
    "Prompt de modification":              "Edit prompt",
    "Décrivez la modification… (FR accepté, traduit automatiquement)":
        "Describe the change… (FR accepted, auto-translated)",
    "Moteur de génération":                "Generation engine",
    "Durée : 5 s":                         "Duration: 5 s",
    "Durée :":                             "Duration:",
    "Générer la modification":             "Generate the edit",
    "Génération en cours…":                "Generating…",
    "Aucun clip":                          "No clip",
    "Envoyez d'abord un clip depuis la Vidéothèque.":
        "First send a clip from the Library.",
    "Terminé (mode démo — aucune clé fal.ai)":
        "Done (demo mode — no fal.ai key)",
    "✓  Terminé (mode démo — aucune clé fal.ai)":
        "✓  Done (demo mode — no fal.ai key)",
    "Téléchargement échoué :":             "Download failed:",
    "Ouvrir le dossier":                   "Open folder",
    "Actualiser":                          "Refresh",
    "Onglet conservé pour évaluation — non prioritaire.":
        "Tab kept for evaluation — not a priority.",
    "Paramètres du module Live.":          "Live module settings.",
    # Studio IA / Séquences Live
    "Template de style":                   "Style template",
    "Aucun style":                         "No style",
    "Images de référence":                 "Reference images",
    "Ajouter une image de référence":      "Add a reference image",
    "Mapping source":                      "Mapping source",
    "Ajouter l'image à mapper":            "Add the image to map",
    "Contexte injecté":                    "Injected context",
    "prompt vide":                         "empty prompt",
    "image(s) jointe(s) en référence":     "reference image(s) attached",
    "dont mapping verrouillé":             "incl. locked mapping",
    "traduction automatique en anglais avant envoi":
        "automatic translation to English before sending",
    "Image du lieu/objet à mapper — gardée identique (caméra fixe). "
    "Seuls lumière, ambiance et fond peuvent changer via le prompt.":
        "Image of the place/object to map — kept identical (locked camera). "
        "Only lighting, atmosphere and background may change via the prompt.",
    "Générer depuis Séquences":            "Generate from Sequences",
    # Nav Live (nouvelles sections)
    "Conducteur":                          "Rundown",
    "Séquences Live":                      "Live Sequences",
    "Séquences Mapping":                   "Mapping Sequences",
    "Outils de mapping":                   "Mapping tools",
    "Contrôleur Resolume":                 "Resolume controller",
    # Pages Casting / Accessoires / Véhicules Live
    "Ajouter un personnage":               "Add a character",
    "Ajouter un accessoire":               "Add a prop",
    "Ajouter un véhicule":                 "Add a vehicle",
    "Nom du personnage":                   "Character name",
    "Nom de l'accessoire":                 "Prop name",
    "Nom du véhicule":                     "Vehicle name",
    "Rôle / type":                         "Role / type",
    "Catégorie":                           "Category",
    "Apparence, costume, style visuel…":   "Appearance, costume, visual style…",
    "Matière, couleur, état…":             "Material, color, condition…",
    "Marque, modèle, couleur, état…":      "Make, model, color, condition…",
    "Aucun élément. Cliquez « + » pour en créer un.":
        "No item yet. Click “+” to create one.",
    "Nouvel élément":                      "New item",
    "Nom":                                 "Name",
    "Générer une image":                   "Generate an image",
    "Ajouter une image":                   "Add an image",
    "Nom requis":                          "Name required",
    "Donnez un nom à l'élément.":          "Give the item a name.",
    "Donnez un nom avant d'ajouter des images.":
        "Give a name before adding images.",
    "Choisir une ou plusieurs images":     "Choose one or more images",
    "Description requise":                 "Description required",
    "Décrivez l'élément pour générer une image.":
        "Describe the item to generate an image.",
    # Conducteur
    "Mode :":                              "Mode:",
    "Conducteur enregistré.":              "Rundown saved.",
    "Générer le découpage avec Claude":    "Generate the breakdown with Claude",
    "Trame vide":                          "Empty outline",
    "Écrivez la trame de votre performance d'abord.":
        "Write the outline of your performance first.",
    "Génération du découpage avec Claude…": "Generating the breakdown with Claude…",
    "Génération du découpage via Claude…":  "Generating the breakdown via Claude…",
    "segments générés →":                  "segments generated →",
    "Mise en page du conducteur via Claude…": "Formatting the rundown via Claude…",
    "Mise en page PANDORA":                "PANDORA layout",
    "Mise en page PANDORA générée ✓":      "PANDORA layout generated ✓",
    "Clique « Mise en page PANDORA » (panneau de droite) pour générer ici la "
    "version optimisée pour les moteurs : plans découpés + prompts prêts pour Seedance. "
    "Ton conducteur, lui, reste intact dans l'onglet Conducteur.":
        "Click “PANDORA layout” (right panel) to generate here the engine-optimized "
        "version: broken-down shots + Seedance-ready prompts. Your rundown stays intact "
        "in the Rundown tab.",
    "Arrangement du conducteur via Claude…":  "Arranging the rundown via Claude…",
    "Conducteur mis à jour par Claude ✓":  "Rundown updated by Claude ✓",
    "♫  Musiques du set":                  "♫  Set music",
    "Analyser le set (BPM + drops)":       "Analyze set (BPM + drops)",
    "Cale le découpage sur la musique (tempo + temps forts)":
        "Sync the breakdown to the music (tempo + peaks)",
    "Ajouter des morceaux (mp3/wav…)\nClaude calera le découpage sur leur BPM et leurs drops.":
        "Add tracks (mp3/wav…)\nClaude will sync the breakdown to their BPM and drops.",
    "non analysé":                         "not analyzed",
    "Ajouter des morceaux":                "Add tracks",
    "Morceau(x) ajouté(s) — clique « Analyser le set » pour détecter BPM et drops.":
        "Track(s) added — click “Analyze set” to detect BPM and drops.",
    "Ajoute d'abord des morceaux dans « Musiques du set ».":
        "First add tracks in “Set music”.",
    "Analyse audio en cours (BPM + drops)…":  "Analyzing audio (BPM + drops)…",
    "Analyse":                             "Analyzing",
    "morceau(x) analysé(s) — timeline musicale prête ✓":
        "track(s) analyzed — music timeline ready ✓",
    "Corriger le BPM (tap-tempo, ÷2 / ×2)":  "Fix BPM (tap-tempo, ÷2 / ×2)",
    "Corriger le BPM":                     "Fix BPM",
    "Tape en rythme sur la musique…":      "Tap along with the music…",
    "Continue à taper…":                   "Keep tapping…",
    "⊙  Tap tempo":                        "⊙  Tap tempo",
    "Valider":                             "Apply",
    "Analyse musicale du set":             "Set music analysis",
    "L'analyse apparaît au fil de l'écoute…":  "The analysis appears as it listens…",
    "✓  Appliquer l'analyse":              "✓  Apply analysis",
    "Analyse musicale annulée.":           "Music analysis cancelled.",
    "analyse…":                            "analyzing…",
    "énergie":                             "energy",
    "✓  Appliquer dans l'onglet":          "✓  Apply to the tab",
    "Mode :":                              "Mode:",
    "Acte":                                "Act",
    "Musique":                             "Music",
    "Notes / Repère":                      "Notes / Cue",
    "Transition":                          "Transition",
    "Fondu":                               "Fade",
    "Prompt vidéo / son":                  "Video / sound prompt",
    "Vidéo":                               "Video",
    "Son":                                 "Sound",
    "Prompt vidéo (Seedance)":             "Video prompt (Seedance)",
    "Prompt sound design":                 "Sound design prompt",
    "Ambiance / SFX du plan (anglais), sans voix — injecté dans Sound Design.":
        "Shot ambience / SFX (English), no voice — fed into Sound Design.",
    "▦  Référence bâtiment (façade)":      "▦  Building reference (facade)",
    "Image de la façade projetée. En Séquence Mapping, les moods sont générés "
    "SUR cette façade (sa géométrie est conservée).":
        "Image of the projected facade. In the Mapping sequence, moods are generated "
        "ON this facade (its geometry is preserved).",
    "Choisir la façade":                   "Choose the facade",
    "Choisir la façade du bâtiment":       "Choose the building facade",
    "Façade enregistrée ✓":                "Facade saved ✓",
    "Isoler sur fond noir":                "Isolate on black",
    "Isoler (fond noir)":                  "Isolate (black bg)",
    "Détoure le bâtiment (BiRefNet) et le place sur fond noir pur — "
    "supprime les bâtiments et objets voisins.":
        "Cuts out the building (BiRefNet) onto pure black — removes neighboring "
        "buildings and objects.",
    "Détourage de la façade (BiRefNet)…":  "Cutting out the facade (BiRefNet)…",
    "Détourage indisponible (mode démo — renseigne la clé fal.ai).":
        "Cutout unavailable (demo mode — set your fal.ai key).",
    "Façade isolée sur fond noir ✓":       "Facade isolated on black ✓",
    "Choisis la façade du bâtiment":       "Choose the building facade",
    "Rendu de nuit automatique":           "Automatic night render",
    "Soigne les prompts vidéo et son":     "Refine the video and sound prompts",
    "Soigne le prompt vidéo":              "Refine the video prompt",
    "Pense au prompt sound design":        "Mind the sound design prompt",
    "Dans le Conducteur, renseigne la « Référence bâtiment » et isole-la "
    "sur fond noir. Les Moods sont générés SUR cette façade, dont la "
    "géométrie est conservée.":
        "In the Rundown, set the « Building reference » and isolate it on black. "
        "Moods are generated ON that facade, whose geometry is preserved.",
    "Le mapping se projette de nuit : les Moods sont automatiquement "
    "convertis en nuit (façade éclairée uniquement par la projection, "
    "environnement en fond noir).":
        "Mapping is projected at night: Moods are automatically converted to night "
        "(facade lit only by the projection, surroundings on black).",
    "Décris l'évolution sur la façade (lumière, effets, matières) dans le "
    "« Prompt vidéo ». Ajoute un « Prompt sound design » pour l'ambiance "
    "sonore du plan (injecté dans Sound Design).":
        "Describe the evolution on the facade (light, effects, materials) in the "
        "« Video prompt ». Add a « Sound design prompt » for the shot's ambience "
        "(fed into Sound Design).",
    "Le Mood teste l'ambiance du loop. Plus le « Prompt vidéo » du plan est "
    "détaillé, plus l'image générée reflète le visuel VJ que tu veux obtenir.":
        "The Mood tests the loop's mood. The more detailed the plan's « Video prompt », "
        "the more the generated image reflects the VJ visual you want.",
    "Chaque plan a aussi un « Prompt sound design » (SFX / ambiance, sans "
    "voix) qui sera injecté dans l'onglet Sound Design.":
        "Each shot also has a « Sound design prompt » (SFX / ambience, no voice) "
        "that will be fed into the Sound Design tab.",
    "Une fois les Moods satisfaisants, ils servent de référence visuelle "
    "pour générer les loops (Seedance et autres moteurs). "
    "Ce n'est pas une pré-visualisation fidèle.":
        "Once the Moods are good, they serve as visual reference to generate the "
        "loops (Seedance and other engines). It is not a faithful preview.",
    "Découpage — Aperçu":                  "Breakdown — Preview",
    "Découpage en cours…":                 "Generating breakdown…",
    "Découpage terminé":                   "Breakdown complete",
    "Découpage annulé.":                   "Breakdown cancelled.",
    "Découpage vide.":                     "Empty breakdown.",
    "Les plans découpés apparaissent ici…":  "The breakdown shots appear here…",
    "✓  Appliquer le découpage":           "✓  Apply breakdown",
    "Écrit les plans dans la séquence Live/Mapping.":
        "Writes the shots into the Live/Mapping sequence.",
    "Écrit la mise en page dans l'onglet « Mise en page PANDORA ». "
    "Le Conducteur reste intact.":
        "Writes the layout into the “PANDORA layout” tab. The Rundown stays intact.",
    "Sound Design":                        "Sound Design",
    "Sound Design — Mirelo SFX":           "Sound Design — Mirelo SFX",
    "Sonorise ta performance : un prompt son → SFX, ou un loop vidéo → bande-son "
    "synchronisée. Colle ici les PROMPT SON générés par « Mise en page PANDORA ».":
        "Score your performance: a sound prompt → SFX, or a video loop → synced "
        "soundtrack. Paste here the SOUND PROMPTS generated by “PANDORA layout”.",
    "Prompt → SFX":                        "Prompt → SFX",
    "Loop vidéo → bande-son":              "Video loop → soundtrack",
    "⚡  Générer le son":                   "⚡  Generate sound",
    "Fichiers générés":                    "Generated files",
    "Décris l'ambiance / les effets sonores (en anglais de préférence). "
    "Ex. « deep pulsing bass drone, glitchy risers, crowd energy, no vocals »":
        "Describe the ambience / sound effects (English preferred). "
        "E.g. “deep pulsing bass drone, glitchy risers, crowd energy, no vocals”",
    "📁  Choisir un loop vidéo…":           "📁  Choose a video loop…",
    "Aucun loop sélectionné":              "No loop selected",
    "Prompt son optionnel (anglais) pour orienter la bande-son. "
    "Laisse vide pour une sonorisation automatique du loop.":
        "Optional sound prompt (English) to steer the soundtrack. "
        "Leave empty for automatic scoring of the loop.",
    "Choisir un loop vidéo":               "Choose a video loop",
    "Écris d'abord un prompt son.":        "Write a sound prompt first.",
    "Choisis d'abord un loop vidéo.":      "Choose a video loop first.",
    "Mode mock — renseigne la clé fal.ai dans Paramètres.":
        "Mock mode — set your fal.ai key in Settings.",
    "Généré ✓":                            "Generated ✓",
    "Envoyer vers Sound Design (Studio IA)":  "Send to Sound Design (AI Studio)",
    "Remplacer le découpage ?":            "Replace the breakdown?",
    "Caler sur la musique":                "Sync to music",
    "Quantise les durées en MESURES (BPM du morceau assigné) et attire les cuts "
    "sur les DROPS — calage exact, calculé localement (pas par l'IA).":
        "Quantizes durations to BARS (BPM of the assigned track) and snaps cuts "
        "to DROPS — exact sync, computed locally (not by the AI).",
    "Musique non analysée":                "Music not analyzed",
    "Aucun morceau analysé.\n\nDans le Conducteur, ajoute tes morceaux "
    "dans « Musiques du set » puis clique « Analyser le set » "
    "(BPM + drops) avant de caler le découpage.":
        "No analyzed track.\n\nIn the Rundown, add your tracks in “Set music” then "
        "click “Analyze set” (BPM + drops) before syncing the breakdown.",
    "Déjà calé":                           "Already in sync",
    "Toutes les durées sont déjà calées sur les mesures et les drops ✓":
        "All durations are already snapped to bars and drops ✓",
    "plan(s) ajusté(s) en mesures":        "shot(s) adjusted to bars",
    "cut(s) sur un drop":                  "cut(s) on a drop",
    "Durée totale :":                      "Total duration:",
    "Appliquer ?":                         "Apply?",
    "Sound design auto":                   "Auto sound design",
    "Depuis les Séquences — file d'attente":  "From Sequences — queue",
    "Charger les plans":                   "Load shots",
    "Générer la file":                     "Generate queue",
    "Exporter la bande-son (fondu 1s)":    "Export soundtrack (1s crossfade)",
    "Concatène les SFX générés en UNE bande-son continue avec fondu enchaîné "
    "entre les plans (pas de coupes nettes) — ffmpeg acrossfade.":
        "Concatenates the generated SFX into ONE continuous soundtrack with "
        "crossfades between shots (no hard cuts) — ffmpeg acrossfade.",
    "Aucun plan avec prompt son dans cette séquence — génère le découpage "
    "ou renseigne les champs 🔊 Son.":
        "No shot with a sound prompt in this sequence — generate the breakdown "
        "or fill in the 🔊 Sound fields.",
    "plan(s) chargé(s) — prêt à générer.":  "shot(s) loaded — ready to generate.",
    "ambiance(s) générée(s)":              "ambience(s) generated",
    "Il faut au moins 2 ambiances générées.":  "At least 2 generated ambiences are needed.",
    "Assemblage de la bande-son (durée exacte)…":
        "Assembling the soundtrack (exact duration)…",
    "Bande-son calée exportée ✓ (durée = somme des plans)":
        "Aligned soundtrack exported ✓ (duration = sum of shots)",
    "À la fin de chaque clip, génère aussi l'ambiance SFX du plan (prompt son, "
    "Mirelo ~$0.01/s) — exportée dans data/live_sound_design":
        "At the end of each clip, also generates the shot's SFX ambience (sound "
        "prompt, Mirelo ~$0.01/s) — exported to data/live_sound_design",
    "plan(s) existant(s) seront REMPLACÉS par le nouveau découpage.\n\nContinuer ?":
        "existing shot(s) will be REPLACED by the new breakdown.\n\nContinue?",
    "Upscaling":                           "Upscaling",
    "Upscaling de la séquence (Live)":     "Sequence upscaling (Live)",
    "▸ Ajoutez des clips, ou importez toute la Vidéothèque.":
        "▸ Add clips, or import the whole library.",
    "▸ Choisissez le moteur et le facteur (ex. ×2, ×4).":
        "▸ Pick the engine and factor (e.g. ×2, ×4).",
    "▸ « Upscaler toute la file » ressort tous les plans en haute résolution.":
        "▸ “Upscale entire queue” re-renders all shots in high resolution.",
    "Ajouter des clips":                   "Add clips",
    "Importer la Vidéothèque":             "Import library",
    "Vider":                               "Clear",
    "File d'attente":                      "Queue",
    "File vide — ajoutez des clips ou importez la Vidéothèque.":
        "Empty queue — add clips or import the library.",
    "Moteur d'upscaling":                  "Upscaling engine",
    "Facteur":                             "Factor",
    "Modèle Topaz":                        "Topaz model",
    "Upscaler toute la file":              "Upscale entire queue",
    "Vidéothèque indisponible.":           "Library unavailable.",
    "clip(s) importé(s) depuis la Vidéothèque.":  "clip(s) imported from the library.",
    "upscalé(s)":                          "upscaled",
    "erreur(s)":                           "error(s)",
    "Upscale":                             "Upscale",
    "Envoyer vers l'onglet Upscaling (Live)":  "Send to the Upscaling tab (Live)",
    "Découpe le conducteur en séquence (Live/Mapping)":
        "Breaks the rundown into a sequence (Live/Mapping)",
    "Écris d'abord un texte à mettre en page.": "Write a text to format first.",
    "Écris d'abord un texte à analyser.":  "Write a text to analyze first.",
    "Écris d'abord un conducteur à découper.": "Write a rundown to break down first.",
    # Panneau Conducteur (Claude IA / Générer / Références)
    "☁  Claude IA":                        "☁  Claude AI",
    "☁  Générer depuis le conducteur":     "☁  Generate from the rundown",
    "◎  Références visuelles":             "◎  Visual references",
    "Références visuelles":                "Visual references",
    "Mise en page":                        "Layout",
    "Met en forme la trame (typée Live/Mapping)": "Formats the outline (Live/Mapping-typed)",
    "Proposer un arrangement":             "Propose an arrangement",
    "Réécrit une version améliorée de la trame": "Rewrites an improved version of the outline",
    "Générer le casting":                  "Generate the casting",
    "Identifier les personnages depuis la trame": "Identify characters from the outline",
    "Générer les accessoires":             "Generate the props",
    "Identifier les accessoires depuis la trame": "Identify props from the outline",
    "Générer les véhicules":               "Generate the vehicles",
    "Identifier les véhicules depuis la trame": "Identify vehicles from the outline",
    "Générer le découpage":                "Generate the breakdown",
    "Découpe la trame en séquence (Live/Mapping)": "Breaks the outline into a sequence (Live/Mapping)",
    "Tout générer":                        "Generate all",
    "Casting + accessoires + véhicules + découpage": "Casting + props + vehicles + breakdown",
    "Ajouter des images":                  "Add images",
    "Photos de lieux, ambiances, références": "Photos of places, moods, references",
    "Analyser avec Claude":                "Analyze with Claude",
    "Enrichit la trame à partir des images": "Enriches the outline from the images",
    "Mise en page en cours via Claude…":   "Formatting via Claude…",
    "Arrangement en cours via Claude…":    "Arranging via Claude…",
    "Trame mise à jour par Claude.":       "Outline updated by Claude.",
    "Extraction en cours via Claude…":     "Extracting via Claude…",
    "éléments ajoutés à":                  "items added to",
    "Lancer l'extraction du casting, des accessoires, des véhicules et "
    "le découpage depuis la trame ?":
        "Run extraction of casting, props, vehicles and the breakdown from the outline?",
    "Tout générer — en cours via Claude…": "Generate all — running via Claude…",
    "Tout générer terminé.":               "Generate all finished.",
    "Choisir des images de référence":     "Choose reference images",
    "Ajoutez d'abord des images de référence.": "Add reference images first.",
    "Analyse des références avec Claude…": "Analyzing references with Claude…",
    "Trame enrichie depuis les références.": "Outline enriched from the references.",
    "Écrivez la trame de votre performance… (ambiances, moments, montée, "
    "ruptures, final). Claude la découpera en segments selon le mode choisi.":
        "Write the outline of your performance… (moods, moments, build-up, breaks, "
        "finale). Claude will break it into segments based on the chosen mode.",
    "Mode Mapping : la trame sera découpée en une séquence CONTINUE projetée "
    "sur une façade verrouillée (caméra fixe, raccord automatique).":
        "Mapping mode: the outline will be broken into a CONTINUOUS sequence projected "
        "onto a locked facade (static camera, automatic continuity).",
    "Mode Live : la trame sera découpée en une suite de plans/loops pour "
    "votre performance VJ (valeurs de plan, mouvements).":
        "Live mode: the outline will be broken into a series of shots/loops for your "
        "VJ performance (shot sizes, movements).",
    # Séquences
    "Source de mapping :":                 "Mapping source:",
    "Choisir la façade…":                  "Choose facade…",
    "Choisir la façade à mapper":          "Choose the facade to map",
    "Raccord continu (un seul plan long)": "Continuous take (one long shot)",
    "Ajouter un plan":                     "Add a shot",
    "Aucun plan. Cliquez « + » ou générez le découpage depuis le Conducteur.":
        "No shot yet. Click “+” or generate the breakdown from the Rundown.",
    "(plan sans description)":             "(shot without description)",
    "Aucun plan sélectionné":              "No shot selected",
    "Valeur de plan":                      "Shot size",
    "Mouvement":                           "Movement",
    "Supprimer ce plan":                   "Delete this shot",
    "Plan":                                "Shot",
    "Écrivez la trame de votre performance. À la création, vous choisissez "
    "Live ou Mapping : l'arrangement avec Claude et la mise en page PANDORA "
    "sont alors calibrés pour produire un découpage adapté — séquence live "
    "ou séquence à mapper. À venir.":
        "Write the outline of your performance. When creating it, you choose Live or "
        "Mapping: the Claude arrangement and the PANDORA layout are then calibrated to "
        "produce a suitable breakdown — a live sequence or a sequence to map. Coming soon.",
    "Personnages et performers de la performance, propres au module Live "
    "(générés et stockés séparément du Cinéma). À venir.":
        "Characters and performers of the show, specific to the Live module (generated "
        "and stored separately from Cinema). Coming soon.",
    "Objets et accessoires propres au Live, avec leurs images de référence. "
    "À venir.":
        "Objects and props specific to Live, with their reference images. Coming soon.",
    "Véhicules propres au Live, avec leurs images de référence. À venir.":
        "Vehicles specific to Live, with their reference images. Coming soon.",
    "Séquence destinée à être mappée sur un bâtiment. On choisit la source "
    "de mapping (façade), puis on construit une séquence continue où les plans "
    "s'enchaînent via le raccord automatique — pour ne former qu'un seul plan "
    "long. À venir.":
        "A sequence meant to be mapped onto a building. You pick the mapping source "
        "(facade), then build a continuous sequence where shots chain together via "
        "auto-continuity — forming a single long take. Coming soon.",
    "Cet onglet générera les loops directement à partir de vos séquences "
    "(onglet Séquences) : choix du segment, du style et du moteur, puis envoi "
    "vers Resolume. Disponible une fois les Séquences construites.":
        "This tab will generate loops directly from your sequences (Sequences tab): "
        "pick the segment, style and engine, then send to Resolume. Available once "
        "Sequences are built.",
    "Studio IA":                           "AI Studio",
    "Séquences":                           "Sequences",
    "Studio IA — Live":                    "AI Studio — Live",
    "Génération de loops vidéo optimisés pour Resolume.":
        "Generation of video loops optimized for Resolume.",
    "Onglet « Génération directe » : choisissez un moteur et lancez un loop.":
        "“Direct generation” tab: pick an engine and launch a loop.",
    "Un sélecteur de 20 styles VJ sera intégré à la génération.":
        "A selector of 20 VJ styles will be integrated into generation.",
    "Mode loop Resolume : la première image rejoint la dernière (boucle parfaite).":
        "Resolume loop mode: the first frame meets the last (perfect loop).",
    "Sans clé fal.ai, la génération est simulée (mode démo).":
        "Without a fal.ai key, generation is simulated (demo mode).",
    "Enchaînements de loops pour le live (équivalent storyboard).":
        "Loop sequences for live (storyboard equivalent).",
    "Composez des séquences de loops par segment.":
        "Build loop sequences segment by segment.",
    "À venir : style par segment, durées, transitions, export Resolume.":
        "Coming: per-segment style, durations, transitions, Resolume export.",
    "Composez des enchaînements de loops optimisés pour Resolume — "
    "l'équivalent du storyboard, pensé pour le live. Choix du style par "
    "segment, durées et transitions, puis export vers votre composition. "
    "Cette partie sera développée prochainement.":
        "Build chains of loops optimized for Resolume — the storyboard equivalent, "
        "designed for live. Per-segment style, durations and transitions, then export "
        "to your composition. This part will be developed soon.",

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
    "Moteur de génération":          "Generation engine",
    "⚠  Ce moteur ne supporte pas les images de référence nativement. "
    "Vos personnages, décors et accessoires seront convertis en mots-clés de style "
    "via Claude Vision et ajoutés au prompt texte.":
        "⚠  This engine does not natively support reference images. "
        "Your characters, sets and props will be converted to style keywords "
        "via Claude Vision and added to the text prompt.",
    "Créer un nouveau clip":         "Create a new clip",
    "Sélectionner une image":        "Select an image",
    "Choisir une image…":            "Choose an image…",
    "Parcourir":                     "Browse",

    # ── Tab video engines (DaVinci Edit — LatentSync) ────────────────────────────
    "Resynchroniser les lèvres":     "Resync lips",
    "Synchronisation labiale LatentSync — aligne les lèvres sur l'audio source du clip":
        "LatentSync lip sync — aligns lips with the source audio",

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

    # ── Storyboard sync confirm dialog ───────────────────────────────────────────
    "Synchronisation — Confirmation":   "Sync — Confirmation",
    "Synchronisation — Storyboard":     "Sync — Storyboard",
    "Synchronisation du Storyboard":    "Storyboard Synchronization",
    "Continuer":                        "Continue",
    "Continuer →":                      "Continue →",
    "Appliquer la synchronisation":     "Apply synchronization",
    "Lancer la synchronisation":        "Run synchronization",
    "Réassigner les noms":              "Reassign names",
    "Réécrire les prompts":             "Rewrite prompts",
    "Re-synchroniser les décors":       "Re-sync locations",
    "Réécrire le scénario depuis le storyboard": "Rewrite screenplay from storyboard",
    "Scénario":                         "Screenplay",
    "Scénario reconstruit depuis le storyboard": "Screenplay rebuilt from storyboard",
    "nouvelle version":                 "new version",
    "Réécriture du scénario…":          "Rewriting screenplay…",
    "Enregistrer le scénario":          "Save screenplay",
    "Réessayer":                        "Retry",
    "Identifier et générer les 7 vues de la pièce": "Identify and generate the 7 room views",
    "Chat Storyboard":                  "Storyboard Chat",
    "Discuter du storyboard avec l'IA…": "Chat about the storyboard with the AI…",
    "Envoyer":                          "Send",
    "Le chat IA est désactivé.":        "The AI chat is disabled.",
    "▶  Paramètres avancés — moteur IA par tâche": "▶  Advanced — AI engine per task",
    "▼  Paramètres avancés — moteur IA par tâche": "▼  Advanced — AI engine per task",
    "Par défaut":                       "Default",
    "Amélioration des prompts":         "Prompt enhancement",
    "Chat du Storyboard":               "Storyboard chat",
    "Assistant / guide complet":        "Assistant / full guide",
    "Génération du storyboard":         "Storyboard generation",
    "Scénario (mise en page, arrangement)": "Screenplay (formatting, arrangement)",
    "Extraction d'éléments (personnages, décors…)": "Element extraction (characters, locations…)",
    "Synchronisation du storyboard":    "Storyboard synchronization",
    "✓  Tester API GPT-5.5":            "✓  Test GPT-5.5 API",
    "✓  Tester API Mistral":            "✓  Test Mistral API",
    "⇗  Obtenir une clé OpenAI":        "⇗  Get an OpenAI key",
    "⇗  Obtenir une clé Mistral":       "⇗  Get a Mistral key",
    "OpenAI — GPT-5.5  (assistant texte, par moteur ou par tâche)":
        "OpenAI — GPT-5.5  (text assistant, per engine or per task)",
    "Mistral  (assistant texte, expérimental)":
        "Mistral  (text assistant, experimental)",
    "Obligatoire":                      "Required",
    "Facultatif":                       "Optional",
    "▶  Clés API facultatives  (OpenAI, Mistral, autres à venir)":
        "▶  Optional API keys  (OpenAI, Mistral, more to come)",
    "▼  Clés API facultatives  (OpenAI, Mistral, autres à venir)":
        "▼  Optional API keys  (OpenAI, Mistral, more to come)",
    "Choix personnalisé — un moteur par tâche":
        "Custom — one engine per task",
    "PANDORA optimisé — moteur conseillé par tâche":
        "PANDORA optimized — recommended engine per task",
    "✓  Sauvegarde automatique — chaque modification est enregistrée.":
        "✓  Auto-save — every change is saved.",
    "✓  Enregistré automatiquement.":   "✓  Saved automatically.",
    "Tout est synchronisé":             "Everything is in sync",
    "Chargement du casting…":           "Loading cast…",
    "Sauvegarde…":                      "Saving…",

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
    "Style d'image :":                  "Image style:",

    # ── Lot 15 — fenêtre Tout Générer (confirmation) ──
    '⚡  Génération complète du projet': '⚡  Full project generation',
    "Vous êtes sur le point de lancer la génération complète :\n\n  ☁  Extraction depuis le scénario (Claude IA)\n       personnages · décors · accessoires · HMC · véhicules · storyboard\n\n  ◉  Génération d'images (Nano Banana)\n       1 image par personnage · 1 image par décor · 1 image par accessoire\n       1 image par élément HMC · 1 image par véhicule\n\n  ◈  Génération des Moods storyboard (Flux IA)\n       1 aperçu par plan storyboard": 'You are about to launch the full generation:\n\n  ☁  Extraction from the screenplay (Claude AI)\n       characters · sets · props · HMC · vehicles · storyboard\n\n  ◉  Image generation (Nano Banana)\n       1 image per character · 1 image per set · 1 image per prop\n       1 image per HMC item · 1 image per vehicle\n\n  ◈  Storyboard Mood generation (Flux AI)\n       1 preview per storyboard shot',
    'Éléments actuels :': 'Current elements:',
    'personnages': 'characters',
    'accessoires': 'props',
    'Plans storyboard :': 'Storyboard shots:',
    'Estimation (éléments actuels) :': 'Estimate (current elements):',
    "L'extraction peut créer plus d'éléments — le coût final sera plus élevé.": 'Extraction may create more elements — the final cost will be higher.',
    'Estimation (sans données actuelles) :\n  • Images Nano Banana : ~$0.039/image (standard) — $0.15/image (Pro)\n  • Moods Flux IA : ~$0.06/image\n  • Extraction Claude IA : < $0.05': 'Estimate (no current data):\n  • Nano Banana images: ~$0.039/image (standard) — $0.15/image (Pro)\n  • Flux AI Moods: ~$0.06/image\n  • Claude AI extraction: < $0.05',
    '⚠  Les tarifs sont indicatifs et peuvent varier.\nConsultez fal.ai pour vérifier les prix actuels avant de lancer.': '⚠  Prices are indicative and may vary.\nCheck fal.ai for current prices before launching.',
    "💡  La méthode la moins coûteuse\n\nIdentifiez vos éléments manuellement et créez-les un à un dans les onglets dédiés : Castings pour les personnages, Décors, Accessoires, HMC, Véhicules. Vous gardez ainsi la main sur chaque génération d'image et ne payez que ce que vous validez.\n\n« Tout générer » est pratique pour un premier jet rapide, mais chaque image générée automatiquement est facturée — le coût peut rapidement devenir élevé si le scénario contient de nombreux éléments.": '💡  The least expensive method\n\nIdentify your elements manually and create them one by one in the dedicated tabs: Castings for characters, Sets, Props, HMC, Vehicles. This way you keep control over each image generation and only pay for what you validate.\n\n« Generate all » is handy for a quick first draft, but each automatically generated image is billed — the cost can quickly become high if the screenplay contains many elements.',
    "⚠  ATTENTION — SUPPRESSION PRÉALABLE\n\nAvant de régénérer, cette opération va d'abord supprimer\nTOUS les personnages, décors, accessoires, HMC, véhicules\net plans storyboard existants.\n\nCette action est irréversible. Partez d'un scénario finalisé.": '⚠  WARNING — PRIOR DELETION\n\nBefore regenerating, this operation will first delete\nALL existing characters, sets, props, HMC, vehicles\nand storyboard shots.\n\nThis action is irreversible. Start from a finalized screenplay.',
    '⚡  Lancer la génération complète': '⚡  Launch full generation',

    # ── Lot 16 — Analyse références visuelles + plans importés ──
    "Analyser avec Claude": "Analyze with Claude",
    "Décrypte les images pour enrichir le scénario": "Decodes the images to enrich the screenplay",
    "Analyse en cours via Claude…": "Analysis in progress via Claude…",
    "Références visuelles — Analyse Claude": "Visual references — Claude Analysis",
    "◎  Analyse des références visuelles": "◎  Visual references analysis",
    "◎  Enrichir le scénario": "◎  Enrich the screenplay",
    "image(s) analysée(s)": "image(s) analyzed",
    "plans importés dans le Storyboard ✓": "shots imported into the Storyboard ✓",
    "plans importés ✓": "shots imported ✓",

    # ── Références visuelles Live — persistance, bibliothèque, chat DA ──
    "Analyse des références disponible ✓": "Reference analysis available ✓",
    "Discuter de la direction artistique avec": "Discuss the art direction with",
    "Envoyer": "Send",
    "Vous": "You",
    "↻  Relancer l'analyse": "↻  Re-run analysis",
    "Refait l'analyse complète des images (une requête par image).":
        "Re-runs the full image analysis (one request per image).",
    "Aucune image dans la section Références visuelles.":
        "No image in the Visual references section.",
    "Relancer l'analyse": "Re-run analysis",
    "Relancer l'analyse complète ?": "Re-run the full analysis?",
    "requête(s) IA": "AI request(s)",
    "💾  Sauvegarder": "💾  Save",
    "Sauvegarde cette analyse dans la bibliothèque globale\npour la réutiliser dans d'autres projets.":
        "Saves this analysis to the global library\nto reuse it in other projects.",
    "Sauvegarder l'analyse": "Save analysis",
    "Nom de l'analyse :": "Analysis name:",
    "Analyse sans titre": "Untitled analysis",
    "Analyse sauvegardée dans la bibliothèque ✓": "Analysis saved to the library ✓",
    "📂  Bibliothèque": "📂  Library",
    "Charge une analyse sauvegardée — mêmes références visuelles,\nmême direction artistique, sans refaire l'analyse.":
        "Loads a saved analysis — same visual references,\nsame art direction, without re-running the analysis.",
    "Analyse chargée": "Analysis loaded",
    "Charger une analyse": "Load an analysis",
    "Recharge une analyse sauvegardée — réutilisable entre projets":
        "Reloads a saved analysis — reusable across projects",
    "Supprimer une analyse": "Delete an analysis",
    "Aucune analyse sauvegardée": "No saved analysis",
    "Analyse supprimée de la bibliothèque.": "Analysis deleted from the library.",

    # ── Bibliothèque d'images globale (Cinéma + Live) ──
    "Bibliothèque d'images": "Image library",
    "📚  Bibliothèque d'images": "📚  Image library",
    "Partagée entre tous les projets — Cinéma et Live":
        "Shared across all projects — Cinema and Live",
    "Nouvelle collection": "New collection",
    "Renommer la collection": "Rename collection",
    "Supprimer la collection": "Delete collection",
    "Nom de la collection :": "Collection name:",
    "Crée une collection (✚) puis ajoute-lui des images.":
        "Create a collection (✚) then add images to it.",
    "⬆  Ajouter des images": "⬆  Add images",
    "Copie des images du disque dans cette collection\n(la bibliothèque garde sa propre copie).":
        "Copies images from disk into this collection\n(the library keeps its own copy).",
    "Retirer de la collection": "Remove from collection",
    "💻  Parcourir le disque…": "💻  Browse disk…",
    "Choisir des fichiers hors bibliothèque —\nPANDORA proposera de les ranger dans une collection.":
        "Pick files outside the library —\nPANDORA will offer to file them into a collection.",
    "✓  Utiliser la sélection": "✓  Use selection",
    "Utiliser la sélection": "Use selection",
    "Supprimer cette collection et ses images ?":
        "Delete this collection and its images?",
    "les copies de la bibliothèque seront effacées.":
        "the library copies will be erased.",
    "Ajouter des images à la collection": "Add images to the collection",
    "Choisir des images sur le disque": "Pick images from disk",
    "Ajouter aussi ces images à la collection courante ?":
        "Also add these images to the current collection?",
    "⬆  Importer une image": "⬆  Import an image",
    "Utiliser une image à toi comme mood — choisie dans la\nbibliothèque ou sur le disque (copiée dans le plan).":
        "Use one of your own images as the mood — picked from the\nlibrary or from disk (copied into the shot).",
    "Image(s) importée(s) — clique « Activer » pour en faire le mood du plan.":
        "Image(s) imported — click « Activate » to make it the shot's mood.",
    "◎  Mood inspiré d'une image": "◎  Mood inspired by an image",
    "Choisis une image d'inspiration (bibliothèque ou disque) :\nson univers — palette, lumière, matières, style — est transposé\nsur la façade (mapping) ou réinterprété pour le plan.\nL'image n'est jamais collée telle quelle.":
        "Pick an inspiration image (library or disk):\nits universe — palette, light, materials, style — is transposed\nonto the facade (mapping) or reinterpreted for the shot.\nThe image is never pasted as-is.",
    "Mood inspiré de l'image…": "Mood inspired by the image…",
    "Envoi de la façade et de l'inspiration à fal.ai…":
        "Sending facade and inspiration to fal.ai…",
    "Mood inspiré sur la façade (Kontext multi)…":
        "Inspired mood on the facade (Kontext multi)…",
    "Envoi de l'image d'inspiration à fal.ai…":
        "Sending inspiration image to fal.ai…",
    "Mood inspiré de l'image (Kontext)…":
        "Mood inspired by the image (Kontext)…",
    "Co-écrire l'arrangement avec": "Co-write the arrangement with",
    "plan(s) → colonnes Musique/BPM remplies": "shot(s) → Music/BPM columns filled",
    "Aucun plan — génère le découpage depuis le Conducteur.":
        "No shot — generate the breakdown from the Rundown.",
    "Charge les plans en file d'attente — la sélection du Conducteur\nsi tu en as une (Ctrl+clic = multi), sinon toute la séquence.":
        "Loads shots into the queue — the Rundown selection\nif you have one (Ctrl+click = multi), otherwise the whole sequence.",
    "RENDU": "OUTPUT",
    "Assembler la bande-son (durée exacte)":
        "Assemble the soundtrack (exact duration)",
    "À la fin de la file : une seule piste CALÉE sur la vidéo — chaque plan garde sa durée exacte, micro-fondus aux jonctions (pas de coupes nettes, pas de décalage).":
        "When the queue ends: one single track ALIGNED with the video — every shot keeps its exact duration, micro-fades at junctions (no hard cuts, no drift).",
    "prompt son chargé ✓": "sound prompt loaded ✓",
    "⚠ pas de prompt son sur ce plan (champ 🔊 Son)":
        "⚠ no sound prompt on this shot (🔊 Sound field)",

    # ── Lot 17 — co-écriture (accueil), génération en série, divers ──
    "J'ai analysé votre scénario et rédigé des suggestions détaillées (visibles dans l'onglet « Analyse initiale »).\n\nDites-moi ce que vous souhaitez modifier, affiner ou conserver — je produirai alors une version remaniée de votre scénario en direct. Nous pouvons itérer autant de fois que nécessaire.": "I've analyzed your screenplay and written detailed suggestions (visible in the « Initial analysis » tab).\n\nTell me what you'd like to change, refine or keep — I'll then produce a reworked version of your screenplay live. We can iterate as many times as needed.",
    "Génération en série": "Batch generation",
    "Vous avez sélectionné": "You selected",
    "plans.": "shots.",
    "La génération sera lancée en file d'attente — un clip après l'autre.\n\n⚠  Chaque plan consomme des crédits fal.ai.": "Generation will run in a queue — one clip after another.\n\n⚠  Each shot consumes fal.ai credits.",
    "Impossible d'ouvrir la fenêtre de soutien.": "Could not open the support window.",
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

    # ── Tab Modifier depuis DaVinci Resolve ────────────────────────────────────
    "Modifier depuis DaVinci Resolve — Génération batch":
        "Edit from DaVinci Resolve — Batch generation",
    "▸ Sélectionner des clips spécifiques : clic droit sur chaque clip → Flag → couleur.":
        "▸ Select specific clips: right-click each clip → Flag → color.",
    "  pandora_send n'envoie que les clips flaggés. Sans flag = toute la timeline.":
        "  pandora_send only sends flagged clips. No flag = entire timeline.",
    "▸ Envoyez vos clips : Espace de travail → Scripts → pandora_send":
        "▸ Send your clips: Workspace → Scripts → pandora_send",
    "  (ou votre raccourci clavier — Personnalisation du clavier → pandora_send).":
        "  (or your keyboard shortcut — Keyboard Customization → pandora_send).",
    "▸ Écrivez un prompt global ou un prompt différent par clip.":
        "▸ Write a global prompt or a different prompt per clip.",
    "▸ Cliquez sur « Lancer la file d'attente » : chaque clip est uploadé comme référence":
        "▸ Click 'Launch queue': each clip is uploaded as a reference",
    "  vidéo (@Video1) et Seedance génère une nouvelle version selon votre prompt,":
        "  video (@Video1) and Seedance generates a new version based on your prompt,",
    "  séquentiellement (1 clip à la fois), N prises par clip.":
        "  sequentially (1 clip at a time), N takes per clip.",
    "▸ Les vidéos générées sont automatiquement importées dans le Media Pool de DaVinci.":
        "▸ Generated videos are automatically imported into DaVinci's Media Pool.",
    "⚠  Format requis par Seedance 2.0 pour l'upload de référence vidéo :":
        "⚠  Format required by Seedance 2.0 for video reference upload:",
    "  • Résolution : 720p maximum":             "  • Resolution: 720p maximum",
    "  • Taille : moins de 50 MB":               "  • Size: less than 50 MB",
    "  • Format : H.264 MP4 ou MOV recommandé":  "  • Format: H.264 MP4 or MOV recommended",
    "  → Depuis DaVinci : Fichier → Exporter → sélectionner H.264 Master à 720p":
        "  → From DaVinci: File → Export → select H.264 Master at 720p",
    "    avant d'envoyer les clips via pandora_send.":
        "    before sending clips via pandora_send.",

    # Status bridge
    "○  Bridge non connecté":                   "○  Bridge not connected",
    "↻  Actualiser":                             "↻  Refresh",
    "Pour connecter le bridge : dans DaVinci Resolve Studio →\n"
    "Espace de travail → Scripts → seedance_bridge\n"
    "Laissez la fenêtre PANDORA Bridge ouverte pendant votre session.":
        "To connect the bridge: in DaVinci Resolve Studio →\n"
        "Workspace → Scripts → seedance_bridge\n"
        "Keep the PANDORA Bridge window open during your session.",

    # Style film
    "selon image de référence":                  "according to reference image",
    "\U0001f5bc  Template de style":             "\U0001f5bc  Style template",

    # ADN visuel
    "🔓  ADN visuel — aléatoire":                "🔓  Visual DNA — random",
    "🔒  ADN visuel — garder pour tous les plans": "🔒  Visual DNA — keep for all shots",

    # Section Clips importés
    "Clips importés":                            "Imported clips",
    "▼  Clips importés":                         "▼  Imported clips",
    "▶  Clips importés":                         "▶  Imported clips",
    "Tout désélectionner":                       "Deselect all",
    "✕  Vider la liste":                         "✕  Clear list",
    "Aucun clip — lancez pandora_send dans DaVinci (Espace de travail → Scripts)":
        "No clips — run pandora_send in DaVinci (Workspace → Scripts)",

    # Section Prompt de modification
    "Prompt de modification":                    "Edit prompt",
    "▼  Prompt de modification":                 "▼  Edit prompt",
    "▶  Prompt de modification":                 "▶  Edit prompt",
    "Prompt global":                             "Global prompt",
    "Prompt par clip":                           "Per-clip prompt",
    "← Sélectionne un clip pour écrire son prompt":
        "← Select a clip to write its prompt",

    # Section Paramètres (section headers)
    "16:9 — Paysage":                            "16:9 — Landscape",
    "9:16 — Portrait":                           "9:16 — Portrait",
    "▼  Paramètres":                             "▼  Settings",
    "▶  Paramètres":                             "▶  Settings",

    # Section File d'attente
    "File d'attente":                            "Queue",
    "▼  File d'attente":                         "▼  Queue",
    "▶  File d'attente":                         "▶  Queue",
    "Aucune génération en cours.":               "No generation in progress.",
    "Import auto dans DaVinci Media Pool après génération":
        "Auto import to DaVinci Media Pool after generation",
    "▶▶  Lancer la file d'attente":              "▶▶  Launch queue",
    "📁  Ouvrir le dossier des vidéos":          "📁  Open videos folder",
    "Ouvrir le dossier des vidéos":              "Open videos folder",
    "Nombre de prises par clip (1–10)":          "Number of takes per clip (1–10)",

    # Dialog bridge non connecté
    "Bridge non connecté":                       "Bridge not connected",
    "○  Le bridge DaVinci n'est pas connecté.\n\n"
    "Les vidéos générées ne seront pas importées\n"
    "automatiquement dans le Media Pool.\n\n"
    "Pour connecter le bridge :\n"
    "DaVinci Resolve → Espace de travail → Scripts → seedance_bridge\n"
    "Laissez la fenêtre PANDORA Bridge ouverte.":
        "○  The DaVinci bridge is not connected.\n\n"
        "Generated videos will not be imported\n"
        "automatically into the Media Pool.\n\n"
        "To connect the bridge:\n"
        "DaVinci Resolve → Workspace → Scripts → seedance_bridge\n"
        "Keep the PANDORA Bridge window open.",
    "↻  Vérifier la connexion":                  "↻  Check connection",
    "Générer sans import":                       "Generate without import",

    # Warning dialogs queue
    "Génération en cours":                       "Generation in progress",
    "Une génération est déjà en cours. Attendez qu'elle se termine.":
        "A generation is already in progress. Wait for it to finish.",
    "Aucun clip sélectionné":                    "No clip selected",
    "Cochez au moins un clip avant de lancer la file d'attente.":
        "Check at least one clip before launching the queue.",

    # Status labels
    "File annulée.":                             "Queue cancelled.",
    "× Retirer":                                 "× Remove",

    # Enhance Claude — DaVinci Edit prompts
    "Optimiser avec Claude\nAméliore le prompt de modification pour Seedance 2.0.":
        "Optimize with Claude\nImproves the modification prompt for Seedance 2.0.",
    "Prompt vide":                               "Empty prompt",
    "Écris un prompt à améliorer !":             "Write a prompt to improve!",
    "Amélioration impossible":                   "Cannot improve",

    # Format validation
    "Format non supporté":                       "Unsupported format",

    # ── HelpBlock — titres ────────────────────────────────────────────────────
    "Scénario — Éditeur et assistant Claude IA":
        "Screenplay — Editor and Claude AI assistant",
    "Storyboard — Découpage plan par plan":
        "Storyboard — Shot-by-shot breakdown",
    "Castings — Personnages du film":
        "Cast — Film characters",
    "Décors — Lieux de tournage":
        "Locations — Shooting locations",
    "Accessoires — Props & matériel":
        "Props — Equipment & materials",
    "HMC — Habillage, Maquillage, Coiffure":
        "HMC — Costume, Makeup, Hair",
    "Véhicules — Parc automobile & transport":
        "Vehicles — Fleet & transport",
    "Image & Son":
        "Camera & Sound",
    "Doublage & Synthèse vocale IA":
        "Dubbing & AI Voice Synthesis",
    "Image-to-Video — Animer une image fixe":
        "Image-to-Video — Animate a still image",
    "Extension de clip — Prolonger ou modifier":
        "Clip Extension — Extend or modify",
    "Référence multimodale — Guider avec image, vidéo ou audio":
        "Multimodal Reference — Guide with image, video or audio",
    "Historique des générations":
        "Generation history",
    "Paramètres — Clés API et préférences":
        "Settings — API keys and preferences",

    # ── HelpBlock — page Scénario ─────────────────────────────────────────────
    "▸ Rédigez ou collez votre scénario, puis utilisez Claude pour le formater en mise en page cinéma standard.":
        "▸ Write or paste your screenplay, then use Claude to format it in standard cinema layout.",
    "▸ Arrangement IA : Claude analyse la structure narrative et propose des améliorations (intensité réglable 1-10).":
        "▸ AI Arrangement: Claude analyzes the narrative structure and suggests improvements (adjustable intensity 1-10).",
    "▸ Générez automatiquement depuis le scénario : personnages, décors, accessoires, HMC, véhicules et storyboard.":
        "▸ Auto-generate from the screenplay: characters, locations, props, HMC, vehicles and storyboard.",
    "▸ Versions : sauvegardez plusieurs versions nommées et basculez entre elles à tout moment.":
        "▸ Versions: save multiple named versions and switch between them at any time.",
    "▸ Undo\\Redo : chaque modification par Claude est annulable — les boutons ↩ ↪ conservent l'historique manuel.":
        "▸ Undo/Redo: every Claude edit is reversible — the ↩ ↪ buttons keep the manual history.",
    "▸ Style de film : le style sélectionné ici se propage à Seedance 2.0 et aux générations d'éléments.":
        "▸ Film style: the style selected here propagates to Seedance 2.0 and element generations.",

    # ── HelpBlock — page Storyboard ───────────────────────────────────────────
    "▸ Chaque ligne représente un plan : numéro, mouvement caméra, valeur, focale, vitesse, décor, acteurs.":
        "▸ Each row represents a shot: number, camera movement, size, focal, speed, location, actors.",
    "▸ Cliquez sur une cellule pour modifier en ligne, ou sur Éditer pour ouvrir la fiche complète du plan.":
        "▸ Click a cell to edit inline, or click Edit to open the full shot card.",
    "▸ Glissez-déposez les plans (⠿) pour réorganiser le découpage.":
        "▸ Drag and drop shots (⠿) to reorder the breakdown.",
    "▸ Mood IA : générez automatiquement le prompt Seedance de chaque plan depuis la description de la scène.":
        "▸ AI Mood: automatically generate the Seedance prompt for each shot from the scene description.",
    "▸ Bouton Générer (▶) sur chaque plan : envoie directement le plan vers Seedance 2.0 pour la génération.":
        "▸ Generate button (▶) on each shot: sends the shot directly to Seedance 2.0 for generation.",
    "▸ Versions : gérez plusieurs versions du découpage (découpage final, alternatives, montage court…).":
        "▸ Versions: manage multiple breakdown versions (final cut, alternatives, short edit…).",

    # ── HelpBlock — page Décors ───────────────────────────────────────────────
    "▸ Répertoriez tous les lieux de tournage avec description, ambiance et contraintes techniques.":
        "▸ List all shooting locations with description, atmosphere and technical constraints.",
    "▸ Ajoutez des images de référence (photo de repérage, moodboard) pour chaque décor.":
        "▸ Add reference images (location scouting photo, moodboard) for each location.",
    "▸ Catégorisez par type (intérieur, extérieur, studio…) pour filtrer rapidement.":
        "▸ Categorize by type (interior, exterior, studio…) for quick filtering.",
    "▸ Les décors sont assignables aux plans du storyboard pour un suivi de production précis.":
        "▸ Locations can be assigned to storyboard shots for precise production tracking.",
    "▸ La liste des décors peut être générée automatiquement depuis le scénario (page Scénario → Claude IA).":
        "▸ The location list can be auto-generated from the screenplay (Screenplay page → Claude AI).",

    # ── HelpBlock — page Accessoires ──────────────────────────────────────────
    "▸ Listez tous les accessoires nécessaires au tournage avec description et quantité.":
        "▸ List all props needed for the shoot with description and quantity.",
    "▸ Ajoutez des images de référence pour chaque prop afin de faciliter les achats et la régie.":
        "▸ Add reference images for each prop to facilitate purchasing and production management.",
    "▸ Assignez les accessoires aux personnages et aux plans du storyboard.":
        "▸ Assign props to characters and storyboard shots.",
    "▸ La liste peut être générée automatiquement depuis le scénario (page Scénario → Claude IA).":
        "▸ The list can be auto-generated from the screenplay (Screenplay page → Claude AI).",

    # ── HelpBlock — page HMC ─────────────────────────────────────────────────
    "▸ Créez une fiche HMC par personnage ou par scène avec description et références visuelles.":
        "▸ Create an HMC card per character or scene with description and visual references.",
    "▸ Catégories : Habillage (costumes, tenues), Maquillage, Coiffure, Effets spéciaux.":
        "▸ Categories: Costume, Makeup, Hair, Special effects.",
    "▸ Ajoutez des images de référence pour chaque élément afin de guider les équipes artistiques.":
        "▸ Add reference images for each item to guide the artistic teams.",
    "▸ Les fiches HMC peuvent être générées automatiquement depuis le scénario (page Scénario → Claude IA).":
        "▸ HMC cards can be auto-generated from the screenplay (Screenplay page → Claude AI).",

    # ── HelpBlock — page Véhicules ────────────────────────────────────────────
    "▸ Répertoriez tous les véhicules nécessaires au tournage (voitures, motos, camions…).":
        "▸ List all vehicles needed for the shoot (cars, motorcycles, trucks…).",
    "▸ Précisez la marque, le modèle, l'année, la couleur et les contraintes de disponibilité.":
        "▸ Specify the brand, model, year, color and availability constraints.",
    "▸ Ajoutez des images de référence pour faciliter la recherche et la location.":
        "▸ Add reference images to facilitate sourcing and rental.",

    # ── HelpBlock — page Image & Son ──────────────────────────────────────────
    "▸ Bloc 1 — Réglages techniques : corps de caméra, optiques, filtres et microphone.":
        "▸ Block 1 — Technical settings: camera body, lenses, filters and microphone.",
    "  Ces préférences sont injectées dans les prompts Seedance pour guider le rendu visuel.":
        "  These preferences are injected into Seedance prompts to guide the visual rendering.",
    "▸ Bloc 2 — Sound Design : génère des ambiances sonores IA (Mirelo AI SFX 1.6 · $0.01/s).":
        "▸ Block 2 — Sound Design: generates AI soundscapes (Mirelo AI SFX 1.6 · $0.01/s).",
    "  L'audio généré est automatiquement importé dans le Media Pool de DaVinci Resolve.":
        "  Generated audio is automatically imported into DaVinci Resolve's Media Pool.",

    # ── HelpBlock — page Doublage ─────────────────────────────────────────────
    "▸ ElevenLabs Turbo v2.5 : synthèse vocale avec sélection de voix — principalement anglais, résultats variables en français.":
        "▸ ElevenLabs Turbo v2.5: voice synthesis with voice selection — mainly English, variable results in French.",
    "▸ F5-TTS Clonage : clone une voix depuis un échantillon audio — langue détectée depuis le texte. Entraîné principalement sur l'anglais et le chinois : le français peut sonner avec un accent.":
        "▸ F5-TTS Cloning: clones a voice from an audio sample — language detected from text. Trained mainly on English and Chinese: French may sound accented.",
    "▸ Note : les modèles de synthèse vocale IA sont encore peu optimisés pour le français. Pour un résultat professionnel en FR, un comédien de doublage reste la meilleure option.":
        "▸ Note: AI voice synthesis models are still poorly optimized for French. For professional FR results, a voice actor remains the best option.",
    "▸ Sélectionne un mode, écris le texte, puis clique sur « Générer l'audio ».":
        "▸ Select a mode, write the text, then click 'Generate audio'.",
    "▸ Les fichiers générés apparaissent en bas — clique ▶ pour écouter ou 📁 pour ouvrir le dossier.":
        "▸ Generated files appear below — click ▶ to listen or 📁 to open the folder.",

    # ── HelpBlock — tab I2V ───────────────────────────────────────────────────
    "▸ Chargez une image (PNG · JPG · WEBP) pour l'animer et en faire un clip vidéo.":
        "▸ Load an image (PNG · JPG · WEBP) to animate it into a video clip.",
    "▸ Ajoutez un prompt pour décrire le mouvement et l'ambiance souhaitée.":
        "▸ Add a prompt to describe the desired movement and atmosphere.",
    "▸ Activez Référence casting pour injecter les portraits des personnages sélectionnés.":
        "▸ Enable Cast Reference to inject the portraits of selected characters.",
    "▸ Choisissez la durée (2–10 s), la résolution et le style de film avant de lancer.":
        "▸ Choose the duration (2–10 s), resolution and film style before launching.",
    "▸ Sans clé fal.ai → mode mock (simulation locale, aucun crédit consommé).":
        "▸ Without a fal.ai key → mock mode (local simulation, no credits used).",

    # ── HelpBlock — tab Extension ─────────────────────────────────────────────
    "▸ Prolongez un clip existant avant (étendre au début) ou après (étendre à la fin) sa durée originale.":
        "▸ Extend an existing clip before (extend at start) or after (extend at end) its original duration.",
    "▸ Mode Nouveau rush : génère une nouvelle prise à partir du même clip source.":
        "▸ New take mode: generates a new take from the same source clip.",
    "▸ Importez un fichier vidéo local ou récupérez le clip actif depuis la timeline DaVinci Resolve.":
        "▸ Import a local video file or retrieve the active clip from the DaVinci Resolve timeline.",
    "▸ Ajoutez un prompt pour guider la direction visuelle de la continuation.":
        "▸ Add a prompt to guide the visual direction of the continuation.",
    "▸ La durée ajoutée s'additionne à la durée originale du clip source.":
        "▸ The added duration is cumulative with the original source clip duration.",

    # ── HelpBlock — tab Référence ─────────────────────────────────────────────
    "▸ Combinez jusqu'à 3 références (image + vidéo + audio) pour guider la génération.":
        "▸ Combine up to 3 references (image + video + audio) to guide generation.",
    "▸ Image de référence : impose l'apparence visuelle, les couleurs et la composition.":
        "▸ Reference image: imposes the visual appearance, colors and composition.",
    "▸ Vidéo de référence : guide le mouvement et le rythme du clip généré.":
        "▸ Reference video: guides the movement and rhythm of the generated clip.",
    "▸ Audio de référence : synchronise l'ambiance sonore avec le rendu visuel.":
        "▸ Reference audio: synchronizes the soundscape with the visual rendering.",
    "▸ Ajoutez un prompt pour affiner davantage le résultat au-delà des références.":
        "▸ Add a prompt to further refine the result beyond the references.",

    # ── HelpBlock — tab Historique ────────────────────────────────────────────
    "▸ Retrouvez toutes les générations effectuées pour ce projet (50 entrées max).":
        "▸ Find all generations made for this project (50 entries max).",
    "▸ Chaque entrée affiche le mode (T2V · I2V · Extension · Référence), le prompt, la durée et la résolution.":
        "▸ Each entry shows the mode (T2V · I2V · Extension · Reference), prompt, duration and resolution.",
    "▸ Les clips sont sauvegardés localement ; utilisez le bouton Import DaVinci au moment de la génération.":
        "▸ Clips are saved locally; use the Import DaVinci button at the time of generation.",

    # ── HelpBlock — tab Paramètres ────────────────────────────────────────────
    "▸ Clé fal.ai : requise pour générer des vidéos réelles via Seedance 2.0. Sans clé → mode mock.":
        "▸ fal.ai key: required to generate real videos via Seedance 2.0. Without key → mock mode.",
    "▸ Clé Anthropic : requise pour l'assistant Claude (formatage scénario, génération storyboard, optimisation prompts).":
        "▸ Anthropic key: required for the Claude assistant (screenplay formatting, storyboard generation, prompt optimization).",
    "▸ Clé Nano Banana : requise pour la génération de portraits de personnages (page Castings).":
        "▸ Nano Banana key: required for character portrait generation (Cast page).",
    "▸ Dossier de sortie : répertoire local où sont sauvegardés les clips générés.":
        "▸ Output folder: local directory where generated clips are saved.",

    # ── Onboarding / Guide de démarrage ──────────────────────────────────────
    "Guide de démarrage - PANDORA":              "Getting Started - PANDORA",
    "Passer":                                    "Skip",
    "Guide de configuration des services IA":   "AI Services Configuration Guide",
    "Voir le tutoriel":                          "Watch the tutorial",
    "Ne plus afficher ce message":               "Don't show this again",
    "Tutoriel complet PANDORA":                  "Complete PANDORA Tutorial",
    "Visionner le tuto sur notre chaine de vidéo — YouTube":
        "Watch the tutorial on our YouTube channel",
    "Configurer ffal.ai":                        "Set up fal.ai",
    "Configurer Anthropic":                      "Set up Anthropic",
    "Coller les clés":                           "Paste the keys",
    "Coller les clés dans PANDORA":              "Paste the keys into PANDORA",
    "Aller aux Paramètres ->":                   "Go to Settings →",
    "Créer un compte (Sign up)":                 "Create an account (Sign up)",
    "Ouvrir ffal.ai/signup":                     "Open fal.ai/signup",
    "Ouvrir ffal.ai/dashboard/keys":             "Open fal.ai/dashboard/keys",
    "Ouvrir Billing":                            "Open Billing",
    "Ouvrir console.anthropic.com":              "Open console.anthropic.com",
    "Ouvrir API Keys":                           "Open API Keys",
    "Recommandé : 10$ minimum":                  "Recommended: $10 minimum",
    "Recommandé : 15$ minimum":                  "Recommended: $15 minimum",

    # ── Splash / Projet ───────────────────────────────────────────────────────
    "PROJETS RÉCENTS - CINÉMA":                  "RECENT PROJECTS - CINEMA",
    "Nouveau projet PANDORA":                    "New PANDORA project",
    "Mon Film":                                  "My Film",
    "Choisir...":                                "Choose...",
    "Créer le projet":                           "Create project",

    # ── Mise à jour ───────────────────────────────────────────────────────────
    "Mise à jour":                               "Update",
    "PANDORA est à jour.":                       "PANDORA is up to date.",
    "Vérifier les mises à jour":                 "Check for updates",

    # ── Financement ───────────────────────────────────────────────────────────
    "Finance le developpement":                  "Fund development",
    "Financer le développement":                 "Fund development",
    "Choisissez votre moyen de soutenir le developpement de PANDORA :":
        "Choose how to support PANDORA's development:",
    "Cryptomonnaie":                             "Cryptocurrency",
    "Bientôt disponible...":                     "Coming soon...",
    "Bientôt disponible… (Prochaine version)":   "Coming soon… (Next version)",

    # ── Page Scénario — manquants ─────────────────────────────────────────────
    "Proposer un arrangement":                   "Propose an arrangement",
    "Mise en page PANDORA":                      "PANDORA Layout",
    "Session de co-écriture":                    "Co-writing session",
    "Appliquer les suggestions":                 "Apply suggestions",
    "DIALOGUE AVEC CLAUDE":                      "DIALOGUE WITH CLAUDE",
    "VOTRE INSTRUCTION":                         "YOUR INSTRUCTION",
    "Envoyer à Claude":                          "Send to Claude",
    "Mise en page PANDORA — Aperçu":             "PANDORA Layout — Preview",
    "Mise en page PANDORA terminée":             "PANDORA layout complete",
    "Aucun scénario détecté.":                   "No screenplay detected.",
    "Remplacer le texte":                        "Replace text",
    "Comment souhaitez-vous procéder ?":         "How would you like to proceed?",
    "Identifier les personnages":                "Identify characters",
    "Identifier les décors":                     "Identify locations",
    "Identifier les accessoires":                "Identify props",
    "Identifier les véhicules":                  "Identify vehicles",
    "Identifier la HMC":                         "Identify HMC",
    "Identifier et générer les images":          "Identify and generate images",
    "Claude analyse le scénario...":             "Claude is analyzing the screenplay...",
    "Aucun élément détecté dans le scénario.":   "No elements detected in the screenplay.",
    "Générer — Personnages depuis le scénario":  "Generate — Characters from screenplay",
    "Générer — Décors depuis le scénario":       "Generate — Locations from screenplay",
    "Générer — Accessoires depuis le scénario":  "Generate — Props from screenplay",
    "Générer — HMC depuis le scénario":          "Generate — HMC from screenplay",
    "Générer — Véhicules depuis le scénario":    "Generate — Vehicles from screenplay",
    "Générer — Découpage Storyboard":            "Generate — Storyboard Breakdown",
    "Générer characters":                        "Generate characters",
    "Générer les décors":                        "Generate locations",
    "Générer les accessoires":                   "Generate props",
    "Générer la HMC":                            "Generate HMC",
    "Générer les véhicules":                     "Generate vehicles",
    "Générer le storyboard":                     "Generate storyboard",
    "Analyse en cours...":                       "Analyzing...",
    "L'analyse apparaît ici au fil de la génération...":
        "Analysis will appear here as it generates...",
    "Arrangement — Analyse":                     "Arrangement — Analysis",
    "Studio de Création — Co-écriture avec Claude":
        "Creation Studio — Co-writing with Claude",
    "Glissez-déposez des images ou cliquez pour en ajouter":
        "Drag and drop images or click to add",
    "Soumettez un scénario avec scènes, personnages et dialogues pour que j'en génère la mise en page PANDORA.":
        "Submit a screenplay with scenes, characters and dialogue so I can generate the PANDORA layout.",

    # ── Page Storyboard — manquants ───────────────────────────────────────────
    "Storyboard — Planification plan par plan":  "Storyboard — Shot-by-shot planning",
    "Aucun découpage pour ce projet.":           "No breakdown for this project.",
    "Génère un découpage depuis l'onglet Scénario.":
        "Generate a breakdown from the Screenplay tab.",
    "Aucun découpage pour ce projet.\n\nGénère un découpage depuis le Conducteur.":
        "No breakdown for this project.\n\nGenerate a breakdown from the Rundown.",
    "Aucun plan dans ce découpage.\n\nClique ＋ Ajouter un plan pour créer un plan manuellement.":
        "No shot in this breakdown.\n\nClick ＋ Add a shot to create one manually.",

    # ── Page Castings — manquants ─────────────────────────────────────────────
    "Aucun personnage.":                         "No characters.",
    "Cliquez sur Créer un personnage pour commencer.":
        "Click Create a character to get started.",
    "Inspiration — Claude enrichit le prompt":   "Inspiration — Claude enriches the prompt",
    "Génération d'idées":                        "Idea generation",
    "Générer portrait":                          "Generate portrait",
    "Supprimer le fond":                         "Remove background",
    "Avertissement de prompt":                   "Prompt warning",

    # ── Pages éléments — manquants ────────────────────────────────────────────
    "Catégories : Toutes":                       "Categories: All",
    "Aucun décor.":                              "No locations.",
    "Aucun accessoire.":                         "No props.",
    "Cliquez sur Créer un décor pour commencer.":
        "Click Create a location to get started.",
    "Cliquez sur Créer un accessoire pour commencer.":
        "Click Create a prop to get started.",
    "HMC — Habillage - Maquillage - Coiffure":   "HMC — Costume - Makeup - Hair",
    "Véhicule — Parc automobile":                "Vehicles — Fleet",
    "Véhicule — Parc automobile _transport":     "Vehicles — Fleet",

    # ── Page Image & Son — manquants ──────────────────────────────────────────
    "Réglages techniques":                       "Technical settings",

    # ── Page Doublage — manquants ─────────────────────────────────────────────
    "Doublage & Synthèse vocale IA":             "Dubbing & AI Voice Synthesis",
    "Prochainement — Intégration audio multi-personnages":
        "Coming soon — Multi-character audio integration",
    "TEXTE À SYNTHÉTISER":                       "TEXT TO SYNTHESIZE",
    "VOIX DISPONIBLES":                          "AVAILABLE VOICES",
    "VOIX ASSIGNÉES AUX PERSONNAGES":            "VOICES ASSIGNED TO CHARACTERS",
    "Clonage de voix — FS-TTS":                  "Voice cloning — FS-TTS",
    "Générer des voix à partir d'échantillons personnalisés...":
        "Generate voices from custom samples...",
    "Aucun fichier généré.":                     "No files generated.",

    # ── AI Studio — manquants ─────────────────────────────────────────────────
    "Générer depuis Storyboard":                 "Generate from Storyboard",
    "Modifier des clips":                        "Edit clips",
    "Vidéothèque":                               "Video Library",

    # ── Studio IA — Musique IA + Image IA (2026-06-15) ────────────────────────
    "Musique IA":                                "AI Music",
    "Image IA":                                  "AI Image",
    "Compose la musique de tes scènes : score instrumental ou chanson "
    "avec paroles, via les meilleurs moteurs de fal.ai.":
        "Compose the music for your scenes: instrumental score or song with "
        "lyrics, via the best fal.ai engines.",
    "MOTEUR DE GÉNÉRATION":                      "GENERATION ENGINE",
    "STYLE / DESCRIPTION":                       "STYLE / DESCRIPTION",
    "PAROLES (optionnel)":                       "LYRICS (optional)",
    "Décris la musique (en anglais de préférence). "
    "Ex. « epic orchestral score, slow build, strings and brass, cinematic, tense »":
        "Describe the music (preferably in English). "
        "E.g. « epic orchestral score, slow build, strings and brass, cinematic, tense »",
    "Paroles à chanter. Laisse vide pour un morceau instrumental.":
        "Lyrics to sing. Leave empty for an instrumental track.",
    "Générer la musique":                        "Generate music",
    "Décris d'abord la musique à générer.":      "Describe the music to generate first.",
    "Ouvre le dossier des musiques générées.":   "Opens the generated music folder.",

    # ── Plan des décors (vue de dessus, Mise en scène / Plan de feu) ───────────
    "Plan des décors":                           "Set floor plans",
    "— vus de dessus, synchronisés avec Mise en scène et Plan de feu":
        "— top-down, synced with Staging and Lighting plan",
    "Générer les plans manquants":               "Generate missing plans",
    "à générer":                                 "to generate",
    "Génération…":                               "Generating…",

    # ── Mise en scène / Plan de feu — outils & projecteurs (2026-06-16) ────────
    "Déplacer":                                  "Move",
    "Rotation":                                  "Rotate",
    "Raccourci : R":                             "Shortcut: R",
    "Choisir un projecteur":                     "Choose a fixture",
    "Famille":                                   "Family",
    "Modèle":                                    "Model",
    "Rôle :":                                    "Role:",
    "Nom affiché (laisser vide = modèle)":       "Display name (empty = model)",
    "Valider":                                   "Confirm",
    "Synchroniser la mise en scène":             "Sync staging",
    "Synchroniser le plan de feu":               "Sync lighting plan",
    "Générer les décors + plan":                 "Generate sets + plan",
    "Choisir une référence visuelle":            "Choose a visual reference",
    "Générer depuis les images de référence":    "Generate from reference images",
    "Notice audio":                              "Audio notice",
    "Prise de vue réelle":                       "Real footage",
    "Action de la caméra":                       "Camera action",
    "Améliorer le prompt":                       "Improve prompt",
    "Analyser le prompt":                        "Analyze prompt",
    "Vidéothèque — Bibliothèque des vidéos générées":
        "Video Library — Generated videos library",
    "Aucune vidéo générée dans ce projet.":      "No videos generated in this project.",
    "Lancez une génération depuis l'onglet Storyboard ou « Modifier des clips ».":
        "Start a generation from the Storyboard tab or 'Edit clips'.",
    "COHÉRENCE VISUELLE — maintenu":             "VISUAL CONSISTENCY — maintained",
    "Importer des fichiers vidéo":               "Import video files",
    "Décris la modification souhaitée...":       "Describe the desired edit...",
    "Décrivez précisément la scène à générer...": "Describe the scene to generate precisely...",
    "Sélection 2.0 (recommandé)":                "Selection 2.0 (recommended)",
    "Activer le rendu réaliste (ex: 8k, IMAX, grain argentique, ultra-réaliste, photo, etc.). Utile pour le rendu cinéma.":
        "Enable realistic rendering (e.g. 8K, IMAX, film grain, ultra-realistic, photo). Useful for cinema rendering.",

    # ── Page Paramètres — manquants ───────────────────────────────────────────
    "APPARENCE":                                 "APPEARANCE",
    "Sombre":                                    "Dark",
    "Clair":                                     "Light",
    "Test ffal.ai API":                          "Test fal.ai API",

    # ── Dialog Contact — manquants ────────────────────────────────────────────
    "Contactez-nous":                            "Contact us",
    "Communauté WhatsApp":                       "WhatsApp Community",
    "Rejoindre":                                 "Join",
    "Avis / suggestion — objet : Avis":          "Feedback — subject: Feedback",
    "Donnez votre avis, partagez vos idées et impressions.":
        "Share your feedback, ideas and impressions.",
    "Charte d'utilisation":                      "Terms of use",

    # ── Chips créatifs (creative_panel.py) ───────────────────────────────────
    "Éclairage":                    "Lighting",
    "Météo":                        "Weather",
    "Époque":                       "Era",
    "Photoréaliste":                "Photorealistic",
    "Néon":                         "Neon",
    "Héroïque":                     "Heroic",
    "Mystérieux":                   "Mysterious",
    "Épique":                       "Epic",
    "Crépuscule":                   "Dusk",
    "Ensoleillé":                   "Sunny",
    "Abandonné":                    "Abandoned",
    "Animé":                        "Animated",
    "Métal":                        "Metal",
    "Abîmé":                        "Worn",
    "Détail":                       "Detail",
    "Années 80":                    "80s",
    "Années 70":                    "70s",
    "Médiéval":                     "Medieval",
    "Endommagé":                    "Damaged",
    "Modifié":                      "Modified",
    "Chromé":                       "Chrome",
    "Rouillé":                      "Rusty",
    "Cinématique":                  "Cinematic",
    "Émotionnel":                   "Emotional",
    "↺  Réinitialiser":             "↺  Reset",

    # ── Sliders créatifs ─────────────────────────────────────────────────────
    "RÉALISATION":                  "EXECUTION",
    "Interprétation":               "Interpretation",
    "Littéral":                     "Literal",
    "Lumière":                      "Light",
    "Contrastée":                   "Contrasted",
    "FIDÉLITÉ":                     "FIDELITY",
    "Cohérence":                    "Consistency",
    "ESTHÉTIQUE":                   "AESTHETIC",
    "Stylisé":                      "Stylized",
    "Épurée":                       "Minimalist",
    "Désaturé":                     "Desaturated",
    "Éclatant":                     "Vibrant",
    "Tolérance":                    "Tolerance",
    "  Contrôles créatifs":         "  Creative controls",
    "  Liberté créative":           "  Creative freedom",
    "⚙  Contrôles créatifs    ":    "⚙  Creative controls    ",
    "Expérimental  —  Liberté créative maximale":
        "Experimental  —  Maximum creative freedom",
    "Très libre  —  Interprétation artistique affirmée":
        "Very free  —  Expressive artistic interpretation",
    "Libre  —  Grande liberté créative":
        "Free  —  Great creative freedom",
    "Créatif  —  Interprétation libre du prompt":
        "Creative  —  Free prompt interpretation",
    "Souple  —  Interprétation nuancée du prompt":
        "Flexible  —  Nuanced prompt interpretation",
    "Équilibré  —  Latitude artistique raisonnable":
        "Balanced  —  Reasonable artistic latitude",
    "Fidèle  —  Légère latitude sur les détails mineurs":
        "Faithful  —  Slight latitude on minor details",
    "Précis  —  Respecte strictement le prompt":
        "Precise  —  Strictly follows the prompt",
    "Strict  —  Composition précise et contrôlée":
        "Strict  —  Precise and controlled composition",
    "Très strict  —  Reproduction fidèle, sans interprétation":
        "Very strict  —  Faithful reproduction, no interpretation",

    # ── Panneau DaVinci ───────────────────────────────────────────────────────
    "— Non connecté":               "— Not connected",
    "Bridge installé ✓":            "Bridge installed ✓",
    "Échec installation":           "Installation failed",
    "Connecté":                     "Connected",
    "✓ Connecté":                   "✓ Connected",
    "Non connecté":                 "Not connected",
    "DaVinci non connecté":         "DaVinci not connected",

    # ── Dialog Mood / Aperçu ─────────────────────────────────────────────────
    "Recharger le prompt depuis les données du plan":
        "Reload prompt from shot data",
    "✦  Générer une variation":     "✦  Generate a variation",
    "Génération du Mood…":          "Generating Mood…",
    "Aucun Mood disponible\n\nCliquez sur  ✦  Générer une variation  pour créer le premier":
        "No Mood available\n\nClick  ✦  Generate a variation  to create the first one",

    # ── Dialog arrangement (session) ─────────────────────────────────────────
    "Minimal — uniquement ce qui est demandé, rien d'autre":
        "Minimal — only what is asked, nothing more",
    "Précis — modifie exactement les zones indiquées":
        "Precise — modifies exactly the indicated areas",
    "Ciblé — suit l'instruction, affine légèrement le style dans la zone":
        "Targeted — follows the instruction, slightly refines the style in the area",
    "Créatif — enrichit et reformule, retouche les passages adjacents":
        "Creative — enriches and rephrases, touches up adjacent passages",
    "Libre — réécrit dans son style, transforme le rythme et l'écriture":
        "Free — rewrites in its own style, transforms the rhythm and writing",
    "☁  Studio de Création — Co-écriture avec Claude":
        "☁  Creation Studio — Co-writing with Claude",
    "Remplace le scénario de l'éditeur par la version co-écrite avec Claude":
        "Replace the editor's screenplay with the co-written version",
    "Copier le scénario remanié dans le presse-papier":
        "Copy the revised screenplay to clipboard",
    "✏  Édition manuelle active":   "✏  Manual editing active",
    "✦  Scénario remanié":          "✦  Revised screenplay",
    "Envoyer à Claude  ☁":          "Send to Claude  ☁",
    "Ajouter des images de référence (max 4)":
        "Add reference images (max 4)",
    "Sélectionner des images de référence":
        "Select reference images",
    "Rédaction en cours…":          "Writing in progress…",

    # ── Dialog contact ────────────────────────────────────────────────────────
    "Communauté WhatsApp\nPANDORA | Cinéma":
        "WhatsApp Community\nPANDORA | Cinema",
    "Communauté WhatsApp\nPANDORA | Live":
        "WhatsApp Community\nPANDORA | Live",
    "Rejoignez les utilisateurs de PANDORA pour signaler des bugs, suivre les nouveautés et échanger avec la communauté.":
        "Join PANDORA users to report bugs, follow updates and connect with the community.",

    # ── Dialog extraction + génération ───────────────────────────────────────
    "⟳  Génération image…":         "⟳  Generating image…",
    "✓  Image générée":             "✓  Image generated",
    "✓  Sauvegardé":                "✓  Saved",
    "Choisir une option pour démarrer":
        "Choose an option to start",
    "Extrait et sauvegarde les éléments — sans générer d'images":
        "Extract and save elements — without generating images",
    "Extrait, sauvegarde, puis génère une image via Nano Banana pour chaque élément":
        "Extract, save, then generate an image via Nano Banana for each element",
    "Claude analyse le scénario…":  "Claude is analyzing the screenplay…",
    "Générer — ":                   "Generate — ",
    "  Identifier et générer les images":
        "  Identify and generate images",
    "Aucun élément identifié dans le scénario.":
        "No elements identified in the screenplay.",
    "Génération des images via Nano Banana…":
        "Generating images via Nano Banana…",
    " élément(s) sauvegardé(s) — sans image":
        " element(s) saved — without image",
    "✓  Terminé — ":                "✓  Done — ",
    " image(s) générée(s)":         " image(s) generated",
    " élément(s) sauvegardé(s) · ": " element(s) saved · ",
    "Personnages depuis le scénario":
        "Characters from screenplay",
    "Décors depuis le scénario":    "Locations from screenplay",
    "décors":                       "locations",
    "Accessoires depuis le scénario":
        "Props from screenplay",
    "HMC depuis le scénario":       "HMC from screenplay",
    "éléments HMC":                 "HMC items",
    "Véhicules depuis le scénario": "Vehicles from screenplay",
    "véhicules":                    "vehicles",
    " élément(s) identifié(s) — génération des images…":
        " element(s) identified — generating images…",
    "Voir les Décors":              "View Locations",
    "Voir les Véhicules":           "View Vehicles",

    # ── Dialog onboarding — étapes ────────────────────────────────────────────
    "fal.ai — Vidéos & Images IA":  "fal.ai — AI Videos & Images",
    "ÉTAPE 1 — CRÉER UN COMPTE":    "STEP 1 — CREATE AN ACCOUNT",
    "👆  Clique sur  [ Create account ]  puis vérifie ton e-mail":
        "👆  Click on  [ Create account ]  then check your email",
    "ÉTAPE 2 — CRÉER UNE CLÉ API":  "STEP 2 — CREATE AN API KEY",
    "👆  Clique sur l'icône  📋  pour copier ta clé  fal_key_xxxx…":
        "👆  Click the  📋  icon to copy your key  fal_key_xxxx…",
    "ÉTAPE 3 — AJOUTER DES CRÉDITS":
        "STEP 3 — ADD CREDITS",
    "👆  Clique sur  [ Add credits ]  →  Recommandé : $10 minimum":
        "👆  Click  [ Add credits ]  →  Recommended: $10 minimum",
    "👆  Clique sur l'icône  📋  pour copier ta clé  sk-ant-api03-xxxx…":
        "👆  Click the  📋  icon to copy your key  sk-ant-api03-xxxx…",
    "👆  Clique sur  [ Add to credit balance ]  →  Recommandé : $5 minimum":
        "👆  Click  [ Add to credit balance ]  →  Recommended: $5 minimum",
    "DANS PANDORA — PAGE PARAMÈTRES":
        "IN PANDORA — SETTINGS PAGE",
    "PANDORA  ›  Paramètres":       "PANDORA  ›  Settings",
    "👆  Colle tes clés ici et clique  [ Enregistrer ]":
        "👆  Paste your keys here and click  [ Save ]",
    "Guide de démarrage — PANDORA": "Getting Started — PANDORA",
    "← Précédent":                  "← Previous",
    "Crédits à la consommation — commence avec $10":
        "Pay-as-you-go — start with $10",
    "Crédits à la consommation — commence avec $5":
        "Pay-as-you-go — start with $5",
    "Assiste la rédaction du scénario, génère le storyboard et optimise les prompts vidéo":
        "Assists screenplay writing, generates storyboard and optimizes video prompts",
    "Découvrez toutes les fonctionnalités en vidéo — YouTube":
        "Discover all features on video — YouTube",
    "Scénario  ·  Storyboard  ·  Prompts  ·  Extraction d'éléments":
        "Screenplay  ·  Storyboard  ·  Prompts  ·  Element extraction",
    "⚙  Aller aux Paramètres →":    "⚙  Go to Settings →",

    # ── Dialog génération storyboard ─────────────────────────────────────────
    "Générer le Storyboard":        "Generate Storyboard",
    "Découpage Storyboard":         "Storyboard Breakdown",
    "Claude génère le découpage technique…":
        "Claude is generating the technical breakdown…",
    "Analyse du scénario via Claude Sonnet…":
        "Analyzing screenplay via Claude Sonnet…",
    "Aucun plan généré — le scénario est peut-être trop court.":
        "No shots generated — the screenplay may be too short.",
    " générés":                     " generated",
    " · durée totale ":             " · total duration ",

    # ── Dialog sync storyboard ────────────────────────────────────────────────
    " plan(s) analysé(s)":          " shot(s) analyzed",
    "Vérification des prompts  —  Claude Haiku":
        "Prompt verification  —  Claude Haiku",
    "inchangé":                     "unchanged",
    "après : ":                     "after: ",
    " plan(s) à mettre à jour":     " shot(s) to update",
    " prompt(s) réécrit(s) · ":     " prompt(s) rewritten · ",
    " ré-assignation(s) sur ":      " reassignment(s) on ",
    " plans modifiés · ":           " shots modified · ",
    "Aucune mise à jour nécessaire — ":
        "No update needed — ",
    " plan(s) analysé(s), tout est cohérent.":
        " shot(s) analyzed, everything is consistent.",
    " plans analysés — storyboard déjà synchronisé":
        " shots analyzed — storyboard already synchronized",
    "✓  Aucune modification n'est appliquée sans votre confirmation finale.":
        "✓  No changes are applied without your final confirmation.",
    "Détecte et réassigne les personnages, décors et accessoires dont\nle nom a légèrement changé (accents, articles, casse…).":
        "Detects and reassigns characters, locations and props whose\nname has slightly changed (accents, articles, case…).",

    # ── Dialog galerie de styles ──────────────────────────────────────────────
    "＋  Nouvelle catégorie":        "＋  New category",
    "Sélectionne un style à gauche": "Select a style on the left",
    "Ajoutez vos propres images de référence pour ce style :":
        "Add your own reference images for this style:",
    "Choisir des images de référence":
        "Choose reference images",
    "Nouvelle catégorie":           "New category",
    "Nom de la catégorie :":        "Category name:",
    "Sélectionnée : ":              "Selected: ",

    # ── Page Doublage ─────────────────────────────────────────────────────────
    "Écouter":                      "Listen",
    "Ouvrir le fichier audio dans le lecteur par défaut":
        "Open audio file in default player",
    "🔜  Prochainement — Intégration audio multi-personnages":
        "🔜  Coming soon — Multi-character audio integration",
    "🎙  Générer l'audio":          "🎙  Generate audio",
    "0 caractères":                 "0 characters",
    "Aucun échantillon chargé":     "No sample loaded",
    "FICHIERS GÉNÉRÉS":             "GENERATED FILES",
    "Charger un échantillon vocal": "Load a voice sample",
    "Texte à synthétiser":          "Text to synthesize",
    "Échantillon vocal de référence":
        "Reference voice sample",
    "✓  Audio généré avec succès":  "✓  Audio successfully generated",
    "✓  Terminé (mode mock)":       "✓  Done (mock mode)",
    "Aucune voix assignée":         "No voice assigned",
    "Retirer la voix assignée":     "Remove assigned voice",
    "Assigner une voix à ":         "Assign a voice to ",
    " caractères  ~$":              " characters  ~$",
    " caractères":                  " characters",
    "Échantillon vocal requis":     "Voice sample required",
    "Chargez un fichier audio de référence pour utiliser le clonage de voix.":
        "Load a reference audio file to use voice cloning.",
    "La langue est détectée automatiquement depuis le texte saisi — écris en français, le rendu sera en français.":
        "Language is automatically detected from the text — write in French, the result will be in French.",
    "Écris ici le dialogue à synthétiser…\nex: « Bienvenue dans PANDORA, l'outil de pré-production cinéma IA. »":
        "Write the dialogue to synthesize here…\nex: 'Welcome to PANDORA, the AI cinema pre-production tool.'",

    # ── Page Paramètres ───────────────────────────────────────────────────────
    "Le changement de thème est appliqué au prochain démarrage.":
        "The theme change will be applied on the next startup.",
    "↑  Vérifier les mises à jour": "↑  Check for updates",
    "Vérification…":                "Checking…",
    "Mise à jour disponible":       "Update available",
    "À jour":                       "Up to date",
    "Vérification impossible":      "Cannot check",
    "Impossible de contacter le serveur.\nVérifiez votre connexion internet.":
        "Unable to reach the server.\nCheck your internet connection.",
    "Thème enregistré":             "Theme saved",
    "Le nouveau thème sera appliqué au prochain démarrage de PANDORA.":
        "The new theme will be applied on the next startup of PANDORA.",
    " est la dernière version disponible ✓":
        " is the latest available version ✓",
    "Script installé":              "Script installed",
    "Entre ta clé API fal.ai d'abord !":
        "Enter your fal.ai API key first!",
    "Clé fal.ai valide !":          "fal.ai key valid!",
    "La clé API fal.ai est incorrecte.":
        "The fal.ai API key is incorrect.",

    # ── Page Stub ─────────────────────────────────────────────────────────────
    "BIENTÔT DISPONIBLE":           "COMING SOON",
    "Cette section est en cours de développement.":
        "This section is under development.",

    # ── Fenêtre principale (mises à jour) ─────────────────────────────────────
    "↑  Mises à jour":              "↑  Updates",
    "Vérifier les mises à jour de PANDORA":
        "Check for PANDORA updates",
    "Les données du storyboard et des fiches sont sauvegardées automatiquement.":
        "Storyboard data and cards are saved automatically.",
    "❤  PANDORA est gratuit. Il fonctionne grâce au soutien de la communauté.":
        "❤  PANDORA is free. It runs thanks to community support.",
    "Si ce logiciel vous est utile, un don — même modeste — nous aide à continuer à le développer.":
        "If this software is useful to you, a donation — even modest — helps us keep developing it.",
    "Télécharger  →":               "Download  →",
    "Mises à jour":                 "Updates",
    " — Mettez à jour PANDORA pour bénéficier des dernières améliorations.":
        " — Update PANDORA to benefit from the latest improvements.",
    "Français":                     "French",

    # ── Studio IA (seedance_widget) ───────────────────────────────────────────
    "Génération vidéo IA — fal.ai": "AI Video Generation — fal.ai",
    "Studio IA — Générer un clip vidéo IA":
        "AI Studio — Generate an AI video clip",

    # ── Onglet DaVinci Edit ───────────────────────────────────────────────────
    "Ajouter une image de référence":
        "Add a reference image",
    "Choisir une image de référence":
        "Choose a reference image",
    "Image de référence globale (appliquée à tous les clips)":
        "Global reference image (applied to all clips)",
    "Image de référence pour ce clip uniquement":
        "Reference image for this clip only",
    "ffmpeg non détecté — installez ffmpeg et ajoutez-le au PATH pour activer LatentSync.":
        "ffmpeg not detected — install ffmpeg and add it to PATH to activate LatentSync.",
    "Mode simulation — aucune clé fal.ai":
        "Simulation mode — no fal.ai key",
    " génération(s)  —  traitement séquentiel, 1 clip à la fois":
        " generation(s)  —  sequential processing, 1 clip at a time",
    "Clé API invalide ou expirée":  "Invalid or expired API key",
    "Délai d'attente dépassé":      "Timeout exceeded",
    "Erreur de connexion réseau":   "Network connection error",
    "Durée du clip trop courte":    "Clip duration too short",
    "File terminée — ":             "Queue complete — ",
    " génération(s) complétée(s).": " generation(s) completed.",
    " génération(s) échouée(s)":    " generation(s) failed",
    "Simulation — aucun fichier créé":
        "Simulation — no file created",
    " ✓ sauvegardé":                " ✓ saved",
    " ↷ ✓ sauvegardé":              " ↷ ✓ saved",
    " génération(s) sur ":          " generation(s) out of ",
    " génération(s) — ":            " generation(s) — ",
    " terminée(s)":                 " completed",
    " clip(s) n'ont pas pu être générés :\n\n":
        " clip(s) could not be generated:\n\n",
    " génération(s) sur ":          " generation(s) out of ",

    # ── Onglet Extension ─────────────────────────────────────────────────────
    "Clique pour choisir un clip vidéo":
        "Click to choose a video clip",
    "Aucun clip sélectionné dans DaVinci Resolve":
        "No clip selected in DaVinci Resolve",
    "Générer un début":             "Generate a start",
    "Générer une suite":            "Generate a continuation",
    "Photo d'acteur, style, décor… · max 3":
        "Actor photo, style, location… · max 3",
    "Si vide → même prompt original · Si rempli → remplace le prompt":
        "If empty → same original prompt · If filled → replaces the prompt",
    "Décris ce que doit contenir l'extension… ex: la caméra continue son travelling, le personnage sort du cadre":
        "Describe what the extension should contain… ex: the camera continues its tracking shot, the character exits the frame",
    "Après génération terminée":    "After generation complete",
    "Ajouter des images de référence":
        "Add reference images",
    "◀  Générer un début":          "◀  Generate a start",
    "▶  Générer une suite":         "▶  Generate a continuation",
    "Extension prête !":            "Extension ready!",
    "début généré":                 "start generated",
    "suite générée":                "continuation generated",
    "✓ Modification terminée":      "✓ Edit complete",
    "Clip sélectionné":             "Selected clip",
    "Images de référence (optionnel)":
        "Reference images (optional)",
    "Impossible de récupérer le chemin du clip.\nVérifie que le média est bien présent sur le disque.":
        "Cannot retrieve clip path.\nCheck that the media is present on the disk.",
    "Sélectionne un clip vidéo à étendre !":
        "Select a video clip to extend!",
    "Laisse vide pour réutiliser le prompt original…\nOu décris les changements voulus pour cette nouvelle prise":
        "Leave empty to reuse the original prompt…\nOr describe the desired changes for this new take",
    "Clip modifié (":               "Clip edited (",
    ") !\n\nDurée ajoutée : ":      ") !\n\nDuration added: ",
    "\n\nCrédits : ":               "\n\nCredits: ",

    # ── Onglet Historique ─────────────────────────────────────────────────────
    "Générations récentes":         "Recent generations",
    "Aucune génération pour l'instant.\nLance une génération depuis T2V ou I2V !":
        "No generations yet.\nStart a generation from T2V or I2V!",

    # ── Onglet I2V ────────────────────────────────────────────────────────────
    "Décris le mouvement... ex: la caméra recule lentement, le personnage tourne la tête":
        "Describe the movement... ex: camera slowly pulls back, character turns their head",
    "✓ Terminé":                    "✓ Done",
    "Écris un prompt de mouvement !":
        "Write a movement prompt!",

    # ── Onglet Référence ─────────────────────────────────────────────────────
    "Image de référence":           "Reference image",
    "Vidéo de référence":           "Reference video",
    "Audio de référence":           "Reference audio",
    "Clique sur un slot pour uploader · Insère @image @video @audio dans le prompt":
        "Click a slot to upload · Insert @image @video @audio in the prompt",
    "Vidéo prête !":                "Video ready!",
    "✓ Génération terminée":        "✓ Generation complete",
    "Références médias":            "Media references",
    "Rien à générer":               "Nothing to generate",
    "Ajoute au moins une référence média ou un prompt !":
        "Add at least one media reference or a prompt!",
    "Clip généré depuis références !\n\nDurée : ":
        "Clip generated from references!\n\nDuration: ",
    "\nCrédits : ":                 "\nCredits: ",

    # ── Onglet Paramètres Studio ──────────────────────────────────────────────
    "Clé API Anthropic (bouton Améliorer)":
        "Anthropic API key (Improve button)",
    "Paramètres par défaut":        "Default settings",
    "Durée (s)":                    "Duration (s)",
    "Par défaut : ":                "Default: ",
    "Clé fal.ai valide !\nMode réel activé.":
        "fal.ai key valid!\nReal mode activated.",

    # ── Onglet T2V ────────────────────────────────────────────────────────────
    "Exclure les images de personnages des références visuelles":
        "Exclude character images from visual references",
    "Exclure les images d'accessoires des références visuelles":
        "Exclude prop images from visual references",
    "Exclure les images de véhicules des références visuelles":
        "Exclude vehicle images from visual references",
    "Exclure l'image de décor des références visuelles":
        "Exclude location image from visual references",
    "Sélectionne un personnage pour voir ses accessoires.":
        "Select a character to see their props.",
    "Entité absente du plan":       "Entity absent from shot",
    "Continuer depuis la dernière frame du plan précédent (I2V)":
        "Continue from the last frame of the previous shot (I2V)",
    "Verrouiller la graine visuelle — même apparence pour tous les plans":
        "Lock visual seed — same appearance for all shots",
    "Aléatoire — résultats variables à chaque génération":
        "Random — variable results with each generation",
    "Verrouillée — même ADN visuel pour tous les plans":
        "Locked — same visual DNA for all shots",
    "Verrouiller l'ADN visuel — même empreinte visuelle pour tous les plans":
        "Lock visual DNA — same visual fingerprint for all shots",
    "🔒  ADN visuel verrouillé — cohérence visuelle activée":
        "🔒  Visual DNA locked — visual consistency enabled",
    "⊘  Ne pas envoyer les images de référence":
        "⊘  Do not send reference images",
    "▦  Verrouiller les clips au masque de façade (noir hors silhouette)":
        "▦  Lock clips to the facade mask (black outside the silhouette)",
    "Après chaque génération Mapping : tout ce qui dépasse la silhouette du bâtiment est rendu noir pur dans le clip final (garanti à 100 %). Nécessite une façade isolée sur fond noir (BiRefNet).":
        "After every Mapping generation: anything beyond the building silhouette is rendered pure black in the final clip (100% guaranteed). Requires a facade isolated on a black background (BiRefNet).",
    "▦ Verrouillé au masque de façade": "▦ Locked to the facade mask",
    "Durée :":                      "Duration:",
    "0 plans sélectionnés":         "0 shots selected",
    " plans sélectionnés":          " shots selected",
    "Vous allez générer plusieurs plans en file d'attente.":
        "You are about to generate multiple shots in a queue.",
    "Décris ta scène... ex: plan cinématique d'une forêt brumeuse au lever du soleil":
        "Describe your scene... ex: cinematic shot of a misty forest at sunrise",
    "Coché → piste musicale présente · Décoché → « no background music » injecté":
        "Checked → music track present · Unchecked → 'no background music' injected",
    "Coché → sous-titres incrustés · Décoché → « no subtitles » injecté":
        "Checked → subtitles embedded · Unchecked → 'no subtitles' injected",
    "🔒 Paramètres propres à chaque plan":
        "🔒 Settings per shot",
    "🔒 Durée définie par le storyboard":
        "🔒 Duration set by storyboard",
    "🔒 Paramètres propres à chaque plan":
        "🔒 Settings per shot",
    "Vérification du solde…":       "Checking balance…",
    "Génération en série":          "Series generation",
    "▶  Générer quand même":        "▶  Generate anyway",
    "Aucun personnage — crée-en un dans Castings.":
        "No characters — create one in Cast.",
    "Aucun véhicule — crée-en un dans Véhicules.":
        "No vehicles — create one in Vehicles.",
    "Aucun décor — crée-en un dans Décors.":
        "No locations — create one in Locations.",
    "Aucun plan — crée-en un dans le Storyboard.":
        "No shots — create one in Storyboard.",
    "Génération en série terminée !\n\n":
        "Series generation complete!\n\n",
    " clips générés avec succès.":  " clips generated successfully.",
    "Clip généré avec succès !\n\nModèle : ":
        "Clip generated successfully!\n\nModel: ",
    "Répétition ":                  "Repetition ",
    " généré":                      " generated",
    " avec succès !\n\nModèle : ":  " successfully!\n\nModel: ",
    "\n\n◈ Sauvegardé + importé dans le Media Pool ✓\n":
        "\n\n◈ Saved + imported into Media Pool ✓\n",
    "\n\n◈ Vidéo sauvegardée :\n":  "\n\n◈ Video saved:\n",
    "\n\n◈ Téléchargement échoué : ":
        "\n\n◈ Download failed: ",
    "\n\n◈ Import DaVinci : simulé (mode mock)":
        "\n\n◈ DaVinci import: simulated (mock mode)",
    "Erreur — génération en série interrompue":
        "Error — series generation interrupted",
    "Images de référence partiellement transmises (":
        "Reference images partially transmitted (",
    " clips générés":               " clips generated",
    "Décor : ":                     "Location: ",
    "Véhicules : ":                 "Vehicles: ",
    "Caméra : ":                    "Camera: ",
    "Créatifs : ":                  "Creative: ",
    "━━━ IMAGES ENVOYÉES ━━━":      "━━━ IMAGES SENT ━━━",
    "━━━ PARAMÈTRES ━━━":           "━━━ PARAMETERS ━━━",
    "◈ MODE RÉFÉRENCE ACTIF — ":    "◈ REFERENCE MODE ACTIVE — ",
    "Certaines images de référence n'ont pas pu être uploadées — la génération a été lancée avec les images disponibles.":
        "Some reference images could not be uploaded — generation was started with available images.",
    "Vous n'êtes pas connecté à DaVinci Resolve.\n\nVoulez-vous tenter la connexion avant de générer ?":
        "You are not connected to DaVinci Resolve.\n\nWould you like to try connecting before generating?",

    # ── Onglet Moteurs vidéo ──────────────────────────────────────────────────
    "Image de départ (requis)":     "Starting image (required)",
    "Décrivez le mouvement et l'action de la scène… (FR accepté, traduit auto)":
        "Describe the movement and action of the scene… (FR accepted, auto-translated)",
    "Prompt négatif (optionnel) :": "Negative prompt (optional):",
    "Générer l'audio (recommandé)": "Generate audio (recommended)",
    "Image de départ requise pour Kling I2V.":
        "Starting image required for Kling I2V.",
    "Décrivez la scène complète… (FR accepté, traduit automatiquement en anglais)":
        "Describe the full scene… (FR accepted, auto-translated to English)",
    "Résolution :":                 "Resolution:",
    "1:1 — Carré":                  "1:1 — Square",
    "Coût":                         "Cost",
    "Durée : ":                     "Duration: ",
    "Durée : 5 s  (~$0.56)":        "Duration: 5 s  (~$0.56)",
    "Durée : 5 s  (~$0.84)":        "Duration: 5 s  (~$0.84)",
    "Durée : 5 s (fixe)":           "Duration: 5 s (fixed)",
    "Durée : 5 s  (~$1.40)":        "Duration: 5 s  (~$1.40)",
    "Durée : 5 s  (~$2.10)":        "Duration: 5 s  (~$2.10)",
    "Durée : 5 s  (~$0.58)":        "Duration: 5 s  (~$0.58)",
    "Durée : 5 s  (~$0.70)":        "Duration: 5 s  (~$0.70)",
    "Durée : 5 s":                  "Duration: 5 s",
    "Sans audio natif · Idéal pour itérations rapides":
        "No native audio · Ideal for quick iterations",
    "Décrivez librement la scène à générer…\n(FR accepté, traduit automatiquement en anglais)":
        "Freely describe the scene to generate…\n(FR accepted, auto-translated to English)",
    "Décrivez la scène… (FR accepté, traduit automatiquement en anglais)":
        "Describe the scene… (FR accepted, auto-translated to English)",
    "Image de départ requise pour Happy Horse I2V.":
        "Starting image required for Happy Horse I2V.",
    "Image de départ requise pour Kling O3 I2V.":
        "Starting image required for Kling O3 I2V.",
    "Améliorer le prompt avec Claude":
        "Improve prompt with Claude",
    "Aucune vidéo générée.":        "No video generated.",
    "▸ Génération vidéo sans storyboard — idéal pour expérimenter rapidement avec différents modèles.":
        "▸ Video generation without storyboard — ideal for quickly experimenting with different models.",
    "▸ Les prompts en français sont traduits automatiquement en anglais avant envoi.":
        "▸ French prompts are automatically translated to English before sending.",
    "Génération Directe — Multi-moteurs IA":
        "Direct Generation — Multi-engine AI",
    "Paramètre manquant":           "Missing parameter",
    "✓  Terminé (mode mock — aucune clé fal.ai)":
        "✓  Done (mock mode — no fal.ai key)",

    # ── Vidéothèque ───────────────────────────────────────────────────────────
    "Date (récent → ancien)":       "Date (recent → old)",
    "Date (ancien → récent)":       "Date (old → recent)",
    "Aucune vidéo générée dans ce projet.\nLancez une génération depuis « Générer depuis Storyboard » ou « Modifier des clips ».":
        "No videos generated for this project.\nStart a generation from 'Generate from Storyboard' or 'Edit clips'.",
    "aperçu indisponible":          "preview unavailable",
    " vidéo":                       " video",
    "Aucun log d'erreur trouvé.":   "No error log found.",
    "▸ Retrouvez ici toutes les vidéos générées pour ce projet.":
        "▸ Find all videos generated for this project here.",
    "▸ Cliquez sur ▶ Lire pour ouvrir dans votre lecteur vidéo par défaut.":
        "▸ Click ▶ Play to open in your default video player.",

    # ── Widgets ───────────────────────────────────────────────────────────────
    "Crédits insuffisants":         "Insufficient credits",
    "Crédits fal.ai insuffisants":  "Insufficient fal.ai credits",
    "GÉNÉRATION EN COURS":          "GENERATION IN PROGRESS",
    "✓  VIDÉO GÉNÉRÉE":             "✓  VIDEO GENERATED",

    # ── Panneau assistant ─────────────────────────────────────────────────────
    "Logiciel de pré-production cinéma pour DaVinci Resolve.":
        "Cinema pre-production software for DaVinci Resolve.",
    "Gestion des projets de pré-production cinéma.":
        "Cinema pre-production project management.",
    "Éditeur de scénario avec Claude IA — mise en page, co-écriture, extraction d'éléments.":
        "Screenplay editor with Claude AI — layout, co-writing, element extraction.",
    "Découpage plan par plan avec génération IA intégrée.":
        "Shot-by-shot breakdown with integrated AI generation.",
    "Props et objets — références visuelles pour la production.":
        "Props and objects — visual references for production.",
    "Habillage, Maquillage, Coiffure — cohérence visuelle.":
        "Costume, Makeup, Hair — visual consistency.",
    "Véhicules du film — références visuelles pour la production.":
        "Film vehicles — visual references for production.",
    "Préférences caméra, optiques et chaîne son du projet.":
        "Camera, lens and sound chain preferences for the project.",
    "Synthèse vocale et clonage vocal pour la post-production.":
        "Voice synthesis and voice cloning for post-production.",
    "Clés API et préférences globales de PANDORA.":
        "API keys and global PANDORA preferences.",
    "Naviguez entre les sections depuis la barre latérale gauche.":
        "Navigate between sections from the left sidebar.",
    "Les données sont sauvegardées automatiquement.":
        "Data is saved automatically.",
    "Chaque projet a son propre dossier de données isolé.":
        "Each project has its own isolated data folder.",
    "Injectez des références visuelles — Claude les analyse et enrichit votre scénario.":
        "Inject visual references — Claude analyzes them and enriches your screenplay.",
    "'Proposer un arrangement' ouvre le Studio de co-écriture interactif avec Claude.":
        "'Propose an arrangement' opens the interactive co-writing Studio with Claude.",
    "'Tout Générer' crée personnages, décors, accessoires, HMC, véhicules en une passe.":
        "'Generate All' creates characters, locations, props, HMC, vehicles in one pass.",
    "Double-cliquez sur un plan pour éditer : Caméra, Éléments, Mise en scène, Prompt.":
        "Double-click a shot to edit: Camera, Elements, Scene, Prompt.",
    "'✦ Générer les Moods' génère un aperçu visuel pour chaque plan en batch.":
        "'✦ Generate Moods' generates a visual preview for each shot in batch.",
    "Glissez-déposez les plans pour réorganiser le découpage.":
        "Drag and drop shots to reorder the breakdown.",
    "Générez un portrait via Nano Banana depuis la fiche personnage.":
        "Generate a portrait via Nano Banana from the character card.",
    "Assignez un personnage à un plan depuis le storyboard pour l'inclure dans la génération.":
        "Assign a character to a shot from the storyboard to include them in generation.",
    "Générez une image de référence du décor via Nano Banana.":
        "Generate a location reference image via Nano Banana.",
    "Chaque décor peut avoir son propre style visuel.":
        "Each location can have its own visual style.",
    "'Sheet 4 vues' génère quatre angles différents du même lieu.":
        "'4-view sheet' generates four different angles of the same location.",
    "Associez un style visuel spécifique à chaque accessoire.":
        "Assign a specific visual style to each prop.",
    "'Générer une variation' crée une alternative de l'image existante.":
        "'Generate a variation' creates an alternative to the existing image.",
    "Décrivez précisément matière, couleur et état (neuf, abîmé, vintage).":
        "Describe precisely the material, color and condition (new, worn, vintage).",
    "Associez des éléments HMC à des personnages ou séquences.":
        "Associate HMC items with characters or sequences.",
    "Générez une image de référence pour chaque élément.":
        "Generate a reference image for each item.",
    "Renseignez marque, modèle, année et couleur pour chaque véhicule.":
        "Fill in brand, model, year and color for each vehicle.",
    "Générez une image de référence via Nano Banana.":
        "Generate a reference image via Nano Banana.",
    "Précisez l'état (neuf, accidenté, modifié) dans la description.":
        "Specify the condition (new, damaged, modified) in the description.",
    "Définissez la caméra principale, les optiques et le format d'image.":
        "Define the main camera, lenses and image format.",
    "Ces paramètres pré-remplissent les champs techniques du storyboard.":
        "These settings pre-fill the technical fields in the storyboard.",
    "Renseignez le micro et la chaîne son pour préparer le tournage.":
        "Fill in the microphone and sound chain to prepare for the shoot.",
    "Le ratio d'image (1.85:1, 2.39:1) s'applique à tous les plans.":
        "The aspect ratio (1.85:1, 2.39:1) applies to all shots.",
    "ElevenLabs génère des voix naturalistes multilingues depuis votre texte.":
        "ElevenLabs generates naturalistic multilingual voices from your text.",
    "F5-TTS clone n'importe quelle voix depuis un court échantillon audio.":
        "F5-TTS clones any voice from a short audio sample.",
    "Le français est pris en charge par ElevenLabs ; F5-TTS fonctionne mieux en anglais.":
        "French is supported by ElevenLabs; F5-TTS works best in English.",
    "Les fichiers audio générés s'importent directement dans DaVinci Resolve.":
        "Generated audio files import directly into DaVinci Resolve.",
    "T2V : décrivez la scène en français, la traduction est automatique.":
        "T2V: describe the scene in French, translation is automatic.",
    "Génération directe : 13 moteurs (Kling v3 Pro, Veo 3.1, Sora 2…).":
        "Direct generation: 13 engines (Kling v3 Pro, Veo 3.1, Sora 2…).",
    "La vidéothèque centralise tous les clips avec prévisualisation.":
        "The video library centralizes all clips with preview.",
    "Clé Anthropic : assistant IA, scénario, traduction des prompts.":
        "Anthropic key: AI assistant, screenplay, prompt translation.",
    "Clé Nano Banana : portraits et images d'éléments.":
        "Nano Banana key: portraits and element images.",
    "Le dossier de sortie définit où les vidéos sont enregistrées.":
        "The output folder defines where videos are saved.",
    "Activer l'assistant IA — utilise des crédits Anthropic\n(désactivé par défaut)":
        "Enable AI assistant — uses Anthropic credits\n(disabled by default)",
    "L'assistant IA est désactivé.\nActivez-le via « IA ○ » pour poser des questions.\n(Utilise des crédits Anthropic)":
        "The AI assistant is disabled.\nEnable it via 'AI ○' to ask questions.\n(Uses Anthropic credits)",

    # ── Chooser (module Live / Cinéma) ────────────────────────────────────────
    "Cinéma":                       "Cinema",
    "Pré-production IA\nScénario · Storyboard · DaVinci":
        "AI Pre-production\nScreenplay · Storyboard · DaVinci",

    # ── API mock — messages de progression ───────────────────────────────────
    "Initialisation de la requête...":  "Initializing request...",
    "Génération des frames clés...":    "Generating key frames...",
    "Rendu intermédiaire...":           "Intermediate rendering...",
    "Encodage vidéo...":                "Encoding video...",

    # ── API aperçu / Mood ─────────────────────────────────────────────────────
    "Travelling arrière":           "Track out",
    "Travelling latéral":           "Lateral tracking",
    "Zoom arrière":                 "Zoom out",
    "Caméra portée":                "Handheld camera",
    "Génération du Mood via Flux…": "Generating Mood via Flux…",
    "Téléchargement de l'image…":   "Downloading image…",
    "Simulation (pas de clé fal.ai)…":
        "Simulation (no fal.ai key)…",

    # ── API enhance ───────────────────────────────────────────────────────────
    "Clé API Anthropic manquante.\nConfigure-la dans l'onglet Config → Clé API Anthropic.":
        "Anthropic API key missing.\nConfigure it in the Config tab → Anthropic API key.",

    # ── API lipsync ───────────────────────────────────────────────────────────
    "Téléchargement vidéo lip-synced…":
        "Downloading lip-synced video…",
    "Terminé.":                     "Done.",
    "Clé fal.ai non configurée (page Paramètres).":
        "fal.ai key not configured (Settings page).",

    # ── Page Live ─────────────────────────────────────────────────────────────
    "BIBLIOTHÈQUE PANDORA":         "PANDORA LIBRARY",
    "Déconnecté":                   "Disconnected",
    "Déconnecter":                  "Disconnect",
    "Connecté : ":                  "Connected: ",
    "Paramètres Live":              "Live Settings",
    "Aucune couche détectée dans Resolume.":
        "No layer detected in Resolume.",
    "Clip sélectionné : ":          "Selected clip: ",
    "Sélectionnez d'abord un clip dans la bibliothèque gauche.":
        "Select a clip in the left library first.",
    "✗  Connexion à Resolume requise pour déclencher un clip.":
        "✗  Connection to Resolume required to trigger a clip.",
    "CLÉ API FAL.AI":               "FAL.AI API KEY",
    "Clé fal.ai :":                 "fal.ai key:",
    "✓  Paramètres enregistrés.":   "✓  Settings saved.",

    # ── Chips créatifs — labels manquants ─────────────────────────────────────
    "État":                         "Condition",
    "Créatif":                      "Creative",
    "éléments":                     "elements",
    "véhicule":                     "vehicle",
    "décor":                        "location",

    # ── Dialog arrangement — placeholders visibles ────────────────────────────
    "Entrez votre instruction ici…\nEx : « Ne change pas le flashback de la scène 4 »":
        "Enter your instruction here…\nEx: 'Don't change the flashback in scene 4'",
    "💬  Dites à Claude ce que vous voulez changer.\nEx : « Garde la scène 3 intacte », « Rends les dialogues plus percutants »,\n« Développe le personnage secondaire du plan 5 »":
        "💬  Tell Claude what you want to change.\nEx: 'Keep scene 3 intact', 'Make the dialogues punchier',\n'Develop the secondary character in shot 5'",

    # ── Dialog génération storyboard — texte visible ──────────────────────────
    "⏳  La génération peut prendre du temps selon la longueur du scénario.\nSi vous utilisez un VPN, désactivez-le — il peut bloquer les connexions API.":
        "⏳  Generation may take time depending on the screenplay length.\nIf you use a VPN, disable it — it may block API connections.",

    # ── Dialog sync storyboard — descriptions visibles ────────────────────────
    "La synchronisation va comparer votre storyboard avec le casting,\nles décors et les accessoires actuels. Elle se déroule en deux passes :":
        "Synchronization will compare your storyboard with the current cast,\nlocations and props. It runs in two passes:",
    "Analyse si les prompts reflètent encore les descriptions actuelles\ndes éléments assignés. Réécrit uniquement ce qui est incohérent.":
        "Checks if prompts still reflect the current descriptions\nof assigned elements. Rewrites only what is inconsistent.",

    # ── Onglet DaVinci Edit — strings visibles restants ───────────────────────
    "📁  Importer des fichiers vidéo":
        "📁  Import video files",
    "Image de référence (ce clip)": "Reference image (this clip)",
    "⚠  Ce moteur ne supporte pas les images de référence nativement. Vos personnages, décors et accessoires seront convertis en mots-clés descriptifs dans le prompt.":
        "⚠  This engine does not natively support reference images. Your characters, locations and props will be converted to descriptive keywords in the prompt.",
    "▸ Sélectionner des clips spécifiques : clic droit sur chaque clip → Flag → n'importe quelle couleur.":
        "▸ Select specific clips: right-click each clip → Flag → any color.",
    "  pandora_send n'envoie que les clips flaggés (toutes couleurs). Sans flag = toute la timeline.":
        "  pandora_send only sends flagged clips (all colors). No flag = entire timeline.",
    "  • Résolution : 1080p maximum":
        "  • Resolution: 1080p maximum",
    "  → Depuis DaVinci : Fichier → Exporter → sélectionner H.264 Master à 1080p":
        "  → From DaVinci: File → Export → select H.264 Master at 1080p",
    "Décris la modification souhaitée…\nex: same scene but background replaced by a futuristic city at night, cinematic lighting":
        "Describe the desired edit…\nex: same scene but background replaced by a futuristic city at night, cinematic lighting",
    "Prompt spécifique à ce clip…\nex: same scene but background replaced by a futuristic city at night":
        "Prompt for this clip…\nex: same scene but background replaced by a futuristic city at night",

    # ── Onglet I2V ────────────────────────────────────────────────────────────
    "Image animée avec succès !":   "Image animated successfully!",
    "\n\n◈ Vidéo sauvegardée localement :\n":
        "\n\n◈ Video saved locally:\n",

    # ── Onglet Référence — placeholder visible ────────────────────────────────
    "Décris ta scène... Utilise @image, @video, @audio pour référencer tes uploads.\nEx: génère une scène où @image marche dans la forêt":
        "Describe your scene... Use @image, @video, @audio to reference your uploads.\nEx: generate a scene where @image walks in the forest",

    # ── Onglet T2V — strings manquants ────────────────────────────────────────
    "Aucun accessoire assigné aux personnages sélectionnés.":
        "No props assigned to the selected characters.",
    "Écris un prompt avant de générer !":
        "Write a prompt before generating!",
    "Vous avez sélectionné ":       "You have selected ",
    " plans.\n\nLa génération sera lancée en file d'attente — un clip après l'autre.\n\n⚠  Chaque plan consomme des crédits fal.ai":
        " shots.\n\nGeneration will be queued — one clip at a time.\n\n⚠  Each shot consumes fal.ai credits",
    "(prompt vide — aucun style ni caméra configurés)":
        "(empty prompt — no style or camera configured)",
    "(prompt vide — éléments qui seront ajoutés à votre texte :)":
        "(empty prompt — elements that will be added to your text:)",
    "\nDurée : ":                    "\nDuration: ",
    "\nCrédits : ":                  "\nCredits: ",
    "] → analysé par Claude Vision": "] → analyzed by Claude Vision",
    "Détail : ":                     "Detail: ",
    "+ Caméra : ":                   "+ Camera: ",
    "✗ → no background music injecté":
        "✗ → no background music injected",
    "✗ → no subtitles injecté":     "✗ → no subtitles injected",
    " clip(s) généré(s) avant l'erreur. ":
        " clip(s) generated before the error. ",
    " plan(s) annulé(s).":          " shot(s) cancelled.",

    # ── Page Paramètres — strings restants ───────────────────────────────────
    "L'application est optimisée pour une apparence sombre.  Si vous constatez des problèmes d'affichage en mode clair, contactez 22eme.arkane@gmail.com":
        "The application is optimized for a dark appearance.  If you notice display issues in light mode, contact 22eme.arkane@gmail.com",

    # ── Panneau DaVinci — texte visible ───────────────────────────────────────
    "Fichier copié dans :\n":       "File copied to:\n",
    "Le bridge TCP est actif mais le scripting DaVinci ne répond pas.\n\nCette fonctionnalité nécessite DaVinci Resolve Studio.\n\nLa version gratuite de DaVinci Resolve ne supporte pas le scripting Python.":
        "The TCP bridge is active but DaVinci scripting is not responding.\n\nThis feature requires DaVinci Resolve Studio.\n\nThe free version of DaVinci Resolve does not support Python scripting.",

    # ── Strings doublage — restants ───────────────────────────────────────────
    "Formats acceptés : MP3 · WAV · M4A · AAC · OGG  —  durée recommandée : 5–30 s  ·  Langue détectée automatiquement depuis le texte":
        "Accepted formats: MP3 · WAV · M4A · AAC · OGG  —  recommended duration: 5–30 s  ·  Language detected automatically from text",

    # ── Rendu & Audio (tab_t2v.py) ───────────────────────────────────────────
    "RENDU & AUDIO":                    "RENDER & AUDIO",

    # ── Ajouts i18n (audit 2026-06) ─────────────────────────────────────────
    "Effacer la conversation": "Clear conversation",
    "Posez une question sur cette page…": "Ask a question about this page…",
    "Ouvrir / fermer l'assistant pédagogique": "Open / close the learning assistant",
    "Choisissez votre espace de travail": "Choose your workspace",
    "Installer le bridge PANDORA dans DaVinci →": "Install the PANDORA bridge in DaVinci →",
    "2.  Dans DaVinci : Espace de travail → Scripts → seedance_bridge": "2.  In DaVinci: Workspace → Scripts → seedance_bridge",
    "3.  Revenez ici et cliquez sur « Connecter » →": "3.  Come back here and click « Connect » →",
    "DaVinci — Studio requis pour le scripting": "DaVinci — Studio required for scripting",
    "Le bridge TCP est actif mais le scripting DaVinci ne répond pas.\n\nCette fonctionnalité nécessite DaVinci Resolve Studio.\n\nLa génération de clips fonctionne normalement.\nL'import automatique dans le Media Pool et la lecture\ndes clips DaVinci seront actifs avec la version Studio.": "The TCP bridge is active but DaVinci scripting is not responding.\n\nThis feature requires DaVinci Resolve Studio.\n\nClip generation works normally.\nAutomatic import into the Media Pool and playback\nof DaVinci clips will be available with the Studio version.",
    "▶  Qu'est-ce qu'un Mood ?": "▶  What is a Mood?",
    "Teste le prompt et l'ambiance du plan avant de lancer Seedance 2.0. L'image est générée à partir du prompt Seedance, de la valeur de plan, la focale, l'axe caméra, le mouvement, le lieu, l'heure et le style visuel du film. Ce n'est pas une pré-visualisation fidèle — c'est un outil pour valider l'atmosphère, l'éclairage et le prompt. Une fois validée, l'image active pourra être injectée comme référence dans Seedance 2.0.": "Test the shot's prompt and mood before launching Seedance 2.0. The image is generated from the Seedance prompt, the shot size, focal length, camera axis, movement, location, time and the film's visual style. It is not an exact preview — it's a tool to validate the atmosphere, lighting and prompt. Once validated, the active image can be injected as a reference in Seedance 2.0.",
    "Le scénario remanié apparaîtra ici après votre première instruction à Claude…\n\nUtilisez la zone de dialogue à droite pour co-écrire avec Claude.": "The reworked screenplay will appear here after your first instruction to Claude…\n\nUse the chat area on the right to co-write with Claude.",
    "💬  Dites à Claude ce que vous voulez changer.\nEx : « Garde la scène 3 intacte », « Rends les dialogues plus percutants »,\n« Développe l'acte 2 », « Coupe toutes les voix off »…": "💬  Tell Claude what you want to change.\nE.g.: « Keep scene 3 intact », « Make the dialogue punchier »,\n« Develop act 2 », « Cut all the voice-overs »…",
    "📎  Joindre des images pour enrichir les descriptions — max 4": "📎  Attach images to enrich the descriptions — max 4",
    "Efface le champ de saisie": "Clear the input field",
    "Ctrl+↵ pour envoyer": "Ctrl+↵ to send",
    "Vous devez accepter la charte pour utiliser PANDORA.": "You must accept the agreement to use PANDORA.",
    "✕  Annuler": "✕  Cancel",
    "Génère les vidéos (Seedance, Kling, Veo…) et les images de référence (portraits, décors…)": "Generates videos (Seedance, Kling, Veo…) and reference images (portraits, locations…)",
    "▶  Voir le tutoriel →": "▶  Watch the tutorial →",
    "⏳  La génération peut prendre du temps selon la longueur du scénario.\nSi vous utilisez un VPN, désactivez-le — il peut bloquer la connexion avec Claude.": "⏳  Generation may take a while depending on the screenplay length.\nIf you use a VPN, disable it — it may block the connection to Claude.",
    "Importer dans le Storyboard": "Import into the Storyboard",
    "La synchronisation va comparer votre storyboard avec le casting,\nles décors et les accessoires actuels. Elle se déroule en deux phases :": "Synchronization will compare your storyboard with the current cast,\nlocations and props. It runs in two phases:",
    "Choisir un template de style": "Choose a style template",
    "L'image sera envoyée à Seedance comme 4ᵉ référence visuelle (style)": "The image will be sent to Seedance as a 4th visual reference (style)",
    "＋  Ajouter un template…": "＋  Add a template…",
    "✕  Retirer le template": "✕  Remove template",
    "Ouvrir le dossier contenant le fichier audio": "Open the folder containing the audio file",
    "Les moteurs de génération vidéo (Seedance, Kling, Veo…) ne permettent pas encore d'incorporer un audio personnalisé par personnage directement dans la génération. L'injection multi-personnages avec timecodes — \"personnage A parle de T1 à T2, personnage B de T3 à T4\" — est prévue dans une prochaine version de PANDORA.\n\nEn attendant : les outils de synthèse vocale ci-dessous restent pleinement fonctionnels pour générer et prévisualiser les voix de vos personnages. L'audio produit peut ensuite être appliqué manuellement via LatentSync (onglet Modifier depuis DaVinci Resolve) ou intégré dans DaVinci Resolve.": "Video generation engines (Seedance, Kling, Veo…) do not yet allow embedding custom per-character audio directly into the generation. Multi-character injection with timecodes — \"character A speaks from T1 to T2, character B from T3 to T4\" — is planned for an upcoming version of PANDORA.\n\nIn the meantime: the voice synthesis tools below remain fully functional to generate and preview your characters' voices. The audio produced can then be applied manually via LatentSync (Edit from DaVinci Resolve tab) or integrated in DaVinci Resolve.",
    "FR/EN = voix disponibles en français · EN = anglais uniquement · résultats variables selon la voix": "FR/EN = voices available in French · EN = English only · results vary by voice",
    "Formats acceptés : MP3 · WAV · M4A · AAC · OGG  —  durée recommandée : 5–30 s  ·  Langue détectée automatiquement depuis le texte (FR, EN, ES, ZH…)": "Accepted formats: MP3 · WAV · M4A · AAC · OGG  —  recommended length: 5–30 s  ·  Language detected automatically from the text (FR, EN, ES, ZH…)",
    "Aucun personnage dans ce projet.": "No character in this project.",
    "Déconnecté · Clic gauche sur un slot = charger le clip sélectionné · Clic droit = déclencher (nécessite connexion)": "Disconnected · Left-click a slot = load the selected clip · Right-click = trigger (requires connection)",
    "Aucun clip trouvé\ndans ~/Videos/PANDORA/": "No clip found\nin ~/Videos/PANDORA/",
    "Configuration de la connexion Resolume et des clés API.": "Resolume connection and API keys configuration.",
    "Resolume Arena ou Avenue doit être lancé avec le serveur web activé :\nPréférences → Webserver → « Enable Webserver & REST API »  (port : 8080)": "Resolume Arena or Avenue must be running with the web server enabled:\nPreferences → Webserver → \"Enable Webserver & REST API\"  (port: 8080)",
    "Port Webserver :": "Webserver port:",
    "Toute la bibliothèque": "Whole library",
    "clip(s) reçus de la Vidéothèque": "clip(s) received from the Video library",
    "Régler le BPM de la composition": "Set the composition BPM",
    "Analyse d'abord le set dans le Conducteur (« Analyser le set »).":
        "Analyze the set first in the Conductor (« Analyze the set »).",
    "Envoyer vers Resolume": "Send to Resolume",
    "Mode show (enchaînement auto, calé mesure)": "Show mode (auto-chain, bar-snapped)",
    "Actualiser la bibliothèque": "Refresh library",
    "Re-scanne les clips du projet.": "Re-scans the project's clips.",
    "Affichage :": "View:",
    "Détails": "Details",
    "Grandes vignettes": "Large thumbnails",
    "Vider la couche": "Clear layer",
    "Vider TOUS les slots de la couche": "Clear ALL slots of layer",
    "Vide TOUS les slots de la couche choisie\n(spin « Couche » de l'envoi en file).":
        "Clears ALL slots of the chosen layer\n(the queue's « Layer » spin).",
    "Une couche par acte (SQ1 → couche 1…)": "One layer per act (SQ1 → layer 1…)",
    "Répartit les clips par acte : tous les SQ1 sur la 1re couche,\nles SQ2 sur la suivante, etc. (colonnes redémarrent à 1 par couche).\nDécoché : tout sur la couche choisie, colonnes consécutives.":
        "Distributes clips by act: all SQ1 on the 1st layer,\nSQ2 on the next, etc. (columns restart at 1 per layer).\nUnchecked: everything on the chosen layer, consecutive columns.",
    "Envoi : le clip sélectionné": "Sending: the selected clip",
    "Envoi :": "Sending:",
    "clips sélectionnés": "clips selected",
    "glisser un clip sur un slot · clic droit : déclencher · Maj+clic : vider":
        "drag a clip onto a slot · right click: trigger · Shift+click: clear",
    "Annuler la file": "Cancel queue",
    "Lancer la file d'attente": "Launch queue",
    "Ouvre le dossier de destination des upscales.": "Opens the upscales destination folder.",
    "Ouvre le dossier de destination du sound design.": "Opens the sound design destination folder.",
    "Ouvre le dossier de destination des clips.": "Opens the clips destination folder.",
    "Langues":                                   "Languages",
    "📦  Les 6 vues de la pièce  (sol · plafond · gauche · droite · avant · arrière)":
        "📦  The 6 views of the room  (floor · ceiling · left · right · front · back)",
    "Génération des 6 vues de la pièce…":        "Generating the 6 room views…",
    "Anglais  (recommandé)":                     "English  (recommended)",
    "Langue des dialogues — traduite automatiquement à l'envoi vers Seedance.\nAnglais recommandé (meilleur lipsync). Le prompt à l'écran n'est pas modifié.":
        "Dialogue language — translated automatically when sent to Seedance.\nEnglish recommended (best lipsync). The on-screen prompt is left unchanged.",
    "▸  Choisir les références": "▸  Choose references",
    "▾  Choisir les références": "▾  Choose references",
    "▸  Éléments récurrents  ·  casting · accessoires · véhicules":
        "▸  Recurring elements  ·  cast · props · vehicles",
    "▾  Éléments récurrents  ·  casting · accessoires · véhicules":
        "▾  Recurring elements  ·  cast · props · vehicles",

    # ── Studio IA Cinéma : onglets Sound Design + Upscaling (portés du Live) ──
    "Upscaling de vos clips": "Upscale your clips",
    "▸ La sortie garde le MÊME NOM que la source → Relink Media direct dans DaVinci.":
        "▸ The output keeps the SAME NAME as the source → direct Relink Media in DaVinci.",
    "Sonorise tes plans : un prompt son → SFX/ambiance, ou un clip vidéo → bande-son synchronisée (Mirelo SFX 1.6, ~$0.01/s).":
        "Add sound to your shots: a sound prompt → SFX/ambience, or a video clip → synchronized soundtrack (Mirelo SFX 1.6, ~$0.01/s).",
    "Vidéo → bande-son": "Video → soundtrack",
    "📁  Choisir un clip vidéo…": "📁  Choose a video clip…",
    "Aucun clip sélectionné": "No clip selected",
    "Choisir un clip vidéo": "Choose a video clip",
    "Choisis d'abord un clip vidéo.": "Choose a video clip first.",
    "Prompt son optionnel (anglais) pour orienter la bande-son. Laisse vide pour une sonorisation automatique du clip.":
        "Optional sound prompt (English) to guide the soundtrack. Leave empty for automatic clip scoring.",
    "Décris l'ambiance / les effets sonores (en anglais de préférence). Ex. « rain on a tin roof, distant thunder, no music, no vocals »":
        "Describe the ambience / sound effects (preferably in English). E.g. \"rain on a tin roof, distant thunder, no music, no vocals\"",
    "Statut": "Status",
    "Double-clic : lire le clip upscalé": "Double-click: play the upscaled clip",
    "Clic droit : retirer de la file": "Right click: remove from queue",
    "Annuler l'envoi": "Cancel sending",
    "Calage Resolume": "Resolume calibration",
    "CONTRÔLEUR RESOLUME": "RESOLUME CONTROLLER",
    "Connexion :": "Connection:",
    "couches × colonnes — clic gauche : charger le clip sélectionné · clic droit : déclencher":
        "layers × columns — left click: load selected clip · right click: trigger",
    "Extrait automatiquement le polygone de la façade et génère :\n• un preset Advanced Output (menu Presets de Resolume)\n• une mire de calage PNG spécifique au bâtiment.\nLe calage manuel des points devient une simple vérification.":
        "Automatically extracts the facade polygon and generates:\n• an Advanced Output preset (Resolume's Presets menu)\n• a building-specific PNG calibration card.\nManual point calibration becomes a simple check.",
    "Choisis d'abord la façade du bâtiment.": "Pick the building facade first.",
    "Choisis d'abord la façade du bâtiment (Conducteur → Référence bâtiment).":
        "Pick the building facade first (Conductor → Building reference).",
    "Façade non détectée — utilise « Isoler (fond noir) » d'abord.":
        "Facade not detected — use « Isolate (black background) » first.",
    "Calage généré": "Calibration generated",
    "preset": "preset",
    "mire": "calibration card",
    "Resolume : Advanced Output → Presets": "Resolume: Advanced Output → Presets",
    "Proteus  (polyvalent — recommandé)": "Proteus  (all-round — recommended)",
    "Artemis HQ  (footage propre)": "Artemis HQ  (clean footage)",
    "Artemis MQ  (footage moyen)": "Artemis MQ  (average footage)",
    "Gaia HQ  (rendu naturel)": "Gaia HQ  (natural render)",
    "Gaia CG  (rendu 3D / CG)": "Gaia CG  (3D / CG render)",
    "Nyx  (réduction de bruit)": "Nyx  (noise reduction)",
    "Starlight Mini  (qualité max, lent)": "Starlight Mini  (max quality, slow)",
    "Arrête la file : le plan en cours est abandonné,\nles plans restants sont conservés en attente.":
        "Stops the queue: the current shot is abandoned,\nremaining shots stay pending.",
    "Arrête la file : le clip en cours est abandonné,\nles clips restants sont conservés en attente.":
        "Stops the queue: the current clip is abandoned,\nremaining clips stay pending.",
    "File annulée": "Queue cancelled",
    "en attente": "pending",
    "Chaque clip est réglé : Play Once & Hold (joue une fois, tient sa\ndernière frame), Beat Snap 1 mesure, Autopilot « clip suivant ».\nDéclenche le 1er clip : toute la séquence se joue seule, au tempo.":
        "Each clip is set to: Play Once & Hold (plays once, holds its\nlast frame), Beat Snap 1 bar, Autopilot \"next clip\".\nTrigger the 1st clip: the whole sequence plays itself, on tempo.",
    "◈  Tester la connexion": "◈  Test connection",
    "La clé fal.ai est partagée avec PANDORA | Cinéma.\nElle est utilisée pour la génération de clips IA dans le module Live.": "The fal.ai key is shared with PANDORA | Cinéma.\nIt is used for AI clip generation in the Live module.",
    "Fonctionnalité optionnelle — ne fonctionne pas avec DaVinci Resolve (version gratuite/Lite). Requiert DaVinci Resolve Studio (version payante).": "Optional feature — does not work with DaVinci Resolve (free/Lite version). Requires DaVinci Resolve Studio (paid version).",
    "⚙  Installer le script PANDORA dans DaVinci Resolve Studio": "⚙  Install the PANDORA script in DaVinci Resolve Studio",
    "Installe le script pandora_send dans DaVinci Resolve Studio\n(Fusion/Scripts/Utility).\nPermet d'envoyer des clips vers AI Studio\n→ Modifier depuis DaVinci Resolve\nvia Espace de travail → Scripts → pandora_send.\n\nPour configurer un raccourci clavier dans DaVinci Resolve Studio :\nEspace de travail → Personnalisation du clavier\n→ Rechercher « pandora_send »\n→ Assigner votre raccourci (ex. Ctrl+Shift+P)": "Installs the pandora_send script in DaVinci Resolve Studio\n(Fusion/Scripts/Utility).\nLets you send clips to AI Studio\n→ Edit from DaVinci Resolve\nvia Workspace → Scripts → pandora_send.\n\nTo set a keyboard shortcut in DaVinci Resolve Studio:\nWorkspace → Keyboard Customization\n→ Search « pandora_send »\n→ Assign your shortcut (e.g. Ctrl+Shift+P)",
    "Installe le client :\n\npip install fal-client": "Install the client:\n\npip install fal-client",
    "Voulez-vous vraiment quitter le programme ?": "Are you sure you want to quit?",
    "Quitter sans sauvegarder": "Quit without saving",
    "DaVinci Resolve Studio requis — connectez le bridge pour activer cette option": "DaVinci Resolve Studio required — connect the bridge to enable this option",
    "💰  Génération facturée via fal.ai (Seedance 2.0)  ·  Tarifs détaillés dans le Manuel d'utilisation": "💰  Generation billed via fal.ai (Seedance 2.0)  ·  Detailed pricing in the User Manual",
    "● Étape 2/3 — Synchronisation LatentSync…": "● Step 2/3 — LatentSync synchronization…",
    "● Étape 3/3 — Import DaVinci…": "● Step 3/3 — DaVinci import…",
    "Après génération Seedance, resynchronise les lèvres de l'acteur\navec l'audio source du clip DaVinci (fal-ai/latentsync).\nImporte la vidéo lip-synced + la piste audio séparément dans DaVinci.": "After Seedance generation, resync the actor's lips\nwith the source audio of the DaVinci clip (fal-ai/latentsync).\nImports the lip-synced video + the audio track separately into DaVinci.",
    "Aucune clé API fal.ai n'est configurée.\n\nLa génération va tourner en mode simulation :\nles vidéos seront fictives et aucun fichier ne sera créé.\n\nPour générer de vraies vidéos, ajoutez votre clé fal.ai\ndans Paramètres, puis relancez.\n\nContinuer en mode simulation ?": "No fal.ai API key is configured.\n\nGeneration will run in simulation mode:\nvideos will be fake and no file will be created.\n\nTo generate real videos, add your fal.ai key\nin Settings, then try again.\n\nContinue in simulation mode?",
    "◎  Modifier un clip existant": "◎  Edit an existing clip",
    "Cet onglet permet de travailler sur un clip vidéo existant selon 3 modes :\n  • Générer un début  —  génère un nouveau clip à placer avant le clip source\n  • Générer une suite  —  génère un nouveau clip à placer après le clip source\n  • Nouveau rush  —  génère une nouvelle prise à partir du même clip\n\nPour utiliser un clip depuis DaVinci Resolve :\n  → Sélectionne le clip dans la timeline DaVinci\n  → Clique sur « Utiliser le clip DaVinci » ci-dessous\n  → Le nom du clip apparaît dans « Clip sélectionné »": "This tab lets you work on an existing video clip in 3 modes:\n  • Generate a beginning  —  generates a new clip to place before the source clip\n  • Generate a continuation  —  generates a new clip to place after the source clip\n  • New take  —  generates a new take from the same clip\n\nTo use a clip from DaVinci Resolve:\n  → Select the clip in the DaVinci timeline\n  → Click « Use DaVinci clip » below\n  → The clip name appears in « Selected clip »",
    "Connecte DaVinci Resolve via la barre de statut en haut.": "Connect DaVinci Resolve via the status bar at the top.",
    "Sélectionne un clip dans la timeline DaVinci puis réessaie.\n\nAstuce : clique sur le clip dans la timeline DaVinci\njuste avant de cliquer ce bouton.": "Select a clip in the DaVinci timeline then try again.\n\nTip: click the clip in the DaVinci timeline\njust before clicking this button.",
    "Décris ta scène... Utilise @image, @video, @audio pour référencer tes uploads.\nEx: génère une scène où @image marche dans la forêt, avec l'ambiance de @video.": "Describe your scene... Use @image, @video, @audio to reference your uploads.\nE.g.: generate a scene where @image walks in the forest, with the mood of @video.",
    "Utilisée par le bouton ✦ Améliorer pour optimiser tes prompts via Claude.": "Used by the ✦ Enhance button to optimize your prompts via Claude.",
    "Tester la connexion API": "Test API connection",
    "⊘ Ne pas envoyer": "⊘ Don't send",
    "🏛  Mode ancré — Seedance traite le décor comme un espace 3D réel (conserve l'architecture et les angles du lieu)": "🏛  Anchored mode — Seedance treats the location as a real 3D space (preserves the architecture and angles of the place)",
    "Inclure dans le prompt": "Include in the prompt",
    "Images de référence non transmises à Seedance": "Reference images not sent to Seedance",
    "L'upload des images de référence (personnages, décors, véhicules) a échoué. Vérifie que ta clé fal.ai est correcte dans les Paramètres du plugin.": "Uploading the reference images (characters, locations, vehicles) failed. Check that your fal.ai key is correct in the plugin Settings.",
    "Quand cochée, aucune image de référence (personnages, décors, accessoires, véhicules) n'est envoyée à Seedance — génération texte uniquement.": "When checked, no reference image (characters, locations, props, vehicles) is sent to Seedance — text-only generation.",
    "Chaque plan possède ses propres paramètres prédéfinis (prompt, focale, durée, casting…). Vous ne pouvez pas modifier les paramètres individuellement lors d'une sélection multiple.": "Each shot has its own preset parameters (prompt, focal length, duration, cast…). You cannot edit parameters individually during a multiple selection.",
    "Nombre de générations (1–10)\nEn mode multi-plan, répète chaque plan N fois.": "Number of generations (1–10)\nIn multi-shot mode, repeats each shot N times.",
    "◈  PANDORA — Prompt envoyé à Seedance": "◈  PANDORA — Prompt sent to Seedance",
    "traduit auto · sans upload images": "auto-translated · no image upload",
    "🔗  Recharger sur fal.ai →": "🔗  Top up on fal.ai →",
    "Décrivez le mouvement… (FR accepté)": "Describe the movement… (French accepted)",
    "Décrivez la scène en détail — Veo 3.1 génère vidéo + audio haute qualité…\n(FR accepté, traduit automatiquement en anglais)": "Describe the scene in detail — Veo 3.1 generates high-quality video + audio…\n(French accepted, automatically translated to English)",
    "Décrivez la scène en détail — Sora 2 génère une vidéo 1080p haute qualité…\n(FR accepté, traduit automatiquement en anglais)": "Describe the scene in detail — Sora 2 generates high-quality 1080p video…\n(French accepted, automatically translated to English)",
    "▸ Happy Horse 1.0 ★ : modèle Alibaba #1 Video Arena, 720p ou 1080p, T2V + I2V ($0.14–0.28/s).": "▸ Happy Horse 1.0 ★: Alibaba's #1 Video Arena model, 720p or 1080p, T2V + I2V ($0.14–0.28/s).",
    "▸ Kling O3 4K : dernier Kling, résolution 4K, T2V + I2V (~$0.42/s).": "▸ Kling O3 4K: latest Kling, 4K resolution, T2V + I2V (~$0.42/s).",
    "▸ PixVerse v6 : T2V 360p–1080p avec audio optionnel ($0.025–0.115/s).": "▸ PixVerse v6: T2V 360p–1080p with optional audio ($0.025–0.115/s).",
    "▸ Veo 3.1 : modèle Google, audio natif, 8 s fixes, 1080p (~$1.00/vidéo).": "▸ Veo 3.1: Google model, native audio, fixed 8 s, 1080p (~$1.00/video).",
    "▸ Sora 2 : modèle OpenAI, 4 s fixes, 1080p, haute qualité (~$0.40/vidéo).": "▸ Sora 2: OpenAI model, fixed 4 s, 1080p, high quality (~$0.40/video).",
    "Image de fin (optionnel)": "End image (optional)",
    "Le prompt est requis.": "A prompt is required.",
    "Le prompt est requis pour Kling T2V.": "A prompt is required for Kling T2V.",
    "Le prompt est requis pour Kling v3 4K.": "A prompt is required for Kling v3 4K.",
    "Le prompt est requis pour Veo 3.1.": "A prompt is required for Veo 3.1.",
    "Le prompt est requis pour Happy Horse.": "A prompt is required for Happy Horse.",
    "Le prompt est requis pour Kling O3 4K.": "A prompt is required for Kling O3 4K.",
    "Le prompt est requis pour PixVerse v6.": "A prompt is required for PixVerse v6.",
    "Le prompt est requis pour Sora 2.": "A prompt is required for Sora 2.",
    "Image requise pour PixVerse I2V.": "Image required for PixVerse I2V.",
    "⤷ Modifier": "⤷ Edit",
    "Envoyer vers « Modifier depuis DaVinci Resolve »": "Send to « Edit from DaVinci Resolve »",
    "Vidéothèque — bibliothèque des vidéos générées": "Video Library — library of generated videos",
    "▸ Cliquez sur ⤷ Modifier pour envoyer vers « Modifier depuis DaVinci Resolve ».": "▸ Click ⤷ Edit to send to « Edit from DaVinci Resolve ».",
    "▸ Le bouton 📁 ouvre directement le dossier de destination dans l'explorateur.": "▸ The 📁 button opens the destination folder directly in the file explorer.",
    "Ouvrir le log d'erreurs d'extraction dans le Bloc-notes": "Open the extraction error log in Notepad",
    "📁  Ouvrir le dossier": "📁  Open folder",
    "La génération n'a pas pu démarrer.\n\nRechargez votre compte sur fal.ai/dashboard\npour continuer à utiliser PANDORA.": "Generation could not start.\n\nTop up your account on fal.ai/dashboard\nto keep using PANDORA.",
    "Optimiser avec Claude\nAméliore le prompt via l'API Anthropic pour de meilleurs résultats.": "Optimize with Claude\nImproves the prompt via the Anthropic API for better results.",
    "Activé : l'optimisation Claude s'exécute automatiquement quand c'est pertinent.\nDésactivé : Claude n'intervient que si vous cliquez explicitement sur le bouton.": "Enabled: Claude optimization runs automatically when relevant.\nDisabled: Claude only acts when you explicitly click the button.",
    "Lectrosonics (Sans fil)": "Lectrosonics (Wireless)",
    "Zaxcom (Sans fil)": "Zaxcom (Wireless)",
    "Wisycom (Sans fil)": "Wisycom (Wireless)",
    "Lever du soleil": "Sunrise",
    "Coucher du soleil": "Sunset",
    "Traduction du prompt…": "Translating prompt…",
    "Analyse de l'image de style…": "Analyzing style image…",
    "Suppression du fond…": "Removing background…",
    "Encodage de l'image…": "Encoding image…",
    "Upload de la photo (mode mock)…": "Uploading photo (mock mode)…",
    "Analyse du visage (mode mock)…": "Analyzing face (mock mode)…",
    "Assemblage du character sheet…": "Assembling character sheet…",
    "✗  Resolve non accessible": "✗  Resolve not reachable",
    "Resolve non disponible": "Resolve unavailable",
    "Aucun projet DaVinci ouvert": "No DaVinci project open",
    "DaVinci Resolve non accessible — DaVinci Studio requis.": "DaVinci Resolve not reachable — DaVinci Studio required.",
    "Aucune timeline ouverte dans DaVinci.": "No timeline open in DaVinci.",
    "Ancre le rendu dans le filmage réel — ARRI 35mm, grain argentique, peau naturelle, no CGI, no 3D  ·  Automatiquement ignoré si le style 'Film réaliste' ou 'Photoréaliste' est actif (déjà inclus)": "Anchors the render in real footage — ARRI 35mm, film grain, natural skin, no CGI, no 3D  ·  Automatically ignored if the 'Realistic film' or 'Photorealistic' style is active (already included)",
    "Utilise la dernière frame du plan précédent comme point de départ (I2V) — enchaîne les plans comme un Extend": "Uses the last frame of the previous shot as the starting point (I2V) — chains shots together like an Extend",

    # ── Lot 1 — valeurs d'enum + menus storyboard + dialog_shot (audit 2026-06) ─
    'Fixe': 'Static',
    'Panoramique horizontal': 'Horizontal pan',
    'Panoramique vertical': 'Vertical tilt',
    'Travelling avant': 'Dolly in',
    'Zoom avant': 'Zoom in',
    'Grue / Drone': 'Crane / Drone',
    'Sphérique': 'Spherical',
    'Anamorphique': 'Anamorphic',
    'Jour': 'Day',
    'Nuit': 'Night',
    'Normale': 'Normal',
    'Ralenti': 'Slow motion',
    'Accéléré': 'Fast motion',
    'Vue subjective': 'POV (subjective)',
    'Autre': 'Other',
    'GP — Gros Plan': 'CU — Close-Up',
    'GM — Grand Médium': 'MCU — Medium Close-Up',
    'PM — Plan Moyen': 'MS — Medium Shot',
    'PP — Plan Poitrine': 'MS — Chest Shot',
    'PL — Plan Large': 'WS — Wide Shot',
    "PE — Plan d'Ensemble": 'FS — Full Shot',
    'PTG — Plan Très Général': 'EWS — Extreme Wide Shot',
    '— Aucune —': '— None —',
    'Axe Caméra': 'Camera Axis',
    'Heure précise…': 'Specific time…',
    'Heure (ex : 14h30, 07h00) :': 'Time (e.g. 14:30, 07:00):',
    '✎  Saisir une valeur…': '✎  Enter a value…',
    'Distance sujet-caméra': 'Subject-camera distance',
    'Distance (ex : 4m, 4.5m, 12m) :': 'Distance (e.g. 4m, 4.5m, 12m):',
    'Modifier la séquence': 'Edit sequence',
    'N° de séquence': 'Sequence no.',
    'Choisir un décor': 'Choose a location',
    'Sélectionner un décor': 'Select a location',
    'Aucun décor créé dans ce projet.': 'No location created in this project.',
    'Aucun élément disponible.': 'No item available.',
    'Voir / générer le Mood de ce plan': "View / generate this shot's Mood",
    'Aucun découpage': 'No breakdown',
    "Ex: La fuite, L'affrontement…": 'E.g. The escape, The showdown…',
    '✦  Améliorer': '✦  Enhance',
    'Numéro de séquence': 'Sequence number',
    'N° du plan dans la séquence — ex: 3 → Plan 1/3': 'Shot no. within the sequence — e.g. 3 → Shot 1/3',
    'Ex: Prison, Voiture Nuit, Concert…': 'E.g. Prison, Car Night, Concert…',
    'Ex: Le chanteur est assis sur la banquette…': 'E.g. The singer is sitting on the bench seat…',
    'ex : 14h30, Jour…': 'e.g. 14:30, Day…',
    'Ex: Face table côté Raoul, légère 3/4…': "E.g. Facing the table on Raoul's side, slight 3/4…",
    'Ex: PÈRE + MÈRE côté gauche, SARAH + RAOUL côté droit': 'E.g. FATHER + MOTHER on the left, SARAH + RAOUL on the right',
    'Ex: RAOUL (gros plan)': 'E.g. RAOUL (close-up)',
    'Ex: SARAH (amorce épaule), PÈRE hors-champ': 'E.g. SARAH (shoulder framing), FATHER off-screen',
    'Ex: RAOUL (perche)': 'E.g. RAOUL (boom mic)',

    # ── Lot 2 — CRUD pages, éléments, créatif, studio, assistant (audit 2026-06) ─
    '✦  Créer un personnage': '✦  Create a character',
    '✕  Supprimer tout le casting': '✕  Delete all cast',
    'Aucun personnage.\nClique sur ✦ Créer un personnage pour commencer.': 'No characters.\nClick ✦ Create a character to get started.',
    'Supprimer tout le casting': 'Delete all cast',
    'Importer des portraits': 'Import portraits',
    'Usage des références': 'Reference usage',
    'Style de génération': 'Generation style',
    '↓  Suffix de style injecté (modifiable) :': '↓  Injected style suffix (editable):',
    "Vide — sélectionnez un Style d'image ci-dessus ou définissez le Style du projet": 'Empty — select an Image style above or set the Project style',
    '🎬  Character Sheet 5 vues': '🎬  Character Sheet 5 views',
    '📷  Portrait classique': '📷  Classic portrait',
    '🌟  Inspiration  —  Claude enrichit le prompt': '🌟  Inspiration  —  Claude enriches the prompt',
    '🎨  Style pictural  —  extrait et applique le style visuel': '🎨  Pictorial style  —  extracts and applies the visual style',
    '🧑  Référence de visage  —  génère le portrait avec ce visage': '🧑  Face reference  —  generates the portrait with this face',
    '🎯  Fidélité exacte  —  reproduit le sujet précisément': '🎯  Exact fidelity  —  reproduces the subject precisely',
    "🎯  Fidélité exacte  —  reproduit l'objet précisément": '🎯  Exact fidelity  —  reproduces the object precisely',
    '🎯  Fidélité exacte  —  reproduit le look précisément': '🎯  Exact fidelity  —  reproduces the look precisely',
    '🎯  Fidélité exacte  —  reproduit le véhicule précisément': '🎯  Exact fidelity  —  reproduces the vehicle precisely',
    "Voir le Manuel d'utilisation pour tous les tarifs": 'See the User Manual for all pricing',
    'Aucun portrait\ngénéré': 'No portrait\ngenerated',
    '✓  Activer': '✓  Activate',
    '🎙  Doublage': '🎙  Dubbing',
    '🔄  Générer à nouveau': '🔄  Regenerate',
    '✨  Générer avec HMC': '✨  Generate with HMC',
    'Assignés à ce personnage': 'Assigned to this character',
    'Autres éléments HMC': 'Other HMC items',
    'Catégorie :': 'Category:',
    'Toutes': 'All',
    '✦  Créer un décor': '✦  Create a location',
    '✕  Tout supprimer': '✕  Delete all',
    'Tout supprimer': 'Delete all',
    'Aucun décor.\nClique sur ✦ Créer un décor pour commencer.': 'No locations.\nClick ✦ Create a location to get started.',
    'Non assigné': 'Unassigned',
    'Supprimer tous les décors': 'Delete all locations',
    '✦  Créer un accessoire': '✦  Create a prop',
    'Aucun accessoire.\nClique sur ✦ Créer un accessoire pour commencer.': 'No props.\nClick ✦ Create a prop to get started.',
    'Supprimer tous les accessoires': 'Delete all props',
    'Ex: Château médiéval en ruines': 'E.g.: Medieval castle ruins',
    'Optimiser avec Claude\nAdapté aux décors de production cinéma.': 'Optimize with Claude\nTailored for cinema production locations.',
    'Claude enrichit le prompt': 'Claude enriches the prompt',
    '📁  Importer une image depuis le disque': '📁  Import an image from disk',
    'Ex: Montre en or victorienne': 'E.g.: Victorian gold watch',
    'Optimiser avec Claude\nAdapté aux accessoires de production cinéma.': 'Optimize with Claude\nTailored for cinema production props.',
    'Intérieur': 'Interior',
    'Extérieur': 'Exterior',
    'Urbain': 'Urban',
    'Aquatique': 'Water',
    'Aérien': 'Aerial',
    'Fantastique': 'Fantasy',
    'Industriel': 'Industrial',
    'Bijoux': 'Jewelry',
    'Armes': 'Weapons',
    'Électronique': 'Electronics',
    'Mobilier': 'Furniture',
    'Vêtement': 'Clothing',
    'Véhicule': 'Vehicle',
    'Autre…': 'Other…',
    'Habillage · Maquillage · Coiffure': 'Costume · Makeup · Hair',
    '✦  Créer un élément HMC': '✦  Create an HMC item',
    'Supprimer tout le HMC': 'Delete all HMC',
    'Aucun élément HMC.\nClique sur ✦ Créer un élément HMC pour commencer.': 'No HMC items.\nClick ✦ Create an HMC item to get started.',
    'Habit': 'Costume',
    '✦  Créer un véhicule': '✦  Create a vehicle',
    'Aucun véhicule.\nClique sur ✦ Créer un véhicule pour commencer.': 'No vehicles.\nClick ✦ Create a vehicle to get started.',
    'Supprimer tous les véhicules': 'Delete all vehicles',
    'Ex: La Citroën DS noire de Viktor': "E.g.: Viktor's black Citroën DS",
    'Tous': 'All',
    'Moto': 'Motorcycle',
    'Camion': 'Truck',
    'Bateau': 'Boat',
    'Avion': 'Plane',
    'Vélo': 'Bicycle',
    'Voiture': 'Car',
    'Heure du jour': 'Time of day',
    'Saison': 'Season',
    'Vue': 'View',
    'Palette couleurs': 'Color palette',
    'Finition': 'Finish',
    'Peinture': 'Painting',
    'Aquarelle': 'Watercolor',
    'Rendu 3D': '3D render',
    'Croquis': 'Sketch',
    'Naturel': 'Natural',
    'Dramatique': 'Dramatic',
    'Charismatique': 'Charismatic',
    'Neutre': 'Neutral',
    'Aube': 'Dawn',
    'Matin': 'Morning',
    'Midi': 'Noon',
    'Brumeux': 'Foggy',
    'Nuageux': 'Cloudy',
    'Pluvieux': 'Rainy',
    'Orageux': 'Stormy',
    'Neigeux': 'Snowy',
    'Printemps': 'Spring',
    'Été': 'Summer',
    'Automne': 'Autumn',
    'Hiver': 'Winter',
    'Cuir': 'Leather',
    'Tissu': 'Fabric',
    'Bois': 'Wood',
    'Or': 'Gold',
    'Argent': 'Silver',
    'Pierre': 'Stone',
    'Plastique': 'Plastic',
    'Neuf': 'New',
    'Usé': 'Worn',
    'Vieilli': 'Aged',
    'Poli': 'Polished',
    'Mat': 'Matte',
    'Profil': 'Profile',
    'Contemporain': 'Contemporary',
    'Victorien': 'Victorian',
    'Futuriste': 'Futuristic',
    'Haute Couture': 'Haute couture',
    'Formel': 'Formal',
    'Fantaisie': 'Fantasy',
    'Chaud': 'Warm',
    'Froid': 'Cool',
    'Vif': 'Vibrant',
    'Brillant': 'Gloss',
    'Militaire': 'Military',
    '3/4 Avant': '3/4 front',
    '3/4 Arrière': '3/4 rear',
    'Dessus': 'Top-down',
    'Zoom lent': 'Slow zoom',
    'Calme': 'Calm',
    'Contrejour': 'Backlit',
    'Libre': 'Free',
    'Rythme': 'Pace',
    'Rendu': 'Rendering',
    'Prof. de champ': 'Depth of field',
    'Dynamique': 'Dynamic',
    'Subtil': 'Subtle',
    'Lent': 'Slow',
    'Rapide': 'Fast',
    'Douce': 'Soft',
    'Riche': 'Rich',
    'Net': 'Sharp',
    'Flou': 'Blurry',
    'Corps de caméra · Optiques · Filtres · Microphone': 'Camera body · Optics · Filters · Microphone',
    'Microphone principal du tournage — injecté dans les paramètres sonores des prompts.': 'Main production microphone — injected into the sound parameters of prompts.',
    "Génération d'ambiances sonores & bruitages IA": 'AI sound atmospheres & SFX generation',
    "🎵  Générer l'ambiance": '🎵  Generate atmosphere',
    'Initialisation…': 'Initializing…',
    'Raccord automatique': 'Auto continuity',
    "Changement d'angle toutes les 2 secondes": 'Camera angle change every 2 seconds',
    'Format :': 'Format:',
    'Audio :': 'Audio:',
    'Natif': 'Native',
    'Nouveau rush': 'New take',
    'Clip source': 'Source clip',
    'Dossier de sortie des clips': 'Output folder for clips',
    '▼  CONSEILS': '▼  TIPS',
    '▼  GUIDE COMPLET': '▼  FULL GUIDE',
    '▶  CONSEILS': '▶  TIPS',
    '▶  GUIDE COMPLET': '▶  FULL GUIDE',
    '✦  Demander': '✦  Ask',
    'Renommez un projet en cliquant sur son nom dans la fiche.': 'Rename a project by clicking its name in the record.',
    'Changez de projet depuis cette page sans quitter PANDORA.': 'Switch projects from this page without leaving PANDORA.',
    "'Mise en page PANDORA' structure le texte en blocs plans optimisés pour Seedance.": "'PANDORA formatting' structures the text into shot blocks optimized for Seedance.",
    "Versions nommées (✚/✕) et undo/redo (↩/↪) pour revenir à n'importe quel état.": 'Named versions (✚/✕) and undo/redo (↩/↪) to return to any state.',
    "'⟳ Synchronisation' aligne les prompts avec les noms actuels du casting/décors.": "'⟳ Sync' aligns prompts with the current casting/location names.",
    'Assignez personnages et décors à chaque plan — ils servent de références Seedance.': 'Assign characters and locations to each shot — they serve as Seedance references.',
    'Personnages du film — portraits et références Seedance.': 'Film characters — portraits and Seedance references.',
    'Les portraits servent de références visuelles dans Seedance.': 'Portraits serve as visual references in Seedance.',
    "La 'Fiche 4 vues' génère face, 3/4, profil et dos pour plus de cohérence.": "The '4-view sheet' generates front, 3/4, profile and back for more coherence.",
    'Lieux de tournage — visuels de référence pour Seedance.': 'Shooting locations — reference visuals for Seedance.',
    "L'image du décor est envoyée automatiquement comme référence visuelle à Seedance.": 'The location image is sent automatically as a visual reference to Seedance.',
    'Les accessoires assignés à un plan sont envoyés comme références visuelles à Seedance.': 'Props assigned to a shot are sent as visual references to Seedance.',
    'HMC = Habillage, Maquillage, Coiffure.': 'HMC = Costume, Makeup, Hair.',
    "Partagez ces références avec l'équipe costume/maquillage.": 'Share these references with the costume/makeup team.',
    'Les véhicules assignés à un plan sont envoyés comme références visuelles à Seedance.': 'Vehicles assigned to a shot are sent as visual references to Seedance.',
    'Studio IA': 'AI Studio',
    'Génération vidéo IA — 13 moteurs dont Seedance, Kling, Veo 3.1.': 'AI video generation — 13 engines including Seedance, Kling, Veo 3.1.',
    "Si des personnages/décors sont assignés, le mode référence s'active.": 'If characters/locations are assigned, reference mode activates.',
    'Utilisez Ctrl+S pour une sauvegarde manuelle.': 'Use Ctrl+S for a manual save.',
    'Durée du plan': 'Shot duration',
    'Durée (1 — 15 secondes) :': 'Duration (1 — 15 seconds):',
    'Image supprimée.': 'Image deleted.',
    'Portrait ajouté ✓': 'Portrait added ✓',
    'Réaliste': 'Realistic',
    "Ces paramètres s'injectent automatiquement dans les prompts de génération vidéo pour reproduire le rendu d'un équipement spécifique — corps de caméra, gamme d'optiques, filtres et microphone du tournage.": "These settings are automatically injected into the video generation prompts to reproduce the look of specific equipment — camera body, lens range, filters and production microphone.",

    # ── Lot 9 — panneau Scénario + barre Storyboard (captures 2026-06) ──
    "◎  Références visuelles": "◎  Visual references",
    "☁  Claude IA": "☁  Claude AI",
    "☁  Générer depuis le scénario": "☁  Generate from the screenplay",
    "Analyse structure + suggestions": "Structure analysis + suggestions",
    "Structure le scénario en blocs plans optimisés pour PANDORA": "Structures the screenplay into shot blocks optimized for PANDORA",
    "Générer le HMC": "Generate HMC",
    "Identifier les personnages depuis le scénario": "Identify characters from the screenplay",
    "Identifier les décors depuis le scénario": "Identify locations from the screenplay",
    "Identifier les accessoires depuis le scénario": "Identify props from the screenplay",
    "Identifier les éléments HMC depuis le scénario": "Identify HMC items from the screenplay",
    "Identifier les véhicules depuis le scénario": "Identify vehicles from the screenplay",
    "Importe les plans dans Storyboard": "Imports the shots into Storyboard",
    "Durée cible :": "Target duration:",
    "Estimé :": "Estimated:",
    "Estimé : —": "Estimated: —",
    "Personnages · Décors · Accessoires · HMC · Véhicules · Storyboard · Images · Moods": "Characters · Locations · Props · HMC · Vehicles · Storyboard · Images · Moods",
    "⟳  Synchronisation": "⟳  Sync",
    "✕  Supprimer": "✕  Delete",
    "＋ Créer un storyboard": "＋ Create a storyboard",
    "＋  Ajouter un plan": "＋  Add shot",

    # ── Lot 10 — dialogues Aperçu/Analyse, mise à jour, soutien (captures) ──
    "Mise en page PANDORA — Aperçu Claude": "PANDORA Layout — Claude Preview",
    "◈  Mise en page PANDORA — Aperçu": "◈  PANDORA Layout — Preview",
    "Mise en page en cours…": "Layout in progress…",
    "Mise en page terminée": "Layout complete",
    "Mise en page PANDORA terminée": "PANDORA Layout complete",
    "Le scénario mis en page apparaît ici au fil de la génération…": "The formatted screenplay appears here as it is generated…",
    "↩  Remplacer le texte": "↩  Replace text",
    "Arrangement — Analyse Claude": "Arrangement — Claude Analysis",
    "◈  Arrangement — Analyse": "◈  Arrangement — Analysis",
    "Analyse en cours…": "Analysis in progress…",
    "Analyse terminée": "Analysis complete",
    "☁  Session de co-écriture": "☁  Co-writing session",
    "✓  Appliquer les suggestions": "✓  Apply suggestions",
    "Mises à jour": "Updates",
    "↑  Mises à jour": "↑  Updates",
    "PANDORA est à jour.": "PANDORA is up to date.",
    "Choisissez votre moyen de soutenir le développement de PANDORA :": "Choose how you'd like to support PANDORA's development:",
    "Don rapide en euros — carte bancaire ou compte PayPal": "Quick donation in euros — bank card or PayPal account",
    "Bitcoin (Taproot) · USDC (Réseau Sonic)": "Bitcoin (Taproot) · USDC (Sonic Network)",
    "Réseau Bitcoin · Taproot": "Bitcoin Network · Taproot",
    "Réseau Sonic": "Sonic Network",
    "← Retour": "← Back",
    "⎘  Copier": "⎘  Copy",
    "✓  Copié !": "✓  Copied!",

    # ── Lot 11 — fenêtres de génération (ExtractGenerateDialog) ──
    "Générer —": "Generate —",
    "Personnages depuis le scénario": "Characters from the screenplay",
    "Décors depuis le scénario": "Locations from the screenplay",
    "Accessoires depuis le scénario": "Props from the screenplay",
    "HMC depuis le scénario": "HMC from the screenplay",
    "Véhicules depuis le scénario": "Vehicles from the screenplay",
    "Choisir une option pour démarrer": "Choose an option to start",
    "Comment souhaitez-vous procéder ?": "How would you like to proceed?",
    "Identifier les personnages": "Identify characters",
    "Identifier les décors": "Identify locations",
    "Identifier les accessoires": "Identify props",
    "Identifier les éléments HMC": "Identify HMC items",
    "Identifier les véhicules": "Identify vehicles",
    "Identifier et générer les images": "Identify and generate images",
    "Extrait et sauvegarde les éléments — sans générer d'images": "Extracts and saves the items — without generating images",
    "Extrait, sauvegarde, puis génère une image via Nano Banana pour chaque élément": "Extracts, saves, then generates an image via Nano Banana for each item",
    "✕  Annuler": "✕  Cancel",
    "Extraction via Claude IA…": "Extraction via Claude AI…",
    "Claude analyse le scénario…": "Claude is analyzing the screenplay…",
    "Aucun élément identifié dans le scénario.": "No item identified in the screenplay.",
    "Terminé": "Done",

    # ── Lot 12 — fenêtre Découpage Storyboard (génération) ──
    "Générer le Storyboard": "Generate the Storyboard",
    "Découpage Storyboard": "Storyboard Breakdown",
    "Claude génère le découpage technique…": "Claude is generating the technical breakdown…",
    "Analyse du scénario via Claude Sonnet…": "Analyzing the screenplay via Claude Sonnet…",
    "Aucun plan généré — le scénario est peut-être trop court.": "No shot generated — the screenplay may be too short.",
    "plans générés": "shots generated",
    "plans": "shots",
    "durée totale": "total duration",
    "Confirmez pour importer dans le Storyboard.": "Confirm to import into the Storyboard.",
    "Erreur": "Error",
    "Enregistrement…": "Saving…",
    "Erreur sauvegarde :": "Save error:",

    # ── Lot 13 — fenêtre Quitter PANDORA ──
    "Quitter PANDORA": "Quit PANDORA",
    "Les données du storyboard et des fiches sont sauvegardées automatiquement.": "Storyboard and sheet data are saved automatically.",
    "❤  PANDORA est gratuit. Il fonctionne grâce au soutien de la communauté.": "❤  PANDORA is free. It runs thanks to community support.",
    "Si ce logiciel vous est utile, un don — même modeste — nous aide à continuer à le développer.": "If this software is useful to you, a donation — even a small one — helps us keep developing it.",
    "❤  Soutenir PANDORA  →": "❤  Support PANDORA  →",
    "Sauvegarder et quitter": "Save and quit",

    # ── Lot 14 — placeholders & tooltips Scénario ──
    "L'analyse apparaît ici au fil de la génération…": "The analysis appears here as it is generated…",
    "Le scénario réécrit apparaît ici…": "The rewritten screenplay appears here…",
    "Le scénario enrichi apparaît ici au fil de la génération…": "The enriched screenplay appears here as it is generated…",
    "Écris ton scénario ici…\n\nINT. LIEU — JOUR\n\nDescription de la scène…\n\nPERSONNAGE\nDialogue du personnage.": "Write your screenplay here…\n\nINT. LOCATION — DAY\n\nScene description…\n\nCHARACTER\nCharacter's dialogue.",
    "Claude réécrit le scénario en appliquant directement les suggestions.\nLe résultat apparaît ici pour prévisualisation avant d'être appliqué.": "Claude rewrites the screenplay applying the suggestions directly.\nThe result appears here for preview before being applied.",

    # ── Lot 8 — Aide API, Projets, divers ──
    'Optimisation de prompts  ·  Scénario  ·  Storyboard': 'Prompt optimization  ·  Screenplay  ·  Storyboard',
    "💡  <b>Utilisation :</b> fal.ai et Anthropic sont des services payants à l'usage. Chaque génération consomme des crédits. Les deux plateformes offrent des crédits de démarrage gratuits pour tester.": '💡  <b>Usage:</b> fal.ai and Anthropic are pay-as-you-go services. Each generation consumes credits. Both platforms offer free starter credits to try them out.',
    "🔒  <b>VPN :</b> si Claude ne répond pas ou génère des erreurs, désactivez votre VPN — certains serveurs VPN sont bloqués par l'API Anthropic.": '🔒  <b>VPN:</b> if Claude does not respond or returns errors, disable your VPN — some VPN servers are blocked by the Anthropic API.',
    'Va sur <b>fal.ai</b> et crée un compte gratuit (ou connecte-toi).': 'Go to <b>fal.ai</b> and create a free account (or log in).',
    'Copie la clé (commence par <code>fal_</code>) et colle-la dans PANDORA.': 'Copy the key (starts with <code>fal_</code>) and paste it into PANDORA.',
    'Recharge ton compte fal.ai pour générer des vidéos et portraits.': 'Top up your fal.ai account to generate videos and portraits.',
    'Va sur <b>console.anthropic.com</b> et crée un compte (ou connecte-toi).': 'Go to <b>console.anthropic.com</b> and create an account (or log in).',
    'Copie la clé (commence par <code>sk-ant-</code>) et colle-la dans PANDORA.': 'Copy the key (starts with <code>sk-ant-</code>) and paste it into PANDORA.',
    'Claude est utilisé pour optimiser les prompts ☁, formater le scénario et générer le storyboard.': 'Claude is used to optimize prompts ☁, format the screenplay and generate the storyboard.',
    'Tout générer': 'Generate all',
    '✎  Renommer ce projet…': '✎  Rename this project…',
    'Renommer le projet': 'Rename project',
    'Nouveau nom :': 'New name:',

    # ── Lot 7 — styles visuels (core/style.py) ──
    'Arts & Esthétiques': 'Arts & Aesthetics',
    'Hybride': 'Hybrid',
    'Film réaliste': 'Realistic film',
    'Acteurs réels, photographie cinématographique naturaliste — ARRI Alexa, lumière naturelle': 'Real actors, naturalistic cinematic photography — ARRI Alexa, natural light',
    'Documentaire': 'Documentary',
    "Style journalistique, lumière naturelle, caméra à l'épaule": 'Journalistic style, natural light, handheld camera',
    'Drame social': 'Social drama',
    'Réalisme social, lumière froide naturelle, Ken Loach / Dardenne Brothers': 'Social realism, cold natural light, Ken Loach / Dardenne Brothers',
    'Noir et blanc, ombres dramatiques, atmosphère néo-noir': 'Black and white, dramatic shadows, neo-noir atmosphere',
    'Palette froide désaturée, tension psychologique, Fincher': 'Cold desaturated palette, psychological tension, Fincher',
    'Horreur': 'Horror',
    'Atmosphère sombre et oppressante, tension, effets pratiques': 'Dark, oppressive atmosphere, tension, practical effects',
    'Grand désert américain, lumière dure, Sergio Leone — gros plans intenses': 'Great American desert, harsh light, Sergio Leone — intense close-ups',
    'Guerre': 'War',
    'Champ de bataille désaturé, caméra portée, Saving Private Ryan / Dunkirk': 'Desaturated battlefield, handheld camera, Saving Private Ryan / Dunkirk',
    "Film d'action": 'Action film',
    'Caméra dynamique, coupes rapides, effets pratiques, Christopher Nolan / Michael Bay': 'Dynamic camera, fast cuts, practical effects, Christopher Nolan / Michael Bay',
    'Comédie musicale': 'Musical',
    'Couleurs vibrantes, éclairages théâtraux, chorégraphie — La La Land / Moulin Rouge': 'Vibrant colors, theatrical lighting, choreography — La La Land / Moulin Rouge',
    'Comédie romantique': 'Romantic comedy',
    'Lumière dorée douce, palette pastel, Paris ou New York — Richard Curtis / Nora Ephron': 'Soft golden light, pastel palette, Paris or New York — Richard Curtis / Nora Ephron',
    'Sci-fi spatiale': 'Space sci-fi',
    'Space opera, technologies avancées, chrome et blanc pur': 'Space opera, advanced technology, chrome and pure white',
    'Fantasy épique': 'Epic fantasy',
    'Mondes fantastiques, magie, épopée héroïque': 'Fantastical worlds, magic, heroic epic',
    'Publicité luxe': 'Luxury ad',
    'Parfum, haute couture — ultra-léché, lumière spéculaire': 'Perfume, haute couture — ultra-polished, specular light',
    'Animation 3D': '3D animation',
    'Images de synthèse, rendu CGI photoréaliste ou stylisé': 'CGI imagery, photorealistic or stylized render',
    'Dessin animé 2D': '2D cartoon',
    'Animation traditionnelle, illustration cartoon colorée': 'Traditional animation, colorful cartoon illustration',
    'Animation japonaise, esthétique manga et anime': 'Japanese animation, manga and anime aesthetic',
    'Cyberpunk néon': 'Neon cyberpunk',
    'Tokyo nocturne, néons violets et cyan, pluie et chrome': 'Nighttime Tokyo, purple and cyan neon, rain and chrome',
    'Lo-fi rétro': 'Lo-fi retro',
    'Super 8, grain argentique, couleurs passées, VHS et Kodachrome': 'Super 8, film grain, faded colors, VHS and Kodachrome',
    "Lavis d'aquarelle poétique, textures papier, doux et lumineux": 'Poetic watercolor wash, paper textures, soft and luminous',
    "Peinture à l'huile": 'Oil painting',
    'Impressionniste ou réaliste, matière riche et texture peinte': 'Impressionist or realist, rich impasto and painted texture',
    'BD franco-belge': 'Franco-Belgian comics',
    'Ligne claire, Moebius, Hergé — aplats nets, contours précis': 'Clear line, Moebius, Hergé — flat colors, precise outlines',
    'Cinéma de marque': 'Brand cinema',
    'Film réaliste premium — grain 35mm, noirs profonds, lumière dramatique maîtrisée. Entre auteur et haute publicité.': 'Premium realistic film — 35mm grain, deep blacks, controlled dramatic light. Between auteur and high-end advertising.',
    'Fusion créative — mêle live action et animation, réaliste et cartoon…': 'Creative fusion — blends live action and animation, realistic and cartoon…',

    # ── Lot 6 — messages de statut des workers (api/*) ──
    'Démultiplexage audio/vidéo…': 'Demuxing audio/video…',
    'Encodage de la photo de référence…': 'Encoding the reference photo…',
    'Génération du buste de référence…': 'Generating the reference bust…',
    'Génération des 4 vues corps entier en parallèle…': 'Generating the 4 full-body views in parallel…',
    'Génération NB2 Edit (~$0.08)…': 'NB2 Edit generation (~$0.08)…',
    'Téléchargement du portrait…': 'Downloading the portrait…',
    'Portrait généré ✓  (NB2 Edit · $0.08)': 'Portrait generated ✓  (NB2 Edit · $0.08)',
    'Portrait généré !': 'Portrait generated!',
    'Texture non extraite — prompt brut utilisé.': 'Texture not extracted — raw prompt used.',
    'Buste généré ✓ — upload comme ancre identité…': 'Bust generated ✓ — uploading as identity anchor…',
    "Analyse du style de l'image de référence…": 'Analyzing the reference image style…',
    'Ancre encodée — génération des 4 vues…': 'Anchor encoded — generating the 4 views…',
    '⚠ Encodage ancre échoué — utilisation photo originale.': '⚠ Anchor encoding failed — using the original photo.',
    "Analyse de fidélité de l'image de référence…": 'Analyzing the reference image fidelity…',
    'Chargement du casting et des éléments…': 'Loading the cast and elements…',
    'Phase 1 — ré-assignation des éléments par nom…': 'Phase 1 — reassigning elements by name…',
    'Phase 2 — préparation des données pour Claude Haiku…': 'Phase 2 — preparing the data for Claude Haiku…',
    'Application des résultats…': 'Applying the results…',
    'Synchronisation terminée': 'Synchronization complete',
    'Aucun prompt à synchroniser (aucun élément assigné avec description)': 'No prompt to synchronize (no assigned element with a description)',
    'Téléchargement du fichier audio…': 'Downloading the audio file…',
    "Upload de l'échantillon vocal…": 'Uploading the voice sample…',
    'Détourage du fond (BiRefNet)…': 'Removing background (BiRefNet)…',
    'Téléchargement du résultat…': 'Downloading the result…',
    'Voix clonée ✓  (~$0.002/s)': 'Voice cloned ✓  (~$0.002/s)',
    'Clonage vocal F5-TTS (détection langue auto)…': 'F5-TTS voice cloning (auto language detection)…',
    'Voix clonée ✓  (F5-TTS multilingue)': 'Voice cloned ✓  (F5-TTS multilingual)',
    "Téléchargement de l'ambiance…": 'Downloading the atmosphere…',
    'Téléchargement de la vidéo…': 'Downloading the video…',
    'Téléchargement…': 'Downloading…',
    'Téléchargement de la vidéo 4K…': 'Downloading the 4K video…',
    'Sora 2 — soumission (~$0.40 / vidéo)…': 'Sora 2 — submitting (~$0.40 / video)…',
    'Références visuelles détectées — mode Reference-to-Video…': 'Visual references detected — Reference-to-Video mode…',
    'Références détectées — mode Reference-to-Video PixVerse…': 'References detected — PixVerse Reference-to-Video mode…',

    # ── Lot 5 — guide de démarrage (dialog_onboarding) ──
    "PANDORA utilise deux services d'intelligence artificielle pour fonctionner. Ce guide va t'accompagner étape par étape pour les configurer — même si tu n'as jamais utilisé d'API auparavant.": "PANDORA uses two artificial intelligence services to work. This guide will walk you through configuring them step by step — even if you've never used an API before.",
    '💡  <b>Aucune clé requise pour essayer PANDORA</b> — le logiciel fonctionne en mode simulation sans clé. Tu peux explorer toutes les pages et revenir configurer les clés plus tard depuis <b>Paramètres</b>.': '💡  <b>No key required to try PANDORA</b> — the software runs in simulation mode without a key. You can explore all the pages and come back to configure the keys later from <b>Settings</b>.',
    'Clique sur le bouton ci-dessous pour ouvrir fal.ai dans ton navigateur.': 'Click the button below to open fal.ai in your browser.',
    'Clique sur <b>Sign Up</b> (en haut à droite) et crée ton compte avec ton e-mail.': 'Click <b>Sign Up</b> (top right) and create your account with your email.',
    "<b style='color:#c0c0d0'>fal.ai</b><span style='color:#555'>  ·  Create your account</span><br><br><span style='color:#888'>Email&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;</span> <span style='color:#ccc'>[ ton-email@exemple.com        ]</span><br><span style='color:#888'>Password&nbsp;</span> <span style='color:#ccc'>[ ••••••••••••••               ]</span>": "<b style='color:#c0c0d0'>fal.ai</b><span style='color:#555'>  ·  Create your account</span><br><br><span style='color:#888'>Email&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;</span> <span style='color:#ccc'>[ your-email@example.com        ]</span><br><span style='color:#888'>Password&nbsp;</span> <span style='color:#ccc'>[ ••••••••••••••               ]</span>",
    '🌐  Ouvrir fal.ai/signup →': '🌐  Open fal.ai/signup →',
    'Une fois connecté, clique sur ton avatar (en haut à droite) → <b>Dashboard</b>.': 'Once logged in, click your avatar (top right) → <b>Dashboard</b>.',
    'Dans le menu de gauche, clique sur <b>Keys</b>.': 'In the left menu, click <b>Keys</b>.',
    'Clique sur <b>+ Add key</b>, donne-lui le nom <b>PANDORA</b>, puis clique <b>Create</b>.': 'Click <b>+ Add key</b>, name it <b>PANDORA</b>, then click <b>Create</b>.',
    "<b style='color:#c0c0d0'>API Keys</b><br><br><span style='color:#888'>Aucune clé pour l'instant...</span>": "<b style='color:#c0c0d0'>API Keys</b><br><br><span style='color:#888'>No keys yet...</span>",
    '👆  Clique sur  [ + Add key ]  →  Nom : PANDORA  →  [ Create ]': '👆  Click  [ + Add key ]  →  Name: PANDORA  →  [ Create ]',
    "La clé générée ressemble à : <b>fal_key_xxxxxxxxxxxxxxxx</b><br>⚠️  Copie-la maintenant — elle ne sera affichée qu'une seule fois !": 'The generated key looks like: <b>fal_key_xxxxxxxxxxxxxxxx</b><br>⚠️  Copy it now — it will only be shown once!',
    "<b style='color:#c0c0d0'>API Keys</b><br><br><span style='color:#888'>PANDORA</span>": "<b style='color:#c0c0d0'>API Keys</b><br><br><span style='color:#888'>PANDORA</span>",
    '🔑  Ouvrir fal.ai/dashboard/keys →': '🔑  Open fal.ai/dashboard/keys →',
    'Dans le menu de gauche, clique sur <b>Billing</b>.': 'In the left menu, click <b>Billing</b>.',
    'Clique sur <b>Add credits</b> et ajoute <b>au minimum $10</b> pour bien démarrer.': 'Click <b>Add credits</b> and add <b>at least $10</b> to get started.',
    "<b style='color:#c0c0d0'>Billing</b><br><br><span style='color:#888'>Current balance :</span> <span style='color:#9C3FE4'>$0.00</span>": "<b style='color:#c0c0d0'>Billing</b><br><br><span style='color:#888'>Current balance :</span> <span style='color:#9C3FE4'>$0.00</span>",
    '💡  <b>Coût moyen :</b> environ $0.20–$0.50 par vidéo Seedance 2.0 (10 secondes). Avec $10, tu peux générer environ 20 à 50 vidéos.': '💡  <b>Average cost:</b> about $0.20–$0.50 per Seedance 2.0 video (10 seconds). With $10, you can generate roughly 20 to 50 videos.',
    '💳  Ouvrir fal.ai/dashboard/billing →': '💳  Open fal.ai/dashboard/billing →',
    'Anthropic — Claude IA': 'Anthropic — Claude AI',
    'Clique sur le bouton ci-dessous pour ouvrir la console Anthropic dans ton navigateur.': 'Click the button below to open the Anthropic console in your browser.',
    'Clique sur <b>Sign up</b> et crée ton compte avec ton e-mail ou ton compte Google.': 'Click <b>Sign up</b> and create your account with your email or your Google account.',
    "<b style='color:#c0c0d0'>Anthropic Console</b><br><br><span style='color:#888'>Welcome to Claude</span>": "<b style='color:#c0c0d0'>Anthropic Console</b><br><br><span style='color:#888'>Welcome to Claude</span>",
    '👆  Clique sur  [ Sign up ]  ou  [ Continue with Google ]': '👆  Click  [ Sign up ]  or  [ Continue with Google ]',
    '🌐  Ouvrir console.anthropic.com →': '🌐  Open console.anthropic.com →',
    'Une fois connecté, clique sur <b>Settings</b> dans le menu de gauche.': 'Once logged in, click <b>Settings</b> in the left menu.',
    'Dans Settings, clique sur <b>API Keys</b>.': 'In Settings, click <b>API Keys</b>.',
    'Clique sur <b>Create Key</b>, donne-lui le nom <b>PANDORA</b>, puis clique <b>Create Key</b>.': 'Click <b>Create Key</b>, name it <b>PANDORA</b>, then click <b>Create Key</b>.',
    "<b style='color:#c0c0d0'>Settings  ›  API Keys</b><br><br><span style='color:#888'>No API keys yet.</span>": "<b style='color:#c0c0d0'>Settings  ›  API Keys</b><br><br><span style='color:#888'>No API keys yet.</span>",
    '👆  Clique sur  [ Create Key ]  →  Nom : PANDORA  →  [ Create Key ]': '👆  Click  [ Create Key ]  →  Name: PANDORA  →  [ Create Key ]',
    "La clé générée ressemble à : <b>sk-ant-api03-xxxxxxxxxxxxxxxx</b><br>⚠️  Copie-la maintenant — elle ne sera affichée qu'une seule fois !": 'The generated key looks like: <b>sk-ant-api03-xxxxxxxxxxxxxxxx</b><br>⚠️  Copy it now — it will only be shown once!',
    "<b style='color:#c0c0d0'>API Keys</b><br><br><span style='color:#888'>PANDORA  ·  Créée maintenant</span>": "<b style='color:#c0c0d0'>API Keys</b><br><br><span style='color:#888'>PANDORA  ·  Just created</span>",
    '🔑  Ouvrir API Keys →': '🔑  Open API Keys →',
    'Dans Settings, clique sur <b>Billing</b>.': 'In Settings, click <b>Billing</b>.',
    'Clique sur <b>Add to credit balance</b> et ajoute <b>au minimum $5</b>.': 'Click <b>Add to credit balance</b> and add <b>at least $5</b>.',
    "<b style='color:#c0c0d0'>Billing</b><br><br><span style='color:#888'>Credit balance :</span> <span style='color:#7c3aed'>$0.00</span>": "<b style='color:#c0c0d0'>Billing</b><br><br><span style='color:#888'>Credit balance :</span> <span style='color:#7c3aed'>$0.00</span>",
    "💡  <b>Coût moyen :</b> environ $0.01–$0.05 par opération Claude (formatage, génération storyboard, extraction d'éléments). Avec $5, tu as des centaines d'opérations disponibles.": '💡  <b>Average cost:</b> about $0.01–$0.05 per Claude operation (formatting, storyboard generation, element extraction). With $5, you have hundreds of operations available.',
    '💳  Ouvrir Billing →': '💳  Open Billing →',
    "🔒  <b>VPN :</b> si Claude ne répond pas, désactivez votre VPN — certains serveurs VPN sont bloqués par l'API Anthropic.": '🔒  <b>VPN:</b> if Claude does not respond, disable your VPN — some VPN servers are blocked by the Anthropic API.',
    "Tu as maintenant tes deux clés API. Il ne reste plus qu'à les coller dans la page <b>Paramètres</b> de PANDORA.": "You now have your two API keys. All that's left is to paste them into PANDORA's <b>Settings</b> page.",
    "<b style='color:#c0c0d0'>Clé fal.ai</b><br><span style='color:#888'>[ fal_key_…</span><span style='color:#555'>                            ]</span><br><br><b style='color:#c0c0d0'>Clé Anthropic</b><br><span style='color:#888'>[ sk-ant-api03-…</span><span style='color:#555'>                     ]</span>": "<b style='color:#c0c0d0'>fal.ai key</b><br><span style='color:#888'>[ fal_key_…</span><span style='color:#555'>                            ]</span><br><br><b style='color:#c0c0d0'>Anthropic key</b><br><span style='color:#888'>[ sk-ant-api03-…</span><span style='color:#555'>                     ]</span>",
    'Colle ta clé <b>fal.ai</b> dans le champ « Clé fal.ai »': 'Paste your <b>fal.ai</b> key into the "fal.ai key" field',
    'Colle ta clé <b>Anthropic</b> dans le champ « Clé Anthropic »': 'Paste your <b>Anthropic</b> key into the "Anthropic key" field',
    "Clique sur <b>Enregistrer</b> — c'est tout !": "Click <b>Save</b> — that's it!",
    '✅  <b>Prêt à créer !</b> Une fois tes clés enregistrées, reviens sur la page <b>Scénario</b> pour commencer ton projet. Tu peux retrouver ce guide à tout moment depuis la page <b>Paramètres → Aide API</b>.': '✅  <b>Ready to create!</b> Once your keys are saved, go back to the <b>Screenplay</b> page to start your project. You can find this guide again at any time from <b>Settings → API Help</b>.',
    'Passer ✕': 'Skip ✕',
    'Suivant →': 'Next →',

    # ── Lot 4 — dialogues secondaires storyboard (Moods, version, analyse) ──
    '✦ Avant de générer les Moods': '✦ Before generating the Moods',
    'Pour un résultat optimal': 'For an optimal result',
    'Soigne le prompt Seedance': 'Polish the Seedance prompt',
    'Le Mood est avant tout un test de prompt et d\'ambiance. Plus le champ "Prompt Seedance" du plan est détaillé, plus l\'image générée sera représentative de ce que tu veux obtenir dans Seedance 2.0.': 'The Mood is above all a test of the prompt and the atmosphere. The more detailed the shot\'s "Seedance Prompt" field, the more the generated image will represent what you want to obtain in Seedance 2.0.',
    'Découpage technique complet': 'Complete technical breakdown',
    "Renseigne la valeur de plan, la focale, l'axe caméra, l'heure et le décor. Ces paramètres enrichissent automatiquement le prompt pour valider l'ambiance, l'éclairage et le cadrage avant de lancer Seedance 2.0.": 'Fill in the shot size, focal length, camera axis, time and location. These parameters automatically enrich the prompt to validate the atmosphere, lighting and framing before launching Seedance 2.0.',
    'Valider avant de générer la vidéo': 'Validate before generating the video',
    "Une fois les Moods satisfaisants, ils peuvent servir de base de discussion et de référence visuelle pour la génération Seedance 2.0. Ce n'est pas une pré-visualisation fidèle des personnages ou du décor.": 'Once the Moods are satisfactory, they can serve as a basis for discussion and a visual reference for Seedance 2.0 generation. It is not a faithful preview of the characters or the location.',
    'Génération rapide': 'Fast generation',
    "La génération batch traite les plans l'un après l'autre. Tu peux l'arrêter à tout moment — les Moods déjà générés sont conservés.": 'Batch generation processes the shots one after another. You can stop it at any time — the Moods already generated are kept.',
    '✦ Génération des Moods': '✦ Mood generation',
    'Génération automatique des Moods': 'Automatic Mood generation',
    'Sélectionne les plans pour lesquels générer un Mood. Les plans marqués ✓ ont déjà un Mood — ils sont décochés par défaut.': 'Select the shots to generate a Mood for. Shots marked ✓ already have a Mood — they are unchecked by default.',
    'Plans à générer :': 'Shots to generate:',
    'Nouvelle version': 'New version',
    'Nom de la nouvelle version :': 'New version name:',
    'Ex: Découpage final, Version action, Avant-projet…': 'E.g.: Final breakdown, Action version, Draft…',
    'Génération du storyboard': 'Storyboard generation',
    'Analyse du scénario via Claude IA': 'Analyzing the screenplay via Claude AI',
    'Génération du découpage en plans… Cette opération peut prendre quelques secondes.': 'Generating the shot breakdown… This may take a few seconds.',
    'Choisir un scénario': 'Choose a screenplay',
    'Sélectionne le scénario à analyser :': 'Select the screenplay to analyze:',

    # ── Lot 3 — guides complets de l'assistant (audit 2026-06) ──
    "Créer un projet\nCliquez sur '+ Nouveau projet', donnez un nom et choisissez l'emplacement. PANDORA crée automatiquement la structure de fichiers.\n\nOuvrir un projet existant\nCliquez sur un projet dans la liste. Toutes les pages se mettent à jour automatiquement avec les données du projet sélectionné.\n\nRenommer / supprimer\nAccédez à la fiche du projet pour renommer. La suppression retire le projet de la liste uniquement — vos fichiers restent sur le disque.\n\nOrganisation des données\nChaque projet stocke scénario, storyboard, castings, décors, accessoires, HMC, véhicules et clips générés dans son propre dossier.": "Create a project\nClick '+ New project', give it a name and choose the location. PANDORA automatically creates the file structure.\n\nOpen an existing project\nClick a project in the list. All pages update automatically with the selected project's data.\n\nRename / delete\nGo to the project record to rename. Deleting only removes the project from the list — your files stay on disk.\n\nData organization\nEach project stores its screenplay, storyboard, castings, locations, props, HMC, vehicles and generated clips in its own folder.",
    "Éditeur de scénario\nRédigez votre scénario directement dans l'éditeur. Vos modifications sont sauvegardées automatiquement. La barre du haut regroupe le choix du style visuel, la gestion des versions nommées (✚ ✕) et la durée du film.\n\nRéférences visuelles\nAjoutez des images dans '◎ Références visuelles' — photos de lieux, personnages, moodboards. '◈ Analyser avec Claude' analyse ces images et enrichit votre scénario en s'inspirant de leurs ambiances et détails.\n\nMise en page PANDORA\n'◈ Mise en page PANDORA' restructure votre texte en blocs plans lisibles par Seedance : en-têtes INT./EXT., titres de séquences, descriptions d'action. Format pensé pour la génération IA, pas pour le format Hollywood classique.\n\nCo-écriture avec Claude\n'⊞ Proposer un arrangement' ouvre le Studio de co-écriture. Ajustez l'intensité (1-10) pour des suggestions légères ou profondes. Claude ne touche que ce que vous lui demandez — le reste de votre texte est préservé. Vous pouvez joindre des images à vos messages pour guider les suggestions.\n\nGénérer depuis le scénario\nExtrayez automatiquement personnages, décors, accessoires, HMC, véhicules et storyboard depuis votre texte. Chaque extraction propose d'identifier uniquement ou de générer aussi les images de référence.": "Screenplay editor\nWrite your screenplay directly in the editor. Your changes are saved automatically. The top bar groups the visual style choice, named-version management (✚ ✕) and the film duration.\n\nVisual references\nAdd images in '◎ Visual references' — location photos, characters, moodboards. '◈ Analyze with Claude' analyzes these images and enriches your screenplay, drawing on their moods and details.\n\nPANDORA formatting\n'◈ PANDORA formatting' restructures your text into shot blocks readable by Seedance: INT./EXT. headers, sequence titles, action descriptions. A format designed for AI generation, not the classic Hollywood format.\n\nCo-writing with Claude\n'⊞ Suggest an arrangement' opens the co-writing Studio. Adjust the intensity (1-10) for light or deep suggestions. Claude only touches what you ask — the rest of your text is preserved. You can attach images to your messages to guide the suggestions.\n\nGenerate from the screenplay\nAutomatically extract characters, locations, props, HMC, vehicles and storyboard from your text. Each extraction offers to only identify, or to also generate the reference images.",
    "Le tableau de plans\nChaque ligne représente un plan de votre film. Vous y voyez d'un coup d'œil l'aperçu visuel, la séquence, le mouvement caméra, le décor, les personnages, la durée et le prompt de génération.\n\nÉditer un plan (double-clic)\nOuvrez la fiche complète pour renseigner : les choix caméra (mouvement, valeur de plan, focale, vitesse), les éléments du plan (décor, personnages, accessoires, véhicules), la mise en scène (placement caméra et acteurs, axe, entrée/sortie), la durée et le prompt de génération.\n\nSynchronisation\n'⟳ Synchronisation' met à jour tous les prompts si vous avez renommé des personnages, décors ou accessoires — vos descriptions restent cohérentes.\n\nAperçus visuels\nCliquez sur la colonne Mood d'un plan pour générer un aperçu visuel. '✦ Générer les Moods' traite tous les plans en une fois.\n\nGénération Seedance\nCliquez '▶' sur un plan pour lancer la génération. Si des personnages ou un décor sont assignés, leurs images sont automatiquement utilisées comme références visuelles pour plus de cohérence.\n\nVersions nommées\nSauvegardez des versions de votre découpage à chaque étape clé pour pouvoir revenir en arrière à tout moment.": "The shot table\nEach row represents a shot of your film. At a glance you see the visual preview, the sequence, the camera movement, the location, the characters, the duration and the generation prompt.\n\nEdit a shot (double-click)\nOpen the full record to fill in: camera choices (movement, shot size, focal length, speed), shot elements (location, characters, props, vehicles), staging (camera and actor placement, axis, entrance/exit), duration and generation prompt.\n\nSync\n'⟳ Sync' updates all prompts if you renamed characters, locations or props — your descriptions stay coherent.\n\nVisual previews\nClick a shot's Mood column to generate a visual preview. '✦ Generate Moods' processes all shots at once.\n\nSeedance generation\nClick '▶' on a shot to start generation. If characters or a location are assigned, their images are automatically used as visual references for more coherence.\n\nNamed versions\nSave versions of your breakdown at every key step so you can go back at any time.",
    "Créer un personnage\nCliquez '+ Ajouter'. Renseignez : nom, âge, rôle, description physique détaillée (cheveux, yeux, silhouette, traits distinctifs) et costume.\n\nGénérer un portrait\nDans la fiche, cliquez 'Générer portrait'. Nano Banana crée une image de référence. Plus la description physique est précise, plus le portrait sera fidèle au personnage imaginé.\n\nFiche 4 vues\nCliquez 'Générer fiche' pour obtenir face, 3/4, profil et dos. Cette fiche multi-vues donne à Seedance plus de cohérence sur plusieurs plans.\n\nAssigner à un plan\nDans le storyboard, ouvrez un plan et sélectionnez les personnages présents dans 'Éléments'. Les portraits assignés sont envoyés automatiquement comme images de référence à Seedance.\n\nStyle visuel\nChoisissez un style (cinéma, anime, photoréaliste…) pour orienter l'esthétique des portraits générés. Chaque personnage peut avoir son propre style.": "Create a character\nClick '+ Add'. Fill in: name, age, role, detailed physical description (hair, eyes, build, distinctive traits) and costume.\n\nGenerate a portrait\nIn the record, click 'Generate portrait'. Nano Banana creates a reference image. The more precise the physical description, the more faithful the portrait to your imagined character.\n\n4-view sheet\nClick 'Generate sheet' to get front, 3/4, profile and back. This multi-view sheet gives Seedance more coherence across shots.\n\nAssign to a shot\nIn the storyboard, open a shot and select the present characters in 'Elements'. Assigned portraits are automatically sent as reference images to Seedance.\n\nVisual style\nChoose a style (cinema, anime, photorealistic…) to guide the aesthetic of the generated portraits. Each character can have its own style.",
    "Créer un décor\nCliquez '+ Ajouter'. Renseignez : nom, type (INT./EXT.), description détaillée (architecture, lumière, ambiance, époque, éléments présents).\n\nGénérer l'image de référence\nCliquez 'Générer image' pour créer une référence visuelle via Nano Banana. Soyez précis sur l'ambiance, la lumière et les détails architecturaux.\n\nSheet 4 vues\nGénère quatre angles du décor (entrée, milieu, fond, détail). Utile pour les scènes complexes avec plusieurs axes caméra.\n\nStyle d'image\nChaque décor peut avoir son propre style (cinéma noir et blanc, photoréaliste, aquarelle…) indépendamment du style global du projet.\n\nAssigner à un plan\nDans l'édition d'un plan storyboard, choisissez le décor dans 'Éléments'. Son image est envoyée automatiquement comme référence visuelle à Seedance.": "Create a location\nClick '+ Add'. Fill in: name, type (INT./EXT.), detailed description (architecture, light, mood, era, present elements).\n\nGenerate the reference image\nClick 'Generate image' to create a visual reference via Nano Banana. Be precise about the mood, the light and the architectural details.\n\n4-view sheet\nGenerates four angles of the location (entrance, middle, background, detail). Useful for complex scenes with several camera axes.\n\nImage style\nEach location can have its own style (black-and-white cinema, photorealistic, watercolor…) independently of the project's global style.\n\nAssign to a shot\nWhen editing a storyboard shot, choose the location in 'Elements'. Its image is automatically sent as a visual reference to Seedance.",
    "Créer un accessoire\nDécrivez précisément l'objet : type, matière, couleur, état (neuf, abîmé, vintage), époque et contexte d'utilisation. Plus la description est précise, plus la génération sera fidèle.\n\nGénérer l'image\nCliquez 'Générer image' pour créer une référence visuelle de l'accessoire. Utilisez 'Générer une variation' pour explorer d'autres interprétations.\n\nNombre de générations\nChoisissez combien d'images générer en une fois. Naviguez entre les résultats avec les flèches du panneau de prévisualisation.\n\nAssigner à un plan\nDans l'édition d'un plan, section 'Éléments', sélectionnez les accessoires présents. Leurs images sont envoyées à Seedance comme références visuelles.": "Create a prop\nDescribe the object precisely: type, material, color, condition (new, worn, vintage), era and use context. The more precise the description, the more faithful the generation.\n\nGenerate the image\nClick 'Generate image' to create a visual reference of the prop. Use 'Generate a variation' to explore other interpretations.\n\nNumber of generations\nChoose how many images to generate at once. Navigate between the results with the arrows in the preview panel.\n\nAssign to a shot\nWhen editing a shot, in the 'Elements' section, select the present props. Their images are sent to Seedance as visual references.",
    "Rôle du HMC\nLe HMC documente les éléments visuels portés par les personnages : vêtements, accessoires de mode, maquillage, coiffure. Indispensable pour la continuité entre les plans et les jours de tournage.\n\nCréer un élément HMC\nRenseignez : type (costume, maquillage, coiffure, bijou…), nom, description détaillée et le personnage associé.\n\nImage de référence\nGénérez une image via Nano Banana pour visualiser l'élément. Ces images peuvent être partagées avec l'équipe costume/maquillage.\n\nStyle d'image\nChoisissez un style adapté : 'Photoréaliste' pour un rendu proche du réel, 'Fashion plate' pour un rendu costume de théâtre.": "Role of HMC\nHMC documents the visual elements worn by the characters: clothing, fashion accessories, makeup, hair. Essential for continuity between shots and shooting days.\n\nCreate an HMC item\nFill in: type (costume, makeup, hair, jewelry…), name, detailed description and the associated character.\n\nReference image\nGenerate an image via Nano Banana to visualize the item. These images can be shared with the costume/makeup team.\n\nImage style\nChoose a suitable style: 'Photorealistic' for a true-to-life render, 'Fashion plate' for a theatrical-costume render.",
    "Créer un véhicule\nRenseignez : marque, modèle, année, couleur, état (neuf, vieilli, modifié, accidenté) et toute particularité visuelle (autocollants, rouille, modification de carrosserie).\n\nImage de référence\nNano Banana génère le véhicule sur fond neutre. Pour les véhicules historiques ou fictifs, la description est particulièrement importante.\n\nAssigner à un plan\nDans l'édition d'un plan storyboard, sélectionnez le(s) véhicule(s) présent(s). Leurs images sont envoyées à Seedance comme références visuelles.\n\nCohérence entre plans\nEn assignant le même véhicule à plusieurs plans, vous garantissez une cohérence visuelle dans les séquences de poursuite ou de déplacement.": 'Create a vehicle\nFill in: brand, model, year, color, condition (new, aged, modified, damaged) and any visual particularity (stickers, rust, bodywork modification).\n\nReference image\nNano Banana generates the vehicle on a neutral background. For historical or fictional vehicles, the description is particularly important.\n\nAssign to a shot\nWhen editing a storyboard shot, select the present vehicle(s). Their images are sent to Seedance as visual references.\n\nCoherence across shots\nBy assigning the same vehicle to several shots, you ensure visual coherence in chase or travel sequences.',
    "Caméra et capteur\nChoisissez votre caméra principale (ARRI, RED, Sony, Canon…) et le format de capteur. Ces informations pré-remplissent les champs techniques du storyboard.\n\nOptiques\nRenseignez la série d'optiques (Cooke, Leica, Zeiss, Master Prime…) et les focales disponibles. Le storyboard proposera ces focales dans ses menus.\n\nFormat d'image\nDéfinissez le ratio : 1.33:1 (plein cadre), 1.78:1 (16:9), 1.85:1 (flat), 2.39:1 (scope). S'applique à la génération Seedance et à l'export.\n\nChaîne son\nDocumentez micros, perches, enregistreurs. Ces notes préparent la coordination avec le chef opérateur son.": "Camera and sensor\nChoose your main camera (ARRI, RED, Sony, Canon…) and the sensor format. This information pre-fills the storyboard's technical fields.\n\nOptics\nEnter the optics series (Cooke, Leica, Zeiss, Master Prime…) and the available focal lengths. The storyboard will offer these focal lengths in its menus.\n\nImage format\nSet the ratio: 1.33:1 (full frame), 1.78:1 (16:9), 1.85:1 (flat), 2.39:1 (scope). Applies to Seedance generation and export.\n\nSound chain\nDocument mics, boom poles, recorders. These notes prepare coordination with the sound recordist.",
    "Moteurs disponibles\n— ElevenLabs Turbo v2.5 : synthèse vocale de haute qualité avec sélection de voix préenregistrées (anglais, français et plus). Service payant, clé API requise.\n— F5-TTS Clonage : clone une voix depuis un échantillon audio de quelques secondes. Entraîné principalement sur l'anglais et le chinois — le français peut avoir un léger accent.\n\nWorkflow recommandé\n1. Écrivez le texte à doubler dans l'éditeur.\n2. Choisissez un moteur : ElevenLabs pour la qualité FR, F5-TTS pour reproduire une voix spécifique.\n3. Générez et écoutez le rendu.\n4. Importez dans DaVinci Resolve pour synchroniser avec la vidéo.\n\nDétourage automatique\nSupprimez le fond d'une image ou d'une vidéo automatiquement pour créer des fonds transparents, sans avoir besoin de fond vert.": 'Available engines\n— ElevenLabs Turbo v2.5: high-quality voice synthesis with a selection of pre-recorded voices (English, French and more). Paid service, API key required.\n— F5-TTS Cloning: clones a voice from a few-second audio sample. Trained mainly on English and Chinese — French may have a slight accent.\n\nRecommended workflow\n1. Write the text to dub in the editor.\n2. Choose an engine: ElevenLabs for FR quality, F5-TTS to reproduce a specific voice.\n3. Generate and listen to the result.\n4. Import into DaVinci Resolve to sync with the video.\n\nAutomatic background removal\nRemove the background of an image or video automatically to create transparent backgrounds, without needing a green screen.',
    "Générer depuis Storyboard\nSélectionnez un plan et cliquez '▶▶ Lancer'. Le prompt du plan est utilisé, traduit en anglais, et les références (personnages, décor) sont envoyées automatiquement. Quand des références visuelles sont disponibles, elles guident Seedance pour une cohérence visuelle accrue.\n\nModifier des clips\nImportez des clips existants et modifiez-les avec un prompt. Seedance applique la modification en préservant la structure visuelle. LatentSync resynchronise les lèvres sur une nouvelle piste audio.\n\nGénération directe\nAccès aux 13 moteurs (Seedance, Happy Horse, Kling, Veo 3.1, PixVerse, Sora 2…) avec leurs paramètres et tarifs spécifiques.\n\nVidéothèque\nGalerie de tous les clips générés pour ce projet. Cliquez sur un clip pour le prévisualiser, l'envoyer dans 'Modifier des clips', ou l'ouvrir.\n\nTarifs\nLa génération est facturée via fal.ai. Seedance 2.0 est le moteur recommandé pour la cohérence visuelle. Consultez le Manuel pour le comparatif des tarifs par moteur.": "Generate from Storyboard\nSelect a shot and click '▶▶ Launch'. The shot's prompt is used, translated to English, and the references (characters, location) are sent automatically. When visual references are available, they guide Seedance for increased visual coherence.\n\nEdit clips\nImport existing clips and modify them with a prompt. Seedance applies the change while preserving the visual structure. LatentSync re-syncs the lips to a new audio track.\n\nDirect generation\nAccess to the 13 engines (Seedance, Happy Horse, Kling, Veo 3.1, PixVerse, Sora 2…) with their specific parameters and pricing.\n\nVideo library\nGallery of all clips generated for this project. Click a clip to preview it, send it to 'Edit clips', or open it.\n\nPricing\nGeneration is billed via fal.ai. Seedance 2.0 is the recommended engine for visual coherence. See the Manual for the per-engine pricing comparison.",
    "Clé fal.ai\nCréez un compte sur fal.ai et générez une clé API dans votre tableau de bord. Donne accès à tous les moteurs vidéo (Seedance, Kling, Veo, PixVerse, Sora, Wan…) et aux modèles d'image (Flux).\n\nClé Anthropic\nCréez un compte sur console.anthropic.com. Utilisée pour : formatage du scénario, génération du storyboard, traduction des prompts, et l'assistant pédagogique.\n\nClé Nano Banana\nDédiée à la génération de portraits de personnages et d'images d'éléments (décors, accessoires, HMC, véhicules).\n\nDossier de sortie\nChoisissez où vos vidéos générées seront enregistrées. Par défaut, elles sont sauvegardées dans votre dossier Vidéos, sous-dossier PANDORA. Vous pouvez rediriger vers votre NAS ou dossier de projet DaVinci.\n\nMode sans clé\nSans clé fal.ai, PANDORA fonctionne en mode démonstration — les générations sont simulées sans consommation de crédits, pour découvrir l'interface.": 'fal.ai key\nCreate an account on fal.ai and generate an API key in your dashboard. Gives access to all video engines (Seedance, Kling, Veo, PixVerse, Sora, Wan…) and image models (Flux).\n\nAnthropic key\nCreate an account on console.anthropic.com. Used for: screenplay formatting, storyboard generation, prompt translation, and the learning assistant.\n\nNano Banana key\nDedicated to generating character portraits and element images (locations, props, HMC, vehicles).\n\nOutput folder\nChoose where your generated videos will be saved. By default they are saved in your Videos folder, PANDORA subfolder. You can redirect to your NAS or DaVinci project folder.\n\nKey-free mode\nWithout a fal.ai key, PANDORA runs in demo mode — generations are simulated without consuming credits, to explore the interface.',
    "Bienvenue dans PANDORA\nPANDORA est un outil de pré-production cinéma intégré à DaVinci Resolve. Il couvre l'ensemble du pipeline de pré-production : scénario, storyboard, castings, décors, accessoires, HMC, véhicules et génération vidéo IA.\n\nDémarrage rapide\n1. Créez ou ouvrez un projet depuis la page Projets.\n2. Rédigez votre scénario et utilisez Claude IA pour le formater.\n3. Générez le storyboard depuis le scénario.\n4. Ajoutez personnages, décors et accessoires avec images de référence.\n5. Générez vos clips vidéo depuis Studio IA.": 'Welcome to PANDORA\nPANDORA is a cinema pre-production tool integrated into DaVinci Resolve. It covers the entire pre-production pipeline: screenplay, storyboard, castings, locations, props, HMC, vehicles and AI video generation.\n\nQuick start\n1. Create or open a project from the Projects page.\n2. Write your screenplay and use Claude AI to format it.\n3. Generate the storyboard from the screenplay.\n4. Add characters, locations and props with reference images.\n5. Generate your video clips from AI Studio.',
}


# ── API publique ───────────────────────────────────────────────────────────────

def tr(key: str) -> str:
    """Retourne la chaîne traduite dans la langue courante (fallback FR)."""
    entry = _T.get(key, {})
    return entry.get(_LANG, entry.get("fr", key))


def translate(text: str) -> str:
    """Traduit une chaîne FR directe dans la langue courante.
    Retourne le texte inchangé si pas de traduction ou si langue = FR.

    Les libellés mentionnant l'assistant IA (« Claude ») sont automatiquement
    rebaptisés au nom de l'assistant actif (Fable 5, Mistral, Ollama…) via
    core.ai_provider.brand — « Analyser avec Claude » → « Analyser avec Mistral »."""
    if not text:
        return text
    out = text if _LANG == "fr" else _FR_TO_EN.get(text, text)
    if "Claude" in out:
        try:
            from core.ai_provider import brand
            out = brand(out)
        except Exception:
            pass
    return out


_EN_TO_FR: dict[str, str] | None = None


def to_source(text: str) -> str:
    """Inverse de translate() : convertit une valeur affichée (EN) vers sa clé FR.

    Sert à récupérer la valeur canonique française à enregistrer quand un widget
    (QComboBox traduit par retranslate_widget) renvoie son texte traduit.
    Retourne le texte inchangé si langue = FR ou si aucune correspondance
    (valeurs libres saisies par l'utilisateur, valeurs déjà françaises, etc.)."""
    global _EN_TO_FR
    if _LANG == "fr" or not text:
        return text
    if _EN_TO_FR is None:
        _EN_TO_FR = {en: fr for fr, en in _FR_TO_EN.items()}
    return _EN_TO_FR.get(text, text)


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
