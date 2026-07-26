"""
core/live_prompt.py — Assemblage DÉTERMINISTE du prompt final Live.

Pourquoi ce module (2026-07-26) : côté Cinéma, le prompt final est écrit dans la
grammaire du moteur par une COMPOSITION IA (api/video_prompt.compose). Le Live ne
peut pas s'offrir ça : une réécriture par l'IA diluerait les beats début/milieu/fin
et casserait le calage musical — c'est la règle du projet.

Or la grammaire n'a pas besoin d'un modèle pour être appliquée : le Live possède
déjà les données STRUCTURÉES (sections du prompt, termes caméra traduits, style
visuel). Il suffit de les ASSEMBLER dans l'ordre qu'attend chaque moteur. C'est ce
que fait ce module : aucun appel réseau, aucun modèle, sortie reproductible.

Le corps du plan (la section action) est repris MOT POUR MOT. Rien n'est réécrit.
"""

from __future__ import annotations

from core.engine_grammar import grammar_for, strip_ip_names


def _clean(text: str) -> str:
    return " ".join((text or "").split()).strip(" .,;:")


def _join_sentences(parts: list) -> str:
    """Phrases propres, sans double ponctuation ni fragment vide."""
    out = [_clean(p) for p in parts if _clean(p)]
    return ". ".join(out) + "." if out else ""


def assemble(body: str, *, engine_key: str = "", camera_bits: list | None = None,
             style: str = "", extras: list | None = None) -> tuple:
    """Prompt final Live, écrit dans la grammaire du moteur. DÉTERMINISTE.

    `body`        — corps du plan, déjà aplati et traduit (repris tel quel) ;
    `camera_bits` — termes caméra du plan (core.shot_terms.camera_terms) ;
    `style`       — style visuel (projet + note de réalisation) ;
    `extras`      — suffixes techniques déjà anglais (ADN mapping, « no music »…).

    Retourne (prompt_final, noms_d_IP_retirés). Les noms de studios/franchises sont
    retirés partout — un moteur les refuse ou les imite mal, seuls les descripteurs
    de style produisent le rendu.
    """
    body = _clean(body)
    cam = [c for c in (camera_bits or []) if _clean(c)]
    style = _clean(style)
    extras = [e for e in (extras or []) if _clean(e)]
    grammar = grammar_for(engine_key)

    if grammar == "fields":
        # Seedance : champs nommés. Le moteur suit mieux « Camera: … » qu'une
        # subordonnée noyée dans la prose.
        blocks = [body]
        if cam:
            blocks.append("Camera: " + ", ".join(_clean(c) for c in cam))
        if style:
            blocks.append("Style: " + style)
        blocks.extend(extras)
        final = _join_sentences(blocks)

    elif grammar == "sentence":
        # Veo / Sora : UNE phrase continue, sans étiquette ni liste.
        parts = [body]
        if cam:
            parts.append("shot with " + ", ".join(_clean(c) for c in cam))
        if style:
            parts.append("rendered in " + style)
        parts.extend(extras)
        final = _join_sentences(parts)

    elif grammar == "directive":
        # Kling : l'ACTION d'abord, courte et impérative ; le reste ensuite.
        parts = [body]
        if cam:
            parts.append(", ".join(_clean(c) for c in cam))
        if style:
            parts.append(style)
        parts.extend(extras)
        final = _join_sentences(parts)

    else:  # "plain" — prose dense, ordre naturel, style en fin (mieux suivi).
        parts = [body]
        if cam:
            parts.append(", ".join(_clean(c) for c in cam))
        parts.extend(extras)
        if style:
            parts.append(style)
        final = _join_sentences(parts)

    return strip_ip_names(final)


def describe(engine_key: str) -> str:
    """Libellé de la grammaire appliquée, pour l'affichage « Éléments injectés »."""
    from core.engine_grammar import grammar_label
    return grammar_label(engine_key)
