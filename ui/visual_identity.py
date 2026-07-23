"""Contrôleur UI partagé pour l'identité visuelle des cinq familles."""

from __future__ import annotations

import os

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QDialog, QHBoxLayout, QLabel, QPushButton, QTextEdit, QVBoxLayout,
)

from core.i18n import translate
from core.visual_identity import (
    identity_matches_image, pending_identity, ready_identity,
)
from core.worker import abandon_thread
from ui.styles import CP


def _status(owner, text: str):
    widget = getattr(owner, "_status", None)
    if widget is not None:
        widget.setText(translate(text))


def current_prompt(owner) -> str:
    widget = getattr(owner, "_prompt", None)
    try:
        return widget.toPlainText().strip()
    except Exception:
        return ""


def prepare_owner(owner, entity_type: str, item: dict):
    owner._visual_identity_type = entity_type
    owner._visual_identity = dict((item or {}).get("visual_identity") or {})
    owner._visual_identity_worker = None

    def _cleanup():
        worker = getattr(owner, "_visual_identity_worker", None)
        if worker is not None and worker.isRunning():
            abandon_thread(worker)

    owner.destroyed.connect(_cleanup)


def analyze_active_image(owner, image_path: str, source: str = "selected",
                         force: bool = False):
    """Analyse en arrière-plan ; ne bloque jamais la sélection de l'image."""
    if not image_path or not os.path.isfile(image_path):
        owner._visual_identity = pending_identity(image_path, source)
        return
    previous = getattr(owner, "_visual_identity", {}) or {}
    if not force and identity_matches_image(previous, image_path):
        _status(owner, "Identité visuelle vérifiée ✓")
        return
    owner._visual_identity = pending_identity(image_path, source, previous)
    old = getattr(owner, "_visual_identity_worker", None)
    if old is not None and old.isRunning():
        abandon_thread(old)
    from api.visual_identity import VisualIdentityWorker
    worker = VisualIdentityWorker(
        getattr(owner, "_visual_identity_type", "accessory"),
        image_path,
        source=source,
        current_description=current_prompt(owner),
    )
    owner._visual_identity_worker = worker
    _status(owner, "Analyse de l'image active pour la continuité…")

    def _done(identity: dict):
        owner._visual_identity = identity
        _status(owner, "Identité visuelle analysée et liée à cette image ✓")
        btn = getattr(owner, "_btn_visual_identity", None)
        if btn is not None:
            btn.setEnabled(True)

    def _failed(message: str):
        # L'image reste utilisable ; son ancienne description n'est simplement pas
        # présentée comme vérifiée. Jamais de JSON brut d'API dans le libellé.
        low = (message or "").lower()
        if "invalid_request_error" in low or "error code: 4" in low:
            message = "requête refusée par le moteur vision — relancez via « Identité visuelle »"
        _status(owner, f"Image active enregistrée · analyse visuelle en attente : {message[:90]}")

    worker.done.connect(_done)
    worker.failed.connect(_failed)
    worker.start()


# Workers détachés (analyse proposée à la SAUVEGARDE) : gardés vivants ici même
# quand le dialogue d'origine est fermé — le résultat est réécrit dans la fiche.
_DETACHED_WORKERS: list = []


