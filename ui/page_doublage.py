"""
ui/page_doublage.py — Page Doublage : synthèse vocale IA + clonage de voix.

Modes :
  - ElevenLabs Turbo v2.5 : voix multilingues dont FR (fal-ai, $0.05/1000 chars)
  - F5-TTS                : clonage de voix multilingue (EN/ZH principalement, FR expérimental)

Pipeline complet : F5-TTS → (futur) pydub mix → (futur) LatentSync lip sync
"""

import os
import subprocess

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QScrollArea, QTextEdit, QComboBox, QFrame, QFileDialog,
    QProgressBar, QSizePolicy,
)
from PyQt6.QtCore import Qt, QUrl
from core.i18n import translate
from PyQt6.QtGui import QDesktopServices

from ui.styles import CP, PANDORA_STYLESHEET
from ui.widgets import section_label, HelpBlock, show_api_error
from ui.icons import load_icon
from api.tts import (
    ElevenLabsWorker, ELEVENLABS_VOICES, ELEVENLABS_VOICES_FR,
    F5TTSWorker,
)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _btn(text: str, accent: str, h: int = 34) -> QPushButton:
    """Bouton outline PANDORA — même style que « Générer les Moods »."""
    b = QPushButton(text)
    b.setFixedHeight(h)
    b.setCursor(Qt.CursorShape.PointingHandCursor)
    # Calcule une rgba pour le hover à partir de la couleur hex
    try:
        r = int(accent[1:3], 16)
        g = int(accent[3:5], 16)
        bv = int(accent[5:7], 16)
        hover = f"rgba({r},{g},{bv},0.12)"
        pressed = f"rgba({r},{g},{bv},0.22)"
    except Exception:
        hover = "rgba(78,205,196,0.12)"
        pressed = "rgba(78,205,196,0.22)"
    b.setStyleSheet(
        f"QPushButton{{background:transparent;color:{accent};"
        f"border:1px solid {accent};border-radius:8px;"
        f"font-size:11px;font-weight:700;padding:0 14px;}}"
        f"QPushButton:hover{{background:{hover};}}"
        f"QPushButton:pressed{{background:{pressed};}}"
        f"QPushButton:disabled{{color:{CP['text_dim']};border-color:{CP['border']};}}"
    )
    return b


def _sep() -> QFrame:
    f = QFrame()
    f.setFrameShape(QFrame.Shape.HLine)
    f.setStyleSheet(f"background:{CP['border']};max-height:1px;border:none;")
    return f


# ── Carte de résultat audio ───────────────────────────────────────────────────

