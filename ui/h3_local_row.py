"""
ui/h3_local_row.py — Rangée « MiniMax H3 en local » des Paramètres.

Composant NEUTRE (ni Cinéma ni Live), instancié tel quel par les deux pages
Paramètres, comme ui/projects_location_row.py. La logique vit dans
core/h3_local.py ; ici, uniquement l'affichage.

La rangée dit trois choses :
  · l'adresse du serveur local (par défaut celle du projet communautaire) ;
  · s'il répond en ce moment — un bouton le vérifie ;
  · ce que dit la licence des poids. Pas pour bloquer : pour que chacun
    décide en sachant.
"""
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton,
)

from core import h3_local as _h3l
from core.i18n import translate
from ui.styles import CP


class H3LocalRow(QWidget):
    """Champ URL + bouton « Tester » + état + avis de licence. Émet `changed(str)`."""

    changed = pyqtSignal(str)

    def __init__(self, parent=None, initial_url: str = ""):
        super().__init__(parent)
        self.setStyleSheet("background:transparent;")

        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(6)

        row = QHBoxLayout()
        row.setSpacing(8)

        self._field = QLineEdit()
        self._field.setFixedHeight(38)
        self._field.setPlaceholderText(
            translate("Adresse du serveur H3 local (défaut : ") + _h3l.DEFAULT_URL + ")")
        self._field.setText(initial_url or "")
        self._field.setStyleSheet(
            f"QLineEdit{{background:{CP['bg3']};border:1px solid {CP['border']};"
            f"border-radius:6px;color:{CP['text_primary']};font-size:11px;"
            f"font-family:'Consolas',monospace;padding:0 12px;}}"
            f"QLineEdit:focus{{border-color:{CP['accent']};}}"
        )
        self._field.editingFinished.connect(self._on_edited)
        row.addWidget(self._field, 1)

        self._btn = QPushButton(translate("Tester"))
        self._btn.setFixedHeight(38)
        self._btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn.setStyleSheet(
            f"QPushButton{{background:transparent;color:{CP['text_secondary']};"
            f"border:1px solid {CP['border']};border-radius:6px;"
            f"font-size:12px;font-weight:600;padding:0 18px;}}"
            f"QPushButton:hover{{background:{CP['bg3']};color:{CP['text_primary']};}}"
        )
        self._btn.clicked.connect(self._probe)
        row.addWidget(self._btn)
        lay.addLayout(row)

        self._state = QLabel(translate("Non vérifié — cliquez sur « Tester »."))
        self._state.setWordWrap(True)
        self._state.setStyleSheet(
            f"color:{CP['text_dim']};font-size:10px;background:transparent;border:none;")
        lay.addWidget(self._state)

        hint = QLabel(translate(
            "Installez le projet communautaire minimax-h3-local (stable-diffusion.cpp, "
            "fonctionne sur une carte 8 Go), lancez start_server.ps1, puis testez. "
            "PANDORA n'embarque ni les poids ni le moteur."))
        hint.setWordWrap(True)
        hint.setStyleSheet(
            f"color:{CP['text_dim']};font-size:10px;background:transparent;border:none;")
        lay.addWidget(hint)

        # La licence, en clair et en couleur d'avertissement : ni cachée, ni
        # bloquante. C'est l'utilisateur qui décide — en sachant.
        lic = QLabel("⚠  " + translate(_h3l.LICENSE_NOTICE))
        lic.setWordWrap(True)
        lic.setStyleSheet(
            "color:#f0b429;font-size:10px;background:transparent;border:none;")
        lay.addWidget(lic)

    # ── État ────────────────────────────────────────────────────────────────

    def url(self) -> str:
        return self._field.text().strip()

    def _on_edited(self):
        # Auto-enregistrement, comme le reste des Paramètres : la rangée se
        # persiste elle-même (core/h3_local.set_url relit la config entière
        # avant d'écrire). Les pages n'ont donc rien à ajouter à leur dict.
        try:
            saved = _h3l.set_url(self.url())
        except Exception:
            saved = self.url()
        self.changed.emit(saved)

    def _probe(self):
        ok, msg = _h3l.ping(self.url())
        self._state.setText(translate(msg) if not ok else "✓  " + translate(msg))
        self._state.setStyleSheet(
            f"color:{CP['text_dim'] if ok else '#f0b429'};font-size:10px;"
            f"background:transparent;border:none;")
