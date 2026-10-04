"""
ui/compose_controls.py — « Recomposer le prompt » + case « automatique ».

Demande Matthieu du 04/10/2026 : la recomposition du prompt par l'IA partait
toute seule — à l'ouverture d'un Mood, à la sélection d'un plan dans le Studio —
avec parfois un refus (« composition refusée : information perdue… »). Il veut
UN BOUTON pour la lancer quand il le décide, et À CÔTÉ une case pour qu'elle se
fasse automatiquement — réglage MÉMORISÉ : qui veut l'automatique le coche une
fois, qui n'en veut pas n'a plus à décocher à chaque fois.

Composant neutre (Mood, Studio Cinéma, Studio Live) : chaque écran a SA clé de
config (« mood_auto_compose », « studio_auto_compose »). Défaut : automatique
(le comportement d'avant), pour que rien ne change sans que l'utilisateur le
décide.
"""
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import QCheckBox, QHBoxLayout, QPushButton, QWidget

from core.i18n import translate
from ui.styles import CP


def auto_compose_enabled(config_key: str) -> bool:
    """Le réglage mémorisé (vrai par défaut : comportement historique)."""
    try:
        from core.config import load_config
        v = load_config().get(config_key)
        return True if v is None else bool(v)
    except Exception:
        return True


class ComposeControls(QWidget):
    """Bouton « Recomposer » + case « Recomposer automatiquement »."""

    recompose_requested = pyqtSignal()
    auto_changed = pyqtSignal(bool)

    def __init__(self, config_key: str, parent=None, compact: bool = False):
        super().__init__(parent)
        self._key = config_key
        self.setStyleSheet("background:transparent;")
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(10)

        self.button = QPushButton(translate("✦  Recomposer le prompt"))
        self.button.setFixedHeight(24 if compact else 28)
        self.button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.button.setToolTip(translate(
            "Réécrit le prompt avec l'IA pour le moteur choisi (un appel payant). "
            "Votre texte retouché à la main sera remplacé."))
        self.button.setStyleSheet(
            f"QPushButton{{background:transparent;color:{CP['accent']};"
            f"border:1px solid {CP['accent']};border-radius:6px;"
            f"font-size:10px;font-weight:700;padding:0 10px;}}"
            f"QPushButton:hover{{background:rgba(78,205,196,0.12);}}"
            f"QPushButton:disabled{{color:{CP['text_dim']};border-color:{CP['border']};}}")
        self.button.clicked.connect(self.recompose_requested.emit)
        lay.addWidget(self.button)

        self.auto_cb = QCheckBox(translate("Recomposer automatiquement"))
        self.auto_cb.setToolTip(translate(
            "Coché : le prompt est réécrit par l'IA dès que le plan s'affiche. "
            "Décoché : seulement quand vous cliquez « Recomposer » — un prompt déjà "
            "composé reste affiché sans nouvel appel. Le choix est mémorisé."))
        self.auto_cb.setStyleSheet(
            f"QCheckBox{{color:{CP['text_secondary']};font-size:10px;background:transparent;}}")
        self.auto_cb.setChecked(auto_compose_enabled(config_key))
        self.auto_cb.toggled.connect(self._on_toggled)
        lay.addWidget(self.auto_cb)
        from PyQt6.QtWidgets import QLabel
        self._note = QLabel("")
        self._note.setStyleSheet(
            f"color:{CP['text_dim']};font-size:10px;font-style:italic;background:transparent;")
        lay.addWidget(self._note, 1)

    def is_auto(self) -> bool:
        return self.auto_cb.isChecked()

    def set_note(self, text: str):
        """Petite mention d'état à droite (texte déjà traduit, "" pour effacer)."""
        self._note.setText(text or "")

    def _on_toggled(self, on: bool):
        try:
            from core.config import load_config, save_config
            cfg = load_config()
            if cfg.get(self._key) != bool(on):
                cfg[self._key] = bool(on)
                save_config(cfg)
        except Exception:
            pass
        self.auto_changed.emit(bool(on))
