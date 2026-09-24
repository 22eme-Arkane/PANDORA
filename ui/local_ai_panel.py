"""ui/local_ai_panel.py — Le serveur IA local OpenAI-compatible, dans les Paramètres.

Préréglage (LM Studio, llama.cpp, vLLM, Jan, autre), adresse, modèle, clé
facultative, « Tester » (liste les modèles chargés sur le serveur et remplit
le choix), bandeau d'installation du module (ui/external_banner) et accès à
sa fenêtre (ui/dialog_external). Chantier IA locales du 24/09/2026.

Composant NEUTRE : les deux pages Paramètres l'insèrent tel quel. Il ne
sauvegarde rien lui-même — il émet `changed`, la page appelle `apply(cfg)`
dans sa sauvegarde automatique (core/config.save_config remplace tout le
fichier : la page reste la seule à écrire).
"""

from __future__ import annotations

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QComboBox, QLineEdit, QPushButton,
)

from core import local_llm as _ll
from core.i18n import translate
from ui.styles import CP

_AMBER = "#f0b429"


def _field_style() -> str:
    return (f"QLineEdit{{background:{CP['bg2']};border:1px solid {CP['border']};"
            f"border-radius:6px;color:{CP['text_primary']};font-size:12px;padding:0 10px;}}"
            f"QLineEdit:focus{{border-color:{CP['accent']};}}")


def _combo_style() -> str:
    return (f"QComboBox{{background:{CP['bg2']};border:1px solid {CP['border']};"
            f"border-radius:6px;color:{CP['text_primary']};font-size:12px;padding:0 10px;}}"
            f"QComboBox::drop-down{{border:none;width:22px;}}"
            f"QComboBox QAbstractItemView{{background:{CP['bg3']};"
            f"border:1px solid {CP['border_bright']};color:{CP['text_primary']};"
            f"selection-background-color:{CP['accent_dim']};}}")


def _btn(text: str, accent: str) -> QPushButton:
    b = QPushButton(text)
    b.setFixedHeight(32)
    b.setCursor(Qt.CursorShape.PointingHandCursor)
    b.setStyleSheet(
        f"QPushButton{{background:transparent;border:1px solid {accent};border-radius:6px;"
        f"color:{accent};font-size:11px;font-weight:600;padding:0 14px;}}"
        f"QPushButton:hover{{background:{CP['bg3']};}}")
    return b


