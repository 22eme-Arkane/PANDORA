"""
core/flux3_family.py — Famille vidéo Flux 3 (Black Forest Labs) sur fal.ai.

Relevé sur les schémas OpenAPI publiés par fal le 2026-08-09 (sortie 2026-08-04).

CE QUI REND CETTE FAMILLE INTÉRESSANTE POUR UN FILM
---------------------------------------------------
Un palier **BROUILLON** à 0,06 $/s, puis un **AFFINAGE** qui reprend le
brouillon et le rend en pleine qualité. Sur un découpage de 75 plans de 5 s :

    tout en brouillon         375 s × 0,06 = 22,50 $
    affiner 40 plans retenus  200 s × 0,29 = 58,00 $
                                     total ≈ 80,50 $
    contre tout en 1080p      375 s × 0,29 = 108,75 $

L'économie compte, mais l'essentiel est ailleurs : on ITÈRE à bas coût et on
ne paie le prix fort que sur les plans gardés — au lieu de payer plein tarif
des prises qu'on jette.

⚠ L'affinage ne reprend PAS une URL de vidéo : le brouillon renvoie un
`draft_cache_url` (paquet de cache chiffré) que `draft-enhance` consomme. Il
faut donc CONSERVER ce jeton à côté du clip brouillon, sinon l'affinage est
impossible et il faut tout regénérer.

AUTRES POINTS NOTABLES
----------------------
· `keyframes-to-video` accepte jusqu'à **10 images épinglées** à un
  `frame_index` — bien au-delà des deux plaques du mapping Live actuel.
· `first-last-frame-to-video` correspond exactement au raccord début+fin
  déjà modélisé par `engine_caps.end_frame`.
· `safety_tolerance` va de **0 à 4** ici, alors que Seedance utilise 1 à 6 :
  ne jamais recopier la valeur d'un moteur à l'autre.
· `extend-video` n'accepte qu'un MP4 < 50 Mo et < 15 s.
"""
from __future__ import annotations

_BASE = "blackforestlabs/flux-3"

# Mode PANDORA → chemin d'endpoint (hors palier brouillon).
_MODES = {
    "t2v":       f"{_BASE}/text-to-video",
    "i2v":       f"{_BASE}/image-to-video",
    "flf":       f"{_BASE}/first-last-frame-to-video",
    "keyframes": f"{_BASE}/keyframes-to-video",
    "ext":       f"{_BASE}/extend-video",
}

ENHANCE_ENDPOINT = f"{_BASE}/draft-enhance"

RESOLUTIONS = ("1080p", "720p")
DURATIONS   = tuple(str(s) for s in range(5, 21))
ASPECTS     = ("auto", "21:9", "2:1", "16:9", "4:3", "1:1", "3:4", "9:16")

MAX_KEYFRAMES = 10
SAFETY_MIN, SAFETY_MAX = 0, 4          # ⚠ échelle propre à Flux 3

# $/s relevés sur fal le 2026-08-09.
_PRICE_FULL   = {"720p": 0.17, "1080p": 0.29}
_PRICE_EXTEND = {"720p": 0.41, "1080p": 0.53}
_PRICE_DRAFT        = 0.06             # 720p, tous modes sauf extension
_PRICE_DRAFT_EXTEND = 0.12
_PRICE_ENHANCE      = 0.29             # rendu pleine qualité 1080p, audio inclus


def endpoint(mode: str, draft: bool = False) -> str:
    """Endpoint Flux 3 pour un mode PANDORA. `draft=True` → palier brouillon.

    Repli sur le text-to-video pour un mode inconnu, jamais d'URL inventée.
    """
    base = _MODES.get((mode or "t2v").strip(), _MODES["t2v"])
    return f"{base}/draft" if draft else base


def price_per_second(mode: str, resolution: str, draft: bool = False) -> float:
    """$/s indicatif. L'extension est nettement plus chère que les autres modes."""
    res = (resolution or "720p").strip().lower()
    is_ext = (mode or "").strip() == "ext"
    if draft:
        return _PRICE_DRAFT_EXTEND if is_ext else _PRICE_DRAFT
    table = _PRICE_EXTEND if is_ext else _PRICE_FULL
    return table.get(res, table["720p"])


def enhance_price_per_second() -> float:
    """$/s de l'affinage d'un brouillon (rendu 1080p, audio compris)."""
    return _PRICE_ENHANCE


def clamp_resolution(resolution: str) -> str:
    """Flux 3 ne connaît que 720p et 1080p — 4K y est impossible."""
    res = (resolution or "").strip().lower()
    return res if res in RESOLUTIONS else "720p"


def clamp_duration(seconds) -> str:
    """Ramène une durée dans la fenêtre 5–20 s acceptée par Flux 3.

    Le storyboard PANDORA autorise des plans de 2 s : les envoyer tels quels
    ferait refuser l'appel. On rabat sur le minimum du moteur.
    """
    try:
        v = int(round(float(seconds)))
    except (TypeError, ValueError):
        v = 5
    return str(min(20, max(5, v)))


def clamp_safety(value) -> int:
    """Ramène une tolérance dans l'échelle 0–4 de Flux 3.

    Piège réel : Seedance utilise 1–6. Recopier un « 6 » ici serait hors
    domaine et ferait échouer l'appel.
    """
    try:
        v = int(value)
    except (TypeError, ValueError):
        v = 2
    return min(SAFETY_MAX, max(SAFETY_MIN, v))


def estimate(mode: str, resolution: str, seconds: float,
             draft: bool = False) -> float:
    """Coût indicatif d'un plan (USD)."""
    return price_per_second(mode, resolution, draft) * max(0.0, float(seconds or 0))


def estimate_draft_then_enhance(n_shots: int, seconds_each: float,
                                kept_ratio: float = 1.0) -> dict:
    """Compare « tout en pleine qualité » et « brouillon puis affinage ».

    Sert à ANNONCER l'économie dans l'interface plutôt qu'à la promettre :
    le calcul est explicite et vérifiable par l'utilisateur.
    """
    n = max(0, int(n_shots or 0))
    s = max(0.0, float(seconds_each or 0))
    total_s = n * s
    kept_s  = total_s * min(1.0, max(0.0, float(kept_ratio)))
    drafts  = total_s * _PRICE_DRAFT
    enhance = kept_s * _PRICE_ENHANCE
    return {
        "tout_pleine_qualite": total_s * _PRICE_FULL["1080p"],
        "brouillons":          drafts,
        "affinage":            enhance,
        "total_deux_temps":    drafts + enhance,
    }
