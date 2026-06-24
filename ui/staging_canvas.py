"""
ui/staging_canvas.py — Canevas vu de dessus, éditable (Mise en scène & Plan de feu).

Fond = plan d'architecte du décor ; par-dessus, des jetons DÉPLAÇABLES : caméra,
personnages, éléments (mode « staging ») ou lumières (mode « lighting »). Les
positions sont normalisées 0..1 et réécrites en direct dans le dict de mise en
scène (core/staging). Caméra et lumières ont une direction (flèche) pivotable.
"""

import math

from PyQt6.QtWidgets import (
    QGraphicsView, QGraphicsScene, QGraphicsEllipseItem,
    QGraphicsSimpleTextItem, QGraphicsLineItem, QGraphicsRectItem,
    QGraphicsPixmapItem,
)
from PyQt6.QtCore import Qt, QRectF, pyqtSignal
from PyQt6.QtGui import QPen, QBrush, QColor, QPixmap, QPainter
from ui.styles import CP
from ui.icons import load_icon
import core.projectors as _proj

_SIZE = 1000.0   # côté de la scène (unités) — normalisation = pos / _SIZE
_R    = 26       # rayon des jetons
_ARM  = _R * 1.9 # longueur de la flèche de direction (= position de la poignée)


def _token_icon_file(kind: str, model: dict) -> str:
    """Fichier d'icône (badge circulaire d'assets/icons) pour un jeton, ou "" si
    aucun (→ pastille colorée). Caméra/acteurs (Mise en scène) + projecteurs PAR
    FAMILLE (Plan de feu, cf. core.projectors.FAMILY_ICONS)."""
    if kind == "camera":
        return "camera_mise en scene.png"
    if kind == "actor":
        return "Acteur.png"
    if kind == "light":
        return _proj.family_icon((model or {}).get("family", ""))
    return ""


class _RotKnob(QGraphicsEllipseItem):
    """Poignée de rotation au bout de la flèche (jetons à direction)."""
    def __init__(self, parent, color):
        super().__init__(-7, -7, 14, 14, parent)
        self.setBrush(QBrush(QColor("#07080f")))
        self.setPen(QPen(QColor(color), 2))
        self.setZValue(12)
        self.setPos(0, -_ARM)


