"""ui/dictation.py — Le micro d'ORAKLE dans tous les champs de texte de PANDORA.

Demande Matthieu (27/10/2026) : « intégré dans toutes les parties où on peut écrire
du texte, avec un petit logo de micro ; quand on clique dessus ça fonctionne comme
ORAKLE en position ouverte ; au survol, les raccourcis pour l'utiliser ».

- `install(app)` (main.py) pose UN filtre d'événements sur l'application : chaque
  champ modifiable qui s'affiche reçoit son micro — un bouton à droite d'un
  QLineEdit, en bas à droite d'un QTextEdit / QPlainTextEdit. Pas de micro sur les
  mots de passe et clés, les champs numériques, ceux des listes déroulantes et des
  compteurs, ni ceux qu'un code marque `setProperty("orakle", False)`.
- Clic sur le micro : mains-libres — on parle, on reclique, le texte s'écrit au
  curseur. Raccourci d'ORAKLE (Ctrl+1 par défaut, lu dans ses réglages) dans un
  champ : maintenu = on parle tant qu'il est enfoncé ; deux fois = mains-libres,
  une fois de plus = écrire. Échap annule.
- Une pastille (l'onde d'ORAKLE) s'affiche sous le champ pendant l'écoute, puis
  « Transcription… ». Elle ne prend jamais le focus.
- La transcription tourne dans un QThread (signal `done`) : l'interface ne fige pas.

Le moteur (micro, Whisper, dictionnaire, machine à états) est core/dictation.py.
"""
from __future__ import annotations

import math
import sys
import time
from typing import Optional

from PyQt6 import sip
from PyQt6.QtCore import QEvent, QObject, QPoint, QRectF, Qt, QThread, QTimer, pyqtSignal
from PyQt6.QtGui import (
    QAction, QColor, QDoubleValidator, QGuiApplication, QIcon, QIntValidator, QPainter,
    QPainterPath, QPen, QPixmap,
)
from PyQt6.QtWidgets import (
    QAbstractSpinBox, QApplication, QComboBox, QKeySequenceEdit, QLineEdit, QMessageBox,
    QPlainTextEdit, QTextBrowser, QTextEdit, QToolButton, QWidget,
)

from core import dictation as dict_core
from core.i18n import translate
from ui.styles import CP

#: Couleur du micro pendant l'écoute : le jaune « enregistrement » d'ORAKLE,
#: pensé pour le daltonisme (sens fixe, indépendant du thème).
_REC_COLOR = "#f2c14e"
#: Micro fermé après ce temps sans dictée (l'indicateur « micro utilisé » de
#: Windows s'éteint) ; Whisper libéré de la mémoire après une longue pause.
_MIC_IDLE_MS = 120_000
_MODEL_IDLE_MS = 15 * 60_000

_PROP = "_orakle_mic"          # posé sur chaque champ équipé
_PROP_HOST = "_orakle_host"    # posé sur le viewport d'un QTextEdit équipé
#: Noms des contrôles ajoutés : retrouvés par findChild, y compris sur les champs
#: créés par Qt lui-même (dont l'objet Python peut être recréé entre deux appels).
_ACTION_NAME = "orakleMicAction"
_BUTTON_NAME = "orakleMicButton"


# ── Icône du micro (dessinée : nette à toutes les échelles, teinte libre) ─────

def _mic_pixmap(color: str, size: int, dpr: float, filled: bool) -> QPixmap:
    pm = QPixmap(int(size * dpr), int(size * dpr))
    pm.setDevicePixelRatio(dpr)
    pm.fill(Qt.GlobalColor.transparent)
    s = size / 16.0
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    col = QColor(color)
    p.setPen(QPen(col, 1.5 * s, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap,
                  Qt.PenJoinStyle.RoundJoin))
    p.setBrush(col if filled else Qt.BrushStyle.NoBrush)
    p.drawRoundedRect(QRectF(5.5 * s, 1.5 * s, 5 * s, 8.5 * s), 2.5 * s, 2.5 * s)
    p.setBrush(Qt.BrushStyle.NoBrush)
    p.drawArc(QRectF(3.2 * s, 3.6 * s, 9.6 * s, 8.4 * s), 180 * 16, 180 * 16)
    p.drawLine(QPoint(round(8 * s), round(12 * s)), QPoint(round(8 * s), round(14.2 * s)))
    p.drawLine(QPoint(round(5.6 * s), round(14.4 * s)), QPoint(round(10.4 * s), round(14.4 * s)))
    p.end()
    return pm


