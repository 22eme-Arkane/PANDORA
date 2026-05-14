import webbrowser
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QFrame, QScrollArea, QWidget,
)
from PyQt6.QtCore import Qt
from ui.styles import CP, PANDORA_STYLESHEET

_FAL_URL       = "https://fal.ai/dashboard/keys"
_ANTHROPIC_URL = "https://console.anthropic.com/settings/keys"


def _sep():
    f = QFrame()
    f.setFixedHeight(1)
    f.setStyleSheet(f"background:{CP['border']};")
    return f


def _step(num: str, text: str) -> QHBoxLayout:
    row = QHBoxLayout()
    row.setSpacing(12)
    row.setAlignment(Qt.AlignmentFlag.AlignTop)
    badge = QLabel(num)
    badge.setFixedSize(26, 26)
    badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
    badge.setStyleSheet(
        f"background:{CP['accent']};color:#07080f;border-radius:13px;"
        f"font-size:12px;font-weight:800;border:none;"
    )
    lbl = QLabel(text)
    lbl.setWordWrap(True)
    lbl.setStyleSheet(
        f"color:{CP['text_secondary']};font-size:12px;background:transparent;border:none;"
    )
    row.addWidget(badge)
    row.addWidget(lbl, 1)
    return row


def _link_btn(label: str, url: str, color: str) -> QPushButton:
    btn = QPushButton(label)
    btn.setFixedHeight(34)
    btn.setStyleSheet(
        f"QPushButton{{background:transparent;color:{color};"
        f"border:1px solid {color};border-radius:8px;"
        f"font-size:11px;font-weight:700;padding:0 14px;}}"
        f"QPushButton:hover{{background:{color};color:#07080f;}}"
        f"QPushButton:pressed{{background:{color};color:#07080f;opacity:0.8;}}"
    )
    btn.clicked.connect(lambda: webbrowser.open(url))
    return btn


