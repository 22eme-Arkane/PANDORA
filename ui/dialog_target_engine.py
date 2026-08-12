"""
ui/dialog_target_engine.py — « Pour quel moteur écrit-on ce découpage ? »

Posée AVANT la génération du storyboard : le prompt de chaque plan est écrit
dans la grammaire du moteur visé, et une grammaire ne se rattrape pas après
coup sur 75 plans sans tout recomposer.

Composant NEUTRE (ni Cinéma ni Live). La liste des moteurs est FOURNIE par
l'appelant — c'est chaque édition qui sait lesquels elle propose ; ce dialogue
n'en connaît aucun et n'en invente aucun.
"""
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QComboBox,
)

from core import target_engine as _te
from core.i18n import translate
from ui.styles import CP
from ui.widgets import disable_default_buttons


class TargetEngineDialog(QDialog):
    """Retourne la clé du moteur choisi via `chosen()`. `exec()` standard."""

    def __init__(self, engines: list, parent=None, current: str = ""):
        """engines : liste [(libellé, clé)] telle que l'édition la propose."""
        super().__init__(parent)
        self.setWindowTitle(translate("Moteur de génération visé"))
        self.setMinimumWidth(620)
        self.setStyleSheet(f"QDialog{{background:{CP['bg1']};}}")

        self._engines = [e for e in (engines or []) if e and len(e) == 2]
        self._chosen = current or _te.get_target_engine()

        lay = QVBoxLayout(self)
        lay.setContentsMargins(28, 24, 28, 22)
        lay.setSpacing(14)

        title = QLabel(translate("Pour quel moteur écrit-on ce découpage ?"))
        title.setStyleSheet(
            f"color:{CP['text_primary']};font-size:17px;font-weight:700;"
            f"background:transparent;"
        )
        lay.addWidget(title)

        intro = QLabel(translate(
            "Chaque moteur attend une forme de prompt différente. Le découpage "
            "sera écrit dans celle du moteur choisi — c'est plus simple que de "
            "réécrire tous les plans ensuite."
        ))
        intro.setWordWrap(True)
        intro.setStyleSheet(
            f"color:{CP['text_secondary']};font-size:12px;background:transparent;")
        lay.addWidget(intro)

        self._combo = QComboBox()
        self._combo.setFixedHeight(38)
        for label, key in self._engines:
            self._combo.addItem(label, key)
        idx = self._combo.findData(self._chosen)
        if idx >= 0:
            self._combo.setCurrentIndex(idx)
        self._combo.currentIndexChanged.connect(self._refresh)
        lay.addWidget(self._combo)

        self._detail = QLabel()
        self._detail.setWordWrap(True)
        self._detail.setStyleSheet(
            f"color:{CP['text_dim']};font-size:11px;background:transparent;"
            f"border:1px solid {CP['border']};border-radius:6px;padding:10px 12px;"
        )
        lay.addWidget(self._detail)

        note = QLabel(translate(
            "Ce choix n'enferme rien : vous pourrez toujours rendre un plan "
            "avec un autre moteur depuis le Studio."
        ))
        note.setWordWrap(True)
        note.setStyleSheet(
            f"color:{CP['text_dim']};font-size:10px;background:transparent;")
        lay.addWidget(note)

        row = QHBoxLayout()
        row.addStretch()
        cancel = QPushButton(translate("Annuler"))
        ok = QPushButton(translate("Écrire le découpage"))
        for b in (cancel, ok):
            b.setFixedHeight(36)
            b.setCursor(Qt.CursorShape.PointingHandCursor)
        cancel.setStyleSheet(
            f"QPushButton{{background:transparent;color:{CP['text_secondary']};"
            f"border:1px solid {CP['border']};border-radius:7px;"
            f"font-size:12px;padding:0 18px;}}"
            f"QPushButton:hover{{background:{CP['bg3']};}}"
        )
        ok.setStyleSheet(
            f"QPushButton{{background:{CP['accent']};color:#07080f;border:none;"
            f"border-radius:7px;font-size:12px;font-weight:700;padding:0 22px;}}"
            f"QPushButton:hover{{background:{CP['accent_dim']};color:#fff;}}"
        )
        cancel.clicked.connect(self.reject)
        ok.clicked.connect(self._accept)
        row.addWidget(cancel)
        row.addWidget(ok)
        lay.addLayout(row)

        # Sinon Entrée déclencherait le bouton par défaut de Qt.
        disable_default_buttons(self)
        self._refresh()

    # ── Détail du moteur sélectionné ────────────────────────────────────────

    def _refresh(self):
        key = self._combo.currentData() or ""
        self._detail.setText(self._describe(key))

    def _describe(self, key: str) -> str:
        """Décrit la forme de prompt et les contraintes RÉELLES du moteur.

        Tout est lu sur les tables du projet — aucune donnée récitée ici, pour
        qu'une évolution de moteur n'ait pas à être répercutée dans ce texte.
        """
        bits = []
        try:
            from core import engine_grammar
            bits.append(translate("Forme du prompt") + " : "
                        + engine_grammar.grammar_label(key))
        except Exception:
            pass
        try:
            from core import seedance_family as _sf
            if _sf.is_seedance(key):
                spec = _sf.spec(key)
                bits.append(translate("Résolutions") + " : "
                            + ", ".join(spec["resolutions"]))
                if _sf.uses_named_refs(key):
                    bits.append(translate(
                        "Les fiches sont désignées dans le prompt (@Image1)."))
                if spec["max_images"]:
                    bits.append(translate("Images de référence")
                                + f" : {spec['max_images']}")
        except Exception:
            pass
        try:
            if key.startswith("flux-3"):
                from core import flux3_family as _f3
                bits.append(translate("Résolutions") + " : "
                            + ", ".join(_f3.RESOLUTIONS))
                bits.append(translate("Durées") + " : 5–20 s")
                bits.append(translate(
                    "Audio natif : chaque plan reçoit une clause sonore."))
        except Exception:
            pass
        try:
            from core import pricing
            rate = pricing.price_per_second(key, "720p")
            if rate:
                bits.append(translate("Coût indicatif") + f" : ~${rate:.2f}/s "
                            + translate("en 720p"))
        except Exception:
            pass
        return "  ·  ".join(bits) if bits else translate(
            "Aucune contrainte particulière relevée pour ce moteur.")

    # ── Sortie ──────────────────────────────────────────────────────────────

    def _accept(self):
        self._chosen = self._combo.currentData() or self._chosen
        _te.set_target_engine(self._chosen)
        self.accept()

    def chosen(self) -> str:
        return self._chosen


def ask_target_engine(engines: list, parent=None, force: bool = False) -> str | None:
    """Pose la question SI elle n'a pas déjà été tranchée pour ce projet.

    Retourne la clé du moteur, ou None si l'utilisateur annule (l'appelant doit
    alors renoncer à générer). `force=True` rouvre la fenêtre même si un choix
    existe — c'est ce que branche un bouton « changer de moteur ».
    """
    if not force and _te.has_choice():
        return _te.get_target_engine()
    dlg = TargetEngineDialog(engines, parent=parent,
                             current=_te.get_target_engine())
    if dlg.exec() != QDialog.DialogCode.Accepted:
        return None
    return dlg.chosen()
