"""
api/live_refs.py — Analyse des références visuelles du CONDUCTEUR (PANDORA | Live).

Refonte demandée par l'utilisateur (2026-06-10) :
  1. FILE D'ATTENTE : chaque image est analysée SÉPARÉMENT (une requête par image,
     redimensionnée via core/image_payload) — fini le « 413 request_too_large »
     quand on met beaucoup de photos.
  2. VRAI TRAVAIL DE FOND : après les analyses individuelles, une SYNTHÈSE croise
     l'ensemble avec le conducteur : direction visuelle globale (palette, lumière,
     matières), correspondances image → acte, et suggestions concrètes prêtes à
     nourrir les prompts.
  3. ENRICHISSEMENT calibré CONDUCTEUR (l'ancien worker réécrivait au format
     scénario Cinéma).

Vision = Anthropic direct (doctrine v1 : le sélecteur d'assistant ne couvre que
le texte) ; la synthèse et l'enrichissement passent par core/ai_provider.
"""

import os

from PyQt6.QtCore import QThread, pyqtSignal

from core.image_payload import encode_image_for_vision


def _mode_ctx(mode: str) -> str:
    if mode == "mapping":
        return ("performance de MAPPING vidéo projetée sur la façade d'un bâtiment, "
                "de nuit (façade = écran, fond noir)")
    return "performance LIVE / VJ (loops visuels projetés en concert ou installation)"


_PER_IMAGE_SYSTEM = (
    "Tu analyses UNE image de référence pour une {ctx}. "
    "Décris-la en français, orienté direction visuelle de projection :\n"
    "• **Ambiance / mood** : l'émotion, l'énergie\n"
    "• **Lumière** : direction, qualité, température, contrastes\n"
    "• **Palette** : couleurs dominantes et accents (précis : teintes, saturation)\n"
    "• **Matières & textures** : ce qui pourrait vivre/se transformer en projection\n"
    "• **Motifs & composition** : formes, rythmes graphiques exploitables en loop\n"
    "• **Idée de projection** : 1 phrase — comment cette image pourrait nourrir un plan\n"
    "Sois concret et concis (≤ 120 mots). Pas de personnages/casting : on parle "
    "de matière visuelle."
)

_SYNTHESIS_SYSTEM = (
    "Tu es directeur artistique d'une {ctx}. On te fournit le CONDUCTEUR et les "
    "analyses individuelles des images de référence.\n\n"
    "Produis la SYNTHÈSE de direction visuelle, en français :\n"
    "1. **DIRECTION GLOBALE** — palette maîtresse, signature lumineuse, matières "
    "récurrentes, énergie d'ensemble qui se dégage du moodboard ;\n"
    "2. **CORRESPONDANCES PAR ACTE** — pour chaque acte/moment du conducteur, "
    "quelles images le nourrissent et comment (sois précis : « Image 3 → acte 2 : "
    "ses dorures deviennent les filaments du build-up ») ;\n"
    "3. **SUGGESTIONS CONCRÈTES** — 5 à 8 propositions actionnables : ambiances de "
    "plans, transitions visuelles, mots-clés de style à injecter dans les prompts.\n"
    "INTERDIT : vocabulaire scénario (INT./EXT., scènes, séquences). On raisonne "
    "en ACTES et en PLANS projetés."
)

_ENRICH_SYSTEM = (
    "Tu reçois un CONDUCTEUR de {ctx} et la SYNTHÈSE de direction visuelle issue "
    "des images de référence. Réécris le conducteur en l'ENRICHISSANT : intègre "
    "la palette, la lumière, les matières et les correspondances par acte là où "
    "elles renforcent le propos — sans changer la structure, les intentions ni la "
    "voix de l'auteur.\n"
    "IMPORTANT — c'est un CONDUCTEUR, PAS un scénario : INTERDIT « INT. » / "
    "« EXT. », en-têtes de scène, « séquence », « scène ». Garde la forme du "
    "conducteur original et le français.\n"
    "Réponds UNIQUEMENT avec le conducteur enrichi (aucun commentaire autour)."
)


