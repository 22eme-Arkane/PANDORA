"""
ui/dialog_onboarding.py — Wizard de démarrage pour les novices.

Affiché au premier lancement (ou tant que show_api_guide=True dans la config).
Refonte 2026-07-16 (maquette validée par Matthieu) : une idée par écran —
grande icône lumineuse, titre, description précise, UN bouton d'action.
8 écrans : Bienvenue → fal.ai (compte/clé/crédits) → Claude (compte/clé/
crédits) → Coller les clés. Les vraies captures assets/onboarding/*.png
s'affichent quand elles existent (sinon rien — pas de fausse maquette).
"""
from PyQt6.QtWidgets import (
    QApplication, QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFrame, QScrollArea, QWidget, QCheckBox, QStackedWidget,
    QGraphicsDropShadowEffect, QLineEdit,
)
from PyQt6.QtCore import Qt, QUrl
from PyQt6.QtGui import QDesktopServices, QColor
from ui.styles import CP, PANDORA_STYLESHEET
from core.i18n import translate

_FAL_SIGNUP   = "https://fal.ai"
_FAL_KEYS     = "https://fal.ai/dashboard/keys"
_FAL_BILLING  = "https://fal.ai/dashboard/billing"
# console.anthropic.com redirige désormais vers platform.claude.com (vérifié 2026-07-13)
_ANT_SIGNUP   = "https://platform.claude.com"
_ANT_KEYS     = "https://platform.claude.com/settings/keys"
_ANT_BILLING  = "https://platform.claude.com/settings/billing"

_TUTO_URL     = "https://www.youtube.com/watch?v=SC3pRI5bR1Q"

_FAL_COLOR    = "#9C3FE4"     # violet fal.ai (couleur de marque)


# ── Helpers visuels ────────────────────────────────────────────────────────────

def _open(url):
    QDesktopServices.openUrl(QUrl(url))


def _rgba(hex_color: str, alpha: float) -> str:
    """'#9C3FE4', 0.12 → 'rgba(156,63,228,0.12)' (doctrine : jamais de suffixe
    hex-opacity sur fond sombre)."""
    c = QColor(hex_color)
    return f"rgba({c.red()},{c.green()},{c.blue()},{alpha})"


def _glow(widget: QWidget, color: str, radius: int = 32):
    fx = QGraphicsDropShadowEffect()
    fx.setBlurRadius(radius)
    fx.setColor(QColor(color))
    fx.setOffset(0, 0)
    widget.setGraphicsEffect(fx)


def _icon_chip(char: str, color: str, size: int = 84) -> QLabel:
    """Grande icône lumineuse centrale (style maquette : glyphe + halo)."""
    ico = QLabel(char)
    ico.setFixedSize(size, size)
    ico.setAlignment(Qt.AlignmentFlag.AlignCenter)
    ico.setStyleSheet(
        f"background:{_rgba(color, 0.10)};color:{color};"
        f"border:1px solid {_rgba(color, 0.35)};border-radius:{size * 22 // 84}px;"
        f"font-size:{size * 36 // 84}px;"
    )
    _glow(ico, color, 44)
    return ico


def _kicker(text: str) -> QLabel:
    lbl = QLabel(translate(text))
    lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
    lbl.setStyleSheet(
        f"color:{CP['text_dim']};font-size:9px;font-weight:700;"
        f"font-family:'Consolas',monospace;letter-spacing:3px;background:transparent;"
    )
    return lbl


def _title(text: str) -> QLabel:
    lbl = QLabel(translate(text))
    lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
    lbl.setWordWrap(True)
    lbl.setStyleSheet(
        f"color:{CP['text_primary']};font-size:21px;font-weight:800;"
        f"background:transparent;"
    )
    return lbl


def _subtitle(text: str) -> QLabel:
    lbl = QLabel(translate(text))
    lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
    lbl.setWordWrap(True)
    lbl.setTextFormat(Qt.TextFormat.RichText)
    lbl.setStyleSheet(
        f"color:{CP['text_secondary']};font-size:12px;background:transparent;"
    )
    return lbl


