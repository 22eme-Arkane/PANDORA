"""
api/live_video_prompt.py — Composition IA du prompt final LIVE.

Pendant de `api/video_prompt.py` (Cinéma), mais PAS une copie : le composeur Cinéma
impose les champs « Camera: / Lighting: / Sound: », dont trois sont interdits en
mapping. Le brancher tel quel sur le Live aurait produit exactement les défauts que
`core/live_bar.py` recense.

Pourquoi ce module existe (2026-07-26, demande Matthieu) : jusqu'ici le Live
assemblait son prompt de façon purement déterministe (`core/live_prompt.assemble`)
parce qu'une réécriture par l'IA risquait de diluer les beats et de casser le calage
musical. La demande est désormais d'avoir le même confort qu'au Cinéma — composition,
barre de chargement, résultat mémorisé.

L'arbitrage retenu ne supprime pas la garantie, il la DÉPLACE : la composition a
lieu, puis elle est VÉRIFIÉE. Une sortie qui a perdu la structure de barre (état au
premier temps → UNE transformation continue → état au dernier temps) est rejetée, et
l'appelant retombe sur l'assemblage déterministe. Les beats sont donc garantis par
contrôle et non par abstinence — et un échec est toujours visible, jamais silencieux.

Le contrôle porte sur QUATRE choses :

    barre       les trois ancres temporelles sont présentes (ouverture, progression,
                fermeture) — c'est ce qui distingue une barre d'une image fixe décrite
    continuité  aucune coupe, aucun changement de scène : un plan de mapping est un
                processus unique du temps 1 au temps 8
    caméra      en mapping, aucun terme de mouvement d'appareil affirmé — le
                vidéoprojecteur est boulonné (les « no pan / no zoom » des contraintes
                sont, eux, légitimes : le contrôle tient compte de la négation)
    boosters    aucun mot de qualité générique (cf. core/live_bar.BANNED_POSITIVES)

Le routage IA réutilise `task="video_prompt"` : c'est la même nature de tâche (« prompt
final → moteur ») et la préférence de moteur de Matthieu s'y applique déjà. Créer une
tâche dédiée aurait obligé à modifier `core/ai_registry.py`, partagé avec le Cinéma.
"""

from __future__ import annotations

import re

LAST_COMPOSE_ERROR = ""   # raison humanisée du dernier échec (crédits, quota, clé…)


# ── Consigne système — le socle, commun aux deux modes ────────────────────────
_SYSTEM_LIVE = """Tu écris le prompt final d'un plan de spectacle VIDÉO LIVE (VJing,
mapping vidéo projeté). On te donne la fiche du plan en français et son contexte.
Compose UN prompt en ANGLAIS, en prose dense, SANS étiquette, SANS liste à puces,
SANS crochet, SANS emoji.

CE QUI FAIT LA VALEUR DE CE PROMPT — la STRUCTURE DE BARRE :
Un plan live n'est pas une image : c'est UNE barre musicale. Elle a un état au
PREMIER temps, UNE seule transformation continue, et un état au DERNIER temps.
Tu dois rendre ces trois moments, dans cet ordre, avec des ancres temporelles
EXPLICITES en anglais :
  · ouverture   « At the first beat, … » (ou « The shot opens with … »)
  · progression « Across the bar, … » + un adverbe de progression (gradually,
                progressively, steadily, continuously, throughout…)
  · fermeture   « By the final beat, … » (ou « By the end, … »)
Ne fusionne JAMAIS ces trois moments en une description statique : un prompt qui
décrit un état sans progression est inutilisable, le plan doit ÉVOLUER sur la barre.

RÈGLES STRICTES :
- UNE seule transformation, continue, du premier au dernier temps. Aucune coupe,
  aucun changement de scène, aucun second plan.
- Ne transforme pas l'intention : même processus, même sens de progression que la
  fiche. Tu COMPLÈTES la précision visuelle, tu ne réécris pas le plan.
- N'introduis aucun objet ni motif absent de la fiche.
- Aucun mot de qualité générique (cinematic, 4K, 8K, ultra-detailed, masterpiece,
  photorealistic).
- Réponds UNIQUEMENT avec le prompt anglais final, sans commentaire ni préambule."""


def _system_for(engine: str = "", mode: str = "live") -> str:
    """Socle + grammaire du moteur ET du mode (core/live_grammar).

    C'est ici que le mapping devient contraignant : la consigne de format y
    interdit nommément Camera:, Lighting: et Sound:, là où la consigne Cinéma les
    exige. Un même moteur reçoit donc deux consignes opposées selon l'édition.
    """
    try:
        from core.live_grammar import format_rules
        return f"{_SYSTEM_LIVE}\n\n{format_rules(engine, mode)}"
    except Exception:
        return _SYSTEM_LIVE