class _AudioCard(QFrame):
    def __init__(self, path: str, label: str, mode: str, parent=None):
        super().__init__(parent)
        self._path = path
        self.setStyleSheet(
            f"QFrame{{background:{CP['bg2']};border:1px solid {CP['border']};"
            f"border-radius:8px;}}"
        )
        lay = QHBoxLayout(self)
        lay.setContentsMargins(14, 10, 14, 10)
        lay.setSpacing(10)

        mode_lbl = QLabel(mode)
        mode_lbl.setFixedWidth(60)
        mode_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        _c = CP["accent"] if mode == "ElevenLabs" else (
            CP["accent2"] if mode == "F5-TTS" else CP["text_secondary"]
        )
        mode_lbl.setStyleSheet(
            f"color:{_c};font-size:9px;font-weight:700;font-family:'Consolas',monospace;"
            f"background:transparent;border:1px solid {_c};border-radius:4px;"
            f"padding:2px 4px;"
        )
        lay.addWidget(mode_lbl)

        name_lbl = QLabel(label)
        name_lbl.setStyleSheet(
            f"color:{CP['text_primary']};font-size:11px;font-weight:600;"
            f"background:transparent;border:none;"
        )
        lay.addWidget(name_lbl, 1)

        if path and os.path.isfile(path):
            file_lbl = QLabel(os.path.basename(path))
            file_lbl.setStyleSheet(
                f"color:{CP['text_dim']};font-size:9px;font-family:'Consolas',monospace;"
                f"background:transparent;border:none;"
            )
            lay.addWidget(file_lbl)

        _btn_ss = (
            f"QPushButton{{background:{CP['bg3']};color:{CP['text_secondary']};"
            f"border:1px solid {CP['border']};border-radius:6px;"
            f"font-size:10px;font-weight:700;padding:0 8px;}}"
            f"QPushButton:hover{{background:{CP['bg2']};color:{CP['text_primary']};"
            f"border-color:{CP['border_bright']};}}"
        )
        btn_play = QPushButton("Écouter")
        btn_play.setFixedHeight(28)
        btn_play.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_play.setToolTip("Ouvrir le fichier audio dans le lecteur par défaut")
        btn_play.setStyleSheet(_btn_ss)
        btn_play.clicked.connect(self._play)
        lay.addWidget(btn_play)

        btn_folder = QPushButton("Dossier")
        btn_folder.setFixedHeight(28)
        btn_folder.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_folder.setToolTip("Ouvrir le dossier contenant le fichier audio")
        btn_folder.setStyleSheet(_btn_ss)
        btn_folder.clicked.connect(self._open_folder)
        lay.addWidget(btn_folder)

    def _play(self):
        if self._path and os.path.isfile(self._path):
            QDesktopServices.openUrl(QUrl.fromLocalFile(self._path))

    def _open_folder(self):
        folder = os.path.dirname(self._path) if self._path else ""
        if folder and os.path.isdir(folder):
            try:
                subprocess.Popen(["explorer", folder])
            except Exception:
                QDesktopServices.openUrl(QUrl.fromLocalFile(folder))


# ── Page principale ───────────────────────────────────────────────────────────

