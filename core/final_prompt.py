"""
core/final_prompt.py — Le prompt FINAL d'un plan, conservé avec lui.

LE PROBLÈME
-----------
Le prompt envoyé au moteur n'est pas celui qu'on lit dans le Storyboard. Le
Storyboard garde le **document de travail** : des blocs français ([ACTION],
[DÉCOR], [PLAN DE FEU]…) qui structurent le plan et ne dépendent d'aucun
moteur. Au moment d'envoyer, PANDORA les réécrit en anglais, en continu, dans
la grammaire du moteur choisi.

Ce prompt final ne vivait QUE dans un cache mémoire du Studio, perdu à la
fermeture. Conséquence : impossible de le relire depuis le Storyboard, et un
affichage « prompt final » sur 75 plans aurait déclenché 75 compositions IA
PAYANTES rien que pour regarder.

CE QUE FAIT CE MODULE
---------------------
Il range le prompt final À CÔTÉ du plan, une fois qu'il a été composé pour de
bon. Le Storyboard peut alors l'AFFICHER sans rien recomposer.

FRAÎCHEUR — pourquoi on garde la source
----------------------------------------
On mémorise aussi le texte structuré qui a servi à le composer. Si le plan a
été modifié depuis, le prompt final est PÉRIMÉ et on le dit, au lieu de
montrer un texte qui ne correspond plus au plan. On ne recompose jamais tout
seul : composer coûte de l'argent, c'est une décision de l'utilisateur.
"""
from __future__ import annotations

# Champs ajoutés au plan (JSON du storyboard).
F_TEXT   = "final_prompt"          # le prompt anglais réellement envoyé
F_SRC    = "final_prompt_src"      # le document de travail dont il vient
F_ENGINE = "final_prompt_engine"   # moteur visé au moment de la composition
F_FORM   = "final_prompt_form"     # forme utilisée (auto/fields/sentence…)
F_CTX    = "final_prompt_ctx"      # empreinte du contexte hors-prompt (axe…)


def ctx_fingerprint(shot: dict) -> str:
    """Empreinte des champs qui entrent dans le final SANS passer par le texte
    structuré : termes caméra (dont l'AXE — il ne vit pas dans le bloc
    TECHNIQUE), heure du plan, durée, langue des dialogues.

    Sans elle, changer l'axe caméra laissait un final « frais » qui décrivait
    l'ancien axe — mensonge WYSIWYG silencieux (question de Matthieu,
    2026-08-11). Comparer le seul texte structuré ne suffisait pas."""
    import hashlib
    try:
        from core.shot_terms import camera_terms
        cam = camera_terms(shot or {})
    except Exception:
        cam = []
    shot = shot or {}
    payload = "|".join([
        ";".join(cam),
        (shot.get("shot_time") or "").strip(),
        str(shot.get("duration") or ""),
        (shot.get("dialogue_lang") or "en").strip(),
    ])
    return hashlib.sha1(payload.encode("utf-8")).hexdigest()[:16]

# États possibles de la vue « prompt final ».
ABSENT = "absent"    # jamais composé pour ce plan
STALE  = "perime"    # composé, mais le plan a changé depuis
FRESH  = "frais"     # à jour


# ── Vue courante (affichage seulement) ───────────────────────────────────────
# État de SESSION, pas une donnée du film : rouvrir PANDORA repart sur le
# document de travail. Vit ici plutôt que dans le widget parce que les rangées
# du Storyboard sont reconstruites à chaque rendu — les faire transiter par
# l'arbre de widgets ajouterait du plomberie pour rien.
_VIEW = "structure"


def current_view() -> str:
    return _VIEW


def set_current_view(view: str) -> str:
    global _VIEW
    _VIEW = "final" if view == "final" else "structure"
    return _VIEW


def remember(shot: dict, final_text: str, source_text: str,
             engine: str = "", form: str = "") -> dict:
    """Range le prompt final dans le plan et l'ENREGISTRE.

    Ne lève jamais : rater cette mémorisation ne doit pas faire échouer une
    génération qui, elle, a réussi.
    """
    if not isinstance(shot, dict) or not (final_text or "").strip():
        return shot
    try:
        shot[F_TEXT]   = final_text
        shot[F_SRC]    = source_text or ""
        shot[F_ENGINE] = engine or ""
        shot[F_FORM]   = form or ""
        shot[F_CTX]    = ctx_fingerprint(shot)
        import core.storyboard as _sb
        _sb.save_shot(shot)
    except Exception:
        pass
    return shot


def state_of(shot: dict) -> str:
    """ABSENT / STALE / FRESH pour ce plan.

    Deux comparaisons : le TEXTE structuré (F_SRC) et l'EMPREINTE de contexte
    (F_CTX — axe, heure, durée, langue, qui n'apparaissent pas dans le texte).
    Un final sans F_CTX (composé avant l'empreinte) reste jugé sur le texte
    seul : on ne périme pas rétroactivement des compositions déjà payées."""
    if not isinstance(shot, dict):
        return ABSENT
    if not (shot.get(F_TEXT) or "").strip():
        return ABSENT
    src_now = (shot.get("seedance_prompt") or "").strip()
    src_was = (shot.get(F_SRC) or "").strip()
    if src_now != src_was:
        return STALE
    ctx_was = (shot.get(F_CTX) or "").strip()
    if ctx_was and ctx_was != ctx_fingerprint(shot):
        return STALE
    return FRESH


def text_of(shot: dict) -> str:
    return (shot or {}).get(F_TEXT, "") or ""


def display_text(shot: dict, view: str) -> str:
    """Texte à AFFICHER dans la colonne Prompt selon la vue demandée.

    view == "structure" → le document de travail, inchangé.
    view == "final"     → le prompt anglais, ou un message explicite. Jamais de
                          composition déclenchée depuis un simple affichage.
    """
    shot = shot or {}
    structured = shot.get("seedance_prompt", "") or ""
    if (view or "structure") != "final":
        return structured

    st = state_of(shot)
    if st == ABSENT:
        # Storyboards antérieurs à l'architecture « à l'endroit », imports
        # déterministes, projets sans clé. COURT et ACTIONNABLE : la première
        # version était un pavé répété à chaque ligne, sans issue (constat
        # Matthieu 2026-08-11) — le bouton de la barre est la réponse.
        return ("— prompt final pas encore composé —\n"
                "Cliquez « Composer » dans la barre (un appel IA par plan).")
    txt = text_of(shot)
    if st == STALE:
        return ("⚠ PÉRIMÉ — le plan a été modifié depuis cette composition.\n"
                "Voici le dernier prompt réellement envoyé :\n\n" + txt)
    return txt


def badge_of(shot: dict, view: str) -> str:
    """Courte mention d'état pour l'interface ("" si rien à signaler)."""
    if (view or "structure") != "final":
        return ""
    st = state_of(shot)
    if st == ABSENT:
        return "jamais composé"
    if st == STALE:
        return "périmé"
    eng = (shot.get(F_ENGINE) or "").strip()
    return f"envoyé à {eng}" if eng else "à jour"
