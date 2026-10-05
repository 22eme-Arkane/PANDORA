"""
ui/distrib_picker.py — Menu « Distributeur » du Studio IA, à côté du moteur de
génération (demande Matthieu du 04/10/2026), commun aux deux éditions.

  · le menu suit l'ORDRE DE PRIORITÉ (Paramètres → Distribution des vidéos) ;
    chaque entrée affiche le prix du plan courant chez ce distributeur ;
  · y choisir un distributeur le met EN TÊTE de l'ordre (écrit dans la
    config : Studio et Paramètres restent d'accord) ;
  · `availability()` dit ce que les distributeurs ACTIVÉS permettent pour ce
    moteur — l'onglet ne grise une option que si AUCUN ne sait la faire
    (en mono : si le premier ne sait pas) ;
  · `resolution_options()` réécrit les prix du menu « Résolution » au tarif
    du distributeur qui servira chaque résolution — ils affichaient le tarif
    fal quel que soit le choix (constat Matthieu du 04/10/2026).
"""
from __future__ import annotations

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QStandardItemModel
from PyQt6.QtWidgets import QComboBox, QLabel, QVBoxLayout, QWidget

from core.i18n import translate
from ui.styles import CP


def _cached_can_receive(cfg: dict, engine: str = ""):
    """Sonde SANS réseau (le Studio ne bloque jamais) : seul un refus connu
    écarte un distributeur ; l'inconnu passe (l'envoi tranchera, et
    s'arrêtera avant de payer si les fichiers ne passent pas). Avec le
    moteur : un modèle connu comme NON ACTIVÉ chez BytePlus l'écarte aussi."""
    from api import distrib_probe as dp

    def _cr(pid, needs):
        ok, why = dp.can_receive(pid, needs, network=False, cfg=cfg, engine=engine)
        return (False, why) if ok is False else (True, "")
    return _cr


def _known_refusal(pid: str, engine: str, cfg: dict) -> str:
    """Libellé court si l'on SAIT déjà que ce distributeur refusera (sondes
    gratuites ou refus reçu en génération, 05/10/2026) ; "" sinon."""
    from api import distrib_probe as dp
    if pid == "byteplus":
        ok, _why = dp.byteplus_model_state((cfg.get("byteplus_key") or "").strip(), engine,
                                           network=False)
        return translate("Seedance non activé (console BytePlus)") if ok is False else ""
    if pid == "runware":
        ok, _why = dp.can_receive("runware", (), network=False, cfg=cfg)
        return translate("crédit insuffisant (my.runware.ai)") if ok is False else ""
    return ""


def availability(engine: str, resolution: str = "", cfg: dict | None = None) -> dict:
    """Qui servira quoi pour ce moteur, d'après ce qu'on sait déjà.

    Clés : text / ref / i2v / mute → distributeur ("" si personne) ;
    why_ref / why_i2v / why_mute → raisons des distributeurs sautés."""
    from core import media_provider as mp
    from core.config import load_config
    cfg = load_config() if cfg is None else cfg
    cr = _cached_can_receive(cfg, engine)
    text, s_text = mp.route(engine, "t2v", resolution, cfg=cfg, can_receive=cr)
    ref, s_ref = mp.route(engine, "ref", resolution, needs=("images",), cfg=cfg,
                          can_receive=cr)
    i2v, s_i2v = mp.route(engine, "i2v", resolution, needs=("images",), cfg=cfg,
                          can_receive=cr)
    mute, s_mute = mp.route(engine, "", resolution, audio=False, cfg=cfg, can_receive=cr)
    return {"text": text, "ref": ref, "i2v": i2v, "mute": mute,
            "why_text": " ; ".join(s_text), "why_ref": " ; ".join(s_ref),
            "why_i2v": " ; ".join(s_i2v), "why_mute": " ; ".join(s_mute)}


def resolution_options(engine: str, base: list) -> list:
    """Options (libellé, valeur) du menu Résolution : seules les résolutions
    qu'un distributeur ACTIVÉ peut servir, au prix de celui qui les servira."""
    from core import media_provider as mp
    from core.config import load_config
    cfg = load_config()
    cr = _cached_can_receive(cfg, engine)
    out = []
    for item in base:
        label, value = item if isinstance(item, tuple) else (item, item)
        pid, _skipped = mp.route(engine, "", value, cfg=cfg, can_receive=cr)
        if not pid:
            continue
        if pid == "fal":
            out.append((label, value))
            continue
        rate = mp.provider_rate(pid, engine, value)
        name = "4K" if str(value).lower() == "4k" else value
        out.append((label, value) if rate is None else
                   (f"{name}  (~${rate:.2f}/s · {mp.provider_short(pid)})", value))
    return out or base


