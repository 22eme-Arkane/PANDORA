"""
ui/live_studio_widget.py — Studio IA dédié à PANDORA | Live.

Variante du Studio IA pensée pour le live / VJ (distincte de Cinéma) :
  Onglets :
    1. Génération directe       — TabVideoEngines + sélecteur de style VJ (loops)
    2. Générer depuis Séquences — (placeholder, dépend de l'onglet Séquences)
    3. Vidéothèque              — TabVideoLibraryLive (Lire / Modifier / → Resolume)
    4. Modifier                 — TabModifyLive (modifie un clip généré, adapté Live)
    5. Historique               — TabHistory

Différences avec le Studio Cinéma :
  - PAS d'onglet « Générer depuis Storyboard » (casting/décors/accessoires/véhicules)
  - L'onglet « Modifier » est une version Live (sans DaVinci : ni inbox, ni bridge,
    ni import Media Pool). La Vidéothèque y envoie les clips d'un clic.
  - L'envoi vers Resolume se fait via l'onglet Resolume (connexion REST déjà en place,
    voir resolume/client.py + ui/page_live.py). La Vidéothèque y renvoie d'un clic.

Cinéma n'est pas modifié : ce widget est un composant séparé.
"""

from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel, QTabWidget, QScrollArea
from PyQt6.QtCore import Qt, pyqtSignal

from ui.styles import C, STYLESHEET
from core.i18n import translate
from ui.live_pages import TabVideoEnginesLive, TabHistoryLive
from ui.tab_video_library_live import TabVideoLibraryLive
from ui.tab_modify_live import TabModifyLive
from ui.tab_sound_design_live import TabSoundDesignLive
from ui.tab_upscale_live import TabUpscaleLive
from ui.tab_t2v_live import TabT2V as FromSequencesTabLive


# ── Onglet « Générer depuis Séquences » (placeholder) ──────────────────────────

class _FromSequencesTab(QWidget):
    """Placeholder — la génération depuis séquences dépend de l'onglet Séquences
    (modèle de données à construire). Voir ui/page_live_sequences.py."""

    def __init__(self):
        super().__init__()
        self.setStyleSheet(f"background:{C['bg0']};")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(40, 40, 40, 40)
        lay.setSpacing(14)
        lay.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self._icon = QLabel("▤")
        self._icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._icon.setStyleSheet(
            f"color:{C['accent']};font-size:46px;background:transparent;border:none;"
        )
        lay.addWidget(self._icon)

        self._title = QLabel(translate("Générer depuis Séquences"))
        self._title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._title.setStyleSheet(
            f"color:{C['text_primary']};font-size:18px;font-weight:800;"
            f"letter-spacing:1px;background:transparent;border:none;"
        )
        lay.addWidget(self._title)

        self._badge = QLabel(translate("Bientôt disponible"))
        self._badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._badge.setStyleSheet(
            f"color:{C['accent']};font-size:10px;font-weight:700;letter-spacing:2px;"
            f"background:rgba(124,107,255,0.12);border:1px solid rgba(124,107,255,0.30);"
            f"border-radius:10px;padding:5px 14px;"
        )
        lay.addWidget(self._badge, 0, Qt.AlignmentFlag.AlignCenter)

        self._desc = QLabel(translate(
            "Cet onglet générera les loops directement à partir de vos séquences "
            "(onglet Séquences) : choix du segment, du style et du moteur, puis envoi "
            "vers Resolume. Disponible une fois les Séquences construites."
        ))
        self._desc.setWordWrap(True)
        self._desc.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._desc.setMaximumWidth(540)
        self._desc.setStyleSheet(
            f"color:{C['text_secondary']};font-size:12px;line-height:1.5;"
            f"background:transparent;border:none;"
        )
        lay.addWidget(self._desc, 0, Qt.AlignmentFlag.AlignCenter)

    def retranslate(self):
        self._title.setText(translate("Générer depuis Séquences"))
        self._badge.setText(translate("Bientôt disponible"))
        self._desc.setText(translate(
            "Cet onglet générera les loops directement à partir de vos séquences "
            "(onglet Séquences) : choix du segment, du style et du moteur, puis envoi "
            "vers Resolume. Disponible une fois les Séquences construites."
        ))


# ── Studio IA Live ─────────────────────────────────────────────────────────────

