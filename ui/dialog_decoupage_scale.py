"""ui/dialog_decoupage_scale.py — « Ce scénario est très gros. »

Avertissement affiché AVANT de lancer un découpage, quand l'estimation montre
que le pipeline va peiner ou ne pourra pas aboutir.

Ce n'est pas une boîte de dialogue de politesse : elle existe parce qu'un
utilisateur a collé un livre entier, attendu, payé, et vu le découpage
s'arrêter. Elle annonce donc des CHIFFRES — plans attendus, ordre de grandeur
du coût — et propose la sortie par lots plutôt que de dire seulement « non ».

Elle ne décide rien : elle renvoie le choix, l'appelant agit.
"""

from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QFrame,
)

from core import decoupage_scale as scale
from core.i18n import translate
from ui.styles import CP
from ui.widgets import disable_default_buttons, section_label

#: Choix rendus par le dialogue.
CANCEL = "cancel"
BATCHES = "batches"
ANYWAY = "anyway"


def _btn(text: str, accent: str, strong: bool = False) -> QPushButton:
    b = QPushButton(text)
    b.setFixedHeight(38)
    b.setCursor(Qt.CursorShape.PointingHandCursor)
    r, g, bl = int(accent[1:3], 16), int(accent[3:5], 16), int(accent[5:7], 16)
    if strong:
        b.setStyleSheet(
            f"QPushButton{{background:{accent};border:none;border-radius:8px;"
            f"color:#0c0e1a;font-size:12px;font-weight:700;padding:0 18px;}}"
            f"QPushButton:hover{{background:rgba({r},{g},{bl},0.85);}}"
        )
    else:
        b.setStyleSheet(
            f"QPushButton{{background:transparent;border:1px solid {accent};"
            f"border-radius:8px;color:{accent};font-size:12px;padding:0 18px;}}"
            f"QPushButton:hover{{background:rgba({r},{g},{bl},0.12);}}"
        )
    return b


