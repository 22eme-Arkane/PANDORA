"""Modal dialog — Mood storyboard : voir, naviguer, générer des variations."""

import os
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QScrollArea, QWidget, QProgressBar, QSizePolicy, QFrame, QTextEdit,
)
from PyQt6.QtCore import Qt, pyqtSignal, QTimer
from PyQt6.QtGui import QPixmap
from ui.styles import CP, PANDORA_STYLESHEET
import core.storyboard as sb_api


def _btn(text: str, accent: bool = False, danger: bool = False) -> QPushButton:
    b = QPushButton(text)
    b.setFixedHeight(36)
    b.setCursor(Qt.CursorShape.PointingHandCursor)
    if accent:
        b.setStyleSheet(
            f"QPushButton{{background:{CP['accent']};color:#07080f;"
            f"border:none;border-radius:8px;font-size:11px;font-weight:700;padding:0 14px;}}"
            f"QPushButton:hover{{background:#6eded6;}}"
            f"QPushButton:disabled{{background:{CP['bg3']};color:{CP['text_dim']};}}"
        )
    elif danger:
        b.setStyleSheet(
            f"QPushButton{{background:transparent;color:{CP['red']};"
            f"border:1px solid {CP['red']};border-radius:8px;"
            f"font-size:11px;font-weight:700;padding:0 14px;}}"
            f"QPushButton:hover{{background:rgba(255,79,106,0.12);}}"
        )
    else:
        b.setStyleSheet(
            f"QPushButton{{background:transparent;color:{CP['text_secondary']};"
            f"border:1px solid {CP['border']};border-radius:8px;"
            f"font-size:11px;font-weight:700;padding:0 14px;}}"
            f"QPushButton:hover{{background:{CP['bg3']};color:{CP['text_primary']};}}"
            f"QPushButton:disabled{{color:{CP['text_dim']};border-color:{CP['bg3']};}}"
        )
    return b


