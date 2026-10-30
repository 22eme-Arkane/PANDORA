"""ui/aiodos_peers_panel.py — Les machines d'AIODOS, en bas du Studio IA.

Demande Matthieu (27/10/2026) : « si on utilise AIODOS dans le Studio IA à la
place de Seedance 2.0, il faut qu'on voie en bas, comme un panneau pliable et
dépliable, les personnes qui sont connectées, comme les clients de BitTorrent ».

Composant NEUTRE, posé sous les onglets du Studio IA Cinéma (ui/seedance_widget)
et Live (ui/live_studio_widget). Il n'existe que quand le calcul des gabarits
ComfyUI passe par AIODOS (réglage « Calcul : Mes machines · AIODOS ») :

  · en-tête cliquable : « AIODOS · MACHINES CONNECTÉES » et, à droite,
    « 3 machine(s) · 1 travail(s) en cours » — lisible même replié ;
  · déplié : une ligne par machine, comme la liste des pairs d'un torrent
    (machine, lieu, état, unités en cours, faites), et le travail en cours
    avec son avancement.

Relu (core/aiodos_view, dans un fil) toutes les 3 s seulement déplié ET
visible ; toutes les 10 s replié, ou la fenêtre cachée ou réduite ; jamais
pendant un envoi vers AIODOS (core/comfy_aiodos.sending). Un relevé coûte
environ quatre requêtes à clé, sur les 120 par minute permises à une appli
(relecture du 28/10/2026 : à 3 s en continu, un envoi risquait `rate_limited`).
L'état replié / déplié est retenu pour la session.
"""
from __future__ import annotations

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtWidgets import QFrame, QHBoxLayout, QLabel, QProgressBar, QPushButton, QVBoxLayout, QWidget

from core.i18n import translate
from ui.styles import CP

REFRESH_MS = 3000          # déplié et visible
REFRESH_IDLE_MS = 10000    # replié, ou fenêtre cachée / réduite
_OPEN = {"open": False}   # replié par défaut (27/10/2026)


