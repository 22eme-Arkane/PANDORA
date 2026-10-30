"""ui/timeline_bar.py — Frise de mise en scène de la vue 3D (Matthieu 29-30/10/2026).

Sous la vue 3D : lecture / pause, puis deux bandes sur la durée du plan, comme dans un logiciel de
montage. La RÈGLE du haut (secondes) sert à défiler : on y attrape toujours la tête de lecture.
La PISTE du bas montre les KEYFRAMES de l'élément choisi (personnage, caméra, décor…), chaque
élément ayant les siennes : glisser un losange change son temps, cliquer un losange y amène la
tête de lecture, clic droit : changer son action ou le supprimer ; cliquer à côté défile aussi.

« ＋ Keyframe » en pose une au temps courant (déplacer ensuite l'élément dans la vue la corrige) ;
le menu d'action donne ce que fait le personnage À PARTIR de cette keyframe (vide : marche ou
course selon la vitesse, repos à l'arrêt). Le widget ne connaît pas la vue : il émet des demandes,
la page les relaie.
"""
from __future__ import annotations

from PyQt6.QtCore import QPointF, QRectF, Qt, pyqtSignal
from PyQt6.QtGui import QColor, QFont, QPainter, QPainterPath, QPen
from PyQt6.QtWidgets import (QComboBox, QDoubleSpinBox, QHBoxLayout, QLabel, QMenu, QPushButton,
                             QSizePolicy, QToolButton, QVBoxLayout, QWidget)

from core.i18n import get_lang, translate
from ui.styles import CP

MARGIN = 12          # marge de la règle à gauche et à droite (px)
SCALE_H = 22         # hauteur de la règle des secondes (px)
KEY_GRAB = 8         # distance à laquelle on attrape un losange (px)
SAME_KEY = 0.06      # deux temps plus proches désignent la même keyframe (s)


def fmt_s(t: float) -> str:
    return f"{t:.1f}".replace(".", ",") + " s"


def _style(w) -> None:
    """Même allure que les boutons de la barre de la vue 3D (ui/page_3d._btn)."""
    w.setCursor(Qt.CursorShape.PointingHandCursor)
    w.setMinimumHeight(28)
    w.setStyleSheet(
        f"QPushButton,QToolButton{{background:{CP['bg2']};color:{CP['text_primary']};"
        f"border:1px solid {CP['border']};border-radius:6px;font-size:11px;font-weight:600;padding:0 10px;}}"
        f"QPushButton:hover,QToolButton:hover{{border-color:{CP['accent_dim']};}}"
        f"QPushButton:disabled{{color:{CP['text_dim']};}}")


