# -*- mode: python ; coding: utf-8 -*-
#
# pandora.spec — PyInstaller build spec for PANDORA v1.3.0 (Cinéma + Live)
#
# Multi-plateforme : Windows (build.ps1) et macOS (.app via BUNDLE, compilé sur
# un runner GitHub Actions — PyInstaller ne cross-compile pas).
#
# Prérequis :
#   python tools/make_ico.py     # Windows : génère assets/pandora_badge.ico
#   python tools/make_icns.py    # macOS   : génère assets/pandora_badge.icns
#   pip install pyinstaller
#   pyinstaller pandora.spec     # produit dist/PANDORA/ (+ dist/PANDORA.app sur mac)

import os
import sys

block_cipher = None

_IS_MAC = sys.platform == "darwin"
_ICO  = os.path.join("assets", "pandora_badge.ico")
_ICNS = os.path.join("assets", "pandora_badge.icns")

# Binaires ffmpeg — inclus s'ils sont présents dans le dossier racine du projet.
# build.ps1 (Windows) / le workflow GitHub Actions (mac) les téléchargent avant
# de lancer PyInstaller. Sur mac les binaires n'ont pas d'extension .exe.
_FFMPEG_NAMES = ("ffmpeg", "ffprobe") if _IS_MAC else ("ffmpeg.exe", "ffprobe.exe")
_FFMPEG_BINS = [
    (exe, ".")
    for exe in _FFMPEG_NAMES
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
        # ── PANDORA | Live : INCLUS depuis la v1.3.0 (décision Matthieu
        #    2026-07-02 — « on enlève la séparation, le Live est prêt »).
        #    main.py détecte la présence de live_window (core.edition) et
        #    affiche le sélecteur Cinéma | Live au démarrage. Les modules Live
        #    sont atteints par imports littéraux depuis main.py → analyse
        #    statique PyInstaller suffisante, pas de hiddenimports requis. ──
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
    icon=(_ICNS if (_IS_MAC and os.path.isfile(_ICNS))
          else (_ICO if os.path.isfile(_ICO) else None)),
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

# macOS : paquet applicatif .app (le workflow GitHub Actions le met en DMG).
if _IS_MAC:
    app = BUNDLE(
        coll,
        name="PANDORA.app",
        icon=_ICNS if os.path.isfile(_ICNS) else None,
        bundle_identifier="com.arkane22eme.pandora",
        info_plist={
            "CFBundleShortVersionString": "1.3.3",
            "CFBundleVersion": "1.3.3",
            "NSHighResolutionCapable": True,
            "LSMinimumSystemVersion": "12.0",
        },
    )
