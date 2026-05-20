# PANDORA — Cinema Pre-Production Plugin × Seedance 2.0

**PANDORA** is a cinema pre-production software for Windows that integrates AI video generation (Seedance 2.0 / ByteDance via fal.ai) into a complete workflow: screenplay, storyboard, casting, sets, props, costumes & makeup, and vehicles.

---

## Presentation

[![Watch the PANDORA presentation on YouTube](https://img.youtube.com/vi/ci9jA_Tye2E/maxresdefault.jpg)](https://youtu.be/ci9jA_Tye2E)

## Full Tutorial

[![Watch the full PANDORA tutorial on YouTube](https://img.youtube.com/vi/SC3pRI5bR1Q/maxresdefault.jpg)](https://www.youtube.com/watch?v=SC3pRI5bR1Q)

---

## Download

**[⬇ Download PANDORA v1.1.4](https://github.com/22eme-Arkane/PANDORA/releases/download/v1.1.4/PANDORA_Setup_1.1.4.exe)**

All versions: [Releases](../../releases)

> **Windows note:** on first install, Windows may show a SmartScreen warning ("Unknown app").
> Click **"More info"** then **"Run anyway"**. This warning will disappear in a future version
> (code signing certificate in progress).

---

## Features

| Module | Description |
|--------|-------------|
| **Screenplay** | Cinema screenplay editor + auto-formatting via Claude AI + version management |
| **Storyboard** | Shot grid with direct AI video generation (Seedance 2.0) from each shot |
| **Castings** | Character sheets + AI portrait generation |
| **Sets** | Location sheets + multi-angle AI image generation |
| **Props / Costumes / Vehicles** | Element sheets + AI image generation |
| **AI Studio** | 13 video engines — Seedance 2.0, Kling, PixVerse, Veo 3.1, Happy Horse, Sora 2… |
| **"Generate All"** | One-click extraction + image generation for all screenplay elements |
| **Dubbing** | Text-to-speech synthesis + background removal (BiRefNet) |
| **Image & Sound** | Camera and optics preferences |
| **DaVinci Resolve** | Automatic clip import into Media Pool (DaVinci Studio required) |

---

## Requirements

- **Windows 10/11** 64-bit
- **DaVinci Resolve Studio** (optional — only for Media Pool integration)
- API keys (optional — the software runs in simulation mode without them):
  - [fal.ai](https://fal.ai) — AI video & image generation (Seedance 2.0, portraits, elements…)
  - [Anthropic](https://www.anthropic.com) — Claude AI (screenplay, storyboard, prompts)

---

## Installation

1. Download `PANDORA_Setup_1.1.4.exe` from the link above
2. Run the installer and accept the End User License Agreement
3. Launch **PANDORA** from the Start menu or desktop shortcut
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

## End User License Agreement

See [EULA.txt](EULA.txt) — accepted at first launch.

---

## License

© 2026 22eme Arkane. All rights reserved.  
Proprietary software — viewing the source code does not grant any right to use, copy, or redistribute.  
See [LICENSE](LICENSE) and [EULA.txt](EULA.txt) for full terms.
