"""ui/generation_error_dialog.py — LA fenêtre d'erreur d'une génération vidéo du
Studio, commune aux deux éditions.

Demande Matthieu du 05/10/2026 : « lorsqu'il y a un message d'erreur, ce serait
bien qu'on puisse avoir une option essayer avec un autre distributeur » — SANS
bascule automatique (« comme ça, on est au courant qu'il y a un problème avec
ce distributeur »). Chaque distributeur capable de faire le plan a son bouton,
avec le prix du plan chez lui ; le choisir le met en tête de l'ordre (comme le
menu Distributeur du Studio) et relance.

Elle remplace aussi deux défauts : le Studio ouvrait DEUX fenêtres à la suite
(show_api_error, puis « Une erreur est survenue » ou « génération en série
interrompue »), et la fenêtre des crédits annonçait « fal.ai » quel que soit le
distributeur.
"""
from __future__ import annotations

from PyQt6.QtWidgets import QMessageBox

from core.i18n import translate

#: Au-delà, la fenêtre deviendrait un mur de boutons.
_MAX_CHOICES = 3


def alternatives(engine: str, resolution: str, seconds: float, audio: bool = True,
                 exclude: str = "", mode: str = "") -> list[dict]:
    """Distributeurs à proposer pour réessayer, dans l'ordre de priorité :
    clé présente, demande couverte (moteur, résolution, son), refus pas déjà
    connu (Seedance non activé chez BytePlus, crédit Runware…), et autre que
    celui qui vient d'échouer. [{id, name, cost}]"""
    from core import media_provider as mp
    from core.config import load_config
    try:
        from api import distrib_probe as dp
    except Exception:
        dp = None
    cfg = load_config()
    quotes = {q["id"]: q for q in mp.quotes(engine, resolution, seconds, mode=mode, audio=audio)}
    out: list[dict] = []
    for pid in mp.provider_order(cfg):
        q = quotes.get(pid) or {}
        if pid == exclude or not q.get("supported") or not q.get("has_key"):
            continue
        if dp is not None:
            known, _why = dp.can_receive(pid, (), network=False, cfg=cfg, engine=engine)
            if known is False:
                continue
        out.append({"id": pid, "name": mp.provider_short(pid), "cost": q.get("cost")})
    return out[:_MAX_CHOICES]


def build(parent, message: str, choices: list[dict], title: str = "Erreur de génération"):
    """(fenêtre, {bouton: id du distributeur}) — séparé de `show` pour les tests."""
    from core.worker import is_credit_error
    box = QMessageBox(parent)
    box.setIcon(QMessageBox.Icon.Critical)
    box.setWindowTitle(translate("Crédits insuffisants") if is_credit_error(message)
                       else translate(title))
    box.setText(message)
    if choices:
        box.setInformativeText(translate(
            "Aucun autre distributeur n'est essayé sans ton accord. Réessayer avec :"))
    by_button = {}
    for c in choices:
        # Libellé COURT (le rendu tronquait « Réessayer avec Runware (≈ 9.2… ») ;
        # prix au format du menu Distributeur.
        label = f"↻  {c['name']}"
        if c.get("cost") is not None:
            label += f"  ≈ ${c['cost']:.2f}"
        btn = box.addButton(label, QMessageBox.ButtonRole.ActionRole)
        btn.setMinimumWidth(btn.fontMetrics().horizontalAdvance(label) + 48)
        by_button[btn] = c["id"]
    ok = box.addButton(QMessageBox.StandardButton.Ok)
    box.setDefaultButton(ok)
    return box, by_button


def show(parent, message: str, choices: list[dict], title: str = "Erreur de génération") -> str:
    """Affiche l'erreur ; rend l'id du distributeur choisi pour réessayer, ou ""."""
    box, by_button = build(parent, message, choices, title)
    box.exec()
    return by_button.get(box.clickedButton(), "")
