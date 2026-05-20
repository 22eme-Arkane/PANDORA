import os
from datetime import datetime
from PyQt6.QtWidgets import (
    QScrollArea, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QPushButton, QLabel, QFileDialog, QMessageBox, QFrame, QTextEdit, QCheckBox,
)
from PyQt6.QtCore import Qt, pyqtSignal
from ui.styles import C
from ui.widgets import section_label, combo, toggle_row, ProgressBlock, HelpBlock, show_api_error
from core.history import save_to_history
from core.config import get_output_dir
from core.worker import GenerationWorker
from api.enhance import EnhanceWorker
from davinci.importer import import_result


# ── Slot upload individuel ────────────────────────────────────────────────────

class UploadSlot(QFrame):
    """Zone d'upload cliquable avec affichage du fichier sélectionné."""

    FILE_FILTERS = {
        "image": "Images (*.png *.jpg *.jpeg *.webp)",
        "video": "Vidéos (*.mp4 *.mov *.avi *.webm)",
        "audio": "Audio (*.mp3 *.wav *.aac *.m4a *.ogg)",
    }
    ICONS = {"image": "🖼", "video": "🎞", "audio": "🎵"}

    def __init__(self, kind: str, label: str):
        super().__init__()
        self.kind = kind
        self.path = None

        self.setStyleSheet(f"""
            QFrame{{background:{C['bg2']};border:1px dashed {C['border_bright']};border-radius:10px;}}
            QFrame:hover{{border-color:{C['accent_dim']};background:rgba(124,107,255,0.08);}}
        """)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        lay = QVBoxLayout(self)
        lay.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lay.setContentsMargins(12, 16, 12, 16)
        lay.setSpacing(5)

        self.icon_lbl = QLabel(self.ICONS[kind])
        self.icon_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.icon_lbl.setStyleSheet("font-size:22px;border:none;background:transparent;")

        self.main_lbl = QLabel(label)
        self.main_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.main_lbl.setStyleSheet(
            f"color:{C['text_secondary']};font-size:11px;border:none;background:transparent;"
        )

        self.file_lbl = QLabel("")
        self.file_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.file_lbl.setStyleSheet(
            f"color:{C['green']};font-size:10px;font-family:'Consolas',monospace;"
            f"border:none;background:transparent;"
        )
        self.file_lbl.setVisible(False)

        lay.addWidget(self.icon_lbl)
        lay.addWidget(self.main_lbl)
        lay.addWidget(self.file_lbl)

    def mousePressEvent(self, event):
        path, _ = QFileDialog.getOpenFileName(
            self, f"Choisir {self.kind}", "", self.FILE_FILTERS[self.kind]
        )
        if path:
            self.path = path
            name = os.path.basename(path)
            display = name if len(name) <= 22 else name[:19] + "…"
            self.file_lbl.setText(f"✓ {display}")
            self.file_lbl.setVisible(True)
            self.setStyleSheet(f"""
                QFrame{{background:rgba(61,220,151,0.06);border:1px solid {C['green']}44;border-radius:10px;}}
                QFrame:hover{{border-color:{C['green']}88;background:rgba(61,220,151,0.1);}}
            """)

    def clear(self):
        self.path = None
        self.file_lbl.setText("")
        self.file_lbl.setVisible(False)
        self.setStyleSheet(f"""
            QFrame{{background:{C['bg2']};border:1px dashed {C['border_bright']};border-radius:10px;}}
            QFrame:hover{{border-color:{C['accent_dim']};background:rgba(124,107,255,0.08);}}
        """)


# ── Chip @mention ─────────────────────────────────────────────────────────────

class MentionChip(QPushButton):
    """Petit bouton cliquable qui insère @mention dans le prompt."""

    def __init__(self, tag: str, color: str):
        super().__init__(f"@{tag}")
        self.setFixedHeight(22)
        self.setStyleSheet(f"""
            QPushButton{{
                background:rgba(124,107,255,0.12);color:{color};
                border:1px solid {color}55;border-radius:11px;
                font-size:10px;font-weight:700;padding:0 10px;letter-spacing:0px;
            }}
            QPushButton:hover{{background:rgba(124,107,255,0.25);}}
        """)
        self.tag = tag


# ── Bloc prompt avec @mentions ────────────────────────────────────────────────