class _Token(QGraphicsEllipseItem):
    """Jeton déplaçable lié à une entrée du modèle (dict avec x, y[, angle])."""

    def __init__(self, canvas, kind: str, label: str, model: dict,
                 color: str, has_dir: bool = False, reference: bool = False):
        super().__init__(-_R, -_R, 2 * _R, 2 * _R)
        self._canvas  = canvas
        self.kind     = kind
        self.model    = model
        self.has_dir  = has_dir
        self.reference = reference   # affiché en référence (non éditable, estompé)
        if reference:
            # Référence (ex. caméra/acteurs visibles dans le Plan de feu) : non
            # déplaçable, estompée, sous les jetons actifs.
            self.setZValue(5)
            self.setOpacity(0.40)
        else:
            self.setZValue(10)
            self.setFlag(QGraphicsEllipseItem.GraphicsItemFlag.ItemIsMovable, True)
            self.setFlag(QGraphicsEllipseItem.GraphicsItemFlag.ItemIsSelectable, True)
            self.setFlag(QGraphicsEllipseItem.GraphicsItemFlag.ItemSendsGeometryChanges, True)
        self.setPos(model.get("x", 0.5) * _SIZE, model.get("y", 0.5) * _SIZE)
        # Projecteur ÉTEINT → jeton grisé (toujours déplaçable / clic droit).
        if kind == "light" and not (model.get("settings") or {}).get("on", True):
            self.setOpacity(0.30)
        if model.get("name"):
            self.setToolTip(model.get("name"))

        # Icône (badge circulaire) si disponible → remplace la pastille colorée +
        # les initiales ; l'ellipse devient un ANNEAU coloré (identité + sélection).
        # Repli (élément, ou famille sans icône) : pastille colorée + initiales.
        icon_file = _token_icon_file(kind, model)
        pix = load_icon(icon_file, size=int(2 * _R)) if icon_file else None
        if pix is not None and not pix.isNull():
            self.setBrush(QBrush(QColor(Qt.GlobalColor.transparent)))
            self.setPen(QPen(QColor(color), 2))
            ic = QGraphicsPixmapItem(pix, self)
            ic.setOffset(-_R, -_R)
            ic.setZValue(11)
            # Nom sous l'icône — seulement pour les jetons SANS direction
            # (acteurs/éléments) ; ceux à direction pivotent → label illisible tourné.
            if label and not has_dir:
                cap = QGraphicsSimpleTextItem(label, self)
                cap.setBrush(QBrush(QColor(color)))
                cf = cap.font(); cf.setBold(True); cf.setPointSize(8); cap.setFont(cf)
                cbr = cap.boundingRect()
                cap.setPos(-cbr.width() / 2, _R + 1)
        else:
            self.setBrush(QBrush(QColor(color)))
            self.setPen(QPen(QColor("#07080f"), 2))
            txt = QGraphicsSimpleTextItem(label, self)
            txt.setBrush(QBrush(QColor("#07080f")))
            f = txt.font(); f.setBold(True); f.setPointSize(9); txt.setFont(f)
            br = txt.boundingRect()
            txt.setPos(-br.width() / 2, -br.height() / 2)

        self._arrow = None
        self._knob  = None
        if has_dir:
            self._arrow = QGraphicsLineItem(0, 0, 0, -_ARM, self)
            self._arrow.setPen(QPen(QColor(color), 4))
            self._arrow.setZValue(9)
            # Poignée de rotation (sauf en référence, non éditable)
            if not reference:
                self._knob = _RotKnob(self, color)
            self.setRotation(model.get("angle", 0.0))

    def itemChange(self, change, value):
        if change == QGraphicsEllipseItem.GraphicsItemChange.ItemPositionHasChanged:
            self.model["x"] = max(0.0, min(1.0, self.pos().x() / _SIZE))
            self.model["y"] = max(0.0, min(1.0, self.pos().y() / _SIZE))
            if self._canvas:
                self._canvas.changed.emit()
        return super().itemChange(change, value)

    def rotate_by(self, delta: float):
        self.set_angle(self.model.get("angle", 0.0) + delta)

    def set_angle(self, angle: float):
        if not self.has_dir:
            return
        ang = angle % 360
        self.model["angle"] = ang
        self.setRotation(ang)
        if self._canvas:
            self._canvas.changed.emit()


