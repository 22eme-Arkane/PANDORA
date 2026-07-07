"""
api/live_extract.py — Workers Claude pour le Conducteur Live (équivalents adaptés
des workers Scénario de Cinéma, mais typés Live / Mapping).

  - FormatConducteurWorker   : mise en page de la trame (calibrée Live/Mapping)
  - ArrangeConducteurWorker  : proposition d'arrangement (réécriture améliorée)
  - ExtractLiveAssetsWorker  : extraction casting / accessoires / véhicules → live_assets

Tout passe par la clé Anthropic (config.json).
"""

from PyQt6.QtCore import QThread, pyqtSignal

from api.live_screenplay import _extract_json_array, _FACADE_FRAME_RULE

_MODEL = "claude-haiku-4-5"


def _mode_ctx(mode: str) -> str:
    if mode == "mapping":
        return ("Contexte : performance de MAPPING vidéo projeté sur la façade d'un "
                "bâtiment (façade verrouillée, caméra fixe, séquence continue). "
                "SEULE la façade de la photo de référence existe — aucune action "
                "reposant sur un élément non visible sur cette photo.")
    return ("Contexte : performance LIVE / VJ (visuels en boucle projetés en concert "
            "ou installation).")


def _claude(system: str, user: str, task: str | None = None) -> str:
    """Appel IA texte via la couche d'abstraction — voir core/ai_provider.
    `task` route vers le moteur adapté (Paramètres → moteur par tâche) ; tier
    créatif pour router comme les équivalents Cinéma (extraction → Sonnet…)."""
    from core.ai_provider import complete, key_error
    err = key_error(task)
    if err:
        raise RuntimeError(err)
    return complete(system, user, tier="creative", max_tokens=4096, task=task)


def _fmt_err(e) -> str:
    from core.worker import humanize_api_error
    return humanize_api_error(str(e))


# ── Mise en page ─────────────────────────────────────────────────────────────

