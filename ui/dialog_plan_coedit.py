"""Studio de co-écriture des plans — réécrire/enrichir la « Mise en page PANDORA »
un plan à la fois, en dialoguant avec l'assistant, avant la génération du découpage.

Fenêtre PARTAGÉE Cinéma ↔ Live (nouvelle fonctionnalité) : le paramètre ``edition``
calibre le worker (format « P01 | … » Cinéma vs « PLAN n — … » Live) et ``mode``
calibre le Live (live / mapping).

Boucle : on choisit un plan (colonne gauche) → on dialogue avec l'assistant
(colonne droite, images de référence facultatives) → l'aperçu du plan se met à
jour. « Appliquer les modifications » réinjecte EN UNE FOIS tous les plans
édités / réordonnés / ajoutés / supprimés dans la « Mise en page PANDORA », puis
ferme la fenêtre. « Fermer » abandonne les changements (avec confirmation).
"""
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QTextEdit,
    QListWidget, QListWidgetItem, QWidget, QSplitter, QFrame, QMenu,
    QAbstractItemView, QScrollArea,
)
from PyQt6.QtGui import QPixmap, QKeySequence, QShortcut
from PyQt6.QtCore import Qt, pyqtSignal, QTimer

from core.i18n import translate
from ui.styles import CP
from core.worker import abandon_thread
import core.plan_layout as pl

# Plafond d'images de référence : source de vérité côté worker (importée ici pour que
# l'UI et l'envoi soient TOUJOURS d'accord — sinon relever l'UI ne servirait à rien).
try:
    from api.plan_coedit import _MAX_REF_IMAGES as _MAX_REFS
except Exception:
    _MAX_REFS = 12


class _PlanListWidget(QListWidget):
    """Liste des plans avec réordonnancement par GLISSER-DÉPOSER (comme le storyboard).
    Émet ``reordered`` après un déplacement interne."""
    reordered = pyqtSignal()

    def dropEvent(self, event):
        super().dropEvent(event)
        self.reordered.emit()


