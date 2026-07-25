"""
core/image_grammar.py — Grammaire de prompt par moteur IMAGE.

Pendant du volet vidéo (`core/engine_grammar.py`), pour tout ce qui produit une
IMAGE : portraits de casting, décors, accessoires, véhicules, HMC, moods du
storyboard, et l'onglet Image IA.

Trois grammaires (dossier de recherche fal.ai fourni par Matthieu, 25/07/2026 —
celui-ci s'appuie sur de vrais guides de prompting publiés par fal, pas sur des
reconstructions) :

  fields   — Nano Banana Pro, GPT Image 2 : brief de directeur artistique à champs
             nommés (Subject / Action / Setting / Style / Composition and camera /
             Lighting and color / Text / Constraints). Les NÉGATIFS sont supportés
             et attendus : la doc dit que la liste de contraintes n'est pas
             optionnelle.

  natural  — Seedream 5 : 2 à 4 phrases descriptives en langage naturel. Le modèle
             fait une passe de raisonnement avant de peindre.
             ⚠ ByteDance a RETIRÉ de l'API le prompt négatif, le seed, le guidance
             scale et le nombre de steps. On ne peut donc RIEN interdire : les
             contraintes doivent être converties en descriptions POSITIVES (occuper
             la place au lieu d'interdire) ou abandonnées. Les « quality boosters »
             (masterpiece, best quality, 8K) DÉGRADENT le résultat en distrayant la
             passe de raisonnement — ils sont retirés.

  json     — FLUX.2, Bria FIBO : objet à clés. Les négatifs sont mal gérés (ignorés).
             Les codes HEX sont lus s'ils sont précédés du mot « hex » ou « color ».

Règles communes : une image fige UN INSTANT (jamais une durée), aucun emoji ni
crochet dans le payload, pas de nom propre d'IP/studio (réutilise le filtre du volet
vidéo), et les adjectifs creux ne se rendent pas — « peinture écaillée » se dessine,
« magnifique » non.
"""

from __future__ import annotations

import re


# Clé de moteur image → grammaire.
# ⚠ Les clés sont celles du catalogue canonique `core/image_engines.ENGINES`
# (source : studio_images/engines.py + les 2 extras côté éléments). Les alias
# « longs » restent acceptés pour ne casser aucun appel externe.
_GRAMMAR_BY_ENGINE = {
    # Brief à champs (négatifs supportés)
    "nb2":              "fields",
    "nb_pro":           "fields",
    "nb2_lite":         "fields",
    "gpt2":             "fields",
    "nano_banana":      "fields",
    "nano_banana_pro":  "fields",
    "gpt_image_2":      "fields",
    "gpt-image-2":      "fields",
    # Langage naturel raisonné (AUCUN négatif possible)
    "seedream5":        "natural",
    "seedream5_pro":    "natural",
    "seedream5_lite":   "natural",
    "seedream45":       "natural",
    "seedream":         "natural",
    # JSON structuré
    "flux2":            "json",
    "flux_2":           "json",
    "flux2_pro":        "json",
    "flux2_flex":       "json",
    "fibo":             "json",
    # Prose descriptive — FLUX 1.x, Z-Image, Qwen, Ideogram, Recraft et le chemin
    # Flux historique des Moods. Ces moteurs n'ont pas de champ négatif dédié mais
    # lisent la prose telle quelle : on garde les interdits en clair (comportement
    # actuel, aucune régression).
    "flux":             "plain",
    "flux_ultra":       "plain",
    "zimage":           "plain",
    "qwen_image":       "plain",
    "ideogram":         "plain",
    "ideogram4":        "plain",
    "recraft":          "plain",
}

# Libellés destinés à s'afficher À CÔTÉ du nom du moteur : ils décrivent la FORME
# du prompt, sans renommer de moteur (« brief à champs (Nano Banana Pro / GPT Image
# 2) » posé à côté de « Nano Banana 2 » se lisait comme une contradiction).
GRAMMAR_LABELS = {
    "fields":  "brief à champs nommés",
    "natural": "prose descriptive, sans interdit",
    "json":    "objet JSON",
    "plain":   "prose descriptive",
}

# Moteurs SANS prompt négatif ni seed : l'API les a retirés.
NO_NEGATIVE_ENGINES = {"seedream5", "seedream5_pro", "seedream5_lite",
                       "seedream45", "seedream"}


def grammar_for(engine_key: str) -> str:
    """Grammaire attendue par ce moteur image. Repli « plain »."""
    return _GRAMMAR_BY_ENGINE.get((engine_key or "").strip().lower(), "plain")


def grammar_label(engine_key: str) -> str:
    return GRAMMAR_LABELS.get(grammar_for(engine_key), GRAMMAR_LABELS["plain"])


