"""
core/media_provider.py — Distributeurs de génération VIDÉO (fal.ai, PiAPI…).

fal.ai reste le SOCLE : distributeur par défaut, et REPLI automatique quand le
moteur demandé n'est pas couvert par le distributeur choisi (jamais de bascule
muette : l'appelant peut afficher `active_video_provider()` ≠ choix utilisateur).

Le choix se fait dans Paramètres → avancés (config "video_provider") ; chaque
distributeur alternatif a sa clé API dédiée (config "<id>_key").

⚠ Les uploads de fichiers locaux (images de référence, keyframes, clips)
passent TOUJOURS par le CDN fal.ai (URLs publiques) — les distributeurs
alternatifs reçoivent ces URLs. Une clé fal.ai reste donc nécessaire dès
qu'un plan envoie des images ; le t2v pur fonctionne sans.

Grilles de prix : indicatives, comme core/pricing.py (source : docs publiques
des distributeurs — PiAPI vérifié le 2026-07-16).
"""

from core.config import load_config

# ── Registre des distributeurs ────────────────────────────────────────────────

PROVIDERS: dict[str, dict] = {
    "fal": {
        "label":   "fal.ai (par défaut)",
        "key_cfg": "api_key",
        "site":    "fal.ai",
    },
    "piapi": {
        "label":   "PiAPI (low cost)",
        "key_cfg": "piapi_key",
        "site":    "piapi.ai",
    },
}

_DEFAULT = "fal"

# Moteurs PANDORA couverts par chaque distributeur alternatif (fal couvre tout).
# PiAPI : Seedance 2 standard + fast (doc piapi.ai/docs/seedance-api/seedance-2).
_COVERAGE: dict[str, set] = {
    "piapi": {"seedance-2.0", "seedance-2.0-fast"},
}

# Grilles $/s par distributeur → moteur → résolution (mêmes clés que
# core/pricing._PER_SECOND ; fal = grille de core/pricing, non dupliquée ici).
_PER_SECOND: dict[str, dict] = {
    "piapi": {
        "seedance-2.0":      {"1080p": 0.50, "720p": 0.20, "480p": 0.10},
        "seedance-2.0-fast": {"720p": 0.16, "480p": 0.08},
    },
}


# ── Services PANDORA par distributeur (pour le mode MONO) ────────────────────
# Un « service » = une intégration réelle de PANDORA (onglet du Studio, page).
# fal couvre tout ; les alternatifs ne couvrent que ce que NOS backends savent
# leur envoyer aujourd'hui. Sert au grisage des onglets en mono-distributeur.
SERVICES: dict[str, str] = {
    "video_seedance": "Générer depuis Storyboard/Séquences (Seedance 2.0)",
    "video_engines":  "Génération directe (moteurs multiples)",
    "edit_clips":     "Modifier des clips",
    "upscale":        "Upscaling",
    "sound":          "Sound Design (ElevenLabs, Mirelo, MMAudio…)",
    "music":          "Musique IA",
    "images":         "Image IA / portraits / moods",
}

_PROVIDER_SERVICES: dict[str, set] = {
    "fal":   set(SERVICES),
    "piapi": {"video_seedance"},
}


# ── Sélection ─────────────────────────────────────────────────────────────────

def get_video_provider() -> str:
    """Distributeur vidéo CHOISI dans la config ("fal" par défaut)."""
    pid = (load_config().get("video_provider") or _DEFAULT).strip().lower()
    return pid if pid in PROVIDERS else _DEFAULT


def get_distribution_mode() -> str:
    """"multi" (défaut) : fal.ai + alternatifs, repli automatique.
    "mono" : le distributeur choisi est le SEUL utilisé — les services qu'il
    ne couvre pas sont INDISPONIBLES (grisés) au lieu de replier sur fal."""
    m = (load_config().get("distribution_mode") or "multi").strip().lower()
    return m if m in ("multi", "mono") else "multi"


def service_available(service: str) -> tuple[bool, str]:
    """(disponible, message_ui). Toujours disponible en multi. En mono, dépend
    de la couverture du distributeur choisi ; le message explique le grisage."""
    if get_distribution_mode() == "multi":
        return True, ""
    pid = get_video_provider()
    if service in _PROVIDER_SERVICES.get(pid, set()):
        return True, ""
    return False, (
        f"Indisponible en mono-distributeur ({provider_label(pid)}) : ce service "
        f"est servi par fal.ai. Repassez en « Multi-distributeurs » dans "
        f"Paramètres → avancés pour le réactiver."
    )


def mono_blocked_engine(engine: str) -> str:
    """En mode MONO : message d'erreur si ce MOTEUR vidéo ne peut pas être servi
    par le distributeur choisi (non couvert, ou clé manquante) ; "" sinon.
    En multi : jamais bloqué (repli fal). Appelé par api/real.py AVANT l'appel."""
    if get_distribution_mode() != "mono":
        return ""
    pid = get_video_provider()
    if pid == "fal":
        return ""
    if not provider_covers(pid, engine):
        return (f"Moteur « {engine} » indisponible chez {provider_label(pid)} "
                f"(mode mono-distributeur). Choisis Seedance 2.0, ou repasse en "
                f"« Multi-distributeurs » dans Paramètres → avancés.")
    if not provider_key(pid):
        return (f"Clé {provider_label(pid)} manquante — renseigne-la dans "
                f"Paramètres → avancés, ou repasse en « Multi-distributeurs ».")
    return ""


def provider_covers(provider_id: str, engine: str) -> bool:
    if provider_id == "fal":
        return True
    return (engine or "").strip() in _COVERAGE.get(provider_id, set())


def active_video_provider(engine: str = "seedance-2.0") -> str:
    """Distributeur EFFECTIF pour ce moteur.

    Multi (défaut) : le choix utilisateur s'il couvre le moteur ET que sa clé
    est renseignée, sinon repli fal. Mono : TOUJOURS le distributeur choisi —
    le blocage précis (moteur non couvert, clé absente) est porté par
    mono_blocked_engine(), jamais par un repli silencieux."""
    pid = get_video_provider()
    if pid == "fal":
        return "fal"
    if get_distribution_mode() == "mono":
        return pid
    if not provider_covers(pid, engine):
        return "fal"
    if not provider_key(pid):
        return "fal"
    return pid


def provider_key(provider_id: str) -> str:
    meta = PROVIDERS.get(provider_id) or {}
    return (load_config().get(meta.get("key_cfg", "")) or "").strip()


def provider_label(provider_id: str) -> str:
    return (PROVIDERS.get(provider_id) or {}).get("label", provider_id)


def provider_site(provider_id: str) -> str:
    return (PROVIDERS.get(provider_id) or {}).get("site", provider_id)


# ── Prix ──────────────────────────────────────────────────────────────────────

def price_per_second(engine: str, resolution: str) -> tuple[float | None, str]:
    """($/s, distributeur_effectif) pour (moteur, résolution).

    Retourne la grille du distributeur EFFECTIF (repli fal inclus) ; None en
    $/s si le moteur est facturé au clip (délégué à core/pricing)."""
    pid = active_video_provider(engine)
    if pid != "fal":
        rates = _PER_SECOND.get(pid, {}).get((engine or "").strip())
        if rates:
            res = (resolution or "").strip()
            rate = rates.get(res) or rates.get(res.lower())
            if rate is not None:
                return rate, pid
            # Résolution non couverte chez l'alternatif (ex. 1080p en fast)
            # → grille fal pour rester honnête sur le prix réellement payé.
    from core import pricing as _fal_pricing
    return _fal_pricing.price_per_second(engine, resolution), "fal"
