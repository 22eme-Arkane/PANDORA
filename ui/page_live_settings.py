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
        lay.addWidget(_section_title("CLÉS API"))
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

        key_row = QHBoxLayout()
        key_row.setSpacing(12)
        key_row.addWidget(_key_label("Clé fal.ai :"))
        self._api_key_input = _input("xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx:xxxx…", 0)
        self._api_key_input.setEchoMode(QLineEdit.EchoMode.Password)
        key_row.addWidget(self._api_key_input, 1)
        key_row.addWidget(_link_btn("⇗  Clés", "https://fal.ai/dashboard/keys"))
        key_row.addWidget(_link_btn("⇗  Crédits", "https://fal.ai/dashboard/billing"))
        ac.addLayout(key_row)

        ant_row = QHBoxLayout()
        ant_row.setSpacing(12)
        ant_row.addWidget(_key_label("Clé Anthropic (Claude) :"))
        self._anthropic_input = _input("sk-ant-…", 0)
        self._anthropic_input.setEchoMode(QLineEdit.EchoMode.Password)
        ant_row.addWidget(self._anthropic_input, 1)
        ant_row.addWidget(_link_btn("⇗  Clés", "https://console.anthropic.com/settings/keys"))
        ant_row.addWidget(_link_btn("⇗  Crédits", "https://console.anthropic.com/settings/billing"))
        ac.addLayout(ant_row)

        # ── Assistant IA (texte) — même réglage que Cinéma (config partagée) ──
        from PyQt6.QtWidgets import QComboBox
        ai_row = QHBoxLayout()
        ai_row.setSpacing(12)
        ai_row.addWidget(_key_label("Assistant IA (texte) :"))
        self._AI_CHOICES = [
            ("Claude (Anthropic) — défaut",       "anthropic", "claude-sonnet-4-6"),
            ("Fable 5 (Anthropic) — qualité max", "anthropic", "claude-fable-5"),
            ("Mistral — expérimental",            "mistral",   ""),
            ("Ollama local — expérimental",       "ollama",    ""),
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

        mis_row = QHBoxLayout()
        mis_row.setSpacing(12)
        mis_row.addWidget(_key_label("Clé Mistral :"))
        self._mistral_input = _input("Clé API Mistral", 0)
        self._mistral_input.setEchoMode(QLineEdit.EchoMode.Password)
        mis_row.addWidget(self._mistral_input, 1)
        self._mistral_row_widgets = (mis_row.itemAt(0).widget(), self._mistral_input)
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

        def _on_ai_changed(*_):
            prov = (self._ai_combo.currentData() or ("anthropic", ""))[0]
            for wdg in self._mistral_row_widgets:
                wdg.setVisible(prov == "mistral")
            for wdg in self._ollama_row_widgets:
                wdg.setVisible(prov == "ollama")
        self._ai_combo.currentIndexChanged.connect(_on_ai_changed)
        self._on_ai_changed = _on_ai_changed

        btn_save = QPushButton("Enregistrer")
        btn_save.setFixedHeight(36)
        btn_save.setFixedWidth(140)
        btn_save.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_save.setStyleSheet(
            f"QPushButton{{background:{CP['accent']};color:#07080f;border:none;"
            f"border-radius:8px;font-size:12px;font-weight:700;padding:0 16px;}}"
            f"QPushButton:hover{{background:#6eded6;}}"
            f"QPushButton:pressed{{background:{CP['accent_dim']};color:#fff;}}"
        )
        btn_save.clicked.connect(self._save_api_key)
        ac.addWidget(btn_save)

        lay.addWidget(api_card)
        lay.addStretch()

        root.addWidget(content, 1)

        self._load_settings()

    def _load_settings(self):
        from core.config import load_config
        cfg = load_config()
        key = cfg.get("api_key", "")
        if key:
            self._api_key_input.setText(key)
        ant = cfg.get("anthropic_key", "")
        if ant:
            self._anthropic_input.setText(ant)
        # Assistant IA (texte)
        _cur = (cfg.get("ai_provider", "anthropic"), cfg.get("ai_model_creative", ""))
        for i, (_, prov, model) in enumerate(self._AI_CHOICES):
            if prov == _cur[0] and (prov != "anthropic" or model == (_cur[1] or "claude-sonnet-4-6")):
                self._ai_combo.setCurrentIndex(i)
                break
        self._mistral_input.setText(cfg.get("mistral_key", ""))
        self._ollama_url_input.setText(cfg.get("ollama_url", ""))
        self._ollama_model_input.setText(cfg.get("ollama_model", ""))
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
        cfg["mistral_key"]       = self._mistral_input.text().strip()
        cfg["ollama_url"]        = self._ollama_url_input.text().strip()
        cfg["ollama_model"]      = self._ollama_model_input.text().strip()
        cfg["resolume_host"] = self._host_input.text().strip() or "localhost"
        cfg["resolume_port"] = self._port_spin.value()
        save_config(cfg)
        from core.ai_provider import refresh_name_cache
        refresh_name_cache()   # le nom de l'assistant change → libellés au prochain démarrage
        self._test_lbl.setText("✓  Paramètres enregistrés.")
        self._test_lbl.setStyleSheet(
            f"color:{CP['accent']};font-size:11px;background:transparent;border:none;"
        )

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
