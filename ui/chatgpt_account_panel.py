"""ui/chatgpt_account_panel.py — Le compte ChatGPT (forfait Plus / Pro), dans les Paramètres.

« Continuer avec ChatGPT » ouvre la page de connexion d'OpenAI dans le
navigateur ; les jetons restent sur ce poste (api/chatgpt_plan). Le panneau
montre l'état du compte, le modèle choisi dans le catalogue DU COMPTE, le lien
« Gérer l'utilisation » et la case de repli sur la clé API — décochée par
défaut : le repli doit être un choix explicite de l'utilisateur (conditions
OpenAI du 29/09/2026). Chantier du 04/10/2026.

Composant NEUTRE : les deux pages Paramètres l'insèrent tel quel. Il ne
sauvegarde rien lui-même — il émet `changed`, la page appelle `apply(cfg)`
(core/config.save_config remplace tout le fichier : la page reste la seule à
écrire). La connexion tourne hors du thread de l'interface (core/background).
"""

from __future__ import annotations

import threading

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QCheckBox, QComboBox, QHBoxLayout, QLabel, QMessageBox, QPushButton, QVBoxLayout, QWidget,
)

from core.i18n import translate
from ui.styles import CP

USAGE_URL = "https://chatgpt.com/settings/usage"

PRIVACY_NOTICE = (
    "PANDORA va ouvrir la page de connexion d'OpenAI dans votre navigateur.\n\n"
    "• PANDORA reçoit votre nom, votre adresse e-mail et des jetons d'accès. Ils sont "
    "conservés UNIQUEMENT sur cet ordinateur (chiffrés sous Windows, dans un fichier "
    "réservé à votre compte sur macOS) et ne sont envoyés qu'à OpenAI.\n"
    "• Les requêtes texte de PANDORA (vos actions, et les automatismes que vous avez "
    "activés, comme « Recomposer automatiquement ») utiliseront votre forfait ChatGPT "
    "Plus ou Pro.\n"
    "• Vous pouvez vous déconnecter ici, ou dans ChatGPT : Réglages → Sécurité → "
    "Connexions.\n\n"
    "Continuer ?"
)
WELCOME = ("Les requêtes éligibles de PANDORA utilisent votre forfait ChatGPT. "
           "Gérez l'utilisation dans vos réglages ChatGPT.")


def _combo_style() -> str:
    return (f"QComboBox{{background:{CP['bg2']};border:1px solid {CP['border']};"
            f"border-radius:6px;color:{CP['text_primary']};font-size:12px;padding:0 10px;}}"
            f"QComboBox::drop-down{{border:none;width:22px;}}"
            f"QComboBox QAbstractItemView{{background:{CP['bg3']};"
            f"border:1px solid {CP['border_bright']};color:{CP['text_primary']};"
            f"selection-background-color:{CP['accent_dim']};}}")


def _btn(text: str, accent: str, filled: bool = False) -> QPushButton:
    b = QPushButton(text)
    b.setFixedHeight(32)
    b.setCursor(Qt.CursorShape.PointingHandCursor)
    if filled:
        b.setStyleSheet(
            f"QPushButton{{background:{accent};border:none;border-radius:6px;"
            f"color:#07080f;font-size:11px;font-weight:700;padding:0 16px;}}"
            f"QPushButton:hover{{background:{CP['accent']};}}"
            f"QPushButton:disabled{{background:{CP['bg3']};color:{CP['text_dim']};}}")
    else:
        b.setStyleSheet(
            f"QPushButton{{background:transparent;border:1px solid {accent};border-radius:6px;"
            f"color:{accent};font-size:11px;font-weight:600;padding:0 14px;}}"
            f"QPushButton:hover{{background:{CP['bg3']};}}"
            f"QPushButton:disabled{{color:{CP['text_dim']};border-color:{CP['border']};}}")
    return b