class FormatConducteurWorker(QThread):
    """Mise en page PANDORA en STREAMING (signaux chunk/finished/failed) → alimente
    la fenêtre d'aperçu, comme l'arrangement."""
    finished = pyqtSignal(str)
    failed   = pyqtSignal(str)
    chunk    = pyqtSignal(str)

    def __init__(self, text: str, mode: str, duration_secs: int = 0):
        super().__init__()
        self._text = text
        self._mode = mode
        self._dur  = duration_secs

    def run(self):
        if not self._text.strip():
            self.failed.emit("La trame est vide.")
            return
        from core.ai_provider import stream as ai_stream, key_error
        # Mise en page du conducteur = équivalent Live de FormatPandoraWorker
        # (Cinéma) → même tâche « screenplay » (routage/défauts par tâche).
        err = key_error("screenplay")
        if err:
            self.failed.emit(err)
            return
        try:
            _lock = ("Caméra FIXE, cadre verrouillé. La façade est un ÉCRAN, pas un sujet : "
                     "elle ne doit PAS rester visible en permanence. Alterne au fil des plans : "
                     "révélation (arêtes/fenêtres dessinées en lumière depuis le noir), "
                     "extinction (façade disparue, noir total), transformation (matière qui se "
                     "fissure/fond/se reconstruit), recouvrement total (un autre monde plein "
                     "cadre), jeu architectural (seules des parties s'illuminent). Chaque "
                     "PROMPT VIDÉO doit COMMENCER par l'état de la façade dans ce plan.\n"
                     + _FACADE_FRAME_RULE
                     if self._mode == "mapping" else "")
            # Langue de TRAVAIL (fr/en) : la mise en page reste dans la langue de
            # l'utilisateur — la traduction en anglais est faite au moment de l'ENVOI
            # aux moteurs (translate_to_english : api/real.py, video_engines.py, tts.py).
            # On garde donc PROMPT VIDÉO / PROMPT SON lisibles et éditables à la main.
            from core.i18n import get_lang
            _is_en   = (get_lang() == "en")
            _pl      = "anglais" if _is_en else "français"
            _quality = ("cinematic, ultra-detailed, sharp, 4K" if _is_en
                        else "cinématographique, ultra-détaillé, net, 4K")
            _beats   = ("'opening:', 'then', 'in the final moment'" if _is_en
                        else "« ouverture : », « puis », « dans le dernier instant »")
            system = (
                "Tu es superviseur de génération vidéo IA ET sound designer pour PANDORA | Live. "
                + _mode_ctx(self._mode) + " " + _lock +
                "À partir du CONDUCTEUR fourni (et de la TIMELINE MUSICALE éventuelle : BPM, "
                "drops, énergie), produis une MISE EN PAGE optimisée pour les MOTEURS de "
                "génération. La lisibilité humaine importe peu : le but est que les moteurs "
                "comprennent au mieux. Organise en ACTES (grandes sections du conducteur), "
                "chaque acte regroupant plusieurs PLANS numérotés. "
                "⭐ Les PROMPT VIDÉO doivent être RICHES et TRÈS DÉTAILLÉS : Seedance 2.0 "
                "donne de bien meilleurs résultats avec des descriptions visuelles denses. "
                "Ne résume PAS le conducteur en une ligne — DÉVELOPPE chaque plan.\n\n"
                "RÈGLE STRICTE — séparation vidéo / son : la TIMELINE MUSICALE (BPM, drops, "
                "énergie) ne sert QU'À deux choses : (1) fixer les DURÉES et le timing des "
                "plans, (2) nourrir le PROMPT SON. Le PROMPT VIDÉO est destiné à un moteur "
                "VIDÉO (Seedance) : il doit être 100 % VISUEL — INTERDIT d'y mettre le BPM, "
                "un tempo, des chiffres musicaux, des noms d'instruments ou tout terme audio.\n\n"
                "Présente chaque acte par un en-tête, puis ses plans selon EXACTEMENT ce format :\n\n"
                "=== ACTE {n} — {nom court de l'acte} ===\n"
                "PLAN {n} — {titre court en français}\n"
                "Durée : {x}s · Valeur de plan : {…} · Mouvement : {…}\n"
                "PROMPT VIDÉO (Seedance 2.0, " + _pl + ") : \"{prompt visuel TRÈS DÉTAILLÉ et "
                "dense — Seedance 2.0 exploite un MAXIMUM de détails, ne sois donc PAS bref. "
                "Décris précisément : SUJET + ACTION, DÉCOR / environnement, COMPOSITION & "
                "cadrage, LUMIÈRE (direction, qualité, température de couleur), PALETTE de "
                "couleurs, TEXTURES & matières, MOUVEMENT (ce qui bouge et comment), "
                "ATMOSPHÈRE / mood, STYLE visuel, et repères de QUALITÉ (" + _quality + "). "
                "Structure l'évolution en BEATS RELATIFS (" + _beats + ") — JAMAIS de timecode absolu, "
                "le moteur ne les respecte pas ; les impacts musicaux exacts vont sur les "
                "CUTS entre plans. 3 à 5 phrases riches, autonome, prêt tel quel ; "
                "AUCUN terme audio ni BPM}\"\n"
                "PROMPT SON (sound design / SFX, " + _pl + ") : \"{prompt audio décrivant l'ambiance "
                "sonore, les effets, textures et rythme du plan, prêt pour un générateur de SFX. "
                "AUCUNE parole ni voix. C'est ICI que le BPM et les drops sont pris en compte}\"\n\n"
                "Réponds UNIQUEMENT avec les actes et leurs plans (aucun texte autour)."
            )
            user = self._text
            if self._dur and self._dur > 0:
                mins, secs = divmod(int(self._dur), 60)
                dur_str = f"{mins}min {secs:02d}s" if mins else f"{secs}s"
                user = (f"[DURÉE CIBLE TOTALE : {dur_str} = {int(self._dur)} secondes. "
                        f"Dimensionne le NOMBRE et la durée des plans en conséquence.]\n\n"
                        + self._text)
            # Tier créatif (Sonnet/Fable…) : prompts vidéo riches/détaillés pour
            # Seedance 2.0. 16000 tokens — un conducteur complet mis en page
            # dépassait 8000 (tronqué en réel le 2026-06-11) ; aligné sur Cinéma.
            full = ai_stream(system, user, on_chunk=self.chunk.emit,
                             tier="creative", max_tokens=16000, task="screenplay")
            self.finished.emit(full.strip())
        except Exception as e:
            self.failed.emit(_fmt_err(e))


