"""ui/page_aiodos.py — L'onglet « AIODOS » (Cinéma ET Live).

Demande Matthieu (27/10/2026) : « un nouvel onglet AIODOS pour voir les tâches
en cours, les clients qui sont connectés, et quelques réglages », avec le logo
d'AIODOS. Composant NEUTRE, construit par les deux fenêtres (ui/lazy_pages).

  · CONNEXION ET RÉGLAGES — le panneau des Paramètres (ui/aiodos_panel) :
    état, Lancer / Se connecter / Se déconnecter, « Calcul des gabarits » ;
    plus les lieux de calcul demandés à la prochaine connexion ;
  · MACHINES — ce PC et les machines appairées : ComfyUI, modèles, unités en
    cours et faites (core/aiodos_view compose la liste : l'API des
    applications n'a pas de route « pairs ») ;
  · TRAVAUX DE PANDORA — état, avancement, lieu retenu par AIODOS, machines,
    fichiers ; Pause / Reprendre / Annuler / Relancer les échecs / Récupérer /
    Oublier. Les travaux dont des fichiers n'ont jamais été récupérés (PANDORA
    fermé pendant le calcul…) sont listés et signalés : AIODOS ne les efface
    jamais seul. « Oublier » efface alors aussi ces fichiers, et le dit.

Relu toutes les 4 s tant que l'onglet est visible, dans un fil (jamais sur le
fil de l'interface) ; rien n'est demandé à AIODOS quand l'onglet est caché.
"""
from __future__ import annotations

import time

from PyQt6.QtCore import Qt, QThread, QTimer, pyqtSignal
from PyQt6.QtWidgets import (
    QAbstractItemView, QCheckBox, QFrame, QHBoxLayout, QHeaderView, QLabel, QProgressBar,
    QPushButton, QScrollArea, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget,
)

from core.i18n import translate
from ui.styles import CP

REFRESH_MS = 4000

PLACE_LABELS = {"here": "ce PC", "mine": "mes machines", "friend": "ami", "public": "réseau public"}
STATUS_LABELS = {"queued": "en file", "in_progress": "en cours", "pausing": "mise en pause…",
                 "paused": "en pause", "cancelling": "annulation…", "completed": "terminé",
                 "failed": "échoué", "cancelled": "annulé"}
#: Les lieux de calcul que PANDORA demande à la connexion (config `aiodos_where`).
CIRCLES = (("here", "Ce PC"), ("mine", "Mes machines"), ("friends", "Amis"),
           ("public", "Réseau public"))


# ── Fils ──────────────────────────────────────────────────────────────────────

_RUNNING: list = []


def keep_thread(worker: QThread) -> QThread:
    """Garde un fil en vie jusqu'à sa fin. Les fils FINIS sont oubliés au fil
    suivant — jamais dans leur propre signal `finished`, émis alors que le fil
    tourne encore (un QThread détruit en marche fait tomber l'application)."""
    _RUNNING[:] = [t for t in _RUNNING if _alive(t)]
    _RUNNING.append(worker)
    return worker


def _alive(t) -> bool:
    try:
        return t.isRunning()
    except RuntimeError:
        return False


class SnapshotWorker(QThread):
    done = pyqtSignal(object)

    def run(self):
        from core import aiodos_view
        try:
            snap = aiodos_view.snapshot()
        except Exception as e:                     # snapshot() ne lève pas ; par prudence
            snap = {"ready": False, "state": "error", "message": str(e), "machines": [],
                    "jobs": [], "errors": [str(e)]}
        self.done.emit(snap)


class CallWorker(QThread):
    done = pyqtSignal(object)
    failed = pyqtSignal(str)

    def __init__(self, fn):
        super().__init__()
        self._fn = fn

    def run(self):
        try:
            self.done.emit(self._fn())
        except Exception as e:
            self.failed.emit(str(e))


# ── Tableaux partagés (page et panneau du Studio IA) ─────────────────────────

