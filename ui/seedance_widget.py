from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QTabWidget,
)
from PyQt6.QtCore import Qt, QTimer
from ui.icons import load_icon
from ui.styles import C, STYLESHEET
from ui.tab_t2v import TabT2V
from ui.tab_history import TabHistory
from ui.tab_video_engines import TabVideoEngines
from ui.tab_davinci_edit import TabDavinciEdit
from ui.tab_video_library import TabVideoLibrary


class SeedanceHeader(QWidget):
    def __init__(self):
        super().__init__()
        self.setFixedHeight(52)
        self.setStyleSheet(f"background:{C['bg1']};border-bottom:1px solid {C['border']};")
        lay = QHBoxLayout(self)
        lay.setContentsMargins(20, 0, 20, 0)

        icon = QLabel()
        icon.setFixedSize(28, 28)
        icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        _ico_pix = load_icon("seedance.png", 20)
        if not _ico_pix.isNull():
            icon.setPixmap(_ico_pix)
            icon.setStyleSheet(
                f"background:{C['accent']};border-radius:6px;padding:4px;"
            )
        else:
            icon.setText("✦")
            icon.setStyleSheet(
                f"background:{C['accent']};border-radius:6px;font-size:14px;padding:4px 6px;"
            )

        col = QVBoxLayout()
        col.setSpacing(1)
        name = QLabel("STUDIO IA")
        name.setStyleSheet(
            f"color:{C['text_primary']};font-size:13px;font-weight:700;letter-spacing:1px;"
        )
        sub = QLabel("Génération vidéo IA — fal.ai")
        sub.setStyleSheet(
            f"color:{C['text_dim']};font-size:9px;font-family:'Consolas',monospace;letter-spacing:1px;"
        )
        col.addWidget(name)
        col.addWidget(sub)

        self._dot = QLabel("●")
        self._dot.setStyleSheet(f"color:{C['green']};font-size:10px;")
        self._on = True
        t = QTimer(self)
        t.timeout.connect(self._blink)
        t.start(900)

        lay.addWidget(icon)
        lay.addSpacing(10)
        lay.addLayout(col)
        lay.addStretch()
        lay.addWidget(self._dot)

    def _blink(self):
        self._on = not self._on
        alpha = "ff" if self._on else "44"
        self._dot.setStyleSheet(f"color:{C['green']}{alpha};font-size:10px;")


class SeedanceWidget(QWidget):
    """Contenu complet Studio IA — embarquable dans PandoraWindow."""

    def __init__(self):
        super().__init__()
        self.setStyleSheet(STYLESHEET)

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        self.tabs = QTabWidget()
        self.tabs.setDocumentMode(True)

        self.tab_t2v      = TabT2V()
        self.tab_davinci  = TabDavinciEdit()
        self.tab_engines  = TabVideoEngines()
        self.tab_history  = TabHistory()
        self.tab_library  = TabVideoLibrary()

        self.tabs.addTab(self.tab_t2v,     "Générer depuis Storyboard")
        self.tabs.addTab(self.tab_davinci, "Modifier des clips")
        self.tabs.addTab(self.tab_engines, "Génération directe")
        self.tabs.addTab(self.tab_library, "Vidéothèque")
        self.tabs.addTab(self.tab_history, "Historique")

        self.tab_t2v.generation_done.connect(self.tab_history.add_entry)
        self.tab_davinci.generation_done.connect(self.tab_history.add_entry)

        # Vidéothèque → Modifier depuis DaVinci
        self.tab_library.send_to_davinci_edit.connect(self._on_send_to_edit)

        # Ping bridge quand l'onglet "Modifier depuis DaVinci" devient actif
        # Refresh vidéothèque quand on clique sur l'onglet
        self._davinci_tab_index = self.tabs.indexOf(self.tab_davinci)
        self._library_tab_index = self.tabs.indexOf(self.tab_library)
        self.tabs.currentChanged.connect(self._on_tab_changed)

        root.addWidget(self.tabs)

    def _on_tab_changed(self, index: int):
        if index == self._davinci_tab_index:
            self.tab_davinci._ping_bridge()
        elif index == self._library_tab_index:
            self.tab_library.refresh()

    def _on_send_to_edit(self, paths: list):
        self.tab_davinci.add_clips_from_paths(paths)
        self.tabs.setCurrentWidget(self.tab_davinci)

    def refresh(self):
        self.tab_t2v.refresh()
