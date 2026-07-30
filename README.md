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

**[⬇ Download PANDORA v2.1.0 for Windows](https://github.com/22eme-Arkane/PANDORA/releases/download/v2.1.0/PANDORA_Setup_2.1.0.exe)**

**[⬇ Download PANDORA v2.1.0 for macOS](https://github.com/22eme-Arkane/PANDORA/releases/download/v2.1.0/PANDORA_2.1.0.dmg)** *(Apple Silicon — see [Installation](#installation) for the first launch)*

All versions: [Releases](../../releases)

🌐 **Official 22eme ARKANE website: [22eme-arkane.com](https://22eme-arkane.com)**

---

## What's new in v2.1.0

**Live mapping stops drifting — and every image lands at the exact size you asked for.**

This release attacks the #1 complaint on video-mapping work: after a few shots, the
generated clips slowly zoomed, cropped and wandered off the building. The cause was
structural — each shot restarted from a frame extracted from the previous *video*,
so every generation's small drift was re-injected and compounded, like a photocopy
of a photocopy.

- **New "Image chain" mode (default) in Sequence Mapping.** Shots are generated in
  image-to-video with a start and an end image: each shot *ends* on its own Mood and
  the next shot *starts* from that exact same file. Identity, not extraction — the
  snowball is gone by construction. Shot 1 gets two thumbnails (start state + end
  state); every following shot chains automatically. The previous frames-based mode
  is still there behind the **Mode** toggle next to ACTION.
- **Start/end thumbnails right in the storyboard.** Click either one to generate or
  regenerate that state alone, without running the whole batch. You can also
  **import your own image** as a Mood — in Live *and* in Cinema.
- **Images at the exact resolution you chose.** Every ratio except 1:1 was silently
  rendered at SDXL bucket sizes (a 16:9 request came back 1368×768). All image
  generation now delivers the exact definition selected, 1920×1080 by default, and
  batch moods are conformed pixel-exact before being saved.
- **Facade masking repaired.** The confinement mask silently did nothing on RGBA
  facades, and re-applying it ate one pixel per pass. Fixed, cache rebuilt, and the
  option is now clearly toggleable (off by default) in RENDU & AUDIO.
- **The Mood prompt is composed by AI in the engine's grammar** — batch and single
  generations alike, in both editions, with a persistent cache so a composition is
  never paid twice. The prompt and preview panes are now collapsible; unfold the
  prompt alone and it takes the full height.
- **New project folder layout.** New projects are created with a clean, numbered
  English structure (`01_writing`, `02_elements`, `03_production`, `04_live`,
  hidden `.cache`). **Existing projects are untouched** — they keep their historical
  folders forever and everything keeps working, no migration, nothing to do.
- **Config file writes are now atomic** — a crash mid-save can no longer corrupt
  your API keys; a corrupted file is quarantined and rebuilt instead of taking the
  app down.
- **Resolume integration is set aside for now** — the tab and buttons are removed
  from the Live edition; generated sets live in the project's videos folder, ready
  to import into any VJ software. The engine remains in the code and may return.
- Plus: the batch "Generate Moods" respects the two-plate anchoring (a shot *leaves*
  the previous frame and *arrives* on its Mood), reference images went back to being
  true inspirations, cancellable Mood generation, neon-green highlight for the
  active Mood, readable errors throughout, and both user guides (Cinema + Live)
  brought up to date in French and English.

---

## What's new in v2.0.2

**The Live edition catches up with Cinema — including a silent data-loss bug.**

- **Your Live breakdown is actually saved now.** It never was: from the second save
  onward, an empty canonical key overwrote it every time. PANDORA said "breakdown
  applied ✓" and kept nothing — on reopening, the tab was empty *and* greyed out, and
  your sequences silently fell back to the raw rundown instead of your co-written
  prompts. **Everyone working in Live should check their current breakdowns.**
- **The Live breakdown uses the "DÉCOUPAGE PANDORA 2" shot-sheet contract**, like
  Cinema: rundown source, intent, rhythm, duration, visual prompt, characters, props,
  vehicles — plus `SON`, a Live-only field that feeds sound design and musical sync.
  Existing flat-format breakdowns keep working; nothing to migrate.
- **The Breakdown tab is editable.** It was read-only in Live: once generated, you
  could not delete a shot, fix a duration or rewrite a prompt. Edits autosave.
- **Live sequences no longer re-cut with the Cinema engine**, which applied the film
  contract, rebuilt prompts and dropped the sound design entirely.
- **"Sync" can no longer destroy your VJ prompts.** Two operations inherited from
  Cinema — rewriting prompts and rebuilding a screenplay — are gone from the Live
  dialog.
- **A duration written as a timecode is read correctly.** `0:20` was parsed as **zero
  seconds**, silently, in both editions.
- **No more error window when closing PANDORA** (a worker tested after its C++ object
  had been destroyed).
- Text-AI errors name the right provider — a spent text account no longer sends you
  to top up fal.ai. Extraction ceiling raised to 16 000 tokens. Depth-of-field column
  and setting ported to Live. The breakdown is validated, retried once, and refused
  rather than saved broken. Musical analysis and the director's note now reach Live
  co-writing.

---

## What's new in v2.0.1

A fast fix for a data-loss bug found in 2.0.0, worth its own release.

- **The shot breakdown is never silently truncated again.** On a feature-length
  screenplay the engine hit its output limit and stopped mid-document — at shot 28,
  about half the script. Because the contract validates each shot independently, a
  half-document whose shots are all well-formed passed without a single error, and
  PANDORA saved half a film believing it was done. The cut is now **detected** and
  the continuation requested automatically (up to six rounds), or the breakdown is
  **refused with an explicit message** — a partial breakdown is worse than none.
  Same fix on the Live layout.
- **The "Support PANDORA" PayPal button works.** It pointed at PayPal's donation
  endpoint, which is reserved for registered charities and always answered "this
  organization can't accept donations". It now uses a PayPal.me link.

Everyone on 2.0.0 should update.

---

## What's new in v2.0.0

**A major release — the prompt is no longer one text sent to every engine.**

Until now, the same prompt went out to every video and image engine, and each one
understood it its own way. PANDORA now **rewrites your shot in the writing style of
the engine that will receive it** — and shows you on screen, editable, the exact text
that will be sent. That single change reaches every generation in the app, which is
why this is a 2.0.

### The prompt, rebuilt end to end

- **Written in the grammar of the chosen engine.** Named `Camera / Lighting / Motion /
  Sound` lines for Seedance, one continuous sentence for Veo and Sora, a short action
  directive for Kling, dense prose for the rest. Switching engines reassembles the
  prompt on its own; if you edited the text by hand, your version is adapted, never
  overwritten.
- **Same rule for images**, everywhere in the app: a named-field brief for Nano Banana
  and GPT Image, plain descriptive prose with no negatives at all for Seedream (its API
  dropped negative prompts — writing "no person" there asks for a person), a structured
  object for FLUX.2.
- **What you see is what is sent.** Select a shot and the box fills with the final
  English prose, everything PANDORA adds written out in plain sight. Edit it word by
  word — nothing is re-glued or re-translated afterwards, alone or in a batch.
- **Your project sheets actually reach the engine.** Character appearance, sets, props,
  costumes and vehicles present in the shot are now written into the prompt. No more
  engine inventing a character it only knew by name.
- **The film's visual style is carried from screenplay to engine** — captured as a
  visible, editable section on every shot, translated, and placed at the end of the
  prompt where engines follow it best. Existing storyboards must be regenerated to
  benefit.
- **Every camera setting travels.** Shot size, axis, focal length, depth of field,
  distance, height and speed used to stop at the Storyboard. They are translated and
  injected now, with an explicit *locked-off* when there is no movement.
- **Nothing video-only in an image prompt** — camera movement, height, speed, duration
  and sound are stripped out (in French and English), and the shot's time of day becomes
  a lighting intention instead of a raw word.
- **Forbidden things become positive descriptions** for engines that cannot express a
  negative, and **studio or franchise names are removed** from the payload while the
  style descriptors that actually produce the look are kept.
- **Dialogue is written in the shot's language**, and a **composed prompt is never paid
  for twice** — come back to a shot you already prepared and it is reused as is.

### A different AI engine for each task

Assign a model per use: screenplay writing, shot breakdown, storyboard chat, video
prompt, translation, art direction, vision analysis. Ready-made per-task profiles for
Anthropic and ChatGPT, a button that lists only the models your keys really unlock, and
support for a custom provider or a local server. **When something fails, the real reason
is shown** — an exhausted credit balance now says so instead of a vague "unavailable".

### Screenplay and shot breakdown

- **The breakdown became a series of shot sheets** — the exact screenplay excerpt,
  intent, pace, duration, visual prompt and characters present, each shot revisable in
  co-writing before anything is sent. Old breakdowns are converted automatically.
- **A dedicated Director's Notes tab** separates craft intentions (visual style, light,
  rhythm, camera grammar, continuity, sound) from the narrative text — and passes them
  to the breakdown untouched.
- **Co-writing is saved and restored** when you reopen the project, and the storyboard
  assistant answers in full while driving more columns.
- **New Depth of field column** in the Storyboard, and the whole chain
  screenplay → notes → breakdown → storyboard is now shown as a chain.

### Images and elements

- **Every element gets a canonical visual identity** deduced from its active image and
  editable by hand — change the active image and PANDORA offers to update the shots
  where that element appears. Continuity no longer rests on your memory.
- **Fourteen image engines, selectable everywhere** — in Storyboard and Live moods and
  in all five element sheets, where there used to be two or six. Seedream 5 Pro joins
  the catalogue.
- **Guaranteed white background** on casting, props, costumes and vehicles: these sheets
  are sent back as references to the video engine, where a stray set would contaminate
  the shot.
- **Outpaint an image to your target ratio** without cropping anything, **seven matched
  views for each set**, an **art-direction chat inside element sheets**, engine and
  variant **comparison in one command**, drag-and-drop references, and a new **Arri 65**
  image style.

### Interface

A new home screen and illustrated project wall, right-click on a project thumbnail to
rename, duplicate or delete, a single **Action** menu on every page, the lighting plan
turned into a real workstation synchronised both ways with the storyboard, and the mouse
wheel no longer changes a setting by accident.

### Reliability

French no longer leaks into prompts (four separate leaks closed, including a translator
that answered instead of translating), your prompt edits are not lost, image generation
no longer freezes or crashes, and large folders and image-heavy pages open instantly.

### Live / mapping

The Live edition follows the Cinéma one: same reworked interface, same shot sheets, same
per-engine mood prompts, same fixes.

> Previous release (v1.3.5): low-cost video provider, imported photos in element sheets,
> exact-fidelity reproduction, friendlier first launch. Full history: [Releases](../../releases).

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

1. Download `PANDORA_Setup_2.1.0.exe` from the link above and run it
2. If Windows shows *"Windows protected your PC"* (SmartScreen), click
   **More info** then **Run anyway** — the app is not code-signed yet
   (certificate in progress), this is the Windows equivalent of the macOS
   notice below
3. Follow the installer and accept the Terms of Use
4. Launch **PANDORA** from the Start menu or desktop shortcut
5. Enter your API keys in **Settings** (optional)

### macOS

1. Download `PANDORA_2.1.0.dmg` from the link above
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