class PromptWithMentions(QFrame):
    def __init__(self):
        super().__init__()
        self.setStyleSheet(
            f"QFrame{{background:{C['bg2']};border:1px solid {C['border']};border-radius:10px;}}"
        )
        lay = QVBoxLayout(self)
        lay.setContentsMargins(14, 14, 14, 12)
        lay.setSpacing(10)

        self.ta = QTextEdit()
        self.ta.setPlaceholderText(
            "Décris ta scène... Utilise @image, @video, @audio pour référencer tes uploads.\n"
            "Ex: génère une scène où @image marche dans la forêt, avec l'ambiance de @video."
        )
        self.ta.setMinimumHeight(90)
        self.ta.setStyleSheet(
            "QTextEdit{background:transparent;border:none;border-radius:0;font-size:13px;padding:0;}"
        )

        counter = QLabel("0")
        counter.setStyleSheet(
            f"color:{C['text_dim']};font-size:10px;font-family:'Consolas',monospace;"
            f"border:none;background:transparent;"
        )

        def update_count():
            counter.setText(str(len(self.ta.toPlainText())))

        self.ta.textChanged.connect(update_count)

        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet(f"background:{C['border']};max-height:1px;")

        # Chips @mentions
        self.chip_row = QHBoxLayout()
        self.chip_row.setSpacing(6)
        self.chip_row.setContentsMargins(0, 0, 0, 0)

        chip_colors = {
            "image": C["accent"],
            "video": C["orange"],
            "audio": C["green"],
        }
        self._chips = {}
        for tag, color in chip_colors.items():
            chip = MentionChip(tag, color)
            chip.clicked.connect(lambda _, t=tag: self._insert_mention(t))
            self._chips[tag] = chip
            self.chip_row.addWidget(chip)
        self.chip_row.addStretch()
        self.chip_row.addWidget(counter)

        self.enhance_btn = QPushButton("✦ Améliorer")
        self.enhance_btn.setFixedHeight(26)
        self.enhance_btn.setStyleSheet(f"""
            QPushButton{{background:rgba(124,107,255,0.15);color:{C['accent']};
            border:1px solid {C['accent_dim']};border-radius:4px;
            font-size:10px;font-weight:700;padding:0 10px;letter-spacing:0px;}}
            QPushButton:hover{{background:rgba(124,107,255,0.28);}}
        """)

        footer = QHBoxLayout()
        footer.setContentsMargins(0, 0, 0, 0)
        footer.addLayout(self.chip_row)
        footer.addWidget(self.enhance_btn)

        lay.addWidget(self.ta)
        lay.addWidget(sep)
        lay.addLayout(footer)

    def _insert_mention(self, tag: str):
        cursor = self.ta.textCursor()
        text = self.ta.toPlainText()
        pos = cursor.position()
        if pos > 0 and text[pos - 1] != " ":
            cursor.insertText(f" @{tag} ")
        else:
            cursor.insertText(f"@{tag} ")
        self.ta.setFocus()

    def text(self) -> str:
        return self.ta.toPlainText().strip()


# ── Onglet Référence ──────────────────────────────────────────────────────────

