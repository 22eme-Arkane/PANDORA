from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QFrame, QScrollArea, QWidget,
)
from PyQt6.QtCore import Qt
from ui.styles import CP, PANDORA_STYLESHEET


def _sep():
    f = QFrame()
    f.setFixedHeight(1)
    f.setStyleSheet(f"background:{CP['border']};")
    return f


def _step(num: str, title: str, detail: str = "") -> QWidget:
    w = QWidget()
    w.setStyleSheet("background:transparent;")
    lay = QHBoxLayout(w)
    lay.setContentsMargins(0, 0, 0, 0)
    lay.setSpacing(14)
    lay.setAlignment(Qt.AlignmentFlag.AlignTop)

    badge = QLabel(num)
    badge.setFixedSize(30, 30)
    badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
    badge.setStyleSheet(
        f"background:{CP['accent']};color:#07080f;border-radius:15px;"
        f"font-size:13px;font-weight:800;border:none;"
    )

    col = QVBoxLayout()
    col.setSpacing(4)
    t = QLabel(title)
    t.setWordWrap(True)
    t.setStyleSheet(
        f"color:{CP['text_primary']};font-size:12px;font-weight:700;background:transparent;border:none;"
    )
    col.addWidget(t)
    if detail:
        d = QLabel(detail)
        d.setWordWrap(True)
        d.setStyleSheet(
            f"color:{CP['text_dim']};font-size:11px;"
            f"font-family:'Consolas',monospace;background:transparent;border:none;"
        )
        col.addWidget(d)

    lay.addWidget(badge)
    lay.addLayout(col, 1)
    return w


