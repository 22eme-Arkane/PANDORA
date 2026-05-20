import os
from PyQt6.QtWidgets import (
    QScrollArea, QWidget, QVBoxLayout, QGridLayout,
    QPushButton, QLabel, QFileDialog, QMessageBox, QCheckBox,
)
from PyQt6.QtCore import Qt, pyqtSignal
from ui.styles import C
from ui.widgets import section_label, combo, toggle_row, prompt_block, upload_zone, ProgressBlock, HelpBlock, show_api_error
from core.history import save_to_history
from core.config import get_output_dir
from core.worker import GenerationWorker
from api.enhance import EnhanceWorker
from davinci.bridge import resolve
from davinci.importer import import_result


class TabI2V(QScrollArea):
    generation_done = pyqtSignal(dict)

    def __init__(self):
        super().__init__()
        self.setWidgetResizable(True)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._worker = None
        self._enhance_worker = None
        self._image_path = None

        container = QWidget()
        self.setWidget(container)
        lay = QVBoxLayout(container)
        lay.setContentsMargins(20, 20, 20, 20)
        lay.setSpacing(16)

        lay.addWidget(HelpBlock("Image-to-Video — Animer une image fixe", [
            "▸ Chargez une image (PNG · JPG · WEBP) pour l'animer et en faire un clip vidéo.",
            "▸ Ajoutez un prompt pour décrire le mouvement et l'ambiance souhaitée.",
            "▸ Activez Référence casting pour injecter les portraits des personnages sélectionnés.",
            "▸ Choisissez la durée (2–10 s), la résolution et le style de film avant de lancer.",
            "▸ Sans clé fal.ai → mode mock (simulation locale, aucun crédit consommé).",
        ], C))

        lay.addWidget(section_label("Image source"))
        self.upload = upload_zone("🖼", "Clique pour choisir une image", "PNG · JPG · WEBP · max 10 MB")
        self.upload.mousePressEvent = lambda e: self.pick_image()
        lay.addWidget(self.upload)

        self.image_label = QLabel("")
        self.image_label.setStyleSheet(
            f"color:{C['green']};font-size:11px;font-family:'Consolas',monospace;"
        )
        lay.addWidget(self.image_label)

        lay.addWidget(section_label("Prompt de mouvement"))
        prompt_frame, self.prompt_ta, self._btn_enhance, _ = prompt_block(
            "Décris le mouvement... ex: la caméra recule lentement, le personnage tourne la tête"
        )
        self._btn_enhance.clicked.connect(self._on_enhance)
        lay.addWidget(prompt_frame)

        grid = QGridLayout()
        grid.setSpacing(12)
        self.cb_dur = combo(["5 secondes", "10 secondes", "15 secondes"])
        self.cb_res = combo(["1080p", "720p", "480p"])
        for col_idx, lbl, widget in [(0, "Durée", self.cb_dur), (1, "Résolution", self.cb_res)]:
            g = QWidget()
            l = QVBoxLayout(g)
            l.setContentsMargins(0, 0, 0, 0)
            l.setSpacing(6)
            l.addWidget(section_label(lbl))
            l.addWidget(widget)
            grid.addWidget(g, 0, col_idx)
        lay.addLayout(grid)

        lay.addWidget(toggle_row("Contrôle premier / dernier frame", "Frames-to-Video mode", False))

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

        self.progress = ProgressBlock()
        lay.addWidget(self.progress)

        self.btn_generate = QPushButton("▶  Animer l'image")
        self.btn_generate.setMinimumHeight(46)
        self.btn_generate.clicked.connect(self.start_generation)
        lay.addWidget(self.btn_generate)
        lay.addStretch()

    def pick_image(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Choisir une image", "", "Images (*.png *.jpg *.jpeg *.webp)"
        )
        if path:
            self._image_path = path
            self.image_label.setText(f"✓  {os.path.basename(path)}")

    def start_generation(self):
        prompt = self.prompt_ta.toPlainText().strip()
        if not prompt:
            QMessageBox.warning(self, "Prompt vide", "Écris un prompt de mouvement !")
            return

        params = {
            "mode":       "i2v",
            "prompt":     prompt,
            "model":      "seedance-2.0",
            "duration":   [5, 10, 15][self.cb_dur.currentIndex()],
            "resolution": self.cb_res.currentText(),
            "image_path": self._image_path or "",
        }

        self.btn_generate.setEnabled(False)
        self.progress.reset()
        self.progress.setVisible(True)

        self._worker = GenerationWorker(params)
        self._worker.progress.connect(self.progress.update)
        self._worker.finished.connect(self.on_finished)
        self._worker.failed.connect(self.on_failed)
        self._worker.start()

    def on_finished(self, result: dict):
        self.progress.set_done()
        self.btn_generate.setEnabled(True)
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

        QMessageBox.information(self, "✓ Terminé", "Image animée avec succès !" + davinci_msg)

    def on_failed(self, error: str):
        self.progress.set_error(error)
        self.btn_generate.setEnabled(True)
        show_api_error(self, error)

    def _on_enhance(self):
        prompt = self.prompt_ta.toPlainText().strip()
        if not prompt:
            QMessageBox.warning(self, "Prompt vide", "Écris un prompt à améliorer !")
            return
        self._btn_enhance.setEnabled(False)
        self._btn_enhance.setText("…")
        self._enhance_worker = EnhanceWorker(prompt)
        self._enhance_worker.finished.connect(self._on_enhance_done)
        self._enhance_worker.failed.connect(self._on_enhance_failed)
        self._enhance_worker.start()

    def _on_enhance_done(self, enhanced: str):
        self.prompt_ta.setPlainText(enhanced)
        self._btn_enhance.setEnabled(True)
        self._btn_enhance.setText("✦ Améliorer")

    def _on_enhance_failed(self, error: str):
        self._btn_enhance.setEnabled(True)
        self._btn_enhance.setText("✦ Améliorer")
        QMessageBox.warning(self, "Amélioration impossible", error)
