"""ui/dialog_comfy_install.py — « ComfyUI n'est pas joignable. »

Ouverte quand on choisit un moteur ComfyUI sans serveur vivant. Elle ne fait
pas l'installation à la place de l'utilisateur — PANDORA n'embarque rien de
ComfyUI et n'exécute pas d'installeur tiers — mais elle rend le chemin
évident : télécharger ComfyUI Desktop, le lancer, charger le gabarit H3 qui
télécharge les modèles, puis « Vérifier ».

Le texte change selon ce qu'on sait : Desktop déjà installé mais pas lancé
(le cas de loin le plus fréquent après la première fois) ou rien du tout.
Décision Matthieu 2026-09-13 : ce sont les utilisateurs qui installent ;
la fenêtre guide, elle ne bloque pas au-delà du moteur choisi.
"""

from __future__ import annotations

from PyQt6.QtCore import Qt, QUrl
from PyQt6.QtGui import QDesktopServices
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QLineEdit, QFrame,
)

from core import comfy as _cf
from core.i18n import translate
from ui.styles import CP
from ui.widgets import disable_default_buttons, section_label


def _btn(text: str, accent: str, strong: bool = False) -> QPushButton:
    b = QPushButton(text)
    b.setFixedHeight(38)
    b.setCursor(Qt.CursorShape.PointingHandCursor)
    r, g, bl = int(accent[1:3], 16), int(accent[3:5], 16), int(accent[5:7], 16)
    if strong:
        b.setStyleSheet(
            f"QPushButton{{background:{accent};border:none;border-radius:8px;"
            f"color:#0c0e1a;font-size:12px;font-weight:700;padding:0 18px;}}"
            f"QPushButton:hover{{background:rgba({r},{g},{bl},0.85);}}")
    else:
        b.setStyleSheet(
            f"QPushButton{{background:transparent;border:1px solid {accent};"
            f"border-radius:8px;color:{accent};font-size:12px;padding:0 18px;}}"
            f"QPushButton:hover{{background:rgba({r},{g},{bl},0.12);}}")
    return b


