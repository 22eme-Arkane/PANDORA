# -*- mode: python ; coding: utf-8 -*-
#
# pandora.spec — PyInstaller build spec for PANDORA v1.2.1 (Cinéma)
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
    # studio_images/ contient l'app « Image IA » importée à plat (import config,
    # window, …) → on l'ajoute au chemin d'analyse pour résoudre ses modules.
    pathex=[".", "studio_images"],
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
        # ── Analyse musicale (Scénario → « Musiques du set ») ──────────────────
        # Moteur librosa PARTAGÉ avec PANDORA | Live, désormais embarqué dans le
        # build Cinéma pour le travail en clip (BPM + drops → découpage calé).
        # +~250 Mo assumés. numpy/scipy sont donc retirés des excludes ci-dessous.
        # NB : numba peut nécessiter un ajustement au build (hook PyInstaller).
        "numpy",
        "scipy",
        "scipy.signal",
        "librosa",
        "soundfile",
        "audioread",
        "lazy_loader",
        "pooch",
        "numba",
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
        # ── Modules importés LAZY (dans des fonctions) → invisibles à l'analyse
        #    statique de PyInstaller. À déclarer pour le build Cinéma (aucun n'importe
        #    de module Live). ──────────────────────────────────────────────────────
        "api.lipsync", "api.shot_lipsync", "core.dialogue",   # lip-sync Studio IA + DaVinci
        "api.face_swap",     # « Changer un visage / le décor » → Pixverse Swap
        "ui.file_dialogs",   # dialogues fichiers non-natifs + vignettes d'images
        # ── Studio Images (onglet « Image IA ») ───────────────────────────────
        # Modules importés à plat au runtime via sys.path.insert dans
        # ui/tab_image.py → invisibles à l'analyse statique de PyInstaller.
        # On les déclare explicitement (résolus via pathex="studio_images").
        # NB : config.json / refs / prompts.json NE sont PAS embarqués — ils
        # contiennent des clés API et des données de dev ; le code est
        # frozen-aware et les recrée dans %LOCALAPPDATA%\PANDORA\studio_images\.
        "window", "styles", "config", "engines", "imagegen",
        "prompts", "projects", "chat",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        "tkinter",
        "matplotlib",
        # numpy / scipy NE SONT PLUS exclus : requis par librosa pour l'analyse
        # musicale du Scénario (« Musiques du set »), feature partagée avec le Live.
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