class DistributorPicker(QWidget):
    """Menu des distributeurs + ligne d'explication (`hint`, placée par l'onglet)."""

    changed = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)
        # Même fabrique que les autres menus du Studio : la molette ne change
        # pas la valeur au survol (sinon un défilement de page changeait le
        # distributeur — et la config).
        from ui.widgets import combo as _combo
        self.combo: QComboBox = _combo([])
        self.combo.setToolTip(translate(
            "Qui vend la génération : le moteur est le même partout, seuls le prix et "
            "les options changent. Le distributeur choisi ici passe en tête de l'ordre "
            "de priorité (Paramètres → Distribution des vidéos)."))
        lay.addWidget(self.combo)
        self.hint = QLabel("")
        self.hint.setWordWrap(True)
        self.hint.setTextFormat(Qt.TextFormat.RichText)
        self.hint.setStyleSheet(
            f"color:{CP['text_dim']};font-size:10px;background:transparent;border:none;")
        self.hint.setVisible(False)
        self._filling = False
        self.combo.currentIndexChanged.connect(self._on_index)

    # ── Remplissage ──────────────────────────────────────────────────────────

    def refresh(self, engine: str, resolution: str, seconds: float, audio: bool = True,
                engine_label: str = "", avail: dict | None = None):
        """Reconstruit le menu (ordre de priorité, prix du plan courant) et
        l'explication de qui servira quoi."""
        from core import media_provider as mp
        from core.config import load_config
        cfg = load_config()
        enabled = mp.enabled_order(cfg)
        off = [p for p in mp.provider_order(cfg) if p not in enabled]
        quotes = {q["id"]: q for q in mp.quotes(engine, resolution, seconds, audio=audio)}
        self._filling = True
        try:
            self.combo.clear()
            model = self.combo.model()
            for rank, pid in enumerate(enabled + off, start=1):
                q = quotes.get(pid) or {}
                short = mp.provider_short(pid)
                if pid in off:
                    text = f"{short}  —  {translate('désactivé (Paramètres)')}"
                elif pid != "fal" and not q.get("has_key"):
                    text = f"{rank}. {short}  —  {translate('clé manquante (Paramètres)')}"
                elif not q.get("supported"):
                    text = f"{rank}. {short}  —  {translate('ne vend pas ce moteur')}"
                elif _known_refusal(pid, engine, cfg):
                    text = f"{rank}. {short}  —  {_known_refusal(pid, engine, cfg)}"
                elif q.get("cost") is not None:
                    text = f"{rank}. {short}  —  ≈ ${q['cost']:.2f}  ({seconds:g} s)"
                else:
                    text = f"{rank}. {short}"
                self.combo.addItem(text, pid)
                if pid in off and isinstance(model, QStandardItemModel):
                    it = model.item(self.combo.count() - 1)
                    if it is not None:
                        it.setEnabled(False)
            self.combo.setCurrentIndex(0)
        finally:
            self._filling = False
        self._refresh_hint(cfg, engine_label or engine, avail or {})

    def _refresh_hint(self, cfg: dict, engine_label: str, av: dict):
        from core import media_provider as mp
        enabled = mp.enabled_order(cfg)
        names = " → ".join(mp.provider_short(p) for p in enabled)
        mono = mp.get_distribution_mode(cfg) == "mono"
        lines: list[str] = []
        if mono:
            lines.append(translate("Mono : {name} seul.").format(name=names))
        else:
            lines.append(translate("Ordre : {names} — pour chaque plan, le premier qui "
                                   "sait le faire.").format(names=names))
        text, ref = av.get("text", ""), av.get("ref", "")
        if not text:
            lines.append(f"<span style='color:{CP['orange']};'>⚠ " + translate(
                "Aucun distributeur activé ne peut servir {engine} : {why}").format(
                engine=engine_label, why=av.get("why_text", "")) + "</span>")
        else:
            if enabled and text != enabled[0]:
                lines.append(translate("Plans sans image : {name} ({why}).").format(
                    name=mp.provider_short(text), why=av.get("why_text", "")))
            if ref and ref != text:
                lines.append(translate("Plans avec images : {name} ({why}).").format(
                    name=mp.provider_short(ref), why=av.get("why_ref", "")))
            elif not ref:
                lines.append(f"<span style='color:{CP['orange']};'>⚠ " + translate(
                    "Aucun distributeur activé ne peut recevoir d'images ({why}) : les "
                    "options qui en envoient sont désactivées. BytePlus et Runware les "
                    "reçoivent directement.").format(why=av.get("why_ref", "")) + "</span>")
        self.hint.setText("<br>".join(lines))
        self.hint.setVisible(bool(lines))

    # ── Choix ────────────────────────────────────────────────────────────────

    def _on_index(self, _i: int):
        if self._filling:
            return
        pid = self.combo.currentData() or "fal"
        try:
            from core.config import load_config, save_config
            from core.media_provider import promote_in_config
            cfg = load_config()
            if (cfg.get("video_provider_order") or [None])[0] != pid \
                    or cfg.get("video_provider") != pid:
                save_config(promote_in_config(cfg, pid))
        except Exception:
            pass
        # Différé d'un tour : l'onglet reconstruit ce menu en réponse — pas
        # depuis l'intérieur de son propre signal.
        from PyQt6.QtCore import QTimer
        QTimer.singleShot(0, lambda: self.changed.emit(pid))
