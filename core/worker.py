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

def _still_running(t) -> bool:
    try:
        return t.isRunning()
    except Exception:
        return False


_CREDIT_KEYWORDS = (
    "insufficient", "credit", "balance", "payment", "402",
    "not enough", "out of", "topup", "top up", "top-up",
    "quota", "limit exceeded", "billing",
)

def is_credit_error(err: str) -> bool:
    low = err.lower()
    return any(kw in low for kw in _CREDIT_KEYWORDS)

def humanize_api_error(err: str) -> str:
    """Détecte les erreurs de crédit fal.ai et retourne un message lisible."""
    if is_credit_error(err):
        return (
            "Crédits fal.ai insuffisants — la génération n'a pas pu démarrer.\n"
            "Rechargez votre compte sur fal.ai/dashboard pour continuer."
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