class LiveStudioWidget(QWidget):
    """Studio IA du mode Live — génération de loops + envoi vers Resolume."""

    open_resolume = pyqtSignal()   # demande de bascule vers l'onglet Resolume

    def __init__(self):
        super().__init__()
        self.setStyleSheet(STYLESHEET)

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        self.tabs = QTabWidget()
        self.tabs.setDocumentMode(True)

        # 1. Génération directe (version Live : outils VJ/Mapping activés dans __init__)
        self.tab_engines = TabVideoEnginesLive()

        # 2. Générer depuis Séquences (adapté de « Générer depuis Storyboard » Cinéma,
        #    avec sélecteur Séquences Live / Mapping)
        self.tab_sequences = FromSequencesTabLive()

        # 3. Vidéothèque (Live, dédiée)
        self.tab_library = TabVideoLibraryLive()

        # 4. Modifier (Live) — pont depuis la Vidéothèque
        self.tab_modify = TabModifyLive()

        # 5. Sound Design (Live) — Mirelo SFX (texte→audio + vidéo→bande-son synchro)
        self.tab_sound = TabSoundDesignLive()

        # 6. Upscaling (Live) — Topaz / SeedVR2, en lot depuis la Vidéothèque
        self.tab_upscale = TabUpscaleLive()
        self.tab_upscale.set_library_provider(self.tab_library.list_all_clips)
        self.tab_modify.set_library_provider(self.tab_library.list_all_clips)

        # 7. Historique (version Live)
        self.tab_history = TabHistoryLive()

        # Lisibilité plein écran (nav en barre basse, retour 2026-06-12) : le
        # contenu des onglets FORMULAIRE est plafonné en largeur et centré —
        # le fond remplit les côtés. La Vidéothèque et l'Historique (galeries /
        # listes) gardent la pleine largeur.
        for _t in (self.tab_sequences, self.tab_engines, self.tab_modify,
                   self.tab_sound, self.tab_upscale):
            self._clamp_content_width(_t)

        # Ordre validé : Séquences d'abord (le cœur du workflow), puis production.
        self.tabs.addTab(self.tab_sequences, translate("Générer depuis Séquences"))
        self.tabs.addTab(self.tab_engines,   translate("Génération directe"))
        self.tabs.addTab(self.tab_modify,    translate("Modifier des clips"))
        self.tabs.addTab(self.tab_sound,     translate("Sound Design"))
        self.tabs.addTab(self.tab_upscale,   translate("Upscaling"))
        self.tabs.addTab(self.tab_library,   translate("Vidéothèque"))
        self.tabs.addTab(self.tab_history,   translate("Historique"))

        # Générations → historique
        self.tab_engines.generation_done.connect(self.tab_history.add_entry)
        self.tab_modify.generation_done.connect(self.tab_history.add_entry)
        self.tab_sequences.generation_done.connect(self.tab_history.add_entry)

        # Pont Vidéothèque → Modifier (Live)
        self.tab_library.send_to_modify.connect(self._on_send_to_modify)
        # Vidéothèque → Resolume (connexion REST gérée par l'onglet Resolume / page_live.py)
        self.tab_library.send_to_resolume.connect(self._on_send_to_resolume)
        # Vidéothèque → Upscaling (Live)
        self.tab_library.send_to_upscale.connect(self._on_send_to_upscale)

        self._library_tab_index   = self.tabs.indexOf(self.tab_library)
        self._sequences_tab_index  = self.tabs.indexOf(self.tab_sequences)
        self.tabs.currentChanged.connect(self._on_tab_changed)

        root.addWidget(self.tabs)

    @staticmethod
    def _clamp_content_width(tab: QWidget, max_w: int = 1360):
        """Plafonne la largeur du CONTENU d'un onglet formulaire et le centre
        (l'onglet lui-même reste pleine largeur, le fond remplit les côtés)."""
        scroll = tab if isinstance(tab, QScrollArea) else tab.findChild(QScrollArea)
        if scroll is not None and scroll.widget() is not None:
            scroll.widget().setMaximumWidth(max_w)
            scroll.setAlignment(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop)

    def _on_tab_changed(self, index: int):
        if index == self._library_tab_index:
            self.tab_library.refresh()
        elif index == self._sequences_tab_index:
            # Recale le namespace sur la séquence sélectionnée + recharge les plans.
            self.tab_sequences.refresh()

    def _on_send_to_modify(self, paths):
        self.tab_modify.add_clips_from_paths(paths)
        self.tabs.setCurrentWidget(self.tab_modify)

    def _on_send_to_resolume(self, _paths):
        # Bascule vers l'onglet Resolume (connexion REST + chargement dans les slots).
        self.open_resolume.emit()

    def _on_send_to_upscale(self, paths):
        self.tab_upscale.add_clips_from_paths(paths)
        self.tabs.setCurrentWidget(self.tab_upscale)

    def open_sound_design(self, prompt: str, duration: float = 10.0):
        """Ouvre l'onglet Sound Design pré-rempli (bouton « ➤ SFX » des Séquences)."""
        self.tab_sound.open_with_prompt(prompt, duration)
        self.tabs.setCurrentWidget(self.tab_sound)

    def refresh(self):
        if hasattr(self.tab_library, "refresh"):
            self.tab_library.refresh()
