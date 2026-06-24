"""
core/edition.py — Édition courante de PANDORA (Cinéma seule vs. Cinéma + Live).

Le build distribué (≥ v1.2.0) NE CONTIENT QUE PANDORA Cinéma : le module Live
est exclu du paquet PyInstaller (voir pandora.spec). On le détecte au runtime
sans aucun flag manuel : si `live_window` n'est pas importable, on est en
édition Cinéma seule → main.py saute le sélecteur de module (pas de page
« Cinéma | Live ») et lance directement le Studio Cinéma.

En développement (live_window.py présent sur le disque), la détection renvoie
False → le sélecteur complet reste disponible pour continuer à développer Live.
"""

import importlib.util


def is_cinema_only() -> bool:
    """True si le module Live n'est pas packagé (build Cinéma) — pas de chooser."""
    try:
        return importlib.util.find_spec("live_window") is None
    except (ImportError, ValueError):
        return True
