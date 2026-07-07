"""
api/live_screenplay.py — Génération du découpage Live/Mapping via Claude.

GenerateDecoupageWorker : transforme la trame du Conducteur en une liste de
segments, calibrée selon le mode :
  - "live"    → segments visuels d'une performance VJ (valeurs de plan, mouvement)
  - "mapping" → séquence CONTINUE sur une façade (caméra fixe, raccord, un seul plan long)

Sortie : list[dict] avec les clés action / shot_size / camera_movement / duration / prompt.
"""

import json
import re

from PyQt6.QtCore import QThread, pyqtSignal


def _decoupage_live_system(lang: str = "fr") -> str:
    """Système du découpage VJ Live. Les champs "prompt"/"sound_prompt" sont produits
    dans la LANGUE DE TRAVAIL (fr/en) — la traduction anglaise est faite à l'ENVOI aux
    moteurs (translate_to_english). Les amorces calibrées moteur suivent la même langue."""
    en    = (lang == "en")
    pl    = "ANGLAIS" if en else "FRANÇAIS"
    loop  = '"Seamless VJ loop, "' if en else "« Boucle VJ fluide, »"
    beats = ('"opening:", "then", "building up", "in the final moment"' if en
             else "« ouverture : », « puis », « montée », « dans le dernier instant »")
    absol = '"at 3 seconds"' if en else "« à 3 secondes »"
    qual  = ("cinematic, ultra-detailed, sharp, 4K" if en
             else "cinématographique, ultra-détaillé, net, 4K")
    return f"""\
Tu es un directeur artistique VJ. À partir du CONDUCTEUR fourni, produis le DÉCOUPAGE
d'une performance vidéo live (VJing), organisée en ACTES (grandes sections du
conducteur), chaque acte regroupant plusieurs PLANS / loops visuels.

Pour CHAQUE plan, donne un objet JSON avec :
- "act": numéro de l'acte auquel ce plan appartient (entier, commence à 1).
- "act_name": nom court de l'acte, en français (ex: "Intro", "Montée", "Drop", "Final").
- "action": description courte du visuel, en français (1 phrase).
- "shot_size": valeur de plan (ex: "Plan d'ensemble", "Plan large", "Plan moyen", "Gros plan", "Très gros plan") ou "".
- "camera_movement": mouvement (ex: "Fixe", "Panoramique", "Travelling", "Zoom avant", "Zoom arrière") ou "".
- "duration": durée en secondes (entier entre 4 et 15).
- "prompt": prompt VIDÉO en {pl} pour un loop VJ, TRÈS DÉTAILLÉ et dense (Seedance 2.0
  exploite un MAXIMUM de détails — ne sois PAS bref). Commence par {loop} puis
  décris précisément : sujet + action, décor/environnement, composition & cadrage, lumière
  (direction, qualité, température), palette de couleurs, textures & matières, mouvement
  (ce qui bouge et comment), atmosphère/mood, style visuel, repères de qualité ({qual}).
  STRUCTURE TEMPORELLE EN BEATS RELATIFS : décris l'évolution
  dans l'ordre avec {beats} — JAMAIS de
  timecode absolu ({absol}) : le moteur ne respecte pas les horodatages ; les impacts
  musicaux exacts sont gérés par les CUTS entre plans, pas à l'intérieur du clip.
  3 à 5 phrases riches. VISUEL UNIQUEMENT — INTERDIT d'y mettre
  le BPM, un tempo, des chiffres musicaux, des instruments ou tout terme audio.
- "sound_prompt": prompt SOUND DESIGN en {pl} (SFX / ambiance, AUCUNE voix ni parole).
  C'est ICI — et seulement ici — que le BPM et les temps forts sont pris en compte.

Réponds UNIQUEMENT avec un tableau JSON de plans (aucun texte autour).
"""

# Règle PARTAGÉE par tous les prompts IA du mode Mapping (découpage, mise en
# page, arrangement, application, co-écriture). Retour de test réel : l'IA
# demandait « le Père Noël entre par la cheminée » — or la cheminée n'est pas
# sur la façade mappée. L'amont (texte) doit être confiné comme l'aval (image).
_FACADE_FRAME_RULE = """\
- ZONE MAPPÉE — la seule chose qui existe est la façade telle qu'elle apparaît
  sur la photo de référence, en plan frontal. Tout élément VISIBLE sur cette
  photo est utilisable. N'écris JAMAIS d'action qui repose sur un élément NON
  VISIBLE sur la photo (architecture hors champ, côtés ou arrière du bâtiment,
  sol ou rue devant, ciel, alentours). Tout ce qui apparaît, entre ou sort passe
  par les BORDS du cadre ou par les éléments DE la façade (portes, fenêtres,
  corniches, arêtes). Si la trame évoque un élément non visible (ex. « il entre
  par la cheminée » alors qu'aucune cheminée n'apparaît sur la photo),
  TRANSPOSE l'action sur un élément visible (ex. une fenêtre s'illumine et il
  s'y engouffre) au lieu de la reprendre telle quelle.
- ANCRAGE ARCHITECTURAL — la projection se SUPERPOSE au vrai bâtiment : quand
  la façade ou l'un de ses éléments (fenêtres, portes, arêtes) est visible, il
  est EXACTEMENT à la position et à l'échelle de la photo de référence. JAMAIS
  de zoom, dézoom, rétrécissement, agrandissement ou glissement de la façade
  ENTIÈRE : si la nuit n'est pas parfaitement noire le soir du mapping, la
  fenêtre projetée se sépare de la vraie fenêtre et tout paraît raté. La façade
  peut disparaître, changer de matière ou être recouverte par un autre monde —
  mais dès que son architecture se montre, elle est à sa place exacte.
"""

