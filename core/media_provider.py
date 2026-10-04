"""
core/media_provider.py — Distributeurs de génération VIDÉO.

Un DISTRIBUTEUR revend l'accès à un moteur : Seedance appartient à ByteDance,
fal.ai, BytePlus, Runware et PiAPI le revendent. Le moteur et son filtre de
contenu sont les mêmes partout ; seuls changent le prix, les options exposées
et la façon de recevoir les fichiers.

Relevé du 04/10/2026 (rapport « Distributeurs vidéo IA low cost ») — un plan
Seedance 2.5 de 30 s en 480p / 720p / 1080p :
  fal.ai     6,60 / 14,19 / 34,92 $
  BytePlus   3,08 /  6,93 / 17,06 $ HT (officiel ByteDance ; +20 % de TVA en
             compte personnel, plus de 30 $ de solde pour activer la 2.x)
  Runware    3,06 /  6,90 / 18,42 $
  PiAPI      4,50 / 10,50 / 24,00 $
Segmind (≈ Runware) est ÉCARTÉ : il n'accepte que des URL publiques, donc ne
recevrait aucune image sans le relais fal — exactement ce qui a cassé le
04/10/2026 (compte fal bloqué faute de solde : le mood n'est jamais parti chez
PiAPI, le plan a été généré et facturé sans lui).

fal.ai reste le SOCLE : distributeur par défaut. En MULTI-distributeurs, une
demande que le choix ne couvre pas part chez le moins cher des AUTRES
distributeurs configurés qui la couvre, sinon chez fal — le Studio l'affiche
et la progression nomme toujours le distributeur réellement appelé. En MONO,
le choix est le seul utilisé : ce qu'il ne couvre pas est BLOQUÉ, avec la
raison, jamais replié en silence.

COUVERTURE = (moteur, mode, résolution, son coupé), relevée champ par champ
dans la doc de chaque distributeur (04/10/2026) :
  · PiAPI en 2.5 n'a ni image de début/fin, ni interrupteur du son ;
  · Runware ne fait pas la prolongation / modification de clip (non vérifiée) ;
  · BytePlus et Runware vont jusqu'au 4K en 2.0, PiAPI s'arrête au 1080p.

Les fichiers locaux partent par le canal du distributeur (api/distrib_upload),
plus systématiquement par le stockage fal.
"""

from core.config import load_config

# ── Registre des distributeurs ────────────────────────────────────────────────

PROVIDERS: dict[str, dict] = {
    "fal": {
        "label":    "fal.ai (par défaut)",
        "short":    "fal.ai",
        "key_cfg":  "api_key",
        "site":     "fal.ai",
        "keys_url": "https://fal.ai/dashboard/keys",
        "blurb":    "Tous les moteurs (vidéo, image, son). Le plus complet, le plus cher "
                    "sur Seedance.",
    },
    "byteplus": {
        "label":    "BytePlus (officiel ByteDance)",
        "short":    "BytePlus",
        "key_cfg":  "byteplus_key",
        "site":     "byteplus.com",
        "keys_url": "https://console.byteplus.com/ark/region:ark+ap-southeast-1/apiKey",
        "blurb":    "Le vendeur OFFICIEL de Seedance : environ deux fois moins cher que "
                    "fal. Prix HT (+20 % de TVA en compte personnel) ; il faut plus de "
                    "30 $ de solde pour activer Seedance 2.x.",
    },
    "runware": {
        "label":    "Runware",
        "short":    "Runware",
        "key_cfg":  "runware_key",
        "site":     "runware.ai",
        "keys_url": "https://my.runware.ai/keys",
        "blurb":    "Revendeur au prix officiel de ByteDance, sans TVA affichée. Recharge "
                    "minimale 20 $. Ne fait pas la prolongation de clip.",
    },
    "piapi": {
        "label":    "PiAPI (low cost)",
        "short":    "PiAPI",
        "key_cfg":  "piapi_key",
        "site":     "piapi.ai",
        "keys_url": "https://piapi.ai/workspace",
        "blurb":    "Revendeur à bas prix. N'accepte que des liens publics vers les images "
                    "(dépôt réservé à l'abonnement Creator, sinon relais fal.ai).",
    },
}

#: Ordre d'affichage (Studio, Paramètres, onboarding).
ORDER: tuple[str, ...] = ("fal", "byteplus", "runware", "piapi")

