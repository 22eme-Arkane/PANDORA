"""
ui/page_live_conducteur.py — Page « Conducteur » de PANDORA | Live.

Équivalent Live du scénario : éditeur de trame à gauche, panneau Claude à droite
(même arborescence que le Scénario Cinéma, mais typé Live / Mapping) :
  - ☁ Claude IA : Mise en page · Analyse & co-écriture
  - ☁ Générer depuis le conducteur : Casting · Accessoires · Véhicules · Découpage · Tout générer
  - ◎ Références visuelles : ajout d'images + analyse Claude

Le mode (Live / Mapping) calibre toutes les opérations Claude.
"""

import os

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QTextEdit, QFrame,
    QMessageBox, QScrollArea, QFileDialog,
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QPixmap

from ui.styles import CP
from core.i18n import translate
import core.live_conducteur as lc
import core.live_sequences as lseq
import core.live_assets as la


class PageLiveConducteur(QWidget):
    navigate_requested = pyqtSignal(str)   # "seq_live" | "seq_mapping"

    def __init__(self):
        super().__init__()
        self._mode = "live"
        self._workers: list = []
        self._ref_images: list[str] = []
        self._pending_all = 0

        self.setStyleSheet(f"background:{CP['bg0']};")
        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        root.addWidget(self._build_editor(), 1)
        root.addWidget(self._build_side_panel())

        self._load()

    # ── Éditeur (gauche) ───────────────────────────────────────────────────────

    def _build_editor(self) -> QWidget:
        w = QWidget()
        w.setStyleSheet("background:transparent;")
        lay = QVBoxLayout(w)
        lay.setContentsMargins(32, 24, 24, 24)
        lay.setSpacing(14)

        top = QHBoxLayout(); top.setSpacing(12)
        title = QLabel(translate("Conducteur"))
        title.setStyleSheet(
            f"color:{CP['text_primary']};font-size:22px;font-weight:800;background:transparent;border:none;"
        )
        top.addWidget(title)
        top.addSpacing(16)
        mode_lbl = QLabel(translate("Mode :"))
        mode_lbl.setStyleSheet(f"color:{CP['text_secondary']};font-size:12px;background:transparent;border:none;")
        top.addWidget(mode_lbl)
        self._btn_live    = self._mode_btn("Live")
        self._btn_mapping = self._mode_btn("Mapping")
        self._btn_live.clicked.connect(lambda: self._set_mode("live"))
        self._btn_mapping.clicked.connect(lambda: self._set_mode("mapping"))
        top.addWidget(self._btn_live)
        top.addWidget(self._btn_mapping)
        top.addStretch()
        btn_save = QPushButton(translate("Enregistrer"))
        btn_save.setFixedHeight(32)
        btn_save.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_save.setStyleSheet(
            f"QPushButton{{background:transparent;color:{CP['text_secondary']};"
            f"border:1px solid {CP['border']};border-radius:7px;font-size:11px;font-weight:700;padding:0 16px;}}"
            f"QPushButton:hover{{background:{CP['bg2']};color:{CP['text_primary']};}}"
        )
        btn_save.clicked.connect(self._save)
        top.addWidget(btn_save)
        lay.addLayout(top)

        self._hint = QLabel("")
        self._hint.setWordWrap(True)
        self._hint.setStyleSheet(f"color:{CP['text_dim']};font-size:11px;background:transparent;border:none;")
        lay.addWidget(self._hint)

        self._editor = QTextEdit()
        self._editor.setPlaceholderText(translate(
            "Écrivez la trame de votre performance… (ambiances, moments, montée, "
            "ruptures, final). Claude la découpera en segments selon le mode choisi."
        ))
        self._editor.setStyleSheet(
            f"QTextEdit{{background:{CP['bg2']};border:1px solid {CP['border']};"
            f"border-radius:10px;color:{CP['text_primary']};font-size:13px;padding:12px 14px;}}"
            f"QTextEdit:focus{{border-color:{CP['accent2']};}}"
        )
        lay.addWidget(self._editor, 1)

        self._status = QLabel("")
        self._status.setWordWrap(True)
        self._status.setStyleSheet(f"color:{CP['text_dim']};font-size:11px;background:transparent;border:none;")
        lay.addWidget(self._status)
        return w

    def _mode_btn(self, label: str) -> QPushButton:
        b = QPushButton(translate(label))
        b.setFixedHeight(32)
        b.setCursor(Qt.CursorShape.PointingHandCursor)
        return b

    def _apply_mode_style(self):
        for b, m in ((self._btn_live, "live"), (self._btn_mapping, "mapping")):
            active = (self._mode == m)
            b.setStyleSheet(
                f"QPushButton{{background:{'rgba(124,107,255,0.18)' if active else 'transparent'};"
                f"color:{CP['accent2'] if active else CP['text_secondary']};"
                f"border:1px solid {CP['accent2'] if active else CP['border']};border-radius:7px;"
                f"font-size:12px;font-weight:700;padding:0 16px;}}"
                f"QPushButton:hover{{border-color:{CP['accent2']};}}"
            )
        self._hint.setText(translate(
            "Mode Mapping : la trame sera découpée en une séquence CONTINUE projetée "
            "sur une façade verrouillée (caméra fixe, raccord automatique)."
        ) if self._mode == "mapping" else translate(
            "Mode Live : la trame sera découpée en une suite de plans/loops pour "
            "votre performance VJ (valeurs de plan, mouvements)."
        ))

    def _set_mode(self, mode: str):
        self._mode = mode
        self._apply_mode_style()

    # ── Panneau droit ──────────────────────────────────────────────────────────

    def _build_side_panel(self) -> QWidget:
        panel = QScrollArea()
        panel.setFixedWidth(300)
        panel.setWidgetResizable(True)
        panel.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        panel.setStyleSheet(f"QScrollArea{{background:{CP['bg1']};border-left:1px solid {CP['border']};}}")
        inner = QWidget()
        inner.setStyleSheet("background:transparent;")
        panel.setWidget(inner)
        lay = QVBoxLayout(inner)
        lay.setContentsMargins(14, 16, 14, 16)
        lay.setSpacing(10)

        # ── Claude IA ──────────────────────────────────────────────────────────
        body_ia, lay_ia = self._make_section("☁  Claude IA", True)
        lay_ia.addWidget(self._action("◈", "Mise en page", "Met en forme la trame (typée Live/Mapping)", self._on_format))
        lay_ia.addWidget(self._action("⊞", "Analyse & co-écriture", "Réécrit une version améliorée de la trame", self._on_arrange))
        lay.addWidget(body_ia)

        # ── Générer depuis le conducteur ───────────────────────────────────────
        body_gen, lay_gen = self._make_section("☁  Générer depuis le conducteur", True)
        lay_gen.addWidget(self._action("☺", "Générer le casting", "Identifier les personnages depuis la trame", lambda: self._on_extract("casting")))
        lay_gen.addWidget(self._action("❖", "Générer les accessoires", "Identifier les accessoires depuis la trame", lambda: self._on_extract("accessoires")))
        lay_gen.addWidget(self._action("⛟", "Générer les véhicules", "Identifier les véhicules depuis la trame", lambda: self._on_extract("vehicules")))
        lay_gen.addWidget(self._action("⊕", "Générer le découpage", "Découpe la trame en séquence (Live/Mapping)", self._on_decoupage))
        self._btn_all = self._action("✦", "Tout générer", "Casting + accessoires + véhicules + découpage", self._on_all, accent=True)
        lay_gen.addWidget(self._btn_all)
        lay.addWidget(body_gen)

        # ── Références visuelles ───────────────────────────────────────────────
        body_ref, lay_ref = self._make_section("◎  Références visuelles", False)
        self._refs_row = QHBoxLayout(); self._refs_row.setSpacing(6); self._refs_row.setAlignment(Qt.AlignmentFlag.AlignLeft)
        _refs_wrap = QWidget(); _refs_wrap.setStyleSheet("background:transparent;"); _refs_wrap.setLayout(self._refs_row)
        lay_ref.addWidget(_refs_wrap)
        lay_ref.addWidget(self._action("＋", "Ajouter des images", "Photos de lieux, ambiances, références", self._on_add_refs))
        lay_ref.addWidget(self._action("◈", "Analyser avec Claude", "Enrichit la trame à partir des images", self._on_analyze_refs))
        lay.addWidget(body_ref)

        lay.addStretch()
        return panel

    def _make_section(self, title: str, expanded: bool):
        wrap = QWidget(); wrap.setStyleSheet("background:transparent;")
        wl = QVBoxLayout(wrap); wl.setContentsMargins(0, 0, 0, 0); wl.setSpacing(6)
        header = QPushButton(("▼  " if expanded else "▶  ") + translate(title))
        header.setFlat(True); header.setCursor(Qt.CursorShape.PointingHandCursor)
        header.setStyleSheet(
            f"QPushButton{{background:transparent;color:{CP['accent2']};font-size:11px;font-weight:700;"
            f"letter-spacing:1px;border:none;text-align:left;padding:4px 0;}}"
            f"QPushButton:hover{{color:#8f80ff;}}"
        )
        body = QWidget(); body.setStyleSheet("background:transparent;")
        body.setVisible(expanded)
        bl = QVBoxLayout(body); bl.setContentsMargins(0, 0, 0, 6); bl.setSpacing(6)
        wl.addWidget(header); wl.addWidget(body)

        def _toggle(_=None, h=header, b=body, t=title):
            vis = not b.isVisible()
            b.setVisible(vis)
            h.setText(("▼  " if vis else "▶  ") + translate(t))
        header.clicked.connect(_toggle)
        return wrap, bl

    def _action(self, icon: str, label: str, desc: str, slot, accent: bool = False) -> QWidget:
        btn = QPushButton()
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.setMinimumHeight(46)
        bg = "rgba(124,107,255,0.16)" if accent else CP["bg2"]
        bd = CP["accent2"] if accent else CP["border"]
        btn.setStyleSheet(
            f"QPushButton{{background:{bg};border:1px solid {bd};border-radius:8px;text-align:left;padding:6px 10px;}}"
            f"QPushButton:hover{{border-color:{CP['accent2']};}}"
            f"QPushButton:disabled{{color:{CP['text_dim']};}}"
        )
        lay = QHBoxLayout(btn); lay.setContentsMargins(6, 4, 6, 4); lay.setSpacing(8)
        ic = QLabel(icon); ic.setFixedWidth(18)
        ic.setStyleSheet(f"color:{CP['accent2']};font-size:14px;background:transparent;border:none;")
        lay.addWidget(ic)
        col = QVBoxLayout(); col.setSpacing(1)
        l1 = QLabel(translate(label))
        l1.setStyleSheet(f"color:{CP['text_primary']};font-size:12px;font-weight:700;background:transparent;border:none;")
        l2 = QLabel(translate(desc))
        l2.setWordWrap(True)
        l2.setStyleSheet(f"color:{CP['text_dim']};font-size:9px;background:transparent;border:none;")
        col.addWidget(l1); col.addWidget(l2)
        lay.addLayout(col, 1)
        btn.clicked.connect(slot)
        return btn

    # ── Persistance ────────────────────────────────────────────────────────────

    def _load(self):
        data = lc.load()
        self._editor.setPlainText(data.get("text", ""))
        self._mode = data.get("mode", "live")
        self._apply_mode_style()

    def _save(self):
        lc.save(self._editor.toPlainText(), self._mode)
        self._status.setText("✓  " + translate("Conducteur enregistré."))

    def _text(self) -> str:
        return self._editor.toPlainText().strip()

    def _require_text(self) -> bool:
        if not self._text():
            QMessageBox.warning(self, translate("Trame vide"),
                                translate("Écrivez la trame de votre performance d'abord."))
            return False
        return True

    # ── Mise en page / arrangement ──────────────────────────────────────────────

    def _on_format(self):
        if not self._require_text():
            return
        self._save()
        from api.live_extract import FormatConducteurWorker
        self._status.setText(translate("Mise en page en cours via Claude…"))
        w = FormatConducteurWorker(self._text(), self._mode)
        w.finished.connect(self._on_text_result)
        w.failed.connect(self._on_fail)
        self._run(w)

    def _on_arrange(self):
        if not self._require_text():
            return
        self._save()
        from api.live_extract import ArrangeConducteurWorker
        self._status.setText(translate("Arrangement en cours via Claude…"))
        w = ArrangeConducteurWorker(self._text(), self._mode)
        w.finished.connect(self._on_text_result)
        w.failed.connect(self._on_fail)
        self._run(w)

    def _on_text_result(self, text: str):
        if text:
            self._editor.setPlainText(text)
            self._save()
            self._status.setText("✓  " + translate("Trame mise à jour par Claude."))

    # ── Extraction casting / accessoires / véhicules ─────────────────────────────

    def _on_extract(self, kind: str):
        if not self._require_text():
            return
        from api.live_extract import ExtractLiveAssetsWorker
        self._status.setText(translate("Extraction en cours via Claude…"))
        w = ExtractLiveAssetsWorker(kind, self._text(), self._mode)
        w.finished.connect(self._on_extracted)
        w.failed.connect(self._on_fail)
        self._run(w)

    def _on_extracted(self, kind: str, items: list):
        import core.casting as _cast, core.accessories as _acc, core.vehicles as _veh
        savers = {
            "casting":     _cast.save_character,
            "accessoires": _acc.save_accessory,
            "vehicules":   _veh.save_vehicle,
        }
        save = savers.get(kind)
        for it in items:
            desc = it.get("description", "")
            cat  = it.get("category", "")
            if cat:
                desc = f"{cat} — {desc}" if desc else cat
            if save:
                save({"name": it.get("name", ""), "description": desc})
        names = {"casting": "Casting", "accessoires": "Accessoires", "vehicules": "Véhicules"}
        self._status.setText(
            f"✓  {len(items)} " + translate("éléments ajoutés à") + f" {translate(names.get(kind, kind))}"
        )
        if self._pending_all:
            self._pending_all -= 1
            self._check_all_done()

    # ── Découpage ────────────────────────────────────────────────────────────────

    def _on_decoupage(self):
        if not self._require_text():
            return
        self._save()
        from api.live_screenplay import GenerateDecoupageWorker
        self._status.setText(translate("Génération du découpage avec Claude…"))
        w = GenerateDecoupageWorker(self._text(), self._mode)
        w.finished.connect(self._on_decoupage_done)
        w.failed.connect(self._on_fail)
        self._run(w)

    def _on_decoupage_done(self, segments: list):
        import core.storyboard as _sb
        _sb.set_namespace(f"live_seq_{self._mode}")
        _sb.clear_version_shots(_sb.DEFAULT_VERSION_ID)
        for i, seg in enumerate(segments, 1):
            _sb.save_shot({
                "number":          i,
                "scene_title":     seg.get("action", ""),
                "shot_size":       seg.get("shot_size", ""),
                "camera_movement": seg.get("camera_movement", ""),
                "duration":        seg.get("duration", 5),
                # UN seul prompt à sections (vidéo + [🎵 SOUND DESIGN]) ; sound_prompt en repli.
                "seedance_prompt": seg.get("seedance_prompt") or seg.get("prompt", ""),
                "sound_prompt":    seg.get("sound_prompt", ""),
            }, _sb.DEFAULT_VERSION_ID)
        target = "seq_mapping" if self._mode == "mapping" else "seq_live"
        seq_name = translate("Séquences Mapping") if self._mode == "mapping" else translate("Séquences Live")
        self._status.setText(f"✓  {len(segments)} " + translate("segments générés →") + f" {seq_name}")
        if self._pending_all:
            self._pending_all -= 1
            self._check_all_done()
        else:
            self.navigate_requested.emit(target)

    # ── Tout générer ─────────────────────────────────────────────────────────────

    def _on_all(self):
        if not self._require_text():
            return
        if QMessageBox.question(
            self, translate("Tout générer"),
            translate("Lancer l'extraction du casting, des accessoires, des véhicules et "
                      "le découpage depuis la trame ?")
        ) != QMessageBox.StandardButton.Yes:
            return
        self._save()
        self._pending_all = 4
        self._status.setText(translate("Tout générer — en cours via Claude…"))
        from api.live_extract import ExtractLiveAssetsWorker
        from api.live_screenplay import GenerateDecoupageWorker
        for kind in ("casting", "accessoires", "vehicules"):
            w = ExtractLiveAssetsWorker(kind, self._text(), self._mode)
            w.finished.connect(self._on_extracted)
            w.failed.connect(self._on_all_fail)
            self._run(w)
        w = GenerateDecoupageWorker(self._text(), self._mode)
        w.finished.connect(self._on_decoupage_done)
        w.failed.connect(self._on_all_fail)
        self._run(w)

    def _on_all_fail(self, err: str):
        if self._pending_all:
            self._pending_all -= 1
            self._check_all_done()
        self._status.setText(f"✗  {err[:140]}")

    def _check_all_done(self):
        if self._pending_all <= 0:
            self._pending_all = 0
            self._status.setText("✓  " + translate("Tout générer terminé."))

    # ── Références visuelles ─────────────────────────────────────────────────────

    def _on_add_refs(self):
        paths, _ = QFileDialog.getOpenFileNames(
            self, translate("Choisir des images de référence"), "",
            "Images (*.png *.jpg *.jpeg *.webp *.bmp)")
        for p in paths:
            if p and os.path.isfile(p) and p not in self._ref_images:
                self._ref_images.append(p)
        self._refresh_refs()

    def _refresh_refs(self):
        while self._refs_row.count():
            it = self._refs_row.takeAt(0)
            if it.widget():
                it.widget().deleteLater()
        for p in self._ref_images[:6]:
            thumb = QLabel()
            thumb.setFixedSize(46, 46)
            thumb.setStyleSheet(f"background:{CP['bg3']};border:1px solid {CP['border']};border-radius:5px;")
            thumb.setPixmap(QPixmap(p).scaled(44, 44, Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                                              Qt.TransformationMode.SmoothTransformation))
            self._refs_row.addWidget(thumb)

    def _on_analyze_refs(self):
        if not self._ref_images:
            self._status.setText(translate("Ajoutez d'abord des images de référence."))
            return
        from api.screenplay import AnalyzeReferencesWorker
        self._status.setText(translate("Analyse des références avec Claude…"))
        w = AnalyzeReferencesWorker(list(self._ref_images), self._text())
        w.done.connect(self._on_refs_analyzed)
        w.failed.connect(self._on_fail)
        self._run(w)

    def _on_refs_analyzed(self, text: str):
        if text:
            cur = self._editor.toPlainText().rstrip()
            self._editor.setPlainText((cur + "\n\n" + text.strip()) if cur else text.strip())
            self._save()
            self._status.setText("✓  " + translate("Trame enrichie depuis les références."))

    # ── Utilitaires workers ──────────────────────────────────────────────────────

    def _run(self, worker):
        worker.finished.connect(lambda *_: self._cleanup(worker)) if hasattr(worker, "finished") else None
        if hasattr(worker, "done"):
            worker.done.connect(lambda *_: self._cleanup(worker))
        worker.failed.connect(lambda *_: self._cleanup(worker))
        self._workers.append(worker)
        worker.start()

    def _cleanup(self, worker):
        try:
            self._workers.remove(worker)
        except ValueError:
            pass

    def _on_fail(self, err: str):
        self._status.setText(f"✗  {err[:160]}")