def _decoupage_mapping_system(lang: str = "fr") -> str:
    """Système du découpage Mapping. Comme le Live : "prompt"/"sound_prompt" dans la
    LANGUE DE TRAVAIL (traduction anglaise à l'ENVOI aux moteurs). Amorces + exemples
    d'état de façade + glose de confinement suivent la même langue."""
    en    = (lang == "en")
    pl    = "ANGLAIS" if en else "FRANÇAIS"
    beats = ('"opening:", "then", "building up", "in the final moment"' if en
             else "« ouverture : », « puis », « montée », « dans le dernier instant »")
    absol = '"at 3 seconds"' if en else "« à 3 secondes »"
    qual  = ("cinematic, ultra-detailed, sharp, 4K" if en
             else "cinématographique, ultra-détaillé, net, 4K")
    states = ('(ex: "the facade is fully covered by…", "the facade dissolves into '
              'darkness while…", "only the window frames glow…", "the building '
              'reappears, rebuilt out of…")' if en else
              "(ex : « la façade est entièrement recouverte par… », « la façade se "
              "dissout dans le noir tandis que… », « seuls les encadrements de "
              "fenêtres s'illuminent… », « le bâtiment réapparaît, reconstruit en… »)")
    zone   = ("(only architecture actually visible in the reference facade image) — "
              "jamais d'élément supposé hors champ ; entries and exits happen through "
              "the frame edges or through the facade's own visible elements (doors, "
              "windows, edges)." if en else
              "(uniquement l'architecture réellement visible sur la photo de référence "
              "de la façade) — jamais d'élément supposé hors champ ; les entrées et "
              "sorties se font par les bords du cadre ou par les éléments visibles de "
              "la façade (portes, fenêtres, arêtes).")
    return f"""\
Tu es un concepteur de mapping vidéo (projection sur façade de bâtiment). À partir du
CONDUCTEUR fourni, produis le DÉCOUPAGE d'une séquence de mapping projetée sur une
façade VERROUILLÉE, organisée en ACTES (grandes sections), chaque acte regroupant
plusieurs PLANS qui s'enchaînent.

Contraintes IMPÉRATIVES :
- La caméra est TOTALEMENT FIXE (pas de mouvement, pas de zoom). camera_movement = "Fixe".
- La séquence est CONTINUE : chaque plan enchaîne le précédent comme un seul plan long.
- Le CADRE physique ne change jamais, mais la façade est un ÉCRAN / CANEVAS, pas un sujet :
  elle ne doit PAS rester visible en permanence. Un mapping qui montre la façade du début
  à la fin est un mapping raté (effet « image plaquée à 50 % d'opacité »). JOUE avec sa
  présence au fil des plans, en variant ces modes :
  * RÉVÉLATION — depuis le noir total, ses arêtes/fenêtres se dessinent en lignes de lumière ;
  * EXTINCTION — la façade disparaît entièrement dans le noir (fond noir pur) ;
  * TRANSFORMATION — elle se fissure, fond, se reconstruit, change de matière (eau, feu, métal…) ;
  * RECOUVREMENT — le contenu projeté la remplace totalement : un autre monde plein cadre ;
  * JEU ARCHITECTURAL — seules certaines parties s'illuminent (fenêtres, corniches, colonnes).
- Alterne ces modes d'un plan à l'autre pour créer des surprises et des respirations.
{_FACADE_FRAME_RULE}
Pour CHAQUE plan, donne un objet JSON avec :
- "act": numéro de l'acte auquel ce plan appartient (entier, commence à 1).
- "act_name": nom court de l'acte, en français (ex: "Apparition", "Transformation", "Apogée", "Final").
- "action": ce qui se passe sur la façade pendant ce plan, en français (1 phrase).
- "shot_size": "" (non pertinent en mapping).
- "camera_movement": "Fixe".
- "duration": durée en secondes (entier entre 4 et 15).
- "prompt": prompt VIDÉO en {pl} décrivant l'évolution projetée (sans mouvement de
  caméra), TRÈS DÉTAILLÉ et dense (Seedance 2.0 exploite un MAXIMUM de détails — ne sois PAS
  bref). COMMENCE par déclarer l'ÉTAT DE LA FAÇADE dans ce plan {states}. Puis décris
  précisément : l'effet/visuel projeté, la lumière (direction, qualité, couleur), la palette,
  les textures & matières, ce qui évolue et comment, l'atmosphère/mood, le style, et des
  repères de qualité ({qual}). STRUCTURE TEMPORELLE EN BEATS RELATIFS :
  décris l'évolution dans l'ordre avec {beats} — JAMAIS de timecode absolu ({absol}) : le
  moteur ne respecte pas les horodatages ; les impacts musicaux exacts sont gérés par les
  CUTS entre plans.
  3 à 5 phrases riches. VISUEL UNIQUEMENT —
  INTERDIT d'y mettre le BPM, un tempo, des chiffres musicaux, des instruments ou tout
  terme audio. RESTE DANS LA ZONE : le prompt ne s'appuie QUE sur l'architecture
  réellement VISIBLE sur la photo de référence de la façade {zone}
- "sound_prompt": prompt SOUND DESIGN en {pl} (SFX / ambiance, AUCUNE voix ni parole).
  C'est ICI — et seulement ici — que le BPM et les temps forts sont pris en compte.

Réponds UNIQUEMENT avec un tableau JSON de plans (aucun texte autour).
"""


