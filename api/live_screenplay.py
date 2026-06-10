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
  ultra-detailed, sharp, 4K). 3 à 5 phrases riches. VISUEL UNIQUEMENT — INTERDIT d'y mettre
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
- La géométrie de la façade reste identique ; seuls la lumière, les effets, les matières
  et le fond évoluent.

Pour CHAQUE plan, donne un objet JSON avec :
- "act": numéro de l'acte auquel ce plan appartient (entier, commence à 1).
- "act_name": nom court de l'acte, en français (ex: "Apparition", "Transformation", "Apogée", "Final").
- "action": ce qui se passe sur la façade pendant ce plan, en français (1 phrase).
- "shot_size": "" (non pertinent en mapping).
- "camera_movement": "Fixe".
- "duration": durée en secondes (entier entre 4 et 15).
- "prompt": prompt VIDÉO en ANGLAIS décrivant l'évolution sur la façade (sans mouvement de
  caméra), TRÈS DÉTAILLÉ et dense (Seedance 2.0 exploite un MAXIMUM de détails — ne sois PAS
  bref). Décris précisément : l'effet/visuel projeté, la lumière (direction, qualité,
  couleur), la palette, les textures & matières, ce qui évolue et comment, l'atmosphère/mood,
  le style, et des repères de qualité (cinematic, ultra-detailed, sharp, 4K). 3 à 5 phrases
  riches. VISUEL UNIQUEMENT — INTERDIT d'y mettre le BPM, un tempo, des chiffres musicaux,
  des instruments ou tout terme audio.
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
            from core.config import load_config
            key = load_config().get("anthropic_key", "").strip()
            if not key:
                self.failed.emit(
                    "Clé Anthropic (Claude) manquante — renseignez-la dans Paramètres "
                    "pour générer le découpage.")
                return
            import anthropic
            client = anthropic.Anthropic(api_key=key)
            system = _SYSTEM_MAPPING if self._mode == "mapping" else _SYSTEM_LIVE
            msg = client.messages.create(
                model="claude-sonnet-4-6",
                max_tokens=8000,
                system=system,
                messages=[{"role": "user", "content": text}],
            )
            out = "".join(
                block.text for block in msg.content if getattr(block, "type", "") == "text"
            )
            segments = [_normalize(s, self._mode) for s in _extract_json_array(out) if isinstance(s, dict)]
            if not segments:
                snippet = (out or "").strip()[:200].replace("\n", " ")
                self.failed.emit(
                    "Découpage vide — réponse Claude non exploitable. Réessayez.\n\n"
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
- cohérence sur la façade (géométrie inchangée ; seuls lumière, effets, matières évoluent) ;
- placement des moments forts et transitions SANS coupe entre actes.

Donne d'abord une ANALYSE claire, puis des SUGGESTIONS concrètes et numérotées.
Ne réécris pas tout le conducteur — tu PROPOSES. Réponds en français.
"""


class ArrangeConducteurStreamWorker(QThread):
    """Arrangement du conducteur en STREAMING (même interface que le worker Cinéma :
    signaux chunk/finished/failed) → alimente la fenêtre de co-écriture. Calibré Live/Mapping."""
    finished = pyqtSignal(str)
    failed   = pyqtSignal(str)
    chunk    = pyqtSignal(str)

    def __init__(self, text: str, mode: str, duration_secs: int = 0):
        super().__init__()
        self._text = text
        self._mode = mode if mode in ("live", "mapping") else "live"
        self._dur  = duration_secs

    def run(self):
        from core.config import load_config
        key = load_config().get("anthropic_key", "").strip()
        if not key:
            self.failed.emit("Clé Anthropic (Claude) manquante — renseignez-la dans Paramètres.")
            return
        try:
            import anthropic
            client = anthropic.Anthropic(api_key=key)
            system = _ARRANGE_MAPPING if self._mode == "mapping" else _ARRANGE_LIVE
            prefix = ""
            if self._dur > 0:
                mins, secs = divmod(self._dur, 60)
                dur_str = f"{mins}min {secs:02d}s" if mins else f"{secs}s"
                prefix = (f"[DURÉE CIBLE : {dur_str} = {self._dur} secondes. "
                          f"Tiens-en compte dans le rythme et la structure.]\n\n")
            full = ""
            with client.messages.stream(
                model="claude-sonnet-4-6",
                max_tokens=4096,
                system=system,
                messages=[{"role": "user", "content": prefix + self._text}],
            ) as stream:
                for t in stream.text_stream:
                    full += t
                    self.chunk.emit(t)
            self.finished.emit(full)
        except Exception as e:
            from core.worker import humanize_api_error
            self.failed.emit(humanize_api_error(str(e)))
