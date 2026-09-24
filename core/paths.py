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


def assets_root() -> str:
    """Racine des fichiers LIVRÉS avec PANDORA (assets/ : icônes, gabarits
    ComfyUI…) — à ne pas confondre avec APP_ROOT, qui est le dossier de
    DONNÉES en version installée (%LOCALAPPDATA%\\PANDORA).

    ⚠ Constat Matthieu 24/09/2026 sur l'installeur 2.4.0 : les gabarits H3
    de ComfyUI étaient cherchés sous APP_ROOT → « Aucun workflow ComfyUI »
    à chaque génération, alors que les .json étaient bien dans _internal/.
    En gelé, PyInstaller dépose assets/ dans sys._MEIPASS (= _internal/) ;
    en développement c'est le dossier du projet. Évalué à l'appel (pas à
    l'import) pour rester testable en simulant le mode gelé."""
    if getattr(sys, "frozen", False):
        return getattr(sys, "_MEIPASS", os.path.dirname(sys.executable))
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
