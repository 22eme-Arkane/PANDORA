"""
live_window.py — Fenêtre PANDORA | Live (mode spectacle / VJ Resolume).

Structure identique à PandoraWindow : sidebar gauche + stack de pages.
"""

from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QVBoxLayout,
    QLabel, QStackedWidget, QFrame, QPushButton,
)
from PyQt6.QtCore import Qt, pyqtSignal
from ui.styles import CP, PANDORA_STYLESHEET
from ui.icons import app_icon


# ── Item de navigation Live ───────────────────────────────────────────────────

class _LiveNavItem(QWidget):
    nav_clicked = pyqtSignal(str)

    def __init__(self, icon: str, label: str, key: str):
        super().__init__()
        self._key    = key
        self._active = False
        self.setFixedHeight(54)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        outer = QHBoxLayout(self)
        outer.setContentsMargins(10, 3, 8, 3)
        outer.setSpacing(10)
        outer.setAlignment(Qt.AlignmentFlag.AlignVCenter)

        self._ico = QLabel(icon)
        self._ico.setFixedSize(30, 30)
        self._ico.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._ico.setStyleSheet("background:transparent;border:none;font-size:16px;")

        self._frame = QFrame()
        self._frame.setFixedHeight(36)
        fl = QHBoxLayout(self._frame)
        fl.setContentsMargins(10, 0, 10, 0)
        fl.setSpacing(0)

        self._lbl = QLabel(label)
        fl.addWidget(self._lbl)
        fl.addStretch()

        outer.addWidget(self._ico)
        outer.addWidget(self._frame, 1)

        self._apply(False)

    def _apply(self, active: bool):
        accent = CP["accent2"]
        if active:
            self._frame.setStyleSheet(
                f"QFrame{{background:rgba(124,107,255,0.18);"
                f"border:1px solid rgba(124,107,255,0.32);border-radius:8px;}}"
            )
            self._ico.setStyleSheet(
                f"color:{accent};font-size:16px;background:transparent;border:none;"
            )
            self._lbl.setStyleSheet(
                f"color:{accent};font-size:16px;font-weight:700;"
                f"letter-spacing:0.4px;background:transparent;border:none;"
            )
        else:
            self._frame.setStyleSheet(
                "QFrame{background:transparent;border:none;border-radius:8px;}"
            )
            self._ico.setStyleSheet(
                f"color:{CP['text_dim']};font-size:16px;background:transparent;border:none;"
            )
            self._lbl.setStyleSheet(
                f"color:{CP['text_secondary']};font-size:16px;font-weight:600;"
                f"letter-spacing:0.3px;background:transparent;border:none;"
            )

    def setActive(self, active: bool):
        self._active = active
        self._apply(active)

    def enterEvent(self, e):
        if not self._active:
            self._frame.setStyleSheet(
                "QFrame{background:rgba(255,255,255,0.05);"
                "border:1px solid rgba(255,255,255,0.08);border-radius:8px;}"
            )
            self._lbl.setStyleSheet(
                f"color:{CP['text_primary']};font-size:16px;font-weight:600;"
                f"background:transparent;border:none;"
            )

    def leaveEvent(self, e):
        if not self._active:
            self._apply(False)

    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            self.nav_clicked.emit(self._key)


# ── Sidebar Live ──────────────────────────────────────────────────────────────

_NAV_ITEMS = [
    ("◈", "Mapping",     "mapping"),
    None,
    ("⚙", "Paramètres",  "settings"),
]