class PageDoublage(QWidget):
    def __init__(self):
        super().__init__()
        self.setStyleSheet(f"background:{CP['bg0']};")

        self._tts_worker             = None
        self._mode: str              = "elevenlabs"   # "elevenlabs" | "clone"
        self._voice_sample_path: str = ""
        self._results: list[dict]    = []

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ── En-tête ───────────────────────────────────────────────────────────
        hdr = QWidget()
        hdr.setFixedHeight(56)
        hdr.setStyleSheet(
            f"background:{CP['bg1']};border-bottom:1px solid {CP['border']};"
        )
        hl = QHBoxLayout(hdr)
        hl.setContentsMargins(24, 0, 24, 0)
        badge = QLabel()
        badge.setFixedSize(36, 36)
        badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        _badge_pix = load_icon("doublage.png", 28)
        if not _badge_pix.isNull():
            badge.setPixmap(_badge_pix)
            badge.setStyleSheet(
                f"background:{CP['accent']}22;border-radius:8px;border:none;"
            )
        else:
            badge.setText("🎙")
            badge.setStyleSheet(
                f"background:{CP['accent']}22;border-radius:8px;"
                f"font-size:18px;border:none;"
            )
        hl.addWidget(badge)
        hl.addSpacing(10)
        title_col = QVBoxLayout()
        title_col.setSpacing(1)
        t1 = QLabel("Doublage & Synthèse vocale IA")
        t1.setStyleSheet(
            f"color:{CP['accent']};font-size:14px;font-weight:700;"
            f"background:transparent;"
        )
        t2 = QLabel("ElevenLabs Turbo v2.5 · F5-TTS (clonage voix)")
        t2.setStyleSheet(
            f"color:{CP['text_dim']};font-size:9px;font-family:'Consolas',monospace;"
            f"letter-spacing:1px;background:transparent;"
        )
        title_col.addWidget(t1)
        title_col.addWidget(t2)
        hl.addLayout(title_col)
        hl.addStretch()
        root.addWidget(hdr)

        # ── Scroll principal ──────────────────────────────────────────────────
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet("QScrollArea{background:transparent;border:none;}")
        content = QWidget()
        content.setStyleSheet("background:transparent;")
        self._content_lay = QVBoxLayout(content)
        self._content_lay.setContentsMargins(24, 24, 24, 24)
        self._content_lay.setSpacing(20)
        scroll.setWidget(content)
        root.addWidget(scroll, 1)

        self._content_lay.addWidget(HelpBlock("Doublage & Synthèse vocale IA", [
            "▸ ElevenLabs Turbo v2.5 : synthèse vocale avec sélection de voix — principalement anglais, résultats variables en français.",
            "▸ F5-TTS Clonage : clone une voix depuis un échantillon audio — langue détectée depuis le texte. Entraîné principalement sur l'anglais et le chinois : le français peut sonner avec un accent.",
            "▸ Note : les modèles de synthèse vocale IA sont encore peu optimisés pour le français. Pour un résultat professionnel en FR, un comédien de doublage reste la meilleure option.",
            "▸ Sélectionne un mode, écris le texte, puis clique sur « Générer l'audio ».",
            "▸ Les fichiers générés apparaissent en bas — clique ▶ pour écouter ou 📁 pour ouvrir le dossier.",
        ], CP))

        self._build_mode_selector()
        self._build_input_panel()
        self._build_results_panel()
        self._build_voice_assign_panel()
        self._content_lay.addStretch()

    # ── Sélecteur de mode ─────────────────────────────────────────────────────

    def _build_mode_selector(self):
        row = QHBoxLayout()
        row.setSpacing(10)

        self._btn_mode_eleven = self._make_mode_card(
            "ElevenLabs Turbo v2.5",
            "20 voix · multilingue FR/EN/ES… · sélection de voix\n$0.05 / 1000 caractères",
            CP["accent"], True,
        )
        self._btn_mode_clone = self._make_mode_card(
            "Clonage de voix — F5-TTS",
            "Clone n'importe quelle voix · EN/ZH principalement · FR expérimental\nLangue détectée automatiquement depuis le texte",
            CP["accent2"], False,
        )
        self._btn_mode_eleven.clicked.connect(lambda: self._set_mode("elevenlabs"))
        self._btn_mode_clone.clicked.connect(lambda: self._set_mode("clone"))

        row.addWidget(self._btn_mode_eleven, 1)
        row.addWidget(self._btn_mode_clone, 1)
        self._content_lay.addLayout(row)

    def _make_mode_card(self, title: str, desc: str,
                         accent: str, active: bool) -> QPushButton:
        btn = QPushButton()
        btn.setFixedHeight(72)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.setCheckable(True)
        btn.setChecked(active)
        self._apply_mode_card_style(btn, active, accent)

        lay = QHBoxLayout(btn)
        lay.setContentsMargins(18, 0, 20, 0)
        lay.setSpacing(0)

        txt = QVBoxLayout()
        txt.setSpacing(4)
        t1 = QLabel(title)
        t1.setStyleSheet(
            f"color:{CP['text_primary']};font-size:13px;font-weight:700;"
            f"background:transparent;border:none;"
        )
        t2 = QLabel(desc)
        t2.setStyleSheet(
            f"color:{CP['text_dim']};font-size:9px;background:transparent;border:none;"
        )
        txt.addWidget(t1)
        txt.addWidget(t2)
        lay.addLayout(txt, 1)
        btn.setProperty("accent", accent)
        return btn

    @staticmethod
    def _apply_mode_card_style(btn: QPushButton, active: bool, accent: str):
        if active:
            try:
                r = int(accent[1:3], 16)
                g = int(accent[3:5], 16)
                b = int(accent[5:7], 16)
                hover_bg = f"rgba({r},{g},{b},0.10)"
            except Exception:
                hover_bg = "rgba(78,205,196,0.10)"
            btn.setStyleSheet(
                f"QPushButton{{background:transparent;color:{accent};"
                f"border:2px solid {accent};"
                f"border-radius:10px;text-align:left;}}"
                f"QPushButton:hover{{background:{hover_bg};}}"
            )
        else:
            btn.setStyleSheet(
                f"QPushButton{{background:{CP['bg2']};border:1px solid {CP['border']};"
                f"border-radius:10px;text-align:left;}}"
                f"QPushButton:hover{{background:{CP['bg3']};"
                f"border-color:{CP['border_bright']};}}"
            )

    def _set_mode(self, mode: str):
        self._mode = mode
        is_eleven = (mode == "elevenlabs")
        is_clone  = (mode == "clone")
        self._apply_mode_card_style(
            self._btn_mode_eleven, is_eleven, self._btn_mode_eleven.property("accent"))
        self._apply_mode_card_style(
            self._btn_mode_clone, is_clone, self._btn_mode_clone.property("accent"))
        self._btn_mode_eleven.setChecked(is_eleven)
        self._btn_mode_clone.setChecked(is_clone)
        self._eleven_frame.setVisible(is_eleven)
        self._clone_frame.setVisible(is_clone)
        self._btn_generate.setText("🎙  Générer l'audio")

    # ── Panneau d'entrée ──────────────────────────────────────────────────────

    def _build_input_panel(self):
        frame = QFrame()
        frame.setStyleSheet(
            f"QFrame{{background:{CP['bg1']};border:1px solid {CP['border']};"
            f"border-radius:12px;}}"
        )
        lay = QVBoxLayout(frame)
        lay.setContentsMargins(20, 18, 20, 18)
        lay.setSpacing(14)

        # ── Texte à synthétiser (caché en mode sous-titrage) ──────────────────
        self._text_section = QWidget()
        self._text_section.setStyleSheet("background:transparent;")
        ts_lay = QVBoxLayout(self._text_section)
        ts_lay.setContentsMargins(0, 0, 0, 0)
        ts_lay.setSpacing(6)

        ts_lay.addWidget(section_label("Texte à synthétiser"))
        self._text_edit = QTextEdit()
        self._text_edit.setPlaceholderText(
            "Écris ici le dialogue à synthétiser…\n"
            "ex: « Bienvenue dans PANDORA, l'outil de pré-production cinéma IA. »"
        )
        self._text_edit.setMinimumHeight(90)
        self._text_edit.setStyleSheet(
            f"QTextEdit{{background:{CP['bg2']};border:1px solid {CP['border']};"
            f"border-radius:8px;color:{CP['text_primary']};font-size:12px;"
            f"font-family:'Segoe UI',sans-serif;padding:8px;}}"
            f"QTextEdit:focus{{border-color:{CP['accent']};}}"
        )
        self._text_edit.textChanged.connect(self._on_text_changed)
        ts_lay.addWidget(self._text_edit)

        self._char_counter = QLabel("0 caractères")
        self._char_counter.setStyleSheet(
            f"color:{CP['text_dim']};font-size:10px;font-family:'Consolas',monospace;"
            f"background:transparent;"
        )
        ts_lay.addWidget(self._char_counter)
        lay.addWidget(self._text_section)

        lay.addWidget(_sep())

        # ── Config ElevenLabs ─────────────────────────────────────────────────
        self._eleven_frame = QWidget()
        ef_lay = QVBoxLayout(self._eleven_frame)
        ef_lay.setContentsMargins(0, 0, 0, 0)
        ef_lay.setSpacing(8)

        voice_row = QHBoxLayout()
        voice_row.setSpacing(12)

        voice_col = QVBoxLayout()
        voice_col.setSpacing(4)
        voice_col.addWidget(section_label("Voix ElevenLabs"))
        _combo_ss = (
            f"QComboBox{{background:{CP['bg2']};border:1px solid {CP['border']};"
            f"border-radius:6px;color:{CP['text_primary']};font-size:12px;padding:0 8px;}}"
            f"QComboBox:focus{{border-color:{CP['accent']};}}"
            f"QComboBox::drop-down{{border:none;width:18px;}}"
            f"QComboBox QAbstractItemView{{background:{CP['bg2']};border:1px solid {CP['border_bright']};"
            f"color:{CP['text_primary']};selection-background-color:{CP['accent_dim']};"
            f"font-size:11px;padding:4px;}}"
        )
        self._voice_combo = QComboBox()
        self._voice_combo.setFixedHeight(34)
        self._voice_combo.setStyleSheet(_combo_ss)
        for v in ELEVENLABS_VOICES:
            lang_tag = " · FR/EN" if v in ELEVENLABS_VOICES_FR else " · EN"
            self._voice_combo.addItem(f"{v}{lang_tag}", v)
        self._voice_combo.setCurrentIndex(0)
        voice_col.addWidget(self._voice_combo)
        voice_row.addLayout(voice_col, 1)

        ef_lay.addLayout(voice_row)
        note_el = QLabel("FR/EN = voix disponibles en français · EN = anglais uniquement · résultats variables selon la voix")
        note_el.setStyleSheet(
            f"color:{CP['text_dim']};font-size:9px;font-family:'Consolas',monospace;"
            f"background:transparent;"
        )
        ef_lay.addWidget(note_el)
        lay.addWidget(self._eleven_frame)

        # ── Config F5-TTS — Clonage voix multilingue ─────────────────────────
        self._clone_frame = QWidget()
        self._clone_frame.setVisible(False)
        cf_lay = QVBoxLayout(self._clone_frame)
        cf_lay.setContentsMargins(0, 0, 0, 0)
        cf_lay.setSpacing(8)
        cf_lay.addWidget(section_label("Échantillon vocal de référence"))

        sample_row = QHBoxLayout()
        sample_row.setSpacing(8)
        self._lbl_sample = QLabel("Aucun échantillon chargé")
        self._lbl_sample.setStyleSheet(
            f"color:{CP['text_dim']};font-size:10px;font-family:'Consolas',monospace;"
            f"background:{CP['bg2']};border:1px solid {CP['border']};border-radius:6px;"
            f"padding:6px 10px;"
        )
        self._lbl_sample.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed
        )
        self._lbl_sample.setFixedHeight(32)
        btn_upload = _btn("📂  Charger un fichier audio", CP["accent2"])
        btn_upload.setFixedWidth(220)
        btn_upload.clicked.connect(self._on_load_sample)
        sample_row.addWidget(self._lbl_sample, 1)
        sample_row.addWidget(btn_upload)
        cf_lay.addLayout(sample_row)

        note_clone = QLabel(
            "Formats acceptés : MP3 · WAV · M4A · AAC · OGG  —  durée recommandée : 5–30 s"
            "  ·  Langue détectée automatiquement depuis le texte (FR, EN, ES, ZH…)"
        )
        note_clone.setStyleSheet(
            f"color:{CP['text_dim']};font-size:9px;font-family:'Consolas',monospace;"
            f"background:transparent;"
        )
        cf_lay.addWidget(note_clone)

        lang_info = QLabel("La langue est détectée automatiquement depuis le texte saisi — écris en français, le rendu sera en français.")
        lang_info.setWordWrap(True)
        lang_info.setStyleSheet(
            f"color:{CP['text_secondary']};font-size:9px;font-family:'Consolas',monospace;"
            f"background:transparent;"
        )
        cf_lay.addWidget(lang_info)

        lay.addWidget(self._clone_frame)

        lay.addWidget(_sep())

        # ── Barre de progression ──────────────────────────────────────────────
        self._progress = QProgressBar()
        self._progress.setFixedHeight(5)
        self._progress.setTextVisible(False)
        self._progress.setRange(0, 100)
        self._progress.setValue(0)
        self._progress.setVisible(False)
        self._progress.setStyleSheet(
            f"QProgressBar{{background:{CP['bg3']};border-radius:2px;border:none;}}"
            f"QProgressBar::chunk{{background:{CP['accent2']};border-radius:2px;}}"
        )
        lay.addWidget(self._progress)

        self._lbl_status = QLabel("")
        self._lbl_status.setVisible(False)
        self._lbl_status.setStyleSheet(
            f"color:{CP['text_dim']};font-size:10px;font-family:'Consolas',monospace;"
            f"background:transparent;"
        )
        lay.addWidget(self._lbl_status)

        # ── Bouton Générer ────────────────────────────────────────────────────
        self._btn_generate = QPushButton("🎙  Générer l'audio")
        self._btn_generate.setFixedHeight(44)
        self._btn_generate.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_generate.setStyleSheet(
            f"QPushButton{{background:{CP['accent']};color:#07080f;"
            f"border:none;border-radius:8px;font-size:13px;font-weight:700;"
            f"letter-spacing:0.5px;}}"
            f"QPushButton:hover{{background:#6eded6;}}"
            f"QPushButton:pressed{{background:{CP['accent_dim']};color:#fff;}}"
            f"QPushButton:disabled{{background:{CP['bg3']};color:{CP['text_dim']};}}"
        )
        self._btn_generate.clicked.connect(self._on_generate)
        lay.addWidget(self._btn_generate)

        self._content_lay.addWidget(frame)

    # ── Panneau résultats ─────────────────────────────────────────────────────

    def _build_results_panel(self):
        hdr_row = QHBoxLayout()
        hdr_lbl = QLabel("FICHIERS GÉNÉRÉS")
        hdr_lbl.setStyleSheet(
            f"color:{CP['text_secondary']};font-size:10px;font-weight:700;"
            f"letter-spacing:3px;font-family:'Consolas',monospace;background:transparent;"
        )
        hdr_row.addWidget(hdr_lbl)
        hdr_row.addStretch()
        btn_clear = QPushButton("✕  Vider la liste")
        btn_clear.setFixedHeight(24)
        btn_clear.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_clear.setStyleSheet(
            f"QPushButton{{background:transparent;color:{CP['text_dim']};"
            f"border:1px solid {CP['border']};border-radius:5px;font-size:10px;padding:0 10px;}}"
            f"QPushButton:hover{{color:{CP['red']};border-color:{CP['red']};}}"
        )
        btn_clear.clicked.connect(self._clear_results)
        hdr_row.addWidget(btn_clear)
        self._content_lay.addLayout(hdr_row)

        self._results_container = QVBoxLayout()
        self._results_container.setSpacing(8)
        self._results_container.setAlignment(Qt.AlignmentFlag.AlignTop)

        self._lbl_empty_results = QLabel("Aucun fichier généré.")
        self._lbl_empty_results.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._lbl_empty_results.setStyleSheet(
            f"color:{CP['text_dim']};font-size:12px;padding:20px;"
            f"background:transparent;"
        )
        self._results_container.addWidget(self._lbl_empty_results)
        self._content_lay.addLayout(self._results_container)

    # ── Logique ───────────────────────────────────────────────────────────────

    def _on_text_changed(self):
        n = len(self._text_edit.toPlainText())
        if self._mode == "elevenlabs":
            cost = n / 1000 * 0.05
            self._char_counter.setText(f"{n} caractères  ~${cost:.4f} (ElevenLabs)")
        else:
            self._char_counter.setText(f"{n} caractères")

    def _on_load_sample(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Charger un échantillon vocal",
            os.path.expanduser("~"),
            "Audio (*.mp3 *.wav *.m4a *.aac *.ogg);;Tous (*.*)",
        )
        if not path:
            return
        self._voice_sample_path = path
        self._lbl_sample.setText(os.path.basename(path))
        self._lbl_sample.setStyleSheet(
            f"color:{CP['accent2']};font-size:10px;font-family:'Consolas',monospace;"
            f"background:{CP['bg2']};border:1px solid {CP['accent2']};border-radius:6px;"
            f"padding:6px 10px;"
        )

    def _on_generate(self):
        self._btn_generate.setEnabled(False)
        self._progress.setVisible(True)
        self._progress.setValue(0)
        self._lbl_status.setVisible(True)
        self._lbl_status.setText("Initialisation…")

        if self._mode == "clone":
            text = self._text_edit.toPlainText().strip()
            if not text:
                self._btn_generate.setEnabled(True)
                self._progress.setVisible(False)
                self._lbl_status.setVisible(False)
                return
            if not self._voice_sample_path:
                from PyQt6.QtWidgets import QMessageBox
                QMessageBox.warning(
                    self, "Échantillon vocal requis",
                    "Chargez un fichier audio de référence pour utiliser le clonage de voix."
                )
                self._btn_generate.setEnabled(True)
                self._progress.setVisible(False)
                self._lbl_status.setVisible(False)
                return
            label = os.path.splitext(os.path.basename(self._voice_sample_path))[0]
            self._tts_worker = F5TTSWorker(text, self._voice_sample_path, label=label)
            mode_label = "F5-TTS"

        else:  # elevenlabs
            text = self._text_edit.toPlainText().strip()
            if not text:
                self._btn_generate.setEnabled(True)
                self._progress.setVisible(False)
                self._lbl_status.setVisible(False)
                return
            voice     = self._voice_combo.currentData() or "Charlotte"
            lang_code = "fr" if voice in ELEVENLABS_VOICES_FR else "en"
            label     = voice
            self._tts_worker = ElevenLabsWorker(
                text, voice=voice, language_code=lang_code, label=label
            )
            mode_label = "ElevenLabs"

        self._tts_worker.progress.connect(self._on_progress)
        self._tts_worker.finished.connect(lambda p: self._on_done(p, label, mode_label))
        self._tts_worker.failed.connect(self._on_failed)
        self._tts_worker.start()

    def _on_progress(self, pct: int, msg: str):
        self._progress.setValue(pct)
        self._lbl_status.setText(translate(msg))

    def _on_done(self, path: str, label: str, mode: str):
        self._btn_generate.setEnabled(True)
        self._progress.setValue(100)
        self._lbl_status.setText("✓  Audio généré avec succès" if path else "✓  Terminé (mode mock)")

        if path:
            self._add_result(path, label, mode)

    def _on_failed(self, error: str):
        self._btn_generate.setEnabled(True)
        self._progress.setVisible(False)
        self._lbl_status.setVisible(False)
        show_api_error(self, error)

    def _add_result(self, path: str, label: str, mode: str):
        if self._lbl_empty_results.isVisible():
            self._lbl_empty_results.setVisible(False)
        card = _AudioCard(path, label, mode)
        self._results.append({"path": path, "label": label, "mode": mode})
        self._results_container.insertWidget(0, card)

    def _clear_results(self):
        self._results.clear()
        while self._results_container.count():
            it = self._results_container.takeAt(0)
            if it.widget() and it.widget() is not self._lbl_empty_results:
                it.widget().deleteLater()
        self._lbl_empty_results.setVisible(True)
        self._results_container.addWidget(self._lbl_empty_results)

    # ── Panneau assignation voix aux personnages ──────────────────────────────

    def _build_voice_assign_panel(self):
        hdr_row = QHBoxLayout()
        hdr_lbl = QLabel("VOIX ASSIGNÉES AUX PERSONNAGES")
        hdr_lbl.setStyleSheet(
            f"color:{CP['text_secondary']};font-size:10px;font-weight:700;"
            f"letter-spacing:3px;font-family:'Consolas',monospace;background:transparent;"
        )
        hdr_row.addWidget(hdr_lbl)
        hdr_row.addStretch()
        self._content_lay.addLayout(hdr_row)

        self._assign_container = QVBoxLayout()
        self._assign_container.setSpacing(8)
        self._assign_container.setAlignment(Qt.AlignmentFlag.AlignTop)

        self._lbl_no_chars = QLabel("Aucun personnage dans ce projet.")
        self._lbl_no_chars.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._lbl_no_chars.setStyleSheet(
            f"color:{CP['text_dim']};font-size:12px;padding:16px;"
            f"background:transparent;"
        )
        self._assign_container.addWidget(self._lbl_no_chars)
        self._content_lay.addLayout(self._assign_container)
        self._refresh_assign_panel()

    def _refresh_assign_panel(self):
        while self._assign_container.count():
            it = self._assign_container.takeAt(0)
            if it.widget():
                it.widget().deleteLater()

        try:
            import core.casting as casting_api
            chars = casting_api.list_characters()
        except Exception:
            chars = []

        if not chars:
            self._lbl_no_chars = QLabel("Aucun personnage dans ce projet.")
            self._lbl_no_chars.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self._lbl_no_chars.setStyleSheet(
                f"color:{CP['text_dim']};font-size:12px;padding:16px;"
                f"background:transparent;"
            )
            self._assign_container.addWidget(self._lbl_no_chars)
            return

        for char in chars:
            self._assign_container.addWidget(self._make_assign_card(char))

    def _make_assign_card(self, char: dict) -> QFrame:
        card = QFrame()
        card.setStyleSheet(
            f"QFrame{{background:{CP['bg2']};border:1px solid {CP['border']};"
            f"border-radius:10px;}}"
        )
        lay = QHBoxLayout(card)
        lay.setContentsMargins(14, 10, 14, 10)
        lay.setSpacing(12)

        # Miniature personnage
        thumb = QLabel()
        thumb.setFixedSize(44, 44)
        thumb.setAlignment(Qt.AlignmentFlag.AlignCenter)
        img = char.get("image_path", "") or char.get("portrait_path", "")
        if img and os.path.isfile(img):
            from PyQt6.QtGui import QPixmap as _QP
            pix = _QP(img).scaled(
                44, 44,
                Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                Qt.TransformationMode.SmoothTransformation,
            )
            thumb.setPixmap(pix)
            thumb.setStyleSheet("border-radius:8px;border:none;background:transparent;")
        else:
            thumb.setText("🎭")
            thumb.setStyleSheet(
                f"background:{CP['bg3']};border-radius:8px;border:none;"
                f"font-size:20px;"
            )
        lay.addWidget(thumb)

        # Nom + voix assignée
        info = QVBoxLayout()
        info.setSpacing(2)
        name_lbl = QLabel(char.get("name", "Personnage"))
        name_lbl.setStyleSheet(
            f"color:{CP['text_primary']};font-size:12px;font-weight:700;"
            f"background:transparent;border:none;"
        )
        info.addWidget(name_lbl)

        voice_path = char.get("doublage_voice", "")
        if voice_path and os.path.isfile(voice_path):
            voice_lbl = QLabel(f"🎙  {os.path.basename(voice_path)}")
            voice_lbl.setStyleSheet(
                f"color:{CP['accent']};font-size:10px;font-family:'Consolas',monospace;"
                f"background:transparent;border:none;"
            )
        else:
            voice_lbl = QLabel("Aucune voix assignée")
            voice_lbl.setStyleSheet(
                f"color:{CP['text_dim']};font-size:10px;font-family:'Consolas',monospace;"
                f"background:transparent;border:none;"
            )
        info.addWidget(voice_lbl)
        lay.addLayout(info, 1)

        # Bouton Assigner
        btn_assign = _btn("🎙  Assigner", CP["accent2"], h=30)
        btn_assign.setFixedWidth(100)
        btn_assign.clicked.connect(lambda _, c=char: self._on_assign_voice(c))
        lay.addWidget(btn_assign)

        # Bouton Retirer (visible seulement si voix assignée)
        if voice_path and os.path.isfile(voice_path):
            btn_remove = _btn("✕", CP["red"] if CP.get("red") else "#e05c5c", h=30)
            btn_remove.setFixedWidth(32)
            btn_remove.setToolTip("Retirer la voix assignée")
            btn_remove.clicked.connect(lambda _, c=char: self._on_remove_voice(c))
            lay.addWidget(btn_remove)

        return card

    def _on_assign_voice(self, char: dict):
        from core.context import get_data_root
        import core.casting as casting_api
        doublage_dir = os.path.join(get_data_root(), "doublage")
        path, _ = QFileDialog.getOpenFileName(
            self, f"Assigner une voix à {char.get('name', '')}",
            doublage_dir if os.path.isdir(doublage_dir) else os.path.expanduser("~"),
            "Audio (*.mp3 *.wav *.m4a *.aac *.ogg);;Tous (*.*)",
        )
        if not path:
            return
        char["doublage_voice"] = path
        casting_api.save_character(char)
        self._refresh_assign_panel()

    def _on_remove_voice(self, char: dict):
        import core.casting as casting_api
        char["doublage_voice"] = ""
        casting_api.save_character(char)
        self._refresh_assign_panel()

    def refresh(self):
        self._refresh_assign_panel()
