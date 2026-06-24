from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QTabWidget, QTabBar,
)
from PyQt6.QtCore import Qt, QTimer, QRect
from PyQt6.QtGui import QPainter, QColor
from ui.icons import load_icon
from ui.styles import C, STYLESHEET
from ui.tab_t2v import TabT2V
from ui.tab_history import TabHistory
from ui.tab_video_engines import TabVideoEngines
from ui.tab_davinci_edit import TabDavinciEdit
from ui.tab_video_library import TabVideoLibrary


class _GroupedTabBar(QTabBar):
    """Barre d'onglets qui peint un TRAIT vertical en fin de groupe — même
    logique de séparation que le dashboard du bas (groupes séparés par un trait).
    """

    def __init__(self):
        super().__init__()
        self._group_ends: set[int] = set()   # index du DERNIER onglet de chaque groupe

    def set_group_ends(self, ends):
        self._group_ends = {i for i in ends if i >= 0}
        self.update()

    def paintEvent(self, e):
        super().paintEvent(e)
        if not self._group_ends:
            return
        p = QPainter(self)
        col = QColor(255, 255, 255, 28)   # discret, comme les _vsep du dashboard
        for i in self._group_ends:
            if i >= self.count() - 1 or i >= self.count():
                continue   # pas de trait après le tout dernier onglet
            r = self.tabRect(i)
            if not r.isValid():
                continue
            h = int(r.height() * 0.5)
            y = r.center().y() - h // 2
            p.fillRect(QRect(r.right() + 4, y, 1, h), col)
        p.end()


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
        # documentMode=False : sinon la barre d'onglets occupe toute la largeur et
        # « alignment:center » n'a aucun effet (onglets collés à gauche).
        self.tabs.setDocumentMode(False)
        # Onglets CENTRÉS dans la fenêtre (esprit du dashboard du bas)
        self.tabs.setStyleSheet(
            self.tabs.styleSheet() + "QTabWidget::pane{border:none;}"
            "QTabWidget::tab-bar{alignment:center;}")
        # Barre d'onglets GROUPÉE (trait vertical entre groupes, façon dashboard).
        self.tabs.setTabBar(_GroupedTabBar())
        self.tabs.tabBar().setExpanding(False)
        # Un seul trait en haut (celui de la topbar) : le documentMode dessine
        # sa propre ligne de base sous la barre d'onglets → trait DOUBLÉ
        # (refonte 2026-06-12, portée depuis Live)
        self.tabs.tabBar().setDrawBase(False)

        from ui.tab_sound_design import TabSoundDesign
        from ui.tab_upscale import TabUpscale
        from ui.tab_music import TabMusic
        from ui.tab_image import TabImage

        self.tab_t2v      = TabT2V()
        self.tab_davinci  = TabDavinciEdit()
        self.tab_engines  = TabVideoEngines()
        self.tab_sound    = TabSoundDesign()
        self.tab_music    = TabMusic()
        self.tab_image    = TabImage()
        self.tab_upscale  = TabUpscale()
        self.tab_history  = TabHistory()
        self.tab_library  = TabVideoLibrary()

        # Upscaling relié à la Vidéothèque (« Importer la Vidéothèque »)
        self.tab_upscale.set_library_provider(self.tab_library.list_all_clips)

        # Lisibilité plein écran (nav en barre basse) : le contenu des onglets
        # FORMULAIRE est plafonné en largeur et centré — le fond remplit les
        # côtés. Vidéothèque et Historique (galeries/listes) gardent la pleine
        # largeur.
        for _t in (self.tab_t2v, self.tab_davinci, self.tab_engines,
                   self.tab_sound, self.tab_music, self.tab_upscale):
            self._clamp_content_width(_t)

        # Onglets groupés (2026-06-15) — un trait vertical sépare chaque groupe,
        # comme le dashboard du bas :
        #   1. VIDÉO    : Storyboard · Modifier · Génération directe · Upscaling
        #   2. AUDIO    : Sound Design · Musique IA
        #   3. IMAGE    : Image IA
        #   4. ARCHIVES : Vidéothèque · Historique
        self.tabs.addTab(self.tab_t2v,     "Générer depuis Storyboard")   # 0
        self.tabs.addTab(self.tab_davinci, "Modifier des clips")          # 1
        self.tabs.addTab(self.tab_engines, "Génération directe")          # 2
        self.tabs.addTab(self.tab_upscale, "Upscaling")                   # 3 ─ fin G1
        self.tabs.addTab(self.tab_sound,   "Sound Design")                # 4
        self.tabs.addTab(self.tab_music,   "Musique IA")                  # 5 ─ fin G2
        self.tabs.addTab(self.tab_image,   "Image IA")                    # 6 ─ fin G3
        self.tabs.addTab(self.tab_library, "Vidéothèque")                 # 7
        self.tabs.addTab(self.tab_history, "Historique")                  # 8

        # Traits de groupe après Upscaling (3), Musique IA (5) et Image IA (6)
        self.tabs.tabBar().set_group_ends({3, 5, 6})

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

    @staticmethod
    def _clamp_content_width(tab: QWidget, max_w: int = 1360):
        """Plafonne la largeur du CONTENU d'un onglet formulaire et le centre
        (l'onglet lui-même reste pleine largeur, le fond remplit les côtés)."""
        from PyQt6.QtWidgets import QScrollArea
        from PyQt6.QtCore import Qt as _Qt
        scroll = tab if isinstance(tab, QScrollArea) else tab.findChild(QScrollArea)
        if scroll is not None and scroll.widget() is not None:
            scroll.widget().setMaximumWidth(max_w)
            scroll.setAlignment(_Qt.AlignmentFlag.AlignHCenter | _Qt.AlignmentFlag.AlignTop)

    def _on_tab_changed(self, index: int):
        if index == self._davinci_tab_index:
            self.tab_davinci._ping_bridge()
        elif index == self._library_tab_index:
            self.tab_library.refresh()
        elif self.tabs.widget(index) is self.tab_sound:
            # Le conducteur du Sound Design suit le storyboard courant.
            self.tab_sound.refresh()

    def _on_send_to_edit(self, paths: list):
        self.tab_davinci.add_clips_from_paths(paths)
        self.tabs.setCurrentWidget(self.tab_davinci)

    def refresh(self):
        self.tab_t2v.refresh()