# Constantes = version LANGUE DE TRAVAIL PAR DÉFAUT (fr). Le worker reconstruit selon
# get_lang() à l'exécution ; ces constantes restent la référence (imports, tests).
_SYSTEM_LIVE    = _decoupage_live_system("fr")
_SYSTEM_MAPPING = _decoupage_mapping_system("fr")


def _extract_json_array(text: str) -> list:
    """Extrait un tableau JSON d'objets depuis la réponse Claude, de façon ROBUSTE :
    - tolère le texte autour et les blocs ```json (capture GREEDY de tout le tableau) ;
    - récupère les objets complets même si le tableau est TRONQUÉ (max_tokens atteint)
      ou contient des virgules finales / caractères parasites."""
    if not text:
        return []
    # 1) bloc ```json … ``` — greedy pour capturer le tableau ENTIER
    m = re.search(r"```(?:json)?\s*(\[[\s\S]*\])\s*```", text)
    if m:
        raw = m.group(1)
    else:
        start = text.find("[")
        end   = text.rfind("]")
        raw = text[start:end + 1] if (start != -1 and end > start) else text

    # 2) tentative directe
    try:
        data = json.loads(raw)
        if isinstance(data, list):
            return [d for d in data if isinstance(d, dict)]
    except Exception:
        pass

    # 3) récupération objet par objet (tableau tronqué / parasites)
    objs: list = []
    decoder = json.JSONDecoder()
    idx = raw.find("{")
    while idx != -1:
        try:
            obj, end = decoder.raw_decode(raw, idx)
        except json.JSONDecodeError:
            nxt = raw.find("{", idx + 1)
            if nxt == -1:
                break
            idx = nxt
            continue
        if isinstance(obj, dict):
            objs.append(obj)
        idx = raw.find("{", end)
    return objs


def _normalize(seg: dict, mode: str) -> dict:
    try:
        dur = int(seg.get("duration", 5))
    except (TypeError, ValueError):
        dur = 5
    dur = max(4, min(15, dur))
    mv = seg.get("camera_movement", "") or ("Fixe" if mode == "mapping" else "")
    try:
        act = int(seg.get("act", 1))
    except (TypeError, ValueError):
        act = 1
    from core.prompt_sections import video_with_sound
    _video = str(seg.get("prompt", "")).strip()
    _sound = str(seg.get("sound_prompt", "")).strip()
    return {
        "action":          str(seg.get("action", "")).strip(),
        "shot_size":       "" if mode == "mapping" else str(seg.get("shot_size", "")).strip(),
        "camera_movement": "Fixe" if mode == "mapping" else str(mv).strip(),
        "duration":        dur,
        "prompt":          _video,
        "sound_prompt":    _sound,
        # UN seul prompt à SECTIONS (comme Cinéma) : vidéo + [🎵 SOUND DESIGN]. Le son
        # reste extrait par sound_of() (Sound Design) et retiré par video_of() (moteur
        # vidéo). `prompt`/`sound_prompt` restent fournis en repli (rétro-compat).
        "seedance_prompt": video_with_sound(_video, _sound),
        "act":             max(1, act),
        "act_name":        str(seg.get("act_name", "")).strip(),
        "image_path":      "",
    }


