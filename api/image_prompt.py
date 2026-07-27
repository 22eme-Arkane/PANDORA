"""
api/image_prompt.py — Composition IA du prompt final IMAGE.

Pendant de `api/video_prompt.py` (vidéo Cinéma) et `api/live_video_prompt.py`
(vidéo Live), pour le volet image : Moods, portraits, décors, accessoires, HMC,
véhicules.

Pourquoi ce module (2026-07-27, demande Matthieu) — trois constats mesurés :

  ① `core/image_grammar.build_image_prompt` ne réécrit que le CONTENANT. Le même
    corps FRANÇAIS traverse les cinq moteurs, étiquettes internes comprises :
    Seedream reçoit « SURFACE : … ÉTAT 0 : … » quand sa doc demande deux à quatre
    phrases naturelles, et FLUX.2 reçoit ce bloc fourré dans sa clé JSON.

  ② Rien ne traduit. Chaque autre appel de PANDORA passe par
    `core.lang.translate_to_english` avant d'envoyer ; le volet image était
    l'exception.

  ③ Les blocs d'une barre de mapping se contredisent pour une image FIXE.
    Exemple réel : « ÉTAT 0 : monde forestier vert-doré » avec « STYLE : bleu
    outremer à cyan électrique » — le STYLE décrit où le plan ARRIVE, l'ÉTAT 0
    d'où il PART. Aucun filtre déterministe ne peut trancher : il faut lire et
    réécrire. C'est précisément ce qu'un compositeur sait faire.

Le contrat est celui du Studio : la composition a lieu, puis elle est VÉRIFIÉE,
et l'appelant retombe sur l'assemblage déterministe si elle est refusée. Un échec
est toujours visible, jamais silencieux.

Le routage IA réutilise `task="video_prompt"` : c'est la même nature de tâche
(« prompt de travail → prompt final pour un moteur ») et la préférence de moteur
de Matthieu s'y applique déjà. Créer une tâche dédiée aurait obligé à modifier
`core/ai_registry.py`, partagé.

⚠ Ce module CONSOMME `core.image_grammar` — la table moteur→forme, les moteurs
sans négatif, les tokens de référence — il ne la recopie jamais. Deux tables
divergeraient au premier moteur ajouté au catalogue.
"""

from __future__ import annotations

import json
import re

LAST_COMPOSE_ERROR = ""

# Même marqueur que côté Live : distingue un verdict REPRODUCTIBLE du contrôle
# (à mémoriser, inutile de le repayer) d'un aléa d'infrastructure (à retenter).
REFUSAL_PREFIX = "composition refusée : "


def is_deterministic_refusal(why: str) -> bool:
    """True si `why` est un refus du contrôle, donc reproductible à l'identique."""
    return (why or "").startswith(REFUSAL_PREFIX)


# ── Ce que le prompt de travail contient et qui ne doit JAMAIS ressortir ──────
# Vocabulaire interne PANDORA. Il structure la barre pour l'auteur et pour le
# moteur VIDÉO ; pour un moteur d'image c'est du bruit sans référent.
#
# ⚠ N'y mettre que ce qui est SANS AMBIGUÏTÉ interne. « Action », « Style »,
# « Setting », « Subject » sont les champs OFFICIELS de Nano Banana Pro et de
# GPT Image 2 : les bannir refuserait précisément les sorties bien formées.
_ETIQUETTES_INTERNES = (
    "SURFACE", "ÉTAT 0", "ETAT 0", "STATE 0", "ÉTAT 1", "ETAT 1", "STATE 1",
    "TRANSFORMATION", "NOIR", "CONTRAINTES", "SOUND DESIGN", "GRILLE",
    "PROMPT VISUEL", "MISE EN SCÈNE", "STYLE VISUEL", "PLAN DE FEU", "AMBIANCE",
)

# Résidus de français : le prompt DOIT sortir en anglais. Mots-outils choisis
# pour ne pas exister en anglais, afin de ne pas déclencher sur un faux ami.
_MOTS_FRANCAIS = (
    "façade", "lumière", "pierre", "avec", "dans", "les ", "des ", "une ",
    "qui ", "sur la", "vers ", "puis ", "aucun", "aucune", "jamais",
)


