"""
api/billing.py — Vérification du solde fal.ai avant génération.

Endpoint : GET https://api.fal.ai/v1/account/billing?expand=credits
"""
import time
import requests
from PyQt6.QtCore import QThread, pyqtSignal
from core.config import load_config

# Seuils en USD (fal.ai facture en USD)
WARN_THRESHOLD  = 5.0   # $ — avertissement solde faible
BLOCK_THRESHOLD = 0.0   # $ — blocage si solde ≤ 0

_FAL_BILLING_URL = "https://api.fal.ai/v1/account/billing"
_DASHBOARD_URL   = "https://fal.ai/dashboard/billing"

# Cache en mémoire — évite de spammer l'API sur les clics rapides
_cache: dict = {}
_CACHE_TTL   = 30  # secondes


def get_cached_balance() -> tuple[float, str] | None:
    """Retourne (balance, currency) depuis le cache si encore valide, sinon None."""
    if "ts" in _cache and time.time() - _cache["ts"] < _CACHE_TTL:
        return _cache["balance"], _cache["currency"]
    return None


def invalidate_cache():
    _cache.clear()


def _fetch_balance(api_key: str) -> tuple[float, str]:
    """Appel HTTP synchrone — à appeler uniquement depuis un QThread."""
    r = requests.get(
        _FAL_BILLING_URL,
        params={"expand": "credits"},
        headers={"Authorization": f"Key {api_key}"},
        timeout=8,
    )
    r.raise_for_status()
    data = r.json()
    bal  = float(data["credits"]["current_balance"])
    cur  = data["credits"].get("currency", "USD")
    _cache.update({"balance": bal, "currency": cur, "ts": time.time()})
    return bal, cur


class BillingCheckWorker(QThread):
    """Worker asynchrone — vérifie le solde fal.ai en arrière-plan."""
    result = pyqtSignal(float, str)   # (balance, currency)
    failed = pyqtSignal(str)          # message d'erreur

    def run(self):
        cfg = load_config()
        key = cfg.get("api_key", "").strip()
        if not key:
            self.failed.emit("no_key")
            return
        cached = get_cached_balance()
        if cached:
            self.result.emit(*cached)
            return
        try:
            bal, cur = _fetch_balance(key)
            self.result.emit(bal, cur)
        except Exception as e:
            self.failed.emit(str(e))
