"""
api/live_extract.py — Workers Claude pour le Conducteur Live (équivalents adaptés
des workers Scénario de Cinéma, mais typés Live / Mapping).

  - FormatConducteurWorker   : mise en page de la trame (calibrée Live/Mapping)
  - ArrangeConducteurWorker  : proposition d'arrangement (réécriture améliorée)
  - ExtractLiveAssetsWorker  : extraction casting / accessoires / véhicules → live_assets

Tout passe par la clé Anthropic (config.json).
"""

from PyQt6.QtCore import QThread, pyqtSignal

from api.live_screenplay import _extract_json_array, _FACADE_FRAME_RULE

_MODEL = "claude-haiku-4-5"


def _mode_ctx(mode: str) -> str:
    if mode == "mapping":
        return ("Contexte : performance de MAPPING vidéo projeté sur la façade d'un "
                "bâtiment (façade verrouillée, caméra fixe, séquence continue). "
                "SEULE la façade de la photo de référence existe — aucune action "
                "reposant sur un élément non visible sur cette photo.")
    return ("Contexte : performance LIVE / VJ (visuels en boucle projetés en concert "
            "ou installation).")


# Plafonds de sortie par tâche (2026-07-26, parité Cinéma) : les 4096 en dur
# tronquaient un gros casting/inventaire SANS le dire — _extract_json_array
# récupère délibérément un tableau incomplet, donc la perte était invisible. Le
# Cinéma est à 16000 depuis le 2026-07-23 ; le coût ne dépend que de la sortie
# réelle, pas du plafond.
_MAX_TOKENS_BY_TASK = {
    "extraction": 16000,   # listes exhaustives — ne doit JAMAIS revenir tronquée
    "screenplay": 8192,    # arrangement conversationnel
}
_MAX_TOKENS_DEFAULT = 8192


def _claude(system: str, user: str, task: str | None = None,
            max_tokens: int | None = None) -> str:
    """Appel IA texte via la couche d'abstraction — voir core/ai_provider.
    `task` route vers le moteur adapté (Paramètres → moteur par tâche) ; tier
    créatif pour router comme les équivalents Cinéma (extraction → Sonnet…)."""
    from core.ai_provider import complete, key_error
    err = key_error(task)
    if err:
        raise RuntimeError(err)
    if max_tokens is None:
        max_tokens = _MAX_TOKENS_BY_TASK.get(task or "", _MAX_TOKENS_DEFAULT)
    return complete(system, user, tier="creative", max_tokens=max_tokens, task=task)