def supports_negatives(engine_key: str) -> bool:
    """Peut-on écrire des interdits EN CLAIR (« no text », « no person ») ?

    False pour Seedream (ByteDance a retiré le prompt négatif de l'API : le mot
    « no » y est lu comme un élément à représenter) et pour le JSON de FLUX.2, qui
    les ignore. Dans ces deux cas les contraintes doivent devenir POSITIVES.
    True pour le brief à champs (Nano Banana / GPT Image) et pour la prose simple
    (FLUX 1.x, Z-Image, Qwen, Ideogram, Recraft) — comportement historique."""
    if (engine_key or "").strip().lower() in NO_NEGATIVE_ENGINES:
        return False
    return grammar_for(engine_key) in ("fields", "plain")


# ── Contraintes ────────────────────────────────────────────────────────────────

# Valables pour toute image de production, quel que soit le sujet.
BASE_CONSTRAINTS = [
    "no text or lettering anywhere",
    "no watermark",
    "no extra fingers",
    "no lens flare",
    "no stock-photo polish",
]

# Contraintes CONTEXTUELLES — ajoutées seulement quand le cas se présente.
# ⚠ « no halo / no nimbus / no religious iconography » n'est PAS universel : le
# dossier le prescrit « tant que le personnage est celui-là ». L'ajouter partout
# polluerait les projets qui n'ont rien de religieux.
_RELIGIOUS_HINTS = (
    "jésus", "jesus", "christ", "vierge", "marie", "saint", "sainte", "apôtre",
    "apotre", "moïse", "moise", "bouddha", "buddha", "prophète", "prophete",
    "ange", "angel", "madone", "madonna",
)
RELIGIOUS_CONSTRAINTS = [
    "no halo", "no nimbus", "no religious iconography",
]
SOLO_CONSTRAINT = "no second person"


def context_constraints(subject_text: str = "", solo: bool = False) -> list[str]:
    """Contraintes contextuelles à ajouter aux contraintes de base.

    `subject_text` : nom/description du sujet — s'il évoque une figure religieuse,
    on ajoute l'anti-auréole (les modèles ajoutent un halo par défaut dès qu'ils
    reconnaissent le personnage, ce qui casse une intention comique).
    `solo` : le plan ne contient qu'un personnage → interdire un second."""
    out = []
    low = (subject_text or "").lower()
    if any(h in low for h in _RELIGIOUS_HINTS):
        out.extend(RELIGIOUS_CONSTRAINTS)
    if solo:
        out.append(SOLO_CONSTRAINT)
    return out


# Conversion des interdits en formulations POSITIVES, pour les moteurs qui ne
# savent pas interdire (Seedream 5). « On n'interdit pas, on occupe la place. »
_POSITIVE_REWRITES = {
    "no halo": "bare head, uncovered hair",
    "no nimbus": "plain sky directly behind the head",
    # ⚠ La réécriture ne doit contenir AUCUN « no » : sur un moteur sans négatif,
    # le mot serait lu comme un élément à représenter.
    "no religious iconography": "plain everyday setting",
    "no second person": "completely alone in the frame",
    "no visible lamp or light source in frame":
        "lit entirely by natural light coming from outside the frame",
    "no text or lettering anywhere": "clean surfaces without signage",
    "no watermark": "clean uncluttered image",
    "no lens flare": "clean optics",
    "no stock-photo polish": "raw, naturalistic rendering",
}


def to_positive(constraints: list[str]) -> list[str]:
    """Réécrit des contraintes négatives en descriptions positives.

    Celles qui n'ont pas d'équivalent positif utile (« no extra fingers ») sont
    ABANDONNÉES plutôt que traduites mot à mot : sur un moteur sans négatif, écrire
    « extra fingers » augmenterait la probabilité d'en voir."""
    out = []
    for c in constraints or []:
        v = _POSITIVE_REWRITES.get((c or "").strip().lower())
        if v and v not in out:
            out.append(v)
    return out


# « Quality boosters » : dégradent Seedream 5 (ils distraient la passe de
# raisonnement) et sont interdits par la doctrine de prompt de PANDORA.
_BOOSTERS_RE = re.compile(
    r"(?<![A-Za-zÀ-ÿ])(masterpiece|best quality|high quality|ultra[- ]?hd|8k|4k|"
    r"highly detailed|ultra[- ]?detailed|award[- ]winning|trending on artstation)"
    r"(?![A-Za-zÀ-ÿ])",
    re.IGNORECASE,
)


