"""Onglet « 7 vues » de la partie Décors — atelier de VRAIES rotations.

Première étape de la refonte Décors (décision Matthieu 2026-07-31) : le
workflow 7 vues, plus costaud que la gestion classique, obtient sa propre
page. On y choisit une pièce (ou un décor libre avec image), un MOTEUR de
rotation, et on régénère les six vues dérivées à partir de l'image
d'ensemble — les trois moteurs sont comparables :

- « Multi-angles (Qwen) »   : angles caméra NUMÉRIQUES, 6 vues, ~0,04 $/vue.
- « Orbite (Seedance) »     : vidéo orbitale 360° → frames aux quarts de
  tour ; 4 faces murales seulement, ~2,40 $ l'orbite (720p × 8 s).
- « Panorama 360° (Hunyuan)»: un panorama équirectangulaire puis 6
  reprojections locales gratuites (géométrie garantie par construction).

Les vues générées sont écrites sur les décors frères de la pièce
(room_group) — la page Décors, le storyboard et la Mise en scène les voient
immédiatement. Un décor libre devient une pièce à sa première génération.
"""

from __future__ import annotations

import os

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel, QPushButton,
    QComboBox, QSlider, QProgressBar, QScrollArea,
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPixmap

from ui.styles import CP
from core.i18n import translate
import core.decors as decors_api
from core.room_views import SIX_FACES
from ui.page_decors import _load_card_pixmap


# (clé, libellé court, ligne d'info affichée sous les contrôles)
ENGINES = [
    ("qwen", "Multi-angles (Qwen)",
     "4 vues par angles caméra numériques (Droite, Arrière, Gauche, Sol) · "
     "~0,04 $/vue · Avant = votre image d'ensemble, Plafond hors de portée"),
    ("orbit", "Orbite 360° (Seedance)",
     "1 vidéo orbitale 720p × 8 s (~2,40 $) → 4 faces murales · Sol/Plafond non couverts"),
    ("hunyuan", "Panorama 360° (Hunyuan World)",
     "1 panorama (~0,10 $) → 6 vues reprojetées en LOCAL, géométrie garantie"),
]

_CARD_W, _CARD_H = 208, 117


