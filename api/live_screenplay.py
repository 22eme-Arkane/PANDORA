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


_SYSTEM_LIVE = """\
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
- "prompt": prompt VIDÉO en ANGLAIS pour un loop VJ, TRÈS DÉTAILLÉ et dense (Seedance 2.0
  exploite un MAXIMUM de détails — ne sois PAS bref). Commence par "Seamless VJ loop, " puis
  décris précisément : sujet + action, décor/environnement, composition & cadrage, lumière
  (direction, qualité, température), palette de couleurs, textures & matières, mouvement
  (ce qui bouge et comment), atmosphère/mood, style visuel, repères de qualité (cinematic,
  ultra-detailed, sharp, 4K). STRUCTURE TEMPORELLE EN BEATS RELATIFS : décris l'évolution
  dans l'ordre avec "opening:", "then", "building up", "in the final moment" — JAMAIS de
  timecode absolu ("at 3 seconds") : le moteur ne respecte pas les horodatages ; les impacts
  musicaux exacts sont gérés par les CUTS entre plans, pas à l'intérieur du clip.
  3 à 5 phrases riches. VISUEL UNIQUEMENT — INTERDIT d'y mettre
  le BPM, un tempo, des chiffres musicaux, des instruments ou tout terme audio.
- "sound_prompt": prompt SOUND DESIGN en ANGLAIS (SFX / ambiance, AUCUNE voix ni parole).
  C'est ICI — et seulement ici — que le BPM et les temps forts sont pris en compte.

Réponds UNIQUEMENT avec un tableau JSON de plans (aucun texte autour).
"""

_SYSTEM_MAPPING = """\
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

Pour CHAQUE plan, donne un objet JSON avec :
- "act": numéro de l'acte auquel ce plan appartient (entier, commence à 1).
- "act_name": nom court de l'acte, en français (ex: "Apparition", "Transformation", "Apogée", "Final").
- "action": ce qui se passe sur la façade pendant ce plan, en français (1 phrase).
- "shot_size": "" (non pertinent en mapping).
- "camera_movement": "Fixe".
- "duration": durée en secondes (entier entre 4 et 15).
- "prompt": prompt VIDÉO en ANGLAIS décrivant l'évolution projetée (sans mouvement de
  caméra), TRÈS DÉTAILLÉ et dense (Seedance 2.0 exploite un MAXIMUM de détails — ne sois PAS
  bref). COMMENCE par déclarer l'ÉTAT DE LA FAÇADE dans ce plan (ex: "the facade is fully
  covered by…", "the facade dissolves into darkness while…", "only the window frames glow…",
  "the building reappears, rebuilt out of…"). Puis décris précisément : l'effet/visuel
  projeté, la lumière (direction, qualité, couleur), la palette, les textures & matières,
  ce qui évolue et comment, l'atmosphère/mood, le style, et des repères de qualité
  (cinematic, ultra-detailed, sharp, 4K). STRUCTURE TEMPORELLE EN BEATS RELATIFS :
  décris l'évolution dans l'ordre avec "opening:", "then", "building up", "in the final
  moment" — JAMAIS de timecode absolu ("at 3 seconds") : le moteur ne respecte pas les
  horodatages ; les impacts musicaux exacts sont gérés par les CUTS entre plans.
  3 à 5 phrases riches. VISUEL UNIQUEMENT —
  INTERDIT d'y mettre le BPM, un tempo, des chiffres musicaux, des instruments ou tout
  terme audio.
- "sound_prompt": prompt SOUND DESIGN en ANGLAIS (SFX / ambiance, AUCUNE voix ni parole).
  C'est ICI — et seulement ici — que le BPM et les temps forts sont pris en compte.

Réponds UNIQUEMENT avec un tableau JSON de plans (aucun texte autour).
"""


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
    return {
        "action":          str(seg.get("action", "")).strip(),
        "shot_size":       "" if mode == "mapping" else str(seg.get("shot_size", "")).strip(),
        "camera_movement": "Fixe" if mode == "mapping" else str(mv).strip(),
        "duration":        dur,
        "prompt":          str(seg.get("prompt", "")).strip(),
        "sound_prompt":    str(seg.get("sound_prompt", "")).strip(),
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
            from core.ai_provider import complete, key_error, ai_name
            err = key_error()
            if err:
                self.failed.emit(err)
                return
            system = _SYSTEM_MAPPING if self._mode == "mapping" else _SYSTEM_LIVE
            # 16000 : un découpage dense (beaucoup de plans × prompts détaillés)
            # atteignait le plafond de 8000 → JSON tronqué
            out = complete(system, text, tier="creative", max_tokens=16000)
            segments = [_normalize(s, self._mode) for s in _extract_json_array(out) if isinstance(s, dict)]
            if not segments:
                snippet = (out or "").strip()[:200].replace("\n", " ")
                self.failed.emit(
                    f"Découpage vide — réponse {ai_name()} non exploitable. Réessayez.\n\n"
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

Réponds UNIQUEMENT avec le conducteur réécrit (aucun commentaire autour).
"""


class ApplyArrangeConducteurWorker(QThread):
    """Applique les suggestions d'arrangement au CONDUCTEUR (streaming).
    Remplace ApplyArrangeWorker (Cinéma) qui réécrivait au format scénario."""
    finished = pyqtSignal(str)
    failed   = pyqtSignal(str)
    chunk    = pyqtSignal(str)

    def __init__(self, original: str, suggestions: str, intensity: int = 5):
        super().__init__()
        self._original    = original
        self._suggestions = suggestions
        self._intensity   = max(1, min(10, intensity))

    def run(self):
        from core.ai_provider import stream, key_error
        err = key_error()
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
            # 16000 : sortie = conducteur COMPLET réécrit — 8192 tronquait les longs
            full = stream(_APPLY_ARRANGE_CONDUCTEUR, user, on_chunk=self.chunk.emit,
                          tier="creative", max_tokens=16000)
            self.finished.emit(full.strip())
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
        err = key_error()
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
                          tier="creative", max_tokens=8192)
            self.finished.emit(full)
        except Exception as e:
            from core.worker import humanize_api_error
            self.failed.emit(humanize_api_error(str(e)))
