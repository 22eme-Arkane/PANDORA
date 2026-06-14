import os
import webbrowser
from PyQt6.QtWidgets import (
    QScrollArea, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QLineEdit, QPushButton, QMessageBox, QComboBox,
)
from PyQt6.QtCore import Qt
from ui.styles import CP
from ui.icons import load_icon
from ui.davinci_panel import DaVinciPanel
from core.config import load_config, save_config
from davinci.bridge import install_pandora_send

_FAL_KEYS_URL       = "https://fal.ai/dashboard/keys"
_ANTHROPIC_KEYS_URL = "https://console.anthropic.com/settings/keys"
_OPENAI_KEYS_URL    = "https://platform.openai.com/api-keys"
_MISTRAL_KEYS_URL   = "https://console.mistral.ai/api-keys"


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
    def __init__(self):
        super().__init__()
        self.setWidgetResizable(True)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setStyleSheet(f"background:{CP['bg0']};border:none;")

        container = QWidget()
        container.setStyleSheet(f"background:{CP['bg0']};")
        self.setWidget(container)

        lay = QVBoxLayout(container)
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
        lay.addWidget(_divider())

        cfg = load_config()

        # ── Assistant IA (texte) — juste après l'Apparence (retour 2026-06-13) ─
        lay.addWidget(_section("Assistant IA"))
        _lbl_ai = QLabel(
            "Moteur IA des fonctions texte : prompts, scénario, arrangement, storyboard, "
            "assistant. L'analyse d'images reste sur Anthropic."
        )
        _lbl_ai.setWordWrap(True)
        _lbl_ai.setStyleSheet(
            f"color:{CP['text_secondary']};font-size:12px;background:transparent;"
        )
        lay.addWidget(_lbl_ai)

        # (libellé, provider, modèle créatif)
        self._AI_CHOICES = [
            ("Claude Opus 4.8 (Anthropic) — défaut",      "anthropic", "claude-opus-4-8"),
            ("Claude Sonnet 4.6 (Anthropic) — équilibré", "anthropic", "claude-sonnet-4-6"),
            ("Claude Haiku 4.5 (Anthropic) — rapide",     "anthropic", "claude-haiku-4-5"),
            ("Fable 5 (Anthropic) — optimisé PANDORA",    "anthropic", "claude-fable-5"),
            ("GPT-5.5 (OpenAI)",                          "openai",    ""),
            ("Mistral — expérimental",                    "mistral",   ""),
            ("Ollama local — expérimental",               "ollama",    ""),
            ("PANDORA optimisé — moteur conseillé par tâche", "pandora", ""),
            ("Choix personnalisé — un moteur par tâche",  "custom",     ""),
        ]
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
        for label, prov, model in self._AI_CHOICES:
            self.ai_combo.addItem(label, (prov, model))
        _cur = (cfg.get("ai_provider", "anthropic"), cfg.get("ai_model_creative", ""))
        for i, (_, prov, model) in enumerate(self._AI_CHOICES):
            if prov == _cur[0] and (prov != "anthropic" or model == (_cur[1] or "claude-sonnet-4-6")):
                self.ai_combo.setCurrentIndex(i)
                break
        self.ai_combo.currentIndexChanged.connect(self._on_ai_choice_changed)
        lay.addWidget(self.ai_combo)

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

        self._lbl_ai_restart = QLabel(
            "Le nom de l'assistant dans l'interface se met à jour au prochain démarrage."
        )
        self._lbl_ai_restart.setWordWrap(True)
        self._lbl_ai_restart.setStyleSheet(
            f"color:{CP['text_dim']};font-size:10px;font-style:italic;background:transparent;"
        )
        lay.addWidget(self._lbl_ai_restart)

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
            "PANDORA est optimisé avec Fable 5 — le rendu avec les autres moteurs "
            "n'est pas encore totalement fiable."
        )
        _adv_hint.setWordWrap(True)
        _adv_hint.setStyleSheet(f"color:{CP['text_dim']};font-size:10px;background:transparent;")
        adv_lay.addWidget(_adv_hint)

        from core.ai_provider import TASKS, ENGINES, ENGINE_ORDER
        _engine_items = [("Par défaut", "")] + [
            (ENGINES[k]["name"], k) for k in ENGINE_ORDER
        ]
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
            for name, key in _engine_items:
                combo.addItem(name, key)
            _cur_eng = _saved_tasks.get(task_key, "")
            for i, (_, key) in enumerate(_engine_items):
                if key == _cur_eng:
                    combo.setCurrentIndex(i)
                    break
            self._task_combos[task_key] = combo
            row.addWidget(combo)
            adv_lay.addLayout(row)
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
            "▶  Clés API facultatives  (OpenAI, Mistral, autres à venir)")
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
            "Non requises pour faire fonctionner PANDORA — uniquement si vous "
            "voulez utiliser ces moteurs comme assistant texte (global ou par tâche)."
        )
        _opt_hint.setWordWrap(True)
        _opt_hint.setStyleSheet(f"color:{CP['text_dim']};font-size:10px;background:transparent;")
        opt_lay.addWidget(_opt_hint)

        # OpenAI (GPT-5.5)
        oa_lbl_row = QHBoxLayout()
        oa_lbl_row.setSpacing(8)
        lbl_oa = QLabel("OpenAI — GPT-5.5  (assistant texte, par moteur ou par tâche)")
        lbl_oa.setStyleSheet(
            f"color:{CP['text_secondary']};font-size:12px;background:transparent;"
        )
        oa_lbl_row.addWidget(lbl_oa, 1)
        oa_lbl_row.addWidget(_badge("Facultatif", "opt"))
        oa_lbl_row.addWidget(_test_btn("✓  Tester API GPT-5.5", self.test_openai_connection))
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

        _send_row = QHBoxLayout()
        _send_row.setContentsMargins(0, 4, 0, 0)
        _btn_send = QPushButton("⚙  Installer le script PANDORA dans DaVinci Resolve Studio")
        _btn_send.setFixedHeight(30)
        _btn_send.setCursor(Qt.CursorShape.PointingHandCursor)
        _btn_send.setStyleSheet(
            f"QPushButton{{background:{CP['bg3']};color:{CP['text_dim']};"
            f"border:1px solid {CP['border']};border-radius:6px;"
            f"font-size:11px;padding:0 14px;}}"
            f"QPushButton:hover{{background:{CP['bg2']};color:{CP['text_secondary']};}}"
        )
        _btn_send.setToolTip(
            "Installe le script pandora_send dans DaVinci Resolve Studio\n"
            "(Fusion/Scripts/Utility).\n"
            "Permet d'envoyer des clips vers AI Studio\n"
            "→ Modifier depuis DaVinci Resolve\n"
            "via Espace de travail → Scripts → pandora_send.\n\n"
            "Pour configurer un raccourci clavier dans DaVinci Resolve Studio :\n"
            "Espace de travail → Personnalisation du clavier\n"
            "→ Rechercher « pandora_send »\n"
            "→ Assigner votre raccourci (ex. Ctrl+Shift+P)"
        )
        _btn_send.clicked.connect(self._install_pandora_send)
        _send_row.addWidget(_btn_send)
        _send_row.addStretch()
        lay.addLayout(_send_row)
        # (le bouton de vérification de mise à jour a été retiré de cette page :
        # il existe déjà en haut à droite de la fenêtre — retour 2026-06-13)
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

    # ── Dialogues d'aide ─────────────────────────────────────────────────────

    def _show_davinci_help(self):
        from ui.dialog_davinci_help import DaVinciHelpDialog
        DaVinciHelpDialog(self).exec()

    def _show_api_help(self):
        from ui.dialog_api_help import ApiHelpDialog
        ApiHelpDialog(self).exec()

    def _on_ai_choice_changed(self, *_):
        """Champs Ollama conditionnels + « Choix personnalisé » ouvre les avancés."""
        prov = (self.ai_combo.currentData() or ("anthropic", ""))[0]
        self.ollama_url_input.setVisible(prov == "ollama")
        self.ollama_model_input.setVisible(prov == "ollama")
        # « Choix personnalisé » et « PANDORA optimisé » déplient le moteur par tâche
        if prov in ("custom", "pandora") and not self._adv_open:
            self._set_advanced(True)
        # « PANDORA optimisé » remplit les combos avec le preset conseillé
        if prov == "pandora":
            self._apply_pandora_preset()

    def _set_advanced(self, open_: bool):
        self._adv_open = open_
        self._adv_box.setVisible(open_)
        self._btn_adv.setText(
            ("▼" if open_ else "▶") + "  Paramètres avancés — moteur IA par tâche"
        )

    def _toggle_advanced(self):
        self._set_advanced(not self._adv_open)

    def _toggle_opt_keys(self):
        self._opt_keys_open = not self._opt_keys_open
        self._opt_keys_box.setVisible(self._opt_keys_open)
        self._btn_opt_keys.setText(
            ("▼" if self._opt_keys_open else "▶")
            + "  Clés API facultatives  (OpenAI, Mistral, autres à venir)"
        )

    # ── Sauvegarde ────────────────────────────────────────────────────────────

    def save(self):
        cfg = load_config()
        prov, model = self.ai_combo.currentData() or ("anthropic", "")
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
            "ai_provider":       prov,
            "ai_model_creative": model,
            "mistral_key":       self.mistral_input.text(),
            "ollama_url":        self.ollama_url_input.text(),
            "ollama_model":      self.ollama_model_input.text(),
            "ai_task_engines":   task_engines,
        })
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
                  self.mistral_input, self.ollama_url_input, self.ollama_model_input):
            w.textChanged.connect(self.save)
        for combo in getattr(self, "_task_combos", {}).values():
            combo.currentIndexChanged.connect(self.save)

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
                QMessageBox.information(self, "✓ Connexion OK", "Clé OpenAI (GPT-5.5) valide !")
            elif r.status_code in (401, 403):
                QMessageBox.critical(self, "Clé invalide", "La clé API OpenAI est incorrecte.")
            else:
                QMessageBox.information(
                    self, "Réponse OpenAI",
                    f"Code {r.status_code}. La clé sera testée à la première génération.")
        except Exception as e:
            QMessageBox.critical(self, "Erreur OpenAI", f"Erreur : {str(e)[:200]}")

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