class TabReference(QScrollArea):
    generation_done = pyqtSignal(dict)

    def __init__(self):
        super().__init__()
        self.setWidgetResizable(True)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._worker = None
        self._enhance_worker = None

        container = QWidget()
        self.setWidget(container)
        lay = QVBoxLayout(container)
        lay.setContentsMargins(20, 20, 20, 20)
        lay.setSpacing(16)

        lay.addWidget(HelpBlock("Référence multimodale — Guider avec image, vidéo ou audio", [
            "▸ Combinez jusqu'à 3 références (image + vidéo + audio) pour guider la génération.",
            "▸ Image de référence : impose l'apparence visuelle, les couleurs et la composition.",
            "▸ Vidéo de référence : guide le mouvement et le rythme du clip généré.",
            "▸ Audio de référence : synchronise l'ambiance sonore avec le rendu visuel.",
            "▸ Ajoutez un prompt pour affiner davantage le résultat au-delà des références.",
        ], C))

        # ── Slots upload ──────────────────────────────────────────────────────
        lay.addWidget(section_label("Références médias"))

        slots_row = QHBoxLayout()
        slots_row.setSpacing(10)
        self.slot_image = UploadSlot("image", "Image de référence")
        self.slot_video = UploadSlot("video", "Vidéo de référence")
        self.slot_audio = UploadSlot("audio", "Audio de référence")
        slots_row.addWidget(self.slot_image)
        slots_row.addWidget(self.slot_video)
        slots_row.addWidget(self.slot_audio)
        lay.addLayout(slots_row)

        hint = QLabel("Clique sur un slot pour uploader · Insère @image @video @audio dans le prompt")
        hint.setStyleSheet(
            f"color:{C['text_dim']};font-size:10px;font-family:'Consolas',monospace;"
        )
        lay.addWidget(hint)

        # ── Prompt ────────────────────────────────────────────────────────────
        lay.addWidget(section_label("Prompt"))
        self.prompt_widget = PromptWithMentions()
        self.prompt_widget.enhance_btn.clicked.connect(self._on_enhance)
        lay.addWidget(self.prompt_widget)

        # ── Options ───────────────────────────────────────────────────────────
        grid = QGridLayout()
        grid.setSpacing(12)
        self.cb_dur = combo(["5 secondes", "10 secondes", "15 secondes"])
        self.cb_res = combo(["1080p", "720p", "480p"])
        self.cb_ratio = combo(["16:9 — Paysage", "9:16 — Portrait", "4:3", "3:4"])

        for (row, col), lbl, widget in [
            ((0, 0), "Durée",      self.cb_dur),
            ((0, 1), "Résolution", self.cb_res),
            ((1, 0), "Ratio",      self.cb_ratio),
        ]:
            g = QWidget()
            l = QVBoxLayout(g)
            l.setContentsMargins(0, 0, 0, 0)
            l.setSpacing(6)
            l.addWidget(section_label(lbl))
            l.addWidget(widget)
            grid.addWidget(g, row, col)
        lay.addLayout(grid)

        toggle_import = toggle_row("Import auto dans Media Pool", "Après génération terminée", True)
        self._import_cb = toggle_import.findChild(QCheckBox)
        lay.addWidget(toggle_import)

        # ── Progression ───────────────────────────────────────────────────────
        self.progress = ProgressBlock()
        lay.addWidget(self.progress)

        # ── Boutons ───────────────────────────────────────────────────────────
        btn_row = QHBoxLayout()
        self.btn_generate = QPushButton("▶  Générer depuis références")
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

    def start_generation(self):
        prompt = self.prompt_widget.text()
        has_media = any([
            self.slot_image.path,
            self.slot_video.path,
            self.slot_audio.path,
        ])

        if not prompt and not has_media:
            QMessageBox.warning(
                self, "Rien à générer",
                "Ajoute au moins une référence média ou un prompt !"
            )
            return

        params = {
            "mode":        "ref",
            "prompt":      prompt,
            "model":       "seedance-2.0",
            "duration":    [5, 10, 15][self.cb_dur.currentIndex()],
            "resolution":  self.cb_res.currentText(),
            "aspect_ratio": self.cb_ratio.currentText().split(" ")[0],
            "image_path":  self.slot_image.path or "",
            "video_path":  self.slot_video.path or "",
            "audio_path":  self.slot_audio.path or "",
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
        self.progress.update(100, "Vidéo prête !")
        self._reset_ui()
        entry = {**result, "status": "done"}
        save_to_history(entry)
        self.generation_done.emit(entry)
        davinci_msg = ""
        if self._import_cb and self._import_cb.isChecked():
            ir = import_result(result, get_output_dir())
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
            self, "✓ Génération terminée",
            f"Clip généré depuis références !\n\n"
            f"Durée : {result['duration']}s · {result['resolution']}\n"
            f"Crédits : {result['credits_used']}"
            + davinci_msg
        )

    def on_failed(self, error: str):
        self.progress.set_error(error)
        show_api_error(self, error)
        self._reset_ui()
        entry = {
            "mode":         "ref",
            "prompt":       self.prompt_widget.text(),
            "status":       "error",
            "error":        error,
            "generated_at": datetime.now().isoformat(),
        }
        save_to_history(entry)
        self.generation_done.emit(entry)
        QMessageBox.critical(self, "Erreur", error)

    def _on_enhance(self):
        prompt = self.prompt_widget.text()
        if not prompt:
            QMessageBox.warning(self, "Prompt vide", "Écris un prompt à améliorer !")
            return
        btn = self.prompt_widget.enhance_btn
        btn.setEnabled(False)
        btn.setText("…")
        self._enhance_worker = EnhanceWorker(prompt)
        self._enhance_worker.finished.connect(self._on_enhance_done)
        self._enhance_worker.failed.connect(self._on_enhance_failed)
        self._enhance_worker.start()

    def _on_enhance_done(self, enhanced: str):
        self.prompt_widget.ta.setPlainText(enhanced)
        btn = self.prompt_widget.enhance_btn
        btn.setEnabled(True)
        btn.setText("✦ Améliorer")

    def _on_enhance_failed(self, error: str):
        btn = self.prompt_widget.enhance_btn
        btn.setEnabled(True)
        btn.setText("✦ Améliorer")
        QMessageBox.warning(self, "Amélioration impossible", error)

    def _reset_ui(self):
        self.btn_generate.setEnabled(True)
        self.btn_cancel.setVisible(False)