def strip_quality_boosters(text: str) -> tuple[str, list[str]]:
    """Retire les mots de qualité génériques. Retourne (texte, retirés)."""
    found = []
    for m in _BOOSTERS_RE.finditer(text or ""):
        v = m.group(0)
        if v.lower() not in {f.lower() for f in found}:
            found.append(v)
    if not found:
        return (text or ""), []
    out = _BOOSTERS_RE.sub("", text or "")
    out = re.sub(r"\s*,\s*,+", ", ", out)
    out = re.sub(r"[ \t]{2,}", " ", out)
    out = re.sub(r"\s+([,.;:])", r"\1", out)
    out = re.sub(r"^[\s,;:]+|[\s,;:]+$", "", out)
    return out.strip(), found


# ── Ce qui ne concerne QUE la vidéo et n'a rien à faire dans un prompt image ───
# Une image fige UN INSTANT : elle n'a ni mouvement, ni vitesse, ni durée, ni son.
# Ces mentions ne sont pas neutres — elles poussent le moteur à dessiner du flou de
# filé, des traînées de mouvement ou une composition « en cours de travelling ».
# La HAUTEUR de caméra part aussi (décision Matthieu 2026-07-25) : l'axe la porte
# déjà, et le doublon fait dériver le cadrage.
# En revanche la valeur de plan, l'axe, la focale, la profondeur de champ et la
# distance RESTENT : ce sont des propriétés d'une image fixe.

_CAM_MOTION_RE = re.compile(
    r"(?i)("
    r"\bcamera\s+(?:\w+\s+){0,2}?"
    r"(?:moves?|pushes?|pulls?|tracks?|trucks?|pans?|tilts?|dollies|zooms?|orbits?|"
    r"glides?|drifts?|rises?|descends?|circles?|follows?|sweeps?|creeps?|floats?|"
    r"travels?|arcs?)\b"
    # « dolly » seul est ambigu (poupée, chariot de jouet) : on exige la suite
    # cinéma. Le verbe « camera dollies… » est déjà pris par l'alternative ci-dessus.
    r"|\bdolly[- ](?:push|pull|in|out|shot|move|track|zoom|forward|backward)\b"
    r"|\bsteadicam\b"
    r"|\btracking shot\b|\btravelling shot\b|\btravelling (?:in|out|forward|backward)\b"
    r"|\bhandheld\s+(?:camera|cam|shot|footage|look|feel|style)\b"
    r"|\borganic movement\b"
    r"|\bpush(?:es|ing)? in\b|\bpull(?:s|ing)? (?:out|back)\b"
    r"|\bzoom(?:s|ing)? (?:in|out)\b"
    r"|\b(?:horizontal|vertical|whip|slow|quick|gentle)\s+pan(?:ning)?\b"
    r"|\bpan(?:s|ning)?\s+(?:left|right|across|over|towards?|to the)\b"
    r"|\b(?:downward|upward|vertical)\s+tilt\b|\btilt(?:s|ing)?\s+(?:up|down)\b"
    # « crane » et « handheld » sont volontairement exigeants : une grue de plateau
    # et une grue oiseau s'écrivent pareil en anglais, et un miroir « handheld » est
    # un accessoire. Sans contexte caméra explicite, on ne touche à rien.
    r"|\bcrane\s+(?:or drone|aerial|shot|move|movement|up|down)\b|\bcamera cranes?\b"
    r"|\bgimbal\b|\bdrone (?:aerial )?(?:move|shot|flight)\b"
    r"|\bcamera (?:movement|move|motion)\b"
    r"|\bno (?:pan|tilt|dolly|zoom)\b"
    r"|\blocked-off\b|\bfixed tripod\b|\bstatic camera\b"
    r"|\bmotion blur\b|\bmotion trail\b"
    r")")

_SPEED_RE = re.compile(
    r"(?i)\b(slow[- ]?motion|slo-?mo|fast motion|sped[- ]?up|time[- ]?lapse|"
    r"speed ramp(?:ing)?|frame rate|fps)\b")

_HEIGHT_RE = re.compile(
    r"(?i)(\bcamera\s+[\d.]+\s*m\s+high\b"
    r"|\b(?:ground-level|waist-level|low waist-level|eye-level|slightly elevated|"
    r"high overhead)\s+viewpoint\b"
    r"|\bcamera\s+(?:at|height)\b[^,.]*\bheight\b)")

# ⚠ « 8 s » exige un ESPACE : sans lui, « a 1970s leather jacket » ou « 80s
# sneakers » (descriptions de costume parfaitement courantes) étaient lus comme une
# durée et la proposition entière disparaissait.
_DURATION_RE = re.compile(
    r"(?i)(\b\d+(?:\.\d+)?\s*(?:seconds?|secs?)\b"
    r"|\b\d+\s+s\b(?=\s|$|[,.;])"
    r"|\bduration\b|\b\d+-second\b)")

