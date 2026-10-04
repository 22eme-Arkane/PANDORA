"""
api/distributors.py — Point d'entrée UNIQUE vers les distributeurs vidéo
alternatifs (BytePlus, Runware, PiAPI) : génération et test de clé.

La couverture, les prix et le choix du distributeur vivent dans
core/media_provider ; ici, seulement l'appel réseau de chacun. fal.ai reste
appelé par api/real.py (fal_client).
"""
from __future__ import annotations


def runner(provider_id: str):
    """Fonction run(mode, model, args, api_key, emit_progress, is_cancelled)."""
    if provider_id == "byteplus":
        from api.byteplus import run
    elif provider_id == "runware":
        from api.runware import run
    elif provider_id == "piapi":
        from api.piapi import run
    else:
        raise KeyError(f"distributeur inconnu : {provider_id}")
    return run


def test_key(provider_id: str, api_key: str) -> tuple[bool, str]:
    """(ok, message) — test GRATUIT : aucune génération n'est lancée."""
    if not (api_key or "").strip():
        return False, "Aucune clé saisie."
    if provider_id == "byteplus":
        from api.byteplus import test_key as _t
    elif provider_id == "runware":
        from api.runware import test_key as _t
    elif provider_id == "piapi":
        from api.piapi import test_key as _t
    else:
        return False, f"Distributeur inconnu : {provider_id}"
    return _t(api_key.strip())
