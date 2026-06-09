"""
api/live_extract.py — Workers Claude pour le Conducteur Live (équivalents adaptés
des workers Scénario de Cinéma, mais typés Live / Mapping).

  - FormatConducteurWorker   : mise en page de la trame (calibrée Live/Mapping)
  - ArrangeConducteurWorker  : proposition d'arrangement (réécriture améliorée)
  - ExtractLiveAssetsWorker  : extraction casting / accessoires / véhicules → live_assets

Tout passe par la clé Anthropic (config.json).
"""

from PyQt6.QtCore import QThread, pyqtSignal

from api.live_screenplay import _extract_json_array

_MODEL = "claude-haiku-4-5"


def _mode_ctx(mode: str) -> str:
    if mode == "mapping":
        return ("Contexte : performance de MAPPING vidéo projeté sur la façade d'un "
                "bâtiment (façade verrouillée, caméra fixe, séquence continue).")
    return ("Contexte : performance LIVE / VJ (visuels en boucle projetés en concert "
            "ou installation).")


def _claude(system: str, user: str) -> str:
    from core.config import load_config
    key = load_config().get("anthropic_key", "").strip()
    if not key:
        raise RuntimeError("Clé Anthropic (Claude) manquante — renseignez-la dans Paramètres.")
    import anthropic
    client = anthropic.Anthropic(api_key=key)
    msg = client.messages.create(
        model=_MODEL, max_tokens=3000, system=system,
        messages=[{"role": "user", "content": user}],
    )
    return "".join(b.text for b in msg.content if getattr(b, "type", "") == "text")


def _fmt_err(e) -> str:
    from core.worker import humanize_api_error
    return humanize_api_error(str(e))


# ── Mise en page ─────────────────────────────────────────────────────────────

class FormatConducteurWorker(QThread):
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
                "Tu es directeur artistique pour PANDORA | Live. " + _mode_ctx(self._mode) + " "
                "Mets en page la trame fournie en un document clair et structuré, "
                "optimisé pour ensuite être découpé en segments. Garde le français. "
                "Structure en sections lisibles (intro, montée, temps forts, ruptures, final), "
                "avec pour chaque moment l'ambiance visuelle, les couleurs et l'énergie. "
                "Réponds UNIQUEMENT avec le document mis en page."
            )
            self.finished.emit(_claude(system, self._text).strip())
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
            self.finished.emit(_claude(system, self._text).strip())
        except Exception as e:
            self.failed.emit(_fmt_err(e))


# ── Extraction casting / accessoires / véhicules ─────────────────────────────

_KIND_LABEL = {
    "casting":     ("personnages / performers", "name, category (rôle/type), description (apparence, costume, style visuel)"),
    "accessoires": ("accessoires / objets",     "name, category, description (matière, couleur, état)"),
    "vehicules":   ("véhicules",                "name, category, description (marque, modèle, couleur, état)"),
}


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
        label, fields = _KIND_LABEL.get(self._kind, _KIND_LABEL["casting"])
        try:
            system = (
                f"Tu es assistant de production pour PANDORA | Live. {_mode_ctx(self._mode)} "
                f"Identifie les {label} évoqués (ou pertinents) dans la trame fournie. "
                f"Pour chacun, fournis : {fields}. Textes en français. "
                "Réponds UNIQUEMENT avec un tableau JSON d'objets (aucun texte autour). "
                "Si aucun élément pertinent, renvoie []."
            )
            out = _claude(system, self._text)
            items = []
            for it in _extract_json_array(out):
                if isinstance(it, dict) and it.get("name"):
                    items.append({
                        "name":        str(it.get("name", "")).strip(),
                        "category":    str(it.get("category", "")).strip(),
                        "description": str(it.get("description", "")).strip(),
                        "images":      [],
                    })
            self.finished.emit(self._kind, items)
        except Exception as e:
            self.failed.emit(_fmt_err(e))