class AnalyzeRefsConducteurWorker(QThread):
    """Analyse en FILE D'ATTENTE (1 requête/image, images redimensionnées) puis
    SYNTHÈSE croisée avec le conducteur. Signaux : chunk/finished/failed —
    compatible avec la fenêtre d'analyse existante (_open_refs_window)."""
    finished = pyqtSignal(str)
    failed   = pyqtSignal(str)
    chunk    = pyqtSignal(str)

    def __init__(self, ref_paths: list, scenario_text: str = "", mode: str = "live"):
        super().__init__()
        self._paths = [p for p in (ref_paths or []) if p]
        self._text  = scenario_text or ""
        self._mode  = mode if mode in ("live", "mapping") else "live"

    def run(self):
        from core.config import load_config
        key = load_config().get("anthropic_key", "").strip()
        if not key:
            self.failed.emit("Clé Anthropic (Claude) manquante — renseignez-la dans Paramètres.")
            return
        paths = [p for p in self._paths if os.path.isfile(p)]
        if not paths:
            self.failed.emit("Aucune image valide à analyser.")
            return
        try:
            # VISION : Anthropic direct (hors couche ai_provider — texte seulement)
            import anthropic
            client = anthropic.Anthropic(api_key=key)
            ctx = _mode_ctx(self._mode)
            analyses: list[str] = []

            # ── Phase 1 : file d'attente — une requête par image ──────────────
            for i, path in enumerate(paths, 1):
                if self.isInterruptionRequested():
                    return
                name = os.path.basename(path)
                self.chunk.emit(f"── Image {i}/{len(paths)} — {name} ──\n")
                mime, b64 = encode_image_for_vision(path)
                msg = client.messages.create(
                    model="claude-haiku-4-5",
                    max_tokens=500,
                    system=_PER_IMAGE_SYSTEM.format(ctx=ctx),
                    messages=[{"role": "user", "content": [
                        {"type": "image",
                         "source": {"type": "base64", "media_type": mime, "data": b64}},
                        {"type": "text", "text": f"Image {i} : analyse-la."},
                    ]}],
                )
                txt = "".join(b.text for b in msg.content
                              if getattr(b, "type", "") == "text").strip()
                analyses.append(f"IMAGE {i} ({name}) :\n{txt}")
                self.chunk.emit(txt + "\n\n")

            # ── Phase 2 : synthèse croisée avec le conducteur ─────────────────
            self.chunk.emit("═══ SYNTHÈSE — DIRECTION VISUELLE ═══\n")
            from core.ai_provider import stream
            user = "ANALYSES DES IMAGES :\n\n" + "\n\n".join(analyses)
            if self._text.strip():
                user += f"\n\nCONDUCTEUR :\n{self._text.strip()}"
            else:
                user += "\n\n(Pas de conducteur fourni — fais la direction globale et les suggestions.)"
            synthesis = stream(_SYNTHESIS_SYSTEM.format(ctx=ctx), user,
                               on_chunk=self.chunk.emit,
                               tier="creative", max_tokens=4096)

            full = ("\n\n".join(analyses)
                    + "\n\n═══ SYNTHÈSE — DIRECTION VISUELLE ═══\n" + synthesis.strip())
            self.finished.emit(full)
        except Exception as e:
            from core.worker import humanize_api_error
            self.failed.emit(humanize_api_error(str(e)))


class EnrichConducteurWithRefsWorker(QThread):
    """Réécrit le CONDUCTEUR en intégrant la direction visuelle (streaming).
    Signaux chunk/done/failed — compatibles avec le bouton « Enrichir » existant.
    Remplace EnrichScenarioWithRefsWorker (Cinéma) qui réécrivait en scénario."""
    done   = pyqtSignal(str)
    failed = pyqtSignal(str)
    chunk  = pyqtSignal(str)

    def __init__(self, scenario_text: str, analysis: str, mode: str = "live"):
        super().__init__()
        self._text     = scenario_text
        self._analysis = analysis
        self._mode     = mode if mode in ("live", "mapping") else "live"

    def run(self):
        from core.ai_provider import stream, key_error
        err = key_error()
        if err:
            self.failed.emit(err)
            return
        try:
            user = (f"CONDUCTEUR ORIGINAL :\n{self._text}\n\n"
                    f"DIRECTION VISUELLE (références) :\n{self._analysis}")
            full = stream(_ENRICH_SYSTEM.format(ctx=_mode_ctx(self._mode)), user,
                          on_chunk=self.chunk.emit,
                          tier="creative", max_tokens=8192)
            self.done.emit(full.strip())
        except Exception as e:
            from core.worker import humanize_api_error
            self.failed.emit(humanize_api_error(str(e)))
