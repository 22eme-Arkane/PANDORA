from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QScrollArea,
    QFrame, QGridLayout, QTextEdit,
)
from PyQt6.QtCore import Qt, pyqtSignal
from core.i18n import translate
from ui.styles import CP
import core.style as style_api


def _hex_to_rgb(h: str) -> tuple[int, int, int]:
    h = h.lstrip("#")
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)


# ── Style card ────────────────────────────────────────────────────────────────

class _StyleCard(QWidget):
    selected = pyqtSignal(str)  # key

    def __init__(self, style: dict):
        super().__init__()
        self._key    = style["key"]
        self._active = False
        self._color  = style["color"]
        r, g, b      = _hex_to_rgb(self._color)
        self._rgba_bg  = f"rgba({r},{g},{b},0.18)"
        self._rgba_bdr = self._color

        self.setFixedSize(206, 118)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        content_w = QWidget()
        content_w.setObjectName("content")
        lay = QVBoxLayout(content_w)
        lay.setContentsMargins(12, 10, 12, 8)
        lay.setSpacing(5)

        top = QHBoxLayout()
        top.setSpacing(8)
        top.setContentsMargins(0, 0, 0, 0)

        self._icon_lbl = QLabel(style["icon"])
        self._icon_lbl.setFixedSize(32, 32)
        self._icon_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._icon_lbl.setStyleSheet(
            f"font-size:18px;background:rgba(255,255,255,0.05);"
            f"border-radius:8px;border:none;"
        )
        top.addWidget(self._icon_lbl)

        name_lbl = QLabel(style["name"])
        name_lbl.setStyleSheet(
            f"color:{CP['text_primary']};font-size:11px;font-weight:800;"
            f"background:transparent;border:none;"
        )
        name_lbl.setWordWrap(True)
        top.addWidget(name_lbl, 1)

        self._check = QLabel("✓")
        self._check.setFixedSize(18, 18)
        self._check.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._check.setStyleSheet(
            f"color:#07080f;background:{self._color};"
            f"border-radius:9px;font-size:10px;font-weight:900;border:none;"
        )
        self._check.setVisible(False)
        top.addWidget(self._check)
        lay.addLayout(top)

        desc_lbl = QLabel(style["description"])
        desc_lbl.setWordWrap(True)
        desc_lbl.setStyleSheet(
            f"color:{CP['text_dim']};font-size:9px;"
            f"background:transparent;border:none;"
        )
        lay.addWidget(desc_lbl, 1)

        outer.addWidget(content_w, 1)

        self._underline = QFrame()
        self._underline.setFixedHeight(3)
        self._underline.setStyleSheet(
            f"background:{self._color};border:none;border-radius:0 0 10px 10px;"
        )
        self._underline.setVisible(False)
        outer.addWidget(self._underline)

        self._content_w = content_w
        self._apply_style()

    def _apply_style(self):
        if self._active:
            self._content_w.setStyleSheet(
                f"QWidget#content{{background:{self._rgba_bg};"
                f"border:2px solid {self._rgba_bdr};"
                f"border-bottom:none;"
                f"border-radius:10px 10px 0 0;}}"
            )
            self._check.setVisible(True)
            self._underline.setVisible(True)
            self._icon_lbl.setStyleSheet(
                f"font-size:18px;background:{self._color};"
                f"border-radius:8px;border:none;color:#07080f;"
            )
        else:
            self._content_w.setStyleSheet(
                f"QWidget#content{{background:{CP['bg2']};"
                f"border:1px solid {CP['border']};"
                f"border-radius:10px;}}"
            )
            self._check.setVisible(False)
            self._underline.setVisible(False)
            self._icon_lbl.setStyleSheet(
                f"font-size:18px;background:rgba(255,255,255,0.05);"
                f"border-radius:8px;border:none;"
            )

    def set_active(self, active: bool):
        if self._active == active:
            return
        self._active = active
        self._apply_style()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.selected.emit(self._key)
        super().mousePressEvent(event)


# ── Page ──────────────────────────────────────────────────────────────────────

_COLS = 5  # cards per row within a group