def offer_analysis_after_save(parent_widget, entity_type: str, saved: dict,
                              save_fn) -> None:
    """Après la sauvegarde d'un élément (demande Matthieu 2026-07-23) : si
    l'image active n'a pas d'identité visuelle vérifiée (nouvelle image,
    variation…), propose d'analyser l'image pour adapter automatiquement les
    prompts du Storyboard partout où l'élément apparaît.

    L'analyse tourne DÉTACHÉE du dialogue : son résultat est persisté via
    ``save_fn`` même si la fenêtre d'édition est déjà fermée. Ne lève jamais.
    """
    try:
        saved = dict(saved or {})
        image_path = saved.get("image_path", "")
        if not saved.get("id") or not image_path or not os.path.isfile(image_path):
            return
        if identity_matches_image(dict(saved.get("visual_identity") or {}), image_path):
            return   # identité déjà vérifiée pour cette image — rien à proposer
        from core.ai_provider import key_error
        if key_error("vision"):
            return   # pas de moteur vision configuré — ne pas promettre l'analyse
        from PyQt6.QtWidgets import QMessageBox
        name = saved.get("name") or ""
        rep = QMessageBox.question(
            parent_widget,
            translate("Analyser la nouvelle image ?"),
            translate(
                "L'image active de « {name} » a changé.\n\n"
                "Voulez-vous l'analyser maintenant pour adapter automatiquement "
                "les prompts du Storyboard dans tous les plans où cet élément "
                "apparaît ?"
            ).format(name=name),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if rep != QMessageBox.StandardButton.Yes:
            return
        from api.visual_identity import VisualIdentityWorker
        worker = VisualIdentityWorker(
            entity_type, image_path, source="selected",
            current_description=(saved.get("prompt") or saved.get("description") or ""),
        )
        _DETACHED_WORKERS.append(worker)

        def _persist(identity_out: dict):
            try:
                fresh = dict(saved)
                fresh["visual_identity"] = identity_out
                save_fn(fresh)
            except Exception:
                pass
            finally:
                try:
                    _DETACHED_WORKERS.remove(worker)
                except ValueError:
                    pass

        def _abandon(_msg: str):
            try:
                _DETACHED_WORKERS.remove(worker)
            except ValueError:
                pass

        worker.done.connect(_persist)
        worker.failed.connect(_abandon)
        worker.start()
    except Exception:
        pass


def show_identity_editor(owner):
    identity = getattr(owner, "_visual_identity", {}) or {}
    path = getattr(owner, "_image_path", "") or ""
    dlg = QDialog(owner)
    dlg.setWindowTitle(translate("Identité visuelle canonique"))
    dlg.setMinimumSize(660, 460)
    dlg.setStyleSheet(f"QDialog{{background:{CP['bg1']};}}")
    lay = QVBoxLayout(dlg)
    lay.setContentsMargins(20, 18, 20, 18)
    lay.setSpacing(12)

    intro = QLabel(translate(
        "Cette description est liée à l'image active. Elle sera injectée avec "
        "l'image de référence dans les prompts du Storyboard. Ne conserve que les "
        "caractéristiques stables de l'entité."
    ))
    intro.setWordWrap(True)
    intro.setStyleSheet(f"color:{CP['text_secondary']};font-size:11px;")
    lay.addWidget(intro)

    edit = QTextEdit()
    edit.setPlainText(str(identity.get("canonical_description") or ""))
    edit.setPlaceholderText(translate("Description visuelle canonique…"))
    edit.setStyleSheet(
        f"QTextEdit{{background:{CP['bg2']};color:{CP['text_primary']};"
        f"border:1px solid {CP['border']};border-radius:8px;padding:10px;}}"
    )
    lay.addWidget(edit, 1)

    meta = QLabel(translate(
        f"Statut : {identity.get('status', 'absente')}  ·  "
        f"Source : {identity.get('source', '—')}  ·  "
        f"Analyse : {identity.get('analysis_model', '—')}"
    ))
    meta.setStyleSheet(f"color:{CP['text_dim']};font-size:9px;")
    lay.addWidget(meta)

    row = QHBoxLayout()
    reanalyze = QPushButton(translate("↻  Réanalyser l'image active"))
    cancel = QPushButton(translate("Annuler"))
    save = QPushButton(translate("✓  Enregistrer l'identité"))
    for button in (reanalyze, cancel, save):
        button.setMinimumHeight(34)
    reanalyze.clicked.connect(lambda: (dlg.reject(), analyze_active_image(
        owner, path, source=identity.get("source") or "selected", force=True
    )))
    cancel.clicked.connect(dlg.reject)

    def _save():
        description = edit.toPlainText().strip()
        if description:
            analysis = dict(identity)
            analysis["canonical_description"] = description
            owner._visual_identity = ready_identity(
                path, identity.get("source") or "manual", analysis,
                identity.get("analysis_model") or "validation humaine",
            )
        dlg.accept()

    save.clicked.connect(_save)
    row.addWidget(reanalyze)
    row.addStretch()
    row.addWidget(cancel)
    row.addWidget(save)
    lay.addLayout(row)
    dlg.exec()


def make_identity_button(owner) -> QPushButton:
    button = QPushButton(translate("📌  Identité visuelle"))
    button.setMinimumHeight(30)
    button.setToolTip(translate(
        "Voir ou corriger la description exacte déduite de l'image active"
    ))
    button.setStyleSheet(
        f"QPushButton{{background:transparent;color:{CP['accent']};"
        f"border:1px solid {CP['accent']};border-radius:6px;font-size:10px;font-weight:700;}}"
        f"QPushButton:hover{{background:{CP['bg3']};}}"
    )
    button.clicked.connect(lambda: show_identity_editor(owner))
    owner._btn_visual_identity = button
    return button
