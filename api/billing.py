"""
api/billing.py — Vérification du solde fal.ai avant génération.

Endpoint : GET https://api.fal.ai/v1/account/billing?expand=credits
Auth     : Authorization: Key <ADMIN_API_KEY>

⚠  Requiert une clé admin fal.ai (full-permission), pas une clé d'inférence restreinte.
   Sur le dashboard fal.ai → Settings → API Keys → créer une clé sans restrictions.
"""
import time
import requests
from PyQt6.QtCore import QThread, pyqtSignal
from core.config import load_config

# Seuils en USD
WARN_THRESHOLD  = 5.0
BLOCK_THRESHOLD = 0.0

_FAL_BILLING_URL = "https://api.fal.ai/v1/account/billing"
_DASHBOARD_URL   = "https://fal.ai/dashboard/billing"

_cache: dict = {}
_CACHE_TTL   = 30  # secondes


def get_cached_balance() -> tuple[float, str] | None:
    if "ts" in _cache and time.time() - _cache["ts"] < _CACHE_TTL:
        return _cache["balance"], _cache["currency"]
    return None


def invalidate_cache():
    _cache.clear()


def _fetch_balance(api_key: str) -> tuple[float, str]:
    """Appel HTTP synchrone — à appeler uniquement depuis un QThread.

    Lève ValueError avec un code sémantique :
      "no_key"             — clé vide
      "invalid_key"        — 401 Unauthorized
      "admin_key_required" — 403 Forbidden (clé d'inférence, pas admin)
      "<message>"          — autre erreur réseau/parsing
    """
    r = requests.get(
        _FAL_BILLING_URL,
        params={"expand": "credits"},
        headers={"Authorization": f"Key {api_key}"},
        timeout=8,
    )

    if r.status_code == 401:
        raise ValueError("invalid_key")
    if r.status_code == 403:
        raise ValueError("admin_key_required")
    if not r.ok:
        raise ValueError(f"HTTP {r.status_code}")

    data = r.json()
    credits = data.get("credits", {})
    bal = float(credits.get("current_balance", 0))
    cur = credits.get("currency", "USD")
    _cache.update({"balance": bal, "currency": cur, "ts": time.time()})
    return bal, cur


class BillingCheckWorker(QThread):
    result           = pyqtSignal(float, str)  # (balance, currency)
    failed           = pyqtSignal(str)         # "no_key" | "invalid_key" | "admin_key_required"
    network_error    = pyqtSignal(str)         # erreur réseau — affichée dans tooltip

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
        except ValueError as e:
            code = str(e)
            if code in ("invalid_key", "admin_key_required"):
                self.failed.emit(code)
            else:
                self.network_error.emit(code)
        except Exception as e:
            self.network_error.emit(str(e)[:80])