_ICONS: dict = {}


def mic_icon(state: str = "idle") -> QIcon:
    """Micro au repos (teinte discrète), à l'écoute (jaune plein), en transcription."""
    if state not in _ICONS:
        color = {"recording": _REC_COLOR, "processing": CP["accent"]}.get(
            state, CP["text_secondary"])
        icon = QIcon()
        for dpr in (1.0, 2.0):
            icon.addPixmap(_mic_pixmap(color, 16, dpr, state == "recording"))
            icon.addPixmap(_mic_pixmap(CP["text_dim"], 16, dpr, False), QIcon.Mode.Disabled)
        _ICONS[state] = icon
    return _ICONS[state]


# ── Textes ────────────────────────────────────────────────────────────────────

def tooltip_text(cfg: Optional[dict] = None) -> str:
    """L'infobulle du micro : comment dicter, avec le raccourci réel d'ORAKLE."""
    key = dict_core.hotkey_label((cfg or dict_core.settings()).get("hotkey", ""))
    lines = [
        translate("Dictée vocale (ORAKLE)"),
        translate("Clic : parlez, puis recliquez pour écrire le texte"),
        translate("{key} maintenu : parlez, relâchez pour écrire").format(key=key),
        translate("{key} deux fois : mains libres, puis {key} pour écrire").format(key=key),
        translate("Échap : annuler la dictée"),
    ]
    return "\n".join(lines)


# ── Quels champs reçoivent un micro ───────────────────────────────────────────

def eligible(w) -> bool:
    """Un champ où l'on écrit du texte libre (lecture seule incluse : son micro
    apparaît dès qu'il devient modifiable)."""
    if isinstance(w, QLineEdit):
        if w.echoMode() != QLineEdit.EchoMode.Normal:
            return False                       # mots de passe, clés API
        if isinstance(w.validator(), (QIntValidator, QDoubleValidator)):
            return False                       # champs numériques
        if w.maximumWidth() < 110:
            return False                       # petits champs fixes (valeurs, codes)
        if w.metaObject().className() == "QExpandingLineEdit":
            return False                       # éditeur de cellule d'un tableau
        parent = w.parentWidget()
        if isinstance(parent, (QAbstractSpinBox, QComboBox, QKeySequenceEdit)):
            return False
    elif isinstance(w, (QTextEdit, QPlainTextEdit)):
        if isinstance(w, QTextBrowser):
            return False
    else:
        return False
    return w.property("orakle") is not False


def _editable(w) -> bool:
    return not w.isReadOnly() and w.isEnabled()


def _alive(w) -> bool:
    return w is not None and not sip.isdeleted(w)


# ── La pastille d'ORAKLE (onde pendant l'écoute, texte ensuite) ───────────────

