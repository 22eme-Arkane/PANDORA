"""core/h3_family.py — MiniMax H3 (Hailuo 3.0) sur fal.ai : la table de famille.

Comme `seedance_family` et `flux3_family` : un seul endroit qui sait ce que
chaque palier accepte — chemins, résolutions, durées, références, tarifs. Les
workers, la grammaire, le briefing du découpage et « Coût du projet » lisent
ici, jamais de mémoire.

Relevé le 2026-09-13 sur les schémas OpenAPI et les pages de tarif de fal.

Trois paliers :
  - `minimax-h3`            : 480P/768P natifs, **2K et 4K = upscale du 768P**
                              (fal le dit en toutes lettres — ne pas le vendre
                              comme du 4K natif). Réfs : 9 images + 3 vidéos +
                              3 audios, désignées « Image 1, Image 2 » dans le
                              prompt.
  - `minimax-h3-max`        : 480P/768P natifs, 1080P = raffinement latent.
                              `prompt_expansion_mode` OBLIGATOIRE (pas de fast).
  - `minimax-h3-max-turbo`  : idem Max, moitié prix.

Durée 5–15 s pour tous. Ratios 21:9 → 9:16 (Seedance n'a pas le 21:9).

⚠ TARIFS : H3 Max et Turbo étaient en promotion −75 % jusqu'au 14/09/2026.
On enregistre le tarif PLEIN — c'est celui qui restera, et sous-estimer un coût
est la seule erreur qu'on ne se pardonne pas dans « Coût du projet ».
"""

from __future__ import annotations

# ── Chemins fal ──────────────────────────────────────────────────────────────
# Namespace « minimax/… » — SANS le préfixe « fal-ai/ » des Hailuo 2.x.
_ENDPOINTS = {
    "minimax-h3": {
        "t2v": "minimax/h3/text-to-video",
        "i2v": "minimax/h3/image-to-video",
        "ref": "minimax/h3/reference-to-video",
    },
    "minimax-h3-max": {
        "t2v": "minimax/h3-max/text-to-video",
        "i2v": "minimax/h3-max/image-to-video",
        "ref": "minimax/h3-max/reference-to-video",
        "cam": "minimax/h3-max/camera-controls",
    },
    "minimax-h3-max-turbo": {
        "t2v": "minimax/h3-max-turbo/text-to-video",
        "i2v": "minimax/h3-max-turbo/image-to-video",
    },
}

# Résolutions : valeur PANDORA (minuscule, celle des menus et de pricing) →
# valeur attendue par fal (majuscule). L'ordre est celui du menu.
_RESOLUTIONS = {
    "minimax-h3":           [("480p", "480P"), ("768p", "768P"), ("2k", "2K"), ("4k", "4K")],
    "minimax-h3-max":       [("480p", "480P"), ("768p", "768P"), ("1080p", "1080P")],
    "minimax-h3-max-turbo": [("480p", "480P"), ("768p", "768P"), ("1080p", "1080P")],
}

#: Résolutions qui ne sont PAS une génération native mais un agrandissement.
UPSCALED = {"minimax-h3": ("2k", "4k")}

# $/s par résolution — tarif plein, hors promotion.
_PRICE_PER_S = {
    "minimax-h3":           {"480p": 0.05, "768p": 0.06, "2k": 0.13, "4k": 0.16},
    "minimax-h3-max":       {"480p": 0.05, "768p": 0.08, "1080p": 0.16},
    "minimax-h3-max-turbo": {"480p": 0.025, "768p": 0.04, "1080p": 0.08},
}

ASPECT_RATIOS = ("16:9", "21:9", "4:3", "1:1", "3:4", "9:16")
DURATION_MIN, DURATION_MAX = 5, 15
MAX_REF_IMAGES = 9
MAX_REF_VIDEOS = 3
MAX_REF_AUDIOS = 3
#: Réfs gratuites avant facturation (H3 : 5 images ; Max : 4 096 jetons ≈ 4 images 1024²).
FREE_REF_IMAGES = {"minimax-h3": 5, "minimax-h3-max": 4}
EXTRA_REF_IMAGE_USD = {"minimax-h3": 0.08, "minimax-h3-max": 0.02}

