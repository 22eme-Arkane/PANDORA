"""ui/page_3d.py — Onglet « 3D » : lumière, mise en scène et décor de chaque plan.

Demande Matthieu (29/10/2026) : le Plan de feu devient un vrai outil 3D, qui reprend le
plan de feu d'ARKLIGHT PC (projecteurs réels, grip, décor, mannequins, caméra avec sa
focale) et enrichit le prompt. Remplace PageLighting dans la navigation (clé
« plan_de_feu » conservée : raccourcis et liens internes restent valables).

  gauche  : plans du storyboard (même liste que l'ancien Plan de feu) ;
  centre  : la vue 3D d'ARKLIGHT (ui/scene3d_web), sa barre d'outils et la frise ;
  droite  : UN SEUL panneau : les réglages de l'élément sélectionné, puis le texte du prompt.

Le haut du panneau de droite est soit l'inspecteur d'ARKLIGHT (un projecteur : il vit dans la page
web, la vue 3D s'étend donc sous toute la largeur), soit les réglages de PANDORA posés par-dessus
(les autres éléments). La vue ne change jamais de taille : c'est aussi ce qui évite les flashs noirs.

Chaque modification faite dans la vue est enregistrée dans la scène du plan (core/scene3d), mais le
prompt du storyboard ne change QUE sur demande (Matthieu 30/10/2026) : « Inscrire dans le
storyboard » (ce plan), ou le menu Action (tous les plans).
"""
from __future__ import annotations

import os

from PyQt6.QtCore import QRectF, QSize, Qt, QTimer
from PyQt6.QtGui import QColor, QCursor, QIcon, QPainter, QPixmap
from PyQt6.QtWidgets import (QCheckBox, QComboBox, QDoubleSpinBox, QFrame, QGridLayout, QHBoxLayout,
                             QLabel, QLineEdit, QListWidget, QListWidgetItem, QMenu,
                             QPushButton, QScrollArea, QSpinBox, QStackedWidget,
                             QVBoxLayout, QWidget)

import core.scene3d as scene3d
import core.scene3d_prompt as scene_text
import core.storyboard as sb_api
from core.i18n import translate
from ui.lighting_workspace import LightingShotCard, sequence_label
from ui.scene3d_web import Scene3DView, share_image
from ui.styles import CP

# Poses du mannequin d'ARKLIGHT (shared/props.js)
POSES = (("standing", "Debout"), ("walking", "Marche"), ("sitting", "Assis"), ("lying", "Allongé"),
         ("crossed", "Bras croisés"), ("phone", "Au téléphone"), ("pointing", "Montre du doigt"),
         ("handsup", "Bras levés"))
SENSORS = (("s35", "Super 35"), ("ff", "Plein format"), ("m43", "Micro 4/3"))
VIEWS = (("persp", "Perspective", "cube"), ("top", "Dessus", "view-top"), ("front", "Face", "view-front"),
         ("side", "Côté", "view-side"))
RIGHT_W = 340        # largeur du panneau de droite (la même que l'inspecteur d'ARKLIGHT, pandora.css)
PROMPT_H = 236       # hauteur de la zone du prompt, sous les réglages


def _btn(text: str, tip: str = "", accent: str | None = None) -> QPushButton:
    b = QPushButton(translate(text))
    b.setCursor(Qt.CursorShape.PointingHandCursor)
    b.setMinimumHeight(30)
    if tip:
        b.setToolTip(translate(tip))
    col = accent or CP["text_primary"]
    # Coché = cadre NÉON (Matthieu 29/10/2026 : « sinon on ne sait pas qui est
    # sélectionné ») : bord de 2 px à la couleur d'accent et léger halo de fond ; la
    # marge intérieure perd 1 px pour que le bouton ne change pas de taille.
    b.setStyleSheet(
        f"QPushButton{{background:{CP['bg2']};color:{col};border:1px solid {CP['border']};"
        "border-radius:6px;font-size:11px;font-weight:600;padding:0 10px;}"
        f"QPushButton:hover{{border-color:{CP['accent_dim']};}}"
        f"QPushButton:checked{{border:2px solid {CP['accent']};color:{CP['accent']};"
        "background:rgba(78,205,196,0.14);padding:0 9px;}")
    return b


def _svg_pixmap(name: str, color: str, side: int = 18) -> QPixmap:
    """Pictogramme d'ARKLIGHT (assets/icons/vue3d), à la couleur demandée."""
    from PyQt6.QtSvg import QSvgRenderer
    from core.paths import assets_root
    pm = QPixmap(side * 2, side * 2)
    pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm)
    QSvgRenderer(os.path.join(assets_root(), "assets", "icons", "vue3d", f"{name}.svg")).render(
        p, QRectF(0, 0, side * 2, side * 2))
    p.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceIn)
    p.fillRect(pm.rect(), QColor(color))
    p.end()
    pm.setDevicePixelRatio(2)
    return pm


def _icon_btn(name: str, tip: str) -> QPushButton:
    """Bouton à pictogramme, coché en cadre néon comme les autres (nom complet en infobulle)."""
    b = _btn("", tip)
    b.setText("")
    icon = QIcon()
    icon.addPixmap(_svg_pixmap(name, CP["text_primary"]), QIcon.Mode.Normal, QIcon.State.Off)
    icon.addPixmap(_svg_pixmap(name, CP["accent"]), QIcon.Mode.Normal, QIcon.State.On)
    b.setIcon(icon)
    b.setIconSize(QSize(18, 18))
    b.setFixedSize(36, 30)
    b.setFocusPolicy(Qt.FocusPolicy.NoFocus)
    return b


def _title(text: str) -> QLabel:
    lab = QLabel(translate(text))
    lab.setStyleSheet(f"color:{CP['accent']};font-size:10px;font-weight:800;letter-spacing:1px;"
                      "background:transparent;border:none;padding-top:6px;")
    return lab


def _small(text: str) -> QLabel:
    lab = QLabel(translate(text))
    lab.setStyleSheet(f"color:{CP['text_dim']};font-size:10px;background:transparent;border:none;")
    return lab