# ⚠ « audio » seul est un mot d'objet (« an audio cassette », « audio interface ») :
# on ne vise que les tournures qui décrivent une BANDE SON.
_AUDIO_RE = re.compile(
    r"(?i)\b(sound design|sound effects?|the sound of|audible|voice[- ]?over|"
    r"ambient sound|ambience track|sfx|foley|audio (?:track|mix|design|layer)|"
    r"soundtrack)\b")

# ── Les mêmes règles, en FRANÇAIS ─────────────────────────────────────────────
# Indispensable : le corps du prompt d'un plan est écrit dans la langue de travail
# et n'est traduit qu'au moment de la composition finale. Sans ces motifs, « la
# caméra avance lentement vers lui. 8 secondes. » traversait intact tout le filtre
# anglais et arrivait tel quel au moteur d'image (constaté au rendu, 2026-07-25).
#
# Volontairement prudents : « panoramique » seul décrit aussi une vue panoramique,
# et « grue » est un oiseau autant qu'un engin de plateau — on exige donc soit le
# vocabulaire exact du Storyboard, soit un verbe de caméra explicite.
_CAM_MOTION_FR_RE = re.compile(
    r"(?i)("
    r"\b(?:la\s+|une\s+)?cam[ée]ra\s+(?:\w+\s+){0,2}?"
    r"(?:avance|recule|s'approche|se rapproche|s'[ée]loigne|suit|pivote|tourne|"
    r"monte|descend|glisse|survole|balaie|accompagne|se d[ée]place|bouge|zoome|"
    r"d[ée]zoome|panote|effectue|remonte|plonge|reste fixe)"
    r"|\btravelling\b"
    r"|\bpanoramique\s+(?:horizontal|vertical|lent|rapide|filé)\b"
    r"|\bzoom\s+(?:avant|arri[èe]re)\b"
    r"|\bsteadicam\b|\bcam[ée]ra\s+port[ée]e\b|\bcam[ée]ra\s+[àa]\s+l'[ée]paule\b"
    r"|\bplan\s+fixe\b|\bcam[ée]ra\s+fixe\b|\bmouvement\s+de\s+cam[ée]ra\b"
    r"|\bvue\s+drone\b|\ben\s+drone\b|\bau\s+drone\b|\bprise\s+de\s+vue\s+a[ée]rienne\b"
    r"|\bfil[ée]\s+de\s+mouvement\b|\bflou\s+de\s+bougé\b"
    r")")

_SPEED_FR_RE = re.compile(
    r"(?i)\b(?:au\s+)?ralenti\b|\bacc[ée]l[ée]r[ée]\b|\bhyperlapse\b|\btimelapse\b|"
    r"\bvitesse\s+de\s+d[ée]filement\b")

_HEIGHT_FR_RE = re.compile(
    r"(?i)\bcam[ée]ra\s+[àa]\s+[\d.,]+\s*m\s+(?:de\s+haut|du\s+sol)\b"
    r"|\bhauteur\s+(?:de\s+)?cam[ée]ra\b")

_DURATION_FR_RE = re.compile(
    r"(?i)\b\d+(?:[.,]\d+)?\s*(?:secondes?|sec\.?)\b|\bdur[ée]e\s+(?:du\s+plan|de)\b")

_AUDIO_FR_RE = re.compile(
    r"(?i)\bbande[- ]son\b|\bbruitage\b|\bvoix\s+off\b|\bambiance\s+sonore\b|"
    r"\bnappe\s+sonore\b|\bdesign\s+sonore\b")

_VIDEO_ONLY_RES = (_CAM_MOTION_RE, _SPEED_RE, _HEIGHT_RE, _DURATION_RE, _AUDIO_RE,
                   _CAM_MOTION_FR_RE, _SPEED_FR_RE, _HEIGHT_FR_RE, _DURATION_FR_RE,
                   _AUDIO_FR_RE)


def _drop_video_clause(clause: str) -> bool:
    """Cette proposition ne parle-t-elle QUE de vidéo ? (anglais ET français)"""
    c = (clause or "").strip()
    if not c:
        return False
    return any(rx.search(c) for rx in _VIDEO_ONLY_RES)


# Séparateurs de propositions, CAPTURÉS pour être restitués tels quels : un
# prompt qui utilise « — » ne doit pas ressortir avec des virgules.
_CLAUSE_SEP_RE = re.compile(r"(\s*[,;—–]\s*)")


