import os
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QSizePolicy,
    QScrollArea, QFrame, QMessageBox, QProgressBar, QDialog,
    QComboBox, QLineEdit, QMenu, QInputDialog, QTextEdit, QCheckBox,
    QListWidget, QListWidgetItem, QScrollBar,
)
from PyQt6.QtCore import Qt, pyqtSignal, QObject, QTimer
from PyQt6.QtGui import QPixmap
from ui.styles import CP
from ui.widgets import HelpBlock
from ui.icons import load_icon, claude_icon_pixmap
import core.storyboard as sb_api
import core.decors as dec_api
import core.casting as casting_api
import core.accessories as acc_api
from core.storyboard import (
    DEFAULT_VERSION_ID,
    CAMERA_MOVEMENTS, SPEEDS, SHOT_SIZES, SHOT_SIZE_LABELS, FOCALS, DISTANCES, HEURE_PRESETS,
)
from core.worker import abandon_thread
from ui.dialog_shot_live import ShotDialog
from core.i18n import translate


def _sep():
    f = QFrame()
    f.setFixedHeight(1)
    f.setStyleSheet(f"background:{CP['border']};")
    return f


# ── Table columns definition ──────────────────────────────────────────────────
# (header_text, fixed_width, is_stretch)
_COLS = [
    ("",              22,  False),  # 0  Drag grip
    ("Mood",          92,  False),  # 1  mood/aperçu storyboard
    ("Acte",          78,  False),  # 2  seq_num / seq_name (acte du conducteur)
    ("Plan",          52,  False),  # 3
    ("Prompt vidéo / son", 300, False),  # 4  seedance_prompt + sound_prompt
    ("Axe Caméra",    120, False),  # 5  camera_axis + chars_in + chars_out
    ("Mouvement",     96,  False),  # 6
    ("Valeur",        72,  False),  # 7  Shot size
    ("Focal",         72,  False),  # 8
    ("Dist.",         64,  False),  # 9  camera_distance
    ("Vitesse",       74,  False),  # 10
    ("Décor",        152,  False),  # 11
    ("Heure",         96,  False),  # 12
    ("Accessoires",  102,  False),  # 13
    ("Acteurs",       96,  False),  # 14
    ("Durée",         52,  False),  # 15
    ("TC",            68,  False),  # 16 timecode de début (calculé)
    ("Musique",      120,  False),  # 17 music_track (depuis « Musiques du set »)
    ("BPM",           52,  False),  # 18 dérivé du morceau assigné
    ("Transition",    96,  False),  # 19 transition
    ("Notes / Repère", 150, False), # 20 cue_note
    ("",              78,  False),  # 21 Boutons
]

_HEURE_PRESETS = HEURE_PRESETS

# Mutable column widths — shared by header and all rows; updated on drag-resize
_col_widths: list[int] = [w for _, w, _ in _COLS]

# Mutable column visual order — list of logical column indices in left→right display order.
# Indices 0 (grip) and 16 (buttons) always stay at first/last; the rest are reorderable.
# Loaded from project config in PageStoryboard._render().
_col_order: list[int] = list(range(len(_COLS)))

# Colonnes masquées pour la page courante (Mapping en masque plusieurs).
# Défini par PageStoryboard._render() selon le mode (via self._hidden_cols).
_HIDDEN_COLS: set = set()


def _visible_order() -> list:
    """Ordre d'affichage des colonnes, en retirant celles masquées (par mode)."""
    return [c for c in _col_order if c not in _HIDDEN_COLS]


class _ColHub(QObject):
    resized   = pyqtSignal(int, int)   # (col_index, new_width)
    reordered = pyqtSignal(list)        # new _col_order


_col_hub = _ColHub()


# Sequence color palette — (row_bg, seq_cell_bg, seq_text_color)
_SEQ_PALETTE = [
    ("rgba(100,105,115,0.14)", "rgba(140,145,155,0.32)", "#a0a4b0"),  # neutral
    ("rgba(255,79,106,0.10)",  "rgba(255,79,106,0.36)",  "#ff8fa0"),  # rose
    ("rgba(78,205,196,0.08)",  "rgba(78,205,196,0.33)",  "#4ecdc4"),  # teal
    ("rgba(124,107,255,0.09)", "rgba(124,107,255,0.35)", "#a090ff"),  # violet
    ("rgba(255,180,50,0.09)",  "rgba(255,180,50,0.35)",  "#ffc040"),  # amber
    ("rgba(50,200,100,0.08)",  "rgba(50,200,100,0.33)",  "#50c864"),  # green
    ("rgba(255,120,60,0.09)",  "rgba(255,120,60,0.35)",  "#ff9060"),  # orange
]


# ── Dialogue helpers ──────────────────────────────────────────────────────────

def _text_dialog(parent: QWidget, title: str, initial: str = "",
                 placeholder: str = "", enhance: bool = False) -> str | None:
    """Styled multi-line text editor dialog. Returns new text or None if cancelled."""
    from ui.styles import PANDORA_STYLESHEET
    dlg = QDialog(parent)
    dlg.setWindowTitle(title)
    dlg.setMinimumSize(540, 240)
    dlg.setStyleSheet(PANDORA_STYLESHEET + f"QDialog{{background:{CP['bg1']};}}")

    lay = QVBoxLayout(dlg)
    lay.setContentsMargins(20, 18, 20, 18)
    lay.setSpacing(12)

    te = QTextEdit()
    te.setPlainText(initial or "")
    if placeholder:
        te.setPlaceholderText(placeholder)
    te.setStyleSheet(
        f"QTextEdit{{background:{CP['bg3']};border:1px solid {CP['border']};"
        f"border-radius:6px;color:{CP['text_primary']};font-size:12px;padding:8px;}}"
        f"QTextEdit:focus{{border-color:{CP['accent']};}}"
    )
    lay.addWidget(te, 1)

    btn_row = QHBoxLayout()

    if False:   # bouton « ✦ Améliorer » RETIRÉ (fonction instable) — param `enhance` ignoré
        from PyQt6.QtGui import QIcon
        _wh = [None, None]  # [0]=worker, [1]=dialog-ref to prevent GC while worker runs

        btn_claude = QPushButton("✦  Améliorer")
        btn_claude.setFixedHeight(34)
        pix = claude_icon_pixmap(15)
        if pix and not pix.isNull():
            btn_claude.setIcon(QIcon(pix))
        btn_claude.setStyleSheet(
            f"QPushButton{{background:transparent;color:{CP['accent']};"
            f"border:1px solid {CP['accent']};border-radius:8px;"
            f"font-size:11px;font-weight:700;padding:0 14px;}}"
            f"QPushButton:hover{{background:rgba(78,205,196,0.12);}}"
            f"QPushButton:disabled{{color:{CP['text_dim']};border-color:{CP['border']};}}"
        )

        def _on_enhance():
            text = te.toPlainText().strip()
            if not text:
                return
            from api.enhance import EnhanceWorker
            w = EnhanceWorker(text)
            _wh[0] = w
            _wh[1] = dlg  # keep dialog alive in Python until worker finishes
            btn_claude.setEnabled(False)
            btn_claude.setText("En cours…")

            def _done(result: str):
                try:
                    te.setPlainText(result)
                    btn_claude.setEnabled(True)
                    btn_claude.setText("✦  Améliorer")
                except RuntimeError:
                    pass  # dialog was closed before worker finished
                _wh[0] = None
                _wh[1] = None

            def _fail(_err: str):
                try:
                    btn_claude.setEnabled(True)
                    btn_claude.setText("✦  Améliorer")
                except RuntimeError:
                    pass
                _wh[0] = None
                _wh[1] = None

            w.finished.connect(_done)
            w.failed.connect(_fail)
            w.start()

        btn_claude.clicked.connect(_on_enhance)
        btn_row.addWidget(btn_claude)

    btn_row.addStretch()

    btn_cancel = QPushButton(translate("Annuler"))
    btn_cancel.setFixedHeight(34)
    btn_cancel.setStyleSheet(
        f"QPushButton{{background:transparent;color:{CP['text_secondary']};"
        f"border:1px solid {CP['border']};border-radius:8px;"
        f"font-size:11px;font-weight:700;padding:0 14px;}}"
        f"QPushButton:hover{{background:{CP['bg3']};}}"
    )
    btn_cancel.clicked.connect(dlg.reject)

    btn_ok = QPushButton(translate("Valider"))
    btn_ok.setFixedHeight(34)
    btn_ok.setStyleSheet(
        f"QPushButton{{background:{CP['accent']};color:#07080f;"
        f"border:none;border-radius:8px;"
        f"font-size:11px;font-weight:700;padding:0 14px;}}"
        f"QPushButton:hover{{background:#6eded6;}}"
    )
    btn_ok.clicked.connect(dlg.accept)

    btn_row.addWidget(btn_cancel)
    btn_row.addSpacing(8)
    btn_row.addWidget(btn_ok)
    lay.addLayout(btn_row)

    if dlg.exec() == QDialog.DialogCode.Accepted:
        return te.toPlainText().strip()
    return None


