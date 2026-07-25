"""
core/engine_grammar.py — Grammaire de prompt PAR MOTEUR de génération.

Chaque moteur a été entraîné sur une forme différente ; envoyer la même chaîne à
tous dégrade le rendu. Ce module dit, pour une clé de moteur du Studio, QUELLE
forme le prompt doit prendre, et fournit la consigne de format à passer au
composeur (api/video_prompt).

Grammaires (dossier de recherche fal.ai fourni par Matthieu, 25/07/2026) :

  fields    — Seedance 2.0 : prose d'ouverture, puis lignes à champs
              Camera: / Lighting: / Motion: / Sound: / Style: / Constraints:
              C'est le seul moteur du catalogue qui comprend des en-têtes de champs
              et qui gère les contraintes négatives explicites.

  sentence  — Veo 3.1 : UNE phrase continue, ordre plan → sujet → action → décor →
              style → clause « audio: ». Les négations sont mal gérées : elles
              doivent être reformulées POSITIVEMENT (« lit entirely by low sun from
              off-frame left » plutôt que « pas de lampe visible »).

  directive — Kling O3 / v3 : une DIRECTIVE d'action courte, pas une description.
              Le style se pilote par l'image de départ, pas par le texte.

  plain     — Repli pour les autres moteurs : prose dense sans en-têtes.

⚠ Règle commune à tous : aucun emoji, aucun crochet dans le payload (bruit de
tokenisation, aucun moteur ne les traite comme des délimiteurs), et pas de nom
propre d'IP ou de studio (déclencheur de filtre, et pièce gênante dans un dossier
de livraison commerciale). Les DESCRIPTEURS de style, eux, sont conservés : ce sont
eux qui produisent le rendu.
"""

from __future__ import annotations

import re


# Clé de moteur (ui/tab_t2v._ENGINES) → grammaire.
_GRAMMAR_BY_ENGINE = {
    "seedance-2.0":       "fields",
    "seedance-2.0-fast":  "fields",
    "seedance-2.0-mini":  "fields",
    "seedance-1.5-pro":   "fields",
    "veo-3.1":            "sentence",
    "sora-2":             "sentence",
    "kling-v3-pro":       "directive",
    "kling-o3-4k":        "directive",
}

GRAMMAR_LABELS = {
    "fields":    "champs Seedance (Camera:/Lighting:/…)",
    "sentence":  "phrase continue (Veo)",
    "directive": "directive d'action courte (Kling)",
    "plain":     "prose dense",
}


def grammar_for(engine_key: str) -> str:
    """Grammaire attendue par ce moteur. Repli « plain » pour tout moteur inconnu."""
    return _GRAMMAR_BY_ENGINE.get((engine_key or "").strip(), "plain")


def grammar_label(engine_key: str) -> str:
    """Libellé lisible de la grammaire (affiché dans « Éléments injectés »)."""
    return GRAMMAR_LABELS.get(grammar_for(engine_key), GRAMMAR_LABELS["plain"])


# Consigne de FORMAT ajoutée au prompt système du composeur, par grammaire.
_FORMAT_RULES = {
    "fields": (
        "FORMAT DE SORTIE — moteur Seedance :\n"
        "Écris d'abord un paragraphe de prose (sujet + action + décor), puis ces "
        "lignes à champs, une par ligne, dans cet ordre et uniquement si elles ont "
        "du contenu :\n"
        "Camera: …\nLighting: …\nMotion: …\nSound: …\nStyle: …\nConstraints: …\n"
        "La ligne Constraints regroupe les interdits (no camera movement, no text, "
        "no watermark…). Aucune autre étiquette, aucun crochet, aucun emoji."
    ),
    "sentence": (
        "FORMAT DE SORTIE — moteur Veo :\n"
        "UNE SEULE phrase continue, sans aucune étiquette ni retour à la ligne, "
        "dans l'ordre : cadrage, sujet, action, décor, lumière, style, puis une "
        "clause finale « audio: … » décrivant l'ambiance sonore.\n"
        "IMPÉRATIF : ce moteur gère mal les négations. Reformule POSITIVEMENT toute "
        "contrainte (au lieu de « les sources de lumière ne sont pas visibles », "
        "écris « lit entirely by low natural sun from off-frame left »). "
        "N'écris jamais « no … » sauf pour « no speech » ou « no subtitles », qui "
        "portent sur un canal et sont bien respectés.\n"
        "Aucun crochet, aucun emoji."
    ),
    "directive": (
        "FORMAT DE SORTIE — moteur Kling :\n"
        "Une DIRECTIVE d'action courte (2 à 4 phrases maximum), à l'impératif "
        "descriptif : ce que fait le sujet et ce que fait la caméra. Pas de "
        "description de style ni de longue mise en ambiance — sur ce moteur le style "
        "vient de l'image de départ. Aucune étiquette, aucun crochet, aucun emoji."
    ),
    "plain": (
        "FORMAT DE SORTIE : prose anglaise dense en un ou deux paragraphes, sans "
        "étiquette, sans crochet, sans emoji."
    ),
}


