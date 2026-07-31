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

# Sous ce rapport à la matière de départ, la « composition » est un résumé.
# 0,60 et non 0,90 : l'anglais est plus compact que le français, et retirer les
# étiquettes (« SURFACE : », « ÉTAT 0 : ») raccourcit légitimement le texte. Le
# seuil vise la perte GROSSIÈRE, pas le resserrement normal.
_SEUIL_PERTE = 0.60


def is_deterministic_refusal(why: str) -> bool:
    """True si `why` est un refus du contrôle, donc reproductible à l'identique."""
    return (why or "").startswith(REFUSAL_PREFIX)


_FINGERPRINT = ""


def grammar_fingerprint() -> str:
    """Empreinte du compositeur — versionne le cache des compositions.

    La consigne système est une ENTRÉE de la composition au même titre que la
    fiche : un correctif de consigne doit invalider les compositions mémorisées,
    sinon il n'atteint JAMAIS un plan déjà composé (audit du 2026-07-28 : le
    correctif « la composition ne résume plus » du 27/07 au soir restait sans
    effet sur tout plan dont la fiche n'avait pas bougé — le cache resservait
    l'ancienne version, et le correctif semblait ne rien changer).

    Empreinte = hash du SOURCE de ce module : en dev, toute retouche du
    compositeur invalide ; en build figé (source indisponible), la VERSION de
    PANDORA prend le relais — une mise à jour invalide.
    """
    global _FINGERPRINT
    if _FINGERPRINT:
        return _FINGERPRINT
    try:
        import hashlib, inspect, sys
        _src = inspect.getsource(sys.modules[__name__])
        _FINGERPRINT = hashlib.sha1(_src.encode("utf-8")).hexdigest()[:12]
    except Exception:
        try:
            from core.version import VERSION
            _FINGERPRINT = f"v{VERSION}"
        except Exception:
            _FINGERPRINT = "sans-empreinte"
    return _FINGERPRINT


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

# Résidus de français : le prompt DOIT sortir en anglais. Mots-outils testés
# en MOTS ENTIERS — l'ancien test par SOUS-CHAÎNE refusait des sorties
# parfaitement anglaises : « les  » attrapait angles/circles, « des  »
# attrapait shades/sides, et « façade » est un emprunt que l'anglais écrit
# couramment (la composition réussie du même plan disait « the limestone
# façade »). Constat Matthieu 2026-07-28 : « composition refusée : prompt
# encore en français (façade, les) » — refus ensuite MÉMORISÉ par le cache.
_MOTS_FRANCAIS = (
    "lumière", "pierre", "avec", "dans", "les", "des", "une",
    "qui", "vers", "puis", "aucun", "aucune", "jamais",
)
_RE_FRANCAIS = re.compile(
    r"\b(?:" + "|".join(_MOTS_FRANCAIS) + r")\b", re.IGNORECASE)


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

6. TU NE PERDS AUCUNE INFORMATION. C'est une RÉÉCRITURE, jamais un résumé. Tout
   ce que la fiche décrit de l'instant demandé — chaque ouverture, chaque
   matière, chaque couleur, chaque détail d'architecture, chaque contrainte
   visuelle — doit se retrouver dans le prompt final. Tu retires les étiquettes,
   tu traduis, tu réorganises dans la forme qu'attend le moteur ; tu ne coupes
   pas. Si le résultat est plus court que la fiche, c'est que tu as perdu
   quelque chose : reprends. La seule chose que tu écartes est ce qui décrit un
   AUTRE moment que celui demandé.

