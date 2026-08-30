"""ui/audio_preview.py — Lecture d'un extrait audio DANS l'application.

Partout ailleurs, PANDORA ouvre l'audio dans le lecteur du système
(`QDesktopServices`). C'est acceptable pour un rendu qu'on va garder ; c'est
insupportable pour comparer des voix, où chaque écoute ouvrirait une fenêtre
de plus.

On utilise donc QtMultimedia — avec un repli. QtMultimedia dépend de
composants système (Media Foundation sous Windows) qui peuvent manquer dans un
build gelé : si l'import ou la lecture échoue, on retombe sur le lecteur
externe plutôt que d'avaler l'erreur. Le bouton fait toujours quelque chose.
"""

from __future__ import annotations

import os

from PyQt6.QtCore import QUrl
from PyQt6.QtGui import QDesktopServices

# Le lecteur est un singleton de module : un QMediaPlayer détruit par le
# ramasse-miettes en pleine lecture coupe le son, et Qt n'en avertit pas.
_player = None
_output = None
_unavailable = False


def _ensure_player():
    """Instancie le lecteur au premier besoin. Renvoie None si QtMultimedia
    n'est pas exploitable ici — l'appelant retombe alors sur le système."""
    global _player, _output, _unavailable
    if _unavailable:
        return None
    if _player is not None:
        return _player
    try:
        from PyQt6.QtMultimedia import QAudioOutput, QMediaPlayer
        _output = QAudioOutput()
        _output.setVolume(1.0)
        _player = QMediaPlayer()
        _player.setAudioOutput(_output)
        return _player
    except Exception:
        _unavailable = True
        return None


def is_inline_available() -> bool:
    """Vrai si la lecture peut se faire dans l'application."""
    return _ensure_player() is not None


def play(path: str) -> bool:
    """Joue un fichier. Renvoie True si la lecture s'est faite dans l'app,
    False si elle a été confiée au lecteur du système."""
    if not path or not os.path.isfile(path):
        return False
    p = _ensure_player()
    if p is None:
        QDesktopServices.openUrl(QUrl.fromLocalFile(path))
        return False
    try:
        p.stop()                       # une écoute annule la précédente
        p.setSource(QUrl.fromLocalFile(path))
        p.play()
        return True
    except Exception:
        QDesktopServices.openUrl(QUrl.fromLocalFile(path))
        return False


def stop() -> None:
    """Coupe la lecture en cours, s'il y en a une."""
    if _player is not None:
        try:
            _player.stop()
        except Exception:
            pass
