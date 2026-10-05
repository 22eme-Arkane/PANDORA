"""ui/generation_error_dialog.py — LA fenêtre d'erreur d'une génération vidéo du
Studio, commune aux deux éditions.

Demande Matthieu du 05/10/2026 : « lorsqu'il y a un message d'erreur, ce serait
bien qu'on puisse avoir une option essayer avec un autre distributeur » — SANS
bascule automatique (« comme ça, on est au courant qu'il y a un problème avec
ce distributeur »). Chaque distributeur capable de faire le plan a son bouton,
avec le prix du plan chez lui ; le choisir le met en tête de l'ordre (comme le
menu Distributeur du Studio) et relance.

Puis, le même jour (« ils sont vraiment pas beaux ») : boutons au style PANDORA
— contour néon violet comme ceux des distributeurs dans les Paramètres, plus
fins —, OK plein à DROITE. Aucun bouton quand le refus vient du filtre du
PROPRIÉTAIRE du modèle (visages réels, droits d'auteur : le même chez tous les
distributeurs, le message le dit), et PiAPI écarté quand le prompt envoyé
dépasse sa limite.

Elle remplace aussi deux défauts : le Studio ouvrait DEUX fenêtres à la suite
(show_api_error, puis « Une erreur est survenue » ou « génération en série
interrompue »), et la fenêtre des crédits annonçait « fal.ai » quel que soit le
distributeur.
"""
from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QDialog, QHBoxLayout, QLabel, QPushButton, QSizePolicy, QStyle, QVBoxLayout,
)

from core.i18n import translate
from ui.styles import CP

#: Au-delà, la fenêtre deviendrait un mur de boutons.
_MAX_CHOICES = 3


def alternatives(engine: str, resolution: str, seconds: float, audio: bool = True,
                 exclude: str = "", mode: str = "", prompt_len: int = 0) -> list[dict]:
    """Distributeurs à proposer pour réessayer, dans l'ordre de priorité :
    clé présente, demande couverte (moteur, résolution, son, longueur du
    prompt), refus pas déjà connu (Seedance non activé chez BytePlus, crédit
    Runware…), et autre que celui qui vient d'échouer. [{id, name, cost}]"""
    from core import media_provider as mp
    from core.config import load_config
    try:
        from api import distrib_probe as dp
    except Exception:
        dp = None
    try:
        from api.piapi import PROMPT_MAX as _piapi_max
    except Exception:
        _piapi_max = 0
    cfg = load_config()
    quotes = {q["id"]: q for q in mp.quotes(engine, resolution, seconds, mode=mode, audio=audio)}
    out: list[dict] = []
    for pid in mp.provider_order(cfg):
        q = quotes.get(pid) or {}
        if pid == exclude or not q.get("supported") or not q.get("has_key"):
            continue
        if pid == "piapi" and _piapi_max and prompt_len > _piapi_max:
            continue
        if dp is not None:
            known, _why = dp.can_receive(pid, (), network=False, cfg=cfg, engine=engine)
            if known is False:
                continue
        out.append({"id": pid, "name": mp.provider_short(pid), "cost": q.get("cost")})
    return out[:_MAX_CHOICES]


def _retry_style() -> str:
    # Même contour néon que les boutons des distributeurs (Paramètres).
    return (f"QPushButton{{background:transparent;color:{CP['accent2']};"
            f"border:1px solid {CP['accent2']};border-radius:6px;"
            f"font-size:10px;font-weight:700;padding:0 12px;}}"
            f"QPushButton:hover{{background:rgba(124,107,255,0.14);color:#9d8fff;}}"
            f"QPushButton:pressed{{background:rgba(124,107,255,0.24);}}")


def _ok_style() -> str:
    return (f"QPushButton{{background:{CP['accent']};color:#ffffff;border:none;"
            f"border-radius:6px;font-size:11px;font-weight:700;padding:0 22px;}}"
            f"QPushButton:hover{{background:{CP['accent_dim']};}}")


