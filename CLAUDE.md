# CLAUDE.md — Pandora × Seedance 2.0

# BOUCLE DE TRAVAIL — auto-vérification et auto-correction (à appliquer systématiquement)

> Directive permanente pour Claude Code sur PANDORA. S'applique à CHAQUE tâche de code,
> sans qu'on ait à la redemander. Objectif : ne jamais rendre la main sur un travail non
> vérifié. Travailler comme un ingénieur qui relit, teste, REGARDE et corrige son propre
> code avant de le livrer — la rigueur d'auto-vérification, pas la précipitation.

## 1. AVANT d'agir — planifier
- Reformuler la tâche en une phrase pour confirmer la compréhension.
- Décomposer en étapes explicites. Si une étape est ambiguë ou entre en conflit avec
  une règle du projet, DEMANDER avant de coder — ne pas supposer.
- Identifier les fichiers concernés ET le périmètre : Cinéma OU Live (jamais les deux
  par erreur — voir séparation ci-dessous).
- Vérifier le contexte de session AVANT de lire des fichiers : si une donnée a déjà été
  produite/affichée dans la conversation courante, l'utiliser directement (ne pas relire
  les JSON pour la retrouver).

## 2. PENDANT — coder par petits incréments
- Une modification cohérente à la fois, pas un gros bloc non vérifiable.
- Après chaque modification, RELIRE son propre diff comme le code d'un autre : fautes,
  imports manquants, effets de bord, régressions.
- Architecture modulaire : toute nouvelle fonctionnalité = nouveau fichier/module dédié.
  Jamais de code monolithique.

## 3. APRÈS chaque modification — VÉRIFIER (obligatoire, jamais sauté)
- Compiler : `python -c "import compileall; compileall.compile_dir('.')"`.
- Test headless : instancier la fenêtre/page concernée dans un QApplication et imprimer
  un état. JAMAIS relancer l'app de façon interactive (`pythonw main.py`) sauf demande
  explicite de l'utilisateur (règle stricte : il reste maître du lancement).
- Lancer les harnais pertinents : `tools/test_cinema.py` + `tools/test_live.py` + le
  RADAR de divergence Cinéma/Live. Un harnais rouge ou une divergence non assumée =
  CORRIGER avant de continuer. Ne jamais rendre la main sur un harnais rouge.

## 4. VÉRIFICATION VISUELLE — quand le rendu UI compte
- Pour toute modification d'apparence (layout, couleurs, position, nouveau widget) :
  produire un RENDU HEADLESS en image (`widget.grab()` → PNG, ou rendu offscreen), PUIS
  RELIRE ce PNG pour juger le résultat visuel réel.
- Cette capture hors-écran NE viole PAS « pas de relance auto » : aucune fenêtre
  interactive n'est ouverte. C'est la façon de « voir » son travail sans lancer l'app.
- Critiquer le rendu : alignements, marges, lisibilité, cohérence, ET conformité couleurs
  (voir doctrine couleurs). Si insatisfaisant : corriger et re-rendre, en boucle, AVANT de
  livrer.

## 5. AUTO-CRITIQUE — avant de rendre la main
Se poser explicitement, à chaque fin de tâche :
- « Qu'est-ce qui pourrait être cassé que je n'ai pas testé ? »
- « Ai-je introduit une régression dans l'autre page / l'autre module (Cinéma↔Live) ? »
- « Le texte UI ajouté est-il traduit FR + EN dans _FR_TO_EN ? »
- « Un test a-t-il pu toucher la vraie config / les vraies clés ? »
- « Ai-je respecté toutes les doctrines techniques ci-dessous ? »
Si un doute subsiste, le VÉRIFIER, ne pas l'ignorer.

## 6. RENDRE LA MAIN — rapport de vérification
- Ne pas dire seulement « c'est fait ». Dire « c'est fait ET voici ce que j'ai vérifié » :
  harnais passés (chiffres Cinéma/Live/radar), rendu visuel contrôlé, points restants.
- Signaler honnêtement tout ce qui n'a PAS pu être vérifié.
- Références temporelles NEUTRES (« plus tôt dans la session », « il y a quelques
  commits ») — jamais « ce matin/ce soir » sans vérifier `Get-Date`. Dates absolues dans
  les mémoires/devlog.

---

## GARDE-FOUS — la boucle d'autonomie ne doit JAMAIS les violer

L'auto-vérification autorise à RELIRE, TESTER, RENDRE EN IMAGE et CORRIGER. Elle
n'autorise PAS à franchir les limites suivantes, qui priment sur tout :

### Git / publication
- **Jamais** `git push`, `git reset --hard`, `git clean`, `rm`, `Remove-Item`, ni
  publication `gh` sans demande explicite. Commit + `git add` locaux OK.
  (Le garde-fou `.claude/settings.local.json` `permissions.ask` le fait redemander —
  ne JAMAIS remettre `bypassPermissions`.)
