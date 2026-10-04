"""
ui/distrib_settings_panel.py — Section « Distribution des vidéos » des
Paramètres, commune aux deux éditions (04/10/2026).

Ce qu'elle réunit, autrefois éparpillé entre « Paramètres avancés — moteur IA
par tâche » (le choix) et « Clés API facultatives » (la clé PiAPI) :
  · ce qu'est un distributeur, en deux phrases ;
  · le prix d'un plan Seedance 2.5 de 30 s chez chacun (480p / 720p / 1080p) ;
  · le mode (multi / mono) et le distributeur choisi — le MÊME réglage que le
    menu du Studio, relu à chaque affichage (sinon la page, qui enregistre
    tout à chaque frappe, remettrait l'ancien choix par-dessus celui du Studio) ;
  · une clé par distributeur, avec « Tester » (gratuit) et « Obtenir une clé » ;
  · pour PiAPI, la vérification gratuite de l'envoi d'images.

Le panneau n'enregistre rien lui-même : il émet `changed`, la page enregistre.
"""
from __future__ import annotations

import webbrowser

from PyQt6.QtCore import QThread, Qt, pyqtSignal
from PyQt6.QtWidgets import (QComboBox, QHBoxLayout, QLabel, QLineEdit, QMessageBox,
                             QPushButton, QVBoxLayout, QWidget)

from core.i18n import translate
from ui.styles import CP

#: Distributeurs alternatifs à clé (fal a sa clé dans « Clés API »).
_ALT = ("byteplus", "runware", "piapi")


class _KeyTestWorker(QThread):
    """Test GRATUIT d'une clé hors du fil de l'interface."""
    done = pyqtSignal(str, bool, str)

    def __init__(self, pid: str, key: str):
        super().__init__()
        self._pid, self._key = pid, key

    def run(self):
        try:
            from api.distributors import test_key
            ok, msg = test_key(self._pid, self._key)
        except Exception as e:
            ok, msg = False, str(e)[:200]
        self.done.emit(self._pid, ok, msg)


def _small(text: str, color: str = "") -> QLabel:
    lbl = QLabel(translate(text))
    lbl.setWordWrap(True)
    lbl.setStyleSheet(f"color:{color or CP['text_dim']};font-size:10px;"
                      f"background:transparent;border:none;")
    return lbl


def _btn(label: str) -> QPushButton:
    b = QPushButton(translate(label))
    b.setFixedHeight(26)
    b.setCursor(Qt.CursorShape.PointingHandCursor)
    b.setStyleSheet(
        f"QPushButton{{background:transparent;color:{CP['accent2']};"
        f"border:1px solid {CP['accent2_dim']};border-radius:6px;"
        f"font-size:10px;font-weight:700;padding:0 10px;}}"
        f"QPushButton:hover{{background:rgba(124,107,255,0.12);color:#9d8fff;}}")
    return b


def _combo_style() -> str:
    return (f"QComboBox{{background:{CP['bg2']};border:1px solid {CP['border']};"
            f"border-radius:6px;color:{CP['text_primary']};font-size:11px;padding:0 8px;}}"
            f"QComboBox::drop-down{{border:none;width:20px;}}"
            f"QComboBox QAbstractItemView{{background:{CP['bg3']};"
            f"border:1px solid {CP['border_bright']};color:{CP['text_primary']};"
            f"selection-background-color:{CP['accent_dim']};}}")