#: Modes de réécriture du prompt côté fal. « quality » peut prendre ~30 s.
EXPANSION_MODES = {
    "minimax-h3":           ("fast", "balanced", "quality"),
    "minimax-h3-max":       ("balanced", "quality"),
    "minimax-h3-max-turbo": ("balanced", "quality"),
}
#: Le champ est REQUIS sur Max et Turbo — l'omettre est un rejet 422.
EXPANSION_REQUIRED = ("minimax-h3-max", "minimax-h3-max-turbo")

LABELS = {
    "minimax-h3":           "MiniMax H3",
    "minimax-h3-max":       "MiniMax H3 Max",
    "minimax-h3-max-turbo": "MiniMax H3 Max Turbo",
}


def is_h3(engine_key: str) -> bool:
    return (engine_key or "").startswith("minimax-h3")


def tiers() -> list[str]:
    return list(_ENDPOINTS)


def endpoint(tier: str, mode: str) -> str:
    """Chemin fal d'un mode. Chaîne vide si ce palier n'a pas ce mode : Turbo n'a
    pas de reference-to-video, et l'appelant doit le savoir plutôt que de
    tomber sur un 404."""
    return _ENDPOINTS.get(tier, {}).get(mode, "")


def resolutions(tier: str) -> list[str]:
    return [p for p, _ in _RESOLUTIONS.get(tier, [])]


def fal_resolution(tier: str, resolution: str) -> str:
    """« 768p » (PANDORA) → « 768P » (fal). Repli sur le 768P natif."""
    table = dict(_RESOLUTIONS.get(tier, []))
    return table.get((resolution or "").lower().split()[0], "768P")


def clamp_resolution(tier: str, resolution: str) -> str:
    r = (resolution or "").lower().split()[0] if resolution else ""
    return r if r in resolutions(tier) else "768p"


def is_upscaled(tier: str, resolution: str) -> bool:
    return (resolution or "").lower() in UPSCALED.get(tier, ())


def clamp_duration(seconds) -> int:
    try:
        s = int(round(float(seconds)))
    except (TypeError, ValueError):
        s = DURATION_MIN
    return max(DURATION_MIN, min(DURATION_MAX, s))


def clamp_expansion(tier: str, mode: str) -> str:
    modes = EXPANSION_MODES.get(tier, ("balanced",))
    m = (mode or "").strip().lower()
    return m if m in modes else "balanced"


def price_per_second(tier: str, resolution: str) -> float:
    return _PRICE_PER_S.get(tier, {}).get(clamp_resolution(tier, resolution), 0.0)


def estimate(tier: str, resolution: str, seconds: float, n_ref_images: int = 0) -> float:
    """Coût estimé d'un plan, références comprises au-delà de la franchise."""
    cost = clamp_duration(seconds) * price_per_second(tier, resolution)
    free = FREE_REF_IMAGES.get(tier, 0)
    extra = max(0, int(n_ref_images or 0) - free)
    cost += extra * EXTRA_REF_IMAGE_USD.get(tier, 0.0)
    return round(cost, 4)


def price_table() -> dict:
    """Vue pour core/pricing : clé moteur → {résolution: $/s}."""
    return {k: dict(v) for k, v in _PRICE_PER_S.items()}


def annotate_roles_with_tokens(ref_roles: list[str]) -> list[str]:
    """« Léa (Image 1) », « Le dojo (Image 2) »… — la désignation attendue par
    H3, qui numérote les références dans l'ordre d'envoi. Même rôle que la
    version Seedance 2.5 (« @Image1 »), avec la convention de MiniMax."""
    return [f"{r} (Image {i + 1})" for i, r in enumerate(ref_roles or [])]