class DecoupageScaleDialog(QDialog):
    """Annonce l'ampleur d'un découpage et laisse le choix.

    `choice()` renvoie CANCEL, BATCHES ou ANYWAY. ANYWAY n'est proposé que
    lorsque le découpage d'une traite a une chance d'aboutir : offrir un bouton
    qui mène à coup sûr à l'erreur serait un piège, pas une liberté.
    """

    def __init__(self, parent, text: str, cost_usd: float = 0.0,
                 batch_chars: int = 6000):
        super().__init__(parent)
        self._choice = CANCEL
        est = scale.estimate(text)
        self._est = est
        impossible = (est["verdict"] == scale.IMPOSSIBLE)
        n_lots = scale.batches_needed(text, batch_chars)

        self.setWindowTitle(translate("Scénario volumineux"))
        self.setMinimumWidth(680)
        self.setStyleSheet(f"QDialog{{background:{CP['bg1']};}}")

        lay = QVBoxLayout(self)
        lay.setContentsMargins(26, 22, 26, 20)
        lay.setSpacing(14)

        titre = QLabel(
            translate("Ce découpage ne peut pas aboutir d'une seule traite")
            if impossible else
            translate("Ce découpage va être long et coûteux")
        )
        titre.setWordWrap(True)
        titre.setStyleSheet(
            f"color:{CP['text_primary']};font-size:17px;font-weight:700;"
            f"background:transparent;"
        )
        lay.addWidget(titre)

        # ── Les chiffres, en clair ────────────────────────────────────────────
        lay.addWidget(section_label("Estimation"))
        grid = QFrame()
        grid.setStyleSheet(
            f"QFrame{{background:{CP['bg2']};border:1px solid {CP['border']};"
            f"border-radius:8px;}}"
        )
        g_lay = QVBoxLayout(grid)
        g_lay.setContentsMargins(16, 12, 16, 12)
        g_lay.setSpacing(5)

        lignes = [
            (translate("Longueur du scénario"),
             f"{est['chars']:,} ".replace(",", " ") + translate("caractères")),
            (translate("Plans attendus"), f"{est['shots']}"),
            (translate("Reprises nécessaires"),
             f"{est['rounds_needed']} / {est['max_rounds']} "
             + translate("maximum")),
        ]
        if cost_usd > 0:
            lignes.append((translate("Coût estimé du découpage"),
                           f"≈ {cost_usd:.2f} $"))
        for k, v in lignes:
            row = QHBoxLayout()
            row.setSpacing(10)
            lk = QLabel(k)
            lk.setStyleSheet(
                f"color:{CP['text_secondary']};font-size:12px;background:transparent;")
            lv = QLabel(v)
            lv.setStyleSheet(
                f"color:{CP['text_primary']};font-size:12px;font-weight:700;"
                f"font-family:'Consolas',monospace;background:transparent;")
            row.addWidget(lk)
            row.addStretch()
            row.addWidget(lv)
            g_lay.addLayout(row)
        lay.addWidget(grid)

        # ── L'explication, sans jargon ────────────────────────────────────────
        if impossible:
            corps = translate(
                "Le découpage produit environ six fois la longueur du scénario. "
                "Au-delà d'environ 58 000 caractères, il dépasse ce que le moteur "
                "peut écrire en une fois, même avec ses reprises automatiques : "
                "il s'arrêterait en cours de route et rien ne serait enregistré.")
        else:
            corps = translate(
                "Le découpage produit environ six fois la longueur du scénario. "
                "À cette taille, le moteur devra s'y reprendre à plusieurs fois, "
                "et chaque reprise relit tout ce qu'il a déjà écrit — c'est ce qui "
                "fait grimper le coût.")
        p1 = QLabel(corps)
        p1.setWordWrap(True)
        p1.setStyleSheet(
            f"color:{CP['text_secondary']};font-size:12px;background:transparent;")
        lay.addWidget(p1)

        p2 = QLabel(translate(
            "Le découpage par lots traite le scénario tranche par tranche et "
            "reprend là où il s'est arrêté. C'est plus sûr, moins cher, et vous "
            "pouvez l'interrompre puis le reprendre.")
            + f"  ({n_lots} " + translate("lots prévus") + ")")
        p2.setWordWrap(True)
        p2.setStyleSheet(
            f"color:{CP['accent']};font-size:12px;background:transparent;")
        lay.addWidget(p2)

        note = QLabel(translate(
            "Chiffres estimés à partir de deux découpages réels — un ordre de "
            "grandeur, pas une facture."))
        note.setWordWrap(True)
        note.setStyleSheet(
            f"color:{CP['text_dim']};font-size:9px;font-family:'Consolas',monospace;"
            f"background:transparent;")
        lay.addWidget(note)

        # ── Boutons ───────────────────────────────────────────────────────────
        row = QHBoxLayout()
        row.setSpacing(10)
        b_cancel = _btn(translate("Annuler"), CP["text_dim"])
        b_cancel.clicked.connect(self._on_cancel)
        row.addWidget(b_cancel)
        row.addStretch()
        if not impossible:
            b_anyway = _btn(translate("Découper d'une traite quand même"),
                            CP["accent2"])
            b_anyway.clicked.connect(self._on_anyway)
            row.addWidget(b_anyway)
        b_batch = _btn(translate("Découper par lots"), CP["accent"], strong=True)
        b_batch.clicked.connect(self._on_batches)
        row.addWidget(b_batch)
        lay.addLayout(row)

        # Sans ça, Entrée déclencherait le premier bouton du dialogue.
        disable_default_buttons(self)

    # Méthodes liées, jamais de lambda : Qt sait déconnecter les premières.
    def _on_cancel(self):
        self._choice = CANCEL
        self.reject()

    def _on_batches(self):
        self._choice = BATCHES
        self.accept()

    def _on_anyway(self):
        self._choice = ANYWAY
        self.accept()

    def choice(self) -> str:
        return self._choice

    def estimate(self) -> dict:
        return dict(self._est)


def should_warn(text: str) -> bool:
    """Faut-il avertir ? Seulement quand le découpage devient réellement lourd.

    Avertir trop tôt est le meilleur moyen de rendre l'avertissement invisible :
    un court métrage (deux tours) passe sans rien dire.
    """
    return scale.estimate(text)["verdict"] != scale.OK
