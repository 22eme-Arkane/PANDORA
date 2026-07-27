from PyQt6.QtWidgets import (
    QLabel, QFrame, QComboBox, QWidget, QVBoxLayout, QHBoxLayout,
    QTextEdit, QPushButton, QCheckBox, QProgressBar, QDialog, QDialogButtonBox,
)
from PyQt6.QtCore import Qt, QObject, QEvent, QTimer
from ui.styles import C, CP
from ui.icons import claude_icon_pixmap, install_hover_icon


def fit_dialog_to_screen(dlg, w_pct: float = 0.75, h_pct: float = 0.85,
                          min_w: int = 640, min_h: int = 480) -> None:
    """Resize dialog to fit available screen area and center it."""
    from PyQt6.QtWidgets import QApplication
    geo = QApplication.primaryScreen().availableGeometry()
    avail_w, avail_h = geo.width(), geo.height()
    pref_w = min(int(avail_w * w_pct), avail_w - 20)
    pref_h = min(int(avail_h * h_pct), avail_h - 20)
    safe_min_w = min(min_w, avail_w - 20)
    safe_min_h = min(min_h, avail_h - 20)
    dlg.setMinimumSize(safe_min_w, safe_min_h)
    w = max(pref_w, safe_min_w)
    h = max(pref_h, safe_min_h)
    dlg.resize(w, h)
    dlg.move(geo.x() + (avail_w - w) // 2, geo.y() + (avail_h - h) // 2)


class _ReadingColumnFilter(QObject):
    """Garde le texte d'un QTextEdit dans une COLONNE de lecture centrée de largeur
    MAX lisible : marges HORIZONTALES dynamiques (recalculées au redimensionnement)
    → sur un large éditeur, les lignes ne traversent plus tout l'écran, mise en page
    classique et lisible (le bloc reste centré sur la page).

    ⚠ Deux pièges corrigés (2026-07-06) :
    1. Le recalcul est DIFFÉRÉ (QTimer.singleShot 0) : un filtre d'événement voit le
       Resize AVANT que Qt n'ait redimensionné le viewport → lire viewport().width()
       tout de suite renvoie l'ANCIENNE largeur (colonne restée pleine largeur collée
       à gauche sur grand écran).
    2. On utilise les marges GAUCHE/DROITE du frame racine — PAS setDocumentMargin()
       qui s'applique aussi en HAUT/BAS (le texte descendait de 387 px sous le titre).
       La marge verticale reste petite (documentMargin fixe)."""

    def __init__(self, te, max_width: int = 820, vertical: int = 18):
        super().__init__(te)
        self._te = te
        self._max = max_width
        self._vpad = vertical
        te.document().setDocumentMargin(vertical)   # petite marge haut/bas/base
        QTimer.singleShot(0, self._sync)            # après le premier layout

    def _sync(self):
        try:
            doc = self._te.document()
            vw = self._te.viewport().width()
            if vw <= 1:
                return
            # Marge latérale du frame racine = ce qu'il faut pour centrer une colonne
            # de largeur `_max` (en tenant compte de la marge de document déjà posée).
            side = max(0, (vw - self._max) // 2 - self._vpad)
            root = doc.rootFrame()
            fmt = root.frameFormat()
            if abs(int(fmt.leftMargin()) - side) > 1:
                doc.setUndoRedoEnabled(False)       # pas de pollution de l'undo Qt
                fmt.setLeftMargin(side)
                fmt.setRightMargin(side)
                root.setFrameFormat(fmt)
                doc.setUndoRedoEnabled(True)
        except Exception:
            pass

    def eventFilter(self, obj, ev):
        if ev.type() in (QEvent.Type.Resize, QEvent.Type.Show):
            QTimer.singleShot(0, self._sync)   # après le redim. réel du viewport
        return False


def _set_reading_center(te, center: bool):
    """Aligne (ou non) le texte au CENTRE de la colonne de lecture — via l'option de
    texte par défaut du document, qui s'applique aussi au texte saisi ensuite et
    survit à setPlainText. Marqueur `_reading_center` lu par apply_paragraph_spacing."""
    try:
        from PyQt6.QtGui import QTextOption
        opt = te.document().defaultTextOption()
        opt.setAlignment(Qt.AlignmentFlag.AlignHCenter if center
                         else Qt.AlignmentFlag.AlignLeft)
        te.document().setDefaultTextOption(opt)
        te._reading_center = bool(center)
    except Exception:
        pass


def install_reading_column(te, max_width: int = 820, vertical: int = 18,
                           center: bool = False):
    """Contraint un QTextEdit à une colonne de lecture centrée (largeur max lisible).

    Le texte est cadré dans une colonne centrée sur la page (au lieu de laisser les
    lignes traverser tout l'écran). `center=True` : le texte est en plus aligné au
    CENTRE de cette colonne (mise en page façon Word) ; sinon il reste à GAUCHE.
    Marges latérales dynamiques (frame racine) ; marge haut/bas = `vertical` (petite).
    """
    f = _ReadingColumnFilter(te, max_width, vertical)
    te.installEventFilter(f)
    te._reading_column_filter = f    # référence anti-GC
    _set_reading_center(te, center)
    return f


def scrollbar_on_left(te):
    """Place la scrollbar VERTICALE d'un QTextEdit sur son bord GAUCHE (widget en
    disposition droite-à-gauche) SANS toucher au sens de lecture : la direction du
    texte est verrouillée gauche-à-droite sur le document (demande Matthieu
    2026-07-23 : scrollbar du Scénario collée à la bande GUIDE)."""
    from PyQt6.QtCore import Qt
    te.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
    opt = te.document().defaultTextOption()
    opt.setTextDirection(Qt.LayoutDirection.LeftToRight)
    te.document().setDefaultTextOption(opt)


def apply_paragraph_spacing(te, px: int = 12, center=None):
    """Ajoute une RESPIRATION sous chaque paragraphe (bloc) d'un QTextEdit — « retour
    à la ligne » visuel entre les paragraphes, sans polluer l'undo Qt ni déplacer le
    curseur de l'utilisateur. Les blocs saisis ensuite héritent du format.
    `center` : None = déduit du marqueur `_reading_center` posé par install_reading_column
    (colonne centrée → texte centré) ; True/False force l'alignement.
    À appeler après avoir écrit le texte (setPlainText)."""
    try:
        from PyQt6.QtGui import QTextCursor, QTextBlockFormat
        if center is None:
            center = bool(getattr(te, "_reading_center", False))
        doc = te.document()
        doc.setUndoRedoEnabled(False)
        cur = QTextCursor(doc)                     # curseur détaché : ne bouge pas celui de l'UI
        cur.select(QTextCursor.SelectionType.Document)
        bf = QTextBlockFormat()
        bf.setBottomMargin(px)                     # respiration entre paragraphes
        bf.setAlignment(Qt.AlignmentFlag.AlignHCenter if center
                        else Qt.AlignmentFlag.AlignLeft)
        cur.mergeBlockFormat(bf)
        doc.setUndoRedoEnabled(True)
        # Le texte tapé ENSUITE hérite aussi de l'alignement voulu.
        if center:
            te.setAlignment(Qt.AlignmentFlag.AlignHCenter)
    except Exception:
        pass


def show_api_error(parent, message: str):
    """Affiche une fenêtre d'erreur. Si c'est une erreur de crédit fal.ai, dialog dédié."""
    from core.worker import is_credit_error
    if is_credit_error(message):
        dlg = QDialog(parent)
        dlg.setWindowTitle("Crédits insuffisants")
        dlg.setMinimumWidth(420)
        dlg.setStyleSheet(
            f"QDialog{{background:{CP['bg1']};color:{CP['text_primary']};}}"
            f"QLabel{{background:transparent;color:{CP['text_primary']};}}"
        )
        lay = QVBoxLayout(dlg)
        lay.setContentsMargins(28, 24, 28, 20)
        lay.setSpacing(16)

        ico = QLabel("💳")
        ico.setAlignment(Qt.AlignmentFlag.AlignCenter)
        ico.setStyleSheet("font-size:40px;background:transparent;")
        lay.addWidget(ico)

        title = QLabel("Crédits fal.ai insuffisants")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet(
            f"color:{CP.get('red','#ff4f6a')};font-size:15px;font-weight:700;"
            f"background:transparent;"
        )
        lay.addWidget(title)

        body = QLabel(
            "La génération n'a pas pu démarrer.\n\n"
            "Rechargez votre compte sur fal.ai/dashboard\n"
            "pour continuer à utiliser PANDORA."
        )
        body.setAlignment(Qt.AlignmentFlag.AlignCenter)
        body.setWordWrap(True)
        body.setStyleSheet(
            f"color:{CP['text_secondary']};font-size:11px;background:transparent;"
        )
        lay.addWidget(body)

        btns = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok)
        btns.button(QDialogButtonBox.StandardButton.Ok).setText("OK")
        btns.button(QDialogButtonBox.StandardButton.Ok).setStyleSheet(
            f"QPushButton{{background:{CP.get('red','#ff4f6a')};color:#fff;"
            f"border:none;border-radius:8px;font-size:12px;font-weight:700;"
            f"padding:8px 28px;}}"
            f"QPushButton:hover{{background:#cc2040;}}"
        )
        btns.accepted.connect(dlg.accept)
        lay.addWidget(btns, 0, Qt.AlignmentFlag.AlignCenter)

        dlg.exec()
    else:
        from PyQt6.QtWidgets import QMessageBox
        QMessageBox.critical(parent, "Erreur de génération", message)


class _WheelIgnoreFilter(QObject):
    """Blocks scroll-wheel events so combos/spinboxes don't change accidentally."""
    def eventFilter(self, obj, event):
        if event.type() == QEvent.Type.Wheel:
            event.ignore()
            return True
        return super().eventFilter(obj, event)


class WheelHScroller(QObject):
    """Molette → défilement HORIZONTAL d'un QScrollArea (bandes de miniatures).

    Par défaut Qt route la molette vers le scroll vertical : sur une bande
    horizontale, elle ne fait rien. Usage :
        WheelHScroller.attach(scroll_area)
    """
    def __init__(self, area):
        super().__init__(area)
        self._area = area

    def eventFilter(self, obj, event):
        if event.type() == QEvent.Type.Wheel:
            sb = self._area.horizontalScrollBar()
            delta = event.angleDelta().y() or event.angleDelta().x()
            sb.setValue(sb.value() - delta)
            return True
        return super().eventFilter(obj, event)

    @classmethod
    def attach(cls, area):
        f = cls(area)
        area.viewport().installEventFilter(f)
        return f


def disable_default_buttons(dlg) -> None:
    """Neutralise les boutons « auto-default » d'un QDialog.

    Par défaut Qt fait de chaque QPushButton un bouton par défaut potentiel :
    appuyer sur Entrée dans un champ déclenche le premier bouton du dialogue
    (Annuler, Appliquer…) au lieu d'envoyer le message. À appeler juste avant
    dlg.exec() sur toute fenêtre contenant un champ de saisie + des boutons."""
    from PyQt6.QtWidgets import QPushButton
    for b in dlg.findChildren(QPushButton):
        b.setAutoDefault(False)
        b.setDefault(False)


# ── Help block ─────────────────────────────────────────────────────────────────

class HelpBlock(QFrame):
    """Collapsible contextual help strip — collapsed by default, discreet 28 px bar.

    RETIRÉ DE L'AFFICHAGE le 2026-07-23 (demande Matthieu) : le guide complet du
    panneau GUIDE remplace ces bandeaux dans tous les onglets. Le composant et
    ses textes restent en place — remettre ``_HELP_STRIPS_VISIBLE = True`` pour
    les réafficher.
    """

    _HELP_STRIPS_VISIBLE = False

    def __init__(self, title: str, lines: list[str], colors: dict | None = None):
        super().__init__()
        clr = colors or C
        self._title = title
        self.setObjectName("help_block")
        if not HelpBlock._HELP_STRIPS_VISIBLE:
            self.setVisible(False)
            self.setMaximumHeight(0)
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
        # « & » nu = mnémonique Qt sur un QPushButton (caractère avalé + soulignement)
        _t = _tr(title).replace("&", "&&")
        self._btn = QPushButton(f"ℹ  {_t}    ▶")
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
        _t = _tr(self._title).replace("&", "&&")
        self._btn.setText(f"ℹ  {_t}    {arrow}")


def section_label(text: str) -> QLabel:
    lbl = QLabel(text.upper())
    lbl.setStyleSheet(
        f"color:{C['accent']};font-size:9px;letter-spacing:2px;"
        f"font-family:'Consolas',monospace;font-weight:700;margin-bottom:4px;"
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
    cb.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
    cb.installEventFilter(_wheel_ignore)
    for opt in options:
        if isinstance(opt, tuple):
            cb.addItem(opt[0], opt[1])  # (label, data)
        else:
            cb.addItem(str(opt))
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

    loading_lbl = QLabel("⟳  optimisation…")
    loading_lbl.setStyleSheet(
        f"color:{C['accent']};font-size:9px;font-style:italic;background:transparent;border:none;"
    )
    loading_lbl.setVisible(False)
    cloud._loading = loading_lbl

    header.addWidget(counter)
    header.addStretch()
    # « Améliorer le prompt » RETIRÉ (Cinéma + Live) : la fonction dégradait les
    # prompts (storyboard notamment) et n'était pas fiable. On ne l'ajoute plus au
    # header. Les objets (cloud / auto_cb / loading) restent créés et CACHÉS pour ne
    # casser aucun appelant qui les déballe encore (prompt_block renvoie 4 valeurs).
    auto_cb.setChecked(False)
    for _w in (loading_lbl, auto_cb, cloud):
        _w.setVisible(False)

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


def make_actions_menu_button(bar, entries, red_entry=None, label="Action"):
    """Bouton « ☰ Action » + menu déroulant reprenant des boutons EXISTANTS
    (principe introduit sur le Storyboard le 2026-07-22).

    Les boutons sources sont reparentés à ``bar`` et cachés : toute la logique
    d'état existante (setEnabled/setText) continue d'écrire dedans, et le menu se
    recale sur leur texte/état/infobulle à chaque ouverture. ``red_entry`` est un
    bouton destructif affiché en ROUGE (via QWidgetAction, seule façon de colorer
    une entrée individuelle de QMenu).
    """
    from PyQt6.QtWidgets import QMenu, QWidgetAction, QPushButton
    from core.i18n import translate as _tr

    sources = list(entries) + ([red_entry] if red_entry is not None else [])
    for _b in sources:
        _b.setParent(bar)
        _b.hide()

    btn = QPushButton("☰  " + _tr(label))
    btn.setFixedHeight(36)
    btn.setStyleSheet(
        f"QPushButton{{background:transparent;color:{CP['accent']};"
        f"border:1px solid {CP['accent']};border-radius:8px;"
        f"font-size:11px;font-weight:700;padding:0 14px;}}"
        f"QPushButton:hover{{background:rgba(78,205,196,0.12);}}"
        f"QPushButton:pressed{{background:rgba(78,205,196,0.22);}}"
        f"QPushButton::menu-indicator{{image:none;width:0;}}"
    )
    menu = QMenu(btn)
    menu.setStyleSheet(
        f"QMenu{{background:{CP['bg2']};border:1px solid {CP['border_bright']};"
        f"border-radius:8px;padding:6px;}}"
        f"QMenu::item{{color:{CP['text_primary']};padding:7px 18px;font-size:11px;}}"
        f"QMenu::item:selected{{background:{CP.get('accent_dim', CP['bg3'])};color:{CP['text_primary']};}}"
        f"QMenu::item:disabled{{color:{CP['text_dim']};}}"
    )
    menu.setToolTipsVisible(True)
    pairs = [(menu.addAction(""), _src) for _src in entries]
    for _act, _src in pairs:
        _act.triggered.connect(_src.click)   # .click() respecte l'état désactivé

    del_btn = None
    if red_entry is not None:
        _wa = QWidgetAction(menu)
        del_btn = QPushButton()
        del_btn.setFlat(True)
        del_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        del_btn.setStyleSheet(
            f"QPushButton{{background:transparent;color:{CP['red']};border:none;"
            f"border-radius:0px;padding:7px 18px;font-size:11px;text-align:left;}}"
            f"QPushButton:hover{{background:rgba(255,79,106,0.12);}}"
            f"QPushButton:disabled{{color:{CP['text_dim']};}}"
        )

        def _red_clicked():
            menu.close()
            red_entry.click()

        del_btn.clicked.connect(_red_clicked)
        _wa.setDefaultWidget(del_btn)
        menu.addAction(_wa)

    def _sync():
        for _act, _src in pairs:
            _act.setText(_src.text())
            _act.setToolTip(_src.toolTip())
            _act.setEnabled(_src.isEnabled())
        if del_btn is not None:
            del_btn.setText(red_entry.text())
            del_btn.setToolTip(red_entry.toolTip())
            del_btn.setEnabled(red_entry.isEnabled())

    menu.aboutToShow.connect(_sync)
    btn.setMenu(menu)
    return btn


class ResolutionCombo(QComboBox):
    """Définition des images générées — le MÊME sélecteur partout.

    Un seul composant pour le Cinéma, le Live et le Studio IA : c'est ce qui
    garantit que les quatre paliers, leurs libellés et leur défaut ne divergent
    pas d'une page à l'autre au premier ajout.

    Pourquoi il existe (2026-07-27, demande Matthieu) : les tailles cibles
    étaient figées dans une table héritée des buckets SDXL, dont les ratios sont
    FAUX (« 16:9 » y valait 1,750 au lieu de 1,7778). Toute image sortait
    légèrement étirée, et un Mood étiré servant d'image de départ à une
    génération vidéo déforme la façade qu'on projette sur un bâtiment réel.
    Le calcul juste vit dans `core.image_resolution` ; ce widget n'en est que
    la façade.

    Ne persiste RIEN : il lit un défaut éventuel dans la config, il ne l'écrit
    jamais. Les pages Paramètres sont en auto-save, et un combo qui écrit la
    vraie `config.json` au premier changement d'index est précisément le piège
    qui a déjà corrompu les clés API du projet.
    """

    def __init__(self, parent=None, *, compact: bool = False):
        super().__init__(parent)
        from core.image_resolution import DEFAULT_KEY, RESOLUTIONS
        for _key, _label in RESOLUTIONS:
            self.addItem(_label, _key)
        _default = DEFAULT_KEY
        try:
            from core.config import load_config
            _default = (load_config().get("image_resolution") or DEFAULT_KEY)
        except Exception:
            pass
        _i = self.findData(_default)
        self.setCurrentIndex(_i if _i >= 0 else self.findData(DEFAULT_KEY))
        self.setFixedHeight(26 if compact else 30)
        self.setToolTip(
            "Définition des images générées.\n"
            "Le ratio est toujours EXACT : c'est lui qui garantit que l'image "
            "se superpose sans déformation.")
        _fs = 10 if compact else 11
        self.setStyleSheet(
            f"QComboBox{{background:{CP['bg3']};border:1px solid {CP['border']};"
            f"border-radius:6px;color:{CP['text_primary']};font-size:{_fs}px;padding:0 8px;}}"
            f"QComboBox::drop-down{{border:none;width:20px;}}"
            f"QComboBox QAbstractItemView{{background:{CP['bg3']};"
            f"border:1px solid {CP['border_bright']};color:{CP['text_primary']};"
            f"selection-background-color:{CP['accent_dim']};}}"
        )

    def resolution_key(self) -> str:
        """Palier choisi (« 720p » … « 4k »). Jamais vide."""
        from core.image_resolution import DEFAULT_KEY, normalize_key
        return normalize_key(self.currentData() or DEFAULT_KEY)

    def target(self, aspect_ratio: str = "16:9") -> tuple:
        """(largeur, hauteur) au ratio EXACT pour ce palier."""
        from core.image_resolution import target_for
        return target_for(aspect_ratio, self.resolution_key())


class RatioCombo(QComboBox):
    """Format (ratio) de l'image générée — composant PARTAGÉ, comme ResolutionCombo.

    Première entrée « Automatique », de donnée VIDE : c'est le défaut, et il
    laisse chaque appelant garder sa règle historique (1:1 pour un accessoire,
    16:9 pour un décor, 2:3 pour un portrait classique, 9:16 pour une pose
    d'action…). Sans cette entrée, poser le combo changerait le rendu de toutes
    les générations existantes le jour de l'installation — un réglage neuf ne
    doit jamais modifier ce que l'utilisateur obtenait la veille.

    `ratio()` renvoie donc "" tant que l'utilisateur n'a rien choisi, et
    l'appelant s'écrit `self._ar_override or <sa règle>`.
    """

    # Les ratios réellement utiles en production. Tous exacts par construction :
    # c'est core.image_resolution qui en dérive les dimensions.
    CHOICES = (
        ("",      "Automatique"),
        ("1:1",   "1:1  ·  carré"),
        ("16:9",  "16:9  ·  paysage"),
        ("9:16",  "9:16  ·  portrait"),
        ("4:3",   "4:3  ·  paysage classique"),
        ("3:4",   "3:4  ·  portrait classique"),
        ("3:2",   "3:2  ·  photo"),
        ("2:3",   "2:3  ·  photo portrait"),
        ("21:9",  "21:9  ·  cinémascope"),
        ("4:5",   "4:5  ·  portrait réseaux"),
    )

    def __init__(self, parent=None, *, compact: bool = False,
                 auto_hint: str = ""):
        super().__init__(parent)
        for _key, _label in self.CHOICES:
            self.addItem(
                (f"{_label} ({auto_hint})" if (not _key and auto_hint) else _label),
                _key)
        self.setCurrentIndex(0)
        self.setFixedHeight(26 if compact else 30)
        self.setToolTip(
            "Format de l'image générée.\n"
            "« Automatique » garde le format habituel de cet élément.")
        _fs = 10 if compact else 11
        self.setStyleSheet(
            f"QComboBox{{background:{CP['bg3']};border:1px solid {CP['border']};"
            f"border-radius:6px;color:{CP['text_primary']};font-size:{_fs}px;padding:0 8px;}}"
            f"QComboBox::drop-down{{border:none;width:20px;}}"
            f"QComboBox QAbstractItemView{{background:{CP['bg3']};"
            f"border:1px solid {CP['border_bright']};color:{CP['text_primary']};"
            f"selection-background-color:{CP['accent_dim']};}}"
        )

    def ratio(self) -> str:
        """Ratio choisi (« 16:9 »…), ou "" si « Automatique »."""
        return (self.currentData() or "").strip()


# Ce que l'utilisateur doit comprendre en ouvrant un encart de prompt : ce texte
# est un DOCUMENT DE TRAVAIL, pas ce qui part au moteur. Sans cette phrase, les
# étiquettes SURFACE / ÉTAT 0 / ACTION passent pour ce que le moteur va lire, et
# on cherche longtemps pourquoi le rendu ne correspond pas (constat Matthieu,
# 2026-07-27). Composant PARTAGÉ : la même explication au Cinéma et au Live.
PROMPT_WORKFLOW_NOTE = (
    "Ce prompt est votre document de travail : gardez ces blocs, ils structurent "
    "le plan. À chaque envoi, PANDORA le réécrit pour le moteur choisi — en "
    "anglais, en texte continu, sans les étiquettes — selon la grammaire propre "
    "à la vidéo ou à l'image."
)


def prompt_workflow_label(parent=None) -> QLabel:
    """Note d'explication à poser JUSTE AU-DESSUS d'un encart de prompt."""
    from core.i18n import translate
    lbl = QLabel(translate(PROMPT_WORKFLOW_NOTE), parent)
    lbl.setWordWrap(True)
    # La hauteur minimale d'un QLabel en wordWrap ne compte qu'UNE ligne : sans
    # ce correctif, le layout réclame moins qu'il ne lui faut et Qt redimensionne
    # la fenêtre à une taille que Windows refuse (cf. dialog_reference_images).
    lbl.setStyleSheet(
        f"color:{CP['text_dim']};font-size:11px;font-style:italic;"
        f"background:transparent;border:none;")
    return lbl
