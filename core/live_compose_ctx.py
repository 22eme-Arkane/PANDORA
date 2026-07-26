"""
core/live_compose_ctx.py — Contexte de composition Live et empreinte de cache.

Module PUR : aucun réseau, aucun Qt, aucun appel IA. Il peut donc être vérifié
hors ligne, ce qui est exactement ce qu'on veut d'une pièce dont le rôle est de
dire « ce prompt est-il encore valable ? ».

À quoi il sert (2026-07-26) : côté Cinéma, une prose composée est mémorisée pour
qu'un aller-retour entre deux plans ne la recalcule pas — et ne la refacture pas.
La mémorisation ne vaut que par son EMPREINTE : si une entrée change sans que la
clé change, on ressert une prose périmée sans le moindre signe à l'écran.

Le Live a des entrées que le Cinéma n'a pas, et ce sont les plus traîtres :

    mode        « live » ou « mapping » — le même texte donne deux prompts opposés
                (caméra autorisée d'un côté, bannie de l'autre)
    surface     la géométrie de la façade : changer de bâtiment change tout
    bpm/beats   la durée de barre, donc le rythme demandé au moteur

Les oublier dans la clé, c'est garantir qu'un changement de façade ou de tempo
réutilise silencieusement l'ancienne prose. C'est la raison d'être de ce fichier.

⚠ Le nom contient « live » : il tombe dans le glob du test `grammaire_live_separee`
et n'a donc PAS le droit d'importer `core.engine_grammar` en direct — tout passe
par `core.live_grammar`.
"""

from __future__ import annotations

import hashlib
import json

from core.live_grammar import normalize_mode

# Au-delà, on purge les entrées les plus anciennement insérées : un long balayage
# de plans ne doit pas faire enfler la mémoire indéfiniment.
CACHE_MAX = 200

# Repli quand aucun tempo n'est connu : une barre de 4 temps est le découpage le
# plus courant, mais sans BPM on ne peut rien en déduire — on laisse 8 (une mesure
# complète en 4/4 comptée en croches), valeur de référence de core/live_bar.
DEFAULT_BEATS = 8


def compose_context(*, engine: str = "", mode: str = "live", style_suffix: str = "",
                    surface: str = "", bpm: float = 0.0, beats: int = DEFAULT_BEATS,
                    duration=None, extras=None) -> dict:
    """Tout ce qui détermine la prose composée, sous une forme STABLE.

    Normalisé pour que deux états équivalents donnent la même clé : le mode est
    canonisé, le BPM arrondi au dixième (un tempo détecté par librosa oscille de
    quelques millièmes d'une analyse à l'autre et ferait rater tous les caches),
    les extras triés et dédoublonnés.
    """
    _extras = sorted({" ".join((e or "").split()) for e in (extras or [])
                      if (e or "").strip()})
    return {
        "engine":       (engine or "").strip(),
        "mode":         normalize_mode(mode),
        "style_suffix": " ".join((style_suffix or "").split()),
        # La surface est longue (description Vision de la façade) : on n'en garde
        # que l'empreinte, la clé n'a pas à transporter le texte entier.
        "surface":      hashlib.sha1(
            " ".join((surface or "").split()).encode("utf-8")).hexdigest()[:16],
        "bpm":          round(float(bpm or 0.0), 1),
        "beats":        int(beats or DEFAULT_BEATS),
        "duration":     str(duration or ""),
        "extras":       _extras,
    }


def cache_key(prompt_fr: str, ctx: dict) -> str:
    """Empreinte de (texte pré-composition + contexte). Une seule chose change →
    clé différente → recomposition."""
    payload = json.dumps({"p": " ".join((prompt_fr or "").split()), "c": ctx or {}},
                         sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.sha1(payload.encode("utf-8")).hexdigest()


def bpm_for_shot(shot: dict, tracks) -> float:
    """BPM du morceau assigné au plan. 0.0 si inconnu — jamais d'exception.

    Recette RECOPIÉE du tableau Séquences (ui/page_storyboard_live) plutôt que
    factorisée dans un module commun : c'est du savoir Live, et le Cinéma n'a pas
    de morceaux assignés aux plans.
    """
    try:
        name = (shot or {}).get("music_track", "")
        if not name:
            return 0.0
        tk = next((t for t in (tracks or [])
                   if isinstance(t, dict) and t.get("name") == name), None)
        return float((tk or {}).get("bpm") or 0.0)
    except (TypeError, ValueError, AttributeError):
        return 0.0


def beats_for(duration, bpm: float) -> int:
    """Nombre de temps que couvre cette durée à ce tempo. Repli DEFAULT_BEATS.

    Sert à dire au composeur « la transformation doit tenir sur N temps », pas à
    calculer la durée envoyée au moteur — c'est core/live_bar.api_duration qui
    s'en charge, et lui seul.
    """
    try:
        d, b = float(duration or 0), float(bpm or 0)
    except (TypeError, ValueError):
        return DEFAULT_BEATS
    if d <= 0 or b <= 0:
        return DEFAULT_BEATS
    n = round(d * b / 60.0)
    return int(n) if n >= 1 else DEFAULT_BEATS


def purge(cache: dict, maximum: int = CACHE_MAX) -> dict:
    """Ramène le cache sous son plafond, en retirant les plus anciennes entrées."""
    if len(cache) > maximum:
        for old in list(cache)[:len(cache) - maximum]:
            cache.pop(old, None)
    return cache
