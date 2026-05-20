import io
import os
import webbrowser
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFrame, QApplication, QStackedWidget,
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPixmap
from ui.styles import CP, PANDORA_STYLESHEET

_BTC_ADDRESS  = "bc1p386af47cm9eyk8k9cse5r72s7z9nr50q2s0ysk8d8ys5vugmnj7qgn3hca"
_USDC_ADDRESS = "0x15a5177E00eD4D916953A3492C562197E91f7045"
_PAYPAL_URL   = "https://www.paypal.com/donate?business=22eme.arkane%40gmail.com&currency_code=EUR"

_QR_SIZE = 150

import sys as _sys
_ASSETS = (os.path.join(_sys._MEIPASS, "assets") if getattr(_sys, "frozen", False)
           else os.path.join(os.path.dirname(os.path.dirname(__file__)), "assets"))
_QR_BTC_PATH  = os.path.join(_ASSETS, "qr_btc.png")
_QR_USDC_PATH = os.path.join(_ASSETS, "qr_usdc.png")


def _load_static_qr(path: str, size: int = _QR_SIZE) -> QPixmap:
    if os.path.isfile(path):
        pix = QPixmap(path)
        if not pix.isNull():
            return pix.scaled(
                size, size,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
    return QPixmap()


def _make_qr_pixmap(data: str, size: int = _QR_SIZE) -> QPixmap:
    try:
        import qrcode
        qr = qrcode.QRCode(
            version=None,
            error_correction=qrcode.constants.ERROR_CORRECT_M,
            box_size=6,
            border=3,
        )
        qr.add_data(data)
        qr.make(fit=True)
        img = qr.make_image(fill_color="#000000", back_color="#ffffff")
        img = img.resize((size, size))
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        pix = QPixmap()
        pix.loadFromData(buf.getvalue())
        return pix
    except Exception:
        return QPixmap()


def _copy_btn(address: str) -> QPushButton:
    btn = QPushButton("⎘  Copier")
    btn.setFixedHeight(32)
    btn.setMinimumWidth(100)
    btn.setCursor(Qt.CursorShape.PointingHandCursor)
    btn.setStyleSheet(
        f"QPushButton{{background:transparent;color:{CP['text_secondary']};"
        f"border:1px solid {CP['border']};border-radius:6px;"
        f"font-size:10px;font-weight:700;padding:0 12px;}}"
        f"QPushButton:hover{{background:{CP['bg3']};color:{CP['text_primary']};"
        f"border-color:{CP['border_bright']};}}"
        f"QPushButton:pressed{{background:{CP['bg4']};}}"
    )
    _default_style = btn.styleSheet()

    def _do_copy():
        QApplication.clipboard().setText(address)
        btn.setText("✓  Copié !")
        btn.setStyleSheet(
            f"QPushButton{{background:rgba(61,220,151,0.12);color:{CP['green']};"
            f"border:1px solid {CP['green']}44;border-radius:6px;"
            f"font-size:10px;font-weight:700;padding:0 12px;}}"
        )
        from PyQt6.QtCore import QTimer
        QTimer.singleShot(2000, lambda: (
            btn.setText("⎘  Copier"),
            btn.setStyleSheet(_default_style),
        ))

    btn.clicked.connect(_do_copy)
    return btn


def _crypto_block(icon: str, name: str, network: str, address: str,
                  accent: str, qr_file_path: str = "") -> QFrame:
    frame = QFrame()
    frame.setStyleSheet(
        f"QFrame{{background:{CP['bg2']};border:1px solid {CP['border']};"
        f"border-radius:10px;}}"
    )
    outer = QVBoxLayout(frame)
    outer.setContentsMargins(16, 14, 16, 14)
    outer.setSpacing(10)

    head = QHBoxLayout()
    head.setSpacing(8)
    icon_lbl = QLabel(icon)
    icon_lbl.setFixedSize(32, 32)
    icon_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
    icon_lbl.setStyleSheet(
        f"background:{accent};color:#07080f;border-radius:8px;"
        f"font-size:16px;font-weight:900;border:none;"
    )
    name_lbl = QLabel(name)
    name_lbl.setStyleSheet(
        f"color:{CP['text_primary']};font-size:14px;font-weight:700;"
        f"background:transparent;border:none;"
    )
    net_lbl = QLabel(network)
    net_lbl.setStyleSheet(
        f"color:{CP['text_dim']};font-size:9px;font-family:'Consolas',monospace;"
        f"background:rgba(0,0,0,0.3);border:1px solid {CP['border_bright']};"
        f"border-radius:4px;padding:2px 7px;"
    )
    head.addWidget(icon_lbl)
    head.addWidget(name_lbl)
    head.addWidget(net_lbl)
    head.addStretch()
    outer.addLayout(head)

    body = QHBoxLayout()
    body.setSpacing(14)
    body.setAlignment(Qt.AlignmentFlag.AlignTop)

    left_col = QVBoxLayout()
    left_col.setSpacing(8)
    left_col.setAlignment(Qt.AlignmentFlag.AlignTop)
    addr_frame = QFrame()
    addr_frame.setStyleSheet(
        f"QFrame{{background:{CP['bg3']};border:1px solid {CP['border_bright']};"
        f"border-radius:6px;}}"
    )
    addr_inner = QVBoxLayout(addr_frame)
    addr_inner.setContentsMargins(10, 8, 10, 8)
    addr_lbl = QLabel(address)
    addr_lbl.setWordWrap(True)
    addr_lbl.setStyleSheet(
        f"color:{accent};font-size:10px;font-family:'Consolas',monospace;"
        f"font-weight:600;background:transparent;border:none;letter-spacing:0.4px;"
    )
    addr_inner.addWidget(addr_lbl)
    left_col.addWidget(addr_frame)
    left_col.addWidget(_copy_btn(address))
    body.addLayout(left_col, 1)

    qr_pix = _load_static_qr(qr_file_path) if qr_file_path else QPixmap()
    if qr_pix.isNull():
        qr_pix = _make_qr_pixmap(address)
    qr_lbl = QLabel()
    qr_lbl.setFixedSize(_QR_SIZE, _QR_SIZE)
    qr_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
    if not qr_pix.isNull():
        qr_lbl.setPixmap(qr_pix)
        qr_lbl.setStyleSheet("background:#ffffff;border:2px solid #ffffff;border-radius:6px;")
    else:
        qr_lbl.setText("QR\nn/a")
        qr_lbl.setStyleSheet(
            f"color:{CP['text_dim']};font-size:10px;background:{CP['bg3']};"
            f"border:1px solid {CP['border_bright']};border-radius:6px;"
        )
    body.addWidget(qr_lbl)
    outer.addLayout(body)
    return frame


def _choice_card(icon: str, title: str, subtitle: str,
                 accent: str, callback) -> QPushButton:
    """Large clickable card for the choice page."""
    btn = QPushButton()
    btn.setFixedHeight(90)
    btn.setCursor(Qt.CursorShape.PointingHandCursor)
    btn.setStyleSheet(
        f"QPushButton{{background:{CP['bg2']};border:1px solid {CP['border']};"
        f"border-radius:12px;text-align:left;padding:0 20px;}}"
        f"QPushButton:hover{{background:{CP['bg3']};border-color:{accent};}}"
        f"QPushButton:pressed{{background:{CP['bg4']};}}"
    )
    btn.clicked.connect(callback)

    lay = QHBoxLayout(btn)
    lay.setContentsMargins(16, 0, 20, 0)
    lay.setSpacing(16)

    icon_lbl = QLabel(icon)
    icon_lbl.setFixedSize(44, 44)
    icon_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
    icon_lbl.setStyleSheet(
        f"background:{accent};border-radius:10px;color:#07080f;"
        f"font-size:20px;font-weight:900;border:none;"
    )

    text_col = QVBoxLayout()
    text_col.setSpacing(3)
    title_lbl = QLabel(title)
    title_lbl.setStyleSheet(
        f"color:{CP['text_primary']};font-size:14px;font-weight:700;"
        f"background:transparent;border:none;"
    )
    sub_lbl = QLabel(subtitle)
    sub_lbl.setStyleSheet(
        f"color:{CP['text_dim']};font-size:10px;background:transparent;border:none;"
    )
    text_col.addWidget(title_lbl)
    text_col.addWidget(sub_lbl)

    arrow = QLabel("›")
    arrow.setStyleSheet(
        f"color:{CP['text_dim']};font-size:20px;background:transparent;border:none;"
    )

    lay.addWidget(icon_lbl)
    lay.addLayout(text_col, 1)
    lay.addWidget(arrow)
    return btn


class FundingDialog(QDialog):

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Financer le développement")
        self.setFixedSize(640, 780)
        self.setWindowFlag(Qt.WindowType.Window, True)
        self.setStyleSheet(PANDORA_STYLESHEET + f"QDialog{{background:{CP['bg1']};}}")

        root = QVBoxLayout(self)
        root.setContentsMargins(32, 28, 32, 28)
        root.setSpacing(0)

        # ── Header (shared) ───────────────────────────────────────────────────
        head = QHBoxLayout()
        badge = QLabel("$")
        badge.setFixedSize(48, 48)
        badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        badge.setStyleSheet(
            "background:qlineargradient(x1:0,y1:0,x2:1,y2:1,"
            "stop:0 #f5c518,stop:1 #e8a000);"
            "border-radius:12px;color:#07080f;"
            "font-size:22px;font-weight:900;border:none;"
        )
        head.addWidget(badge)
        head.addSpacing(14)
        title_col = QVBoxLayout()
        title_col.setSpacing(2)
        title = QLabel("Financer le plugin")
        title.setStyleSheet(
            f"color:{CP['text_primary']};font-size:20px;font-weight:800;background:transparent;"
        )
        sub = QLabel("PANDORA | Studio IA")
        sub.setStyleSheet(
            f"color:{CP['text_dim']};font-size:10px;font-family:'Consolas',monospace;"
            f"letter-spacing:1px;background:transparent;"
        )
        title_col.addWidget(title)
        title_col.addWidget(sub)
        head.addLayout(title_col)
        head.addStretch()
        root.addLayout(head)
        root.addSpacing(20)

        # ── Stack ─────────────────────────────────────────────────────────────
        self._stack = QStackedWidget()
        root.addWidget(self._stack, 1)

        self._stack.addWidget(self._build_choice_page())
        self._stack.addWidget(self._build_crypto_page())

        from core.i18n import retranslate_widget
        retranslate_widget(self)

    def _build_choice_page(self) -> QWidget:
        from PyQt6.QtWidgets import QWidget
        page = QWidget()
        lay = QVBoxLayout(page)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(14)

        intro = QLabel(
            "Choisissez votre moyen de soutenir le développement de PANDORA :"
        )
        intro.setWordWrap(True)
        intro.setStyleSheet(
            f"color:{CP['text_secondary']};font-size:12px;background:transparent;"
        )
        lay.addWidget(intro)

        lay.addWidget(_choice_card(
            "P", "PayPal",
            "Don rapide en euros — carte bancaire ou compte PayPal",
            "#009cde",
            self._on_paypal,
        ))

        lay.addWidget(_choice_card(
            "₿", "Cryptomonnaie",
            "Bitcoin (Taproot) · USDC (Réseau Sonic)",
            "#f7931a",
            self._on_crypto,
        ))

        lay.addStretch()

        note = QLabel("Merci pour votre soutien. ◈ 22eme ARKANE")
        note.setAlignment(Qt.AlignmentFlag.AlignCenter)
        note.setStyleSheet(
            f"color:{CP['text_dim']};font-size:9px;font-family:'Consolas',monospace;"
            f"background:transparent;letter-spacing:1px;"
        )
        lay.addWidget(note)

        btn_close = QPushButton("Fermer")
        btn_close.setFixedHeight(40)
        btn_close.setStyleSheet(
            f"QPushButton{{background:{CP['bg3']};color:{CP['text_secondary']};"
            f"border:1px solid {CP['border']};border-radius:8px;"
            f"font-size:12px;font-weight:700;}}"
            f"QPushButton:hover{{background:{CP['bg4']};color:{CP['text_primary']};}}"
        )
        btn_close.clicked.connect(self.accept)
        lay.addWidget(btn_close)
        return page

    def _build_crypto_page(self) -> QWidget:
        from PyQt6.QtWidgets import QWidget, QScrollArea
        outer = QWidget()
        outer_lay = QVBoxLayout(outer)
        outer_lay.setContentsMargins(0, 0, 0, 0)
        outer_lay.setSpacing(10)

        # Back button
        btn_back = QPushButton("← Retour")
        btn_back.setFixedHeight(32)
        btn_back.setFixedWidth(100)
        btn_back.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_back.setStyleSheet(
            f"QPushButton{{background:transparent;color:{CP['text_dim']};"
            f"border:1px solid {CP['border']};border-radius:6px;"
            f"font-size:11px;font-weight:700;}}"
            f"QPushButton:hover{{background:{CP['bg3']};color:{CP['text_primary']};}}"
        )
        btn_back.clicked.connect(lambda: self._stack.setCurrentIndex(0))
        outer_lay.addWidget(btn_back)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet("QScrollArea{background:transparent;border:none;}")

        inner = QWidget()
        inner.setStyleSheet("background:transparent;")
        inner_lay = QVBoxLayout(inner)
        inner_lay.setContentsMargins(0, 0, 0, 0)
        inner_lay.setSpacing(12)

        inner_lay.addWidget(_crypto_block(
            "₿", "Bitcoin", "Réseau Bitcoin · Taproot",
            _BTC_ADDRESS, "#f7931a", _QR_BTC_PATH,
        ))
        inner_lay.addWidget(_crypto_block(
            "$", "USDC", "Réseau Sonic",
            _USDC_ADDRESS, "#2775ca", _QR_USDC_PATH,
        ))
        inner_lay.addStretch()

        scroll.setWidget(inner)
        outer_lay.addWidget(scroll, 1)

        btn_close = QPushButton("Fermer")
        btn_close.setFixedHeight(40)
        btn_close.setStyleSheet(
            f"QPushButton{{background:{CP['bg3']};color:{CP['text_secondary']};"
            f"border:1px solid {CP['border']};border-radius:8px;"
            f"font-size:12px;font-weight:700;}}"
            f"QPushButton:hover{{background:{CP['bg4']};color:{CP['text_primary']};}}"
        )
        btn_close.clicked.connect(self.accept)
        outer_lay.addWidget(btn_close)
        return outer

    def _on_paypal(self):
        webbrowser.open(_PAYPAL_URL)
        self.accept()

    def _on_crypto(self):
        self._stack.setCurrentIndex(1)

    def showEvent(self, event):
        super().showEvent(event)
        screen = QApplication.primaryScreen().availableGeometry()
        x = screen.x() + max(0, (screen.width()  - self.width())  // 2)
        y = screen.y() + max(0, (screen.height() - self.height()) // 2)
        self.move(x, y)