class PlanCoEditDialog(QDialog):
    """Co-écriture plan par plan de la mise en page PANDORA.

    Après ``exec()`` : ``was_applied()`` n'est vrai QUE si l'utilisateur a cliqué
    « Appliquer les modifications » (ou confirmé « Appliquer et fermer ») —
    les édits/réordos/ajouts vivent dans l'état de la fenêtre jusque-là.
    ``result_layout()`` retourne la mise en page complète à réécrire dans
    l'onglet « Mise en page PANDORA ».

    ⚠ AUTO-SAVE : à CHAQUE modification (réécriture IA, édition manuelle, réordo,
    ajout, suppression), ``layout_committed(str)`` est émis → le parent réécrit et
    persiste la Mise en page en DIRECT. Plus aucune perte possible, même en fermant.
    Ctrl+Z / Ctrl+Y annulent / rétablissent.
    """

    # Émis à chaque modification de la mise en page → auto-save immédiat côté parent.
    layout_committed = pyqtSignal(str)

    def __init__(self, parent, layout_text: str,
                 edition: str = "cinema", mode: str = "live"):
        super().__init__(parent)
        self._edition = "cinema" if edition == "cinema" else "live"
        self._mode    = mode if mode in ("live", "mapping") else "live"
        self._layout  = layout_text or ""
        self._orig_layout = self._layout      # référence pour détecter les changements
        self._plans   = pl.split_plans(self._layout)
        self._cur     = 0
        self._applied = False
        self._worker  = None
        self._ref_images: list[str] = []
        self._histories: dict[int, list] = {}   # index → [{role, content}]
        self._undo_stack: list[str] = []        # annulation (Ctrl+Z) : layouts précédents
        self._redo_stack: list[str] = []        # rétablissement (Ctrl+Y)
        self._pending_plan = None               # index du plan envoyé à l'assistant
        self._suppress_commit = False           # bloque l'auto-commit pendant _set_preview
        # Mapping : la façade RÉELLE du bâtiment est jointe à l'assistant pour qu'il
        # respecte fenêtres/portes réelles au lieu d'en inventer.
        self._facade_path = ""
        if self._mode == "mapping":
            try:
                from core.live_building import get_building_ref
                self._facade_path = get_building_ref()
            except Exception:
                self._facade_path = ""

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
            self._btn_modify.setEnabled(False)
            self._btn_apply.setEnabled(False)

        try:
            from ui.widgets import disable_default_buttons
            disable_default_buttons(self)
        except Exception:
            pass

        # Annuler / Rétablir (Ctrl+Z / Ctrl+Y, ⌘Z / ⌘⇧Z sur Mac).
        QShortcut(QKeySequence.StandardKey.Undo, self, activated=self._undo)
        QShortcut(QKeySequence.StandardKey.Redo, self, activated=self._redo)

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
            "Réécris chaque plan avec l'assistant, réordonne, ajoute ou supprime. "
            "Tout s'enregistre AUTOMATIQUEMENT dans la mise en page (Ctrl+Z pour annuler)."))
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

        self._plan_list = _PlanListWidget()
        self._plan_list.setFixedHeight(150)
        self._plan_list.setStyleSheet(
            f"QListWidget{{background:{CP['bg2']};border:1px solid {CP['border']};"
            f"border-radius:8px;color:{CP['text_secondary']};font-size:11px;padding:4px;}}"
            f"QListWidget::item{{padding:5px 6px;border-radius:5px;}}"
            f"QListWidget::item:selected{{background:{CP['accent2']};color:#fff;}}"
            f"QListWidget::item:hover{{background:{CP['bg3']};}}")
        # Glisser-déposer pour réordonner (comme le storyboard) + menu clic droit
        # (ajouter / dupliquer / supprimer un plan).
        self._plan_list.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
        self._plan_list.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self._plan_list.setDefaultDropAction(Qt.DropAction.MoveAction)
        self._plan_list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._plan_list.customContextMenuRequested.connect(self._plan_context_menu)
        self._plan_list.reordered.connect(self._on_plans_reordered)
        self._plan_list.currentRowChanged.connect(self._on_row_changed)
        ll.addWidget(self._plan_list)

        _hint = QLabel(translate(
            "Glisse un plan pour le déplacer · clic droit : ajouter / dupliquer / supprimer"))
        _hint.setWordWrap(True)
        _hint.setStyleSheet(
            f"color:{CP['text_dim']};font-size:8px;background:transparent;")
        ll.addWidget(_hint)

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
        # Auto-save de l'édition MANUELLE : débounce ~600 ms (coalesce une rafale de
        # frappe en UN seul commit → un pas d'annulation par pause, pas par touche).
        self._preview_timer = QTimer(self)
        self._preview_timer.setSingleShot(True)
        self._preview_timer.setInterval(600)
        self._preview_timer.timeout.connect(self._commit_current_preview)
        self._plan_preview.textChanged.connect(self._on_preview_edited)
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

        # Bande d'images de référence (bibliothèque + fichier) — SCROLLABLE à
        # l'horizontale pour absorber jusqu'à _MAX_REFS vignettes sans déborder.
        self._refs_hbox = QHBoxLayout()
        self._refs_hbox.setSpacing(6)
        self._refs_hbox.setContentsMargins(0, 0, 0, 0)
        _refs_wrap = QWidget()
        _refs_wrap.setStyleSheet("background:transparent;")
        _refs_wrap.setLayout(self._refs_hbox)
        _refs_scroll = QScrollArea()
        _refs_scroll.setWidgetResizable(True)
        _refs_scroll.setWidget(_refs_wrap)
        _refs_scroll.setFixedHeight(58)
        _refs_scroll.setFrameShape(QFrame.Shape.NoFrame)
        _refs_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        _refs_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        _refs_scroll.setStyleSheet(
            "QScrollArea{background:transparent;border:none;}"
            f"QScrollBar:horizontal{{background:{CP['bg2']};height:7px;border-radius:3px;margin:0;}}"
            f"QScrollBar::handle:horizontal{{background:{CP['border_bright']};border-radius:3px;min-width:24px;}}"
            "QScrollBar::add-line:horizontal,QScrollBar::sub-line:horizontal{width:0;}")
        rl.addWidget(_refs_scroll)

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

        self._btn_send = QPushButton(translate("💬  Envoyer à l'assistant"))
        self._btn_send.setFixedHeight(38)
        self._btn_send.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_send.setStyleSheet(
            f"QPushButton{{background:{CP['accent2']};color:#fff;border:none;"
            f"border-radius:8px;font-size:11px;font-weight:700;padding:0 18px;}}"
            f"QPushButton:hover{{background:#9d8fff;}}"
            f"QPushButton:disabled{{background:{CP['bg3']};color:{CP['text_dim']};}}")
        self._btn_send.setToolTip(translate(
            "Discuter du plan avec l'assistant (conseils, idées) — SANS modifier le plan."))
        self._btn_send.clicked.connect(self._on_send)
        rl.addWidget(self._btn_send)

        # « Modifier le plan » : action DÉCIDÉE — l'assistant réécrit et applique.
        self._btn_modify = QPushButton(translate("✏️  Modifier le plan"))
        self._btn_modify.setFixedHeight(38)
        self._btn_modify.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_modify.setStyleSheet(
            f"QPushButton{{background:{CP['accent']};color:{CP['bg0']};border:none;"
            f"border-radius:8px;font-size:11px;font-weight:800;padding:0 18px;}}"
            f"QPushButton:hover{{background:{CP['accent_dim']};color:#fff;}}"
            f"QPushButton:disabled{{background:{CP['bg3']};color:{CP['text_dim']};}}")
        self._btn_modify.setToolTip(translate(
            "Appliquer une modification au plan : l'assistant le réécrit en tenant "
            "compte de la discussion."))
        self._btn_modify.clicked.connect(self._on_modify_plan)
        rl.addWidget(self._btn_modify)
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
        btn_close.clicked.connect(self._on_close_requested)

        self._btn_apply = QPushButton(translate("✓  Appliquer les modifications"))
        self._btn_apply.setFixedHeight(36)
        self._btn_apply.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_apply.setStyleSheet(
            f"QPushButton{{background:{CP['accent']};color:{CP['bg0']};border:none;"
            f"border-radius:7px;font-size:11px;font-weight:800;padding:0 22px;}}"
            f"QPushButton:hover{{background:{CP['accent_dim']};color:#fff;}}"
            f"QPushButton:disabled{{background:{CP['bg3']};color:{CP['text_dim']};}}")
        self._btn_apply.clicked.connect(self._on_apply_all)

        bottom.addWidget(btn_close)
        bottom.addStretch()
        bottom.addWidget(self._btn_apply)
        root.addLayout(bottom)

        self._refresh_refs_strip()

    # ── Sélection de plan ────────────────────────────────────────────────────
    def _reload_list(self):
        self._plan_list.blockSignals(True)
        self._plan_list.clear()
        for i, p in enumerate(self._plans):
            it = QListWidgetItem(p["label"], self._plan_list)
            it.setData(Qt.ItemDataRole.UserRole, i)   # index d'origine (glisser-déposer)
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

    def _on_row_changed(self, row: int):
        if row < 0 or row >= len(self._plans) or row == self._cur:
            return
        # Sauve l'édition manuelle du plan qu'on QUITTE dans la mise en page (état de
        # travail) — pour qu'« Appliquer les modifications » n'oublie AUCUN plan.
        self._commit_current_preview()
        self._cur = row
        self._set_preview(self._plans[row]["text"])
        self._render_chat()

    # ── Source de vérité unique + auto-save + annulation ─────────────────────
    def _commit_layout(self, new_layout: str, *, push_undo: bool = True, emit: bool = True):
        """SEUL point d'écriture dans self._layout (source de vérité). (a) empile
        l'ANCIEN layout pour l'annulation ; (b) met à jour layout + plans ; (c) émet
        ``layout_committed`` → le parent réécrit et PERSISTE la Mise en page en direct
        (auto-save). No-op si le layout n'a pas changé."""
        if new_layout == self._layout:
            return
        if push_undo:
            self._undo_stack.append(self._layout)
            if len(self._undo_stack) > 100:
                self._undo_stack.pop(0)
            self._redo_stack.clear()
        self._layout = new_layout
        self._plans = pl.split_plans(self._layout)
        if emit:
            self.layout_committed.emit(self._layout)

    def _ensure_plan_header(self, plan_text: str, index: int) -> str:
        """Garantit que ``plan_text`` commence par un en-tête de plan (« PLAN n » /
        « P0N »). Si l'IA l'a oublié, ré-applique l'en-tête d'origine du plan ``index``
        — sinon split_plans fusionnerait ce bloc au précédent et un plan disparaîtrait."""
        t = (plan_text or "").strip()
        if not t or pl.has_header(t):
            return t
        real = pl.split_plans(self._layout)
        if 0 <= index < len(real):
            first = real[index]["text"].strip().splitlines()
            if first and pl.has_header(first[0]):
                return first[0] + "\n" + t
        return t

    def _on_preview_edited(self):
        """Frappe manuelle dans l'aperçu → auto-commit débouncé (sauf pendant un
        remplissage programmatique via _set_preview)."""
        if self._suppress_commit:
            return
        self._preview_timer.start()

    def _commit_current_preview(self):
        """Réinjecte l'aperçu courant (édits manuels / proposition IA) dans la mise en
        page de travail via _commit_layout (auto-save immédiat), SANS changer la
        structure. No-op si rien n'a changé."""
        self._preview_timer.stop()
        if not self._plans or not (0 <= self._cur < len(self._plans)):
            return
        txt = self._plan_preview.toPlainText().strip()
        if not txt:
            return
        # Compare au bloc RÉEL de self._layout (pas à self._plans, qui a pu être muté).
        real = pl.split_plans(self._layout)
        if self._cur < len(real) and txt == real[self._cur]["text"].strip():
            return
        txt = self._ensure_plan_header(txt, self._cur)
        self._commit_layout(pl.replace_plan(self._layout, self._cur, txt))

    def _set_preview(self, text: str):
        """Écrit l'aperçu du plan avec une RESPIRATION entre les paragraphes (comme la
        Mise en page PANDORA) : chaque ligne (Durée, PROMPT VIDÉO, PROMPT SON…) est
        séparée pour une lecture facile — plus de bloc compact illisible."""
        # Remplissage PROGRAMMATIQUE : ne pas déclencher l'auto-commit débouncé.
        self._suppress_commit = True
        try:
            self._plan_preview.setPlainText(text)
            try:
                from ui.widgets import apply_paragraph_spacing
                apply_paragraph_spacing(self._plan_preview, px=10)
            except Exception:
                pass
        finally:
            self._suppress_commit = False

    # ── Réordonner (glisser-déposer) / menu clic droit (ajout/dup/suppr) ──────
    def _structural_change(self, new_layout: str, select_index: int):
        """Applique un changement STRUCTUREL (ordre / ajout / dup / suppression) à l'état
        de TRAVAIL : met à jour la mise en page, re-parse et sélectionne le plan voulu.
        Ne marque PAS « appliqué » — seul « Appliquer les modifications » valide et écrit
        dans la « Mise en page PANDORA ». Le chat par plan est réinitialisé (index changés)."""
        self._commit_layout(new_layout)   # écrit + empile undo + auto-save parent
        self._histories.clear()
        if not self._plans:
            self._plan_list.clear()
            self._set_preview("")
            self._count_lbl.setText(translate("{n} plan(s)").format(n=0))
            # Plus aucun plan : désactive Envoyer/Appliquer (évite d'appliquer du vide).
            for w in (getattr(self, "_input", None), getattr(self, "_btn_send", None),
                      getattr(self, "_btn_apply", None)):
                if w is not None:
                    w.setEnabled(False)
            return
        # Réactive la saisie si on repart d'un état « aucun plan ».
        for w in (getattr(self, "_input", None), getattr(self, "_btn_send", None),
                  getattr(self, "_btn_modify", None), getattr(self, "_btn_apply", None)):
            if w is not None:
                w.setEnabled(True)
        self._plan_preview.setReadOnly(False)
        self._select_plan(max(0, min(select_index, len(self._plans) - 1)))

    def _on_plans_reordered(self):
        """Après un glisser-déposer : recompose la mise en page selon le nouvel ordre
        visuel (index d'origine stockés en UserRole), renumérote, resélectionne."""
        self._commit_current_preview()   # ne pas perdre l'édition en cours
        order = []
        for i in range(self._plan_list.count()):
            d = self._plan_list.item(i).data(Qt.ItemDataRole.UserRole)
            if d is not None:
                order.append(int(d))
        if sorted(order) != list(range(len(self._plans))):
            return   # ordre incohérent → on ne touche à rien
        new_row = max(0, self._plan_list.currentRow())
        self._structural_change(pl.reorder(self._layout, order), new_row)
        self._status.setText(translate("Plan déplacé ✓"))

    def _plan_context_menu(self, pos):
        """Clic droit : sur un plan → dupliquer / supprimer ; dans le vide → ajouter."""
        item = self._plan_list.itemAt(pos)
        menu = QMenu(self)
        if item is not None:
            row = self._plan_list.row(item)
            menu.addAction(translate("Dupliquer ce plan"), lambda: self._duplicate_plan(row))
            menu.addSeparator()
            menu.addAction(translate("Supprimer ce plan"), lambda: self._delete_plan_at(row))
        else:
            menu.addAction(translate("＋  Ajouter un plan"), self._add_plan)
        menu.exec(self._plan_list.mapToGlobal(pos))

    def _add_plan(self):
        self._commit_current_preview()   # flush l'aperçu AVANT de re-structurer (anti-perte)
        idx = self._cur if self._plans else -1
        self._structural_change(pl.add_plan(self._layout, idx, self._edition),
                                (idx + 1) if self._plans else 0)
        self._status.setText(translate("Plan ajouté ✓"))

    def _duplicate_plan(self, row: int):
        if not (0 <= row < len(self._plans)):
            return
        self._commit_current_preview()   # flush l'aperçu AVANT de re-structurer (anti-perte)
        self._structural_change(pl.duplicate_plan(self._layout, row), row + 1)
        self._status.setText(translate("Plan dupliqué ✓"))

    def _delete_plan_at(self, row: int):
        if not (0 <= row < len(self._plans)):
            return
        self._commit_current_preview()   # flush l'aperçu AVANT de re-structurer (anti-perte)
        self._structural_change(pl.delete_plan(self._layout, row),
                                min(row, len(self._plans) - 2))
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
        """« Envoyer à l'assistant » : DISCUSSION seule — l'assistant conseille sans
        modifier le plan. On applique ensuite via « Modifier le plan »."""
        msg = self._input.toPlainText().strip()
        if not msg:
            return
        self._launch(msg, discuss_only=True)

    def _on_modify_plan(self):
        """« Modifier le plan » : l'assistant réécrit le plan (en tenant compte de la
        discussion) et la modification est appliquée (auto-save). Sans consigne saisie,
        applique ce qui vient d'être discuté."""
        msg = self._input.toPlainText().strip() or translate(
            "Réécris le plan en appliquant ce qu'on vient de discuter.")
        self._launch(msg, discuss_only=False)

    def _launch(self, msg: str, discuss_only: bool):
        if not self._plans:
            return
        if self._worker and self._worker.isRunning():
            return
        # Le plan courant part de l'aperçu (édits manuels pris en compte) — committé
        # d'abord (auto-save). En MODIFICATION, on retient le plan cible (course worker).
        cur_plan = self._plan_preview.toPlainText().strip()
        self._commit_current_preview()
        self._pending_plan = None if discuss_only else self._cur
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
            facade_path=self._facade_path,
            discuss_only=discuss_only,
        )
        self._worker.message_ready.connect(self._on_message_ready)
        self._worker.plan_ready.connect(self._on_plan_ready)   # non émis en discussion
        self._worker.failed.connect(self._on_failed)
        # Signal NATIF QThread : réactive l'UI dès la fin de run() (indispensable en
        # DISCUSSION où aucun plan_ready ne vient lever le « busy »).
        self._worker.finished.connect(self._on_worker_finished)
        self._worker.start()

    def _on_message_ready(self, reply: str):
        self._histories.setdefault(self._cur, []).append(
            {"role": "assistant", "content": reply})
        self._render_chat()

    def _on_plan_ready(self, plan: str):
        self._set_busy(False)
        plan = (plan or "").strip()
        # Le rewrite est rattaché au plan ENVOYÉ (pas au plan actuellement affiché —
        # l'utilisateur a pu naviguer pendant la rédaction).
        target = self._pending_plan if self._pending_plan is not None else self._cur
        self._pending_plan = None
        if not plan or not self._plans or not (0 <= target < len(self._plans)):
            return
        # Le chat a-t-il créé un/des NOUVEAUX plans (plusieurs blocs) ? → splice + renum
        # de toute la mise en page (décale les plans suivants), changement structurel.
        if pl.plan_count(plan) > 1:
            new_layout = pl.replace_plan_multi(self._layout, target, plan)
            if new_layout != self._layout:
                self._structural_change(new_layout, target)
                self._status.setText(translate(
                    "Nouveau(x) plan(s) créé(s) — plans renumérotés. "
                    "Relis, ajuste, puis « Appliquer les modifications »."))
            return
        # Plan unique : garantir l'en-tête (sinon fusion → plan perdu).
        plan = self._ensure_plan_header(plan, target)
        if target == self._cur:
            # Le plan affiché est bien celui envoyé → aperçu + commit (auto-save).
            self._set_preview(plan)
            self._commit_current_preview()
            self._status.setText(translate("Plan modifié ✓ (enregistré automatiquement)"))
        else:
            # L'utilisateur a changé de plan pendant la rédaction : écris DIRECTEMENT
            # dans le plan cible, sans toucher l'aperçu courant (anti-corruption).
            self._commit_layout(pl.replace_plan(self._layout, target, plan))
            self._status.setText(translate("Plan {n} mis à jour ✓").format(n=target + 1))

    def _on_failed(self, err: str):
        self._set_busy(False)
        self._status.setText("⚠ " + str(err)[:200])

    def _set_busy(self, busy: bool):
        self._btn_send.setEnabled(not busy)
        if hasattr(self, "_btn_modify"):
            self._btn_modify.setEnabled(not busy)
        self._input.setEnabled(not busy)
        if busy:
            self._status.setText(translate("Rédaction en cours…"))
        elif self._status.text() == translate("Rédaction en cours…"):
            # Ne pas effacer un statut utile déjà posé (ex. « Plan modifié ✓ »).
            self._status.setText("")

    def _on_worker_finished(self):
        """Filet de sécurité : la FIN du worker (discussion, modification OU réponse
        vide) réactive TOUJOURS l'UI. En DISCUSSION le worker n'émet que message_ready
        (pas plan_ready) — sans ce filet, « Rédaction en cours » resterait bloqué."""
        self._set_busy(False)

    # ── Annuler / Rétablir (Ctrl+Z / Ctrl+Y) ─────────────────────────────────
    def _undo(self):
        """Ctrl+Z : revient à l'état précédent (annule la dernière modification —
        réécriture IA, édition, réordo, ajout, suppression). Ré-émet vers le parent."""
        self._commit_current_preview()   # fige l'édition en cours pour qu'elle soit annulable
        if not self._undo_stack:
            self._status.setText(translate("Rien à annuler"))
            return
        if self._worker is not None and self._worker.isRunning():
            try:
                abandon_thread(self._worker)
            except Exception:
                pass
            self._worker = None
            self._set_busy(False)
        self._pending_plan = None
        self._redo_stack.append(self._layout)
        self._apply_history_state(self._undo_stack.pop())
        self._status.setText(translate("Annulé ✓ (Ctrl+Y pour rétablir)"))

    def _redo(self):
        """Ctrl+Y : rétablit la modification annulée."""
        if not self._redo_stack:
            self._status.setText(translate("Rien à rétablir"))
            return
        self._undo_stack.append(self._layout)
        self._apply_history_state(self._redo_stack.pop())
        self._status.setText(translate("Rétabli ✓"))

    def _apply_history_state(self, layout_text: str):
        """Restaure un layout depuis l'historique : met à jour l'état, ré-émet vers le
        parent (auto-save) SANS re-empiler d'annulation, et rafraîchit la vue."""
        self._layout = layout_text
        self._plans = pl.split_plans(self._layout)
        self._histories.clear()
        self.layout_committed.emit(self._layout)   # le parent se réaligne
        if not self._plans:
            self._plan_list.clear()
            self._set_preview("")
            self._count_lbl.setText(translate("{n} plan(s)").format(n=0))
            for w in (self._input, self._btn_send, self._btn_modify, self._btn_apply):
                w.setEnabled(False)
            return
        for w in (self._input, self._btn_send, self._btn_apply):
            w.setEnabled(True)
        self._plan_preview.setReadOnly(False)
        self._select_plan(max(0, min(self._cur, len(self._plans) - 1)))

    # ── Application globale ──────────────────────────────────────────────────
    def _on_apply_all(self):
        """Applique TOUTES les modifications (édits de chaque plan + réordos + ajouts +
        suppressions) à la « Mise en page PANDORA » en une fois, puis ferme."""
        self._commit_current_preview()   # n'oublie pas l'édition du plan affiché
        self._applied = True
        self.accept()

    def _has_pending(self) -> bool:
        """Y a-t-il des modifications non encore validées ? (structure/ordre changés,
        ou édition manuelle en cours dans l'aperçu)."""
        if self._layout != self._orig_layout:
            return True
        if self._plans and 0 <= self._cur < len(self._plans):
            cur = self._plan_preview.toPlainText().strip()
            if cur and cur != self._plans[self._cur]["text"].strip():
                return True
        return False

    def _on_close_requested(self):
        """« Fermer » : ferme la fenêtre. AUCUNE perte possible — chaque modification a
        déjà été enregistrée automatiquement dans la « Mise en page PANDORA » (auto-save).
        On fige juste l'édition en cours par sécurité avant de fermer."""
        self._commit_current_preview()
        self.reject()

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
        btn_add.setToolTip(translate(
            "Ajouter des images d'inspiration (bibliothèque ou fichier, max {n})").format(n=_MAX_REFS))
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
        # Pas de addStretch() : la largeur du ruban = celle de ses vignettes → la
        # QScrollArea peut défiler horizontalement au-delà de la largeur du panneau.

    # ── Résultat ─────────────────────────────────────────────────────────────
    def was_applied(self) -> bool:
        return self._applied

    def result_layout(self) -> str:
        return self._layout

    def closeEvent(self, ev):
        # Fermeture par la croix : fige l'édition en cours (auto-save) — jamais de perte.
        try:
            self._commit_current_preview()
        except Exception:
            pass
        if self._worker is not None:
            try:
                abandon_thread(self._worker)
            except Exception:
                pass
        super().closeEvent(ev)


def _esc(s: str) -> str:
    return (str(s).replace("&", "&amp;").replace("<", "&lt;")
            .replace(">", "&gt;").replace("\n", "<br>"))
