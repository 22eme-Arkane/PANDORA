from PyQt6.QtWidgets import (
    QLabel, QFrame, QComboBox, QWidget, QVBoxLayout, QHBoxLayout,
    QTextEdit, QPushButton, QCheckBox, QProgressBar,
)
from PyQt6.QtCore import Qt, QObject, QEvent
from ui.styles import C
from ui.icons import claude_icon_pixmap, install_hover_icon


class _WheelIgnoreFilter(QObject):
    """Blocks scroll-wheel events so combos/spinboxes don't change accidentally."""
    def eventFilter(self, obj, event):
        if event.type() == QEvent.Type.Wheel:
            event.ignore()
            return True
        return super().eventFilter(obj, event)


# ── Help block ─────────────────────────────────────────────────────────────────

class HelpBlock(QFrame):
    """Collapsible contextual help strip — collapsed by default, discreet 28 px bar."""

    def __init__(self, title: str, lines: list[str], colors: dict | None = None):
        super().__init__()
        clr = colors or C
        self._title = title
        self.setObjectName("help_block")
        self.setStyleSheet(
            "QFrame#help_block{"
            "background:rgba(255,255,255,0.02);"
            f"border:1px solid {clr['border']};border-radius:8px;}}"
        )

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        try:
            from core.i18n import translate as _tr
        except ImportError:
            def _tr(x): return x
        self._btn = QPushButton(f"ℹ  {_tr(title)}    ▶")
        self._btn.setFixedHeight(28)
        self._btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn.setStyleSheet(
            f"QPushButton{{background:transparent;border:none;"
            f"color:{clr['text_dim']};font-size:10px;"
            f"text-align:left;padding:0 12px;"
            f"font-family:'Consolas',monospace;}}"
            f"QPushButton:hover{{color:{clr.get('text_secondary', clr['text_dim'])};}}"
        )
        self._btn.clicked.connect(self._toggle)
        root.addWidget(self._btn)

        self._body = QWidget()
        self._body.setVisible(False)
        b_lay = QVBoxLayout(self._body)
        b_lay.setContentsMargins(12, 2, 12, 10)
        b_lay.setSpacing(5)

        sep = QFrame()
        sep.setFixedHeight(1)
        sep.setStyleSheet(f"background:{clr['border']};border:none;")
        b_lay.addWidget(sep)
        b_lay.addSpacing(2)

        for line in lines:
            lbl = QLabel(line)
            lbl.setWordWrap(True)
            lbl.setStyleSheet(
                f"color:{clr['text_dim']};font-size:10px;"
                f"background:transparent;border:none;padding:0;"
            )
            b_lay.addWidget(lbl)

        root.addWidget(self._body)

    def _toggle(self):
        try:
            from core.i18n import translate as _tr
        except ImportError:
            def _tr(x): return x
        expanded = not self._body.isVisible()
        self._body.setVisible(expanded)
        arrow = "▼" if expanded else "▶"
        self._btn.setText(f"ℹ  {_tr(self._title)}    {arrow}")


def section_label(text: str) -> QLabel:
    lbl = QLabel(text.upper())
    lbl.setStyleSheet(
        f"color:{C['text_dim']};font-size:9px;letter-spacing:2px;"
        f"font-family:'Consolas',monospace;font-weight:600;margin-bottom:4px;"
    )
    return lbl


def divider() -> QFrame:
    f = QFrame()
    f.setFrameShape(QFrame.Shape.HLine)
    f.setStyleSheet(f"background:{C['border']};max-height:1px;")
    return f


_wheel_ignore = _WheelIgnoreFilter()


def combo(options: list) -> QComboBox:
    cb = QComboBox()
    cb.addItems(options)
    cb.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
    cb.installEventFilter(_wheel_ignore)
    return cb


def option_group(label: str, options: list) -> QWidget:
    w = QWidget()
    lay = QVBoxLayout(w)
    lay.setContentsMargins(0, 0, 0, 0)
    lay.setSpacing(6)
    lay.addWidget(section_label(label))
    lay.addWidget(combo(options))
    return w


