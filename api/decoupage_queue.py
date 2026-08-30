"""api/decoupage_queue.py — Découpage par lots successifs.

Un scénario trop gros ne peut pas être découpé d'une traite (voir
`core.decoupage_scale`). Ce worker le traite **tranche par tranche**, chaque
tranche calibrée pour tenir en un seul appel — donc sans continuation, donc
sans le coût quadratique de la boucle anti-troncature.

UN SEUL QThread pour toute la file, et non un worker par lot enchaîné depuis
l'interface. Ce choix évite d'un coup les trois pièges Qt du projet : pas de
réassignation de `self._worker` à chaud, pas de lambda à déconnecter, pas de
QThread ramassé en vol. L'annulation passe par `requestInterruption()`, jamais
par `terminate()`.

**Rien n'est jamais perdu.** Après chaque lot réussi, le document recollé est
émis (`batch_done`). Si le lot 7 échoue, les six premiers sont déjà entre les
mains de l'appelant, qui peut les enregistrer et reprendre plus tard.
"""

from __future__ import annotations

from PyQt6.QtCore import QThread, pyqtSignal

from core.decoupage_batches import (
    SLICE_CHARS, carry_over, join_batches, slice_screenplay,
    trim_trailing_prose, strip_marker,
)
from core.decoupage_document import is_v2_document, validate_v2_document

#: Un lot est calibré pour tenir en un tour. On autorise malgré tout UNE
#: reprise : une tranche exceptionnellement dense ne doit pas faire échouer
#: toute la file. Au-delà, c'est la tranche qui est mal dimensionnée, et la
#: relancer à l'identique ne servirait à rien.
_MAX_ROUNDS_PER_BATCH = 1


class DecoupageQueueWorker(QThread):
    """Découpe un scénario en lots et les enchaîne jusqu'au bout.

    Signaux :
      `progress(pct, message)`            — avancement global
      `batch_done(index, total, document)`— un lot de plus, document recollé
                                            à cet instant (jamais partiel)
      `done(document)`                    — tous les lots ont abouti
      `failed(message, index, document)`  — arrêt ; `document` porte ce qui a
                                            déjà été produit, jamais vide sauf
                                            échec du tout premier lot
    """

    progress   = pyqtSignal(int, str)
    batch_done = pyqtSignal(int, int, str)
    done       = pyqtSignal(str)
    failed     = pyqtSignal(str, int, str)

    def __init__(self, text: str, direction_note: str = "",
                 budget_chars: int = SLICE_CHARS,
                 resume_from: str = "", start_index: int = 0):
        super().__init__()
        self._text = text or ""
        self._note = direction_note or ""
        self._budget = max(800, int(budget_chars or SLICE_CHARS))
        # Reprise : les lots déjà produits lors d'une session précédente.
        self._done_docs: list[str] = [resume_from] if resume_from.strip() else []
        self._start = max(0, int(start_index or 0))

    # ── Appel d'un lot ───────────────────────────────────────────────────────

    def _call_batch(self, system: str, user_content: str) -> str:
        """Un lot, ou une erreur explicite. Jamais un demi-lot silencieux.

        Le drapeau `truncated` est LU — l'ignorer laisserait passer un lot
        coupé au milieu, que la validation accepterait sans broncher puisque
        chaque plan qu'il contient est, lui, bien formé.
        """
        from core.ai_provider import chat_until_complete_ex
        res = chat_until_complete_ex(
            system, [{"role": "user", "content": user_content}],
            tier="creative", max_tokens=16000, task="decoupage",
            max_rounds=_MAX_ROUNDS_PER_BATCH)
        if res.get("truncated"):
            raise ValueError(
                "Ce lot dépasse encore la longueur maximale du moteur. "
                "Réduisez la taille des lots et relancez.")
        return (res.get("text") or "").strip()

    # ── Boucle ───────────────────────────────────────────────────────────────

    def run(self):
        from core.ai_provider import key_error
        err = key_error("decoupage")
        if err:
            self.failed.emit(err, 0, "")
            return

        try:
            from api.screenplay import _format_pandora_prompt, _lang_hint, _get_lang
            from core.direction_note import note_for_ai

            lang = _get_lang()
            system = _format_pandora_prompt(lang)
            note = note_for_ai(self._note)

            tranches = slice_screenplay(self._text, self._budget)
            total = len(tranches)
            if not total:
                self.failed.emit("Le scénario est vide.", 0, "")
                return

            screenplay_label = "SCREENPLAY" if lang == "en" else "SCÉNARIO"
            note_label = "DIRECTOR'S NOTE" if lang == "en" else "NOTE DE RÉALISATION"

            for i in range(self._start, total):
                if self.isInterruptionRequested():
                    doc = join_batches(self._done_docs)
                    self.failed.emit("Découpage interrompu.", i, doc)
                    return

                pct = int(i / total * 100)
                self.progress.emit(
                    pct, f"Découpage — lot {i + 1} sur {total}…")

                # Le rappel de continuité est reconstruit à chaque lot depuis
                # ce qui est DÉJÀ produit : taille bornée, pas de renvoi du
                # document entier.
                rappel = carry_over(join_batches(self._done_docs)) \
                    if self._done_docs else ""

                user = ""
                if rappel:
                    user += rappel + "\n\n"
                user += f"[{screenplay_label} — TRANCHE {i + 1}/{total}]\n{tranches[i]}"
                if note:
                    user += f"\n\n[{note_label} — INTENTIONS DE FABRICATION]\n{note}"

                brut = self._call_batch(system, _lang_hint(lang) + user)
                lot = trim_trailing_prose(strip_marker(brut))
                if not lot.strip():
                    raise ValueError(
                        f"Le lot {i + 1} est revenu vide du moteur.")

                self._done_docs.append(lot)
                doc = join_batches(self._done_docs)
                self.batch_done.emit(i + 1, total, doc)

            doc = join_batches(self._done_docs)
            if not is_v2_document(doc):
                raise ValueError(
                    "Le document recollé ne respecte pas le contrat Découpage "
                    "PANDORA 2. Les lots produits sont conservés — vous pouvez "
                    "les relire avant de relancer.")
            issues = validate_v2_document(doc)
            if issues:
                raise ValueError(
                    "Le découpage recollé comporte des champs invalides "
                    f"({', '.join(issues[:6])}).")

            self.progress.emit(100, f"Découpage terminé — {total} lots ✓")
            self.done.emit(doc)

        except Exception as e:
            doc = join_batches(self._done_docs) if self._done_docs else ""
            self.failed.emit(str(e), len(self._done_docs), doc)