- **Build / push = Cinéma UNIQUEMENT.** Ne jamais embarquer le Live. Le `main` local
  CONTIENT le Live → ne PAS faire un simple `git push origin main`. Pousser = cherry-pick
  / branche basée sur `origin/main` (0ca8a99), diff vérifié SANS aucun fichier ni
  plomberie Live. **RAPPELER ce point proactivement au prochain push Cinéma.**
- **Jamais `git push --tags`** : les tags locaux pointent sur d'anciens SHAs d'avant
  réécriture d'historique → restaurerait le Live public.
- Fichiers de contexte Claude (PANDORA_CONTEXT/COMMS/DEVLOG) = locaux, gitignorés,
  jamais poussés.

### Tests / config (CRITIQUE — risque aggravé par une boucle d'auto-test renforcée)
- **Ne JAMAIS écrire dans le vrai `data/config.json` pendant un test.** Il contient les
  clés API réelles ET les préférences IA (`ai_provider`, `ai_model_creative`,
  `ai_task_engines`) ; il est gitignoré donc NON restaurable. Un test de `save_config()`
  l'a déjà corrompu (incident 2026-06-18 : `ai_provider="mistral"` laissé en place).
- Tout test touchant la config DOIT l'isoler : monkeypatch `load_config`/`save_config`,
  OU `_ROOT` sur dossier temporaire, OU lire→sauver en variable→restaurer en `finally`.
  Jamais `save_config()` sur la vraie config dans un script jetable.
- Pièges packaging à revérifier à CHAQUE build : déclarer `studio_images/` dans
  `pandora.spec` (pathex + hiddenimports) ; ne JAMAIS bundler `studio_images/config.json`
  ni `refs/` (vraies clés) ; ne pas exclure `api.tts`/`api.upscale` du build Cinéma
  (partagés Sound Design + Upscaling).

### Séparation Cinéma / Live (ABSOLUE)
- Modifier le Live = éditer uniquement les copies `*_live.py` / `live_window.py` / etc.
  Modifier le Cinéma = fichiers d'origine. Ne JAMAIS toucher l'autre côté par effet de
  bord. Le radar de divergence vérifie l'alignement — le garder à 0.
- `librosa` = build Live uniquement (+250 Mo) — jamais dans le requirements/build Cinéma.

### Threads / workers PyQt6 (anti-crash, causes de segfaults C réels)
- Signaux workers = `done` (JAMAIS `finished` — masque le signal natif QThread).
- **JAMAIS `QThread.terminate()`** → état Qt/Python corrompu → segfault sur le worker
  suivant. Toujours `core.worker.abandon_thread(w)` (blockSignals + requestInterruption +
  quit + référence anti-GC).
- Dans les chaînes de file (`_process_next_*`), PARQUER le worker précédent
  (`abandon_thread`) AVANT de réassigner `self._worker` — sinon la file s'arrête au 1er
  élément. Jamais `worker_ref = None` à chaud.
- Toute exception non gérée dans un slot/handler PyQt6 fait ABORT toute l'app → try/except
  dans les handlers ; garder le filet `sys.excepthook` + `faulthandler` de `main.py`.

### UI / style
- `disable_default_buttons(dlg)` sur toute fenêtre champ + boutons (sinon Entrée
  déclenche Annuler/Appliquer).
- Fond = `PANDORA_STYLESHEET`, CP['bg1'] = #0c0e1a (bleu-violet), JAMAIS noir #000000.
- JAMAIS de suffixe hex-opacity (`{color}12/33/44`) sur fond sombre (rend « vert caca de
  bois ») → style outline (`border: 1px solid {accent}`, fond transparent) ou `rgba()`
  explicite.
- Listes de lignes dynamiques → toujours dans une zone scrollable bornée.
- Plafonds anti-troncature : sortie complète = 16000 tokens ; chat/synthèse = 8192.

### i18n
- Tout texte UI ajouté = traduit FR + EN dans `core/i18n.py → _FR_TO_EN`. Exceptions :
  systèmes bilingues dédiés (manuel `_BUILDERS_EN`, gros blocs « guide » assistant) — ne
  PAS les mettre dans `_FR_TO_EN`.

### Mapping (Live)
- Critère de confinement façade = VISIBILITÉ sur la photo de référence, JAMAIS une liste
  noire d'éléments. Le harnais vérifie l'absence de liste noire dans `_SYSTEM_MAPPING`.

## Esprit de la directive
La vitesse vient de la fiabilité, pas de la précipitation : une tâche vérifiée et juste
vaut mieux que trois tâches rendues vite et fausses. Le but n'est pas que l'outil fasse
plus à la place de Matthieu, mais qu'il produise un travail juste, vérifié et cohérent
avec un projet qu'il maîtrise.