class ChatGPTAccountPanel(QWidget):
    changed = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet("background:transparent;")
        self._cancel: threading.Event | None = None
        self._loading = False
        self._saved_model = ""
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 4, 0, 0)
        lay.setSpacing(8)

        hint = QLabel(translate(
            "Utilise votre abonnement ChatGPT Plus ou Pro pour les tâches texte de PANDORA, "
            "sans clé API. La connexion se fait dans votre navigateur, sur le site d'OpenAI."))
        hint.setWordWrap(True)
        hint.setStyleSheet(f"color:{CP['text_secondary']};font-size:11px;background:transparent;")
        lay.addWidget(hint)

        row = QHBoxLayout()
        row.setSpacing(8)
        self._dot = QLabel("●")
        self._dot.setFixedWidth(14)
        row.addWidget(self._dot)
        self._status = QLabel("")
        self._status.setWordWrap(True)
        row.addWidget(self._status, 1)
        self._b_connect = _btn(translate("Continuer avec ChatGPT"), CP["accent"], filled=True)
        self._b_connect.clicked.connect(self._on_connect)
        row.addWidget(self._b_connect)
        self._b_resume = _btn(translate("Réessayer le forfait"), CP["accent2"])
        self._b_resume.clicked.connect(self._on_resume)
        row.addWidget(self._b_resume)
        self._b_disconnect = _btn(translate("Se déconnecter"), CP["red"])
        self._b_disconnect.clicked.connect(self._on_disconnect)
        row.addWidget(self._b_disconnect)
        lay.addLayout(row)

        mrow = QHBoxLayout()
        mrow.setSpacing(8)
        mlbl = QLabel(translate("Modèle"))
        mlbl.setStyleSheet(f"color:{CP['text_secondary']};font-size:11px;background:transparent;")
        mrow.addWidget(mlbl)
        self.model_combo = QComboBox()
        self.model_combo.setFixedHeight(32)
        self.model_combo.setStyleSheet(_combo_style())
        self.model_combo.currentIndexChanged.connect(self._emit)
        mrow.addWidget(self.model_combo, 1)
        self._usage = QLabel(f'<a href="{USAGE_URL}" style="color:{CP["accent2"]};">'
                             f'{translate("Gérer l’utilisation")}</a>')
        self._usage.setOpenExternalLinks(True)
        self._usage.setStyleSheet("background:transparent;font-size:11px;")
        mrow.addWidget(self._usage)
        lay.addLayout(mrow)

        self.fallback_cb = QCheckBox(translate(
            "Utiliser ma clé API OpenAI quand le forfait ChatGPT est indisponible "
            "(facturé à l'usage)"))
        self.fallback_cb.setStyleSheet(
            f"QCheckBox{{color:{CP['text_secondary']};font-size:11px;background:transparent;}}")
        self.fallback_cb.toggled.connect(self._emit)
        lay.addWidget(self.fallback_cb)

        note = QLabel(translate(
            "Forfait Plus ou Pro requis. Pour l'instant, OpenAI coupe la session au bout d'une "
            "heure : PANDORA vous demandera alors de vous reconnecter."))
        note.setWordWrap(True)
        note.setStyleSheet(f"color:{CP['text_dim']};font-size:10px;font-style:italic;"
                           f"background:transparent;")
        lay.addWidget(note)
        self.refresh()

    # ── Configuration (la page sauvegarde) ────────────────────────────────────

    def _emit(self, *_):
        if not self._loading:
            self.changed.emit()

    def load(self, cfg: dict):
        self._loading = True
        try:
            self._saved_model = (cfg.get("chatgpt_model") or "").strip()
            self.fallback_cb.setChecked(bool(cfg.get("chatgpt_api_fallback")))
            self.refresh()
        finally:
            self._loading = False

    def apply(self, cfg: dict):
        cfg["chatgpt_model"] = self.model_combo.currentData() or ""
        cfg["chatgpt_api_fallback"] = bool(self.fallback_cb.isChecked())

    # ── État ──────────────────────────────────────────────────────────────────

    def refresh(self):
        """Relit l'état LOCAL du compte (fichier chiffré, aucun appel réseau)."""
        try:
            from api import chatgpt_plan as cp
            st = cp.status()
        except Exception:
            st = {"state": "disconnected", "email": "", "models": []}
        state = st.get("state", "disconnected")
        who = st.get("email") or st.get("name") or ""
        texts = {
            "connected": (CP["green"], translate("Connecté") + (f" : {who}" if who else "")
                          + "  ·  " + translate("Forfait ChatGPT utilisé")),
            "reauth_required": (CP["orange"], translate(
                "Session expirée : cliquez sur « Continuer avec ChatGPT » pour vous reconnecter.")),
            "paused": (CP["orange"], translate(
                "Limite d'utilisation atteinte : forfait en pause. Vérifiez vos réglages "
                "ChatGPT, puis « Réessayer le forfait ».")),
            "not_eligible": (CP["red"], translate(
                "Ce compte ne peut pas utiliser son forfait dans PANDORA (Plus ou Pro requis).")),
            "plan_off": (CP["orange"], translate(
                "Connecté, mais l'usage du forfait n'a pas été autorisé : reconnectez-vous et "
                "acceptez « Utiliser votre forfait ChatGPT ».")),
            "disconnected": (CP["text_dim"], translate("Non connecté")),
        }
        color, text = texts.get(state, texts["disconnected"])
        self._dot.setStyleSheet(f"color:{color};font-size:13px;background:transparent;")
        self._status.setText(text)
        self._status.setStyleSheet(f"color:{color};font-size:11px;background:transparent;")
        connecting = self._cancel is not None
        self._b_connect.setText(translate("Annuler la connexion") if connecting
                                else translate("Continuer avec ChatGPT"))
        self._b_connect.setVisible(connecting or state != "connected")
        self._b_resume.setVisible(state == "paused" and not connecting)
        self._b_disconnect.setVisible(state != "disconnected" and not connecting)
        self._fill_models(st.get("models") or [])

    def _fill_models(self, models: list):
        keep = self.model_combo.currentData() or self._saved_model
        was_loading = self._loading
        self._loading = True
        try:
            self.model_combo.clear()
            self.model_combo.addItem(translate("Premier modèle proposé par le compte"), "")
            for m in models:
                self.model_combo.addItem(m.get("display_name") or m.get("slug"), m.get("slug"))
            if keep and self.model_combo.findData(keep) < 0:
                self.model_combo.addItem(keep, keep)   # choix gardé même hors catalogue
            idx = self.model_combo.findData(keep)
            self.model_combo.setCurrentIndex(idx if idx >= 0 else 0)
        finally:
            self._loading = was_loading

    # ── Actions ───────────────────────────────────────────────────────────────

    def _on_connect(self):
        if self._cancel is not None:                    # « Annuler la connexion »
            self._cancel.set()
            return
        if QMessageBox.question(
                self, translate("Compte ChatGPT"), translate(PRIVACY_NOTICE),
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No) != QMessageBox.StandardButton.Yes:
            return
        from api import chatgpt_plan as cp
        from core.background import run_task
        self._cancel = threading.Event()
        cancel = self._cancel

        def work():
            try:
                return {"ok": True, "status": cp.connect(cancel=cancel)}
            except cp.SiwcError as exc:
                return {"ok": False, "code": exc.code, "message": cp.user_message(exc)}

        self.refresh()
        run_task(work, self._on_connect_done)

    def _on_connect_done(self, res):
        self._cancel = None
        self.refresh()
        res = res if isinstance(res, dict) else {}
        if not res.get("ok"):
            if res.get("code") not in ("cancelled", "access_denied"):
                QMessageBox.warning(self, translate("Compte ChatGPT"),
                                    translate(res.get("message") or res.get("error") or
                                              "Connexion impossible."))
            return
        self.changed.emit()
        state = (res.get("status") or {}).get("state")
        if state == "connected":
            try:
                from api import chatgpt_plan as cp
                st = cp.store()
                if not st.flag("welcome"):              # une seule fois (consigne OpenAI)
                    QMessageBox.information(self, translate("Vous utilisez votre forfait ChatGPT"),
                                            translate(WELCOME))
                    st.set_flag("welcome")
            except Exception:
                pass

    def _on_disconnect(self):
        from api import chatgpt_plan as cp
        from core.background import run_task

        def _done(confirmed):
            self.refresh()
            if confirmed is False:
                QMessageBox.information(
                    self, translate("Compte ChatGPT"),
                    translate("Déconnecté sur ce poste. La révocation chez OpenAI n'a pas pu "
                              "être confirmée : vous pouvez aussi déconnecter PANDORA dans "
                              "ChatGPT (Réglages → Sécurité → Connexions)."))
        run_task(cp.disconnect, _done)

    def _on_resume(self):
        try:
            from api import chatgpt_plan as cp
            cp.resume_plan()
        except Exception:
            pass
        self.refresh()