_DEFAULT = "fal"

_ALL_MODES = frozenset({"t2v", "i2v", "ref", "ext"})

#: Couverture par distributeur alternatif → moteur PANDORA (fal couvre tout).
#: "res" : résolutions acceptées ; "audio_off" : le son peut être coupé.
_CAPS: dict[str, dict[str, dict]] = {
    "byteplus": {
        "seedance-2.5":      {"modes": _ALL_MODES, "res": {"480p", "720p", "1080p"},
                              "audio_off": True},
        "seedance-2.0":      {"modes": _ALL_MODES, "res": {"480p", "720p", "1080p", "4k"},
                              "audio_off": True},
        "seedance-2.0-fast": {"modes": _ALL_MODES, "res": {"480p", "720p"},
                              "audio_off": True},
    },
    "runware": {
        "seedance-2.5": {"modes": frozenset({"t2v", "i2v", "ref"}),
                         "res": {"480p", "720p", "1080p"}, "audio_off": True},
        "seedance-2.0": {"modes": frozenset({"t2v", "i2v", "ref"}),
                         "res": {"480p", "720p", "1080p", "4k"}, "audio_off": True},
    },
    "piapi": {
        "seedance-2.5":      {"modes": frozenset({"t2v", "ref", "ext"}),
                              "res": {"480p", "720p", "1080p"}, "audio_off": False},
        "seedance-2.0":      {"modes": _ALL_MODES, "res": {"480p", "720p", "1080p"},
                              "audio_off": True},
        "seedance-2.0-fast": {"modes": _ALL_MODES, "res": {"480p", "720p"},
                              "audio_off": True},
    },
}

#: Grilles $/s des distributeurs alternatifs (sans vidéo en entrée, son compris).
#: fal = grille de core/pricing, non dupliquée ici.
_PER_SECOND: dict[str, dict[str, dict[str, float]]] = {
    # Jetons × tarif officiel (grille BytePlus du 28/09/2026), en 16:9 : HT.
    "byteplus": {
        "seedance-2.5":      {"480p": 0.1028, "720p": 0.2311, "1080p": 0.5686},
        "seedance-2.0":      {"480p": 0.0703, "720p": 0.1512, "1080p": 0.3742,
                              "4k": 0.7776},
        "seedance-2.0-fast": {"480p": 0.0562, "720p": 0.1210},
    },
    # Fiches modèles Runware (04/10/2026).
    "runware": {
        "seedance-2.5": {"480p": 0.102, "720p": 0.23, "1080p": 0.614},
        "seedance-2.0": {"480p": 0.07, "720p": 0.16, "1080p": 0.40, "4k": 0.856},
    },
    # Docs PiAPI seedance-2 / seedance-25 (04/10/2026).
    "piapi": {
        "seedance-2.5":      {"480p": 0.15, "720p": 0.35, "1080p": 0.80},
        "seedance-2.0":      {"480p": 0.10, "720p": 0.20, "1080p": 0.50},
        "seedance-2.0-fast": {"480p": 0.048, "720p": 0.096},
    },
}

_MODE_LABELS = {
    "t2v": "le texte → vidéo",
    "i2v": "l'image de début / fin",
    "ref": "les images de référence",
    "ext": "la prolongation / modification de clip",
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
    "fal":      set(SERVICES),
    "byteplus": {"video_seedance"},
    "runware":  {"video_seedance"},
    "piapi":    {"video_seedance"},
}


# ── Ordre de priorité (04/10/2026) ───────────────────────────────────────────
# Questions de Matthieu : « si plusieurs API sont référencées, quel moteur est
# utilisé en premier ? Peut-on sélectionner les distributeurs, les classer ?
# Si PiAPI est en premier mais que j'utilise des images de référence, est-ce
# que ça bascule automatiquement ? » Réponse, désormais : un ORDRE réglable.
#   video_provider_order : les quatre distributeurs, du premier au dernier ;
#   video_providers_off  : ceux que l'utilisateur a décochés ;
#   video_provider       : le premier activé (lu par l'ancien code).
# Pour chaque plan, route() prend le premier distributeur activé qui SAIT le
# servir (clé, moteur, mode, résolution, son, réception des fichiers) et dit
# pourquoi les précédents ont été sautés. En mono : le premier, seul.

