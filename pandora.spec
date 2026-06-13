# -*- mode: python ; coding: utf-8 -*-
#
# pandora.spec — PyInstaller build spec for PANDORA v1.0.0
#
# Prérequis :
#   python tools/make_ico.py     # génère assets/pandora_badge.ico
#   pip install pyinstaller
#   pyinstaller pandora.spec     # produit dist/PANDORA/

import os

block_cipher = None

_ICO = os.path.join("assets", "pandora_badge.ico")

# Binaires ffmpeg — inclus s'ils sont présents dans le dossier racine du projet.
# build.ps1 les télécharge automatiquement avant de lancer PyInstaller.
_FFMPEG_BINS = [
    (exe, ".")
    for exe in ("ffmpeg.exe", "ffprobe.exe")
    if os.path.isfile(exe)
]

a = Analysis(
    ["main.py"],
    pathex=["."],
    binaries=_FFMPEG_BINS,
    datas=[
        # Tout le dossier assets (icônes, badges, style_refs, svg)
        ("assets", "assets"),
        # Chartes d'utilisation FR + EN (lues par dialog_eula.py via sys._MEIPASS)
        ("EULA.txt", "."),
        ("EULA_EN.txt", "."),
        # Scripts DaVinci — copiés dans Fusion/Scripts/Utility par PANDORA
        ("davinci/bridge_server.py", "davinci"),
        ("davinci/pandora_send.py",  "davinci"),
    ],
    hiddenimports=[
        # Pillow
        "PIL",
        "PIL._imaging",
        "PIL.Image",
        "PIL.PngImagePlugin",
        "PIL.JpegImagePlugin",
        # Réseau (anthropic / fal-client)
        "httpx",
        "httpcore",
        "httpcore._async",
        "httpcore._sync",
        "anyio",
        "anyio._backends._asyncio",
        "sniffio",
        "h11",
        "certifi",
        "charset_normalizer",
        "urllib3",
        "idna",
        # fal_client
        "websockets",
        "aiofiles",
        # Anthropic
        "anthropic",
        "anthropic._streaming",
        # PyQt6
        "PyQt6.sip",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        "tkinter",
        "matplotlib",
        "numpy",
        "scipy",
        "pandas",
        "IPython",
        "jupyter",
        "pytest",
        "setuptools",
        # ── PANDORA | Live — JAMAIS dans le build Cinéma (v1.2.0) ──────────────
        # Aucun module Live n'est packagé : main.py détecte l'absence de
        # live_window (core.edition.is_cinema_only) et saute le sélecteur de
        # module. Les rares imports Live dans des fichiers partagés (main.py,
        # api/apercu.py) sont conditionnels et jamais atteints en Cinéma.
        "live_window",
        "ui.chooser",
        "ui.live_pages", "ui.live_studio_widget",
        "ui.page_live", "ui.page_live_assets", "ui.page_live_conducteur",
        "ui.page_live_placeholder", "ui.page_live_sequence",
        "ui.page_live_sequences", "ui.page_live_settings",
        "ui.page_scenario_live", "ui.page_storyboard_live",
        "ui.page_castings_live", "ui.page_accessories_live",
        "ui.page_vehicles_live", "ui.page_projects_live",
        "ui.tab_t2v_live", "ui.tab_video_engines_live", "ui.tab_history_live",
        "ui.tab_video_library_live", "ui.tab_modify_live",
        "ui.tab_sound_design_live", "ui.tab_upscale_live",
        "ui.assistant_panel_live", "ui.dialog_user_manual_live",
        "ui.dialog_contact_live", "ui.dialog_shot_live",
        "core.live_assets", "core.live_building", "core.live_conducteur",
        "core.live_mapping", "core.live_sequences", "core.music_align",
        "core.vj_styles",
        "api.live_extract", "api.live_refs", "api.live_screenplay",
        "api.resolume_push",
        "resolume", "resolume.client",
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="PANDORA",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=_ICO if os.path.isfile(_ICO) else None,
    version_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=["vcruntime*.dll", "api-ms-*.dll"],
    name="PANDORA",
)
