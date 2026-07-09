"""Dialogues du DÉCOUPAGE — helper PARTAGÉ Cinéma + Live (comme ui.quit_dialog).

RÈGLE DE SOURCE (Matthieu 2026-07-09, remplace l'ancienne fenêtre de choix) : où qu'on
lance la génération (« Générer le découpage » en page Scénario/Conducteur, placeholder
« ⊕ Générer depuis… » en Storyboard / Séquences Live / Séquences Mapping), la source est
AUTOMATIQUE : la « Mise en page PANDORA » si elle existe, sinon le scénario (Cinéma) ou
le conducteur (Live). Aucun choix manuel.

Ce module ne contient donc que l'AVERTISSEMENT DE RÉÉCRITURE : affiché UNIQUEMENT quand
le passage vers le storyboard/les séquences va réellement RÉÉCRIRE les prompts d'une Mise
en page co-écrite (l'IA reformule chaque plan — cas Cinéma, ou mise en page non parsable
en Live). Quand le passage est fidèle (conversion déterministe Live : prompts repris tels
quels), AUCUNE fenêtre — pas de surprise, c'est tout."""

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
)

from ui.styles import CP, PANDORA_STYLESHEET
from core.i18n import translate


class _RewriteWarningDialog(QDialog):
    """Avertissement (fond sombre PANDORA) avant une génération qui va RÉÉCRIRE les
    prompts d'une Mise en page PANDORA existante. ``ok`` = True si « Continuer »."""

    def __init__(self, parent):
        super().__init__(parent)
        self.ok = False
        self.setWindowTitle(translate("Réécriture des prompts"))
        self.setMinimumWidth(460)
        self.setStyleSheet(PANDORA_STYLESHEET + f"QDialog{{background:{CP['bg1']};}}")

        lay = QVBoxLayout(self)
        lay.setContentsMargins(22, 20, 22, 18)
        lay.setSpacing(12)

        title = QLabel(translate("⚠  Cette génération va RÉÉCRIRE les prompts."))
        title.setWordWrap(True)
        title.setStyleSheet(
            f"color:{CP['text_primary']};font-size:13px;font-weight:700;background:transparent;")
        lay.addWidget(title)

        body = QLabel(translate(
            "La Mise en page PANDORA sert de source, mais l'IA reformule chaque plan pour "
            "produire le découpage : vos prompts co-écrits seront réécrits.\n\n"
            "Continuer quand même ?"))
        body.setWordWrap(True)
        body.setStyleSheet(f"color:{CP['text_secondary']};font-size:12px;background:transparent;")
        lay.addWidget(body)

        lay.addSpacing(4)
        row = QHBoxLayout()
        row.addStretch()
        btn_cancel = QPushButton(translate("Annuler"))
        btn_cancel.setFixedHeight(34)
        btn_cancel.setStyleSheet(
            f"QPushButton{{background:transparent;color:{CP['text_secondary']};"
            f"border:1px solid {CP['border']};border-radius:8px;"
            f"font-size:11px;font-weight:700;padding:0 16px;}}"
            f"QPushButton:hover{{background:{CP['bg3']};}}")
        btn_cancel.clicked.connect(self.reject)
        self._btn_cont = QPushButton(translate("Continuer"))
        self._btn_cont.setFixedHeight(34)
        self._btn_cont.setStyleSheet(
            f"QPushButton{{background:{CP['accent']};color:#07080f;border:none;"
            f"border-radius:8px;font-size:11px;font-weight:700;padding:0 18px;}}"
            f"QPushButton:hover{{background:#6eded6;}}")
        self._btn_cont.clicked.connect(self._on_continue)
        row.addWidget(btn_cancel)
        row.addSpacing(8)
        row.addWidget(self._btn_cont)
        lay.addLayout(row)

        # Entrée ne doit PAS déclencher « Continuer » (le choix SÛR reste de ne rien réécrire).
        try:
            from ui.widgets import disable_default_buttons
            disable_default_buttons(self)
        except Exception:
            pass

    def _on_continue(self):
        self.ok = True
        self.accept()


def confirm_prompt_rewrite(parent) -> bool:
    """Ouvre l'avertissement de réécriture et renvoie True (continuer) / False (annuler).
    À appeler UNIQUEMENT quand une Mise en page PANDORA existe ET que le chemin de
    génération repasse par l'IA (qui reformule les prompts)."""
    dlg = _RewriteWarningDialog(parent)
    dlg.exec()
    return bool(dlg.ok)