class _Pill(QWidget):
    _BARS = 13

    def __init__(self, level_provider):
        super().__init__(None)
        self._level = level_provider
        self._bars = [0.12] * self._BARS
        self._phase = 0.0
        self._text = ""
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Tool
                            | Qt.WindowType.WindowStaysOnTopHint
                            | Qt.WindowType.WindowDoesNotAcceptFocus)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._anim = QTimer(self)
        self._anim.setInterval(40)
        self._anim.timeout.connect(self._tick)
        self._hide_timer = QTimer(self)
        self._hide_timer.setSingleShot(True)
        self._hide_timer.timeout.connect(self.hide_pill)

    def show_wave(self, anchor) -> None:
        self._text = ""
        self._bars = [0.12] * self._BARS
        self.resize(96, 28)
        self._place(anchor)
        self._hide_timer.stop()
        self._anim.start()
        self.show()
        self.raise_()

    def show_text(self, anchor, text: str, ms: int = 0) -> None:
        self._anim.stop()
        self._text = text
        fm = self.fontMetrics()
        self.resize(min(520, fm.horizontalAdvance(text) + 34), 28)
        self._place(anchor)
        self.show()
        self.raise_()
        self.update()
        if ms:
            self._hide_timer.start(ms)
        else:
            self._hide_timer.stop()

    def hide_pill(self) -> None:
        self._anim.stop()
        self._hide_timer.stop()
        self.hide()

    def _place(self, anchor) -> None:
        """Sous le champ, calée sur son bord droit (au-dessus s'il touche le bas)."""
        if not _alive(anchor) or not anchor.isVisible():
            screen = QGuiApplication.primaryScreen()
            geo = screen.availableGeometry() if screen else None
            if geo is not None:
                self.move(geo.x() + (geo.width() - self.width()) // 2,
                          geo.bottom() - self.height() - 8)
            return
        top_left = anchor.mapToGlobal(QPoint(0, 0))
        x = top_left.x() + anchor.width() - self.width()
        y = top_left.y() + anchor.height() + 6
        screen = QGuiApplication.screenAt(top_left) or QGuiApplication.primaryScreen()
        if screen is not None:
            geo = screen.availableGeometry()
            if y + self.height() > geo.bottom():
                y = top_left.y() - self.height() - 6
            x = max(geo.left() + 4, min(x, geo.right() - self.width() - 4))
        self.move(x, y)

    def _tick(self) -> None:
        self._phase += 0.35
        try:
            level = max(0.0, min(1.0, float(self._level()) * 8.0))
        except Exception:
            level = 0.0
        n = self._BARS
        mid = (n - 1) / 2
        for i in range(n):
            bell = 1.0 - abs((i - mid) / mid)
            osc = 0.5 + 0.5 * math.sin(self._phase + i * 0.55)
            target = 0.12 + (0.25 + 0.75 * level) * (0.35 + 0.65 * bell) * osc
            self._bars[i] += (target - self._bars[i]) * 0.4
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        path = QPainterPath()
        path.addRoundedRect(QRectF(0.5, 0.5, w - 1.0, h - 1.0), h / 2, h / 2)
        bg = QColor(CP["bg1"])
        bg.setAlpha(240)
        p.fillPath(path, bg)
        p.setPen(QPen(QColor(CP["border_bright"]), 1))
        p.drawPath(path)
        if self._text:
            p.setPen(QColor(CP["text_primary"]))
            p.drawText(QRectF(0, 0, w, h), Qt.AlignmentFlag.AlignCenter, self._text)
            return
        pad, n = 12.0, self._BARS
        slot = (w - 2 * pad) / n
        bar_w = min(4.0, slot * 0.55)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(_REC_COLOR))
        for i in range(n):
            bh = max(3.0, self._bars[i] * h * 0.55)
            x = pad + slot * i + (slot - bar_w) / 2.0
            p.drawRoundedRect(QRectF(x, h / 2.0 - bh / 2.0, bar_w, bh), bar_w / 2, bar_w / 2)


# ── Transcription hors du fil de l'interface ──────────────────────────────────

class _TranscribeWorker(QThread):
    done = pyqtSignal(str, str)      # texte, erreur

    def __init__(self, engine, audio):
        super().__init__()
        self._engine = engine
        self._audio = audio

    def run(self):
        try:
            self.done.emit(self._engine.transcribe(self._audio), "")
        except Exception as exc:      # noqa: BLE001 — affiché à l'utilisateur
            self.done.emit("", str(exc) or exc.__class__.__name__)


# ── Le contrôleur ─────────────────────────────────────────────────────────────

