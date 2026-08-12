"""
core/seedance_family.py — Table de la famille Seedance (2.0 et 2.5).

SOURCE UNIQUE des différences entre versions : chemin d'endpoint, résolutions
acceptées, durée, plafond de références, et façon de DÉSIGNER les références.
Relevé sur le schéma d'API publié par fal.ai (OpenAPI de chaque endpoint), pas
sur la communication marketing — le 2026-08-09.

⚠ LA 2.5 N'EST PAS UN REMPLACEMENT DE LA 2.0
--------------------------------------------
Elle plafonne à **720p** (pas de 1080p, pas de 4K) et coûte **56 % plus cher**
à résolution égale. Elle gagne ailleurs : plan-séquence de 30 s d'un bloc, et
jusqu'à 50 entrées multimodales au lieu de 9 images.

  · livrer en 1080p/4K            → 2.0
  · plan long tenu, beaucoup de réfs → 2.5

Le défaut du projet reste donc la 2.0. La 2.5 s'ajoute au choix.

DÉSIGNATION DES RÉFÉRENCES — la vraie nouveauté pour PANDORA
------------------------------------------------------------
La 2.0 reçoit les images sans qu'on puisse les nommer : PANDORA doit décrire
leur rôle en prose et espérer que le moteur fasse le lien (correctif 2.1.1).
La 2.5 les adresse par un JETON dans le prompt : `@Image1`, `@Video1`,
`@Audio1`, numérotés dans l'ordre d'envoi. Le lien devient STRUCTUREL au lieu
d'être persuasif — c'est `core/mood_refs.reference_plan()` qui fixe cet ordre,
donc les jetons se déduisent du plan sans autre source de vérité.
"""
from __future__ import annotations

# Clé moteur PANDORA → caractéristiques réelles de l'endpoint fal.
_FAMILY = {
    "seedance-2.0": {
        "base":        "bytedance/seedance-2.0",
        "resolutions": ("4k", "1080p", "720p", "480p"),
        "max_images":  9,
        "max_videos":  3,
        "max_audios":  3,
        "durations":   None,          # borné ailleurs (slider du plan)
        "named_refs":  False,
    },
    "seedance-2.0-fast": {
        "base":        "bytedance/seedance-2.0/fast",
        "resolutions": ("720p", "480p"),
        "max_images":  9,
        "max_videos":  3,
        "max_audios":  3,
        "durations":   None,
        "named_refs":  False,
    },
    "seedance-2.0-mini": {
        "base":        "bytedance/seedance-2.0/mini",
        "resolutions": ("720p", "480p"),
        "max_images":  0,
        "max_videos":  0,
        "max_audios":  0,
        "durations":   None,
        "named_refs":  False,
    },
    "seedance-2.5": {
        "base":        "bytedance/seedance-2.5",
        "resolutions": ("720p", "480p"),      # PAS de 1080p ni de 4K
        "max_images":  50,                    # 50 ENTRÉES multimodales au total
        "max_videos":  50,
        "max_audios":  50,
        "durations":   tuple(str(s) for s in range(4, 31)),
        "named_refs":  True,                  # @Image1 / @Video1 / @Audio1
    },
}

_DEFAULT_KEY = "seedance-2.0"

# Plafond GLOBAL d'entrées multimodales de la 2.5 (images + vidéos + audio).
MAX_MULTIMODAL_2_5 = 50


def is_seedance(engine_key: str) -> bool:
    return (engine_key or "").strip() in _FAMILY


def spec(engine_key: str) -> dict:
    """Caractéristiques du moteur. Repli sur la 2.0 pour tout inconnu."""
    return _FAMILY.get((engine_key or "").strip(), _FAMILY[_DEFAULT_KEY])


def endpoint_base(engine_key: str) -> str:
    """Préfixe d'endpoint fal (sans le mode)."""
    return spec(engine_key)["base"]


def endpoints(engine_key: str) -> dict:
    """Les 4 modes PANDORA → endpoint complet.

    « ext » (extension de clip) passe par reference-to-video avec `video_urls`,
    comme en 2.0 : il n'existe pas d'endpoint d'extension dédié.
    """
    base = endpoint_base(engine_key)
    return {
        "t2v": f"{base}/text-to-video",
        "i2v": f"{base}/image-to-video",
        "ref": f"{base}/reference-to-video",
        "ext": f"{base}/reference-to-video",
    }


def max_images(engine_key: str) -> int:
    return int(spec(engine_key)["max_images"])


def supports_resolution(engine_key: str, resolution: str) -> bool:
    return (resolution or "").strip().lower() in spec(engine_key)["resolutions"]


def clamp_resolution(engine_key: str, resolution: str) -> str:
    """Ramène une résolution non supportée à la meilleure disponible.

    Cas réel : un plan réglé en 1080p ou 4K puis basculé sur la 2.5. Envoyer
    « 4k » à un endpoint qui ne connaît que 480p/720p ferait échouer l'appel —
    on préfère livrer le plan à la meilleure résolution possible et le DIRE.
    """
    res = (resolution or "").strip().lower()
    allowed = spec(engine_key)["resolutions"]
    if res in allowed:
        return res
    return allowed[0]          # les tuples sont ordonnés du meilleur au moindre


def duration_bounds(engine_key: str) -> tuple[int, int]:
    """Fenêtre de durée ACCEPTÉE par l'endpoint, en secondes (min, max).

    La 2.5 monte à **30 s** (plan-séquence natif — le vrai plus pour le
    mapping) ; le reste de la famille plafonne à 15 s côté fal. Ces bornes
    étaient écrites en dur (« min(15, … ) ») dans quatre fichiers : c'est ici
    qu'elles vivent désormais, sinon la 2.5 restait bridée à 15 s partout.
    """
    d = spec(engine_key).get("durations")
    if d:
        vals = [int(x) for x in d if str(x).isdigit()]
        if vals:
            return (min(vals), max(vals))
    return (4, 15)          # famille 2.0 : bornes historiques de l'API fal


def clamp_duration(engine_key: str, seconds) -> int:
    """Ramène une durée dans la fenêtre du moteur (entier, jamais d'exception)."""
    lo, hi = duration_bounds(engine_key)
    try:
        v = int(round(float(seconds)))
    except (TypeError, ValueError):
        v = lo
    return min(hi, max(lo, v))


def uses_named_refs(engine_key: str) -> bool:
    """True si le moteur adresse ses références par jeton dans le prompt."""
    return bool(spec(engine_key)["named_refs"])


def ref_token(kind: str, index_1based: int) -> str:
    """Jeton de référence : ref_token("image", 1) → « @Image1 »."""
    label = {"image": "Image", "video": "Video", "audio": "Audio"}.get(
        (kind or "image").strip().lower(), "Image")
    return f"@{label}{max(1, int(index_1based))}"


def annotate_roles_with_tokens(roles: list[str], engine_key: str) -> list[str]:
    """Ajoute « (@ImageN) » à chaque rôle de référence, pour un moteur qui les
    nomme. Sans effet sur un moteur qui ne les nomme pas — l'appelant peut
    donc traiter les deux familles avec le même code.

    L'ordre de `roles` EST l'ordre d'envoi (core/mood_refs.reference_plan) :
    c'est ce qui garantit que @Image1 désigne bien la première image jointe.
    """
    if not uses_named_refs(engine_key):
        return list(roles or [])
    out = []
    for i, role in enumerate(roles or [], start=1):
        tok = ref_token("image", i)
        role = (role or "").strip()
        out.append(f"{role} ({tok})" if role else tok)
    return out
