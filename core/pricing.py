"""
core/pricing.py — Estimation INDICATIVE du coût de génération vidéo (fal.ai).

⚠ Les tarifs fal.ai ÉVOLUENT : ces valeurs sont approximatives et servent à donner
un ordre de grandeur AVANT génération. Toujours vérifier le prix réel sur fal.ai.

SOURCE DE VÉRITÉ = la grille publiée par fal.ai (catalogue fal, champ
`pricingInfoOverride` de chaque endpoint), relevée le 2026-08-09.
⚠ Ce fichier est le SEUL point de vérité ; les libellés de résolution des
onglets et le manuel ne font que le RECOPIER. Ne jamais faire l'inverse : la
docstring citait auparavant le manuel et les combos comme sources, et c'est
exactement par là qu'une grille périmée (1080p à $0.60 au lieu de $0.682,
Fast à $0.18 au lieu de $0.2419) a survécu dans quinze fichiers.
À chaque mise à jour : corriger ICI, puis répercuter dans les libellés.

Deux modes de facturation :
  - à la SECONDE (Seedance, PixVerse, Happy Horse, Kling…) → prix × durée totale ;
  - au CLIP (Veo 3.1, Sora 2 : durée fixe) → prix × nombre de clips.
"""

# $/seconde par moteur × résolution (valeurs API minuscules « 4k/1080p/720p/480p »).
#
# ⚠ Grille Seedance RELEVÉE SUR fal.ai le 2026-08-09 (API du catalogue fal,
# champ `pricingInfoOverride` des endpoints bytedance/seedance-2.0/*). Les
# valeurs précédentes sous-estimaient le 1080p de 12 % et le Fast de 34 %.
# fal facture en réalité au TOKEN : tokens = (largeur × hauteur × durée × 24)
# / 1024, puis $0.014/1000 tokens (480p/720p/1080p), $0.008/1000 (4k) pour le
# standard, $0.0112/1000 pour le Fast, $0.007/1000 pour le Mini. Les $/s
# ci-dessous sont cette formule appliquée aux définitions usuelles — fal publie
# lui-même 720p et 1080p en $/s, et les deux concordent à 0,3 % près.
_PER_SECOND = {
    # Seedance 2.5 (sortie fal 2026-08-07) : 720p MAXIMUM — ni 1080p ni 4K —
    # et 56 % plus cher que la 2.0 à résolution égale. Ce n'est pas un
    # remplacement : voir core/seedance_family.
    "seedance-2.5":      {"720p": 0.4730, "480p": 0.2205},
    "seedance-2.0":      {"4k": 1.56, "1080p": 0.682, "720p": 0.3034, "480p": 0.135},
    "seedance-2.0-fast": {"720p": 0.2419, "480p": 0.108},
    "seedance-2.0-mini": {"720p": 0.1547, "480p": 0.0721},
    "pixverse-v6":       {"1080p": 0.115, "720p": 0.075, "480p": 0.025},
    # Happy Horse : la clé reste « -1.0 » car elle est ENREGISTRÉE dans les
    # plans et l'historique des projets existants — la renommer les ferait
    # retomber sur le repli. Le moteur appelé est bien la v1.1 depuis le
    # 2026-08-09 (api/video_engines), d'où le 1080p à $0.18 au lieu de $0.28.
    "happy-horse-1.0":   {"1080p": 0.18, "720p": 0.14},
    # Kling v3 Turbo (fal 2026-06-17) : palier rapide du Kling déjà intégré.
    "kling-v3-turbo-pro":      {"1080p": 0.14},
    "kling-v3-turbo-standard": {"1080p": 0.112},
    # Flux 3 (Black Forest Labs, fal 2026-08-04). Le détail par mode — dont
    # l'extension, bien plus chère, et le palier brouillon à 0,06 $/s — vit
    # dans core/flux3_family ; ici seul le tarif du mode courant.
    "flux-3":       {"1080p": 0.29, "720p": 0.17},
    "flux-3-draft": {"720p": 0.06},
    "kling-v3-pro":      {"1080p": 0.15},          # manuel : $0.112–0.196/s → ~milieu
    "kling-o3-4k":       {"4k": 0.42, "4K": 0.42},
}
# MiniMax H3 (fal 2026-09-13) : la grille vit dans core/h3_family — UNE source,
# lue ici plutôt que recopiée. Tarif PLEIN (la promo −75 % de lancement de
# H3 Max/Turbo expirait le 14/09/2026 ; sous-estimer un coût est la seule
# erreur impardonnable dans « Coût du projet »).
try:
    from core import h3_family as _h3
    _PER_SECOND.update(_h3.price_table())
