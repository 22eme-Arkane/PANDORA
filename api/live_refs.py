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
    "Tu décodes UNE image de référence pour une {ctx}. Ce n'est PAS une image à "
    "réutiliser telle quelle : c'est une INSPIRATION, une direction artistique à "
    "décoder ENTIÈREMENT pour en extraire les codes réutilisables.\n"
    "Analyse en français, de façon complète :\n"
    "• **Ambiance / mood** : l'émotion, l'énergie, l'univers évoqué\n"
    "• **Style d'image** : médium et rendu (photo, peinture, 3D, gravure, "
    "argentique…), technique, grain, époque, références culturelles/artistiques\n"
    "• **Architecture & espaces** : formes bâties, volumes, ornements, échelle, "
    "vocabulaire architectural — ce qui peut dialoguer avec une façade/projection\n"
    "• **Personnages & figures** : silhouettes, costumes, postures, traitement "
    "(réaliste, stylisé, spectral…) — comme codes de style, pas comme casting\n"
    "• **Lumière** : direction, qualité, température, contrastes\n"
    "• **Palette** : couleurs dominantes et accents (précis : teintes, saturation)\n"
    "• **Matières, textures & motifs** : ce qui peut vivre, se répéter, se "
    "transformer en projection\n"
    "• **Idée de projection** : 1-2 phrases — comment transposer ces codes dans un plan\n"
    "Sois concret et précis (≤ 200 mots). Décode les codes, ne décris pas pour copier."
)

_SYNTHESIS_SYSTEM = (
    "Tu es directeur artistique d'une {ctx}. On te fournit le CONDUCTEUR et les "
    "analyses individuelles des images de référence.\n\n"
    "Les références sont une INSPIRATION à décoder, jamais à copier : extrais-en "
    "les codes (architecture, traitement des figures, style d'image, lumière, "
    "matières) et TRANSPOSE-les en langage de projection.\n"
    "Produis la SYNTHÈSE de direction artistique, en français :\n"
    "1. **DIRECTION GLOBALE** — l'univers qui se dégage du moodboard : style "
    "d'image et rendu (médium, époque, technique), vocabulaire architectural, "
    "traitement des personnages/figures, palette maîtresse, signature lumineuse, "
    "matières récurrentes, énergie d'ensemble ;\n"
    "2. **CORRESPONDANCES PAR ACTE** — pour chaque acte/moment du conducteur, "
    "quelles images le nourrissent et comment leurs codes se transposent (sois "
    "précis : « Image 3 → acte 2 : ses arcades gothiques deviennent la grammaire "
    "des ouvertures lumineuses du build-up ») ;\n"
    "3. **SUGGESTIONS CONCRÈTES** — 5 à 8 propositions actionnables : ambiances de "
    "plans, figures et architectures à faire vivre, transitions visuelles, "
    "mots-clés de style (rendu, médium, lumière) à injecter dans les prompts.\n"
    "INTERDIT : vocabulaire scénario (INT./EXT., scènes, séquences). On raisonne "
    "en ACTES et en PLANS projetés."
)

_ENRICH_SYSTEM = (
    "Tu reçois un CONDUCTEUR de {ctx} et la SYNTHÈSE de direction visuelle issue "
    "des images de référence. Réécris le conducteur en l'ENRICHISSANT : intègre "
    "les codes décodés — style d'image et rendu, vocabulaire architectural, "
    "traitement des figures, palette, lumière, matières — et les correspondances "
    "par acte là où ils renforcent le propos, sans changer la structure, les "
    "intentions ni la voix de l'auteur. La direction artistique est une "
    "inspiration transposée, pas une copie des images.\n"
    "IMPORTANT — c'est un CONDUCTEUR, PAS un scénario : INTERDIT « INT. » / "
    "« EXT. », en-têtes de scène, « séquence », « scène ». Garde la forme du "
    "conducteur original et le français.\n"
    "Réponds UNIQUEMENT avec le conducteur enrichi (aucun commentaire autour)."
)


