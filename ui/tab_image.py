"""
ui/tab_image.py — Onglet « Image IA » du Studio IA PANDORA | Cinéma.

Embarque le panneau de l'app autonome Studio Images (studio_images/) SANS le
dupliquer : `StudioImagesPanel` est la SOURCE UNIQUE, partagée entre l'app
autonome (`python studio_images/main.py`) et cet onglet. Travailler sur Studio
Images fait donc évoluer l'onglet Image IA, et réciproquement.

studio_images utilise des imports « à plat » (import config, engines, …) : on
ajoute son dossier au sys.path avant d'importer le panneau. Aucun de ces noms
n'entre en collision avec le package PANDORA (qui importe en core.* / ui.*).
"""

import os
import sys

from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel

_STUDIO_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "studio_images")


def _load_panel():
    """Importe StudioImagesPanel + sa feuille de style depuis studio_images/.
    Retourne (PanelClass, stylesheet) ou (None, "") si indisponible."""
    if _STUDIO_DIR not in sys.path:
        sys.path.insert(0, _STUDIO_DIR)
    try:
        from window import StudioImagesPanel   # studio_images/window.py
        try:
            from styles import STYLESHEET as _SS   # studio_images/styles.py
        except Exception:
            _SS = ""
        return StudioImagesPanel, _SS
    except Exception:
        return None, ""


class TabImage(QWidget):
    """Onglet Image IA — hôte du StudioImagesPanel partagé."""

    def __init__(self):
        super().__init__()
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)

        PanelClass, stylesheet = _load_panel()
        if PanelClass is None:
            err = QLabel(
                "Studio Images est indisponible.\n"
                "Vérifie le dossier studio_images/ à la racine du projet.")
            err.setWordWrap(True)
            err.setContentsMargins(28, 28, 28, 28)
            lay.addWidget(err)
            self.panel = None
            return

        self.panel = PanelClass()
        # Applique la feuille de style de Studio Images au panneau (rendu fidèle
        # à l'app autonome, sans toucher au thème global de PANDORA).
        if stylesheet:
            self.panel.setStyleSheet(stylesheet)
        lay.addWidget(self.panel)
