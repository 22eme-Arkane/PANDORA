"""ui/seed_reprise.py — Reprendre un plan de l'Historique (même prompt, même
seed, mêmes réglages), commun aux deux éditions du Studio.

Question de Matthieu (05/10/2026) : « est-ce qu'on peut réutiliser une seed ?
Un plan était vraiment bien, je l'ai ressorti et il est moins bien. » Constat :
la reprise (bouton « ↑ HD » de l'Historique) ne reproduisait rien, sans le dire —
  · le prompt repris était le texte de TRAVAIL : l'envoi le retraduisait (une
    réécriture par l'IA, différente à chaque fois) puis le complétait de
    suffixes ; le texte réellement parti n'était enregistré nulle part ;
  · la seed n'atteignait pas le moteur : jamais transmise à BytePlus, et fal
    n'a pas de champ seed en texte→vidéo Seedance 2.5.
Désormais l'envoi garde le texte RÉELLEMENT parti (`prompt_sent`) et les
réglages ; la reprise les remet tels quels, verrouille la seed, et le Studio
dit — sous « ADN visuel » et dans le bandeau de reprise — si le distributeur
qui servira le plan la transmettra (core.media_provider.seed_supported).
ByteDance ne promet pas un rendu identique à seed égale : proche seulement.
"""
from __future__ import annotations

from core.i18n import translate


def is_exact(tab) -> bool:
    """L'encart contient-il encore, mot pour mot, le prompt d'origine repris ?
    Si oui, il repart tel quel (params["prompt_exact"]) ; retouché, il part en
    prompt final ordinaire."""
    text = getattr(tab, "_reprise_text", None)
    try:
        return bool(text) and tab.prompt_ta.toPlainText().strip() == text.strip()
    except Exception:
        return False


def seed_status(tab) -> str:
    """Quand une seed est verrouillée : sera-t-elle transmise par le distributeur
    qui servira le plan ? "" sans seed verrouillée."""
    try:
        seed = tab._get_seed()
    except Exception:
        return ""
    if not seed:
        return ""
    try:
        from core.media_provider import billing_provider, provider_short, seed_supported
        model = tab._get_model()
        res = tab.cb_res.currentData() or ""
        cb = getattr(tab, "_audio_cb", None)
        audio = bool(cb.isChecked()) if cb else True
        pid = billing_provider(model, res, audio)
        no_ref = getattr(tab, "_no_ref_global_cb", None)
        refs = bool(tab._casting.get_ref_images()) and not (no_ref and no_ref.isChecked())
        who = provider_short(pid) if pid else "—"
        if pid and seed_supported(pid, model, "ref" if refs else "t2v"):
            return translate("🔒 Seed {seed} transmise par {who}.").format(seed=seed, who=who)
        return translate(
            "⚠ Seed {seed} non transmise par {who} pour ce moteur dans ce mode : le "
            "rendu sera différent. En Seedance 2.5, BytePlus la transmet ; fal "
            "seulement en mode référence.").format(seed=seed, who=who)
    except Exception:
        return ""


def make_status_label():
    """Petite ligne sous « ADN visuel » : seed transmise ou non (05/10/2026)."""
    from PyQt6.QtCore import Qt
    from PyQt6.QtWidgets import QLabel
    lbl = QLabel("")
    lbl.setWordWrap(True)
    lbl.setAlignment(Qt.AlignmentFlag.AlignHCenter)
    lbl.setVisible(False)
    return lbl


def _banner_text(tab) -> str:
    seed = getattr(tab, "_reprise_seed", 0)
    if getattr(tab, "_reprise_text", None):
        if is_exact(tab):
            head = translate(
                "Plan repris — prompt d'origine exact (envoyé tel quel), seed {seed} et "
                "réglages remis. Rendu proche, pas identique : ByteDance ne garantit pas "
                "la reproduction, même à seed égale.").format(seed=seed)
        elif getattr(tab, "_prompt_is_final", False):
            head = translate(
                "Plan repris, prompt retouché : il part tel qu'il est écrit, avec la "
                "seed {seed}. Le rendu s'éloignera de l'original.").format(seed=seed)
        else:
            # Le Live sort du mode final à la première frappe : le texte est
            # alors retraduit et complété à l'envoi.
            head = translate(
                "Plan repris, prompt retouché : il sera retraduit et complété à "
                "l'envoi, avec la seed {seed}. Le rendu s'éloignera de "
                "l'original.").format(seed=seed)
    else:
        head = translate(
            "Plan repris — seed {seed} verrouillée. Le prompt exactement envoyé "
            "n'était pas encore enregistré pour ce plan (avant le 05/10/2026) : il "
            "sera retraduit, le rendu peut s'éloigner.").format(seed=seed)
    status = getattr(tab, "_seed_status_text", "")
    return f"{head}\n{status}" if status else head


