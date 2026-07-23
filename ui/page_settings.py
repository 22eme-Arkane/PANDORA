import os
import webbrowser
from PyQt6.QtWidgets import (
    QScrollArea, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QLineEdit, QPushButton, QMessageBox, QComboBox,
)
from PyQt6.QtCore import Qt, pyqtSignal
from ui.styles import CP
from ui.icons import load_icon
from ui.davinci_panel import DaVinciPanel
from core.config import load_config, save_config
from davinci.bridge import install_pandora_send

_FAL_KEYS_URL       = "https://fal.ai/dashboard/keys"
_ANTHROPIC_KEYS_URL = "https://console.anthropic.com/settings/keys"
_OPENAI_KEYS_URL    = "https://platform.openai.com/api-keys"
_MISTRAL_KEYS_URL   = "https://console.mistral.ai/api-keys"
_KIMI_KEYS_URL      = "https://platform.moonshot.ai/console/api-keys"
_GLM_KEYS_URL       = "https://bigmodel.cn/usercenter/apikeys"


def _section(text: str) -> QLabel:
    lbl = QLabel(text.upper())
    lbl.setStyleSheet(
        f"color:{CP['accent']};font-size:9px;font-weight:700;"
        f"letter-spacing:3px;font-family:'Consolas',monospace;"
        f"background:transparent;"
    )
    return lbl


def _divider() -> QWidget:
    d = QWidget()
    d.setFixedHeight(1)
    d.setStyleSheet(f"background:{CP['border']};")
    return d


def _field_style():
    return (
        f"QLineEdit{{background:{CP['bg2']};border:1px solid {CP['border']};"
        f"border-radius:6px;color:{CP['text_primary']};"
        f"font-size:12px;font-family:'Consolas',monospace;padding:8px 12px;}}"
        f"QLineEdit:focus{{border-color:{CP['accent_dim']};}}"
    )


def _info_btn(tooltip: str, callback) -> QPushButton:
    # « ? » bien visible (l'ancien glyphe ⓘ ne se rendait pas → rond vide,
    # personne ne comprenait que c'était un bouton d'aide — retour 2026-06-13)
    btn = QPushButton("?")
    btn.setFixedSize(24, 24)
    btn.setToolTip(tooltip)
    btn.setCursor(Qt.CursorShape.PointingHandCursor)
    btn.setStyleSheet(
        f"QPushButton{{background:rgba(78,205,196,0.10);color:{CP['accent']};"
        f"border:1px solid {CP['accent_dim']};border-radius:12px;"
        f"font-size:13px;font-weight:900;}}"
        f"QPushButton:hover{{color:#07080f;background:{CP['accent']};"
        f"border-color:{CP['accent']};}}"
    )
    btn.clicked.connect(callback)
    return btn


def _test_btn(label: str, callback) -> QPushButton:
    """Bouton « Tester API… » — même style bleu que les liens « Obtenir une clé »."""
    btn = QPushButton(label)
    btn.setFixedHeight(26)
    btn.setCursor(Qt.CursorShape.PointingHandCursor)
    btn.setStyleSheet(
        f"QPushButton{{background:transparent;color:{CP['accent2']};"
        f"border:1px solid {CP['accent2_dim']};border-radius:6px;"
        f"font-size:10px;font-weight:700;padding:0 10px;}}"
        f"QPushButton:hover{{background:rgba(124,107,255,0.12);color:#9d8fff;}}"
    )
    btn.clicked.connect(callback)
    return btn


def _link_btn(label: str, url: str) -> QPushButton:
    btn = QPushButton(label)
    btn.setFixedHeight(26)
    btn.setCursor(Qt.CursorShape.PointingHandCursor)
    btn.setStyleSheet(
        f"QPushButton{{background:transparent;color:{CP['accent2']};"
        f"border:1px solid {CP['accent2_dim']};border-radius:6px;"
        f"font-size:10px;font-weight:700;padding:0 10px;}}"
        f"QPushButton:hover{{background:rgba(124,107,255,0.12);color:#9d8fff;}}"
    )
    btn.clicked.connect(lambda: webbrowser.open(url))
    return btn


def _badge(text: str, kind: str) -> QLabel:
    """Pastille « Obligatoire » (rouge) ou « Facultatif » (bleu) — contour, pas
    d'opacité hex (rend mal sur fond sombre)."""
    col = CP.get("red", "#ff4f6a") if kind == "req" else CP["accent2"]
    b = QLabel(text)
    b.setFixedHeight(18)
    b.setStyleSheet(
        f"color:{col};background:transparent;border:1px solid {col};"
        f"border-radius:5px;font-size:8px;font-weight:700;padding:1px 6px;"
    )
    return b