def table_style() -> str:
    return (
        f"QTableWidget{{background:{CP['bg1']};border:1px solid {CP['border']};"
        f"border-radius:8px;color:{CP['text_primary']};font-size:11px;"
        f"gridline-color:transparent;selection-background-color:{CP['bg3']};"
        f"selection-color:{CP['text_primary']};}}"
        f"QHeaderView::section{{background:{CP['bg2']};color:{CP['text_dim']};border:none;"
        f"border-bottom:1px solid {CP['border']};padding:5px 8px;font-size:10px;"
        f"font-weight:700;}}"
        f"QTableWidget::item{{padding:4px 8px;}}")


def make_table(headers: list[str], stretch: int = 0) -> QTableWidget:
    t = QTableWidget(0, len(headers))
    t.setHorizontalHeaderLabels([translate(h) for h in headers])
    t.verticalHeader().setVisible(False)
    t.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
    t.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
    t.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
    t.setShowGrid(False)
    t.setAlternatingRowColors(False)
    t.setStyleSheet(table_style())
    h = t.horizontalHeader()
    for i in range(len(headers)):
        h.setSectionResizeMode(i, QHeaderView.ResizeMode.Stretch if i == stretch
                               else QHeaderView.ResizeMode.ResizeToContents)
    t.verticalHeader().setDefaultSectionSize(28)
    return t


def _cell(text: str, color: str | None = None, tip: str = "") -> QTableWidgetItem:
    it = QTableWidgetItem(text)
    if color:
        it.setForeground(_qcolor(color))
    if tip:
        it.setToolTip(tip)
    return it


def _qcolor(c: str):
    from PyQt6.QtGui import QColor
    return QColor(c)


def machine_state(m: dict) -> tuple[str, str]:
    if m.get("busy") or m.get("running"):
        return translate("calcule"), CP["accent"]
    if m.get("comfy") or m.get("chat_models"):
        return translate("prête"), CP["text_secondary"]
    return translate("connue"), CP["text_dim"]


def fill_machines(table: QTableWidget, machines: list, compact: bool = False) -> None:
    """Machine | Lieu | État | En cours | Faites | ComfyUI | Modèles IA (compact :
    sans les deux dernières colonnes, comme la liste des pairs de BitTorrent)."""
    table.setRowCount(len(machines))
    for r, m in enumerate(machines):
        state, color = machine_state(m)
        name = m.get("name") or "?"
        if m.get("place") == "here":
            name = f"{name}  ({translate('ce PC')})"
        cells = [
            _cell(name, CP["text_primary"]),
            _cell(translate(PLACE_LABELS.get(m.get("place"), m.get("place") or "")),
                  CP["text_secondary"]),
            _cell(("●  " if m.get("busy") else "○  ") + state, color),
            _cell(str(m.get("running") or 0)),
            _cell(str(m.get("done") or 0)),
        ]
        if not compact:
            if m.get("comfy"):
                bits = ["✓"]
                if m.get("comfy_version"):
                    bits.append(str(m["comfy_version"]))
                if m.get("vram_mib"):
                    bits.append(f"{int(m['vram_mib']) / 1024:.0f} Go VRAM")
                if m.get("comfy_models"):
                    bits.append(translate("{n} modèle(s)").format(n=m["comfy_models"]))
                cells.append(_cell("  ·  ".join(bits), CP["text_secondary"]))
            else:
                cells.append(_cell("—", CP["text_dim"]))
            chats = m.get("chat_models") or []
            loaded = set(m.get("loaded") or [])
            text = ", ".join(c + (" ●" if c in loaded else "") for c in chats[:4])
            if len(chats) > 4:
                text += f" +{len(chats) - 4}"
            cells.append(_cell(text or "—", CP["text_secondary"] if chats else CP["text_dim"],
                               "\n".join(chats)))
        for c, it in enumerate(cells):
            table.setItem(r, c, it)


def _when(ts) -> str:
    if not ts:
        return ""
    try:
        lt = time.localtime(float(ts))
    except (TypeError, ValueError, OverflowError):
        return ""
    if time.strftime("%Y%m%d", lt) == time.strftime("%Y%m%d"):
        return time.strftime("%H:%M", lt)
    return time.strftime("%d/%m %H:%M", lt)