Réponds UNIQUEMENT avec le prompt final, sans commentaire ni préambule."""


def _refs_rules(engine: str, refs) -> str:
    """Consigne sur les IMAGES JOINTES et leur RÔLE.

    Sans elle, le compositeur écrit comme s'il n'y avait que du texte : deux
    phrases pour Seedream, conformément à sa doc… face à deux images. Le modèle
    n'a alors presque rien à rendre et recopie ce qu'il voit — l'image
    d'inspiration se retrouve plaquée sur la façade au lieu de l'inspirer
    (constat Matthieu, 2026-07-27).

    La désignation des images est un FAIT CONSTRUCTEUR, différent chez chacun
    (« Figure 1 » chez Seedream, « @image1 » chez FLUX.2, « the first attached
    image » chez Nano Banana) : on la lit dans `core.image_grammar`, jamais en
    dur ici.
    """
    _refs = [r for r in (refs or []) if (r or "").strip()]
    if not _refs:
        return ""
    try:
        from core.image_grammar import ref_syntax_label, ref_token
    except Exception:
        return ""
    _lignes = []
    for _i, _role in enumerate(_refs, start=1):
        _tok = ""
        try:
            _tok = ref_token(engine, _i) or ""
        except Exception:
            _tok = ""
        _lignes.append(f"  · {_tok or f'image {_i}'} — {_role}")
    try:
        _syntaxe = ref_syntax_label(engine)
    except Exception:
        _syntaxe = ""
    return (
        f"IMAGES JOINTES — {len(_refs)} image(s) accompagnent ce prompt, dans cet "
        "ordre :\n" + "\n".join(_lignes) +
        (f"\nCe moteur les désigne ainsi : {_syntaxe}. " if _syntaxe else "\n") +
        "Écris le prompt EN TENANT COMPTE d'elles : dis explicitement ce que le "
        "moteur doit faire de chacune. Une image de CANEVAS impose la géométrie "
        "et ne doit jamais être remplacée ; une image d'INSPIRATION ne fournit "
        "que palette, matière et ambiance, et ne doit jamais être recopiée ni "
        "devenir le sujet ; une image de COHÉRENCE est la FICHE OFFICIELLE d'un "
        "personnage, d'un décor ou d'un objet du film — son apparence ET sa "
        "facture graphique font autorité, et le prompt doit renvoyer à elle "
        "plutôt que de redécrire le sujet de zéro. Ne décris JAMAIS un élément "
        "d'une façon qui contredise sa fiche : si la fiche est peinte, le plan "
        "est peint.\n"
        "Et sois PLUS DÉTAILLÉ que pour un prompt sans image : un texte trop "
        "court laisse le moteur se rabattre sur ce qu'il voit, et il recopie."
    )


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
        # ⚠ La doc de ce moteur déconseille les LISTES DE MOTS-CLÉS ; elle ne
        # demande pas d'être BREF. Écrire « deux à quatre phrases » ici a
        # transformé une règle de FORME en ordre de COMPRESSION : le prompt est
        # passé de ~600 caractères à moins de 250 et la description a fondu
        # (constat Matthieu, 2026-07-27 : « la composition ne doit pas enlever
        # de l'information »). La contrainte porte sur la FORME, pas la longueur.
        base = (
            "FORMAT — de la prose descriptive, en phrases complètes et "
            "conversationnelles : AUTANT DE PHRASES QU'IL EN FAUT pour ne rien "
            "perdre de la fiche. Aucun champ nommé, aucune liste de mots-clés "
            "séparés par des virgules : ce moteur raisonne avant de peindre et "
            "une accumulation de tags dégrade ce raisonnement — mais une "
            "description longue et articulée ne le gêne pas. Le style se donne "
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


def _system_for(engine: str = "", kind: str = "", refs=None) -> str:
    """Socle + contexte d'usage + grammaire du moteur + rôle des images jointes."""
    _bloc = f"{_SYSTEM_IMAGE}\n\n[USAGE]\n{_kind_brief(kind)}\n\n{_format_rules(engine)}"
    _r = _refs_rules(engine, refs)
    return f"{_bloc}\n\n{_r}" if _r else _bloc


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
    _fr = sorted({m.group(0).lower() for m in _RE_FRANCAIS.finditer(low)})
    if len(_fr) >= 2:
        errors.append("prompt encore en français (" + ", ".join(_fr[:4]) + ")")

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
        # AVERTISSEMENT, jamais un refus : la règle des 2 à 4 phrases vaut pour
        # un texte SEUL. Avec des images jointes, un prompt trop court laisse le
        # moteur se rabattre sur ce qu'il voit — et il recopie l'inspiration au
        # lieu de s'en inspirer.
        if len(_phrases) > 8:
            warnings.append(f"{len(_phrases)} phrases — vérifier que le moteur suit")

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

    # ⑥ PERTE D'INFORMATION. Une composition est une RÉÉCRITURE, pas un résumé :
    #    « ça ne doit pas enlever de l'information » (Matthieu, 2026-07-27). On
    #    compare à la matière RÉELLEMENT à rendre — pas à la fiche entière, dont
    #    une partie décrit volontairement un autre moment. Refuser ici n'est pas
    #    une perte : le repli est précisément le texte complet.
    _ref = " ".join((source_prompt or "").split())
    if _ref and len(_ref) >= 200:
        _ratio = len(" ".join(text.split())) / float(len(_ref))
        if _ratio < _SEUIL_PERTE:
            errors.append(
                f"information perdue — le prompt fait {int(_ratio * 100)} % de "
                "la matière à rendre, c'est un résumé et non une réécriture")

    if len(text) < 80:
        warnings.append("prompt très court")
    return {"valid": not errors, "errors": errors, "warnings": warnings}


def compose(prompt: str, *, engine: str = "", kind: str = "", surface: str = "",
            moment: str = "", style_suffix: str = "", extras=None,
            refs=None, source_ref: str = "") -> str:
    """Prompt final anglais pour ce moteur d'image. "" si échec ou refus.

    Appel RÉSEAU : à exécuter dans un QThread, jamais sur le thread UI.
    """
    global LAST_COMPOSE_ERROR
    LAST_COMPOSE_ERROR = ""
    try:
        from core import ai_provider
        system = _system_for(engine, kind, refs)
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

        # `source_ref` = la matière RÉELLEMENT à rendre (le repli déterministe),
        # pas la fiche entière : celle-ci contient aussi ce qu'on demande
        # volontairement d'écarter, et la comparer condamnerait toute sortie.
        verdict = validate_image_composed(out, engine=engine,
                                          source_prompt=source_ref or "")
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