class PageDecorsMultiview(QWidget):
    """Atelier 7 vues — sélection d'une pièce, moteur, génération, écriture
    des vues sur les décors frères (room_group)."""

    def __init__(self):
        super().__init__()
        self.setStyleSheet(f"background:{CP['bg0']};")
        self._reps: list[dict] = []
        self._worker = None
        self._view_cards: dict[str, QLabel] = {}

        root = QVBoxLayout(self)
        root.setContentsMargins(32, 18, 32, 14)
        root.setSpacing(10)

        # ── Titre ────────────────────────────────────────────────────────────
        title = QLabel("⟳  " + translate("Atelier 7 vues"))
        title.setStyleSheet(
            f"color:{CP['text_primary']};font-size:16px;font-weight:800;"
            f"letter-spacing:1px;background:transparent;")
        root.addWidget(title)
        sub = QLabel(translate(
            "Vraies rotations de caméra autour d'un décor : les six vues sont "
            "recalculées depuis l'image d'ensemble, puis écrites sur les vues "
            "de la pièce (page Décors, storyboard, Mise en scène)."))
        sub.setWordWrap(True)
        sub.setStyleSheet(
            f"color:{CP['text_dim']};font-size:10px;background:transparent;")
        root.addWidget(sub)

        # ── Bandeau EXPÉRIMENTAL (demande Matthieu 2026-07-31) ───────────────
        # L'atelier donne de vrais résultats sur les quatre faces murales, mais
        # deux vues restent des approximations que le moteur ne sait pas
        # produire : l'ARRIÈRE (ce qui est derrière l'objectif n'existe pas dans
        # l'image source — le modèle retourne l'image) et le PLAFOND (il
        # faudrait −90° de site, le LoRA s'arrête à −30°). Le dire ici plutôt
        # que laisser l'utilisateur croire à une panne de son côté.
        warn = QLabel(translate(
            "⚗  EXPÉRIMENTAL — en cours de test. En multi-angles, seules les "
            "vues réellement tenues par le moteur sont demandées : Droite, "
            "Arrière, Gauche et Sol. « Avant » n'est pas régénéré (c'est votre "
            "image d'ensemble) et « Plafond » n'est pas demandé (le moteur ne "
            "lève pas la caméra assez haut). L'ARRIÈRE reste imparfait : ce qui "
            "se trouve derrière la caméra n'existe pas dans l'image de départ, "
            "le moteur l'invente. Vérifiez chaque vue avant de l'utiliser."))
        warn.setWordWrap(True)
        warn.setStyleSheet(
            f"color:{CP['orange']};font-size:10px;background:transparent;"
            f"border:1px solid {CP['orange']};border-radius:6px;padding:6px 8px;")
        root.addWidget(warn)

        # ── Contrôles ────────────────────────────────────────────────────────
        bar = QHBoxLayout()
        bar.setSpacing(10)

        lbl_d = QLabel(translate("Pièce / décor"))
        lbl_d.setStyleSheet(
            f"color:{CP['text_secondary']};font-size:10px;font-weight:700;"
            f"background:transparent;")
        bar.addWidget(lbl_d)
        self._decor_combo = QComboBox()
        self._decor_combo.setFixedHeight(30)
        self._decor_combo.setMinimumWidth(220)
        self._decor_combo.currentIndexChanged.connect(self._on_decor_changed)
        bar.addWidget(self._decor_combo, 1)

        lbl_e = QLabel(translate("Moteur"))
        lbl_e.setStyleSheet(
            f"color:{CP['text_secondary']};font-size:10px;font-weight:700;"
            f"background:transparent;")
        bar.addWidget(lbl_e)
        self._engine_combo = QComboBox()
        self._engine_combo.setFixedHeight(30)
        self._engine_combo.setMinimumWidth(230)
        for key, label, _info in ENGINES:
            self._engine_combo.addItem(translate(label), key)
        self._engine_combo.currentIndexChanged.connect(self._on_engine_changed)
        bar.addWidget(self._engine_combo)

        # Zoom — spécifique au moteur Multi-angles (0 = très large … 10 = serré).
        self._zoom_lbl = QLabel(translate("Zoom"))
        self._zoom_lbl.setStyleSheet(
            f"color:{CP['text_secondary']};font-size:10px;font-weight:700;"
            f"background:transparent;")
        bar.addWidget(self._zoom_lbl)
        self._zoom = QSlider(Qt.Orientation.Horizontal)
        self._zoom.setRange(0, 10)
        self._zoom.setValue(0)
        self._zoom.setFixedWidth(90)
        self._zoom.setToolTip(translate(
            "0 = très large (tout le mur) · 5 = moyen · 10 = serré"))
        bar.addWidget(self._zoom)
        self._zoom_val = QLabel("0")
        self._zoom_val.setFixedWidth(16)
        self._zoom_val.setStyleSheet(
            f"color:{CP['text_dim']};font-size:10px;background:transparent;")
        self._zoom.valueChanged.connect(lambda v: self._zoom_val.setText(str(v)))
        bar.addWidget(self._zoom_val)

        self._btn_gen = QPushButton("✦  " + translate("Générer les vues"))
        self._btn_gen.setFixedHeight(30)
        self._btn_gen.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_gen.setStyleSheet(
            f"QPushButton{{background:{CP['accent']};color:#07080f;border:none;"
            f"border-radius:6px;font-size:11px;font-weight:700;padding:0 16px;}}"
            f"QPushButton:hover{{background:#6eded6;}}"
            f"QPushButton:disabled{{background:{CP['bg3']};color:{CP['text_dim']};}}")
        self._btn_gen.clicked.connect(self._on_generate)
        bar.addWidget(self._btn_gen)
        root.addLayout(bar)

        self._engine_info = QLabel("")
        self._engine_info.setStyleSheet(
            f"color:{CP['text_dim']};font-size:9px;"
            f"font-family:'Consolas',monospace;background:transparent;")
        root.addWidget(self._engine_info)

        # ── Corps : image maître + grille des 6 vues ─────────────────────────
        body_scroll = QScrollArea()
        body_scroll.setWidgetResizable(True)
        body_scroll.setStyleSheet("QScrollArea{background:transparent;border:none;}")
        body_w = QWidget()
        body_w.setStyleSheet("background:transparent;")
        body = QHBoxLayout(body_w)
        body.setContentsMargins(0, 4, 0, 0)
        body.setSpacing(18)

        master_col = QVBoxLayout()
        master_col.setSpacing(6)
        cap_m = QLabel(translate("Plan d'ensemble (source)"))
        cap_m.setStyleSheet(
            f"color:{CP['text_secondary']};font-size:10px;font-weight:700;"
            f"letter-spacing:1px;background:transparent;")
        master_col.addWidget(cap_m)
        self._master = QLabel()
        self._master.setFixedSize(384, 216)
        self._master.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._master.setStyleSheet(
            f"background:{CP['bg3']};border:1px solid {CP['border']};"
            f"border-radius:10px;color:{CP['text_dim']};font-size:11px;")
        master_col.addWidget(self._master)
        self._master_name = QLabel("")
        self._master_name.setStyleSheet(
            f"color:{CP['text_primary']};font-size:11px;font-weight:700;"
            f"background:transparent;")
        master_col.addWidget(self._master_name)
        master_col.addStretch()
        body.addLayout(master_col)

        views_col = QVBoxLayout()
        views_col.setSpacing(6)
        cap_v = QLabel(translate("Les 6 vues dérivées"))
        cap_v.setStyleSheet(
            f"color:{CP['text_secondary']};font-size:10px;font-weight:700;"
            f"letter-spacing:1px;background:transparent;")
        views_col.addWidget(cap_v)
        self._grid = QGridLayout()
        self._grid.setHorizontalSpacing(12)
        self._grid.setVerticalSpacing(12)
        grid_row = QHBoxLayout()
        grid_row.addLayout(self._grid)
        grid_row.addStretch(1)   # cartes bornées, calées à gauche
        views_col.addLayout(grid_row)
        views_col.addStretch()
        body.addLayout(views_col, 1)

        body_scroll.setWidget(body_w)
        root.addWidget(body_scroll, 1)

        # ── Progression + statut ─────────────────────────────────────────────
        self._progress = QProgressBar()
        self._progress.setRange(0, 100)
        self._progress.setFixedHeight(4)
        self._progress.setVisible(False)
        self._progress.setStyleSheet(
            f"QProgressBar{{background:{CP['bg3']};border:none;border-radius:2px;}}"
            f"QProgressBar::chunk{{background:qlineargradient(x1:0,y1:0,x2:1,y2:0,"
            f"stop:0 {CP['accent_dim']},stop:1 {CP['accent']});border-radius:2px;}}")
        root.addWidget(self._progress)
        self._status = QLabel("")
        self._status.setWordWrap(True)
        self._status.setStyleSheet(
            f"color:{CP['text_dim']};font-size:10px;"
            f"font-family:'Consolas',monospace;background:transparent;")
        root.addWidget(self._status)

        self._on_engine_changed()

    # ── Données ──────────────────────────────────────────────────────────────

    def _representatives(self) -> list[dict]:
        """Un représentant par PIÈCE (la vue « Ensemble ») + les décors libres
        AVEC image (candidats à devenir une pièce)."""
        seen, out = set(), []
        for d in decors_api.list_decors():
            img = d.get("image_path", "")
            if not (img and os.path.isfile(img)):
                continue
            g = d.get("room_group", "") or ""
            if g:
                if g in seen:
                    continue
                rep = d if d.get("room_view") == "Ensemble" else next(
                    (s for s in decors_api.list_decors()
                     if s.get("room_group") == g
                     and s.get("room_view") == "Ensemble"
                     and s.get("image_path")
                     and os.path.isfile(s.get("image_path", ""))), d)
                seen.add(g)
                out.append(rep)
            else:
                out.append(d)
        return out

    def _current_rep(self) -> dict | None:
        i = self._decor_combo.currentIndex()
        return self._reps[i] if 0 <= i < len(self._reps) else None

    def _siblings(self, rep: dict) -> dict:
        """Vues sœurs existantes par LABEL (« Avant »…) → décor."""
        g = rep.get("room_group", "")
        if not g:
            return {}
        return {s.get("room_view", ""): s for s in decors_api.list_decors()
                if s.get("room_group") == g and s.get("id") != rep.get("id")}

    def refresh(self):
        busy = self._worker is not None and self._worker.isRunning()
        if busy:
            return   # ne pas reconstruire les cartes sous une génération
        current = ""
        rep = self._current_rep()
        if rep:
            current = rep.get("room_group") or rep.get("name", "")
        self._reps = self._representatives()
        self._decor_combo.blockSignals(True)
        self._decor_combo.clear()
        for d in self._reps:
            self._decor_combo.addItem(d.get("room_group") or d.get("name", "—"))
        if current:
            for i, d in enumerate(self._reps):
                if (d.get("room_group") or d.get("name", "")) == current:
                    self._decor_combo.setCurrentIndex(i)
                    break
        self._decor_combo.blockSignals(False)
        self._on_decor_changed()

    # ── Affichage ────────────────────────────────────────────────────────────

    def _on_decor_changed(self, *_a):
        rep = self._current_rep()
        while self._grid.count():
            it = self._grid.takeAt(0)
            w = it.widget()
            if w is not None:
                # setParent(None) AVANT deleteLater : `deleteLater` ne détruit
                # qu'au prochain tour de boucle d'événements, et une carte
                # seulement retirée du LAYOUT reste enfant de la page — elle
                # flotte alors en (0,0) par-dessus le plan d'ensemble (carte
                # « Plafond » fantôme, constatée au rendu 2026-07-31).
                w.setParent(None)
                w.deleteLater()
        self._view_cards.clear()
        if rep is None:
            self._master.setPixmap(QPixmap())
            self._master.setText(translate("Aucun décor avec une image.\n"
                                           "Génère d'abord un décor dans l'onglet Standard."))
            self._master_name.setText("")
            self._btn_gen.setEnabled(False)
            return
        self._btn_gen.setEnabled(True)
        img = rep.get("image_path", "")
        self._master.setText("")
        self._master.setPixmap(_load_card_pixmap(img, 384, 216))
        self._master.setCursor(Qt.CursorShape.PointingHandCursor)
        self._master.setToolTip(translate("Cliquer pour voir en grand"))
        self._master.mousePressEvent = lambda e: (
            self._open_preview("ensemble")
            if e.button() == Qt.MouseButton.LeftButton else None)
        self._master_name.setText(rep.get("room_group") or rep.get("name", ""))
        sibs = self._siblings(rep)
        for i, (label, code, _d) in enumerate(SIX_FACES):
            card = QWidget()
            card.setFixedSize(_CARD_W, _CARD_H + 22)
            cv = QVBoxLayout(card)
            cv.setContentsMargins(0, 0, 0, 0)
            cv.setSpacing(0)
            thumb = QLabel()
            thumb.setFixedSize(_CARD_W, _CARD_H)
            thumb.setAlignment(Qt.AlignmentFlag.AlignCenter)
            thumb.setStyleSheet(
                f"background:{CP['bg3']};border:1px solid {CP['border']};"
                f"border-radius:8px 8px 0 0;color:{CP['text_dim']};font-size:10px;")
            sib = sibs.get(label)
            simg = (sib or {}).get("thumbnail_path", "")
            if not (simg and os.path.isfile(simg)):
                simg = (sib or {}).get("image_path", "")
            if simg and os.path.isfile(simg):
                thumb.setPixmap(_load_card_pixmap(simg, _CARD_W, _CARD_H))
                # Clic → aperçu en grand, avec navigation entre toutes les vues.
                thumb.setCursor(Qt.CursorShape.PointingHandCursor)
                thumb.setToolTip(translate("Cliquer pour voir en grand"))
                thumb.mousePressEvent = (
                    lambda e, _c=code: self._open_preview(_c)
                    if e.button() == Qt.MouseButton.LeftButton else None)
            else:
                thumb.setText("⟳\n" + translate("à générer"))
            name = QLabel(translate(label))
            name.setFixedSize(_CARD_W, 22)
            name.setAlignment(Qt.AlignmentFlag.AlignCenter)
            name.setStyleSheet(
                f"color:{CP['text_secondary']};font-size:9px;font-weight:700;"
                f"background:{CP['bg2']};border:1px solid {CP['border']};"
                f"border-top:none;border-radius:0 0 8px 8px;")
            cv.addWidget(thumb)
            cv.addWidget(name)
            self._grid.addWidget(card, i // 3, i % 3)
            self._view_cards[code] = thumb

    def _preview_items(self) -> list[tuple[str, str]]:
        """Le plan d'ensemble puis les vues DISPONIBLES, dans l'ordre des faces.

        On donne les images PLEINE RÉSOLUTION (pas les aperçus légers) : c'est
        tout l'intérêt d'ouvrir en grand.
        """
        rep = self._current_rep()
        if rep is None:
            return []
        items: list[tuple[str, str]] = []
        master = rep.get("image_path", "")
        if master and os.path.isfile(master):
            items.append((translate("Plan d'ensemble"), master))
        sibs = self._siblings(rep)
        for label, _code, _d in SIX_FACES:
            sib = sibs.get(label)
            path = (sib or {}).get("image_path", "")
            if path and os.path.isfile(path):
                items.append((translate(label), path))
        pano = rep.get("panorama_path", "")
        if pano and os.path.isfile(pano):
            items.append((translate("Panorama 360°"), pano))
        return items

    def _open_preview(self, code: str):
        """Aperçu plein écran, positionné sur la vue cliquée."""
        items = self._preview_items()
        if not items:
            return
        if code == "ensemble":
            wanted = translate("Plan d'ensemble")
        else:
            wanted = translate(next((l for l, c, _d in SIX_FACES if c == code), ""))
        index = next((i for i, (lbl, _p) in enumerate(items) if lbl == wanted), 0)
        from ui.image_preview_dialog import show_images
        rep = self._current_rep() or {}
        show_images(self, items, index,
                    title=rep.get("room_group") or rep.get("name", "Aperçu"))

    def _on_engine_changed(self, *_a):
        key = self._engine_combo.currentData()
        info = next((i for k, _l, i in ENGINES if k == key), "")
        self._engine_info.setText(translate(info))
        is_qwen = key == "qwen"
        self._zoom.setVisible(is_qwen)
        self._zoom_lbl.setVisible(is_qwen)
        self._zoom_val.setVisible(is_qwen)
        self._btn_gen.setText("✦  " + translate(
            "Générer les 4 faces" if key == "orbit" else "Générer les vues"))

    # ── Génération ───────────────────────────────────────────────────────────

    def _on_generate(self):
        if self._worker is not None and self._worker.isRunning():
            return
        rep = self._current_rep()
        if rep is None:
            return
        from core.config import load_config
        if not load_config().get("api_key", "").strip():
            self._status.setText(translate(
                "Mode mock : configure ta clé fal.ai dans Paramètres pour générer les vues."))
            return
        from core.worker import abandon_thread
        if self._worker is not None:
            abandon_thread(self._worker)
        key = self._engine_combo.currentData()
        img = rep.get("image_path", "")
        name = rep.get("room_group") or rep.get("name", "decor")
        base = rep.get("room_base_prompt") or rep.get("prompt", "")
        from api.multiview import (
            QwenMultiAngleWorker, SeedanceOrbitWorker, HunyuanPanoramaWorker,
        )
        if key == "orbit":
            self._worker = SeedanceOrbitWorker(img, name, base)
        elif key == "hunyuan":
            self._worker = HunyuanPanoramaWorker(img, name, base)
        else:
            self._worker = QwenMultiAngleWorker(img, name, base,
                                                zoom=float(self._zoom.value()))
        self._worker.progress.connect(
            lambda p, m: (self._progress.setValue(p),
                          self._status.setText(translate(m))))
        self._worker.view_done.connect(self._on_view_done)
        self._worker.done.connect(self._on_done)
        self._worker.failed.connect(self._on_failed)
        self._btn_gen.setEnabled(False)
        self._progress.setValue(0)
        self._progress.setVisible(True)
        self._status.setText(translate("Génération des vues…"))
        self._worker.start()

    # ── Écriture des vues sur la pièce ───────────────────────────────────────

    def _ensure_room(self, rep: dict) -> str:
        """Un décor libre devient une pièce à sa première génération de vues."""
        g = rep.get("room_group", "")
        if g:
            return g
        g = rep.get("name", "") or "Pièce"
        rep["room_group"] = g
        rep["room_view"] = "Ensemble"
        try:
            decors_api.save_decor(rep)
        except Exception:
            pass
        return g

    def _apply_view(self, rep: dict, entry: dict):
        """Écrit UNE vue générée sur le décor frère correspondant (créé au
        besoin). Persistance incrémentale : chaque vue est sauvée dès qu'elle
        arrive, une vue qui échoue ne fait rien perdre."""
        code = entry.get("code", "")
        path = entry.get("path", "")
        if not (path and os.path.isfile(path)):
            return
        if entry.get("is_panorama"):
            rep["panorama_path"] = path
            decors_api.save_decor(rep)
            return
        if entry.get("is_orbit_video"):
            rep["orbit_video_path"] = path
            decors_api.save_decor(rep)
            return
        label = entry.get("label", code)
        group = self._ensure_room(rep)
        sib = next((s for s in decors_api.list_decors()
                    if s.get("room_group") == group
                    and s.get("room_view") == label), None)
        if sib is not None:
            sib["image_path"] = path
            sib["thumbnail_path"] = entry.get("thumbnail_path", "")
            imgs = sib.get("generated_images") or []
            if path not in imgs:
                imgs.append(path)
            sib["generated_images"] = imgs
            decors_api.save_decor(sib)
        else:
            decors_api.save_decor({
                "name":             f"{group} · {label}",
                "room_group":       group,
                "room_view":        label,
                "prompt":           entry.get("prompt", "") or rep.get("prompt", ""),
                "room_base_prompt": rep.get("room_base_prompt", ""),
                "category":         rep.get("category", "Autre"),
                "image_path":       path,
                "thumbnail_path":   entry.get("thumbnail_path", ""),
                "generated_images": [path],
                "floor_plan":       rep.get("floor_plan", ""),
                "floor_plan_thumbnail": rep.get("floor_plan_thumbnail", ""),
            })

    # ── Fin de génération ────────────────────────────────────────────────────

    def _on_view_done(self, entry: dict):
        rep = self._current_rep()
        if rep is None:
            return
        try:
            self._apply_view(rep, entry)
        except Exception:
            pass
        thumb = self._view_cards.get(entry.get("code", ""))
        p = entry.get("path", "")
        if thumb is not None and p and os.path.isfile(p) \
                and not entry.get("is_orbit_video"):
            try:
                thumb.setText("")
                thumb.setPixmap(_load_card_pixmap(p, _CARD_W, _CARD_H))
            except RuntimeError:
                pass

    def _on_done(self, views: list):
        self._progress.setVisible(False)
        self._btn_gen.setEnabled(True)
        real = [v for v in (views or [])
                if not v.get("is_panorama") and not v.get("is_orbit_video")]
        if not real:
            self._status.setText(translate(
                "Mode mock : aucune vue générée (clé fal.ai absente)"))
            return
        extras = []
        if any(v.get("is_panorama") for v in (views or [])):
            extras.append(translate("panorama 360° conservé sur la pièce"))
        if any(v.get("is_orbit_video") for v in (views or [])):
            extras.append(translate("vidéo d'orbite conservée sur la pièce"))
        n = len(real)
        msg = translate("✓ {n} vue(s) écrite(s) sur la pièce.").replace("{n}", str(n))
        if n < 6:
            msg += "  " + translate(
                "Les vues manquantes gardent leur image actuelle.")
        if extras:
            msg += "  (" + ", ".join(extras) + ")"
        self._status.setText(msg)
        self.refresh()

    def _on_failed(self, err: str):
        self._progress.setVisible(False)
        self._btn_gen.setEnabled(True)
        self._status.setText(err)