def format_rules(engine_key: str) -> str:
    """Consigne de format à ajouter au prompt système du composeur."""
    return _FORMAT_RULES.get(grammar_for(engine_key), _FORMAT_RULES["plain"])


# ── Noms propres d'IP / studios ────────────────────────────────────────────────
# Retirés du PAYLOAD : ils déclenchent des filtres chez plusieurs fournisseurs et
# n'apportent presque rien (ce sont les descripteurs qui produisent le rendu).
# Liste volontairement courte et explicite — elle doit rester lisible et vérifiable.
_IP_NAMES = [
    "arcane league of legends", "league of legends", "arcane",
    "fortiche studio", "fortiche",
    "studio ghibli", "ghibli",
    "pixar", "disney", "dreamworks", "marvel", "netflix", "hbo",
    "blizzard", "riot games", "nintendo", "star wars",
]

_IP_RE = re.compile(
    r"(?<![A-Za-zÀ-ÿ])(" + "|".join(re.escape(n) for n in _IP_NAMES) + r")(?![A-Za-zÀ-ÿ])",
    re.IGNORECASE,
)

# « Arcane style », « Fortiche Studio aesthetic » : sans le nom propre, le
# qualificatif restant (« style », « aesthetic ») ne veut plus rien dire. On le
# retire avec le nom pour ne pas laisser « : style, aesthetic, 3D painterly… ».
_IP_WITH_QUALIFIER_RE = re.compile(
    r"(?<![A-Za-zÀ-ÿ])(?:" + "|".join(re.escape(n) for n in _IP_NAMES) + r")"
    r"(?:\s+(?:style|styled|aesthetic|aesthetics|look|vibe|inspired|esque))*"
    r"(?![A-Za-zÀ-ÿ])",
    re.IGNORECASE,
)


def find_ip_names(text: str) -> list[str]:
    """Noms d'IP/studios présents dans le texte (dédoublonnés, ordre d'apparition)."""
    seen, out = set(), []
    for m in _IP_RE.finditer(text or ""):
        v = m.group(0)
        k = v.lower()
        if k not in seen:
            seen.add(k)
            out.append(v)
    return out


def strip_ip_names(text: str) -> tuple[str, list[str]]:
    """Retire les noms d'IP/studios du prompt en CONSERVANT les descripteurs.

    Retourne (texte_nettoyé, noms_retirés). Le nettoyage supprime aussi les
    tournures devenues creuses (« façon », « style de », guillemets vides) et les
    séparateurs orphelins, pour ne pas laisser « rendu façon " : , 3D peint ».
    """
    found = find_ip_names(text)
    if not found:
        return (text or ""), []
    out = _IP_WITH_QUALIFIER_RE.sub("", text or "")
    # Guillemets vides laissés par la suppression : « " " », « « » ».
    out = re.sub(r"[«\"“]\s*[»\"”]", "", out)
    # Tournures d'attribution devenues sans objet.
    out = re.sub(r"(?i)\b(?:façon|facon|à la manière de|a la maniere de|"
                 r"in the style of|style of)\s*(?=[,.;:]|$)", "", out)
    # Ponctuation et espaces orphelins.
    out = re.sub(r"\s*,\s*,+", ", ", out)
    out = re.sub(r"\s*:\s*,", " :", out)
    out = re.sub(r"\(\s*\)", "", out)
    out = re.sub(r"[ \t]{2,}", " ", out)
    out = re.sub(r"\s+([,.;:])", r"\1", out)
    out = re.sub(r"^[\s,;:]+", "", out, flags=re.MULTILINE)
    return out.strip(), found