# ── Détection de mention AFFIRMÉE (la négation ne compte pas) ─────────────────
# « no camera movement », « no zoom » sont des CONTRAINTES légitimes et figurent
# dans tout prompt de mapping correct. Sans cette nuance, le contrôle rejetterait
# précisément les prompts les mieux écrits.
_NEGATIONS = ("no ", "without ", "avoid ", "never ", "free of ", "not ")


def _asserted(text: str, term: str) -> bool:
    """True si `term` apparaît AFFIRMÉ (pas précédé d'une négation).

    Les formes fléchies comptent : « the camera slowly PANS right » est un
    mouvement d'appareil au même titre que « pan ». Sans le suffixe optionnel, le
    contrôle laissait passer exactement la tournure qu'un modèle produit
    naturellement (constat sur la première passe de test).
    """
    low = (text or "").lower()
    rx = r"(?<![a-z])" + re.escape(term.lower()) + r"(?:s|es|ing|ed)?(?![a-z])"
    for m in re.finditer(rx, low):
        avant = low[max(0, m.start() - 14):m.start()]
        if not any(avant.endswith(n) for n in _NEGATIONS):
            return True
    return False


# ── Les trois ancres de la barre ──────────────────────────────────────────────
_ANCRES_OUVERTURE = ("at the first beat", "on the first beat", "at the start",
                     "at the outset", "initially", "at first", "the shot opens",
                     "opens with", "begins with", "at the opening", "from the start")
_ANCRES_PROGRESSION = ("across the bar", "across the shot", "throughout", "gradually",
                       "progressively", "steadily", "continuously", "slowly",
                       "over the course", "little by little", "increasingly",
                       "as the bar")
_ANCRES_FERMETURE = ("by the final", "by the last", "by the end", "at the end",
                     "in the final", "finally", "ends with", "closes with",
                     "comes to rest", "settles into")

# Une coupe tue le calage : la barre doit être un processus unique.
_COUPURES = ("cut to", "cuts to", "jump cut", "scene change", "second shot",
             "then we see", "cross-dissolve", "smash cut")

# Mouvements d'appareil — interdits AFFIRMÉS en mapping (le projecteur est boulonné).
# « camera » y figure seul : la règle de core/live_bar n'est pas « pas de mouvement »
# mais « caméra VERROUILLÉE, jamais NOMMÉE ». Un prompt correct ne la mentionne que
# dans ses contraintes (« no camera movement »), donc toujours sous négation.
# « orbit » est volontairement absent : en mapping il décrit bien plus souvent un
# motif qui tourne qu'un déplacement d'appareil.
_CAMERA_MOUVANTE = ("camera", "pan", "tilt", "zoom", "dolly", "crane shot",
                    "push in", "pull back", "handheld", "parallax", "rack focus",
                    "tracking shot")


def validate_live_composed(output: str, *, mode: str = "live",
                           source_prompt: str = "") -> dict:
    """Contrôle déterministe de la prose composée. {valid, errors, warnings}.

    Chaque erreur est formulée pour être MONTRÉE à l'utilisateur : quand la
    composition est refusée, il doit comprendre pourquoi son plan est reparti sur
    l'assemblage déterministe.
    """
    from core.live_bar import BANNED_POSITIVES
    from core.live_grammar import allows_camera, banned_fields, normalize_mode

    mode = normalize_mode(mode)
    errors, warnings = [], []
    text = (output or "").strip()
    low = text.lower()

    if not text:
        return {"valid": False, "errors": ["réponse vide"], "warnings": []}
    if low.startswith(("voici", "here is", "here's", "sure,", "bien sûr")):
        errors.append("préambule parasite")
    if re.search(r"^\s*\[[^\]]+\]", text, flags=re.MULTILINE):
        errors.append("étiquettes de section encore présentes")

    # ① La structure de barre — la garantie qui remplace l'abstinence.
    manquantes = []
    if not any(a in low for a in _ANCRES_OUVERTURE):
        manquantes.append("l'état au premier temps")
    if not any(a in low for a in _ANCRES_PROGRESSION):
        manquantes.append("la transformation continue")
    if not any(a in low for a in _ANCRES_FERMETURE):
        manquantes.append("l'état au dernier temps")
    if manquantes:
        errors.append("structure de barre perdue — il manque " + ", ".join(manquantes))

    # ② La continuité : un plan de mapping ne se coupe pas.
    for c in _COUPURES:
        if _asserted(text, c):
            errors.append(f"coupe introduite dans la barre (« {c} »)")
            break

    # ③ La caméra, en mapping seulement.
    if not allows_camera(mode):
        for terme in _CAMERA_MOUVANTE:
            if _asserted(text, terme):
                errors.append(f"mouvement d'appareil affirmé en mapping (« {terme} ») "
                              "— le vidéoprojecteur est boulonné")
                break
        rx = re.compile(r"(?im)^[ \t]*(?:" +
                        "|".join(re.escape(l) for l in banned_fields(mode)) +
                        r")[ \t]*:")
        if rx.search(text):
            errors.append("champ interdit en mapping (Camera/Lighting/Sound/Music)")

    # ④ Les boosters de plateau : des défauts, projetés sur de la pierre.
    trouves = [w for w in BANNED_POSITIVES
               if re.search(r"(?<![a-zà-ÿ0-9])" + re.escape(w.lower()) +
                            r"(?![a-zà-ÿ0-9])", low)]
    if trouves:
        errors.append("mots de qualité génériques : " + ", ".join(sorted(set(trouves))))

    if text and len(text) < 150:
        warnings.append("prompt très court")
    return {"valid": not errors, "errors": errors, "warnings": warnings}


