"""Panneau de chat « direction artistique » réutilisable, à greffer sur le côté
droit des dialogs d'éléments (Casting, Décor, Accessoire, HMC, Véhicule).

Même esprit que le chat du Studio Images : on discute avec Claude pour affiner
l'idée, on peut joindre des images de référence, puis « Mettre à jour le prompt »
synthétise la conversation et l'injecte dans le champ prompt du dialog hôte.

Réutilisable : le type d'élément (`kind`) et le callback d'injection sont passés
au constructeur. Workers dans api/element_chat.py (signaux `done`, jamais
`finished`) ; le worker précédent est PARQUÉ avant réassignation (anti-segfault).
"""

import os

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QImageReader, QPixmap
from PyQt6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QProgressBar, QPushButton, QScrollArea,
    QTextEdit, QVBoxLayout, QWidget,
)

from core.i18n import translate
from ui.styles import CP


def _thumb(path: str, px: int) -> QPixmap:
    """Vignette bornée (QImageReader.setScaledSize — décode réduit pour le JPEG,
    évite de charger une image lourde en pleine résolution sur le thread UI)."""
    r = QImageReader(path)
    r.setAutoTransform(True)
    sz = r.size()
    if sz.isValid() and (sz.width() > px or sz.height() > px):
        s = min(px / max(1, sz.width()), px / max(1, sz.height()))
        r.setScaledSize(sz * s)
    img = r.read()
    return QPixmap.fromImage(img) if not img.isNull() else QPixmap(path)


class _ChatInput(QTextEdit):
    """Zone de saisie : Entrée envoie, Maj+Entrée = nouvelle ligne."""
    submit = pyqtSignal()

    def keyPressEvent(self, e):
        if (e.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter)
                and not (e.modifiers() & Qt.KeyboardModifier.ShiftModifier)):
            self.submit.emit()
            return
        super().keyPressEvent(e)


