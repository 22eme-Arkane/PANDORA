"""
core/live_grammar.py — Grammaire de prompt du LIVE, séparée de celle du Cinéma.

Pourquoi ce module (2026-07-26, demande Matthieu) : `core/engine_grammar.py`
mélangeait deux natures de savoir, et le Live héritait de la mauvaise.

  ① FAIT CONSTRUCTEUR — quelle FORME chaque moteur attend (Seedance lit des
    champs, Veo une phrase continue, Kling une directive) ; quels noms propres
    déclenchent un filtre. Vrai pour le Cinéma comme pour le Live : le dupliquer,
    c'est se retrouver avec deux tables qui divergent le jour où Seedance 3.0
    sort. Ce module les CONSOMME, il ne les recopie pas.

  ② DÉCISION DE PROJET — quel VOCABULAIRE remplit cette forme. Là, le Cinéma et
    le Live sont en opposition frontale : `_FORMAT_RULES` du Cinéma impose les
    champs « Camera: / Lighting: / Motion: / Sound: », dont TROIS sont interdits
    en mapping (cf. core/live_bar : la caméra est le vidéoprojecteur et il est
    boulonné ; la lumière, c'est l'image projetée elle-même ; le son, c'est le
    set). Ce vocabulaire-là est désormais ICI, et ici seulement.

Conséquence pratique — la règle demandée :

    travailler sur le Live = éditer core/live_grammar.py et core/live_bar.py.
    core/engine_grammar.py est en LECTURE SEULE pour le Live.

Le harnais le vérifie (`grammaire_live_separee` dans tools/test_live.py) : aucun
module Live n'importe `engine_grammar` en direct — tout passe par ce fichier —
et `engine_grammar.py` ne doit contenir aucun vocabulaire Live dans son CODE.

Précédent dans le dépôt : `core/image_grammar.py` fait déjà exactement ça pour le
volet image. Ce module est son équivalent pour le Live.
"""

from __future__ import annotations

import re

# ① Faits constructeur — consommés, jamais recopiés.
from core.engine_grammar import grammar_for as _shape_of_engine
from core.engine_grammar import grammar_label as _label_of_engine
from core.engine_grammar import strip_ip_names as _strip_ip_shared

# ② Décisions Live — la grammaire mapping proprement dite.
from core.live_bar import BANNED_POSITIVES, MAPPING_NEGATIVES, sanitize_payload

MODES = ("live", "mapping")


def normalize_mode(mode: str) -> str:
    """Mode de séquence Live. Tout ce qui n'est pas « mapping » est du « live »."""
    return "mapping" if (mode or "").strip().lower() == "mapping" else "live"


# ── La forme attendue par le moteur (fait constructeur) ───────────────────────
def grammar_for(engine_key: str) -> str:
    """Forme attendue par ce moteur : fields / sentence / directive / plain.

    Délègue à `core.engine_grammar` : Seedance lit des champs qu'on lui envoie un
    plan de cinéma ou une barre de mapping. Cette table n'a pas à exister en deux
    exemplaires — c'est le CONTENU qui diffère, pas la forme.
    """
    return _shape_of_engine(engine_key)


def grammar_label(engine_key: str) -> str:
    """Libellé lisible de la forme, pour le bloc « Éléments injectés »."""
    return _label_of_engine(engine_key)


# ── Le vocabulaire, lui, est une décision de projet ───────────────────────────
# Champs autorisés dans la grammaire « fields », DANS L'ORDRE, par mode.
# Le mapping n'a ni Camera ni Lighting ni Sound : ce sont les trois inversions
# structurelles de core/live_bar, pas des préférences de style.
FIELDS_BY_MODE = {
    "live":    ("Camera", "Style", "Constraints"),
    "mapping": ("Surface", "Motion", "Black", "Style", "Constraints"),
}

# Étiquettes de champ INTERDITES au payload, par mode. Une seule ligne
# « Camera: locked-off » suffit à faire bouger un moteur qui, sans elle, restait
# fixe — l'interdit porte sur le mot, pas sur son contenu.
BANNED_FIELDS_BY_MODE = {
    "live":    (),
    "mapping": ("Camera", "Lighting", "Sound", "Audio", "Music"),
}


def fields_for(mode: str = "live") -> tuple:
    """Champs autorisés pour ce mode, dans l'ordre d'écriture."""
    return FIELDS_BY_MODE[normalize_mode(mode)]


def banned_fields(mode: str = "live") -> tuple:
    """Étiquettes de champ qui ne doivent JAMAIS atteindre le moteur."""
    return BANNED_FIELDS_BY_MODE[normalize_mode(mode)]


def allows_camera(mode: str = "live") -> bool:
    """En mapping la « caméra » est le vidéoprojecteur : elle est boulonnée."""
    return "Camera" not in banned_fields(mode)