def validate_live_layout(text: str) -> list[str]:
    """Erreurs BLOQUANTES d'un découpage Live (2026-07-26).

    ⚠ Ne JAMAIS utiliser validate_v2_document / is_v2_document ici : le contrat v2 du
    Cinéma exige SOURCE SCÉNARIO / INTENTION / PROMPT VISUEL, que le Live ne produit
    pas — il refuserait 100 % des découpages Live. Le validateur juste est
    core.decoupage_layout.validate_layout, dont la branche non-v2 comprend le format
    Live (« === ACTE n === », « PLAN n — titre », « PROMPT VIDÉO »).

    On y AJOUTE la seule exigence propre au Live : un PROMPT SON par plan. Le sound
    design et le calage musical en dépendent. Cette règle vit ICI et pas dans core/ :
    le Cinéma n'exige pas de son par plan.

    ⚠ La DURÉE hors 2–15 s n'est PAS bloquante (correctif 2026-07-26, remonté par
    Matthieu sur un vrai découpage refusé). core.music_align.conform_durations_to_set
    la répare déjà, EN PLACE et avec ces mêmes bornes, au moment d'écrire les plans :
    refuser le document revenait à jeter un découpage que PANDORA sait corriger seul.
    Ce qui reste bloquant, c'est ce qu'aucun automatisme ne peut inventer : une
    structure illisible, un plan sans durée du tout, sans prompt vidéo ou sans son.

    Codes : structure_non_reconnue · aucun_plan · Pnn:duree · Pnn:prompt · Pnn:son
    """
    from core.decoupage_document import is_v2_document, validate_v2_document
    from core.decoupage_layout import is_structured_layout, parse_layout_segments
    value = text or ""
    # Contrat v2 (« DÉCOUPAGE PANDORA 2 ») depuis le 2026-07-26 : on applique le
    # contrat partagé — SOURCE / INTENTION / PROMPT VISUEL obligatoires — PUIS la
    # règle propre au Live, le SON. Les anciens découpages Live au format plat
    # restent acceptés tels quels par la branche suivante : rien à migrer.
    if is_v2_document(value):
        issues = [i for i in validate_v2_document(value) if not i.endswith(":durée")]
        segments = parse_layout_segments(value)
        for index, segment in enumerate(segments, 1):
            if not str(segment.get("sound_prompt") or "").strip():
                issues.append(f"P{index:02d}:son")
        return issues
    if not is_structured_layout(value):
        return ["structure_non_reconnue"]
    segments = parse_layout_segments(value)
    if not segments:
        return ["aucun_plan"]
    issues: list[str] = []
    for index, segment in enumerate(segments, 1):
        label = f"P{index:02d}"
        try:
            duration = float(segment.get("duration") or 0)
        except (TypeError, ValueError):
            duration = 0
        # Filet : le parseur met 5 s par défaut quand la ligne Durée est absente,
        # donc ce test ne mord pas aujourd'hui. Il est gardé pour le jour où le
        # parseur cesserait de combler — un plan sans durée n'est pas conformable.
        if duration <= 0:
            issues.append(f"{label}:duree")
        # PROMPT VIDÉO manquant : le parseur retombe silencieusement sur le TITRE du
        # plan. Un prompt égal au titre signifie donc « aucune ligne PROMPT VIDÉO » —
        # le plan partirait en génération avec trois mots au lieu d'une description.
        _prompt = str(segment.get("prompt") or "").strip()
        _title  = str(segment.get("action") or "").strip()
        if not _prompt or (_title and _prompt == _title):
            issues.append(f"{label}:prompt")
        if not str(segment.get("sound_prompt") or "").strip():
            issues.append(f"{label}:son")
    return issues


_ISSUE_LABELS = {
    "duree":  "durée absente",
    "prompt": "PROMPT VIDÉO vide",
    "son":    "PROMPT SON manquant",
}


def describe_layout_issues(issues: list) -> str:
    """Rend les codes de validate_live_layout lisibles pour l'utilisateur."""
    if not issues:
        return ""
    if "structure_non_reconnue" in issues:
        return ("la structure n'est pas reconnue — il faut des actes « === ACTE n === » "
                "et des plans « PLAN n — titre »")
    if "aucun_plan" in issues:
        return "aucun plan n'a pu être lu"
    parts = []
    for code in issues[:8]:
        plan, _, kind = str(code).partition(":")
        parts.append(f"{plan} : {_ISSUE_LABELS.get(kind, kind)}")
    if len(issues) > 8:
        parts.append(f"… et {len(issues) - 8} autre(s)")
    return " · ".join(parts)


def _fmt_err(e, task: str = "screenplay") -> str:
    """Erreur du fournisseur IA TEXTE réellement sélectionné pour CETTE tâche.
    Passait par l'humaniseur fal.ai (vidéo) jusqu'au 2026-07-26 : un compte IA
    texte à zéro envoyait l'utilisateur recharger fal.ai. Voir live_screenplay."""
    from api.live_screenplay import fmt_err
    return fmt_err(e, task)


