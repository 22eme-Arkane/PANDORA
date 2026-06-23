"""
ui/dialog_room_variations.py — Variations d'une PIÈCE entière (toutes ses vues).

Depuis la page Décors, sur le bandeau d'une pièce (7 vues groupées par room_group),
le bouton « 🎲 Variations » ouvre cette fenêtre : on édite le prompt et on régénère
EN BLOC toutes les vues de la pièce (le groupe entier — pas vue par vue). Chaque
nouvelle image remplace l'aperçu de sa vue ; l'ancienne est conservée dans la
galerie du décor (variante). Le plan d'architecture est régénéré et repartagé.

Réutilise api.nano_banana.GenerateRoomViewsWorker (le même moteur 7 vues).
"""

import os

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QTextEdit, QProgressBar,
)
from PyQt6.QtCore import Qt, pyqtSignal

from ui.styles import CP, PANDORA_STYLESHEET
from core.i18n import translate
import core.decors as decors_api

# Code de vue (worker) → libellé room_view stocké sur le décor.
_CODE_TO_RV = {
    "ensemble": "Ensemble", "avant": "Avant", "arriere": "Arrière",
    "gauche": "Gauche", "droite": "Droite", "sol": "Sol", "plafond": "Plafond",
}


class RoomVariationsDialog(QDialog):
    """Régénère toutes les vues d'une pièce avec un prompt édité (variations)."""
    done = pyqtSignal()   # PAS « finished » : émis quand des variations ont été créées

    def __init__(self, parent, room_group: str, decors: list):
        super().__init__(parent)
        self._room = room_group or "Décor"
        self._decors = list(decors or [])
        self._worker = None
        self._created = False

        self.setWindowTitle(f"{translate('Variations')} — {self._room}")
        self.setStyleSheet(PANDORA_STYLESHEET + f"QDialog{{background:{CP['bg1']};}}")
        self.setMinimumWidth(560)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(20, 18, 20, 18)
        lay.setSpacing(12)

        title = QLabel("🎲  " + translate("Créer des variations de la pièce"))
        title.setStyleSheet(
            f"color:{CP['accent']};font-size:14px;font-weight:800;background:transparent;")
        lay.addWidget(title)

        views = [d.get("room_view", "") for d in self._decors if d.get("room_view")]
        sub = QLabel(
            translate("Régénère EN BLOC toutes les vues de la pièce")
            + f" ({len(self._decors)}) : " + (", ".join(views) if views else "—")
            + ".\n" + translate("L'ancienne image de chaque vue est conservée en variante."))
        sub.setWordWrap(True)
        sub.setStyleSheet(f"color:{CP['text_dim']};font-size:11px;background:transparent;")
        lay.addWidget(sub)

        lbl = QLabel(translate("Prompt (éditable) :"))
        lbl.setStyleSheet(f"color:{CP['text_secondary']};font-size:11px;background:transparent;")
        lay.addWidget(lbl)

        self._prompt = QTextEdit()
        self._prompt.setPlainText(self._base_prompt())
        self._prompt.setFixedHeight(120)
        self._prompt.setStyleSheet(
            f"QTextEdit{{background:{CP['bg3']};border:1px solid {CP['border']};"
            f"border-radius:6px;color:{CP['text_primary']};font-size:12px;padding:8px;}}"
            f"QTextEdit:focus{{border-color:{CP['accent']};}}")
        lay.addWidget(self._prompt)

        self._progress = QProgressBar()
        self._progress.setRange(0, 100)
        self._progress.setVisible(False)
        self._progress.setFixedHeight(6)
        self._progress.setTextVisible(False)
        self._progress.setStyleSheet(
            f"QProgressBar{{background:{CP['bg3']};border:none;border-radius:3px;}}"
            f"QProgressBar::chunk{{background:{CP['accent']};border-radius:3px;}}")
        lay.addWidget(self._progress)

        self._status = QLabel("")
        self._status.setWordWrap(True)
        self._status.setStyleSheet(f"color:{CP['text_dim']};font-size:10px;background:transparent;")
        lay.addWidget(self._status)

        row = QHBoxLayout()
        row.addStretch()
        cancel = QPushButton(translate("Fermer"))
        cancel.setFixedHeight(34)
        cancel.setStyleSheet(
            f"QPushButton{{background:transparent;color:{CP['text_dim']};"
            f"border:1px solid {CP['border']};border-radius:8px;font-size:12px;padding:0 18px;}}"
            f"QPushButton:hover{{color:{CP['text_primary']};border-color:{CP['text_primary']};}}")
        cancel.clicked.connect(self.reject)
        self._btn_gen = QPushButton("🎲  " + translate("Générer les variations"))
        self._btn_gen.setFixedHeight(34)
        self._btn_gen.setStyleSheet(
            f"QPushButton{{background:{CP['accent']};color:#07080f;border:none;"
            f"border-radius:8px;font-size:12px;font-weight:700;padding:0 22px;}}"
            f"QPushButton:hover{{background:#6eded6;}}"
            f"QPushButton:disabled{{background:{CP['bg3']};color:{CP['text_dim']};}}")
        self._btn_gen.clicked.connect(self._on_generate)
        row.addWidget(cancel)
        row.addWidget(self._btn_gen)
        lay.addLayout(row)

    def _base_prompt(self) -> str:
        """Prompt de départ = celui de la vue d'ensemble, sinon le 1er décor."""
        ov = next((d for d in self._decors if d.get("room_view") == "Ensemble"), None)
        d = ov or (self._decors[0] if self._decors else {})
        return d.get("prompt", "") or d.get("description", "") or self._room

    # ── Génération ──────────────────────────────────────────────────────────────

    def _on_generate(self):
        prompt = self._prompt.toPlainText().strip()
        if not prompt:
            self._status.setText(translate("Écris un prompt."))
            return
        if self._worker is not None and self._worker.isRunning():
            return
        import core.style as style_api
        from api.nano_banana import GenerateRoomViewsWorker
        self._btn_gen.setEnabled(False)
        self._progress.setVisible(True)
        self._progress.setValue(0)
        self._status.setText(translate("Génération des variations…"))
        self._worker = GenerateRoomViewsWorker(
            base_prompt=prompt, decor_name=self._room,
            style_suffix=style_api.get_image_suffix())
        self._worker.progress.connect(lambda pct, msg: (self._progress.setValue(pct),
                                                        self._status.setText(translate(msg))))
        self._worker.views_finished.connect(self._on_done)
        self._worker.failed.connect(self._on_fail)
        self._worker.start()

    def _on_done(self, views: list):
        self._btn_gen.setEnabled(True)
        self._progress.setVisible(False)
        all_views = [v for v in (views or []) if v.get("path") and os.path.isfile(v["path"])]
        fp = next((v.get("path") for v in all_views if v.get("is_floor_plan")), "")
        by_rv = {d.get("room_view", ""): d for d in self._decors}
        n = 0
        for v in all_views:
            if v.get("is_floor_plan"):
                continue
            rv = _CODE_TO_RV.get(v.get("code", ""), v.get("label", ""))
            d = by_rv.get(rv)
            if not d:
                continue
            d = decors_api.get_decor(d.get("id", "")) or d
            gallery = [p for p in (d.get("generated_images") or []) if p and os.path.isfile(p)]
            old = d.get("image_path", "")
            if old and old not in gallery and os.path.isfile(old):
                gallery.append(old)        # ancienne image conservée en variante
            new_path = v["path"]
            if new_path not in gallery:
                gallery.append(new_path)
            d["image_path"] = new_path     # la variation devient l'aperçu courant
            d["generated_images"] = gallery
            d["prompt"] = self._prompt.toPlainText().strip() or d.get("prompt", "")
            if fp:
                d["floor_plan"] = fp
            decors_api.save_decor(d)
            n += 1
        if n:
            self._created = True
            self.done.emit()
            self._status.setText(translate("{n} vue(s) régénérée(s) en variations.").format(n=n))
        else:
            self._status.setText(
                translate("Aucune vue régénérée (mode mock sans clé fal.ai, ou échec)."))

    def _on_fail(self, err: str):
        self._btn_gen.setEnabled(True)
        self._progress.setVisible(False)
        self._status.setText(translate("Erreur :") + " " + str(err)[:160])