def _kind_brief(kind: str) -> str:
    """Contexte d'usage — la phrase qui oriente la passe de raisonnement.

    Les guides fal sont explicites : dire à QUOI l'image est destinée oriente
    mieux le modèle qu'un adjectif de plus. C'est aussi ce qui empêche un mood de
    mapping de devenir une belle photo d'architecture.
    """
    k = (kind or "").strip().lower()
    if k == "mood_mapping":
        return (
            "This image is the OPENING FRAME of a video-mapping shot projected "
            "onto a real building at night. It will be used as the start image "
            "of a video generation, so the building's geometry must match the "
            "reference photograph exactly. Everything outside the projected "
            "light falls to pure black.")
    if k == "mood":
        return ("This image is a concept frame used to validate the lighting and "
                "atmosphere of a shot before animating it.")
    if k == "character":
        return ("This image is a character reference sheet for a film production: "
                "it must read as the SAME person in every later render.")
    if k == "decor":
        return ("This image is a location reference for a film production: "
                "readable layout, no people unless asked.")
    if k in ("accessory", "hmc", "vehicle"):
        return ("This image is a product-style reference of a single item for a "
                "film production: the object isolated and fully readable.")
    return "This image is a visual reference for a film production."


# ── Consigne système ─────────────────────────────────────────────────────────
_SYSTEM_IMAGE = """Tu écris le prompt final d'une IMAGE FIXE destinée à un moteur
de génération d'images. On te donne la fiche de travail, en français, et le
contexte. Compose UN prompt en ANGLAIS.

CE QUI FAIT LA VALEUR DE CE PROMPT :

1. UN SEUL INSTANT. Une image n'a pas de durée. Si la fiche décrit une évolution
   (un état de départ, une transformation, un état d'arrivée), tu ne décris QUE
   l'instant demandé. Tu ne mentionnes JAMAIS ce qui n'est pas encore là : ne pas
   vouloir un élément et le décrire quand même, c'est l'obtenir.

2. TU RÉSOUS LES CONTRADICTIONS. Les blocs d'une fiche sont écrits pour toute la
   durée du plan : le bloc de STYLE décrit souvent où le plan ARRIVE, alors que
   l'état demandé est celui d'où il PART. Dans ce cas tu ne gardes du style que
   ce qui vaut pour l'instant demandé — la facture, la matière, le traitement —
   et tu ÉCARTES la palette et les motifs qui n'apparaissent que plus tard.
   C'est le point le plus important de ta tâche.

3. AUCUNE ÉTIQUETTE INTERNE. Les mots SURFACE, ÉTAT 0, TRANSFORMATION, NOIR,
   CONTRAINTES structurent la fiche pour son auteur ; ils n'ont aucun sens pour
   un moteur d'image et le désorientent. Ils ne doivent pas apparaître.

4. DU CONCRET. Les adjectifs d'appréciation ne se dessinent pas : « magnifique »
   ne donne rien, « peinture écaillée » et « lumière rasante » si. Aucun mot de
   qualité générique (cinematic, 4K, 8K, ultra-detailed, masterpiece,
   photorealistic) : ils dégradent la passe de raisonnement des moteurs récents.

5. TU NE TRANSFORMES PAS L'INTENTION. Même sujet, même lumière, même parti pris
   que la fiche. Tu complètes la précision visuelle, tu n'inventes ni objet ni
   personnage absent.

Réponds UNIQUEMENT avec le prompt final, sans commentaire ni préambule."""


