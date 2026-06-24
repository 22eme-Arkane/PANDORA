"""
Dialog de synchronisation Storyboard ↔ Casting / Décors / Accessoires.

Affiche la progression en temps réel, liste les plans modifiés,
puis sauvegarde sur confirmation.
"""
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QScrollArea, QWidget, QFrame, QProgressBar, QCheckBox,
)
from PyQt6.QtCore import Qt
from core.i18n import translate
from core.worker import abandon_thread
from ui.styles import CP


# ── Dialog de confirmation avant synchronisation ───────────────────────────────

class StoryboardSyncConfirmDialog(QDialog):
    """
    Fenêtre de synchronisation : l'utilisateur choisit les opérations à lancer.

    Options (sélection multiple) :
      • reassign        — réassigner les noms (personnages / décors / accessoires)
      • rewrite_prompts — réécrire les prompts incohérents (IA)
      • resync_decors   — re-synchroniser les décors
      • rewrite_scenario— réécrire le scénario depuis le storyboard (IA, nouvelle version)

    Après exec() == Accepted, lire selected_options() → dict[str, bool].
    """

    # (clé, libellé, description, coché par défaut, badge IA)
    _OPTIONS = [
        ("reassign",
         "Réassigner les noms",
         "Détecte les personnages, décors et accessoires renommés (accents, articles, "
         "casse…) et met à jour les assignations de chaque plan.",
         True, False),
        ("rewrite_prompts",
         "Réécrire les prompts",
         "Vérifie chaque prompt et réécrit uniquement ceux qui ne reflètent plus les "
         "fiches actuelles (traits, costumes, lieux…).",
         True, True),
        ("sync_staging",
         "Synchroniser la mise en scène",
         "Ajoute au prompt une section MISE EN SCÈNE : placement des personnages "
         "(in/off, assis/debout…) et de la caméra, d'après le plan vu de dessus.",
         False, False),
        ("sync_lighting",
         "Synchroniser le plan de feu",
         "Ajoute au prompt une section PLAN DE FEU : description de la lumière et de "
         "l'ambiance d'après les projecteurs placés.",
         False, False),
        ("resync_decors",
         "Re-synchroniser les décors",
         "Met à jour le nom des décors renommés et ré-assigne les plans sans décor "
         "d'après le titre et le prompt.",
         False, False),
        ("sync_casting",
         "Synchroniser le casting",
         "Met à jour les noms de personnages renommés et ré-assigne aux plans les "
         "personnages cités dans le titre ou le prompt.",
         False, False),
        ("sync_accessories",
         "Synchroniser les accessoires",
         "Met à jour les accessoires renommés et ré-assigne aux plans les accessoires "
         "cités dans le titre ou le prompt.",
         False, False),
        ("sync_vehicles",
         "Synchroniser les véhicules",
         "Met à jour les véhicules renommés et ré-assigne aux plans les véhicules "
         "cités dans le titre ou le prompt.",
         False, False),
        ("rewrite_scenario",
         "Réécrire le scénario depuis le storyboard",
         "Reconstitue un scénario littéraire à partir des plans, visible dans l'onglet "
         "Scénario. Le scénario actuel n'est jamais écrasé (fiche séparée si besoin).",
         False, True),
    ]

    def __init__(self, n_shots: int, parent=None):
        super().__init__(parent)
        self._checks: dict[str, QCheckBox] = {}

        self.setWindowTitle("Synchronisation — Storyboard")
        self.setMinimumWidth(540)
        self.setMaximumWidth(600)
        self.setStyleSheet(f"background:{CP['bg1']};")

        root = QVBoxLayout(self)
        root.setContentsMargins(28, 24, 28, 24)
        root.setSpacing(18)

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
        sub = QLabel(f"{n_shots} plan(s) — choisissez les opérations à lancer")
        sub.setStyleSheet(
            f"color:{CP['text_dim']};font-size:10px;background:transparent;"
        )
        title_col.addWidget(sub)
        hdr.addLayout(title_col, 1)
        root.addLayout(hdr)

        sep = QFrame()
        sep.setFixedHeight(1)
        sep.setStyleSheet(f"background:{CP['border']};")
        root.addWidget(sep)

        # ── Options (cases à cocher) — zone scrollable bornée (liste qui grandit) ─
        _opts_scroll = QScrollArea()
        _opts_scroll.setWidgetResizable(True)
        _opts_scroll.setStyleSheet("QScrollArea{background:transparent;border:none;}")
        _opts_inner = QWidget()
        _opts_inner.setStyleSheet("background:transparent;")
        _opts_lay = QVBoxLayout(_opts_inner)
        _opts_lay.setContentsMargins(0, 0, 2, 0)
        _opts_lay.setSpacing(10)
        for key, label, detail, default_on, is_ai in self._OPTIONS:
            card = QFrame()
            card.setStyleSheet(
                f"background:{CP['bg2']};border-radius:10px;border:1px solid {CP['border']};"
            )
            card_lay = QVBoxLayout(card)
            card_lay.setContentsMargins(14, 12, 14, 12)
            card_lay.setSpacing(4)

            top = QHBoxLayout()
            top.setSpacing(8)
            chk = QCheckBox(label)
            chk.setChecked(default_on)
            chk.setStyleSheet(
                f"QCheckBox{{color:{CP['text_primary']};font-size:13px;font-weight:700;"
                f"background:transparent;spacing:8px;}}"
                f"QCheckBox::indicator{{width:17px;height:17px;border-radius:4px;"
                f"border:1px solid {CP['border']};background:{CP['bg3']};}}"
                f"QCheckBox::indicator:checked{{background:{CP.get('accent2','#7c6bff')};"
                f"border:1px solid {CP.get('accent2','#7c6bff')};}}"
            )
            chk.stateChanged.connect(self._update_launch)
            self._checks[key] = chk
            top.addWidget(chk)
            top.addStretch()
            if is_ai:
                ai_badge = QLabel("IA")
                ai_badge.setStyleSheet(
                    f"color:{CP.get('accent','#4ecdc4')};background:transparent;"
                    f"border:1px solid {CP.get('accent','#4ecdc4')};border-radius:4px;"
                    f"font-size:8px;font-weight:700;padding:1px 6px;"
                )
                top.addWidget(ai_badge)
            card_lay.addLayout(top)

            d_lbl = QLabel(detail)
            d_lbl.setStyleSheet(
                f"color:{CP['text_secondary']};font-size:10px;"
                f"background:transparent;padding-left:25px;"
            )
            d_lbl.setWordWrap(True)
            card_lay.addWidget(d_lbl)

            _opts_lay.addWidget(card)

        _opts_lay.addStretch()
        _opts_scroll.setWidget(_opts_inner)
        _opts_scroll.setMinimumHeight(300)
        _opts_scroll.setMaximumHeight(460)
        root.addWidget(_opts_scroll, 1)

        # ── Note finale ──────────────────────────────────────────────────────
        note = QLabel(
            "✓  Une prévisualisation des modifications s'affiche avant toute écriture."
        )
        note.setStyleSheet(
            f"color:{CP.get('accent', '#4ecdc4')};font-size:10px;"
            f"font-style:italic;background:transparent;"
        )
        note.setWordWrap(True)
        root.addWidget(note)

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

        self._btn_ok = QPushButton("Lancer la synchronisation")
        self._btn_ok.setMinimumHeight(40)
        self._btn_ok.setMinimumWidth(200)
        self._btn_ok.setStyleSheet(
            f"QPushButton{{background:{CP.get('accent2', '#7c6bff')};color:#fff;"
            f"border:none;border-radius:8px;"
            f"font-size:13px;font-weight:700;padding:0 24px;}}"
            f"QPushButton:hover{{background:#9a8aff;}}"
            f"QPushButton:disabled{{background:{CP['bg3']};color:{CP['text_dim']};"
            f"border:1px solid {CP['border']};}}"
        )
        self._btn_ok.clicked.connect(self.accept)
        self._btn_ok.setDefault(True)
        foot.addWidget(self._btn_ok)

        root.addLayout(foot)
        self._update_launch()

    def _update_launch(self):
        any_on = any(c.isChecked() for c in self._checks.values())
        self._btn_ok.setEnabled(any_on)

    def selected_options(self) -> dict:
        return {key: chk.isChecked() for key, chk in self._checks.items()}


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
        dlg = StoryboardSyncDialog(shots, options, parent)
        dlg.exec()
        # shots (et éventuellement une nouvelle version de scénario) sauvegardés sur confirmation
    """

    def __init__(self, shots: list, options: dict | None = None, parent=None):
        super().__init__(parent)
        self._shots_in    = shots
        self._shots_out   = []
        self._worker      = None
        self._n_changed   = 0
        self._options     = options or {
            "reassign": True, "rewrite_prompts": True,
            "resync_decors": True, "rewrite_scenario": False,
            "sync_staging": False, "sync_lighting": False,
            "sync_casting": False, "sync_accessories": False, "sync_vehicles": False,
        }
        self._scenario_text   = ""   # texte du scénario reconstruit (si demandé)
        self._scenario_worker = None

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
        # Y a-t-il au moins une opération qui touche les plans ?
        shot_ops = any(self._options.get(k) for k in
                       ("reassign", "rewrite_prompts", "resync_decors",
                        "sync_staging", "sync_lighting",
                        "sync_casting", "sync_accessories", "sync_vehicles"))
        if shot_ops:
            from api.screenplay import SyncStoryboardWorker
            w = SyncStoryboardWorker(self._shots_in, self._options)
            self._worker = w
            w.progress.connect(self._on_progress)
            w.finished.connect(self._on_shots_done)
            w.failed.connect(self._on_failed)
            w.start()
        else:
            # Uniquement la réécriture du scénario : on saute la phase plans.
            self._shots_out = [dict(s) for s in self._shots_in]
            self._start_scenario()

    def _on_progress(self, pct: int, msg: str):
        self._progress.setRange(0, 100)
        self._progress.setValue(pct)
        self._status_lbl.setText(translate(msg))
        self._phase_lbl.setText(translate(msg))

    def _on_shots_done(self, shots: list):
        self._shots_out = shots
        if self._options.get("rewrite_scenario"):
            self._start_scenario()
        else:
            self._finalize()

    # ── Réécriture du scénario (optionnelle) ─────────────────────────────────────

    def _start_scenario(self):
        from api.screenplay import RewriteScreenplayFromStoryboardWorker
        self._progress.setRange(0, 100)
        self._progress.setValue(0)
        self._phase_lbl.setText("Réécriture du scénario…")
        self._status_lbl.setText("Reconstruction du scénario depuis le storyboard…")
        w = RewriteScreenplayFromStoryboardWorker(self._shots_in)
        self._scenario_worker = w
        w.progress.connect(self._on_progress)
        w.finished.connect(self._on_scenario_done)
        w.failed.connect(self._on_failed)
        w.start()

    def _on_scenario_done(self, text: str):
        self._scenario_text = text or ""
        self._finalize()

    # ── Finalisation : preview + résumé ──────────────────────────────────────────

    def _finalize(self):
        shots = self._shots_out
        self._progress.setRange(0, 1)
        self._progress.setValue(1)

        changed   = [s for s in shots if s.get("_reassigned") or s.get("_prompt_changed")]
        unchanged = [s for s in shots if not s.get("_reassigned") and not s.get("_prompt_changed")]
        self._n_changed = len(changed)

        self._list_frame.setVisible(True)

        shot_ops = any(self._options.get(k) for k in
                       ("reassign", "rewrite_prompts", "resync_decors",
                        "sync_staging", "sync_lighting",
                        "sync_casting", "sync_accessories", "sync_vehicles"))

        # Changed first, then unchanged — uniquement si une opération sur les plans
        # a réellement tourné (sinon mode « scénario seul »).
        if shot_ops:
            for shot in changed + unchanged:
                row = _ShotSyncRow(shot)
                self._list_lay.addWidget(row)

        # ── Ligne scénario reconstruit (si demandé) ──────────────────────────
        if self._scenario_text:
            self._list_lay.addWidget(self._build_scenario_row())

        self._list_lay.addStretch()

        total = len(shots)
        n_reassign = sum(1 for s in shots if s.get("_reassigned"))
        n_prompt   = sum(1 for s in shots if s.get("_prompt_changed"))
        has_scenario = bool(self._scenario_text)

        if self._n_changed or has_scenario:
            bits = []
            if self._n_changed:
                bits.append(f"{self._n_changed} plan(s)")
            if has_scenario:
                bits.append("scénario réécrit")
            self._phase_lbl.setText(" · ".join(bits) + " à appliquer")
            sm = (
                f"{n_prompt} prompt(s) réécrit(s) · {n_reassign} ré-assignation(s) sur {total} plans"
                if self._n_changed else f"{total} plan(s) analysé(s)"
            )
            if has_scenario:
                sm += f" · scénario {len(self._scenario_text)} caractères → nouvelle version"
            self._status_lbl.setText(sm)
            summ = f"✓  {self._n_changed}/{total} plans modifiés · {n_prompt} prompts · {n_reassign} assignations"
            if has_scenario:
                summ += " · + scénario (nouvelle version)"
            self._summary_lbl.setText(summ)
            btn_txt = "Appliquer"
            if self._n_changed and has_scenario:
                btn_txt = f"Appliquer ({self._n_changed} plan(s) + scénario)"
            elif self._n_changed:
                btn_txt = f"Appliquer ({self._n_changed} plan(s))"
            elif has_scenario:
                btn_txt = "Enregistrer le scénario"
            self._btn_confirm.setText(btn_txt)
            self._btn_confirm.setVisible(True)
        else:
            self._phase_lbl.setText("Tout est synchronisé")
            self._status_lbl.setText(
                f"Aucune mise à jour nécessaire — {total} plan(s) analysé(s), tout est cohérent."
            )
            self._summary_lbl.setText(f"✓  {total} plans analysés — storyboard déjà synchronisé")
            self._btn_cancel.setText("Fermer")

        self._summary_lbl.setVisible(True)

    def _build_scenario_row(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(10, 8, 10, 8)
        lay.setSpacing(4)

        top = QHBoxLayout()
        top.setSpacing(8)
        icon_lbl = QLabel("✎")
        icon_lbl.setStyleSheet(
            f"color:{CP.get('accent2', '#7c6bff')};font-size:13px;font-weight:700;background:transparent;"
        )
        icon_lbl.setFixedWidth(18)
        top.addWidget(icon_lbl)
        tag = QLabel("Scénario")
        tag.setStyleSheet(
            f"color:#07080f;background:{CP.get('accent2', '#7c6bff')};"
            f"border-radius:3px;font-size:8px;font-weight:700;padding:1px 6px;"
        )
        tag.setFixedHeight(17)
        top.addWidget(tag)
        title_lbl = QLabel("Scénario reconstruit depuis le storyboard")
        title_lbl.setStyleSheet(
            f"color:{CP['text_primary']};font-size:11px;font-weight:600;background:transparent;"
        )
        top.addWidget(title_lbl, 1)
        # Bouton « Copier le texte » : copie le scénario reconstruit COMPLET dans le
        # presse-papier — vérification + secours (coller dans l'éditeur Scénario).
        copy_btn = QPushButton("📋  " + translate("Copier le texte"))
        copy_btn.setFixedHeight(24)
        copy_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        copy_btn.setStyleSheet(
            f"QPushButton{{background:transparent;color:{CP.get('accent2', '#7c6bff')};"
            f"border:1px solid {CP.get('accent2', '#7c6bff')};border-radius:5px;"
            f"font-size:9px;font-weight:700;padding:0 10px;}}"
            f"QPushButton:hover{{background:rgba(124,107,255,0.14);}}")

        def _copy_scenario():
            from PyQt6.QtGui import QGuiApplication
            txt = self._scenario_text or ""
            QGuiApplication.clipboard().setText(txt)
            copy_btn.setText("✓  " + translate("Copié") + f" ({len(txt)} car.)")
        copy_btn.clicked.connect(_copy_scenario)
        top.addWidget(copy_btn)

        new_lbl = QLabel("nouvelle version")
        new_lbl.setStyleSheet(f"color:{CP['text_dim']};font-size:9px;background:transparent;")
        top.addWidget(new_lbl)
        lay.addLayout(top)

        preview = self._scenario_text.strip().replace("\n", " ")
        ex = QLabel(f"{preview[:160]}{'…' if len(preview) > 160 else ''}")
        ex.setStyleSheet(
            f"color:{CP['text_dim']};font-size:8px;font-family:'Consolas',monospace;"
            f"background:transparent;padding-left:26px;"
        )
        ex.setWordWrap(True)
        lay.addWidget(ex)
        return w

    def _on_failed(self, err: str):
        self._progress.setRange(0, 1)
        self._progress.setValue(0)
        self._phase_lbl.setText("Erreur")
        self._status_lbl.setText(f"⚠ {err[:180]}")
        self._btn_cancel.setText("Fermer")

    # ── Actions ────────────────────────────────────────────────────────────────

    def _on_confirm(self):
        from PyQt6.QtWidgets import QMessageBox
        if not self._shots_out and not self._scenario_text:
            self.accept()
            return
        self._btn_confirm.setEnabled(False)
        self._btn_confirm.setText("Sauvegarde…")
        saved = None
        try:
            import core.storyboard as sb_api
            for shot in self._shots_out:
                if shot.get("_reassigned") or shot.get("_prompt_changed"):
                    clean = {k: v for k, v in shot.items() if not k.startswith("_")}
                    sb_api.save_shot(clean)
            if self._scenario_text:
                saved = self._save_scenario_version(self._scenario_text)
        except Exception as e:
            # Erreur VISIBLE (modale) — sinon l'utilisateur croit que « ça ne marche pas »
            # sans savoir pourquoi.
            QMessageBox.critical(
                self, translate("Erreur d'enregistrement"),
                translate("Le scénario n'a pas pu être enregistré :") + f"\n\n{e}")
            self._status_lbl.setText(f"⚠ Erreur sauvegarde : {e}")
            self._btn_confirm.setEnabled(True)
            self._btn_confirm.setText("Réessayer")
            return
        # Confirmation VISIBLE quand un scénario a été enregistré → l'utilisateur sait
        # que ça a marché et où regarder.
        if self._scenario_text and saved is not None:
            title = (saved.get("title") or "Scénario").strip()
            QMessageBox.information(
                self, translate("Scénario enregistré"),
                "✓ " + translate("Scénario reconstruit enregistré")
                + f" ({len(self._scenario_text)} " + translate("caractères") + ")\n"
                + translate("sous") + f" « {title} ».\n\n"
                + translate("Ouvre l'onglet Scénario pour le voir."))
        self.accept()

    def _save_scenario_version(self, text: str) -> dict:
        """Enregistre le scénario reconstruit depuis le storyboard et renvoie la fiche
        enregistrée. Le résultat est TOUJOURS une fiche scénario VISIBLE dans l'onglet
        Scénario (jamais enfouie dans une version cachée).

        - Aucun scénario, ou scénario courant VIDE → le texte devient son contenu
          courant (s'affiche directement dans l'éditeur).
        - Scénario courant DÉJÀ rempli → on ne l'écrase pas : on enregistre une fiche
          SÉPARÉE « Scénario (reconstruit du storyboard) », visible comme sa propre
          carte. Robuste : la numérotation de version ne peut pas lever d'exception."""
        from datetime import datetime
        import core.scenario as scenario_api

        def _with_version(sc: dict) -> dict:
            sc = dict(sc)
            versions = list(sc.get("versions", []))
            try:
                num = int(versions[-1].get("num", 0)) + 1 if versions else 1
            except (TypeError, ValueError, AttributeError):
                num = len(versions) + 1
            versions.append({
                "num":      num,
                "name":     "Reconstruit depuis le storyboard",
                "content":  text,
                "saved_at": datetime.now().isoformat(timespec="seconds"),
            })
            sc["versions"] = versions
            sc["raw_content"] = text
            sc["formatted_content"] = text
            return sc

        scenarios = scenario_api.list_scenarios()
        current = scenarios[0] if scenarios else None
        has_content = bool(current and
            (current.get("formatted_content") or current.get("raw_content") or "").strip())

        if not has_content:
            target = _with_version(current or {})
            if not target.get("title"):
                target["title"] = "Scénario"
            return scenario_api.save_scenario(target)

        # Scénario rempli existant → fiche séparée « reconstruit » (jamais écraser).
        recon = next((s for s in scenarios
                      if (s.get("title") or "").startswith("Scénario (reconstruit")), None)
        if recon:
            return scenario_api.save_scenario(_with_version(recon))
        new_sc = _with_version({"title": "Scénario (reconstruit du storyboard)"})
        return scenario_api.save_scenario(new_sc)

    def _on_cancel(self):
        for w in (self._worker, self._scenario_worker):
            if w and w.isRunning():
                abandon_thread(w)
        self.reject()
