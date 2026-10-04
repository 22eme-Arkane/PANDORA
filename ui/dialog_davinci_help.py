from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QFrame, QScrollArea, QWidget,
)
from PyQt6.QtCore import Qt
from ui.styles import CP, PANDORA_STYLESHEET
from core.i18n import translate


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
    t = QLabel(translate(title))
    t.setWordWrap(True)
    t.setStyleSheet(
        f"color:{CP['text_primary']};font-size:12px;font-weight:700;background:transparent;border:none;"
    )
    col.addWidget(t)
    if detail:
        d = QLabel(translate(detail))
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
        sub = QLabel("Pont local  ·  Media Pool  ·  Timeline")
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
            "PANDORA communique avec DaVinci Resolve par un <b>pont local</b> "
            "(un petit script Python lancé dans Resolve). Il importe les clips générés "
            "dans le Media Pool, rangés par séquence, monte le storyboard sur une "
            "timeline, et lit les clips de la timeline pour les modifier."
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
            "Paramètres → DaVinci Resolve → « Installer / mettre à jour les scripts »",
            "Copie seedance_bridge et pandora_send dans le dossier Scripts de Resolve. "
            "Après une première installation, redémarrez Resolve.",
        ))
        sl.addWidget(_step(
            "2",
            "Ouvrez DaVinci Resolve et un projet",
            "Jusqu'à Resolve 20.x, un Python 3 64 bits doit être installé sur le poste "
            "(python.org, « pour tous les utilisateurs ») : Resolve s'en sert pour "
            "exécuter les scripts.",
        ))
        sl.addWidget(_step(
            "3",
            "Dans DaVinci : Espace de travail → Scripts → seedance_bridge",
            "Une petite fenêtre « PANDORA Bridge » confirme que le pont est actif "
            "(port 19876). Laissez-la ouverte : la fermer arrête le pont.",
        ))
        sl.addWidget(_step(
            "4",
            "Dans PANDORA → Paramètres, cliquez sur « Connecter »",
            "Le voyant passe au vert ●. Les clips générés arrivent dans le chutier "
            "PANDORA, rangés par séquence (SQ01, SQ02…).",
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
        studio_title = QLabel("⚠  Version gratuite ou Studio ?")
        studio_title.setStyleSheet(
            f"color:{CP['orange']};font-size:12px;font-weight:700;background:transparent;border:none;"
        )
        studio_body = QLabel(
            "Jusqu'à Resolve 21.0, la version gratuite lance aussi le pont depuis le menu "
            "Scripts. Depuis <b>Resolve 21.1</b> (septembre 2026), Blackmagic réserve le "
            "scripting Python à <b>DaVinci Resolve Studio</b> : le pont n'apparaît plus "
            "dans le menu de la version gratuite.<br><br>"
            "Sans pont, tout le reste fonctionne : la génération, et l'export de la "
            "timeline (Storyboard → Action → « Exporter la timeline (XML) »), que Resolve "
            "— gratuit ou Studio — et Premiere savent importer."
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
             "Lancez seedance_bridge dans Resolve (Espace de travail → Scripts) et "
             "laissez sa fenêtre ouverte."),
            ("Le script n'est pas dans le menu",
             "Paramètres → DaVinci Resolve → « Installer / mettre à jour les scripts », "
             "puis redémarrez Resolve. Version gratuite 21.1 ou plus : le menu "
             "n'affiche plus les scripts Python."),
            ("« Pont à mettre à jour »",
             "Mettez les scripts à jour, fermez la fenêtre « PANDORA Bridge », puis "
             "relancez seedance_bridge."),
            ("« Port déjà utilisé » dans la fenêtre du pont",
             "Un ancien pont tourne encore : fermez sa fenêtre, ou redémarrez Resolve."),
            ("« API DaVinci indisponible »",
             "Ouvrez un projet, puis relancez le pont depuis le menu Scripts. Resolve "
             "20.x et antérieurs : vérifiez qu'un Python 3 64 bits est installé."),
        ]
        for problem, solution in tips:
            tip_row = QVBoxLayout()
            tip_row.setSpacing(2)
            p_lbl = QLabel(f"● {translate(problem)}")
            p_lbl.setStyleSheet(
                f"color:{CP['text_secondary']};font-size:11px;font-weight:700;"
                f"background:transparent;border:none;"
            )
            s_lbl = QLabel(f"   → {translate(solution)}")
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