def _format_rules(engine: str) -> str:
    """Consigne de FORME, dérivée de la grammaire réelle du moteur.

    Lue dans `core.image_grammar` : si le catalogue gagne un moteur, la consigne
    suit sans qu'on touche ici.
    """
    try:
        from core.image_grammar import grammar_for, supports_negatives
        shape = grammar_for(engine)
        negs  = supports_negatives(engine)
    except Exception:
        shape, negs = "plain", True

    if shape == "fields":
        # Les deux moteurs à champs n'ont PAS le même gabarit officiel — c'est un
        # fait constructeur, pas une préférence. `core.image_grammar` ne modélise
        # aujourd'hui que celui de Nano Banana ; le gabarit GPT est donc porté
        # ici, où il ne sert qu'à INSTRUIRE le rédacteur.
        if (engine or "").strip().lower().startswith("gpt"):
            base = (
                "FORMAT — gabarit GPT Image 2, dans cet ordre :\n"
                "Scene: …\nSubject: …\nImportant details: …\nUse case: …\n"
                "Constraints: …\n"
                "La liste de contraintes n'est PAS optionnelle sur ce moteur, et "
                "elle fonctionne mieux en paragraphe de clôture.")
        else:
            base = (
                "FORMAT — brief à champs nommés, une ligne par champ, dans cet "
                "ordre et uniquement s'ils ont du contenu :\n"
                "Subject: …\nAction: …\nSetting: …\nStyle: …\n"
                "Composition and camera: …\nLighting and color: …\nConstraints: …\n"
                "Le contexte d'usage se met en PREMIER, en une phrase, avant "
                "les champs.")
    elif shape == "natural":
        base = (
            "FORMAT — DEUX à QUATRE phrases descriptives complètes, en prose "
            "conversationnelle. Aucun champ nommé, aucune liste de mots-clés "
            "séparés par des virgules : ce moteur raisonne avant de peindre et "
            "une accumulation de tags dégrade ce raisonnement. Le style se donne "
            "comme un adjectif portant sur TOUTE la scène (« a moody noir "
            "photograph of… ») et non comme une étiquette ajoutée à la fin.")
    elif shape == "json":
        base = (
            "FORMAT — un OBJET JSON valide et RIEN d'autre, avec ces clés quand "
            "elles ont du sens : scene, subjects (liste d'objets à description / "
            "position), style, color_palette (liste de codes hex), lighting, "
            "mood, composition, camera. Aucun texte hors de l'objet.")
    else:
        base = ("FORMAT — prose anglaise dense, un ou deux paragraphes, sans "
                "étiquette, sans crochet, sans emoji.")

    if negs:
        base += ("\nCONTRAINTES — ce moteur lit les interdits en clair : "
                 "termine par une ligne « Constraints: … » qui les liste.")
    else:
        base += ("\nCONTRAINTES — ce moteur N'A PAS de prompt négatif : on "
                 "n'interdit pas, on OCCUPE la place. N'écris jamais « no X » ; "
                 "décris positivement ce qui est là à la place (« nothing but "
                 "open black sky behind it » plutôt que « no background »).")
    return base


def _system_for(engine: str = "", kind: str = "") -> str:
    """Socle + contexte d'usage + grammaire du moteur."""
    return f"{_SYSTEM_IMAGE}\n\n[USAGE]\n{_kind_brief(kind)}\n\n{_format_rules(engine)}"


def _sans_interdits(text: str) -> str:
    """Retire les interdits résiduels d'un texte destiné à un moteur SANS négatif.

    `core.image_grammar.neutralize_negatives` fait le gros du travail mais reste
    partiel : « There is no text and no watermark anywhere » — deux interdits
    dans une seule proposition — lui échappe. On termine à la PHRASE : une
    contrainte occupe presque toujours sa propre phrase, et en retirer une de
    trop coûte moins cher que de refuser toute la composition pour un « no ».
    """
    from core.image_grammar import BASE_CONSTRAINTS, neutralize_negatives, to_positive

    out = text or ""
    try:
        out, _ = neutralize_negatives(out)
    except Exception:
        pass
    _phrases = re.split(r"(?<=[.!?])\s+", out)
    _gardees = [p for p in _phrases
                if not re.search(r"(?i)\bno\s+[a-z]", p)]
    if len(_gardees) != len(_phrases):
        out = " ".join(_gardees).strip()
        # Ce qui est retiré ne doit pas être PERDU : on le remet en positif.
        try:
            _pos = to_positive(BASE_CONSTRAINTS)
            if _pos:
                out = (out + " " + ", ".join(_pos[:3]) + ".").strip()
        except Exception:
            pass
    return re.sub(r"\s{2,}", " ", out).strip()


