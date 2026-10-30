"""ui/dictation_panel.py — Réglage « Dictée vocale (ORAKLE) » des Paramètres.

Même composant dans les Paramètres Cinéma et Live (module neutre) : une case pour
afficher ou masquer le micro des champs de texte (config `dictation_enabled`,
appliquée tout de suite), les raccourcis, et l'état du moteur embarqué (modèle
Whisper présent ou à télécharger, réglages d'ORAKLE repris ou non).
"""
from __future__ import annotations

from PyQt6.QtWidgets import QCheckBox, QLabel, QVBoxLayout, QWidget

from core import dictation as dict_core
from core.i18n import translate
from ui.styles import CP


def status_text() -> str:
    if not dict_core.engine_available():
        return translate("Le moteur de dictée n'est pas présent dans cette installation.")
    from orakle_engine import VERSION
    cfg = dict_core.settings()
    name = cfg.get("model", "small")
    if dict_core.model_cached(name):
        model = translate("modèle Whisper « {name} » prêt").format(name=name)
    else:
        model = translate(
            "modèle Whisper « {name} » téléchargé à la première dictée ({size} Mo environ)"
        ).format(name=name, size=dict_core.model_size_mb(name) or "?")
    origin = (translate("réglages et dictionnaire d'ORAKLE repris")
              if dict_core.orakle_installed()
              else translate("réglages par défaut d'ORAKLE (français, anglais, espagnol)"))
    return (translate("Moteur ORAKLE {v} intégré").format(v=VERSION) + " · " + model
            + " · " + origin + ". "
            + translate("Tout reste sur cet ordinateur."))


class DictationPanel(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet("background:transparent;")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(6)

        self.check = QCheckBox("Micro de dictée dans les champs de texte")
        self.check.setChecked(dict_core.is_enabled())
        self.check.setStyleSheet(
            f"QCheckBox{{color:{CP['text_primary']};font-size:12px;background:transparent;}}")
        self.check.toggled.connect(self._on_toggled)
        lay.addWidget(self.check)

        from ui.dictation import tooltip_text
        lines = tooltip_text().split("\n")[1:]
        self.help = QLabel("\n".join(lines))
        self.help.setWordWrap(True)
        self.help.setStyleSheet(
            f"color:{CP['text_secondary']};font-size:11px;background:transparent;border:none;")
        lay.addWidget(self.help)

        self.status = QLabel(status_text())
        self.status.setWordWrap(True)
        self.status.setStyleSheet(
            f"color:{CP['text_dim']};font-size:10px;background:transparent;border:none;")
        lay.addWidget(self.status)

        available = dict_core.engine_available()
        self.check.setEnabled(available)
        self.help.setVisible(available)

    def _on_toggled(self, enabled: bool) -> None:
        dict_core.set_enabled(enabled)
        from ui.dictation import controller
        ctl = controller()
        if ctl is not None:
            ctl.set_enabled(enabled)