# Suffixe de RELANCE CORRECTIVE (2026-07-26). Il rappelle le format LIVE — surtout
# pas le contrat « DÉCOUPAGE PANDORA 2 » du Cinéma, vers lequel on téléguiderait le
# moteur alors que le Live ne le produit pas.
_LAYOUT_CORRECTION = """

CORRECTION OBLIGATOIRE : ta réponse précédente ne respecte pas le contrat de fiches.
Recommence ENTIÈREMENT, sans commenter la correction :
- la PREMIÈRE ligne du document est exactement « DÉCOUPAGE PANDORA 2 » ;
- les actes sont des lignes « SÉQUENCE {n} — {titre} », les plans « PLAN 01 », « PLAN 02 »… ;
- CHAQUE plan porte TOUS les champs, dans cet ordre : SOURCE CONDUCTEUR, INTENTION,
  RYTHME, DURÉE, PROMPT VISUEL, SON, PERSONNAGES, ACCESSOIRES, VÉHICULES — et AUCUN
  autre : pas de VALEUR PROPOSÉE, pas de MOUVEMENT PROPOSÉ, pas de MOOD ;
- SOURCE CONDUCTEUR, INTENTION et PROMPT VISUEL ne sont JAMAIS vides ;
- DURÉE porte une durée chiffrée sur chaque plan (vise 2 à 15 s ; pour un set long,
  ajoute des plans plutôt que d'allonger un plan) ;
- PROMPT VISUEL est 100 % visuel, en beats relatifs (« ouverture : », « puis », « dans
  le dernier instant »), JAMAIS en timecodes absolus, sans BPM ni terme audio ;
- SON n'est jamais vide — c'est là, et là seulement, que le BPM et les temps forts
  interviennent.
Aucun plan ne doit être abrégé, résumé ou remplacé par « même structure ».
N'utilise PAS l'ancien format « === ACTE … === » / « PROMPT VIDÉO : »."""


# ── Mise en page ─────────────────────────────────────────────────────────────

