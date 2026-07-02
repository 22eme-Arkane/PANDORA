"""Chemin racine de PANDORA — résout dev vs. build gelé (PyInstaller).

Tous les modules core qui ont besoin de _ROOT doivent importer APP_ROOT depuis
ce module plutôt que de recalculer os.path.dirname(os.path.dirname(__file__)).

- Dev          : répertoire parent de core/ (le répertoire du projet)
- Gelé Windows : %LOCALAPPDATA%\\PANDORA\\ (inscriptible sans UAC, même depuis Program Files)
- Gelé macOS   : ~/Library/Application Support/PANDORA/ (équivalent Apple)
"""
import os
import sys

if getattr(sys, "frozen", False):
    if sys.platform == "darwin":
        APP_ROOT = os.path.expanduser("~/Library/Application Support/PANDORA")
    else:
        APP_ROOT = os.path.join(
            os.environ.get("LOCALAPPDATA", os.path.expanduser("~")), "PANDORA")
else:
    APP_ROOT = os.path.dirname(os.path.dirname(__file__))