def toggle_row(title: str, subtitle: str = "", checked: bool = True) -> QWidget:
    w = QFrame()
    w.setStyleSheet(
        f"QFrame{{background:{C['bg2']};border:1px solid {C['border']};"
        f"border-radius:6px;padding:4px;}}"
        f"QCheckBox{{color:{C['text_secondary']};background:transparent;border:none;}}"
        f"QCheckBox::indicator{{width:16px;height:16px;"
        f"border:1px solid {C['border_bright']};border-radius:4px;background:{C['bg3']};}}"
        f"QCheckBox::indicator:checked{{background:{C['accent']};border-color:{C['accent']};}}"
        f"QCheckBox::indicator:unchecked:hover{{border-color:{C['accent_dim']};}}"
    )
    lay = QHBoxLayout(w)
    lay.setContentsMargins(14, 10, 14, 10)
    col = QVBoxLayout()
    col.setSpacing(2)
    t = QLabel(title)
    t.setStyleSheet(f"color:{C['text_secondary']};font-size:12px;font-weight:600;border:none;")
    col.addWidget(t)
    if subtitle:
        s = QLabel(subtitle)
        s.setStyleSheet(
            f"color:{C['text_dim']};font-size:10px;font-family:'Consolas',monospace;border:none;"
        )
        col.addWidget(s)
    cb = QCheckBox()
    cb.setChecked(checked)
    lay.addLayout(col)
    lay.addStretch()
    lay.addWidget(cb)
    return w


def upload_zone(icon: str, label: str, sub: str = "") -> QFrame:
    f = QFrame()
    f.setStyleSheet(f"""
        QFrame{{background:{C['bg2']};border:1px dashed {C['border_bright']};border-radius:10px;}}
        QFrame:hover{{border-color:{C['accent_dim']};background:rgba(124,107,255,0.08);}}
    """)
    f.setCursor(Qt.CursorShape.PointingHandCursor)
    lay = QVBoxLayout(f)
    lay.setAlignment(Qt.AlignmentFlag.AlignCenter)
    lay.setContentsMargins(20, 24, 20, 24)
    lay.setSpacing(6)
    for txt, style in [
        (icon,  "font-size:26px;border:none;background:transparent;"),
        (label, f"color:{C['text_secondary']};font-size:12px;border:none;background:transparent;"),
    ]:
        lbl = QLabel(txt)
        lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl.setStyleSheet(style)
        lay.addWidget(lbl)
    if sub:
        s = QLabel(sub)
        s.setAlignment(Qt.AlignmentFlag.AlignCenter)
        s.setStyleSheet(
            f"color:{C['text_dim']};font-size:10px;font-family:'Consolas',"
            f"monospace;border:none;background:transparent;"
        )
        lay.addWidget(s)
    return f


def prompt_block(placeholder: str):
    """Retourne (frame, textarea, cloud_button, auto_checkbox)."""
    frame = QFrame()
    frame.setStyleSheet(
        f"QFrame{{background:{C['bg2']};border:1px solid {C['border']};border-radius:10px;}}"
    )
    lay = QVBoxLayout(frame)
    lay.setContentsMargins(14, 10, 14, 12)
    lay.setSpacing(6)

    # ── En-tête : compteur + icône cloud + case auto ──────────────────────────
    header = QHBoxLayout()
    header.setContentsMargins(0, 0, 0, 0)
    header.setSpacing(6)

    counter = QLabel("0")
    counter.setStyleSheet(
        f"color:{C['text_dim']};font-size:10px;font-family:'Consolas',monospace;"
        f"border:none;background:transparent;"
    )

    cloud = QPushButton()
    cloud.setFixedSize(26, 26)
    cloud.setToolTip(
        "Optimiser avec Claude\n"
        "Améliore le prompt via l'API Anthropic pour de meilleurs résultats."
    )
    cloud.setCursor(Qt.CursorShape.PointingHandCursor)
    cloud.setStyleSheet("""
        QPushButton{background:transparent;border:none;border-radius:5px;padding:0;}
        QPushButton:hover{background:rgba(124,107,255,0.12);}
        QPushButton:pressed{background:rgba(124,107,255,0.20);}
        QPushButton:disabled{opacity:0.3;}
    """)
    pix_n = claude_icon_pixmap(15, C["text_dim"])
    pix_h = claude_icon_pixmap(15, C["accent"])
    if not pix_n.isNull():
        install_hover_icon(cloud, pix_n, pix_h, icon_size=15)
    else:
        cloud.setText("☁")

    auto_cb = QCheckBox("Auto")
    auto_cb.setChecked(True)
    auto_cb.setToolTip(
        "Activé : l'optimisation Claude s'exécute automatiquement quand c'est pertinent.\n"
        "Désactivé : Claude n'intervient que si vous cliquez explicitement sur le bouton."
    )
    auto_cb.setStyleSheet(
        f"QCheckBox{{color:{C['text_dim']};font-size:9px;background:transparent;border:none;"
        f"spacing:3px;}}"
        f"QCheckBox::indicator{{width:11px;height:11px;}}"
        f"QCheckBox::indicator:checked{{background:{C['accent_dim']};border:1px solid {C['accent']};border-radius:2px;}}"
        f"QCheckBox::indicator:unchecked{{background:{C['bg3']};border:1px solid {C['border_bright']};border-radius:2px;}}"
    )

    def _sync_cloud_state():
        cloud.setEnabled(auto_cb.isChecked())
    auto_cb.toggled.connect(_sync_cloud_state)

    header.addWidget(counter)
    header.addStretch()
    header.addWidget(auto_cb)
    header.addWidget(cloud)

    sep = QFrame()
    sep.setFrameShape(QFrame.Shape.HLine)
    sep.setStyleSheet(f"background:{C['border']};max-height:1px;")

    # ── Zone de texte ─────────────────────────────────────────────────────────
    ta = QTextEdit()
    ta.setPlaceholderText(placeholder)
    ta.setMinimumHeight(90)
    ta.setStyleSheet(
        "QTextEdit{background:transparent;border:none;border-radius:0;font-size:13px;padding:0;}"
    )

    def update_count():
        counter.setText(str(len(ta.toPlainText())))

    ta.textChanged.connect(update_count)

    lay.addLayout(header)
    lay.addWidget(sep)
    lay.addWidget(ta)

    return frame, ta, cloud, auto_cb