class GenerateDecoupageWorker(QThread):
    finished = pyqtSignal(list)   # list[dict] de segments
    failed   = pyqtSignal(str)

    def __init__(self, text: str, mode: str):
        super().__init__()
        self._text = text
        self._mode = mode if mode in ("live", "mapping") else "live"

    def run(self):
        text = (self._text or "").strip()
        if not text:
            self.failed.emit("La trame est vide — écrivez votre conducteur d'abord.")
            return
        try:
            from core.ai_provider import complete, key_error, ai_name_for_task
            # Découpage du conducteur = équivalent Live de la génération du
            # storyboard Cinéma → même tâche « storyboard_gen » (routage/défauts).
            err = key_error("storyboard_gen")
            if err:
                self.failed.emit(err)
                return
            # Découpage produit dans la LANGUE DE TRAVAIL (fr/en) — traduction anglaise
            # faite à l'ENVOI aux moteurs (translate_to_english), pas ici, pour rester
            # lisible et éditable dans le tableau Séquences.
            from core.i18n import get_lang
            _lang  = get_lang()
            system = (_decoupage_mapping_system(_lang) if self._mode == "mapping"
                      else _decoupage_live_system(_lang))
            # 16000 : un découpage dense (beaucoup de plans × prompts détaillés)
            # atteignait le plafond de 8000 → JSON tronqué
            out = complete(system, text, tier="creative", max_tokens=16000,
                           task="storyboard_gen")
            segments = [_normalize(s, self._mode) for s in _extract_json_array(out) if isinstance(s, dict)]
            if not segments:
                snippet = (out or "").strip()[:200].replace("\n", " ")
                self.failed.emit(
                    f"Découpage vide — réponse {ai_name_for_task('storyboard_gen')} "
                    f"non exploitable. Réessayez.\n\n"
                    f"Début de la réponse : {snippet}")
                return
            self.finished.emit(segments)
        except Exception as e:
            from core.worker import humanize_api_error
            self.failed.emit(humanize_api_error(str(e)))


# ── Arrangement (streaming, pour la fenêtre de co-écriture) ───────────────────

_ARRANGE_LIVE = """\
Tu es directeur artistique VJ et dramaturge de performance live. On te fournit un
CONDUCTEUR (déroulé d'une performance vidéo live / VJing).

IMPORTANT — c'est un CONDUCTEUR de performance live, PAS un scénario de film.
N'emploie JAMAIS de vocabulaire scénaristique : INTERDIT « INT. » / « EXT. »,
« intérieur » / « extérieur », en-têtes de scène, numéros de scène, « séquence »,
« scène », « plateau », « décor ». Raisonne en ACTES (grandes sections du conducteur)
et en PLANS / loops visuels.

Analyse-le et propose un ARRANGEMENT :
- découpage en ACTES (intro, montées, climax, breakdowns, drops, final) et progression d'intensité ;
- cohérence visuelle, variations de styles/ambiances par acte ;
- placement des temps forts, respirations et transitions entre actes.

Donne d'abord une ANALYSE claire, puis des SUGGESTIONS concrètes et actionnables (numérotées).
Ne réécris pas tout le conducteur — tu PROPOSES. Réponds en français.
"""

_ARRANGE_MAPPING = """\
Tu es concepteur de mapping vidéo (projection sur la façade d'un bâtiment). On te fournit
un CONDUCTEUR de mapping (façade VERROUILLÉE, caméra fixe, continuité).

IMPORTANT — c'est un CONDUCTEUR de mapping, PAS un scénario de film.
N'emploie JAMAIS de vocabulaire scénaristique : INTERDIT « INT. » / « EXT. »,
« intérieur » / « extérieur », en-têtes de scène, numéros de scène, « séquence »,
« scène ». Raisonne en ACTES (grandes sections) et en PLANS projetés sur la façade.

Analyse-le et propose un ARRANGEMENT :
- découpage en ACTES (apparition/reveal, transformations, apogée, final) et progression continue ;
- dramaturgie de la PRÉSENCE de la façade : elle ne doit pas rester visible en permanence —
  alterne révélations (arêtes qui se dessinent), extinctions (noir total), transformations
  (matière qui change), recouvrements (le contenu projeté la remplace) et jeux architecturaux
  (seules des parties s'illuminent) ;
- placement des moments forts et transitions SANS coupe entre actes.
""" + _FACADE_FRAME_RULE + """\

Donne d'abord une ANALYSE claire, puis des SUGGESTIONS concrètes et numérotées.
Ne réécris pas tout le conducteur — tu PROPOSES. Réponds en français.
"""


_APPLY_ARRANGE_CONDUCTEUR = """\
Tu reçois un CONDUCTEUR de performance visuelle (live VJ ou mapping) et des
SUGGESTIONS d'arrangement. Réécris le conducteur en appliquant ces suggestions.

IMPORTANT — c'est un CONDUCTEUR, PAS un scénario de film. INTERDIT : « INT. » /
« EXT. », en-têtes de scène, numéros de scène, « séquence », « scène », mise en
page scénario. Garde la FORME du conducteur original (déroulé en actes / moments),
le français et la voix de l'auteur. N'invente aucun élément non demandé.
Pour un conducteur de MAPPING : toute action reste STRICTEMENT sur la façade
mappée (la photo de référence, plan frontal) — jamais d'action reposant sur un
élément non visible sur cette photo ; si une suggestion l'exige, transpose
l'action sur un élément visible de la façade (portes, fenêtres, arêtes, bords
du cadre).

Réponds UNIQUEMENT avec le conducteur réécrit (aucun commentaire autour).
"""


