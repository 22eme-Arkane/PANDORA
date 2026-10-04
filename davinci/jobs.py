"""
Appels au pont DaVinci HORS du thread de l'interface, et état de connexion
partagé par toute l'application (Cinéma uniquement — le Live n'importe jamais
davinci.*).

Avant (audit du 04/10/2026) : chaque rafraîchissement faisait jusqu'à trois
allers-retours TCP sur le thread de l'interface, et l'import après génération
y attendait la réponse de Resolve. Le panneau des Paramètres émettait
`status_changed` sans que personne ne l'écoute : la barre du Studio et la case
« Import auto » ne suivaient pas une connexion faite ailleurs.
"""

from PyQt6.QtCore import QObject, pyqtSignal

from core.background import BackgroundTask as DaVinciJob, run_task as run_job  # noqa: F401


class _StatusHub(QObject):
    """Prévient tous les écrans quand l'état du pont a changé."""
    changed = pyqtSignal()


_HUB = None


def hub() -> _StatusHub:
    """À appeler depuis le thread de l'interface (les écrans s'y abonnent à leur
    construction) : l'objet doit naître sur ce thread."""
    global _HUB
    if _HUB is None:
        _HUB = _StatusHub()
    return _HUB


def notify():
    """Signale un changement d'état. Sans abonné (aucun écran construit), rien à
    faire — et surtout ne pas créer le hub depuis un thread de travail."""
    if _HUB is None:
        return
    try:
        _HUB.changed.emit()
    except Exception:
        pass