def _build_user_message(prompt: str, *, mode: str, style_suffix: str,
                        surface: str, bpm: float, beats: int,
                        duration, extras: list | None) -> str:
    """Fiche du plan + contexte. La GRILLE (BPM, temps) est donnée au composeur
    comme information de RYTHME — elle ne doit jamais ressortir dans le prompt :
    aucun moteur ne lit un tempo, et le chiffre pollue la tokenisation."""
    parts = [f"[FICHE DU PLAN]\n{(prompt or '').strip()}"]
    if surface.strip():
        parts.append("[SURFACE DE PROJECTION — géométrie réelle, à respecter]\n"
                     + surface.strip())
    parts.append("[STYLE VISUEL — à rendre en ANGLAIS, à placer en fin]\n"
                 + (style_suffix.strip() if style_suffix.strip() else "(aucun)"))
    if bpm:
        parts.append(f"[RYTHME — information de tempo, NE PAS écrire dans le prompt]\n"
                     f"{beats} temps à {bpm:g} BPM. La transformation doit couvrir "
                     "exactement cette durée, sans temps mort ni accélération finale.")
    if duration:
        parts.append(f"[DURÉE] {duration} seconds")
    for e in (extras or []):
        if (e or "").strip():
            parts.append(f"[CONTRAINTE TECHNIQUE — à respecter]\n{e.strip()}")
    if mode == "mapping":
        parts.append("[MODE] Mapping projeté sur façade : cadre verrouillé, noir "
                     "structurel (ce qui est noir n'est pas projeté), aucun son.")
    else:
        parts.append("[MODE] Live / VJ : le cadre peut bouger, mais le plan reste "
                     "une barre unique.")
    parts.append("[SON] NE PAS mentionner le son — le son, c'est le set.")
    return "\n\n".join(parts)


def compose(prompt: str, *, engine: str = "", mode: str = "live",
            style_suffix: str = "", surface: str = "", bpm: float = 0.0,
            beats: int = 8, duration=None, extras: list | None = None) -> str:
    """Prose anglaise du plan Live. Renvoie "" si la composition échoue ou est
    refusée — l'appelant replie alors sur `core.live_prompt.assemble()`.

    Appel RÉSEAU : à exécuter dans un QThread, jamais sur le thread UI.
    """
    global LAST_COMPOSE_ERROR
    LAST_COMPOSE_ERROR = ""
    try:
        from core import ai_provider
        from core.live_grammar import normalize_mode
        mode = normalize_mode(mode)
        system = _system_for(engine, mode)
        user = _build_user_message(prompt, mode=mode, style_suffix=style_suffix or "",
                                   surface=surface or "", bpm=bpm or 0.0,
                                   beats=beats or 8, duration=duration,
                                   extras=extras)
        try:
            out = (ai_provider.complete(system, user, tier="creative",
                                        max_tokens=8192,
                                        task="video_prompt") or "").strip()
        except Exception as _e:
            # Erreur de facturation/réseau : on la REMONTE telle quelle. La
            # confondre avec « prose invalide » ferait croire à un problème de
            # qualité de texte alors que c'est une clé ou un quota.
            try:
                LAST_COMPOSE_ERROR = ai_provider.humanize_ai_error(str(_e))
            except Exception:
                LAST_COMPOSE_ERROR = str(_e)[:200]
            return ""
        verdict = validate_live_composed(out, mode=mode, source_prompt=prompt)
        if not verdict["valid"]:
            LAST_COMPOSE_ERROR = "composition refusée : " + " · ".join(verdict["errors"])
            return ""
        # Dernier filet : la grammaire du mode s'applique AUSSI à une sortie IA.
        from core.live_grammar import enforce_mode, strip_names
        out, _ = enforce_mode(out, mode)
        out, _ = strip_names(out)
        return out
    except Exception:
        return ""