JOB_COLUMNS = ["Travail", "État", "Avancement", "Lieu", "Machines", "Fichiers", "Lancé"]


def files_text(j: dict) -> tuple[str, str]:
    """« 2 à récupérer » (en évidence) / « 2 récupéré(s) » / « — »."""
    n, total = int(j.get("unfetched") or 0), int(j.get("files") or 0)
    if n:
        return translate("{n} à récupérer").format(n=n), "#f0b429"
    if total:
        return translate("{n} récupéré(s)").format(n=total), CP["text_dim"]
    return "—", CP["text_dim"]


def fill_jobs(table: QTableWidget, jobs: list) -> None:
    """Travail | État | Avancement | Lieu (retenu par AIODOS) | Machines |
    Fichiers | Lancé."""
    from core.aiodos import places_text
    table.setRowCount(len(jobs))
    for r, j in enumerate(jobs):
        status = j.get("status") or ""
        color = {"completed": CP["accent"], "failed": "#f0b429",
                 "cancelled": CP["text_dim"]}.get(status, CP["text_primary"])
        label = _cell(j.get("label") or j.get("id") or "", CP["text_primary"], j.get("id") or "")
        label.setData(Qt.ItemDataRole.UserRole, j.get("id"))
        table.setItem(r, 0, label)
        table.setItem(r, 1, _cell(translate(STATUS_LABELS.get(status, status)), color))
        bar = QProgressBar()
        bar.setRange(0, 100)
        pct = j.get("percent")
        if pct is None:
            pct = 100 if status == "completed" else 0
        bar.setValue(int(pct))
        bar.setFormat(f"{int(pct)} %" + (f"  ·  {j['message']}" if j.get("message") else ""))
        bar.setFixedHeight(18)
        bar.setStyleSheet(
            f"QProgressBar{{background:{CP['bg2']};border:1px solid {CP['border']};"
            f"border-radius:5px;color:{CP['text_primary']};font-size:9px;text-align:center;}}"
            f"QProgressBar::chunk{{background:{CP['accent_dim']};border-radius:4px;}}")
        table.setCellWidget(r, 2, bar)
        eff = j.get("where_effective") or []
        reason = j.get("where_reason") or ""
        tip = translate("Lieu retenu par AIODOS : {places}").format(places=places_text(eff))
        table.setItem(r, 3, _cell(places_text(eff) if eff else "—", CP["text_secondary"],
                                  tip + (f"\n{reason}" if reason else "")))
        names = [f"{m['name']} ({m['running']}/{m['done']})" for m in j.get("machines") or ()]
        table.setItem(r, 4, _cell(", ".join(names) or "—", CP["text_secondary"]))
        ftext, fcolor = files_text(j)
        table.setItem(r, 5, _cell(ftext, fcolor))
        table.setItem(r, 6, _cell(_when(j.get("created_at")), CP["text_dim"]))


def section_title(text: str) -> QLabel:
    lbl = QLabel(translate(text).upper())
    lbl.setStyleSheet(
        f"color:{CP['accent']};font-size:10px;font-weight:700;letter-spacing:3px;"
        f"font-family:'Consolas',monospace;background:transparent;")
    return lbl


def _card() -> tuple[QFrame, QVBoxLayout]:
    f = QFrame()
    f.setObjectName("aiodosCard")
    f.setStyleSheet(f"QFrame#aiodosCard{{background:{CP['bg1']};border:1px solid {CP['border']};"
                    f"border-radius:10px;}}")
    lay = QVBoxLayout(f)
    lay.setContentsMargins(18, 14, 18, 16)
    lay.setSpacing(10)
    return f, lay