class ApplyArrangeConducteurWorker(QThread):
    """Applique les suggestions d'arrangement au CONDUCTEUR (streaming).
    Remplace ApplyArrangeWorker (Cinéma) qui réécrivait au format scénario."""
    finished = pyqtSignal(str)
    failed   = pyqtSignal(str)
    chunk    = pyqtSignal(str)

    def __init__(self, original: str, suggestions: str, intensity: int = 5,
                 refs_analysis: str = ""):
        super().__init__()
        self._original    = original
        self._suggestions = suggestions
        self._intensity   = max(1, min(10, intensity))
        self._refs        = refs_analysis or ""

    def run(self):
        from core.ai_provider import stream, key_error
        # Même tâche que l'application d'arrangement Cinéma (ApplyArrangeWorker).
        err = key_error("screenplay")
        if err:
            self.failed.emit(err)
            return
        try:
            user = (
                f"[INTENSITÉ D'APPLICATION : {self._intensity}/10 — "
                f"{'modifications légères' if self._intensity <= 3 else 'modifications équilibrées' if self._intensity <= 6 else 'refonte assumée'}]\n\n"
                f"CONDUCTEUR ORIGINAL :\n{self._original}\n\n"
                f"SUGGESTIONS D'ARRANGEMENT :\n{self._suggestions}"
            )
            if self._refs.strip():
                user += ("\n\n[DIRECTION ARTISTIQUE — issue de l'analyse des images "
                         "de référence. Inspiration à transposer, jamais à copier : "
                         "ancre les ambiances, matières et lumières du conducteur "
                         "réécrit dans cette direction.]\n" + self._refs.strip())
            # 16000 : sortie = conducteur COMPLET réécrit — 8192 tronquait les longs
            full = stream(_APPLY_ARRANGE_CONDUCTEUR, user, on_chunk=self.chunk.emit,
                          tier="creative", max_tokens=16000, task="screenplay")
            self.finished.emit(full.strip())
        except Exception as e:
            from core.worker import humanize_api_error
            self.failed.emit(humanize_api_error(str(e)))


_ARRANGE_CHAT = (
    "Tu es CO-AUTEUR d'un conducteur de {ctx}. Tu viens de proposer des "
    "SUGGESTIONS d'arrangement ; l'utilisateur (le réalisateur) en discute avec "
    "toi pour les affiner AVANT de les appliquer.\n"
    "Règles :\n"
    "• Réponds en français, concret et bref — on est en séance de travail ;\n"
    "• Quand une suggestion évolue suite à la discussion, reformule-la "
    "clairement et complètement (préfixe « SUGGESTION RÉVISÉE — ») : c'est elle "
    "qui sera appliquée ;\n"
    "• Si une direction artistique (références) est fournie, appuie-toi dessus "
    "— inspiration à transposer, jamais à copier ;\n"
    "• INTERDIT : vocabulaire scénario (INT./EXT., scènes, séquences) — on "
    "raisonne en ACTES et en PLANS ;\n"
    "• Reste sur l'arrangement du conducteur : structure, rythme, dramaturgie."
)


class ArrangeChatConducteurWorker(QThread):
    """Un tour de CO-ÉCRITURE sur l'arrangement (streaming) — fenêtre Arrangement.
    messages = historique [{role, content}], dernier = message du réalisateur.
    Signaux : chunk/done/failed."""
    done   = pyqtSignal(str)
    failed = pyqtSignal(str)
    chunk  = pyqtSignal(str)

    def __init__(self, messages: list, conducteur: str, suggestions: str,
                 mode: str = "live", refs_analysis: str = ""):
        super().__init__()
        self._messages    = list(messages or [])
        self._conducteur  = conducteur or ""
        self._suggestions = suggestions or ""
        self._mode        = mode if mode in ("live", "mapping") else "live"
        self._refs        = refs_analysis or ""

    def run(self):
        from core.ai_provider import chat_stream, key_error
        # Même tâche que la co-écriture d'arrangement Cinéma (ArrangeChatWorker).
        err = key_error("screenplay")
        if err:
            self.failed.emit(err)
            return
        if not self._messages:
            self.failed.emit("Aucun message à envoyer.")
            return
        try:
            ctx = ("performance de MAPPING vidéo projetée sur une façade (nuit, "
                   "façade = écran ; SEULE la façade de la photo de référence "
                   "existe — jamais d'action reposant sur un élément non visible "
                   "sur cette photo : transpose sur la façade)"
                   if self._mode == "mapping"
                   else "performance LIVE / VJ (loops visuels projetés)")
            doc = (f"CONDUCTEUR ACTUEL :\n{self._conducteur}\n\n"
                   f"SUGGESTIONS D'ARRANGEMENT PROPOSÉES :\n{self._suggestions}")
            if self._refs.strip():
                doc += f"\n\nDIRECTION ARTISTIQUE (références) :\n{self._refs.strip()}"
            messages = [dict(m) for m in self._messages]
            first = messages[0]
            messages[0] = {"role": first["role"],
                           "content": f"{doc}\n\n---\n\n{first['content']}"}
            full = chat_stream(_ARRANGE_CHAT.format(ctx=ctx), messages,
                               on_chunk=self.chunk.emit,
                               tier="creative", max_tokens=8192, task="screenplay")
            self.done.emit(full.strip())
        except Exception as e:
            from core.worker import humanize_api_error
            self.failed.emit(humanize_api_error(str(e)))


