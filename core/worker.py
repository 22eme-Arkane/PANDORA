from PyQt6.QtCore import QThread, pyqtSignal

# ── Annulation SÛRE d'un QThread ──────────────────────────────────────────────
# QThread.terminate() est dangereux : il tue le thread n'importe où dans son code,
# laissant Qt/Python dans un état corrompu → segfault sur l'opération suivante.
# À la place : on coupe les signaux (résultats ignorés), on demande l'interruption,
# et on garde une référence pour que le thread finisse tranquillement sans être
# ramassé par le GC pendant qu'il tourne encore.
_ABANDONED_THREADS: list = []

def abandon_thread(w) -> None:
    """Abandonne un QThread en cours sans le terminer brutalement (anti-segfault)."""
    if w is None:
        return
    try:
        w.blockSignals(True)
    except Exception:
        pass
    try:
        w.requestInterruption()
    except Exception:
        pass
    try:
        w.quit()
    except Exception:
        pass
    _ABANDONED_THREADS.append(w)
    # Purge les threads déjà terminés (sûrs à libérer)
    _ABANDONED_THREADS[:] = [t for t in _ABANDONED_THREADS if _still_running(t)]

def is_running(t) -> bool:
    """isRunning() SÛR : renvoie False au lieu de lever quand l'objet C++ du QThread
    a déjà été détruit.

    Appeler t.isRunning() directement lève « RuntimeError: wrapped C/C++ object of
    type … has been deleted » — typiquement depuis un slot branché sur destroyed,
    qui par construction se déclenche APRÈS la destruction côté C++ (crash réel à la
    fermeture du Live, 2026-07-26). Tout code qui teste un worker susceptible d'avoir
    été détruit doit passer par ici."""
    try:
        return t.isRunning()
    except Exception:
        return False


# Ancien nom interne, conservé : utilisé par abandon_thread ci-dessus.
_still_running = is_running


# Mots-clés d'un VRAI refus de facturation. « out of », « limit exceeded »,
# « quota », « balance » ou le simple mot « credit » y figuraient : un rejet
# de validation fal (« duration out of range », « file size limit exceeded »)
# ou l'erreur de crédit du fournisseur IA TEXTE (Anthropic : « Your credit
# balance is too low ») s'affichaient tous en « Crédits fal.ai insuffisants »
# — constat Matthieu 25/09/2026, alors que fal avait 13 $ de solde.
_CREDIT_KEYWORDS = (
    "exhausted balance", "insufficient balance", "balance is too low",
    "insufficient credit", "insufficient funds", "top up your", "topup",
    "payment required", "402", "purchase credits", "billing_hard_limit",
    "insufficient_quota", "exceeded your current quota", "not enough credit",
)
# Ce qui signe une erreur du fournisseur IA TEXTE (traduction, analyse
# d'image, composition) et non de fal.ai.
_TEXT_AI_MARKERS = (
    "anthropic", "plans & billing", "openai", "mistral", "insufficient_quota",
    "exceeded your current quota", "x-api-key", "console.anthropic",
)


def is_credit_error(err: str) -> bool:
    low = (err or "").lower()
    return any(kw in low for kw in _CREDIT_KEYWORDS)


def is_text_ai_error(err: str) -> bool:
    """L'erreur vient du fournisseur IA texte (Anthropic/OpenAI…), pas de fal."""
    low = (err or "").lower()
    return any(m in low for m in _TEXT_AI_MARKERS)


def fal_error_detail(err: str) -> str:
    """Le ou les `msg` d'un détail de validation fal (liste JSON-like
    `[{'loc': [...], 'msg': '…'}]`), sinon l'erreur elle-même, courte. Ce que
    fal reproche au clip (durée, résolution, taille) doit se LIRE, pas se
    deviner (« durée trop courte ? »)."""
    import re as _re
    msgs = _re.findall(r"""['"]msg['"]\s*:\s*['"]([^'"]{3,200})['"]""", err or "")
    if msgs:
        return " · ".join(dict.fromkeys(m.strip() for m in msgs))
    return (err or "").strip().replace("\n", " ")[:200]


def humanize_api_error(err: str) -> str:
    """Erreur d'un worker de génération, lisible : nomme le BON compte quand
    c'est une affaire de crédits, laisse passer tout le reste tel quel."""
    if is_credit_error(err):
        if is_text_ai_error(err):
            return (
                "Crédits du fournisseur IA TEXTE (Anthropic/OpenAI…) épuisés — la "
                "préparation du prompt (traduction, analyse d'image, composition) a "
                "échoué. Le compte fal.ai n'est pas en cause.\n"
                "Rechargez ce compte (console.anthropic.com → Plans & Billing) ou "
                "changez de fournisseur dans Paramètres → Assistant IA."
            )
        return (
            "Crédits fal.ai insuffisants — la génération n'a pas pu démarrer.\n"
            "Rechargez votre compte sur fal.ai/dashboard pour continuer.\n"
            f"({fal_error_detail(err)})"
        )
    return err


class GenerationWorker(QThread):
    progress = pyqtSignal(int, str)
    finished = pyqtSignal(dict)
    failed   = pyqtSignal(str)

    def __init__(self, params: dict):
        super().__init__()
        self.params = params
        self._cancelled = False

    def cancel(self):
        self._cancelled = True

    def run(self):
        # Bascule automatiquement sur la vraie API si une clé est configurée
        try:
            from core.config import load_config
            has_key = bool(load_config().get("api_key", "").strip())
        except Exception as e:
            self.failed.emit(f"Impossible de charger la configuration : {e}")
            return

        try:
            if has_key:
                from api.real import run_real as runner
            else:
                from api.mock import run_mock as runner
        except ImportError as e:
            pkg = "fal-client" if "fal" in str(e).lower() else str(e)
            self.failed.emit(
                f"Module manquant : {pkg}\n"
                "Installe les dépendances : pip install fal-client"
            )
            return

        try:
            result = runner(self.params, self.progress.emit, lambda: self._cancelled)
            if not self._cancelled:
                self.finished.emit(result)
        except Exception as e:
            if not self._cancelled:
                self.failed.emit(humanize_api_error(str(e)))