def _detail_box(text: str, color: str) -> QFrame:
    """Encadré « comment faire, précisément » — noms de boutons exacts."""
    f = QFrame()
    f.setStyleSheet(
        f"QFrame{{background:{_rgba(color, 0.07)};"
        f"border:1px solid {_rgba(color, 0.30)};border-radius:10px;}}"
    )
    lay = QVBoxLayout(f)
    lay.setContentsMargins(16, 12, 16, 12)
    lbl = QLabel(translate(text))
    lbl.setWordWrap(True)
    lbl.setTextFormat(Qt.TextFormat.RichText)
    lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
    lbl.setStyleSheet(
        f"color:{CP['text_secondary']};font-size:11.5px;background:transparent;border:none;"
    )
    lay.addWidget(lbl)
    return f


def _cta(label: str, color: str, on_click) -> QPushButton:
    """Gros bouton d'action lumineux (style maquette)."""
    c = QColor(color)
    bright = QColor(color).lighter(122).name()
    lum = 0.299 * c.red() + 0.587 * c.green() + 0.114 * c.blue()
    fg = "#07080f" if lum > 150 else "#ffffff"
    btn = QPushButton(translate(label))
    btn.setFixedHeight(46)
    btn.setMinimumWidth(260)
    btn.setCursor(Qt.CursorShape.PointingHandCursor)
    btn.setStyleSheet(
        f"QPushButton{{background:qlineargradient(x1:0,y1:0,x2:1,y2:0,"
        f"stop:0 {color},stop:1 {bright});color:{fg};"
        f"border:none;border-radius:12px;font-size:13px;font-weight:700;padding:0 28px;}}"
        f"QPushButton:hover{{background:{bright};}}"
    )
    _glow(btn, color, 30)
    btn.clicked.connect(on_click)
    return btn


