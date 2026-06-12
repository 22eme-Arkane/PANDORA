"""
ui/dialog_contact_live.py — PANDORA | Live : divergence LÉGÈRE de Cinéma.

Même dialogue que ui/dialog_contact.py, mais la communauté WhatsApp est celle
de PANDORA | Live (retour Matthieu 2026-06-12 : le dialogue affichait encore
le groupe Cinéma). La classe Cinéma expose _WA_GROUP/_WA_LINK pour cette
surcharge — toute autre évolution du dialogue reste héritée de Cinéma.
"""

from ui.dialog_contact import ContactDialog as _ContactDialogCinema


class ContactDialog(_ContactDialogCinema):
    _WA_GROUP = "PANDORA | Live"
    _WA_LINK  = "https://chat.whatsapp.com/LEVinbwbtOv3yn8zr8zWPL"