class ArrangeConducteurStreamWorker(QThread):
    """Arrangement du conducteur en STREAMING (même interface que le worker Cinéma :
    signaux chunk/finished/failed) → alimente la fenêtre de co-écriture. Calibré Live/Mapping."""
    finished = pyqtSignal(str)
    failed   = pyqtSignal(str)
    chunk    = pyqtSignal(str)

    def __init__(self, text: str, mode: str, duration_secs: int = 0,
                 refs_analysis: str = ""):
        super().__init__()
        self._text = text
        self._mode = mode if mode in ("live", "mapping") else "live"
        self._dur  = duration_secs
        self._refs = refs_analysis or ""

    def run(self):
        from core.ai_provider import stream, key_error
        # Même tâche que l'arrangement Cinéma (ArrangeScreenplayWorker).
        err = key_error("screenplay")
        if err:
            self.failed.emit(err)
            return
        try:
            system = _ARRANGE_MAPPING if self._mode == "mapping" else _ARRANGE_LIVE
            prefix = ""
            if self._dur > 0:
                mins, secs = divmod(self._dur, 60)
                dur_str = f"{mins}min {secs:02d}s" if mins else f"{secs}s"
                prefix = (f"[DURÉE CIBLE : {dur_str} = {self._dur} secondes. "
                          f"Tiens-en compte dans le rythme et la structure.]\n\n")
            if self._refs.strip():
                prefix += ("[DIRECTION ARTISTIQUE — issue de l'analyse des images de "
                           "référence. C'est une inspiration à transposer, jamais à "
                           "copier : appuie tes suggestions dessus quand c'est "
                           "pertinent.]\n" + self._refs.strip() + "\n\n")
            full = stream(system, prefix + self._text, on_chunk=self.chunk.emit,
                          tier="creative", max_tokens=8192, task="screenplay")
            self.finished.emit(full)
        except Exception as e:
            from core.worker import humanize_api_error
            self.failed.emit(humanize_api_error(str(e)))


# ── Studio de co-écriture — session interactive (fenêtre dédiée) ──────────────
# Équivalent Live de ArrangeChatWorker (api/screenplay.py) : même protocole à
# MARQUEURS (MESSAGE / document réécrit), calibré CONDUCTEUR live/mapping —
# jamais de format scénario cinéma (INT./EXT., dialogues screenplay).

# Vision (images jointes) : appel DIRECT Anthropic — hors couche ai_provider
# (aligné sur api/screenplay.py : les autres fournisseurs gèrent la vision
# différemment ; périmètre v1 = texte). Réflexion désactivée pour ne pas
# rogner la sortie.
_VISION_MODEL    = "claude-sonnet-5"
_VISION_NO_THINK = {"type": "disabled"}

# Confinement façade pour la co-écriture d'un conducteur de MAPPING — critère
# de VISIBILITÉ sur la photo de référence (jamais de liste noire d'éléments),
# même règle que _APPLY_ARRANGE_CONDUCTEUR.
_SESSION_FACADE_RULE = (
    "CONDUCTEUR DE MAPPING : toute action reste STRICTEMENT sur la façade "
    "mappée (la photo de référence, plan frontal) — jamais d'action reposant "
    "sur un élément non visible sur cette photo ; si une demande l'exige, "
    "transpose l'action sur un élément visible de la façade (portes, "
    "fenêtres, arêtes, bords du cadre).\n\n"
)


