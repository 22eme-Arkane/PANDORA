from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFrame, QApplication,
)
from PyQt6.QtCore import Qt
from ui.styles import CP, PANDORA_STYLESHEET

_EMAIL = "22eme.arkane@gmail.com"


class ContactDialog(QDialog):
    # Groupe WhatsApp — surchargé par la variante Live (ui/dialog_contact_live.py)
    _WA_GROUP = "PANDORA | Cinéma"
    _WA_LINK  = "https://chat.whatsapp.com/JRo5SWLBwbxLgACtrDksDj"

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Nous contacter")
        # Largeur fixe, hauteur adaptative : évite que le contenu (plus long en
        # anglais) soit rogné en bas.
        self.setFixedWidth(520)
        self.setMinimumHeight(470)
        self.setStyleSheet(PANDORA_STYLESHEET + f"QDialog{{background:{CP['bg1']};}}")

        lay = QVBoxLayout(self)
        lay.setContentsMargins(32, 28, 32, 28)
        lay.setSpacing(18)

        # ── Header ────────────────────────────────────────────────────────────
        head = QHBoxLayout()
        badge = QLabel("✉")
        badge.setFixedSize(48, 48)
        badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        badge.setStyleSheet(
            f"background:qlineargradient(x1:0,y1:0,x2:1,y2:1,"
            f"stop:0 {CP['accent']},stop:1 {CP['accent2']});"
            f"border-radius:12px;color:#07080f;"
            f"font-size:22px;font-weight:900;border:none;"
        )
        head.addWidget(badge)
        head.addSpacing(14)

        title_col = QVBoxLayout()
        title_col.setSpacing(2)
        title = QLabel("Nous contacter")
        title.setStyleSheet(
            f"color:{CP['text_primary']};font-size:20px;font-weight:800;background:transparent;"
        )
        sub = QLabel("PANDORA × 22eme ARKANE")
        sub.setStyleSheet(
            f"color:{CP['text_dim']};font-size:10px;font-family:'Consolas',monospace;"
            f"letter-spacing:1px;background:transparent;"
        )
        title_col.addWidget(title)
        title_col.addWidget(sub)
        head.addLayout(title_col)
        head.addStretch()
        lay.addLayout(head)

        # ── Adresse e-mail + bouton copier ────────────────────────────────────
        email_frame = QFrame()
        email_frame.setStyleSheet(
            f"QFrame{{background:{CP['bg2']};border:1px solid {CP['border']};"
            f"border-radius:10px;}}"
        )
        ef = QHBoxLayout(email_frame)
        ef.setContentsMargins(16, 12, 12, 12)
        ef.setSpacing(12)

        email_lbl = QLabel(_EMAIL)
        email_lbl.setStyleSheet(
            f"color:{CP['accent']};font-size:13px;font-family:'Consolas',monospace;"
            f"font-weight:700;background:transparent;border:none;"
        )

        self._btn_copy = QPushButton("⎘  Copier")
        self._btn_copy.setFixedHeight(34)
        self._btn_copy.setFixedWidth(104)
        self._btn_copy.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_copy.setStyleSheet(
            f"QPushButton{{background:transparent;color:{CP['text_secondary']};"
            f"border:1px solid {CP['border']};border-radius:6px;"
            f"font-size:11px;font-weight:700;padding:0 12px;}}"
            f"QPushButton:hover{{background:{CP['bg3']};color:{CP['text_primary']};"
            f"border-color:{CP['border_bright']};}}"
            f"QPushButton:pressed{{background:{CP['bg4']};}}"
        )
        self._btn_copy.clicked.connect(self._copy_email)

        ef.addWidget(email_lbl, 1)
        ef.addWidget(self._btn_copy)
        lay.addWidget(email_frame)

        # ── Communauté WhatsApp ───────────────────────────────────────────────
        wa_frame = QFrame()
        wa_frame.setStyleSheet(
            f"QFrame{{background:rgba(37,211,102,0.06);"
            f"border:1px solid rgba(37,211,102,0.20);border-radius:10px;}}"
        )
        wf = QHBoxLayout(wa_frame)
        wf.setContentsMargins(16, 12, 12, 12)
        wf.setSpacing(12)

        wa_ico = QLabel("💬")
        wa_ico.setFixedSize(36, 36)
        wa_ico.setAlignment(Qt.AlignmentFlag.AlignCenter)
        wa_ico.setStyleSheet(
            "background:rgba(37,211,102,0.12);border-radius:8px;"
            "font-size:18px;border:none;"
        )

        wa_col = QVBoxLayout()
        wa_col.setSpacing(2)
        wa_title = QLabel("Communauté WhatsApp\n" + self._WA_GROUP)
        wa_title.setStyleSheet(
            f"color:{CP['text_primary']};font-size:11px;font-weight:700;"
            f"background:transparent;border:none;"
        )
        wa_desc = QLabel(
            "Rejoignez les utilisateurs de PANDORA pour signaler des bugs, "
            "suivre les nouveautés et échanger avec la communauté."
        )
        wa_desc.setWordWrap(True)
        wa_desc.setStyleSheet(
            f"color:{CP['text_secondary']};font-size:10px;"
            f"background:transparent;border:none;"
        )
        wa_col.addWidget(wa_title)
        wa_col.addWidget(wa_desc)

        btn_wa = QPushButton("Rejoindre")
        btn_wa.setFixedHeight(34)
        btn_wa.setMinimumWidth(94)
        btn_wa.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_wa.setStyleSheet(
            "QPushButton{background:rgba(37,211,102,0.15);color:#25d366;"
            "border:1px solid rgba(37,211,102,0.35);border-radius:6px;"
            "font-size:11px;font-weight:700;padding:0 16px;}"
            "QPushButton:hover{background:rgba(37,211,102,0.25);"
            "border-color:rgba(37,211,102,0.60);}"
        )
        btn_wa.clicked.connect(self._open_whatsapp)

        wf.addWidget(wa_ico)
        wf.addLayout(wa_col, 1)
        wf.addWidget(btn_wa)
        lay.addWidget(wa_frame)

        # ── Instructions ──────────────────────────────────────────────────────
        inst_frame = QFrame()
        inst_frame.setStyleSheet(
            f"QFrame{{background:rgba(78,205,196,0.05);"
            f"border:1px solid rgba(78,205,196,0.15);border-radius:10px;}}"
        )
        il = QVBoxLayout(inst_frame)
        il.setContentsMargins(16, 14, 16, 14)
        il.setSpacing(10)

        def _row(icon: str, subject: str, detail: str) -> QHBoxLayout:
            row = QHBoxLayout()
            row.setSpacing(10)
            ico = QLabel(icon)
            ico.setFixedWidth(22)
            ico.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignHCenter)
            ico.setStyleSheet("background:transparent;border:none;font-size:14px;")
            col = QVBoxLayout()
            col.setSpacing(2)
            subj_lbl = QLabel(subject)
            subj_lbl.setStyleSheet(
                f"color:{CP['text_primary']};font-size:11px;font-weight:700;"
                f"background:transparent;border:none;"
            )
            det_lbl = QLabel(detail)
            det_lbl.setWordWrap(True)
            det_lbl.setStyleSheet(
                f"color:{CP['text_secondary']};font-size:10px;"
                f"background:transparent;border:none;"
            )
            col.addWidget(subj_lbl)
            col.addWidget(det_lbl)
            row.addWidget(ico)
            row.addLayout(col, 1)
            return row

        il.addLayout(_row(
            "🐛",
            "Signaler un bug — objet : Bug",
            "Décrivez le problème et les étapes pour le reproduire.",
        ))
        il.addLayout(_row(
            "💬",
            "Avis / suggestion — objet : Avis",
            "Partagez vos retours, idées de fonctionnalités ou impressions.",
        ))
        lay.addWidget(inst_frame)

        # ── Envoi DIRECT (Supabase) — sans passer par une boîte mail ──────────
        # Visible seulement si le serveur est configuré (core/support_backend) ;
        # sinon on garde les instructions e-mail ci-dessus (repli complet).
        from core.support_backend import is_configured as _sb_ok
        if _sb_ok():
            inst_frame.setVisible(False)
            self._build_report_form(lay)

        lay.addStretch()

        # ── Footer : charte + fermer ──────────────────────────────────────────
        footer_row = QHBoxLayout()
        footer_row.setSpacing(10)

        btn_eula = QPushButton("Charte d'utilisation")
        btn_eula.setFixedHeight(40)
        btn_eula.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_eula.setStyleSheet(
            f"QPushButton{{background:transparent;color:{CP['text_dim']};"
            f"border:1px solid {CP['border']};border-radius:8px;"
            f"font-size:11px;font-weight:600;}}"
            f"QPushButton:hover{{color:{CP['text_secondary']};border-color:{CP['border_bright']};}}"
        )
        btn_eula.clicked.connect(self._open_eula)
        footer_row.addWidget(btn_eula)

        btn_close = QPushButton("Fermer")
        btn_close.setFixedHeight(40)
        btn_close.setStyleSheet(
            f"QPushButton{{background:{CP['bg3']};color:{CP['text_secondary']};"
            f"border:1px solid {CP['border']};border-radius:8px;"
            f"font-size:12px;font-weight:700;}}"
            f"QPushButton:hover{{background:{CP['bg4']};color:{CP['text_primary']};}}"
        )
        btn_close.clicked.connect(self.accept)
        footer_row.addWidget(btn_close, 1)
        lay.addLayout(footer_row)

        from core.i18n import retranslate_widget
        retranslate_widget(self)

    # ── Formulaire d'envoi direct (avis / bug → table Supabase) ───────────────

    def _build_report_form(self, lay):
        from PyQt6.QtWidgets import QComboBox, QTextEdit, QLineEdit

        form = QFrame()
        form.setStyleSheet(
            f"QFrame{{background:rgba(78,205,196,0.05);"
            f"border:1px solid rgba(78,205,196,0.15);border-radius:10px;}}"
        )
        fl = QVBoxLayout(form)
        fl.setContentsMargins(16, 14, 16, 14)
        fl.setSpacing(10)

        head = QLabel("💬  Donner votre avis / Signaler un bug")
        head.setStyleSheet(
            f"color:{CP['text_primary']};font-size:12px;font-weight:700;"
            f"background:transparent;border:none;"
        )
        fl.addWidget(head)

        sub = QLabel("Envoyé directement à 22eme ARKANE — aucune boîte mail requise.")
        sub.setWordWrap(True)
        sub.setStyleSheet(
            f"color:{CP['text_dim']};font-size:10px;background:transparent;border:none;"
        )
        fl.addWidget(sub)

        row = QHBoxLayout()
        row.setSpacing(8)
        self._report_kind = QComboBox()
        self._report_kind.addItem("💬  Avis / suggestion", "avis")
        self._report_kind.addItem("🐛  Bug", "bug")
        self._report_kind.setFixedHeight(32)
        row.addWidget(self._report_kind, 1)
        self._report_email = QLineEdit()
        self._report_email.setFixedHeight(32)
        self._report_email.setPlaceholderText("Votre e-mail (optionnel, pour une réponse)")
        row.addWidget(self._report_email, 2)
        fl.addLayout(row)

        self._report_msg = QTextEdit()
        self._report_msg.setFixedHeight(96)
        self._report_msg.setPlaceholderText(
            "Décrivez votre avis ou le problème rencontré (étapes pour le reproduire)…")
        self._report_msg.setStyleSheet(
            f"QTextEdit{{background:{CP['bg2']};border:1px solid {CP['border']};"
            f"border-radius:8px;color:{CP['text_primary']};font-size:11px;padding:8px;}}"
        )
        fl.addWidget(self._report_msg)

        send_row = QHBoxLayout()
        send_row.setSpacing(10)
        self._report_status = QLabel("")
        self._report_status.setWordWrap(True)
        self._report_status.setStyleSheet(
            f"color:{CP['text_dim']};font-size:10px;background:transparent;border:none;"
        )
        send_row.addWidget(self._report_status, 1)
        self._btn_report_send = QPushButton("✉  Envoyer")
        self._btn_report_send.setFixedHeight(34)
        self._btn_report_send.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_report_send.setStyleSheet(
            f"QPushButton{{background:{CP['accent']};color:#07080f;"
            f"border:none;border-radius:8px;font-size:11px;font-weight:700;padding:0 20px;}}"
            f"QPushButton:hover{{background:#6eded6;}}"
            f"QPushButton:disabled{{background:{CP['bg3']};color:{CP['text_dim']};"
            f"border:1px solid {CP['border']};}}"
        )
        self._btn_report_send.clicked.connect(self._on_send_report)
        send_row.addWidget(self._btn_report_send)
        fl.addLayout(send_row)

        lay.addWidget(form)

    def _on_send_report(self):
        msg = self._report_msg.toPlainText().strip()
        if not msg:
            self._report_status.setText("Écrivez d'abord votre message.")
            return
        kind = self._report_kind.currentData() or "avis"
        # Pour un BUG, on joint la queue du log de crash (contexte précieux).
        log = ""
        if kind == "bug":
            try:
                import tempfile, os as _os
                _lp = _os.path.join(tempfile.gettempdir(), "pandora_crash.log")
                if _os.path.isfile(_lp):
                    with open(_lp, encoding="utf-8", errors="replace") as f:
                        log = f.read()
            except Exception:
                pass
        from api.report import SendReportWorker
        self._btn_report_send.setEnabled(False)
        self._report_status.setText("Envoi en cours…")
        self._report_worker = SendReportWorker(
            kind, msg, self._report_email.text().strip(), log)
        self._report_worker.done.connect(self._on_report_sent)
        self._report_worker.failed.connect(self._on_report_failed)
        self._report_worker.start()

    def _on_report_sent(self):
        from core.worker import abandon_thread
        abandon_thread(self._report_worker)
        self._report_worker = None
        self._btn_report_send.setEnabled(True)
        self._report_msg.clear()
        self._report_status.setText("Envoyé — merci pour votre retour ! ✓")
        self._report_status.setStyleSheet(
            f"color:{CP['green']};font-size:10px;background:transparent;border:none;"
        )

    def _on_report_failed(self, msg: str):
        from core.worker import abandon_thread
        abandon_thread(self._report_worker)
        self._report_worker = None
        self._btn_report_send.setEnabled(True)
        self._report_status.setText(f"Échec de l'envoi : {msg}")
        self._report_status.setStyleSheet(
            f"color:{CP['red']};font-size:10px;background:transparent;border:none;"
        )

    def _open_whatsapp(self):
        import webbrowser
        webbrowser.open(self._WA_LINK)

    def _open_eula(self):
        from ui.dialog_eula import EulaDialog
        EulaDialog(self, mode="read").exec()

    def _copy_email(self):
        QApplication.clipboard().setText(_EMAIL)
        self._btn_copy.setText("✓  Copié !")
        self._btn_copy.setStyleSheet(
            f"QPushButton{{background:rgba(78,205,196,0.12);color:{CP['accent']};"
            f"border:1px solid {CP['accent']}44;border-radius:6px;"
            f"font-size:11px;font-weight:700;padding:0 12px;}}"
        )
        from PyQt6.QtCore import QTimer
        _default = (
            f"QPushButton{{background:transparent;color:{CP['text_secondary']};"
            f"border:1px solid {CP['border']};border-radius:6px;"
            f"font-size:11px;font-weight:700;padding:0 12px;}}"
            f"QPushButton:hover{{background:{CP['bg3']};color:{CP['text_primary']};"
            f"border-color:{CP['border_bright']};}}"
            f"QPushButton:pressed{{background:{CP['bg4']};}}"
        )
        QTimer.singleShot(2000, lambda: (
            self._btn_copy.setText("⎘  Copier"),
            self._btn_copy.setStyleSheet(_default),
        ))
