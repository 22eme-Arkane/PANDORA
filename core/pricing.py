"""
core/pricing.py — Estimation INDICATIVE du coût de génération vidéo (fal.ai).

⚠ Les tarifs fal.ai ÉVOLUENT : ces valeurs sont approximatives et servent à donner
un ordre de grandeur AVANT génération. Toujours vérifier le prix réel sur fal.ai.
Sources : Manuel d'utilisation (dialog_user_manual) + libellés des combos de
résolution (tab_t2v_live._ENGINE_RESOLUTIONS).

Deux modes de facturation :
  - à la SECONDE (Seedance, PixVerse, Happy Horse, Kling…) → prix × durée totale ;
  - au CLIP (Veo 3.1, Sora 2 : durée fixe) → prix × nombre de clips.
"""

# $/seconde par moteur × résolution (valeurs API minuscules « 4k/1080p/720p/480p »).
_PER_SECOND = {
    "seedance-2.0":      {"4k": 1.55, "1080p": 0.60, "720p": 0.30, "480p": 0.16},
    "seedance-2.0-fast": {"720p": 0.18, "480p": 0.09},
    "pixverse-v6":       {"1080p": 0.115, "720p": 0.075, "480p": 0.025},
    "happy-horse-1.0":   {"1080p": 0.28, "720p": 0.14},
    "kling-v3-pro":      {"1080p": 0.15},          # manuel : $0.112–0.196/s → ~milieu
    "kling-o3-4k":       {"4k": 0.42, "4K": 0.42},
}
# $/clip pour les moteurs à durée fixe (facturés à la vidéo).
_PER_VIDEO = {
    "veo-3.1": 1.00,
    "sora-2":  0.40,
}
_DEFAULT_PER_S = 0.30   # repli prudent (≈ Seedance 720p) pour un moteur inconnu


def price_per_second(engine: str, resolution: str) -> float | None:
    """$/s pour (moteur, résolution), ou None si le moteur est facturé au clip."""
    engine = (engine or "").strip()
    if engine in _PER_VIDEO:
        return None
    rates = _PER_SECOND.get(engine)
    if not rates:
        return _DEFAULT_PER_S
    res = (resolution or "").strip()
    return rates.get(res) or rates.get(res.lower()) or next(iter(rates.values()))


def estimate(engine: str, resolution: str, total_seconds: float,
             n_clips: int = 1) -> tuple[float, str]:
    """Coût INDICATIF total (USD) + mode de facturation.

    Tient compte du DISTRIBUTEUR choisi (Paramètres avancés) : si un
    distributeur alternatif (PiAPI…) couvre le moteur, c'est SA grille
    qui est utilisée — sinon la grille fal.ai ci-dessus.

    Retour : (coût_usd, mode) avec mode ∈ {"s", "clip", "approx"}.
      - "s"      : facturé à la seconde (prix connu) ;
      - "clip"   : facturé à la vidéo (durée fixe) ;
      - "approx" : moteur inconnu → repli prudent.
    """
    engine = (engine or "").strip()
    n_clips = max(1, int(n_clips or 1))
    total_seconds = max(0.0, float(total_seconds or 0.0))
    if engine in _PER_VIDEO:
        return _PER_VIDEO[engine] * n_clips, "clip"
    # Grille du distributeur actif (import paresseux — pas de cycle au chargement)
    try:
        from core import media_provider as _mp
        if _mp.active_video_provider(engine) != "fal":
            _rate, _pid = _mp.price_per_second(engine, resolution)
            if _pid != "fal" and _rate is not None:
                return _rate * total_seconds, "s"
    except Exception:
        pass
    rates = _PER_SECOND.get(engine)
    if rates:
        res = (resolution or "").strip()
        rate = rates.get(res) or rates.get(res.lower()) or next(iter(rates.values()))
        return rate * total_seconds, "s"
    return _DEFAULT_PER_S * total_seconds, "approx"


def _active_site(engine: str) -> str:
    """Nom du site du distributeur EFFECTIF pour ce moteur (mention du rappel)."""
    try:
        from core import media_provider as _mp
        return _mp.provider_site(_mp.active_video_provider(engine))
    except Exception:
        return "fal.ai"


def format_estimate(engine_label: str, engine_key: str, resolution: str,
                    total_seconds: float, n_clips: int = 1) -> str:
    """Message d'estimation prêt à afficher (français). Toujours accompagné du
    rappel : prix INDICATIF, vérifier sur le site du distributeur ACTIF
    (les tarifs peuvent évoluer)."""
    cost, mode = estimate(engine_key, resolution, total_seconds, n_clips)
    plan_word = "plan" if n_clips <= 1 else "plans"
    eng = (engine_label or engine_key or "moteur").strip()
    res = (resolution or "").strip()
    site = _active_site(engine_key)
    head = f"💰  ≈ ${cost:.2f}  ·  {n_clips} {plan_word}"
    if mode != "clip":
        head += f" (~{total_seconds:.0f}s)"
    head += f"  ·  {eng}"
    if res:
        head += f" · {res}"
    if site != "fal.ai":
        head += f" · via {site}"
    return (head + f"  —  estimation INDICATIVE : vérifie le prix réel sur "
            f"{site} (les tarifs peuvent évoluer).")