class AiodosPeersPanel(QFrame):
    """Panneau pliable des machines d'AIODOS (Studio IA)."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("aiodosPeers")
        self.setStyleSheet(f"QFrame#aiodosPeers{{background:{CP['bg1']};"
                           f"border-top:1px solid {CP['border']};}}")
        # Jamais plus haut que son contenu (Matthieu 29/10/2026 : déplié, il prenait
        # la moitié du Studio IA pour une ligne « Aucun travail en cours »).
        from PyQt6.QtWidgets import QSizePolicy
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Maximum)
        self._worker = None
        self._snap = None
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)

        self._header = QPushButton()
        self._header.setObjectName("aiodosPeersHeader")
        self._header.setCursor(Qt.CursorShape.PointingHandCursor)
        self._header.setFixedHeight(32)
        self._header.setStyleSheet(
            "QPushButton#aiodosPeersHeader{background:transparent;border:none;text-align:left;}"
            f"QPushButton#aiodosPeersHeader:hover{{background:{CP['bg2']};}}")
        hl = QHBoxLayout(self._header)
        hl.setContentsMargins(14, 0, 14, 0)
        hl.setSpacing(8)
        self._arrow = QLabel()
        self._logo = QLabel()
        self._logo.setFixedSize(16, 16)
        try:
            from ui.icons import load_icon
            pix = load_icon("aiodos.png", 16)
            if not pix.isNull():
                self._logo.setPixmap(pix)
        except Exception:
            pass
        self._title = QLabel(translate("AIODOS · machines connectées").upper())
        self._summary = QLabel("")
        for w in (self._arrow, self._logo, self._title, self._summary):
            w.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self._arrow.setStyleSheet(f"color:{CP['accent']};font-size:9px;background:transparent;")
        self._title.setStyleSheet(
            f"color:{CP['accent']};font-size:10px;font-weight:700;letter-spacing:2px;"
            f"font-family:'Consolas',monospace;background:transparent;")
        self._summary.setStyleSheet(f"color:{CP['text_dim']};font-size:10px;background:transparent;")
        # Titre CENTRÉ (Matthieu 27/10/2026 : « tout est centré dans
        # l'application, c'est bizarre d'avoir quelque chose sur le côté gauche ») ;
        # l'état suit juste après lui.
        hl.addStretch(1)
        hl.addWidget(self._arrow)
        hl.addWidget(self._logo)
        hl.addWidget(self._title)
        hl.addSpacing(14)
        hl.addWidget(self._summary)
        hl.addStretch(1)
        self._header.clicked.connect(self.toggle)
        lay.addWidget(self._header)

        self._body = QWidget()
        self._body.setStyleSheet("background:transparent;")
        bl = QVBoxLayout(self._body)
        bl.setContentsMargins(14, 0, 14, 10)
        bl.setSpacing(6)
        jrow = QHBoxLayout()
        jrow.setSpacing(10)
        self._job_lbl = QLabel("")
        self._job_lbl.setStyleSheet(f"color:{CP['text_secondary']};font-size:10px;background:transparent;")
        jrow.addWidget(self._job_lbl, 1)
        self._job_bar = QProgressBar()
        self._job_bar.setRange(0, 100)
        self._job_bar.setFixedSize(220, 14)
        self._job_bar.setStyleSheet(
            f"QProgressBar{{background:{CP['bg2']};border:1px solid {CP['border']};"
            f"border-radius:4px;color:{CP['text_primary']};font-size:8px;text-align:center;}}"
            f"QProgressBar::chunk{{background:{CP['accent_dim']};border-radius:3px;}}")
        jrow.addWidget(self._job_bar)
        bl.addLayout(jrow)
        from ui.page_aiodos import make_table
        self.table = make_table(["Machine", "Lieu", "État", "En cours", "Faites"], stretch=0)
        self._fit_table(0)      # hauteur réglée sur le nombre de machines (_fit_table)
        bl.addWidget(self.table)
        self._empty = QLabel("")
        self._empty.setWordWrap(True)
        self._empty.setStyleSheet(f"color:{CP['text_dim']};font-size:10px;background:transparent;")
        bl.addWidget(self._empty)
        lay.addWidget(self._body)

        self._timer = QTimer(self)
        self._timer.setInterval(REFRESH_IDLE_MS)
        self._timer.timeout.connect(self.refresh)
        self.set_open(_OPEN["open"])
        self.apply_snapshot(None)
        from ui.comfy_choice import hub
        hub.compute_changed.connect(self._on_compute)
        self._on_compute()

    # ── Présence : seulement quand le calcul passe par AIODOS ────────────────

    def _on_compute(self, *_a):
        try:
            from core import comfy_aiodos
            enabled = comfy_aiodos.enabled()
            if enabled and self.parentWidget() is None:
                return          # pas encore rangé : ne jamais devenir une fenêtre à part
            self.setVisible(enabled)
        except (RuntimeError, AttributeError):                 # panneau détruit
            pass

    def set_open(self, open_: bool):
        _OPEN["open"] = bool(open_)
        self._body.setVisible(bool(open_))
        self._arrow.setText("▼" if open_ else "▶")
        self._retime()

    def toggle(self):
        self.set_open(not _OPEN["open"])
        if _OPEN["open"] and self.isVisible():
            QTimer.singleShot(0, self.refresh)        # déplié : un relevé frais tout de suite

    def is_open(self) -> bool:
        return _OPEN["open"]

    def _fit_table(self, rows: int):
        """Table à la hauteur de ses lignes (5 au plus, puis défilement) : plus de
        grand vide sous une seule machine."""
        t = self.table
        # isHidden() et non isVisible() : avant le premier affichage, tout est « invisible »
        head = 0 if t.horizontalHeader().isHidden() else t.horizontalHeader().sizeHint().height()
        row = t.verticalHeader().defaultSectionSize()
        t.setFixedHeight(head + row * max(1, min(5, rows)) + 2 * t.frameWidth() + 2)

    # ── Rafraîchissement ──────────────────────────────────────────────────────

    def interval(self) -> int:
        """3 s déplié et visible (fenêtre montrée, pas réduite) ; 10 s sinon."""
        try:
            win = self.window()
            shown = (self.isVisible() and win is not None and win.isVisible()
                     and not win.isMinimized())
        except RuntimeError:                                   # panneau détruit
            return REFRESH_IDLE_MS
        return REFRESH_MS if (_OPEN["open"] and shown) else REFRESH_IDLE_MS

    def _retime(self):
        timer = getattr(self, "_timer", None)
        if timer is None:
            return
        ms = self.interval()
        if timer.interval() != ms:
            timer.setInterval(ms)          # relancé au nouveau rythme s'il tournait

    def showEvent(self, event):
        super().showEvent(event)
        self._retime()
        self._timer.start()
        QTimer.singleShot(0, self.refresh)

    def hideEvent(self, event):
        super().hideEvent(event)
        self._timer.stop()

    def refresh(self):
        from ui.page_aiodos import SnapshotWorker, _alive, keep_thread
        self._retime()                     # la fenêtre a pu être réduite ou rendue
        try:
            from core import comfy_aiodos
            if comfy_aiodos.sending():
                return                     # un envoi en cours : pas de relecture
        except Exception:
            pass
        if self._worker is not None and _alive(self._worker):
            return
        w = SnapshotWorker()
        w.done.connect(self._on_snapshot)
        self._worker = keep_thread(w)
        w.start()

    def _on_snapshot(self, snap):
        try:
            self.apply_snapshot(snap)
        except (RuntimeError, AttributeError):
            pass

    def apply_snapshot(self, snap: dict | None):
        from core import aiodos_view
        from ui.page_aiodos import fill_machines
        self._snap = snap
        ready = bool(snap and snap.get("ready"))
        machines = (snap or {}).get("machines") or [] if ready else []
        fill_machines(self.table, machines, compact=True)
        self._fit_table(len(machines))
        self._summary.setText(aiodos_view.summary(snap) if snap else "")
        active = [j for j in (snap or {}).get("jobs") or () if j.get("status") in aiodos_view.ACTIVE]
        if ready and active:
            j = active[0]
            pct = j.get("percent")
            eff = j.get("where_effective") or []
            from core.aiodos import places_text
            self._job_lbl.setText(translate("Travail en cours : {label}").format(label=j.get("label") or "")
                                  + (f"  ·  {j['message']}" if j.get("message") else "")
                                  + ("  ·  " + translate("lieu retenu : {places}").format(
                                      places=places_text(eff)) if eff else ""))
            self._job_lbl.setToolTip(str(j.get("where_reason") or ""))
            self._job_bar.setValue(int(pct or 0))
            self._job_bar.setFormat(f"{int(pct or 0)} %")
            self._job_bar.setVisible(True)
        else:
            self._job_lbl.setText(translate("Aucun travail en cours.") if ready else "")
            self._job_bar.setVisible(False)
        if snap is None:
            empty = translate("Lecture de l'état d'AIODOS…")
        elif not ready:
            empty = (snap.get("message") or "") + "  " + translate("Paramètres → AIODOS.")
        elif not machines:
            empty = translate("Aucune machine ne s'annonce encore.")
        else:
            empty = ""
        self._empty.setText(empty.strip())
        self._empty.setVisible(bool(empty.strip()))
        self.table.setVisible(bool(machines))
        # Replié par défaut et JAMAIS ouvert de lui-même (Matthieu 29/10/2026 :
        # « il reste plié même si une machine se connecte, sinon il se déplierait
        # à chaque connexion ; libre à l'utilisateur de le déplier »). L'en-tête,
        # lisible replié, donne déjà le nombre de machines et de travaux.
