"""
ui/element_io_buttons.py — Boutons « Sauvegarder » / « Ouvrir » réutilisables.

Ajoute aux pages éléments (Castings, Décors, Accessoires, HMC, Véhicules) les
deux boutons fichier, sur le même principe et le même style que le storyboard
(💾 jaune / 📂 bleu). Toute la plomberie (QFileDialog, confirmation, messages,
refresh) est centralisée ici — chaque page n'appelle que
make_save_open_buttons(...) et place les deux boutons à côté de sa barre de
recherche.

S'appuie sur core.element_io (pur, sans UI) pour la (dé)sérialisation.
"""

import os

from PyQt6.QtWidgets import QPushButton, QFileDialog, QMessageBox, QWidget

from ui.styles import CP
from core.i18n import translate
import core.element_io as eio
from core import context as _ctx

_YELLOW, _BLUE = "#f5c518", "#4aa3ff"
_RGBA = {_YELLOW: "245,197,24", _BLUE: "74,163,255"}


def toolbar_separator() -> QWidget:
    """Petite barre verticale (style Storyboard) pour séparer le groupe fichier
    (Sauvegarder/Ouvrir) du bouton « Créer » dans les toolbars des pages éléments."""
    s = QWidget()
    s.setFixedWidth(1)
    s.setFixedHeight(24)
    s.setStyleSheet(f"background:{CP['border_bright']};")
    return s


def _btn(text: str, color: str) -> QPushButton:
    b = QPushButton(text)
    b.setFixedHeight(36)
    b.setStyleSheet(
        f"QPushButton{{background:transparent;color:{color};"
        f"border:1px solid {color};border-radius:8px;font-size:11px;font-weight:700;padding:0 14px;}}"
        f"QPushButton:hover{{background:rgba({_RGBA[color]},0.12);}}"
        f"QPushButton:pressed{{background:rgba({_RGBA[color]},0.22);}}"
    )
    return b


def make_save_open_buttons(page, *, kind, list_fn, save_fn, delete_fn, refresh_fn):
    """Crée et renvoie (btn_save, btn_open) câblés.

    `page`      : widget parent des boîtes de dialogue.
    `kind`      : type machine ('casting'/'decors'/'accessories'/'hmc'/'vehicles').
    list/save/delete_fn : callables du module métier de la page.
    refresh_fn  : méthode à appeler après une ouverture réussie.
    """
    btn_save = _btn("💾  " + translate("Sauvegarder"), _YELLOW)
    btn_save.setToolTip(translate("Sauvegarder dans un fichier"))
    btn_open = _btn("📂  " + translate("Ouvrir"), _BLUE)
    btn_open.setToolTip(translate("Ouvrir depuis un fichier"))

    def _suggested_name() -> str:
        proj = _ctx.get_project_name() or "PANDORA"
        return f"{proj} - {eio.file_suffix(kind)}.json"

    def _on_save():
        items = list(list_fn() or [])
        if not items:
            QMessageBox.information(page, translate("Sauvegarder"),
                                    translate("Rien à sauvegarder."))
            return
        # Démarre dans le dossier DÉDIÉ du type (Casting / Décors / Accessoires /
        # HMC / Véhicules), pas dans la racine du projet.
        start = os.path.join(eio.saves_dir(kind), _suggested_name())
        path, _ = QFileDialog.getSaveFileName(
            page, translate("Sauvegarder"), start, "PANDORA (*.json)")
        if not path:
            return
        if not path.lower().endswith(".json"):
            path += ".json"
        try:
            eio.export_items(path, kind, items)
            QMessageBox.information(page, translate("Sauvegardé"),
                                    translate("Sauvegardé."))
        except Exception as e:
            QMessageBox.critical(page, translate("Erreur"), str(e))

    def _on_open():
        path, _ = QFileDialog.getOpenFileName(
            page, translate("Ouvrir"), eio.saves_dir(kind), "PANDORA (*.json)")
        if not path:
            return
        if QMessageBox.question(
                page, translate("Ouvrir"),
                translate("Charger ce fichier ? Les éléments actuels seront remplacés."),
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        ) != QMessageBox.StandardButton.Yes:
            return
        try:
            n = eio.import_items(path, kind, list_fn, save_fn, delete_fn)
            refresh_fn()
            QMessageBox.information(page, translate("Ouvert"),
                                   translate("{n} élément(s) chargé(s).").format(n=n))
        except Exception as e:
            QMessageBox.critical(page, translate("Erreur"), str(e))

    btn_save.clicked.connect(_on_save)
    btn_open.clicked.connect(_on_open)
    return btn_save, btn_open