class AnalyzeRefsConducteurWorker(QThread):
    """Analyse en FILE D'ATTENTE (1 requête/image, images redimensionnées) puis
    SYNTHÈSE croisée avec le conducteur. Signaux : chunk/done/failed —
    compatible avec la fenêtre d'analyse existante (_open_refs_window).
    NB : « done », pas « finished » — redéfinir finished masquerait le signal
    natif de QThread."""
    done   = pyqtSignal(str)
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
                    max_tokens=800,
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
            # 8192 tokens : la synthèse croise N analyses × actes — 4096 tronquait
            synthesis = stream(_SYNTHESIS_SYSTEM.format(ctx=ctx), user,
                               on_chunk=self.chunk.emit,
                               tier="creative", max_tokens=8192)

            full = ("\n\n".join(analyses)
                    + "\n\n═══ SYNTHÈSE — DIRECTION VISUELLE ═══\n" + synthesis.strip())
            self.done.emit(full)
        except Exception as e:
            from core.worker import humanize_api_error
            self.failed.emit(humanize_api_error(str(e)))


_CHAT_SYSTEM = (
    "Tu es conseiller en direction artistique pour une {ctx}. "
    "Tu disposes de l'ANALYSE du moodboard de référence (décodage complet : "
    "architecture, figures, style d'image, lumière, palette, matières) et du "
    "CONDUCTEUR du spectacle. L'utilisateur dialogue avec toi pour décider "
    "comment TRANSPOSER cette direction artistique dans son conducteur et ses "
    "plans projetés.\n"
    "Règles :\n"
    "• Réponds en français, concret et actionnable — propose des formulations "
    "prêtes à coller dans le conducteur ou dans les prompts quand c'est utile ;\n"
    "• La DA est une inspiration à transposer, jamais à copier ;\n"
    "• INTERDIT : vocabulaire scénario (INT./EXT., scènes, séquences) — on "
    "raisonne en ACTES et en PLANS projetés ;\n"
    "• Reste dans ton rôle : direction artistique, visuels, projection."
)


class RefsChatWorker(QThread):
    """Un tour de dialogue direction artistique (streaming) dans la fenêtre
    Références visuelles. messages = historique [{role, content}] complet,
    dernier message = question de l'utilisateur. Signaux : chunk/done/failed."""
    done   = pyqtSignal(str)
    failed = pyqtSignal(str)
    chunk  = pyqtSignal(str)

    def __init__(self, messages: list, analysis: str, scenario_text: str = "",
                 mode: str = "live"):
        super().__init__()
        self._messages = list(messages or [])
        self._analysis = analysis or ""
        self._text     = scenario_text or ""
        self._mode     = mode if mode in ("live", "mapping") else "live"

    def run(self):
        from core.ai_provider import chat_stream, key_error
        err = key_error()
        if err:
            self.failed.emit(err)
            return
        if not self._messages:
            self.failed.emit("Aucun message à envoyer.")
            return
        try:
            ctx_doc = f"ANALYSE DES RÉFÉRENCES (direction artistique) :\n{self._analysis}"
            if self._text.strip():
                ctx_doc += f"\n\nCONDUCTEUR ACTUEL :\n{self._text.strip()}"
            # Le contexte documentaire est préfixé au premier message utilisateur
            # (les providers locaux n'aiment pas les très longs system prompts).
            messages = [dict(m) for m in self._messages]
            first = messages[0]
            messages[0] = {"role": first["role"],
                           "content": f"{ctx_doc}\n\n---\n\n{first['content']}"}
            # 8192 tokens : une réponse acte par acte dépasse largement 2048
            # (vu en réel : coupure nette en plein acte 7).
            full = chat_stream(_CHAT_SYSTEM.format(ctx=_mode_ctx(self._mode)),
                               messages, on_chunk=self.chunk.emit,
                               tier="creative", max_tokens=8192)
            self.done.emit(full.strip())
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
