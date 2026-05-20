"""
ui/assistant_panel.py — Panneau assistant pédagogique contextuel.

Panneau droit collapsible :
  - Tips statiques par page (corpus)
  - Chat Claude Haiku pour les questions libres
  - Toggle strip 20px toujours visible
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTextEdit, QScrollArea,
)
from PyQt6.QtCore import Qt
from ui.styles import CP


# ── Corpus de tips par page ────────────────────────────────────────────────────

CORPUS: dict[str, dict] = {
    "projects": {
        "title": "Projets",
        "context": "L'utilisateur gère ses projets de pré-production cinéma dans PANDORA.",
        "tips": [
            "Chaque projet dispose de son propre dossier de données isolé.",
            "Renommez un projet depuis sa fiche en cliquant sur son nom.",
            "Changez de projet depuis cette page sans quitter PANDORA.",
        ],
    },
    "scenario": {
        "title": "Scénario",
        "context": "L'utilisateur édite son scénario cinéma avec l'assistant Claude IA.",
        "tips": [
            "'Formater' applique la mise en page cinéma standard automatiquement.",
            "Créez des versions nommées avant chaque révision majeure.",
            "Extrayez personnages, décors et accessoires en un clic depuis le panneau IA.",
        ],
    },
    "storyboard": {
        "title": "Storyboard",
        "context": "L'utilisateur gère son découpage storyboard plan par plan.",
        "tips": [
            "Double-cliquez sur un plan pour éditer tous ses détails.",
            "Générez un aperçu visuel Flux T2I depuis le bouton '⊕ Aperçu'.",
            "Glissez-déposez les plans pour réorganiser le découpage.",
        ],
    },
    "castings": {
        "title": "Castings",
        "context": "L'utilisateur gère les personnages du film.",
        "tips": [
            "Générez un portrait de personnage via Nano Banana depuis la fiche.",
            "Les portraits servent de références visuelles dans la génération Seedance.",
            "Cochez 'Assigné' pour qu'un personnage apparaisse dans les sélections T2V.",
        ],
    },
    "decors": {
        "title": "Décors",
        "context": "L'utilisateur gère les décors et lieux de tournage.",
        "tips": [
            "Générez une image de référence du décor via Nano Banana.",
            "Chaque décor peut avoir son propre style visuel (cinéma, photoréaliste…).",
            "'Sheet 4 vues' génère quatre angles différents d'un même lieu.",
        ],
    },
    "accessoires": {
        "title": "Accessoires",
        "context": "L'utilisateur gère les accessoires (props) du film.",
        "tips": [
            "Associez un style visuel spécifique à chaque accessoire.",
            "'Générer une variation' crée une alternative de l'image existante.",
            "Les accessoires assignés à un plan sont envoyés en référence à Seedance.",
        ],
    },
    "hmc": {
        "title": "HMC",
        "context": "L'utilisateur gère l'habillage, maquillage et coiffure du film.",
        "tips": [
            "HMC = Habillage, Maquillage, Coiffure — éléments de costume et beauté.",
            "Associez des éléments HMC à des personnages ou des séquences.",
            "Générez une image de référence pour chaque élément.",
        ],
    },
    "vehicles": {
        "title": "Véhicules",
        "context": "L'utilisateur gère les véhicules du film.",
        "tips": [
            "Renseignez marque, modèle, année et couleur pour chaque véhicule.",
            "Générez une image de référence via Nano Banana.",
            "Les véhicules assignés sont inclus dans les mosaïques de référence Seedance.",
        ],
    },
    "camera": {
        "title": "Image & Son",
        "context": "L'utilisateur configure les préférences caméra et son du projet.",
        "tips": [
            "Définissez la caméra principale, les optiques et le format d'image.",
            "Ces informations pré-remplissent les champs techniques des plans storyboard.",
            "Renseignez le micro et la chaîne son pour le tournage.",
        ],
    },
    "doublage": {
        "title": "Doublage",
        "context": "L'utilisateur génère des pistes audio TTS pour le doublage.",
        "tips": [
            "Kokoro TTS propose 30 voix pré-entraînées (EN, ES, JA, ZH…).",
            "Lux TTS clone n'importe quelle voix à partir d'un échantillon audio.",
            "Les fichiers audio générés peuvent être importés dans DaVinci Resolve.",
        ],
    },
    "seedance": {
        "title": "Studio IA",
        "context": "L'utilisateur génère des clips vidéo IA avec Seedance et d'autres moteurs.",
        "tips": [
            "T2V : décrivez la scène en français, le prompt est traduit automatiquement.",
            "Si des personnages/décors sont assignés, ils servent de références visuelles.",
            "L'onglet 'Génération directe' donne accès à 13 moteurs : Kling, Veo 3.1, PixVerse, Sora 2…",
        ],
    },
    "settings": {
        "title": "Paramètres",
        "context": "L'utilisateur configure les clés API et les préférences globales.",
        "tips": [
            "Clé fal.ai requise pour Seedance, Kling, Veo 3.1, PixVerse et Flux.",
            "Clé Anthropic requise pour l'assistant IA et la génération de scénario.",
            "Clé Nano Banana requise pour les portraits et images d'éléments.",
        ],
    },
}

_DEFAULT_CORPUS = {
    "title": "PANDORA",
    "context": "Logiciel de pré-production cinéma pour DaVinci Resolve.",
    "tips": [
        "Naviguez entre les sections depuis la barre latérale gauche.",
        "Les données sont sauvegardées automatiquement.",
        "Utilisez Ctrl+S pour une sauvegarde manuelle.",
    ],
}


# ── Panneau assistant ──────────────────────────────────────────────────────────

class AssistantPanel(QWidget):
    """Panneau assistant contextuel avec corpus par page et chat Haiku."""

    def __init__(self):
        super().__init__()
        self._history:  list[dict] = []
        self._worker    = None
        self._page_key  = ""
        self._corpus    = _DEFAULT_CORPUS
        self._ai_enabled: bool = False   # désactivé par défaut

        self.setFixedWidth(258)
        self.setStyleSheet(
            f"background:{CP['bg1']};border-left:1px solid {CP['border']};"
        )

        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)

        # ── En-tête ────────────────────────────────────────────────────────────
        header = QWidget()
        header.setFixedHeight(50)
        header.setStyleSheet(
            f"background:{CP['bg2']};border-bottom:1px solid {CP['border']};"
        )
        hl = QHBoxLayout(header)
        hl.setContentsMargins(14, 0, 10, 0)
        hl.setSpacing(8)

        ico = QLabel("✦")
        ico.setStyleSheet(
            f"color:{CP['accent']};font-size:14px;background:transparent;"
        )
        hl.addWidget(ico)

        self._title_lbl = QLabel("Assistant")
        self._title_lbl.setStyleSheet(
            f"color:{CP['text_primary']};font-size:13px;font-weight:700;"
            f"background:transparent;"
        )
        hl.addWidget(self._title_lbl)
        hl.addStretch()

        self._btn_ai_toggle = QPushButton("IA ○")
        self._btn_ai_toggle.setFixedHeight(22)
        self._btn_ai_toggle.setMinimumWidth(46)
        self._btn_ai_toggle.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_ai_toggle.setToolTip(
            "Activer l'assistant IA — utilise des crédits Anthropic\n"
            "(désactivé par défaut)"
        )
        self._btn_ai_toggle.setStyleSheet(
            f"QPushButton{{background:transparent;color:{CP['text_dim']};"
            f"border:1px solid {CP['border']};border-radius:5px;"
            f"font-size:9px;font-weight:700;padding:0 6px;}}"
            f"QPushButton:hover{{border-color:{CP['border_bright']};"
            f"color:{CP['text_secondary']};}}"
        )
        self._btn_ai_toggle.clicked.connect(self._toggle_ai)
        hl.addWidget(self._btn_ai_toggle)

        btn_clear = QPushButton("✕")
        btn_clear.setFixedSize(20, 20)
        btn_clear.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_clear.setToolTip("Effacer la conversation")
        btn_clear.setStyleSheet(
            f"QPushButton{{background:transparent;color:{CP['text_dim']};"
            f"border:none;font-size:10px;font-weight:700;}}"
            f"QPushButton:hover{{color:{CP['text_primary']};}}"
        )
        btn_clear.clicked.connect(self._clear_chat)
        hl.addWidget(btn_clear)
        lay.addWidget(header)

        # ── Tips contextuels ───────────────────────────────────────────────────
        self._tips_frame = QWidget()
        self._tips_frame.setStyleSheet(
            f"background:rgba(78,205,196,0.05);"
            f"border-bottom:1px solid {CP['border']};"
        )
        tips_lay = QVBoxLayout(self._tips_frame)
        tips_lay.setContentsMargins(12, 10, 12, 10)
        tips_lay.setSpacing(6)

        self._page_lbl = QLabel("PANDORA")
        self._page_lbl.setStyleSheet(
            f"color:{CP['accent']};font-size:9px;font-weight:700;"
            f"letter-spacing:2px;background:transparent;"
        )
        tips_lay.addWidget(self._page_lbl)

        self._context_lbl = QLabel()
        self._context_lbl.setWordWrap(True)
        self._context_lbl.setStyleSheet(
            f"color:{CP['text_dim']};font-size:10px;font-style:italic;"
            f"background:transparent;"
        )
        tips_lay.addWidget(self._context_lbl)

        _sep = QLabel()
        _sep.setFixedHeight(1)
        _sep.setStyleSheet(f"background:{CP['border']};")
        tips_lay.addWidget(_sep)

        _conseils_lbl = QLabel("CONSEILS")
        _conseils_lbl.setStyleSheet(
            f"color:{CP['text_dim']};font-size:8px;font-weight:700;"
            f"letter-spacing:2px;background:transparent;"
        )
        tips_lay.addWidget(_conseils_lbl)

        self._tips_lbl = QLabel()
        self._tips_lbl.setWordWrap(True)
        self._tips_lbl.setStyleSheet(
            f"color:{CP['text_secondary']};font-size:10px;background:transparent;"
        )
        tips_lay.addWidget(self._tips_lbl)
        lay.addWidget(self._tips_frame)

        # ── Zone de chat ───────────────────────────────────────────────────────
        chat_scroll = QScrollArea()
        chat_scroll.setWidgetResizable(True)
        chat_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        chat_scroll.setStyleSheet(
            f"QScrollArea{{background:{CP['bg1']};border:none;}}"
            f"QScrollBar:vertical{{width:4px;background:{CP['bg2']};}}"
            f"QScrollBar::handle:vertical{{background:{CP['border_bright']};border-radius:2px;}}"
        )
        self._chat_container = QWidget()
        self._chat_container.setStyleSheet(f"background:{CP['bg1']};")
        self._chat_lay = QVBoxLayout(self._chat_container)
        self._chat_lay.setContentsMargins(10, 14, 10, 8)
        self._chat_lay.setSpacing(8)
        self._chat_lay.addStretch()
        chat_scroll.setWidget(self._chat_container)
        self._chat_scroll = chat_scroll
        lay.addWidget(chat_scroll, 1)

        # ── Input ──────────────────────────────────────────────────────────────
        input_frame = QWidget()
        input_frame.setStyleSheet(
            f"background:{CP['bg2']};border-top:1px solid {CP['border']};"
        )
        input_lay = QVBoxLayout(input_frame)
        input_lay.setContentsMargins(10, 8, 10, 10)
        input_lay.setSpacing(6)

        # Notice "IA désactivée" — visible quand désactivé
        self._disabled_notice = QLabel(
            "L'assistant IA est désactivé.\n"
            "Activez-le via « IA ○ » pour poser des questions.\n"
            "(Utilise des crédits Anthropic)"
        )
        self._disabled_notice.setWordWrap(True)
        self._disabled_notice.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._disabled_notice.setStyleSheet(
            f"color:{CP['text_dim']};font-size:10px;font-style:italic;"
            f"padding:8px 4px;background:transparent;"
        )
        input_lay.addWidget(self._disabled_notice)

        self._input = QTextEdit()
        self._input.setPlaceholderText("Posez une question sur cette page…")
        self._input.setFixedHeight(56)
        self._input.setStyleSheet(
            f"QTextEdit{{background:{CP['bg3']};border:1px solid {CP['border']};"
            f"border-radius:6px;color:{CP['text_primary']};font-size:11px;"
            f"padding:5px 8px;}}"
            f"QTextEdit:focus{{border-color:{CP['accent_dim']};}}"
        )
        self._input.setVisible(False)
        input_lay.addWidget(self._input)

        self._btn_ask = QPushButton("✦  Demander")
        self._btn_ask.setMinimumHeight(32)
        self._btn_ask.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_ask.setStyleSheet(
            f"QPushButton{{background:{CP['accent']};color:#07080f;"
            f"border:none;border-radius:6px;font-size:11px;font-weight:700;"
            f"padding:0 12px;}}"
            f"QPushButton:hover{{background:#6eded6;}}"
            f"QPushButton:pressed{{background:{CP['accent_dim']};color:#fff;}}"
            f"QPushButton:disabled{{background:{CP['bg3']};color:{CP['text_dim']};}}"
        )
        self._btn_ask.clicked.connect(self._on_ask)
        self._btn_ask.setVisible(False)
        input_lay.addWidget(self._btn_ask)
        lay.addWidget(input_frame)

        self._update_tips()

    # ── API publique ───────────────────────────────────────────────────────────

    def set_context(self, page_key: str):
        if page_key == self._page_key:
            return
        self._page_key = page_key
        self._corpus   = CORPUS.get(page_key, _DEFAULT_CORPUS)
        self._update_tips()

    # ── Activation IA ─────────────────────────────────────────────────────────

    def _toggle_ai(self):
        self._ai_enabled = not self._ai_enabled
        self._apply_ai_state()

    def _apply_ai_state(self):
        on = self._ai_enabled
        self._btn_ai_toggle.setText("IA ●" if on else "IA ○")
        self._btn_ai_toggle.setStyleSheet(
            f"QPushButton{{background:{'rgba(78,205,196,0.15)' if on else 'transparent'};"
            f"color:{CP['accent'] if on else CP['text_dim']};"
            f"border:1px solid {CP['accent'] if on else CP['border']};border-radius:5px;"
            f"font-size:9px;font-weight:700;padding:0 6px;}}"
            f"QPushButton:hover{{border-color:{CP['accent_dim']};color:{CP['accent']};}}"
        )
        self._disabled_notice.setVisible(not on)
        self._input.setVisible(on)
        self._btn_ask.setVisible(on)

    # ── Interne ────────────────────────────────────────────────────────────────

    def _update_tips(self):
        self._page_lbl.setText(self._corpus["title"].upper())
        self._context_lbl.setText(self._corpus.get("context", ""))
        tips = self._corpus.get("tips", [])
        self._tips_lbl.setText("\n".join(f"· {t}" for t in tips))

    def _on_ask(self):
        if not self._ai_enabled:
            return
        if self._worker and self._worker.isRunning():
            return
        question = self._input.toPlainText().strip()
        if not question:
            return

        self._add_bubble("user", question)
        self._input.clear()
        self._btn_ask.setEnabled(False)
        self._btn_ask.setText("…")

        from api.assistant import AssistantWorker
        self._worker = AssistantWorker(
            question=question,
            page_context=self._corpus.get("context", ""),
            history=list(self._history),
        )
        self._worker.finished.connect(self._on_answer)
        self._worker.failed.connect(self._on_error)
        self._worker.start()

        self._history.append({"role": "user", "content": question})

    def _on_answer(self, text: str):
        self._add_bubble("assistant", text)
        self._history.append({"role": "assistant", "content": text})
        self._btn_ask.setEnabled(True)
        self._btn_ask.setText("✦  Demander")

    def _on_error(self, err: str):
        self._add_bubble("assistant", f"Erreur : {err}")
        self._btn_ask.setEnabled(True)
        self._btn_ask.setText("✦  Demander")

    def _add_bubble(self, role: str, text: str):
        is_user = (role == "user")
        bubble = QWidget()
        bubble.setStyleSheet(
            f"background:{'rgba(78,205,196,0.10)' if is_user else CP['bg2']};"
            f"border-radius:8px;"
        )
        b_lay = QVBoxLayout(bubble)
        b_lay.setContentsMargins(10, 7, 10, 7)
        b_lay.setSpacing(3)

        lbl_role = QLabel("Vous" if is_user else "✦ Assistant")
        lbl_role.setStyleSheet(
            f"color:{CP['accent'] if is_user else CP['text_dim']};"
            f"font-size:9px;font-weight:700;letter-spacing:1px;background:transparent;"
        )
        b_lay.addWidget(lbl_role)

        lbl_text = QLabel(text)
        lbl_text.setWordWrap(True)
        lbl_text.setStyleSheet(
            f"color:{CP['text_primary']};font-size:11px;background:transparent;"
        )
        b_lay.addWidget(lbl_text)

        # Insérer avant le stretch final
        self._chat_lay.insertWidget(self._chat_lay.count() - 1, bubble)

        # Scroll vers le bas
        from PyQt6.QtCore import QTimer
        QTimer.singleShot(60, lambda: self._chat_scroll.verticalScrollBar().setValue(
            self._chat_scroll.verticalScrollBar().maximum()
        ))

    def _clear_chat(self):
        self._history.clear()
        while self._chat_lay.count() > 1:
            item = self._chat_lay.takeAt(0)
            if item and item.widget():
                item.widget().deleteLater()


# ── Toggle strip ───────────────────────────────────────────────────────────────

class AssistantToggleStrip(QWidget):
    """Bande verticale 20px pour ouvrir/fermer le panneau assistant."""

    def __init__(self, panel: AssistantPanel):
        super().__init__()
        self._panel  = panel
        self._open   = panel.isVisible()
        self.setFixedWidth(20)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setToolTip("Ouvrir / fermer l'assistant")
        self.setStyleSheet(
            f"background:{CP['bg2']};border-left:1px solid {CP['border']};"
        )

        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)
        lay.addStretch()

        self._arrow = QLabel(self._arrow_char())
        self._arrow.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._arrow.setFixedWidth(20)
        self._arrow.setStyleSheet(
            f"color:{CP['accent']};font-size:12px;font-weight:700;background:transparent;"
        )
        lay.addWidget(self._arrow)
        lay.addStretch()

    def _arrow_char(self) -> str:
        return "❮" if self._open else "❯"

    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            self._open = not self._open
            self._panel.setVisible(self._open)
            self._arrow.setText(self._arrow_char())

    def enterEvent(self, e):
        self._arrow.setStyleSheet(
            f"color:#ffffff;font-size:12px;font-weight:700;background:transparent;"
        )

    def leaveEvent(self, e):
        self._arrow.setStyleSheet(
            f"color:{CP['accent']};font-size:12px;font-weight:700;background:transparent;"
        )
