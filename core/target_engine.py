"""
core/target_engine.py — Moteur vidéo VISÉ par le projet.

À QUOI ÇA SERT
--------------
Un découpage n'est pas neutre : le prompt de chaque plan doit être écrit dans la
grammaire du moteur qui le rendra. Choisir le moteur APRÈS avoir généré 75 plans
oblige à tout recomposer. Le choix se fait donc AVANT la génération, et il est
retenu pour tout le projet.

CE QUE LE RÉGLAGE PILOTE
------------------------
· la FORME du prompt écrit par l'IA de découpage (core/engine_grammar) ;
· les CONTRAINTES annoncées à l'IA : durées possibles, ratios, plafond de
  résolution, présence ou non d'un mécanisme de références.

CE QU'IL NE FAIT PAS
--------------------
Il ne verrouille pas la génération : on reste libre de rendre un plan avec un
autre moteur depuis le Studio. C'est une CIBLE d'écriture, pas un verrou.

STOCKAGE — dans le projet, pas dans la config globale
------------------------------------------------------
Deux projets peuvent viser deux moteurs différents. Le réglage vit donc dans
`<projet>/data/target_engine.json`, à côté du storyboard qu'il a servi à
écrire. Hors projet, on retombe sur le défaut sans jamais écrire.
"""
from __future__ import annotations

import json
import os

_FILENAME = "target_engine.json"
_DEFAULT  = "seedance-2.0"


def _path() -> str:
    """Chemin du fichier dans le projet courant, ou "" hors projet.

    ⚠ On teste `get_project_path()` et PAS `get_data_root()` : sans projet
    ouvert, `get_data_root()` retombe sur le dossier `data/` local de
    l'application. Le réglage s'y serait écrit hors de tout projet, puis se
    serait appliqué à TOUS les projets suivants — défaut trouvé au test.
    """
    try:
        from core.context import get_project_path, get_data_root
        if not get_project_path():
            return ""
        root = get_data_root()
    except Exception:
        return ""
    if not root:
        return ""
    return os.path.join(root, _FILENAME)


def get_target_engine() -> str:
    """Moteur visé par le projet. Repli sur Seedance 2.0, jamais vide."""
    p = _path()
    if not p or not os.path.isfile(p):
        return _DEFAULT
    try:
        with open(p, "r", encoding="utf-8") as f:
            key = str((json.load(f) or {}).get("engine") or "").strip()
        return key or _DEFAULT
    except (OSError, json.JSONDecodeError, ValueError):
        # Fichier illisible : on ne casse JAMAIS la génération pour ça.
        return _DEFAULT


def has_choice() -> bool:
    """True si l'utilisateur a DÉJÀ choisi pour ce projet.

    Sert à ne poser la question qu'une fois : au premier découpage. Les fois
    suivantes, le choix est repris en silence (il reste modifiable).
    """
    p = _path()
    return bool(p) and os.path.isfile(p)


def set_target_engine(engine_key: str) -> str:
    """Enregistre le moteur visé (écriture atomique). Retourne la clé retenue."""
    key = (engine_key or "").strip() or _DEFAULT
    p = _path()
    if not p:
        return key                      # hors projet : rien à écrire
    try:
        os.makedirs(os.path.dirname(p), exist_ok=True)
        tmp = p + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump({"engine": key}, f, ensure_ascii=False, indent=2)
        os.replace(tmp, p)
    except OSError:
        pass                            # ne jamais bloquer sur l'écriture
    return key


def clear() -> None:
    """Oublie le choix (la question sera reposée au prochain découpage)."""
    p = _path()
    if p and os.path.isfile(p):
        try:
            os.remove(p)
        except OSError:
            pass


# ── Consigne d'écriture transmise à l'IA de découpage ────────────────────────

def briefing(engine_key: str | None = None) -> str:
    """Consigne EN ANGLAIS décrivant au modèle la forme de prompt attendue.

    Volontairement construite depuis `core/engine_grammar` : il n'existe qu'UNE
    table moteur→forme dans PANDORA, et elle ne doit pas être dupliquée ici.
    Les contraintes dures viennent des tables de famille, jamais de mémoire.
    """
    from core import engine_grammar

    key = (engine_key or get_target_engine()).strip()
    shape = engine_grammar.grammar_for(key)

    forms = {
        "fields": (
            "Write each shot prompt as LABELLED FIELDS on separate lines "
            "(Camera:, Subject:, Action:, Lighting:, Style:). One value per "
            "field, no prose paragraphs."
        ),
        "sentence": (
            "Write each shot prompt as ONE continuous cinematic sentence, then "
            "a second sentence of supporting detail. Order: camera framing and "
            "movement, then subject and action, then location, then lens and "
            "light, then style. Use nouns and verbs a lens can actually see."
        ),
        "directive": (
            "Write each shot prompt as a SHORT ACTION DIRECTIVE: what moves, "
            "where the camera goes. No inventory of the set, no adjective piles."
        ),
        "dense": (
            "Write each shot prompt as DENSE PROSE: one tight block that names "
            "framing, movement, subject, action, location, light and style "
            "without labels and without filler."
        ),
        "plain": (
            "Write each shot prompt as clear descriptive prose: framing, "
            "movement, subject, action, location, light, style."
        ),
    }
    out = [f"TARGET VIDEO ENGINE: {key}.", forms.get(shape, forms["plain"])]

    # Contraintes dures — lues sur les tables, jamais récitées de mémoire.
    try:
        from core import seedance_family as _sf
        if _sf.is_seedance(key):
            spec = _sf.spec(key)
            out.append("Available output resolutions: "
                       + ", ".join(spec["resolutions"]) + ".")
            if _sf.uses_named_refs(key):
                out.append(
                    "Reference images are addressed inside the prompt as "
                    "@Image1, @Image2… — when a shot relies on a character or "
                    "location sheet, refer to it that way."
                )
    except Exception:
        pass
    try:
        if key.startswith("flux-3"):
            from core import flux3_family as _f3
            out.append("Shot durations must be between 5 and 20 seconds.")
            out.append("Available output resolutions: "
                       + ", ".join(_f3.RESOLUTIONS) + ".")
            out.append(
                "Audio is generated natively: end each prompt with a short "
                "sound clause. Any spoken line must name who says it, "
                "otherwise it is burned into the image as text."
            )
    except Exception:
        pass
    return "\n".join(out)
