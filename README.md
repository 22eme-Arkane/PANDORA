# PANDORA — Plugin de pré-production cinéma × Seedance 2.0

**PANDORA** est un logiciel de pré-production cinéma pour Windows qui intègre la génération vidéo IA (Seedance 2.0 / ByteDance via fal.ai) dans un workflow complet : scénario, storyboard, casting, décors, accessoires, HMC et véhicules.

---

## Fonctionnalités

| Module | Description |
|--------|-------------|
| **Scénario** | Éditeur de scénario cinéma + mise en page automatique via Claude IA + gestion de versions |
| **Storyboard** | Grille de plans avec génération vidéo directe (Seedance 2.0) depuis chaque plan |
| **Castings** | Fiches personnages + génération de portraits IA (Nano Banana) |
| **Décors** | Fiches de lieux + génération d'images IA multi-vues |
| **Accessoires / HMC / Véhicules** | Fiches éléments + génération d'images IA |
| **AI Studio** | Génération vidéo Seedance 2.0 — Text-to-Video, Image-to-Video, Extension, Référence multimodale |
| **Image & Son** | Préférences caméra et optiques |
| **Intégration DaVinci Resolve** | Import automatique des clips dans le Media Pool (DaVinci Studio requis) |

---

## Prérequis

- **Windows 10/11** 64 bits
- **DaVinci Resolve Studio** (optionnel — uniquement pour l'intégration Media Pool)
- Clés API (optionnelles — le logiciel fonctionne en mode simulation sans elles) :
  - [fal.ai](https://fal.ai) — génération vidéo Seedance 2.0
  - [Anthropic](https://www.anthropic.com) — assistant IA (scénario, storyboard, prompts)
  - Nano Banana — génération de portraits et d'images

---

## Installation

1. Télécharger `PANDORA_Setup_1.0.0.exe` depuis la page [Releases](../../releases)
2. Exécuter l'installeur et accepter la charte d'utilisation
3. Lancer **PANDORA** depuis le menu Démarrer ou le bureau
4. Renseigner vos clés API dans **Paramètres** (optionnel)

---

## Utilisation rapide

1. **Créer un projet** — depuis l'écran d'accueil, cliquez sur "Nouveau projet"
2. **Écrire le scénario** — page Scénario, avec mise en page et suggestions Claude IA
3. **Générer le storyboard** — depuis le scénario, cliquez "Générer le storyboard"
4. **Créer les fiches** — Castings, Décors, Accessoires, HMC, Véhicules
5. **Générer des vidéos** — page AI Studio, onglet Text-to-Video ou depuis chaque plan du storyboard

---

## Construire depuis les sources

**Prérequis dev :**
```
Python 3.14+
pip install PyQt6 anthropic fal-client Pillow requests pyinstaller
```

**Lancer en dev :**
```powershell
python main.py
```

**Créer l'installeur :**
```powershell
.\build.ps1 -Installer
```

Produit : `dist\PANDORA_Setup_1.0.0.exe`

---

## Architecture

```
core/      Logique métier (config, projets, scénario, storyboard, i18n, migration…)
api/       Appels réseau dans QThread (Seedance, Claude, Nano Banana, update check)
ui/        Composants PyQt6 (pages, dialogs, onglets AI Studio)
davinci/   Pont DaVinci Resolve Scripting API
assets/    Icônes, badges, références visuelles
tools/     Scripts utilitaires (build, conversion ICO)
```

---

## Soutenir PANDORA

PANDORA est gratuit et open source. Si ce projet vous est utile :

- ⭐ Mettez une étoile sur GitHub
- ❤ [Faites un don](../../releases) (PayPal / crypto)
- 🐛 [Signalez un bug](../../issues) — objet : `Bug`
- 💬 [Partagez vos retours](mailto:22eme.arkane@gmail.com) — objet : `Avis`

---

## Charte d'utilisation

Voir [EULA.txt](EULA.txt) — acceptée lors de la première installation.

---

## Licence

© 2025 22ème Arkane. Tous droits réservés.  
Distribution autorisée uniquement via les [Releases officielles](../../releases).  
Voir [EULA.txt](EULA.txt) pour les conditions complètes.
