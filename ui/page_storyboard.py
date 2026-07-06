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
from ui.dialog_shot import ShotDialog
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
    ("Séq",           78,  False),  # 2
    ("Plan",          52,  False),  # 3
    ("Prompt",       280,  False),  # 4  seedance_prompt
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
    ("Langues",      120,  False),  # 16 dialogue_lang (traduit à l'envoi Seedance)
    ("Nom du plan",  150,  False),  # 17 scene_title (nom du plan) — affiché après « Plan »
    ("",              78,  False),  # 18 Boutons
    ("Hauteur",       64,  False),  # 19 camera_height (à côté de Dist.)
    ("Référence",    100,  False),  # 20 reference_images — inspiration → rôle « reference »
]

_HEURE_PRESETS = HEURE_PRESETS

# Mutable column widths — shared by header and all rows; updated on drag-resize
_col_widths: list[int] = [w for _, w, _ in _COLS]

# Mutable column visual order — list of logical column indices in left→right display order.
# Index 0 (grip) reste en tête et la colonne Boutons (dernière) reste en queue ; le reste
# est réordonnable. « Nom du plan » (logique 17) s'affiche par défaut juste après « Plan »
# (logique 3). Loaded from project config in PageStoryboard._render().
_DEFAULT_COL_ORDER: list[int] = [0, 1, 20, 2, 3, 17, 4, 5, 6, 7, 8, 9, 19, 10, 11, 12, 13, 14, 15, 16, 18]
_col_order: list[int] = list(_DEFAULT_COL_ORDER)


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


def _contrast_text(hexc: str) -> str:
    """Texte noir ou blanc selon la luminance d'une couleur hex — pour rester
    lisible quand le libellé couleur remplit le fond de la cellule Séquence."""
    h = (hexc or "").lstrip("#")
    if len(h) != 6:
        return "#ffffff"
    try:
        r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    except ValueError:
        return "#ffffff"
    return "#07080f" if (0.299 * r + 0.587 * g + 0.114 * b) > 150 else "#ffffff"


# ── Dialogue helpers ──────────────────────────────────────────────────────────