class StagingCanvas(QGraphicsView):
    """Canevas éditable. mode = 'staging' (caméra/acteurs/éléments) ou 'lighting'
    (lumières). load(record) puis commit() pour relire les positions."""
    changed       = pyqtSignal()
    selection     = pyqtSignal()
    actor_context  = pyqtSignal(object)   # clic droit sur un acteur (model dict)
    light_context  = pyqtSignal(object)   # clic droit sur une lumière (model dict)
    camera_context = pyqtSignal(object)   # clic droit sur la caméra (model dict)
    empty_context  = pyqtSignal(float, float)  # clic droit sur le vide (x, y normalisés)

    def __init__(self, mode: str = "staging"):
        super().__init__()
        self._mode   = mode
        self._record = None
        self._tool   = "move"            # "move" | "rotate"
        self._rotating = None            # _Token en cours de rotation
        self._scene  = QGraphicsScene(0, 0, _SIZE, _SIZE)
        self.setScene(self._scene)
        self.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        self.setStyleSheet(f"background:{CP['bg2']};border:1px solid {CP['border']};border-radius:8px;")
        self.setMinimumHeight(420)
        self.scene().selectionChanged.connect(self.selection.emit)

    def set_tool(self, tool: str):
        self._tool = "rotate" if tool == "rotate" else "move"

    def resizeEvent(self, e):
        super().resizeEvent(e)
        self.fitInView(self._scene.sceneRect(), Qt.AspectRatioMode.KeepAspectRatio)

    # ── Rotation directe (poignée) + mode Rotation (glisser sur le jeton) ───────

    def _token_at(self, item):
        """Remonte jusqu'au _Token parent (item peut être texte/flèche/poignée)."""
        while item is not None and not isinstance(item, _Token):
            item = item.parentItem()
        return item

    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            sp   = self.mapToScene(e.pos())
            item = self._scene.itemAt(sp, self.transform())
            on_knob = isinstance(item, _RotKnob)
            tok = self._token_at(item)
            if tok is not None and tok.has_dir and not tok.reference and \
                    (on_knob or self._tool == "rotate"):
                self._rotating = tok
                tok.setSelected(True)
                self._apply_rotation(sp)
                e.accept()
                return
        super().mousePressEvent(e)

    def mouseMoveEvent(self, e):
        if self._rotating is not None:
            self._apply_rotation(self.mapToScene(e.pos()))
            e.accept()
            return
        super().mouseMoveEvent(e)

    def mouseReleaseEvent(self, e):
        if self._rotating is not None:
            self._rotating = None
            e.accept()
            return
        super().mouseReleaseEvent(e)

    def _apply_rotation(self, scene_pos):
        tok = self._rotating
        if tok is None:
            return
        c = tok.pos()
        dx = scene_pos.x() - c.x()
        dy = scene_pos.y() - c.y()
        # angle 0 = flèche vers le haut, horaire
        ang = math.degrees(math.atan2(dx, -dy))
        tok.set_angle(ang)

    def contextMenuEvent(self, e):
        sp   = self.mapToScene(e.pos())
        tok  = self._token_at(self._scene.itemAt(sp, self.transform()))
        if tok is None:
            # Clic droit sur le VIDE → menu d'ajout (acteur/caméra ou projecteur),
            # placé au point cliqué (coords normalisées 0..1).
            x = max(0.0, min(1.0, sp.x() / float(_SIZE)))
            y = max(0.0, min(1.0, sp.y() / float(_SIZE)))
            self.empty_context.emit(x, y)
            return
        # La caméra a un menu même en référence (Plan de feu) → régler sa hauteur.
        if tok.kind == "camera":
            self.camera_context.emit(tok.model)
            return
        if tok.reference:
            return
        if tok.kind == "actor":
            self.actor_context.emit(tok.model)
        elif tok.kind == "light":
            self.light_context.emit(tok.model)

    # ── Chargement / relecture ──────────────────────────────────────────────────

    def load(self, record: dict):
        self._record = record
        self._scene.clear()
        # Fond : plan d'architecte ou grille neutre
        plan = record.get("plan_image", "")
        pix = QPixmap(plan) if plan else QPixmap()
        if not pix.isNull():
            item = self._scene.addPixmap(pix.scaled(
                int(_SIZE), int(_SIZE), Qt.AspectRatioMode.IgnoreAspectRatio,
                Qt.TransformationMode.SmoothTransformation))
            item.setZValue(0)
        else:
            self._draw_grid()
        # Jetons
        if self._mode == "staging":
            self._scene.addItem(_Token(self, "camera", "CAM", record["camera"],
                                       CP["accent"], has_dir=True))
            for a in record.get("actors", []):
                self._scene.addItem(_Token(self, "actor", _initials(a.get("name", "?")),
                                           a, CP.get("green", "#3ddc97")))
            for p in record.get("props", []):
                self._scene.addItem(_Token(self, "prop", _initials(p.get("name", "?")),
                                           p, CP.get("text_dim", "#5a6a7a")))
        else:
            # Plan de feu : on AFFICHE la caméra et les acteurs placés en Mise en
            # scène (référence non éditable, estompée) pour éclairer juste.
            cam = record.get("camera")
            if cam:
                self._scene.addItem(_Token(self, "camera", "CAM", cam,
                                           CP["accent"], has_dir=True, reference=True))
            for a in record.get("actors", []):
                self._scene.addItem(_Token(self, "actor", _initials(a.get("name", "?")),
                                           a, CP.get("green", "#3ddc97"), reference=True))
            for p in record.get("props", []):
                self._scene.addItem(_Token(self, "prop", _initials(p.get("name", "?")),
                                           p, CP.get("text_dim", "#5a6a7a"), reference=True))
            # Lumières (éditables)
            for l in record.get("lights", []):
                self._scene.addItem(_Token(self, "light", _initials(l.get("name", "L")),
                                           l, "#f5c518", has_dir=True))
        self.fitInView(self._scene.sceneRect(), Qt.AspectRatioMode.KeepAspectRatio)

    def _draw_grid(self):
        bg = QGraphicsRectItem(0, 0, _SIZE, _SIZE)
        bg.setBrush(QBrush(QColor(CP["bg3"])))
        bg.setPen(QPen(QColor(CP["border"]), 2))
        bg.setZValue(0)
        self._scene.addItem(bg)
        pen = QPen(QColor(CP["border"]), 1)
        for i in range(1, 4):
            self._scene.addLine(i * _SIZE / 4, 0, i * _SIZE / 4, _SIZE, pen)
            self._scene.addLine(0, i * _SIZE / 4, _SIZE, i * _SIZE / 4, pen)

    def commit(self) -> dict:
        return self._record

    # ── Édition ──────────────────────────────────────────────────────────────────

    def selected_token(self):
        for it in self._scene.selectedItems():
            if isinstance(it, _Token):
                return it
        return None

    def add_actor(self, name: str, x: float = 0.35, y: float = 0.5):
        a = {"name": name, "x": x, "y": y}
        self._record.setdefault("actors", []).append(a)
        self._scene.addItem(_Token(self, "actor", _initials(name), a, CP.get("green", "#3ddc97")))
        self.changed.emit()

    def add_prop(self, name: str, x: float = 0.65, y: float = 0.5):
        p = {"name": name, "x": x, "y": y}
        self._record.setdefault("props", []).append(p)
        self._scene.addItem(_Token(self, "prop", _initials(name), p, CP.get("text_dim", "#5a6a7a")))
        self.changed.emit()

    def add_light(self, name: str, role: str, family: str = "", model: str = "",
                  x: float = 0.5, y: float = 0.3):
        l = {"name": name, "type": role, "family": family, "model": model,
             "x": x, "y": y, "angle": 180.0}
        self._record.setdefault("lights", []).append(l)
        self._scene.addItem(_Token(self, "light", _initials(name), l, "#f5c518", has_dir=True))
        self.changed.emit()

    def place_camera(self, x: float, y: float):
        """Place (ou crée) la caméra au point donné (coords normalisées)."""
        if self._record is None:
            return
        cam = self._record.setdefault("camera", {"x": 0.5, "y": 0.9, "angle": 0.0})
        cam["x"], cam["y"] = x, y
        self.load(self._record)
        self.changed.emit()

    def reload(self):
        """Recharge le canevas depuis le record courant (après édition externe)."""
        if self._record is not None:
            self.load(self._record)

    def _clearable_keys(self):
        return ("actors", "props") if self._mode == "staging" else ("lights",)

    def has_clearable(self) -> bool:
        """Y a-t-il quelque chose à supprimer ? (éléments éditables OU plan de fond)"""
        if self._record is None:
            return False
        if any(self._record.get(k) for k in self._clearable_keys()):
            return True
        return bool(self._record.get("plan_image"))

    def clear_all(self):
        """Retire TOUS les éléments éditables de ce mode (acteurs + accessoires en
        Mise en scène, projecteurs en Plan de feu) ET le PLAN DE DÉCOR assigné (fond).
        Conserve la caméra et les références non éditables. Le plan est figé sur
        « aucun » (plan_decor_id = __none__) pour qu'il ne se ré-rattache pas au
        rechargement via le décor du storyboard."""
        if self._record is None:
            return False
        keys = self._clearable_keys()
        had = (any(self._record.get(k) for k in keys)
               or bool(self._record.get("plan_image")))
        for k in keys:
            self._record[k] = []
        self._record["plan_image"] = ""
        self._record["plan_decor_id"] = "__none__"
        self.load(self._record)
        if had:
            self.changed.emit()
        return had

    def remove_selected(self):
        tok = self.selected_token()
        if not tok or tok.kind == "camera":
            return
        key = {"actor": "actors", "prop": "props", "light": "lights"}.get(tok.kind)
        if key and tok.model in self._record.get(key, []):
            self._record[key].remove(tok.model)
        self._scene.removeItem(tok)
        self.changed.emit()

    def remove_model(self, model: dict):
        """Retire un jeton donné par son modèle (clic droit → Supprimer)."""
        if self._record is None:
            return
        for key in ("actors", "props", "lights"):
            lst = self._record.get(key, [])
            if model in lst:
                lst.remove(model)
                self.load(self._record)
                self.changed.emit()
                return

    def rotate_selected(self, delta: float):
        tok = self.selected_token()
        if tok:
            tok.rotate_by(delta)


def _initials(name: str) -> str:
    name = (name or "?").strip()
    parts = name.split()
    if len(parts) >= 2:
        return (parts[0][:1] + parts[1][:1]).upper()
    return name[:3].upper()
