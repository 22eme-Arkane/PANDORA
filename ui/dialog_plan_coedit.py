"""Studio de co-écriture des plans — réécrire/enrichir la « Mise en page PANDORA »
un plan à la fois, en dialoguant avec l'assistant, avant la génération du découpage.

Fenêtre PARTAGÉE Cinéma ↔ Live (nouvelle fonctionnalité) : le paramètre ``edition``
calibre le worker (format « P01 | … » Cinéma vs « PLAN n — … » Live) et ``mode``
calibre le Live (live / mapping).

Boucle : on choisit un plan (colonne gauche) → on dialogue avec l'assistant
(colonne droite, images de référence facultatives) → l'aperçu du plan se met à
jour → « Appliquer ce plan » le réinjecte dans la mise en page (chirurgical).
"""
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QTextEdit,
    QListWidget, QListWidgetItem, QWidget, QSplitter, QFrame,
)
from PyQt6.QtGui import QPixmap
from PyQt6.QtCore import Qt

from core.i18n import translate
from ui.styles import CP
from core.worker import abandon_thread
import core.plan_layout as pl

_MAX_REFS = 4


class PlanCoEditDialog(QDialog):
    """Co-écriture plan par plan de la mise en page PANDORA.

    Après ``exec()`` : ``was_applied()`` dit si au moins un plan a été appliqué,
    ``result_layout()`` retourne la mise en page mise à jour à réécrire dans
    l'onglet « Mise en page PANDORA ».
    """

    def __init__(self, parent, layout_text: str,
                 edition: str = "cinema", mode: str = "live"):
        super().__init__(parent)
        self._edition = "cinema" if edition == "cinema" else "live"
        self._mode    = mode if mode in ("live", "mapping") else "live"
        self._layout  = layout_text or ""
        self._plans   = pl.split_plans(self._layout)
        self._cur     = 0
        self._applied = False
        self._worker  = None
        self._ref_images: list[str] = []
        self._histories: dict[int, list] = {}   # index → [{role, content}]

        self.setWindowTitle(translate("☁  Co-écriture des plans — Finalisation"))
        self.setStyleSheet(f"QDialog{{background:{CP['bg0']};}}")
        try:
            from ui.widgets import fit_dialog_to_screen
            fit_dialog_to_screen(self, 0.86, 0.88, 900, 560)
        except Exception:
            self.resize(1100, 680)

        self._build_ui()
        if self._plans:
            self._select_plan(0)
        else:
            self._plan_preview.setPlainText(translate(
                "Aucun plan détecté. Génère d'abord « Mise en page PANDORA », "
                "puis reviens co-écrire les plans un par un."))
            self._plan_preview.setReadOnly(True)
            self._input.setEnabled(False)
            self._btn_send.setEnabled(False)
            self._btn_apply.setEnabled(False)
            self._update_plan_tools()   # ↑↓✕ désactivés, « ＋ Plan » reste actif

        try:
            from ui.widgets import disable_default_buttons
            disable_default_buttons(self)
        except Exception:
            pass

    # ── Construction UI ──────────────────────────────────────────────────────
    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(20, 18, 20, 16)
        root.setSpacing(12)

        # En-tête
        hdr = QHBoxLayout()
        title = QLabel(translate("☁  Co-écriture des plans"))
        title.setStyleSheet(
            f"color:{CP['text_primary']};font-size:15px;font-weight:800;background:transparent;")
        self._count_lbl = QLabel("")
        self._count_lbl.setStyleSheet(
            f"color:{CP['text_dim']};font-size:11px;background:transparent;"
            "font-family:'Consolas',monospace;")
        hdr.addWidget(title)
        hdr.addStretch()
        hdr.addWidget(self._count_lbl)
        root.addLayout(hdr)

        sub = QLabel(translate(
            "Choisis un plan, dialogue avec l'assistant pour le réécrire et l'enrichir, "
            "puis applique-le. Le reste de la mise en page reste intact."))
        sub.setWordWrap(True)
        sub.setStyleSheet(f"color:{CP['text_dim']};font-size:10px;background:transparent;")
        root.addWidget(sub)

        split = QSplitter(Qt.Orientation.Horizontal)
        split.setChildrenCollapsible(False)
        split.setStyleSheet("QSplitter::handle{background:transparent;}")

        # ── Gauche : liste des plans + aperçu du plan sélectionné ──────────────
        left = QWidget()
        left.setStyleSheet(f"background:{CP['bg1']};border-radius:10px;")
        ll = QVBoxLayout(left)
        ll.setContentsMargins(12, 12, 12, 12)
        ll.setSpacing(8)

        _lbl_plans = QLabel(translate("PLANS"))
        _lbl_plans.setStyleSheet(
            f"color:{CP['accent']};font-size:10px;font-weight:800;"
            "letter-spacing:1px;background:transparent;")
        ll.addWidget(_lbl_plans)

        self._plan_list = QListWidget()
        self._plan_list.setFixedHeight(150)
        self._plan_list.setStyleSheet(
            f"QListWidget{{background:{CP['bg2']};border:1px solid {CP['border']};"
            f"border-radius:8px;color:{CP['text_secondary']};font-size:11px;padding:4px;}}"
            f"QListWidget::item{{padding:5px 6px;border-radius:5px;}}"
            f"QListWidget::item:selected{{background:{CP['accent2']};color:#fff;}}"
            f"QListWidget::item:hover{{background:{CP['bg3']};}}")
        self._plan_list.currentRowChanged.connect(self._on_row_changed)
        ll.addWidget(self._plan_list)

        # ── Réordonner / ajouter / supprimer des plans ─────────────────────────
        _plan_tools = QHBoxLayout()
        _plan_tools.setContentsMargins(0, 0, 0, 0)
        _plan_tools.setSpacing(5)

        def _mini_btn(txt, tip, fn, danger=False):
            b = QPushButton(translate(txt))
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.setToolTip(translate(tip))
            b.setFixedHeight(26)
            _c = CP.get("red", "#ff4f6a") if danger else CP["accent2"]
            b.setStyleSheet(
                f"QPushButton{{background:transparent;border:1px solid {CP['border']};"
                f"border-radius:6px;color:{CP['text_secondary']};font-size:11px;"
                f"font-weight:700;padding:0 8px;}}"
                f"QPushButton:hover{{border-color:{_c};color:{_c};}}"
                f"QPushButton:disabled{{opacity:0.35;}}")
            b.clicked.connect(fn)
            return b

        self._btn_move_up   = _mini_btn("↑", "Monter ce plan", lambda: self._move_plan(-1))
        self._btn_move_down = _mini_btn("↓", "Descendre ce plan", lambda: self._move_plan(1))
        self._btn_add_plan  = _mini_btn("＋ Plan", "Ajouter un plan après celui-ci", self._add_plan)
        self._btn_del_plan  = _mini_btn("×  Suppr.", "Supprimer ce plan", self._delete_plan, danger=True)
        _plan_tools.addWidget(self._btn_move_up)
        _plan_tools.addWidget(self._btn_move_down)
        _plan_tools.addWidget(self._btn_add_plan, 1)
        _plan_tools.addWidget(self._btn_del_plan)
        ll.addLayout(_plan_tools)

        _lbl_prev = QLabel(translate("APERÇU DU PLAN"))
        _lbl_prev.setStyleSheet(
            f"color:{CP['accent']};font-size:10px;font-weight:800;"
            "letter-spacing:1px;background:transparent;")
        ll.addWidget(_lbl_prev)

        self._plan_preview = QTextEdit()
        self._plan_preview.setStyleSheet(
            f"QTextEdit{{background:{CP['bg2']};border:1px solid {CP['border']};"
            f"border-radius:8px;color:{CP['text_primary']};font-size:11px;"
            "font-family:'Consolas',monospace;padding:10px;}}")
        ll.addWidget(self._plan_preview, 1)
        split.addWidget(left)

        # ── Droite : chat + images + saisie ────────────────────────────────────
        right = QWidget()
        right.setStyleSheet(f"background:{CP['bg1']};border-radius:10px;")
        rl = QVBoxLayout(right)
        rl.setContentsMargins(12, 12, 12, 12)
        rl.setSpacing(8)

        _lbl_chat = QLabel(translate("DIALOGUE"))
        _lbl_chat.setStyleSheet(
            f"color:{CP['accent']};font-size:10px;font-weight:800;"
            "letter-spacing:1px;background:transparent;")
        rl.addWidget(_lbl_chat)

        self._chat = QTextEdit()
        self._chat.setReadOnly(True)
        self._chat.setStyleSheet(
            f"QTextEdit{{background:{CP['bg2']};border:1px solid {CP['border']};"
            f"border-radius:8px;color:{CP['text_primary']};font-size:11px;padding:10px;}}")
        rl.addWidget(self._chat, 1)

        # Bande d'images de référence (bibliothèque + fichier, max 4)
        self._refs_hbox = QHBoxLayout()
        self._refs_hbox.setSpacing(6)
        _refs_wrap = QWidget()
        _refs_wrap.setStyleSheet("background:transparent;")
        _refs_wrap.setLayout(self._refs_hbox)
        rl.addWidget(_refs_wrap)

        self._input = QTextEdit()
        self._input.setFixedHeight(64)
        self._input.setPlaceholderText(translate(
            "Ex : « Rends ce plan plus intime, lumière tamisée, caméra plus proche… »"))
        self._input.setStyleSheet(
            f"QTextEdit{{background:{CP['bg2']};border:1px solid {CP['border']};"
            f"border-radius:8px;color:{CP['text_primary']};font-size:11px;padding:8px;}}")
        rl.addWidget(self._input)

        self._status = QLabel("")
        self._status.setStyleSheet(
            f"color:{CP['text_dim']};font-size:10px;background:transparent;"
            "font-family:'Consolas',monospace;")
        rl.addWidget(self._status)

        self._btn_send = QPushButton(translate("☁  Envoyer à l'assistant"))
        self._btn_send.setFixedHeight(38)
        self._btn_send.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_send.setStyleSheet(
            f"QPushButton{{background:{CP['accent2']};color:#fff;border:none;"
            f"border-radius:8px;font-size:11px;font-weight:700;padding:0 18px;}}"
            f"QPushButton:hover{{background:#9d8fff;}}"
            f"QPushButton:disabled{{background:{CP['bg3']};color:{CP['text_dim']};}}")
        self._btn_send.clicked.connect(self._on_send)
        rl.addWidget(self._btn_send)
        split.addWidget(right)

        split.setSizes([420, 520])
        root.addWidget(split, 1)

        # ── Bas : Fermer / Appliquer ce plan ───────────────────────────────────
        bottom = QHBoxLayout()
        bottom.setSpacing(8)
        btn_close = QPushButton(translate("Fermer"))
        btn_close.setFixedHeight(36)
        btn_close.setStyleSheet(
            f"QPushButton{{background:{CP['bg3']};color:{CP['text_secondary']};"
            f"border:1px solid {CP['border']};border-radius:7px;font-size:11px;"
            f"font-weight:600;padding:0 22px;}}"
            f"QPushButton:hover{{background:{CP['bg4']};color:{CP['text_primary']};}}")
        btn_close.clicked.connect(self.accept)

        self._btn_apply = QPushButton(translate("✓  Appliquer ce plan"))
        self._btn_apply.setFixedHeight(36)
        self._btn_apply.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_apply.setStyleSheet(
            f"QPushButton{{background:{CP['accent']};color:{CP['bg0']};border:none;"
            f"border-radius:7px;font-size:11px;font-weight:800;padding:0 22px;}}"
            f"QPushButton:hover{{background:{CP['accent_dim']};color:#fff;}}"
            f"QPushButton:disabled{{background:{CP['bg3']};color:{CP['text_dim']};}}")
        self._btn_apply.clicked.connect(self._on_apply_plan)

        bottom.addWidget(btn_close)
        bottom.addStretch()
        bottom.addWidget(self._btn_apply)
        root.addLayout(bottom)

        self._refresh_refs_strip()

    # ── Sélection de plan ────────────────────────────────────────────────────
    def _reload_list(self):
        self._plan_list.blockSignals(True)
        self._plan_list.clear()
        for p in self._plans:
            QListWidgetItem(p["label"], self._plan_list)
        self._count_lbl.setText(
            translate("{n} plan(s)").format(n=len(self._plans)))
        self._plan_list.blockSignals(False)

    def _select_plan(self, index: int):
        if not self._plans:
            return
        index = max(0, min(index, len(self._plans) - 1))
        self._cur = index
        self._reload_list()
        self._plan_list.setCurrentRow(index)
        self._set_preview(self._plans[index]["text"])
        self._render_chat()
        self._update_plan_tools()

    def _on_row_changed(self, row: int):
        if row < 0 or row >= len(self._plans) or row == self._cur:
            return
        self._cur = row
        self._set_preview(self._plans[row]["text"])
        self._render_chat()
        self._update_plan_tools()

    def _set_preview(self, text: str):
        """Écrit l'aperçu du plan avec une RESPIRATION entre les paragraphes (comme la
        Mise en page PANDORA) : chaque ligne (Durée, PROMPT VIDÉO, PROMPT SON…) est
        séparée pour une lecture facile — plus de bloc compact illisible."""
        self._plan_preview.setPlainText(text)
        try:
            from ui.widgets import apply_paragraph_spacing
            apply_paragraph_spacing(self._plan_preview, px=10)
        except Exception:
            pass

    # ── Réordonner / ajouter / supprimer des plans ───────────────────────────
    def _update_plan_tools(self):
        """Active/désactive ↑ ↓ ✕ selon la position et le nombre de plans."""
        if not hasattr(self, "_btn_move_up"):
            return
        n = len(self._plans)
        self._btn_move_up.setEnabled(0 < self._cur < n)
        self._btn_move_down.setEnabled(0 <= self._cur < n - 1)
        self._btn_del_plan.setEnabled(n > 0)

    def _structural_change(self, new_layout: str, select_index: int):
        """Applique un changement STRUCTUREL (ordre / ajout / suppression) : met à jour
        la mise en page, re-parse, marque « appliqué » et sélectionne le plan voulu.
        Le chat par plan est réinitialisé (les index changent)."""
        self._layout = new_layout
        self._plans = pl.split_plans(self._layout)
        self._histories.clear()
        self._applied = True
        if not self._plans:
            self._plan_list.clear()
            self._set_preview("")
            self._count_lbl.setText(translate("{n} plan(s)").format(n=0))
            self._update_plan_tools()
            return
        # Réactive la saisie si on repart d'un état « aucun plan ».
        for w in (getattr(self, "_input", None), getattr(self, "_btn_send", None),
                  getattr(self, "_btn_apply", None)):
            if w is not None:
                w.setEnabled(True)
        self._plan_preview.setReadOnly(False)
        self._select_plan(max(0, min(select_index, len(self._plans) - 1)))

    def _move_plan(self, delta: int):
        if not self._plans or not (0 <= self._cur + delta < len(self._plans)):
            return
        self._structural_change(pl.move_plan(self._layout, self._cur, delta),
                                self._cur + delta)
        self._status.setText(translate("Plan déplacé ✓"))

    def _add_plan(self):
        idx = self._cur if self._plans else -1
        self._structural_change(pl.add_plan(self._layout, idx, self._edition),
                                (idx + 1) if self._plans else 0)
        self._status.setText(translate("Plan ajouté ✓"))

    def _delete_plan(self):
        if not self._plans:
            return
        self._structural_change(pl.delete_plan(self._layout, self._cur),
                                min(self._cur, len(self._plans) - 2))
        self._status.setText(translate("Plan supprimé ✓"))

    # ── Chat ─────────────────────────────────────────────────────────────────
    def _render_chat(self):
        hist = self._histories.get(self._cur, [])
        if not hist:
            self._chat.setHtml(
                f"<div style='color:{CP['text_dim']};font-size:11px;'>"
                + translate("Décris à l'assistant comment retravailler ce plan.")
                + "</div>")
            return
        html = []
        for m in hist:
            if m["role"] == "user":
                html.append(
                    f"<p style='margin:6px 0;'><b style='color:{CP['accent2']};'>"
                    + translate("Toi") + " :</b> "
                    + f"<span style='color:{CP['text_primary']};'>{_esc(m['content'])}</span></p>")
            else:
                html.append(
                    f"<p style='margin:6px 0;'><b style='color:{CP['accent']};'>"
                    + translate("Assistant") + " :</b> "
                    + f"<span style='color:{CP['text_secondary']};'>{_esc(m['content'])}</span></p>")
        self._chat.setHtml("".join(html))
        self._chat.verticalScrollBar().setValue(
            self._chat.verticalScrollBar().maximum())

    def _on_send(self):
        if not self._plans:
            return
        msg = self._input.toPlainText().strip()
        if not msg:
            return
        if self._worker and self._worker.isRunning():
            return
        # Le plan courant part de l'aperçu (édits manuels pris en compte).
        cur_plan = self._plan_preview.toPlainText().strip()
        self._plans[self._cur]["text"] = cur_plan
        hist = self._histories.setdefault(self._cur, [])
        hist.append({"role": "user", "content": msg})
        self._render_chat()
        self._input.clear()

        from api.plan_coedit import PlanCoEditWorker
        self._set_busy(True)
        self._worker = PlanCoEditWorker(
            layout_text=self._layout,
            plan_text=cur_plan,
            plan_label=self._plans[self._cur]["label"],
            history=hist[:-1],
            user_message=msg,
            edition=self._edition,
            mode=self._mode,
            ref_images=list(self._ref_images),
        )
        self._worker.message_ready.connect(self._on_message_ready)
        self._worker.plan_ready.connect(self._on_plan_ready)
        self._worker.failed.connect(self._on_failed)
        self._worker.start()

    def _on_message_ready(self, reply: str):
        self._histories.setdefault(self._cur, []).append(
            {"role": "assistant", "content": reply})
        self._render_chat()

    def _on_plan_ready(self, plan: str):
        self._set_busy(False)
        self._set_preview(plan.strip())
        self._status.setText(translate(
            "Proposition prête — relis, ajuste, puis « Appliquer ce plan »."))

    def _on_failed(self, err: str):
        self._set_busy(False)
        self._status.setText("⚠ " + str(err)[:200])

    def _set_busy(self, busy: bool):
        self._btn_send.setEnabled(not busy)
        self._input.setEnabled(not busy)
        self._status.setText(translate("Rédaction en cours…") if busy else "")

    # ── Application chirurgicale ─────────────────────────────────────────────
    def _on_apply_plan(self):
        if not self._plans:
            return
        new_text = self._plan_preview.toPlainText().strip()
        if not new_text:
            return
        self._layout = pl.replace_plan(self._layout, self._cur, new_text)
        self._plans = pl.split_plans(self._layout)
        self._applied = True
        idx = min(self._cur, len(self._plans) - 1) if self._plans else 0
        self._select_plan(idx)
        self._status.setText(translate("Plan appliqué à la mise en page ✓"))

    # ── Images de référence ──────────────────────────────────────────────────
    def _on_add_refs(self):
        if len(self._ref_images) >= _MAX_REFS:
            return
        try:
            from ui.dialog_image_library import ImageLibraryDialog
            paths = ImageLibraryDialog.pick(self)
        except Exception:
            paths = None
        if not paths:
            return
        for p in paths[:_MAX_REFS - len(self._ref_images)]:
            if p not in self._ref_images:
                self._ref_images.append(p)
        self._refresh_refs_strip()

    def _remove_ref(self, path: str):
        if path in self._ref_images:
            self._ref_images.remove(path)
        self._refresh_refs_strip()

    def _refresh_refs_strip(self):
        while self._refs_hbox.count():
            item = self._refs_hbox.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        btn_add = QPushButton("＋")
        btn_add.setFixedSize(44, 44)
        btn_add.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_add.setToolTip(translate("Ajouter des images d'inspiration (bibliothèque ou fichier, max 4)"))
        btn_add.setEnabled(len(self._ref_images) < _MAX_REFS)
        btn_add.setStyleSheet(
            f"QPushButton{{background:{CP['bg2']};color:{CP['text_dim']};"
            f"border:2px dashed {CP['border']};border-radius:6px;font-size:18px;}}"
            f"QPushButton:hover{{background:{CP['bg3']};color:{CP['text_secondary']};"
            f"border-color:{CP['border_bright']};}}")
        btn_add.clicked.connect(self._on_add_refs)
        self._refs_hbox.addWidget(btn_add)

        for path in self._ref_images:
            cell = QWidget()
            cell.setFixedSize(44, 44)
            cell.setStyleSheet("background:transparent;")
            thumb = QLabel(cell)
            thumb.setFixedSize(44, 44)
            thumb.setScaledContents(True)
            thumb.setStyleSheet(
                f"border-radius:6px;border:1px solid {CP['border']};background:{CP['bg2']};")
            px = QPixmap(path)
            if not px.isNull():
                thumb.setPixmap(px)
            else:
                thumb.setText("?")
                thumb.setAlignment(Qt.AlignmentFlag.AlignCenter)
            btn_rm = QPushButton("✕", cell)
            btn_rm.setFixedSize(15, 15)
            btn_rm.move(29, 0)
            btn_rm.setCursor(Qt.CursorShape.PointingHandCursor)
            btn_rm.setStyleSheet(
                f"QPushButton{{background:{CP['bg3']};color:{CP['text_primary']};"
                f"border:1px solid {CP['border_bright']};border-radius:4px;"
                "font-size:9px;font-weight:700;padding:0;}}"
                f"QPushButton:hover{{background:{CP['red']};color:#fff;border-color:{CP['red']};}}")
            btn_rm.clicked.connect(lambda _=False, p=path: self._remove_ref(p))
            self._refs_hbox.addWidget(cell)

        self._refs_hbox.addStretch()

    # ── Résultat ─────────────────────────────────────────────────────────────
    def was_applied(self) -> bool:
        return self._applied

    def result_layout(self) -> str:
        return self._layout

    def closeEvent(self, ev):
        if self._worker is not None:
            try:
                abandon_thread(self._worker)
            except Exception:
                pass
        super().closeEvent(ev)


def _esc(s: str) -> str:
    return (str(s).replace("&", "&amp;").replace("<", "&lt;")
            .replace(">", "&gt;").replace("\n", "<br>"))
