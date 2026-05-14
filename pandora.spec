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

a = Analysis(
    ["main.py"],
    pathex=["."],
    binaries=[],
    datas=[
        # Tout le dossier assets (icônes, badges, style_refs, svg)
        ("assets", "assets"),
        # Charte d'utilisation (lue par dialog_eula.py via sys._MEIPASS)
        ("EULA.txt", "."),
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
