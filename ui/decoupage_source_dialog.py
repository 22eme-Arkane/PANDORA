"""Fenêtre de choix de la SOURCE du découpage.

Affichée AVANT de lancer la génération du découpage (bouton « Générer le découpage »)
pour lever tout doute sur CE QUI sera découpé :
  - le texte source brut (« le scénario » en Cinéma, « le conducteur » en Live) ;
  - la « Mise en page PANDORA » (version structurée plan par plan), si elle existe.

Helper PARTAGÉ Cinéma + Live (comme ui.quit_dialog) : les deux pages Scénario/Conducteur
l'appellent avec le libellé de leur source brute. Renvoie la clé choisie :
``"source"`` | ``"layout"`` | ``None`` (annulé)."""

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
)
from PyQt6.QtCore import Qt

from ui.styles import CP, PANDORA_STYLESHEET
from core.i18n import translate


class _DecoupageSourceDialog(QDialog):
    """Dialogue interne. ``choice`` vaut ``"source"`` / ``"layout"`` après validation,
    ``None`` si annulé. Une option dont le texte est vide est proposée mais GRISÉE
    (on voit qu'elle existe mais n'est pas disponible → « éviter le doute »)."""

    def __init__(self, parent, source_label: str, source_text: str, layout_text: str):
        super().__init__(parent)
        self.choice = None
        self.setWindowTitle(translate("Générer le découpage"))
        self.setMinimumWidth(460)
        self.setStyleSheet(PANDORA_STYLESHEET + f"QDialog{{background:{CP['bg1']};}}")

        lay = QVBoxLayout(self)
        lay.setContentsMargins(22, 20, 22, 18)
        lay.setSpacing(14)

        q = QLabel(translate("Depuis quelle source générer le découpage ?"))
        q.setWordWrap(True)
        q.setStyleSheet(
            f"color:{CP['text_primary']};font-size:13px;font-weight:700;"
            "background:transparent;")
        lay.addWidget(q)

        self._btn_source = self._choice_button(source_label, bool(source_text.strip()))
        self._btn_source.clicked.connect(lambda: self._pick("source"))
        lay.addWidget(self._btn_source)

        _lay_label = translate("📝  Depuis la Mise en page PANDORA")
        if not layout_text.strip():
            _lay_label += "  " + translate("(aucune mise en page générée)")
        self._btn_layout = self._choice_button(_lay_label, bool(layout_text.strip()))
        self._btn_layout.clicked.connect(lambda: self._pick("layout"))
        lay.addWidget(self._btn_layout)

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
        row.addWidget(btn_cancel)
        lay.addLayout(row)

        # Entrée ne doit PAS déclencher un bouton par défaut (doctrine PANDORA).
        try:
            from ui.widgets import disable_default_buttons
            disable_default_buttons(self)
        except Exception:
            pass

    def _choice_button(self, text: str, enabled: bool) -> QPushButton:
        b = QPushButton(text)
        b.setMinimumHeight(50)
        b.setEnabled(enabled)
        if enabled:
            b.setCursor(Qt.CursorShape.PointingHandCursor)
        b.setStyleSheet(
            f"QPushButton{{background:{CP['bg2']};color:{CP['text_primary']};"
            f"border:1px solid {CP['border']};border-radius:10px;font-size:13px;"
            f"font-weight:600;padding:10px 16px;text-align:left;}}"
            f"QPushButton:hover{{border-color:{CP['accent']};"
            f"background:rgba(78,205,196,0.10);}}"
            f"QPushButton:disabled{{color:{CP['text_dim']};background:{CP['bg1']};"
            f"border-color:{CP['border']};}}")
        return b

    def _pick(self, key: str):
        self.choice = key
        self.accept()


def choose_decoupage_source(parent, *, source_label: str,
                            source_text: str, layout_text: str):
    """Ouvre la fenêtre de choix et renvoie ``"source"`` | ``"layout"`` | ``None``.

    ``source_label`` : libellé complet du bouton de la source brute
    (« 📄  Depuis le scénario » en Cinéma, « 🎬  Depuis le conducteur » en Live).
    ``source_text`` / ``layout_text`` : contenus courants (une option vide est grisée)."""
    dlg = _DecoupageSourceDialog(parent, source_label, source_text, layout_text)
    if dlg.exec() == QDialog.DialogCode.Accepted:
        return dlg.choice
    return None
