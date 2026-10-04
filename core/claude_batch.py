"""
Mode Batch de Claude (Message Batches API d'Anthropic) : −50 % sur les jetons.

Utilisé par les traitements LONGS et INDÉPENDANTS (génération du storyboard par
lots, composition des prompts finals de tous les plans). Le principe :

    with claude_batch.session({"storyboard_gen", "video_prompt"}, ...):
        ... code existant, inchangé ...

Pendant la session, chaque appel Anthropic des tâches citées, fait depuis un
thread qui APPARTIENT à la session (variable de contexte, voir `run_in_session`),
part dans un lot au lieu d'un appel direct : `core.ai_provider._anthropic_send`
le confie à `send()`, qui BLOQUE jusqu'au résultat et rend le même objet
`Message` qu'un appel direct. Tout le code appelant (contrôles, replis, reprises
de troncature, journal de coût) reste donc identique.

Les requêtes qui arrivent ensemble (les lots du storyboard, puis les plans à
composer) sont regroupées dans UN lot : on attend un court moment de calme
avant l'envoi. Anthropic traite la plupart des lots en moins d'une heure
(24 h au plus) : la session publie l'état pour la fenêtre (`on_status`) et
s'annule proprement (`should_cancel`).

Aucune donnée n'est persistée ici : fermer PANDORA pendant l'attente perd les
résultats (les lots déjà facturés restent consultables 29 jours dans la console
Anthropic).
"""

from __future__ import annotations

import contextvars
import threading
import time
import uuid
from concurrent.futures import Future

POLL_SECONDS = 15.0       # intervalle de suivi d'un lot (Anthropic : minutes à heures)
QUIET_SECONDS = 2.0       # calme exigé avant d'envoyer les requêtes accumulées
MAX_GATHER_SECONDS = 20.0  # au-delà, le lot part même si des requêtes arrivent encore
MAX_REQUESTS = 10000      # l'API en accepte 100 000 (256 Mo) par lot

_SESSION: contextvars.ContextVar = contextvars.ContextVar("pandora_claude_batch", default=None)


class BatchCancelled(RuntimeError):
    """La session a été annulée (bouton Arrêter) : la requête n'aura pas de réponse."""


class BatchRequestError(RuntimeError):
    """Une requête du lot a échoué côté Anthropic (errored / expired / canceled)."""


def _client():
    import anthropic
    from core.config import load_config
    return anthropic.Anthropic(api_key=(load_config().get("anthropic_key") or "").strip())


