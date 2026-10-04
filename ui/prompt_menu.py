"""
ui/prompt_menu.py — Menu « Prompt » de la barre Storyboard (04/10/2026).

Demande Matthieu : « prompt structuré, prompt final et forme du prompt, ça fait
beaucoup d'éléments pour pas grand-chose — un seul menu déroulant comme le
menu Action, marqué Prompt, à gauche du nombre de plans ».

Remplace dans la barre la bascule PromptViewToggle et le sélecteur
PromptFormSelector. Les ÉTATS ne bougent pas : la vue vit dans
core/final_prompt (mémoire, jamais dans le projet), la forme dans
core/prompt_form (projet) — une seule source de vérité, relue à la
construction (un bouton neuf ne doit jamais mentir sur l'état du module).

API compatible PromptViewToggle : view(), set_view(), signal changed(str) ;
pour la forme : signal form_changed(str), reload(), current_form(),
set_form_enabled(). Composant NEUTRE : le Live l'instancie sans la vue
(il n'a pas de prompt final à afficher dans sa colonne).
"""
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QAction, QActionGroup
from PyQt6.QtWidgets import QMenu, QPushButton

from core import prompt_form as _pf
from core.i18n import translate
from ui.styles import CP

STRUCTURE = "structure"
FINAL = "final"


class PromptMenu(QPushButton):
    """Bouton « ☰ Prompt » à menu déroulant : vue de la colonne + forme."""

    changed = pyqtSignal(str)        # vue : "structure" | "final"
    form_changed = pyqtSignal(str)   # clé de forme retenue (core/prompt_form)

    def __init__(self, parent=None, with_view: bool = True):
        super().__init__(parent)
        self._with_view = with_view
        if with_view:
            from core import final_prompt as _fp
            v = _fp.current_view()
            self._view = v if v in (STRUCTURE, FINAL) else STRUCTURE
        else:
            self._view = FINAL
        self.setFixedHeight(34)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setStyleSheet(
            f"QPushButton{{background:transparent;color:{CP['accent']};"
            f"border:1px solid {CP['accent']};border-radius:8px;"
            f"font-size:11px;font-weight:700;padding:0 14px;}}"
            f"QPushButton:hover{{background:rgba(78,205,196,0.12);}}"
            f"QPushButton:pressed{{background:rgba(78,205,196,0.22);}}"
            f"QPushButton::menu-indicator{{image:none;width:0;}}")

        menu = QMenu(self)
        menu.setStyleSheet(
            f"QMenu{{background:{CP['bg2']};border:1px solid {CP['border_bright']};"
            f"border-radius:8px;padding:6px;}}"
            f"QMenu::item{{color:{CP['text_primary']};padding:7px 18px 7px 26px;"
            f"font-size:11px;}}"
            f"QMenu::item:selected{{background:{CP['accent_dim']};color:{CP['text_primary']};}}"
            f"QMenu::item:disabled{{color:{CP['text_dim']};}}"
            f"QMenu::separator{{height:1px;background:{CP['border']};margin:5px 8px;}}")
        menu.setToolTipsVisible(True)

        self._act_struct = self._act_final = None
        if with_view:
            menu.addAction(self._header(translate("AFFICHAGE DE LA COLONNE")))
            grp = QActionGroup(self)
            grp.setExclusive(True)
            self._act_struct = QAction(translate("Prompt structuré"), self, checkable=True)
            self._act_struct.setToolTip(translate(
                "Votre document de travail : les blocs qui structurent le plan. "
                "C'est ce que vous éditez."))
            self._act_final = QAction(translate("Prompt final"), self, checkable=True)
            self._act_final.setToolTip(translate(
                "Le texte réellement envoyé au moteur, réécrit en anglais dans sa "
                "grammaire. Affiché seulement s'il a déjà été composé."))
            for a, v in ((self._act_struct, STRUCTURE), (self._act_final, FINAL)):
                grp.addAction(a)
                menu.addAction(a)
                a.triggered.connect(lambda _c=False, vv=v: self.set_view(vv))
            menu.addSeparator()

        self._form_header = self._header(translate("FORME DU PROMPT"))
        menu.addAction(self._form_header)
        fgrp = QActionGroup(self)
        fgrp.setExclusive(True)
        self._form_actions: list[QAction] = []
        for key, label, desc in _pf.FORMS:
            a = QAction(translate(label), self, checkable=True)
            a.setData(key)
            a.setToolTip(translate(desc))
            fgrp.addAction(a)
            menu.addAction(a)
            a.triggered.connect(lambda _c=False, k=key: self._on_form(k))
            self._form_actions.append(a)
        self.setMenu(menu)
        self._form_tip = ""
        self._refresh()

    def _header(self, text: str) -> QAction:
        """Intitulé de groupe (action inactive). Parent = le bouton : sans
        parent, l'action pouvait être ramassée et disparaître du menu."""
        a = QAction(text, self)
        a.setEnabled(False)
        return a

    # ── Vue (API PromptViewToggle) ───────────────────────────────────────────

    def view(self) -> str:
        return self._view

    def set_view(self, view: str):
        v = view if view in (STRUCTURE, FINAL) else STRUCTURE
        if v == self._view:
            self._refresh()
            return
        self._view = v
        self._refresh()
        self.changed.emit(v)

    # ── Forme (API PromptFormSelector) ───────────────────────────────────────

    def reload(self):
        """Relit la forme du projet (changement de projet)."""
        self._refresh()

    def current_form(self) -> str:
        return _pf.get_form()

    def set_form_enabled(self, on: bool, tip: str = ""):
        """La forme ne concerne que le prompt final : grisée sinon, avec la raison."""
        for a in self._form_actions:
            a.setEnabled(bool(on))
        self._form_tip = "" if on else tip
        self._form_header.setText(translate("FORME DU PROMPT") + (
            "" if on else "  —  " + translate("prompt final uniquement")))
        self._refresh()

    def _on_form(self, key: str):
        saved = _pf.set_form(key)
        self._refresh()
        self.form_changed.emit(saved)

    # ── Affichage ────────────────────────────────────────────────────────────

    def _refresh(self):
        form = _pf.get_form()
        for a in self._form_actions:
            a.setChecked(a.data() == form)
        if self._act_struct is not None:
            self._act_struct.setChecked(self._view == STRUCTURE)
            self._act_final.setChecked(self._view == FINAL)
        # Le libellé dit l'état sans ouvrir le menu — et un ESSAI de forme en
        # cours doit se voir, sinon on attribue le résultat au moteur.
        parts = ["☰  " + translate("Prompt")]
        if self._with_view:
            parts.append(translate("structuré") if self._view == STRUCTURE
                         else translate("final"))
        if form != _pf.AUTO:
            parts.append(translate("essai"))
        self.setText("  ·  ".join(parts))
        tip = [translate("Vue de la colonne Prompt et forme du prompt final.")]
        if form != _pf.AUTO:
            tip.append(_pf.description_of(form))
        if self._form_tip:
            tip.append(self._form_tip)
        self.setToolTip("\n".join(tip))