---

## Vue d'ensemble

**Pandora** est un plugin de pré-production cinéma pour DaVinci Resolve. Il permet de gérer l'intégralité de la pré-production (scénario, storyboard, casting, décors, accessoires, HMC, véhicules, image & son) et de générer des vidéos IA via Seedance 2.0 (ByteDance/fal.ai) directement depuis l'interface de montage.

---

## Stack technique

- **Langage** : Python 3.14+
- **UI** : PyQt6 (thème sombre, style DaVinci Resolve)
- **API vidéo** : Seedance 2.0 via fal.ai (`fal-client`) — bascule auto mock ↔ réel selon la clé
- **API portraits** : Nano Banana — génération de portraits de personnages et d'éléments (mock/réel)
- **IA textuelle** : Claude API (Anthropic) — Haiku pour traduction/formatage, Sonnet pour génération storyboard JSON
- **Intégration DaVinci** : DaVinci Resolve Scripting API (Python)
- **Stockage local** : JSON par projet + dossier global PANDORA/

### Dépendances
```
PyQt6>=6.11.0
anthropic          # Claude API (traduction, scénario, storyboard)
fal-client         # Seedance 2.0 (activé si api_key présent)
requests           # fallback HTTP
Pillow             # preview images
```

---

## Comment lancer

```powershell
C:\Users\22eme\AppData\Local\Python\pythoncore-3.14-64\python.exe main.py
```

> Utiliser ce Python spécifique — c'est celui où PyQt6 et anthropic sont installés.

---

## Architecture du projet