def _btn(text: str) -> QPushButton:
    b = QPushButton(translate(text))
    b.setFixedHeight(30)
    b.setCursor(Qt.CursorShape.PointingHandCursor)
    b.setStyleSheet(
        f"QPushButton{{background:transparent;color:{CP['text_secondary']};"
        f"border:1px solid {CP['border']};border-radius:6px;font-size:11px;"
        f"font-weight:600;padding:0 14px;}}"
        f"QPushButton:hover{{background:{CP['bg3']};color:{CP['text_primary']};}}"
        f"QPushButton:disabled{{color:{CP['text_dim']};border-color:{CP['bg3']};}}")
    return b


def _hint(text: str) -> QLabel:
    lbl = QLabel(translate(text))
    lbl.setWordWrap(True)
    lbl.setStyleSheet(f"color:{CP['text_dim']};font-size:10px;background:transparent;")
    return lbl


# ── La page ───────────────────────────────────────────────────────────────────

class PageAiodos(QScrollArea):
    """L'onglet AIODOS : connexion et réglages, machines, travaux de PANDORA."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWidgetResizable(True)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setStyleSheet(f"QScrollArea{{background:{CP['bg0']};border:none;}}")
        self._snap = None
        self._worker = None
        self._jobs = []

        content = QWidget()
        content.setStyleSheet(f"background:{CP['bg0']};")
        content.setMaximumWidth(1360)
        wrap = QWidget()
        wrap.setStyleSheet(f"background:{CP['bg0']};")
        center = QHBoxLayout(wrap)
        center.setContentsMargins(0, 0, 0, 0)
        center.addStretch(1)
        center.addWidget(content, 4)
        center.addStretch(1)
        self.setWidget(wrap)
        lay = QVBoxLayout(content)
        lay.setContentsMargins(32, 28, 32, 32)
        lay.setSpacing(18)

        # ── Titre ─────────────────────────────────────────────────────────────
        head = QHBoxLayout()
        head.setSpacing(12)
        logo = QLabel()
        logo.setFixedSize(40, 40)
        logo.setStyleSheet("background:transparent;")
        try:
            from ui.icons import load_icon
            pix = load_icon("aiodos.png", 40)
            if not pix.isNull():
                logo.setPixmap(pix)
        except Exception:
            pass
        head.addWidget(logo)
        tcol = QVBoxLayout()
        tcol.setSpacing(2)
        title = QLabel("AIODOS")
        title.setStyleSheet(f"color:{CP['text_primary']};font-size:20px;font-weight:700;"
                            f"letter-spacing:1px;background:transparent;")
        tcol.addWidget(title)
        sub = QLabel(translate("La puissance de calcul mise en commun, par Internet"))
        sub.setStyleSheet(f"color:{CP['text_dim']};font-size:11px;background:transparent;")
        tcol.addWidget(sub)
        head.addLayout(tcol)
        head.addStretch(1)
        self._updated = QLabel("")
        self._updated.setStyleSheet(f"color:{CP['text_dim']};font-size:10px;background:transparent;")
        head.addWidget(self._updated)
        self._btn_open = _btn("Ouvrir AIODOS")
        self._btn_open.clicked.connect(self._open_aiodos)
        head.addWidget(self._btn_open)
        self._btn_refresh = _btn("Actualiser")
        self._btn_refresh.clicked.connect(self.refresh)
        head.addWidget(self._btn_refresh)
        lay.addLayout(head)

        # ── AIODOS pas installé : le présenter et proposer de l'installer ─────
        # (Matthieu 27/10/2026 : « si l'utilisateur a choisi de ne pas installer
        # AIODOS, un message qui présente AIODOS et un bouton pour l'installer »).
        self._intro, il = _card()
        il.addWidget(section_title("Découvrir AIODOS"))
        # Relecture du 28/10/2026 : AIODOS relie D'ABORD des inconnus par Internet ;
        # le réseau local et « mes machines » viennent ensuite.
        intro = QLabel(translate(
            "AIODOS relie par Internet les ordinateurs de personnes qui ne se connaissent "
            "pas, pour mettre leur puissance de calcul en commun ; il relie aussi vos "
            "propres machines, chez vous ou en réseau local. Une fois installé, il prête "
            "par défaut une part de ce PC au réseau public : 60 % de sa puissance au plus, "
            "jamais sur batterie, et tout se coupe dans ses Réglages. Les travaux de "
            "PANDORA, eux, restent là où PANDORA le demande : par défaut ce PC, et une "
            "image de référence ou un clip jamais ailleurs que sur vos machines. Gratuit, "
            "sans abonnement."))
        intro.setWordWrap(True)
        intro.setStyleSheet(f"color:{CP['text_primary']};font-size:12px;background:transparent;")
        il.addWidget(intro)
        irow = QHBoxLayout()
        self._btn_install = _btn("Installer AIODOS")
        self._btn_install.clicked.connect(self._install_aiodos)
        irow.addWidget(self._btn_install)
        irow.addWidget(_hint("Après l'installation, lancez AIODOS puis revenez ici : "
                             "« Se connecter à AIODOS »."), 1)
        il.addLayout(irow)
        self._intro.setVisible(False)
        lay.addWidget(self._intro)

        # ── Connexion et réglages ─────────────────────────────────────────────
        card, cl = _card()
        cl.addWidget(section_title("Connexion et réglages"))
        from ui.aiodos_panel import AiodosPanel
        self.panel = AiodosPanel()
        cl.addWidget(self.panel)
        crow = QHBoxLayout()
        crow.setSpacing(14)
        clbl = QLabel(translate("Lieux de calcul demandés"))
        clbl.setStyleSheet(f"color:{CP['text_secondary']};font-size:12px;background:transparent;")
        crow.addWidget(clbl)
        self._circles = {}
        from core import aiodos
        wanted = set(aiodos.where())
        for key, label in CIRCLES:
            cb = QCheckBox(translate(label))
            cb.setChecked(key in wanted)
            cb.setStyleSheet(f"QCheckBox{{color:{CP['text_primary']};font-size:11px;"
                             f"background:transparent;spacing:6px;}}")
            cb.toggled.connect(self._on_circles)
            crow.addWidget(cb)
            self._circles[key] = cb
        crow.addStretch(1)
        cl.addLayout(crow)
        # AIODOS ne change pas les lieux d'un accès déjà donné (ni le même
        # connect(), ni une demande de droits en plus) : le dire honnêtement.
        cl.addWidget(_hint(
            "Les lieux cochés partent avec la prochaine demande d'accès. Pour changer ceux "
            "d'un accès déjà donné : « Se déconnecter », puis « Se connecter à AIODOS ». "
            "AIODOS calcule aujourd'hui les gabarits ComfyUI sur ce PC et vos machines ; une "
            "image de référence ou un clip ne quitte jamais ce PC et vos machines."))
        self._circles_hint = QLabel("")
        self._circles_hint.setWordWrap(True)
        self._circles_hint.setStyleSheet("color:#f0b429;font-size:10px;background:transparent;")
        self._circles_hint.setVisible(False)
        cl.addWidget(self._circles_hint)
        lay.addWidget(card)

        # ── Machines ──────────────────────────────────────────────────────────
        card, ml = _card()
        mh = QHBoxLayout()
        mh.addWidget(section_title("Machines"))
        mh.addStretch(1)
        self._machines_sum = QLabel("")
        self._machines_sum.setStyleSheet(f"color:{CP['text_dim']};font-size:10px;background:transparent;")
        mh.addWidget(self._machines_sum)
        ml.addLayout(mh)
        self.machines = make_table(["Machine", "Lieu", "État", "En cours", "Faites", "ComfyUI",
                                    "Modèles IA"], stretch=6)
        self.machines.setMinimumHeight(150)
        ml.addWidget(self.machines)
        self._machines_empty = _hint("")
        ml.addWidget(self._machines_empty)
        lay.addWidget(card)

        # ── Travaux de PANDORA ────────────────────────────────────────────────
        card, jl = _card()
        jh = QHBoxLayout()
        jh.addWidget(section_title("Travaux de PANDORA"))
        jh.addStretch(1)
        self._jobs_sum = QLabel("")
        self._jobs_sum.setStyleSheet(f"color:{CP['text_dim']};font-size:10px;background:transparent;")
        jh.addWidget(self._jobs_sum)
        jl.addLayout(jh)
        self.jobs = make_table(JOB_COLUMNS, stretch=0)
        self.jobs.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.jobs.setMinimumHeight(200)
        self.jobs.itemSelectionChanged.connect(self._sync_job_buttons)
        jl.addWidget(self.jobs)
        # Des fichiers jamais récupérés : AIODOS ne les efface jamais seul.
        self._unfetched_note = QLabel("")
        self._unfetched_note.setWordWrap(True)
        self._unfetched_note.setStyleSheet("color:#f0b429;font-size:10px;background:transparent;")
        self._unfetched_note.setVisible(False)
        jl.addWidget(self._unfetched_note)
        brow = QHBoxLayout()
        brow.setSpacing(8)
        self._job_btns = {}
        for action, text in (("pause", "Pause"), ("resume", "Reprendre"), ("cancel", "Annuler"),
                             ("retry", "Relancer les échecs"), ("fetch", "Récupérer"),
                             ("delete", "Oublier")):
            b = _btn(text)
            b.clicked.connect(lambda _c=False, a=action: self._job_action(a))
            brow.addWidget(b)
            self._job_btns[action] = b
        self._job_btns["fetch"].setToolTip(translate(
            "Range les fichiers du travail dans PANDORA/AIODOS, dans le dossier de sortie "
            "de PANDORA."))
        brow.addStretch(1)
        jl.addLayout(brow)
        self._notice = QLabel("")
        self._notice.setWordWrap(True)
        self._notice.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self._notice.setStyleSheet(f"color:{CP['accent']};font-size:10px;background:transparent;")
        self._notice.setVisible(False)
        jl.addWidget(self._notice)
        self._errors = QLabel("")
        self._errors.setWordWrap(True)
        self._errors.setStyleSheet("color:#f0b429;font-size:10px;background:transparent;")
        self._errors.setVisible(False)
        jl.addWidget(self._errors)
        lay.addWidget(card)
        lay.addStretch(1)

        self._timer = QTimer(self)
        self._timer.setInterval(REFRESH_MS)
        self._timer.timeout.connect(self.refresh)
        self.apply_snapshot(None)

    # ── Rafraîchissement (seulement visible) ──────────────────────────────────

    def showEvent(self, event):
        super().showEvent(event)
        self._timer.start()
        QTimer.singleShot(0, self.refresh)

    def hideEvent(self, event):
        super().hideEvent(event)
        self._timer.stop()

    def refresh(self):
        if self._worker is not None and _alive(self._worker):
            return
        w = SnapshotWorker()
        w.done.connect(self._on_snapshot)
        self._worker = keep_thread(w)
        w.start()

    def _on_snapshot(self, snap):
        try:
            self.apply_snapshot(snap)
        except (RuntimeError, AttributeError):                 # page détruite entre-temps
            pass

    def apply_snapshot(self, snap: dict | None):
        """Affiche un relevé de core/aiodos_view (None : rien de lu encore)."""
        from core import aiodos_view
        self._snap = snap
        self._intro.setVisible(bool(snap) and snap.get("state") == "not_installed")
        ready = bool(snap and snap.get("ready"))
        machines = (snap or {}).get("machines") or []
        jobs = (snap or {}).get("jobs") or []
        self._jobs = jobs
        fill_machines(self.machines, machines if ready else [])
        fill_jobs(self.jobs, jobs if ready else [])
        if snap is None:
            empty = translate("Lecture de l'état d'AIODOS…")
        elif not ready:
            empty = (snap.get("message") or "") + "  " + translate(
                "Connectez PANDORA à AIODOS pour voir vos machines et vos travaux.")
        elif not machines:
            empty = translate("Aucune machine ne s'annonce encore : ouvrez ComfyUI ou un modèle "
                              "de conversation dans AIODOS, sur ce PC ou une machine appairée.")
        else:
            empty = ""
        self._machines_empty.setText(empty.strip())
        self._machines_empty.setVisible(bool(empty.strip()))
        self._machines_sum.setText(aiodos_view.summary(snap or {}) if ready else "")
        active = sum(1 for j in jobs if j.get("status") in aiodos_view.ACTIVE)
        self._jobs_sum.setText(translate("{n} en cours · {m} au total").format(n=active, m=len(jobs))
                               if ready else "")
        left = ((snap or {}).get("unfetched") or {}) if ready else {}
        if left.get("jobs"):
            self._unfetched_note.setText(translate(
                "{n} travail(s) ont des fichiers jamais récupérés ({size}) — PANDORA fermé "
                "pendant le calcul, par exemple. AIODOS ne les efface jamais seul : "
                "choisissez-les, puis « Récupérer » ou « Oublier », sinon sa réserve finit "
                "par se remplir.").format(n=left["jobs"],
                                          size=aiodos_view.size_text(left.get("bytes") or 0)))
        self._unfetched_note.setVisible(bool(left.get("jobs")))
        errs = (snap or {}).get("errors") or []
        self._errors.setText("\n".join(errs))
        self._errors.setVisible(bool(errs))
        self._btn_open.setEnabled(ready)
        if snap is not None:
            self._updated.setText(translate("à jour à {t}").format(
                t=time.strftime("%H:%M:%S", time.localtime(snap.get("at") or time.time()))))
        self._update_circles_hint()
        self._sync_job_buttons()

    # ── Actions ───────────────────────────────────────────────────────────────

    def _selected_job(self) -> dict | None:
        rows = self.jobs.selectionModel().selectedRows() if self.jobs.selectionModel() else []
        if not rows:
            return None
        item = self.jobs.item(rows[0].row(), 0)
        jid = item.data(Qt.ItemDataRole.UserRole) if item else None
        return next((j for j in self._jobs if j.get("id") == jid), None)

    def _sync_job_buttons(self):
        j = self._selected_job()
        status = (j or {}).get("status") or ""
        allowed = {
            "pause": status in ("queued", "in_progress"),
            "resume": status in ("paused", "pausing"),
            "cancel": status in ("queued", "in_progress", "paused", "pausing"),
            "retry": bool(j) and int(j.get("failed") or 0) > 0,
            "fetch": bool(j) and int(j.get("unfetched") or 0) > 0,
            "delete": status in ("completed", "failed", "cancelled"),
        }
        for action, b in self._job_btns.items():
            b.setEnabled(bool(allowed.get(action)))

    def _job_action(self, action: str):
        j = self._selected_job()
        if not j:
            return
        from core import aiodos_view
        unfetched = int(j.get("unfetched") or 0)
        if action == "delete" and unfetched:
            # Oublier efface AUSSI les fichiers jamais récupérés (files=True) :
            # sinon AIODOS les garderait sans fin. Le dire, et laisser le choix.
            from PyQt6.QtWidgets import QMessageBox
            ans = QMessageBox.question(
                self, translate("Oublier ce travail ?"),
                translate("Ce travail a {n} fichier(s) jamais récupéré(s). L'oublier les "
                          "efface aussi dans AIODOS (sinon ils y resteraient sans fin). "
                          "« Récupérer » d'abord si vous les voulez.\n\nOublier ce travail "
                          "et effacer ces fichiers ?").format(n=unfetched))
            if ans != QMessageBox.StandardButton.Yes:
                return
        if action == "fetch":
            self._show_notice(translate("Récupération des fichiers…"))

        def call():
            if action == "fetch":
                return action, aiodos_view.fetch(j["id"])
            return action, aiodos_view.job_action(j["id"], action)
        w = CallWorker(call)
        w.done.connect(self._on_action_done)
        w.failed.connect(self._on_action_failed)
        keep_thread(w).start()

    def _on_action_done(self, result):
        try:
            action, value = result
            if action == "fetch":
                folder, n = value
                self._show_notice(translate("{n} fichier(s) récupéré(s) dans {folder}").format(
                    n=n, folder=folder))
                from PyQt6.QtCore import QUrl
                from PyQt6.QtGui import QDesktopServices
                QDesktopServices.openUrl(QUrl.fromLocalFile(folder))
            elif action == "delete":
                self._show_notice(
                    translate("Travail oublié ; {n} fichier(s) jamais récupéré(s) effacé(s) "
                              "dans AIODOS.").format(n=value) if value
                    else translate("Travail oublié."))
            self.refresh()
        except (RuntimeError, AttributeError, TypeError, ValueError):
            pass

    def _show_notice(self, text: str):
        try:
            self._errors.setVisible(False)
            self._notice.setText(text)
            self._notice.setVisible(bool(text))
        except (RuntimeError, AttributeError):
            pass

    def _on_action_failed(self, msg: str):
        try:
            self._notice.setVisible(False)
            self._errors.setText(msg)
            self._errors.setVisible(True)
        except (RuntimeError, AttributeError):
            pass

    def _install_aiodos(self):
        from PyQt6.QtCore import QUrl
        from PyQt6.QtGui import QDesktopServices
        from core import aiodos
        QDesktopServices.openUrl(QUrl(aiodos.DOWNLOAD_URL))

    def _open_aiodos(self):
        from core import aiodos_view
        keep_thread(CallWorker(lambda: aiodos_view.open_aiodos("jobs"))).start()

    def _on_circles(self, _on: bool):
        """Les lieux demandés à la PROCHAINE connexion (config `aiodos_where`). Au
        moins un : décocher le dernier le remet."""
        chosen = [k for k, cb in self._circles.items() if cb.isChecked()]
        if not chosen:
            self._circles["here"].blockSignals(True)
            self._circles["here"].setChecked(True)
            self._circles["here"].blockSignals(False)
            chosen = ["here"]
        try:
            from core.config import load_config, save_config
            cfg = load_config()                  # save_config remplace tout le fichier
            before = cfg.get("aiodos_where") or []
            if cfg.get("aiodos_where") != chosen:
                cfg["aiodos_where"] = chosen
                # Réseau public coché → c'est lui que « Calcul » propose (Matthieu
                # 27/10/2026) ; décoché alors qu'il était choisi → mes machines.
                from core import aiodos
                mode = cfg.get(aiodos.COMPUTE_KEY)
                if "public" in chosen and "public" not in before:
                    cfg[aiodos.COMPUTE_KEY] = aiodos.COMPUTE_PUBLIC
                elif "public" not in chosen and mode == aiodos.COMPUTE_PUBLIC:
                    cfg[aiodos.COMPUTE_KEY] = aiodos.COMPUTE_AIODOS
                save_config(cfg)
                from ui.comfy_choice import hub
                hub.compute_changed.emit(aiodos.compute_mode())
        except Exception:
            pass
        self._circles_touched = True
        PageAiodos._update_circles_hint(self)

    def _update_circles_hint(self):
        """Lieux cochés ≠ lieux de l'accès déjà donné (après un changement fait
        ici) : AIODOS ne les change pas sans nouvel accès — le dire."""
        hint = getattr(self, "_circles_hint", None)
        circles = getattr(self, "_circles", None)
        if hint is None or not circles:
            return
        from types import SimpleNamespace
        from core import aiodos
        snap = getattr(self, "_snap", None) or {}
        chosen = [k for k, cb in circles.items() if cb.isChecked()]
        differs = bool(getattr(self, "_circles_touched", False)) and aiodos.where_differs(
            chosen, SimpleNamespace(state=snap.get("state"), where=snap.get("where") or ()))
        try:
            hint.setText(translate(
                "Lieux changés : « Se déconnecter », puis « Se connecter à AIODOS » pour les "
                "appliquer. D'ici là, AIODOS garde ceux de l'accès déjà donné ({places})."
            ).format(places=aiodos.places_text(snap.get("where") or ())) if differs else "")
            hint.setVisible(differs)
        except (RuntimeError, AttributeError):
            pass