class _Ruler(QWidget):
    """Règle des secondes, tête de lecture et piste des keyframes de l'élément choisi."""

    seek = pyqtSignal(float)
    key_moved = pyqtSignal(float, float)       # ancien temps, nouveau temps
    mark_menu = pyqtSignal(float, object)      # temps de la keyframe, position globale du clic

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(58)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setMouseTracking(True)
        self.duration = 5.0
        self.t = 0.0
        self.marks: list[dict] = []
        self.labels: dict[str, str] = {}
        self._drag = False
        self._press_key: dict | None = None    # keyframe attrapée (pas encore forcément déplacée)
        self._press_x = 0.0
        self._key_moved = False
        self._key_from = 0.0

    def _x(self, t: float) -> float:
        return MARGIN + (self.width() - 2 * MARGIN) * (t / max(1e-6, self.duration))

    def _t(self, x: float) -> float:
        return max(0.0, min(self.duration, (x - MARGIN) / max(1, self.width() - 2 * MARGIN) * self.duration))

    def _key_y(self) -> float:
        return SCALE_H + (self.height() - SCALE_H) / 2

    def _mark_at(self, x: float, y: float):
        """Keyframe sous la souris : seulement dans la piste, la règle reste à la tête de lecture."""
        if y < SCALE_H:
            return None
        hits = [mk for mk in self.marks if abs(self._x(float(mk.get("t", 0))) - x) <= KEY_GRAB]
        return min(hits, key=lambda mk: abs(self._x(float(mk.get("t", 0))) - x)) if hits else None

    def paintEvent(self, _e):   # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        p.fillRect(self.rect(), QColor(CP["bg2"]))
        p.fillRect(QRectF(0, 0, w, SCALE_H), QColor(CP["bg3"]))
        p.setPen(QPen(QColor(CP["border"]), 1))
        p.drawLine(QPointF(0, SCALE_H), QPointF(w, SCALE_H))
        f = QFont(self.font())
        f.setPointSizeF(7.5)
        p.setFont(f)
        # jusqu'à 30 s (Seedance 2.5) : secondes écrites de 1 en 1, 2 en 2, 5 en 5… selon la place
        pps = (w - 2 * MARGIN) / max(1e-6, self.duration)          # pixels par seconde
        every = next((s for s in (1, 2, 5, 10) if s * pps >= 36), 10)
        minor = 0.5 if 0.5 * pps >= 6 else 1.0
        steps = int(self.duration / minor + 1e-6) + 1
        for i in range(steps):
            t = i * minor
            x = self._x(t)
            whole = abs(t - round(t)) < 1e-6
            shown = whole and int(round(t)) % every == 0
            p.setPen(QPen(QColor(CP["text_dim"] if whole else CP["border"]), 1))
            p.drawLine(QPointF(x, SCALE_H), QPointF(x, SCALE_H - (6 if shown else 4 if whole else 3)))
            if shown:
                p.drawText(QRectF(x - 16, 1, 32, 13), Qt.AlignmentFlag.AlignCenter, f"{int(round(t))} s")
        # piste : trajet entre les keyframes puis losanges
        y = self._key_y()
        xs = sorted(self._x(float(mk.get("t", 0))) for mk in self.marks)
        if len(xs) >= 2:
            p.setPen(QPen(QColor(CP["accent_dim"]), 3))
            p.drawLine(QPointF(xs[0], y), QPointF(xs[-1], y))
        for mk in self.marks:
            x = self._x(float(mk.get("t", 0)))
            path = QPainterPath()
            r = 8 if mk is self._press_key else 6
            path.moveTo(x, y - r)
            path.lineTo(x + r, y)
            path.lineTo(x, y + r)
            path.lineTo(x - r, y)
            path.closeSubpath()
            current = abs(float(mk.get("t", 0)) - self.t) < SAME_KEY
            p.setPen(QPen(QColor(CP["text_primary"] if current else CP["bg0"]), 1.5 if current else 1))
            p.setBrush(QColor(CP["accent"] if mk.get("action") else CP["text_secondary"]))
            p.drawPath(path)
        # tête de lecture, avec sa poignée dans la règle
        x = self._x(self.t)
        gold = QColor(CP["gold"] if "gold" in CP else "#e8c46a")
        p.setPen(QPen(gold, 2))
        p.drawLine(QPointF(x, 0), QPointF(x, h))
        handle = QPainterPath()
        handle.moveTo(x - 6, 0)
        handle.lineTo(x + 6, 0)
        handle.lineTo(x, 9)
        handle.closeSubpath()
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(gold)
        p.drawPath(handle)
        p.end()

    def mousePressEvent(self, e):   # noqa: N802
        pos = e.position()
        mk = self._mark_at(pos.x(), pos.y())
        if e.button() == Qt.MouseButton.RightButton:
            if mk is not None:
                self.mark_menu.emit(float(mk.get("t", 0)), e.globalPosition().toPoint())
            return
        if mk is not None:
            self._press_key = mk
            self._press_x = pos.x()
            self._key_moved = False
            self._key_from = float(mk.get("t", 0))
            self.update()
            return
        self._drag = True
        self.seek.emit(self._t(pos.x()))

    def mouseMoveEvent(self, e):   # noqa: N802
        pos = e.position()
        if self._press_key is not None:
            if self._key_moved or abs(pos.x() - self._press_x) > 3:
                self._key_moved = True
                self._press_key["t"] = round(self._t(pos.x()) * 20) / 20   # au 1/20 s
                self.setToolTip(fmt_s(self._press_key["t"]))
                self.update()
            return
        if self._drag:
            self.seek.emit(self._t(pos.x()))
            return
        mk = self._mark_at(pos.x(), pos.y())
        self.setCursor(Qt.CursorShape.SizeHorCursor if mk is not None else Qt.CursorShape.ArrowCursor)
        if mk is not None:
            act = self.labels.get(mk.get("action", ""), "") or translate("automatique")
            self.setToolTip(f"{fmt_s(float(mk.get('t', 0)))} · {act}")
        else:
            self.setToolTip("")

    def mouseReleaseEvent(self, _e):   # noqa: N802
        self._drag = False
        mk, self._press_key = self._press_key, None
        if mk is None:
            return
        if self._key_moved:
            self.key_moved.emit(self._key_from, float(mk.get("t", 0)))
        else:
            self.seek.emit(float(mk.get("t", 0)))
        self.update()