class Session:
    """Regroupe les requêtes des threads de la session, les envoie par lots, rend
    à chaque appelant son résultat."""

    def __init__(self, tasks, on_status=None, should_cancel=None, client_factory=None):
        self.tasks = set(tasks or ())
        self.on_status = on_status
        self.should_cancel = should_cancel
        self._client_factory = client_factory or _client
        self._lock = threading.Lock()
        self._pending: list[tuple[str, dict, Future]] = []
        self._first_at = 0.0
        self._last_at = 0.0
        self._closed = threading.Event()
        self._cancelled = threading.Event()
        self._inflight: dict[str, dict[str, Future]] = {}     # batch_id → custom_id → futur
        self.stats = {"requests": 0, "done": 0, "batches": 0, "started": time.monotonic()}
        self._thread = threading.Thread(target=self._gather_loop, daemon=True)
        self._thread.start()

    # ── Côté appelant ─────────────────────────────────────────────────────────

    def submit(self, params: dict) -> Future:
        fut: Future = Future()
        if self._cancelled.is_set():
            fut.set_exception(BatchCancelled("Génération interrompue."))
            return fut
        cid = "p" + uuid.uuid4().hex[:20]
        now = time.monotonic()
        with self._lock:
            if not self._pending:
                self._first_at = now
            self._last_at = now
            self._pending.append((cid, params, fut))
            self.stats["requests"] += 1
        self._status()
        return fut

    def cancel(self):
        """Annule tout : requêtes en attente et lots en cours (côté Anthropic aussi)."""
        if self._cancelled.is_set():
            return
        self._cancelled.set()
        with self._lock:
            pending, self._pending = self._pending, []
            inflight = dict(self._inflight)
        for _cid, _params, fut in pending:
            if not fut.done():
                fut.set_exception(BatchCancelled("Génération interrompue."))
        for batch_id, futures in inflight.items():
            try:
                self._client_factory().messages.batches.cancel(batch_id)
            except Exception:
                pass
            for fut in futures.values():
                if not fut.done():
                    fut.set_exception(BatchCancelled("Génération interrompue."))

    def close(self):
        self._closed.set()

    # ── Envoi et suivi ────────────────────────────────────────────────────────

    def _status(self):
        if self.on_status:
            try:
                self.on_status(dict(self.stats, inflight=len(self._inflight),
                                    pending=len(self._pending)))
            except Exception:
                pass

    def _check_cancel(self) -> bool:
        if self._cancelled.is_set():
            return True
        try:
            if self.should_cancel and self.should_cancel():
                self.cancel()
                return True
        except Exception:
            pass
        return False

    def _gather_loop(self):
        while not self._closed.is_set():
            if self._check_cancel():
                return
            batch = None
            with self._lock:
                if self._pending:
                    now = time.monotonic()
                    quiet = now - self._last_at >= QUIET_SECONDS
                    too_long = now - self._first_at >= MAX_GATHER_SECONDS
                    if quiet or too_long or len(self._pending) >= MAX_REQUESTS:
                        batch, self._pending = (self._pending[:MAX_REQUESTS],
                                                self._pending[MAX_REQUESTS:])
            if batch:
                self._create(batch)
            else:
                time.sleep(0.2)

    def _create(self, batch: list[tuple[str, dict, Future]]):
        try:
            created = self._client_factory().messages.batches.create(
                requests=[{"custom_id": cid, "params": params} for cid, params, _f in batch])
        except Exception as exc:
            for _cid, _p, fut in batch:
                if not fut.done():
                    fut.set_exception(exc)
            return
        futures = {cid: fut for cid, _p, fut in batch}
        with self._lock:
            self._inflight[created.id] = futures
            self.stats["batches"] += 1
        self._status()
        threading.Thread(target=self._poll, args=(created.id, futures), daemon=True).start()

    def _poll(self, batch_id: str, futures: dict[str, Future]):
        client = self._client_factory()
        try:
            while True:
                if self._check_cancel():
                    return
                b = client.messages.batches.retrieve(batch_id)
                if getattr(b, "processing_status", "") == "ended":
                    break
                self._status()
                for _ in range(int(POLL_SECONDS / 0.5)):
                    if self._check_cancel():
                        return
                    time.sleep(0.5)
            for entry in client.messages.batches.results(batch_id):
                fut = futures.get(getattr(entry, "custom_id", ""))
                if fut is None or fut.done():
                    continue
                res = entry.result
                kind = getattr(res, "type", "")
                if kind == "succeeded":
                    fut.set_result(res.message)
                else:
                    err = getattr(res, "error", None)
                    detail = getattr(getattr(err, "error", None), "message", "") or str(err or "")
                    fut.set_exception(BatchRequestError(
                        f"Requête du lot Claude {kind or 'en échec'}" + (f" : {detail}" if detail else "")))
            for fut in futures.values():               # absente des résultats : jamais muette
                if not fut.done():
                    fut.set_exception(BatchRequestError("Requête absente des résultats du lot."))
        except Exception as exc:
            for fut in futures.values():
                if not fut.done():
                    fut.set_exception(exc)
        finally:
            with self._lock:
                self._inflight.pop(batch_id, None)
                self.stats["done"] = self.stats["requests"] - len(self._pending) - sum(
                    len(f) for f in self._inflight.values())
            self._status()


class session:
    """Context manager : ouvre une session pour le thread courant (et ceux lancés
    par `run_in_session`)."""

    def __init__(self, tasks, on_status=None, should_cancel=None, client_factory=None):
        self._args = (tasks, on_status, should_cancel, client_factory)
        self._token = None
        self.session: Session | None = None

    def __enter__(self) -> Session:
        self.session = Session(*self._args)
        self._token = _SESSION.set(self.session)
        return self.session

    def __exit__(self, *exc):
        try:
            self.session.close()
        finally:
            _SESSION.reset(self._token)
        return False


def current() -> Session | None:
    return _SESSION.get()


def wants(task: str) -> bool:
    """Vrai si l'appel de cette tâche, dans ce contexte, doit partir en lot."""
    s = _SESSION.get()
    return s is not None and (task or "") in s.tasks


def run_in_session(fn):
    """Enveloppe `fn` pour qu'un AUTRE thread (pool) hérite de la session :
    `pool.submit(run_in_session(f), ...)`. Le contexte est copié MAINTENANT, dans
    le thread qui soumet ; chaque exécution en reçoit sa propre copie (un même
    contexte ne peut pas être ouvert par deux threads à la fois)."""
    ctx = contextvars.copy_context()

    def _wrapped(*a, **k):
        return ctx.copy().run(fn, *a, **k)
    return _wrapped


def send(params: dict, timeout: float | None = None):
    """Soumet `params` (paramètres d'un appel Messages) au lot de la session
    courante et attend le `Message` résultat."""
    s = _SESSION.get()
    if s is None:
        raise RuntimeError("Aucune session Batch ouverte.")
    return s.submit(params).result(timeout=timeout)