class _ErrorDialog(QDialog):
    """Le message, puis « Réessayer avec : » et ses boutons néon, OK à droite."""

    def __init__(self, parent, message: str, choices: list[dict], title: str):
        super().__init__(parent)
        from core.worker import is_credit_error
        self.chosen = ""
        self.retry_buttons: dict = {}
        self.setWindowTitle(translate("Crédits insuffisants") if is_credit_error(message)
                            else translate(title))
        self.setModal(True)
        self.setStyleSheet(f"QDialog{{background:{CP['bg2']};}}"
                           f"QLabel{{background:transparent;border:none;}}")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(22, 20, 22, 16)
        lay.setSpacing(16)

        top = QHBoxLayout()
        top.setSpacing(14)
        icon = QLabel()
        icon.setFixedWidth(32)
        icon.setPixmap(self.style().standardIcon(
            QStyle.StandardPixmap.SP_MessageBoxCritical).pixmap(32, 32))
        icon.setAlignment(Qt.AlignmentFlag.AlignTop)
        top.addWidget(icon)
        text = QVBoxLayout()
        text.setSpacing(8)
        msg = QLabel(message)
        msg.setTextFormat(Qt.TextFormat.PlainText)
        msg.setWordWrap(True)
        msg.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        msg.setStyleSheet(f"color:{CP['text_primary']};font-size:12px;")
        wrapped = [msg]
        if len(message) > 1200:
            # Une erreur brute peut recopier tout le prompt : bornée, défilable.
            from PyQt6.QtWidgets import QScrollArea
            scroll = QScrollArea()
            scroll.setWidgetResizable(True)
            scroll.setFixedHeight(320)
            scroll.setWidget(msg)
            text.addWidget(scroll)
        else:
            text.addWidget(msg)
        if choices:
            note = QLabel(translate("Aucun autre distributeur n'est essayé sans ton accord."))
            note.setWordWrap(True)
            note.setStyleSheet(f"color:{CP['text_secondary']};font-size:11px;")
            text.addWidget(note)
            wrapped.append(note)
        top.addLayout(text, 1)
        lay.addLayout(top)

        row = QHBoxLayout()
        row.setSpacing(8)
        if choices:
            hint = QLabel(translate("Réessayer avec :"))
            hint.setStyleSheet(f"color:{CP['text_secondary']};font-size:11px;")
            row.addWidget(hint)
            for c in choices:
                label = f"↻ {c['name']}"
                if c.get("cost") is not None:
                    label += f" · ≈ ${c['cost']:.2f}"
                btn = QPushButton(label)
                btn.setFixedHeight(26)
                # Jamais tronqué : la fenêtre s'élargit plutôt (« ≈ $12. » au 1er rendu).
                btn.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
                btn.setCursor(Qt.CursorShape.PointingHandCursor)
                # Jamais déclenché par Entrée : relancer COÛTE (choix explicite).
                btn.setAutoDefault(False)
                btn.setDefault(False)
                btn.setStyleSheet(_retry_style())
                btn.clicked.connect(lambda _c=False, pid=c["id"]: self._pick(pid))
                self.retry_buttons[btn] = c["id"]
                row.addWidget(btn)
        row.addStretch(1)
        self.ok_button = QPushButton("OK")
        self.ok_button.setFixedHeight(26)
        self.ok_button.setMinimumWidth(72)
        self.ok_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.ok_button.setAutoDefault(True)
        self.ok_button.setDefault(True)
        self.ok_button.setStyleSheet(_ok_style())
        self.ok_button.clicked.connect(self.accept)
        row.addWidget(self.ok_button)
        lay.addLayout(row)

        # Largeur : celle qu'exige la rangée de boutons, 560 au moins. Le texte
        # est replié à une largeur EXACTE : sans elle, Qt estime sa hauteur pour
        # une autre largeur et coupe la fin du message (1er rendu, 05/10/2026).
        m = lay.contentsMargins()
        width = max(560, row.minimumSize().width() + m.left() + m.right())
        for lbl in wrapped:
            lbl.setFixedWidth(width - m.left() - m.right() - 32 - top.spacing()
                              - (18 if len(message) > 1200 and lbl is msg else 0))
        self.setFixedWidth(width)

    def _pick(self, pid: str):
        self.chosen = pid
        self.accept()


def build(parent, message: str, choices: list[dict], title: str = "Erreur de génération"):
    """(fenêtre, {bouton: id du distributeur}) — séparé de `show` pour les tests.
    Un refus du filtre du propriétaire du modèle n'offre AUCUN autre
    distributeur : le message dit lui-même que c'est le même partout."""
    from core.worker import is_model_owner_refusal
    if choices and is_model_owner_refusal(message):
        choices = []
    dlg = _ErrorDialog(parent, message, choices, title)
    return dlg, dlg.retry_buttons


def show(parent, message: str, choices: list[dict], title: str = "Erreur de génération") -> str:
    """Affiche l'erreur ; rend l'id du distributeur choisi pour réessayer, ou ""."""
    dlg, _buttons = build(parent, message, choices, title)
    dlg.exec()
    return dlg.chosen