class PageStyle(QWidget):

    def __init__(self):
        super().__init__()
        self.setStyleSheet(f"background:{CP['bg0']};")
        self._cards: dict[str, _StyleCard] = {}
        self._custom_edit = None

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        root.addWidget(self._build_topbar())
        root.addWidget(self._build_separator())
        root.addWidget(self._build_body(), 1)

    # ── Topbar ────────────────────────────────────────────────────────────────

    def _build_topbar(self) -> QWidget:
        bar = QWidget()
        bar.setFixedHeight(60)
        bar.setStyleSheet(f"background:{CP['bg1']};")
        bl = QHBoxLayout(bar)
        bl.setContentsMargins(32, 0, 32, 0)

        title = QLabel("Univers cinématographique")
        title.setStyleSheet(
            f"color:{CP['text_primary']};font-size:22px;font-weight:700;background:transparent;"
        )
        bl.addWidget(title)
        bl.addStretch()

        self._active_badge = QLabel("")
        self._active_badge.setFixedHeight(28)
        self._active_badge.setVisible(False)
        self._active_badge.setStyleSheet(
            f"color:{CP['bg0']};background:{CP['accent']};"
            f"border-radius:8px;font-size:11px;font-weight:700;"
            f"padding:0 12px;"
        )
        bl.addWidget(self._active_badge)

        return bar

    def _build_separator(self) -> QFrame:
        f = QFrame()
        f.setFixedHeight(1)
        f.setStyleSheet(f"background:{CP['border']};")
        return f

    # ── Body ──────────────────────────────────────────────────────────────────

    def _build_body(self) -> QWidget:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet("QScrollArea{background:transparent;border:none;}")

        container = QWidget()
        container.setStyleSheet("background:transparent;")
        lay = QVBoxLayout(container)
        lay.setContentsMargins(32, 24, 32, 40)
        lay.setSpacing(0)

        lay.addWidget(self._build_info_block())
        lay.addSpacing(24)

        for group in style_api.GROUPS:
            group_styles = [s for s in style_api.STYLES if s.get("group") == group["key"]]
            if not group_styles:
                continue
            lay.addWidget(self._build_group_header(group))
            lay.addSpacing(10)
            lay.addWidget(self._build_group_grid(group_styles))
            lay.addSpacing(40)

        lay.addWidget(self._build_custom_block())
        lay.addStretch()
        scroll.setWidget(container)
        return scroll

    def _build_info_block(self) -> QWidget:
        frame = QFrame()
        frame.setStyleSheet(
            f"QFrame{{background:rgba(78,205,196,0.07);"
            f"border:1px solid rgba(78,205,196,0.25);border-radius:12px;}}"
        )
        fl = QHBoxLayout(frame)
        fl.setContentsMargins(20, 14, 20, 14)
        fl.setSpacing(14)

        icon = QLabel("◈")
        icon.setFixedSize(38, 38)
        icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon.setStyleSheet(
            f"font-size:20px;color:{CP['accent']};"
            f"background:rgba(78,205,196,0.12);border-radius:10px;border:none;"
        )
        fl.addWidget(icon)

        text = QLabel(
            "Choisissez l'univers visuel de votre projet pour influencer toutes les créations "
            "dans le style correspondant — personnages, costumes, décors, accessoires et vidéos Seedance 2.0. "
            "Un film réaliste génèrera de vraies photos, une animation 3D des rendus CGI, etc."
        )
        text.setWordWrap(True)
        text.setStyleSheet(
            f"color:{CP['text_secondary']};font-size:12px;background:transparent;border:none;"
        )
        fl.addWidget(text, 1)
        return frame

    def _build_group_header(self, group: dict) -> QWidget:
        w = QWidget()
        w.setStyleSheet("background:transparent;")
        hl = QHBoxLayout(w)
        hl.setContentsMargins(0, 0, 0, 0)
        hl.setSpacing(10)

        icon_lbl = QLabel(group["icon"])
        icon_lbl.setFixedSize(26, 26)
        icon_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon_lbl.setStyleSheet(
            f"font-size:14px;background:rgba(255,255,255,0.06);"
            f"border-radius:6px;border:none;"
        )
        hl.addWidget(icon_lbl)

        name_lbl = QLabel(group["name"].upper())
        name_lbl.setStyleSheet(
            f"color:{CP['text_secondary']};font-size:10px;font-weight:700;"
            f"font-family:'Consolas',monospace;letter-spacing:1.2px;"
            f"background:transparent;border:none;"
        )
        hl.addWidget(name_lbl)

        line = QFrame()
        line.setFixedHeight(1)
        line.setStyleSheet(f"background:{CP['border']};border:none;")
        hl.addWidget(line, 1)

        return w

    def _build_group_grid(self, styles: list) -> QWidget:
        grid_w = QWidget()
        grid_w.setStyleSheet("background:transparent;")
        grid = QGridLayout(grid_w)
        grid.setSpacing(10)
        grid.setContentsMargins(0, 0, 0, 0)

        for i, s in enumerate(styles):
            card = _StyleCard(s)
            card.selected.connect(self._on_select)
            self._cards[s["key"]] = card
            grid.addWidget(card, i // _COLS, i % _COLS)

        rem = len(styles) % _COLS
        if rem:
            for j in range(rem, _COLS):
                ph = QWidget()
                ph.setFixedSize(206, 118)
                ph.setStyleSheet("background:transparent;")
                grid.addWidget(ph, len(styles) // _COLS, j)

        return grid_w

    def _build_custom_block(self) -> QWidget:
        self._custom_frame = QFrame()
        self._custom_frame.setStyleSheet(
            f"QFrame{{background:{CP['bg1']};border:1px solid {CP['border']};border-radius:12px;}}"
        )
        fl = QVBoxLayout(self._custom_frame)
        fl.setContentsMargins(20, 16, 20, 16)
        fl.setSpacing(8)

        header = QHBoxLayout()
        lbl = QLabel("Description libre du style")
        lbl.setStyleSheet(
            f"color:{CP['text_primary']};font-size:12px;font-weight:700;"
            f"background:transparent;border:none;"
        )
        hint = QLabel("Précise le style ou décris la fusion pour Multi-style")
        hint.setStyleSheet(
            f"color:{CP['text_dim']};font-size:10px;background:transparent;border:none;"
        )
        header.addWidget(lbl)
        header.addStretch()
        header.addWidget(hint)
        fl.addLayout(header)

        self._custom_edit = QTextEdit()
        self._custom_edit.setFixedHeight(72)
        self._custom_edit.setPlaceholderText(
            "Ex: « Mélange de prises de vue réelles et d'effets d'animation 2D, "
            "style Roger Rabbit, couleurs vives sur fond naturaliste… »"
        )
        self._custom_edit.setStyleSheet(
            f"QTextEdit{{background:{CP['bg3']};border:1px solid {CP['border']};"
            f"border-radius:8px;color:{CP['text_primary']};font-size:12px;padding:8px;}}"
            f"QTextEdit:focus{{border-color:{CP['accent']};}}"
        )
        self._custom_edit.textChanged.connect(self._on_custom_changed)
        fl.addWidget(self._custom_edit)

        return self._custom_frame

    # ── Logic ─────────────────────────────────────────────────────────────────

    def _on_select(self, key: str):
        for k, card in self._cards.items():
            card.set_active(k == key)

        style = next((s for s in style_api.STYLES if s["key"] == key), None)
        if style:
            self._active_badge.setText(f"  {style['icon']}  {translate(style['name'])}  ")
            self._active_badge.setStyleSheet(
                f"color:{CP['bg0']};background:{style['color']};"
                f"border-radius:8px;font-size:11px;font-weight:700;"
                f"padding:0 4px;"
            )
            self._active_badge.setVisible(True)

        custom = self._custom_edit.toPlainText().strip() if self._custom_edit else ""
        style_api.set_style(key, custom)

    def _on_custom_changed(self):
        key = style_api.get_style_key()
        custom = self._custom_edit.toPlainText().strip() if self._custom_edit else ""
        if key:
            style_api.set_style(key, custom)

    def refresh(self):
        """Reload current style from storage and sync card states."""
        key = style_api.get_style_key()
        for k, card in self._cards.items():
            card.set_active(k == key)

        if key:
            style = next((s for s in style_api.STYLES if s["key"] == key), None)
            if style:
                self._active_badge.setText(f"  {style['icon']}  {translate(style['name'])}  ")
                self._active_badge.setStyleSheet(
                    f"color:{CP['bg0']};background:{style['color']};"
                    f"border-radius:8px;font-size:11px;font-weight:700;"
                    f"padding:0 4px;"
                )
                self._active_badge.setVisible(True)
        else:
            self._active_badge.setVisible(False)

        if self._custom_edit:
            custom = style_api.get_style_custom()
            self._custom_edit.blockSignals(True)
            self._custom_edit.setPlainText(custom)
            self._custom_edit.blockSignals(False)
