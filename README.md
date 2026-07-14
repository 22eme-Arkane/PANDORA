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

**[⬇ Download PANDORA v1.3.4 for Windows](https://github.com/22eme-Arkane/PANDORA/releases/download/v1.3.4/PANDORA_Setup_1.3.4.exe)**

**[⬇ Download PANDORA v1.3.4 for macOS](https://github.com/22eme-Arkane/PANDORA/releases/download/v1.3.4/PANDORA_1.3.4.dmg)** *(Apple Silicon — see [Installation](#installation) for the first launch)*

All versions: [Releases](../../releases)

🌐 **Official 22eme ARKANE website: [22eme-arkane.com](https://22eme-arkane.com)**

---

## What's new in v1.3.4

This update makes **AI co-writing actually apply your edits**, gets **Live/Mapping timings to match the music**, and turns the intimidating API setup screen into a short guided walkthrough.

**Co-writing — edits now land every time**
- **Typography tolerance**: your text uses `'` `« »` `…` while the AI writes back `'` `"` `...` — the passage to edit was no longer found. Both forms now match, in both directions.
- **No more truncation**: past a few long passages the reply was cut off and *no* edit came through. The ceiling was doubled.
- **No more empty promises**: the AI sometimes said "I'll change X" without returning the edit. Any requested change now ships in the same reply.
- Replies are **airier** — paragraphs and lists instead of one dense block.

**Live / Mapping — timings finally match the track**
- On a 4:28 set, the découpage produced shots totalling 3:55 — **a full minute missing at export**. Shot durations are now **automatically conformed to the set length** (pro-rata), and the arithmetic instruction was hardened in every prompt that writes durations.
- **"Generate all"** now starts from the *PANDORA layout* when it exists (like the découpage button) — your co-written prompts are no longer rewritten.

**Cinéma — the layout becomes a real découpage, with no AI pass**
- When the PANDORA layout is co-written shot by shot, the storyboard is derived **directly**: prompts kept verbatim, zero loss, zero AI call (so zero cost). The rewrite warning only appears when the AI actually steps in.

**Visual references — the Live feature set comes to Cinéma**
- Images and analysis **saved with the project** (no longer lost on close)
- "Analyze" **reopens** the existing analysis instead of paying for it again
- **Analysis library**, reusable across projects
- **Art-direction chat** inside the analysis window
- The art direction now feeds both the arrangement *and* the co-writing

**Four new image engines** — **GPT Image 2**, **FLUX.2 [pro]**, **Seedream 4.5** and **Recraft** join Nano Banana for characters, sets, props, costumes and vehicles.

**Character sheets — a single face** — body views (front, 3/4, profile) are now cropped **without the face**; only the close-up shows it, so Seedance is no longer confused by several faces.

**Getting started, simplified** — the API setup screen now fits in **3 steps per service** (account → key → credits), with clear cues ("2 keys, ≈ 5 minutes, no technical knowledge") and **up-to-date URLs** (the Anthropic console is now `platform.claude.com`).

**Report a bug without an email client** — a feedback / bug form lands in *Contact us*, and the error dialog offers to send the crash report in one click *(server-side activation coming soon)*.

**PANDORA | Live — Mapping & Sequences**
- **Conductor thumbnails now show each shot's last rendered frame**, with a red ✕ to clear it — spot a drifted shot at a glance and reset it so the next generation restarts clean. Thumbnails load automatically when you open a project, and **self-repair** if a frame link was lost.
- **Shot-to-shot continuity** in mapping sequences (each shot picks up from the previous shot's real last frame), with stronger anti-drift instructions to keep the façade's proportions stable.
- **"Use the Mood images" option** in *Render & Audio*: keep the mood keyframes, or generate from the building façade alone with strict façade preservation (no zoom, no reframing).
- **Mood engine choice — Flux or Nano Banana 2** — before batch generation *and* for a single mood variation, with identical instructions on both engines. The façade stays the priority; façade elements the prompt marks as "not visible" render as pure black.

**Storyboard & Découpage (Live + Cinéma)**
- **Automatic découpage source**: PANDORA uses your *PANDORA layout* if present, otherwise the screenplay/conductor — no manual choice — with an honest warning **only** when prompts are actually rewritten.
- **Zero-loss découpage** from a structured PANDORA layout (deterministic — every shot is kept).
- **"All shots" batch co-writing** — no shot dropped, with Save / Open of the layout.
- **Reference images**: visible on the first add, no longer cropped in the cell, all 3 shown; shot references now feed the Mood generation.

**Also**
- Numerous robustness fixes across the sequence / conductor workflow.

> Full history: [Releases](../../releases).

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

1. Download `PANDORA_Setup_1.3.4.exe` from the link above and run it
2. If Windows shows *"Windows protected your PC"* (SmartScreen), click
   **More info** then **Run anyway** — the app is not code-signed yet
   (certificate in progress), this is the Windows equivalent of the macOS
   notice below
3. Follow the installer and accept the Terms of Use
4. Launch **PANDORA** from the Start menu or desktop shortcut
5. Enter your API keys in **Settings** (optional)

### macOS

1. Download `PANDORA_1.3.4.dmg` from the link above
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