```
pandora/
├── CLAUDE.md
├── main.py                    # Point d'entrée — QApplication, splash, palette
│
├── core/                      # Logique métier (aucune dépendance UI)
│   ├── config.py              # Lecture/écriture config.json (clés API, préférences)
│   ├── version.py             # VERSION = "1.0.0" + GITHUB_RELEASES_URL (update check)
│   ├── paths.py               # APP_ROOT — résout dev vs. PyInstaller frozen (centralise _ROOT)
│   ├── context.py             # État global du projet en cours (project_id, project_path)
│   ├── pandora_dirs.py        # Structure de dossiers ~/Videos/PANDORA/
│   ├── project.py             # CRUD projets (index.json)
│   ├── scenario.py            # CRUD scénarios par projet
│   ├── storyboard.py          # CRUD plans storyboard + constantes caméra
│   ├── casting.py             # CRUD personnages
│   ├── decors.py              # CRUD décors
│   ├── accessories.py         # CRUD accessoires
│   ├── hmc.py                 # CRUD HMC (Habillage, Maquillage, Coiffure)
│   ├── vehicles.py            # CRUD véhicules
│   ├── history.py             # Historique générations Seedance (50 entrées max)
│   ├── worker.py              # GenerationWorker — bascule mock/réel auto
│   ├── lang.py                # Traduction prompt → anglais/chinois via Claude Haiku
│   ├── i18n.py                # Système de traduction FR↔EN de l'interface
│   ├── migration.py           # Migration données JSON entre versions
│   ├── camera_prefs.py        # Préférences caméra par projet
│   ├── camera_data.py         # Données référentielles caméra/optique
│   ├── style.py               # Styles visuels (film styles, palettes) + STYLES/GROUPS
│   ├── mosaic.py              # Génération mosaïques d'images (build_ref_mosaics)
│   └── video_utils.py         # Utilitaires vidéo
│
├── api/                       # Appels réseau — toujours dans QThread
│   ├── mock.py                # Simulation Seedance (run_mock)
│   ├── real.py                # Vrai appel fal-client (run_real) + bascule T2V→REF auto
│   ├── screenplay.py          # Workers Claude pour scénario et storyboard
│   ├── nano_banana.py         # Workers Nano Banana (portraits + sheets éléments)
│   ├── enhance.py             # Optimisation de prompts via Claude
│   ├── update_check.py        # UpdateCheckWorker — vérification GitHub Releases au démarrage
│   ├── apercu.py              # Workers Flux T2I — génération de moods/aperçus pour le storyboard
│   ├── tts.py                 # Workers Kokoro TTS (synthèse vocale) + BiRefNet (détourage) — page Doublage
│   └── video_engines.py       # Workers Kling v3 Pro + PixVerse v4.5 — moteurs vidéo alternatifs
│
├── ui/                        # Composants PyQt6
│   ├── styles.py              # CP (palette couleurs) + PANDORA_STYLESHEET
│   ├── icons.py               # Chargement icônes PNG + colorisation
│   ├── widgets.py             # Composants réutilisables
│   ├── creative_panel.py      # NanaBananaControlsPanel — contrôles créatifs partagés
│   ├── splash.py              # SplashWindow — sélection/création de projet
│   ├── pandora_window.py      # PandoraWindow — fenêtre principale + nav latérale
│   ├── seedance_widget.py     # SeedanceWidget — conteneur onglets AI Studio
│   ├── davinci_panel.py       # Panneau intégration DaVinci
│   │
│   ├── tab_t2v.py             # Onglet Text-to-Video (+ envoi refs auto)
│   ├── tab_i2v.py             # Onglet Image-to-Video
│   ├── tab_extension.py       # Onglet Extension de clip
│   ├── tab_reference.py       # Onglet Référence multimodale
│   ├── tab_settings.py        # Onglet Paramètres AI Studio
│   ├── tab_video_engines.py   # Onglet moteurs vidéo (multi-modèles)
│   ├── tab_history.py         # Onglet Historique des générations
│   │
│   ├── page_projects.py       # Page Projets
│   ├── page_scenario.py       # Page Scénario — éditeur + Claude IA + versions
│   ├── page_storyboard.py     # Page Storyboard — grille de plans
│   ├── page_castings.py       # Page Castings — liste personnages
│   ├── page_decors.py         # Page Décors
│   ├── page_accessories.py    # Page Accessoires
│   ├── page_hmc.py            # Page HMC
│   ├── page_vehicles.py       # Page Véhicules
│   ├── page_camera.py         # Page Image & Son
│   ├── page_settings.py       # Page Paramètres (clés API, dossier sortie)
│   ├── page_style.py          # Page Style visuel du film
│   ├── page_doublage.py       # Page Doublage
│   ├── page_stub.py           # Page placeholder (pages non encore implémentées)
│   │
│   ├── dialog_shot.py         # Dialogue édition d'un plan storyboard
│   ├── dialog_character.py    # Dialogue édition d'un personnage
│   ├── dialog_decor.py        # Dialogue édition d'un décor (+ style + variation)
│   ├── dialog_accessory.py    # Dialogue édition d'un accessoire (+ style + variation)
│   ├── dialog_hmc.py          # Dialogue édition HMC (+ style + variation)
│   ├── dialog_vehicle.py      # Dialogue édition véhicule (+ style + variation)
│   ├── dialog_user_manual.py  # Manuel d'utilisation bilingue FR/EN
│   ├── dialog_gallery.py      # Galerie d'images
│   ├── dialog_assign.py       # Dialogue assignation d'éléments
│   ├── dialog_arrange_session.py  # Session d'arrangement du scénario
│   ├── dialog_apercu.py       # MoodDialog — génération et sélection d'aperçus storyboard (Flux)
│   ├── dialog_portrait_result.py  # Résultat génération portrait
│   ├── dialog_style_gallery.py    # StyleGalleryDialog — sélection de template de style pour T2V
│   ├── dialog_contact.py      # Dialogue contact
│   ├── dialog_funding.py      # Dialogue financement
│   ├── dialog_api_help.py     # Aide configuration API
│   └── dialog_davinci_help.py # Aide intégration DaVinci
│
├── davinci/                   # Pont DaVinci Resolve
│   ├── bridge.py              # Connexion DaVinci Resolve Scripting API
│   ├── bridge_server.py       # Serveur bridge (communication inter-process)
│   ├── importer.py            # Import automatique dans le Media Pool
│   └── timeline.py            # Lecture des clips de la timeline
│
├── tools/                     # Scripts utilitaires standalone
│   └── translate_storyboard_prompts.py  # Migration/traduction prompts storyboard
│
└── data/                      # Généré automatiquement
    ├── config.json            # Clés API + préférences globales (JAMAIS commité/distribué)
    ├── config.clean.json      # Template vierge utilisé par le build PyInstaller
    └── {scenarios,storyboard,castings,decors,...}/  # Données par projet ou global
```

---

## Navigation de l'application

La barre latérale gauche de `PandoraWindow` contient 11 pages :

| Icône | Page | Fichier |
|-------|------|---------|
| Projets | Sélection/création de projets | `page_projects.py` |
| Scénario | Éditeur scénario + Claude IA | `page_scenario.py` |
| Storyboard | Grille de plans + génération IA | `page_storyboard.py` |
| Castings | Personnages + portraits Nano Banana | `page_castings.py` |
| Décors | Lieux de tournage | `page_decors.py` |
| Accessoires | Props / accessoires | `page_accessories.py` |
| HMC | Habillage, Maquillage, Coiffure | `page_hmc.py` |
| Véhicules | Véhicules du film | `page_vehicles.py` |
| Image & Son | Préférences caméra/son | `page_camera.py` |
| AI Studio | Génération vidéo IA (Seedance 2.0) | `seedance_widget.py` + `tab_*.py` |
| Paramètres | Clés API, dossier sortie | `page_settings.py` |

---

## Flux de démarrage