def _filter_clauses(text: str, drop) -> tuple[str, list[str]]:
    """Applique `drop(proposition) -> bool` proposition par proposition.

    Découpe ligne → phrase → proposition pour ne JAMAIS supprimer une phrase
    entière à cause d'un seul mot : seule la proposition fautive tombe. Une phrase
    dont toutes les propositions tombent disparaît ; les lignes vides (séparateurs
    de blocs) sont conservées telles quelles, et la ponctuation d'origine aussi."""
    removed: list[str] = []
    out_lines: list[str] = []
    for line in (text or "").split("\n"):
        if not line.strip():
            out_lines.append(line)
            continue
        kept_sentences = []
        for sentence in re.split(r"(?<=[.!?])\s+", line):
            m = re.search(r"([.!?]+)\s*$", sentence)
            tail, body = (m.group(1), sentence[:m.start()]) if m else ("", sentence)
            tokens = _CLAUSE_SEP_RE.split(body)
            chunks = [("", tokens[0])]
            for i in range(1, len(tokens) - 1, 2):
                chunks.append((tokens[i], tokens[i + 1]))
            kept = []
            for sep, part in chunks:
                if part.strip() and drop(part):
                    removed.append(part.strip())
                else:
                    kept.append((sep, part))
            kept = [(s, p) for s, p in kept if p.strip()]
            if kept:
                rebuilt = kept[0][1] + "".join(s + p for s, p in kept[1:])
                kept_sentences.append(rebuilt.strip() + tail)
        if kept_sentences:
            out_lines.append(" ".join(kept_sentences))
    # Ne pas laisser de ligne vide en tête/queue après suppression.
    while out_lines and not out_lines[0].strip():
        out_lines.pop(0)
    while out_lines and not out_lines[-1].strip():
        out_lines.pop()
    return "\n".join(out_lines), removed


def strip_video_terms(text: str) -> tuple[str, list[str]]:
    """Retire d'un prompt IMAGE tout ce qui n'existe qu'en vidéo.

    Retourne (texte, propositions retirées) — la liste sert à l'affichage
    « ce qui a été retiré » et aux tests."""
    return _filter_clauses(text, _drop_video_clause)


# ── Interdits → formulations positives (moteurs sans négatif) ──────────────────

_NEGATIVE_CLAUSE_RE = re.compile(
    r"(?i)(?:^\s*(?:and\s+)?(?:absolutely\s+|strictly\s+|completely\s+)?"
    r"(?:no|not|never|without|avoid|avoiding|exclude|excluding|zero)\b"
    r"|\b(?:must not|should not|do not|don't|doesn't|shall not|no visible)\b)")

# Table de repli PAR MOT-CLÉ : chaque interdit courant a une contrepartie qui
# OCCUPE LA PLACE au lieu de l'interdire. Un interdit sans contrepartie utile est
# ABANDONNÉ — sur un moteur sans négatif, écrire « extra fingers » ferait
# apparaître des doigts en trop.
_POSITIVE_BY_KEYWORD = [
    (("text", "lettering", "label", "watermark", "caption", "annotation",
      "signage", "writing", "logo"),        "clean bare surfaces"),
    (("halo", "nimbus", "aureole"),          "bare head, plain background behind the head"),
    (("religious",),                          "plain everyday setting"),
    (("second person", "other person", "another person", "bystander"),
                                              "completely alone in the frame"),
    # « unpopulated » convient AUX DEUX cas : la nature morte d'un accessoire comme
    # le décor vide. « the subject alone in the frame » poussait un décor à faire
    # apparaître un sujet unique au milieu du paysage.
    (("person", "people", "human", "face", "model", "driver", "figure",
      "character", "mannequin", "hand"),      "unpopulated"),
    (("environment", "scene", "backdrop", "background detail", "setting",
      "room", "landscape", "sky", "road", "street", "ground", "floor",
      "furniture", "prop"),                   "a plain seamless studio backdrop"),
    (("shadow",),                             "even shadowless lighting"),
    (("crop", "cropping", "cut off"),         "the whole subject inside the frame"),
    (("border", "frame edge", "vignette"),    "an edge-to-edge image"),
    (("lens flare", "bloom", "glare"),        "clean optics"),
    (("stock", "polish", "cgi", "3d render"), "raw naturalistic rendering"),
    (("blur", "soft focus"),                  "crisp detail"),
    (("daylight", "sun", "sunlight"),         "night lighting only"),
    (("color", "colour", "saturation"),       "restrained natural colour"),
    # « Zero variation between views » porte une VRAIE consigne de planche
    # tournante : la perdre affaiblirait la fiche. On la garde, en positif.
    (("variation", "variance", "deviation"),  "every view strictly identical"),
    (("visible", "shown", "appear", "appears"), "kept out of frame"),
]


