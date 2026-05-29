import os
from datetime import datetime
from PyQt6.QtWidgets import (
    QScrollArea, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QPushButton, QLabel, QFileDialog, QMessageBox, QFrame,
    QTextEdit, QCheckBox, QSpinBox,
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QPixmap
from ui.styles import C
from ui.widgets import section_label, combo, toggle_row, prompt_block, ProgressBlock, HelpBlock, show_api_error
from core.history import save_to_history
from core.config import get_output_dir
from core.worker import GenerationWorker
from api.enhance import EnhanceWorker
from davinci.bridge import resolve
from davinci.timeline import get_selected_clip, get_clip_info
from davinci.importer import import_result
from ui.tab_t2v import _DaVinciBar, _CreativeControlPanel


# ── Bouton direction (radio-style) ────────────────────────────────────────────

class DirectionBtn(QPushButton):
    def __init__(self, icon: str, label: str, value: str):
        super().__init__(f"{icon}\n{label}")
        self.value = value
        self._active = False
        self._apply_style()

    def set_active(self, active: bool):
        self._active = active
        self._apply_style()

    def _apply_style(self):
        if self._active:
            self.setStyleSheet(f"""
                QPushButton{{
                    background:rgba(124,107,255,0.18);color:{C['accent']};
                    border:2px solid {C['accent']};border-radius:8px;
                    font-size:11px;font-weight:700;padding:10px 8px;
                    line-height:1.6;
                }}
            """)
        else:
            self.setStyleSheet(f"""
                QPushButton{{
                    background:{C['bg2']};color:{C['text_secondary']};
                    border:1px solid {C['border']};border-radius:8px;
                    font-size:11px;font-weight:600;padding:10px 8px;
                    line-height:1.6;
                }}
                QPushButton:hover{{
                    border-color:{C['border_bright']};color:{C['text_primary']};
                }}
            """)


# ── Zone upload clip ──────────────────────────────────────────────────────────

class ClipUploadZone(QFrame):
    def __init__(self):
        super().__init__()
        self.path = None
        self._default_style = f"""
            QFrame{{background:{C['bg2']};border:1px dashed {C['border_bright']};border-radius:10px;}}
            QFrame:hover{{border-color:{C['accent_dim']};background:rgba(124,107,255,0.08);}}
        """
        self._active_style = f"""
            QFrame{{background:rgba(61,220,151,0.06);border:1px solid {C['green']}44;border-radius:10px;}}
        """
        self.setStyleSheet(self._default_style)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        lay = QVBoxLayout(self)
        lay.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lay.setContentsMargins(16, 20, 16, 20)
        lay.setSpacing(6)

        self._icon = QLabel("🎞")
        self._icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._icon.setStyleSheet("font-size:26px;border:none;background:transparent;")

        self._lbl = QLabel("Clique pour choisir un clip vidéo")
        self._lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._lbl.setStyleSheet(
            f"color:{C['text_secondary']};font-size:12px;border:none;background:transparent;"
        )

        self._sub = QLabel("MP4 · MOV · AVI · WEBM")
        self._sub.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._sub.setStyleSheet(
            f"color:{C['text_dim']};font-size:10px;font-family:'Consolas',monospace;"
            f"border:none;background:transparent;"
        )

        lay.addWidget(self._icon)
        lay.addWidget(self._lbl)
        lay.addWidget(self._sub)

    def mousePressEvent(self, event):
        self._pick()

    def _pick(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Choisir un clip", "",
            "Vidéos (*.mp4 *.mov *.avi *.webm *.mkv)"
        )
        if path:
            self._set_path(path)

    def set_from_davinci(self, file_path: str, name: str):
        self._set_path(file_path, label=f"◈ {name}")

    def _set_path(self, path: str, label: str | None = None):
        self.path = path
        display = label or os.path.basename(path)
        if len(display) > 34:
            display = display[:31] + "…"
        self._lbl.setText(f"✓  {display}")
        self._lbl.setStyleSheet(
            f"color:{C['green']};font-size:11px;font-weight:600;"
            f"border:none;background:transparent;"
        )
        self._sub.setText(path if len(path) <= 42 else "…" + path[-39:])
        self.setStyleSheet(self._active_style)
        self.setCursor(Qt.CursorShape.ArrowCursor)

    def clear(self):
        self.path = None
        self._lbl.setText("Clique pour choisir un clip vidéo")
        self._lbl.setStyleSheet(
            f"color:{C['text_secondary']};font-size:12px;border:none;background:transparent;"
        )
        self._sub.setText("MP4 · MOV · AVI · WEBM")
        self.setStyleSheet(self._default_style)
        self.setCursor(Qt.CursorShape.PointingHandCursor)


# ── Onglet Extension ──────────────────────────────────────────────────────────

class TabExtension(QScrollArea):
    generation_done = pyqtSignal(dict)

    def __init__(self):
        super().__init__()
        self.setWidgetResizable(True)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._worker = None
        self._enhance_worker = None
        self._direction = "after"
        self._clip_name = ""
        self._ref_images: list[str] = []

        container = QWidget()
        self.setWidget(container)
        lay = QVBoxLayout(container)
        lay.setContentsMargins(20, 20, 20, 20)
        lay.setSpacing(16)

        lay.addWidget(HelpBlock("Extension de clip — Prolonger ou modifier", [
            "▸ Prolongez un clip existant avant (étendre au début) ou après (étendre à la fin) sa durée originale.",
            "▸ Mode Nouveau rush : génère une nouvelle prise à partir du même clip source.",
            "▸ Importez un fichier vidéo local ou récupérez le clip actif depuis la timeline DaVinci Resolve.",
            "▸ Ajoutez un prompt pour guider la direction visuelle de la continuation.",
            "▸ La durée ajoutée s'additionne à la durée originale du clip source.",
        ], C))

        # ── Info block ────────────────────────────────────────────────────────
        info = QFrame()
        info.setStyleSheet(
            f"QFrame{{background:rgba(124,107,255,0.08);"
            f"border:1px solid rgba(124,107,255,0.25);border-radius:8px;}}"
        )
        info_lay = QVBoxLayout(info)
        info_lay.setContentsMargins(16, 12, 16, 12)
        info_lay.setSpacing(6)

        info_title = QLabel("◎  Modifier un clip existant")
        info_title.setStyleSheet(
            f"color:{C['accent']};font-size:12px;font-weight:700;background:transparent;"
        )
        info_lay.addWidget(info_title)

        info_desc = QLabel(
            "Cet onglet permet de travailler sur un clip vidéo existant selon 3 modes :\n"
            "  • Générer un début  —  génère un nouveau clip à placer avant le clip source\n"
            "  • Générer une suite  —  génère un nouveau clip à placer après le clip source\n"
            "  • Nouveau rush  —  génère une nouvelle prise à partir du même clip\n\n"
            "Pour utiliser un clip depuis DaVinci Resolve :\n"
            "  → Sélectionne le clip dans la timeline DaVinci\n"
            "  → Clique sur « Utiliser le clip DaVinci » ci-dessous\n"
            "  → Le nom du clip apparaît dans « Clip sélectionné »"
        )
        info_desc.setWordWrap(True)
        info_desc.setStyleSheet(
            f"color:{C['text_secondary']};font-size:10px;background:transparent;"
        )
        info_lay.addWidget(info_desc)
        lay.addWidget(info)

        # ── Clip source ───────────────────────────────────────────────────────
        lay.addWidget(section_label("Clip source"))
        self.clip_zone = ClipUploadZone()
        lay.addWidget(self.clip_zone)

        # Bouton DaVinci
        dvr_row = QHBoxLayout()
        self.btn_davinci = QPushButton("◈  Utiliser le clip DaVinci")
        self.btn_davinci.setFixedHeight(32)
        self.btn_davinci.setStyleSheet(f"""
            QPushButton{{
                background:rgba(124,107,255,0.10);color:{C['accent']};
                border:1px solid {C['accent_dim']};border-radius:6px;
                font-size:11px;font-weight:700;padding:0 14px;letter-spacing:0px;
            }}
            QPushButton:hover{{background:rgba(124,107,255,0.22);}}
            QPushButton:disabled{{color:{C['text_dim']};border-color:{C['border']};
            background:{C['bg2']};}}
        """)
        self.btn_davinci.clicked.connect(self._load_davinci_clip)
        dvr_row.addWidget(self.btn_davinci)
        dvr_row.addStretch()

        btn_clear = QPushButton("Effacer")
        btn_clear.setFixedHeight(32)
        btn_clear.setFixedWidth(70)
        btn_clear.setStyleSheet(f"""
            QPushButton{{background:transparent;color:{C['text_dim']};
            border:1px solid {C['border']};border-radius:6px;font-size:10px;font-weight:600;}}
            QPushButton:hover{{color:{C['text_secondary']};border-color:{C['border_bright']};}}
        """)
        btn_clear.clicked.connect(self._clear_clip)
        dvr_row.addWidget(btn_clear)
        lay.addLayout(dvr_row)

        # Clip sélectionné dans DaVinci
        lay.addWidget(section_label("Clip sélectionné"))
        self._davinci_clip_lbl = QLabel("Aucun clip sélectionné dans DaVinci Resolve")
        self._davinci_clip_lbl.setStyleSheet(
            f"color:{C['text_dim']};font-size:11px;"
            f"background:{C['bg2']};border:1px solid {C['border']};"
            f"border-radius:6px;padding:8px 14px;"
        )
        lay.addWidget(self._davinci_clip_lbl)

        # ── Direction ─────────────────────────────────────────────────────────
        lay.addWidget(section_label("Mode"))

        dir_row = QHBoxLayout()
        dir_row.setSpacing(10)
        self.btn_before   = DirectionBtn("◀", "Générer un début",  "before")
        self.btn_after    = DirectionBtn("▶", "Générer une suite", "after")
        self.btn_new_take = DirectionBtn("◎", "Nouveau rush",      "new_take")
        self.btn_before.clicked.connect(lambda:   self._set_direction("before"))
        self.btn_after.clicked.connect(lambda:    self._set_direction("after"))
        self.btn_new_take.clicked.connect(lambda: self._set_direction("new_take"))
        self._set_direction("new_take")
        dir_row.addWidget(self.btn_new_take)
        dir_row.addWidget(self.btn_before)
        dir_row.addWidget(self.btn_after)
        lay.addLayout(dir_row)

        # ── Images de référence ───────────────────────────────────────────────
        ref_hdr = QHBoxLayout()
        ref_hdr.setContentsMargins(0, 0, 0, 0)
        ref_hdr.addWidget(section_label("Images de référence (optionnel)"))
        _ref_hint = QLabel("Photo d'acteur, style, décor… · max 3")
        _ref_hint.setStyleSheet(
            f"color:{C['text_dim']};font-size:9px;font-style:italic;"
            f"background:transparent;border:none;"
        )
        ref_hdr.addStretch()
        ref_hdr.addWidget(_ref_hint)
        lay.addLayout(ref_hdr)

        self._ref_frame = QFrame()
        self._ref_frame.setFixedHeight(76)
        self._ref_frame.setStyleSheet(
            f"QFrame{{background:{C['bg2']};border:1px solid {C['border']};"
            f"border-radius:8px;}}"
        )
        self._ref_lay = QHBoxLayout(self._ref_frame)
        self._ref_lay.setContentsMargins(8, 8, 8, 8)
        self._ref_lay.setSpacing(8)
        self._refresh_ref_images()
        lay.addWidget(self._ref_frame)

        # ── Options ───────────────────────────────────────────────────────────
        grid = QGridLayout()
        grid.setSpacing(12)
        self.cb_dur = QSpinBox()
        self.cb_dur.setRange(1, 15)
        self.cb_dur.setValue(5)
        self.cb_dur.setSuffix("  s")
        self.cb_dur.setMinimumHeight(36)
        self.cb_dur.setStyleSheet(f"""
            QSpinBox{{background:{C['bg2']};color:{C['text_primary']};
            border:1px solid {C['border']};border-radius:6px;
            padding:4px 8px;font-size:12px;}}
            QSpinBox:focus{{border-color:{C['accent']};}}
            QSpinBox::up-button,QSpinBox::down-button{{
            width:22px;background:{C['bg3']};border:none;}}
            QSpinBox::up-button:hover,QSpinBox::down-button:hover{{background:{C['border_bright']};}}
        """)
        self.cb_res = combo([("1080p  (~$0.60/s)", "1080p"), ("720p  (~$0.30/s)", "720p"), ("480p  (~$0.16/s)", "480p")])

        for col_idx, lbl, widget in [
            (0, "Durée à ajouter", self.cb_dur),
            (1, "Résolution",      self.cb_res),
        ]:
            g = QWidget()
            l = QVBoxLayout(g)
            l.setContentsMargins(0, 0, 0, 0)
            l.setSpacing(6)
            l.addWidget(section_label(lbl))
            l.addWidget(widget)
            grid.addWidget(g, 0, col_idx)
        lay.addLayout(grid)

        # ── Contrôles créatifs ────────────────────────────────────────────────
        self._creative = _CreativeControlPanel()
        lay.addWidget(self._creative)

        # ── Prompt optionnel ──────────────────────────────────────────────────
        prompt_hdr = QHBoxLayout()
        prompt_hdr.setContentsMargins(0, 0, 0, 0)
        prompt_hdr.addWidget(section_label("Prompt (optionnel)"))
        self._new_take_note = QLabel(
            "Si vide → même prompt original · Si rempli → remplace le prompt"
        )
        self._new_take_note.setStyleSheet(
            f"color:{C['red']};font-size:9px;font-style:italic;"
            f"background:transparent;border:none;"
        )
        self._new_take_note.setVisible(False)
        prompt_hdr.addStretch()
        prompt_hdr.addWidget(self._new_take_note)
        lay.addLayout(prompt_hdr)
        prompt_frame, self.prompt_ta, self._btn_enhance, _ = prompt_block(
            "Décris ce que doit contenir l'extension… ex: la caméra continue son travelling, le personnage sort du cadre"
        )
        self._btn_enhance.clicked.connect(self._on_enhance)
        lay.addWidget(prompt_frame)

        # ── Toggle import ─────────────────────────────────────────────────────
        toggle_import = toggle_row("Import auto dans Media Pool", "Après génération terminée", True)
        self._import_cb = toggle_import.findChild(QCheckBox)
        _dv_ok = resolve.is_connected()
        self._import_cb.setChecked(_dv_ok)
        self._import_cb.setEnabled(_dv_ok)
        if not _dv_ok:
            self._import_cb.setToolTip(
                "DaVinci Resolve Studio requis — connectez le bridge pour activer cette option"
            )
        lay.addWidget(toggle_import)

        # ── Progression ───────────────────────────────────────────────────────
        self.progress = ProgressBlock()
        lay.addWidget(self.progress)

        # ── Connexion DaVinci ─────────────────────────────────────────────────
        self._davinci_bar = _DaVinciBar()
        lay.addWidget(self._davinci_bar)

        # ── Boutons ───────────────────────────────────────────────────────────
        btn_row = QHBoxLayout()
        self.btn_generate = QPushButton("◎  Générer un nouveau rush")
        self.btn_generate.setMinimumHeight(46)
        self.btn_generate.clicked.connect(self.start_generation)

        self.btn_cancel = QPushButton("Annuler")
        self.btn_cancel.setVisible(False)
        self.btn_cancel.setFixedWidth(100)
        self.btn_cancel.setStyleSheet(f"""
            QPushButton{{background:{C['bg3']};color:{C['text_secondary']};
            border:1px solid {C['border']};border-radius:8px;font-size:12px;
            font-weight:700;padding:13px;}}
            QPushButton:hover{{background:{C['border']};color:{C['text_primary']};}}
        """)
        self.btn_cancel.clicked.connect(self.cancel_generation)

        btn_row.addWidget(self.btn_generate)
        btn_row.addWidget(self.btn_cancel)
        lay.addLayout(btn_row)
        lay.addStretch()

    # ── Images de référence ───────────────────────────────────────────────────

    def _refresh_ref_images(self):
        while self._ref_lay.count():
            item = self._ref_lay.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        for path in self._ref_images:
            thumb = self._make_ref_thumb(path)
            self._ref_lay.addWidget(thumb)

        if len(self._ref_images) < 3:
            btn_add = QPushButton("+")
            btn_add.setFixedSize(56, 56)
            btn_add.setCursor(Qt.CursorShape.PointingHandCursor)
            btn_add.setStyleSheet(f"""
                QPushButton{{
                    background:transparent;color:{C['text_dim']};
                    border:1px dashed {C['border_bright']};border-radius:8px;
                    font-size:20px;font-weight:300;
                }}
                QPushButton:hover{{
                    background:rgba(78,205,196,0.08);color:{C['accent']};
                    border-color:{C['accent']};
                }}
            """)
            btn_add.clicked.connect(self._on_add_ref)
            self._ref_lay.addWidget(btn_add)

        self._ref_lay.addStretch()

    def _make_ref_thumb(self, path: str) -> QWidget:
        w = QWidget()
        w.setFixedSize(56, 56)
        inner = QVBoxLayout(w)
        inner.setContentsMargins(0, 0, 0, 0)
        inner.setSpacing(0)

        img_lbl = QLabel()
        img_lbl.setFixedSize(56, 56)
        img_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        img_lbl.setStyleSheet(
            f"border:1px solid {C['border']};border-radius:6px;"
            f"background:{C['bg3']};"
        )
        pix = QPixmap(path)
        if not pix.isNull():
            img_lbl.setPixmap(pix.scaled(56, 56, Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                                          Qt.TransformationMode.SmoothTransformation))
        else:
            img_lbl.setText("?")

        # Bouton × en overlay
        btn_rm = QPushButton("×", img_lbl)
        btn_rm.setFixedSize(16, 16)
        btn_rm.move(38, 2)
        btn_rm.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_rm.setStyleSheet(
            f"QPushButton{{background:rgba(20,20,30,0.85);color:{C['red']};"
            f"border:none;border-radius:8px;font-size:10px;font-weight:900;padding:0;}}"
            f"QPushButton:hover{{background:{C['red']};color:#fff;}}"
        )
        btn_rm.clicked.connect(lambda _, p=path: self._remove_ref(p))

        inner.addWidget(img_lbl)
        return w

    def _on_add_ref(self):
        paths, _ = QFileDialog.getOpenFileNames(
            self, "Ajouter des images de référence", "",
            "Images (*.png *.jpg *.jpeg *.webp *.bmp)"
        )
        for p in paths:
            if p not in self._ref_images and len(self._ref_images) < 3:
                self._ref_images.append(p)
        self._refresh_ref_images()

    def _remove_ref(self, path: str):
        if path in self._ref_images:
            self._ref_images.remove(path)
        self._refresh_ref_images()

    # ── Direction ─────────────────────────────────────────────────────────────

    def _set_direction(self, value: str):
        self._direction = value
        self.btn_before.set_active(value == "before")
        self.btn_after.set_active(value == "after")
        self.btn_new_take.set_active(value == "new_take")
        labels = {
            "before":   "◀  Générer un début",
            "after":    "▶  Générer une suite",
            "new_take": "◎  Générer un nouveau rush",
        }
        if hasattr(self, "btn_generate"):
            self.btn_generate.setText(labels.get(value, "▶  Modifier le clip"))
        if hasattr(self, "_new_take_note"):
            self._new_take_note.setVisible(value == "new_take")
        if hasattr(self, "prompt_ta"):
            if value == "new_take":
                self.prompt_ta.setPlaceholderText(
                    "Laisse vide pour réutiliser le prompt original…\n"
                    "Ou décris les changements voulus pour cette nouvelle prise"
                )
            else:
                self.prompt_ta.setPlaceholderText(
                    "Décris ce que doit contenir l'extension… "
                    "ex: la caméra continue son travelling, le personnage sort du cadre"
                )

    # ── Clip DaVinci ──────────────────────────────────────────────────────────

    def _load_davinci_clip(self):
        if not resolve.is_connected():
            QMessageBox.warning(
                self, "DaVinci non connecté",
                "Connecte DaVinci Resolve via la barre de statut en haut."
            )
            return

        # Reset label before each attempt
        self._davinci_clip_lbl.setText("Aucun clip sélectionné dans DaVinci Resolve")
        self._davinci_clip_lbl.setStyleSheet(
            f"color:{C['text_dim']};font-size:11px;"
            f"background:{C['bg2']};border:1px solid {C['border']};"
            f"border-radius:6px;padding:8px 14px;"
        )

        clip = get_selected_clip()
        if clip is None:
            # DaVinci scripting API sometimes needs a second call after state change
            import time
            time.sleep(0.3)
            clip = get_selected_clip()

        if clip is None:
            QMessageBox.warning(
                self, "Aucun clip sélectionné",
                "Sélectionne un clip dans la timeline DaVinci puis réessaie.\n\n"
                "Astuce : clique sur le clip dans la timeline DaVinci\n"
                "juste avant de cliquer ce bouton."
            )
            return

        info = get_clip_info(clip)
        file_path = info.get("file_path", "")
        name      = info.get("name", "Clip DaVinci")
        if not file_path:
            QMessageBox.warning(
                self, "Chemin introuvable",
                "Impossible de récupérer le chemin du clip.\n"
                "Vérifie que le média est bien présent sur le disque."
            )
            return
        self._clip_name = name
        self.clip_zone.set_from_davinci(file_path, name)
        self._davinci_clip_lbl.setText(f"◈  {name}")
        self._davinci_clip_lbl.setStyleSheet(
            f"color:{C['accent']};font-size:11px;font-weight:600;"
            f"background:rgba(124,107,255,0.08);border:1px solid {C['accent_dim']};"
            f"border-radius:6px;padding:8px 14px;"
        )

    # ── Génération ────────────────────────────────────────────────────────────

    def _get_duration(self) -> int:
        return self.cb_dur.value()

    def start_generation(self):
        if not self.clip_zone.path:
            QMessageBox.warning(
                self, "Clip manquant",
                "Sélectionne un clip vidéo à étendre !"
            )
            return

        creative_suffix = self._creative.get_creative_suffix()
        base_prompt = self.prompt_ta.toPlainText().strip()

        params = {
            "mode":            "ext",
            "video_path":      self.clip_zone.path,
            "direction":       self._direction,
            "prompt":          base_prompt,
            "creative_suffix": creative_suffix,
            "model":       "seedance-2.0",
            "duration":    self._get_duration(),
            "resolution":  (self.cb_res.currentData() or self.cb_res.currentText()),
            "audio":       False,
            "ref_images":  [p for p in self._ref_images if p and os.path.isfile(p)],
        }

        self.btn_generate.setEnabled(False)
        self.btn_cancel.setVisible(True)
        self.progress.reset()
        self.progress.setVisible(True)

        self._worker = GenerationWorker(params)
        self._worker.progress.connect(self.on_progress)
        self._worker.finished.connect(self.on_finished)
        self._worker.failed.connect(self.on_failed)
        self._worker.start()

    def cancel_generation(self):
        if self._worker:
            self._worker.cancel()
        self._reset_ui()
        self.progress.setVisible(False)

    def on_progress(self, pct: int, msg: str):
        self.progress.update(pct, msg)

    def on_finished(self, result: dict):
        self.progress.set_done()
        self.progress.update(100, "Extension prête !")
        self._reset_ui()

        entry = {**result, "status": "done"}
        save_to_history(entry)
        self.generation_done.emit(entry)

        direction_labels = {"before": "début généré", "after": "suite générée", "new_take": "nouveau rush"}
        direction_lbl = direction_labels.get(self._direction, self._direction)
        davinci_msg = ""
        if self._import_cb and self._import_cb.isChecked():
            dest_dir = get_output_dir()
            base = self._get_clip_base_name()
            filename = self._next_take_filename(base, dest_dir) if base else None
            ir = import_result(result, dest_dir, filename=filename)
            if ir["mock"]:
                davinci_msg = "\n\n◈ Import DaVinci : simulé (mode mock)"
            elif ir["success"]:
                path = ir.get("local_path", "")
                if ir.get("davinci_imported"):
                    davinci_msg = f"\n\n◈ Sauvegardé + importé dans le Media Pool ✓\n{path}"
                else:
                    davinci_msg = f"\n\n◈ Vidéo sauvegardée localement :\n{path}"
            else:
                davinci_msg = f"\n\n◈ Téléchargement échoué : {ir['error']}"

        QMessageBox.information(
            self, "✓ Modification terminée",
            f"Clip modifié ({direction_lbl}) !\n\n"
            f"Durée ajoutée : {result['duration']}s · {result['resolution']}\n"
            f"Crédits : {result['credits_used']}"
            + davinci_msg
        )

    def on_failed(self, error: str):
        self.progress.set_error(error)
        show_api_error(self, error)
        self._reset_ui()
        entry = {
            "mode":         "ext",
            "prompt":       self.prompt_ta.toPlainText().strip(),
            "status":       "error",
            "error":        error,
            "generated_at": datetime.now().isoformat(),
        }
        save_to_history(entry)
        self.generation_done.emit(entry)
        QMessageBox.critical(self, "Erreur", error)

    def _on_enhance(self):
        prompt = self.prompt_ta.toPlainText().strip()
        if not prompt:
            QMessageBox.warning(self, "Prompt vide", "Écris un prompt à améliorer !")
            return
        self._btn_enhance.setEnabled(False)
        if hasattr(self._btn_enhance, "_loading"):
            self._btn_enhance._loading.setVisible(True)
        self._enhance_worker = EnhanceWorker(prompt)
        self._enhance_worker.finished.connect(self._on_enhance_done)
        self._enhance_worker.failed.connect(self._on_enhance_failed)
        self._enhance_worker.start()

    def _on_enhance_done(self, enhanced: str):
        self.prompt_ta.setPlainText(enhanced)
        self._btn_enhance.setEnabled(True)
        if hasattr(self._btn_enhance, "_loading"):
            self._btn_enhance._loading.setVisible(False)

    def _on_enhance_failed(self, error: str):
        self._btn_enhance.setEnabled(True)
        if hasattr(self._btn_enhance, "_loading"):
            self._btn_enhance._loading.setVisible(False)
        QMessageBox.warning(self, "Amélioration impossible", error)

    def _clear_clip(self):
        self.clip_zone.clear()
        self._clip_name = ""

    def _get_clip_base_name(self) -> str:
        """Retourne le nom de base du clip sans suffixe de prise (P01, P1…)."""
        import re
        raw = self._clip_name or os.path.splitext(
            os.path.basename(self.clip_zone.path or "")
        )[0]
        if not raw:
            return ""
        m = re.search(r'\s+[Pp]\d+$', raw)
        return raw[:m.start()].strip() if m else raw.strip()

    def _next_take_filename(self, base: str, dest_dir: str) -> str:
        """Retourne le prochain nom de prise : base P01.mp4, P02.mp4…"""
        import re
        os.makedirs(dest_dir, exist_ok=True)
        pat = re.compile(rf"^{re.escape(base)}\s+P(\d+)\.mp4$", re.IGNORECASE)
        nums = []
        try:
            for fname in os.listdir(dest_dir):
                m = pat.match(fname)
                if m:
                    nums.append(int(m.group(1)))
        except OSError:
            pass
        next_num = (max(nums) + 1) if nums else 1
        return f"{base} P{next_num:02d}.mp4"

    def _reset_ui(self):
        self.btn_generate.setEnabled(True)
        self.btn_cancel.setVisible(False)
