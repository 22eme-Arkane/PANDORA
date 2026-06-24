"""
ui/storyboard_chat.py — Panneau de chat connecté au Storyboard.

Un panneau droit repliable (poignée « CHAT » avec flèche, comme l'assistant IA)
qui discute avec le moteur d'IA sélectionné. Le chat lit TOUT le storyboard et
applique les modifications demandées par l'utilisateur — de façon CHIRURGICALE :
si on demande de changer une seule phrase de dialogue, seule cette phrase change.

Fermé par défaut, ouvert via la poignée.
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTextEdit, QScrollArea,
)
from PyQt6.QtCore import Qt, QTimer
from ui.styles import CP
from core.i18n import translate


class StoryboardChatPanel(QWidget):
    """Chat storyboard. `shots_provider()` renvoie la liste des plans courants ;
    `on_applied()` est appelé après l'application d'éditions pour rafraîchir l'UI.
    `header_height` aligne l'en-tête sur les bandeaux de page."""

    def __init__(self, shots_provider, on_applied=None, header_height: int = 60):
        super().__init__()
        self._shots_provider = shots_provider
        self._on_applied     = on_applied
        self._history: list[dict] = []
        self._worker = None

        self.setFixedWidth(300)
        self.setStyleSheet(f"background:{CP['bg1']};")

        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)

        # ── En-tête ────────────────────────────────────────────────────────────
        header = QWidget()
        header.setFixedHeight(header_height)
        header.setStyleSheet(
            f"background:{CP['bg2']};border-bottom:1px solid {CP['border']};"
        )
        hl = QHBoxLayout(header)
        hl.setContentsMargins(14, 0, 10, 0)
        hl.setSpacing(8)
        ico = QLabel("✦")
        ico.setStyleSheet(f"color:{CP['accent']};font-size:14px;background:transparent;")
        hl.addWidget(ico)
        title = QLabel(translate("IA"))
        title.setStyleSheet(
            f"color:{CP['text_primary']};font-size:13px;font-weight:700;background:transparent;"
        )
        hl.addWidget(title)
        hl.addStretch()
        btn_clear = QPushButton("✕")
        btn_clear.setFixedSize(20, 20)
        btn_clear.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_clear.setToolTip(translate("Effacer la conversation"))
        btn_clear.setStyleSheet(
            f"QPushButton{{background:transparent;color:{CP['text_dim']};"
            f"border:none;font-size:10px;font-weight:700;}}"
            f"QPushButton:hover{{color:{CP['text_primary']};}}"
        )
        btn_clear.clicked.connect(self._clear_chat)
        hl.addWidget(btn_clear)
        lay.addWidget(header)

        # ── Bandeau d'intro ──────────────────────────────────────────────────────
        intro = QLabel(
            "Discutez du découpage avec l'IA. Elle lit tout le storyboard et "
            "n'applique QUE les modifications que vous demandez explicitement."
        )
        intro.setWordWrap(True)
        intro.setStyleSheet(
            f"color:{CP['text_dim']};font-size:10px;font-style:italic;"
            f"padding:10px 12px;background:transparent;"
            f"border-bottom:1px solid {CP['border']};"
        )
        lay.addWidget(intro)

        # ── Zone de chat ───────────────────────────────────────────────────────
        chat_scroll = QScrollArea()
        chat_scroll.setWidgetResizable(True)
        chat_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        chat_scroll.setStyleSheet(
            f"QScrollArea{{background:{CP['bg1']};border:none;}}"
            f"QScrollBar:vertical{{width:4px;background:{CP['bg2']};}}"
            f"QScrollBar::handle:vertical{{background:{CP['border_bright']};border-radius:2px;}}"
        )
        self._chat_container = QWidget()
        self._chat_container.setStyleSheet(f"background:{CP['bg1']};")
        self._chat_lay = QVBoxLayout(self._chat_container)
        self._chat_lay.setContentsMargins(10, 14, 10, 8)
        self._chat_lay.setSpacing(8)
        self._chat_lay.addStretch()
        chat_scroll.setWidget(self._chat_container)
        self._chat_scroll = chat_scroll
        lay.addWidget(chat_scroll, 1)

        # ── Input ──────────────────────────────────────────────────────────────
        input_frame = QWidget()
        input_frame.setStyleSheet(
            f"background:{CP['bg2']};border-top:1px solid {CP['border']};"
        )
        input_lay = QVBoxLayout(input_frame)
        input_lay.setContentsMargins(10, 8, 10, 10)
        input_lay.setSpacing(6)

        self._input = QTextEdit()
        self._input.setPlaceholderText(translate("Discuter du storyboard avec l'IA…"))
        self._input.setFixedHeight(60)
        self._input.setStyleSheet(
            f"QTextEdit{{background:{CP['bg3']};border:1px solid {CP['border']};"
            f"border-radius:6px;color:{CP['text_primary']};font-size:11px;padding:5px 8px;}}"
            f"QTextEdit:focus{{border-color:{CP['accent_dim']};}}"
        )
        input_lay.addWidget(self._input)

        self._btn_send = QPushButton("✦  " + translate("Envoyer"))
        self._btn_send.setMinimumHeight(32)
        self._btn_send.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_send.setStyleSheet(
            f"QPushButton{{background:{CP['accent']};color:#07080f;"
            f"border:none;border-radius:6px;font-size:11px;font-weight:700;padding:0 12px;}}"
            f"QPushButton:hover{{background:#6eded6;}}"
            f"QPushButton:disabled{{background:{CP['bg3']};color:{CP['text_dim']};}}"
        )
        self._btn_send.clicked.connect(self._on_send)
        input_lay.addWidget(self._btn_send)
        lay.addWidget(input_frame)

    # ── Envoi ────────────────────────────────────────────────────────────────────

    def _on_send(self):
        if self._worker and self._worker.isRunning():
            return
        msg = self._input.toPlainText().strip()
        if not msg:
            return
        shots = list(self._shots_provider() or [])
        if not shots:
            self._add_bubble("assistant", "Le storyboard est vide — rien à modifier.")
            return

        self._add_bubble("user", msg)
        self._input.clear()
        self._btn_send.setEnabled(False)
        self._btn_send.setText("…")

        from api.screenplay import StoryboardChatWorker
        self._worker = StoryboardChatWorker(msg, shots, list(self._history))
        self._worker.finished.connect(self._on_reply)
        self._worker.failed.connect(self._on_error)
        self._worker.start()
        self._history.append({"role": "user", "content": msg})

    def _on_reply(self, result: dict):
        reply = (result.get("reply") or "").strip()
        edits = result.get("edits") or []

        applied = self._apply_edits(edits) if edits else []

        if reply:
            self._add_bubble("assistant", reply)
            self._history.append({"role": "assistant", "content": reply})

        if applied:
            summary = "Modifications appliquées :\n" + "\n".join(
                f"· Plan {a['number']} — {a['summary']}" for a in applied
            )
            self._add_bubble("system", summary)
            if self._on_applied:
                self._on_applied()
        elif edits:
            self._add_bubble("system",
                             "Aucune modification appliquée (plan ou champ introuvable).")

        self._btn_send.setEnabled(True)
        self._btn_send.setText("✦  " + translate("Envoyer"))

    def _on_error(self, err: str):
        self._add_bubble("assistant", f"Erreur : {err}")
        self._btn_send.setEnabled(True)
        self._btn_send.setText("✦  " + translate("Envoyer"))

    # ── Application des éditions (chirurgicale) ────────────────────────────────────

    def _apply_edits(self, edits: list) -> list:
        import core.storyboard as sb_api
        from api.screenplay import STORYBOARD_CHAT_FIELDS
        shots = list(self._shots_provider() or [])
        by_id  = {s.get("id"): s for s in shots if s.get("id")}
        by_num = {str(s.get("number")): s for s in shots if s.get("number") not in (None, "")}

        applied = []
        for e in edits:
            field = e.get("field")
            if field not in STORYBOARD_CHAT_FIELDS:
                continue
            shot = by_id.get(e.get("id")) or by_num.get(str(e.get("number")))
            if not shot:
                continue
            value = e.get("value")
            cur = shot.get(field)
            # Champs liste : accepter une chaîne « a, b » → liste.
            if isinstance(cur, list) and isinstance(value, str):
                value = [v.strip() for v in value.split(",") if v.strip()]
            if field == "duration":
                try:
                    value = int(float(value))
                except (TypeError, ValueError):
                    pass
            shot[field] = value
            try:
                sb_api.save_shot({k: v for k, v in shot.items() if not k.startswith("_")})
            except Exception:
                continue
            applied.append({
                "number":  shot.get("number", "?"),
                "summary": e.get("summary") or f"{field} mis à jour",
            })
        return applied

    # ── Bulles ─────────────────────────────────────────────────────────────────

    def _add_bubble(self, role: str, text: str):
        is_user = (role == "user")
        is_sys  = (role == "system")
        if is_user:
            bg = "rgba(78,205,196,0.10)"
        elif is_sys:
            bg = "rgba(124,107,255,0.12)"
        else:
            bg = CP['bg2']
        bubble = QWidget()
        bubble.setStyleSheet(f"background:{bg};border-radius:8px;")
        b_lay = QVBoxLayout(bubble)
        b_lay.setContentsMargins(10, 7, 10, 7)
        b_lay.setSpacing(3)

        role_lbl = {"user": "Vous", "system": "⟳ Storyboard"}.get(role, "✦ Assistant")
        role_col = {"user": CP['accent'], "system": CP.get('accent2', '#7c6bff')}.get(
            role, CP['text_dim'])
        lbl_role = QLabel(role_lbl)
        lbl_role.setStyleSheet(
            f"color:{role_col};font-size:9px;font-weight:700;"
            f"letter-spacing:1px;background:transparent;"
        )
        b_lay.addWidget(lbl_role)

        lbl_text = QLabel(text)
        lbl_text.setWordWrap(True)
        lbl_text.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        lbl_text.setStyleSheet(
            f"color:{CP['text_primary']};font-size:11px;background:transparent;"
        )
        b_lay.addWidget(lbl_text)

        self._chat_lay.insertWidget(self._chat_lay.count() - 1, bubble)
        QTimer.singleShot(60, lambda: self._chat_scroll.verticalScrollBar().setValue(
            self._chat_scroll.verticalScrollBar().maximum()
        ))

    def _clear_chat(self):
        self._history.clear()
        while self._chat_lay.count() > 1:
            item = self._chat_lay.takeAt(0)
            if item and item.widget():
                item.widget().deleteLater()


