"""
core/edition.py — Édition courante de PANDORA (Cinéma seule vs. Cinéma + Live).

La détection reste utile aux éventuelles éditions Cinéma seules : si
`live_window` n'est pas importable, la carte Live de la page de démarrage unifiée
reste visible mais désactivée. Quand le module est présent, les deux modes sont
sélectionnables sur cette même page, sans écran intermédiaire.
"""

import importlib.util


def is_cinema_only() -> bool:
    """True si le module Live n'est pas packagé (édition Cinéma seule)."""
    try:
        return importlib.util.find_spec("live_window") is None
    except (ImportError, ValueError):
        return True