class FormatConducteurWorker(QThread):
    """Mise en page PANDORA en STREAMING (signaux chunk/finished/failed) → alimente
    la fenêtre d'aperçu, comme l'arrangement."""
    finished = pyqtSignal(str)
    failed   = pyqtSignal(str)
    chunk    = pyqtSignal(str)
    retrying = pyqtSignal(str)   # (raison lisible) — relance corrective en cours

    def __init__(self, text: str, mode: str, duration_secs: int = 0, facade_path: str = "",
                 direction_note: str = ""):
        super().__init__()
        self._text   = text
        self._mode   = mode
        self._dur    = duration_secs
        self._facade = facade_path or ""   # image façade réelle (mapping) → Vision → texte
        self._direction_note = direction_note or ""   # Note de réalisation Live (parité Cinéma)

    def run(self):
        if not self._text.strip():
            self.failed.emit("La trame est vide.")
            return
        from core.ai_provider import stream as ai_stream, key_error
        # Mise en page du conducteur = équivalent Live de FormatPandoraWorker
        # (Cinéma) → tâche « decoupage », comme l'appel réel plus bas. Le garde-fou
        # vérifiait « screenplay » (2026-07-26) : sur un projet où le Découpage est
        # routé vers un autre fournisseur, la clé manquante passait le contrôle et
        # l'appel échouait plus loin avec une erreur brute.
        err = key_error("decoupage")
        if err:
            self.failed.emit(err)
            return
        try:
            _lock = ("Caméra FIXE, cadre verrouillé. La façade est un ÉCRAN, pas un sujet : "
                     "elle ne doit PAS rester visible en permanence. Alterne au fil des plans : "
                     "révélation (arêtes/fenêtres dessinées en lumière depuis le noir), "
                     "extinction (façade disparue, noir total), transformation (matière qui se "
                     "fissure/fond/se reconstruit), recouvrement total (un autre monde plein "
                     "cadre), jeu architectural (seules des parties s'illuminent). Chaque "
                     "PROMPT VIDÉO doit COMMENCER par l'état de la façade dans ce plan.\n"
                     + _FACADE_FRAME_RULE
                     if self._mode == "mapping" else "")
            # Langue de TRAVAIL (fr/en) : la mise en page reste dans la langue de
            # l'utilisateur — la traduction en anglais est faite au moment de l'ENVOI
            # aux moteurs (translate_to_english : api/real.py, video_engines.py, tts.py).
            # On garde donc PROMPT VIDÉO / PROMPT SON lisibles et éditables à la main.
            from core.i18n import get_lang
            _is_en   = (get_lang() == "en")
            _pl      = "anglais" if _is_en else "français"
            # Repères de qualité UTILES EN PROJECTION (2026-07-26). Les anciens
            # (« cinématographique, ultra-détaillé, 4K ») étaient une contradiction
            # en production : core/live_bar.BANNED_POSITIVES les bannit, la
            # grammaire mapping les efface et le contrôle de composition rejette
            # toute prose qui les contient. On faisait écrire ce qu'on allait
            # refuser. Ceux-ci décrivent ce qui tient VRAIMENT sur de la pierre :
            # du contraste, des arêtes franches, et du noir qui reste noir.
            _quality = ("high contrast, crisp edges, pure black background, no haze"
                        if _is_en
                        else "fort contraste, arêtes nettes, fond noir pur, sans brume")
            _beats   = ("'opening:', 'then', 'in the final moment'" if _is_en
                        else "« ouverture : », « puis », « dans le dernier instant »")
            system = (
                "Tu es superviseur de génération vidéo IA ET sound designer pour PANDORA | Live. "
                + _mode_ctx(self._mode) + " " + _lock +
                "À partir du CONDUCTEUR fourni (et de la TIMELINE MUSICALE éventuelle : BPM, "
                "drops, énergie), produis une MISE EN PAGE optimisée pour les MOTEURS de "
                "génération. La lisibilité humaine importe peu : le but est que les moteurs "
                "comprennent au mieux. Organise en ACTES (grandes sections du conducteur), "
                "chaque acte regroupant plusieurs PLANS numérotés. "
                "⭐ Les PROMPT VIDÉO doivent être RICHES et TRÈS DÉTAILLÉS : Seedance 2.0 "
                "donne de bien meilleurs résultats avec des descriptions visuelles denses. "
                "Ne résume PAS le conducteur en une ligne — DÉVELOPPE chaque plan.\n\n"
                "RÈGLE STRICTE — séparation vidéo / son : la TIMELINE MUSICALE (BPM, drops, "
                "énergie) ne sert QU'À deux choses : (1) fixer les DURÉES et le timing des "
                "plans, (2) nourrir le PROMPT SON. Le PROMPT VIDÉO est destiné à un moteur "
                "VIDÉO (Seedance) : il doit être 100 % VISUEL — INTERDIT d'y mettre le BPM, "
                "un tempo, des chiffres musicaux, des noms d'instruments ou tout terme audio.\n\n"
                "DURÉE PAR PLAN : entre 2 et 15 secondes — c'est la fenêtre des moteurs "
                "vidéo. Pour couvrir un set long, AJOUTE des plans plutôt que d'allonger "
                "un plan au-delà de 15 s (précision 2026-07-26 : la borne n'était écrite "
                "nulle part, le modèle produisait des plans de 20 à 40 s).\n\n"
                "ARITHMÉTIQUE OBLIGATOIRE — budget durée : la SOMME des durées de TOUS les "
                "plans doit ÉGALER la durée totale du set (±2 s). ADDITIONNE les durées "
                "avant de répondre ; s'il manque des secondes, RALLONGE des plans ou "
                "AJOUTE des plans — un set de 4:28 ne se couvre pas avec 3:55 de plans.\n\n"
                # ── Contrat « DÉCOUPAGE PANDORA 2 », porté du Cinéma le 2026-07-26 ──
                # Chaque plan devient une FICHE autonome : on sait d'où il vient dans le
                # conducteur (SOURCE), pourquoi il existe (INTENTION) et comment il
                # s'enchaîne (RYTHME). Champs propres au Live : SON (sound design +
                # calage musical) ; pas de DÉCOR ni HMC, qui n'existent pas ici.
                "FORMAT OBLIGATOIRE — respecte exactement ces libellés et cet ordre :\n\n"
                "DÉCOUPAGE PANDORA 2\n\n"
                "SÉQUENCE 1 — TITRE COURT DE L'ACTE\n\n"
                "PLAN 01\n"
                "SOURCE CONDUCTEUR : Extrait EXACT et autonome du conducteur couvert par ce "
                "plan. Aucune technique, aucun enrichissement visuel — c'est une citation.\n"
                "INTENTION : Fonction dramatique et visuelle du plan, en une ou deux phrases.\n"
                "RYTHME : Tempo, point de coupe, relation aux plans voisins et aux temps "
                "forts de la musique.\n"
                "DURÉE : 6s\n"
                "PROMPT VISUEL : prompt en " + _pl + ", TRÈS DÉTAILLÉ et dense — Seedance 2.0 "
                "exploite un MAXIMUM de détails, ne sois donc PAS bref. Décris précisément : "
                "SUJET + ACTION, environnement, COMPOSITION & cadrage, LUMIÈRE (direction, "
                "qualité, température), PALETTE, TEXTURES & matières, MOUVEMENT (ce qui bouge "
                "et comment), ATMOSPHÈRE, STYLE visuel, repères de QUALITÉ (" + _quality + "). "
                "Structure l'évolution en BEATS RELATIFS (" + _beats + ") — "
                "JAMAIS de timecode absolu, le moteur ne les respecte pas ; les impacts "
                "musicaux exacts vont sur les CUTS entre plans. 3 à 5 phrases riches, "
                "autonome, prêt tel quel ; AUCUN terme audio ni BPM.\n"
                "SON : prompt de sound design / SFX en " + _pl + " — ambiance, effets, textures "
                "et rythme du plan, prêt pour un générateur de SFX. AUCUNE parole ni voix. "
                "C'est ICI, et seulement ici, que le BPM et les drops interviennent.\n"
                "PERSONNAGES : Noms exacts séparés par des virgules, ou —\n"
                "ACCESSOIRES : Noms séparés par des virgules, ou —\n"
                "VÉHICULES : Noms séparés par des virgules, ou —\n\n"
                # VALEUR PROPOSÉE / MOUVEMENT PROPOSÉ / MOOD sont RETIRÉS du contrat
                # Live (demande Matthieu 2026-07-26) : hérités du Cinéma, ils n'ont pas
                # d'objet pour une boucle VJ ou un mapping à caméra verrouillée — le
                # modèle y rangeait d'ailleurs n'importe quoi (« VALEUR PROPOSÉE :
                # Traînée lumineuse ascendante »). Les libellés restent connus du
                # parseur partagé : un ancien découpage qui les porte reste lisible.
                "PLAN 02\n"
                "Répète ICI tous les champs de PLAN 01 avec le contenu réel du 2e plan.\n\n"
                "RÈGLES DE FORME :\n"
                "- La PREMIÈRE ligne du document est exactement « DÉCOUPAGE PANDORA 2 ».\n"
                "- Numérotation PLAN 01, PLAN 02… continue ; les actes sont des lignes "
                "« SÉQUENCE {n} — {titre} » séparées.\n"
                "- CHAQUE plan contient TOUS les champs. N'écris jamais « même structure », "
                "des points de suspension, ni un champ implicite.\n"
                "- SOURCE CONDUCTEUR est une citation fidèle, pas une réécriture enrichie ; "
                "INTENTION explique pourquoi le plan existe ; PROMPT VISUEL décrit l'image.\n"
                "- Retourne UNIQUEMENT le document, sans markdown ni commentaire."
            )
            # Mapping : injecte la description de la FAÇADE RÉELLE (Vision) pour que l'IA
            # respecte le bâtiment (fenêtres/portes réelles) au lieu d'en inventer.
            if self._mode == "mapping" and self._facade:
                try:
                    from core.live_building import describe_facade, facade_context_block
                    _fdesc = describe_facade(self._facade)
                    if _fdesc:
                        system = system + facade_context_block(_fdesc, "en" if _is_en else "fr")
                except Exception:
                    pass
            user = self._text
            if self._dur and self._dur > 0:
                mins, secs = divmod(int(self._dur), 60)
                dur_str = f"{mins}min {secs:02d}s" if mins else f"{secs}s"
                user = (f"[DURÉE CIBLE TOTALE : {dur_str} = {int(self._dur)} secondes. "
                        f"Dimensionne le NOMBRE et la durée des plans en conséquence.]\n\n"
                        + self._text)
            # Note de réalisation Live : intentions de fabrication injectées AVEC le
            # conducteur (même contrat que FormatPandoraWorker Cinéma via note_for_ai).
            if self._direction_note.strip():
                from core.direction_note import note_for_ai
                note = note_for_ai(self._direction_note)
                if note:
                    note_label = ("DIRECTOR'S NOTE" if _is_en else "NOTE DE RÉALISATION")
                    user += f"\n\n[{note_label} — INTENTIONS DE FABRICATION]\n{note}"
            # Tier créatif (Sonnet/Fable…) : prompts vidéo riches/détaillés pour
            # Seedance 2.0. 16000 tokens — un conducteur complet mis en page
            # dépassait 8000 (tronqué en réel le 2026-06-11) ; aligné sur Cinéma.
            # task="decoupage" : la Mise en page Live est le pivot créatif du flux
            # Live (les séquences en découlent) — même routage de tête que le
            # Découpage Cinéma (2026-07-23).
            # ⚠ ANTI-TRONCATURE (2026-07-25) : relever le plafond ne fait que
            # repousser le mur — il avait déjà été passé de 8000 à 16000 après une
            # coupe réelle le 2026-06-11, et le Découpage Cinéma s'est fait couper
            # à 16000 le 2026-07-25 (28 plans pour la moitié d'un scénario). On
            # DÉTECTE désormais la coupe et on demande la suite jusqu'au document
            # complet. Le texte arrive par blocs au lieu de mot à mot : chaque
            # reprise est un nouvel appel, mais rien n'est perdu.
            # VALIDATION + RELANCE CORRECTIVE (2026-07-26, parité Cinéma).
            # La fenêtre ne reçoit RIEN tant que le document n'est pas valide : un
            # premier jet raté s'affichait puis se faisait remplacer par l'erreur,
            # et l'utilisateur avait vu passer un découpage qui n'existait pas.
            full = self._layout_call(system, user)
            issues = validate_live_layout(full)
            if issues:
                self.retrying.emit(describe_layout_issues(issues))
                full = self._layout_call(system + _LAYOUT_CORRECTION, user)
                issues = validate_live_layout(full)
            if issues:
                raise ValueError(
                    "Le moteur IA n'a pas respecté le format de découpage Live, "
                    "même après une relance corrective (" +
                    describe_layout_issues(issues) + "). Rien n'a été enregistré : "
                    "un découpage incomplet est pire qu'aucun découpage.")
            self.chunk.emit(full)
            self.finished.emit(full)
        except Exception as e:
            self.failed.emit(_fmt_err(e, "decoupage"))

    def _layout_call(self, system: str, user: str) -> str:
        """Un appel de mise en page, coupe DÉTECTÉE et refusée. Isolé pour que la
        relance corrective rejoue exactement le même chemin."""
        from core.ai_provider import chat_until_complete_ex
        res = chat_until_complete_ex(system, [{"role": "user", "content": user}],
                                     tier="creative", max_tokens=16000,
                                     task="decoupage", max_rounds=6)
        if res.get("truncated"):
            raise ValueError(
                "La mise en page est INCOMPLÈTE : le moteur IA a atteint sa "
                "limite de longueur même après 6 reprises automatiques. Rien "
                "n'a été enregistré. Découpez le conducteur en parties, ou "
                "choisissez un moteur à plus grande sortie dans Paramètres › "
                "Moteur IA par tâche › Découpage.")
        return (res.get("text") or "").strip()


