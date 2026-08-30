"""api/storyboard_queue.py — Génération du storyboard par lots successifs.

`GenerateStoryboardWorker` convertit TOUTES les fiches d'un découpage en un
seul appel, plafonné à 16 000 jetons. Au-delà d'une centaine de fiches la
réponse se coupe, et un storyboard amputé passe les contrôles : chaque plan
qu'il contient est bien formé, seul le compte est faux.

Ce coordinateur découpe le document en sous-documents valides et les traite
l'un après l'autre.

**Il ne réécrit pas la conversion — il réutilise le worker existant.** Chaque
lot passe par un `GenerateStoryboardWorker` dont on appelle `run()` directement,
dans CE thread : pas de thread imbriqué, et surtout tout l'acquis reste en
place — repli déterministe, détection de fusion, résolution des personnages et
décors, composition des prompts finals. Dupliquer cette logique aurait été le
plus sûr moyen de la voir diverger.

**Rien n'est enregistré ici.** Le contrat de la page Storyboard est « aperçu
PUIS confirmation » : ce worker rend des plans, l'auteur décide.
"""

from __future__ import annotations

from PyQt6.QtCore import QThread, pyqtSignal

from core.storyboard_batches import (
    FICHES_PER_BATCH, count_fiches, merge_shots, split_document,
)


class StoryboardQueueWorker(QThread):
    """Génère le storyboard d'un découpage, lot de fiches par lot de fiches.

    Signaux :
      `progress(pct, message)`         — avancement global
      `batch_done(index, total, n)`    — un lot de plus, `n` plans au total
      `compose_progress(faits, total)` — composition des prompts finals, cumulée
      `done(shots)`                    — tous les lots ont abouti
      `failed(message, shots)`         — arrêt ; `shots` porte ce qui a déjà été
                                         produit, jamais perdu
    """

    progress         = pyqtSignal(int, str)
    batch_done       = pyqtSignal(int, int, int)
    compose_progress = pyqtSignal(int, int)
    done             = pyqtSignal(list)
    failed           = pyqtSignal(str, list)

    def __init__(self, text: str, duration_secs: int = 0,
                 element_names: dict | None = None,
                 strict_no_merge: bool = False, target_engine: str = "",
                 per_batch: int = FICHES_PER_BATCH):
        super().__init__()
        self._text = text or ""
        self._duration = duration_secs
        self._names = element_names or {}
        self._strict = strict_no_merge
        self._engine = target_engine
        self._per = max(1, int(per_batch or FICHES_PER_BATCH))
        self._groupes: list[list[dict]] = []

    # ── Un lot ───────────────────────────────────────────────────────────────

    def _run_batch(self, sous_doc: str, part_secs: int) -> list[dict]:
        """Fait tourner le worker existant sur un sous-document.

        `run()` est appelé directement plutôt que `start()` : le travail se
        fait dans CE thread, ce qui évite un QThread imbriqué et rend la
        collecte synchrone. Les connexions vont vers des fonctions Python
        simples, donc en direct.
        """
        from api.screenplay import GenerateStoryboardWorker

        recu: list[list[dict]] = []
        erreur: list[str] = []

        w = GenerateStoryboardWorker(
            sous_doc, duration_secs=part_secs,
            element_names=self._names, strict_no_merge=self._strict,
            target_engine=self._engine)
        w.finished.connect(recu.append)
        w.failed.connect(erreur.append)
        # La composition des prompts finals d'un lot alimente le total global.
        w.compose_progress.connect(self._on_sub_compose)
        try:
            w.run()
        finally:
            # Le worker n'a jamais été démarré comme thread : rien à parquer,
            # mais on coupe les connexions pour qu'un signal tardif n'atteigne
            # pas des listes qui ne nous appartiennent plus.
            try:
                w.finished.disconnect()
                w.failed.disconnect()
                w.compose_progress.disconnect()
            except Exception:
                pass

        if erreur:
            raise RuntimeError(erreur[0])
        return recu[0] if recu else []

    def _on_sub_compose(self, faits: int, total: int):
        # Relayé tel quel : la fenêtre affiche l'avancement du lot en cours,
        # ce qui reste lisible et évite un compteur global faux si un lot
        # compose moins de plans qu'annoncé.
        self.compose_progress.emit(faits, total)

    # ── Boucle ───────────────────────────────────────────────────────────────

    def run(self):
        try:
            lots = split_document(self._text, self._per)
            total = len(lots)
            if not total:
                self.failed.emit(
                    "Aucune fiche PLAN trouvée dans le découpage.", [])
                return

            n_fiches = count_fiches(self._text)
            # La durée cible est répartie au prorata des fiches du lot : sinon
            # chaque lot viserait la durée du film entier.
            for i, sous_doc in enumerate(lots):
                if self.isInterruptionRequested():
                    self.failed.emit("Génération interrompue.",
                                     merge_shots(self._groupes))
                    return

                self.progress.emit(
                    int(i / total * 100),
                    f"Storyboard — lot {i + 1} sur {total}…")

                part = 0
                if self._duration and n_fiches:
                    part = max(1, int(self._duration
                                      * count_fiches(sous_doc) / n_fiches))

                plans = self._run_batch(sous_doc, part)
                if not plans:
                    raise RuntimeError(
                        f"Le lot {i + 1} n'a produit aucun plan.")
                self._groupes.append(plans)
                self.batch_done.emit(i + 1, total,
                                     sum(len(g) for g in self._groupes))

            shots = merge_shots(self._groupes)
            # Le compte doit correspondre aux fiches d'origine, à la fusion
            # près. Un écart franc signale une réponse tronquée qu'aucun
            # contrôle de forme n'aurait vue.
            if n_fiches and len(shots) < n_fiches * 0.5:
                raise RuntimeError(
                    f"{len(shots)} plans produits pour {n_fiches} fiches : "
                    "une partie du découpage n'a pas été convertie.")
            self.progress.emit(100, f"Storyboard terminé — {len(shots)} plans ✓")
            self.done.emit(shots)

        except Exception as e:
            self.failed.emit(str(e), merge_shots(self._groupes))