class ElementChatPanel(QWidget):
    """Panneau chat DA. `kind` ∈ {character, decor, accessory, hmc, vehicle}.
    `apply_cb(prompt)` reçoit le prompt synthétisé (à écrire dans le champ hôte)."""

    def __init__(self, kind: str, apply_cb, parent=None):
        super().__init__(parent)
        self._kind = kind
        self._apply_cb = apply_cb
        self._history = []            # [{"role","content"}] — schéma api/element_chat
        self._pending_images = []     # chemins joints au prochain message
        self._chat_worker = None
        self._synth_worker = None
        self._parked = []             # workers en cours d'arrêt (anti-GC)

        self._W_FULL  = 400
        self._W_STRIP = 40
        self._expanded = False
        self.setStyleSheet(f"background:{CP['bg1']};")
        self._build()
        self._greet()
        self._apply_state()
        # Parque les workers à la fermeture du dialog hôte (anti-segfault),
        # sans imposer un closeEvent à chaque dialog (intégration uniforme).
        try:
            win = self.window()
            if win is not None and hasattr(win, "finished"):
                win.finished.connect(lambda *_a: self.shutdown())
        except Exception:
            pass

    # ── Construction ──────────────────────────────────────────────────────────
    def _build(self):
        outer = QHBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # Poignée fine (état replié) : clic → ouvre le chat IA.
        self._handle = QPushButton("☁\n❯")
        self._handle.setCursor(Qt.CursorShape.PointingHandCursor)
        self._handle.setFixedWidth(self._W_STRIP)
        self._handle.setToolTip(translate("Améliorer avec l'IA — chat de direction artistique"))
        self._handle.setStyleSheet(
            f"QPushButton{{background:{CP['bg2']};color:{CP['accent']};border:none;"
            f"border-left:1px solid {CP['border']};font-size:14px;font-weight:700;}}"
            f"QPushButton:hover{{background:{CP['bg3']};}}")
        self._handle.clicked.connect(self._expand)
        outer.addWidget(self._handle)

        self._full = QWidget()
        self._full.setFixedWidth(self._W_FULL)
        self._full.setStyleSheet(
            f"background:{CP['bg1']};border-left:1px solid {CP['border']};")
        outer.addWidget(self._full)

        root = QVBoxLayout(self._full)
        root.setContentsMargins(10, 10, 10, 10)
        root.setSpacing(8)

        head = QHBoxLayout()
        btn_collapse = QPushButton("›")
        btn_collapse.setFixedSize(22, 22)
        btn_collapse.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_collapse.setToolTip(translate("Replier"))
        btn_collapse.setStyleSheet(
            f"QPushButton{{background:transparent;color:{CP['text_dim']};border:none;"
            f"font-size:16px;font-weight:700;}}QPushButton:hover{{color:{CP['text_primary']};}}")
        btn_collapse.clicked.connect(self._collapse)
        head.addWidget(btn_collapse)
        title = QLabel(translate("☁  Améliorer avec l'IA"))
        title.setStyleSheet(
            f"color:{CP['accent']};font-size:12px;font-weight:700;background:transparent;")
        head.addWidget(title)
        head.addStretch(1)
        btn_clear = QPushButton(translate("Vider"))
        btn_clear.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_clear.setStyleSheet(
            f"QPushButton{{background:transparent;color:{CP['text_dim']};border:none;"
            f"font-size:10px;}}QPushButton:hover{{color:{CP['text_primary']};}}")
        btn_clear.clicked.connect(self._clear)
        head.addWidget(btn_clear)
        root.addLayout(head)

        # Fil de discussion
        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._scroll.setStyleSheet(
            f"QScrollArea{{background:{CP['bg1']};border:1px solid {CP['border']};border-radius:8px;}}")
        wrap = QWidget()
        wrap.setStyleSheet(f"background:{CP['bg1']};")
        self._thread = QVBoxLayout(wrap)
        self._thread.setContentsMargins(6, 6, 6, 6)
        self._thread.setSpacing(8)
        self._thread.addStretch(1)
        self._scroll.setWidget(wrap)
        root.addWidget(self._scroll, 1)

        # Bandeau d'attente
        self._busy = QWidget()
        _bl = QHBoxLayout(self._busy)
        _bl.setContentsMargins(0, 0, 0, 0)
        self._status = QLabel("")
        self._status.setStyleSheet(f"color:{CP['text_dim']};font-size:10px;background:transparent;")
        _bl.addWidget(self._status)
        self._progress = QProgressBar()
        self._progress.setRange(0, 0)
        self._progress.setTextVisible(False)
        self._progress.setFixedHeight(5)
        self._progress.setStyleSheet(
            f"QProgressBar{{background:{CP['bg3']};border:none;border-radius:3px;}}"
            f"QProgressBar::chunk{{background:{CP['accent']};border-radius:3px;}}")
        _bl.addWidget(self._progress, 1)
        self._busy.setVisible(False)
        root.addWidget(self._busy)

        # Vignettes des images jointes en attente
        self._attach_row = QHBoxLayout()
        self._attach_row.setSpacing(6)
        self._attach_row.addStretch(1)
        _aw = QWidget()
        _aw.setLayout(self._attach_row)
        _aw.setFixedHeight(52)
        root.addWidget(_aw)

        # Saisie
        self._input = _ChatInput()
        self._input.setPlaceholderText(translate("Décris ton idée, pose une question…"))
        self._input.setFixedHeight(60)
        self._input.setStyleSheet(
            f"QTextEdit{{background:{CP['bg3']};border:1px solid {CP['border']};border-radius:8px;"
            f"color:{CP['text_primary']};font-size:11px;padding:6px;}}"
            f"QTextEdit:focus{{border-color:{CP['accent']};}}")
        self._input.submit.connect(self._send)
        root.addWidget(self._input)

        # Boutons d'action
        b1 = QHBoxLayout()
        self._btn_attach = QPushButton(translate("📎  Joindre une image"))
        self._btn_attach.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_attach.setStyleSheet(
            f"QPushButton{{background:transparent;color:{CP['text_secondary']};"
            f"border:1px solid {CP['border_bright']};border-radius:8px;font-size:11px;padding:6px;}}"
            f"QPushButton:hover{{color:{CP['text_primary']};border-color:{CP['accent']};}}")
        self._btn_attach.clicked.connect(self._attach)
        b1.addWidget(self._btn_attach)
        self._btn_send = QPushButton(translate("☁  Envoyer"))
        self._btn_send.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_send.setStyleSheet(
            f"QPushButton{{background:{CP['accent']};color:#07080f;border:none;border-radius:8px;"
            f"font-size:11px;font-weight:700;padding:6px 14px;}}"
            f"QPushButton:hover{{background:#6eded6;}}"
            f"QPushButton:disabled{{background:{CP['bg3']};color:{CP['text_dim']};}}")
        self._btn_send.clicked.connect(self._send)
        b1.addWidget(self._btn_send)
        root.addLayout(b1)

        self._btn_apply = QPushButton(translate("✍️  Mettre à jour le prompt"))
        self._btn_apply.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_apply.setStyleSheet(
            f"QPushButton{{background:transparent;color:{CP['accent']};"
            f"border:1px solid {CP['accent_dim']};border-radius:8px;font-size:11px;"
            f"font-weight:700;padding:7px;}}"
            f"QPushButton:hover{{background:rgba(78,205,196,0.12);border-color:{CP['accent']};}}"
            f"QPushButton:disabled{{color:{CP['text_dim']};border-color:{CP['border']};}}")
        self._btn_apply.setToolTip(translate(
            "Synthétise la discussion en un prompt et le place dans le champ « Prompt »."))
        self._btn_apply.clicked.connect(self._apply_prompt)
        root.addWidget(self._btn_apply)

    # ── Bulles ────────────────────────────────────────────────────────────────
    def _greet(self):
        self._add_bubble("assistant", translate(
            "Décris l'élément que tu veux créer — ou joins une image de référence. "
            "Je t'aide à préciser l'idée, puis « Mettre à jour le prompt » l'écrit "
            "dans le champ Prompt."))

    def _add_bubble(self, role: str, text: str, images=None):
        is_user = role == "user"
        bubble = QFrame()
        bubble.setStyleSheet(
            f"QFrame{{background:{CP['bg3'] if is_user else CP['bg2']};"
            f"border:1px solid {CP['border']};border-radius:10px;}}")
        bl = QVBoxLayout(bubble)
        bl.setContentsMargins(10, 8, 10, 8)
        bl.setSpacing(6)
        if text:
            lbl = QLabel(text)
            lbl.setWordWrap(True)
            lbl.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            lbl.setStyleSheet(
                f"color:{CP['text_primary'] if not is_user else CP['text_secondary']};"
                f"font-size:11px;background:transparent;border:none;")
            bl.addWidget(lbl)
        for p in (images or []):
            if p and os.path.isfile(p):
                thumb = QLabel()
                pix = _thumb(p, 120)
                if not pix.isNull():
                    thumb.setPixmap(pix)
                thumb.setStyleSheet("border:none;background:transparent;")
                bl.addWidget(thumb)

        wrap = QHBoxLayout()
        if is_user:
            wrap.addStretch(1)
            wrap.addWidget(bubble, 5)
        else:
            wrap.addWidget(bubble, 5)
            wrap.addStretch(1)
        holder = QWidget()
        holder.setLayout(wrap)
        holder.setStyleSheet("background:transparent;")
        self._thread.insertWidget(self._thread.count() - 1, holder)
        # défilement en bas
        from PyQt6.QtCore import QTimer
        QTimer.singleShot(30, lambda: self._scroll.verticalScrollBar().setValue(
            self._scroll.verticalScrollBar().maximum()))

    # ── Images jointes en attente ─────────────────────────────────────────────
    def _refresh_attach(self):
        while self._attach_row.count() > 1:
            it = self._attach_row.takeAt(0)
            if it and it.widget():
                it.widget().deleteLater()
        for p in self._pending_images:
            chip = QLabel()
            pix = _thumb(p, 44)
            if not pix.isNull():
                chip.setPixmap(pix)
            chip.setFixedSize(44, 44)
            chip.setToolTip(os.path.basename(p))
            chip.setStyleSheet(f"border:1px solid {CP['accent_dim']};border-radius:5px;")
            self._attach_row.insertWidget(self._attach_row.count() - 1, chip)

    def _attach(self):
        try:
            from ui.dialog_image_library import ImageLibraryDialog
            paths = ImageLibraryDialog.pick(self)
        except Exception:
            paths = None
        for p in (paths or []):
            if p and os.path.isfile(p) and p not in self._pending_images:
                self._pending_images.append(p)
        self._refresh_attach()

    # ── Envoi / réception ─────────────────────────────────────────────────────
    def _park(self, w):
        if w is None:
            return
        try:
            if w.isRunning():
                w.blockSignals(True)
                w.requestInterruption()
                w.quit()
                self._parked.append(w)
        except Exception:
            pass
        self._parked[:] = [t for t in self._parked if _still_running(t)]

    def _set_busy(self, busy: bool, msg: str = ""):
        self._busy.setVisible(busy)
        self._status.setText(translate(msg) if msg else "")
        self._btn_send.setEnabled(not busy)
        self._btn_apply.setEnabled(not busy)
        self._btn_attach.setEnabled(not busy)

    def _send(self):
        text = self._input.toPlainText().strip()
        if not text and not self._pending_images:
            return
        # Construire le contenu du tour (texte + images en attente)
        content = []
        if text:
            content.append({"t": "text", "text": text})
        for p in self._pending_images:
            content.append({"t": "image", "path": p})
        self._history.append({"role": "user", "content": content if len(content) > 1
                              or (content and content[0]["t"] == "image") else text})
        self._add_bubble("user", text, images=list(self._pending_images))
        self._input.clear()
        self._pending_images = []
        self._refresh_attach()

        from api.element_chat import ElementChatWorker
        self._park(self._chat_worker)
        self._chat_worker = ElementChatWorker(self._history, self._kind)
        self._chat_worker.done.connect(self._on_reply)
        self._chat_worker.failed.connect(self._on_error)
        self._chat_worker.notice.connect(lambda m: self._status.setText(m))
        self._set_busy(True, "Claude réfléchit…")
        self._chat_worker.start()

    def _on_reply(self, reply: str):
        self._set_busy(False)
        self._history.append({"role": "assistant", "content": reply})
        self._add_bubble("assistant", reply)

    def _on_error(self, err: str):
        self._set_busy(False)
        self._add_bubble("assistant", "⚠ " + err)

    # ── Synthèse → injection dans le champ prompt de l'hôte ───────────────────
    def _apply_prompt(self):
        if not self._history:
            self._add_bubble("assistant", translate(
                "Discute d'abord un peu de ce que tu veux, puis je pourrai rédiger le prompt."))
            return
        from api.element_chat import ElementSynthWorker
        self._park(self._synth_worker)
        self._synth_worker = ElementSynthWorker(self._history, self._kind)
        self._synth_worker.done.connect(self._on_synth)
        self._synth_worker.failed.connect(self._on_error)
        self._set_busy(True, "Rédaction du prompt…")
        self._synth_worker.start()

    def _on_synth(self, prompt: str):
        self._set_busy(False)
        if prompt and callable(self._apply_cb):
            self._apply_cb(prompt)
        self._add_bubble("assistant", translate("✓ Prompt mis à jour dans le champ « Prompt »."))

    # ── Réinitialisation ──────────────────────────────────────────────────────
    def _clear(self):
        self._history = []
        self._pending_images = []
        while self._thread.count() > 1:
            it = self._thread.takeAt(0)
            if it and it.widget():
                it.widget().deleteLater()
        self._refresh_attach()
        self._greet()

    # ── Repli / expansion (le panneau gère l'élargissement de la fenêtre hôte) ─
    def _apply_state(self):
        self._full.setVisible(self._expanded)
        self._handle.setVisible(not self._expanded)
        self.setFixedWidth(self._W_FULL if self._expanded else self._W_STRIP)

    def _expand(self):
        if self._expanded:
            return
        self._expanded = True
        win = self.window()
        if win is not None:
            win.resize(win.width() + (self._W_FULL - self._W_STRIP), win.height())
        self._apply_state()

    def _collapse(self):
        if not self._expanded:
            return
        self._expanded = False
        self._apply_state()
        win = self.window()
        if win is not None:
            win.resize(max(win.minimumWidth(), win.width() - (self._W_FULL - self._W_STRIP)),
                       win.height())

    def shutdown(self):
        """À appeler à la fermeture du dialog hôte : parque les workers actifs."""
        self._park(self._chat_worker)
        self._park(self._synth_worker)


def _still_running(w) -> bool:
    try:
        return w is not None and w.isRunning()
    except Exception:
        return False