def _positive_for(clause: str) -> str:
    """Contrepartie positive d'une proposition négative, ou "" si elle doit être
    simplement abandonnée.

    ⚠ Comparaison au MOT, jamais en sous-chaîne : « ground » est contenu dans
    « background » — un `in` naïf transformait « NOT a white background » (consigne
    de décor) en « a plain seamless studio backdrop », soit l'inverse exact."""
    low = (clause or "").strip().lower().rstrip(".;:")
    direct = _POSITIVE_REWRITES.get(low)
    if direct:
        return direct
    for keys, positive in _POSITIVE_BY_KEYWORD:
        for k in keys:
            if re.search(r"(?<![a-z])" + re.escape(k) + r"(?![a-z])", low):
                return positive
    return ""


def neutralize_negatives(text: str) -> tuple[str, list[str]]:
    """Réécrit TOUTES les propositions négatives d'un texte en descriptions
    positives, pour un moteur qui ne sait pas interdire (Seedream 5, FLUX.2 JSON).

    Retourne (texte, positifs ajoutés). Les positifs sont regroupés à la fin —
    dédupliqués — pour ne pas hacher la description."""
    def _is_neg(clause: str) -> bool:
        return bool(_NEGATIVE_CLAUSE_RE.search((clause or "").strip()))

    positives: list[str] = []

    def _drop(clause: str) -> bool:
        if not _is_neg(clause):
            return False
        pos = _positive_for(clause)
        if pos and pos not in positives:
            positives.append(pos)
        return True

    body, _ = _filter_clauses(text, _drop)
    if positives:
        tail = ", ".join(positives)
        body = f"{body.rstrip().rstrip('.')}. {tail}." if body.strip() else tail + "."
    return body, positives


# ── Fond blanc obligatoire (casting, accessoires, HMC, véhicules) ──────────────
# Décision Matthieu 2026-07-25 : un personnage, un accessoire, un véhicule ou un
# élément HMC est une FICHE DE RÉFÉRENCE. Un décor derrière lui repartirait ensuite
# dans la génération vidéo comme s'il faisait partie du personnage, et polluerait
# le plan. Fond blanc TOUJOURS — portrait classique, éditorial, action, duo, sheet
# 5 vues, et même quand une image de référence impose un style pictural.
# (Les DÉCORS sont exclus : ce sont de vrais lieux.)

WHITE_BG_POSITIVE = (
    "Pure white seamless studio background: the subject is fully isolated on plain "
    "white, evenly lit, filling the frame"
)
WHITE_BG_CONSTRAINTS = [
    "no environment", "no scene", "no backdrop detail",
    "no ground shadow", "no props", "no set dressing",
]


def white_bg_directive(engine_key: str = "") -> str:
    """Consigne de fond blanc, formulée pour ce moteur.

    Sur un moteur qui sait interdire, on ajoute la liste d'exclusions (la doc dit
    qu'elle n'est pas optionnelle). Sur Seedream/FLUX.2, on n'écrit QUE le positif :
    « no environment » y ferait apparaître un environnement."""
    if supports_negatives(engine_key):
        return WHITE_BG_POSITIVE + ". " + ", ".join(WHITE_BG_CONSTRAINTS) + "."
    return WHITE_BG_POSITIVE + "."


def has_white_bg(text: str) -> bool:
    """Le texte impose-t-il déjà un fond blanc ? (évite le doublon)"""
    low = (text or "").lower()
    return ("white seamless" in low
            or ("white" in low and "background" in low and "seamless" in low)
            or "pure white background" in low
            or "white studio background" in low)


# ── Point d'entrée unique : adapter un prompt libre à un moteur ────────────────

def adapt_prompt(text: str, engine_key: str, *, drop_video: bool = True,
                 white_bg: bool = False) -> tuple[str, dict]:
    """Adapte un prompt image EXISTANT à la grammaire du moteur choisi.

    Ne restructure PAS la prose (contrairement à `build_image_prompt`, qui part
    d'une intention structurée) : c'est le chemin des générations d'éléments, dont
    les consignes sont écrites à la main et éprouvées. On y applique seulement ce
    qui dépend réellement du moteur ou du média :
      1. retrait des mots de qualité génériques (dégradent Seedream, interdits par
         la doctrine de prompt de PANDORA) ;
      2. retrait de ce qui n'existe qu'en vidéo (mouvement, hauteur, vitesse,
         durée, son) si `drop_video` ;
      3. fond blanc imposé si `white_bg` ;
      4. interdits convertis en positif si le moteur ne sait pas interdire.

    Retourne (prompt, rapport) — `rapport` liste ce qui a été retiré/ajouté, pour
    l'afficher et pour les tests."""
    report = {"boosters": [], "video": [], "positives": [], "white_bg": False,
              "grammar": grammar_for(engine_key)}
    out = text or ""

    out, boosters = strip_quality_boosters(out)
    report["boosters"] = boosters

    if drop_video:
        out, dropped = strip_video_terms(out)
        report["video"] = dropped

    if white_bg and not has_white_bg(out):
        sep = "\n\n" if "\n" in out.strip() else " "
        out = (out.rstrip() + sep + white_bg_directive(engine_key)).strip()
        report["white_bg"] = True

    if not supports_negatives(engine_key):
        out, positives = neutralize_negatives(out)
        report["positives"] = positives

    return _tidy(out), report