class _Inspector(QWidget):
    """Réglages de l'élément sélectionné dans la vue (projecteur, personnage, caméra, objet)."""

    def __init__(self, page: "Page3D"):
        super().__init__()
        self._page = page
        self._sel: dict = {}
        self._busy = False
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(6)
        self._head = QLabel(translate("Aucune sélection"))
        self._head.setWordWrap(True)
        self._head.setStyleSheet(f"color:{CP['text_primary']};font-size:12px;font-weight:700;"
                                 "background:transparent;border:none;")
        lay.addWidget(self._head)
        self._name = QLineEdit()
        self._name.setPlaceholderText(translate("Nom"))
        self._name.editingFinished.connect(lambda: self._update({"name": self._name.text().strip()}))
        lay.addWidget(self._name)
        self._stack = QStackedWidget()
        # la pile prend la hauteur de la page AFFICHÉE (pas celle du plus grand formulaire)
        self._stack.currentChanged.connect(self._fit_stack)
        lay.addWidget(self._stack)
        self._stack.addWidget(QWidget())                    # 0 : rien
        self._stack.addWidget(QWidget())                    # 1 : projecteur (inspecteur d'ARKLIGHT)
        self._stack.addWidget(self._build_person())        # 2 : personnage
        self._stack.addWidget(self._build_camera())        # 3 : caméra
        self._stack.addWidget(QWidget())                    # 4 : autre objet
        row = QHBoxLayout()
        self._btn_frame = _btn("Cadrer", "Centrer la vue sur l'élément")
        self._btn_frame.clicked.connect(self._frame_clicked)
        self._btn_del = _btn("Supprimer", "", CP["red"])
        self._btn_del.clicked.connect(self._delete)
        row.addWidget(self._btn_frame)
        row.addWidget(self._btn_del)
        lay.addLayout(row)
        self.show_selection({})
        self._fit_stack(0)

    def _frame_clicked(self) -> None:
        # Une caméra : elle se tourne vers le personnage. Le reste : la vue se centre sur l'élément.
        oid = self._sel.get("id")
        if str((self._sel.get("data") or {}).get("type", "")).startswith("camera"):
            self._page.view.send("frame.person", id=oid)
        else:
            self._page.view.send("select", id=oid, frame=True)

    def _fit_stack(self, index: int) -> None:
        from PyQt6.QtWidgets import QSizePolicy
        for i in range(self._stack.count()):
            pol = QSizePolicy.Policy.Preferred if i == index else QSizePolicy.Policy.Ignored
            self._stack.widget(i).setSizePolicy(QSizePolicy.Policy.Preferred, pol)
        self._stack.adjustSize()

    # ---------------------------------------------------------------- formulaires
    def _build_person(self) -> QWidget:
        w = QWidget()
        f = QVBoxLayout(w)
        f.setContentsMargins(0, 0, 0, 0)
        f.addWidget(_small("Personnage du casting"))
        self._p_char = QComboBox()
        self._p_char.activated.connect(self._char_changed)
        f.addWidget(self._p_char)
        f.addWidget(_small("Pose"))
        self._p_pose = QComboBox()
        for key, lab in POSES:
            self._p_pose.addItem(translate(lab), key)
        self._p_pose.activated.connect(lambda _i: self._update({"props": {"pose": self._p_pose.currentData()}}))
        f.addWidget(self._p_pose)
        row = QHBoxLayout()
        row.addWidget(_small("Taille (cm)"))
        self._p_h = QSpinBox()
        self._p_h.setRange(60, 220)
        self._p_h.editingFinished.connect(lambda: self._update({"props": {"height": int(self._p_h.value())}}))
        row.addWidget(self._p_h)
        f.addLayout(row)
        f.addStretch(1)   # champs serrés en haut (la pile prend la hauteur du plus grand)
        return w

    def _build_camera(self) -> QWidget:
        w = QWidget()
        f = QVBoxLayout(w)
        f.setContentsMargins(0, 0, 0, 0)
        row = QHBoxLayout()
        row.addWidget(_small("Focale (mm)"))
        self._c_focal = QSpinBox()
        self._c_focal.setRange(8, 300)
        self._c_focal.editingFinished.connect(lambda: self._update({"props": {"focal": int(self._c_focal.value())}}))
        row.addWidget(self._c_focal)
        f.addLayout(row)
        self._c_sensor = QComboBox()
        for key, lab in SENSORS:
            self._c_sensor.addItem(translate(lab), key)
        self._c_sensor.activated.connect(lambda _i: self._update({"props": {"sensor": self._c_sensor.currentData()}}))
        f.addWidget(self._c_sensor)
        row = QHBoxLayout()
        row.addWidget(_small("Hauteur d'objectif (m)"))
        self._c_lens = QDoubleSpinBox()
        self._c_lens.setRange(0.15, 8.0)
        self._c_lens.setToolTip(translate("Monter ou descendre la caméra sur son pied : ici, ou avec la "
                                          "flèche verticale de ses poignées dans la vue"))
        self._c_lens.setSingleStep(0.05)
        self._c_lens.editingFinished.connect(lambda: self._update({"props": {"lens": round(self._c_lens.value(), 2)}}))
        row.addWidget(self._c_lens)
        f.addLayout(row)
        self._c_shot = QCheckBox(translate("Caméra du plan (celle du prompt)"))
        self._c_shot.toggled.connect(self._shot_camera_toggled)
        f.addWidget(self._c_shot)
        self._c_look = _btn("Voir par cette caméra")
        self._c_look.clicked.connect(lambda: self._page.view.send("look", id=self._sel.get("id")))
        f.addWidget(self._c_look)
        f.addStretch(1)   # champs serrés en haut (la pile prend la hauteur du plus grand)
        return w

    # ---------------------------------------------------------------- affichage
    def show_selection(self, sel: dict) -> None:
        self._sel = sel or {}
        data = self._sel.get("data") or {}
        kind = self._sel.get("kind")
        self._busy = True
        try:
            has = bool(kind)
            self._name.setVisible(has)
            self._btn_frame.setVisible(has)
            self._btn_del.setVisible(has)
            self._name.setText(data.get("name", ""))
            camera = str(data.get("type", "")).startswith("camera")
            self._btn_frame.setText(translate("Cadrer le personnage" if camera else "Cadrer"))
            if kind == "fixture":
                self._head.setText(translate("Projecteur"))
                self._stack.setCurrentIndex(1)
            elif kind == "object" and str(data.get("type", "")).startswith("person"):
                props = data.get("props") or {}
                self._head.setText(translate("Personnage"))
                self._fill_characters(data)
                i = self._p_pose.findData(props.get("pose", "standing"))
                self._p_pose.setCurrentIndex(max(0, i))
                self._p_h.setValue(int(props.get("height") or 175))
                self._stack.setCurrentIndex(2)
            elif kind == "object" and str(data.get("type", "")).startswith("camera"):
                props = data.get("props") or {}
                self._head.setText(translate("Caméra"))
                self._c_focal.setValue(int(props.get("focal") or 35))
                self._c_sensor.setCurrentIndex(max(0, self._c_sensor.findData(props.get("sensor", "s35"))))
                self._c_lens.setValue(float(props.get("lens") or 1.45))
                self._c_shot.setChecked(self._page.shot_camera_id() == data.get("id"))
                self._stack.setCurrentIndex(3)
            elif kind == "object":
                self._head.setText(translate("Élément du décor"))
                self._stack.setCurrentIndex(4)
            else:
                self._head.setText(translate("Aucune sélection — cliquez un élément dans la vue, "
                                             "ou ajoutez-en un avec les boutons « + »."))
                self._stack.setCurrentIndex(0)
        finally:
            self._busy = False

    def _fill_characters(self, data: dict) -> None:
        self._p_char.blockSignals(True)
        self._p_char.clear()
        self._p_char.addItem(translate("— Figurant (sans fiche) —"), "")
        for name in self._page.character_names():
            self._p_char.addItem(name, name)
        cur = (data.get("pandora") or {}).get("name") or ""
        i = self._p_char.findData(cur)
        self._p_char.setCurrentIndex(i if i >= 0 else 0)
        self._p_char.blockSignals(False)

    # ---------------------------------------------------------------- modifications
    def _update(self, changes: dict) -> None:
        if self._busy or not self._sel.get("id"):
            return
        self._page.view.send("update", id=self._sel["id"], changes=changes)

    def _char_changed(self, _i) -> None:
        name = self._p_char.currentData() or ""
        changes = {"pandora": {"kind": "character" if name else "extra", "name": name}}
        if name:
            changes["name"] = name
            self._name.setText(name)
        self._update(changes)

    def _shot_camera_toggled(self, on: bool) -> None:
        if not self._busy and on and self._sel.get("id"):
            self._page.set_shot_camera(self._sel["id"])

    def _delete(self) -> None:
        if self._sel.get("id"):
            self._page.view.send("remove", id=self._sel["id"])
            self.show_selection({})