def _arrange_session_chat_system(intensity: int, mode: str) -> str:
    """Prompt système de la co-écriture interactive du CONDUCTEUR.

    Adapté de api/screenplay.py → _arrange_chat_system (Cinéma) : mêmes
    paliers d'intensité et même format de réponse à marqueurs, mais l'IA
    co-écrit un CONDUCTEUR de performance live/mapping (actes, tableaux,
    ambiances, musiques/BPM) — jamais un scénario de film."""
    intensity = max(1, min(10, intensity))
    if intensity <= 2:
        rule = (
            f"━━━ INTENSITÉ MINIMALE ({intensity}/10) — MODIFICATION CHIRURGICALE STRICTE ━━━\n"
            "Modifie UNIQUEMENT ce que le réalisateur demande, mot pour mot.\n"
            "Si la demande cible un plan ou un moment, seul ce passage change — rien avant, rien après.\n"
            "Tout le reste est copié CARACTÈRE PAR CARACTÈRE depuis la version précédente.\n"
            "Aucune amélioration, aucune correction, aucune retouche hors de la zone ciblée."
        )
    elif intensity <= 4:
        rule = (
            f"━━━ INTENSITÉ PRÉCISE ({intensity}/10) — CHIRURGIE CIBLÉE ━━━\n"
            "Tu ne modifies QUE ce que le réalisateur demande EXPLICITEMENT.\n"
            "Tout le reste du conducteur est copié MOT POUR MOT — sans reformulation, sans retouche.\n"
            "Tu peux uniquement harmoniser la ponctuation dans la phrase ciblée pour la cohérence."
        )
    elif intensity <= 6:
        rule = (
            f"━━━ INTENSITÉ CIBLÉE ({intensity}/10) — MODIFICATION PRÉCISE ━━━\n"
            "Tu modifies les zones que le réalisateur demande. Tout le reste est conservé.\n"
            "Tu peux légèrement affiner le style dans la zone ciblée pour assurer la cohérence de ton.\n"
            "Ne retouche pas les passages non mentionnés, même si tu penses pouvoir les améliorer."
        )
    elif intensity <= 8:
        rule = (
            f"━━━ INTENSITÉ CRÉATIVE ({intensity}/10) — RÉÉCRITURE DES ZONES CIBLÉES ━━━\n"
            "Tu modifies les zones demandées avec liberté créative : reformule, enrichis, améliore le rythme.\n"
            "Tu peux retoucher les passages adjacents pour assurer la fluidité dramatique.\n"
            "Les zones non mentionnées sont conservées, avec d'éventuelles harmonisations stylistiques légères."
        )
    else:
        rule = (
            f"━━━ INTENSITÉ LIBRE ({intensity}/10) — CO-ÉCRITURE COMPLÈTE ━━━\n"
            "Tu réécris dans l'esprit des instructions du réalisateur, avec pleine liberté créative.\n"
            "Tu peux transformer le style, le rythme, les ambiances et la structure dans l'ensemble du conducteur.\n"
            "Respecte scrupuleusement ce que le réalisateur demande de conserver explicitement."
        )
    ctx = ("performance de MAPPING vidéo projetée sur la façade d'un bâtiment "
           "(façade verrouillée, caméra fixe, continuité)"
           if mode == "mapping"
           else "performance LIVE / VJ (loops visuels projetés)")
    facade = _SESSION_FACADE_RULE if mode == "mapping" else ""
    return (
        "Tu es un co-auteur travaillant dans Pandora, un outil de création de "
        "performances visuelles live. Tu dialogues avec le réalisateur pour "
        f"affiner le CONDUCTEUR de sa {ctx}.\n\n"
        f"{rule}\n\n"
        "IMPORTANT — c'est un CONDUCTEUR de performance, PAS un scénario de film. "
        "N'introduis JAMAIS de format ni de vocabulaire scénario : INTERDIT "
        "« INT. » / « EXT. », en-têtes de scène, numéros de scène, « séquence », "
        "« scène », dialogues au format screenplay (noms de personnages en "
        "MAJUSCULES avant des répliques). Tu CONSERVES la STRUCTURE du conducteur "
        "original (déroulé en actes / moments / tableaux, ambiances, musiques/BPM) "
        "et la voix de l'auteur. Raisonne en ACTES et en PLANS / loops visuels.\n\n"
        f"{facade}"
        "RÉFÉRENCES VISUELLES : Si des images sont jointes, intègre leurs détails visuels "
        "UNIQUEMENT dans les parties que le réalisateur demande de modifier. Si une "
        "DIRECTION ARTISTIQUE (analyse de références) est fournie, appuie-toi dessus — "
        "inspiration à transposer, jamais à copier.\n\n"
        "FORMAT DE RÉPONSE OBLIGATOIRE :\n"
        "Ta réponse doit contenir EXACTEMENT deux parties séparées par ces marqueurs :\n\n"
        "══════════ MESSAGE ══════════\n"
        "[Message conversationnel : indique précisément CE QUE TU AS CHANGÉ et où — "
        "2 à 4 lignes max, ton direct et collaboratif. Si la portée est ambiguë, pose une question.]\n"
        "══════════ CONDUCTEUR ══════════\n"
        "[Le conducteur complet réécrit, dans la MÊME forme que l'original.]\n\n"
        "RÈGLES :\n"
        "- « Ne touche pas X » ou « garde X intact » → X est copié mot pour mot, sans exception\n"
        "- « Développe Y » → ajoute du contenu cohérent UNIQUEMENT dans Y\n"
        "- « Coupe Z » → supprime Z proprement, le reste est intact\n"
        "- Les noms d'actes et de moments restent IDENTIQUES sauf demande contraire\n"
        "- N'invente rien qui ne soit pas dans l'original ou explicitement demandé"
    )