def _build_user_message(prompt: str, *, kind: str, surface: str,
                        moment: str, style_suffix: str, extras,
                        engine: str = "") -> str:
    """Fiche de travail + contexte. Le MOMENT demandé est dit explicitement.

    Sur un moteur SANS prompt négatif, le bloc de contraintes de la fiche est
    converti en positif AVANT d'être montré : lui demander de ne pas recopier une
    liste d'interdits qu'on lui met sous les yeux est un combat perdu d'avance —
    il l'a recopiée à chaque fois.
    """
    _p = (prompt or "").strip()
    _contraintes_pos = []
    try:
        from core.image_grammar import (BASE_CONSTRAINTS, supports_negatives,
                                        to_positive)
        if _p and not supports_negatives(engine):
            # La fiche est en FRANÇAIS : `neutralize_negatives`, qui travaille sur
            # l'anglais, n'y peut rien. On RETIRE donc le bloc de contraintes au
            # lieu de tenter de le réécrire, et on redonne l'équivalent positif à
            # part. Lui montrer une liste d'interdits en lui demandant de ne pas
            # la recopier est un combat perdu — il l'a recopiée à chaque essai.
            _p = re.sub(r"(?im)^[ \t]*(?:CONTRAINTES|CONSTRAINTS)[ \t]*:.*$", "", _p)
            _p = re.sub(r"\n{3,}", "\n\n", _p).strip()
            _contraintes_pos = to_positive(BASE_CONSTRAINTS)
    except Exception:
        pass
    parts = [f"[FICHE DE TRAVAIL]\n{_p}"]
    if _contraintes_pos:
        parts.append("[CONTRAINTES — ce moteur n'a PAS de prompt négatif : "
                     "exprime-les ainsi, en POSITIF, jamais en « no … »]\n"
                     + ", ".join(_contraintes_pos))
    if (moment or "").strip():
        parts.append("[INSTANT À RENDRE — et lui seul]\n" + moment.strip())
    if (surface or "").strip():
        parts.append("[SURFACE DE PROJECTION — géométrie réelle, à respecter]\n"
                     + surface.strip())
    if (style_suffix or "").strip():
        parts.append("[STYLE DU PROJET — à fondre dans la description]\n"
                     + style_suffix.strip())
    for e in (extras or []):
        if (e or "").strip():
            parts.append(f"[CONTRAINTE TECHNIQUE — à respecter]\n{e.strip()}")
    return "\n\n".join(parts)


# ── Contrôle déterministe de la sortie ───────────────────────────────────────
def validate_image_composed(output: str, *, engine: str = "",
                            source_prompt: str = "") -> dict:
    """{valid, errors, warnings}. Chaque erreur est formulée pour être MONTRÉE."""
    from core.image_grammar import grammar_for, strip_quality_boosters, supports_negatives

    errors, warnings = [], []
    text = (output or "").strip()
    low  = text.lower()

    if not text:
        return {"valid": False, "errors": ["réponse vide"], "warnings": []}
    if low.startswith(("voici", "here is", "here's", "sure,", "bien sûr", "```json",
                       "certainly")):
        errors.append("préambule parasite")

    # ① Les étiquettes internes ne doivent pas survivre.
    _vues = [e for e in _ETIQUETTES_INTERNES
             if re.search(r"(?<![A-Za-zÀ-ÿ])" + re.escape(e) + r"\s*:", text,
                          re.IGNORECASE)]
    if _vues:
        errors.append("étiquettes internes conservées : " + ", ".join(sorted(set(_vues))))
    # Les blocs du prompt de travail sont écrits « [🎬 ACTION] » : on les attrape
    # par leur FORME, ce qui couvre aussi ceux qu'on n'a pas listés — et sans
    # risquer de refuser un champ officiel qui porterait le même nom.
    if re.search(r"^\s*\[[^\]]+\]", text, flags=re.MULTILINE):
        errors.append("blocs entre crochets encore présents")

    # ② Le prompt doit être en ANGLAIS. C'était le défaut historique du volet
    #    image : le français partait tel quel au moteur.
    _fr = [m for m in _MOTS_FRANCAIS if m in low]
    if len(_fr) >= 2:
        errors.append("prompt encore en français (" + ", ".join(sorted(set(_fr))[:4]) + ")")

    # ③ Les boosters dégradent la passe de raisonnement des moteurs récents.
    _, boosters = strip_quality_boosters(text)
    if boosters:
        errors.append("mots de qualité génériques : " + ", ".join(sorted(set(boosters))))

    # ④ Forme réellement attendue par ce moteur.
    shape = grammar_for(engine)
    if shape == "json":
        try:
            _o = json.loads(text)
            if not isinstance(_o, dict):
                errors.append("JSON valide mais ce n'est pas un objet")
        except Exception:
            errors.append("ce moteur attend un objet JSON, la sortie n'en est pas un")
    elif shape == "fields":
        # Pas d'ancrage en début de ligne : le gabarit GPT Image 2 tient
        # légitimement sur un paragraphe continu, champs enchaînés.
        if not re.search(r"(?i)\b(subject|scene|action|setting|style|"
                         r"important details)\s*:", text):
            errors.append("aucun champ nommé alors que ce moteur en attend")
    elif shape == "natural":
        if re.search(r"(?im)^\s*(subject|action|setting|style|constraints)\s*:", text):
            errors.append("champs nommés alors que ce moteur veut de la prose")
        _phrases = [p for p in re.split(r"(?<=[.!?])\s+", text) if p.strip()]
        if len(_phrases) > 6:
            warnings.append(f"{len(_phrases)} phrases — ce moteur en préfère 2 à 4")

    # ⑤ Interdits en clair sur un moteur qui n'en a pas : ils deviennent des
    #    SUJETS. « no text » sur Seedream, c'est du texte à l'image.
    if not supports_negatives(engine):
        # Seuls les interdits NUS (« no text », « no watermark ») posent problème.
        # « without » n'est PAS flagué : les réécritures positives du dépôt s'en
        # servent comme préposition (« clean surfaces without signage »), et les
        # bannir ferait refuser par le contrôle ce que la réparation vient tout
        # juste de produire — le serpent qui se mord la queue.
        if re.search(r"(?i)\bno\s+[a-z]", text):
            errors.append("interdits en clair alors que ce moteur n'a pas de "
                          "prompt négatif — ils seront rendus comme des sujets")

    if len(text) < 80:
        warnings.append("prompt très court")
    return {"valid": not errors, "errors": errors, "warnings": warnings}