class DictationController(QObject):
    """Équipe les champs, écoute le raccourci, enchaîne écoute → transcription →
    écriture. Un seul à la fois dans l'application."""

    state_changed = pyqtSignal(str)   # "idle" | "recording" | "processing"

    _WATCHED = frozenset((QEvent.Type.Show, QEvent.Type.Resize, QEvent.Type.ReadOnlyChange,
                          QEvent.Type.EnabledChange, QEvent.Type.KeyPress,
                          QEvent.Type.KeyRelease))

    def __init__(self, engine=None, cfg: Optional[dict] = None, enabled: bool = True,
                 parent=None):
        super().__init__(parent)
        self.cfg = dict(cfg or dict_core.settings())
        self.engine = engine if engine is not None else dict_core.engine()
        self.enabled = enabled
        self.state = "idle"
        self._target = None
        self._tooltip = tooltip_text(self.cfg)
        self._mods, self._key = dict_core.hotkey_parts(self.cfg.get("hotkey", ""))
        self.machine = dict_core.HotkeyMachine(self.cfg.get("hold_threshold_ms", 300),
                                               self.cfg.get("double_tap_window_ms", 400))
        self._pill = None
        self._threads: list = []
        self._download_thread = None
        self._hold_timer = QTimer(self)
        self._hold_timer.setSingleShot(True)
        self._hold_timer.timeout.connect(self._on_hold_tick)
        self._mic_timer = QTimer(self)
        self._mic_timer.setSingleShot(True)
        self._mic_timer.timeout.connect(self._release_mic)
        self._model_timer = QTimer(self)
        self._model_timer.setSingleShot(True)
        self._model_timer.timeout.connect(self._release_model)
        self._download_timer = QTimer(self)
        self._download_timer.setInterval(1000)
        self._download_timer.timeout.connect(self._poll_download)
        # Détection anticipée de la langue pendant l'écoute (comme ORAKLE).
        self._lang_timer = QTimer(self)
        self._lang_timer.setInterval(500)
        self._lang_timer.timeout.connect(self._prefetch_language)

    # ── équipement des champs ────────────────────────────────────────────────
    def attach(self, w) -> bool:
        if w.property(_PROP) is not None or not eligible(w):
            return False
        if isinstance(w, QLineEdit):
            act = QAction(mic_icon("idle"), "", w)
            act.setObjectName(_ACTION_NAME)
            act.setToolTip(self._tooltip)
            act.triggered.connect(lambda _c=False, f=w: self.toggle_for(f))
            w.addAction(act, QLineEdit.ActionPosition.TrailingPosition)
        else:
            btn = QToolButton(w)
            btn.setObjectName(_BUTTON_NAME)
            btn.setIcon(mic_icon("idle"))
            btn.setToolTip(self._tooltip)
            btn.setFixedSize(24, 24)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            btn.setStyleSheet(
                "QToolButton{background:transparent;border:none;border-radius:6px;}"
                "QToolButton:hover{background:rgba(255,255,255,0.10);}")
            btn.clicked.connect(lambda _c=False, f=w: self.toggle_for(f))
            w.viewport().setProperty(_PROP_HOST, True)
        w.setProperty(_PROP, True)
        self._refresh(w)
        return True

    @staticmethod
    def _button(w):
        if isinstance(w, QLineEdit):
            return None
        return w.findChild(QToolButton, _BUTTON_NAME, Qt.FindChildOption.FindDirectChildrenOnly)

    def _control(self, w):
        if isinstance(w, QLineEdit):
            return w.findChild(QAction, _ACTION_NAME, Qt.FindChildOption.FindDirectChildrenOnly)
        return self._button(w)

    def _refresh(self, w) -> None:
        """Micro visible si la dictée est active et le champ modifiable ; bouton des
        zones de texte recalé en bas à droite, hors barres de défilement."""
        ctl = self._control(w)
        if ctl is None:
            return
        ctl.setVisible(self.enabled and _editable(w))
        btn = self._button(w)
        if btn is None:
            return
        x = w.width() - btn.width() - 5
        y = w.height() - btn.height() - 5
        vbar, hbar = w.verticalScrollBar(), w.horizontalScrollBar()
        if vbar.isVisible():
            x -= vbar.width()
        if hbar.isVisible():
            y -= hbar.height()
        if w.height() < 48:
            y = (w.height() - btn.height()) // 2
        btn.move(max(0, x), max(0, y))
        btn.raise_()

    def _set_icon(self, w, state: str) -> None:
        if _alive(w):
            ctl = self._control(w)
            if ctl is not None:
                ctl.setIcon(mic_icon(state))

    def set_enabled(self, enabled: bool) -> None:
        self.enabled = bool(enabled)
        if not self.enabled and self.state == "recording":
            self.cancel()
        for w in QApplication.allWidgets():
            if w.property(_PROP):
                self._refresh(w)

    # ── filtre d'événements de l'application ─────────────────────────────────
    def eventFilter(self, obj, event):
        t = event.type()
        if t not in self._WATCHED:
            return False
        if t in (QEvent.Type.KeyPress, QEvent.Type.KeyRelease):
            return self._on_key(event, t == QEvent.Type.KeyPress, obj)
        if not isinstance(obj, QWidget):
            return False
        if t == QEvent.Type.Show:
            if self.enabled and isinstance(obj, (QLineEdit, QTextEdit, QPlainTextEdit)):
                if not self.attach(obj) and obj.property(_PROP):
                    self._refresh(obj)
        elif obj.property(_PROP):
            self._refresh(obj)
        elif t == QEvent.Type.Resize and obj.property(_PROP_HOST):
            host = obj.parentWidget()
            if host is not None and host.property(_PROP):
                self._refresh(host)
        return False

    # ── raccourci ────────────────────────────────────────────────────────────
    def _mods_ok(self, mods) -> bool:
        mac = sys.platform == "darwin"
        km = Qt.KeyboardModifier
        need = {
            "ctrl": km.MetaModifier if mac else km.ControlModifier,
            "cmd": km.ControlModifier if mac else km.MetaModifier,
            "shift": km.ShiftModifier,
            "alt": km.AltModifier,
        }
        if any(not (mods & need[m]) for m in self._mods):
            return False
        return "alt" in self._mods or not (mods & km.AltModifier)   # pas d'AltGr

    def _key_ok(self, event) -> bool:
        k, main = event.key(), self._key
        if len(main) == 1:
            c = main.upper()
            if k == ord(c):
                return True
            # Clavier AZERTY : la touche « 1/& » rend « & » ; on reconnaît la
            # touche physique par son code Windows (0x31 pour « 1 »), comme ORAKLE.
            return (sys.platform.startswith("win") and c.isalnum()
                    and event.nativeVirtualKey() == ord(c))
        if main.startswith("f") and main[1:].isdigit():
            return k == Qt.Key.Key_F1.value + int(main[1:]) - 1
        named = {"space": Qt.Key.Key_Space, "enter": Qt.Key.Key_Return,
                 "tab": Qt.Key.Key_Tab, "insert": Qt.Key.Key_Insert}
        return main in named and k == named[main].value

    def _focused_field(self, receiver=None):
        # La touche arrive d'abord à la fenêtre (QWindow) : le champ visé est alors
        # celui qui a le focus ; envoyée directement à un widget, c'est lui.
        w = receiver if isinstance(receiver, QWidget) else QApplication.focusWidget()
        while w is not None and not w.property(_PROP):
            w = w.parentWidget() if isinstance(w.parentWidget(), (QTextEdit, QPlainTextEdit)) else None
        return w if (w is not None and self.enabled and _editable(w)) else None

    def _on_key(self, event, pressed: bool, receiver=None) -> bool:
        if (pressed and event.key() == Qt.Key.Key_Escape.value
                and self.state == "recording"):
            self.cancel()
            return True
        if not self._key_ok(event):
            return False
        if self.machine.engaged:
            if event.isAutoRepeat():
                return True
            if not pressed:
                self._run(self.machine.release(time.monotonic()))
                return True
            return True
        if not pressed or event.isAutoRepeat() or not self._mods_ok(event.modifiers()):
            return False
        if self.machine.mode == "toggle":
            self._run(self.machine.press(time.monotonic()))
            return True
        field = self._focused_field(receiver)
        if field is None or self.state == "processing" or dict_core.hotkey_owned_by_orakle(self.cfg):
            return False
        self._target = field
        self._run(self.machine.press(time.monotonic()))
        if self.machine.engaged:
            self._hold_timer.start(int(self.machine.hold * 1000) + 15)
        return True

    def _on_hold_tick(self) -> None:
        self._run(self.machine.tick(time.monotonic()))

    def _run(self, actions: list) -> None:
        for act in actions:
            if act == "start":
                if not self._capture_start(self._target):
                    self.machine.reset()
                    return
            elif act == "confirm":
                self._enter_recording()
            elif act == "commit":
                self._hold_timer.stop()
                self.commit()
            elif act == "cancel":
                self._hold_timer.stop()
                self.engine.cancel()
                if self.state == "recording":
                    self._leave("idle")

    # ── gestes ───────────────────────────────────────────────────────────────
    def toggle_for(self, w) -> None:
        """Clic sur un micro : mains-libres ; un 2ᵉ clic écrit."""
        if self.state == "processing":
            self._message(w, translate("Transcription en cours…"), 1800)
            return
        if self.state == "recording":
            self.commit()
            return
        if not (_alive(w) and _editable(w)):
            return
        w.setFocus(Qt.FocusReason.OtherFocusReason)
        if self._capture_start(w):
            self.machine.enter_toggle()
            self._enter_recording()

    def _capture_start(self, target) -> bool:
        if not _alive(target):
            return False
        if not self._model_ready(target):
            return False
        try:
            self.engine.start()
        except Exception as exc:      # noqa: BLE001 — micro absent, refusé, occupé
            self._message(target, translate("Micro indisponible : {e}").format(e=exc), 5000)
            return False
        self._target = target
        self._mic_timer.stop()
        self._model_timer.stop()
        try:
            self.engine.warm_async()
        except Exception:
            pass
        return True

    def _enter_recording(self) -> None:
        self.state = "recording"
        self._set_icon(self._target, "recording")
        self._pill_widget().show_wave(self._target)
        self._lang_timer.start()
        self.state_changed.emit(self.state)

    def _prefetch_language(self) -> None:
        if self.state != "recording":
            self._lang_timer.stop()
            return
        prefetch = getattr(self.engine, "prefetch_language", None)
        if prefetch is not None:
            try:
                prefetch()
            except Exception:
                self._lang_timer.stop()

    def cancel(self) -> None:
        """Échap : la dictée est jetée."""
        self._hold_timer.stop()
        self.machine.reset()
        self.engine.cancel()
        self._mic_timer.start(_MIC_IDLE_MS)
        self._leave("idle")

    def commit(self) -> None:
        """Fin de l'écoute : transcrire puis écrire dans le champ."""
        self._hold_timer.stop()
        self.machine.reset()
        audio = self.engine.stop()
        self._mic_timer.start(_MIC_IDLE_MS)
        if audio is None or len(audio) < dict_core.MIN_AUDIO_SECONDS * 16_000:
            self._leave("idle")
            return
        self._lang_timer.stop()
        self.state = "processing"
        self._set_icon(self._target, "processing")
        self._pill_widget().show_text(self._target, translate("Transcription…"))
        self.state_changed.emit(self.state)
        self._threads = [t for t in self._threads if t.isRunning()]
        worker = _TranscribeWorker(self.engine, audio)
        worker.done.connect(self._on_transcribed)
        self._threads.append(worker)
        worker.start()

    def _on_transcribed(self, text: str, error: str) -> None:
        target = self._target
        self._leave("idle", keep_pill=True)
        self._model_timer.start(_MODEL_IDLE_MS)
        if error:
            self._message(target, translate("La dictée a échoué : {e}").format(e=error), 6000)
            return
        if not text:
            self._message(target, translate("Rien entendu"), 1800)
            return
        if _alive(target) and _editable(target):
            insert_text(target, text, bool(self.cfg.get("append_trailing_space", True)))
            self._pill_widget().hide_pill()
        else:
            QGuiApplication.clipboard().setText(text)
            self._message(None, translate("Texte dicté copié dans le presse-papiers"), 3000)

    def _leave(self, state: str, keep_pill: bool = False) -> None:
        self._lang_timer.stop()
        self._set_icon(self._target, "idle")
        self.state = state
        if not keep_pill and self._pill is not None:
            self._pill.hide_pill()
        self.state_changed.emit(self.state)

    # ── modèle Whisper : téléchargé une fois, avec l'accord de l'utilisateur ──
    def _model_ready(self, anchor) -> bool:
        if self.engine.model_loaded or dict_core.model_cached(self.cfg.get("model", "small")):
            return True
        if self._download_thread is not None:
            self._message(anchor, translate("Le modèle de dictée se télécharge…"), 2500)
            return False
        name = self.cfg.get("model", "small")
        size = dict_core.model_size_mb(name)
        box = QMessageBox(anchor.window() if _alive(anchor) else None)
        box.setIcon(QMessageBox.Icon.Question)
        box.setWindowTitle(translate("Dictée vocale (ORAKLE)"))
        box.setText(translate(
            "La dictée a besoin du modèle Whisper « {name} » ({size} Mo environ). Il "
            "se télécharge une seule fois ; ensuite tout reste sur cet ordinateur, "
            "sans connexion.").format(name=name, size=size or "?"))
        yes = box.addButton(translate("Télécharger"), QMessageBox.ButtonRole.AcceptRole)
        box.addButton(translate("Plus tard"), QMessageBox.ButtonRole.RejectRole)
        box.exec()
        if box.clickedButton() is not yes:
            return False
        self._start_download(anchor)
        return False

    def _start_download(self, anchor) -> None:
        self.engine.warm_async()
        self._download_thread = getattr(self.engine, "_warm_thread", None)
        self._download_anchor = anchor
        self._message(anchor, translate("Téléchargement du modèle de dictée…"))
        self._download_timer.start()

    def _poll_download(self) -> None:
        th = self._download_thread
        if th is not None and th.is_alive():
            return
        self._download_timer.stop()
        self._download_thread = None
        anchor = getattr(self, "_download_anchor", None)
        if self.engine.model_loaded:
            self._message(anchor, translate("Dictée prête : cliquez sur le micro et parlez"), 4000)
        else:
            self._message(anchor, translate(
                "Téléchargement du modèle impossible : vérifiez la connexion"), 6000)

    # ── ressources ───────────────────────────────────────────────────────────
    def _release_mic(self) -> None:
        if self.state == "idle":
            self.engine.release_mic()

    def _release_model(self) -> None:
        if self.state == "idle":
            self.engine.release_model()

    def _pill_widget(self) -> _Pill:
        if self._pill is None:
            self._pill = _Pill(lambda: self.engine.level)
        return self._pill

    def _message(self, anchor, text: str, ms: int = 0) -> None:
        self._pill_widget().show_text(anchor if _alive(anchor) else None, text, ms)

    def shutdown(self) -> None:
        """Fermeture de PANDORA : on jette l'écoute, on laisse finir la transcription."""
        try:
            if self.state == "recording":
                self.cancel()
            self.engine.release_mic()
            from core.worker import abandon_thread
            for t in self._threads:
                if t.isRunning():
                    abandon_thread(t)
            if self._pill is not None:
                self._pill.hide_pill()
        except Exception:
            pass


