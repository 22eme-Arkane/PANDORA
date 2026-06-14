"""
ui/page_staging.py — Mise en scène & Plan de feu (vue de dessus, par plan).

PageStaging (mode 'staging') : place CAMÉRA, personnages et éléments sur un plan
vu de dessus généré depuis le décor. L'axe caméra est réécrit dans le plan du
storyboard. PageLighting (mode 'lighting') : place les LUMIÈRES (type de
projecteur + direction) sur le MÊME plan — record partagé par plan (core/staging).
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QComboBox,
    QListWidget, QListWidgetItem, QInputDialog, QMenu,
)
from PyQt6.QtCore import Qt
from ui.styles import CP
from ui.widgets import HelpBlock
from ui.staging_canvas import StagingCanvas
from core.i18n import translate
import core.storyboard as sb_api
import core.staging as staging


def _btn(label: str) -> QPushButton:
    b = QPushButton(label)
    b.setMinimumHeight(34)
    b.setCursor(Qt.CursorShape.PointingHandCursor)
    b.setStyleSheet(
        f"QPushButton{{background:{CP['bg3']};color:{CP['text_primary']};"
        f"border:1px solid {CP['border']};border-radius:7px;font-size:11px;"
        f"font-weight:600;padding:0 12px;}}"
        f"QPushButton:hover{{background:{CP['bg2']};border-color:{CP['accent_dim']};}}"
    )
    return b


class PageStaging(QWidget):

    MODE = "staging"

    def __init__(self):
        super().__init__()
        self._mode = self.MODE
        self._shots: list[dict] = []
        self._shot: dict | None = None
        self._worker = None
        self.setStyleSheet(f"background:{CP['bg0']};")

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ── Bandeau ────────────────────────────────────────────────────────────
        band = QWidget()
        band.setFixedHeight(60)
        band.setStyleSheet(f"background:{CP['bg1']};border-bottom:1px solid {CP['border']};")
        bl = QHBoxLayout(band)
        bl.setContentsMargins(20, 0, 20, 0)
        title = QLabel(("🎬  " if self._mode == "staging" else "💡  ")
                       + translate("Mise en scène" if self._mode == "staging" else "Plan de feu"))
        title.setStyleSheet(
            f"color:{CP['text_primary']};font-size:16px;font-weight:700;background:transparent;")
        bl.addWidget(title)
        bl.addStretch()
        root.addWidget(band)

        hb = HelpBlock(
            "Mise en scène — plan vu de dessus" if self._mode == "staging"
            else "Plan de feu — éclairage vu de dessus",
            self._help_lines(), CP)
        _hw = QWidget(); _hl = QVBoxLayout(_hw)
        _hl.setContentsMargins(20, 8, 20, 4); _hl.addWidget(hb)
        root.addWidget(_hw)

        # ── Corps : liste des plans (gauche) + canevas (droite) ─────────────────
        body = QHBoxLayout()
        body.setContentsMargins(16, 8, 16, 16)
        body.setSpacing(12)

        left = QVBoxLayout()
        left.setSpacing(6)
        _lst_lbl = QLabel(translate("Plans du storyboard"))
        _lst_lbl.setStyleSheet(f"color:{CP['text_dim']};font-size:10px;font-weight:700;"
                               f"letter-spacing:1px;background:transparent;")
        left.addWidget(_lst_lbl)
        self._list = QListWidget()
        self._list.setFixedWidth(220)
        self._list.setStyleSheet(
            f"QListWidget{{background:{CP['bg2']};border:1px solid {CP['border']};"
            f"border-radius:8px;color:{CP['text_primary']};font-size:12px;padding:4px;}}"
            f"QListWidget::item{{padding:6px 8px;border-radius:5px;}}"
            f"QListWidget::item:selected{{background:{CP['accent_dim']};color:#07080f;}}"
        )
        self._list.currentRowChanged.connect(self._on_shot_changed)
        left.addWidget(self._list, 1)
        body.addLayout(left)

        right = QVBoxLayout()
        right.setSpacing(8)
        self._canvas = StagingCanvas(mode=self._mode)
        self._canvas.changed.connect(self._autosave)
        right.addLayout(self._build_toolbar())
        right.addWidget(self._canvas, 1)
        body.addLayout(right, 1)
        root.addLayout(body, 1)

    # ── Contenu spécifique au mode ──────────────────────────────────────────────

    def _help_lines(self):
        if self._mode == "staging":
            return [
                "▸ Sélectionnez un plan, générez le plan vu de dessus du décor, puis placez caméra, acteurs et éléments.",
                "▸ Glissez les jetons ; pivotez la caméra avec ⟲ ⟳. L'axe caméra est réécrit dans le storyboard.",
                "▸ Tout est enregistré automatiquement et réutilisé par la synchronisation des prompts.",
            ]
        return [
            "▸ Reprend le plan de la Mise en scène : placez les projecteurs et choisissez leur type.",
            "▸ Glissez chaque lumière, orientez-la avec ⟲ ⟳ pour définir la direction du faisceau.",
            "▸ La synchronisation des prompts tient compte de l'éclairage défini ici.",
        ]

    def _build_toolbar(self) -> QHBoxLayout:
        tb = QHBoxLayout()
        tb.setSpacing(8)
        self._btn_gen = _btn("✦  " + translate("Générer le plan"))
        self._btn_gen.clicked.connect(self._on_generate_plan)
        tb.addWidget(self._btn_gen)
        if self._mode == "staging":
            b_actor = _btn("＋ " + translate("Acteur")); b_actor.clicked.connect(self._add_actor)
            b_prop  = _btn("＋ " + translate("Élément")); b_prop.clicked.connect(self._add_prop)
            tb.addWidget(b_actor); tb.addWidget(b_prop)
        else:
            b_light = _btn("＋ " + translate("Lumière")); b_light.clicked.connect(self._add_light)
            tb.addWidget(b_light)
        b_rl = _btn("⟲"); b_rl.setFixedWidth(40); b_rl.clicked.connect(lambda: self._canvas.rotate_selected(-15))
        b_rr = _btn("⟳"); b_rr.setFixedWidth(40); b_rr.clicked.connect(lambda: self._canvas.rotate_selected(15))
        b_del = _btn("🗑"); b_del.setFixedWidth(40); b_del.clicked.connect(self._canvas.remove_selected)
        tb.addWidget(b_rl); tb.addWidget(b_rr); tb.addWidget(b_del)
        tb.addStretch()
        return tb

    # ── Données ─────────────────────────────────────────────────────────────────

    def showEvent(self, e):
        super().showEvent(e)
        self.refresh()

    def refresh(self):
        cur = self._shot.get("id") if self._shot else None
        try:
            versions = sb_api.list_versions()
            vid = versions[0]["id"] if versions else sb_api.DEFAULT_VERSION_ID
            self._shots = sb_api.list_shots(vid)
        except Exception:
            self._shots = []
        self._list.blockSignals(True)
        self._list.clear()
        for s in self._shots:
            num = s.get("number", "?")
            self._list.addItem(QListWidgetItem(f"Plan {num} — {s.get('scene_title', '')[:24]}"))
        self._list.blockSignals(False)
        if self._shots:
            idx = next((i for i, s in enumerate(self._shots) if s.get("id") == cur), 0)
            self._list.setCurrentRow(idx)

    def _on_shot_changed(self, row: int):
        if row < 0 or row >= len(self._shots):
            self._shot = None
            return
        self._shot = self._shots[row]
        rec = staging.get(self._shot["id"])
        # Amorçage : acteurs depuis les personnages du plan (si vide)
        if self._mode == "staging" and not rec.get("actors"):
            names = self._shot.get("character_names", []) or []
            rec["actors"] = [{"name": n, "x": 0.3 + 0.15 * i, "y": 0.5}
                             for i, n in enumerate(names[:6])]
        self._canvas.load(rec)

    # ── Actions ─────────────────────────────────────────────────────────────────

    def _add_actor(self):
        names = (self._shot or {}).get("character_names", []) or []
        if names:
            menu = QMenu(self)
            for n in names:
                menu.addAction(n, lambda _=False, nm=n: self._canvas.add_actor(nm))
            menu.addAction(translate("Autre…"), self._add_actor_free)
            menu.exec(self.cursor().pos())
        else:
            self._add_actor_free()

    def _add_actor_free(self):
        name, ok = QInputDialog.getText(self, translate("Acteur"), translate("Nom :"))
        if ok and name.strip():
            self._canvas.add_actor(name.strip())

    def _add_prop(self):
        name, ok = QInputDialog.getText(self, translate("Élément"), translate("Nom :"))
        if ok and name.strip():
            self._canvas.add_prop(name.strip())

    def _add_light(self):
        items = [lbl for _, lbl in staging.PROJECTOR_TYPES]
        lbl, ok = QInputDialog.getItem(self, translate("Lumière"),
                                       translate("Type de projecteur :"), items, 0, False)
        if not ok:
            return
        ltype = next((k for k, l in staging.PROJECTOR_TYPES if l == lbl), "key")
        name, ok2 = QInputDialog.getText(self, translate("Lumière"), translate("Nom :"),
                                         text=lbl.split(" (")[0])
        if ok2 and name.strip():
            self._canvas.add_light(name.strip(), ltype)

    def _on_generate_plan(self):
        if not self._shot:
            return
        self._btn_gen.setEnabled(False)
        self._btn_gen.setText("…")
        from api.nano_banana import GenerateFloorPlanWorker
        prompt = self._decor_prompt(self._shot)
        self._worker = GenerateFloorPlanWorker(prompt, self._shot.get("decor_name", "plan"))
        self._worker.finished.connect(self._on_plan_done)
        self._worker.failed.connect(self._on_plan_fail)
        self._worker.start()

    def _on_plan_done(self, path: str):
        self._btn_gen.setEnabled(True)
        self._btn_gen.setText("✦  " + translate("Générer le plan"))
        if path and self._shot:
            rec = staging.get(self._shot["id"])
            rec["plan_image"] = path
            staging.save(self._shot["id"], rec)
            self._canvas.load(rec)
        elif not path:
            self._btn_gen.setText("Mode mock — plan non généré (clé fal.ai absente)")

    def _on_plan_fail(self, err: str):
        self._btn_gen.setEnabled(True)
        self._btn_gen.setText("✦  " + translate("Générer le plan"))

    def _autosave(self):
        if not self._shot:
            return
        rec = self._canvas.commit()
        staging.save(self._shot["id"], rec)
        # Mise en scène → axe caméra réécrit dans le storyboard
        if self._mode == "staging":
            cam = rec.get("camera") or {}
            axis = staging.axis_from_angle(cam.get("angle", 0))
            if self._shot.get("camera_axis") != axis:
                self._shot["camera_axis"] = axis
                try:
                    sb_api.save_shot({k: v for k, v in self._shot.items() if not k.startswith("_")})
                except Exception:
                    pass

    def _decor_prompt(self, shot: dict) -> str:
        did = shot.get("decor_id")
        if did:
            try:
                import core.decors as d
                dec = d.get_decor(did)
                if dec:
                    return dec.get("prompt") or dec.get("name", "")
            except Exception:
                pass
        return shot.get("decor_name", "") or shot.get("scene_title", "")


class PageLighting(PageStaging):
    """Plan de feu — même canevas, mode lumières, record partagé avec la Mise en
    scène (réutilise le plan vu de dessus généré)."""
    MODE = "lighting"