```
main.py
  └── SplashWindow (sélection ou création de projet)
        └── project_selected → PandoraWindow(data)
              ├── core.context.set_project_id / set_project_path
              └── Toutes les pages chargent leurs données via core.context.get_data_root()
```

---

## Stockage des données

### Par projet
Chaque projet a son propre dossier. Le chemin est dans `core.context`:
```
<projet>/data/
  ├── scenarios/index.json
  ├── storyboard/{default.json, versions...}
  ├── castings/index.json + images/
  ├── decors/index.json + images/
  ├── accessories/index.json + images/
  ├── hmc/index.json + images/
  ├── vehicles/index.json + images/
  └── Seedance/            # Clips générés pour ce projet
```

### Global (sans projet ouvert)
```
~/Videos/PANDORA/
  ├── Castings/
  ├── Scénario/
  ├── Storyboard/
  ├── Décors/
  ├── HMC/
  ├── Accessoires/
  ├── Véhicules/
  └── Seedance 2.0/        # Clips générés hors projet
```

### Config globale
```
data/config.json
{
  "api_key":               "",   # Clé fal.ai
  "anthropic_key":         "",   # Clé Anthropic (Claude)
  "nano_banana_key":       "",   # Clé Nano Banana
  "default_model":         "seedance-2.0",
  "default_duration":      "10",
  "default_resolution":    "720p",
  "output_dir":            "",   # Vide = ~/Videos/PANDORA/
  "last_project_location": ""
}
```

### Clés par élément (dans le JSON de chaque item)
```
"decor_style_key":     ""   # Style d'image sélectionné pour ce décor
"accessory_style_key": ""   # Style d'image sélectionné pour cet accessoire
"hmc_style_key":       ""   # Style d'image sélectionné pour ce HMC
"vehicle_style_key":   ""   # Style d'image sélectionné pour ce véhicule
```

---

## Génération vidéo Seedance (AI Studio)

### Architecture onglets (`ui/seedance_widget.py` + `ui/tab_*.py`)

`SeedanceWidget` est un conteneur à onglets. Chaque mode de génération est dans son propre fichier :

| Onglet | Fichier | Mode fal.ai |
|--------|---------|-------------|
| Text-to-Video | `tab_t2v.py` | `text-to-video` (ou `reference-to-video` auto) |
| Image-to-Video | `tab_i2v.py` | `image-to-video` |
| Extension | `tab_extension.py` | `extend-video` |
| Référence | `tab_reference.py` | `reference-to-video` |
| Paramètres | `tab_settings.py` | — |
| Moteurs | `tab_video_engines.py` | multi-modèles |
| Historique | `tab_history.py` | — |

### Bascule T2V → Référence automatique (`api/real.py`)

**IMPORTANT** : Dans l'onglet T2V, si des images de référence sont présentes (personnages, décors, accessoires, véhicules), l'endpoint change **silencieusement** de `text-to-video` vers `reference-to-video` :

```python
# api/real.py lignes 46-51
ref_images = [p for p in params.get("ref_images", []) if p and os.path.isfile(p)][:3]
_auto_ref = mode == "t2v" and bool(ref_images)
if _auto_ref:
    mode = "ref"
    endpoint = endpoints["ref"]  # bytedance/seedance-2.0/reference-to-video
```

L'onglet T2V construit ces références via `get_ref_mosaics()` (`tab_t2v.py` ligne 877) :
- Slot 1 : mosaïque des portraits de personnages assignés
- Slot 2 : image du décor assigné
- Slot 3 : mosaïque véhicules + accessoires

La fonction `build_ref_mosaics()` dans `core/mosaic.py` assemble les images composites.

### Worker (`core/worker.py`)
`GenerationWorker(QThread)` bascule automatiquement :
- **Sans clé fal.ai** → `api.mock.run_mock` (simulation avec progression)
- **Avec clé fal.ai** → `api.real.run_real` (vrai appel fal-client)

Signaux : `progress(int, str)`, `finished(dict)`, `failed(str)`

### Modes

| Mode | Endpoint fal.ai | Statut |
|------|----------------|--------|
| Text-to-Video (T2V) | `bytedance/seedance-2.0/text-to-video` | ✅ Mock + réel |
| Image-to-Video (I2V) | `bytedance/seedance-2.0/image-to-video` | ✅ Mock + réel |
| Extension de clip | `bytedance/seedance-2.0/extend-video` | ✅ Implémenté |
| Référence multimodale | `bytedance/seedance-2.0/reference-to-video` | ✅ Implémenté |

### Traduction des prompts (`core/lang.py`)
Avant chaque appel Seedance ou Nano Banana, le prompt est traduit via Claude Haiku :
- `translate_to_english(text)` — pour Seedance (prompts en anglais requis)
- `translate_to_chinese(text)` — fallback compression (le chinois est ~3× plus compact)
- Les dialogues entre guillemets (`« »`, `" "`, `' '`) sont protégés par des marqueurs `§D0§`
  et restaurés après traduction — ils ne sont jamais traduits.