def _refresh_banner(tab) -> None:
    banner = getattr(tab, "_reprise_banner", None)
    if banner is None:
        return
    if getattr(tab, "_reprise_active", False):
        banner.setText(_banner_text(tab))
        banner.setVisible(True)
    else:
        banner.setVisible(False)


def refresh_status(tab) -> None:
    """Relit l'état de la seed (verrou, moteur, distributeur, références) et met
    à jour la ligne sous « ADN visuel » et le bandeau de reprise. Appelée au
    changement de verrou, de distributeur, de moteur ou de références."""
    from ui.styles import CP
    text = seed_status(tab)
    tab._seed_status_text = text
    lbl = getattr(tab, "_seed_status_lbl", None)
    if lbl is not None:
        color = CP["orange"] if text.startswith("⚠") else CP["text_secondary"]
        lbl.setStyleSheet(f"color:{color};font-size:10px;background:transparent;border:none;")
        lbl.setText(text)
        lbl.setVisible(bool(text))
    # Seed déverrouillée : la reprise est finie, son bandeau aussi.
    if getattr(tab, "_reprise_active", False) and not text:
        tab._reprise_active = False
    _refresh_banner(tab)


def on_prompt_edited(tab) -> None:
    """Le prompt a changé (saisie ou remplacement) : le bandeau de reprise dit
    s'il part encore à l'identique. Aucune lecture de configuration : appelée
    à chaque frappe."""
    if getattr(tab, "_reprise_active", False):
        _refresh_banner(tab)


def _select_data(combo, value) -> None:
    if combo is None or value in (None, ""):
        return
    idx = combo.findData(value)
    if idx >= 0:
        combo.setCurrentIndex(idx)


def _select_duration(tab, seconds) -> None:
    try:
        seconds = float(seconds)
        opts = list(getattr(tab, "_DUR_OPTIONS", []) or [])
    except (TypeError, ValueError):
        return
    if not opts or seconds <= 0:
        return
    best = min(range(len(opts)), key=lambda i: abs(opts[i] - seconds))
    tab.cb_dur.setCurrentIndex(best)


def _select_ratio(tab, ratio: str) -> None:
    ratio = (ratio or "").strip()
    combo = getattr(tab, "cb_ratio", None)
    if not ratio or combo is None:
        return
    for i in range(combo.count()):
        if combo.itemText(i).split(" ")[0] == ratio:
            combo.setCurrentIndex(i)
            return


def apply_reprise(tab, entry: dict) -> None:
    """Remet dans le Studio un plan de l'Historique : réglages d'origine, prompt
    réellement envoyé (qui repartira tel quel), seed verrouillée, bandeau."""
    if not isinstance(entry, dict):
        return
    # 1. Réglages AVANT le prompt : changer de moteur peut réassembler l'encart.
    try:
        _select_data(tab.cb_model, entry.get("model"))
        _select_data(tab.cb_res, entry.get("resolution"))
        _select_duration(tab, entry.get("duration"))
        _select_ratio(tab, entry.get("aspect_ratio", ""))
        cb = getattr(tab, "_audio_cb", None)
        if cb is not None and "audio" in entry:
            cb.setChecked(bool(entry.get("audio")))
    except Exception:
        pass

    # 2. Prompt : le texte RÉELLEMENT parti ; à défaut (plan d'avant le
    #    05/10/2026), le prompt de travail, que l'envoi retraduira.
    exact = (entry.get("prompt_sent") or "").strip()
    if exact:
        tab._suppress_prompt_signal = True
        try:
            tab.prompt_ta.setPlainText(exact)
        finally:
            tab._suppress_prompt_signal = False
        tab._prompt_is_final = True
        tab._final_engine = tab._get_model()
        tab._reprise_text = exact
    else:
        tab._reprise_text = None
        prompt = (entry.get("prompt") or "").strip()
        if prompt:
            tab._prompt_is_final = False
            tab.prompt_ta.setPlainText(prompt)

    # 3. Seed verrouillée.
    try:
        seed = int(entry.get("seed") or 0)
    except (TypeError, ValueError):
        seed = 0
    tab._reprise_seed = seed
    if seed > 0:
        tab._last_seed = seed
        if not tab._seed_lock_btn.isChecked():
            tab._seed_lock_btn.setChecked(True)   # → _on_seed_toggle (garde _last_seed)

    # 4. Bandeau et ligne d'état.
    tab._reprise_active = seed > 0
    refresh_status(tab)
