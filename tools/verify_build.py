"""Vérification post-build du bundle PANDORA (dist/PANDORA).

Depuis la v1.3.0 (double édition), le build doit :
  1. CONTENIR les modules Live (live_window, copies *_live, resolume…) ;
  2. contenir les modules Cinéma habituels (témoins) ;
  3. ne contenir AUCUN fichier sensible (config.json, studio_images/refs…) ;
  4. embarquer ffmpeg/ffprobe.

Usage :  python tools/verify_build.py  [dist/PANDORA]
Sortie : OK/ECHEC par contrôle + code retour 0/1.
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DIST = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, "dist", "PANDORA")
EXE  = os.path.join(DIST, "PANDORA.exe")

failures = []


def check(label: str, ok: bool, detail: str = ""):
    print(f"  {'OK   ' if ok else 'ECHEC'} {label}{('  — ' + detail) if detail else ''}")
    if not ok:
        failures.append(label)


print(f"Bundle : {DIST}")
check("PANDORA.exe présent", os.path.isfile(EXE))

# ── 1+2. Modules du PYZ embarqué ──────────────────────────────────────────────
LIVE_WITNESSES   = ["live_window", "ui.tab_t2v_live", "ui.page_scenario_live",
                    "ui.live_pages", "core.live_mapping", "resolume.client",
                    "api.resolume_push", "core.music_align"]
CINEMA_WITNESSES = ["ui.pandora_window", "ui.tab_t2v", "ui.storyboard_chat",
                    "core.pitch_deck", "api.tts", "api.upscale",
                    "window", "engines"]   # studio_images (embarqué à plat)
try:
    from PyInstaller.archive.readers import CArchiveReader, ZlibArchiveReader
    arch = CArchiveReader(EXE)
    pyz_name = next(n for n in arch.toc if n.endswith(".pyz"))
    import tempfile
    with tempfile.TemporaryDirectory() as td:
        pyz_path = os.path.join(td, "embedded.pyz")
        with open(pyz_path, "wb") as f:
            f.write(arch.extract(pyz_name))
        pyz = ZlibArchiveReader(pyz_path)
        mods = set(pyz.toc.keys())
    for m in LIVE_WITNESSES:
        check(f"Live embarqué : {m}", m in mods)
    for m in CINEMA_WITNESSES:
        check(f"Cinéma embarqué : {m}", m in mods)
except Exception as e:
    check("lecture du PYZ embarqué", False, f"{e.__class__.__name__}: {e}")

# ── 3. Aucune fuite sensible ─────────────────────────────────────────────────
INTERNAL = os.path.join(DIST, "_internal")
for leak in ("data/config.json", "config.json", "studio_images/config.json",
             "studio_images/prompts.json", "studio_images/refs", "refs"):
    p = os.path.join(INTERNAL, *leak.split("/"))
    check(f"absent du bundle : {leak}", not os.path.exists(p))

# style_refs : les dossiers peuvent exister mais VIDES de fichiers
sr = os.path.join(INTERNAL, "assets", "style_refs")
n_imgs = sum(len(fs) for _, _, fs in os.walk(sr)) if os.path.isdir(sr) else 0
check("style_refs sans images de dev", n_imgs == 0, f"{n_imgs} fichier(s)")

# ── 4. ffmpeg embarqué + icônes Live conservées ──────────────────────────────
check("ffmpeg.exe embarqué", os.path.isfile(os.path.join(DIST, "ffmpeg.exe"))
      or os.path.isfile(os.path.join(INTERNAL, "ffmpeg.exe")))
check("ffprobe.exe embarqué", os.path.isfile(os.path.join(DIST, "ffprobe.exe"))
      or os.path.isfile(os.path.join(INTERNAL, "ffprobe.exe")))
icons = os.path.join(INTERNAL, "assets", "icons")
check("icône Live conservée (double édition)",
      os.path.isfile(os.path.join(icons, "Live.png")))

print()
if failures:
    print(f"ECHEC : {len(failures)} contrôle(s) → {failures}")
    sys.exit(1)
print("BUILD VÉRIFIÉ : double édition complète, aucune fuite.")