class MoodDialog(QDialog):
    apercu_changed = pyqtSignal(str, str)   # shot_id, active_image_path

    def __init__(self, parent, shot: dict):
        super().__init__(parent)
        self._shot        = shot
        self._paths: list[str] = []
        self._active_idx  = 0
        self._current_idx = 0
        self._worker      = None
        self._pulse_timer = QTimer(self)
        self._pulse_val   = 0
        self._pulse_dir   = 1

        n = shot.get("number", "?")
        title_text = (shot.get("scene_title") or "")[:60]
        self.setWindowTitle(f"Mood — Plan {n}")
        self.setStyleSheet(PANDORA_STYLESHEET + f"QDialog{{background:{CP['bg1']};}}")
        from ui.widgets import fit_dialog_to_screen
        fit_dialog_to_screen(self, 0.70, 0.92, 760, 580)
        self.setModal(True)

        self._load()
        self._build_ui(n, title_text)
        self._refresh()

        from core.i18n import retranslate_widget
        retranslate_widget(self)

    # ── Data ──────────────────────────────────────────────────────────────────

    def _load(self):
        data = sb_api.load_apercus(self._shot["id"])
        self._paths = [p for p in data.get("paths", []) if os.path.isfile(p)]
        self._active_idx = min(
            data.get("active_idx", 0), max(0, len(self._paths) - 1)
        )
        self._current_idx = self._active_idx

    # ── UI ────────────────────────────────────────────────────────────────────

    def _build_ui(self, plan_num, title_text: str):
        root = QVBoxLayout(self)
        root.setContentsMargins(20, 16, 20, 16)
        root.setSpacing(10)

        # ── Titre ─────────────────────────────────────────────────────────────
        hdr = QHBoxLayout()
        lbl_title = QLabel(
            f"Plan {plan_num}  ·  {title_text}" if title_text else f"Plan {plan_num}"
        )
        lbl_title.setStyleSheet(
            f"color:{CP['text_primary']};font-size:14px;font-weight:700;background:transparent;"
        )
        hdr.addWidget(lbl_title, 1)
        btn_close = _btn("Fermer")
        btn_close.clicked.connect(self.accept)
        hdr.addWidget(btn_close)
        root.addLayout(hdr)

        # ── Bandeau description (déroulant) ───────────────────────────────────
        desc_frame = QFrame()
        desc_frame.setStyleSheet(
            f"QFrame{{background:rgba(78,205,196,0.07);border:1px solid rgba(78,205,196,0.22);"
            f"border-radius:8px;}}"
        )
        desc_lay = QVBoxLayout(desc_frame)
        desc_lay.setContentsMargins(14, 8, 14, 8)
        desc_lay.setSpacing(4)

        desc_title = QPushButton("▶  Qu'est-ce qu'un Mood ?")
        desc_title.setCheckable(True)
        desc_title.setChecked(False)
        desc_title.setCursor(Qt.CursorShape.PointingHandCursor)
        desc_title.setStyleSheet(
            f"QPushButton{{color:{CP['accent']};font-size:11px;font-weight:700;"
            f"background:transparent;border:none;text-align:left;padding:0;}}"
            f"QPushButton:hover{{color:#6eded6;}}"
        )
        desc_lay.addWidget(desc_title)

        desc_body = QLabel(
            "Teste le prompt et l'ambiance du plan avant de lancer Seedance 2.0. "
            "L'image est générée à partir du prompt Seedance, de la valeur de plan, "
            "la focale, l'axe caméra, le mouvement, le lieu, l'heure et le style visuel du film. "
            "Ce n'est pas une pré-visualisation fidèle — c'est un outil pour valider "
            "l'atmosphère, l'éclairage et le prompt. Une fois validée, l'image active "
            "pourra être injectée comme référence dans Seedance 2.0."
        )
        desc_body.setWordWrap(True)
        desc_body.setStyleSheet(
            f"color:{CP['text_secondary']};font-size:10px;line-height:1.5;"
            f"background:transparent;border:none;"
        )
        desc_body.setVisible(False)
        desc_lay.addWidget(desc_body)

        def _toggle_desc(checked: bool):
            desc_body.setVisible(checked)
            desc_title.setText(
                "▼  Qu'est-ce qu'un Mood ?" if checked else "▶  Qu'est-ce qu'un Mood ?"
            )
        desc_title.toggled.connect(_toggle_desc)
        root.addWidget(desc_frame)

        # ── Zone prompt modifiable ─────────────────────────────────────────────
        prompt_hdr = QHBoxLayout()
        prompt_lbl = QLabel("Prompt")
        prompt_lbl.setStyleSheet(
            f"color:{CP['text_secondary']};font-size:11px;font-weight:600;"
            f"background:transparent;"
        )
        prompt_hdr.addWidget(prompt_lbl)
        prompt_hdr.addStretch()
        btn_reset_prompt = QPushButton("↺  Réinitialiser")
        btn_reset_prompt.setFixedHeight(24)
        btn_reset_prompt.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_reset_prompt.setToolTip("Recharger le prompt depuis les données du plan")
        btn_reset_prompt.setStyleSheet(
            f"QPushButton{{background:transparent;color:{CP['text_dim']};"
            f"border:1px solid {CP['border']};border-radius:5px;"
            f"font-size:10px;padding:0 8px;}}"
            f"QPushButton:hover{{color:{CP['text_primary']};border-color:{CP['border_bright']};}}"
        )
        prompt_hdr.addWidget(btn_reset_prompt)
        root.addLayout(prompt_hdr)

        from api.apercu import build_mood_prompt
        import core.style as _style_mod
        _auto_prompt = build_mood_prompt(self._shot, _style_mod.get_image_suffix() or "")
        self._prompt_edit = QTextEdit()
        self._prompt_edit.setPlainText(_auto_prompt)
        self._prompt_edit.setFixedHeight(82)
        self._prompt_edit.setStyleSheet(
            f"QTextEdit{{background:{CP['bg3']};border:1px solid {CP['border']};"
            f"border-radius:6px;color:{CP['text_primary']};font-size:11px;padding:6px;}}"
            f"QTextEdit:focus{{border-color:{CP['accent']};}}"
        )
        btn_reset_prompt.clicked.connect(
            lambda: self._prompt_edit.setPlainText(
                build_mood_prompt(self._shot, _style_mod.get_image_suffix() or "")
            )
        )
        root.addWidget(self._prompt_edit)

        # ── Image principale ───────────────────────────────────────────────────
        self._img_lbl = QLabel()
        self._img_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._img_lbl.setMinimumSize(760, 427)
        self._img_lbl.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self._img_lbl.setStyleSheet(
            f"background:{CP['bg0']};border:1px solid {CP['border']};border-radius:8px;"
        )
        root.addWidget(self._img_lbl, 1)

        # ── Bande de miniatures ────────────────────────────────────────────────
        self._thumb_scroll = QScrollArea()
        self._thumb_scroll.setFixedHeight(72)
        self._thumb_scroll.setWidgetResizable(True)
        self._thumb_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self._thumb_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._thumb_scroll.setStyleSheet(
            "background:transparent;border:none;"
            "QScrollBar:horizontal{height:4px;}"
        )
        self._thumb_inner = QWidget()
        self._thumb_inner.setStyleSheet("background:transparent;")
        self._thumb_lay = QHBoxLayout(self._thumb_inner)
        self._thumb_lay.setContentsMargins(0, 4, 0, 4)
        self._thumb_lay.setSpacing(6)
        self._thumb_lay.addStretch()
        self._thumb_scroll.setWidget(self._thumb_inner)
        root.addWidget(self._thumb_scroll)

        # ── Navigation ────────────────────────────────────────────────────────
        nav = QHBoxLayout()
        self._btn_prev = _btn("◀")
        self._btn_prev.setFixedWidth(48)
        self._btn_prev.clicked.connect(lambda: self._nav(-1))
        nav.addWidget(self._btn_prev)

        self._count_lbl = QLabel("— / —")
        self._count_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._count_lbl.setStyleSheet(
            f"color:{CP['text_dim']};font-size:11px;background:transparent;"
        )
        nav.addWidget(self._count_lbl, 1)

        self._btn_next = _btn("▶")
        self._btn_next.setFixedWidth(48)
        self._btn_next.clicked.connect(lambda: self._nav(1))
        nav.addWidget(self._btn_next)
        root.addLayout(nav)

        # ── Boutons d'action ──────────────────────────────────────────────────
        acts = QHBoxLayout()
        self._btn_activate = _btn("✓  Activer cette image", accent=True)
        self._btn_activate.clicked.connect(self._activate)
        acts.addWidget(self._btn_activate)

        self._btn_delete = _btn("🗑  Supprimer", danger=True)
        self._btn_delete.clicked.connect(self._delete)
        acts.addWidget(self._btn_delete)

        acts.addStretch()
        self._btn_generate = _btn("✦  Générer une variation")
        self._btn_generate.clicked.connect(self._generate)
        acts.addWidget(self._btn_generate)
        root.addLayout(acts)

        # ── Barre de progression ───────────────────────────────────────────────
        progress_wrap = QWidget()
        progress_wrap.setFixedHeight(28)
        progress_wrap.setStyleSheet("background:transparent;")
        pw_lay = QVBoxLayout(progress_wrap)
        pw_lay.setContentsMargins(0, 4, 0, 0)
        pw_lay.setSpacing(3)

        self._progress = QProgressBar()
        self._progress.setFixedHeight(8)
        self._progress.setTextVisible(False)
        self._progress.setRange(0, 100)
        self._progress.setValue(0)
        self._progress.setStyleSheet(
            f"QProgressBar{{background:{CP['bg3']};border:none;border-radius:4px;}}"
            f"QProgressBar::chunk{{background:qlineargradient(x1:0,y1:0,x2:1,y2:0,"
            f"stop:0 {CP['accent']},stop:1 #6eded6);border-radius:4px;}}"
        )
        self._progress.hide()
        pw_lay.addWidget(self._progress)

        self._status_lbl = QLabel("")
        self._status_lbl.setStyleSheet(
            f"color:{CP['text_dim']};font-size:10px;background:transparent;"
        )
        self._status_lbl.hide()
        pw_lay.addWidget(self._status_lbl)

        root.addWidget(progress_wrap)

        # Timer pour animation de la barre (pulsation 0→80→0)
        self._pulse_timer.timeout.connect(self._pulse_step)

    # ── Pulsation de la barre ─────────────────────────────────────────────────

    def _pulse_step(self):
        self._pulse_val += self._pulse_dir * 3
        if self._pulse_val >= 80:
            self._pulse_val = 80
            self._pulse_dir = -1
        elif self._pulse_val <= 0:
            self._pulse_val = 0
            self._pulse_dir = 1
        self._progress.setValue(self._pulse_val)

    def _start_loading(self, msg: str = ""):
        self._progress.show()
        self._status_lbl.show()
        self._status_lbl.setText(msg)
        self._pulse_val = 0
        self._pulse_dir = 1
        self._pulse_timer.start(25)

    def _stop_loading(self):
        self._pulse_timer.stop()
        self._progress.hide()
        self._status_lbl.hide()
        self._progress.setValue(0)

    # ── Affichage ─────────────────────────────────────────────────────────────

    def _refresh(self):
        has      = bool(self._paths)
        is_active = has and self._current_idx == self._active_idx

        # Image principale
        if has and 0 <= self._current_idx < len(self._paths):
            pix = QPixmap(self._paths[self._current_idx])
            if not pix.isNull():
                scaled = pix.scaled(
                    self._img_lbl.size(),
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
                self._img_lbl.setPixmap(scaled)
                self._img_lbl.setText("")
            else:
                self._img_lbl.clear()
                self._img_lbl.setText("Image introuvable")
        else:
            self._img_lbl.clear()
            self._img_lbl.setText(
                "Aucun Mood disponible\n\nCliquez sur  ✦  Générer une variation  pour créer le premier"
            )
            self._img_lbl.setStyleSheet(
                f"background:{CP['bg0']};border:1px solid {CP['border']};border-radius:8px;"
                f"color:{CP['text_dim']};font-size:12px;"
            )

        # Navigation
        total = len(self._paths)
        self._count_lbl.setText(f"{self._current_idx + 1} / {total}" if has else "— / —")
        self._btn_prev.setEnabled(has and self._current_idx > 0)
        self._btn_next.setEnabled(has and self._current_idx < total - 1)
        self._btn_activate.setEnabled(has and not is_active)
        self._btn_activate.setText("✓  Image active" if is_active else "✓  Activer cette image")
        self._btn_delete.setEnabled(has)

        # Miniatures (rebuild)
        while self._thumb_lay.count() > 1:
            item = self._thumb_lay.takeAt(0)
            if item and item.widget():
                item.widget().deleteLater()
        for i, path in enumerate(self._paths):
            thumb = QLabel()
            thumb.setFixedSize(106, 62)
            thumb.setCursor(Qt.CursorShape.PointingHandCursor)
            pix = QPixmap(path).scaled(
                106, 62,
                Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                Qt.TransformationMode.SmoothTransformation,
            )
            pix = pix.copy((pix.width() - 106) // 2, (pix.height() - 62) // 2, 106, 62)
            thumb.setPixmap(pix)
            border = CP["accent"] if i == self._active_idx else (
                CP["border_bright"] if i == self._current_idx else CP["border"]
            )
            thumb.setStyleSheet(f"border:2px solid {border};border-radius:4px;")

            def _make_jump(idx):
                def _handler(_e):
                    self._current_idx = idx
                    self._refresh()
                return _handler
            thumb.mousePressEvent = _make_jump(i)
            self._thumb_lay.insertWidget(i, thumb)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self._paths and 0 <= self._current_idx < len(self._paths):
            pix = QPixmap(self._paths[self._current_idx])
            if not pix.isNull():
                scaled = pix.scaled(
                    self._img_lbl.size(),
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
                self._img_lbl.setPixmap(scaled)

    # ── Actions ───────────────────────────────────────────────────────────────

    def _nav(self, delta: int):
        new_idx = self._current_idx + delta
        if 0 <= new_idx < len(self._paths):
            self._current_idx = new_idx
            self._refresh()

    def _activate(self):
        if not self._paths:
            return
        self._active_idx = self._current_idx
        sb_api.save_apercus(self._shot["id"], self._paths, self._active_idx)
        self.apercu_changed.emit(self._shot["id"], self._paths[self._active_idx])
        self._refresh()

    def _delete(self):
        if not self._paths or not (0 <= self._current_idx < len(self._paths)):
            return
        path = self._paths[self._current_idx]
        # Supprimer le fichier sur disque
        try:
            if os.path.isfile(path):
                os.remove(path)
        except OSError:
            pass
        self._paths.pop(self._current_idx)
        # Recalculer l'index actif
        if self._paths:
            self._active_idx = min(self._active_idx, len(self._paths) - 1)
            self._current_idx = min(self._current_idx, len(self._paths) - 1)
        else:
            self._active_idx  = 0
            self._current_idx = 0
        sb_api.save_apercus(self._shot["id"], self._paths, self._active_idx)
        active_path = self._paths[self._active_idx] if self._paths else ""
        self.apercu_changed.emit(self._shot["id"], active_path)
        self._refresh()

    def _disconnect_worker(self):
        if self._worker is None:
            return
        try:
            self._worker.progress.disconnect(self._on_progress)
            self._worker.finished.disconnect(self._on_generated)
            self._worker.failed.disconnect(self._on_failed)
        except Exception:
            pass

    def accept(self):
        self._disconnect_worker()
        super().accept()

    def reject(self):
        self._disconnect_worker()
        super().reject()

    def _generate(self):
        from api.apercu import MoodGenerationWorker
        apercu_dir  = sb_api.get_apercu_dir(self._shot["id"])
        custom_prompt = self._prompt_edit.toPlainText().strip()
        self._disconnect_worker()
        self._worker = MoodGenerationWorker(self._shot, apercu_dir,
                                            custom_prompt=custom_prompt)
        self._worker.progress.connect(self._on_progress)
        self._worker.finished.connect(self._on_generated)
        self._worker.failed.connect(self._on_failed)
        self._btn_generate.setEnabled(False)
        self._btn_activate.setEnabled(False)
        self._start_loading("Génération du Mood…")
        self._worker.start()

    def _on_progress(self, msg: str):
        self._status_lbl.setText(msg)

    def _on_generated(self, path: str):
        self._stop_loading()
        self._btn_generate.setEnabled(True)
        if path and os.path.isfile(path):
            self._paths.append(path)
            self._current_idx = len(self._paths) - 1
            sb_api.save_apercus(self._shot["id"], self._paths, self._active_idx)
        self._refresh()

    def _on_failed(self, error: str):
        self._stop_loading()
        self._status_lbl.setText(f"Erreur : {error[:120]}")
        self._status_lbl.show()
        self._btn_generate.setEnabled(True)
        self._btn_activate.setEnabled(bool(self._paths) and self._current_idx != self._active_idx)