def compose(prompt: str, *, engine: str = "", kind: str = "", surface: str = "",
            moment: str = "", style_suffix: str = "", extras=None) -> str:
    """Prompt final anglais pour ce moteur d'image. "" si échec ou refus.

    Appel RÉSEAU : à exécuter dans un QThread, jamais sur le thread UI.
    """
    global LAST_COMPOSE_ERROR
    LAST_COMPOSE_ERROR = ""
    try:
        from core import ai_provider
        system = _system_for(engine, kind)
        user   = _build_user_message(prompt, kind=kind, surface=surface,
                                     moment=moment, style_suffix=style_suffix,
                                     extras=extras, engine=engine)
        try:
            out = (ai_provider.complete(system, user, tier="creative",
                                        max_tokens=8192,
                                        task="video_prompt") or "").strip()
        except Exception as _e:
            # Erreur de facturation/réseau : REMONTÉE telle quelle. La confondre
            # avec « prose invalide » ferait croire à un problème de qualité de
            # texte alors que c'est une clé ou un quota.
            try:
                LAST_COMPOSE_ERROR = ai_provider.humanize_ai_error(str(_e))
            except Exception:
                LAST_COMPOSE_ERROR = str(_e)[:200]
            return ""

        # Une clôture ```json … ``` est fréquente et inoffensive : on la retire
        # avant de juger, plutôt que de refuser une sortie par ailleurs correcte.
        out = re.sub(r"^```(?:json|text)?\s*|\s*```$", "", out).strip()

        # Filet côté SORTIE : même la fiche nettoyée, un modèle glisse parfois un
        # « no text ». On RÉPARE avant de juger — refuser ferait perdre une
        # composition par ailleurs bonne, et le repli déterministe est pire.
        try:
            from core.image_grammar import supports_negatives as _sn
            if not _sn(engine):
                out = _sans_interdits(out)
        except Exception:
            pass

        verdict = validate_image_composed(out, engine=engine, source_prompt=prompt)
        if not verdict["valid"]:
            LAST_COMPOSE_ERROR = REFUSAL_PREFIX + " · ".join(verdict["errors"])
            return ""

        # Dernier filet : les noms d'IP/studios n'ont pas leur place au payload.
        try:
            from core.engine_grammar import strip_ip_names
            out, _ = strip_ip_names(out)
        except Exception:
            pass
        return out.strip()
    except Exception:
        return ""
