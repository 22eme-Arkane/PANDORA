from PyQt6.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QLabel, QPushButton, QMessageBox,
    QSizePolicy,
)
from PyQt6.QtCore import pyqtSignal, Qt
from ui.styles import C
from davinci.bridge import resolve
from davinci.ping_worker import BridgePingWorker


class DaVinciPanel(QWidget):
    """Barre de statut + connexion DaVinci Resolve."""

    status_changed = pyqtSignal(bool)

    def __init__(self):
        super().__init__()
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        self.setStyleSheet(f"background:transparent;")

        root = QVBoxLayout(self)
        root.setContentsMargins(16, 12, 16, 12)
        root.setSpacing(8)

        # ── Ligne principale : icône + titre + bouton ─────────────────────────
        r1 = QHBoxLayout()
        r1.setSpacing(10)

        self._dot = QLabel("●")
        self._dot.setFixedSize(20, 20)
        self._dot.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._dot.setStyleSheet(f"color:{C['red']};font-size:15px;border:none;background:transparent;")
        r1.addWidget(self._dot)

        self._title_lbl = QLabel("DaVinci Resolve Studio")
        self._title_lbl.setStyleSheet(
            f"color:{C['text_primary']};font-size:14px;font-weight:700;"
            f"border:none;background:transparent;"
        )
        r1.addWidget(self._title_lbl)

        self._btn = QPushButton("Connecter")
        self._btn.setFixedHeight(30)
        self._btn.setMinimumWidth(100)
        self._btn.setStyleSheet(f"""
            QPushButton{{
                background:{C['accent_dim']};color:#ffffff;
                border:none;border-radius:6px;
                font-size:11px;font-weight:700;padding:0 14px;
            }}
            QPushButton:hover{{background:{C['accent']};}}
            QPushButton:disabled{{background:{C['bg3']};color:{C['text_dim']};}}
        """)
        self._btn.clicked.connect(self._on_connect)
        r1.addWidget(self._btn)

        self._status_chip = QLabel("— Non connecté")
        self._status_chip.setStyleSheet(
            f"color:{C['red']};font-size:12px;font-weight:600;"
            f"border:none;background:transparent;"
        )
        r1.addWidget(self._status_chip)

        r1.addStretch(1)
        root.addLayout(r1)

        # ── Instructions de connexion (visible uniquement quand non connecté) ─
        self._instructions_w = QWidget()
        self._instructions_w.setStyleSheet("background:transparent;")
        ins = QVBoxLayout(self._instructions_w)
        ins.setContentsMargins(30, 0, 0, 4)
        ins.setSpacing(4)

        _red = (
            f"color:{C['red']};font-size:10px;font-family:'Consolas',monospace;"
            f"background:transparent;border:none;"
        )

        # Le bridge PANDORA est installé AUTOMATIQUEMENT à l'installation de PANDORA
        # (le bouton d'installation manuelle a été retiré).
        step1 = QLabel("1.  Dans DaVinci : Espace de travail → Scripts → seedance_bridge")
        step1.setStyleSheet(_red)
        ins.addWidget(step1)

        step2 = QLabel("2.  Revenez ici et cliquez sur « Connecter » →")
        step2.setStyleSheet(_red)
        ins.addWidget(step2)

        root.addWidget(self._instructions_w)

        # ── Infos de connexion (visible uniquement quand connecté) ────────────
        self._subtitle_lbl = QLabel("")
        self._subtitle_lbl.setStyleSheet(
            f"color:{C['text_dim']};font-size:10px;font-family:'Consolas',monospace;"
            f"background:transparent;border:none;"
        )
        self._subtitle_lbl.setContentsMargins(30, 0, 0, 0)
        root.addWidget(self._subtitle_lbl)

        self._refresh_ui()

        # Ping unique au démarrage — pas de timer récurrent
        self._ping_worker: BridgePingWorker | None = None
        self._auto_ping()

    def _on_connect(self):
        if resolve.is_connected():
            resolve.refresh()
            self._refresh_ui()
            dvr_err = resolve.get_dvr_error()
            if dvr_err:
                QMessageBox.warning(
                    self, "DaVinci — Studio requis pour le scripting",
                    "Le bridge TCP est actif mais le scripting DaVinci ne répond pas.\n\n"
                    "Cette fonctionnalité nécessite DaVinci Resolve Studio.\n\n"
                    "La génération de clips fonctionne normalement.\n"
                    "L'import automatique dans le Media Pool et la lecture\n"
                    "des clips DaVinci seront actifs avec la version Studio."
                )
        else:
            self._btn.setEnabled(False)
            self._btn.setText("…")
            ok, err = resolve.connect()
            self._btn.setEnabled(True)
            self._refresh_ui()
            self.status_changed.emit(ok)
            if not ok:
                QMessageBox.warning(self, "DaVinci — Connexion impossible", err)

    def _refresh_ui(self):
        connected = resolve.is_connected()
        if connected:
            proj = resolve.project_name() or "Connecté"
            tl   = resolve.timeline_name()
            self._dot.setStyleSheet(
                f"color:{C['green']};font-size:15px;border:none;background:transparent;"
            )
            self._status_chip.setText(f"— {proj}")
            self._status_chip.setStyleSheet(
                f"color:{C['green']};font-size:12px;font-weight:600;"
                f"border:none;background:transparent;"
            )
            self._btn.setText("Actualiser")
            self._instructions_w.setVisible(False)
            self._subtitle_lbl.setText(tl or "Aucune timeline ouverte")
            self._subtitle_lbl.setVisible(True)
        else:
            self._dot.setStyleSheet(
                f"color:{C['red']};font-size:15px;border:none;background:transparent;"
            )
            self._status_chip.setText("— Non connecté")
            self._status_chip.setStyleSheet(
                f"color:{C['red']};font-size:12px;font-weight:600;"
                f"border:none;background:transparent;"
            )
            self._btn.setText("Connecter")
            self._instructions_w.setVisible(True)
            self._subtitle_lbl.setVisible(False)

    def is_connected(self) -> bool:
        return resolve.is_connected()

    # ── Polling automatique ───────────────────────────────────────────────────

    def _auto_ping(self):
        """Lance un ping asynchrone si aucun n'est en cours."""
        if self._ping_worker and self._ping_worker.isRunning():
            return
        self._ping_worker = BridgePingWorker()
        self._ping_worker.result.connect(self._on_auto_ping_result)
        self._ping_worker.start()

    def _on_auto_ping_result(self, connected: bool, timeline_name: str):
        was_connected = resolve._connected
        resolve._connected = connected
        if connected != was_connected:
            # État changé → mettre à jour l'UI et émettre le signal
            self._refresh_ui()
            self.status_changed.emit(connected)
        elif connected:
            # Toujours connecté → mettre à jour juste la timeline si elle a changé
            tl_text = timeline_name or "Aucune timeline ouverte"
            if self._subtitle_lbl.text() != tl_text:
                self._subtitle_lbl.setText(tl_text)