def allows_sound(mode: str = "live") -> bool:
    """En mapping le son n'est jamais généré — le son, c'est le set."""
    return "Sound" not in banned_fields(mode)


def _banned_field_re(mode: str):
    labels = banned_fields(mode)
    if not labels:
        return None
    return re.compile(
        r"(?im)^[ \t]*(?:" + "|".join(re.escape(l) for l in labels) + r")[ \t]*:.*$")


def enforce_mode(text: str, mode: str = "live") -> tuple:
    """Retire du texte ce que ce mode interdit. Retourne (texte, retiré).

    Filet de sécurité en BOUT de chaîne : même si un appelant distrait passe des
    termes caméra à un plan de mapping, ils n'atteignent pas le moteur. Ne réécrit
    rien d'autre — le corps du plan passe mot pour mot.
    """
    out = text or ""
    removed = []
    rx = _banned_field_re(mode)
    if rx is not None:
        for m in rx.finditer(out):
            removed.append(m.group(0).strip())
        out = rx.sub("", out)
    if normalize_mode(mode) == "mapping":
        # Les boosters de plateau sont, projetés sur de la pierre, des défauts.
        out, boosters = sanitize_payload(out)
        removed.extend(boosters)
    out = re.sub(r"\n{3,}", "\n\n", out).strip()
    return out, removed


def strip_names(text: str) -> tuple:
    """Retrait des noms d'IP/studios, PUIS nettoyage propre au Live.

    Le retrait lui-même est mutualisé (une franchise déclenche le même filtre des
    deux côtés). Ce qui vient après appartient au Live : c'est le point d'entrée
    de toute correction future motivée par un plan Live, pour qu'elle n'ait plus
    jamais à être écrite dans le fichier partagé.
    """
    out, found = _strip_ip_shared(text)
    # Ponctuation orpheline propre aux prompts Live, qui empilent les suffixes
    # techniques (« …, no music, no subtitles ») et laissent des virgules nues.
    out = re.sub(r"(?:\s*,)+", ", ", out)
    out = re.sub(r"\s+([,.;:])", r"\1", out)
    out = re.sub(r"[\s,;:]+$", "", out.strip())
    return out, found


def format_rules(engine_key: str, mode: str = "live") -> str:
    """Consigne de format pour une IA qui ÉCRIT un prompt Live.

    Distincte de `engine_grammar.format_rules`, qui décrit un plan de cinéma
    (Camera / Lighting / Motion / Sound). Ici, en mapping, ces quatre champs sont
    précisément ce qu'il ne faut pas produire.
    """
    shape = grammar_for(engine_key)
    mode = normalize_mode(mode)
    if mode != "mapping":
        from core.engine_grammar import format_rules as _cine_rules
        return _cine_rules(engine_key)

    negs = ", ".join(MAPPING_NEGATIVES[:8]) + "…"
    commun = (
        "CONTEXTE — mapping vidéo projeté sur une façade :\n"
        "· Le cadre est VERROUILLÉ : ne nomme jamais la caméra, ni un mouvement, "
        "ni une valeur de plan. Le vidéoprojecteur est boulonné.\n"
        "· Le noir est STRUCTUREL : ce qui est noir n'est pas projeté. Dis "
        "explicitement ce qui doit rester à zéro lumière.\n"
        "· UN seul processus continu sur toute la barre, aucune coupe.\n"
        "· N'écris JAMAIS de son : le son, c'est le set.\n"
        f"· Bannis ces mots : {', '.join(BANNED_POSITIVES)}.\n"
        f"· Contraintes à porter : {negs}\n"
    )
    if shape == "fields":
        return commun + (
            "FORMAT — moteur Seedance : un paragraphe de prose, puis ces lignes, "
            "une par ligne, uniquement si elles ont du contenu :\n"
            "Surface: …\nMotion: …\nBlack: …\nStyle: …\nConstraints: …\n"
            "Aucune ligne Camera, Lighting, Sound ou Music. Aucun crochet, "
            "aucun emoji.")
    if shape == "sentence":
        return commun + (
            "FORMAT — moteur Veo : UNE phrase continue, sans étiquette ni retour "
            "à la ligne, dans l'ordre : surface, état au premier temps, "
            "transformation, état final, noir, style. Pas de clause « audio: ». "
            "Ce moteur gère mal les négations : formule POSITIVEMENT (« the "
            "background stays pure black » plutôt que « no background »).")
    if shape == "directive":
        return commun + (
            "FORMAT — moteur Kling : une directive courte (2 à 4 phrases) "
            "décrivant le seul processus qui court sur la barre. Le style vient "
            "de l'image de départ, ne le décris pas.")
    return commun + (
        "FORMAT : prose anglaise dense, un ou deux paragraphes, sans étiquette, "
        "sans crochet, sans emoji.")