class _LiveSidebar(QWidget):
    nav_clicked = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self.setFixedWidth(268)
        self.setStyleSheet(
            f"background:{CP['sidebar']};border-right:1px solid {CP['border']};"
        )

        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(2)

        # ── En-tête ────────────────────────────────────────────────────────────
        header = QWidget()
        header.setFixedHeight(76)
        header.setStyleSheet(
            f"background:{CP['bg1']};"
            f"border:none;border-bottom:1px solid {CP['border']};"
        )
        hl = QHBoxLayout(header)
        hl.setContentsMargins(16, 0, 16, 0)
        hl.setSpacing(12)

        badge = QLabel("◈")
        badge.setFixedSize(40, 40)
        badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        badge.setStyleSheet(
            f"background:qlineargradient(x1:0,y1:0,x2:1,y2:1,"
            f"stop:0 {CP['accent2']},stop:1 #a060ff);"
            f"border-radius:10px;color:#fff;font-size:20px;font-weight:900;border:none;"
        )
        hl.addWidget(badge)

        title_col = QVBoxLayout()
        title_col.setSpacing(1)
        t1 = QLabel("PANDORA")
        t1.setStyleSheet(
            f"color:{CP['text_primary']};font-size:14px;font-weight:800;"
            f"letter-spacing:2px;background:transparent;border:none;"
        )
        t2 = QLabel("| Live")
        t2.setStyleSheet(
            f"color:{CP['accent2']};font-size:11px;font-weight:700;"
            f"letter-spacing:1px;background:transparent;border:none;"
        )
        title_col.addWidget(t1)
        title_col.addWidget(t2)
        hl.addLayout(title_col, 1)
        lay.addWidget(header)

        lay.addSpacing(6)

        # ── Items nav ──────────────────────────────────────────────────────────
        self._items: dict[str, _LiveNavItem] = {}
        for entry in _NAV_ITEMS:
            if entry is None:
                lay.addSpacing(2)
                sep = QFrame()
                sep.setFixedHeight(1)
                sep.setStyleSheet("background:rgba(255,255,255,0.07);margin:0 20px;")
                lay.addWidget(sep)
                lay.addSpacing(2)
                continue

            icon, label, key = entry
            if key == "settings":
                lay.addStretch()
                sep2 = QFrame()
                sep2.setFixedHeight(1)
                sep2.setStyleSheet(f"background:{CP['border']};margin:0 12px;")
                lay.addWidget(sep2)
                lay.addSpacing(4)

            item = _LiveNavItem(icon, label, key)
            item.nav_clicked.connect(self.nav_clicked)
            self._items[key] = item
            lay.addWidget(item)

        lay.addSpacing(10)

    def set_active(self, key: str):
        for k, item in self._items.items():
            item.setActive(k == key)


# ── Fenêtre principale ────────────────────────────────────────────────────────

class LiveWindow(QMainWindow):
    """Fenêtre principale du mode PANDORA | Live."""
    closed = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.setWindowTitle("PANDORA | Live")
        self.setMinimumSize(1100, 720)
        self.setStyleSheet(PANDORA_STYLESHEET)

        icon = app_icon()
        if not icon.isNull():
            self.setWindowIcon(icon)

        central = QWidget()
        self.setCentralWidget(central)

        outer = QVBoxLayout(central)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        body = QWidget()
        body.setStyleSheet("background:transparent;")
        body_lay = QHBoxLayout(body)
        body_lay.setContentsMargins(0, 0, 0, 0)
        body_lay.setSpacing(0)

        self._sidebar = _LiveSidebar()
        self._stack   = QStackedWidget()
        self._stack.setStyleSheet(f"background:{CP['bg0']};")

        body_lay.addWidget(self._sidebar)
        body_lay.addWidget(self._stack, 1)
        outer.addWidget(body, 1)

        self._pages: dict[str, QWidget] = {}
        self._build_pages()

        self._sidebar.nav_clicked.connect(self._navigate)
        self._navigate("mapping")

    def _build_pages(self):
        from ui.page_live import PageLive
        self._pages["mapping"] = PageLive()
        self._stack.addWidget(self._pages["mapping"])

        from ui.page_live_settings import PageLiveSettings
        self._pages["settings"] = PageLiveSettings()
        self._stack.addWidget(self._pages["settings"])

    def _navigate(self, key: str):
        if key not in self._pages:
            return
        self._stack.setCurrentWidget(self._pages[key])
        self._sidebar.set_active(key)

    def closeEvent(self, e):
        self.closed.emit()
        e.accept()
