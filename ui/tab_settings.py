import os
from PyQt6.QtWidgets import (
    QScrollArea, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLineEdit, QPushButton, QMessageBox, QFileDialog, QLabel,
)
from PyQt6.QtCore import Qt
from ui.styles import C
from ui.widgets import section_label, divider, combo, HelpBlock
from core.config import load_config, save_config, get_output_dir


class TabSettings(QScrollArea):
    def __init__(self):
        super().__init__()
        self.setWidgetResizable(True)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        container = QWidget()
        self.setWidget(container)
        lay = QVBoxLayout(container)
        lay.setContentsMargins(20, 20, 20, 20)
        lay.setSpacing(16)

        lay.addWidget(HelpBlock("Paramètres — Clés API et préférences", [
            "▸ Clé fal.ai : requise pour générer des vidéos réelles via Seedance 2.0. Sans clé → mode mock.",
            "▸ Clé Anthropic : requise pour l'assistant Claude (formatage scénario, génération storyboard, optimisation prompts).",
            "▸ Clé Nano Banana : requise pour la génération de portraits de personnages (page Castings).",
            "▸ Dossier de sortie : répertoire local où sont sauvegardés les clips générés.",
        ], C))

        cfg = load_config()

        # ── Clé API fal.ai ────────────────────────────────────────────────────
        lay.addWidget(section_label("Clé API fal.ai"))
        self.api_input = QLineEdit()
        self.api_input.setPlaceholderText("fal_••••••••••••••••••••••••")
        self.api_input.setText(cfg.get("api_key", ""))
        self.api_input.setEchoMode(QLineEdit.EchoMode.Password)
        lay.addWidget(self.api_input)

        lay.addWidget(divider())

        # ── Clé API Anthropic ─────────────────────────────────────────────────
        lay.addWidget(section_label("Clé API Anthropic (bouton Améliorer)"))
        self.anthropic_input = QLineEdit()
        self.anthropic_input.setPlaceholderText("sk-ant-••••••••••••••••••••••••")
        self.anthropic_input.setText(cfg.get("anthropic_key", ""))
        self.anthropic_input.setEchoMode(QLineEdit.EchoMode.Password)
        lay.addWidget(self.anthropic_input)

        hint_ant = QLabel("Utilisée par le bouton ✦ Améliorer pour optimiser tes prompts via Claude.")
        hint_ant.setWordWrap(True)
        hint_ant.setStyleSheet(
            f"color:{C['text_dim']};font-size:10px;font-family:'Consolas',monospace;"
        )
        lay.addWidget(hint_ant)

        lay.addWidget(divider())

        # ── Paramètres génération ─────────────────────────────────────────────
        lay.addWidget(section_label("Paramètres par défaut"))

        g = QGridLayout()
        g.setSpacing(12)
        self.cb_model = combo(["seedance-2.0", "seedance-2.0-fast"])
        self.cb_dur   = combo(["5", "10", "15"])
        self.cb_res   = combo(["720p", "480p"])

        for col_idx, lbl, widget in [
            (0, "Modèle",    self.cb_model),
            (1, "Durée (s)", self.cb_dur),
        ]:
            gw = QWidget()
            l = QVBoxLayout(gw)
            l.setContentsMargins(0, 0, 0, 0)
            l.setSpacing(6)
            l.addWidget(section_label(lbl))
            l.addWidget(widget)
            g.addWidget(gw, 0, col_idx)

        gw3 = QWidget()
        l3 = QVBoxLayout(gw3)
        l3.setContentsMargins(0, 0, 0, 0)
        l3.setSpacing(6)
        l3.addWidget(section_label("Résolution"))
        l3.addWidget(self.cb_res)
        g.addWidget(gw3, 1, 0)
        lay.addLayout(g)

        lay.addWidget(divider())

        # ── Dossier de sortie ─────────────────────────────────────────────────
        lay.addWidget(section_label("Dossier de sortie des clips"))

        dir_row = QHBoxLayout()
        dir_row.setSpacing(8)
        self.dir_input = QLineEdit()
        self.dir_input.setPlaceholderText(get_output_dir(cfg))
        self.dir_input.setText(cfg.get("output_dir", ""))
        self.dir_input.setReadOnly(True)
        self.dir_input.setStyleSheet(
            f"QLineEdit{{background:{C['bg2']};border:1px solid {C['border']};"
            f"border-radius:6px;color:{C['text_secondary']};font-size:11px;"
            f"font-family:'Consolas',monospace;padding:8px 12px;}}"
        )

        btn_browse = QPushButton("Parcourir")
        btn_browse.setFixedWidth(90)
        btn_browse.setMinimumHeight(38)
        btn_browse.setStyleSheet(f"""
            QPushButton{{background:{C['bg3']};color:{C['text_secondary']};
            border:1px solid {C['border']};border-radius:6px;font-size:11px;font-weight:700;}}
            QPushButton:hover{{background:{C['border_bright']};color:{C['text_primary']};}}
        """)
        btn_browse.clicked.connect(self._browse_dir)
        dir_row.addWidget(self.dir_input, 1)
        dir_row.addWidget(btn_browse)
        lay.addLayout(dir_row)

        hint = QLabel(f"Par défaut : {get_output_dir(cfg)}")
        hint.setStyleSheet(
            f"color:{C['text_dim']};font-size:10px;font-family:'Consolas',monospace;"
        )
        lay.addWidget(hint)

        lay.addWidget(divider())

        # ── Boutons ───────────────────────────────────────────────────────────
        btn_row = QHBoxLayout()
        btn_save = QPushButton("💾  Sauvegarder")
        btn_save.setMinimumHeight(42)
        btn_save.clicked.connect(self.save)

        btn_test = QPushButton("Tester API")
        btn_test.setFixedWidth(110)
        btn_test.setMinimumHeight(42)
        btn_test.setStyleSheet(f"""
            QPushButton{{background:{C['bg3']};color:{C['text_secondary']};
            border:1px solid {C['border']};border-radius:8px;font-size:11px;font-weight:700;}}
            QPushButton:hover{{background:{C['border']};color:{C['text_primary']};}}
        """)
        btn_test.clicked.connect(self.test_connection)

        btn_row.addWidget(btn_save)
        btn_row.addWidget(btn_test)
        lay.addLayout(btn_row)
        lay.addStretch()

    def _browse_dir(self):
        path = QFileDialog.getExistingDirectory(self, "Choisir le dossier de sortie")
        if path:
            self.dir_input.setText(path)

    def save(self):
        cfg = {
            "api_key":            self.api_input.text(),
            "anthropic_key":      self.anthropic_input.text(),
            "default_model":      self.cb_model.currentText(),
            "default_duration":   self.cb_dur.currentText(),
            "default_resolution": self.cb_res.currentText(),
            "output_dir":         self.dir_input.text(),
        }
        save_config(cfg)
        QMessageBox.information(self, "Sauvegardé", "Configuration sauvegardée ✓")

    def test_connection(self):
        key = self.api_input.text().strip()
        if not key:
            QMessageBox.warning(self, "Clé manquante", "Entre ta clé API fal.ai d'abord !")
            return
        try:
            import os
            import fal_client
            os.environ["FAL_KEY"] = key
            # Ping léger : liste les modèles accessibles
            fal_client.run("fal-ai/ping", arguments={})
            QMessageBox.information(self, "✓ Connexion OK", "Clé fal.ai valide !\nMode réel activé.")
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
                    f"fal-client chargé. Clé enregistrée — le test complet\n"
                    f"se fera à la première génération.\n\n({err[:80]})"
                )
