"""
Dialog de synchronisation Storyboard ↔ Casting / Décors / Accessoires.

Affiche la progression en temps réel, liste les plans modifiés,
puis sauvegarde sur confirmation.
"""
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QScrollArea, QWidget, QFrame, QProgressBar,
)
from PyQt6.QtCore import Qt
from ui.styles import CP


# ── Dialog de confirmation avant synchronisation ───────────────────────────────

class StoryboardSyncConfirmDialog(QDialog):
    """
    Dialogue affiché avant de lancer la synchronisation.
    Explique ce qui va se passer et demande confirmation.
    """

    def __init__(self, n_shots: int, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Synchronisation — Confirmation")
        self.setMinimumWidth(500)
        self.setMaximumWidth(560)
        self.setSizePolicy(
            self.sizePolicy().horizontalPolicy(),
            self.sizePolicy().verticalPolicy(),
        )
        self.setStyleSheet(f"background:{CP['bg1']};")

        root = QVBoxLayout(self)
        root.setContentsMargins(28, 24, 28, 24)
        root.setSpacing(20)

        # ── Header ──────────────────────────────────────────────────────────
        hdr = QHBoxLayout()
        hdr.setSpacing(14)

        ico = QLabel("⟳")
        ico.setFixedSize(44, 44)
        ico.setAlignment(Qt.AlignmentFlag.AlignCenter)
        ico.setStyleSheet(
            f"font-size:22px;background:{CP['bg2']};border-radius:10px;"
            f"color:{CP.get('accent2', '#7c6bff')};"
        )
        hdr.addWidget(ico)

        title_col = QVBoxLayout()
        title_col.setSpacing(3)

        t = QLabel("Synchronisation du Storyboard")
        t.setStyleSheet(
            f"color:{CP['text_primary']};font-size:16px;"
            f"font-weight:700;background:transparent;"
        )
        title_col.addWidget(t)

        sub = QLabel(f"{n_shots} plan(s) analysé(s)")
        sub.setStyleSheet(
            f"color:{CP['text_dim']};font-size:10px;background:transparent;"
        )
        title_col.addWidget(sub)
        hdr.addLayout(title_col, 1)
        root.addLayout(hdr)

        # ── Séparateur ───────────────────────────────────────────────────────
        sep = QFrame()
        sep.setFixedHeight(1)
        sep.setStyleSheet(f"background:{CP['border']};")
        root.addWidget(sep)

        # ── Description ──────────────────────────────────────────────────────
        desc_lbl = QLabel(
            "La synchronisation va comparer votre storyboard avec le casting,\n"
            "les décors et les accessoires actuels. Elle se déroule en deux phases :"
        )
        desc_lbl.setStyleSheet(
            f"color:{CP['text_secondary']};font-size:12px;"
            f"line-height:1.5;background:transparent;"
        )
        desc_lbl.setWordWrap(True)
        root.addWidget(desc_lbl)

        # ── Phases ───────────────────────────────────────────────────────────
        phases_frame = QFrame()
        phases_frame.setStyleSheet(
            f"background:{CP['bg2']};border-radius:10px;border:1px solid {CP['border']};"
        )
        phases_lay = QVBoxLayout(phases_frame)
        phases_lay.setContentsMargins(16, 14, 16, 14)
        phases_lay.setSpacing(12)

        for badge, title, detail in [
            (
                "1",
                "Correspondance des noms  —  sans IA",
                "Détecte et réassigne les personnages, décors et accessoires dont\n"
                "le nom a légèrement changé (accents, articles, casse…).",
            ),
            (
                "2",
                "Vérification des prompts  —  Claude Haiku",
                "Analyse si les prompts reflètent encore les descriptions actuelles\n"
                "des éléments assignés. Réécrit uniquement ce qui est incohérent.",
            ),
        ]:
            row = QHBoxLayout()
            row.setSpacing(12)
            row.setAlignment(Qt.AlignmentFlag.AlignTop)

            badge_lbl = QLabel(badge)
            badge_lbl.setFixedSize(22, 22)
            badge_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            badge_lbl.setStyleSheet(
                f"background:{CP.get('accent2', '#7c6bff')};color:#fff;"
                f"border-radius:11px;font-size:10px;font-weight:700;"
            )
            row.addWidget(badge_lbl)

            text_col = QVBoxLayout()
            text_col.setSpacing(2)

            t_lbl = QLabel(title)
            t_lbl.setStyleSheet(
                f"color:{CP['text_primary']};font-size:11px;"
                f"font-weight:700;background:transparent;"
            )
            text_col.addWidget(t_lbl)

            d_lbl = QLabel(detail)
            d_lbl.setStyleSheet(
                f"color:{CP['text_secondary']};font-size:10px;background:transparent;"
            )
            d_lbl.setWordWrap(True)
            text_col.addWidget(d_lbl)

            row.addLayout(text_col, 1)
            phases_lay.addLayout(row)

        root.addWidget(phases_frame)

        # ── Note finale ──────────────────────────────────────────────────────
        note = QLabel(
            "✓  Aucune modification n'est appliquée sans votre confirmation finale."
        )
        note.setStyleSheet(
            f"color:{CP.get('accent', '#4ecdc4')};font-size:10px;"
            f"font-style:italic;background:transparent;"
        )
        note.setWordWrap(True)
        root.addWidget(note)

        # ── Séparateur footer ────────────────────────────────────────────────
        sep2 = QFrame()
        sep2.setFixedHeight(1)
        sep2.setStyleSheet(f"background:{CP['border']};")
        root.addWidget(sep2)

        # ── Boutons ──────────────────────────────────────────────────────────
        foot = QHBoxLayout()
        foot.setSpacing(12)

        btn_cancel = QPushButton("Annuler")
        btn_cancel.setMinimumHeight(40)
        btn_cancel.setMinimumWidth(110)
        btn_cancel.setStyleSheet(
            f"QPushButton{{background:{CP['bg3']};color:{CP['text_secondary']};"
            f"border:1px solid {CP['border']};border-radius:8px;"
            f"font-size:13px;font-weight:600;padding:0 20px;}}"
            f"QPushButton:hover{{background:{CP['bg2']};color:{CP['text_primary']};}}"
        )
        btn_cancel.clicked.connect(self.reject)
        foot.addWidget(btn_cancel)

        foot.addStretch()

        btn_ok = QPushButton("Continuer")
        btn_ok.setMinimumHeight(40)
        btn_ok.setMinimumWidth(130)
        btn_ok.setStyleSheet(
            f"QPushButton{{background:{CP.get('accent2', '#7c6bff')};color:#fff;"
            f"border:none;border-radius:8px;"
            f"font-size:13px;font-weight:700;padding:0 24px;}}"
            f"QPushButton:hover{{background:#9a8aff;}}"
        )
        btn_ok.clicked.connect(self.accept)
        btn_ok.setDefault(True)
        foot.addWidget(btn_ok)

        root.addLayout(foot)


# ── Ligne de résultat par plan ─────────────────────────────────────────────────

class _ShotSyncRow(QWidget):
    def __init__(self, shot: dict):
        super().__init__()
        self._shot = shot

        reassigned     = shot.get("_reassigned", [])
        prompt_changed = shot.get("_prompt_changed", False)
        old_prompt     = shot.get("_old_prompt", "")
        reason         = shot.get("_reason", "")

        changed = bool(reassigned or prompt_changed)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(10, 8, 10, 8)
        lay.setSpacing(4)

        # ── Ligne titre ───────────────────────────────────────────────────────
        top = QHBoxLayout()
        top.setSpacing(8)

        status_icon = "✎" if changed else "✓"
        status_color = CP.get("accent2", CP.get("accent", "#7c6bff")) if changed else CP.get("text_dim", "#5a6a7a")

        icon_lbl = QLabel(status_icon)
        icon_lbl.setStyleSheet(f"color:{status_color};font-size:13px;font-weight:700;background:transparent;")
        icon_lbl.setFixedWidth(18)
        top.addWidget(icon_lbl)

        num = shot.get("number", "?")
        num_lbl = QLabel(f"Plan {num}")
        num_lbl.setStyleSheet(
            f"color:#07080f;background:{status_color};"
            f"border-radius:3px;font-size:8px;font-weight:700;padding:1px 6px;"
        )
        num_lbl.setFixedHeight(17)
        top.addWidget(num_lbl)

        title = shot.get("scene_title", "—")
        title_lbl = QLabel(title)
        title_lbl.setStyleSheet(
            f"color:{CP['text_primary']};font-size:11px;font-weight:600;background:transparent;"
        )
        top.addWidget(title_lbl, 1)

        if not changed:
            ok_lbl = QLabel("inchangé")
            ok_lbl.setStyleSheet(
                f"color:{CP['text_dim']};font-size:9px;background:transparent;"
            )
            top.addWidget(ok_lbl)

        lay.addLayout(top)

        # ── Badges détails ────────────────────────────────────────────────────
        if reassigned:
            ra_lbl = QLabel("🔗 Assignation : " + " · ".join(reassigned))
            ra_lbl.setStyleSheet(
                f"color:{CP.get('accent', '#4ecdc4')};font-size:9px;"
                f"background:transparent;padding-left:26px;"
            )
            ra_lbl.setWordWrap(True)
            lay.addWidget(ra_lbl)

        if prompt_changed and reason:
            rs_lbl = QLabel(f"✎ {reason}")
            rs_lbl.setStyleSheet(
                f"color:{CP.get('accent2', '#7c6bff')};font-size:9px;"
                f"background:transparent;padding-left:26px;"
            )
            lay.addWidget(rs_lbl)

        if prompt_changed and old_prompt:
            old_lbl = QLabel(f"avant : {old_prompt[:100]}{'…' if len(old_prompt) > 100 else ''}")
            old_lbl.setStyleSheet(
                f"color:{CP['text_dim']};font-size:8px;font-family:'Consolas',monospace;"
                f"background:transparent;padding-left:26px;"
            )
            old_lbl.setWordWrap(True)
            lay.addWidget(old_lbl)

            new_prompt = shot.get("seedance_prompt", "")
            new_lbl = QLabel(f"après : {new_prompt[:100]}{'…' if len(new_prompt) > 100 else ''}")
            new_lbl.setStyleSheet(
                f"color:{CP['text_primary']};font-size:8px;font-family:'Consolas',monospace;"
                f"background:transparent;padding-left:26px;"
            )
            new_lbl.setWordWrap(True)
            lay.addWidget(new_lbl)


# ── Dialog principal ───────────────────────────────────────────────────────────

class StoryboardSyncDialog(QDialog):
    """
    Usage:
        dlg = StoryboardSyncDialog(shots, parent)
        dlg.exec()
        # shots saved internally on confirm
    """

    def __init__(self, shots: list, parent=None):
        super().__init__(parent)
        self._shots_in    = shots
        self._shots_out   = []
        self._worker      = None
        self._n_changed   = 0

        self.setWindowTitle("Synchronisation — Storyboard")
        self.setMinimumWidth(560)
        self.setMinimumHeight(440)
        self.setStyleSheet(f"background:{CP['bg1']};")

        root = QVBoxLayout(self)
        root.setContentsMargins(24, 20, 24, 20)
        root.setSpacing(16)

        # ── Header ──────────────────────────────────────────────────────────
        hdr = QHBoxLayout()
        ico = QLabel("⟳")
        ico.setFixedSize(36, 36)
        ico.setAlignment(Qt.AlignmentFlag.AlignCenter)
        ico.setStyleSheet(
            f"font-size:20px;background:{CP['bg2']};border-radius:8px;"
            f"color:{CP.get('accent2', CP.get('accent', '#7c6bff'))};"
        )
        hdr.addWidget(ico)
        _col = QVBoxLayout()
        _col.setSpacing(2)
        _t = QLabel("Synchronisation du Storyboard")
        _t.setStyleSheet(
            f"color:{CP['text_primary']};font-size:16px;font-weight:700;background:transparent;"
        )
        _col.addWidget(_t)
        self._phase_lbl = QLabel("Analyse en cours…")
        self._phase_lbl.setStyleSheet(
            f"color:{CP['text_dim']};font-size:10px;background:transparent;"
        )
        _col.addWidget(self._phase_lbl)
        hdr.addLayout(_col, 1)
        root.addLayout(hdr)

        sep = QFrame()
        sep.setFixedHeight(1)
        sep.setStyleSheet(f"background:{CP['border']};")
        root.addWidget(sep)

        # ── Progress ─────────────────────────────────────────────────────────
        self._progress = QProgressBar()
        self._progress.setRange(0, 0)
        self._progress.setFixedHeight(4)
        self._progress.setTextVisible(False)
        self._progress.setStyleSheet(
            f"QProgressBar{{background:{CP['bg3']};border:none;border-radius:2px;}}"
            f"QProgressBar::chunk{{background:{CP.get('accent2', CP.get('accent','#7c6bff'))};border-radius:2px;}}"
        )
        root.addWidget(self._progress)

        self._status_lbl = QLabel("Chargement du casting…")
        self._status_lbl.setStyleSheet(
            f"color:{CP['text_secondary']};font-size:11px;background:transparent;"
        )
        root.addWidget(self._status_lbl)

        # ── Liste résultats (cachée jusqu'à la fin) ──────────────────────────
        self._list_frame = QWidget()
        self._list_frame.setVisible(False)
        self._list_frame.setStyleSheet("background:transparent;")
        self._list_lay = QVBoxLayout(self._list_frame)
        self._list_lay.setContentsMargins(0, 0, 0, 0)
        self._list_lay.setSpacing(2)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet("QScrollArea{background:transparent;border:none;}")
        scroll.setWidget(self._list_frame)
        scroll.setMinimumHeight(180)
        root.addWidget(scroll, 1)

        # ── Résumé ────────────────────────────────────────────────────────────
        self._summary_lbl = QLabel("")
        self._summary_lbl.setStyleSheet(
            f"color:{CP['accent']};font-size:10px;"
            f"font-family:'Consolas',monospace;background:transparent;"
        )
        self._summary_lbl.setVisible(False)
        root.addWidget(self._summary_lbl)

        # ── Footer ────────────────────────────────────────────────────────────
        sep2 = QFrame()
        sep2.setFixedHeight(1)
        sep2.setStyleSheet(f"background:{CP['border']};")
        root.addWidget(sep2)

        foot = QHBoxLayout()
        foot.setSpacing(10)

        self._btn_cancel = QPushButton("Annuler")
        self._btn_cancel.setMinimumHeight(36)
        self._btn_cancel.setMinimumWidth(90)
        self._btn_cancel.setStyleSheet(
            f"QPushButton{{background:{CP['bg3']};color:{CP['text_secondary']};"
            f"border:1px solid {CP['border']};border-radius:8px;font-size:12px;font-weight:600;"
            f"padding:0 18px;}}"
            f"QPushButton:hover{{background:{CP['bg2']};}}"
        )
        self._btn_cancel.clicked.connect(self._on_cancel)
        foot.addWidget(self._btn_cancel)

        foot.addStretch()

        self._btn_confirm = QPushButton("Appliquer la synchronisation")
        self._btn_confirm.setMinimumHeight(36)
        self._btn_confirm.setMinimumWidth(180)
        self._btn_confirm.setVisible(False)
        self._btn_confirm.setStyleSheet(
            f"QPushButton{{background:{CP.get('accent2', CP.get('accent','#7c6bff'))};color:#fff;"
            f"border:none;border-radius:8px;font-size:12px;font-weight:700;padding:0 18px;}}"
            f"QPushButton:hover{{background:#9a8aff;}}"
            f"QPushButton:disabled{{background:{CP['bg3']};color:{CP['text_dim']};"
            f"border:1px solid {CP['border']};}}"
        )
        self._btn_confirm.clicked.connect(self._on_confirm)
        foot.addWidget(self._btn_confirm)

        root.addLayout(foot)

        self._start()

    # ── Worker ─────────────────────────────────────────────────────────────────

    def _start(self):
        from api.screenplay import SyncStoryboardWorker
        w = SyncStoryboardWorker(self._shots_in)
        self._worker = w
        w.progress.connect(self._on_progress)
        w.finished.connect(self._on_done)
        w.failed.connect(self._on_failed)
        w.start()

    def _on_progress(self, pct: int, msg: str):
        self._progress.setRange(0, 100)
        self._progress.setValue(pct)
        self._status_lbl.setText(msg)
        self._phase_lbl.setText(msg)

    def _on_done(self, shots: list):
        self._shots_out = shots
        self._progress.setRange(0, 1)
        self._progress.setValue(1)

        changed   = [s for s in shots if s.get("_reassigned") or s.get("_prompt_changed")]
        unchanged = [s for s in shots if not s.get("_reassigned") and not s.get("_prompt_changed")]
        self._n_changed = len(changed)

        self._list_frame.setVisible(True)

        # Changed first, then unchanged
        for shot in changed + unchanged:
            row = _ShotSyncRow(shot)
            self._list_lay.addWidget(row)
        self._list_lay.addStretch()

        total = len(shots)
        n_reassign = sum(1 for s in shots if s.get("_reassigned"))
        n_prompt   = sum(1 for s in shots if s.get("_prompt_changed"))

        if self._n_changed:
            self._phase_lbl.setText(f"{self._n_changed} plan(s) à mettre à jour")
            self._status_lbl.setText(
                f"{n_prompt} prompt(s) réécrit(s) · {n_reassign} ré-assignation(s) sur {total} plans"
            )
            self._summary_lbl.setText(
                f"✓  {self._n_changed}/{total} plans modifiés · {n_prompt} prompts · {n_reassign} assignations"
            )
            self._btn_confirm.setText(f"Appliquer ({self._n_changed} plan(s))")
            self._btn_confirm.setVisible(True)
        else:
            self._phase_lbl.setText("Tout est synchronisé")
            self._status_lbl.setText(
                f"Aucune mise à jour nécessaire — {total} plan(s) analysé(s), tout est cohérent."
            )
            self._summary_lbl.setText(f"✓  {total} plans analysés — storyboard déjà synchronisé")
            self._btn_cancel.setText("Fermer")

        self._summary_lbl.setVisible(True)

    def _on_failed(self, err: str):
        self._progress.setRange(0, 1)
        self._progress.setValue(0)
        self._phase_lbl.setText("Erreur")
        self._status_lbl.setText(f"⚠ {err[:180]}")
        self._btn_cancel.setText("Fermer")

    # ── Actions ────────────────────────────────────────────────────────────────

    def _on_confirm(self):
        if not self._shots_out:
            self.accept()
            return
        self._btn_confirm.setEnabled(False)
        self._btn_confirm.setText("Sauvegarde…")
        try:
            import core.storyboard as sb_api
            for shot in self._shots_out:
                if shot.get("_reassigned") or shot.get("_prompt_changed"):
                    clean = {k: v for k, v in shot.items() if not k.startswith("_")}
                    sb_api.save_shot(clean)
        except Exception as e:
            self._status_lbl.setText(f"⚠ Erreur sauvegarde : {e}")
            self._btn_confirm.setEnabled(True)
            self._btn_confirm.setText(f"Appliquer ({self._n_changed} plan(s))")
            return
        self.accept()

    def _on_cancel(self):
        if self._worker and self._worker.isRunning():
            self._worker.terminate()
        self.reject()