class ComfyInstallDialog(QDialog):
    """`accepted()` signifie : un serveur ComfyUI répond maintenant."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._ok = False
        self.setWindowTitle(translate("ComfyUI — installation"))
        self.setMinimumWidth(640)
        self.setStyleSheet(f"QDialog{{background:{CP['bg1']};}}")

        lay = QVBoxLayout(self)
        lay.setContentsMargins(26, 22, 26, 20)
        lay.setSpacing(12)

        installed = _cf.desktop_installed()
        titre = QLabel(translate("ComfyUI est installé mais ne répond pas")
                       if installed else translate("ComfyUI n'est pas installé"))
        titre.setWordWrap(True)
        titre.setStyleSheet(
            f"color:{CP['text_primary']};font-size:17px;font-weight:700;background:transparent;")
        lay.addWidget(titre)

        intro = QLabel(translate(
            "ComfyUI est un moteur de rendu local à construction nodale — le "
            "même principe que Fusion dans DaVinci Resolve ou Nuke. PANDORA "
            "s'y connecte pour faire tourner MiniMax H3 et tout workflow que "
            "vous y assemblez, sur votre propre carte graphique, sans facture."))
        intro.setWordWrap(True)
        intro.setStyleSheet(f"color:{CP['text_secondary']};font-size:12px;background:transparent;")
        lay.addWidget(intro)

        lay.addWidget(section_label("Étapes"))
        box = QFrame()
        box.setStyleSheet(f"QFrame{{background:{CP['bg2']};border:1px solid {CP['border']};border-radius:8px;}}")
        bl = QVBoxLayout(box)
        bl.setContentsMargins(16, 12, 16, 12)
        bl.setSpacing(6)
        etapes = ([translate("1.  Lancez ComfyUI Desktop et attendez que sa fenêtre affiche l'éditeur.")]
                  if installed else
                  [translate("1.  Téléchargez ComfyUI Desktop (site officiel) et installez-le."),
                   translate("2.  Lancez-le une première fois : il prépare son environnement (plusieurs minutes).")])
        etapes += [
            translate("•  Pour MiniMax H3 : dans ComfyUI, Bibliothèque de gabarits › Vidéo › "
                      "MiniMax H3. Le gabarit télécharge les modèles (plusieurs dizaines de Go)."),
            translate("•  Revenez ici et cliquez « Vérifier ». L'adresse se détecte seule ; "
                      "ne la changez que si ComfyUI écoute ailleurs."),
        ]
        for e in etapes:
            l = QLabel(e); l.setWordWrap(True)
            l.setStyleSheet(f"color:{CP['text_primary']};font-size:12px;background:transparent;")
            bl.addWidget(l)
        lay.addWidget(box)

        row = QHBoxLayout()
        row.setSpacing(8)
        self._url = QLineEdit()
        self._url.setFixedHeight(36)
        self._url.setPlaceholderText(translate("Adresse (détection automatique : ") + ", ".join(_cf.CANDIDATE_URLS) + ")")
        self._url.setText("")
        self._url.setStyleSheet(
            f"QLineEdit{{background:{CP['bg3']};border:1px solid {CP['border']};border-radius:6px;"
            f"color:{CP['text_primary']};font-size:11px;font-family:'Consolas',monospace;padding:0 12px;}}")
        row.addWidget(self._url, 1)
        b_check = _btn(translate("Vérifier"), CP["accent"], strong=True)
        b_check.clicked.connect(self._check)
        row.addWidget(b_check)
        lay.addLayout(row)

        self._state = QLabel("")
        self._state.setWordWrap(True)
        self._state.setStyleSheet(f"color:{CP['text_dim']};font-size:10px;background:transparent;")
        lay.addWidget(self._state)

        note = QLabel("⚠  " + translate(
            "Les poids MiniMax H3 sont publiés sous une licence qui exclut l'Union "
            "européenne, le Royaume-Uni, la Corée du Sud et les États-Unis. PANDORA ne "
            "distribue ni les poids ni le moteur : les installer et les utiliser relève "
            "de votre seule responsabilité."))
        note.setWordWrap(True)
        note.setStyleSheet("color:#f0b429;font-size:10px;background:transparent;")
        lay.addWidget(note)

        btns = QHBoxLayout()
        b_close = _btn(translate("Plus tard"), CP["text_dim"])
        b_close.clicked.connect(self.reject)
        btns.addWidget(b_close)
        btns.addStretch()
        b_docs = _btn(translate("Guide H3 (docs.comfy.org)"), CP["accent2"])
        b_docs.clicked.connect(self._open_docs)
        btns.addWidget(b_docs)
        b_dl = _btn(translate("Télécharger ComfyUI Desktop"), CP["accent"])
        b_dl.clicked.connect(self._open_download)
        btns.addWidget(b_dl)
        lay.addLayout(btns)

        disable_default_buttons(self)

    # ── Actions (méthodes liées, jamais de lambda) ───────────────────────────

    def _open_download(self):
        QDesktopServices.openUrl(QUrl(_cf.DOWNLOAD_URL))

    def _open_docs(self):
        QDesktopServices.openUrl(QUrl(_cf.DOCS_H3_URL))

    def _check(self):
        typed = self._url.text().strip()
        base = _cf.discover() if not typed else (_cf.normalize_url(typed)
                                                 if _cf.ping(typed)[0] else "")
        if base:
            ok, msg, info = _cf.ping(base)
            if typed:
                try:
                    _cf.set_url(base)
                except Exception:
                    pass
            warn = ""
            if info.get("version") and not _cf.version_ok(info["version"]):
                warn = "  ·  " + translate("version trop ancienne pour H3 (0.30.0 minimum) — mettez ComfyUI à jour")
            self._state.setText("✓  " + translate(msg) + warn)
            self._state.setStyleSheet(f"color:{CP['accent']};font-size:10px;background:transparent;")
            self._ok = True
            self.accept()
        else:
            self._state.setText(translate(
                "Toujours injoignable. ComfyUI Desktop doit être lancé ET avoir fini "
                "de démarrer son serveur (la fenêtre affiche l'éditeur de nœuds)."))
            self._state.setStyleSheet("color:#f0b429;font-size:10px;background:transparent;")

    def is_ready(self) -> bool:
        return self._ok
