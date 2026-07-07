"""Fenêtre de confirmation « Quitter PANDORA » — PARTAGÉE Cinéma ↔ Live.

Extraite de PandoraWindow.closeEvent pour que les DEUX éditions affichent la MÊME
demande de sauvegarde à la fermeture. Retourne :
    0 → Annuler (rester ouvert)
    1 → Sauvegarder et quitter
    2 → Quitter sans sauvegarder
L'appelant gère lui-même la sauvegarde (page scénario/conducteur) et accept/ignore.
"""
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QWidget, QFrame,
)
from PyQt6.QtCore import Qt

from core.i18n import retranslate_widget
from ui.styles import CP, PANDORA_STYLESHEET


def confirm_quit(parent) -> int:
    """Affiche la confirmation de fermeture et retourne 0 (annuler) / 1 (sauver+quitter)
    / 2 (quitter sans sauver)."""
    dlg = QDialog(parent)
    dlg.setWindowTitle("Quitter PANDORA")
    dlg.setFixedSize(560, 310)
    dlg.setStyleSheet(PANDORA_STYLESHEET + f"QDialog{{background:{CP['bg1']};}}")

    lay = QVBoxLayout(dlg)
    lay.setContentsMargins(28, 24, 28, 22)
    lay.setSpacing(14)

    lbl = QLabel("Voulez-vous vraiment quitter le programme ?")
    lbl.setWordWrap(True)
    lbl.setStyleSheet(
        f"color:{CP['text_primary']};font-size:14px;font-weight:600;background:transparent;")
    lay.addWidget(lbl)

    sub = QLabel("Les données du storyboard et des fiches sont sauvegardées automatiquement.")
    sub.setWordWrap(True)
    sub.setStyleSheet(f"color:{CP['text_dim']};font-size:10px;background:transparent;")
    lay.addWidget(sub)

    _sep = QFrame()
    _sep.setFixedHeight(1)
    _sep.setStyleSheet("background:rgba(200,164,0,0.22);margin:0 0;")
    lay.addWidget(_sep)

    # ── Callout soutien PANDORA ───────────────────────────────────────────────
    _don_frame = QWidget()
    _don_frame.setStyleSheet("background:rgba(200,164,0,0.06);border-radius:8px;")
    _don_lay = QVBoxLayout(_don_frame)
    _don_lay.setContentsMargins(14, 12, 14, 12)
    _don_lay.setSpacing(8)

    _don_lbl = QLabel("❤  PANDORA est gratuit. Il fonctionne grâce au soutien de la communauté.")
    _don_lbl.setWordWrap(True)
    _don_lbl.setStyleSheet("color:#c8a400;font-size:11px;font-weight:600;background:transparent;")
    _don_lay.addWidget(_don_lbl)

    _don_sub = QLabel(
        "Si ce logiciel vous est utile, un don — même modeste — nous aide à continuer à le développer.")
    _don_sub.setWordWrap(True)
    _don_sub.setStyleSheet(f"color:{CP['text_dim']};font-size:10px;background:transparent;")
    _don_lay.addWidget(_don_sub)

    _don_btn_row = QHBoxLayout()
    _don_btn_row.setSpacing(0)
    _don_btn_row.addStretch()
    _ss_don = (
        "QPushButton{background:transparent;color:#c8a400;"
        "border:1px solid rgba(200,164,0,0.50);border-radius:6px;"
        "font-size:10px;font-weight:700;padding:0 14px;}"
        "QPushButton:hover{background:rgba(245,197,24,0.12);color:#f5c518;"
        "border-color:rgba(245,197,24,0.70);}"
        "QPushButton:pressed{background:rgba(245,197,24,0.20);}")
    _btn_don = QPushButton("❤  Soutenir PANDORA  →")
    _btn_don.setFixedHeight(30)
    _btn_don.setCursor(Qt.CursorShape.PointingHandCursor)
    _btn_don.setStyleSheet(_ss_don)

    def _open_funding(*_args, dlg=dlg):
        from ui.dialog_funding import FundingDialog
        FundingDialog(dlg).exec()

    _btn_don.clicked.connect(_open_funding)
    _don_btn_row.addWidget(_btn_don)
    _don_lay.addLayout(_don_btn_row)
    lay.addWidget(_don_frame)
    lay.addStretch()

    btn_row = QHBoxLayout()
    btn_row.setSpacing(8)

    _ss_cancel = (
        f"QPushButton{{background:transparent;color:{CP['text_secondary']};"
        f"border:1px solid {CP['border']};border-radius:7px;"
        f"font-size:11px;font-weight:700;padding:0 14px;}}"
        f"QPushButton:hover{{background:{CP['bg2']};color:{CP['text_primary']};}}")
    _ss_quit = (
        f"QPushButton{{background:transparent;color:{CP['red']};"
        f"border:1px solid rgba(255,79,106,0.45);border-radius:7px;"
        f"font-size:11px;font-weight:700;padding:0 14px;}}"
        f"QPushButton:hover{{background:rgba(255,79,106,0.14);}}")
    _ss_save = (
        f"QPushButton{{background:{CP['accent']};color:#07080f;"
        f"border:none;border-radius:7px;"
        f"font-size:11px;font-weight:700;padding:0 14px;}}"
        f"QPushButton:hover{{background:#6eded6;}}")

    btn_cancel = QPushButton("Annuler")
    btn_cancel.setFixedHeight(36)
    btn_cancel.setStyleSheet(_ss_cancel)
    btn_cancel.clicked.connect(dlg.reject)

    btn_quit = QPushButton("Quitter sans sauvegarder")
    btn_quit.setFixedHeight(36)
    btn_quit.setStyleSheet(_ss_quit)
    btn_quit.clicked.connect(lambda: dlg.done(2))

    btn_save_quit = QPushButton("Sauvegarder et quitter")
    btn_save_quit.setFixedHeight(36)
    btn_save_quit.setStyleSheet(_ss_save)
    btn_save_quit.clicked.connect(lambda: dlg.done(1))

    btn_row.addWidget(btn_cancel)
    btn_row.addStretch()
    btn_row.addWidget(btn_quit)
    btn_row.addSpacing(4)
    btn_row.addWidget(btn_save_quit)
    lay.addLayout(btn_row)

    try:
        retranslate_widget(dlg)
    except Exception:
        pass
    return dlg.exec()
