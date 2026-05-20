"""
Dialog for storyboard generation with preview.

Flow:
  1. Opens and immediately starts GenerateStoryboardWorker (Claude Sonnet).
  2. Shows an indeterminate progress bar while Claude works.
  3. When shots arrive, displays them as rows (Plan N / title / camera / duration).
  4. User confirms → shots saved to storyboard.  Cancel → nothing saved.
"""
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QScrollArea, QWidget, QFrame, QProgressBar,
)
from PyQt6.QtCore import Qt
from ui.styles import CP


# ── Shot row ───────────────────────────────────────────────────────────────────

class _ShotRow(QWidget):
    def __init__(self, shot: dict):
        super().__init__()
        lay = QHBoxLayout(self)
        lay.setContentsMargins(10, 6, 10, 6)
        lay.setSpacing(10)

        num = shot.get("number", "?")
        badge = QLabel(f"Plan {num}")
        badge.setStyleSheet(
            f"color:#07080f;background:{CP.get('accent2', CP.get('accent', '#7c6bff'))};"
            f"border-radius:3px;font-size:8px;font-weight:700;padding:1px 6px;"
        )
        badge.setFixedHeight(17)
        lay.addWidget(badge)

        title = QLabel(shot.get("scene_title", "—"))
        title.setStyleSheet(
            f"color:{CP['text_primary']};font-size:11px;font-weight:600;background:transparent;"
        )
        title.setSizePolicy(title.sizePolicy().horizontalPolicy(),
                            title.sizePolicy().verticalPolicy())
        lay.addWidget(title, 1)

        move = shot.get("camera_movement", "")
        size = shot.get("shot_size", "")
        cam_info = " · ".join(filter(None, [move, size]))
        if cam_info:
            cam_lbl = QLabel(cam_info)
            cam_lbl.setStyleSheet(
                f"color:{CP['text_dim']};font-size:9px;background:transparent;"
            )
            lay.addWidget(cam_lbl)

        dur = shot.get("duration", 5)
        dur_lbl = QLabel(f"{dur:.0f}s")
        dur_lbl.setStyleSheet(
            f"color:{CP['accent']};font-size:9px;font-family:'Consolas',monospace;"
            f"background:transparent;min-width:28px;"
        )
        dur_lbl.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        lay.addWidget(dur_lbl)


# ── Main dialog ────────────────────────────────────────────────────────────────

