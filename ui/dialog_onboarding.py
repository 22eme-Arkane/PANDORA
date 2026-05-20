"""
ui/dialog_onboarding.py — Wizard de démarrage pour les novices.

Affiché au premier lancement (ou tant que show_api_guide=True dans la config).
Guide pas-à-pas : fal.ai + Anthropic Claude → coller les clés dans PANDORA.
"""
import webbrowser
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFrame, QScrollArea, QWidget, QCheckBox, QStackedWidget,
)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QDesktopServices
from PyQt6.QtCore import QUrl
from ui.styles import CP, PANDORA_STYLESHEET

_FAL_SIGNUP   = "https://fal.ai/signup"
_FAL_KEYS     = "https://fal.ai/dashboard/keys"
_FAL_BILLING  = "https://fal.ai/dashboard/billing"
_ANT_SIGNUP   = "https://console.anthropic.com"
_ANT_KEYS     = "https://console.anthropic.com/settings/keys"
_ANT_BILLING  = "https://console.anthropic.com/settings/billing"


# ── Helpers visuels ────────────────────────────────────────────────────────────

def _open(url):
    QDesktopServices.openUrl(QUrl(url))


def _h(text: str, size: int = 15, color: str | None = None) -> QLabel:
    lbl = QLabel(text)
    lbl.setStyleSheet(
        f"color:{color or CP['text_primary']};font-size:{size}px;font-weight:700;"
        f"background:transparent;"
    )
    lbl.setWordWrap(True)
    return lbl


def _p(text: str, size: int = 12, color: str | None = None) -> QLabel:
    lbl = QLabel(text)
    lbl.setWordWrap(True)
    lbl.setStyleSheet(
        f"color:{color or CP['text_secondary']};font-size:{size}px;background:transparent;"
    )
    return lbl


def _sep() -> QFrame:
    f = QFrame()
    f.setFixedHeight(1)
    f.setStyleSheet(f"background:{CP['border']};")
    return f


def _link_btn(label: str, url: str, color: str = None) -> QPushButton:
    c = color or CP["accent"]
    btn = QPushButton(label)
    btn.setFixedHeight(34)
    btn.setCursor(Qt.CursorShape.PointingHandCursor)
    btn.setStyleSheet(
        f"QPushButton{{background:transparent;color:{c};"
        f"border:1px solid {c};border-radius:8px;"
        f"font-size:11px;font-weight:700;padding:0 14px;}}"
        f"QPushButton:hover{{background:{c};color:#07080f;}}"
    )
    btn.clicked.connect(lambda: _open(url))
    return btn