def insert_text(w, text: str, trailing_space: bool = True) -> None:
    """Écrit le texte dicté au curseur (remplace la sélection), espaces ajustés."""
    if isinstance(w, QLineEdit):
        if w.hasSelectedText():
            start = w.selectionStart()
            end = start + len(w.selectedText())
        else:
            start = end = w.cursorPosition()
        full = w.text()
        piece = dict_core.spaced(full[:start], text, full[end:], trailing_space)
        if piece:
            w.insert(piece)
    else:
        cur = w.textCursor()
        block = cur.block().text()
        a = min(cur.selectionStart(), cur.selectionEnd()) - cur.block().position()
        b = max(cur.selectionStart(), cur.selectionEnd()) - cur.block().position()
        before = block[:a] if 0 <= a <= len(block) else ""
        after = block[b:] if 0 <= b <= len(block) else ""
        piece = dict_core.spaced(before, text, after, trailing_space)
        if piece:
            # Couleur du thème, jamais celle du texte voisin (un texte collé
            # depuis le web donnait au texte dicté son noir illisible, 27/10/2026).
            fmt = cur.charFormat()
            fmt.clearForeground()
            fmt.clearBackground()
            cur.insertText(piece, fmt)
            w.setTextCursor(cur)
    w.setFocus(Qt.FocusReason.OtherFocusReason)


_CONTROLLER: Optional[DictationController] = None


def controller() -> Optional[DictationController]:
    return _CONTROLLER


def install(app: QApplication) -> Optional[DictationController]:
    """main.py : équipe tous les champs de texte. Rien si le moteur manque."""
    global _CONTROLLER
    if _CONTROLLER is not None:
        return _CONTROLLER
    if not dict_core.engine_available():
        return None
    _CONTROLLER = DictationController(enabled=dict_core.is_enabled(), parent=app)
    app.installEventFilter(_CONTROLLER)
    app.aboutToQuit.connect(_CONTROLLER.shutdown)
    return _CONTROLLER


def uninstall(app: QApplication) -> None:
    """Retire le filtre (essais)."""
    global _CONTROLLER
    if _CONTROLLER is not None:
        app.removeEventFilter(_CONTROLLER)
        _CONTROLLER = None