class SettingsPage(QScrollArea):
    manual_requested = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.setWidgetResizable(True)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setStyleSheet(f"background:{CP['bg0']};border:none;")

        # Le contenu est CENTRÉ (largeur max 1360) à l'intérieur du scroll : la
        # zone de défilement occupe toute la largeur de la fenêtre, donc sa barre
        # est collée au bord droit (demande Matthieu 2026-07-22).
        content = QWidget()
        content.setStyleSheet(f"background:{CP['bg0']};")
        content.setMaximumWidth(1360)

        container = QWidget()
        container.setStyleSheet(f"background:{CP['bg0']};")
        _center = QHBoxLayout(container)
        _center.setContentsMargins(0, 0, 0, 0)
        _center.setSpacing(0)
        _center.addStretch(1)
        _center.addWidget(content, 4)
        _center.addStretch(1)
        self.setWidget(container)

        lay = QVBoxLayout(content)
        lay.setContentsMargins(32, 28, 32, 32)
        lay.setSpacing(20)

        # ── Titre ─────────────────────────────────────────────────────────────
        _title_row = QHBoxLayout()
        _title_row.setSpacing(10)
        _title_row.setContentsMargins(0, 0, 0, 0)
        _ico = QLabel()
        _ico.setFixedSize(28, 28)
        _ico.setAlignment(Qt.AlignmentFlag.AlignCenter)
        _ico.setStyleSheet("background:transparent;")
        _ico_pix = load_icon("settings.png", 28)
        if not _ico_pix.isNull():
            _ico.setPixmap(_ico_pix)
        _title_row.addWidget(_ico)
        title = QLabel("Paramètres")
        title.setStyleSheet(
            f"color:{CP['text_primary']};font-size:20px;font-weight:700;"
            f"letter-spacing:1px;background:transparent;"
        )
        _title_row.addWidget(title)
        _title_row.addStretch()
        lay.addLayout(_title_row)
        lay.addWidget(_divider())

        # ── Apparence ─────────────────────────────────────────────────────────
        lay.addWidget(_section("Apparence"))

        _appear_row = QHBoxLayout()
        _appear_row.setSpacing(8)

        _cfg_now = load_config()
        _theme_now = _cfg_now.get("theme", "dark")

        _ss_theme_active = (
            f"QPushButton{{background:{CP['accent']};color:#07080f;"
            f"border:none;border-radius:7px;font-size:12px;font-weight:700;"
            f"padding:0 18px;}}"
            f"QPushButton:hover{{background:{CP['accent_dim']};color:#fff;}}"
        )
        _ss_theme_inactive = (
            f"QPushButton{{background:transparent;color:{CP['text_secondary']};"
            f"border:1px solid {CP['border']};border-radius:7px;"
            f"font-size:12px;font-weight:600;padding:0 18px;}}"
            f"QPushButton:hover{{background:{CP['bg3']};color:{CP['text_primary']};}}"
        )

        self._btn_dark  = QPushButton("◐  Sombre")
        self._btn_light = QPushButton("◑  Clair")
        self._btn_dark.setFixedHeight(36)
        self._btn_light.setFixedHeight(36)
        self._btn_dark.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_light.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_dark.setStyleSheet(
            _ss_theme_active if _theme_now == "dark" else _ss_theme_inactive
        )
        self._btn_light.setStyleSheet(
            _ss_theme_active if _theme_now == "light" else _ss_theme_inactive
        )

        def _set_theme(theme: str):
            cfg = load_config()
            cfg["theme"] = theme
            save_config(cfg)
            self._btn_dark.setStyleSheet(
                _ss_theme_active if theme == "dark" else _ss_theme_inactive
            )
            self._btn_light.setStyleSheet(
                _ss_theme_active if theme == "light" else _ss_theme_inactive
            )
            QMessageBox.information(
                self, "Thème enregistré",
                "Le nouveau thème sera appliqué au prochain démarrage de PANDORA."
            )

        self._btn_dark.clicked.connect(lambda: _set_theme("dark"))
        self._btn_light.clicked.connect(lambda: _set_theme("light"))

        _appear_row.addWidget(self._btn_dark)
        _appear_row.addWidget(self._btn_light)
        _appear_row.addStretch()
        lay.addLayout(_appear_row)

        _lbl_theme = QLabel("Le changement de thème est appliqué au prochain démarrage.")
        _lbl_theme.setStyleSheet(
            f"color:{CP['text_dim']};font-size:10px;background:transparent;"
        )
        lay.addWidget(_lbl_theme)

        _lbl_light_note = QLabel(
            "L'application est optimisée pour une apparence sombre.  "
            "Si vous constatez des problèmes d'affichage en mode clair, "
            "contactez 22eme.arkane@gmail.com"
        )
        _lbl_light_note.setWordWrap(True)
        _lbl_light_note.setStyleSheet(
            f"color:{CP['text_dim']};font-size:10px;font-style:italic;background:transparent;"
        )
        lay.addWidget(_lbl_light_note)

        # ── Double écran (P5) — ouvrir une 2ᵉ fenêtre déplaçable ──────────────
        _screen_row = QHBoxLayout()
        _screen_row.setSpacing(8)
        self._btn_second_window = QPushButton("🖥  Ouvrir une 2ᵉ fenêtre (2 écrans)")
        self._btn_second_window.setFixedHeight(36)
        self._btn_second_window.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_second_window.setStyleSheet(_ss_theme_inactive)
        self._btn_second_window.clicked.connect(self._open_second_window)
        _screen_row.addWidget(self._btn_second_window)
        _screen_row.addStretch()
        lay.addLayout(_screen_row)

        _lbl_screen = QLabel(
            "Ouvre une copie de PANDORA sur le même projet, à déplacer sur un 2ᵉ écran. "
            "Chaque fenêtre a sa propre navigation (ex. Storyboard à droite pendant "
            "l'écriture du Scénario à gauche). Évitez de modifier la même page dans les "
            "deux fenêtres en même temps."
        )
        _lbl_screen.setWordWrap(True)
        _lbl_screen.setStyleSheet(
            f"color:{CP['text_dim']};font-size:10px;background:transparent;"
        )
        lay.addWidget(_lbl_screen)

        _manual_row = QHBoxLayout()
        self._btn_manual = QPushButton("☰  Manuel d'utilisation")
        self._btn_manual.setFixedHeight(36)
        self._btn_manual.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_manual.setStyleSheet(_ss_theme_inactive)
        self._btn_manual.clicked.connect(self.manual_requested)
        _manual_row.addWidget(self._btn_manual)
        _manual_row.addStretch()
        lay.addLayout(_manual_row)
        lay.addWidget(_divider())

        cfg = load_config()

        # ── Assistant IA (texte) — juste après l'Apparence (retour 2026-06-13) ─
        lay.addWidget(_section("Assistant IA"))
        _lbl_ai = QLabel(
            "Moteur IA des fonctions texte et d'analyse visuelle : prompts, scénario, "
            "arrangement, storyboard et assistant. Les profils optimisés choisissent "
            "automatiquement le meilleur modèle de leur famille pour chaque tâche."
        )
        _lbl_ai.setWordWrap(True)
        _lbl_ai.setStyleSheet(
            f"color:{CP['text_secondary']};font-size:12px;background:transparent;"
        )
        lay.addWidget(_lbl_ai)

        self.ai_combo = QComboBox()
        self.ai_combo.setFixedHeight(34)
        self.ai_combo.setStyleSheet(
            f"QComboBox{{background:{CP['bg2']};border:1px solid {CP['border']};"
            f"border-radius:8px;color:{CP['text_primary']};font-size:12px;padding:0 10px;}}"
            f"QComboBox::drop-down{{border:none;width:22px;}}"
            f"QComboBox QAbstractItemView{{background:{CP['bg3']};"
            f"border:1px solid {CP['border_bright']};color:{CP['text_primary']};"
            f"selection-background-color:{CP['accent_dim']};}}"
        )
        from ui.ai_model_selector import populate_primary
        populate_primary(self.ai_combo, cfg)
        self.ai_combo.currentIndexChanged.connect(self._on_ai_choice_changed)
        lay.addWidget(self.ai_combo)

        self._btn_refresh_ai_models = QPushButton("Actualiser les modèles accessibles")
        self._btn_refresh_ai_models.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_refresh_ai_models.setStyleSheet(
            f"QPushButton{{background:transparent;color:{CP['accent2']};border:1px solid {CP['border']};"
            f"border-radius:7px;padding:6px 10px;text-align:left;}}"
            f"QPushButton:hover{{border-color:{CP['accent2']};}}"
        )
        self._btn_refresh_ai_models.clicked.connect(self._refresh_ai_models)
        # Bouton RETIRÉ de l'affichage (demande Matthieu 2026-07-22) : la
        # découverte des modèles se déclenche automatiquement au changement
        # d'assistant. Le widget reste vivant : start_model_discovery écrit son
        # état dedans pendant la découverte.
        self._btn_refresh_ai_models.setParent(self)
        self._btn_refresh_ai_models.hide()

        # Champs spécifiques aux fournisseurs alternatifs (visibles selon le choix).
        # Les CLÉS (OpenAI, Mistral) vivent dans la section « Clés API » plus bas
        # pour rester accessibles même quand on règle un moteur PAR TÂCHE.
        self.ollama_url_input = QLineEdit()
        self.ollama_url_input.setPlaceholderText("URL Ollama (défaut : http://localhost:11434)")
        self.ollama_url_input.setText(cfg.get("ollama_url", ""))
        self.ollama_url_input.setStyleSheet(_field_style())
        lay.addWidget(self.ollama_url_input)

        self.ollama_model_input = QLineEdit()
        self.ollama_model_input.setPlaceholderText("Modèle Ollama (défaut : llama3.1)")
        self.ollama_model_input.setText(cfg.get("ollama_model", ""))
        self.ollama_model_input.setStyleSheet(_field_style())
        lay.addWidget(self.ollama_model_input)

        # Champs Kimi (Moonshot) — visibles quand le moteur Kimi est choisi. L'URL de
        # base sert d'aiguillage API↔local : cloud Moonshot par défaut, ou un serveur
        # local OpenAI-compatible (ex. http://localhost:11434/v1 pour Ollama).
        self.kimi_url_input = QLineEdit()
        self.kimi_url_input.setPlaceholderText(
            "URL Kimi (défaut : https://api.moonshot.ai/v1 — ou serveur local /v1)")
        self.kimi_url_input.setText(cfg.get("kimi_url", ""))
        self.kimi_url_input.setStyleSheet(_field_style())
        lay.addWidget(self.kimi_url_input)

        self.kimi_model_input = QLineEdit()
        self.kimi_model_input.setPlaceholderText("Modèle Kimi (défaut : kimi-k2.7-code)")
        self.kimi_model_input.setText(cfg.get("kimi_model", ""))
        self.kimi_model_input.setStyleSheet(_field_style())
        lay.addWidget(self.kimi_model_input)

        # Champs GLM (Zhipu) — visibles quand le moteur GLM est choisi. Même schéma
        # que Kimi : l'URL de base aiguille API cloud ↔ serveur local OpenAI-compatible
        # (ex. http://localhost:11434/v1 pour Ollama, ou un vLLM local).
        self.glm_url_input = QLineEdit()
        self.glm_url_input.setPlaceholderText(
            "URL GLM (défaut : https://open.bigmodel.cn/api/paas/v4 — ou serveur local /v1)")
        self.glm_url_input.setText(cfg.get("glm_url", ""))
        self.glm_url_input.setStyleSheet(_field_style())
        lay.addWidget(self.glm_url_input)

        self.glm_model_input = QLineEdit()
        self.glm_model_input.setPlaceholderText("Modèle GLM (défaut : glm-4.7)")
        self.glm_model_input.setText(cfg.get("glm_model", ""))
        self.glm_model_input.setStyleSheet(_field_style())
        lay.addWidget(self.glm_model_input)

        # Fournisseur OpenAI-compatible libre : vLLM, LM Studio, passerelle privée…
        self.custom_url_input = QLineEdit()
        self.custom_url_input.setPlaceholderText(
            "URL OpenAI-compatible (ex. http://localhost:1234/v1)")
        self.custom_url_input.setText(cfg.get("custom_url", ""))
        self.custom_url_input.setStyleSheet(_field_style())
        lay.addWidget(self.custom_url_input)

        self.custom_model_input = QLineEdit()
        self.custom_model_input.setPlaceholderText("Identifiant exact du modèle personnalisé")
        self.custom_model_input.setText(cfg.get("custom_model", ""))
        self.custom_model_input.setStyleSheet(_field_style())
        lay.addWidget(self.custom_model_input)

        self._lbl_ai_restart = QLabel(
            "Le nom de l'assistant dans l'interface se met à jour au prochain démarrage."
        )
        self._lbl_ai_restart.setWordWrap(True)
        self._lbl_ai_restart.setStyleSheet(
            f"color:{CP['text_dim']};font-size:10px;font-style:italic;background:transparent;"
        )
        # Légende RETIRÉE de l'affichage avec le bouton (2026-07-22).
        self._lbl_ai_restart.setParent(self)
        self._lbl_ai_restart.hide()

        # ── Paramètres avancés : moteur IA PAR TÂCHE (repliable) ───────────────
        self._adv_open = False
        self._btn_adv = QPushButton("▶  Paramètres avancés — moteur IA par tâche")
        self._btn_adv.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_adv.setStyleSheet(
            f"QPushButton{{background:transparent;color:{CP['accent2']};"
            f"border:none;text-align:left;font-size:11px;font-weight:700;padding:4px 0;}}"
            f"QPushButton:hover{{color:#9d8fff;}}"
        )
        self._btn_adv.clicked.connect(self._toggle_advanced)
        lay.addWidget(self._btn_adv)

        self._adv_box = QWidget()
        self._adv_box.setVisible(False)
        self._adv_box.setStyleSheet("background:transparent;")
        adv_lay = QVBoxLayout(self._adv_box)
        adv_lay.setContentsMargins(2, 2, 2, 6)
        adv_lay.setSpacing(8)
        _adv_hint = QLabel(
            "Choisissez un moteur différent selon la tâche. « Par défaut » utilise "
            "le moteur sélectionné ci-dessus ; les clés se renseignent dans « Clés API ». "
            "Les profils Anthropic et ChatGPT restent strictement dans leur famille "
            "de modèles, sans repli silencieux vers un autre fournisseur."
        )
        _adv_hint.setWordWrap(True)
        _adv_hint.setStyleSheet(f"color:{CP['text_dim']};font-size:10px;background:transparent;")
        adv_lay.addWidget(_adv_hint)

        from core.ai_provider import TASKS
        from ui.ai_model_selector import populate_task_engines
        self._task_combos = {}
        _saved_tasks = cfg.get("ai_task_engines") or {}
        for task_key, task_label in TASKS:
            row = QHBoxLayout()
            row.setSpacing(8)
            lbl = QLabel(task_label)
            lbl.setStyleSheet(
                f"color:{CP['text_secondary']};font-size:11px;background:transparent;"
            )
            row.addWidget(lbl, 1)
            combo = QComboBox()
            combo.setFixedHeight(28)
            combo.setMinimumWidth(160)
            combo.setStyleSheet(
                f"QComboBox{{background:{CP['bg2']};border:1px solid {CP['border']};"
                f"border-radius:6px;color:{CP['text_primary']};font-size:11px;padding:0 8px;}}"
                f"QComboBox::drop-down{{border:none;width:20px;}}"
                f"QComboBox QAbstractItemView{{background:{CP['bg3']};"
                f"border:1px solid {CP['border_bright']};color:{CP['text_primary']};"
                f"selection-background-color:{CP['accent_dim']};}}"
            )
            _cur_eng = _saved_tasks.get(task_key, "")
            populate_task_engines(combo, cfg, task_key, _cur_eng)
            self._task_combos[task_key] = combo
            row.addWidget(combo)
            adv_lay.addLayout(row)

        # ── Distribution des générations VIDÉO (distributeur alternatif) ──────
        adv_lay.addSpacing(12)
        _dist_title = QLabel("Distribution des générations vidéo")
        _dist_title.setStyleSheet(
            f"color:{CP['text_secondary']};font-size:11px;font-weight:700;"
            f"background:transparent;"
        )
        adv_lay.addWidget(_dist_title)
        _dist_hint = QLabel(
            "fal.ai reste le distributeur par défaut et le repli automatique. "
            "Un distributeur low cost peut servir les mêmes générations Seedance 2.0 "
            "moins cher — les prix affichés dans le Studio s'adaptent. "
            "⚠ Les images de référence transitent toujours par fal.ai (clé fal "
            "requise dès qu'un plan envoie des images)."
        )
        _dist_hint.setWordWrap(True)
        _dist_hint.setStyleSheet(
            f"color:{CP['text_dim']};font-size:10px;background:transparent;")
        adv_lay.addWidget(_dist_hint)

        from core.media_provider import PROVIDERS as _MEDIA_PROVIDERS
        _combo_style = (
            f"QComboBox{{background:{CP['bg2']};border:1px solid {CP['border']};"
            f"border-radius:6px;color:{CP['text_primary']};font-size:11px;padding:0 8px;}}"
            f"QComboBox::drop-down{{border:none;width:20px;}}"
            f"QComboBox QAbstractItemView{{background:{CP['bg3']};"
            f"border:1px solid {CP['border_bright']};color:{CP['text_primary']};"
            f"selection-background-color:{CP['accent_dim']};}}"
        )
        mode_row = QHBoxLayout()
        mode_row.setSpacing(8)
        _mode_lbl = QLabel("Mode de distribution")
        _mode_lbl.setStyleSheet(
            f"color:{CP['text_secondary']};font-size:11px;background:transparent;")
        mode_row.addWidget(_mode_lbl, 1)
        self.distribution_mode_combo = QComboBox()
        self.distribution_mode_combo.setFixedHeight(28)
        self.distribution_mode_combo.setMinimumWidth(160)
        self.distribution_mode_combo.setStyleSheet(_combo_style)
        self.distribution_mode_combo.addItem(
            "Multi-distributeurs (recommandé)", "multi")
        self.distribution_mode_combo.addItem(
            "Mono-distributeur (uniquement celui choisi)", "mono")
        if cfg.get("distribution_mode", "multi") == "mono":
            self.distribution_mode_combo.setCurrentIndex(1)
        mode_row.addWidget(self.distribution_mode_combo)
        adv_lay.addLayout(mode_row)
        _mode_hint = QLabel(
            "Mono-distributeur : les services que le distributeur choisi ne couvre "
            "pas (Sound Design, Musique IA, Image IA, Upscaling…) sont grisés dans "
            "le Studio au lieu de repasser par fal.ai."
        )
        _mode_hint.setWordWrap(True)
        _mode_hint.setStyleSheet(
            f"color:{CP['text_dim']};font-size:10px;background:transparent;")
        adv_lay.addWidget(_mode_hint)

        prov_row = QHBoxLayout()
        prov_row.setSpacing(8)
        _prov_lbl = QLabel("Distributeur vidéo")
        _prov_lbl.setStyleSheet(
            f"color:{CP['text_secondary']};font-size:11px;background:transparent;")
        prov_row.addWidget(_prov_lbl, 1)
        self.video_provider_combo = QComboBox()
        self.video_provider_combo.setFixedHeight(28)
        self.video_provider_combo.setMinimumWidth(160)
        self.video_provider_combo.setStyleSheet(
            f"QComboBox{{background:{CP['bg2']};border:1px solid {CP['border']};"
            f"border-radius:6px;color:{CP['text_primary']};font-size:11px;padding:0 8px;}}"
            f"QComboBox::drop-down{{border:none;width:20px;}}"
            f"QComboBox QAbstractItemView{{background:{CP['bg3']};"
            f"border:1px solid {CP['border_bright']};color:{CP['text_primary']};"
            f"selection-background-color:{CP['accent_dim']};}}"
        )
        for _pid, _pmeta in _MEDIA_PROVIDERS.items():
            self.video_provider_combo.addItem(_pmeta["label"], _pid)
        _cur_prov = cfg.get("video_provider", "fal")
        for i in range(self.video_provider_combo.count()):
            if self.video_provider_combo.itemData(i) == _cur_prov:
                self.video_provider_combo.setCurrentIndex(i)
                break
        prov_row.addWidget(self.video_provider_combo)
        adv_lay.addLayout(prov_row)

        _piapi_hint = QLabel(
            "La clé PiAPI se renseigne dans « Clés API facultatives » ci-dessous."
        )
        _piapi_hint.setWordWrap(True)
        _piapi_hint.setStyleSheet(
            f"color:{CP['text_dim']};font-size:10px;background:transparent;")
        adv_lay.addWidget(_piapi_hint)
        lay.addWidget(self._adv_box)

        self._on_ai_choice_changed()
        lay.addWidget(_divider())

        # ── Clés API (testeurs à côté des liens « Obtenir une clé ») ──────────
        api_row = QHBoxLayout()
        api_row.addWidget(_section("Clés API"))
        api_row.addStretch()
        api_row.addWidget(_info_btn(
            "Comment obtenir les clés API",
            lambda: self._show_api_help(),
        ))
        lay.addLayout(api_row)

        # ── Clés OBLIGATOIRES (fal.ai + Anthropic, pastille rouge) ────────────
        # fal.ai
        fal_lbl_row = QHBoxLayout()
        fal_lbl_row.setSpacing(8)
        lbl_fal = QLabel(
            "fal.ai — Seedance 2.0 (vidéo)  ·  Nano Banana (portraits, accessoires, HMC)"
        )
        lbl_fal.setStyleSheet(
            f"color:{CP['text_secondary']};font-size:12px;background:transparent;"
        )
        fal_lbl_row.addWidget(lbl_fal, 1)
        fal_lbl_row.addWidget(_badge("Obligatoire", "req"))
        fal_lbl_row.addWidget(_test_btn("✓  Tester API fal.ai", self.test_connection))
        fal_lbl_row.addWidget(_link_btn("⇗  Obtenir une clé fal.ai", _FAL_KEYS_URL))
        lay.addLayout(fal_lbl_row)

        self.api_input = QLineEdit()
        self.api_input.setPlaceholderText("fal_••••••••••••••••••••••••")
        self.api_input.setText(cfg.get("api_key", ""))
        self.api_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.api_input.setStyleSheet(_field_style())
        lay.addWidget(self.api_input)

        # Anthropic
        ant_lbl_row = QHBoxLayout()
        ant_lbl_row.setSpacing(8)
        lbl_ant = QLabel("Anthropic — Claude  (optimisation prompts, scénario, storyboard)")
        lbl_ant.setStyleSheet(
            f"color:{CP['text_secondary']};font-size:12px;background:transparent;"
        )
        ant_lbl_row.addWidget(lbl_ant, 1)
        ant_lbl_row.addWidget(_badge("Obligatoire", "req"))
        ant_lbl_row.addWidget(_test_btn("✓  Tester API Anthropic", self.test_anthropic_connection))
        ant_lbl_row.addWidget(_link_btn("⇗  Obtenir une clé Anthropic", _ANTHROPIC_KEYS_URL))
        lay.addLayout(ant_lbl_row)

        self.anthropic_input = QLineEdit()
        self.anthropic_input.setPlaceholderText("sk-ant-••••••••••••••••••••••••")
        self.anthropic_input.setText(cfg.get("anthropic_key", ""))
        self.anthropic_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.anthropic_input.setStyleSheet(_field_style())
        lay.addWidget(self.anthropic_input)

        # ── Clés FACULTATIVES (menu déroulant : OpenAI, Mistral, à venir) ──────
        self._opt_keys_open = False
        self._btn_opt_keys = QPushButton(
            "▶  Clés API facultatives  (PiAPI, OpenAI, Mistral…)")
        self._btn_opt_keys.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_opt_keys.setStyleSheet(
            f"QPushButton{{background:transparent;color:{CP['accent2']};"
            f"border:none;text-align:left;font-size:11px;font-weight:700;padding:4px 0;}}"
            f"QPushButton:hover{{color:#9d8fff;}}"
        )
        self._btn_opt_keys.clicked.connect(self._toggle_opt_keys)
        lay.addWidget(self._btn_opt_keys)

        self._opt_keys_box = QWidget()
        self._opt_keys_box.setVisible(False)
        self._opt_keys_box.setStyleSheet("background:transparent;")
        opt_lay = QVBoxLayout(self._opt_keys_box)
        opt_lay.setContentsMargins(2, 2, 2, 4)
        opt_lay.setSpacing(8)
        _opt_hint = QLabel(
            "Non requises pour faire fonctionner PANDORA — distributeur vidéo "
            "low cost (PiAPI) ou moteurs d'assistant texte (global ou par tâche)."
        )
        _opt_hint.setWordWrap(True)
        _opt_hint.setStyleSheet(f"color:{CP['text_dim']};font-size:10px;background:transparent;")
        opt_lay.addWidget(_opt_hint)

        # PiAPI — distributeur vidéo low cost (en PREMIER, demande Matthieu
        # 2026-07-16 ; le combo « Distributeur vidéo » reste dans les avancés)
        piapi_lbl_row = QHBoxLayout()
        piapi_lbl_row.setSpacing(8)
        self._piapi_lbl = QLabel(
            "PiAPI — Seedance 2.0 low cost  (distributeur vidéo, voir avancés)")
        self._piapi_lbl.setStyleSheet(
            f"color:{CP['text_secondary']};font-size:12px;background:transparent;")
        piapi_lbl_row.addWidget(self._piapi_lbl, 1)
        piapi_lbl_row.addWidget(_badge("Facultatif", "opt"))
        self._piapi_test_btn = _test_btn("✓  Tester API PiAPI", self.test_piapi_connection)
        piapi_lbl_row.addWidget(self._piapi_test_btn)
        self._piapi_link_btn = _link_btn("⇗  Obtenir une clé PiAPI",
                                         "https://piapi.ai/workspace")
        piapi_lbl_row.addWidget(self._piapi_link_btn)
        opt_lay.addLayout(piapi_lbl_row)

        self.piapi_input = QLineEdit()
        self.piapi_input.setPlaceholderText("Clé PiAPI (X-API-Key)")
        self.piapi_input.setText(cfg.get("piapi_key", ""))
        self.piapi_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.piapi_input.setStyleSheet(_field_style())
        opt_lay.addWidget(self.piapi_input)

        # OpenAI
        oa_lbl_row = QHBoxLayout()
        oa_lbl_row.setSpacing(8)
        lbl_oa = QLabel("OpenAI — GPT-5.6 / GPT-5.5  (assistant, par profil ou par tâche)")
        lbl_oa.setStyleSheet(
            f"color:{CP['text_secondary']};font-size:12px;background:transparent;"
        )
        oa_lbl_row.addWidget(lbl_oa, 1)
        oa_lbl_row.addWidget(_badge("Facultatif", "opt"))
        oa_lbl_row.addWidget(_test_btn("✓  Tester API OpenAI", self.test_openai_connection))
        oa_lbl_row.addWidget(_link_btn("⇗  Obtenir une clé OpenAI", _OPENAI_KEYS_URL))
        opt_lay.addLayout(oa_lbl_row)

        self.openai_input = QLineEdit()
        self.openai_input.setPlaceholderText("sk-••••••••••••••••••••••••")
        self.openai_input.setText(cfg.get("openai_key", ""))
        self.openai_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.openai_input.setStyleSheet(_field_style())
        opt_lay.addWidget(self.openai_input)

        # Mistral
        ms_lbl_row = QHBoxLayout()
        ms_lbl_row.setSpacing(8)
        lbl_ms = QLabel("Mistral  (assistant texte, expérimental)")
        lbl_ms.setStyleSheet(
            f"color:{CP['text_secondary']};font-size:12px;background:transparent;"
        )
        ms_lbl_row.addWidget(lbl_ms, 1)
        ms_lbl_row.addWidget(_badge("Facultatif", "opt"))
        ms_lbl_row.addWidget(_test_btn("✓  Tester API Mistral", self.test_mistral_connection))
        ms_lbl_row.addWidget(_link_btn("⇗  Obtenir une clé Mistral", _MISTRAL_KEYS_URL))
        opt_lay.addLayout(ms_lbl_row)

        self.mistral_input = QLineEdit()
        self.mistral_input.setPlaceholderText("Clé API Mistral")
        self.mistral_input.setText(cfg.get("mistral_key", ""))
        self.mistral_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.mistral_input.setStyleSheet(_field_style())
        opt_lay.addWidget(self.mistral_input)

        # Kimi (Moonshot) — clé facultative (inutile en local)
        km_lbl_row = QHBoxLayout()
        km_lbl_row.setSpacing(8)
        lbl_km = QLabel("Kimi K2.7 (Moonshot)  (assistant texte — API ou local, expérimental)")
        lbl_km.setStyleSheet(
            f"color:{CP['text_secondary']};font-size:12px;background:transparent;"
        )
        km_lbl_row.addWidget(lbl_km, 1)
        km_lbl_row.addWidget(_badge("Facultatif", "opt"))
        km_lbl_row.addWidget(_test_btn("✓  Tester API Kimi", self.test_kimi_connection))
        km_lbl_row.addWidget(_link_btn("⇗  Obtenir une clé Kimi", _KIMI_KEYS_URL))
        opt_lay.addLayout(km_lbl_row)

        self.kimi_input = QLineEdit()
        self.kimi_input.setPlaceholderText("sk-••••••••••••  (vide si serveur local)")
        self.kimi_input.setText(cfg.get("kimi_key", ""))
        self.kimi_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.kimi_input.setStyleSheet(_field_style())
        opt_lay.addWidget(self.kimi_input)

        # GLM (Zhipu) — clé facultative (inutile en local)
        gl_lbl_row = QHBoxLayout()
        gl_lbl_row.setSpacing(8)
        lbl_gl = QLabel("GLM 4.7 (Zhipu)  (assistant texte — API ou local, expérimental)")
        lbl_gl.setStyleSheet(
            f"color:{CP['text_secondary']};font-size:12px;background:transparent;"
        )
        gl_lbl_row.addWidget(lbl_gl, 1)
        gl_lbl_row.addWidget(_badge("Facultatif", "opt"))
        gl_lbl_row.addWidget(_test_btn("✓  Tester API GLM", self.test_glm_connection))
        gl_lbl_row.addWidget(_link_btn("⇗  Obtenir une clé GLM", _GLM_KEYS_URL))
        opt_lay.addLayout(gl_lbl_row)

        self.glm_input = QLineEdit()
        self.glm_input.setPlaceholderText("Clé API GLM  (vide si serveur local)")
        self.glm_input.setText(cfg.get("glm_key", ""))
        self.glm_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.glm_input.setStyleSheet(_field_style())
        opt_lay.addWidget(self.glm_input)

        # Fournisseur OpenAI-compatible personnalisé — clé facultative en local.
        cu_lbl_row = QHBoxLayout()
        cu_lbl_row.setSpacing(8)
        lbl_cu = QLabel("Fournisseur personnalisé  (API OpenAI-compatible ou serveur local)")
        lbl_cu.setStyleSheet(
            f"color:{CP['text_secondary']};font-size:12px;background:transparent;"
        )
        cu_lbl_row.addWidget(lbl_cu, 1)
        cu_lbl_row.addWidget(_badge("Facultatif", "opt"))
        cu_lbl_row.addWidget(_test_btn("✓  Tester le fournisseur", self.test_custom_connection))
        opt_lay.addLayout(cu_lbl_row)

        self.custom_key_input = QLineEdit()
        self.custom_key_input.setPlaceholderText("Clé API personnalisée  (vide si serveur local)")
        self.custom_key_input.setText(cfg.get("custom_key", ""))
        self.custom_key_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.custom_key_input.setStyleSheet(_field_style())
        opt_lay.addWidget(self.custom_key_input)

        lay.addWidget(self._opt_keys_box)
        lay.addWidget(_divider())

        # ── Sauvegarde AUTOMATIQUE (plus de bouton — tout changement est enregistré) ──
        self._autosave_lbl = QLabel("✓  Sauvegarde automatique — chaque modification est enregistrée.")
        self._autosave_lbl.setStyleSheet(
            f"color:{CP['text_dim']};font-size:11px;font-style:italic;background:transparent;"
        )
        lay.addWidget(self._autosave_lbl)
        lay.addWidget(_divider())

        # Brancher l'auto-save sur tous les champs (après construction complète).
        self._wire_autosave()

        # ── Connexion DaVinci Resolve Studio — tout en bas ────────────────────
        dvr_row = QHBoxLayout()
        dvr_row.setSpacing(8)
        _dvr_title = QLabel("Connexion DaVinci Resolve Studio".upper())
        _dvr_title.setStyleSheet(
            f"color:{CP['text_dim']};font-size:9px;font-weight:700;"
            f"letter-spacing:3px;font-family:'Consolas',monospace;background:transparent;"
        )
        dvr_row.addWidget(_dvr_title)
        _studio_badge = QLabel("Studio uniquement")
        _studio_badge.setStyleSheet(
            f"color:{CP['text_dim']};font-size:9px;font-weight:600;"
            f"background:{CP['bg3']};border:1px solid {CP['border']};"
            f"border-radius:4px;padding:1px 6px;"
        )
        dvr_row.addWidget(_studio_badge)
        dvr_row.addStretch()
        dvr_row.addWidget(_info_btn(
            "Guide de connexion DaVinci Resolve Studio",
            lambda: self._show_davinci_help(),
        ))
        lay.addLayout(dvr_row)

        _lbl_studio_note = QLabel(
            "Fonctionnalité optionnelle — ne fonctionne pas avec DaVinci Resolve (version gratuite/Lite). "
            "Requiert DaVinci Resolve Studio (version payante)."
        )
        _lbl_studio_note.setWordWrap(True)
        _lbl_studio_note.setStyleSheet(
            f"color:{CP['text_dim']};font-size:10px;font-style:italic;background:transparent;"
        )
        lay.addWidget(_lbl_studio_note)

        self._davinci = DaVinciPanel()
        self._davinci.setStyleSheet(
            f"background:{CP['bg2']};border:1px solid {CP['border']};"
            f"border-radius:10px;"
        )
        lay.addWidget(self._davinci)

        # (Le bouton « Installer le script / bridge PANDORA » a été retiré : les
        # scripts DaVinci — pandora_send + seedance_bridge — sont installés
        # AUTOMATIQUEMENT par l'installeur PANDORA. Les instructions restent dans
        # le panneau DaVinci ci-dessus.)
        # (le bouton de vérification de mise à jour a aussi été retiré : il existe
        # déjà en haut à droite de la fenêtre — retour 2026-06-13)
        lay.addStretch()

    def _install_pandora_send(self):
        ok, msg = install_pandora_send()
        if ok:
            QMessageBox.information(
                self, "Script installé",
                f"pandora_send.py installé dans :\n{msg}\n\n"
                "Dans DaVinci Resolve Studio, pour configurer un raccourci clavier :\n\n"
                "  1. Espace de travail → Personnalisation du clavier\n"
                "  2. Dans la barre de recherche, taper « pandora_send »\n"
                "  3. Assigner votre raccourci (ex. Ctrl+Shift+P)\n\n"
                "Le script s'exécute aussi via :\n"
                "DaVinci Resolve Studio → Espace de travail → Scripts → pandora_send",
            )
        else:
            QMessageBox.warning(self, "Erreur", msg)

    # ── Double écran (P5) ──────────────────────────────────────────────────────

    def _open_second_window(self):
        """Demande à la fenêtre PANDORA parente d'ouvrir une 2ᵉ fenêtre (2 écrans)."""
        win = self.window()
        if win is not None and hasattr(win, "open_secondary_window"):
            win.open_secondary_window()
        else:
            QMessageBox.information(
                self, "Indisponible",
                "La 2ᵉ fenêtre ne peut être ouverte que depuis la fenêtre principale."
            )

    # ── Dialogues d'aide ─────────────────────────────────────────────────────

    def _show_davinci_help(self):
        from ui.dialog_davinci_help import DaVinciHelpDialog
        DaVinciHelpDialog(self).exec()

    def _show_api_help(self):
        # Rouvre le guide de démarrage (promis par son écran final) — remplace
        # l'ancienne ApiHelpDialog depuis la refonte 2026-07-16.
        from ui.dialog_onboarding import OnboardingDialog
        OnboardingDialog(parent=self).exec()

    def _on_ai_choice_changed(self, *_):
        """Champs Ollama conditionnels + « Choix personnalisé » ouvre les avancés."""
        from ui.ai_model_selector import selected_primary, selection_provider
        _choice = selected_primary(self.ai_combo)
        prov = selection_provider(self.ai_combo)
        self.ollama_url_input.setVisible(prov == "ollama")
        self.ollama_model_input.setVisible(prov == "ollama")
        self.kimi_url_input.setVisible(prov == "kimi")
        self.kimi_model_input.setVisible(prov == "kimi")
        self.glm_url_input.setVisible(prov == "glm")
        self.glm_model_input.setVisible(prov == "glm")
        self.custom_url_input.setVisible(prov == "custom")
        self.custom_model_input.setVisible(prov == "custom")
        # « Choix personnalisé » et « PANDORA optimisé » déplient le moteur par tâche
        if (_choice.get("profile") in ("custom", "anthropic_optimized", "openai_optimized")
                and not self._adv_open):
            self._set_advanced(True)
        # Appel avec un index = changement réel de l'utilisateur. L'appel sans
        # argument pendant la construction ne doit pas écraser ses overrides sauvés.
        if _ and hasattr(self, "_task_combos"):
            from core.config import load_config
            from ui.ai_model_selector import refresh_task_engines_for_primary
            refresh_task_engines_for_primary(
                self.ai_combo, self._task_combos, load_config())
            # Découverte AUTOMATIQUE des modèles réellement accessibles à chaque
            # changement d'assistant — remplace l'ancien bouton « Actualiser les
            # modèles accessibles » (demande Matthieu 2026-07-22).
            # UNIQUEMENT si la page est visible : les harnais instancient cette
            # page hors écran et changent l'index — sans ce garde, des workers
            # réseau seraient encore vivants à la sortie du processus (abort
            # 0xC0000409 constaté dans tools/test_live.py).
            if self.isVisible():
                self._refresh_ai_models()

    def _set_advanced(self, open_: bool):
        self._adv_open = open_
        self._adv_box.setVisible(open_)
        self._btn_adv.setText(
            ("▼" if open_ else "▶") + "  Paramètres avancés — moteur IA par tâche"
        )

    def _toggle_advanced(self):
        self._set_advanced(not self._adv_open)

    def _refresh_ai_models(self):
        """Interroge les API /models sans bloquer l'interface."""
        self.save()  # les clés/URL visibles deviennent le snapshot de découverte
        from ui.ai_model_selector import start_model_discovery
        start_model_discovery(self, self.ai_combo, self._task_combos,
                              self._btn_refresh_ai_models)

    def test_piapi_connection(self):
        key = self.piapi_input.text().strip()
        if not key:
            QMessageBox.warning(self, "Clé manquante", "Entre ta clé PiAPI d'abord !")
            return
        from api.piapi import test_key
        ok, msg = test_key(key)
        if ok:
            QMessageBox.information(self, "✓ Connexion OK", msg)
        else:
            QMessageBox.critical(self, "Erreur PiAPI", msg)

    def _toggle_opt_keys(self):
        self._opt_keys_open = not self._opt_keys_open
        self._opt_keys_box.setVisible(self._opt_keys_open)
        self._btn_opt_keys.setText(
            ("▼" if self._opt_keys_open else "▶")
            + "  Clés API facultatives  (PiAPI, OpenAI, Mistral…)"
        )

    # ── Sauvegarde ────────────────────────────────────────────────────────────

    def save(self):
        cfg = load_config()
        from ui.ai_model_selector import apply_primary_to_config
        # Moteur PAR TÂCHE : ne garder que les tâches dont le moteur ≠ « Par défaut »
        task_engines = {}
        for task_key, combo in getattr(self, "_task_combos", {}).items():
            eng = combo.currentData()
            if eng:
                task_engines[task_key] = eng
        cfg.update({
            "api_key":           self.api_input.text(),
            "anthropic_key":     self.anthropic_input.text(),
            "openai_key":        self.openai_input.text(),
            "mistral_key":       self.mistral_input.text(),
            "kimi_key":          self.kimi_input.text(),
            "kimi_url":          self.kimi_url_input.text(),
            "kimi_model":        self.kimi_model_input.text(),
            "glm_key":           self.glm_input.text(),
            "glm_url":           self.glm_url_input.text(),
            "glm_model":         self.glm_model_input.text(),
            "custom_key":        self.custom_key_input.text(),
            "custom_url":        self.custom_url_input.text(),
            "custom_model":      self.custom_model_input.text(),
            "ollama_url":        self.ollama_url_input.text(),
            "ollama_model":      self.ollama_model_input.text(),
            "ai_task_engines":   task_engines,
            "video_provider":    self.video_provider_combo.currentData() or "fal",
            "piapi_key":         self.piapi_input.text(),
            "distribution_mode": self.distribution_mode_combo.currentData() or "multi",
        })
        apply_primary_to_config(cfg, self.ai_combo)
        save_config(cfg)
        from core.ai_provider import refresh_name_cache
        refresh_name_cache()   # le nom de l'assistant change → libellés au prochain démarrage
        # Sauvegarde automatique : retour discret (pas de pop-up à chaque frappe)
        if hasattr(self, "_autosave_lbl"):
            self._autosave_lbl.setText("✓  Enregistré automatiquement.")

    def _wire_autosave(self):
        """Sauvegarde automatique : tout changement de champ persiste aussitôt."""
        self.ai_combo.currentIndexChanged.connect(self.save)
        for w in (self.api_input, self.anthropic_input, self.openai_input,
                  self.mistral_input, self.kimi_input, self.kimi_url_input,
                  self.kimi_model_input, self.glm_input, self.glm_url_input,
                  self.glm_model_input, self.ollama_url_input, self.ollama_model_input,
                  self.custom_key_input, self.custom_url_input,
                  self.custom_model_input, self.piapi_input):
            w.textChanged.connect(self.save)
        for combo in getattr(self, "_task_combos", {}).values():
            combo.currentIndexChanged.connect(self.save)
        self.video_provider_combo.currentIndexChanged.connect(self.save)
        self.distribution_mode_combo.currentIndexChanged.connect(self.save)

    def _apply_pandora_preset(self):
        """Renseigne les combos « moteur par tâche » avec le preset PANDORA optimisé."""
        from core.ai_provider import PANDORA_OPTIMIZED
        for task_key, combo in getattr(self, "_task_combos", {}).items():
            eng = PANDORA_OPTIMIZED.get(task_key, "")
            for i in range(combo.count()):
                if combo.itemData(i) == eng:
                    combo.setCurrentIndex(i)
                    break

    def test_anthropic_connection(self):
        key = self.anthropic_input.text().strip()
        if not key:
            QMessageBox.warning(self, "Clé manquante", "Entre ta clé API Anthropic d'abord !")
            return
        try:
            import anthropic
            client = anthropic.Anthropic(api_key=key)
            client.messages.create(
                model="claude-haiku-4-5-20251001",
                max_tokens=5,
                messages=[{"role": "user", "content": "ping"}],
            )
            QMessageBox.information(self, "✓ Connexion OK", "Clé Anthropic valide !")
        except ImportError:
            QMessageBox.warning(
                self, "anthropic manquant",
                "Installe le client :\n\npip install anthropic"
            )
        except Exception as e:
            err = str(e)
            if "401" in err or "authentication" in err.lower() or "invalid" in err.lower():
                QMessageBox.critical(self, "Clé invalide", "La clé API Anthropic est incorrecte.")
            else:
                QMessageBox.critical(self, "Erreur Anthropic", f"Erreur : {err[:200]}")

    def test_openai_connection(self):
        key = self.openai_input.text().strip()
        if not key:
            QMessageBox.warning(self, "Clé manquante", "Entre ta clé API OpenAI d'abord !")
            return
        try:
            import requests
            r = requests.get(
                "https://api.openai.com/v1/models",
                headers={"Authorization": f"Bearer {key}"}, timeout=20,
            )
            if r.status_code == 200:
                QMessageBox.information(self, "✓ Connexion OK", "Clé OpenAI valide !")
            elif r.status_code in (401, 403):
                QMessageBox.critical(self, "Clé invalide", "La clé API OpenAI est incorrecte.")
            else:
                QMessageBox.information(
                    self, "Réponse OpenAI",
                    f"Code {r.status_code}. La clé sera testée à la première génération.")
        except Exception as e:
            QMessageBox.critical(self, "Erreur OpenAI", f"Erreur : {str(e)[:200]}")

    def test_custom_connection(self):
        base = self.custom_url_input.text().strip().rstrip("/")
        key = self.custom_key_input.text().strip()
        if not base:
            QMessageBox.warning(self, "URL manquante",
                                "Entre l'URL du fournisseur OpenAI-compatible.")
            return
        try:
            import requests
            headers = {"Authorization": f"Bearer {key}"} if key else {}
            r = requests.get(f"{base}/models", headers=headers, timeout=20)
            if r.status_code == 200:
                QMessageBox.information(
                    self, "✓ Connexion OK", f"Fournisseur joignable sur {base}.")
            elif r.status_code in (401, 403):
                QMessageBox.critical(self, "Clé invalide",
                                     "La clé du fournisseur personnalisé est refusée.")
            else:
                QMessageBox.information(
                    self, "Réponse du fournisseur",
                    f"Code {r.status_code}. Vérifie que l'URL expose /models.")
        except Exception as e:
            QMessageBox.critical(self, "Erreur du fournisseur",
                                 f"Erreur : {str(e)[:200]}")

    def test_mistral_connection(self):
        key = self.mistral_input.text().strip()
        if not key:
            QMessageBox.warning(self, "Clé manquante", "Entre ta clé API Mistral d'abord !")
            return
        try:
            import requests
            r = requests.get(
                "https://api.mistral.ai/v1/models",
                headers={"Authorization": f"Bearer {key}"}, timeout=20,
            )
            if r.status_code == 200:
                QMessageBox.information(self, "✓ Connexion OK", "Clé Mistral valide !")
            elif r.status_code in (401, 403):
                QMessageBox.critical(self, "Clé invalide", "La clé API Mistral est incorrecte.")
            else:
                QMessageBox.information(
                    self, "Réponse Mistral",
                    f"Code {r.status_code}. La clé sera testée à la première génération.")
        except Exception as e:
            QMessageBox.critical(self, "Erreur Mistral", f"Erreur : {str(e)[:200]}")

    def test_kimi_connection(self):
        # URL de base éditable (cloud Moonshot par défaut ou serveur local /v1).
        base = (self.kimi_url_input.text().strip()
                or "https://api.moonshot.ai/v1").rstrip("/")
        key = self.kimi_input.text().strip()
        is_local = ("localhost" in base.lower()) or ("127.0.0.1" in base.lower())
        if not key and not is_local:
            QMessageBox.warning(
                self, "Clé manquante",
                "Entre ta clé API Kimi (Moonshot) d'abord — ou pointe l'URL vers un "
                "serveur local.")
            return
        try:
            import requests
            headers = {"Authorization": f"Bearer {key or 'local'}"}
            r = requests.get(f"{base}/models", headers=headers, timeout=20)
            if r.status_code == 200:
                QMessageBox.information(
                    self, "✓ Connexion OK",
                    f"Kimi joignable sur {base} — clé/endpoint valides !")
            elif r.status_code in (401, 403):
                QMessageBox.critical(self, "Clé invalide",
                                     "La clé API Kimi (Moonshot) est incorrecte.")
            else:
                QMessageBox.information(
                    self, "Réponse Kimi",
                    f"Code {r.status_code}. L'endpoint sera testé à la première génération.")
        except Exception as e:
            QMessageBox.critical(self, "Erreur Kimi", f"Erreur : {str(e)[:200]}")

    def test_glm_connection(self):
        # URL de base éditable (cloud Zhipu par défaut ou serveur local /v1) —
        # même schéma de testeur que Kimi.
        base = (self.glm_url_input.text().strip()
                or "https://open.bigmodel.cn/api/paas/v4").rstrip("/")
        key = self.glm_input.text().strip()
        is_local = ("localhost" in base.lower()) or ("127.0.0.1" in base.lower())
        if not key and not is_local:
            QMessageBox.warning(
                self, "Clé manquante",
                "Entre ta clé API GLM (Zhipu) d'abord — ou pointe l'URL vers un "
                "serveur local.")
            return
        try:
            import requests
            headers = {"Authorization": f"Bearer {key or 'local'}"}
            r = requests.get(f"{base}/models", headers=headers, timeout=20)
            if r.status_code == 200:
                QMessageBox.information(
                    self, "✓ Connexion OK",
                    f"GLM joignable sur {base} — clé/endpoint valides !")
            elif r.status_code in (401, 403):
                QMessageBox.critical(self, "Clé invalide",
                                     "La clé API GLM (Zhipu) est incorrecte.")
            else:
                QMessageBox.information(
                    self, "Réponse GLM",
                    f"Code {r.status_code}. L'endpoint sera testé à la première génération.")
        except Exception as e:
            QMessageBox.critical(self, "Erreur GLM", f"Erreur : {str(e)[:200]}")

    def test_connection(self):
        key = self.api_input.text().strip()
        if not key:
            QMessageBox.warning(self, "Clé manquante", "Entre ta clé API fal.ai d'abord !")
            return
        try:
            import fal_client
            os.environ["FAL_KEY"] = key
            fal_client.run("fal-ai/ping", arguments={})
            QMessageBox.information(self, "✓ Connexion OK", "Clé fal.ai valide !")
        except ImportError:
            QMessageBox.warning(
                self, "fal-client manquant",
                "Installe le client :\n\npip install fal-client"
            )
        except Exception as e:
            err = str(e)
            if "401" in err or "unauthorized" in err.lower():
                QMessageBox.critical(self, "Clé invalide", "La clé API fal.ai est incorrecte.")
            else:
                QMessageBox.information(
                    self, "✓ Client OK",
                    f"fal-client chargé. La clé sera testée à la première génération.\n\n"
                    f"({err[:100]})"
                )