def _text_dialog(parent: QWidget, title: str, initial: str = "",
                 placeholder: str = "", enhance: bool = False) -> str | None:
    """Styled multi-line text editor dialog. Returns new text or None if cancelled."""
    from ui.styles import PANDORA_STYLESHEET
    dlg = QDialog(parent)
    dlg.setWindowTitle(title)
    # Redimensionnable (poignée) + taille par défaut CONFORTABLE, plafonnée à 85 %
    # de l'écran disponible → jamais plus grand que l'affichage (pas de crop).
    from PyQt6.QtGui import QGuiApplication
    _scr = QGuiApplication.primaryScreen().availableGeometry()
    _w = min(920, int(_scr.width() * 0.85))
    _h = min(640, int(_scr.height() * 0.85))
    dlg.setMinimumSize(min(480, _w), min(240, _h))
    dlg.resize(_w, _h)
    dlg.setSizeGripEnabled(True)
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

        for i, col_logical in enumerate(_col_order):
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
            if i < len(_col_order) - 1:
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
                    # Perform reorder: move src to tgt position
                    new_order = list(_col_order)
                    item = new_order.pop(src)
                    new_order.insert(tgt, item)
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
    edit_requested      = pyqtSignal(dict)
    delete_requested    = pyqtSignal(str)
    duplicate_requested = pyqtSignal(str)
    changed             = pyqtSignal()

    _MIN_H = 72

    def contextMenuEvent(self, e):
        """Clic droit sur un plan : Éditer · Dupliquer · Supprimer."""
        menu = QMenu(self)
        menu.setStyleSheet(
            f"QMenu{{background:{CP['bg2']};border:1px solid {CP['border_bright']};"
            f"border-radius:8px;padding:4px 0;}}"
            f"QMenu::item{{color:{CP['text_primary']};padding:7px 18px;font-size:11px;}}"
            f"QMenu::item:selected{{background:{CP['accent_dim']};color:{CP['text_primary']};}}")
        menu.addAction(translate("Éditer"), lambda: self.edit_requested.emit(self._data))
        menu.addAction(translate("Dupliquer le plan"),
                       lambda: self.duplicate_requested.emit(self._data.get("id", "")))
        import core.storyboard as _sb
        from PyQt6.QtGui import QPixmap, QIcon, QColor

        def _color_submenu(title, setter, none_label):
            s = menu.addMenu(translate(title))
            s.setStyleSheet(menu.styleSheet())
            for cname, chex in _sb.LABEL_COLORS:
                _pm = QPixmap(12, 12)
                _pm.fill(QColor(chex))
                a = s.addAction(QIcon(_pm), translate(cname))
                a.triggered.connect(lambda _=False, c=chex: setter(c))
            s.addSeparator()
            s.addAction(translate(none_label), lambda: setter(""))

        # Deux repères DISTINCTS : libellé couleur ESTHÉTIQUE (bande) ↔ FLAG « plan
        # récurrent » (coin de la vignette, clé de groupe Rendu/Audio).
        _color_submenu("Libellé couleur", self._set_label, "Aucun libellé")
        _color_submenu("Plan récurrent", self._set_recurrent, "Pas récurrent")
        menu.addSeparator()
        menu.addAction(translate("Supprimer"),
                       lambda: self.delete_requested.emit(self._data.get("id", "")))
        menu.exec(e.globalPos())

    def _set_label(self, color: str):
        """Libellé couleur ESTHÉTIQUE (bande gauche) — clic droit → Libellé couleur."""
        import core.storyboard as sb
        sb.set_label(self._data.get("id", ""), color, "")
        self.changed.emit()

    def _set_recurrent(self, color: str):
        """FLAG « plan récurrent » (coin) — clic droit → Plan récurrent."""
        import core.storyboard as sb
        sb.set_recurrent(self._data.get("id", ""), color, "")
        self.changed.emit()

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

        return max(
            self._MIN_H,
            _h((self._data.get("seedance_prompt", "") or "")[:300], 4, 9),
            _h(self._data.get("scene_title", "") or "", 17, 10),
            _h(", ".join(self._data.get("accessory_names", []) or []), 12, 9),
            _h(", ".join(self._data.get("character_names", []) or []), 13, 10),
        )

    def sizeHint(self):
        from PyQt6.QtCore import QSize
        return QSize(max(self.minimumWidth(), 100), self._content_height())

    def minimumSizeHint(self):
        from PyQt6.QtCore import QSize
        return QSize(max(self.minimumWidth(), 100), self._content_height())

    def __init__(self, data: dict, decors_cache: dict | None = None):
        super().__init__()
        self._data    = data
        self._pmt_lbl = None  # set after build; used by _content_height()
        self.setMinimumHeight(self._MIN_H)

        try:
            pal_idx = (int(data.get("seq_num", 1)) - 1) % len(_SEQ_PALETTE)
        except (TypeError, ValueError):
            pal_idx = 0
        row_bg, seq_bg, seq_color = _SEQ_PALETTE[pal_idx]

        # Libellé couleur ESTHÉTIQUE : appliqué en FOND de la cellule Séquence
        # (cf. plus bas) — PLUS de bande à gauche (sans intérêt). Le flag « plan
        # récurrent » reste un coin sur la vignette.
        _lc = (data.get("label_color") or "").strip()
        self.setStyleSheet(
            f"QFrame{{background:{row_bg};border:none;"
            f"border-top:1px solid {CP['border']};}}"
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

        # Champs caméra → alimentent la section [🖼️ TECHNIQUE] du prompt.
        _CAM_FIELDS = ("camera_movement", "shot_size", "focal", "optic", "speed")

        def _rebuild_technique():
            """Réécrit INSTANTANÉMENT la section [🖼️ TECHNIQUE] du prompt depuis les
            champs caméra (uniquement si le prompt est déjà structuré en sections)."""
            try:
                from core.prompt_sections import (is_structured as _isS, parse as _pp,
                                                  build as _pb, technique_line as _tl)
                p = self._data.get("seedance_prompt", "")
                if not _isS(p):
                    return
                sec = _pp(p)
                tech = _tl(self._data)
                if tech != sec.get("technique", ""):
                    self._data["seedance_prompt"] = _pb(
                        action=sec["action"], staging=sec["staging"], ambiance=sec["ambiance"],
                        decor=sec["decor"], lighting=sec["lighting"], technique=tech,
                        sound=sec["sound"] or self._data.get("sound_prompt", ""))
            except Exception:
                pass

        def _save_field(key: str, value):
            self._data[key] = value
            if key in _CAM_FIELDS:
                _rebuild_technique()
            sb_api.save_shot(self._data)
            self.changed.emit()

        def _save_fields(updates: dict):
            self._data.update(updates)
            if any(k in _CAM_FIELDS for k in updates):
                _rebuild_technique()
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

        # FLAG « plan récurrent » dans le coin haut-droit de la vignette (façon
        # DaVinci) — couleur = groupe. Distinct du libellé couleur esthétique (bande).
        _rc = (data.get("recurrent_color") or "").strip()
        if _rc:
            _flag = QLabel(img_lbl)
            _flag.setFixedSize(14, 14)
            _flag.move(86 - 14, 0)
            _rtxt = data.get("recurrent_text", "") or ""
            _flag.setToolTip(translate("Plan récurrent") + (f" · {_rtxt}" if _rtxt else ""))
            _flag.setStyleSheet(
                f"background:{_rc};border:1px solid #07080f;border-bottom-left-radius:9px;")
            _flag.show()

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

        # ── Référence (col 20) — images d'INSPIRATION injectées en génération ──
        ref_w = QWidget()
        ref_w.setFixedWidth(_col_widths[20])
        ref_w.setMinimumHeight(self._MIN_H)
        ref_w.setStyleSheet("background:transparent;")
        ref_l = QVBoxLayout(ref_w)
        ref_l.setContentsMargins(3, 4, 3, 4)
        ref_l.setAlignment(Qt.AlignmentFlag.AlignCenter)
        ref_lbl = QLabel()
        ref_lbl.setFixedSize(86, 58)
        ref_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        ref_lbl.setWordWrap(True)

        def _render_ref(lbl=ref_lbl, shot_data=data):
            _rps = [p for p in (shot_data.get("reference_images") or []) if os.path.isfile(p)]
            if _rps:
                pix = QPixmap(_rps[0]).scaled(
                    86, 58, Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                    Qt.TransformationMode.SmoothTransformation)
                pix = pix.copy((pix.width()-86)//2, (pix.height()-58)//2, 86, 58)
                lbl.setPixmap(pix)
                lbl.setText("")
                lbl.setStyleSheet(f"background:{CP['bg3']};border:none;")
                lbl.setToolTip(translate("Images de référence (inspiration)")
                               + (f" · {len(_rps)}" if len(_rps) > 1 else ""))
            else:
                lbl.setPixmap(QPixmap())
                lbl.setStyleSheet(
                    f"background:{CP['bg3']};border:1px dashed {CP['border_bright']};"
                    f"color:{CP['accent_dim']};font-size:8px;padding:4px;")
                lbl.setText(translate("＋ Réf"))
                lbl.setToolTip(translate("Ajouter des images de référence (inspiration)"))
        _render_ref()
        ref_lbl.setCursor(Qt.CursorShape.PointingHandCursor)

        def _open_refs(lbl=ref_lbl, shot_data=data, row_self=self):
            from ui.dialog_reference_images import ReferenceImagesDialog
            dlg = ReferenceImagesDialog(shot_data.get("reference_images", []), row_self.window())
            if dlg.exec():
                shot_data["reference_images"] = dlg.result_paths()
                sb_api.save_shot(shot_data)
                _render_ref(lbl, shot_data)
        _clickable(ref_lbl, _open_refs)
        ref_l.addWidget(ref_lbl)
        cells[20] = ref_w

        # ── Séq ──────────────────────────────────────────────────────────────
        seq_w = QWidget()
        seq_w.setFixedWidth(_col_widths[2])
        seq_w.setMinimumHeight(self._MIN_H)
        # Fond de la cellule = libellé couleur esthétique s'il est défini, sinon la
        # couleur de séquence par défaut. Texte contrasté pour rester lisible.
        seq_w.setStyleSheet(f"background:{_lc or seq_bg};")
        _seq_txt = _contrast_text(_lc) if _lc else seq_color
        seq_lay = QVBoxLayout(seq_w)
        seq_lay.setContentsMargins(6, 8, 6, 8)
        seq_lay.setSpacing(2)
        seq_lay.setAlignment(Qt.AlignmentFlag.AlignCenter)
        sq = data.get("seq_num", "")
        sn = data.get("seq_name", "")
        if sq is not None and str(sq):
            n = QLabel(f"S{sq}")
            n.setAlignment(Qt.AlignmentFlag.AlignCenter)
            n.setStyleSheet(
                f"color:{_seq_txt};font-size:22px;font-weight:800;"
                f"font-family:'Consolas',monospace;background:transparent;border:none;"
            )
            seq_lay.addWidget(n)
        if sn:
            s2 = QLabel(sn)
            s2.setAlignment(Qt.AlignmentFlag.AlignCenter)
            s2.setWordWrap(True)
            s2.setStyleSheet(
                f"color:{_seq_txt};font-size:8px;font-weight:700;"
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

        # ── Nom du plan (scene_title) ─────────────────────────────────────────
        nom_w, nom_l = _cell(_col_widths[17], fill=True)
        nom_l.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        _nom_full = data.get("scene_title", "") or ""
        _nom_lbl = _lbl(_nom_full or "—", size=10)
        if _nom_full:
            _nom_lbl.setToolTip(_nom_full)
        nom_l.addWidget(_nom_lbl)
        def _edit_nom():
            v = _text_dialog(self, "Nom du plan", data.get("scene_title", ""))
            if v is not None:
                _save_field("scene_title", v)
        _clickable(nom_w, _edit_nom)
        cells[17] = nom_w

        # ── Prompt Seedance ───────────────────────────────────────────────────
        pmt_w = QWidget()
        pmt_w.setFixedWidth(_col_widths[4])
        pmt_w.setStyleSheet("background:transparent;")
        pmt_l = QVBoxLayout(pmt_w)
        pmt_l.setContentsMargins(7, 8, 6, 6)
        pmt_l.setSpacing(0)
        _full_pmt = data.get("seedance_prompt", "") or ""
        _prev_pmt = (_full_pmt[:300] + "…") if len(_full_pmt) > 300 else (_full_pmt or "—")
        _pmt_lbl = _WrapLabel(_prev_pmt or "—")
        _pmt_lbl.setWordWrap(True)
        _pmt_lbl.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        _pmt_lbl.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        _pmt_lbl.setStyleSheet(
            f"color:{CP['text_dim']};font-size:9px;background:transparent;border:none;"
        )
        if _full_pmt:
            _pmt_lbl.setToolTip(_full_pmt)
        pmt_l.addWidget(_pmt_lbl)
        self._pmt_lbl = _pmt_lbl
        def _edit_prompt():
            v = _text_dialog(self, "Prompt Seedance", data.get("seedance_prompt", ""),
                             enhance=True)
            if v is not None:
                _save_field("seedance_prompt", v)
        _clickable(pmt_w, _edit_prompt)
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

        # ── Hauteur caméra ────────────────────────────────────────────────────
        hgt_w, hgt_l = _cell(_col_widths[19])
        _cur_hgt = data.get("camera_height", "")
        hgt_l.addWidget(_lbl(_cur_hgt or "—", CP["accent_dim"], 10, mono=True))

        def _height_click(_w=hgt_w, _c=_cur_hgt):
            menu = QMenu(self)
            menu.setStyleSheet(
                f"QMenu{{background:{CP['bg2']};border:1px solid {CP['border_bright']};"
                f"border-radius:8px;padding:4px 0;}}"
                f"QMenu::item{{color:{CP['text_primary']};padding:7px 18px;font-size:11px;}}"
                f"QMenu::item:selected{{background:{CP['accent_dim']};color:{CP['text_primary']};}}"
                f"QMenu::item:checked{{color:{CP['accent']};font-weight:700;}}"
            )
            for opt in ("", "0,5 m", "1 m", "1,2 m", "1,7 m", "2 m", "3 m", "5 m"):
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
                    self, translate("Hauteur caméra"),
                    translate("Hauteur (ex : 1,7 m) :"), text=_c
                )
                if ok and text.strip():
                    _save_field("camera_height", text.strip())
            else:
                _save_field("camera_height", chosen.data())

        _clickable(hgt_w, _height_click)
        cells[19] = hgt_w

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

        # ── Langues (dialogue_lang) — traduit à l'ENVOI vers Seedance ─────────
        from core.lang import DIALOGUE_LANGS, lang_label
        lang_w, lang_l = _cell(_col_widths[16])
        _cur_lang = data.get("dialogue_lang", "en") or "en"
        _lang_lbl = _lbl(lang_label(_cur_lang), size=10)
        if _cur_lang == "en":
            _lang_lbl.setStyleSheet(
                f"color:{CP['accent']};font-size:10px;background:transparent;border:none;")
        lang_l.addWidget(_lang_lbl)
        lang_w.setToolTip(translate(
            "Langue des dialogues — traduite automatiquement à l'envoi vers Seedance.\n"
            "Anglais recommandé (meilleur lipsync). Le prompt à l'écran n'est pas modifié."))

        def _pick_lang(anchor=lang_w):
            menu = QMenu(self)
            menu.setStyleSheet(
                f"QMenu{{background:{CP['bg2']};border:1px solid {CP['border_bright']};"
                f"border-radius:8px;padding:4px 0;}}"
                f"QMenu::item{{color:{CP['text_primary']};padding:7px 18px;font-size:11px;}}"
                f"QMenu::item:selected{{background:{CP['accent_dim']};color:{CP['text_primary']};}}"
                f"QMenu::item:checked{{color:{CP['accent']};font-weight:700;}}"
            )
            cur = data.get("dialogue_lang", "en") or "en"
            for _label, _code in DIALOGUE_LANGS:
                act = menu.addAction(_label)
                act.setData(_code)
                act.setCheckable(True)
                act.setChecked(_code == cur)
            chosen = menu.exec(anchor.mapToGlobal(anchor.rect().bottomLeft()))
            if chosen:
                _save_field("dialogue_lang", chosen.data())

        _clickable(lang_w, _pick_lang)
        cells[16] = lang_w

        # ── Boutons ──────────────────────────────────────────────────────────
        btns_w = QWidget()
        btns_w.setFixedWidth(_col_widths[18])
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
        cells[18] = btns_w

        # ── Assemblage des colonnes dans l'ordre visuel (_col_order) ─────────
        for i, col_logical in enumerate(_col_order):
            outer.addWidget(cells[col_logical])
            if i < len(_col_order) - 1:
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
        w = sum(_col_widths) + len(_col_widths) - 1
        return QSize(w, super().minimumSizeHint().height())

    def sizeHint(self):
        from PyQt6.QtCore import QSize
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

        # Conseils
        conseils = [
            ("✍️", "Soigne le prompt Seedance",
             "Le Mood est avant tout un test de prompt et d'ambiance. Plus le champ "
             "\"Prompt Seedance\" du plan est détaillé, plus l'image générée sera "
             "représentative de ce que tu veux obtenir dans Seedance 2.0."),
            ("🎬", "Découpage technique complet",
             "Renseigne la valeur de plan, la focale, l'axe caméra, l'heure et le décor. "
             "Ces paramètres enrichissent automatiquement le prompt pour valider "
             "l'ambiance, l'éclairage et le cadrage avant de lancer Seedance 2.0."),
            ("🎨", "Valider avant de générer la vidéo",
             "Une fois les Moods satisfaisants, ils peuvent servir de base de discussion "
             "et de référence visuelle pour la génération Seedance 2.0. "
             "Ce n'est pas une pré-visualisation fidèle des personnages ou du décor."),
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
        self.setMinimumSize(480, 600)
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

        # ── Options de génération (moteur + références à envoyer) ──────────────
        lay.addWidget(_sep())
        opt_lbl = QLabel(translate("Options de génération :"))
        opt_lbl.setStyleSheet(
            f"color:{CP['text_primary']};font-size:11px;font-weight:600;background:transparent;"
        )
        lay.addWidget(opt_lbl)

        eng_row = QHBoxLayout()
        eng_row.setSpacing(8)
        _eng_lbl = QLabel(translate("Moteur d'image :"))
        _eng_lbl.setStyleSheet(f"color:{CP['text_dim']};font-size:11px;background:transparent;")
        eng_row.addWidget(_eng_lbl)
        self._opt_engine = QComboBox()
        self._opt_engine.addItem(translate("Nano Banana 2 (avec références)"), "nb2")
        self._opt_engine.addItem(translate("Flux (depuis le prompt seul)"), "flux")
        self._opt_engine.setFixedHeight(28)
        self._opt_engine.setStyleSheet(
            f"QComboBox{{background:{CP['bg2']};border:1px solid {CP['border']};"
            f"border-radius:6px;color:{CP['text_primary']};font-size:11px;padding:0 8px;}}"
            f"QComboBox::drop-down{{border:none;width:20px;}}"
            f"QComboBox QAbstractItemView{{background:{CP['bg3']};"
            f"border:1px solid {CP['border_bright']};color:{CP['text_primary']};"
            f"selection-background-color:{CP['accent_dim']};}}"
        )
        eng_row.addWidget(self._opt_engine, 1)
        lay.addLayout(eng_row)

        _cb_style = (
            f"QCheckBox{{color:{CP['text_secondary']};font-size:11px;"
            f"background:transparent;spacing:7px;}}"
            f"QCheckBox::indicator{{width:15px;height:15px;border:1px solid {CP['border_bright']};"
            f"border-radius:4px;background:{CP['bg0']};}}"
            f"QCheckBox::indicator:checked{{background:{CP['accent']};border-color:{CP['accent']};}}"
            f"QCheckBox:disabled{{color:{CP['text_dim']};}}"
        )
        self._opt_chars = QCheckBox(translate("Envoyer les références des personnages"))
        self._opt_decor = QCheckBox(translate("Envoyer la référence du décor"))
        self._opt_floor = QCheckBox(translate("Envoyer le plan d'architecte (repère d'agencement)"))
        for _cb in (self._opt_chars, self._opt_decor, self._opt_floor):
            _cb.setChecked(True)
            _cb.setStyleSheet(_cb_style)
            lay.addWidget(_cb)

        def _sync_engine_opts(*_a):
            # Les références ne concernent que Nano Banana 2 — grisées pour Flux.
            _nb2 = (self._opt_engine.currentData() == "nb2")
            for _c in (self._opt_chars, self._opt_decor, self._opt_floor):
                _c.setEnabled(_nb2)
        self._opt_engine.currentIndexChanged.connect(_sync_engine_opts)
        _sync_engine_opts()

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
            # Feedback explicite si un scénario a été reconstruit : sinon l'utilisateur
            # ne sait pas où regarder (le scénario est dans l'onglet Scénario).
            if getattr(dlg, "_scenario_text", ""):
                self._ai_lbl.setText(translate(
                    "✓ Scénario reconstruit enregistré — ouvre l'onglet Scénario pour le voir."))

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
        lay.addWidget(table_wrap, 1)

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
        lay.addWidget(self._ai_lbl, 1)

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
        lay.addWidget(self._mood_progress)

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

        # Plans récurrents : analyse IA des configurations caméra qui reviennent
        # (champ/contrechamp…) → coloration par groupe.
        self._btn_recurrent = QPushButton("✦  Plans récurrents")
        self._btn_recurrent.setFixedHeight(34)
        self._btn_recurrent.setToolTip(
            "Analyse le storyboard (Claude) pour repérer les configurations caméra\n"
            "RÉCURRENTES par séquence (champ/contrechamp, plans qui reviennent) et\n"
            "colorer chaque groupe d'une couleur distincte. Sélectionnable ensuite\n"
            "d'un bloc pour le Rendu / l'Audio.")
        self._btn_recurrent.setStyleSheet(
            f"QPushButton{{background:transparent;color:{_sync_accent};"
            f"border:1px solid {_sync_accent};border-radius:8px;"
            f"font-size:11px;font-weight:700;padding:0 14px;}}"
            f"QPushButton:hover{{background:rgba(124,107,255,0.12);}}"
            f"QPushButton:pressed{{background:rgba(124,107,255,0.22);}}"
            f"QPushButton:disabled{{color:{CP['text_dim']};border-color:{CP['border']};}}"
        )
        self._btn_recurrent.clicked.connect(self._on_detect_recurrent)
        # Sauvegarder (jaune) / Ouvrir (bleu) — storyboard sauvegardé physiquement
        # dans <projet>/data/Storyboard/ (comme un projet à part).
        _yellow, _blue = "#f5c518", "#4aa3ff"
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

        # Pitch deck (L2) — export d'un dossier de présentation HTML/PDF
        _green = "#37d366"
        self._btn_pitch_deck = QPushButton("🎬  Pitch deck")
        self._btn_pitch_deck.setFixedHeight(34)
        self._btn_pitch_deck.setToolTip(
            "Exporter un dossier de présentation (couverture, casting, décors, découpage) — PDF, images PNG ou HTML")
        self._btn_pitch_deck.setStyleSheet(
            f"QPushButton{{background:transparent;color:{_green};"
            f"border:1px solid {_green};border-radius:8px;font-size:11px;font-weight:700;padding:0 14px;}}"
            f"QPushButton:hover{{background:rgba(55,211,102,0.12);}}"
            f"QPushButton:pressed{{background:rgba(55,211,102,0.22);}}"
        )
        self._btn_pitch_deck.clicked.connect(self._on_export_pitch_deck)

        # « Générer les Moods » tout à gauche, « Synchronisation » à sa droite
        # (retour 2026-06-14) — avant le label/stretch qui pousse le reste à droite
        lay.insertWidget(0, self._btn_batch_mood)
        lay.insertWidget(1, self._btn_sync)
        lay.insertWidget(2, self._btn_recurrent)

        # Sauvegarder / Ouvrir : à droite de « Plans récurrents », séparés par un
        # petit espace + une barre verticale.
        _tb_sep = QWidget()
        _tb_sep.setFixedWidth(1)
        _tb_sep.setFixedHeight(24)
        _tb_sep.setStyleSheet(f"background:{CP['border_bright']};")
        lay.insertSpacing(3, 12)
        lay.insertWidget(4, _tb_sep)
        lay.insertSpacing(5, 12)
        lay.insertWidget(6, self._btn_save_sb_file)
        lay.insertWidget(7, self._btn_open_sb_file)
        lay.insertWidget(8, self._btn_pitch_deck)

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

    # ── Sauvegarde / ouverture physique du storyboard ───────────────────────────

    def _on_save_storyboard_file(self):
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
        """L2 — exporte un dossier de présentation depuis les plans de la version
        courante + casting + décors, au choix en PDF, images PNG ou HTML."""
        from PyQt6.QtWidgets import QFileDialog, QMessageBox
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
        # Format déduit de l'extension saisie, sinon du filtre choisi.
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

        kwargs = {}
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
        # Proposer d'ouvrir le résultat (le fichier, ou le dossier pour les PNG).
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

    def _on_col_width_changed(self, col_idx: int, new_w: int):
        total = sum(_col_widths) + len(_col_widths) - 1
        self._list_container.setMinimumWidth(total)
        self._list_container.updateGeometry()

    def _render(self):
        # Reload column order from project config
        order = sb_api.load_col_order(len(_COLS), _DEFAULT_COL_ORDER)
        _col_order[:] = order

        while self._list_lay.count():
            item = self._list_lay.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        if not self._all_shots:
            no_version = not self._active_version_id or self._active_version_id == DEFAULT_VERSION_ID
            if no_version:
                # Aucun découpage encore généré → bouton de génération en un clic
                # à la place du simple texte (demande Matthieu 2026-07-06).
                empty = QWidget()
                empty.setStyleSheet("background:transparent;")
                _el = QVBoxLayout(empty)
                _el.setContentsMargins(0, 48, 0, 0)
                _el.setSpacing(18)
                _el.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignHCenter)
                _lbl = QLabel(translate("Aucun découpage pour ce projet."))
                _lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
                _lbl.setStyleSheet(
                    f"color:{CP['text_dim']};font-size:13px;background:transparent;border:none;")
                _el.addWidget(_lbl, 0, Qt.AlignmentFlag.AlignHCenter)
                _btn_gen = QPushButton("⊕  " + translate("Générer depuis le scénario"))
                _btn_gen.setCursor(Qt.CursorShape.PointingHandCursor)
                _btn_gen.setFixedHeight(42)
                _btn_gen.setStyleSheet(
                    f"QPushButton{{background:{CP['accent2']};color:#fff;border:none;"
                    f"border-radius:8px;font-size:12px;font-weight:700;padding:0 28px;}}"
                    f"QPushButton:hover{{background:#9d8fff;}}"
                    f"QPushButton:pressed{{background:#6a5acd;}}")
                _btn_gen.clicked.connect(self._on_analyze)
                _el.addWidget(_btn_gen, 0, Qt.AlignmentFlag.AlignHCenter)
                self._list_lay.addWidget(empty)
            else:
                empty = QLabel(translate(
                    "Aucun plan dans ce découpage.\n\nClique ＋ Ajouter un plan pour créer un plan manuellement."))
                empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
                empty.setStyleSheet(
                    f"color:{CP['text_dim']};font-size:13px;background:transparent;border:none;")
                self._list_lay.addWidget(empty)
            self._dur_lbl.setText("")
            return

        total_dur = sum(float(s.get("duration", 5.0)) for s in self._all_shots)
        mins = int(total_dur) // 60
        secs = int(total_dur) % 60
        _n = len(self._all_shots)
        self._dur_lbl.setText(
            f"{_n} plan{'s' if _n > 1 else ''}  ·  {total_dur:.1f}s total"
            + (f"  ·  ≈{mins}m{secs:02d}s" if mins else "")
        )

        self._list_lay.addWidget(_ResizableHeader())

        self._shot_rows = {}
        decors_cache = {d["id"]: d for d in dec_api.list_decors()}
        for shot in self._all_shots:
            row = _ShotRow(shot, decors_cache=decors_cache)
            row.edit_requested.connect(self._on_edit)
            row.delete_requested.connect(self._on_delete)
            row.duplicate_requested.connect(self._on_duplicate)
            row.changed.connect(self.refresh)
            self._shot_rows[shot["id"]] = row
            self._list_lay.addWidget(row)
            self._list_lay.addWidget(_RowResizeHandle(row))

        self._list_lay.addStretch()
        QTimer.singleShot(0, lambda: _col_hub.resized.emit(4, _col_widths[4]))

    # ── Plans récurrents (analyse IA → coloration par groupe) ───────────────────

    def _on_detect_recurrent(self):
        if getattr(self, "_recurrent_worker", None) and self._recurrent_worker.isRunning():
            return
        from api.screenplay import AnalyzeRecurrentShotsWorker
        self._btn_recurrent.setEnabled(False)
        self._btn_recurrent.setText(translate("Analyse…"))
        w = AnalyzeRecurrentShotsWorker(self._active_version_id)
        w.done.connect(self._on_recurrent_done)
        w.failed.connect(self._on_recurrent_fail)
        self._recurrent_worker = w
        w.start()

    def _on_recurrent_done(self, n: int):
        self._btn_recurrent.setEnabled(True)
        self._btn_recurrent.setText("✦  " + translate("Plans récurrents"))
        self.refresh()
        QMessageBox.information(
            self, translate("Plans récurrents"),
            (translate("{n} groupe(s) de plans récurrents identifié(s) et colorés.")
             .format(n=n)) if n else
            translate("Aucun groupe de plans récurrents détecté dans ce storyboard."))

    def _on_recurrent_fail(self, err: str):
        self._btn_recurrent.setEnabled(True)
        self._btn_recurrent.setText("✦  " + translate("Plans récurrents"))
        QMessageBox.warning(self, translate("Plans récurrents"), str(err)[:300])

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

    def _on_duplicate(self, shot_id: str):
        """Duplique un plan (clic droit → Dupliquer) : copie le plan + sa mise en
        scène / plan de feu, insérée juste après l'original."""
        if not shot_id:
            return
        dup = sb_api.duplicate_shot(shot_id)
        if not dup:
            return
        # Duplique aussi la mise en scène / le plan de feu (record staging) du plan.
        try:
            import core.staging as _stg, copy as _copy
            rec = _stg.get(shot_id)
            if rec:
                _stg.save(dup["id"], _copy.deepcopy(rec))
        except Exception:
            pass
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
        from core.ai_provider import ai_name_for_task
        _eng = ai_name_for_task("storyboard_gen")
        self._btn_analyze.setEnabled(False)
        self._ai_lbl.setText(translate("Génération du découpage via {ai}…").format(ai=_eng))
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

        from core.ai_provider import ai_name_for_task
        title_lbl = QLabel(translate("Analyse du scénario via {ai}").format(
            ai=ai_name_for_task("storyboard_gen")))
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
            shot.pop("merged", None)          # champs de travail P2 (non persistés)
            shot.pop("merged_note", None)
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

        # Garde-fou : sans clé fal.ai, la génération NB2 échoue silencieusement —
        # on le dit clairement plutôt que d'afficher un faux « Moods générés ».
        from core.config import load_config, save_config
        if not load_config().get("api_key", "").strip():
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.information(
                self, translate("Générer les Moods"),
                translate("Configure ta clé fal.ai dans Paramètres pour générer les moods."))
            return

        # Dialog d'info (une seule fois, sauf si l'utilisateur a coché "Ne plus afficher")
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

        # Options cochées dans la fenêtre (moteur + références à envoyer).
        _mood_opts = {
            "engine":     dlg._opt_engine.currentData() or "nb2",
            "chars":      dlg._opt_chars.isChecked(),
            "decor":      dlg._opt_decor.isChecked(),
            "floor_plan": dlg._opt_floor.isChecked(),
        }

        # Compteurs de résultat (message final honnête : succès / échecs).
        self._mood_ok = 0
        self._mood_fail = 0
        self._mood_last_err = ""

        from api.apercu import MoodBatchWorker
        self._batch_mood_worker = MoodBatchWorker(selected, options=_mood_opts)
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
        # On ne compte un SUCCÈS que si une vraie image existe — sinon « done »
        # sans image (échec silencieux) ne doit pas se faire passer pour un succès.
        if image_path and os.path.isfile(image_path):
            self._mood_ok = getattr(self, "_mood_ok", 0) + 1
            row = self._shot_rows.get(shot_id)
            if row:
                row._on_apercu_changed(shot_id, image_path)
        else:
            self._mood_fail = getattr(self, "_mood_fail", 0) + 1

    def _on_batch_mood_failed(self, shot_id: str, err: str):
        self._mood_fail = getattr(self, "_mood_fail", 0) + 1
        self._mood_last_err = err or ""
        self._ai_lbl.setText(f"Erreur plan {shot_id[:8]}… : {err[:80]}")

    def _on_batch_mood_all_done(self):
        # PARQUER le worker (abandon_thread) au lieu de « = None » à chaud : le nuller
        # pendant que le thread termine encore peut le faire GC en plein vol → segfault
        # (doctrine PyQt du projet). abandon_thread garde une référence anti-GC.
        w = self._batch_mood_worker
        was_cancelled = getattr(w, "_was_cancelled", False)
        self._batch_mood_worker = None
        if w is not None:
            abandon_thread(w)
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
        ok   = getattr(self, "_mood_ok", 0)
        fail = getattr(self, "_mood_fail", 0)
        last = getattr(self, "_mood_last_err", "")
        if was_cancelled:
            self._ai_lbl.setText("Génération annulée")
        elif ok and not fail:
            self._ai_lbl.setText(f"✓ {ok} mood(s) généré(s)")
        elif ok and fail:
            self._ai_lbl.setText(f"✓ {ok} mood(s) · {fail} échec(s)"
                                 + (f" — {last[:60]}" if last else ""))
        else:
            self._ai_lbl.setText(f"⚠ Aucun mood généré ({fail} échec(s))"
                                 + (f" — {last[:90]}" if last else ""))

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