class Page3D(QWidget):
    """Onglet « 3D » (voir le module)."""

    # Comme l'ancien Plan de feu : la liste construit une carte par plan, le rafraîchissement
    # est donc planifié par PandoraWindow après le premier rendu de l'onglet.
    DEFER_NAV_REFRESH = True

    def __init__(self):
        super().__init__()
        self._all_shots: list[dict] = []
        self._shots: list[dict] = []
        self._shot: dict | None = None
        self._scene: dict | None = None
        self._catalog: dict = {}
        self.setStyleSheet(f"background:{CP['bg0']};")
        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        root.addWidget(self._build_left())
        root.addWidget(self._build_work(), 1)

    # ---------------------------------------------------------------- construction
    def _build_left(self) -> QWidget:
        left = QFrame()
        left.setObjectName("Scene3DShots")
        left.setFixedWidth(272)
        left.setStyleSheet("QFrame#Scene3DShots{background:" + CP["bg1"] + ";"
                           f"border-right:1px solid {CP['border']};}}")
        ll = QVBoxLayout(left)
        ll.setContentsMargins(10, 12, 10, 10)
        ll.setSpacing(8)
        ll.addWidget(_title("PLANS DU STORYBOARD"))
        self._seq = QComboBox()
        self._seq.setMinimumHeight(32)
        self._seq.currentIndexChanged.connect(lambda _i: self._rebuild_list(self._current_id()))
        ll.addWidget(self._seq)
        self._list = QListWidget()
        self._list.setSpacing(5)
        self._list.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._list.setStyleSheet(
            "QListWidget{background:transparent;border:none;outline:none;padding:0;}"
            f"QListWidget::item{{background:{CP['bg2']};border:1px solid {CP['border']};border-radius:8px;}}"
            f"QListWidget::item:selected{{border:1px solid {CP['accent']};}}")
        self._list.currentRowChanged.connect(self._on_shot_changed)
        ll.addWidget(self._list, 1)
        self._count = _small("")
        ll.addWidget(self._count)
        return left

    def _build_work(self) -> QWidget:
        """Barre en haut ; la vue 3D sous toute la largeur (l'inspecteur d'ARKLIGHT en occupe la
        droite), les réglages de PANDORA posés dessus ; frise à gauche et prompt à droite en bas."""
        work = QWidget()
        grid = QGridLayout(work)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setSpacing(0)
        grid.setColumnStretch(0, 1)
        grid.setColumnMinimumWidth(1, RIGHT_W)
        grid.setRowStretch(1, 1)
        grid.addWidget(self._build_bar(), 0, 0, 1, 2)
        self.view = Scene3DView()
        self.view.ready.connect(self._on_ready)
        self.view.scene_edited.connect(self._on_scene_edited)
        self.view.selection_changed.connect(self._on_selection)
        self.view.page_event.connect(self._on_page_event)
        grid.addWidget(self.view, 1, 0, 1, 2)
        self._sel_panel = self._build_selection()
        grid.addWidget(self._sel_panel, 1, 1)
        self._sel_panel.raise_()
        grid.addWidget(self._build_timeline(), 2, 0)
        grid.addWidget(self._build_prompt(), 2, 1)
        return work

    def _build_bar(self) -> QWidget:
        host = QWidget()
        bar = QHBoxLayout(host)
        bar.setContentsMargins(8, 8, 8, 6)
        bar.setSpacing(5)
        # Menu Action, à gauche des points de vue, comme dans les autres onglets. Les exports et
        # l'inscription de TOUS les plans y vivent ; les boutons sources gardent l'état à jour.
        self._btn_previs = _btn("🎬  Exporter la vidéo",
                                "Rend le plan vu par sa caméra, avec la mise en scène de la frise "
                                "(1280×720, 24 i/s). Studio IA → RENDU & AUDIO → « Prévisualisation "
                                "de la vue 3D » l'envoie à Seedance comme référence.")
        self._btn_previs.clicked.connect(self._render_previs)
        self._btn_previs_open = _btn("▶  Voir la vidéo exportée", "Ouvre la vidéo exportée de ce plan")
        self._btn_previs_open.clicked.connect(self._open_previs)
        self._btn_write_all = _btn("Inscrire toutes les modifications dans le storyboard",
                                   "Écrit dans le storyboard la mise en scène et la lumière de TOUS "
                                   "les plans qui ont une scène 3D")
        self._btn_write_all.clicked.connect(self._write_all)
        from ui.widgets import make_actions_menu_button
        self._btn_action = make_actions_menu_button(
            host, [self._btn_previs, self._btn_previs_open, self._btn_write_all])
        self._btn_action.setFixedHeight(30)
        bar.addWidget(self._btn_action)
        bar.addSpacing(10)
        # Points de vue : celui qui est actif porte le cadre néon (Matthieu 29/10/2026).
        # « Caméra » = ce que filme la caméra du plan ; Échap (ou un autre point de
        # vue) en sort. Une vue libre (orbite à la souris) ne coche rien.
        self._view_btns = {}
        for key, lab, icon in VIEWS:
            b = _icon_btn(icon, lab)
            b.setCheckable(True)
            b.clicked.connect(lambda _c=False, k=key: self._pick_view(k))
            bar.addWidget(b)
            self._view_btns[key] = b
        self._btn_look = _icon_btn("camera", "Voir exactement ce que filme la caméra du plan "
                                   "(Échap pour revenir à la vue libre)")
        self._btn_look.setCheckable(True)
        self._btn_look.clicked.connect(lambda _c=False: self._pick_view("camera"))
        bar.addWidget(self._btn_look)
        self._view_btns["camera"] = self._btn_look
        self._mark_view("persp")
        bar.addSpacing(10)
        self._btn_move = _icon_btn("move", "Déplacer")
        self._btn_rot = _icon_btn("rotate", "Pivoter")
        for b, mode in ((self._btn_move, "translate"), (self._btn_rot, "rotate")):
            b.setCheckable(True)
            b.clicked.connect(lambda _c=False, m=mode: self._set_tool(m))
            bar.addWidget(b)
        self._btn_move.setChecked(True)
        bar.addStretch(1)
        self._btn_add_fx = _btn("＋ Projecteur", "Ajouter un projecteur de la bibliothèque d'ARKLIGHT")
        self._btn_add_fx.clicked.connect(lambda: self._add_menu("fixture", self._btn_add_fx))
        self._btn_add_char = _btn("＋ Personnage", "Ajouter un personnage du plan ou un figurant")
        self._btn_add_char.clicked.connect(lambda: self._add_menu("person", self._btn_add_char))
        self._btn_add_obj = _btn("＋ Décor", "Ajouter un meuble, un élément de décor, un véhicule…")
        self._btn_add_obj.clicked.connect(lambda: self._add_menu("object", self._btn_add_obj))
        self._btn_add_grip = _btn("＋ Grip", "Ajouter un cadre, un drapeau, un réflecteur…")
        self._btn_add_grip.clicked.connect(lambda: self._add_menu("grip", self._btn_add_grip))
        self._btn_add_cam = _btn("＋ Caméra", "Ajouter une caméra sur pied ou un travelling")
        self._btn_add_cam.clicked.connect(lambda: self._add_menu("camera", self._btn_add_cam))
        for b in (self._btn_add_fx, self._btn_add_char, self._btn_add_obj, self._btn_add_grip, self._btn_add_cam):
            b.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            bar.addWidget(b)
        return host

    def _build_timeline(self) -> QWidget:
        host = QWidget()
        cl = QVBoxLayout(host)
        cl.setContentsMargins(8, 6, 8, 6)
        cl.setSpacing(6)
        # Frise de mise en scène (29/10/2026) : les keyframes de chaque élément
        from ui.timeline_bar import TimelineBar
        self.timeline = TimelineBar()
        self.timeline.seek.connect(lambda t: self.view.send("time", t=t))
        self.timeline.play_toggled.connect(lambda on: self.view.send("play" if on else "pause"))
        self.timeline.mark_requested.connect(
            lambda oid, t, act: self.view.send("mark", id=oid, t=t, action=act))
        self.timeline.unmark_requested.connect(lambda oid, t: self.view.send("unmark", id=oid, t=t))
        self.timeline.key_moved.connect(lambda oid, a, b: self.view.send("key.move", id=oid, **{"from": a, "to": b}))
        self.timeline.element_picked.connect(lambda oid: self.view.send("select", id=oid or None))
        self.timeline.duration_changed.connect(self._duration_changed)
        cl.addWidget(self.timeline, 1)
        # État de la vidéo exportée (rendue depuis la caméra du plan, envoyée à Seedance si la
        # case de RENDU & AUDIO du Studio IA est cochée) et mise en scène par l'IA.
        prow = QHBoxLayout()
        prow.setSpacing(6)
        self._previs_lbl = _small("")
        prow.addWidget(self._previs_lbl, 1)
        # Claude chorégraphe (30/10/2026) : la mise en scène décrite en mots -> keyframes
        self._btn_choreo = _btn("✦  Mise en scène par l'IA",
                                "Décrivez l'action du plan : l'IA pose les keyframes des personnages "
                                "sur la frise, que vous ajustez ensuite", CP["accent2"])
        self._btn_choreo.clicked.connect(self._open_choreo)
        prow.addWidget(self._btn_choreo)
        cl.addLayout(prow)
        self._previs_job = None
        self.setFocusPolicy(Qt.FocusPolicy.ClickFocus)    # Espace et Suppr : voir keyPressEvent
        self._status = _small("")
        cl.addWidget(self._status)
        return host

    # ---------------------------------------------------------------- prévisualisation
    def _previs_state(self) -> None:
        """« Voir la vidéo exportée » et ligne d'état d'après l'export du plan (à refaire si la scène a changé)."""
        sid = self._current_id()
        path = scene3d.previs_for(sid) if sid else ""
        self._btn_previs_open.setEnabled(bool(path))
        if self._previs_job is not None:
            return
        if not path:
            self._previs_lbl.setText(translate("Aucune vidéo exportée pour ce plan."))
            return
        import datetime
        when = datetime.datetime.fromtimestamp(os.path.getmtime(path)).strftime("%d/%m %H:%M")
        stale = scene3d.exists(sid) and os.path.getmtime(scene3d.path(sid)) > os.path.getmtime(path) + 1
        self._previs_lbl.setText(translate("Vidéo exportée le {when}").format(when=when)
                                 + ("  ·  " + translate("la scène a changé depuis : à refaire") if stale else ""))

    def _render_previs(self) -> None:
        if not self._shot or self._scene is None or self._previs_job is not None:
            return
        self.view.send("flush")          # dernières modifications enregistrées avant le rendu
        QTimer.singleShot(500, self._start_previs)

    def _start_previs(self) -> None:
        from ui.previs_render import PrevisRenderer
        sid = self._current_id()
        scene = dict(self._scene or {})
        url = share_image((scene.get("pandora") or {}).get("underlay_path", ""))
        under = scene3d.underlay_for_view(scene, url)
        if under:
            scene["plot"] = {**(scene.get("plot") or {}), "underlay": under}
        job = PrevisRenderer(scene, scene3d.previs_path(sid), self)
        job.progress.connect(lambda p, m: self._previs_lbl.setText(f"{translate(m)} ({p} %)"))
        job.done.connect(lambda _p: self._previs_end(sid, ""))
        job.failed.connect(lambda m: self._previs_end(sid, m))
        self._previs_job = job
        self._btn_previs.setEnabled(False)
        job.start()

    def _previs_end(self, sid: str, error: str) -> None:
        self._previs_job = None
        self._btn_previs.setEnabled(True)
        if error:
            self._previs_lbl.setText(translate("Export impossible : {err}").format(err=error[:160]))
            self._btn_previs_open.setEnabled(bool(scene3d.previs_for(self._current_id())))
            return
        if sid == self._current_id():
            self._previs_state()

    def _open_choreo(self) -> None:
        if not self._shot or self._scene is None:
            return
        from ui.choreo_dialog import ChoreoDialog
        dlg = ChoreoDialog(self._scene, self._shot, self)
        dlg.apply_tracks.connect(lambda tracks: self.view.send("tracks.set", tracks=tracks))
        dlg.remember.connect(self._remember_choreo)
        dlg.show()

    def _remember_choreo(self, data: dict) -> None:
        """Dernière demande au chorégraphe et son résumé, gardés avec la scène du plan."""
        if self._scene is None:
            return
        self._scene.setdefault("pandora", {})["choreo"] = data
        scene3d.save(self._current_id(), self._scene)

    def _open_previs(self) -> None:
        path = scene3d.previs_for(self._current_id())
        if path:
            from PyQt6.QtCore import QUrl
            from PyQt6.QtGui import QDesktopServices
            QDesktopServices.openUrl(QUrl.fromLocalFile(path))

    def _build_selection(self) -> QWidget:
        """Réglages de PANDORA (personnage, caméra, décor), posés sur la colonne de l'inspecteur
        d'ARKLIGHT ; masqués quand un projecteur est sélectionné : c'est alors lui qu'on voit."""
        panel = QFrame()
        panel.setObjectName("Scene3DInspector")
        panel.setFixedWidth(RIGHT_W)
        panel.setStyleSheet("QFrame#Scene3DInspector{background:" + CP["bg1"] + ";"
                            f"border-left:1px solid {CP['border']};}}")
        outer = QVBoxLayout(panel)
        outer.setContentsMargins(0, 0, 0, 0)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        body = QWidget()
        lay = QVBoxLayout(body)
        lay.setContentsMargins(12, 10, 12, 12)
        lay.setSpacing(6)
        lay.addWidget(_title("SÉLECTION"))
        self._inspector = _Inspector(self)
        lay.addWidget(self._inspector)
        lay.addStretch(1)
        scroll.setWidget(body)
        outer.addWidget(scroll)
        return panel

    def _build_prompt(self) -> QWidget:
        """Bas du panneau de droite : le texte qui sera écrit, et le bouton qui l'inscrit."""
        panel = QFrame()
        panel.setObjectName("Scene3DPrompt")
        panel.setFixedSize(RIGHT_W, PROMPT_H)
        panel.setStyleSheet("QFrame#Scene3DPrompt{background:" + CP["bg1"] + ";"
                            f"border-left:1px solid {CP['border']};border-top:1px solid {CP['border']};}}")
        lay = QVBoxLayout(panel)
        lay.setContentsMargins(12, 6, 12, 8)
        lay.setSpacing(5)
        lay.addWidget(_title("TEXTE POUR LE PROMPT"))
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._preview = QLabel("")
        self._preview.setWordWrap(True)
        self._preview.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        self._preview.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self._preview.setStyleSheet(f"color:{CP['text_secondary']};font-size:10px;background:transparent;"
                                    "border:none;")
        scroll.setWidget(self._preview)
        lay.addWidget(scroll, 1)
        self._write_state = _small("")
        lay.addWidget(self._write_state)
        self._btn_write = _btn("Inscrire dans le storyboard",
                               "Écrit ce texte dans le prompt de CE plan (mise en scène, caméra, lumière). "
                               "Pour tous les plans : menu Action.", CP["accent"])
        self._btn_write.clicked.connect(self._write_prompt)
        lay.addWidget(self._btn_write)
        return panel

    # ---------------------------------------------------------------- plans
    def refresh(self):
        cur = self._current_id()
        try:
            versions = sb_api.list_versions()
            vid = versions[0]["id"] if versions else sb_api.DEFAULT_VERSION_ID
            self._all_shots = sb_api.list_shots(vid)
        except Exception:
            self._all_shots = []
        prev = self._seq.currentData()
        values = []
        for s in self._all_shots:
            v = sequence_label(s)
            if v not in values:
                values.append(v)
        self._seq.blockSignals(True)
        self._seq.clear()
        self._seq.addItem(translate("Toutes les séquences"), "")
        for v in values:
            self._seq.addItem(v, v)
        self._seq.setCurrentIndex(max(0, self._seq.findData(prev)))
        self._seq.blockSignals(False)
        self._rebuild_list(cur)

    def _current_id(self) -> str:
        return (self._shot or {}).get("id", "")

    def _rebuild_list(self, current_id: str = ""):
        seq = self._seq.currentData() or ""
        self._shots = [s for s in self._all_shots if not seq or sequence_label(s) == seq]
        self._list.blockSignals(True)
        self._list.clear()
        for s in self._shots:
            item = QListWidgetItem()
            item.setSizeHint(QSize(240, 66))
            self._list.addItem(item)
            self._list.setItemWidget(item, LightingShotCard(s))
        self._list.blockSignals(False)
        self._count.setText(f"{len(self._shots)} {translate('plan(s)')}")
        if self._shots:
            row = next((i for i, s in enumerate(self._shots) if s.get("id") == current_id), 0)
            self._list.setCurrentRow(row)
            if self._list.currentRow() == row and self._current_id() != self._shots[row].get("id"):
                self._on_shot_changed(row)
        else:
            self._shot = None
            self._scene = None

    def _on_shot_changed(self, row: int):
        if row < 0 or row >= len(self._shots):
            return
        shot = self._shots[row]
        if self._scene is not None and shot.get("id") == self._current_id():
            # Simple rafraîchissement de l'onglet, même plan : on ne recharge RIEN dans la vue
            # (recharger remettait la tête de lecture à zéro et changeait le point de vue).
            self._shot = shot
            d = scene3d._duration(shot)
            if d != (self._scene.get("pandora") or {}).get("duration"):
                self._scene.setdefault("pandora", {})["duration"] = d
                self.view.send("duration", d=d)
            if scene3d.apply_camera_movement(shot, self._scene):   # mouvement changé au storyboard
                scene3d.save(shot.get("id", ""), self._scene)
                self._send_scene()
            self._show_duration()
            self._previs_state()
            self._update_preview()
            return
        self._shot = shot
        self._scene = scene3d.ensure(self._shot)
        # la frise dure ce que dure le plan au storyboard
        self._scene.setdefault("pandora", {})["duration"] = scene3d._duration(self._shot)
        self._show_duration()
        self._send_scene()
        self._previs_state()
        self._inspector.show_selection({})
        self._sel_panel.show()
        self._fill_elements()
        self._update_preview()

    def _show_duration(self) -> None:
        """Durée du plan dans la frise, bornée par le moteur visé (30 s en Seedance 2.5)."""
        d = scene3d._duration(self._shot)
        try:
            from core import seedance_family as _sf
            from core.target_engine import get_target_engine, shot_duration_max
            key = get_target_engine()
            top, name = shot_duration_max(key), (_sf.label(key) if _sf.is_seedance(key) else key)
        except Exception:
            top, name = 15, ""
        self.timeline.set_duration(d, top, name)

    def _duration_changed(self, d: float) -> None:
        """Nouvelle durée choisie dans la frise : c'est la durée du plan au storyboard
        (génération comprise) ; la scène et la prévisualisation la suivent."""
        shot = self._shot
        if not shot or self._scene is None:
            return
        shot["duration"] = round(float(d), 1)
        self._scene.setdefault("pandora", {})["duration"] = shot["duration"]
        if scene3d.apply_camera_movement(shot, self._scene):      # le mouvement du storyboard s'étire
            self._send_scene()
        self.view.send("duration", d=shot["duration"])
        try:
            sb_api.save_shot({k: v for k, v in shot.items() if not k.startswith("_")})
        except Exception:
            pass
        sid = self._current_id()
        if sid:
            scene3d.save(sid, self._scene)
        self._previs_state()

    def _send_scene(self) -> None:
        scene = dict(self._scene or {})
        url = share_image((scene.get("pandora") or {}).get("underlay_path", ""))
        under = scene3d.underlay_for_view(scene, url)
        if under:
            plot = dict(scene.get("plot") or {})
            plot["underlay"] = under
            scene["plot"] = plot
        self.view.set_scene(scene)

    # ---------------------------------------------------------------- vue
    def _on_ready(self, info: dict) -> None:
        self._catalog = info.get("catalog") or {}
        if not info.get("gl", True):
            self._status.setText(translate("WebGL indisponible : la vue 3D ne peut pas dessiner sur ce poste."))

    def _on_page_event(self, ev: dict) -> None:
        kind = ev.get("kind")
        if kind == "time":
            self.timeline.set_time(ev.get("t", 0), bool(ev.get("playing")))
            return
        if kind == "context":
            QTimer.singleShot(0, lambda: self._context_menu(ev))
            return
        if kind == "actions":
            self.timeline.set_actions(ev)
            return
        if kind == "track":
            self.timeline.set_marks(ev.get("id", ""), ev.get("marks") or [])
            return
        if kind == "loaded":
            self.timeline.set_duration(ev.get("duration") or scene3d._duration(self._shot))
        if kind == "look":
            # entrée dans la vue caméra (bouton, scène rouverte en vue caméra) ou
            # sortie (Échap, autre point de vue) : le cadre néon suit
            if ev.get("id"):
                self._mark_view("camera")
            elif self._view_btns["camera"].isChecked():
                self._mark_view(None)
        elif kind == "error":
            self._status.setText(translate("Vue 3D") + " : " + str(ev.get("message", ""))[:200])
        elif kind == "loaded":
            self._status.setText("")
            # scène semée par PANDORA : la vue renvoie la version complétée -> enregistrée
            if self._scene is not None and not scene3d.exists(self._current_id()):
                self.view.send("flush")

    def _on_scene_edited(self, scene: dict) -> None:
        sid = self._current_id()
        if not sid or (scene.get("pandora") or {}).get("shot_id", sid) != sid:
            return
        # champs tenus par PANDORA seul (la vue ne les connaît pas) : jamais perdus
        old_p = (self._scene or {}).get("pandora") or {}
        new_p = scene.setdefault("pandora", {})
        for k in ("choreo", "inscribed"):
            if k in old_p:
                new_p[k] = old_p[k]
        self._scene = scene
        scene3d.save(sid, scene)
        self._fill_elements()
        self._update_preview()
        self._previs_state()

    def _on_selection(self, sel: dict) -> None:
        self._inspector.show_selection(sel)
        # Un projecteur : l'inspecteur d'ARKLIGHT, sous ce panneau, apparaît à la même place
        self._sel_panel.setVisible(sel.get("kind") != "fixture")
        data = sel.get("data") or {}
        # Chaque élément du plan a ses propres keyframes ; seuls les personnages jouent des actions
        if sel.get("kind") == "object":
            person = str(data.get("type", "")).startswith("person")
            self.timeline.set_target(sel.get("id", ""), data.get("name", ""), sel.get("marks") or [], person)
        else:
            self.timeline.set_target("", "", [])

    def _fill_elements(self) -> None:
        """Liste des éléments de la frise : personnages, caméras, puis le reste."""
        objs = (self._scene or {}).get("objects") or []
        def rank(o):
            t = str(o.get("type", ""))
            return 0 if t.startswith("person") else 1 if t.startswith("camera") else 2
        self.timeline.set_elements([(o.get("id", ""), o.get("name") or o.get("type", ""))
                                    for o in sorted(objs, key=rank)])

    def _pick_view(self, key: str) -> None:
        # Qt a déjà basculé la case au moment du clic : « Caméra » cochée = on y entre,
        # décochée (re-clic) = retour à la vue libre.
        if key == "camera":
            cam = self.shot_camera_id()
            on = self._view_btns["camera"].isChecked() and bool(cam)
            self.view.send("look", id=cam if on else None)
            self._mark_view("camera" if on else None)
            return
        self.view.send("view", name=key)
        self._mark_view(key)

    def _mark_view(self, key: str | None) -> None:
        """Coche le point de vue actif (un seul cadre néon), ou aucun (vue libre)."""
        for k, b in self._view_btns.items():
            b.setChecked(k == key)

    def _set_tool(self, mode: str) -> None:
        self._btn_move.setChecked(mode == "translate")
        self._btn_rot.setChecked(mode == "rotate")
        self.view.send("tool", mode=mode)

    # ---------------------------------------------------------------- ajout
    def _add_menu(self, kind: str, anchor: QPushButton) -> None:
        menu = QMenu(self)
        self._fill_add(menu, kind)
        menu.exec(anchor.mapToGlobal(anchor.rect().bottomLeft()))

    def _add_item(self, at, **kw) -> None:
        """Ajoute un élément ; `at` : là où l'on a cliqué droit (x, z au sol)."""
        if at:
            kw["at"] = at
        self.view.send("add", **kw)

    def _context_menu(self, ev: dict) -> None:
        """Clic droit dans la vue 3D : tout ce qu'on peut faire ici, sans remonter à la barre."""
        menu = QMenu(self)
        at = ev.get("at")
        oid, fid = ev.get("objectId"), ev.get("id")
        if oid:
            camera = str(next((o.get("type", "") for o in (self._scene or {}).get("objects") or []
                               if o.get("id") == oid), "")).startswith("camera")
            act = menu.addAction(translate("＋ Keyframe"))
            act.triggered.connect(lambda: self.view.send("mark", id=oid))
            act = menu.addAction(translate("Supprimer la keyframe"))
            act.triggered.connect(lambda: self.view.send("unmark", id=oid))
            if camera:
                act = menu.addAction(translate("Cadrer le personnage"))
                act.triggered.connect(lambda: self.view.send("frame.person", id=oid))
                act = menu.addAction(translate("Voir par cette caméra"))
                act.triggered.connect(lambda: self.view.send("look", id=oid))
            act = menu.addAction(translate("Supprimer"))
            act.triggered.connect(lambda: self.view.send("remove", id=oid))
            menu.addSeparator()
        elif fid:
            act = menu.addAction(translate("Cadrer le personnage"))
            act.triggered.connect(lambda: self.view.send("aim"))
            act = menu.addAction(translate("Supprimer"))
            act.triggered.connect(lambda: self.view.send("remove", id=fid))
            menu.addSeparator()
        for kind, label in (("fixture", "＋ Projecteur"), ("person", "＋ Personnage"), ("object", "＋ Décor"),
                            ("grip", "＋ Grip"), ("camera", "＋ Caméra")):
            self._fill_add(menu.addMenu(translate(label)), kind, at)
        menu.exec(QCursor.pos())

    def keyPressEvent(self, e):   # noqa: N802
        # Quand le clavier est ici plutôt que dans la vue web (qui a les mêmes raccourcis)
        if e.key() == Qt.Key.Key_Space and not e.isAutoRepeat():
            self.view.send("play.toggle")
        elif e.key() == Qt.Key.Key_Delete and not e.isAutoRepeat():
            self.view.send("key.delete")
        else:
            super().keyPressEvent(e)

    def _fill_add(self, menu: QMenu, kind: str, at=None) -> None:
        cat = self._catalog
        if kind == "fixture":
            groups = {}
            for f in cat.get("fixtures") or []:
                groups.setdefault(f.get("category") or "", []).append(f)
            for c in cat.get("fixture_categories") or []:
                items = groups.get(c.get("id"), [])
                if not items:
                    continue
                sub = menu.addMenu(translate(c.get("label", "")))
                for f in sorted(items, key=lambda x: (x.get("brand", ""), x.get("name", ""))):
                    act = sub.addAction(f.get("name", ""))
                    act.triggered.connect(lambda _c=False, t=f["id"]: self._add_item(at, kind="fixture", type=t))
        elif kind == "person":
            for name in self.character_names():
                typ = scene3d._character_build(name)[0]
                act = menu.addAction(name)
                act.triggered.connect(lambda _c=False, n=name, t=typ: self._add_item(at, kind="object", type=t, name=n, pandora={"kind": "character", "name": n}))
            if menu.actions():
                menu.addSeparator()
            for t, lab in (("person-man", "Figurant (homme)"), ("person-woman", "Figurante (femme)"),
                           ("person-child", "Enfant")):
                act = menu.addAction(translate(lab))
                act.triggered.connect(lambda _c=False, tt=t: self._add_item(at, kind="object", type=tt, pandora={"kind": "extra"}))
        elif kind == "camera":
            for o in cat.get("objects") or []:
                if o.get("model") in ("camera", "dolly"):
                    act = menu.addAction(o.get("name", ""))
                    act.triggered.connect(lambda _c=False, t=o["id"]: self._add_item(at, kind="object", type=t))
        elif kind == "object":
            groups = {}
            for o in cat.get("objects") or []:
                if o.get("category") != "people":
                    groups.setdefault(o.get("category") or "", []).append(o)
            for c in cat.get("object_categories") or []:
                items = groups.get(c.get("id"), [])
                if not items:
                    continue
                sub = menu.addMenu(translate(c.get("label", "")))
                for o in items:
                    act = sub.addAction(o.get("name", ""))
                    act.triggered.connect(lambda _c=False, t=o["id"]: self._add_item(at, kind="object", type=t))
        else:
            groups = {}
            for g in cat.get("grip") or []:
                groups.setdefault(g.get("family") or "", []).append(g)
            fams = cat.get("grip_families") or []
            for fam in fams:
                items = groups.get(fam.get("id"), [])
                if not items:
                    continue
                sub = menu.addMenu(translate(fam.get("label", fam.get("name", ""))))
                for g in items:
                    act = sub.addAction(g.get("name", ""))
                    act.triggered.connect(lambda _c=False, t=g["id"]: self._add_item(at, kind="object", type=t))
        if not menu.actions():
            menu.addAction(translate("La vue 3D se prépare…")).setEnabled(False)

    # ---------------------------------------------------------------- données
    def character_names(self) -> list[str]:
        names = list((self._shot or {}).get("character_names") or [])
        try:
            import core.casting as casting
            for c in casting.list_characters():
                n = str(c.get("name", "")).strip()
                if n and n not in names:
                    names.append(n)
        except Exception:
            pass
        return [n for n in names if n]

    def shot_camera_id(self) -> str:
        return ((self._scene or {}).get("pandora") or {}).get("shot_camera", "")

    def set_shot_camera(self, oid: str) -> None:
        if self._scene is None:
            return
        self._scene.setdefault("pandora", {})["shot_camera"] = oid
        scene3d.save(self._current_id(), self._scene)
        self._send_scene()
        self._update_preview()

    def analysis_for(self, fid: str) -> dict:
        ana = ((self._scene or {}).get("pandora") or {}).get("analysis") or {}
        return next((f for f in ana.get("fixtures") or [] if f.get("id") == fid), {})

    # ---------------------------------------------------------------- prompt
    def _update_preview(self) -> None:
        """Texte que « Inscrire dans le storyboard » écrira, et s'il l'est déjà."""
        t = scene_text.texts(self._scene) if self._scene else {}
        parts = [p for p in (t.get("staging"), t.get("lighting")) if p]
        self._preview.setText("\n\n".join(parts) if parts else translate("Rien à écrire pour l'instant."))
        pending = bool(self._shot and self._scene and scene_text.pending(self._shot, self._scene))
        self._btn_write.setEnabled(pending)
        self._write_state.setText(translate("Modifications à inscrire dans le storyboard") if pending
                                  else translate("Le storyboard est à jour") if parts else "")

    def _save_written(self, shot: dict, scene: dict) -> None:
        sb_api.save_shot({k: v for k, v in shot.items() if not k.startswith("_")})
        scene3d.save(shot.get("id", ""), scene)

    def _write_prompt(self) -> None:
        """Inscrit CE plan : sections [🎭 MISE EN SCÈNE] et [💡 PLAN DE FEU] + champs techniques."""
        if not self._shot or not self._scene:
            return
        try:
            if scene_text.write_to_shot(self._shot, self._scene):
                self._save_written(self._shot, self._scene)
        except Exception as e:
            self._status.setText(translate("Inscription impossible : {err}").format(err=str(e)[:160]))
        self._update_preview()

    def _write_all(self) -> None:
        self.view.send("flush")          # dernières modifications enregistrées d'abord
        QTimer.singleShot(500, self._write_all_now)

    def _write_all_now(self) -> None:
        """Inscrit tous les plans qui ont une scène 3D, sans ouvrir aucun d'eux."""
        cur = self._current_id()
        done = errors = 0
        for shot in self._all_shots:
            sid = shot.get("id", "")
            scene = self._scene if sid == cur else scene3d.load(sid)
            if not scene:
                continue
            scene3d.apply_camera_movement(shot, scene)
            try:
                if scene_text.write_to_shot(shot, scene):
                    self._save_written(shot, scene)
                    done += 1
            except Exception:
                errors += 1
        msg = translate("{n} plan(s) inscrit(s) dans le storyboard.").format(n=done)
        if errors:
            msg += " " + translate("{n} plan(s) en échec.").format(n=errors)
        self._status.setText(msg)
        self._update_preview()
