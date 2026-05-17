import os
import webbrowser
from PyQt6.QtWidgets import (
    QScrollArea, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QLineEdit, QPushButton, QMessageBox,
)
from PyQt6.QtCore import Qt
from ui.styles import CP
from ui.icons import load_icon
from ui.davinci_panel import DaVinciPanel
from core.config import load_config, save_config
from davinci.bridge import install_pandora_send

_FAL_KEYS_URL       = "https://fal.ai/dashboard/keys"
_ANTHROPIC_KEYS_URL = "https://console.anthropic.com/settings/keys"


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
    btn = QPushButton("?")
    btn.setFixedSize(24, 24)
    btn.setToolTip(tooltip)
    btn.setCursor(Qt.CursorShape.PointingHandCursor)
    btn.setStyleSheet(
        f"QPushButton{{background:{CP['bg3']};color:{CP['text_secondary']};"
        f"border:1px solid {CP['border_bright']};border-radius:12px;"
        f"font-size:11px;font-weight:700;}}"
        f"QPushButton:hover{{color:{CP['accent']};border-color:{CP['accent_dim']};"
        f"background:rgba(78,205,196,0.12);}}"
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

        # ── DaVinci Resolve ───────────────────────────────────────────────────
        dvr_row = QHBoxLayout()
        dvr_row.addWidget(_section("Connexion DaVinci Resolve"))
        dvr_row.addStretch()
        dvr_row.addWidget(_info_btn(
            "Guide de connexion DaVinci Resolve",
            lambda: self._show_davinci_help(),
        ))
        lay.addLayout(dvr_row)

        self._davinci = DaVinciPanel()
        self._davinci.setStyleSheet(
            f"background:{CP['bg2']};border:1px solid {CP['border']};"
            f"border-radius:10px;"
        )
        lay.addWidget(self._davinci)

        # Bouton installation script pandora_send (AI Studio → Modifier depuis DaVinci)
        _send_row = QHBoxLayout()
        _send_row.setContentsMargins(0, 4, 0, 0)
        _btn_send = QPushButton("⚙  Installer le script PANDORA dans DaVinci Resolve Studio")
        _btn_send.setFixedHeight(30)
        _btn_send.setCursor(Qt.CursorShape.PointingHandCursor)
        _btn_send.setStyleSheet(
            f"QPushButton{{background:{CP['bg3']};color:{CP['text_secondary']};"
            f"border:1px solid {CP['border']};border-radius:6px;"
            f"font-size:11px;padding:0 14px;}}"
            f"QPushButton:hover{{background:{CP['bg2']};}}"
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
        _lbl_send = QLabel("Script pour DaVinci Resolve Studio → AI Studio → Modifier depuis DaVinci Resolve")
        _lbl_send.setStyleSheet(
            f"color:{CP['text_dim']};font-size:10px;font-family:'Consolas',monospace;"
        )
        _send_row.addWidget(_btn_send)
        _send_row.addSpacing(10)
        _send_row.addWidget(_lbl_send)
        _send_row.addStretch()
        lay.addLayout(_send_row)

        lay.addWidget(_divider())

        # ── Clés API ──────────────────────────────────────────────────────────
        api_row = QHBoxLayout()
        api_row.addWidget(_section("Clés API"))
        api_row.addStretch()
        api_row.addWidget(_info_btn(
            "Comment obtenir les clés API",
            lambda: self._show_api_help(),
        ))
        lay.addLayout(api_row)

        cfg = load_config()

        # fal.ai
        fal_lbl_row = QHBoxLayout()
        lbl_fal = QLabel(
            "fal.ai — Seedance 2.0 (vidéo)  ·  Nano Banana (portraits, accessoires, HMC)"
        )
        lbl_fal.setStyleSheet(
            f"color:{CP['text_secondary']};font-size:12px;background:transparent;"
        )
        fal_lbl_row.addWidget(lbl_fal, 1)
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
        lbl_ant = QLabel("Anthropic — Claude  (optimisation prompts, scénario, storyboard)")
        lbl_ant.setStyleSheet(
            f"color:{CP['text_secondary']};font-size:12px;background:transparent;"
        )
        ant_lbl_row.addWidget(lbl_ant, 1)
        ant_lbl_row.addWidget(_link_btn("⇗  Obtenir une clé Anthropic", _ANTHROPIC_KEYS_URL))
        lay.addLayout(ant_lbl_row)

        self.anthropic_input = QLineEdit()
        self.anthropic_input.setPlaceholderText("sk-ant-••••••••••••••••••••••••")
        self.anthropic_input.setText(cfg.get("anthropic_key", ""))
        self.anthropic_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.anthropic_input.setStyleSheet(_field_style())
        lay.addWidget(self.anthropic_input)
        lay.addWidget(_divider())

        # ── Sauvegarde / Test ─────────────────────────────────────────────────
        btn_row = QHBoxLayout()

        btn_save = QPushButton("💾  Sauvegarder")
        btn_save.setMinimumHeight(44)
        btn_save.setStyleSheet(f"""
            QPushButton{{
                background:{CP['accent']};color:#07080f;border:none;
                border-radius:8px;font-size:13px;font-weight:700;
                letter-spacing:1px;padding:0 24px;
            }}
            QPushButton:hover{{background:#6eded6;}}
            QPushButton:pressed{{background:{CP['accent_dim']};color:#ffffff;}}
        """)
        btn_save.clicked.connect(self.save)

        btn_test = QPushButton("Tester API fal.ai")
        btn_test.setMinimumHeight(44)
        btn_test.setStyleSheet(f"""
            QPushButton{{
                background:transparent;color:{CP['text_secondary']};
                border:1px solid {CP['border']};border-radius:8px;
                font-size:12px;font-weight:700;padding:0 20px;
            }}
            QPushButton:hover{{background:{CP['bg3']};color:{CP['text_primary']};}}
        """)
        btn_test.clicked.connect(self.test_connection)

        btn_test_ant = QPushButton("Tester API Anthropic")
        btn_test_ant.setMinimumHeight(44)
        btn_test_ant.setStyleSheet(f"""
            QPushButton{{
                background:transparent;color:{CP['text_secondary']};
                border:1px solid {CP['border']};border-radius:8px;
                font-size:12px;font-weight:700;padding:0 20px;
            }}
            QPushButton:hover{{background:{CP['bg3']};color:{CP['text_primary']};}}
        """)
        btn_test_ant.clicked.connect(self.test_anthropic_connection)

        btn_row.addWidget(btn_save)
        btn_row.addWidget(btn_test)
        btn_row.addWidget(btn_test_ant)
        btn_row.addStretch()
        lay.addLayout(btn_row)
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

    # ── Sauvegarde ────────────────────────────────────────────────────────────

    def save(self):
        cfg = load_config()
        cfg.update({
            "api_key":       self.api_input.text(),
            "anthropic_key": self.anthropic_input.text(),
        })
        save_config(cfg)
        QMessageBox.information(self, "Sauvegardé", "Configuration sauvegardée ✓")

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