def _shot(filename: str) -> QWidget | None:
    """VRAIE capture d'écran si assets/onboarding/<filename> existe (déposée
    plus tard), sinon None — l'écran reste épuré, sans fausse maquette.
    Chemin frozen-aware (PyInstaller)."""
    import os, sys
    base = getattr(sys, "_MEIPASS",
                   os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    path = os.path.join(base, "assets", "onboarding", filename)
    if os.path.isfile(path):
        from PyQt6.QtGui import QPixmap
        pix = QPixmap(path)
        if not pix.isNull():
            lbl = QLabel()
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lbl.setPixmap(pix.scaledToWidth(
                480, Qt.TransformationMode.SmoothTransformation))
            lbl.setStyleSheet(
                f"background:{CP['bg2']};border:1px solid {CP['border_bright']};"
                f"border-radius:10px;padding:4px;")
            return lbl
    return None


def _key_row(cfg_key: str, placeholder: str, color: str,
             expect_prefix: str = "") -> QWidget:
    """Champ « colle ta clé ICI » : enregistre directement dans la config,
    sans obliger à passer par la page Paramètres (demande Matthieu 2026-07-16).
    Champ masqué (EchoMode.Password) comme dans Paramètres ; le bouton
    « Coller » lit le presse-papiers, remplit le champ ET enregistre."""
    box = QWidget()
    box.setStyleSheet("background:transparent;")
    v = QVBoxLayout(box)
    v.setContentsMargins(0, 0, 0, 0)
    v.setSpacing(6)

    row = QHBoxLayout()
    row.setSpacing(8)
    field = QLineEdit()
    field.setPlaceholderText(translate(placeholder))
    field.setFixedHeight(38)
    field.setEchoMode(QLineEdit.EchoMode.Password)
    field.setStyleSheet(
        f"QLineEdit{{background:{CP['bg2']};color:{CP['text_primary']};"
        f"border:1px solid {CP['border_bright']};border-radius:10px;"
        f"font-size:12px;padding:0 12px;}}"
        f"QLineEdit:focus{{border:1px solid {color};}}"
    )
    row.addWidget(field, 1)

    btn = QPushButton(translate("📋  Coller"))
    btn.setFixedHeight(38)
    btn.setCursor(Qt.CursorShape.PointingHandCursor)
    btn.setStyleSheet(
        f"QPushButton{{background:transparent;color:{color};"
        f"border:1px solid {color};border-radius:10px;"
        f"font-size:11px;font-weight:700;padding:0 16px;}}"
        f"QPushButton:hover{{background:{_rgba(color, 0.12)};}}"
    )
    row.addWidget(btn)
    v.addLayout(row)

    status = QLabel("")
    status.setWordWrap(True)
    status.setAlignment(Qt.AlignmentFlag.AlignCenter)
    status.setStyleSheet(
        f"color:{CP['text_dim']};font-size:10.5px;background:transparent;"
    )
    v.addWidget(status)

    def _set_status(text: str, col: str):
        status.setText(translate(text))
        status.setStyleSheet(f"color:{col};font-size:10.5px;background:transparent;")

    def _save():
        val = field.text().strip()
        if not val:
            _set_status("Le champ est vide — copie d'abord la clé, puis colle-la ici.",
                        CP["orange"])
            return
        from core.config import load_config, save_config
        cfg = load_config()
        cfg[cfg_key] = val
        save_config(cfg)
        if expect_prefix and not val.startswith(expect_prefix):
            _set_status("⚠️  Clé enregistrée — mais elle ne ressemble pas à une clé "
                        "attendue, vérifie au besoin.", CP["orange"])
        else:
            _set_status("✅  Clé enregistrée — tu peux passer à l'étape suivante.",
                        CP["green"])

    def _paste():
        txt = (QApplication.clipboard().text() or "").strip()
        if not txt:
            _set_status("Le presse-papiers est vide — copie d'abord la clé sur la "
                        "page ouverte, puis reviens cliquer ici.", CP["orange"])
            return
        field.setText(txt)
        _save()

    btn.clicked.connect(_paste)
    field.returnPressed.connect(_save)

    # Pré-remplissage si la clé existe déjà (guide rouvert)
    try:
        from core.config import load_config
        _existing = (load_config().get(cfg_key) or "").strip()
        if _existing:
            field.setText(_existing)
            _set_status("✅  Une clé est déjà enregistrée pour ce service.", CP["green"])
    except Exception:
        pass
    return box


def _step_page(icon_char: str, color: str, kicker: str, title: str,
               subtitle: str, detail: str = "", cta_label: str = "",
               cta_action=None, shot_file: str = "", note: str = "",
               note_color: str = "", key_cfg: str = "",
               key_placeholder: str = "", key_prefix: str = "") -> QWidget:
    """Un écran du wizard : icône lumineuse, titre, description, UN bouton."""
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
    outer_lay = QHBoxLayout(inner)
    outer_lay.setContentsMargins(48, 24, 48, 24)

    col_w = QWidget()
    col_w.setMaximumWidth(560)
    col_w.setStyleSheet("background:transparent;")
    lay = QVBoxLayout(col_w)
    lay.setContentsMargins(0, 0, 0, 0)
    lay.setSpacing(0)

    # Espacement FIXE en haut (pas de stretch) : dans un QScrollArea, la hauteur
    # des labels repliés est surestimée → un stretch haut pousserait le bas du
    # contenu sous la ligne de flottaison (vécu au rendu offscreen).
    lay.addSpacing(34)
    lay.addWidget(_kicker(kicker), 0, Qt.AlignmentFlag.AlignCenter)
    lay.addSpacing(20)
    lay.addWidget(_icon_chip(icon_char, color), 0, Qt.AlignmentFlag.AlignCenter)
    lay.addSpacing(20)
    lay.addWidget(_title(title))
    lay.addSpacing(10)
    lay.addWidget(_subtitle(subtitle))
    if detail:
        lay.addSpacing(16)
        lay.addWidget(_detail_box(detail, color))
    if shot_file:
        shot = _shot(shot_file)
        if shot is not None:
            lay.addSpacing(14)
            lay.addWidget(shot, 0, Qt.AlignmentFlag.AlignCenter)
    if note:
        lay.addSpacing(12)
        n = QLabel(translate(note))
        n.setWordWrap(True)
        n.setAlignment(Qt.AlignmentFlag.AlignCenter)
        n.setStyleSheet(
            f"color:{note_color or CP['orange']};font-size:10.5px;background:transparent;"
        )
        lay.addWidget(n)
    if cta_label:
        lay.addSpacing(20)
        lay.addWidget(_cta(cta_label, color, cta_action or (lambda: None)),
                      0, Qt.AlignmentFlag.AlignCenter)
    if key_cfg:
        lay.addSpacing(16)
        then = QLabel(translate("… puis colle la clé copiée ici :"))
        then.setAlignment(Qt.AlignmentFlag.AlignCenter)
        then.setStyleSheet(
            f"color:{CP['text_secondary']};font-size:11px;background:transparent;"
        )
        lay.addWidget(then)
        lay.addSpacing(8)
        lay.addWidget(_key_row(key_cfg, key_placeholder, color, key_prefix))
    lay.addStretch()

    outer_lay.addStretch()
    outer_lay.addWidget(col_w, 1)
    outer_lay.addStretch()
    w.setWidget(inner)
    return w


# ── Dialog principal ───────────────────────────────────────────────────────────

class OnboardingDialog(QDialog):

    def __init__(self, navigate_to_settings_fn=None, parent=None):
        super().__init__(parent)
        self._navigate_settings = navigate_to_settings_fn or (lambda: None)

        self.setWindowTitle(translate("Guide de démarrage — PANDORA"))
        self.setWindowModality(Qt.WindowModality.ApplicationModal)
        self.setStyleSheet(PANDORA_STYLESHEET + f"QDialog{{background:{CP['bg1']};}}")
        from ui.widgets import fit_dialog_to_screen
        fit_dialog_to_screen(self, 0.45, 0.88, 620, 600)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # ── Header : PANDORA — stepper — Passer (style maquette) ───────────────
        header = QWidget()
        header.setFixedHeight(58)
        header.setStyleSheet(f"background:{CP['bg1']};border:none;")
        hl = QHBoxLayout(header)
        hl.setContentsMargins(24, 0, 24, 0)
        hl.setSpacing(12)

        wordmark = QLabel("PANDORA")
        wordmark.setStyleSheet(
            f"color:{CP['text_primary']};font-size:13px;font-weight:800;"
            f"letter-spacing:3px;background:transparent;"
        )
        hl.addWidget(wordmark)
        hl.addStretch()

        btn_skip = QPushButton(translate("Passer"))
        btn_skip.setFixedHeight(28)
        btn_skip.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_skip.setStyleSheet(
            f"QPushButton{{background:transparent;color:{CP['text_dim']};"
            f"border:1px solid {CP['border']};border-radius:8px;"
            f"font-size:10px;font-weight:700;padding:0 14px;}}"
            f"QPushButton:hover{{color:{CP['text_secondary']};border-color:{CP['border_bright']};}}"
        )
        btn_skip.clicked.connect(self.accept)
        hl.addWidget(btn_skip)
        outer.addWidget(header)

        # ── Stepper centré (points reliés, étape courante = badge numéroté) ────
        self._colors = [
            CP["accent"],                     # 1 Bienvenue
            _FAL_COLOR, _FAL_COLOR, _FAL_COLOR,   # 2-4 fal.ai
            CP["accent2"], CP["accent2"], CP["accent2"],  # 5-7 Claude
            CP["green"],                      # 8 Finale
        ]
        n = len(self._colors)
        strip = QWidget()
        strip.setFixedHeight(34)
        strip.setStyleSheet("background:transparent;")
        sl = QHBoxLayout(strip)
        sl.setContentsMargins(0, 0, 0, 0)
        sl.setSpacing(6)
        sl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._step_dots: list[QLabel] = []
        self._step_lines: list[QFrame] = []
        for i in range(n):
            if i:
                line = QFrame()
                line.setFixedSize(16, 2)
                sl.addWidget(line)
                self._step_lines.append(line)
            dot = QLabel()
            dot.setAlignment(Qt.AlignmentFlag.AlignCenter)
            sl.addWidget(dot)
            self._step_dots.append(dot)
        outer.addWidget(strip)

        # ── Pages ──────────────────────────────────────────────────────────────
        self._stack = QStackedWidget()
        self._stack.setStyleSheet(f"background:{CP['bg1']};")

        A, A2, F, G = CP["accent"], CP["accent2"], _FAL_COLOR, CP["green"]
        self._pages = [
            self._page_welcome(),
            _step_page(
                "🔌", F, "FAL.AI · VIDÉOS & IMAGES — 1 SUR 3",
                "Créons ton compte fal.ai",
                "fal.ai est le service qui génère tes <b>vidéos</b> (Seedance, Kling, Veo…) "
                "et tes <b>images</b> (portraits, décors, storyboards).",
                detail="Sur la page d'accueil, clique sur <b>« Get started »</b> en haut à "
                       "droite — connexion avec <b>Google</b> ou <b>GitHub</b>, 30 secondes.",
                cta_label="🌐  Ouvrir fal.ai →",
                cta_action=lambda: _open(_FAL_SIGNUP),
            ),
            _step_page(
                "🔑", F, "FAL.AI · VIDÉOS & IMAGES — 2 SUR 3",
                "Copie ta clé fal.ai",
                "La clé API est ton <b>badge d'accès personnel</b> : PANDORA l'utilise "
                "pour lancer les générations en ton nom.",
                detail="Sur la page <b>Keys</b> : clique <b>« + Add key »</b> → nomme-la "
                       "<b>PANDORA</b> → <b>« Create »</b> → copie la clé <b>fal_key_…</b>",
                note="⚠️  La clé ne s'affiche qu'une seule fois — copie-la tout de suite.",
                shot_file="fal_keys.png",
                cta_label="🔑  Ouvrir la page Keys →",
                cta_action=lambda: _open(_FAL_KEYS),
                key_cfg="api_key",
                key_placeholder="Colle ici ta clé fal.ai (fal_key_…)",
            ),
            _step_page(
                "💳", F, "FAL.AI · VIDÉOS & IMAGES — 3 SUR 3",
                "Ajoute quelques crédits",
                "fal.ai fonctionne <b>à la consommation, sans abonnement</b> : "
                "tu ne paies que ce que tu génères.",
                detail="Sur la page <b>Billing</b> : clique <b>« Add credits »</b> — "
                       "<b>$10</b> suffisent pour bien démarrer : environ <b>20 à 50 vidéos</b> "
                       "Seedance 2.0 ($0.20–$0.50 la vidéo de 10 s).",
                cta_label="💳  Ouvrir la page Billing →",
                cta_action=lambda: _open(_FAL_BILLING),
            ),
            # NB glyphes : rester sur des emoji à présentation emoji par défaut
            # (🔌🔑💳🧠✨✅…) — les glyphes « texte » (✦ ☁ 🗝 ✓ ⚙) sortent en
            # carré vide (tofu) hors Windows/GDI (vérifié au rendu offscreen).
            _step_page(
                "🧠", A2, "CLAUDE · SCÉNARIO & STORYBOARD — 1 SUR 3",
                "Créons ton compte Claude",
                "Claude est l'IA qui t'assiste sur le <b>scénario</b>, génère le "
                "<b>storyboard</b> et optimise tes <b>prompts vidéo</b>.",
                detail="Sur <b>platform.claude.com</b> : clique <b>« Continuer avec Google »</b> "
                       "(ou avec ton adresse e-mail) — la page est en français.",
                shot_file="claude_login.png",
                cta_label="🌐  Ouvrir platform.claude.com →",
                cta_action=lambda: _open(_ANT_SIGNUP),
            ),
            _step_page(
                "🔑", A2, "CLAUDE · SCÉNARIO & STORYBOARD — 2 SUR 3",
                "Copie ta clé Claude",
                "Comme pour fal.ai : une clé personnelle — colle-la ci-dessous, "
                "PANDORA s'en souviendra.",
                detail="Sur la page <b>API Keys</b> : clique <b>« Create Key »</b> → nomme-la "
                       "<b>PANDORA</b> → <b>« Create Key »</b> → copie la clé <b>sk-ant-…</b>",
                note="⚠️  La clé ne s'affiche qu'une seule fois — copie-la tout de suite.",
                shot_file="claude_keys.png",
                cta_label="🔑  Ouvrir la page API Keys →",
                cta_action=lambda: _open(_ANT_KEYS),
                key_cfg="anthropic_key",
                key_placeholder="Colle ici ta clé Claude (sk-ant-…)",
                key_prefix="sk-ant",
            ),
            _step_page(
                "💳", A2, "CLAUDE · SCÉNARIO & STORYBOARD — 3 SUR 3",
                "Ajoute quelques crédits",
                "Même principe que fal.ai : <b>à la consommation, sans abonnement</b>.",
                detail="Sur la page <b>Billing</b> : clique <b>« Add to credit balance »</b> — "
                       "<b>$5</b> suffisent largement : des <b>centaines d'opérations</b> "
                       "(scénario, storyboard — $0.01 à $0.05 l'opération).",
                note="🔒  Si Claude ne répond pas : désactive ton VPN — certains serveurs "
                     "VPN sont bloqués par l'API.",
                cta_label="💳  Ouvrir la page Billing →",
                cta_action=lambda: _open(_ANT_BILLING),
            ),
            self._page_finish(),
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
        fl.setContentsMargins(24, 0, 24, 0)
        fl.setSpacing(12)

        self._cb_no_show = QCheckBox(translate("Ne plus afficher ce message"))
        self._cb_no_show.setStyleSheet(
            f"QCheckBox{{color:{CP['text_dim']};font-size:10px;background:transparent;}}"
            f"QCheckBox::indicator{{width:14px;height:14px;"
            f"border:1px solid {CP['border_bright']};border-radius:3px;background:{CP['bg3']};}}"
            f"QCheckBox::indicator:checked{{background:{CP['accent']};border-color:{CP['accent']};}}"
        )
        fl.addWidget(self._cb_no_show)

        btn_tuto = QPushButton(translate("▶  Tutoriel vidéo"))
        btn_tuto.setFixedHeight(28)
        btn_tuto.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_tuto.setToolTip("YouTube")
        btn_tuto.setStyleSheet(
            f"QPushButton{{background:transparent;color:{CP['text_dim']};"
            f"border:none;font-size:10px;font-weight:600;padding:0 10px;}}"
            f"QPushButton:hover{{color:{CP['text_secondary']};}}"
        )
        btn_tuto.clicked.connect(lambda: _open(_TUTO_URL))
        fl.addWidget(btn_tuto)
        fl.addStretch()

        self._btn_prev = QPushButton(translate("← Précédent"))
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

        self._btn_next = QPushButton(translate("Suivant →"))
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

        from ui.widgets import disable_default_buttons
        disable_default_buttons(self)

        self._idx = 0
        self._update_ui()

    # ── Page Bienvenue (spécifique : chips + tutoriel) ─────────────────────────

    def _page_welcome(self) -> QWidget:
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
        outer_lay = QHBoxLayout(inner)
        outer_lay.setContentsMargins(48, 12, 48, 12)

        col_w = QWidget()
        col_w.setMaximumWidth(560)
        col_w.setStyleSheet("background:transparent;")
        lay = QVBoxLayout(col_w)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)

        lay.addSpacing(34)   # fixe, pas de stretch haut (voir _step_page)
        lay.addWidget(_kicker("GUIDE DE CONFIGURATION DES SERVICES IA"),
                      0, Qt.AlignmentFlag.AlignCenter)
        lay.addSpacing(14)
        lay.addWidget(_icon_chip("✨", CP["accent"], 68),
                      0, Qt.AlignmentFlag.AlignCenter)
        lay.addSpacing(14)
        lay.addWidget(_title("Bienvenue dans PANDORA"))
        lay.addSpacing(8)
        lay.addWidget(_subtitle(
            "Deux clés, cinq minutes : c'est tout ce qu'il faut pour débloquer la génération."
        ))

        lay.addSpacing(12)
        chips = QHBoxLayout()
        chips.setSpacing(8)
        chips.addStretch()
        for txt in ("🔑  2 clés", "⏳  ≈ 5 minutes", "👌  aucune connaissance technique"):
            c = QLabel(translate(txt))
            c.setStyleSheet(
                f"color:{CP['text_secondary']};font-size:10px;font-weight:600;"
                f"background:{CP['bg2']};border:1px solid {CP['border']};"
                f"border-radius:11px;padding:4px 12px;")
            chips.addWidget(c)
        chips.addStretch()
        lay.addLayout(chips)

        lay.addSpacing(12)
        lay.addWidget(_detail_box(
            "💡  <b>Aucune clé requise pour essayer</b> — PANDORA fonctionne en mode "
            "simulation sans clé. Tu peux tout explorer et revenir configurer les "
            "clés plus tard depuis <b>Paramètres</b>.",
            CP["accent"]
        ))

        lay.addSpacing(18)
        lay.addWidget(_cta("Commencer la configuration →", CP["accent"], self._next),
                      0, Qt.AlignmentFlag.AlignCenter)
        lay.addStretch()

        outer_lay.addStretch()
        outer_lay.addWidget(col_w, 1)
        outer_lay.addStretch()
        w.setWidget(inner)
        return w

    # ── Page finale : état des clés + accès Paramètres ─────────────────────────

    def _page_finish(self) -> QWidget:
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
        outer_lay = QHBoxLayout(inner)
        outer_lay.setContentsMargins(48, 12, 48, 12)

        col_w = QWidget()
        col_w.setMaximumWidth(560)
        col_w.setStyleSheet("background:transparent;")
        lay = QVBoxLayout(col_w)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)

        G = CP["green"]
        lay.addSpacing(34)
        lay.addWidget(_kicker("DERNIÈRE ÉTAPE"), 0, Qt.AlignmentFlag.AlignCenter)
        lay.addSpacing(20)
        lay.addWidget(_icon_chip("✅", G), 0, Qt.AlignmentFlag.AlignCenter)
        lay.addSpacing(20)
        lay.addWidget(_title("Dernière vérification"))
        lay.addSpacing(10)
        lay.addWidget(_subtitle(
            "Si tu as collé tes deux clés aux étapes précédentes, tout est prêt — "
            "vérifie ci-dessous. Tu peux aussi les gérer à tout moment depuis la "
            "page <b>Paramètres</b>."
        ))

        # État des clés (rafraîchi à l'arrivée sur la page)
        lay.addSpacing(16)
        status_box = QFrame()
        status_box.setStyleSheet(
            f"QFrame{{background:{CP['bg2']};border:1px solid {CP['border']};"
            f"border-radius:10px;}}"
        )
        sb = QVBoxLayout(status_box)
        sb.setContentsMargins(18, 12, 18, 12)
        sb.setSpacing(6)
        self._status_fal = QLabel("")
        self._status_ant = QLabel("")
        for lbl in (self._status_fal, self._status_ant):
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lbl.setStyleSheet(
                f"color:{CP['text_secondary']};font-size:12px;"
                f"background:transparent;border:none;"
            )
            sb.addWidget(lbl)
        lay.addWidget(status_box)

        lay.addSpacing(12)
        lay.addWidget(_detail_box(
            "✅  Tu pourras rouvrir ce guide à tout moment depuis "
            "<b>Paramètres → Aide API</b>. Et sans clés, PANDORA reste "
            "entièrement explorable en mode simulation.",
            G
        ))
        lay.addSpacing(20)
        lay.addWidget(_cta("Aller aux Paramètres →", G, self._go_settings),
                      0, Qt.AlignmentFlag.AlignCenter)
        lay.addStretch()

        outer_lay.addStretch()
        outer_lay.addWidget(col_w, 1)
        outer_lay.addStretch()
        w.setWidget(inner)
        return w

    def _refresh_key_status(self):
        try:
            from core.config import load_config
            cfg = load_config()
        except Exception:
            cfg = {}
        for lbl, cfg_key, ok_txt, miss_txt in (
            (self._status_fal, "api_key",
             "✅  Clé fal.ai enregistrée",
             "○  Clé fal.ai manquante — reviens à l'étape 3"),
            (self._status_ant, "anthropic_key",
             "✅  Clé Claude enregistrée",
             "○  Clé Claude manquante — reviens à l'étape 6"),
        ):
            if (cfg.get(cfg_key) or "").strip():
                lbl.setText(translate(ok_txt))
                lbl.setStyleSheet(
                    f"color:{CP['green']};font-size:12px;font-weight:600;"
                    f"background:transparent;border:none;")
            else:
                lbl.setText(translate(miss_txt))
                lbl.setStyleSheet(
                    f"color:{CP['orange']};font-size:12px;"
                    f"background:transparent;border:none;")

    # ── Navigation ─────────────────────────────────────────────────────────────

    def _update_ui(self):
        i = self._idx
        n = len(self._pages)
        self._stack.setCurrentIndex(i)
        accent = self._colors[i]
        # Stepper : étape courante = badge numéroté coloré, faites = points
        # pleins, à venir = points creux ; segments parcourus colorés.
        for j, dot in enumerate(self._step_dots):
            if j == i:
                dot.setFixedSize(24, 24)
                dot.setText(str(j + 1))
                dot.setStyleSheet(
                    f"background:{accent};color:#07080f;border-radius:7px;"
                    f"font-size:11px;font-weight:800;border:none;"
                )
            elif j < i:
                dot.setFixedSize(10, 10)
                dot.setText("")
                dot.setStyleSheet(
                    f"background:{self._colors[j]};border-radius:5px;border:none;"
                )
            else:
                dot.setFixedSize(10, 10)
                dot.setText("")
                dot.setStyleSheet(
                    f"background:{CP['bg3']};border:1px solid {CP['border_bright']};"
                    f"border-radius:5px;"
                )
        for j, line in enumerate(self._step_lines):
            done = j < i
            line.setStyleSheet(
                f"background:{self._colors[j] if done else CP['border']};border:none;"
            )
        self._btn_prev.setEnabled(i > 0)
        self._btn_next.setText(translate("Terminer") if i == n - 1 else translate("Suivant →"))
        if i == n - 1:
            self._refresh_key_status()

    def _prev(self):
        if self._idx > 0:
            self._idx -= 1
            self._update_ui()

    def _next(self):
        if self._idx < len(self._pages) - 1:
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

    def showEvent(self, event):
        super().showEvent(event)
        screen = QApplication.primaryScreen()
        if screen:
            avail = screen.availableGeometry()
            x = avail.x() + max(0, (avail.width()  - self.width())  // 2)
            y = avail.y() + max(0, (avail.height() - self.height()) // 2)
            self.move(x, y)

    def closeEvent(self, e):
        self._save_pref()
        super().closeEvent(e)