---

## Système de traduction i18n (`core/i18n.py`)

Pandora est bilingue FR/EN. Le système de traduction est dans `core/i18n.py`.

### Architecture

- **`get_lang()` / `set_lang(lang)`** — lit/écrit la langue courante (`"fr"` ou `"en"`)
- **`tr(key)`** — retourne la traduction d'une clé depuis le dict `_T`
- **`_FR_TO_EN`** — dict de traduction directe `texte français → texte anglais` pour tous les labels UI
- **`retranslate_widget(widget)`** — parcourt récursivement l'arbre de widgets et traduit chaque texte trouvé dans `_FR_TO_EN`

### Pattern d'utilisation

Les pages et dialogs appellent `retranslate_widget(self)` lors du changement de langue. Les boutons et labels dont le texte est dans `_FR_TO_EN` sont traduits automatiquement. Les textes non trouvés restent en français.

Pour ajouter une traduction, ajouter une entrée dans `_FR_TO_EN` :
```python
"Texte français":  "English text",
```

### Langue du manuel (`ui/dialog_user_manual.py`)

Le `UserManualDialog` a son propre toggle FR/EN indépendant de l'interface (deux boutons 🇫🇷/🇬🇧 dans l'en-tête). Il initialise sa langue depuis `get_lang()` mais peut être basculé sans changer la langue de l'app.

Structure interne :
- `_SECTIONS` + `_BUILDERS` — 15 sections en français (fonctions `_s_*`)
- `_SECTIONS_EN` + `_BUILDERS_EN` — 15 sections en anglais (fonctions `_e_*`)
- `_show_section(idx)` — utilise `_BUILDERS` ou `_BUILDERS_EN` selon `self._lang`
- `_build_nav_buttons()` — reconstruit les boutons de navigation pour la langue courante
- `_set_lang(lang)` — bascule la langue, reconstruit la nav, ré-affiche la section courante

---

## Nano Banana — Workers (`api/nano_banana.py`)

| Worker | Signal(s) | Rôle |
|--------|-----------|------|
| `GeneratePortraitWorker` | `finished(str)`, `failed(str)` | Portrait personnage (1 image) |
| `GenerateItemWorker` | `finished(str)`, `multi_finished(list)`, `failed(str)` | Image élément (Décor/Accessoire/HMC/Véhicule) — N images |
| `GenerateDecorSheetWorker` | `finished(str)`, `multi_finished(list)`, `failed(str)` | Sheet 4 vues d'un décor — N sheets |

**Note** : `GenerateDecorSheetWorker` prend `num_images: int = 1`. Quand N>1, il boucle N fois sur l'API et émet `multi_finished(paths)`. Le dialogue `dialog_decor._on_generate()` passe `num_images=_num` depuis le spinbox.

---

## Dialogs éléments — fonctionnalités communes

Les 4 dialogs `dialog_decor.py`, `dialog_accessory.py`, `dialog_hmc.py`, `dialog_vehicle.py` partagent les mêmes patterns :

### Style d'image par élément

Chaque dialog possède `self._style_combo` (QComboBox) avec les styles de `core/style.py` :
```python
# Peuplé avec STYLES / GROUPS depuis core/style.py
# Valeur courante : self._style_combo.currentData() → style_key (str)
# Persisté en JSON : "decor_style_key" / "accessory_style_key" / "hmc_style_key" / "vehicle_style_key"
```

Lecture dans `_on_generate()` :
```python
style_key = self._style_combo.currentData()
if style_key:
    _s = next((s for s in style_api.STYLES if s["key"] == style_key), None)
    suffix = _s["image_suffix"] if _s else style_api.get_image_suffix()
else:
    suffix = style_api.get_image_suffix()  # style du projet courant
```

### Bouton "Générer une variation"

Chaque dialog possède deux boutons variation :
- `self._btn_variation` — dans le formulaire gauche, après le spinbox
- `self._btn_panel_variation` — dans le panneau de prévisualisation droit, après la nav

Les deux boutons sont cachés (`setVisible(False)`) initialement et apparaissent uniquement quand au moins une image existe, via `_refresh_preview_nav()` :
```python
has_any = n > 0  # n = nombre d'images dans la galerie
if hasattr(self, "_btn_variation"):
    self._btn_variation.setVisible(has_any)
if hasattr(self, "_btn_panel_variation"):
    self._btn_panel_variation.setVisible(has_any)
```

---

## Claude IA — Workers scénario (`api/screenplay.py`)

Tous ces workers héritent de `QThread` et utilisent la clé `anthropic_key` de `config.json`.