except Exception:
    pass
# H3 en LOCAL (stable-diffusion.cpp sur la machine) : rien n'est facturé. Sans
# cette entrée, un moteur inconnu retombe sur _DEFAULT_PER_S = 0,30 $/s et le
# journal afficherait un coût pour une génération gratuite — même famille
# d'erreur que le prix des images lu dans le numéro de version (30/08/2026).
_PER_SECOND["minimax-h3-local"] = {"480p": 0.0, "768p": 0.0, "1080p": 0.0,
                                   "rapide": 0.0, "qualite": 0.0}
# ComfyUI (13/09/2026) : rendu sur la machine de l'utilisateur, rien n'est facturé.
_PER_SECOND["comfy"] = {"480p": 0.0, "768p": 0.0, "1080p": 0.0, "": 0.0}
# Moteurs de la famille _SimpleFalVideoWorker (api/video_engines) qui portaient
# leur tarif UNIQUEMENT dans leur attribut PRICE_PER_S : absents de la grille,
# ils étaient journalisés au repli 0,30 $/s (constat 14/09/2026). Les valeurs
# ci-dessous sont celles des workers ; le harnais vérifie qu'elles ne divergent
# pas de plus de 10 % — deux chiffres différents avant et après seraient un
# mensonge. Wan 2.7 n'annonce de tarif nulle part : il reste sur le repli.
_PER_SECOND.update({
    "seedance-1.5-pro":  {"720p": 0.052, "480p": 0.052},
    "ltx-2":             {"1080p": 0.04, "720p": 0.04, "4k": 0.04},
    "gemini-omni-flash": {"720p": 0.125, "1080p": 0.125},
    "grok-video":        {"720p": 0.07, "480p": 0.05},
})
# $/clip pour les moteurs à durée fixe (facturés à la vidéo).
_PER_VIDEO = {
    "veo-3.1": 1.00,
    "sora-2":  0.40,
    # Hailuo 2.3 Pro est facturé AU CLIP (~0,49 $), pas à la seconde : sans
    # cette entrée il était journalisé à 0,30 $/s × durée (constat 14/09/2026).
    "hailuo-2.3-pro": 0.49,
}
_DEFAULT_PER_S = 0.30   # repli prudent (≈ Seedance 720p) pour un moteur inconnu


#: Suffixes de MODE que les workers accolent à leur clé de moteur dans le dict
#: émis (« seedance-1.5-pro-t2v », « minimax-h3-i2v »). Le journal de coût
#: reçoit cette clé composée ; la grille est indexée sans suffixe.
_MODE_SUFFIXES = ("-t2v", "-i2v", "-ref", "-ext", "-r2v", "-flf2v")


def canonical_engine(engine: str) -> str:
    """Clé de grille d'un moteur tel que les workers le nomment.

    ⚠ Bug trouvé le 13/09/2026 : sans ce retrait, TOUS les moteurs de la
    famille _SimpleFalVideoWorker (Seedance 1.5, LTX-2, Wan, Hailuo, Mini,
    Gemini, Grok, H3) tombaient sur _DEFAULT_PER_S = 0,30 $/s dans « Coût du
    projet », quel que soit leur tarif réel — même famille d'erreur que le
    prix des images lu dans le numéro de version (30/08/2026).
    """
    e = (engine or "").strip()
    for suf in _MODE_SUFFIXES:
        if e.lower().endswith(suf):
            return e[: -len(suf)]
    return e


def price_per_second(engine: str, resolution: str) -> float | None:
    """$/s pour (moteur, résolution), ou None si le moteur est facturé au clip."""
    engine = canonical_engine(engine)
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
    # C'est CETTE fonction que le journal de coût appelle (core/history) : la
    # clé arrive avec son suffixe de mode (« hailuo-2.3-pro-t2v ») et doit être
    # canonisée ICI, pas seulement dans price_per_second — sinon Hailuo (au
    # clip), ComfyUI et H3 local (0 $) tombaient tous à 0,30 $/s.
    engine = canonical_engine(engine)
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