class ArrangeSessionChatConducteurWorker(QThread):
    """Co-écriture interactive du CONDUCTEUR avec l'IA — fenêtre Studio de
    co-écriture (ui/dialog_arrange_session_live.py).

    Équivalent Live de ArrangeChatWorker (api/screenplay.py) : même protocole
    à marqueurs, calibré conducteur live/mapping.

    Signaux :
        message_ready(str)    — réponse conversationnelle (à afficher dans le chat)
        screenplay_ready(str) — conducteur remanié complet (prévisualisation)
        failed(str)           — message d'erreur
    """
    message_ready    = pyqtSignal(str)
    screenplay_ready = pyqtSignal(str)
    failed           = pyqtSignal(str)

    _MARKER_MSG = "══════════ MESSAGE ══════════"
    _MARKER_DOC = "══════════ CONDUCTEUR ══════════"

    def __init__(
        self,
        original: str,
        analysis: str,
        history: list,
        user_message: str,
        intensity: int = 5,
        ref_images: list | None = None,
        mode: str = "live",
        refs_analysis: str = "",
    ):
        super().__init__()
        self._original     = original or ""       # le CONDUCTEUR complet
        self._analysis     = analysis or ""
        self._history      = list(history or [])  # [{"role": "user"/"assistant", "content": str}]
        self._user_message = user_message
        self._intensity    = intensity
        self._ref_images   = ref_images or []
        self._mode         = mode if mode in ("live", "mapping") else "live"
        self._refs         = refs_analysis or ""

    def run(self):
        try:
            from core.ai_provider import chat as ai_chat, key_error
            # Même tâche que la co-écriture Cinéma (ArrangeChatWorker → screenplay).
            err = key_error("screenplay")
            if err:
                self.failed.emit(err)
                return

            context_block = (
                f"CONDUCTEUR ORIGINAL :\n{self._original}\n\n"
                f"ANALYSE INITIALE (intensité {self._intensity}/10) :\n{self._analysis}"
            )
            if self._refs.strip():
                context_block += (
                    "\n\n[DIRECTION ARTISTIQUE — issue de l'analyse des images "
                    "de référence. Inspiration à transposer, jamais à copier : "
                    "ancre les ambiances, matières et lumières du conducteur "
                    "dans cette direction.]\n" + self._refs.strip()
                )

            # Construction des messages : contexte injecté dans le 1er message user
            messages = []
            for i, msg in enumerate(self._history):
                if i == 0 and msg["role"] == "user":
                    messages.append({
                        "role": "user",
                        "content": context_block + "\n\n" + msg["content"],
                    })
                else:
                    messages.append(msg)

            # Message courant — multimodal si images jointes
            if self._ref_images:
                import base64, os as _os
                _MT = {"jpg": "image/jpeg", "jpeg": "image/jpeg", "png": "image/png",
                       "webp": "image/webp", "gif": "image/gif"}
                cur_content: list = []
                for path in self._ref_images[:4]:
                    try:
                        with open(path, "rb") as fh:
                            data = base64.b64encode(fh.read()).decode()
                        ext = _os.path.splitext(path)[1].lower().lstrip(".")
                        mt  = _MT.get(ext, "image/jpeg")
                        cur_content.append({"type": "image",
                                            "source": {"type": "base64",
                                                       "media_type": mt,
                                                       "data": data}})
                    except Exception:
                        pass
                text_prefix = context_block + "\n\n" if not messages else ""
                cur_content.append({"type": "text",
                                    "text": text_prefix + self._user_message})
                messages.append({"role": "user", "content": cur_content})
            else:
                if not messages:
                    messages.append({
                        "role": "user",
                        "content": context_block + "\n\n" + self._user_message,
                    })
                else:
                    messages.append({"role": "user", "content": self._user_message})

            system = _arrange_session_chat_system(self._intensity, self._mode)

            # 16000 : la sortie contient le conducteur COMPLET réécrit —
            # même plafond que ApplyArrangeConducteurWorker (8192 tronquait).
            if self._ref_images:
                # VISION (images jointes) : direct Anthropic — hors couche ai_provider.
                import anthropic
                from core.config import load_config as _lc
                client = anthropic.Anthropic(api_key=_lc().get("anthropic_key", "").strip())
                response = client.messages.create(
                    model=_VISION_MODEL,
                    max_tokens=16000,
                    thinking=_VISION_NO_THINK,
                    system=system,
                    messages=messages,
                )
                raw = response.content[0].text.strip()
            else:
                raw = ai_chat(system, messages,
                              tier="creative", max_tokens=16000,
                              task="screenplay").strip()

            # Split sur les marqueurs
            chat_msg   = ""
            conducteur = ""
            if self._MARKER_DOC in raw:
                parts      = raw.split(self._MARKER_DOC, 1)
                conducteur = parts[1].strip()
                # Extraire le message du premier bloc
                first      = parts[0]
                if self._MARKER_MSG in first:
                    chat_msg = first.split(self._MARKER_MSG, 1)[1].strip()
                else:
                    chat_msg = first.strip()
            elif self._MARKER_MSG in raw:
                chat_msg = raw.split(self._MARKER_MSG, 1)[1].strip()
            else:
                # Réponse sans format — tout considéré comme message
                chat_msg = raw

            if chat_msg:
                self.message_ready.emit(chat_msg)
            if conducteur:
                self.screenplay_ready.emit(conducteur)

        except Exception as e:
            from core.worker import humanize_api_error
            self.failed.emit(humanize_api_error(str(e)))