| Worker | Modèle | Rôle |
|--------|--------|------|
| `FormatScreenplayWorker` | Haiku | Mise en page scénario cinéma standard |
| `ArrangeScreenplayWorker` | Haiku | Analyse narrative + suggestions d'arrangement |
| `ApplyArrangeWorker` | Haiku | Application des suggestions au texte |
| `GenerateStoryboardWorker` | Sonnet | Génération découpage JSON depuis le scénario |
| `ExtractCharactersWorker` | Haiku | Extraction personnages → JSON |
| `ExtractDecorsWorker` | Haiku | Extraction décors → JSON |
| `ExtractAccessoriesWorker` | Haiku | Extraction accessoires → JSON |
| `ExtractVehiclesWorker` | Haiku | Extraction véhicules → JSON |
| `ExtractHMCWorker` | Haiku | Extraction HMC → JSON |

---

## Page Scénario (`ui/page_scenario.py`)

Fonctionnalités clés :
- **Éditeur de texte** — éditeur pleine page avec historique undo/redo manuel (`_undo_stack`, `_redo_stack`)
- **Versions** — sauvegarde nommée de versions dans `scenario["versions"]` (combo + boutons ✚ ⤓ ✕ dans la top bar)
- **Undo/Redo** — boutons ↩ ↪ dans la top bar ; poussés avant chaque modification par Claude
- **Panneau droit collapsible** — sections ▼/▶ pour "☁ Claude IA" et "☁ Générer depuis le scénario" (toutes deux ouvertes par défaut)
- **Intensité d'arrangement** — slider 1-10 avec légende dynamique + descriptions niveau par niveau
- **Résultat Claude** — texte modifié en premier, puis analyse séparée par `═══ ANALYSE ═══`
- **Génération automatique** — depuis le scénario : personnages, décors, accessoires, HMC, véhicules, storyboard
- **Session d'arrangement** — `dialog_arrange_session.py` pour sessions itératives

---

## Page Storyboard (`ui/page_storyboard.py`)

### Colonnes du tableau (`_COLS`, index 0-16)

| # | En-tête | Champ | Largeur |
|---|---------|-------|---------|
| 0 | — | Drag grip | 22 |
| 1 | Aperçu | image_path | 92 |
| 2 | Séq | seq_num / seq_name | 78 |
| 3 | Plan | number | 52 |
| 4 | Action | scene_title | stretch |
| 5 | Mouvement | camera_movement | 96 |
| 6 | Valeur | shot_size | 72 |
| 7 | Focal | focal | 72 |
| 8 | Vitesse | speed | 74 |
| 9 | Décor | decor_id / decor_name | 152 |
| 10 | Heure | shot_time | 96 |
| 11 | Accessoires | accessory_names | 102 |
| 12 | Acteurs | character_names | 96 |
| 13 | Axe | camera_axis | 72 |
| 14 | Durée | duration | 52 |
| 15 | Prompt | seedance_prompt | stretch |
| 16 | — | Boutons Éditer/Générer/Supprimer | 78 |

