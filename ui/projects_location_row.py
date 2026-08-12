"""
ui/projects_location_row.py — Rangée « Dossier des projets » des Paramètres.

Composant NEUTRE (ni Cinéma ni Live) : les deux pages Paramètres l'instancient
telle quelle, exactement comme ui/widgets.py ou ui/thumb_cache.py. La logique
vit dans core/projects_location.py ; ici, uniquement l'affichage.

La rangée annonce trois choses que l'utilisateur ne peut pas deviner :
  · où naissent les nouveaux projets ;
  · que changer ce dossier ne DÉPLACE rien ;
  · que le disque est actuellement branché — ou pas.
"""
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QFileDialog,
)

from core import projects_location as _loc
from core.i18n import translate
from ui.styles import CP


class ProjectsLocationRow(QWidget):
    """Champ + bouton Parcourir + état du dossier. Émet `changed(str)`."""

    changed = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet("background:transparent;")

        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(6)

        row = QHBoxLayout()
        row.setSpacing(8)

        self._field = QLineEdit()
        self._field.setReadOnly(True)
        self._field.setFixedHeight(38)
        self._field.setStyleSheet(
            f"QLineEdit{{background:{CP['bg3']};border:1px solid {CP['border']};"
            f"border-radius:6px;color:{CP['text_secondary']};font-size:11px;"
            f"font-family:'Consolas',monospace;padding:0 12px;}}"
        )
        row.addWidget(self._field, 1)

        self._btn = QPushButton(translate("Parcourir…"))
        self._btn.setFixedHeight(38)
        self._btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn.setStyleSheet(
            f"QPushButton{{background:transparent;color:{CP['text_secondary']};"
            f"border:1px solid {CP['border']};border-radius:6px;"
            f"font-size:12px;font-weight:600;padding:0 18px;}}"
            f"QPushButton:hover{{background:{CP['bg3']};color:{CP['text_primary']};}}"
        )
        self._btn.clicked.connect(self._browse)
        row.addWidget(self._btn)
        lay.addLayout(row)

        self._state = QLabel()
        self._state.setWordWrap(True)
        self._state.setStyleSheet(
            f"color:{CP['text_dim']};font-size:10px;background:transparent;border:none;"
        )
        lay.addWidget(self._state)

        hint = QLabel(translate(
            "Les nouveaux projets seront créés ici — pratique pour travailler "
            "sur un disque externe depuis plusieurs machines. Changer ce dossier "
            "ne déplace aucun projet existant : déplacez-le vous-même, puis "
            "utilisez « Ouvrir un projet » une fois."
        ))
        hint.setWordWrap(True)
        hint.setStyleSheet(
            f"color:{CP['text_dim']};font-size:10px;background:transparent;border:none;"
        )
        lay.addWidget(hint)

        self.refresh()

    # ── État ────────────────────────────────────────────────────────────────

    def refresh(self):
        path = _loc.get_projects_root()
        self._field.setText(path)
        if _loc.is_default(path):
            # Le dossier par défaut n'existe qu'à partir du premier projet :
            # son absence est NORMALE et ne doit pas déclencher l'alerte
            # « disque débranché » (constaté au rendu — le cas le plus fréquent
            # sur une installation neuve était le plus alarmant).
            txt = (translate("Dossier par défaut.") if _loc.is_available(path)
                   else translate("Dossier par défaut — créé au premier projet."))
            col = CP['text_dim']
        elif _loc.is_available(path):
            txt = translate("Dossier accessible ✓")
            col = CP['text_dim']
        else:
            # Cas réel du disque externe débranché : le dire, sinon l'utilisateur
            # croit que ses projets se sont volatilisés.
            txt = translate(
                "⚠  Dossier introuvable actuellement (disque débranché ?). "
                "Les projets qui s'y trouvent ne sont pas listés tant qu'il "
                "n'est pas rebranché — ils ne sont pas perdus."
            )
            col = "#f0b429"
        self._state.setText(txt)
        self._state.setStyleSheet(
            f"color:{col};font-size:10px;background:transparent;border:none;"
        )

    # ── Action ──────────────────────────────────────────────────────────────

    def _browse(self):
        start = _loc.get_projects_root()
        if not _loc.is_available(start):
            start = ""
        path = QFileDialog.getExistingDirectory(
            self, translate("Choisir le dossier des projets"), start
        )
        if not path:
            return
        saved = _loc.set_projects_root(path)
        self.refresh()
        self.changed.emit(saved)