# ── Syntaxe des références multi-images ────────────────────────────────────────
# Cinq moteurs, cinq syntaxes NON interchangeables. C'est la première chose à
# encoder dans les adaptateurs (dossier fal.ai, §7).
_REF_SYNTAX = {
    "seedream5":       "figure",   # « Figure 1 », « Figure 2 » — positionnel
    "seedream5_pro":   "figure",
    "seedream5_lite":  "figure",
    "seedream45":      "figure",
    "seedream":        "figure",
    "flux2":           "at",       # « @image1 »
    "flux_2":          "at",
    "flux2_pro":       "at",
    "flux2_flex":      "at",
    "nb2":             "natural",  # « the attached wireframe », « the first image »
    "nb_pro":          "natural",
    "nb2_lite":        "natural",
    "nano_banana":     "natural",
    "nano_banana_pro": "natural",
    "gpt2":            "ordinal",  # « the first image », « the second image »
    "gpt_image_2":     "ordinal",
    "gpt-image-2":     "ordinal",
}

_ORDINALS = ["first", "second", "third", "fourth", "fifth",
             "sixth", "seventh", "eighth", "ninth", "tenth"]


def ref_token(engine_key: str, index: int) -> str:
    """Désignation TEXTUELLE de la n-ième image de référence (index 1-based) pour
    ce moteur. Chaîne vide si le moteur n'attend aucune mention textuelle."""
    if index < 1:
        return ""
    kind = _REF_SYNTAX.get((engine_key or "").strip().lower(), "")
    if kind == "figure":
        return f"Figure {index}"
    if kind == "at":
        return f"@image{index}"
    if kind == "ordinal":
        return f"the {_ORDINALS[index - 1]} image" if index <= len(_ORDINALS) else \
               f"image {index}"
    if kind == "natural":
        return f"the {_ORDINALS[index - 1]} attached image" if index <= len(_ORDINALS) \
               else f"attached image {index}"
    return ""


def ref_syntax_label(engine_key: str) -> str:
    """Libellé lisible de la syntaxe de référence (affichage UI)."""
    kind = _REF_SYNTAX.get((engine_key or "").strip().lower(), "")
    return {
        "figure":  "« Figure 1 », « Figure 2 » (positionnel)",
        "at":      "« @image1 », « @image2 »",
        "ordinal": "« the first image », « the second image »",
        "natural": "langage naturel (« the first attached image »)",
    }.get(kind, "aucune mention textuelle")


# ── Assemblage ─────────────────────────────────────────────────────────────────

_FIELD_ORDER = [
    ("subject",   "Subject"),
    ("action",    "Action"),
    ("setting",   "Setting"),
    ("style",     "Style"),
    ("camera",    "Composition and camera"),
    ("lighting",  "Lighting and color"),
    ("text",      "Text"),
]


def _tidy(text: str) -> str:
    """Ponctuation propre après retrait de morceaux (boosters, noms d'IP,
    termes vidéo, interdits).

    Deux pièges corrigés au branchement du module (2026-07-25) :
      - le groupe capturé doit être RESTITUÉ : la ligne portait un octet de
        contrôle (0x01) à la place de la référence arrière, si bien que la règle
        censée recoller « mot , » injectait un caractère invisible ;
      - ne travailler que sur espaces et tabulations : un \\s+ mange les sauts de
        ligne et recolle des blocs qui doivent rester séparés.
    """
    out = re.sub(r"\s*,\s*(,\s*)+", ", ", text or "")
    out = re.sub(r"[ \t]{2,}", " ", out)
    # Seulement « , » et « . » : en français l'espace AVANT « ; » « : » « ? » « ! »
    # est correcte, et le prompt affiché est lu par l'utilisateur — on ne recolle
    # pas sa ponctuation (« Arcane » : rendu peint » devenait « Arcane »: rendu »).
    out = re.sub(r"[ \t]+([,.])", r"\1", out)
    # Après suppression d'une proposition, une phrase peut commencer par une
    # virgule orpheline (« … real atmosphere., sharp focus ») : on recolle.
    out = re.sub(r"([.!?])[ \t]*[,;:]+[ \t]*", r"\1 ", out)
    out = re.sub(r"[,;:]+[ \t]*([.!?])", r"\1", out)
    out = re.sub(r"\.{2,}", ".", out)
    out = re.sub(r"(?m)^[ \t,;:]+", "", out)
    out = re.sub(r"(?m)[ \t,;:]+$", "", out)
    out = re.sub(r"\n{3,}", "\n\n", out)
    return out.strip()


