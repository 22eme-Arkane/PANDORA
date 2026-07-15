"""
ui/page_live_settings.py — Paramètres PANDORA | Live.

Connexion Resolume par défaut + clés API utilisées par le module Live.
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QLineEdit, QSpinBox, QFrame,
)
from PyQt6.QtCore import Qt
from core.i18n import translate
from ui.styles import CP


def _section_title(text: str) -> QLabel:
    lbl = QLabel(text)
    lbl.setStyleSheet(
        f"color:{CP['text_secondary']};font-size:10px;font-weight:700;"
        f"letter-spacing:3px;font-family:'Consolas',monospace;"
        f"background:transparent;border:none;"
    )
    return lbl


def _label(text: str) -> QLabel:
    lbl = QLabel(text)
    lbl.setStyleSheet(
        f"color:{CP['text_secondary']};font-size:11px;"
        f"background:transparent;border:none;"
    )
    return lbl


def _input(placeholder: str = "", width: int = 320) -> QLineEdit:
    e = QLineEdit()
    e.setPlaceholderText(placeholder)
    e.setFixedHeight(36)
    if width:
        e.setFixedWidth(width)
    e.setStyleSheet(
        f"QLineEdit{{background:{CP['bg3']};border:1px solid {CP['border']};"
        f"border-radius:6px;color:{CP['text_primary']};font-size:12px;padding:0 12px;}}"
        f"QLineEdit:focus{{border-color:{CP['accent2']};}}"
    )
    return e


def _separator() -> QFrame:
    sep = QFrame()
    sep.setFixedHeight(1)
    sep.setStyleSheet(f"background:{CP['border']};")
    return sep


class PageLiveSettings(QWidget):
    """Page Paramètres — connexion Resolume + clés API Live."""

    def __init__(self):
        super().__init__()
        self.setStyleSheet(f"background:{CP['bg0']};")

        scroll_area = QWidget()
        scroll_area.setStyleSheet("background:transparent;")
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        content = QWidget()
        content.setStyleSheet("background:transparent;")
        lay = QVBoxLayout(content)
        lay.setContentsMargins(48, 36, 48, 36)
        lay.setSpacing(0)

        # ── Titre ──────────────────────────────────────────────────────────────
        title = QLabel("Paramètres Live")
        title.setStyleSheet(
            f"color:{CP['text_primary']};font-size:22px;font-weight:800;"
            f"background:transparent;border:none;"
        )
        lay.addWidget(title)
        lay.addSpacing(4)

        sub = QLabel("Configuration de la connexion Resolume et des clés API.")
        sub.setStyleSheet(
            f"color:{CP['text_dim']};font-size:12px;"
            f"background:transparent;border:none;"
        )
        lay.addWidget(sub)
        lay.addSpacing(32)

        # ── Affichage : thème + 2ᵉ fenêtre / 2 écrans (parité Cinéma) ───────────
        lay.addWidget(_section_title("AFFICHAGE"))
        lay.addSpacing(10)

        # Thème Sombre / Clair — même clé config « theme » que le Cinéma,
        # appliqué au prochain démarrage (porté le 2026-07-14, parité Paramètres).
        from core.config import load_config as _lc_theme
        _theme_now = _lc_theme().get("theme", "dark")
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
        for _b in (self._btn_dark, self._btn_light):
            _b.setFixedHeight(36)
            _b.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_dark.setStyleSheet(
            _ss_theme_active if _theme_now == "dark" else _ss_theme_inactive)
        self._btn_light.setStyleSheet(
            _ss_theme_active if _theme_now == "light" else _ss_theme_inactive)

        def _set_theme(theme: str):
            from PyQt6.QtWidgets import QMessageBox
            from core.config import load_config, save_config
            cfg = load_config()
            cfg["theme"] = theme
            save_config(cfg)
            self._btn_dark.setStyleSheet(
                _ss_theme_active if theme == "dark" else _ss_theme_inactive)
            self._btn_light.setStyleSheet(
                _ss_theme_active if theme == "light" else _ss_theme_inactive)
            QMessageBox.information(
                self, translate("Thème enregistré"),
                translate("Le nouveau thème sera appliqué au prochain démarrage de PANDORA."))

        self._btn_dark.clicked.connect(lambda: _set_theme("dark"))
        self._btn_light.clicked.connect(lambda: _set_theme("light"))
        _theme_row = QHBoxLayout()
        _theme_row.setSpacing(8)
        _theme_row.addWidget(self._btn_dark)
        _theme_row.addWidget(self._btn_light)
        _theme_row.addStretch()
        lay.addLayout(_theme_row)
        _lbl_theme = QLabel("Le changement de thème est appliqué au prochain démarrage.")
        _lbl_theme.setStyleSheet(
            f"color:{CP['text_dim']};font-size:10px;background:transparent;border:none;")
        lay.addSpacing(6)
        lay.addWidget(_lbl_theme)
        lay.addSpacing(12)

        self._btn_second_window = QPushButton("🖥  Ouvrir une 2ᵉ fenêtre (2 écrans)")
        self._btn_second_window.setFixedHeight(36)
        self._btn_second_window.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_second_window.setStyleSheet(
            f"QPushButton{{background:transparent;color:{CP['text_secondary']};"
            f"border:1px solid {CP['border']};border-radius:7px;font-size:12px;"
            f"font-weight:600;padding:0 18px;}}"
            f"QPushButton:hover{{background:{CP['bg3']};color:{CP['text_primary']};}}"
        )
        self._btn_second_window.clicked.connect(self._open_second_window)
        lay.addWidget(self._btn_second_window)
        _scr_note = QLabel(
            "Ouvre une copie de PANDORA | Live sur le même projet, à déplacer sur un "
            "2ᵉ écran (ex. contrôleur d'un côté, mapping/preview de l'autre). Navigation "
            "indépendante ; évitez de modifier la même page dans les deux fenêtres."
        )
        _scr_note.setWordWrap(True)
        _scr_note.setStyleSheet(
            f"color:{CP['text_dim']};font-size:10px;background:transparent;border:none;")
        lay.addSpacing(6)
        lay.addWidget(_scr_note)
        lay.addSpacing(28)

        # ── Section Resolume ────────────────────────────────────────────────────
        lay.addWidget(_section_title("CONNEXION RESOLUME"))
        lay.addSpacing(14)

        resolume_card = QFrame()
        resolume_card.setStyleSheet(
            f"QFrame{{background:{CP['bg2']};border:1px solid {CP['border']};"
            f"border-radius:12px;}}"
        )
        rc = QVBoxLayout(resolume_card)
        rc.setContentsMargins(24, 20, 24, 20)
        rc.setSpacing(14)

        info = QLabel(
            "Resolume Arena ou Avenue doit être lancé avec le serveur web activé :\n"
            "Préférences → Webserver → « Enable Webserver & REST API »  (port : 8080)"
        )
        info.setWordWrap(True)
        info.setStyleSheet(
            f"color:{CP['text_secondary']};font-size:11px;"
            f"background:transparent;border:none;"
        )
        rc.addWidget(info)

        rc.addWidget(_separator())

        # Adresse hôte
        host_row = QHBoxLayout()
        host_row.setSpacing(12)
        host_row.addWidget(_label("Adresse IP / hôte :"))
        self._host_input = _input("localhost", 200)
        self._host_input.setText("localhost")
        host_row.addWidget(self._host_input)
        host_row.addStretch()
        rc.addLayout(host_row)

        # Port
        port_row = QHBoxLayout()
        port_row.setSpacing(12)
        port_row.addWidget(_label("Port Webserver :"))
        self._port_spin = QSpinBox()
        self._port_spin.setRange(1024, 65535)
        self._port_spin.setValue(8080)
        self._port_spin.setFixedSize(100, 36)
        self._port_spin.setStyleSheet(
            f"QSpinBox{{background:{CP['bg3']};border:1px solid {CP['border']};"
            f"border-radius:6px;color:{CP['text_primary']};font-size:12px;padding:0 8px;}}"
            f"QSpinBox:focus{{border-color:{CP['accent2']};}}"
        )
        port_row.addWidget(self._port_spin)
        port_row.addStretch()
        rc.addLayout(port_row)

        # Bouton tester
        btn_test = QPushButton("◈  Tester la connexion")
        btn_test.setFixedHeight(38)
        btn_test.setFixedWidth(220)
        btn_test.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_test.setStyleSheet(
            f"QPushButton{{background:transparent;color:{CP['accent2']};"
            f"border:1.5px solid {CP['accent2']};border-radius:8px;"
            f"font-size:12px;font-weight:700;padding:0 16px;}}"
            f"QPushButton:hover{{background:rgba(124,107,255,0.12);}}"
            f"QPushButton:pressed{{background:rgba(124,107,255,0.22);}}"
        )
        btn_test.clicked.connect(self._test_connection)

        self._test_lbl = QLabel("")
        self._test_lbl.setStyleSheet(
            f"color:{CP['text_dim']};font-size:11px;background:transparent;border:none;"
        )

        test_row = QHBoxLayout()
        test_row.setSpacing(14)
        test_row.addWidget(btn_test)
        test_row.addWidget(self._test_lbl, 1)
        rc.addLayout(test_row)

        lay.addWidget(resolume_card)
        lay.addSpacing(28)

        # ── Section Clés API ────────────────────────────────────────────────────
        _api_head = QHBoxLayout()
        _api_head.setSpacing(10)
        _api_head.addWidget(_section_title("CLÉS API"))
        _api_head.addStretch()
        _btn_api_help = QPushButton("ℹ  Comment obtenir les clés API")
        _btn_api_help.setFixedHeight(28)
        _btn_api_help.setCursor(Qt.CursorShape.PointingHandCursor)
        _btn_api_help.setStyleSheet(
            f"QPushButton{{background:transparent;color:{CP['accent']};"
            f"border:1px solid {CP['accent_dim']};border-radius:6px;"
            f"font-size:10px;font-weight:700;padding:0 10px;}}"
            f"QPushButton:hover{{background:rgba(78,205,196,0.10);}}"
        )
        _btn_api_help.clicked.connect(self._show_api_help)
        _api_head.addWidget(_btn_api_help)
        lay.addLayout(_api_head)
        lay.addSpacing(14)

        api_card = QFrame()
        api_card.setStyleSheet(
            f"QFrame{{background:{CP['bg2']};border:1px solid {CP['border']};"
            f"border-radius:12px;}}"
        )
        ac = QVBoxLayout(api_card)
        ac.setContentsMargins(24, 20, 24, 20)
        ac.setSpacing(14)

        api_info = QLabel(
            "Ces clés sont partagées avec PANDORA | Cinéma (mêmes clés, même config).\n"
            "fal.ai : génération vidéo IA  ·  Anthropic (Claude) : assistant et traduction des prompts."
        )
        api_info.setWordWrap(True)
        api_info.setStyleSheet(
            f"color:{CP['text_secondary']};font-size:11px;"
            f"background:transparent;border:none;"
        )
        ac.addWidget(api_info)

        ac.addWidget(_separator())

        def _key_label(text: str) -> QLabel:
            lbl = _label(text)
            lbl.setFixedWidth(180)
            return lbl

        def _link_btn(label: str, url: str) -> QPushButton:
            b = QPushButton(label)
            b.setFixedHeight(28)
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.setToolTip(url)
            b.setStyleSheet(
                f"QPushButton{{background:transparent;color:{CP['accent']};"
                f"border:1px solid {CP['accent_dim']};border-radius:6px;"
                f"font-size:10px;font-weight:700;padding:0 10px;}}"
                f"QPushButton:hover{{background:rgba(78,205,196,0.10);}}"
            )
            def _open(checked=False, u=url):
                from PyQt6.QtGui import QDesktopServices
                from PyQt6.QtCore import QUrl
                QDesktopServices.openUrl(QUrl(u))
            b.clicked.connect(_open)
            return b

        def _test_btn(label: str, cb) -> QPushButton:
            b = QPushButton(label)
            b.setFixedHeight(28)
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.setStyleSheet(
                f"QPushButton{{background:transparent;color:{CP['accent2']};"
                f"border:1px solid {CP['accent2']};border-radius:6px;"
                f"font-size:10px;font-weight:700;padding:0 10px;}}"
                f"QPushButton:hover{{background:rgba(124,107,255,0.12);}}"
            )
            b.clicked.connect(cb)
            return b

        key_row = QHBoxLayout()
        key_row.setSpacing(12)
        key_row.addWidget(_key_label("Clé fal.ai :"))
        self._api_key_input = _input("xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx:xxxx…", 0)
        self._api_key_input.setEchoMode(QLineEdit.EchoMode.Password)
        key_row.addWidget(self._api_key_input, 1)
        key_row.addWidget(_test_btn("✓  Tester API fal.ai", self.test_connection))
        key_row.addWidget(_link_btn("⇗  Clés", "https://fal.ai/dashboard/keys"))
        key_row.addWidget(_link_btn("⇗  Crédits", "https://fal.ai/dashboard/billing"))
        ac.addLayout(key_row)

        ant_row = QHBoxLayout()
        ant_row.setSpacing(12)
        ant_row.addWidget(_key_label("Clé Anthropic (Claude) :"))
        self._anthropic_input = _input("sk-ant-…", 0)
        self._anthropic_input.setEchoMode(QLineEdit.EchoMode.Password)
        ant_row.addWidget(self._anthropic_input, 1)
        ant_row.addWidget(_test_btn("✓  Tester API Anthropic", self.test_anthropic_connection))
        ant_row.addWidget(_link_btn("⇗  Clés", "https://console.anthropic.com/settings/keys"))
        ant_row.addWidget(_link_btn("⇗  Crédits", "https://console.anthropic.com/settings/billing"))
        ac.addLayout(ant_row)

        # ── Assistant IA (texte) — même réglage que Cinéma (config partagée) ──
        from PyQt6.QtWidgets import QComboBox
        ai_row = QHBoxLayout()
        ai_row.setSpacing(12)
        ai_row.addWidget(_key_label("Assistant IA (texte) :"))
        # 1er choix = profil PAR DÉFAUT (routage idéal par tâche — cf.
        # core.ai_provider.TASK_DEFAULTS) : même sémantique que le combo Cinéma.
        # ⚠ Un modèle vide en config doit présélectionner CE choix (Opus), sinon
        # l'auto-save rétrograderait silencieusement le profil en Sonnet partout.
        self._AI_CHOICES = [
            ("PANDORA optimisé — idéal par tâche (défaut)", "anthropic", "claude-opus-4-8"),
            ("Claude Sonnet 5 — tout en équilibré", "anthropic", "claude-sonnet-5"),
            ("Claude Haiku 4.5 — tout en rapide / économe", "anthropic", "claude-haiku-4-5"),
            ("Fable 5 (Anthropic) — qualité max",  "anthropic", "claude-fable-5"),
            ("GPT-5.5 (OpenAI) — partout",         "openai",    ""),
            ("Mistral — expérimental",             "mistral",   ""),
            ("Kimi K2.7 (Moonshot) — API ou local", "kimi",     ""),
            ("GLM 4.7 (Zhipu) — API ou local",     "glm",       ""),
            ("Ollama local — expérimental",        "ollama",    ""),
            ("Choix personnalisé — un moteur par tâche", "custom", ""),
        ]
        self._ai_combo = QComboBox()
        self._ai_combo.setFixedHeight(34)
        self._ai_combo.setStyleSheet(
            f"QComboBox{{background:{CP['bg3']};border:1px solid {CP['border']};"
            f"border-radius:8px;color:{CP['text_primary']};font-size:12px;padding:0 10px;}}"
            f"QComboBox::drop-down{{border:none;width:22px;}}"
            f"QComboBox QAbstractItemView{{background:{CP['bg3']};"
            f"border:1px solid {CP['border_bright']};color:{CP['text_primary']};"
            f"selection-background-color:{CP['accent_dim']};}}"
        )
        for label, prov, model in self._AI_CHOICES:
            self._ai_combo.addItem(label, (prov, model))
        ai_row.addWidget(self._ai_combo, 1)
        ac.addLayout(ai_row)

        # OpenAI (GPT-5.5) — clé visible quand le moteur OpenAI (ou « Choix
        # personnalisé ») est sélectionné ; même clé de config que Cinéma.
        oa_row = QHBoxLayout()
        oa_row.setSpacing(12)
        oa_row.addWidget(_key_label("Clé OpenAI (GPT-5.5) :"))
        self._openai_input = _input("sk-••••••••••••••••••••••••", 0)
        self._openai_input.setEchoMode(QLineEdit.EchoMode.Password)
        oa_row.addWidget(self._openai_input, 1)
        _oa_test = _test_btn("✓  Tester API GPT-5.5", self.test_openai_connection)
        oa_row.addWidget(_oa_test)
        _oa_link = _link_btn("⇗  Clés", "https://platform.openai.com/api-keys")
        oa_row.addWidget(_oa_link)
        self._openai_row_widgets = (oa_row.itemAt(0).widget(), self._openai_input,
                                    _oa_test, _oa_link)
        ac.addLayout(oa_row)

        mis_row = QHBoxLayout()
        mis_row.setSpacing(12)
        mis_row.addWidget(_key_label("Clé Mistral :"))
        self._mistral_input = _input("Clé API Mistral", 0)
        self._mistral_input.setEchoMode(QLineEdit.EchoMode.Password)
        mis_row.addWidget(self._mistral_input, 1)
        _ms_test = _test_btn("✓  Tester API Mistral", self.test_mistral_connection)
        mis_row.addWidget(_ms_test)
        self._mistral_row_widgets = (mis_row.itemAt(0).widget(), self._mistral_input,
                                     _ms_test)
        ac.addLayout(mis_row)

        oll_row = QHBoxLayout()
        oll_row.setSpacing(12)
        oll_row.addWidget(_key_label("Ollama (URL · modèle) :"))
        self._ollama_url_input = _input("http://localhost:11434", 0)
        self._ollama_model_input = _input("llama3.1", 0)
        oll_row.addWidget(self._ollama_url_input, 1)
        oll_row.addWidget(self._ollama_model_input, 1)
        self._ollama_row_widgets = (oll_row.itemAt(0).widget(),
                                    self._ollama_url_input, self._ollama_model_input)
        ac.addLayout(oll_row)

        # Kimi (Moonshot) — clé facultative (vide en local) + URL/modèle. L'URL de base
        # sert d'aiguillage API cloud ↔ serveur local OpenAI-compatible (mêmes clés de
        # config que Cinéma : kimi_key / kimi_url / kimi_model).
        kim_row = QHBoxLayout()
        kim_row.setSpacing(12)
        kim_row.addWidget(_key_label("Clé Kimi (Moonshot) :"))
        self._kimi_input = _input("sk-••••  (vide si serveur local)", 0)
        self._kimi_input.setEchoMode(QLineEdit.EchoMode.Password)
        kim_row.addWidget(self._kimi_input, 1)
        _km_test = _test_btn("✓  Tester API Kimi", self.test_kimi_connection)
        kim_row.addWidget(_km_test)
        _km_link = _link_btn("⇗  Clés", "https://platform.moonshot.ai/console/api-keys")
        kim_row.addWidget(_km_link)
        self._kimi_key_row_widgets = (kim_row.itemAt(0).widget(), self._kimi_input,
                                      _km_test, _km_link)
        ac.addLayout(kim_row)

        kimu_row = QHBoxLayout()
        kimu_row.setSpacing(12)
        kimu_row.addWidget(_key_label("Kimi (URL · modèle) :"))
        self._kimi_url_input = _input("https://api.moonshot.ai/v1  (ou local /v1)", 0)
        self._kimi_model_input = _input("kimi-k2.7-code", 0)
        kimu_row.addWidget(self._kimi_url_input, 1)
        kimu_row.addWidget(self._kimi_model_input, 1)
        self._kimi_row_widgets = (kimu_row.itemAt(0).widget(),
                                  self._kimi_url_input, self._kimi_model_input)
        ac.addLayout(kimu_row)

        # GLM (Zhipu) — même schéma que Kimi : clé facultative (vide en local) +
        # URL/modèle, l'URL de base aiguillant API cloud ↔ serveur local
        # OpenAI-compatible (mêmes clés de config que Cinéma : glm_key/glm_url/glm_model).
        glk_row = QHBoxLayout()
        glk_row.setSpacing(12)
        glk_row.addWidget(_key_label("Clé GLM (Zhipu) :"))
        self._glm_input = _input("Clé API GLM  (vide si serveur local)", 0)
        self._glm_input.setEchoMode(QLineEdit.EchoMode.Password)
        glk_row.addWidget(self._glm_input, 1)
        _gl_test = _test_btn("✓  Tester API GLM", self.test_glm_connection)
        glk_row.addWidget(_gl_test)
        _gl_link = _link_btn("⇗  Clés", "https://bigmodel.cn/usercenter/apikeys")
        glk_row.addWidget(_gl_link)
        self._glm_key_row_widgets = (glk_row.itemAt(0).widget(), self._glm_input,
                                     _gl_test, _gl_link)
        ac.addLayout(glk_row)

        glu_row = QHBoxLayout()
        glu_row.setSpacing(12)
        glu_row.addWidget(_key_label("GLM (URL · modèle) :"))
        self._glm_url_input = _input("https://open.bigmodel.cn/api/paas/v4  (ou local /v1)", 0)
        self._glm_model_input = _input("glm-4.7", 0)
        glu_row.addWidget(self._glm_url_input, 1)
        glu_row.addWidget(self._glm_model_input, 1)
        self._glm_row_widgets = (glu_row.itemAt(0).widget(),
                                 self._glm_url_input, self._glm_model_input)
        ac.addLayout(glu_row)

        # ── Paramètres avancés : moteur IA PAR TÂCHE (repliable, parité Cinéma) ──
        # Le Live UTILISE le routage ai_task_engines (task=) mais ne pouvait pas le
        # RÉGLER — il fallait passer par l'édition Cinéma (constat 2026-07-14).
        self._adv_open = False
        self._btn_adv = QPushButton("▶  Paramètres avancés — moteur IA par tâche")
        self._btn_adv.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_adv.setStyleSheet(
            f"QPushButton{{background:transparent;color:{CP['accent2']};"
            f"border:none;text-align:left;font-size:11px;font-weight:700;padding:4px 0;}}"
            f"QPushButton:hover{{color:#9d8fff;}}"
        )
        self._btn_adv.clicked.connect(self._toggle_advanced)
        ac.addWidget(self._btn_adv)

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
        _adv_hint.setStyleSheet(
            f"color:{CP['text_dim']};font-size:10px;background:transparent;border:none;")
        adv_lay.addWidget(_adv_hint)

        from core.config import load_config as _lc_tasks
        from core.ai_provider import (TASKS, ENGINES, ENGINE_ORDER,
                                      recommended_engine_name)
        _engine_items = [(ENGINES[k]["name"], k) for k in ENGINE_ORDER]
        self._task_combos = {}
        _saved_tasks = _lc_tasks().get("ai_task_engines") or {}
        for task_key, task_label in TASKS:
            row = QHBoxLayout()
            row.setSpacing(8)
            lbl = QLabel(task_label)
            lbl.setStyleSheet(
                f"color:{CP['text_secondary']};font-size:11px;"
                f"background:transparent;border:none;")
            row.addWidget(lbl, 1)
            combo = QComboBox()
            combo.setFixedHeight(28)
            combo.setMinimumWidth(160)
            combo.setStyleSheet(
                f"QComboBox{{background:{CP['bg3']};border:1px solid {CP['border']};"
                f"border-radius:6px;color:{CP['text_primary']};font-size:11px;padding:0 8px;}}"
                f"QComboBox::drop-down{{border:none;width:20px;}}"
                f"QComboBox QAbstractItemView{{background:{CP['bg3']};"
                f"border:1px solid {CP['border_bright']};color:{CP['text_primary']};"
                f"selection-background-color:{CP['accent_dim']};}}"
            )
            combo.addItem(f"Par défaut · {recommended_engine_name(task_key)}", "")
            for name, key in _engine_items:
                combo.addItem(name, key)
            _cur_eng = _saved_tasks.get(task_key, "")
            for i in range(combo.count()):
                if combo.itemData(i) == _cur_eng:
                    combo.setCurrentIndex(i)
                    break
            self._task_combos[task_key] = combo
            row.addWidget(combo)
            adv_lay.addLayout(row)
        ac.addWidget(self._adv_box)

        def _on_ai_changed(*_):
            prov = (self._ai_combo.currentData() or ("anthropic", ""))[0]
            # « Choix personnalisé » : toutes les clés restent saisissables (le
            # routage par tâche peut viser n'importe quel moteur) + avancés dépliés.
            _all = prov == "custom"
            for wdg in self._openai_row_widgets:
                wdg.setVisible(_all or prov == "openai")
            for wdg in self._mistral_row_widgets:
                wdg.setVisible(_all or prov == "mistral")
            for wdg in self._ollama_row_widgets:
                wdg.setVisible(_all or prov == "ollama")
            for wdg in self._kimi_key_row_widgets:
                wdg.setVisible(_all or prov == "kimi")
            for wdg in self._kimi_row_widgets:
                wdg.setVisible(_all or prov == "kimi")
            for wdg in self._glm_key_row_widgets:
                wdg.setVisible(_all or prov == "glm")
            for wdg in self._glm_row_widgets:
                wdg.setVisible(_all or prov == "glm")
            if _all and not self._adv_open:
                self._set_advanced(True)
        self._ai_combo.currentIndexChanged.connect(_on_ai_changed)
        self._on_ai_changed = _on_ai_changed

        # ── Sauvegarde AUTOMATIQUE (plus de bouton — tout changement est
        #    enregistré, comme le Cinéma) ───────────────────────────────────────
        self._autosave_lbl = QLabel("✓  Sauvegarde automatique — chaque modification est enregistrée.")
        self._autosave_lbl.setStyleSheet(
            f"color:{CP['text_dim']};font-size:11px;font-style:italic;background:transparent;"
        )
        ac.addWidget(self._autosave_lbl)

        lay.addWidget(api_card)
        lay.addStretch()

        root.addWidget(content, 1)

        self._load_settings()
        # Branché APRÈS le chargement : les setText de _load_settings ne
        # déclenchent pas de re-sauvegarde des valeurs fraîchement lues.
        self._wire_autosave()

    def _wire_autosave(self):
        """Sauvegarde automatique : tout changement de champ persiste aussitôt (parité Cinéma)."""
        self._ai_combo.currentIndexChanged.connect(self._save_api_key)
        for w in (self._api_key_input, self._anthropic_input, self._openai_input,
                  self._mistral_input,
                  self._ollama_url_input, self._ollama_model_input,
                  self._kimi_input, self._kimi_url_input, self._kimi_model_input,
                  self._glm_input, self._glm_url_input, self._glm_model_input,
                  self._host_input):
            w.textChanged.connect(self._save_api_key)
        self._port_spin.valueChanged.connect(self._save_api_key)
        for combo in getattr(self, "_task_combos", {}).values():
            combo.currentIndexChanged.connect(self._save_api_key)

    def _set_advanced(self, open_: bool):
        self._adv_open = open_
        self._adv_box.setVisible(open_)
        self._btn_adv.setText(
            ("▼" if open_ else "▶") + "  Paramètres avancés — moteur IA par tâche")

    def _toggle_advanced(self):
        self._set_advanced(not self._adv_open)

    def _show_api_help(self):
        from ui.dialog_api_help import ApiHelpDialog
        ApiHelpDialog(self).exec()

    def _open_second_window(self):
        """Demande à la fenêtre Live parente d'ouvrir une 2ᵉ fenêtre (2 écrans)."""
        from PyQt6.QtWidgets import QMessageBox
        win = self.window()
        if win is not None and hasattr(win, "open_secondary_window"):
            win.open_secondary_window()
        else:
            QMessageBox.information(
                self, translate("Indisponible"),
                translate("La 2ᵉ fenêtre ne peut être ouverte que depuis la fenêtre principale."))

    def _load_settings(self):
        from core.config import load_config
        cfg = load_config()
        key = cfg.get("api_key", "")
        if key:
            self._api_key_input.setText(key)
        ant = cfg.get("anthropic_key", "")
        if ant:
            self._anthropic_input.setText(ant)
        # Assistant IA (texte). Défaut = Opus 4.8 (cf. core.ai_provider._DEFAULT_CREATIVE) :
        # un modèle vide doit présélectionner « PANDORA optimisé », sinon le combo
        # affichait Sonnet à tort — et l'auto-save aurait réellement rétrogradé
        # l'assistant en Sonnet partout (perte du routage par tâche).
        _cur = (cfg.get("ai_provider", "anthropic"), cfg.get("ai_model_creative", ""))
        for i, (_, prov, model) in enumerate(self._AI_CHOICES):
            if prov == _cur[0] and (prov != "anthropic" or model == (_cur[1] or "claude-opus-4-8")):
                self._ai_combo.setCurrentIndex(i)
                break
        self._openai_input.setText(cfg.get("openai_key", ""))
        self._mistral_input.setText(cfg.get("mistral_key", ""))
        self._ollama_url_input.setText(cfg.get("ollama_url", ""))
        self._ollama_model_input.setText(cfg.get("ollama_model", ""))
        self._kimi_input.setText(cfg.get("kimi_key", ""))
        self._kimi_url_input.setText(cfg.get("kimi_url", ""))
        self._kimi_model_input.setText(cfg.get("kimi_model", ""))
        self._glm_input.setText(cfg.get("glm_key", ""))
        self._glm_url_input.setText(cfg.get("glm_url", ""))
        self._glm_model_input.setText(cfg.get("glm_model", ""))
        self._on_ai_changed()
        host = cfg.get("resolume_host", "localhost")
        port = cfg.get("resolume_port", 8080)
        self._host_input.setText(str(host))
        self._port_spin.setValue(int(port))

    def _save_api_key(self):
        from core.config import load_config, save_config
        cfg = load_config()
        cfg["api_key"]       = self._api_key_input.text().strip()
        cfg["anthropic_key"] = self._anthropic_input.text().strip()
        prov, model = self._ai_combo.currentData() or ("anthropic", "")
        cfg["ai_provider"]       = prov
        cfg["ai_model_creative"] = model
        cfg["openai_key"]        = self._openai_input.text().strip()
        # Moteur PAR TÂCHE : ne garder que les tâches dont le moteur ≠ « Par défaut »
        task_engines = {}
        for task_key, combo in getattr(self, "_task_combos", {}).items():
            eng = combo.currentData()
            if eng:
                task_engines[task_key] = eng
        cfg["ai_task_engines"]   = task_engines
        cfg["mistral_key"]       = self._mistral_input.text().strip()
        cfg["ollama_url"]        = self._ollama_url_input.text().strip()
        cfg["ollama_model"]      = self._ollama_model_input.text().strip()
        cfg["kimi_key"]          = self._kimi_input.text().strip()
        cfg["kimi_url"]          = self._kimi_url_input.text().strip()
        cfg["kimi_model"]        = self._kimi_model_input.text().strip()
        cfg["glm_key"]           = self._glm_input.text().strip()
        cfg["glm_url"]           = self._glm_url_input.text().strip()
        cfg["glm_model"]         = self._glm_model_input.text().strip()
        cfg["resolume_host"] = self._host_input.text().strip() or "localhost"
        cfg["resolume_port"] = self._port_spin.value()
        save_config(cfg)
        from core.ai_provider import refresh_name_cache
        refresh_name_cache()   # le nom de l'assistant change → libellés au prochain démarrage
        # Sauvegarde automatique : retour discret (pas de pop-up à chaque frappe)
        if hasattr(self, "_autosave_lbl"):
            self._autosave_lbl.setText("✓  Enregistré automatiquement.")

    # ── Testeurs de clés API (portés du Cinéma, mêmes comportements) ──────────

    def test_connection(self):
        from PyQt6.QtWidgets import QMessageBox
        key = self._api_key_input.text().strip()
        if not key:
            QMessageBox.warning(self, "Clé manquante", "Entre ta clé API fal.ai d'abord !")
            return
        try:
            import os
            import fal_client
            os.environ["FAL_KEY"] = key
            fal_client.run("fal-ai/ping", arguments={})
            QMessageBox.information(self, "✓ Connexion OK", "Clé fal.ai valide !")
        except ImportError:
            QMessageBox.warning(
                self, "fal-client manquant",
                "Installe le client :\n\npip install fal-client")
        except Exception as e:
            err = str(e)
            if "401" in err or "unauthorized" in err.lower():
                QMessageBox.critical(self, "Clé invalide", "La clé API fal.ai est incorrecte.")
            else:
                QMessageBox.information(
                    self, "✓ Client OK",
                    f"fal-client chargé. La clé sera testée à la première génération.\n\n"
                    f"({err[:100]})")

    def test_anthropic_connection(self):
        from PyQt6.QtWidgets import QMessageBox
        key = self._anthropic_input.text().strip()
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
                "Installe le client :\n\npip install anthropic")
        except Exception as e:
            err = str(e)
            if "401" in err or "authentication" in err.lower() or "invalid" in err.lower():
                QMessageBox.critical(self, "Clé invalide", "La clé API Anthropic est incorrecte.")
            else:
                QMessageBox.critical(self, "Erreur Anthropic", f"Erreur : {err[:200]}")

    def test_openai_connection(self):
        from PyQt6.QtWidgets import QMessageBox
        key = self._openai_input.text().strip()
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
        from PyQt6.QtWidgets import QMessageBox
        key = self._mistral_input.text().strip()
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
        from PyQt6.QtWidgets import QMessageBox
        base = (self._kimi_url_input.text().strip()
                or "https://api.moonshot.ai/v1").rstrip("/")
        key = self._kimi_input.text().strip()
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
        from PyQt6.QtWidgets import QMessageBox
        base = (self._glm_url_input.text().strip()
                or "https://open.bigmodel.cn/api/paas/v4").rstrip("/")
        key = self._glm_input.text().strip()
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

    def _test_connection(self):
        host = self._host_input.text().strip() or "localhost"
        port = self._port_spin.value()
        self._test_lbl.setText("Connexion…")
        self._test_lbl.setStyleSheet(
            f"color:#f5a623;font-size:11px;background:transparent;border:none;"
        )

        from PyQt6.QtCore import QThread, pyqtSignal as _sig

        class _TestWorker(QThread):
            done = _sig(str, bool)

            def __init__(self, h, p):
                super().__init__()
                self._h, self._p = h, p

            def run(self):
                try:
                    from resolume.client import ResolumeClient
                    info = ResolumeClient(self._h, self._p).get_product_info()
                    if info:
                        product = info.get("product", "Resolume")
                        version = info.get("version", "")
                        self.done.emit(f"✓  {product} {version} — connecté sur {self._h}:{self._p}", True)
                    else:
                        self.done.emit(f"✗  Aucune réponse de {self._h}:{self._p}", False)
                except Exception as e:
                    self.done.emit(f"✗  Erreur : {e}", False)

        self._test_worker = _TestWorker(host, port)
        self._test_worker.done.connect(self._on_test_done)
        self._test_worker.finished.connect(self._test_worker.deleteLater)
        self._test_worker.start()

    def _on_test_done(self, msg: str, ok: bool):
        color = CP["accent"] if ok else "#e05c5c"
        self._test_lbl.setText(translate(msg))
        self._test_lbl.setStyleSheet(
            f"color:{color};font-size:11px;background:transparent;border:none;"
        )