def provider_order(cfg: dict | None = None) -> list[str]:
    """Les quatre distributeurs dans l'ordre de priorité (activés ou non)."""
    cfg = load_config() if cfg is None else cfg
    raw = cfg.get("video_provider_order")
    if isinstance(raw, list) and raw:
        order = [p for p in dict.fromkeys(str(x).strip().lower() for x in raw)
                 if p in PROVIDERS]
    else:
        # Config d'avant le 04/10/2026 : le distributeur choisi d'abord, puis
        # les autres, fal en dernier recours — ceux sans clé sont sautés de
        # toute façon. Un utilisateur resté sur fal le garde en tête.
        chosen = (cfg.get("video_provider") or _DEFAULT).strip().lower()
        chosen = chosen if chosen in PROVIDERS else _DEFAULT
        order = [chosen] + [p for p in ("byteplus", "runware", "piapi") if p != chosen]
    for p in ORDER:
        if p not in order:
            order.append(p)
    return order


def enabled_order(cfg: dict | None = None) -> list[str]:
    """Distributeurs ACTIVÉS dans l'ordre de priorité ; en mono, le premier seul."""
    cfg = load_config() if cfg is None else cfg
    off = {str(x).strip().lower() for x in (cfg.get("video_providers_off") or [])}
    order = [p for p in provider_order(cfg) if p not in off] or [_DEFAULT]
    if get_distribution_mode(cfg) == "mono":
        return order[:1]
    return order


def promote_in_config(cfg: dict, provider_id: str) -> dict:
    """Met ce distributeur EN TÊTE de l'ordre et l'active (choix fait dans le
    Studio). Modifie et rend `cfg` ; l'appelant enregistre."""
    order = provider_order(cfg)
    cfg["video_provider_order"] = [provider_id] + [p for p in order if p != provider_id]
    cfg["video_providers_off"] = [p for p in (cfg.get("video_providers_off") or [])
                                  if p != provider_id]
    cfg["video_provider"] = provider_id
    return cfg


def _key_of(cfg: dict, provider_id: str) -> str:
    meta = PROVIDERS.get(provider_id) or {}
    return (cfg.get(meta.get("key_cfg", "")) or "").strip()


def route(engine: str, mode: str = "", resolution: str = "", audio: bool = True,
          needs=(), can_receive=None, cfg: dict | None = None) -> tuple[str, list[str]]:
    """Le premier distributeur ACTIVÉ capable de servir cette demande, et la
    raison pour laquelle chacun des précédents a été sauté.

    `needs` : fichiers à envoyer ("images", "video", "audio") ;
    `can_receive(pid, needs)` → (True | False | None, raison) : sonde de ce que
    le distributeur peut recevoir (api/distrib_probe) — None = on ne sait pas,
    on essaie (l'envoi s'arrêtera avant de payer si les fichiers ne passent
    pas). Rend ("", raisons) si personne ne peut."""
    cfg = load_config() if cfg is None else cfg
    skipped: list[str] = []
    for pid in enabled_order(cfg):
        name = provider_short(pid)
        if not _key_of(cfg, pid):
            skipped.append(f"{name} : clé manquante")
            continue
        ok, why = provider_supports(pid, engine, mode, resolution, audio)
        if not ok:
            skipped.append(why)
            continue
        if can_receive is not None:
            try:
                okr, whyr = can_receive(pid, tuple(needs or ()))
            except Exception:
                okr, whyr = None, ""
            if okr is False:
                skipped.append(f"{name} : {whyr}")
                continue
        return pid, skipped
    return "", skipped


# ── Sélection ─────────────────────────────────────────────────────────────────

def get_video_provider() -> str:
    """Distributeur vidéo EN TÊTE de l'ordre ("fal" par défaut)."""
    return enabled_order()[0]


def get_distribution_mode(cfg: dict | None = None) -> str:
    """"multi" (défaut) : les distributeurs activés, dans l'ordre, avec bascule
    automatique sur le suivant. "mono" : le premier est le SEUL utilisé — ce
    qu'il ne sait pas faire est INDISPONIBLE (grisé), sans bascule."""
    cfg = load_config() if cfg is None else cfg
    m = (cfg.get("distribution_mode") or "multi").strip().lower()
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