# ── Arrangement ──────────────────────────────────────────────────────────────

class ArrangeConducteurWorker(QThread):
    finished = pyqtSignal(str)
    failed   = pyqtSignal(str)

    def __init__(self, text: str, mode: str):
        super().__init__()
        self._text = text
        self._mode = mode

    def run(self):
        if not self._text.strip():
            self.failed.emit("La trame est vide.")
            return
        try:
            system = (
                "Tu es dramaturge pour une performance visuelle. " + _mode_ctx(self._mode) + " "
                "Propose une version AMÉLIORÉE et réarrangée de la trame : meilleure "
                "progression, montées et respirations, cohérence visuelle, temps forts "
                "bien placés. Garde le français et l'esprit de l'auteur. "
                "Réponds UNIQUEMENT avec la trame réarrangée."
            )
            # Arrangement = tâche « screenplay » (comme ArrangeScreenplayWorker Cinéma).
            self.finished.emit(_claude(system, self._text, task="screenplay").strip())
        except Exception as e:
            self.failed.emit(_fmt_err(e))


# ── Extraction casting / accessoires / véhicules ─────────────────────────────

_KIND_LABEL = {
    "casting":     ("personnages / performers", "name, category (rôle/type), description (apparence, costume, style visuel)"),
    "accessoires": ("accessoires / objets",     "name, category, description (matière, couleur, état)"),
    "vehicules":   ("véhicules",                "name, category, description (marque, modèle, couleur, état)"),
}


def extract_live_assets(kind: str, text: str, mode: str) -> list:
    """Extraction calibrée LIVE (performers / objets de scène / véhicules) —
    lève une exception en cas d'erreur. Logique partagée worker + adaptateur."""
    label, fields = _KIND_LABEL.get(kind, _KIND_LABEL["casting"])
    system = (
        f"Tu es assistant de production pour PANDORA | Live. {_mode_ctx(mode)} "
        f"Identifie les {label} évoqués (ou pertinents) dans la trame fournie. "
        f"Pour chacun, fournis : {fields}. Textes en français. "
        "Réponds UNIQUEMENT avec un tableau JSON d'objets (aucun texte autour). "
        "Si aucun élément pertinent, renvoie []."
    )
    # Extraction JSON = tâche « extraction » (comme les extracteurs Cinéma).
    out = _claude(system, text, task="extraction")
    items = []
    for it in _extract_json_array(out):
        if isinstance(it, dict) and it.get("name"):
            items.append({
                "name":        str(it.get("name", "")).strip(),
                "category":    str(it.get("category", "")).strip(),
                "description": str(it.get("description", "")).strip(),
                "images":      [],
            })
    return items


def live_extract_worker_cls(kind: str, mode: str):
    """Fabrique une classe worker compatible ExtractGenerateDialog
    (ctor(text), signaux finished(list)/failed(str)) mais calibrée LIVE —
    remplace les extracteurs Cinéma (terminologie film) dans le Conducteur."""

    class _LiveExtractWorker(QThread):
        finished = pyqtSignal(list)
        failed   = pyqtSignal(str)

        def __init__(self, text: str):
            super().__init__()
            self._text = text

        def run(self):
            if not self._text.strip():
                self.failed.emit("La trame est vide.")
                return
            try:
                self.finished.emit(extract_live_assets(kind, self._text, mode))
            except Exception as e:
                self.failed.emit(_fmt_err(e))

    return _LiveExtractWorker


class ExtractLiveAssetsWorker(QThread):
    """Extrait les éléments d'un type depuis la trame → list[{name,category,description}]."""
    finished = pyqtSignal(str, list)   # (kind, items)
    failed   = pyqtSignal(str)

    def __init__(self, kind: str, text: str, mode: str):
        super().__init__()
        self._kind = kind
        self._text = text
        self._mode = mode

    def run(self):
        if not self._text.strip():
            self.failed.emit("La trame est vide.")
            return
        try:
            self.finished.emit(self._kind,
                               extract_live_assets(self._kind, self._text, self._mode))
        except Exception as e:
            self.failed.emit(_fmt_err(e))