class ProgressBlock(QFrame):
    def __init__(self):
        super().__init__()
        self.setStyleSheet(
            f"QFrame{{background:{C['bg2']};border:1px solid {C['border']};border-radius:10px;}}"
        )
        self.setVisible(False)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(14, 12, 14, 12)
        lay.setSpacing(8)

        header = QHBoxLayout()
        self.title = QLabel("GÉNÉRATION EN COURS")
        self.title.setStyleSheet(
            f"color:{C['text_secondary']};font-size:11px;font-weight:700;"
            f"letter-spacing:1px;border:none;"
        )
        self.pct_label = QLabel("0%")
        self.pct_label.setStyleSheet(
            f"color:{C['accent']};font-size:11px;font-family:'Consolas',monospace;border:none;"
        )
        header.addWidget(self.title)
        header.addStretch()
        header.addWidget(self.pct_label)

        self.bar = QProgressBar()
        self.bar.setValue(0)
        self.bar.setFixedHeight(6)
        self.bar.setTextVisible(False)

        self.status = QLabel("Initialisation...")
        self.status.setStyleSheet(
            f"color:{C['text_dim']};font-size:10px;font-family:'Consolas',monospace;border:none;"
        )

        lay.addLayout(header)
        lay.addWidget(self.bar)
        lay.addWidget(self.status)

    def update(self, pct: int, msg: str):
        self.bar.setValue(pct)
        self.pct_label.setText(f"{pct}%")
        self.status.setText(f"› {msg}")

    def reset(self):
        self.bar.setValue(0)
        self.pct_label.setText("0%")
        self.status.setText("Initialisation...")
        self.title.setText("GÉNÉRATION EN COURS")
        self.title.setStyleSheet(
            f"color:{C['text_secondary']};font-size:11px;font-weight:700;"
            f"letter-spacing:1px;border:none;"
        )

    def set_done(self):
        self.title.setText("✓  VIDÉO GÉNÉRÉE")
        self.title.setStyleSheet(
            f"color:{C['green']};font-size:11px;font-weight:700;letter-spacing:1px;border:none;"
        )
        self.pct_label.setStyleSheet(
            f"color:{C['green']};font-size:11px;font-family:'Consolas',monospace;border:none;"
        )

    def set_error(self, msg: str):
        self.title.setText("✗  ERREUR")
        self.title.setStyleSheet(
            f"color:{C['red']};font-size:11px;font-weight:700;letter-spacing:1px;border:none;"
        )
        self.status.setText(f"› {msg}")