class ApiHelpDialog(QDialog):

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Comment obtenir les clés API")
        self.setFixedSize(580, 640)
        self.setStyleSheet(PANDORA_STYLESHEET + f"QDialog{{background:{CP['bg1']};}}")

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # Header
        header = QWidget()
        header.setFixedHeight(72)
        header.setStyleSheet(f"background:{CP['bg0']};border-bottom:1px solid {CP['border']};")
        hl = QHBoxLayout(header)
        hl.setContentsMargins(28, 0, 28, 0)
        hl.setSpacing(14)

        badge = QLabel("ⓘ")
        badge.setFixedSize(44, 44)
        badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        badge.setStyleSheet(
            f"background:rgba(78,205,196,0.12);color:{CP['accent']};"
            f"border:1px solid {CP['accent_dim']};border-radius:10px;"
            f"font-size:22px;font-weight:900;"
        )
        hl.addWidget(badge)

        title_col = QVBoxLayout()
        title_col.setSpacing(2)
        title = QLabel("Configurer les clés API")
        title.setStyleSheet(
            f"color:{CP['text_primary']};font-size:18px;font-weight:800;background:transparent;"
        )
        sub = QLabel("fal.ai  ·  Anthropic Claude")
        sub.setStyleSheet(
            f"color:{CP['text_dim']};font-size:10px;font-family:'Consolas',monospace;"
            f"letter-spacing:1px;background:transparent;"
        )
        title_col.addWidget(title)
        title_col.addWidget(sub)
        hl.addLayout(title_col)
        hl.addStretch()
        outer.addWidget(header)

        # Scroll content
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea{background:transparent;border:none;}")

        inner = QWidget()
        inner.setStyleSheet(f"background:{CP['bg1']};")
        lay = QVBoxLayout(inner)
        lay.setContentsMargins(28, 24, 28, 28)
        lay.setSpacing(20)

        # ── fal.ai ───────────────────────────────────────────────────────────
        fal_head = QHBoxLayout()
        fal_icon = QLabel("▶")
        fal_icon.setFixedSize(32, 32)
        fal_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        fal_icon.setStyleSheet(
            f"background:#9C3FE4;color:#fff;border-radius:8px;"
            f"font-size:14px;font-weight:900;border:none;"
        )
        fal_title = QLabel("fal.ai — Seedance 2.0 & Nano Banana")
        fal_title.setStyleSheet(
            f"color:{CP['text_primary']};font-size:14px;font-weight:700;background:transparent;border:none;"
        )
        fal_badge = QLabel("Vidéo  ·  Images IA")
        fal_badge.setStyleSheet(
            f"color:{CP['text_dim']};font-size:9px;font-family:'Consolas',monospace;"
            f"background:{CP['bg3']};border:1px solid {CP['border_bright']};"
            f"border-radius:4px;padding:2px 8px;"
        )
        fal_head.addWidget(fal_icon)
        fal_head.addSpacing(10)
        fal_head.addWidget(fal_title)
        fal_head.addWidget(fal_badge)
        fal_head.addStretch()
        lay.addLayout(fal_head)

        fal_frame = QFrame()
        fal_frame.setStyleSheet(
            f"QFrame{{background:{CP['bg2']};border:1px solid {CP['border']};border-radius:10px;}}"
        )
        fl = QVBoxLayout(fal_frame)
        fl.setContentsMargins(18, 16, 18, 16)
        fl.setSpacing(12)
        fl.addLayout(_step("1", "Va sur <b>fal.ai</b> et crée un compte gratuit (ou connecte-toi)."))
        fl.addLayout(_step("2", "Dans le tableau de bord, va dans <b>Keys</b> → <b>Create new key</b>."))
        fl.addLayout(_step("3", "Copie la clé (commence par <code>fal_</code>) et colle-la dans PANDORA."))
        fl.addLayout(_step("4", "Recharge ton compte fal.ai pour générer des vidéos et portraits."))
        fl.addWidget(_sep())
        link_row = QHBoxLayout()
        link_row.addWidget(_link_btn("⇗  Ouvrir fal.ai/dashboard/keys", _FAL_URL, "#9C3FE4"))
        link_row.addStretch()
        fl.addLayout(link_row)
        lay.addWidget(fal_frame)

        lay.addWidget(_sep())

        # ── Anthropic Claude ─────────────────────────────────────────────────
        ant_head = QHBoxLayout()
        ant_icon = QLabel("☁")
        ant_icon.setFixedSize(32, 32)
        ant_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        ant_icon.setStyleSheet(
            f"background:{CP['accent2']};color:#fff;border-radius:8px;"
            f"font-size:16px;font-weight:900;border:none;"
        )
        ant_title = QLabel("Anthropic — Claude")
        ant_title.setStyleSheet(
            f"color:{CP['text_primary']};font-size:14px;font-weight:700;background:transparent;border:none;"
        )
        ant_badge = QLabel("Optimisation de prompts  ·  Scénario  ·  Storyboard")
        ant_badge.setStyleSheet(
            f"color:{CP['text_dim']};font-size:9px;font-family:'Consolas',monospace;"
            f"background:{CP['bg3']};border:1px solid {CP['border_bright']};"
            f"border-radius:4px;padding:2px 8px;"
        )
        ant_head.addWidget(ant_icon)
        ant_head.addSpacing(10)
        ant_head.addWidget(ant_title)
        ant_head.addWidget(ant_badge)
        ant_head.addStretch()
        lay.addLayout(ant_head)

        ant_frame = QFrame()
        ant_frame.setStyleSheet(
            f"QFrame{{background:{CP['bg2']};border:1px solid {CP['border']};border-radius:10px;}}"
        )
        al = QVBoxLayout(ant_frame)
        al.setContentsMargins(18, 16, 18, 16)
        al.setSpacing(12)
        al.addLayout(_step("1", "Va sur <b>console.anthropic.com</b> et crée un compte (ou connecte-toi)."))
        al.addLayout(_step("2", "Dans <b>Settings → API Keys</b>, clique <b>Create Key</b>."))
        al.addLayout(_step("3", "Copie la clé (commence par <code>sk-ant-</code>) et colle-la dans PANDORA."))
        al.addLayout(_step("4", "Claude est utilisé pour optimiser les prompts ☁, formater le scénario et générer le storyboard."))
        al.addWidget(_sep())
        link_row2 = QHBoxLayout()
        link_row2.addWidget(_link_btn("⇗  Ouvrir console.anthropic.com", _ANTHROPIC_URL, CP["accent2"]))
        link_row2.addStretch()
        al.addLayout(link_row2)
        lay.addWidget(ant_frame)

        lay.addWidget(_sep())

        # ── Usage gratuit ─────────────────────────────────────────────────────
        note_frame = QFrame()
        note_frame.setStyleSheet(
            f"QFrame{{background:rgba(255,140,66,0.07);"
            f"border:1px solid rgba(255,140,66,0.22);border-radius:8px;}}"
        )
        nl = QVBoxLayout(note_frame)
        nl.setContentsMargins(14, 12, 14, 12)
        nl.setSpacing(8)
        note = QLabel(
            "💡  <b>Utilisation :</b> fal.ai et Anthropic sont des services payants à l'usage. "
            "Chaque génération consomme des crédits. "
            "Les deux plateformes offrent des crédits de démarrage gratuits pour tester."
        )
        note.setWordWrap(True)
        note.setStyleSheet(
            f"color:{CP['orange']};font-size:11px;background:transparent;border:none;"
        )
        nl.addWidget(note)

        vpn_note = QLabel(
            "🔒  <b>VPN :</b> si Claude ne répond pas ou génère des erreurs, "
            "désactivez votre VPN — certains serveurs VPN sont bloqués par l'API Anthropic."
        )
        vpn_note.setWordWrap(True)
        vpn_note.setStyleSheet(
            f"color:{CP['orange']};font-size:11px;background:transparent;border:none;"
        )
        nl.addWidget(vpn_note)
        lay.addWidget(note_frame)

        scroll.setWidget(inner)
        outer.addWidget(scroll, 1)

        # Footer
        footer = QWidget()
        footer.setFixedHeight(60)
        footer.setStyleSheet(f"background:{CP['bg0']};border-top:1px solid {CP['border']};")
        fl2 = QHBoxLayout(footer)
        fl2.setContentsMargins(28, 0, 28, 0)
        fl2.addStretch()
        btn_close = QPushButton("Fermer")
        btn_close.setFixedHeight(38)
        btn_close.setStyleSheet(
            f"QPushButton{{background:{CP['bg3']};color:{CP['text_secondary']};"
            f"border:1px solid {CP['border']};border-radius:8px;"
            f"font-size:12px;font-weight:700;padding:0 20px;}}"
            f"QPushButton:hover{{background:{CP['bg4']};color:{CP['text_primary']};}}"
        )
        btn_close.clicked.connect(self.accept)
        fl2.addWidget(btn_close)
        outer.addWidget(footer)

        from core.i18n import retranslate_widget
        retranslate_widget(self)