def _norm_res(resolution: str) -> str:
    """« 720p (~$0.30/s) » → « 720p » ; « 4K » → « 4k »."""
    r = (resolution or "").strip()
    return r.split()[0].lower() if r else ""


def provider_supports(provider_id: str, engine: str, mode: str = "",
                      resolution: str = "", audio: bool = True) -> tuple[bool, str]:
    """(couvert, raison lisible si non). Un critère vide n'est pas vérifié."""
    if provider_id == "fal":
        return True, ""
    name = provider_short(provider_id)
    caps = _CAPS.get(provider_id, {}).get((engine or "").strip())
    if not caps:
        return False, f"{name} ne propose pas ce moteur"
    if mode and mode not in caps["modes"]:
        return False, f"{name} ne propose pas {_MODE_LABELS.get(mode, mode)} sur ce moteur"
    res = _norm_res(resolution)
    if res and res not in caps["res"]:
        return False, f"{name} ne propose pas le {res} sur ce moteur"
    if not audio and not caps["audio_off"]:
        return False, f"{name} ne permet pas de couper le son sur ce moteur"
    return True, ""


def provider_covers(provider_id: str, engine: str) -> bool:
    """Le distributeur propose-t-il ce moteur (tous modes confondus) ?"""
    return provider_supports(provider_id, engine)[0]


def _rate(provider_id: str, engine: str, resolution: str) -> float | None:
    rates = _PER_SECOND.get(provider_id, {}).get((engine or "").strip())
    if not rates:
        return None
    return rates.get(_norm_res(resolution))


def provider_rate(provider_id: str, engine: str, resolution: str) -> float | None:
    """$/s chez un distributeur ALTERNATIF pour (moteur, résolution), ou None."""
    return _rate(provider_id, engine, resolution)


def active_video_provider(engine: str = "seedance-2.0", mode: str = "",
                          resolution: str = "", audio: bool = True) -> str:
    """Distributeur EFFECTIF pour cette demande (sans sonde réseau).

    Multi (défaut) : le premier distributeur ACTIVÉ de l'ordre qui a sa clé
    et sait faire la demande ; fal si personne. Mono : TOUJOURS le premier —
    le blocage précis (non couvert, clé absente) est porté par
    mono_blocked_engine(), jamais par une bascule silencieuse."""
    cfg = load_config()
    pid, _skipped = route(engine, mode, resolution, audio, cfg=cfg)
    if pid:
        return pid
    if get_distribution_mode(cfg) == "mono":
        return enabled_order(cfg)[0]
    return "fal"


#: Moteurs routés par l'ordre des distributeurs (api/real). Les autres moteurs
#: vidéo partent chez fal.ai ; les moteurs LOCAUX ne facturent rien.
ROUTED_ENGINES = ("seedance-2.0", "seedance-2.0-fast", "seedance-2.5")
LOCAL_ENGINES = ("comfy", "minimax-h3-local")


def billing_provider(engine: str, resolution: str = "", audio: bool = True) -> str:
    """Qui facture cette génération : id du distributeur (« fal », « piapi »…), ou
    "" pour un moteur local (aucun crédit). Constat Matthieu 04/10/2026 : la file
    annonçait « crédits fal.ai » alors que PiAPI servait les plans."""
    engine = (engine or "").strip()
    if engine in LOCAL_ENGINES or engine.startswith("comfy"):
        return ""
    if engine in ROUTED_ENGINES:
        return active_video_provider(engine, "", resolution, audio)
    return "fal"


def billing_notice(engine: str, resolution: str = "", audio: bool = True) -> str:
    """Ligne « qui facture » des confirmations de file (texte déjà traduit)."""
    from core.i18n import translate
    try:
        pid = billing_provider(engine, resolution, audio)
    except Exception:
        return translate("⚠  Chaque plan est facturé par le distributeur choisi.")
    if not pid:
        return translate("Moteur local : aucun crédit consommé.")
    return translate("⚠  Chaque plan est facturé par :") + f" {provider_short(pid)}."