# ── Poignée d'ouverture/fermeture ──────────────────────────────────────────────

class StoryboardChatToggleStrip(QWidget):
    """Bande verticale 28px pour ouvrir/fermer le chat storyboard (à droite)."""

    def __init__(self, panel: StoryboardChatPanel):
        super().__init__()
        self._panel = panel
        self._open  = panel.isVisible()
        self.setFixedWidth(42)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setToolTip(translate("Ouvrir / fermer l'IA (actions sur le projet)"))
        self.setStyleSheet(f"background:{CP['bg1']};")

        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)
        lay.addStretch()

        self._lbl = QLabel("IA")
        self._lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._lbl.setFixedWidth(42)
        # Libellé court → on garde horizontal compact.
        self._lbl.setStyleSheet(
            f"color:{CP['accent']};font-size:8px;font-weight:900;"
            f"letter-spacing:1px;background:transparent;"
        )
        lay.addWidget(self._lbl)
        lay.addSpacing(6)

        self._arrow = QLabel(self._arrow_char())
        self._arrow.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._arrow.setFixedWidth(42)
        self._arrow.setStyleSheet(
            f"color:{CP['accent']};font-size:18px;font-weight:700;background:transparent;"
        )
        lay.addWidget(self._arrow)
        lay.addStretch()

    def _arrow_char(self) -> str:
        return "❮" if self._open else "❯"

    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            self._open = not self._open
            self._panel.setVisible(self._open)
            self._arrow.setText(self._arrow_char())

    def enterEvent(self, e):
        self._lbl.setStyleSheet(
            f"color:#ffffff;font-size:8px;font-weight:900;"
            f"letter-spacing:1px;background:transparent;"
        )
        self._arrow.setStyleSheet(
            f"color:#ffffff;font-size:18px;font-weight:700;background:transparent;"
        )

    def leaveEvent(self, e):
        self._lbl.setStyleSheet(
            f"color:{CP['accent']};font-size:8px;font-weight:900;"
            f"letter-spacing:1px;background:transparent;"
        )
        self._arrow.setStyleSheet(
            f"color:{CP['accent']};font-size:18px;font-weight:700;background:transparent;"
        )