class _OrderList(QWidget):
    """Ordre de priorité des distributeurs : une ligne par distributeur, case
    « utiliser », rang, état de la clé, ▲ ▼ (demande Matthieu du 04/10/2026 :
    « sélectionner les distributeurs qu'on veut utiliser… classer lequel on
    veut en premier »). Au moins un reste coché."""

    changed = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet("background:transparent;")
        self._lay = QVBoxLayout(self)
        self._lay.setContentsMargins(0, 0, 0, 0)
        self._lay.setSpacing(4)
        self._order: list[str] = []
        self._off: set[str] = set()
        self._keys: dict[str, bool] = {}
        self._mono = False

    def set_mono(self, mono: bool):
        """En mono, seul le premier coché sert : les suivants le disent."""
        self._mono = bool(mono)
        self._rebuild()

    def set_state(self, order: list[str], off, keys: dict[str, bool]):
        self._order = list(order)
        self._off = set(off or ()) & set(order)
        self._keys = dict(keys)
        self._rebuild()

    def set_keys(self, keys: dict[str, bool]):
        self._keys = dict(keys)
        self._rebuild()

    def order(self) -> list[str]:
        return list(self._order)

    def off(self) -> list[str]:
        return [p for p in self._order if p in self._off]

    def enabled(self) -> list[str]:
        return [p for p in self._order if p not in self._off]

    def _rebuild(self):
        from PyQt6.QtWidgets import QCheckBox
        from core import media_provider as mp
        while self._lay.count():
            it = self._lay.takeAt(0)
            w = it.widget()
            if w is not None:
                w.setParent(None)
                w.deleteLater()
        rank = 0
        for i, pid in enumerate(self._order):
            on = pid not in self._off
            rank += 1 if on else 0
            row = QWidget()
            row.setStyleSheet(
                f"QWidget#orderRow{{background:{CP['bg2']};border:1px solid {CP['border']};"
                f"border-radius:7px;}}")
            row.setObjectName("orderRow")
            h = QHBoxLayout(row)
            h.setContentsMargins(10, 4, 8, 4)
            h.setSpacing(8)
            cb = QCheckBox()
            cb.setChecked(on)
            cb.setToolTip(translate("Utiliser ce distributeur"))
            cb.toggled.connect(lambda checked, p=pid: self._toggle(p, checked))
            h.addWidget(cb)
            name = QLabel(f"{rank}.  {translate(mp.provider_label(pid))}" if on
                          else translate(mp.provider_label(pid)))
            name.setStyleSheet(
                f"color:{CP['text_primary'] if on else CP['text_dim']};font-size:12px;"
                f"font-weight:{'600' if on else '400'};background:transparent;border:none;")
            h.addWidget(name, 1)
            if self._mono and on and rank > 1:
                idle = QLabel(translate("non utilisé en mono"))
                idle.setStyleSheet(f"color:{CP['text_dim']};font-size:10px;"
                                   f"background:transparent;border:none;")
                h.addWidget(idle)
            has_key = self._keys.get(pid, False)
            st = QLabel(translate("clé ✓") if has_key else translate("clé manquante"))
            st.setStyleSheet(
                f"color:{CP['green'] if has_key else CP['orange']};font-size:10px;"
                f"background:transparent;border:none;")
            h.addWidget(st)
            for txt, delta in (("▲", -1), ("▼", 1)):
                b = QPushButton(txt)
                b.setFixedSize(26, 22)
                b.setCursor(Qt.CursorShape.PointingHandCursor)
                b.setEnabled(0 <= i + delta < len(self._order))
                # padding:0 explicite : la marge du style global écrasait le
                # glyphe dans 26 px (bouton vide au rendu).
                b.setStyleSheet(
                    f"QPushButton{{background:transparent;color:{CP['accent2']};"
                    f"border:1px solid {CP['border']};border-radius:5px;font-size:10px;"
                    f"padding:0;min-width:0;min-height:0;}}"
                    f"QPushButton:hover{{border-color:{CP['accent2']};}}"
                    f"QPushButton:disabled{{color:{CP['text_dim']};border-color:{CP['bg3']};}}")
                b.clicked.connect(lambda _c=False, p=pid, d=delta: self._move(p, d))
                h.addWidget(b)
            self._lay.addWidget(row)

    # La reconstruction supprime le bouton / la case qui émet : différée d'un tour.
    def _later_rebuild(self):
        from PyQt6.QtCore import QTimer
        QTimer.singleShot(0, self._rebuild)

    def _toggle(self, pid: str, checked: bool):
        if not checked and len(self.enabled()) <= 1:
            self._later_rebuild()    # au moins un distributeur reste utilisé
            return
        (self._off.discard if checked else self._off.add)(pid)
        self._later_rebuild()
        self.changed.emit()

    def _move(self, pid: str, delta: int):
        i = self._order.index(pid)
        j = i + delta
        if 0 <= j < len(self._order):
            self._order[i], self._order[j] = self._order[j], self._order[i]
            self._later_rebuild()
            self.changed.emit()


