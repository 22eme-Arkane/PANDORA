from PyQt6.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QLabel, QPushButton, QMessageBox,
    QSizePolicy,
)
from PyQt6.QtCore import pyqtSignal, Qt
from ui.styles import C
from core.i18n import translate
from davinci.bridge import resolve, EXPECTED_BRIDGE, translated as _translate_lines
from davinci.ping_worker import BridgePingWorker
from davinci import jobs, scripts_install


class DaVinciPanel(QWidget):
    """Connexion au pont DaVinci Resolve + état des scripts installés.

    Version 2 (04/10/2026) : la connexion ne bloque plus l'interface, l'état
    affiché vient du pont lui-même (version, API, projet), et le bouton
    « Installer / mettre à jour les scripts » revient — l'installeur ne copiait
    les scripts que si Resolve était déjà installé, sans moyen de réparer."""

    status_changed = pyqtSignal(bool)

    def __init__(self):
        super().__init__()
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        self.setStyleSheet("background:transparent;")
        self._was_connected = False

        root = QVBoxLayout(self)
        root.setContentsMargins(16, 12, 16, 12)
        root.setSpacing(8)

        # ── Ligne principale : voyant + titre + bouton + état ─────────────────
        r1 = QHBoxLayout()
        r1.setSpacing(10)
        self._dot = QLabel("●")
        self._dot.setFixedSize(20, 20)
        self._dot.setAlignment(Qt.AlignmentFlag.AlignCenter)
        r1.addWidget(self._dot)

        self._title_lbl = QLabel("DaVinci Resolve")
        self._title_lbl.setStyleSheet(
            f"color:{C['text_primary']};font-size:14px;font-weight:700;"
            f"border:none;background:transparent;"
        )
        r1.addWidget(self._title_lbl)

        self._btn = QPushButton(translate("Connecter"))
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

        self._status_chip = QLabel()
        r1.addWidget(self._status_chip)
        r1.addStretch(1)
        root.addLayout(r1)

        # ── Instructions (visibles tant que le pont ne répond pas) ────────────
        self._instructions_w = QWidget()
        self._instructions_w.setStyleSheet("background:transparent;")
        ins = QVBoxLayout(self._instructions_w)
        ins.setContentsMargins(30, 0, 0, 4)
        ins.setSpacing(4)
        _hint = (f"color:{C['text_secondary']};font-size:10px;font-family:'Consolas',monospace;"
                 f"background:transparent;border:none;")
        for text in ("1.  Dans DaVinci : Espace de travail → Scripts → seedance_bridge",
                     "2.  Revenez ici et cliquez sur « Connecter » →"):
            step = QLabel(translate(text))
            step.setStyleSheet(_hint)
            ins.addWidget(step)
        root.addWidget(self._instructions_w)

        # ── Détail de la connexion (timeline, version du pont, Resolve) ───────
        self._subtitle_lbl = QLabel("")
        self._subtitle_lbl.setWordWrap(True)
        self._subtitle_lbl.setStyleSheet(
            f"color:{C['text_dim']};font-size:10px;font-family:'Consolas',monospace;"
            f"background:transparent;border:none;"
        )
        self._subtitle_lbl.setContentsMargins(30, 0, 0, 0)
        root.addWidget(self._subtitle_lbl)

        # ── Scripts installés dans Resolve ────────────────────────────────────
        r3 = QHBoxLayout()
        r3.setContentsMargins(30, 4, 0, 0)
        r3.setSpacing(10)
        self._scripts_lbl = QLabel("")
        self._scripts_lbl.setWordWrap(True)
        r3.addWidget(self._scripts_lbl, 1)
        self._btn_install = QPushButton(translate("Installer / mettre à jour les scripts"))
        self._btn_install.setFixedHeight(28)
        self._btn_install.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_install.setToolTip(translate(
            "Copie seedance_bridge et pandora_send dans le dossier Scripts de "
            "DaVinci Resolve (sans droits administrateur si possible)."))
        self._btn_install.setStyleSheet(
            f"QPushButton{{background:transparent;color:{C['accent']};"
            f"border:1px solid {C['accent_dim']};border-radius:6px;"
            f"font-size:10px;font-weight:700;padding:0 12px;}}"
            f"QPushButton:hover{{background:rgba(78,205,196,0.12);}}"
        )
        self._btn_install.clicked.connect(self._on_install)
        r3.addWidget(self._btn_install)
        root.addLayout(r3)

        jobs.hub().changed.connect(self._refresh_ui)
        self._refresh_scripts()
        self._refresh_ui()

        # Ping unique au démarrage, hors interface — pas de timer récurrent
        self._ping_worker: BridgePingWorker | None = None
        self._auto_ping()

    # ── Connexion ─────────────────────────────────────────────────────────────

    def _on_connect(self):
        self._btn.setEnabled(False)
        self._btn.setText("…")
        jobs.run_job(resolve.connect, self._on_connect_done)

    def _on_connect_done(self, res):
        self._btn.setEnabled(True)
        ok, msg = res if isinstance(res, tuple) else (False, str((res or {}).get("error", "")))
        jobs.notify()
        self._refresh_ui()
        if not ok:
            QMessageBox.warning(self, translate("DaVinci — Connexion impossible"),
                                _translate_lines(msg))
        elif msg:
            QMessageBox.information(self, translate("DaVinci Resolve"), _translate_lines(msg))

    def _refresh_ui(self):
        """Affiche l'état EN CACHE (aucun appel réseau ici)."""
        connected = resolve._connected
        if connected and resolve.outdated:
            color, chip = C["orange"], translate("— pont à mettre à jour")
        elif connected and not resolve.api_ok:
            color, chip = C["orange"], translate("— API DaVinci indisponible")
        elif connected:
            color, chip = C["green"], "— " + (resolve.project or translate("Connecté"))
        else:
            color, chip = C["red"], translate("— Non connecté")
        self._dot.setStyleSheet(f"color:{color};font-size:15px;border:none;background:transparent;")
        self._status_chip.setText(chip)
        self._status_chip.setStyleSheet(
            f"color:{color};font-size:12px;font-weight:600;border:none;background:transparent;")
        self._btn.setText(translate("Actualiser") if connected else translate("Connecter"))
        self._instructions_w.setVisible(not connected)
        if connected:
            bits = [resolve.timeline or translate("Aucune timeline ouverte")]
            if resolve.bridge_version:
                bits.append(translate("pont") + f" v{resolve.bridge_version}")
            if resolve.product_label:
                bits.append(resolve.product_label)
            self._subtitle_lbl.setText("  ·  ".join(bits))
        self._subtitle_lbl.setVisible(connected)
        if connected != self._was_connected:
            self._was_connected = connected
            self.status_changed.emit(connected)

    def is_connected(self) -> bool:
        return resolve.is_connected()

    # ── Scripts installés ─────────────────────────────────────────────────────

    def _refresh_scripts(self):
        try:
            st = scripts_install.status()
        except Exception:
            st = {"state": "absent", "copies": [], "resolve": False}
        state = st.get("state")
        if state == "ok":
            text = translate("Scripts PANDORA dans Resolve : à jour") + f" (v{EXPECTED_BRIDGE})"
            color = C["text_dim"]
        elif state == "outdated":
            old = min((c["version"] for c in st.get("copies", [])
                       if c["name"] == scripts_install.BRIDGE_FILE), default=0)
            text = translate("Scripts PANDORA dans Resolve : à mettre à jour") + \
                (f" (v{old} → v{EXPECTED_BRIDGE})" if old else "")
            color = C["orange"]
        elif not st.get("resolve"):
            text = translate("DaVinci Resolve n'est pas détecté sur ce poste.")
            color = C["text_dim"]
        else:
            text = translate("Scripts PANDORA non installés dans Resolve.")
            color = C["orange"]
        self._scripts_lbl.setText(text)
        self._scripts_lbl.setStyleSheet(
            f"color:{color};font-size:10px;background:transparent;border:none;")

    def _on_install(self):
        res = scripts_install.install()
        self._refresh_scripts()
        if res.get("no_resolve"):
            QMessageBox.warning(self, translate("DaVinci Resolve introuvable"), translate(
                "DaVinci Resolve n'est pas détecté sur ce poste. Installez-le, "
                "lancez-le une fois, puis recommencez."))
            return
        if res.get("missing_source"):
            QMessageBox.warning(self, translate("Installation impossible"),
                                translate("Script introuvable dans PANDORA :") + " "
                                + res["missing_source"])
            return
        lines = []
        if res.get("written"):
            lines.append(translate("Scripts installés dans :"))
            lines += ["  " + d for d in res["written"]]
        if res.get("failed"):
            lines.append("")
            lines.append(translate("Écriture impossible dans :"))
            lines += [f"  {d} ({e})" for d, e in res["failed"]]
        lines.append("")
        if res.get("new"):
            lines.append(translate(
                "Redémarrez DaVinci Resolve : il ne liste les nouveaux scripts qu'à son "
                "démarrage. Ensuite : Espace de travail → Scripts → seedance_bridge."))
        else:
            lines.append(translate(
                "Si le pont tourne déjà dans Resolve, fermez sa fenêtre « PANDORA Bridge » "
                "puis relancez Espace de travail → Scripts → seedance_bridge."))
        box = QMessageBox.information if res.get("ok") else QMessageBox.warning
        box(self, translate("Scripts DaVinci"), "\n".join(lines))

    # ── Ping automatique ──────────────────────────────────────────────────────

    def _auto_ping(self):
        """Lance un ping asynchrone si aucun n'est en cours."""
        if self._ping_worker and self._ping_worker.isRunning():
            return
        self._ping_worker = BridgePingWorker()
        self._ping_worker.result.connect(self._on_auto_ping_result)
        self._ping_worker.start()

    def _on_auto_ping_result(self, connected: bool, timeline_name: str):
        self._refresh_ui()
