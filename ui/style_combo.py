"""Remplissage partagé des listes « Style d'image ».

Toutes les fenêtres qui génèrent une image (décors, casting, accessoires,
HMC, véhicules, Image IA) proposaient la même liste, construite cinq fois à
l'identique. Elle est désormais construite ICI, avec en TÊTE l'entrée
« Style de la note de réalisation » (demande Matthieu 2026-07-31) : plutôt
que de re-choisir un style figé dans chaque fenêtre, on reprend le style
visuel écrit dans la note de réalisation, relu EN DIRECT à chaque
génération — réécrire la note change le style de la génération suivante.

L'entrée de tête est sélectionnée PAR DÉFAUT quand la note décrit
réellement un style ; sinon la liste retombe sur l'ancien défaut (le style
du projet), pour ne jamais promettre un style qui n'existe pas.
"""

from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor

from ui.styles import CP
from core.i18n import translate
import core.style as style_api


NOTE_KEY = style_api.NOTE_STYLE_KEY
NOTE_LABEL = "📝  Style de la note de réalisation"
NOTE_TOOLTIP = (
    "Reprend le STYLE VISUEL écrit dans la note de réalisation (page "
    "Scénario). Relu à chaque génération : modifier la note change le style."
)


def populate(combo, first_label: str = "— Style du projet —",
             first_key: str = "", saved_key: str | None = None,
             accent_key: str = "accent2", select_default: bool = True) -> None:
    """Remplit un QComboBox de styles : note de réalisation, entrée neutre,
    puis les styles groupés par famille (en-têtes non sélectionnables).

    `saved_key` = clé persistée de l'élément édité. Quand elle est absente,
    la sélection par défaut est la note de réalisation SI elle décrit un
    style, sinon le style du projet.

    `select_default=False` : laisse le combo sur l'entrée neutre — pour les
    appelants qui posent eux-mêmes la sélection après coup (page Scénario,
    qui la lit dans le scénario chargé).
    """
    combo.clear()
    has_note = style_api.has_note_visual_style()
    combo.addItem(translate(NOTE_LABEL), NOTE_KEY)
    note_item = combo.model().item(0)
    note_item.setForeground(QColor(CP.get("accent", "#4ecdc4")))
    tip_role = Qt.ItemDataRole.ToolTipRole
    if not has_note:
        # Laissée VISIBLE mais désactivée : l'utilisateur voit l'option
        # exister et comprend qu'il doit écrire la note pour s'en servir.
        note_item.setEnabled(False)
        combo.setItemData(0, translate(
            "Aucun style visuel dans la note de réalisation — "
            "écris-le dans la page Scénario."), tip_role)
    else:
        combo.setItemData(0, translate(NOTE_TOOLTIP), tip_role)
    combo.addItem(translate(first_label), first_key)

    current_group = None
    for style in style_api.STYLES:
        group = style.get("group", "")
        if group != current_group:
            current_group = group
            info = next((g for g in style_api.GROUPS if g["key"] == group), None)
            if info:
                combo.addItem(f"  {info['icon']}  {translate(info['name']).upper()}",
                              "__sep__")
                header = combo.model().item(combo.count() - 1)
                header.setEnabled(False)
                header.setForeground(QColor(CP.get(accent_key, "#7c6bff")))
        combo.addItem(f"    {style['icon']}  {translate(style['name'])}", style["key"])

    if not select_default:
        select_key = first_key
    else:
        select_key = saved_key if saved_key else (
            NOTE_KEY if has_note else style_api.get_style_key())
    if select_key == NOTE_KEY and not has_note:
        select_key = style_api.get_style_key()
    if select_key:
        for i in range(combo.count()):
            if combo.itemData(i) == select_key:
                combo.setCurrentIndex(i)
                return
    # Clé inconnue (style supprimé) → entrée neutre, jamais un en-tête.
    for i in range(combo.count()):
        if combo.itemData(i) == first_key:
            combo.setCurrentIndex(i)
            return


def suffix_for(combo, no_cam: bool = False) -> str:
    """Suffixe d'image correspondant à la sélection courante du combo."""
    key = combo.currentData() if combo is not None else ""
    return style_api.image_suffix_for_key(key or "", no_cam=no_cam)