Les largeurs de colonnes sont dans `_col_widths` (liste partagée entre l'en-tête et toutes les lignes).
Toutes les colonnes sont cliquables en ligne — menu ou dialog pour modifier.

### Dialogue d'édition de plan (`ui/dialog_shot.py`)
Sections dans le dialogue :
- **CAMÉRA** — mouvement, valeur de plan, focale, optique, vitesse
- **ÉLÉMENTS** — décor, heure, séquence, personnages, accessoires, véhicules
- **MISE EN SCÈNE** — axe caméra, placement caméra, placement acteurs, entrée/sortie (IN/OUT), micro
- **DURÉE** — slider 2-15s
- **COMMENTAIRES** — notes de tournage
- **PROMPT SEEDANCE** — prompt de génération vidéo

### Champs MISE EN SCÈNE
```python
camera_axis       # "Face" | "3/4" | "Latéral 90°" | "Dos" | "Plongée" | "Contre-plongée"
camera_placement  # Description libre du placement caméra
actor_placement   # Description libre du placement des acteurs dans le cadre
chars_in          # Personnages entrant dans le plan (ancrage spatial)
chars_out         # Personnages sortant du plan
mic_placement     # Placement du micro
```

---

## Conventions de code

- `CP` (Color Palette) — toujours importé depuis `ui/styles.py`, jamais de couleur hardcodée
- Les appels réseau tournent TOUJOURS dans un `QThread` — jamais dans le thread principal
- Les signaux PyQt6 (`pyqtSignal`) sont le seul moyen de communiquer entre threads et pages
- `core.context` est le seul endroit qui contient l'état global du projet courant
- `core.context.get_data_root()` retourne `<projet>/data/` si un projet est ouvert, sinon `data/` local
- Les sections collapsibles du panneau droit utilisent le pattern `_make_toggle(title, container, expanded)`
- L'undo/redo du scénario est manuel (liste Python) — pas `QTextEdit.undo()` qui est vidé par `setPlainText()`
- Sonnet (`claude-sonnet-5`) pour les sorties JSON longues (storyboard), Haiku (`claude-haiku-4-5`) pour tout le reste
- Les dialogs éléments (Décor/Accessoire/HMC/Véhicule) partagent les patterns style combo + variation buttons

---

## État d'avancement

### ✅ Fait
- Architecture complète multi-pages (11 pages + AI Studio)
- Gestion de projets (splash, création, ouverture, switch)
- Page Scénario — éditeur complet + Claude IA (format, arrange, apply) + versions nommées + undo/redo + génération automatique depuis scénario + session d'arrangement
- Page Storyboard — grille complète avec toutes les colonnes, édition inline, dialog complet, champs MISE EN SCÈNE, colonne Axe, versions nommées, protection suppression dernière version
- Pages Castings, Décors, Accessoires, HMC, Véhicules — CRUD complet + génération Nano Banana
- Style d'image par élément dans Décors, Accessoires, HMC, Véhicules (clé persistée en JSON)
- Bouton "Générer une variation" dans formulaire + panneau preview de tous les 4 dialogs éléments
- Bug corrigé : Sheet 4 vues × N génère bien N sheets (signal multi_finished + param num_images)
- Page Paramètres — clés API (fal.ai, Anthropic, Nano Banana), dossier sortie
- AI Studio — onglets T2V, I2V, Extension, Référence, Paramètres, Moteurs, Historique
- Bascule T2V → Référence automatique quand des images de référence sont disponibles
- Mosaïques de références (personnages / décor / autres) via `core/mosaic.py`
- Traduction automatique des prompts (FR → EN/ZH) via Claude Haiku
- Protection des dialogues entre guillemets pendant la traduction
- Système i18n FR↔EN — `core/i18n.py` avec `_FR_TO_EN` + `retranslate_widget()`
- Manuel d'utilisation bilingue — toggle FR/EN dans `UserManualDialog`
- Intégration DaVinci Resolve (bridge, importer)
- Dossier PANDORA/ structuré par module
- Génération de moods/aperçus storyboard via Flux T2I (`api/apercu.py` + `ui/dialog_apercu.py`)
- Moteurs vidéo alternatifs Kling v3 Pro + PixVerse v4.5 (`api/video_engines.py`)
- Synthèse vocale Kokoro TTS + détourage BiRefNet pour page Doublage (`api/tts.py`)
- Galerie de templates de style Seedance (`ui/dialog_style_gallery.py`)
- Optimisation de prompt style pictural — `OptimizeStyleReferenceWorker` préserve le style de référence sans transposer en photoréaliste
- Audit v1.0.0 : 88 fichiers, 0 erreur de syntaxe, 0 import cassé — code propre

### 🔲 À faire
- "Mise en page scénario" — génération du bloc technique par plan (IN/OUT, axe, placement) depuis les champs MISE EN SCÈNE
- Style de film → base d'images de référence Seedance (images exemplaires du style envoyées comme ref)
- Affichage explicite dans l'UI quand T2V bascule en Référence (indicateur visuel)
- Page Doublage — implémentation complète
- Page Image & Son — complément des fonctionnalités
- Polish UI — animations, espacements

### 🔲 Release v1.0.0 (en cours)
- ✅ Audit complet du code
- ✅ EULA — charte d'utilisation (droit FR/EU) → `EULA.txt`, `ui/dialog_eula.py`, check au démarrage dans `main.py`, accessible depuis `dialog_contact.py`
- ✅ Vérification de mise à jour in-app (GitHub Releases API) → `core/version.py` (VERSION + GITHUB_RELEASES_URL), `api/update_check.py` (UpdateCheckWorker), banner dismissible dans PandoraWindow
- ✅ PyInstaller — bundle Windows : `pandora.spec`, `build.ps1`, `tools/make_ico.py` ; tous les paths __file__ rendus frozen-aware (assets → sys._MEIPASS, data → %LOCALAPPDATA%\PANDORA\ via core/paths.py)
- ✅ Inno Setup — installeur Windows : `pandora_setup.iss` (installe dans `C:\Program Files\PANDORA\`, EULA obligatoire, raccourcis menu Démarrer + bureau optionnel, désinstalleur propre)
- ✅ README.md créé (documentation utilisateur + instructions de build + architecture)
- 🔲 Dépôt GitHub public — créer le repo, pousser le code, créer la Release v1.0.0, puis mettre à jour `GITHUB_REPO` dans `core/version.py` avec le vrai slug
- 🔲 Certificat de signature EV Code Signing — `tools/sign_release.ps1` prêt ; acheter le certificat (Sectigo ~$200/an, Certum ~$80/an) puis exécuter le script