def _decor_picker_dialog(parent: QWidget, current_decor_id: str) -> dict | None:
    """Shows a list of available decors with thumbnails. Returns chosen decor dict or None."""
    from ui.styles import PANDORA_STYLESHEET
    decors = dec_api.list_decors()

    dlg = QDialog(parent)
    dlg.setWindowTitle(translate("Choisir un décor"))
    dlg.setFixedSize(480, 440)
    dlg.setStyleSheet(PANDORA_STYLESHEET + f"QDialog{{background:{CP['bg1']};}}")

    lay = QVBoxLayout(dlg)
    lay.setContentsMargins(16, 14, 16, 14)
    lay.setSpacing(10)

    hdr = QLabel(translate("Sélectionner un décor"))
    hdr.setStyleSheet(
        f"color:{CP['text_primary']};font-size:14px;font-weight:700;background:transparent;"
    )
    lay.addWidget(hdr)

    scroll = QScrollArea()
    scroll.setWidgetResizable(True)
    scroll.setStyleSheet("QScrollArea{background:transparent;border:none;}")
    inner = QWidget()
    inner.setStyleSheet("background:transparent;")
    inner_lay = QVBoxLayout(inner)
    inner_lay.setSpacing(6)
    inner_lay.setContentsMargins(0, 0, 0, 0)

    selected_box = [None]

    if not decors:
        lbl = QLabel(translate("Aucun décor créé dans ce projet."))
        lbl.setStyleSheet(f"color:{CP['text_dim']};font-size:12px;background:transparent;")
        inner_lay.addWidget(lbl)
    else:
        for decor in decors:
            is_active = decor.get("id") == current_decor_id
            card = QFrame()
            card.setFixedHeight(58)
            card.setCursor(Qt.CursorShape.PointingHandCursor)
            card.setStyleSheet(
                f"QFrame{{background:{'rgba(78,205,196,0.14)' if is_active else CP['bg2']};"
                f"border:1px solid {CP['accent'] if is_active else CP['border']};"
                f"border-radius:8px;}}"
                f"QFrame:hover{{background:{CP['bg3']};border-color:{CP['accent_dim']};}}"
            )
            card_lay = QHBoxLayout(card)
            card_lay.setContentsMargins(8, 6, 12, 6)
            card_lay.setSpacing(10)

            thumb = QLabel()
            thumb.setFixedSize(40, 34)
            d_img = decor.get("image_path", "")
            if d_img and os.path.isfile(d_img):
                pix = QPixmap(d_img).scaled(
                    40, 34, Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                    Qt.TransformationMode.SmoothTransformation,
                )
                pix = pix.copy((pix.width()-40)//2, (pix.height()-34)//2, 40, 34)
                thumb.setPixmap(pix)
                thumb.setStyleSheet("border-radius:4px;")
            else:
                thumb.setStyleSheet(
                    f"background:{CP['bg3']};border-radius:4px;border:none;"
                    f"color:{CP['text_dim']};font-size:16px;"
                )
                thumb.setAlignment(Qt.AlignmentFlag.AlignCenter)
                thumb.setText("◻")
            card_lay.addWidget(thumb)

            name_lbl = QLabel(decor.get("name", ""))
            name_lbl.setStyleSheet(
                f"color:{CP['text_primary']};font-size:12px;font-weight:600;"
                f"background:transparent;border:none;"
            )
            card_lay.addWidget(name_lbl, 1)

            if is_active:
                chk = QLabel("✓")
                chk.setStyleSheet(f"color:{CP['accent']};font-size:14px;font-weight:700;background:transparent;border:none;")
                card_lay.addWidget(chk)

            def _on_click(_, d=decor, sb=selected_box, dlg_ref=dlg):
                sb[0] = d
                dlg_ref.accept()

            card.mousePressEvent = _on_click
            inner_lay.addWidget(card)

    inner_lay.addStretch()
    scroll.setWidget(inner)
    lay.addWidget(scroll, 1)

    btn_cancel = QPushButton(translate("Annuler"))
    btn_cancel.setFixedHeight(34)
    btn_cancel.setStyleSheet(
        f"QPushButton{{background:transparent;color:{CP['text_secondary']};"
        f"border:1px solid {CP['border']};border-radius:8px;"
        f"font-size:11px;font-weight:700;padding:0 14px;}}"
        f"QPushButton:hover{{background:{CP['bg3']};}}"
    )
    btn_cancel.clicked.connect(dlg.reject)
    lay.addWidget(btn_cancel, alignment=Qt.AlignmentFlag.AlignRight)

    if dlg.exec() == QDialog.DialogCode.Accepted:
        return selected_box[0]
    return None


def _elements_picker_dialog(parent: QWidget, title: str,
                             items: list[dict], selected_ids: list[str]) -> tuple | None:
    """Multi-select picker with checkboxes. Returns (ids, names) or None if cancelled."""
    from ui.styles import PANDORA_STYLESHEET

    dlg = QDialog(parent)
    dlg.setWindowTitle(translate(title))
    dlg.setFixedSize(380, 420)
    dlg.setStyleSheet(PANDORA_STYLESHEET + f"QDialog{{background:{CP['bg1']};}}")

    lay = QVBoxLayout(dlg)
    lay.setContentsMargins(20, 16, 20, 16)
    lay.setSpacing(10)

    hdr = QLabel(title)
    hdr.setStyleSheet(
        f"color:{CP['text_primary']};font-size:14px;font-weight:700;background:transparent;"
    )
    lay.addWidget(hdr)

    lst = QListWidget()
    lst.setStyleSheet(
        f"QListWidget{{background:{CP['bg2']};border:1px solid {CP['border']};"
        f"border-radius:8px;color:{CP['text_primary']};font-size:12px;padding:4px;}}"
        f"QListWidget::item{{padding:6px 10px;border-radius:4px;}}"
        f"QListWidget::item:selected{{background:transparent;}}"
    )

    for item in items:
        li = QListWidgetItem(item.get("name", ""))
        li.setData(Qt.ItemDataRole.UserRole, item)
        li.setFlags(li.flags() | Qt.ItemFlag.ItemIsUserCheckable)
        li.setCheckState(
            Qt.CheckState.Checked if item.get("id", "") in selected_ids
            else Qt.CheckState.Unchecked
        )
        lst.addItem(li)

    if not items:
        li = QListWidgetItem(translate("Aucun élément disponible."))
        li.setFlags(Qt.ItemFlag.NoItemFlags)
        lst.addItem(li)

    lay.addWidget(lst, 1)

    btn_row = QHBoxLayout()
    btn_cancel = QPushButton(translate("Annuler"))
    btn_cancel.setFixedHeight(34)
    btn_cancel.setStyleSheet(
        f"QPushButton{{background:transparent;color:{CP['text_secondary']};"
        f"border:1px solid {CP['border']};border-radius:8px;"
        f"font-size:11px;font-weight:700;padding:0 14px;}}"
        f"QPushButton:hover{{background:{CP['bg3']};}}"
    )
    btn_cancel.clicked.connect(dlg.reject)

    btn_ok = QPushButton(translate("Valider"))
    btn_ok.setFixedHeight(34)
    btn_ok.setStyleSheet(
        f"QPushButton{{background:{CP['accent']};color:#07080f;"
        f"border:none;border-radius:8px;"
        f"font-size:11px;font-weight:700;padding:0 14px;}}"
        f"QPushButton:hover{{background:#6eded6;}}"
    )
    btn_ok.clicked.connect(dlg.accept)

    btn_row.addStretch()
    btn_row.addWidget(btn_cancel)
    btn_row.addSpacing(8)
    btn_row.addWidget(btn_ok)
    lay.addLayout(btn_row)

    if dlg.exec() == QDialog.DialogCode.Accepted:
        ids, names = [], []
        for i in range(lst.count()):
            li = lst.item(i)
            if li and li.checkState() == Qt.CheckState.Checked:
                d = li.data(Qt.ItemDataRole.UserRole)
                if d:
                    ids.append(d.get("id", ""))
                    names.append(d.get("name", ""))
        return ids, names
    return None


# ── En-tête de tableau redimensionnable ──────────────────────────────────────

class _ResizableHeader(QWidget):
    """Table header with drag-to-resize column handles (like Excel)."""

    def __init__(self):
        super().__init__()
        self.setFixedHeight(30)
        self.setMouseTracking(True)
        self.setStyleSheet(
            f"background:{CP['bg1']};border-bottom:2px solid {CP['border_bright']};"
        )
        self._cells: list[QWidget] = []         # visual order
        self._cell_logical: list[int] = []      # _cell_logical[visual_pos] = logical_col_idx
        self._drag_col: int | None = None
        self._drag_start_x: int = 0
        self._drag_start_w: int = 0
        self._reorder_vis    = None   # visual position being dragged (for reorder)
        self._reorder_target = None   # visual insertion position

        self._lay = QHBoxLayout(self)
        self._lay.setContentsMargins(0, 0, 0, 0)
        self._lay.setSpacing(0)

        self._indicator = QWidget(self)
        self._indicator.setFixedWidth(3)
        self._indicator.setStyleSheet(f"background:{CP['accent']};border-radius:1px;")
        self._indicator.hide()

        self._build_cells()

    def _build_cells(self):
        while self._lay.count():
            item = self._lay.takeAt(0)
            if item.widget():
                item.widget().setParent(None)
        self._cells = []
        self._cell_logical = []

        _vis = _visible_order()
        for i, col_logical in enumerate(_vis):
            title, _, _ = _COLS[col_logical]
            w = _col_widths[col_logical]
            cell = QWidget()
            cell.setStyleSheet("background:transparent;")
            cell.setFixedWidth(w)
            cl = QHBoxLayout(cell)
            cl.setContentsMargins(7, 0, 4, 0)
            if title:
                lbl = QLabel(translate(title).upper())
                lbl.setStyleSheet(
                    f"color:{CP['text_dim']};font-size:8px;font-weight:700;"
                    f"letter-spacing:1.5px;font-family:'Consolas',monospace;"
                    f"background:transparent;"
                )
                cl.addWidget(lbl)
            self._cells.append(cell)
            self._cell_logical.append(col_logical)
            self._lay.addWidget(cell)
            if i < len(_vis) - 1:
                s = QWidget()
                s.setFixedWidth(1)
                s.setStyleSheet(f"background:{CP['border']};")
                self._lay.addWidget(s)
        self._lay.addStretch()

    def _col_at(self, x: int) -> int | None:
        """Returns the LOGICAL column index whose right edge is within ±5 px of x."""
        for vis_pos, cell in enumerate(self._cells):
            logical = self._cell_logical[vis_pos]
            if logical == 0 or logical == len(_COLS) - 1:
                continue  # grip and buttons not resizable
            right = cell.geometry().right()
            if abs(x - right) <= 5:
                return logical
        return None

    def _visual_pos_at(self, x: int) -> int | None:
        """Returns the visual position of the cell under x."""
        for vis_pos, cell in enumerate(self._cells):
            if cell.geometry().left() <= x <= cell.geometry().right():
                return vis_pos
        return None

    def mousePressEvent(self, e):
        if e.button() != Qt.MouseButton.LeftButton:
            return
        col_logical = self._col_at(e.pos().x())
        if col_logical is not None:
            # Near right edge → resize
            self._drag_col = col_logical
            self._drag_start_x = e.pos().x()
            self._drag_start_w = _col_widths[col_logical]
            self.grabMouse()
            self.setCursor(Qt.CursorShape.SizeHorCursor)
        else:
            # Center of cell → start possible reorder
            vis_pos = self._visual_pos_at(e.pos().x())
            if vis_pos is not None and self._cell_logical[vis_pos] not in (0, len(_COLS) - 1):
                self._reorder_vis = vis_pos
                self._reorder_target = vis_pos
                self._drag_start_x = e.pos().x()
                self.setCursor(Qt.CursorShape.SizeHorCursor)
        e.accept()

    def mouseMoveEvent(self, e):
        x = e.pos().x()
        if self._drag_col is not None and (e.buttons() & Qt.MouseButton.LeftButton):
            # Resize
            delta = x - self._drag_start_x
            new_w = max(36, self._drag_start_w + delta)
            _col_widths[self._drag_col] = new_w
            # find visual cell for this logical col
            for vis_pos, logical in enumerate(self._cell_logical):
                if logical == self._drag_col:
                    self._cells[vis_pos].setFixedWidth(new_w)
                    break
            _col_hub.resized.emit(self._drag_col, new_w)
            e.accept()
        elif self._reorder_vis is not None and (e.buttons() & Qt.MouseButton.LeftButton):
            # Reorder drag
            vis_target = self._visual_pos_at(x)
            if vis_target is not None and self._cell_logical[vis_target] not in (0, len(_COLS) - 1):
                self._reorder_target = vis_target
                # Show indicator at the left edge of target cell
                cell = self._cells[vis_target]
                ind_x = cell.geometry().left() - 1
                self._indicator.setGeometry(ind_x, 0, 3, self.height())
                self._indicator.show()
                self._indicator.raise_()
            e.accept()
        else:
            # Hover: show resize cursor near edges
            if self._col_at(x) is not None:
                self.setCursor(Qt.CursorShape.SizeHorCursor)
            elif self._visual_pos_at(x) is not None:
                self.setCursor(Qt.CursorShape.OpenHandCursor)
            else:
                self.setCursor(Qt.CursorShape.ArrowCursor)

    def mouseReleaseEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            if self._drag_col is not None:
                self._drag_col = None
                self.releaseMouse()
                self.setCursor(Qt.CursorShape.ArrowCursor)
            elif self._reorder_vis is not None:
                self._indicator.hide()
                src = self._reorder_vis
                tgt = self._reorder_target
                if tgt is not None and src != tgt:
                    # src/tgt sont des positions VISUELLES ; _col_order est LOGIQUE
                    # (et contient aussi les colonnes masquées) → on mappe via
                    # _cell_logical, sinon le drag déplace la mauvaise colonne
                    # dès qu'une colonne est masquée (Mapping).
                    src_logical = self._cell_logical[src]
                    tgt_logical = self._cell_logical[tgt]
                    new_order = list(_col_order)
                    new_order.remove(src_logical)
                    insert_at = new_order.index(tgt_logical)
                    if tgt > src:
                        insert_at += 1   # déposé À DROITE de la cible
                    new_order.insert(insert_at, src_logical)
                    _col_order[:] = new_order
                    _col_hub.reordered.emit(new_order)
                self._reorder_vis = None
                self._reorder_target = None
                self.setCursor(Qt.CursorShape.ArrowCursor)


# ── Label avec hauteur adaptative pour word-wrap dans HBoxLayout ─────────────

class _WrapLabel(QLabel):
    """QLabel that correctly propagates heightForWidth so word-wrap rows expand."""

    def hasHeightForWidth(self) -> bool:
        return True

    def heightForWidth(self, w: int) -> int:
        fm = self.fontMetrics()
        rect = fm.boundingRect(
            0, 0, max(w - 2, 1), 10000,
            int(Qt.TextFlag.TextWordWrap) | int(Qt.AlignmentFlag.AlignLeft),
            self.text(),
        )
        return rect.height() + 6


# ── Ligne de plan ─────────────────────────────────────────────────────────────

class _ShotRow(QFrame):
    edit_requested   = pyqtSignal(dict)
    delete_requested = pyqtSignal(str)
    changed          = pyqtSignal()
    sound_requested  = pyqtSignal(str, float)   # (sound_prompt, durée) → Sound Design

    _MIN_H = 72

    def _content_height(self) -> int:
        from PyQt6.QtGui import QFont, QFontMetrics

        def _h(text: str, col_idx: int, px: int, bold: bool = False) -> int:
            if not text:
                return 0
            avail = max(10, _col_widths[col_idx] - 13)  # 7+6 = cell left+right padding
            f = QFont()
            f.setPixelSize(px)
            if bold:
                f.setBold(True)
            r = QFontMetrics(f).boundingRect(
                0, 0, avail, 10000,
                int(Qt.TextFlag.TextWordWrap) | int(Qt.AlignmentFlag.AlignLeft),
                text,
            )
            return r.height() + 14  # 8+6 = cell top+bottom padding

        # Colonne 4 = deux prompts empilés (vidéo + son) → on cumule leurs hauteurs.
        _pmt_h = (_h((self._data.get("seedance_prompt", "") or "")[:300], 4, 9)
                  + _h((self._data.get("sound_prompt", "") or "")[:300], 4, 9))
        return max(
            self._MIN_H,
            _pmt_h,
            _h(", ".join(self._data.get("accessory_names", []) or []), 12, 9),
            _h(", ".join(self._data.get("character_names", []) or []), 13, 10),
        )

    def sizeHint(self):
        from PyQt6.QtCore import QSize
        return QSize(max(self.minimumWidth(), 100), self._content_height())

    def minimumSizeHint(self):
        from PyQt6.QtCore import QSize
        return QSize(max(self.minimumWidth(), 100), self._content_height())

    def __init__(self, data: dict, decors_cache: dict | None = None,
                 start_tc: str = "", avail_tracks: list | None = None):
        super().__init__()
        self._data    = data
        self._start_tc = start_tc          # timecode de début (calculé par la page)
        self._avail_tracks = avail_tracks or []  # morceaux du conducteur (nom + bpm)
        self._pmt_lbl = None  # set after build; used by _content_height()
        self.setMinimumHeight(self._MIN_H)

        try:
            pal_idx = (int(data.get("seq_num", 1)) - 1) % len(_SEQ_PALETTE)
        except (TypeError, ValueError):
            pal_idx = 0
        row_bg, seq_bg, seq_color = _SEQ_PALETTE[pal_idx]

        self.setStyleSheet(
            f"QFrame{{background:{row_bg};border:none;border-top:1px solid {CP['border']};}}"
        )

        outer = QHBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # Dict mapping logical column index → widget (populated as cells are built)
        cells: dict[int, QWidget] = {}

        # ── Helpers ───────────────────────────────────────────────────────────

        def _vsep():
            s = QWidget()
            s.setFixedWidth(1)
            s.setStyleSheet(f"background:{CP['border']};")
            return s

        def _cell(width: int, stretch: bool = False, fill: bool = False) -> tuple:
            w = QWidget()
            w.setStyleSheet("background:transparent;")
            if stretch:
                w.setMinimumWidth(width)
                w.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
            else:
                w.setFixedWidth(width)
            lay = QVBoxLayout(w)
            lay.setContentsMargins(7, 8, 6, 6)
            lay.setSpacing(2)
            if not fill:
                # AlignTop prevents layout from expanding to fill row height.
                # Cells with multi-line text must use fill=True so their label
                # expands to the row height and word-wrap shows all content.
                lay.setAlignment(Qt.AlignmentFlag.AlignTop)
            return w, lay

        def _lbl(text: str, color: str = "", size: int = 10,
                 bold: bool = False, mono: bool = False) -> _WrapLabel:
            l = _WrapLabel(text or "")
            s = f"color:{color or CP['text_secondary']};font-size:{size}px;"
            if bold: s += "font-weight:700;"
            if mono: s += "font-family:'Consolas',monospace;"
            s += "background:transparent;border:none;"
            l.setStyleSheet(s)
            l.setWordWrap(True)
            l.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Minimum)
            return l

        def _save_field(key: str, value):
            self._data[key] = value
            sb_api.save_shot(self._data)
            self.changed.emit()

        def _save_fields(updates: dict):
            self._data.update(updates)
            sb_api.save_shot(self._data)
            self.changed.emit()

        def _clickable(widget: QWidget, fn):
            widget.setCursor(Qt.CursorShape.PointingHandCursor)
            _orig = widget.mousePressEvent
            def _mpe(e, _fn=fn, _o=_orig):
                if e.button() == Qt.MouseButton.LeftButton:
                    _fn()
                else:
                    _o(e)
            widget.mousePressEvent = _mpe

        def _dropdown(anchor: QWidget, options: list, current: str, key: str,
                      labels: dict | None = None):
            menu = QMenu(self)
            menu.setStyleSheet(
                f"QMenu{{background:{CP['bg2']};border:1px solid {CP['border_bright']};"
                f"border-radius:8px;padding:4px 0;}}"
                f"QMenu::item{{color:{CP['text_primary']};padding:7px 18px;font-size:11px;}}"
                f"QMenu::item:selected{{background:{CP['accent_dim']};color:{CP['text_primary']};}}"
                f"QMenu::item:checked{{color:{CP['accent']};font-weight:700;}}"
            )
            for opt in options:
                label = labels.get(opt, opt) if labels else opt
                act = menu.addAction(translate(label))
                act.setData(opt)
                act.setCheckable(True)
                act.setChecked(opt == current)
            chosen = menu.exec(anchor.mapToGlobal(anchor.rect().bottomLeft()))
            if chosen:
                _save_field(key, chosen.data())

        # ── Drag grip ─────────────────────────────────────────────────────────
        grip_w = QWidget()
        grip_w.setFixedWidth(_col_widths[0])
        grip_w.setMinimumHeight(self._MIN_H)
        grip_w.setStyleSheet("background:transparent;")
        grip_w.setCursor(Qt.CursorShape.SizeVerCursor)
        grip_lay = QVBoxLayout(grip_w)
        grip_lay.setContentsMargins(0, 0, 0, 0)
        grip_lay.setAlignment(Qt.AlignmentFlag.AlignCenter)
        grip_lbl = QLabel("⠿")
        grip_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        grip_lbl.setStyleSheet(
            f"color:{CP['text_dim']};font-size:15px;background:transparent;border:none;"
        )
        grip_lay.addWidget(grip_lbl)

        grip_w._drag_start = None

        def _grip_press(e, _gw=grip_w):
            if e.button() == Qt.MouseButton.LeftButton:
                _gw._drag_start = e.pos()
        grip_w.mousePressEvent = _grip_press

        def _grip_move(e, _gw=grip_w, _row=self, _shot_id=data["id"]):
            if (e.buttons() & Qt.MouseButton.LeftButton
                    and _gw._drag_start is not None
                    and (e.pos() - _gw._drag_start).manhattanLength() > 6):
                from PyQt6.QtGui import QDrag
                from PyQt6.QtCore import QMimeData, QByteArray
                drag = QDrag(_gw)
                mime = QMimeData()
                mime.setData("application/x-shot-id",
                             QByteArray(_shot_id.encode()))
                drag.setMimeData(mime)
                # Force layout geometry to be applied before capturing the pixmap
                _row.ensurePolished()
                if _row.layout():
                    _row.layout().activate()
                pix_full = _row.grab()
                target_w = max(400, pix_full.width() // 2)
                scale = target_w / max(1, pix_full.width())
                pix = pix_full.scaledToWidth(
                    target_w, Qt.TransformationMode.SmoothTransformation
                )
                drag.setPixmap(pix)
                # Scale hotspot coordinates to match the scaled pixmap
                from PyQt6.QtCore import QPoint
                hot = _row.mapFromGlobal(_gw.mapToGlobal(e.pos()))
                drag.setHotSpot(QPoint(int(hot.x() * scale), int(hot.y() * scale)))
                _gw._drag_start = None
                drag.exec(Qt.DropAction.MoveAction)
        grip_w.mouseMoveEvent = _grip_move

        cells[0] = grip_w

        # ── Aperçu (col 1) ───────────────────────────────────────────────────
        mood_w = QWidget()
        mood_w.setFixedWidth(_col_widths[1])
        mood_w.setMinimumHeight(self._MIN_H)
        mood_w.setStyleSheet("background:transparent;")
        mood_l = QVBoxLayout(mood_w)
        mood_l.setContentsMargins(3, 4, 3, 4)
        mood_l.setAlignment(Qt.AlignmentFlag.AlignCenter)
        img_lbl = QLabel()
        img_lbl.setFixedSize(86, 58)
        img_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        # Load active aperçu image
        apercu_data = sb_api.load_apercus(data["id"])
        apercu_paths = [p for p in apercu_data.get("paths", []) if os.path.isfile(p)]
        active_idx = min(apercu_data.get("active_idx", 0), max(0, len(apercu_paths) - 1))
        active_path = apercu_paths[active_idx] if apercu_paths else ""
        if active_path:
            pix = QPixmap(active_path).scaled(
                86, 58,
                Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                Qt.TransformationMode.SmoothTransformation,
            )
            pix = pix.copy((pix.width()-86)//2, (pix.height()-58)//2, 86, 58)
            img_lbl.setPixmap(pix)
            img_lbl.setStyleSheet(f"background:{CP['bg3']};border:none;")
        else:
            img_lbl.setStyleSheet(
                f"background:{CP['bg3']};border:1px solid {CP['border_bright']};"
                f"color:{CP['accent_dim']};font-size:7px;padding:4px;"
            )
            img_lbl.setWordWrap(True)
            img_lbl.setText("Cliquer\npour Mood")
        img_lbl.setCursor(Qt.CursorShape.PointingHandCursor)
        img_lbl.setToolTip("Voir / générer le Mood de ce plan")
        self._apercu_lbl = img_lbl

        def _open_apercu(img_label=img_lbl, shot_data=data, row_self=self):
            from ui.dialog_apercu import MoodDialog
            dlg = MoodDialog(row_self.window(), shot_data)
            dlg.apercu_changed.connect(row_self._on_apercu_changed)
            dlg.exec()
            # Rafraîchit la cellule à la fermeture — une variation peut avoir été
            # générée ou activée sans passer par le signal apercu_changed.
            apercu = sb_api.load_apercus(shot_data["id"])
            paths  = [p for p in apercu.get("paths", []) if os.path.isfile(p)]
            idx    = min(apercu.get("active_idx", 0), max(0, len(paths) - 1))
            row_self._on_apercu_changed(shot_data["id"], paths[idx] if paths else "")
        _clickable(img_lbl, _open_apercu)

        mood_l.addWidget(img_lbl)
        cells[1] = mood_w

        # ── Séq ──────────────────────────────────────────────────────────────
        seq_w = QWidget()
        seq_w.setFixedWidth(_col_widths[2])
        seq_w.setMinimumHeight(self._MIN_H)
        seq_w.setStyleSheet(f"background:{seq_bg};")
        seq_lay = QVBoxLayout(seq_w)
        seq_lay.setContentsMargins(6, 8, 6, 8)
        seq_lay.setSpacing(2)
        seq_lay.setAlignment(Qt.AlignmentFlag.AlignCenter)
        sq = data.get("seq_num", "")
        sn = data.get("seq_name", "")
        if sq is not None and str(sq):
            n = QLabel(f"SQ{sq}")
            n.setAlignment(Qt.AlignmentFlag.AlignCenter)
            n.setStyleSheet(
                f"color:{seq_color};font-size:22px;font-weight:800;"
                f"font-family:'Consolas',monospace;background:transparent;border:none;"
            )
            seq_lay.addWidget(n)
        if sn:
            s2 = QLabel(sn)
            s2.setAlignment(Qt.AlignmentFlag.AlignCenter)
            s2.setWordWrap(True)
            s2.setStyleSheet(
                f"color:{seq_color};font-size:8px;font-weight:700;"
                f"background:transparent;border:none;"
            )
            seq_lay.addWidget(s2)

        def _edit_seq():
            from PyQt6.QtWidgets import (
                QDialog, QFormLayout, QSpinBox, QLineEdit,
                QDialogButtonBox,
            )
            from ui.styles import PANDORA_STYLESHEET
            dlg = QDialog(self.window())
            dlg.setWindowTitle(translate("Modifier la séquence"))
            dlg.setFixedSize(340, 190)
            dlg.setStyleSheet(PANDORA_STYLESHEET + f"QDialog{{background:{CP['bg1']};}}")

            root = QVBoxLayout(dlg)
            root.setContentsMargins(24, 22, 24, 20)
            root.setSpacing(14)

            _field_ss = (
                f"background:{CP['bg3']};border:1px solid {CP['border']};"
                f"border-radius:6px;color:{CP['text_primary']};font-size:12px;padding:0 10px;"
            )

            form = QFormLayout()
            form.setSpacing(10)
            form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

            _lbl_ss = f"color:{CP['text_secondary']};font-size:11px;background:transparent;"

            num_lbl = QLabel(translate("N° de séquence"))
            num_lbl.setStyleSheet(_lbl_ss)
            spin = QSpinBox()
            spin.setRange(1, 99)
            spin.setValue(int(data.get("seq_num", 1)) if data.get("seq_num") else 1)
            spin.setFixedHeight(36)
            spin.setStyleSheet(f"QSpinBox{{{_field_ss}}}"
                               f"QSpinBox::up-button, QSpinBox::down-button{{width:18px;}}")
            form.addRow(num_lbl, spin)

            name_lbl = QLabel(translate("Nom de séquence"))
            name_lbl.setStyleSheet(_lbl_ss)
            name_edit = QLineEdit()
            name_edit.setPlaceholderText(translate("Ex: La fuite, L'affrontement…"))
            name_edit.setText(data.get("seq_name", "") or "")
            name_edit.setFixedHeight(36)
            name_edit.setStyleSheet(f"QLineEdit{{{_field_ss}}}"
                                    f"QLineEdit:focus{{border-color:{CP['accent']};}}")
            form.addRow(name_lbl, name_edit)

            root.addLayout(form)

            btns = QDialogButtonBox(
                QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
            )
            btns.setStyleSheet(
                f"QPushButton{{background:{CP['bg3']};color:{CP['text_secondary']};"
                f"border:1px solid {CP['border']};border-radius:6px;"
                f"font-size:11px;font-weight:700;padding:6px 18px;}}"
                f"QPushButton:hover{{background:{CP['bg2']};color:{CP['text_primary']};}}"
                f"QPushButton[text='OK']{{background:{CP['accent2']};color:#fff;"
                f"border:none;}}"
                f"QPushButton[text='OK']:hover{{background:#9d8fff;}}"
            )
            btns.accepted.connect(dlg.accept)
            btns.rejected.connect(dlg.reject)
            root.addWidget(btns)

            if dlg.exec() == QDialog.DialogCode.Accepted:
                _save_fields({
                    "seq_num":  spin.value(),
                    "seq_name": name_edit.text().strip(),
                })

        _clickable(seq_w, _edit_seq)
        cells[2] = seq_w

        # ── Plan ─────────────────────────────────────────────────────────────
        plan_w, plan_l = _cell(_col_widths[3])
        plan_l.setAlignment(Qt.AlignmentFlag.AlignCenter)
        pn = QLabel(f"P{data.get('number', '?')}")
        pn.setAlignment(Qt.AlignmentFlag.AlignCenter)
        pn.setStyleSheet(
            f"color:{seq_color};font-size:16px;font-weight:800;"
            f"font-family:'Consolas',monospace;background:transparent;border:none;"
        )
        plan_l.addWidget(pn)
        cells[3] = plan_w

        # ── Prompts : vidéo (→ Seedance) + sound design (→ Sound Design) ──────
        pmt_w = QWidget()
        pmt_w.setFixedWidth(_col_widths[4])
        pmt_w.setStyleSheet("background:transparent;")
        pmt_l = QVBoxLayout(pmt_w)
        pmt_l.setContentsMargins(7, 8, 6, 6)
        pmt_l.setSpacing(5)

        def _prompt_field(icon: str, icon_color: str, value: str, edit_fn,
                          action=None):
            """Un champ prompt cliquable (icône + aperçu), édité inline.
            `action` = (texte_bouton, tooltip, fn) → petit bouton dans l'en-tête."""
            box = QWidget()
            box.setStyleSheet("background:transparent;")
            bl = QVBoxLayout(box)
            bl.setContentsMargins(0, 0, 0, 0)
            bl.setSpacing(0)
            head = QLabel(icon)
            head.setStyleSheet(
                f"color:{icon_color};font-size:8px;font-weight:700;"
                f"background:transparent;border:none;")
            if action is not None:
                _txt, _tip, _fn = action
                head_row = QWidget()
                head_row.setStyleSheet("background:transparent;")
                hr = QHBoxLayout(head_row)
                hr.setContentsMargins(0, 0, 0, 0)
                hr.setSpacing(4)
                hr.addWidget(head)
                act_btn = QPushButton(_txt)
                act_btn.setFixedHeight(14)
                act_btn.setCursor(Qt.CursorShape.PointingHandCursor)
                act_btn.setToolTip(_tip)
                act_btn.setStyleSheet(
                    f"QPushButton{{background:transparent;color:{icon_color};"
                    f"border:1px solid {CP['border']};border-radius:3px;"
                    f"font-size:8px;font-weight:700;padding:0 5px;}}"
                    f"QPushButton:hover{{border-color:{icon_color};}}")
                act_btn.clicked.connect(_fn)
                hr.addWidget(act_btn)
                hr.addStretch()
                head = head_row
            prev = (value[:280] + "…") if len(value) > 280 else (value or "—")
            body = _WrapLabel(prev)
            body.setWordWrap(True)
            body.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
            body.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
            body.setStyleSheet(
                f"color:{CP['text_dim']};font-size:9px;background:transparent;border:none;")
            if value:
                body.setToolTip(value)
            bl.addWidget(head)
            bl.addWidget(body)
            _clickable(box, edit_fn)
            return box, body

        def _edit_video():
            v = _text_dialog(self, translate("Prompt vidéo (Seedance)"),
                             data.get("seedance_prompt", ""), enhance=True)
            if v is not None:
                _save_field("seedance_prompt", v)

        def _edit_sound():
            v = _text_dialog(self, translate("Prompt sound design"),
                             data.get("sound_prompt", ""), enhance=False)
            if v is not None:
                _save_field("sound_prompt", v)

        _vid_box, _pmt_lbl = _prompt_field(
            "🎬 " + translate("Vidéo"), CP["accent"],
            data.get("seedance_prompt", "") or "", _edit_video)
        def _send_sound():
            self.sound_requested.emit(
                self._data.get("sound_prompt", "") or "",
                float(self._data.get("duration", 5.0) or 5.0))

        _snd_box, _snd_lbl = _prompt_field(
            "🔊 " + translate("Son"), CP.get("orange", CP["accent"]),
            data.get("sound_prompt", "") or "", _edit_sound,
            action=("➤ SFX", translate("Envoyer vers Sound Design (Studio IA)"), _send_sound))
        pmt_l.addWidget(_vid_box)
        pmt_l.addWidget(_snd_box)
        self._pmt_lbl = _pmt_lbl
        cells[4] = pmt_w

        # ── Mise en scène (axe + IN + OUT) ───────────────────────────────────
        axe_w, axe_l = _cell(_col_widths[5])
        _cur_axe = data.get("camera_axis", "") or ""
        _chars_in  = (data.get("chars_in", "") or "").strip()
        _chars_out = (data.get("chars_out", "") or "").strip()
        _cam_place = (data.get("camera_placement", "") or "").strip()
        _act_place = (data.get("actor_placement", "") or "").strip()
        axe_l.addWidget(_lbl(translate(_cur_axe) or "—", CP["accent_dim"], 10, mono=True))
        if _chars_in:
            axe_l.addWidget(_lbl(f"↙ {_chars_in}", CP["green"], 8))
        if _chars_out:
            axe_l.addWidget(_lbl(f"↗ {_chars_out}", CP["red"], 8))
        _tip_parts = []
        if _cam_place:  _tip_parts.append(f"Caméra : {_cam_place}")
        if _act_place:  _tip_parts.append(f"Acteurs : {_act_place}")
        if _tip_parts:
            axe_w.setToolTip("\n".join(_tip_parts))
        _clickable(axe_w, lambda _w=axe_w, _c=_cur_axe: _dropdown(
            _w,
            ["", "Face", "3/4", "Latéral 90°", "Dos", "Plongée", "Contre-plongée", "Vue subjective"],
            _c, "camera_axis",
        ))
        cells[5] = axe_w

        # ── Mouvement ────────────────────────────────────────────────────────
        mvt_w, mvt_l = _cell(_col_widths[6])
        _cur_mvt = data.get("camera_movement", "")
        mvt_l.addWidget(_lbl(translate(_cur_mvt), size=10))
        _clickable(mvt_w, lambda _w=mvt_w, _c=_cur_mvt: _dropdown(
            _w, CAMERA_MOVEMENTS, _c, "camera_movement"))
        cells[6] = mvt_w

        # ── Valeur de plan ────────────────────────────────────────────────────
        val_w, val_l = _cell(_col_widths[7])
        _cur_ss = data.get("shot_size", "")
        val_l.addWidget(_lbl(_cur_ss or "—", CP["accent_dim"], 10, mono=True))
        _clickable(val_w, lambda _w=val_w, _c=_cur_ss: _dropdown(
            _w, SHOT_SIZES, _c, "shot_size", SHOT_SIZE_LABELS))
        cells[7] = val_w

        # ── Focal ─────────────────────────────────────────────────────────────
        foc_w, foc_l = _cell(_col_widths[8])
        _cur_foc = data.get("focal", "")
        foc_l.addWidget(_lbl(translate(_cur_foc) or "—", CP["accent_dim"], 10, mono=True))
        _clickable(foc_w, lambda _w=foc_w, _c=_cur_foc: _dropdown(
            _w, FOCALS, _c, "focal"))
        cells[8] = foc_w

        # ── Distance sujet-caméra ─────────────────────────────────────────────
        dst_w, dst_l = _cell(_col_widths[9])
        _cur_dst = data.get("camera_distance", "")
        dst_l.addWidget(_lbl(_cur_dst or "—", CP["accent_dim"], 10, mono=True))

        def _dist_click(_w=dst_w, _c=_cur_dst):
            menu = QMenu(self)
            menu.setStyleSheet(
                f"QMenu{{background:{CP['bg2']};border:1px solid {CP['border_bright']};"
                f"border-radius:8px;padding:4px 0;}}"
                f"QMenu::item{{color:{CP['text_primary']};padding:7px 18px;font-size:11px;}}"
                f"QMenu::item:selected{{background:{CP['accent_dim']};color:{CP['text_primary']};}}"
                f"QMenu::item:checked{{color:{CP['accent']};font-weight:700;}}"
            )
            for opt in DISTANCES:
                label = opt if opt else "— Aucune —"
                act = menu.addAction(translate(label))
                act.setData(opt)
                act.setCheckable(True)
                act.setChecked(opt == _c)
            menu.addSeparator()
            free_act = menu.addAction(translate("✎  Saisir une valeur…"))
            free_act.setData("__free__")
            chosen = menu.exec(_w.mapToGlobal(_w.rect().bottomLeft()))
            if not chosen:
                return
            if chosen.data() == "__free__":
                text, ok = QInputDialog.getText(
                    self, translate("Distance sujet-caméra"),
                    translate("Distance (ex : 4m, 4.5m, 12m) :"), text=_c
                )
                if ok and text.strip():
                    _save_field("camera_distance", text.strip())
            else:
                _save_field("camera_distance", chosen.data())

        _clickable(dst_w, _dist_click)
        cells[9] = dst_w

        # ── Vitesse ──────────────────────────────────────────────────────────
        spd_w, spd_l = _cell(_col_widths[10])
        _cur_spd = data.get("speed", "Normale") or "Normale"
        spd_color = (CP["orange"] if _cur_spd == "Ralenti"
                     else CP["accent"] if _cur_spd == "Accéléré"
                     else CP["text_dim"])
        spd_l.addWidget(_lbl(translate(_cur_spd), spd_color, 10))
        _clickable(spd_w, lambda _w=spd_w, _c=_cur_spd: _dropdown(
            _w, SPEEDS, _c, "speed"))
        cells[10] = spd_w

        # ── Décor ────────────────────────────────────────────────────────────
        dec_w = QWidget()
        dec_w.setFixedWidth(_col_widths[11])
        dec_w.setMinimumHeight(self._MIN_H)
        dec_w.setStyleSheet("background:transparent;")
        dec_lay = QHBoxLayout(dec_w)
        dec_lay.setContentsMargins(5, 6, 5, 6)
        dec_lay.setSpacing(6)

        _dec_id   = data.get("decor_id", "")
        _dec_data = (decors_cache or {}).get(_dec_id, {}) if _dec_id else {}
        d_img = _dec_data.get("image_path", "")
        d_thumb = QLabel()
        d_thumb.setFixedSize(38, 30)
        if d_img and os.path.isfile(d_img):
            d_pix = QPixmap(d_img).scaled(
                38, 30, Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                Qt.TransformationMode.SmoothTransformation,
            )
            d_pix = d_pix.copy((d_pix.width()-38)//2, (d_pix.height()-30)//2, 38, 30)
            d_thumb.setPixmap(d_pix)
            d_thumb.setStyleSheet("border-radius:3px;background:transparent;")
        else:
            d_thumb.setStyleSheet(f"background:{CP['bg3']};border-radius:3px;border:none;")
        dec_lay.addWidget(d_thumb)

        d_name_lbl = QLabel(data.get("decor_name", "") or "—")
        d_name_lbl.setWordWrap(True)
        d_name_lbl.setStyleSheet(
            f"color:{CP['text_secondary']};font-size:10px;background:transparent;border:none;"
        )
        dec_lay.addWidget(d_name_lbl, 1)

        def _pick_decor():
            result = _decor_picker_dialog(self, data.get("decor_id", ""))
            if result is not None:
                _save_fields({"decor_id": result.get("id", ""),
                              "decor_name": result.get("name", "")})
        _clickable(dec_w, _pick_decor)
        cells[11] = dec_w

        # ── Heure (préset + heure libre) ─────────────────────────────────────
        hr_w, hr_l = _cell(_col_widths[12])
        _cur_hr = data.get("shot_time", "") or ""
        _hr_lbl = _lbl(translate(_cur_hr) or "—", size=10)
        hr_l.addWidget(_hr_lbl)

        def _pick_heure(anchor=hr_w):
            menu = QMenu(self)
            menu.setStyleSheet(
                f"QMenu{{background:{CP['bg2']};border:1px solid {CP['border_bright']};"
                f"border-radius:8px;padding:4px 0;}}"
                f"QMenu::item{{color:{CP['text_primary']};padding:7px 18px;font-size:11px;}}"
                f"QMenu::item:selected{{background:{CP['accent_dim']};color:{CP['text_primary']};}}"
                f"QMenu::item:checked{{color:{CP['accent']};font-weight:700;}}"
            )
            cur = data.get("shot_time", "") or ""
            for preset in _HEURE_PRESETS:
                act = menu.addAction(translate(preset))
                act.setData(preset)
                act.setCheckable(True)
                act.setChecked(preset == cur)
            menu.addSeparator()
            custom_act = menu.addAction(translate("Heure précise…"))
            custom_act.setData("__custom__")
            chosen = menu.exec(anchor.mapToGlobal(anchor.rect().bottomLeft()))
            if not chosen:
                return
            val = chosen.data()
            if val == "__custom__":
                from PyQt6.QtWidgets import QInputDialog
                v, ok = QInputDialog.getText(
                    self, translate("Heure du plan"), translate("Heure (ex : 14h30, 07h00) :"),
                    text=cur if cur not in _HEURE_PRESETS else "",
                )
                if ok:
                    val = v.strip()
                else:
                    return
            _save_field("shot_time", val)

        _clickable(hr_w, _pick_heure)
        cells[12] = hr_w

        # ── Accessoires ──────────────────────────────────────────────────────
        acc_w, acc_l = _cell(_col_widths[13], fill=True)
        acc_names = data.get("accessory_names", [])
        _acc_lbl = _lbl(", ".join(acc_names) if acc_names else "—", size=9)
        _acc_lbl.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        _acc_lbl.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        acc_l.addWidget(_acc_lbl)
        def _pick_accessories():
            items = acc_api.list_accessories()
            result = _elements_picker_dialog(self, "Accessoires", items,
                                             data.get("accessory_ids", []))
            if result is not None:
                ids, names = result
                _save_fields({"accessory_ids": ids, "accessory_names": names})
        _clickable(acc_w, _pick_accessories)
        cells[13] = acc_w

        # ── Acteurs ──────────────────────────────────────────────────────────
        chr_w, chr_l = _cell(_col_widths[14], fill=True)
        char_names = data.get("character_names", [])
        _chr_lbl = _lbl(", ".join(char_names) if char_names else "—", size=10)
        _chr_lbl.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        _chr_lbl.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        chr_l.addWidget(_chr_lbl)
        def _pick_actors():
            items = casting_api.list_characters()
            result = _elements_picker_dialog(self, "Acteurs / Personnages", items,
                                             data.get("character_ids", []))
            if result is not None:
                ids, names = result
                _save_fields({"character_ids": ids, "character_names": names})
        _clickable(chr_w, _pick_actors)
        cells[14] = chr_w

        # ── Durée ────────────────────────────────────────────────────────────
        dur_w, dur_l = _cell(_col_widths[15])
        dur_l.setAlignment(Qt.AlignmentFlag.AlignCenter)
        dur = float(data.get("duration", 5.0))
        dur_color = CP["red"] if dur > 12 else CP["orange"] if dur > 8 else CP["green"]
        dur_badge = QLabel(f"{dur:.1f}s")
        dur_badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        dur_badge.setStyleSheet(
            f"color:#07080f;background:{dur_color};border-radius:4px;"
            f"font-size:9px;font-weight:800;font-family:'Consolas',monospace;padding:2px 4px;"
        )
        dur_l.addWidget(dur_badge)
        def _edit_duration():
            val, ok = QInputDialog.getDouble(
                self, translate("Durée du plan"), translate("Durée (1 — 15 secondes) :"),
                float(data.get("duration", 5.0)), 1.0, 15.0, 1,
            )
            if ok:
                _save_field("duration", round(val, 1))
        _clickable(dur_w, _edit_duration)
        cells[15] = dur_w

        _tracks = getattr(self, "_avail_tracks", []) or []
        _track_names = [t.get("name", "") for t in _tracks if t.get("name")]

        # ── TC (timecode de début, calculé) ───────────────────────────────────
        tc_w, tc_l = _cell(_col_widths[16])
        tc_l.setAlignment(Qt.AlignmentFlag.AlignCenter)
        tc_l.addWidget(_lbl(getattr(self, "_start_tc", "") or "—",
                            CP["text_secondary"], 10, mono=True))
        cells[16] = tc_w

        # ── Musique (morceau assigné depuis « Musiques du set ») ──────────────
        mus_w, mus_l = _cell(_col_widths[17])
        _cur_mus = data.get("music_track", "") or ""
        mus_l.addWidget(_lbl(_cur_mus or "—", CP["accent"], 9))
        def _pick_music(_w=mus_w, _opts=[""] + _track_names, _c=_cur_mus):
            _dropdown(_w, _opts, _c, "music_track", labels={"": "— Aucune —"})
        _clickable(mus_w, _pick_music)
        cells[17] = mus_w

        # ── BPM (dérivé du morceau assigné) ───────────────────────────────────
        bpm_w, bpm_l = _cell(_col_widths[18])
        bpm_l.setAlignment(Qt.AlignmentFlag.AlignCenter)
        _bpm_val = ""
        if _cur_mus:
            _tk = next((t for t in _tracks if t.get("name") == _cur_mus), None)
            if _tk and _tk.get("bpm"):
                try:
                    _bpm_val = f"{float(_tk['bpm']):.0f}"
                except (TypeError, ValueError):
                    _bpm_val = ""
        bpm_l.addWidget(_lbl(_bpm_val or "—", CP["accent_dim"], 10, mono=True))
        cells[18] = bpm_w

        # ── Transition ────────────────────────────────────────────────────────
        tr_w, tr_l = _cell(_col_widths[19])
        _cur_tr = data.get("transition", "") or ""
        tr_l.addWidget(_lbl(translate(_cur_tr) or "—", size=10))
        _clickable(tr_w, lambda _w=tr_w, _c=_cur_tr: _dropdown(
            _w, ["", "Cut", "Fondu", "Dissolve", "Glitch", "Flash", "Wipe"], _c,
            "transition", labels={"": "— Aucune —"}))
        cells[19] = tr_w

        # ── Notes / Repère ────────────────────────────────────────────────────
        note_w, note_l = _cell(_col_widths[20], fill=True)
        _cur_note = data.get("cue_note", "") or ""
        _note_lbl = _lbl(_cur_note or "—", size=9)
        _note_lbl.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        _note_lbl.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        note_l.addWidget(_note_lbl)
        def _edit_note():
            v = _text_dialog(self, translate("Notes / Repère"), data.get("cue_note", ""))
            if v is not None:
                _save_field("cue_note", v)
        _clickable(note_w, _edit_note)
        cells[20] = note_w

        # ── Boutons ──────────────────────────────────────────────────────────
        btns_w = QWidget()
        btns_w.setFixedWidth(_col_widths[21])
        btns_w.setMinimumHeight(self._MIN_H)
        btns_w.setStyleSheet("background:transparent;")
        bl = QVBoxLayout(btns_w)
        bl.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignHCenter)
        bl.setSpacing(6)
        bl.setContentsMargins(6, 10, 6, 10)

        btn_edit = QPushButton(translate("Éditer"))
        btn_edit.setFixedHeight(28)
        btn_edit.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_edit.setStyleSheet(
            f"QPushButton{{background:transparent;color:{CP['accent']};"
            f"border:1px solid {CP['accent']};border-radius:5px;"
            f"font-size:10px;font-weight:700;padding:0 6px;}}"
            f"QPushButton:hover{{background:{CP['accent']};color:#07080f;}}"
        )
        btn_edit.clicked.connect(lambda: self.edit_requested.emit(self._data))
        bl.addWidget(btn_edit)

        btn_del = QPushButton("Suppr.")
        btn_del.setFixedHeight(28)
        btn_del.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_del.setStyleSheet(
            f"QPushButton{{background:transparent;color:{CP['red']};"
            f"border:1px solid {CP['red']};border-radius:5px;"
            f"font-size:10px;font-weight:700;padding:0 6px;}}"
            f"QPushButton:hover{{background:rgba(255,79,106,0.18);}}"
        )
        btn_del.clicked.connect(lambda: self.delete_requested.emit(self._data["id"]))
        bl.addWidget(btn_del)
        cells[21] = btns_w

        # ── Assemblage des colonnes dans l'ordre visuel (_col_order) ─────────
        _vis = _visible_order()
        for i, col_logical in enumerate(_vis):
            outer.addWidget(cells[col_logical])
            if i < len(_vis) - 1:
                outer.addWidget(_vsep())
        outer.addStretch()

        # ── Redimensionnement des colonnes ────────────────────────────────────
        self._col_cells = cells  # dict {logical_col_idx: widget}
        _col_hub.resized.connect(self._on_col_resize)
        # Now that _pmt_lbl is built, compute the correct initial height
        self.setMinimumHeight(self._content_height())

    def _on_col_resize(self, col_idx: int, new_w: int):
        cell = self._col_cells.get(col_idx)
        if cell is None:
            return
        cell.setFixedWidth(new_w)
        self.setMinimumHeight(self._content_height())

    def _on_apercu_changed(self, shot_id: str, image_path: str):
        if shot_id != self._data.get("id") or not hasattr(self, "_apercu_lbl"):
            return
        if image_path and os.path.isfile(image_path):
            pix = QPixmap(image_path).scaled(
                86, 58,
                Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                Qt.TransformationMode.SmoothTransformation,
            )
            pix = pix.copy((pix.width()-86)//2, (pix.height()-58)//2, 86, 58)
            self._apercu_lbl.setPixmap(pix)
            self._apercu_lbl.setStyleSheet(f"background:{CP['bg3']};border:none;")
        else:
            self._apercu_lbl.clear()
            self._apercu_lbl.setText("Cliquer\npour Mood")


# ── Conteneur de plans avec drop-zone ────────────────────────────────────────

class _ShotListContainer(QWidget):
    shot_dropped = pyqtSignal(str, int)  # (shot_id, insertion_index)

    def minimumSizeHint(self):
        from PyQt6.QtCore import QSize
        # Mode vide (pas de tableau) : aucune largeur imposée — le message
        # « Aucun découpage » se centre dans la fenêtre, pas dans les colonnes
        if getattr(self, "_empty_mode", False):
            return super().minimumSizeHint()
        w = sum(_col_widths) + len(_col_widths) - 1
        return QSize(w, super().minimumSizeHint().height())

    def sizeHint(self):
        from PyQt6.QtCore import QSize
        if getattr(self, "_empty_mode", False):
            return super().sizeHint()
        w = sum(_col_widths) + len(_col_widths) - 1
        return QSize(w, super().sizeHint().height())

    def __init__(self):
        super().__init__()
        self.setAcceptDrops(True)
        self._indicator = QFrame(self)
        self._indicator.setFixedHeight(2)
        self._indicator.setStyleSheet(
            f"background:{CP['accent']};border:none;"
        )
        self._indicator.hide()

    def _shot_rows(self) -> list:
        lay = self.layout()
        if not lay:
            return []
        return [
            lay.itemAt(i).widget()
            for i in range(lay.count())
            if lay.itemAt(i) and isinstance(lay.itemAt(i).widget(), _ShotRow)
        ]

    def _insertion_index(self, y: int) -> int:
        for i, row in enumerate(self._shot_rows()):
            if y < row.y() + row.height() // 2:
                return i
        return len(self._shot_rows())

    def dragEnterEvent(self, e):
        if e.mimeData().hasFormat("application/x-shot-id"):
            e.acceptProposedAction()

    def dragMoveEvent(self, e):
        if not e.mimeData().hasFormat("application/x-shot-id"):
            return
        e.acceptProposedAction()
        rows = self._shot_rows()
        if not rows:
            return
        y = e.position().toPoint().y()
        idx = self._insertion_index(y)
        ind_y = rows[0].y() if idx == 0 else (
            rows[-1].y() + rows[-1].height() - 2 if idx >= len(rows)
            else rows[idx].y()
        )
        self._indicator.setGeometry(0, ind_y - 1, self.width(), 2)
        self._indicator.show()
        self._indicator.raise_()

    def dragLeaveEvent(self, e):
        self._indicator.hide()

    def dropEvent(self, e):
        self._indicator.hide()
        if e.mimeData().hasFormat("application/x-shot-id"):
            from PyQt6.QtCore import QByteArray
            shot_id = bytes(e.mimeData().data("application/x-shot-id")).decode()
            idx = self._insertion_index(e.position().toPoint().y())
            self.shot_dropped.emit(shot_id, idx)
            e.acceptProposedAction()


# ── Poignée de redimensionnement vertical des lignes ─────────────────────────

class _RowResizeHandle(QWidget):
    """4 px drag strip between rows — drag to adjust the row height above."""

    def __init__(self, target_row: "_ShotRow"):
        super().__init__()
        self._row           = target_row
        self._drag_start_y  = None
        self._drag_start_h  = None
        self.setFixedHeight(4)
        self.setCursor(Qt.CursorShape.SizeVerCursor)
        self._set_idle()

    def _set_idle(self):
        self.setStyleSheet(f"background:{CP['border']};border:none;")

    def _set_hover(self):
        self.setStyleSheet(f"background:{CP['accent_dim']};border:none;")

    def _set_active(self):
        self.setStyleSheet(f"background:{CP['accent']};border:none;")

    def enterEvent(self, e):
        if self._drag_start_y is None:
            self._set_hover()

    def leaveEvent(self, e):
        if self._drag_start_y is None:
            self._set_idle()

    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            self._drag_start_y = e.globalPosition().toPoint().y()
            self._drag_start_h = self._row.height()
            self._set_active()
            e.accept()

    def mouseMoveEvent(self, e):
        if self._drag_start_y is not None and (e.buttons() & Qt.MouseButton.LeftButton):
            delta  = e.globalPosition().toPoint().y() - self._drag_start_y
            new_h  = max(_ShotRow._MIN_H, self._drag_start_h + delta)
            self._row.setMinimumHeight(new_h)
            e.accept()

    def mouseReleaseEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            self._drag_start_y = None
            self._set_idle()
            e.accept()


# ── Carte version ─────────────────────────────────────────────────────────────

class _VersionCard(QWidget):
    open_requested   = pyqtSignal(str)
    delete_requested = pyqtSignal(str)

    def __init__(self, version: dict):
        super().__init__()
        self._vid  = version.get("id", "")
        self._name = version.get("name", "Version")
        n_shots    = version.get("shot_count", 0)

        self.setFixedHeight(72)
        self.setStyleSheet(
            f"QWidget{{background:{CP['bg2']};border:1px solid {CP['border']};border-radius:10px;}}"
        )

        lay = QHBoxLayout(self)
        lay.setContentsMargins(16, 10, 16, 10)
        lay.setSpacing(14)

        icon_lbl = QLabel("⊞")
        icon_lbl.setFixedSize(38, 38)
        icon_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon_lbl.setStyleSheet(
            f"background:rgba(78,205,196,0.12);border-radius:8px;"
            f"color:{CP['accent']};font-size:20px;border:none;"
        )
        lay.addWidget(icon_lbl)

        # Info column — contains name+buttons row and count row
        info_col = QVBoxLayout()
        info_col.setSpacing(4)
        info_col.setContentsMargins(0, 0, 0, 0)

        name_row = QHBoxLayout()
        name_row.setSpacing(8)
        name_row.setContentsMargins(0, 0, 0, 0)

        name_lbl = QLabel(self._name)
        name_lbl.setStyleSheet(
            f"color:{CP['text_primary']};font-size:13px;font-weight:700;"
            f"background:transparent;border:none;"
        )
        name_row.addWidget(name_lbl, 1)

        btn_open = QPushButton("Ouvrir →")
        btn_open.setFixedHeight(28)
        btn_open.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_open.setStyleSheet(
            f"QPushButton{{background:{CP['accent']};color:#07080f;"
            f"border:none;border-radius:6px;font-size:11px;font-weight:700;padding:0 10px;}}"
            f"QPushButton:hover{{background:#6eded6;}}"
        )
        btn_open.clicked.connect(lambda: self.open_requested.emit(self._vid))
        name_row.addWidget(btn_open)

        btn_del = QPushButton(translate("Supprimer"))
        btn_del.setFixedHeight(28)
        btn_del.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_del.setStyleSheet(
            f"QPushButton{{background:transparent;color:{CP['red']};"
            f"border:1px solid {CP['red']};border-radius:6px;"
            f"font-size:11px;font-weight:700;padding:0 10px;}}"
            f"QPushButton:hover{{background:rgba(255,79,106,0.15);}}"
            f"QPushButton:pressed{{background:rgba(255,79,106,0.30);}}"
        )
        btn_del.clicked.connect(lambda: self.delete_requested.emit(self._vid))
        name_row.addWidget(btn_del)

        count_lbl = QLabel(f"{n_shots} plan{'s' if n_shots != 1 else ''}")
        count_lbl.setStyleSheet(
            f"color:{CP['text_dim']};font-size:10px;font-family:'Consolas',monospace;"
            f"background:transparent;border:none;"
        )

        info_col.addLayout(name_row)
        info_col.addWidget(count_lbl)
        lay.addLayout(info_col, 1)


# ── Dialog d'information avant la génération batch ───────────────────────────

class _MoodInfoDialog(QDialog):
    """Conseils à afficher une seule fois avant la génération automatique des Moods."""

    def __init__(self, parent: QWidget):
        super().__init__(parent)
        from ui.styles import PANDORA_STYLESHEET
        self.setWindowTitle(translate("✦ Avant de générer les Moods"))
        self.setFixedSize(560, 440)
        self.setStyleSheet(PANDORA_STYLESHEET + f"QDialog{{background:{CP['bg1']};}}")
        self._mode = "mapping" if sb_api.get_namespace() == "live_seq_mapping" else "live"
        self._build_ui()

    def _build_ui(self):
        lay = QVBoxLayout(self)
        lay.setContentsMargins(28, 24, 28, 24)
        lay.setSpacing(16)

        # Icône + titre
        title_row = QHBoxLayout()
        icon_lbl = QLabel("✦")
        icon_lbl.setStyleSheet(
            f"color:{CP['accent']};font-size:24px;background:transparent;"
        )
        title_row.addWidget(icon_lbl)
        title_lbl = QLabel(translate("Pour un résultat optimal"))
        title_lbl.setStyleSheet(
            f"color:{CP['text_primary']};font-size:15px;font-weight:700;background:transparent;"
        )
        title_row.addWidget(title_lbl, 1)
        lay.addLayout(title_row)

        # Séparateur
        sep = QFrame()
        sep.setFixedHeight(1)
        sep.setStyleSheet(f"background:{CP['border']};")
        lay.addWidget(sep)

        # Conseils — adaptés au mode (Live VJ / Mapping façade)
        if self._mode == "mapping":
            conseils = [
                ("▦", "Choisis la façade du bâtiment",
                 "Dans le Conducteur, renseigne la « Référence bâtiment » et isole-la "
                 "sur fond noir. Les Moods sont générés SUR cette façade, dont la "
                 "géométrie est conservée."),
                ("🌙", "Rendu de nuit automatique",
                 "Le mapping se projette de nuit : les Moods sont automatiquement "
                 "convertis en nuit (façade éclairée uniquement par la projection, "
                 "environnement en fond noir)."),
                ("✍️", "Soigne les prompts vidéo et son",
                 "Décris l'évolution sur la façade (lumière, effets, matières) dans le "
                 "« Prompt vidéo ». Ajoute un « Prompt sound design » pour l'ambiance "
                 "sonore du plan (injecté dans Sound Design)."),
                ("⚡", "Génération rapide",
                 "La génération batch traite les plans l'un après l'autre. "
                 "Tu peux l'arrêter à tout moment — les Moods déjà générés sont conservés."),
            ]
        else:
            conseils = [
                ("✍️", "Soigne le prompt vidéo",
                 "Le Mood teste l'ambiance du loop. Plus le « Prompt vidéo » du plan est "
                 "détaillé, plus l'image générée reflète le visuel VJ que tu veux obtenir."),
                ("🔊", "Pense au prompt sound design",
                 "Chaque plan a aussi un « Prompt sound design » (SFX / ambiance, sans "
                 "voix) qui sera injecté dans l'onglet Sound Design."),
                ("🎨", "Valider avant de générer la vidéo",
                 "Une fois les Moods satisfaisants, ils servent de référence visuelle "
                 "pour générer les loops (Seedance et autres moteurs). "
                 "Ce n'est pas une pré-visualisation fidèle."),
                ("⚡", "Génération rapide",
                 "La génération batch traite les plans l'un après l'autre. "
                 "Tu peux l'arrêter à tout moment — les Moods déjà générés sont conservés."),
            ]

        for icon, titre, corps in conseils:
            bloc = QFrame()
            bloc.setStyleSheet(
                f"QFrame{{background:{CP['bg0']};border:1px solid {CP['border']};"
                f"border-radius:8px;}}"
            )
            bloc_lay = QHBoxLayout(bloc)
            bloc_lay.setContentsMargins(12, 10, 14, 10)
            bloc_lay.setSpacing(12)

            ic = QLabel(icon)
            ic.setStyleSheet("background:transparent;border:none;font-size:16px;")
            ic.setFixedWidth(24)
            bloc_lay.addWidget(ic)

            txt_col = QVBoxLayout()
            txt_col.setSpacing(2)
            t = QLabel(translate(titre))
            t.setStyleSheet(
                f"color:{CP['text_primary']};font-size:11px;font-weight:700;"
                f"background:transparent;border:none;"
            )
            txt_col.addWidget(t)
            c = QLabel(translate(corps))
            c.setWordWrap(True)
            c.setStyleSheet(
                f"color:{CP['text_secondary']};font-size:10px;"
                f"background:transparent;border:none;"
            )
            txt_col.addWidget(c)
            bloc_lay.addLayout(txt_col, 1)
            lay.addWidget(bloc)

        lay.addStretch()

        # Checkbox + bouton
        bottom = QHBoxLayout()
        self._cb_skip = QCheckBox(translate("Ne plus afficher ce message"))
        self._cb_skip.setStyleSheet(
            f"color:{CP['text_secondary']};font-size:10px;background:transparent;"
        )
        bottom.addWidget(self._cb_skip, 1)

        btn = QPushButton(translate("Continuer →"))
        btn.setFixedHeight(36)
        btn.setStyleSheet(
            f"QPushButton{{background:{CP['accent']};color:#07080f;"
            f"border:none;border-radius:8px;font-size:12px;font-weight:700;padding:0 24px;}}"
            f"QPushButton:hover{{background:#6eded6;}}"
        )
        btn.clicked.connect(self.accept)
        bottom.addWidget(btn)
        lay.addLayout(bottom)

    def skip_next_time(self) -> bool:
        return self._cb_skip.isChecked()


# ── Dialogue de configuration de la génération batch des Moods ───────────────

class _MoodBatchDialog(QDialog):
    """Choisir les plans dont générer le Mood."""

    def __init__(self, parent: QWidget, shots: list[dict]):
        super().__init__(parent)
        from ui.styles import PANDORA_STYLESHEET
        self.setWindowTitle(translate("✦ Génération des Moods"))
        self.setMinimumSize(480, 480)
        self.setStyleSheet(PANDORA_STYLESHEET + f"QDialog{{background:{CP['bg1']};}}")
        self._shots = shots
        self._has_mood: set[str] = set()
        for shot in shots:
            sid  = shot.get("id", "")
            data = sb_api.load_apercus(sid)
            if any(os.path.isfile(p) for p in data.get("paths", [])):
                self._has_mood.add(sid)
        self._build_ui()
        self._populate()

    def _build_ui(self):
        lay = QVBoxLayout(self)
        lay.setContentsMargins(24, 20, 24, 20)
        lay.setSpacing(14)

        title = QLabel(translate("Génération automatique des Moods"))
        title.setStyleSheet(
            f"color:{CP['text_primary']};font-size:14px;font-weight:700;background:transparent;"
        )
        lay.addWidget(title)

        desc = QLabel(translate(
            "Sélectionne les plans pour lesquels générer un Mood. "
            "Les plans marqués ✓ ont déjà un Mood — ils sont décochés par défaut."
        ))
        desc.setStyleSheet(f"color:{CP['text_dim']};font-size:11px;background:transparent;")
        desc.setWordWrap(True)
        lay.addWidget(desc)

        lay.addWidget(_sep())

        lbl_shots = QLabel(translate("Plans à générer :"))
        lbl_shots.setStyleSheet(
            f"color:{CP['text_primary']};font-size:11px;font-weight:600;background:transparent;"
        )
        lay.addWidget(lbl_shots)

        qsel = QHBoxLayout()
        qsel.setSpacing(6)
        self._btn_all     = QPushButton(translate("Tout"))
        self._btn_none    = QPushButton(translate("Aucun"))
        self._btn_no_mood = QPushButton(translate("Sans Mood"))
        _qsel_style = (
            f"QPushButton{{background:transparent;color:{CP['text_dim']};"
            f"border:1px solid {CP['border']};border-radius:5px;"
            f"font-size:10px;padding:0 9px;height:24px;}}"
            f"QPushButton:hover{{color:{CP['text_primary']};border-color:{CP['accent']};}}"
        )
        for b in (self._btn_all, self._btn_none, self._btn_no_mood):
            b.setStyleSheet(_qsel_style)
        self._btn_all.clicked.connect(self._select_all)
        self._btn_none.clicked.connect(self._select_none)
        self._btn_no_mood.clicked.connect(self._select_no_mood)
        qsel.addWidget(self._btn_all)
        qsel.addWidget(self._btn_none)
        qsel.addWidget(self._btn_no_mood)
        qsel.addStretch()
        lay.addLayout(qsel)

        self._list = QListWidget()
        self._list.setStyleSheet(
            f"QListWidget{{background:{CP['bg0']};border:1px solid {CP['border']};"
            f"border-radius:6px;color:{CP['text_primary']};font-size:11px;outline:none;}}"
            f"QListWidget::item{{padding:5px 8px;}}"
            f"QListWidget::item:hover{{background:rgba(78,205,196,0.08);}}"
        )
        lay.addWidget(self._list, 1)

        self._count_lbl = QLabel("")
        self._count_lbl.setStyleSheet(
            f"color:{CP['text_dim']};font-size:10px;background:transparent;"
        )
        lay.addWidget(self._count_lbl)

        lay.addWidget(_sep())

        btns = QHBoxLayout()
        btns.setSpacing(10)
        cancel_btn = QPushButton(translate("Annuler"))
        cancel_btn.setFixedHeight(36)
        cancel_btn.setStyleSheet(
            f"QPushButton{{background:transparent;color:{CP['text_dim']};"
            f"border:1px solid {CP['border']};border-radius:8px;"
            f"font-size:12px;padding:0 20px;}}"
            f"QPushButton:hover{{color:{CP['text_primary']};border-color:{CP['text_primary']};}}"
        )
        cancel_btn.clicked.connect(self.reject)
        self._gen_btn = QPushButton(translate("✦  Générer"))
        self._gen_btn.setFixedHeight(36)
        self._gen_btn.setStyleSheet(
            f"QPushButton{{background:{CP['accent']};color:#07080f;"
            f"border:none;border-radius:8px;font-size:12px;font-weight:700;padding:0 24px;}}"
            f"QPushButton:hover{{background:#6eded6;}}"
            f"QPushButton:disabled{{background:{CP['border']};color:{CP['text_dim']};}}"
        )
        self._gen_btn.clicked.connect(self.accept)
        btns.addStretch()
        btns.addWidget(cancel_btn)
        btns.addWidget(self._gen_btn)
        lay.addLayout(btns)

    def _populate(self):
        self._list.clear()
        for shot in self._shots:
            num   = shot.get("number", "?")
            title = (shot.get("scene_title") or "").strip()
            sid   = shot.get("id", "")
            label = f"Plan {num}"
            if title:
                label += f"  —  {title[:50]}"
            if sid in self._has_mood:
                label += "  ✓"
            item = QListWidgetItem(label)
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(
                Qt.CheckState.Unchecked if sid in self._has_mood else Qt.CheckState.Checked
            )
            item.setData(Qt.ItemDataRole.UserRole, shot)
            self._list.addItem(item)
        self._list.itemChanged.connect(self._update_count)
        self._update_count()

    def _update_count(self):
        n = sum(
            1 for i in range(self._list.count())
            if self._list.item(i).checkState() == Qt.CheckState.Checked
        )
        self._gen_btn.setText(f"✦  Générer {n} plan{'s' if n != 1 else ''}")
        self._gen_btn.setEnabled(n > 0)
        self._count_lbl.setText(
            f"{n} plan{'s' if n != 1 else ''} sélectionné{'s' if n != 1 else ''}"
        )

    def _select_all(self):
        self._list.itemChanged.disconnect(self._update_count)
        for i in range(self._list.count()):
            self._list.item(i).setCheckState(Qt.CheckState.Checked)
        self._list.itemChanged.connect(self._update_count)
        self._update_count()

    def _select_none(self):
        self._list.itemChanged.disconnect(self._update_count)
        for i in range(self._list.count()):
            self._list.item(i).setCheckState(Qt.CheckState.Unchecked)
        self._list.itemChanged.connect(self._update_count)
        self._update_count()

    def _select_no_mood(self):
        self._list.itemChanged.disconnect(self._update_count)
        for i in range(self._list.count()):
            item = self._list.item(i)
            has = item.data(Qt.ItemDataRole.UserRole).get("id", "") in self._has_mood
            item.setCheckState(Qt.CheckState.Unchecked if has else Qt.CheckState.Checked)
        self._list.itemChanged.connect(self._update_count)
        self._update_count()

    def selected_shots(self) -> list[dict]:
        return [
            self._list.item(i).data(Qt.ItemDataRole.UserRole)
            for i in range(self._list.count())
            if self._list.item(i).checkState() == Qt.CheckState.Checked
        ]


# ── Page principale Storyboard ────────────────────────────────────────────────

class PageStoryboard(QWidget):

    # (sound_prompt, durée) relayé vers le Studio IA → onglet Sound Design.
    sound_to_studio = pyqtSignal(str, float)

    # Colonnes masquées pour cette page (vide = toutes visibles).
    # SequenceMappingPage la surcharge pour masquer Axe/Valeur/Distance/Décor/Heure.
    _hidden_cols: set = set()

    # Ordre de colonnes par défaut de la page (None = ordre naturel). Utilisé
    # seulement si l'utilisateur n'a pas encore personnalisé l'ordre (drag).
    _default_col_order: list | None = None

    def __init__(self):
        super().__init__()
        self.setStyleSheet(f"background:{CP['bg0']};")
        self._all_shots: list[dict] = []
        self._worker = None
        self._batch_mood_worker = None
        self._shot_rows: dict[str, "_ShotRow"] = {}
        self._analysis_dlg = None
        self._first_show_done = False

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        root.addWidget(self._build_shots_page())

        versions = sb_api.list_versions()
        self._active_version_id = versions[0]["id"] if versions else DEFAULT_VERSION_ID

        self._fill_version_combo()
        self._all_shots = sb_api.list_shots(self._active_version_id)
        self._refresh_snap_combo()
        self._render()

    def showEvent(self, event):
        super().showEvent(event)
        if not self._first_show_done:
            self._first_show_done = True
            # Stylesheets are now applied — recalculate all row heights with real font metrics
            QTimer.singleShot(0, lambda: _col_hub.resized.emit(4, _col_widths[4]))


    def _on_new_version(self):
        from ui.styles import PANDORA_STYLESHEET
        dlg = QDialog(self)
        dlg.setWindowTitle(translate("Nouvelle version"))
        dlg.setFixedSize(380, 160)
        dlg.setStyleSheet(PANDORA_STYLESHEET + f"QDialog{{background:{CP['bg1']};}}")

        lay = QVBoxLayout(dlg)
        lay.setContentsMargins(24, 24, 24, 24)
        lay.setSpacing(12)

        lbl = QLabel(translate("Nom de la nouvelle version :"))
        lbl.setStyleSheet(f"color:{CP['text_primary']};font-size:12px;background:transparent;")
        lay.addWidget(lbl)

        inp = QLineEdit()
        inp.setPlaceholderText(translate("Ex: Découpage final, Version action, Avant-projet…"))
        inp.setFixedHeight(36)
        inp.setStyleSheet(
            f"QLineEdit{{background:{CP['bg3']};border:1px solid {CP['border']};"
            f"border-radius:6px;color:{CP['text_primary']};font-size:12px;padding:0 10px;}}"
            f"QLineEdit:focus{{border-color:{CP['accent']};}}"
        )
        lay.addWidget(inp)

        btn_row = QHBoxLayout()
        btn_cancel = QPushButton(translate("Annuler"))
        btn_cancel.setFixedHeight(36)
        btn_cancel.setStyleSheet(
            f"QPushButton{{background:transparent;color:{CP['text_secondary']};"
            f"border:1px solid {CP['border']};border-radius:8px;font-size:12px;font-weight:700;padding:0 14px;}}"
            f"QPushButton:hover{{background:{CP['bg3']};color:{CP['text_primary']};}}"
        )
        btn_cancel.clicked.connect(dlg.reject)

        btn_ok = QPushButton(translate("Créer"))
        btn_ok.setFixedHeight(36)
        btn_ok.setStyleSheet(
            f"QPushButton{{background:{CP['accent']};color:#07080f;"
            f"border:none;border-radius:8px;font-size:12px;font-weight:700;padding:0 14px;}}"
            f"QPushButton:hover{{background:#6eded6;}}"
        )
        btn_ok.clicked.connect(dlg.accept)

        btn_row.addWidget(btn_cancel)
        btn_row.addStretch()
        btn_row.addWidget(btn_ok)
        lay.addLayout(btn_row)

        if dlg.exec() == QDialog.DialogCode.Accepted:
            name = inp.text().strip()
            if name:
                new_v = sb_api.create_version(name)
                self._active_version_id = new_v["id"]
                self._fill_version_combo()
                self._all_shots = sb_api.list_shots(self._active_version_id)
                self._refresh_snap_combo()
                self._render()

    def _on_delete_version(self, version_id: str) -> bool:
        versions = sb_api.list_versions()
        v_name = next((v["name"] for v in versions if v["id"] == version_id), "Version")
        shot_count = next((v.get("shot_count", 0) for v in versions if v["id"] == version_id), 0)
        msg = f"Supprimer la version « {v_name} » ?"
        if shot_count:
            msg += f"\n\n{shot_count} plan(s) seront supprimés définitivement."
        reply = QMessageBox.question(
            self, "Supprimer la version", msg,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            sb_api.delete_version(version_id)
            return True
        return False

    def _on_delete_current_version(self):
        if self._on_delete_version(self._active_version_id):
            versions = sb_api.list_versions()
            self._active_version_id = versions[0]["id"] if versions else ""
            self._fill_version_combo()
            self._all_shots = sb_api.list_shots(self._active_version_id) if self._active_version_id else []
            self._refresh_snap_combo()
            self._render()

    def _on_chat_applied(self):
        """Le chat storyboard a appliqué des modifications → recharge et réaffiche."""
        self._all_shots = sb_api.list_shots(self._active_version_id)
        self._render()

    def _on_sync(self):
        if not self._all_shots:
            return
        from ui.dialog_storyboard_sync import StoryboardSyncConfirmDialog, StoryboardSyncDialog
        confirm = StoryboardSyncConfirmDialog(len(self._all_shots), parent=self)
        if confirm.exec() != StoryboardSyncConfirmDialog.DialogCode.Accepted:
            return
        options = confirm.selected_options()
        dlg = StoryboardSyncDialog(self._all_shots, options, parent=self)
        if dlg.exec() == StoryboardSyncDialog.DialogCode.Accepted:
            self._all_shots = sb_api.list_shots(self._active_version_id)
            self._render()

    def _on_clear_shots(self):
        """Supprime tous les plans du découpage actuel pour permettre une régénération."""
        n = len(self._all_shots)
        if not n:
            return
        reply = QMessageBox.question(
            self, "Vider le découpage",
            f"Supprimer les {n} plan(s) du découpage actuel ?\n\n"
            "Le découpage sera vidé pour permettre une régénération depuis le scénario.\n"
            "Cette action est irréversible.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        for shot in list(self._all_shots):
            sb_api.delete_shot(shot["id"])
        self._all_shots = []
        self._render()

    # ── Page des plans ────────────────────────────────────────────────────────

    def _build_shots_page(self) -> QWidget:
        page = QWidget()
        page.setStyleSheet(f"background:{CP['bg0']};")
        lay = QVBoxLayout(page)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)

        lay.addWidget(self._build_shots_topbar())
        lay.addWidget(_sep())

        _hw = QWidget()
        _hw.setStyleSheet("background:transparent;")
        _hl = QVBoxLayout(_hw)
        _hl.setContentsMargins(20, 8, 20, 4)
        _hl.setSpacing(0)
        _hl.addWidget(HelpBlock("Storyboard — Découpage plan par plan", [
            "▸ Chaque ligne représente un plan : numéro, mouvement caméra, valeur, focale, vitesse, décor, acteurs.",
            "▸ Cliquez sur une cellule pour modifier en ligne, ou sur Éditer pour ouvrir la fiche complète du plan.",
            "▸ Glissez-déposez les plans (⠿) pour réorganiser le découpage.",
            "▸ Mood IA : générez automatiquement le prompt Seedance de chaque plan depuis la description de la scène.",
            "▸ Bouton Générer (▶) sur chaque plan : envoie directement le plan vers Seedance 2.0 pour la génération.",
            "▸ Versions : gérez plusieurs versions du découpage (découpage final, alternatives, montage court…).",
        ], CP))
        lay.addWidget(_hw)

        lay.addWidget(self._build_shots_toolbar())
        lay.addWidget(_sep())

        # ── Scrollbar horizontale en haut + zone de plans (avec marges) ──────
        self._top_hscroll = QScrollBar(Qt.Orientation.Horizontal)
        self._top_hscroll.setFixedHeight(12)
        self._top_hscroll.setStyleSheet(
            f"QScrollBar:horizontal{{background:{CP['bg1']};height:12px;border:none;"
            f"border-bottom:1px solid {CP['border']};}}"
            f"QScrollBar::handle:horizontal{{background:{CP['border_bright']};"
            f"border-radius:3px;min-width:32px;margin:2px 2px;}}"
            f"QScrollBar::add-line:horizontal,QScrollBar::sub-line:horizontal{{width:0px;}}"
        )

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        # ScrollBarAsNeeded (not AlwaysOff) lets Qt expand the container beyond
        # viewport width — the key to preventing the accordion compression effect.
        # The native bar is hidden visually (height=0) so only _top_hscroll shows.
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll.setStyleSheet("QScrollArea{background:transparent;border:none;}"
                             "QScrollBar:horizontal{height:0px;}")
        self._scroll = scroll

        self._list_container = _ShotListContainer()
        self._list_container.setStyleSheet("background:transparent;")
        self._list_container.setMinimumWidth(sum(_col_widths) + len(_col_widths) - 1)
        self._list_lay = QVBoxLayout(self._list_container)
        self._list_lay.setContentsMargins(0, 0, 0, 0)
        self._list_lay.setSpacing(0)
        self._list_lay.setAlignment(Qt.AlignmentFlag.AlignTop)
        self._list_container.shot_dropped.connect(self._on_shot_dropped)
        _col_hub.resized.connect(self._on_col_width_changed)
        _col_hub.reordered.connect(self._on_col_reordered)

        scroll.setWidget(self._list_container)

        # Encapsuler scrollbar + table dans un widget avec marges latérales
        table_wrap = QWidget()
        table_wrap.setStyleSheet("background:transparent;")
        tw_lay = QVBoxLayout(table_wrap)
        tw_lay.setContentsMargins(12, 0, 12, 6)
        tw_lay.setSpacing(0)
        tw_lay.addWidget(self._top_hscroll)
        tw_lay.addWidget(scroll, 1)
        self._table_wrap = table_wrap
        lay.addWidget(table_wrap, 1)

        # Message « tableau vide » HORS du scroll : centré dans la fenêtre de
        # façon déterministe (le conteneur de colonnes gardait sa largeur même
        # vide — vu deux fois en réel malgré sizeHint/minimumWidth neutralisés)
        self._empty_lbl = QLabel("")
        self._empty_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._empty_lbl.setWordWrap(True)
        self._empty_lbl.setStyleSheet(
            f"color:{CP['text_dim']};font-size:13px;background:transparent;border:none;"
        )
        self._empty_lbl.setVisible(False)
        lay.addWidget(self._empty_lbl, 1)

        # Synchroniser la scrollbar du haut avec la scrollbar interne du QScrollArea
        h_bar = scroll.horizontalScrollBar()

        def _sync_range(mn: int, mx: int):
            self._top_hscroll.setRange(mn, mx)
            self._top_hscroll.setPageStep(h_bar.pageStep())

        h_bar.rangeChanged.connect(_sync_range)
        h_bar.valueChanged.connect(self._top_hscroll.setValue)
        self._top_hscroll.valueChanged.connect(h_bar.setValue)

        return page

    def _build_shots_topbar(self) -> QWidget:
        bar = QWidget()
        bar.setFixedHeight(60)   # hauteur STANDARD des bandeaux (alignement assistant)
        bar.setStyleSheet(f"background:{CP['bg1']};")
        lay = QHBoxLayout(bar)
        lay.setContentsMargins(20, 0, 20, 0)
        lay.setSpacing(10)

        _ico = QLabel()
        _ico.setFixedSize(26, 26)
        _ico.setAlignment(Qt.AlignmentFlag.AlignCenter)
        _ico.setStyleSheet("background:transparent;")
        _ico_pix = load_icon("storyboard.png", 26)
        if not _ico_pix.isNull():
            _ico.setPixmap(_ico_pix)
        lay.addWidget(_ico)

        title = QLabel("Storyboard")
        title.setStyleSheet(
            f"color:{CP['text_primary']};font-size:18px;font-weight:700;background:transparent;"
        )
        lay.addWidget(title)

        self._version_combo = QComboBox()
        self._version_combo.setFixedHeight(32)
        self._version_combo.setMinimumWidth(220)
        self._version_combo.setStyleSheet(
            f"QComboBox{{background:{CP['bg2']};border:1px solid {CP['border']};"
            f"border-radius:7px;color:{CP['text_primary']};font-size:12px;"
            f"font-weight:600;padding:0 10px;}}"
            f"QComboBox:focus{{border-color:{CP['accent_dim']};}}"
            f"QComboBox::drop-down{{border:none;width:20px;}}"
            f"QComboBox::down-arrow{{image:none;border-left:4px solid transparent;"
            f"border-right:4px solid transparent;border-top:5px solid {CP['text_dim']};"
            f"margin-right:6px;}}"
            f"QComboBox QAbstractItemView{{background:{CP['bg2']};border:1px solid {CP['border_bright']};"
            f"selection-background-color:{CP['accent_dim']};color:{CP['text_primary']};"
            f"font-size:12px;padding:4px;}}"
        )
        self._version_combo.currentIndexChanged.connect(self._on_combo_changed)
        lay.addWidget(self._version_combo)
        self._version_combo.setVisible(False)

        btn_new_ver = QPushButton("＋ Créer un storyboard")
        btn_new_ver.setFixedHeight(32)
        btn_new_ver.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_new_ver.setStyleSheet(
            f"QPushButton{{background:transparent;color:{CP['text_secondary']};"
            f"border:1px solid {CP['border']};border-radius:7px;"
            f"font-size:11px;font-weight:700;padding:0 12px;}}"
            f"QPushButton:hover{{background:{CP['bg2']};color:{CP['text_primary']};"
            f"border-color:{CP['border_bright']};}}"
        )
        btn_new_ver.clicked.connect(self._on_new_version)
        lay.addWidget(btn_new_ver)
        btn_new_ver.setVisible(False)

        # ── Séparateur + versions snapshot ────────────────────────────────────
        _vs = QFrame()
        _vs.setFixedSize(1, 24)
        _vs.setStyleSheet(f"background:{CP['border']};")
        lay.addSpacing(4)
        lay.addWidget(_vs)
        _vs.setVisible(False)
        lay.addSpacing(4)

        _snap_lbl = QLabel("Versions :")
        _snap_lbl.setStyleSheet(
            f"color:{CP['text_dim']};font-size:10px;font-weight:600;"
            f"letter-spacing:0.5px;background:transparent;"
        )
        lay.addWidget(_snap_lbl)
        _snap_lbl.setVisible(False)

        self._snap_combo = QComboBox()
        self._snap_combo.setFixedHeight(30)
        self._snap_combo.setMinimumWidth(160)
        self._snap_combo.setMaximumWidth(220)
        self._snap_combo.setPlaceholderText("Versions…")
        self._snap_combo.setStyleSheet(
            f"QComboBox{{background:{CP['bg2']};border:1px solid {CP['border']};"
            f"border-radius:6px;color:{CP['text_secondary']};font-size:10px;padding:0 8px;}}"
            f"QComboBox:focus{{border-color:{CP['accent2_dim']};}}"
            f"QComboBox::drop-down{{border:none;width:16px;}}"
            f"QComboBox::down-arrow{{image:none;border-left:4px solid transparent;"
            f"border-right:4px solid transparent;border-top:5px solid {CP['text_dim']};"
            f"margin-right:4px;}}"
            f"QComboBox QAbstractItemView{{background:{CP['bg2']};border:1px solid {CP['border_bright']};"
            f"selection-background-color:{CP['accent2_dim']};color:{CP['text_primary']};"
            f"font-size:10px;padding:4px;}}"
        )
        self._snap_combo.currentIndexChanged.connect(self._on_snap_selected)
        self._snap_combo.activated.connect(self._on_snap_activated)
        lay.addWidget(self._snap_combo)
        self._snap_combo.setVisible(False)

        _snap_btn_ss = (
            f"QPushButton{{background:transparent;color:{CP['text_dim']};"
            f"border:1px solid {CP['border']};border-radius:6px;"
            f"font-size:11px;font-weight:700;padding:0 8px;}}"
            f"QPushButton:hover:enabled{{background:{CP['bg2']};color:{CP['text_primary']};"
            f"border-color:{CP['border_bright']};}}"
            f"QPushButton:disabled{{color:{CP['bg3']};border-color:{CP['bg3']};}}"
        )
        self._btn_save_snap = QPushButton("✚")
        self._btn_save_snap.setFixedSize(30, 30)
        self._btn_save_snap.setToolTip("Sauvegarder une version du storyboard")
        self._btn_save_snap.setStyleSheet(_snap_btn_ss)
        self._btn_save_snap.clicked.connect(self._on_save_snapshot)
        lay.addWidget(self._btn_save_snap)
        self._btn_save_snap.setVisible(False)

        self._btn_del_snap = QPushButton("✕")
        self._btn_del_snap.setFixedSize(30, 30)
        self._btn_del_snap.setToolTip("Supprimer la version sélectionnée")
        self._btn_del_snap.setEnabled(False)
        self._btn_del_snap.setStyleSheet(
            _snap_btn_ss
            + f"QPushButton:hover:enabled{{color:{CP['red']};border-color:{CP['red']};"
            f"background:rgba(255,79,106,0.1);}}"
        )
        self._btn_del_snap.clicked.connect(self._on_delete_snapshot)
        lay.addWidget(self._btn_del_snap)
        self._btn_del_snap.setVisible(False)

        lay.addStretch(1)

        self._dur_lbl = QLabel("")
        self._dur_lbl.setStyleSheet(
            f"color:{CP['text_secondary']};font-size:10px;"
            f"font-family:'Consolas',monospace;background:transparent;"
        )
        lay.addWidget(self._dur_lbl)
        return bar

    def _build_shots_toolbar(self) -> QWidget:
        bar = QWidget()
        bar.setMinimumHeight(52)
        bar.setStyleSheet(f"background:{CP['bg0']};")
        lay = QHBoxLayout(bar)
        lay.setContentsMargins(20, 8, 20, 8)
        lay.setSpacing(10)

        self._ai_lbl = QLabel("")
        self._ai_lbl.setStyleSheet(
            f"color:{CP['text_dim']};font-size:10px;font-family:'Consolas',monospace;"
            f"background:transparent;"
        )
        self._ai_lbl.setMinimumWidth(0)
        # (ajouté au layout APRÈS Moods/Caler — boutons d'IA à GAUCHE, actions à droite)

        self._mood_progress = QProgressBar()
        self._mood_progress.setRange(0, 100)
        self._mood_progress.setValue(0)
        self._mood_progress.setTextVisible(False)
        self._mood_progress.setFixedHeight(6)
        self._mood_progress.setMinimumWidth(60)
        self._mood_progress.setMaximumWidth(180)
        self._mood_progress.setVisible(False)
        self._mood_progress.setStyleSheet(
            f"QProgressBar{{background:{CP['bg3']};border:none;border-radius:3px;}}"
            f"QProgressBar::chunk{{background:{CP['accent']};border-radius:3px;}}"
        )

        # Hidden analyze button kept so callbacks (_on_shots_generated, _on_ai_fail) work
        self._btn_analyze = QPushButton()
        self._btn_analyze.setVisible(False)

        _sync_accent = CP.get("accent2", "#7c6bff")
        self._btn_sync = QPushButton("⟳  Synchronisation")
        self._btn_sync.setFixedHeight(34)
        self._btn_sync.setToolTip(
            "Synchronise les prompts Seedance avec les descriptions actuelles\n"
            "du casting, des décors, accessoires, HMC et véhicules.\n"
            "Rapproche les noms légèrement différents (ex : « Le Samouraï » ↔ « samouraï »).\n"
            "Utilise Claude Haiku pour détecter et corriger les incohérences."
        )
        self._btn_sync.setStyleSheet(
            f"QPushButton{{background:transparent;color:{_sync_accent};"
            f"border:1px solid {_sync_accent};border-radius:8px;"
            f"font-size:11px;font-weight:700;padding:0 14px;}}"
            f"QPushButton:hover{{background:rgba(124,107,255,0.12);}}"
            f"QPushButton:pressed{{background:rgba(124,107,255,0.22);}}"
            f"QPushButton:disabled{{color:{CP['text_dim']};border-color:{CP['border']};}}"
        )
        self._btn_sync.clicked.connect(self._on_sync)
        lay.addWidget(self._btn_sync)
        # Héritage Cinéma retiré (validé) : la synchro réaligne les prompts sur les
        # fiches casting/décors — sans objet en Live (prompts issus du découpage).
        self._btn_sync.setVisible(False)

        self._btn_batch_mood = QPushButton("✦  Générer les Moods")
        self._btn_batch_mood.setFixedHeight(34)
        self._btn_batch_mood.setStyleSheet(
            f"QPushButton{{background:transparent;color:{CP['accent']};"
            f"border:1px solid {CP['accent']};border-radius:8px;"
            f"font-size:11px;font-weight:700;padding:0 14px;}}"
            f"QPushButton:hover{{background:rgba(78,205,196,0.12);}}"
            f"QPushButton:pressed{{background:rgba(78,205,196,0.22);}}"
            f"QPushButton:disabled{{color:{CP['text_dim']};border-color:{CP['border']};}}"
        )
        self._btn_batch_mood.clicked.connect(self._on_batch_mood)
        lay.addWidget(self._btn_batch_mood)

        self._btn_music_align = QPushButton("♫  " + translate("Caler sur la musique"))
        self._btn_music_align.setFixedHeight(34)
        self._btn_music_align.setToolTip(translate(
            "Quantise les durées en MESURES (BPM du morceau assigné) et attire les cuts "
            "sur les DROPS — calage exact, calculé localement (pas par l'IA)."))
        self._btn_music_align.setStyleSheet(
            f"QPushButton{{background:transparent;color:{CP['accent']};"
            f"border:1px solid {CP['accent']};border-radius:8px;"
            f"font-size:11px;font-weight:700;padding:0 14px;}}"
            f"QPushButton:hover{{background:rgba(78,205,196,0.12);}}"
            f"QPushButton:pressed{{background:rgba(78,205,196,0.22);}}"
            f"QPushButton:disabled{{color:{CP['text_dim']};border-color:{CP['border']};}}"
        )
        self._btn_music_align.clicked.connect(self._on_music_align)
        lay.addWidget(self._btn_music_align)

        # Boutons d'IA (Moods / Caler) à GAUCHE — la progression et le statut
        # les suivent, puis l'espace extensible pousse les actions à droite.
        lay.addWidget(self._mood_progress)
        lay.addWidget(self._ai_lbl, 1)

        # Sauvegarder / Ouvrir un storyboard + Pitch deck (portés du Cinéma).
        _yellow, _blue, _green = "#f5c518", "#4aa3ff", "#37d366"
        self._btn_save_sb_file = QPushButton("💾  Sauvegarder")
        self._btn_save_sb_file.setFixedHeight(34)
        self._btn_save_sb_file.setToolTip("Sauvegarder ce storyboard sous un nom (dossier Storyboard du projet)")
        self._btn_save_sb_file.setStyleSheet(
            f"QPushButton{{background:transparent;color:{_yellow};"
            f"border:1px solid {_yellow};border-radius:8px;font-size:11px;font-weight:700;padding:0 14px;}}"
            f"QPushButton:hover{{background:rgba(245,197,24,0.12);}}"
            f"QPushButton:pressed{{background:rgba(245,197,24,0.22);}}"
        )
        self._btn_save_sb_file.clicked.connect(self._on_save_storyboard_file)
        lay.addWidget(self._btn_save_sb_file)

        self._btn_open_sb_file = QPushButton("📂  Ouvrir")
        self._btn_open_sb_file.setFixedHeight(34)
        self._btn_open_sb_file.setToolTip("Ouvrir un storyboard sauvegardé")
        self._btn_open_sb_file.setStyleSheet(
            f"QPushButton{{background:transparent;color:{_blue};"
            f"border:1px solid {_blue};border-radius:8px;font-size:11px;font-weight:700;padding:0 14px;}}"
            f"QPushButton:hover{{background:rgba(74,163,255,0.12);}}"
            f"QPushButton:pressed{{background:rgba(74,163,255,0.22);}}"
        )
        self._btn_open_sb_file.clicked.connect(self._on_open_storyboard_file)
        lay.addWidget(self._btn_open_sb_file)

        self._btn_pitch_deck = QPushButton("🎬  Pitch deck")
        self._btn_pitch_deck.setFixedHeight(34)
        self._btn_pitch_deck.setToolTip(
            "Exporter un dossier de présentation (couverture, casting, découpage) — PDF, images PNG ou HTML")
        self._btn_pitch_deck.setStyleSheet(
            f"QPushButton{{background:transparent;color:{_green};"
            f"border:1px solid {_green};border-radius:8px;font-size:11px;font-weight:700;padding:0 14px;}}"
            f"QPushButton:hover{{background:rgba(55,211,102,0.12);}}"
            f"QPushButton:pressed{{background:rgba(55,211,102,0.22);}}"
        )
        self._btn_pitch_deck.clicked.connect(self._on_export_pitch_deck)
        lay.addWidget(self._btn_pitch_deck)

        btn_new = QPushButton("＋  Ajouter un plan")
        btn_new.setFixedHeight(34)
        btn_new.setStyleSheet(
            f"QPushButton{{background:{CP['accent']};color:#07080f;"
            f"border:none;border-radius:8px;font-size:11px;font-weight:700;padding:0 14px;}}"
            f"QPushButton:hover{{background:#6eded6;}}"
            f"QPushButton:pressed{{background:{CP['accent_dim']};color:#fff;}}"
        )
        btn_new.clicked.connect(self._on_new)
        lay.addWidget(btn_new)

        self._btn_clear_shots = QPushButton("✕  Supprimer")
        self._btn_clear_shots.setFixedHeight(34)
        self._btn_clear_shots.setStyleSheet(
            f"QPushButton{{background:transparent;color:{CP['red']};"
            f"border:1px solid {CP['red']};border-radius:8px;"
            f"font-size:11px;font-weight:700;padding:0 14px;}}"
            f"QPushButton:hover{{background:rgba(220,50,50,0.12);}}"
            f"QPushButton:pressed{{background:rgba(220,50,50,0.25);}}"
            f"QPushButton:disabled{{color:{CP['text_dim']};border-color:{CP['border']};}}"
        )
        self._btn_clear_shots.setToolTip("Supprimer tous les plans du découpage actuel pour le régénérer")
        self._btn_clear_shots.clicked.connect(self._on_clear_shots)
        lay.addWidget(self._btn_clear_shots)

        self._btn_del_sb = QPushButton("Supprimer")
        self._btn_del_sb.setFixedHeight(34)
        self._btn_del_sb.setStyleSheet(
            f"QPushButton{{background:transparent;color:{CP['red']};"
            f"border:1px solid {CP['red']};border-radius:8px;"
            f"font-size:11px;font-weight:700;padding:0 14px;}}"
            f"QPushButton:hover{{background:rgba(220,50,50,0.12);}}"
            f"QPushButton:pressed{{background:rgba(220,50,50,0.25);}}"
            f"QPushButton:disabled{{color:{CP['text_dim']};border-color:{CP['border']};}}"
        )
        self._btn_del_sb.clicked.connect(self._on_delete_current_version)
        lay.addWidget(self._btn_del_sb)
        self._btn_del_sb.setVisible(False)
        return bar

    def _fill_version_combo(self):
        self._version_combo.blockSignals(True)
        self._version_combo.clear()
        versions = sb_api.list_versions()
        if not versions:
            self._version_combo.addItem("Aucun découpage", "")
            self._version_combo.setCurrentIndex(0)
            self._version_combo.blockSignals(False)
            self._btn_del_sb.setEnabled(False)
            return
        for v in versions:
            n = v.get("shot_count", 0)
            label = v["name"] + (f"  ({n} plan{'s' if n != 1 else ''})" if n else "")
            self._version_combo.addItem(label, v["id"])
        for i in range(self._version_combo.count()):
            if self._version_combo.itemData(i) == self._active_version_id:
                self._version_combo.setCurrentIndex(i)
                break
        else:
            # ID actif absent de la liste → sélectionner le premier
            self._version_combo.setCurrentIndex(0)
            self._active_version_id = self._version_combo.itemData(0) or ""
        self._version_combo.blockSignals(False)
        self._btn_del_sb.setEnabled(len(versions) > 1)

    def _on_combo_changed(self, index: int):
        if index < 0:
            return
        vid = self._version_combo.itemData(index)
        if vid and vid != self._active_version_id:
            self._active_version_id = vid
            self._all_shots = sb_api.list_shots(vid)
            self._refresh_snap_combo()
            self._render()

    def open_version(self, version_id: str):
        """Ouvre directement une version par son ID (appelé depuis la navigation externe)."""
        self._active_version_id = version_id
        self._fill_version_combo()
        self._all_shots = sb_api.list_shots(version_id)
        self._refresh_snap_combo()
        self._render()

    # ── Snapshot methods ──────────────────────────────────────────────────────

    def _refresh_snap_combo(self):
        self._snap_combo.blockSignals(True)
        self._snap_combo.clear()
        snaps = sb_api.list_snapshots(self._active_version_id)
        for s in snaps:
            label = f"#{s['num']} — {s['name']}"
            self._snap_combo.addItem(label, s["id"])
        self._snap_combo.blockSignals(False)
        self._btn_del_snap.setEnabled(self._snap_combo.count() > 0 and self._snap_combo.currentIndex() >= 0)

    def _on_snap_selected(self, idx: int):
        self._btn_del_snap.setEnabled(idx >= 0 and self._snap_combo.count() > 0)

    def _on_snap_activated(self, idx: int):
        if idx < 0:
            return
        snap_id = self._snap_combo.itemData(idx)
        snap_name = self._snap_combo.itemText(idx)
        reply = QMessageBox.question(
            self,
            "Restaurer une version",
            f"Restaurer la version « {snap_name} » ?\n\nLe storyboard actuel sera remplacé.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        sb_api.restore_snapshot(snap_id, self._active_version_id)
        self._all_shots = sb_api.list_shots(self._active_version_id)
        self._render()

    def _on_save_storyboard_file(self):
        """Sauvegarder le storyboard sous un nom (porté du Cinéma)."""
        from PyQt6.QtWidgets import QFileDialog, QMessageBox
        import os
        if not self._all_shots:
            QMessageBox.information(self, "Sauvegarder", "Le storyboard est vide.")
            return
        from core import context as _ctx
        suggested = sb_api._safe_name(_ctx.get_project_name() or "Storyboard") + ".json"
        start = os.path.join(sb_api.saves_dir(), suggested)
        path, _ = QFileDialog.getSaveFileName(
            self, translate("Sauvegarder le storyboard"), start,
            "Storyboard PANDORA (*.json)")
        if not path:
            return
        if not path.lower().endswith(".json"):
            path += ".json"
        try:
            sb_api.export_storyboard_to(path, self._active_version_id)
            QMessageBox.information(self, "Sauvegardé", "Storyboard sauvegardé.")
        except Exception as e:
            QMessageBox.critical(self, "Erreur", f"Échec de la sauvegarde : {e}")

    def _on_open_storyboard_file(self):
        """Ouvrir un storyboard sauvegardé (porté du Cinéma)."""
        from PyQt6.QtWidgets import QFileDialog, QMessageBox
        path, _ = QFileDialog.getOpenFileName(
            self, translate("Ouvrir un storyboard"), sb_api.saves_dir(),
            "Storyboard PANDORA (*.json)")
        if not path:
            return
        if QMessageBox.question(
                self, "Ouvrir",
                "Charger ce storyboard ? Les plans actuels de cette version seront remplacés.",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        ) != QMessageBox.StandardButton.Yes:
            return
        try:
            n = sb_api.import_storyboard_from(path, self._active_version_id)
            self.refresh()
            QMessageBox.information(self, "Ouvert", f"{n} plan(s) chargé(s).")
        except Exception as e:
            QMessageBox.critical(self, "Erreur", f"Échec de l'ouverture : {e}")

    def _on_export_pitch_deck(self):
        """Exporter un dossier de présentation (PDF / PNG / HTML) — porté du Cinéma.
        Côté Live, la section Décors est simplement omise (pas de page Décors)."""
        from PyQt6.QtWidgets import QFileDialog, QMessageBox
        import os
        shots = [s for s in (self._all_shots or [])]
        if not shots:
            QMessageBox.information(
                self, translate("Pitch deck"),
                translate("Aucun plan à présenter — générez d'abord un storyboard."))
            return
        try:
            import core.context as _ctx
            proj_name = _ctx.get_project_name() if hasattr(_ctx, "get_project_name") else ""
        except Exception:
            proj_name = ""
        safe = "".join(c for c in (proj_name or "PANDORA") if c.isalnum() or c in " -_").strip() or "PANDORA"
        default_path = os.path.join(os.path.expanduser("~"), f"{safe} - pitch deck.pdf")
        _F_PDF  = "PDF (*.pdf)"
        _F_PNG  = translate("Images PNG (*.png)")
        _F_HTML = translate("Présentation HTML (*.html)")
        path, sel = QFileDialog.getSaveFileName(
            self, translate("Exporter le pitch deck"), default_path,
            f"{_F_PDF};;{_F_PNG};;{_F_HTML}")
        if not path:
            return
        low = path.lower()
        if   low.endswith(".pdf"):  fmt = "pdf"
        elif low.endswith(".png"):  fmt = "png"
        elif low.endswith(".html") or low.endswith(".htm"): fmt = "html"
        elif sel == _F_PNG:  fmt = "png"
        elif sel == _F_HTML: fmt = "html"
        else:                fmt = "pdf"
        if not (low.endswith(".pdf") or low.endswith(".png")
                or low.endswith(".html") or low.endswith(".htm")):
            path += {"pdf": ".pdf", "png": ".png", "html": ".html"}[fmt]
        try:
            import core.casting as _ca, core.decors as _dc
            import core.pitch_deck as pdk
            kwargs = dict(project={"name": proj_name} if proj_name else {},
                          shots=shots, characters=_ca.list_characters(),
                          decors=_dc.list_decors())
            if fmt == "pdf":
                written = pdk.export_pitch_deck_pdf(path, **kwargs)
            elif fmt == "png":
                imgs = pdk.export_pitch_deck_images(path, **kwargs)
                written = imgs[0] if imgs else path
            else:
                written = pdk.export_pitch_deck(path, **kwargs)
        except Exception as e:
            _msg = translate("Échec de l'export :")
            QMessageBox.critical(self, translate("Erreur"), f"{_msg} {e}")
            return
        _open_lbl = (translate("Ouvrir le dossier des images ?") if fmt == "png"
                     else translate("L'ouvrir ?"))
        if QMessageBox.question(
                self, translate("Pitch deck"),
                translate("Dossier de présentation exporté ✓") + f"\n\n{_open_lbl}",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        ) == QMessageBox.StandardButton.Yes:
            try:
                from PyQt6.QtGui import QDesktopServices
                from PyQt6.QtCore import QUrl
                target = os.path.dirname(written) if fmt == "png" else written
                QDesktopServices.openUrl(QUrl.fromLocalFile(target))
            except Exception:
                pass

    def _on_save_snapshot(self):
        name, ok = QInputDialog.getText(
            self,
            "Nouvelle version",
            "Nom de la version :",
            text="",
        )
        if not ok or not name.strip():
            return
        sb_api.save_snapshot(name.strip(), self._active_version_id)
        self._refresh_snap_combo()
        # Select the newly saved snapshot (last item)
        last_idx = self._snap_combo.count() - 1
        if last_idx >= 0:
            self._snap_combo.setCurrentIndex(last_idx)

    def _on_delete_snapshot(self):
        idx = self._snap_combo.currentIndex()
        if idx < 0:
            return
        snap_id = self._snap_combo.itemData(idx)
        snap_name = self._snap_combo.itemText(idx)
        reply = QMessageBox.question(
            self,
            "Supprimer la version",
            f"Supprimer définitivement la version « {snap_name} » ?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        sb_api.delete_snapshot(snap_id)
        self._refresh_snap_combo()

    def refresh(self):
        self._fill_version_combo()
        self._all_shots = sb_api.list_shots(self._active_version_id)
        self._refresh_snap_combo()
        self._render()

    def _on_col_width_changed(self, col_idx: int, new_w: int):
        total = sum(_col_widths) + len(_col_widths) - 1
        self._list_container.setMinimumWidth(total)
        self._list_container.updateGeometry()

    def _load_conductor_tracks(self) -> list:
        """Morceaux (nom + BPM) du conducteur d'où vient ce découpage — colonne Musique."""
        try:
            import core.scenario as _sc
            scs = _sc.list_scenarios()
            sc_id = next((s.get("scenario_id") for s in self._all_shots
                          if s.get("scenario_id")), "")
            chosen = next((s for s in scs if s.get("id") == sc_id), None) if sc_id else None
            if chosen is None:
                chosen = next((s for s in scs if s.get("music_tracks")), None)
            tracks = (chosen or {}).get("music_tracks", []) or []
            return [t for t in tracks if isinstance(t, dict) and t.get("name")]
        except Exception:
            return []

    def _on_music_align(self):
        """Cale le découpage sur la musique : durées en mesures + cuts sur les drops.
        Calcul LOCAL et déterministe (core/music_align) — aperçu avant application."""
        tracks = self._load_conductor_tracks()
        analyzed = [t for t in tracks if t.get("bpm")]
        if not analyzed:
            QMessageBox.information(
                self, translate("Musique non analysée"),
                translate("Aucun morceau analysé.\n\nDans le Conducteur, ajoute tes morceaux "
                          "dans « Musiques du set » puis clique « Analyser le set » "
                          "(BPM + drops) avant de caler le découpage."))
            return
        if not self._all_shots:
            QMessageBox.information(
                self, translate("Aucun plan"),
                translate("Cette séquence ne contient aucun plan à caler."))
            return
        from core.music_align import align_shots_to_music, assign_tracks_to_shots
        # Colonnes Musique/BPM : assignation AUTO du morceau couvrant chaque plan
        assigns = assign_tracks_to_shots(self._all_shots, analyzed)
        changes = align_shots_to_music(self._all_shots, analyzed)
        modified = [c for c in changes if abs(c["new"] - c["old"]) >= 0.05]
        if not modified and not assigns:
            QMessageBox.information(
                self, translate("Déjà calé"),
                translate("Toutes les durées sont déjà calées sur les mesures et les drops ✓"))
            return
        snapped = sum(1 for c in changes if c["snapped_drop"])
        old_total = sum(c["old"] for c in changes)
        new_total = sum(c["new"] for c in changes)
        _lines = [f"  Plan {c['number']} : {c['old']:.1f}s → {c['new']:.1f}s"
                  + ("  ⚡ drop" if c["snapped_drop"] else "")
                  for c in modified[:12]]
        if len(modified) > 12:
            _lines.append(f"  … +{len(modified) - 12}")
        _msg = (f"{len(modified)} {translate('plan(s) ajusté(s) en mesures')} · "
                f"{snapped} {translate('cut(s) sur un drop')}\n")
        if assigns:
            _msg += f"{len(assigns)} {translate('plan(s) → colonnes Musique/BPM remplies')}\n"
        _msg += f"{translate('Durée totale :')} {old_total:.1f}s → {new_total:.1f}s\n\n"
        reply = QMessageBox.question(
            self, translate("Caler sur la musique"),
            _msg + "\n".join(_lines) + "\n\n" + translate("Appliquer ?"),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Yes,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        by_id = {s.get("id"): s for s in self._all_shots}
        dirty: set = set()
        for a in assigns:
            shot = by_id.get(a["id"])
            if shot is not None:
                shot["music_track"] = a["track"]
                dirty.add(a["id"])
        for c in modified:
            shot = by_id.get(c["id"])
            if shot is not None:
                shot["duration"] = c["new"]
                dirty.add(c["id"])
        for sid in dirty:
            sb_api.save_shot(by_id[sid])
        self.refresh()

    def _render(self):
        # Colonnes masquées selon le mode de la page (Mapping en masque plusieurs).
        global _HIDDEN_COLS
        _HIDDEN_COLS = set(getattr(self, "_hidden_cols", set()) or set())
        # Reload column order from project config
        order = sb_api.load_col_order(len(_COLS))
        # Pas de personnalisation sauvegardée → ordre par défaut de la page
        # (Live : TC/Durée/BPM/Musique/Transition/Notes en tête, acteurs/accessoires en fin)
        if order == list(range(len(_COLS))) and self._default_col_order \
                and sorted(self._default_col_order) == list(range(len(_COLS))):
            order = list(self._default_col_order)
        _col_order[:] = order

        while self._list_lay.count():
            item = self._list_lay.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        if not self._all_shots:
            no_version = not self._active_version_id or self._active_version_id == DEFAULT_VERSION_ID
            msg = (
                "Aucun découpage pour ce projet.\n\nGénère un découpage depuis le Conducteur."
                if no_version else
                "Aucun plan dans ce découpage.\n\nClique ＋ Ajouter un plan pour créer un plan manuellement."
            )
            # Pas de tableau → on masque ENTIÈREMENT la zone tableau (scroll +
            # scrollbar) et on affiche le message dans un label dédié, centré
            # dans la fenêtre de façon déterministe
            self._list_container._empty_mode = True
            self._list_container.setMinimumWidth(0)
            self._empty_lbl.setText(translate(msg))
            self._table_wrap.setVisible(False)
            self._empty_lbl.setVisible(True)
            self._dur_lbl.setText("")
            return

        # Tableau présent → zone tableau rétablie, message masqué
        self._list_container._empty_mode = False
        self._list_container.setMinimumWidth(sum(_col_widths) + len(_col_widths) - 1)
        self._empty_lbl.setVisible(False)
        self._table_wrap.setVisible(True)

        total_dur = sum(float(s.get("duration", 5.0)) for s in self._all_shots)
        mins = int(total_dur) // 60
        secs = int(total_dur) % 60
        self._dur_lbl.setText(
            f"{len(self._all_shots)} plans  ·  {total_dur:.1f}s total"
            + (f"  ·  ≈{mins}m{secs:02d}s" if mins else "")
        )

        self._list_lay.addWidget(_ResizableHeader())

        self._shot_rows = {}
        decors_cache = {d["id"]: d for d in dec_api.list_decors()}
        avail_tracks = self._load_conductor_tracks()
        _cum = 0.0   # timecode cumulé (début de chaque plan)
        for shot in self._all_shots:
            mins, secs = divmod(int(_cum), 60)
            start_tc = f"{mins}:{secs:02d}"
            row = _ShotRow(shot, decors_cache=decors_cache,
                           start_tc=start_tc, avail_tracks=avail_tracks)
            try:
                _cum += float(shot.get("duration", 5.0))
            except (TypeError, ValueError):
                _cum += 5.0
            row.edit_requested.connect(self._on_edit)
            row.delete_requested.connect(self._on_delete)
            row.changed.connect(self.refresh)
            row.sound_requested.connect(self.sound_to_studio)
            self._shot_rows[shot["id"]] = row
            self._list_lay.addWidget(row)
            self._list_lay.addWidget(_RowResizeHandle(row))

        self._list_lay.addStretch()
        QTimer.singleShot(0, lambda: _col_hub.resized.emit(4, _col_widths[4]))

    # ── Actions ───────────────────────────────────────────────────────────────

    def _on_new(self):
        next_num = max((s.get("number", 0) for s in self._all_shots), default=0) + 1
        # Auto-suggest next notation from last shot (same sequence, next plan/seq)
        last = self._all_shots[-1] if self._all_shots else {}
        try:
            last_siq = int(last.get("shot_in_seq", 0))
        except (TypeError, ValueError):
            last_siq = 0
        dlg = ShotDialog(self, shot={
            "number":      next_num,
            "version_id":  self._active_version_id,
            "seq_num":     last.get("seq_num", 1),
            "seq_name":    last.get("seq_name", ""),
            "shot_in_seq": last_siq + 1,
        })
        if dlg.exec() == ShotDialog.DialogCode.Accepted:
            self.refresh()

    def _on_edit(self, shot: dict):
        fresh = sb_api.get_shot(shot.get("id", "")) or shot
        dlg = ShotDialog(self, shot=fresh)
        if dlg.exec() == ShotDialog.DialogCode.Accepted:
            self.refresh()

    def _on_delete(self, shot_id: str):
        shot = sb_api.get_shot(shot_id)
        num = shot.get("number", "?") if shot else "?"
        reply = QMessageBox.question(
            self, "Supprimer",
            f"Supprimer le plan {num} ?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            sb_api.delete_shot(shot_id)
            self.refresh()

    def _on_shot_dropped(self, shot_id: str, target_index: int):
        """Reorders shots after a drag-and-drop: moves shot_id to target_index."""
        shots = list(self._all_shots)
        drag_idx = next(
            (i for i, s in enumerate(shots) if s.get("id") == shot_id), None
        )
        if drag_idx is None:
            return
        shot = shots.pop(drag_idx)
        if drag_idx < target_index:
            target_index = max(0, target_index - 1)
        shots.insert(target_index, shot)
        sb_api.reorder_shots(
            self._active_version_id, [s["id"] for s in shots]
        )
        self.refresh()

    def _on_analyze(self):
        import core.scenario as scenario_api
        scenarios = scenario_api.list_scenarios()
        if not scenarios:
            QMessageBox.information(
                self, "Aucun scénario",
                "Aucun scénario disponible.\nCrée ou importe un scénario dans l'onglet Scénario d'abord."
            )
            return

        if len(scenarios) == 1:
            sc = scenarios[0]
        else:
            sc = self._pick_scenario(scenarios)
            if not sc:
                return

        text = sc.get("formatted_content") or sc.get("raw_content", "")
        if not text:
            QMessageBox.warning(self, "Scénario vide", "Le scénario sélectionné est vide.")
            return

        reply = QMessageBox.question(
            self, "Générer le storyboard",
            f"Générer un découpage depuis « {sc.get('title', 'Scénario sans titre')} » ?\n"
            "Les nouveaux plans seront ajoutés à cette version.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        from api.screenplay import GenerateStoryboardWorker
        self._btn_analyze.setEnabled(False)
        self._ai_lbl.setText("Génération du découpage via Claude…")
        self._worker = GenerateStoryboardWorker(text)
        sc_id = sc.get("id", "")
        self._worker.finished.connect(lambda shots: self._on_shots_generated(shots, sc_id))
        self._worker.failed.connect(self._on_ai_fail)
        self._worker.start()
        self._show_analysis_dialog(sc)

    def _show_analysis_dialog(self, sc: dict):
        from ui.styles import PANDORA_STYLESHEET
        self._analysis_dlg = QDialog(self)
        self._analysis_dlg.setWindowTitle(translate("Génération du storyboard"))
        self._analysis_dlg.setFixedSize(440, 210)
        self._analysis_dlg.setStyleSheet(
            PANDORA_STYLESHEET + f"QDialog{{background:{CP['bg1']};}}"
        )
        self._analysis_dlg.setWindowFlags(
            self._analysis_dlg.windowFlags()
            & ~Qt.WindowType.WindowContextHelpButtonHint
        )

        lay = QVBoxLayout(self._analysis_dlg)
        lay.setContentsMargins(32, 28, 32, 28)
        lay.setSpacing(14)

        title_lbl = QLabel(translate("Analyse du scénario via Claude IA"))
        title_lbl.setStyleSheet(
            f"color:{CP['text_primary']};font-size:15px;font-weight:700;background:transparent;"
        )
        lay.addWidget(title_lbl)

        sc_name = sc.get("title", "Scénario sans titre")
        info_lbl = QLabel(
            f"« {sc_name} »\n"
            + translate("Génération du découpage en plans… Cette opération peut prendre quelques secondes.")
        )
        info_lbl.setWordWrap(True)
        info_lbl.setStyleSheet(
            f"color:{CP['text_secondary']};font-size:11px;background:transparent;"
        )
        lay.addWidget(info_lbl)

        prog = QProgressBar()
        prog.setRange(0, 0)
        prog.setFixedHeight(4)
        prog.setTextVisible(False)
        prog.setStyleSheet(
            f"QProgressBar{{background:{CP['bg3']};border:none;border-radius:2px;}}"
            f"QProgressBar::chunk{{background:{CP['accent2']};border-radius:2px;}}"
        )
        lay.addWidget(prog)

        btn_cancel = QPushButton(translate("Annuler"))
        btn_cancel.setFixedHeight(36)
        btn_cancel.setStyleSheet(
            f"QPushButton{{background:transparent;color:{CP['text_secondary']};"
            f"border:1px solid {CP['border']};border-radius:8px;"
            f"font-size:12px;font-weight:700;padding:0 16px;}}"
            f"QPushButton:hover{{background:{CP['bg3']};color:{CP['text_primary']};}}"
        )
        btn_cancel.clicked.connect(self._cancel_analysis)
        lay.addWidget(btn_cancel, alignment=Qt.AlignmentFlag.AlignRight)

        self._analysis_dlg.exec()

    def _pick_scenario(self, scenarios: list) -> dict | None:
        from PyQt6.QtWidgets import QDialog, QListWidget, QListWidgetItem, QDialogButtonBox
        from ui.styles import PANDORA_STYLESHEET

        dlg = QDialog(self)
        dlg.setWindowTitle(translate("Choisir un scénario"))
        dlg.setFixedSize(420, 320)
        dlg.setStyleSheet(PANDORA_STYLESHEET + f"QDialog{{background:{CP['bg1']};}}")

        lay = QVBoxLayout(dlg)
        lay.setContentsMargins(20, 20, 20, 20)
        lay.setSpacing(12)

        lbl = QLabel(translate("Sélectionne le scénario à analyser :"))
        lbl.setStyleSheet(f"color:{CP['text_primary']};font-size:12px;background:transparent;")
        lay.addWidget(lbl)

        lst = QListWidget()
        lst.setStyleSheet(
            f"QListWidget{{background:{CP['bg2']};border:1px solid {CP['border']};"
            f"border-radius:8px;color:{CP['text_primary']};font-size:12px;}}"
            f"QListWidget::item{{padding:8px 12px;}}"
            f"QListWidget::item:selected{{background:{CP['accent_dim']};color:{CP['text_primary']};}}"
        )
        for sc in scenarios:
            item = QListWidgetItem(sc.get("title") or "Scénario sans titre")
            item.setData(Qt.ItemDataRole.UserRole, sc)
            lst.addItem(item)
        lst.setCurrentRow(0)
        lay.addWidget(lst, 1)

        btns = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        btns.setStyleSheet(
            f"QPushButton{{background:{CP['accent']};color:#07080f;border:none;"
            f"border-radius:6px;font-size:12px;font-weight:700;padding:6px 16px;}}"
            f"QPushButton:hover{{background:#6eded6;}}"
        )
        btns.accepted.connect(dlg.accept)
        btns.rejected.connect(dlg.reject)
        lay.addWidget(btns)

        if dlg.exec() == QDialog.DialogCode.Accepted:
            selected = lst.currentItem()
            return selected.data(Qt.ItemDataRole.UserRole) if selected else None
        return None

    def _on_shots_generated(self, shots: list, sc_id: str):
        if hasattr(self, "_analysis_dlg") and self._analysis_dlg:
            self._analysis_dlg.accept()
        self._btn_analyze.setEnabled(True)
        decors = dec_api.list_decors()
        decor_by_name = {d["name"].strip().lower(): d["id"] for d in decors}
        for shot in shots:
            shot["scenario_id"] = sc_id
            shot["version_id"]  = self._active_version_id
            if shot.get("decor_name") and not shot.get("decor_id"):
                shot["decor_id"] = decor_by_name.get(shot["decor_name"].strip().lower(), "")
            sb_api.save_shot(shot)
        self._ai_lbl.setText(f"{len(shots)} {translate('plans importés ✓')}")
        self.refresh()

    def _on_ai_fail(self, err: str):
        if hasattr(self, "_analysis_dlg") and self._analysis_dlg:
            self._analysis_dlg.reject()
        self._btn_analyze.setEnabled(True)
        self._ai_lbl.setText(f"Erreur : {err[:100]}")

    # ── Génération batch des Moods ────────────────────────────────────────────

    def _on_batch_mood(self):
        if self._batch_mood_worker and self._batch_mood_worker.isRunning():
            self._batch_mood_worker.cancel()
            self._btn_batch_mood.setEnabled(False)
            self._ai_lbl.setText("Annulation en cours…")
            return

        if not self._all_shots:
            return

        # Dialog d'info (une seule fois, sauf si l'utilisateur a coché "Ne plus afficher")
        from core.config import load_config, save_config
        cfg = load_config()
        if not cfg.get("mood_batch_info_shown"):
            info_dlg = _MoodInfoDialog(self)
            if info_dlg.exec() != QDialog.DialogCode.Accepted:
                return
            if info_dlg.skip_next_time():
                cfg["mood_batch_info_shown"] = True
                save_config(cfg)

        dlg = _MoodBatchDialog(self, self._all_shots)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return

        selected = dlg.selected_shots()
        if not selected:
            return

        from api.apercu import MoodBatchWorker
        self._batch_mood_worker = MoodBatchWorker(selected)
        self._batch_mood_worker.shot_progress.connect(self._on_batch_mood_progress)
        self._batch_mood_worker.shot_done.connect(self._on_batch_mood_done)
        self._batch_mood_worker.shot_failed.connect(self._on_batch_mood_failed)
        self._batch_mood_worker.all_done.connect(self._on_batch_mood_all_done)
        self._batch_mood_worker.start()

        self._mood_progress.setMaximum(len(selected))
        self._mood_progress.setValue(0)
        self._mood_progress.setVisible(True)

        self._btn_batch_mood.setText("⏹  Arrêter")
        self._btn_batch_mood.setStyleSheet(
            f"QPushButton{{background:transparent;color:{CP['red']};"
            f"border:1px solid {CP['red']};border-radius:8px;"
            f"font-size:11px;font-weight:700;padding:0 14px;}}"
            f"QPushButton:hover{{background:rgba(220,50,50,0.12);}}"
            f"QPushButton:pressed{{background:rgba(220,50,50,0.22);}}"
        )

    def _on_batch_mood_progress(self, current: int, total: int, msg: str):
        self._ai_lbl.setText(f"Mood {current}/{total} — {msg}")
        self._mood_progress.setValue(current)

    def _on_batch_mood_done(self, shot_id: str, image_path: str):
        row = self._shot_rows.get(shot_id)
        if row:
            row._on_apercu_changed(shot_id, image_path)

    def _on_batch_mood_failed(self, shot_id: str, err: str):
        self._ai_lbl.setText(f"Erreur plan {shot_id[:8]}… : {err[:80]}")

    def _on_batch_mood_all_done(self):
        was_cancelled = getattr(self._batch_mood_worker, "_was_cancelled", False)
        self._batch_mood_worker = None
        self._mood_progress.setVisible(False)
        self._btn_batch_mood.setText("✦  Générer les Moods")
        self._btn_batch_mood.setEnabled(True)
        self._btn_batch_mood.setStyleSheet(
            f"QPushButton{{background:transparent;color:{CP['accent']};"
            f"border:1px solid {CP['accent']};border-radius:8px;"
            f"font-size:11px;font-weight:700;padding:0 14px;}}"
            f"QPushButton:hover{{background:rgba(78,205,196,0.12);}}"
            f"QPushButton:pressed{{background:rgba(78,205,196,0.22);}}"
            f"QPushButton:disabled{{color:{CP['text_dim']};border-color:{CP['border']};}}"
        )
        self._ai_lbl.setText("Génération annulée" if was_cancelled else "✓ Moods générés")

    def _on_col_reordered(self, new_order: list):
        _col_order[:] = new_order
        sb_api.save_col_order(new_order)
        self._render()

    def _cancel_analysis(self):
        if self._worker:
            abandon_thread(self._worker)
        if hasattr(self, "_analysis_dlg") and self._analysis_dlg:
            self._analysis_dlg.reject()
        self._btn_analyze.setEnabled(True)
        self._ai_lbl.setText("Analyse annulée")