def build_image_prompt(intent: dict, engine_key: str) -> str:
    """Assemble le prompt image dans la grammaire du moteur.

    `intent` : dict à clés subject / action / setting / style / camera / lighting /
    text / use_case / constraints (liste). Les clés absentes sont ignorées.
    L'ACTION doit décrire UN INSTANT figé — une image n'a pas de durée."""
    intent = dict(intent or {})
    g = grammar_for(engine_key)
    # Les mots de qualité génériques sont retirés de TOUTES les grammaires : ils
    # dégradent Seedream (ils distraient sa passe de raisonnement) et la doctrine
    # de prompt de PANDORA les interdit partout (ils poussent au rendu CGI).
    for _k in ("subject", "action", "setting", "style", "camera", "lighting"):
        if intent.get(_k):
            intent[_k] = strip_quality_boosters(str(intent[_k]))[0]
    use_case = (intent.get("use_case") or "").strip()
    cons = [c for c in (intent.get("constraints") or []) if str(c).strip()]

    if g == "natural":
        # 2-4 phrases, aucun négatif : les contraintes deviennent des descriptions
        # positives, et les mots de qualité sont retirés.
        # `style_first` : certains appelants (les Moods du Storyboard) placent
        # historiquement le style en TÊTE, et le rendu obtenu leur convient — on ne
        # déplace pas ce qui marche.
        _order = (("style", "subject", "action", "setting", "lighting", "camera")
                  if intent.get("style_first")
                  else ("subject", "action", "setting", "lighting", "camera", "style"))
        parts = [(intent.get(k) or "").strip() for k in _order]
        body = ". ".join(p.rstrip(" .") for p in parts if p)
        pos = to_positive(cons)
        if pos:
            body = f"{body}, {', '.join(pos)}" if body else ", ".join(pos)
        if use_case:
            body = f"{body}. {use_case}" if body else use_case
        body = _tidy(body)
        return (body + ".") if body and not body.endswith(".") else body

    if g == "json":
        import json as _json
        payload = {k: v for k, v in {
            "scene":    (intent.get("setting") or "").strip(),
            "subject":  (intent.get("subject") or "").strip(),
            "action":   (intent.get("action") or "").strip(),
            "style":    (intent.get("style") or "").strip(),
            "lighting": (intent.get("lighting") or "").strip(),
            "camera":   (intent.get("camera") or "").strip(),
            "mood":     use_case,
        }.items() if v}
        pal = intent.get("color_palette") or []
        if pal:
            # Les HEX ne sont lus que précédés de « hex » ou « color ».
            payload["color_palette"] = [f"hex {c}" if not str(c).lower().startswith("hex")
                                        else str(c) for c in pal]
        return _json.dumps(payload, ensure_ascii=False, indent=2)

    if g == "plain":
        # Prose descriptive — FLUX 1.x, Z-Image, Qwen, Ideogram, Recraft. Même
        # forme que « natural » (ces moteurs lisent une description suivie), mais
        # les interdits restent écrits en clair : ils les tolèrent, et c'est le
        # comportement historique du chemin Flux des Moods.
        # `style_first` : certains appelants (les Moods du Storyboard) placent
        # historiquement le style en TÊTE, et le rendu obtenu leur convient — on ne
        # déplace pas ce qui marche.
        _order = (("style", "subject", "action", "setting", "lighting", "camera")
                  if intent.get("style_first")
                  else ("subject", "action", "setting", "lighting", "camera", "style"))
        parts = [(intent.get(k) or "").strip() for k in _order]
        body = ". ".join(p.rstrip(" .") for p in parts if p)
        if cons:
            body = f"{body}. {', '.join(cons)}" if body else ", ".join(cons)
        if use_case:
            body = f"{body}. {use_case}" if body else use_case
        body = _tidy(body)
        return (body + ".") if body and not body.endswith(".") else body

    # fields : brief de directeur artistique à champs nommés, contraintes en bloc
    # final explicite (la doc fal dit que cette liste n'est pas optionnelle).
    lines = []
    if use_case:
        lines.append(use_case)
        lines.append("")
    for key, label in _FIELD_ORDER:
        v = _tidy((intent.get(key) or "").strip())
        if v:
            lines.append(f"{label}: {v}")
    if cons:
        if supports_negatives(engine_key):
            lines.append("Constraints: " + ", ".join(cons))
        else:
            pos = to_positive(cons)
            if pos:
                lines.append("Constraints: " + ", ".join(pos))
    return "\n".join(lines).strip()
