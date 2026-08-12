"""
ui/prompt_view_toggle.py — Bascule « Prompt structuré / Prompt final ».

Le Storyboard montre par défaut le DOCUMENT DE TRAVAIL (blocs français). Cette
bascule affiche à la place le PROMPT RÉELLEMENT ENVOYÉ au moteur — anglais,
continu, dans la grammaire du moteur — pour voir l'effet du moteur visé et de
la forme choisie sans ouvrir le Studio.

⚠ Elle n'AFFICHE que ce qui a déjà été composé. Composer coûte un appel IA par
plan : un simple changement de vue ne doit jamais en déclencher 75.

La vue est un état d'AFFICHAGE, pas une donnée du film : elle vit en mémoire,
pas dans le projet. Rouvrir PANDORA repart sur le document de travail.
"""
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import QWidget, QHBoxLayout, QPushButton

from core.i18n import translate
from ui.styles import CP

STRUCTURE = "structure"
FINAL     = "final"


class PromptViewToggle(QWidget):
    """Deux boutons exclusifs. Émet `changed(str)` : "structure" ou "final"."""

    changed = pyqtSignal(str)

    def __init__(self, parent=None, view: str = ""):
        super().__init__(parent)
        self.setStyleSheet("background:transparent;")
        # ⚠ UNE SEULE source de vérité : l'état du module. Le défaut était
        # STRUCTURE en dur, alors que `final_prompt._VIEW` survit au changement
        # de projet — en rouvrant un projet depuis la vue finale, le bouton
        # affichait « structuré » pendant que les cellules obéissaient encore
        # à « final » (message « à composer » partout). Il fallait basculer
        # deux fois pour resynchroniser (signalé par Matthieu, FIGHTER 2.0).
        if view not in (STRUCTURE, FINAL):
            from core import final_prompt as _fp
            view = _fp.current_view()
        self._view = view if view in (STRUCTURE, FINAL) else STRUCTURE

        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)

        self._btn_struct = QPushButton(translate("Prompt structuré"))
        self._btn_final  = QPushButton(translate("Prompt final"))
        for b in (self._btn_struct, self._btn_final):
            b.setFixedHeight(32)
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            lay.addWidget(b)

        self._btn_struct.setToolTip(translate(
            "Votre document de travail : les blocs qui structurent le plan. "
            "C'est ce que vous éditez."))
        self._btn_final.setToolTip(translate(
            "Le texte réellement envoyé au moteur, réécrit en anglais dans sa "
            "grammaire. Affiché seulement s'il a déjà été composé."))

        self._btn_struct.clicked.connect(lambda: self.set_view(STRUCTURE))
        self._btn_final.clicked.connect(lambda: self.set_view(FINAL))
        self._restyle()

    # ── État ────────────────────────────────────────────────────────────────

    def view(self) -> str:
        return self._view

    def set_view(self, view: str):
        v = view if view in (STRUCTURE, FINAL) else STRUCTURE
        if v == self._view:
            return
        self._view = v
        self._restyle()
        self.changed.emit(v)

    def _restyle(self):
        on = (
            f"QPushButton{{background:{CP['accent']};color:#07080f;border:none;"
            f"font-size:11px;font-weight:700;padding:0 14px;}}"
        )
        off = (
            f"QPushButton{{background:transparent;color:{CP['text_secondary']};"
            f"border:1px solid {CP['border']};font-size:11px;font-weight:600;"
            f"padding:0 14px;}}"
            f"QPushButton:hover{{background:{CP['bg3']};color:{CP['text_primary']};}}"
        )
        # Coins arrondis seulement aux extrémités : les deux boutons forment
        # un seul bloc, comme un interrupteur.
        self._btn_struct.setStyleSheet(
            (on if self._view == STRUCTURE else off)
            + "QPushButton{border-top-left-radius:7px;border-bottom-left-radius:7px;}")
        self._btn_final.setStyleSheet(
            (on if self._view == FINAL else off)
            + "QPushButton{border-top-right-radius:7px;border-bottom-right-radius:7px;}")