# ── Arrangement ──────────────────────────────────────────────────────────────

class ArrangeConducteurWorker(QThread):
    finished = pyqtSignal(str)
    failed   = pyqtSignal(str)

    def __init__(self, text: str, mode: str):
        super().__init__()
        self._text = text
        self._mode = mode

    def run(self):
        if not self._text.strip():
            self.failed.emit("La trame est vide.")
            return
        try:
            system = (
                "Tu es dramaturge pour une performance visuelle. " + _mode_ctx(self._mode) + " "
                "Propose une version AMÉLIORÉE et réarrangée de la trame : meilleure "
                "progression, montées et respirations, cohérence visuelle, temps forts "
                "bien placés. Garde le français et l'esprit de l'auteur. "
                "Réponds UNIQUEMENT avec la trame réarrangée."
            )
            # Arrangement = tâche « screenplay » (comme ArrangeScreenplayWorker Cinéma).
            self.finished.emit(_claude(system, self._text, task="screenplay").strip())
        except Exception as e:
            self.failed.emit(_fmt_err(e, "screenplay"))


# ── Extraction casting / accessoires / véhicules ─────────────────────────────

_KIND_LABEL = {
    "casting":     ("personnages / performers", "name, category (rôle/type), description (apparence, costume, style visuel)"),
    "accessoires": ("accessoires / objets",     "name, category, description (matière, couleur, état)"),
    "vehicules":   ("véhicules",                "name, category, description (marque, modèle, couleur, état)"),
}


