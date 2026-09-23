"""ui/dialog_comfy_install.py — « ComfyUI n'est pas joignable. »

Depuis le 24/09/2026 c'est la fenêtre GÉNÉRIQUE des modules externes
(ui/dialog_external) ouverte sur ComfyUI : état (installé ? lancé ? modèles
H3 présents ?), marche à suivre, et ce que PANDORA fait lui-même —
télécharger l'installeur officiel et le lancer, déposer les cinq modèles H3
dans le dossier de ComfyUI, ouvrir ComfyUI Desktop. Le nom de classe reste
pour les onglets qui l'ouvrent au clic « Générer ».

Décision Matthieu 2026-09-13 : ce sont les utilisateurs qui installent ;
la fenêtre guide et, depuis le 24/09, fait le téléchargement pour eux — mais
n'exécute jamais rien sans un clic.
"""

from __future__ import annotations

from ui.dialog_external import ExternalDialog


class ComfyInstallDialog(ExternalDialog):
    """`is_ready()` : un serveur ComfyUI répond maintenant."""

    def __init__(self, parent=None, status=None):
        super().__init__("comfyui", parent, status)
