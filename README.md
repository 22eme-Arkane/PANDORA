# PANDORA — Standalone AI Cinema Pre-Production Studio × Seedance 2.0

[![License: GPL v3](https://img.shields.io/badge/License-GPLv3-blue.svg)](https://www.gnu.org/licenses/gpl-3.0)

**PANDORA** is a free, open-source, **standalone** cinema pre-production studio for Windows and macOS that integrates AI video generation (Seedance 2.0 / ByteDance via fal.ai) into a complete workflow: screenplay, storyboard, casting, sets, props, costumes & makeup, and vehicles. It runs entirely on its own — DaVinci Resolve integration (automatic clip import into the Media Pool) is available as an **option**, not a requirement.

---

## Presentation

[![Watch the PANDORA presentation on YouTube](https://img.youtube.com/vi/ci9jA_Tye2E/maxresdefault.jpg)](https://youtu.be/ci9jA_Tye2E)

## Full Tutorial

[![Watch the full PANDORA tutorial on YouTube](https://img.youtube.com/vi/SC3pRI5bR1Q/maxresdefault.jpg)](https://www.youtube.com/watch?v=SC3pRI5bR1Q)

---

## Download

**[⬇ Download PANDORA v1.3.1 for Windows](https://github.com/22eme-Arkane/PANDORA/releases/download/v1.3.1/PANDORA_Setup_1.3.1.exe)**

**[⬇ Download PANDORA v1.3.1 for macOS](https://github.com/22eme-Arkane/PANDORA/releases/download/v1.3.1/PANDORA_1.3.1.dmg)** *(Apple Silicon — see [Installation](#installation) for the first launch)*

All versions: [Releases](../../releases)

🌐 **Official 22eme ARKANE website: [22eme-arkane.com](https://22eme-arkane.com)**

---

## Features

| Module | Description |
|--------|-------------|
| **Screenplay** | Cinema screenplay editor + auto-formatting via Claude AI + version management |
| **Storyboard** | Shot grid with direct AI video generation (Seedance 2.0) from each shot |
| **Castings** | Character sheets + AI portrait generation |
| **Sets** | Location sheets + multi-angle AI image generation |
| **Props / Costumes / Vehicles** | Element sheets + AI image generation |
| **AI Studio** | 20+ video engines — Seedance 2.0/Mini, Kling, LTX-2, PixVerse, Veo 3.1, Sora 2… + AI Music, AI Images, Sound Design |
| **"Generate All"** | One-click extraction + image generation for all screenplay elements |
| **Dubbing** | Text-to-speech synthesis + background removal (BiRefNet) |
| **Image & Sound** | Camera and optics preferences |
| **DaVinci Resolve** *(optional)* | Automatic clip import into Media Pool (DaVinci Studio required) |

---

## Requirements

- **Windows 10/11** 64-bit, or **macOS** (Apple Silicon)
- **DaVinci Resolve Studio** (optional — only for Media Pool integration)
- API keys (optional — the software runs in simulation mode without them):
  - [fal.ai](https://fal.ai) — AI video & image generation (Seedance 2.0, portraits, elements…)
  - [Anthropic](https://www.anthropic.com) — Claude AI (screenplay, storyboard, prompts)

---

## Installation

### Windows

1. Download `PANDORA_Setup_1.3.0.exe` from the link above and run it
2. If Windows shows *"Windows protected your PC"* (SmartScreen), click
   **More info** then **Run anyway** — the app is not code-signed yet
   (certificate in progress), this is the Windows equivalent of the macOS
   notice below
3. Follow the installer and accept the Terms of Use
4. Launch **PANDORA** from the Start menu or desktop shortcut
5. Enter your API keys in **Settings** (optional)

### macOS

1. Download `PANDORA_1.3.0.dmg` from the link above
2. Open the DMG and drag **PANDORA** into **Applications** (as usual)
3. **First launch** — macOS will claim that *"PANDORA is damaged and can't be
   opened"*. **This is normal, the app is not damaged** — macOS blocks apps
   that are not registered with Apple. To unblock it (one time only):
   - Open **Terminal** (Cmd+Space, type "Terminal")
   - Paste this line and press Enter:

     ```bash
     xattr -cr /Applications/PANDORA.app
     ```

   - Launch PANDORA normally by double-clicking — it won't ask again.
4. Enter your API keys in **Settings** (optional)

---

## Quick Start

1. **Create a project** — from the home screen, click "New project"
2. **Write the screenplay** — Screenplay page, with auto-formatting and Claude AI suggestions
3. **Generate the storyboard** — from the screenplay, click "Generate storyboard"
4. **Create element sheets** — Castings, Sets, Props, Costumes, Vehicles
5. **Or use "Generate All"** — one-click extraction of all elements from the screenplay
6. **Generate videos** — AI Studio tab, Text-to-Video or directly from each storyboard shot

---

## Architecture

```
core/      Business logic (config, projects, screenplay, storyboard, i18n, migration…)
api/       Network calls in QThread (Seedance, Claude, Nano Banana, update check)
ui/        PyQt6 components (pages, dialogs, AI Studio tabs)
davinci/   DaVinci Resolve Scripting API bridge
assets/    Icons, badges, visual references
tools/     Utility scripts (build, ICO conversion, wizard images)
```

---

## Support PANDORA

PANDORA is free. If this project is useful to you:

- ⭐ Star the repo on GitHub
- 🐛 [Report a bug](../../issues) — subject: `Bug`
- 💬 [Share your feedback](mailto:22eme.arkane@gmail.com) — subject: `Feedback`

---

## Terms of Use

See [EULA.txt](EULA.txt) (English: [EULA_EN.txt](EULA_EN.txt)) — accepted at first launch.

---

## License

PANDORA is free software distributed under the **GNU General Public License v3 (GPL v3)**.  
You are free to use, study, modify, and redistribute it under the same terms.  
Copyright © 2026 22eme Arkane — Matthieu Terrien.  
See [LICENSE](LICENSE) for the full license text, and [EULA.txt](EULA.txt) for the Terms of Use.