class DaVinciHelpDialog(QDialog):

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Connecter DaVinci Resolve — Guide")
        self.setFixedSize(580, 620)
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

        badge = QLabel("◈")
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
        title = QLabel("Connexion DaVinci Resolve")
        title.setStyleSheet(
            f"color:{CP['text_primary']};font-size:18px;font-weight:800;background:transparent;"
        )
        sub = QLabel("Bridge TCP  ·  Media Pool  ·  Timeline")
        sub.setStyleSheet(
            f"color:{CP['text_dim']};font-size:10px;font-family:'Consolas',monospace;"
            f"letter-spacing:1px;background:transparent;"
        )
        title_col.addWidget(title)
        title_col.addWidget(sub)
        hl.addLayout(title_col)
        hl.addStretch()
        outer.addWidget(header)

        # Scroll
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea{background:transparent;border:none;}")

        inner = QWidget()
        inner.setStyleSheet(f"background:{CP['bg1']};")
        lay = QVBoxLayout(inner)
        lay.setContentsMargins(28, 24, 28, 28)
        lay.setSpacing(16)

        # ── Comment ça fonctionne ──────────────────────────────────────────────
        explain_frame = QFrame()
        explain_frame.setStyleSheet(
            f"QFrame{{background:rgba(78,205,196,0.06);"
            f"border:1px solid rgba(78,205,196,0.18);border-radius:10px;}}"
        )
        el = QVBoxLayout(explain_frame)
        el.setContentsMargins(16, 14, 16, 14)
        el.setSpacing(6)
        explain_title = QLabel("Comment ça fonctionne ?")
        explain_title.setStyleSheet(
            f"color:{CP['accent']};font-size:12px;font-weight:700;background:transparent;border:none;"
        )
        explain_body = QLabel(
            "PANDORA communique avec DaVinci Resolve via un <b>bridge TCP local</b> "
            "(un petit script Python qui tourne dans DaVinci). "
            "Cette connexion permet d'importer automatiquement les médias générés "
            "dans le Media Pool et de lire les clips de la timeline."
        )
        explain_body.setWordWrap(True)
        explain_body.setStyleSheet(
            f"color:{CP['text_secondary']};font-size:11px;background:transparent;border:none;"
        )
        el.addWidget(explain_title)
        el.addWidget(explain_body)
        lay.addWidget(explain_frame)

        # ── Étapes ────────────────────────────────────────────────────────────
        steps_frame = QFrame()
        steps_frame.setStyleSheet(
            f"QFrame{{background:{CP['bg2']};border:1px solid {CP['border']};border-radius:10px;}}"
        )
        sl = QVBoxLayout(steps_frame)
        sl.setContentsMargins(20, 18, 20, 18)
        sl.setSpacing(16)

        steps_lbl = QLabel("Étapes de configuration")
        steps_lbl.setStyleSheet(
            f"color:{CP['text_primary']};font-size:13px;font-weight:700;background:transparent;border:none;"
        )
        sl.addWidget(steps_lbl)
        sl.addWidget(_sep())

        sl.addWidget(_step(
            "1",
            "Dans PANDORA → Paramètres, clique « Installer bridge »",
            "Le fichier seedance_bridge.py sera copié dans le dossier Scripts de DaVinci.",
        ))
        sl.addWidget(_step(
            "2",
            "Ouvre DaVinci Resolve et charge ton projet",
            "Le bridge doit être lancé depuis un projet ouvert.",
        ))
        sl.addWidget(_step(
            "3",
            "Dans DaVinci : Espace de travail → Scripts → seedance_bridge",
            "Le script démarre le serveur TCP local (port 19876). "
            "DaVinci affiche une notification de confirmation.",
        ))
        sl.addWidget(_step(
            "4",
            "Dans PANDORA → Paramètres, clique « Connecter »",
            "PANDORA se connecte au bridge. Le voyant passe au vert ●.",
        ))
        lay.addWidget(steps_frame)

        # ── Version Studio ────────────────────────────────────────────────────
        studio_frame = QFrame()
        studio_frame.setStyleSheet(
            f"QFrame{{background:rgba(255,140,66,0.07);"
            f"border:1px solid rgba(255,140,66,0.22);border-radius:8px;}}"
        )
        stl = QVBoxLayout(studio_frame)
        stl.setContentsMargins(14, 12, 14, 12)
        studio_title = QLabel("⚠  DaVinci Resolve Studio requis")
        studio_title.setStyleSheet(
            f"color:{CP['orange']};font-size:12px;font-weight:700;background:transparent;border:none;"
        )
        studio_body = QLabel(
            "Le scripting Python de DaVinci Resolve (accès au Media Pool, aux timelines) "
            "est <b>réservé à DaVinci Resolve Studio</b> (version payante).\n\n"
            "Avec la version gratuite, le bridge TCP fonctionne mais l'import automatique "
            "dans le Media Pool et la lecture des clips de la timeline ne sont pas disponibles.\n\n"
            "La génération de vidéos et portraits Seedance 2.0 fonctionne normalement "
            "dans les deux versions."
        )
        studio_body.setWordWrap(True)
        studio_body.setStyleSheet(
            f"color:{CP['text_secondary']};font-size:11px;background:transparent;border:none;"
        )
        stl.addWidget(studio_title)
        stl.addWidget(studio_body)
        lay.addWidget(studio_frame)

        # ── Dépannage ─────────────────────────────────────────────────────────
        trouble_frame = QFrame()
        trouble_frame.setStyleSheet(
            f"QFrame{{background:{CP['bg2']};border:1px solid {CP['border']};border-radius:10px;}}"
        )
        tl = QVBoxLayout(trouble_frame)
        tl.setContentsMargins(16, 14, 16, 14)
        tl.setSpacing(8)
        trouble_title = QLabel("Dépannage")
        trouble_title.setStyleSheet(
            f"color:{CP['text_primary']};font-size:12px;font-weight:700;background:transparent;border:none;"
        )
        tl.addWidget(trouble_title)

        tips = [
            ("Connexion refusée",
             "Vérifie que seedance_bridge tourne dans DaVinci (Espace de travail → Scripts)."),
            ("Le script ne s'affiche pas",
             "Clique « Installer bridge » dans Paramètres et relance DaVinci."),
            ("Bridge actif mais scripting inactif",
             "Ton installation DaVinci est en version gratuite — Studio requis pour le scripting."),
            ("Déconnexion aléatoire",
             "Recharge DaVinci ou clique « Actualiser » dans Paramètres."),
        ]
        for problem, solution in tips:
            tip_row = QVBoxLayout()
            tip_row.setSpacing(2)
            p_lbl = QLabel(f"● {problem}")
            p_lbl.setStyleSheet(
                f"color:{CP['text_secondary']};font-size:11px;font-weight:700;"
                f"background:transparent;border:none;"
            )
            s_lbl = QLabel(f"   → {solution}")
            s_lbl.setWordWrap(True)
            s_lbl.setStyleSheet(
                f"color:{CP['text_dim']};font-size:10px;font-family:'Consolas',monospace;"
                f"background:transparent;border:none;"
            )
            tip_row.addWidget(p_lbl)
            tip_row.addWidget(s_lbl)
            tl.addLayout(tip_row)
        lay.addWidget(trouble_frame)

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