def extract_live_assets(kind: str, text: str, mode: str) -> list:
    """Extraction calibrée LIVE (performers / objets de scène / véhicules) —
    lève une exception en cas d'erreur. Logique partagée worker + adaptateur."""
    label, fields = _KIND_LABEL.get(kind, _KIND_LABEL["casting"])
    system = (
        f"Tu es assistant de production pour PANDORA | Live. {_mode_ctx(mode)} "
        f"Identifie les {label} évoqués (ou pertinents) dans la trame fournie. "
        f"Pour chacun, fournis : {fields}. Textes en français. "
        "Réponds UNIQUEMENT avec un tableau JSON d'objets (aucun texte autour). "
        "Si aucun élément pertinent, renvoie []."
    )
    # Extraction JSON = tâche « extraction » (comme les extracteurs Cinéma).
    out = _claude(system, text, task="extraction")
    items = []
    for it in _extract_json_array(out):
        if isinstance(it, dict) and it.get("name"):
            items.append({
                "name":        str(it.get("name", "")).strip(),
                "category":    str(it.get("category", "")).strip(),
                "description": str(it.get("description", "")).strip(),
                "images":      [],
            })
    return items


def live_extract_worker_cls(kind: str, mode: str):
    """Fabrique une classe worker compatible ExtractGenerateDialog
    (ctor(text), signaux finished(list)/failed(str)) mais calibrée LIVE —
    remplace les extracteurs Cinéma (terminologie film) dans le Conducteur."""

    class _LiveExtractWorker(QThread):
        finished = pyqtSignal(list)
        failed   = pyqtSignal(str)

        def __init__(self, text: str):
            super().__init__()
            self._text = text

        def run(self):
            if not self._text.strip():
                self.failed.emit("La trame est vide.")
                return
            try:
                self.finished.emit(extract_live_assets(kind, self._text, mode))
            except Exception as e:
                self.failed.emit(_fmt_err(e, "extraction"))

    return _LiveExtractWorker


class ExtractLiveAssetsWorker(QThread):
    """Extrait les éléments d'un type depuis la trame → list[{name,category,description}]."""
    finished = pyqtSignal(str, list)   # (kind, items)
    failed   = pyqtSignal(str)

    def __init__(self, kind: str, text: str, mode: str):
        super().__init__()
        self._kind = kind
        self._text = text
        self._mode = mode

    def run(self):
        if not self._text.strip():
            self.failed.emit("La trame est vide.")
            return
        try:
            self.finished.emit(self._kind,
                               extract_live_assets(self._kind, self._text, self._mode))
        except Exception as e:
            self.failed.emit(_fmt_err(e, "extraction"))