def _step_row(num: int, text: str, accent: str = None) -> QHBoxLayout:
    a = accent or CP["accent"]
    row = QHBoxLayout()
    row.setSpacing(12)
    row.setAlignment(Qt.AlignmentFlag.AlignTop)
    badge = QLabel(str(num))
    badge.setFixedSize(28, 28)
    badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
    badge.setStyleSheet(
        f"background:{a};color:#07080f;border-radius:14px;"
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


def _mock_browser(url_text: str, content_html: str,
                  highlight_text: str = "", accent: str = None) -> QFrame:
    """Crée un cadre qui ressemble à une capture d'écran de navigateur."""
    a = accent or CP["accent"]
    outer = QFrame()
    outer.setStyleSheet(
        f"QFrame{{background:#0d0f1c;border:1px solid {CP['border_bright']};"
        f"border-radius:10px;}}"
    )
    v = QVBoxLayout(outer)
    v.setContentsMargins(0, 0, 0, 0)
    v.setSpacing(0)

    # Barre URL
    bar = QWidget()
    bar.setFixedHeight(32)
    bar.setStyleSheet(
        f"background:#141629;border-bottom:1px solid {CP['border']};"
        f"border-radius:10px 10px 0 0;"
    )
    bar_lay = QHBoxLayout(bar)
    bar_lay.setContentsMargins(10, 0, 10, 0)
    bar_lay.setSpacing(6)
    for c in ["#ff5f57", "#febc2e", "#28c840"]:
        dot = QLabel("●")
        dot.setFixedWidth(10)
        dot.setStyleSheet(f"color:{c};font-size:8px;background:transparent;")
        bar_lay.addWidget(dot)
    bar_lay.addSpacing(8)
    url_lbl = QLabel(f"🔒  {url_text}")
    url_lbl.setStyleSheet(
        f"color:{CP['text_dim']};font-size:10px;font-family:'Consolas',monospace;"
        f"background:#1c1f35;border:1px solid {CP['border']};border-radius:4px;"
        f"padding:2px 8px;"
    )
    bar_lay.addWidget(url_lbl, 1)
    v.addWidget(bar)

    # Contenu simulé
    body = QWidget()
    body.setStyleSheet(f"background:#0d0f1c;border-radius:0 0 10px 10px;")
    b = QVBoxLayout(body)
    b.setContentsMargins(16, 12, 16, 12)
    b.setSpacing(6)

    content = QLabel(content_html)
    content.setWordWrap(True)
    content.setTextFormat(Qt.TextFormat.RichText)
    content.setStyleSheet(f"color:{CP['text_secondary']};font-size:11px;background:transparent;")
    b.addWidget(content)

    if highlight_text:
        hl = QLabel(highlight_text)
        hl.setWordWrap(True)
        hl.setTextFormat(Qt.TextFormat.RichText)
        hl.setStyleSheet(
            f"color:{a};font-size:11px;font-weight:700;"
            f"background:rgba(78,205,196,0.08);border:1px solid {a}55;"
            f"border-radius:6px;padding:6px 10px;"
        )
        b.addWidget(hl)

    v.addWidget(body)
    return outer


def _info_box(text: str, color: str = None) -> QFrame:
    c = color or CP["accent"]
    f = QFrame()
    f.setStyleSheet(
        f"QFrame{{background:rgba(78,205,196,0.07);"
        f"border:1px solid {c}44;border-radius:8px;}}"
    )
    lay = QVBoxLayout(f)
    lay.setContentsMargins(14, 10, 14, 10)
    lbl = QLabel(text)
    lbl.setWordWrap(True)
    lbl.setTextFormat(Qt.TextFormat.RichText)
    lbl.setStyleSheet(f"color:{c};font-size:11px;background:transparent;border:none;")
    lay.addWidget(lbl)
    return f


def _section_title(text: str, color: str = None) -> QLabel:
    lbl = QLabel(text)
    lbl.setStyleSheet(
        f"color:{color or CP['text_dim']};font-size:9px;font-weight:700;"
        f"letter-spacing:2px;background:transparent;"
    )
    return lbl


# ── Pages du wizard ────────────────────────────────────────────────────────────

def _page_welcome() -> QWidget:
    w = QWidget()
    lay = QVBoxLayout(w)
    lay.setContentsMargins(32, 28, 32, 28)
    lay.setSpacing(18)

    # Icône centrale
    ico = QLabel("✦")
    ico.setAlignment(Qt.AlignmentFlag.AlignCenter)
    ico.setStyleSheet(
        f"color:{CP['accent']};font-size:40px;background:transparent;"
    )
    lay.addWidget(ico)

    title = QLabel("Bienvenue dans PANDORA")
    title.setAlignment(Qt.AlignmentFlag.AlignCenter)
    title.setStyleSheet(
        f"color:{CP['text_primary']};font-size:20px;font-weight:800;background:transparent;"
    )
    lay.addWidget(title)

    sub = QLabel("Guide de configuration des services IA")
    sub.setAlignment(Qt.AlignmentFlag.AlignCenter)
    sub.setStyleSheet(
        f"color:{CP['text_dim']};font-size:11px;font-family:'Consolas',monospace;"
        f"letter-spacing:1px;background:transparent;"
    )
    lay.addWidget(sub)

    lay.addWidget(_sep())

    intro = _p(
        "PANDORA utilise deux services d'intelligence artificielle pour fonctionner. "
        "Ce guide va t'accompagner étape par étape pour les configurer — "
        "même si tu n'as jamais utilisé d'API auparavant."
    )
    intro.setAlignment(Qt.AlignmentFlag.AlignCenter)
    lay.addWidget(intro)

    # Carte fal.ai
    fal_card = QFrame()
    fal_card.setStyleSheet(
        f"QFrame{{background:{CP['bg2']};border:1px solid {CP['border']};"
        f"border-radius:10px;}}"
    )
    fc = QHBoxLayout(fal_card)
    fc.setContentsMargins(18, 14, 18, 14)
    fc.setSpacing(14)
    fal_ico = QLabel("▶")
    fal_ico.setFixedSize(40, 40)
    fal_ico.setAlignment(Qt.AlignmentFlag.AlignCenter)
    fal_ico.setStyleSheet(
        "background:#9C3FE4;color:#fff;border-radius:10px;"
        "font-size:16px;font-weight:900;border:none;"
    )
    fc.addWidget(fal_ico)
    fal_txt = QVBoxLayout()
    fal_txt.setSpacing(3)
    fal_name = QLabel("fal.ai")
    fal_name.setStyleSheet(
        f"color:{CP['text_primary']};font-size:14px;font-weight:700;background:transparent;"
    )
    fal_desc = QLabel(
        "Génère les vidéos (Seedance, Kling, Veo…) et les images de référence (portraits, décors…)"
    )
    fal_desc.setWordWrap(True)
    fal_desc.setStyleSheet(
        f"color:{CP['text_dim']};font-size:11px;background:transparent;"
    )
    fal_price = QLabel("💰  Crédits à la consommation — commence avec $10")
    fal_price.setStyleSheet(
        f"color:#9C3FE4;font-size:10px;font-weight:600;background:transparent;"
    )
    fal_txt.addWidget(fal_name)
    fal_txt.addWidget(fal_desc)
    fal_txt.addWidget(fal_price)
    fc.addLayout(fal_txt, 1)
    lay.addWidget(fal_card)

    # Carte Anthropic
    ant_card = QFrame()
    ant_card.setStyleSheet(
        f"QFrame{{background:{CP['bg2']};border:1px solid {CP['border']};"
        f"border-radius:10px;}}"
    )
    ac = QHBoxLayout(ant_card)
    ac.setContentsMargins(18, 14, 18, 14)
    ac.setSpacing(14)
    ant_ico = QLabel("☁")
    ant_ico.setFixedSize(40, 40)
    ant_ico.setAlignment(Qt.AlignmentFlag.AlignCenter)
    ant_ico.setStyleSheet(
        f"background:{CP['accent2']};color:#fff;border-radius:10px;"
        "font-size:18px;font-weight:900;border:none;"
    )
    ac.addWidget(ant_ico)
    ant_txt = QVBoxLayout()
    ant_txt.setSpacing(3)
    ant_name = QLabel("Anthropic — Claude")
    ant_name.setStyleSheet(
        f"color:{CP['text_primary']};font-size:14px;font-weight:700;background:transparent;"
    )
    ant_desc = QLabel(
        "Assiste la rédaction du scénario, génère le storyboard et optimise les prompts vidéo"
    )
    ant_desc.setWordWrap(True)
    ant_desc.setStyleSheet(
        f"color:{CP['text_dim']};font-size:11px;background:transparent;"
    )
    ant_price = QLabel("💰  Crédits à la consommation — commence avec $5")
    ant_price.setStyleSheet(
        f"color:{CP['accent2']};font-size:10px;font-weight:600;background:transparent;"
    )
    ant_txt.addWidget(ant_name)
    ant_txt.addWidget(ant_desc)
    ant_txt.addWidget(ant_price)
    ac.addLayout(ant_txt, 1)
    lay.addWidget(ant_card)

    lay.addWidget(_info_box(
        "💡  <b>Aucune clé requise pour essayer PANDORA</b> — le logiciel fonctionne en mode "
        "simulation sans clé. Tu peux explorer toutes les pages et revenir configurer "
        "les clés plus tard depuis <b>Paramètres</b>.",
        CP["accent"]
    ))

    lay.addWidget(_sep())

    tuto_row = QHBoxLayout()
    tuto_row.setSpacing(14)
    tuto_icon = QLabel("▶")
    tuto_icon.setFixedSize(36, 36)
    tuto_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
    tuto_icon.setStyleSheet(
        "background:#ff0000;color:#fff;border-radius:8px;"
        "font-size:13px;font-weight:900;border:none;"
    )
    tuto_row.addWidget(tuto_icon)
    tuto_col = QVBoxLayout()
    tuto_col.setSpacing(3)
    tuto_title = QLabel("Tutoriel complet PANDORA")
    tuto_title.setStyleSheet(
        f"color:{CP['text_primary']};font-size:13px;font-weight:700;background:transparent;"
    )
    tuto_sub = QLabel("Découvrez toutes les fonctionnalités en vidéo — YouTube")
    tuto_sub.setStyleSheet(
        f"color:{CP['text_dim']};font-size:10px;background:transparent;"
    )
    tuto_col.addWidget(tuto_title)
    tuto_col.addWidget(tuto_sub)
    tuto_row.addLayout(tuto_col, 1)
    btn_tuto = QPushButton("▶  Voir le tutoriel →")
    btn_tuto.setFixedHeight(34)
    btn_tuto.setCursor(Qt.CursorShape.PointingHandCursor)
    btn_tuto.setStyleSheet(
        "QPushButton{background:#ff0000;color:#fff;"
        "border:none;border-radius:8px;"
        "font-size:11px;font-weight:700;padding:0 14px;}"
        "QPushButton:hover{background:#cc0000;}"
    )
    btn_tuto.clicked.connect(lambda: _open("https://www.youtube.com/watch?v=SC3pRI5bR1Q"))
    tuto_row.addWidget(btn_tuto)
    lay.addLayout(tuto_row)

    lay.addStretch()
    return w


def _page_fal() -> QWidget:
    w = QScrollArea()
    w.setWidgetResizable(True)
    w.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
    w.setStyleSheet(
        f"QScrollArea{{background:transparent;border:none;}}"
        f"QScrollBar:vertical{{width:4px;background:{CP['bg2']};}}"
        f"QScrollBar::handle:vertical{{background:{CP['border_bright']};border-radius:2px;}}"
    )
    inner = QWidget()
    inner.setStyleSheet("background:transparent;")
    lay = QVBoxLayout(inner)
    lay.setContentsMargins(32, 24, 32, 24)
    lay.setSpacing(20)

    # En-tête
    hrow = QHBoxLayout()
    hrow.setSpacing(12)
    ico = QLabel("▶")
    ico.setFixedSize(38, 38)
    ico.setAlignment(Qt.AlignmentFlag.AlignCenter)
    ico.setStyleSheet(
        "background:#9C3FE4;color:#fff;border-radius:9px;"
        "font-size:15px;font-weight:900;border:none;"
    )
    hrow.addWidget(ico)
    col = QVBoxLayout()
    col.setSpacing(2)
    col.addWidget(_h("fal.ai — Vidéos & Images IA", 16))
    sub = QLabel("Seedance 2.0  ·  Kling  ·  Veo  ·  Flux  ·  Nano Banana")
    sub.setStyleSheet(
        f"color:#9C3FE4;font-size:9px;font-family:'Consolas',monospace;"
        f"letter-spacing:1px;background:transparent;"
    )
    col.addWidget(sub)
    hrow.addLayout(col, 1)
    lay.addLayout(hrow)

    lay.addWidget(_sep())

    # ─ Étape 1
    lay.addWidget(_section_title("ÉTAPE 1 — CRÉER UN COMPTE"))
    lay.addLayout(_step_row(1, "Clique sur le bouton ci-dessous pour ouvrir fal.ai dans ton navigateur.", "#9C3FE4"))
    lay.addLayout(_step_row(2, "Clique sur <b>Sign Up</b> (en haut à droite) et crée ton compte avec ton e-mail.", "#9C3FE4"))

    lay.addWidget(_mock_browser(
        "fal.ai/signup",
        "<b style='color:#c0c0d0'>fal.ai</b>"
        "<span style='color:#555'>  ·  Create your account</span><br><br>"
        "<span style='color:#888'>Email&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;</span> "
        "<span style='color:#ccc'>[ ton-email@exemple.com        ]</span><br>"
        "<span style='color:#888'>Password&nbsp;</span> "
        "<span style='color:#ccc'>[ ••••••••••••••               ]</span>",
        "👆  Clique sur  [ Create account ]  puis vérifie ton e-mail",
        "#9C3FE4"
    ))

    btn_row = QHBoxLayout()
    btn_row.addWidget(_link_btn("🌐  Ouvrir fal.ai/signup →", _FAL_SIGNUP, "#9C3FE4"))
    btn_row.addStretch()
    lay.addLayout(btn_row)

    lay.addWidget(_sep())

    # ─ Étape 2 — Clé API
    lay.addWidget(_section_title("ÉTAPE 2 — CRÉER UNE CLÉ API"))
    lay.addLayout(_step_row(1, "Une fois connecté, clique sur ton avatar (en haut à droite) → <b>Dashboard</b>.", "#9C3FE4"))
    lay.addLayout(_step_row(2, "Dans le menu de gauche, clique sur <b>Keys</b>.", "#9C3FE4"))
    lay.addLayout(_step_row(3, "Clique sur <b>+ Add key</b>, donne-lui le nom <b>PANDORA</b>, puis clique <b>Create</b>.", "#9C3FE4"))

    lay.addWidget(_mock_browser(
        "fal.ai/dashboard/keys",
        "<b style='color:#c0c0d0'>API Keys</b><br><br>"
        "<span style='color:#888'>Aucune clé pour l'instant...</span>",
        "👆  Clique sur  [ + Add key ]  →  Nom : PANDORA  →  [ Create ]",
        "#9C3FE4"
    ))

    lay.addLayout(_step_row(4,
        "La clé générée ressemble à : <b>fal_key_xxxxxxxxxxxxxxxx</b><br>"
        "⚠️  Copie-la maintenant — elle ne sera affichée qu'une seule fois !",
        "#9C3FE4"
    ))

    lay.addWidget(_mock_browser(
        "fal.ai/dashboard/keys",
        "<b style='color:#c0c0d0'>API Keys</b><br><br>"
        "<span style='color:#888'>PANDORA</span>",
        "👆  Clique sur l'icône  📋  pour copier ta clé  fal_key_xxxx…",
        "#9C3FE4"
    ))

    btn_row2 = QHBoxLayout()
    btn_row2.addWidget(_link_btn("🔑  Ouvrir fal.ai/dashboard/keys →", _FAL_KEYS, "#9C3FE4"))
    btn_row2.addStretch()
    lay.addLayout(btn_row2)

    lay.addWidget(_sep())

    # ─ Étape 3 — Crédits
    lay.addWidget(_section_title("ÉTAPE 3 — AJOUTER DES CRÉDITS"))
    lay.addLayout(_step_row(1, "Dans le menu de gauche, clique sur <b>Billing</b>.", "#9C3FE4"))
    lay.addLayout(_step_row(2, "Clique sur <b>Add credits</b> et ajoute <b>au minimum $10</b> pour bien démarrer.", "#9C3FE4"))

    lay.addWidget(_mock_browser(
        "fal.ai/dashboard/billing",
        "<b style='color:#c0c0d0'>Billing</b><br><br>"
        "<span style='color:#888'>Current balance :</span> "
        "<span style='color:#9C3FE4'>$0.00</span>",
        "👆  Clique sur  [ Add credits ]  →  Recommandé : $10 minimum",
        "#9C3FE4"
    ))

    lay.addWidget(_info_box(
        "💡  <b>Coût moyen :</b> environ $0.20–$0.50 par vidéo Seedance 2.0 (10 secondes). "
        "Avec $10, tu peux générer environ 20 à 50 vidéos.",
        "#9C3FE4"
    ))

    btn_row3 = QHBoxLayout()
    btn_row3.addWidget(_link_btn("💳  Ouvrir fal.ai/dashboard/billing →", _FAL_BILLING, "#9C3FE4"))
    btn_row3.addStretch()
    lay.addLayout(btn_row3)

    lay.addStretch()
    w.setWidget(inner)
    return w


def _page_anthropic() -> QWidget:
    w = QScrollArea()
    w.setWidgetResizable(True)
    w.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
    w.setStyleSheet(
        f"QScrollArea{{background:transparent;border:none;}}"
        f"QScrollBar:vertical{{width:4px;background:{CP['bg2']};}}"
        f"QScrollBar::handle:vertical{{background:{CP['border_bright']};border-radius:2px;}}"
    )
    inner = QWidget()
    inner.setStyleSheet("background:transparent;")
    lay = QVBoxLayout(inner)
    lay.setContentsMargins(32, 24, 32, 24)
    lay.setSpacing(20)

    # En-tête
    hrow = QHBoxLayout()
    hrow.setSpacing(12)
    ico = QLabel("☁")
    ico.setFixedSize(38, 38)
    ico.setAlignment(Qt.AlignmentFlag.AlignCenter)
    ico.setStyleSheet(
        f"background:{CP['accent2']};color:#fff;border-radius:9px;"
        "font-size:18px;font-weight:900;border:none;"
    )
    hrow.addWidget(ico)
    col = QVBoxLayout()
    col.setSpacing(2)
    col.addWidget(_h("Anthropic — Claude IA", 16))
    sub = QLabel("Scénario  ·  Storyboard  ·  Prompts  ·  Extraction d'éléments")
    sub.setStyleSheet(
        f"color:{CP['accent2']};font-size:9px;font-family:'Consolas',monospace;"
        f"letter-spacing:1px;background:transparent;"
    )
    col.addWidget(sub)
    hrow.addLayout(col, 1)
    lay.addLayout(hrow)

    lay.addWidget(_sep())

    # ─ Étape 1
    lay.addWidget(_section_title("ÉTAPE 1 — CRÉER UN COMPTE"))
    lay.addLayout(_step_row(1,
        "Clique sur le bouton ci-dessous pour ouvrir la console Anthropic dans ton navigateur.",
        CP["accent2"]
    ))
    lay.addLayout(_step_row(2,
        "Clique sur <b>Sign up</b> et crée ton compte avec ton e-mail ou ton compte Google.",
        CP["accent2"]
    ))

    lay.addWidget(_mock_browser(
        "console.anthropic.com",
        "<b style='color:#c0c0d0'>Anthropic Console</b><br><br>"
        "<span style='color:#888'>Welcome to Claude</span>",
        "👆  Clique sur  [ Sign up ]  ou  [ Continue with Google ]",
        CP["accent2"]
    ))

    btn_row = QHBoxLayout()
    btn_row.addWidget(_link_btn("🌐  Ouvrir console.anthropic.com →", _ANT_SIGNUP, CP["accent2"]))
    btn_row.addStretch()
    lay.addLayout(btn_row)

    lay.addWidget(_sep())

    # ─ Étape 2 — Clé API
    lay.addWidget(_section_title("ÉTAPE 2 — CRÉER UNE CLÉ API"))
    lay.addLayout(_step_row(1,
        "Une fois connecté, clique sur <b>Settings</b> dans le menu de gauche.",
        CP["accent2"]
    ))
    lay.addLayout(_step_row(2,
        "Dans Settings, clique sur <b>API Keys</b>.",
        CP["accent2"]
    ))
    lay.addLayout(_step_row(3,
        "Clique sur <b>Create Key</b>, donne-lui le nom <b>PANDORA</b>, puis clique <b>Create Key</b>.",
        CP["accent2"]
    ))

    lay.addWidget(_mock_browser(
        "console.anthropic.com/settings/keys",
        "<b style='color:#c0c0d0'>Settings  ›  API Keys</b><br><br>"
        "<span style='color:#888'>No API keys yet.</span>",
        "👆  Clique sur  [ Create Key ]  →  Nom : PANDORA  →  [ Create Key ]",
        CP["accent2"]
    ))

    lay.addLayout(_step_row(4,
        "La clé générée ressemble à : <b>sk-ant-api03-xxxxxxxxxxxxxxxx</b><br>"
        "⚠️  Copie-la maintenant — elle ne sera affichée qu'une seule fois !",
        CP["accent2"]
    ))

    lay.addWidget(_mock_browser(
        "console.anthropic.com/settings/keys",
        "<b style='color:#c0c0d0'>API Keys</b><br><br>"
        "<span style='color:#888'>PANDORA  ·  Créée maintenant</span>",
        "👆  Clique sur l'icône  📋  pour copier ta clé  sk-ant-api03-xxxx…",
        CP["accent2"]
    ))

    btn_row2 = QHBoxLayout()
    btn_row2.addWidget(_link_btn("🔑  Ouvrir API Keys →", _ANT_KEYS, CP["accent2"]))
    btn_row2.addStretch()
    lay.addLayout(btn_row2)

    lay.addWidget(_sep())

    # ─ Étape 3 — Crédits
    lay.addWidget(_section_title("ÉTAPE 3 — AJOUTER DES CRÉDITS"))
    lay.addLayout(_step_row(1,
        "Dans Settings, clique sur <b>Billing</b>.",
        CP["accent2"]
    ))
    lay.addLayout(_step_row(2,
        "Clique sur <b>Add to credit balance</b> et ajoute <b>au minimum $5</b>.",
        CP["accent2"]
    ))

    lay.addWidget(_mock_browser(
        "console.anthropic.com/settings/billing",
        "<b style='color:#c0c0d0'>Billing</b><br><br>"
        "<span style='color:#888'>Credit balance :</span> "
        "<span style='color:#7c3aed'>$0.00</span>",
        "👆  Clique sur  [ Add to credit balance ]  →  Recommandé : $5 minimum",
        CP["accent2"]
    ))

    lay.addWidget(_info_box(
        "💡  <b>Coût moyen :</b> environ $0.01–$0.05 par opération Claude "
        "(formatage, génération storyboard, extraction d'éléments). "
        "Avec $5, tu as des centaines d'opérations disponibles.",
        CP["accent2"]
    ))

    btn_row3 = QHBoxLayout()
    btn_row3.addWidget(_link_btn("💳  Ouvrir Billing →", _ANT_BILLING, CP["accent2"]))
    btn_row3.addStretch()
    lay.addLayout(btn_row3)

    lay.addWidget(_info_box(
        "🔒  <b>VPN :</b> si Claude ne répond pas, désactivez votre VPN — "
        "certains serveurs VPN sont bloqués par l'API Anthropic.",
        CP["orange"]
    ))

    lay.addStretch()
    w.setWidget(inner)
    return w


def _page_finish(navigate_to_settings_fn) -> QWidget:
    w = QWidget()
    lay = QVBoxLayout(w)
    lay.setContentsMargins(32, 28, 32, 28)
    lay.setSpacing(18)

    ico = QLabel("⚙")
    ico.setAlignment(Qt.AlignmentFlag.AlignCenter)
    ico.setStyleSheet(
        f"color:{CP['accent']};font-size:36px;background:transparent;"
    )
    lay.addWidget(ico)

    lay.addWidget(_h("Coller les clés dans PANDORA", 16, CP["text_primary"]))
    lay.addWidget(_p(
        "Tu as maintenant tes deux clés API. Il ne reste plus qu'à les coller "
        "dans la page <b>Paramètres</b> de PANDORA.",
        color=CP["text_secondary"]
    ))

    lay.addWidget(_sep())

    # Maquette page Paramètres PANDORA
    lay.addWidget(_section_title("DANS PANDORA — PAGE PARAMÈTRES"))

    lay.addWidget(_mock_browser(
        "PANDORA  ›  Paramètres",
        "<b style='color:#c0c0d0'>Clé fal.ai</b><br>"
        "<span style='color:#888'>[ fal_key_…</span>"
        "<span style='color:#555'>                            ]</span><br><br>"
        "<b style='color:#c0c0d0'>Clé Anthropic</b><br>"
        "<span style='color:#888'>[ sk-ant-api03-…</span>"
        "<span style='color:#555'>                     ]</span>",
        "👆  Colle tes clés ici et clique  [ Enregistrer ]",
        CP["accent"]
    ))

    # Bouton aller aux paramètres
    btn_settings = QPushButton("⚙  Aller aux Paramètres →")
    btn_settings.setMinimumHeight(44)
    btn_settings.setCursor(Qt.CursorShape.PointingHandCursor)
    btn_settings.setStyleSheet(
        f"QPushButton{{background:{CP['accent']};color:#07080f;"
        f"border:none;border-radius:10px;font-size:13px;font-weight:700;padding:0 24px;}}"
        f"QPushButton:hover{{background:#6eded6;}}"
    )
    btn_settings.clicked.connect(navigate_to_settings_fn)
    lay.addWidget(btn_settings)

    lay.addWidget(_sep())

    # Récap
    recap = QFrame()
    recap.setStyleSheet(
        f"QFrame{{background:{CP['bg2']};border:1px solid {CP['border']};border-radius:10px;}}"
    )
    rc = QVBoxLayout(recap)
    rc.setContentsMargins(18, 14, 18, 14)
    rc.setSpacing(8)
    rc.addLayout(_step_row(1, "Colle ta clé <b>fal.ai</b> dans le champ « Clé fal.ai »", "#9C3FE4"))
    rc.addLayout(_step_row(2, "Colle ta clé <b>Anthropic</b> dans le champ « Clé Anthropic »", CP["accent2"]))
    rc.addLayout(_step_row(3, "Clique sur <b>Enregistrer</b> — c'est tout !", CP["accent"]))
    lay.addWidget(recap)

    lay.addWidget(_info_box(
        "✅  <b>Prêt à créer !</b> Une fois tes clés enregistrées, reviens sur la page "
        "<b>Scénario</b> pour commencer ton projet. Tu peux retrouver ce guide à tout moment "
        "depuis la page <b>Paramètres → Aide API</b>."
    ))

    lay.addStretch()
    return w


# ── Dialog principal ───────────────────────────────────────────────────────────

class OnboardingDialog(QDialog):

    _PAGE_TITLES = [
        "Bienvenue",
        "Configurer fal.ai",
        "Configurer Anthropic",
        "Coller les clés",
    ]

    def __init__(self, navigate_to_settings_fn=None, parent=None):
        super().__init__(parent)
        self._navigate_settings = navigate_to_settings_fn or (lambda: None)

        self.setWindowTitle("Guide de démarrage — PANDORA")
        self.setFixedSize(680, 680)
        self.setStyleSheet(PANDORA_STYLESHEET + f"QDialog{{background:{CP['bg1']};}}")

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # ── Header ─────────────────────────────────────────────────────────────
        self._header = QWidget()
        self._header.setFixedHeight(68)
        self._header.setStyleSheet(
            f"background:{CP['bg0']};border-bottom:1px solid {CP['border']};"
        )
        hl = QHBoxLayout(self._header)
        hl.setContentsMargins(28, 0, 28, 0)
        hl.setSpacing(14)

        self._step_badge = QLabel("1")
        self._step_badge.setFixedSize(38, 38)
        self._step_badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._step_badge.setStyleSheet(
            f"background:{CP['accent']};color:#07080f;border-radius:10px;"
            f"font-size:16px;font-weight:800;border:none;"
        )
        hl.addWidget(self._step_badge)

        title_col = QVBoxLayout()
        title_col.setSpacing(2)
        self._page_title = QLabel(self._PAGE_TITLES[0])
        self._page_title.setStyleSheet(
            f"color:{CP['text_primary']};font-size:16px;font-weight:800;background:transparent;"
        )
        self._dots_lbl = QLabel(self._make_dots(0))
        self._dots_lbl.setStyleSheet(
            f"color:{CP['text_dim']};font-size:11px;background:transparent;"
            f"letter-spacing:4px;"
        )
        title_col.addWidget(self._page_title)
        title_col.addWidget(self._dots_lbl)
        hl.addLayout(title_col)
        hl.addStretch()

        btn_skip = QPushButton("Passer ✕")
        btn_skip.setFixedHeight(30)
        btn_skip.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_skip.setStyleSheet(
            f"QPushButton{{background:transparent;color:{CP['text_dim']};"
            f"border:1px solid {CP['border']};border-radius:6px;"
            f"font-size:10px;font-weight:700;padding:0 12px;}}"
            f"QPushButton:hover{{color:{CP['text_secondary']};border-color:{CP['border_bright']};}}"
        )
        btn_skip.clicked.connect(self.accept)
        hl.addWidget(btn_skip)
        outer.addWidget(self._header)

        # ── Stack de pages ─────────────────────────────────────────────────────
        self._stack = QStackedWidget()
        self._stack.setStyleSheet(f"background:{CP['bg1']};")

        self._pages = [
            _page_welcome(),
            _page_fal(),
            _page_anthropic(),
            _page_finish(self._go_settings),
        ]
        for p in self._pages:
            self._stack.addWidget(p)
        outer.addWidget(self._stack, 1)

        # ── Footer ─────────────────────────────────────────────────────────────
        footer = QWidget()
        footer.setFixedHeight(64)
        footer.setStyleSheet(
            f"background:{CP['bg0']};border-top:1px solid {CP['border']};"
        )
        fl = QHBoxLayout(footer)
        fl.setContentsMargins(28, 0, 28, 0)
        fl.setSpacing(12)

        self._cb_no_show = QCheckBox("Ne plus afficher ce message")
        self._cb_no_show.setStyleSheet(
            f"QCheckBox{{color:{CP['text_dim']};font-size:10px;background:transparent;}}"
            f"QCheckBox::indicator{{width:14px;height:14px;"
            f"border:1px solid {CP['border_bright']};border-radius:3px;background:{CP['bg3']};}}"
            f"QCheckBox::indicator:checked{{background:{CP['accent']};border-color:{CP['accent']};}}"
        )
        fl.addWidget(self._cb_no_show)
        fl.addStretch()

        self._btn_prev = QPushButton("← Précédent")
        self._btn_prev.setFixedHeight(38)
        self._btn_prev.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_prev.setStyleSheet(
            f"QPushButton{{background:{CP['bg3']};color:{CP['text_secondary']};"
            f"border:1px solid {CP['border']};border-radius:8px;"
            f"font-size:12px;font-weight:700;padding:0 18px;}}"
            f"QPushButton:hover{{background:{CP['bg4']};color:{CP['text_primary']};}}"
            f"QPushButton:disabled{{background:{CP['bg2']};color:{CP['text_dim']};border-color:{CP['bg3']};}}"
        )
        self._btn_prev.clicked.connect(self._prev)
        fl.addWidget(self._btn_prev)

        self._btn_next = QPushButton("Suivant →")
        self._btn_next.setFixedHeight(38)
        self._btn_next.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_next.setStyleSheet(
            f"QPushButton{{background:{CP['accent']};color:#07080f;"
            f"border:none;border-radius:8px;"
            f"font-size:12px;font-weight:700;padding:0 20px;}}"
            f"QPushButton:hover{{background:#6eded6;}}"
        )
        self._btn_next.clicked.connect(self._next)
        fl.addWidget(self._btn_next)

        outer.addWidget(footer)

        self._idx = 0
        self._update_ui()

    # ── Navigation ─────────────────────────────────────────────────────────────

    def _make_dots(self, current: int) -> str:
        return "  ".join("●" if i == current else "○" for i in range(len(self._PAGE_TITLES)))

    def _update_ui(self):
        i = self._idx
        n = len(self._PAGE_TITLES)
        self._stack.setCurrentIndex(i)
        self._page_title.setText(self._PAGE_TITLES[i])
        self._step_badge.setText(str(i + 1))
        self._dots_lbl.setText(self._make_dots(i))
        self._btn_prev.setEnabled(i > 0)
        self._btn_next.setText("Terminer" if i == n - 1 else "Suivant →")

    def _prev(self):
        if self._idx > 0:
            self._idx -= 1
            self._update_ui()

    def _next(self):
        if self._idx < len(self._PAGE_TITLES) - 1:
            self._idx += 1
            self._update_ui()
        else:
            self._finish()

    def _finish(self):
        self._save_pref()
        self.accept()

    def _go_settings(self):
        self._save_pref()
        self.accept()
        if self._navigate_settings:
            self._navigate_settings()

    def _save_pref(self):
        if self._cb_no_show.isChecked():
            from core.config import load_config, save_config
            cfg = load_config()
            cfg["show_api_guide"] = False
            save_config(cfg)

    def closeEvent(self, e):
        self._save_pref()
        super().closeEvent(e)