class TimelineBar(QWidget):
    """Frise : lecture, règle, keyframes et action de l'élément choisi."""

    seek = pyqtSignal(float)
    play_toggled = pyqtSignal(bool)
    mark_requested = pyqtSignal(str, float, object)     # id, temps, action (None = inchangée)
    unmark_requested = pyqtSignal(str, float)
    key_moved = pyqtSignal(str, float, float)           # id, ancien temps, nouveau temps
    element_picked = pyqtSignal(str)                    # élément choisi dans la liste de la frise
    duration_changed = pyqtSignal(float)                # nouvelle durée du plan, en secondes

    def __init__(self, parent=None):
        super().__init__(parent)
        self._id = ""
        self._name = ""
        self._person = True
        self._playing = False
        self._actions: list[dict] = []
        self._groups: list = []
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 2, 0, 0)
        lay.setSpacing(4)
        top = QHBoxLayout()
        top.setSpacing(6)
        self.btn_play = QToolButton()
        self.btn_play.setText("▶")
        self.btn_play.setToolTip(translate("Lire la mise en scène du plan"))
        self.btn_play.setFixedSize(30, 26)
        self.btn_play.clicked.connect(self._toggle)
        top.addWidget(self.btn_play)
        self.lbl_time = QLabel("0,0 s")
        self.lbl_time.setFixedWidth(92)
        self.lbl_time.setStyleSheet(f"color:{CP['text_primary']};font-size:11px;font-weight:600;")
        top.addWidget(self.lbl_time)
        self.ruler = _Ruler()
        self.ruler.seek.connect(self._seek)
        self.ruler.key_moved.connect(lambda a, b: self._id and self.key_moved.emit(self._id, a, b))
        self.ruler.mark_menu.connect(self._mark_menu)
        top.addWidget(self.ruler, 1)
        # Durée du plan (Matthieu 30/10/2026 : « des plans jusqu'à 30 s avec Seedance 2.5 ») :
        # c'est celle du storyboard ; la frise et la prévisualisation durent autant.
        self.spin_dur = QDoubleSpinBox()
        self.spin_dur.setDecimals(1)
        self.spin_dur.setSingleStep(0.5)
        self.spin_dur.setSuffix(" s")
        self.spin_dur.setKeyboardTracking(False)       # une seule mise à jour, à la validation
        self.spin_dur.setRange(1.0, 15.0)
        self.spin_dur.setValue(5.0)
        self.spin_dur.setFixedWidth(92)
        self.spin_dur.setMinimumHeight(28)
        self.spin_dur.setStyleSheet(
            f"QDoubleSpinBox{{background:{CP['bg2']};color:{CP['text_primary']};"
            f"border:1px solid {CP['border']};border-radius:6px;font-size:11px;font-weight:600;padding:0 4px;}}")
        self.spin_dur.valueChanged.connect(self._duration_picked)
        top.addWidget(self.spin_dur, 0, Qt.AlignmentFlag.AlignTop)
        lay.addLayout(top, 1)
        row = QHBoxLayout()
        row.setSpacing(6)
        # Chaque élément a ses keyframes : on choisit ici lequel on règle (ou en cliquant dans la vue)
        self.combo_el = QComboBox()
        self.combo_el.setMinimumWidth(170)
        self.combo_el.setToolTip(translate("Élément dont la frise montre les keyframes"))
        self.combo_el.activated.connect(lambda _i: self.element_picked.emit(self.combo_el.currentData() or ""))
        row.addWidget(self.combo_el)
        self.lbl_target = QLabel("")
        self.lbl_target.setStyleSheet(f"color:{CP['text_secondary']};font-size:10px;")
        row.addWidget(self.lbl_target, 1)
        self.combo = QComboBox()
        self.combo.setMinimumWidth(190)
        self.combo.setToolTip(translate("Ce que fait le personnage à partir de cette keyframe"))
        self.combo.activated.connect(self._action_picked)
        row.addWidget(self.combo)
        self.btn_mark = QPushButton(translate("＋ Keyframe"))
        self.btn_mark.setToolTip(translate("Pose une keyframe au temps courant ; déplacez ensuite "
                                           "l'élément dans la vue pour la placer"))
        self.btn_mark.clicked.connect(lambda: self._id and self.mark_requested.emit(
            self._id, self.ruler.t, self.combo.currentData() if self._person else None))
        row.addWidget(self.btn_mark)
        self.btn_unmark = QPushButton(translate("Supprimer la keyframe"))
        self.btn_unmark.clicked.connect(lambda: self._id and self.unmark_requested.emit(self._id, self.ruler.t))
        row.addWidget(self.btn_unmark)
        lay.addLayout(row)
        for w in (self.btn_play, self.btn_mark, self.btn_unmark):
            _style(w)
        # Espace et Suppr restent aux raccourcis de la vue 3D, même après un clic ici
        for w in (self.btn_play, self.btn_mark, self.btn_unmark, self.combo, self.combo_el):
            w.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.ruler.setFocusPolicy(Qt.FocusPolicy.ClickFocus)
        self.btn_play.setFixedSize(34, 28)
        self.set_elements([])
        self.set_target("", "", [])

    # ---------------------------------------------------------------- état
    def set_actions(self, info: dict) -> None:
        self._actions = list((info or {}).get("actions") or [])
        self._groups = list((info or {}).get("groups") or [])
        en = get_lang() == "en"
        self.ruler.labels = {a["id"]: (a.get("en") if en else a.get("fr")) or a["id"] for a in self._actions}
        self.combo.blockSignals(True)
        self.combo.clear()
        self.combo.addItem(translate("Automatique (marche, course ou repos)"), "")
        for g in self._groups:
            items = [a for a in self._actions if a.get("group") == g[0]]
            if not items:
                continue
            self.combo.insertSeparator(self.combo.count())
            for a in items:
                self.combo.addItem(f"{g[2] if en else g[1]} · {(a.get('en') if en else a.get('fr'))}", a["id"])
        self.combo.blockSignals(False)
        self._sync_combo()

    def set_elements(self, items: list[tuple[str, str]]) -> None:
        """Éléments de la scène (id, nom) proposés dans la liste de la frise."""
        self.combo_el.blockSignals(True)
        self.combo_el.clear()
        self.combo_el.addItem(translate("— Choisir un élément —"), "")
        for oid, name in items:
            self.combo_el.addItem(name, oid)
        self.combo_el.setCurrentIndex(max(0, self.combo_el.findData(self._id)))
        self.combo_el.blockSignals(False)

    def set_duration(self, d: float, max_s: float | None = None, engine: str = "") -> None:
        """Durée affichée ; `max_s` : plafond du moteur visé (30 s en Seedance 2.5)."""
        self.ruler.duration = max(1.0, float(d or 5))
        top = float(max_s or self.spin_dur.maximum() or 15)
        self.spin_dur.blockSignals(True)
        # jamais rabotée à l'affichage : un plan plus long que le plafond reste lisible
        self.spin_dur.setRange(1.0, max(top, self.ruler.duration))
        self.spin_dur.setValue(self.ruler.duration)
        self.spin_dur.blockSignals(False)
        if max_s:
            tip = translate("Durée du plan au storyboard : la frise et la prévisualisation durent "
                            "autant. Jusqu'à {n} s").format(n=f"{top:g}")
            self.spin_dur.setToolTip(tip + (f" ({engine})." if engine else "."))
        self.set_time(min(self.ruler.t, self.ruler.duration))

    def set_time(self, t: float, playing: bool | None = None) -> None:
        self.ruler.t = max(0.0, float(t or 0))
        self.lbl_time.setText(f"{fmt_s(self.ruler.t)} / {fmt_s(self.ruler.duration)}")
        if playing is not None and playing != self._playing:
            self._playing = playing
            self.btn_play.setText("⏸" if playing else "▶")
        self.ruler.update()
        self._sync_combo()

    def set_target(self, oid: str, name: str, marks: list, person: bool = True) -> None:
        """Élément dont on montre et modifie les keyframes ("" : aucun). Seuls les personnages
        jouent des actions ; les autres éléments n'ont que leur place et leur orientation."""
        self._id, self._name, self._person = oid or "", name or "", bool(person)
        self.ruler.marks = list(marks or [])
        on = bool(self._id)
        self.btn_mark.setEnabled(on)
        self.btn_unmark.setEnabled(on)
        self.combo.setEnabled(on and self._person)
        self.combo_el.setCurrentIndex(max(0, self.combo_el.findData(self._id)))
        if not on:
            self.lbl_target.setText(translate("Sélectionnez un élément pour poser ses keyframes."))
        else:
            n = len(self.ruler.marks)
            self.lbl_target.setText(translate("{n} keyframe(s)").format(n=n) if n
                                    else translate("fixe (aucune keyframe)"))
        self.ruler.update()
        self._sync_combo()

    def set_marks(self, oid: str, marks: list) -> None:
        if oid == self._id:
            self.set_target(self._id, self._name, marks, self._person)

    def _current_mark(self):
        return next((m for m in self.ruler.marks if abs(float(m.get("t", 0)) - self.ruler.t) < SAME_KEY), None)

    def _sync_combo(self) -> None:
        mk = self._current_mark()
        self.btn_unmark.setEnabled(bool(self._id) and mk is not None)
        i = self.combo.findData((mk or {}).get("action", ""))
        self.combo.blockSignals(True)
        self.combo.setCurrentIndex(max(0, i))
        self.combo.blockSignals(False)

    # ---------------------------------------------------------------- actions de l'utilisateur
    def _toggle(self):
        self.play_toggled.emit(not self._playing)

    def _seek(self, t: float):
        self.set_time(t)
        self.seek.emit(t)

    def _duration_picked(self, d: float):
        if abs(float(d) - self.ruler.duration) < 1e-6:
            return
        self.ruler.duration = max(1.0, float(d))
        self.set_time(min(self.ruler.t, self.ruler.duration))
        self.duration_changed.emit(self.ruler.duration)

    def _action_picked(self, _i):
        if self._id:
            # sur une keyframe existante : change son action ; sinon en pose une avec cette action
            self.mark_requested.emit(self._id, self.ruler.t, self.combo.currentData() or "")

    def _mark_menu(self, t: float, pos):
        menu = QMenu(self)
        go = menu.addAction(translate("Aller à cette keyframe"))
        choices = {}
        if self._person and self._actions:
            sub = menu.addMenu(translate("Action à partir de cette keyframe"))
            choices[sub.addAction(translate("Automatique (marche, course ou repos)"))] = ""
            en = get_lang() == "en"
            for g in self._groups:
                items = [a for a in self._actions if a.get("group") == g[0]]
                if items:
                    gm = sub.addMenu(g[2] if en else g[1])
                    for a in items:
                        choices[gm.addAction(a.get("en") if en else a.get("fr"))] = a["id"]
        rm = menu.addAction(translate("Supprimer la keyframe"))
        chosen = menu.exec(pos)
        if chosen is go:
            self._seek(t)
        elif chosen is rm and self._id:
            self.unmark_requested.emit(self._id, t)
        elif chosen in choices and self._id:
            self.mark_requested.emit(self._id, t, choices[chosen])