class LocalAIPanel(QWidget):
    changed = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet("background:transparent;")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 4, 0, 0)
        lay.setSpacing(8)

        hint = QLabel(translate(
            "Serveur OpenAI-compatible qui tourne sur votre machine (ou sur une machine du réseau). "
            "Choisissez le logiciel, « Tester » liste les modèles qu'il a chargés."))
        hint.setWordWrap(True)
        hint.setStyleSheet(f"color:{CP['text_secondary']};font-size:11px;background:transparent;")
        lay.addWidget(hint)

        row1 = QHBoxLayout()
        row1.setSpacing(8)
        self.preset_combo = QComboBox()
        self.preset_combo.setFixedHeight(32)
        self.preset_combo.setStyleSheet(_combo_style())
        for key, p in _ll.LOCAL_PRESETS.items():
            self.preset_combo.addItem(translate(p["name"]) + f"  ·  {p['url']}", key)
        self.preset_combo.currentIndexChanged.connect(self._on_preset)
        row1.addWidget(self.preset_combo, 1)
        self._b_module = _btn(translate("Installer / Guide…"), CP["accent2"])
        self._b_module.clicked.connect(self._open_module)
        row1.addWidget(self._b_module)
        lay.addLayout(row1)

        row2 = QHBoxLayout()
        row2.setSpacing(8)
        self.url_input = QLineEdit()
        self.url_input.setFixedHeight(32)
        self.url_input.setStyleSheet(_field_style())
        self.url_input.textChanged.connect(self._emit)
        row2.addWidget(self.url_input, 1)
        self._b_test = _btn("✓  " + translate("Tester"), CP["accent"])
        self._b_test.clicked.connect(self._test)
        row2.addWidget(self._b_test)
        lay.addLayout(row2)

        row3 = QHBoxLayout()
        row3.setSpacing(8)
        self.model_combo = QComboBox()
        self.model_combo.setEditable(True)
        self.model_combo.setFixedHeight(32)
        self.model_combo.setStyleSheet(_combo_style())
        self.model_combo.lineEdit().setPlaceholderText(
            translate("Identifiant du modèle chargé (« Tester » les liste)"))
        self.model_combo.editTextChanged.connect(self._emit)
        row3.addWidget(self.model_combo, 2)
        self.key_input = QLineEdit()
        self.key_input.setFixedHeight(32)
        self.key_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.key_input.setPlaceholderText(translate("Clé (vide pour un serveur local)"))
        self.key_input.setStyleSheet(_field_style())
        self.key_input.textChanged.connect(self._emit)
        row3.addWidget(self.key_input, 1)
        lay.addLayout(row3)

        self._state = QLabel("")
        self._state.setWordWrap(True)
        self._state.setStyleSheet(f"color:{CP['text_dim']};font-size:10px;background:transparent;")
        lay.addWidget(self._state)

        from ui.external_banner import ExternalBanner
        self._banner = ExternalBanner()
        lay.addWidget(self._banner)

        self._loading = False
        self._on_preset()

    # ── Config ───────────────────────────────────────────────────────────────

    def load(self, cfg: dict) -> None:
        self._loading = True
        try:
            key = _ll.preset_key(cfg)
            idx = self.preset_combo.findData(key)
            self.preset_combo.setCurrentIndex(max(0, idx))
            self.url_input.setText((cfg.get("local_url") or "").strip())
            self.key_input.setText((cfg.get("local_key") or "").strip())
            known = list((cfg.get("ai_available_models") or {}).get("local") or [])
            self._set_models(known, (cfg.get("local_model") or "").strip())
            self._on_preset()
        finally:
            self._loading = False

    def apply(self, cfg: dict) -> dict:
        cfg["local_preset"] = self.current_preset()
        cfg["local_url"] = self.url_input.text().strip()
        cfg["local_model"] = self.model_combo.currentText().strip()
        cfg["local_key"] = self.key_input.text().strip()
        return cfg

    def current_preset(self) -> str:
        return str(self.preset_combo.currentData() or _ll.DEFAULT_PRESET)

    def base_url(self) -> str:
        return self.url_input.text().strip().rstrip("/") or _ll.preset_url(self.current_preset())

    # ── Slots ────────────────────────────────────────────────────────────────

    def _set_models(self, names: list, current: str) -> None:
        self.model_combo.blockSignals(True)
        self.model_combo.clear()
        for n in names:
            self.model_combo.addItem(n)
        if current and current not in names:
            self.model_combo.addItem(current)
        self.model_combo.setEditText(current)
        self.model_combo.blockSignals(False)

    def _on_preset(self, *_):
        p = _ll.preset(self.current_preset())
        self.url_input.setPlaceholderText(translate("Adresse") + f" (défaut : {p['url']})")
        self._b_module.setVisible(bool(p["external"]))
        if self.isVisible():
            self._banner.set_engine("local:" + self.current_preset() if p["external"] else "")
        self._emit()

    def _emit(self, *_):
        if not self._loading:
            self.changed.emit()

    def showEvent(self, event):
        super().showEvent(event)
        p = _ll.preset(self.current_preset())
        self._banner.set_engine("local:" + self.current_preset() if p["external"] else "")

    def _test(self):
        """Interroge /models (serveur local : réponse immédiate) et remplit le choix."""
        base = self.base_url()
        key = self.key_input.text().strip()
        try:
            import requests
            r = requests.get(f"{base}/models",
                             headers={"Authorization": f"Bearer {key or 'local'}"}, timeout=8)
            if r.status_code in (401, 403):
                self._state.setText("⚠  " + translate("Le serveur refuse la clé."))
                self._state.setStyleSheet(f"color:{_AMBER};font-size:10px;background:transparent;")
                return
            r.raise_for_status()
            names = [str(m.get("id") if isinstance(m, dict) else m)
                     for m in (r.json().get("data") or [])]
            names = [n for n in names if _ll.is_chat_model(n)]
            current = self.model_combo.currentText().strip()
            self._set_models(names, current or (names[0] if names else ""))
            if names:
                self._state.setText("✓  " + translate("Serveur joignable") + f" ({base}) — "
                                    + translate("modèles chargés") + f" : {', '.join(names[:6])}"
                                    + (" …" if len(names) > 6 else ""))
                self._state.setStyleSheet(f"color:{CP['accent']};font-size:10px;background:transparent;")
            else:
                self._state.setText("⚠  " + translate("Serveur joignable, mais aucun modèle chargé — chargez-en un dans l'application."))
                self._state.setStyleSheet(f"color:{_AMBER};font-size:10px;background:transparent;")
            self._emit()
        except Exception:
            self._state.setText("⚠  " + translate("Serveur injoignable sur") + f" {base} — "
                                + translate("lancez-le, ou installez-le (« Installer / Guide… »)."))
            self._state.setStyleSheet(f"color:{_AMBER};font-size:10px;background:transparent;")
        self._banner.refresh()

    def _open_module(self):
        ext = _ll.external_for_preset(self.current_preset())
        if not ext:
            return
        from ui.dialog_external import ExternalDialog
        ExternalDialog(ext, self).exec()
        self._banner.refresh()