def mono_blocked_engine(engine: str, mode: str = "", resolution: str = "",
                        audio: bool = True) -> str:
    """En mode MONO : message d'erreur si cette demande ne peut pas être servie
    par le distributeur en tête (non couverte, ou clé manquante) ; "" sinon.
    En multi : jamais bloqué ici (bascule). Appelé par api/real.py AVANT tout envoi."""
    cfg = load_config()
    if get_distribution_mode(cfg) != "mono":
        return ""
    pid = enabled_order(cfg)[0]
    ok, why = provider_supports(pid, engine, mode, resolution, audio)
    if not ok:
        return (f"Moteur « {engine} » indisponible chez {provider_label(pid)} "
                f"(mode mono-distributeur) : {why}. Change de réglage, ou repasse en "
                f"« Multi-distributeurs » dans Paramètres → Distribution des vidéos.")
    if pid != "fal" and not _key_of(cfg, pid):
        return (f"Clé {provider_label(pid)} manquante — renseigne-la dans "
                f"Paramètres → Distribution des vidéos, ou repasse en "
                f"« Multi-distributeurs ».")
    return ""


def real_generation_possible(engine: str = "seedance-2.0") -> bool:
    """Une génération RÉELLE peut-elle partir ? (sinon : simulation).

    Jusqu'au 04/10/2026, seule la clé fal comptait : un utilisateur avec une
    clé BytePlus mais sans fal restait en simulation. En mono, on part en réel
    même sans clé du distributeur en tête, pour que l'erreur « clé manquante »
    s'affiche au lieu d'une fausse vidéo de simulation."""
    cfg = load_config()
    if (cfg.get("api_key") or "").strip():
        return True
    order = enabled_order(cfg)
    if get_distribution_mode(cfg) == "mono":
        return order[0] != "fal"
    return any(_key_of(cfg, p) for p in order if p != "fal")


def provider_key(provider_id: str) -> str:
    meta = PROVIDERS.get(provider_id) or {}
    return (load_config().get(meta.get("key_cfg", "")) or "").strip()


def provider_label(provider_id: str) -> str:
    return (PROVIDERS.get(provider_id) or {}).get("label", provider_id)


def provider_short(provider_id: str) -> str:
    return (PROVIDERS.get(provider_id) or {}).get("short", provider_id)


def provider_site(provider_id: str) -> str:
    return (PROVIDERS.get(provider_id) or {}).get("site", provider_id)


def provider_keys_url(provider_id: str) -> str:
    return (PROVIDERS.get(provider_id) or {}).get("keys_url", "")


def max_ref_images(provider_id: str, engine: str) -> int | None:
    """Plafond d'images de référence chez un distributeur ALTERNATIF (30 en
    2.5, 9 en 2.0) ; None pour fal (plafond de core/seedance_family)."""
    if provider_id == "fal":
        return None
    return 30 if (engine or "").strip() == "seedance-2.5" else 9


# ── Prix ──────────────────────────────────────────────────────────────────────

def price_per_second(engine: str, resolution: str,
                     provider: str | None = None) -> tuple[float | None, str]:
    """($/s, distributeur) pour (moteur, résolution).

    `provider` : distributeur imposé (celui qui a réellement servi un plan) ;
    sinon le distributeur EFFECTIF. Une résolution absente de la grille de
    l'alternatif retombe sur la grille fal, pour rester honnête."""
    pid = provider or active_video_provider(engine, resolution=resolution)
    if pid != "fal":
        rate = _rate(pid, engine, resolution)
        if rate is not None:
            return rate, pid
    from core import pricing as _fal_pricing
    return _fal_pricing.price_per_second(engine, resolution), "fal"


def quotes(engine: str, resolution: str, seconds: float, mode: str = "",
           audio: bool = True) -> list[dict]:
    """Prix de la même demande chez CHAQUE distributeur (Studio, Paramètres).

    Une entrée par distributeur de ORDER : id, label, short, cost (USD ou
    None si non couvert), has_key, supported, why (raison si non couvert)."""
    from core import pricing as _pricing
    out: list[dict] = []
    for pid in ORDER:
        ok, why = provider_supports(pid, engine, mode, resolution, audio)
        cost = None
        if ok:
            if pid == "fal":
                cost = _pricing.fal_estimate(engine, resolution, seconds)[0]
            else:
                r = _rate(pid, engine, resolution)
                cost = None if r is None else r * max(0.0, float(seconds or 0.0))
        out.append({"id": pid, "label": provider_label(pid), "short": provider_short(pid),
                    "cost": cost, "has_key": bool(provider_key(pid)),
                    "supported": ok, "why": why})
    return out