def price_table_html() -> str:
    """Prix d'un plan Seedance 2.5 de 30 s chez chaque distributeur."""
    from core import media_provider as mp
    res_list = ("480p", "720p", "1080p")
    cols = {r: {q["id"]: q for q in mp.quotes("seedance-2.5", r, 30)} for r in res_list}
    head = "".join(f"<td align='right' style='color:{CP['text_dim']};'>{r}</td>"
                   for r in res_list)
    rows = []
    for pid in mp.ORDER:
        cells = []
        for r in res_list:
            q = cols[r].get(pid) or {}
            c = q.get("cost")
            cells.append(f"<td align='right'>{'—' if c is None else f'${c:.2f}'}</td>")
        name = mp.provider_short(pid) + (" <span style='color:%s;'>HT</span>" % CP["text_dim"]
                                         if pid == "byteplus" else "")
        rows.append(f"<tr><td style='color:{CP['text_secondary']};'>{name}</td>"
                    + "".join(cells) + "</tr>")
    return (f"<table cellspacing='0' cellpadding='5' style='color:{CP['text_primary']};"
            f"font-size:11px;'><tr><td></td>{head}</tr>{''.join(rows)}</table>")


class DistributionPanel(QWidget):
    """Contenu de la section « Distribution des vidéos »."""

    changed = pyqtSignal()

    def __init__(self, cfg: dict, field_style: str = "", parent=None):
        super().__init__(parent)
        from core import media_provider as mp
        self.setStyleSheet("background:transparent;")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(10)
        self._workers: list = []

        lay.addWidget(_small(
            "Un distributeur vend l'accès aux moteurs : Seedance est le même partout, "
            "seuls le prix et les options changent. fal.ai reste le socle (tous les "
            "moteurs, image et son compris) ; un distributeur moins cher peut servir "
            "Seedance à sa place. Le choix se fait aussi dans le Studio, à côté du moteur.",
            CP["text_secondary"]))

        lay.addWidget(_small("Plan Seedance 2.5 de 30 secondes — prix indicatifs relevés "
                             "le 04/10/2026 :"))
        self._prices = QLabel(price_table_html())
        self._prices.setTextFormat(Qt.TextFormat.RichText)
        self._prices.setStyleSheet("background:transparent;border:none;")
        lay.addWidget(self._prices)

        # ── Mode + distributeur choisi ───────────────────────────────────────
        def _row(label: str, combo: QComboBox):
            r = QHBoxLayout()
            r.setSpacing(8)
            lbl = QLabel(translate(label))
            lbl.setStyleSheet(f"color:{CP['text_secondary']};font-size:11px;"
                              f"background:transparent;border:none;")
            r.addWidget(lbl, 1)
            combo.setFixedHeight(28)
            combo.setMinimumWidth(260)
            combo.setStyleSheet(_combo_style())
            r.addWidget(combo)
            lay.addLayout(r)

        self.mode_combo = QComboBox()
        self.mode_combo.addItem(translate("Multi-distributeurs (recommandé)"), "multi")
        self.mode_combo.addItem(translate("Mono-distributeur (uniquement le premier)"), "mono")
        _row("Mode de distribution", self.mode_combo)

        # ── Ordre de priorité (04/10/2026) ───────────────────────────────────
        lay.addWidget(_small(
            "Ordre de priorité — pour chaque plan, PANDORA prend le PREMIER distributeur "
            "coché qui sait le faire (moteur, résolution, son coupé, image de début / fin, "
            "réception des images de référence) ; sinon il passe automatiquement au "
            "suivant, et la progression dit pourquoi. Un compte fal.ai bloqué faute de "
            "solde est sauté. En mono, seul le premier est utilisé. L'ordre ne concerne "
            "que Seedance : les autres moteurs (Kling, Veo…) ne sont vendus que par fal.ai.",
            CP["text_secondary"]))
        self.order_list = _OrderList()
        self.order_list.changed.connect(lambda: self.changed.emit())
        lay.addWidget(self.order_list)

        # ── Une clé par distributeur ─────────────────────────────────────────
        self.key_inputs: dict[str, QLineEdit] = {}
        placeholders = {"byteplus": "Clé API BytePlus ModelArk (Bearer)",
                        "runware": "Clé API Runware",
                        "piapi": "Clé PiAPI (X-API-Key)"}
        for pid in _ALT:
            head = QHBoxLayout()
            head.setSpacing(8)
            name = QLabel(translate(mp.provider_label(pid)))
            name.setStyleSheet(f"color:{CP['text_primary']};font-size:12px;font-weight:600;"
                               f"background:transparent;border:none;")
            head.addWidget(name, 1)
            t = _btn("✓  Tester la clé")
            t.clicked.connect(lambda _c=False, p=pid: self.test_key(p))
            head.addWidget(t)
            o = _btn("⇗  Obtenir une clé")
            o.clicked.connect(lambda _c=False, u=mp.provider_keys_url(pid): webbrowser.open(u))
            head.addWidget(o)
            lay.addLayout(head)
            lay.addWidget(_small(mp.PROVIDERS[pid]["blurb"]))
            field = QLineEdit()
            field.setEchoMode(QLineEdit.EchoMode.Password)
            field.setPlaceholderText(translate(placeholders[pid]))
            if field_style:
                field.setStyleSheet(field_style)
            field.textChanged.connect(lambda *_: self._on_key_edited())
            self.key_inputs[pid] = field
            lay.addWidget(field)

        # ── Ce que les comptes permettent (sondes gratuites) ─────────────────
        img_row = QHBoxLayout()
        img_row.setSpacing(8)
        self._img_status = _small(
            "Compte fal.ai et dépôt PiAPI : non vérifiés. Un compte fal bloqué ne sert "
            "plus ni à générer ni de relais ; PiAPI ne reçoit des images qu'avec son "
            "dépôt (abonnement Creator) ou le relais fal.")
        img_row.addWidget(self._img_status, 1)
        self._img_btn = _btn("Vérifier (gratuit)")
        self._img_btn.clicked.connect(self.check_images)
        img_row.addWidget(self._img_btn)
        lay.addLayout(img_row)

        self._fal_key = (cfg.get("api_key") or "").strip()
        self.sync_from_config(cfg)
        self.mode_combo.currentIndexChanged.connect(self._on_mode_changed)

    def _on_mode_changed(self, *_):
        self.order_list.set_mono(self.mode_combo.currentData() == "mono")
        self.changed.emit()

    # ── Valeurs ──────────────────────────────────────────────────────────────

    def _keys_state(self) -> dict[str, bool]:
        st = {pid: bool(f.text().strip()) for pid, f in self.key_inputs.items()}
        st["fal"] = bool(self._fal_key)
        return st

    def _on_key_edited(self):
        self.order_list.set_keys(self._keys_state())
        self.changed.emit()

    def sync_from_config(self, cfg: dict):
        """Relit l'ordre (peut-être changé dans le Studio), le mode et les clés
        SANS émettre `changed`."""
        from core import media_provider as mp
        self._fal_key = (cfg.get("api_key") or "").strip()
        for w in (self.mode_combo, *self.key_inputs.values()):
            w.blockSignals(True)
        try:
            self.mode_combo.setCurrentIndex(
                1 if (cfg.get("distribution_mode") or "multi") == "mono" else 0)
            for pid, field in self.key_inputs.items():
                want = cfg.get(f"{pid}_key", "") or ""
                if field.text() != want:
                    field.setText(want)
        finally:
            for w in (self.mode_combo, *self.key_inputs.values()):
                w.blockSignals(False)
        self.order_list._mono = (cfg.get("distribution_mode") or "multi") == "mono"
        self.order_list.set_state(mp.provider_order(cfg), cfg.get("video_providers_off") or [],
                                  self._keys_state())

    def set_fal_key_present(self, present: bool):
        """La clé fal se saisit dans « Clés API » : la page la signale ici."""
        self._fal_key = "x" if present else ""
        self.order_list.set_keys(self._keys_state())

    def values(self) -> dict:
        enabled = self.order_list.enabled() or ["fal"]
        out = {"video_provider": enabled[0],
               "video_provider_order": self.order_list.order(),
               "video_providers_off": self.order_list.off(),
               "distribution_mode": self.mode_combo.currentData() or "multi"}
        for pid, field in self.key_inputs.items():
            out[f"{pid}_key"] = field.text().strip()
        return out

    def summary(self) -> str:
        """Résumé pour l'en-tête de la section : l'ordre effectif et le mode."""
        from core import media_provider as mp
        v = self.values()
        enabled = self.order_list.enabled() or ["fal"]
        if v["distribution_mode"] == "mono":
            enabled = enabled[:1]
        # « mono » / « multi » restent tels quels (compris dans les deux langues ;
        # les traduire seuls toucherait d'autres libellés identiques).
        mode = "mono" if v["distribution_mode"] == "mono" else "multi"
        return f"{' → '.join(mp.provider_short(p) for p in enabled)} · {mode}"

    # ── Tests gratuits ───────────────────────────────────────────────────────

    def _park(self):
        from core.worker import abandon_thread, is_running
        for w in list(self._workers):
            if not is_running(w):
                self._workers.remove(w)
        return abandon_thread

    def test_key(self, pid: str):
        key = self.key_inputs[pid].text().strip()
        if not key:
            QMessageBox.warning(self, translate("Clé manquante"),
                                translate("Colle d'abord la clé, puis teste-la."))
            return
        self._park()
        from api.distrib_probe import keep_alive
        w = keep_alive(_KeyTestWorker(pid, key))
        w.done.connect(self._on_key_tested)
        self._workers.append(w)
        w.start()

    def _on_key_tested(self, pid: str, ok: bool, msg: str):
        if ok:
            QMessageBox.information(self, translate("✓ Connexion OK"), msg)
        else:
            QMessageBox.critical(self, translate("Clé refusée"), msg)

    def check_images(self):
        """Sondes gratuites (api/distrib_probe) : compte fal utilisable ? dépôt
        PiAPI ouvert ? (Aucune génération.)"""
        from api import distrib_probe as dp
        dp.forget()
        self._park()
        self._img_status.setText(translate("Vérification du compte fal.ai et du dépôt PiAPI…"))
        w = dp.keep_alive(dp.FactsProbe())
        w.done.connect(self._on_images_checked)
        self._workers.append(w)
        w.start()

    def _on_images_checked(self, facts: dict):
        def _line(label: str, state: tuple, ok_txt: str) -> tuple[str, str]:
            ok, why = state
            if ok is True:
                return f"✓ {translate(label)} : {translate(ok_txt)}", CP["green"]
            if ok is False:
                return f"✕ {translate(label)} : {why}", CP["orange"]
            return f"? {translate(label)} : {translate('vérification impossible pour l’instant')}", \
                CP["text_dim"]
        lines = [_line("Compte fal.ai", facts.get("fal", (None, "")), "utilisable"),
                 _line("Dépôt PiAPI", facts.get("piapi_upload", (None, "")),
                       "ouvert (PiAPI reçoit les images)")]
        self._img_status.setTextFormat(Qt.TextFormat.RichText)
        self._img_status.setText("<br>".join(
            f"<span style='color:{col};'>{txt}</span>" for txt, col in lines))