class StoryboardGenerateDialog(QDialog):
    """
    Usage:
        dlg = StoryboardGenerateDialog(scenario_text, duration_secs, scenario_id, parent)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            # shots already saved — nothing extra to do
    """

    def __init__(self, scenario_text: str, duration_secs: int = 0,
                 scenario_id: str = "", parent=None):
        super().__init__(parent)
        self._scenario_text  = scenario_text
        self._duration_secs  = duration_secs
        self._scenario_id    = scenario_id
        self._shots: list[dict] = []
        self._worker = None

        self.setWindowTitle("Générer le Storyboard")
        self.setMinimumWidth(540)
        self.setMinimumHeight(420)
        self.setStyleSheet(f"background:{CP['bg1']};")

        root = QVBoxLayout(self)
        root.setContentsMargins(24, 20, 24, 20)
        root.setSpacing(16)

        # ── Header ──────────────────────────────────────────────────────────────
        hdr = QHBoxLayout()
        ico = QLabel("⬡")
        ico.setFixedSize(36, 36)
        ico.setAlignment(Qt.AlignmentFlag.AlignCenter)
        ico.setStyleSheet(f"font-size:20px;background:{CP['bg2']};border-radius:8px;")
        hdr.addWidget(ico)
        _col = QVBoxLayout()
        _col.setSpacing(2)
        _t = QLabel("Découpage Storyboard")
        _t.setStyleSheet(
            f"color:{CP['text_primary']};font-size:16px;font-weight:700;background:transparent;"
        )
        _col.addWidget(_t)
        self._phase_lbl = QLabel("Claude génère le découpage technique…")
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

        # ── Progress bar (indeterminate while generating) ────────────────────────
        self._progress = QProgressBar()
        self._progress.setRange(0, 0)
        self._progress.setFixedHeight(4)
        self._progress.setTextVisible(False)
        self._progress.setStyleSheet(
            f"QProgressBar{{background:{CP['bg3']};border:none;border-radius:2px;}}"
            f"QProgressBar::chunk{{background:{CP.get('accent2', CP.get('accent','#7c6bff'))};border-radius:2px;}}"
        )
        root.addWidget(self._progress)

        self._status_lbl = QLabel("Analyse du scénario via Claude Sonnet…")
        self._status_lbl.setStyleSheet(
            f"color:{CP['text_secondary']};font-size:11px;background:transparent;"
        )
        root.addWidget(self._status_lbl)

        # ── Shot list (hidden until generation done) ─────────────────────────────
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

        # ── Summary label ────────────────────────────────────────────────────────
        self._summary_lbl = QLabel("")
        self._summary_lbl.setStyleSheet(
            f"color:{CP['accent']};font-size:10px;"
            f"font-family:'Consolas',monospace;background:transparent;"
        )
        self._summary_lbl.setVisible(False)
        root.addWidget(self._summary_lbl)

        # ── Footer ──────────────────────────────────────────────────────────────
        sep2 = QFrame()
        sep2.setFixedHeight(1)
        sep2.setStyleSheet(f"background:{CP['border']};")
        root.addWidget(sep2)

        foot = QHBoxLayout()
        foot.setSpacing(10)

        self._btn_cancel = QPushButton("Annuler")
        self._btn_cancel.setFixedHeight(36)
        self._btn_cancel.setStyleSheet(
            f"QPushButton{{background:{CP['bg3']};color:{CP['text_secondary']};"
            f"border:1px solid {CP['border']};border-radius:8px;font-size:12px;font-weight:600;}}"
            f"QPushButton:hover{{background:{CP['bg2']};}}"
        )
        self._btn_cancel.clicked.connect(self._on_cancel)
        foot.addWidget(self._btn_cancel)

        foot.addStretch()

        self._btn_confirm = QPushButton("Importer dans le Storyboard")
        self._btn_confirm.setFixedHeight(36)
        self._btn_confirm.setVisible(False)
        self._btn_confirm.setStyleSheet(
            f"QPushButton{{background:{CP.get('accent2', CP.get('accent','#7c6bff'))};color:#fff;"
            f"border:none;border-radius:8px;font-size:12px;font-weight:700;}}"
            f"QPushButton:hover{{opacity:0.85;}}"
            f"QPushButton:disabled{{background:{CP['bg3']};color:{CP['text_dim']};"
            f"border:1px solid {CP['border']};}}"
        )
        self._btn_confirm.clicked.connect(self._on_confirm)
        foot.addWidget(self._btn_confirm)

        root.addLayout(foot)

        # Start generation immediately
        self._start()

    # ── Generation ────────────────────────────────────────────────────────────

    def _start(self):
        from api.screenplay import GenerateStoryboardWorker

        # Charge les noms exacts des éléments pour que Claude les réutilise à l'identique
        element_names: dict = {}
        try:
            import core.casting as casting_api
            import core.decors as decors_api
            import core.accessories as acc_api
            import core.vehicles as veh_api
            chars = [c["name"] for c in casting_api.list_characters() if c.get("name")]
            decs  = [d["name"] for d in decors_api.list_decors()       if d.get("name")]
            accs  = [a["name"] for a in acc_api.list_accessories()      if a.get("name")]
            vehs  = [v["name"] for v in veh_api.list_vehicles()         if v.get("name")]
            if chars:
                element_names["characters"]  = chars
            if decs:
                element_names["decors"]      = decs
            if accs:
                element_names["accessories"] = accs
            if vehs:
                element_names["vehicles"]    = vehs
        except Exception:
            pass  # éléments non critiques — la génération continue sans eux

        w = GenerateStoryboardWorker(
            self._scenario_text, self._duration_secs,
            element_names=element_names or None,
        )
        self._worker = w
        w.finished.connect(self._on_done)
        w.failed.connect(self._on_failed)
        w.start()

    def _on_done(self, shots: list):
        self._shots = shots
        self._progress.setRange(0, 1)
        self._progress.setValue(1)

        if not shots:
            self._phase_lbl.setText("Terminé")
            self._status_lbl.setText("Aucun plan généré — le scénario est peut-être trop court.")
            self._btn_cancel.setText("Fermer")
            return

        # Build rows
        self._list_frame.setVisible(True)
        total_dur = 0.0
        for shot in shots:
            row = _ShotRow(shot)
            self._list_lay.addWidget(row)
            total_dur += float(shot.get("duration", 5))
        self._list_lay.addStretch()

        mins, secs = divmod(int(total_dur), 60)
        dur_str = f"{mins}m{secs:02d}s" if mins else f"{secs}s"
        count = len(shots)

        self._phase_lbl.setText(f"{count} plan{'s' if count > 1 else ''} générés")
        self._status_lbl.setText(
            f"{count} plan{'s' if count > 1 else ''} · durée totale {dur_str} · "
            "Confirmez pour importer dans le Storyboard."
        )
        self._summary_lbl.setText(
            f"✓  {count} plans · {dur_str} total"
        )
        self._summary_lbl.setVisible(True)
        self._btn_confirm.setVisible(True)
        self._btn_cancel.setText("Annuler")

    def _on_failed(self, err: str):
        self._progress.setRange(0, 1)
        self._progress.setValue(0)
        self._phase_lbl.setText("Erreur")
        self._status_lbl.setText(f"⚠ {err[:160]}")
        self._btn_cancel.setText("Fermer")

    # ── Actions ───────────────────────────────────────────────────────────────

    def _on_confirm(self):
        if not self._shots:
            self.accept()
            return
        self._btn_confirm.setEnabled(False)
        self._btn_confirm.setText("Enregistrement…")
        try:
            import core.storyboard as sb_api
            vid = sb_api.DEFAULT_VERSION_ID
            sb_api.clear_version_shots(vid)
            for shot in self._shots:
                shot["scenario_id"] = self._scenario_id
                shot["version_id"]  = vid
                sb_api.save_shot(shot)
        except Exception as e:
            self._status_lbl.setText(f"⚠ Erreur sauvegarde : {e}")
            self._btn_confirm.setEnabled(True)
            self._btn_confirm.setText("Importer dans le Storyboard")
            return
        self.accept()

    def _on_cancel(self):
        if self._worker and self._worker.isRunning():
            self._worker.terminate()
        self.reject()
