"""
Fenêtre principale de Studio Images.

Gauche  : génération d'image (format, modèle, prompt, références, aperçu).
Droite  : dialogue avec Claude + bouton de synthèse du prompt.
"""

import os
import time

from PyQt6.QtCore import Qt, QPoint, QUrl, pyqtSignal
from PyQt6.QtGui import QDesktopServices, QPixmap
from PyQt6.QtWidgets import (
    QAbstractSpinBox, QComboBox, QDialog, QFileDialog, QFormLayout, QHBoxLayout,
    QInputDialog, QLabel, QLineEdit, QMainWindow, QMessageBox, QProgressBar,
    QPushButton, QScrollArea, QSpinBox, QSplitter, QTextEdit, QVBoxLayout, QWidget,
)


# ── Combo dont la liste s'ouvre TOUJOURS vers le bas ─────────────────────────
class DownComboBox(QComboBox):
    """QComboBox dont le menu déroulant s'ouvre toujours SOUS le champ.

    Par défaut Qt positionne le popup pour que l'élément sélectionné chevauche le
    champ : sélectionner un élément en bas de liste fait « remonter » le popup
    (il s'ouvre vers le haut, parfois tronqué). On force ici le haut du popup à
    s'aligner sur le bas du champ — il déroule donc toujours vers le bas."""

    def showPopup(self):
        super().showPopup()
        view = self.view()
        popup = view.window() if view is not None else None
        if popup is None:
            return
        below = self.mapToGlobal(self.rect().bottomLeft())
        popup.move(QPoint(below.x(), below.y()))

import config as cfg_mod
import engines
import projects
import prompts as prompt_lib
from chat import ChatWorker, SynthPromptWorker, text_of
from imagegen import ImageWorker
from styles import CP, BUBBLE_AI, BUBBLE_USER


# ── Champ de saisie chat : Ctrl+Entrée pour envoyer ──────────────────────────
class ChatInput(QTextEdit):
    submit = pyqtSignal()

    def keyPressEvent(self, e):
        if e.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            # Maj+Entrée → nouvelle ligne ; Entrée seule → envoie
            if e.modifiers() & Qt.KeyboardModifier.ShiftModifier:
                super().keyPressEvent(e)
                return
            self.submit.emit()
            return
        super().keyPressEvent(e)


# ── Poignée d'ouverture/fermeture de la discussion Claude (à droite) ─────────
class _ChatToggleStrip(QWidget):
    """Bande verticale pour ouvrir/fermer la discussion Claude — même principe
    que le chat du Storyboard de PANDORA (poignée + flèche)."""

    def __init__(self, panel, start_open: bool = True):
        super().__init__()
        self._panel = panel
        self._open = start_open   # ouvert par défaut ; pilote la visibilité réelle
        panel.setVisible(start_open)
        self.setFixedWidth(26)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setToolTip("Ouvrir / fermer la discussion")
        self.setStyleSheet(f"background:{CP['bg1']};")

        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(6)
        lay.addStretch()
        self._lbl = QLabel("CHAT")
        self._lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._lbl.setStyleSheet(
            f"color:{CP['accent']};font-size:8px;font-weight:900;"
            f"letter-spacing:1px;background:transparent;")
        lay.addWidget(self._lbl)
        self._arrow = QLabel(self._arrow_char())
        self._arrow.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._arrow.setStyleSheet(
            f"color:{CP['accent']};font-size:18px;font-weight:700;background:transparent;")
        lay.addWidget(self._arrow)
        lay.addStretch()

    def _arrow_char(self) -> str:
        return "❮" if self._open else "❯"

    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            self._open = not self._open
            self._panel.setVisible(self._open)
            self._arrow.setText(self._arrow_char())


# ── Dialogue de configuration des clés ───────────────────────────────────────
# URLs consoles (identiques à PANDORA)
_ANT_KEYS    = "https://console.anthropic.com/settings/keys"
_ANT_BILLING = "https://console.anthropic.com/settings/billing"
_FAL_KEYS    = "https://fal.ai/dashboard/keys"
_FAL_BILLING = "https://fal.ai/dashboard/billing"


class KeysDialog(QDialog):
    def __init__(self, cfg, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Clés API & dossier de sortie")
        self.setMinimumWidth(560)
        self._cfg = cfg

        form = QFormLayout(self)
        form.setSpacing(12)

        self._anthropic = QLineEdit(cfg.get("anthropic_key", ""))
        self._anthropic.setEchoMode(QLineEdit.EchoMode.Password)
        self._anthropic.setPlaceholderText("sk-ant-…")
        form.addRow("Clé Anthropic (Claude)",
                    self._key_field(self._anthropic, _ANT_KEYS, _ANT_BILLING))

        self._fal = QLineEdit(cfg.get("fal_key", ""))
        self._fal.setEchoMode(QLineEdit.EchoMode.Password)
        self._fal.setPlaceholderText("fal.ai key — vide = mode mock")
        form.addRow("Clé fal.ai",
                    self._key_field(self._fal, _FAL_KEYS, _FAL_BILLING))

        out_row = QHBoxLayout()
        self._out = QLineEdit(cfg.get("output_dir", ""))
        browse = QPushButton("Parcourir…")
        browse.setObjectName("secondary")
        browse.clicked.connect(self._browse)
        out_row.addWidget(self._out, 1)
        out_row.addWidget(browse)
        form.addRow("Dossier de sortie", out_row)

        btns = QHBoxLayout()
        btns.addStretch(1)
        cancel = QPushButton("Annuler")
        cancel.setObjectName("secondary")
        cancel.clicked.connect(self.reject)
        ok = QPushButton("Enregistrer")
        ok.clicked.connect(self.accept)
        btns.addWidget(cancel)
        btns.addWidget(ok)
        form.addRow(btns)

    def _key_field(self, line_edit, keys_url, billing_url):
        """QLineEdit + liens cliquables (obtenir une clé / facturation)."""
        box = QVBoxLayout()
        box.setSpacing(3)
        box.setContentsMargins(0, 0, 0, 0)
        box.addWidget(line_edit)
        links = QHBoxLayout()
        links.setSpacing(14)
        links.addWidget(self._link("🔑 Obtenir une clé", keys_url))
        links.addWidget(self._link("💳 Recharger / facturation", billing_url))
        links.addStretch(1)
        box.addLayout(links)
        wrap = QWidget()
        wrap.setLayout(box)
        return wrap

    def _link(self, text, url):
        b = QPushButton(text)
        b.setCursor(Qt.CursorShape.PointingHandCursor)
        b.setStyleSheet(
            f"QPushButton{{background: transparent; border: none; padding: 0; "
            f"color: {CP['accent']}; font-size: 11px; font-weight: 600; text-align: left;}}"
            f"QPushButton:hover{{color: {CP['text_primary']}; text-decoration: underline;}}")
        b.clicked.connect(lambda: QDesktopServices.openUrl(QUrl(url)))
        return b

    def _browse(self):
        d = QFileDialog.getExistingDirectory(self, "Dossier de sortie", self._out.text())
        if d:
            self._out.setText(d)

    def values(self) -> dict:
        return {
            "anthropic_key": self._anthropic.text().strip(),
            "fal_key":       self._fal.text().strip(),
            "output_dir":    self._out.text().strip() or cfg_mod.default_output_dir(),
        }


class StudioImagesPanel(QWidget):
    """Contenu complet de Studio Images, embarquable comme widget.

    SOURCE UNIQUE : utilisé tel quel par l'app autonome (StudioWindow ci-dessous,
    `python studio_images/main.py`) ET par l'onglet « Image IA » du Studio IA de
    PANDORA (ui/tab_image.py). Faire évoluer ce panneau fait évoluer les deux.
    """

    def __init__(self):
        super().__init__()
        self.cfg = cfg_mod.load_config()
        self._history = []          # conversation Claude (schéma interne chat.py)
        self._ref_paths = []        # images de référence
        self._refs_in_chat = set()  # réfs déjà transmises à Claude
        self._pending_images = []   # images (générées/réfs) à joindre au prochain message
        self._chat_attachments = [] # images jointes UNIQUEMENT à la discussion (pas la génération)
        self._current_path = ""     # dernière image générée
        self._project_id = None     # projet actif (None = session non sauvegardée)
        self._chat_worker = None
        self._synth_worker = None
        self._img_worker = None

        root = QVBoxLayout(self)
        root.setContentsMargins(14, 12, 14, 12)
        root.setSpacing(10)

        root.addLayout(self._build_topbar())

        # Corps : génération RECENTRÉE (méthode Studio IA — largeur plafonnée +
        # centrée) + discussion Claude repliable à DROITE (poignée + flèche).
        body = QHBoxLayout()
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(0)

        left = self._build_left()
        # Largeur de colonne « document » : un MINIMUM confortable (sinon, coincée
        # entre deux stretch, la colonne s'effondrait à sa sizeHint ≈ 285 px → tout
        # paraissait riquiqui) + un MAXIMUM pour rester centrée sur écran large.
        left.setMinimumWidth(680)
        left.setMaximumWidth(860)
        left_wrap = QWidget()
        lw = QHBoxLayout(left_wrap)
        lw.setContentsMargins(0, 0, 0, 0)
        lw.setSpacing(0)
        lw.addStretch(1)
        lw.addWidget(left)
        lw.addStretch(1)
        body.addWidget(left_wrap, 1)

        self._chat_panel = self._build_right()
        self._chat_panel.setFixedWidth(440)
        self._chat_toggle = _ChatToggleStrip(self._chat_panel)
        body.addWidget(self._chat_toggle)
        body.addWidget(self._chat_panel)

        root.addLayout(body, 1)

        # Restaure les images de référence de la dernière session
        self._ref_paths = [p for p in self.cfg.get("ref_paths", []) if p and os.path.isfile(p)]
        self._refresh_refs()

    # ── Barre supérieure ─────────────────────────────────────────────────────
    def _build_topbar(self):
        bar = QHBoxLayout()
        # (titre retiré — l'onglet « Image IA » fait déjà office de titre)
        # (bouton de configuration des clés retiré — clés gérées dans Paramètres)
        bar.addStretch(1)

        # Sauvegarder (jaune) / Ouvrir (bleu) — session Image IA sauvegardée
        # physiquement dans <projet>/data/Image IA/ (comme Scénario / Storyboard).
        _yellow, _blue = "#f5c518", "#4aa3ff"
        self._btn_img_save = QPushButton("💾  Sauvegarder")
        self._btn_img_save.setToolTip("Sauvegarder cette session Image IA sous un nom")
        self._btn_img_save.setStyleSheet(
            f"QPushButton{{background:transparent;color:{_yellow};"
            f"border:1px solid {_yellow};border-radius:7px;font-size:11px;font-weight:700;padding:6px 14px;}}"
            f"QPushButton:hover{{background:rgba(245,197,24,0.12);}}")
        self._btn_img_save.clicked.connect(self._on_save_session)
        bar.addWidget(self._btn_img_save)

        self._btn_img_open = QPushButton("📂  Ouvrir")
        self._btn_img_open.setToolTip("Ouvrir une session Image IA sauvegardée")
        self._btn_img_open.setStyleSheet(
            f"QPushButton{{background:transparent;color:{_blue};"
            f"border:1px solid {_blue};border-radius:7px;font-size:11px;font-weight:700;padding:6px 14px;}}"
            f"QPushButton:hover{{background:rgba(74,163,255,0.12);}}")
        self._btn_img_open.clicked.connect(self._on_open_session)
        bar.addWidget(self._btn_img_open)

        return bar

    def _mini_label(self, text):
        lbl = QLabel(text)
        lbl.setStyleSheet(f"color: {CP['text_secondary']}; font-size: 11px; font-weight: 600;")
        return lbl

    def _dim_spin(self, value):
        """Champ de dimension (px) SANS flèches : on clique et on tape la valeur."""
        sb = QSpinBox()
        sb.setRange(64, 14000)
        sb.setValue(int(value))
        sb.setSuffix(" px")
        sb.setButtonSymbols(QAbstractSpinBox.ButtonSymbols.NoButtons)
        sb.setAlignment(Qt.AlignmentFlag.AlignCenter)
        sb.setToolTip("Clique et tape la valeur en pixels")
        sb.setStyleSheet(
            f"background:{CP['bg2']}; border:1px solid {CP['border']}; "
            f"border-radius:6px; padding:7px; color:{CP['text_primary']}; font-weight:600;")
        return sb

    # ── Sauvegarder / Ouvrir une session Image IA (dossier « Image IA ») ───────

    def _img_saves_dir(self) -> str:
        """Dossier des sessions Image IA : <projet>/data/Image IA/ si embarqué
        dans PANDORA, sinon le dossier de sortie configuré (app autonome)."""
        try:
            from core.context import get_data_root
            base = get_data_root()
        except Exception:
            base = self.cfg.get("output_dir") or cfg_mod.default_output_dir()
        d = os.path.join(base, "Image IA")
        os.makedirs(d, exist_ok=True)
        return d

    def _session_dict(self) -> dict:
        return {
            "settings": {
                "image_model": self._model.currentData(),
                "format":      self._format.currentData(),
                "custom_w":    self._cw.value(),
                "custom_h":    self._ch.value(),
                "prompt":      self._prompt.toPlainText(),
            },
            "history":    self._history,
            "last_image": self._current_path,
            "ref_paths":  self._ref_paths,
        }

    def _on_save_session(self):
        import json
        name, ok = QInputDialog.getText(self, "Sauvegarder", "Nom de la session :")
        if not (ok and name.strip()):
            return
        safe = "".join(c for c in name.strip() if c.isalnum() or c in " -_").strip() or "image"
        try:
            with open(os.path.join(self._img_saves_dir(), safe + ".json"), "w",
                      encoding="utf-8") as f:
                json.dump(self._session_dict(), f, ensure_ascii=False, indent=2)
            self._status.setText(f"Session « {name.strip()} » sauvegardée ✓")
        except Exception as e:
            QMessageBox.critical(self, "Erreur", f"Échec de la sauvegarde : {e}")

    def _on_open_session(self):
        import json
        d = self._img_saves_dir()
        try:
            names = sorted(f[:-5] for f in os.listdir(d) if f.endswith(".json"))
        except Exception:
            names = []
        if not names:
            QMessageBox.information(self, "Ouvrir", "Aucune session Image IA sauvegardée.")
            return
        name, ok = QInputDialog.getItem(self, "Ouvrir une session", "Session :",
                                        names, 0, False)
        if not (ok and name):
            return
        try:
            with open(os.path.join(d, name + ".json"), encoding="utf-8") as f:
                data = json.load(f)
        except Exception as e:
            QMessageBox.critical(self, "Erreur", f"Échec de l'ouverture : {e}")
            return
        self._load_session_dict(data)
        self._status.setText(f"Session « {name} » ouverte ✓")

    def _load_session_dict(self, data: dict):
        s = data.get("settings", {})
        if s.get("image_model"):
            self._select_data(self._model, s["image_model"])
        if s.get("format"):
            self._select_data(self._format, s["format"])   # peut pré-remplir L/H…
        if s.get("custom_w"):
            self._cw.setValue(int(s["custom_w"]))          # …puis on restaure la taille saisie
        if s.get("custom_h"):
            self._ch.setValue(int(s["custom_h"]))
        self._prompt.setPlainText(s.get("prompt", ""))

        self._history = data.get("history", [])
        self._refs_in_chat = set()
        for m in self._history:
            c = m.get("content")
            if isinstance(c, list):
                for it in c:
                    if it.get("t") == "image":
                        self._refs_in_chat.add(it.get("path"))
        self._rebuild_chat_view()

        self._pending_images = []
        self._chat_attachments = []
        self._refresh_attach()
        self._ref_paths = [p for p in data.get("ref_paths", []) if p and os.path.isfile(p)]
        self._refresh_refs()
        self._persist_refs()
        last = data.get("last_image", "")
        if last and os.path.isfile(last):
            self._current_path = last
            self._show_preview(last)
            self._discuss_btn.setEnabled(True)
        else:
            self._current_path = ""
            self._clear_preview()
            self._discuss_btn.setEnabled(False)

    # ── Panneau gauche : génération ──────────────────────────────────────────
    def _build_left(self):
        panel = QWidget()
        lay = QVBoxLayout(panel)
        lay.setContentsMargins(0, 0, 6, 0)
        lay.setSpacing(10)

        # Moteur de génération (catalogue engines.py)
        self._model = DownComboBox()
        for key, spec in engines.ENGINES.items():
            self._model.addItem(spec["label"], key)
        self._select_data(self._model, self.cfg.get("image_model", "nb_pro"))
        self._model.currentIndexChanged.connect(self._on_engine_changed)
        lay.addWidget(self._section_label("MOTEUR DE GÉNÉRATION"))
        lay.addWidget(self._model)

        # Format (templates) + nombre d'images. Choisir un template pré-remplit
        # Largeur/Hauteur ci-dessous (ils restent la source de vérité de la taille).
        row = QHBoxLayout()
        self._format = DownComboBox()
        for key, (label, _sz) in cfg_mod.FORMATS.items():
            self._format.addItem(label, key)
        self._select_data(self._format, self.cfg.get("format", "thumbnail"))
        # NB : on connecte APRÈS _select_data → le format initial ne réécrit pas
        # les Largeur/Hauteur restaurés de la config.
        self._format.currentIndexChanged.connect(self._on_format_changed)

        self._count = QSpinBox()
        self._count.setRange(1, 4)
        self._count.setValue(int(self.cfg.get("count", 1)))
        self._count.setPrefix("×")
        self._count.setToolTip("Nombre d'images à générer (variations)")
        self._count.setStyleSheet(
            f"background:{CP['bg2']}; border:1px solid {CP['border']}; "
            f"border-radius:6px; padding:7px; color:{CP['text_primary']}; font-weight:600;")

        row.addWidget(self._format, 1)
        row.addWidget(self._count)
        lay.addLayout(row)

        # Largeur × Hauteur — TOUJOURS visibles, saisie directe au clavier (pas de
        # flèches). Un template les pré-remplit ; on peut toujours taper une valeur.
        self._custom_row = QWidget()
        crow = QHBoxLayout(self._custom_row)
        crow.setContentsMargins(0, 0, 0, 0)
        crow.setSpacing(8)
        self._cw = self._dim_spin(int(self.cfg.get("custom_w", 1024)))
        self._ch = self._dim_spin(int(self.cfg.get("custom_h", 1024)))
        crow.addWidget(self._mini_label("Largeur"))
        crow.addWidget(self._cw, 1)
        crow.addWidget(self._mini_label("Hauteur"))
        crow.addWidget(self._ch, 1)
        lay.addWidget(self._custom_row)

        # Prompt — en-tête avec bibliothèque de prompts
        prompt_head = QHBoxLayout()
        prompt_head.addWidget(self._section_label("PROMPT"))
        prompt_head.addStretch(1)
        self._prompt_lib = DownComboBox()
        self._prompt_lib.setMinimumWidth(150)
        self._prompt_lib.setToolTip("Prompts enregistrés — sélectionne pour charger")
        self._prompt_lib.activated.connect(self._on_prompt_selected)
        prompt_head.addWidget(self._prompt_lib)
        save_p = QPushButton("💾")
        save_p.setObjectName("secondary")
        save_p.setFixedWidth(36)
        save_p.setToolTip("Enregistrer le prompt actuel")
        save_p.clicked.connect(self._save_prompt_clicked)
        prompt_head.addWidget(save_p)
        del_p = QPushButton("🗑")
        del_p.setObjectName("secondary")
        del_p.setFixedWidth(36)
        del_p.setToolTip("Supprimer le prompt sélectionné")
        del_p.clicked.connect(self._delete_prompt_clicked)
        prompt_head.addWidget(del_p)
        lay.addLayout(prompt_head)

        self._prompt = QTextEdit()
        self._prompt.setPlaceholderText(
            "Le prompt apparaît ici depuis la discussion avec Claude — "
            "ou écris/édite-le directement.")
        self._prompt.setMinimumHeight(110)
        self._prompt.setMaximumHeight(160)
        lay.addWidget(self._prompt)
        self._refresh_prompt_lib()

        # Références
        lay.addWidget(self._section_label("RÉFÉRENCES"))

        # Indication du support des références par le moteur sélectionné
        self._refs_hint = QLabel("")
        self._refs_hint.setWordWrap(True)
        self._refs_hint.setStyleSheet(f"color: {CP['text_secondary']}; font-size: 11px;")
        lay.addWidget(self._refs_hint)

        self._refs_row = QHBoxLayout()
        self._refs_row.setSpacing(6)
        self._refs_row.addStretch(1)
        refs_wrap = QWidget()
        refs_wrap.setLayout(self._refs_row)
        refs_wrap.setFixedHeight(72)
        lay.addWidget(refs_wrap)

        self._on_engine_changed()  # initialise le hint
        self._refresh_refs()       # construit les slots + tuile « + »

        # Génération
        self._gen_btn = QPushButton("⚡  GÉNÉRER L'IMAGE")
        self._gen_btn.clicked.connect(self._generate)
        lay.addWidget(self._gen_btn)

        # Annuler — visible uniquement pendant un travail en cours
        self._cancel_btn = QPushButton("✕  Annuler")
        self._cancel_btn.setObjectName("secondary")
        self._cancel_btn.setStyleSheet(
            f"QPushButton{{background: transparent; color: {CP.get('red', '#ff4f6a')}; "
            f"border: 1px solid rgba(255,79,106,0.40); border-radius: 8px; "
            f"font-weight: 700; padding: 6px;}}"
            f"QPushButton:hover{{background: rgba(255,79,106,0.10); "
            f"border-color: rgba(255,79,106,0.70);}}")
        self._cancel_btn.clicked.connect(self._cancel_work)
        self._cancel_btn.setVisible(False)
        lay.addWidget(self._cancel_btn)

        self._progress = QProgressBar()
        self._progress.setRange(0, 100)
        self._progress.setValue(0)
        self._progress.setVisible(False)   # visible seulement pendant le chargement
        lay.addWidget(self._progress)
        self._status = QLabel("")
        self._status.setStyleSheet(f"color: {CP['text_secondary']}; font-size: 11px;")
        lay.addWidget(self._status)

        # Aperçu : COMPACT tant qu'aucune image (petit cadre placeholder), puis
        # dimensionné EXACTEMENT à l'image générée (mise à l'échelle pour tenir
        # dans la zone) → pas de bandes noires autour. Centré ; le ressort ajouté
        # en bas de colonne absorbe l'espace libre (contenu calé en haut).
        self._preview = QLabel(self._PREVIEW_PLACEHOLDER)
        self._preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._preview.setStyleSheet(
            f"QLabel{{background: {CP['bg2']}; border: 1px solid {CP['border_bright']}; "
            f"border-radius: 12px; color: {CP['text_secondary']}; font-size: 14px;}}")
        self._preview.setFixedSize(*self._PREVIEW_EMPTY_SIZE)
        lay.addWidget(self._preview, 0, Qt.AlignmentFlag.AlignHCenter)

        # Actions image
        actions = QHBoxLayout()
        self._discuss_btn = QPushButton("💬  Analyser avec Claude")
        self._discuss_btn.setObjectName("secondary")
        self._discuss_btn.setToolTip("Envoie l'image générée à Claude pour qu'il l'analyse")
        self._discuss_btn.clicked.connect(self._send_result_to_claude)
        self._discuss_btn.setEnabled(False)
        self._open_dir_btn = QPushButton("📂  Voir le fichier")
        self._open_dir_btn.setObjectName("secondary")
        self._open_dir_btn.setToolTip("Ouvre le dossier avec l'image sélectionnée")
        self._open_dir_btn.clicked.connect(self._open_dir)
        actions.addWidget(self._discuss_btn, 1)
        actions.addWidget(self._open_dir_btn, 1)
        lay.addLayout(actions)

        # Historique de session
        self._hist_row = QHBoxLayout()
        self._hist_row.setSpacing(6)
        self._hist_row.addStretch(1)
        hist_wrap = QWidget()
        hist_wrap.setLayout(self._hist_row)
        hist_scroll = QScrollArea()
        hist_scroll.setWidgetResizable(True)
        hist_scroll.setWidget(hist_wrap)
        hist_scroll.setFixedHeight(74)
        hist_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        hist_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        lay.addWidget(hist_scroll)

        # Ressort final : absorbe l'espace libre en bas → tout le contenu reste
        # calé en haut, l'aperçu garde sa taille réelle (pas de trous au milieu).
        lay.addStretch(1)

        return panel

    # ── Panneau droit : chat ─────────────────────────────────────────────────
    def _build_right(self):
        panel = QWidget()
        lay = QVBoxLayout(panel)
        lay.setContentsMargins(6, 0, 0, 0)
        lay.setSpacing(8)

        lay.addWidget(self._section_label("DISCUSSION AVEC CLAUDE"))

        self._chat_scroll = QScrollArea()
        self._chat_scroll.setWidgetResizable(True)
        chat_wrap = QWidget()
        self._chat_layout = QVBoxLayout(chat_wrap)
        self._chat_layout.setContentsMargins(2, 2, 8, 2)
        self._chat_layout.setSpacing(8)
        self._chat_layout.addStretch(1)
        self._chat_scroll.setWidget(chat_wrap)
        lay.addWidget(self._chat_scroll, 1)

        self._greeting = (
            "Salut ! Décris-moi le visuel à créer pour PANDORA — logo, vignette, "
            "bannière, affiche… (sujet, usage, texte, ambiance). Tu peux aussi me "
            "joindre une image de référence. Je t'aide à le concevoir, puis je "
            "génère le prompt.")
        self._add_bubble("assistant", self._greeting)

        # Indicateur de chargement DU CHAT (« Claude réfléchit ») — distinct de la
        # barre de génération à gauche, qui ne sert qu'au prompt et à l'image.
        self._chat_busy = QWidget()
        _cb = QHBoxLayout(self._chat_busy)
        _cb.setContentsMargins(2, 0, 8, 0)
        _cb.setSpacing(8)
        self._chat_status = QLabel("")
        self._chat_status.setStyleSheet(
            f"color:{CP['accent']};font-size:11px;background:transparent;")
        _cb.addWidget(self._chat_status)
        self._chat_progress = QProgressBar()
        self._chat_progress.setRange(0, 0)        # indéterminé (animé)
        self._chat_progress.setTextVisible(False)
        self._chat_progress.setFixedHeight(6)
        _cb.addWidget(self._chat_progress, 1)
        self._chat_busy.setVisible(False)
        lay.addWidget(self._chat_busy)

        # Pièces jointes de discussion (n'entrent PAS dans la génération)
        attach_head = QHBoxLayout()
        lbl = QLabel("📎 Joindre à la discussion (pas à la génération)")
        lbl.setStyleSheet(f"color: {CP['text_dim']}; font-size: 10px; font-weight: 600;")
        attach_head.addWidget(lbl)
        attach_head.addStretch(1)
        lay.addLayout(attach_head)

        self._attach_row = QHBoxLayout()
        self._attach_row.setSpacing(6)
        self._attach_row.addStretch(1)
        attach_wrap = QWidget()
        attach_wrap.setLayout(self._attach_row)
        attach_wrap.setFixedHeight(62)
        lay.addWidget(attach_wrap)
        self._refresh_attach()

        self._input = ChatInput()
        self._input.setPlaceholderText("Ton message…  (Entrée pour envoyer · Maj+Entrée = nouvelle ligne)")
        self._input.setFixedHeight(84)
        self._input.submit.connect(self._send_chat)
        lay.addWidget(self._input)

        synth = QPushButton("✨ Générer le prompt depuis la discussion")
        synth.setObjectName("secondary")
        synth.clicked.connect(self._synth_prompt)
        lay.addWidget(synth)

        return panel

    # ── Helpers UI ───────────────────────────────────────────────────────────
    def _section_label(self, text):
        lbl = QLabel(text)
        lbl.setStyleSheet(
            f"color: {CP['text_dim']}; font-size: 10px; font-weight: 700; letter-spacing: 1.5px;")
        return lbl

    def _select_data(self, combo, data):
        idx = combo.findData(data)
        if idx >= 0:
            combo.setCurrentIndex(idx)

    def _add_bubble(self, role, text, images=None):
        box = QVBoxLayout()
        box.setSpacing(4)
        box.setContentsMargins(0, 0, 0, 0)

        if text:
            bubble = QLabel(text)
            bubble.setWordWrap(True)
            bubble.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            bubble.setStyleSheet(BUBBLE_USER if role == "user" else BUBBLE_AI)
            box.addWidget(bubble)

        # Vignettes des images jointes au message
        if images:
            thumbs = QHBoxLayout()
            thumbs.setSpacing(4)
            if role == "user":
                thumbs.addStretch(1)
            for p in images:
                t = QLabel()
                pm = self._load_pixmap(p)
                if pm is not None and not pm.isNull():
                    t.setPixmap(pm.scaled(54, 54, Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                                          Qt.TransformationMode.SmoothTransformation))
                else:
                    t.setText("?")
                    t.setAlignment(Qt.AlignmentFlag.AlignCenter)
                t.setFixedSize(54, 54)
                t.setStyleSheet(f"border: 1px solid {CP['accent_dim']}; border-radius: 5px;")
                t.setToolTip(os.path.basename(p))
                thumbs.addWidget(t)
            if role != "user":
                thumbs.addStretch(1)
            box.addLayout(thumbs)

        inner = QWidget()
        inner.setLayout(box)
        inner.setMaximumWidth(440)

        wrap = QHBoxLayout()
        if role == "user":
            wrap.addStretch(1)
            wrap.addWidget(inner)
        else:
            wrap.addWidget(inner)
            wrap.addStretch(1)
        container = QWidget()
        container.setLayout(wrap)
        self._chat_layout.insertWidget(self._chat_layout.count() - 1, container)

        # auto-scroll
        bar = self._chat_scroll.verticalScrollBar()
        bar.setMaximum(bar.maximum() + 400)
        bar.setValue(bar.maximum())

    # ── Clés API ─────────────────────────────────────────────────────────────
    def _open_keys(self):
        dlg = KeysDialog(self.cfg, self)
        if dlg.exec():
            self.cfg.update(dlg.values())
            self._persist_cfg()

    def _persist_cfg(self):
        self.cfg["image_model"] = self._model.currentData()
        self.cfg["format"] = self._format.currentData()
        self.cfg["custom_w"] = self._cw.value()
        self.cfg["custom_h"] = self._ch.value()
        self.cfg["count"] = self._count.value()
        cfg_mod.save_config(self.cfg)

    def _on_format_changed(self):
        """Sélectionner un template qui a des dimensions les reporte automatiquement
        dans Largeur/Hauteur. « Personnalisé… » ne touche pas aux valeurs saisies."""
        fmt = self._format.currentData()
        if fmt and fmt != "free" and fmt in cfg_mod.FORMATS:
            w, h = cfg_mod.FORMATS[fmt][1]
            self._cw.setValue(int(w))
            self._ch.setValue(int(h))

    def _on_engine_changed(self):
        key = self._model.currentData()
        # Support des références par ce moteur
        if hasattr(self, "_refs_hint"):
            sup = engines.ref_support(key)
            self._refs_hint.setText(sup.get("hint", ""))
            supports = sup.get("max", 0) > 0
            color = CP["text_secondary"] if supports else CP["orange"]
            self._refs_hint.setStyleSheet(f"color: {color}; font-size: 11px;")
            self._refresh_refs()  # affiche/masque la tuile « + » selon le moteur

    # ── Tuiles d'image réutilisables (style PANDORA) ─────────────────────────
    def _thumb_tile(self, path, on_remove):
        t = QLabel()
        pm = self._load_pixmap(path)
        if pm is not None and not pm.isNull():
            t.setPixmap(pm.scaled(56, 56, Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                                  Qt.TransformationMode.SmoothTransformation))
        else:
            t.setText("?")
            t.setAlignment(Qt.AlignmentFlag.AlignCenter)
        t.setFixedSize(56, 56)
        t.setStyleSheet(f"border: 1px solid {CP['border_bright']}; border-radius: 8px;")
        t.setToolTip("Cliquer pour retirer\n" + os.path.basename(path))
        t.setCursor(Qt.CursorShape.PointingHandCursor)
        t.mousePressEvent = lambda e, p=path: on_remove(p)
        return t

    def _add_tile(self, on_add, tooltip=""):
        t = QLabel("＋")
        t.setAlignment(Qt.AlignmentFlag.AlignCenter)
        t.setFixedSize(56, 56)
        t.setStyleSheet(
            f"QLabel{{border: 1px dashed {CP['border_bright']}; border-radius: 8px; "
            f"color: {CP['text_secondary']}; font-size: 24px; background: {CP['bg2']};}}")
        t.setToolTip(tooltip or "Ajouter une image")
        t.setCursor(Qt.CursorShape.PointingHandCursor)
        t.mousePressEvent = lambda e: on_add()
        return t

    def _target_size(self):
        # Largeur/Hauteur sont la source de vérité (toujours visibles ; un template
        # les pré-remplit). La taille de sortie exacte = ces deux champs.
        return (self._cw.value(), self._ch.value())

    # ── Projets ──────────────────────────────────────────────────────────────
    def _refresh_projects(self):
        self._project_combo.blockSignals(True)
        self._project_combo.clear()
        self._project_combo.addItem("(session non sauvegardée)", None)
        for p in projects.list_projects():
            self._project_combo.addItem(p["name"], p["id"])
        # Resélectionne le projet actif
        idx = self._project_combo.findData(self._project_id) if self._project_id else 0
        self._project_combo.setCurrentIndex(max(0, idx))
        self._project_combo.blockSignals(False)

    def _on_project_change(self, _index):
        pid = self._project_combo.currentData()
        if pid is None or pid == self._project_id:
            return
        try:
            self._load_project_into_ui(pid)
        except Exception as e:
            QMessageBox.critical(self, "Projet", f"Impossible d'ouvrir : {e}")
            self._refresh_projects()

    def _new_project(self):
        name, ok = QInputDialog.getText(self, "Nouveau projet", "Nom du projet :")
        if not ok or not name.strip():
            return
        pid = projects.create_project(name.strip(), int(time.time()))
        self._project_id = pid
        self._reset_session()
        self._save_project_data()      # enregistre les réglages courants
        self._refresh_projects()
        self._status.setText(f"Projet « {name.strip()} » créé.")

    def _save_project_clicked(self):
        if not self._project_id:
            # Pas de projet actif → en créer un
            self._new_project()
            return
        self._save_project_data()
        self._status.setText("Projet enregistré ✓")

    def _autosave(self):
        if self._project_id:
            try:
                self._save_project_data()
            except Exception:
                pass

    def _save_project_data(self):
        if not self._project_id:
            return
        try:
            data = projects.load_project(self._project_id)
        except Exception:
            data = {"name": self._project_id, "created": int(time.time())}
        data["updated"] = int(time.time())
        data["settings"] = {
            "image_model": self._model.currentData(),
            "format":      self._format.currentData(),
            "custom_w":    self._cw.value(),
            "custom_h":    self._ch.value(),
            "prompt":      self._prompt.toPlainText(),
        }
        data["history"] = self._history
        data["last_image"] = self._current_path
        data["ref_paths"] = self._ref_paths
        projects.save_project(self._project_id, data)

    def _load_project_into_ui(self, pid):
        data = projects.load_project(pid)
        self._project_id = pid

        s = data.get("settings", {})
        if s.get("image_model"):
            self._select_data(self._model, s["image_model"])
        if s.get("format"):
            self._select_data(self._format, s["format"])   # peut pré-remplir L/H…
        if s.get("custom_w"):
            self._cw.setValue(int(s["custom_w"]))          # …puis on restaure la taille saisie
        if s.get("custom_h"):
            self._ch.setValue(int(s["custom_h"]))
        self._prompt.setPlainText(s.get("prompt", ""))

        # Fil de discussion
        self._history = data.get("history", [])
        self._refs_in_chat = set()
        for m in self._history:
            c = m.get("content")
            if isinstance(c, list):
                for it in c:
                    if it.get("t") == "image":
                        self._refs_in_chat.add(it.get("path"))
        self._rebuild_chat_view()

        # Aperçu
        self._pending_images = []
        self._chat_attachments = []
        self._refresh_attach()
        # Images de référence (génération) — restaurées depuis le projet
        self._ref_paths = [p for p in data.get("ref_paths", []) if p and os.path.isfile(p)]
        self._refresh_refs()
        self._persist_refs()
        last = data.get("last_image", "")
        if last and os.path.isfile(last):
            self._current_path = last
            self._show_preview(last)
            self._discuss_btn.setEnabled(True)
        else:
            self._current_path = ""
            self._clear_preview()
            self._discuss_btn.setEnabled(False)
        self._refresh_projects()
        self._status.setText(f"Projet « {data.get('name', pid)} » ouvert.")

    def _reset_session(self):
        self._history = []
        self._refs_in_chat = set()
        self._pending_images = []
        self._chat_attachments = []
        self._ref_paths = []
        self._current_path = ""
        self._refresh_attach()
        self._refresh_refs()
        self._persist_refs()
        self._rebuild_chat_view()
        self._clear_preview()
        self._discuss_btn.setEnabled(False)
        # vide l'historique de miniatures
        while self._hist_row.count() > 1:
            item = self._hist_row.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

    def _rebuild_chat_view(self):
        # Retire toutes les bulles (garde le stretch final)
        while self._chat_layout.count() > 1:
            item = self._chat_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self._add_bubble("assistant", self._greeting)
        for m in self._history:
            c = m["content"]
            imgs = ([it["path"] for it in c if it.get("t") == "image" and it.get("path")]
                    if isinstance(c, list) else [])
            self._add_bubble(m["role"], text_of(c), images=imgs)

    # ── Chat ─────────────────────────────────────────────────────────────────
    def _send_chat(self):
        self._do_send(self._input.toPlainText().strip(), from_input=True)

    def _send_result_to_claude(self):
        """Joint l'image générée et demande à Claude de l'analyser."""
        if not self._current_path or not os.path.isfile(self._current_path):
            return
        if self._current_path not in self._pending_images:
            self._pending_images.append(self._current_path)
        self._do_send(
            "Voici l'image générée. Analyse-la : composition, lisibilité du texte, "
            "safe zone, cohérence avec le branding PANDORA, et dis-moi précisément "
            "quoi ajuster dans le prompt.")

    def _add_chat_attachment(self):
        files, _ = QFileDialog.getOpenFileNames(
            self, "Joindre à la discussion", "",
            "Images (*.png *.jpg *.jpeg *.webp *.bmp)")
        for f in files:
            if f and f not in self._chat_attachments:
                self._chat_attachments.append(f)
        self._refresh_attach()

    def _remove_chat_attachment(self, path):
        if path in self._chat_attachments:
            self._chat_attachments.remove(path)
            self._refresh_attach()

    def _refresh_attach(self):
        if not hasattr(self, "_attach_row"):
            return
        while self._attach_row.count() > 1:  # garde le stretch final
            item = self._attach_row.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        for p in self._chat_attachments:
            tile = self._thumb_tile(p, self._remove_chat_attachment)
            self._attach_row.insertWidget(self._attach_row.count() - 1, tile)
        # Tuile « + » (jusqu'à 6 pièces jointes de discussion)
        if len(self._chat_attachments) < 6:
            add = self._add_tile(self._add_chat_attachment,
                                 "Joindre une image à la discussion")
            self._attach_row.insertWidget(self._attach_row.count() - 1, add)

    def _do_send(self, text, from_input=False):
        # Images à joindre : générées en attente + réfs pas encore envoyées + pièces jointes de discussion
        new_refs = [p for p in self._ref_paths if p not in self._refs_in_chat]
        imgs = list(self._pending_images) + new_refs + list(self._chat_attachments)
        # dédoublonne en conservant l'ordre
        seen = set()
        imgs = [p for p in imgs if not (p in seen or seen.add(p))]
        if not text and not imgs:
            return
        if not text and imgs:
            text = "Analyse cette/ces image(s)."
        if from_input:
            self._input.clear()

        if imgs:
            content = [{"t": "image", "path": p} for p in imgs]
            content.append({"t": "text", "text": text})
            for p in new_refs:
                self._refs_in_chat.add(p)
        else:
            content = text
        self._pending_images = []
        self._chat_attachments = []
        self._refresh_attach()

        self._add_bubble("user", text, images=imgs)
        self._history.append({"role": "user", "content": content})

        self._set_chat_busy(True, "Claude réfléchit…")
        self._chat_worker = ChatWorker(self.cfg.get("anthropic_key", ""), list(self._history))
        self._chat_worker.finished.connect(self._on_chat_done)
        self._chat_worker.failed.connect(self._on_chat_error)
        self._chat_worker.notice.connect(lambda m: self._set_chat_busy(True, m))
        self._chat_worker.start()

    def _on_chat_done(self, reply):
        self._set_chat_busy(False)
        self._history.append({"role": "assistant", "content": reply})
        self._add_bubble("assistant", reply)
        self._autosave()

    def _on_chat_error(self, msg):
        # Retire le dernier tour utilisateur pour garder l'historique cohérent
        if self._history and self._history[-1]["role"] == "user":
            self._history.pop()
        self._set_chat_busy(False)
        QMessageBox.critical(self, "Erreur", msg)

    def _synth_prompt(self):
        if not self._history:
            QMessageBox.information(self, "Studio Images",
                                    "Discute d'abord avec Claude pour décrire ton idée.")
            return
        self._set_busy(True, "Synthèse du prompt…")
        fmt_label = self._format.currentText()
        self._synth_worker = SynthPromptWorker(
            self.cfg.get("anthropic_key", ""), list(self._history), fmt_label)
        self._synth_worker.finished.connect(self._on_synth_done)
        self._synth_worker.failed.connect(self._on_worker_error)
        self._synth_worker.start()

    def _on_synth_done(self, prompt):
        self._set_busy(False, "Prompt prêt — vérifie-le puis Génère.")
        self._prompt.setPlainText(prompt)

    # ── Bibliothèque de prompts ──────────────────────────────────────────────
    def _refresh_prompt_lib(self):
        self._prompt_lib.blockSignals(True)
        self._prompt_lib.clear()
        self._prompt_lib.addItem("— Prompts enregistrés —", None)
        for it in prompt_lib.load_prompts():
            self._prompt_lib.addItem(it.get("name", "?"), it.get("prompt", ""))
        self._prompt_lib.setCurrentIndex(0)
        self._prompt_lib.blockSignals(False)

    def _on_prompt_selected(self, index):
        data = self._prompt_lib.itemData(index)
        if data:
            self._prompt.setPlainText(data)
            self._status.setText(f"Prompt « {self._prompt_lib.currentText()} » chargé.")

    def _save_prompt_clicked(self):
        text = self._prompt.toPlainText().strip()
        if not text:
            QMessageBox.information(self, "Studio Images", "Le champ Prompt est vide.")
            return
        name, ok = QInputDialog.getText(self, "Enregistrer le prompt", "Nom du prompt :")
        if not ok or not name.strip():
            return
        prompt_lib.save_prompt(name.strip(), text)
        self._refresh_prompt_lib()
        idx = self._prompt_lib.findText(name.strip())
        if idx >= 0:
            self._prompt_lib.setCurrentIndex(idx)
        self._status.setText(f"Prompt « {name.strip()} » enregistré ✓")

    def _delete_prompt_clicked(self):
        name = self._prompt_lib.currentText()
        if self._prompt_lib.currentData() is None:
            QMessageBox.information(self, "Studio Images",
                                    "Sélectionne d'abord un prompt enregistré à supprimer.")
            return
        if QMessageBox.question(self, "Supprimer", f"Supprimer le prompt « {name} » ?") \
                == QMessageBox.StandardButton.Yes:
            prompt_lib.delete_prompt(name)
            self._refresh_prompt_lib()
            self._status.setText(f"Prompt « {name} » supprimé.")

    # ── Références ───────────────────────────────────────────────────────────
    def _store_ref(self, src):
        """Copie l'image dans studio_images/refs/ (nom = hash du contenu) et
        retourne le chemin de la copie. Dédoublonne : même image → même copie."""
        import hashlib
        import shutil
        try:
            with open(src, "rb") as f:
                h = hashlib.md5(f.read()).hexdigest()[:16]
            ext = os.path.splitext(src)[1].lower() or ".png"
            dest = os.path.join(cfg_mod.refs_dir(), h + ext)
            if not os.path.isfile(dest):
                shutil.copyfile(src, dest)
            return dest
        except Exception:
            return src  # repli : on garde le chemin d'origine

    def _persist_refs(self):
        """Mémorise les références courantes dans la config (revient au prochain lancement)."""
        self.cfg["ref_paths"] = self._ref_paths
        cfg_mod.save_config(self.cfg)

    def _add_ref(self):
        cap = engines.ref_support(self._model.currentData()).get("max", 0)
        if cap <= 0 or len(self._ref_paths) >= cap:
            return
        files, _ = QFileDialog.getOpenFileNames(
            self, "Images de référence", "",
            "Images (*.png *.jpg *.jpeg *.webp *.bmp)")
        for f in files:
            if not f or len(self._ref_paths) >= cap:
                continue
            dest = self._store_ref(f)  # copie persistante
            if dest not in self._ref_paths:
                self._ref_paths.append(dest)
        self._refresh_refs()
        self._persist_refs()

    def _refresh_refs(self):
        if not hasattr(self, "_refs_row"):
            return
        while self._refs_row.count() > 1:  # garde le stretch final
            item = self._refs_row.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        for path in self._ref_paths:
            tile = self._thumb_tile(path, self._remove_ref)
            self._refs_row.insertWidget(self._refs_row.count() - 1, tile)
        # Tuile « + » si le moteur accepte encore des références
        cap = engines.ref_support(self._model.currentData()).get("max", 0)
        if 0 < cap and len(self._ref_paths) < cap:
            add = self._add_tile(self._add_ref, "Ajouter une image de référence")
            self._refs_row.insertWidget(self._refs_row.count() - 1, add)

    def _remove_ref(self, path):
        if path in self._ref_paths:
            self._ref_paths.remove(path)
            self._refresh_refs()
            self._persist_refs()

    # ── Génération image ─────────────────────────────────────────────────────
    def _generate(self):
        prompt = self._prompt.toPlainText().strip()
        if not prompt:
            QMessageBox.information(
                self, "Studio Images",
                "Le prompt est vide. Écris-le ou clique « ✨ Générer le prompt ».")
            return
        self._persist_cfg()
        target = self._target_size()
        out_dir = projects.project_dir(self._project_id) if self._project_id \
            else self.cfg.get("output_dir", "")

        self._set_busy(True, "Génération…")
        self._gen_btn.setEnabled(False)
        self._img_worker = ImageWorker(
            fal_key=self.cfg.get("fal_key", ""),
            engine_key=self._model.currentData(),
            prompt=prompt,
            resolution=self._res_value(),
            ref_paths=self._ref_paths,
            out_dir=out_dir,
            target_size=target,
            count=self._count.value(),
        )
        self._img_worker.progress.connect(self._on_img_progress)
        self._img_worker.finished.connect(self._on_img_done)
        self._img_worker.failed.connect(self._on_img_error)
        self._img_worker.start()

    def _on_img_progress(self, pct, msg):
        self._progress.setValue(pct)
        self._status.setText(msg)

    def _on_img_done(self, paths):
        self._gen_btn.setEnabled(True)
        self._progress.setValue(100)
        if not paths:
            self._set_busy(False, "Aucune image générée.")
            return
        n = len(paths)
        msg = ("Image prête — « 💬 Analyser avec Claude » pour en discuter."
               if n == 1 else
               f"{n} images — clique une miniature pour l'agrandir, puis « 💬 Analyser ».")
        self._set_busy(False, msg)
        for p in paths:
            self._add_history(p)
        # Affiche la première ; _show_preview met aussi à jour current + file en attente
        self._show_preview(paths[0])
        self._discuss_btn.setEnabled(True)
        self._autosave()

    def _on_img_error(self, msg):
        self._set_busy(False, "")
        self._gen_btn.setEnabled(True)
        self._progress.setValue(0)
        QMessageBox.critical(self, "Erreur de génération", msg)

    _PREVIEW_PLACEHOLDER = "🖼\n\nEn attente d'aperçu"
    _PREVIEW_EMPTY_SIZE  = (340, 150)   # petit cadre tant qu'aucune image
    _PREVIEW_MAX_W       = 660          # plafond d'affichage de l'image générée
    _PREVIEW_MAX_H       = 600

    def _clear_preview(self):
        """Remet l'aperçu sur son état vide : petit cadre + placeholder centré."""
        self._preview.setPixmap(QPixmap())
        self._preview.setText(self._PREVIEW_PLACEHOLDER)
        self._preview.setFixedSize(*self._PREVIEW_EMPTY_SIZE)

    def _show_preview(self, path):
        # L'image affichée devient celle jointe au prochain message Claude
        self._current_path = path
        self._pending_images = [path]
        self._discuss_btn.setEnabled(True)
        pm = self._load_pixmap(path)
        if pm is None or pm.isNull():
            self._preview.setPixmap(QPixmap())
            self._preview.setText("🅥  Logo vectoriel SVG généré\n\nOuvre-le via 📂 Voir le fichier")
            self._preview.setFixedSize(*self._PREVIEW_EMPTY_SIZE)
            return
        # Affiche à la taille réelle de l'image, plafonnée à la zone max (on ne
        # sur-agrandit jamais une petite image). La zone épouse EXACTEMENT l'image
        # affichée → aucune bande noire autour.
        bound_w = min(pm.width(), self._PREVIEW_MAX_W)
        bound_h = min(pm.height(), self._PREVIEW_MAX_H)
        disp = pm.scaled(bound_w, bound_h,
                         Qt.AspectRatioMode.KeepAspectRatio,
                         Qt.TransformationMode.SmoothTransformation)
        self._preview.setText("")
        self._preview.setPixmap(disp)
        self._preview.setFixedSize(disp.size())

    def _load_pixmap(self, path):
        """Charge un QPixmap (rasterise les SVG via QtSvg si disponible)."""
        if path.lower().endswith(".svg"):
            try:
                from PyQt6.QtSvg import QSvgRenderer
                from PyQt6.QtGui import QImage, QPainter
                renderer = QSvgRenderer(path)
                if not renderer.isValid():
                    return None
                img = QImage(800, 800, QImage.Format.Format_ARGB32)
                img.fill(Qt.GlobalColor.transparent)
                p = QPainter(img)
                renderer.render(p)
                p.end()
                return QPixmap.fromImage(img)
            except Exception:
                return None
        return QPixmap(path)

    def _add_history(self, path):
        thumb = QLabel()
        pm = self._load_pixmap(path)
        if pm is not None and not pm.isNull():
            thumb.setPixmap(pm.scaled(110, 62, Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                                      Qt.TransformationMode.SmoothTransformation))
        else:
            thumb.setText("SVG")
            thumb.setAlignment(Qt.AlignmentFlag.AlignCenter)
        thumb.setFixedSize(110, 62)
        thumb.setStyleSheet(f"border: 1px solid {CP['border_bright']}; border-radius: 4px;")
        thumb.setCursor(Qt.CursorShape.PointingHandCursor)
        thumb.mousePressEvent = lambda e, p=path: self._show_preview(p)
        self._hist_row.insertWidget(self._hist_row.count() - 1, thumb)

    # ── Accès au fichier ─────────────────────────────────────────────────────
    def _open_dir(self):
        # Ouvre l'explorateur avec l'image générée sélectionnée si possible
        if self._current_path and os.path.isfile(self._current_path):
            try:
                import subprocess
                subprocess.Popen(["explorer", "/select,", os.path.normpath(self._current_path)])
                return
            except Exception:
                pass
        d = projects.project_dir(self._project_id) if self._project_id \
            else self.cfg.get("output_dir", "")
        os.makedirs(d, exist_ok=True)
        try:
            os.startfile(d)  # Windows
        except Exception:
            QMessageBox.information(self, "Dossier", d)

    # ── Divers ───────────────────────────────────────────────────────────────
    def _on_worker_error(self, msg):
        self._set_busy(False, "")
        QMessageBox.critical(self, "Erreur", msg)

    def _set_busy(self, busy, msg):
        # Barre de chargement GAUCHE (fenêtre Image IA) : réservée à la GÉNÉRATION
        # du prompt et de l'image — PAS à la discussion (qui a son propre indicateur
        # dans le chat, voir _set_chat_busy).
        self._status.setText(msg)
        self._progress.setVisible(busy)
        self._cancel_btn.setVisible(busy)
        self._gen_btn.setEnabled(not busy)
        if busy:
            self._progress.setRange(0, 0)  # indéterminé
        else:
            self._progress.setRange(0, 100)

    def _set_chat_busy(self, busy, msg=""):
        """Indicateur de chargement DANS le chat (« Claude réfléchit »)."""
        self._chat_status.setText(msg)
        self._chat_busy.setVisible(busy)

    def _cancel_work(self):
        """Annule le travail en cours (génération image / discussion / synthèse)."""
        for w in (self._img_worker, self._chat_worker, self._synth_worker):
            if w and w.isRunning():
                try:
                    w.blockSignals(True)
                    w.terminate()
                    w.wait(300)
                except Exception:
                    pass
        self._set_busy(False, "Travail annulé.")
        self._set_chat_busy(False)
        self._gen_btn.setEnabled(True)

    def _res_value(self) -> str:
        """Palier de résolution Nano Banana, dérivé de la taille saisie
        (Largeur × Hauteur). L'image finale est de toute façon redimensionnée à
        la taille exacte par imagegen — ce palier ne pilote que la génération."""
        w, h = self._target_size()
        m = max(int(w), int(h))
        if m <= 512:
            return "512x512"
        if m <= 1024:
            return "1K"
        if m <= 2048:
            return "2K"
        return "4K"

    def resizeEvent(self, e):
        super().resizeEvent(e)
        if self._current_path:
            self._show_preview(self._current_path)


class StudioWindow(QMainWindow):
    """Coquille fenêtre pour l'app autonome — embarque StudioImagesPanel.

    L'implémentation vit dans StudioImagesPanel (partagée avec l'onglet
    « Image IA » de PANDORA). Cette fenêtre ne fait que l'héberger.
    """

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Studio Images — PANDORA")
        self.resize(1320, 860)
        self.panel = StudioImagesPanel()
        self.setCentralWidget(self.panel)
